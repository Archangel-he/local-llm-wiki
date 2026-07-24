from __future__ import annotations

import httpx
import pytest

from app.llm.providers import OllamaAdapter
from app.llm.types import LLMHealthStatus, RuntimeModelProfile


@pytest.fixture
def profile() -> RuntimeModelProfile:
    return RuntimeModelProfile(
        profile_id="profile-1",
        provider="ollama",
        base_url="http://ollama.test:11434",
        model_name="qwen:latest",
    )


async def test_ollama_health_reports_ok_when_selected_model_exists(
    profile: RuntimeModelProfile,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("http://ollama.test:11434/api/tags")
        return httpx.Response(200, json={"models": [{"name": "qwen:latest"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await OllamaAdapter(client=client).health(profile)

    assert result.status is LLMHealthStatus.OK
    assert result.safe_reason is None


async def test_ollama_health_reports_missing_model_without_throwing(
    profile: RuntimeModelProfile,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"models": [{"name": "other"}]})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        result = await OllamaAdapter(client=client).health(profile)

    assert result.status is LLMHealthStatus.UNAVAILABLE
    assert result.safe_reason == "model_not_found"


async def test_ollama_health_normalizes_timeout_without_retrying(
    profile: RuntimeModelProfile,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("not exposed", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await OllamaAdapter(client=client).health(profile)

    assert result.status is LLMHealthStatus.UNAVAILABLE
    assert result.safe_reason == "timeout"
    assert calls == 1


async def test_ollama_health_does_not_expose_upstream_body(
    profile: RuntimeModelProfile,
) -> None:
    secret_body = "upstream-secret-body"
    transport = httpx.MockTransport(
        lambda request: httpx.Response(500, text=secret_body)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        result = await OllamaAdapter(client=client).health(profile)

    assert result.status is LLMHealthStatus.UNAVAILABLE
    assert secret_body not in repr(result)
