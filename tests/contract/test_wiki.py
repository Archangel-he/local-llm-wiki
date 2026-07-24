from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestWikiContract:
    WORKSPACE_ID = "00000000-0000-0000-0000-000000000002"
    PAGE_TYPES = ("topic", "entity", "source", "analysis", "question")
    LINK_TYPES = ("wikilink", "citation", "derived_from")

    @pytest.fixture(autouse=True)
    def _skip_if_not_implemented(self):
        resp = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/wiki")
        if resp.status_code in (404, 405):
            pytest.skip("Wiki API not implemented")

    def test_list_pages_returns_array(self):
        resp = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/wiki")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_page_has_required_fields(self):
        pages = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/wiki").json()
        if not pages:
            pytest.skip("No pages")
        p = pages[0]
        assert "id" in p and "title" in p and "slug" in p
        assert "page_type" in p and p["page_type"] in self.PAGE_TYPES

    def test_get_page_returns_markdown(self):
        pages = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/wiki").json()
        if not pages:
            pytest.skip("No pages")
        detail = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/wiki/{pages[0]['id']}")
        assert detail.status_code == 200
        assert "markdown" in detail.json()

    def test_graph_returns_nodes_and_edges(self):
        resp = client.get(f"/api/workspaces/{self.WORKSPACE_ID}/graph")
        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body and "edges" in body
        assert isinstance(body["nodes"], list)
        assert isinstance(body["edges"], list)
