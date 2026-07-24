"""Compatibility bridge to the provider-neutral LLM package.

New code should import from :mod:`app.llm` directly. Keeping this module
prevents A/B branches from retaining a second Ollama-specific implementation.
"""

from __future__ import annotations

from app.llm import LLMAdapter, RuntimeModelProfile, create_adapter


def get_llm(profile: RuntimeModelProfile) -> LLMAdapter:
    """Return the adapter authorized for one runtime profile."""

    return create_adapter(profile.provider)


__all__ = ["LLMAdapter", "RuntimeModelProfile", "get_llm"]
