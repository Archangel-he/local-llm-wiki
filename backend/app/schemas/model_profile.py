from __future__ import annotations

import uuid
from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from ..models import ModelProfile


class ModelProfileRead(BaseModel):
    id: uuid.UUID
    profile_key: str
    scope: str
    provider: str
    display_name: str
    endpoint_origin: str | None
    model_name: str | None
    has_credential: bool
    capabilities: dict
    status: str
    last_tested_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, profile: ModelProfile) -> "ModelProfileRead":
        endpoint_origin = None
        if profile.base_url:
            parsed = urlsplit(profile.base_url)
            host = parsed.hostname
            if host:
                rendered_host = f"[{host}]" if ":" in host else host
                try:
                    parsed_port = parsed.port
                except ValueError:
                    parsed_port = None
                port = f":{parsed_port}" if parsed_port is not None else ""
                endpoint_origin = f"{parsed.scheme}://{rendered_host}{port}"
        return cls(
            id=profile.id,
            profile_key=profile.profile_key,
            scope=profile.scope,
            provider=profile.provider,
            display_name=profile.display_name,
            endpoint_origin=endpoint_origin,
            model_name=profile.model_name,
            has_credential=profile.credential_ciphertext is not None,
            capabilities=profile.capabilities_json,
            status=profile.status,
            last_tested_at=profile.last_tested_at,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )


class ModelProfileList(BaseModel):
    items: list[ModelProfileRead]
    next_cursor: str | None = None


class ModelProfileCreate(BaseModel):
    profile_key: str | None = Field(default=None, min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    provider: str
    base_url: str = Field(min_length=1, max_length=2000)
    model_name: str = Field(min_length=1, max_length=300)
    api_key: str | None = Field(default=None, min_length=1, max_length=8192)


class ModelProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    base_url: str | None = Field(default=None, min_length=1, max_length=2000)
    model_name: str | None = Field(default=None, min_length=1, max_length=300)
    api_key: str | None = Field(default=None, min_length=1, max_length=8192)


class ModelDiscoveryRequest(BaseModel):
    profile_id: uuid.UUID | None = None
    provider: str
    base_url: str = Field(min_length=1, max_length=2000)
    api_key: str | None = Field(default=None, min_length=1, max_length=8192)


class ModelDiscoveryResult(BaseModel):
    items: list[str]


class ModelPolicyUpdate(BaseModel):
    default_model_profile_id: uuid.UUID


class ModelProfileTestResult(BaseModel):
    reachable: bool
    model_found: bool
    streaming_supported: bool
    structured_output_supported: bool
    latency_ms: int | None = None
    safe_reason: str | None = None
