from __future__ import annotations

import argparse
import csv
import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"

BASELINE_LAYER_PATH = REPORT_ROOT / "layer_consistency_report.json"
REMEDIATION_PLAN_PATH = REPORT_ROOT / "layer_remediation_plan.json"
ATTEMPTS = [
    {
        "attempt_id": "retry_v1_layer_contract",
        "label": "Retry v1 Layer Contract",
        "results_path": REPORT_ROOT / "layer_remediation_retry_results.jsonl",
        "audit_path": REPORT_ROOT / "layer_remediation_retry_result_audit.json",
        "layer_path": REPORT_ROOT / "layer_remediation_retry_layer_consistency.json",
    },
    {
        "attempt_id": "retry_v2_pipe_gloss",
        "label": "Retry v2 Pipe Gloss",
        "results_path": REPORT_ROOT / "layer_remediation_retry_v2_results.jsonl",
        "audit_path": REPORT_ROOT / "layer_remediation_retry_v2_result_audit.json",
        "layer_path": REPORT_ROOT / "layer_remediation_retry_v2_layer_consistency.json",
    },
    {
        "attempt_id": "retry_v3_grammatical_literal",
        "label": "Retry v3 Grammatical Literal",
        "results_path": REPORT_ROOT / "layer_remediation_retry_v3_results.jsonl",
        "audit_path": REPORT_ROOT / "layer_remediation_retry_v3_result_audit.json",
        "layer_path": REPORT_ROOT / "layer_remediation_retry_v3_layer_consistency.json",
    },
]

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "layer_remediation_experiment_report.json"
DEFAULT_ATTEMPT_CSV_OUTPUT = REPORT_ROOT / "layer_remediation_experiment_attempts.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "layer_remediation_experiment_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "layer_remediation_experiment_report.html"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
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


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def rel(path: Path) -> str:
    resolved = path.resolve()
    return str(resolved.relative_to(ROOT)) if resolved.is_relative_to(ROOT) else str(path)


def baseline_target_row(layer_report: dict[str, Any], unit_id: str) -> dict[str, Any]:
    for row in layer_report.get("pair_rows", []):
        if row.get("unit_id") == unit_id:
            return row
    return {}


def first_pair(layer_report: dict[str, Any]) -> dict[str, Any]:
    rows = layer_report.get("pair_rows", [])
    return rows[0] if rows else {}


def has_pipe_gloss(pair: dict[str, Any]) -> bool:
    return "|" in str(pair.get("gloss_text") or "")


def attempt_row(attempt: dict[str, Any]) -> dict[str, Any]:
    audit = load_json_if_exists(attempt["audit_path"])
    layer = load_json_if_exists(attempt["layer_path"])
    if audit is None or layer is None:
        return {
            "attempt_id": attempt["attempt_id"],
            "label": attempt["label"],
            "status": "missing_artifacts",
            "submitted_result_count": 0,
            "schema_valid_result_count": 0,
            "schema_valid_pct": 0.0,
            "source_anchor_issue_count": 0,
            "paired_unit_model_count": 0,
            "exact_duplicate_pair_count": 0,
            "near_duplicate_pair_count": 0,
            "weak_layer_differentiation_pair_count": 0,
            "divine_name_inconsistent_pair_count": 0,
            "mean_word_jaccard_pct": 0.0,
            "mean_layer_risk_score": 0.0,
            "gloss_pipe_marker_pair_count": 0,
            "top_ref": "",
            "top_unit_id": "",
            "gloss_text": "",
            "literal_text": "",
            "results_path": rel(attempt["results_path"]),
            "audit_path": rel(attempt["audit_path"]),
            "layer_path": rel(attempt["layer_path"]),
        }
    pair = first_pair(layer)
    summary = layer["summary"]
    audit_summary = audit["summary"]
    return {
        "attempt_id": attempt["attempt_id"],
        "label": attempt["label"],
        "status": "generated",
        "submitted_result_count": audit_summary["submitted_result_count"],
        "schema_valid_result_count": audit_summary["schema_valid_result_count"],
        "schema_valid_pct": audit_summary["schema_valid_pct"],
        "source_anchor_issue_count": audit_summary.get("source_anchor_issue_count", 0),
        "paired_unit_model_count": summary["paired_unit_model_count"],
        "exact_duplicate_pair_count": summary["exact_duplicate_pair_count"],
        "near_duplicate_pair_count": summary["near_duplicate_pair_count"],
        "weak_layer_differentiation_pair_count": (summary["weak_layer_differentiation_pair_count"]),
        "divine_name_inconsistent_pair_count": (summary["divine_name_inconsistent_pair_count"]),
        "mean_word_jaccard_pct": summary["mean_word_jaccard_pct"],
        "mean_layer_risk_score": summary["mean_layer_risk_score"],
        "gloss_pipe_marker_pair_count": 1 if has_pipe_gloss(pair) else 0,
        "top_ref": summary["top_layer_risk_ref"],
        "top_unit_id": summary["top_layer_risk_unit"],
        "gloss_text": pair.get("gloss_text", ""),
        "literal_text": pair.get("literal_text", ""),
        "results_path": rel(attempt["results_path"]),
        "audit_path": rel(attempt["audit_path"]),
        "layer_path": rel(attempt["layer_path"]),
    }


