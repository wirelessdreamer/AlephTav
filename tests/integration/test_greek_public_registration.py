from __future__ import annotations

import json

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api import mcp_server
from app.api.main import app
from app.core.errors import NotFoundError
from app.services import greek_study_service

pytestmark = pytest.mark.no_seeded_repo


def test_mounted_greek_routes_have_mcp_coverage_and_default_unavailable(monkeypatch) -> None:
    def missing(*args):
        raise NotFoundError("No active study snapshot")

    monkeypatch.setattr(greek_study_service, "load_public_view", missing)
    routes = {
        route.endpoint
        for route in app.routes
        if isinstance(route, APIRoute) and route.endpoint.__module__ == "app.api.routes.greek_study"
    }
    assert len(routes) == 8
    assert routes <= mcp_server.COVERED
    assert not routes & mcp_server.EXCLUDED
    response = TestClient(app).get("/lxx/editions")
    assert response.status_code == 200
    assert response.json()["editions"] == []
    assert json.loads(mcp_server.list_greek_editions())["editions"] == []
