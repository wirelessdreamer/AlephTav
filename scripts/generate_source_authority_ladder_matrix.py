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
    "source_packets": REPORT_ROOT / "contextual_source_packet_roadmap.json",
    "source_acquisition": REPORT_ROOT / "contextual_source_acquisition_plan.json",
    "source_maturity": REPORT_ROOT / "scholarly_source_maturity_report.json",
    "bibliography": REPORT_ROOT / "doctoral_bibliography_provenance.json",
    "source_verification": REPORT_ROOT / "doctoral_source_verification.json",
    "review_workbook": REPORT_ROOT / "contextual_review_signoff_workbook.json",
    "priority_dossier_atlas": REPORT_ROOT / "doctoral_priority_dossier_atlas.json",
    "interpretive_control": REPORT_ROOT / "interpretive_tradition_control_matrix.json",
    "context_integration": REPORT_ROOT / "doctoral_context_integration_matrix.json",
    "authority_critical_path": REPORT_ROOT / "authority_critical_path_report.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "source_authority_ladder_matrix.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "source_authority_ladder_units.csv"
DEFAULT_FAMILY_CSV_OUTPUT = REPORT_ROOT / "source_authority_ladder_families.csv"
DEFAULT_SOURCE_CSV_OUTPUT = REPORT_ROOT / "source_authority_ladder_sources.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "source_authority_ladder_matrix.html"

AUTHORITY_POLICY = (
    "The source authority ladder measures provenance, source reachability, license risk, "
    "review workload, and source-family coverage. It does not approve sources, decide "
    "interpretation, authorize model training, or change canonical translation text."
)


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


def risk_rank(value: str) -> int:
    text = value.lower()
    if text in {"", "low", "public domain", "cc by 4.0", "none_internal"}:
        return 0
    if "medium" in text or "custom" in text or "project_specific" in text:
        return 1
    if "per_text" in text or "sharealike" in text:
        return 2
    if "high" in text or "noncommercial" in text or "rights" in text:
        return 3
    return 1


def is_source_approved(row: dict[str, Any]) -> bool:
    status = str(row.get("authority_status", "")).lower()
    verification = str(row.get("verification_status", "")).lower()
    approved_statuses = {
        "approved",
        "source_approved",
        "license_provenance_approved",
        "approved_for_generation",
        "approved_for_canonical_use",
    }
    return status in approved_statuses or verification in approved_statuses


def source_family_map(data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["source_family"]): row
        for row in data["bibliography"].get("source_family_rows", [])
        if row.get("source_family")
    }


def source_rows_by_id(data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in data["source_verification"].get("source_rows", []):
        rows[str(row["source_id"])] = row
    return rows


def acquisition_rows_by_id(data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["candidate_id"]): row
        for row in data["source_acquisition"].get("candidate_rows", [])
        if row.get("candidate_id")
    }


def bibliography_rows_by_id(data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["source_id"]): row
        for row in data["bibliography"].get("bibliography_rows", [])
        if row.get("source_id")
    }


def build_source_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    acquisition_by_id = acquisition_rows_by_id(data)
    bibliography_by_id = bibliography_rows_by_id(data)
    rows: list[dict[str, Any]] = []
    for source in data["source_verification"].get("source_rows", []):
        source_id = str(source["source_id"])
        acquisition = acquisition_by_id.get(source_id, {})
        bibliography = bibliography_by_id.get(source_id, {})
        source_families = acquisition.get("source_families") or bibliography.get(
            "source_families", []
        )
        rows.append(
            {
                "source_id": source_id,
                "source_class": source.get("source_class", ""),
                "label": source.get("label", ""),
                "tier": source.get("tier", bibliography.get("tier", "")),
                "source_families": list_join(source_families),
                "license_risk": source.get("license_risk", ""),
                "reachable": bool(source.get("reachable")),
                "http_status": source.get("http_status", ""),
                "verification_status": source.get("verification_status", ""),
                "license_claim_status": source.get("license_claim_status", ""),
                "detected_terms": list_join(source.get("detected_terms", [])),
                "machine_readable": bool(
                    acquisition.get("machine_readable", bibliography.get("machine_readable", False))
                ),
                "generation_policy": source.get(
                    "generation_policy", bibliography.get("generation_policy", "")
                ),
                "source_approved": is_source_approved(source),
                "authority_status": source.get("authority_status", ""),
                "official_url": source.get("official_url", ""),
                "authority_boundary": source.get("authority_boundary", ""),
            }
        )
    rows.sort(
        key=lambda row: (
            row["source_class"] != "source_acquisition_candidate",
            -risk_rank(str(row["license_risk"])),
            row["source_id"],
        )
    )
    return rows


