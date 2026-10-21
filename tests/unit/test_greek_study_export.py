from __future__ import annotations

import hashlib
import json

import pytest

from app.core.errors import LicensePolicyError, ReleaseValidationError
from app.services import greek_study_export_service as export
from app.services import source_capability_service, study_snapshot_service
from app.services.registry_service import file_hash

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def approved_release(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    monkeypatch.setattr(source_capability_service, "policy_revision", lambda: "policy.authored")
    descriptor = {"study_snapshot_id": "study.authored"}
    record = {
        "enabled": True,
        "release": "A",
        "study_snapshot_id": "study.authored",
        "policy_revision_id": "policy.authored",
        "review_decisions": [],
    }
    for name in ("coverage_report", "expert_review_report"):
        data = json.dumps(
            {
                "status": "passed",
                "study_snapshot_id": "study.authored",
                "policy_revision_id": "policy.authored",
            }
        ).encode()
        path = f"{name}.json"
        (tmp_path / path).write_bytes(data)
        record[name] = {"path": path, "sha256": hashlib.sha256(data).hexdigest()}
    payload_hash = file_hash(
        {
            "descriptor_sha256": file_hash(descriptor),
            "policy_revision_id": "policy.authored",
            "release": "A",
            "audit_files": [],
            "coverage_report": record["coverage_report"],
            "expert_review_report": record["expert_review_report"],
        }
    )
    for reviewer, role in [
        ("owner", "owner"),
        ("release", "release reviewer"),
        ("greek-1", "Greek reviewer"),
        ("greek-2", "Greek reviewer"),
    ]:
        record["review_decisions"].append(
            {
                "reviewer_id": reviewer,
                "role": role,
                "decision": "approve",
                "payload_hash": payload_hash,
            }
        )
    monkeypatch.setattr(export, "availability_record", lambda: record)
    return tmp_path, descriptor, record


def test_release_requires_report_bytes_and_latest_applicable_decisions(approved_release) -> None:
    root, descriptor, record = approved_release
    assert export.availability(descriptor)
    decision = {**record["review_decisions"][-1], "decision": "withdraw"}
    record["review_decisions"].append(decision)
    assert not export.availability(descriptor)
    record["review_decisions"].pop()
    (root / record["coverage_report"]["path"]).write_text("changed", encoding="utf-8")
    assert not export.availability(descriptor)


def test_release_rejects_placeholder_signoffs_stale_policy_and_unfinished_bridge(
    approved_release,
    monkeypatch,
) -> None:
    _, descriptor, record = approved_release
    record["release"] = "B"
    assert not export.availability(descriptor)
    record["release"] = "A"
    monkeypatch.setattr(source_capability_service, "policy_revision", lambda: "policy.changed")
    assert not export.availability(descriptor)
    monkeypatch.setattr(source_capability_service, "policy_revision", lambda: "policy.authored")
    record["review_decisions"] = []
    record.update(
        owner_signoff="yes",
        source_signoff="yes",
        release_reviewer_signoff="yes",
        coverage_report_sha256="yes",
        expert_review_report_sha256="yes",
    )
    assert not export.availability(descriptor)


def test_release_defaults_off_and_cannot_infer_permission_from_publication(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    descriptor = {"study_snapshot_id": "study.fixture"}
    monkeypatch.setattr(study_snapshot_service, "active_snapshot", lambda _: descriptor)
    assert export.availability(descriptor) is False
    with pytest.raises(ReleaseValidationError, match="availability gates"):
        export.prepare_bundle("study.fixture")


def test_mt_bridge_export_fails_until_source_provenance_closure_is_ready(monkeypatch) -> None:
    descriptor = {
        "study_snapshot_id": "study.fixture",
        "mt_source_snapshot": {"snapshot_id": "mt.fixture"},
    }
    monkeypatch.setattr(study_snapshot_service, "active_snapshot", lambda _: descriptor)
    monkeypatch.setattr(export, "availability", lambda _: True)
    with pytest.raises(ReleaseValidationError, match="Hebrew provenance"):
        export.prepare_bundle("study.fixture")


def test_current_export_policy_applies_to_every_snapshot_source_before_serialization(
    monkeypatch,
) -> None:
    descriptor = {
        "study_snapshot_id": "study.fixture",
        "mt_source_snapshot": None,
        "source_ids": ["source", "restricted_nested_dictionary"],
    }
    monkeypatch.setattr(study_snapshot_service, "active_snapshot", lambda _: descriptor)
    monkeypatch.setattr(export, "availability", lambda _: True)
    monkeypatch.setattr(source_capability_service, "policy_revision", lambda: "policy.fixture")
    checked = []

    def require(source, capability):
        checked.append((source, capability))
        if source == "restricted_nested_dictionary":
            raise LicensePolicyError("Revoked export capability")

    monkeypatch.setattr(source_capability_service, "require_capability", require)
    with pytest.raises(LicensePolicyError, match="Revoked"):
        export.prepare_bundle("study.fixture")
    assert checked == [("source", "export"), ("restricted_nested_dictionary", "export")]
