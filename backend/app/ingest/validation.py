"""C-side validation before the B-owned atomic Wiki commit."""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Mapping

from pydantic import ValidationError

from app.ingest.context import ExistingPageCandidate, IngestContext
from app.ingest.parser import ParsedSource
from app.schemas.wiki import WikiOperationBatch
from app.services.wiki import AliasConflict, normalize_alias, normalize_slug

MARKDOWN_SOURCE_PATTERN = re.compile(
    r"source:(?P<source>[0-9a-fA-F-]{36})#(?P<locator>lines:\d+-\d+)"
)


class IngestValidationError(ValueError):
    code = "SCHEMA_VALIDATION_FAILED"
    retryable = True


def _candidate_names(candidate: ExistingPageCandidate) -> set[str]:
    return {
        normalize_alias(value)
        for value in (candidate.title, candidate.slug, *candidate.aliases)
    }


def _compact(value: str) -> str:
    return unicodedata.normalize("NFKC", " ".join(value.split()))


def validate_ingest_batch(
    data: Mapping[str, object],
    context: IngestContext,
    parsed: ParsedSource,
) -> WikiOperationBatch:
    try:
        batch = WikiOperationBatch.model_validate(data)
    except ValidationError as exc:
        raise IngestValidationError("The model output does not match the ingest schema.") from exc
    if batch.schema_version != context.schema_version or batch.source_id != context.source_id:
        raise IngestValidationError("The model output targets the wrong schema or source.")
    source_operations = [op for op in batch.operations if op.page_type == "source"]
    if len(source_operations) != 1:
        raise IngestValidationError("Exactly one Source Summary operation is required.")

    candidates_by_id = {candidate.id: candidate for candidate in context.existing_pages}
    existing_source_summary = next(
        (
            candidate
            for candidate in context.existing_pages
            if candidate.primary_source_id == context.source_id
        ),
        None,
    )
    source_operation = source_operations[0]
    if existing_source_summary is None and source_operation.action != "create_page":
        raise IngestValidationError("A new Source Summary must use create_page.")
    if existing_source_summary is not None and (
        source_operation.page_id != existing_source_summary.id
        or source_operation.expected_revision_no != existing_source_summary.revision_no
        or source_operation.action not in {"update_page", "mark_page_for_review"}
    ):
        raise IngestValidationError("The existing Source Summary must be updated in place.")

    declared_pages: set[uuid.UUID] = set()
    declared_slugs: set[str] = set()
    declared_names: set[str] = set()
    other_slugs = {normalize_slug(op.slug) for op in batch.operations if op is not source_operation}
    summary_targets = {normalize_slug(link.target_slug) for link in source_operation.links}
    if not other_slugs.issubset(summary_targets):
        raise IngestValidationError("The Source Summary must link to every extracted page.")

    locator_map = parsed.locators
    for operation in batch.operations:
        slug = normalize_slug(operation.slug)
        try:
            base_names = {
                normalize_alias(operation.title),
                normalize_alias(operation.slug),
            }
            normalized_aliases = [
                normalize_alias(value) for value in operation.aliases
            ]
        except AliasConflict as exc:
            raise IngestValidationError("A title, slug, or alias is empty.") from exc
        if (
            len(normalized_aliases) != len(set(normalized_aliases))
            or base_names & set(normalized_aliases)
        ):
            raise IngestValidationError("An operation contains duplicate aliases.")
        names = base_names | set(normalized_aliases)
        if slug in declared_slugs or names & declared_names:
            raise IngestValidationError("The batch contains duplicate pages or aliases.")
        declared_slugs.add(slug)
        declared_names.update(names)

        if operation.action in {"update_page", "mark_page_for_review"}:
            candidate = candidates_by_id.get(operation.page_id)
            if candidate is None or operation.expected_revision_no != candidate.revision_no:
                raise IngestValidationError("An update references an unknown or stale page.")
            if operation.page_id in declared_pages:
                raise IngestValidationError("The batch modifies the same page more than once.")
            declared_pages.add(operation.page_id)
        else:
            if operation.expected_revision_no is not None:
                raise IngestValidationError(
                    "A create operation must not declare an expected revision."
                )
            if operation.page_id is not None and (
                operation.page_id in declared_pages
                or operation.page_id in candidates_by_id
            ):
                raise IngestValidationError("A create operation reuses an existing page ID.")
            if operation.page_id is not None:
                declared_pages.add(operation.page_id)
            for candidate in context.existing_pages:
                if names & _candidate_names(candidate):
                    raise IngestValidationError(
                        "A create operation matches an existing title, slug, or alias."
                    )

        if operation.page_type != "question" and not operation.citations:
            raise IngestValidationError("Every factual page requires a citation.")
        declared_citations: set[tuple[uuid.UUID, str]] = set()
        for citation in operation.citations:
            if citation.source_id != context.source_id:
                raise IngestValidationError("A citation targets an unavailable source.")
            segment = locator_map.get(citation.locator)
            if segment is None:
                raise IngestValidationError("A citation locator does not exist in the source.")
            if citation.excerpt and _compact(citation.excerpt) not in _compact(segment.text):
                raise IngestValidationError("A citation excerpt is not supported by its locator.")
            declared_citations.add((citation.source_id, citation.locator))
        for match in MARKDOWN_SOURCE_PATTERN.finditer(operation.markdown):
            marker = (uuid.UUID(match.group("source")), match.group("locator"))
            if marker not in declared_citations:
                raise IngestValidationError(
                    "Markdown contains a source marker without a structured citation."
                )
        for link in operation.links:
            if link.evidence_source_id not in {None, context.source_id}:
                raise IngestValidationError("A link targets unavailable source evidence.")
            if link.type in {"related", "contradicts"} and (
                link.evidence_source_id != context.source_id
            ):
                raise IngestValidationError("An inferred link lacks source evidence.")
    return batch
