"""Provider-neutral LLM contracts and MVP0 adapters."""

from app.llm.base import LLMAdapter
from app.llm.bootstrap import bootstrap_runtime_profile
from app.llm.errors import LLMAdapterError, LLMErrorCategory
from app.llm.factory import create_adapter
from app.llm.mock import MockLLMAdapter, MockScenario
from app.llm.types import (
    ChatMessage,
    ConnectionTestResult,
    GenerationOptions,
    LLMHealth,
    LLMHealthStatus,
    ModelProvider,
    RuntimeModelProfile,
    StreamChunk,
    StreamChunkType,
    StructuredResponse,
)

__all__ = [
    "ChatMessage",
    "ConnectionTestResult",
    "GenerationOptions",
    "LLMAdapter",
    "LLMAdapterError",
    "LLMErrorCategory",
    "LLMHealth",
    "LLMHealthStatus",
    "MockLLMAdapter",
    "MockScenario",
    "ModelProvider",
    "RuntimeModelProfile",
    "StreamChunk",
    "StreamChunkType",
    "StructuredResponse",
    "bootstrap_runtime_profile",
    "create_adapter",
]
