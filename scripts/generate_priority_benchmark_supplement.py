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
MODEL_DATA_PATH = ROOT / "docs" / "research" / "local_translation_model_data.json"
DOSSIER_PATH = REPORT_ROOT / "priority_unit_dossiers.json"
OUTPUT_SCHEMA_PATH = ROOT / "app" / "llm" / "contracts" / "generation_output.schema.json"
DEFAULT_JSON_OUTPUT = REPORT_ROOT / "priority_benchmark_supplement_suite.json"
DEFAULT_JSONL_OUTPUT = REPORT_ROOT / "priority_benchmark_supplement_tasks.jsonl"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "priority_benchmark_supplement_suite.html"

SUPPLEMENT_SEED_BASE = 2026061500


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


def compact_task_token(
    token: dict[str, Any],
    high_context_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    high_context = high_context_by_id.get(str(token.get("token_id"))) or {}
    return {
        "token_id": token.get("token_id"),
        "surface": token.get("surface"),
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
        "surface_query": high_context.get("surface_query"),
        "surface_outside_psalms_count": high_context.get("outside_psalms_count", 0),
        "surface_outside_psalms_sample_refs": high_context.get(
            "outside_psalms_sample_refs",
            [],
        )[:5],
        "greek": token.get("greek"),
        "missing_enrichments": token.get("missing_enrichments") or [],
        "compiler_features": token.get("compiler_features") or {},
    }


def derive_benchmark_tags(dossier: dict[str, Any]) -> list[str]:
    domains = set(str(domain) for domain in dossier.get("context_domains", {}))
    tags = {"priority_dossier", "supplemental_priority"}
    if dossier.get("primary_stratum"):
        tags.add(str(dossier["primary_stratum"]))
    if "jewish_christian_reception" in domains:
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


def locked_inputs_for_dossier(dossier: dict[str, Any]) -> dict[str, Any]:
    high_context_by_id = {
        str(token["token_id"]): token
        for token in dossier["context_coverage"]["high_context_tokens"]
    }
    return {
        "source": {
            "unit_id": dossier["unit_id"],
            "ref": dossier["ref"],
            "source_hebrew": dossier["source_hebrew"],
            "token_count": dossier["source_summary"]["token_count"],
            "tokens": [
                compact_task_token(token, high_context_by_id) for token in dossier["tokens"]
            ],
        },
        "context": {
            "priority_rank": dossier["priority_rank"],
            "priority_score": dossier["priority"]["score"],
            "primary_stratum": dossier["primary_stratum"],
            "context_pressure": dossier["priority"],
            "domain_groups": dossier["domain_groups"],
            "context_domains": dossier["context_domains"],
            "reception_profile": dossier["reception_profile"],
            "review_roles": dossier["review_roles"],
            "model_controls": dossier["model_controls"],
            "reviewer_questions": dossier["reviewer_questions"],
            "outside_context_division_counts": dossier["context_coverage"][
                "outside_context_division_counts"
            ],
            "high_context_tokens": dossier["context_coverage"]["high_context_tokens"],
            "missing_enrichment_counts": dossier["context_coverage"]["missing_enrichment_counts"],
        },
        "witnesses": dossier["witnesses"],
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
            "dossier_boundary": (
                "This supplement exists because the priority dossier lacked "
                "gloss/literal benchmark task coverage in the seed suite."
            ),
        },
    }


def task_for_layer(
    *,
    dossier: dict[str, Any],
    layer_def: dict[str, Any],
    task_index: int,
) -> dict[str, Any]:
    layer = str(layer_def["layer"])
    task_id = f"bench.{dossier['unit_id']}.{layer}"
    tags = derive_benchmark_tags(dossier)
    locked_inputs = locked_inputs_for_dossier(dossier)
    generation_input = {
        "unit_id": dossier["unit_id"],
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
        ],
        "supplement_reason": (
            "Generated from priority dossier because this layer was missing "
            "from the seed benchmark suite."
        ),
    }
    task = {
        "task_id": task_id,
        "unit_id": dossier["unit_id"],
        "ref": dossier["ref"],
        "layer": layer,
        "benchmark_tags": tags,
        "token_count": dossier["source_summary"]["token_count"],
        "outside_psalms_context_pct": dossier["priority"]["surface_outside_context_pct"],
        "priority_rank": dossier["priority_rank"],
        "priority_score": dossier["priority"]["score"],
        "source_priority": "priority_unit_dossiers",
        "generation_input": generation_input,
        "benchmark": benchmark,
    }
    task["estimated_payload_chars"] = estimate_task_chars(generation_input, benchmark)
    return task


