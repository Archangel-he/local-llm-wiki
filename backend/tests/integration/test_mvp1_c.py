from __future__ import annotations

import hashlib
import os
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from redis import Redis
from rq import Queue, SimpleWorker
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import SessionLocal
from app.models import AuditLog, Citation, Job, ModelProfile, PageAlias, Source, WikiLink, WikiPage
from app.seed import (
    DEFAULT_MOCK_PROFILE_ID,
    DEFAULT_USER_ID,
    DEFAULT_WORKSPACE_ID,
    seed_database,
)
from app.services.job_state import InvalidJobTransition, claim_ingest_job, fail_job
from app.services.storage import LocalStorage
from app.worker.jobs import ingest_job

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def database_ready():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        pytest.skip("PostgreSQL integration database is unavailable")
    seed_database()


@pytest.fixture
def redis_connection() -> Redis:
    url = os.environ.get("REDIS_TEST_URL")
    if not url:
        pytest.skip("Set REDIS_TEST_URL to an isolated, disposable Redis database")
    connection = Redis.from_url(url)
    connection.ping()
    connection.flushdb()
    yield connection
    connection.flushdb()
    connection.close()


def _create_queued_job(*, max_attempts: int = 3) -> uuid.UUID:
    marker = uuid.uuid4().hex
    with SessionLocal.begin() as db:
        source = Source(
            workspace_id=DEFAULT_WORKSPACE_ID,
            sha256=marker + marker,
            original_filename=f"state-{marker}.md",
            safe_filename=f"state-{marker}.md",
            mime_type="text/markdown",
            size_bytes=1,
            storage_key=f"raw/state/{marker}",
            status="active",
            created_by=DEFAULT_USER_ID,
        )
        db.add(source)
        db.flush()
        job = Job(
            workspace_id=DEFAULT_WORKSPACE_ID,
            source_id=source.id,
            model_profile_id=DEFAULT_MOCK_PROFILE_ID,
            model_snapshot_json={"provider": "mock", "name": "mock"},
            job_type="ingest",
            status="queued",
            idempotency_key=marker,
            attempt=0,
            max_attempts=max_attempts,
            progress=0,
            progress_json={"stage": "queued", "current": 0, "total": 1},
            created_by=DEFAULT_USER_ID,
        )
        db.add(job)
        db.flush()
        return job.id


def test_retryable_failure_stops_after_three_total_attempts() -> None:
    job_id = _create_queued_job(max_attempts=3)
    for expected_attempt in range(1, 4):
        with SessionLocal() as db:
            claimed = claim_ingest_job(db, job_id)
            assert claimed.attempt == expected_attempt
        with SessionLocal() as db:
            failed = fail_job(
                db,
                job_id,
                error_code="LLM_TIMEOUT",
                safe_message="The model request timed out.",
                retryable=True,
            )
            expected_status = "retrying" if expected_attempt < 3 else "failed"
            assert failed.status == expected_status

    with SessionLocal() as db:
        persisted = db.get(Job, job_id)
        assert persisted is not None
        assert persisted.status == "failed"
        assert persisted.attempt == 3


def test_cancel_requested_job_is_never_claimed() -> None:
    job_id = _create_queued_job()
    with SessionLocal.begin() as db:
        job = db.get(Job, job_id)
        assert job is not None
        job.status = "cancel_requested"

    with SessionLocal() as db, pytest.raises(InvalidJobTransition):
        claim_ingest_job(db, job_id)

    with SessionLocal() as db:
        persisted = db.get(Job, job_id)
        assert persisted is not None
        assert persisted.status == "cancelled"
        assert persisted.attempt == 0


def test_aurora_fixture_executes_real_ingest_job_through_rq(
    redis_connection: Redis,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture_path = Path(__file__).parents[1] / "fixtures" / "aurora.md"
    payload = fixture_path.read_bytes()
    storage = LocalStorage(tmp_path)
    stored = storage.put_immutable(BytesIO(payload))
    monkeypatch.setattr(settings, "local_storage_path", str(tmp_path))

    marker = uuid.uuid4().hex
    with SessionLocal.begin() as db:
        profile = db.get(ModelProfile, DEFAULT_MOCK_PROFILE_ID)
        assert profile is not None and profile.status == "active"
        source = Source(
            workspace_id=DEFAULT_WORKSPACE_ID,
            sha256=hashlib.sha256(payload + marker.encode()).hexdigest(),
            original_filename=f"aurora-{marker[:8]}.md",
            safe_filename=f"aurora-{marker[:8]}.md",
            mime_type="text/markdown",
            size_bytes=len(payload),
            storage_key=stored.storage_key,
            status="active",
            created_by=DEFAULT_USER_ID,
        )
        db.add(source)
        db.flush()
        job = Job(
            workspace_id=DEFAULT_WORKSPACE_ID,
            source_id=source.id,
            model_profile_id=profile.id,
            model_snapshot_json={"provider": "mock", "name": "mock"},
            job_type="ingest",
            status="queued",
            idempotency_key=marker,
            attempt=0,
            max_attempts=3,
            progress=0,
            progress_json={"stage": "queued", "current": 0, "total": 1},
            created_by=DEFAULT_USER_ID,
        )
        db.add(job)
        db.flush()
        job_id = job.id
        source_id = source.id

    queue = Queue(settings.rq_queue_name, connection=redis_connection)
    rq_job = queue.enqueue(
        ingest_job,
        str(job_id),
        job_id=f"ingest-{job_id}-attempt-1",
    )
    worker = SimpleWorker([queue], connection=redis_connection)
    assert worker.work(burst=True, logging_level="WARNING") is True
    rq_job.refresh()
    assert rq_job.is_finished

    with SessionLocal() as db:
        persisted_job = db.get(Job, job_id)
        assert persisted_job is not None
        assert persisted_job.status == "completed"
        assert persisted_job.progress == 100
        assert persisted_job.progress_json["stage"] == "completed"

        source_summary = db.scalar(
            select(WikiPage).where(
                WikiPage.workspace_id == DEFAULT_WORKSPACE_ID,
                WikiPage.primary_source_id == source_id,
                WikiPage.page_type == "source",
            )
        )
        aurora = db.scalar(
            select(WikiPage).where(
                WikiPage.workspace_id == DEFAULT_WORKSPACE_ID,
                WikiPage.slug == "project-aurora",
            )
        )
        lin = db.scalar(
            select(WikiPage).where(
                WikiPage.workspace_id == DEFAULT_WORKSPACE_ID,
                WikiPage.slug == "lin",
            )
        )
        assert source_summary is not None
        assert aurora is not None
        assert lin is not None
        assert db.scalar(
            select(func.count()).select_from(PageAlias).where(
                PageAlias.workspace_id == DEFAULT_WORKSPACE_ID,
                PageAlias.page_id == aurora.id,
                PageAlias.alias_normalized == "aurora project",
            )
        ) == 1
        assert db.scalar(
            select(func.count()).select_from(WikiLink).where(
                WikiLink.workspace_id == DEFAULT_WORKSPACE_ID,
                WikiLink.source_page_id == source_summary.id,
            )
        ) >= 2
        assert db.scalar(
            select(func.count()).select_from(Citation).where(
                Citation.workspace_id == DEFAULT_WORKSPACE_ID,
                Citation.source_id == source_id,
            )
        ) >= 3
        assert db.scalar(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.workspace_id == DEFAULT_WORKSPACE_ID,
                AuditLog.action == "wiki.page_committed",
                AuditLog.metadata_json["job_id"].astext == str(job_id),
            )
        ) >= 3
