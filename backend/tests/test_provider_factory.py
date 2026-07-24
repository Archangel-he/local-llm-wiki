from __future__ import annotations

import pytest

from app.llm.errors import LLMAdapterError, LLMErrorCategory
from app.llm.factory import create_adapter
from app.llm.providers import OllamaAdapter, OpenAICompatibleAdapter
from app.llm.types import GenerationOptions, ModelProvider, RuntimeModelProfile


def test_factory_only_accepts_persisted_provider_values() -> None:
    assert isinstance(create_adapter(ModelProvider.OLLAMA), OllamaAdapter)
    assert isinstance(
        create_adapter(ModelProvider.OPENAI_COMPATIBLE), OpenAICompatibleAdapter
    )
    with pytest.raises(ValueError):
        create_adapter("mock")


def test_provider_base_urls_are_normalized_without_duplicate_api_prefixes() -> None:
    ollama_root = RuntimeModelProfile(
        profile_id="o1",
        provider="ollama",
        base_url="http://ollama.test:11434/",
        model_name="qwen",
    )
    ollama_api = RuntimeModelProfile(
        profile_id="o2",
        provider="ollama",
        base_url="http://ollama.test:11434/api/",
        model_name="qwen",
    )
    openai_root = RuntimeModelProfile(
        profile_id="a1",
        provider="openai_compatible",
        base_url="https://api.example.test/",
        model_name="model",
    )

    assert OllamaAdapter.api_base_url(ollama_root) == "http://ollama.test:11434/api"
    assert OllamaAdapter.api_base_url(ollama_api) == "http://ollama.test:11434/api"
    assert (
        OpenAICompatibleAdapter.api_base_url(openai_root)
        == "https://api.example.test/v1"
    )


async def test_real_generation_methods_fail_explicitly_in_mvp0() -> None:
    profile = RuntimeModelProfile(
        profile_id="o1",
        provider="ollama",
        base_url="http://ollama.test:11434",
        model_name="qwen",
    )
    adapter = OllamaAdapter()

    with pytest.raises(LLMAdapterError) as captured:
        await adapter.generate_structured(profile, {}, [], GenerationOptions())

    assert captured.value.category is LLMErrorCategory.NOT_ENABLED
    assert captured.value.retryable is False


def test_openai_authorization_header_is_transient_and_adapter_repr_is_safe() -> None:
    secret = "header-secret"
    profile = RuntimeModelProfile(
        profile_id="a1",
        provider="openai_compatible",
        base_url="https://api.example.test",
        model_name="model",
        credential=secret,
    )
    adapter = OpenAICompatibleAdapter()

    headers = adapter.authorization_headers(profile)

    assert headers["Authorization"] == f"Bearer {secret}"
    assert secret not in repr(adapter)
