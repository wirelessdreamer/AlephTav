from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from app.core.errors import ValidationError
from app.services.review_evidence_service import (
    classify_review_evidence,
    is_legacy_review_decision,
    validate_review_decision,
)

pytestmark = pytest.mark.no_seeded_repo
SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
DIGEST = {"version": 2, "algorithm": "sha256", "value": "a" * 64}
POLICY = "b" * 64


def legacy_record() -> dict[str, Any]:
    return {
        "decision_id": "rev.ps001.v001.a.0001",
        "target_id": "rnd.ps001.v001.a.literal.alt.0001",
        "reviewer_role": "Hebrew reviewer",
        "reviewer": "Review display name",
        "decision": "approve",
        "notes": "Authored test evidence; no real approval",
        "timestamp": "2026-11-05T19:00:00Z",
    }


def v2_record() -> dict[str, Any]:
    return {
        **legacy_record(),
        "contract_version": 2,
        "principal": {"principal_id": "reviewer.fixture", "kind": "human"},
        "channel": "ui",
        "payload_digest": deepcopy(DIGEST),
        "policy_revision": POLICY,
    }


def schema_validator(name: str) -> Draft202012Validator:
    resources = [
        (path.resolve().as_uri(), Resource.from_contents(json.loads(path.read_text("utf-8"))))
        for path in SCHEMAS.glob("*.schema.json")
    ]
    registry = Registry().with_resources(resources)
    return Draft202012Validator(
        {"$ref": (SCHEMAS / name).resolve().as_uri()},
        registry=registry,
        format_checker=FormatChecker(),
    )


def unit_with_decisions(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "psalm_id": "ps001",
        "unit_id": "ps001.v001.a",
        "ref": "Psalm 1:1",
        "segmentation_type": "verse",
        "source_hebrew": "א",
        "source_transliteration": "a",
        "token_ids": [],
        "concept_ids": [],
        "status": "draft",
        "current_layer_state": {"locked_layers": [], "latest_layer": "source"},
        "canonical_rendering_ids": [],
        "alternate_rendering_ids": [],
        "audit_ids": [],
        "issue_links": [],
        "pr_links": [],
        "tokens": [],
        "alignments": [],
        "renderings": [],
        "audit_records": [],
        "review_decisions": records,
        "witnesses": [],
    }


def test_legacy_constraints_are_frozen_exactly() -> None:
    schema = json.loads((SCHEMAS / "review_decision_v1.schema.json").read_text("utf-8"))
    schema.pop("$schema")
    schema.pop("title")
    assert schema == {
        "type": "object",
        "required": [
            "decision_id",
            "target_id",
            "reviewer_role",
            "reviewer",
            "decision",
            "notes",
            "timestamp",
        ],
        "additionalProperties": False,
        "properties": {
            "decision_id": {
                "type": "string",
                "pattern": (
                    r"^rev\.(?:(?:lxx\.[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*\.r[0-9]{4,}\.)"
                    r"|lxx\.)?ps\d{3}\.v\d{3}\.[a-z]\.\d{4}$"
                ),
            },
            **{key: {"type": "string"} for key in legacy_record() if key != "decision_id"},
        },
    }
    permissive = {key: "" for key in legacy_record()}
    permissive["decision_id"] = "rev.ps001.v001.a.0001"
    assert validate_review_decision(permissive) == "legacy"


@pytest.mark.parametrize("record,version", [(legacy_record(), "legacy"), (v2_record(), "v2")])
def test_standalone_composite_and_unit_resolvers_accept_both_contracts(
    record: dict[str, Any], version: str
) -> None:
    assert validate_review_decision(record) == version
    assert schema_validator("review_decision.schema.json").is_valid(record)
    assert schema_validator("unit.schema.json").is_valid(unit_with_decisions([record]))


def test_unit_accepts_mixed_historical_and_explicit_evidence_without_rewriting_it() -> None:
    records = [legacy_record(), v2_record()]
    records[1]["decision_id"] = "rev.ps001.v001.a.0002"
    before = deepcopy(records)
    assert schema_validator("unit.schema.json").is_valid(unit_with_decisions(records))
    assert records == before


