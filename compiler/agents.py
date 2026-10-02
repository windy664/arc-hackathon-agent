"""A small parallel engineer team.

Concurrency equals team size (ARCBENCH_AGENTS, default 3) — not the task count.
Each engineer is a persistent agent: it keeps its own compacting conversation
(reusing the request prefix across its areas) and works a sequential queue of
UI areas. Reviews belong to reviewer agents with their own conversations.
"""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from .config import BUDGET
from .generate import FRONTEND_PAGE_PROMPT, SYSTEM_PROMPT, digest_requirements
from .integration import (
    area_scenario_digest,
    comp_name_for,
    digest_integration,
)
from .model import Conversation, ModelClient, extract_code, extract_json
from .visual import VISUAL_REVIEW_PROMPT

TEAM_SIZE = max(1, int(os.environ.get("ARCBENCH_AGENTS", "4")))


class EngineerAgent:
    def __init__(self, client: ModelClient, contract: dict, index: int,
                 integration: dict | None = None) -> None:
        self.index = index
        self.built = 0
        prefix = (
            f"You are engineer #{index + 1} on a small team generating a web "
            "application from structured requirements. The shared accessibility "
            "contract you must obey:\n"
            f"{json.dumps(contract, ensure_ascii=False)[:4000]}\n\n"
            f"{digest_integration(integration or {})}\n\n"
            "You will receive one UI area at a time. For each area return the "
            "complete component in a single fenced code block."
        )
        self.conv = Conversation(client, SYSTEM_PROMPT, prefix)

    def build(self, area: dict) -> tuple[dict, str, str]:
        comp = comp_name_for(area)
        prompt = FRONTEND_PAGE_PROMPT.format(
            comp=comp,
            area=area.get("key", "core"),
            reqs=digest_requirements(area.get("reqs", []), 12000),
            contract="already in your context; obey it",
        )
        scenarios = area_scenario_digest(area)
        if scenarios:
            prompt += (
                "\n\nScenario flows this area must support (tests follow these "
                f"exact paths and texts):\n{scenarios}"
            )
        code = extract_code(self.conv.ask(prompt, images=area.get("images") or None))
        self.built += 1
        return area, comp, code


class EngineerTeam:
    def __init__(self, client: ModelClient, contract: dict, size: int = TEAM_SIZE,
                 integration: dict | None = None) -> None:
        self.agents = [
            EngineerAgent(client, contract, i, integration) for i in range(size)
        ]

    def build_all(self, areas: list[dict]) -> list[tuple[dict, str, str]]:
        """Pull-based assignment: each engineer claims the next unclaimed area
        whenever it comes free. Fast workers take more work; nothing stalls
        behind a slow area. Results stay aligned with the input order.
        """
        queue: list[tuple[int, dict]] = list(enumerate(areas))
        lock = threading.Lock()
        results: dict[int, tuple[dict, str, str]] = {}

        def worker(agent: EngineerAgent) -> None:
            while True:
                with lock:
                    if not queue:
                        return
                    idx, area = queue.pop(0)
                if not BUDGET.allow():
                    results[idx] = (area, "", "")
                    continue
                results[idx] = agent.build(area)

        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = [pool.submit(worker, agent) for agent in self.agents]
            for fut in futures:
                fut.result()
        return [results[i] for i in range(len(areas))]


class ReviewerAgent:
    def __init__(self, client: ModelClient, index: int) -> None:
        self.index = index
        self.reviewed = 0
        prefix = (
            f"You are design reviewer #{index + 1}. You compare generated pages "
            "against reference screenshots and report concrete differences only."
        )
        self.conv = Conversation(client, SYSTEM_PROMPT, prefix)

    def review(self, area: dict, reference, screenshot) -> dict:
        prompt = VISUAL_REVIEW_PROMPT + (
            f"\n\nThis area covers requirement ids: "
            f"{', '.join(area.get('req_ids', [])[:6])}"
        )
        raw = self.conv.ask(prompt, images=[reference, screenshot])
        verdict = extract_json(raw)
        if not isinstance(verdict, dict):
            verdict = {
                "ok": False,
                "missing_or_wrong": ["visual review returned no parseable verdict"],
                "controls": [],
            }
        verdict.setdefault("ok", False)
        verdict.setdefault("missing_or_wrong", [])
        verdict.setdefault("controls", [])
        self.reviewed += 1
        return verdict


class ReviewerTeam:
    def __init__(self, client: ModelClient, size: int = 2) -> None:
        self.agents = [ReviewerAgent(client, i) for i in range(size)]

    def review_all(self, items: list[tuple[dict, object, object]]) -> list[dict]:
        """Pull-based assignment, same as the engineer team."""
        queue: list[tuple[int, tuple[dict, object, object]]] = list(enumerate(items))
        lock = threading.Lock()
        results: dict[int, dict] = {}

        def worker(agent: ReviewerAgent) -> None:
            while True:
                with lock:
                    if not queue:
                        return
                    idx, (area, reference, screenshot) = queue.pop(0)
                results[idx] = agent.review(area, reference, screenshot)

        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = [pool.submit(worker, agent) for agent in self.agents]
            for fut in futures:
                fut.result()
        return [results[i] for i in range(len(items))]
