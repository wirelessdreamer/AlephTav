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
    "contextual_review_signoff": REPORT_ROOT / "contextual_review_signoff_workbook.json",
    "source_authority_ladder": REPORT_ROOT / "source_authority_ladder_matrix.json",
    "translation_accuracy_certification": (
        REPORT_ROOT / "translation_accuracy_certification_matrix.json"
    ),
    "model_training_certification": REPORT_ROOT / "model_training_certification_roadmap.json",
    "authority_critical_path": REPORT_ROOT / "authority_critical_path_report.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "critical_unit_review_execution_plan.json"
DEFAULT_ROLE_CSV_OUTPUT = REPORT_ROOT / "critical_unit_review_execution_plan_roles.csv"
DEFAULT_WAVE_CSV_OUTPUT = REPORT_ROOT / "critical_unit_review_execution_plan_waves.csv"
DEFAULT_UNIT_ROLE_CSV_OUTPUT = REPORT_ROOT / "critical_unit_review_execution_plan_unit_roles.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "critical_unit_review_execution_plan_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "critical_unit_review_execution_plan.html"

AUTHORITY_POLICY = (
    "The critical unit review execution plan is a workload and signoff-routing artifact. "
    "It does not assign real reviewers, approve source use, decide interpretations, certify "
    "model output, authorize wording, or release canonical translation text."
)

ROLE_WAVES = {
    "Hebrew": "WAVE-03",
    "lexical": "WAVE-03",
    "alignment": "WAVE-03",
    "theology": "WAVE-04",
    "lyric": "WAVE-04",
    "release": "WAVE-06",
}

LANE_ROLE_MAP = {
    "source_approval": ["Hebrew", "lexical", "release"],
    "whole_tanakh_morphology": ["Hebrew", "lexical", "alignment"],
    "semantic_referent": ["Hebrew", "lexical", "alignment"],
    "jewish_christian": ["theology", "Hebrew"],
    "textual_witness": ["Hebrew", "alignment"],
    "model_evidence": ["Hebrew", "alignment", "theology"],
    "human_signoff": ["Hebrew", "lexical", "alignment", "theology", "release"],
    "release_authority": ["release"],
}

ROLE_CLAIM_FAMILIES = {
    "Hebrew": {
        "hebrew_basis",
        "whole_tanakh_context",
        "semantic_referent",
        "textual_witness",
        "divine_name_policy",
        "academic_comparison",
        "ancient_culture",
    },
    "lexical": {
        "hebrew_basis",
        "whole_tanakh_context",
        "semantic_referent",
        "ancient_culture",
    },
    "alignment": {
        "hebrew_basis",
        "whole_tanakh_context",
        "semantic_referent",
        "textual_witness",
        "model_evidence",
    },
    "theology": {
        "jewish_reception",
        "christian_reception",
        "divine_name_policy",
        "academic_comparison",
        "release_authority",
    },
    "lyric": {
        "poetic_rhetorical",
        "ancient_culture",
    },
    "release": {
        "release_authority",
        "model_evidence",
        "translation_text_authority",
    },
}

ROLE_NEXT_ACTIONS = {
    "Hebrew": (
        "Assign Hebrew reviewers to verify source-basis, morphology, witness, and "
        "semantic/referent decisions for every critical unit."
    ),
    "lexical": (
        "Resolve lexeme, Strong, whole-Tanakh, semantic-role, and referent questions "
        "before any wording claim moves toward release."
    ),
    "alignment": (
        "Verify token-to-rendering alignment and source anchoring for human and model "
        "outputs before accepting any candidate rendering."
    ),
    "theology": (
        "Separate Jewish, Christian, and academic reception claims into labeled decisions "
        "and prevent unsigned reception claims from entering translation text."
    ),
    "lyric": (
        "Review poetic and rhetorical pressure only after Hebrew and semantic controls "
        "are stable enough to prevent style-driven semantic drift."
    ),
    "release": (
        "Confirm all source, reviewer, model, alignment, and canonical-change gates before "
        "any unit receives release authority."
    ),
}

