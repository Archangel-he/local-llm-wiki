import pytest

from app.services.credentials import (
    CredentialEncryptionUnavailable,
    DisabledCredentialCipher,
)


def test_disabled_cipher_never_persists_plaintext():
    cipher = DisabledCredentialCipher()

    with pytest.raises(CredentialEncryptionUnavailable):
        cipher.encrypt("real-secret")
