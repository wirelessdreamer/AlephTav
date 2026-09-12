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
    "reception_divergence": REPORT_ROOT / "reception_divergence_atlas.json",
    "reception_boundary": REPORT_ROOT / "reception_interpretation_boundary.json",
    "reception_source_packets": REPORT_ROOT / "reception_source_packet_workbook.json",
    "interpretive_adjudication": REPORT_ROOT / "interpretive_adjudication_matrix.json",
    "cultural_atlas": REPORT_ROOT / "cultural_historical_domain_atlas.json",
    "corpus_reception_signal": REPORT_ROOT / "corpus_reception_signal_atlas.json",
    "canonical_cross_reference": REPORT_ROOT / "canonical_cross_reference_atlas.json",
    "witness_divergence": REPORT_ROOT / "witness_divergence_report.json",
    "unit_heatmap": REPORT_ROOT / "doctoral_unit_authority_heatmap.json",
    "review_workbook": REPORT_ROOT / "contextual_review_signoff_workbook.json",
    "authority_critical_path": REPORT_ROOT / "authority_critical_path_report.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "interpretive_tradition_control_matrix.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "interpretive_tradition_control_units.csv"
DEFAULT_PACKET_CSV_OUTPUT = REPORT_ROOT / "interpretive_tradition_control_packets.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "interpretive_tradition_control_matrix.html"


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


def by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key)}


def list_join(values: list[Any], limit: int | None = None) -> str:
    if limit is not None:
        values = values[:limit]
    return "; ".join(str(value) for value in values)


def build_packet_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for packet in data["reception_source_packets"].get("packet_rows", []):
        context_inputs = packet.get("context_inputs", {})
        rows.append(
            {
                "packet_id": packet["packet_id"],
                "unit_id": packet["unit_id"],
                "ref": packet["ref"],
                "lane_id": packet["lane_id"],
                "lane_label": packet["lane_label"],
                "priority_score": packet["priority_score"],
                "candidate_count": packet["candidate_count"],
                "reachable_candidate_count": packet["reachable_candidate_count"],
                "best_license_risk": packet["best_license_risk"],
                "review_roles": list_join(packet.get("review_roles", [])),
                "required_note_fields": list_join(packet.get("required_note_fields", [])),
                "review_questions": list_join(packet.get("review_questions", [])),
                "hebrew_controls": list_join(packet.get("hebrew_controls", [])),
                "required_frames": list_join(context_inputs.get("required_frames", []), 8),
                "signal_ids": list_join(context_inputs.get("signal_ids", []), 6),
                "top_anchor_form_labels": list_join(
                    context_inputs.get("top_anchor_form_labels", []), 5
                ),
                "witness_divergence_pct": context_inputs.get("witness_divergence_pct", 0.0),
                "status": packet["status"],
                "authority_boundary": packet["authority_boundary"],
            }
        )
    rows.sort(key=lambda row: (-float(row["priority_score"]), row["lane_id"]))
    return rows


