from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"
SCHEMA_PATH = ROOT / "app" / "llm" / "contracts" / "generation_output.schema.json"
SUITE_PATH = REPORT_ROOT / "local_model_benchmark_suite.json"
SUITE_SOURCES = [
    {
        "label": "base_benchmark_suite",
        "path": REPORT_ROOT / "local_model_benchmark_suite.json",
    },
    {
        "label": "integrated_benchmark_suite",
        "path": REPORT_ROOT / "integrated_benchmark_suite.json",
    },
    {
        "label": "contextual_expanded_benchmark_suite",
        "path": REPORT_ROOT / "contextual_expanded_benchmark_suite.json",
    },
]
DEFAULT_JSON_OUTPUT = REPORT_ROOT / "structured_output_tuning_report.json"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "structured_output_tuning_report.html"

RESULT_SOURCES = [
    {
        "label": "base_official_real_results",
        "path": REPORT_ROOT / "local_model_benchmark_results.jsonl",
    },
    {
        "label": "contextual_expanded_real_results",
        "path": REPORT_ROOT / "contextual_expanded_benchmark_results.jsonl",
    },
    {
        "label": "gemma_compact_json_tuning",
        "path": REPORT_ROOT / "local_model_benchmark_tuning_results.jsonl",
    },
    {
        "label": "mistral_compact_json_tuning",
        "path": REPORT_ROOT / "local_model_benchmark_tuning_mistral_results.jsonl",
    },
]


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"missing file: {path}"]
    rows = []
    errors = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: {exc}")
                continue
            row["_line_number"] = line_number
            rows.append(row)
    return rows, errors


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def task_lookup(suites: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for suite in suites:
        for task in suite.get("tasks", []):
            tasks[str(task["task_id"])] = task
    return tasks


def error_category(row: dict[str, Any], schema_errors: list[str]) -> str:
    if not row.get("output"):
        error = str(row.get("error") or "")
        if "JSONDecodeError" in error:
            return "json_decode_error"
        if error:
            return "runtime_or_bridge_error"
        return "missing_output"
    if schema_errors:
        return "schema_error"
    return "schema_valid"


def attempt_row(
    *,
    source_label: str,
    row: dict[str, Any],
    validator: Draft202012Validator,
    tasks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    output = row.get("output")
    schema_errors = []
    if isinstance(output, dict):
        schema_errors = [
            error.message
            for error in sorted(validator.iter_errors(output), key=lambda item: item.path)
        ]
    runtime = row.get("runtime") or {}
    task = tasks.get(str(row.get("task_id")))
    raw_text = str(row.get("raw_text") or "")
    raw_text_preview = " ".join(raw_text.split())[:260]
    prompt_mode = str(runtime.get("prompt_mode") or "full")
    format_mode = str(runtime.get("format_mode") or "schema")
    return {
        "source": source_label,
        "line_number": row.get("_line_number"),
        "task_id": row.get("task_id"),
        "unit_id": task.get("unit_id") if task else None,
        "ref": task.get("ref") if task else None,
        "layer": task.get("layer") if task else None,
        "model_profile_id": row.get("model_profile_id"),
        "runtime_model": runtime.get("model"),
        "adapter": runtime.get("adapter"),
        "prompt_mode": prompt_mode,
        "format_mode": format_mode,
        "requested_candidate_count": runtime.get("requested_candidate_count"),
        "elapsed_ms": runtime.get("elapsed_ms"),
        "prompt_eval_count": runtime.get("prompt_eval_count"),
        "eval_count": runtime.get("eval_count"),
        "raw_text_chars": len(raw_text),
        "has_output": isinstance(output, dict),
        "schema_valid": bool(isinstance(output, dict) and not schema_errors),
        "schema_error_count": len(schema_errors),
        "schema_errors": schema_errors[:8],
        "error": row.get("error"),
        "raw_text_preview": raw_text_preview,
        "error_category": error_category(row, schema_errors),
    }


def build_attempts(
    *,
    schema: dict[str, Any],
    suites: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    validator = Draft202012Validator(schema)
    tasks = task_lookup(suites)
    attempts = []
    load_errors = []
    for source in RESULT_SOURCES:
        rows, errors = load_jsonl(source["path"])
        load_errors.extend(f"{source['label']}: {error}" for error in errors)
        for row in rows:
            attempts.append(
                attempt_row(
                    source_label=source["label"],
                    row=row,
                    validator=validator,
                    tasks=tasks,
                )
            )
    return attempts, load_errors


def summarize(attempts: list[dict[str, Any]], load_errors: list[str]) -> dict[str, Any]:
    model_counts: Counter[str] = Counter()
    valid_by_model: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    valid_by_mode: Counter[str] = Counter()
    error_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    elapsed_by_model: dict[str, list[float]] = defaultdict(list)
    for attempt in attempts:
        model = str(attempt["model_profile_id"])
        mode = f"{attempt['prompt_mode']}+{attempt['format_mode']}"
        model_counts[model] += 1
        mode_counts[mode] += 1
        source_counts[str(attempt["source"])] += 1
        error_counts[str(attempt["error_category"])] += 1
        if attempt["schema_valid"]:
            valid_by_model[model] += 1
            valid_by_mode[mode] += 1
        if isinstance(attempt.get("elapsed_ms"), int | float):
            elapsed_by_model[model].append(float(attempt["elapsed_ms"]))
    model_rows = []
    for model, count in model_counts.most_common():
        elapsed = elapsed_by_model.get(model, [])
        model_rows.append(
            {
                "model_profile_id": model,
                "attempt_count": count,
                "schema_valid_count": valid_by_model[model],
                "schema_valid_pct": pct(valid_by_model[model], count),
                "mean_elapsed_ms": round(sum(elapsed) / len(elapsed), 2) if elapsed else 0.0,
            }
        )
    mode_rows = []
    for mode, count in mode_counts.most_common():
        mode_rows.append(
            {
                "mode": mode,
                "attempt_count": count,
                "schema_valid_count": valid_by_mode[mode],
                "schema_valid_pct": pct(valid_by_mode[mode], count),
            }
        )
    return {
        "attempt_count": len(attempts),
        "schema_valid_attempt_count": sum(1 for row in attempts if row["schema_valid"]),
        "schema_valid_pct": pct(
            sum(1 for row in attempts if row["schema_valid"]),
            len(attempts),
        ),
        "load_error_count": len(load_errors),
        "error_category_counts": dict(error_counts.most_common()),
        "source_counts": dict(source_counts.most_common()),
        "model_rows": model_rows,
        "mode_rows": mode_rows,
    }


def build_report(schema_path: Path, suite_paths: list[Path]) -> dict[str, Any]:
    schema = load_json(schema_path)
    suites = [load_json(path) for path in suite_paths]
    attempts, load_errors = build_attempts(schema=schema, suites=suites)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated structured-output tuning analysis",
        "source_paths": {
            "schema": "app/llm/contracts/generation_output.schema.json",
            "benchmark_suites": [
                str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
                for path in suite_paths
            ],
            "result_sources": [str(source["path"].relative_to(ROOT)) for source in RESULT_SOURCES],
        },
        "summary": summarize(attempts, load_errors),
        "load_errors": load_errors,
        "attempts": attempts,
    }


def rows_from_counter(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
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
    row_h = 29
    left = 330
    right = 58
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
            f'<text x="{left - 12}" y="{y + 19}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row[label_key])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="19" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 19}" font-size="12" '
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


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    attempt_rows = [
        [
            row["source"],
            row["task_id"],
            row.get("ref") or "",
            row.get("layer") or "",
            row["model_profile_id"],
            row["prompt_mode"],
            row["format_mode"],
            "yes" if row["schema_valid"] else "no",
            row["error_category"],
            row.get("elapsed_ms") or "",
            row.get("raw_text_chars") or 0,
            row.get("error") or row.get("raw_text_preview") or "",
        ]
        for row in report["attempts"]
    ]
    model_rows = [
        [
            row["model_profile_id"],
            row["attempt_count"],
            row["schema_valid_count"],
            f"{row['schema_valid_pct']:.2f}%",
            row["mean_elapsed_ms"],
        ]
        for row in summary["model_rows"]
    ]
    mode_rows = [
        [
            row["mode"],
            row["attempt_count"],
            row["schema_valid_count"],
            f"{row['schema_valid_pct']:.2f}%",
        ]
        for row in summary["mode_rows"]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Structured Output Tuning</title>
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
    .lede {{ max-width: 990px; font-size: 17px; color: #33414c; }}
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
    <h1>AlephTav Structured Output Tuning</h1>
    <p class="lede">
      Real local-output control analysis for the Windows Ollama bridge. The
      goal is to separate schema obedience from translation quality before any
      local model is treated as a candidate translator.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Tuning Summary</h2>
      {
        metric_cards(
            [
                ("Attempts", fmt_int(summary["attempt_count"]), "Real local generations analyzed."),
                (
                    "Schema-valid",
                    fmt_int(summary["schema_valid_attempt_count"]),
                    f'''{summary["schema_valid_pct"]:.2f}% of attempts.''',
                ),
                (
                    "Load errors",
                    fmt_int(summary["load_error_count"]),
                    "JSONL/source loading errors.",
                ),
                (
                    "Error types",
                    fmt_int(len(summary["error_category_counts"])),
                    "Distinct output categories observed.",
                ),
            ]
        )
    }
      <div class="warning">
        Schema validity means the output can be audited. It does not mean the
        translation is correct, accepted, or publication-ready.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["error_category_counts"], "category"),
            label_key="category",
            value_key="count",
            aria_label="Structured output error categories",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            summary["model_rows"],
            label_key="model_profile_id",
            value_key="schema_valid_count",
            aria_label="Schema-valid attempts by model",
            color="#2f6f73",
        )
    }</div>
    </section>

    <section>
      <h2>Model Results</h2>
      {table(["Model", "Attempts", "Valid", "Valid %", "Mean elapsed ms"], model_rows)}
    </section>

    <section>
      <h2>Prompt Modes</h2>
      {table(["Mode", "Attempts", "Valid", "Valid %"], mode_rows)}
    </section>

    <section>
      <h2>Attempts</h2>
      {
        table(
            [
                "Source",
                "Task",
                "Ref",
                "Layer",
                "Model",
                "Prompt",
                "Format",
                "Schema valid",
                "Category",
                "Elapsed ms",
                "Raw chars",
                "Error / preview",
            ],
            attempt_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate structured-output tuning report.")
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("--suite", type=Path, action="append", dest="suites")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suite_paths = args.suites or [source["path"] for source in SUITE_SOURCES]
    report = build_report(args.schema, suite_paths)
    write_json(args.json_output, report)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
