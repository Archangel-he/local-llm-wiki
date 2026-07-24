from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.ingest.context import ExistingPageCandidate, IngestContext
from app.ingest.mock_planner import build_mock_ingest_batch
from app.ingest.parser import parse_source
from app.ingest.validation import IngestValidationError, validate_ingest_batch
from app.llm.types import RuntimeModelProfile
from app.schemas.wiki import WikiOperationBatch


def _context(
    *, existing_pages: tuple[ExistingPageCandidate, ...] = ()
) -> IngestContext:
    return IngestContext(
        job_id=uuid.UUID("10000000-0000-0000-0000-000000000001"),
        workspace_id=uuid.UUID("20000000-0000-0000-0000-000000000001"),
        source_id=uuid.UUID("30000000-0000-0000-0000-000000000001"),
        source_filename="aurora.md",
        source_mime_type="text/markdown",
        source_storage_key="sources/aurora.md",
        schema_version=1,
        prompt_version="mvp1-ingest-v1",
        runtime_profile=RuntimeModelProfile(
            profile_id="mock-default",
            provider="mock",
            base_url="mock://local",
            model_name="deterministic",
        ),
        existing_pages=existing_pages,
    )


def _fixture():
    parsed = parse_source("# Project Aurora\n\n项目负责人是 Lin。\n")
    context = _context()
    batch = build_mock_ingest_batch(context, parsed)
    return context, parsed, batch.model_dump(mode="json")


def test_mock_planner_produces_source_topic_entity_links_and_citations() -> None:
    context, parsed, data = _fixture()
    result = validate_ingest_batch(data, context, parsed)

    assert [operation.page_type for operation in result.operations] == [
        "source",
        "topic",
        "entity",
    ]
    assert result.operations[1].title == "Project Aurora"
    assert result.operations[2].title == "Lin"
    assert all(operation.citations for operation in result.operations)


def test_forged_excerpt_is_rejected() -> None:
    context, parsed, data = _fixture()
    data["operations"][1]["citations"][0]["excerpt"] = "not in source"

    with pytest.raises(IngestValidationError, match="excerpt"):
        validate_ingest_batch(data, context, parsed)


def test_wrong_source_and_missing_locator_are_rejected() -> None:
    context, parsed, data = _fixture()
    data["operations"][0]["citations"][0]["source_id"] = str(uuid.uuid4())
    with pytest.raises(IngestValidationError, match="unavailable source"):
        validate_ingest_batch(data, context, parsed)

    _, _, data = _fixture()
    data["operations"][0]["citations"][0]["locator"] = "lines:99-100"
    with pytest.raises(IngestValidationError, match="locator"):
        validate_ingest_batch(data, context, parsed)


def test_missing_source_summary_and_duplicate_alias_are_rejected() -> None:
    context, parsed, data = _fixture()
    data["operations"] = data["operations"][1:]
    with pytest.raises(IngestValidationError, match="Source Summary"):
        validate_ingest_batch(data, context, parsed)

    _, _, data = _fixture()
    data["operations"][2]["aliases"] = ["Aurora Project"]
    with pytest.raises(IngestValidationError, match="duplicate"):
        validate_ingest_batch(data, context, parsed)


def test_inferred_relationship_requires_current_source_evidence() -> None:
    context, parsed, data = _fixture()
    data["operations"][1]["links"] = [
        {"target_slug": "lin", "type": "related"}
    ]
    with pytest.raises(IngestValidationError, match="evidence"):
        validate_ingest_batch(data, context, parsed)


def test_existing_page_update_requires_current_revision() -> None:
    page_id = uuid.uuid4()
    candidate = ExistingPageCandidate(
        id=page_id,
        title="Project Aurora",
        slug="project-aurora",
        page_type="topic",
        aliases=(),
        revision_no=7,
        summary=None,
        primary_source_id=None,
    )
    context = _context(existing_pages=(candidate,))
    parsed = parse_source("# Project Aurora\n\n项目负责人是 Lin。")
    data = build_mock_ingest_batch(context, parsed).model_dump(mode="json")
    data["operations"][1]["expected_revision_no"] = 6

    with pytest.raises(IngestValidationError, match="stale"):
        validate_ingest_batch(data, context, parsed)


def test_runtime_schema_matches_checked_in_json_schema() -> None:
    schema_path = Path(__file__).parents[2] / "wiki" / "schema" / "ingest.schema.json"
    checked_in = json.loads(schema_path.read_text(encoding="utf-8"))
    assert checked_in == WikiOperationBatch.model_json_schema()
