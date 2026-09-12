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

SOURCE_PATHS = {
    "critical_unit_decision_dossier": REPORT_ROOT / "critical_unit_decision_dossier.json",
    "critical_unit_review_execution": REPORT_ROOT / "critical_unit_review_execution_plan.json",
    "contextual_expanded_benchmark_suite": (
        REPORT_ROOT / "contextual_expanded_benchmark_suite.json"
    ),
    "contextual_expanded_benchmark_cross_exam": (
        REPORT_ROOT / "contextual_expanded_benchmark_cross_exam_protocol.json"
    ),
    "contextual_expanded_benchmark_result_audit": (
        REPORT_ROOT / "contextual_expanded_benchmark_result_audit.json"
    ),
    "contextual_real_model_evidence": REPORT_ROOT / "contextual_real_model_evidence_matrix.json",
    "local_model_doctoral_bakeoff": REPORT_ROOT / "local_model_doctoral_bakeoff_matrix.json",
    "model_training_certification": REPORT_ROOT / "model_training_certification_roadmap.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "critical_unit_model_cross_exam_plan.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "critical_unit_model_cross_exam_plan_units.csv"
DEFAULT_MODEL_CSV_OUTPUT = REPORT_ROOT / "critical_unit_model_cross_exam_plan_models.csv"
DEFAULT_JUDGE_CSV_OUTPUT = REPORT_ROOT / "critical_unit_model_cross_exam_plan_judges.csv"
DEFAULT_TASK_CSV_OUTPUT = REPORT_ROOT / "critical_unit_model_cross_exam_plan_tasks.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "critical_unit_model_cross_exam_plan_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "critical_unit_model_cross_exam_plan.html"

AUTHORITY_POLICY = (
    "The critical unit model cross-exam plan is an execution matrix for benchmark and "
    "advisory judge work. It is not model certification, source approval, reviewer "
    "signoff, translation-text authority, or release authority."
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def serialize_cell(value: Any) -> Any:
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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: serialize_cell(value) for key, value in row.items()})


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def task_ref_lookup(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(task["task_id"]): task for task in tasks}


