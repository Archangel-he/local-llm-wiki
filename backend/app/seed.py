"""Idempotently create the MVP 0 user, workspace, membership, and profiles."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert

from .config import settings
from .database import SessionLocal
from .models import Membership, ModelProfile, User, Workspace

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DEFAULT_MOCK_PROFILE_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
PROFILE_NAMESPACE = uuid.UUID("c196fd75-9898-4a75-a627-457c3e27eb20")


@dataclass(frozen=True)
class SeedProfile:
    profile_key: str
    display_name: str
    provider: str
    base_url: str | None
    model_name: str | None
    status: str
    profile_id: uuid.UUID | None = None

    @property
    def id(self) -> uuid.UUID:
        return self.profile_id or uuid.uuid5(PROFILE_NAMESPACE, self.profile_key)


def _profiles_from_settings() -> list[SeedProfile]:
    profiles = [
        SeedProfile(
            profile_key="mock-default",
            display_name="Mock LLM",
            provider="mock",
            base_url=None,
            model_name="mock",
            status="active",
            profile_id=DEFAULT_MOCK_PROFILE_ID,
        )
    ]
    if settings.mac_qwen36_enabled:
        profiles.append(
            SeedProfile(
                profile_key="mac-qwen36",
                display_name="Mac Studio Qwen 3.6",
                provider="openai_compatible",
                base_url=settings.mac_qwen36_base_url.rstrip("/"),
                model_name=settings.mac_qwen36_model,
                status="untested",
            )
        )
    if settings.spark_qwen36_enabled:
        profiles.append(
            SeedProfile(
                profile_key="spark-qwen36",
                display_name="DGX Spark Qwen 3.6",
                provider="openai_compatible",
                base_url=settings.spark_qwen36_base_url.rstrip("/"),
                model_name=settings.spark_qwen36_model,
                status="untested",
            )
        )
    return profiles


def seed_database() -> None:
    """Create missing defaults without overwriting user-managed values."""

    profiles = _profiles_from_settings()
    with SessionLocal.begin() as db:
        db.execute(
            insert(User)
            .values(
                id=DEFAULT_USER_ID,
                email=settings.default_user_email.strip().lower(),
                display_name=settings.default_user_display_name,
                status="active",
            )
            .on_conflict_do_nothing(index_elements=[User.id])
        )
        db.execute(
            insert(Workspace)
            .values(
                id=DEFAULT_WORKSPACE_ID,
                owner_id=DEFAULT_USER_ID,
                name=settings.default_workspace_name,
                slug=settings.default_workspace_slug,
                status="active",
                schema_version=1,
            )
            .on_conflict_do_nothing(index_elements=[Workspace.id])
        )
        db.execute(
            insert(Membership)
            .values(
                workspace_id=DEFAULT_WORKSPACE_ID,
                user_id=DEFAULT_USER_ID,
                role="owner",
            )
            .on_conflict_do_nothing(index_elements=[Membership.workspace_id, Membership.user_id])
        )

        for profile in profiles:
            db.execute(
                insert(ModelProfile)
                .values(
                    id=profile.id,
                    scope="workspace",
                    workspace_id=DEFAULT_WORKSPACE_ID,
                    owner_user_id=None,
                    profile_key=profile.profile_key,
                    provider=profile.provider,
                    display_name=profile.display_name,
                    base_url=profile.base_url,
                    model_name=profile.model_name,
                    capabilities_json={},
                    status=profile.status,
                    created_by=DEFAULT_USER_ID,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        ModelProfile.workspace_id,
                        ModelProfile.profile_key,
                    ],
                    index_where=text("scope = 'workspace'"),
                )
            )

        requested_profile = next(
            (
                p
                for p in profiles
                if p.profile_key == settings.default_llm_profile_key and p.status == "active"
            ),
            profiles[0],
        )
        active_profile_id = db.scalar(
            select(ModelProfile.id).where(
                ModelProfile.workspace_id == DEFAULT_WORKSPACE_ID,
                ModelProfile.profile_key == requested_profile.profile_key,
                ModelProfile.status == "active",
            )
        )
        db.execute(
            update(Workspace)
            .where(
                Workspace.id == DEFAULT_WORKSPACE_ID,
                Workspace.default_model_profile_id.is_(None),
            )
            .values(default_model_profile_id=active_profile_id)
        )

    print(
        "Default data ready: "
        f"user={DEFAULT_USER_ID} workspace={DEFAULT_WORKSPACE_ID} "
        f"profiles={','.join(profile.profile_key for profile in profiles)}"
    )


if __name__ == "__main__":
    seed_database()
