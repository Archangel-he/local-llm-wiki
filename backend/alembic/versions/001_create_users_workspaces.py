"""Create users, workspaces, memberships tables.

Revision ID: 001
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(320), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("password_hash", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("schema_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "memberships",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("memberships")
    op.drop_table("workspaces")
    op.drop_table("users")