WAVE_DEFINITIONS = [
    {
        "wave_id": "WAVE-01",
        "wave": "Reviewer identity and authority boundary freeze",
        "depends_on": "",
        "lane_ids": ["human_signoff"],
        "roles": ["Hebrew", "lexical", "alignment", "theology", "lyric", "release"],
        "next_action": (
            "Record reviewer identities, role qualifications, authority boundaries, and "
            "decision rubric before evaluating content."
        ),
    },
    {
        "wave_id": "WAVE-02",
        "wave": "Source license, provenance, and family approval",
        "depends_on": "WAVE-01",
        "lane_ids": ["source_approval"],
        "roles": ["Hebrew", "lexical", "release"],
        "next_action": (
            "Approve or reject source-family use and license posture before importing or "
            "using evidence as translation authority."
        ),
    },
    {
        "wave_id": "WAVE-03",
        "wave": "Hebrew, morphology, semantic, referent, and alignment adjudication",
        "depends_on": "WAVE-02",
        "lane_ids": ["whole_tanakh_morphology", "semantic_referent"],
        "roles": ["Hebrew", "lexical", "alignment"],
        "next_action": (
            "Adjudicate token evidence, morphology gaps, semantic roles, referents, and "
            "alignment before comparing interpretive traditions."
        ),
    },
    {
        "wave_id": "WAVE-04",
        "wave": "Witness, ancient culture, poetic, and Jewish/Christian split review",
        "depends_on": "WAVE-03",
        "lane_ids": ["textual_witness", "jewish_christian"],
        "roles": ["Hebrew", "alignment", "theology", "lyric"],
        "next_action": (
            "Review witnesses, cultural context, poetic pressure, and separated Jewish and "
            "Christian lanes without allowing them to override Hebrew evidence silently."
        ),
    },
    {
        "wave_id": "WAVE-05",
        "wave": "Model evidence, cross-exam, and benchmark review",
        "depends_on": "WAVE-03; WAVE-04",
        "lane_ids": ["model_evidence"],
        "roles": ["Hebrew", "alignment", "theology"],
        "next_action": (
            "Run scaled local-model and cross-exam rows, then review source anchoring, "
            "schema validity, and contextual fidelity before accepting model evidence."
        ),
    },
    {
        "wave_id": "WAVE-06",
        "wave": "Human signoff, canonical-change approval, and release gate",
        "depends_on": "WAVE-01; WAVE-02; WAVE-03; WAVE-04; WAVE-05",
        "lane_ids": ["human_signoff", "release_authority"],
        "roles": ["Hebrew", "lexical", "alignment", "theology", "release"],
        "next_action": (
            "Require signed reviewer decisions, canonical-change approvals, and release "
            "review before authorizing translation text."
        ),
    },
]


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


