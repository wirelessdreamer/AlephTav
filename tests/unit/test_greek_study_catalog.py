from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from app.core.errors import LicensePolicyError, ValidationError
from app.services import greek_analysis_service as analysis
from app.services import greek_dictionary_service as dictionary
from app.services import greek_study_service, registry_service, source_capability_service
from app.services import study_snapshot_service as snapshots
from app.services.greek_catalog_projection_service import canonical_projection
from app.services.immutable_file_service import sha256_file

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    shutil.copytree(Path(__file__).resolve().parents[2] / "schemas", tmp_path / "schemas")
    unit_id = "lxx.authored.r0001.ps151.v001.a"
    token_id = "lxx.authored.r0001.ps151.v001.t001"
    unit = {
        "schema_version": "1.0",
        "unit_id": unit_id,
        "corpus": "lxx",
        "edition_id": "authored",
        "text_revision_id": "r0001",
        "psalm_id": "ps151",
        "ref": "Psalm 151:1",
        "source_greek": "λόγος",
        "tokens": [
            {
                "token_id": token_id,
                "surface": "λόγος",
                "normalized": "λόγος",
                "position": 1,
                "text_span": {"start": 0, "end": 5},
                "source_locator": {"file": "authored.txt", "locator": "151:1", "fragments": []},
            }
        ],
    }
    license_bytes = b"Authored offline test fixture; no real source approval.\n"
    license_path = tmp_path / "license.txt"
    license_path.write_bytes(license_bytes)
    license_hash = sha256_file(license_path)
    attribution = {
        "source_id": "dictionary",
        "package_revision": "r0001",
        "license": "Authored",
        "license_text_sha256": license_hash,
        "required_attribution": "Authored test",
    }
    entry = (
        dictionary.parse_step_dictionary(
            "G3056\tG3056 =\tG3056\tλόγος\tlogos\tG:N\tauthored word\tAuthored definition",
            package_id="dict-package",
            source_file="authored.tsv",
            attribution=attribution,
        )
        .require_valid()
        .entries[0]
    )
    rows = analysis.parse_quantforge(
        "024151001 N- ----NSM- λόγος λόγος λόγος λόγος grc morpheus",
        package_id="analysis-package",
    )
    analysis_set = analysis.propose_analyses(
        [unit],
        rows,
        verse_map={"024151001": [unit_id]},
        analysis_set_id="authored-analysis",
    )
    packages = []
    for package_id, source_id, kind, filename, data in (
        (
            "source-package",
            "source",
            "source_text",
            "unit.json",
            registry_service.deterministic_json(unit).encode(),
        ),
        (
            "dict-package",
            "dictionary",
            "dictionary",
            "entries.jsonl",
            (json.dumps(entry, ensure_ascii=False) + "\n").encode(),
        ),
        (
            "analysis-package",
            "analysis",
            "analysis",
            "analyses.json",
            registry_service.deterministic_json(analysis_set).encode(),
        ),
    ):
        directory = tmp_path / "content" / "test-packages" / package_id
        directory.mkdir(parents=True)
        (directory / filename).write_bytes(data)
        (directory / "LICENSE.txt").write_bytes(license_bytes)
        manifest = {
            "schema_version": "1.0",
            "package_id": package_id,
            "source_id": source_id,
            "package_revision": "r0001",
            "kind": kind,
            "dependencies": [],
            "review_status": "approved",
            "files": [
                {
                    "path": name,
                    "sha256": sha256_file(directory / name),
                    "size_bytes": (directory / name).stat().st_size,
                }
                for name in (filename, "LICENSE.txt")
            ],
            "provenance": {
                "upstream_url": "https://example.invalid/authored",
                "upstream_revision": "fixture",
                "license": "Authored",
                "license_text_sha256": license_hash,
                "attribution": "Authored test",
            },
        }
        registry_service.write_json(directory / "package.json", manifest)
        packages.append(
            {
                "package_id": package_id,
                "path": (directory / "package.json").relative_to(tmp_path).as_posix(),
                "sha256": sha256_file(directory / "package.json"),
            }
        )
    # Only policy decisions are mocked; real publication verifies package bytes,
    # license closure, strict schemas and canonical file membership.
    monkeypatch.setattr(source_capability_service, "policy_revision", lambda: "policy.fixture")
    monkeypatch.setattr(source_capability_service, "require_capability", lambda *args: None)
    monkeypatch.setattr(source_capability_service, "require_package_capability", lambda *args: None)
    state = {"descriptor": None}

    def publish(payload):
        path = tmp_path / "catalogs" / (registry_service.file_hash(payload) + ".json")
        registry_service.write_json(path, payload)
        current = state["descriptor"]
        predecessor = current["study_snapshot_id"] if current else None
        descriptor = {
            "schema_version": "1.0",
            "predecessor_id": predecessor,
            "edition_id": "authored",
            "text_revision_id": "r0001",
            "policy_revision_id": "policy.fixture",
            "source_ids": ["source", "analysis", "dictionary"],
            "packages": packages,
            "catalog": {"path": path.relative_to(tmp_path).as_posix(), "sha256": sha256_file(path)},
            "mt_source_snapshot": None,
        }
        descriptor["study_snapshot_id"] = snapshots.snapshot_id(descriptor)
        snapshots.publish_snapshot(
            descriptor, predecessor, created_by="test:authored", rationale="Authored fixture only"
        )
        state["descriptor"] = descriptor
        return descriptor

    payload = {
        "units": [unit],
        "entries": [entry],
        "analyses": [
            candidate for item in analysis_set["annotations"] for candidate in item["analyses"]
        ],
    }
    publish(payload)
    return {
        "root": tmp_path,
        "payload": payload,
        "token_id": token_id,
        "entry": entry,
        "publish": publish,
        "state": state,
    }


