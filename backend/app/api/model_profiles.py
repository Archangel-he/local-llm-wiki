from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.errors import ApiError
from ..database import get_db
from ..models import AuditLog
from ..repositories.workspaces import (
    get_model_profile,
    get_workspace,
    list_model_profiles,
)
from ..schemas import (
    ModelPolicyUpdate,
    ModelProfileCreate,
    ModelProfileList,
    ModelProfileRead,
    ModelProfileTestResult,
    ModelProfileUpdate,
)
from ..seed import DEFAULT_USER_ID
from ..services.credentials import CredentialEncryptionUnavailable
from ..services.model_profiles import (
    InvalidModelProfile,
    create_workspace_profile,
    test_workspace_profile,
    update_workspace_profile,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/model-profiles", tags=["model-profiles"])


def _require_workspace(db: Session, workspace_id: uuid.UUID) -> None:
    if get_workspace(db, workspace_id) is None:
        raise ApiError(404, "NOT_FOUND", "Workspace not found.")


@router.get("", response_model=ModelProfileList)
def profiles(workspace_id: uuid.UUID, db: Session = Depends(get_db)) -> ModelProfileList:
    _require_workspace(db, workspace_id)
    return ModelProfileList(
        items=[
            ModelProfileRead.from_model(profile)
            for profile in list_model_profiles(db, workspace_id)
        ]
    )


@router.post("", response_model=ModelProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(
    workspace_id: uuid.UUID,
    payload: ModelProfileCreate,
    db: Session = Depends(get_db),
) -> ModelProfileRead:
    _require_workspace(db, workspace_id)
    try:
        item = create_workspace_profile(db, workspace_id, payload)
    except InvalidModelProfile as exc:
        db.rollback()
        raise ApiError(422, "VALIDATION_ERROR", str(exc)) from exc
    except CredentialEncryptionUnavailable as exc:
        db.rollback()
        raise ApiError(503, "MODEL_PROFILE_INVALID", str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "MODEL_PROFILE_INVALID", "Profile key already exists.") from exc
    return ModelProfileRead.from_model(item)


@router.get("/{profile_id}", response_model=ModelProfileRead)
def profile(
    workspace_id: uuid.UUID,
    profile_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ModelProfileRead:
    _require_workspace(db, workspace_id)
    item = get_model_profile(db, workspace_id, profile_id)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Model profile not found.")
    return ModelProfileRead.from_model(item)


@router.patch("/{profile_id}", response_model=ModelProfileRead)
def update_profile(
    workspace_id: uuid.UUID,
    profile_id: uuid.UUID,
    payload: ModelProfileUpdate,
    db: Session = Depends(get_db),
) -> ModelProfileRead:
    item = get_model_profile(db, workspace_id, profile_id)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Model profile not found.")
    if item.provider == "mock":
        raise ApiError(409, "MODEL_PROFILE_INVALID", "The built-in Mock profile is immutable.")
    try:
        item = update_workspace_profile(db, item, payload)
    except InvalidModelProfile as exc:
        db.rollback()
        raise ApiError(422, "VALIDATION_ERROR", str(exc)) from exc
    except CredentialEncryptionUnavailable as exc:
        db.rollback()
        raise ApiError(503, "MODEL_PROFILE_INVALID", str(exc)) from exc
    return ModelProfileRead.from_model(item)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_profile(
    workspace_id: uuid.UUID,
    profile_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    workspace = get_workspace(db, workspace_id)
    item = get_model_profile(db, workspace_id, profile_id)
    if workspace is None or item is None:
        raise ApiError(404, "NOT_FOUND", "Model profile not found.")
    if item.provider == "mock":
        raise ApiError(409, "MODEL_PROFILE_INVALID", "The built-in Mock profile is immutable.")
    item.status = "revoked"
    item.credential_ciphertext = None
    item.credential_key_version = None
    if workspace.default_model_profile_id == item.id:
        workspace.default_model_profile_id = None
    db.add(
        AuditLog(
            actor_id=DEFAULT_USER_ID,
            workspace_id=workspace_id,
            action="model_profile.revoked",
            resource_type="model_profile",
            resource_id=item.id,
            metadata_json={"provider": item.provider, "model": item.model_name},
        )
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{profile_id}/test", response_model=ModelProfileTestResult)
async def test_profile(
    workspace_id: uuid.UUID,
    profile_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ModelProfileTestResult:
    item = get_model_profile(db, workspace_id, profile_id)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Model profile not found.")
    if item.provider == "mock":
        return ModelProfileTestResult(
            reachable=True,
            model_found=True,
            streaming_supported=True,
            structured_output_supported=True,
            latency_ms=0,
        )
    result = await test_workspace_profile(db, item)
    return ModelProfileTestResult(
        reachable=result.reachable,
        model_found=result.model_found,
        streaming_supported=result.streaming_supported,
        structured_output_supported=result.structured_output_supported,
        latency_ms=result.latency_ms,
        safe_reason=result.safe_reason,
    )


@router.put("/policy/default", response_model=ModelProfileRead)
def update_model_policy(
    workspace_id: uuid.UUID,
    payload: ModelPolicyUpdate,
    db: Session = Depends(get_db),
) -> ModelProfileRead:
    workspace = get_workspace(db, workspace_id)
    profile = get_model_profile(db, workspace_id, payload.default_model_profile_id)
    if workspace is None or profile is None:
        raise ApiError(404, "NOT_FOUND", "Workspace or model profile not found.")
    if profile.status != "active":
        raise ApiError(409, "MODEL_PROFILE_INVALID", "Only an active profile can be selected.")
    workspace.default_model_profile_id = profile.id
    db.add(
        AuditLog(
            actor_id=DEFAULT_USER_ID,
            workspace_id=workspace_id,
            action="model_policy.updated",
            resource_type="model_profile",
            resource_id=profile.id,
            metadata_json={"provider": profile.provider, "model": profile.model_name},
        )
    )
    db.commit()
    return ModelProfileRead.from_model(profile)
