from __future__ import annotations

import json

import pytest

from app.llm.types import ModelProvider, RuntimeModelProfile


def test_runtime_profile_repr_and_snapshot_never_expose_credential() -> None:
    secret = "super-secret-api-key"
    profile = RuntimeModelProfile(
        profile_id="profile-1",
        provider=ModelProvider.OPENAI_COMPATIBLE,
        base_url="https://llm.example.test/v1/private",
        model_name="example-model",
        credential=secret,
    )

    snapshot = dict(profile.safe_snapshot(adapter_version="mvp0"))
    serialized = json.dumps(snapshot)

    assert secret not in repr(profile)
    assert secret not in serialized
    assert snapshot == {
        "profile_id": "profile-1",
        "provider": "openai_compatible",
        "endpoint_origin": "https://llm.example.test",
        "model_name": "example-model",
        "adapter_version": "mvp0",
    }


def test_runtime_profile_uses_slots_instead_of_a_serializable_dict() -> None:
    profile = RuntimeModelProfile(
        profile_id="profile-1",
        provider="ollama",
        base_url="http://host.docker.internal:11434",
        model_name="qwen",
    )

    assert not hasattr(profile, "__dict__")


def test_runtime_profile_repr_and_snapshot_hide_endpoint_path() -> None:
    hidden_path = "private-tenant-path"
    profile = RuntimeModelProfile(
        profile_id="profile-1",
        provider="openai_compatible",
        base_url=f"https://llm.example.test/v1/{hidden_path}",
        model_name="model",
    )

    assert hidden_path not in repr(profile)
    assert hidden_path not in json.dumps(profile.safe_snapshot(adapter_version="mvp0"))
    assert profile.endpoint_origin == "https://llm.example.test"


@pytest.mark.parametrize(
    "base_url",
    [
        "ftp://llm.example.test",
        "https://user:secret@llm.example.test/v1",
        "https://llm.example.test/v1?api_key=secret",
        "https://llm.example.test/v1#secret",
        "not-a-url",
    ],
)
def test_runtime_profile_rejects_structurally_unsafe_urls(base_url: str) -> None:
    with pytest.raises(ValueError):
        RuntimeModelProfile(
            profile_id="profile-1",
            provider="openai_compatible",
            base_url=base_url,
            model_name="model",
        )