def build_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    adjudication_by_unit = by_key(data["interpretive_adjudication"].get("unit_rows", []), "unit_id")
    heatmap_by_unit = by_key(data["unit_heatmap"].get("unit_rows", []), "unit_id")
    review_by_unit = by_key(data["review_workbook"].get("unit_rows", []), "unit_id")
    packet_by_unit = by_key(data["reception_source_packets"].get("unit_rows", []), "unit_id")
    canonical_by_unit = by_key(data["canonical_cross_reference"].get("unit_rows", []), "unit_id")
    signal_by_unit = by_key(data["corpus_reception_signal"].get("unit_rows", []), "unit_id")
    witness_by_unit = by_key(data["witness_divergence"].get("unit_rows", []), "unit_id")

    rows: list[dict[str, Any]] = []
    for reception in data["reception_divergence"].get("unit_rows", []):
        unit_id = str(reception["unit_id"])
        adjudication = adjudication_by_unit.get(unit_id, {})
        heatmap = heatmap_by_unit.get(unit_id, {})
        review = review_by_unit.get(unit_id, {})
        packet = packet_by_unit.get(unit_id, {})
        canonical = canonical_by_unit.get(unit_id, {})
        signal = signal_by_unit.get(unit_id, {})
        witness = witness_by_unit.get(unit_id, {})
        required_frames = reception.get("required_frames", [])
        claim_controls = reception.get("claim_controls", [])
        lane_statuses = reception.get("lane_statuses", {})
        translation_forbidden = (
            "reception_claims_must_stay_out_of_translation_text" in claim_controls
            or reception.get("reception_sensitive")
        )
        row = {
            "rank": 0,
            "unit_id": unit_id,
            "ref": reception["ref"],
            "source_hebrew": reception.get("source_hebrew", ""),
            "interpretive_control_score": round(
                float(reception.get("reception_divergence_priority_score") or 0.0)
                + float(reception.get("boundary_risk_score") or 0.0)
                + float(reception.get("claim_risk_score") or 0.0) * 0.35
                + float(heatmap.get("gap_priority_score") or 0.0) * 0.25
                + (35 if reception.get("jewish_christian_separation_required") else 0)
                + (20 if reception.get("ancient_culture_pressure") else 0)
                + (20 if reception.get("textual_witness_pressure") else 0)
                + (15 if adjudication.get("layer_exact_duplicate") else 0),
                2,
            ),
            "reception_divergence_priority_score": reception.get(
                "reception_divergence_priority_score", 0.0
            ),
            "boundary_risk_score": reception.get("boundary_risk_score", 0.0),
            "claim_risk_score": reception.get("claim_risk_score", 0.0),
            "packet_priority_score": reception.get("packet_priority_score", 0.0),
            "unit_authority_score_pct": heatmap.get(
                "unit_authority_score_pct", packet.get("unit_authority_score_pct", "")
            ),
            "jewish_christian_separation_required": bool(
                reception.get("jewish_christian_separation_required")
            ),
            "has_jewish_reception_frame": bool(reception.get("has_jewish_reception_frame")),
            "has_christian_reception_frame": bool(reception.get("has_christian_reception_frame")),
            "has_academic_comparison_frame": bool(reception.get("has_academic_comparison_frame")),
            "reception_sensitive": bool(reception.get("reception_sensitive")),
            "ancient_culture_pressure": bool(reception.get("ancient_culture_pressure")),
            "textual_witness_pressure": bool(reception.get("textual_witness_pressure")),
            "theology_pressure": bool(reception.get("theology_pressure")),
            "translation_text_forbidden_reception_claim": translation_forbidden,
            "required_frames": list_join(required_frames),
            "domains": list_join(reception.get("domains", []), 10),
            "case_family_labels": list_join(reception.get("case_family_labels", []), 8),
            "claim_controls": list_join(claim_controls, 12),
            "required_review_roles": list_join(reception.get("required_review_roles", [])),
            "reviewer_roles": list_join(review.get("distinct_reviewer_roles", [])),
            "packet_families": list_join(
                review.get("packet_families", reception.get("packet_families", [])), 10
            ),
            "source_packet_count": packet.get("packet_count", 0),
            "packet_review_row_count": review.get("packet_review_row_count", 0),
            "blocked_lane_count": reception.get(
                "blocked_lane_count", adjudication.get("blocked_lane_count", 0)
            ),
            "review_lane_count": reception.get(
                "review_lane_count", adjudication.get("review_lane_count", 0)
            ),
            "lane_status_summary": "; ".join(
                f"{lane}:{status}" for lane, status in lane_statuses.items()
            ),
            "mean_english_witness_divergence_pct": reception.get(
                "mean_english_witness_divergence_pct",
                witness.get("mean_english_witness_divergence_pct", 0.0),
            ),
            "witness_marker_flags": list_join(witness.get("marker_flags", []), 6),
            "cross_reference_anchor_token_count": reception.get(
                "cross_reference_anchor_token_count",
                canonical.get("anchor_token_count", 0),
            ),
            "cross_reference_three_division": bool(
                reception.get("cross_reference_three_division")
                or canonical.get("has_three_division_evidence")
            ),
            "top_anchor_form_labels": list_join(reception.get("top_anchor_form_labels", []), 6),
            "signal_labels": list_join(signal.get("signal_labels", []), 8),
            "model_candidate_count": adjudication.get("model_candidate_count", 0),
            "schema_valid_model_candidate_count": adjudication.get(
                "schema_valid_model_candidate_count", 0
            ),
            "layer_risk_score": adjudication.get("layer_risk_score", 0.0),
            "layer_exact_duplicate": bool(adjudication.get("layer_exact_duplicate")),
            "authority_boundary": reception.get(
                "authority_boundary",
                "Reception evidence routes review only; Hebrew source controls translation text.",
            ),
            "next_action": heatmap.get(
                "next_action",
                "Keep reception claims in labeled review lanes until signed.",
            ),
        }
        rows.append(row)
    rows.sort(key=lambda row: row["interpretive_control_score"], reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_lane_rows(
    data: dict[str, dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    packet_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    packet_counts = Counter(row["lane_id"] for row in packet_rows)
    packet_reachable = defaultdict(int)
    packet_candidate = defaultdict(int)
    for row in packet_rows:
        packet_reachable[row["lane_id"]] += int(row["reachable_candidate_count"])
        packet_candidate[row["lane_id"]] += int(row["candidate_count"])
    lane_specs = [
        ("jewish_reception", "Jewish Reception", "jewish_christian_separation_required"),
        ("christian_reception", "Christian Reception", "jewish_christian_separation_required"),
        ("academic_comparison", "Academic Comparison", "has_academic_comparison_frame"),
        ("ancient_culture", "Ancient Culture", "ancient_culture_pressure"),
        ("textual_witness", "Textual Witness", "textual_witness_pressure"),
        ("theology_policy", "Theology Policy", "theology_pressure"),
        ("whole_tanakh_context", "Whole-Tanakh Context", "cross_reference_three_division"),
    ]
    rows = []
    for lane_id, label, unit_flag in lane_specs:
        flagged = [row for row in unit_rows if row.get(unit_flag)]
        rows.append(
            {
                "lane_id": lane_id,
                "lane_label": label,
                "unit_count": len(flagged),
                "unit_pct": pct(len(flagged), len(unit_rows)),
                "packet_count": packet_counts.get(lane_id, 0),
                "reachable_candidate_count": packet_reachable.get(lane_id, 0),
                "candidate_count": packet_candidate.get(lane_id, 0),
                "mean_interpretive_control_score": mean(
                    [float(row["interpretive_control_score"]) for row in flagged]
                ),
                "top_ref": flagged[0]["ref"] if flagged else "",
                "review_status": "unsigned",
                "authority_boundary": (
                    "Lane evidence routes review and notes; it cannot authorize "
                    "translation wording without Hebrew and release signoff."
                ),
            }
        )
    rows.sort(key=lambda row: (-row["unit_count"], -row["packet_count"], row["lane_id"]))
    return rows


def build_control_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    top_refs: dict[str, str] = {}
    for row in unit_rows:
        for control in str(row["claim_controls"]).split("; "):
            if not control:
                continue
            counts[control] += 1
            top_refs.setdefault(control, row["ref"])
    return [
        {
            "control": control,
            "unit_count": count,
            "unit_pct": pct(count, len(unit_rows)),
            "top_ref": top_refs.get(control, ""),
            "authority_effect": (
                "Control must be satisfied by reviewer evidence before interpretive "
                "claims affect translation wording."
            ),
        }
        for control, count in counts.most_common()
    ]


def build_summary(
    data: dict[str, dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    packet_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    reception = data["reception_divergence"]["summary"]
    boundary = data["reception_boundary"]["summary"]
    packets = data["reception_source_packets"]["summary"]
    adjudication = data["interpretive_adjudication"]["summary"]
    signals = data["corpus_reception_signal"]["summary"]
    witness = data["witness_divergence"]["summary"]
    critical_path = data["authority_critical_path"]["summary"]
    return {
        "unit_count": len(unit_rows),
        "reception_sensitive_unit_count": reception["reception_sensitive_unit_count"],
        "jewish_christian_separation_unit_count": reception[
            "jewish_christian_separation_unit_count"
        ],
        "academic_comparison_unit_count": reception["academic_comparison_unit_count"],
        "ancient_culture_pressure_unit_count": reception["ancient_culture_pressure_unit_count"],
        "textual_witness_pressure_unit_count": reception["textual_witness_pressure_unit_count"],
        "theology_pressure_unit_count": reception["theology_pressure_unit_count"],
        "translation_text_forbidden_reception_claim_units": boundary[
            "translation_text_forbidden_reception_claim_units"
        ],
        "high_boundary_risk_unit_count": boundary["high_boundary_risk_unit_count"],
        "avg_boundary_risk_score": boundary["avg_boundary_risk_score"],
        "packet_count": packets["packet_count"],
        "jewish_packet_count": packets["jewish_packet_count"],
        "christian_packet_count": packets["christian_packet_count"],
        "academic_packet_count": packets["academic_packet_count"],
        "reachable_candidate_source_count": packets["reachable_candidate_source_count"],
        "source_approval_count": packets["source_approval_count"],
        "completed_packet_review_count": packets["completed_packet_review_count"],
        "blocked_gate_count": packets["blocked_gate_count"],
        "failed_adjudication_gate_count": adjudication["failed_gate_count"],
        "failed_adjudication_gates": adjudication["failed_gates"],
        "units_with_layer_blockers": adjudication["units_with_layer_blockers"],
        "corpus_signal_unit_count": signals["signal_unit_count"],
        "corpus_high_pressure_signal_unit_count": signals["high_pressure_unit_count"],
        "corpus_new_high_pressure_candidate_count": signals[
            "new_high_pressure_expansion_candidate_count"
        ],
        "witness_high_divergence_unit_count": witness["high_divergence_unit_count"],
        "witness_divine_name_disagreement_unit_count": witness[
            "divine_name_disagreement_unit_count"
        ],
        "lane_count": len(lane_rows),
        "control_count": len(control_rows),
        "top_control_ref": unit_rows[0]["ref"] if unit_rows else "",
        "top_control_score": unit_rows[0]["interpretive_control_score"] if unit_rows else 0.0,
        "review_row_count": critical_path["review_row_count"],
        "completed_review_row_count": critical_path["completed_review_row_count"],
        "authority_verdict": (
            "Interpretive tradition evidence is rich enough to route separated review, "
            "but it is not authority: Jewish, Christian, academic, witness, and culture "
            "claims must remain outside translation wording until Hebrew, theology, "
            "and release signoff exist."
        ),
    }


def build_visual_data(
    unit_rows: list[dict[str, Any]],
    packet_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
    data: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    frame_rows = data["reception_divergence"].get("frame_rows", [])
    domain_rows = data["reception_divergence"].get("domain_rows", [])
    return {
        "top_unit_rows": [
            {"label": row["ref"], "value": row["interpretive_control_score"]}
            for row in unit_rows[:20]
        ],
        "lane_unit_rows": [
            {"label": row["lane_label"], "value": row["unit_count"]} for row in lane_rows
        ],
        "packet_lane_rows": [
            {"label": row["lane_label"], "value": row["packet_count"]} for row in lane_rows
        ],
        "control_rows": [
            {"label": row["control"], "value": row["unit_count"]} for row in control_rows[:15]
        ],
        "frame_rows": [
            {"label": row["frame"], "value": row["unit_count"]} for row in frame_rows[:16]
        ],
        "domain_rows": [
            {"label": row["domain"], "value": row["unit_count"]} for row in domain_rows[:12]
        ],
        "packet_license_rows": [
            {"label": label, "value": count}
            for label, count in Counter(row["best_license_risk"] for row in packet_rows).items()
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    packet_rows = build_packet_rows(data)
    unit_rows = build_unit_rows(data)
    lane_rows = build_lane_rows(data, unit_rows, packet_rows)
    control_rows = build_control_rows(unit_rows)
    summary = build_summary(data, unit_rows, packet_rows, lane_rows, control_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "interpretive tradition control matrix generated; not signoff",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": (
            "This matrix separates Jewish, Christian, academic, witness, culture, and "
            "Hebrew-source controls for review only. It does not decide interpretation, "
            "approve sources, authorize model training, or change canonical translation text."
        ),
        "summary": summary,
        "unit_rows": unit_rows,
        "lane_rows": lane_rows,
        "packet_rows": packet_rows,
        "control_rows": control_rows,
        "visual_data": build_visual_data(unit_rows, packet_rows, lane_rows, control_rows, data),
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
    label_width = 300
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
    unit_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['interpretive_control_score']:.2f}",
            f"{row['boundary_risk_score']:.2f}",
            "yes" if row["jewish_christian_separation_required"] else "no",
            "yes" if row["translation_text_forbidden_reception_claim"] else "no",
            f"{float(row['unit_authority_score_pct'] or 0):.2f}%",
            row["packet_review_row_count"],
            row["required_frames"],
            row["claim_controls"],
            row["next_action"],
        ]
        for row in report["unit_rows"][:35]
    ]
    lane_rows = [
        [
            row["lane_label"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["packet_count"],
            row["reachable_candidate_count"],
            f"{row['mean_interpretive_control_score']:.2f}",
            row["top_ref"],
            row["authority_boundary"],
        ]
        for row in report["lane_rows"]
    ]
    packet_rows = [
        [
            row["ref"],
            row["lane_label"],
            f"{row['priority_score']:.2f}",
            row["candidate_count"],
            row["reachable_candidate_count"],
            row["best_license_risk"],
            row["review_roles"],
            row["review_questions"],
            row["authority_boundary"],
        ]
        for row in report["packet_rows"][:45]
    ]
    control_rows = [
        [
            row["control"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["top_ref"],
            row["authority_effect"],
        ]
        for row in report["control_rows"][:30]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Interpretive Tradition Control Matrix</title>
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
  <h1>Interpretive Tradition Control Matrix</h1>
  <p class="lede">
    This report consolidates Jewish, Christian, academic, textual-witness,
    ancient-cultural, and Hebrew-source controls for the Psalms translation
    workbench. It is built from existing generated evidence and keeps reception
    claims separated from translation wording.
  </p>
  <div class="warning">
    <strong>Authority boundary:</strong> {esc(report["authority_policy"])}
  </div>
  {
        metric_cards(
            [
                (
                    "Split-lane units",
                    summary["jewish_christian_separation_unit_count"],
                    "Jewish and Christian reception must be separated.",
                ),
                (
                    "Reception-sensitive",
                    summary["reception_sensitive_unit_count"],
                    (
                        f"{summary['translation_text_forbidden_reception_claim_units']} "
                        "forbidden in translation text."
                    ),
                ),
                (
                    "Ancient culture",
                    summary["ancient_culture_pressure_unit_count"],
                    "Units requiring cultural/historical review.",
                ),
                (
                    "Textual witness",
                    summary["textual_witness_pressure_unit_count"],
                    "Witness pressure cannot override Hebrew silently.",
                ),
                (
                    "Reception packets",
                    summary["packet_count"],
                    f"{summary['source_approval_count']} source approvals.",
                ),
                (
                    "Review complete",
                    summary["completed_packet_review_count"],
                    f"{summary['review_row_count']} total critical-path review rows.",
                ),
                (
                    "Corpus signals",
                    summary["corpus_signal_unit_count"],
                    f"{summary['corpus_high_pressure_signal_unit_count']} high-pressure.",
                ),
                (
                    "Top control",
                    summary["top_control_ref"],
                    f"Score {summary['top_control_score']:.2f}.",
                ),
            ]
        )
    }
  <section>
    <h2>Control Frontier</h2>
    <div class="grid">
      <div class="chart">{
        svg_horizontal_bars(visual["top_unit_rows"], color="#9b3d3d", limit=20)
    }</div>
      <div class="chart">{
        svg_horizontal_bars(visual["lane_unit_rows"], color="#2f6f73", limit=10)
    }</div>
      <div class="chart">{
        svg_horizontal_bars(visual["control_rows"], color="#8a6426", limit=15)
    }</div>
      <div class="chart">{
        svg_horizontal_bars(visual["packet_lane_rows"], color="#2f6f73", limit=10)
    }</div>
    </div>
    {
        table(
            [
                "Rank",
                "Ref",
                "Control Score",
                "Boundary Risk",
                "J/C Split",
                "Forbidden In Text",
                "Authority %",
                "Review Rows",
                "Frames",
                "Controls",
                "Next Action",
            ],
            unit_rows,
        )
    }
  </section>
  <section>
    <h2>Lane Controls</h2>
    {
        table(
            [
                "Lane",
                "Units",
                "Pct",
                "Packets",
                "Reachable Sources",
                "Mean Score",
                "Top Ref",
                "Boundary",
            ],
            lane_rows,
        )
    }
  </section>
  <section>
    <h2>Reception Source Packets</h2>
    <div class="chart">{svg_horizontal_bars(visual["packet_license_rows"], color="#8a6426")}</div>
    {
        table(
            [
                "Ref",
                "Lane",
                "Priority",
                "Candidates",
                "Reachable",
                "License Risk",
                "Roles",
                "Review Questions",
                "Boundary",
            ],
            packet_rows,
        )
    }
  </section>
  <section>
    <h2>Claim Controls</h2>
    {table(["Control", "Units", "Pct", "Top Ref", "Authority Effect"], control_rows)}
  </section>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate interpretive tradition control matrix.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--packet-csv-output", type=Path, default=DEFAULT_PACKET_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.packet_csv_output, report["packet_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.packet_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
