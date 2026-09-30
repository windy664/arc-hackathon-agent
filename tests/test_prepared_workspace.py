import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app_type_handler.web import WebAppType
from app_type_handler.web_template import repair_sqlite_initialization


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "arc-template/templates/web-react-express"
INIT_DB = Path("backend/src/database/init_db.js")


def legacy_scaffold():
    source = (TEMPLATE / INIT_DB).read_text()
    start = source.index("  if (initPromise) {")
    end = source.index("\n\n  const database = getDb();", start)
    return source[:start] + "  if (initPromise) {\n    return initPromise;\n  }" + source[end:]


class PreparedWorkspaceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.workspace = Path(temp.name)
        self.database_file = self.workspace / INIT_DB
        self.database_file.parent.mkdir(parents=True)
        self.database_file.write_text(legacy_scaffold())
        self.log = AsyncMock()
        self.handler = WebAppType(
            workspace_path=str(self.workspace), requirement_path="", interface_designer=None,
            log_cb=self.log,
        )

    async def test_prepared_workspace_is_repaired_without_copying_template(self):
        existing = self.workspace / "frontend/src/App.tsx"
        existing.parent.mkdir(parents=True)
        existing.write_text("// existing application\n")
        with patch.object(self.handler, "check_prerequisites", AsyncMock(return_value=True)), \
             patch.object(self.handler, "copy_template", AsyncMock()) as copy_template, \
             patch.object(self.handler, "post_template_setup", AsyncMock()) as setup, \
             patch.object(self.handler, "install_dependencies", AsyncMock()):
            self.assertTrue(await self.handler.initialize_workspace(seed_template=False))
        copy_template.assert_not_called()
        setup.assert_not_called()
        self.assertIn("await initPromise;\n    return getDb();", self.database_file.read_text())
        self.assertEqual(existing.read_text(), "// existing application\n")

    async def test_resume_repairs_schema_from_interrupted_generation(self):
        from core.workflow import ARCWorkflowManager
        schema = "    await runStatement(database, 'CREATE TABLE IF NOT EXISTS accounts (id INTEGER)');"
        content = legacy_scaffold().replace(
            "    await runStatement(database, 'PRAGMA foreign_keys = ON;');", schema,
        )
        self.database_file.write_text(content)
        manager = object.__new__(ARCWorkflowManager)
        manager.workspace_path = str(self.workspace)
        manager.requirement_path = ""
        manager.app_type = "web"
        manager.web_port = 3301
        manager.arc_dir = str(self.workspace / ".arc")
        manager.project_metadata_path = str(self.workspace / ".arc/project.json")
        manager.interface_designer = None
        manager.log_cb = self.log
        runtime = Mock()
        with patch.dict(os.environ), \
             patch("core.workflow.set_workspace_root"), \
             patch("core.workflow.set_app_type"), \
             patch("core.workflow.set_web_port"), \
             patch("core.workflow.configure_runtime", return_value=runtime), \
             patch("core.workflow.read_json_file", return_value={"workspace_mode": "evolution"}):
            await manager.prepare_resume_context()
        repaired = self.database_file.read_text()
        self.assertIn(schema, repaired)
        self.assertIn("await initPromise;\n    return getDb();", repaired)
        runtime.events.mark_run_resumed.assert_called_once()

    def test_repair_is_idempotent_and_preserves_crlf(self):
        self.database_file.write_bytes(legacy_scaffold().replace("\n", "\r\n").encode())
        self.assertTrue(repair_sqlite_initialization(str(self.workspace)))
        repaired = self.database_file.read_bytes()
        self.assertNotIn(b"\n", repaired.replace(b"\r\n", b""))
        self.assertFalse(repair_sqlite_initialization(str(self.workspace)))
        self.assertEqual(self.database_file.read_bytes(), repaired)

    def test_custom_initializer_is_preserved(self):
        source = "async function initializeDatabase() { return customDatabase; }\n"
        self.database_file.write_text(source)
        self.assertFalse(repair_sqlite_initialization(str(self.workspace)))
        self.assertEqual(self.database_file.read_text(), source)

    def test_fixed_template_is_preserved(self):
        source = (TEMPLATE / INIT_DB).read_bytes()
        self.database_file.write_bytes(source)
        self.assertFalse(repair_sqlite_initialization(str(self.workspace)))
        self.assertEqual(self.database_file.read_bytes(), source)

    def test_external_symlink_is_preserved(self):
        with TemporaryDirectory() as outside:
            target = Path(outside) / "init_db.js"
            original = legacy_scaffold()
            target.write_text(original)
            self.database_file.unlink()
            self.database_file.symlink_to(target)
            self.assertFalse(repair_sqlite_initialization(str(self.workspace)))
            self.assertEqual(target.read_text(), original)


if __name__ == "__main__":
    unittest.main()
