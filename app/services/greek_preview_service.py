"""Owner-approved local display preview of a staged, unreleased Greek source package.

A preview is display-only and never a release: it does not install the package, publish
a study snapshot, or grant export/generation. It shows proposed verse-map records, and
the UI labels it unreviewed. The owner's approval is bound to the exact manifest hash.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import LicensePolicyError
from app.core.license_rules import evaluate_manifest
from app.services import source_capability_service
from app.services.greek_package_intake_service import _relative_file, inspect_package
from app.services.immutable_file_service import atomic_write, sha256_file, workspace_lock
from app.services.package_audit_service import record_package_mutation
from app.services.registry_service import deterministic_json, file_hash


def _approval_path() -> Path:
    settings = get_settings()
    path = settings.content_dir / "study_snapshots" / "preview.json"
    if not path.resolve().is_relative_to(settings.root_dir):
        raise ValueError("Greek preview approval escapes its workspace")
    return path


def staged_package_dir(package_id: str, revision: str) -> Path:
    for value in (package_id, revision):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
            raise ValueError("Unsafe Greek preview package identity")
    settings = get_settings()
    root = settings.derived_dir / "greek_staging"
    path = root / package_id / revision
    if (
        not root.resolve().is_relative_to(settings.root_dir)
        or not path.resolve().is_relative_to(root.resolve())
        or any(item.is_symlink() for item in (root, path.parent, path))
    ):
        raise ValueError("Greek preview package escapes its staging directory")
    return path


def _require_display_policy(manifest: dict[str, Any], manifest_hash: str) -> None:
    """Owner preview consent never overrides an explicit current source policy."""
    if not evaluate_manifest(manifest["provenance"])["allowed"]:
        raise LicensePolicyError("Greek preview source license does not allow local display")
    policy = source_capability_service._registry()
    if any(source["source_id"] == manifest["source_id"] for source in policy["sources"]):
        source_capability_service.require_package_capability(
            manifest["source_id"], manifest["package_id"], manifest_hash, "display"
        )


def _validate_approval(approval: Any) -> bool:
    fields = {
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
    if not isinstance(approval, dict) or set(approval) != fields:
        raise ValueError("Invalid Greek preview approval fields")
    if not all(isinstance(value, str) and value.strip() for value in approval.values()):
        raise ValueError("Greek preview approval requires nonempty text values")
    if (approval["scope"], approval["role"]) != ("local_display_preview", "owner"):
        raise ValueError("Greek preview approval has an invalid scope or role")
    if not re.fullmatch(r"[0-9a-f]{64}", approval["manifest_sha256"]):
        raise ValueError("Greek preview approval has an invalid manifest checksum")
    if approval["decision"] in {"withdraw", "request_changes"}:
        return False
    if approval["decision"] != "approve":
        raise ValueError("Greek preview approval has an invalid decision")
    return True


def approve_preview(
    package_id: str, revision: str, *, reviewer_id: str, rationale: str
) -> dict[str, Any]:
    """Record the owner's approval to display this exact staged package as a preview."""
    staged = staged_package_dir(package_id, revision)
    manifest_hash = sha256_file(_relative_file(staged, "package.json"))
    package = _load_staged(str(staged), manifest_hash)
    manifest = package["manifest"]
    if (manifest["package_id"], manifest["package_revision"]) != (package_id, revision):
        raise ValueError("Staged package identity differs from its directory")
    if manifest["kind"] != "source_text":
        raise ValueError("Only a Greek source-text package can be previewed")
    record = {
        "package_id": package_id,
        "package_revision": revision,
        "source_id": manifest["source_id"],
        "manifest_sha256": manifest_hash,
        "scope": "local_display_preview",
        "role": "owner",
        "reviewer_id": reviewer_id,
        "decision": "approve",
        "rationale": rationale,
    }
    _validate_approval(record)
    _require_display_policy(manifest, manifest_hash)
    path = _approval_path()
    with workspace_lock(get_settings().derived_dir / "locks" / "greek-preview.lock"):
        before = sha256_file(path) if path.exists() else "0" * 64
        audit = record_package_mutation(
            package_id="greek_preview",
            before_hash=before,
            after_hash=file_hash(record),
            summary=f"Approve unreviewed display preview of {package_id} {revision}",
            rationale=rationale,
            created_by=reviewer_id,
            checks=["source_lock_hashes", "strict_manifest", "owner_preview_approval"],
        )
        atomic_write(path, deterministic_json(record).encode("utf-8"))
    return {**record, "audit_id": audit["audit_id"]}


def _load_staged(staged: str, manifest_sha256: str) -> dict[str, Any]:
    """Recheck every locked byte on each read; only strict parsing is cached."""
    root = Path(staged)
    manifest_bytes = _relative_file(root, "package.json").read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != manifest_sha256:
        raise ValueError("Greek preview package changed since the owner approved it")
    manifest = json.loads(manifest_bytes)
    for record in manifest["files"]:
        data = _relative_file(root, record["path"]).read_bytes()
        if (
            len(data) != record["size_bytes"]
            or hashlib.sha256(data).hexdigest() != record["sha256"]
        ):
            raise ValueError(f"Greek preview file changed since staging: {record['path']}")
    return deepcopy(_validated_package(staged, manifest_sha256))


@lru_cache(maxsize=2)
def _validated_package(staged: str, manifest_sha256: str) -> dict[str, Any]:
    manifest_path = _relative_file(Path(staged), "package.json")
    manifest_bytes = manifest_path.read_bytes()
    inspection = inspect_package(Path(staged), require_full_psalter=False)
    if (
        hashlib.sha256(manifest_bytes).hexdigest() != manifest_sha256
        or inspection["manifest"] != json.loads(manifest_bytes)
        or sha256_file(manifest_path) != manifest_sha256
    ):
        raise ValueError("Greek preview package changed during validation")
    return inspection


def load_preview() -> dict[str, Any] | None:
    """The approved preview's units, verse-map records and attribution; None if unapproved."""
    path = _approval_path()
    if not path.exists():
        return None
    approval_bytes = path.read_bytes()
    approval = json.loads(approval_bytes)
    if not _validate_approval(approval):
        return None
    policy_id = source_capability_service.policy_revision()
    staged = staged_package_dir(approval["package_id"], approval["package_revision"])
    if not (staged / "package.json").exists():
        raise FileNotFoundError(
            "The approved Greek preview package is not staged. "
            "Run psalms-workbench greek-build-swete to rebuild it."
        )
    package = _load_staged(str(staged), approval["manifest_sha256"])
    manifest = package["manifest"]
    if (manifest["package_id"], manifest["package_revision"], manifest["source_id"]) != (
        approval["package_id"],
        approval["package_revision"],
        approval["source_id"],
    ) or manifest["kind"] != "source_text":
        raise ValueError("Greek preview approval differs from its source package")
    _require_display_policy(manifest, approval["manifest_sha256"])
    first = package["units"][0]
    provenance = package["manifest"]["provenance"]
    if (
        path.read_bytes() != approval_bytes
        or source_capability_service.policy_revision() != policy_id
    ):
        raise ValueError("Greek preview approval or source policy changed during read")
    return {
        "edition_id": first["edition_id"],
        "manifest_sha256": approval["manifest_sha256"],
        "text_revision_id": first["text_revision_id"],
        "units": package["units"],
        "records": [
            record
            for payload in package["maps"]
            if (payload["edition_id"], payload["text_revision_id"])
            == (first["edition_id"], first["text_revision_id"])
            for record in payload["records"]
        ],
        "source_attribution": [
            {"attribution": provenance["attribution"], "license": provenance["license"]}
        ],
    }
