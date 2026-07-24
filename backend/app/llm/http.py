"""Credential-safe HTTP normalization shared by real model adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from app.llm.errors import LLMAdapterError, LLMErrorCategory


def raise_for_safe_status(response: httpx.Response) -> None:
    status = response.status_code
    if 200 <= status < 300:
        return
    if 300 <= status < 400:
        category = LLMErrorCategory.ENDPOINT_BLOCKED
        message = "The model endpoint returned a disallowed redirect."
        retryable = False
    elif status in {401, 403}:
        category = LLMErrorCategory.AUTHENTICATION
        message = "The model endpoint rejected authentication."
        retryable = False
    elif status == 404:
        category = LLMErrorCategory.MODEL_NOT_FOUND
        message = "The configured model or endpoint was not found."
        retryable = False
    elif status == 429:
        category = LLMErrorCategory.RATE_LIMITED
        message = "The model endpoint is rate limited."
        retryable = True
    elif status in {408, 425} or status >= 500:
        category = LLMErrorCategory.UNAVAILABLE
        message = "The model endpoint is temporarily unavailable."
        retryable = True
    else:
        category = LLMErrorCategory.INVALID_RESPONSE
        message = "The model endpoint rejected the request."
        retryable = False
    raise LLMAdapterError(category, message, retryable=retryable)


def json_object(response: httpx.Response) -> Mapping[str, Any]:
    try:
        payload = response.json()
    except (ValueError, TypeError):
        raise LLMAdapterError(
            LLMErrorCategory.INVALID_RESPONSE,
            "The model endpoint returned invalid JSON.",
            retryable=True,
        ) from None
    if not isinstance(payload, Mapping):
        raise LLMAdapterError(
            LLMErrorCategory.INVALID_RESPONSE,
            "The model endpoint returned an invalid response shape.",
            retryable=True,
        )
    return payload


def normalize_network_error(exc: Exception) -> LLMAdapterError:
    if isinstance(exc, httpx.TimeoutException):
        return LLMAdapterError(
            LLMErrorCategory.TIMEOUT,
            "The model request timed out.",
            retryable=True,
        )
    return LLMAdapterError(
        LLMErrorCategory.UNAVAILABLE,
        "The model endpoint could not be reached.",
        retryable=True,
    )