def build_family_rows(
    data: dict[str, dict[str, Any]], source_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    source_by_id = {row["source_id"]: row for row in source_rows}
    family_rows: list[dict[str, Any]] = []
    for family in data["bibliography"].get("source_family_rows", []):
        candidate_ids = [str(value) for value in family.get("candidate_ids", [])]
        candidates = [
            source_by_id[candidate_id]
            for candidate_id in candidate_ids
            if candidate_id in source_by_id
        ]
        reachable = [row for row in candidates if row["reachable"]]
        approved = [row for row in candidates if row["source_approved"]]
        machine = [row for row in candidates if row["machine_readable"]]
        high_risk = [row for row in candidates if risk_rank(str(row.get("license_risk", ""))) >= 3]
        no_candidate = not candidate_ids
        no_reachable = bool(candidate_ids) and not reachable
        if no_candidate:
            blocker = "candidate_source_missing"
        elif no_reachable:
            blocker = "reachable_source_missing"
        elif high_risk:
            blocker = "license_risk_requires_manual_rights_review"
        elif not approved:
            blocker = "source_approval_missing"
        else:
            blocker = "packet_review_and_release_signoff_missing"
        family_rows.append(
            {
                "source_family": family["source_family"],
                "label": family["label"],
                "unit_count": family["unit_count"],
                "candidate_count": len(candidate_ids),
                "reachable_candidate_count": len(reachable),
                "machine_readable_candidate_count": len(machine),
                "high_license_risk_candidate_count": len(high_risk),
                "source_approval_count": len(approved),
                "best_license_risk": family.get("best_license_risk", ""),
                "candidate_ids": list_join(candidate_ids),
                "review_roles": list_join(family.get("review_roles", [])),
                "required_artifacts": list_join(family.get("required_artifacts", [])),
                "top_ref": family.get("top_ref", ""),
                "top_packet_priority_score": family.get("top_packet_priority_score", 0.0),
                "authority_blocker": blocker,
                "authority_boundary": family.get("authority_boundary", ""),
            }
        )
    family_rows.sort(
        key=lambda row: (
            row["source_approval_count"] > 0,
            -int(row["unit_count"]),
            row["source_family"],
        )
    )
    return family_rows


def unit_stage(
    candidate_count: int,
    reachable_count: int,
    source_approval_count: int,
    completed_review_count: int,
    review_row_count: int,
) -> str:
    if (
        source_approval_count
        and completed_review_count
        and completed_review_count >= review_row_count
    ):
        return "L6_signed_review_ready_for_release_gate"
    if source_approval_count and completed_review_count:
        return "L5_partial_review_after_source_approval"
    if source_approval_count:
        return "L4_sources_approved_review_pending"
    if reachable_count:
        return "L3_reachable_sources_unapproved"
    if candidate_count:
        return "L2_candidate_sources_unverified"
    return "L1_packet_family_only"


def chief_blocker(
    missing_family_count: int,
    unreachable_family_count: int,
    high_license_family_count: int,
    source_approval_count: int,
    review_row_count: int,
    completed_review_count: int,
) -> str:
    if missing_family_count:
        return "source_family_candidate_missing"
    if unreachable_family_count:
        return "source_reachability_gap"
    if high_license_family_count:
        return "manual_rights_or_noncommercial_license_gap"
    if not source_approval_count:
        return "source_approval_missing"
    if review_row_count and not completed_review_count:
        return "review_signoff_missing"
    return "release_authority_missing"


def build_unit_rows(
    data: dict[str, dict[str, Any]],
    family_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    families = {row["source_family"]: row for row in family_rows}
    sources = {row["source_id"]: row for row in source_rows}
    review_by_unit = by_key(data["review_workbook"].get("unit_rows", []), "unit_id")
    dossier_by_unit = by_key(data["priority_dossier_atlas"].get("unit_rows", []), "unit_id")
    control_by_unit = by_key(data["interpretive_control"].get("unit_rows", []), "unit_id")
    integration_by_unit = by_key(data["context_integration"].get("unit_rows", []), "unit_id")

    rows: list[dict[str, Any]] = []
    for packet in data["source_packets"].get("unit_rows", []):
        unit_id = str(packet["unit_id"])
        review = review_by_unit.get(unit_id, {})
        dossier = dossier_by_unit.get(unit_id, {})
        control = control_by_unit.get(unit_id, {})
        integration = integration_by_unit.get(unit_id, {})
        packet_families = [str(value) for value in packet.get("packet_families", [])]
        family_refs = [families[family] for family in packet_families if family in families]
        candidate_ids = sorted(
            {
                candidate_id
                for family in family_refs
                for candidate_id in str(family.get("candidate_ids", "")).split("; ")
                if candidate_id
            }
        )
        candidate_sources = [
            sources[source_id] for source_id in candidate_ids if source_id in sources
        ]
        reachable_sources = [source for source in candidate_sources if source["reachable"]]
        machine_sources = [source for source in candidate_sources if source["machine_readable"]]
        low_risk_sources = [
            source for source in candidate_sources if risk_rank(str(source["license_risk"])) == 0
        ]
        high_risk_sources = [
            source for source in candidate_sources if risk_rank(str(source["license_risk"])) >= 3
        ]
        approved_sources = [source for source in candidate_sources if source["source_approved"]]
        missing_family_count = sum(1 for family in family_refs if not family["candidate_count"])
        unreachable_family_count = sum(
            1
            for family in family_refs
            if family["candidate_count"] and not family["reachable_candidate_count"]
        )
        high_license_family_count = sum(
            1 for family in family_refs if family["high_license_risk_candidate_count"]
        )
        review_rows = int(review.get("packet_review_row_count", 0))
        completed_reviews = int(review.get("completed_review_row_count", 0) or 0)
        source_authority_readiness_pct = round(
            min(
                100.0,
                20.0
                + pct(len(reachable_sources), max(1, len(candidate_ids))) * 0.20
                + pct(len(machine_sources), max(1, len(candidate_ids))) * 0.10
                + pct(len(low_risk_sources), max(1, len(candidate_ids))) * 0.10
                + pct(len(approved_sources), max(1, len(candidate_ids))) * 0.30
                + pct(completed_reviews, max(1, review_rows)) * 0.30,
            ),
            2,
        )
        source_authority_gap_score = round(
            float(packet.get("packet_priority_score") or 0.0)
            + missing_family_count * 20
            + unreachable_family_count * 16
            + high_license_family_count * 14
            + (45 if not approved_sources else 0)
            + (35 if review_rows and not completed_reviews else 0)
            + (25 if packet.get("jewish_christian_separation_required") else 0)
            + (20 if packet.get("ancient_culture_pressure") else 0)
            + (20 if packet.get("textual_witness_pressure") else 0)
            + (15 if dossier.get("cross_reference_three_division") else 0),
            2,
        )
        stage = unit_stage(
            len(candidate_ids),
            len(reachable_sources),
            len(approved_sources),
            completed_reviews,
            review_rows,
        )
        rows.append(
            {
                "rank": 0,
                "unit_id": unit_id,
                "ref": packet["ref"],
                "source_hebrew": packet.get("source_hebrew", ""),
                "source_authority_gap_score": source_authority_gap_score,
                "source_authority_readiness_pct": source_authority_readiness_pct,
                "evidence_ladder_stage": stage,
                "chief_blocker": chief_blocker(
                    missing_family_count,
                    unreachable_family_count,
                    high_license_family_count,
                    len(approved_sources),
                    review_rows,
                    completed_reviews,
                ),
                "packet_priority_score": packet.get("packet_priority_score", 0.0),
                "dossier_priority_score": dossier.get("doctoral_dossier_priority_score", 0.0),
                "interpretive_control_score": control.get("interpretive_control_score", 0.0),
                "integration_pressure_score": integration.get(
                    "integration_pressure_score",
                    integration.get("top_integration_pressure_score", 0.0),
                ),
                "packet_family_count": len(packet_families),
                "missing_candidate_family_count": missing_family_count,
                "unreachable_family_count": unreachable_family_count,
                "high_license_risk_family_count": high_license_family_count,
                "candidate_source_count": len(candidate_ids),
                "reachable_candidate_source_count": len(reachable_sources),
                "machine_readable_candidate_source_count": len(machine_sources),
                "low_license_risk_source_count": len(low_risk_sources),
                "high_license_risk_source_count": len(high_risk_sources),
                "source_approval_count": len(approved_sources),
                "packet_review_row_count": review_rows,
                "completed_review_row_count": completed_reviews,
                "review_completion_pct": pct(completed_reviews, review_rows),
                "required_review_roles": list_join(
                    review.get("distinct_reviewer_roles", packet.get("required_review_roles", []))
                ),
                "packet_families": list_join(packet_families, 12),
                "candidate_source_ids": list_join(candidate_ids, 12),
                "reachable_source_ids": list_join(
                    [source["source_id"] for source in reachable_sources], 12
                ),
                "high_license_risk_source_ids": list_join(
                    [source["source_id"] for source in high_risk_sources], 8
                ),
                "jewish_christian_separation_required": bool(
                    packet.get("jewish_christian_separation_required")
                ),
                "reception_sensitive": bool(packet.get("reception_sensitive")),
                "ancient_culture_pressure": bool(packet.get("ancient_culture_pressure")),
                "textual_witness_pressure": bool(packet.get("textual_witness_pressure")),
                "cross_reference_three_division": bool(
                    dossier.get("cross_reference_three_division")
                ),
                "claim_controls": list_join(packet.get("claim_controls", []), 12),
                "authority_boundary": AUTHORITY_POLICY,
                "next_action": (
                    "Resolve missing/unreachable/high-risk source families, record source "
                    "approval decisions, then complete packet and release review."
                ),
            }
        )
    rows.sort(key=lambda row: (-float(row["source_authority_gap_score"]), row["ref"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_lane_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane in data["bibliography"].get("lane_rows", []):
        rows.append(
            {
                "lane": lane["lane"],
                "label": lane["label"],
                "evidence_score_pct": lane["evidence_score_pct"],
                "authority_score_pct": lane["authority_score_pct"],
                "present_source_count": lane["present_source_count"],
                "candidate_source_count": lane["candidate_source_count"],
                "generation_allowed_present_count": lane["generation_allowed_present_count"],
                "blocked_or_unsigned": lane["blocked_or_unsigned"],
                "source_ids": list_join(lane.get("source_ids", [])),
                "candidate_ids": list_join(lane.get("candidate_ids", [])),
                "blocking_gap": lane["blocking_gap"],
                "next_action": lane["next_action"],
            }
        )
    rows.sort(key=lambda row: (float(row["authority_score_pct"]), row["lane"]))
    return rows


def build_gate_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact_key, artifact_label in [
        ("source_acquisition", "Source Acquisition"),
        ("source_maturity", "Source Maturity"),
        ("bibliography", "Bibliography Provenance"),
        ("source_verification", "Source Verification"),
        ("review_workbook", "Review Signoff"),
    ]:
        for gate in data[artifact_key].get("gate_rows", []):
            rows.append(
                {
                    "artifact": artifact_label,
                    "gate": gate["gate"],
                    "score_pct": gate.get("score_pct", 0.0),
                    "status": gate.get("status", ""),
                    "evidence": gate.get("evidence", ""),
                    "next_action": gate.get("next_action", ""),
                }
            )
    if not rows:
        verification_summary = data["source_verification"]["summary"]
        rows.append(
            {
                "artifact": "Source Verification",
                "gate": "source_approval",
                "score_pct": pct(
                    verification_summary["source_approval_count"],
                    verification_summary["source_count"],
                ),
                "status": "blocked",
                "evidence": (
                    f"{verification_summary['source_approval_count']} of "
                    f"{verification_summary['source_count']} source rows are approved."
                ),
                "next_action": "Record license, provenance, and role-specific approval decisions.",
            }
        )
    return rows


def build_summary(
    unit_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    data: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    candidate_sources = [
        row for row in source_rows if row["source_class"] == "source_acquisition_candidate"
    ]
    review = data["review_workbook"]["summary"]
    verification = data["source_verification"]["summary"]
    top = unit_rows[0] if unit_rows else {}
    return {
        "unit_count": len(unit_rows),
        "critical_gap_unit_count": sum(
            1 for row in unit_rows if row["source_authority_gap_score"] >= 500
        ),
        "mean_source_authority_readiness_pct": mean(
            [float(row["source_authority_readiness_pct"]) for row in unit_rows]
        ),
        "source_family_count": len(family_rows),
        "family_without_candidate_count": sum(
            1 for row in family_rows if not row["candidate_count"]
        ),
        "family_without_reachable_candidate_count": sum(
            1
            for row in family_rows
            if row["candidate_count"] and not row["reachable_candidate_count"]
        ),
        "family_with_high_license_risk_count": sum(
            1 for row in family_rows if row["high_license_risk_candidate_count"]
        ),
        "candidate_source_count": len(candidate_sources),
        "candidate_reachable_count": sum(1 for row in candidate_sources if row["reachable"]),
        "candidate_machine_readable_count": sum(
            1 for row in candidate_sources if row["machine_readable"]
        ),
        "candidate_high_license_risk_count": sum(
            1 for row in candidate_sources if risk_rank(str(row["license_risk"])) >= 3
        ),
        "local_manifest_source_count": sum(
            1 for row in source_rows if row["source_class"] == "local_manifest"
        ),
        "source_approval_count": verification["source_approval_count"],
        "reachable_url_count": verification["reachable_url_count"],
        "reachable_url_pct": verification["reachable_url_pct"],
        "verification_gap_count": verification["gap_count"],
        "lane_count": len(lane_rows),
        "blocked_or_unsigned_lane_count": sum(1 for row in lane_rows if row["blocked_or_unsigned"]),
        "gate_count": len(gate_rows),
        "blocked_gate_count": sum(
            1
            for row in gate_rows
            if str(row.get("status", "")).lower() in {"blocked", "not_started"}
        ),
        "packet_review_row_count": review["packet_review_row_count"],
        "source_acquisition_review_row_count": review["source_acquisition_review_row_count"],
        "total_review_row_count": review["total_review_row_count"],
        "completed_review_row_count": review["completed_review_row_count"],
        "review_completion_pct": review["review_completion_pct"],
        "top_gap_unit": top.get("unit_id", ""),
        "top_gap_ref": top.get("ref", ""),
        "top_gap_score": top.get("source_authority_gap_score", 0.0),
        "top_gap_stage": top.get("evidence_ladder_stage", ""),
        "authority_verdict": (
            "Source evidence is strong enough to prioritize acquisition and review, but not "
            "authority: all high-risk units remain blocked by missing source approvals, "
            "unsigned packet reviews, and release signoff."
        ),
    }


def build_visual_data(
    unit_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    stage_counts = Counter(row["evidence_ladder_stage"] for row in unit_rows)
    license_counts = Counter(str(row["license_risk"]) for row in source_rows)
    status_counts = Counter(str(row["verification_status"]) for row in source_rows)
    return {
        "top_unit_gap_rows": [
            {"label": row["ref"], "value": row["source_authority_gap_score"]}
            for row in unit_rows[:20]
        ],
        "family_unit_rows": [
            {"label": row["label"], "value": row["unit_count"]} for row in family_rows
        ],
        "family_candidate_rows": [
            {"label": row["label"], "value": row["reachable_candidate_count"]}
            for row in family_rows
        ],
        "stage_rows": [
            {"label": label, "value": count} for label, count in stage_counts.most_common()
        ],
        "license_risk_rows": [
            {"label": label, "value": count} for label, count in license_counts.most_common()
        ],
        "verification_status_rows": [
            {"label": label, "value": count} for label, count in status_counts.most_common()
        ],
        "lane_authority_rows": [
            {"label": row["label"], "value": row["authority_score_pct"]} for row in lane_rows
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    source_rows = build_source_rows(data)
    family_rows = build_family_rows(data, source_rows)
    unit_rows = build_unit_rows(data, family_rows, source_rows)
    lane_rows = build_lane_rows(data)
    gate_rows = build_gate_rows(data)
    summary = build_summary(unit_rows, family_rows, source_rows, lane_rows, gate_rows, data)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "source authority ladder matrix generated; not source approval",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": AUTHORITY_POLICY,
        "summary": summary,
        "unit_rows": unit_rows,
        "family_rows": family_rows,
        "source_rows": source_rows,
        "lane_rows": lane_rows,
        "gate_rows": gate_rows,
        "visual_data": build_visual_data(unit_rows, family_rows, source_rows, lane_rows),
    }


def metric_cards(cards: list[tuple[str, Any, str]]) -> str:
    return "\n".join(
        f"""
        <article class="metric">
          <div class="metric-label">{esc(label)}</div>
          <div class="metric-value">{esc(value)}</div>
          <p>{esc(detail)}</p>
        </article>
        """
        for label, value, detail in cards
    )


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    color: str = "#2f6f73",
    limit: int = 18,
) -> str:
    rows = rows[:limit]
    if not rows:
        return "<p>No rows.</p>"
    max_value = max(float(row["value"]) for row in rows) or 1.0
    width = 920
    row_height = 28
    label_width = 330
    bar_width = width - label_width - 90
    height = 34 + len(rows) * row_height
    parts = [(f'<svg role="img" aria-label="horizontal bar chart" viewBox="0 0 {width} {height}">')]
    for index, row in enumerate(rows):
        y = 24 + index * row_height
        value = float(row["value"])
        bar = value / max_value * bar_width
        parts.append(
            f'<text x="0" y="{y + 14}" font-size="12" fill="#263238">{esc(row["label"])}</text>'
        )
        parts.append(
            f'<rect x="{label_width}" y="{y}" width="{bar:.1f}" height="18" '
            f'rx="3" fill="{color}"></rect>'
        )
        parts.append(
            f'<text x="{label_width + bar + 8:.1f}" y="{y + 14}" '
            f'font-size="12" fill="#263238">{value:.2f}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    unit_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['source_authority_gap_score']:.2f}",
            f"{row['source_authority_readiness_pct']:.2f}%",
            row["evidence_ladder_stage"],
            row["chief_blocker"],
            row["candidate_source_count"],
            row["reachable_candidate_source_count"],
            row["source_approval_count"],
            row["packet_review_row_count"],
            row["completed_review_row_count"],
            row["packet_families"],
        ]
        for row in report["unit_rows"][:30]
    ]
    family_rows = [
        [
            row["label"],
            row["unit_count"],
            row["candidate_count"],
            row["reachable_candidate_count"],
            row["machine_readable_candidate_count"],
            row["high_license_risk_candidate_count"],
            row["source_approval_count"],
            row["authority_blocker"],
            row["candidate_ids"],
        ]
        for row in report["family_rows"]
    ]
    source_rows = [
        [
            row["source_id"],
            row["source_class"],
            row["label"],
            row["license_risk"],
            "yes" if row["reachable"] else "no",
            row["verification_status"],
            "yes" if row["source_approved"] else "no",
            row["generation_policy"],
        ]
        for row in report["source_rows"]
    ]
    lane_rows = [
        [
            row["label"],
            f"{row['evidence_score_pct']:.2f}%",
            f"{row['authority_score_pct']:.2f}%",
            row["present_source_count"],
            row["candidate_source_count"],
            "yes" if row["blocked_or_unsigned"] else "no",
            row["blocking_gap"],
        ]
        for row in report["lane_rows"]
    ]
    gate_rows = [
        [
            row["artifact"],
            row["gate"],
            f"{float(row['score_pct']):.2f}%",
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in report["gate_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Source Authority Ladder Matrix</title>
  <style>
    body {{
      margin: 0;
      background: #f7f5ef;
      color: #263238;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }}
    header, main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    header {{ padding-top: 42px; }}
    h1 {{ margin: 0 0 8px; font-size: 32px; letter-spacing: 0; }}
    h2 {{ margin-top: 32px; font-size: 22px; letter-spacing: 0; }}
    p {{ line-height: 1.5; }}
    .warning {{
      border-left: 5px solid #9b3d3d;
      background: #fff8f2;
      padding: 14px 16px;
      margin: 18px 0;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 18px 0;
    }}
    .metric {{
      border: 1px solid #d7d1c2;
      background: #fff;
      border-radius: 8px;
      padding: 14px;
    }}
    .metric-label {{ font-size: 12px; text-transform: uppercase; color: #607d8b; }}
    .metric-value {{ font-size: 28px; font-weight: 700; margin-top: 6px; }}
    .metric p {{ margin: 6px 0 0; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: 1fr; gap: 16px; }}
    .chart {{
      overflow-x: auto;
      border: 1px solid #d7d1c2;
      background: #fff;
      border-radius: 8px;
      padding: 12px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 14px 0 24px;
      background: #fff;
      border: 1px solid #d7d1c2;
      font-size: 13px;
    }}
    th, td {{ border-bottom: 1px solid #e5dfd2; padding: 8px; vertical-align: top; }}
    th {{ text-align: left; background: #eee7d7; }}
    td {{ max-width: 360px; }}
  </style>
</head>
<body>
<header>
  <h1>Source Authority Ladder Matrix</h1>
  <p>
    Unit-level provenance and review-readiness controls for high-risk Hebrew-to-English
    Psalms translation claims. This is a source-critical report, not source approval.
  </p>
  <div class="warning">{esc(report["authority_policy"])}</div>
  <section class="metrics">
    {
        metric_cards(
            [
                ("Units", summary["unit_count"], "High-risk units with source packets."),
                (
                    "Critical Gaps",
                    summary["critical_gap_unit_count"],
                    "Units with source authority gap score >= 500.",
                ),
                (
                    "Mean Readiness",
                    f"{summary['mean_source_authority_readiness_pct']:.2f}%",
                    "Computed from reachability, risk, approvals, and review completion.",
                ),
                (
                    "Families",
                    summary["source_family_count"],
                    f"{summary['family_without_candidate_count']} lack candidates.",
                ),
                (
                    "Candidates",
                    summary["candidate_source_count"],
                    f"{summary['candidate_reachable_count']} reachable candidate sources.",
                ),
                (
                    "Approvals",
                    summary["source_approval_count"],
                    "Recorded source approvals across verified source rows.",
                ),
                (
                    "Review Rows",
                    summary["total_review_row_count"],
                    f"{summary['completed_review_row_count']} completed.",
                ),
                (
                    "Top Gap",
                    summary["top_gap_ref"],
                    f"Score {summary['top_gap_score']:.2f}; {summary['top_gap_stage']}.",
                ),
            ]
        )
    }
  </section>
</header>
<main>
  <section>
    <h2>Authority Gap Frontier</h2>
    <div class="grid">
      <div class="chart">{svg_horizontal_bars(visual["top_unit_gap_rows"], color="#9b3d3d")}</div>
      <div class="chart">{svg_horizontal_bars(visual["stage_rows"], color="#2f6f73")}</div>
      <div class="chart">{svg_horizontal_bars(visual["family_unit_rows"], color="#7c5b2f")}</div>
      <div class="chart">{svg_horizontal_bars(visual["license_risk_rows"], color="#9b3d3d")}</div>
    </div>
    {
        table(
            [
                "Rank",
                "Ref",
                "Gap Score",
                "Readiness",
                "Stage",
                "Chief Blocker",
                "Candidates",
                "Reachable",
                "Approvals",
                "Review Rows",
                "Completed",
                "Families",
            ],
            unit_rows,
        )
    }
  </section>
  <section>
    <h2>Source Families</h2>
    {
        table(
            [
                "Family",
                "Units",
                "Candidates",
                "Reachable",
                "Machine",
                "High Risk",
                "Approvals",
                "Blocker",
                "Candidate IDs",
            ],
            family_rows,
        )
    }
  </section>
  <section>
    <h2>Verified And Candidate Sources</h2>
    <div class="chart">{
        svg_horizontal_bars(visual["verification_status_rows"], color="#2f6f73")
    }</div>
    {
        table(
            [
                "Source ID",
                "Class",
                "Label",
                "License Risk",
                "Reachable",
                "Verification",
                "Approved",
                "Generation Policy",
            ],
            source_rows,
        )
    }
  </section>
  <section>
    <h2>Lane And Gate Controls</h2>
    <div class="chart">{svg_horizontal_bars(visual["lane_authority_rows"], color="#7c5b2f")}</div>
    {
        table(
            [
                "Lane",
                "Evidence",
                "Authority",
                "Present",
                "Candidates",
                "Blocked",
                "Gap",
            ],
            lane_rows,
        )
    }
    {table(["Artifact", "Gate", "Score", "Status", "Evidence", "Next Action"], gate_rows)}
  </section>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate source authority ladder matrix.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--family-csv-output", type=Path, default=DEFAULT_FAMILY_CSV_OUTPUT)
    parser.add_argument("--source-csv-output", type=Path, default=DEFAULT_SOURCE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.family_csv_output, report["family_rows"])
    write_csv(args.source_csv_output, report["source_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.family_csv_output}")
    print(f"Wrote {args.source_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