def test_catalog_adapter_preserves_proposed_evidence_and_greek_only_identity(catalog) -> None:
    view = greek_study_service.load_view(None, "policy.fixture")
    card = view.card(catalog["token_id"])
    assert card["token"]["psalm"] == 151
    assert card["analyses"][0]["status"] == "proposed"
    assert card["dictionary_entries"] == []  # No invented reviewed lexical links.
    assert view.entry(catalog["entry"]["entry_id"])["entry"] == catalog["entry"]


@pytest.mark.parametrize(
    "field", ["source_text", "dictionary", "analysis", "reviewed", "selected", "foreign"]
)
def test_sealed_catalog_cannot_author_or_relabel_canonical_records(catalog, field) -> None:
    payload = copy.deepcopy(catalog["payload"])
    if field == "source_text":
        payload["units"][0]["source_greek"] = "κρυπτός"
        payload["units"][0]["tokens"][0]["surface"] = "κρυπτός"
    elif field == "dictionary":
        payload["entries"][0]["gloss"] = "Unauthorized extra dictionary text"
    elif field == "analysis":
        payload["analyses"][0]["lemma"] = "κρυπτός"
    elif field == "reviewed":
        payload["analyses"][0]["status"] = "reviewed"
    elif field == "selected":
        payload["units"][0]["tokens"][0]["selected_analysis_id"] = payload["analyses"][0][
            "analysis_id"
        ]
    else:
        payload["entries"].append({**payload["entries"][0], "entry_id": "foreign-entry"})
    with pytest.raises(ValidationError, match="canonical"):
        catalog["publish"](payload)
    assert greek_study_service.load_view().tokens[catalog["token_id"]]["surface"] == "λόγος"


def test_unenumerated_package_file_is_not_canonical_membership(catalog) -> None:
    payload = copy.deepcopy(catalog["payload"])
    entry = {**payload["entries"][0], "entry_id": "unenumerated-entry"}
    path = catalog["root"] / "content/test-packages/dict-package/hidden.json"
    registry_service.write_json(path, entry)
    payload["entries"].append(entry)
    with pytest.raises(ValidationError, match="canonical"):
        catalog["publish"](payload)


def test_expression_requires_canonical_evidence_not_catalog_claim(catalog) -> None:
    payload = copy.deepcopy(catalog["payload"])
    payload["expressions"] = [{"occurrence_id": "invented", "token_ids": [catalog["token_id"]]}]
    with pytest.raises(ValidationError, match="expressions"):
        catalog["publish"](payload)


def test_current_dictionary_revocation_fails_closed(catalog, monkeypatch) -> None:
    def revoked(source, capability):
        if source == "dictionary":
            raise LicensePolicyError("Revoked dictionary")

    monkeypatch.setattr(source_capability_service, "require_capability", revoked)
    with pytest.raises(LicensePolicyError):
        greek_study_service.load_view()


def test_projection_uses_current_capability_authority_after_module_import(
    catalog, monkeypatch
) -> None:
    def revoked(*args):
        raise LicensePolicyError("Current package capability revoked")

    monkeypatch.setattr(source_capability_service, "require_package_capability", revoked)
    with pytest.raises(LicensePolicyError, match="Current package"):
        canonical_projection(catalog["state"]["descriptor"])


def test_policy_is_bound_before_first_permission_check(catalog, monkeypatch) -> None:
    policy = {"current": "policy.fixture"}
    original = snapshots.active_snapshot

    def changed_after_validation(identifier):
        descriptor = original(identifier)
        policy["current"] = "policy.revoked"
        return descriptor

    monkeypatch.setattr(snapshots, "active_snapshot", changed_after_validation)
    monkeypatch.setattr(source_capability_service, "policy_revision", lambda: policy["current"])
    with pytest.raises(greek_study_service.StaleStudyError, match="during read"):
        greek_study_service.load_view()


def test_incompatible_descriptor_cannot_replace_good_snapshot(catalog) -> None:
    before = copy.deepcopy(catalog["state"]["descriptor"])
    incompatible = copy.deepcopy(before)
    incompatible["predecessor_id"] = before["study_snapshot_id"]
    incompatible["edition_id"] = "other-edition"
    incompatible["study_snapshot_id"] = snapshots.snapshot_id(incompatible)
    with pytest.raises(ValidationError, match="outside selected edition"):
        snapshots.publish_snapshot(
            incompatible,
            before["study_snapshot_id"],
            created_by="test",
            rationale="Authored adversarial scope",
        )
    assert snapshots.active_snapshot()["study_snapshot_id"] == before["study_snapshot_id"]
