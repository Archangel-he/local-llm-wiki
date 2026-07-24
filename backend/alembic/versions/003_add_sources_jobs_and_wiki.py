"""Add immutable sources, jobs, audit log, and versioned wiki tables.

Revision ID: 003
Revises: 002
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | None = None
depends_on: str | None = None


def _id() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False)


def _workspace_id() -> sa.Column:
    return sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _updated_at() -> sa.Column:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "sources",
        _id(),
        _workspace_id(),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("safe_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint("size_bytes >= 0", name="ck_sources_size_bytes"),
        sa.CheckConstraint(
            "status IN ('active', 'archived', 'rejected')", name="ck_sources_status"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_sources_workspace_id"),
        sa.UniqueConstraint("workspace_id", "sha256", name="uq_sources_workspace_sha256"),
    )

    op.create_table(
        "jobs",
        _id(),
        _workspace_id(),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("job_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="queued", nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "progress_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message_safe", sa.Text(), nullable=True),
        sa.Column("rq_job_id", sa.String(length=100), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint("attempt >= 0 AND attempt <= max_attempts", name="ck_jobs_attempt"),
        sa.CheckConstraint("max_attempts > 0", name="ck_jobs_max_attempts"),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_jobs_progress"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'retrying', 'completed', 'failed', "
            "'cancel_requested', 'cancelled')",
            name="ck_jobs_status",
        ),
        sa.CheckConstraint(
            "job_type IN ('ingest', 'query', 'lint', 'wiki_update', "
            "'schema_migration', 'export')",
            name="ck_jobs_type",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["model_profile_id"], ["model_profiles.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rq_job_id", name="uq_jobs_rq_job_id"),
    )
    op.create_index(
        "ix_jobs_workspace_status_created",
        "jobs",
        ["workspace_id", "status", "created_at"],
    )
    op.create_index(
        "uq_jobs_active_idempotency",
        "jobs",
        ["workspace_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('queued', 'running', 'retrying', 'completed', 'cancel_requested')"
        ),
    )

    op.create_table(
        "audit_logs",
        _id(),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        _workspace_id(),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        _created_at(),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_logs_workspace_created", "audit_logs", ["workspace_id", "created_at"]
    )

    op.create_table(
        "wiki_pages",
        _id(),
        _workspace_id(),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("page_type", sa.String(length=30), nullable=False),
        sa.Column("primary_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("current_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "(page_type = 'source' AND primary_source_id IS NOT NULL) "
            "OR (page_type <> 'source' AND primary_source_id IS NULL)",
            name="ck_wiki_pages_primary_source",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'needs_review', 'archived')",
            name="ck_wiki_pages_status",
        ),
        sa.CheckConstraint(
            "page_type IN ('topic', 'entity', 'source', 'analysis', 'question')",
            name="ck_wiki_pages_type",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "primary_source_id"],
            ["sources.workspace_id", "sources.id"],
            name="fk_wiki_pages_workspace_primary_source",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_wiki_pages_workspace_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "primary_source_id",
            name="uq_wiki_pages_workspace_primary_source",
        ),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_wiki_pages_workspace_slug"),
    )

    op.create_table(
        "wiki_revisions",
        _id(),
        _workspace_id(),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column(
            "frontmatter_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=300), nullable=True),
        sa.Column("model_provider", sa.String(length=40), nullable=True),
        sa.Column("model_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("prompt_version", sa.String(length=100), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        _created_at(),
        sa.CheckConstraint("revision_no > 0", name="ck_wiki_revisions_no"),
        sa.CheckConstraint("schema_version > 0", name="ck_wiki_revisions_schema_version"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["model_profile_id"], ["model_profiles.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "page_id"],
            ["wiki_pages.workspace_id", "wiki_pages.id"],
            name="fk_wiki_revisions_workspace_page",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_id", "revision_no", name="uq_wiki_revisions_page_no"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_wiki_revisions_workspace_id"),
    )
    op.create_foreign_key(
        "fk_wiki_pages_workspace_current_revision",
        "wiki_pages",
        "wiki_revisions",
        ["current_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "page_aliases",
        _id(),
        _workspace_id(),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alias_normalized", sa.String(length=300), nullable=False),
        sa.Column("alias_display", sa.String(length=300), nullable=False),
        sa.Column("language", sa.String(length=35), nullable=True),
        sa.Column("created_by_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "created_by_revision_id"],
            ["wiki_revisions.workspace_id", "wiki_revisions.id"],
            name="fk_page_aliases_workspace_revision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "page_id"],
            ["wiki_pages.workspace_id", "wiki_pages.id"],
            name="fk_page_aliases_workspace_page",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "alias_normalized", name="uq_page_aliases_workspace_normalized"
        ),
    )

    op.create_table(
        "wiki_links",
        _id(),
        _workspace_id(),
        sa.Column("source_page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_slug", sa.String(length=200), nullable=False),
        sa.Column("link_type", sa.String(length=30), nullable=False),
        sa.Column("evidence_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weight", sa.Float(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "link_type NOT IN ('related', 'contradicts') OR evidence_source_id IS NOT NULL",
            name="ck_wiki_links_inferred_evidence",
        ),
        sa.CheckConstraint(
            "link_type IN ('wikilink', 'citation', 'derived_from', 'related', 'contradicts')",
            name="ck_wiki_links_type",
        ),
        sa.CheckConstraint("weight > 0", name="ck_wiki_links_weight"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "evidence_revision_id"],
            ["wiki_revisions.workspace_id", "wiki_revisions.id"],
            name="fk_wiki_links_workspace_evidence_revision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "evidence_source_id"],
            ["sources.workspace_id", "sources.id"],
            name="fk_wiki_links_workspace_evidence_source",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_page_id"],
            ["wiki_pages.workspace_id", "wiki_pages.id"],
            name="fk_wiki_links_workspace_source_page",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_page_id"],
            ["wiki_pages.id"],
            name="fk_wiki_links_workspace_target_page",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wiki_links_workspace_source", "wiki_links", ["workspace_id", "source_page_id"]
    )
    op.create_index(
        "ix_wiki_links_workspace_target", "wiki_links", ["workspace_id", "target_page_id"]
    )

    op.create_table(
        "citations",
        _id(),
        _workspace_id(),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("locator", sa.String(length=500), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("excerpt_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "revision_id"],
            ["wiki_revisions.workspace_id", "wiki_revisions.id"],
            name="fk_citations_workspace_revision",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "source_id"],
            ["sources.workspace_id", "sources.id"],
            name="fk_citations_workspace_source",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_citations_workspace_source", "citations", ["workspace_id", "source_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_citations_workspace_source", table_name="citations")
    op.drop_table("citations")
    op.drop_index("ix_wiki_links_workspace_target", table_name="wiki_links")
    op.drop_index("ix_wiki_links_workspace_source", table_name="wiki_links")
    op.drop_table("wiki_links")
    op.drop_table("page_aliases")
    op.drop_constraint(
        "fk_wiki_pages_workspace_current_revision", "wiki_pages", type_="foreignkey"
    )
    op.drop_table("wiki_revisions")
    op.drop_table("wiki_pages")
    op.drop_index("ix_audit_logs_workspace_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("uq_jobs_active_idempotency", table_name="jobs")
    op.drop_index("ix_jobs_workspace_status_created", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("sources")
