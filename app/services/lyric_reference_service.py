from __future__ import annotations

import os
import re
from collections import Counter
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'/-]*")
DIRECT_ADDRESS_RE = re.compile(
    r"^(listen|please|quick|god|lord|o lord|o god|my god|king-god)\b", re.IGNORECASE
)
PETITION_OPENING_RE = re.compile(
    r"^(listen|hear|help|save|give|lead|make|let|wake|rise|come|turn|keep|guard|break|answer|remember)\b",
    re.IGNORECASE,
)
CONTRACTION_RE = re.compile(
    r"\b(?:don't|doesn't|can't|won't|you'll|you're|i'm|i've|we're|they're|it's)\b", re.IGNORECASE
)
CONCRETE_IMAGE_RE = re.compile(
    r"\b(tree|fruit|leaf|dust|road|shield|fire|bed|tears|flood|grave|valley|table|oil|cup|mountains?|enemy|bones?|eyes?|waters?)\b",
    re.IGNORECASE,
)
LAMENT_PRESSURE_RE = re.compile(
    r"\b(why|how long|no more|tired|depths|cry|groan|help|afraid|enemy|death|tears?)\b",
    re.IGNORECASE,
)
MIN_SURFACED_PRODUCTION_QUALITY = 0.85
ARCHAIC_DICTION_RE = re.compile(
    r"\b(nor|behold|walketh|standeth|sitteth|doth|hast|thou|thee|thy|thine|yea|unto)\b",
    re.IGNORECASE,
)
PERFORMANCE_DIRECTION_RE = re.compile(
    r"(^|\n)\s*\[[^\]]+\]|\b(intro|outro|verse|chorus|bridge|hook|pre-chorus|bars?|piano|vocals?|spoken|swell|cutout)\b",
    re.IGNORECASE,
)
TRANSLATIONESE_RE = re.compile(
    r"\b(in your \w+ me \w+|me \w+ (?:do not|don't)|(?:do not|don't) me \w+|of [a-z]+ of [a-z]+)\b",
    re.IGNORECASE,
)
UNSINGABLE_THIRD_PERSON_NEGATIVE_CONNECTOR_RE = re.compile(
    r"^\s*and\s+(?:doesn['’]?t|does not|won['’]?t|will not|shall not|can['’]?t|cannot)\b",
    re.IGNORECASE,
)
MUSICAL_HEADING_TO_FRAGMENT_RE = re.compile(
    r"^\s*to\s+(?:the\s+)?(?:flutes?|choir\s*(?:master|director)?|choirmaster|"
    r"chief musician|director)\b",
    re.IGNORECASE,
)
ARCHAIC_VERB_BARE = {
    "walketh": "walk",
    "standeth": "stand",
    "sitteth": "sit",
    "doth": "do",
    "hath": "have",
    "hast": "have",
}
ARCHAIC_WORD_REPLACEMENTS = {
    "thou": "you",
    "thee": "you",
    "thy": "your",
    "thine": "your",
    "unto": "to",
}


def _contracted_auxiliary(stage: str) -> str:
    return "does not" if stage in {"gloss", "literal", "phrase"} else "doesn't"


def _negative_imperative(stage: str) -> str:
    return "Do not" if stage in {"gloss", "literal", "phrase"} else "Don't"


def _bare_verb(value: str) -> str:
    lowered = value.lower()
    return ARCHAIC_VERB_BARE.get(lowered, lowered)


def _capitalize_first(value: str) -> str:
    return value[:1].upper() + value[1:] if value else value


def _repair_archaisms(line: str, stage: str) -> str:
    auxiliary = _contracted_auxiliary(stage)

    def replace_verb_not(match: re.Match[str]) -> str:
        return f"{auxiliary} {_bare_verb(match.group(1))}"

    repaired = re.sub(
        r"\b(walketh|standeth|sitteth|doth|hath|hast)\s+not\b",
        replace_verb_not,
        line,
        flags=re.IGNORECASE,
    )
    for archaic, modern in ARCHAIC_WORD_REPLACEMENTS.items():
        repaired = re.sub(rf"\b{archaic}\b", modern, repaired, flags=re.IGNORECASE)
    return repaired


