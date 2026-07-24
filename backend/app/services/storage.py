from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

from ..config import settings

CHUNK_SIZE = 1024 * 1024


class StorageError(RuntimeError):
    """Base error safe for translation to a stable API code."""


class InvalidStorageKey(StorageError):
    pass


class StorageConflict(StorageError):
    pass


class StorageHashMismatch(StorageError):
    pass


@dataclass(frozen=True)
class StoredObject:
    storage_key: str
    sha256: str
    size_bytes: int


class Storage(Protocol):
    def put_immutable(
        self,
        stream: BinaryIO,
        storage_key: str | None = None,
        expected_sha256: str | None = None,
    ) -> StoredObject: ...

    def open(self, storage_key: str) -> BinaryIO: ...

    def exists(self, storage_key: str) -> bool: ...

    def archive(self, storage_key: str) -> None: ...

    def health(self) -> bool: ...


class LocalStorage:
    """Content-addressed, immutable local filesystem storage."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or settings.local_storage_path).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.temp_root = self.root / ".tmp"
        self.temp_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_key(storage_key: str) -> PurePosixPath:
        if not storage_key or "\\" in storage_key:
            raise InvalidStorageKey("Storage key must be a non-empty POSIX path")
        key = PurePosixPath(storage_key)
        if key.is_absolute() or any(part in {"", ".", ".."} for part in key.parts):
            raise InvalidStorageKey("Storage key escapes the storage root")
        return key

    def _path_for(self, storage_key: str) -> Path:
        key = self._validate_key(storage_key)
        path = self.root.joinpath(*key.parts).resolve(strict=False)
        if not path.is_relative_to(self.root):
            raise InvalidStorageKey("Storage key escapes the storage root")
        return path

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def put_immutable(
        self,
        stream: BinaryIO,
        storage_key: str | None = None,
        expected_sha256: str | None = None,
    ) -> StoredObject:
        digest = hashlib.sha256()
        size_bytes = 0
        temp_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.temp_root, prefix="upload-", delete=False
            ) as temp:
                temp_path = Path(temp.name)
                while True:
                    chunk = stream.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    if not isinstance(chunk, bytes):
                        raise TypeError("Storage stream must return bytes")
                    temp.write(chunk)
                    digest.update(chunk)
                    size_bytes += len(chunk)
                temp.flush()
                os.fsync(temp.fileno())

            actual_sha256 = digest.hexdigest()
            if expected_sha256 and actual_sha256.lower() != expected_sha256.lower():
                raise StorageHashMismatch("Uploaded bytes do not match expected SHA-256")

            key = storage_key or (f"raw/{actual_sha256[:2]}/{actual_sha256[2:4]}/{actual_sha256}")
            target = self._path_for(key)
            target.parent.mkdir(parents=True, exist_ok=True)

            try:
                # A hard link publishes the completed temporary file atomically and
                # fails rather than replacing an existing immutable object.
                os.link(temp_path, target)
            except FileExistsError:
                if not target.is_file() or self._sha256_file(target) != actual_sha256:
                    raise StorageConflict("Storage key already exists with different content")

            return StoredObject(
                storage_key=key,
                sha256=actual_sha256,
                size_bytes=size_bytes,
            )
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def open(self, storage_key: str) -> BinaryIO:
        return self._path_for(storage_key).open("rb")

    def exists(self, storage_key: str) -> bool:
        return self._path_for(storage_key).is_file()

    def archive(self, storage_key: str) -> None:
        """Validate that an immutable object exists; Source status lives in PostgreSQL."""
        if not self.exists(storage_key):
            raise FileNotFoundError(storage_key)

    def health(self) -> bool:
        return (
            self.root.is_dir() and os.access(self.root, os.R_OK) and os.access(self.root, os.W_OK)
        )


def get_storage() -> LocalStorage:
    return LocalStorage()
