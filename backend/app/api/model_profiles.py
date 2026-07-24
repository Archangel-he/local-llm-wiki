from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.errors import ApiError
from ..database import get_db
from ..repositories.workspaces import (
    get_model_profile,
    get_workspace,
    list_model_profiles,
)
from ..schemas import ModelProfileList, ModelProfileRead

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
