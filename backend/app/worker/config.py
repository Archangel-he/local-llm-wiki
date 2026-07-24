"""Small environment boundary for the worker process."""

from __future__ import annotations

from collections.abc import Mapping

DEFAULT_REDIS_URL = "redis://redis:6379/0"
DEFAULT_QUEUE_NAME = "default"


def redis_url(environ: Mapping[str, str]) -> str:
    value = environ.get("REDIS_URL", DEFAULT_REDIS_URL).strip()
    if not value:
        raise ValueError("REDIS_URL must not be empty")
    return value


def queue_name(environ: Mapping[str, str]) -> str:
    value = environ.get("RQ_QUEUE_NAME", DEFAULT_QUEUE_NAME).strip()
    if value != DEFAULT_QUEUE_NAME:
        raise ValueError("MVP0 worker only supports the default queue")
    return value
