from __future__ import annotations

import copy
import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from jsonschema import ValidationError as SchemaValidationError

from app.core.config import get_settings
from app.core.errors import ValidationError
from app.core.ids import parse_unit_id, rendering_id, unit_id_from_entity_id
from app.db import session
from app.db.models import JOB_TABLE_SQL, LEXICAL_STATE_TABLE_SQL
from app.services import concordance_service, registry_service, source_capability_service
from app.services import study_snapshot_service as snapshots
from app.services.foundation_contract_service import validate_greek_unit, workspace_path
from app.services.immutable_file_service import sha256_file
from app.services.mt_source_snapshot_service import capture_mt_source_snapshot
from app.services.package_install_service import install_staged_package

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    shutil.copytree(Path(__file__).resolve().parents[2] / "schemas", tmp_path / "schemas")
    registry_service.invalidate_summary_cache()
    return tmp_path


def greek_unit() -> dict:
    return {
        "schema_version": "1.0",
        "unit_id": "lxx.swete1896.r0001.ps001.v001.a",
        "corpus": "lxx",
        "edition_id": "swete1896",
        "text_revision_id": "r0001",
        "psalm_id": "ps001",
        "ref": "Psalm 1:1",
        "source_greek": "μακάριος",
        "tokens": [
            {
                "token_id": "lxx.swete1896.r0001.ps001.v001.t001",
                "position": 1,
                "surface": "μακάριος",
                "normalized": "μακάριος",
                "text_span": {"start": 0, "end": 8},
                "source_locator": {"file": "authored.txt", "locator": "1:1", "fragments": []},
            }
        ],
    }


def mt_unit() -> dict:
    return {
        "unit_id": "ps001.v001.a",
        "psalm_id": "ps001",
        "ref": "Psalm 1:1",
        "status": "draft",
        "source_hebrew": "א",
        "tokens": [],
    }


def policy(package_hashes: dict[str, str] | None = None) -> dict:
    caps = {name: name != "generation" for name in source_capability_service.CAPABILITIES}
    digest = source_capability_service.approval_payload_hash(
        "fixture.greek", "text", caps, package_hashes
    )
    return {
        "schema_version": "1.0",
        "policy_revision_id": "authored-test-only",
        "sources": [
            {
                "source_id": "fixture.greek",
                "components": {
                    "text": {
                        "status": "approved",
                        "capabilities": caps,
                        "package_hashes": package_hashes or {},
                        "approvals": [
                            {
                                "role": role,
                                "reviewer_id": role + ":fixture",
                                "decision": "approve",
                                "payload_hash": digest,
                            }
                            for role in ("owner", "license")
                        ],
                    }
                },
            }
        ],
    }


def install_fixture(workspace: Path) -> dict:
    staged = workspace / "staging"
    staged.mkdir()
    unit = greek_unit()
    text = registry_service.deterministic_json(unit).encode()
    (staged / "unit.json").write_bytes(text)
    license_bytes = b"Authored test fixture license; no upstream source approval.\n"
    (staged / "LICENSE.txt").write_bytes(license_bytes)
    manifest = {
        "schema_version": "1.0",
        "package_id": "fixture-greek-r0001",
        "source_id": "fixture.greek",
        "package_revision": "r0001",
        "kind": "source_text",
        "files": [
            {
                "path": "unit.json",
                "sha256": sha256_file(staged / "unit.json"),
                "size_bytes": len(text),
            },
            {
                "path": "LICENSE.txt",
                "sha256": sha256_file(staged / "LICENSE.txt"),
                "size_bytes": len(license_bytes),
            },
        ],
        "dependencies": [],
        "review_status": "approved",
        "provenance": {
            "upstream_url": "https://example.invalid/authored",
            "upstream_revision": "fixture",
            "license": "Authored test fixture",
            "license_text_sha256": sha256_file(staged / "LICENSE.txt"),
            "attribution": "Synthetic test data; no real source approval",
        },
    }
    registry_service.write_json(staged / "package.json", manifest)
    return install_staged_package(
        staged,
        "content/lxx/editions/swete1896/r0001",
        created_by="test:fixture",
        rationale="Authored offline test",
    )


