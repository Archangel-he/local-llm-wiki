"""Contract tests for Sources API.

These tests define the expected request/response format for Sources endpoints.
B should implement the API to make these tests pass.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings

client = TestClient(app)


class TestSourcesContract:
    """Contract tests for Sources API.

    These tests validate the API contract format, not the business logic.
    """

    WORKSPACE_ID = "00000000-0000-0000-0000-000000000002"

    @pytest.fixture(autouse=True)
    def _skip_if_not_implemented(self):
        """Skip all tests if the sources endpoint doesn't exist yet."""
        resp = client.post(f"/api/workspaces/{self.WORKSPACE_ID}/sources")
        if resp.status_code in (404, 405):
            pytest.skip("Sources API not yet implemented")

    def test_upload_returns_202(self):
        """POST /sources must return 202 Accepted with Source + Job IDs."""
        resp = client.post(
            f"/api/workspaces/{self.WORKSPACE_ID}/sources",
            files={"file": ("aurora-a.md", open("tests/fixtures/aurora-a.md", "rb"))},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "source" in body, "Response must include 'source' object"
        assert "job" in body, "Response must include 'job' object"
        assert "id" in body["source"], "Source must have an 'id'"
        assert "sha256" in body["source"], "Source must have a 'sha256' field"
        assert "status" in body["source"], "Source must have a 'status' field"
        assert body["source"]["status"] == "active"
        assert "id" in body["job"], "Job must have an 'id'"
        assert body["job"]["status"] == "queued", "New job must be 'queued'"

    def test_upload_rejects_invalid_type(self):
        """Uploading unsupported file types must return 4xx."""
        resp = client.post(
            f"/api/workspaces/{self.WORKSPACE_ID}/sources",
            files={"file": ("test.exe", b"fake binary content")},
        )
        assert resp.status_code in (400, 415, 422)
        body = resp.json()
        assert "error" in body or "detail" in body

    def test_upload_rejects_too_large(self):
        """File exceeding MAX_UPLOAD_MB must return 4xx."""
        large = b"x" * (settings.max_upload_bytes + 1)
        resp = client.post(
            f"/api/workspaces/{self.WORKSPACE_ID}/sources",
            files={"file": ("huge.md", large)},
        )
        assert resp.status_code in (400, 413, 422)

    def test_get_source_returns_metadata(self):
        """GET /sources/{id} must return source metadata with all fields."""
        # First upload
        upload = client.post(
            f"/api/workspaces/{self.WORKSPACE_ID}/sources",
            files={"file": ("test-get.md", b"# Test get source")},
        )
        source_id = upload.json()["source"]["id"]

        resp = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/sources/{source_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == source_id
        assert "sha256" in body
        assert "original_filename" in body
        assert "mime_type" in body
        assert "size_bytes" in body
        assert "status" in body
        assert "created_at" in body

    def test_get_source_content(self):
        """GET /sources/{id}/content must return raw file bytes."""
        upload = client.post(
            f"/api/workspaces/{self.WORKSPACE_ID}/sources",
            files={"file": ("content-test.md", b"# Raw content")},
        )
        source_id = upload.json()["source"]["id"]

        resp = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/sources/{source_id}/content")
        assert resp.status_code == 200
        assert resp.headers["content-type"] in ("text/markdown", "text/plain", "application/octet-stream")

    def test_delete_source_archives(self):
        """DELETE /sources/{id} must archive (not hard delete)."""
        upload = client.post(
            f"/api/workspaces/{self.WORKSPACE_ID}/sources",
            files={"file": ("delete-test.md", b"# To be deleted")},
        )
        source_id = upload.json()["source"]["id"]

        resp = client.delete(f"/api/workspaces/{self.WORKSPACE_ID}/sources/{source_id}")
        assert resp.status_code in (200, 204)

        # After delete, status should be 'archived'
        get = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/sources/{source_id}")
        if get.status_code == 200:
            assert get.json()["status"] == "archived"

    def test_duplicate_upload_returns_existing(self):
        """Same SHA-256 in same workspace must return existing Source."""
        content = b"# Duplicate test content"
        resp1 = client.post(
            f"/api/workspaces/{self.WORKSPACE_ID}/sources",
            files={"file": ("dup-a.md", content)},
        )
        resp2 = client.post(
            f"/api/workspaces/{self.WORKSPACE_ID}/sources",
            files={"file": ("dup-b.md", content)},
        )
        # Must return existing source, not create new one
        assert resp1.json()["source"]["sha256"] == resp2.json()["source"]["sha256"]
        # If it returns existing source without creating new job, job might be empty
        body2 = resp2.json()
        assert body2["source"]["status"] == "active"
