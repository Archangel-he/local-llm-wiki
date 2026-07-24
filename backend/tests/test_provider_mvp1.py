from __future__ import annotations

import json

import httpx
import pytest

from app.llm.errors import LLMAdapterError, LLMErrorCategory
from app.llm.providers import OllamaAdapter, OpenAICompatibleAdapter
from app.llm.security import EndpointPolicy
from app.llm.types import (
    ChatMessage,
    GenerationOptions,
    RuntimeModelProfile,
    StreamChunkType,
)

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}
MESSAGES = [ChatMessage("user", "respond")]


def _profile(provider: str, *, credential: str | None = None) -> RuntimeModelProfile:
    return RuntimeModelProfile(
        profile_id="profile-1",
        provider=provider,
        base_url="http://model.test:11434",
        model_name="wiki-model",
        credential=credential,
    )


async def test_ollama_structured_generation_and_ndjson_stream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "wiki-model"
        if body["stream"]:
            return httpx.Response(
                200,
                text=(
                    '{"message":{"content":"hel"},"done":false}\n'
                    '{"message":{"content":"lo"},"done":false}\n'
                    '{"done":true}\n'
                ),
            )
        assert body["format"] == SCHEMA
        return httpx.Response(
            200,
            json={"message": {"content": '{"ok":true}'}, "eval_count": 2},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OllamaAdapter(client=client)
        result = await adapter.generate_structured(
            _profile("ollama"), SCHEMA, MESSAGES, GenerationOptions()
        )
        chunks = [
            item
            async for item in adapter.stream(
                _profile("ollama"), MESSAGES, GenerationOptions()
            )
        ]

    assert result.data == {"ok": True}
    assert [item.text for item in chunks[:-1]] == ["hel", "lo"]
    assert chunks[-1].type is StreamChunkType.DONE


async def test_openai_structured_generation_and_sse_stream() -> None:
    secret = "do-not-leak-this-key"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {secret}"
        body = json.loads(request.content)
        if body["stream"]:
            return httpx.Response(
                200,
                text=(
                    'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                    "data: [DONE]\n\n"
                ),
                headers={"content-type": "text/event-stream"},
            )
        assert body["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok":true}'}}]},
        )

    profile = _profile("openai_compatible", credential=secret)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OpenAICompatibleAdapter(client=client)
        result = await adapter.generate_structured(
            profile, SCHEMA, MESSAGES, GenerationOptions()
        )
        chunks = [
            item async for item in adapter.stream(profile, MESSAGES, GenerationOptions())
        ]

    assert result.data == {"ok": True}
    assert chunks[0].text == "hello"
    assert chunks[-1].type is StreamChunkType.DONE
    assert secret not in repr(profile)
    assert secret not in repr(adapter)


async def test_both_connection_tests_probe_model_and_structured_output() -> None:
    ollama_calls: list[str] = []

    def ollama_handler(request: httpx.Request) -> httpx.Response:
        ollama_calls.append(request.url.path)
        if request.url.path.endswith("/tags"):
            return httpx.Response(200, json={"models": [{"name": "wiki-model"}]})
        return httpx.Response(200, json={"message": {"content": '{"ok":true}'}})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(ollama_handler)
    ) as client:
        result = await OllamaAdapter(client=client).test_connection(_profile("ollama"))
    assert result.reachable and result.model_found
    assert result.structured_output_supported and result.streaming_supported
    assert ollama_calls == ["/api/tags", "/api/chat"]

    openai_calls: list[str] = []

    def openai_handler(request: httpx.Request) -> httpx.Response:
        openai_calls.append(request.url.path)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "wiki-model"}]})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok":true}'}}]},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(openai_handler)
    ) as client:
        result = await OpenAICompatibleAdapter(client=client).test_connection(
            _profile("openai_compatible")
        )
    assert result.reachable and result.model_found
    assert result.structured_output_supported and result.streaming_supported
    assert openai_calls == ["/v1/models", "/v1/chat/completions"]


@pytest.mark.parametrize("provider", ["ollama", "openai_compatible"])
async def test_stream_without_terminal_marker_is_invalid(provider: str) -> None:
    if provider == "ollama":
        body = '{"message":{"content":"partial"},"done":false}\n'
        adapter_type = OllamaAdapter
    else:
        body = 'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
        adapter_type = OpenAICompatibleAdapter
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body))
    ) as client:
        adapter = adapter_type(client=client)
        with pytest.raises(LLMAdapterError) as captured:
            _ = [
                item
                async for item in adapter.stream(
                    _profile(provider), MESSAGES, GenerationOptions()
                )
            ]
    assert captured.value.category is LLMErrorCategory.INVALID_RESPONSE
    assert captured.value.retryable is True


@pytest.mark.parametrize(
    ("status", "category", "retryable"),
    [
        (302, LLMErrorCategory.ENDPOINT_BLOCKED, False),
        (401, LLMErrorCategory.AUTHENTICATION, False),
        (403, LLMErrorCategory.AUTHENTICATION, False),
        (404, LLMErrorCategory.MODEL_NOT_FOUND, False),
        (429, LLMErrorCategory.RATE_LIMITED, True),
        (503, LLMErrorCategory.UNAVAILABLE, True),
    ],
)
async def test_http_failures_are_safely_classified(
    status: int,
    category: LLMErrorCategory,
    retryable: bool,
) -> None:
    upstream_secret = "body-header-url-secret"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            status,
            text=upstream_secret,
            headers={"x-secret": upstream_secret},
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = OpenAICompatibleAdapter(client=client)
        with pytest.raises(LLMAdapterError) as captured:
            await adapter.generate_structured(
                _profile("openai_compatible", credential=upstream_secret),
                SCHEMA,
                MESSAGES,
                GenerationOptions(),
            )

    assert captured.value.category is category
    assert captured.value.retryable is retryable
    assert upstream_secret not in repr(captured.value)


async def test_timeout_and_invalid_json_are_retryable_and_safe() -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream detail", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(timeout_handler)
    ) as client:
        with pytest.raises(LLMAdapterError) as captured:
            await OllamaAdapter(client=client).generate_structured(
                _profile("ollama"), SCHEMA, MESSAGES, GenerationOptions()
            )
    assert captured.value.category is LLMErrorCategory.TIMEOUT
    assert captured.value.retryable is True

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="bad"))
    ) as client:
        with pytest.raises(LLMAdapterError) as captured:
            await OllamaAdapter(client=client).generate_structured(
                _profile("ollama"), SCHEMA, MESSAGES, GenerationOptions()
            )
    assert captured.value.category is LLMErrorCategory.INVALID_RESPONSE
    assert captured.value.retryable is True


async def test_endpoint_policy_blocks_private_dns_and_production_http() -> None:
    private_policy = EndpointPolicy(
        app_env="local",
        allowlist={"never-matches"},
        resolver=lambda hostname, port: {"10.1.2.3"},
    )
    with pytest.raises(LLMAdapterError) as captured:
        await private_policy.validate("http://internal.example/v1/models")
    assert captured.value.category is LLMErrorCategory.ENDPOINT_BLOCKED

    production_policy = EndpointPolicy(
        app_env="production",
        allowlist={"model.example"},
    )
    with pytest.raises(LLMAdapterError):
        await production_policy.validate("http://model.example/v1/models")
