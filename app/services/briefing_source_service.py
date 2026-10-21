"""Edition-bound Greek evidence for briefing and arrangement source blocks."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from jsonschema import ValidationError as SchemaValidationError  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.core.errors import LicensePolicyError, NotFoundError, ValidationError
from app.core.ids import parse_unit_id
from app.services import (
    greek_preview_service,
    greek_study_service,
    registry_service,
    source_capability_service,
)
from app.services.greek_study_export_service import availability

PREVIEW_MESSAGE = (
    "Unreviewed preview: unreleased Greek text on a proposed verse map. "
    "Not approved for export or generation."
)


def greek_evidence(psalm_id: str) -> dict[str, Any]:
    """Released evidence first; otherwise an owner-approved preview, unless policy blocks it."""
    released = _released_greek_evidence(psalm_id)
    if released["available"] or released.get("state") == "blocked":
        return released
    return _preview_greek_evidence(psalm_id) or released


def _released_greek_evidence(psalm_id: str) -> dict[str, Any]:
    """Read current permitted evidence; failures never expose cached Greek or glosses."""
    empty: dict[str, Any] = {"by_mt_unit": {}, "available": False}
    try:
        return _greek_evidence(psalm_id)
    except LicensePolicyError:
        return {
            **empty,
            "state": "blocked",
            "message": "Greek sources are blocked by current source permissions.",
        }
    except NotFoundError as error:
        return {**empty, "message": f"Greek study unavailable: {error}"}
    except (ValidationError, OSError, ValueError, KeyError, TypeError, SchemaValidationError):
        return {
            **empty,
            "state": "unavailable",
            "message": (
                "Greek source evidence could not be verified. "
                "Reload after its source packages are repaired."
            ),
        }


def _greek_evidence(psalm_id: str) -> dict[str, Any]:
    empty: dict[str, Any] = {"by_mt_unit": {}, "available": False}
    view = greek_study_service.load_view()
    if not availability(view.descriptor):
        return {**empty, "message": "Greek study is awaiting source release approval."}
    root = get_settings().root_dir.resolve()
    mappings = []
    for package in view.descriptor["packages"]:
        manifest_path = (root / package["path"]).resolve()
        if not manifest_path.is_relative_to(root):
            raise ValidationError("Greek source manifest escapes workspace")
        manifest_bytes = manifest_path.read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != package["sha256"]:
            raise ValidationError("Greek source package changed during read")
        manifest = json.loads(manifest_bytes)
        for file in manifest.get("files", []):
            path = file["path"]
            if path.endswith("map.json") and (
                manifest["kind"] == "versification" or "versification/" in path
            ):
                map_path = (manifest_path.parent / path).resolve()
                if not map_path.is_relative_to(manifest_path.parent):
                    raise ValidationError("Greek verse map escapes its source package")
                map_bytes = map_path.read_bytes()
                if (
                    hashlib.sha256(map_bytes).hexdigest() != file["sha256"]
                    or len(map_bytes) != file["size_bytes"]
                ):
                    raise ValidationError("Greek verse map changed during read")
                mapping = json.loads(map_bytes)
                if (mapping["edition_id"], mapping["text_revision_id"]) == (
                    view.descriptor["edition_id"],
                    view.descriptor["text_revision_id"],
                ):
                    mappings.extend(mapping["records"])
    greek_units = {unit["unit_id"]: unit for unit in view.payload.get("units", [])}
    entries = {entry["entry_id"]: entry for entry in view.payload.get("entries", [])}
    by_mt, used_entries = _by_mt_unit(
        mappings,
        registry_service.load_psalm(psalm_id)["units"],
        greek_units,
        entries,
        view.analyses,
        statuses={"reviewed"},
    )
    # Glosses and maps were read after load_view's policy check. A revocation or
    # release disable during this projection must discard the complete result.
    if source_capability_service.policy_revision() != view.policy_id:
        raise ValidationError("Greek source policy changed during source evidence read")
    if not availability(view.descriptor):
        return {**empty, "message": "Greek study is awaiting source release approval."}
    return {
        **view.identity(),
        "available": True,
        "by_mt_unit": by_mt,
        "edition_id": view.descriptor["edition_id"],
        "text_revision_id": view.descriptor["text_revision_id"],
        "source_attribution": [
            *view.payload.get("source_attribution", []),
            *list(
                {
                    entries[entry_id]["attribution"]["source_id"]: {
                        "attribution": entries[entry_id]["attribution"]["required_attribution"],
                        "license": entries[entry_id]["attribution"]["license"],
                    }
                    for entry_id in sorted(used_entries)
                    if entries[entry_id].get("attribution")
                }.values()
            ),
        ],
    }


def _preview_greek_evidence(psalm_id: str) -> dict[str, Any] | None:
    """The owner-approved unreleased preview, or None when no preview is approved."""
    try:
        preview = greek_preview_service.load_preview()
        if preview is None:
            return None
        greek_units = {unit["unit_id"]: unit for unit in preview["units"]}
        by_mt, _ = _by_mt_unit(
            preview["records"],
            registry_service.load_psalm(psalm_id)["units"],
            greek_units,
            {},
            {},
            statuses={"proposed", "reviewed"},
        )
    except LicensePolicyError:
        return {
            "by_mt_unit": {},
            "available": False,
            "state": "blocked",
            "message": "Greek preview is blocked by current source permissions.",
        }
    except (ValidationError, OSError, ValueError, KeyError, TypeError, SchemaValidationError):
        return {
            "by_mt_unit": {},
            "available": False,
            "state": "unavailable",
            "message": (
                "Greek preview unavailable: its approval or source package could not be verified."
            ),
        }
    from app.services import greek_lexical_preview_service

    units = {unit["unit_id"]: unit for mapping in by_mt.values() for unit in mapping["units"]}
    lexical = greek_lexical_preview_service.enrich(
        list(units.values()),
        preview.get("manifest_sha256"),
    )
    # Merged map records may show the same Greek verse beneath multiple MT units.
    for mapping in by_mt.values():
        mapping["units"] = [units[unit["unit_id"]] for unit in mapping["units"]]
    generation_available = source_capability_service.effective_capabilities(
        json.loads(greek_preview_service._approval_path().read_text(encoding="utf-8"))["source_id"]
    )["generation"]
    return {
        "available": True,
        "generation_available": generation_available,
        "preview": True,
        "message": (
            "Unreviewed text/proposed verse map; approved for local generation. "
            "Not approved for export or release."
            if generation_available
            else PREVIEW_MESSAGE
        ),
        "by_mt_unit": by_mt,
        "edition_id": preview["edition_id"],
        "text_revision_id": preview["text_revision_id"],
        **{key: value for key, value in lexical.items() if key != "source_attribution"},
        "source_attribution": [
            *preview["source_attribution"],
            *lexical.get("source_attribution", []),
        ],
    }


def _by_mt_unit(
    mappings: list[dict[str, Any]],
    mt_units: list[dict[str, Any]],
    greek_units: dict[str, dict[str, Any]],
    entries: dict[str, dict[str, Any]],
    analyses_by_token: dict[str, list[dict[str, Any]]],
    *,
    statuses: set[str],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    mt_ids = {unit["unit_id"] for unit in mt_units}
    mt_refs = {unit["ref"]: unit["unit_id"] for unit in mt_units}
    used_entries: set[str] = set()
    by_mt: dict[str, dict[str, Any]] = {}
    for mapping in mappings:
        if mapping["status"] not in statuses:
            continue
        endpoints = [*mapping["sources"], *mapping["targets"]]
        matched_mt = set()
        for endpoint in endpoints:
            unit_id = endpoint.get("unit_id")
            if unit_id and unit_id.startswith("lxx.") and unit_id not in greek_units:
                raise ValidationError(
                    "Greek verse-map endpoint is outside its published source revision"
                )
            if unit_id in mt_ids:
                matched_mt.add(unit_id)
            elif endpoint["baseline"].lower() in {"mt", "masoretic"}:
                if endpoint["reference"] in mt_refs:
                    matched_mt.add(mt_refs[endpoint["reference"]])
        for mt_id in matched_mt:
            evidence = by_mt.setdefault(mt_id, {"units": [], "relations": []})
            if mapping["relation"] not in evidence["relations"]:
                evidence["relations"].append(mapping["relation"])
            for endpoint in endpoints:
                unit = greek_units.get(endpoint.get("unit_id"))
                if unit is None:
                    continue
                span = endpoint.get("text_span")
                if span is not None and (
                    set(span) != {"start", "end"}
                    or any(type(span[key]) is not int for key in span)
                    or not 0 <= span["start"] < span["end"] <= len(unit["source_greek"])
                ):
                    raise ValidationError(
                        "Greek verse-map span does not resolve to its source text"
                    )
                existing = next(
                    (item for item in evidence["units"] if item["unit_id"] == unit["unit_id"]), None
                )
                if existing is not None:
                    if (
                        endpoint.get("text_span")
                        and endpoint["text_span"] not in existing["mapped_spans"]
                    ):
                        existing["mapped_spans"].append(dict(endpoint["text_span"]))
                        existing["partial"] = True
                    continue
                words = []
                for token in unit["tokens"]:
                    analyses = analyses_by_token.get(token["token_id"], [])
                    used_entries.update(
                        entry_id
                        for analysis in analyses
                        for entry_id in analysis.get("entry_ids", [])
                        if entries.get(entry_id, {}).get("gloss")
                    )
                    glosses = list(
                        dict.fromkeys(
                            entries[entry_id]["gloss"]
                            for analysis in analyses
                            for entry_id in analysis.get("entry_ids", [])
                            if entries.get(entry_id, {}).get("gloss")
                        )
                    )
                    words.append({**token, "gloss": " / ".join(glosses) or None})
                evidence["units"].append(
                    {
                        **unit,
                        "tokens": words,
                        "literal_text": " · ".join(word["gloss"] or "?" for word in words),
                        "partial": mapping["relation"] == "partial"
                        or bool(endpoint.get("text_span")),
                        "mapped_spans": [dict(endpoint["text_span"])]
                        if endpoint.get("text_span")
                        else [],
                    }
                )
    for evidence in by_mt.values():

        def source_order(unit: dict[str, Any]) -> tuple[str, int, str]:
            identity = parse_unit_id(unit["unit_id"], require_versioned=True)
            return identity.psalm_id, identity.verse, identity.segment

        evidence["units"].sort(key=source_order)
    return by_mt, used_entries
