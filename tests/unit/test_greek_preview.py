from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from app.core.errors import LicensePolicyError
from app.services import briefing_source_service as sources
from app.services import greek_preview_service as preview
from app.services import swete_package_service as swete
from app.services.greek_package_intake_service import canonical_bytes
from app.services.registry_service import file_hash
from tests.unit.test_swete_package import exports

pytestmark = pytest.mark.no_seeded_repo

MT_UNITS = [{"unit_id": "ps001.v001.a", "ref": "Psalm 1:1"}]


@pytest.fixture
def staged(tmp_path, monkeypatch):
    """A staged Swete package plus an owner preview approval bound to its manifest."""
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    preview._validated_package.cache_clear()
    shutil.copytree(Path(__file__).resolve().parents[2] / "schemas", tmp_path / "schemas")
    units = swete.build_units(exports(), "r0001")
    verse_map, _ = swete.build_map(units, MT_UNITS, "r0001")
    files = {
        "LICENSE": b"license text",
        "versification/map.json": canonical_bytes(verse_map),
        **{
            f"psalms/{u['psalm_id']}/v{u['unit_id'][-6:-2]}.json": canonical_bytes(u) for u in units
        },
    }
    manifest = {
        "schema_version": "1.0",
        "package_id": "swete1896.text",
        "source_id": "swete1896",
        "package_revision": "r0001",
        "kind": "source_text",
        "files": [
            {"path": p, "sha256": hashlib.sha256(d).hexdigest(), "size_bytes": len(d)}
            for p, d in sorted(files.items())
        ],
        "dependencies": [],
        "provenance": {
            "attribution": "Swete 1896, transcribed",
            "license": "CC BY-SA 4.0",
            "upstream_url": "https://example.invalid/authored-fixture",
            "upstream_revision": "authored-fixture-r1",
            "license_text_sha256": hashlib.sha256(files["LICENSE"]).hexdigest(),
        },
        "review_status": "pending",
    }
    root = preview.staged_package_dir("swete1896.text", "r0001")
    swete._write_package(root, files, manifest)
    preview.approve_preview(
        "swete1896.text", "r0001", reviewer_id="owner-1", rationale="Authored local preview"
    )
    monkeypatch.setattr(sources.registry_service, "load_psalm", lambda _: {"units": MT_UNITS})
    yield root
    preview._validated_package.cache_clear()


def test_approved_preview_shows_proposed_greek_when_nothing_is_released(staged):
    result = sources.greek_evidence("ps001")
    assert result["available"] is True
    assert result["preview"] is True
    assert "study_snapshot_id" not in result
    unit = result["by_mt_unit"]["ps001.v001.a"]["units"][0]
    assert unit["unit_id"] == "lxx.swete1896.r0001.ps001.v001.a"
    assert unit["source_greek"].startswith("ΜΑΚΑΡΙΟΣ")
    assert {token["gloss"] for token in unit["tokens"]} == {None}
    assert result["source_attribution"] == [
        {"attribution": "Swete 1896, transcribed", "license": "CC BY-SA 4.0"}
    ]


def test_without_owner_approval_the_released_message_is_unchanged(staged, tmp_path):
    (tmp_path / "content" / "study_snapshots" / "preview.json").unlink()
    result = sources.greek_evidence("ps001")
    assert result == {
        "by_mt_unit": {},
        "available": False,
        "message": "Greek study unavailable: No active study snapshot",
    }


def test_package_changed_after_approval_shows_no_text(staged):
    unit_file = next((staged / "psalms" / "ps001").rglob("*.json"))
    unit_file.write_bytes(unit_file.read_bytes().replace("ἀνὴρ".encode(), "ἀνήρ".encode()))
    result = sources.greek_evidence("ps001")
    assert result["available"] is False
    assert result["by_mt_unit"] == {}
    assert "could not be verified" in result["message"]


def test_policy_block_never_falls_back_to_the_preview(staged, monkeypatch):
    blocked = {"by_mt_unit": {}, "available": False, "state": "blocked", "message": "blocked"}
    monkeypatch.setattr(sources, "_released_greek_evidence", lambda _: blocked)
    assert sources.greek_evidence("ps001") == blocked


