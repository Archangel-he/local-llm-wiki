"""Integration seam for the API health aggregator owned by role A."""

from __future__ import annotations

from collections.abc import Callable

from app.llm.base import LLMAdapter
from app.llm.errors import LLMAdapterError
from app.llm.factory import create_adapter
from app.llm.types import LLMHealth, LLMHealthStatus, RuntimeModelProfile


async def probe_default_llm(
    profile: RuntimeModelProfile | None,
    *,
    adapter_factory: Callable[[str], LLMAdapter] = create_adapter,
) -> LLMHealth:
    """Probe exactly one default profile without failing the overall API.

    Loading and authorizing the profile remains the responsibility of the data
    layer.  This helper intentionally has no list-of-profiles input, preventing
    a health request from probing every user endpoint.
    """

    if profile is None:
        return LLMHealth(
            LLMHealthStatus.UNAVAILABLE,
            safe_reason="default_profile_missing",
        )
    try:
        adapter = adapter_factory(profile.provider.value)
        return await adapter.health(profile)
    except (LLMAdapterError, ValueError):
        return LLMHealth(
            LLMHealthStatus.UNAVAILABLE,
            safe_reason="health_probe_failed",
        )
