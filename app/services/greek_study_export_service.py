"""Fail-closed preparation of a dependency-complete offline study bundle.

No release signoff, source installation, or Greek generation is performed here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.errors import ReleaseValidationError


def availability_record() -> dict[str, Any]:
    from app.core.config import get_settings

    path = get_settings().content_dir / "study_snapshots" / "availability.json"
    if not path.exists():
        return {}
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    return record if isinstance(record, dict) else {}


def availability(descriptor: dict[str, Any]) -> bool:
    from app.core.config import get_settings
    from app.services.registry_service import file_hash
    from app.services.source_capability_service import policy_revision

    record = availability_record()
    current_policy = policy_revision()
    # Release B needs the future accepted-bridge authority. A string claiming a
    # signoff or report is never sufficient to enable a production source.
    if (
        record.get("enabled") is not True
        or record.get("study_snapshot_id") != descriptor["study_snapshot_id"]
        or record.get("policy_revision_id") != current_policy
        or record.get("release") != "A"
    ):
        return False
    root = get_settings().root_dir.resolve()
    reports: dict[str, dict[str, str]] = {}
    for name in ("coverage_report", "expert_review_report"):
        reference = record.get(name)
        if not isinstance(reference, dict):
            return False
        if not isinstance(reference.get("path"), str):
            return False
        path = (root / reference["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return False
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != reference.get("sha256"):
            return False
        try:
            report = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            return False
        if (
            not isinstance(report, dict)
            or report.get("status") != "passed"
            or report.get("study_snapshot_id") != descriptor["study_snapshot_id"]
            or report.get("policy_revision_id") != current_policy
        ):
            return False
        reports[name] = {"path": reference["path"], "sha256": reference["sha256"]}
    expected = file_hash(
        {
            "descriptor_sha256": file_hash(descriptor),
            "policy_revision_id": current_policy,
            "release": "A",
            "audit_files": record.get("audit_files", []),
            **reports,
        }
    )
    latest: dict[str, dict[str, Any]] = {}
    decisions = record.get("review_decisions", [])
    if not isinstance(decisions, list):
        return False
    for decision in decisions:
        if not isinstance(decision, dict) or not isinstance(decision.get("reviewer_id"), str):
            return False
        if not decision["reviewer_id"].strip():
            return False
        latest[decision["reviewer_id"]] = decision
    if any(d.get("decision") == "request_changes" for d in latest.values()):
        return False
    roles: dict[str, set[str]] = {}
    for reviewer, decision in latest.items():
        if decision.get("decision") == "approve" and decision.get("payload_hash") == expected:
            roles.setdefault(decision.get("role", ""), set()).add(reviewer)
    return bool(
        roles.get("owner")
        and roles.get("release reviewer")
        and len(roles.get("Greek reviewer", set())) >= 2
        and policy_revision() == current_policy
    )


def prepare_bundle(snapshot_id: str) -> dict[str, Any]:
    """Validate candidate export closure; reconstruction remains an explicit release gate.

    This helper is not exposed as an export endpoint. It returns no source bytes
    until a separately implemented independent reconstruction contract is available.
    """
    from app.core.config import get_settings
    from app.services.foundation_contract_service import validate_contract
    from app.services.registry_service import file_hash
    from app.services.source_capability_service import (
        policy_revision,
        require_capability,
        require_package_capability,
    )
    from app.services.study_snapshot_service import active_snapshot

    # Capture before any descriptor, release report or permission read.
    current_policy = policy_revision()
    descriptor = active_snapshot(snapshot_id)
    if not availability(descriptor):
        raise ReleaseValidationError("Greek study release availability gates are incomplete")
    if policy_revision() != current_policy:
        raise ReleaseValidationError("Source policy changed while opening export snapshot")
    if descriptor.get("mt_source_snapshot") is not None:
        raise ReleaseValidationError("MT bridge export awaits complete Hebrew provenance closure")
    for source_id in descriptor["source_ids"]:
        require_capability(source_id, "export")
    record = availability_record()
    release_hash = file_hash(record)
    root = get_settings().root_dir.resolve()
    content = root / "content"
    manifests: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    required = {"source_text", "dictionary", "analysis", "lexemes", "crosswalks", "versification"}

    def checked(reference: dict[str, Any], *, base: Path) -> tuple[Path, bytes]:
        path = (base / reference["path"]).resolve()
        if not path.is_relative_to(base.resolve()) or not path.is_file():
            raise ReleaseValidationError("Export dependency escapes its permitted root")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != reference["sha256"]:
            raise ReleaseValidationError("Export dependency checksum changed")
        if "size_bytes" in reference and len(data) != reference["size_bytes"]:
            raise ReleaseValidationError("Export dependency size changed")
        return path, data

    for reference in descriptor["packages"]:
        path, data = checked(reference, base=root)
        if not any(
            path.is_relative_to(content / kind)
            for kind in ("lxx", "lexicons", "lexemes", "versification", "cross_alignments")
        ):
            raise ReleaseValidationError("Source manifest is outside normalized package roots")
        manifest = json.loads(data)
        validate_contract("source_package.schema.json", manifest)
        package_id = reference["package_id"]
        if manifest["package_id"] != package_id or package_id in manifests:
            raise ReleaseValidationError("Duplicate or mismatched export package identity")
        if manifest["source_id"] not in descriptor["source_ids"]:
            raise ReleaseValidationError("Export package source is outside descriptor closure")
        require_package_capability(manifest["source_id"], package_id, reference["sha256"], "export")
        license_found = False
        for locked_file in manifest["files"]:
            _, payload = checked(locked_file, base=path.parent)
            license_found |= (
                hashlib.sha256(payload).hexdigest() == manifest["provenance"]["license_text_sha256"]
            )
        if not license_found:
            raise ReleaseValidationError(
                "Source package does not contain its declared license bytes"
            )
        manifests[package_id] = manifest
        hashes[package_id] = reference["sha256"]
    for manifest in manifests.values():
        if any(hashes.get(dep["package_id"]) != dep["sha256"] for dep in manifest["dependencies"]):
            raise ReleaseValidationError("Export package dependency closure is incomplete")
    if not required.issubset({manifest["kind"] for manifest in manifests.values()}):
        raise ReleaseValidationError("Study bundle lacks source/lexical/map dependencies")

    references = record.get("audit_files")
    if not isinstance(references, list) or not references:
        raise ReleaseValidationError("Study bundle lacks release-bound package audit evidence")
    audited: set[str] = set()
    audit_paths: set[Path] = set()
    import re

    for reference in references:
        if not isinstance(reference, dict) or set(reference) != {"path", "sha256", "package_id"}:
            raise ReleaseValidationError(
                "Package audit references require path, hash and package identity"
            )
        package_id = reference["package_id"]
        if package_id not in manifests:
            raise ReleaseValidationError("Audit refers to a package outside the export closure")
        path = (root / reference["path"]).resolve()
        if not path.is_relative_to(content / "audit" / "packages") or path.suffix != ".json":
            raise ReleaseValidationError("Audit dependency is outside content/audit/packages")
        path, raw = checked(reference, base=root)
        if path in audit_paths:
            raise ReleaseValidationError("Duplicate package audit path")
        audit_paths.add(path)
        audit = json.loads(raw)
        validate_contract("audit_record.schema.json", audit)
        namespace = re.sub(r"[^a-z0-9_-]", "_", package_id.lower()).strip("_")
        if (
            audit["entity_type"] != "package"
            or audit["entity_id"] != package_id
            or audit["after_hash"] != hashes[package_id]
            or not audit["audit_id"].startswith(f"aud.pkg.{namespace}.")
            or path.name != audit["audit_id"][len("aud.pkg.") : -len(".0001")] + ".json"
        ):
            raise ReleaseValidationError(
                "Package audit does not attest the declared immutable revision"
            )
        audited.add(package_id)
    if audited != set(manifests):
        raise ReleaseValidationError(
            "Every exported package needs its release-bound audit evidence"
        )

    # Revalidate nested source/entry/analysis closure and the canonical projection.
    from app.services.greek_study_service import load_view

    load_view(snapshot_id, current_policy)
    if (
        policy_revision() != current_policy
        or file_hash(availability_record()) != release_hash
        or not availability(descriptor)
    ):
        raise ReleaseValidationError("Source policy or release evidence changed during export")
    raise ReleaseValidationError(
        "Greek study bundle export awaits independently verified reconstruction; "
        "no bundle was serialized"
    )
