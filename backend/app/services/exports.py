from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import uuid
import zipfile
from datetime import datetime, timezone

import yaml
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import (
    AuditLog,
    Citation,
    Job,
    PageAlias,
    Source,
    WikiLink,
    WikiPage,
    WikiRevision,
    Workspace,
)
from ..seed import DEFAULT_USER_ID
from .job_state import (
    InvalidJobTransition,
    cancellation_requested,
    claim_export_job,
    fail_job,
    update_job_progress,
)
from .storage import StorageError, get_storage

LOGGER = logging.getLogger("wiki.export")
PAGE_DIRECTORIES = {
    "source": "sources",
    "entity": "entities",
    "topic": "concepts",
    "analysis": "analyses",
    "question": "questions",
}


def _snapshot_digest(
    db: Session, workspace_id: uuid.UUID, *, include_raw: bool
) -> tuple[Workspace, str]:
    workspace = db.scalar(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.status == "active",
        )
    )
    if workspace is None:
        raise LookupError("workspace")
    revisions = list(
        db.execute(
            select(WikiPage.id, WikiPage.current_revision_id)
            .where(
                WikiPage.workspace_id == workspace_id,
                WikiPage.status != "archived",
                WikiPage.current_revision_id.is_not(None),
            )
            .order_by(WikiPage.id)
        ).all()
    )
    activity_head = db.scalar(
        select(AuditLog.id)
        .where(
            AuditLog.workspace_id == workspace_id,
            ~AuditLog.action.like("export.%"),
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    )
    raw_sources = (
        list(
            db.execute(
                select(Source.id, Source.sha256)
                .where(
                    Source.workspace_id == workspace_id,
                    Source.status == "active",
                )
                .order_by(Source.id)
            ).all()
        )
        if include_raw
        else []
    )
    payload = {
        "workspace_id": str(workspace.id),
        "schema_version": workspace.schema_version,
        "include_raw": include_raw,
        "revisions": [(str(page_id), str(revision_id)) for page_id, revision_id in revisions],
        "activity_head": str(activity_head) if activity_head else None,
        "raw_sources": [
            (str(source_id), sha256) for source_id, sha256 in raw_sources
        ],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return workspace, digest


def create_export_job(
    db: Session,
    workspace_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    include_raw: bool = True,
) -> Job:
    _, snapshot = _snapshot_digest(db, workspace_id, include_raw=include_raw)
    idempotency_key = hashlib.sha256(f"export:{snapshot}".encode()).hexdigest()
    existing = db.scalar(
        select(Job).where(
            Job.workspace_id == workspace_id,
            Job.job_type == "export",
            Job.idempotency_key == idempotency_key,
            Job.status.in_(
                {"queued", "running", "retrying", "completed", "cancel_requested"}
            ),
        )
    )
    if existing is not None:
        progress = dict(existing.progress_json or {})
        storage_key = progress.get("storage_key")
        if existing.status == "completed" and (
            not storage_key or not get_storage().exists(storage_key)
        ):
            existing.status = "queued"
            existing.attempt = 0
            existing.progress = 0
            existing.progress_json = {
                "stage": "queued",
                "current": 0,
                "total": 1,
                "include_raw": include_raw,
                "snapshot": snapshot,
            }
            existing.error_code = None
            existing.error_message_safe = None
            existing.rq_job_id = None
            existing.finished_at = None
            db.add(
                AuditLog(
                    actor_id=actor_id,
                    workspace_id=workspace_id,
                    action="export.recovered",
                    resource_type="export",
                    resource_id=existing.id,
                    metadata_json={"reason": "artifact_missing"},
                )
            )
            db.commit()
        return existing

    job = Job(
        workspace_id=workspace_id,
        source_id=None,
        model_profile_id=None,
        model_snapshot_json=None,
        job_type="export",
        status="queued",
        idempotency_key=idempotency_key,
        attempt=0,
        max_attempts=settings.job_max_attempts,
        progress=0,
        progress_json={
            "stage": "queued",
            "current": 0,
            "total": 1,
            "include_raw": include_raw,
            "snapshot": snapshot,
        },
        created_by=actor_id,
    )
    db.add(job)
    db.flush()
    db.add(
        AuditLog(
            actor_id=actor_id,
            workspace_id=workspace_id,
            action="export.created",
            resource_type="export",
            resource_id=job.id,
            metadata_json={"include_raw": include_raw, "snapshot": snapshot},
        )
    )
    db.commit()
    return job


def enqueue_export_job(db: Session, job: Job) -> bool:
    connection: Redis | None = None
    try:
        connection = Redis.from_url(
            settings.redis_url,
            decode_responses=False,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        queue = Queue(settings.rq_queue_name, connection=connection)
        rq_job_id = f"export-{job.id}-attempt-{job.attempt + 1}"
        queue.enqueue(
            "app.worker.jobs.export_job",
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


def _rewrite_wikilinks(markdown: str, slug_by_name: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        target, separator, label = match.group(1).partition("|")
        slug = slug_by_name.get(target.strip().casefold(), target.strip())
        return f"[[{slug}{separator}{label}]]"

    return re.sub(r"\[\[([^\]]+)\]\]", replace, markdown)


def _frontmatter(document: dict) -> str:
    return "---\n" + yaml.safe_dump(
        document,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip() + "\n---\n\n"


def _zip_bytes(db: Session, job: Job) -> bytes:
    workspace = db.get(Workspace, job.workspace_id)
    if workspace is None:
        raise LookupError("workspace")
    pages = list(
        db.scalars(
            select(WikiPage)
            .where(
                WikiPage.workspace_id == job.workspace_id,
                WikiPage.status != "archived",
                WikiPage.current_revision_id.is_not(None),
            )
            .order_by(WikiPage.page_type, WikiPage.slug, WikiPage.id)
        ).all()
    )
    revisions = {
        revision.id: revision
        for revision in db.scalars(
            select(WikiRevision).where(
                WikiRevision.id.in_(
                    [page.current_revision_id for page in pages if page.current_revision_id]
                )
            )
        ).all()
    }
    aliases_by_page: dict[uuid.UUID, list[str]] = {}
    for alias in db.scalars(
        select(PageAlias)
        .where(PageAlias.workspace_id == job.workspace_id)
        .order_by(PageAlias.alias_normalized)
    ).all():
        aliases_by_page.setdefault(alias.page_id, []).append(alias.alias_display)
    links = list(
        db.scalars(
            select(WikiLink)
            .where(WikiLink.workspace_id == job.workspace_id)
            .order_by(WikiLink.source_page_id, WikiLink.target_slug)
        ).all()
    )
    citations = list(
        db.scalars(
            select(Citation)
            .where(Citation.workspace_id == job.workspace_id)
            .order_by(Citation.revision_id, Citation.source_id, Citation.locator)
        ).all()
    )
    slug_by_name: dict[str, str] = {}
    for page in pages:
        slug_by_name[page.slug.casefold()] = page.slug
        slug_by_name[page.title.casefold()] = page.slug
        for alias in aliases_by_page.get(page.id, []):
            slug_by_name[alias.casefold()] = page.slug

    files: dict[str, bytes] = {}
    citations_by_revision: dict[uuid.UUID, list[Citation]] = {}
    for citation in citations:
        citations_by_revision.setdefault(citation.revision_id, []).append(citation)
    for page in pages:
        revision = revisions[page.current_revision_id]
        page_citations = citations_by_revision.get(revision.id, [])
        document = {
            "id": str(page.id),
            "title": page.title,
            "type": page.page_type,
            "aliases": aliases_by_page.get(page.id, []),
            "status": page.status,
            "revision": revision.revision_no,
            "schema_version": revision.schema_version,
            "source_ids": sorted({str(item.source_id) for item in page_citations}),
        }
        markdown = _rewrite_wikilinks(revision.markdown, slug_by_name)
        path = f"{PAGE_DIRECTORIES[page.page_type]}/{page.slug}.md"
        files[path] = (_frontmatter(document) + markdown.rstrip() + "\n").encode()

    index_lines = [f"# {workspace.name}", "", "## Wiki", ""]
    for page in pages:
        directory = PAGE_DIRECTORIES[page.page_type]
        index_lines.append(f"- [[{directory}/{page.slug}|{page.title}]]")
    files["index.md"] = ("\n".join(index_lines).rstrip() + "\n").encode()

    activities = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.workspace_id == job.workspace_id)
            .order_by(AuditLog.created_at, AuditLog.id)
        ).all()
    )
    log_lines = ["# Activity", ""]
    log_lines.extend(
        f"- {item.created_at.isoformat()} · {item.action} · {item.resource_type}"
        for item in activities
    )
    files["log.md"] = ("\n".join(log_lines).rstrip() + "\n").encode()

    if (job.progress_json or {}).get("include_raw", True):
        sources = list(
            db.scalars(
                select(Source)
                .where(
                    Source.workspace_id == job.workspace_id,
                    Source.status == "active",
                )
                .order_by(Source.created_at, Source.id)
            ).all()
        )
        storage = get_storage()
        for source in sources:
            if storage.exists(source.storage_key):
                with storage.open(source.storage_key) as handle:
                    files[f"raw/{source.sha256[:12]}-{source.safe_filename}"] = handle.read()

    exported_at = job.created_at.astimezone(timezone.utc).isoformat()
    manifest = {
        "workspace": {
            "id": str(workspace.id),
            "name": workspace.name,
            "schema_version": workspace.schema_version,
        },
        "export_id": str(job.id),
        "exported_at": exported_at,
        "files": {
            path: hashlib.sha256(content).hexdigest()
            for path, content in sorted(files.items())
        },
        "links": [
            {
                "source_page_id": str(link.source_page_id),
                "target_slug": link.target_slug,
                "type": link.link_type,
            }
            for link in links
        ],
    }
    files["export-manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, content in sorted(files.items()):
            info = zipfile.ZipInfo(path, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    return output.getvalue()


def run_export_job(job_id: str | uuid.UUID) -> None:
    try:
        resolved_job_id = uuid.UUID(str(job_id))
    except (TypeError, ValueError):
        LOGGER.error("export_rejected reason=invalid_job_id")
        return
    try:
        with SessionLocal() as db:
            claimed = claim_export_job(db, resolved_job_id)
            workspace_id = claimed.workspace_id
        with SessionLocal() as db:
            update_job_progress(
                db,
                resolved_job_id,
                percent=20,
                stage="building_vault",
                current=0,
                total=1,
            )
        with SessionLocal() as db:
            job = db.get(Job, resolved_job_id)
            if job is None:
                raise LookupError("job")
            payload = _zip_bytes(db, job)
            workspace_slug = db.scalar(
                select(Workspace.slug).where(Workspace.id == workspace_id)
            )
        with SessionLocal() as db:
            if cancellation_requested(db, resolved_job_id):
                fail_job(
                    db,
                    resolved_job_id,
                    error_code="CANCELLED",
                    safe_message="The export job was cancelled.",
                    retryable=False,
                )
                return
        sha256 = hashlib.sha256(payload).hexdigest()
        filename = f"{workspace_slug or 'workspace'}-vault.zip"
        storage_key = f"exports/{workspace_id}/{resolved_job_id}.zip"
        stored = get_storage().put_immutable(
            io.BytesIO(payload),
            storage_key=storage_key,
            expected_sha256=sha256,
        )
        with SessionLocal.begin() as db:
            job = db.scalar(
                select(Job).where(Job.id == resolved_job_id).with_for_update()
            )
            if job is None or job.status != "running":
                raise InvalidJobTransition("Export is no longer running.")
            job.status = "completed"
            job.progress = 100
            job.progress_json = {
                "stage": "completed",
                "current": 1,
                "total": 1,
                "filename": filename,
                "storage_key": stored.storage_key,
                "sha256": stored.sha256,
                "size_bytes": stored.size_bytes,
            }
            job.heartbeat_at = datetime.now(timezone.utc)
            job.finished_at = datetime.now(timezone.utc)
            db.add(
                AuditLog(
                    actor_id=DEFAULT_USER_ID,
                    workspace_id=job.workspace_id,
                    action="export.completed",
                    resource_type="export",
                    resource_id=job.id,
                    metadata_json={
                        "sha256": stored.sha256,
                        "size_bytes": stored.size_bytes,
                    },
                )
            )
    except InvalidJobTransition:
        return
    except Exception as exc:
        LOGGER.error(
            "export_failed job_id=%s exception_type=%s",
            resolved_job_id,
            type(exc).__name__,
        )
        with SessionLocal() as db:
            try:
                job = fail_job(
                    db,
                    resolved_job_id,
                    error_code=(
                        "STORAGE_UNAVAILABLE"
                        if isinstance(exc, StorageError)
                        else "EXPORT_FAILED"
                    ),
                    safe_message="The Vault export could not be created.",
                    retryable=isinstance(exc, StorageError),
                )
                if job.status == "retrying":
                    enqueue_export_job(db, job)
            except InvalidJobTransition:
                return
