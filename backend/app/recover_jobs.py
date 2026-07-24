from __future__ import annotations

from sqlalchemy import select

from .database import SessionLocal
from .models import Job
from .services.content import enqueue_ingest_job


def recover_queued_jobs(limit: int = 100) -> tuple[int, int]:
    recovered = 0
    deferred = 0
    with SessionLocal() as db:
        jobs = list(
            db.scalars(
                select(Job)
                .where(
                    Job.job_type == "ingest",
                    Job.status.in_(["queued", "retrying"]),
                    Job.rq_job_id.is_(None),
                )
                .order_by(Job.created_at, Job.id)
                .limit(limit)
            ).all()
        )
        for job in jobs:
            if enqueue_ingest_job(db, job):
                recovered += 1
            else:
                deferred += 1
    return recovered, deferred


if __name__ == "__main__":
    ready, waiting = recover_queued_jobs()
    print(f"Queued jobs recovery: enqueued={ready} deferred={waiting}")
