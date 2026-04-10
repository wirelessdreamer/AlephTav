from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.services import registry_service


CANONICAL_SCOPES = {
    "hebrew_surface",
    "normalized_hebrew",
    "lemma",
    "strong",
    "morphology",
    "english_renderings",
    "audit_notes",
    "issue_links",
}
WITNESS_SCOPES = {"witness_text", "witness_metadata"}
ALL_SCOPES = CANONICAL_SCOPES | WITNESS_SCOPES | {"all"}


def list_witnesses(unit_id: str) -> list[dict[str, Any]]:
    unit = registry_service.load_unit(unit_id)
    return [
        {
            **witness,
            "unit_id": unit["unit_id"],
            "psalm_id": unit["psalm_id"],
            "canonical_ref": unit["ref"],
            "namespace": "witness",
        }
        for witness in unit.get("witnesses", [])
    ]


def advanced_search(query: str, scope: str = "all", include_witnesses: bool = False) -> list[dict[str, Any]]:
    if scope not in ALL_SCOPES:
        raise ValidationError(f"Unsupported search scope: {scope}")

    needle = query.strip().casefold()
    if not needle:
        return []

    results: list[dict[str, Any]] = []
    for unit in registry_service.list_units():
        results.extend(_search_unit(unit, needle, scope, include_witnesses))
    return sorted(results, key=lambda item: (item["ref"], item["kind"], item["label"]))


def preset_view(name: str, release_id: str | None = None) -> list[dict[str, Any]]:
    if name == "alternates_meter_fit":
        return _meter_fit_alternates()
    if name == "units_with_unresolved_drift":
        return _units_with_unresolved_drift()
    if name == "units_changed_since_release":
        if not release_id:
            raise ValidationError("release_id is required for units_changed_since_release")
        cutoff = _resolve_release_timestamp(release_id)
        return _units_changed_since(cutoff)
    raise ValidationError(f"Unsupported preset view: {name}")


