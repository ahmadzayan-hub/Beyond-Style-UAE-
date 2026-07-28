"""LLM adapters.

Three access modes, selected via BSOS_LLM_PROVIDER:
  - `anthropic` — Anthropic Messages API (API key billing)
  - `ollama`    — a local model server (no key, runs on the owner's machine)
  - subscription plans (claude.ai Pro/Max) are chat products without a
    programmatic API; they cannot back an adapter and SETUP.md says so.

Used for text tasks (brief prose, bilingual copy scaffolds, engineering
review) and, wrapped by vision.LLMVisionExtractor, for attribute extraction —
where only structured JSON leaves the adapter.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import httpx


class LLMError(Exception):
    pass


class AnthropicLLM:
    BASE = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "claude-sonnet-5", timeout: float = 120.0):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY missing — LLM adapter cannot start (see SETUP.md)")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _post(self, messages: list[dict], max_tokens: int = 2048) -> str:
        resp = httpx.post(
            self.BASE,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={"model": self.model, "max_tokens": max_tokens, "messages": messages},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise LLMError(f"LLM call failed: HTTP {resp.status_code}: {resp.text[:300]}")
        blocks = resp.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        return self._post([{"role": "user", "content": prompt}], max_tokens)

    def complete_vision(self, prompt: str, image_path: Path, max_tokens: int = 2048) -> str:
        media_type = mimetypes.guess_type(str(image_path))[0] or "image/png"
        data = base64.b64encode(Path(image_path).read_bytes()).decode()
        return self._post(
            [{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": media_type, "data": data}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens,
        )


class OllamaLLM:
    """Local model server (Ollama /api/chat). No key, no cloud.

    Vision works when the configured model is multimodal (e.g. llava,
    llama3.2-vision); otherwise complete_vision raises a clear error.
    """

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "llama3.2", timeout: float = 300.0, transport=None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._post_fn = transport or (
            lambda url, payload: httpx.post(url, json=payload, timeout=self.timeout)
        )

    def _chat(self, messages: list[dict]) -> str:
        resp = self._post_fn(f"{self.base_url}/api/chat", {
            "model": self.model, "messages": messages, "stream": False,
        })
        if resp.status_code != 200:
            raise LLMError(
                f"Ollama call failed: HTTP {resp.status_code}: {resp.text[:300]} — "
                f"is `ollama serve` running and model '{self.model}' pulled?"
            )
        return resp.json().get("message", {}).get("content", "")

    def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        return self._chat([{"role": "user", "content": prompt}])

    def complete_vision(self, prompt: str, image_path: Path, max_tokens: int = 2048) -> str:
        data = base64.b64encode(Path(image_path).read_bytes()).decode()
        out = self._chat([{"role": "user", "content": prompt, "images": [data]}])
        if not out:
            raise LLMError(
                f"model '{self.model}' returned nothing for a vision request — "
                "use a multimodal model (e.g. llava, llama3.2-vision)"
            )
        return out
