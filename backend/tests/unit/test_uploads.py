from __future__ import annotations

import io

import pytest

from app.services.storage import LocalStorage
from app.services.uploads import (
    InvalidTextEncoding,
    UnsupportedFileType,
    UploadTooLarge,
    prepare_upload,
    safe_filename,
)


def test_prepare_markdown_upload_is_utf8_and_content_addressed(tmp_path):
    storage = LocalStorage(tmp_path)

    upload = prepare_upload(
        io.BytesIO("# 极光\n".encode()),
        "notes/极光 plan.md",
        "text/markdown; charset=utf-8",
        storage,
        max_bytes=1024,
    )

    assert upload.original_filename == "极光 plan.md"
    assert upload.safe_filename == "极光-plan.md"
    assert upload.mime_type == "text/markdown"
    assert upload.stored.size_bytes == len("# 极光\n".encode())
    with storage.open(upload.stored.storage_key) as handle:
        assert handle.read() == "# 极光\n".encode()


@pytest.mark.parametrize("filename", ["payload.pdf", "payload", "payload.md.exe", "\x00.md"])
def test_upload_rejects_unsupported_or_unsafe_names(filename):
    with pytest.raises(UnsupportedFileType):
        safe_filename(filename)


def test_upload_rejects_invalid_utf8_before_publishing(tmp_path):
    storage = LocalStorage(tmp_path)

    with pytest.raises(InvalidTextEncoding):
        prepare_upload(
            io.BytesIO(b"\xff\xfe"),
            "bad.txt",
            "text/plain",
            storage,
            max_bytes=1024,
        )

    assert not any(path.is_file() for path in tmp_path.rglob("*") if ".tmp" not in path.parts)


def test_upload_enforces_streaming_byte_limit(tmp_path):
    storage = LocalStorage(tmp_path)

    with pytest.raises(UploadTooLarge):
        prepare_upload(
            io.BytesIO(b"12345"),
            "large.txt",
            "text/plain",
            storage,
            max_bytes=4,
        )
