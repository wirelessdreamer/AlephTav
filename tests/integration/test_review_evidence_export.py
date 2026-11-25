from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.core.errors import ReviewRequiredError
from app.core.ids import decision_id
from app.services import export_service, registry_service, rendering_service, review_service

UNIT_ID = "ps001.v001.a"


@pytest.fixture
def accepted_rendering() -> dict[str, Any]:
    created = rendering_service.create_rendering(
        UNIT_ID,
        "literal",
        "Blessed is the man",
        "proposed",
        "Authored export policy fixture",
        "test:fixture",
    )
    review_service.add_review_decision(
        created["rendering_id"], "approve", "fixture-reviewer", "Hebrew reviewer"
    )
    return review_service.add_review_decision(
        created["rendering_id"], "accept-alternate", "fixture-reviewer", "Hebrew reviewer"
    )


def _export(kind: str) -> Path:
    if kind == "book":
        return export_service.export_book("ps001")
    return export_service.export_release("review-evidence-fixture")


def _content_and_reports() -> dict[str, bytes | None]:
    settings = get_settings()
    return {
        path.relative_to(settings.root_dir).as_posix(): path.read_bytes()
        if path.is_file()
        else None
        for base in (settings.content_dir, settings.reports_dir)
        for path in base.rglob("*")
    }


@pytest.mark.parametrize("kind", ["book", "release"])
def test_quarantined_accepted_alternate_blocks_public_export_before_writes(
    accepted_rendering: dict[str, Any], kind: str
) -> None:
    assert accepted_rendering["status"] == "accepted_as_alternate"
    unit = registry_service.load_unit(UNIT_ID)
    unit["review_decisions"].append(
        {
            "decision_id": decision_id(
                UNIT_ID, [record["decision_id"] for record in unit["review_decisions"]]
            ),
            "target_id": accepted_rendering["rendering_id"],
            "reviewer_role": "Hebrew reviewer",
            "reviewer": "Authored versioned evidence fixture",
            "decision": "approve",
            "notes": "Contract fixture; does not establish authenticated human review",
            "timestamp": "2026-11-05T19:00:00Z",
            "contract_version": 2,
            "principal": {"principal_id": "fixture.person", "kind": "human"},
            "channel": "ui",
            "payload_digest": {"version": 2, "algorithm": "sha256", "value": "a" * 64},
            "policy_revision": "b" * 64,
        }
    )
    registry_service.save_unit(unit)
    settings = get_settings()
    destination = settings.release_reports_dir / (
        "book-export" if kind == "book" else "review-evidence-fixture/bundle"
    )
    destination.mkdir(parents=True, exist_ok=True)
    artifact = destination / ("book.json" if kind == "book" else "text.json")
    artifact.write_bytes(b"Previous approved artifact must remain intact")
    before = _content_and_reports()

    with pytest.raises(ReviewRequiredError, match="[Vv]ersioned"):
        _export(kind)

    assert _content_and_reports() == before


@pytest.mark.parametrize("kind", ["book", "release"])
def test_wholly_legacy_accepted_alternate_keeps_existing_export_behavior(
    accepted_rendering: dict[str, Any], kind: str
) -> None:
    destination = _export(kind)
    payload = json.loads(
        (destination / ("book.json" if kind == "book" else "text.json")).read_text(encoding="utf-8")
    )
    exported = [
        rendering
        for psalm in payload
        for unit in psalm["units"]
        for rendering in unit["alternate_renderings"]
        if rendering["rendering_id"] == accepted_rendering["rendering_id"]
    ]
    assert len(exported) == 1
    assert exported[0]["text"] == "Blessed is the man"