def make_tasks(dossiers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks = []
    task_index = 0
    layers_by_name = {str(layer["layer"]): layer for layer in BENCHMARK_LAYERS}
    for dossier in dossiers:
        missing_layers = dossier["benchmark"]["missing_task_layers"]
        for layer in missing_layers:
            if layer not in layers_by_name:
                continue
            task_index += 1
            tasks.append(
                task_for_layer(
                    dossier=dossier,
                    layer_def=layers_by_name[layer],
                    task_index=task_index,
                )
            )
    return tasks


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
    token_ids = [
        token.get("token_id") for token in generation_input["locked_inputs"]["source"]["tokens"]
    ]
    if len(token_ids) != len(set(token_ids)):
        errors.append(f"{task.get('task_id')}: duplicate source token IDs")
    return errors


def summarize(
    *,
    tasks: list[dict[str, Any]],
    dossiers: list[dict[str, Any]],
    model_data: dict[str, Any],
) -> dict[str, Any]:
    chars = [int(task["estimated_payload_chars"]) for task in tasks]
    layer_counts = Counter(str(task["layer"]) for task in tasks)
    tags: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    units = {str(task["unit_id"]) for task in tasks}
    for task in tasks:
        tags.update(str(tag) for tag in task.get("benchmark_tags", []))
    for dossier in dossiers:
        if dossier["unit_id"] in units:
            domains.update(str(domain) for domain in dossier["context_domains"])
    planned_models = model_data.get("recommended_bakeoff_models", [])
    return {
        "source_dossier_count": len(dossiers),
        "supplement_unit_count": len(units),
        "task_count": len(tasks),
        "layer_counts": dict(sorted(layer_counts.items())),
        "token_instances": sum(int(task["token_count"]) for task in tasks),
        "candidate_count_per_task": 3,
        "planned_model_count": len(planned_models),
        "planned_model_runs": len(tasks) * len(planned_models),
        "closed_dossier_task_gap_count": len(units),
        "remaining_dossier_task_gap_count": sum(
            1
            for dossier in dossiers
            if dossier["benchmark"]["missing_task_layers"] and dossier["unit_id"] not in units
        ),
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
    dossier_path: Path,
    output_schema_path: Path,
) -> dict[str, Any]:
    model_data = load_json(model_data_path)
    dossier_report = load_json(dossier_path)
    output_schema = load_json(output_schema_path)
    dossiers = dossier_report["dossiers"]
    tasks = make_tasks(dossiers)
    validation_errors = []
    for task in tasks:
        validation_errors.extend(validate_task_shape(task))
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": (
            "generated supplemental priority benchmark suite; tasks are ready for local model runs"
        ),
        "source_paths": {
            "model_data": "docs/research/local_translation_model_data.json",
            "priority_unit_dossiers": "reports/research/priority_unit_dossiers.json",
            "generation_output_schema": "app/llm/contracts/generation_output.schema.json",
        },
        "output_schema_title": output_schema.get("title"),
        "recommended_bakeoff_models": model_data.get("recommended_bakeoff_models", []),
        "summary": summarize(tasks=tasks, dossiers=dossiers, model_data=model_data),
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
    left = 280
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


def render_html(suite: dict[str, Any]) -> str:
    summary = suite["summary"]
    task_rows = [
        [
            task["task_id"],
            task["ref"],
            task["layer"],
            task["priority_rank"],
            f"{task['priority_score']:.2f}",
            fmt_int(task["token_count"]),
            f"{task['outside_psalms_context_pct']:.2f}%",
            fmt_int(task["estimated_payload_chars"]),
        ]
        for task in suite["tasks"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Priority Benchmark Supplement</title>
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
    <h1>AlephTav Priority Benchmark Supplement</h1>
    <p class="lede">
      Supplemental gloss and literal benchmark tasks for top-priority dossier
      units that were not covered by the original seed benchmark. The tasks
      keep source tokens, witnesses, context domains, reception frames, and
      review questions in the model input.
    </p>
    <p class="meta">Generated {esc(suite["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Supplement Inventory</h2>
      {
        metric_cards(
            [
                ("Tasks", fmt_int(summary["task_count"]), "Supplemental runnable tasks."),
                (
                    "Units",
                    fmt_int(summary["supplement_unit_count"]),
                    "Priority dossier gaps closed.",
                ),
                (
                    "Token instances",
                    fmt_int(summary["token_instances"]),
                    "Tokens counted once per task layer.",
                ),
                (
                    "Planned runs",
                    fmt_int(summary["planned_model_runs"]),
                    "Tasks multiplied by planned bake-off models.",
                ),
            ]
        )
    }
      <div class="warning">
        This supplement closes benchmark task coverage for priority dossiers,
        but it is not yet merged into the primary benchmark baseline.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(summary["layer_counts"], "layer"),
            label_key="layer",
            value_key="count",
            aria_label="Supplement task counts by layer",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(summary["domain_counts"], "domain"),
            label_key="domain",
            value_key="count",
            aria_label="Supplement domain coverage",
            color="#7c5b2f",
        )
    }</div>
    </section>
    <section>
      <h2>Supplement Tasks</h2>
      {
        table(
            [
                "Task",
                "Ref",
                "Layer",
                "Priority Rank",
                "Priority Score",
                "Tokens",
                "Outside Context",
                "Payload Chars",
            ],
            task_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate supplemental benchmark tasks for priority dossiers."
    )
    parser.add_argument("--model-data", type=Path, default=MODEL_DATA_PATH)
    parser.add_argument("--dossiers", type=Path, default=DOSSIER_PATH)
    parser.add_argument("--output-schema", type=Path, default=OUTPUT_SCHEMA_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--jsonl-output", type=Path, default=DEFAULT_JSONL_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suite = build_suite(
        model_data_path=args.model_data,
        dossier_path=args.dossiers,
        output_schema_path=args.output_schema,
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
