from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.main import app
from app.models import Membership, ModelProfile, User, Workspace
from app.seed import (
    DEFAULT_MOCK_PROFILE_ID,
    DEFAULT_USER_ID,
    DEFAULT_WORKSPACE_ID,
    seed_database,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def database_ready():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        pytest.skip("PostgreSQL integration database is unavailable")
    seed_database()


def test_seed_is_idempotent():
    seed_database()
    seed_database()

    with SessionLocal() as db:
        assert (
            db.scalar(select(func.count()).select_from(User).where(User.id == DEFAULT_USER_ID)) == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(Workspace)
                .where(Workspace.id == DEFAULT_WORKSPACE_ID)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(Membership)
                .where(
                    Membership.workspace_id == DEFAULT_WORKSPACE_ID,
                    Membership.user_id == DEFAULT_USER_ID,
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(ModelProfile)
                .where(ModelProfile.id == DEFAULT_MOCK_PROFILE_ID)
            )
            == 1
        )


def test_workspace_and_profile_api_are_available_and_redacted():
    client = TestClient(app)

    workspace_response = client.get("/api/workspaces")
    assert workspace_response.status_code == 200
    workspace = workspace_response.json()["items"][0]
    workspace_id = workspace["id"]

    profile_response = client.get(f"/api/workspaces/{workspace_id}/model-profiles")
    assert profile_response.status_code == 200
    profile = profile_response.json()["items"][0]
    assert profile["profile_key"] == "mock-default"
    assert profile["has_credential"] is False
    assert "base_url" not in profile
    assert "credential_ciphertext" not in profile
    assert "credential_key_version" not in profile


def test_profile_lookup_is_scoped_to_workspace():
    client = TestClient(app)
    other_workspace = uuid.uuid4()

    response = client.get(
        f"/api/workspaces/{other_workspace}/model-profiles/{DEFAULT_MOCK_PROFILE_ID}"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["request_id"].startswith("req_")


def test_validation_errors_use_stable_shape():
    client = TestClient(app)

    response = client.get("/api/workspaces/not-a-uuid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.headers["x-request-id"].startswith("req_")
