from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import BinaryIO

from ..config import settings


class LocalStorage:
    """Local filesystem storage adapter for MVP 0."""

    def __init__(self) -> None:
        self.root = Path(settings.local_storage_path)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_immutable(self, stream: BinaryIO) -> tuple[str, str]:
        """Write stream to storage, return (storage_key, sha256)."""
        sha256 = hashlib.sha256()
        data = stream.read()
        sha256.update(data)
        digest = sha256.hexdigest()

        # Content-addressed key
        key = f"raw/{digest[:2]}/{digest[2:4]}/{digest}"
        full_path = self.root / key
        if not full_path.exists():
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)

        return key, digest

    def open(self, storage_key: str) -> bytes:
        full_path = self.root / storage_key
        return full_path.read_bytes()

    def exists(self, storage_key: str) -> bool:
        return (self.root / storage_key).exists()

    def delete(self, storage_key: str) -> None:
        path = self.root / storage_key
        if path.exists():
            path.unlink()


def get_storage() -> LocalStorage:
    return LocalStorage()
