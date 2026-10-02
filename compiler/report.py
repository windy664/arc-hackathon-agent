"""Per-requirement progress and traceability reporting through the ARC SDK.

Every call is defensive: reporting problems must never break generation.
Follows the official runtime-signals contract (design/implement/test states per
node id, interfaces and tests in .arc/traceability).
"""

from __future__ import annotations

from pathlib import Path


def ancestors(req_id: str) -> list[str]:
    """REQ-1-1-1 -> [REQ-1-1-1, REQ-1-1, REQ-1, ROOT]."""
    if req_id == "ROOT":
        return ["ROOT"]
    ids = [req_id]
    cur = req_id
    while "-" in cur[4:]:
        cur = cur.rsplit("-", 1)[0]
        ids.append(cur)
    ids.append("ROOT")
    return ids


class Reporter:
    def __init__(self, out: Path) -> None:
        self.rt = None
        try:
            from arcbench_agent_runtime import AgentRuntime

            self.rt = AgentRuntime.from_env(project_dir=str(out))
            self.rt.traceability.init_db()
        except Exception:
            self.rt = None

    def _events(self, name: str, *args) -> None:
        if not self.rt:
            return
        try:
            fn = getattr(self.rt.events, name, None)
            if fn:
                fn(*args)
        except Exception:
            pass

    def _trace(self, fn_name: str, *args, **kwargs) -> None:
        if not self.rt:
            return
        try:
            fn = getattr(self.rt.traceability, fn_name, None)
            if fn:
                fn(*args, **kwargs)
        except Exception:
            pass

    def store_tree(self, tree: dict) -> None:
        self._trace("store_requirement_tree", tree)

    def run_started(self, message: str) -> None:
        self._events("mark_run_started", message)

    def run_completed(self, message: str) -> None:
        self._events("mark_run_completed", message)

    def run_failed(self, message: str) -> None:
        self._events("mark_run_failed", message)

    def _for_all(self, req_ids: list[str], event: str, message: str) -> None:
        seen: set[str] = set()
        for rid in req_ids:
            for nid in ancestors(rid):
                if nid not in seen:
                    seen.add(nid)
                    self._events(event, nid, message)

    def design_started(self, req_ids: list[str], message: str) -> None:
        self._for_all(req_ids, "mark_design_started", message)

    def design_done(self, req_ids: list[str], message: str) -> None:
        self._for_all(req_ids, "mark_design_done", message)

    def implement_started(self, req_ids: list[str], message: str) -> None:
        self._for_all(req_ids, "mark_implementation_started", message)

    def implement_done(self, req_ids: list[str], message: str) -> None:
        self._for_all(req_ids, "mark_implementation_done", message)

    def test_passed(self, req_ids: list[str], message: str) -> None:
        self._for_all(req_ids, "mark_test_passed", message)
        for rid in req_ids:
            self._trace("upsert_node_state", rid, "PASSED", "test")

    def test_failed(self, req_ids: list[str], message: str) -> None:
        self._for_all(req_ids, "mark_test_failed", message)
        for rid in req_ids:
            self._trace("upsert_node_state", rid, "FAILED", "test")

    def interface(self, interface_id: str, req_ids: list[str], content: str,
                  file_path: str) -> None:
        self._trace(
            "upsert_interface",
            interface_id=interface_id,
            req_ids=req_ids,
            type="ui",
            content=content,
            file_path=file_path,
        )
        self._trace("set_interface_implemented", interface_id)
