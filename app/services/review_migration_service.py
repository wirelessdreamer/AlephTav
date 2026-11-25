"""Read stored review history without bootstrapping, hydrating, or migrating it.

Binding readiness requires readable project and source-registry files. Missing
authority context is incomplete, even where legacy runtime readers permit fallback;
this preview never substitutes manifest/default authority or changes that runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections import Counter
from pathlib import Path
from typing import Any

from app.core.errors import ValidationError

PSALM_DIRECTORY = re.compile(r"ps[0-9]{3}\Z")
UNIT_ID = re.compile(r"ps[0-9]{3}\.v[0-9]{3}\.[a-z]\Z")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z")
MAX_JSON_BYTES = 16 * 1024 * 1024
AUTHORITY_FIELDS = (
    "approval_count",
    "alternate_approval_count",
    "approvers",
    "alternate_approvers",
    "eligible_for_alternate",
    "eligible_for_canonical",
    "publication_ready",
    "has_release_signoff",
    "release_signoff",
)


def _diagnostic(report: dict[str, Any], path: str, pointer: str, code: str) -> None:
    report["diagnostics"].append({"path": path, "pointer": pointer, "code": code})
    report["scan_complete"] = False


def _bounded_path(root: Path, path: Path, report: dict[str, Any]) -> os.stat_result | None:
    relative = path.relative_to(root)
    current = root
    try:
        info = root.stat()
    except OSError:
        _diagnostic(report, relative.as_posix(), "", "unreadable_path")
        return None
    for part in relative.parts:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            _diagnostic(report, relative.as_posix(), "", "missing_path")
            return None
        except OSError:
            _diagnostic(report, relative.as_posix(), "", "unreadable_path")
            return None
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            _diagnostic(report, relative.as_posix(), "", "reparse_or_symlink_path")
            return None
        try:
            contained = current.resolve().is_relative_to(root)
        except (OSError, RuntimeError):
            contained = False
        if not contained:
            _diagnostic(report, relative.as_posix(), "", "outside_workspace")
            return None
    return info


def _children(root: Path, path: Path, report: dict[str, Any]) -> list[Path]:
    info = _bounded_path(root, path, report)
    if info is None:
        return []
    if not stat.S_ISDIR(info.st_mode):
        _diagnostic(report, path.relative_to(root).as_posix(), "", "expected_directory")
        return []
    try:
        return sorted(path.iterdir(), key=lambda item: item.name)
    except OSError:
        _diagnostic(report, path.relative_to(root).as_posix(), "", "unreadable_directory")
        return []


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON number")


def _read_object(
    root: Path, path: Path, kind: str, report: dict[str, Any]
) -> dict[str, Any] | None:
    relative = path.relative_to(root).as_posix()
    info = _bounded_path(root, path, report)
    if info is None:
        return None
    if not stat.S_ISREG(info.st_mode):
        _diagnostic(report, relative, "", "expected_regular_file")
        return None
    if info.st_size > MAX_JSON_BYTES:
        _diagnostic(report, relative, "", "file_size_limit")
        return None
    try:
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                _diagnostic(report, relative, "", "changed_during_scan")
                return None
            raw = stream.read(MAX_JSON_BYTES + 1)
            after = os.fstat(stream.fileno())
    except OSError:
        _diagnostic(report, relative, "", "unreadable_file")
        return None
    if len(raw) > MAX_JSON_BYTES:
        _diagnostic(report, relative, "", "file_size_limit")
        return None
    if (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        _diagnostic(report, relative, "", "changed_during_scan")
        return None
    report["files"].append(
        {"path": relative, "kind": kind, "observed_sha256": hashlib.sha256(raw).hexdigest()}
    )
    try:
        payload = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except (UnicodeError, ValueError, RecursionError):
        _diagnostic(report, relative, "", "malformed_json")
        return None
    if not isinstance(payload, dict):
        _diagnostic(report, relative, "", "expected_object")
        return None
    return payload


def _array(
    obj: dict[str, Any], key: str, report: dict[str, Any], path: str, pointer: str
) -> list[Any]:
    value = obj.get(key, [])
    if not isinstance(value, list):
        _diagnostic(report, path, pointer + "/" + key, "expected_array")
        return []
    return value


def _observed_ids(record: dict[str, Any], *fields: str) -> dict[str, str]:
    return {
        field: record[field]
        for field in fields
        if isinstance(record.get(field), str) and SAFE_ID.fullmatch(record[field])
    }


def _arrangements(meta: dict[str, Any], path: str, report: dict[str, Any], counts: Counter) -> None:
    for index, arrangement in enumerate(_array(meta, "arrangements", report, path, "")):
        pointer = f"/arrangements/{index}"
        if not isinstance(arrangement, dict):
            _diagnostic(report, path, pointer, "expected_object")
            continue
        counts["arrangements"] += 1
        for section_index, section in enumerate(
            _array(arrangement, "sections", report, path, pointer)
        ):
            section_pointer = f"{pointer}/sections/{section_index}"
            if not isinstance(section, dict):
                _diagnostic(report, path, section_pointer, "expected_object")
                continue
            for line_index, line in enumerate(
                _array(section, "lines", report, path, section_pointer)
            ):
                line_pointer = f"{section_pointer}/lines/{line_index}"
                if not isinstance(line, dict):
                    _diagnostic(report, path, line_pointer, "expected_object")
                    continue
                counts["arrangement_line_approvals"] += len(
                    _array(line, "approvals", report, path, line_pointer)
                )
        for omission_index, omission in enumerate(
            _array(arrangement, "omissions", report, path, pointer)
        ):
            omission_pointer = f"{pointer}/omissions/{omission_index}"
            if not isinstance(omission, dict):
                _diagnostic(report, path, omission_pointer, "expected_object")
                continue
            counts["arrangement_omission_approvals"] += len(
                _array(omission, "approvals", report, path, omission_pointer)
            )


def _scan_unit(
    unit: dict[str, Any], path: str, report: dict[str, Any], counts: Counter
) -> dict[str, int]:
    targets: Counter[str] = Counter()
    for index, rendering in enumerate(_array(unit, "renderings", report, path, "")):
        pointer = f"/renderings/{index}"
        if not isinstance(rendering, dict):
            _diagnostic(report, path, pointer, "expected_object")
            continue
        counts["renderings"] += 1
        target_id = rendering.get("rendering_id")
        if not isinstance(target_id, str) or not SAFE_ID.fullmatch(target_id):
            _diagnostic(report, path, pointer + "/rendering_id", "invalid_target_id")
        else:
            targets[target_id] += 1
            if targets[target_id] > 1:
                _diagnostic(report, path, pointer + "/rendering_id", "duplicate_target_id")
        if "review_signoff" not in rendering:
            continue
        signoff = rendering["review_signoff"]
        if not isinstance(signoff, dict):
            _diagnostic(report, path, pointer + "/review_signoff", "expected_object")
            continue
        counts["cached_signoffs"] += 1
        claim = any(signoff.get(field) for field in AUTHORITY_FIELDS)
        counts["cached_authority_claims"] += int(claim)
        report["records"].append(
            {
                "path": path,
                "pointer": pointer + "/review_signoff",
                "kind": "cached_signoff",
                "status": "cached_summary_not_review_evidence",
                "claimed_authority": claim,
                "counts_for_publication": False,
                **_observed_ids(rendering, "rendering_id"),
            }
        )
    return dict(targets)


def _scan_decisions(
    unit: dict[str, Any],
    path: str,
    targets: dict[str, int],
    all_targets: Counter,
    seen_decisions: set[str],
    project: dict[str, Any] | None,
    source_registry: dict[str, Any] | None,
    report: dict[str, Any],
    counts: Counter,
) -> None:
    from app.services.review_evidence_service import (
        classify_review_evidence,
        validate_review_decision,
    )
    from app.services.review_payload_service import review_payload_digest, review_policy_revision

    for index, decision in enumerate(_array(unit, "review_decisions", report, path, "")):
        pointer = f"/review_decisions/{index}"
        counts["review_decisions"] += 1
        item = {"path": path, "pointer": pointer, "kind": "review_decision"}
        if not isinstance(decision, dict):
            _diagnostic(report, path, pointer, "expected_object")
            report["records"].append({**item, "status": "invalid", "counts_for_publication": False})
            counts["invalid_decisions"] += 1
            continue
        item.update(_observed_ids(decision, "decision_id", "target_id"))
        decision_id = decision.get("decision_id")
        if isinstance(decision_id, str):
            if decision_id in seen_decisions:
                _diagnostic(report, path, pointer + "/decision_id", "duplicate_decision_id")
            seen_decisions.add(decision_id)
        target_id = decision.get("target_id")
        target_count = targets.get(target_id, 0) if isinstance(target_id, str) else 0
        if target_count == 1 and all_targets[target_id] != 1:
            target_count = all_targets[target_id]
        if target_count != 1:
            code = "ambiguous_target" if target_count > 1 else "orphan_target"
            if target_count == 0 and isinstance(target_id, str) and all_targets[target_id]:
                code = "cross_unit_target"
            _diagnostic(report, path, pointer + "/target_id", code)
        try:
            version = validate_review_decision(decision)
        except (ValidationError, RecursionError):
            code = "invalid_review_decision"
            if "contract_version" in decision and decision["contract_version"] != 2:
                code = "unsupported_contract_version"
            _diagnostic(report, path, pointer, code)
            counts["invalid_decisions"] += 1
            report["records"].append({**item, "status": "invalid", "counts_for_publication": False})
            continue
        digest = None
        policy = None
        counts["legacy_decisions" if version == "legacy" else "versioned_decisions"] += 1
        if (
            version == "v2"
            and project is not None
            and source_registry is not None
            and isinstance(target_id, str)
            and target_count == 1
        ):
            try:
                digest = review_payload_digest(unit, target_id, project)
                policy = review_policy_revision(
                    unit, target_id, project, source_registry=source_registry
                )
            except (ValidationError, KeyError, TypeError, ValueError, RecursionError):
                _diagnostic(report, path, pointer, "binding_context_unavailable")
        elif version == "v2":
            _diagnostic(report, path, pointer, "binding_context_unavailable")
        classification = classify_review_evidence(
            decision, payload_digest=digest, policy_revision=policy
        )
        report["records"].append(
            {**item, "status": classification["status"], "counts_for_publication": False}
        )


def preview_review_migration(root: Path | str | None = None) -> dict[str, Any]:
    """Inventory evidence only; supplied bindings are not publication authorization."""
    report: dict[str, Any] = {
        "preview_version": 1,
        "target_contract_version": 2,
        "scan_complete": True,
        "counts_for_publication": False,
        "arrangement_scope": "informational_only_not_migrated",
        "files": [],
        "records": [],
        "diagnostics": [],
    }
    counts: Counter[str] = Counter(
        dict.fromkeys(
            (
                "unit_files",
                "meta_files",
                "renderings",
                "review_decisions",
                "legacy_decisions",
                "versioned_decisions",
                "invalid_decisions",
                "cached_signoffs",
                "cached_authority_claims",
                "arrangements",
                "arrangement_line_approvals",
                "arrangement_omission_approvals",
            ),
            0,
        )
    )
    report["summary"] = counts
    try:
        selected_root = (
            root
            if root is not None
            else (os.environ.get("ALEPHTAV_ROOT_DIR") or Path(__file__).resolve().parents[2])
        )
        workspace = Path(selected_root).resolve()
    except (OSError, RuntimeError, ValueError):
        _diagnostic(report, ".", "", "invalid_workspace")
        return report
    try:
        valid_workspace = workspace.is_dir()
    except OSError:
        valid_workspace = False
    if not valid_workspace:
        _diagnostic(report, ".", "", "missing_or_invalid_workspace")
        return report
    project = _read_object(workspace, workspace / "content/project.json", "project", report)
    source_registry = _read_object(
        workspace, workspace / "content/source_registry.json", "source_registry", report
    )
    units: list[tuple[str, dict[str, Any], dict[str, int]]] = []
    all_targets: Counter[str] = Counter()
    seen_units: set[str] = set()
    for directory in _children(workspace, workspace / "content/psalms", report):
        if not PSALM_DIRECTORY.fullmatch(directory.name):
            continue
        for path in _children(workspace, directory, report):
            if path.suffix != ".json":
                continue
            is_meta = path.name == directory.name + ".meta.json"
            payload = _read_object(workspace, path, "meta" if is_meta else "unit", report)
            if payload is None:
                continue
            relative = path.relative_to(workspace).as_posix()
            if is_meta:
                counts["meta_files"] += 1
                _arrangements(payload, relative, report, counts)
                continue
            counts["unit_files"] += 1
            unit_id = payload.get("unit_id")
            for field in ("unit_id", "renderings", "review_decisions"):
                if field not in payload:
                    _diagnostic(report, relative, "/" + field, "missing_required_preview_field")
            if (
                not isinstance(unit_id, str)
                or not UNIT_ID.fullmatch(unit_id)
                or path.stem != unit_id
                or not unit_id.startswith(directory.name + ".")
            ):
                _diagnostic(report, relative, "/unit_id", "invalid_or_misplaced_unit_id")
            if isinstance(unit_id, str) and unit_id in seen_units:
                _diagnostic(report, relative, "/unit_id", "duplicate_unit_id")
            if isinstance(unit_id, str):
                seen_units.add(unit_id)
            targets = _scan_unit(payload, relative, report, counts)
            all_targets.update(targets)
            units.append((relative, payload, targets))
    if not counts["unit_files"]:
        _diagnostic(report, "content/psalms", "", "no_unit_files")
    seen_decisions: set[str] = set()
    for relative, payload, targets in units:
        for target_id, count in targets.items():
            if count == 1 and all_targets[target_id] > 1:
                _diagnostic(report, relative, "/renderings", "duplicate_target_id")
        _scan_decisions(
            payload,
            relative,
            targets,
            all_targets,
            seen_decisions,
            project,
            source_registry,
            report,
            counts,
        )
    report["files"].sort(key=lambda item: item["path"])
    report["records"].sort(key=lambda item: (item["path"], item["pointer"], item["kind"]))
    report["diagnostics"].sort(key=lambda item: (item["path"], item["pointer"], item["code"]))
    return report
