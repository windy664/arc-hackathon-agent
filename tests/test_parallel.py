import threading

from compiler.agents import EngineerTeam, ReviewerTeam
from compiler.config import Budget


def test_budget_is_thread_safe() -> None:
    b = Budget()
    errors = []

    def worker() -> None:
        try:
            for _ in range(20):
                b.note({"total_tokens": 10})
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert b.requests == 200
    assert b.tokens == 2000


def _areas(n: int) -> list[dict]:
    return [
        {"key": f"img-{i}.png",
         "reqs": [{"id": f"REQ-{i}", "name": f"Page{i}", "description": "x"}],
         "req_ids": [f"REQ-{i}"], "images": []}
        for i in range(n)
    ]


def test_engineer_team_chunks_queues_and_preserves_order(monkeypatch) -> None:
    monkeypatch.setenv("ARCBENCH_MOCK_MODEL", "1")
    from compiler import model as model_mod

    monkeypatch.setattr(model_mod, "MOCK_MODE", True)
    areas = _areas(6)
    team = EngineerTeam(model_mod.ModelClient(), {"accessible_names": []}, size=3)
    results = team.build_all(areas)

    # order aligned with input
    assert [a["key"] for a, _, _ in results] == [a["key"] for a in areas]
    # each engineer owns a disjoint sequential queue (2 of 6)
    assert sorted(agent.built for agent in team.agents) == [2, 2, 2]
    # persistent conversations still produce per-area component names
    assert [comp for _, comp, _ in results] == [f"Page{i}" for i in range(6)]
    assert all(code for _, _, code in results)


def test_reviewer_team_chunks_and_orders(monkeypatch) -> None:
    monkeypatch.setenv("ARCBENCH_MOCK_MODEL", "1")
    from compiler import model as model_mod

    monkeypatch.setattr(model_mod, "MOCK_MODE", True)
    from pathlib import Path

    fake = Path(".")
    items = [({"req_ids": [f"REQ-{i}"]}, fake, fake) for i in range(5)]
    team = ReviewerTeam(model_mod.ModelClient(), size=2)
    verdicts = team.review_all(items)
    assert len(verdicts) == 5
    assert all(v.get("ok") is True for v in verdicts)
    assert sorted(a.reviewed for a in team.agents) == [2, 3]
