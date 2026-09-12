from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from app.core.errors import ValidationError
from app.services import registry_service

LAYERS = {
    "gloss",
    "literal",
    "phrase",
    "concept",
    "lyric",
    "metered_lyric",
    "parallelism_lyric",
}
TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z'-]*")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "he",
    "her",
    "him",
    "his",
    "i",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "she",
    "that",
    "the",
    "their",
    "them",
    "they",
    "to",
    "we",
    "with",
    "you",
    "your",
}
CREATIVE_ALIGNMENT_TYPES = {
    "idiom",
    "conceptual",
    "editorial_expansion",
    "omission_accounted_for",
    "uncertain",
}
ALIGNMENT_WEIGHTS = {
    "direct": 1.0,
    "grouped": 0.9,
    "idiom": 0.72,
    "conceptual": 0.56,
    "editorial_expansion": 0.5,
    "omission_accounted_for": 0.22,
    "uncertain": 0.4,
}
IMAGE_ROLES = {"animal", "caregiver", "natural_phenomenon", "object", "place"}
ANCHOR_NOISE = {"dm"}
ANCHOR_VARIANTS = {
    "choirmaster": ("chief musician", "music director", "choir director"),
    "director": ("chief musician", "music director", "choir director"),
}
RENDERING_STATUS_PRIORITY = {
    "canonical": 0,
    "accepted_as_alternate": 1,
    "under_review": 2,
    "proposed": 3,
    "draft": 4,
    "deprecated": 5,
    "rejected": 6,
}
TRANSLATION_SOURCES = {"saved", "witness"}
SELECTABLE_RENDERING_STATUSES = {
    "preferred",
    "canonical",
    "accepted_as_alternate",
    "under_review",
    "proposed",
    "draft",
}


def _words(value: str | None) -> list[str]:
    return [word.casefold() for word in TOKEN_PATTERN.findall(value or "")]


def _content_words(value: str | None) -> list[str]:
    return [
        word
        for word in _words(value)
        if word not in STOP_WORDS and word not in ANCHOR_NOISE and len(word) > 1
    ]


def _clean_anchor(value: str | None) -> str:
    return " ".join(_content_words(value))


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _rendering_for_layer(
    unit: dict[str, Any], layer: str, rendering_status: str
) -> dict[str, Any] | None:
    candidates = [
        rendering
        for rendering in unit.get("renderings", [])
        if rendering.get("layer") == layer and rendering.get("text", "").strip()
    ]
    if rendering_status != "preferred":
        candidates = [
            rendering for rendering in candidates if rendering.get("status") == rendering_status
        ]
    return min(
        candidates,
        key=lambda item: RENDERING_STATUS_PRIORITY.get(item.get("status", ""), 99),
        default=None,
    )


def _witness_rendering(
    unit: dict[str, Any], layer: str, witness_source_id: str
) -> dict[str, Any] | None:
    for witness in unit.get("witnesses", []):
        if (
            witness.get("source_id") != witness_source_id
            or not str(witness.get("text") or "").strip()
        ):
            continue
        return {
            "rendering_id": f"witness.{witness_source_id}.{unit['unit_id']}",
            "status": "witness",
            "layer": layer,
            "text": witness["text"],
            "target_spans": [],
            "drift_flags": [],
            "rationale": "Read-only witness comparison; not a project rendering.",
            "_source_kind": "witness",
            "_source_label": witness.get("versionTitle") or witness_source_id,
            "_witness": witness,
        }
    return None


def _token_anchors(token: dict[str, Any]) -> list[str]:
    values = [
        _clean_anchor(str(token.get(field) or ""))
        for field in ("display_gloss", "word_sense", "referent")
    ]
    values.extend(_clean_anchor(str(part)) for part in token.get("gloss_parts", []))
    return [anchor for anchor in _unique(values) if anchor and anchor not in STOP_WORDS]


