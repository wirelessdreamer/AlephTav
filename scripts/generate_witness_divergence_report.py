from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = ROOT / "content" / "psalms"
REPORT_ROOT = ROOT / "reports" / "research"

CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
WITNESS_READINESS_PATH = REPORT_ROOT / "witness_reception_readiness.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "witness_divergence_report.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "witness_divergence_units.csv"
DEFAULT_PAIR_CSV_OUTPUT = REPORT_ROOT / "witness_divergence_pairs.csv"
DEFAULT_PSALM_CSV_OUTPUT = REPORT_ROOT / "witness_divergence_psalms.csv"
DEFAULT_MARKER_CSV_OUTPUT = REPORT_ROOT / "witness_divergence_markers.csv"
DEFAULT_PRIORITY_CSV_OUTPUT = REPORT_ROOT / "witness_divergence_priority_units.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "witness_divergence_report.html"

ENGLISH_WITNESS_SOURCES = ["kjv", "asv", "web"]
HIGH_DIVERGENCE_THRESHOLD = 55.0
HIGH_PRIORITY_THRESHOLD = 90.0

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
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
    "me",
    "my",
    "nor",
    "not",
    "of",
    "on",
    "or",
    "our",
    "shall",
    "she",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "unto",
    "up",
    "us",
    "we",
    "who",
    "will",
    "with",
    "you",
    "your",
}

ARCHAIC_TERMS = {
    "art",
    "dost",
    "doth",
    "hast",
    "hath",
    "saith",
    "shalt",
    "thee",
    "thine",
    "thou",
    "thy",
    "unto",
    "wast",
    "wert",
}

