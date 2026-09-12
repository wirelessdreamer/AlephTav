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

LAYER_CONSISTENCY_PATH = REPORT_ROOT / "layer_consistency_report.json"
QUALITY_TRIAGE_PATH = REPORT_ROOT / "model_output_quality_triage.json"
STRUCTURED_TUNING_PATH = REPORT_ROOT / "structured_output_tuning_report.json"
MODEL_EVIDENCE_GAP_PATH = REPORT_ROOT / "model_evidence_gap_report.json"
WINDOWS_RUNNER_PATH = ROOT / "scripts" / "run_windows_ollama_benchmark_suite.py"
LOCAL_RUNNER_PATH = ROOT / "scripts" / "run_local_model_benchmark_suite.py"
GLOSS_PROMPT_PATH = ROOT / "app" / "llm" / "prompts" / "pass_01_gloss.md"
LITERAL_PROMPT_PATH = ROOT / "app" / "llm" / "prompts" / "pass_02_literal.md"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "layer_remediation_plan.json"
DEFAULT_ACTION_CSV_OUTPUT = REPORT_ROOT / "layer_remediation_actions.csv"
DEFAULT_RETRY_CSV_OUTPUT = REPORT_ROOT / "layer_remediation_retry_tasks.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "layer_remediation_plan.html"

