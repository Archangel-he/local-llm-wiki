"""Ollama implementation of the provider-neutral LLM contract."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from time import perf_counter
from typing import Any

import httpx

from app.config import settings
from app.llm.errors import LLMAdapterError, LLMErrorCategory
from app.llm.http import json_object, normalize_network_error, raise_for_safe_status
from app.llm.security import EndpointPolicy
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


class OllamaAdapter:
    ADAPTER_VERSION = "mvp1-v1"

    def __init__(
        self,
        *,
        health_timeout_seconds: float = 2.0,
        request_timeout_seconds: float | None = None,
        client: httpx.AsyncClient | None = None,
        endpoint_policy: EndpointPolicy | None = None,
    ) -> None:
        self._health_timeout_seconds = health_timeout_seconds
        self._request_timeout_seconds = (
            request_timeout_seconds or settings.llm_request_timeout_seconds
        )
        self._client = client
        self._endpoint_policy = endpoint_policy or (
            None if client is not None else EndpointPolicy()
        )

    @staticmethod
    def _timeout(request_seconds: float) -> httpx.Timeout:
        return httpx.Timeout(
            request_seconds,
            connect=settings.llm_connect_timeout_seconds,
        )

    @staticmethod
    def api_base_url(profile: RuntimeModelProfile) -> str:
        base_url = profile.base_url.rstrip("/")
        return base_url if base_url.endswith("/api") else f"{base_url}/api"

    async def _validate(self, url: str) -> None:
        if self._endpoint_policy is not None:
            await self._endpoint_policy.validate(url)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        payload: Mapping[str, Any] | None = None,
        timeout: float,
    ) -> httpx.Response:
        await self._validate(url)
        try:
            if self._client is not None:
                response = await self._client.request(
                    method,
                    url,
                    json=payload,
                    timeout=self._timeout(timeout),
                )
            else:
                async with httpx.AsyncClient(follow_redirects=False) as client:
                    response = await client.request(
                        method,
                        url,
                        json=payload,
                        timeout=self._timeout(timeout),
                    )
        except httpx.HTTPError as exc:
            raise normalize_network_error(exc) from None
        raise_for_safe_status(response)
        return response

    async def _models(self, profile: RuntimeModelProfile) -> set[str]:
        response = await self._request(
            "GET",
            f"{self.api_base_url(profile)}/tags",
            timeout=self._health_timeout_seconds,
        )
        models = json_object(response).get("models")
        if not isinstance(models, list):
            raise LLMAdapterError(
                LLMErrorCategory.INVALID_RESPONSE,
                "Ollama returned an invalid model list.",
                retryable=True,
            )
        return {
            name
            for item in models
            if isinstance(item, Mapping)
            for name in (item.get("name"), item.get("model"))
            if isinstance(name, str)
        }

    async def health(self, profile: RuntimeModelProfile) -> LLMHealth:
        started = perf_counter()
        try:
            models = await self._models(profile)
            if profile.model_name not in models:
                return self._unavailable(started, "model_not_found")
            return LLMHealth(LLMHealthStatus.OK, latency_ms=self._elapsed_ms(started))
        except LLMAdapterError as exc:
            return self._unavailable(started, exc.category.value)

    async def test_connection(
        self, profile: RuntimeModelProfile
    ) -> ConnectionTestResult:
        started = perf_counter()
        try:
            models = await self._models(profile)
            if profile.model_name not in models:
                return ConnectionTestResult(
                    reachable=True,
                    model_found=False,
                    streaming_supported=False,
                    structured_output_supported=False,
                    latency_ms=self._elapsed_ms(started),
                    safe_reason="model_not_found",
                )
            probe_schema = {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            }
            await self.generate_structured(
                profile,
                probe_schema,
                [ChatMessage("user", 'Return exactly {"ok":true}.')],
                GenerationOptions(temperature=0.0, max_tokens=32),
            )
            return ConnectionTestResult(
                reachable=True,
                model_found=True,
                streaming_supported=True,
                structured_output_supported=True,
                latency_ms=self._elapsed_ms(started),
            )
        except LLMAdapterError as exc:
            return ConnectionTestResult(
                reachable=False,
                model_found=False,
                streaming_supported=False,
                structured_output_supported=False,
                latency_ms=self._elapsed_ms(started),
                safe_reason=exc.category.value,
            )

    async def generate_structured(
        self,
        profile: RuntimeModelProfile,
        schema: Mapping[str, Any],
        messages: Sequence[ChatMessage],
        options: GenerationOptions,
    ) -> StructuredResponse:
        request_options: dict[str, Any] = {"temperature": options.temperature}
        if options.max_tokens is not None:
            request_options["num_predict"] = options.max_tokens
        response = await self._request(
            "POST",
            f"{self.api_base_url(profile)}/chat",
            payload={
                "model": profile.model_name,
                "messages": [
                    {"role": message.role, "content": message.content}
                    for message in messages
                ],
                "format": dict(schema),
                "stream": False,
                "options": request_options,
            },
            timeout=self._request_timeout_seconds,
        )
        payload = json_object(response)
        message = payload.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str):
            raise self._invalid_response()
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            raise self._invalid_response() from None
        if not isinstance(data, Mapping):
            raise self._invalid_response()
        usage = {
            key: value
            for key, value in {
                "prompt_tokens": payload.get("prompt_eval_count"),
                "completion_tokens": payload.get("eval_count"),
            }.items()
            if isinstance(value, int)
        }
        return StructuredResponse(data=data, model_name=profile.model_name, usage=usage)

    async def stream(
        self,
        profile: RuntimeModelProfile,
        messages: Sequence[ChatMessage],
        options: GenerationOptions,
    ) -> AsyncIterator[StreamChunk]:
        url = f"{self.api_base_url(profile)}/chat"
        await self._validate(url)
        request_options: dict[str, Any] = {"temperature": options.temperature}
        if options.max_tokens is not None:
            request_options["num_predict"] = options.max_tokens
        body = {
            "model": profile.model_name,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "stream": True,
            "options": request_options,
        }
        sequence = 0
        try:
            if self._client is not None:
                context = self._client.stream(
                    "POST", url, json=body, timeout=self._timeout(self._request_timeout_seconds)
                )
                async with context as response:
                    async for chunk in self._stream_response(response, sequence):
                        yield chunk
            else:
                async with httpx.AsyncClient(follow_redirects=False) as client:
                    async with client.stream(
                        "POST",
                        url,
                        json=body,
                        timeout=self._timeout(self._request_timeout_seconds),
                    ) as response:
                        async for chunk in self._stream_response(response, sequence):
                            yield chunk
        except LLMAdapterError:
            raise
        except httpx.HTTPError as exc:
            raise normalize_network_error(exc) from None

    async def _stream_response(
        self, response: httpx.Response, sequence: int
    ) -> AsyncIterator[StreamChunk]:
        raise_for_safe_status(response)
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                raise self._invalid_response() from None
            message = payload.get("message") if isinstance(payload, Mapping) else None
            text = message.get("content") if isinstance(message, Mapping) else None
            if isinstance(text, str) and text:
                yield StreamChunk(StreamChunkType.TOKEN, sequence=sequence, text=text)
                sequence += 1
            if isinstance(payload, Mapping) and payload.get("done") is True:
                yield StreamChunk(StreamChunkType.DONE, sequence=sequence)
                return
        raise self._invalid_response()

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
    def _invalid_response() -> LLMAdapterError:
        return LLMAdapterError(
            LLMErrorCategory.INVALID_RESPONSE,
            "Ollama returned invalid structured output.",
            retryable=True,
        )
