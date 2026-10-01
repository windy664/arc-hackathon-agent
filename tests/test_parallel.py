import threading

from compiler.config import Budget
from compiler.generate import parallel_generate_pages
from compiler.model import ModelClient


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


def test_parallel_pages_keep_input_order(monkeypatch) -> None:
    monkeypatch.setenv("ARCBENCH_MOCK_MODEL", "1")
    from compiler import model as model_mod

    monkeypatch.setattr(model_mod, "MOCK_MODE", True)
    areas = [
        {"key": f"img-{i}.png", "reqs": [{"id": f"REQ-{i}", "name": f"Page{i}", "description": "x"}],
         "req_ids": [f"REQ-{i}"], "images": []}
        for i in range(6)
    ]
    results = parallel_generate_pages(model_mod.ModelClient(), areas, {"accessible_names": []})
    assert [a["key"] for a, _, _ in results] == [a["key"] for a in areas]
    comps = [comp for _, comp, _ in results]
    assert comps == ["Page0", "Page1", "Page2", "Page3", "Page4", "Page5"]
    assert all(code for _, _, code in results)
