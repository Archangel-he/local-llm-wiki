from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class Source(TimestampMixin, Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("workspace_id", "sha256", name="uq_sources_workspace_sha256"),
        UniqueConstraint("workspace_id", "id", name="uq_sources_workspace_id"),
        CheckConstraint("size_bytes >= 0", name="ck_sources_size_bytes"),
        CheckConstraint(
            "status IN ('active', 'archived', 'rejected')",
            name="ck_sources_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    safe_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('ingest', 'query', 'lint', 'wiki_update', "
            "'schema_migration', 'export')",
            name="ck_jobs_type",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'retrying', 'completed', 'failed', "
            "'cancel_requested', 'cancelled')",
            name="ck_jobs_status",
        ),
        CheckConstraint("attempt >= 0 AND attempt <= max_attempts", name="ck_jobs_attempt"),
        CheckConstraint("max_attempts > 0", name="ck_jobs_max_attempts"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_jobs_progress"),
        Index(
            "uq_jobs_active_idempotency",
            "workspace_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text(
                "status IN ('queued', 'running', 'retrying', 'completed', 'cancel_requested')"
            ),
        ),
        Index("ix_jobs_workspace_status_created", "workspace_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=True
    )
    model_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="SET NULL"), nullable=True
    )
    model_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    job_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="queued", server_default="queued"
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    progress_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    rq_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WikiPage(TimestampMixin, Base):
    __tablename__ = "wiki_pages"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_wiki_pages_workspace_slug"),
        UniqueConstraint("workspace_id", "id", name="uq_wiki_pages_workspace_id"),
        UniqueConstraint(
            "workspace_id",
            "primary_source_id",
            name="uq_wiki_pages_workspace_primary_source",
        ),
        CheckConstraint(
            "page_type IN ('topic', 'entity', 'source', 'analysis', 'question')",
            name="ck_wiki_pages_type",
        ),
        CheckConstraint(
            "status IN ('active', 'needs_review', 'archived')",
            name="ck_wiki_pages_status",
        ),
        CheckConstraint(
            "(page_type = 'source' AND primary_source_id IS NOT NULL) "
            "OR (page_type <> 'source' AND primary_source_id IS NULL)",
            name="ck_wiki_pages_primary_source",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "primary_source_id"],
            ["sources.workspace_id", "sources.id"],
            name="fk_wiki_pages_workspace_primary_source",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["current_revision_id"],
            ["wiki_revisions.id"],
            name="fk_wiki_pages_workspace_current_revision",
            ondelete="SET NULL",
            use_alter=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    page_type: Mapped[str] = mapped_column(String(30), nullable=False)
    primary_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class WikiRevision(Base):
    __tablename__ = "wiki_revisions"
    __table_args__ = (
        UniqueConstraint("page_id", "revision_no", name="uq_wiki_revisions_page_no"),
        UniqueConstraint("workspace_id", "id", name="uq_wiki_revisions_workspace_id"),
        CheckConstraint("revision_no > 0", name="ck_wiki_revisions_no"),
        CheckConstraint("schema_version > 0", name="ck_wiki_revisions_schema_version"),
        ForeignKeyConstraint(
            ["workspace_id", "page_id"],
            ["wiki_pages.workspace_id", "wiki_pages.id"],
            name="fk_wiki_revisions_workspace_page",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    frontmatter_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_profiles.id", ondelete="SET NULL"), nullable=True
    )
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PageAlias(Base):
    __tablename__ = "page_aliases"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "alias_normalized", name="uq_page_aliases_workspace_normalized"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "page_id"],
            ["wiki_pages.workspace_id", "wiki_pages.id"],
            name="fk_page_aliases_workspace_page",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "created_by_revision_id"],
            ["wiki_revisions.workspace_id", "wiki_revisions.id"],
            name="fk_page_aliases_workspace_revision",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    alias_normalized: Mapped[str] = mapped_column(String(300), nullable=False)
    alias_display: Mapped[str] = mapped_column(String(300), nullable=False)
    language: Mapped[str | None] = mapped_column(String(35), nullable=True)
    created_by_revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class WikiLink(Base):
    __tablename__ = "wiki_links"
    __table_args__ = (
        CheckConstraint(
            "link_type IN ('wikilink', 'citation', 'derived_from', 'related', 'contradicts')",
            name="ck_wiki_links_type",
        ),
        CheckConstraint("weight > 0", name="ck_wiki_links_weight"),
        CheckConstraint(
            "link_type NOT IN ('related', 'contradicts') OR evidence_source_id IS NOT NULL",
            name="ck_wiki_links_inferred_evidence",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "source_page_id"],
            ["wiki_pages.workspace_id", "wiki_pages.id"],
            name="fk_wiki_links_workspace_source_page",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_page_id"],
            ["wiki_pages.id"],
            name="fk_wiki_links_workspace_target_page",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "evidence_source_id"],
            ["sources.workspace_id", "sources.id"],
            name="fk_wiki_links_workspace_evidence_source",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "evidence_revision_id"],
            ["wiki_revisions.workspace_id", "wiki_revisions.id"],
            name="fk_wiki_links_workspace_evidence_revision",
            ondelete="CASCADE",
        ),
        Index("ix_wiki_links_workspace_source", "workspace_id", "source_page_id"),
        Index("ix_wiki_links_workspace_target", "workspace_id", "target_page_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_page_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_page_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    target_slug: Mapped[str] = mapped_column(String(200), nullable=False)
    link_type: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    evidence_revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1")


class Citation(Base):
    __tablename__ = "citations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "revision_id"],
            ["wiki_revisions.workspace_id", "wiki_revisions.id"],
            name="fk_citations_workspace_revision",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "source_id"],
            ["sources.workspace_id", "sources.id"],
            name="fk_citations_workspace_source",
            ondelete="RESTRICT",
        ),
        Index("ix_citations_workspace_source", "workspace_id", "source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    locator: Mapped[str] = mapped_column(String(500), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    excerpt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
