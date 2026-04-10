from __future__ import annotations

import re
from collections import Counter
from typing import Any


LYRIC_LAYERS = {"lyric", "metered_lyric", "parallelism_lyric"}
HIGH_SEVERITY = "high"
REQUIRED_LYRIC_METRICS = {
    "syllable_count",
    "stress_approximation",
    "line_length",
    "repetition_score",
    "singability_score",
    "parallelism_preservation_score",
}

_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)
_WORD_RE = re.compile(r"[A-Za-z']+")
_NEGATION_WORDS = {"no", "not", "never", "none", "nothing", "without", "neither", "nor"}
_NUMBER_WORDS = {
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
}
_DOCTRINE_WORDS = {"grace", "gospel", "cross", "salvation", "redeem", "redeemer", "atonement", "faith", "spirit", "sin"}
_GENERIC_FLATTENING_WORDS = {"care", "help", "guide", "protector", "comfort", "support", "presence"}
def analyze_rendering(
    unit: dict[str, Any],
    layer: str,
    text: str,
    style_tags: list[str] | None = None,
    target_spans: list[dict[str, Any]] | None = None,
    existing_flags: list[dict[str, Any] | str] | None = None,
    existing_metrics: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    style_tags = style_tags or []
    target_spans = target_spans or []
    if layer not in LYRIC_LAYERS:
        return [_normalize_flag(flag) for flag in (existing_flags or [])], dict(existing_metrics or {})
    normalized_text = text.strip()
    literal = next((item for item in unit.get("renderings", []) if item.get("layer") == "literal" and item.get("status") == "canonical"), None)
    literal_text = literal.get("text", "") if literal else ""
    literal_span_count = len(literal.get("target_spans", [])) if literal else 0

    metrics = dict(existing_metrics or {})
    metrics.update(_compute_metrics(normalized_text, literal_text, style_tags, target_spans))

    computed_flags = _compute_drift_flags(
        unit=unit,
        layer=layer,
        text=normalized_text,
        literal_text=literal_text,
        literal_span_count=literal_span_count,
        target_spans=target_spans,
    )
    flags = _merge_flags(existing_flags or [], computed_flags)
    return flags, metrics


def has_blocking_drift(rendering: dict[str, Any]) -> bool:
    return any(flag.get("severity") == HIGH_SEVERITY for flag in rendering.get("drift_flags", []))


def missing_required_lyric_metrics(rendering: dict[str, Any]) -> list[str]:
    if rendering.get("layer") not in LYRIC_LAYERS:
        return []
    metrics = rendering.get("metrics", {})
    return sorted(metric for metric in REQUIRED_LYRIC_METRICS if metric not in metrics)


def format_flag(flag: dict[str, Any] | str) -> str:
    if isinstance(flag, str):
        return flag
    return f"{flag['code']}:{flag['severity']}"


def normalize_flag(flag: dict[str, Any] | str) -> dict[str, Any]:
    return _normalize_flag(flag)


def _compute_metrics(
    text: str,
    literal_text: str,
    style_tags: list[str],
    target_spans: list[dict[str, Any]],
) -> dict[str, float | int]:
    words = _words(text)
    syllable_count = sum(_approximate_syllables(word) for word in words)
    line_length = len(words)
    repetition_score = _repetition_score(words)
    stress_approximation = _stress_approximation(words)
    target_syllables = _target_syllables(style_tags)
    singability_score = _singability_score(syllable_count, line_length, repetition_score, target_syllables)
    parallelism_score = _parallelism_preservation_score(text, literal_text, target_spans)
    return {
        "syllable_count": syllable_count,
        "syllables": syllable_count,
        "stress_approximation": stress_approximation,
        "line_length": line_length,
        "repetition_score": repetition_score,
        "singability_score": singability_score,
        "parallelism_preservation_score": parallelism_score,
    }


def _compute_drift_flags(
    unit: dict[str, Any],
    layer: str,
    text: str,
    literal_text: str,
    literal_span_count: int,
    target_spans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if layer not in LYRIC_LAYERS:
        return []
    lowered_words = set(_words(text))
    source_hint_text = " ".join(
        str(token.get(field) or "")
        for token in unit.get("tokens", [])
        for field in ("surface", "normalized", "lemma", "referent", "word_sense", "morph_code", "morph_readable")
    ).casefold()
    flags: list[dict[str, Any]] = []

    if _contains_any(lowered_words, _NEGATION_WORDS) and not _contains_any(source_hint_text.split(), _NEGATION_WORDS):
        flags.append(_flag("negation_change", "high", 0.97, "English introduces negation absent from source cues."))

    source_numbers = _extract_number_markers(source_hint_text)
    target_numbers = _extract_number_markers(text)
    if source_numbers != target_numbers:
        if source_numbers or target_numbers:
            flags.append(_flag("number_change", "high", 0.9, "Number marking diverges between source cues and English line."))

    source_persons = _source_person_markers(unit)
    target_persons = _target_person_markers(text)
    if source_persons and source_persons != target_persons:
        flags.append(_flag("speaker_addressee_change", "high", 0.9, "Pronoun or person marking diverges from source morphology."))

    if _has_tense_shift(source_hint_text, text):
        flags.append(_flag("tense_aspect_shift", "medium", 0.76, "English tense/aspect appears to shift from source cues."))

    if _has_omitted_image(unit, lowered_words):
        flags.append(_flag("omitted_image", "high", 0.88, "Image-bearing source term is missing from the lyric line."))

    if _contains_any(lowered_words, _DOCTRINE_WORDS):
        literal_words = set(_words(literal_text))
        if not _contains_any(literal_words, _DOCTRINE_WORDS):
            flags.append(_flag("added_doctrine", "high", 0.93, "Lyric line adds doctrinal vocabulary not present in the canonical literal line."))

    if _has_metaphor_flattening(unit, lowered_words):
        flags.append(_flag("metaphor_flattening", "medium", 0.74, "Concrete source image has been flattened into a generic abstraction."))

    if literal_span_count > 1 and len(target_spans) <= 1:
        flags.append(_flag("parallelism_break", "medium", 0.72, "Lyric line compresses a multi-span source into a single span."))

    literal_words = _words(literal_text)
    target_words = _words(text)
    if literal_words and len(target_words) <= max(1, int(len(literal_words) * 0.6)):
        flags.append(_flag("semantic_overcompression", "medium", 0.79, "Lyric line is materially shorter than the canonical literal rendering."))

    return flags


def _merge_flags(existing: list[dict[str, Any] | str], computed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for flag in existing:
        normalized = _normalize_flag(flag)
        merged[(normalized["code"], normalized["severity"])] = normalized
    for flag in computed:
        key = (flag["code"], flag["severity"])
        prior = merged.get(key)
        if prior is None or flag["confidence"] >= prior["confidence"]:
            merged[key] = flag
    return sorted(merged.values(), key=lambda item: (item["severity"], item["code"]))


def _normalize_flag(flag: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(flag, dict):
        return {
            "code": flag["code"],
            "severity": flag["severity"],
            "confidence": round(float(flag.get("confidence", 0.5)), 2),
            "message": flag.get("message", flag["code"].replace("_", " ")),
        }
    code, _, severity = flag.partition(":")
    severity = severity or "medium"
    return _flag(code, severity, 0.5, code.replace("_", " "))


def _flag(code: str, severity: str, confidence: float, message: str) -> dict[str, Any]:
    return {"code": code, "severity": severity, "confidence": round(confidence, 2), "message": message}


def _words(text: str) -> list[str]:
    return [match.group(0).casefold() for match in _WORD_RE.finditer(text)]


def _approximate_syllables(word: str) -> int:
    groups = _VOWEL_GROUP_RE.findall(word)
    return max(1, len(groups))


def _repetition_score(words: list[str]) -> float:
    if not words:
        return 0.0
    counts = Counter(words)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return round(repeated / len(words), 2)


def _stress_approximation(words: list[str]) -> float:
    syllables = [_approximate_syllables(word) for word in words]
    if not syllables:
        return 0.0
    stressed = sum(1 for count in syllables if count >= 1)
    heavy = sum(1 for count in syllables if count >= 2)
    return round((stressed + heavy) / max(1, 2 * len(words)), 2)


def _target_syllables(style_tags: list[str]) -> int:
    tag_text = " ".join(style_tags)
    match = re.search(r"(\d+)", tag_text)
    if match:
        return int(match.group(1))
    if "metered_common_meter" in style_tags:
        return 8
    if "formal_liturgical" in style_tags:
        return 9
    return 8


def _singability_score(syllable_count: int, line_length: int, repetition_score: float, target_syllables: int) -> float:
    syllable_fit = max(0.0, 1.0 - (abs(syllable_count - target_syllables) / max(1, target_syllables)))
    line_fit = max(0.0, 1.0 - (abs(line_length - 8) / 8))
    repetition_fit = min(1.0, 0.4 + repetition_score)
    return round((0.5 * syllable_fit) + (0.3 * line_fit) + (0.2 * repetition_fit), 2)


def _parallelism_preservation_score(text: str, literal_text: str, target_spans: list[dict[str, Any]]) -> float:
    literal_words = set(_words(literal_text))
    target_words = set(_words(text))
    if not literal_words:
        return 1.0
    lexical_overlap = len(literal_words & target_words) / len(literal_words)
    span_bonus = 1.0 if len(target_spans) > 1 else 0.85
    return round(min(1.0, (0.75 * lexical_overlap) + (0.25 * span_bonus)), 2)


def _contains_any(words: set[str] | list[str], candidates: set[str]) -> bool:
    return any(word in candidates for word in words)


def _extract_number_markers(text: str) -> set[str]:
    words = set(_words(text))
    digits = set(re.findall(r"\b\d+\b", text))
    return words & _NUMBER_WORDS | digits


def _source_person_markers(unit: dict[str, Any]) -> set[str]:
    markers: set[str] = set()
    for token in unit.get("tokens", []):
        morph = str(token.get("morph_code") or "").casefold()
        referent_words = set(_words(str(token.get("referent") or "")))
        if any(hint in morph for hint in ("1cs", "1cp")) or referent_words & {"i", "me", "my", "mine", "we", "our", "us"}:
            markers.add("first")
        if any(hint in morph for hint in ("2ms", "2fs", "2mp", "2fp")) or referent_words & {"you", "your", "yours", "thee", "thou"}:
            markers.add("second")
        if any(hint in morph for hint in ("3ms", "3fs", "3mp", "3fp")) or referent_words & {"he", "his", "she", "her", "they", "their"}:
            markers.add("third")
    return markers


def _target_person_markers(text: str) -> set[str]:
    words = set(_words(text))
    markers: set[str] = set()
    if words & {"i", "me", "my", "mine", "we", "our", "us"}:
        markers.add("first")
    if words & {"you", "your", "yours", "thee", "thou"}:
        markers.add("second")
    if words & {"he", "his", "she", "her", "they", "their"}:
        markers.add("third")
    return markers


def _has_tense_shift(source_hint_text: str, text: str) -> bool:
    source_has_participle = "participle" in source_hint_text
    text_words = set(_words(text))
    target_has_past = bool(text_words & {"was", "were", "had", "did"})
    return source_has_participle and target_has_past


def _has_omitted_image(unit: dict[str, Any], lowered_words: set[str]) -> bool:
    image_terms = {
        str(token.get("word_sense") or "").casefold()
        for token in unit.get("tokens", [])
        if str(token.get("semantic_role") or "").casefold() in {"caregiver", "animal", "object", "place", "natural_phenomenon"}
        and token.get("word_sense")
    }
    image_terms -= {"the", "a", "an", "man", "person"}
    return bool(image_terms) and not any(term in lowered_words for term in image_terms)


def _has_metaphor_flattening(unit: dict[str, Any], lowered_words: set[str]) -> bool:
    source_images = {
        str(token.get("referent") or token.get("word_sense") or "").casefold()
        for token in unit.get("tokens", [])
        if token.get("semantic_role") or token.get("word_sense") or token.get("referent")
    }
    if not source_images:
        return False
    if any(any(part in lowered_words for part in image.split()) for image in source_images):
        return False
    return any(word in lowered_words for word in _GENERIC_FLATTENING_WORDS)
