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

CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
MODEL_GAP_PATH = REPORT_ROOT / "model_evidence_gap_report.json"
REVIEW_WORKBOOK_PATH = REPORT_ROOT / "contextual_review_signoff_workbook.json"
SOURCE_PACKET_PATH = REPORT_ROOT / "contextual_source_packet_roadmap.json"
BIBLIOGRAPHY_PATH = REPORT_ROOT / "doctoral_bibliography_provenance.json"
AUTHORITY_PATH = REPORT_ROOT / "scholarly_authority_readiness.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "doctoral_unit_authority_heatmap.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "doctoral_unit_authority_heatmap_units.csv"
DEFAULT_LANE_CSV_OUTPUT = REPORT_ROOT / "doctoral_unit_authority_heatmap_lanes.csv"
DEFAULT_QUEUE_CSV_OUTPUT = REPORT_ROOT / "doctoral_unit_authority_heatmap_queue.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "doctoral_unit_authority_heatmap.html"

LANE_LABELS = {
    "hebrew_basis": "Hebrew Basis",
    "morphology_lexeme": "Morph/Lexeme",
    "whole_tanakh": "Whole Tanakh",
    "textual_witness": "Witnesses",
    "ancient_culture": "Culture",
    "jewish_christian_reception": "Jewish/Christian",
    "academic_comparison": "Academic",
    "source_packet": "Source Packet",
    "model_evidence": "Model Evidence",
    "human_signoff": "Human Signoff",
    "release_authority": "Release",
}

LANE_WEIGHTS = {
    "hebrew_basis": 14,
    "morphology_lexeme": 10,
    "whole_tanakh": 10,
    "textual_witness": 9,
    "ancient_culture": 8,
    "jewish_christian_reception": 10,
    "academic_comparison": 8,
    "source_packet": 10,
    "model_evidence": 8,
    "human_signoff": 8,
    "release_authority": 5,
}

BLOCKING_STATUSES = {"blocked", "not_started", "unsigned", "missing"}


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


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def rows_by_unit(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in rows if row.get("unit_id")}


def family_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["source_family"]): row for row in rows if row.get("source_family")}


def lane_row(
    *,
    unit_id: str,
    ref: str,
    lane: str,
    required: bool,
    score_pct: float,
    status: str,
    evidence: str,
    blocking_gap: str,
    next_action: str,
    source_families: list[str] | None = None,
    reviewer_roles: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "ref": ref,
        "lane": lane,
        "lane_label": LANE_LABELS[lane],
        "required": required,
        "weight": LANE_WEIGHTS[lane],
        "score_pct": clamp(score_pct),
        "status": status,
        "evidence": evidence,
        "blocking_gap": blocking_gap,
        "next_action": next_action,
        "source_families": source_families or [],
        "reviewer_roles": reviewer_roles or [],
    }


def score_from_status_text(text: str) -> tuple[float, str]:
    lowered = text.lower()
    if "strong" in lowered:
        return 75.0, "prototype"
    if "partial" in lowered:
        return 45.0, "partial"
    if "weak" in lowered or "absent" in lowered:
        return 15.0, "weak"
    if "surface bridge" in lowered:
        return 25.0, "blocked"
    if "required" in lowered:
        return 70.0, "prototype"
    return 30.0, "prototype"


