"""Model client, compacting conversation, and response extractors."""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.request
from pathlib import Path

from .config import (
    BUDGET,
    MAX_CONVERSATION_CHARS,
    MAX_EXCHANGE_SUMMARY_CHARS,
    MAX_OUTPUT_TOKENS,
    REQUEST_TIMEOUT,
    log,
)

MOCK_MODE = os.environ.get("ARCBENCH_MOCK_MODEL") == "1"


def _mock_reply(messages: list[dict]) -> str:
    """Deterministic canned replies so the pipeline can run without credentials."""
    text = " ".join(str(m.get("content") or "") for m in messages)
    if "Express backend" in text:
        return (
            "```js\n"
            "const express = require('express');\n"
            "const cors = require('cors');\n"
            "const path = require('path');\n"
            "const app = express();\n"
            "app.use(cors());\n"
            "app.use(express.json());\n"
            "app.get('/api/health', (req, res) => res.json({ status: 'ok' }));\n"
            "const port = process.env.PORT || 3000;\n"
            "const dist = path.resolve(__dirname, '../../frontend/dist');\n"
            "app.use(express.static(dist));\n"
            "app.get('*', (req, res) => res.sendFile(path.join(dist, 'index.html')));\n"
            "app.listen(port, () => console.log('listening on ' + port));\n"
            "```\n"
        )
    if "React page component" in text:
        name = "HomePage"
        m = re.search(r"named `([A-Za-z0-9]+)`", text)
        if m:
            name = m.group(1)
        return (
            f"```tsx\n"
            f"export default function {name}() {{\n"
            f"  return (\n    <main aria-label=\"Page\">\n"
            f"      <h1>{name}</h1>\n"
            f"      <button type=\"button\">Action</button>\n"
            f"    </main>\n  )\n}}\n"
            f"```\n"
        )
    if "Design the REST API" in text or ('"seed"' in text and '"api"' in text):
        return json.dumps({
            "seed": {"items": [{"id": 1, "name": "demo"}]},
            "api": [{"method": "GET", "path": "/api/items", "summary": "list items"}],
            "pages": [{"route": "/", "name": "Home", "summary": "home"}],
        })
    return '{"ok": true, "missing_or_wrong": [], "controls": []}'


class ModelClient:
    def __init__(self) -> None:
        self.key = os.environ.get("OPENAI_API_KEY", "")
        self.base = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
        self.model = os.environ.get("MODEL") or "deepseek-v4-flash"
        self.vbase = (os.environ.get("VISUAL_BASE_URL") or self.base).rstrip("/")
        self.vmodel = (os.environ.get("VISUAL_MODEL") or "").strip() or self.model

    def chat_messages(self, messages: list[dict], *, images: list[Path] | None = None) -> str:
        if MOCK_MODE:
            BUDGET.note({"total_tokens": 100})
            return _mock_reply(messages)
        use_vision = bool(images)
        base, model = (self.vbase, self.vmodel) if use_vision else (self.base, self.model)
        sent = [dict(m) for m in messages]
        if use_vision and sent and isinstance(sent[-1].get("content"), str):
            content: list[dict] = [{"type": "text", "text": sent[-1]["content"]}]
            for img in images[:2]:
                data = base64.b64encode(img.read_bytes()).decode()
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{data}"},
                })
            sent[-1] = {"role": sent[-1]["role"], "content": content}
        body = json.dumps({
            "model": model,
            "messages": sent,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0.2,
        }).encode()
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                    payload = json.loads(resp.read())
                BUDGET.note(payload.get("usage") or {})
                choice = (payload.get("choices") or [{}])[0]
                return (choice.get("message") or {}).get("content") or ""
            except Exception as exc:
                log(f"model call error (attempt {attempt + 1}): {exc}")
                time.sleep(4 * (attempt + 1))
        return ""

    def chat(self, prompt: str, *, system: str = "",
             images: list[Path] | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat_messages(messages, images=images)


class Conversation:
    """Fixed-prefix conversation with bounded compaction.

    The system prompt and the first user message (requirement context) are never
    rewritten so the provider can reuse the request prefix. Older exchanges are
    folded into short summaries once the transcript grows too large.
    """

    def __init__(self, client: ModelClient, system: str, prefix_user: str) -> None:
        self.client = client
        self.messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prefix_user},
        ]

    def ask(self, prompt: str, *, images: list[Path] | None = None) -> str:
        self.messages.append({"role": "user", "content": prompt})
        self._compact()
        reply = self.client.chat_messages(self.messages, images=images)
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def _compact(self) -> None:
        def total() -> int:
            return sum(len(str(m.get("content") or "")) for m in self.messages)

        while total() > MAX_CONVERSATION_CHARS and len(self.messages) > 4:
            old = self.messages[2]
            summary = str(old.get("content") or "")[:MAX_EXCHANGE_SUMMARY_CHARS]
            self.messages[2:4] = [{
                "role": "user",
                "content": f"[earlier exchange condensed] {summary}",
            }]


def extract_code(text: str) -> str:
    if "```" not in text:
        return text.strip()
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)```", text, re.S)
    return max(blocks, key=len).strip() if blocks else text.strip()


def extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return {}