def descriptor(workspace: Path) -> dict:
    package = install_fixture(workspace)
    registry_service.write_json(
        workspace / "content" / "source_registry.json",
        policy({package["package_id"]: package["sha256"]}),
    )
    path = workspace / "data" / "derived" / "indexes" / "catalog.json"
    registry_service.write_json(path, {"units": [greek_unit()], "analyses": [], "entries": []})
    result = {
        "schema_version": "1.0",
        "predecessor_id": None,
        "edition_id": "swete1896",
        "text_revision_id": "r0001",
        "policy_revision_id": source_capability_service.policy_revision(),
        "source_ids": ["fixture.greek"],
        "packages": [{key: package[key] for key in ("package_id", "path", "sha256")}],
        "catalog": {"path": path.relative_to(workspace).as_posix(), "sha256": sha256_file(path)},
        "mt_source_snapshot": capture_mt_source_snapshot([mt_unit()]),
    }
    result["study_snapshot_id"] = snapshots.snapshot_id(result)
    return result


@pytest.mark.parametrize("edition,revision", [("swete1896", "r0001"), ("other-edition", "r0002")])
def test_qualified_id_round_trip_and_paths(workspace: Path, edition: str, revision: str) -> None:
    value = f"lxx.{edition}.{revision}.ps023.v001.a"
    identity = parse_unit_id(value, require_versioned=True)
    assert identity.unit_id == value
    assert identity.psalm_id == "ps023"
    assert (
        unit_id_from_entity_id("rendering_id", rendering_id(value, "literal", "alt", [])) == value
    )
    assert (
        registry_service.unit_path(value)
        == workspace
        / "content"
        / "lxx"
        / "editions"
        / edition
        / revision
        / "psalms"
        / "ps023"
        / f"{value}.json"
    )
    assert (
        registry_service.unit_path("ps023.v001.a")
        == workspace / "content/psalms/ps023/ps023.v001.a.json"
    )
    with pytest.raises(ValueError, match="explicit edition"):
        registry_service.unit_path("lxx.ps023.v001.a")


def test_greek_contract_rejects_hebrew_fields_and_invalid_spans(workspace: Path) -> None:
    unit = greek_unit()
    validate_greek_unit(unit)
    unit["source_hebrew"] = "fake"
    with pytest.raises(SchemaValidationError):
        validate_greek_unit(unit)
    del unit["source_hebrew"]
    unit["tokens"][0]["text_span"]["end"] = 7
    with pytest.raises(ValueError, match="position/span"):
        validate_greek_unit(unit)


def test_source_policy_latest_decision_and_legacy_isolation(workspace: Path) -> None:
    registry_service.write_json(workspace / "content/source_registry.json", policy())
    source_capability_service.require_capability("fixture.greek", "display")
    value = policy()
    value["sources"][0]["components"]["text"]["approvals"].append(
        {**value["sources"][0]["components"]["text"]["approvals"][0], "decision": "withdraw"}
    )
    registry_service.write_json(workspace / "content/source_registry.json", value)
    with pytest.raises(source_capability_service.SourceUnavailableError):
        source_capability_service.require_capability("fixture.greek", "display")
    registry_service.bootstrap_project()
    assert not source_capability_service.effective_capabilities("lxx")["generation"]
    assert not source_capability_service.effective_capabilities("macula", "greek")["display"]
    assert source_capability_service.effective_capabilities("macula")["display"]
    assert not list((workspace / "data/raw").rglob("*"))