def gate_rows(
    *,
    baseline_pair: dict[str, Any],
    best_attempt: dict[str, Any],
) -> list[dict[str, Any]]:
    baseline_exact = bool(baseline_pair.get("exact_duplicate"))
    return [
        {
            "gate": "schema_validity",
            "status": "pass" if best_attempt["schema_valid_pct"] == 100.0 else "fail",
            "evidence": (
                f"{best_attempt['schema_valid_result_count']} of "
                f"{best_attempt['submitted_result_count']} retry rows schema-valid."
            ),
            "next_action": "Keep schema format mode and compact candidate count at 1.",
        },
        {
            "gate": "source_anchor_integrity",
            "status": "pass" if best_attempt["source_anchor_issue_count"] == 0 else "fail",
            "evidence": f"{best_attempt['source_anchor_issue_count']} source-anchor issues.",
            "next_action": "Do not relax source-anchor checks.",
        },
        {
            "gate": "exact_duplicate_removal",
            "status": (
                "pass"
                if baseline_exact and best_attempt["exact_duplicate_pair_count"] == 0
                else "fail"
            ),
            "evidence": (
                f"Baseline exact duplicate: {baseline_exact}; best retry exact "
                f"duplicates: {best_attempt['exact_duplicate_pair_count']}."
            ),
            "next_action": "Retain explicit layer contracts in benchmark prompts.",
        },
        {
            "gate": "gloss_structural_marker",
            "status": "pass" if best_attempt["gloss_pipe_marker_pair_count"] else "fail",
            "evidence": (
                f"{best_attempt['gloss_pipe_marker_pair_count']} paired retry rows "
                "use pipe-separated gloss structure."
            ),
            "next_action": "Keep pipe-separated gloss instruction for compact prompts.",
        },
        {
            "gate": "weak_layer_differentiation",
            "status": (
                "pass" if best_attempt["weak_layer_differentiation_pair_count"] == 0 else "fail"
            ),
            "evidence": (
                f"{best_attempt['weak_layer_differentiation_pair_count']} weak "
                f"differentiation pairs; mean overlap "
                f"{best_attempt['mean_word_jaccard_pct']:.2f}%."
            ),
            "next_action": (
                "Add a layer-aware scoring gate and rerun more than one pair only "
                "after the single-pair weak-differentiation gate passes."
            ),
        },
        {
            "gate": "divine_name_consistency",
            "status": (
                "pass" if best_attempt["divine_name_inconsistent_pair_count"] == 0 else "fail"
            ),
            "evidence": (
                f"{best_attempt['divine_name_inconsistent_pair_count']} visible "
                "divine-name differences across paired retry rows."
            ),
            "next_action": "Keep divine-name policy review in the human review route.",
        },
    ]


def best_attempt(rows: list[dict[str, Any]]) -> dict[str, Any]:
    generated = [row for row in rows if row["status"] == "generated"]
    if not generated:
        return rows[0] if rows else {}
    return sorted(
        generated,
        key=lambda row: (
            row["weak_layer_differentiation_pair_count"],
            row["exact_duplicate_pair_count"],
            -row["gloss_pipe_marker_pair_count"],
            row["mean_layer_risk_score"],
        ),
    )[0]


