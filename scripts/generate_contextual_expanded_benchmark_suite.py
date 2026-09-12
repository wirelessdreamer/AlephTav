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
REPORT_ROOT = ROOT / "reports" / "research"
INTEGRATED_SUITE_PATH = REPORT_ROOT / "integrated_benchmark_suite.json"
GAP_SUPPLEMENT_PATH = REPORT_ROOT / "contextual_gap_benchmark_supplement_suite.json"
DEFAULT_JSON_OUTPUT = REPORT_ROOT / "contextual_expanded_benchmark_suite.json"
DEFAULT_JSONL_OUTPUT = REPORT_ROOT / "contextual_expanded_benchmark_tasks.jsonl"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "contextual_expanded_benchmark_suite.html"


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


def suite_models(*suites: dict[str, Any]) -> list[str]:
    models: list[str] = []
    for suite in suites:
        for model in suite.get("recommended_bakeoff_models", []):
            model_text = str(model)
            if model_text not in models:
                models.append(model_text)
    return models


def attributed_tasks(
    integrated: dict[str, Any],
    gap_supplement: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    tasks = []
    errors = []
    seen: dict[str, str] = {}
    sources = [
        ("integrated_benchmark_suite", integrated),
        ("contextual_gap_benchmark_supplement", gap_supplement),
    ]
    for source_name, suite in sources:
        for task in suite.get("tasks", []):
            task_id = str(task.get("task_id") or "")
            if task_id in seen:
                errors.append(
                    f"duplicate task_id {task_id} in {source_name}; already seen in {seen[task_id]}"
                )
                continue
            copied = dict(task)
            copied["suite_source"] = source_name
            copied["upstream_suite_source"] = task.get("suite_source") or source_name
            seen[task_id] = source_name
            tasks.append(copied)
    return tasks, errors


def payload_chars(tasks: list[dict[str, Any]]) -> list[int]:
    return [int(task.get("estimated_payload_chars") or 0) for task in tasks]


def source_unit_counts(tasks: list[dict[str, Any]]) -> dict[str, int]:
    source_units: dict[str, set[str]] = {}
    for task in tasks:
        source = str(task.get("suite_source") or "unknown")
        source_units.setdefault(source, set()).add(str(task["unit_id"]))
    return {source: len(units) for source, units in sorted(source_units.items())}


def aggregate_dimension_weights(tasks: list[dict[str, Any]]) -> dict[str, int]:
    weights: Counter[str] = Counter()
    for task in tasks:
        dimensions = task.get("benchmark", {}).get("rubric", {}).get("dimensions", {})
        for dimension, data in dimensions.items():
            if not data.get("gate"):
                weights[str(dimension)] += int(data.get("weight") or 0)
    return dict(weights.most_common())


def validate_tasks(tasks: list[dict[str, Any]]) -> list[str]:
    errors = []
    for task in tasks:
        generation_input = task.get("generation_input") or {}
        if generation_input.get("unit_id") != task.get("unit_id"):
            errors.append(f"{task.get('task_id')}: unit_id mismatch")
        if generation_input.get("layer") != task.get("layer"):
            errors.append(f"{task.get('task_id')}: layer mismatch")
        source = generation_input.get("locked_inputs", {}).get("source", {})
        token_ids = [
            str(token.get("token_id") or "")
            for token in source.get("tokens", [])
            if token.get("token_id")
        ]
        if len(token_ids) != len(set(token_ids)):
            errors.append(f"{task.get('task_id')}: duplicate token IDs")
        if int(task.get("token_count") or 0) != int(source.get("token_count") or 0):
            errors.append(f"{task.get('task_id')}: token_count mismatch")
    return errors


def summarize(
    *,
    tasks: list[dict[str, Any]],
    integrated: dict[str, Any],
    gap_supplement: dict[str, Any],
    models: list[str],
) -> dict[str, Any]:
    chars = payload_chars(tasks)
    layer_counts = Counter(str(task["layer"]) for task in tasks)
    source_counts = Counter(str(task["suite_source"]) for task in tasks)
    upstream_counts = Counter(str(task["upstream_suite_source"]) for task in tasks)
    tag_counts: Counter[str] = Counter()
    for task in tasks:
        tag_counts.update(str(tag) for tag in task.get("benchmark_tags", []))
    gap_summary = gap_supplement["summary"]
    integrated_summary = integrated["summary"]
    projected_covered = int(gap_summary["projected_atlas_covered_unit_count"])
    closed_gaps = int(gap_summary["closed_uncovered_unit_count"])
    source_uncovered = int(gap_summary["source_uncovered_unit_count"])
    atlas_total = source_uncovered + projected_covered - closed_gaps
    atlas_covered_before = projected_covered - closed_gaps
    return {
        "integrated_task_count": integrated_summary["task_count"],
        "contextual_gap_task_count": gap_summary["task_count"],
        "task_count": len(tasks),
        "unit_count": len({str(task["unit_id"]) for task in tasks}),
        "layer_counts": dict(sorted(layer_counts.items())),
        "source_task_counts": dict(source_counts.most_common()),
        "upstream_source_task_counts": dict(upstream_counts.most_common()),
        "source_unit_counts": source_unit_counts(tasks),
        "token_instances": sum(int(task.get("token_count") or 0) for task in tasks),
        "candidate_count_per_task": 3,
        "planned_model_count": len(models),
        "planned_model_runs": len(tasks) * len(models),
        "contextual_gap_unit_count": gap_summary["selected_gap_unit_count"],
        "contextual_gap_remaining_unit_count": gap_summary["remaining_uncovered_unit_count"],
        "atlas_coverage_before_pct": pct(atlas_covered_before, atlas_total),
        "projected_atlas_coverage_after_pct": gap_summary["projected_expanded_atlas_coverage_pct"],
        "estimated_payload_chars": {
            "min": min(chars) if chars else 0,
            "max": max(chars) if chars else 0,
            "mean": round(statistics.mean(chars), 2) if chars else 0,
            "median": round(statistics.median(chars), 2) if chars else 0,
        },
        "benchmark_tag_counts": dict(tag_counts.most_common()),
        "aggregate_dimension_weights": aggregate_dimension_weights(tasks),
    }


def build_suite(integrated_path: Path, gap_supplement_path: Path) -> dict[str, Any]:
    integrated = load_json(integrated_path)
    gap_supplement = load_json(gap_supplement_path)
    tasks, duplicate_errors = attributed_tasks(integrated, gap_supplement)
    validation_errors = duplicate_errors + validate_tasks(tasks)
    models = suite_models(integrated, gap_supplement)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": (
            "generated contextual expanded benchmark suite; integrated suite "
            "plus contextual gap supplement"
        ),
        "source_paths": {
            "integrated_suite": str(integrated_path.relative_to(ROOT)),
            "contextual_gap_supplement": str(gap_supplement_path.relative_to(ROOT)),
        },
        "output_schema_title": integrated.get("output_schema_title"),
        "recommended_bakeoff_models": models,
        "summary": summarize(
            tasks=tasks,
            integrated=integrated,
            gap_supplement=gap_supplement,
            models=models,
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
    chars = summary["estimated_payload_chars"]
    task_rows = [
        [
            task["task_id"],
            task["ref"],
            task["layer"],
            task["suite_source"],
            fmt_int(task["token_count"]),
            fmt_int(task["estimated_payload_chars"]),
        ]
        for task in suite["tasks"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Contextual Expanded Benchmark Suite</title>
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
    <h1>AlephTav Contextual Expanded Benchmark Suite</h1>
    <p class="lede">
      Single runnable benchmark target combining the integrated seed plus
      priority supplement suite with the contextual coverage-gap supplement.
      This is the broadest generated local-model bake-off suite in the
      research portfolio.
    </p>
    <p class="meta">Generated {esc(suite["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Expanded Inventory</h2>
      {
        metric_cards(
            [
                ("Tasks", fmt_int(summary["task_count"]), "Runnable gloss/literal tasks."),
                ("Units", fmt_int(summary["unit_count"]), "Distinct Psalm units covered."),
                (
                    "Projected atlas coverage",
                    f'''{summary["projected_atlas_coverage_after_pct"]:.2f}%''',
                    "Contextual atlas coverage after gap supplement.",
                ),
                (
                    "Planned runs",
                    fmt_int(summary["planned_model_runs"]),
                    "Tasks multiplied by planned bake-off models.",
                ),
                (
                    "Integrated tasks",
                    fmt_int(summary["integrated_task_count"]),
                    "Previously generated integrated suite tasks.",
                ),
                (
                    "Gap tasks",
                    fmt_int(summary["contextual_gap_task_count"]),
                    "New contextual coverage-gap tasks.",
                ),
                (
                    "Payload mean",
                    fmt_int(chars["mean"]),
                    "Mean serialized task payload characters.",
                ),
                (
                    "Validation errors",
                    fmt_int(len(suite["validation_errors"])),
                    "Duplicate or task-shape errors.",
                ),
            ]
        )
    }
      <div class="warning">
        This suite is runnable and dry-run verifiable. It still requires real
        model outputs, cross-exam review, and human Hebrew/lexical/alignment
        signoff before any translation claim is approved.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(summary["source_task_counts"], "source"),
            label_key="source",
            value_key="count",
            aria_label="Expanded task counts by source suite",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(summary["benchmark_tag_counts"], "tag"),
            label_key="tag",
            value_key="count",
            aria_label="Expanded benchmark tag counts",
            color="#7c5b2f",
        )
    }</div>
    </section>
    <section>
      <h2>Task Index</h2>
      {
        table(
            [
                "Task",
                "Ref",
                "Layer",
                "Source",
                "Tokens",
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
        description="Generate expanded benchmark suite with contextual gap tasks."
    )
    parser.add_argument("--integrated", type=Path, default=INTEGRATED_SUITE_PATH)
    parser.add_argument("--gap-supplement", type=Path, default=GAP_SUPPLEMENT_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--jsonl-output", type=Path, default=DEFAULT_JSONL_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suite = build_suite(args.integrated, args.gap_supplement)
    write_json(args.json_output, suite)
    write_jsonl(args.jsonl_output, suite["tasks"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(suite), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.jsonl_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