def test_owner_approval_binds_the_manifest_hash_and_is_audited(staged, tmp_path):
    record = preview.approve_preview(
        "swete1896.text", "r0001", reviewer_id="owner-1", rationale="Owner sample checked"
    )
    stored = json.loads(
        (tmp_path / "content" / "study_snapshots" / "preview.json").read_text(encoding="utf-8")
    )
    assert (
        stored["manifest_sha256"]
        == hashlib.sha256((staged / "package.json").read_bytes()).hexdigest()
    )
    assert (stored["role"], stored["decision"], stored["scope"]) == (
        "owner",
        "approve",
        "local_display_preview",
    )
    audits = list((tmp_path / "content" / "audit" / "packages").glob("greek_preview.*.json"))
    audit = next(
        json.loads(a.read_text(encoding="utf-8"))
        for a in audits
        if json.loads(a.read_text(encoding="utf-8"))["audit_id"] == record["audit_id"]
    )
    assert audit["after_hash"] == file_hash(stored)
    assert set(stored) == {
        "package_id",
        "package_revision",
        "source_id",
        "manifest_sha256",
        "scope",
        "role",
        "reviewer_id",
        "decision",
        "rationale",
    }


def test_warm_preview_rechecks_locked_file_bytes(staged):
    assert preview.load_preview() is not None
    unit_file = next((staged / "psalms").rglob("*.json"))
    unit_file.write_bytes(unit_file.read_bytes() + b" ")
    with pytest.raises(ValueError, match="changed since staging"):
        preview.load_preview()


@pytest.mark.parametrize("decision", ["withdraw", "request_changes"])
def test_warm_preview_respects_owner_withdrawal(staged, tmp_path, decision):
    assert preview.load_preview() is not None
    path = tmp_path / "content" / "study_snapshots" / "preview.json"
    approval = json.loads(path.read_text(encoding="utf-8"))
    approval["decision"] = decision
    path.write_text(json.dumps(approval), encoding="utf-8")
    assert preview.load_preview() is None


@pytest.mark.parametrize(
    ("field", "value"),
    [("scope", "release"), ("role", "Greek"), ("reviewer_id", " "), ("decision", "yes")],
)
def test_invalid_approval_cannot_display_text(staged, tmp_path, field, value):
    path = tmp_path / "content" / "study_snapshots" / "preview.json"
    approval = json.loads(path.read_text(encoding="utf-8"))
    approval[field] = value
    path.write_text(json.dumps(approval), encoding="utf-8")
    with pytest.raises(ValueError, match="approval"):
        preview.load_preview()


@pytest.mark.parametrize("identity", ["../outside", "C:/outside", "..\\outside", "/outside"])
def test_staged_identity_cannot_escape_the_workspace(tmp_path, monkeypatch, identity):
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="Unsafe"):
        preview.staged_package_dir(identity, "r0001")
    with pytest.raises(ValueError, match="Unsafe"):
        preview.staged_package_dir("swete1896.text", identity)


def test_manifest_file_paths_cannot_escape_staging(staged, tmp_path):
    manifest_path = staged / "package.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["path"] = "../outside"
    manifest_path.write_bytes(canonical_bytes(manifest))
    path = tmp_path / "content" / "study_snapshots" / "preview.json"
    approval = json.loads(path.read_text(encoding="utf-8"))
    approval["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    path.write_text(json.dumps(approval), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe package path"):
        preview.load_preview()


def test_current_explicit_policy_denial_blocks_a_warm_preview(staged, tmp_path):
    assert preview.load_preview() is not None
    policy = {
        "schema_version": "1.0",
        "policy_revision_id": "revoked-r2",
        "sources": [
            {
                "source_id": "swete1896",
                "components": {
                    "text": {
                        "status": "revoked",
                        "capabilities": dict.fromkeys(
                            ("display", "export", "generation", "dictionary", "analysis"), False
                        ),
                        "approvals": [],
                    }
                },
            }
        ],
    }
    (tmp_path / "content" / "source_registry.json").write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(LicensePolicyError):
        preview.load_preview()
    blocked = sources.greek_evidence("ps001")
    assert blocked["state"] == "blocked"
    assert blocked["by_mt_unit"] == {}
    with pytest.raises(LicensePolicyError):
        preview.approve_preview(
            "swete1896.text", "r0001", reviewer_id="owner-1", rationale="Still display only"
        )
