from __future__ import annotations

import json
from typing import Any

import anyio
from mcp import Client

from app.api import mcp_server
from app.services import registry_service, rendering_service

PSALM = "ps001"
UNIT = "ps001.v001.a"


def _call(name: str, **arguments: Any) -> Any:
    async def invoke() -> Any:
        async with Client(mcp_server.server) as client:
            result = await client.call_tool(name, arguments)
            text = result.content[0].text
            return ("error", text) if result.is_error else json.loads(text)

    return anyio.run(invoke)


def test_mcp_records_stated_intent_as_an_agent_without_changing_review() -> None:
    rendering = rendering_service.create_rendering(
        UNIT, "lyric", "An authored lyrical choice", "proposed", "Fixture", "fixture"
    )
    before = registry_service.read_json(registry_service.unit_path(UNIT))
    view = _call("list_translation_choices", psalm_id=PSALM, unit_id=UNIT)
    target = next(item for item in view["targets"] if item["id"] == rendering["rendering_id"])

    entry = _call(
        "record_translation_choice",
        psalm_id=PSALM,
        targets=[
            {
                "kind": "rendering",
                "id": target["id"],
                "expected_revision": target["revision"]["value"],
            }
        ],
        decision="Retain this authored image",
        rationale="The translator states the image is deliberate",
        context_note="Supporting historical context has not been established",
        created_by="fixture-agent",
    )

    assert entry["created_by"] == "mcp:fixture-agent"
    assert entry["counts_for_publication"] is False
    assert entry["choice"]["context_status"] == "not_established"
    after = registry_service.read_json(registry_service.unit_path(UNIT))
    assert after["audit_records"][:-1] == before["audit_records"]
    assert after["audit_records"][-1]["created_by"] == "mcp:fixture-agent"
    assert after["audit_records"][-1]["review_signoff"] == {}
    assert {
        key: value for key, value in after.items() if key not in {"audit_ids", "audit_records"}
    } == {key: value for key, value in before.items() if key not in {"audit_ids", "audit_records"}}
    assert (
        _call("list_translation_choices", psalm_id=PSALM)["choices"][0]["audit_id"]
        == entry["audit_id"]
    )


def test_mcp_stale_choice_refusal_preserves_persisted_bytes() -> None:
    rendering = rendering_service.create_rendering(
        UNIT, "lyric", "An earlier line", "proposed", "Fixture", "fixture"
    )
    view = _call("list_translation_choices", psalm_id=PSALM, unit_id=UNIT)
    target = next(item for item in view["targets"] if item["id"] == rendering["rendering_id"])
    rendering_service.update_rendering(target["id"], {"text": "A changed line"}, "fixture")
    path = registry_service.unit_path(UNIT)
    before = path.read_bytes()

    result = _call(
        "record_translation_choice",
        psalm_id=PSALM,
        targets=[
            {
                "kind": "rendering",
                "id": target["id"],
                "expected_revision": target["revision"]["value"],
            }
        ],
        decision="Retain the earlier wording",
        rationale="A stale submission must be refused",
        context_note="Context remains unestablished",
        created_by="fixture-agent",
    )

    assert result[0] == "error"
    assert path.read_bytes() == before
