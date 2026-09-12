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
    "claim_matrix": REPORT_ROOT / "translation_claim_evidence_matrix.json",
    "reception_boundary": REPORT_ROOT / "reception_interpretation_boundary.json",
    "interpretive_control": REPORT_ROOT / "interpretive_tradition_control_matrix.json",
    "source_ladder": REPORT_ROOT / "source_authority_ladder_matrix.json",
    "doctoral_defense": REPORT_ROOT / "doctoral_defense_exhibit_pack.json",
    "hebrew_token_defense": REPORT_ROOT / "hebrew_token_defense_matrix.json",
    "semantic_referent": REPORT_ROOT / "semantic_referent_enrichment_roadmap.json",
    "canonical_cross_reference": REPORT_ROOT / "canonical_cross_reference_atlas.json",
    "cultural_atlas": REPORT_ROOT / "cultural_historical_domain_atlas.json",
    "witness_divergence": REPORT_ROOT / "witness_divergence_report.json",
    "divine_name_policy": REPORT_ROOT / "divine_name_policy_report.json",
    "superscription_context": REPORT_ROOT / "superscription_context_report.json",
    "poetic_rhetorical": REPORT_ROOT / "poetic_rhetorical_pressure_atlas.json",
    "contextual_real_model": REPORT_ROOT / "contextual_real_model_evidence_matrix.json",
    "review_workbook": REPORT_ROOT / "contextual_review_signoff_workbook.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "translation_claim_traceability_audit.json"
DEFAULT_CLAIM_CSV_OUTPUT = REPORT_ROOT / "translation_claim_traceability_claims.csv"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "translation_claim_traceability_units.csv"
DEFAULT_FAMILY_CSV_OUTPUT = REPORT_ROOT / "translation_claim_traceability_families.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "translation_claim_traceability_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "translation_claim_traceability_audit.html"

AUTHORITY_POLICY = (
    "The translation claim traceability audit is an admissibility map. It routes "
    "Hebrew, broader-canon, cultural, witness, reception, model, and release "
    "claims into permitted review locations, but it does not approve sources, "
    "resolve interpretation, alter canonical wording, certify model output, or "
    "grant release authority."
)

CLAIM_FAMILIES = [
    {
        "family_id": "hebrew_plain_sense",
        "label": "Hebrew Plain Sense",
        "default_location": "draft_translation_and_notes",
        "rule": "Translation wording must stay anchored to the Hebrew source and token alignment.",
    },
    {
        "family_id": "lexical_morphology",
        "label": "Lexical/Morphology",
        "default_location": "translation_notes_and_alignment",
        "rule": "Lexical claims require token IDs, lemma/Strong evidence, and morphology review.",
    },
    {
        "family_id": "semantic_referent",
        "label": "Semantic/Referent",
        "default_location": "enrichment_queue_only",
        "rule": "Semantic-role and referent claims require enrichment and reviewer adjudication.",
    },
    {
        "family_id": "whole_tanakh_context",
        "label": "Whole-Tanakh Context",
        "default_location": "source_packet_and_notes",
        "rule": "Whole-Tanakh surface anchors are context evidence, not lemma/sense proof.",
    },
    {
        "family_id": "ancient_culture",
        "label": "Ancient Culture",
        "default_location": "source_packet_and_notes",
        "rule": "Ancient-culture claims require tagged rationale and source review.",
    },
    {
        "family_id": "textual_witness",
        "label": "Textual Witnesses",
        "default_location": "apparatus_and_notes",
        "rule": "Witness variants may be compared but must not override Hebrew silently.",
    },
    {
        "family_id": "jewish_reception",
        "label": "Jewish Reception",
        "default_location": "separated_reception_notes",
        "rule": (
            "Jewish reception must be separated from translation wording and Christian reception."
        ),
    },
    {
        "family_id": "christian_reception",
        "label": "Christian Reception",
        "default_location": "separated_reception_notes",
        "rule": (
            "Christian reception must be separated from translation wording and Jewish reception."
        ),
    },
    {
        "family_id": "academic_comparison",
        "label": "Academic Comparison",
        "default_location": "academic_notes_and_benchmark",
        "rule": "Academic comparison frames are review context, not source-text authority.",
    },
    {
        "family_id": "divine_name_policy",
        "label": "Divine-Name Policy",
        "default_location": "policy_review_and_notes",
        "rule": "Divine-name rendering decisions require project policy and theology review.",
    },
    {
        "family_id": "superscription_context",
        "label": "Superscription Context",
        "default_location": "heading_notes_and_review",
        "rule": "Superscription context informs review but is not proof of authorship or setting.",
    },
    {
        "family_id": "poetic_rhetorical",
        "label": "Poetic/Rhetorical Form",
        "default_location": "layered_rendering_review",
        "rule": "Poetic form can guide lyric layers only while preserving token alignment.",
    },
    {
        "family_id": "model_output",
        "label": "Model Output",
        "default_location": "benchmark_candidate_only",
        "rule": "Model output is a candidate artifact until schema, source, and human review pass.",
    },
    {
        "family_id": "release_authority",
        "label": "Release Authority",
        "default_location": "release_gate_only",
        "rule": "Canonical wording and release require review signoff and audit records.",
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


def as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "yes", "1"}
    return bool(value)


def by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key)}


