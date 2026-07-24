from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class WikiLinkInput(BaseModel):
    target_slug: str = Field(min_length=1, max_length=200)
    type: Literal["wikilink", "citation", "derived_from", "related", "contradicts"]
    evidence_source_id: uuid.UUID | None = None
    weight: float = Field(default=1.0, gt=0)


class CitationInput(BaseModel):
    source_id: uuid.UUID
    locator: str = Field(min_length=1, max_length=500)
    excerpt: str | None = Field(default=None, max_length=4000)


class WikiPageOperation(BaseModel):
    action: Literal["create_page", "update_page", "mark_page_for_review", "create_open_question"]
    page_id: uuid.UUID | None = None
    expected_revision_no: int | None = Field(default=None, ge=0)
    title: str = Field(min_length=1, max_length=300)
    slug: str = Field(min_length=1, max_length=200)
    page_type: Literal["topic", "entity", "source", "analysis", "question"]
    aliases: list[str] = Field(default_factory=list, max_length=100)
    markdown: str = Field(min_length=1)
    summary: str | None = Field(default=None, max_length=2000)
    change_summary: str | None = Field(default=None, max_length=2000)
    links: list[WikiLinkInput] = Field(default_factory=list, max_length=500)
    citations: list[CitationInput] = Field(default_factory=list, max_length=500)


class WikiOperationBatch(BaseModel):
    schema_version: int = Field(gt=0)
    source_id: uuid.UUID
    operations: list[WikiPageOperation] = Field(min_length=1, max_length=100)


class CitationRead(BaseModel):
    source_id: uuid.UUID
    locator: str
    excerpt: str | None


class WikiLinkRead(BaseModel):
    target_page_id: uuid.UUID | None
    target_slug: str
    type: str
    weight: float


class WikiPageSummary(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    page_type: str
    summary: str | None
    status: str
    revision_no: int | None
    updated_at: datetime


class WikiPageRead(WikiPageSummary):
    markdown: str
    frontmatter: dict
    aliases: list[str]
    links: list[WikiLinkRead]
    citations: list[CitationRead]


class WikiPageList(BaseModel):
    items: list[WikiPageSummary]
    next_cursor: str | None = None


class TreeSource(BaseModel):
    id: uuid.UUID
    filename: str
    status: str


class WorkspaceTree(BaseModel):
    sources: list[TreeSource]
    wiki: list[WikiPageSummary]


class ActivityItem(BaseModel):
    id: uuid.UUID
    action: str
    resource_type: str
    resource_id: uuid.UUID
    created_at: datetime
    metadata: dict


class ActivityList(BaseModel):
    items: list[ActivityItem]


class GraphNode(BaseModel):
    id: uuid.UUID
    label: str
    slug: str
    type: str
    status: str
    degree: int
    updated_at: datetime


class GraphEdge(BaseModel):
    id: uuid.UUID
    source: uuid.UUID
    target: uuid.UUID | None
    target_slug: str
    type: str
    weight: float


class GraphRead(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
