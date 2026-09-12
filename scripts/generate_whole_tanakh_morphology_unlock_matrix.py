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
    "morphology_acquisition": REPORT_ROOT / "whole_tanakh_morphology_acquisition_readiness.json",
    "oshb_alignment_pilot": REPORT_ROOT / "oshb_whole_tanakh_alignment_pilot.json",
    "oshb_exception_review": REPORT_ROOT / "oshb_alignment_exception_review.json",
    "oshb_exception_taxonomy": REPORT_ROOT / "oshb_exception_taxonomy.json",
    "oshb_mapping_rule_simulation": REPORT_ROOT / "oshb_mapping_rule_simulation.json",
    "canonical_cross_reference": REPORT_ROOT / "canonical_cross_reference_atlas.json",
    "unit_heatmap": REPORT_ROOT / "doctoral_unit_authority_heatmap.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "whole_tanakh_morphology_unlock_matrix.json"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "whole_tanakh_morphology_unlock_matrix.html"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "whole_tanakh_morphology_unlock_units.csv"
DEFAULT_BOOK_CSV_OUTPUT = REPORT_ROOT / "whole_tanakh_morphology_unlock_books.csv"


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


def weighted_mean(rows: list[dict[str, Any]], value_key: str, weight_key: str) -> float:
    total_weight = sum(float(row.get(weight_key) or 0) for row in rows)
    if not total_weight:
        return 0.0
    value = sum(float(row.get(value_key) or 0) * float(row.get(weight_key) or 0) for row in rows)
    return round(value / total_weight, 2)


def whole_tanakh_lane_rows(heatmap: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in heatmap["lane_rows"] if row.get("lane") == "whole_tanakh"]


def cross_reference_by_unit(cross_reference: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in cross_reference.get("unit_rows", [])}


