"""Audited immutable installation, deliberately separate from activation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.foundation_contract_service import validate_contract, workspace_path
from app.services.immutable_file_service import install_immutable, sha256_file, workspace_lock
from app.services.package_audit_service import record_package_mutation
from app.services.registry_service import deterministic_json, file_hash


def install_staged_package(
    staged_dir: Path,
    destination: str,
    *,
    created_by: str,
    rationale: str,
) -> dict[str, Any]:
    staged_dir = staged_dir.resolve()
    manifest = json.loads((staged_dir / "package.json").read_text(encoding="utf-8"))
    validate_contract("source_package.schema.json", manifest)
    target = workspace_path(destination)
    content = get_settings().content_dir.resolve()
    permitted = ("lxx", "lexicons", "lexemes", "versification", "cross_alignments")
    if not target.is_relative_to(content) or target.relative_to(content).parts[0] not in permitted:
        raise ValueError("Package destination is outside normalized source package roots")
    paths: set[str] = {"package.json"}
    files: list[tuple[Path, bytes]] = []
    for item in manifest["files"]:
        relative = Path(item["path"])
        candidate = (staged_dir / relative).resolve()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "\\" in item["path"]
            or not candidate.is_relative_to(staged_dir)
            or item["path"] in paths
        ):
            raise ValueError("Package file path is unsafe or duplicated")
        paths.add(item["path"])
        if (
            candidate.stat().st_size != item["size_bytes"]
            or sha256_file(candidate) != item["sha256"]
        ):
            raise ValueError("Staged package file differs from source lock")
        files.append((target / relative, candidate.read_bytes()))
    encoded = deterministic_json(manifest).encode("utf-8")
    with workspace_lock(get_settings().data_dir / "local" / "study-publication.lock"):
        # Detect every conflicting revision before writing even the first file.
        for path, data in [*files, (target / "package.json", encoded)]:
            if path.exists() and path.read_bytes() != data:
                raise ValueError("Immutable package revision checksum reuse")
        for path, data in files:
            install_immutable(path, data)
        audit = record_package_mutation(
            package_id=manifest["package_id"],
            before_hash="0" * 64,
            after_hash=file_hash(manifest),
            summary="Install immutable normalized source package",
            rationale=rationale,
            created_by=created_by,
            checks=["source_lock_hashes", "strict_manifest", "inactive_install"],
            idempotency_key=f"install:{destination}:{file_hash(manifest)}",
        )
        changed = install_immutable(target / "package.json", encoded)
    return {
        "package_id": manifest["package_id"],
        "installed": changed,
        "active": False,
        "audit_id": audit["audit_id"],
        "path": (target / "package.json").relative_to(get_settings().root_dir).as_posix(),
        "sha256": file_hash(manifest),
    }
