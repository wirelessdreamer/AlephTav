from __future__ import annotations

import argparse
import html
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL_DATA_PATH = ROOT / "docs" / "research" / "local_translation_model_data.json"
SEED_PACKETS_PATH = ROOT / "reports" / "research" / "psalms_seed_context_packets.json"
OUTPUT_SCHEMA_PATH = ROOT / "app" / "llm" / "contracts" / "generation_output.schema.json"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "local_model_benchmark_suite.json"
DEFAULT_JSONL_OUTPUT = ROOT / "reports" / "research" / "local_model_benchmark_tasks.jsonl"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "local_model_benchmark_suite.html"

BENCHMARK_LAYERS = [
    {
        "layer": "gloss",
        "prompt_file": "app/llm/prompts/pass_01_gloss.md",
        "style_profile": {
            "profile_id": "benchmark_gloss",
            "target": "token-traceable gloss",
            "constraints": [
                "Preserve token order where possible.",
                "Do not add doctrinal interpretation.",
                "Keep alignment hints explicit.",
            ],
        },
    },
    {
        "layer": "literal",
        "prompt_file": "app/llm/prompts/pass_02_literal.md",
        "style_profile": {
            "profile_id": "benchmark_literal",
            "target": "literal English rendering",
            "constraints": [
                "Preserve Hebrew source imagery before smoothing English.",
                "Do not import reception-history conclusions into translation text.",
                "Use drift flags for necessary interpretive or stylistic movement.",
            ],
        },
    },
]

BASE_RUBRIC = {
    "schema_validity": {
        "weight": 0,
        "gate": True,
        "description": "Output must validate against generation_output.schema.json.",
    },
    "token_alignment": {
        "weight": 15,
        "gate": False,
        "description": "Candidate should cite valid token IDs and preserve source-token coverage.",
    },
    "lexical_morphology": {
        "weight": 15,
        "gate": False,
        "description": (
            "Rendering should respect morphology, lemmas, POS, suffixes, and construct chains."
        ),
    },
    "source_image_poetics": {
        "weight": 12,
        "gate": False,
        "description": (
            "Rendering should preserve source images, parallelism, terseness, and genre signals."
        ),
    },
    "whole_tanakh_context": {
        "weight": 12,
        "gate": False,
        "description": "Rationale should use cross-book context only where evidence supports it.",
    },
    "witness_boundary": {
        "weight": 10,
        "gate": False,
        "description": (
            "Witnesses must be cited as witnesses, not silently used as canonical basis."
        ),
    },
    "reception_separation": {
        "weight": 12,
        "gate": False,
        "description": "Jewish, Christian, liturgical, and academic reception must stay separate.",
    },
    "style_layer_compliance": {
        "weight": 10,
        "gate": False,
        "description": "Candidate should obey the selected layer's freedom and constraints.",
    },
    "unsupported_claim_control": {
        "weight": 9,
        "gate": False,
        "description": "Rationale should flag missing evidence and avoid invented claims.",
    },
    "local_runtime_metadata": {
        "weight": 5,
        "gate": False,
        "description": (
            "Run record should include model, quantization, seed, latency, and tokens/sec."
        ),
    },
}

