import asyncio
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx
from openai import BadRequestError
from langchain_openai import ChatOpenAI

from agents.model.request_retry import is_transient, request_async, request_sync
from agents.model.openai_api_adapter import build_openai_chat_model, ARCModelAPIError
from agents.runtime.runners import _try_astream_stage_agent
from types import SimpleNamespace


def provider_error(code="proxy_error", message="read: connection reset by peer"):
    return BadRequestError("provider error", response=httpx.Response(
        400, request=httpx.Request("POST", "https://example.test/v1/chat/completions")),
        body={"error": {"code": code, "message": message}})


class RetryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "ARC_MODEL_MAX_ATTEMPTS": "3", "ARC_MODEL_REQUEST_TIMEOUT": "1"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    async def test_proxy_400_recovers_without_replaying_stage(self):
        call = AsyncMock(side_effect=[provider_error(), provider_error(), "ok"])
        with patch("agents.model.request_retry.retry_delay", return_value=0):
            self.assertEqual(await request_async(call), "ok")
        self.assertEqual(call.await_count, 3)

    async def test_bad_parameters_are_not_retried(self):
        for error in [provider_error("invalid_request_error", "invalid model"),
                      provider_error("proxy_error", "invalid request schema")]:
            call = AsyncMock(side_effect=error)
            with self.assertRaises(BadRequestError):
                await request_async(call)
            self.assertEqual(call.await_count, 1)

    async def test_exhaustion_is_bounded(self):
        call = AsyncMock(side_effect=provider_error())
        with patch("agents.model.request_retry.retry_delay", return_value=0):
            with self.assertRaises(BadRequestError):
                await request_async(call)
        self.assertEqual(call.await_count, 3)

    async def test_timeout_cancels_requests(self):
        cancelled = []
        async def hang():
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)
        with patch.dict(os.environ, {"ARC_MODEL_REQUEST_TIMEOUT": "0.01"}), \
             patch("agents.model.request_retry.retry_delay", return_value=0):
            with self.assertRaises(TimeoutError):
                await request_async(hang)
        self.assertEqual(len(cancelled), 3)

    async def test_cancellation_does_not_retry(self):
        call = AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await request_async(call)
        self.assertEqual(call.await_count, 1)

    async def test_adapter_retries_and_normalizes_final_error(self):
        model = build_openai_chat_model("test", base_url="https://example.test/v1", api_key="dummy")
        self.assertEqual(model.max_retries, 0)
        self.assertEqual(model.request_timeout, 1)
        with patch.object(ChatOpenAI, "_agenerate", new_callable=AsyncMock) as generate, \
             patch("agents.model.request_retry.retry_delay", return_value=0):
            generate.side_effect = provider_error()
            with self.assertRaises(ARCModelAPIError) as error:
                await model._agenerate([])
            self.assertTrue(is_transient(error.exception))
            self.assertEqual(generate.await_count, 3)

    def test_sync_path_retries(self):
        call = Mock(side_effect=[provider_error(), "ok"])
        with patch("agents.model.request_retry.time.sleep"):
            self.assertEqual(request_sync(call), "ok")
        self.assertEqual(call.call_count, 2)

    async def test_model_failure_does_not_trigger_stage_fallback(self):
        error = ARCModelAPIError("exhausted", api_mode="chat_completions", model="test")
        async def events(*args, **kwargs):
            raise error
            yield
        agent = SimpleNamespace(astream_events=events)
        context = SimpleNamespace(node_id="REQ-2-1-1")
        with self.assertRaises(ARCModelAPIError):
            await _try_astream_stage_agent(agent, message="test", context=context,
                thread_id="test", run_label="TestGenerator", log_cb=None, logger=None)

    async def test_interrupted_workflow_saves_queue_for_resume(self):
        from core.workflow import ARCWorkflowManager
        manager = object.__new__(ARCWorkflowManager)
        task = {"task_id": "design-1", "node_id": "REQ-1", "phase": "DESIGN", "status": "PENDING"}
        queue = {"tasks": [task], "node_states": {"REQ-1": "UNSEEN"}}
        manager.runtime = Mock()
        manager._load_or_create_processing_queue = Mock(return_value=queue)
        manager._sync_queue_node_states = Mock()
        manager._recover_interrupted_queue = Mock(return_value=[])
        manager._apply_retry_plan = Mock(return_value=[])
        manager._append_test_generation_task = Mock(return_value=None)
        manager._append_incremental_requirement_tasks = Mock(return_value=[])
        snapshots = []
        import copy
        manager._save_processing_queue = Mock(side_effect=lambda q: snapshots.append(copy.deepcopy(q)))
        manager._mark_task_running = Mock()
        manager._log = AsyncMock()
        error = ARCModelAPIError("exhausted", api_mode="chat_completions", model="test")
        manager._run_task = AsyncMock(side_effect=error)
        # A platform-owned variable with the previous generic name must not
        # shorten ARC's stage deadline and bypass the model retry policy.
        with patch.dict(os.environ, {"ARC_PHASE_TIMEOUT": "0.001"}):
            with self.assertRaises(ARCModelAPIError):
                await manager.compile_requirement_tree({"id": "ROOT"})
        self.assertEqual(snapshots[-1]["tasks"][0]["status"], "RUNNING")
        self.assertEqual(snapshots[-1]["tasks"][0]["last_error"], "ARCModelAPIError")
        manager.runtime.events.mark_run_failed.assert_called_once()
        manager.runtime.events.mark_test_passed.assert_not_called()
        # Exercise the existing recovery path, which retains the workspace.
        manager.runtime.git.status_porcelain.return_value = " M frontend/src/App.tsx"
        with patch("core.workflow.sessions.merge_node_session"):
            recovered = ARCWorkflowManager._recover_interrupted_queue(manager, queue)
        self.assertEqual(task["status"], "PENDING")
        self.assertEqual(recovered[0]["node_id"], "REQ-1")


if __name__ == "__main__":
    unittest.main()
