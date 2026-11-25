from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import review_migration_service as migration
from app.services.review_payload_service import review_payload_digest, review_policy_revision

pytestmark = pytest.mark.no_seeded_repo
REPO = Path(__file__).resolve().parents[2]
TARGET = "rnd.ps001.v001.a.literal.alt.0001"


def _unit() -> dict[str, Any]:
    return {
        "unit_id": "ps001.v001.a",
        "psalm_id": "ps001",
        "renderings": [
            {
                "rendering_id": TARGET,
                "unit_id": "ps001.v001.a",
                "layer": "literal",
                "status": "proposed",
                "text": "Authored fixture draft",
                "target_spans": [],
                "provenance": {"source_ids": ["fixture"]},
                "review_signoff": {},
            }
        ],
        "tokens": [],
        "alignments": [],
        "review_decisions": [],
    }


def _legacy(index: int = 1) -> dict[str, Any]:
    return {
        "decision_id": f"rev.ps001.v001.a.{index:04}",
        "target_id": TARGET,
        "reviewer": "Fixture display name",
        "reviewer_role": "Hebrew reviewer",
        "decision": "approve",
        "timestamp": "2026-11-05T12:00:00Z",
        "notes": "PRIVATE REVIEW NOTES MUST NOT APPEAR IN PREVIEW",
    }


def _project() -> dict[str, Any]:
    return {
        "review_policy": {
            "canonical_required_approvals": 2,
            "alternate_required_approvals": 1,
            "release_required_role": "release reviewer",
            "reviewer_roles": ["Hebrew reviewer", "release reviewer"],
        },
        "source_manifests": [],
    }


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _workspace(root: Path, unit: dict[str, Any] | None = None) -> Path:
    _write(root / "content/project.json", _project())
    _write(root / "content/source_registry.json", {"sources": []})
    target = root / "content/psalms/ps001/ps001.v001.a.json"
    _write(target, _unit() if unit is None else unit)
    return target


def _snapshot(root: Path) -> dict[str, bytes | None]:
    return {
        path.relative_to(root).as_posix(): None if path.is_dir() else path.read_bytes()
        for path in sorted(root.rglob("*"))
    }


def _cli(root: Path, *, explicit_root: bool = True) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, ALEPHTAV_ROOT_DIR=str(root), PYTHONDONTWRITEBYTECODE="1")
    args = [sys.executable, "-B", "-m", "app.cli", "preview-review-migration"]
    if explicit_root:
        env["ALEPHTAV_ROOT_DIR"] = str(root.parent / "unused-environment-root")
        args += ["--root", str(root)]
    return subprocess.run(
        args, cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60
    )


@pytest.mark.parametrize("existing", [False, True])
def test_fresh_cli_missing_or_empty_root_never_creates_files(
    tmp_path: Path, existing: bool
) -> None:
    root = tmp_path / "uninitialized"
    if existing:
        root.mkdir()
    result = _cli(root, explicit_root=existing)

    assert result.returncode == 1, result.stderr
    report = json.loads(result.stdout)
    assert report["scan_complete"] is False
    assert report["counts_for_publication"] is False
    assert (list(root.iterdir()) == []) if existing else not root.exists()
    assert not (tmp_path / "unused-environment-root").exists()


