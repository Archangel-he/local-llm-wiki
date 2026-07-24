"""Safe data types shared by every LLM adapter.

The runtime profile deliberately is not a dataclass or a Pydantic model.  Its
credential must not accidentally appear in generic serializers such as
``dataclasses.asdict`` or ``model_dump``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlsplit


class ModelProvider(StrEnum):
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"


class LLMHealthStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"


class StreamChunkType(StrEnum):
    TOKEN = "token"
    DONE = "done"


class RuntimeModelProfile:
    """An authorized, in-memory model configuration.

    The B/data layer is responsible for loading, authorizing, validating and
    decrypting this value.  Adapters only consume it.  ``credential`` is
    intentionally private, excluded from repr, and omitted from snapshots.
    """

    __slots__ = (
        "__credential",
        "base_url",
        "model_name",
        "profile_id",
        "provider",
    )

    def __init__(
        self,
        *,
        profile_id: str,
        provider: ModelProvider | str,
        base_url: str,
        model_name: str,
        credential: str | None = None,
    ) -> None:
        resolved_profile_id = str(profile_id).strip()
        resolved_base_url = base_url.strip()
        resolved_model_name = model_name.strip()
        if not resolved_profile_id:
            raise ValueError("profile_id must not be empty")

        parts = urlsplit(resolved_base_url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        if parts.username is not None or parts.password is not None:
            raise ValueError("base_url must not contain user information")
        if parts.query or parts.fragment:
            raise ValueError("base_url must not contain a query or fragment")
        try:
            _ = parts.port
        except ValueError as exc:
            raise ValueError("base_url contains an invalid port") from exc
        if not resolved_model_name:
            raise ValueError("model_name must not be empty")

        self.profile_id = resolved_profile_id
        self.provider = ModelProvider(provider)
        self.base_url = resolved_base_url
        self.model_name = resolved_model_name
        self.__credential = credential

    def __repr__(self) -> str:
        return (
            "RuntimeModelProfile("
            f"profile_id={self.profile_id!r}, "
            f"provider={self.provider.value!r}, "
            f"endpoint_origin={self.endpoint_origin!r}, "
            f"model_name={self.model_name!r}, "
            f"has_credential={self.__credential is not None})"
        )

    @property
    def endpoint_origin(self) -> str:
        """Return a credential-free origin suitable for logs and API output."""

        parts = urlsplit(self.base_url)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def credential(self) -> str | None:
        """Return the secret only to the adapter at the point of use."""

        return self.__credential

    def safe_snapshot(self, *, adapter_version: str) -> dict[str, Any]:
        """Return a JSON-serializable, credential-free audit snapshot."""

        return {
            "profile_id": self.profile_id,
            "provider": self.provider.value,
            "endpoint_origin": self.endpoint_origin,
            "model_name": self.model_name,
            "adapter_version": adapter_version,
        }


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class GenerationOptions:
    temperature: float = 0.0
    max_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class LLMHealth:
    status: LLMHealthStatus
    latency_ms: int | None = None
    safe_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    reachable: bool
    model_found: bool
    streaming_supported: bool
    structured_output_supported: bool
    latency_ms: int | None = None
    safe_reason: str | None = None


@dataclass(frozen=True, slots=True)
class StructuredResponse:
    data: Mapping[str, Any]
    model_name: str
    usage: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StreamChunk:
    type: StreamChunkType
    sequence: int
    text: str = ""
