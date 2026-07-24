from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestJobsContract:
    WORKSPACE_ID = "00000000-0000-0000-0000-000000000002"
    JOB_TYPES = ("ingest", "query", "lint", "export")
    VALID_STATUSES = ("queued", "running", "completed", "failed", "cancelled", "retrying")

    @pytest.fixture(autouse=True)
    def _skip_if_not_implemented(self):
        resp = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/jobs")
        if resp.status_code in (404, 405):
            pytest.skip("Jobs API not implemented")

    def test_list_jobs_returns_array(self):
        resp = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/jobs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_job_has_required_fields(self):
        jobs = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/jobs").json()
        if not jobs:
            pytest.skip("No jobs")
        j = jobs[0]
        assert "id" in j and "type" in j
        assert j["type"] in self.JOB_TYPES
        assert "status" in j and j["status"] in self.VALID_STATUSES

    def test_job_detail_has_progress(self):
        jobs = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/jobs").json()
        if not jobs:
            pytest.skip("No jobs")
        d = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/jobs/{jobs[0]['id']}")
        assert d.status_code == 200
        b = d.json()
        assert "attempt" in b and "max_attempts" in b

    def test_invalid_job_404(self):
        assert client.get(f"/api/workspaces/{self.WORKSPACE_ID}/jobs/bad-id").status_code == 404