def build_unit_lane_rows(
    *,
    claim: dict[str, Any],
    model: dict[str, Any] | None,
    review: dict[str, Any],
    packet: dict[str, Any] | None,
    source_families: dict[str, dict[str, Any]],
    authority: dict[str, Any],
) -> list[dict[str, Any]]:
    unit_id = str(claim["unit_id"])
    ref = str(claim["ref"])
    basis_statuses = claim.get("basis_statuses", {})
    packet_families = list(review.get("packet_families", []))
    reviewer_roles = list(review.get("distinct_reviewer_roles", []))
    required_frames = set(str(frame) for frame in claim.get("required_frames", []))
    claim_controls = set(str(control) for control in claim.get("claim_controls", []))

    rows: list[dict[str, Any]] = []
    hebrew_score, hebrew_status = score_from_status_text(
        str(basis_statuses.get("hebrew_source", ""))
    )
    rows.append(
        lane_row(
            unit_id=unit_id,
            ref=ref,
            lane="hebrew_basis",
            required=True,
            score_pct=hebrew_score,
            status=hebrew_status,
            evidence=str(basis_statuses.get("hebrew_source", "missing")),
            blocking_gap="Hebrew token basis still requires role review before authority.",
            next_action="Review token evidence, alignment rationale, and Hebrew wording basis.",
            source_families=["hebrew_source_tokens"],
            reviewer_roles=["Hebrew", "alignment", "lexical"],
        )
    )

    morphology_score, morphology_status = score_from_status_text(
        str(basis_statuses.get("morphology", ""))
    )
    if claim.get("outside_strong_context_pct", 0) == 0:
        morphology_score = min(morphology_score, 65.0)
    rows.append(
        lane_row(
            unit_id=unit_id,
            ref=ref,
            lane="morphology_lexeme",
            required=True,
            score_pct=morphology_score,
            status=morphology_status,
            evidence=str(basis_statuses.get("morphology", "missing")),
            blocking_gap="Non-Psalm Strong/lemma support remains absent locally.",
            next_action="Check Psalm morphology and defer whole-canon lexeme claims.",
            source_families=["morphology_lexeme"],
            reviewer_roles=["Hebrew", "lexical"],
        )
    )

    whole_required = True
    whole_score = 25.0 if claim.get("surface_outside_context_pct", 0) else 0.0
    rows.append(
        lane_row(
            unit_id=unit_id,
            ref=ref,
            lane="whole_tanakh",
            required=whole_required,
            score_pct=whole_score,
            status="blocked",
            evidence=(
                f"Surface bridge {claim.get('surface_outside_context_pct', 0):.2f}%; "
                f"outside Strong context {claim.get('outside_strong_context_pct', 0):.2f}%."
            ),
            blocking_gap="Whole-Tanakh evidence is surface-form context, not lemma or sense proof.",
            next_action="Build or import reviewed whole-Tanakh morphology before lexical claims.",
            source_families=["whole_tanakh_lemma_context"],
            reviewer_roles=["Hebrew", "lexical"],
        )
    )

    witness_required = bool(claim.get("textual_witness_pressure"))
    witness_score = 80.0 if claim.get("complete_expected_witness_set") else 35.0
    witness_status = "review_required" if witness_required else "not_required"
    rows.append(
        lane_row(
            unit_id=unit_id,
            ref=ref,
            lane="textual_witness",
            required=witness_required,
            score_pct=witness_score if witness_required else 100.0,
            status=witness_status,
            evidence=(
                f"{claim.get('witness_count', 0)} witnesses; "
                f"LXX present={bool(claim.get('has_lxx'))}; "
                f"English witnesses={claim.get('english_witness_count', 0)}."
            ),
            blocking_gap="Witnesses must remain labeled and cannot override Hebrew silently.",
            next_action="Attach witness notes and check leakage into generated wording.",
            source_families=["textual_witness_variants"],
            reviewer_roles=["Hebrew", "alignment", "theology"],
        )
    )

    culture_required = bool(claim.get("ancient_culture_pressure"))
    rows.append(
        lane_row(
            unit_id=unit_id,
            ref=ref,
            lane="ancient_culture",
            required=culture_required,
            score_pct=30.0 if culture_required else 100.0,
            status="routing_only" if culture_required else "not_required",
            evidence=(
                "Ancient-culture pressure present."
                if culture_required
                else "No ancient-culture pressure flag."
            ),
            blocking_gap="Culture claims are routed, not signed source synthesis.",
            next_action="Add cultural source packet and reviewer decision where required.",
            source_families=["ancient_near_eastern_context"],
            reviewer_roles=["Hebrew", "theology"],
        )
    )

    reception_required = bool(
        claim.get("reception_sensitive")
        or claim.get("has_jewish_reception_frame")
        or claim.get("has_christian_reception_frame")
        or "jewish_and_christian_reception_must_be_separate" in claim_controls
    )
    rows.append(
        lane_row(
            unit_id=unit_id,
            ref=ref,
            lane="jewish_christian_reception",
            required=reception_required,
            score_pct=0.0 if reception_required else 100.0,
            status="blocked" if reception_required else "not_required",
            evidence=(
                f"Jewish frame={bool(claim.get('has_jewish_reception_frame'))}; "
                f"Christian frame={bool(claim.get('has_christian_reception_frame'))}; "
                f"separation required={reception_required}."
            ),
            blocking_gap="Jewish and Christian reception packets are not signed.",
            next_action="Create separated reception packets and theology review decisions.",
            source_families=["jewish_reception_sources", "christian_reception_sources"],
            reviewer_roles=["theology", "Hebrew"],
        )
    )

    academic_required = "academic_critical_comparison" in required_frames
    rows.append(
        lane_row(
            unit_id=unit_id,
            ref=ref,
            lane="academic_comparison",
            required=academic_required,
            score_pct=0.0 if academic_required else 100.0,
            status="blocked" if academic_required else "not_required",
            evidence=(
                "Academic critical comparison required."
                if academic_required
                else "No academic comparison frame required."
            ),
            blocking_gap="No signed scholarly literature synthesis exists for this lane.",
            next_action="Attach scoped academic comparison notes as evidence packets.",
            source_families=["academic_critical_comparison"],
            reviewer_roles=["Hebrew", "theology"],
        )
    )

    packet_score = 0.0
    if packet_families:
        available = 0
        for family in packet_families:
            status = str(source_families.get(str(family), {}).get("status", ""))
            if "available" in status or "evidence_ready" in status or status == "prototype":
                available += 1
        packet_score = pct(available, len(packet_families)) * 0.55
    rows.append(
        lane_row(
            unit_id=unit_id,
            ref=ref,
            lane="source_packet",
            required=True,
            score_pct=packet_score,
            status="unsigned",
            evidence=(
                f"{len(packet_families)} packet families; "
                f"{review.get('packet_review_row_count', 0)} packet review rows."
            ),
            blocking_gap="Generated source packets are reviewer workload, not approval.",
            next_action="Complete source-packet review rows with reviewer decisions.",
            source_families=packet_families,
            reviewer_roles=reviewer_roles,
        )
    )

    model = model or {}
    model_score = float(model.get("schema_valid_expected_pct") or 0)
    model_status = str(model.get("evidence_status", "no_real_model_evidence"))
    rows.append(
        lane_row(
            unit_id=unit_id,
            ref=ref,
            lane="model_evidence",
            required=True,
            score_pct=model_score,
            status="partial" if model_score else "not_started",
            evidence=(
                f"{model.get('schema_valid_results', 0)} schema-valid of "
                f"{model.get('expected_model_task_results', 0)} expected model-task rows; "
                f"status={model_status}."
            ),
            blocking_gap=(
                "Real model grid is incomplete and model output is proposal evidence only."
            ),
            next_action=str(model.get("next_action", "run model grid and score outputs")),
            source_families=[],
            reviewer_roles=reviewer_roles,
        )
    )

    rows.append(
        lane_row(
            unit_id=unit_id,
            ref=ref,
            lane="human_signoff",
            required=True,
            score_pct=0.0,
            status="blocked",
            evidence="No completed human review rows exist.",
            blocking_gap="Reviewer identity, decision, score, and notes are missing.",
            next_action=(
                "Collect Hebrew, lexical, alignment, theology, lyric, and release decisions."
            ),
            source_families=["human_release_signoff"],
            reviewer_roles=reviewer_roles,
        )
    )
    rows.append(
        lane_row(
            unit_id=unit_id,
            ref=ref,
            lane="release_authority",
            required=True,
            score_pct=0.0,
            status="blocked",
            evidence=", ".join(authority["summary"].get("hard_blockers", [])),
            blocking_gap="Release authority is blocked until signoff and audit records exist.",
            next_action="Do not promote generated outputs to canonical.",
            source_families=["human_release_signoff"],
            reviewer_roles=["release"],
        )
    )
    return rows


