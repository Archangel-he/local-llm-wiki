from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    slug: str
    status: str
    schema_version: int
    default_model_profile_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class WorkspaceList(BaseModel):
    items: list[WorkspaceRead]
    next_cursor: str | None = None