def lane_rows_by_unit(lane_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lane_rows:
        grouped[str(row["unit_id"])].append(row)
    return grouped


def claim_rows_by_unit(claim_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in claim_rows:
        grouped[str(row["unit_id"])].append(row)
    return grouped


def packet_rows_by_unit_role(
    packet_rows: list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in packet_rows:
        grouped[(str(row["unit_id"]), str(row["reviewer_role"]))].append(row)
    return grouped


def blocked_lane_count_for_role(lanes: list[dict[str, Any]], role: str) -> int:
    return sum(
        1
        for lane in lanes
        if lane.get("status") == "blocked" and role in LANE_ROLE_MAP.get(str(lane["lane_id"]), [])
    )


def claim_gate_count_for_role(claims: list[dict[str, Any]], role: str) -> int:
    families = ROLE_CLAIM_FAMILIES.get(role, set())
    return sum(
        int(claim.get("blocking_gate_count", 0))
        for claim in claims
        if str(claim.get("family_id")) in families
    )


def build_unit_role_rows(
    critical_units: list[dict[str, Any]],
    critical_packet_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    claim_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    packet_lookup = packet_rows_by_unit_role(critical_packet_rows)
    lane_lookup = lane_rows_by_unit(lane_rows)
    claim_lookup = claim_rows_by_unit(claim_rows)
    rows: list[dict[str, Any]] = []
    for unit in critical_units:
        unit_id = str(unit["unit_id"])
        roles = sorted(str(role) for role in as_list(unit.get("required_review_roles")))
        if "release" not in roles:
            roles.append("release")
        for role in roles:
            packets = packet_lookup.get((unit_id, role), [])
            blocked_lanes = blocked_lane_count_for_role(lane_lookup.get(unit_id, []), role)
            claim_gate_count = claim_gate_count_for_role(claim_lookup.get(unit_id, []), role)
            completed_rows = sum(1 for row in packets if row.get("status") == "completed")
            packet_review_count = len(packets)
            rows.append(
                {
                    "unit_id": unit_id,
                    "ref": unit["ref"],
                    "reviewer_role": role,
                    "wave_id": ROLE_WAVES.get(role, "WAVE-04"),
                    "decision_pressure_score": unit["decision_pressure_score"],
                    "decision_pressure_band": unit["decision_pressure_band"],
                    "packet_review_row_count": packet_review_count,
                    "completed_packet_review_row_count": completed_rows,
                    "blocked_lane_count": blocked_lanes,
                    "claim_blocking_gate_count": claim_gate_count,
                    "jewish_christian_separation_required": unit[
                        "jewish_christian_separation_required"
                    ],
                    "textual_witness_pressure": unit["textual_witness_pressure"],
                    "ancient_culture_pressure": unit["ancient_culture_pressure"],
                    "status": "blocked" if blocked_lanes or claim_gate_count else "pending",
                    "next_action": ROLE_NEXT_ACTIONS.get(
                        role, "Assign reviewer and record decision."
                    ),
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            -float(row["decision_pressure_score"]),
            str(row["ref"]),
            str(row["reviewer_role"]),
        ),
    )


def build_role_rows(
    unit_role_rows: list[dict[str, Any]],
    critical_packet_rows: list[dict[str, Any]],
    source_acquisition_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    roles = sorted(
        {
            str(row["reviewer_role"])
            for row in unit_role_rows + critical_packet_rows + source_acquisition_rows
        }
    )
    rows: list[dict[str, Any]] = []
    for role in roles:
        role_unit_rows = [row for row in unit_role_rows if row["reviewer_role"] == role]
        role_packet_rows = [row for row in critical_packet_rows if row["reviewer_role"] == role]
        source_rows = [row for row in source_acquisition_rows if row["reviewer_role"] == role]
        completed_packet_rows = sum(
            1 for row in role_packet_rows if row.get("status") == "completed"
        )
        total_rows = len(role_packet_rows) + len(source_rows)
        completed_rows = completed_packet_rows + sum(
            1 for row in source_rows if row.get("status") == "completed"
        )
        top_unit = max(
            role_unit_rows,
            key=lambda row: float(row["decision_pressure_score"]),
            default={},
        )
        rows.append(
            {
                "reviewer_role": role,
                "wave_id": ROLE_WAVES.get(role, "WAVE-04"),
                "critical_unit_assignment_count": len({row["unit_id"] for row in role_unit_rows}),
                "unit_role_assignment_count": len(role_unit_rows),
                "critical_packet_review_row_count": len(role_packet_rows),
                "source_acquisition_review_row_count": len(source_rows),
                "total_review_row_count": total_rows,
                "completed_review_row_count": completed_rows,
                "completion_pct": pct(completed_rows, total_rows),
                "blocked_lane_count": sum(int(row["blocked_lane_count"]) for row in role_unit_rows),
                "claim_blocking_gate_count": sum(
                    int(row["claim_blocking_gate_count"]) for row in role_unit_rows
                ),
                "top_ref": top_unit.get("ref", ""),
                "top_decision_pressure_score": top_unit.get("decision_pressure_score", 0.0),
                "status": "blocked" if completed_rows < total_rows else "completed",
                "next_action": ROLE_NEXT_ACTIONS.get(role, "Assign reviewer and record decision."),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -int(row["total_review_row_count"]),
            -int(row["blocked_lane_count"]),
            str(row["reviewer_role"]),
        ),
    )


def build_lane_dependency_rows(lane_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lane_summary: dict[str, dict[str, Any]] = {}
    for lane in lane_rows:
        lane_id = str(lane["lane_id"])
        if lane_id not in lane_summary:
            lane_summary[lane_id] = {
                "lane_id": lane_id,
                "lane_label": lane["lane_label"],
                "status_counts": Counter(),
                "unit_count": 0,
                "wave_id": "",
                "responsible_roles": LANE_ROLE_MAP.get(lane_id, []),
            }
        lane_summary[lane_id]["status_counts"][str(lane["status"])] += 1
        lane_summary[lane_id]["unit_count"] += 1
    for summary in lane_summary.values():
        wave = next(
            (
                wave["wave_id"]
                for wave in WAVE_DEFINITIONS
                if summary["lane_id"] in wave["lane_ids"]
            ),
            "WAVE-04",
        )
        status_counts = summary.pop("status_counts")
        summary["wave_id"] = wave
        summary["blocked_unit_count"] = status_counts.get("blocked", 0)
        summary["review_required_unit_count"] = status_counts.get("review_required", 0)
        summary["pass_or_ready_unit_count"] = sum(
            count
            for status, count in status_counts.items()
            if status not in {"blocked", "review_required"}
        )
        summary["status"] = (
            "blocked"
            if summary["blocked_unit_count"]
            else "review_required"
            if summary["review_required_unit_count"]
            else "ready"
        )
        summary["next_action"] = next(
            (
                wave["next_action"]
                for wave in WAVE_DEFINITIONS
                if wave["wave_id"] == summary["wave_id"]
            ),
            "Record reviewer decision.",
        )
    return sorted(
        lane_summary.values(),
        key=lambda row: (-int(row["blocked_unit_count"]), str(row["lane_id"])),
    )


def build_wave_rows(
    unit_role_rows: list[dict[str, Any]],
    lane_dependency_rows: list[dict[str, Any]],
    claim_rows: list[dict[str, Any]],
    model_training: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    claims_by_family = Counter(str(row["family_id"]) for row in claim_rows)
    for wave in WAVE_DEFINITIONS:
        wave_roles = set(wave["roles"])
        wave_lanes = set(wave["lane_ids"])
        role_rows = [row for row in unit_role_rows if row["reviewer_role"] in wave_roles]
        lane_rows = [row for row in lane_dependency_rows if row["lane_id"] in wave_lanes]
        completed = sum(int(row["completed_packet_review_row_count"]) for row in role_rows)
        packet_rows = sum(int(row["packet_review_row_count"]) for row in role_rows)
        blocked_lanes = sum(int(row["blocked_unit_count"]) for row in lane_rows)
        claim_gate_count = sum(int(row["claim_blocking_gate_count"]) for row in role_rows)
        if wave["wave_id"] == "WAVE-05":
            packet_rows += int(model_training["projected_model_human_review_rows"])
        if wave["wave_id"] == "WAVE-06":
            release_claims = claims_by_family.get("release_authority", 0)
            claim_gate_count += release_claims
        rows.append(
            {
                "wave_id": wave["wave_id"],
                "wave": wave["wave"],
                "depends_on": wave["depends_on"],
                "responsible_roles": wave["roles"],
                "unit_count": len({row["unit_id"] for row in role_rows}),
                "packet_or_projected_review_row_count": packet_rows,
                "completed_review_row_count": completed,
                "completion_pct": pct(completed, packet_rows),
                "blocked_lane_count": blocked_lanes,
                "claim_blocking_gate_count": claim_gate_count,
                "status": "blocked" if blocked_lanes or completed < packet_rows else "completed",
                "next_action": wave["next_action"],
            }
        )
    return rows


def build_gate_rows(
    critical_units: list[dict[str, Any]],
    role_rows: list[dict[str, Any]],
    lane_dependency_rows: list[dict[str, Any]],
    review_summary: dict[str, Any],
    accuracy_summary: dict[str, Any],
    model_training: dict[str, Any],
) -> list[dict[str, Any]]:
    lane_lookup = {row["lane_id"]: row for row in lane_dependency_rows}
    total_role_rows = sum(int(row["total_review_row_count"]) for row in role_rows)
    completed_role_rows = sum(int(row["completed_review_row_count"]) for row in role_rows)
    source_blocked = int(lane_lookup.get("source_approval", {}).get("blocked_unit_count", 0))
    morph_blocked = int(lane_lookup.get("whole_tanakh_morphology", {}).get("blocked_unit_count", 0))
    semantic_blocked = int(lane_lookup.get("semantic_referent", {}).get("blocked_unit_count", 0))
    reception_blocked = int(lane_lookup.get("jewish_christian", {}).get("blocked_unit_count", 0))
    model_blocked = int(lane_lookup.get("model_evidence", {}).get("blocked_unit_count", 0))
    release_blocked = int(lane_lookup.get("release_authority", {}).get("blocked_unit_count", 0))
    return [
        {
            "gate_id": "REV-GATE-01",
            "gate": "Reviewer identities and qualifications recorded",
            "status": "blocked",
            "current_value": "0 completed critical-unit review rows",
            "target_value": f"{total_role_rows} role/source rows assigned and auditable",
            "blocking_gap": "Reviewer IDs, decisions, scores, and notes are empty.",
            "next_action": "Assign named reviewers by role before content decisions are accepted.",
        },
        {
            "gate_id": "REV-GATE-02",
            "gate": "Source approval before translation-text authority",
            "status": "blocked",
            "current_value": f"{source_blocked} critical units with source approval blocked",
            "target_value": "0 source-approval lane blockers",
            "blocking_gap": "Source-family approval and license/provenance decisions are missing.",
            "next_action": "Complete source acquisition and source-family decisions first.",
        },
        {
            "gate_id": "REV-GATE-03",
            "gate": "Hebrew morphology and semantic/referent adjudication",
            "status": "blocked",
            "current_value": f"{morph_blocked + semantic_blocked} morphology/semantic blockers",
            "target_value": "0 morphology or semantic/referent blockers",
            "blocking_gap": (
                "Whole-Tanakh morphology and semantic/referent enrichment are not complete."
            ),
            "next_action": (
                "Clear Hebrew, lexical, and alignment decisions before reception review."
            ),
        },
        {
            "gate_id": "REV-GATE-04",
            "gate": "Jewish/Christian, witness, culture, and poetic review separated",
            "status": "blocked",
            "current_value": f"{reception_blocked} separated reception blockers",
            "target_value": "0 unsigned split-lane reception blockers",
            "blocking_gap": "Jewish, Christian, witness, culture, and poetic lanes are not signed.",
            "next_action": (
                "Keep tradition claims labeled until theology and Hebrew review sign off."
            ),
        },
        {
            "gate_id": "REV-GATE-05",
            "gate": "Model evidence reviewed under source-anchor controls",
            "status": "blocked",
            "current_value": (
                f"{model_blocked} model-evidence lane blockers; "
                f"{model_training['valid_model_task_coverage_pct']:.2f}% model-task coverage"
            ),
            "target_value": "Scaled benchmark coverage with signed human/model cross-exam review",
            "blocking_gap": "Real model evidence is sparse and not reviewer-approved.",
            "next_action": (
                "Run scaled bakeoff and cross-exam rows before model certification claims."
            ),
        },
        {
            "gate_id": "REV-GATE-06",
            "gate": "Release authorization after all upstream gates pass",
            "status": "blocked",
            "current_value": (
                f"{release_blocked} release blockers; "
                f"{completed_role_rows}/{total_role_rows} role/source rows complete; "
                f"{accuracy_summary['release_authorized_dimension_count']} release-authorized "
                "accuracy dimensions"
            ),
            "target_value": (
                f"{len(critical_units)} critical units with source, review, model, claim, and "
                "release signoff"
            ),
            "blocking_gap": (
                "Human signoff, canonical-change approvals, and release reviewer decisions "
                "are not complete."
            ),
            "next_action": "Do not promote critical-unit wording to release authority yet.",
        },
    ]


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    dossier = data["critical_unit_decision_dossier"]
    review = data["contextual_review_signoff"]
    source_ladder = data["source_authority_ladder"]
    accuracy = data["translation_accuracy_certification"]
    model_training = data["model_training_certification"]["summary"]
    authority_path = data["authority_critical_path"]["summary"]

    critical_units = dossier["unit_rows"]
    critical_unit_ids = {str(row["unit_id"]) for row in critical_units}
    critical_packet_rows = [
        row for row in review["packet_review_rows"] if str(row["unit_id"]) in critical_unit_ids
    ]
    source_acquisition_rows = review["source_acquisition_review_rows"]
    lane_rows = dossier["lane_rows"]
    claim_rows = dossier["claim_rows"]

    unit_role_rows = build_unit_role_rows(
        critical_units,
        critical_packet_rows,
        lane_rows,
        claim_rows,
    )
    role_rows = build_role_rows(unit_role_rows, critical_packet_rows, source_acquisition_rows)
    lane_dependency = build_lane_dependency_rows(lane_rows)
    wave_rows = build_wave_rows(unit_role_rows, lane_dependency, claim_rows, model_training)
    gate_rows = build_gate_rows(
        critical_units,
        role_rows,
        lane_dependency,
        review["summary"],
        accuracy["summary"],
        model_training,
    )

    top_role = role_rows[0] if role_rows else {}
    top_wave = max(
        wave_rows,
        key=lambda row: int(row["packet_or_projected_review_row_count"]),
        default={},
    )
    blocked_gate_count = sum(1 for row in gate_rows if row["status"] == "blocked")
    total_review_rows = sum(int(row["total_review_row_count"]) for row in role_rows)
    completed_review_rows = sum(int(row["completed_review_row_count"]) for row in role_rows)
    total_unit_role_assignments = len(unit_role_rows)
    blocked_unit_role_assignments = sum(1 for row in unit_role_rows if row["status"] == "blocked")

    role_visual_rows = [
        {
            "label": row["reviewer_role"],
            "value": row["total_review_row_count"],
        }
        for row in role_rows
    ]
    wave_visual_rows = [
        {
            "label": row["wave_id"],
            "value": row["packet_or_projected_review_row_count"],
        }
        for row in wave_rows
    ]
    lane_visual_rows = [
        {
            "label": row["lane_label"],
            "value": row["blocked_unit_count"],
        }
        for row in lane_dependency
    ]
    unit_visual_rows = [
        {
            "label": row["ref"],
            "value": row["decision_pressure_score"],
        }
        for row in critical_units[:20]
    ]

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "critical_unit_review_execution_plan_generated_not_assigned",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": AUTHORITY_POLICY,
        "summary": {
            "critical_unit_count": len(critical_units),
            "critical_packet_review_row_count": len(critical_packet_rows),
            "source_acquisition_review_row_count": len(source_acquisition_rows),
            "total_role_review_row_count": total_review_rows,
            "completed_role_review_row_count": completed_review_rows,
            "review_completion_pct": pct(completed_review_rows, total_review_rows),
            "reviewer_role_count": len(role_rows),
            "unit_role_assignment_count": total_unit_role_assignments,
            "blocked_unit_role_assignment_count": blocked_unit_role_assignments,
            "wave_count": len(wave_rows),
            "blocked_wave_count": sum(1 for row in wave_rows if row["status"] == "blocked"),
            "gate_count": len(gate_rows),
            "blocked_gate_count": blocked_gate_count,
            "blocked_decision_lane_count": dossier["summary"]["blocked_lane_row_count"],
            "text_blocked_unit_count": dossier["summary"]["text_blocked_unit_count"],
            "clean_model_evidence_unit_count": dossier["summary"][
                "clean_model_evidence_unit_count"
            ],
            "jewish_christian_separation_unit_count": dossier["summary"][
                "jewish_christian_separation_unit_count"
            ],
            "source_authority_mean_unit_score_pct": source_ladder["summary"][
                "mean_source_authority_readiness_pct"
            ],
            "accuracy_certification_readiness_pct": accuracy["summary"][
                "weighted_certification_readiness_pct"
            ],
            "model_valid_task_coverage_pct": model_training["valid_model_task_coverage_pct"],
            "model_projected_human_review_rows": model_training[
                "projected_model_human_review_rows"
            ],
            "model_projected_cross_exam_rows": model_training["projected_cross_exam_rows"],
            "authority_path_blocked_phase_count": authority_path["blocked_phase_count"],
            "top_role": top_role.get("reviewer_role", ""),
            "top_role_review_rows": top_role.get("total_review_row_count", 0),
            "top_wave": top_wave.get("wave_id", ""),
            "top_wave_review_rows": top_wave.get("packet_or_projected_review_row_count", 0),
            "top_unit_ref": dossier["summary"]["top_decision_ref"],
            "top_unit_decision_pressure_score": dossier["summary"]["top_decision_pressure_score"],
            "certification_status": "blocked_not_review_assignable_as_authority",
        },
        "wave_rows": wave_rows,
        "role_rows": role_rows,
        "unit_role_rows": unit_role_rows,
        "lane_dependency_rows": lane_dependency,
        "gate_rows": gate_rows,
        "visual_data": {
            "role_workload_rows": role_visual_rows,
            "wave_workload_rows": wave_visual_rows,
            "lane_blocker_rows": lane_visual_rows,
            "unit_pressure_rows": unit_visual_rows,
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
    left = 260
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
    role_rows = [
        [
            row["reviewer_role"],
            row["wave_id"],
            row["critical_unit_assignment_count"],
            row["critical_packet_review_row_count"],
            row["source_acquisition_review_row_count"],
            row["total_review_row_count"],
            f"{row['completion_pct']:.2f}%",
            row["blocked_lane_count"],
            row["claim_blocking_gate_count"],
            row["top_ref"],
            row["next_action"],
        ]
        for row in report["role_rows"]
    ]
    wave_rows = [
        [
            row["wave_id"],
            row["wave"],
            row["depends_on"],
            "; ".join(row["responsible_roles"]),
            row["unit_count"],
            row["packet_or_projected_review_row_count"],
            f"{row['completion_pct']:.2f}%",
            row["blocked_lane_count"],
            row["claim_blocking_gate_count"],
            row["status"],
            row["next_action"],
        ]
        for row in report["wave_rows"]
    ]
    unit_role_rows = [
        [
            index,
            row["ref"],
            row["reviewer_role"],
            row["wave_id"],
            f"{row['decision_pressure_score']:.2f}",
            row["packet_review_row_count"],
            row["blocked_lane_count"],
            row["claim_blocking_gate_count"],
            "yes" if row["jewish_christian_separation_required"] else "no",
            "yes" if row["textual_witness_pressure"] else "no",
            row["status"],
        ]
        for index, row in enumerate(report["unit_role_rows"][:180], start=1)
    ]
    lane_rows = [
        [
            row["lane_label"],
            row["wave_id"],
            "; ".join(row["responsible_roles"]),
            row["unit_count"],
            row["blocked_unit_count"],
            row["review_required_unit_count"],
            row["status"],
            row["next_action"],
        ]
        for row in report["lane_dependency_rows"]
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
    summary_cards = metric_cards(
        [
            (
                "Critical units",
                summary["critical_unit_count"],
                f"{summary['text_blocked_unit_count']} are text-blocked.",
            ),
            (
                "Critical packet rows",
                summary["critical_packet_review_row_count"],
                "Packet rows scoped to the critical decision dossier.",
            ),
            (
                "Role review rows",
                summary["total_role_review_row_count"],
                f"{summary['completed_role_review_row_count']} completed.",
            ),
            (
                "Review completion",
                f"{summary['review_completion_pct']:.2f}%",
                "Critical-unit role/source rows completed.",
            ),
            (
                "Blocked gates",
                f"{summary['blocked_gate_count']}/{summary['gate_count']}",
                "Execution gates still blocking review authority.",
            ),
            (
                "Top role",
                summary["top_role"],
                f"{summary['top_role_review_rows']} review/source rows.",
            ),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Critical Unit Review Execution Plan</title>
  <style>
    body {{
      font-family: Inter, Segoe UI, sans-serif;
      color: #24313a;
      margin: 0;
      background: #f6f4ef;
    }}
    header {{
      background: #20343b;
      color: white;
      padding: 30px 44px;
    }}
    main {{ padding: 28px 44px 48px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin: 28px 0; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
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
    <h1>Critical Unit Review Execution Plan</h1>
    <p>
      Role workload, wave sequencing, lane dependencies, and release gates for
      the currently undecidable Psalms translation units.
    </p>
  </header>
  <main>
    <section>
      <div class="warning">
        <strong>Authority boundary:</strong> {esc(report["authority_policy"])}
      </div>
      {summary_cards}
    </section>

    <section>
      <h2>Visual Workload</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["role_workload_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit review workload by role",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["wave_workload_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit review workload by wave",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["lane_blocker_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit blocked lanes by lane",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["unit_pressure_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit pressure by unit",
            color="#584b87",
        )
    }</div>
    </section>

    <section>
      <h2>Review Waves</h2>
      {
        table(
            [
                "Wave",
                "Description",
                "Depends On",
                "Roles",
                "Units",
                "Rows",
                "Complete",
                "Blocked Lanes",
                "Claim Gates",
                "Status",
                "Next Action",
            ],
            wave_rows,
        )
    }
    </section>

    <section>
      <h2>Reviewer Roles</h2>
      {
        table(
            [
                "Role",
                "Wave",
                "Units",
                "Packet Rows",
                "Source Rows",
                "Total Rows",
                "Complete",
                "Blocked Lanes",
                "Claim Gates",
                "Top Unit",
                "Next Action",
            ],
            role_rows,
        )
    }
    </section>

    <section>
      <h2>Lane Dependencies</h2>
      {
        table(
            [
                "Lane",
                "Wave",
                "Roles",
                "Units",
                "Blocked",
                "Review Required",
                "Status",
                "Next Action",
            ],
            lane_rows,
        )
    }
    </section>

    <section>
      <h2>Release Gates</h2>
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

    <section>
      <h2>Unit Role Queue</h2>
      {
        table(
            [
                "Rank",
                "Ref",
                "Role",
                "Wave",
                "Pressure",
                "Packet Rows",
                "Blocked Lanes",
                "Claim Gates",
                "J/C Split",
                "Witness",
                "Status",
            ],
            unit_role_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate critical unit review execution plan.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--role-csv-output", type=Path, default=DEFAULT_ROLE_CSV_OUTPUT)
    parser.add_argument("--wave-csv-output", type=Path, default=DEFAULT_WAVE_CSV_OUTPUT)
    parser.add_argument("--unit-role-csv-output", type=Path, default=DEFAULT_UNIT_ROLE_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.role_csv_output, report["role_rows"])
    write_csv(args.wave_csv_output, report["wave_rows"])
    write_csv(args.unit_role_csv_output, report["unit_role_rows"])
    write_csv(args.gate_csv_output, report["gate_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.role_csv_output}")
    print(f"Wrote {args.wave_csv_output}")
    print(f"Wrote {args.unit_role_csv_output}")
    print(f"Wrote {args.gate_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
