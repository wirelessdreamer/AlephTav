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

SOURCE_MATURITY_PATH = REPORT_ROOT / "scholarly_source_maturity_report.json"
SOURCE_ACQUISITION_PATH = REPORT_ROOT / "contextual_source_acquisition_plan.json"
SOURCE_PACKET_PATH = REPORT_ROOT / "contextual_source_packet_roadmap.json"
REVIEW_WORKBOOK_PATH = REPORT_ROOT / "contextual_review_signoff_workbook.json"
CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
AUTHORITY_PATH = REPORT_ROOT / "scholarly_authority_readiness.json"
SOURCE_VERIFICATION_PATH = REPORT_ROOT / "doctoral_source_verification.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "doctoral_bibliography_provenance.json"
DEFAULT_BIBLIOGRAPHY_CSV_OUTPUT = REPORT_ROOT / "doctoral_bibliography_sources.csv"
DEFAULT_LANE_CSV_OUTPUT = REPORT_ROOT / "doctoral_bibliography_lanes.csv"
DEFAULT_FAMILY_CSV_OUTPUT = REPORT_ROOT / "doctoral_bibliography_source_families.csv"
DEFAULT_GAP_CSV_OUTPUT = REPORT_ROOT / "doctoral_bibliography_gaps.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "doctoral_bibliography_provenance.html"

SOURCE_FAMILY_TO_LANES = {
    "academic_critical_comparison": ["academic_comparison"],
    "ancient_near_eastern_context": ["ancient_cultural_context"],
    "christian_reception_sources": ["christian_reception"],
    "divine_name_title_policy": [
        "hebrew_source_corpus",
        "ancient_cultural_context",
        "academic_comparison",
    ],
    "hebrew_source_tokens": ["hebrew_source_corpus", "psalm_morphology_lexeme"],
    "human_release_signoff": ["human_review_signoff"],
    "jewish_reception_sources": ["jewish_reception"],
    "morphology_lexeme": ["psalm_morphology_lexeme", "whole_tanakh_context"],
    "poetic_genre_form": ["ancient_cultural_context", "academic_comparison"],
    "textual_witness_variants": ["textual_witnesses"],
    "whole_tanakh_lemma_context": ["whole_tanakh_context"],
}

SOURCE_FAMILY_TO_TIER = {
    "academic_critical_comparison": "academic_critical_comparison",
    "ancient_near_eastern_context": "ancient_cultural_context",
    "christian_reception_sources": "christian_reception",
    "divine_name_title_policy": "hebrew_policy_context",
    "hebrew_source_tokens": "primary_hebrew_basis",
    "human_release_signoff": "human_release_signoff",
    "jewish_reception_sources": "jewish_reception",
    "morphology_lexeme": "morphology_lexeme",
    "poetic_genre_form": "poetic_genre_form",
    "textual_witness_variants": "textual_witnesses",
    "whole_tanakh_lemma_context": "whole_tanakh_context",
}

