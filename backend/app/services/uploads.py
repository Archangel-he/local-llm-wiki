from __future__ import annotations

import codecs
import hashlib
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import BinaryIO

from .storage import CHUNK_SIZE, Storage, StoredObject

ALLOWED_EXTENSIONS = {".md", ".txt"}
ALLOWED_MIME_TYPES = {
    "application/octet-stream",
    "text/markdown",
    "text/plain",
    "text/x-markdown",
}


class UploadValidationError(ValueError):
    code = "VALIDATION_ERROR"


class UnsupportedFileType(UploadValidationError):
    code = "UNSUPPORTED_FILE_TYPE"


class UploadTooLarge(UploadValidationError):
    code = "FILE_TOO_LARGE"


class InvalidTextEncoding(UploadValidationError):
    code = "UNSUPPORTED_FILE_TYPE"


@dataclass(frozen=True)
class PreparedUpload:
    original_filename: str
    safe_filename: str
    mime_type: str
    stored: StoredObject


def safe_filename(filename: str) -> tuple[str, str]:
    if not filename or "\x00" in filename:
        raise UnsupportedFileType("A filename is required.")
    original = PurePosixPath(filename.replace("\\", "/")).name
    normalized = unicodedata.normalize("NFKC", original).strip()
    extension = PurePosixPath(normalized).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileType("Only UTF-8 Markdown and text files are supported.")

    stem = normalized[: -len(extension)].strip()
    stem = re.sub(r"[^\w.-]+", "-", stem, flags=re.UNICODE).strip("._-")
    if not stem:
        stem = "source"
    max_stem = 255 - len(extension)
    return original, f"{stem[:max_stem]}{extension}"


def normalized_mime_type(content_type: str | None, extension: str) -> str:
    candidate = (content_type or "").split(";", 1)[0].strip().lower()
    if candidate and candidate not in ALLOWED_MIME_TYPES:
        raise UnsupportedFileType("The uploaded MIME type is not supported.")
    if candidate in {"text/markdown", "text/x-markdown"} and extension != ".md":
        raise UnsupportedFileType("The filename extension does not match the MIME type.")
    return "text/markdown" if extension == ".md" else "text/plain"


def prepare_upload(
    stream: BinaryIO,
    filename: str,
    content_type: str | None,
    storage: Storage,
    max_bytes: int,
) -> PreparedUpload:
    original, safe = safe_filename(filename)
    mime_type = normalized_mime_type(content_type, PurePosixPath(safe).suffix)
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    digest = hashlib.sha256()
    size_bytes = 0

    with tempfile.SpooledTemporaryFile(max_size=min(max_bytes, 2 * 1024 * 1024)) as staged:
        try:
            while True:
                chunk = stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                if not isinstance(chunk, bytes):
                    raise TypeError("Upload stream must return bytes")
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise UploadTooLarge(f"The upload exceeds the {max_bytes}-byte limit.")
                decoder.decode(chunk, final=False)
                digest.update(chunk)
                staged.write(chunk)
            decoder.decode(b"", final=True)
        except UnicodeDecodeError as exc:
            raise InvalidTextEncoding("The uploaded file must be valid UTF-8.") from exc

        staged.seek(0)
        stored = storage.put_immutable(
            staged,
            expected_sha256=digest.hexdigest(),
            max_bytes=max_bytes,
        )

    return PreparedUpload(
        original_filename=original,
        safe_filename=safe,
        mime_type=mime_type,
        stored=stored,
    )