TAG_DIMENSION_BOOSTS = {
    "reception_history": {"reception_separation": 4},
    "jewish_christian_reception": {"reception_separation": 5},
    "messianic_interpretation": {"reception_separation": 5},
    "textual_witness": {"witness_boundary": 5},
    "textual_sensitivity": {"witness_boundary": 3},
    "lexical_dispute": {"lexical_morphology": 3, "witness_boundary": 2},
    "lexical_ambiguity": {"lexical_morphology": 3, "unsupported_claim_control": 2},
    "parallelism": {"source_image_poetics": 4},
    "negative_parallelism": {"source_image_poetics": 4},
    "terse_poetry": {"source_image_poetics": 3},
    "source_image_pressure": {"source_image_poetics": 3},
    "metaphor": {"source_image_poetics": 3},
    "lament": {"source_image_poetics": 2},
    "imprecation": {"source_image_poetics": 2, "unsupported_claim_control": 2},
    "anthropology": {"whole_tanakh_context": 2, "unsupported_claim_control": 2},
    "canonical_intertext": {"whole_tanakh_context": 4},
    "intertextuality": {"whole_tanakh_context": 4},
    "torah_psalm": {"whole_tanakh_context": 3},
    "divine_name_policy": {"lexical_morphology": 2, "witness_boundary": 2},
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def compact_token(token: dict[str, Any]) -> dict[str, Any]:
    surface_context = token.get("surface_context") or {}
    lemma_context = token.get("lemma_form_context") or {}
    return {
        "token_id": token.get("token_id"),
        "surface": token.get("surface"),
        "lemma": token.get("lemma"),
        "display_gloss": token.get("display_gloss"),
        "part_of_speech": token.get("part_of_speech"),
        "surface_query": token.get("surface_query"),
        "surface_tanakh_count": surface_context.get("tanakh_count", 0),
        "surface_outside_psalms_count": surface_context.get("outside_psalms_count", 0),
        "surface_outside_psalms_sample_refs": surface_context.get(
            "outside_psalms_sample_refs",
            [],
        )[:5],
        "lemma_form_query": token.get("lemma_form_query"),
        "lemma_form_tanakh_count": lemma_context.get("tanakh_count", 0),
        "lemma_form_outside_psalms_count": lemma_context.get(
            "outside_psalms_count",
            0,
        ),
    }


def task_rubric(tags: list[str], layer: str) -> dict[str, Any]:
    dimensions = {
        key: {
            "weight": value["weight"],
            "gate": value["gate"],
            "description": value["description"],
        }
        for key, value in BASE_RUBRIC.items()
    }
    for tag in tags:
        for dimension, boost in TAG_DIMENSION_BOOSTS.get(tag, {}).items():
            dimensions[dimension]["weight"] += boost
    if layer == "gloss":
        dimensions["token_alignment"]["weight"] += 3
        dimensions["style_layer_compliance"]["weight"] += 2
    if layer == "literal":
        dimensions["source_image_poetics"]["weight"] += 2
        dimensions["style_layer_compliance"]["weight"] += 2
    scored_total = sum(item["weight"] for item in dimensions.values() if not item.get("gate"))
    return {
        "score_scale": "0-5 per non-gate dimension; weighted to 100",
        "weighted_total": scored_total,
        "dimensions": dimensions,
    }


def locked_inputs_for_packet(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": {
            "unit_id": packet["unit_id"],
            "ref": packet["ref"],
            "source_hebrew": packet["source_hebrew"],
            "token_count": packet["token_count"],
            "tokens": [compact_token(token) for token in packet["tokens"]],
        },
        "context": {
            "benchmark_tags": packet["benchmark_tags"],
            "why_in_seed": packet["why_in_seed"],
            "contextual_case_layers": packet.get("contextual_case_layers", []),
            "contextual_case_reason": packet.get("contextual_case_reason"),
            "coverage": packet["coverage"],
            "missing_enrichment_counts": packet["missing_enrichment_counts"],
            "high_context_tokens": packet["high_context_tokens"],
        },
        "witnesses": packet["witness_summary"],
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
        },
    }


