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

SOURCE_PATHS = {
    "synthesis": REPORT_ROOT / "doctoral_translation_synthesis.json",
    "authority": REPORT_ROOT / "scholarly_authority_readiness.json",
    "review_workbook": REPORT_ROOT / "contextual_review_signoff_workbook.json",
    "unit_heatmap": REPORT_ROOT / "doctoral_unit_authority_heatmap.json",
    "bibliography": REPORT_ROOT / "doctoral_bibliography_provenance.json",
    "source_acquisition": REPORT_ROOT / "contextual_source_acquisition_plan.json",
    "morphology_unlock": REPORT_ROOT / "whole_tanakh_morphology_unlock_matrix.json",
    "local_bakeoff": REPORT_ROOT / "local_model_doctoral_bakeoff_matrix.json",
    "contextual_real_model": REPORT_ROOT / "contextual_real_model_evidence_matrix.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "authority_critical_path_report.json"
DEFAULT_PHASE_CSV_OUTPUT = REPORT_ROOT / "authority_critical_path_phases.csv"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "authority_critical_path_units.csv"
DEFAULT_ROLE_CSV_OUTPUT = REPORT_ROOT / "authority_critical_path_roles.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "authority_critical_path_report.html"

SEVERITY_ORDER = {"critical": 0, "hard": 1, "high": 2, "medium": 3, "watch": 4}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def status_from_score(score_pct: float, *, hard_blocked: bool = False) -> str:
    if hard_blocked:
        return "blocked"
    if score_pct >= 90:
        return "strong"
    if score_pct >= 60:
        return "prototype"
    if score_pct > 0:
        return "partial"
    return "blocked"


def blocker_ids(
    blocker_rows: list[dict[str, Any]],
    *,
    severities: set[str] | None = None,
    contains: list[str] | None = None,
) -> list[str]:
    selected: list[str] = []
    contains = contains or []
    for row in blocker_rows:
        text = " ".join(
            str(row.get(key, "")) for key in ("blocker", "evidence", "next_action")
        ).lower()
        if severities and row.get("severity") not in severities:
            continue
        if contains and not any(term.lower() in text for term in contains):
            continue
        selected.append(str(row["blocker_id"]))
    return selected


def present_blocker_ids(blocker_rows: list[dict[str, Any]], ids: list[str]) -> str:
    present = {str(row["blocker_id"]) for row in blocker_rows}
    return "; ".join(blocker_id for blocker_id in ids if blocker_id in present)


def build_phase_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    blockers = data["synthesis"]["blocker_rows"]
    authority = data["authority"]["summary"]
    review = data["review_workbook"]["summary"]
    bibliography = data["bibliography"]["summary"]
    source_acquisition = data["source_acquisition"]["summary"]
    morph = data["morphology_unlock"]["summary"]
    bakeoff = data["local_bakeoff"]["summary"]
    contextual_model = data["contextual_real_model"]["summary"]
    heatmap = data["unit_heatmap"]["summary"]

    rows = [
        {
            "phase_id": "PATH-01",
            "phase": "Freeze authority boundary and assign reviewers",
            "dependency_ids": "",
            "status": "blocked",
            "readiness_pct": 0.0,
            "work_unit_count": review["total_review_row_count"],
            "critical_unit_count": review["critical_unit_count"],
            "blocking_gate_count": review["blocked_gate_count"],
            "blocker_ids": present_blocker_ids(blockers, ["BLK-01", "BLK-02"]),
            "evidence": (
                f"{review['completed_review_row_count']} of "
                f"{review['total_review_row_count']} review rows are completed; "
                f"{review['blocked_gate_count']} review gates are blocked."
            ),
            "exit_criterion": (
                "Reviewer IDs, roles, decisions, scores, confidence, and notes exist for "
                "source-packet and source-acquisition rows."
            ),
            "next_action": (
                "Assign Hebrew, lexical, alignment, theology, lyric, and release reviewers."
            ),
        },
        {
            "phase_id": "PATH-02",
            "phase": "Approve source licenses, provenance, and source families",
            "dependency_ids": "PATH-01",
            "status": "blocked",
            "readiness_pct": bibliography["source_verification_source_approval_count"],
            "work_unit_count": review["source_acquisition_review_row_count"],
            "critical_unit_count": source_acquisition["critical_candidate_count"],
            "blocking_gate_count": source_acquisition["blocked_gate_count"],
            "blocker_ids": present_blocker_ids(blockers, ["BLK-06", "BLK-07", "BLK-11"]),
            "evidence": (
                f"{source_acquisition['candidate_count']} source candidates; "
                f"{source_acquisition['blocked_gate_count']} acquisition gates blocked; "
                f"{bibliography['source_verification_source_approval_count']} source "
                "approval rows recorded."
            ),
            "exit_criterion": (
                "License/provenance decisions and allowed-use boundaries are signed for "
                "source families needed by high-priority units."
            ),
            "next_action": "Start with low-risk machine-readable candidates and record approvals.",
        },
        {
            "phase_id": "PATH-03",
            "phase": "Import whole-Tanakh morphology under approval controls",
            "dependency_ids": "PATH-02",
            "status": "blocked",
            "readiness_pct": morph["mean_current_whole_tanakh_score_pct"],
            "work_unit_count": morph["exception_review_row_count"],
            "critical_unit_count": morph["critical_exception_book_count"],
            "blocking_gate_count": 5,
            "blocker_ids": present_blocker_ids(blockers, ["BLK-03", "BLK-23", "BLK-16", "BLK-22"]),
            "evidence": (
                f"{morph['current_local_non_psalm_morphology_book_count']} of "
                f"{morph['target_non_psalm_book_count']} non-Psalm morphology books "
                "are local; pilot maps "
                f"{morph['pilot_mapped_non_psalm_book_count']} non-Psalm books with "
                f"{morph['exception_review_row_count']} exception rows."
            ),
            "exit_criterion": (
                "Version-pinned derived importer, exception review, Psalm regression, "
                "and release boundary review pass."
            ),
            "next_action": (
                "Approve OSHB terms, implement derived import fixture, and review residuals."
            ),
        },
        {
            "phase_id": "PATH-04",
            "phase": "Complete contextual source-packet review",
            "dependency_ids": "PATH-02; PATH-03",
            "status": "blocked",
            "readiness_pct": review["review_completion_pct"],
            "work_unit_count": review["packet_review_row_count"],
            "critical_unit_count": review["critical_unit_count"],
            "blocking_gate_count": review["blocked_gate_count"],
            "blocker_ids": present_blocker_ids(
                blockers,
                [
                    "BLK-01",
                    "BLK-07",
                    "BLK-14",
                    "BLK-15",
                    "BLK-17",
                    "BLK-20",
                    "BLK-21",
                    "BLK-22",
                    "BLK-24",
                ],
            ),
            "evidence": (
                f"{review['packet_review_row_count']} packet review rows pending across "
                f"{review['reviewer_role_count']} roles; "
                f"{review['jewish_christian_unit_count']} Jewish/Christian split units; "
                f"{review['ancient_culture_unit_count']} ancient-culture units."
            ),
            "exit_criterion": (
                "Separated Hebrew, culture, witness, Jewish, Christian, academic, poetic, "
                "theology, and release decisions exist where required."
            ),
            "next_action": (
                "Work top queue units first, preserving Jewish/Christian lane separation."
            ),
        },
        {
            "phase_id": "PATH-05",
            "phase": "Repair local model gates and run scaled bakeoff",
            "dependency_ids": "PATH-01; PATH-02",
            "status": "blocked",
            "readiness_pct": bakeoff["contextual_valid_model_task_coverage_pct"],
            "work_unit_count": contextual_model["missing_model_task_count_after_smoke"],
            "critical_unit_count": authority["model_evidence_gap_high_risk_without_valid"],
            "blocking_gate_count": bakeoff["blocked_gate_count"],
            "blocker_ids": present_blocker_ids(
                blockers, ["BLK-04", "BLK-05", "BLK-09", "BLK-10", "BLK-19", "BLK-25"]
            ),
            "evidence": (
                f"{contextual_model['attempt_count']} contextual attempts; "
                f"{contextual_model['clean_source_anchored_count']} clean source-anchored; "
                f"{contextual_model['missing_model_task_count_after_smoke']} planned rows "
                "still missing; best current baseline "
                f"{bakeoff['best_current_bakeoff_baseline']}."
            ),
            "exit_criterion": (
                "Source-anchor integrity, layer differentiation, schema admission, expanded "
                "runs, cross-exam rows, and result audits pass."
            ),
            "next_action": (
                "Fix Gemma anchors/layers, keep Mistral baseline, add DictaLM specialist."
            ),
        },
        {
            "phase_id": "PATH-06",
            "phase": "Adjudicate high-risk units and release authority",
            "dependency_ids": "PATH-01; PATH-02; PATH-03; PATH-04; PATH-05",
            "status": "blocked",
            "readiness_pct": 0.0,
            "work_unit_count": review["model_projected_human_review_rows"],
            "critical_unit_count": heatmap["critical_queue_unit_count"],
            "blocking_gate_count": authority["hard_blocker_count"],
            "blocker_ids": "; ".join(blocker_ids(blockers, severities={"critical", "hard"})),
            "evidence": (
                f"{heatmap['blocked_unit_count']} of {heatmap['unit_count']} authority "
                "heatmap units are blocked; projected model human review rows "
                f"{review['model_projected_human_review_rows']}; hard blockers "
                f"{', '.join(authority['hard_blockers'])}."
            ),
            "exit_criterion": (
                "Qualified reviewer signoff, audit records, release signoff, and canonical "
                "promotion policy pass."
            ),
            "next_action": "Do not promote outputs to canonical until all upstream gates pass.",
        },
    ]
    for row in rows:
        row["status"] = status_from_score(
            float(row["readiness_pct"]),
            hard_blocked=row["blocking_gate_count"] > 0 or row["readiness_pct"] == 0,
        )
    return rows


def build_role_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in data["review_workbook"].get("review_role_rows", []):
        total = int(row["total_review_row_count"])
        critical = int(row["critical_packet_review_row_count"])
        highest = int(row["highest_packet_review_row_count"])
        rows.append(
            {
                "reviewer_role": row["reviewer_role"],
                "total_review_row_count": total,
                "packet_review_row_count": row["packet_review_row_count"],
                "source_acquisition_review_row_count": row["source_acquisition_review_row_count"],
                "critical_packet_review_row_count": critical,
                "highest_packet_review_row_count": highest,
                "critical_or_highest_pct": pct(critical + highest, total),
                "unit_count": row["unit_count"],
                "packet_family_count": row["packet_family_count"],
                "status": row["status"],
            }
        )
    rows.sort(key=lambda item: (-item["total_review_row_count"], item["reviewer_role"]))
    return rows


def build_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    unit_packets = {row["unit_id"]: row for row in data["review_workbook"].get("unit_rows", [])}
    rows: list[dict[str, Any]] = []
    for row in data["unit_heatmap"].get("queue_rows", [])[:30]:
        packet = unit_packets.get(row["unit_id"], {})
        rows.append(
            {
                "rank": row["rank"],
                "unit_id": row["unit_id"],
                "ref": row["ref"],
                "unit_authority_score_pct": row["unit_authority_score_pct"],
                "gap_priority_score": row["gap_priority_score"],
                "claim_risk_band": row["claim_risk_band"],
                "blocking_lane_count": row["blocking_lane_count"],
                "packet_review_row_count": row["packet_review_row_count"],
                "required_review_role_count": row["required_review_role_count"],
                "packet_family_count": row["packet_family_count"],
                "weakest_required_lanes": "; ".join(row["weakest_required_lanes"]),
                "reviewer_roles": "; ".join(packet.get("distinct_reviewer_roles", [])),
                "packet_families": "; ".join(packet.get("packet_families", [])[:8]),
                "next_action": row["next_action"],
            }
        )
    return rows


def build_gate_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sources = [
        ("authority", "Authority readiness", data["authority"].get("gate_rows", [])),
        ("review", "Review workbook", data["review_workbook"].get("gate_rows", [])),
        ("source", "Source acquisition", data["source_acquisition"].get("gate_rows", [])),
        ("model", "Local model bakeoff", data["local_bakeoff"].get("gate_rows", [])),
        ("morphology", "Morphology unlock", data["morphology_unlock"].get("phase_rows", [])),
    ]
    for source_id, source_label, gate_rows in sources:
        for row in gate_rows:
            gate = row.get("gate") or row.get("phase_id")
            label = row.get("label") or row.get("gate") or row.get("phase")
            score = float(row.get("score_pct") or 0.0)
            status = row.get("status", "")
            evidence = row.get("evidence", "")
            next_action = row.get("next_action") or row.get("exit_criterion", "")
            rows.append(
                {
                    "source": source_label,
                    "source_id": source_id,
                    "gate": gate,
                    "label": label,
                    "status": status,
                    "score_pct": score,
                    "blocked": status in {"blocked", "not started"},
                    "evidence": evidence,
                    "next_action": next_action,
                }
            )
    rows.sort(
        key=lambda item: (
            0 if item["blocked"] else 1,
            item["score_pct"],
            item["source"],
            str(item["gate"]),
        )
    )
    return rows


def build_blocker_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in data["synthesis"].get("blocker_rows", []):
        severity = str(row["severity"])
        rows.append(
            {
                "blocker_id": row["blocker_id"],
                "severity": severity,
                "severity_order": SEVERITY_ORDER.get(severity, 99),
                "blocker": row["blocker"],
                "affected_requirement_ids": "; ".join(row["affected_requirement_ids"]),
                "evidence": row["evidence"],
                "next_action": row["next_action"],
            }
        )
    rows.sort(key=lambda item: (item["severity_order"], item["blocker_id"]))
    return rows


def build_summary(
    data: dict[str, dict[str, Any]],
    phase_rows: list[dict[str, Any]],
    role_rows: list[dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    blocker_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    review = data["review_workbook"]["summary"]
    authority = data["authority"]["summary"]
    heatmap = data["unit_heatmap"]["summary"]
    source_acquisition = data["source_acquisition"]["summary"]
    morph = data["morphology_unlock"]["summary"]
    bakeoff = data["local_bakeoff"]["summary"]
    severity_counts = Counter(row["severity"] for row in blocker_rows)
    blocked_gates = [row for row in gate_rows if row["blocked"]]
    top_role = role_rows[0] if role_rows else {}
    return {
        "authority_critical_path_status": "blocked_not_authority",
        "phase_count": len(phase_rows),
        "blocked_phase_count": sum(1 for row in phase_rows if row["status"] == "blocked"),
        "gate_row_count": len(gate_rows),
        "blocked_gate_row_count": len(blocked_gates),
        "blocker_count": len(blocker_rows),
        "critical_blocker_count": severity_counts.get("critical", 0),
        "hard_blocker_count": severity_counts.get("hard", 0),
        "review_row_count": review["total_review_row_count"],
        "completed_review_row_count": review["completed_review_row_count"],
        "review_completion_pct": review["review_completion_pct"],
        "packet_review_row_count": review["packet_review_row_count"],
        "source_acquisition_review_row_count": review["source_acquisition_review_row_count"],
        "projected_model_human_review_rows": review["model_projected_human_review_rows"],
        "projected_cross_exam_rows": review["model_projected_cross_exam_rows"],
        "reviewer_role_count": len(role_rows),
        "top_reviewer_role": top_role.get("reviewer_role", ""),
        "top_reviewer_role_row_count": top_role.get("total_review_row_count", 0),
        "blocked_unit_count": heatmap["blocked_unit_count"],
        "heatmap_unit_count": heatmap["unit_count"],
        "blocked_unit_pct": heatmap["blocked_unit_pct"],
        "top_gap_ref": heatmap["top_gap_ref"],
        "top_gap_score_pct": heatmap["top_gap_score_pct"],
        "source_candidate_count": source_acquisition["candidate_count"],
        "source_blocked_gate_count": source_acquisition["blocked_gate_count"],
        "source_approval_count": data["bibliography"]["summary"][
            "source_verification_source_approval_count"
        ],
        "morph_unlockable_priority_unit_count": morph["unlockable_priority_unit_count"],
        "morph_exception_review_row_count": morph["exception_review_row_count"],
        "model_contextual_coverage_pct": bakeoff["contextual_valid_model_task_coverage_pct"],
        "best_current_model_baseline": bakeoff["best_current_bakeoff_baseline"],
        "authority_readiness_score_pct": authority["authority_readiness_score_pct"],
        "hard_blockers": authority["hard_blockers"],
        "authority_verdict": (
            "The critical path is executable but blocked: source approval, morphology "
            "import, source-packet review, model gate repair, human signoff, and release "
            "authority remain incomplete."
        ),
    }


def build_visual_data(
    phase_rows: list[dict[str, Any]],
    role_rows: list[dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    blocker_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    severity_counts = Counter(row["severity"] for row in blocker_rows)
    gate_source_counts = Counter(row["source"] for row in gate_rows if row["blocked"])
    return {
        "phase_readiness_rows": [
            {"label": row["phase_id"], "value": row["readiness_pct"]} for row in phase_rows
        ],
        "phase_work_rows": [
            {"label": row["phase_id"], "value": row["work_unit_count"]} for row in phase_rows
        ],
        "review_role_rows": [
            {"label": row["reviewer_role"], "value": row["total_review_row_count"]}
            for row in role_rows
        ],
        "unit_gap_rows": [
            {"label": row["ref"], "value": row["gap_priority_score"]} for row in unit_rows[:15]
        ],
        "blocked_gate_source_rows": [
            {"label": label, "value": count}
            for label, count in sorted(gate_source_counts.items(), key=lambda item: -item[1])
        ],
        "blocker_severity_rows": [
            {"label": label, "value": severity_counts[label]}
            for label in sorted(severity_counts, key=lambda item: SEVERITY_ORDER.get(item, 99))
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    phase_rows = build_phase_rows(data)
    role_rows = build_role_rows(data)
    unit_rows = build_unit_rows(data)
    gate_rows = build_gate_rows(data)
    blocker_rows = build_blocker_rows(data)
    summary = build_summary(data, phase_rows, role_rows, unit_rows, gate_rows, blocker_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "authority critical path generated; not signoff",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": (
            "This report orders blocker clearance work only. It does not approve sources, "
            "import morphology, complete human review, approve model outputs, or authorize "
            "canonical translation wording."
        ),
        "summary": summary,
        "phase_rows": phase_rows,
        "review_role_rows": role_rows,
        "unit_queue_rows": unit_rows,
        "gate_rows": gate_rows,
        "blocker_rows": blocker_rows,
        "visual_data": build_visual_data(phase_rows, role_rows, unit_rows, gate_rows, blocker_rows),
    }


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str = "label",
    value_key: str = "value",
    width: int = 900,
    row_height: int = 28,
    color: str = "#2f6f73",
    limit: int = 14,
    max_value: float | None = None,
) -> str:
    chart_rows = rows[:limit]
    if not chart_rows:
        return ""
    values = [float(row.get(value_key) or 0.0) for row in chart_rows]
    maximum = max_value or max(values) or 1.0
    label_width = 250
    bar_width = width - label_width - 80
    height = 28 + len(chart_rows) * row_height
    parts = [
        (
            f'<svg role="img" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        )
    ]
    for index, row in enumerate(chart_rows):
        y = 22 + index * row_height
        label = str(row.get(label_key, ""))
        value = float(row.get(value_key) or 0.0)
        length = 0 if maximum <= 0 else value / maximum * bar_width
        parts.append(f'<text x="0" y="{y + 14}" font-size="12" fill="#263238">{esc(label)}</text>')
        parts.append(
            f'<rect x="{label_width}" y="{y}" width="{length:.2f}" height="18" '
            f'rx="3" fill="{color}" />'
        )
        parts.append(
            f'<text x="{label_width + length + 8:.2f}" y="{y + 14}" '
            f'font-size="12" fill="#263238">{value:.2f}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def metric_cards(cards: list[tuple[str, Any, str]]) -> str:
    return (
        '<div class="metrics">'
        + "".join(
            (
                '<div class="metric">'
                f'<div class="metric-label">{esc(label)}</div>'
                f'<div class="metric-value">{esc(value)}</div>'
                f'<div class="metric-note">{esc(note)}</div>'
                "</div>"
            )
            for label, value, note in cards
        )
        + "</div>"
    )


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    phase_rows = [
        [
            row["phase_id"],
            row["phase"],
            row["dependency_ids"],
            row["status"],
            f"{row['readiness_pct']:.2f}%",
            row["work_unit_count"],
            row["blocker_ids"],
            row["evidence"],
            row["next_action"],
        ]
        for row in report["phase_rows"]
    ]
    role_rows = [
        [
            row["reviewer_role"],
            row["total_review_row_count"],
            row["critical_packet_review_row_count"],
            row["highest_packet_review_row_count"],
            f"{row['critical_or_highest_pct']:.2f}%",
            row["unit_count"],
            row["packet_family_count"],
            row["status"],
        ]
        for row in report["review_role_rows"]
    ]
    unit_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['unit_authority_score_pct']:.2f}%",
            f"{row['gap_priority_score']:.2f}",
            row["blocking_lane_count"],
            row["packet_review_row_count"],
            row["weakest_required_lanes"],
            row["next_action"],
        ]
        for row in report["unit_queue_rows"]
    ]
    gate_rows = [
        [
            row["source"],
            row["gate"],
            row["status"],
            f"{row['score_pct']:.2f}%",
            row["evidence"],
            row["next_action"],
        ]
        for row in report["gate_rows"][:60]
    ]
    blocker_rows = [
        [
            row["blocker_id"],
            row["severity"],
            row["blocker"],
            row["affected_requirement_ids"],
            row["evidence"],
            row["next_action"],
        ]
        for row in report["blocker_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Authority Critical Path Report</title>
  <style>
    :root {{
      --ink: #263238;
      --muted: #667073;
      --line: #d7dedf;
      --panel: #f7faf9;
      --accent: #2f6f73;
      --warn: #8a6426;
      --bad: #9b3d3d;
    }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #fff;
      line-height: 1.45;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 56px;
    }}
    h1, h2 {{
      margin: 0 0 12px;
    }}
    section {{
      margin-top: 28px;
      border-top: 1px solid var(--line);
      padding-top: 22px;
    }}
    .lede {{
      max-width: 980px;
      color: var(--muted);
      font-size: 1.03rem;
    }}
    .warning {{
      border-left: 4px solid var(--bad);
      background: #fff7f5;
      padding: 12px 16px;
      margin: 16px 0;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin: 18px 0;
    }}
    .metric {{
      border: 1px solid var(--line);
      background: var(--panel);
      padding: 12px;
      border-radius: 8px;
      min-height: 92px;
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .metric-value {{
      font-size: 1.42rem;
      font-weight: 700;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }}
    .metric-note {{
      color: var(--muted);
      font-size: 0.88rem;
      margin-top: 7px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .chart {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fff;
      margin-bottom: 16px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 0.88rem;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 7px 8px;
      vertical-align: top;
      text-align: left;
    }}
    th {{
      background: #edf3f2;
    }}
    td {{
      overflow-wrap: anywhere;
    }}
  </style>
</head>
<body>
<main>
  <h1>Authority Critical Path Report</h1>
  <p class="lede">
    This report converts the current doctoral translation evidence into an
    ordered execution path for source approval, whole-Tanakh morphology, model
    bakeoff, source-packet review, human signoff, and release authority.
  </p>
  <div class="warning">
    <strong>Authority boundary:</strong> {esc(report["authority_policy"])}
  </div>
  {
        metric_cards(
            [
                (
                    "Critical path status",
                    summary["authority_critical_path_status"],
                    summary["authority_verdict"],
                ),
                (
                    "Review rows",
                    summary["review_row_count"],
                    f"{summary['completed_review_row_count']} completed.",
                ),
                (
                    "Projected model review",
                    summary["projected_model_human_review_rows"],
                    f"{summary['projected_cross_exam_rows']} cross-exam rows.",
                ),
                (
                    "Blocked units",
                    f"{summary['blocked_unit_count']}/{summary['heatmap_unit_count']}",
                    f"Top gap: {summary['top_gap_ref']}.",
                ),
                (
                    "Source approvals",
                    summary["source_approval_count"],
                    f"{summary['source_blocked_gate_count']} source gates blocked.",
                ),
                (
                    "Morph exception rows",
                    summary["morph_exception_review_row_count"],
                    f"{summary['morph_unlockable_priority_unit_count']} priority units unlockable.",
                ),
                (
                    "Model coverage",
                    f"{summary['model_contextual_coverage_pct']:.2f}%",
                    f"Baseline: {summary['best_current_model_baseline']}.",
                ),
                (
                    "Top reviewer role",
                    summary["top_reviewer_role"],
                    f"{summary['top_reviewer_role_row_count']} rows.",
                ),
            ]
        )
    }
  <section>
    <h2>Phase Critical Path</h2>
    <div class="grid">
      <div class="chart">{
        svg_horizontal_bars(
            visual["phase_readiness_rows"],
            color="#2f6f73",
            max_value=100,
        )
    }</div>
      <div class="chart">{svg_horizontal_bars(visual["phase_work_rows"], color="#8a6426")}</div>
    </div>
    {
        table(
            [
                "Phase",
                "Name",
                "Depends On",
                "Status",
                "Readiness",
                "Work Units",
                "Blockers",
                "Evidence",
                "Next Action",
            ],
            phase_rows,
        )
    }
  </section>
  <section>
    <h2>Reviewer Load</h2>
    <div class="chart">{
        svg_horizontal_bars(visual["review_role_rows"], color="#2f6f73", limit=12)
    }</div>
    {
        table(
            [
                "Role",
                "Rows",
                "Critical",
                "Highest",
                "Critical/Highest",
                "Units",
                "Families",
                "Status",
            ],
            role_rows,
        )
    }
  </section>
  <section>
    <h2>Top Unit Queue</h2>
    <div class="chart">{
        svg_horizontal_bars(visual["unit_gap_rows"], color="#9b3d3d", limit=15)
    }</div>
    {
        table(
            [
                "Rank",
                "Ref",
                "Authority Score",
                "Gap Score",
                "Blocking Lanes",
                "Review Rows",
                "Weakest Lanes",
                "Next Action",
            ],
            unit_rows,
        )
    }
  </section>
  <section>
    <h2>Gate Register</h2>
    <div class="grid">
      <div class="chart">{
        svg_horizontal_bars(visual["blocked_gate_source_rows"], color="#8a6426")
    }</div>
      <div class="chart">{
        svg_horizontal_bars(visual["blocker_severity_rows"], color="#9b3d3d")
    }</div>
    </div>
    {table(["Source", "Gate", "Status", "Score", "Evidence", "Next Action"], gate_rows)}
  </section>
  <section>
    <h2>Blocker Register</h2>
    {
        table(
            ["ID", "Severity", "Blocker", "Requirements", "Evidence", "Next Action"],
            blocker_rows,
        )
    }
  </section>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate authority critical path report.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--phase-csv-output", type=Path, default=DEFAULT_PHASE_CSV_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--role-csv-output", type=Path, default=DEFAULT_ROLE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.phase_csv_output, report["phase_rows"])
    write_csv(args.unit_csv_output, report["unit_queue_rows"])
    write_csv(args.role_csv_output, report["review_role_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.phase_csv_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.role_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