def _search_unit(unit: dict[str, Any], needle: str, scope: str, include_witnesses: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if scope in {"all", "hebrew_surface", "normalized_hebrew", "lemma", "strong", "morphology"}:
        results.extend(_search_tokens(unit, needle, scope))
    if scope in {"all", "english_renderings"}:
        results.extend(_search_renderings(unit, needle))
    if scope in {"all", "audit_notes"}:
        results.extend(_search_audit(unit, needle))
    if scope in {"all", "issue_links"}:
        results.extend(_search_links(unit, needle))
    if scope in WITNESS_SCOPES or (scope == "all" and include_witnesses):
        results.extend(_search_witnesses(unit, needle, scope))
    return results


def _search_tokens(unit: dict[str, Any], needle: str, scope: str) -> Iterable[dict[str, Any]]:
    scopes = {
        "hebrew_surface": [("surface", "surface")],
        "normalized_hebrew": [("normalized", "normalized")],
        "lemma": [("lemma", "lemma")],
        "strong": [("strong", "strong")],
        "morphology": [("morph_code", "morphology"), ("morph_readable", "morphology"), ("stem", "morphology")],
        "all": [
            ("surface", "surface"),
            ("normalized", "normalized"),
            ("lemma", "lemma"),
            ("strong", "strong"),
            ("morph_code", "morphology"),
            ("morph_readable", "morphology"),
            ("stem", "morphology"),
        ],
    }[scope]
    seen: set[tuple[str, str]] = set()
    for token in unit.get("tokens", []):
        for field_name, label in scopes:
            value = token.get(field_name)
            if _matches(value, needle):
                dedupe_key = (token["token_id"], label)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                yield {
                    "kind": "token",
                    "namespace": "canonical",
                    "scope": label,
                    "label": token["surface"],
                    "snippet": f"{token.get('lemma') or '—'} / {token.get('strong') or '—'} / {token.get('morph_readable') or token.get('morph_code') or '—'}",
                    "unit_id": unit["unit_id"],
                    "psalm_id": unit["psalm_id"],
                    "ref": token["ref"],
                    "token_id": token["token_id"],
                }


def _search_renderings(unit: dict[str, Any], needle: str) -> Iterable[dict[str, Any]]:
    for rendering in unit.get("renderings", []):
        if _matches(rendering.get("text"), needle):
            yield {
                "kind": "rendering",
                "namespace": "canonical",
                "scope": "english_renderings",
                "label": rendering["rendering_id"],
                "snippet": rendering["text"],
                "unit_id": unit["unit_id"],
                "psalm_id": unit["psalm_id"],
                "ref": unit["ref"],
                "rendering_id": rendering["rendering_id"],
                "status": rendering["status"],
                "layer": rendering["layer"],
            }


def _search_audit(unit: dict[str, Any], needle: str) -> Iterable[dict[str, Any]]:
    for record in unit.get("audit_records", []):
        haystacks = [record.get("summary"), record.get("rationale"), record.get("created_by")]
        if any(_matches(value, needle) for value in haystacks):
            yield {
                "kind": "audit_record",
                "namespace": "canonical",
                "scope": "audit_notes",
                "label": record["summary"],
                "snippet": record.get("rationale") or record.get("created_by") or "",
                "unit_id": unit["unit_id"],
                "psalm_id": unit["psalm_id"],
                "ref": unit["ref"],
                "audit_id": record["audit_id"],
            }
    for decision in unit.get("review_decisions", []):
        haystacks = [decision.get("decision"), decision.get("notes"), decision.get("reviewer"), decision.get("reviewer_role")]
        if any(_matches(value, needle) for value in haystacks):
            yield {
                "kind": "review_decision",
                "namespace": "canonical",
                "scope": "audit_notes",
                "label": decision["decision"],
                "snippet": decision.get("notes") or decision.get("reviewer") or "",
                "unit_id": unit["unit_id"],
                "psalm_id": unit["psalm_id"],
                "ref": unit["ref"],
                "decision_id": decision["decision_id"],
            }


def _search_links(unit: dict[str, Any], needle: str) -> Iterable[dict[str, Any]]:
    for issue_link in unit.get("issue_links", []):
        if _matches(issue_link, needle):
            yield {
                "kind": "issue_link",
                "namespace": "canonical",
                "scope": "issue_links",
                "label": issue_link,
                "snippet": "Issue-linked unit",
                "unit_id": unit["unit_id"],
                "psalm_id": unit["psalm_id"],
                "ref": unit["ref"],
            }
    for pr_link in unit.get("pr_links", []):
        if _matches(pr_link, needle):
            yield {
                "kind": "pr_link",
                "namespace": "canonical",
                "scope": "issue_links",
                "label": pr_link,
                "snippet": "PR-linked unit",
                "unit_id": unit["unit_id"],
                "psalm_id": unit["psalm_id"],
                "ref": unit["ref"],
            }


def _search_witnesses(unit: dict[str, Any], needle: str, scope: str) -> Iterable[dict[str, Any]]:
    for witness in unit.get("witnesses", []):
        text_match = _matches(witness.get("text"), needle)
        metadata_match = any(
            _matches(witness.get(field_name), needle)
            for field_name in ("source_id", "versionTitle", "language", "ref", "source_url")
        )
        if scope == "witness_text" and not text_match:
            continue
        if scope == "witness_metadata" and not metadata_match:
            continue
        if scope == "all" and not (text_match or metadata_match):
            continue
        yield {
            "kind": "witness",
            "namespace": "witness",
            "scope": "witness_text" if text_match else "witness_metadata",
            "label": f"{witness['source_id']} · {witness['versionTitle']}",
            "snippet": witness.get("text") or witness.get("source_url") or "",
            "unit_id": unit["unit_id"],
            "psalm_id": unit["psalm_id"],
            "ref": unit["ref"],
            "source_id": witness["source_id"],
            "versionTitle": witness["versionTitle"],
            "language": witness["language"],
            "source_url": witness["source_url"],
            "witness_ref": witness["ref"],
        }


def _meter_fit_alternates() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for unit in registry_service.list_units():
        for rendering in unit.get("renderings", []):
            if rendering["status"] == "canonical":
                continue
            tags = {tag.casefold() for tag in rendering.get("style_tags", [])}
            if "meter-fit" not in tags and not any("meter" in tag for tag in tags) and rendering["layer"] != "metered_lyric":
                continue
            results.append(
                {
                    "kind": "rendering",
                    "namespace": "canonical",
                    "scope": "alternates_meter_fit",
                    "label": rendering["rendering_id"],
                    "snippet": rendering["text"],
                    "unit_id": unit["unit_id"],
                    "psalm_id": unit["psalm_id"],
                    "ref": unit["ref"],
                    "status": rendering["status"],
                    "layer": rendering["layer"],
                }
            )
    return sorted(results, key=lambda item: (item["ref"], item["label"]))


def _units_with_unresolved_drift() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for unit in registry_service.list_units():
        flags = sorted({flag for rendering in unit.get("renderings", []) for flag in rendering.get("drift_flags", [])})
        if not flags:
            continue
        results.append(
            {
                "kind": "unit",
                "namespace": "canonical",
                "scope": "units_with_unresolved_drift",
                "label": unit["unit_id"],
                "snippet": ", ".join(flags),
                "unit_id": unit["unit_id"],
                "psalm_id": unit["psalm_id"],
                "ref": unit["ref"],
            }
        )
    return results


def _units_changed_since(cutoff: datetime) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for unit in registry_service.list_units():
        changed_at = [
            _parse_datetime(record["created_at"])
            for record in unit.get("audit_records", [])
            if record.get("created_at")
        ]
        if not changed_at or max(changed_at) <= cutoff:
            continue
        results.append(
            {
                "kind": "unit",
                "namespace": "canonical",
                "scope": "units_changed_since_release",
                "label": unit["unit_id"],
                "snippet": f"Latest audit change {max(changed_at).isoformat()}",
                "unit_id": unit["unit_id"],
                "psalm_id": unit["psalm_id"],
                "ref": unit["ref"],
            }
        )
    return results


def _resolve_release_timestamp(release_id: str) -> datetime:
    settings = get_settings()
    candidates = [
        settings.release_reports_dir / "release_manifest.json",
        settings.release_reports_dir / release_id / "bundle" / "AUDIT_REPORT.json",
    ]
    for path in candidates:
        timestamp = _timestamp_from_release_file(path, release_id)
        if timestamp is not None:
            return timestamp
    try:
        return _parse_datetime(release_id)
    except ValueError as error:
        raise NotFoundError(f"Release not found: {release_id}") from error


def _timestamp_from_release_file(path: Path, release_id: str) -> datetime | None:
    if not path.exists():
        return None
    payload = registry_service.read_json(path)
    if payload.get("release_id") != release_id:
        return None
    generated_at = payload.get("generated_at")
    if not generated_at:
        return None
    return _parse_datetime(generated_at)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _matches(value: Any, needle: str) -> bool:
    return needle in str(value or "").casefold()