def estimate_task_chars(generation_input: dict[str, Any], benchmark: dict[str, Any]) -> int:
    payload = {
        "generation_input": generation_input,
        "benchmark": benchmark,
    }
    return len(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def make_tasks(seed_packets: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = []
    for packet_index, packet in enumerate(seed_packets["packets"], start=1):
        locked_inputs = locked_inputs_for_packet(packet)
        for layer_def in BENCHMARK_LAYERS:
            layer = layer_def["layer"]
            task_id = f"bench.{packet['unit_id']}.{layer}"
            generation_input = {
                "unit_id": packet["unit_id"],
                "layer": layer,
                "locked_inputs": locked_inputs,
                "style_profile": layer_def["style_profile"],
                "candidate_count": 3,
                "seed": 20260615 + packet_index,
                "model_profile_id": "{model_profile_id}",
            }
            benchmark = {
                "task_id": task_id,
                "prompt_file": layer_def["prompt_file"],
                "required_output_schema": "app/llm/contracts/generation_output.schema.json",
                "rubric": task_rubric(packet["benchmark_tags"], layer),
                "must_check": [
                    "JSON schema validity",
                    "valid unit_id and layer",
                    "valid token IDs in alignment_hints and preserved_source_images",
                    "translation_basis uses Hebrew source unless explicitly testing LXX",
                    "no reception-history claim inside the translation text",
                    "no whole-Tanakh claim without cited context evidence",
                ],
            }
            task = {
                "task_id": task_id,
                "unit_id": packet["unit_id"],
                "ref": packet["ref"],
                "layer": layer,
                "benchmark_tags": packet["benchmark_tags"],
                "token_count": packet["token_count"],
                "outside_psalms_context_pct": packet["coverage"]["surface_outside_context_pct"],
                "generation_input": generation_input,
                "benchmark": benchmark,
            }
            task["estimated_payload_chars"] = estimate_task_chars(
                generation_input,
                benchmark,
            )
            tasks.append(task)
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
    candidate_count = generation_input.get("candidate_count")
    if not isinstance(candidate_count, int) or not 1 <= candidate_count <= 5:
        errors.append(f"{task.get('task_id')}: candidate_count outside schema bounds")
    return errors


def summarize(tasks: list[dict[str, Any]], model_data: dict[str, Any]) -> dict[str, Any]:
    task_chars = [int(task["estimated_payload_chars"]) for task in tasks]
    layer_counts = Counter(task["layer"] for task in tasks)
    tag_counts: Counter[str] = Counter()
    dimension_weights: Counter[str] = Counter()
    unit_count = len({task["unit_id"] for task in tasks})
    token_instances = sum(int(task["token_count"]) for task in tasks)
    for task in tasks:
        tag_counts.update(str(tag) for tag in task["benchmark_tags"])
        for dimension, data in task["benchmark"]["rubric"]["dimensions"].items():
            if not data.get("gate"):
                dimension_weights[dimension] += int(data["weight"])
    return {
        "task_count": len(tasks),
        "unit_count": unit_count,
        "layer_counts": dict(sorted(layer_counts.items())),
        "token_instances": token_instances,
        "candidate_count_per_task": 3,
        "planned_model_count": len(model_data.get("recommended_bakeoff_models", [])),
        "planned_model_runs": len(tasks) * len(model_data.get("recommended_bakeoff_models", [])),
        "estimated_payload_chars": {
            "min": min(task_chars) if task_chars else 0,
            "max": max(task_chars) if task_chars else 0,
            "mean": round(statistics.mean(task_chars), 2) if task_chars else 0,
            "median": round(statistics.median(task_chars), 2) if task_chars else 0,
        },
        "benchmark_tag_counts": dict(tag_counts.most_common()),
        "aggregate_dimension_weights": dict(dimension_weights.most_common()),
    }


def build_suite(
    model_data_path: Path,
    seed_packets_path: Path,
    output_schema_path: Path,
) -> dict[str, Any]:
    model_data = load_json(model_data_path)
    seed_packets = load_json(seed_packets_path)
    output_schema = load_json(output_schema_path)
    tasks = make_tasks(seed_packets)
    validation_errors = []
    for task in tasks:
        validation_errors.extend(validate_task_shape(task))
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated benchmark suite; tasks are ready for local model runs",
        "source_paths": {
            "model_data": "docs/research/local_translation_model_data.json",
            "seed_context_packets": "reports/research/psalms_seed_context_packets.json",
            "generation_output_schema": "app/llm/contracts/generation_output.schema.json",
        },
        "output_schema_title": output_schema.get("title"),
        "recommended_bakeoff_models": model_data.get("recommended_bakeoff_models", []),
        "summary": summarize(tasks, model_data),
        "validation_errors": validation_errors,
        "tasks": tasks,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_jsonl(path: Path, tasks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(json.dumps(task, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


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
    left = 260
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
        label = str(row[label_key])
        parts.append(
            f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(label)}</text>'
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


def counter_rows(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
    return [
        {label_key: key, "count": value}
        for key, value in sorted(counter.items(), key=lambda item: item[1], reverse=True)
    ]


def model_rows(models: list[str]) -> list[dict[str, Any]]:
    return [{"model": model, "count": 1} for model in models]


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
        cells = []
        for cell in row:
            if str(cell).startswith("<"):
                cells.append(f"<td>{cell}</td>")
            else:
                cells.append(f"<td>{esc(cell)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_html(suite: dict[str, Any]) -> str:
    summary = suite["summary"]
    chars = summary["estimated_payload_chars"]
    task_rows = [
        [
            task["task_id"],
            task["ref"],
            task["layer"],
            fmt_int(task["token_count"]),
            f"{task['outside_psalms_context_pct']:.2f}%",
            fmt_int(task["estimated_payload_chars"]),
        ]
        for task in suite["tasks"]
    ]
    model_table_rows = [[model] for model in suite["recommended_bakeoff_models"]]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Local Model Benchmark Suite</title>
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
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AlephTav Local Model Benchmark Suite</h1>
    <p class="lede">
      A generated bake-off suite for local Hebrew-to-English Psalms models. It
      converts seed context packets into schema-shaped gloss and literal tasks,
      with scoring dimensions for alignment, morphology, poetry, witnesses,
      whole-Tanakh context, reception separation, and local runtime metadata.
    </p>
    <p class="meta">
      Generated {esc(suite["generated_on"])}. JSONL task file:
      reports/research/local_model_benchmark_tasks.jsonl.
    </p>
  </header>
  <main>
    <section>
      <h2>Suite Inventory</h2>
      {
        metric_cards(
            [
                ("Tasks", fmt_int(summary["task_count"]), "Gloss and literal benchmark tasks."),
                ("Seed units", fmt_int(summary["unit_count"]), "Distinct Psalm units covered."),
                (
                    "Token instances",
                    fmt_int(summary["token_instances"]),
                    "Tokens counted once per task layer.",
                ),
                (
                    "Planned model runs",
                    fmt_int(summary["planned_model_runs"]),
                    "Tasks multiplied by planned bake-off models.",
                ),
            ]
        )
    }
      <div class="warning">
        This is a benchmark suite, not a benchmark result. A model only earns
        authority after outputs are generated locally, schema-validated, scored,
        compared across models, and reviewed by humans.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(summary["layer_counts"], "layer"),
            label_key="layer",
            value_key="count",
            aria_label="Benchmark tasks by layer",
            color="#2f6f73",
        )
    }</div>
      <div class="note">
        Estimated task payload length: min {fmt_int(chars["min"])} chars, median
        {fmt_int(chars["median"])} chars, mean {chars["mean"]:.2f} chars, max
        {fmt_int(chars["max"])} chars.
      </div>
    </section>

    <section>
      <h2>Scoring Pressure</h2>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(summary["aggregate_dimension_weights"], "dimension"),
            label_key="dimension",
            value_key="count",
            aria_label="Aggregate rubric dimension weights",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(summary["benchmark_tag_counts"], "tag"),
            label_key="tag",
            value_key="count",
            aria_label="Benchmark tag counts across tasks",
            color="#58508d",
        )
    }</div>
    </section>

    <section>
      <h2>Model Bake-Off</h2>
      <p>
        The suite is configured for the recommended local comparison set from
        the model research data. Runtime results should record model hash,
        quantization, context length, seed, latency, tokens/sec, and VRAM.
      </p>
      <div class="chart">{
        svg_horizontal_bars(
            model_rows(suite["recommended_bakeoff_models"]),
            label_key="model",
            value_key="count",
            aria_label="Recommended benchmark models",
            color="#4f6f9f",
            limit=12,
        )
    }</div>
      {table(["Model"], model_table_rows)}
    </section>

    <section>
      <h2>Task Manifest</h2>
      {
        table(
            [
                "Task",
                "Reference",
                "Layer",
                "Tokens",
                "Outside-Psalms context",
                "Payload chars",
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
    parser = argparse.ArgumentParser(description="Generate local model benchmark suite artifacts.")
    parser.add_argument("--model-data", type=Path, default=MODEL_DATA_PATH)
    parser.add_argument("--seed-packets", type=Path, default=SEED_PACKETS_PATH)
    parser.add_argument("--output-schema", type=Path, default=OUTPUT_SCHEMA_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--jsonl-output", type=Path, default=DEFAULT_JSONL_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suite = build_suite(args.model_data, args.seed_packets, args.output_schema)
    write_json(args.json_output, suite)
    write_jsonl(args.jsonl_output, suite["tasks"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(suite), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.jsonl_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
