from __future__ import annotations

# Mock LLM adapter for testing
# Returns fixed responses instead of calling Ollama

from typing import Any

MOCK_INGEST: dict[str, Any] = {
    "schema_version": 1,
    "source_id": "MOCK-SOURCE-ID",
    "operations": [
        {
            "action": "update_page",
            "page_id": None,
            "expected_revision_no": None,
            "title": "Project Aurora",
            "slug": "project-aurora",
            "page_type": "topic",
            "markdown": "# Project Aurora\n\nA test page.\n\nLead: [[lin]]\n",
            "change_summary": "Initial page",
            "links": [{"target_slug": "lin", "type": "wikilink"}],
            "citations": [],
            "conflicts": [],
        }
    ],
}


class MockLLM:
    def health(self) -> bool:
        return True

    def generate_structured(
        self, schema: dict, messages: list, options: dict | None = None
    ) -> dict[str, Any]:
        return MOCK_INGEST.copy()

    def stream(self, messages: list, options: dict | None = None):
        yield "mock token\n"


def get_mock_llm() -> MockLLM:
    return MockLLM()