DIVINE_PATTERNS = {
    "LORD": re.compile(r"\bLORD\b"),
    "Jehovah": re.compile(r"\bJehovah\b", flags=re.I),
    "Lord": re.compile(r"\bLord\b"),
    "God": re.compile(r"\bGod\b"),
    "Most High": re.compile(r"\bMost High\b", flags=re.I),
    "Yah": re.compile(r"\bYah\b", flags=re.I),
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def maybe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_json(path)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def fmt_pct(value: Any) -> str:
    return f"{float(value):.2f}%"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def normalize_tokens(text: str) -> list[str]:
    normalized = (
        text.replace("[", " ").replace("]", " ").replace("`", "'").replace("’", "'").lower()
    )
    return re.findall(r"[a-z]+(?:'[a-z]+)?", normalized)


def meaningful_tokens(tokens: list[str]) -> set[str]:
    return {token for token in tokens if token not in STOPWORDS and len(token) > 1}


def jaccard_pct(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 100.0
    union = left | right
    if not union:
        return 0.0
    return round(len(left & right) / len(union) * 100, 2)


def text_excerpt(text: str, limit: int = 150) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def divine_renderings(text: str) -> list[str]:
    return sorted(label for label, pattern in DIVINE_PATTERNS.items() if pattern.search(text))


def divine_name_token_count(unit: dict[str, Any]) -> int:
    count = 0
    for token in unit.get("tokens", []):
        features = token.get("compiler_features", {})
        lemma = str(token.get("lemma", ""))
        normalized = str(token.get("normalized", ""))
        if features.get("divine_name") or lemma in {"יהוה", "אֱלֹהִים"}:
            count += 1
        elif normalized in {"יהוה", "אלהים", "אל", "עליון"}:
            count += 1
    return count


def witness_texts(unit: dict[str, Any]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for witness in unit.get("witnesses", []):
        source_id = str(witness.get("source_id", ""))
        if source_id in ENGLISH_WITNESS_SOURCES:
            texts[source_id] = str(witness.get("text", ""))
    return texts


def source_url_map(unit: dict[str, Any]) -> dict[str, str]:
    urls: dict[str, str] = {}
    for witness in unit.get("witnesses", []):
        source_id = str(witness.get("source_id", ""))
        if source_id in ENGLISH_WITNESS_SOURCES:
            urls[source_id] = str(witness.get("source_url", ""))
    return urls


def claim_lookup(claim_matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["unit_id"]): row
        for row in claim_matrix.get("unit_claim_rows", [])
        if row.get("unit_id")
    }


def pair_metrics(source_texts: dict[str, str]) -> tuple[list[dict[str, Any]], list[float]]:
    rows: list[dict[str, Any]] = []
    overlaps: list[float] = []
    for source_a, source_b in combinations(ENGLISH_WITNESS_SOURCES, 2):
        text_a = source_texts.get(source_a, "")
        text_b = source_texts.get(source_b, "")
        if not text_a or not text_b:
            continue
        tokens_a = normalize_tokens(text_a)
        tokens_b = normalize_tokens(text_b)
        terms_a = meaningful_tokens(tokens_a)
        terms_b = meaningful_tokens(tokens_b)
        overlap = jaccard_pct(terms_a, terms_b)
        rows.append(
            {
                "source_a": source_a,
                "source_b": source_b,
                "token_count_a": len(tokens_a),
                "token_count_b": len(tokens_b),
                "meaningful_token_count_a": len(terms_a),
                "meaningful_token_count_b": len(terms_b),
                "meaningful_jaccard_pct": overlap,
                "divergence_pct": round(100.0 - overlap, 2),
                "source_a_only_terms": sorted(terms_a - terms_b)[:18],
                "source_b_only_terms": sorted(terms_b - terms_a)[:18],
            }
        )
        overlaps.append(overlap)
    return rows, overlaps


def unit_marker_flags(
    *,
    source_texts: dict[str, str],
    pair_rows: list[dict[str, Any]],
    length_spread_pct: float,
    divine_count: int,
) -> list[str]:
    flags = []
    if (
        pair_rows
        and mean([float(row["divergence_pct"]) for row in pair_rows]) >= HIGH_DIVERGENCE_THRESHOLD
    ):
        flags.append("high_english_witness_divergence")
    if length_spread_pct >= 45:
        flags.append("large_witness_length_spread")
    if sum(text.count("[") for text in source_texts.values()) > 0:
        flags.append("bracketed_expansion_present")
    archaic_count = sum(
        1
        for text in source_texts.values()
        for token in normalize_tokens(text)
        if token in ARCHAIC_TERMS or token.endswith("eth")
    )
    if archaic_count:
        flags.append("archaic_register_pressure")
    profiles = {source: tuple(divine_renderings(text)) for source, text in source_texts.items()}
    nonempty_profiles = {profile for profile in profiles.values() if profile}
    if divine_count and len(nonempty_profiles) > 1:
        flags.append("divine_name_rendering_disagreement")
    if len(source_texts) < len(ENGLISH_WITNESS_SOURCES):
        flags.append("missing_english_witness")
    return flags


def unit_priority_score(
    *,
    divergence_pct: float,
    length_spread_pct: float,
    single_source_term_pct: float,
    marker_flags: list[str],
    claim: dict[str, Any],
) -> float:
    score = divergence_pct * 0.85
    score += min(80.0, length_spread_pct) * 0.25
    score += min(80.0, single_source_term_pct) * 0.25
    if "divine_name_rendering_disagreement" in marker_flags:
        score += 24.0
    if "bracketed_expansion_present" in marker_flags:
        score += 9.0
    if "archaic_register_pressure" in marker_flags:
        score += 7.0
    if "large_witness_length_spread" in marker_flags:
        score += 10.0
    if claim.get("textual_witness_pressure"):
        score += 14.0
    if claim.get("reception_sensitive"):
        score += 12.0
    if claim.get("theology_pressure"):
        score += 8.0
    score += min(30.0, float(claim.get("claim_risk_score") or 0) / 8.0)
    return round(score, 2)


def build_unit_row(unit: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any]:
    source_texts = witness_texts(unit)
    urls = source_url_map(unit)
    pair_rows, overlaps = pair_metrics(source_texts)
    token_counts = {source: len(normalize_tokens(text)) for source, text in source_texts.items()}
    lengths = list(token_counts.values())
    average_length = mean([float(value) for value in lengths])
    length_spread_pct = (
        round((max(lengths) - min(lengths)) / average_length * 100, 2)
        if lengths and average_length
        else 0.0
    )

    all_meaningful_terms: list[str] = []
    terms_by_source = {
        source: meaningful_tokens(normalize_tokens(text)) for source, text in source_texts.items()
    }
    for terms in terms_by_source.values():
        all_meaningful_terms.extend(terms)
    term_counts = Counter(all_meaningful_terms)
    single_source_terms = sorted(term for term, count in term_counts.items() if count == 1)
    single_source_term_pct = pct(len(single_source_terms), len(term_counts))

    divergence_pct = round(100.0 - mean(overlaps), 2) if overlaps else 0.0
    divine_count = divine_name_token_count(unit)
    marker_flags = unit_marker_flags(
        source_texts=source_texts,
        pair_rows=pair_rows,
        length_spread_pct=length_spread_pct,
        divine_count=divine_count,
    )
    source_profiles = {source: divine_renderings(text) for source, text in source_texts.items()}
    priority_score = unit_priority_score(
        divergence_pct=divergence_pct,
        length_spread_pct=length_spread_pct,
        single_source_term_pct=single_source_term_pct,
        marker_flags=marker_flags,
        claim=claim,
    )

    return {
        "unit_id": unit["unit_id"],
        "ref": unit.get("ref", ""),
        "psalm_id": unit["psalm_id"],
        "english_witness_count": len(source_texts),
        "complete_english_witness_set": len(source_texts) == len(ENGLISH_WITNESS_SOURCES),
        "missing_english_witness_sources": [
            source for source in ENGLISH_WITNESS_SOURCES if source not in source_texts
        ],
        "mean_english_witness_overlap_pct": mean(overlaps),
        "mean_english_witness_divergence_pct": divergence_pct,
        "length_spread_pct": length_spread_pct,
        "single_source_meaningful_term_count": len(single_source_terms),
        "single_source_meaningful_term_pct": single_source_term_pct,
        "divine_name_token_count": divine_count,
        "divine_rendering_profiles": source_profiles,
        "marker_flags": marker_flags,
        "marker_count": len(marker_flags),
        "claim_risk_score": claim.get("claim_risk_score", 0),
        "claim_risk_band": claim.get("claim_risk_band", ""),
        "reception_sensitive": bool(claim.get("reception_sensitive")),
        "textual_witness_pressure": bool(claim.get("textual_witness_pressure")),
        "theology_pressure": bool(claim.get("theology_pressure")),
        "ancient_culture_pressure": bool(claim.get("ancient_culture_pressure")),
        "required_frames": claim.get("required_frames", []),
        "priority_score": priority_score,
        "kjv_token_count": token_counts.get("kjv", 0),
        "asv_token_count": token_counts.get("asv", 0),
        "web_token_count": token_counts.get("web", 0),
        "kjv_excerpt": text_excerpt(source_texts.get("kjv", "")),
        "asv_excerpt": text_excerpt(source_texts.get("asv", "")),
        "web_excerpt": text_excerpt(source_texts.get("web", "")),
        "source_urls": urls,
        "pair_rows": pair_rows,
    }


def build_unit_rows(content_root: Path, claims: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(content_root.glob("ps*/*.v*.json")):
        unit = load_json(path)
        rows.append(build_unit_row(unit, claims.get(str(unit["unit_id"]), {})))
    return rows


def build_pair_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for unit in unit_rows:
        for pair in unit["pair_rows"]:
            grouped[(pair["source_a"], pair["source_b"])].append(pair)

    rows = []
    for (source_a, source_b), pairs in sorted(grouped.items()):
        divergence_values = [float(pair["divergence_pct"]) for pair in pairs]
        length_delta_values = [
            abs(float(pair["token_count_a"]) - float(pair["token_count_b"])) for pair in pairs
        ]
        rows.append(
            {
                "source_pair": f"{source_a}:{source_b}",
                "source_a": source_a,
                "source_b": source_b,
                "unit_count": len(pairs),
                "mean_divergence_pct": mean(divergence_values),
                "median_divergence_pct": percentile(divergence_values, 50),
                "p90_divergence_pct": percentile(divergence_values, 90),
                "max_divergence_pct": max(divergence_values) if divergence_values else 0.0,
                "mean_token_delta": mean(length_delta_values),
                "high_divergence_unit_count": sum(
                    1 for value in divergence_values if value >= HIGH_DIVERGENCE_THRESHOLD
                ),
            }
        )
    return sorted(rows, key=lambda row: float(row["mean_divergence_pct"]), reverse=True)


def percentile(values: list[float], percentile_value: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * percentile_value / 100
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return round(sorted_values[int(index)], 2)
    weight = index - lower
    return round(sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight, 2)


def build_marker_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for unit in unit_rows:
        counts.update(unit["marker_flags"])
    return [
        {
            "marker": marker,
            "unit_count": count,
            "unit_pct": pct(count, len(unit_rows)),
        }
        for marker, count in counts.most_common()
    ]


def build_psalm_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in unit_rows:
        grouped[str(unit["psalm_id"])].append(unit)
    rows = []
    for psalm_id, rows_for_psalm in grouped.items():
        sorted_priority = sorted(
            rows_for_psalm,
            key=lambda row: float(row["priority_score"]),
            reverse=True,
        )
        rows.append(
            {
                "psalm_id": psalm_id,
                "unit_count": len(rows_for_psalm),
                "complete_english_witness_unit_count": sum(
                    1 for row in rows_for_psalm if row["complete_english_witness_set"]
                ),
                "mean_divergence_pct": mean(
                    [float(row["mean_english_witness_divergence_pct"]) for row in rows_for_psalm]
                ),
                "high_divergence_unit_count": sum(
                    1
                    for row in rows_for_psalm
                    if float(row["mean_english_witness_divergence_pct"])
                    >= HIGH_DIVERGENCE_THRESHOLD
                ),
                "divine_name_disagreement_unit_count": sum(
                    1
                    for row in rows_for_psalm
                    if "divine_name_rendering_disagreement" in row["marker_flags"]
                ),
                "mean_priority_score": mean(
                    [float(row["priority_score"]) for row in rows_for_psalm]
                ),
                "top_unit_id": sorted_priority[0]["unit_id"],
                "top_ref": sorted_priority[0]["ref"],
                "top_priority_score": sorted_priority[0]["priority_score"],
            }
        )
    return sorted(rows, key=lambda row: float(row["mean_priority_score"]), reverse=True)


def flatten_unit_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for row in unit_rows:
        flattened.append(
            {
                key: value
                for key, value in row.items()
                if key not in {"pair_rows", "source_urls", "divine_rendering_profiles"}
            }
            | {
                "divine_rendering_profiles": row["divine_rendering_profiles"],
                "source_urls": row["source_urls"],
            }
        )
    return flattened


def priority_rows(unit_rows: list[dict[str, Any]], limit: int = 75) -> list[dict[str, Any]]:
    rows = sorted(unit_rows, key=lambda row: float(row["priority_score"]), reverse=True)
    return [
        {
            "rank": index + 1,
            "unit_id": row["unit_id"],
            "ref": row["ref"],
            "priority_score": row["priority_score"],
            "mean_divergence_pct": row["mean_english_witness_divergence_pct"],
            "length_spread_pct": row["length_spread_pct"],
            "single_source_meaningful_term_pct": row["single_source_meaningful_term_pct"],
            "marker_flags": row["marker_flags"],
            "claim_risk_score": row["claim_risk_score"],
            "reception_sensitive": row["reception_sensitive"],
            "textual_witness_pressure": row["textual_witness_pressure"],
            "required_frames": row["required_frames"],
            "kjv_excerpt": row["kjv_excerpt"],
            "asv_excerpt": row["asv_excerpt"],
            "web_excerpt": row["web_excerpt"],
        }
        for index, row in enumerate(rows[:limit])
    ]


def chart_rows(rows: list[dict[str, Any]], label_key: str, value_key: str) -> list[dict[str, Any]]:
    return [
        {
            "label": str(row[label_key]),
            "value": row[value_key],
        }
        for row in rows
    ]


def build_report() -> dict[str, Any]:
    claim_matrix = maybe_load_json(CLAIM_MATRIX_PATH)
    witness_readiness = maybe_load_json(WITNESS_READINESS_PATH)
    claims = claim_lookup(claim_matrix)
    unit_rows = build_unit_rows(CONTENT_ROOT, claims)
    pair_rows = build_pair_rows(unit_rows)
    marker_rows = build_marker_rows(unit_rows)
    psalm_rows = build_psalm_rows(unit_rows)
    priority = priority_rows(unit_rows)

    complete_rows = [row for row in unit_rows if row["complete_english_witness_set"]]
    divergence_values = [float(row["mean_english_witness_divergence_pct"]) for row in complete_rows]
    high_divergence_rows = [
        row
        for row in complete_rows
        if float(row["mean_english_witness_divergence_pct"]) >= HIGH_DIVERGENCE_THRESHOLD
    ]
    high_priority_rows = [
        row for row in priority if float(row["priority_score"]) >= HIGH_PRIORITY_THRESHOLD
    ]
    divine_disagreement_rows = [
        row for row in unit_rows if "divine_name_rendering_disagreement" in row["marker_flags"]
    ]
    archaic_rows = [row for row in unit_rows if "archaic_register_pressure" in row["marker_flags"]]
    bracket_rows = [
        row for row in unit_rows if "bracketed_expansion_present" in row["marker_flags"]
    ]

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "witness divergence generated; witnesses are not generation sources",
        "source_paths": {
            "content_root": "content/psalms",
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
            "witness_readiness": str(WITNESS_READINESS_PATH.relative_to(ROOT)),
        },
        "method": {
            "english_witness_sources": ENGLISH_WITNESS_SOURCES,
            "overlap_metric": (
                "Mean pairwise Jaccard overlap over normalized, non-stopword English tokens."
            ),
            "divergence_metric": "100 minus mean English witness overlap.",
            "authority_boundary": (
                "English witnesses are comparison evidence and never direct generation basis."
            ),
            "priority_score": (
                "Weighted witness divergence, length spread, single-source terms, marker flags, "
                "and existing claim-matrix pressure."
            ),
        },
        "summary": {
            "unit_count": len(unit_rows),
            "complete_english_witness_unit_count": len(complete_rows),
            "complete_english_witness_unit_pct": pct(len(complete_rows), len(unit_rows)),
            "mean_english_witness_divergence_pct": mean(divergence_values),
            "median_english_witness_divergence_pct": percentile(divergence_values, 50),
            "p90_english_witness_divergence_pct": percentile(divergence_values, 90),
            "high_divergence_unit_count": len(high_divergence_rows),
            "high_divergence_unit_pct": pct(len(high_divergence_rows), len(complete_rows)),
            "high_priority_unit_count": len(high_priority_rows),
            "divine_name_disagreement_unit_count": len(divine_disagreement_rows),
            "archaic_register_pressure_unit_count": len(archaic_rows),
            "bracketed_expansion_unit_count": len(bracket_rows),
            "claim_matrix_unit_count": len(claims),
            "witness_readiness_record_count": witness_readiness.get("summary", {}).get(
                "witness_record_count", 0
            ),
            "source_pair_count": len(pair_rows),
            "marker_type_count": len(marker_rows),
            "psalm_count": len(psalm_rows),
            "top_priority_unit": priority[0]["unit_id"] if priority else "",
            "top_priority_ref": priority[0]["ref"] if priority else "",
            "top_priority_score": priority[0]["priority_score"] if priority else 0.0,
            "top_priority_markers": priority[0]["marker_flags"] if priority else [],
            "status": "generated_not_authority",
        },
        "unit_rows": flatten_unit_rows(unit_rows),
        "source_pair_rows": pair_rows,
        "marker_rows": marker_rows,
        "psalm_rows": psalm_rows,
        "priority_rows": priority,
        "visual_data": {
            "source_pair_divergence": chart_rows(
                pair_rows,
                "source_pair",
                "mean_divergence_pct",
            ),
            "marker_counts": chart_rows(marker_rows, "marker", "unit_count"),
            "top_psalm_priority": chart_rows(
                psalm_rows[:20],
                "psalm_id",
                "mean_priority_score",
            ),
            "top_unit_priority": chart_rows(priority[:20], "ref", "priority_score"),
        },
    }


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    width: int = 980,
    limit: int = 20,
) -> str:
    rows = rows[:limit]
    row_h = 29
    left = 285
    right = 90
    top = 24
    height = top * 2 + row_h * max(1, len(rows))
    max_value = max((float(row.get(value_key) or 0) for row in rows), default=1.0)
    chart_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, row in enumerate(rows):
        value = float(row.get(value_key) or 0)
        y = top + index * row_h
        bar_w = chart_w * value / max_value if max_value else 0.0
        parts.append(
            f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row.get(label_key, ""))}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="18" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 18}" font-size="12" '
            f'font-weight="700" fill="#24313a">{value:g}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def metric_cards(cards: list[tuple[str, str, str]]) -> str:
    return (
        '<div class="metric-grid">'
        + "".join(
            f"""
            <article class="metric-card">
              <h3>{esc(label)}</h3>
              <p class="metric-value">{esc(value)}</p>
              <p>{esc(note)}</p>
            </article>
            """
            for label, value, note in cards
        )
        + "</div>"
    )


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    priority_rows_html = [
        [
            row["rank"],
            row["ref"],
            row["priority_score"],
            f"{row['mean_divergence_pct']:.2f}%",
            f"{row['length_spread_pct']:.2f}%",
            ", ".join(row["marker_flags"]),
            row["kjv_excerpt"],
            row["asv_excerpt"],
            row["web_excerpt"],
        ]
        for row in report["priority_rows"][:35]
    ]
    pair_rows_html = [
        [
            row["source_pair"],
            f"{row['mean_divergence_pct']:.2f}%",
            f"{row['median_divergence_pct']:.2f}%",
            f"{row['p90_divergence_pct']:.2f}%",
            row["high_divergence_unit_count"],
            f"{row['mean_token_delta']:.2f}",
        ]
        for row in report["source_pair_rows"]
    ]
    marker_rows_html = [
        [row["marker"], row["unit_count"], f"{row['unit_pct']:.2f}%"]
        for row in report["marker_rows"]
    ]
    psalm_rows_html = [
        [
            row["psalm_id"],
            row["unit_count"],
            f"{row['mean_divergence_pct']:.2f}%",
            row["high_divergence_unit_count"],
            row["divine_name_disagreement_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["psalm_rows"][:35]
    ]
    visual = report["visual_data"]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Witness Divergence Report</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #53616f;
      --line: #c9d1d9;
      --panel: #f8fafc;
      --accent: #2f6f73;
      --accent-2: #7c5b2f;
      --warn: #a12727;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #fff;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 1260px;
      margin: 0 auto;
      padding: 34px 24px 58px;
    }}
    h1, h2, h3 {{
      line-height: 1.15;
      margin: 0;
    }}
    h1 {{
      font-size: 2.15rem;
      max-width: 980px;
    }}
    h2 {{
      margin-top: 36px;
      font-size: 1.45rem;
    }}
    h3 {{
      color: var(--muted);
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    p {{
      color: var(--muted);
      margin: 8px 0 0;
    }}
    .lede {{
      max-width: 980px;
      font-size: 1.05rem;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
      gap: 12px;
      margin-top: 24px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 16px;
    }}
    .metric-value {{
      color: var(--ink);
      font-size: 1.7rem;
      font-weight: 700;
      margin-top: 6px;
    }}
    .grid-2 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
      gap: 20px;
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 0.84rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f4f7fa;
      color: var(--muted);
    }}
    svg {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .callout {{
      border-left: 4px solid var(--warn);
      background: #fff7f5;
      padding: 12px 16px;
      margin-top: 20px;
    }}
    .callout strong {{
      color: var(--warn);
    }}
    footer {{
      margin-top: 32px;
      color: var(--muted);
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>
<main>
  <h1>English Witness Divergence and Translation-Risk Report</h1>
  <p class="lede">
    This report compares the KJV, ASV, and WEB English witness texts already
    attached to Psalm units. It quantifies lexical overlap, length spread,
    single-source wording, divine-name rendering variation, archaic register,
    and bracketed expansion pressure, then cross-references current
    claim-matrix risk for review routing.
  </p>
  <div class="callout">
    <strong>Authority boundary:</strong>
    {esc(report["method"]["authority_boundary"])}
  </div>

  {
        metric_cards(
            [
                (
                    "Units",
                    fmt_int(summary["unit_count"]),
                    (
                        f"{fmt_pct(summary['complete_english_witness_unit_pct'])} "
                        "complete English set."
                    ),
                ),
                (
                    "Mean Divergence",
                    fmt_pct(summary["mean_english_witness_divergence_pct"]),
                    f"P90 {fmt_pct(summary['p90_english_witness_divergence_pct'])}.",
                ),
                (
                    "High Divergence",
                    fmt_int(summary["high_divergence_unit_count"]),
                    f"{fmt_pct(summary['high_divergence_unit_pct'])} of complete units.",
                ),
                (
                    "Divine Names",
                    fmt_int(summary["divine_name_disagreement_unit_count"]),
                    "Units with English divine-name rendering disagreement.",
                ),
                (
                    "Register Pressure",
                    fmt_int(summary["archaic_register_pressure_unit_count"]),
                    "Units containing archaic English witness forms.",
                ),
                (
                    "Top Unit",
                    summary["top_priority_ref"],
                    f"Priority score {summary['top_priority_score']:.2f}.",
                ),
            ]
        )
    }

  <section>
    <h2>Visual Divergence</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Source-Pair Divergence</h3>
        {
        svg_horizontal_bars(
            visual["source_pair_divergence"],
            label_key="label",
            value_key="value",
            aria_label="Mean English witness divergence by source pair",
            color="#2f6f73",
        )
    }
      </div>
      <div class="panel">
        <h3>Marker Counts</h3>
        {
        svg_horizontal_bars(
            visual["marker_counts"],
            label_key="label",
            value_key="value",
            aria_label="Witness divergence marker counts",
            color="#7c5b2f",
        )
    }
      </div>
      <div class="panel">
        <h3>Top Psalm Priority</h3>
        {
        svg_horizontal_bars(
            visual["top_psalm_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top Psalms by witness divergence priority",
            color="#2f6f73",
        )
    }
      </div>
      <div class="panel">
        <h3>Top Unit Priority</h3>
        {
        svg_horizontal_bars(
            visual["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top units by witness divergence priority",
            color="#7c5b2f",
        )
    }
      </div>
    </div>
  </section>

  <section>
    <h2>Source Pair Metrics</h2>
    {
        table(
            ["Pair", "Mean Divergence", "Median", "P90", "High-Div Units", "Mean Token Delta"],
            pair_rows_html,
        )
    }
  </section>

  <section>
    <h2>Marker Counts</h2>
    {table(["Marker", "Unit Count", "Unit %"], marker_rows_html)}
  </section>

  <section>
    <h2>Highest Priority Units</h2>
    {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Divergence",
                "Length Spread",
                "Markers",
                "KJV Excerpt",
                "ASV Excerpt",
                "WEB Excerpt",
            ],
            priority_rows_html,
        )
    }
  </section>

  <section>
    <h2>Psalm Summary</h2>
    {
        table(
            [
                "Psalm",
                "Units",
                "Mean Divergence",
                "High-Div Units",
                "Divine Name Disagreement",
                "Mean Priority",
                "Top Ref",
            ],
            psalm_rows_html,
        )
    }
  </section>

  <footer>
    Generated {esc(report["generated_at"])} from current local unit JSON.
  </footer>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate English witness divergence report.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--pair-csv-output", type=Path, default=DEFAULT_PAIR_CSV_OUTPUT)
    parser.add_argument("--psalm-csv-output", type=Path, default=DEFAULT_PSALM_CSV_OUTPUT)
    parser.add_argument("--marker-csv-output", type=Path, default=DEFAULT_MARKER_CSV_OUTPUT)
    parser.add_argument(
        "--priority-csv-output",
        type=Path,
        default=DEFAULT_PRIORITY_CSV_OUTPUT,
    )
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.pair_csv_output, report["source_pair_rows"])
    write_csv(args.psalm_csv_output, report["psalm_rows"])
    write_csv(args.marker_csv_output, report["marker_rows"])
    write_csv(args.priority_csv_output, report["priority_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")


if __name__ == "__main__":
    main()
