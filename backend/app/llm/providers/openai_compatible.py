"""OpenAI-compatible implementation of the provider-neutral contract."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit

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


class OpenAICompatibleAdapter:
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
        return base_url if base_url.endswith("/v1") else f"{base_url}/v1"

    @staticmethod
    def authorization_headers(profile: RuntimeModelProfile) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if profile.credential is not None:
            headers["Authorization"] = f"Bearer {profile.credential}"
        return headers

    async def _validate(self, url: str) -> None:
        if self._endpoint_policy is not None:
            await self._endpoint_policy.validate(url)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        profile: RuntimeModelProfile,
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
                    headers=self.authorization_headers(profile),
                    timeout=self._timeout(timeout),
                )
            else:
                async with httpx.AsyncClient(follow_redirects=False) as client:
                    response = await client.request(
                        method,
                        url,
                        json=payload,
                        headers=self.authorization_headers(profile),
                        timeout=self._timeout(timeout),
                    )
        except httpx.HTTPError as exc:
            raise normalize_network_error(exc) from None
        raise_for_safe_status(response)
        return response

    async def _models(self, profile: RuntimeModelProfile) -> set[str]:
        response = await self._request(
            "GET",
            f"{self.api_base_url(profile)}/models",
            profile=profile,
            timeout=self._health_timeout_seconds,
        )
        data = json_object(response).get("data")
        if not isinstance(data, list):
            raise self._invalid_response()
        return {
            item["id"]
            for item in data
            if isinstance(item, Mapping) and isinstance(item.get("id"), str)
        }

    async def list_models(self, profile: RuntimeModelProfile) -> list[str]:
        return sorted(await self._models(profile), key=str.casefold)

    async def health(self, profile: RuntimeModelProfile) -> LLMHealth:
        started = perf_counter()
        try:
            models = await self._models(profile)
            if profile.model_name not in models:
                return LLMHealth(
                    LLMHealthStatus.UNAVAILABLE,
                    latency_ms=self._elapsed_ms(started),
                    safe_reason="model_not_found",
                )
            return LLMHealth(LLMHealthStatus.OK, latency_ms=self._elapsed_ms(started))
        except LLMAdapterError as exc:
            return LLMHealth(
                LLMHealthStatus.UNAVAILABLE,
                latency_ms=self._elapsed_ms(started),
                safe_reason=exc.category.value,
            )

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
            await self.generate_structured(
                profile,
                {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                    "additionalProperties": False,
                },
                [
                    ChatMessage(
                        "user",
                        'Return exactly this JSON object with no extra keys: {"ok":true}.',
                    )
                ],
                GenerationOptions(temperature=0.0, max_tokens=128),
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
        wire_messages = [
            {"role": message.role, "content": message.content} for message in messages
        ]
        hostname = (urlsplit(profile.base_url).hostname or "").casefold()
        if hostname == "api.deepseek.com":
            schema_instruction = (
                "Return only valid JSON matching this JSON Schema: "
                + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
            )
            system_message = next(
                (message for message in wire_messages if message["role"] == "system"),
                None,
            )
            if system_message is None:
                wire_messages.insert(
                    0,
                    {"role": "system", "content": schema_instruction},
                )
            else:
                system_message["content"] += f"\n{schema_instruction}"
            response_format: dict[str, Any] = {"type": "json_object"}
        else:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "wiki_ingest",
                    "strict": True,
                    "schema": dict(schema),
                },
            }
        body: dict[str, Any] = {
            "model": profile.model_name,
            "messages": wire_messages,
            "temperature": options.temperature,
            "stream": False,
            "response_format": response_format,
        }
        if options.max_tokens is not None:
            body["max_tokens"] = options.max_tokens
        if hostname == "api.deepseek.com":
            body["thinking"] = {"type": "disabled"}
        response = await self._request(
            "POST",
            f"{self.api_base_url(profile)}/chat/completions",
            profile=profile,
            payload=body,
            timeout=self._request_timeout_seconds,
        )
        payload = json_object(response)
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise self._invalid_response()
        message = choices[0].get("message") if isinstance(choices[0], Mapping) else None
        content = message.get("content") if isinstance(message, Mapping) else None
        if isinstance(content, Mapping):
            data = content
        elif isinstance(content, str):
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                raise self._invalid_response() from None
        else:
            raise self._invalid_response()
        if not isinstance(data, Mapping):
            raise self._invalid_response()
        usage_payload = payload.get("usage")
        usage = {
            str(key): value
            for key, value in (usage_payload.items() if isinstance(usage_payload, Mapping) else ())
            if isinstance(value, int)
        }
        return StructuredResponse(data=data, model_name=profile.model_name, usage=usage)

    async def stream(
        self,
        profile: RuntimeModelProfile,
        messages: Sequence[ChatMessage],
        options: GenerationOptions,
    ) -> AsyncIterator[StreamChunk]:
        url = f"{self.api_base_url(profile)}/chat/completions"
        await self._validate(url)
        body: dict[str, Any] = {
            "model": profile.model_name,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "temperature": options.temperature,
            "stream": True,
        }
        if options.max_tokens is not None:
            body["max_tokens"] = options.max_tokens
        try:
            if self._client is not None:
                context = self._client.stream(
                    "POST",
                    url,
                    json=body,
                    headers=self.authorization_headers(profile),
                    timeout=self._timeout(self._request_timeout_seconds),
                )
                async with context as response:
                    async for chunk in self._stream_response(response):
                        yield chunk
            else:
                async with httpx.AsyncClient(follow_redirects=False) as client:
                    async with client.stream(
                        "POST",
                        url,
                        json=body,
                        headers=self.authorization_headers(profile),
                        timeout=self._timeout(self._request_timeout_seconds),
                    ) as response:
                        async for chunk in self._stream_response(response):
                            yield chunk
        except LLMAdapterError:
            raise
        except httpx.HTTPError as exc:
            raise normalize_network_error(exc) from None

    async def _stream_response(
        self, response: httpx.Response
    ) -> AsyncIterator[StreamChunk]:
        raise_for_safe_status(response)
        sequence = 0
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                yield StreamChunk(StreamChunkType.DONE, sequence=sequence)
                return
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                raise self._invalid_response() from None
            choices = payload.get("choices") if isinstance(payload, Mapping) else None
            first = choices[0] if isinstance(choices, list) and choices else None
            delta = first.get("delta") if isinstance(first, Mapping) else None
            text = delta.get("content") if isinstance(delta, Mapping) else None
            if isinstance(text, str) and text:
                yield StreamChunk(StreamChunkType.TOKEN, sequence=sequence, text=text)
                sequence += 1
        raise self._invalid_response()

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, round((perf_counter() - started) * 1000))

    @staticmethod
    def _invalid_response() -> LLMAdapterError:
        return LLMAdapterError(
            LLMErrorCategory.INVALID_RESPONSE,
            "The model endpoint returned invalid structured output.",
            retryable=True,
        )
