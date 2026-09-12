from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"

SOURCE_PATHS = {
    "defense_exhibit": REPORT_ROOT / "doctoral_defense_exhibit_pack.json",
    "priority_dossier": REPORT_ROOT / "doctoral_priority_dossier_atlas.json",
    "context_integration": REPORT_ROOT / "doctoral_context_integration_matrix.json",
    "source_ladder": REPORT_ROOT / "source_authority_ladder_matrix.json",
    "claim_traceability": REPORT_ROOT / "translation_claim_traceability_audit.json",
    "unit_heatmap": REPORT_ROOT / "doctoral_unit_authority_heatmap.json",
    "translation_accuracy": REPORT_ROOT / "translation_accuracy_certification_matrix.json",
    "review_workbook": REPORT_ROOT / "contextual_review_signoff_workbook.json",
    "model_training": REPORT_ROOT / "model_training_certification_roadmap.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "critical_unit_decision_dossier.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "critical_unit_decision_dossier_units.csv"
DEFAULT_LANE_CSV_OUTPUT = REPORT_ROOT / "critical_unit_decision_dossier_lanes.csv"
DEFAULT_CLAIM_CSV_OUTPUT = REPORT_ROOT / "critical_unit_decision_dossier_claims.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "critical_unit_decision_dossier.html"

AUTHORITY_POLICY = (
    "The critical unit decision dossier is a committee triage artifact. It joins "
    "existing Hebrew, whole-Tanakh, cultural, witness, reception, model, source, "
    "claim, review, and release data, but it does not approve sources, settle "
    "Jewish or Christian interpretation, certify model output, authorize wording, "
    "or release canonical translation text."
)

DECISION_LANES = [
    ("source_approval", "Source approval"),
    ("whole_tanakh_morphology", "Whole-Tanakh morphology"),
    ("semantic_referent", "Semantic/referent"),
    ("jewish_christian", "Jewish/Christian separation"),
    ("textual_witness", "Textual witnesses"),
    ("model_evidence", "Model evidence"),
    ("human_signoff", "Human signoff"),
    ("release_authority", "Release authority"),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: float | int, total: float | int) -> float:
    return round(float(part) / float(total) * 100.0, 2) if total else 0.0


def decision_band(score: float) -> str:
    if score >= 1600:
        return "critical"
    if score >= 1100:
        return "highest"
    if score >= 750:
        return "high"
    return "watch"


def index_by_unit(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in rows}


def collect_unit_ids(data: dict[str, dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    sources = [
        data["defense_exhibit"].get("unit_rows", [])[:30],
        data["unit_heatmap"].get("unit_rows", [])[:30],
        data["claim_traceability"].get("unit_rows", [])[:30],
        data["context_integration"].get("priority_unit_rows", [])[:30],
        data["priority_dossier"].get("unit_rows", [])[:30],
    ]
    for rows in sources:
        for row in rows:
            unit_id = str(row["unit_id"])
            if unit_id not in seen:
                seen.add(unit_id)
                ordered.append(unit_id)
    return ordered


def build_model_counts(data: dict[str, dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "attempt_count": 0,
            "schema_valid_count": 0,
            "clean_source_anchored_count": 0,
            "source_anchor_issue_count": 0,
        }
    )
    for row in data["defense_exhibit"].get("unit_rows", []):
        unit_id = str(row["unit_id"])
        counts[unit_id] = {
            "attempt_count": int(row.get("model_attempt_count") or 0),
            "schema_valid_count": int(row.get("schema_valid_model_attempt_count") or 0),
            "clean_source_anchored_count": int(row.get("clean_source_anchored_attempt_count") or 0),
            "source_anchor_issue_count": int(row.get("model_source_anchor_issue_count") or 0),
        }
    return counts


def build_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    defense = index_by_unit(data["defense_exhibit"].get("unit_rows", []))
    priority = index_by_unit(data["priority_dossier"].get("unit_rows", []))
    heatmap = index_by_unit(data["unit_heatmap"].get("unit_rows", []))
    source = index_by_unit(data["source_ladder"].get("unit_rows", []))
    claims = index_by_unit(data["claim_traceability"].get("unit_rows", []))
    context = index_by_unit(data["context_integration"].get("unit_rows", []))
    model_counts = build_model_counts(data)

    rows: list[dict[str, Any]] = []
    for unit_id in collect_unit_ids(data):
        defense_row = defense.get(unit_id, {})
        priority_row = priority.get(unit_id, {})
        heatmap_row = heatmap.get(unit_id, {})
        source_row = source.get(unit_id, {})
        claim_row = claims.get(unit_id, {})
        context_row = context.get(unit_id, {})
        model = model_counts[unit_id]
        ref = (
            defense_row.get("ref")
            or priority_row.get("ref")
            or heatmap_row.get("ref")
            or claim_row.get("ref")
            or context_row.get("ref")
            or unit_id
        )
        source_readiness = float(
            source_row.get("source_authority_readiness_pct")
            or defense_row.get("source_authority_readiness_pct")
            or 0.0
        )
        unit_authority = float(
            heatmap_row.get("unit_authority_score_pct")
            or defense_row.get("unit_authority_score_pct")
            or priority_row.get("unit_authority_score_pct")
            or 0.0
        )
        blocking_lanes = int(
            heatmap_row.get("blocking_lane_count") or priority_row.get("blocking_lane_count") or 0
        )
        claim_gate_count = int(claim_row.get("blocking_gate_count") or 0)
        packet_review_rows = int(
            defense_row.get("packet_review_row_count")
            or heatmap_row.get("packet_review_row_count")
            or priority_row.get("packet_review_row_count")
            or 0
        )
        completed_review_rows = int(
            defense_row.get("completed_review_row_count")
            or source_row.get("completed_review_row_count")
            or 0
        )
        source_gap = float(
            source_row.get("source_authority_gap_score")
            or defense_row.get("source_authority_gap_score")
            or 0.0
        )
        defense_score = float(defense_row.get("defense_exhibit_score") or 0.0)
        integration_score = float(
            context_row.get("integration_pressure_score")
            or defense_row.get("integration_pressure_score")
            or 0.0
        )
        no_text_authority = int(claim_row.get("translation_text_allowed_now_count") or 0) == 0
        no_review = completed_review_rows == 0
        pressure_score = round(
            defense_score
            + source_gap
            + integration_score
            + claim_gate_count * 10.0
            + blocking_lanes * 28.0
            + (125.0 if no_text_authority else 0.0)
            + (100.0 if no_review else 0.0),
            2,
        )
        weakest_lanes = as_list(
            heatmap_row.get("weakest_required_lanes")
            or priority_row.get("weakest_required_lanes")
            or defense_row.get("weakest_required_lanes")
        )
        rows.append(
            {
                "unit_id": unit_id,
                "ref": ref,
                "decision_pressure_score": pressure_score,
                "decision_pressure_band": decision_band(pressure_score),
                "decision_status": "blocked_not_decidable",
                "source_authority_gap_score": source_gap,
                "source_authority_readiness_pct": source_readiness,
                "unit_authority_score_pct": unit_authority,
                "integration_pressure_score": integration_score,
                "active_lens_count": int(
                    context_row.get("active_lens_count")
                    or defense_row.get("active_lens_count")
                    or 0
                ),
                "claim_risk_score": float(
                    claim_row.get("claim_risk_score")
                    or heatmap_row.get("claim_risk_score")
                    or defense_row.get("claim_risk_score")
                    or 0.0
                ),
                "required_claim_family_count": int(
                    claim_row.get("required_claim_family_count") or 0
                ),
                "blocked_or_review_claim_family_count": int(
                    claim_row.get("blocked_or_review_claim_family_count") or 0
                ),
                "notes_only_claim_family_count": int(
                    claim_row.get("notes_only_claim_family_count") or 0
                ),
                "translation_text_allowed_now_count": int(
                    claim_row.get("translation_text_allowed_now_count") or 0
                ),
                "translation_text_allowed_after_review_count": int(
                    claim_row.get("translation_text_allowed_after_review_count") or 0
                ),
                "claim_blocking_gate_count": claim_gate_count,
                "blocking_lane_count": blocking_lanes,
                "weakest_required_lanes": weakest_lanes,
                "packet_review_row_count": packet_review_rows,
                "completed_review_row_count": completed_review_rows,
                "review_completion_pct": pct(completed_review_rows, packet_review_rows),
                "source_approval_count": int(
                    defense_row.get("source_approval_count")
                    or source_row.get("source_approval_count")
                    or 0
                ),
                "model_attempt_count": model["attempt_count"],
                "schema_valid_model_attempt_count": model["schema_valid_count"],
                "clean_source_anchored_attempt_count": model["clean_source_anchored_count"],
                "model_source_anchor_issue_count": model["source_anchor_issue_count"],
                "required_review_roles": as_list(
                    defense_row.get("required_review_roles")
                    or priority_row.get("required_review_roles")
                    or ""
                ),
                "jewish_christian_separation_required": bool(
                    defense_row.get("jewish_christian_separation_required")
                    or heatmap_row.get("jewish_christian_separation_required")
                    or priority_row.get("jewish_christian_separation_required")
                ),
                "textual_witness_pressure": bool(
                    defense_row.get("textual_witness_pressure")
                    or heatmap_row.get("textual_witness_pressure")
                    or priority_row.get("textual_witness_pressure")
                ),
                "ancient_culture_pressure": bool(
                    defense_row.get("ancient_culture_pressure")
                    or heatmap_row.get("ancient_culture_pressure")
                    or priority_row.get("ancient_culture_pressure")
                ),
                "cross_reference_three_division": bool(
                    defense_row.get("cross_reference_three_division")
                    or priority_row.get("cross_reference_three_division")
                    or context_row.get("whole_tanakh_three_division")
                ),
                "top_blocking_gates": as_list(claim_row.get("top_blocking_gates")),
                "blocked_claim_families": as_list(claim_row.get("blocked_claim_families")),
                "notes_only_claim_families": as_list(claim_row.get("notes_only_claim_families")),
                "next_action": (
                    heatmap_row.get("next_action")
                    or defense_row.get("next_action")
                    or priority_row.get("next_action")
                    or "Complete source, review, model, and release gates."
                ),
                "authority_boundary": AUTHORITY_POLICY,
            }
        )

    return sorted(rows, key=lambda row: (-float(row["decision_pressure_score"]), row["ref"]))[:35]


def lane_status(
    lane_id: str,
    unit: dict[str, Any],
    claim_row: dict[str, Any],
) -> tuple[str, str, str]:
    blocked_families = set(as_list(claim_row.get("blocked_claim_families")))
    weakest = set(as_list(unit.get("weakest_required_lanes")))
    top_gates = set(as_list(unit.get("top_blocking_gates")))
    if lane_id == "source_approval":
        status = "blocked" if int(unit["source_approval_count"]) == 0 else "partial"
        return (
            status,
            f"{unit['source_approval_count']} source approvals",
            "Record source decisions.",
        )
    if lane_id == "whole_tanakh_morphology":
        status = "blocked" if "whole_tanakh_context" in blocked_families else "review_required"
        return (
            status,
            "outside-Psalms morphology not locally authoritative",
            "Import approved morphology.",
        )
    if lane_id == "semantic_referent":
        status = "blocked" if "semantic_referent" in blocked_families else "review_required"
        return status, "semantic/referent enrichment missing", "Enrich and adjudicate roles."
    if lane_id == "jewish_christian":
        status = "blocked" if unit["jewish_christian_separation_required"] else "not_required"
        return status, "separated reception lanes required", "Complete Jewish/Christian review."
    if lane_id == "textual_witness":
        status = "review_required" if unit["textual_witness_pressure"] else "not_required"
        return (
            status,
            "witness pressure routes review",
            "Compare witnesses without overriding Hebrew.",
        )
    if lane_id == "model_evidence":
        if "model_evidence" in weakest or int(unit["clean_source_anchored_attempt_count"]) == 0:
            status = "blocked"
        else:
            status = "partial_not_authority"
        evidence = (
            f"{unit['clean_source_anchored_attempt_count']}/"
            f"{unit['model_attempt_count']} clean model attempts"
        )
        return status, evidence, "Run expanded benchmark and cross-exam."
    if lane_id == "human_signoff":
        status = "blocked" if "human_review_missing" in top_gates else "blocked"
        return (
            status,
            f"{unit['completed_review_row_count']} completed reviews",
            "Record signed review rows.",
        )
    if lane_id == "release_authority":
        status = "blocked"
        return status, "release signoff missing", "Keep claims out of canonical text."
    return "review_required", "", "Review lane."


def build_lane_rows(
    unit_rows: list[dict[str, Any]], data: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    claims = index_by_unit(data["claim_traceability"].get("unit_rows", []))
    rows: list[dict[str, Any]] = []
    for unit in unit_rows:
        claim_row = claims.get(str(unit["unit_id"]), {})
        for lane_id, label in DECISION_LANES:
            status, evidence, next_action = lane_status(lane_id, unit, claim_row)
            rows.append(
                {
                    "unit_id": unit["unit_id"],
                    "ref": unit["ref"],
                    "lane_id": lane_id,
                    "lane_label": label,
                    "status": status,
                    "evidence": evidence,
                    "next_action": next_action,
                }
            )
    return rows


def build_claim_rows(
    unit_rows: list[dict[str, Any]], data: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    selected = {str(row["unit_id"]) for row in unit_rows}
    rows = []
    for row in data["claim_traceability"].get("claim_rows", []):
        if str(row["unit_id"]) not in selected or not row.get("required"):
            continue
        rows.append(
            {
                "unit_id": row["unit_id"],
                "ref": row["ref"],
                "family_id": row["family_id"],
                "family_label": row["family_label"],
                "admissibility_status": row["admissibility_status"],
                "allowed_location": row["allowed_location"],
                "translation_text_allowed_now": row["translation_text_allowed_now"],
                "translation_text_allowed_after_review": row[
                    "translation_text_allowed_after_review"
                ],
                "blocking_gate_count": row["blocking_gate_count"],
                "blocking_gates": row["blocking_gates"],
                "evidence_grade": row["evidence_grade"],
                "evidence_summary": row["evidence_summary"],
            }
        )
    return rows


def build_visual_data(
    unit_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    claim_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    lane_blockers = Counter(
        row["lane_label"] for row in lane_rows if str(row["status"]).startswith("blocked")
    )
    gate_counts: Counter[str] = Counter()
    for row in claim_rows:
        gate_counts.update(as_list(row["blocking_gates"]))
    return {
        "decision_pressure_rows": [
            {"label": row["ref"], "value": row["decision_pressure_score"]} for row in unit_rows[:20]
        ],
        "authority_readiness_rows": [
            {"label": row["ref"], "value": row["unit_authority_score_pct"]}
            for row in sorted(unit_rows, key=lambda item: float(item["unit_authority_score_pct"]))[
                :20
            ]
        ],
        "lane_blocker_rows": [
            {"label": label, "value": count} for label, count in lane_blockers.most_common()
        ],
        "claim_gate_rows": [
            {"label": label, "value": count} for label, count in gate_counts.most_common(12)
        ],
        "model_attempt_rows": [
            {"label": row["ref"], "value": row["clean_source_anchored_attempt_count"]}
            for row in unit_rows[:20]
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    unit_rows = build_unit_rows(data)
    lane_rows = build_lane_rows(unit_rows, data)
    claim_rows = build_claim_rows(unit_rows, data)
    visual_data = build_visual_data(unit_rows, lane_rows, claim_rows)
    blocked_lane_rows = [row for row in lane_rows if str(row["status"]).startswith("blocked")]
    text_blocked_units = [
        row for row in unit_rows if int(row["translation_text_allowed_now_count"]) == 0
    ]
    clean_model_units = [
        row for row in unit_rows if int(row["clean_source_anchored_attempt_count"]) > 0
    ]
    jewish_christian_units = [
        row for row in unit_rows if row["jewish_christian_separation_required"]
    ]
    top_unit = unit_rows[0] if unit_rows else {}
    summary = {
        "unit_count": len(unit_rows),
        "critical_or_highest_unit_count": sum(
            1 for row in unit_rows if row["decision_pressure_band"] in {"critical", "highest"}
        ),
        "decision_lane_row_count": len(lane_rows),
        "blocked_lane_row_count": len(blocked_lane_rows),
        "claim_family_row_count": len(claim_rows),
        "text_blocked_unit_count": len(text_blocked_units),
        "clean_model_evidence_unit_count": len(clean_model_units),
        "jewish_christian_separation_unit_count": len(jewish_christian_units),
        "total_packet_review_row_count": sum(
            int(row["packet_review_row_count"]) for row in unit_rows
        ),
        "completed_review_row_count": sum(
            int(row["completed_review_row_count"]) for row in unit_rows
        ),
        "mean_unit_authority_score_pct": round(
            sum(float(row["unit_authority_score_pct"]) for row in unit_rows) / len(unit_rows),
            2,
        )
        if unit_rows
        else 0.0,
        "top_decision_unit": top_unit.get("unit_id", ""),
        "top_decision_ref": top_unit.get("ref", ""),
        "top_decision_pressure_score": top_unit.get("decision_pressure_score", 0),
        "top_decision_band": top_unit.get("decision_pressure_band", ""),
        "certification_status": "blocked_not_decidable",
        "authority_verdict": (
            "Critical units have enough joined evidence for committee triage, but no "
            "unit can be treated as a decided translation case until source approval, "
            "semantic/referent enrichment, separated reception review, benchmark "
            "coverage, human signoff, and release authority are complete."
        ),
    }
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "critical unit decision dossier generated; not review signoff",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": AUTHORITY_POLICY,
        "summary": summary,
        "unit_rows": unit_rows,
        "lane_rows": lane_rows,
        "claim_rows": claim_rows,
        "visual_data": visual_data,
    }


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def metric_cards(cards: list[tuple[str, str, str]]) -> str:
    return "".join(
        f"""
        <div class="metric-card">
          <h3>{escape(title)}</h3>
          <div class="metric-value">{escape(value)}</div>
          <p>{escape(detail)}</p>
        </div>
        """
        for title, value, detail in cards
    )


def bar_rows(
    rows: list[dict[str, Any]], *, suffix: str = "", max_value: float | None = None
) -> str:
    if max_value is None:
        max_value = max([float(row["value"]) for row in rows] or [1.0])
    rendered = []
    for row in rows:
        value = float(row["value"])
        width = 0.0 if not max_value else min(100.0, value / max_value * 100.0)
        rendered.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{escape(str(row["label"]))}</div>
              <div class="bar-track"><div class="bar-fill" style="width: {width:.2f}%"></div></div>
              <div class="bar-value">{value:.2f}{escape(suffix)}</div>
            </div>
            """
        )
    return "".join(rendered)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    unit_rows = report["unit_rows"]
    lane_rows = report["lane_rows"]
    claim_rows = report["claim_rows"]
    visual = report["visual_data"]

    unit_table = [
        [
            row["ref"],
            row["decision_pressure_score"],
            row["decision_pressure_band"],
            f"{row['unit_authority_score_pct']:.2f}%",
            row["claim_blocking_gate_count"],
            row["blocking_lane_count"],
            row["translation_text_allowed_now_count"],
            row["clean_source_anchored_attempt_count"],
            row["jewish_christian_separation_required"],
            "; ".join(row["weakest_required_lanes"][:5]),
        ]
        for row in unit_rows[:20]
    ]
    lane_table = [
        [
            row["ref"],
            row["lane_label"],
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in lane_rows[:120]
    ]
    claim_table = [
        [
            row["ref"],
            row["family_label"],
            row["admissibility_status"],
            row["allowed_location"],
            "yes" if row["translation_text_allowed_now"] else "no",
            row["blocking_gate_count"],
            "; ".join(row["blocking_gates"][:5]),
        ]
        for row in claim_rows[:120]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Critical Unit Decision Dossier</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #53616f;
      --line: #c9d1d9;
      --panel: #f8fafc;
      --accent: #2868a8;
      --accent-2: #9b3d2e;
      --bad: #a12727;
    }}
    body {{
      margin: 0;
      background: #ffffff;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 32px 24px 56px;
    }}
    h1, h2, h3 {{
      line-height: 1.15;
      margin: 0;
    }}
    h1 {{
      font-size: 2.15rem;
      max-width: 980px;
    }}
    h2 {{
      margin-top: 36px;
      font-size: 1.45rem;
    }}
    h3 {{
      font-size: 0.95rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    p {{
      color: var(--muted);
      margin: 8px 0 0;
    }}
    .lede {{
      max-width: 1040px;
      font-size: 1.05rem;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 12px;
      margin-top: 24px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: var(--panel);
    }}
    .metric-value {{
      color: var(--ink);
      font-size: 1.65rem;
      font-weight: 700;
      margin-top: 6px;
    }}
    .grid-2 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 20px;
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      background: #fff;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(150px, 1.2fr) minmax(140px, 2fr) 90px;
      gap: 10px;
      align-items: center;
      margin: 10px 0;
      font-size: 0.9rem;
    }}
    .bar-track {{
      height: 12px;
      background: #edf1f5;
      border-radius: 4px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
    }}
    .bar-value {{
      text-align: right;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 0.88rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      background: #f4f7fa;
      font-weight: 700;
    }}
    .callout {{
      border-left: 4px solid var(--bad);
      padding: 12px 16px;
      background: #fff7f5;
      margin-top: 20px;
    }}
    .callout strong {{
      color: var(--bad);
    }}
    footer {{
      margin-top: 32px;
      color: var(--muted);
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>
<main>
  <h1>Critical Unit Decision Dossier</h1>
  <p class="lede">
    This dossier joins the highest-pressure Psalm units into a decision-state ledger.
    It identifies which translation lanes are blocked, which claim families must stay
    outside translation text, where model evidence exists, and which reviewer actions
    would move each unit toward certifiable accuracy.
  </p>
  <div class="callout">
    <strong>Authority boundary:</strong> {escape(report["authority_policy"])}
  </div>

  <section class="metric-grid" aria-label="Headline metrics">
    {
        metric_cards(
            [
                (
                    "Decision Status",
                    summary["certification_status"],
                    summary["authority_verdict"],
                ),
                (
                    "Dossier Units",
                    fmt_int(summary["unit_count"]),
                    f"{fmt_int(summary['critical_or_highest_unit_count'])} critical/highest.",
                ),
                (
                    "Text-Blocked Units",
                    fmt_int(summary["text_blocked_unit_count"]),
                    "Units with zero current translation-text authority.",
                ),
                (
                    "Blocked Lane Rows",
                    fmt_int(summary["blocked_lane_row_count"]),
                    f"{fmt_int(summary['decision_lane_row_count'])} decision-lane rows.",
                ),
                (
                    "Clean Model Evidence",
                    fmt_int(summary["clean_model_evidence_unit_count"]),
                    "Units with at least one clean source-anchored model attempt.",
                ),
                (
                    "Review Rows",
                    fmt_int(summary["total_packet_review_row_count"]),
                    f"{fmt_int(summary['completed_review_row_count'])} completed.",
                ),
                (
                    "Top Unit",
                    summary["top_decision_ref"],
                    f"pressure {summary['top_decision_pressure_score']}.",
                ),
                (
                    "Mean Authority",
                    f"{summary['mean_unit_authority_score_pct']:.2f}%",
                    "Mean unit authority score across dossier units.",
                ),
            ]
        )
    }
  </section>

  <section>
    <h2>Visual Decision Pressure</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Top Decision Pressure</h3>
        {bar_rows(visual["decision_pressure_rows"])}
      </div>
      <div class="panel">
        <h3>Weakest Authority Scores</h3>
        {bar_rows(visual["authority_readiness_rows"], suffix="%", max_value=100.0)}
      </div>
      <div class="panel">
        <h3>Blocked Lanes</h3>
        {bar_rows(visual["lane_blocker_rows"])}
      </div>
      <div class="panel">
        <h3>Claim Blocking Gates</h3>
        {bar_rows(visual["claim_gate_rows"])}
      </div>
    </div>
  </section>

  <section>
    <h2>Dossier Units</h2>
    {
        table(
            [
                "Ref",
                "Pressure",
                "Band",
                "Authority",
                "Claim Gates",
                "Blocked Lanes",
                "Text Now",
                "Clean Model",
                "J/C Split",
                "Weakest Lanes",
            ],
            unit_table,
        )
    }
  </section>

  <section>
    <h2>Decision Lanes</h2>
    {table(["Ref", "Lane", "Status", "Evidence", "Next Action"], lane_table)}
  </section>

  <section>
    <h2>Required Claim Families</h2>
    {
        table(
            ["Ref", "Family", "Status", "Location", "Text Now", "Gate Count", "Gates"],
            claim_table,
        )
    }
  </section>

  <footer>
    Generated {escape(report["generated_on"])} from local research artifacts.
  </footer>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--lane-csv-output", type=Path, default=DEFAULT_LANE_CSV_OUTPUT)
    parser.add_argument("--claim-csv-output", type=Path, default=DEFAULT_CLAIM_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    args = parser.parse_args()

    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.lane_csv_output, report["lane_rows"])
    write_csv(args.claim_csv_output, report["claim_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")

    for path in [
        args.json_output,
        args.unit_csv_output,
        args.lane_csv_output,
        args.claim_csv_output,
        args.html_output,
    ]:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
