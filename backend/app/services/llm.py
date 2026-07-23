from __future__ import annotations

import json
import urllib.request
from typing import Any

from ..config import settings


class LLMAdapter:
    """Ollama adapter for MVP 0 skeleton."""

    def __init__(self) -> None:
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model = settings.llm_model or ""

    def health(self) -> bool:
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            return False

    def generate(self, prompt: str, schema: dict | None = None) -> dict[str, Any] | str:
        """Send a generate request to Ollama. Returns parsed JSON or string."""
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if schema:
            payload["format"] = schema

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        response_text = result.get("response", "")
        if schema:
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                return response_text
        return response_text


def get_llm() -> LLMAdapter:
    return LLMAdapter()