def build_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    cross_refs = cross_reference_by_unit(data["canonical_cross_reference"])
    rows = []
    for lane in whole_tanakh_lane_rows(data["unit_heatmap"]):
        unit = cross_refs.get(str(lane["unit_id"]), {})
        outside_books = unit.get("outside_book_counts") if isinstance(unit, dict) else {}
        if not isinstance(outside_books, dict):
            outside_books = {}
        top_books = sorted(outside_books.items(), key=lambda item: int(item[1]), reverse=True)[:6]
        anchor_count = int(unit.get("anchor_token_count") or 0)
        high_value_anchor_count = int(unit.get("high_value_anchor_count") or 0)
        three_division = bool(unit.get("has_three_division_evidence"))
        current_score = float(lane.get("score_pct") or 0.0)
        projected_review_ready_score = 55.0 if anchor_count else current_score
        rows.append(
            {
                "unit_id": lane["unit_id"],
                "ref": lane["ref"],
                "current_lane_score_pct": current_score,
                "current_lane_status": lane["status"],
                "current_blocking_gap": lane["blocking_gap"],
                "anchor_token_count": anchor_count,
                "high_value_anchor_count": high_value_anchor_count,
                "has_torah_evidence": bool(unit.get("has_torah_evidence")),
                "has_prophets_evidence": bool(unit.get("has_prophets_evidence")),
                "has_non_psalm_writings_evidence": bool(
                    unit.get("has_non_psalm_writings_evidence")
                ),
                "has_three_division_evidence": three_division,
                "top_outside_books": [f"{book} ({count})" for book, count in top_books],
                "domain_labels": unit.get("domain_labels") or [],
                "projected_review_ready_score_pct_if_oshb_approved": projected_review_ready_score,
                "projected_lane_score_delta_pct": round(
                    projected_review_ready_score - current_score,
                    2,
                ),
                "unlock_status": (
                    "morphology_import_would_create_review_ready_context"
                    if anchor_count
                    else "no_cross_reference_anchor_to_unlock"
                ),
                "authority_boundary": (
                    "Projected review-ready score assumes source approval, derived importer, "
                    "exception review, and reviewer signoff; it is not current authority."
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -float(row["projected_lane_score_delta_pct"]),
            -int(row["anchor_token_count"]),
            str(row["ref"]),
        ),
    )


def build_book_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    cross_book_counts = {
        str(row["book"]): row for row in data["canonical_cross_reference"].get("book_rows", [])
    }
    rule_packets = data["oshb_mapping_rule_simulation"].get("packet_rows", [])
    high_confidence: Counter[str] = Counter()
    targeted: Counter[str] = Counter()
    manual: Counter[str] = Counter()
    textual: Counter[str] = Counter()
    aramaic: Counter[str] = Counter()
    psalm_regression: Counter[str] = Counter()
    for row in rule_packets:
        book = str(row["book"])
        lane = str(row.get("automation_lane") or "")
        if lane == "rule_candidate_after_review":
            high_confidence[book] += 1
        elif lane == "targeted_rule_review":
            targeted[book] += 1
        elif lane == "manual_exception_review":
            manual[book] += 1
        elif lane == "textual_witness_review":
            textual[book] += 1
        if row.get("requires_aramaic_review"):
            aramaic[book] += 1
        if row.get("requires_psalm_regression"):
            psalm_regression[book] += 1
    rows = []
    for book in data["oshb_exception_review"].get("book_rows", []):
        name = str(book["book"])
        cross = cross_book_counts.get(name, {})
        mismatch = int(book.get("mismatch_verse_count") or 0)
        candidate_routable = high_confidence[name] + targeted[name]
        rows.append(
            {
                "book": name,
                "division": book["division"],
                "priority": book["priority"],
                "mismatch_verse_count": mismatch,
                "mismatch_verse_pct": float(book.get("mismatch_verse_pct") or 0.0),
                "exact_sequence_match_pct": float(book.get("exact_sequence_match_pct") or 0.0),
                "mean_sequence_similarity_pct": float(
                    book.get("mean_sequence_similarity_pct") or 0.0
                ),
                "exception_pressure_score": float(book.get("exception_pressure_score") or 0.0),
                "candidate_rule_routable_count": candidate_routable,
                "candidate_rule_routable_pct": pct(candidate_routable, mismatch),
                "manual_exception_count": manual[name],
                "textual_witness_review_count": textual[name],
                "aramaic_review_count": aramaic[name],
                "psalm_regression_count": psalm_regression[name],
                "psalm_anchor_unit_count": int(cross.get("unit_count") or 0),
                "psalm_anchor_token_count": int(cross.get("anchor_token_count") or 0),
                "outside_occurrence_sum": int(cross.get("outside_occurrence_sum") or 0),
                "review_lanes": book.get("review_lanes") or [],
                "recommended_action": book.get("recommended_action") or "",
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row["priority"]) != "critical",
            -float(row["exception_pressure_score"]),
            -int(row["psalm_anchor_token_count"]),
        ),
    )


def build_phase_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    mapping = data["oshb_mapping_rule_simulation"]["summary"]
    exception = data["oshb_exception_review"]["summary"]
    taxonomy = data["oshb_exception_taxonomy"]["summary"]
    acquisition = data["morphology_acquisition"]["summary"]
    rows.append(
        {
            "phase_id": "PHASE-01",
            "phase": "Source approval and manifest",
            "status": "blocked",
            "evidence": (
                f"{acquisition['blocked_gate_count']} blocked acquisition gates; "
                "OSHB source approval is not recorded."
            ),
            "exit_criterion": (
                "Signed license/provenance decision and version-pinned source manifest."
            ),
        }
    )
    rows.append(
        {
            "phase_id": "PHASE-02",
            "phase": "Derived importer fixture",
            "status": "pilot_partial",
            "evidence": (
                f"{acquisition['oshb_alignment_pilot_mapped_book_count']} books mapped; "
                f"{acquisition['oshb_alignment_pilot_mean_sequence_similarity_pct']:.2f}% "
                "mean verse similarity."
            ),
            "exit_criterion": "Importer writes derived, reproducible, non-raw alignment artifacts.",
        }
    )
    rows.append(
        {
            "phase_id": "PHASE-03",
            "phase": "Exception review and rule approval",
            "status": "blocked",
            "evidence": (
                f"{exception['mismatch_verse_count']} exception verses; "
                f"{taxonomy['taxonomy_cause_count']} cause families; "
                f"{mapping['candidate_rule_reduction_pct']:.2f}% candidate rule reduction."
            ),
            "exit_criterion": (
                "Signed Hebrew/alignment/source-provenance decisions for candidate rules and "
                "manual residual rows."
            ),
        }
    )
    rows.append(
        {
            "phase_id": "PHASE-04",
            "phase": "Psalm regression and authority boundary",
            "status": "not_started",
            "evidence": (
                f"{taxonomy['psalm_regression_row_count']} Psalm regression rows and "
                f"{taxonomy['aramaic_review_row_count']} Aramaic review rows require routing."
            ),
            "exit_criterion": (
                "Regression confirms Psalm morphology remains stable and Aramaic/textual rows "
                "are fenced from Hebrew claims."
            ),
        }
    )
    return rows