def _repair_leading_nor(line: str, stage: str) -> str:
    auxiliary = _contracted_auxiliary(stage)

    def replace(match: re.Match[str]) -> str:
        verb = _bare_verb(match.group("verb"))
        tail = match.group("tail") or ""
        connector = "And " if stage in {"gloss", "literal", "phrase"} else ""
        return _capitalize_first(f"{connector}{auxiliary} {verb}{tail}")

    return re.sub(
        r"^\s*nor\s+(?P<verb>[A-Za-z][A-Za-z'-]*)(?P<tail>(?:\s+.*)?)$",
        replace,
        line,
        flags=re.IGNORECASE,
    )


def _repair_translationese_order(line: str, stage: str) -> str:
    negative = _negative_imperative(stage)

    def replace_negative_preposed(match: re.Match[str]) -> str:
        pressure = match.group("pressure").strip()
        verb = match.group("verb").strip().lower()
        return f"{negative} {verb} me in your {pressure}"

    repaired = re.sub(
        r"^\s*in your (?P<pressure>[A-Za-z][A-Za-z' -]*?)\s+me\s+"
        r"(?P<verb>[A-Za-z][A-Za-z'-]*)\s+(?:do not|don't)\s*$",
        replace_negative_preposed,
        line,
        flags=re.IGNORECASE,
    )
    if repaired != line:
        return _capitalize_first(repaired)

    def replace_preposed(match: re.Match[str]) -> str:
        pressure = match.group("pressure").strip()
        verb = match.group("verb").strip().lower()
        return f"{verb} me in your {pressure}"

    repaired = re.sub(
        r"^\s*in your (?P<pressure>[A-Za-z][A-Za-z' -]*?)\s+me\s+(?P<verb>[A-Za-z][A-Za-z'-]*)\s*$",
        replace_preposed,
        line,
        flags=re.IGNORECASE,
    )
    if repaired != line:
        return _capitalize_first(repaired)

    def replace_negative_object_first(match: re.Match[str]) -> str:
        verb = match.group("verb").strip().lower()
        return f"{negative} {verb} me"

    repaired = re.sub(
        r"^\s*me\s+(?P<verb>[A-Za-z][A-Za-z'-]*)\s+(?:do not|don't)\s*$",
        replace_negative_object_first,
        line,
        flags=re.IGNORECASE,
    )
    return _capitalize_first(repaired) if repaired != line else line


def _repair_musical_heading_fragment(line: str, stage: str) -> str:
    if stage in {"gloss", "literal", "phrase"}:
        return line
    repaired = re.sub(
        r"^\s*to\s+(?:the\s+)?(?:choir\s*)?(?:master|director|choirmaster)\s*,?\s+to\s+the\s+flutes?\s*$",
        "For the choir director, with flutes",
        line,
        flags=re.IGNORECASE,
    )
    repaired = re.sub(
        r"^\s*to\s+(?:the\s+)?(?:choir\s*)?(?:master|director|choirmaster)\s*$",
        "For the choir director",
        repaired,
        flags=re.IGNORECASE,
    )
    repaired = re.sub(
        r"^\s*to\s+the\s+flutes?\s*$",
        "With flutes",
        repaired,
        flags=re.IGNORECASE,
    )
    return repaired


def repair_candidate_delivery(text: str, stage: str) -> str:
    """Repair reversible delivery defects without changing source content."""

    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    repaired_lines: list[str] = []
    for line in lines:
        repaired = " ".join(line.split())
        if not repaired:
            continue
        repaired = _repair_musical_heading_fragment(repaired, stage)
        repaired = _repair_leading_nor(repaired, stage)
        repaired = _repair_translationese_order(repaired, stage)
        repaired = _repair_archaisms(repaired, stage)
        repaired = re.sub(r"\s+([,.;:!?])", r"\1", repaired)
        repaired = " ".join(repaired.split())
        if repaired:
            repaired_lines.append(repaired)
    return "\n".join(repaired_lines).strip()


