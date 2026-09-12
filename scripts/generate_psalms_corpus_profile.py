from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = ROOT / "content" / "psalms"
SEED_PATH = ROOT / "docs" / "research" / "local_translation_benchmark_seed.json"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "psalms_corpus_profile.json"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "psalms_corpus_profile.html"

TOKEN_FIELDS = [
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
    "greek",
    "greek_strong",
    "display_gloss",
    "transliteration",
]

FEATURE_LABELS = {
    "divine_name": "Divine-name tokens",
    "construct_state": "Construct-state tokens",
    "suffix_pronoun": "Suffix-pronoun tokens",
    "preposition_role": "Preposition-role tokens",
    "discourse_marker": "Discourse-marker tokens",
    "temporal_pair_candidate": "Temporal-pair candidates",
    "multi_component": "Multi-component tokens",
}

PALETTE = [
    "#2f6f73",
    "#7c5b2f",
    "#58508d",
    "#9b3d3d",
    "#4f6f9f",
    "#6f7f3f",
    "#8b5e83",
]


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if value == "":
        return False
    if value == []:
        return False
    if value == {}:
        return False
    return True


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def round_mean(values: list[int]) -> float:
    if not values:
        return 0.0
    return round(mean(values), 2)


def round_median(values: list[int]) -> float:
    if not values:
        return 0.0
    return round(median(values), 2)


def counter_rows(
    counter: Counter[Any],
    *,
    total: int | None = None,
    limit: int | None = None,
    key_name: str = "key",
) -> list[dict[str, Any]]:
    items = counter.most_common(limit)
    denominator = total if total is not None else sum(counter.values())
    return [
        {
            key_name: key,
            "count": count,
            "pct": pct(count, denominator),
        }
        for key, count in items
    ]


def psalm_sort_key(psalm_id: str) -> tuple[int, str]:
    digits = "".join(ch for ch in psalm_id if ch.isdigit())
    if digits:
        return (int(digits), psalm_id)
    return (999, psalm_id)


def unit_sort_key(unit_id: str) -> tuple[int, int, str]:
    parts = unit_id.split(".")
    psalm = psalm_sort_key(parts[0])[0] if parts else 999
    verse = 999
    if len(parts) > 1:
        digits = "".join(ch for ch in parts[1] if ch.isdigit())
        if digits:
            verse = int(digits)
    return (psalm, verse, unit_id)


def bucket_token_count(token_count: int) -> str:
    if token_count <= 5:
        return "01-05"
    if token_count <= 10:
        return "06-10"
    if token_count <= 15:
        return "11-15"
    if token_count <= 20:
        return "16-20"
    if token_count <= 30:
        return "21-30"
    if token_count <= 40:
        return "31-40"
    return "41+"


def load_seed_units(seed_path: Path) -> dict[str, dict[str, Any]]:
    if not seed_path.exists():
        return {}
    data = load_json(seed_path)
    return {
        str(unit["unit_id"]): unit for unit in data.get("seed_units", []) if unit.get("unit_id")
    }


