"""The workbench's MCP tools: every API operation, stamped as MCP work, refused as the API is."""

from __future__ import annotations

import json
from typing import Any

import anyio
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from mcp import Client

from app.api import mcp_server
from app.api.main import app
from app.core.config import get_settings
from app.services import registry_service

PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"


@pytest.fixture(autouse=True)
def _restore_psalm():
    get_settings().collections_file.unlink(missing_ok=True)
    meta = registry_service.load_psalm_meta(PSALM_ID)
    unit = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_psalm_meta(PSALM_ID, meta)
    registry_service.save_unit(unit)
    get_settings().collections_file.unlink(missing_ok=True)


def _calls(*steps: tuple[str, dict[str, Any]]) -> list[Any]:
    """Call tools in order, in-process; a result is its JSON, or ("error", text)."""

    async def run() -> list[Any]:
        results: list[Any] = []
        async with Client(mcp_server.server) as client:
            for name, arguments in steps:
                result = await client.call_tool(name, arguments)
                text = result.content[0].text
                results.append(("error", text) if result.is_error else json.loads(text))
        return results

    return anyio.run(run)


def _call(name: str, **arguments: Any) -> Any:
    return _calls((name, arguments))[0]


def test_every_api_route_is_a_tool_or_deliberately_left_out() -> None:
    routes = {
        route.endpoint
        for route in app.routes
        if isinstance(route, APIRoute) and route.endpoint.__module__.startswith("app.api.routes.")
    }
    missing = routes - mcp_server.COVERED - mcp_server.EXCLUDED
    assert not missing, sorted(f"{fn.__module__}.{fn.__name__}" for fn in missing)
    assert not mcp_server.COVERED & mcp_server.EXCLUDED


def test_an_outside_llm_writes_a_projects_translation_stamped_as_mcp() -> None:
    project = _call("create_project", title="Psalms for strings", created_by="claude")
    translation = _call(
        "create_translation",
        psalm_id=PSALM_ID,
        title="Psalms for strings",
        collection_id=project["collection_id"],
        created_by="claude",
    )
    rendering = _call(
        "create_rendering",
        unit_id=UNIT_ID,
        layer="lyric",
        text="Blessed is the one who will not walk the way the wicked counsel",
        rationale="first draft",
        translation_id=translation["translation_id"],
        created_by="claude",
    )

    assert rendering["translation_id"] == translation["translation_id"]
    table = _call(
        "get_comparison_table",
        psalm_id=PSALM_ID,
        translation_id=translation["translation_id"],
    )
    row = next(row for row in table["rows"] if UNIT_ID in row["unit_ids"])
    assert "wicked counsel" in json.dumps(row)
    main = _call("get_comparison_table", psalm_id=PSALM_ID)
    assert "wicked counsel" not in json.dumps(main)
    audit = _call("get_unit_audit", unit_id=UNIT_ID)
    assert audit[-1]["created_by"] == "mcp:claude"


def test_review_decisions_are_recorded_as_mcp_reviewers() -> None:
    rendering = _call(
        "create_rendering", unit_id=UNIT_ID, layer="lyric", text="Happy the one", rationale="r"
    )
    decision = _call(
        "review_rendering",
        target_id=rendering["rendering_id"],
        decision="approve",
        reviewer="alice",
        reviewer_role="lyric reviewer",
    )

    assert decision["reviewer"] == "mcp:alice"


def test_refusals_reach_the_llm_with_their_reason() -> None:
    project = _call("create_project", title="One of each")
    first, second = _calls(
        (
            "create_translation",
            {"psalm_id": PSALM_ID, "title": "A", "collection_id": project["collection_id"]},
        ),
        (
            "create_translation",
            {"psalm_id": PSALM_ID, "title": "B", "collection_id": project["collection_id"]},
        ),
    )

    assert "translation_id" in first
    assert second[0] == "error"
    assert "One of each" in second[1]


def test_status_and_canonical_text_do_not_change_outside_review() -> None:
    rendering = _call(
        "create_rendering", unit_id=UNIT_ID, layer="lyric", text="Happy the one", rationale="r"
    )
    status = _call(
        "update_rendering", rendering_id=rendering["rendering_id"], changes={"status": "canonical"}
    )
    assert status[0] == "error"

    canonical = next(
        r for r in registry_service.load_unit(UNIT_ID)["renderings"] if r["status"] == "canonical"
    )
    text = _call(
        "update_rendering", rendering_id=canonical["rendering_id"], changes={"text": "Rewritten"}
    )
    assert text[0] == "error"
    assert "canonical" in text[1]

    edited = _call(
        "update_rendering",
        rendering_id=rendering["rendering_id"],
        changes={"text": "Happy is the one"},
        created_by="claude",
    )
    assert edited["text"] == "Happy is the one"


def test_the_api_serves_the_tools_at_mcp_to_local_clients_only() -> None:
    headers = {"Accept": "application/json, text/event-stream"}
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    with TestClient(app, base_url="http://127.0.0.1:43174") as local:
        response = local.post("/mcp", headers=headers, json=request)
        foreign = TestClient(app).post("/mcp", headers=headers, json=request)

    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert {"create_rendering", "review_rendering", "codex_import_translation"} <= names
    assert foreign.status_code == 421
