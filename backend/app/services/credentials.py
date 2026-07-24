from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class CredentialEncryptionUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class EncryptedCredential:
    ciphertext: bytes
    key_version: int


class CredentialCipher(Protocol):
    """Boundary for a future authenticated-encryption implementation.

    MVP 0 never stores a real API key. A no-op or Base64 implementation is
    intentionally not provided because either would silently persist plaintext.
    """

    def encrypt(self, plaintext: str) -> EncryptedCredential: ...

    def decrypt(self, ciphertext: bytes, key_version: int) -> str: ...


class DisabledCredentialCipher:
    def encrypt(self, plaintext: str) -> EncryptedCredential:
        raise CredentialEncryptionUnavailable(
            "Credential persistence is disabled until encryption is configured"
        )

    def decrypt(self, ciphertext: bytes, key_version: int) -> str:
        raise CredentialEncryptionUnavailable(
            "Credential persistence is disabled until encryption is configured"
        )
