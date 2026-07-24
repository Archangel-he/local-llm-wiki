import json

from app.main import app


def test_openapi_never_exposes_credential_storage_fields():
    schema = json.dumps(app.openapi())

    assert "credential_ciphertext" not in schema
    assert "credential_key_version" not in schema