def result_counts_by_task_model(
    scored_results: list[dict[str, Any]],
    critical_task_ids: set[str],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for result in scored_results:
        task_id = str(result.get("task_id", ""))
        if task_id not in critical_task_ids:
            continue
        model = str(result.get("model_profile_id", ""))
        grouped[(task_id, model)].append(result)
    return grouped


def result_counts_by_unit(
    scored_results: list[dict[str, Any]],
    task_lookup: dict[str, dict[str, Any]],
    critical_task_ids: set[str],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in scored_results:
        task_id = str(result.get("task_id", ""))
        if task_id not in critical_task_ids:
            continue
        task = task_lookup.get(task_id, {})
        unit_id = str(task.get("unit_id", ""))
        if unit_id:
            grouped[unit_id].append(result)
    return grouped


def source_anchor_issue_count(results: list[dict[str, Any]]) -> int:
    return sum(int(row.get("source_anchor_issue_count", 0) or 0) for row in results)


def schema_valid_count(results: list[dict[str, Any]]) -> int:
    return sum(1 for row in results if row.get("schema_valid") is True)


def build_task_rows(
    critical_tasks: list[dict[str, Any]],
    planned_models: list[str],
    candidate_count: int,
    task_model_results: dict[tuple[str, str], list[dict[str, Any]]],
    execution_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    execution_by_task = Counter(str(row["task_id"]) for row in execution_rows)
    rows: list[dict[str, Any]] = []
    for task in critical_tasks:
        task_id = str(task["task_id"])
        results = [
            result
            for model in planned_models
            for result in task_model_results.get((task_id, model), [])
        ]
        expected_model_results = len(planned_models)
        submitted_model_results = len(
            {str(result.get("model_profile_id", "")) for result in results}
        )
        expected_candidate_outputs = expected_model_results * candidate_count
        rows.append(
            {
                "task_id": task_id,
                "unit_id": task["unit_id"],
                "ref": task["ref"],
                "layer": task["layer"],
                "suite_source": task.get("suite_source", ""),
                "benchmark_tags": as_list(task.get("benchmark_tags")),
                "expected_model_result_count": expected_model_results,
                "submitted_model_result_count": submitted_model_results,
                "missing_model_result_count": expected_model_results - submitted_model_results,
                "expected_candidate_output_count": expected_candidate_outputs,
                "schema_valid_result_count": schema_valid_count(results),
                "source_anchor_issue_count": source_anchor_issue_count(results),
                "cross_exam_execution_row_count": execution_by_task.get(task_id, 0),
                "status": (
                    "blocked_missing_model_results"
                    if submitted_model_results < expected_model_results
                    else "results_submitted_pending_review"
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (-int(row["missing_model_result_count"]), str(row["task_id"])),
    )


def build_unit_rows(
    critical_units: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
    unit_results: dict[str, list[dict[str, Any]]],
    cross_exam_packets: list[dict[str, Any]],
    execution_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tasks_by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    packets_by_unit = Counter(str(row["unit_id"]) for row in cross_exam_packets)
    execution_by_unit = Counter(str(row["unit_id"]) for row in execution_rows)
    for row in task_rows:
        tasks_by_unit[str(row["unit_id"])].append(row)
    rows: list[dict[str, Any]] = []
    for unit in critical_units:
        unit_id = str(unit["unit_id"])
        unit_task_rows = tasks_by_unit.get(unit_id, [])
        results = unit_results.get(unit_id, [])
        expected_model_results = sum(
            int(row["expected_model_result_count"]) for row in unit_task_rows
        )
        submitted_model_results = len(
            {
                (str(result.get("task_id", "")), str(result.get("model_profile_id", "")))
                for result in results
            }
        )
        expected_candidates = sum(
            int(row["expected_candidate_output_count"]) for row in unit_task_rows
        )
        rows.append(
            {
                "unit_id": unit_id,
                "ref": unit["ref"],
                "decision_pressure_score": unit["decision_pressure_score"],
                "decision_pressure_band": unit["decision_pressure_band"],
                "task_count": len(unit_task_rows),
                "expected_model_result_count": expected_model_results,
                "submitted_model_result_count": submitted_model_results,
                "missing_model_result_count": expected_model_results - submitted_model_results,
                "expected_candidate_output_count": expected_candidates,
                "schema_valid_result_count": schema_valid_count(results),
                "source_anchor_issue_count": source_anchor_issue_count(results),
                "cross_exam_packet_count": packets_by_unit.get(unit_id, 0),
                "cross_exam_execution_row_count": execution_by_unit.get(unit_id, 0),
                "jewish_christian_separation_required": unit[
                    "jewish_christian_separation_required"
                ],
                "textual_witness_pressure": unit["textual_witness_pressure"],
                "ancient_culture_pressure": unit["ancient_culture_pressure"],
                "clean_source_anchored_attempt_count": unit["clean_source_anchored_attempt_count"],
                "status": "blocked_missing_model_cross_exam",
                "next_action": (
                    "Run all planned model-task rows, then route candidate outputs through "
                    "Codex, Claude, and Hebrew-specialist advisory judges before human review."
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -int(row["missing_model_result_count"]),
            -float(row["decision_pressure_score"]),
            str(row["ref"]),
        ),
    )


def build_model_rows(
    planned_models: list[str],
    critical_task_count: int,
    candidate_count: int,
    scored_results: list[dict[str, Any]],
    critical_task_ids: set[str],
    bakeoff_candidates: list[dict[str, Any]],
    training_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    bakeoff_by_model = {str(row["model"]): row for row in bakeoff_candidates}
    training_by_model = {str(row["model"]): row for row in training_candidates}
    rows: list[dict[str, Any]] = []
    for model in planned_models:
        results = [
            row
            for row in scored_results
            if str(row.get("task_id", "")) in critical_task_ids
            and str(row.get("model_profile_id", "")) == model
        ]
        submitted_tasks = {str(row.get("task_id", "")) for row in results}
        bakeoff = bakeoff_by_model.get(model, {})
        training = training_by_model.get(model, {})
        expected_model_results = critical_task_count
        expected_candidates = critical_task_count * candidate_count
        rows.append(
            {
                "model_profile_id": model,
                "short_name": bakeoff.get("short_name", training.get("short_name", model)),
                "role": bakeoff.get("role", training.get("role", "")),
                "local_asset_status": bakeoff.get(
                    "local_asset_status",
                    training.get("local_asset_status", ""),
                ),
                "doctoral_bakeoff_score_pct": bakeoff.get("doctoral_bakeoff_score_pct", 0.0),
                "training_readiness_score_pct": training.get("training_readiness_score_pct", 0.0),
                "expected_model_result_count": expected_model_results,
                "submitted_model_result_count": len(submitted_tasks),
                "missing_model_result_count": expected_model_results - len(submitted_tasks),
                "expected_candidate_output_count": expected_candidates,
                "schema_valid_result_count": schema_valid_count(results),
                "source_anchor_issue_count": source_anchor_issue_count(results),
                "contextual_clean_source_anchored_pct": bakeoff.get(
                    "contextual_clean_source_anchored_pct",
                    0.0,
                ),
                "status_band": bakeoff.get("status_band", "not_measured"),
                "next_action": bakeoff.get(
                    "current_action",
                    "Acquire/run model profile and score critical benchmark tasks.",
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -int(row["missing_model_result_count"]),
            -float(row["doctoral_bakeoff_score_pct"] or 0.0),
            str(row["model_profile_id"]),
        ),
    )


def build_judge_rows(
    cross_exam_packets: list[dict[str, Any]],
    execution_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    packets_by_judge = defaultdict(list)
    execution_by_judge = defaultdict(list)
    for row in cross_exam_packets:
        packets_by_judge[str(row["judge_id"])].append(row)
    for row in execution_rows:
        execution_by_judge[str(row["judge_id"])].append(row)
    rows: list[dict[str, Any]] = []
    for judge_id in sorted(set(packets_by_judge) | set(execution_by_judge)):
        packets = packets_by_judge.get(judge_id, [])
        execution = execution_by_judge.get(judge_id, [])
        probe_count = sum(len(as_list(packet.get("probe_questions"))) for packet in packets)
        roles = sorted(
            {
                str(role)
                for packet in packets
                for role in as_list(packet.get("required_human_roles"))
            }
        )
        rows.append(
            {
                "judge_id": judge_id,
                "judge_type": packets[0].get("judge_type", "model_critic") if packets else "",
                "authority": packets[0].get("authority", "advisory_only") if packets else "",
                "packet_count": len(packets),
                "execution_row_count": len(execution),
                "probe_question_count": probe_count,
                "required_human_roles": roles,
                "status": "not_executed",
                "next_action": (
                    "Run advisory cross-exam after candidate outputs exist; route concerns "
                    "to the required human reviewer roles."
                ),
            }
        )
    return sorted(rows, key=lambda row: str(row["judge_id"]))


def build_gate_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "gate_id": "MX-GATE-01",
            "gate": "Critical benchmark tasks generated",
            "status": "pass" if summary["critical_task_count"] else "blocked",
            "current_value": f"{summary['critical_task_count']} critical tasks",
            "target_value": "Gloss and literal tasks for every critical unit",
            "blocking_gap": "",
            "next_action": "Keep task identity locked while model outputs are generated.",
        },
        {
            "gate_id": "MX-GATE-02",
            "gate": "Model-task result coverage",
            "status": "blocked" if summary["missing_model_result_count"] else "pass",
            "current_value": (
                f"{summary['submitted_model_result_count']}/"
                f"{summary['expected_model_result_count']} model-task rows submitted"
            ),
            "target_value": "All critical model-task rows submitted and schema-audited",
            "blocking_gap": f"{summary['missing_model_result_count']} model-task rows missing",
            "next_action": "Run planned model profiles across all critical tasks.",
        },
        {
            "gate_id": "MX-GATE-03",
            "gate": "Candidate-output depth",
            "status": "blocked",
            "current_value": (
                f"{summary['expected_candidate_output_count']} expected candidate outputs; "
                f"{summary['submitted_model_result_count']} model-task rows submitted"
            ),
            "target_value": "Three candidate outputs per model-task row",
            "blocking_gap": "Candidate-level output depth is not complete for critical tasks.",
            "next_action": "Generate candidate outputs before judge cross-exam.",
        },
        {
            "gate_id": "MX-GATE-04",
            "gate": "Advisory judge cross-exam execution",
            "status": "blocked" if summary["cross_exam_execution_row_count"] else "not_started",
            "current_value": f"{summary['cross_exam_execution_row_count']} planned execution rows",
            "target_value": "Codex, Claude, and Hebrew-specialist judge rows scored",
            "blocking_gap": "Cross-exam rows are planned but not executed.",
            "next_action": "Run advisory judges after candidate outputs exist.",
        },
        {
            "gate_id": "MX-GATE-05",
            "gate": "Source-anchor and schema integrity",
            "status": "blocked"
            if summary["source_anchor_issue_count"] or summary["missing_model_result_count"]
            else "review_required",
            "current_value": (
                f"{summary['schema_valid_result_count']} schema-valid rows; "
                f"{summary['source_anchor_issue_count']} source-anchor issues"
            ),
            "target_value": "No source-anchor issues and complete schema-valid result set",
            "blocking_gap": "Model evidence is incomplete and source-anchor risks remain.",
            "next_action": (
                "Repair model profiles/prompts before model evidence can support review."
            ),
        },
        {
            "gate_id": "MX-GATE-06",
            "gate": "Human review and release integration",
            "status": "blocked",
            "current_value": "0 critical model cross-exam rows human-approved",
            "target_value": "All advisory concerns routed to human reviewers and release gates",
            "blocking_gap": "Model/cross-exam evidence is advisory and unsigned.",
            "next_action": (
                "Keep model evidence out of authority claims until human review signs off."
            ),
        },
    ]


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    critical_units = data["critical_unit_decision_dossier"]["unit_rows"]
    critical_unit_ids = {str(row["unit_id"]) for row in critical_units}
    expanded_suite = data["contextual_expanded_benchmark_suite"]
    cross_exam = data["contextual_expanded_benchmark_cross_exam"]
    expanded_result_audit = data["contextual_expanded_benchmark_result_audit"]
    real_model = data["contextual_real_model_evidence"]["summary"]
    bakeoff = data["local_model_doctoral_bakeoff"]
    training = data["model_training_certification"]

    planned_models = [str(model) for model in expanded_suite["recommended_bakeoff_models"]]
    candidate_count = int(expanded_suite["summary"]["candidate_count_per_task"])
    critical_tasks = [
        task for task in expanded_suite["tasks"] if str(task["unit_id"]) in critical_unit_ids
    ]
    critical_task_ids = {str(task["task_id"]) for task in critical_tasks}
    task_lookup = task_ref_lookup(critical_tasks)
    scored_results = expanded_result_audit.get("scored_results", [])
    task_model_results = result_counts_by_task_model(scored_results, critical_task_ids)
    unit_results = result_counts_by_unit(scored_results, task_lookup, critical_task_ids)
    critical_packets = [
        row for row in cross_exam["packets"] if str(row["unit_id"]) in critical_unit_ids
    ]
    critical_execution = [
        row for row in cross_exam["execution_matrix"] if str(row["unit_id"]) in critical_unit_ids
    ]

    task_rows = build_task_rows(
        critical_tasks,
        planned_models,
        candidate_count,
        task_model_results,
        critical_execution,
    )
    unit_rows = build_unit_rows(
        critical_units,
        task_rows,
        unit_results,
        critical_packets,
        critical_execution,
    )
    model_rows = build_model_rows(
        planned_models,
        len(critical_tasks),
        candidate_count,
        scored_results,
        critical_task_ids,
        bakeoff["candidate_rows"],
        training["candidate_rows"],
    )
    judge_rows = build_judge_rows(critical_packets, critical_execution)

    expected_model_results = len(critical_tasks) * len(planned_models)
    submitted_model_results = sum(int(row["submitted_model_result_count"]) for row in task_rows)
    expected_candidates = expected_model_results * candidate_count
    schema_valid = sum(int(row["schema_valid_result_count"]) for row in task_rows)
    anchor_issues = sum(int(row["source_anchor_issue_count"]) for row in task_rows)
    missing_model_results = expected_model_results - submitted_model_results
    top_missing_unit = unit_rows[0] if unit_rows else {}
    top_missing_model = model_rows[0] if model_rows else {}
    summary = {
        "critical_unit_count": len(critical_units),
        "critical_task_count": len(critical_tasks),
        "critical_gloss_task_count": sum(1 for task in critical_tasks if task["layer"] == "gloss"),
        "critical_literal_task_count": sum(
            1 for task in critical_tasks if task["layer"] == "literal"
        ),
        "planned_model_count": len(planned_models),
        "candidate_count_per_task": candidate_count,
        "expected_model_result_count": expected_model_results,
        "submitted_model_result_count": submitted_model_results,
        "missing_model_result_count": missing_model_results,
        "model_result_coverage_pct": pct(submitted_model_results, expected_model_results),
        "expected_candidate_output_count": expected_candidates,
        "schema_valid_result_count": schema_valid,
        "schema_valid_expected_pct": pct(schema_valid, expected_model_results),
        "source_anchor_issue_count": anchor_issues,
        "cross_exam_packet_count": len(critical_packets),
        "cross_exam_execution_row_count": len(critical_execution),
        "judge_count": len(judge_rows),
        "probe_question_count": sum(int(row["probe_question_count"]) for row in judge_rows),
        "real_contextual_attempt_count": real_model["attempt_count"],
        "real_contextual_valid_coverage_pct": real_model["valid_model_task_coverage_pct"],
        "real_contextual_source_anchor_issue_count": real_model["source_anchor_issue_count"],
        "training_certification_status": training["summary"]["certification_status"],
        "projected_model_human_review_rows": training["summary"][
            "projected_model_human_review_rows"
        ],
        "projected_cross_exam_rows": training["summary"]["projected_cross_exam_rows"],
        "top_missing_unit_ref": top_missing_unit.get("ref", ""),
        "top_missing_unit_model_rows": top_missing_unit.get("missing_model_result_count", 0),
        "top_missing_model": top_missing_model.get("model_profile_id", ""),
        "top_missing_model_rows": top_missing_model.get("missing_model_result_count", 0),
        "certification_status": "blocked_critical_model_cross_exam_not_executed",
    }
    gate_rows = build_gate_rows(summary)

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "critical_unit_model_cross_exam_plan_generated_not_executed",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": AUTHORITY_POLICY,
        "summary": summary,
        "unit_rows": unit_rows,
        "model_rows": model_rows,
        "judge_rows": judge_rows,
        "task_rows": task_rows,
        "gate_rows": gate_rows,
        "visual_data": {
            "unit_missing_rows": [
                {"label": row["ref"], "value": row["missing_model_result_count"]}
                for row in unit_rows
            ],
            "model_missing_rows": [
                {"label": row["short_name"], "value": row["missing_model_result_count"]}
                for row in model_rows
            ],
            "judge_execution_rows": [
                {"label": row["judge_id"], "value": row["execution_row_count"]}
                for row in judge_rows
            ],
            "layer_task_rows": [
                {"label": layer, "value": count}
                for layer, count in sorted(Counter(row["layer"] for row in task_rows).items())
            ],
            "gate_blocker_rows": [
                {"label": row["gate_id"], "value": 1 if row["status"] == "blocked" else 0}
                for row in gate_rows
            ],
        },
    }


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
    row_h = 30
    left = 285
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
    unit_rows = [
        [
            index,
            row["ref"],
            f"{row['decision_pressure_score']:.2f}",
            row["task_count"],
            row["expected_model_result_count"],
            row["submitted_model_result_count"],
            row["missing_model_result_count"],
            row["expected_candidate_output_count"],
            row["cross_exam_execution_row_count"],
            "yes" if row["jewish_christian_separation_required"] else "no",
            row["status"],
        ]
        for index, row in enumerate(report["unit_rows"][:35], start=1)
    ]
    model_rows = [
        [
            row["short_name"],
            row["model_profile_id"],
            row["local_asset_status"],
            f"{row['doctoral_bakeoff_score_pct']:.2f}",
            row["expected_model_result_count"],
            row["submitted_model_result_count"],
            row["missing_model_result_count"],
            row["schema_valid_result_count"],
            row["source_anchor_issue_count"],
            row["status_band"],
        ]
        for row in report["model_rows"]
    ]
    judge_rows = [
        [
            row["judge_id"],
            row["authority"],
            row["packet_count"],
            row["execution_row_count"],
            row["probe_question_count"],
            "; ".join(row["required_human_roles"]),
            row["status"],
        ]
        for row in report["judge_rows"]
    ]
    task_rows = [
        [
            row["task_id"],
            row["ref"],
            row["layer"],
            row["expected_model_result_count"],
            row["submitted_model_result_count"],
            row["missing_model_result_count"],
            row["cross_exam_execution_row_count"],
            row["status"],
        ]
        for row in report["task_rows"][:100]
    ]
    gate_rows = [
        [
            row["gate_id"],
            row["gate"],
            row["status"],
            row["current_value"],
            row["target_value"],
            row["blocking_gap"],
            row["next_action"],
        ]
        for row in report["gate_rows"]
    ]
    visual = report["visual_data"]
    cards = metric_cards(
        [
            (
                "Critical tasks",
                summary["critical_task_count"],
                (
                    f"{summary['critical_gloss_task_count']} gloss and "
                    f"{summary['critical_literal_task_count']} literal."
                ),
            ),
            (
                "Model-task rows",
                f"{summary['submitted_model_result_count']}/{summary['expected_model_result_count']}",
                f"{summary['model_result_coverage_pct']:.2f}% submitted.",
            ),
            (
                "Candidate outputs",
                summary["expected_candidate_output_count"],
                "Expected at three candidates per model-task row.",
            ),
            (
                "Cross-exam rows",
                summary["cross_exam_execution_row_count"],
                f"{summary['cross_exam_packet_count']} judge packets.",
            ),
            (
                "Judges",
                summary["judge_count"],
                f"{summary['probe_question_count']} probe questions.",
            ),
            (
                "Top missing model",
                summary["top_missing_model"],
                f"{summary['top_missing_model_rows']} missing model-task rows.",
            ),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Critical Unit Model Cross-Exam Plan</title>
  <style>
    body {{
      font-family: Inter, Segoe UI, sans-serif;
      color: #24313a;
      margin: 0;
      background: #f6f4ef;
    }}
    header {{
      background: #21333c;
      color: white;
      padding: 30px 44px;
    }}
    main {{ padding: 28px 44px 48px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin: 28px 0; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin: 16px 0;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #d6d2c8;
      border-radius: 8px;
      padding: 14px;
    }}
    .metric {{
      font-size: 28px;
      font-weight: 800;
      color: #20343b;
      overflow-wrap: anywhere;
    }}
    .label {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0;
      color: #56636b;
      font-weight: 700;
      margin-top: 4px;
    }}
    .warning {{
      background: #fff8e6;
      border: 1px solid #d9bc66;
      border-left: 5px solid #9b6a1f;
      padding: 12px 14px;
      margin: 12px 0 18px;
    }}
    .chart {{
      background: white;
      border: 1px solid #d6d2c8;
      border-radius: 8px;
      padding: 10px;
      margin: 14px 0;
      overflow-x: auto;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      background: white;
      margin: 14px 0 22px;
      font-size: 12px;
    }}
    th, td {{
      border: 1px solid #d6d2c8;
      padding: 8px 9px;
      vertical-align: top;
    }}
    th {{
      background: #e8e3d8;
      text-align: left;
      font-weight: 800;
    }}
    td {{ overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <header>
    <h1>Critical Unit Model Cross-Exam Plan</h1>
    <p>
      Critical-unit benchmark coverage, planned local-model runs, advisory
      Codex/Claude/Hebrew-specialist cross-exam rows, and blocked authority gates.
    </p>
  </header>
  <main>
    <section>
      <div class="warning">
        <strong>Authority boundary:</strong> {esc(report["authority_policy"])}
      </div>
      {cards}
    </section>

    <section>
      <h2>Visual Matrix</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["unit_missing_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit missing model-task rows",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["model_missing_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit missing rows by model",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["judge_execution_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit cross-exam execution rows by judge",
            color="#2f6f73",
        )
    }</div>
    </section>

    <section>
      <h2>Unit Matrix</h2>
      {
        table(
            [
                "Rank",
                "Ref",
                "Pressure",
                "Tasks",
                "Expected Model Rows",
                "Submitted",
                "Missing",
                "Candidate Outputs",
                "Cross-Exam Rows",
                "J/C Split",
                "Status",
            ],
            unit_rows,
        )
    }
    </section>

    <section>
      <h2>Model Matrix</h2>
      {
        table(
            [
                "Model",
                "Profile",
                "Local Asset",
                "Bakeoff",
                "Expected Rows",
                "Submitted",
                "Missing",
                "Schema Valid",
                "Anchor Issues",
                "Status",
            ],
            model_rows,
        )
    }
    </section>

    <section>
      <h2>Judge Matrix</h2>
      {
        table(
            [
                "Judge",
                "Authority",
                "Packets",
                "Execution Rows",
                "Probe Questions",
                "Human Roles",
                "Status",
            ],
            judge_rows,
        )
    }
    </section>

    <section>
      <h2>Benchmark Tasks</h2>
      {
        table(
            [
                "Task",
                "Ref",
                "Layer",
                "Expected Rows",
                "Submitted",
                "Missing",
                "Cross-Exam Rows",
                "Status",
            ],
            task_rows,
        )
    }
    </section>

    <section>
      <h2>Execution Gates</h2>
      {
        table(
            [
                "Gate",
                "Name",
                "Status",
                "Current",
                "Target",
                "Blocking Gap",
                "Next Action",
            ],
            gate_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate critical unit model cross-exam expansion plan."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--model-csv-output", type=Path, default=DEFAULT_MODEL_CSV_OUTPUT)
    parser.add_argument("--judge-csv-output", type=Path, default=DEFAULT_JUDGE_CSV_OUTPUT)
    parser.add_argument("--task-csv-output", type=Path, default=DEFAULT_TASK_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.model_csv_output, report["model_rows"])
    write_csv(args.judge_csv_output, report["judge_rows"])
    write_csv(args.task_csv_output, report["task_rows"])
    write_csv(args.gate_csv_output, report["gate_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.model_csv_output}")
    print(f"Wrote {args.judge_csv_output}")
    print(f"Wrote {args.task_csv_output}")
    print(f"Wrote {args.gate_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
