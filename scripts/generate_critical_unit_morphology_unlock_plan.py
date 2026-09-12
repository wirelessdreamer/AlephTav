from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"

SOURCE_PATHS = {
    "critical_unit_decision_dossier": REPORT_ROOT / "critical_unit_decision_dossier.json",
    "whole_tanakh_morphology_gap": REPORT_ROOT / "whole_tanakh_morphology_gap.json",
    "whole_tanakh_morphology_acquisition": (
        REPORT_ROOT / "whole_tanakh_morphology_acquisition_readiness.json"
    ),
    "whole_tanakh_morphology_unlock": REPORT_ROOT / "whole_tanakh_morphology_unlock_matrix.json",
    "oshb_alignment_exception_review": REPORT_ROOT / "oshb_alignment_exception_review.json",
    "oshb_exception_taxonomy": REPORT_ROOT / "oshb_exception_taxonomy.json",
    "oshb_mapping_rule_simulation": REPORT_ROOT / "oshb_mapping_rule_simulation.json",
    "contextual_review_signoff": REPORT_ROOT / "contextual_review_signoff_workbook.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "critical_unit_morphology_unlock_plan.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "critical_unit_morphology_unlock_plan_units.csv"
DEFAULT_BOOK_CSV_OUTPUT = REPORT_ROOT / "critical_unit_morphology_unlock_plan_books.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "critical_unit_morphology_unlock_plan_gates.csv"
DEFAULT_PHASE_CSV_OUTPUT = REPORT_ROOT / "critical_unit_morphology_unlock_plan_phases.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "critical_unit_morphology_unlock_plan.html"

AUTHORITY_POLICY = (
    "The critical unit morphology unlock plan is source-import and reviewer-workload "
    "routing only. It does not approve OSHB or any morphology source, import raw source "
    "data, adjudicate exceptions, certify lemma/sense claims, authorize wording, or release "
    "canonical translation text."
)

BOOK_RE = re.compile(r"^(?P<book>.+?)\s+\((?P<count>\d+)\)$")


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


def parse_book_count(value: str) -> tuple[str, int]:
    match = BOOK_RE.match(value)
    if not match:
        return value, 0
    return match.group("book"), int(match.group("count"))


def build_unit_rows(
    critical_units: list[dict[str, Any]],
    unlock_units: list[dict[str, Any]],
    gap_units: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    unlock_by_unit = {str(row["unit_id"]): row for row in unlock_units}
    gap_by_unit = {str(row["unit_id"]): row for row in gap_units}
    rows: list[dict[str, Any]] = []
    for critical in critical_units:
        unit_id = str(critical["unit_id"])
        unlock = unlock_by_unit.get(unit_id, {})
        gap = gap_by_unit.get(unit_id, {})
        top_books = [
            parse_book_count(str(item))[0] for item in as_list(unlock.get("top_outside_books"))
        ]
        rows.append(
            {
                "unit_id": unit_id,
                "ref": critical["ref"],
                "decision_pressure_score": critical["decision_pressure_score"],
                "decision_pressure_band": critical["decision_pressure_band"],
                "morphology_gap_risk_score": gap.get("morphology_gap_risk_score", 0.0),
                "task_count": gap.get("task_count", 0),
                "token_count": gap.get("token_count", 0),
                "strong_coverage_pct": gap.get("strong_coverage_pct", 0.0),
                "lemma_coverage_pct": gap.get("lemma_coverage_pct", 0.0),
                "surface_outside_context_pct": gap.get("surface_outside_context_pct", 0.0),
                "outside_strong_context_pct": gap.get("outside_strong_context_pct", 0.0),
                "anchor_token_count": unlock.get("anchor_token_count", 0),
                "high_value_anchor_count": unlock.get("high_value_anchor_count", 0),
                "has_three_division_evidence": unlock.get("has_three_division_evidence", False),
                "current_lane_score_pct": unlock.get("current_lane_score_pct", 0.0),
                "projected_review_ready_score_pct": unlock.get(
                    "projected_review_ready_score_pct_if_oshb_approved",
                    0.0,
                ),
                "projected_lane_score_delta_pct": unlock.get("projected_lane_score_delta_pct", 0.0),
                "unlock_status": unlock.get("unlock_status", "blocked_no_unlock_row"),
                "top_outside_books": top_books[:6],
                "high_risk_tags": as_list(gap.get("high_risk_tags")),
                "status": "blocked_pending_source_import_review",
                "next_action": (
                    "Do not treat whole-Tanakh anchors as morphology authority until source "
                    "approval, derived import, exception review, Psalm regression, and "
                    "reviewer signoff are complete."
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -float(row["morphology_gap_risk_score"] or 0.0),
            -float(row["decision_pressure_score"]),
            str(row["ref"]),
        ),
    )


def build_book_rows(
    unit_rows: list[dict[str, Any]],
    unlock_books: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    book_unit_counts: Counter[str] = Counter()
    for unit in unit_rows:
        for book in unit["top_outside_books"]:
            book_unit_counts[str(book)] += 1
    rows: list[dict[str, Any]] = []
    for book in unlock_books:
        name = str(book["book"])
        rows.append(
            {
                "book": name,
                "division": book.get("division", ""),
                "critical_unit_anchor_count": book_unit_counts.get(name, 0),
                "priority": book.get("priority", ""),
                "mismatch_verse_count": book.get("mismatch_verse_count", 0),
                "exact_sequence_match_pct": book.get("exact_sequence_match_pct", 0.0),
                "mean_sequence_similarity_pct": book.get("mean_sequence_similarity_pct", 0.0),
                "exception_pressure_score": book.get("exception_pressure_score", 0.0),
                "candidate_rule_routable_count": book.get("candidate_rule_routable_count", 0),
                "manual_exception_count": book.get("manual_exception_count", 0),
                "aramaic_review_count": book.get("aramaic_review_count", 0),
                "psalm_regression_count": book.get("psalm_regression_count", 0),
                "review_lanes": as_list(book.get("review_lanes")),
                "recommended_action": book.get("recommended_action", ""),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -int(row["critical_unit_anchor_count"]),
            -float(row["exception_pressure_score"] or 0.0),
            str(row["book"]),
        ),
    )


def build_phase_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "phase_id": "CMORPH-01",
            "phase": "Approve morphology source and authority boundary",
            "status": "blocked",
            "completion_pct": 0.0,
            "evidence": (
                "Source approval count is 0; no morphology source may become authority "
                "without license/provenance and release-boundary decisions."
            ),
            "next_action": "Approve or reject OSHB source use and document source boundary.",
        },
        {
            "phase_id": "CMORPH-02",
            "phase": "Build derived non-Psalm morphology import",
            "status": "blocked",
            "completion_pct": pct(
                summary["current_local_non_psalm_morphology_book_count"],
                summary["target_non_psalm_book_count"],
            ),
            "evidence": (
                f"{summary['current_local_non_psalm_morphology_book_count']} of "
                f"{summary['target_non_psalm_book_count']} non-Psalm books are locally imported."
            ),
            "next_action": (
                "Build a derived importer only after source approval and manifest pinning."
            ),
        },
        {
            "phase_id": "CMORPH-03",
            "phase": "Adjudicate OSHB alignment exceptions and mapping rules",
            "status": "blocked",
            "completion_pct": 0.0,
            "evidence": (
                f"{summary['exception_review_row_count']} exception rows, "
                f"{summary['review_batch_count']} batches, and "
                f"{summary['targeted_rule_review_count']} targeted rule-review rows remain "
                "unsigned."
            ),
            "next_action": (
                "Review high-impact exception batches and approve or reject mapping rules."
            ),
        },
        {
            "phase_id": "CMORPH-04",
            "phase": "Run Psalm regression and critical-unit review",
            "status": "blocked",
            "completion_pct": 0.0,
            "evidence": (
                f"{summary['psalm_regression_row_count']} Psalm regression rows and "
                f"{summary['critical_unit_count']} critical units require reviewer signoff."
            ),
            "next_action": "Run Psalm regression before enabling morphology-backed claims.",
        },
        {
            "phase_id": "CMORPH-05",
            "phase": "Enable whole-canon lemma/sense query layer",
            "status": "not_started",
            "completion_pct": 0.0,
            "evidence": "Whole-canon lemma/sense query layer is not started.",
            "next_action": "Build query layer after import, exception review, and regression pass.",
        },
        {
            "phase_id": "CMORPH-06",
            "phase": "Release-gate enforcement",
            "status": "blocked",
            "completion_pct": 0.0,
            "evidence": "Projected morphology unlock is not release authority.",
            "next_action": "Keep whole-Tanakh morphology as blocked until signed release review.",
        },
    ]


def build_gate_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "gate_id": "CMORPH-G01",
            "gate": "Source approval and license/provenance",
            "status": "blocked",
            "current_value": "0 source approvals",
            "target_value": "Approved source manifest and authority boundary",
            "blocking_gap": (
                "OSHB and candidate morphology sources are not approved for authority use."
            ),
            "next_action": "Complete source approval before import or training use.",
        },
        {
            "gate_id": "CMORPH-G02",
            "gate": "Non-Psalm morphology import coverage",
            "status": "blocked",
            "current_value": (
                f"{summary['current_local_non_psalm_morphology_book_count']}/"
                f"{summary['target_non_psalm_book_count']} non-Psalm books imported"
            ),
            "target_value": "All target non-Psalm books imported as derived data",
            "blocking_gap": "Local non-Psalm morphology coverage is zero.",
            "next_action": "Create reproducible derived importer after source approval.",
        },
        {
            "gate_id": "CMORPH-G03",
            "gate": "Alignment exception review",
            "status": "blocked",
            "current_value": (
                f"{summary['exception_review_row_count']} exception rows; "
                f"{summary['review_batch_count']} review batches"
            ),
            "target_value": "All critical/high exception rows adjudicated and signed",
            "blocking_gap": "Exception rows are queued but unsigned.",
            "next_action": (
                "Adjudicate exceptions by book, cause family, and Psalm-regression risk."
            ),
        },
        {
            "gate_id": "CMORPH-G04",
            "gate": "Mapping rule approval",
            "status": "blocked",
            "current_value": (
                f"{summary['high_confidence_rule_candidate_count']} high-confidence "
                "candidate rows; 0 approved rules"
            ),
            "target_value": "Approved mapping rules plus manual residual queue",
            "blocking_gap": "Candidate rules are simulated, not approved.",
            "next_action": "Approve or reject candidate rules with reviewer signoff.",
        },
        {
            "gate_id": "CMORPH-G05",
            "gate": "Critical-unit morphology unlock",
            "status": "blocked",
            "current_value": (
                f"{summary['critical_unit_count']} critical units projected review-ready; "
                "0 currently authority-ready"
            ),
            "target_value": "Critical units review-ready under signed imported morphology",
            "blocking_gap": (
                "Projected score increases depend on unsigned source/import/review gates."
            ),
            "next_action": (
                "Keep critical-unit morphology claims blocked until all upstream gates pass."
            ),
        },
        {
            "gate_id": "CMORPH-G06",
            "gate": "Release authority",
            "status": "blocked",
            "current_value": "No morphology-backed release authority",
            "target_value": (
                "Release reviewer signoff after source, import, exception, and regression gates"
            ),
            "blocking_gap": "Release signoff is absent.",
            "next_action": "Do not authorize translation wording from morphology projections.",
        },
    ]


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    critical_units = data["critical_unit_decision_dossier"]["unit_rows"]
    critical_ids = {str(row["unit_id"]) for row in critical_units}
    gap_units = [
        row
        for row in data["whole_tanakh_morphology_gap"]["benchmark_unit_rows"]
        if str(row["unit_id"]) in critical_ids
    ]
    unlock_units = [
        row
        for row in data["whole_tanakh_morphology_unlock"]["unit_rows"]
        if str(row["unit_id"]) in critical_ids
    ]
    acquisition_summary = data["whole_tanakh_morphology_acquisition"]["summary"]
    taxonomy_summary = data["oshb_exception_taxonomy"]["summary"]
    exception_summary = data["oshb_alignment_exception_review"]["summary"]
    rule_summary = data["oshb_mapping_rule_simulation"]["summary"]
    review_summary = data["contextual_review_signoff"]["summary"]

    unit_rows = build_unit_rows(critical_units, unlock_units, gap_units)
    book_rows = build_book_rows(unit_rows, data["whole_tanakh_morphology_unlock"]["book_rows"])
    projected_count = sum(
        1
        for row in unit_rows
        if row["unlock_status"] == "morphology_import_would_create_review_ready_context"
    )
    mean_current = round(
        sum(float(row["current_lane_score_pct"]) for row in unit_rows) / len(unit_rows),
        2,
    )
    mean_projected = round(
        sum(float(row["projected_review_ready_score_pct"]) for row in unit_rows) / len(unit_rows),
        2,
    )
    top_unit = unit_rows[0] if unit_rows else {}
    top_book = book_rows[0] if book_rows else {}
    summary = {
        "critical_unit_count": len(critical_units),
        "matched_morphology_gap_unit_count": len(gap_units),
        "matched_unlock_unit_count": len(unlock_units),
        "projected_review_ready_critical_unit_count": projected_count,
        "projected_review_ready_critical_unit_pct": pct(projected_count, len(critical_units)),
        "mean_current_whole_tanakh_score_pct": mean_current,
        "mean_projected_review_ready_score_pct": mean_projected,
        "mean_projected_score_delta_pct": round(mean_projected - mean_current, 2),
        "target_non_psalm_book_count": acquisition_summary["target_non_psalm_book_count"],
        "current_local_non_psalm_morphology_book_count": acquisition_summary[
            "local_non_psalm_morphology_book_count"
        ],
        "pilot_mapped_non_psalm_book_count": acquisition_summary[
            "oshb_alignment_pilot_mapped_non_psalm_book_count"
        ],
        "pilot_mean_sequence_similarity_pct": acquisition_summary[
            "oshb_alignment_pilot_mean_sequence_similarity_pct"
        ],
        "pilot_exact_sequence_match_pct": acquisition_summary[
            "oshb_alignment_pilot_exact_sequence_match_pct"
        ],
        "exception_review_row_count": exception_summary["review_row_count"],
        "critical_exception_row_count": exception_summary["critical_sample_count"],
        "high_exception_row_count": exception_summary["high_sample_count"],
        "review_batch_count": taxonomy_summary["review_batch_count"],
        "psalm_regression_row_count": taxonomy_summary["psalm_regression_row_count"],
        "aramaic_review_row_count": taxonomy_summary["aramaic_review_row_count"],
        "high_confidence_rule_candidate_count": rule_summary["rule_candidate_after_review_count"],
        "targeted_rule_review_count": rule_summary["targeted_rule_review_count"],
        "manual_residual_row_count": rule_summary["manual_residual_row_count"],
        "candidate_rule_reduction_pct": rule_summary["candidate_rule_reduction_pct"],
        "source_packet_review_row_count": review_summary["packet_review_row_count"],
        "completed_review_row_count": review_summary["completed_review_row_count"],
        "top_unit_ref": top_unit.get("ref", ""),
        "top_unit_morphology_gap_risk_score": top_unit.get("morphology_gap_risk_score", 0.0),
        "top_book": top_book.get("book", ""),
        "top_book_critical_unit_anchor_count": top_book.get("critical_unit_anchor_count", 0),
        "top_book_exception_pressure_score": top_book.get("exception_pressure_score", 0.0),
        "certification_status": "blocked_morphology_source_import_not_approved",
    }
    phase_rows = build_phase_rows(summary)
    gate_rows = build_gate_rows(summary)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "critical_unit_morphology_unlock_plan_generated_not_approved",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": AUTHORITY_POLICY,
        "summary": summary,
        "unit_rows": unit_rows,
        "book_rows": book_rows,
        "phase_rows": phase_rows,
        "gate_rows": gate_rows,
        "candidate_rows": data["whole_tanakh_morphology_acquisition"]["candidate_rows"],
        "rule_rows": data["whole_tanakh_morphology_unlock"]["rule_rows"],
        "visual_data": {
            "unit_gap_rows": [
                {"label": row["ref"], "value": row["morphology_gap_risk_score"]}
                for row in unit_rows
            ],
            "unit_delta_rows": [
                {"label": row["ref"], "value": row["projected_lane_score_delta_pct"]}
                for row in unit_rows
            ],
            "book_anchor_rows": [
                {"label": row["book"], "value": row["critical_unit_anchor_count"]}
                for row in book_rows
                if row["critical_unit_anchor_count"]
            ],
            "book_exception_rows": [
                {"label": row["book"], "value": row["exception_pressure_score"]}
                for row in book_rows[:20]
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
            f"{row['morphology_gap_risk_score']:.2f}",
            f"{row['surface_outside_context_pct']:.2f}%",
            f"{row['outside_strong_context_pct']:.2f}%",
            row["anchor_token_count"],
            row["high_value_anchor_count"],
            f"{row['current_lane_score_pct']:.2f}%",
            f"{row['projected_review_ready_score_pct']:.2f}%",
            "; ".join(row["top_outside_books"]),
            row["unlock_status"],
        ]
        for index, row in enumerate(report["unit_rows"][:35], start=1)
    ]
    book_rows = [
        [
            row["book"],
            row["division"],
            row["critical_unit_anchor_count"],
            row["priority"],
            row["mismatch_verse_count"],
            f"{row['exact_sequence_match_pct']:.2f}%",
            f"{row['exception_pressure_score']:.2f}",
            row["candidate_rule_routable_count"],
            row["manual_exception_count"],
            row["recommended_action"],
        ]
        for row in report["book_rows"][:25]
    ]
    phase_rows = [
        [
            row["phase_id"],
            row["phase"],
            row["status"],
            f"{row['completion_pct']:.2f}%",
            row["evidence"],
            row["next_action"],
        ]
        for row in report["phase_rows"]
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
    candidate_rows = [
        [
            row["candidate_id"],
            row["label"],
            row["license_risk"],
            "yes" if row["machine_readable"] else "no",
            row["acquisition_status"],
            row["recommendation"],
            row["why_this_sequence"],
        ]
        for row in report["candidate_rows"]
    ]
    rule_rows = [
        [
            row["candidate_rule_id"],
            row["candidate_rule"],
            row["row_count"],
            f"{row['row_pct']:.2f}%",
            row["psalm_regression_count"],
            row["authority_status"],
            row["next_action"],
        ]
        for row in report["rule_rows"]
    ]
    visual = report["visual_data"]
    cards = metric_cards(
        [
            (
                "Critical units",
                summary["critical_unit_count"],
                f"{summary['projected_review_ready_critical_unit_count']} projected review-ready.",
            ),
            (
                "Non-Psalm import",
                (
                    f"{summary['current_local_non_psalm_morphology_book_count']}/"
                    f"{summary['target_non_psalm_book_count']}"
                ),
                "Current local non-Psalm morphology books.",
            ),
            (
                "Pilot mapped",
                summary["pilot_mapped_non_psalm_book_count"],
                f"{summary['pilot_mean_sequence_similarity_pct']:.2f}% mean similarity.",
            ),
            (
                "Exceptions",
                summary["exception_review_row_count"],
                f"{summary['review_batch_count']} review batches.",
            ),
            (
                "Rule reduction",
                f"{summary['candidate_rule_reduction_pct']:.2f}%",
                f"{summary['manual_residual_row_count']} manual residual rows.",
            ),
            (
                "Top unit",
                summary["top_unit_ref"],
                f"Risk {summary['top_unit_morphology_gap_risk_score']:.2f}.",
            ),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Critical Unit Morphology Unlock Plan</title>
  <style>
    body {{
      font-family: Inter, Segoe UI, sans-serif;
      color: #24313a;
      margin: 0;
      background: #f6f4ef;
    }}
    header {{
      background: #23343b;
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
    <h1>Critical Unit Morphology Unlock Plan</h1>
    <p>
      Critical-unit whole-Tanakh morphology import, OSHB exception review,
      mapping-rule simulation, Psalm regression, and release-boundary workload.
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
            visual["unit_gap_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit morphology gap risk",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["unit_delta_rows"],
            label_key="label",
            value_key="value",
            aria_label="Projected critical unit whole-Tanakh score delta",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["book_anchor_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit anchor books",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["book_exception_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception pressure by book",
            color="#584b87",
        )
    }</div>
    </section>

    <section>
      <h2>Critical Units</h2>
      {
        table(
            [
                "Rank",
                "Ref",
                "Morph Risk",
                "Surface Context",
                "Strong Context",
                "Anchors",
                "High-Value Anchors",
                "Current",
                "Projected",
                "Top Books",
                "Status",
            ],
            unit_rows,
        )
    }
    </section>

    <section>
      <h2>Book Exception Pressure</h2>
      {
        table(
            [
                "Book",
                "Division",
                "Critical Unit Anchors",
                "Priority",
                "Mismatch Verses",
                "Exact Match",
                "Pressure",
                "Rule-Routable",
                "Manual",
                "Recommended Action",
            ],
            book_rows,
        )
    }
    </section>

    <section>
      <h2>Execution Phases</h2>
      {table(["Phase", "Name", "Status", "Complete", "Evidence", "Next Action"], phase_rows)}
    </section>

    <section>
      <h2>Gates</h2>
      {
        table(
            ["Gate", "Name", "Status", "Current", "Target", "Blocking Gap", "Next Action"],
            gate_rows,
        )
    }
    </section>

    <section>
      <h2>Source Candidates</h2>
      {
        table(
            ["ID", "Label", "License Risk", "Machine", "Status", "Recommendation", "Rationale"],
            candidate_rows,
        )
    }
    </section>

    <section>
      <h2>Mapping Rules</h2>
      {
        table(
            ["ID", "Rule", "Rows", "Share", "Psalm Regression", "Authority", "Next Action"],
            rule_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate critical unit whole-Tanakh morphology unlock plan."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--book-csv-output", type=Path, default=DEFAULT_BOOK_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--phase-csv-output", type=Path, default=DEFAULT_PHASE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.book_csv_output, report["book_rows"])
    write_csv(args.gate_csv_output, report["gate_rows"])
    write_csv(args.phase_csv_output, report["phase_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.book_csv_output}")
    print(f"Wrote {args.gate_csv_output}")
    print(f"Wrote {args.phase_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
