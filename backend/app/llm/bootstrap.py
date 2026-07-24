"""Temporary configuration bridge used until persisted Model Profiles land."""

from __future__ import annotations

from app.llm.types import RuntimeModelProfile


def bootstrap_runtime_profile(
    *,
    provider: str,
    base_url: str,
    model_name: str,
) -> RuntimeModelProfile | None:
    """Build the MVP0 default profile from non-secret startup settings.

    B's data layer can replace this call with an authorized database loader
    without changing any provider adapter. Invalid or incomplete bootstrap
    configuration intentionally degrades health instead of crashing startup.
    """

    if not provider.strip() or not base_url.strip() or not model_name.strip():
        return None
    try:
        return RuntimeModelProfile(
            profile_id="bootstrap-default",
            provider=provider,
            base_url=base_url,
            model_name=model_name,
        )
    except ValueError:
        return None
