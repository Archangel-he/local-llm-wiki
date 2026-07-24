from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.errors import ApiError
from ..database import SessionLocal, get_db
from ..models import AuditLog
from ..repositories.content import get_job, list_jobs
from ..schemas import JobList, JobRead
from ..seed import DEFAULT_USER_ID
from ..services.content import enqueue_ingest_job
from ..services.exports import enqueue_export_job

router = APIRouter(prefix="/workspaces/{workspace_id}/jobs", tags=["jobs"])
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


@router.get("", response_model=JobList)
def jobs(workspace_id: uuid.UUID, db: Session = Depends(get_db)) -> JobList:
    return JobList(items=[JobRead.from_model(item) for item in list_jobs(db, workspace_id)])


@router.get("/{job_id}", response_model=JobRead)
def job(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> JobRead:
    item = get_job(db, workspace_id, job_id)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Job not found.")
    return JobRead.from_model(item)


@router.post("/{job_id}/retry", response_model=JobRead)
def retry_job(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> JobRead:
    item = get_job(db, workspace_id, job_id)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Job not found.")
    if item.status != "failed" or item.attempt >= item.max_attempts:
        raise ApiError(409, "JOB_ALREADY_EXISTS", "The job cannot be retried.")
    item.status = "queued"
    item.error_code = None
    item.error_message_safe = None
    item.finished_at = None
    item.rq_job_id = None
    item.progress = 0
    item.progress_json = {"stage": "queued", "current": 0, "total": 1}
    db.add(
        AuditLog(
            actor_id=DEFAULT_USER_ID,
            workspace_id=workspace_id,
            action="job.retried",
            resource_type="job",
            resource_id=item.id,
            metadata_json={"attempt": item.attempt, "max_attempts": item.max_attempts},
        )
    )
    db.commit()
    if item.job_type == "ingest":
        enqueue_ingest_job(db, item)
    elif item.job_type == "export":
        enqueue_export_job(db, item)
    else:
        raise ApiError(409, "JOB_NOT_RETRYABLE", "This job type cannot be retried.")
    return JobRead.from_model(item)


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> JobRead:
    item = get_job(db, workspace_id, job_id)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "Job not found.")
    if item.status == "queued":
        item.status = "cancelled"
        item.finished_at = datetime.now(timezone.utc)
    elif item.status in {"running", "retrying"}:
        item.status = "cancel_requested"
    elif item.status not in {"cancelled", "cancel_requested"}:
        raise ApiError(409, "JOB_NOT_CANCELLABLE", "The job cannot be cancelled.")
    db.add(
        AuditLog(
            actor_id=DEFAULT_USER_ID,
            workspace_id=workspace_id,
            action="job.cancel_requested",
            resource_type="job",
            resource_id=item.id,
            metadata_json={"status": item.status},
        )
    )
    db.commit()
    return JobRead.from_model(item)


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


@router.get("/{job_id}/events")
async def job_events(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    request: Request,
) -> StreamingResponse:
    with SessionLocal() as db:
        if get_job(db, workspace_id, job_id) is None:
            raise ApiError(404, "NOT_FOUND", "Job not found.")

    async def stream():
        previous: str | None = None
        heartbeat = 0
        while not await request.is_disconnected():
            with SessionLocal() as db:
                item = get_job(db, workspace_id, job_id)
                if item is None:
                    return
                payload = JobRead.from_model(item).model_dump_json()
                if payload != previous:
                    if item.status in TERMINAL_STATUSES:
                        event = item.status
                    else:
                        event = "snapshot" if previous is None else "progress"
                    yield _sse(event, payload)
                    previous = payload
                    if item.status in TERMINAL_STATUSES:
                        return
            heartbeat += 1
            if heartbeat >= 15:
                yield _sse("heartbeat", "{}")
                heartbeat = 0
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
