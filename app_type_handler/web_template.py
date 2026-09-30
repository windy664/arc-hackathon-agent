"""Targeted repairs for known ARC-Bench web scaffold defects."""
from pathlib import Path


_BROKEN_CACHE_BRANCH = """  if (initPromise) {
    return initPromise;
  }

  const database = getDb();
  initPromise = (async () => {"""

_FIXED_CACHE_BRANCH = """  if (initPromise) {
    await initPromise;
    return getDb();
  }

  const database = getDb();
  initPromise = (async () => {"""


def repair_sqlite_initialization(workspace_path: str) -> bool:
    """Fix the stock cached-promise branch without replacing application code.

    ARC-Bench pre-populates the output directory, so changes to our bundled
    template alone do not reach those workspaces. Match the known SQLite
    scaffold and preserve any schema or other changes from earlier stages.
    """
    workspace = Path(workspace_path).resolve()
    target = workspace / "backend/src/database/init_db.js"
    if not target.is_file() or not target.resolve().is_relative_to(workspace):
        return False
    content = target.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in content else "\n"
    normalized = content.replace("\r\n", "\n")
    if not all(marker in normalized for marker in (
        "const sqlite3 = require('sqlite3').verbose();",
        "async function initializeDatabase(options = {}) {",
        "function getDb() {\n  if (!db) {\n    ensureDbDirectory(currentDbPath);\n"
        "    db = new sqlite3.Database(currentDbPath);\n  }\n  return db;\n}",
    )) or normalized.count(_BROKEN_CACHE_BRANCH) != 1:
        return False
    fixed = normalized.replace(_BROKEN_CACHE_BRANCH, _FIXED_CACHE_BRANCH, 1)
    target.write_bytes(fixed.replace("\n", newline).encode("utf-8"))
    return True