def test_cli_is_deterministic_and_does_not_write_sentinels_or_caches(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    unit = _unit()
    unit["review_decisions"] = [_legacy()]
    unit["renderings"][0]["review_signoff"] = {
        "approval_count": 99,
        "publication_ready": True,
        "release_signoff": {"reviewer": "CLAIMED CACHED REVIEWER", "role": "release reviewer"},
    }
    _workspace(root, unit)
    _write(root / "data/derived/caches/sentinel.json", {"keep": "unchanged"})
    _write(root / "reports/sentinel.json", {"keep": "unchanged"})
    before = _snapshot(root)

    first, second = _cli(root), _cli(root)

    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout
    assert _snapshot(root) == before
    report = json.loads(first.stdout)
    assert report["scan_complete"] is True
    assert report["summary"]["legacy_decisions"] == 1
    assert report["summary"]["cached_authority_claims"] == 1
    assert {row["status"] for row in report["records"]} == {
        "legacy_requires_reattestation",
        "cached_summary_not_review_evidence",
    }
    assert all(row["counts_for_publication"] is False for row in report["records"])
    assert all(len(row["observed_sha256"]) == 64 for row in report["files"])
    for forbidden in (
        "payload_digest",
        "policy_revision",
        "principal",
        "PRIVATE REVIEW NOTES",
        "CLAIMED CACHED REVIEWER",
        "Authored fixture draft",
    ):
        assert forbidden not in first.stdout


def test_malformed_orphan_duplicate_and_future_records_are_reported(tmp_path: Path) -> None:
    unit = _unit()
    orphan = {**_legacy(2), "target_id": "../../outside-secret.json"}
    future = {**_legacy(3), "contract_version": 99}
    unit["review_decisions"] = [_legacy(), deepcopy(_legacy()), orphan, future, "bad record"]
    unit["renderings"].append(deepcopy(unit["renderings"][0]))
    path = _workspace(tmp_path, unit)
    (path.parent / "ps001.v002.a.json").write_bytes(b'{"unit_id":')
    (path.parent / "ps001.v003.a.json").write_bytes(b"[]")
    _write(tmp_path / "outside-secret.json", {"secret": "DO NOT READ AS AN ID PATH"})
    before = _snapshot(tmp_path)

    report = migration.preview_review_migration(tmp_path)

    assert report["scan_complete"] is False
    codes = {row["code"] for row in report["diagnostics"]}
    assert {
        "malformed_json",
        "expected_object",
        "duplicate_decision_id",
        "duplicate_target_id",
        "ambiguous_target",
        "orphan_target",
        "unsupported_contract_version",
    } <= codes
    assert report["summary"]["invalid_decisions"] == 2
    assert _snapshot(tmp_path) == before
    assert "DO NOT READ AS AN ID PATH" not in json.dumps(report)
    assert not any(row["path"] == "outside-secret.json" for row in report["files"])


def test_versioned_bindings_remain_unverified_and_mismatches_remain_visible(tmp_path: Path) -> None:
    unit, project, registry = _unit(), _project(), {"sources": []}
    current = {
        **_legacy(),
        "contract_version": 2,
        "principal": {"principal_id": "fixture.person", "kind": "human"},
        "channel": "ui",
        "payload_digest": review_payload_digest(unit, TARGET, project),
        "policy_revision": review_policy_revision(unit, TARGET, project, registry),
    }
    wrong_payload = {
        **deepcopy(current),
        "decision_id": "rev.ps001.v001.a.0002",
        "payload_digest": {"version": 2, "algorithm": "sha256", "value": "0" * 64},
    }
    wrong_policy = {
        **deepcopy(current),
        "decision_id": "rev.ps001.v001.a.0003",
        "policy_revision": "0" * 64,
    }
    unit["review_decisions"] = [current, wrong_payload, wrong_policy]
    _workspace(tmp_path, unit)

    report = migration.preview_review_migration(tmp_path)

    assert report["scan_complete"] is True
    assert {row["status"] for row in report["records"] if row["kind"] == "review_decision"} == {
        "binding_current_unverified",
        "payload_mismatch",
        "policy_mismatch",
    }
    assert report["summary"]["versioned_decisions"] == 3
    assert all(row["counts_for_publication"] is False for row in report["records"])


def test_missing_policy_does_not_bootstrap_or_invent_binding(tmp_path: Path) -> None:
    unit = _unit()
    unit["review_decisions"] = [
        {
            **_legacy(),
            "contract_version": 2,
            "principal": {"principal_id": "fixture.person", "kind": "human"},
            "channel": "ui",
            "payload_digest": {"version": 2, "algorithm": "sha256", "value": "0" * 64},
            "policy_revision": "0" * 64,
        }
    ]
    _workspace(tmp_path, unit)
    _write(tmp_path / "content/project.json", {})
    before = _snapshot(tmp_path)

    report = migration.preview_review_migration(tmp_path)

    assert report["scan_complete"] is False
    assert "binding_unavailable" in {row["status"] for row in report["records"]}
    assert "binding_context_unavailable" in {row["code"] for row in report["diagnostics"]}
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("raw", [b"\xff", b'{"x": 1, "x": 2}', b'{"x": NaN}'])
def test_malformed_context_is_inventory_error_without_writes(tmp_path: Path, raw: bytes) -> None:
    _workspace(tmp_path)
    (tmp_path / "content/project.json").write_bytes(raw)
    before = _snapshot(tmp_path)

    report = migration.preview_review_migration(tmp_path)

    assert report["scan_complete"] is False
    assert "malformed_json" in {row["code"] for row in report["diagnostics"]}
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "relative", ["content/project.json", "content/source_registry.json", "content/psalms/ps001"]
)
def test_reparse_paths_are_refused_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    _workspace(tmp_path)
    forbidden = tmp_path / relative
    original_lstat, original_open = Path.lstat, Path.open

    def reparse_lstat(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path == forbidden:
            return SimpleNamespace(st_mode=original_lstat(path).st_mode, st_file_attributes=0x400)
        return original_lstat(path, *args, **kwargs)

    def guarded_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        assert path != forbidden and forbidden not in path.parents
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", reparse_lstat)
    monkeypatch.setattr(Path, "open", guarded_open)

    report = migration.preview_review_migration(tmp_path)

    assert report["scan_complete"] is False
    assert "reparse_or_symlink_path" in {row["code"] for row in report["diagnostics"]}


def test_no_apply_option_is_exposed(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    _workspace(root)
    before = _snapshot(root)
    env = dict(os.environ, ALEPHTAV_ROOT_DIR=str(root), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-B", "-m", "app.cli", "preview-review-migration", "--apply"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode != 0
    assert _snapshot(root) == before


def test_invalid_oversized_notes_do_not_leak_into_preview(tmp_path: Path) -> None:
    unit = _unit()
    unit["review_decisions"] = [
        {
            **_legacy(),
            "contract_version": 2,
            "principal": {"principal_id": "fixture.person", "kind": "human"},
            "channel": "ui",
            "payload_digest": {"version": 2, "algorithm": "sha256", "value": "0" * 64},
            "policy_revision": "0" * 64,
            "notes": "NEVER PRINT THIS SECRET REVIEW SENTINEL " * 500,
        }
    ]
    _workspace(tmp_path, unit)

    report = migration.preview_review_migration(tmp_path)

    assert report["scan_complete"] is False
    assert report["summary"]["invalid_decisions"] == 1
    assert "SECRET REVIEW SENTINEL" not in json.dumps(report)


def test_symlink_to_an_outside_file_is_not_opened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "workspace"
    unit_path = _workspace(root)
    outside = tmp_path / "outside.json"
    _write(outside, {"secret": "OUTSIDE FILE MUST NOT BE READ"})
    link = unit_path.parent / "ps001.v002.a.json"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks is unavailable on this host")
    original_open = Path.open

    def guarded_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        assert path not in (link, outside)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    report = migration.preview_review_migration(root)

    assert report["scan_complete"] is False
    assert "reparse_or_symlink_path" in {row["code"] for row in report["diagnostics"]}
    assert "OUTSIDE FILE MUST NOT BE READ" not in json.dumps(report)


def test_deep_binding_context_returns_structured_incomplete_preview(tmp_path: Path) -> None:
    unit = _unit()
    features: dict[str, Any] = {}
    cursor = features
    for _ in range(600):
        cursor["nested"] = {}
        cursor = cursor["nested"]
    unit["tokens"] = [{"token_id": "ps001.v001.t001", "compiler_features": features}]
    unit["review_decisions"] = [
        {
            **_legacy(),
            "contract_version": 2,
            "principal": {"principal_id": "fixture.person", "kind": "human"},
            "channel": "ui",
            "payload_digest": {"version": 2, "algorithm": "sha256", "value": "0" * 64},
            "policy_revision": "0" * 64,
        }
    ]
    _workspace(tmp_path, unit)
    before = _snapshot(tmp_path)

    report = migration.preview_review_migration(tmp_path)

    assert report["scan_complete"] is False
    assert "binding_context_unavailable" in {row["code"] for row in report["diagnostics"]}
    assert "binding_unavailable" in {row["status"] for row in report["records"]}
    assert _snapshot(tmp_path) == before


def test_missing_source_authority_is_incomplete_without_manifest_fallback(tmp_path: Path) -> None:
    unit = _unit()
    unit["review_decisions"] = [
        {
            **_legacy(),
            "contract_version": 2,
            "principal": {"principal_id": "fixture.person", "kind": "human"},
            "channel": "ui",
            "payload_digest": {"version": 2, "algorithm": "sha256", "value": "0" * 64},
            "policy_revision": "0" * 64,
        }
    ]
    _workspace(tmp_path, unit)
    registry = tmp_path / "content/source_registry.json"
    registry.unlink()
    before = _snapshot(tmp_path)

    report = migration.preview_review_migration(tmp_path)

    assert report["scan_complete"] is False
    assert any(
        row["path"] == "content/source_registry.json" and row["code"] == "missing_path"
        for row in report["diagnostics"]
    )
    assert "binding_unavailable" in {row["status"] for row in report["records"]}
    assert _snapshot(tmp_path) == before
    assert not registry.exists()
