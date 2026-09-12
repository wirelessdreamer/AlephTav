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

SUITE_PATH = REPORT_ROOT / "contextual_expanded_benchmark_suite.json"
AUDIT_PATH = REPORT_ROOT / "contextual_expanded_benchmark_result_audit.json"
CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "model_evidence_gap_report.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "model_evidence_gap_units.csv"
DEFAULT_MODEL_CSV_OUTPUT = REPORT_ROOT / "model_evidence_gap_models.csv"
DEFAULT_DOMAIN_CSV_OUTPUT = REPORT_ROOT / "model_evidence_gap_domains.csv"
DEFAULT_CONTROL_CSV_OUTPUT = REPORT_ROOT / "model_evidence_gap_controls.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "model_evidence_gap_report.html"


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


def fmt_pct(value: Any) -> str:
    return f"{float(value):.2f}%"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def join_values(values: list[Any], limit: int = 6) -> str:
    text = [str(value) for value in values if value not in (None, "")]
    if len(text) <= limit:
        return ", ".join(text)
    return ", ".join(text[:limit]) + f", +{len(text) - limit} more"


def unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return output


def task_index(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(task["task_id"]): task for task in suite.get("tasks", [])}


def unit_task_rows(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for task in suite.get("tasks", []):
        unit_id = str(task["unit_id"])
        row = rows.setdefault(
            unit_id,
            {
                "unit_id": unit_id,
                "ref": task.get("ref", ""),
                "task_ids": [],
                "layers": set(),
                "benchmark_tags": set(),
                "token_count": 0,
                "outside_psalms_context_pct": 0.0,
            },
        )
        row["task_ids"].append(str(task["task_id"]))
        row["layers"].add(str(task.get("layer", "")))
        row["benchmark_tags"].update(str(tag) for tag in task.get("benchmark_tags", []))
        row["token_count"] = max(int(row["token_count"]), int(task.get("token_count") or 0))
        row["outside_psalms_context_pct"] = max(
            float(row["outside_psalms_context_pct"]),
            float(task.get("outside_psalms_context_pct") or 0),
        )

    for row in rows.values():
        row["layers"] = sorted(row["layers"])
        row["benchmark_tags"] = sorted(row["benchmark_tags"])
        row["task_count"] = len(row["task_ids"])
    return rows


def claim_rows_by_unit(claim_matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["unit_id"]): row
        for row in claim_matrix.get("unit_claim_rows", [])
        if row.get("unit_id")
    }


