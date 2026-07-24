from __future__ import annotations

from app.llm.health import probe_default_llm
from app.llm.mock import MockLLMAdapter
from app.llm.types import LLMHealthStatus, RuntimeModelProfile


async def test_health_without_default_profile_is_degraded_not_exception() -> None:
    result = await probe_default_llm(None)

    assert result.status is LLMHealthStatus.UNAVAILABLE
    assert result.safe_reason == "default_profile_missing"


async def test_health_factory_receives_only_the_default_profile_provider() -> None:
    seen: list[str] = []
    profile = RuntimeModelProfile(
        profile_id="default",
        provider="ollama",
        base_url="http://ollama.test:11434",
        model_name="qwen",
    )

    def factory(provider: str) -> MockLLMAdapter:
        seen.append(provider)
        return MockLLMAdapter()

    result = await probe_default_llm(profile, adapter_factory=factory)

    assert result.status is LLMHealthStatus.OK
    assert seen == ["ollama"]
