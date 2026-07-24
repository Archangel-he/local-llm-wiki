from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Job, Source


def get_source(db: Session, workspace_id: uuid.UUID, source_id: uuid.UUID) -> Source | None:
    return db.scalar(
        select(Source).where(Source.id == source_id, Source.workspace_id == workspace_id)
    )


def get_source_by_hash(db: Session, workspace_id: uuid.UUID, sha256: str) -> Source | None:
    return db.scalar(
        select(Source).where(Source.workspace_id == workspace_id, Source.sha256 == sha256)
    )


def get_job(db: Session, workspace_id: uuid.UUID, job_id: uuid.UUID) -> Job | None:
    return db.scalar(select(Job).where(Job.id == job_id, Job.workspace_id == workspace_id))


def list_jobs(db: Session, workspace_id: uuid.UUID, limit: int = 100) -> list[Job]:
    return list(
        db.scalars(
            select(Job)
            .where(Job.workspace_id == workspace_id)
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(limit)
        ).all()
    )


def latest_source_job(db: Session, workspace_id: uuid.UUID, source_id: uuid.UUID) -> Job | None:
    return db.scalar(
        select(Job)
        .where(
            Job.workspace_id == workspace_id,
            Job.source_id == source_id,
            Job.job_type == "ingest",
        )
        .order_by(Job.created_at.desc(), Job.id.desc())
        .limit(1)
    )
