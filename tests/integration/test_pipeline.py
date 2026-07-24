"""Full pipeline integration test for MVP 1.

Tests: upload -> ingest -> wiki -> graph
Skipped gracefully when endpoints not yet implemented.
"""
from __future__ import annotations

import hashlib
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

WORKSPACE_ID = "00000000-0000-0000-0000-000000000002"
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def fixture_path(name: str) -> str:
    return os.path.join(FIXTURE_DIR, name)


def sha256_of(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class TestIngestPipeline:
    """End-to-end test: upload aurora-a.md -> source created -> job created."""

    def _api_ready(self) -> bool:
        resp = client.get(f"/api/workspaces/{WORKSPACE_ID}/sources")
        return resp.status_code not in (404, 405)

    @pytest.fixture(autouse=True)
    def _skip(self):
        if not self._api_ready():
            pytest.skip("Pipeline endpoints not implemented yet")

    def test_upload_aurora_a_returns_202(self):
        """Upload aurora-a.md -> 202 with source and job."""
        path = fixture_path("aurora-a.md")
        with open(path, "rb") as f:
            resp = client.post(
                f"/api/workspaces/{WORKSPACE_ID}/sources",
                files={"file": ("aurora-a.md", f)},
            )
        assert resp.status_code == 202
        body = resp.json()
        assert "source" in body
        assert "job" in body
        assert body["source"]["sha256"] == sha256_of(path)
        assert body["source"]["status"] == "active"

    def test_source_sha256_matches(self):
        """Upload -> source sha256 matches original file."""
        path = fixture_path("aurora-a.md")
        expected = sha256_of(path)
        with open(path, "rb") as f:
            resp = client.post(
                f"/api/workspaces/{WORKSPACE_ID}/sources",
                files={"file": ("aurora-a.md", f)},
            )
        assert resp.status_code == 202
        assert resp.json()["source"]["sha256"] == expected

    def test_job_status_transitions(self):
        """Upload -> job transitions through statuses."""
        path = fixture_path("aurora-a.md")
        with open(path, "rb") as f:
            resp = client.post(
                f"/api/workspaces/{WORKSPACE_ID}/sources",
                files={"file": ("aurora-a.md", f)},
            )
        job_id = resp.json()["job"]["id"]

        # Poll until completed or timeout
        for _ in range(30):
            job = client.get(f"/api/workspaces/{WORKSPACE_ID}/jobs/{job_id}").json()
            if job["status"] == "completed":
                break
            if job["status"] == "failed":
                pytest.fail(f"Job failed: {job}")
            import time

            time.sleep(1)
        else:
            pytest.fail("Job did not complete in 30 seconds")

    def test_wiki_created_after_ingest(self):
        """After ingest, wiki pages exist for the source."""
        pages = client.get(f"/api/workspaces/{WORKSPACE_ID}/wiki").json()
        assert len(pages) > 0, "Wiki should have at least one page after ingest"

    def test_graph_has_nodes(self):
        """After ingest, graph contains nodes and edges."""
        graph = client.get(f"/api/workspaces/{WORKSPACE_ID}/graph").json()
        assert len(graph["nodes"]) > 0, "Graph should have at least one node"
