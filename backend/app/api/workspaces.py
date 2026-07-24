from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.errors import ApiError
from ..database import get_db
from ..repositories.workspaces import get_workspace, list_workspaces
from ..schemas import WorkspaceList, WorkspaceRead

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=WorkspaceList)
def workspaces(db: Session = Depends(get_db)) -> WorkspaceList:
    return WorkspaceList(items=[WorkspaceRead.model_validate(item) for item in list_workspaces(db)])


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def workspace(workspace_id: uuid.UUID, db: Session = Depends(get_db)) -> WorkspaceRead:
    item = get_workspace(db, workspace_id)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Workspace not found.")
    return WorkspaceRead.model_validate(item)
