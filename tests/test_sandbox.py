from compiler.sandbox import check_patch_script


def test_allows_minimal_patch() -> None:
    script = (
        "from pathlib import Path\n"
        "p = Path('frontend/src/pages/Home.tsx')\n"
        "s = p.read_text(encoding='utf-8')\n"
        "s = s.replace('a', 'b')\n"
        "p.write_text(s, encoding='utf-8')\n"
    )
    assert check_patch_script(script, "Home.tsx") is None


def test_rejects_syntax_error() -> None:
    assert check_patch_script("def broken(:", "Home.tsx") is not None


def test_rejects_dangerous_imports() -> None:
    for bad in ("import os", "import subprocess", "from socket import socket",
                "import urllib.request"):
        script = (
            f"{bad}\n"
            "from pathlib import Path\n"
            "Path('Home.tsx').write_text('x', encoding='utf-8')\n"
        )
        assert check_patch_script(script, "Home.tsx") is not None, bad


def test_rejects_dangerous_calls() -> None:
    for bad in ("eval('1')", "exec('1')", "__import__('os')", "open('/etc/passwd')",
                "compile('1', 'x', 'exec')"):
        script = (
            "from pathlib import Path\n"
            f"{bad}\n"
            "Path('Home.tsx').write_text('x', encoding='utf-8')\n"
        )
        assert check_patch_script(script, "Home.tsx") is not None, bad


def test_rejects_destructive_attributes() -> None:
    for bad in ("import pathlib\npathlib.Path('x').unlink()",
                "import re\nre.compile('x').sub('y','z') and pathlib.os.system('rm')"):
        script = (
            "import pathlib\n"
            f"{bad}\n"
            "pathlib.Path('Home.tsx').write_text('x', encoding='utf-8')\n"
        )
        assert check_patch_script(script, "Home.tsx") is not None, bad


def test_rejects_script_without_write() -> None:
    script = "from pathlib import Path\np = Path('Home.tsx')\np.read_text()\n"
    assert check_patch_script(script, "Home.tsx") is not None


def test_rejects_script_not_touching_target() -> None:
    script = (
        "from pathlib import Path\n"
        "Path('Other.tsx').write_text('x', encoding='utf-8')\n"
    )
    assert check_patch_script(script, "Home.tsx") is not None