SOURCE_ID_TO_TIER = {
    "asv": "english_witness",
    "kjv": "english_witness",
    "lxx": "textual_witnesses",
    "macula": "morphology_lexeme",
    "oshb": "morphology_lexeme",
    "sefaria": "restricted_english_witness",
    "uxlc": "primary_hebrew_basis",
    "web": "english_witness",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def maybe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_json(path)


def maybe_load_manifest(manifest_path: str) -> dict[str, Any]:
    if not manifest_path:
        return {}
    path = ROOT / manifest_path
    if not path.exists():
        return {}
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


def risk_rank(value: str) -> int:
    text = value.lower()
    if text in {"low", "public domain", "cc by 4.0"}:
        return 0
    if "medium" in text or "custom" in text:
        return 1
    if "high" in text or "restricted" in text or "noncommercial" in text:
        return 2
    if "per_text" in text:
        return 3
    return 1


def license_risk_label(value: str) -> str:
    text = value.lower()
    if not text:
        return "unknown"
    if "public domain" in text or "low" == text or "cc by 4.0" in text:
        return "low"
    if "noncommercial" in text or "high" in text:
        return "high"
    if "restricted" in text or "custom" in text:
        return "medium"
    if "per_text" in text:
        return "per_text"
    return "medium"


def acquisition_roles(candidate: dict[str, Any], family_roles: dict[str, list[str]]) -> list[str]:
    roles = {"license", "provenance", "release"}
    for family in candidate.get("source_families", []):
        roles.update(family_roles.get(str(family), []))
    risk = str(candidate.get("license_risk", ""))
    if "high" in risk or "per_text" in risk:
        roles.add("legal")
    return sorted(roles)


def family_roles(packet: dict[str, Any]) -> dict[str, list[str]]:
    return {
        str(row["source_family"]): list(row.get("review_roles", []))
        for row in packet.get("source_family_rows", [])
    }


def family_lookup(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["source_family"]): row
        for row in packet.get("source_family_rows", [])
        if row.get("source_family")
    }


def source_lane_lookup(source_maturity: dict[str, Any]) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    for lane in source_maturity.get("lane_rows", []):
        for source_id in lane.get("source_ids", []):
            lookup.setdefault(str(source_id), []).append(str(lane["lane"]))
    return lookup


def build_existing_source_rows(source_maturity: dict[str, Any]) -> list[dict[str, Any]]:
    source_lanes = source_lane_lookup(source_maturity)
    rows = []
    for source in source_maturity.get("source_rows", []):
        source_id = str(source["source_id"])
        manifest = maybe_load_manifest(str(source.get("manifest_path", "")))
        allowed_for_generation = bool(source.get("allowed_for_generation"))
        basis_role = str(source.get("basis_role") or "")
        tier = SOURCE_ID_TO_TIER.get(source_id, basis_role or "local_manifest")
        source_hierarchy_roles = source.get("source_hierarchy_roles", [])
        if "canonical_source" in source_hierarchy_roles:
            authority_status = "primary_translation_basis"
        elif basis_role == "english_witness":
            authority_status = "witness_only_not_generation_basis"
        elif "enrichment" in basis_role or source_hierarchy_roles:
            authority_status = "enrichment_requires_review"
        elif allowed_for_generation:
            authority_status = "generation_allowed_by_manifest"
        else:
            authority_status = "display_or_enrichment_only"

        rows.append(
            {
                "bibliography_id": f"local.{source_id}",
                "source_class": "local_manifest",
                "source_id": source_id,
                "label": source.get("name", source_id),
                "tier": tier,
                "language": source.get("language") or manifest.get("source_language", ""),
                "evidence_role": basis_role or "; ".join(source_hierarchy_roles),
                "license_or_access": source.get("license", ""),
                "license_risk": license_risk_label(str(source.get("license", ""))),
                "version": source.get("version", ""),
                "version_pinned": bool(source.get("version_pinned")),
                "machine_readable": True,
                "current_repo_status": "present_manifest",
                "acquisition_status": "already_present",
                "manifest_path": source.get("manifest_path", ""),
                "official_url": manifest.get("upstream_url", ""),
                "import_hash": manifest.get("import_hash", ""),
                "imported_at": manifest.get("imported_at", ""),
                "source_families": [],
                "used_in_lanes": source_lanes.get(source_id, source.get("used_in_lanes", [])),
                "allowed_for_generation": allowed_for_generation,
                "allowed_for_display": bool(source.get("allowed_for_display")),
                "allowed_for_export": bool(source.get("allowed_for_export")),
                "generation_policy": source.get("generation_policy", ""),
                "authority_status": authority_status,
                "reviewer_roles": [],
                "packet_unit_count": 0,
                "top_refs": [],
                "priority_score": 0.0,
                "authority_boundary": (
                    "Local manifest evidence still requires role-specific review before "
                    "canonical wording decisions."
                ),
            }
        )
    return rows


