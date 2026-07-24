"""Add model profiles, relational constraints, and mutable timestamps.

Revision ID: 002
Revises: 001
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_foreign_key(
        "fk_workspaces_owner_id_users",
        "workspaces",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint("uq_workspaces_owner_slug", "workspaces", ["owner_id", "slug"])
    op.create_check_constraint("ck_users_status", "users", "status IN ('active', 'disabled')")
    op.create_check_constraint(
        "ck_workspaces_status", "workspaces", "status IN ('active', 'archived')"
    )
    op.create_check_constraint("ck_workspaces_schema_version", "workspaces", "schema_version > 0")
    op.create_foreign_key(
        "fk_memberships_workspace_id_workspaces",
        "memberships",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_memberships_user_id_users",
        "memberships",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_memberships_role",
        "memberships",
        "role IN ('owner', 'editor', 'viewer')",
    )

    op.create_table(
        "model_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("profile_key", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=300), nullable=True),
        sa.Column("credential_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("credential_key_version", sa.Integer(), nullable=True),
        sa.Column(
            "capabilities_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="untested",
            nullable=False,
        ),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(scope = 'personal' AND owner_user_id IS NOT NULL AND workspace_id IS NULL) "
            "OR (scope = 'workspace' AND workspace_id IS NOT NULL AND owner_user_id IS NULL)",
            name="ck_model_profiles_scope_owner",
        ),
        sa.CheckConstraint(
            "provider IN ('mock', 'ollama', 'openai_compatible')",
            name="ck_model_profiles_provider",
        ),
        sa.CheckConstraint(
            "status IN ('untested', 'active', 'invalid', 'revoked')",
            name="ck_model_profiles_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_model_profiles_workspace_key",
        "model_profiles",
        ["workspace_id", "profile_key"],
        unique=True,
        postgresql_where=sa.text("scope = 'workspace'"),
    )
    op.create_index(
        "uq_model_profiles_owner_key",
        "model_profiles",
        ["owner_user_id", "profile_key"],
        unique=True,
        postgresql_where=sa.text("scope = 'personal'"),
    )

    op.add_column(
        "workspaces",
        sa.Column(
            "default_model_profile_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_workspaces_default_model_profile",
        "workspaces",
        "model_profiles",
        ["default_model_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_workspaces_default_model_profile", "workspaces", type_="foreignkey")
    op.drop_column("workspaces", "default_model_profile_id")
    op.drop_index("uq_model_profiles_owner_key", table_name="model_profiles")
    op.drop_index("uq_model_profiles_workspace_key", table_name="model_profiles")
    op.drop_table("model_profiles")

    op.drop_constraint("ck_memberships_role", "memberships", type_="check")
    op.drop_constraint("fk_memberships_user_id_users", "memberships", type_="foreignkey")
    op.drop_constraint("fk_memberships_workspace_id_workspaces", "memberships", type_="foreignkey")
    op.drop_constraint("ck_workspaces_schema_version", "workspaces", type_="check")
    op.drop_constraint("ck_workspaces_status", "workspaces", type_="check")
    op.drop_constraint("ck_users_status", "users", type_="check")
    op.drop_constraint("uq_workspaces_owner_slug", "workspaces", type_="unique")
    op.drop_constraint("fk_workspaces_owner_id_users", "workspaces", type_="foreignkey")
    op.drop_column("workspaces", "updated_at")
    op.drop_column("users", "updated_at")
