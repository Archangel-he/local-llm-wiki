"""Deterministic in-process LLM test double."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
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
    StreamChunkType,
    StructuredResponse,
)


class MockScenario(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    INVALID_JSON = "invalid_json"
    STREAM_ERROR = "stream_error"


@dataclass(frozen=True, slots=True)
class MockCall:
    operation: str
    profile_id: str
    model_name: str
    message_count: int


class MockLLMAdapter:
    """A configurable mock that never stores profile credentials in call history."""

    def __init__(
        self,
        *,
        scenario: MockScenario = MockScenario.OK,
        structured_data: Mapping[str, Any] | None = None,
        stream_tokens: Sequence[str] = ("mock", " response"),
    ) -> None:
        self.scenario = scenario
        self._structured_data = dict(structured_data or {"status": "ok"})
        self._stream_tokens = tuple(stream_tokens)
        self.calls: list[MockCall] = []

    def _record(
        self,
        operation: str,
        profile: RuntimeModelProfile,
        messages: Sequence[ChatMessage] = (),
    ) -> None:
        self.calls.append(
            MockCall(
                operation=operation,
                profile_id=profile.profile_id,
                model_name=profile.model_name,
                message_count=len(messages),
            )
        )

    def _raise_generation_failure(self) -> None:
        if self.scenario is MockScenario.UNAVAILABLE:
            raise LLMAdapterError(
                LLMErrorCategory.UNAVAILABLE,
                "The mock model is unavailable.",
                retryable=True,
            )
        if self.scenario is MockScenario.TIMEOUT:
            raise LLMAdapterError(
                LLMErrorCategory.TIMEOUT,
                "The mock model timed out.",
                retryable=True,
            )

    async def health(self, profile: RuntimeModelProfile) -> LLMHealth:
        self._record("health", profile)
        if self.scenario in {MockScenario.UNAVAILABLE, MockScenario.TIMEOUT}:
            reason = "timeout" if self.scenario is MockScenario.TIMEOUT else "unavailable"
            return LLMHealth(LLMHealthStatus.UNAVAILABLE, safe_reason=reason)
        return LLMHealth(LLMHealthStatus.OK, latency_ms=0)

    async def test_connection(
        self, profile: RuntimeModelProfile
    ) -> ConnectionTestResult:
        self._record("test_connection", profile)
        if self.scenario in {MockScenario.UNAVAILABLE, MockScenario.TIMEOUT}:
            reason = "timeout" if self.scenario is MockScenario.TIMEOUT else "unavailable"
            return ConnectionTestResult(
                reachable=False,
                model_found=False,
                streaming_supported=False,
                structured_output_supported=False,
                safe_reason=reason,
            )
        return ConnectionTestResult(
            reachable=True,
            model_found=True,
            streaming_supported=True,
            structured_output_supported=True,
            latency_ms=0,
        )

    async def generate_structured(
        self,
        profile: RuntimeModelProfile,
        schema: Mapping[str, Any],
        messages: Sequence[ChatMessage],
        options: GenerationOptions,
    ) -> StructuredResponse:
        del schema, options
        self._record("generate_structured", profile, messages)
        self._raise_generation_failure()
        if self.scenario is MockScenario.INVALID_JSON:
            raise LLMAdapterError(
                LLMErrorCategory.INVALID_RESPONSE,
                "The mock model returned invalid structured output.",
                retryable=False,
            )
        return StructuredResponse(
            data=deepcopy(self._structured_data),
            model_name=profile.model_name,
        )

    async def stream(
        self,
        profile: RuntimeModelProfile,
        messages: Sequence[ChatMessage],
        options: GenerationOptions,
    ) -> AsyncIterator[StreamChunk]:
        del options
        self._record("stream", profile, messages)
        self._raise_generation_failure()
        for sequence, token in enumerate(self._stream_tokens):
            yield StreamChunk(StreamChunkType.TOKEN, sequence=sequence, text=token)
            if self.scenario is MockScenario.STREAM_ERROR and sequence == 0:
                raise LLMAdapterError(
                    LLMErrorCategory.UNAVAILABLE,
                    "The mock stream was interrupted.",
                    retryable=True,
                )
        yield StreamChunk(
            StreamChunkType.DONE,
            sequence=len(self._stream_tokens),
        )
