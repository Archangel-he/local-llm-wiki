"""The provider-neutral adapter protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from app.llm.types import (
    ChatMessage,
    ConnectionTestResult,
    GenerationOptions,
    LLMHealth,
    RuntimeModelProfile,
    StreamChunk,
    StructuredResponse,
)


@runtime_checkable
class LLMAdapter(Protocol):
    async def health(self, profile: RuntimeModelProfile) -> LLMHealth: ...

    async def test_connection(
        self, profile: RuntimeModelProfile
    ) -> ConnectionTestResult: ...

    async def generate_structured(
        self,
        profile: RuntimeModelProfile,
        schema: Mapping[str, Any],
        messages: Sequence[ChatMessage],
        options: GenerationOptions,
    ) -> StructuredResponse: ...

    def stream(
        self,
        profile: RuntimeModelProfile,
        messages: Sequence[ChatMessage],
        options: GenerationOptions,
    ) -> AsyncIterator[StreamChunk]: ...
