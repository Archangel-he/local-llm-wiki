"""Deterministic MVP 1 planner used only by the built-in Mock profile."""

from __future__ import annotations

import re
import uuid
from pathlib import PurePath

from app.ingest.context import ExistingPageCandidate, IngestContext
from app.ingest.parser import ParsedSource, SourceSegment
from app.schemas.wiki import WikiOperationBatch
from app.services.wiki import normalize_alias, normalize_slug


def _matching_candidate(
    context: IngestContext,
    title: str,
    slug: str,
    *,
    source_summary: bool = False,
) -> ExistingPageCandidate | None:
    if source_summary:
        return next(
            (
                candidate
                for candidate in context.existing_pages
                if candidate.primary_source_id == context.source_id
            ),
            None,
        )
    names = {normalize_alias(title), normalize_alias(slug)}
    return next(
        (
            candidate
            for candidate in context.existing_pages
            if names
            & {
                normalize_alias(value)
                for value in (candidate.title, candidate.slug, *candidate.aliases)
            }
        ),
        None,
    )


def _identity(
    context: IngestContext,
    title: str,
    slug: str,
    *,
    source_summary: bool = False,
) -> dict[str, object]:
    candidate = _matching_candidate(
        context, title, slug, source_summary=source_summary
    )
    if candidate is not None:
        return {
            "action": "update_page",
            "page_id": str(candidate.id),
            "expected_revision_no": candidate.revision_no,
        }
    return {
        "action": "create_page",
        "page_id": str(uuid.uuid5(context.source_id, normalize_slug(slug))),
    }


def _title(parsed: ParsedSource, filename: str) -> str:
    project = re.search(r"\bProject\s+[A-Z][\w-]*\b", parsed.text)
    if project:
        return project.group(0)
    heading = re.search(r"(?m)^#\s+(.+?)\s*$", parsed.text)
    if heading:
        return heading.group(1).strip()
    return PurePath(filename).stem.replace("-", " ").replace("_", " ").strip().title()


def _segment_for(parsed: ParsedSource, text: str | None = None) -> SourceSegment:
    if text:
        for segment in parsed.segments:
            if text in segment.text:
                return segment
    return parsed.segments[0]


def build_mock_ingest_batch(
    context: IngestContext,
    parsed: ParsedSource,
) -> WikiOperationBatch:
    title = _title(parsed, context.source_filename)
    topic_slug = normalize_slug(title)
    topic_segment = _segment_for(parsed, title)
    topic_aliases = (
        [f"{title.removeprefix('Project ')} Project"]
        if title.startswith("Project ")
        else []
    )

    leader_match = re.search(
        r"(?:项目负责人(?:是|为)|project\s+lead\s+is)\s*([A-Za-z][\w.-]*)",
        parsed.text,
        flags=re.IGNORECASE,
    )
    extracted: list[dict[str, object]] = []
    topic_links: list[dict[str, object]] = []
    if leader_match:
        leader = leader_match.group(1)
        leader_slug = normalize_slug(leader)
        leader_segment = _segment_for(parsed, leader_match.group(0))
        extracted.append(
            {
                **_identity(context, leader, leader_slug),
                "title": leader,
                "slug": leader_slug,
                "page_type": "entity",
                "aliases": [],
                "summary": f"{title} 的项目负责人。",
                "markdown": f"# {leader}\n\n{leader} 是 [[{topic_slug}]] 的项目负责人。",
                "change_summary": "Record the project lead from the source.",
                "links": [{"target_slug": topic_slug, "type": "wikilink"}],
                "citations": [
                    {
                        "source_id": str(context.source_id),
                        "locator": leader_segment.locator,
                        "excerpt": leader_match.group(0),
                    }
                ],
            }
        )
        topic_links.append({"target_slug": leader_slug, "type": "wikilink"})

    topic_operation: dict[str, object] = {
        **_identity(context, title, topic_slug),
        "title": title,
        "slug": topic_slug,
        "page_type": "topic",
        "aliases": topic_aliases,
        "summary": f"从 {context.source_filename} 提取的主题。",
        "markdown": f"# {title}\n\n{topic_segment.text}",
        "change_summary": "Create or update the primary source topic.",
        "links": topic_links,
        "citations": [
            {
                "source_id": str(context.source_id),
                "locator": topic_segment.locator,
                "excerpt": topic_segment.text[:4000],
            }
        ],
    }
    extracted.insert(0, topic_operation)

    source_title = f"{context.source_filename} Source Summary"
    source_slug = normalize_slug(
        f"source-{PurePath(context.source_filename).stem}-{str(context.source_id)[:8]}"
    )
    summary_links = [
        {"target_slug": operation["slug"], "type": "derived_from"}
        for operation in extracted
    ]
    extracted_list = "\n".join(
        f"- [[{operation['slug']}]]" for operation in extracted
    )
    source_operation = {
        **_identity(
            context,
            source_title,
            source_slug,
            source_summary=True,
        ),
        "title": source_title,
        "slug": source_slug,
        "page_type": "source",
        "aliases": [],
        "summary": f"{context.source_filename} 的可追溯来源摘要。",
        "markdown": (
            f"# {source_title}\n\n## Summary\n\n{topic_segment.text}\n\n"
            f"## Extracted pages\n\n{extracted_list}\n\n"
            f"## Ingest metadata\n\n- Source ID: {context.source_id}\n"
            f"- Prompt: {context.prompt_version}\n- Job ID: {context.job_id}"
        ),
        "change_summary": "Create or update the source summary.",
        "links": summary_links,
        "citations": [
            {
                "source_id": str(context.source_id),
                "locator": topic_segment.locator,
                "excerpt": topic_segment.text[:4000],
            }
        ],
    }
    return WikiOperationBatch.model_validate(
        {
            "schema_version": context.schema_version,
            "source_id": str(context.source_id),
            "operations": [source_operation, *extracted],
        }
    )
