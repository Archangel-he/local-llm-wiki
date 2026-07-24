from __future__ import annotations

import uuid
from collections.abc import Iterator
from urllib.parse import quote

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.errors import ApiError
from ..database import get_db
from ..models import Job
from ..repositories.content import get_job
from ..schemas.exports import ExportCreate, ExportRead
from ..seed import DEFAULT_USER_ID
from ..services.exports import create_export_job, enqueue_export_job
from ..services.storage import CHUNK_SIZE, get_storage

router = APIRouter(prefix="/workspaces/{workspace_id}/exports", tags=["exports"])


def _export_job(db: Session, workspace_id: uuid.UUID, export_id: uuid.UUID) -> Job:
    job = get_job(db, workspace_id, export_id)
    if job is None or job.job_type != "export":
        raise ApiError(404, "NOT_FOUND", "Export not found.")
    return job


@router.post("", response_model=ExportRead, status_code=status.HTTP_202_ACCEPTED)
def create_export(
    workspace_id: uuid.UUID,
    body: ExportCreate,
    db: Session = Depends(get_db),
) -> ExportRead:
    try:
        job = create_export_job(
            db,
            workspace_id,
            DEFAULT_USER_ID,
            include_raw=body.include_raw,
        )
    except LookupError as exc:
        raise ApiError(404, "NOT_FOUND", "Workspace not found.") from exc
    if job.status in {"queued", "retrying"} and not job.rq_job_id:
        enqueue_export_job(db, job)
    return ExportRead.from_job(job)


@router.get("/{export_id}", response_model=ExportRead)
def export(
    workspace_id: uuid.UUID,
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ExportRead:
    return ExportRead.from_job(_export_job(db, workspace_id, export_id))


def _chunks(storage_key: str) -> Iterator[bytes]:
    with get_storage().open(storage_key) as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            yield chunk


@router.get("/{export_id}/download")
def download_export(
    workspace_id: uuid.UUID,
    export_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    job = _export_job(db, workspace_id, export_id)
    progress = dict(job.progress_json or {})
    if job.status != "completed":
        raise ApiError(409, "EXPORT_NOT_READY", "The export is not ready for download.")
    storage_key = progress.get("storage_key")
    if not storage_key or not get_storage().exists(storage_key):
        raise ApiError(503, "STORAGE_UNAVAILABLE", "The export file is unavailable.")
    filename = progress.get("filename") or f"local-llm-wiki-{export_id}.zip"
    return StreamingResponse(
        _chunks(storage_key),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "ETag": f'"sha256:{progress.get("sha256", "")}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
