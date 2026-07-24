"""Synchronous RQ orchestration for one MVP 1 ingest Job."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable

from sqlalchemy import select

from app.database import SessionLocal
from app.ingest.context import (
    IngestContextError,
    build_ingest_context,
    load_source_input,
)
from app.ingest.mock_planner import build_mock_ingest_batch
from app.ingest.parser import SourceParseError, parse_source
from app.ingest.prompts import build_ingest_messages
from app.ingest.validation import IngestValidationError, validate_ingest_batch
from app.llm.base import LLMAdapter
from app.llm.errors import LLMAdapterError, LLMErrorCategory
from app.llm.factory import create_adapter
from app.llm.mock import MockLLMAdapter, MockScenario
from app.llm.types import GenerationOptions, ModelProvider
from app.models import Job
from app.schemas.wiki import WikiOperationBatch
from app.seed import DEFAULT_USER_ID
from app.services.content import enqueue_ingest_job
from app.services.credentials import (
    CredentialDecryptionError,
    CredentialEncryptionUnavailable,
)
from app.services.job_state import (
    InvalidJobTransition,
    cancellation_requested,
    claim_ingest_job,
    fail_job,
    update_job_progress,
)
from app.services.storage import StorageError, get_storage
from app.services.wiki import (
    AliasConflict,
    RevisionConflict,
    WikiCommitError,
    apply_wiki_operations,
)

LOGGER = logging.getLogger("wiki.ingest")
AdapterFactory = Callable[[str], LLMAdapter]


class IngestCancelled(RuntimeError):
    pass


def _progress(
    job_id: uuid.UUID,
    percent: int,
    stage: str,
    *,
    current: int,
    total: int,
) -> None:
    with SessionLocal() as db:
        update_job_progress(
            db,
            job_id,
            percent=percent,
            stage=stage,
            current=current,
            total=total,
        )


def _check_cancelled(job_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        requested = cancellation_requested(db, job_id)
    if not requested:
        return
    with SessionLocal() as db:
        job = db.scalar(select(Job).where(Job.id == job_id))
        if job is not None and job.status == "cancel_requested":
            fail_job(
                db,
                job_id,
                error_code="CANCELLED",
                safe_message="The ingest job was cancelled.",
                retryable=False,
            )
    raise IngestCancelled("The ingest job was cancelled.")


def _failure_details(exc: Exception) -> tuple[str, str, bool]:
    if isinstance(exc, LLMAdapterError):
        return f"LLM_{exc.category.value.upper()}", exc.safe_message, exc.retryable
    if isinstance(exc, SourceParseError):
        return exc.code, str(exc), exc.retryable
    if isinstance(exc, IngestValidationError):
        return exc.code, str(exc), exc.retryable
    if isinstance(exc, IngestContextError):
        return exc.code, str(exc), exc.retryable
    if isinstance(exc, RevisionConflict):
        return exc.code, "The Wiki changed while the job was running.", True
    if isinstance(exc, AliasConflict):
        return exc.code, "A generated title or alias conflicts with an existing page.", True
    if isinstance(exc, WikiCommitError):
        return exc.code, "The generated Wiki changes could not be committed.", True
    if isinstance(exc, (CredentialEncryptionUnavailable, CredentialDecryptionError)):
        return "MODEL_CREDENTIAL_UNAVAILABLE", "The model credential is unavailable.", False
    if isinstance(exc, StorageError):
        return "STORAGE_UNAVAILABLE", "The source content is unavailable.", True
    return "INGEST_INTERNAL_ERROR", "The ingest job failed unexpectedly.", True


def _record_failure(job_id: uuid.UUID, exc: Exception) -> None:
    code, message, retryable = _failure_details(exc)
    with SessionLocal() as db:
        try:
            job = fail_job(
                db,
                job_id,
                error_code=code,
                safe_message=message,
                retryable=retryable,
            )
        except InvalidJobTransition:
            return
        if job.status == "retrying":
            enqueue_ingest_job(db, job)


def _adapter_for_context(
    context,
    parsed,
    adapter_factory: AdapterFactory,
) -> LLMAdapter:
    adapter = adapter_factory(context.runtime_profile.provider.value)
    if (
        context.runtime_profile.provider is ModelProvider.MOCK
        and isinstance(adapter, MockLLMAdapter)
        and adapter.scenario is MockScenario.OK
    ):
        batch = build_mock_ingest_batch(context, parsed)
        return MockLLMAdapter(structured_data=batch.model_dump(mode="json"))
    return adapter


def run_ingest_job(
    job_id: str | uuid.UUID,
    *,
    adapter_factory: AdapterFactory = create_adapter,
) -> None:
    try:
        resolved_job_id = uuid.UUID(str(job_id))
    except (TypeError, ValueError):
        LOGGER.error("ingest_rejected reason=invalid_job_id")
        return
    try:
        with SessionLocal() as db:
            claim_ingest_job(db, resolved_job_id)
        _check_cancelled(resolved_job_id)

        _progress(resolved_job_id, 10, "parsing", current=0, total=1)
        with SessionLocal() as db:
            source_input = load_source_input(db, resolved_job_id)
        with get_storage().open(source_input.storage_key) as handle:
            parsed = parse_source(handle.read())
        _check_cancelled(resolved_job_id)

        _progress(resolved_job_id, 30, "loading_context", current=0, total=1)
        with SessionLocal() as db:
            context = build_ingest_context(db, resolved_job_id)
        _check_cancelled(resolved_job_id)

        _progress(resolved_job_id, 45, "calling_model", current=0, total=1)
        adapter = _adapter_for_context(context, parsed, adapter_factory)
        response = asyncio.run(
            adapter.generate_structured(
                context.runtime_profile,
                WikiOperationBatch.model_json_schema(),
                build_ingest_messages(context, parsed),
                GenerationOptions(temperature=0.0),
            )
        )
        _check_cancelled(resolved_job_id)

        _progress(resolved_job_id, 70, "validating", current=0, total=1)
        batch = validate_ingest_batch(response.data, context, parsed)
        _check_cancelled(resolved_job_id)

        _progress(resolved_job_id, 90, "committing", current=0, total=1)
        with SessionLocal() as db:
            apply_wiki_operations(
                db,
                context.workspace_id,
                context.job_id,
                DEFAULT_USER_ID,
                batch,
            )
    except (InvalidJobTransition, IngestCancelled):
        return
    except Exception as exc:  # boundary: normalize every Worker failure
        LOGGER.error(
            "ingest_failed job_id=%s exception_type=%s",
            resolved_job_id,
            type(exc).__name__,
        )
        _record_failure(resolved_job_id, exc)


def llm_error_is_retryable(category: LLMErrorCategory) -> bool:
    """Stable policy helper used by tests and future recovery tooling."""

    return category in {
        LLMErrorCategory.UNAVAILABLE,
        LLMErrorCategory.TIMEOUT,
        LLMErrorCategory.RATE_LIMITED,
        LLMErrorCategory.INVALID_RESPONSE,
    }
