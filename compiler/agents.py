"""A small parallel engineer team.

Concurrency equals team size (ARCBENCH_AGENTS, default 3) — not the task count.
Each engineer is a persistent agent: it keeps its own compacting conversation
(reusing the request prefix across its areas) and works a sequential queue of
UI areas. Reviews belong to reviewer agents with their own conversations.
"""

from __future__ import annotations

import json
import os
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

TEAM_SIZE = max(1, int(os.environ.get("ARCBENCH_AGENTS", "3")))


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
        """Chunk areas among agents; agents run side by side, queues stay serial."""
        n = len(self.agents)
        chunks = [areas[i::n] for i in range(n)]
        collected: list[tuple[dict, str, str]] = []
        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = [
                pool.submit(self._run_queue, agent, chunk)
                for agent, chunk in zip(self.agents, chunks)
            ]
            for fut in futures:
                collected.extend(fut.result())
        order = {id(a): i for i, a in enumerate(areas)}
        collected.sort(key=lambda r: order[id(r[0])])
        return collected

    def _run_queue(self, agent: EngineerAgent,
                   chunk: list[dict]) -> list[tuple[dict, str, str]]:
        out = []
        for area in chunk:
            if not BUDGET.allow():
                out.append((area, "", ""))
                continue
            out.append(agent.build(area))
        return out


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
        n = len(self.agents)
        chunks = [items[i::n] for i in range(n)]
        collected: list[tuple[int, dict]] = []
        with ThreadPoolExecutor(max_workers=n) as pool:
            futures = []
            for agent, chunk in zip(self.agents, chunks):
                futures.append(pool.submit(self._run_queue, agent, chunk))
            for fut in futures:
                collected.extend(fut.result())
        collected.sort(key=lambda r: r[0])
        return [verdict for _, verdict in collected]

    def _run_queue(self, agent: ReviewerAgent,
                   chunk: list[tuple[dict, object, object]]) -> list[tuple[int, dict]]:
        out = []
        for item in chunk:
            area, reference, screenshot = item
            out.append((id(area), agent.review(area, reference, screenshot)))
        return out