def test_install_is_inactive_idempotent_and_conflicting_revision_fails(workspace: Path) -> None:
    first = install_fixture(workspace)
    second = install_staged_package(
        workspace / "staging",
        "content/lxx/editions/swete1896/r0001",
        created_by="test:retry",
        rationale="Retry fixture",
    )
    assert first["installed"] and not second["installed"]
    assert not first["active"]
    assert not (get_settings().indexes_dir / "active_study_snapshot.json").exists()
    target = workspace / "staging/package.json"
    manifest = json.loads(target.read_text())
    manifest["provenance"]["attribution"] = "changed bytes"
    registry_service.write_json(target, manifest)
    with pytest.raises(ValueError, match="checksum reuse"):
        install_staged_package(
            workspace / "staging",
            "content/lxx/editions/swete1896/r0001",
            created_by="test",
            rationale="Conflict",
        )


def test_snapshot_cas_retained_revocation_and_fault_safety(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = descriptor(workspace)
    snapshots.publish_snapshot(first, None, created_by="test", rationale="Publish authored fixture")
    with pytest.raises(ValidationError, match="Stale"):
        snapshots.publish_snapshot(first, None, created_by="test", rationale="Stale builder")
    second = copy.deepcopy(first)
    second["predecessor_id"] = first["study_snapshot_id"]
    second["study_snapshot_id"] = snapshots.snapshot_id(second)
    real_write = snapshots.atomic_write

    def fail_pointer(path, data):
        if path.name == "active_study_snapshot.json":
            raise OSError("simulated disk full")
        return real_write(path, data)

    monkeypatch.setattr(snapshots, "atomic_write", fail_pointer)
    with pytest.raises(OSError, match="disk full"):
        snapshots.publish_snapshot(
            second, first["study_snapshot_id"], created_by="test", rationale="Fault"
        )
    assert snapshots.active_snapshot()["study_snapshot_id"] == first["study_snapshot_id"]
    value = policy()
    value["sources"][0]["components"]["text"]["status"] = "revoked"
    registry_service.write_json(workspace / "content/source_registry.json", value)
    with pytest.raises(source_capability_service.SourceUnavailableError):
        snapshots.active_snapshot(first["study_snapshot_id"])


def test_source_snapshot_survives_live_source_change(workspace: Path) -> None:
    unit = mt_unit()
    first = capture_mt_source_snapshot([unit])
    unit["source_hebrew"] = "ב"
    second = capture_mt_source_snapshot([unit])
    assert first["snapshot_id"] != second["snapshot_id"]
    original = json.loads(workspace_path(first["path"]).read_text(encoding="utf-8"))
    assert original["units"][0]["source_hebrew"] == "א"


def test_last_good_recovery_rechecks_current_policy(workspace: Path) -> None:
    first = descriptor(workspace)
    snapshots.publish_snapshot(first, None, created_by="test", rationale="First fixture")
    second = copy.deepcopy(first)
    second["predecessor_id"] = first["study_snapshot_id"]
    second["study_snapshot_id"] = snapshots.snapshot_id(second)
    snapshots.publish_snapshot(
        second, first["study_snapshot_id"], created_by="test", rationale="Next fixture"
    )
    pointer = get_settings().indexes_dir / "active_study_snapshot.json"
    pointer.write_text("broken pointer", encoding="utf-8")
    result = snapshots.recover_active_snapshot(created_by="test", rationale="Injected corruption")
    assert result["study_snapshot_id"] == first["study_snapshot_id"]
    value = policy()
    value["sources"][0]["components"]["text"]["status"] = "revoked"
    registry_service.write_json(workspace / "content/source_registry.json", value)
    with pytest.raises(source_capability_service.SourceUnavailableError):
        snapshots.recover_active_snapshot(
            created_by="test", rationale="Revocation is not corruption"
        )


def test_source_wide_approval_cannot_activate_an_unapproved_package(workspace: Path) -> None:
    value = descriptor(workspace)
    registry_service.write_json(workspace / "content/source_registry.json", policy())
    source_capability_service.require_capability("fixture.greek", "display")
    with pytest.raises(source_capability_service.SourceUnavailableError, match="package revision"):
        snapshots.verify_snapshot(value)


@pytest.mark.parametrize("defect", ["pending", "unpackaged_license"])
def test_generic_install_cannot_bypass_study_release_or_license_closure(
    workspace: Path, defect: str
) -> None:
    value = descriptor(workspace)
    reference = value["packages"][0]
    path = workspace_path(reference["path"])
    manifest = registry_service.read_json(path)
    if defect == "pending":
        manifest["review_status"] = "pending"
    else:
        manifest["files"] = [item for item in manifest["files"] if item["path"] != "LICENSE.txt"]
    registry_service.write_json(path, manifest)
    reference["sha256"] = sha256_file(path)
    registry_service.write_json(
        workspace / "content/source_registry.json",
        policy({reference["package_id"]: reference["sha256"]}),
    )
    value["policy_revision_id"] = source_capability_service.policy_revision()
    value["study_snapshot_id"] = snapshots.snapshot_id(value)
    with pytest.raises(ValidationError, match="approved release|license text hash"):
        snapshots.verify_snapshot(value)


def test_operational_migration_is_explicit_verified_and_idempotent(workspace: Path) -> None:
    settings = get_settings()
    with sqlite3.connect(settings.db_path) as old:
        old.executescript(JOB_TABLE_SQL + LEXICAL_STATE_TABLE_SQL)
        old.execute(
            "INSERT INTO lexical_card_state VALUES ('global', 'ps001.v001.t001', 'fixture')"
        )
        old.execute(
            "INSERT INTO generation_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "job.0123456789ab",
                "ps001.v001.a",
                "literal",
                "completed",
                "input",
                "local-fixture",
                "v1",
                0,
                "{}",
                '{"result":"retained"}',
            ),
        )
    with pytest.raises(RuntimeError, match="Stop API"):
        session.migrate_operational_state()
    with session.get_operational_connection() as legacy:
        assert legacy.execute("SELECT output_payload FROM generation_jobs").fetchone()[0] == (
            '{"result":"retained"}'
        )
    assert not settings.operational_db_path.exists()
    assert session.migrate_operational_state(writers_quiesced=True) == {"migrated": 2}
    assert session.migrate_operational_state(writers_quiesced=True) == {"migrated": 0}
    with session.get_operational_connection() as current:
        assert (
            current.execute("SELECT token_id FROM lexical_card_state").fetchone()[0]
            == "ps001.v001.t001"
        )
        assert (
            current.execute("SELECT output_payload FROM generation_jobs").fetchone()[0]
            == '{"result":"retained"}'
        )
    assert settings.db_path.exists()
    assert (settings.operational_db_path.parent / "legacy-workbench.backup.sqlite3").exists()


def test_catalog_build_failure_preserves_reader_and_operational_state(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(registry_service, "list_units", lambda: [mt_unit()])
    concordance_service.rebuild_indexes()
    with session.get_operational_connection() as state:
        state.execute("INSERT INTO lexical_card_state VALUES ('global', NULL, 'fixture')")
    with session.get_connection() as reader:
        invalid = mt_unit()
        del invalid["source_hebrew"]
        monkeypatch.setattr(registry_service, "list_units", lambda: [invalid])
        with pytest.raises(KeyError):
            concordance_service.rebuild_indexes()
        assert reader.execute("SELECT COUNT(*) FROM unit_index").fetchone()[0] == 1
    with session.get_connection() as reader:
        assert reader.execute("SELECT COUNT(*) FROM unit_index").fetchone()[0] == 1
    with session.get_operational_connection() as state:
        assert state.execute("SELECT updated_at FROM lexical_card_state").fetchone()[0] == "fixture"


@pytest.mark.parametrize(
    "path", ["../escape", "data/raw/new/file.json", "C:/escape", "content\\bad"]
)
def test_package_paths_cannot_escape_or_write_raw(workspace: Path, path: str) -> None:
    with pytest.raises(ValueError):
        workspace_path(path)
