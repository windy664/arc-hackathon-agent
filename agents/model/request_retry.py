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


def retry_delay(attempt: int) -> float:
    return min(2 ** attempt, 16) + random.uniform(0, 1)


async def request_async(call):
    attempts = int(positive_setting("ARC_MODEL_MAX_ATTEMPTS", 3))
    if attempts < 1:
        raise ValueError("ARC_MODEL_MAX_ATTEMPTS must be at least 1")
    timeout = positive_setting("ARC_MODEL_REQUEST_TIMEOUT", 120)
    for attempt in range(1, attempts + 1):
        try:
            return await asyncio.wait_for(call(), timeout=timeout)
        except Exception as exc:
            if attempt == attempts or not is_transient(exc):
                raise
            delay = retry_delay(attempt)
            # Never log request bodies, headers, or provider exception strings.
            logger.warning("Transient model request failure (%s); retry %d/%d in %.1fs",
                           type(exc).__name__, attempt + 1, attempts, delay)
            await asyncio.sleep(delay)


def request_sync(call):
    attempts = int(positive_setting("ARC_MODEL_MAX_ATTEMPTS", 3))
    if attempts < 1:
        raise ValueError("ARC_MODEL_MAX_ATTEMPTS must be at least 1")
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as exc:
            if attempt == attempts or not is_transient(exc):
                raise
            delay = retry_delay(attempt)
            logger.warning("Transient model request failure (%s); retry %d/%d in %.1fs",
                           type(exc).__name__, attempt + 1, attempts, delay)
            time.sleep(delay)
