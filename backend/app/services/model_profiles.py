from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from ..config import settings
from ..llm import RuntimeModelProfile, create_adapter
from ..llm.errors import LLMAdapterError
from ..llm.types import ConnectionTestResult
from ..models import AuditLog, ModelProfile
from ..schemas.model_profile import ModelProfileCreate, ModelProfileUpdate
from ..seed import DEFAULT_USER_ID
from .credentials import (
    CredentialEncryptionUnavailable,
    credential_cipher_from_settings,
)


class InvalidModelProfile(ValueError):
    pass


def normalize_profile_key(value: str | None, display_name: str, profile_id: uuid.UUID) -> str:
    candidate = unicodedata.normalize("NFKC", value or display_name).strip().lower()
    candidate = re.sub(r"[^a-z0-9]+", "-", candidate).strip("-")
    return (candidate[:100] or f"profile-{profile_id.hex[:8]}")


def normalize_base_url(value: str) -> str:
    candidate = value.strip().rstrip("/")
    parts = urlsplit(candidate)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise InvalidModelProfile("Base URL must be an absolute HTTP(S) URL.")
    if parts.username is not None or parts.password is not None:
        raise InvalidModelProfile("Base URL must not contain user information.")
    if parts.query or parts.fragment:
        raise InvalidModelProfile("Base URL must not contain a query or fragment.")
    try:
        _ = parts.port
    except ValueError as exc:
        raise InvalidModelProfile("Base URL contains an invalid port.") from exc
    if settings.app_env != "local" and parts.scheme != "https":
        raise InvalidModelProfile("Non-local model endpoints must use HTTPS.")
    return candidate


def create_workspace_profile(
    db: Session,
    workspace_id: uuid.UUID,
    payload: ModelProfileCreate,
) -> ModelProfile:
    if payload.provider not in {"ollama", "openai_compatible"}:
        raise InvalidModelProfile("Provider must be ollama or openai_compatible.")
    profile_id = uuid.uuid4()
    profile = ModelProfile(
        id=profile_id,
        scope="workspace",
        workspace_id=workspace_id,
        owner_user_id=None,
        profile_key=normalize_profile_key(payload.profile_key, payload.display_name, profile_id),
        provider=payload.provider,
        display_name=payload.display_name.strip(),
        base_url=normalize_base_url(payload.base_url),
        model_name=payload.model_name.strip(),
        capabilities_json={},
        status="untested",
        created_by=DEFAULT_USER_ID,
    )
    if payload.api_key is not None:
        encrypted = credential_cipher_from_settings().encrypt(payload.api_key, profile_id)
        profile.credential_ciphertext = encrypted.ciphertext
        profile.credential_key_version = encrypted.key_version
    db.add(profile)
    db.flush()
    db.add(
        AuditLog(
            actor_id=DEFAULT_USER_ID,
            workspace_id=workspace_id,
            action="model_profile.created",
            resource_type="model_profile",
            resource_id=profile.id,
            metadata_json={
                "provider": profile.provider,
                "model": profile.model_name,
                "profile_key": profile.profile_key,
            },
        )
    )
    db.commit()
    return profile


def update_workspace_profile(
    db: Session,
    profile: ModelProfile,
    payload: ModelProfileUpdate,
) -> ModelProfile:
    if payload.display_name is not None:
        profile.display_name = payload.display_name.strip()
    if payload.base_url is not None:
        profile.base_url = normalize_base_url(payload.base_url)
    if payload.model_name is not None:
        profile.model_name = payload.model_name.strip()
    if payload.api_key is not None:
        encrypted = credential_cipher_from_settings().encrypt(payload.api_key, profile.id)
        profile.credential_ciphertext = encrypted.ciphertext
        profile.credential_key_version = encrypted.key_version
    profile.status = "untested"
    profile.capabilities_json = {}
    db.add(
        AuditLog(
            actor_id=DEFAULT_USER_ID,
            workspace_id=profile.workspace_id,
            action="model_profile.updated",
            resource_type="model_profile",
            resource_id=profile.id,
            metadata_json={"provider": profile.provider, "model": profile.model_name},
        )
    )
    db.commit()
    return profile


def runtime_profile(profile: ModelProfile) -> RuntimeModelProfile:
    credential = None
    if profile.credential_ciphertext is not None:
        if profile.credential_key_version is None:
            raise CredentialEncryptionUnavailable("Credential key version is missing")
        credential = credential_cipher_from_settings().decrypt(
            profile.credential_ciphertext,
            profile.credential_key_version,
            profile.id,
        )
    return RuntimeModelProfile(
        profile_id=str(profile.id),
        provider=profile.provider,
        base_url=(
            profile.base_url or "mock://local"
            if profile.provider == "mock"
            else profile.base_url or ""
        ),
        model_name=profile.model_name or "",
        credential=credential,
    )


async def test_workspace_profile(db: Session, profile: ModelProfile) -> ConnectionTestResult:
    try:
        runtime = runtime_profile(profile)
        result = await create_adapter(runtime.provider).test_connection(runtime)
    except (CredentialEncryptionUnavailable, LLMAdapterError, ValueError):
        result = ConnectionTestResult(
            reachable=False,
            model_found=False,
            streaming_supported=False,
            structured_output_supported=False,
            safe_reason="connection_test_failed",
        )
    profile.status = "active" if result.reachable and result.model_found else "invalid"
    profile.last_tested_at = datetime.now(timezone.utc)
    profile.capabilities_json = {
        "streaming": result.streaming_supported,
        "structured_output": result.structured_output_supported,
    }
    db.add(
        AuditLog(
            actor_id=DEFAULT_USER_ID,
            workspace_id=profile.workspace_id,
            action="model_profile.tested",
            resource_type="model_profile",
            resource_id=profile.id,
            metadata_json={
                "provider": profile.provider,
                "model": profile.model_name,
                "reachable": result.reachable,
                "model_found": result.model_found,
                "safe_reason": result.safe_reason,
            },
        )
    )
    db.commit()
    return result