LAYER_FAILURE_FLAGS = {
    "exact_gloss_literal_duplicate",
    "near_gloss_literal_duplicate",
    "weak_layer_differentiation",
    "gloss_longer_than_literal",
    "divine_name_missing_in_one_layer",
    "divine_name_rendering_differs_by_layer",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


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


def prompt_stats(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = [line for line in text.splitlines() if line.strip()]
    words = [word for word in text.replace("`", " ").split() if word.strip()]
    return {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
        "char_count": len(text),
        "nonempty_line_count": len(lines),
        "word_count": len(words),
    }


def runner_contract_stats(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
        "has_layer_contracts": "LAYER_CONTRACTS" in text,
        "has_gloss_differentiator": "source-order lexical gloss" in text,
        "has_literal_differentiator": (
            "grammatical literal translation" in text
            or "readable grammatical literal sentence" in text
        ),
        "has_layer_contract_payload": "layer_contract" in text,
    }


def model_row_by_id(tuning: dict[str, Any], model_id: str) -> dict[str, Any]:
    for row in tuning.get("summary", {}).get("model_rows", []):
        if row.get("model_profile_id") == model_id:
            return row
    return {}


def retry_task_rows(layer_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    seen: set[tuple[str, str, str]] = set()
    for pair in layer_report.get("pair_rows", []):
        flags = set(str(flag) for flag in pair.get("flags", []))
        is_high_priority = pair.get("layer_status") == "high_priority_layer_review"
        if not flags & LAYER_FAILURE_FLAGS and not is_high_priority:
            continue
        for layer, task_key in (("gloss", "gloss_task_id"), ("literal", "literal_task_id")):
            key = (str(pair["unit_id"]), str(pair["model_profile_id"]), layer)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "task_id": pair.get(task_key),
                    "unit_id": pair["unit_id"],
                    "ref": pair["ref"],
                    "layer": layer,
                    "model_profile_id": pair["model_profile_id"],
                    "pair_layer_status": pair["layer_status"],
                    "pair_risk_score": pair["layer_risk_score"],
                    "word_jaccard_pct": pair["word_jaccard_pct"],
                    "literal_minus_gloss_words": pair["literal_minus_gloss_words"],
                    "retry_reason_flags": sorted(flags & LAYER_FAILURE_FLAGS),
                    "recommended_prompt_mode": "compact",
                    "recommended_format_mode": "schema",
                    "success_gate": (
                        "Schema-valid output with non-identical paired text, "
                        "visible layer-specific differentiator, and no source-anchor issue."
                    ),
                }
            )
    rows.sort(key=lambda row: (-float(row["pair_risk_score"]), row["task_id"]))
    return rows


def action_rows(
    *,
    layer_report: dict[str, Any],
    quality_triage: dict[str, Any],
    structured_tuning: dict[str, Any],
    model_gap: dict[str, Any],
    source_control: dict[str, Any],
) -> list[dict[str, Any]]:
    layer = layer_report["summary"]
    quality = quality_triage["summary"]
    tuning = structured_tuning["summary"]
    gap = model_gap["summary"]
    gemma_row = model_row_by_id(structured_tuning, "google/gemma-4-26B-A4B-it")
    pair_count = max(1, int(layer["paired_unit_model_count"]))
    weak_pct = pct(layer["weak_layer_differentiation_pair_count"], pair_count)
    exact_pct = pct(layer["exact_duplicate_pair_count"], pair_count)
    divine_pairs = max(1, int(layer["divine_name_pair_count"]))
    divine_inconsistent_pct = pct(layer["divine_name_inconsistent_pair_count"], divine_pairs)
    runner_ready = all(
        row["has_layer_contracts"]
        and row["has_gloss_differentiator"]
        and row["has_literal_differentiator"]
        for row in source_control["runner_rows"]
    )
    rows = [
        {
            "priority": 1,
            "category": "layer_contract_prompting",
            "severity": "critical",
            "evidence": (
                f"{layer['weak_layer_differentiation_pair_count']} of "
                f"{layer['paired_unit_model_count']} pairs weakly differentiated "
                f"({weak_pct:.2f}%); {layer['exact_duplicate_pair_count']} exact "
                f"duplicates ({exact_pct:.2f}%); mean overlap "
                f"{layer['mean_word_jaccard_pct']:.2f}%."
            ),
            "intervention": (
                "Use explicit layer contracts in compact and full benchmark prompts; "
                "gloss must be lexical/source-order and literal must be grammatical."
            ),
            "current_control_state": (
                "runner layer contracts present" if runner_ready else "runner contracts incomplete"
            ),
            "success_gate": (
                "Retry flagged pairs with 0 exact duplicates, weak differentiation "
                "below 20%, and no drop in schema/source-anchor validity."
            ),
            "primary_artifacts": [
                "reports/research/layer_consistency_report.html",
                "scripts/run_windows_ollama_benchmark_suite.py",
                "scripts/run_local_model_benchmark_suite.py",
            ],
        },
        {
            "priority": 2,
            "category": "divine_name_policy",
            "severity": "high",
            "evidence": (
                f"{layer['divine_name_inconsistent_pair_count']} of "
                f"{layer['divine_name_pair_count']} divine-name pairs differ "
                f"across layers ({divine_inconsistent_pct:.2f}%)."
            ),
            "intervention": (
                "Predeclare the project divine-name policy in retry prompts and require "
                "candidate rationale to cite the source token behind each rendering."
            ),
            "current_control_state": "detected by layer audit; not yet proven fixed",
            "success_gate": "0 divine-name rendering differences across paired retry rows.",
            "primary_artifacts": [
                "reports/research/layer_consistency_pairs.csv",
                "reports/research/translation_claim_evidence_matrix.html",
            ],
        },
        {
            "priority": 3,
            "category": "gemma_structured_output",
            "severity": "high",
            "evidence": (
                f"Gemma 4 26B schema-valid attempts: "
                f"{gemma_row.get('schema_valid_count', 0)} of "
                f"{gemma_row.get('attempt_count', 0)}; quality triage has "
                f"{quality['structure_failure_count']} structure failures."
            ),
            "intervention": (
                "Run a Gemma-specific structured-output retry using compact prompt, "
                "schema format mode, lower max text length, and one candidate."
            ),
            "current_control_state": "schema failure remains unproven fixed",
            "success_gate": "Gemma retry reaches at least 90% schema-valid on 10 tasks.",
            "primary_artifacts": [
                "reports/research/structured_output_tuning_report.html",
                "reports/research/model_output_quality_triage.html",
            ],
        },
        {
            "priority": 4,
            "category": "expanded_grid_coverage",
            "severity": "high",
            "evidence": (
                f"{gap['schema_valid_result_count']} schema-valid expanded rows out of "
                f"{gap['expected_result_count']} expected; "
                f"{gap['high_risk_without_schema_valid_count']} high-risk units lack "
                "schema-valid real output."
            ),
            "intervention": (
                "After layer-contract retry passes, expand the real local bake-off over "
                "the remaining high-risk units before broad grid completion."
            ),
            "current_control_state": "evidence gap quantified; coverage still sparse",
            "success_gate": (
                "Every high-risk claim-control unit has at least one schema-valid "
                "real row before human signoff routing."
            ),
            "primary_artifacts": [
                "reports/research/model_evidence_gap_report.html",
                "reports/research/contextual_expanded_benchmark_suite.html",
            ],
        },
        {
            "priority": 5,
            "category": "human_review_routing",
            "severity": "high",
            "evidence": (
                f"{quality['contextual_review_required_count']} valid candidate rows "
                "carry contextual review flags; automated triage is not signoff."
            ),
            "intervention": (
                "Route layer-retry outputs through Hebrew, lexical, alignment, lyric, "
                "and theology review before any canonical promotion discussion."
            ),
            "current_control_state": "review workload planned; completed signoff absent",
            "success_gate": "Completed role-specific signoff rows exist for accepted alternates.",
            "primary_artifacts": [
                "reports/research/review_signoff_plan.html",
                "reports/research/scholarly_authority_readiness.html",
            ],
        },
        {
            "priority": 6,
            "category": "prompt_instruction_density",
            "severity": "medium",
            "evidence": (
                "Pass 01 prompt has "
                f"{source_control['prompt_rows'][0]['word_count']} words; Pass 02 has "
                f"{source_control['prompt_rows'][1]['word_count']} words. "
                f"Overall structured attempts are {tuning['schema_valid_pct']:.2f}% "
                "schema-valid, but layer behavior is weak."
            ),
            "intervention": (
                "Keep short production prompts, but make layer contracts explicit in "
                "generated benchmark prompts and future prompt files."
            ),
            "current_control_state": "runner contracts added; prompt files remain minimal",
            "success_gate": "Prompt changes improve layer audit without increasing schema errors.",
            "primary_artifacts": [
                "app/llm/prompts/pass_01_gloss.md",
                "app/llm/prompts/pass_02_literal.md",
            ],
        },
    ]
    return rows


def build_source_control() -> dict[str, Any]:
    return {
        "prompt_rows": [
            prompt_stats(GLOSS_PROMPT_PATH),
            prompt_stats(LITERAL_PROMPT_PATH),
        ],
        "runner_rows": [
            runner_contract_stats(WINDOWS_RUNNER_PATH),
            runner_contract_stats(LOCAL_RUNNER_PATH),
        ],
    }


def build_report(
    *,
    layer_consistency_path: Path,
    quality_triage_path: Path,
    structured_tuning_path: Path,
    model_evidence_gap_path: Path,
) -> dict[str, Any]:
    layer_report = load_json(layer_consistency_path)
    quality_triage = load_json(quality_triage_path)
    structured_tuning = load_json(structured_tuning_path)
    model_gap = load_json(model_evidence_gap_path)
    source_control = build_source_control()
    retries = retry_task_rows(layer_report)
    actions = action_rows(
        layer_report=layer_report,
        quality_triage=quality_triage,
        structured_tuning=structured_tuning,
        model_gap=model_gap,
        source_control=source_control,
    )
    layer_summary = layer_report["summary"]
    retry_pair_count = len({(row["unit_id"], row["model_profile_id"]) for row in retries})
    flag_counts: Counter[str] = Counter()
    for row in retries:
        flag_counts.update(str(flag) for flag in row.get("retry_reason_flags", []))
    summary = {
        "action_count": len(actions),
        "critical_action_count": sum(1 for row in actions if row["severity"] == "critical"),
        "high_action_count": sum(1 for row in actions if row["severity"] == "high"),
        "retry_task_count": len(retries),
        "retry_pair_count": retry_pair_count,
        "paired_unit_model_count": layer_summary["paired_unit_model_count"],
        "exact_duplicate_pair_count": layer_summary["exact_duplicate_pair_count"],
        "weak_layer_differentiation_pair_count": (
            layer_summary["weak_layer_differentiation_pair_count"]
        ),
        "divine_name_inconsistent_pair_count": (
            layer_summary["divine_name_inconsistent_pair_count"]
        ),
        "mean_word_jaccard_pct": layer_summary["mean_word_jaccard_pct"],
        "runner_contract_ready": all(
            row["has_layer_contracts"]
            and row["has_gloss_differentiator"]
            and row["has_literal_differentiator"]
            for row in source_control["runner_rows"]
        ),
        "top_retry_task": retries[0]["task_id"] if retries else None,
        "top_retry_ref": retries[0]["ref"] if retries else None,
        "retry_flag_counts": dict(flag_counts.most_common()),
    }
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "layer remediation plan; proposed gates require rerun evidence",
        "source_paths": {
            "layer_consistency": str(layer_consistency_path.relative_to(ROOT)),
            "quality_triage": str(quality_triage_path.relative_to(ROOT)),
            "structured_tuning": str(structured_tuning_path.relative_to(ROOT)),
            "model_evidence_gap": str(model_evidence_gap_path.relative_to(ROOT)),
        },
        "method_notes": [
            "The report turns measured layer failures into retry gates and action rows.",
            (
                "Applied prompt-control code is listed as current state, "
                "not proof of model improvement."
            ),
            "Success gates require regenerated real model rows and a fresh layer audit.",
        ],
        "summary": summary,
        "action_rows": actions,
        "retry_task_rows": retries,
        "source_control": source_control,
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
    limit: int = 18,
) -> str:
    rows = rows[:limit]
    row_h = 29
    left = 310
    right = 60
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
    action_table = [
        [
            row["priority"],
            row["severity"],
            row["category"],
            row["evidence"],
            row["intervention"],
            row["success_gate"],
        ]
        for row in report["action_rows"]
    ]
    retry_table = [
        [
            row["task_id"],
            row["ref"],
            row["layer"],
            f"{row['pair_risk_score']:.2f}",
            f"{row['word_jaccard_pct']:.2f}%",
            ", ".join(row["retry_reason_flags"]),
        ]
        for row in report["retry_task_rows"][:40]
    ]
    source_table = [
        [
            row["path"],
            row.get("word_count", ""),
            row.get("has_layer_contracts", ""),
            row.get("has_gloss_differentiator", ""),
            row.get("has_literal_differentiator", ""),
        ]
        for row in report["source_control"]["prompt_rows"] + report["source_control"]["runner_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Layer Remediation Plan</title>
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
    <h1>AlephTav Layer Remediation Plan</h1>
    <p class="lede">
      Action plan generated from real local model output failures. It converts
      measured gloss/literal collapse, divine-name inconsistencies, structure
      failures, and sparse evidence coverage into retry rows and success gates.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Remediation Summary</h2>
      {
        metric_cards(
            [
                (
                    "Actions",
                    fmt_int(summary["action_count"]),
                    f'''{fmt_int(summary["critical_action_count"])} critical; '''
                    f'''{fmt_int(summary["high_action_count"])} high severity.''',
                ),
                (
                    "Retry tasks",
                    fmt_int(summary["retry_task_count"]),
                    f'''{fmt_int(summary["retry_pair_count"])} paired unit/model rows.''',
                ),
                (
                    "Exact duplicates",
                    fmt_int(summary["exact_duplicate_pair_count"]),
                    "Measured gloss/literal duplicate pairs.",
                ),
                (
                    "Mean overlap",
                    f'''{summary["mean_word_jaccard_pct"]:.2f}%''',
                    "Word-set overlap across current paired rows.",
                ),
            ]
        )
    }
      <div class="warning">
        Runner prompt-control changes are current-state evidence only. They do
        not prove model improvement until flagged tasks are rerun and audited.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["retry_flag_counts"], "flag"),
            label_key="flag",
            value_key="count",
            aria_label="Retry task reason flags",
            color="#7c5b2f",
        )
    }</div>
    </section>
    <section>
      <h2>Action Matrix</h2>
      {
        table(
            [
                "Priority",
                "Severity",
                "Category",
                "Evidence",
                "Intervention",
                "Success Gate",
            ],
            action_table,
        )
    }
    </section>
    <section>
      <h2>Retry Queue</h2>
      {
        table(
            ["Task", "Ref", "Layer", "Risk", "Overlap", "Reason Flags"],
            retry_table,
        )
    }
    </section>
    <section>
      <h2>Prompt and Runner Controls</h2>
      {
        table(
            [
                "Path",
                "Prompt Words",
                "Layer Contracts",
                "Gloss Differentiator",
                "Literal Differentiator",
            ],
            source_table,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate layer remediation plan.")
    parser.add_argument(
        "--layer-consistency",
        type=Path,
        default=LAYER_CONSISTENCY_PATH,
    )
    parser.add_argument("--quality-triage", type=Path, default=QUALITY_TRIAGE_PATH)
    parser.add_argument("--structured-tuning", type=Path, default=STRUCTURED_TUNING_PATH)
    parser.add_argument("--model-evidence-gap", type=Path, default=MODEL_EVIDENCE_GAP_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--action-csv-output", type=Path, default=DEFAULT_ACTION_CSV_OUTPUT)
    parser.add_argument("--retry-csv-output", type=Path, default=DEFAULT_RETRY_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        layer_consistency_path=args.layer_consistency,
        quality_triage_path=args.quality_triage,
        structured_tuning_path=args.structured_tuning,
        model_evidence_gap_path=args.model_evidence_gap,
    )
    write_json(args.json_output, report)
    write_csv(args.action_csv_output, report["action_rows"])
    write_csv(args.retry_csv_output, report["retry_task_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.action_csv_output}")
    print(f"Wrote {args.retry_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
