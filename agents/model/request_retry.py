"""Bounded retries for transport failures, including mislabelled proxy HTTP 400s."""
from __future__ import annotations

import asyncio
import logging
import os
import random
import time

import httpx
from openai import APIConnectionError, APITimeoutError

logger = logging.getLogger(__name__)


def positive_setting(name: str, default: float) -> float:
    import math
    value = float(os.environ.get(name, default))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return value


def is_transient(exc: BaseException) -> bool:
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, (APIConnectionError, APITimeoutError, httpx.TransportError, TimeoutError)):
            return True
        status = getattr(exc, "status_code", None)
        if status in (408, 429, 500, 502, 503, 504):
            return True
        # Some gateways incorrectly encode upstream connection failures as 400.
        # Require BOTH the proxy error code and a transport-specific message.
        body = getattr(exc, "body", None)
        error = body.get("error", body) if isinstance(body, dict) else {}
        if isinstance(error, dict) and status == 400 and error.get("code") == "proxy_error":
            message = str(error.get("message", "")).lower()
            if any(marker in message for marker in (
                "connection reset by peer", "connection refused", "connection closed",
                "timed out", "timeout", "unexpected eof",
            )):
                return True
        exc = getattr(exc, "original", None) or exc.__cause__ or exc.__context__
    return False


def _status_code(exc: BaseException) -> int | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        status = getattr(current, "status_code", None)
        if isinstance(status, int):
            return status
        current = getattr(current, "original", None) or current.__cause__ or current.__context__
    return None


def retry_delay(attempt: int, exc: BaseException | None = None) -> float:
    if exc is not None and _status_code(exc) == 429:
        # A short retry is ineffective when a provider reports engine overload.
        # Honor Retry-After when present; otherwise use a bounded cooldown.
        current: BaseException | None = exc
        headers = None
        while current is not None:
            response = getattr(current, "response", None)
            headers = getattr(response, "headers", None)
            if headers:
                break
            current = getattr(current, "original", None) or current.__cause__ or current.__context__
        try:
            retry_after = float(headers.get("retry-after")) if headers else 0
        except (TypeError, ValueError):
            retry_after = 0
        if retry_after > 0:
            return min(retry_after, 120) + random.uniform(0, 1)
        return min(15 * (2 ** (attempt - 1)), 90) + random.uniform(0, 2)
    return min(2 ** attempt, 16) + random.uniform(0, 1)


async def request_async(call):
    attempts = int(positive_setting("ARC_MODEL_MAX_ATTEMPTS", 2))
    if attempts < 1:
        raise ValueError("ARC_MODEL_MAX_ATTEMPTS must be at least 1")
    # Larger reasoning models can legitimately take several minutes on a
    # long tool-using request. Keep the timeout bounded, but don't discard a
    # Kimi/other provider response at the previous five-minute mark.
    timeout = positive_setting("ARC_MODEL_REQUEST_TIMEOUT", 600)
    rate_limit_attempts = int(positive_setting("ARC_MODEL_RATE_LIMIT_ATTEMPTS", 4))
    if rate_limit_attempts < 1:
        raise ValueError("ARC_MODEL_RATE_LIMIT_ATTEMPTS must be at least 1")
    attempt = 0
    while True:
        attempt += 1
        try:
            return await asyncio.wait_for(call(), timeout=timeout)
        except Exception as exc:
            limit = rate_limit_attempts if _status_code(exc) == 429 else attempts
            if attempt >= limit or not is_transient(exc):
                raise
            delay = retry_delay(attempt, exc)
            # Never log request bodies, headers, or provider exception strings.
            logger.warning("Transient model request failure (%s); retry %d/%d in %.1fs",
                           type(exc).__name__, attempt + 1, limit, delay)
            await asyncio.sleep(delay)


def request_sync(call):
    attempts = int(positive_setting("ARC_MODEL_MAX_ATTEMPTS", 2))
    if attempts < 1:
        raise ValueError("ARC_MODEL_MAX_ATTEMPTS must be at least 1")
    rate_limit_attempts = int(positive_setting("ARC_MODEL_RATE_LIMIT_ATTEMPTS", 4))
    if rate_limit_attempts < 1:
        raise ValueError("ARC_MODEL_RATE_LIMIT_ATTEMPTS must be at least 1")
    attempt = 0
    while True:
        attempt += 1
        try:
            return call()
        except Exception as exc:
            limit = rate_limit_attempts if _status_code(exc) == 429 else attempts
            if attempt >= limit or not is_transient(exc):
                raise
            delay = retry_delay(attempt, exc)
            logger.warning("Transient model request failure (%s); retry %d/%d in %.1fs",
                           type(exc).__name__, attempt + 1, limit, delay)
            time.sleep(delay)
