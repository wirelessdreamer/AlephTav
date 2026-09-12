from __future__ import annotations

import argparse
import csv
import html
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = ROOT / "content" / "psalms"
SEED_PATH = ROOT / "docs" / "research" / "local_translation_benchmark_seed.json"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "benchmark_100_expansion_plan.json"
DEFAULT_CSV_OUTPUT = ROOT / "reports" / "research" / "benchmark_100_expansion_plan.csv"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "benchmark_100_expansion_plan.html"

TARGET_STRATA = {
    "routine_lines": 40,
    "morphology_syntax_traps": 20,
    "poetic_parallelism_traps": 15,
    "textual_witness_cases": 10,
    "jewish_christian_reception_cases": 10,
    "license_provenance_adversarial_cases": 5,
}

RECEPTION_PSALMS = {
    "ps002",
    "ps008",
    "ps016",
    "ps022",
    "ps045",
    "ps069",
    "ps072",
    "ps089",
    "ps110",
    "ps118",
}

FAMILIAR_WITNESS_PSALMS = {
    "ps001",
    "ps023",
    "ps051",
    "ps091",
    "ps103",
    "ps121",
    "ps137",
    "ps150",
}

POETIC_TAGS = {
    "parallelism",
    "negative_parallelism",
    "source_image_pressure",
    "terse_poetry",
    "metaphor",
    "lament",
    "imprecation",
    "doxology",
    "repetition",
}

RECEPTION_TAGS = {
    "reception_history",
    "jewish_christian_reception",
    "messianic_interpretation",
    "canonical_intertext",
    "intertextuality",
}

TEXTUAL_TAGS = {
    "textual_witness",
    "textual_sensitivity",
    "lexical_dispute",
    "lexical_ambiguity",
}

