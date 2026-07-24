from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from ..models import Job


class ExportCreate(BaseModel):
    include_raw: bool = True


class ExportRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    status: str
    progress: dict
    error: dict | None
    filename: str | None
    sha256: str | None
    size_bytes: int | None
    created_at: datetime
    finished_at: datetime | None

    @classmethod
    def from_job(cls, job: Job) -> "ExportRead":
        progress = dict(job.progress_json or {})
        error = None
        if job.error_code:
            error = {
                "code": job.error_code,
                "message": job.error_message_safe or "Export failed.",
            }
        return cls(
            id=job.id,
            workspace_id=job.workspace_id,
            status=job.status,
            progress=progress,
            error=error,
            filename=progress.get("filename"),
            sha256=progress.get("sha256"),
            size_bytes=progress.get("size_bytes"),
            created_at=job.created_at,
            finished_at=job.finished_at,
        )
