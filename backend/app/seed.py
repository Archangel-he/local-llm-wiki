"""Create default user and default workspace for MVP 0."""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import engine, SessionLocal
from .models.user import Membership, User, Workspace

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def seed_database() -> None:
    """Create default user and workspace if they don't exist."""
    with SessionLocal() as db:
        existing = db.get(User, DEFAULT_USER_ID)
        if existing is not None:
            print("Default user already exists, skipping seed.")
            return

        user = User(
            id=DEFAULT_USER_ID,
            email="default@local-llm-wiki.local",
            display_name="Default User",
            status="active",
        )
        workspace = Workspace(
            id=DEFAULT_WORKSPACE_ID,
            owner_id=DEFAULT_USER_ID,
            name="My Workspace",
            slug="my-workspace",
            status="active",
            schema_version=1,
        )
        membership = Membership(
            workspace_id=DEFAULT_WORKSPACE_ID,
            user_id=DEFAULT_USER_ID,
            role="owner",
        )
        db.add_all([user, workspace, membership])
        db.commit()
        print(f"Seeded default user ({DEFAULT_USER_ID}) and workspace ({DEFAULT_WORKSPACE_ID}).")


if __name__ == "__main__":
    seed_database()
