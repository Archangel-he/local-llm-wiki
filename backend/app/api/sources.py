from __future__ import annotations

import uuid
from collections.abc import Iterator
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..core.errors import ApiError
from ..database import get_db
from ..models import AuditLog
from ..repositories.content import get_source
from ..schemas import SourceRead, SourceUploadResponse
from ..seed import DEFAULT_USER_ID
from ..services.content import (
    IngestConfigurationError,
    create_source_and_job,
    enqueue_ingest_job,
    require_ingest_profile,
)
from ..services.storage import CHUNK_SIZE, StorageError, get_storage
from ..services.uploads import UploadValidationError, prepare_upload

router = APIRouter(prefix="/workspaces/{workspace_id}/sources", tags=["sources"])


@router.post("", response_model=SourceUploadResponse, status_code=status.HTTP_202_ACCEPTED)
def upload_source(
    workspace_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> SourceUploadResponse:
    try:
        require_ingest_profile(db, workspace_id)
    except LookupError as exc:
        raise ApiError(404, "NOT_FOUND", "Workspace not found.") from exc
    except IngestConfigurationError as exc:
        raise ApiError(409, "MODEL_PROFILE_REQUIRED", str(exc)) from exc
    finally:
        # End the read-only preflight transaction before streaming the body to disk.
        db.rollback()

    try:
        prepared = prepare_upload(
            stream=file.file,
            filename=file.filename or "",
            content_type=file.content_type,
            storage=get_storage(),
            max_bytes=settings.max_upload_bytes,
        )
    except UploadValidationError as exc:
        raise ApiError(413 if exc.code == "FILE_TOO_LARGE" else 415, exc.code, str(exc)) from exc
    except StorageError as exc:
        raise ApiError(503, "STORAGE_UNAVAILABLE", "The source could not be stored.") from exc

    try:
        created = create_source_and_job(db, workspace_id, DEFAULT_USER_ID, prepared)
    except LookupError as exc:
        raise ApiError(404, "NOT_FOUND", "Workspace not found.") from exc
    except IngestConfigurationError as exc:
        raise ApiError(409, "MODEL_PROFILE_REQUIRED", str(exc)) from exc

    if created.job.status == "queued" and not created.job.rq_job_id:
        enqueue_ingest_job(db, created.job)

    from ..schemas.content import JobRead

    return SourceUploadResponse(
        source=SourceRead.from_model(created.source),
        job=JobRead.from_model(created.job),
        deduplicated=created.deduplicated,
    )


@router.get("/{source_id}", response_model=SourceRead)
def source(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SourceRead:
    item = get_source(db, workspace_id, source_id)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Source not found.")
    return SourceRead.from_model(item)


def _file_chunks(storage_key: str) -> Iterator[bytes]:
    with get_storage().open(storage_key) as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            yield chunk


@router.get("/{source_id}/content")
def source_content(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    item = get_source(db, workspace_id, source_id)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Source not found.")
    if not get_storage().exists(item.storage_key):
        raise ApiError(503, "STORAGE_UNAVAILABLE", "Source content is unavailable.")
    disposition = f"inline; filename*=UTF-8''{quote(item.safe_filename)}"
    return StreamingResponse(
        _file_chunks(item.storage_key),
        media_type=item.mime_type,
        headers={
            "Content-Disposition": disposition,
            "ETag": f'"sha256:{item.sha256}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_source(
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    item = get_source(db, workspace_id, source_id)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Source not found.")
    if item.status != "archived":
        get_storage().archive(item.storage_key)
        item.status = "archived"
        db.add(
            AuditLog(
                actor_id=DEFAULT_USER_ID,
                workspace_id=workspace_id,
                action="source.archived",
                resource_type="source",
                resource_id=item.id,
                metadata_json={"sha256": item.sha256},
            )
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
