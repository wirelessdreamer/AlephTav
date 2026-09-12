from __future__ import annotations

import argparse
import html
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from generate_local_model_benchmark_suite import (
    BENCHMARK_LAYERS,
    estimate_task_chars,
    task_rubric,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"
CONTENT_ROOT = ROOT / "content" / "psalms"
MODEL_DATA_PATH = ROOT / "docs" / "research" / "local_translation_model_data.json"
COVERAGE_PATH = REPORT_ROOT / "contextual_benchmark_coverage.json"
ATLAS_PATH = REPORT_ROOT / "contextual_pressure_atlas.json"
OUTPUT_SCHEMA_PATH = ROOT / "app" / "llm" / "contracts" / "generation_output.schema.json"
DEFAULT_JSON_OUTPUT = REPORT_ROOT / "contextual_gap_benchmark_supplement_suite.json"
DEFAULT_JSONL_OUTPUT = REPORT_ROOT / "contextual_gap_benchmark_supplement_tasks.jsonl"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "contextual_gap_benchmark_supplement_suite.html"

DEFAULT_LIMIT = 20
SUPPLEMENT_SEED_BASE = 2026061520


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def unit_path(unit_id: str) -> Path:
    psalm_id = unit_id.split(".")[0]
    return CONTENT_ROOT / psalm_id / f"{unit_id}.json"


def compact_task_token(token: dict[str, Any]) -> dict[str, Any]:
    features = token.get("compiler_features") or {}
    return {
        "token_id": token.get("token_id"),
        "surface": token.get("surface"),
        "normalized": token.get("normalized"),
        "lemma": token.get("lemma"),
        "strong": token.get("strong"),
        "morph_code": token.get("morph_code"),
        "morph_readable": token.get("morph_readable"),
        "display_gloss": token.get("display_gloss"),
        "word_sense": token.get("word_sense"),
        "part_of_speech": token.get("part_of_speech"),
        "stem": token.get("stem"),
        "syntax_role": token.get("syntax_role"),
        "semantic_role": token.get("semantic_role"),
        "referent": token.get("referent"),
        "psalms_occurrence_refs": token.get("psalms_occurrence_refs") or [],
        "corpus_occurrence_refs": token.get("corpus_occurrence_refs") or [],
        "greek": token.get("greek"),
        "missing_enrichments": token.get("missing_enrichments") or [],
        "compiler_features": {
            "component_count": features.get("component_count"),
            "construct_state": features.get("construct_state"),
            "divine_name": features.get("divine_name"),
            "suffix_pronoun": features.get("suffix_pronoun"),
            "preposition_role": features.get("preposition_role"),
            "discourse_marker": features.get("discourse_marker"),
            "conjunction_role": features.get("conjunction_role"),
            "english_parts": features.get("english_parts") or [],
            "gloss_fragments": features.get("gloss_fragments") or [],
        },
    }


def compact_witness(witness: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": witness.get("source_id"),
        "language": witness.get("language"),
        "witness_role": witness.get("witness_role"),
        "version_title": witness.get("versionTitle"),
        "source_version": witness.get("source_version"),
        "text": witness.get("text"),
    }


def derive_benchmark_tags(
    coverage_row: dict[str, Any],
    atlas_row: dict[str, Any],
) -> list[str]:
    domains = {str(domain) for domain in coverage_row.get("domains", [])}
    tags = {"contextual_gap", "coverage_gap_supplement"}
    primary_stratum = coverage_row.get("primary_stratum") or atlas_row.get("primary_stratum")
    if primary_stratum:
        tags.add(str(primary_stratum))
    if coverage_row.get("reception_sensitive"):
        tags.update({"reception_history", "jewish_christian_reception"})
    if "textual_witness_pressure" in domains:
        tags.add("textual_witness")
    if "divine_names_titles" in domains:
        tags.add("divine_name_policy")
    if "royal_kingship" in domains:
        tags.update({"royal_psalm", "messianic_interpretation"})
    if "lament_enemy_justice" in domains:
        tags.add("lament")
    if "anthropology_body" in domains:
        tags.add("anthropology")
    if "creation_cosmos" in domains:
        tags.add("creation_hymn")
    if "wisdom_torah" in domains:
        tags.add("wisdom")
    if "nations_zion_exile" in domains:
        tags.add("nations")
    if "covenant_mercy" in domains:
        tags.add("hesed")
    if "temple_cult_liturgy" in domains:
        tags.add("liturgical_afterlife")
    return sorted(tags)


def locked_inputs_for_unit(
    *,
    unit: dict[str, Any],
    coverage_row: dict[str, Any],
    atlas_row: dict[str, Any],
) -> dict[str, Any]:
    tokens = unit.get("tokens", [])
    return {
        "source": {
            "unit_id": unit["unit_id"],
            "ref": unit["ref"],
            "source_hebrew": unit["source_hebrew"],
            "source_transliteration": unit.get("source_transliteration"),
            "token_count": len(tokens),
            "tokens": [compact_task_token(token) for token in tokens],
        },
        "context": {
            "coverage_priority_rank": coverage_row.get("priority_rank"),
            "coverage_gap_score": coverage_row.get("coverage_gap_score"),
            "projected_gap_closure_source": "contextual_benchmark_coverage.next_unit_rows",
            "primary_stratum": coverage_row.get("primary_stratum"),
            "context_pressure_score": coverage_row.get("context_pressure_score"),
            "context_pressure_intensity": coverage_row.get("context_pressure_intensity"),
            "priority_score": coverage_row.get("priority_score"),
            "domain_count": coverage_row.get("domain_count"),
            "domains": coverage_row.get("domains", []),
            "domain_groups": coverage_row.get("domain_groups", []),
            "reception_sensitive": coverage_row.get("reception_sensitive"),
            "reception_label": atlas_row.get("reception_label"),
            "textual_witness_pressure": coverage_row.get("textual_witness_pressure"),
            "required_frames": coverage_row.get("required_frames", []),
            "review_roles": coverage_row.get("review_roles", []),
            "model_controls": atlas_row.get("model_controls", []),
            "surface_outside_context_pct": coverage_row.get("surface_outside_context_pct"),
            "outside_division_count": coverage_row.get("outside_division_count"),
            "outside_context_division_counts": atlas_row.get(
                "outside_context_division_counts",
                {},
            ),
            "top_context_tokens": atlas_row.get("top_context_tokens", []),
        },
        "witnesses": [compact_witness(witness) for witness in unit.get("witnesses", [])],
        "evidence_policy": {
            "canonical_basis": "UXLC/WLC-derived Hebrew source tokens",
            "witness_boundary": "Witnesses are evidence only, not canonical basis.",
            "context_boundary": (
                "Whole-Tanakh context here is normalized surface-form retrieval; "
                "do not present it as lemma-aware sense evidence."
            ),
            "reception_boundary": (
                "Jewish, Christian, academic, and liturgical reception claims "
                "must be tagged outside the translation string."
            ),
            "gap_boundary": (
                "This supplement closes contextual-atlas benchmark coverage gaps; "
                "it is not human signoff or canonical translation approval."
            ),
        },
    }


def task_for_layer(
    *,
    unit: dict[str, Any],
    coverage_row: dict[str, Any],
    atlas_row: dict[str, Any],
    layer_def: dict[str, Any],
    task_index: int,
) -> dict[str, Any]:
    layer = str(layer_def["layer"])
    task_id = f"bench.{unit['unit_id']}.{layer}"
    tags = derive_benchmark_tags(coverage_row, atlas_row)
    locked_inputs = locked_inputs_for_unit(
        unit=unit,
        coverage_row=coverage_row,
        atlas_row=atlas_row,
    )
    generation_input = {
        "unit_id": unit["unit_id"],
        "layer": layer,
        "locked_inputs": locked_inputs,
        "style_profile": layer_def["style_profile"],
        "candidate_count": 3,
        "seed": SUPPLEMENT_SEED_BASE + task_index,
        "model_profile_id": "{model_profile_id}",
    }
    benchmark = {
        "task_id": task_id,
        "prompt_file": layer_def["prompt_file"],
        "required_output_schema": "app/llm/contracts/generation_output.schema.json",
        "rubric": task_rubric(tags, layer),
        "must_check": [
            "JSON schema validity",
            "valid unit_id and layer",
            "valid token IDs in alignment_hints and preserved_source_images",
            "translation_basis uses Hebrew source unless explicitly testing LXX",
            "no reception-history claim inside the translation text",
            "no whole-Tanakh claim without cited context evidence",
            "witnesses labeled as witnesses, never as canonical Hebrew basis",
            "gap closure does not imply human signoff or canonical acceptance",
        ],
        "supplement_reason": (
            "Generated from contextual benchmark coverage gaps because this "
            "high-priority atlas unit lacked integrated gloss/literal tasks."
        ),
    }
    task = {
        "task_id": task_id,
        "unit_id": unit["unit_id"],
        "ref": unit["ref"],
        "layer": layer,
        "benchmark_tags": tags,
        "token_count": len(unit.get("tokens", [])),
        "outside_psalms_context_pct": coverage_row.get("surface_outside_context_pct", 0),
        "coverage_priority_rank": coverage_row.get("priority_rank"),
        "coverage_gap_score": coverage_row.get("coverage_gap_score", 0),
        "priority_score": coverage_row.get("priority_score", 0),
        "source_priority": "contextual_benchmark_coverage",
        "generation_input": generation_input,
        "benchmark": benchmark,
    }
    task["estimated_payload_chars"] = estimate_task_chars(generation_input, benchmark)
    return task


def selected_gap_rows(coverage: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    rows = [
        row
        for row in coverage.get("next_unit_rows", [])
        if not row.get("covered_by_integrated_benchmark")
    ]
    rows.sort(
        key=lambda row: (
            float(row.get("coverage_gap_score") or 0),
            float(row.get("priority_score") or 0),
        ),
        reverse=True,
    )
    return rows[:limit]


def make_tasks(
    *,
    coverage_rows: list[dict[str, Any]],
    atlas_rows_by_unit: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    tasks: list[dict[str, Any]] = []
    errors: list[str] = []
    task_index = 0
    layers_by_name = {str(layer["layer"]): layer for layer in BENCHMARK_LAYERS}
    for coverage_row in coverage_rows:
        unit_id = str(coverage_row["unit_id"])
        path = unit_path(unit_id)
        if not path.exists():
            errors.append(f"{unit_id}: missing content unit {path.relative_to(ROOT)}")
            continue
        unit = load_json(path)
        atlas_row = atlas_rows_by_unit.get(unit_id, {})
        for layer in ("gloss", "literal"):
            task_index += 1
            tasks.append(
                task_for_layer(
                    unit=unit,
                    coverage_row=coverage_row,
                    atlas_row=atlas_row,
                    layer_def=layers_by_name[layer],
                    task_index=task_index,
                )
            )
    return tasks, errors


def validate_task_shape(task: dict[str, Any]) -> list[str]:
    errors = []
    generation_input = task.get("generation_input") or {}
    required = [
        "unit_id",
        "layer",
        "locked_inputs",
        "style_profile",
        "candidate_count",
        "seed",
        "model_profile_id",
    ]
    for field in required:
        if field not in generation_input:
            errors.append(f"{task.get('task_id')}: missing generation_input.{field}")
    if generation_input.get("layer") != task.get("layer"):
        errors.append(f"{task.get('task_id')}: layer mismatch")
    if generation_input.get("unit_id") != task.get("unit_id"):
        errors.append(f"{task.get('task_id')}: unit_id mismatch")
    source = generation_input.get("locked_inputs", {}).get("source", {})
    token_ids = [
        str(token.get("token_id") or "")
        for token in source.get("tokens", [])
        if token.get("token_id")
    ]
    if len(token_ids) != len(set(token_ids)):
        errors.append(f"{task.get('task_id')}: duplicate source token IDs")
    if int(task.get("token_count") or 0) != int(source.get("token_count") or 0):
        errors.append(f"{task.get('task_id')}: token_count mismatch")
    return errors


def summarize(
    *,
    tasks: list[dict[str, Any]],
    coverage: dict[str, Any],
    selected_rows: list[dict[str, Any]],
    model_data: dict[str, Any],
) -> dict[str, Any]:
    chars = [int(task["estimated_payload_chars"]) for task in tasks]
    layer_counts = Counter(str(task["layer"]) for task in tasks)
    tags: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    units = {str(task["unit_id"]) for task in tasks}
    for task in tasks:
        tags.update(str(tag) for tag in task.get("benchmark_tags", []))
    for row in selected_rows:
        if row["unit_id"] in units:
            domains.update(str(domain) for domain in row.get("domains", []))
    planned_models = model_data.get("recommended_bakeoff_models", [])
    summary = coverage["summary"]
    closed_units = len(units)
    projected_covered = int(summary["integrated_covered_unit_count"]) + closed_units
    return {
        "source_uncovered_unit_count": summary["uncovered_unit_count"],
        "selected_gap_unit_count": closed_units,
        "task_count": len(tasks),
        "layer_counts": dict(sorted(layer_counts.items())),
        "token_instances": sum(int(task["token_count"]) for task in tasks),
        "candidate_count_per_task": 3,
        "planned_model_count": len(planned_models),
        "planned_model_runs": len(tasks) * len(planned_models),
        "closed_uncovered_unit_count": closed_units,
        "remaining_uncovered_unit_count": max(
            0,
            int(summary["uncovered_unit_count"]) - closed_units,
        ),
        "projected_atlas_covered_unit_count": projected_covered,
        "projected_expanded_atlas_coverage_pct": pct(
            projected_covered,
            int(summary["atlas_unit_count"]),
        ),
        "selected_textual_gap_unit_count": sum(
            1 for row in selected_rows if row.get("textual_witness_pressure")
        ),
        "selected_reception_gap_unit_count": sum(
            1 for row in selected_rows if row.get("reception_sensitive")
        ),
        "top_selected_unit": selected_rows[0]["unit_id"] if selected_rows else "",
        "top_selected_gap_score": selected_rows[0]["coverage_gap_score"] if selected_rows else 0,
        "estimated_payload_chars": {
            "min": min(chars) if chars else 0,
            "max": max(chars) if chars else 0,
            "mean": round(statistics.mean(chars), 2) if chars else 0,
            "median": round(statistics.median(chars), 2) if chars else 0,
        },
        "benchmark_tag_counts": dict(tags.most_common()),
        "domain_counts": dict(domains.most_common()),
    }


def build_suite(
    *,
    model_data_path: Path,
    coverage_path: Path,
    atlas_path: Path,
    output_schema_path: Path,
    limit: int,
) -> dict[str, Any]:
    model_data = load_json(model_data_path)
    coverage = load_json(coverage_path)
    atlas = load_json(atlas_path)
    output_schema = load_json(output_schema_path)
    selected_rows = selected_gap_rows(coverage, limit)
    atlas_rows_by_unit = {str(row["unit_id"]): row for row in atlas.get("priority_unit_rows", [])}
    tasks, load_errors = make_tasks(
        coverage_rows=selected_rows,
        atlas_rows_by_unit=atlas_rows_by_unit,
    )
    validation_errors = load_errors
    for task in tasks:
        validation_errors.extend(validate_task_shape(task))
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": (
            "generated contextual gap benchmark supplement; tasks are ready for local model runs"
        ),
        "source_paths": {
            "model_data": str(model_data_path.relative_to(ROOT)),
            "contextual_benchmark_coverage": str(coverage_path.relative_to(ROOT)),
            "contextual_pressure_atlas": str(atlas_path.relative_to(ROOT)),
            "generation_output_schema": str(output_schema_path.relative_to(ROOT)),
        },
        "selection": {
            "method": "top uncovered atlas units by coverage_gap_score",
            "requested_limit": limit,
            "selected_unit_ids": [str(row["unit_id"]) for row in selected_rows],
        },
        "output_schema_title": output_schema.get("title"),
        "recommended_bakeoff_models": model_data.get("recommended_bakeoff_models", []),
        "summary": summarize(
            tasks=tasks,
            coverage=coverage,
            selected_rows=selected_rows,
            model_data=model_data,
        ),
        "validation_errors": validation_errors,
        "tasks": tasks,
    }


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
    left = 300
    right = 70
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


def render_html(suite: dict[str, Any]) -> str:
    summary = suite["summary"]
    selected_rows = [
        [
            task["coverage_priority_rank"],
            task["unit_id"],
            task["ref"],
            task["layer"],
            f"{float(task['coverage_gap_score']):.2f}",
            fmt_int(task["token_count"]),
            f"{float(task['outside_psalms_context_pct']):.2f}%",
            fmt_int(task["estimated_payload_chars"]),
        ]
        for task in suite["tasks"]
    ]
    score_rows = [
        {
            "unit": unit_id,
            "score": next(
                float(task["coverage_gap_score"])
                for task in suite["tasks"]
                if task["unit_id"] == unit_id
            ),
        }
        for unit_id in suite["selection"]["selected_unit_ids"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Contextual Gap Benchmark Supplement</title>
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
    <h1>AlephTav Contextual Gap Benchmark Supplement</h1>
    <p class="lede">
      Gloss and literal benchmark tasks for the highest-scoring uncovered
      contextual-pressure atlas units. This turns coverage gaps into runnable
      local-model bake-off inputs with locked Hebrew source, witnesses, context
      frames, review roles, and evidence boundaries.
    </p>
    <p class="meta">Generated {esc(suite["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Gap Closure Inventory</h2>
      {
        metric_cards(
            [
                ("Tasks", fmt_int(summary["task_count"]), "Runnable gloss/literal tasks."),
                (
                    "Units",
                    fmt_int(summary["selected_gap_unit_count"]),
                    "Uncovered atlas units closed.",
                ),
                (
                    "Projected coverage",
                    f'''{summary["projected_expanded_atlas_coverage_pct"]:.2f}%''',
                    "Atlas coverage after merging this supplement.",
                ),
                (
                    "Planned runs",
                    fmt_int(summary["planned_model_runs"]),
                    "Tasks multiplied by planned bake-off models.",
                ),
                (
                    "Textual gaps",
                    fmt_int(summary["selected_textual_gap_unit_count"]),
                    "Selected units with textual witness pressure.",
                ),
                (
                    "Reception gaps",
                    fmt_int(summary["selected_reception_gap_unit_count"]),
                    "Selected units with reception sensitivity.",
                ),
                (
                    "Remaining gaps",
                    fmt_int(summary["remaining_uncovered_unit_count"]),
                    "Uncovered atlas units after this supplement.",
                ),
                (
                    "Validation errors",
                    fmt_int(len(suite["validation_errors"])),
                    "Duplicate, missing, or task-shape errors.",
                ),
            ]
        )
    }
      <div class="warning">
        This supplement creates executable evaluation tasks. It does not
        approve model outputs, canonical renderings, or release-ready wording.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            score_rows,
            label_key="unit",
            value_key="score",
            aria_label="Selected contextual gap scores",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(summary["domain_counts"], "domain"),
            label_key="domain",
            value_key="count",
            aria_label="Selected contextual gap domains",
            color="#7c5b2f",
        )
    }</div>
    </section>
    <section>
      <h2>Supplement Tasks</h2>
      {
        table(
            [
                "Rank",
                "Unit",
                "Ref",
                "Layer",
                "Gap Score",
                "Tokens",
                "Outside Context",
                "Payload Chars",
            ],
            selected_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate benchmark tasks for uncovered contextual atlas units."
    )
    parser.add_argument("--model-data", type=Path, default=MODEL_DATA_PATH)
    parser.add_argument("--coverage", type=Path, default=COVERAGE_PATH)
    parser.add_argument("--atlas", type=Path, default=ATLAS_PATH)
    parser.add_argument("--output-schema", type=Path, default=OUTPUT_SCHEMA_PATH)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--jsonl-output", type=Path, default=DEFAULT_JSONL_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suite = build_suite(
        model_data_path=args.model_data,
        coverage_path=args.coverage,
        atlas_path=args.atlas,
        output_schema_path=args.output_schema,
        limit=args.limit,
    )
    write_json(args.json_output, suite)
    write_jsonl(args.jsonl_output, suite["tasks"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(suite), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.jsonl_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
