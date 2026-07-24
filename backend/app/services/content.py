from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuditLog, Job, ModelProfile, Source, Workspace
from ..repositories.content import latest_source_job
from .uploads import PreparedUpload


class IngestConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CreatedIngest:
    source: Source
    job: Job
    deduplicated: bool


def require_ingest_profile(db: Session, workspace_id: uuid.UUID) -> ModelProfile:
    workspace = db.scalar(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.status == "active")
    )
    if workspace is None:
        raise LookupError("workspace")
    if workspace.default_model_profile_id is None:
        raise IngestConfigurationError("Workspace has no default model profile.")
    profile = db.scalar(
        select(ModelProfile).where(
            ModelProfile.id == workspace.default_model_profile_id,
            ModelProfile.workspace_id == workspace_id,
            ModelProfile.scope == "workspace",
        )
    )
    if profile is None or profile.status != "active":
        raise IngestConfigurationError("Workspace default model profile is not active.")
    return profile


def _endpoint_origin(base_url: str | None) -> str | None:
    if not base_url:
        return None
    parsed = urlsplit(base_url)
    if not parsed.hostname:
        return None
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    try:
        port = f":{parsed.port}" if parsed.port is not None else ""
    except ValueError:
        port = ""
    return f"{parsed.scheme}://{host}{port}"


def _model_snapshot(profile: ModelProfile) -> dict[str, str | None]:
    return {
        "provider": profile.provider,
        "name": profile.model_name,
        "endpoint_origin": _endpoint_origin(profile.base_url),
        "adapter_version": "mvp1-v1",
    }


def _idempotency_key(
    workspace: Workspace,
    source_sha256: str,
    profile: ModelProfile,
) -> str:
    payload = {
        "workspace_id": str(workspace.id),
        "source_sha256": source_sha256,
        "parser_version": settings.parser_version,
        "schema_version": workspace.schema_version,
        "model_profile_id": str(profile.id),
        "model_name": profile.model_name,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def create_source_and_job(
    db: Session,
    workspace_id: uuid.UUID,
    actor_id: uuid.UUID,
    upload: PreparedUpload,
) -> CreatedIngest:
    profile = require_ingest_profile(db, workspace_id)
    workspace = db.get(Workspace, workspace_id)
    assert workspace is not None

    source_id = uuid.uuid4()
    inserted_source_id = db.scalar(
        insert(Source)
        .values(
            id=source_id,
            workspace_id=workspace_id,
            sha256=upload.stored.sha256,
            original_filename=upload.original_filename,
            safe_filename=upload.safe_filename,
            mime_type=upload.mime_type,
            size_bytes=upload.stored.size_bytes,
            storage_key=upload.stored.storage_key,
            status="active",
            created_by=actor_id,
        )
        .on_conflict_do_nothing(index_elements=[Source.workspace_id, Source.sha256])
        .returning(Source.id)
    )

    deduplicated = inserted_source_id is None
    if deduplicated:
        source = db.scalar(
            select(Source).where(
                Source.workspace_id == workspace_id,
                Source.sha256 == upload.stored.sha256,
            )
        )
        assert source is not None
        existing_job = latest_source_job(db, workspace_id, source.id)
        if existing_job is not None:
            db.commit()
            return CreatedIngest(source=source, job=existing_job, deduplicated=True)
    else:
        source = db.get(Source, inserted_source_id)
        assert source is not None

    job = Job(
        workspace_id=workspace_id,
        source_id=source.id,
        model_profile_id=profile.id,
        model_snapshot_json=_model_snapshot(profile),
        job_type="ingest",
        status="queued",
        idempotency_key=_idempotency_key(workspace, source.sha256, profile),
        attempt=0,
        max_attempts=settings.job_max_attempts,
        progress=0,
        progress_json={"stage": "queued", "current": 0, "total": 1},
        created_by=actor_id,
    )
    db.add(job)
    db.flush()
    db.add(
        AuditLog(
            actor_id=actor_id,
            workspace_id=workspace_id,
            action="source.uploaded",
            resource_type="source",
            resource_id=source.id,
            metadata_json={
                "job_id": str(job.id),
                "sha256": source.sha256,
                "size_bytes": source.size_bytes,
                "mime_type": source.mime_type,
            },
        )
    )
    db.commit()
    return CreatedIngest(source=source, job=job, deduplicated=deduplicated)


def enqueue_ingest_job(db: Session, job: Job) -> bool:
    connection: Redis | None = None
    try:
        connection = Redis.from_url(
            settings.redis_url,
            decode_responses=False,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        queue = Queue(settings.rq_queue_name, connection=connection)
        rq_job_id = f"ingest-{job.id}-attempt-{job.attempt + 1}"
        queue.enqueue(
            "app.worker.jobs.ingest_job",
            str(job.id),
            job_id=rq_job_id,
            job_timeout=settings.ingest_job_timeout_seconds,
        )
        job.rq_job_id = rq_job_id
        db.commit()
        return True
    except (RedisError, ValueError, RuntimeError):
        db.rollback()
        return False
    finally:
        if connection is not None:
            connection.close()
