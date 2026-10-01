"""Structural guard for model-generated patch scripts (defense in depth).

Layer 1: AST parse — reject syntactically invalid scripts without executing.
Layer 2: policy — imports restricted to an allowlist, destructive calls banned.
Layer 3: runtime — caller runs the script with cwd + timeout + file backup and
validates the result (see repair.run_patch_script).

The point is structural: even a fully confused or prompt-injected model cannot
reach network, subprocess, or other files through the patch channel.
"""

from __future__ import annotations

import ast

ALLOWED_IMPORTS = {"pathlib", "re", "typing"}

BANNED_CALLS = {
    "eval", "exec", "compile", "__import__", "open", "input",
    "breakpoint", "globals", "locals", "vars", "getattr", "setattr", "delattr",
}

BANNED_ATTRS = {
    "system", "popen", "spawn", "spawnl", "spawnle", "spawnlp", "spawnlpe",
    "spawnv", "spawnve", "spawnvp", "spawnvpe", "fork", "execl", "execle",
    "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
    "unlink", "rmdir", "rmtree", "chmod", "chown", "chownr", "remove",
    "connect", "urlopen", "request", "check_output", "check_call", "run",
    "Popen", "loads", "load", "read_bytes", "write_bytes",
}


def check_patch_script(script: str, target_name: str) -> str | None:
    """Return a policy error message, or None when the script is acceptable."""
    try:
        tree = ast.parse(script)
    except SyntaxError as exc:
        return f"syntax error: {exc}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    return f"import not allowed: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_IMPORTS:
                return f"import not allowed: {node.module}"
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_CALLS:
                return f"call not allowed: {func.id}"
            if isinstance(func, ast.Attribute) and func.attr in BANNED_ATTRS:
                return f"attribute call not allowed: {func.attr}"
        elif isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTRS:
                return f"attribute not allowed: {node.attr}"

    writes = script.count("write_text")
    if writes == 0:
        return "script never writes the target file"
    if "write_text" in script and target_name not in script:
        return f"script does not mention the target file {target_name}"
    return None
