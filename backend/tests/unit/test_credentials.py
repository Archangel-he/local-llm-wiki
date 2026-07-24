import base64
import uuid

import pytest

from app.services.credentials import (
    AESGCMCredentialCipher,
    CredentialDecryptionError,
    CredentialEncryptionUnavailable,
    DisabledCredentialCipher,
)


def test_disabled_cipher_never_persists_plaintext():
    cipher = DisabledCredentialCipher()

    with pytest.raises(CredentialEncryptionUnavailable):
        cipher.encrypt("real-secret", uuid.uuid4())


def test_aes_gcm_cipher_round_trip_binds_profile_and_version():
    key = b"k" * 32
    profile_id = uuid.uuid4()
    cipher = AESGCMCredentialCipher(key, 7)

    encrypted = cipher.encrypt("real-secret", profile_id)

    assert encrypted.key_version == 7
    assert b"real-secret" not in encrypted.ciphertext
    assert cipher.decrypt(encrypted.ciphertext, 7, profile_id) == "real-secret"
    with pytest.raises(CredentialDecryptionError):
        cipher.decrypt(encrypted.ciphertext, 7, uuid.uuid4())
    with pytest.raises(CredentialDecryptionError):
        cipher.decrypt(encrypted.ciphertext, 6, profile_id)


def test_documented_key_encoding_is_urlsafe_base64():
    encoded = base64.urlsafe_b64encode(b"k" * 32).decode().rstrip("=")
    assert len(base64.urlsafe_b64decode(encoded + "=")) == 32
