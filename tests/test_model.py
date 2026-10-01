from compiler.model import (
    COMPRESSION_MARKER_TEMPLATE,
    TAIL_MESSAGES,
    Conversation,
    ModelClient,
    extract_code,
    extract_json,
    fit_text,
)


def test_extract_code_prefers_largest_block() -> None:
    text = "note\n```js\nsmall\n```\nmore\n```python\nline1\nline2\n```\n"
    assert extract_code(text) == "line1\nline2"


def test_extract_code_plain() -> None:
    assert extract_code("bare code") == "bare code"


def test_extract_json_tolerates_fences() -> None:
    payload = extract_json('```json\n{"ok": true, "items": [1, 2]}\n```')
    assert payload == {"ok": True, "items": [1, 2]}


def test_extract_json_garbage() -> None:
    assert extract_json("no json here") == {}


def test_conversation_compaction_bounds_size() -> None:
    conv = Conversation(ModelClient(), "system prompt", "fixed prefix context")
    tail_contents = []
    for i in range(30):
        conv.messages.append({"role": "user", "content": f"feedback {i} " + "x" * 8000})
        if i >= 30 - TAIL_MESSAGES:
            tail_contents.append(conv.messages[-1]["content"])
    conv._compact()
    total = sum(len(str(m.get("content") or "")) for m in conv.messages)
    assert total < 120_000
    assert conv.messages[0]["content"] == "system prompt"
    assert conv.messages[1]["content"] == "fixed prefix context"
    # head pinned, tail kept verbatim
    for content in tail_contents:
        assert any(m.get("content") == content for m in conv.messages[-TAIL_MESSAGES:])
    # condensed messages carry the anti-imitation marker
    joined = "\n".join(str(m.get("content") or "") for m in conv.messages)
    assert "CONTEXT-COMPACTED" in joined
    assert "must never be reproduced" in joined


def test_compaction_keeps_pairs_together() -> None:
    conv = Conversation(ModelClient(), "sys", "prefix")
    for i in range(20):
        conv.messages.append({"role": "user", "content": f"q{i} " + "x" * 6000})
        conv.messages.append({"role": "assistant", "content": f"a{i} " + "y" * 6000})
    conv._compact()
    total = sum(len(str(m.get("content") or "")) for m in conv.messages)
    assert total < 120_000
    # every surviving original assistant reply still sits next to its own question
    for i in range(1, len(conv.messages)):
        content = str(conv.messages[i].get("content") or "")
        if content.startswith("a") and " " in content and content[1:content.index(" ")].isdigit():
            prev = str(conv.messages[i - 1].get("content") or "")
            n = content[1:content.index(" ")]
            assert prev.startswith(f"q{n} ") or "CONTEXT-COMPACTED" in prev


def test_fit_text_marks_elision() -> None:
    text = "A" * 50000
    fitted = fit_text(text, 5000)
    assert len(fitted) < 6000
    assert "CONTEXT-ELIDED" in fitted
    assert "50,000" in fitted
    assert fit_text("short", 100) == "short"


def test_mock_client_replies() -> None:
    import os

    os.environ["ARCBENCH_MOCK_MODEL"] = "1"
    try:
        import importlib

        from compiler import model as model_mod

        importlib.reload(model_mod)
        client = model_mod.ModelClient()
        design = model_mod.extract_json(
            client.chat('Design the API. shape keys "seed" and "api".')
        )
        assert "api" in design
        code = model_mod.extract_code(
            client.chat("Write the complete Express backend implementing this.")
        )
        assert "express" in code
        page = model_mod.extract_code(
            client.chat("Create a React page component named `MyPage`.")
        )
        assert "MyPage" in page
    finally:
        os.environ.pop("ARCBENCH_MOCK_MODEL", None)