def build_indexes(data: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "claim": by_key(data["claim_matrix"].get("unit_claim_rows", []), "unit_id"),
        "boundary": by_key(data["reception_boundary"].get("unit_boundary_rows", []), "unit_id"),
        "control": by_key(data["interpretive_control"].get("unit_rows", []), "unit_id"),
        "source": by_key(data["source_ladder"].get("unit_rows", []), "unit_id"),
        "defense": by_key(data["doctoral_defense"].get("unit_rows", []), "unit_id"),
        "token_defense": by_key(data["hebrew_token_defense"].get("unit_rows", []), "unit_id"),
        "semantic": by_key(data["semantic_referent"].get("unit_rows", []), "unit_id"),
        "cross": by_key(data["canonical_cross_reference"].get("unit_rows", []), "unit_id"),
        "culture": by_key(data["cultural_atlas"].get("unit_rows", []), "unit_id"),
        "witness": by_key(data["witness_divergence"].get("unit_rows", []), "unit_id"),
        "divine": by_key(data["divine_name_policy"].get("unit_rows", []), "unit_id"),
        "superscription": by_key(data["superscription_context"].get("unit_rows", []), "unit_id"),
        "poetic": by_key(data["poetic_rhetorical"].get("unit_rows", []), "unit_id"),
    }


def evidence_grade(value: float, *, strong: float, partial: float = 1.0) -> str:
    if value >= strong:
        return "evidence_rich"
    if value >= partial:
        return "partial_evidence"
    return "missing_or_not_required"


def required_for_family(family_id: str, rows: dict[str, dict[str, Any]]) -> bool:
    claim = rows["claim"]
    boundary = rows["boundary"]
    control = rows["control"]
    semantic = rows["semantic"]
    cross = rows["cross"]
    culture = rows["culture"]
    witness = rows["witness"]
    divine = rows["divine"]
    superscription = rows["superscription"]
    poetic = rows["poetic"]
    if family_id in {"hebrew_plain_sense", "lexical_morphology", "release_authority"}:
        return True
    if family_id == "semantic_referent":
        return bool(semantic)
    if family_id == "whole_tanakh_context":
        return int(cross.get("anchor_token_count") or 0) > 0
    if family_id == "ancient_culture":
        return boolish(claim.get("ancient_culture_pressure")) or bool(culture)
    if family_id == "textual_witness":
        return boolish(claim.get("textual_witness_pressure")) or bool(witness)
    if family_id == "jewish_reception":
        return boolish(claim.get("has_jewish_reception_frame")) or boolish(
            boundary.get("has_jewish_reception_frame")
        )
    if family_id == "christian_reception":
        return boolish(claim.get("has_christian_reception_frame")) or boolish(
            boundary.get("has_christian_reception_frame")
        )
    if family_id == "academic_comparison":
        return boolish(claim.get("has_academic_comparison_frame")) or boolish(
            boundary.get("has_academic_comparison_frame")
        )
    if family_id == "divine_name_policy":
        return bool(divine) or boolish(control.get("theology_pressure"))
    if family_id == "superscription_context":
        return bool(superscription)
    if family_id == "poetic_rhetorical":
        return bool(poetic) and as_float(poetic.get("poetic_rhetorical_priority_score")) > 0
    if family_id == "model_output":
        return True
    return False


