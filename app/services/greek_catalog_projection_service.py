"""A catalog may mirror approved normalized records; it cannot author new facts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.errors import ValidationError
from app.core.ids import parse_unit_id
from app.services import source_capability_service
from app.services.foundation_contract_service import (
    validate_contract,
    validate_greek_unit,
    workspace_path,
)


def _locked_bytes(path: Path, reference: dict[str, Any]) -> bytes:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != reference["sha256"]:
        raise ValidationError("Canonical package/catalog bytes changed during projection")
    if "size_bytes" in reference and len(data) != reference["size_bytes"]:
        raise ValidationError("Canonical package file size mismatch")
    return data


def _records(path: Path, data: bytes) -> list[Any]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
    if path.suffix == ".json":
        payload = json.loads(data.decode("utf-8"))
        return payload if isinstance(payload, list) else [payload]
    return []


def _indexed(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get(key), str):
            raise ValidationError(f"Malformed canonical Greek {key}")
        identity = record[key]
        if identity in result:
            raise ValidationError(f"Duplicate canonical Greek {key}")
        result[identity] = record
    return result


def canonical_projection(descriptor: dict[str, Any]) -> dict[str, Any]:
    """Require exact membership/equality before returning any catalog text.

    Reviewed selections, lexical entry links and expressions do not yet have a
    specialist-approved canonical resolver. Catalog labels cannot supply one.
    """
    catalog_path = workspace_path(descriptor["catalog"]["path"])
    payload = json.loads(_locked_bytes(catalog_path, descriptor["catalog"]).decode("utf-8"))
    allowed = {"units", "entries", "analyses", "annotations", "expressions"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ValidationError("Unrecognized Greek catalog projection fields")
    if payload.get("expressions"):
        raise ValidationError("Greek expressions require a canonical reviewed evidence contract")
    units: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    attribution = []
    package_sources: dict[str, str] = {}
    for reference in descriptor["packages"]:
        manifest_path = workspace_path(reference["path"])
        manifest = json.loads(_locked_bytes(manifest_path, reference).decode("utf-8"))
        validate_contract("source_package.schema.json", manifest)
        if manifest["package_id"] != reference["package_id"]:
            raise ValidationError("Canonical package identity mismatch")
        package_sources[manifest["package_id"]] = manifest["source_id"]
        kind = manifest["kind"]
        capability = {
            "source_text": "display",
            "dictionary": "dictionary",
            "analysis": "analysis",
        }.get(kind)
        if capability is None:
            continue
        source_capability_service.require_package_capability(
            manifest["source_id"],
            manifest["package_id"],
            reference["sha256"],
            capability,
        )
        if kind == "source_text":
            attribution.append({"source_id": manifest["source_id"], **manifest["provenance"]})
        for file in manifest["files"]:
            path = (manifest_path.parent / file["path"]).resolve()
            if not path.is_relative_to(manifest_path.parent.resolve()):
                raise ValidationError("Canonical file is outside its enumerated package")
            for record in _records(path, _locked_bytes(path, file)):
                if not isinstance(record, dict):
                    raise ValidationError("Normalized Greek records must be objects")
                if kind == "source_text" and "unit_id" in record:
                    validate_greek_unit(record)
                    identity = parse_unit_id(record["unit_id"], require_versioned=True)
                    if (identity.edition_id, identity.text_revision_id) != (
                        descriptor["edition_id"],
                        descriptor["text_revision_id"],
                    ):
                        raise ValidationError(
                            "Canonical source unit is outside selected edition/revision"
                        )
                    units.append(record)
                elif kind == "dictionary" and "entry_id" in record:
                    validate_contract("greek_dictionary_entry.schema.json", record)
                    expected_attribution = {
                        "source_id": manifest["source_id"],
                        "package_revision": manifest["package_revision"],
                        "license": manifest["provenance"]["license"],
                        "license_text_sha256": manifest["provenance"]["license_text_sha256"],
                        "required_attribution": manifest["provenance"]["attribution"],
                    }
                    if (
                        record["package_id"] != manifest["package_id"]
                        or record["attribution"] != expected_attribution
                    ):
                        raise ValidationError("Canonical dictionary provenance mismatch")
                    entries.append(record)
                elif kind == "analysis" and "analysis_set_id" in record:
                    validate_contract("greek_analysis_set.schema.json", record)
                    if record["status"] != "proposed" or record["coverage"]["reviewed_tokens"] != 0:
                        raise ValidationError(
                            "Reviewed Greek analyses require specialist resolution"
                        )
                    annotations.extend(record["annotations"])
    unit_map = _indexed(units, "unit_id")
    entry_map = _indexed(entries, "entry_id")
    annotation_map = _indexed(annotations, "token_id")
    analyses = [analysis for annotation in annotations for analysis in annotation["analyses"]]
    analysis_map = _indexed(analyses, "analysis_id")
    if not unit_map:
        raise ValidationError("Greek catalog has no enumerated canonical source units")
    for field, key, canonical in (
        ("units", "unit_id", unit_map),
        ("entries", "entry_id", entry_map),
        ("analyses", "analysis_id", analysis_map),
    ):
        if field == "analyses" and field not in payload and "annotations" in payload:
            continue
        projected = payload.get(field, [])
        if not isinstance(projected, list) or _indexed(projected, key) != canonical:
            raise ValidationError(
                f"Greek catalog {field} differ from enumerated canonical package records"
            )
    if "annotations" in payload and _indexed(payload["annotations"], "token_id") != annotation_map:
        raise ValidationError("Greek catalog annotations differ from canonical package records")
    ordered_token_ids = [token["token_id"] for unit in units for token in unit["tokens"]]
    token_ids = set(ordered_token_ids)
    if len(token_ids) != len(ordered_token_ids):
        raise ValidationError("Duplicate canonical source token identity across units")
    for annotation in annotations:
        if (
            annotation["token_id"] not in token_ids
            or annotation["selected_analysis_id"] is not None
        ):
            raise ValidationError("Greek annotation endpoint/selection is unavailable")
    for analysis in analyses:
        if analysis["status"] != "proposed" or analysis["token_id"] not in token_ids:
            raise ValidationError("Reviewed/foreign Greek analysis is unavailable")
        source_package = next(
            (p for p in descriptor["packages"] if p["package_id"] == analysis["source_package_id"]),
            None,
        )
        if source_package is None:
            raise ValidationError("Greek analysis provenance outside snapshot closure")
        source_capability_service.require_package_capability(
            package_sources[analysis["source_package_id"]],
            source_package["package_id"],
            source_package["sha256"],
            "analysis",
        )
        if any(item["source_entry_id"] not in entry_map for item in analysis["identifiers"]):
            raise ValidationError("Greek analysis references absent canonical dictionary entry")
    return {
        "units": units,
        "entries": entries,
        "analyses": analyses,
        "annotations": annotations,
        "expressions": [],
        "source_attribution": attribution,
    }
