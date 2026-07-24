from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

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
from ..schemas.wiki import WikiOperationBatch, WikiPageOperation


class WikiCommitError(RuntimeError):
    code = "SCHEMA_VALIDATION_FAILED"


class RevisionConflict(WikiCommitError):
    code = "REVISION_CONFLICT"


class AliasConflict(WikiCommitError):
    code = "ALIAS_CONFLICT"


@dataclass(frozen=True)
class WikiCommitResult:
    affected_page_ids: tuple[uuid.UUID, ...]
    revision_ids: tuple[uuid.UUID, ...]


def normalize_alias(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        raise AliasConflict("Alias must not be empty.")
    return normalized


def normalize_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    normalized = re.sub(r"[^\w]+", "-", normalized, flags=re.UNICODE).strip("-")
    if not normalized:
        raise WikiCommitError("Page slug must not be empty.")
    return normalized[:200]


def _active_source(db: Session, workspace_id: uuid.UUID, source_id: uuid.UUID) -> Source:
    source = db.scalar(
        select(Source).where(
            Source.workspace_id == workspace_id,
            Source.id == source_id,
            Source.status == "active",
        )
    )
    if source is None:
        raise WikiCommitError("A citation references an unavailable source.")
    return source


def _assert_aliases_available(
    db: Session,
    workspace_id: uuid.UUID,
    page_id: uuid.UUID,
    operation: WikiPageOperation,
) -> list[tuple[str, str]]:
    requested = [(normalize_alias(alias), alias.strip()) for alias in operation.aliases]
    normalized_values = [value for value, _ in requested]
    if len(normalized_values) != len(set(normalized_values)):
        raise AliasConflict("The operation contains duplicate aliases.")

    candidate_names = set(normalized_values)
    candidate_names.add(normalize_alias(operation.title))
    candidate_names.add(normalize_alias(operation.slug))
    existing_aliases = db.scalars(
        select(PageAlias).where(
            PageAlias.workspace_id == workspace_id,
            PageAlias.alias_normalized.in_(candidate_names),
            PageAlias.page_id != page_id,
        )
    ).first()
    if existing_aliases is not None:
        raise AliasConflict("An alias belongs to another page.")

    for other in db.scalars(
        select(WikiPage).where(
            WikiPage.workspace_id == workspace_id,
            WikiPage.id != page_id,
            WikiPage.status != "archived",
        )
    ):
        if (
            normalize_alias(other.title) in candidate_names
            or normalize_alias(other.slug) in candidate_names
        ):
            raise AliasConflict("The title, slug, or alias conflicts with another page.")
    return requested


def _page_for_operation(
    db: Session,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    operation: WikiPageOperation,
) -> tuple[WikiPage, int]:
    if operation.action in {"create_page", "create_open_question"}:
        if operation.page_id is not None:
            existing = db.scalar(
                select(WikiPage).where(
                    WikiPage.workspace_id == workspace_id,
                    WikiPage.id == operation.page_id,
                )
            )
            if existing is not None:
                raise AliasConflict("The requested page ID already exists.")
        resolved_page_type = (
            "question" if operation.action == "create_open_question" else operation.page_type
        )
        page = WikiPage(
            id=operation.page_id or uuid.uuid4(),
            workspace_id=workspace_id,
            slug=normalize_slug(operation.slug),
            title=operation.title.strip(),
            page_type=resolved_page_type,
            primary_source_id=source_id if resolved_page_type == "source" else None,
            summary=operation.summary,
            status="needs_review" if operation.action == "create_open_question" else "active",
        )
        return page, 1

    if operation.page_id is None or operation.expected_revision_no is None:
        raise WikiCommitError("Page ID and expected revision are required for updates.")
    page = db.scalar(
        select(WikiPage)
        .where(WikiPage.workspace_id == workspace_id, WikiPage.id == operation.page_id)
        .with_for_update()
    )
    if page is None:
        raise WikiCommitError("The target page does not exist.")
    current_no = 0
    if page.current_revision_id is not None:
        current_no = db.scalar(
            select(WikiRevision.revision_no).where(
                WikiRevision.workspace_id == workspace_id,
                WikiRevision.id == page.current_revision_id,
            )
        ) or 0
    if current_no != operation.expected_revision_no:
        raise RevisionConflict(
            f"Expected revision {operation.expected_revision_no}, current revision is {current_no}."
        )
    page.slug = normalize_slug(operation.slug)
    page.title = operation.title.strip()
    page.page_type = operation.page_type
    page.primary_source_id = source_id if operation.page_type == "source" else None
    page.summary = operation.summary
    if operation.action == "mark_page_for_review":
        page.status = "needs_review"
    return page, current_no + 1


def apply_wiki_operations(
    db: Session,
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    actor_id: uuid.UUID,
    batch: WikiOperationBatch,
) -> WikiCommitResult:
    affected: list[uuid.UUID] = []
    revisions: list[uuid.UUID] = []
    with db.begin():
        workspace = db.scalar(
            select(Workspace)
            .where(Workspace.id == workspace_id, Workspace.status == "active")
            .with_for_update()
        )
        if workspace is None:
            raise WikiCommitError("Workspace is unavailable.")
        if workspace.schema_version != batch.schema_version:
            raise WikiCommitError("Schema version does not match the Workspace.")
        source = _active_source(db, workspace_id, batch.source_id)
        job = db.scalar(
            select(Job)
            .where(
                Job.id == job_id,
                Job.workspace_id == workspace_id,
                Job.source_id == source.id,
                Job.job_type == "ingest",
            )
            .with_for_update()
        )
        if job is None or job.status not in {"running", "retrying"}:
            raise WikiCommitError("Ingest Job is not in a committable state.")

        prepared: list[
            tuple[WikiPageOperation, WikiPage, WikiRevision, list[tuple[str, str]]]
        ] = []
        for operation in batch.operations:
            page, revision_no = _page_for_operation(
                db, workspace_id, source.id, operation
            )
            aliases = _assert_aliases_available(db, workspace_id, page.id, operation)
            db.add(page)
            db.flush()

            revision = WikiRevision(
                workspace_id=workspace_id,
                page_id=page.id,
                revision_no=revision_no,
                markdown=operation.markdown,
                frontmatter_json={},
                change_summary=operation.change_summary,
                schema_version=batch.schema_version,
                model_name=(job.model_snapshot_json or {}).get("name"),
                model_provider=(job.model_snapshot_json or {}).get("provider"),
                model_profile_id=job.model_profile_id,
                prompt_version=None,
                job_id=job.id,
                created_by=actor_id,
            )
            db.add(revision)
            db.flush()
            page.current_revision_id = revision.id
            db.execute(
                delete(PageAlias).where(
                    PageAlias.workspace_id == workspace_id,
                    PageAlias.page_id == page.id,
                )
            )
            for normalized, display in aliases:
                db.add(
                    PageAlias(
                        workspace_id=workspace_id,
                        page_id=page.id,
                        alias_normalized=normalized,
                        alias_display=display,
                        created_by_revision_id=revision.id,
                    )
                )
            db.add(
                AuditLog(
                    actor_id=actor_id,
                    workspace_id=workspace_id,
                    action="wiki.page_committed",
                    resource_type="wiki_page",
                    resource_id=page.id,
                    metadata_json={
                        "job_id": str(job.id),
                        "revision_id": str(revision.id),
                        "revision_no": revision.revision_no,
                    },
                )
            )
            prepared.append((operation, page, revision, aliases))
            affected.append(page.id)
            revisions.append(revision.id)

        # Resolve links only after every page in the batch exists, so links to a
        # page created later in the same operation batch are not left dangling.
        db.flush()
        for operation, page, revision, _ in prepared:
            db.execute(
                delete(WikiLink).where(
                    WikiLink.workspace_id == workspace_id,
                    WikiLink.source_page_id == page.id,
                )
            )
            for link in operation.links:
                target_slug = normalize_slug(link.target_slug)
                target = db.scalar(
                    select(WikiPage).where(
                        WikiPage.workspace_id == workspace_id,
                        WikiPage.slug == target_slug,
                        WikiPage.status != "archived",
                    )
                )
                if link.evidence_source_id is not None:
                    _active_source(db, workspace_id, link.evidence_source_id)
                if link.type in {"related", "contradicts"} and link.evidence_source_id is None:
                    raise WikiCommitError("Inferred links require source evidence.")
                db.add(
                    WikiLink(
                        workspace_id=workspace_id,
                        source_page_id=page.id,
                        target_page_id=target.id if target else None,
                        target_slug=target_slug,
                        link_type=link.type,
                        evidence_source_id=link.evidence_source_id,
                        evidence_revision_id=revision.id,
                        weight=link.weight,
                    )
                )
            for citation in operation.citations:
                cited_source = _active_source(db, workspace_id, citation.source_id)
                excerpt_hash = (
                    hashlib.sha256(citation.excerpt.encode()).hexdigest()
                    if citation.excerpt
                    else None
                )
                db.add(
                    Citation(
                        workspace_id=workspace_id,
                        revision_id=revision.id,
                        source_id=cited_source.id,
                        locator=citation.locator,
                        excerpt=citation.excerpt,
                        excerpt_hash=excerpt_hash,
                    )
                )

        job.status = "completed"
        job.progress = 100
        job.progress_json = {
            "stage": "completed",
            "current": len(affected),
            "total": len(affected),
            "affected_page_ids": [str(page_id) for page_id in affected],
        }
        job.finished_at = db.scalar(select(func.now()))

    return WikiCommitResult(tuple(affected), tuple(revisions))