@pytest.mark.parametrize("record", [None, [], "review", 2, {}, {**legacy_record(), "extra": True}])
def test_invalid_record_shapes_fail_without_legacy_fallback(record: Any) -> None:
    with pytest.raises(ValidationError):
        validate_review_decision(record)
    assert (
        classify_review_evidence(record, payload_digest=DIGEST, policy_revision=POLICY)["status"]
        == "invalid"
    )


@pytest.mark.parametrize("version", [None, 1, 3, "2", True])
def test_tagged_invalid_or_future_versions_do_not_become_legacy(version: Any) -> None:
    record = {**legacy_record(), "contract_version": version}
    assert is_legacy_review_decision(record) is False
    with pytest.raises(ValidationError):
        validate_review_decision(record)
    assert not schema_validator("review_decision.schema.json").is_valid(record)


@pytest.mark.parametrize(
    "field,value",
    [
        ("reviewer", "   "),
        ("reviewer", "x" * 201),
        ("reviewer_role", "\t"),
        ("reviewer_role", "x" * 101),
        ("notes", "x" * 10001),
        ("channel", "assistant"),
        ("channel", "unknown"),
        ("decision", "release_approved"),
        ("target_id", "a different entity"),
        ("policy_revision", "B" * 64),
        ("policy_revision", "b" * 63),
        ("extra", "not allowed"),
        ("principal", {"principal_id": " ", "kind": "human"}),
        ("principal", {"principal_id": "person\n", "kind": "human"}),
        ("principal", {"principal_id": "x" * 201, "kind": "human"}),
        ("principal", {"principal_id": "person", "kind": "owner"}),
        ("principal", {"principal_id": "person", "kind": "human", "authenticated": True}),
        ("payload_digest", {**DIGEST, "algorithm": "md5"}),
        ("payload_digest", {**DIGEST, "version": 3}),
        ("payload_digest", {**DIGEST, "value": "A" * 64}),
        ("payload_digest", {**DIGEST, "extra": True}),
    ],
)
def test_v2_rejects_unbounded_unknown_or_forged_contract_fields(field: str, value: Any) -> None:
    record = {**v2_record(), field: value}
    with pytest.raises(ValidationError):
        validate_review_decision(record)
    assert not schema_validator("unit.schema.json").is_valid(unit_with_decisions([record]))


@pytest.mark.parametrize(
    "timestamp",
    [
        "not a date",
        "2026-11-05T19:00:00",
        "2026-11-05 19:00:00Z",
        "2026-02-30T19:00:00Z",
        "2026-13-05T19:00:00Z",
        "2026-11-05T24:00:00Z",
        "2026-11-05T19:00:00+01:99",
        "2026-11-05T19:00:00+24:00",
        "2026-11-05T19:00:00.1234567890Z",
        "2026-11-05T19:00:00Z\n",
    ],
)
def test_v2_rejects_invalid_actual_or_timezone_timestamps(timestamp: str) -> None:
    record = {**v2_record(), "timestamp": timestamp}
    with pytest.raises(ValidationError):
        validate_review_decision(record)


@pytest.mark.parametrize(
    "timestamp", ["2026-11-05T19:00:00Z", "2026-11-05T19:00:00.123456789-05:00"]
)
def test_v2_preserves_valid_exact_timestamp_precision(timestamp: str) -> None:
    record = {**v2_record(), "timestamp": timestamp}
    assert validate_review_decision(record) == "v2"
    assert record["timestamp"] == timestamp


def test_mcp_channel_cannot_claim_a_human_principal() -> None:
    record = {**v2_record(), "channel": "mcp"}
    with pytest.raises(ValidationError):
        validate_review_decision(record)
    record["principal"]["kind"] = "agent"
    assert validate_review_decision(record) == "v2"
    assert schema_validator("review_decision.schema.json").is_valid(record)


