from __future__ import annotations

import pytest

from app.llm.errors import LLMAdapterError, LLMErrorCategory
from app.llm.mock import MockLLMAdapter, MockScenario
from app.llm.types import (
    ChatMessage,
    GenerationOptions,
    LLMHealthStatus,
    RuntimeModelProfile,
    StreamChunkType,
)


@pytest.fixture
def profile() -> RuntimeModelProfile:
    return RuntimeModelProfile(
        profile_id="profile-1",
        provider="ollama",
        base_url="http://host.docker.internal:11434",
        model_name="qwen",
        credential="must-never-be-recorded",
    )


async def test_mock_supports_deterministic_health_structured_and_stream(
    profile: RuntimeModelProfile,
) -> None:
    adapter = MockLLMAdapter(
        structured_data={"answer": 42},
        stream_tokens=("hello", " world"),
    )

    health = await adapter.health(profile)
    connection = await adapter.test_connection(profile)
    structured = await adapter.generate_structured(
        profile,
        {"type": "object"},
        [ChatMessage("user", "question")],
        GenerationOptions(),
    )
    chunks = [
        chunk
        async for chunk in adapter.stream(
            profile,
            [ChatMessage("user", "question")],
            GenerationOptions(),
        )
    ]

    assert health.status is LLMHealthStatus.OK
    assert connection.reachable is True
    assert structured.data == {"answer": 42}
    assert [(chunk.type, chunk.text) for chunk in chunks] == [
        (StreamChunkType.TOKEN, "hello"),
        (StreamChunkType.TOKEN, " world"),
        (StreamChunkType.DONE, ""),
    ]
    assert "must-never-be-recorded" not in repr(adapter.calls)
    assert [call.operation for call in adapter.calls] == [
        "health",
        "test_connection",
        "generate_structured",
        "stream",
    ]


@pytest.mark.parametrize(
    ("scenario", "expected_category"),
    [
        (MockScenario.UNAVAILABLE, LLMErrorCategory.UNAVAILABLE),
        (MockScenario.TIMEOUT, LLMErrorCategory.TIMEOUT),
        (MockScenario.INVALID_JSON, LLMErrorCategory.INVALID_RESPONSE),
    ],
)
async def test_mock_generation_failure_is_typed(
    profile: RuntimeModelProfile,
    scenario: MockScenario,
    expected_category: LLMErrorCategory,
) -> None:
    adapter = MockLLMAdapter(scenario=scenario)

    with pytest.raises(LLMAdapterError) as captured:
        await adapter.generate_structured(
            profile,
            {},
            [],
            GenerationOptions(),
        )

    assert captured.value.category is expected_category
    assert "must-never-be-recorded" not in str(captured.value)


async def test_mock_stream_can_fail_after_a_deterministic_prefix(
    profile: RuntimeModelProfile,
) -> None:
    adapter = MockLLMAdapter(
        scenario=MockScenario.STREAM_ERROR,
        stream_tokens=("first", "never emitted"),
    )
    emitted = []

    with pytest.raises(LLMAdapterError) as captured:
        async for chunk in adapter.stream(profile, [], GenerationOptions()):
            emitted.append(chunk.text)

    assert emitted == ["first"]
    assert captured.value.retryable is True
