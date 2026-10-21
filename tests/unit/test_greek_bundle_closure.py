"""The unexposed Greek export validates signed audit scope and stays reconstruction-gated."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from app.core.errors import ReleaseValidationError
from app.services import greek_study_export_service as export
from app.services import greek_study_service, source_capability_service, study_snapshot_service
from app.services.package_audit_service import record_package_mutation
from app.services.registry_service import deterministic_json

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    source_schemas = Path(__file__).resolve().parents[2] / "schemas"
    for name in ("source_package.schema.json", "audit_record.schema.json"):
        shutil.copyfile(source_schemas / name, schema_dir / name)
    descriptor = {
        "study_snapshot_id": "study.authored",
        "source_ids": ["authored"],
        "mt_source_snapshot": None,
        "packages": [],
    }
    record = {"audit_files": []}
    for kind, directory in [
        ("source_text", "lxx"),
        ("dictionary", "lexicons"),
        ("analysis", "lxx"),
        ("lexemes", "lexemes"),
        ("crosswalks", "lexemes"),
        ("versification", "versification"),
    ]:
        package_id = "fixture-" + kind
        base = tmp_path / "content" / directory / package_id / "r0001"
        base.mkdir(parents=True)
        license_bytes = b"Authored fixture license: CC0.\n"
        (base / "LICENSE.txt").write_bytes(license_bytes)
        license_hash = hashlib.sha256(license_bytes).hexdigest()
        manifest = {
            "schema_version": "1.0",
            "package_id": package_id,
            "source_id": "authored",
            "package_revision": "r0001",
            "kind": kind,
            "review_status": "pending",
            "dependencies": [],
            "files": [
                {"path": "LICENSE.txt", "sha256": license_hash, "size_bytes": len(license_bytes)}
            ],
            "provenance": {
                "upstream_url": "https://example.org/authored",
                "upstream_revision": "fixture",
                "license": "CC0",
                "license_text_sha256": license_hash,
                "attribution": "Authored tests",
            },
        }
        data = deterministic_json(manifest).encode()
        path = base / "package.json"
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        descriptor["packages"].append(
            {
                "package_id": package_id,
                "path": path.relative_to(tmp_path).as_posix(),
                "sha256": digest,
            }
        )
        audit = record_package_mutation(
            package_id=package_id,
            before_hash="0" * 64,
            after_hash=digest,
            summary="Authored offline fixture",
            rationale="Authored test",
            created_by="authored-test",
            checks=["fixture"],
        )
        audit_name = audit["audit_id"][len("aud.pkg.") : -len(".0001")] + ".json"
        audit_path = tmp_path / "content" / "audit" / "packages" / audit_name
        record["audit_files"].append(
            {
                "path": audit_path.relative_to(tmp_path).as_posix(),
                "sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                "package_id": package_id,
            }
        )
    monkeypatch.setattr(source_capability_service, "policy_revision", lambda: "policy.authored")
    monkeypatch.setattr(source_capability_service, "require_capability", lambda *args: None)
    monkeypatch.setattr(source_capability_service, "require_package_capability", lambda *args: None)
    monkeypatch.setattr(study_snapshot_service, "active_snapshot", lambda _: descriptor)
    monkeypatch.setattr(export, "availability", lambda _: True)
    monkeypatch.setattr(export, "availability_record", lambda: record)
    monkeypatch.setattr(greek_study_service, "load_view", lambda *args: None)
    return tmp_path, descriptor, record


def test_verified_candidate_stays_explicitly_reconstruction_gated(bundle):
    with pytest.raises(ReleaseValidationError, match="independently verified reconstruction"):
        export.prepare_bundle("study.authored")


@pytest.mark.parametrize(
    "path", ["data/raw/secret.json", "secret.json", "content/audit/other.json"]
)
def test_audit_refs_cannot_read_arbitrary_workspace_or_raw_files(bundle, path):
    root, _, record = bundle
    candidate = root / path
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text("SECRET", encoding="utf-8")
    record["audit_files"][0].update(path=path, sha256=hashlib.sha256(b"SECRET").hexdigest())
    with pytest.raises(ReleaseValidationError, match="content/audit/packages"):
        export.prepare_bundle("study.authored")


@pytest.mark.parametrize(
    "field,value",
    [("entity_id", "another-package"), ("entity_type", "unit"), ("after_hash", "0" * 64)],
)
def test_audit_package_identity_and_manifest_hash_must_match(bundle, field, value):
    root, _, record = bundle
    reference = record["audit_files"][0]
    path = root / reference["path"]
    audit = json.loads(path.read_text())
    audit[field] = value
    data = deterministic_json(audit).encode()
    path.write_bytes(data)
    reference["sha256"] = hashlib.sha256(data).hexdigest()
    with pytest.raises(ReleaseValidationError, match="does not attest"):
        export.prepare_bundle("study.authored")


def test_unlisted_or_missing_audit_package_is_rejected(bundle):
    _, _, record = bundle
    reference = record["audit_files"].pop()
    with pytest.raises(ReleaseValidationError, match="Every exported package"):
        export.prepare_bundle("study.authored")
    record["audit_files"].append({**reference, "package_id": "not-in-closure"})
    with pytest.raises(ReleaseValidationError, match="outside the export closure"):
        export.prepare_bundle("study.authored")


def test_policy_capture_precedes_snapshot_open(bundle, monkeypatch):
    _, descriptor, _ = bundle
    policy = ["policy.before"]
    monkeypatch.setattr(source_capability_service, "policy_revision", lambda: policy[0])

    def opening(_):
        policy[0] = "policy.changed"
        return descriptor

    monkeypatch.setattr(study_snapshot_service, "active_snapshot", opening)
    with pytest.raises(ReleaseValidationError, match="while opening"):
        export.prepare_bundle("study.authored")


def test_release_record_cannot_swap_after_validation(bundle, monkeypatch):
    _, _, record = bundle

    def during_nested_read(*args):
        record["audit_files"] = []

    monkeypatch.setattr(greek_study_service, "load_view", during_nested_read)
    with pytest.raises(ReleaseValidationError, match="release evidence changed"):
        export.prepare_bundle("study.authored")