def build_report(
    *,
    baseline_layer_path: Path,
    remediation_plan_path: Path,
) -> dict[str, Any]:
    baseline = load_json(baseline_layer_path)
    remediation = load_json(remediation_plan_path)
    rows = [attempt_row(attempt) for attempt in ATTEMPTS]
    best = best_attempt(rows)
    target_unit = best.get("top_unit_id") or remediation["summary"].get("top_retry_task") or ""
    baseline_pair = baseline_target_row(baseline, str(target_unit)) or baseline_target_row(
        baseline, "ps002.v007.a"
    )
    gates = gate_rows(baseline_pair=baseline_pair, best_attempt=best) if best else []
    failed_gates = [row["gate"] for row in gates if row["status"] != "pass"]
    summary = {
        "attempt_count": len(rows),
        "generated_attempt_count": sum(1 for row in rows if row["status"] == "generated"),
        "best_attempt_id": best.get("attempt_id"),
        "best_attempt_label": best.get("label"),
        "best_attempt_schema_valid_pct": best.get("schema_valid_pct", 0.0),
        "best_attempt_exact_duplicate_pair_count": best.get("exact_duplicate_pair_count", 0),
        "best_attempt_weak_layer_differentiation_pair_count": best.get(
            "weak_layer_differentiation_pair_count", 0
        ),
        "best_attempt_mean_word_jaccard_pct": best.get("mean_word_jaccard_pct", 0.0),
        "best_attempt_gloss_pipe_marker_pair_count": best.get("gloss_pipe_marker_pair_count", 0),
        "baseline_target_unit": baseline_pair.get("unit_id"),
        "baseline_target_ref": baseline_pair.get("ref"),
        "baseline_target_exact_duplicate": baseline_pair.get("exact_duplicate"),
        "baseline_target_word_jaccard_pct": baseline_pair.get("word_jaccard_pct"),
        "gate_count": len(gates),
        "failed_gate_count": len(failed_gates),
        "failed_gates": failed_gates,
        "experiment_status": (
            "partial_improvement_not_sufficient" if failed_gates else "single_pair_probe_passed"
        ),
    }
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "post-remediation experiment report; not release evidence",
        "source_paths": {
            "baseline_layer": rel(baseline_layer_path),
            "remediation_plan": rel(remediation_plan_path),
        },
        "method_notes": [
            "Compares a single paired retry probe against the original layer audit.",
            "A pass here would authorize broader retry, not human translation signoff.",
            "The current experiment is intentionally separate from the original result stream.",
        ],
        "summary": summary,
        "attempt_rows": rows,
        "gate_rows": gates,
    }


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    width: int = 980,
) -> str:
    row_h = 32
    left = 230
    right = 70
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
            f'<text x="{left - 12}" y="{y + 20}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row[label_key])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="20" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 20}" font-size="12" '
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


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    attempt_table = [
        [
            row["label"],
            row["schema_valid_pct"],
            row["exact_duplicate_pair_count"],
            row["weak_layer_differentiation_pair_count"],
            f"{row['mean_word_jaccard_pct']:.2f}%",
            row["gloss_pipe_marker_pair_count"],
            row["gloss_text"],
            row["literal_text"],
        ]
        for row in report["attempt_rows"]
    ]
    gate_table = [
        [row["gate"], row["status"], row["evidence"], row["next_action"]]
        for row in report["gate_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Layer Remediation Experiment</title>
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
    <h1>AlephTav Layer Remediation Experiment</h1>
    <p class="lede">
      Before/after probe over Psalm 2:7 using separate retry result streams.
      The experiment measures whether prompt controls reduce gloss/literal
      collapse without breaking schema validity or source anchoring.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Experiment Result</h2>
      {
        metric_cards(
            [
                (
                    "Best attempt",
                    summary["best_attempt_label"],
                    summary["experiment_status"],
                ),
                (
                    "Schema",
                    f'''{summary["best_attempt_schema_valid_pct"]:.2f}%''',
                    "Best retry schema-valid rate.",
                ),
                (
                    "Weak diff",
                    fmt_int(summary["best_attempt_weak_layer_differentiation_pair_count"]),
                    f'''Mean overlap {summary["best_attempt_mean_word_jaccard_pct"]:.2f}%.''',
                ),
                (
                    "Failed gates",
                    fmt_int(summary["failed_gate_count"]),
                    ", ".join(summary["failed_gates"]) or "none",
                ),
            ]
        )
    }
      <div class="warning">
        The experiment is a partial improvement: exact duplication is gone and
        v3 produces a pipe-separated gloss plus a grammatical literal, but the
        conservative weak layer-differentiation gate still fails. Broader
        retries should wait for this single-pair gate to pass.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            report["attempt_rows"],
            label_key="label",
            value_key="mean_word_jaccard_pct",
            aria_label="Retry attempt mean word overlap",
            color="#7c5b2f",
        )
    }</div>
    </section>
    <section>
      <h2>Gate Results</h2>
      {table(["Gate", "Status", "Evidence", "Next Action"], gate_table)}
    </section>
    <section>
      <h2>Attempt Outputs</h2>
      {
        table(
            [
                "Attempt",
                "Schema %",
                "Exact Dupes",
                "Weak Diff",
                "Overlap",
                "Pipe Gloss",
                "Gloss",
                "Literal",
            ],
            attempt_table,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate post-remediation layer experiment report."
    )
    parser.add_argument("--baseline-layer", type=Path, default=BASELINE_LAYER_PATH)
    parser.add_argument("--remediation-plan", type=Path, default=REMEDIATION_PLAN_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument(
        "--attempt-csv-output",
        type=Path,
        default=DEFAULT_ATTEMPT_CSV_OUTPUT,
    )
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        baseline_layer_path=args.baseline_layer,
        remediation_plan_path=args.remediation_plan,
    )
    write_json(args.json_output, report)
    write_csv(args.attempt_csv_output, report["attempt_rows"])
    write_csv(args.gate_csv_output, report["gate_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.attempt_csv_output}")
    print(f"Wrote {args.gate_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