def family_evidence(family_id: str, rows: dict[str, dict[str, Any]]) -> tuple[float, str, str]:
    claim = rows["claim"]
    source = rows["source"]
    defense = rows["defense"]
    token_defense = rows["token_defense"]
    semantic = rows["semantic"]
    cross = rows["cross"]
    culture = rows["culture"]
    witness = rows["witness"]
    divine = rows["divine"]
    superscription = rows["superscription"]
    poetic = rows["poetic"]
    if family_id == "hebrew_plain_sense":
        score = 40 + as_float(token_defense.get("mean_token_defense_score")) * 0.2
        return score, evidence_grade(score, strong=55), "Hebrew source and token rows exist."
    if family_id == "lexical_morphology":
        token_count = int(token_defense.get("token_count") or claim.get("task_count") or 0)
        score = min(
            80.0, token_count * 3 + as_float(token_defense.get("mean_token_defense_score")) * 0.2
        )
        return (
            score,
            evidence_grade(score, strong=45),
            "Token, lemma, Strong, and morphology rows route review.",
        )
    if family_id == "semantic_referent":
        missing = int(semantic.get("missing_semantic_role_token_count") or 0) + int(
            semantic.get("missing_referent_token_count") or 0
        )
        score = max(0.0, 35.0 - missing * 0.5)
        return score, "blocked_gap", "Semantic-role and referent enrichment are absent."
    if family_id == "whole_tanakh_context":
        anchors = int(cross.get("anchor_token_count") or 0)
        high = int(cross.get("high_value_anchor_count") or 0)
        score = anchors * 8 + high * 8
        return (
            score,
            evidence_grade(score, strong=40),
            "Surface-form anchors route broader-canon review.",
        )
    if family_id == "ancient_culture":
        score = (
            int(culture.get("domain_count") or 0) * 18
            + as_float(culture.get("priority_score")) * 0.1
        )
        return (
            score,
            evidence_grade(score, strong=35),
            "Cultural-domain markers and source packets route review.",
        )
    if family_id == "textual_witness":
        score = (
            as_float(witness.get("mean_english_witness_divergence_pct"))
            + int(witness.get("english_witness_count") or 0) * 8
        )
        return (
            score,
            evidence_grade(score, strong=45),
            "English witnesses/LXX route apparatus review.",
        )
    if family_id in {"jewish_reception", "christian_reception", "academic_comparison"}:
        score = (
            as_float(rows["control"].get("boundary_risk_score"))
            + as_float(rows["control"].get("reception_divergence_priority_score")) * 0.2
        )
        return (
            score,
            evidence_grade(score, strong=45),
            "Separated interpretive frames route reception review.",
        )
    if family_id == "divine_name_policy":
        score = (
            int(divine.get("divine_title_token_count") or 0) * 35
            + as_float(divine.get("priority_score")) * 0.1
        )
        return (
            score,
            evidence_grade(score, strong=35),
            "Divine-title token rows route policy review.",
        )
    if family_id == "superscription_context":
        score = (
            int(superscription.get("context_token_count") or 0) * 24
            + as_float(superscription.get("priority_score")) * 0.08
        )
        return (
            score,
            evidence_grade(score, strong=35),
            "Heading/context tokens route superscription review.",
        )
    if family_id == "poetic_rhetorical":
        score = as_float(poetic.get("poetic_rhetorical_priority_score"))
        return (
            score,
            evidence_grade(score, strong=35),
            "Poetic/rhetorical features route layer review.",
        )
    if family_id == "model_output":
        clean = int(defense.get("clean_source_anchored_attempt_count") or 0)
        score = clean * 35 + as_float(defense.get("unit_authority_score_pct")) * 0.2
        return (
            score,
            "blocked_gap" if clean == 0 else "partial_evidence",
            "Model outputs remain candidates.",
        )
    if family_id == "release_authority":
        score = as_float(source.get("source_authority_readiness_pct"))
        return score, "blocked_gap", "Release and canonical authority are separate gates."
    return 0.0, "missing_or_not_required", ""


