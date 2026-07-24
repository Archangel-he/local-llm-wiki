"""MVP0 real-provider skeletons."""

from app.llm.providers.ollama import OllamaAdapter
from app.llm.providers.openai_compatible import OpenAICompatibleAdapter

__all__ = ["OllamaAdapter", "OpenAICompatibleAdapter"]