def required_lane_mean(rows: list[dict[str, Any]]) -> float:
    required = [row for row in rows if row["required"]]
    total_weight = sum(float(row["weight"]) for row in required)
    if not total_weight:
        return 0.0
    total = sum(float(row["score_pct"]) * float(row["weight"]) for row in required)
    return round(total / total_weight, 2)


def blocking_lane_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if row["required"] and row["status"] in BLOCKING_STATUSES)


def weakest_required_lanes(rows: list[dict[str, Any]]) -> list[str]:
    required = [row for row in rows if row["required"]]
    required.sort(key=lambda row: (float(row["score_pct"]), -float(row["weight"])))
    return [str(row["lane"]) for row in required[:5]]


def next_action_for_unit(rows: list[dict[str, Any]]) -> str:
    required = [row for row in rows if row["required"]]
    required.sort(key=lambda row: (float(row["score_pct"]), -float(row["weight"])))
    if not required:
        return ""
    return str(required[0]["next_action"])


def build_report() -> dict[str, Any]:
    claim_matrix = load_json(CLAIM_MATRIX_PATH)
    model_gap = load_json(MODEL_GAP_PATH)
    review_workbook = load_json(REVIEW_WORKBOOK_PATH)
    source_packet = load_json(SOURCE_PACKET_PATH)
    bibliography = load_json(BIBLIOGRAPHY_PATH)
    authority = load_json(AUTHORITY_PATH)

    claim_rows = rows_by_unit(claim_matrix.get("unit_claim_rows", []))
    model_rows = rows_by_unit(model_gap.get("unit_gap_rows", []))
    review_rows = rows_by_unit(review_workbook.get("unit_rows", []))
    packet_rows = rows_by_unit(source_packet.get("unit_rows", []))
    families = family_lookup(bibliography.get("source_family_rows", []))

    unit_rows = []
    lane_rows = []
    for unit_id, claim in claim_rows.items():
        review = review_rows.get(unit_id, {})
        rows = build_unit_lane_rows(
            claim=claim,
            model=model_rows.get(unit_id),
            review=review,
            packet=packet_rows.get(unit_id),
            source_families=families,
            authority=authority,
        )
        lane_rows.extend(rows)
        required_rows = [row for row in rows if row["required"]]
        unit_authority_score = required_lane_mean(rows)
        blockers = blocking_lane_count(rows)
        unit_rows.append(
            {
                "unit_id": unit_id,
                "ref": claim["ref"],
                "unit_authority_score_pct": unit_authority_score,
                "claim_risk_score": claim.get("claim_risk_score", 0.0),
                "claim_risk_band": claim.get("claim_risk_band", ""),
                "packet_priority_score": review.get("packet_priority_score", 0.0),
                "gap_priority_score": model_rows.get(unit_id, {}).get("gap_priority_score", 0.0),
                "required_lane_count": len(required_rows),
                "blocking_lane_count": blockers,
                "required_review_role_count": len(set(review.get("distinct_reviewer_roles", []))),
                "packet_family_count": review.get("packet_family_count", 0),
                "packet_review_row_count": review.get("packet_review_row_count", 0),
                "schema_valid_expected_pct": model_rows.get(unit_id, {}).get(
                    "schema_valid_expected_pct", 0.0
                ),
                "reception_sensitive": bool(claim.get("reception_sensitive")),
                "jewish_christian_separation_required": bool(
                    review.get("jewish_christian_separation_required")
                    or claim.get("has_jewish_reception_frame")
                    or claim.get("has_christian_reception_frame")
                ),
                "textual_witness_pressure": bool(claim.get("textual_witness_pressure")),
                "ancient_culture_pressure": bool(claim.get("ancient_culture_pressure")),
                "weakest_required_lanes": weakest_required_lanes(rows),
                "next_action": next_action_for_unit(rows),
            }
        )

    unit_rows.sort(
        key=lambda row: (
            float(row["unit_authority_score_pct"]),
            -int(row["blocking_lane_count"]),
            -float(row["claim_risk_score"]),
        )
    )

    lane_summary = []
    for lane in LANE_LABELS:
        rows = [row for row in lane_rows if row["lane"] == lane and row["required"]]
        if not rows:
            continue
        lane_summary.append(
            {
                "lane": lane,
                "lane_label": LANE_LABELS[lane],
                "required_unit_count": len(rows),
                "mean_score_pct": round(
                    sum(float(row["score_pct"]) for row in rows) / len(rows), 2
                ),
                "blocked_unit_count": sum(1 for row in rows if row["status"] in BLOCKING_STATUSES),
                "strong_or_review_ready_count": sum(
                    1 for row in rows if float(row["score_pct"]) >= 70
                ),
                "top_blocking_gap": Counter(str(row["blocking_gap"]) for row in rows).most_common(
                    1
                )[0][0],
            }
        )

    queue_rows = [
        {
            "rank": index + 1,
            **row,
        }
        for index, row in enumerate(unit_rows[:30])
    ]

    blocked_unit_count = sum(1 for row in unit_rows if row["blocking_lane_count"])
    mean_score = round(
        sum(float(row["unit_authority_score_pct"]) for row in unit_rows) / len(unit_rows),
        2,
    )
    lane_status_counts = Counter(str(row["status"]) for row in lane_rows if row["required"])
    weakest_unit = unit_rows[0] if unit_rows else {}

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "doctoral unit authority heatmap generated; not reviewer signoff",
        "source_paths": {
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
            "model_gap": str(MODEL_GAP_PATH.relative_to(ROOT)),
            "review_workbook": str(REVIEW_WORKBOOK_PATH.relative_to(ROOT)),
            "source_packet": str(SOURCE_PACKET_PATH.relative_to(ROOT)),
            "bibliography": str(BIBLIOGRAPHY_PATH.relative_to(ROOT)),
            "authority": str(AUTHORITY_PATH.relative_to(ROOT)),
        },
        "authority_boundary": {
            "heatmap_boundary": "Scores are triage readiness, not approvals.",
            "canonical_boundary": "No unit may become canonical from this report alone.",
            "blocked_lane_boundary": (
                "Blocked lanes require source acquisition, model completion, human review, "
                "or release signoff."
            ),
        },
        "summary": {
            "unit_count": len(unit_rows),
            "lane_row_count": len(lane_rows),
            "required_lane_row_count": sum(1 for row in lane_rows if row["required"]),
            "mean_unit_authority_score_pct": mean_score,
            "blocked_unit_count": blocked_unit_count,
            "blocked_unit_pct": pct(blocked_unit_count, len(unit_rows)),
            "lane_count": len(lane_summary),
            "queue_unit_count": len(queue_rows),
            "critical_queue_unit_count": sum(
                1 for row in queue_rows if row["packet_priority_score"] >= 400
            ),
            "top_gap_unit": weakest_unit.get("unit_id", ""),
            "top_gap_ref": weakest_unit.get("ref", ""),
            "top_gap_score_pct": weakest_unit.get("unit_authority_score_pct", 0.0),
            "top_gap_blocking_lane_count": weakest_unit.get("blocking_lane_count", 0),
            "status_counts": dict(lane_status_counts.most_common()),
            "status": "heatmap_generated_not_signoff",
        },
        "unit_rows": unit_rows,
        "lane_rows": lane_rows,
        "lane_summary_rows": lane_summary,
        "queue_rows": queue_rows,
    }


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def metric_cards(cards: list[tuple[str, str, str]]) -> str:
    return "\n".join(
        f"""
        <article class="metric-card">
          <h3>{esc(label)}</h3>
          <p class="metric-value">{esc(value)}</p>
          <p>{esc(note)}</p>
        </article>
        """
        for label, value, note in cards
    )