def test_configured_role_and_withdrawal_are_contract_values_not_authority() -> None:
    record = {**v2_record(), "reviewer_role": "custom qualified role", "decision": "withdraw"}
    assert validate_review_decision(record) == "v2"
    result = classify_review_evidence(record, payload_digest=DIGEST, policy_revision=POLICY)
    assert result == {"status": "binding_current_unverified", "counts_for_publication": False}


@pytest.mark.parametrize("kind,channel", [("human", "ui"), ("agent", "mcp")])
def test_matching_explicit_evidence_never_authenticates_or_counts(kind: str, channel: str) -> None:
    record = v2_record()
    record["principal"]["kind"] = kind
    record["channel"] = channel
    before = deepcopy(record)
    assert classify_review_evidence(record, payload_digest=DIGEST, policy_revision=POLICY) == {
        "status": "binding_current_unverified",
        "counts_for_publication": False,
    }
    assert record == before


def test_legacy_requires_explicit_reattestation_without_synthesized_identity_or_digest() -> None:
    record = legacy_record()
    before = deepcopy(record)
    assert classify_review_evidence(record, payload_digest=DIGEST, policy_revision=POLICY) == {
        "status": "legacy_requires_reattestation",
        "counts_for_publication": False,
    }
    assert record == before


@pytest.mark.parametrize(
    "digest,policy,status",
    [
        (None, POLICY, "binding_unavailable"),
        (DIGEST, None, "binding_unavailable"),
        ({}, POLICY, "binding_unavailable"),
        (DIGEST, "not a hash", "binding_unavailable"),
        ({**DIGEST, "value": "c" * 64}, POLICY, "payload_mismatch"),
        (DIGEST, "c" * 64, "policy_mismatch"),
    ],
)
def test_binding_classifier_reports_mismatches_without_authority(
    digest: dict[str, Any] | None, policy: str | None, status: str
) -> None:
    result = classify_review_evidence(v2_record(), payload_digest=digest, policy_revision=policy)
    assert result == {"status": status, "counts_for_publication": False}


def test_validation_uses_only_code_owned_schemas_and_never_creates_workspace_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nonexistent = tmp_path / "must-remain-absent"
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(nonexistent))
    assert validate_review_decision(v2_record()) == "v2"
    assert (
        classify_review_evidence(v2_record(), payload_digest=DIGEST, policy_revision=POLICY)[
            "counts_for_publication"
        ]
        is False
    )
    assert not nonexistent.exists()


def test_invalid_reason_does_not_echo_untrusted_notes() -> None:
    record = {**v2_record(), "notes": "private-secret-" * 1000}
    result = classify_review_evidence(record, payload_digest=DIGEST, policy_revision=POLICY)
    assert result["status"] == "invalid"
    assert "private-secret" not in result["reason"]


@pytest.mark.parametrize(
    "field,prefix,suffix",
    [
        ("decision_id", "rev.lxx.", ".r0001.ps001.v001.a.0001"),
        ("target_id", "rnd.lxx.", ".r0001.ps001.v001.a.literal.alt.0001"),
    ],
)
def test_v2_evidence_ids_have_an_explicit_200_character_boundary(
    field: str, prefix: str, suffix: str
) -> None:
    record = v2_record()
    record[field] = prefix + "a" * (200 - len(prefix) - len(suffix)) + suffix
    assert len(record[field]) == 200
    assert validate_review_decision(record) == "v2"
    record[field] = prefix + "a" * (201 - len(prefix) - len(suffix)) + suffix
    with pytest.raises(ValidationError):
        validate_review_decision(record)


@pytest.mark.parametrize("depth", [600, 900])
@pytest.mark.parametrize("field", ["target_id", "notes", "principal"])
def test_json_loadable_deep_scalar_type_errors_remain_safe(depth: int, field: str) -> None:
    nested = json.loads('{"private-nested-value":' * depth + "null" + "}" * depth)
    record = {**v2_record(), field: nested}
    with pytest.raises(ValidationError):
        validate_review_decision(record)
    result = classify_review_evidence(record, payload_digest=DIGEST, policy_revision=POLICY)
    assert result["status"] == "invalid"
    assert result["counts_for_publication"] is False
    assert "private-nested-value" not in result["reason"]
    assert len(result["reason"]) < 240