def _windows_path_to_wsl(path_value: str) -> Path | None:
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", path_value)
    if not match:
        return None
    drive = match.group(1).lower()
    tail = match.group(2).replace("\\", "/")
    return Path("/mnt") / drive / tail


def _candidate_roots() -> list[Path]:
    values: list[str] = []
    env_value = os.environ.get("ALEPHTAV_LYRIC_REFERENCE_ROOT")
    if env_value:
        values.append(env_value)
    values.extend(["/mnt/d/Psalms", "D:/Psalms", r"D:\Psalms"])

    roots: list[Path] = []
    seen: set[str] = set()
    for value in values:
        path = Path(value).expanduser()
        candidates = [path]
        wsl_path = _windows_path_to_wsl(value)
        if wsl_path is not None:
            candidates.append(wsl_path)
        for candidate in candidates:
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                roots.append(candidate)
    return roots


def _selected_root() -> Path | None:
    return next((root for root in _candidate_roots() if root.exists() and root.is_dir()), None)


def _read_lyric_lines(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    return [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]


def _word_count(line: str) -> int:
    return len(TOKEN_RE.findall(line))


def _normalized_line_key(line: str) -> str:
    return " ".join(token.lower() for token in TOKEN_RE.findall(line))


@lru_cache(maxsize=16)
def _reference_line_keys_for_root(root_value: str, min_words: int = 4) -> frozenset[str]:
    if not root_value:
        return frozenset()
    root = Path(root_value)
    if not root.exists() or not root.is_dir():
        return frozenset()
    keys: set[str] = set()
    for path in sorted(root.glob("**/lyrics.txt"))[:24]:
        for line in _read_lyric_lines(path):
            key = _normalized_line_key(line)
            if len(key.split()) >= min_words:
                keys.add(key)
    return frozenset(keys)


def _reference_line_keys(min_words: int = 4) -> set[str]:
    root = _selected_root()
    if root is None:
        return set()
    return set(_reference_line_keys_for_root(str(root), min_words))


@lru_cache(maxsize=16)
def _reference_line_signatures_for_root(
    root_value: str, min_words: int = 4
) -> tuple[tuple[str, frozenset[str]], ...]:
    return tuple(
        (key, frozenset(key.split()))
        for key in _reference_line_keys_for_root(root_value, min_words)
    )


def _reference_line_signatures(min_words: int = 4) -> list[tuple[str, frozenset[str]]]:
    root = _selected_root()
    if root is None:
        return []
    return list(_reference_line_signatures_for_root(str(root), min_words))


def clear_reference_cache() -> None:
    _reference_line_keys_for_root.cache_clear()
    _reference_line_signatures_for_root.cache_clear()


def _is_near_reference_echo(
    line: str,
    reference_signatures: list[tuple[str, frozenset[str]]],
) -> bool:
    key = _normalized_line_key(line)
    words = frozenset(key.split())
    if len(words) < 5:
        return False

    for reference_key, reference_words in reference_signatures:
        if key == reference_key or len(reference_words) < 5:
            continue
        if abs(len(words) - len(reference_words)) > 2:
            continue
        shared = len(words & reference_words)
        if shared < max(4, min(len(words), len(reference_words)) - 1):
            continue
        similarity = SequenceMatcher(None, key, reference_key).ratio()
        if similarity >= 0.9:
            return True
    return False


def _stage_trait(stage: str) -> str:
    if stage == "phrase":
        return (
            "Use the corpus only to prefer living English over inherited Bible diction; "
            "phrase work remains source-close."
        )
    if stage == "concept":
        return (
            "Use the corpus to shape reader-facing concepts: ordinary speech, direct "
            "address, concrete image pressure, and emotionally legible turns."
        )
    return (
        "Use the corpus to shape singable lyric delivery: short lines, breath, "
        "repetition, hooks, and exposed emotional pressure."
    )


def _delivery_patterns(metrics: dict[str, int], stage: str) -> list[str]:
    if stage == "phrase":
        return [
            "Keep phrase candidates source-close; use lyric corpus patterns only to "
            "avoid wooden or archaic English."
        ]

    line_count = max(metrics.get("nonblank_lyric_line_count", 0), 1)
    short_ratio = metrics.get("short_line_count", 0) / line_count
    very_short_ratio = metrics.get("very_short_line_count", 0) / line_count
    question_ratio = metrics.get("question_line_count", 0) / line_count
    petition_ratio = metrics.get("petition_opening_line_count", 0) / line_count
    duplicate_count = metrics.get("duplicate_line_count", 0)
    direct_address_count = metrics.get("direct_address_line_count", 0)
    dash_count = metrics.get("dash_line_count", 0)
    exclamation_count = metrics.get("exclamation_line_count", 0)

    patterns: list[str] = []
    if short_ratio >= 0.55:
        patterns.append(
            "Favor compact delivery: most candidate lines should land in roughly 3-8 words."
        )
    elif very_short_ratio >= 0.25:
        patterns.append("Use very short pressure lines when the source has a strong turn or cry.")
    if direct_address_count:
        patterns.append(
            "Let direct address feel conversational when the source is vocative or petitioning."
        )
    if petition_ratio >= 0.08:
        patterns.append(
            "Petitions often start with active verbs; imperatives may be plain and "
            "immediate when source-grounded."
        )
    if question_ratio >= 0.06:
        patterns.append(
            "Questions can remain direct and unresolved instead of being softened into explanation."
        )
    if duplicate_count:
        patterns.append(
            "Repetition may become a refrain or pressure echo, but only when source "
            "movement supports it."
        )
    if dash_count:
        patterns.append("Dashes and broken clauses can carry hesitation or emotional interruption.")
    if exclamation_count:
        patterns.append(
            "Exclamation is allowed for urgent address, but do not manufacture intensity "
            "without source pressure."
        )
    if not patterns:
        patterns.append("Prefer ordinary spoken cadence over formal prose.")
    return patterns


def build_reference_payload(stage: str, max_files: int = 24) -> dict[str, Any]:
    root = _selected_root()
    if root is None:
        return {
            "available": False,
            "reference_root": "",
            "file_count": 0,
            "style_traits": [
                _stage_trait(stage),
                (
                    "No local lyric corpus was found; use the built-in project lyric "
                    "style brief instead."
                ),
            ],
            "delivery_patterns": _delivery_patterns({}, stage),
            "usage_policy": [
                "Style reference only; never source text.",
                "Do not copy completed lyrics into new candidates.",
                "Do not treat bracketed performance notes as translation content.",
            ],
        }

    files = sorted(root.glob("**/lyrics.txt"))[:max_files]
    nonblank_lines: list[str] = []
    duplicate_counter: Counter[str] = Counter()
    bracketed_count = 0
    direct_address_count = 0
    contraction_count = 0
    concrete_image_count = 0
    lament_pressure_count = 0
    petition_opening_count = 0
    question_count = 0
    exclamation_count = 0
    dash_count = 0

    for path in files:
        for line in _read_lyric_lines(path):
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                bracketed_count += 1
                continue
            normalized = " ".join(line.lower().split())
            duplicate_counter[normalized] += 1
            nonblank_lines.append(line)
            if "?" in line:
                question_count += 1
            if "!" in line:
                exclamation_count += 1
            if "—" in line or "--" in line:
                dash_count += 1
            if PETITION_OPENING_RE.search(line):
                petition_opening_count += 1
            if DIRECT_ADDRESS_RE.search(line):
                direct_address_count += 1
            if CONTRACTION_RE.search(line):
                contraction_count += 1
            if CONCRETE_IMAGE_RE.search(line):
                concrete_image_count += 1
            if LAMENT_PRESSURE_RE.search(line):
                lament_pressure_count += 1

    word_counts = [_word_count(line) for line in nonblank_lines if _word_count(line) > 0]
    duplicate_line_count = sum(count - 1 for count in duplicate_counter.values() if count > 1)
    median_words = int(median(word_counts)) if word_counts else 0
    short_line_count = sum(1 for count in word_counts if count <= 8)
    very_short_line_count = sum(1 for count in word_counts if count <= 3)
    observed_metrics = {
        "nonblank_lyric_line_count": len(nonblank_lines),
        "median_words_per_line": median_words,
        "short_line_count": short_line_count,
        "very_short_line_count": very_short_line_count,
        "duplicate_line_count": duplicate_line_count,
        "direct_address_line_count": direct_address_count,
        "petition_opening_line_count": petition_opening_count,
        "question_line_count": question_count,
        "exclamation_line_count": exclamation_count,
        "dash_line_count": dash_count,
        "concrete_image_line_count": concrete_image_count,
        "lament_pressure_line_count": lament_pressure_count,
    }

    style_traits = [_stage_trait(stage)]
    if median_words and median_words <= 8:
        style_traits.append("Lines trend short and singable; avoid padded prose.")
    if direct_address_count:
        style_traits.append(
            "Direct address is common; vocatives may become immediate ordinary speech "
            "when source-grounded."
        )
    if duplicate_line_count:
        style_traits.append(
            "Repetition is used as pressure or hook; add it only deliberately and flag "
            "it when it exceeds source movement."
        )
    if concrete_image_count:
        style_traits.append(
            "Concrete images carry emotion; do not flatten imagery into generic feeling words."
        )
    if contraction_count:
        style_traits.append(
            "Contemporary contractions are acceptable for concept and lyric delivery "
            "when they do not distort meaning."
        )
    if lament_pressure_count:
        style_traits.append(
            "Lament pressure should stay raw: fatigue, unanswered waiting, fear, "
            "accusation, and need can remain exposed."
        )
    if bracketed_count:
        style_traits.append(
            "Bracketed musical notes are arrangement references only, never translation text."
        )

    return {
        "available": True,
        "reference_root": str(root),
        "file_count": len(files),
        "observed_metrics": observed_metrics,
        "style_traits": style_traits,
        "delivery_patterns": _delivery_patterns(observed_metrics, stage),
        "usage_policy": [
            "Style reference only; never source text.",
            "Do not copy completed lyrics into new candidates.",
            "Do not treat bracketed performance notes as translation content.",
            "Hebrew and explicitly labeled Septuagint Greek remain the only translation bases.",
        ],
    }


def reference_guidance(stage: str) -> str:
    payload = build_reference_payload(stage)
    if not payload["available"]:
        return (
            "Lyric reference corpus: unavailable. "
            + " ".join(payload["style_traits"])
            + " Usage policy: "
            + " ".join(payload["usage_policy"])
        )

    metrics = payload.get("observed_metrics", {})
    return (
        "Lyric reference corpus: sampled "
        f"{payload['file_count']} lyrics.txt files from {payload['reference_root']}. "
        f"Observed median words per lyric line: {metrics.get('median_words_per_line', 0)}; "
        f"duplicate/refrain pressure lines: {metrics.get('duplicate_line_count', 0)}; "
        f"direct-address lines: {metrics.get('direct_address_line_count', 0)}; "
        f"concrete-image lines: {metrics.get('concrete_image_line_count', 0)}. "
        "Style traits: "
        + " ".join(payload["style_traits"])
        + " Delivery patterns: "
        + " ".join(payload.get("delivery_patterns", []))
        + " Usage policy: "
        + " ".join(payload["usage_policy"])
    )


def evaluate_candidate_quality(text: str, stage: str) -> dict[str, Any]:
    normalized = str(text or "").strip()
    issues: list[dict[str, Any]] = []
    score = 1.0

    if not normalized:
        return {
            "score": 0.0,
            "issues": [
                {
                    "code": "empty_candidate",
                    "severity": "high",
                    "message": "Candidate text is empty.",
                }
            ],
        }

    if ARCHAIC_DICTION_RE.search(normalized):
        issues.append(
            {
                "code": "archaic_diction",
                "severity": "medium",
                "message": (
                    "Candidate uses inherited or archaic Bible diction where common "
                    "English is expected."
                ),
            }
        )
        score -= 0.22

    if stage in {
        "concept",
        "lyric",
        "metered_lyric",
        "parallelism_lyric",
    } and PERFORMANCE_DIRECTION_RE.search(normalized):
        issues.append(
            {
                "code": "performance_direction_leak",
                "severity": "high",
                "message": (
                    "Candidate appears to include arrangement or performance direction "
                    "as translation text."
                ),
            }
        )
        score -= 0.38

    if TRANSLATIONESE_RE.search(normalized):
        issues.append(
            {
                "code": "translationese_syntax",
                "severity": "medium",
                "message": "Candidate preserves source-language word order in unnatural English.",
            }
        )
        score -= 0.28

    if stage in {
        "concept",
        "lyric",
        "metered_lyric",
        "parallelism_lyric",
    } and UNSINGABLE_THIRD_PERSON_NEGATIVE_CONNECTOR_RE.search(normalized):
        issues.append(
            {
                "code": "unsingable_series_connector",
                "severity": "medium",
                "message": (
                    "Candidate carries a source connector into a third-person negative "
                    "fragment where ordinary sung or spoken English would usually drop it."
                ),
            }
        )
        score -= 0.18

    if stage in {
        "concept",
        "lyric",
        "metered_lyric",
        "parallelism_lyric",
    } and MUSICAL_HEADING_TO_FRAGMENT_RE.search(normalized):
        issues.append(
            {
                "code": "unsmoothed_musical_heading_fragment",
                "severity": "medium",
                "message": (
                    "Candidate leaves a psalm heading as an unnatural musical-direction "
                    "fragment instead of smoothing it for delivery."
                ),
            }
        )
        score -= 0.22

    reference_keys = _reference_line_keys()
    reference_signatures = _reference_line_signatures()
    echoed_lines = [
        line
        for line in normalized.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if _normalized_line_key(line) in reference_keys
    ]
    if echoed_lines:
        issues.append(
            {
                "code": "lyric_reference_echo",
                "severity": "medium",
                "message": (
                    "Candidate exactly echoes a completed lyric reference line; "
                    "references are style-only, not source text."
                ),
            }
        )
        score -= 0.24

    near_echoed_lines = [
        line
        for line in normalized.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if _normalized_line_key(line) not in reference_keys
        and _is_near_reference_echo(line, reference_signatures)
    ]
    if near_echoed_lines:
        issues.append(
            {
                "code": "lyric_reference_near_echo",
                "severity": "medium",
                "message": (
                    "Candidate closely echoes a completed lyric reference line; "
                    "references are style-only, not reusable lyric text."
                ),
            }
        )
        score -= 0.24

    word_counts = [_word_count(line) for line in normalized.split("\n") if line.strip()]
    if (
        stage in {"lyric", "metered_lyric", "parallelism_lyric"}
        and word_counts
        and max(word_counts) > 18
    ):
        issues.append(
            {
                "code": "padded_prose_line",
                "severity": "low",
                "message": (
                    "Lyric candidate includes a long prose-like line where singable "
                    "delivery is expected."
                ),
            }
        )
        score -= 0.12

    return {"score": round(max(0.0, min(1.0, score)), 2), "issues": issues}


def is_surfaceable_quality(quality: dict[str, Any]) -> bool:
    if float(quality.get("score", 0.0)) < MIN_SURFACED_PRODUCTION_QUALITY:
        return False
    return not any(issue.get("severity") == "high" for issue in quality.get("issues", []))


def quality_drift_codes(text: str, stage: str) -> list[str]:
    return [
        f"{issue['severity']}:{issue['code']}"
        for issue in evaluate_candidate_quality(text, stage)["issues"]
    ]


def quality_drift_flags(text: str, stage: str) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for issue in evaluate_candidate_quality(text, stage)["issues"]:
        flags.append(
            {
                "code": issue["code"],
                "severity": issue["severity"],
                "confidence": 0.82,
                "message": issue["message"],
            }
        )
    return flags
