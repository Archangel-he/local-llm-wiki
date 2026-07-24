from __future__ import annotations

import pytest

from app.ingest.parser import (
    EmptySource,
    SourceParseError,
    SourceTooLargeForModel,
    parse_source,
)


def test_markdown_crlf_and_chinese_produce_stable_line_locators() -> None:
    parsed = parse_source("# Aurora\r\n\r\n项目负责人是 Lin。\r\n状态：启动。")

    assert parsed.text == "# Aurora\n\n项目负责人是 Lin。\n状态：启动。"
    assert [(item.locator, item.text) for item in parsed.segments] == [
        ("lines:1-1", "# Aurora"),
        ("lines:3-4", "项目负责人是 Lin。\n状态：启动。"),
    ]


def test_utf8_bom_is_accepted_without_mutating_raw_storage() -> None:
    parsed = parse_source(b"\xef\xbb\xbfplain text")
    assert parsed.text == "plain text"
    assert parsed.segments[0].locator == "lines:1-1"


def test_markdown_heading_starts_its_own_segment_without_blank_lines() -> None:
    parsed = parse_source("intro\n## Details\nfirst line\nsecond line")
    assert [item.locator for item in parsed.segments] == [
        "lines:1-1",
        "lines:2-2",
        "lines:3-4",
    ]


@pytest.mark.parametrize("content", [b"", " \n\t"])
def test_empty_source_is_rejected(content: bytes | str) -> None:
    with pytest.raises(EmptySource):
        parse_source(content)


def test_invalid_utf8_is_rejected() -> None:
    with pytest.raises(SourceParseError) as captured:
        parse_source(b"\xff\xfe")
    assert captured.value.code == "SOURCE_PARSE_FAILED"


def test_source_is_not_silently_truncated() -> None:
    with pytest.raises(SourceTooLargeForModel) as captured:
        parse_source("12345", max_chars=4)
    assert captured.value.code == "SOURCE_TOO_LARGE_FOR_MODEL"
