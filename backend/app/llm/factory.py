"""Factory for persisted provider types.

The in-process MockLLMAdapter is intentionally absent: tests inject it directly
and no database record can persist ``provider=mock``.
"""

from __future__ import annotations

import httpx

from app.llm.base import LLMAdapter
from app.llm.providers import OllamaAdapter, OpenAICompatibleAdapter
from app.llm.types import ModelProvider


def create_adapter(
    provider: ModelProvider | str,
    *,
    health_timeout_seconds: float = 2.0,
    http_client: httpx.AsyncClient | None = None,
) -> LLMAdapter:
    resolved = ModelProvider(provider)
    if resolved is ModelProvider.OLLAMA:
        return OllamaAdapter(
            health_timeout_seconds=health_timeout_seconds,
            client=http_client,
        )
    return OpenAICompatibleAdapter()
