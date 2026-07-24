"""Load an authorized, credential-safe ingest execution context."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.llm.types import RuntimeModelProfile
from app.models import Job, ModelProfile, PageAlias, Source, WikiPage, WikiRevision, Workspace
from app.services.model_profiles import runtime_profile


class IngestContextError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ExistingPageCandidate:
    id: uuid.UUID
    title: str
    slug: str
    page_type: str
    aliases: tuple[str, ...]
    revision_no: int
    summary: str | None
    primary_source_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class IngestContext:
    job_id: uuid.UUID
    workspace_id: uuid.UUID
    source_id: uuid.UUID
    source_filename: str
    source_mime_type: str
    source_storage_key: str
    schema_version: int
    prompt_version: str
    runtime_profile: RuntimeModelProfile
    existing_pages: tuple[ExistingPageCandidate, ...]


@dataclass(frozen=True, slots=True)
class SourceInput:
    storage_key: str


def load_source_input(db: Session, job_id: uuid.UUID) -> SourceInput:
    """Load only the storage reference required by the parsing stage."""

    row = db.execute(
        select(Job, Source)
        .join(
            Source,
            (Source.id == Job.source_id)
            & (Source.workspace_id == Job.workspace_id),
        )
        .where(
            Job.id == job_id,
            Job.job_type == "ingest",
            Job.status.in_({"running", "retrying"}),
            Source.status == "active",
        )
    ).one_or_none()
    if row is None:
        raise IngestContextError(
            "INGEST_RESOURCE_UNAVAILABLE",
            "The source or ingest job is unavailable.",
        )
    return SourceInput(storage_key=row.Source.storage_key)


def build_ingest_context(
    db: Session,
    job_id: uuid.UUID,
    *,
    max_existing_pages: int | None = None,
) -> IngestContext:
    job = db.scalar(select(Job).where(Job.id == job_id))
    if job is None or job.job_type != "ingest":
        raise IngestContextError("JOB_NOT_FOUND", "The ingest job does not exist.")
    if job.status not in {"running", "retrying"}:
        raise IngestContextError("JOB_NOT_RUNNABLE", "The ingest job is not running.")
    source = db.scalar(
        select(Source).where(
            Source.id == job.source_id,
            Source.workspace_id == job.workspace_id,
            Source.status == "active",
        )
    )
    workspace = db.scalar(
        select(Workspace).where(
            Workspace.id == job.workspace_id,
            Workspace.status == "active",
        )
    )
    profile = db.scalar(
        select(ModelProfile).where(
            ModelProfile.id == job.model_profile_id,
            ModelProfile.workspace_id == job.workspace_id,
            ModelProfile.scope == "workspace",
        )
    )
    if source is None or workspace is None:
        raise IngestContextError(
            "INGEST_RESOURCE_UNAVAILABLE",
            "The source or workspace is unavailable.",
        )
    if profile is None or profile.status != "active":
        raise IngestContextError(
            "MODEL_PROFILE_INVALID",
            "The job model profile is no longer active.",
        )

    limit = max_existing_pages or settings.ingest_max_existing_pages
    rows = list(
        db.execute(
            select(WikiPage, WikiRevision.revision_no)
            .outerjoin(
                WikiRevision,
                (WikiRevision.workspace_id == WikiPage.workspace_id)
                & (WikiRevision.id == WikiPage.current_revision_id),
            )
            .where(
                WikiPage.workspace_id == workspace.id,
                WikiPage.status != "archived",
            )
            .order_by(WikiPage.updated_at.desc(), WikiPage.id)
            .limit(limit)
        ).all()
    )
    page_ids = [page.id for page, _ in rows]
    alias_map: dict[uuid.UUID, list[str]] = {page_id: [] for page_id in page_ids}
    if page_ids:
        for alias in db.scalars(
            select(PageAlias)
            .where(PageAlias.workspace_id == workspace.id, PageAlias.page_id.in_(page_ids))
            .order_by(PageAlias.alias_normalized)
        ):
            alias_map[alias.page_id].append(alias.alias_display)
    candidates = tuple(
        ExistingPageCandidate(
            id=page.id,
            title=page.title,
            slug=page.slug,
            page_type=page.page_type,
            aliases=tuple(alias_map[page.id]),
            revision_no=revision_no or 0,
            summary=page.summary,
            primary_source_id=page.primary_source_id,
        )
        for page, revision_no in rows
    )
    return IngestContext(
        job_id=job.id,
        workspace_id=workspace.id,
        source_id=source.id,
        source_filename=source.original_filename,
        source_mime_type=source.mime_type,
        source_storage_key=source.storage_key,
        schema_version=workspace.schema_version,
        prompt_version=settings.ingest_prompt_version,
        runtime_profile=runtime_profile(profile),
        existing_pages=candidates,
    )
