from __future__ import annotations

import inspect

from app.ingest.pipeline import llm_error_is_retryable
from app.llm.errors import LLMErrorCategory
from app.worker.jobs import ingest_job


def test_public_rq_entry_accepts_only_a_job_id() -> None:
    signature = inspect.signature(ingest_job)
    assert list(signature.parameters) == ["job_id"]
    assert signature.return_annotation in {None, "None"}


def test_retry_policy_matches_mvp1_contract() -> None:
    retryable = {
        LLMErrorCategory.UNAVAILABLE,
        LLMErrorCategory.TIMEOUT,
        LLMErrorCategory.RATE_LIMITED,
        LLMErrorCategory.INVALID_RESPONSE,
    }
    assert {item for item in LLMErrorCategory if llm_error_is_retryable(item)} == retryable
