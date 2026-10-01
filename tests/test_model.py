from compiler.model import Conversation, ModelClient, extract_code, extract_json


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
    for i in range(12):
        conv.messages.append({"role": "user", "content": f"feedback {i} " + "x" * 8000})
        conv._compact()
    total = sum(len(str(m.get("content") or "")) for m in conv.messages)
    assert total < 120_000
    assert conv.messages[0]["content"] == "system prompt"
    assert conv.messages[1]["content"] == "fixed prefix context"


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
