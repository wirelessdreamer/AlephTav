"""Append-only translator intentions bound to authored text, never review authority.

Context declarations are the translator's self-report. Neither this record nor its
revision digest establishes source support, resolves a concern, or authorizes release.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.core.ids import ID_PATTERNS, parse_unit_id, unit_id_from_entity_id
from app.services import arrangement_service, registry_service, translation_context_service
from app.services import psalm_translations_service as translations

_lock = RLock()
_HEX = re.compile(r"[0-9a-f]{64}")
_ARRANGEMENT = re.compile(r"arr\.ps\d{3}\.\d{4}")
_LINE = re.compile(r"ln\.\d{4}")
_TRANSLATION = re.compile(r"tr\.ps\d{3}\.\d{4}")
_DOMAIN = b"alephtav:intentional-choice:authored-target:v1\0"
_RENDERING_FIELDS = (
    "text",
    "layer",
    "style_tags",
    "target_spans",
    "alignment_ids",
    "rationale",
    "variation_basis",
    "preserved_source_images",
    "differentiator",
    "delivery_profile",
    "source_anchor",
    "translation_basis",
    "style_goal",
    "metric_profile",
)


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError(f"{name} must be nonblank text of at most {limit} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValidationError(f"{name} must be valid Unicode text") from exc
    return value.strip()


def _id(value: Any, name: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or len(value) > 200 or not pattern.fullmatch(value):
        raise ValidationError(f"Invalid {name}")
    return value


def _pick(record: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    try:
        return {key: deepcopy(record[key]) for key in fields if key in record}
    except RecursionError as exc:
        raise ValidationError("Authored target nesting exceeds supported limits") from exc


def _revision(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Pure authored-content fingerprint, independent of source/review availability."""
    try:
        encoded = json.dumps(
            snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValidationError("Authored target cannot be fingerprinted") from exc
    return {
        "version": 1,
        "algorithm": "sha256",
        "value": hashlib.sha256(_DOMAIN + encoded).hexdigest(),
    }


def _key(target: dict[str, Any]) -> tuple[str, str, str | None]:
    return target["kind"], target["id"], target.get("arrangement_id")


def _identity(target: dict[str, Any]) -> tuple[Any, ...]:
    return (*_key(target), target.get("unit_id"), target.get("translation_id"), target["shared"])


def _target(
    psalm_id: str,
    *,
    kind: str,
    target_id: str,
    layer: str,
    text: str,
    context_text: str,
    authored: dict[str, Any],
    translation_id: str | None,
    shared: bool = False,
    unit_id: str | None = None,
    arrangement_id: str | None = None,
) -> dict[str, Any]:
    target: dict[str, Any] = {
        "kind": kind,
        "id": target_id,
        "layer": layer,
        "text": text,
        "context_text": context_text,
        "translation_id": translation_id,
        "shared": shared,
    }
    if unit_id is not None:
        target["unit_id"] = unit_id
    if arrangement_id is not None:
        target["arrangement_id"] = arrangement_id
    snapshot = {"psalm_id": psalm_id, "target": deepcopy(target), "authored": authored}
    target["authored_snapshot"] = snapshot
    target["revision"] = _revision(snapshot)
    return target


def _arrangement_snapshot(arrangement: dict[str, Any]) -> dict[str, Any]:
    """Keep the complete written/performed order and declared departures, not approvals."""
    sections = []
    seen_sections: set[str] = set()
    seen_lines: set[str] = set()
    for section in arrangement.get("sections", []):
        section_id = section["section_id"]
        if section_id in seen_sections:
            raise ValidationError("Ambiguous arrangement section")
        seen_sections.add(section_id)
        lines = []
        for line in section["lines"]:
            if line["line_id"] in seen_lines:
                raise ValidationError("Ambiguous arrangement line")
            seen_lines.add(line["line_id"])
            lines.append(_pick(line, ("line_id", "text", "anchors", "liberty", "rationale")))
        sections.append(
            {
                **_pick(section, ("section_id", "kind", "label", "repeat_of")),
                "lines": lines,
            }
        )
    by_id = {section["section_id"]: section for section in sections}
    for section in sections:
        repeat = section["repeat_of"]
        if repeat is not None and (repeat not in by_id or by_id[repeat]["repeat_of"] is not None):
            raise ValidationError("Invalid arrangement repeat context")
    return {
        **_pick(arrangement, ("title", "layer")),
        "sections": sections,
        "omissions": [
            _pick(omission, ("unit_id", "token_ids", "rationale"))
            for omission in arrangement.get("omissions", [])
        ],
    }


def _targets(psalm_id: str, translation_id: str | None) -> list[dict[str, Any]]:
    _id(psalm_id, "psalm_id", ID_PATTERNS["psalm_id"])
    if translation_id is not None:
        _id(translation_id, "translation_id", _TRANSLATION)
    translations.require(psalm_id, translation_id)
    meta = registry_service.load_psalm_meta(psalm_id)
    if meta.get("psalm_id") != psalm_id:
        raise ValidationError("Psalm metadata has a different identity")
    targets: list[dict[str, Any]] = []
    seen_units: set[str] = set()
    seen_renderings: set[str] = set()
    for unit_id in meta.get("unit_ids", []):
        _id(unit_id, "unit_id", ID_PATTERNS["unit_id"])
        if parse_unit_id(unit_id).psalm_id != psalm_id or unit_id in seen_units:
            raise ValidationError("Psalm unit membership is invalid or ambiguous")
        seen_units.add(unit_id)
        unit = registry_service.load_unit(unit_id)
        if unit.get("unit_id") != unit_id:
            raise ValidationError("Unit has a different identity")
        for rendering in unit.get("renderings", []):
            target_id = rendering["rendering_id"]
            _id(target_id, "rendering_id", ID_PATTERNS["rendering_id"])
            if (
                target_id in seen_renderings
                or rendering.get("unit_id") != unit_id
                or unit_id_from_entity_id("rendering_id", target_id) != unit_id
            ):
                raise ValidationError("Rendering parent is invalid or ambiguous")
            seen_renderings.add(target_id)
            if not translations.shows_in(rendering, translation_id):
                continue
            authored = _pick(rendering, _RENDERING_FIELDS)
            authored["declared_provenance"] = _pick(
                rendering.get("provenance") or {}, ("source_ids", "translation_basis")
            )
            span_ids = {span["span_id"] for span in rendering.get("target_spans", [])}
            authored["alignments"] = sorted(
                [
                    _pick(
                        a,
                        (
                            "alignment_id",
                            "source_token_ids",
                            "target_span_ids",
                            "alignment_type",
                            "notes",
                        ),
                    )
                    for a in unit.get("alignments", [])
                    if a["alignment_id"] in rendering.get("alignment_ids", [])
                    or span_ids.intersection(a.get("target_span_ids", []))
                ],
                key=lambda a: a["alignment_id"],
            )
            targets.append(
                _target(
                    psalm_id,
                    kind="rendering",
                    target_id=target_id,
                    unit_id=unit_id,
                    layer=rendering["layer"],
                    text=rendering["text"],
                    context_text=rendering["text"],
                    authored=authored,
                    translation_id=rendering.get("translation_id"),
                    shared=rendering["layer"] in translations.SHARED_LAYERS,
                )
            )
    seen_arrangements: set[str] = set()
    for arrangement in meta.get("arrangements", []):
        arrangement_id = arrangement["arrangement_id"]
        _id(arrangement_id, "arrangement_id", _ARRANGEMENT)
        if (
            arrangement_id in seen_arrangements
            or arrangement.get("psalm_id") != psalm_id
            or not arrangement_id.startswith(f"arr.{psalm_id}.")
        ):
            raise ValidationError("Arrangement parent is invalid or ambiguous")
        seen_arrangements.add(arrangement_id)
        if not translations.in_translation(arrangement, translation_id):
            continue
        authored = _arrangement_snapshot(arrangement)
        performance = arrangement_service.sung_lines(authored)
        context_text = "\n".join(item["line"]["text"] for item in performance)
        for section in authored["sections"]:
            for line in section["lines"]:
                targets.append(
                    _target(
                        psalm_id,
                        kind="arrangement_line",
                        target_id=line["line_id"],
                        arrangement_id=arrangement_id,
                        layer=arrangement["layer"],
                        text=line["text"],
                        context_text=context_text,
                        authored=authored,
                        translation_id=arrangement.get("translation_id"),
                    )
                )
    return targets


def _history(psalm_id: str, translation_id: str | None) -> list[dict[str, Any]]:
    return [
        entry
        for entry in translation_context_service.history(psalm_id, translation_id)
        if entry.get("kind") == "intentional_choice" and entry.get("choice", {}).get("version") == 1
    ]


def _entries(history: list[dict[str, Any]], targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = {_key(target): target for target in targets}
    superseded = {
        entry["choice"]["supersedes_audit_id"]: entry["audit_id"]
        for entry in history
        if entry["choice"].get("supersedes_audit_id")
    }
    result = []
    for entry in history:
        state = "current"
        for old in entry["choice"]["targets"]:
            new = current.get(_key(old))
            if new is None:
                state = "missing"
                break
            if _identity(old) != _identity(new) or old["revision"] != new["revision"]:
                state = "changed"
        result.append(
            {
                **deepcopy(entry),
                "target_state": state,
                "superseded_by_audit_id": superseded.get(entry["audit_id"]),
                "counts_for_publication": False,
            }
        )
    return result


def choices_view(
    psalm_id: str,
    translation_id: str | None = None,
    *,
    unit_id: str | None = None,
    arrangement_id: str | None = None,
) -> dict[str, Any]:
    """Read scoped authored targets and their durable intentions, including obsolete ones."""
    targets = _targets(psalm_id, translation_id)
    meta = registry_service.load_psalm_meta(psalm_id)
    if unit_id is not None:
        _id(unit_id, "unit_id", ID_PATTERNS["unit_id"])
        if unit_id not in meta.get("unit_ids", []):
            raise NotFoundError("Unit is not in this psalm")
    if arrangement_id is not None:
        _id(arrangement_id, "arrangement_id", _ARRANGEMENT)
        if not any(
            a["arrangement_id"] == arrangement_id and translations.in_translation(a, translation_id)
            for a in meta.get("arrangements", [])
        ):
            raise NotFoundError("Arrangement is not in this translation")

    def selected(target: dict[str, Any]) -> bool:
        if arrangement_id is not None and target.get("arrangement_id") != arrangement_id:
            return False
        if unit_id is None or target.get("unit_id") == unit_id:
            return True
        if target["kind"] == "arrangement_line":
            for section in target["authored_snapshot"]["authored"]["sections"]:
                for line in section["lines"]:
                    if line["line_id"] == target["id"]:
                        return any(a["unit_id"] == unit_id for a in line["anchors"])
        return False

    entries = _entries(_history(psalm_id, translation_id), targets)
    return {
        "psalm_id": psalm_id,
        "translation_id": translation_id,
        "targets": [target for target in targets if selected(target)],
        "choices": [
            entry
            for entry in entries
            if any(selected(target) for target in entry["choice"]["targets"])
        ],
    }


def record_choice(
    psalm_id: str,
    translation_id: str | None = None,
    *,
    targets: list[dict[str, Any]],
    decision: str,
    rationale: str,
    context_status: str,
    context_note: str,
    created_by: str,
    supersedes_audit_id: str | None = None,
) -> dict[str, Any]:
    """Append a server-resolved intention; corrections preserve the earlier evidence."""
    decision = _text(decision, "decision", 2000)
    rationale = _text(rationale, "rationale", 8000)
    context_note = _text(context_note, "context_note", 4000)
    created_by = _text(created_by, "created_by", 200)
    if context_status not in ("not_established", "provided_by_translator"):
        raise ValidationError("Unknown context_status")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 20:
        raise ValidationError("A choice needs between 1 and 20 targets")
    refs = []
    seen: set[tuple[str, str, str | None]] = set()
    for ref in targets:
        if not isinstance(ref, dict) or ref.get("kind") not in ("rendering", "arrangement_line"):
            raise ValidationError("Invalid choice target")
        expected_keys = {"kind", "id", "expected_revision"}
        if ref["kind"] == "arrangement_line":
            expected_keys.add("arrangement_id")
        if set(ref) != expected_keys:
            raise ValidationError("Choice target has missing or unknown fields")
        _id(
            ref["id"],
            "target id",
            ID_PATTERNS["rendering_id"] if ref["kind"] == "rendering" else _LINE,
        )
        if ref["kind"] == "arrangement_line":
            _id(ref["arrangement_id"], "arrangement_id", _ARRANGEMENT)
        _id(ref["expected_revision"], "expected_revision", _HEX)
        if _key(ref) in seen:
            raise ValidationError("Duplicate choice target")
        seen.add(_key(ref))
        refs.append(deepcopy(ref))
    if supersedes_audit_id is not None:
        _id(supersedes_audit_id, "supersedes_audit_id", ID_PATTERNS["audit_id"])

    with _lock:
        available = _targets(psalm_id, translation_id)
        by_key = {_key(target): target for target in available}
        resolved = []
        for ref in refs:
            target = by_key.get(_key(ref))
            if target is None:
                raise NotFoundError("Choice target is not in this psalm and translation")
            if target["revision"]["value"] != ref["expected_revision"]:
                raise ValidationError("Choice target changed; reload before recording the choice")
            resolved.append(target)
        history = _history(psalm_id, translation_id)
        previous = None
        if supersedes_audit_id is not None:
            previous = next((e for e in history if e["audit_id"] == supersedes_audit_id), None)
            if previous is None:
                raise ValidationError("Correction must reference an earlier choice in this scope")
            if any(e["choice"].get("supersedes_audit_id") == supersedes_audit_id for e in history):
                raise ValidationError("Choice already has a correction")
            if {_identity(t) for t in previous["choice"]["targets"]} != {
                _identity(t) for t in resolved
            }:
                raise ValidationError("Correction must concern the same target identities")
            try:
                previous_time = datetime.fromisoformat(
                    previous["created_at"].replace("Z", "+00:00")
                )
                future = previous_time > datetime.now(UTC)
            except (ValueError, TypeError) as exc:
                raise ValidationError("Correction references an invalid earlier timestamp") from exc
            if future:
                raise ValidationError("Correction cannot reference a future choice")
        choice = {
            "version": 1,
            "targets": resolved,
            "decision": decision,
            "rationale": rationale,
            "context_status": context_status,
            "context_note": context_note,
            "supersedes_audit_id": supersedes_audit_id,
        }
        entry = translation_context_service.append(
            psalm_id,
            translation_id,
            kind="intentional_choice",
            summary="Record intentional translation choice",
            snapshot={"choice": choice},
            previous=previous["choice"] if previous else None,
            created_by=created_by,
        )
        return _entries([entry], available)[0]
