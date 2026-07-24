"""Versioned MVP 1 ingest prompt construction."""

from __future__ import annotations

import json

from app.ingest.context import IngestContext
from app.ingest.parser import ParsedSource
from app.llm.types import ChatMessage


def build_ingest_messages(
    context: IngestContext,
    parsed: ParsedSource,
) -> list[ChatMessage]:
    candidates = [
        {
            "id": str(candidate.id),
            "title": candidate.title,
            "slug": candidate.slug,
            "page_type": candidate.page_type,
            "aliases": list(candidate.aliases),
            "revision_no": candidate.revision_no,
            "summary": candidate.summary,
            "primary_source_id": (
                str(candidate.primary_source_id) if candidate.primary_source_id else None
            ),
        }
        for candidate in context.existing_pages
    ]
    source = {
        "source_id": str(context.source_id),
        "filename": context.source_filename,
        "mime_type": context.source_mime_type,
        "schema_version": context.schema_version,
        "prompt_version": context.prompt_version,
        "segments": [
            {"locator": segment.locator, "text": segment.text}
            for segment in parsed.segments
        ],
        "existing_pages": candidates,
    }
    system = (
        "You maintain a source-grounded Markdown Wiki. Return only JSON matching the "
        "provided schema. Use no facts outside the supplied source segments. Create or "
        "update exactly one page_type=source Source Summary, use existing page IDs and "
        "revision numbers when a title/slug/alias candidate matches, and attach at least "
        "one structured citation to every factual page. Citation locators and excerpts "
        "must exactly match supplied segments. Inferred related/contradicts links require "
        "evidence_source_id. Never delete pages or sources."
    )
    user = "<ingest_context>\n" + json.dumps(source, ensure_ascii=False) + "\n</ingest_context>"
    return [ChatMessage("system", system), ChatMessage("user", user)]
