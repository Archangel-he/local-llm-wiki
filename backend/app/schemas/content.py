from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..models import Job, Source


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    filename: str
    sha256: str
    mime_type: str
    size_bytes: int
    status: str
    created_at: datetime

    @classmethod
    def from_model(cls, source: Source) -> "SourceRead":
        return cls(
            id=source.id,
            workspace_id=source.workspace_id,
            filename=source.original_filename,
            sha256=source.sha256,
            mime_type=source.mime_type,
            size_bytes=source.size_bytes,
            status=source.status,
            created_at=source.created_at,
        )


class JobModelSnapshot(BaseModel):
    provider: str
    name: str | None
    endpoint_origin: str | None = None
    adapter_version: str = "mvp1-v1"


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    source_id: uuid.UUID | None
    type: str
    status: str
    model_profile_id: uuid.UUID | None
    model: JobModelSnapshot | None
    attempt: int
    max_attempts: int
    progress: dict
    error: dict | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_model(cls, job: Job) -> "JobRead":
        snapshot = (
            JobModelSnapshot.model_validate(job.model_snapshot_json)
            if job.model_snapshot_json
            else None
        )
        error = None
        if job.error_code:
            error = {"code": job.error_code, "message": job.error_message_safe or "Job failed."}
        progress = dict(job.progress_json or {})
        progress.setdefault("percent", job.progress)
        return cls(
            id=job.id,
            workspace_id=job.workspace_id,
            source_id=job.source_id,
            type=job.job_type,
            status=job.status,
            model_profile_id=job.model_profile_id,
            model=snapshot,
            attempt=job.attempt,
            max_attempts=job.max_attempts,
            progress=progress,
            error=error,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


class SourceUploadResponse(BaseModel):
    source: SourceRead
    job: JobRead
    deduplicated: bool = False


class JobList(BaseModel):
    items: list[JobRead]
    next_cursor: str | None = None


class JobEvent(BaseModel):
    event: str
    data: dict = Field(default_factory=dict)
