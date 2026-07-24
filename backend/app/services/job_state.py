from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Job


class InvalidJobTransition(RuntimeError):
    pass


def claim_ingest_job(db: Session, job_id: uuid.UUID) -> Job:
    rejection: str | None = None
    with db.begin():
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None or job.job_type != "ingest":
            raise InvalidJobTransition("Ingest job does not exist.")
        if job.status == "cancel_requested":
            job.status = "cancelled"
            job.finished_at = datetime.now(timezone.utc)
            rejection = "Ingest job was cancelled."
        elif job.status not in {"queued", "retrying"}:
            raise InvalidJobTransition("Ingest job is not available for claiming.")
        elif job.attempt >= job.max_attempts:
            job.status = "failed"
            job.error_code = "MAX_ATTEMPTS_EXCEEDED"
            job.error_message_safe = "The job exhausted its retry limit."
            job.finished_at = datetime.now(timezone.utc)
            rejection = "Ingest job exhausted its retry limit."
        else:
            job.attempt += 1
            job.status = "running"
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.heartbeat_at = datetime.now(timezone.utc)
            job.progress_json = {"stage": "starting", "current": 0, "total": 1}
    if rejection is not None:
        raise InvalidJobTransition(rejection)
    return job


def update_job_progress(
    db: Session,
    job_id: uuid.UUID,
    *,
    percent: int,
    stage: str,
    current: int,
    total: int,
) -> None:
    if not 0 <= percent <= 100 or current < 0 or total < 0 or current > total:
        raise ValueError("Job progress is invalid")
    with db.begin():
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None or job.status not in {"running", "cancel_requested"}:
            raise InvalidJobTransition("Job cannot report progress in its current state.")
        job.progress = percent
        job.progress_json = {"stage": stage, "current": current, "total": total}
        job.heartbeat_at = datetime.now(timezone.utc)


def fail_job(
    db: Session,
    job_id: uuid.UUID,
    *,
    error_code: str,
    safe_message: str,
    retryable: bool,
) -> Job:
    with db.begin():
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None or job.status not in {"running", "cancel_requested"}:
            raise InvalidJobTransition("Job cannot fail in its current state.")
        if job.status == "cancel_requested":
            job.status = "cancelled"
        elif retryable and job.attempt < job.max_attempts:
            job.status = "retrying"
            job.rq_job_id = None
        else:
            job.status = "failed"
        job.error_code = error_code
        job.error_message_safe = safe_message
        job.heartbeat_at = datetime.now(timezone.utc)
        if job.status in {"failed", "cancelled"}:
            job.finished_at = datetime.now(timezone.utc)
    return job


def cancellation_requested(db: Session, job_id: uuid.UUID) -> bool:
    status = db.scalar(select(Job.status).where(Job.id == job_id))
    return status in {"cancel_requested", "cancelled"}
