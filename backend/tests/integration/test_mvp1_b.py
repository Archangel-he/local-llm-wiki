from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal
from app.main import app
from app.models import Job, PageAlias, Source, WikiLink, WikiPage, WikiRevision, Workspace
from app.schemas.wiki import WikiOperationBatch
from app.seed import DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, seed_database
from app.services.wiki import AliasConflict, apply_wiki_operations

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def database_ready():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        pytest.skip("PostgreSQL integration database is unavailable")
    seed_database()


def _create_running_job() -> tuple[uuid.UUID, uuid.UUID]:
    marker = uuid.uuid4().hex
    with SessionLocal.begin() as db:
        workspace = db.get(Workspace, DEFAULT_WORKSPACE_ID)
        assert workspace is not None and workspace.default_model_profile_id is not None
        source = Source(
            workspace_id=DEFAULT_WORKSPACE_ID,
            sha256=marker + marker,
            original_filename=f"{marker}.md",
            safe_filename=f"{marker}.md",
            mime_type="text/markdown",
            size_bytes=1,
            storage_key=f"raw/test/{marker}",
            status="active",
            created_by=DEFAULT_USER_ID,
        )
        db.add(source)
        db.flush()
        job = Job(
            workspace_id=DEFAULT_WORKSPACE_ID,
            source_id=source.id,
            model_profile_id=workspace.default_model_profile_id,
            model_snapshot_json={"provider": "mock", "name": "mock"},
            job_type="ingest",
            status="running",
            idempotency_key=marker,
            attempt=1,
            max_attempts=3,
            progress=50,
            progress_json={"stage": "generating_wiki"},
            created_by=DEFAULT_USER_ID,
        )
        db.add(job)
        db.flush()
        return job.id, source.id


def test_upload_is_immutable_and_idempotent(monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "local_storage_path", str(tmp_path))
    client = TestClient(app)
    payload = b"# Aurora\nLaunch date: 2025-03-01\n"

    first = client.post(
        f"/api/workspaces/{DEFAULT_WORKSPACE_ID}/sources",
        files={"file": ("aurora.md", payload, "text/markdown")},
    )
    second = client.post(
        f"/api/workspaces/{DEFAULT_WORKSPACE_ID}/sources",
        files={"file": ("renamed.md", payload, "text/markdown")},
    )

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert first.json()["source"]["id"] == second.json()["source"]["id"]
    assert first.json()["job"]["id"] == second.json()["job"]["id"]
    assert second.json()["deduplicated"] is True

    content = client.get(
        f"/api/workspaces/{DEFAULT_WORKSPACE_ID}/sources/"
        f"{first.json()['source']['id']}/content"
    )
    assert content.status_code == 200
    assert content.content == payload


def test_wiki_batch_resolves_forward_links_and_commits_atomically():
    job_id, source_id = _create_running_job()

    first_page_id = uuid.uuid4()
    second_page_id = uuid.uuid4()
    batch = WikiOperationBatch.model_validate(
        {
            "schema_version": 1,
            "source_id": source_id,
            "operations": [
                {
                    "action": "create_page",
                    "page_id": first_page_id,
                    "title": "Project Aurora",
                    "slug": "project-aurora",
                    "page_type": "topic",
                    "aliases": ["Aurora Project", "极光项目"],
                    "markdown": "# Project Aurora",
                    "links": [{"target_slug": "lin", "type": "wikilink"}],
                    "citations": [
                        {"source_id": str(source_id), "locator": "paragraph-1"}
                    ],
                },
                {
                    "action": "create_page",
                    "page_id": second_page_id,
                    "title": "Lin",
                    "slug": "lin",
                    "page_type": "entity",
                    "aliases": [],
                    "markdown": "# Lin",
                },
            ],
        }
    )
    with SessionLocal() as db:
        result = apply_wiki_operations(
            db, DEFAULT_WORKSPACE_ID, job_id, DEFAULT_USER_ID, batch
        )

    assert set(result.affected_page_ids) == {first_page_id, second_page_id}
    with SessionLocal() as db:
        link = db.scalar(
            select(WikiLink).where(
                WikiLink.workspace_id == DEFAULT_WORKSPACE_ID,
                WikiLink.source_page_id == first_page_id,
            )
        )
        assert link is not None and link.target_page_id == second_page_id
        assert db.scalar(select(Job.status).where(Job.id == job_id)) == "completed"
        assert db.scalar(
            select(func.count()).select_from(PageAlias).where(PageAlias.page_id == first_page_id)
        ) == 2


def test_alias_conflict_rolls_back_entire_wiki_batch():
    job_id, source_id = _create_running_job()
    with SessionLocal.begin() as db:
        existing_page = WikiPage(
            workspace_id=DEFAULT_WORKSPACE_ID,
            slug=f"existing-{uuid.uuid4().hex}",
            title="Existing Aurora",
            page_type="topic",
            status="active",
        )
        db.add(existing_page)
        db.flush()
        existing_revision = WikiRevision(
            workspace_id=DEFAULT_WORKSPACE_ID,
            page_id=existing_page.id,
            revision_no=1,
            markdown="# Existing",
            frontmatter_json={},
            schema_version=1,
            created_by=DEFAULT_USER_ID,
        )
        db.add(existing_revision)
        db.flush()
        existing_page.current_revision_id = existing_revision.id
        db.add(
            PageAlias(
                workspace_id=DEFAULT_WORKSPACE_ID,
                page_id=existing_page.id,
                alias_normalized="reserved-alias",
                alias_display="Reserved Alias",
                created_by_revision_id=existing_revision.id,
            )
        )

    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(WikiRevision))

    batch = WikiOperationBatch.model_validate(
        {
            "schema_version": 1,
            "source_id": source_id,
            "operations": [
                {
                    "action": "create_page",
                    "title": "Temporary Page",
                    "slug": "temporary-page",
                    "page_type": "topic",
                    "aliases": ["Reserved Alias"],
                    "markdown": "# Must roll back",
                }
            ],
        }
    )
    with SessionLocal() as db, pytest.raises(AliasConflict):
        apply_wiki_operations(db, DEFAULT_WORKSPACE_ID, job_id, DEFAULT_USER_ID, batch)

    with SessionLocal() as db:
        after = db.scalar(select(func.count()).select_from(WikiRevision))
        assert after == before
        assert db.scalar(
            select(func.count())
            .select_from(WikiPage)
            .where(WikiPage.slug == "temporary-page")
        ) == 0
