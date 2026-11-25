from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from app.services import registry_service, report_service
from scripts.validate_content import validate_all_content

UNIT_ID = "ps001.v001.a"
TARGET_ID = "rnd.ps001.v001.a.literal.can.0001"


def _decision(timestamp: str) -> dict[str, Any]:
    return {
        "decision_id": "rev.ps001.v001.a.0099",
        "target_id": TARGET_ID,
        "reviewer_role": "release reviewer",
        "reviewer": "unverified claimed principal",
        "decision": "approve",
        "notes": "Fixture only",
        "timestamp": timestamp,
        "contract_version": 2,
        "principal": {"principal_id": "agent:fixture", "kind": "agent"},
        "channel": "mcp",
        "payload_digest": {"version": 2, "algorithm": "sha256", "value": "0" * 64},
        "policy_revision": "1" * 64,
    }


def _store(record: dict[str, Any]) -> None:
    unit = registry_service.load_unit(UNIT_ID)
    unit["review_decisions"].append(record)
    registry_service.save_unit(unit)


def test_content_validation_accepts_a_structural_v2_record_without_granting_authority() -> None:
    _store(_decision("2026-11-05T12:00:00Z"))

    result = validate_all_content()

    assert result["errors"] == []
    checks = {item["name"]: item for item in report_service.validate_release("fixture")["checks"]}
    assert checks["canonical_review_signoff"]["status"] == "fail"


@pytest.mark.parametrize(
    "timestamp",
    ["2026-11-05T12:00:00", "2026-02-30T12:00:00Z", "2026-11-05T12:00:00+01:99"],
)
def test_content_validation_rejects_invalid_v2_timestamps(timestamp: str) -> None:
    _store(_decision(timestamp))

    errors = validate_all_content()["errors"]

    assert any("review_decisions" in error for error in errors)


def test_legacy_timestamp_and_approval_are_preserved_under_the_frozen_contract() -> None:
    unit = registry_service.load_unit(UNIT_ID)
    unit["review_decisions"][0]["timestamp"] = "historical timestamp retained verbatim"
    original_history = deepcopy(unit["review_decisions"])
    registry_service.save_unit(unit)
    path = registry_service.unit_path(UNIT_ID)
    before = path.read_bytes()

    result = validate_all_content()

    assert result["errors"] == []
    assert registry_service.load_unit(UNIT_ID)["review_decisions"] == original_history
    assert path.read_bytes() == before


def test_invalid_versioned_notes_are_not_echoed_by_unit_schema_diagnostics() -> None:
    record = _decision("2026-11-05T12:00:00Z")
    record["notes"] = "private-review-sentinel" * 1000
    _store(record)

    errors = validate_all_content()["errors"]

    assert errors
    assert "private-review-sentinel" not in str(errors)
