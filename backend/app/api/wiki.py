from __future__ import annotations

import uuid
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.errors import ApiError
from ..database import get_db
from ..repositories.wiki import (
    get_wiki_page,
    list_activity,
    list_graph_links,
    list_sources,
    list_wiki_pages,
)
from ..schemas.wiki import (
    ActivityItem,
    ActivityList,
    CitationRead,
    GraphEdge,
    GraphNode,
    GraphRead,
    TreeSource,
    WikiLinkRead,
    WikiPageList,
    WikiPageRead,
    WikiPageSummary,
    WorkspaceTree,
)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["wiki"])


def _summary(item) -> WikiPageSummary:
    page, revision_no = item
    return WikiPageSummary(
        id=page.id,
        slug=page.slug,
        title=page.title,
        page_type=page.page_type,
        summary=page.summary,
        status=page.status,
        revision_no=revision_no,
        updated_at=page.updated_at,
    )


@router.get("/tree", response_model=WorkspaceTree)
def tree(workspace_id: uuid.UUID, db: Session = Depends(get_db)) -> WorkspaceTree:
    return WorkspaceTree(
        sources=[
            TreeSource(id=item.id, filename=item.original_filename, status=item.status)
            for item in list_sources(db, workspace_id)
        ],
        wiki=[_summary(item) for item in list_wiki_pages(db, workspace_id)],
    )


@router.get("/wiki", response_model=WikiPageList)
def wiki_pages(workspace_id: uuid.UUID, db: Session = Depends(get_db)) -> WikiPageList:
    return WikiPageList(items=[_summary(item) for item in list_wiki_pages(db, workspace_id)])


@router.get("/wiki/{page_id}", response_model=WikiPageRead)
def wiki_page(
    workspace_id: uuid.UUID,
    page_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> WikiPageRead:
    result = get_wiki_page(db, workspace_id, page_id)
    if result is None:
        raise ApiError(404, "NOT_FOUND", "Wiki page not found.")
    page, revision, aliases, links, citations = result
    return WikiPageRead(
        id=page.id,
        slug=page.slug,
        title=page.title,
        page_type=page.page_type,
        summary=page.summary,
        status=page.status,
        revision_no=revision.revision_no,
        updated_at=page.updated_at,
        markdown=revision.markdown,
        frontmatter=revision.frontmatter_json,
        aliases=[alias.alias_display for alias in aliases],
        links=[
            WikiLinkRead(
                target_page_id=link.target_page_id,
                target_slug=link.target_slug,
                type=link.link_type,
                weight=link.weight,
            )
            for link in links
        ],
        citations=[
            CitationRead(
                source_id=citation.source_id,
                locator=citation.locator,
                excerpt=citation.excerpt,
            )
            for citation in citations
        ],
    )


@router.get("/wiki-system/index", response_model=WikiPageList)
def wiki_index(workspace_id: uuid.UUID, db: Session = Depends(get_db)) -> WikiPageList:
    return WikiPageList(items=[_summary(item) for item in list_wiki_pages(db, workspace_id)])


@router.get("/wiki-system/activity", response_model=ActivityList)
def activity(workspace_id: uuid.UUID, db: Session = Depends(get_db)) -> ActivityList:
    return ActivityList(
        items=[
            ActivityItem(
                id=item.id,
                action=item.action,
                resource_type=item.resource_type,
                resource_id=item.resource_id,
                created_at=item.created_at,
                metadata=item.metadata_json,
            )
            for item in list_activity(db, workspace_id)
        ]
    )


@router.get("/graph", response_model=GraphRead)
def graph(workspace_id: uuid.UUID, db: Session = Depends(get_db)) -> GraphRead:
    pages = list_wiki_pages(db, workspace_id)
    links = list_graph_links(db, workspace_id)
    degree: Counter[uuid.UUID] = Counter()
    for link in links:
        degree[link.source_page_id] += 1
        if link.target_page_id is not None:
            degree[link.target_page_id] += 1
    return GraphRead(
        nodes=[
            GraphNode(
                id=page.id,
                label=page.title,
                slug=page.slug,
                type=page.page_type,
                status=page.status,
                degree=degree[page.id],
                updated_at=page.updated_at,
            )
            for page, _ in pages
        ],
        edges=[
            GraphEdge(
                id=link.id,
                source=link.source_page_id,
                target=link.target_page_id,
                target_slug=link.target_slug,
                type=link.link_type,
                weight=link.weight,
            )
            for link in links
        ],
    )
