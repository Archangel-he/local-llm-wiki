"""Deterministic Markdown/TXT parsing for MVP 1."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import settings


class SourceParseError(ValueError):
    code = "SOURCE_PARSE_FAILED"
    retryable = False


class EmptySource(SourceParseError):
    code = "EMPTY_SOURCE"


class SourceTooLargeForModel(SourceParseError):
    code = "SOURCE_TOO_LARGE_FOR_MODEL"


@dataclass(frozen=True, slots=True)
class SourceSegment:
    locator: str
    start_line: int
    end_line: int
    text: str


@dataclass(frozen=True, slots=True)
class ParsedSource:
    text: str
    segments: tuple[SourceSegment, ...]

    @property
    def locators(self) -> dict[str, SourceSegment]:
        return {segment.locator: segment for segment in self.segments}


def parse_source(
    content: bytes | str,
    *,
    max_chars: int | None = None,
) -> ParsedSource:
    """Normalize text and split non-empty blocks into stable line locators."""

    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SourceParseError("The source is not valid UTF-8.") from exc
    else:
        text = content.removeprefix("\ufeff")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    limit = max_chars if max_chars is not None else settings.ingest_max_source_chars
    if len(normalized) > limit:
        raise SourceTooLargeForModel(
            f"The parsed source exceeds the {limit}-character MVP 1 model limit."
        )
    if not normalized.strip():
        raise EmptySource("The source contains no readable text.")

    lines = normalized.split("\n")
    segments: list[SourceSegment] = []
    block_start: int | None = None
    block_lines: list[str] = []
    for index, line in enumerate(lines, start=1):
        if re.match(r"^\s{0,3}#{1,6}(?:\s|$)", line):
            if block_start is not None:
                segments.append(_segment(block_start, index - 1, block_lines))
                block_start = None
                block_lines = []
            segments.append(_segment(index, index, [line]))
            continue
        if line.strip():
            if block_start is None:
                block_start = index
            block_lines.append(line)
            continue
        if block_start is not None:
            segments.append(_segment(block_start, index - 1, block_lines))
            block_start = None
            block_lines = []
    if block_start is not None:
        segments.append(_segment(block_start, len(lines), block_lines))
    return ParsedSource(text=normalized, segments=tuple(segments))


def _segment(start_line: int, end_line: int, lines: list[str]) -> SourceSegment:
    return SourceSegment(
        locator=f"lines:{start_line}-{end_line}",
        start_line=start_line,
        end_line=end_line,
        text="\n".join(lines),
    )