def allowed_location(family_id: str, *, required: bool) -> str:
    if not required:
        return "not_required"
    if family_id in {"jewish_reception", "christian_reception"}:
        return "separated_reception_notes_only"
    if family_id == "semantic_referent":
        return "enrichment_queue_only_until_reviewed"
    if family_id == "whole_tanakh_context":
        return "source_packet_and_notes_not_lemma_proof"
    if family_id == "textual_witness":
        return "apparatus_and_notes_not_silent_override"
    if family_id == "model_output":
        return "benchmark_candidate_only"
    if family_id == "release_authority":
        return "release_gate_only"
    if family_id in {"ancient_culture", "academic_comparison", "superscription_context"}:
        return "tagged_notes_and_source_packet"
    if family_id == "divine_name_policy":
        return "policy_review_before_translation_wording"
    if family_id == "poetic_rhetorical":
        return "layered_rendering_review"
    return "draft_translation_and_alignment_notes"


def blocking_gates(family_id: str, rows: dict[str, dict[str, Any]], grade: str) -> list[str]:
    source = rows["source"]
    defense = rows["defense"]
    semantic = rows["semantic"]
    gates: list[str] = []
    if int(source.get("source_approval_count") or 0) == 0:
        gates.append("source_approval_missing")
    if int(source.get("completed_review_row_count") or 0) == 0:
        gates.append("human_review_missing")
    if family_id == "semantic_referent" and (
        int(semantic.get("missing_semantic_role_token_count") or 0)
        or int(semantic.get("missing_referent_token_count") or 0)
    ):
        gates.append("semantic_referent_enrichment_missing")
    if family_id in {
        "jewish_reception",
        "christian_reception",
        "academic_comparison",
        "ancient_culture",
        "textual_witness",
    }:
        gates.append("claim_must_remain_outside_translation_text")
    if family_id == "whole_tanakh_context":
        gates.append("surface_anchor_not_lemma_or_allusion_proof")
    if (
        family_id == "model_output"
        and int(defense.get("clean_source_anchored_attempt_count") or 0) == 0
    ):
        gates.append("clean_model_evidence_missing")
    if family_id == "release_authority":
        gates.extend(["canonical_change_approval_missing", "release_signoff_missing"])
    if grade == "blocked_gap":
        gates.append("evidence_gap_blocks_authority")
    return sorted(set(gates))


def admissibility_status(required: bool, family_id: str, gates: list[str]) -> str:
    if not required:
        return "not_required"
    if family_id == "hebrew_plain_sense" and gates == [
        "human_review_missing",
        "source_approval_missing",
    ]:
        return "draft_only_not_authoritative"
    if "claim_must_remain_outside_translation_text" in gates:
        return "notes_or_packets_only"
    if family_id in {"model_output", "release_authority", "semantic_referent"}:
        return "blocked"
    if gates:
        return "review_required"
    return "admissible_after_review"


def build_claim_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    indexes = build_indexes(data)
    claim_rows: list[dict[str, Any]] = []
    for unit_id, claim in indexes["claim"].items():
        rows = {name: index.get(unit_id, {}) for name, index in indexes.items()}
        rows["claim"] = claim
        for family in CLAIM_FAMILIES:
            family_id = family["family_id"]
            required = required_for_family(family_id, rows)
            score, grade, evidence = family_evidence(family_id, rows)
            gates = blocking_gates(family_id, rows, grade) if required else []
            status = admissibility_status(required, family_id, gates)
            claim_rows.append(
                {
                    "unit_id": unit_id,
                    "ref": claim.get("ref", ""),
                    "family_id": family_id,
                    "family_label": family["label"],
                    "required": required,
                    "claim_risk_score": as_float(claim.get("claim_risk_score")),
                    "family_evidence_score": round(score, 2),
                    "evidence_grade": grade,
                    "admissibility_status": status,
                    "allowed_location": allowed_location(family_id, required=required),
                    "translation_text_allowed_now": False,
                    "translation_text_allowed_after_review": family_id
                    in {
                        "hebrew_plain_sense",
                        "lexical_morphology",
                        "divine_name_policy",
                        "poetic_rhetorical",
                    },
                    "blocking_gates": gates,
                    "blocking_gate_count": len(gates),
                    "evidence_summary": evidence,
                    "rule": family["rule"],
                    "required_review_roles": claim.get("required_review_roles", []),
                    "source_hebrew": rows["control"].get("source_hebrew", ""),
                    "authority_boundary": AUTHORITY_POLICY,
                }
            )
    claim_rows.sort(
        key=lambda row: (
            -int(row["required"]),
            -int(row["blocking_gate_count"]),
            -float(row["claim_risk_score"]),
            row["ref"],
            row["family_id"],
        )
    )
    for index, row in enumerate(claim_rows, start=1):
        row["rank"] = index
    return claim_rows


