from __future__ import annotations

import json
import re
from typing import Any

from app.core.errors import GenerationError, NotFoundError, ValidationError
from app.llm.adapters import build_adapter
from app.llm.base import GenerationRequest
from app.services import registry_service

STAGES = {"phrase", "concept", "lyric"}
DEFAULT_STYLE_PROFILE = "study_literal"
BASIS_FILTERS = {"hebrew-derived", "septuagint-derived"}
DELIVERY_PROFILES = {
    "source_grounded_phrase",
    "source_clear_concept",
    "emotional_concept",
    "raw_modern",
    "4_4_direct",
    "6_8_lament",
    "hook_refrain",
}


def _style_profile(style_profile: str | None) -> dict[str, Any]:
    project = registry_service.load_project()
    style_profile_id = style_profile or DEFAULT_STYLE_PROFILE
    for item in project.get("style_profiles", []):
        if item["style_profile_id"] == style_profile_id:
            return item
    raise NotFoundError(f"Unknown style profile: {style_profile_id}")


def _model_profile(model_profile: str | None) -> dict[str, Any]:
    project = registry_service.load_project()
    model_profile_id = model_profile or project.get("default_composer_model_profile") or project["default_model_profile"]
    for item in project.get("local_model_profiles", []):
        if item["model_profile_id"] == model_profile_id:
            return item
    raise NotFoundError(f"Unknown model profile: {model_profile_id}")


def _validate_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        chunk_id = str(chunk.get("chunk_id") or "").strip()
        text = str(chunk.get("text") or "").strip()
        if not chunk_id or not text:
            raise ValidationError(f"Chunk {index + 1} is missing chunk_id or text")
        normalized.append(
            {
                "chunk_id": chunk_id,
                "start": int(chunk.get("start", 0)),
                "end": int(chunk.get("end", chunk.get("start", 0))),
                "text": text,
                "source_text": str(chunk.get("source_text") or "").strip(),
                "confidence": float(chunk.get("confidence", 0.0)),
                "confidence_reasons": [str(item) for item in chunk.get("confidence_reasons", [])],
            }
        )
    return normalized


