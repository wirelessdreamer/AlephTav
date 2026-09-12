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

SUITE_PATH = REPORT_ROOT / "doctoral_collision_benchmark_supplement_suite.json"
ATTEMPTS = [
    {
        "attempt_id": "mistral_small_3_2_collision_smoke",
        "label": "Mistral Small 3.2 collision smoke",
        "model_profile_id": "mistralai/Mistral-Small-3.2-24B-Instruct-2506",
        "model_family": "Mistral Small",
        "result_path": REPORT_ROOT
        / "doctoral_collision_benchmark_supplement_results_mistral_smoke.jsonl",
        "audit_path": REPORT_ROOT
        / "doctoral_collision_benchmark_supplement_result_audit_mistral_smoke.json",
        "purpose": "Measure top collision gloss/literal schema and Hebrew source anchoring.",
        "run_profile": "compact prompt; chat API; JSON mode; candidate_count=1; max_tokens=1200",
    },
    {
        "attempt_id": "gemma4_26b_collision_smoke",
        "label": "Gemma 4 26B collision smoke",
        "model_profile_id": "google/gemma-4-26B-A4B-it",
        "model_family": "Gemma 4",
        "result_path": REPORT_ROOT
        / "doctoral_collision_benchmark_supplement_results_gemma4_26b_smoke.jsonl",
        "audit_path": REPORT_ROOT
        / "doctoral_collision_benchmark_supplement_result_audit_gemma4_26b_smoke.json",
        "purpose": "Compare Gemma on the same collision prompt with thinking disabled.",
        "run_profile": (
            "compact prompt; chat API; JSON mode; think=false; candidate_count=1; max_tokens=1200"
        ),
    },
]

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "doctoral_collision_real_smoke_report.json"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "doctoral_collision_real_smoke_report.html"
DEFAULT_CSV_OUTPUT = REPORT_ROOT / "doctoral_collision_real_smoke_attempts.csv"


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


def first_candidate(result: dict[str, Any]) -> dict[str, Any]:
    output = result.get("output")
    if not isinstance(output, dict):
        return {}
    candidates = output.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return {}
    candidate = candidates[0]
    return candidate if isinstance(candidate, dict) else {}


def first_candidate_text(result: dict[str, Any]) -> str:
    candidate = first_candidate(result)
    if candidate:
        return str(candidate.get("text") or "")
    raw = str(result.get("raw_text") or "")
    return raw[:220] + ("..." if len(raw) > 220 else "")


def source_anchor_text(result: dict[str, Any]) -> str:
    candidate = first_candidate(result)
    anchor = candidate.get("source_anchor") if candidate else {}
    if not isinstance(anchor, dict):
        return ""
    return str(anchor.get("source_text") or "")


