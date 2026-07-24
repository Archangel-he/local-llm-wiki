from __future__ import annotations

import uuid

import pytest

from app.services.model_profiles import InvalidModelProfile, normalize_base_url
from app.services.wiki import normalize_alias, normalize_slug


def test_wiki_identifiers_are_normalized_deterministically():
    assert normalize_alias("  Aurora  PROJECT ") == "aurora project"
    assert normalize_alias("极光项目") == "极光项目"
    assert normalize_slug(" Project Aurora ") == "project-aurora"


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@example.com/v1",
        "https://example.com/v1?api_key=secret",
        "https://example.com/v1#secret",
        "file:///tmp/model",
    ],
)
def test_model_profile_rejects_credential_bearing_or_non_http_urls(url):
    with pytest.raises(InvalidModelProfile):
        normalize_base_url(url)


def test_operation_ids_are_uuid_compatible():
    assert str(uuid.UUID(str(uuid.uuid4())))