def _anchor_matches(anchors: list[str], target_words: set[str]) -> list[str]:
    matches = []
    for anchor in anchors:
        for variant in (anchor, *ANCHOR_VARIANTS.get(anchor, ())):
            anchor_words = variant.split()
            if anchor_words and all(word in target_words for word in anchor_words):
                matches.append(anchor if variant == anchor else f"{anchor} → {variant}")
                break
    return matches


def _alignment_lookup(
    unit: dict[str, Any], rendering: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    span_by_id = {span["span_id"]: span for span in rendering.get("target_spans", [])}
    lookup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for alignment in unit.get("alignments", []):
        if alignment.get("layer") != rendering.get("layer"):
            continue
        target_text = " / ".join(
            span_by_id[span_id].get("text", "")
            for span_id in alignment.get("target_span_ids", [])
            if span_id in span_by_id
        )
        for token_id in alignment.get("source_token_ids", []):
            lookup[token_id].append(
                {
                    "alignment_id": alignment["alignment_id"],
                    "type": alignment.get("alignment_type", "uncertain"),
                    "confidence": alignment.get("confidence", 0.0),
                    "target_text": target_text or None,
                    "notes": alignment.get("notes", ""),
                }
            )
    return lookup


def _source_role(token: dict[str, Any]) -> str | None:
    return token.get("semantic_role") or token.get("syntax_role") or token.get("part_of_speech")


def _creative_liberties(
    unit: dict[str, Any], rendering: dict[str, Any], mapped_tokens: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    liberties: list[dict[str, Any]] = []
    for token in mapped_tokens:
        for alignment in token.get("alignments", []):
            alignment_type = alignment["type"]
            if alignment_type in CREATIVE_ALIGNMENT_TYPES:
                alignment_label = alignment_type.replace("_", " ")
                liberties.append(
                    {
                        "kind": "structural_turn",
                        "severity": "review",
                        "token_id": token["token_id"],
                        "label": f"{token['surface']} uses {alignment_label} alignment",
                        "detail": alignment.get("notes")
                        or alignment.get("target_text")
                        or "Review the source-to-target shift.",
                    }
                )
    for flag in rendering.get("drift_flags", []):
        liberties.append(
            {
                "kind": "recorded_drift",
                "severity": flag.get("severity", "review"),
                "token_id": None,
                "label": flag.get("code", "recorded drift").replace("_", " "),
                "detail": flag.get("message", "Recorded by rendering analysis."),
            }
        )
    translation_basis = (
        rendering.get("translation_basis")
        or rendering.get("provenance", {}).get("translation_basis")
        or {}
    )
    if translation_basis.get("basis_type") == "septuagint_greek_to_english":
        liberties.append(
            {
                "kind": "source_basis",
                "severity": "review",
                "token_id": None,
                "label": "Septuagint-based translation",
                "detail": (
                    "This rendering declares a Greek witness basis; compare it with the Hebrew "
                    "source before treating it as Hebrew-close."
                ),
            }
        )
    source_content_count = sum(bool(_token_anchors(token)) for token in unit.get("tokens", []))
    target_count = len(_content_words(rendering.get("text")))
    if source_content_count and target_count > source_content_count * 1.65 + 2:
        liberties.append(
            {
                "kind": "expansion",
                "severity": "review",
                "token_id": None,
                "label": "Expanded English wording",
                "detail": (
                    f"The rendering has {target_count} content words for "
                    f"{source_content_count} source lexical anchors."
                ),
            }
        )
    if source_content_count >= 4 and target_count < source_content_count * 0.5:
        liberties.append(
            {
                "kind": "compression",
                "severity": "review",
                "token_id": None,
                "label": "Compressed English wording",
                "detail": (
                    f"The rendering has {target_count} content words for "
                    f"{source_content_count} source lexical anchors."
                ),
            }
        )
    for token in mapped_tokens:
        if token.get("semantic_role") in IMAGE_ROLES and token["status"] == "unmapped":
            source_image = token["gloss"] or token["surface"]
            liberties.append(
                {
                    "kind": "image_not_lexically_visible",
                    "severity": "review",
                    "token_id": token["token_id"],
                    "label": f"Source image may be transformed: {source_image}",
                    "detail": (
                        "No explicit alignment or lexical anchor was found. This is a review cue, "
                        "not a claim of omission."
                    ),
                }
            )
    return liberties


def _map_unit(
    unit: dict[str, Any],
    layer: str,
    translation_source: str,
    rendering_status: str,
    witness_source_id: str | None,
) -> dict[str, Any]:
    rendering = (
        _rendering_for_layer(unit, layer, rendering_status)
        if translation_source == "saved"
        else _witness_rendering(unit, layer, witness_source_id or "")
    )
    if rendering is None:
        untranslated_tokens = [
            {
                "token_id": token["token_id"],
                "surface": token.get("surface", ""),
                "transliteration": token.get("transliteration"),
                "lemma": token.get("lemma"),
                "gloss": token.get("display_gloss") or token.get("word_sense"),
                "source_role": _source_role(token),
                "semantic_role": token.get("semantic_role"),
                "anchors": _token_anchors(token),
                "visible_anchors": [],
                "alignments": [],
                "status": "unmapped",
                "fidelity_weight": 0.0,
            }
            for token in unit.get("tokens", [])
        ]
        return {
            "unit_id": unit["unit_id"],
            "ref": unit["ref"],
            "source_hebrew": unit["source_hebrew"],
            "source_transliteration": unit.get("source_transliteration"),
            "rendering": None,
            "summary": {
                "state": "untranslated",
                "selection_message": (
                    f"No {witness_source_id} witness is attached to this verse."
                    if translation_source == "witness"
                    else (
                        f"No {rendering_status.replace('_', ' ')} saved rendering exists for "
                        f"the {layer} layer."
                        if rendering_status != "preferred"
                        else f"No saved rendering exists for the {layer} layer."
                    )
                ),
                "source_token_count": len(unit.get("tokens", [])),
                "explicitly_mapped_tokens": 0,
                "lexically_visible_tokens": 0,
                "unmapped_tokens": len(unit.get("tokens", [])),
                "structural_coverage": 0.0,
                "visible_anchor_coverage": 0.0,
                "fidelity_estimate": None,
            },
            "tokens": untranslated_tokens,
            "creative_liberties": [],
        }

    target_words = set(_content_words(rendering.get("text")))
    alignments = _alignment_lookup(unit, rendering) if translation_source == "saved" else {}
    tokens: list[dict[str, Any]] = []
    for token in unit.get("tokens", []):
        token_alignments = alignments.get(token["token_id"], [])
        anchors = _token_anchors(token)
        visible_anchors = _anchor_matches(anchors, target_words)
        if token_alignments:
            status = "explicit"
            fidelity_weight = max(
                ALIGNMENT_WEIGHTS.get(alignment["type"], ALIGNMENT_WEIGHTS["uncertain"])
                * float(alignment.get("confidence", 0.0))
                for alignment in token_alignments
            )
        elif visible_anchors:
            status = "lexical_estimate"
            fidelity_weight = 0.58
        else:
            status = "unmapped"
            fidelity_weight = 0.0
        tokens.append(
            {
                "token_id": token["token_id"],
                "surface": token.get("surface", ""),
                "transliteration": token.get("transliteration"),
                "lemma": token.get("lemma"),
                "gloss": token.get("display_gloss") or token.get("word_sense"),
                "source_role": _source_role(token),
                "semantic_role": token.get("semantic_role"),
                "anchors": anchors,
                "visible_anchors": visible_anchors,
                "alignments": token_alignments,
                "status": status,
                "fidelity_weight": round(fidelity_weight, 3),
            }
        )

    token_count = len(tokens)
    explicit_count = sum(token["status"] == "explicit" for token in tokens)
    lexical_count = sum(token["status"] == "lexical_estimate" for token in tokens)
    unmapped_count = token_count - explicit_count - lexical_count
    return {
        "unit_id": unit["unit_id"],
        "ref": unit["ref"],
        "source_hebrew": unit["source_hebrew"],
        "source_transliteration": unit.get("source_transliteration"),
        "rendering": {
            "rendering_id": rendering["rendering_id"],
            "status": rendering["status"],
            "layer": rendering["layer"],
            "text": rendering["text"],
            "source_kind": rendering.get("_source_kind", "saved"),
            "source_label": rendering.get("_source_label", "Saved rendering"),
            "witness": rendering.get("_witness"),
            "translation_basis": rendering.get("translation_basis")
            or rendering.get("provenance", {}).get("translation_basis"),
            "rationale": rendering.get("rationale", ""),
        },
        "summary": {
            "state": "mapped",
            "source_token_count": token_count,
            "explicitly_mapped_tokens": explicit_count,
            "lexically_visible_tokens": lexical_count,
            "unmapped_tokens": unmapped_count,
            "structural_coverage": round(explicit_count / token_count, 3) if token_count else 0.0,
            "visible_anchor_coverage": round((explicit_count + lexical_count) / token_count, 3)
            if token_count
            else 0.0,
            "fidelity_estimate": round(
                sum(token["fidelity_weight"] for token in tokens) / token_count, 3
            )
            if token_count
            else None,
        },
        "tokens": tokens,
        "creative_liberties": _creative_liberties(unit, rendering, tokens),
    }


def _source_repetitions(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        for token in unit.get("tokens", []):
            anchors = _token_anchors(token)
            anchor_words = {word for anchor in anchors for word in anchor.split()}
            if not anchor_words:
                continue
            key = str(token.get("lemma") or token.get("normalized") or token.get("surface") or "")
            if not key:
                continue
            occurrences[key].append(
                {
                    "unit_id": unit["unit_id"],
                    "ref": unit["ref"],
                    "token_id": token["token_id"],
                    "surface": token.get("surface", ""),
                    "gloss": token.get("display_gloss") or token.get("word_sense"),
                    "anchors": sorted(anchor_words),
                }
            )
    repetitions = []
    for lemma, entries in occurrences.items():
        if len(entries) < 2:
            continue
        repetitions.append(
            {
                "lemma": lemma,
                "label": entries[0]["gloss"] or entries[0]["surface"],
                "glosses": _unique([str(entry["gloss"] or "") for entry in entries]),
                "count": len(entries),
                "occurrences": entries,
            }
        )
    return sorted(repetitions, key=lambda item: (-item["count"], item["label"].casefold()))


def _repetition_report(
    mapped_units: list[dict[str, Any]], source_repetitions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    token_state = {
        token["token_id"]: token for unit in mapped_units for token in unit.get("tokens", [])
    }
    report = []
    for repetition in source_repetitions:
        occurrences = repetition["occurrences"]
        mapped = [token_state.get(item["token_id"]) for item in occurrences]
        explicit_count = sum(item is not None and item["status"] == "explicit" for item in mapped)
        visible_count = sum(
            item is not None and item["status"] in {"explicit", "lexical_estimate"}
            for item in mapped
        )
        report.append(
            {
                **repetition,
                "explicitly_mapped_count": explicit_count,
                "visible_anchor_count": visible_count,
                "preservation": (
                    "structurally_preserved"
                    if explicit_count == repetition["count"]
                    else "lexically_visible"
                    if visible_count == repetition["count"]
                    else "partially_visible"
                    if visible_count
                    else "not_visible"
                ),
            }
        )
    return report


def _possible_added_repetitions(
    mapped_units: list[dict[str, Any]], source_repetitions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    source_anchor_words = {
        word
        for repetition in source_repetitions
        for occurrence in repetition["occurrences"]
        for word in occurrence["anchors"]
    }
    target_words = Counter(
        word
        for unit in mapped_units
        for word in _content_words((unit.get("rendering") or {}).get("text"))
    )
    return [
        {
            "word": word,
            "count": count,
            "label": f"Possible added repetition: {word}",
            "detail": (
                "This English word repeats but is not a visible anchor for a repeated Hebrew "
                "lemma. "
                "Review whether it is a stylistic refrain or a source-grounded echo."
            ),
        }
        for word, count in target_words.most_common()
        if count >= 3 and word not in source_anchor_words
    ][:12]


def _witness_target(units: list[dict[str, Any]], witness_source_id: str) -> dict[str, Any]:
    for unit in units:
        for witness in unit.get("witnesses", []):
            if witness.get("source_id") == witness_source_id:
                version_title = witness.get("versionTitle") or witness_source_id
                return {
                    "kind": "witness",
                    "label": f"{witness_source_id.upper()} · {version_title}",
                    "rendering_status": None,
                    "witness_source_id": witness_source_id,
                    "version_title": version_title,
                    "read_only": True,
                }
    raise ValidationError(f"No attached witness source found: {witness_source_id}")


def get_source_translation_map(
    psalm_id: str,
    layer: str,
    translation_source: str = "saved",
    rendering_status: str = "preferred",
    witness_source_id: str | None = None,
) -> dict[str, Any]:
    if layer not in LAYERS:
        raise ValidationError(f"Unknown rendering layer: {layer}")
    if translation_source not in TRANSLATION_SOURCES:
        raise ValidationError(f"Unknown translation source: {translation_source}")
    if rendering_status not in SELECTABLE_RENDERING_STATUSES:
        raise ValidationError(f"Unknown rendering status: {rendering_status}")
    if translation_source == "witness" and not witness_source_id:
        raise ValidationError("Choose an attached witness source for witness comparison")
    psalm = registry_service.load_psalm(psalm_id)
    units = psalm.get("units", [])
    saved_status_label = (
        "best available status"
        if rendering_status == "preferred"
        else rendering_status.replace("_", " ")
    )
    translation_target = (
        _witness_target(units, witness_source_id or "")
        if translation_source == "witness"
        else {
            "kind": "saved",
            "label": f"Saved {layer} renderings · {saved_status_label}",
            "rendering_status": rendering_status,
            "witness_source_id": None,
            "version_title": None,
            "read_only": False,
        }
    )
    mapped_units = [
        _map_unit(
            unit,
            layer,
            translation_source,
            rendering_status,
            witness_source_id,
        )
        for unit in units
    ]
    source_repetitions = _source_repetitions(units)
    repetitions = _repetition_report(mapped_units, source_repetitions)
    mapped_summaries = [
        unit["summary"] for unit in mapped_units if unit["summary"]["state"] == "mapped"
    ]
    total_tokens = sum(unit["summary"]["source_token_count"] for unit in mapped_units)
    explicit_tokens = sum(unit["summary"]["explicitly_mapped_tokens"] for unit in mapped_units)
    lexical_tokens = sum(unit["summary"]["lexically_visible_tokens"] for unit in mapped_units)
    return {
        "psalm_id": psalm["psalm_id"],
        "title": psalm["title"],
        "layer": layer,
        "translation_target": translation_target,
        "score_basis": (
            "Witness comparisons are read-only and have no project alignments; "
            "their highlights are lexical estimates only."
            if translation_source == "witness"
            else "Explicit alignments are structural evidence. Lexical estimates "
            "only identify visible English anchors and do not prove semantic equivalence."
        ),
        "summary": {
            "total_units": len(mapped_units),
            "translated_units": len(mapped_summaries),
            "total_source_tokens": total_tokens,
            "explicitly_mapped_tokens": explicit_tokens,
            "lexically_visible_tokens": lexical_tokens,
            "structural_coverage": round(explicit_tokens / total_tokens, 3)
            if total_tokens
            else 0.0,
            "visible_anchor_coverage": round((explicit_tokens + lexical_tokens) / total_tokens, 3)
            if total_tokens
            else 0.0,
            "fidelity_estimate": (
                round(
                    sum(item["fidelity_estimate"] or 0.0 for item in mapped_summaries)
                    / len(mapped_summaries),
                    3,
                )
                if mapped_summaries
                else None
            ),
        },
        "units": mapped_units,
        "repetitions": repetitions,
        "possible_added_repetitions": _possible_added_repetitions(mapped_units, source_repetitions),
    }
