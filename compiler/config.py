"""Budget guards, logging, and platform SDK event bridge."""

from __future__ import annotations

import os
import threading
import time

# Defaults follow the leaderboard's normal mid-table band (aggregate view):
# teams at 36-66% pass spend ~11-20 CNY per run (~10-20M tokens on flash).
# The burn zone is an order of magnitude above: one 116M-token run -> 478 CNY -> 402.
# Requests cover the tree-driven walk: per-folder design + backend + pages +
# reviews + one bounded repair round.
MAX_REQUESTS = int(os.environ.get("ARCBENCH_MAX_MODEL_REQUESTS", "48"))
MAX_TOTAL_TOKENS = int(os.environ.get("ARCBENCH_MAX_TOTAL_TOKENS", "20000000"))
MAX_SECONDS = int(os.environ.get("ARCBENCH_MAX_SECONDS", "5400"))
MAX_OUTPUT_TOKENS = 12000
REQUEST_TIMEOUT = 100
MAX_ATTEMPTS = 2

MAX_CONVERSATION_CHARS = 100_000
MAX_EXCHANGE_SUMMARY_CHARS = 900
MAX_REPAIR_AREAS = 6

UI_EXTS = {".tsx", ".ts", ".jsx", ".js", ".css", ".html"}


class Budget:
    def __init__(self) -> None:
        self.start = time.time()
        self.requests = 0
        self.tokens = 0
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self.requests >= MAX_REQUESTS:
                return False
            if self.tokens >= MAX_TOTAL_TOKENS:
                return False
        return (time.time() - self.start) < MAX_SECONDS

    def time_left(self) -> float:
        return MAX_SECONDS - (time.time() - self.start)

    def note(self, usage: dict) -> None:
        with self._lock:
            self.requests += 1
            if isinstance(usage, dict):
                self.tokens += int(usage.get("total_tokens") or 0)

    def status(self) -> str:
        with self._lock:
            requests, tokens = self.requests, self.tokens
        return (
            f"requests={requests}/{MAX_REQUESTS} "
            f"tokens={tokens}/{MAX_TOTAL_TOKENS} "
            f"elapsed={int(time.time() - self.start)}s"
        )


BUDGET = Budget()


def log(msg: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def sdk_event(name: str, detail: str) -> None:
    try:
        from arcbench_agent_runtime import AgentRuntime

        runtime = AgentRuntime.from_env()
        fn = getattr(runtime.events, name, None)
        if fn:
            fn(detail)
    except Exception:
        pass
