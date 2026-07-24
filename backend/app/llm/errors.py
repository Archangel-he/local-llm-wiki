"""Stable, credential-safe adapter errors."""

from __future__ import annotations

from enum import StrEnum


class LLMErrorCategory(StrEnum):
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    MODEL_NOT_FOUND = "model_not_found"
    RATE_LIMITED = "rate_limited"
    ENDPOINT_BLOCKED = "endpoint_blocked"
    INVALID_RESPONSE = "invalid_response"
    NOT_ENABLED = "not_enabled"


class LLMAdapterError(Exception):
    """An internal adapter failure safe enough to map to an API error.

    Upstream bodies, response headers, URLs and credentials must never be
    passed to this exception.
    """

    def __init__(
        self,
        category: LLMErrorCategory,
        safe_message: str,
        *,
        retryable: bool,
    ) -> None:
        super().__init__(safe_message)
        self.category = category
        self.safe_message = safe_message
        self.retryable = retryable

    def __repr__(self) -> str:
        return (
            f"LLMAdapterError(category={self.category.value!r}, "
            f"safe_message={self.safe_message!r}, retryable={self.retryable!r})"
        )
