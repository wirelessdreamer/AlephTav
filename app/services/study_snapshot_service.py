"""Joint immutable study publication, with predecessor CAS and current policy."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.services import source_capability_service
from app.services.foundation_contract_service import validate_contract, workspace_path
from app.services.immutable_file_service import (
    atomic_write,
    install_immutable,
    sha256_file,
    workspace_lock,
)
from app.services.package_audit_service import record_package_mutation
from app.services.registry_service import deterministic_json, file_hash


def snapshot_id(descriptor: dict[str, Any]) -> str:
    payload = {k: v for k, v in descriptor.items() if k != "study_snapshot_id"}
    return "study." + file_hash(payload)[:24]


def _pointer_path() -> Path:
    return get_settings().indexes_dir / "active_study_snapshot.json"


def _last_good_path() -> Path:
    return get_settings().indexes_dir / "last_good_study_snapshot.json"


def _snapshot_path(identifier: str) -> Path:
    import re

    if re.fullmatch(r"study\.[0-9a-f]{24}", identifier) is None:
        raise ValueError("Invalid study snapshot ID")
    return get_settings().content_dir / "study_snapshots" / f"{identifier}.json"


def _verify_file(reference: dict[str, Any]) -> Path:
    path = workspace_path(reference["path"])
    if not path.is_file() or sha256_file(path) != reference["sha256"]:
        raise ValidationError(f"Study dependency hash mismatch: {reference['path']}")
    return path


def verify_snapshot(descriptor: dict[str, Any]) -> None:
    validate_contract("study_snapshot.schema.json", descriptor)
    if descriptor["study_snapshot_id"] != snapshot_id(descriptor):
        raise ValidationError("Study descriptor identity/hash mismatch")
    packages: dict[str, str] = {}
    manifests: list[dict[str, Any]] = []
    for reference in descriptor["packages"]:
        path = _verify_file(reference)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        validate_contract("source_package.schema.json", manifest)
        if manifest["review_status"] != "approved":
            raise ValidationError("Study package requires explicit approved release status")
        if reference["package_id"] != manifest["package_id"] or reference["package_id"] in packages:
            raise ValidationError("Study package identity mismatch/duplicate")
        packages[reference["package_id"]] = reference["sha256"]
        manifests.append(manifest)
        if manifest["source_id"] not in descriptor["source_ids"]:
            raise ValidationError("Study source permissions omit a dependency")
        source_capability_service.require_package_capability(
            manifest["source_id"],
            manifest["package_id"],
            reference["sha256"],
            "display",
        )
        license_present = False
        for item in manifest["files"]:
            candidate = (path.parent / item["path"]).resolve()
            if not candidate.is_relative_to(path.parent.resolve()) or not candidate.is_file():
                raise ValidationError("Package file escapes immutable package")
            if (
                candidate.stat().st_size != item["size_bytes"]
                or sha256_file(candidate) != item["sha256"]
            ):
                raise ValidationError("Package file hash/size mismatch")
            if item["sha256"] == manifest["provenance"]["license_text_sha256"]:
                license_present = True
        if not license_present:
            raise ValidationError(
                "Study package license text hash has no enumerated packaged bytes"
            )
    for manifest in manifests:
        for dependency in manifest["dependencies"]:
            if packages.get(dependency["package_id"]) != dependency["sha256"]:
                raise ValidationError("Study package dependency closure is incomplete")
    _verify_file(descriptor["catalog"])
    if descriptor["mt_source_snapshot"] is not None:
        path = _verify_file(descriptor["mt_source_snapshot"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_contract("mt_source_snapshot.schema.json", payload)
        if payload["snapshot_id"] != descriptor["mt_source_snapshot"]["snapshot_id"]:
            raise ValidationError("MT source snapshot identity mismatch")
        if payload["snapshot_id"] != "mt." + file_hash(payload["units"])[:24]:
            raise ValidationError("MT source snapshot content identity mismatch")
    for source_id in descriptor["source_ids"]:
        source_capability_service.require_capability(source_id, "display")
    from app.services.greek_catalog_projection_service import canonical_projection

    canonical_projection(descriptor)


def active_snapshot(study_snapshot_id: str | None = None) -> dict[str, Any]:
    if study_snapshot_id is None:
        path = _pointer_path()
        if not path.exists():
            raise NotFoundError("No active study snapshot")
        pointer = json.loads(path.read_text(encoding="utf-8"))
        study_snapshot_id = pointer["study_snapshot_id"]
    path = _snapshot_path(study_snapshot_id)
    if not path.exists():
        raise NotFoundError("Study snapshot is unavailable")
    descriptor = json.loads(path.read_text(encoding="utf-8"))
    verify_snapshot(descriptor)
    return descriptor


def publish_snapshot(
    descriptor: dict[str, Any],
    expected_predecessor: str | None,
    *,
    created_by: str,
    rationale: str,
) -> dict[str, Any]:
    descriptor = deepcopy(descriptor)
    if descriptor.get("predecessor_id") != expected_predecessor:
        raise ValidationError("Descriptor predecessor differs from publication expectation")
    with workspace_lock(get_settings().data_dir / "local" / "study-publication.lock"):
        current = None
        if _pointer_path().exists():
            current = json.loads(_pointer_path().read_text(encoding="utf-8"))["study_snapshot_id"]
        if current != expected_predecessor:
            raise ValidationError("Stale study publication predecessor")
        verify_snapshot(descriptor)
        if descriptor["policy_revision_id"] != source_capability_service.policy_revision():
            raise ValidationError("Source policy changed while building study snapshot")
        encoded = deterministic_json(descriptor).encode("utf-8")
        install_immutable(_snapshot_path(descriptor["study_snapshot_id"]), encoded)
        record_package_mutation(
            package_id="study_snapshot",
            before_hash=file_hash(current),
            after_hash=file_hash(descriptor),
            summary="Publish complete study snapshot",
            rationale=rationale,
            created_by=created_by,
            checks=["dependency_hashes", "current_source_policy", "predecessor_cas"],
        )
        if current is not None:
            # Store only an independently validated predecessor. Its permissions
            # are checked again during recovery, never recovered from history.
            try:
                active_snapshot(current)
            except source_capability_service.SourceUnavailableError:
                pass
            else:
                atomic_write(
                    _last_good_path(),
                    deterministic_json(
                        {
                            "study_snapshot_id": current,
                        }
                    ).encode("utf-8"),
                )
        atomic_write(
            _pointer_path(),
            deterministic_json(
                {
                    "study_snapshot_id": descriptor["study_snapshot_id"],
                    "previous_snapshot_id": current,
                }
            ).encode("utf-8"),
        )
    return descriptor


def recover_active_snapshot(*, created_by: str, rationale: str) -> dict[str, Any]:
    """Recover a damaged active selection, subject to today's policy.

    SourceUnavailableError is deliberately not a corruption condition: policy
    revocation must never trigger a fallback into a permissive old snapshot.
    """
    from jsonschema import ValidationError as SchemaValidationError  # type: ignore[import-untyped]

    with workspace_lock(get_settings().data_dir / "local" / "study-publication.lock"):
        try:
            return active_snapshot()
        except (
            OSError,
            ValueError,
            KeyError,
            ValidationError,
            NotFoundError,
            SchemaValidationError,
        ):
            if not _last_good_path().exists():
                raise
        fallback = json.loads(_last_good_path().read_text(encoding="utf-8"))
        descriptor = active_snapshot(fallback["study_snapshot_id"])
        before = sha256_file(_pointer_path()) if _pointer_path().exists() else "0" * 64
        record_package_mutation(
            package_id="study_snapshot_recovery",
            before_hash=before,
            after_hash=file_hash(descriptor),
            summary="Recover last-good study snapshot",
            rationale=rationale,
            created_by=created_by,
            checks=["retained_dependency_hashes", "current_source_policy"],
        )
        atomic_write(
            _pointer_path(),
            deterministic_json(
                {
                    "study_snapshot_id": descriptor["study_snapshot_id"],
                    "previous_snapshot_id": None,
                }
            ).encode("utf-8"),
        )
        return descriptor


def publish_source_policy(
    registry: dict[str, Any],
    *,
    expected_revision: str,
    created_by: str,
    rationale: str,
) -> str:
    """Audit a serialized policy change; rollback snapshots cannot change it."""
    validate_contract("source_registry.schema.json", registry)
    source_ids = [s["source_id"] for s in registry["sources"]]
    if len(source_ids) != len(set(source_ids)):
        raise ValidationError("Duplicate source policy identity")
    with workspace_lock(get_settings().data_dir / "local" / "study-publication.lock"):
        if source_capability_service.policy_revision() != expected_revision:
            raise ValidationError("Stale source policy predecessor")
        before = get_settings().content_dir / "source_registry.json"
        before_hash = sha256_file(before) if before.exists() else "0" * 64
        for source in registry["sources"]:
            for name, component in source["components"].items():
                if component["status"] == "approved" and not source_capability_service._approved(
                    source["source_id"], name, component
                ):
                    raise ValidationError(
                        "Approved source policy requires applicable owner/license decisions"
                    )
        record_package_mutation(
            package_id="source_policy",
            before_hash=before_hash,
            after_hash=file_hash(registry),
            summary="Publish current source capabilities",
            rationale=rationale,
            created_by=created_by,
            checks=[
                "strict_policy_schema",
                "policy_predecessor_cas",
                "applicable_source_decisions",
            ],
        )
        atomic_write(before, deterministic_json(registry).encode("utf-8"))
    return source_capability_service.policy_revision()
