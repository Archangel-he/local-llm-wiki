from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, LargeBinary, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class ModelProfile(TimestampMixin, Base):
    __tablename__ = "model_profiles"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'personal' AND owner_user_id IS NOT NULL AND workspace_id IS NULL) "
            "OR (scope = 'workspace' AND workspace_id IS NOT NULL AND owner_user_id IS NULL)",
            name="ck_model_profiles_scope_owner",
        ),
        CheckConstraint(
            "provider IN ('mock', 'ollama', 'openai_compatible')",
            name="ck_model_profiles_provider",
        ),
        CheckConstraint(
            "status IN ('untested', 'active', 'invalid', 'revoked')",
            name="ck_model_profiles_status",
        ),
        Index(
            "uq_model_profiles_workspace_key",
            "workspace_id",
            "profile_key",
            unique=True,
            postgresql_where=text("scope = 'workspace'"),
        ),
        Index(
            "uq_model_profiles_owner_key",
            "owner_user_id",
            "profile_key",
            unique=True,
            postgresql_where=text("scope = 'personal'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True
    )
    profile_key: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    credential_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    credential_key_version: Mapped[int | None] = mapped_column(nullable=True)
    capabilities_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="untested", server_default="untested"
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