def build_summary(
    data: dict[str, dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    book_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    acquisition = data["morphology_acquisition"]["summary"]
    pilot = data["oshb_alignment_pilot"]["summary"]
    exception = data["oshb_exception_review"]["summary"]
    taxonomy = data["oshb_exception_taxonomy"]["summary"]
    mapping = data["oshb_mapping_rule_simulation"]["summary"]
    heatmap = data["unit_heatmap"]["summary"]
    unlockable_units = [row for row in unit_rows if row["anchor_token_count"]]
    return {
        "status": "unlock_matrix_generated_not_source_approval",
        "target_non_psalm_book_count": acquisition["target_non_psalm_book_count"],
        "current_local_non_psalm_morphology_book_count": acquisition[
            "local_non_psalm_morphology_book_count"
        ],
        "pilot_mapped_non_psalm_book_count": pilot["mapped_non_psalm_book_count"],
        "pilot_remote_oshb_word_count": pilot["remote_oshb_word_count"],
        "pilot_mean_sequence_similarity_pct": pilot["mean_sequence_similarity_pct"],
        "pilot_exact_sequence_match_pct": pilot["exact_sequence_match_pct"],
        "exception_verse_count": exception["mismatch_verse_count"],
        "exception_review_row_count": exception.get(
            "review_row_count",
            exception["sample_row_count"],
        ),
        "exception_cause_family_count": taxonomy["taxonomy_cause_count"],
        "review_batch_count": taxonomy["review_batch_count"],
        "candidate_rule_reduction_pct": mapping["candidate_rule_reduction_pct"],
        "high_confidence_rule_candidate_count": mapping["high_confidence_rule_candidate_count"],
        "targeted_rule_review_count": mapping["targeted_rule_review_count"],
        "manual_residual_row_count": mapping["manual_residual_row_count"],
        "textual_witness_review_count": mapping["textual_witness_review_count"],
        "psalm_regression_row_count": taxonomy["psalm_regression_row_count"],
        "aramaic_review_row_count": taxonomy["aramaic_review_row_count"],
        "heatmap_unit_count": heatmap["unit_count"],
        "blocked_whole_tanakh_lane_count": len(
            [row for row in unit_rows if row["current_lane_status"] == "blocked"]
        ),
        "unlockable_priority_unit_count": len(unlockable_units),
        "unlockable_priority_unit_pct": pct(len(unlockable_units), len(unit_rows)),
        "mean_current_whole_tanakh_score_pct": round(
            sum(float(row["current_lane_score_pct"]) for row in unit_rows) / len(unit_rows),
            2,
        )
        if unit_rows
        else 0.0,
        "projected_review_ready_whole_tanakh_score_pct": weighted_mean(
            unit_rows,
            "projected_review_ready_score_pct_if_oshb_approved",
            "anchor_token_count",
        ),
        "top_unlock_unit_ref": unit_rows[0]["ref"] if unit_rows else "",
        "top_exception_book": book_rows[0]["book"] if book_rows else "",
        "critical_exception_book_count": len(
            [row for row in book_rows if row["priority"] == "critical"]
        ),
        "authority_verdict": (
            "OSHB whole-Tanakh morphology has strong pilot feasibility and a large "
            "rule-routable exception share, but it remains unavailable for authority "
            "claims until source approval, derived import, exception review, Psalm "
            "regression, and reviewer signoff are complete."
        ),
    }


def build_visual_data(
    unit_rows: list[dict[str, Any]],
    book_rows: list[dict[str, Any]],
    cause_rows: list[dict[str, Any]],
    rule_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "top_unit_unlock_rows": [
            {
                "label": row["ref"],
                "value": row["projected_lane_score_delta_pct"],
            }
            for row in unit_rows[:20]
        ],
        "top_book_exception_rows": [
            {
                "label": row["book"],
                "value": row["exception_pressure_score"],
            }
            for row in book_rows[:20]
        ],
        "book_anchor_token_rows": [
            {
                "label": row["book"],
                "value": row["psalm_anchor_token_count"],
            }
            for row in sorted(
                book_rows,
                key=lambda item: int(item["psalm_anchor_token_count"]),
                reverse=True,
            )[:20]
        ],
        "cause_rows": [
            {
                "label": row["cause_family"],
                "value": row["row_count"],
            }
            for row in cause_rows
        ],
        "rule_lane_rows": [
            {
                "label": f"{row['candidate_rule_id']} {row['automation_lane']}",
                "value": row["row_count"],
            }
            for row in rule_rows
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    unit_rows = build_unit_rows(data)
    book_rows = build_book_rows(data)
    phase_rows = build_phase_rows(data)
    cause_rows = data["oshb_exception_taxonomy"]["cause_rows"]
    rule_rows = data["oshb_mapping_rule_simulation"]["rule_rows"]
    summary = build_summary(data, unit_rows, book_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "whole-Tanakh morphology unlock matrix generated; not source approval",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": (
            "This report estimates review and importer impact only. It does not approve OSHB, "
            "write data/raw, import morphology, authorize generation data, or change canonical "
            "translation authority."
        ),
        "summary": summary,
        "phase_rows": phase_rows,
        "unit_rows": unit_rows,
        "book_rows": book_rows,
        "cause_rows": cause_rows,
        "rule_rows": rule_rows,
        "visual_data": build_visual_data(unit_rows, book_rows, cause_rows, rule_rows),
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
    visual = report["visual_data"]
    non_psalm_morph_value = (
        f"{summary['current_local_non_psalm_morphology_book_count']}/"
        f"{summary['target_non_psalm_book_count']}"
    )
    pilot_note = (
        f"{fmt_int(summary['pilot_remote_oshb_word_count'])} remote OSHB words; "
        f"{summary['pilot_mean_sequence_similarity_pct']:.2f}% mean similarity."
    )
    exception_note = f"{summary['exception_cause_family_count']} cause families in queued review."
    rule_reduction_value = f"{summary['candidate_rule_reduction_pct']:.2f}%"
    rule_reduction_note = (
        f"{fmt_int(summary['high_confidence_rule_candidate_count'])} "
        "high-confidence candidate rows."
    )
    manual_note = f"{fmt_int(summary['textual_witness_review_count'])} textual-witness rows."
    unlockable_note = (
        f"{summary['unlockable_priority_unit_pct']:.2f}% have cross-reference anchors."
    )
    top_exception_note = (
        f"{fmt_int(summary['critical_exception_book_count'])} critical exception books."
    )
    phase_rows = [
        [row["phase_id"], row["phase"], row["status"], row["evidence"], row["exit_criterion"]]
        for row in report["phase_rows"]
    ]
    unit_rows = [
        [
            row["ref"],
            row["current_lane_status"],
            f"{row['current_lane_score_pct']:.2f}%",
            row["anchor_token_count"],
            row["high_value_anchor_count"],
            "yes" if row["has_three_division_evidence"] else "no",
            f"{row['projected_review_ready_score_pct_if_oshb_approved']:.2f}%",
            f"{row['projected_lane_score_delta_pct']:.2f}%",
            "; ".join(row["top_outside_books"]),
            row["unlock_status"],
        ]
        for row in report["unit_rows"][:30]
    ]
    book_rows = [
        [
            row["book"],
            row["division"],
            row["priority"],
            row["mismatch_verse_count"],
            f"{row['mismatch_verse_pct']:.2f}%",
            f"{row['exact_sequence_match_pct']:.2f}%",
            row["candidate_rule_routable_count"],
            f"{row['candidate_rule_routable_pct']:.2f}%",
            row["manual_exception_count"],
            row["psalm_anchor_token_count"],
            row["recommended_action"],
        ]
        for row in report["book_rows"][:30]
    ]
    cause_rows = [
        [
            row["cause_family"],
            row["row_count"],
            f"{row['row_pct']:.2f}%",
            row["critical_count"],
            row["high_count"],
            row["psalm_regression_count"],
            row["aramaic_review_count"],
            row["review_intensity"],
        ]
        for row in report["cause_rows"]
    ]
    rule_rows = [
        [
            row["candidate_rule_id"],
            row["candidate_rule"],
            row["automation_lane"],
            row["row_count"],
            f"{row['row_pct']:.2f}%",
            row["high_confidence_count"],
            row["medium_confidence_count"],
            row["critical_count"],
            row["authority_status"],
            row["next_action"],
        ]
        for row in report["rule_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Whole-Tanakh Morphology Unlock Matrix</title>
  <style>
    :root {{
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
    <h1>Whole-Tanakh Morphology Unlock Matrix</h1>
    <p class="lede">
      Impact matrix for the OSHB whole-Tanakh morphology gate. It quantifies
      what the existing alignment pilot, exception taxonomy, mapping-rule
      simulation, and unit authority heatmap imply for broader Old Testament
      lexical context in Psalms translation.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Gate State</h2>
      {
        metric_cards(
            [
                (
                    "Non-Psalm morph books",
                    non_psalm_morph_value,
                    "Current local authority coverage before import.",
                ),
                (
                    "Pilot mapped",
                    fmt_int(summary["pilot_mapped_non_psalm_book_count"]),
                    pilot_note,
                ),
                (
                    "Exception rows",
                    fmt_int(summary["exception_review_row_count"]),
                    exception_note,
                ),
                (
                    "Rule reduction",
                    rule_reduction_value,
                    rule_reduction_note,
                ),
                (
                    "Manual residual",
                    fmt_int(summary["manual_residual_row_count"]),
                    manual_note,
                ),
                (
                    "Blocked units",
                    fmt_int(summary["blocked_whole_tanakh_lane_count"]),
                    "Priority units whose whole-Tanakh lane remains blocked.",
                ),
                (
                    "Unlockable units",
                    fmt_int(summary["unlockable_priority_unit_count"]),
                    unlockable_note,
                ),
                (
                    "Top exception book",
                    summary["top_exception_book"],
                    top_exception_note,
                ),
            ]
        )
    }
      <div class="warning">{esc(summary["authority_verdict"])}</div>
    </section>

    <section>
      <h2>Import Phases</h2>
      {table(["ID", "Phase", "Status", "Evidence", "Exit Criterion"], phase_rows)}
    </section>

    <section>
      <h2>Priority Unit Impact</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["top_unit_unlock_rows"],
            label_key="label",
            value_key="value",
            aria_label="Projected whole-Tanakh morphology lane score delta by priority unit",
            color="#2f6f73",
        )
    }</div>
      {
        table(
            [
                "Ref",
                "Current Status",
                "Current Score",
                "Anchors",
                "High Anchors",
                "Three Divisions",
                "Projected Review-Ready",
                "Delta",
                "Top Outside Books",
                "Unlock Status",
            ],
            unit_rows,
        )
    }
    </section>

    <section>
      <h2>Book Exception Pressure</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["top_book_exception_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception pressure by book",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["book_anchor_token_rows"],
            label_key="label",
            value_key="value",
            aria_label="Psalm cross-reference anchor tokens by non-Psalm book",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Book",
                "Division",
                "Priority",
                "Mismatch Verses",
                "Mismatch %",
                "Exact Match %",
                "Rule-Routable",
                "Rule-Routable %",
                "Manual",
                "Psalm Anchor Tokens",
                "Recommended Action",
            ],
            book_rows,
        )
    }
    </section>

    <section>
      <h2>Exception Taxonomy and Rule Simulation</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["cause_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception rows by cause family",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["rule_lane_rows"],
            label_key="label",
            value_key="value",
            aria_label="Candidate mapping-rule rows by automation lane",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Cause",
                "Rows",
                "Row %",
                "Critical",
                "High",
                "Psalm Regression",
                "Aramaic Review",
                "Review Intensity",
            ],
            cause_rows,
        )
    }
      {
        table(
            [
                "Rule",
                "Candidate Rule",
                "Lane",
                "Rows",
                "Row %",
                "High Confidence",
                "Medium Confidence",
                "Critical",
                "Authority Status",
                "Next Action",
            ],
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
        description="Generate whole-Tanakh morphology unlock impact matrix."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--book-csv-output", type=Path, default=DEFAULT_BOOK_CSV_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.book_csv_output, report["book_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.book_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
