from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"

SUITE_PATH = REPORT_ROOT / "canonical_intertext_benchmark_supplement_suite.json"
ATTEMPTS = [
    {
        "attempt_id": "mistral_small_3_2_500_token_truncation_probe",
        "label": "Mistral Small 3.2 compact/json 500-token probe",
        "model_profile_id": "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        "model_family": "Mistral Small",
        "result_path": REPORT_ROOT
        / "canonical_intertext_benchmark_supplement_results_mistral_smoke.jsonl",
        "audit_path": REPORT_ROOT
        / "canonical_intertext_benchmark_supplement_result_audit_mistral_smoke.json",
        "purpose": "Measure whether a small output budget truncates canonical-intertext JSON.",
        "run_profile": "compact prompt; chat API; JSON mode; candidate_count=1; max_tokens=500",
    },
    {
        "attempt_id": "mistral_small_3_2_1200_token_valid_smoke",
        "label": "Mistral Small 3.2 compact/json 1200-token smoke",
        "model_profile_id": "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        "model_family": "Mistral Small",
        "result_path": REPORT_ROOT
        / "canonical_intertext_benchmark_supplement_results_mistral_smoke_v2.jsonl",
        "audit_path": REPORT_ROOT
        / "canonical_intertext_benchmark_supplement_result_audit_mistral_smoke_v2.json",
        "purpose": "Check whether a larger output budget yields valid anchored JSON.",
        "run_profile": "compact prompt; chat API; JSON mode; candidate_count=1; max_tokens=1200",
    },
    {
        "attempt_id": "gemma4_26b_1200_token_valid_smoke",
        "label": "Gemma 4 26B compact/json/think=false 1200-token smoke",
        "model_profile_id": "google/gemma-4-26B-A4B-it",
        "model_family": "Gemma 4",
        "result_path": REPORT_ROOT
        / "canonical_intertext_benchmark_supplement_results_gemma4_26b_smoke.jsonl",
        "audit_path": REPORT_ROOT
        / "canonical_intertext_benchmark_supplement_result_audit_gemma4_26b_smoke.json",
        "purpose": "Check Gemma as the locally runnable candidate on the same task.",
        "run_profile": (
            "compact prompt; chat API; JSON mode; think=false; candidate_count=1; max_tokens=1200"
        ),
    },
    {
        "attempt_id": "mistral_small_3_2_full_context_smoke",
        "label": "Mistral Small 3.2 full-context canonical smoke",
        "model_profile_id": "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        "model_family": "Mistral Small",
        "result_path": REPORT_ROOT
        / "canonical_intertext_benchmark_supplement_results_mistral_full_smoke.jsonl",
        "audit_path": REPORT_ROOT
        / "canonical_intertext_benchmark_supplement_result_audit_mistral_full_smoke.json",
        "purpose": "Measure full canonical-intertext context with the repaired output contract.",
        "run_profile": "full prompt; chat API; JSON mode; candidate_count=1; max_tokens=1400",
    },
    {
        "attempt_id": "gemma4_26b_full_context_smoke",
        "label": "Gemma 4 26B full-context canonical smoke",
        "model_profile_id": "google/gemma-4-26B-A4B-it",
        "model_family": "Gemma 4",
        "result_path": REPORT_ROOT
        / "canonical_intertext_benchmark_supplement_results_gemma4_26b_full_smoke.jsonl",
        "audit_path": REPORT_ROOT
        / "canonical_intertext_benchmark_supplement_result_audit_gemma4_26b_full_smoke.json",
        "purpose": "Compare Gemma on the same full canonical-intertext context payload.",
        "run_profile": (
            "full prompt; chat API; JSON mode; think=false; candidate_count=1; max_tokens=1400"
        ),
    },
]

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "canonical_intertext_real_smoke_report.json"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "canonical_intertext_real_smoke_report.html"
DEFAULT_CSV_OUTPUT = REPORT_ROOT / "canonical_intertext_real_smoke_attempts.csv"


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


def task_lookup(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(task["task_id"]): task for task in suite.get("tasks", [])}


