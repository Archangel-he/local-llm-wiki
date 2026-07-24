from __future__ import annotations

import base64
import binascii
import os
import uuid
from dataclasses import dataclass
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import settings


class CredentialEncryptionUnavailable(RuntimeError):
    pass


class CredentialDecryptionError(RuntimeError):
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

    def encrypt(self, plaintext: str, profile_id: uuid.UUID) -> EncryptedCredential: ...

    def decrypt(self, ciphertext: bytes, key_version: int, profile_id: uuid.UUID) -> str: ...


class DisabledCredentialCipher:
    def encrypt(self, plaintext: str, profile_id: uuid.UUID) -> EncryptedCredential:
        raise CredentialEncryptionUnavailable(
            "Credential persistence is disabled until encryption is configured"
        )

    def decrypt(self, ciphertext: bytes, key_version: int, profile_id: uuid.UUID) -> str:
        raise CredentialEncryptionUnavailable(
            "Credential persistence is disabled until encryption is configured"
        )


class AESGCMCredentialCipher:
    NONCE_BYTES = 12

    def __init__(self, key: bytes, key_version: int) -> None:
        if len(key) != 32:
            raise ValueError("Credential encryption key must contain exactly 32 bytes")
        if key_version <= 0:
            raise ValueError("Credential key version must be positive")
        self._cipher = AESGCM(key)
        self._key_version = key_version

    @staticmethod
    def _aad(profile_id: uuid.UUID, key_version: int) -> bytes:
        return f"model-profile:{profile_id}:v{key_version}".encode()

    def encrypt(self, plaintext: str, profile_id: uuid.UUID) -> EncryptedCredential:
        if not plaintext:
            raise ValueError("Credential must not be empty")
        nonce = os.urandom(self.NONCE_BYTES)
        ciphertext = self._cipher.encrypt(
            nonce,
            plaintext.encode(),
            self._aad(profile_id, self._key_version),
        )
        return EncryptedCredential(nonce + ciphertext, self._key_version)

    def decrypt(self, ciphertext: bytes, key_version: int, profile_id: uuid.UUID) -> str:
        if key_version != self._key_version or len(ciphertext) <= self.NONCE_BYTES:
            raise CredentialDecryptionError("Credential cannot be decrypted with this key version")
        nonce, encrypted = ciphertext[: self.NONCE_BYTES], ciphertext[self.NONCE_BYTES :]
        try:
            plaintext = self._cipher.decrypt(
                nonce,
                encrypted,
                self._aad(profile_id, key_version),
            )
            return plaintext.decode()
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise CredentialDecryptionError("Credential authentication failed") from exc


def credential_cipher_from_settings() -> CredentialCipher:
    secret = settings.model_credential_key
    if secret is None or not secret.get_secret_value().strip():
        return DisabledCredentialCipher()
    encoded = secret.get_secret_value().strip()
    try:
        padding = "=" * (-len(encoded) % 4)
        key = base64.urlsafe_b64decode(encoded + padding)
    except (ValueError, binascii.Error) as exc:
        raise CredentialEncryptionUnavailable("Credential key is not valid Base64") from exc
    try:
        return AESGCMCredentialCipher(key, settings.model_credential_key_version)
    except ValueError as exc:
        raise CredentialEncryptionUnavailable(str(exc)) from exc
