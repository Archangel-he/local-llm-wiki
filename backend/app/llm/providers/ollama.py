"""Ollama adapter skeleton with a bounded, non-throwing health probe."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from time import perf_counter
from typing import Any

import httpx

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


class OllamaAdapter:
    ADAPTER_VERSION = "mvp0"

    def __init__(
        self,
        *,
        health_timeout_seconds: float = 2.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._health_timeout_seconds = health_timeout_seconds
        self._client = client

    @staticmethod
    def api_base_url(profile: RuntimeModelProfile) -> str:
        base_url = profile.base_url.rstrip("/")
        return base_url if base_url.endswith("/api") else f"{base_url}/api"

    async def health(self, profile: RuntimeModelProfile) -> LLMHealth:
        started = perf_counter()
        try:
            if self._client is not None:
                response = await self._client.get(
                    f"{self.api_base_url(profile)}/tags",
                    timeout=self._health_timeout_seconds,
                )
            else:
                async with httpx.AsyncClient(follow_redirects=False) as client:
                    response = await client.get(
                        f"{self.api_base_url(profile)}/tags",
                        timeout=self._health_timeout_seconds,
                    )
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models")
            if not isinstance(models, list):
                return self._unavailable(started, "invalid_response")
            available_names = {
                name
                for item in models
                if isinstance(item, dict)
                for name in (item.get("name"), item.get("model"))
                if isinstance(name, str)
            }
            if profile.model_name not in available_names:
                return self._unavailable(started, "model_not_found")
            return LLMHealth(
                LLMHealthStatus.OK,
                latency_ms=self._elapsed_ms(started),
            )
        except httpx.TimeoutException:
            return self._unavailable(started, "timeout")
        except (httpx.HTTPError, ValueError, TypeError):
            return self._unavailable(started, "connection_failed")

    async def test_connection(
        self, profile: RuntimeModelProfile
    ) -> ConnectionTestResult:
        del profile
        raise self._not_enabled("Ollama connection testing")

    async def generate_structured(
        self,
        profile: RuntimeModelProfile,
        schema: Mapping[str, Any],
        messages: Sequence[ChatMessage],
        options: GenerationOptions,
    ) -> StructuredResponse:
        del profile, schema, messages, options
        raise self._not_enabled("Ollama structured generation")

    async def stream(
        self,
        profile: RuntimeModelProfile,
        messages: Sequence[ChatMessage],
        options: GenerationOptions,
    ) -> AsyncIterator[StreamChunk]:
        del profile, messages, options
        raise self._not_enabled("Ollama streaming")
        yield  # pragma: no cover - keeps this method an async generator

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, round((perf_counter() - started) * 1000))

    @classmethod
    def _unavailable(cls, started: float, reason: str) -> LLMHealth:
        return LLMHealth(
            LLMHealthStatus.UNAVAILABLE,
            latency_ms=cls._elapsed_ms(started),
            safe_reason=reason,
        )

    @staticmethod
    def _not_enabled(operation: str) -> LLMAdapterError:
        return LLMAdapterError(
            LLMErrorCategory.NOT_ENABLED,
            f"{operation} is not enabled in MVP0.",
            retryable=False,
        )
