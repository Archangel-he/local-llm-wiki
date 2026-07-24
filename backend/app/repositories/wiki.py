from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog, Citation, PageAlias, Source, WikiLink, WikiPage, WikiRevision


def list_wiki_pages(
    db: Session, workspace_id: uuid.UUID
) -> list[tuple[WikiPage, int | None]]:
    return list(
        db.execute(
            select(WikiPage, WikiRevision.revision_no)
            .outerjoin(
                WikiRevision,
                (WikiRevision.workspace_id == WikiPage.workspace_id)
                & (WikiRevision.id == WikiPage.current_revision_id),
            )
            .where(WikiPage.workspace_id == workspace_id, WikiPage.status != "archived")
            .order_by(WikiPage.page_type, WikiPage.title, WikiPage.id)
        ).all()
    )


def get_wiki_page(
    db: Session, workspace_id: uuid.UUID, page_id: uuid.UUID
) -> tuple[WikiPage, WikiRevision, list[PageAlias], list[WikiLink], list[Citation]] | None:
    page = db.scalar(
        select(WikiPage).where(
            WikiPage.workspace_id == workspace_id,
            WikiPage.id == page_id,
            WikiPage.status != "archived",
        )
    )
    if page is None or page.current_revision_id is None:
        return None
    revision = db.scalar(
        select(WikiRevision).where(
            WikiRevision.workspace_id == workspace_id,
            WikiRevision.id == page.current_revision_id,
        )
    )
    if revision is None:
        return None
    aliases = list(
        db.scalars(
            select(PageAlias)
            .where(PageAlias.workspace_id == workspace_id, PageAlias.page_id == page.id)
            .order_by(PageAlias.alias_normalized)
        ).all()
    )
    links = list(
        db.scalars(
            select(WikiLink)
            .where(WikiLink.workspace_id == workspace_id, WikiLink.source_page_id == page.id)
            .order_by(WikiLink.link_type, WikiLink.target_slug)
        ).all()
    )
    citations = list(
        db.scalars(
            select(Citation)
            .where(
                Citation.workspace_id == workspace_id,
                Citation.revision_id == revision.id,
            )
            .order_by(Citation.source_id, Citation.locator)
        ).all()
    )
    return page, revision, aliases, links, citations


def list_sources(db: Session, workspace_id: uuid.UUID) -> list[Source]:
    return list(
        db.scalars(
            select(Source)
            .where(Source.workspace_id == workspace_id)
            .order_by(Source.created_at.desc(), Source.id.desc())
        ).all()
    )


def list_activity(db: Session, workspace_id: uuid.UUID, limit: int = 100) -> list[AuditLog]:
    return list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.workspace_id == workspace_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
        ).all()
    )


def list_graph_links(db: Session, workspace_id: uuid.UUID) -> list[WikiLink]:
    return list(
        db.scalars(
            select(WikiLink)
            .where(WikiLink.workspace_id == workspace_id)
            .order_by(WikiLink.source_page_id, WikiLink.id)
        ).all()
    )
