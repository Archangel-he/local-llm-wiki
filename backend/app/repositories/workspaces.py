from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ModelProfile, Workspace


def list_workspaces(db: Session) -> list[Workspace]:
    return list(db.scalars(select(Workspace).order_by(Workspace.created_at, Workspace.id)).all())


def get_workspace(db: Session, workspace_id: uuid.UUID) -> Workspace | None:
    return db.scalar(select(Workspace).where(Workspace.id == workspace_id))


def list_model_profiles(db: Session, workspace_id: uuid.UUID) -> list[ModelProfile]:
    return list(
        db.scalars(
            select(ModelProfile)
            .where(
                ModelProfile.workspace_id == workspace_id,
                ModelProfile.status != "revoked",
            )
            .order_by(ModelProfile.created_at, ModelProfile.id)
        ).all()
    )


def get_model_profile(
    db: Session, workspace_id: uuid.UUID, profile_id: uuid.UUID
) -> ModelProfile | None:
    return db.scalar(
        select(ModelProfile).where(
            ModelProfile.id == profile_id,
            ModelProfile.workspace_id == workspace_id,
            ModelProfile.status != "revoked",
        )
    )