def scan_corpus(content_root: Path, seed_path: Path) -> dict[str, Any]:
    generated_on = datetime.now(UTC).date().isoformat()
    psalm_dirs = sorted(
        [path for path in content_root.glob("ps*") if path.is_dir()],
        key=lambda path: psalm_sort_key(path.name),
    )
    unit_files = sorted(
        content_root.glob("ps*/ps*.v*.json"),
        key=lambda path: unit_sort_key(path.stem),
    )
    seed_units = load_seed_units(seed_path)
    seed_ids = set(seed_units)

    total_tokens = 0
    units_with_renderings = 0
    status_counts: Counter[str] = Counter()
    unit_token_counts: list[int] = []
    token_bucket_counts: Counter[str] = Counter()
    psalm_stats: dict[str, Counter[str]] = defaultdict(Counter)
    token_field_presence: Counter[str] = Counter()
    provider_status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    provider_available_fields: dict[str, Counter[str]] = defaultdict(Counter)
    provider_missing_fields: dict[str, Counter[str]] = defaultdict(Counter)
    missing_enrichments: Counter[str] = Counter()
    feature_counts: Counter[str] = Counter()
    part_of_speech_counts: Counter[str] = Counter()
    stem_counts: Counter[str] = Counter()
    syntax_role_counts: Counter[str] = Counter()
    word_sense_counts: Counter[str] = Counter()
    lemma_counts: Counter[str] = Counter()
    strong_counts: Counter[str] = Counter()
    lemma_glosses: dict[str, Counter[str]] = defaultdict(Counter)
    witness_role_counts: Counter[str] = Counter()
    witness_source_counts: Counter[str] = Counter()
    witness_language_counts: Counter[str] = Counter()
    units_with_witnesses = 0
    witness_records = 0
    unit_rows: list[dict[str, Any]] = []

    for path in unit_files:
        data = load_json(path)
        unit_id = str(data.get("unit_id") or path.stem)
        psalm_id = str(data.get("psalm_id") or unit_id.split(".")[0])
        ref = str(data.get("ref") or unit_id)
        tokens = data.get("tokens") or []
        witnesses = data.get("witnesses") or []
        token_count = len(tokens)
        unit_feature_counts: Counter[str] = Counter()

        total_tokens += token_count
        unit_token_counts.append(token_count)
        token_bucket_counts[bucket_token_count(token_count)] += 1
        status_counts[str(data.get("status") or "unknown")] += 1
        psalm_stats[psalm_id]["units"] += 1
        psalm_stats[psalm_id]["tokens"] += token_count

        if data.get("renderings"):
            units_with_renderings += 1
        if witnesses:
            units_with_witnesses += 1
        witness_records += len(witnesses)

        for witness in witnesses:
            role = str(witness.get("witness_role") or "unknown")
            source = str(witness.get("source_id") or "unknown")
            language = str(witness.get("language") or "unknown")
            witness_role_counts[role] += 1
            witness_source_counts[source] += 1
            witness_language_counts[language] += 1

        for token in tokens:
            for field in TOKEN_FIELDS:
                if has_value(token.get(field)):
                    token_field_presence[field] += 1

            for provider, source in (token.get("enrichment_sources") or {}).items():
                status = str(source.get("status") or "unknown")
                provider_status_counts[str(provider)][status] += 1
                provider_available_fields[str(provider)].update(
                    str(field) for field in source.get("available_fields", [])
                )
                provider_missing_fields[str(provider)].update(
                    str(field) for field in source.get("missing_fields", [])
                )

            missing_enrichments.update(str(item) for item in token.get("missing_enrichments", []))

            features = token.get("compiler_features") or {}
            if features.get("divine_name") is True:
                feature_counts["divine_name"] += 1
                unit_feature_counts["divine_name"] += 1
            if features.get("construct_state") is True:
                feature_counts["construct_state"] += 1
                unit_feature_counts["construct_state"] += 1
            if features.get("temporal_pair_candidate") is True:
                feature_counts["temporal_pair_candidate"] += 1
                unit_feature_counts["temporal_pair_candidate"] += 1
            if has_value(features.get("suffix_pronoun")):
                feature_counts["suffix_pronoun"] += 1
                unit_feature_counts["suffix_pronoun"] += 1
            if has_value(features.get("preposition_role")):
                feature_counts["preposition_role"] += 1
                unit_feature_counts["preposition_role"] += 1
            if has_value(features.get("discourse_marker")):
                feature_counts["discourse_marker"] += 1
                unit_feature_counts["discourse_marker"] += 1
            if int(features.get("component_count") or 0) > 1:
                feature_counts["multi_component"] += 1
                unit_feature_counts["multi_component"] += 1

            for part in as_list(token.get("part_of_speech")):
                if has_value(part):
                    part_of_speech_counts[str(part)] += 1
            for stem in as_list(token.get("stem")):
                if has_value(stem):
                    stem_counts[str(stem)] += 1
            for role in as_list(token.get("syntax_role")):
                if has_value(role):
                    syntax_role_counts[str(role)] += 1
            for sense in as_list(token.get("word_sense")):
                if has_value(sense):
                    word_sense_counts[str(sense)] += 1

            lemma = token.get("lemma")
            if has_value(lemma):
                lemma_text = str(lemma)
                lemma_counts[lemma_text] += 1
                gloss = token.get("display_gloss")
                if has_value(gloss):
                    lemma_glosses[lemma_text][str(gloss)] += 1
            strong = token.get("strong")
            if has_value(strong):
                strong_counts[str(strong)] += 1

        feature_pressure = sum(unit_feature_counts.values())
        unit_rows.append(
            {
                "unit_id": unit_id,
                "ref": ref,
                "psalm_id": psalm_id,
                "token_count": token_count,
                "feature_pressure": feature_pressure,
                "feature_counts": dict(sorted(unit_feature_counts.items())),
                "witness_count": len(witnesses),
                "is_seed_unit": unit_id in seed_ids,
            }
        )

    psalm_rows = []
    for psalm_id, stats in sorted(psalm_stats.items(), key=lambda item: psalm_sort_key(item[0])):
        units = int(stats["units"])
        tokens = int(stats["tokens"])
        seed_count = sum(
            1 for unit in unit_rows if unit["psalm_id"] == psalm_id and unit["is_seed_unit"]
        )
        psalm_rows.append(
            {
                "psalm_id": psalm_id,
                "unit_count": units,
                "token_count": tokens,
                "avg_tokens_per_unit": round(tokens / units, 2) if units else 0.0,
                "seed_unit_count": seed_count,
            }
        )

    seed_token_count = sum(unit["token_count"] for unit in unit_rows if unit["unit_id"] in seed_ids)
    seed_tag_counts: Counter[str] = Counter()
    for seed in seed_units.values():
        seed_tag_counts.update(str(tag) for tag in seed.get("benchmark_tags", []))
    units_by_id = {str(unit["unit_id"]): unit for unit in unit_rows}
    seed_rows = []
    for seed_id in sorted(seed_ids, key=unit_sort_key):
        seed_manifest = seed_units[seed_id]
        unit = units_by_id.get(seed_id)
        seed_rows.append(
            {
                "unit_id": seed_id,
                "ref": str(seed_manifest.get("ref") or (unit or {}).get("ref") or ""),
                "token_count": int((unit or {}).get("token_count") or 0),
                "feature_pressure": int((unit or {}).get("feature_pressure") or 0),
                "benchmark_tags": list(seed_manifest.get("benchmark_tags", [])),
                "why_in_seed": str(seed_manifest.get("why_in_seed") or ""),
            }
        )

    top_lemmas = []
    for lemma, count in lemma_counts.most_common(30):
        top_lemmas.append(
            {
                "lemma": lemma,
                "count": count,
                "pct": pct(count, total_tokens),
                "representative_glosses": [
                    gloss for gloss, _ in lemma_glosses[lemma].most_common(3)
                ],
            }
        )

    field_coverage = []
    for field in TOKEN_FIELDS:
        present = token_field_presence[field]
        field_coverage.append(
            {
                "field": field,
                "present": present,
                "missing": total_tokens - present,
                "pct_present": pct(present, total_tokens),
            }
        )

    provider_coverage = {}
    for provider in sorted(provider_status_counts):
        provider_coverage[provider] = {
            "status_counts": dict(sorted(provider_status_counts[provider].items())),
            "available_field_counts": dict(sorted(provider_available_fields[provider].items())),
            "missing_field_counts": dict(sorted(provider_missing_fields[provider].items())),
        }

    feature_rows = []
    for key, count in feature_counts.most_common():
        feature_rows.append(
            {
                "feature": key,
                "label": FEATURE_LABELS.get(key, key),
                "count": count,
                "per_1000_tokens": round(count / total_tokens * 1000, 2) if total_tokens else 0.0,
            }
        )

    feature_dense_units = sorted(
        unit_rows,
        key=lambda unit: (
            int(unit["feature_pressure"]),
            int(unit["token_count"]),
            int(unit["witness_count"]),
        ),
        reverse=True,
    )
    expansion_candidates = [unit for unit in feature_dense_units if not unit["is_seed_unit"]][:40]

    return {
        "generated_on": generated_on,
        "status": "generated read-only corpus profile; not a benchmark result",
        "source_paths": {
            "content_root": "content/psalms",
            "seed_manifest": "docs/research/local_translation_benchmark_seed.json",
        },
        "summary": {
            "psalm_count": len(psalm_dirs),
            "unit_count": len(unit_files),
            "total_token_records": total_tokens,
            "units_with_renderings": units_with_renderings,
            "status_counts": dict(sorted(status_counts.items())),
            "unit_token_min": min(unit_token_counts) if unit_token_counts else 0,
            "unit_token_max": max(unit_token_counts) if unit_token_counts else 0,
            "unit_token_mean": round_mean(unit_token_counts),
            "unit_token_median": round_median(unit_token_counts),
            "witness_records": witness_records,
            "units_with_witnesses": units_with_witnesses,
        },
        "unit_token_distribution": {
            "buckets": counter_rows(token_bucket_counts, key_name="bucket"),
        },
        "per_psalm": psalm_rows,
        "top_psalms_by_tokens": sorted(
            psalm_rows,
            key=lambda row: (int(row["token_count"]), str(row["psalm_id"])),
            reverse=True,
        )[:20],
        "witnesses": {
            "role_counts": counter_rows(witness_role_counts, key_name="role"),
            "source_counts": counter_rows(witness_source_counts, key_name="source_id"),
            "language_counts": counter_rows(witness_language_counts, key_name="language"),
        },
        "enrichment": {
            "provider_coverage": provider_coverage,
            "missing_enrichment_counts": counter_rows(
                missing_enrichments,
                total=total_tokens,
                key_name="missing_key",
            ),
            "token_field_coverage": field_coverage,
        },
        "compiler_features": {
            "feature_counts": feature_rows,
            "feature_dense_units": feature_dense_units[:40],
        },
        "linguistic_counts": {
            "part_of_speech": counter_rows(
                part_of_speech_counts,
                total=total_tokens,
                key_name="part_of_speech",
            ),
            "stem": counter_rows(stem_counts, total=total_tokens, key_name="stem"),
            "syntax_role": counter_rows(
                syntax_role_counts,
                total=total_tokens,
                key_name="syntax_role",
            ),
            "word_sense": counter_rows(
                word_sense_counts,
                total=total_tokens,
                limit=30,
                key_name="word_sense",
            ),
            "top_lemmas": top_lemmas,
            "top_strong": counter_rows(
                strong_counts,
                total=total_tokens,
                limit=30,
                key_name="strong",
            ),
        },
        "benchmark_seed_coverage": {
            "seed_unit_count": len(seed_ids),
            "seed_token_count": seed_token_count,
            "pct_units_seeded": pct(len(seed_ids), len(unit_files)),
            "pct_tokens_seeded": pct(seed_token_count, total_tokens),
            "missing_seed_units": sorted(seed_ids - {unit["unit_id"] for unit in unit_rows}),
            "tag_counts": counter_rows(seed_tag_counts, key_name="tag"),
            "seed_units": seed_rows,
            "expansion_candidates": expansion_candidates,
        },
    }


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


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
    row_h = 28
    left = 220
    right = 48
    top = 24
    height = top * 2 + row_h * max(1, len(rows))
    max_value = max((float(row[value_key]) for row in rows), default=1.0)
    chart_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    if not rows:
        parts.append(
            f'<text x="{width / 2}" y="{height / 2}" text-anchor="middle" '
            'font-size="13" fill="#667581">No rows</text>'
        )
        parts.append("</svg>")
        return "".join(parts)
    for index, row in enumerate(rows):
        value = float(row[value_key])
        y = top + index * row_h
        bar_w = chart_w * value / max_value if max_value else 0
        parts.append(
            f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" font-size="12" '
            f'fill="#24313a">{esc(row[label_key])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="18" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 18}" font-size="12" '
            f'font-weight="700" fill="#24313a">{fmt_int(value)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def svg_unit_token_histogram(profile: dict[str, Any]) -> str:
    rows = profile["unit_token_distribution"]["buckets"]
    return svg_horizontal_bars(
        rows,
        label_key="bucket",
        value_key="count",
        aria_label="Unit token-count bucket distribution",
        color="#7c5b2f",
        limit=12,
    )


def metric_cards(cards: list[tuple[str, Any, str]]) -> str:
    return (
        '<div class="grid">'
        + "".join(
            '<div class="card">'
            f'<div class="metric">{esc(value)}</div>'
            f'<div class="label">{esc(label)}</div>'
            f"<p>{esc(note)}</p>"
            "</div>"
            for label, value, note in cards
        )
        + "</div>"
    )


def table(headers: list[str], rows: list[list[Any]], *, class_name: str = "") -> str:
    class_attr = f' class="{esc(class_name)}"' if class_name else ""
    body = []
    for row in rows:
        cells = []
        for cell in row:
            if str(cell).startswith("<"):
                cells.append(f"<td>{cell}</td>")
            else:
                cells.append(f"<td>{esc(cell)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        f"<table{class_attr}><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def provider_status_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    coverage = profile["enrichment"]["provider_coverage"]
    for provider, data in coverage.items():
        for status, count in data["status_counts"].items():
            rows.append({"provider_status": f"{provider}: {status}", "count": count})
    return sorted(rows, key=lambda row: int(row["count"]), reverse=True)


def feature_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    return profile["compiler_features"]["feature_counts"]


def render_html(profile: dict[str, Any]) -> str:
    summary = profile["summary"]
    enrichment = profile["enrichment"]
    linguistic = profile["linguistic_counts"]
    seed = profile["benchmark_seed_coverage"]
    generated = profile["generated_on"]
    semantic_role_coverage = field_coverage_pct(profile, "semantic_role")
    referent_coverage = field_coverage_pct(profile, "referent")

    field_rows = [
        [
            row["field"],
            fmt_int(row["present"]),
            fmt_int(row["missing"]),
            f"{row['pct_present']:.2f}%",
        ]
        for row in enrichment["token_field_coverage"]
    ]
    lemma_rows = [
        [
            row["lemma"],
            fmt_int(row["count"]),
            f"{row['pct']:.2f}%",
            ", ".join(row["representative_glosses"]),
        ]
        for row in linguistic["top_lemmas"][:20]
    ]
    candidate_rows = [
        [
            unit["unit_id"],
            unit["ref"],
            fmt_int(unit["token_count"]),
            fmt_int(unit["feature_pressure"]),
            ", ".join(f"{key}={value}" for key, value in unit["feature_counts"].items()),
        ]
        for unit in seed["expansion_candidates"][:25]
    ]
    seed_unit_rows = [
        [
            unit["unit_id"],
            unit["ref"],
            fmt_int(unit["token_count"]),
            fmt_int(unit["feature_pressure"]),
            ", ".join(unit["benchmark_tags"]),
            unit["why_in_seed"],
        ]
        for unit in seed["seed_units"]
    ]
    psalm_rows = [
        [
            row["psalm_id"],
            fmt_int(row["unit_count"]),
            fmt_int(row["token_count"]),
            f"{row['avg_tokens_per_unit']:.2f}",
            fmt_int(row["seed_unit_count"]),
        ]
        for row in profile["top_psalms_by_tokens"]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Psalms Corpus Profile</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2a33;
      --muted: #667581;
      --line: #d7dde2;
      --band: #f5f7f8;
      --accent: #2f6f73;
      --accent2: #7c5b2f;
      --warn: #9b3d3d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #ffffff;
      line-height: 1.48;
    }}
    header {{
      padding: 42px 54px 34px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #ffffff 0%, #f6f8f8 100%);
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 30px 34px 54px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    p {{ margin: 0 0 13px; }}
    .lede {{ max-width: 980px; font-size: 17px; color: #33414c; }}
    .meta {{ color: var(--muted); font-size: 13px; margin-top: 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
    .card {{ border: 1px solid var(--line); border-radius: 6px; padding: 16px; }}
    .metric {{ font-size: 30px; font-weight: 700; color: var(--accent); }}
    .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .05em;
    }}
    .note {{
      background: #fff8e9;
      border-left: 4px solid var(--accent2);
      padding: 13px 15px;
      margin: 18px 0;
    }}
    .warning {{
      background: #fff1f1;
      border-left: 4px solid var(--warn);
      padding: 13px 15px;
      margin: 18px 0;
    }}
    .chart {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 14px;
      margin: 16px 0;
      overflow-x: auto;
      background: #fff;
    }}
    svg {{ width: 100%; height: auto; display: block; }}
    table {{ border-collapse: collapse; width: 100%; margin: 14px 0 24px; font-size: 13px; }}
    th, td {{ border: 1px solid var(--line); padding: 9px 10px; vertical-align: top; }}
    th {{ background: var(--band); text-align: left; }}
    .num {{ text-align: right; white-space: nowrap; }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AlephTav Psalms Corpus Profile</h1>
    <p class="lede">
      A generated, read-only profile of the current Psalms corpus. This report
      quantifies token inventory, source-enrichment coverage, linguistic feature
      pressure, witnesses, and seed-benchmark coverage for local model planning.
    </p>
    <p class="meta">
      Generated {esc(generated)} from content/psalms and
      docs/research/local_translation_benchmark_seed.json.
    </p>
  </header>
  <main>
    <section>
      <h2>Corpus Inventory</h2>
      {
        metric_cards(
            [
                (
                    "Psalm directories",
                    fmt_int(summary["psalm_count"]),
                    "Canonical Psalm folders scanned.",
                ),
                (
                    "Verse/unit files",
                    fmt_int(summary["unit_count"]),
                    "Current source units available.",
                ),
                (
                    "Token records",
                    fmt_int(summary["total_token_records"]),
                    "Hebrew token rows available.",
                ),
                (
                    "Units with renderings",
                    fmt_int(summary["units_with_renderings"]),
                    "Reviewed English renderings present.",
                ),
            ]
        )
    }
      <div class="warning">
        <strong>Model implication:</strong> this is a source-packet corpus, not
        a completed English reference corpus. Benchmarking must score alignment,
        rationale, context use, and review readiness before reference matching.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            profile["top_psalms_by_tokens"],
            label_key="psalm_id",
            value_key="token_count",
            aria_label="Top Psalms by token count",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{svg_unit_token_histogram(profile)}</div>
      {table(["Psalm", "Units", "Tokens", "Avg tokens/unit", "Seed units"], psalm_rows)}
    </section>

    <section>
      <h2>Source Enrichment Coverage</h2>
      {
        metric_cards(
            [
                (
                    "Witness records",
                    fmt_int(summary["witness_records"]),
                    "Version-pinned witness records attached to units.",
                ),
                (
                    "Units with witnesses",
                    fmt_int(summary["units_with_witnesses"]),
                    "Units with at least one witness record.",
                ),
                (
                    "MACULA semantic role",
                    f"{semantic_role_coverage:.2f}%",
                    "Current token coverage for semantic_role.",
                ),
                (
                    "MACULA referent",
                    f"{referent_coverage:.2f}%",
                    "Current token coverage for referent.",
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            provider_status_rows(profile),
            label_key="provider_status",
            value_key="count",
            aria_label="Enrichment provider status counts",
            color="#58508d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            enrichment["missing_enrichment_counts"][:12],
            label_key="missing_key",
            value_key="count",
            aria_label="Missing enrichment key counts",
            color="#9b3d3d",
            limit=12,
        )
    }</div>
      {table(["Field", "Present", "Missing", "Coverage"], field_rows)}
    </section>

    <section>
      <h2>Linguistic Feature Pressure</h2>
      {
        metric_cards(
            [
                (
                    row["label"],
                    fmt_int(row["count"]),
                    f'''{row["per_1000_tokens"]:.2f} per 1,000 tokens.''',
                )
                for row in feature_rows(profile)[:4]
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            feature_rows(profile),
            label_key="label",
            value_key="count",
            aria_label="Compiler feature counts",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            linguistic["part_of_speech"][:16],
            label_key="part_of_speech",
            value_key="count",
            aria_label="Part of speech counts",
            color="#4f6f9f",
        )
    }</div>
      {table(["Lemma", "Count", "Share", "Representative glosses"], lemma_rows)}
    </section>

    <section>
      <h2>Benchmark Seed Coverage</h2>
      {
        metric_cards(
            [
                (
                    "Seed units",
                    fmt_int(seed["seed_unit_count"]),
                    "Real corpus units in the seed manifest.",
                ),
                (
                    "Seed tokens",
                    fmt_int(seed["seed_token_count"]),
                    "Tokens covered by the current seed.",
                ),
                (
                    "Unit coverage",
                    f'''{seed["pct_units_seeded"]:.2f}%''',
                    "Share of unit files covered.",
                ),
                (
                    "Token coverage",
                    f'''{seed["pct_tokens_seeded"]:.2f}%''',
                    "Share of token records covered.",
                ),
            ]
        )
    }
      <div class="note">
        The expansion candidates below are a heuristic queue based on feature
        density, token count, and witness availability. They are not a substitute
        for scholarly benchmark design, but they point to units likely to stress
        morphology, syntax, and interpretive handling.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            seed["tag_counts"],
            label_key="tag",
            value_key="count",
            aria_label="Benchmark seed tag counts",
            color="#2f6f73",
        )
    }</div>
      {
        table(
            [
                "Seed unit",
                "Reference",
                "Tokens",
                "Feature pressure",
                "Tags",
                "Benchmark reason",
            ],
            seed_unit_rows,
        )
    }
      {
        table(
            ["Candidate unit", "Reference", "Tokens", "Feature pressure", "Feature counts"],
            candidate_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def field_rows_data(profile: dict[str, Any], field: str) -> list[dict[str, Any]]:
    return [row for row in profile["enrichment"]["token_field_coverage"] if row["field"] == field]


def field_coverage_pct(profile: dict[str, Any], field: str) -> float:
    rows = field_rows_data(profile, field)
    if not rows:
        return 0.0
    return float(rows[0]["pct_present"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a read-only Psalms corpus profile report."
    )
    parser.add_argument(
        "--content-root",
        type=Path,
        default=CONTENT_ROOT,
        help="Path to content/psalms.",
    )
    parser.add_argument(
        "--seed-path",
        type=Path,
        default=SEED_PATH,
        help="Path to the benchmark seed manifest.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_OUTPUT,
        help="Path for generated profile JSON.",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        default=DEFAULT_HTML_OUTPUT,
        help="Path for generated profile HTML.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = scan_corpus(args.content_root, args.seed_path)
    write_json(args.json_output, profile)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(profile), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
