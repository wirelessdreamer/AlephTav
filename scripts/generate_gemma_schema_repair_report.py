from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"

CONTEXTUAL_AUDIT_PATH = REPORT_ROOT / "contextual_expanded_benchmark_result_audit.json"
GEMMA_MODEL_ID = "google/gemma-4-26B-A4B-it"
EXPECTED_EXPANDED_RESULT_COUNT = 784

ATTEMPTS = [
    {
        "attempt_id": "baseline_contextual_schema",
        "label": "Baseline Expanded Schema Probe",
        "description": "Original contextual expanded rows for the local gemma4:26b asset.",
        "audit_path": CONTEXTUAL_AUDIT_PATH,
        "results_path": REPORT_ROOT / "contextual_expanded_benchmark_results.jsonl",
        "layer_path": None,
        "model_filter": GEMMA_MODEL_ID,
    },
    {
        "attempt_id": "generate_json_compact",
        "label": "Generate API + JSON Format",
        "description": "Compact prompt through Ollama generate mode with format=json.",
        "audit_path": REPORT_ROOT / "gemma_schema_repair_json_mode_audit.json",
        "results_path": REPORT_ROOT / "gemma_schema_repair_json_mode_results.jsonl",
        "layer_path": None,
        "model_filter": None,
    },
    {
        "attempt_id": "chat_json_no_thinking",
        "label": "Chat API + JSON + Think False",
        "description": "Compact prompt through Ollama chat mode with format=json and think=false.",
        "audit_path": REPORT_ROOT / "gemma_schema_repair_chat_json_audit.json",
        "results_path": REPORT_ROOT / "gemma_schema_repair_chat_json_results.jsonl",
        "layer_path": REPORT_ROOT / "gemma_schema_repair_chat_json_layer_consistency.json",
        "model_filter": None,
    },
    {
        "attempt_id": "chat_schema_no_thinking",
        "label": "Chat API + Schema + Think False",
        "description": (
            "Compact prompt through Ollama chat mode with full schema format and think=false."
        ),
        "audit_path": REPORT_ROOT / "gemma_schema_repair_chat_schema_audit.json",
        "results_path": REPORT_ROOT / "gemma_schema_repair_chat_schema_results.jsonl",
        "layer_path": REPORT_ROOT / "gemma_schema_repair_chat_schema_layer_consistency.json",
        "model_filter": None,
    },
]

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "gemma_schema_repair_report.json"
DEFAULT_ATTEMPT_CSV_OUTPUT = REPORT_ROOT / "gemma_schema_repair_attempts.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "gemma_schema_repair_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "gemma_schema_repair_report.html"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_json_if_exists(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return load_json(path)


def load_jsonl_if_exists(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
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


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    resolved = path.resolve()
    return str(resolved.relative_to(ROOT)) if resolved.is_relative_to(ROOT) else str(path)


def rows_for_audit(audit: dict[str, Any], model_filter: str | None) -> list[dict[str, Any]]:
    rows = list(audit.get("scored_results", []))
    if model_filter is None:
        return rows
    return [row for row in rows if row.get("model_profile_id") == model_filter]


def audit_metrics(audit: dict[str, Any] | None, model_filter: str | None) -> dict[str, Any]:
    if audit is None:
        return {
            "submitted_result_count": 0,
            "schema_valid_result_count": 0,
            "schema_valid_pct": 0.0,
            "source_anchor_issue_count": 0,
            "source_anchor_clean_pct": 0.0,
            "error_count": 0,
            "mean_elapsed_ms": 0.0,
            "error_category_counts": {},
        }
    rows = rows_for_audit(audit, model_filter)
    submitted = len(rows)
    schema_valid = sum(1 for row in rows if row.get("schema_valid"))
    source_anchor_issues = sum(int(row.get("source_anchor_issue_count") or 0) for row in rows)
    errors = sum(int(row.get("error_count") or 0) for row in rows)
    error_categories: Counter[str] = Counter()
    elapsed_values = []
    for row in rows:
        for error in row.get("errors", []):
            category = str(error).split(":", maxsplit=1)[0]
            error_categories[category] += 1
        elapsed = (row.get("runtime") or {}).get("elapsed_ms")
        if isinstance(elapsed, int | float):
            elapsed_values.append(float(elapsed))
    anchor_clean_rows = max(0, submitted - source_anchor_issues)
    return {
        "submitted_result_count": submitted,
        "schema_valid_result_count": schema_valid,
        "schema_valid_pct": pct(schema_valid, submitted),
        "source_anchor_issue_count": source_anchor_issues,
        "source_anchor_clean_pct": pct(anchor_clean_rows, submitted),
        "error_count": errors,
        "mean_elapsed_ms": round(sum(elapsed_values) / len(elapsed_values), 2)
        if elapsed_values
        else 0.0,
        "error_category_counts": dict(sorted(error_categories.items())),
    }


def layer_metrics(layer_report: dict[str, Any] | None) -> dict[str, Any]:
    if layer_report is None:
        return {
            "paired_unit_model_count": 0,
            "schema_valid_pair_count": 0,
            "exact_duplicate_pair_count": 0,
            "weak_layer_differentiation_pair_count": 0,
            "divine_name_inconsistent_pair_count": 0,
            "mean_word_jaccard_pct": 0.0,
            "mean_layer_risk_score": 0.0,
            "top_layer_risk_ref": "",
            "flag_counts": {},
        }
    summary = layer_report["summary"]
    return {
        "paired_unit_model_count": summary["paired_unit_model_count"],
        "schema_valid_pair_count": summary["schema_valid_pair_count"],
        "exact_duplicate_pair_count": summary["exact_duplicate_pair_count"],
        "weak_layer_differentiation_pair_count": (summary["weak_layer_differentiation_pair_count"]),
        "divine_name_inconsistent_pair_count": summary["divine_name_inconsistent_pair_count"],
        "mean_word_jaccard_pct": summary["mean_word_jaccard_pct"],
        "mean_layer_risk_score": summary["mean_layer_risk_score"],
        "top_layer_risk_ref": summary["top_layer_risk_ref"],
        "flag_counts": summary["flag_counts"],
    }


def output_examples(results_path: Path | None, limit: int = 4) -> list[dict[str, Any]]:
    examples = []
    for row in load_jsonl_if_exists(results_path):
        output = row.get("output") or {}
        candidate = (output.get("candidates") or [{}])[0]
        source_anchor = candidate.get("source_anchor") or {}
        raw_text = str(row.get("raw_text") or "")
        examples.append(
            {
                "task_id": row.get("task_id", ""),
                "schema_parse_error": row.get("error", ""),
                "text": candidate.get("text", ""),
                "source_text_has_byte_markers": (
                    "<0x" in str(source_anchor.get("source_text") or "")
                ),
                "raw_excerpt": raw_text[:240],
            }
        )
        if len(examples) >= limit:
            break
    return examples


def attempt_row(attempt: dict[str, Any]) -> dict[str, Any]:
    audit = load_json_if_exists(attempt["audit_path"])
    layer = load_json_if_exists(attempt["layer_path"])
    metrics = audit_metrics(audit, attempt["model_filter"])
    layers = layer_metrics(layer)
    return {
        "attempt_id": attempt["attempt_id"],
        "label": attempt["label"],
        "description": attempt["description"],
        "status": "generated" if audit is not None else "missing_audit",
        **metrics,
        **layers,
        "expanded_evidence_depth_pct": pct(
            metrics["submitted_result_count"],
            EXPECTED_EXPANDED_RESULT_COUNT,
        ),
        "audit_path": rel(attempt["audit_path"]),
        "results_path": rel(attempt["results_path"]),
        "layer_path": rel(attempt["layer_path"]),
        "examples": output_examples(attempt["results_path"]),
    }


def best_schema_attempt(rows: list[dict[str, Any]]) -> dict[str, Any]:
    generated = [row for row in rows if row["status"] == "generated"]
    if not generated:
        return rows[0]
    return max(
        generated,
        key=lambda row: (
            float(row["schema_valid_pct"]),
            int(row["submitted_result_count"]),
            -int(row["source_anchor_issue_count"]),
            -int(row["weak_layer_differentiation_pair_count"]),
        ),
    )


def gate_rows(best_attempt: dict[str, Any]) -> list[dict[str, Any]]:
    submitted = int(best_attempt["submitted_result_count"])
    source_anchor_issues = int(best_attempt["source_anchor_issue_count"])
    weak_pairs = int(best_attempt["weak_layer_differentiation_pair_count"])
    return [
        {
            "gate": "schema_admission",
            "status": "pass" if best_attempt["schema_valid_pct"] == 100.0 else "fail",
            "score_pct": best_attempt["schema_valid_pct"],
            "evidence": (
                f"{best_attempt['schema_valid_result_count']} of {submitted} rows "
                f"schema-valid in {best_attempt['label']}."
            ),
            "next_action": "Use chat mode with think=false for any further Gemma probes.",
        },
        {
            "gate": "source_anchor_integrity",
            "status": "fail" if source_anchor_issues else "pass",
            "score_pct": best_attempt["source_anchor_clean_pct"],
            "evidence": (
                f"{source_anchor_issues} source-anchor mismatch(es); pointed Hebrew "
                "was emitted with byte-marker fragments on Psalm 2:7."
            ),
            "next_action": (
                "Either repair prompting for exact Hebrew echoing or move source anchors "
                "to deterministic wrapper metadata before scaling."
            ),
        },
        {
            "gate": "layer_differentiation",
            "status": "fail" if weak_pairs else "pass",
            "score_pct": pct(
                int(best_attempt["paired_unit_model_count"]) - weak_pairs,
                int(best_attempt["paired_unit_model_count"]),
            ),
            "evidence": (
                f"{weak_pairs} weak gloss/literal pair(s); mean word overlap "
                f"{best_attempt['mean_word_jaccard_pct']:.2f}%."
            ),
            "next_action": "Keep layer-separation gates ahead of any quality bakeoff.",
        },
        {
            "gate": "sample_depth",
            "status": "partial" if submitted >= 4 else "fail",
            "score_pct": best_attempt["expanded_evidence_depth_pct"],
            "evidence": (
                f"{submitted} repair rows cover "
                f"{best_attempt['expanded_evidence_depth_pct']:.2f}% of the expanded "
                "784-row planned bakeoff."
            ),
            "next_action": "Expand only after source-anchor and layer gates pass on stress pairs.",
        },
        {
            "gate": "authority_claim",
            "status": "blocked",
            "score_pct": 0.0,
            "evidence": "This is runtime repair evidence, not translation authority evidence.",
            "next_action": (
                "Require reviewer signoff and cross-model adjudication for authority use."
            ),
        },
    ]


def build_report() -> dict[str, Any]:
    attempt_rows = [attempt_row(attempt) for attempt in ATTEMPTS]
    best = best_schema_attempt(attempt_rows)
    gates = gate_rows(best)
    baseline = next(
        row for row in attempt_rows if row["attempt_id"] == "baseline_contextual_schema"
    )
    chat_json = next(row for row in attempt_rows if row["attempt_id"] == "chat_json_no_thinking")
    summary = {
        "model": GEMMA_MODEL_ID,
        "attempt_count": len(attempt_rows),
        "generated_attempt_count": sum(1 for row in attempt_rows if row["status"] == "generated"),
        "baseline_schema_valid_pct": baseline["schema_valid_pct"],
        "best_schema_attempt_id": best["attempt_id"],
        "best_schema_attempt_label": best["label"],
        "best_schema_valid_pct": best["schema_valid_pct"],
        "best_source_anchor_issue_count": best["source_anchor_issue_count"],
        "best_source_anchor_clean_pct": best["source_anchor_clean_pct"],
        "best_weak_layer_differentiation_pair_count": (
            best["weak_layer_differentiation_pair_count"]
        ),
        "chat_json_schema_valid_pct": chat_json["schema_valid_pct"],
        "chat_json_source_anchor_issue_count": chat_json["source_anchor_issue_count"],
        "chat_json_weak_layer_differentiation_pair_count": (
            chat_json["weak_layer_differentiation_pair_count"]
        ),
        "gate_count": len(gates),
        "failed_gate_count": sum(1 for row in gates if row["status"] in {"fail", "blocked"}),
        "failed_gates": [row["gate"] for row in gates if row["status"] in {"fail", "blocked"}],
        "recommended_status": "schema_repaired_source_anchor_and_layer_blocked",
        "next_action": (
            "Keep Gemma 4 26B as a runnable repair candidate, but do not treat it as "
            "the quality baseline until source anchors and layer differentiation pass."
        ),
    }
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "Gemma schema repair evidence; not model approval",
        "source_paths": {
            "contextual_audit": rel(CONTEXTUAL_AUDIT_PATH),
            "repair_json_audit": rel(REPORT_ROOT / "gemma_schema_repair_chat_json_audit.json"),
            "repair_json_layer": rel(
                REPORT_ROOT / "gemma_schema_repair_chat_json_layer_consistency.json"
            ),
            "repair_schema_audit": rel(REPORT_ROOT / "gemma_schema_repair_chat_schema_audit.json"),
            "repair_schema_layer": rel(
                REPORT_ROOT / "gemma_schema_repair_chat_schema_layer_consistency.json"
            ),
        },
        "summary": summary,
        "attempt_rows": attempt_rows,
        "gate_rows": gates,
    }


def svg_attempt_chart(rows: list[dict[str, Any]]) -> str:
    width = 1100
    height = 330
    left = 76
    right = 30
    top = 34
    bottom = 94
    chart_w = width - left - right
    chart_h = height - top - bottom
    group_gap = 34
    bar_gap = 8
    group_w = (chart_w - group_gap * (len(rows) - 1)) / len(rows)
    bar_w = (group_w - bar_gap) / 2
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Gemma repair schema and source-anchor chart">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for tick in range(0, 101, 25):
        y = top + chart_h - chart_h * tick / 100
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#d9e0e5"/>'
        )
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" '
            'font-size="11" fill="#5d6972">'
            f"{tick}%</text>"
        )
    for index, row in enumerate(rows):
        x = left + index * (group_w + group_gap)
        for offset, value, color, label in [
            (0, float(row["schema_valid_pct"]), "#2f6f73", "schema"),
            (
                bar_w + bar_gap,
                float(row["source_anchor_clean_pct"]),
                "#7c5b2f",
                "anchor",
            ),
        ]:
            bar_h = chart_h * value / 100
            y = top + chart_h - bar_h
            parts.append(
                f'<rect x="{x + offset:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                f'height="{bar_h:.1f}" rx="3" fill="{color}"/>'
            )
            parts.append(
                f'<text x="{x + offset + bar_w / 2:.1f}" y="{y - 6:.1f}" '
                'text-anchor="middle" font-size="10" font-weight="700" fill="#25313a">'
                f"{value:.0f}</text>"
            )
            parts.append(
                f'<text x="{x + offset + bar_w / 2:.1f}" y="{top + chart_h + 16}" '
                'text-anchor="middle" font-size="9" fill="#5d6972">'
                f"{label}</text>"
            )
        parts.append(
            f'<text x="{x + group_w / 2:.1f}" y="{top + chart_h + 34}" '
            'text-anchor="middle" font-size="10" fill="#25313a">'
            f"{esc(row['attempt_id'])}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
        + "</tbody></table>"
    )


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    attempts = report["attempt_rows"]
    gates = report["gate_rows"]
    attempt_table = table(
        [
            "Attempt",
            "Rows",
            "Schema",
            "Anchor clean",
            "Weak pairs",
            "Mean overlap",
            "Evidence",
        ],
        [
            [
                f"<strong>{esc(row['label'])}</strong><br><span>{esc(row['description'])}</span>",
                f'<span class="num">{row["submitted_result_count"]}</span>',
                f'<span class="num">{float(row["schema_valid_pct"]):.2f}%</span>',
                f'<span class="num">{float(row["source_anchor_clean_pct"]):.2f}%</span>',
                f'<span class="num">{row["weak_layer_differentiation_pair_count"]}</span>',
                f'<span class="num">{float(row["mean_word_jaccard_pct"]):.2f}%</span>',
                esc(row["audit_path"]),
            ]
            for row in attempts
        ],
    )
    gate_table = table(
        ["Gate", "Status", "Score", "Evidence", "Next action"],
        [
            [
                esc(row["gate"]),
                esc(row["status"]),
                f'<span class="num">{float(row["score_pct"]):.2f}%</span>',
                esc(row["evidence"]),
                esc(row["next_action"]),
            ]
            for row in gates
        ],
    )
    examples = []
    for row in attempts:
        for example in row["examples"]:
            if example["text"] or example["schema_parse_error"]:
                examples.append((row, example))
    example_table = table(
        ["Attempt", "Task", "Output text", "Source marker issue", "Parse error"],
        [
            [
                esc(row["label"]),
                esc(example["task_id"]),
                esc(example["text"] or example["raw_excerpt"]),
                esc(example["source_text_has_byte_markers"]),
                esc(example["schema_parse_error"]),
            ]
            for row, example in examples[:10]
        ],
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Gemma Schema Repair Report</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2a33;
      --muted: #64727d;
      --line: #d8e0e6;
      --band: #f4f7f8;
      --accent: #2f6f73;
      --warn: #9b3d3d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #fff;
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
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 22px 0; }}
    .card {{ border: 1px solid var(--line); border-radius: 6px; padding: 16px; background: #fff; }}
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
    td span {{ color: var(--muted); font-size: 11px; }}
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
    <h1>AlephTav Gemma Schema Repair Report</h1>
    <p class="lede">
      A targeted audit of whether the local Gemma 4 26B Ollama asset can be
      admitted into the Hebrew-to-English Psalms benchmark after runtime and
      prompt-mode repair.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}. This is not model approval.</p>
  </header>
  <main>
    <section>
      <h2>Repair Finding</h2>
      <div class="grid">
        <div class="card">
          <div class="metric">{float(summary["baseline_schema_valid_pct"]):.0f}%</div>
          <div class="label">Baseline schema</div>
        </div>
        <div class="card">
          <div class="metric">{float(summary["best_schema_valid_pct"]):.0f}%</div>
          <div class="label">Best schema</div>
        </div>
        <div class="card">
          <div class="metric">{summary["best_source_anchor_issue_count"]}</div>
          <div class="label">Anchor issues</div>
        </div>
        <div class="card">
          <div class="metric">{summary["best_weak_layer_differentiation_pair_count"]}</div>
          <div class="label">Weak pairs</div>
        </div>
      </div>
      <div class="warning">
        <strong>Decision:</strong> {esc(summary["next_action"])}
      </div>
    </section>

    <section>
      <h2>Attempt Comparison</h2>
      <div class="chart">{svg_attempt_chart(attempts)}</div>
      {attempt_table}
    </section>

    <section>
      <h2>Admission Gates</h2>
      {gate_table}
    </section>

    <section>
      <h2>Output Examples</h2>
      {example_table}
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Gemma schema repair report.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--attempt-csv-output", type=Path, default=DEFAULT_ATTEMPT_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    args = parse_args()
    report = build_report()
    json_output = resolve(args.json_output)
    attempt_csv_output = resolve(args.attempt_csv_output)
    gate_csv_output = resolve(args.gate_csv_output)
    html_output = resolve(args.html_output)
    write_json(json_output, report)
    write_csv(attempt_csv_output, report["attempt_rows"])
    write_csv(gate_csv_output, report["gate_rows"])
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(render_html(report), encoding="utf-8")
    print(json_output)
    print(attempt_csv_output)
    print(gate_csv_output)
    print(html_output)


if __name__ == "__main__":
    main()