def build_unit_rows(claim_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in claim_rows:
        grouped[row["unit_id"]].append(row)
    rows: list[dict[str, Any]] = []
    for unit_id, claims in grouped.items():
        required = [row for row in claims if row["required"]]
        blocked = [
            row for row in required if row["admissibility_status"] in {"blocked", "review_required"}
        ]
        notes_only = [
            row for row in required if row["admissibility_status"] == "notes_or_packets_only"
        ]
        gates = Counter(gate for row in required for gate in row["blocking_gates"])
        top = (
            max(required, key=lambda row: float(row["claim_risk_score"])) if required else claims[0]
        )
        rows.append(
            {
                "unit_id": unit_id,
                "ref": top["ref"],
                "claim_risk_score": top["claim_risk_score"],
                "required_claim_family_count": len(required),
                "blocked_or_review_claim_family_count": len(blocked),
                "notes_only_claim_family_count": len(notes_only),
                "translation_text_allowed_now_count": sum(
                    1 for row in required if row["translation_text_allowed_now"]
                ),
                "translation_text_allowed_after_review_count": sum(
                    1 for row in required if row["translation_text_allowed_after_review"]
                ),
                "blocking_gate_count": sum(row["blocking_gate_count"] for row in required),
                "top_blocking_gates": [gate for gate, _ in gates.most_common(6)],
                "required_claim_families": [row["family_id"] for row in required],
                "notes_only_claim_families": [row["family_id"] for row in notes_only],
                "blocked_claim_families": [row["family_id"] for row in blocked],
                "source_hebrew": top["source_hebrew"],
                "authority_boundary": AUTHORITY_POLICY,
            }
        )
    rows.sort(
        key=lambda row: (
            -int(row["blocked_or_review_claim_family_count"]),
            -float(row["claim_risk_score"]),
            row["ref"],
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_family_rows(claim_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in claim_rows:
        grouped[row["family_id"]].append(row)
    rows: list[dict[str, Any]] = []
    for family in CLAIM_FAMILIES:
        family_id = family["family_id"]
        claims = grouped[family_id]
        required = [row for row in claims if row["required"]]
        gates = Counter(gate for row in required for gate in row["blocking_gates"])
        top = max(required or claims, key=lambda row: float(row["claim_risk_score"]))
        rows.append(
            {
                "family_id": family_id,
                "family_label": family["label"],
                "unit_count": len(claims),
                "required_unit_count": len(required),
                "required_unit_pct": pct(len(required), len(claims)),
                "blocked_unit_count": sum(
                    1 for row in required if row["admissibility_status"] == "blocked"
                ),
                "review_required_unit_count": sum(
                    1 for row in required if row["admissibility_status"] == "review_required"
                ),
                "notes_only_unit_count": sum(
                    1 for row in required if row["admissibility_status"] == "notes_or_packets_only"
                ),
                "translation_text_allowed_now_count": sum(
                    1 for row in required if row["translation_text_allowed_now"]
                ),
                "mean_evidence_score": mean(
                    [float(row["family_evidence_score"]) for row in required]
                ),
                "top_ref": top["ref"],
                "top_claim_risk_score": top["claim_risk_score"],
                "dominant_blocking_gates": [gate for gate, _ in gates.most_common(6)],
                "default_location": family["default_location"],
                "rule": family["rule"],
                "authority_boundary": AUTHORITY_POLICY,
            }
        )
    rows.sort(key=lambda row: (-int(row["required_unit_count"]), row["family_id"]))
    return rows


def build_gate_rows(claim_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gate_counts: Counter[str] = Counter()
    top_by_gate: dict[str, dict[str, Any]] = {}
    for row in claim_rows:
        for gate in row["blocking_gates"]:
            gate_counts[gate] += 1
            if (
                gate not in top_by_gate
                or row["claim_risk_score"] > top_by_gate[gate]["claim_risk_score"]
            ):
                top_by_gate[gate] = row
    rows: list[dict[str, Any]] = []
    for gate, count in gate_counts.most_common():
        top = top_by_gate[gate]
        rows.append(
            {
                "gate": gate,
                "claim_row_count": count,
                "claim_row_pct": pct(count, len(claim_rows)),
                "unit_count": len(
                    {row["unit_id"] for row in claim_rows if gate in row["blocking_gates"]}
                ),
                "top_ref": top["ref"],
                "top_family": top["family_label"],
                "top_claim_risk_score": top["claim_risk_score"],
                "next_action": next_action_for_gate(gate),
            }
        )
    return rows


def next_action_for_gate(gate: str) -> str:
    if gate == "source_approval_missing":
        return "Complete source/license approval before treating claim evidence as authoritative."
    if gate == "human_review_missing":
        return "Assign qualified reviewers and record signoff."
    if gate == "claim_must_remain_outside_translation_text":
        return "Keep claim in notes/source packets/benchmarks, separated from translation wording."
    if gate == "semantic_referent_enrichment_missing":
        return "Run semantic/referent enrichment workflow and adjudicate results."
    if gate == "surface_anchor_not_lemma_or_allusion_proof":
        return (
            "Label whole-Tanakh evidence as surface context unless lemma/sense proof is imported."
        )
    if gate == "clean_model_evidence_missing":
        return "Run model task and require schema-valid, source-anchored output."
    if gate == "canonical_change_approval_missing":
        return "Require two qualified approvals for canonical wording changes."
    if gate == "release_signoff_missing":
        return "Run release review after source, model, and audit gates pass."
    return "Resolve the blocking gate before authority claims."


def build_visual_data(
    unit_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "top_unit_rows": [
            {"label": row["ref"], "value": row["blocking_gate_count"]} for row in unit_rows[:20]
        ],
        "family_required_rows": [
            {"label": row["family_label"], "value": row["required_unit_count"]}
            for row in family_rows
        ],
        "family_blocked_rows": [
            {
                "label": row["family_label"],
                "value": row["blocked_unit_count"] + row["review_required_unit_count"],
            }
            for row in family_rows
        ],
        "gate_rows": [{"label": row["gate"], "value": row["claim_row_count"]} for row in gate_rows],
    }


def build_summary(
    claim_rows: list[dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    required = [row for row in claim_rows if row["required"]]
    notes_only = [row for row in required if row["admissibility_status"] == "notes_or_packets_only"]
    blocked = [
        row
        for row in required
        if row["admissibility_status"] in {"blocked", "review_required", "notes_or_packets_only"}
    ]
    return {
        "unit_count": len(unit_rows),
        "claim_row_count": len(claim_rows),
        "required_claim_row_count": len(required),
        "claim_family_count": len(family_rows),
        "gate_count": len(gate_rows),
        "translation_text_allowed_now_count": sum(
            1 for row in required if row["translation_text_allowed_now"]
        ),
        "translation_text_allowed_after_review_count": sum(
            1 for row in required if row["translation_text_allowed_after_review"]
        ),
        "notes_or_packets_only_claim_count": len(notes_only),
        "blocked_or_review_claim_count": len(blocked),
        "unit_with_no_translation_text_authority_count": sum(
            1 for row in unit_rows if int(row["translation_text_allowed_now_count"]) == 0
        ),
        "mean_required_family_evidence_score": mean(
            [float(row["family_evidence_score"]) for row in required]
        ),
        "top_traceability_unit": unit_rows[0]["unit_id"] if unit_rows else "",
        "top_traceability_ref": unit_rows[0]["ref"] if unit_rows else "",
        "top_traceability_blocking_gate_count": unit_rows[0]["blocking_gate_count"]
        if unit_rows
        else 0,
        "source_approval_missing_claim_count": sum(
            1 for row in required if "source_approval_missing" in row["blocking_gates"]
        ),
        "human_review_missing_claim_count": sum(
            1 for row in required if "human_review_missing" in row["blocking_gates"]
        ),
        "claim_outside_translation_text_count": sum(
            1
            for row in required
            if "claim_must_remain_outside_translation_text" in row["blocking_gates"]
        ),
        "authority_verdict": (
            "Claim evidence is traceable enough for review routing, but no claim family "
            "has current translation-text authority because source approval, human review, "
            "semantic/referent enrichment, model certification, and release gates remain open."
        ),
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    claim_rows = build_claim_rows(data)
    unit_rows = build_unit_rows(claim_rows)
    family_rows = build_family_rows(claim_rows)
    gate_rows = build_gate_rows(claim_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "translation claim traceability audit generated; not authority signoff",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": AUTHORITY_POLICY,
        "summary": build_summary(claim_rows, unit_rows, family_rows, gate_rows),
        "claim_rows": claim_rows,
        "unit_rows": unit_rows,
        "family_rows": family_rows,
        "gate_rows": gate_rows,
        "visual_data": build_visual_data(unit_rows, family_rows, gate_rows),
    }


def style_block() -> str:
    return """
    :root { color-scheme: light; --ink: #1f2528; --muted: #657076; --line: #d7dedf; }
    body {
      font-family: Inter, Arial, sans-serif;
      color: var(--ink);
      margin: 0;
      background: #f7f8f6;
    }
    header, section { max-width: 1240px; margin: 0 auto; padding: 28px 32px; }
    header { border-bottom: 1px solid var(--line); background: #ffffff; }
    h1, h2 { margin: 0 0 12px; letter-spacing: 0; }
    p { color: var(--muted); line-height: 1.5; }
    .warning {
      border-left: 4px solid #9b3d3d;
      background: #fff5f2;
      padding: 12px 14px;
      margin: 16px 0;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
    }
    .metric { background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
    .metric strong { display: block; font-size: 24px; margin-bottom: 4px; }
    .metric span { color: var(--muted); font-size: 13px; }
    .chart {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      margin: 16px 0;
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      margin: 16px 0 28px;
      font-size: 13px;
    }
    th, td {
      border: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }
    th { background: #eaf0ef; }
    td { max-width: 360px; overflow-wrap: anywhere; }
    .hebrew { direction: rtl; font-family: "SBL Hebrew", "Ezra SIL", serif; font-size: 18px; }
    """


def metric_cards(items: list[tuple[str, Any, str]]) -> str:
    return (
        '<section class="metrics">'
        + "".join(
            f'<div class="metric"><span>{esc(label)}</span><strong>{esc(value)}</strong>'
            f"<span>{esc(note)}</span></div>"
            for label, value, note in items
        )
        + "</section>"
    )


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    limit: int = 12,
) -> str:
    rows = rows[:limit]
    width = 1060
    row_h = 32
    label_w = 350
    chart_w = width - label_w - 90
    height = max(44, 24 + row_h * len(rows))
    max_value = max([float(row.get(value_key) or 0) for row in rows] or [1.0])
    parts = [f'<svg role="img" aria-label="{esc(aria_label)}" width="{width}" height="{height}">']
    for idx, row in enumerate(rows):
        y = 18 + idx * row_h
        value = float(row.get(value_key) or 0)
        bar_w = 0 if not max_value else int(chart_w * value / max_value)
        parts.append(
            f'<text x="0" y="{y + 16}" font-size="12">{esc(row.get(label_key, ""))}</text>'
        )
        parts.append(
            f'<rect x="{label_w}" y="{y}" width="{bar_w}" height="20" fill="{color}"></rect>'
        )
        parts.append(
            f'<text x="{label_w + bar_w + 8}" y="{y + 15}" font-size="12">{value:g}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "".join(
        "<tr>"
        + "".join(
            f'<td class="{"hebrew" if header == "Hebrew" else ""}">{esc(value)}</td>'
            for header, value in zip(headers, row, strict=False)
        )
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    claim_rows = [
        [
            row["rank"],
            row["ref"],
            row["family_label"],
            "yes" if row["required"] else "no",
            row["admissibility_status"],
            row["allowed_location"],
            "yes" if row["translation_text_allowed_now"] else "no",
            f"{row['family_evidence_score']:.2f}",
            row["evidence_grade"],
            "; ".join(row["blocking_gates"][:6]),
            row["evidence_summary"],
        ]
        for row in report["claim_rows"][:80]
    ]
    unit_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['claim_risk_score']:.2f}",
            row["required_claim_family_count"],
            row["blocked_or_review_claim_family_count"],
            row["notes_only_claim_family_count"],
            row["translation_text_allowed_now_count"],
            row["translation_text_allowed_after_review_count"],
            row["blocking_gate_count"],
            "; ".join(row["top_blocking_gates"]),
            "; ".join(row["required_claim_families"][:8]),
        ]
        for row in report["unit_rows"][:30]
    ]
    family_rows = [
        [
            row["family_label"],
            row["required_unit_count"],
            f"{row['required_unit_pct']:.2f}%",
            row["blocked_unit_count"],
            row["review_required_unit_count"],
            row["notes_only_unit_count"],
            row["translation_text_allowed_now_count"],
            f"{row['mean_evidence_score']:.2f}",
            row["top_ref"],
            "; ".join(row["dominant_blocking_gates"][:5]),
            row["default_location"],
        ]
        for row in report["family_rows"]
    ]
    gate_rows = [
        [
            row["gate"],
            row["claim_row_count"],
            f"{row['claim_row_pct']:.2f}%",
            row["unit_count"],
            row["top_ref"],
            row["top_family"],
            row["next_action"],
        ]
        for row in report["gate_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Translation Claim Traceability Audit</title>
  <style>{style_block()}</style>
</head>
<body>
<header>
  <h1>Translation Claim Traceability Audit</h1>
  <p>
    Claim-family admissibility map for high-pressure Psalms units. Each row
    separates Hebrew source claims, broader-canon evidence, ancient culture,
    textual witnesses, Jewish reception, Christian reception, model output, and
    release authority.
  </p>
  <div class="warning">{esc(report["authority_policy"])}</div>
  {
        metric_cards(
            [
                ("Units", summary["unit_count"], "High-pressure units audited."),
                ("Claim Rows", summary["claim_row_count"], "Unit-family traceability rows."),
                (
                    "Allowed Now",
                    summary["translation_text_allowed_now_count"],
                    "Current translation-text authority count.",
                ),
                (
                    "Notes/Packets",
                    summary["notes_or_packets_only_claim_count"],
                    "Claims barred from translation wording.",
                ),
                (
                    "Blocked/Review",
                    summary["blocked_or_review_claim_count"],
                    "Required claims with unresolved gates.",
                ),
                (
                    "Top Unit",
                    summary["top_traceability_ref"],
                    f"{summary['top_traceability_blocking_gate_count']} blocking gates.",
                ),
            ]
        )
    }
</header>

<section>
  <h2>Admissibility Frontiers</h2>
  <div class="chart">{
        svg_horizontal_bars(
            visual["top_unit_rows"],
            label_key="label",
            value_key="value",
            aria_label="Top units by claim blocking gates",
            color="#9b3d3d",
        )
    }</div>
  <div class="chart">{
        svg_horizontal_bars(
            visual["family_blocked_rows"],
            label_key="label",
            value_key="value",
            aria_label="Blocked or review-required claim families",
            color="#2f6f73",
        )
    }</div>
  <div class="chart">{
        svg_horizontal_bars(
            visual["gate_rows"],
            label_key="label",
            value_key="value",
            aria_label="Claim blocking gate counts",
            color="#7c5b2f",
        )
    }</div>
  {
        table(
            [
                "Rank",
                "Ref",
                "Risk",
                "Required",
                "Blocked/Review",
                "Notes Only",
                "Allowed Now",
                "Allowed After Review",
                "Gates",
                "Top Gates",
                "Families",
            ],
            unit_rows,
        )
    }
  {
        table(
            [
                "Rank",
                "Ref",
                "Family",
                "Required",
                "Status",
                "Allowed Location",
                "Text Now",
                "Evidence",
                "Grade",
                "Blocking Gates",
                "Evidence Summary",
            ],
            claim_rows,
        )
    }
</section>

<section>
  <h2>Family And Gate Audit</h2>
  {
        table(
            [
                "Family",
                "Required Units",
                "Required %",
                "Blocked",
                "Review",
                "Notes Only",
                "Text Now",
                "Mean Evidence",
                "Top Ref",
                "Dominant Gates",
                "Default Location",
            ],
            family_rows,
        )
    }
  {table(["Gate", "Claim Rows", "Pct", "Units", "Top Ref", "Top Family", "Next Action"], gate_rows)}
</section>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--claim-csv-output", type=Path, default=DEFAULT_CLAIM_CSV_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--family-csv-output", type=Path, default=DEFAULT_FAMILY_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.claim_csv_output, report["claim_rows"])
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.family_csv_output, report["family_rows"])
    write_csv(args.gate_csv_output, report["gate_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.claim_csv_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.family_csv_output}")
    print(f"Wrote {args.gate_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