def _contract(candidate_count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["unit_id", "stage", "chunks"],
        "additionalProperties": False,
        "properties": {
            "unit_id": {"type": "string"},
            "stage": {"type": "string", "enum": sorted(STAGES)},
            "chunks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["chunk_id", "candidates"],
                    "additionalProperties": False,
                    "properties": {
                        "chunk_id": {"type": "string"},
                        "candidates": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": candidate_count,
                            "items": {
                                "type": "object",
                                "required": [
                                    "text",
                                    "rationale",
                                    "alignment_hints",
                                    "drift_flags",
                                    "metrics",
                                    "variation_basis",
                                    "preserved_source_images",
                                    "differentiator",
                                    "grounding_confidence",
                                    "translation_basis",
                                    "delivery_profile",
                                    "source_anchor",
                                ],
                                "additionalProperties": False,
                                "properties": {
                                    "text": {"type": "string"},
                                    "rationale": {"type": "string"},
                                    "alignment_hints": {"type": "array", "items": {"type": "string"}},
                                    "drift_flags": {"type": "array", "items": {"type": "string"}},
                                    "metrics": {"type": "object"},
                                    "variation_basis": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                                    "preserved_source_images": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["label"],
                                            "additionalProperties": False,
                                            "properties": {
                                                "label": {"type": "string"},
                                                "source_id": {"type": "string"},
                                                "token_ids": {"type": "array", "items": {"type": "string"}},
                                                "note": {"type": "string"},
                                            },
                                        },
                                    },
                                    "differentiator": {"type": "string"},
                                    "grounding_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                    "translation_basis": {
                                        "type": "object",
                                        "required": ["basis_type", "source_ids", "source_language", "source_version", "basis_note"],
                                        "additionalProperties": False,
                                        "properties": {
                                            "basis_type": {
                                                "type": "string",
                                                "enum": ["hebrew_to_english", "septuagint_greek_to_english"],
                                            },
                                            "source_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                                            "source_language": {"type": "string"},
                                            "source_version": {"type": "string"},
                                            "basis_note": {"type": "string"},
                                        },
                                    },
                                    "delivery_profile": {"type": "string", "enum": sorted(DELIVERY_PROFILES)},
                                    "source_anchor": {
                                        "type": "object",
                                        "required": ["anchor_text", "source_language", "source_text", "basis_note"],
                                        "additionalProperties": False,
                                        "properties": {
                                            "anchor_text": {"type": "string"},
                                            "source_language": {"type": "string"},
                                            "source_text": {"type": "string"},
                                            "token_ids": {"type": "array", "items": {"type": "string"}},
                                            "basis_note": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }


def _minimal_compiler_features(features: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "conjunction_role",
        "preposition_role",
        "construct_state",
        "suffix_pronoun",
        "divine_name",
        "temporal_pair_candidate",
        "discourse_marker",
        "english_parts",
        "gloss_fragments",
        "raw_classes",
        "raw_pos",
    }
    return {key: value for key, value in features.items() if key in allowed_keys and value not in (None, "", [], {})}


def _token_prompt_payload(token: dict[str, Any]) -> dict[str, Any]:
    return {
        "token_id": token.get("token_id"),
        "surface": token.get("surface"),
        "transliteration": token.get("transliteration"),
        "greek": token.get("greek"),
        "greek_strong": token.get("greek_strong"),
        "lemma": token.get("lemma"),
        "strong": token.get("strong"),
        "display_gloss": token.get("display_gloss"),
        "gloss_parts": token.get("gloss_parts", []),
        "morph_readable": token.get("morph_readable"),
        "part_of_speech": token.get("part_of_speech"),
        "syntax_role": token.get("syntax_role"),
        "semantic_role": token.get("semantic_role"),
        "compiler_features": _minimal_compiler_features(dict(token.get("compiler_features") or {})),
    }


def _chunk_prompt_payload(unit: dict[str, Any], chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unit_tokens = list(unit.get("tokens") or [])
    lxx_witness = next((item for item in unit.get("witnesses", []) if item.get("source_id") == "lxx"), None)
    payload: list[dict[str, Any]] = []
    for chunk in chunks:
        start = int(chunk["start"])
        end = int(chunk["end"])
        chunk_tokens = unit_tokens[start : end + 1]
        payload.append(
            {
                "chunk_id": chunk["chunk_id"],
                "token_span": [start, end],
                "hebrew_text": " ".join(str(token.get("surface") or "").strip() for token in chunk_tokens if str(token.get("surface") or "").strip()),
                "transliteration_text": " ".join(
                    str(token.get("transliteration") or "").strip() for token in chunk_tokens if str(token.get("transliteration") or "").strip()
                ),
                "septuagint_greek_text": " ".join(str(token.get("greek") or "").strip() for token in chunk_tokens if str(token.get("greek") or "").strip()),
                "septuagint_greek_witness": {
                    "versionTitle": lxx_witness.get("versionTitle"),
                    "source_version": lxx_witness.get("source_version"),
                    "text": lxx_witness.get("text"),
                }
                if lxx_witness
                else None,
                "lexical_tokens": [_token_prompt_payload(token) for token in chunk_tokens],
                "source_anchor_candidates": [
                    {
                        "token_id": token.get("token_id"),
                        "surface": token.get("surface"),
                        "transliteration": token.get("transliteration"),
                        "greek": token.get("greek"),
                        "display_gloss": token.get("display_gloss"),
                    }
                    for token in chunk_tokens
                ],
                "deterministic_seed_english": chunk["text"],
                "seed_scope_note": "Use only as a scope check. Do not rewrite from this English.",
                "confidence": chunk["confidence"],
                "confidence_reasons": chunk["confidence_reasons"],
            }
        )
    return payload


def _stage_guidance(stage: str, style: dict[str, Any]) -> str:
    literalness = float(style.get("literalness", 1.0))
    lyric_freedom = float(style.get("lyric_freedom", 0.0))

    base = {
        "phrase": (
            "Return faithful English phrase alternatives for each chunk. "
            "Keep the chunk anchored tightly to the Hebrew span, but let the English read naturally."
        ),
        "concept": (
            "Return concept-forward alternatives for each chunk. "
            "You may compress idiom and recast wording for clarity and force, while preserving the Hebrew scene, roles, movement, and pressure."
        ),
        "lyric": (
            "Return delivery-first, cadence-aware alternatives for each chunk. "
            "You may smooth, compress, and reorder within the chunk for spoken rhythm, but remain faithful to the Hebrew meaning, scene, and imagery."
        ),
    }[stage]
    flexibility = []
    if lyric_freedom >= 0.75:
        flexibility.append("Take moderate creative liberties in delivery, cadence, and idiom.")
    elif lyric_freedom >= 0.45:
        flexibility.append("Allow measured creative liberties in idiom and delivery, but stay semantically close.")
    else:
        flexibility.append("Stay close to the Hebrew logic and imagery; prefer clarity over flourish.")
    if literalness <= 0.7:
        flexibility.append("Avoid wooden mirror-English; choose living English that still preserves the underlying sense.")
    else:
        flexibility.append("Preserve the Hebrew order and relationships unless English requires adjustment.")
    if stage in {"concept", "lyric"}:
        flexibility.append("Candidates should be materially distinct from each other in delivery, not just tiny wording swaps.")
        flexibility.append(
            "For psalm headings or musical superscriptions, smooth stacked directives into natural English delivery. "
            "Do not repeat a wooden chain like 'to the choir director' followed by 'to the flutes' when the source span means a director cue with flute accompaniment."
        )
    if stage == "lyric":
        flexibility.append(
            "You may use newline characters inside candidate text to create sparse, breath-based lineation. "
            "Prefer short lines, strong pivots, and emotionally legible phrasing over prose-like full sentences."
        )
    return " ".join([base, *flexibility])


def _style_axis_guidance(style: dict[str, Any]) -> str:
    source_anchor_mode = str(style.get("source_anchor_mode") or "scene_preserving")
    metaphor_mode = str(style.get("metaphor_mode") or "minimal")
    imagery_preservation = float(style.get("imagery_preservation", 0.8))
    idiom_modernity = float(style.get("idiom_modernity", 0.5))
    emotional_directness = float(style.get("emotional_directness", 0.5))
    faith_posture = str(style.get("faith_posture") or "observational")
    divine_name_rendering = str(style.get("divine_name_rendering") or "preserve_distinction")

    guidance: list[str] = []
    if source_anchor_mode == "token_literal":
        guidance.append("Stay close to the token sequence and explicit lexical content.")
    elif source_anchor_mode == "hebrew_imagery":
        guidance.append("Preserve the Hebrew image-world first; modernize diction before replacing images with abstraction.")
    else:
        guidance.append("Preserve the scene and clause movement even when English order shifts.")

    if metaphor_mode == "minimal":
        guidance.append("Prefer direct restatement over added symbolism.")
    elif metaphor_mode == "source_metaphor_first":
        guidance.append("Keep source metaphors intact whenever singable English is possible.")
    else:
        guidance.append("You may recast into contemporary symbolic language, but the Hebrew scene must remain clearly legible.")

    if imagery_preservation >= 0.85:
        guidance.append("Do not flatten concrete source images into generic emotion words.")
    elif imagery_preservation >= 0.65:
        guidance.append("Keep at least one concrete source image active in each candidate when the Hebrew supplies one.")
    else:
        guidance.append("You may compress some imagery, but preserve the mechanism of the scene.")

    if idiom_modernity >= 0.75:
        guidance.append(
            "Use contemporary idiom and avoid inherited Bible phrasing unless the Hebrew force requires it. "
            "Avoid defaulting to wording like 'nor', 'walketh', 'sitteth', or similar pseudo-biblical connective language."
        )
    elif idiom_modernity >= 0.45:
        guidance.append(
            "Prefer living English over archaic diction. "
            "Do not use inherited Bible filler like 'nor' when contemporary English can carry the same force."
        )
    else:
        guidance.append("Formal diction is acceptable if it remains natural.")

    if emotional_directness >= 0.75:
        guidance.append("Favor exposed first-person pressure and clean emotional readability.")
    elif emotional_directness >= 0.45:
        guidance.append("Keep the emotional force explicit, not academic.")
    else:
        guidance.append("Restraint is acceptable, but do not mute the emotional stakes.")

    if faith_posture == "contested":
        guidance.append("Permit strained, uncertain, or contested address to God; do not strengthen the speaker into confident confession.")
    elif faith_posture == "observational":
        guidance.append("Do not intensify devotional certainty beyond what the Hebrew requires.")
    else:
        guidance.append("Confessional language is allowed when grounded in the Hebrew.")

    if divine_name_rendering == "contemporary_title":
        guidance.append(
            "When the source uses the divine name, prefer contemporary title forms like 'Lord' when they read more naturally, "
            "but keep the distinction visible instead of flattening it into a generic deity term."
        )
    elif divine_name_rendering == "flexible_address":
        guidance.append(
            "When the source uses the divine name in direct address, you may let one candidate use 'God' or 'my God' for emotional immediacy, "
            "but keep at least one candidate visibly marked as the divine name. Do not blur who is being addressed."
        )
    else:
        guidance.append(
            "When the source uses the divine name, keep that distinction visible in English. "
            "Prefer Lord, LORD, or Yahweh over flattening it into a generic 'God'."
        )

    return " ".join(guidance)


def _candidate_family_guidance(stage: str, candidate_count: int, style: dict[str, Any]) -> str:
    if candidate_count < 2:
        return ""
    guidance: list[str] = []
    if str(style.get("divine_name_rendering") or "preserve_distinction") == "flexible_address":
        guidance.append(
            "If the chunk directly addresses the divine name, diversify the address across the candidate set: "
            "let at least one candidate keep the marked divine-name distinction and let another use 'God' or 'my God' if that yields cleaner contemporary English."
        )
    if stage == "phrase":
        guidance.append(
            "When multiple phrase candidates are justified, vary only by defensible source-grounded ambiguity, "
            "idiom fit, punctuation, or English order shift. Do not manufacture stylistic spread."
        )
    elif stage == "concept":
        guidance.append(
            "When multiple concept candidates are justified, let them differ by emphasis, compression, or idiomatic framing, "
            "but keep the Hebrew scene and agency intact. "
            "Use delivery_profile source_clear_concept for the clearest grounded reading, emotional_concept when the English is reader-facing, "
            "and raw_modern only when the modern idiom is still auditable against the source anchor."
        )
    else:
        guidance.append(
            "When producing multiple lyric candidates, diversify them intentionally: "
            "one closer to the source imagery, one more modern-symbolic, and one more compressed or performative. "
            "At least one may use sparse line breaks if that helps the pressure land cleanly. "
            "Where a chunk can plausibly carry meter, include a square 4/4-feeling delivery and a lilting 6/8-feeling delivery across the candidate set, set delivery_profile to 4_4_direct or 6_8_lament, and name that in the differentiator. "
            "Use hook_refrain only when repetition is suggested by the source movement or by a deliberate delivery choice flagged as hook_repetition_added. "
            "Do not emit near-duplicates."
        )
    return " ".join(guidance)


def _drift_watch_guidance(stage: str) -> str:
    if stage not in {"concept", "lyric"}:
        return ""
    return (
        "Use drift_flags when a candidate adds agency, strengthens theology, erases a source image, "
        "flattens metaphor into explanation, shifts the speaker's posture, leaks performance directions into translation text, "
        "softens a source image, invents a modern epithet, heightens speaker pressure beyond the source, adds hook repetition, "
        "or infers musical form. Prefer flag names such as performance_direction_leak, source_image_softened, modern_epithet_added, "
        "speaker_pressure_heightened, hook_repetition_added, and musical_form_inferred."
    )


def _request_temperature(profile: dict[str, Any], style: dict[str, Any], stage: str) -> float:
    base_temperature = float(profile.get("temperature", 0.2))
    lyric_freedom = float(style.get("lyric_freedom", 0.0))
    literalness = float(style.get("literalness", 1.0))
    idiom_modernity = float(style.get("idiom_modernity", 0.5))
    metaphor_mode = str(style.get("metaphor_mode") or "minimal")
    creative_bump = max(0.0, lyric_freedom - 0.25) * 0.45 + max(0.0, 0.85 - literalness) * 0.2
    creative_bump += max(0.0, idiom_modernity - 0.6) * 0.1
    if metaphor_mode == "symbolic_equivalent":
        creative_bump += 0.05
    if stage == "concept":
        creative_bump += 0.03
    if stage == "lyric":
        creative_bump += 0.08
    return round(min(0.75, max(base_temperature, base_temperature + creative_bump)), 2)


def _request_max_tokens(profile: dict[str, Any], style: dict[str, Any], candidate_count: int) -> int:
    base_max_tokens = int(profile.get("max_tokens", 768))
    lyric_freedom = float(style.get("lyric_freedom", 0.0))
    creative_bonus = 128 if lyric_freedom >= 0.75 else 64 if lyric_freedom >= 0.45 else 0
    return max(base_max_tokens, min(1408, base_max_tokens + creative_bonus + max(0, candidate_count - 3) * 64))


def _prompt(unit: dict[str, Any], stage: str, chunks: list[dict[str, Any]], candidate_count: int, style: dict[str, Any]) -> str:
    return (
        "You are assisting a grounded translation ideation workbench.\n"
        "Return strict JSON only. Do not include markdown.\n"
        "Translate each chunk directly from the Hebrew token data provided below.\n"
        "Use any explicit Septuagint Greek witness data only when present and only as a clearly labeled alternate basis.\n"
        "Hebrew is the canonical basis. If Septuagint Greek witness data is present, you may include a Greek-derived alternate when it adds real grounded value.\n"
        "Do not base the candidates on existing English translations.\n"
        "Do not silently blend Hebrew and Greek logic inside one candidate. Every candidate must declare its translation_basis.\n"
        "The deterministic seed English is present only as a scope check for the chunk span.\n"
        "Stay faithful to speaker/addressee, negation, imagery, clause relationships, and the configured divine-name handling.\n"
        "Do not add doctrine, explanation, or details not grounded in the source chunk.\n"
        "Avoid near-duplicate candidates that differ only by articles or tiny wording swaps.\n"
        "Musical/performance directions from user references are delivery examples, not source text; do not translate them as if they were Hebrew or Greek.\n"
        "Every candidate must set delivery_profile and source_anchor. The source_anchor must name the Hebrew or Greek phrase/token pressure that keeps the rendering auditable.\n"
        "For concept and lyric stages, optimize for speakable or singable English without breaking source anchor, speaker/addressee, negation, agency, or imagery.\n"
        f"{_stage_guidance(stage, style)}\n"
        f"{_style_axis_guidance(style)}\n"
        f"{_candidate_family_guidance(stage, candidate_count, style)}\n"
        f"{_drift_watch_guidance(stage)}\n"
        f"Produce up to {candidate_count} candidates per chunk across both source bases combined. Fewer is acceptable only when the chunk is genuinely constrained.\n\n"
        f"Style target:\n{registry_service.deterministic_json(style)}\n"
        f"Unit context:\n{registry_service.deterministic_json({'unit_id': unit['unit_id'], 'ref': unit['ref'], 'source_hebrew': unit['source_hebrew'], 'source_transliteration': unit.get('source_transliteration'), 'divine_name_policy': registry_service.load_project().get('divine_name_policy'), 'token_count': len(unit.get('tokens', []))})}\n"
        f"Chunk input:\n{registry_service.deterministic_json({'unit_id': unit['unit_id'], 'stage': stage, 'chunks': _chunk_prompt_payload(unit, chunks)})}\n"
        f"Output contract:\n{json.dumps(_contract(candidate_count), indent=2, sort_keys=True)}"
    )


def _candidate_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def _normalize_candidate_text(text: str, preserve_line_breaks: bool = False) -> str:
    raw = str(text).strip()
    if not preserve_line_breaks:
        return re.sub(r"\s+", " ", raw)
    lines = [re.sub(r"\s+", " ", line.strip()) for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line))


def _candidate_words(text: str) -> set[str]:
    return {word for word in _candidate_key(text).split() if word}


def _too_similar(left: str, right: str) -> bool:
    left_words = _candidate_words(left)
    right_words = _candidate_words(right)
    if not left_words or not right_words:
        return False
    overlap = len(left_words & right_words) / max(len(left_words | right_words), 1)
    return overlap >= 0.88 and abs(len(left_words) - len(right_words)) <= 1


def _distinctness_score(text: str, prior_texts: list[str]) -> float:
    if not prior_texts:
        return 1.0
    overlaps = []
    current = _candidate_words(text)
    for prior in prior_texts:
        prior_words = _candidate_words(prior)
        if not current or not prior_words:
            continue
        overlaps.append(len(current & prior_words) / max(len(current | prior_words), 1))
    if not overlaps:
        return 1.0
    return round(max(0.0, 1.0 - max(overlaps)), 2)


def _default_translation_basis() -> dict[str, Any]:
    project = registry_service.load_project()
    manifest = next((item for item in project.get("source_manifests", []) if item["source_id"] == "uxlc"), None)
    return {
        "basis_type": "hebrew_to_english",
        "source_ids": ["uxlc", "oshb", "macula"],
        "source_language": "he",
        "source_version": manifest["version"] if manifest else "unknown",
        "basis_note": "Canonical Hebrew-first translation basis.",
    }


def _normalize_translation_basis(payload: dict[str, Any] | None) -> dict[str, Any]:
    basis = dict(payload or {})
    default = _default_translation_basis()
    basis_type = str(basis.get("basis_type") or default["basis_type"]).strip()
    if basis_type == "septuagint_greek_to_english":
        manifest = next((item for item in registry_service.load_project().get("source_manifests", []) if item["source_id"] == "lxx"), None)
        source_ids = basis.get("source_ids") or ["lxx", "macula"]
        source_language = str(basis.get("source_language") or "grc").strip()
        source_version = str(basis.get("source_version") or (manifest["version"] if manifest else "unknown")).strip()
        basis_note = str(basis.get("basis_note") or "Translate directly from the Septuagint Greek witness.").strip()
    else:
        source_ids = basis.get("source_ids") or default["source_ids"]
        source_language = str(basis.get("source_language") or default["source_language"]).strip()
        source_version = str(basis.get("source_version") or default["source_version"]).strip()
        basis_note = str(basis.get("basis_note") or default["basis_note"]).strip()
    return {
        "basis_type": basis_type,
        "source_ids": [str(source_id).strip() for source_id in source_ids if str(source_id).strip()],
        "source_language": source_language,
        "source_version": source_version,
        "basis_note": basis_note,
    }


def _normalize_delivery_profile(stage: str, value: Any, differentiator: str, variation_basis: list[str]) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
    if normalized in DELIVERY_PROFILES:
        return normalized

    hint = " ".join([differentiator, *variation_basis]).lower()
    if stage == "phrase":
        return "source_grounded_phrase"
    if stage == "concept":
        if any(term in hint for term in ("emotional", "reader", "lament", "direct address")):
            return "emotional_concept"
        if any(term in hint for term in ("raw", "modern", "symbolic")):
            return "raw_modern"
        return "source_clear_concept"
    if "6/8" in hint or "6_8" in hint or "lilt" in hint or "lament" in hint:
        return "6_8_lament"
    if "hook" in hint or "refrain" in hint or "repeat" in hint:
        return "hook_refrain"
    if "raw" in hint or "modern" in hint or "symbolic" in hint:
        return "raw_modern"
    return "4_4_direct"


def _normalize_source_anchor(payload: dict[str, Any] | None, chunk: dict[str, Any], translation_basis: dict[str, Any]) -> dict[str, Any]:
    anchor = dict(payload or {})
    basis_language = str(translation_basis.get("source_language") or "he").strip()
    source_text = str(anchor.get("source_text") or chunk.get("source_text") or chunk.get("text") or "").strip()
    anchor_text = str(anchor.get("anchor_text") or chunk.get("text") or source_text).strip()
    basis_type = translation_basis.get("basis_type")
    default_note = (
        "Septuagint Greek source anchor for this alternate candidate."
        if basis_type == "septuagint_greek_to_english"
        else "Hebrew source anchor for this candidate."
    )
    token_ids = [str(token_id).strip() for token_id in list(anchor.get("token_ids") or []) if str(token_id).strip()]
    normalized = {
        "anchor_text": anchor_text,
        "source_language": str(anchor.get("source_language") or basis_language).strip(),
        "source_text": source_text,
        "basis_note": str(anchor.get("basis_note") or default_note).strip(),
    }
    if token_ids:
        normalized["token_ids"] = token_ids
    return normalized


def _normalize_variation_basis(stage: str, values: list[str] | None) -> list[str]:
    normalized = [str(item).strip() for item in (values or []) if str(item).strip()]
    if normalized:
        return normalized
    if stage == "phrase":
        return ["source_grounded_rendering"]
    if stage == "concept":
        return ["emphasis_shift"]
    return ["cadence_or_emphasis_shift"]


def _normalize_preserved_source_images(images: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for image in images or []:
        label = str(image.get("label") or "").strip()
        if not label:
            continue
        item = {"label": label}
        source_id = str(image.get("source_id") or "").strip()
        if source_id:
            item["source_id"] = source_id
        token_ids = [str(token_id).strip() for token_id in list(image.get("token_ids") or []) if str(token_id).strip()]
        if token_ids:
            item["token_ids"] = token_ids
        note = str(image.get("note") or "").strip()
        if note:
            item["note"] = note
        normalized.append(item)
    return normalized


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    drift_flags = [str(flag).strip() for flag in list(candidate.get("drift_flags") or []) if str(flag).strip()]
    high_risk = any("high" in flag or "basis_blur" in flag or "speaker_posture_shift" in flag for flag in drift_flags)
    medium_risk = any("medium" in flag or "devotional_strengthening" in flag or "source_image_erasure" in flag for flag in drift_flags)
    basis_rank = 0 if candidate["translation_basis"]["basis_type"] == "hebrew_to_english" else 1
    grounding = float(candidate.get("grounding_confidence", 0.0))
    distinctness = float(candidate.get("metrics", {}).get("distinctness_score", 0.0))
    return (high_risk, medium_risk, -grounding, basis_rank, -distinctness, candidate["text"].casefold())


def _normalize_response(
    payload: dict[str, Any],
    unit_id: str,
    stage: str,
    candidate_count: int,
    chunks: list[dict[str, Any]],
    basis_filter: str | None = None,
) -> dict[str, Any]:
    if payload.get("unit_id") != unit_id or payload.get("stage") != stage:
        raise ValidationError("Composer suggestion response returned the wrong unit or stage")
    if basis_filter and basis_filter not in BASIS_FILTERS:
        raise ValidationError(f"Unsupported basis_filter: {basis_filter}")

    seed_keys = {chunk["chunk_id"]: _candidate_key(chunk["text"]) for chunk in chunks}
    chunk_lookup = {chunk["chunk_id"]: chunk for chunk in chunks}
    normalized_chunks: list[dict[str, Any]] = []
    for chunk in payload.get("chunks", []):
        chunk_id = str(chunk.get("chunk_id") or "").strip()
        if not chunk_id:
            continue
        seen: set[str] = set()
        candidates_for_chunk: list[dict[str, Any]] = []
        seed_match_candidate: dict[str, Any] | None = None
        for candidate in list(chunk.get("candidates") or []):
            text = _normalize_candidate_text(candidate.get("text"), preserve_line_breaks=stage == "lyric")
            if not text:
                continue
            key = _candidate_key(text)
            if not key or key in seen:
                continue
            variation_basis = _normalize_variation_basis(stage, candidate.get("variation_basis"))
            differentiator = _normalize_candidate_text(candidate.get("differentiator") or "grounded alternate")
            translation_basis = _normalize_translation_basis(candidate.get("translation_basis"))
            request_chunk = chunk_lookup.get(chunk_id) or {"text": text, "source_text": ""}
            item = {
                "text": text,
                "rationale": _normalize_candidate_text(candidate.get("rationale") or "Generated from Hebrew chunk"),
                "alignment_hints": [str(hint).strip() for hint in list(candidate.get("alignment_hints") or []) if str(hint).strip()],
                "drift_flags": [str(flag).strip() for flag in list(candidate.get("drift_flags") or []) if str(flag).strip()],
                "metrics": dict(candidate.get("metrics") or {}),
                "variation_basis": variation_basis,
                "preserved_source_images": _normalize_preserved_source_images(candidate.get("preserved_source_images")),
                "differentiator": differentiator,
                "grounding_confidence": round(float(candidate.get("grounding_confidence", candidate.get("metrics", {}).get("grounding_score", 0.72))), 2),
                "translation_basis": translation_basis,
                "delivery_profile": _normalize_delivery_profile(stage, candidate.get("delivery_profile"), differentiator, variation_basis),
                "source_anchor": _normalize_source_anchor(candidate.get("source_anchor"), request_chunk, translation_basis),
            }
            if basis_filter == "hebrew-derived" and item["translation_basis"]["basis_type"] != "hebrew_to_english":
                continue
            if basis_filter == "septuagint-derived" and item["translation_basis"]["basis_type"] != "septuagint_greek_to_english":
                continue
            if key == seed_keys.get(chunk_id):
                seed_match_candidate = item
                continue
            seen.add(key)
            candidates_for_chunk.append(item)
        ranked = sorted(candidates_for_chunk, key=_candidate_sort_key)
        kept_candidates: list[dict[str, Any]] = []
        prior_texts: list[str] = []
        for item in ranked:
            if any(_too_similar(item["text"], prior) for prior in prior_texts):
                continue
            metrics = dict(item.get("metrics") or {})
            metrics.setdefault("grounding_score", item["grounding_confidence"])
            metrics["distinctness_score"] = _distinctness_score(item["text"], prior_texts)
            item["metrics"] = metrics
            kept_candidates.append(item)
            prior_texts.append(item["text"])
            if len(kept_candidates) >= candidate_count:
                break
        if not kept_candidates and seed_match_candidate is not None:
            kept_candidates.append(seed_match_candidate)
        if kept_candidates:
            normalized_chunks.append({"chunk_id": chunk_id, "candidates": kept_candidates})

    return {"unit_id": unit_id, "stage": stage, "available": bool(normalized_chunks), "chunks": normalized_chunks}


def suggest_for_unit(
    unit_id: str,
    stage: str,
    chunks: list[dict[str, Any]],
    candidate_count: int = 3,
    model_profile: str | None = None,
    style_profile: str | None = None,
    basis_filter: str | None = None,
) -> dict[str, Any]:
    if stage not in STAGES:
        raise ValidationError(f"Unsupported composer suggestion stage: {stage}")
    if candidate_count < 1 or candidate_count > 5:
        raise ValidationError("candidate_count must be between 1 and 5")
    normalized_chunks = _validate_chunks(chunks)
    if not normalized_chunks:
        return {"unit_id": unit_id, "stage": stage, "available": False, "chunks": []}

    unit = registry_service.load_unit(unit_id)
    profile = _model_profile(model_profile)
    style = _style_profile(style_profile)
    adapter = build_adapter(profile)
    try:
        response = adapter.generate_json(
            GenerationRequest(
                prompt=_prompt(unit, stage, normalized_chunks, candidate_count, style),
                contract=_contract(candidate_count),
                model=str(profile["model"]),
                seed=42,
                temperature=_request_temperature(profile, style, stage),
                max_tokens=_request_max_tokens(profile, style, candidate_count),
                system_prompt="Return valid JSON matching the requested contract exactly.",
                candidate_count=1,
                timeout_seconds=int(profile.get("timeout_seconds", 30)),
                metadata={"unit_id": unit_id, "stage": stage, "style_profile": style["style_profile_id"]},
            )
        )
    except GenerationError:
        return {"unit_id": unit_id, "stage": stage, "available": False, "chunks": []}

    return _normalize_response(response.payload, unit_id, stage, candidate_count, normalized_chunks, basis_filter=basis_filter)
