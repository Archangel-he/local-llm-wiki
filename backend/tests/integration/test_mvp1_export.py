from __future__ import annotations

import hashlib
import io
import json
import os
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from rq import Queue, SimpleWorker
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import PageAlias, Source, WikiPage, WikiRevision
from app.seed import DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, seed_database
from app.services.storage import LocalStorage

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def database_ready():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        pytest.skip("PostgreSQL integration database is unavailable")
    seed_database()


def test_export_job_builds_downloadable_obsidian_vault(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    redis_url = os.environ.get("REDIS_TEST_URL")
    if not redis_url:
        pytest.skip("Set REDIS_TEST_URL to an isolated, disposable Redis database")
    redis = Redis.from_url(redis_url)
    redis.ping()
    redis.flushdb()
    monkeypatch.setattr(settings, "redis_url", redis_url)
    monkeypatch.setattr(settings, "local_storage_path", str(tmp_path))

    marker = uuid.uuid4().hex[:10]
    raw = f"# Aurora Export {marker}\n".encode()
    stored = LocalStorage(tmp_path).put_immutable(io.BytesIO(raw))
    with SessionLocal.begin() as db:
        source = Source(
            workspace_id=DEFAULT_WORKSPACE_ID,
            sha256=hashlib.sha256(raw).hexdigest(),
            original_filename=f"aurora-export-{marker}.md",
            safe_filename=f"aurora-export-{marker}.md",
            mime_type="text/markdown",
            size_bytes=len(raw),
            storage_key=stored.storage_key,
            status="active",
            created_by=DEFAULT_USER_ID,
        )
        db.add(source)
        db.flush()
        page = WikiPage(
            workspace_id=DEFAULT_WORKSPACE_ID,
            slug=f"aurora-export-{marker}",
            title=f"Aurora Export {marker}",
            page_type="topic",
            summary="Export fixture",
            status="active",
        )
        db.add(page)
        db.flush()
        revision = WikiRevision(
            workspace_id=DEFAULT_WORKSPACE_ID,
            page_id=page.id,
            revision_no=1,
            markdown=f"# Aurora Export {marker}\n\nLinks to [[Aurora Export {marker}]].",
            frontmatter_json={},
            schema_version=1,
            created_by=DEFAULT_USER_ID,
        )
        db.add(revision)
        db.flush()
        page.current_revision_id = revision.id
        db.add(
            PageAlias(
                workspace_id=DEFAULT_WORKSPACE_ID,
                page_id=page.id,
                alias_normalized=f"export alias {marker}",
                alias_display=f"Export Alias {marker}",
                created_by_revision_id=revision.id,
            )
        )

    client = TestClient(app)
    created = client.post(
        f"/api/workspaces/{DEFAULT_WORKSPACE_ID}/exports",
        json={"include_raw": True},
    )
    assert created.status_code == 202, created.text
    export_id = created.json()["id"]

    queue = Queue(settings.rq_queue_name, connection=redis)
    worker = SimpleWorker([queue], connection=redis)
    assert worker.work(burst=True, logging_level="WARNING") is True

    status_response = client.get(
        f"/api/workspaces/{DEFAULT_WORKSPACE_ID}/exports/{export_id}"
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"
    assert status_response.json()["sha256"]

    download = client.get(
        f"/api/workspaces/{DEFAULT_WORKSPACE_ID}/exports/{export_id}/download"
    )
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = set(archive.namelist())
        page_path = f"concepts/aurora-export-{marker}.md"
        assert page_path in names
        assert "index.md" in names
        assert "log.md" in names
        assert "export-manifest.json" in names
        assert any(name.startswith("raw/") and name.endswith(f"{marker}.md") for name in names)
        page_markdown = archive.read(page_path).decode()
        assert f"aliases:\n- Export Alias {marker}" in page_markdown
        assert f"[[aurora-export-{marker}]]" in page_markdown
        manifest = json.loads(archive.read("export-manifest.json"))
        assert manifest["export_id"] == export_id
        assert page_path in manifest["files"]

    recovered = client.post(
        f"/api/workspaces/{DEFAULT_WORKSPACE_ID}/exports",
        json={"include_raw": True},
    )
    assert recovered.status_code == 202
    assert recovered.json()["id"] == export_id
    assert recovered.json()["status"] == "completed"

    empty_storage = tmp_path / "recovered-storage"
    monkeypatch.setattr(settings, "local_storage_path", str(empty_storage))
    missing_artifact = client.post(
        f"/api/workspaces/{DEFAULT_WORKSPACE_ID}/exports",
        json={"include_raw": True},
    )
    assert missing_artifact.status_code == 202
    assert missing_artifact.json()["id"] == export_id
    assert missing_artifact.json()["status"] == "queued"
    recovery_worker = SimpleWorker([queue], connection=redis)
    assert recovery_worker.work(burst=True, logging_level="WARNING") is True
    recovered_status = client.get(
        f"/api/workspaces/{DEFAULT_WORKSPACE_ID}/exports/{export_id}"
    )
    assert recovered_status.json()["status"] == "completed"
    redis.flushdb()
    redis.close()
