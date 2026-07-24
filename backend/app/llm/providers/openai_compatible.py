"""Non-networking OpenAI-compatible adapter skeleton for MVP0."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from app.llm.errors import LLMAdapterError, LLMErrorCategory
from app.llm.types import (
    ChatMessage,
    ConnectionTestResult,
    GenerationOptions,
    LLMHealth,
    LLMHealthStatus,
    RuntimeModelProfile,
    StreamChunk,
    StructuredResponse,
)


class OpenAICompatibleAdapter:
    ADAPTER_VERSION = "mvp0"

    @staticmethod
    def api_base_url(profile: RuntimeModelProfile) -> str:
        base_url = profile.base_url.rstrip("/")
        return base_url if base_url.endswith("/v1") else f"{base_url}/v1"

    @staticmethod
    def authorization_headers(profile: RuntimeModelProfile) -> dict[str, str]:
        """Build transient headers without retaining them on the adapter."""

        if profile.credential is None:
            return {"Accept": "application/json"}
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {profile.credential}",
        }

    async def health(self, profile: RuntimeModelProfile) -> LLMHealth:
        del profile
        return LLMHealth(
            LLMHealthStatus.UNAVAILABLE,
            safe_reason="not_enabled_in_mvp0",
        )

    async def test_connection(
        self, profile: RuntimeModelProfile
    ) -> ConnectionTestResult:
        del profile
        raise self._not_enabled("OpenAI-compatible connection testing")

    async def generate_structured(
        self,
        profile: RuntimeModelProfile,
        schema: Mapping[str, Any],
        messages: Sequence[ChatMessage],
        options: GenerationOptions,
    ) -> StructuredResponse:
        del profile, schema, messages, options
        raise self._not_enabled("OpenAI-compatible structured generation")

    async def stream(
        self,
        profile: RuntimeModelProfile,
        messages: Sequence[ChatMessage],
        options: GenerationOptions,
    ) -> AsyncIterator[StreamChunk]:
        del profile, messages, options
        raise self._not_enabled("OpenAI-compatible streaming")
        yield  # pragma: no cover - keeps this method an async generator

    @staticmethod
    def _not_enabled(operation: str) -> LLMAdapterError:
        return LLMAdapterError(
            LLMErrorCategory.NOT_ENABLED,
            f"{operation} is not enabled in MVP0.",
            retryable=False,
        )