def summarize_model_rows(attempt_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    model_counts: Counter[str] = Counter()
    valid_counts: Counter[str] = Counter()
    clean_counts: Counter[str] = Counter()
    anchor_issues: Counter[str] = Counter()
    reception_leaks: Counter[str] = Counter()
    elapsed: dict[str, list[float]] = defaultdict(list)
    alignment: dict[str, list[float]] = defaultdict(list)
    basis: dict[str, list[float]] = defaultdict(list)
    model_family_by_profile: dict[str, str] = {}
    for row in attempt_rows:
        model = str(row["model_profile_id"])
        model_family_by_profile[model] = str(row["model_family"])
        model_counts[model] += 1
        if row["schema_valid"]:
            valid_counts[model] += 1
        if row["schema_valid"] and int(row["source_anchor_issue_count"]) == 0:
            clean_counts[model] += 1
        anchor_issues[model] += int(row["source_anchor_issue_count"])
        reception_leaks[model] += int(row["reception_leak_term_count"])
        if row["elapsed_ms"]:
            elapsed[model].append(float(row["elapsed_ms"]))
        alignment[model].append(float(row["mean_alignment_score_0_5"]))
        basis[model].append(float(row["mean_translation_basis_score_0_5"]))
    rows = []
    for model, count in model_counts.most_common():
        rows.append(
            {
                "model_profile_id": model,
                "model_family": model_family_by_profile.get(model, model),
                "attempt_count": count,
                "schema_valid_attempt_count": valid_counts[model],
                "schema_valid_pct": pct(valid_counts[model], count),
                "clean_schema_valid_attempt_count": clean_counts[model],
                "source_anchor_issue_count": anchor_issues[model],
                "reception_leak_term_count": reception_leaks[model],
                "mean_elapsed_ms": round(sum(elapsed[model]) / len(elapsed[model]), 2)
                if elapsed[model]
                else 0.0,
                "mean_alignment_score_0_5": round(
                    sum(alignment[model]) / len(alignment[model]),
                    2,
                ),
                "mean_translation_basis_score_0_5": round(
                    sum(basis[model]) / len(basis[model]),
                    2,
                ),
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
                "model_profile_id": model,
                "model_family": attempt["model_family"],
                "task_id": task_id,
                "unit_id": task.get("unit_id", ""),
                "ref": task.get("ref", ""),
                "layer": task.get("layer", ""),
                "integration_pressure_score": task.get("integration_pressure_score", ""),
                "integration_pressure_band": task.get("integration_pressure_band", ""),
                "required_decision_lanes": task.get("required_decision_lanes", []),
                "required_review_roles": task.get("required_review_roles", []),
                "reception_required_frames": task.get("reception_required_frames", []),
                "witness_divergence_pct": task.get("witness_divergence_pct", ""),
                "schema_valid": bool(scored.get("schema_valid")),
                "error_count": int(scored.get("error_count") or 0),
                "errors": scored.get("errors", []),
                "candidate_count": int(scored.get("candidate_count") or 0),
                "mean_alignment_score_0_5": float(scored.get("mean_alignment_score_0_5") or 0),
                "mean_translation_basis_score_0_5": float(
                    scored.get("mean_translation_basis_score_0_5") or 0
                ),
                "invalid_token_ref_count": int(scored.get("invalid_token_ref_count") or 0),
                "reception_leak_term_count": int(scored.get("reception_leak_term_count") or 0),
                "source_anchor_issue_count": int(scored.get("source_anchor_issue_count") or 0),
                "elapsed_ms": runtime.get("elapsed_ms", 0),
                "prompt_mode": runtime.get("prompt_mode", ""),
                "api_mode": runtime.get("api_mode", ""),
                "format_mode": runtime.get("format_mode", ""),
                "disable_thinking": runtime.get("disable_thinking", False),
                "candidate_text": first_candidate_text(result),
                "source_anchor_text": source_anchor_text(result),
                "source_anchor_matches": int(scored.get("source_anchor_issue_count") or 0) == 0,
            }
            rows.append(row)
    return rows


def build_report() -> dict[str, Any]:
    suite = load_json(SUITE_PATH)
    attempt_rows = build_attempt_rows(suite)
    model_rows = summarize_model_rows(attempt_rows)
    expected_model_task_count = int(suite["summary"]["planned_model_runs"])
    valid_attempts = sum(1 for row in attempt_rows if row["schema_valid"])
    clean_attempts = sum(
        1 for row in attempt_rows if row["schema_valid"] and row["source_anchor_issue_count"] == 0
    )
    source_anchor_issues = sum(int(row["source_anchor_issue_count"]) for row in attempt_rows)
    reception_leaks = sum(int(row["reception_leak_term_count"]) for row in attempt_rows)
    covered_tasks = {str(row["task_id"]) for row in attempt_rows if row["schema_valid"]}
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated doctoral collision real smoke report; not authority evidence",
        "source_paths": {
            "suite": str(SUITE_PATH.relative_to(ROOT)),
            "attempts": [
                {
                    "attempt_id": attempt["attempt_id"],
                    "result_path": str(attempt["result_path"].relative_to(ROOT)),
                    "audit_path": str(attempt["audit_path"].relative_to(ROOT)),
                }
                for attempt in ATTEMPTS
            ],
        },
        "authority_policy": {
            "model_outputs_are_authoritative": False,
            "required_use": (
                "Use this smoke report for runtime/schema/source-anchor triage only. "
                "Collision interpretation and translation authority still require signed "
                "Hebrew, reception, academic, and release review."
            ),
        },
        "summary": {
            "attempt_count": len(attempt_rows),
            "model_count": len({row["model_profile_id"] for row in attempt_rows}),
            "task_count": len(covered_tasks),
            "expected_model_task_count": expected_model_task_count,
            "missing_model_task_count_after_smoke": max(
                0,
                expected_model_task_count - len(attempt_rows),
            ),
            "schema_valid_attempt_count": valid_attempts,
            "schema_valid_attempt_pct": pct(valid_attempts, len(attempt_rows)),
            "clean_schema_valid_attempt_count": clean_attempts,
            "clean_schema_valid_attempt_pct": pct(clean_attempts, len(attempt_rows)),
            "source_anchor_issue_count": source_anchor_issues,
            "reception_leak_term_count": reception_leaks,
            "top_ref": attempt_rows[0]["ref"] if attempt_rows else "",
            "top_task_id": attempt_rows[0]["task_id"] if attempt_rows else "",
            "top_integration_pressure_score": attempt_rows[0]["integration_pressure_score"]
            if attempt_rows
            else 0,
            "clean_best_model_profile": next(
                (
                    row["model_profile_id"]
                    for row in sorted(
                        model_rows,
                        key=lambda item: (
                            item["source_anchor_issue_count"],
                            -item["schema_valid_pct"],
                            item["mean_elapsed_ms"],
                        ),
                    )
                    if row["clean_schema_valid_attempt_count"]
                ),
                "",
            ),
            "fastest_valid_model_profile": next(
                (
                    row["model_profile_id"]
                    for row in sorted(model_rows, key=lambda item: item["mean_elapsed_ms"])
                    if row["schema_valid_attempt_count"]
                ),
                "",
            ),
        },
        "attempts": [
            {
                **{
                    key: value
                    for key, value in attempt.items()
                    if key not in {"result_path", "audit_path"}
                },
                "result_path": str(attempt["result_path"].relative_to(ROOT)),
                "audit_path": str(attempt["audit_path"].relative_to(ROOT)),
            }
            for attempt in ATTEMPTS
        ],
        "attempt_rows": attempt_rows,
        "model_rows": model_rows,
        "visual_data": {
            "model_elapsed_rows": [
                {
                    "label": row["model_family"],
                    "value": round(float(row["mean_elapsed_ms"]) / 1000, 2),
                }
                for row in model_rows
            ],
            "model_anchor_issue_rows": [
                {
                    "label": row["model_family"],
                    "value": row["source_anchor_issue_count"],
                }
                for row in model_rows
            ],
            "attempt_alignment_rows": [
                {
                    "label": f"{row['model_family']} {row['layer']}",
                    "value": row["mean_alignment_score_0_5"],
                }
                for row in attempt_rows
            ],
        },
    }


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def bars(rows: list[dict[str, Any]], *, label_key: str, value_key: str) -> str:
    if not rows:
        return ""
    max_value = max(float(row[value_key] or 0) for row in rows) or 1.0
    parts = []
    for row in rows:
        width = max(2.0, float(row[value_key] or 0) / max_value * 100.0)
        parts.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{esc(row[label_key])}</div>
              <div class="bar-track"><div class="bar" style="width:{width:.2f}%"></div></div>
              <div class="bar-value">{esc(row[value_key])}</div>
            </div>"""
        )
    return "\n".join(parts)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    model_rows = [
        [
            row["model_profile_id"],
            row["attempt_count"],
            row["schema_valid_attempt_count"],
            row["clean_schema_valid_attempt_count"],
            f"{row['schema_valid_pct']:.2f}%",
            row["source_anchor_issue_count"],
            row["reception_leak_term_count"],
            f"{float(row['mean_elapsed_ms']) / 1000:.2f}s",
            f"{row['mean_alignment_score_0_5']:.2f}",
            f"{row['mean_translation_basis_score_0_5']:.2f}",
        ]
        for row in report["model_rows"]
    ]
    attempt_rows = [
        [
            row["label"],
            row["task_id"],
            row["layer"],
            "yes" if row["schema_valid"] else "no",
            row["source_anchor_issue_count"],
            row["reception_leak_term_count"],
            "; ".join(row["errors"]),
            f"{float(row['elapsed_ms']) / 1000:.2f}s",
            row["candidate_text"],
        ]
        for row in report["attempt_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Doctoral Collision Real Smoke</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      margin: 32px;
      color: #17201b;
    }}
    h1, h2 {{ color: #173d3f; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px;
    }}
    .card {{
      border: 1px solid #ccd7d2;
      border-radius: 8px;
      padding: 14px;
      background: #f8fbfa;
    }}
    .metric {{ font-size: 1.8rem; font-weight: 700; }}
    .warning {{
      border-left: 5px solid #9b3d3d;
      padding: 12px 14px;
      background: #fff5f4;
      margin: 18px 0;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(180px, 1fr) 3fr 80px;
      gap: 10px;
      align-items: center;
      margin: 8px 0;
    }}
    .bar-track {{
      height: 18px;
      background: #e7ece9;
      border-radius: 4px;
      overflow: hidden;
    }}
    .bar {{ height: 100%; background: #2f6f73; }}
    table {{ border-collapse: collapse; width: 100%; margin: 18px 0 30px; font-size: 0.9rem; }}
    th, td {{ border: 1px solid #d7dfdc; padding: 7px 8px; vertical-align: top; }}
    th {{ background: #edf4f2; text-align: left; }}
    td {{ max-width: 520px; }}
  </style>
</head>
<body>
  <h1>Doctoral Collision Real Smoke</h1>
  <p>
    Real local-model smoke outputs for the top doctoral collision benchmark
    unit, Psalm 22:28, across gloss and literal layers. This report measures
    schema validity, source anchoring, reception leakage, and runtime only.
  </p>
  <div class="warning">{esc(report["authority_policy"]["required_use"])}</div>
  <section class="grid">
    <div class="card">
      <div class="metric">{fmt_int(summary["attempt_count"])}</div>
      <p>real attempts</p>
    </div>
    <div class="card">
      <div class="metric">{fmt_int(summary["schema_valid_attempt_count"])}</div>
      <p>schema-valid attempts</p>
    </div>
    <div class="card">
      <div class="metric">{fmt_int(summary["clean_schema_valid_attempt_count"])}</div>
      <p>schema-valid attempts with clean source anchors</p>
    </div>
    <div class="card">
      <div class="metric">{fmt_int(summary["source_anchor_issue_count"])}</div>
      <p>source-anchor issues</p>
    </div>
    <div class="card">
      <div class="metric">{fmt_int(summary["missing_model_task_count_after_smoke"])}</div>
      <p>planned model-task rows still missing</p>
    </div>
  </section>

  <h2>Runtime by Model</h2>
  {bars(report["visual_data"]["model_elapsed_rows"], label_key="label", value_key="value")}

  <h2>Source-Anchor Issues by Model</h2>
  {bars(report["visual_data"]["model_anchor_issue_rows"], label_key="label", value_key="value")}

  <h2>Model Summary</h2>
  {
        table(
            [
                "Model",
                "Attempts",
                "Schema Valid",
                "Clean Valid",
                "Schema %",
                "Anchor Issues",
                "Reception Leaks",
                "Mean Elapsed",
                "Mean Alignment",
                "Mean Basis",
            ],
            model_rows,
        )
    }

  <h2>Attempt Rows</h2>
  {
        table(
            [
                "Attempt",
                "Task",
                "Layer",
                "Schema Valid",
                "Anchor Issues",
                "Reception Leaks",
                "Errors",
                "Elapsed",
                "Candidate Text",
            ],
            attempt_rows,
        )
    }
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate doctoral collision real smoke report.")
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