LICENSE_TAGS = {
    "divine_name_policy",
    "pastoral_image",
    "liturgical_afterlife",
    "familiar_text_bias",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def psalm_sort_key(psalm_id: str) -> tuple[int, str]:
    digits = "".join(ch for ch in psalm_id if ch.isdigit())
    return (int(digits) if digits else 999, psalm_id)


def unit_sort_key(unit_id: str) -> tuple[int, int, str]:
    parts = unit_id.split(".")
    psalm = psalm_sort_key(parts[0])[0] if parts else 999
    verse = 999
    if len(parts) > 1:
        digits = "".join(ch for ch in parts[1] if ch.isdigit())
        if digits:
            verse = int(digits)
    return (psalm, verse, unit_id)


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


def token_features(token: dict[str, Any]) -> dict[str, Any]:
    return token.get("compiler_features") or {}


def unit_metrics(path: Path) -> dict[str, Any]:
    data = load_json(path)
    tokens = data.get("tokens") or []
    witnesses = data.get("witnesses") or []
    feature_counts: Counter[str] = Counter()
    pos_counts: Counter[str] = Counter()
    lemma_counts: Counter[str] = Counter()
    missing: Counter[str] = Counter()
    greek_count = 0
    greek_strong_count = 0

    for token in tokens:
        features = token_features(token)
        if features.get("construct_state") is True:
            feature_counts["construct_state"] += 1
        if features.get("divine_name") is True:
            feature_counts["divine_name"] += 1
        if features.get("temporal_pair_candidate") is True:
            feature_counts["temporal_pair_candidate"] += 1
        if has_value(features.get("suffix_pronoun")):
            feature_counts["suffix_pronoun"] += 1
        if has_value(features.get("preposition_role")):
            feature_counts["preposition_role"] += 1
        if has_value(features.get("discourse_marker")):
            feature_counts["discourse_marker"] += 1
        if int(features.get("component_count") or 0) > 1:
            feature_counts["multi_component"] += 1
        part = token.get("part_of_speech")
        if has_value(part):
            pos_counts[str(part)] += 1
        lemma = token.get("lemma")
        if has_value(lemma):
            lemma_counts[str(lemma)] += 1
        if has_value(token.get("greek")):
            greek_count += 1
        if has_value(token.get("greek_strong")):
            greek_strong_count += 1
        missing.update(str(item) for item in token.get("missing_enrichments", []))

    repeated_lemma_count = sum(1 for count in lemma_counts.values() if count > 1)
    token_count = len(tokens)
    witness_sources = sorted(
        str(witness.get("source_id") or "unknown")
        for witness in witnesses
        if witness.get("source_id")
    )
    unit_id = str(data.get("unit_id") or path.stem)
    psalm_id = str(data.get("psalm_id") or unit_id.split(".")[0])
    feature_pressure = sum(feature_counts.values())
    return {
        "unit_id": unit_id,
        "ref": data.get("ref") or unit_id,
        "psalm_id": psalm_id,
        "token_count": token_count,
        "feature_pressure": feature_pressure,
        "feature_counts": dict(sorted(feature_counts.items())),
        "part_of_speech_counts": dict(sorted(pos_counts.items())),
        "repeated_lemma_count": repeated_lemma_count,
        "missing_enrichment_counts": dict(sorted(missing.items())),
        "witness_count": len(witnesses),
        "witness_sources": witness_sources,
        "greek_token_count": greek_count,
        "greek_strong_token_count": greek_strong_count,
        "greek_coverage_pct": pct(greek_count, token_count),
        "english_witness_count": sum(1 for witness in witnesses if witness.get("language") == "en"),
        "lxx_witness_count": sum(1 for witness in witnesses if witness.get("source_id") == "lxx"),
    }


def load_units(content_root: Path) -> dict[str, dict[str, Any]]:
    rows = {}
    for path in sorted(content_root.glob("ps*/ps*.v*.json")):
        row = unit_metrics(path)
        rows[row["unit_id"]] = row
    return rows


def seed_primary_stratum(tags: list[str], psalm_id: str) -> str:
    tag_set = set(tags)
    if tag_set & LICENSE_TAGS:
        return "license_provenance_adversarial_cases"
    if tag_set & TEXTUAL_TAGS:
        return "textual_witness_cases"
    if tag_set & RECEPTION_TAGS or psalm_id in RECEPTION_PSALMS:
        return "jewish_christian_reception_cases"
    if tag_set & POETIC_TAGS:
        return "poetic_parallelism_traps"
    if tag_set & {"heart", "spirit", "sin_terms", "suffix_pronoun"}:
        return "morphology_syntax_traps"
    return "routine_lines"


def score_for_stratum(row: dict[str, Any], stratum: str) -> float:
    fc = row["feature_counts"]
    token_count = int(row["token_count"])
    feature_pressure = int(row["feature_pressure"])
    repeated = int(row["repeated_lemma_count"])
    psalm_id = row["psalm_id"]
    if stratum == "routine_lines":
        median_distance = abs(token_count - 7)
        return 100 - median_distance * 8 - feature_pressure * 1.5 + row["witness_count"] * 2
    if stratum == "morphology_syntax_traps":
        return (
            feature_pressure * 4
            + fc.get("construct_state", 0) * 5
            + fc.get("suffix_pronoun", 0) * 5
            + fc.get("preposition_role", 0) * 3
            + fc.get("temporal_pair_candidate", 0) * 8
            + fc.get("discourse_marker", 0) * 5
        )
    if stratum == "poetic_parallelism_traps":
        length_pressure = 12 if token_count <= 5 or token_count >= 12 else 0
        return (
            repeated * 15
            + length_pressure
            + fc.get("discourse_marker", 0) * 8
            + fc.get("divine_name", 0) * 2
            + feature_pressure * 1.5
        )
    if stratum == "textual_witness_cases":
        missing_greek = max(0, token_count - int(row["greek_token_count"]))
        return (
            row["witness_count"] * 12
            + row["lxx_witness_count"] * 15
            + row["english_witness_count"] * 4
            + missing_greek * 3
            + abs(100 - float(row["greek_coverage_pct"])) * 0.2
        )
    if stratum == "jewish_christian_reception_cases":
        reception_bonus = 50 if psalm_id in RECEPTION_PSALMS else 0
        return (
            reception_bonus
            + fc.get("divine_name", 0) * 8
            + fc.get("construct_state", 0) * 2
            + feature_pressure
            + token_count * 0.5
        )
    if stratum == "license_provenance_adversarial_cases":
        familiar_bonus = 40 if psalm_id in FAMILIAR_WITNESS_PSALMS else 0
        return (
            familiar_bonus
            + row["english_witness_count"] * 12
            + row["lxx_witness_count"] * 8
            + fc.get("divine_name", 0) * 6
            + row["witness_count"] * 3
        )
    return 0.0


def candidate_reason(row: dict[str, Any], stratum: str) -> str:
    if stratum == "routine_lines":
        return (
            "Routine baseline candidate selected for ordinary unit length, "
            f"{row['token_count']} tokens, and feature pressure {row['feature_pressure']}."
        )
    if stratum == "morphology_syntax_traps":
        return (
            "Morphology/syntax candidate selected for feature pressure "
            f"{row['feature_pressure']} with features {row['feature_counts']}."
        )
    if stratum == "poetic_parallelism_traps":
        return (
            "Poetic candidate selected by repetition/length/form heuristics: "
            f"{row['repeated_lemma_count']} repeated lemmas, {row['token_count']} tokens."
        )
    if stratum == "textual_witness_cases":
        return (
            "Witness candidate selected for multi-witness coverage and LXX/English "
            f"witness presence: sources {', '.join(row['witness_sources'])}."
        )
    if stratum == "jewish_christian_reception_cases":
        return (
            "Reception-history candidate selected by known high-reception Psalm class "
            f"or divine/royal feature pressure in {row['psalm_id']}."
        )
    return (
        "License/provenance adversarial candidate selected for familiar witness "
        "exposure and risk of unlicensed witness-style leakage."
    )


def stratum_tags(stratum: str) -> list[str]:
    return {
        "routine_lines": ["routine_baseline"],
        "morphology_syntax_traps": ["morphology_syntax_trap"],
        "poetic_parallelism_traps": ["poetic_parallelism_trap"],
        "textual_witness_cases": ["textual_witness_case"],
        "jewish_christian_reception_cases": ["reception_history_case"],
        "license_provenance_adversarial_cases": ["license_provenance_adversarial"],
    }[stratum]


def max_per_psalm(psalm_id: str) -> int:
    if psalm_id == "ps119":
        return 5
    return 3


def add_selected(
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    psalm_counts: Counter[str],
    row: dict[str, Any],
    *,
    stratum: str,
    source: str,
    tags: list[str],
    why: str,
    score: float,
) -> None:
    selected_ids.add(row["unit_id"])
    psalm_counts[row["psalm_id"]] += 1
    selected.append(
        {
            "unit_id": row["unit_id"],
            "ref": row["ref"],
            "psalm_id": row["psalm_id"],
            "primary_stratum": stratum,
            "source": source,
            "token_count": row["token_count"],
            "feature_pressure": row["feature_pressure"],
            "feature_counts": row["feature_counts"],
            "witness_count": row["witness_count"],
            "greek_coverage_pct": row["greek_coverage_pct"],
            "benchmark_tags": tags,
            "selection_score": round(score, 2),
            "selection_reason": why,
        }
    )


def build_plan(content_root: Path, seed_path: Path) -> dict[str, Any]:
    units = load_units(content_root)
    seed = load_json(seed_path)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    psalm_counts: Counter[str] = Counter()
    stratum_counts: Counter[str] = Counter()

    for seed_unit in seed["seed_units"]:
        unit_id = seed_unit["unit_id"]
        row = units[unit_id]
        tags = list(seed_unit.get("benchmark_tags", []))
        stratum = seed_primary_stratum(tags, row["psalm_id"])
        add_selected(
            selected,
            selected_ids,
            psalm_counts,
            row,
            stratum=stratum,
            source="existing_seed",
            tags=tags,
            why=seed_unit["why_in_seed"],
            score=score_for_stratum(row, stratum),
        )
        stratum_counts[stratum] += 1

    for stratum, target_count in TARGET_STRATA.items():
        attempts = 0
        while stratum_counts[stratum] < target_count:
            attempts += 1
            relax_diversity = attempts > 3
            candidates = []
            for row in units.values():
                if row["unit_id"] in selected_ids:
                    continue
                over_psalm_limit = psalm_counts[row["psalm_id"]] >= max_per_psalm(row["psalm_id"])
                if not relax_diversity and over_psalm_limit:
                    continue
                score = score_for_stratum(row, stratum)
                candidates.append((score, row))
            if not candidates:
                raise RuntimeError(f"Could not fill stratum {stratum}")
            score, row = max(
                candidates,
                key=lambda item: (
                    item[0],
                    -unit_sort_key(item[1]["unit_id"])[0],
                    item[1]["unit_id"],
                ),
            )
            add_selected(
                selected,
                selected_ids,
                psalm_counts,
                row,
                stratum=stratum,
                source="generated_expansion",
                tags=stratum_tags(stratum),
                why=candidate_reason(row, stratum),
                score=score,
            )
            stratum_counts[stratum] += 1

    selected.sort(
        key=lambda row: (
            list(TARGET_STRATA).index(row["primary_stratum"]),
            unit_sort_key(row["unit_id"]),
        )
    )
    for index, row in enumerate(selected, start=1):
        row["plan_index"] = index

    token_counts = [int(row["token_count"]) for row in selected]
    feature_pressures = [int(row["feature_pressure"]) for row in selected]
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated 100-unit benchmark expansion plan; not reviewed content",
        "source_paths": {
            "content_root": "content/psalms",
            "seed_manifest": "docs/research/local_translation_benchmark_seed.json",
        },
        "target": {
            "unit_count": 100,
            "strata": TARGET_STRATA,
        },
        "summary": {
            "selected_unit_count": len(selected),
            "existing_seed_units": sum(1 for row in selected if row["source"] == "existing_seed"),
            "generated_expansion_units": sum(
                1 for row in selected if row["source"] == "generated_expansion"
            ),
            "distinct_psalms": len({row["psalm_id"] for row in selected}),
            "total_token_count": sum(token_counts),
            "token_count_mean": round(statistics.mean(token_counts), 2),
            "token_count_median": round(statistics.median(token_counts), 2),
            "feature_pressure_mean": round(statistics.mean(feature_pressures), 2),
            "stratum_counts": dict(stratum_counts),
            "psalm_counts": dict(
                sorted(psalm_counts.items(), key=lambda item: psalm_sort_key(item[0]))
            ),
        },
        "selection_method": {
            "principles": [
                "Keep all current 23 seed units fixed.",
                "Fill the published 100-unit target strata from current corpus evidence.",
                (
                    "Use deterministic scores from token features, witnesses, "
                    "Psalm class, and seed tags."
                ),
                "Limit repeated Psalm concentration unless needed to fill the target.",
            ],
            "limitations": [
                "Generated expansion rows are heuristic candidates, not human-approved gold units.",
                (
                    "Reception and license strata use Psalm-class heuristics "
                    "and still need expert review."
                ),
                (
                    "Poetic structure is inferred from repetition/length proxies "
                    "until cola annotations exist."
                ),
            ],
        },
        "selected_units": selected,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "plan_index",
        "unit_id",
        "ref",
        "primary_stratum",
        "source",
        "token_count",
        "feature_pressure",
        "witness_count",
        "greek_coverage_pct",
        "selection_score",
        "benchmark_tags",
        "selection_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            output = {key: row.get(key, "") for key in fieldnames}
            output["benchmark_tags"] = ";".join(row.get("benchmark_tags", []))
            writer.writerow(output)


def counter_rows(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
    return [
        {label_key: key, "count": value}
        for key, value in sorted(counter.items(), key=lambda item: item[1], reverse=True)
    ]


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
    left = 290
    right = 60
    top = 24
    height = top * 2 + row_h * max(1, len(rows))
    max_value = max((float(row[value_key]) for row in rows), default=1.0)
    chart_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, row in enumerate(rows):
        value = float(row[value_key])
        y = top + index * row_h
        bar_w = chart_w * value / max_value if max_value else 0
        parts.append(
            f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row[label_key])}</text>'
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


def table(headers: list[str], rows: list[list[Any]]) -> str:
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>")
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_html(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    source_counts = Counter(row["source"] for row in plan["selected_units"])
    token_buckets: Counter[str] = Counter()
    for row in plan["selected_units"]:
        count = int(row["token_count"])
        if count <= 5:
            token_buckets["01-05"] += 1
        elif count <= 10:
            token_buckets["06-10"] += 1
        elif count <= 15:
            token_buckets["11-15"] += 1
        else:
            token_buckets["16+"] += 1

    rows = [
        [
            row["plan_index"],
            row["unit_id"],
            row["ref"],
            row["primary_stratum"],
            row["source"],
            row["token_count"],
            row["feature_pressure"],
            row["selection_reason"],
        ]
        for row in plan["selected_units"]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav 100-Unit Benchmark Expansion Plan</title>
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
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AlephTav 100-Unit Benchmark Expansion Plan</h1>
    <p class="lede">
      Deterministic expansion from the current 23-unit benchmark seed to a
      100-unit plan, using current corpus token features, witnesses, Psalm-class
      heuristics, and the published benchmark strata.
    </p>
    <p class="meta">Generated {esc(plan["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Plan Summary</h2>
      {
        metric_cards(
            [
                (
                    "Selected units",
                    fmt_int(summary["selected_unit_count"]),
                    "Target benchmark size.",
                ),
                (
                    "Existing seed",
                    fmt_int(summary["existing_seed_units"]),
                    "Current seed units retained.",
                ),
                (
                    "New candidates",
                    fmt_int(summary["generated_expansion_units"]),
                    "Generated expansion candidates.",
                ),
                (
                    "Distinct Psalms",
                    fmt_int(summary["distinct_psalms"]),
                    "Psalm coverage in the 100-unit plan.",
                ),
            ]
        )
    }
      <div class="warning">
        Expansion candidates are not reviewed gold data. They are a reproducible
        routing plan for expert benchmark curation.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(summary["stratum_counts"], "stratum"),
            label_key="stratum",
            value_key="count",
            aria_label="Benchmark expansion strata counts",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(dict(source_counts), "source"),
            label_key="source",
            value_key="count",
            aria_label="Existing seed versus generated expansion",
            color="#58508d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(dict(token_buckets), "bucket"),
            label_key="bucket",
            value_key="count",
            aria_label="Selected unit token-count buckets",
            color="#7c5b2f",
        )
    }</div>
    </section>

    <section>
      <h2>Selected Units</h2>
      {
        table(
            [
                "Index",
                "Unit",
                "Reference",
                "Stratum",
                "Source",
                "Tokens",
                "Feature pressure",
                "Selection reason",
            ],
            rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a 100-unit benchmark expansion plan.")
    parser.add_argument("--content-root", type=Path, default=CONTENT_ROOT)
    parser.add_argument("--seed", type=Path, default=SEED_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan = build_plan(args.content_root, args.seed)
    write_json(args.json_output, plan)
    write_csv(args.csv_output, plan["selected_units"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(plan), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