def raw_result_by_key(results: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = {}
    for row in results:
        task_id = str(row.get("task_id") or "")
        model = str(row.get("model_profile_id") or "")
        if task_id and model:
            rows[(task_id, model)] = row
    return rows


def first_candidate_text(result: dict[str, Any]) -> str:
    output = result.get("output")
    if not isinstance(output, dict):
        raw = str(result.get("raw_text") or "")
        return raw[:180] + ("..." if len(raw) > 180 else "")
    candidates = output.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return ""
    return str(candidate.get("text") or "")


def source_anchor_text(result: dict[str, Any]) -> str:
    output = result.get("output")
    if not isinstance(output, dict):
        return ""
    candidates = output.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return ""
    anchor = candidate.get("source_anchor")
    if not isinstance(anchor, dict):
        return ""
    return str(anchor.get("source_text") or "")


def summarize_model_rows(attempt_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    model_counts: Counter[str] = Counter()
    valid_counts: Counter[str] = Counter()
    anchor_issues: Counter[str] = Counter()
    elapsed: dict[str, list[float]] = defaultdict(list)
    alignment: dict[str, list[float]] = defaultdict(list)
    basis: dict[str, list[float]] = defaultdict(list)
    for row in attempt_rows:
        model = str(row["model_profile_id"])
        model_counts[model] += 1
        if row["schema_valid"]:
            valid_counts[model] += 1
        anchor_issues[model] += int(row["source_anchor_issue_count"])
        if row["elapsed_ms"]:
            elapsed[model].append(float(row["elapsed_ms"]))
        alignment[model].append(float(row["mean_alignment_score_0_5"]))
        basis[model].append(float(row["mean_translation_basis_score_0_5"]))
    rows = []
    for model, count in model_counts.most_common():
        rows.append(
            {
                "model_profile_id": model,
                "attempt_count": count,
                "schema_valid_attempt_count": valid_counts[model],
                "schema_valid_pct": pct(valid_counts[model], count),
                "source_anchor_issue_count": anchor_issues[model],
                "mean_elapsed_ms": round(sum(elapsed[model]) / len(elapsed[model]), 2)
                if elapsed[model]
                else 0.0,
                "mean_alignment_score_0_5": round(sum(alignment[model]) / len(alignment[model]), 2),
                "mean_translation_basis_score_0_5": round(sum(basis[model]) / len(basis[model]), 2),
            }
        )
    return rows


def build_attempt_rows(suite: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = task_lookup(suite)
    rows = []
    for attempt in ATTEMPTS:
        audit = load_json(attempt["audit_path"])
        results = raw_result_by_key(load_jsonl(attempt["result_path"]))
        for scored in audit.get("scored_results", []):
            task_id = str(scored["task_id"])
            model = str(scored["model_profile_id"])
            result = results.get((task_id, model), {})
            runtime = result.get("runtime") if isinstance(result.get("runtime"), dict) else {}
            task = tasks.get(task_id, {})
            row = {
                "attempt_id": attempt["attempt_id"],
                "label": attempt["label"],
                "purpose": attempt["purpose"],
                "run_profile": attempt["run_profile"],
                "task_id": task_id,
                "unit_id": task.get("unit_id", ""),
                "ref": task.get("ref", ""),
                "layer": task.get("layer", ""),
                "token_count": task.get("token_count", ""),
                "canonical_intertext_priority_score": task.get(
                    "canonical_intertext_priority_score", ""
                ),
                "model_profile_id": model,
                "model_family": attempt["model_family"],
                "schema_valid": bool(scored.get("schema_valid")),
                "candidate_count": int(scored.get("candidate_count") or 0),
                "error_count": int(scored.get("error_count") or 0),
                "errors": scored.get("errors", []),
                "mean_alignment_score_0_5": float(scored.get("mean_alignment_score_0_5") or 0.0),
                "mean_translation_basis_score_0_5": float(
                    scored.get("mean_translation_basis_score_0_5") or 0.0
                ),
                "invalid_token_ref_count": int(scored.get("invalid_token_ref_count") or 0),
                "source_anchor_issue_count": int(scored.get("source_anchor_issue_count") or 0),
                "reception_leak_term_count": int(scored.get("reception_leak_term_count") or 0),
                "elapsed_ms": runtime.get("elapsed_ms", 0),
                "eval_count": runtime.get("eval_count", 0),
                "prompt_eval_count": runtime.get("prompt_eval_count", 0),
                "prompt_mode": runtime.get("prompt_mode", ""),
                "format_mode": runtime.get("format_mode", ""),
                "api_mode": runtime.get("api_mode", ""),
                "disable_thinking": runtime.get("disable_thinking", False),
                "candidate_text": first_candidate_text(result),
                "source_anchor_text": source_anchor_text(result),
                "result_path": str(attempt["result_path"].relative_to(ROOT)),
                "audit_path": str(attempt["audit_path"].relative_to(ROOT)),
            }
            rows.append(row)
    return rows


def build_report() -> dict[str, Any]:
    suite = load_json(SUITE_PATH)
    attempt_rows = build_attempt_rows(suite)
    model_rows = summarize_model_rows(attempt_rows)
    valid_rows = [row for row in attempt_rows if row["schema_valid"]]
    clean_valid_rows = [row for row in valid_rows if int(row["source_anchor_issue_count"]) == 0]
    unique_valid_model_tasks = {(row["task_id"], row["model_profile_id"]) for row in valid_rows}
    unique_real_tasks = {row["task_id"] for row in attempt_rows}
    fastest_valid = min(
        valid_rows,
        key=lambda row: float(row.get("elapsed_ms") or 999_999_999),
        default={},
    )
    clean_best = min(
        clean_valid_rows,
        key=lambda row: float(row.get("elapsed_ms") or 999_999_999),
        default={},
    )
    source_anchor_issue_models = sorted(
        {
            str(row["model_profile_id"])
            for row in attempt_rows
            if int(row["source_anchor_issue_count"]) > 0
        }
    )
    suite_summary = suite["summary"]
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "real canonical-intertext smoke evidence generated; not signoff",
        "source_paths": {
            "suite": str(SUITE_PATH.relative_to(ROOT)),
            **{
                f"{attempt['attempt_id']}_results": str(attempt["result_path"].relative_to(ROOT))
                for attempt in ATTEMPTS
            },
            **{
                f"{attempt['attempt_id']}_audit": str(attempt["audit_path"].relative_to(ROOT))
                for attempt in ATTEMPTS
            },
        },
        "authority_boundary": {
            "current_state": "smoke_evidence_only",
            "rule": (
                "These rows are real local model outputs, but they cover one task and "
                "do not replace reviewer signoff, source approval, or full benchmark runs."
            ),
        },
        "summary": {
            "suite_task_count": suite_summary["task_count"],
            "suite_unit_count": suite_summary["selected_intertext_unit_count"],
            "suite_planned_model_runs": suite_summary["planned_model_runs"],
            "attempt_count": len(attempt_rows),
            "model_count": len({row["model_profile_id"] for row in attempt_rows}),
            "unique_task_real_evidence_count": len(unique_real_tasks),
            "unique_task_real_evidence_pct": pct(
                len(unique_real_tasks), suite_summary["task_count"]
            ),
            "schema_valid_attempt_count": len(valid_rows),
            "schema_valid_attempt_pct": pct(len(valid_rows), len(attempt_rows)),
            "clean_schema_valid_attempt_count": len(clean_valid_rows),
            "clean_schema_valid_attempt_pct": pct(len(clean_valid_rows), len(attempt_rows)),
            "valid_model_task_count": len(unique_valid_model_tasks),
            "valid_model_task_coverage_pct": pct(
                len(unique_valid_model_tasks), suite_summary["planned_model_runs"]
            ),
            "missing_model_task_count_after_smoke": (
                suite_summary["planned_model_runs"] - len(unique_valid_model_tasks)
            ),
            "source_anchor_issue_count": sum(
                int(row["source_anchor_issue_count"]) for row in attempt_rows
            ),
            "source_anchor_issue_model_count": len(source_anchor_issue_models),
            "source_anchor_issue_models": source_anchor_issue_models,
            "invalid_token_ref_count": sum(
                int(row["invalid_token_ref_count"]) for row in attempt_rows
            ),
            "truncated_or_invalid_attempt_count": sum(
                1 for row in attempt_rows if not row["schema_valid"]
            ),
            "fastest_valid_model_profile": fastest_valid.get("model_profile_id", ""),
            "fastest_valid_elapsed_ms": fastest_valid.get("elapsed_ms", 0),
            "clean_best_model_profile": clean_best.get("model_profile_id", ""),
            "clean_best_elapsed_ms": clean_best.get("elapsed_ms", 0),
            "shared_smoke_task_id": next(iter(unique_real_tasks), ""),
            "shared_smoke_ref": attempt_rows[0]["ref"] if attempt_rows else "",
            "shared_smoke_layer": attempt_rows[0]["layer"] if attempt_rows else "",
            "boundary_verdict": (
                "The patched full-context prompt produced schema-valid canonical-intertext "
                "rows from both local models. Mistral remains the clean current row across "
                "compact and full prompts because its Hebrew source anchor exactly matched "
                "the task; Gemma was faster on the full prompt but retained byte-escape "
                "artifacts in the Hebrew anchor and was flagged."
            ),
        },
        "model_rows": model_rows,
        "attempt_rows": attempt_rows,
    }


def metric_cards(cards: list[tuple[str, Any, str]]) -> str:
    return (
        '<div class="metric-grid">'
        + "".join(
            '<article class="metric-card">'
            f"<h3>{esc(label)}</h3>"
            f'<p class="metric-value">{esc(value)}</p>'
            f"<p>{esc(note)}</p>"
            "</article>"
            for label, value, note in cards
        )
        + "</div>"
    )


def table(headers: list[str], rows: list[list[Any]]) -> str:
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
        )
        + "</tbody></table>"
    )


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str,
    width: int = 980,
) -> str:
    row_h = 32
    left = 360
    right = 72
    top = 26
    height = top * 2 + row_h * max(1, len(rows))
    max_value = max((float(row.get(value_key) or 0) for row in rows), default=1.0)
    if not max_value:
        max_value = 1.0
    chart_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, row in enumerate(rows):
        value = float(row.get(value_key) or 0)
        y = top + index * row_h
        bar_w = chart_w * value / max_value
        parts.append(
            f'<text x="{left - 12}" y="{y + 20}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row.get(label_key, ""))}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 5}" width="{bar_w:.1f}" height="20" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 20}" font-size="12" '
            f'font-weight="700" fill="#24313a">{value:g}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    attempt_rows = report["attempt_rows"]
    model_rows = report["model_rows"]
    elapsed_rows = [
        {
            "label": row["label"],
            "elapsed_seconds": round(float(row.get("elapsed_ms") or 0) / 1000, 2),
        }
        for row in attempt_rows
    ]
    issue_rows = [
        {
            "label": row["model_profile_id"],
            "source_anchor_issue_count": row["source_anchor_issue_count"],
        }
        for row in model_rows
    ]
    attempt_table = [
        [
            row["label"],
            row["model_profile_id"],
            row["task_id"],
            row["schema_valid"],
            row["candidate_count"],
            row["error_count"],
            "; ".join(row["errors"]),
            row["source_anchor_issue_count"],
            f"{float(row.get('elapsed_ms') or 0) / 1000:.2f}s",
            row["candidate_text"],
        ]
        for row in attempt_rows
    ]
    model_table = [
        [
            row["model_profile_id"],
            row["attempt_count"],
            row["schema_valid_attempt_count"],
            f"{row['schema_valid_pct']:.2f}%",
            row["source_anchor_issue_count"],
            f"{row['mean_elapsed_ms'] / 1000:.2f}s",
            f"{row['mean_alignment_score_0_5']:.2f}",
            f"{row['mean_translation_basis_score_0_5']:.2f}",
        ]
        for row in model_rows
    ]
    headline_cards = metric_cards(
        [
            (
                "Attempts",
                fmt_int(summary["attempt_count"]),
                f"{fmt_int(summary['model_count'])} local models measured.",
            ),
            (
                "Schema Valid",
                f"{summary['schema_valid_attempt_pct']:.2f}%",
                f"{fmt_int(summary['schema_valid_attempt_count'])} attempts valid.",
            ),
            (
                "Clean Valid",
                f"{summary['clean_schema_valid_attempt_pct']:.2f}%",
                "Schema-valid attempts with no source-anchor issue.",
            ),
            (
                "Task Coverage",
                f"{summary['unique_task_real_evidence_pct']:.2f}%",
                (
                    f"{fmt_int(summary['unique_task_real_evidence_count'])} of "
                    f"{fmt_int(summary['suite_task_count'])} tasks touched."
                ),
            ),
            (
                "Model-Task Coverage",
                f"{summary['valid_model_task_coverage_pct']:.2f}%",
                (
                    f"{fmt_int(summary['missing_model_task_count_after_smoke'])} "
                    "planned rows still missing."
                ),
            ),
            (
                "Best Clean Model",
                summary["clean_best_model_profile"],
                f"{float(summary['clean_best_elapsed_ms'] or 0) / 1000:.2f}s elapsed.",
            ),
        ]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Canonical Intertext Real Smoke Report</title>
  <style>
    :root {{
      --ink: #1f2a33;
      --muted: #61717c;
      --line: #d8dee3;
      --panel: #f7f9fa;
      --accent: #2f6f73;
      --warn: #9b3d3d;
      --gold: #7c5b2f;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.48;
      background: #fff;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 34px 28px 56px; }}
    h1 {{ margin: 0 0 10px; font-size: 31px; letter-spacing: 0; }}
    h2 {{ margin: 34px 0 12px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }}
    h3 {{ margin: 0; color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    p {{ color: var(--muted); margin: 8px 0 0; }}
    .lede {{ max-width: 980px; color: #33414c; font-size: 16px; }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 20px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 15px;
      background: var(--panel);
    }}
    .metric-value {{ margin-top: 7px; color: var(--ink); font-size: 27px; font-weight: 700; }}
    .warning {{
      margin: 20px 0;
      padding: 13px 16px;
      border-left: 4px solid var(--warn);
      background: #fff4f2;
    }}
    .chart {{
      border: 1px solid var(--line);
      border-radius: 7px;
      margin: 16px 0;
      padding: 12px;
      overflow-x: auto;
    }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0 24px; font-size: 13px; }}
    th, td {{ border: 1px solid var(--line); padding: 8px 9px; vertical-align: top; }}
    th {{ background: var(--panel); text-align: left; color: var(--muted); }}
  </style>
</head>
<body>
<main>
  <h1>Canonical Intertext Real Smoke Report</h1>
  <p class="lede">
    Real local-model smoke evidence for the canonical-intertext benchmark supplement.
    This report compares compact and full-context Mistral and Gemma runs on the same
    Psalm 96:7 gloss task, preserving the distinction between schema-valid model
    output and authority signoff.
  </p>
  <div class="warning">
    Authority boundary: {esc(report["authority_boundary"]["rule"])}
  </div>
  {headline_cards}
  <section>
    <h2>Measured Attempt Runtime</h2>
    <div class="chart">{
        svg_horizontal_bars(
            elapsed_rows,
            label_key="label",
            value_key="elapsed_seconds",
            aria_label="Canonical intertext real smoke elapsed seconds",
            color="#2f6f73",
        )
    }</div>
    <div class="chart">{
        svg_horizontal_bars(
            issue_rows,
            label_key="label",
            value_key="source_anchor_issue_count",
            aria_label="Canonical intertext source-anchor issues by model",
            color="#9b3d3d",
        )
    }</div>
  </section>
  <section>
    <h2>Model Summary</h2>
    {
        table(
            [
                "Model",
                "Attempts",
                "Schema Valid",
                "Schema %",
                "Anchor Issues",
                "Mean Elapsed",
                "Mean Alignment",
                "Mean Basis",
            ],
            model_table,
        )
    }
  </section>
  <section>
    <h2>Attempt Rows</h2>
    {
        table(
            [
                "Attempt",
                "Model",
                "Task",
                "Schema Valid",
                "Candidates",
                "Errors",
                "Error Detail",
                "Anchor Issues",
                "Elapsed",
                "Candidate Text",
            ],
            attempt_table,
        )
    }
  </section>
  <section>
    <h2>Verdict</h2>
    <p>{esc(summary["boundary_verdict"])}</p>
  </section>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate canonical-intertext real model smoke comparison report."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.csv_output, report["attempt_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
