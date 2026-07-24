"""Factory for persisted provider types.

The built-in Mock provider is internal-only: public APIs still reject creating
new Mock profiles, while the deterministic Seed profile remains executable.
"""

from __future__ import annotations

import httpx

from app.llm.base import LLMAdapter
from app.llm.mock import MockLLMAdapter
from app.llm.providers import OllamaAdapter, OpenAICompatibleAdapter
from app.llm.types import ModelProvider


def create_adapter(
    provider: ModelProvider | str,
    *,
    health_timeout_seconds: float = 2.0,
    http_client: httpx.AsyncClient | None = None,
) -> LLMAdapter:
    resolved = ModelProvider(provider)
    if resolved is ModelProvider.MOCK:
        return MockLLMAdapter()
    if resolved is ModelProvider.OLLAMA:
        return OllamaAdapter(
            health_timeout_seconds=health_timeout_seconds,
            client=http_client,
        )
    return OpenAICompatibleAdapter(
        health_timeout_seconds=health_timeout_seconds,
        client=http_client,
    )