def scored_rows_by_task_model(
    audit: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in audit.get("scored_results", []):
        task_id = str(row.get("task_id") or "")
        model = str(row.get("model_profile_id") or "")
        if task_id and model:
            rows[(task_id, model)] = row
    return rows


def model_gap_rows(
    *,
    suite: dict[str, Any],
    audit: dict[str, Any],
    scored: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    tasks = [str(task["task_id"]) for task in suite.get("tasks", [])]
    rows = []
    for model in suite.get("recommended_bakeoff_models", []):
        model_id = str(model)
        submitted = [
            scored[(task_id, model_id)] for task_id in tasks if (task_id, model_id) in scored
        ]
        schema_valid = [row for row in submitted if row.get("schema_valid")]
        expected = len(tasks)
        anchor_issues = sum(int(row.get("source_anchor_issue_count") or 0) for row in submitted)
        rows.append(
            {
                "model_profile_id": model_id,
                "expected_task_results": expected,
                "submitted_results": len(submitted),
                "schema_valid_results": len(schema_valid),
                "missing_results": expected - len(submitted),
                "submitted_expected_pct": pct(len(submitted), expected),
                "schema_valid_expected_pct": pct(len(schema_valid), expected),
                "schema_valid_submitted_pct": pct(len(schema_valid), len(submitted)),
                "source_anchor_issue_count": anchor_issues,
                "status": model_status(
                    expected=expected,
                    submitted=len(submitted),
                    schema_valid=len(schema_valid),
                    source_anchor_issues=anchor_issues,
                ),
            }
        )

    observed_models = {
        str(row.get("model_profile_id") or "")
        for row in audit.get("scored_results", [])
        if row.get("model_profile_id")
    }
    planned_models = {str(model) for model in suite.get("recommended_bakeoff_models", [])}
    for model_id in sorted(observed_models - planned_models):
        submitted = [
            row
            for row in audit.get("scored_results", [])
            if str(row.get("model_profile_id")) == model_id
        ]
        rows.append(
            {
                "model_profile_id": model_id,
                "expected_task_results": 0,
                "submitted_results": len(submitted),
                "schema_valid_results": sum(1 for row in submitted if row.get("schema_valid")),
                "missing_results": 0,
                "submitted_expected_pct": 0.0,
                "schema_valid_expected_pct": 0.0,
                "schema_valid_submitted_pct": pct(
                    sum(1 for row in submitted if row.get("schema_valid")),
                    len(submitted),
                ),
                "source_anchor_issue_count": sum(
                    int(row.get("source_anchor_issue_count") or 0) for row in submitted
                ),
                "status": "unexpected_model_profile",
            }
        )
    return rows


def model_status(
    *,
    expected: int,
    submitted: int,
    schema_valid: int,
    source_anchor_issues: int,
) -> str:
    if expected and schema_valid == expected and source_anchor_issues == 0:
        return "complete_schema_valid_grid"
    if source_anchor_issues:
        return "source_anchor_review_required"
    if schema_valid:
        return "partial_schema_valid_evidence"
    if submitted:
        return "submitted_but_no_schema_valid_evidence"
    return "not_run"


def unit_gap_priority(
    *,
    expected: int,
    schema_valid: int,
    claim: dict[str, Any],
) -> float:
    claim_score = float(claim.get("claim_risk_score") or 0)
    missing_pct = pct(expected - schema_valid, expected)
    score = claim_score * (missing_pct / 100)
    if schema_valid == 0:
        score += 35
    if claim.get("reception_sensitive"):
        score += 10
    if claim.get("textual_witness_pressure"):
        score += 10
    if claim.get("ancient_culture_pressure"):
        score += 8
    if claim.get("has_jewish_reception_frame") and claim.get("has_christian_reception_frame"):
        score += 10
    if float(claim.get("outside_strong_context_pct") or 0) == 0:
        score += 6
    return round(score, 2)


def evidence_status(
    *,
    expected: int,
    submitted: int,
    schema_valid: int,
    anchor_issues: int,
) -> str:
    if anchor_issues:
        return "source_anchor_review_required"
    if schema_valid == expected and expected:
        return "complete_schema_valid_grid"
    if schema_valid:
        return "partial_schema_valid_evidence"
    if submitted:
        return "submitted_but_no_schema_valid_evidence"
    return "no_real_model_evidence"


def next_action(status: str) -> str:
    if status == "no_real_model_evidence":
        return "run gloss/literal tasks through first local generator and one challenger"
    if status == "submitted_but_no_schema_valid_evidence":
        return "retry with stricter structured-output settings before quality review"
    if status == "partial_schema_valid_evidence":
        return "complete remaining planned model grid, then route human review"
    if status == "source_anchor_review_required":
        return "block quality scoring until Hebrew source-anchor transport is fixed"
    return "route complete model grid to human review"


def unit_gap_rows(
    *,
    suite: dict[str, Any],
    claim_matrix: dict[str, Any],
    audit: dict[str, Any],
) -> list[dict[str, Any]]:
    models = [str(model) for model in suite.get("recommended_bakeoff_models", [])]
    tasks = task_index(suite)
    units = unit_task_rows(suite)
    claims = claim_rows_by_unit(claim_matrix)
    scored = scored_rows_by_task_model(audit)

    submitted_by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    valid_by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    valid_models_by_unit: dict[str, set[str]] = defaultdict(set)
    submitted_models_by_unit: dict[str, set[str]] = defaultdict(set)
    valid_layers_by_unit: dict[str, set[str]] = defaultdict(set)
    source_anchor_by_unit: Counter[str] = Counter()

    for (task_id, model), result in scored.items():
        task = tasks.get(task_id)
        if not task:
            continue
        unit_id = str(task["unit_id"])
        submitted_by_unit[unit_id].append(result)
        submitted_models_by_unit[unit_id].add(model)
        source_anchor_by_unit[unit_id] += int(result.get("source_anchor_issue_count") or 0)
        if result.get("schema_valid"):
            valid_by_unit[unit_id].append(result)
            valid_models_by_unit[unit_id].add(model)
            valid_layers_by_unit[unit_id].add(str(task.get("layer", "")))

    rows = []
    for unit_id, unit in units.items():
        claim = claims.get(unit_id, {})
        expected = len(unit["task_ids"]) * len(models)
        submitted = len(submitted_by_unit.get(unit_id, []))
        schema_valid = len(valid_by_unit.get(unit_id, []))
        anchor_issues = int(source_anchor_by_unit.get(unit_id, 0))
        status = evidence_status(
            expected=expected,
            submitted=submitted,
            schema_valid=schema_valid,
            anchor_issues=anchor_issues,
        )
        missing_models = [model for model in models if model not in valid_models_by_unit[unit_id]]
        missing_layers = [
            layer for layer in unit["layers"] if layer not in valid_layers_by_unit[unit_id]
        ]
        row = {
            "unit_id": unit_id,
            "ref": unit["ref"],
            "evidence_status": status,
            "next_action": next_action(status),
            "gap_priority_score": unit_gap_priority(
                expected=expected,
                schema_valid=schema_valid,
                claim=claim,
            ),
            "claim_risk_score": round(float(claim.get("claim_risk_score") or 0), 2),
            "claim_risk_band": claim.get("claim_risk_band", "unknown"),
            "expected_model_task_results": expected,
            "submitted_results": submitted,
            "schema_valid_results": schema_valid,
            "missing_results": expected - submitted,
            "submitted_expected_pct": pct(submitted, expected),
            "schema_valid_expected_pct": pct(schema_valid, expected),
            "valid_model_count": len(valid_models_by_unit[unit_id]),
            "submitted_model_count": len(submitted_models_by_unit[unit_id]),
            "planned_model_count": len(models),
            "source_anchor_issue_count": anchor_issues,
            "task_count": unit["task_count"],
            "layers": unit["layers"],
            "valid_layers": sorted(valid_layers_by_unit[unit_id]),
            "missing_layers": missing_layers,
            "missing_model_profiles": missing_models,
            "benchmark_tags": unit["benchmark_tags"],
            "high_risk_tags": claim.get("high_risk_tags", []),
            "domains": claim.get("domains", []),
            "domain_groups": claim.get("domain_groups", []),
            "required_frames": claim.get("required_frames", []),
            "required_review_roles": claim.get("required_review_roles", []),
            "claim_controls": claim.get("claim_controls", []),
            "reception_sensitive": bool(claim.get("reception_sensitive")),
            "jewish_christian_separation": bool(
                claim.get("has_jewish_reception_frame")
                and claim.get("has_christian_reception_frame")
            ),
            "textual_witness_pressure": bool(claim.get("textual_witness_pressure")),
            "ancient_culture_pressure": bool(claim.get("ancient_culture_pressure")),
            "theology_pressure": bool(claim.get("theology_pressure")),
            "complete_expected_witness_set": bool(claim.get("complete_expected_witness_set")),
            "surface_outside_context_pct": float(
                claim.get("surface_outside_context_pct")
                or unit.get("outside_psalms_context_pct")
                or 0
            ),
            "outside_strong_context_pct": float(claim.get("outside_strong_context_pct") or 0),
        }
        rows.append(row)

    return sorted(
        rows,
        key=lambda row: (
            -float(row["gap_priority_score"]),
            -float(row["claim_risk_score"]),
            str(row["unit_id"]),
        ),
    )


def domain_gap_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for unit in unit_rows:
        domains = unit.get("domains") or ["unclassified"]
        for domain in domains:
            text = str(domain)
            row = rows.setdefault(
                text,
                {
                    "domain": text,
                    "unit_count": 0,
                    "no_real_model_evidence_units": 0,
                    "no_schema_valid_units": 0,
                    "partial_schema_valid_units": 0,
                    "complete_schema_valid_units": 0,
                    "high_risk_units": 0,
                    "avg_gap_priority_score": 0.0,
                    "total_gap_priority_score": 0.0,
                },
            )
            row["unit_count"] += 1
            row["total_gap_priority_score"] += float(unit["gap_priority_score"])
            if unit["evidence_status"] == "no_real_model_evidence":
                row["no_real_model_evidence_units"] += 1
            if int(unit["schema_valid_results"]) == 0:
                row["no_schema_valid_units"] += 1
            if unit["evidence_status"] == "partial_schema_valid_evidence":
                row["partial_schema_valid_units"] += 1
            if unit["evidence_status"] == "complete_schema_valid_grid":
                row["complete_schema_valid_units"] += 1
            if unit["claim_risk_band"] == "high":
                row["high_risk_units"] += 1
    for row in rows.values():
        row["avg_gap_priority_score"] = round(
            float(row["total_gap_priority_score"]) / max(1, int(row["unit_count"])),
            2,
        )
    return sorted(
        rows.values(),
        key=lambda row: (
            -int(row["no_schema_valid_units"]),
            -float(row["avg_gap_priority_score"]),
            str(row["domain"]),
        ),
    )


def control_gap_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for unit in unit_rows:
        for control in unit.get("claim_controls") or []:
            text = str(control)
            row = rows.setdefault(
                text,
                {
                    "claim_control": text,
                    "unit_count": 0,
                    "no_schema_valid_units": 0,
                    "high_risk_units": 0,
                    "reception_sensitive_units": 0,
                    "jewish_christian_units": 0,
                    "textual_witness_units": 0,
                },
            )
            row["unit_count"] += 1
            if int(unit["schema_valid_results"]) == 0:
                row["no_schema_valid_units"] += 1
            if unit["claim_risk_band"] == "high":
                row["high_risk_units"] += 1
            if unit["reception_sensitive"]:
                row["reception_sensitive_units"] += 1
            if unit["jewish_christian_separation"]:
                row["jewish_christian_units"] += 1
            if unit["textual_witness_pressure"]:
                row["textual_witness_units"] += 1
    return sorted(
        rows.values(),
        key=lambda row: (
            -int(row["no_schema_valid_units"]),
            -int(row["high_risk_units"]),
            str(row["claim_control"]),
        ),
    )


def summarize(
    *,
    suite: dict[str, Any],
    audit: dict[str, Any],
    claim_matrix: dict[str, Any],
    unit_rows: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    audit_summary = audit.get("summary", {})
    expected = int(audit_summary.get("expected_result_count") or 0)
    submitted = int(audit_summary.get("submitted_result_count") or 0)
    schema_valid = int(audit_summary.get("schema_valid_result_count") or 0)
    status_counts = Counter(str(row["evidence_status"]) for row in unit_rows)
    high_risk_rows = [row for row in unit_rows if row["claim_risk_band"] == "high"]
    no_valid_rows = [row for row in unit_rows if int(row["schema_valid_results"]) == 0]
    no_real_rows = [row for row in unit_rows if row["evidence_status"] == "no_real_model_evidence"]
    partial_rows = [
        row for row in unit_rows if row["evidence_status"] == "partial_schema_valid_evidence"
    ]
    top_gap = unit_rows[0] if unit_rows else {}
    top_no_real = no_real_rows[0] if no_real_rows else {}
    top_partial = partial_rows[0] if partial_rows else {}
    return {
        "expanded_task_count": len(suite.get("tasks", [])),
        "expanded_unit_count": len(unit_rows),
        "planned_model_count": len(suite.get("recommended_bakeoff_models", [])),
        "expected_result_count": expected,
        "submitted_result_count": submitted,
        "schema_valid_result_count": schema_valid,
        "missing_expected_result_count": int(
            audit_summary.get("missing_expected_result_count") or expected - submitted
        ),
        "submitted_expected_pct": pct(submitted, expected),
        "schema_valid_expected_pct": pct(schema_valid, expected),
        "schema_valid_submitted_pct": pct(schema_valid, submitted),
        "source_anchor_issue_count": int(audit_summary.get("source_anchor_issue_count") or 0),
        "unit_with_any_submission_count": sum(
            1 for row in unit_rows if int(row["submitted_results"]) > 0
        ),
        "unit_with_schema_valid_count": sum(
            1 for row in unit_rows if int(row["schema_valid_results"]) > 0
        ),
        "unit_without_schema_valid_count": len(no_valid_rows),
        "high_risk_unit_count": len(high_risk_rows),
        "high_risk_without_schema_valid_count": sum(
            1 for row in high_risk_rows if int(row["schema_valid_results"]) == 0
        ),
        "reception_sensitive_without_schema_valid_count": sum(
            1
            for row in unit_rows
            if row["reception_sensitive"] and int(row["schema_valid_results"]) == 0
        ),
        "jewish_christian_without_schema_valid_count": sum(
            1
            for row in unit_rows
            if row["jewish_christian_separation"] and int(row["schema_valid_results"]) == 0
        ),
        "textual_witness_without_schema_valid_count": sum(
            1
            for row in unit_rows
            if row["textual_witness_pressure"] and int(row["schema_valid_results"]) == 0
        ),
        "ancient_culture_without_schema_valid_count": sum(
            1
            for row in unit_rows
            if row["ancient_culture_pressure"] and int(row["schema_valid_results"]) == 0
        ),
        "status_counts": dict(status_counts.most_common()),
        "model_status_counts": dict(
            Counter(str(row["status"]) for row in model_rows).most_common()
        ),
        "claim_matrix_high_risk_units": claim_matrix.get("summary", {}).get(
            "high_risk_unit_count",
            0,
        ),
        "claim_matrix_jewish_christian_units": claim_matrix.get("summary", {}).get(
            "jewish_christian_separation_unit_count",
            0,
        ),
        "top_gap_unit": top_gap.get("unit_id"),
        "top_gap_ref": top_gap.get("ref"),
        "top_gap_priority_score": top_gap.get("gap_priority_score", 0),
        "top_gap_claim_risk_score": top_gap.get("claim_risk_score", 0),
        "top_gap_status": top_gap.get("evidence_status", ""),
        "top_no_real_model_evidence_unit": top_no_real.get("unit_id"),
        "top_no_real_model_evidence_ref": top_no_real.get("ref"),
        "top_no_real_model_evidence_priority_score": top_no_real.get(
            "gap_priority_score",
            0,
        ),
        "top_partial_schema_valid_unit": top_partial.get("unit_id"),
        "top_partial_schema_valid_ref": top_partial.get("ref"),
        "top_partial_schema_valid_priority_score": top_partial.get(
            "gap_priority_score",
            0,
        ),
    }


def build_report(
    *,
    suite_path: Path,
    audit_path: Path,
    claim_matrix_path: Path,
) -> dict[str, Any]:
    suite = load_json(suite_path)
    audit = load_json(audit_path)
    claim_matrix = load_json(claim_matrix_path)
    scored = scored_rows_by_task_model(audit)
    models = model_gap_rows(suite=suite, audit=audit, scored=scored)
    units = unit_gap_rows(suite=suite, claim_matrix=claim_matrix, audit=audit)
    domains = domain_gap_rows(units)
    controls = control_gap_rows(units)
    summary = summarize(
        suite=suite,
        audit=audit,
        claim_matrix=claim_matrix,
        unit_rows=units,
        model_rows=models,
    )
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": (
            "real local-model evidence gap report; automated coverage only, "
            "not translation-quality signoff"
        ),
        "source_paths": {
            "suite": rel(suite_path),
            "audit": rel(audit_path),
            "translation_claim_evidence_matrix": rel(claim_matrix_path),
        },
        "summary": summary,
        "model_rows": models,
        "unit_gap_rows": units,
        "domain_gap_rows": domains,
        "claim_control_gap_rows": controls,
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


def rows_from_counter(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
    return [
        {label_key: key, "count": value}
        for key, value in sorted(counter.items(), key=lambda item: item[1], reverse=True)
    ]


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    model_rows = report["model_rows"]
    unit_rows = report["unit_gap_rows"]
    domain_rows = report["domain_gap_rows"]
    control_rows = report["claim_control_gap_rows"]
    top_units = unit_rows[:30]
    model_table_rows = [
        [
            row["model_profile_id"],
            fmt_int(row["submitted_results"]),
            fmt_int(row["schema_valid_results"]),
            fmt_int(row["missing_results"]),
            fmt_pct(row["schema_valid_expected_pct"]),
            row["status"],
        ]
        for row in model_rows
    ]
    unit_table_rows = [
        [
            row["unit_id"],
            row["ref"],
            row["evidence_status"],
            f"{row['gap_priority_score']:.2f}",
            f"{row['claim_risk_score']:.2f}",
            fmt_int(row["schema_valid_results"]),
            fmt_int(row["missing_results"]),
            join_values(row["domains"], limit=4),
            join_values(row["required_frames"], limit=4),
            row["next_action"],
        ]
        for row in top_units
    ]
    domain_chart_rows = [
        {
            "domain": row["domain"],
            "no_schema_valid_units": row["no_schema_valid_units"],
        }
        for row in domain_rows
    ]
    control_chart_rows = [
        {
            "claim_control": row["claim_control"],
            "no_schema_valid_units": row["no_schema_valid_units"],
        }
        for row in control_rows
    ]
    model_chart_rows = [
        {
            "model": row["model_profile_id"],
            "schema_valid_expected_pct": row["schema_valid_expected_pct"],
        }
        for row in model_rows
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Model Evidence Gap Report</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2a33;
      --muted: #667581;
      --line: #d7dde2;
      --band: #f5f7f8;
      --accent: #2f6f73;
      --warn: #9b3d3d;
      --gold: #8a6a24;
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
    main {{ max-width: 1220px; margin: 0 auto; padding: 30px 34px 54px; }}
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
      background: #fff6df;
      border-left: 4px solid var(--gold);
      padding: 13px 15px;
      margin: 18px 0;
    }}
    .critical {{
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
    <h1>AlephTav Model Evidence Gap Report</h1>
    <p class="lede">
      Unit-level crosswalk between the contextual expanded benchmark, real
      local-model result audit, and translation-claim evidence matrix. This
      report identifies where high-risk cultural, textual, canonical, and
      reception-sensitive units still lack schema-valid local-model evidence.
    </p>
    <p class="meta">
      Generated {esc(report["generated_on"])} from {esc(report["source_paths"]["audit"])}.
    </p>
  </header>
  <main>
    <section>
      <h2>Coverage Reality</h2>
      {
        metric_cards(
            [
                (
                    "Expected model-task rows",
                    fmt_int(summary["expected_result_count"]),
                    "Expanded benchmark tasks multiplied by planned bake-off models.",
                ),
                (
                    "Submitted",
                    fmt_pct(summary["submitted_expected_pct"]),
                    f'''{fmt_int(summary["submitted_result_count"])} real rows submitted.''',
                ),
                (
                    "Schema-valid expected",
                    fmt_pct(summary["schema_valid_expected_pct"]),
                    f'''{fmt_int(summary["schema_valid_result_count"])} rows pass schema.''',
                ),
                (
                    "Units without valid rows",
                    fmt_int(summary["unit_without_schema_valid_count"]),
                    "Expanded benchmark units with no schema-valid local model output.",
                ),
                (
                    "High-risk without valid rows",
                    fmt_int(summary["high_risk_without_schema_valid_count"]),
                    "High claim-risk units with no schema-valid local model output.",
                ),
                (
                    "Reception gaps",
                    fmt_int(summary["reception_sensitive_without_schema_valid_count"]),
                    "Reception-sensitive units lacking schema-valid local output.",
                ),
                (
                    "Jewish/Christian gaps",
                    fmt_int(summary["jewish_christian_without_schema_valid_count"]),
                    "Units requiring Jewish/Christian separation and still lacking valid output.",
                ),
                (
                    "Anchor issues",
                    fmt_int(summary["source_anchor_issue_count"]),
                    "Automated source-anchor mismatch count in submitted rows.",
                ),
                (
                    "Top no-evidence gap",
                    summary["top_no_real_model_evidence_unit"] or "none",
                    summary["top_no_real_model_evidence_ref"] or "All units have rows.",
                ),
                (
                    "Top partial-grid gap",
                    summary["top_partial_schema_valid_unit"] or "none",
                    summary["top_partial_schema_valid_ref"] or "No partial rows.",
                ),
            ]
        )
    }
      <div class="critical">
        This is a coverage and traceability report, not a quality verdict.
        Schema-valid output only earns entry into human Hebrew, lexical,
        cultural, poetic, and theological review.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["status_counts"], "status"),
            label_key="status",
            value_key="count",
            aria_label="Unit evidence status counts",
            color="#9b3d3d",
        )
    }</div>
    </section>

    <section>
      <h2>Model Grid</h2>
      <div class="chart">{
        svg_horizontal_bars(
            model_chart_rows,
            label_key="model",
            value_key="schema_valid_expected_pct",
            aria_label="Schema-valid expected percentage by model",
            color="#2f6f73",
        )
    }</div>
      {
        table(
            [
                "Model",
                "Submitted",
                "Schema-valid",
                "Missing",
                "Valid / expected",
                "Status",
            ],
            model_table_rows,
        )
    }
    </section>

    <section>
      <h2>Domain Gaps</h2>
      <div class="chart">{
        svg_horizontal_bars(
            domain_chart_rows,
            label_key="domain",
            value_key="no_schema_valid_units",
            aria_label="Domain units without schema-valid model evidence",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Domain",
                "Units",
                "No valid",
                "High risk",
                "Partial valid",
                "Avg gap priority",
            ],
            [
                [
                    row["domain"],
                    fmt_int(row["unit_count"]),
                    fmt_int(row["no_schema_valid_units"]),
                    fmt_int(row["high_risk_units"]),
                    fmt_int(row["partial_schema_valid_units"]),
                    f'''{row["avg_gap_priority_score"]:.2f}''',
                ]
                for row in domain_rows
            ],
        )
    }
    </section>

    <section>
      <h2>Highest Priority Unit Gaps</h2>
      {
        table(
            [
                "Unit",
                "Reference",
                "Status",
                "Gap score",
                "Claim risk",
                "Valid rows",
                "Missing rows",
                "Domains",
                "Frames",
                "Next action",
            ],
            unit_table_rows,
        )
    }
    </section>

    <section>
      <h2>Claim-Control Gaps</h2>
      <div class="chart">{
        svg_horizontal_bars(
            control_chart_rows,
            label_key="claim_control",
            value_key="no_schema_valid_units",
            aria_label="Claim controls without schema-valid model evidence",
            color="#58508d",
            limit=18,
        )
    }</div>
      <div class="warning">
        Claim controls remain mandatory even when model output exists. The model
        can supply candidate evidence, but source boundaries, witness use,
        Jewish/Christian separation, and reviewer signoff are policy gates.
      </div>
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a real local-model evidence gap report.")
    parser.add_argument("--suite", type=Path, default=SUITE_PATH)
    parser.add_argument("--audit", type=Path, default=AUDIT_PATH)
    parser.add_argument("--claim-matrix", type=Path, default=CLAIM_MATRIX_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--model-csv-output", type=Path, default=DEFAULT_MODEL_CSV_OUTPUT)
    parser.add_argument("--domain-csv-output", type=Path, default=DEFAULT_DOMAIN_CSV_OUTPUT)
    parser.add_argument(
        "--control-csv-output",
        type=Path,
        default=DEFAULT_CONTROL_CSV_OUTPUT,
    )
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        suite_path=args.suite,
        audit_path=args.audit,
        claim_matrix_path=args.claim_matrix,
    )
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_gap_rows"])
    write_csv(args.model_csv_output, report["model_rows"])
    write_csv(args.domain_csv_output, report["domain_gap_rows"])
    write_csv(args.control_csv_output, report["claim_control_gap_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.model_csv_output}")
    print(f"Wrote {args.domain_csv_output}")
    print(f"Wrote {args.control_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
