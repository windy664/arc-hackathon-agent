import json
import os
from pathlib import Path
import shlex
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import ToolMessage

from agents.runtime.stage_discipline import StageDisciplineMiddleware
from app_type_handler.test_results import parse_test_results
from app_type_handler.web import WebAppType, _execute_web_test_command


class WebRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.handler = WebAppType(
            workspace_path=str(self.root), requirement_path="",
            interface_designer=None, log_cb=AsyncMock(),
        )
        self.test_file = "backend/test-e2e/auth/registration.spec.js"
        self.build = self.patch_async("_build_frontend_dist", (True, "Exit Code: 0\nBuild OK"))
        self.prepare = self.patch_async("_prepare_e2e_database", (True, "Exit Code: 0\nDB OK"))
        self.start = self.patch_async("_start_backend_runtime", (object(), "npm start", "ready", "instance"))
        self.execute = self.patch_async("_execute_web_test_command", "Exit Code: 0\nTests passed")
        self.cleanup = self.patch_async("_terminate_process", "stopped")
        port_patch = patch("core.config._web_port", 3397)
        port_patch.start()
        self.addCleanup(port_patch.stop)

    def patch_async(self, name, result):
        patcher = patch(f"app_type_handler.web.{name}", AsyncMock(return_value=result))
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    async def run_e2e(self, grouped):
        if grouped:
            return await self.handler.run_test_group("E2E", [self.test_file])
        return await self.handler.run_test_file("E2E", self.test_file)

    def assert_status(self, output, expected):
        # Both the compiler and the file-read guard must agree on the result.
        self.assertEqual(parse_test_results(output)["exit_code"], expected, output)
        guard = StageDisciplineMiddleware(stage="implementation")
        path = "/workspace/backend/src/database/init_db.js"
        guard._written_paths.add(path)
        self.assertIsNotNone(guard._validate_read({"file_path": path}))
        guard._record_result(
            SimpleNamespace(tool_call={"name": "run_tests", "args": {}}),
            ToolMessage(content=output, tool_call_id="test"),
        )
        if expected:
            self.assertIsNone(guard._validate_read({"file_path": path}))
        else:
            self.assertIsNotNone(guard._validate_read({"file_path": path}))

    async def test_database_failure_is_not_masked_by_successful_build(self):
        self.prepare.return_value = (False, "Exit Code: 1\nCannot read properties of undefined (reading 'exec')")
        for grouped in (False, True):
            with self.subTest(grouped=grouped):
                self.assert_status(await self.run_e2e(grouped), 1)
        self.start.assert_not_awaited()
        self.execute.assert_not_awaited()

    async def test_missing_build_artifact_fails_even_when_build_command_succeeded(self):
        self.build.return_value = (False, "Exit Code: 0\nMissing frontend/dist/index.html")
        for grouped in (False, True):
            with self.subTest(grouped=grouped):
                self.assert_status(await self.run_e2e(grouped), 1)
        self.prepare.assert_not_awaited()
        self.execute.assert_not_awaited()

    async def test_backend_start_failure_is_not_masked_by_preparation_success(self):
        self.start.return_value = (None, "npm start", "Backend exited", "")
        for grouped in (False, True):
            with self.subTest(grouped=grouped):
                self.assert_status(await self.run_e2e(grouped), 1)
        self.execute.assert_not_awaited()

    async def test_playwright_failure_or_timeout_is_not_masked_by_preparation_success(self):
        for grouped in (False, True):
            for result in ("Exit Code: 1\n1 failed", "Command timed out after 120 seconds."):
                with self.subTest(grouped=grouped, result=result):
                    self.execute.return_value = result
                    self.assert_status(await self.run_e2e(grouped), 1)
        self.assertEqual(self.cleanup.await_count, 4)

    async def test_cleanup_failure_is_not_reported_as_passed(self):
        self.cleanup.side_effect = RuntimeError("could not stop backend")
        for grouped in (False, True):
            with self.subTest(grouped=grouped):
                self.assert_status(await self.run_e2e(grouped), 1)

    async def test_success_uses_same_origin_and_database_for_backend_and_playwright(self):
        for grouped in (False, True):
            with self.subTest(grouped=grouped):
                output = await self.run_e2e(grouped)
                self.assert_status(output, 0)
                runtime_env = self.start.call_args.args[1]
                self.assertEqual(self.prepare.call_args.args[1], runtime_env)
                self.assertEqual(self.execute.call_args.kwargs["extra_env"], runtime_env)
                self.assertEqual(runtime_env["PORT"], "3397")
                self.assertEqual(runtime_env["PLAYWRIGHT_BASE_URL"], "http://localhost:3397")
                self.assertEqual(runtime_env["ARC_WEB_BASE_URL"], runtime_env["PLAYWRIGHT_BASE_URL"])
                self.assertEqual(parse_test_results(output)["sub_batches"][0]["exit_code"], 0)
        self.assertEqual(self.cleanup.await_count, 2)

    async def test_vitest_mixed_results_allow_failure_investigation(self):
        self.execute.side_effect = ["Exit Code: 1\nFAIL backend", "Exit Code: 0\nPASS frontend"]
        output = await self.handler.run_test_group("Unit", [
            "backend/tests/auth/service.test.js", "frontend/tests/auth/session.test.tsx",
        ])
        self.assert_status(output, 1)

    async def test_run_build_reports_failure_in_either_component(self):
        for codes in ((0, 1), (1, 0), (0, 0)):
            with self.subTest(codes=codes):
                self.execute.side_effect = [f"Exit Code: {code}\nBuild result" for code in codes]
                self.assert_status(await self.handler.run_build(), int(any(codes)))


class RuntimeEnvironmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_child_process_overrides_stale_platform_base_urls(self):
        # Exercise the real subprocess environment, without npm, a model, or a server.
        script = "import os,json; print(json.dumps({k:os.environ[k] for k in ('PORT','PLAYWRIGHT_BASE_URL','ARC_WEB_BASE_URL')}))"
        import sys
        with TemporaryDirectory() as root, patch("core.config._web_port", 3397), patch.dict(os.environ, {
            "PLAYWRIGHT_BASE_URL": "http://127.0.0.1:3000",
            "ARC_WEB_BASE_URL": "http://127.0.0.1:3000",
        }):
            result = await _execute_web_test_command(
                f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}", cwd=root,
            )
        self.assertEqual(parse_test_results(result)["exit_code"], 0, result)
        runtime_env = json.loads(result.split("STDOUT:\n", 1)[1])
        self.assertEqual(runtime_env, {
            "PORT": "3397", "PLAYWRIGHT_BASE_URL": "http://localhost:3397",
            "ARC_WEB_BASE_URL": "http://localhost:3397",
        })


if __name__ == "__main__":
    unittest.main()