def build_candidate_source_rows(
    acquisition: dict[str, Any],
    packet: dict[str, Any],
) -> list[dict[str, Any]]:
    roles_by_family = family_roles(packet)
    rows = []
    for candidate in acquisition.get("candidate_rows", []):
        source_families = [str(family) for family in candidate.get("source_families", [])]
        lanes = sorted(
            {lane for family in source_families for lane in SOURCE_FAMILY_TO_LANES.get(family, [])}
        )
        tiers = sorted(
            {
                SOURCE_FAMILY_TO_TIER.get(family, "candidate_context_source")
                for family in source_families
            }
        )
        rows.append(
            {
                "bibliography_id": f"candidate.{candidate['candidate_id']}",
                "source_class": "source_acquisition_candidate",
                "source_id": candidate["candidate_id"],
                "label": candidate.get("label", candidate["candidate_id"]),
                "tier": "; ".join(tiers),
                "language": "",
                "evidence_role": candidate.get("evidence_role", ""),
                "license_or_access": candidate.get("license_or_access", ""),
                "license_risk": candidate.get("license_risk", "unknown"),
                "version": "",
                "version_pinned": False,
                "machine_readable": bool(candidate.get("machine_readable")),
                "current_repo_status": candidate.get("current_repo_status", ""),
                "acquisition_status": candidate.get("acquisition_status", ""),
                "manifest_path": "",
                "official_url": candidate.get("official_url", ""),
                "import_hash": "",
                "imported_at": "",
                "source_families": source_families,
                "used_in_lanes": lanes,
                "allowed_for_generation": False,
                "allowed_for_display": False,
                "allowed_for_export": False,
                "generation_policy": "candidate_not_generation_basis_until_manifested",
                "authority_status": "candidate_not_approved",
                "reviewer_roles": acquisition_roles(candidate, roles_by_family),
                "packet_unit_count": candidate.get("packet_unit_count", 0),
                "top_refs": candidate.get("top_refs", []),
                "priority_score": candidate.get("priority_score", 0.0),
                "authority_boundary": (
                    "Candidate evidence cannot be imported, displayed, or used for "
                    "generation until license, provenance, and release review pass."
                ),
            }
        )
    return rows


