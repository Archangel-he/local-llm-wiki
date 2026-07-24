from __future__ import annotations

import uuid
from io import BytesIO
from types import SimpleNamespace

import pytest

import app.ingest.pipeline as pipeline
from app.ingest.context import IngestContext
from app.llm.mock import MockLLMAdapter, MockScenario
from app.llm.types import RuntimeModelProfile


class _SessionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, traceback):
        return False


class _Storage:
    def open(self, storage_key: str) -> BytesIO:
        assert storage_key == "raw/aurora"
        return BytesIO("# Project Aurora\n\n项目负责人是 Lin。".encode())


def _context(job_id: uuid.UUID) -> IngestContext:
    return IngestContext(
        job_id=job_id,
        workspace_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        source_filename="aurora.md",
        source_mime_type="text/markdown",
        source_storage_key="raw/aurora",
        schema_version=1,
        prompt_version="mvp1-ingest-v1",
        runtime_profile=RuntimeModelProfile(
            profile_id="mock-default",
            provider="mock",
            base_url="mock://local",
            model_name="mock",
        ),
        existing_pages=(),
    )


def _patch_boundaries(monkeypatch: pytest.MonkeyPatch, job_id: uuid.UUID):
    progress: list[str] = []
    commits: list[object] = []
    failures: list[Exception] = []
    monkeypatch.setattr(pipeline, "SessionLocal", _SessionContext)
    monkeypatch.setattr(pipeline, "claim_ingest_job", lambda db, value: None)
    monkeypatch.setattr(pipeline, "_check_cancelled", lambda value: None)
    monkeypatch.setattr(
        pipeline,
        "_progress",
        lambda value, percent, stage, **kwargs: progress.append(stage),
    )
    monkeypatch.setattr(
        pipeline,
        "load_source_input",
        lambda db, value: SimpleNamespace(storage_key="raw/aurora"),
    )
    monkeypatch.setattr(pipeline, "get_storage", lambda: _Storage())
    monkeypatch.setattr(pipeline, "build_ingest_context", lambda db, value: _context(job_id))
    monkeypatch.setattr(
        pipeline,
        "apply_wiki_operations",
        lambda *args: commits.append(args[-1]),
    )
    monkeypatch.setattr(pipeline, "_record_failure", lambda value, exc: failures.append(exc))
    return progress, commits, failures


def test_pipeline_runs_all_stages_and_commits_once(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    progress, commits, failures = _patch_boundaries(monkeypatch, job_id)

    pipeline.run_ingest_job(job_id)

    assert progress == [
        "parsing",
        "loading_context",
        "calling_model",
        "validating",
        "committing",
    ]
    assert len(commits) == 1
    assert failures == []


def test_model_failure_never_reaches_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    _, commits, failures = _patch_boundaries(monkeypatch, job_id)

    pipeline.run_ingest_job(
        job_id,
        adapter_factory=lambda provider: MockLLMAdapter(
            scenario=MockScenario.INVALID_JSON
        ),
    )

    assert commits == []
    assert len(failures) == 1


def test_cancellation_stops_before_any_model_or_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid.uuid4()
    progress, commits, failures = _patch_boundaries(monkeypatch, job_id)
    monkeypatch.setattr(
        pipeline,
        "_check_cancelled",
        lambda value: (_ for _ in ()).throw(pipeline.IngestCancelled()),
    )

    pipeline.run_ingest_job(job_id)

    assert progress == []
    assert commits == []
    assert failures == []


def test_transaction_failure_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid.uuid4()
    _, _, failures = _patch_boundaries(monkeypatch, job_id)
    monkeypatch.setattr(
        pipeline,
        "apply_wiki_operations",
        lambda *args: (_ for _ in ()).throw(RuntimeError("database details")),
    )

    pipeline.run_ingest_job(job_id)

    assert len(failures) == 1
    assert type(failures[0]) is RuntimeError