def bar_rows(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    max_value: float | None = None,
    suffix: str = "",
) -> str:
    if max_value is None:
        max_value = max((float(row.get(value_key) or 0) for row in rows), default=1.0)
    if not max_value:
        max_value = 1.0
    output = []
    for row in rows:
        value = float(row.get(value_key) or 0)
        width = clamp(value / max_value * 100)
        output.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{esc(row.get(label_key, ""))}</div>
              <div class="bar-track">
                <div class="bar-fill" style="width: {width}%"></div>
              </div>
              <div class="bar-value">{esc(f"{value:.2f}{suffix}")}</div>
            </div>
            """
        )
    return "\n".join(output)


def cell_class(score: float, status: str) -> str:
    if status in BLOCKING_STATUSES or score < 25:
        return "cell-blocked"
    if score < 60:
        return "cell-partial"
    if score < 85:
        return "cell-review"
    return "cell-strong"


def render_heatmap_table(report: dict[str, Any], limit: int = 25) -> str:
    lanes = list(LANE_LABELS)
    lane_by_unit: dict[tuple[str, str], dict[str, Any]] = {
        (str(row["unit_id"]), str(row["lane"])): row for row in report["lane_rows"]
    }
    headers = ["Ref", "Score", "Blockers", *[LANE_LABELS[lane] for lane in lanes]]
    rows_html = []
    for unit in report["queue_rows"][:limit]:
        cells = [
            f"<td>{esc(unit['ref'])}<br><span>{esc(unit['unit_id'])}</span></td>",
            f"<td>{float(unit['unit_authority_score_pct']):.2f}%</td>",
            f"<td>{esc(unit['blocking_lane_count'])}</td>",
        ]
        for lane in lanes:
            lane_data = lane_by_unit.get((str(unit["unit_id"]), lane), {})
            score = float(lane_data.get("score_pct", 0))
            status = str(lane_data.get("status", "missing"))
            if not lane_data.get("required", False):
                cells.append('<td class="cell-na">N/R</td>')
                continue
            cells.append(
                f'<td class="{cell_class(score, status)}">'
                f"{score:.0f}<br><span>{esc(status)}</span></td>"
            )
        rows_html.append("<tr>" + "".join(cells) + "</tr>")
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows_html)}</tbody></table>"


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lane_summary_rows = [
        [
            row["lane_label"],
            row["required_unit_count"],
            f"{row['mean_score_pct']:.2f}%",
            row["blocked_unit_count"],
            row["strong_or_review_ready_count"],
            row["top_blocking_gap"],
        ]
        for row in report["lane_summary_rows"]
    ]
    queue_rows = [
        [
            row["rank"],
            row["ref"],
            row["unit_id"],
            f"{row['unit_authority_score_pct']:.2f}%",
            row["blocking_lane_count"],
            row["claim_risk_score"],
            row["packet_review_row_count"],
            row["schema_valid_expected_pct"],
            "; ".join(row["weakest_required_lanes"]),
            row["next_action"],
        ]
        for row in report["queue_rows"][:20]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Doctoral Unit Authority Heatmap</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #53616f;
      --line: #c9d1d9;
      --panel: #f8fafc;
      --accent: #2868a8;
      --accent-2: #7c5b2f;
      --bad: #a12727;
      --warn: #b36b00;
      --review: #2f6f73;
      --strong: #23623d;
    }}
    body {{
      margin: 0;
      background: #fff;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 32px 24px 56px;
    }}
    h1, h2, h3 {{
      line-height: 1.15;
      margin: 0;
    }}
    h1 {{
      font-size: 2.1rem;
      max-width: 980px;
    }}
    h2 {{
      margin-top: 36px;
      font-size: 1.45rem;
    }}
    h3 {{
      color: var(--muted);
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    p {{
      color: var(--muted);
      margin: 8px 0 0;
    }}
    .lede {{
      max-width: 1020px;
      font-size: 1.05rem;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 24px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 16px;
    }}
    .metric-value {{
      color: var(--ink);
      font-size: 1.7rem;
      font-weight: 700;
      margin-top: 6px;
    }}
    .grid-2 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
      gap: 20px;
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(170px, 1.2fr) minmax(140px, 2fr) 86px;
      gap: 10px;
      align-items: center;
      margin: 10px 0;
      font-size: 0.92rem;
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
      color: var(--muted);
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 0.84rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 7px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f4f7fa;
      color: var(--muted);
    }}
    td span {{
      color: var(--muted);
      font-size: 0.76rem;
    }}
    .cell-blocked {{
      background: #fff0ed;
      color: var(--bad);
      font-weight: 700;
      text-align: center;
    }}
    .cell-partial {{
      background: #fff8e8;
      color: var(--warn);
      font-weight: 700;
      text-align: center;
    }}
    .cell-review {{
      background: #edf8f0;
      color: var(--review);
      font-weight: 700;
      text-align: center;
    }}
    .cell-strong {{
      background: #e7f5ec;
      color: var(--strong);
      font-weight: 700;
      text-align: center;
    }}
    .cell-na {{
      background: #f5f7fa;
      color: var(--muted);
      text-align: center;
    }}
    .callout {{
      border-left: 4px solid var(--bad);
      background: #fff7f5;
      padding: 12px 16px;
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
  <h1>Doctoral Unit Authority Heatmap</h1>
  <p class="lede">
    This report scores each expanded Psalm benchmark unit across Hebrew basis,
    morphology, whole-Tanakh context, witnesses, culture, reception, academic
    comparison, source packets, model evidence, human signoff, and release authority.
  </p>
  <div class="callout">
    <strong>Authority boundary:</strong>
    {esc(report["authority_boundary"]["heatmap_boundary"])}
    {esc(report["authority_boundary"]["canonical_boundary"])}
  </div>

  <section class="metric-grid" aria-label="Heatmap metrics">
    {
        metric_cards(
            [
                (
                    "Mean Unit Score",
                    f"{summary['mean_unit_authority_score_pct']:.2f}%",
                    "Weighted over required lanes only.",
                ),
                (
                    "Blocked Units",
                    fmt_int(summary["blocked_unit_count"]),
                    f"{summary['blocked_unit_pct']:.2f}% of heatmap units.",
                ),
                (
                    "Lane Rows",
                    fmt_int(summary["lane_row_count"]),
                    f"{fmt_int(summary['required_lane_row_count'])} required lane rows.",
                ),
                (
                    "Queue Units",
                    fmt_int(summary["queue_unit_count"]),
                    f"{fmt_int(summary['critical_queue_unit_count'])} critical-priority units.",
                ),
                (
                    "Top Gap",
                    summary["top_gap_ref"],
                    f"{summary['top_gap_score_pct']:.2f}% unit score.",
                ),
            ]
        )
    }
  </section>

  <section>
    <h2>Visual Lane Summary</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Mean Lane Score</h3>
        {
        bar_rows(
            report["lane_summary_rows"],
            label_key="lane_label",
            value_key="mean_score_pct",
            max_value=100,
            suffix="%",
        )
    }
      </div>
      <div class="panel">
        <h3>Blocked Units by Lane</h3>
        {
        bar_rows(
            report["lane_summary_rows"], label_key="lane_label", value_key="blocked_unit_count"
        )
    }
      </div>
    </div>
  </section>

  <section>
    <h2>Priority Heatmap</h2>
    {render_heatmap_table(report)}
  </section>

  <section>
    <h2>Lane Summary</h2>
    {
        table(
            ["Lane", "Required Units", "Mean Score", "Blocked", "Review Ready", "Top Gap"],
            lane_summary_rows,
        )
    }
  </section>

  <section>
    <h2>Reviewer Queue</h2>
    {
        table(
            [
                "Rank",
                "Ref",
                "Unit",
                "Score",
                "Blockers",
                "Claim Risk",
                "Packet Rows",
                "Model Valid %",
                "Weakest Lanes",
                "Next Action",
            ],
            queue_rows,
        )
    }
  </section>

  <footer>
    Generated {esc(report["generated_on"])} from current generated research reports.
    Scores are deterministic triage scores and do not approve wording.
  </footer>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the doctoral unit authority heatmap.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--lane-csv-output", type=Path, default=DEFAULT_LANE_CSV_OUTPUT)
    parser.add_argument("--queue-csv-output", type=Path, default=DEFAULT_QUEUE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.lane_csv_output, report["lane_rows"])
    write_csv(args.queue_csv_output, report["queue_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")


if __name__ == "__main__":
    main()
