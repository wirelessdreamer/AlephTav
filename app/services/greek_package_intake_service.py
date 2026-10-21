"""Read-only inspection and immutable *staging* of locked Greek packages.

Staging is deliberately separate from audited canonical installation and study-snapshot
publication. No function here writes raw sources, settings, or an active descriptor.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

from app.core.ids import ensure_id, parse_unit_id
from app.services.greek_analysis_service import unicode_findings

PARSER_VERSION = "greek-package-v1"


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative_file(root: Path, value: str) -> Path:
    relative = PurePosixPath(value)
    if (
        not value
        or relative.is_absolute()
        or ".." in relative.parts
        or "\\" in value
        or ":" in value
        or value != relative.as_posix()
    ):
        raise ValueError(f"Unsafe package path: {value!r}")
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Package path escapes root: {value!r}")
    if path.is_symlink() or any(
        parent.is_symlink()
        for parent in path.parents
        if parent != root.parent and parent.is_relative_to(root)
    ):
        raise ValueError(f"Symlink in immutable package: {value!r}")
    return path


def validate_greek_units(
    units: list[dict[str, Any]], *, expected_psalms: set[int] | None = None
) -> dict[str, Any]:
    from app.services.foundation_contract_service import validate_contract

    seen_units: set[str] = set()
    seen_tokens: set[str] = set()
    psalms: set[int] = set()
    edition_revision = set()
    findings: list[dict[str, Any]] = []
    unit_fields = {
        "schema_version",
        "unit_id",
        "corpus",
        "edition_id",
        "text_revision_id",
        "psalm_id",
        "ref",
        "source_greek",
        "tokens",
    }
    token_fields = {"token_id", "position", "surface", "normalized", "text_span", "source_locator"}
    for unit in units:
        if set(unit) != unit_fields or unit["schema_version"] != "1.0" or unit["corpus"] != "lxx":
            raise ValueError("Greek source unit has missing or unexpected fields")
        validate_contract("greek_unit.schema.json", unit)
        identity = parse_unit_id(unit["unit_id"], require_versioned=True)
        if identity.corpus != "lxx" or identity.edition_id != unit["edition_id"]:
            raise ValueError("Greek source unit edition differs from identity")
        if (
            identity.text_revision_id != unit["text_revision_id"]
            or identity.psalm_id != unit["psalm_id"]
        ):
            raise ValueError("Greek source unit reference differs from identity")
        psalm = int(identity.psalm_id[2:])
        if not 1 <= psalm <= 151:
            raise ValueError("Greek Psalter psalm outside 1–151")
        if identity.edition_id == "swete1896" and psalm == 135 and identity.verse == 23:
            raise ValueError("Swete 135:23 is edition-absent; do not fabricate it")
        if unit["unit_id"] in seen_units:
            raise ValueError("Duplicate Greek source unit")
        seen_units.add(unit["unit_id"])
        psalms.add(psalm)
        edition_revision.add((identity.edition_id, identity.text_revision_id))
        previous_end = 0
        for position, token in enumerate(unit["tokens"], 1):
            if set(token) != token_fields:
                raise ValueError("Greek source token has missing or unexpected fields")
            token_id = ensure_id("token_id", token["token_id"])
            if token_id.rsplit(".", 1)[0] != unit["unit_id"].rsplit(".", 1)[0]:
                raise ValueError("Greek source token belongs to another edition/revision/verse")
            if token_id in seen_tokens or token["position"] != position:
                raise ValueError("Duplicate token or noncontiguous source position")
            seen_tokens.add(token_id)
            span = token["text_span"]
            if set(span) != {"start", "end"} or any(type(span[key]) is not int for key in span):
                raise ValueError("Text spans must use integer Python codepoint offsets")
            start, end = span["start"], span["end"]
            if not previous_end <= start < end <= len(unit["source_greek"]):
                raise ValueError("Overlapping or invalid Greek token span")
            if unit["source_greek"][start:end] != token["surface"]:
                raise ValueError("Greek token surface differs from immutable text span")
            if unicodedata.normalize("NFC", token["surface"]) != token["normalized"]:
                raise ValueError("Token normalized field must preserve NFC source spelling")
            locator = token["source_locator"]
            if set(locator) != {"file", "locator", "fragments"} or not locator["file"]:
                raise ValueError("Greek token requires source file/locator/fragments")
            for fragment in locator["fragments"]:
                if not fragment or set(fragment) - {"leaf", "page", "line", "strip"}:
                    raise ValueError("Unsupported source fragment location")
            findings.extend(
                {**finding, "token_id": token_id} for finding in unicode_findings(token["surface"])
            )
            previous_end = end
        # Punctuation/whitespace may occur outside tokens; letters may not disappear.
        covered = {
            index
            for token in unit["tokens"]
            for index in range(token["text_span"]["start"], token["text_span"]["end"])
        }
        if any(
            unicodedata.category(char)[0] in {"L", "M", "N"} and index not in covered
            for index, char in enumerate(unit["source_greek"])
        ):
            raise ValueError("Greek source letters are not accounted for by source tokens")
    if len(edition_revision) != 1:
        raise ValueError("One Greek text package must contain exactly one edition/revision")
    if expected_psalms is not None and psalms != expected_psalms:
        raise ValueError(
            f"Psalm coverage differs: missing={sorted(expected_psalms - psalms)}, "
            f"unexpected={sorted(psalms - expected_psalms)}"
        )
    return {
        "unit_count": len(seen_units),
        "token_count": len(seen_tokens),
        "psalms": sorted(psalms),
        "findings": findings,
    }


def validate_versification_map(
    payload: dict[str, Any], units: list[dict[str, Any]]
) -> dict[str, Any]:
    """Keep many-to-many/title/absent records; require explicit numbering baselines.

    Generic maps are candidates, never edition overrides. Source witnesses and edition
    absences are authored evidence, not inferred from a missing link.
    """
    from app.services.foundation_contract_service import validate_contract

    validate_contract("greek_versification_map.schema.json", payload)
    required = {"schema_version", "edition_id", "text_revision_id", "records", "witness_spans"}
    if set(payload) != required or payload["schema_version"] != "1.0":
        raise ValueError("Invalid versification map fields")
    by_id = {unit["unit_id"]: unit for unit in units}
    seen = set()
    for record in payload["records"]:
        if set(record) != {"mapping_id", "relation", "sources", "targets", "provenance", "status"}:
            raise ValueError("Invalid versification record fields")
        if record["mapping_id"] in seen:
            raise ValueError("Duplicate versification record ID")
        seen.add(record["mapping_id"])
        if record["status"] not in {"proposed", "reviewed"}:
            raise ValueError("Unknown versification review status")
        if record["relation"] not in {
            "equivalent",
            "title",
            "greek_only",
            "mt_only",
            "edition_absent",
            "hallelujah_shift",
            "partial",
        }:
            raise ValueError("Unknown versification relation")
        if not record["sources"] and not record["targets"]:
            raise ValueError("Empty versification record")
        for endpoint in record["sources"] + record["targets"]:
            if set(endpoint) - {"baseline", "reference", "unit_id", "text_span", "alias"}:
                raise ValueError("Unexpected versification endpoint field")
            if not endpoint.get("baseline") or not endpoint.get("reference"):
                raise ValueError("Map endpoint requires explicit baseline and original reference")
            unit_id = endpoint.get("unit_id")
            if unit_id:
                identity = parse_unit_id(unit_id, require_versioned=True)
                if identity.corpus == "lxx":
                    if (identity.edition_id, identity.text_revision_id) != (
                        payload["edition_id"],
                        payload["text_revision_id"],
                    ) or unit_id not in by_id:
                        raise ValueError("Versification target absent from this Greek revision")
                    span = endpoint.get("text_span")
                    if span and not 0 <= span["start"] < span["end"] <= len(
                        by_id[unit_id]["source_greek"]
                    ):
                        raise ValueError("Invalid subverse span")
    witness_units: dict[str, list[dict[str, Any]]] = {}
    for span in payload["witness_spans"]:
        if set(span) != {"unit_id", "start", "end", "witness", "provenance"}:
            raise ValueError("Invalid witness span fields")
        unit = by_id.get(span["unit_id"])
        if unit is None or not 0 <= span["start"] < span["end"] <= len(unit["source_greek"]):
            raise ValueError("Witness span outside retained Greek text")
        if not span["witness"] or not span["provenance"]:
            raise ValueError("Witness attribution requires documentary evidence")
        witness_units.setdefault(span["unit_id"], []).append(span)
    for spans in witness_units.values():
        ordered = sorted(spans, key=lambda item: item["start"])
        if any(
            left["end"] > right["start"] for left, right in zip(ordered, ordered[1:], strict=False)
        ):
            raise ValueError("Overlapping source witness spans")
    return {"record_count": len(seen), "witness_span_count": len(payload["witness_spans"])}


def inspect_package(package_root: Path, *, require_full_psalter: bool = True) -> dict[str, Any]:
    """Dry run with zero writes. All locked files and all physical files are accounted for."""
    root = package_root.resolve()
    manifest = json.loads((root / "package.json").read_text(encoding="utf-8"))
    from app.services.foundation_contract_service import validate_contract

    validate_contract("source_package.schema.json", manifest)
    required = {
        "schema_version",
        "package_id",
        "source_id",
        "package_revision",
        "kind",
        "files",
        "dependencies",
        "provenance",
        "review_status",
    }
    if set(manifest) != required or manifest["schema_version"] != "1.0":
        raise ValueError("Invalid immutable source package manifest fields")
    provenance = manifest["provenance"]
    if set(provenance) != {
        "upstream_url",
        "upstream_revision",
        "license",
        "license_text_sha256",
        "attribution",
    } or not all(provenance.values()):
        raise ValueError("Package requires full source provenance and attribution")
    if manifest["review_status"] not in {"pending", "approved"}:
        raise ValueError("Unknown package review status")
    if not re.fullmatch(r"[0-9a-f]{64}", provenance["license_text_sha256"]):
        raise ValueError("Invalid license text checksum")
    locked = set()
    units = []
    maps = []
    entries = []
    found_license_text = False
    for record in manifest["files"]:
        if set(record) != {"path", "sha256", "size_bytes"} or record["path"] in locked:
            raise ValueError("Invalid or duplicate file lock")
        path = _relative_file(root, record["path"])
        raw = path.read_bytes()
        if len(raw) != record["size_bytes"] or _sha256(raw) != record["sha256"]:
            raise ValueError(f"Checksum/size mismatch: {record['path']}")
        locked.add(record["path"])
        if record["sha256"] == provenance["license_text_sha256"]:
            found_license_text = True
        if record["path"].startswith("psalms/") and path.suffix == ".json":
            units.append(json.loads(raw))
        elif record["path"] == "versification/map.json":
            maps.append(json.loads(raw))
        elif record["path"] == "entries.jsonl":
            for line in raw.decode("utf-8").splitlines():
                entry = json.loads(line)
                validate_contract("greek_dictionary_entry.schema.json", entry)
                attribution = entry["attribution"]
                if entry["package_id"] != manifest["package_id"] or (
                    attribution["source_id"],
                    attribution["package_revision"],
                    attribution["license"],
                    attribution["license_text_sha256"],
                ) != (
                    manifest["source_id"],
                    manifest["package_revision"],
                    provenance["license"],
                    provenance["license_text_sha256"],
                ):
                    raise ValueError("Dictionary entry attribution differs from its locked package")
                entries.append(entry)
    physical = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    if physical != locked | {"package.json"}:
        raise ValueError("Unaccounted or missing immutable package files")
    if not found_license_text:
        raise ValueError("Package must contain the locked source license text")
    source_counts = (
        validate_greek_units(
            units, expected_psalms=set(range(1, 152)) if require_full_psalter else None
        )
        if units
        else {"unit_count": 0, "token_count": 0, "psalms": [], "findings": []}
    )
    if manifest["kind"] == "source_text" and not units:
        raise ValueError("Greek source package contains no units")
    if manifest["kind"] == "dictionary" and not entries:
        raise ValueError("Dictionary package contains no validated entries")
    if len({entry["entry_id"] for entry in entries}) != len(entries):
        raise ValueError("Duplicate source dictionary entry ID")
    map_counts = [validate_versification_map(payload, units) for payload in maps]
    return {
        "manifest": manifest,
        "manifest_sha256": _sha256(canonical_bytes(manifest)),
        "parser_version": PARSER_VERSION,
        "units": units,
        "maps": maps,
        "entries": entries,
        "dry_run": {
            **source_counts,
            "maps": map_counts,
            "file_count": len(locked),
            "dictionary_entry_count": len(entries),
            "review_status": manifest["review_status"],
            "activation": "not_requested",
            "source_approval": "requires_current_policy",
            "canonical_changes": [],
            "affected_references": [],
            "annotation_status": "not_imported",
        },
    }


def stage_package(
    package_root: Path, staging_root: Path, *, require_full_psalter: bool = True
) -> dict[str, Any]:
    """Copy a validated immutable candidate atomically; same bytes are an idempotent no-op."""
    inspection = inspect_package(package_root, require_full_psalter=require_full_psalter)
    staging = staging_root.resolve()
    from app.core.config import get_settings

    workspace = Path(__file__).resolve().parents[2]
    settings = get_settings()
    protected = (
        workspace / "content",
        workspace / "data" / "raw",
        settings.content_dir.resolve(),
        settings.raw_dir.resolve(),
    )
    if any(
        staging.is_relative_to(path) or path.is_relative_to(staging) for path in protected
    ) or staging.is_relative_to(package_root.resolve()):
        raise ValueError(
            "Staging must be separate from canonical content/raw and the input package"
        )
    package_id = inspection["manifest"]["package_id"]
    revision = inspection["manifest"]["package_revision"]
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", package_id + "-" + revision):
        raise ValueError("Package ID/revision cannot be used as a staging directory")
    target = staging / package_id / revision
    if target.exists():
        existing = inspect_package(target, require_full_psalter=require_full_psalter)
        if existing["manifest_sha256"] != inspection["manifest_sha256"]:
            raise ValueError("An immutable package revision cannot be reused with different bytes")
        return {"path": str(target), "changed": False, **inspection["dry_run"]}
    target.parent.mkdir(parents=True, exist_ok=True)
    candidate = Path(tempfile.mkdtemp(prefix=".candidate-", dir=target.parent))
    try:
        for record in inspection["manifest"]["files"]:
            destination = _relative_file(candidate, record["path"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_relative_file(package_root.resolve(), record["path"]), destination)
        (candidate / "package.json").write_bytes(canonical_bytes(inspection["manifest"]))
        inspect_package(candidate, require_full_psalter=require_full_psalter)
        candidate.rename(target)
    finally:
        if candidate.exists():
            shutil.rmtree(candidate)
    return {"path": str(target), "changed": True, **inspection["dry_run"]}


def install_staged_greek_package(
    staged_dir: Path, *, created_by: str, rationale: str, require_full_psalter: bool = True
) -> dict[str, Any]:
    """Install a reviewed source through foundation auditing; activation remains separate."""
    from app.services.package_install_service import install_staged_package
    from app.services.source_capability_service import require_capability

    inspection = inspect_package(staged_dir, require_full_psalter=require_full_psalter)
    manifest = inspection["manifest"]
    if manifest["kind"] != "source_text" or not inspection["units"]:
        raise ValueError("Greek source installation requires a normalized source-text package")
    if manifest["review_status"] != "approved":
        raise ValueError("Greek package owner review is pending")
    require_capability(manifest["source_id"], "display")
    first = inspection["units"][0]
    destination = f"content/lxx/editions/{first['edition_id']}/{first['text_revision_id']}"
    return install_staged_package(
        staged_dir, destination, created_by=created_by, rationale=rationale
    )