def candidates_by_lane(bibliography_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for row in bibliography_rows:
        if row["source_class"] != "source_acquisition_candidate":
            continue
        for lane in row.get("used_in_lanes", []):
            output.setdefault(str(lane), []).append(row)
    return output


def build_lane_rows(
    source_maturity: dict[str, Any],
    bibliography_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    present_by_id = {
        str(row["source_id"]): row
        for row in bibliography_rows
        if row["source_class"] == "local_manifest"
    }
    candidate_lookup = candidates_by_lane(bibliography_rows)
    rows = []
    for lane in source_maturity.get("lane_rows", []):
        lane_id = str(lane["lane"])
        source_ids = [str(source_id) for source_id in lane.get("source_ids", [])]
        present_rows = [
            present_by_id[source_id] for source_id in source_ids if source_id in present_by_id
        ]
        candidates = candidate_lookup.get(lane_id, [])
        rows.append(
            {
                "lane": lane_id,
                "label": lane["label"],
                "evidence_score_pct": lane["evidence_score_pct"],
                "authority_score_pct": lane["authority_score_pct"],
                "evidence_status": lane["evidence_status"],
                "authority_status": lane["authority_status"],
                "present_source_count": len(present_rows),
                "candidate_source_count": len(candidates),
                "generation_allowed_present_count": sum(
                    1 for row in present_rows if row["allowed_for_generation"]
                ),
                "blocked_or_unsigned": (
                    lane["authority_status"] == "blocked"
                    or not bool(lane.get("signed_source_synthesis"))
                ),
                "source_ids": source_ids,
                "candidate_ids": [row["source_id"] for row in candidates],
                "generation_policy": lane["generation_policy"],
                "reviewer_signoff_required": bool(lane["reviewer_signoff_required"]),
                "blocking_gap": lane["blocking_gap"],
                "next_action": lane["next_action"],
            }
        )
    return rows


def build_family_rows(
    packet: dict[str, Any],
    bibliography_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_rows = [
        row for row in bibliography_rows if row["source_class"] == "source_acquisition_candidate"
    ]
    candidates_by_family: dict[str, list[dict[str, Any]]] = {}
    for row in candidate_rows:
        for family in row.get("source_families", []):
            candidates_by_family.setdefault(str(family), []).append(row)

    rows = []
    for family in packet.get("source_family_rows", []):
        family_id = str(family["source_family"])
        candidates = candidates_by_family.get(family_id, [])
        best_license = "none"
        if candidates:
            best_license = sorted(candidates, key=lambda row: risk_rank(row["license_risk"]))[0][
                "license_risk"
            ]
        rows.append(
            {
                "source_family": family_id,
                "label": family["label"],
                "status": family["status"],
                "unit_count": family["unit_count"],
                "highest_priority_unit_count": family["highest_priority_unit_count"],
                "candidate_source_count": len(candidates),
                "machine_readable_candidate_count": sum(
                    1 for row in candidates if row["machine_readable"]
                ),
                "best_license_risk": best_license,
                "candidate_ids": [row["source_id"] for row in candidates],
                "review_roles": family.get("review_roles", []),
                "source_classes": family.get("source_classes", []),
                "required_artifacts": family.get("required_artifacts", []),
                "top_ref": family.get("top_ref", ""),
                "top_packet_priority_score": family.get("top_packet_priority_score", 0.0),
                "authority_boundary": family.get("authority_boundary", ""),
            }
        )
    return rows


def build_gap_rows(
    lane_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    review_workbook: dict[str, Any],
    authority: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for lane in lane_rows:
        if not lane["blocked_or_unsigned"] and float(lane["authority_score_pct"]) >= 70:
            continue
        rows.append(
            {
                "gap_id": f"lane.{lane['lane']}",
                "gap_type": "authority_lane",
                "severity": "hard" if lane["authority_status"] == "blocked" else "review",
                "label": lane["label"],
                "evidence": (
                    f"Authority {lane['authority_score_pct']:.2f}%; "
                    f"{lane['present_source_count']} present sources; "
                    f"{lane['candidate_source_count']} candidate sources."
                ),
                "blocking_gap": lane["blocking_gap"],
                "closing_sources": lane["candidate_ids"],
                "next_action": lane["next_action"],
            }
        )

    for family in family_rows:
        status = str(family["status"])
        if "blocked" not in status and "routing" not in status:
            continue
        rows.append(
            {
                "gap_id": f"family.{family['source_family']}",
                "gap_type": "source_family",
                "severity": "hard" if "blocked" in status else "routing",
                "label": family["label"],
                "evidence": (
                    f"{family['unit_count']} units; "
                    f"{family['candidate_source_count']} candidate sources; "
                    f"best license risk {family['best_license_risk']}."
                ),
                "blocking_gap": family["authority_boundary"],
                "closing_sources": family["candidate_ids"],
                "next_action": "Complete source packet artifacts and role-specific source review.",
            }
        )

    review_summary = review_workbook["summary"]
    rows.append(
        {
            "gap_id": "review.contextual_signoff_rows",
            "gap_type": "human_signoff",
            "severity": "critical",
            "label": "Contextual review rows",
            "evidence": (
                f"{fmt_int(review_summary['completed_review_row_count'])} of "
                f"{fmt_int(review_summary['total_review_row_count'])} rows completed; "
                f"{fmt_int(review_summary['blocked_gate_count'])} gates blocked."
            ),
            "blocking_gap": "Review workbook rows are templates, not approvals.",
            "closing_sources": [],
            "next_action": "Collect reviewer_id, decision, score, notes, and corrections.",
        }
    )
    rows.append(
        {
            "gap_id": "authority.release",
            "gap_type": "release_authority",
            "severity": "critical",
            "label": "Release authority",
            "evidence": (
                f"{fmt_int(authority['summary']['hard_blocker_count'])} hard blockers: "
                + ", ".join(authority["summary"]["hard_blockers"])
            ),
            "blocking_gap": (
                "Release authority is not established without signoff and audit records."
            ),
            "closing_sources": [],
            "next_action": "Keep model outputs as alternates until release gates pass.",
        }
    )
    return sorted(rows, key=lambda row: (row["severity"] != "critical", row["gap_id"]))


def build_method_rows() -> list[dict[str, Any]]:
    return [
        {
            "method_id": "M-01",
            "rule": "Hebrew token evidence is the only direct translation basis.",
            "allowed_use": "Translation wording, alignment rationale, lexical dispute control.",
            "forbidden_use": "Replacing Hebrew tokens with witness or reception wording.",
        },
        {
            "method_id": "M-02",
            "rule": "Whole-Tanakh surface evidence is broader context, not lemma proof.",
            "allowed_use": "Canonical resonance, review questions, source-packet routing.",
            "forbidden_use": "Unreviewed claims about lemma, sense, syntax, or discourse function.",
        },
        {
            "method_id": "M-03",
            "rule": "LXX and English witnesses remain labeled witnesses.",
            "allowed_use": "Variant pressure, reception history, comparison notes.",
            "forbidden_use": (
                "Silent correction of Hebrew source text or generation from English witnesses."
            ),
        },
        {
            "method_id": "M-04",
            "rule": "Jewish and Christian reception lanes must stay separate.",
            "allowed_use": "Tagged interpretation notes and reviewer adjudication.",
            "forbidden_use": "Blending reception viewpoints into the translation text.",
        },
        {
            "method_id": "M-05",
            "rule": "Local model output is proposal evidence.",
            "allowed_use": "Candidate wording, error discovery, cross-exam material.",
            "forbidden_use": "Authority claims without source anchors and human review.",
        },
        {
            "method_id": "M-06",
            "rule": "Source candidates are not local sources until manifested and reviewed.",
            "allowed_use": "Acquisition planning and reviewer queue prioritization.",
            "forbidden_use": "Import, display, export, or generation before license approval.",
        },
    ]


def build_visual_data(
    bibliography_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    source_class_counts = Counter(str(row["source_class"]) for row in bibliography_rows)
    license_counts = Counter(str(row["license_risk"]) for row in bibliography_rows)
    gap_counts = Counter(str(row["severity"]) for row in gap_rows)
    return {
        "source_class_counts": [
            {"source_class": key, "count": value}
            for key, value in source_class_counts.most_common()
        ],
        "license_risk_counts": [
            {"license_risk": key, "count": value} for key, value in license_counts.most_common()
        ],
        "lane_authority_rows": [
            {
                "lane": row["label"],
                "authority_score_pct": row["authority_score_pct"],
                "candidate_source_count": row["candidate_source_count"],
            }
            for row in lane_rows
        ],
        "source_family_unit_rows": [
            {
                "source_family": row["label"],
                "unit_count": row["unit_count"],
                "candidate_source_count": row["candidate_source_count"],
            }
            for row in family_rows
        ],
        "gap_severity_counts": [
            {"severity": key, "count": value} for key, value in gap_counts.most_common()
        ],
    }


def build_report() -> dict[str, Any]:
    source_maturity = load_json(SOURCE_MATURITY_PATH)
    source_acquisition = load_json(SOURCE_ACQUISITION_PATH)
    packet = load_json(SOURCE_PACKET_PATH)
    review_workbook = load_json(REVIEW_WORKBOOK_PATH)
    claim_matrix = load_json(CLAIM_MATRIX_PATH)
    authority = load_json(AUTHORITY_PATH)
    source_verification = maybe_load_json(SOURCE_VERIFICATION_PATH)

    existing_rows = build_existing_source_rows(source_maturity)
    candidate_rows = build_candidate_source_rows(source_acquisition, packet)
    bibliography_rows = sorted(
        existing_rows + candidate_rows,
        key=lambda row: (
            row["source_class"] != "local_manifest",
            row["tier"],
            -float(row["priority_score"]),
            row["label"],
        ),
    )
    lane_rows = build_lane_rows(source_maturity, bibliography_rows)
    family_rows = build_family_rows(packet, bibliography_rows)
    gap_rows = build_gap_rows(lane_rows, family_rows, review_workbook, authority)
    method_rows = build_method_rows()
    visual_data = build_visual_data(bibliography_rows, lane_rows, family_rows, gap_rows)

    local_rows = [row for row in bibliography_rows if row["source_class"] == "local_manifest"]
    candidates = [
        row for row in bibliography_rows if row["source_class"] == "source_acquisition_candidate"
    ]
    blocked_lanes = [row for row in lane_rows if row["authority_status"] == "blocked"]
    unsigned_lanes = [row for row in lane_rows if row["blocked_or_unsigned"]]
    low_risk_candidates = [row for row in candidates if risk_rank(row["license_risk"]) == 0]
    generation_allowed = [row for row in local_rows if row["allowed_for_generation"]]

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "doctoral bibliography provenance generated; not source approval",
        "source_paths": {
            "source_maturity": str(SOURCE_MATURITY_PATH.relative_to(ROOT)),
            "source_acquisition": str(SOURCE_ACQUISITION_PATH.relative_to(ROOT)),
            "source_packets": str(SOURCE_PACKET_PATH.relative_to(ROOT)),
            "review_workbook": str(REVIEW_WORKBOOK_PATH.relative_to(ROOT)),
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
            "authority": str(AUTHORITY_PATH.relative_to(ROOT)),
            "source_verification": str(SOURCE_VERIFICATION_PATH.relative_to(ROOT)),
        },
        "authority_boundary": {
            "source_boundary": "Bibliography rows are evidence routing, not approval.",
            "candidate_boundary": (
                "Candidate rows require manifest, license, provenance, and release review."
            ),
            "translation_boundary": (
                "Only Hebrew source-token evidence can directly govern wording."
            ),
        },
        "summary": {
            "bibliography_source_count": len(bibliography_rows),
            "local_manifest_source_count": len(local_rows),
            "candidate_source_count": len(candidates),
            "machine_readable_candidate_count": sum(
                1 for row in candidates if row["machine_readable"]
            ),
            "low_license_risk_candidate_count": len(low_risk_candidates),
            "generation_allowed_local_source_count": len(generation_allowed),
            "generation_blocked_local_source_count": sum(
                1 for row in local_rows if not row["allowed_for_generation"]
            ),
            "lane_count": len(lane_rows),
            "blocked_authority_lane_count": len(blocked_lanes),
            "unsigned_or_blocked_lane_count": len(unsigned_lanes),
            "source_family_count": len(family_rows),
            "source_family_with_candidate_count": sum(
                1 for row in family_rows if row["candidate_source_count"]
            ),
            "gap_count": len(gap_rows),
            "critical_gap_count": sum(1 for row in gap_rows if row["severity"] == "critical"),
            "method_boundary_count": len(method_rows),
            "review_completion_pct": review_workbook["summary"]["review_completion_pct"],
            "review_rows_total": review_workbook["summary"]["total_review_row_count"],
            "review_rows_completed": review_workbook["summary"]["completed_review_row_count"],
            "high_risk_claim_unit_count": claim_matrix["summary"]["high_risk_unit_count"],
            "jewish_christian_separation_unit_count": claim_matrix["summary"][
                "jewish_christian_separation_unit_count"
            ],
            "source_verification_source_count": source_verification.get("summary", {}).get(
                "source_count", 0
            ),
            "source_verification_reachable_url_count": source_verification.get("summary", {}).get(
                "reachable_url_count", 0
            ),
            "source_verification_reachable_url_pct": source_verification.get("summary", {}).get(
                "reachable_url_pct", 0.0
            ),
            "source_verification_gap_count": source_verification.get("summary", {}).get(
                "gap_count", 0
            ),
            "source_verification_source_approval_count": source_verification.get("summary", {}).get(
                "source_approval_count", 0
            ),
            "status": "bibliography_generated_not_source_approval",
        },
        "bibliography_rows": bibliography_rows,
        "lane_rows": lane_rows,
        "source_family_rows": family_rows,
        "gap_rows": gap_rows,
        "method_rows": method_rows,
        "visual_data": visual_data,
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


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


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


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    bibliography_rows = [
        [
            row["source_class"],
            row["source_id"],
            row["label"],
            row["tier"],
            row["license_risk"],
            row["current_repo_status"],
            row["authority_status"],
            row["official_url"],
        ]
        for row in report["bibliography_rows"]
    ]
    lane_rows = [
        [
            row["label"],
            f"{row['evidence_score_pct']:.2f}%",
            f"{row['authority_score_pct']:.2f}%",
            row["present_source_count"],
            row["candidate_source_count"],
            row["authority_status"],
            row["blocking_gap"],
        ]
        for row in report["lane_rows"]
    ]
    family_rows = [
        [
            row["label"],
            row["status"],
            row["unit_count"],
            row["candidate_source_count"],
            row["best_license_risk"],
            "; ".join(row["review_roles"]),
            row["authority_boundary"],
        ]
        for row in report["source_family_rows"]
    ]
    gap_rows = [
        [
            row["gap_id"],
            row["severity"],
            row["label"],
            row["evidence"],
            "; ".join(row["closing_sources"]),
            row["next_action"],
        ]
        for row in report["gap_rows"]
    ]
    method_rows = [
        [row["method_id"], row["rule"], row["allowed_use"], row["forbidden_use"]]
        for row in report["method_rows"]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Doctoral Bibliography and Provenance</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #53616f;
      --line: #c9d1d9;
      --panel: #f8fafc;
      --accent: #2868a8;
      --accent-2: #7c5b2f;
      --bad: #a12727;
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
      max-width: 980px;
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
      font-size: 1.75rem;
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
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(160px, 1.2fr) minmax(140px, 2fr) 86px;
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
      font-size: 0.88rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f4f7fa;
      color: var(--muted);
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
  <h1>Doctoral Bibliography and Provenance Apparatus</h1>
  <p class="lede">
    This report separates local manifested sources, external acquisition
    candidates, source-family coverage, reviewer roles, license posture, and
    authority boundaries for Hebrew-to-English Psalms translation assessment.
  </p>
  <div class="callout">
    <strong>Authority boundary:</strong>
    {esc(report["authority_boundary"]["source_boundary"])}
    {esc(report["authority_boundary"]["candidate_boundary"])}
  </div>

  <section class="metric-grid" aria-label="Bibliography metrics">
    {
        metric_cards(
            [
                (
                    "Bibliography Rows",
                    fmt_int(summary["bibliography_source_count"]),
                    f"{fmt_int(summary['local_manifest_source_count'])} local; "
                    f"{fmt_int(summary['candidate_source_count'])} candidates.",
                ),
                (
                    "Candidate Sources",
                    fmt_int(summary["candidate_source_count"]),
                    f"{fmt_int(summary['machine_readable_candidate_count'])} machine-readable.",
                ),
                (
                    "Low License Risk",
                    fmt_int(summary["low_license_risk_candidate_count"]),
                    "Candidate sources still require review.",
                ),
                (
                    "Blocked Lanes",
                    fmt_int(summary["blocked_authority_lane_count"]),
                    (
                        f"{fmt_int(summary['unsigned_or_blocked_lane_count'])} unsigned "
                        "or blocked lanes."
                    ),
                ),
                (
                    "Critical Gaps",
                    fmt_int(summary["critical_gap_count"]),
                    f"{fmt_int(summary['gap_count'])} total bibliography gaps.",
                ),
                (
                    "Verified URLs",
                    f"{summary['source_verification_reachable_url_pct']:.2f}%",
                    f"{fmt_int(summary['source_verification_reachable_url_count'])} "
                    "reachable official URLs.",
                ),
                (
                    "Verification Gaps",
                    fmt_int(summary["source_verification_gap_count"]),
                    "Live URL checks do not confer approval.",
                ),
                (
                    "Review Completion",
                    f"{summary['review_completion_pct']:.2f}%",
                    f"{fmt_int(summary['review_rows_completed'])} of "
                    f"{fmt_int(summary['review_rows_total'])} rows complete.",
                ),
            ]
        )
    }
  </section>

  <section>
    <h2>Visual Source Audit</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Lane Authority</h3>
        {
        bar_rows(
            visual["lane_authority_rows"],
            label_key="lane",
            value_key="authority_score_pct",
            max_value=100,
            suffix="%",
        )
    }
      </div>
      <div class="panel">
        <h3>Source Family Unit Reach</h3>
        {
        bar_rows(
            visual["source_family_unit_rows"], label_key="source_family", value_key="unit_count"
        )
    }
      </div>
      <div class="panel">
        <h3>License Risk</h3>
        {bar_rows(visual["license_risk_counts"], label_key="license_risk", value_key="count")}
      </div>
      <div class="panel">
        <h3>Gap Severity</h3>
        {bar_rows(visual["gap_severity_counts"], label_key="severity", value_key="count")}
      </div>
    </div>
  </section>

  <section>
    <h2>Method Boundaries</h2>
    {table(["ID", "Rule", "Allowed Use", "Forbidden Use"], method_rows)}
  </section>

  <section>
    <h2>Source Lanes</h2>
    {table(["Lane", "Evidence", "Authority", "Present", "Candidates", "Status", "Gap"], lane_rows)}
  </section>

  <section>
    <h2>Bibliography Rows</h2>
    {
        table(
            ["Class", "ID", "Label", "Tier", "License Risk", "Repo Status", "Authority", "URL"],
            bibliography_rows,
        )
    }
  </section>

  <section>
    <h2>Source Families</h2>
    {
        table(
            ["Family", "Status", "Units", "Candidates", "Best Risk", "Roles", "Boundary"],
            family_rows,
        )
    }
  </section>

  <section>
    <h2>Bibliography Gaps</h2>
    {table(["ID", "Severity", "Label", "Evidence", "Closing Sources", "Next Action"], gap_rows)}
  </section>

  <footer>
    Generated {esc(report["generated_on"])} from current local reports and
    read-only source manifests. This report does not approve, download, or alter
    any source.
  </footer>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the doctoral bibliography and provenance apparatus."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument(
        "--bibliography-csv-output",
        type=Path,
        default=DEFAULT_BIBLIOGRAPHY_CSV_OUTPUT,
    )
    parser.add_argument("--lane-csv-output", type=Path, default=DEFAULT_LANE_CSV_OUTPUT)
    parser.add_argument("--family-csv-output", type=Path, default=DEFAULT_FAMILY_CSV_OUTPUT)
    parser.add_argument("--gap-csv-output", type=Path, default=DEFAULT_GAP_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.bibliography_csv_output, report["bibliography_rows"])
    write_csv(args.lane_csv_output, report["lane_rows"])
    write_csv(args.family_csv_output, report["source_family_rows"])
    write_csv(args.gap_csv_output, report["gap_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")


if __name__ == "__main__":
    main()
