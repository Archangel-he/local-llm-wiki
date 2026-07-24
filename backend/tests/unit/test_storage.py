from __future__ import annotations

import io

import pytest

from app.services.storage import (
    InvalidStorageKey,
    LocalStorage,
    StorageConflict,
    StorageHashMismatch,
    StorageLimitExceeded,
)


def test_content_addressed_write_is_idempotent(tmp_path):
    storage = LocalStorage(tmp_path)

    first = storage.put_immutable(io.BytesIO(b"hello wiki"))
    second = storage.put_immutable(io.BytesIO(b"hello wiki"))

    assert first == second
    assert storage.exists(first.storage_key)
    with storage.open(first.storage_key) as handle:
        assert handle.read() == b"hello wiki"


def test_explicit_key_cannot_be_overwritten(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.put_immutable(io.BytesIO(b"first"), "raw/fixed")

    with pytest.raises(StorageConflict):
        storage.put_immutable(io.BytesIO(b"second"), "raw/fixed")


@pytest.mark.parametrize("key", ["../secret", "/absolute", "raw/../../secret", r"raw\windows"])
def test_storage_rejects_unsafe_keys(tmp_path, key):
    storage = LocalStorage(tmp_path)

    with pytest.raises(InvalidStorageKey):
        storage.put_immutable(io.BytesIO(b"data"), key)


def test_storage_rejects_wrong_expected_hash(tmp_path):
    storage = LocalStorage(tmp_path)

    with pytest.raises(StorageHashMismatch):
        storage.put_immutable(io.BytesIO(b"data"), expected_sha256="0" * 64)

    assert not any(path.is_file() for path in tmp_path.rglob("*") if ".tmp" not in path.parts)


def test_archive_does_not_delete_raw_bytes(tmp_path):
    storage = LocalStorage(tmp_path)
    stored = storage.put_immutable(io.BytesIO(b"immutable"))

    storage.archive(stored.storage_key)

    assert storage.exists(stored.storage_key)


def test_storage_enforces_max_bytes_before_publish(tmp_path):
    storage = LocalStorage(tmp_path)

    with pytest.raises(StorageLimitExceeded):
        storage.put_immutable(io.BytesIO(b"12345"), max_bytes=4)

    assert not any(path.is_file() for path in tmp_path.rglob("*") if ".tmp" not in path.parts)
