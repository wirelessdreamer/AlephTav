from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "reports" / "research" / "local_model_benchmark_result_audit.json"
RESULTS_PATH = ROOT / "reports" / "research" / "local_model_benchmark_results.jsonl"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "real_model_smoke_test_report.json"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "real_model_smoke_test_report.html"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                rows.append(json.loads(text))
            except json.JSONDecodeError:
                continue
    return rows


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


def runtime_by_key(results: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = {}
    for row in results:
        key = (str(row.get("task_id") or ""), str(row.get("model_profile_id") or ""))
        if key[0] and key[1]:
            rows[key] = row.get("runtime") or {}
    return rows


def summarize_by_model(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    valid: Counter[str] = Counter()
    candidates: Counter[str] = Counter()
    invalid_refs: Counter[str] = Counter()
    anchor_issues: Counter[str] = Counter()
    align_scores: dict[str, list[float]] = defaultdict(list)
    basis_scores: dict[str, list[float]] = defaultdict(list)
    for row in scored:
        model = str(row["model_profile_id"])
        counts[model] += 1
        candidates[model] += int(row.get("candidate_count") or 0)
        invalid_refs[model] += int(row.get("invalid_token_ref_count") or 0)
        anchor_issues[model] += int(row.get("source_anchor_issue_count") or 0)
        if row.get("schema_valid"):
            valid[model] += 1
        align_scores[model].append(float(row.get("mean_alignment_score_0_5") or 0.0))
        basis_scores[model].append(float(row.get("mean_translation_basis_score_0_5") or 0.0))
    model_rows = []
    for model, count in counts.most_common():
        model_rows.append(
            {
                "model_profile_id": model,
                "submitted_results": count,
                "schema_valid_results": valid[model],
                "schema_valid_pct": pct(valid[model], count),
                "candidate_count": candidates[model],
                "invalid_token_ref_count": invalid_refs[model],
                "source_anchor_issue_count": anchor_issues[model],
                "mean_alignment_score_0_5": round(
                    sum(align_scores[model]) / len(align_scores[model]),
                    2,
                ),
                "mean_translation_basis_score_0_5": round(
                    sum(basis_scores[model]) / len(basis_scores[model]),
                    2,
                ),
            }
        )
    return model_rows


def task_rows(scored: list[dict[str, Any]], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    runtimes = runtime_by_key(results)
    rows = []
    for row in scored:
        key = (str(row["task_id"]), str(row["model_profile_id"]))
        runtime = runtimes.get(key, {})
        rows.append(
            {
                "task_id": row["task_id"],
                "model_profile_id": row["model_profile_id"],
                "schema_valid": row["schema_valid"],
                "candidate_count": row["candidate_count"],
                "mean_alignment_score_0_5": row["mean_alignment_score_0_5"],
                "mean_translation_basis_score_0_5": row["mean_translation_basis_score_0_5"],
                "invalid_token_ref_count": row["invalid_token_ref_count"],
                "source_anchor_issue_count": row.get("source_anchor_issue_count", 0),
                "reception_leak_term_count": row["reception_leak_term_count"],
                "error_count": row["error_count"],
                "errors": row["errors"],
                "elapsed_ms": runtime.get("elapsed_ms"),
                "prompt_mode": runtime.get("prompt_mode") or "full",
                "format_mode": runtime.get("format_mode") or "schema",
            }
        )
    return rows


def build_report(audit_path: Path, results_path: Path) -> dict[str, Any]:
    audit = load_json(audit_path)
    results = load_jsonl(results_path)
    scored = audit.get("scored_results", [])
    rows = task_rows(scored, results)
    valid_rows = [row for row in rows if row["schema_valid"]]
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated real local model smoke-test report; not human review",
        "source_paths": {
            "audit": "reports/research/local_model_benchmark_result_audit.json",
            "results": "reports/research/local_model_benchmark_results.jsonl",
        },
        "summary": {
            **audit["summary"],
            "valid_result_alignment_mean": round(
                sum(float(row["mean_alignment_score_0_5"]) for row in valid_rows) / len(valid_rows),
                2,
            )
            if valid_rows
            else 0.0,
            "valid_result_translation_basis_mean": round(
                sum(float(row["mean_translation_basis_score_0_5"]) for row in valid_rows)
                / len(valid_rows),
                2,
            )
            if valid_rows
            else 0.0,
            "valid_result_invalid_token_refs": sum(
                int(row["invalid_token_ref_count"]) for row in valid_rows
            ),
            "valid_result_source_anchor_issues": sum(
                int(row["source_anchor_issue_count"]) for row in valid_rows
            ),
        },
        "model_rows": summarize_by_model(scored),
        "task_rows": rows,
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
    model_rows = [
        [
            row["model_profile_id"],
            row["submitted_results"],
            row["schema_valid_results"],
            f"{row['schema_valid_pct']:.2f}%",
            row["candidate_count"],
            row["mean_alignment_score_0_5"],
            row["mean_translation_basis_score_0_5"],
            row["invalid_token_ref_count"],
            row["source_anchor_issue_count"],
        ]
        for row in report["model_rows"]
    ]
    task_rows = [
        [
            row["task_id"],
            row["model_profile_id"],
            "yes" if row["schema_valid"] else "no",
            row["mean_alignment_score_0_5"],
            row["mean_translation_basis_score_0_5"],
            row["invalid_token_ref_count"],
            row["source_anchor_issue_count"],
            row["prompt_mode"],
            row["format_mode"],
            row.get("elapsed_ms") or "",
        ]
        for row in report["task_rows"]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Real Model Smoke Test</title>
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
    <h1>AlephTav Real Model Smoke Test</h1>
    <p class="lede">
      Early real local benchmark output audit. This report measures schema
      validity and automatic traceability only; it is not human review and does
      not approve translation quality.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Smoke Summary</h2>
      {
        metric_cards(
            [
                (
                    "Submitted",
                    fmt_int(summary["submitted_result_count"]),
                    "Real local result rows.",
                ),
                (
                    "Schema-valid",
                    fmt_int(summary["schema_valid_result_count"]),
                    f'''{summary["schema_valid_pct"]:.2f}% of submitted rows.''',
                ),
                (
                    "Alignment",
                    f'''{summary["valid_result_alignment_mean"]:.2f}/5''',
                    "Mean automatic score among schema-valid rows.",
                ),
                (
                    "Invalid refs",
                    fmt_int(summary["valid_result_invalid_token_refs"]),
                    "Invalid token refs among schema-valid rows.",
                ),
                (
                    "Anchor issues",
                    fmt_int(summary["valid_result_source_anchor_issues"]),
                    "Source-anchor problems among schema-valid rows.",
                ),
            ]
        )
    }
      <div class="warning">
        These are automated gate metrics. Human lexical, Hebrew, alignment,
        lyric, and theology review still controls signoff.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            report["model_rows"],
            label_key="model_profile_id",
            value_key="schema_valid_results",
            aria_label="Schema-valid real results by model",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            report["model_rows"],
            label_key="model_profile_id",
            value_key="mean_alignment_score_0_5",
            aria_label="Mean alignment score by model",
            color="#7c5b2f",
        )
    }</div>
    </section>

    <section>
      <h2>Model Summary</h2>
      {
        table(
            [
                "Model",
                "Submitted",
                "Valid",
                "Valid %",
                "Candidates",
                "Align",
                "Basis",
                "Invalid refs",
                "Anchor issues",
            ],
            model_rows,
        )
    }
    </section>

    <section>
      <h2>Task Rows</h2>
      {
        table(
            [
                "Task",
                "Model",
                "Valid",
                "Align",
                "Basis",
                "Invalid refs",
                "Anchor issues",
                "Prompt",
                "Format",
                "Elapsed ms",
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
    parser = argparse.ArgumentParser(description="Generate real model smoke-test report.")
    parser.add_argument("--audit", type=Path, default=AUDIT_PATH)
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.audit, args.results)
    write_json(args.json_output, report)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
