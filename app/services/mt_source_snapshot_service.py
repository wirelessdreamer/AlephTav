"""Retained MT source-only evidence: English edits never alter bridge anchors."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.core.ids import parse_unit_id
from app.services.foundation_contract_service import validate_contract
from app.services.immutable_file_service import install_immutable, sha256_file
from app.services.package_audit_service import record_package_mutation
from app.services.registry_service import deterministic_json, file_hash


def capture_mt_source_snapshot(units: list[dict[str, Any]]) -> dict[str, str]:
    sources = []
    for unit in sorted(units, key=lambda item: item["unit_id"]):
        if parse_unit_id(unit["unit_id"]).corpus != "mt":
            continue
        sources.append(
            {
                "unit_id": unit["unit_id"],
                "source_hebrew": unit["source_hebrew"],
                "tokens": [
                    {key: token[key] for key in ("token_id", "surface", "normalized")}
                    for token in unit.get("tokens", [])
                ],
            }
        )
    identifier = "mt." + file_hash(sources)[:24]
    payload = {"schema_version": "1.0", "snapshot_id": identifier, "units": sources}
    validate_contract("mt_source_snapshot.schema.json", payload)
    settings = get_settings()
    path = settings.content_dir / "mt" / "source_snapshots" / identifier / "source_tokens.json"
    if not path.exists():
        record_package_mutation(
            package_id=identifier,
            before_hash="0" * 64,
            after_hash=file_hash(payload),
            summary="Retain immutable MT source-only snapshot",
            rationale="Preserve source evidence independently of live translations",
            created_by="service:catalog-builder",
            checks=["source_only_projection", "strict_mt_snapshot"],
        )
    install_immutable(path, deterministic_json(payload).encode("utf-8"))
    return {
        "snapshot_id": identifier,
        "path": path.relative_to(settings.root_dir).as_posix(),
        "sha256": sha256_file(path),
    }
