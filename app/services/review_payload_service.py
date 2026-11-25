"""Pure version-2 review bindings; these hashes neither grant rights nor replace audit hashes.

The constants below are the explicit projection contract. Unknown provenance and
derived review/audit/runtime fields are deliberately excluded. Ordered semantic
arrays and exact text are retained; only identified record collections are sorted.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any

from app.core.errors import ValidationError

PAYLOAD_VERSION = 2
PAYLOAD_DOMAIN = "alephtav.rendering-review-payload.v2"
POLICY_DOMAIN = "alephtav.rendering-review-policy.v2"
PASS_DEPENDENCIES = {
    "gloss": (),
    "literal": ("gloss",),
    "phrase": ("literal",),
    "concept": ("literal", "phrase"),
    "lyric": ("gloss", "literal", "phrase", "concept"),
    "metered_lyric": ("literal", "phrase", "concept", "lyric"),
    "parallelism_lyric": ("metered_lyric",),
}
LYRIC_LAYERS = {"lyric", "metered_lyric", "parallelism_lyric"}
TARGET_FIELDS = (
    "rendering_id",
    "unit_id",
    "layer",
    "translation_id",
    "text",
    "target_spans",
    "style_tags",
    "rationale",
    "variation_basis",
    "preserved_source_images",
    "differentiator",
    "delivery_profile",
    "style_goal",
    "metric_profile",
)
UNIT_FIELDS = (
    "unit_id",
    "psalm_id",
    "ref",
    "segmentation_type",
    "source_hebrew",
    "source_transliteration",
    "token_ids",
)
TOKEN_FIELDS = (
    "token_id",
    "ref",
    "surface",
    "normalized",
    "transliteration",
    "greek",
    "greek_strong",
    "lemma",
    "strong",
    "morph_code",
    "morph_readable",
    "part_of_speech",
    "stem",
    "syntax_role",
    "semantic_role",
    "referent",
    "word_sense",
    "gloss_parts",
    "display_gloss",
    "compiler_features",
    "enrichment_sources",
    "missing_enrichments",
)
BASIS_FIELDS = ("basis_type", "source_ids", "source_language", "source_version", "basis_note")
ANCHOR_FIELDS = ("anchor_text", "source_language", "source_text", "token_ids", "basis_note")
GREEK_SOURCE_FIELDS = (
    "source_id",
    "package_id",
    "manifest_sha256",
    "edition_id",
    "text_revision_id",
    "source_version",
    "greek_unit_id",
    "mt_unit_id",
    "token_ids",
    "map_status",
    "map_id",
    "map_revision",
    "map_revision_id",
    "map_sha256",
    "map_snapshot_id",
    "snapshot_id",
    "study_snapshot_id",
    "mt_snapshot_id",
    "snapshot_sha256",
    "package_sha256",
    "source_attribution",
    "policy_revision",
)
ALIGNMENT_FIELDS = (
    "alignment_id",
    "unit_id",
    "layer",
    "source_token_ids",
    "target_span_ids",
    "alignment_type",
    "confidence",
    "notes",
)
STYLE_FIELDS = (
    "style_profile_id",
    "literalness",
    "lyric_freedom",
    "target_syllables",
    "rhyme_mode",
    "register",
    "parallelism_priority",
    "source_anchor_mode",
    "metaphor_mode",
    "imagery_preservation",
    "idiom_modernity",
    "emotional_directness",
    "divine_name_rendering",
    "faith_posture",
)
MANIFEST_FIELDS = (
    "source_id",
    "version",
    "source_language",
    "basis_role",
    "version_pinned",
    "import_hash",
    "license",
    "upstream_url",
    "allowed_for_display",
    "allowed_for_generation",
    "allowed_for_export",
)
CAPABILITIES = ("display", "export", "generation", "dictionary", "analysis")
AUTHORITY_DECISION_FIELDS = ("role", "reviewer_id", "decision", "payload_hash")
ATTRIBUTION_FIELDS = ("attribution", "license")


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    return value


def _records(value: dict[str, Any], key: str) -> list[dict[str, Any]]:
    records = value.get(key, [])
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ValidationError(f"{key} must be a list of objects")
    return records


def _strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValidationError(f"{label} must be a list of strings")
    return value


def _identity(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be nonempty text")
    return value


def _text_fields(value: dict[str, Any], names: tuple[str, ...], *, nullable: bool = True) -> None:
    for name in names:
        if name in value and not isinstance(value[name], str):
            if not nullable or value[name] is not None:
                raise ValidationError(f"{name} must be text")


def _fields(value: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    try:
        result = {name: deepcopy(value[name]) for name in names if name in value}
    except RecursionError as error:
        raise ValidationError("Review evidence nesting exceeds the supported depth") from error
    missing = [name for name in names if name not in value]
    if missing:
        result["_missing_fields"] = missing
    return result


def _optional_object(value: dict[str, Any], key: str, names: tuple[str, ...]) -> dict[str, Any]:
    if key not in value:
        return {"present": False}
    if value[key] is None:
        return {"present": True, "value": None}
    record = _object(value[key], key)
    for list_key in ("source_ids", "token_ids"):
        if list_key in record:
            _strings(record[list_key], f"{key}.{list_key}")
    _text_fields(
        record,
        tuple(
            name for name in names if name not in {"source_ids", "token_ids", "source_attribution"}
        ),
        nullable=False,
    )
    projected = _fields(record, names)
    if "source_attribution" in names and "source_attribution" in record:
        attributions = _records(record, "source_attribution")
        for attribution in attributions:
            for name in ATTRIBUTION_FIELDS:
                _identity(attribution.get(name), f"source_attribution.{name}")
        projected["source_attribution"] = [
            _fields(attribution, ATTRIBUTION_FIELDS) for attribution in attributions
        ]
    return {"present": True, "value": projected}


def _hash(value: dict[str, Any]) -> str:
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValidationError("Review binding must contain finite JSON data") from error
    return hashlib.sha256(encoded).hexdigest()


def _context(
    unit: dict[str, Any], target_id: str, project: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    _object(unit, "unit")
    _object(project, "project")
    _identity(unit.get("unit_id"), "unit_id")
    _identity(target_id, "target_id")
    renderings = _records(unit, "renderings")
    matches = [item for item in renderings if item.get("rendering_id") == target_id]
    if len(matches) != 1:
        raise ValidationError("Review target must identify exactly one rendering")
    target = matches[0]
    layer = target.get("layer")
    if not isinstance(layer, str) or layer not in PASS_DEPENDENCIES:
        raise ValidationError("Review target has an invalid layer")
    dependencies = list(PASS_DEPENDENCIES[layer])
    if layer in LYRIC_LAYERS and "literal" not in dependencies:
        dependencies.append("literal")
    selected = [target]
    missing = []
    for dependency in dependencies:
        candidates = [
            item
            for item in renderings
            if item.get("layer") == dependency and item.get("status") == "canonical"
        ]
        if len(candidates) > 1:
            raise ValidationError(f"Ambiguous canonical {dependency} dependency")
        if candidates:
            _identity(candidates[0].get("rendering_id"), "upstream rendering_id")
            selected.append(candidates[0])
        else:
            missing.append({"layer": dependency, "present": False})
    return target, selected, missing


def _source(unit: dict[str, Any]) -> dict[str, Any]:
    _text_fields(unit, tuple(name for name in UNIT_FIELDS if name != "token_ids"), nullable=False)
    tokens = _records(unit, "tokens")
    token_ids = [_identity(token.get("token_id"), "token_id") for token in tokens]
    if len(token_ids) != len(set(token_ids)):
        raise ValidationError("Duplicate source token identity")
    if "token_ids" in unit and _strings(unit["token_ids"], "token_ids") != token_ids:
        raise ValidationError("Source token membership/order disagrees with token records")
    for token in tokens:
        _text_fields(
            token,
            tuple(
                name
                for name in TOKEN_FIELDS
                if name
                not in {
                    "gloss_parts",
                    "compiler_features",
                    "enrichment_sources",
                    "missing_enrichments",
                }
            ),
        )
        _text_fields(token, ("token_id", "surface", "normalized", "ref"), nullable=False)
        for key in ("gloss_parts", "missing_enrichments"):
            if key in token:
                _strings(token[key], key)
        for key in ("compiler_features", "enrichment_sources"):
            if key in token:
                _object(token[key], key)
    result = _fields(unit, UNIT_FIELDS)
    result["tokens"] = {
        "present": "tokens" in unit,
        "items": [_fields(token, TOKEN_FIELDS) for token in tokens],
    }
    return result


def _alignments(unit: dict[str, Any], rendering: dict[str, Any]) -> dict[str, Any]:
    spans = _records(rendering, "target_spans")
    span_ids = [_identity(span.get("span_id"), "span_id") for span in spans]
    if len(span_ids) != len(set(span_ids)):
        raise ValidationError("Duplicate review target span identity")
    owned = set(span_ids)
    for span in spans:
        if not isinstance(span.get("text"), str):
            raise ValidationError("Target span text must be text")
        start, end = span.get("token_start"), span.get("token_end")
        if type(start) is not int or type(end) is not int or not 0 <= start <= end:
            raise ValidationError("Target span boundaries are invalid")
    for other in _records(unit, "renderings"):
        if other is rendering:
            continue
        for span in _records(other, "target_spans"):
            if span.get("span_id") in owned:
                raise ValidationError("Review target span ownership is ambiguous")
    known_tokens = {token["token_id"] for token in _records(unit, "tokens")}
    selected = []
    identities = set()
    for alignment in _records(unit, "alignments"):
        endpoints = _strings(alignment.get("target_span_ids"), "target_span_ids")
        if not owned.intersection(endpoints):
            continue
        if (
            alignment.get("layer") != rendering["layer"]
            or alignment.get("unit_id") != unit["unit_id"]
            or not set(endpoints) <= owned
            or len(endpoints) != len(set(endpoints))
        ):
            raise ValidationError("Selected alignment has invalid or cross-owned target endpoints")
        sources = _strings(alignment.get("source_token_ids"), "source_token_ids")
        if not sources or not set(sources) <= known_tokens or len(sources) != len(set(sources)):
            raise ValidationError("Selected alignment has invalid source endpoints")
        identity = _identity(alignment.get("alignment_id"), "alignment_id")
        if identity in identities:
            raise ValidationError("Duplicate selected alignment identity")
        identities.add(identity)
        confidence = alignment.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ValidationError("Selected alignment confidence is invalid")
        if not 0 <= confidence <= 1 or not math.isfinite(confidence):
            raise ValidationError("Selected alignment confidence is invalid")
        selected.append(_fields(alignment, ALIGNMENT_FIELDS))
    return {
        "present": "alignments" in unit,
        "records": sorted(selected, key=lambda item: item["alignment_id"]),
    }


def _rendering(unit: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value.get("text"), str):
        raise ValidationError("Rendering text must be text")
    if "unit_id" in value and value["unit_id"] != unit["unit_id"]:
        raise ValidationError("Rendering belongs to a different unit")
    for key in ("style_tags", "variation_basis"):
        if key in value:
            _strings(value[key], key)
    if "rationale" in value and not isinstance(value["rationale"], str):
        raise ValidationError("Rendering rationale must be text")
    _text_fields(
        value,
        ("translation_id", "differentiator", "delivery_profile", "style_goal", "metric_profile"),
    )
    _records(value, "preserved_source_images")
    provenance = _object(value.get("provenance", {}), "provenance")
    for key in ("source_ids", "alignment_hints"):
        if key in provenance:
            _strings(provenance[key], f"provenance.{key}")
    result = _fields(value, TARGET_FIELDS)
    result["translation_basis"] = _optional_object(value, "translation_basis", BASIS_FIELDS)
    result["source_anchor"] = _optional_object(value, "source_anchor", ANCHOR_FIELDS)
    result["source_claims"] = {
        "provenance_present": "provenance" in value,
        **_fields(provenance, ("source_ids", "alignment_hints")),
        "translation_basis": _optional_object(provenance, "translation_basis", BASIS_FIELDS),
        "greek_generation_source": _optional_object(
            provenance, "greek_generation_source", GREEK_SOURCE_FIELDS
        ),
    }
    result["formal_alignments"] = _alignments(unit, value)
    return result


def _styles(project: dict[str, Any], selected: list[dict[str, Any]]) -> dict[str, Any]:
    references: set[str] = set()
    for rendering in selected:
        references.update(_strings(rendering.get("style_tags", []), "style_tags"))
        for key in ("style_goal", "metric_profile"):
            value = rendering.get(key)
            if value is not None:
                if not isinstance(value, str):
                    raise ValidationError(f"{key} must be text")
                references.add(value)
    profiles = []
    identities = set()
    for profile in _records(project, "style_profiles"):
        identity = profile.get("style_profile_id")
        if not isinstance(identity, str):
            raise ValidationError("style_profile_id must be text")
        if identity not in references:
            continue
        if identity in identities:
            raise ValidationError("Duplicate applicable style profile")
        identities.add(identity)
        profiles.append(_fields(profile, STYLE_FIELDS))
    return {
        **_fields(project, ("divine_name_policy",)),
        "profiles_present": "style_profiles" in project,
        "profiles": sorted(profiles, key=lambda item: item["style_profile_id"]),
    }


def review_payload_digest(
    unit: dict[str, Any], target_id: str, project: dict[str, Any]
) -> dict[str, Any]:
    """Bind exact target/source semantics, not publication status or cached approval state."""
    target, selected, missing = _context(unit, target_id, project)
    projection = {
        "domain": PAYLOAD_DOMAIN,
        "version": PAYLOAD_VERSION,
        "source": _source(unit),
        "target": _rendering(unit, target),
        "upstream": [_rendering(unit, value) for value in selected[1:]],
        "missing_upstream": missing,
        "applicable_style": _styles(project, selected),
    }
    return {"version": PAYLOAD_VERSION, "algorithm": "sha256", "value": _hash(projection)}


def _review_policy(project: dict[str, Any]) -> dict[str, Any]:
    policy = _object(project.get("review_policy"), "review_policy")
    result: dict[str, Any] = {}
    for key in ("canonical_required_approvals", "alternate_required_approvals"):
        value = policy.get(key)
        if type(value) is not int or value < 1:
            raise ValidationError(f"review_policy.{key} must be a positive integer")
        result[key] = value
    result["release_required_role"] = _identity(
        policy.get("release_required_role"), "release_required_role"
    )
    roles = _strings(policy.get("reviewer_roles"), "reviewer_roles")
    if not roles or len(roles) != len(set(roles)):
        raise ValidationError("reviewer_roles must be nonempty and unique")
    for role in roles:
        _identity(role, "reviewer role")
    result["reviewer_roles"] = sorted(roles)
    return result


def _source_references(unit: dict[str, Any], selected: list[dict[str, Any]]) -> dict[str, set[str]]:
    references: dict[str, set[str]] = {}

    def add(source_id: Any, component: str = "text") -> None:
        references.setdefault(_identity(source_id, "source_id"), set()).add(component)

    for rendering in selected:
        provenance = _object(rendering.get("provenance", {}), "provenance")
        for basis in (rendering.get("translation_basis"), provenance.get("translation_basis")):
            if basis is not None:
                basis = _object(basis, "translation_basis")
                for source_id in _strings(basis.get("source_ids", []), "basis.source_ids"):
                    add(source_id)
        for source_id in _strings(provenance.get("source_ids", []), "provenance.source_ids"):
            add(source_id)
        for image in _records(rendering, "preserved_source_images"):
            if "source_id" in image:
                add(image["source_id"])
        greek = provenance.get("greek_generation_source")
        if greek is not None:
            greek = _object(greek, "greek_generation_source")
            if "source_id" in greek:
                add(greek["source_id"])
    for token in _records(unit, "tokens"):
        enrichment = _object(token.get("enrichment_sources", {}), "enrichment_sources")
        for source_id in enrichment:
            add(source_id)
        if token.get("greek"):
            add("macula", "greek")
    return references


def _authority(component: dict[str, Any]) -> dict[str, Any]:
    result = _fields(component, ("status", "package_hashes"))
    if "status" in component:
        status = component["status"]
        if not isinstance(status, str) or status not in {"pending", "approved", "revoked"}:
            raise ValidationError("Source component status is invalid")
    if "package_hashes" in component:
        packages = _object(component["package_hashes"], "package_hashes")
        for package_id, package_hash in packages.items():
            _identity(package_id, "package_id")
            _identity(package_hash, "package_hash")
    capabilities = _object(component.get("capabilities", {}), "capabilities")
    for key in CAPABILITIES:
        if key in capabilities and type(capabilities[key]) is not bool:
            raise ValidationError("Source capability flags must be boolean")
    result["capabilities"] = _fields(capabilities, CAPABILITIES)
    result["capabilities_present"] = "capabilities" in component
    result["approvals_present"] = "approvals" in component
    # Last decision per reviewer is order-sensitive in current source authority.
    result["approvals"] = [
        _fields(decision, AUTHORITY_DECISION_FIELDS)
        for decision in _records(component, "approvals")
    ]
    return result


def review_policy_revision(
    unit: dict[str, Any],
    target_id: str,
    project: dict[str, Any],
    source_registry: dict[str, Any] | None = None,
) -> str:
    """Fingerprint applicable policy/source evidence; never infer authorization from it."""
    _, selected, _ = _context(unit, target_id, project)
    policy = _review_policy(project)
    references = _source_references(unit, selected)
    registry = {} if source_registry is None else _object(source_registry, "source_registry")
    manifests = _records(project, "source_manifests")
    registry_sources = _records(registry, "sources")
    allowed = (
        _strings(project["allowed_sources"], "allowed_sources")
        if "allowed_sources" in project
        else None
    )
    sources = []
    for source_id, components in sorted(references.items()):
        matching = [item for item in manifests if item.get("source_id") == source_id]
        entries = [item for item in registry_sources if item.get("source_id") == source_id]
        if len(matching) > 1 or len(entries) > 1:
            raise ValidationError("Duplicate applicable source identity")
        entry = entries[0] if entries else None
        source: dict[str, Any] = {
            "source_id": source_id,
            "allowed_sources_present": allowed is not None,
            "listed_in_allowed_sources": source_id in allowed if allowed is not None else None,
            "manifest": {"present": bool(matching)},
            "registry_source_present": entry is not None,
            "components": [],
        }
        if matching:
            _text_fields(
                matching[0],
                tuple(
                    name
                    for name in MANIFEST_FIELDS
                    if name
                    not in {
                        "version_pinned",
                        "allowed_for_display",
                        "allowed_for_generation",
                        "allowed_for_export",
                    }
                ),
                nullable=False,
            )
            for key in (
                "version_pinned",
                "allowed_for_display",
                "allowed_for_generation",
                "allowed_for_export",
            ):
                if key in matching[0] and type(matching[0][key]) is not bool:
                    raise ValidationError(f"Source manifest {key} must be boolean")
            source["manifest"]["value"] = _fields(matching[0], MANIFEST_FIELDS)
        source["components_present"] = entry is not None and "components" in entry
        authority = (
            _object(entry["components"], "source components")
            if entry is not None and "components" in entry
            else {}
        )
        for name in sorted(components):
            component: dict[str, Any] = {"component": name, "present": name in authority}
            if name in authority:
                component["authority"] = _authority(_object(authority[name], "source component"))
            source["components"].append(component)
        sources.append(source)
    return _hash(
        {
            "domain": POLICY_DOMAIN,
            "version": PAYLOAD_VERSION,
            "review_policy": policy,
            "registry_present": source_registry is not None,
            "registry_sources_present": "sources" in registry,
            "manifests_present": "source_manifests" in project,
            "sources": sources,
        }
    )
