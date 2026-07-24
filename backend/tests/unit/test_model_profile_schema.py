from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models import ModelProfile
from app.schemas import ModelProfileRead


def test_public_profile_schema_redacts_endpoint_and_credentials():
    now = datetime.now(UTC)
    profile = ModelProfile(
        id=uuid.uuid4(),
        scope="workspace",
        workspace_id=uuid.uuid4(),
        owner_user_id=None,
        profile_key="private-service",
        provider="openai_compatible",
        display_name="Private service",
        base_url="https://user:password@llm.example.test/v1/private",
        model_name="example-model",
        credential_ciphertext=b"ciphertext",
        credential_key_version=1,
        capabilities_json={"streaming": True},
        status="active",
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )

    payload = ModelProfileRead.from_model(profile).model_dump(mode="json")

    assert payload["endpoint_origin"] == "https://llm.example.test"
    assert payload["has_credential"] is True
    assert "base_url" not in payload
    assert "credential_ciphertext" not in payload
    assert "credential_key_version" not in payload
