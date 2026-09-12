from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"

SOURCE_PATHS = {
    "lexeme": REPORT_ROOT / "lexeme_context_readiness.json",
    "morphology_gap": REPORT_ROOT / "whole_tanakh_morphology_gap.json",
    "morphology_acquisition": REPORT_ROOT / "whole_tanakh_morphology_acquisition_readiness.json",
    "canonical_cross_reference": REPORT_ROOT / "canonical_cross_reference_atlas.json",
    "cultural_historical": REPORT_ROOT / "cultural_historical_domain_atlas.json",
    "poetic_rhetorical": REPORT_ROOT / "poetic_rhetorical_pressure_atlas.json",
    "witness_divergence": REPORT_ROOT / "witness_divergence_report.json",
    "reception_divergence": REPORT_ROOT / "reception_divergence_atlas.json",
    "interpretive_control": REPORT_ROOT / "interpretive_tradition_control_matrix.json",
    "semantic_referent": REPORT_ROOT / "semantic_referent_enrichment_roadmap.json",
    "claim_traceability": REPORT_ROOT / "translation_claim_traceability_audit.json",
    "source_ladder": REPORT_ROOT / "source_authority_ladder_matrix.json",
    "review_workbook": REPORT_ROOT / "contextual_review_signoff_workbook.json",
    "unit_heatmap": REPORT_ROOT / "doctoral_unit_authority_heatmap.json",
    "defense_exhibit": REPORT_ROOT / "doctoral_defense_exhibit_pack.json",
    "model_training": REPORT_ROOT / "model_training_certification_roadmap.json",
    "authority_path": REPORT_ROOT / "authority_critical_path_report.json",
    "synthesis": REPORT_ROOT / "doctoral_translation_synthesis.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "translation_accuracy_certification_matrix.json"
DEFAULT_DIMENSION_CSV_OUTPUT = REPORT_ROOT / "translation_accuracy_certification_dimensions.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "translation_accuracy_certification_gates.csv"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "translation_accuracy_certification_units.csv"
DEFAULT_ROLE_CSV_OUTPUT = REPORT_ROOT / "translation_accuracy_certification_roles.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "translation_accuracy_certification_matrix.html"

AUTHORITY_POLICY = (
    "This matrix certifies evidence readiness only. It does not approve sources, "
    "settle Jewish or Christian interpretation, certify a model, authorize wording, "
    "or release canonical translation text. Certification authority requires signed "
    "source approvals, semantic/referent enrichment where needed, human scholarly "
    "review, and release signoff."
)


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


def clamp(value: float | int) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


def pct(part: float | int, total: float | int) -> float:
    return round(float(part) / float(total) * 100.0, 2) if total else 0.0


def weighted_mean(rows: list[dict[str, Any]], key: str) -> float:
    total_weight = sum(float(row["weight"]) for row in rows)
    if not total_weight:
        return 0.0
    weighted = sum(float(row["weight"]) * float(row[key]) for row in rows)
    return round(weighted / total_weight, 2)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def fmt_pct(value: Any) -> str:
    return f"{float(value):.2f}%"


def status_from_score(score: float, *, hard_blocked: bool = False) -> str:
    if hard_blocked:
        return "blocked"
    if score >= 85:
        return "strong_evidence"
    if score >= 65:
        return "usable_with_caveats"
    if score >= 40:
        return "partial"
    if score > 0:
        return "weak"
    return "blocked"


def source_artifacts(*keys: str) -> list[str]:
    return [str(SOURCE_PATHS[key].relative_to(ROOT)) for key in keys]


def dimension_row(
    *,
    dimension_id: str,
    dimension: str,
    weight: int,
    evidence_maturity_pct: float,
    certification_readiness_pct: float,
    hard_blocked: bool,
    primary_metric: str,
    supporting_metrics: list[str],
    blocking_gap: str,
    next_action: str,
    source_keys: tuple[str, ...],
) -> dict[str, Any]:
    readiness = clamp(certification_readiness_pct)
    maturity = clamp(evidence_maturity_pct)
    return {
        "dimension_id": dimension_id,
        "dimension": dimension,
        "weight": weight,
        "evidence_maturity_pct": maturity,
        "certification_readiness_pct": readiness,
        "status": status_from_score(readiness, hard_blocked=hard_blocked),
        "hard_blocked": hard_blocked,
        "primary_metric": primary_metric,
        "supporting_metrics": supporting_metrics,
        "blocking_gap": blocking_gap,
        "next_action": next_action,
        "source_artifacts": source_artifacts(*source_keys),
    }


def build_dimension_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    lexeme = data["lexeme"]["summary"]
    morphology_gap = data["morphology_gap"]["summary"]
    morphology_acquisition = data["morphology_acquisition"]["summary"]
    canonical = data["canonical_cross_reference"]["summary"]
    cultural = data["cultural_historical"]["summary"]
    poetic = data["poetic_rhetorical"]["summary"]
    witness = data["witness_divergence"]["summary"]
    reception = data["reception_divergence"]["summary"]
    interpretive = data["interpretive_control"]["summary"]
    semantic = data["semantic_referent"]["summary"]
    claim = data["claim_traceability"]["summary"]
    source_ladder = data["source_ladder"]["summary"]
    review = data["review_workbook"]["summary"]
    unit_heatmap = data["unit_heatmap"]["summary"]
    model_training = data["model_training"]["summary"]
    authority_path = data["authority_path"]["summary"]
    synthesis = data["synthesis"]["summary"]

    lexical_maturity = (
        float(lexeme["strong_coverage_pct"]) + float(lexeme["lemma_coverage_pct"])
    ) / 2.0
    whole_tanakh_surface_maturity = float(morphology_gap["surface_outside_context_token_pct"])
    cultural_maturity = float(cultural["domain_unit_pct"])
    poetic_maturity = pct(poetic["high_pressure_unit_count"], poetic["unit_count"])
    witness_maturity = float(witness["complete_english_witness_unit_pct"])
    reception_maturity = pct(
        reception["jewish_christian_separation_unit_count"],
        max(1, reception["reception_sensitive_unit_count"]),
    )
    semantic_maturity = (
        float(semantic["semantic_role_coverage_pct"]) + float(semantic["referent_coverage_pct"])
    ) / 2.0
    review_maturity = float(review["review_completion_pct"])
    release_readiness = 0.0 if authority_path["blocked_phase_count"] else 100.0
    missing_semantic_roles = fmt_int(semantic["missing_semantic_role_token_count"])
    surface_outside_context_pct = fmt_pct(morphology_gap["surface_outside_context_token_pct"])
    outside_strong_context_pct = fmt_pct(morphology_gap["outside_strong_context_token_pct"])
    oshb_mismatch_rows = fmt_int(morphology_acquisition["oshb_alignment_pilot_mismatch_row_count"])
    parallelism_proxy_units = fmt_int(poetic["adjacent_parallelism_proxy_unit_count"])
    mean_witness_divergence = fmt_pct(witness["mean_english_witness_divergence_pct"])
    divine_name_disagreements = fmt_int(witness["divine_name_disagreement_unit_count"])
    completed_interpretive_reviews = fmt_int(interpretive["completed_packet_review_count"])
    measured_contextual_attempts = fmt_int(model_training["measured_contextual_attempt_count"])
    clean_source_anchored_pct = fmt_pct(model_training["clean_source_anchored_pct"])

    return [
        dimension_row(
            dimension_id="ACC-01",
            dimension="Hebrew token and lexeme basis",
            weight=12,
            evidence_maturity_pct=lexical_maturity,
            certification_readiness_pct=min(80.0, lexical_maturity),
            hard_blocked=False,
            primary_metric=(
                f"Strong {fmt_pct(lexeme['strong_coverage_pct'])}; "
                f"lemma {fmt_pct(lexeme['lemma_coverage_pct'])}"
            ),
            supporting_metrics=[
                f"{fmt_int(lexeme['token_count'])} Hebrew token records",
                f"{fmt_int(lexeme['distinct_strong_keys'])} distinct Strong keys",
                f"{fmt_int(lexeme['distinct_lemmas'])} distinct lemmas",
            ],
            blocking_gap=(
                "The token and lemma basis is strong, but semantic role and referent "
                "fields are still absent and review signoff is not complete."
            ),
            next_action=(
                "Keep lexical claims token-cited, then enrich semantic role and referent "
                "fields before high-risk discourse claims."
            ),
            source_keys=("lexeme", "semantic_referent"),
        ),
        dimension_row(
            dimension_id="ACC-02",
            dimension="Semantic role and referent precision",
            weight=12,
            evidence_maturity_pct=semantic_maturity,
            certification_readiness_pct=semantic_maturity,
            hard_blocked=True,
            primary_metric=(
                f"semantic role {fmt_pct(semantic['semantic_role_coverage_pct'])}; "
                f"referent {fmt_pct(semantic['referent_coverage_pct'])}"
            ),
            supporting_metrics=[
                f"{missing_semantic_roles} tokens missing semantic role",
                f"{fmt_int(semantic['missing_referent_token_count'])} tokens missing referent",
                f"{fmt_int(semantic['critical_enrichment_token_count'])} critical tokens",
            ],
            blocking_gap="Semantic-role and referent coverage is 0.00%.",
            next_action=(
                "Import or derive semantic-role and referent fields, then route critical "
                "tokens to Hebrew, lexical, and theology review."
            ),
            source_keys=("semantic_referent", "lexeme"),
        ),
        dimension_row(
            dimension_id="ACC-03",
            dimension="Whole-Old-Testament morphology and lexeme context",
            weight=12,
            evidence_maturity_pct=whole_tanakh_surface_maturity,
            certification_readiness_pct=float(
                morphology_gap["local_non_psalm_morphology_book_pct"]
            ),
            hard_blocked=True,
            primary_metric=(
                f"{fmt_int(morphology_gap['local_non_psalm_books_with_hebrew_morphology'])} "
                f"of {fmt_int(morphology_gap['uxlc_non_psalm_book_count'])} non-Psalm "
                "books have local morphology"
            ),
            supporting_metrics=[
                f"surface-form outside context {surface_outside_context_pct}",
                f"outside Strong context {outside_strong_context_pct}",
                f"{oshb_mismatch_rows} OSHB pilot mismatch rows",
            ],
            blocking_gap=(
                "Outside-Psalms evidence is surface-form context, not local "
                "whole-Tanakh lemma/Strong morphology."
            ),
            next_action=(
                "Approve source terms, import whole-Tanakh morphology, and resolve OSHB "
                "alignment exceptions before making non-Psalm lexeme authority claims."
            ),
            source_keys=("morphology_gap", "morphology_acquisition"),
        ),
        dimension_row(
            dimension_id="ACC-04",
            dimension="Canonical and Old Testament intertext controls",
            weight=9,
            evidence_maturity_pct=float(canonical["cross_reference_unit_pct"]),
            certification_readiness_pct=min(50.0, float(canonical["cross_reference_unit_pct"])),
            hard_blocked=False,
            primary_metric=(
                f"{fmt_pct(canonical['cross_reference_unit_pct'])} Psalm units have "
                "non-Psalm UXLC surface anchors"
            ),
            supporting_metrics=[
                f"{fmt_int(canonical['anchor_token_count'])} anchor tokens",
                f"{fmt_int(canonical['three_division_unit_count'])} three-division units",
                f"{fmt_int(canonical['book_evidence_count'])} non-Psalm books represented",
            ],
            blocking_gap=(
                "Canonical anchors are normalized surface-form evidence and do not prove "
                "lemma identity, allusion, dependence, or wording authority."
            ),
            next_action=(
                "Pair cross-reference anchors with imported morphology, source packets, "
                "and reviewer decisions before intertext claims affect wording."
            ),
            source_keys=("canonical_cross_reference", "morphology_gap"),
        ),
        dimension_row(
            dimension_id="ACC-05",
            dimension="Ancient cultural and historical controls",
            weight=8,
            evidence_maturity_pct=cultural_maturity,
            certification_readiness_pct=min(45.0, cultural_maturity),
            hard_blocked=False,
            primary_metric=(
                f"{fmt_int(cultural['domain_unit_count'])} units carry cultural or "
                "historical domain evidence"
            ),
            supporting_metrics=[
                f"{fmt_int(cultural['domain_token_count'])} domain-token assignments",
                f"{fmt_int(cultural['high_priority_unit_count'])} high-priority units",
                f"top unit {cultural['top_priority_ref']}",
            ],
            blocking_gap=(
                "Cultural markers route review; they do not prove dating, social setting, "
                "or translation wording."
            ),
            next_action=(
                "Create source-approved cultural packets for high-priority units and keep "
                "cultural claims tagged outside translation wording until signed."
            ),
            source_keys=("cultural_historical", "source_ladder"),
        ),
        dimension_row(
            dimension_id="ACC-06",
            dimension="Poetic, rhetorical, and lyric constraints",
            weight=7,
            evidence_maturity_pct=poetic_maturity,
            certification_readiness_pct=min(40.0, poetic_maturity + 20.0),
            hard_blocked=False,
            primary_metric=(
                f"{fmt_int(poetic['high_pressure_unit_count'])} high-pressure poetic/"
                "rhetorical units"
            ),
            supporting_metrics=[
                f"{fmt_int(poetic['critical_pressure_unit_count'])} critical-pressure units",
                f"{fmt_int(poetic['volitive_token_count'])} volitive tokens",
                f"{parallelism_proxy_units} parallelism-proxy units",
            ],
            blocking_gap=(
                "Poetic pressure is routed, but lyric choices still need lexical, poetic, "
                "alignment, theology, and release review."
            ),
            next_action=(
                "Use poetic pressure rows to prioritize lyric and alignment review for "
                "units where style could distort Hebrew meaning."
            ),
            source_keys=("poetic_rhetorical", "review_workbook"),
        ),
        dimension_row(
            dimension_id="ACC-07",
            dimension="Textual witnesses and English comparison controls",
            weight=8,
            evidence_maturity_pct=witness_maturity,
            certification_readiness_pct=min(60.0, witness_maturity),
            hard_blocked=False,
            primary_metric=(
                f"{fmt_pct(witness['complete_english_witness_unit_pct'])} complete "
                "English witness coverage"
            ),
            supporting_metrics=[
                f"{mean_witness_divergence} mean witness divergence",
                f"{fmt_int(witness['high_divergence_unit_count'])} high-divergence units",
                f"{divine_name_disagreements} divine-name disagreements",
            ],
            blocking_gap=(
                "English witnesses are comparison controls only and cannot silently "
                "override Hebrew token evidence."
            ),
            next_action=(
                "Use witness divergence to flag review, especially divine-name and "
                "bracketed-expansion cases, without treating witnesses as source text."
            ),
            source_keys=("witness_divergence", "claim_traceability"),
        ),
        dimension_row(
            dimension_id="ACC-08",
            dimension="Jewish, Christian, and academic interpretation separation",
            weight=10,
            evidence_maturity_pct=reception_maturity,
            certification_readiness_pct=0.0,
            hard_blocked=True,
            primary_metric=(
                f"{fmt_int(reception['jewish_christian_separation_unit_count'])} units "
                "require separated Jewish/Christian review lanes"
            ),
            supporting_metrics=[
                f"{fmt_int(interpretive['packet_count'])} interpretive packets",
                f"{fmt_int(interpretive['source_approval_count'])} source approvals",
                f"{completed_interpretive_reviews} completed packet reviews",
            ],
            blocking_gap=(
                "Separated reception lanes exist, but no source approvals or packet "
                "reviews are complete."
            ),
            next_action=(
                "Complete Jewish, Christian, and academic packet review separately; keep "
                "reception claims outside translation text unless release-reviewed."
            ),
            source_keys=("reception_divergence", "interpretive_control"),
        ),
        dimension_row(
            dimension_id="ACC-09",
            dimension="Source approval, provenance, and license authority",
            weight=12,
            evidence_maturity_pct=float(source_ladder["mean_source_authority_readiness_pct"]),
            certification_readiness_pct=0.0,
            hard_blocked=True,
            primary_metric=(
                f"{fmt_int(source_ladder['source_approval_count'])} source approvals "
                f"for {fmt_int(source_ladder['unit_count'])} high-risk units"
            ),
            supporting_metrics=[
                f"{fmt_int(source_ladder['candidate_reachable_count'])} of "
                f"{fmt_int(source_ladder['candidate_source_count'])} candidate sources reachable",
                f"{fmt_int(source_ladder['critical_gap_unit_count'])} critical source gaps",
                f"{fmt_int(source_ladder['blocked_gate_count'])} blocked source gates",
            ],
            blocking_gap=(
                "All high-risk units remain blocked by missing source approvals, unsigned "
                "packet reviews, or release signoff."
            ),
            next_action=(
                "Resolve missing/unreachable/high-risk source families, approve source "
                "use, and attach provenance before using external data authoritatively."
            ),
            source_keys=("source_ladder", "review_workbook"),
        ),
        dimension_row(
            dimension_id="ACC-10",
            dimension="Local model benchmark and cross-examination evidence",
            weight=9,
            evidence_maturity_pct=float(model_training["valid_model_task_coverage_pct"]),
            certification_readiness_pct=float(model_training["valid_model_task_coverage_pct"]),
            hard_blocked=True,
            primary_metric=(
                f"{fmt_pct(model_training['valid_model_task_coverage_pct'])} valid "
                "contextual model-task coverage"
            ),
            supporting_metrics=[
                f"{measured_contextual_attempts} measured contextual attempts",
                f"{clean_source_anchored_pct} clean source-anchored rows",
                f"{fmt_int(model_training['projected_cross_exam_rows'])} projected cross-exam rows",
            ],
            blocking_gap=(
                "Measured local model evidence is sparse and no model output has "
                "translation-text authority."
            ),
            next_action=(
                "Run expanded benchmarks against the selected baseline, trainable base, "
                "Hebrew-specialist challenger, and advisory cross-exam models."
            ),
            source_keys=("model_training", "claim_traceability"),
        ),
        dimension_row(
            dimension_id="ACC-11",
            dimension="Human scholarly review and role workload",
            weight=12,
            evidence_maturity_pct=review_maturity,
            certification_readiness_pct=review_maturity,
            hard_blocked=True,
            primary_metric=(
                f"{fmt_int(review['completed_review_row_count'])} of "
                f"{fmt_int(review['total_review_row_count'])} review rows complete"
            ),
            supporting_metrics=[
                f"{fmt_int(review['critical_unit_count'])} critical units",
                f"{fmt_int(review['reviewer_role_count'])} reviewer roles",
                f"{fmt_int(review['model_projected_human_review_rows'])} model-human review rows",
            ],
            blocking_gap="No review rows are complete.",
            next_action=(
                "Assign Hebrew, lexical, alignment, theology, lyric, license, provenance, "
                "legal, and release reviewers, then record signed decisions."
            ),
            source_keys=("review_workbook", "authority_path"),
        ),
        dimension_row(
            dimension_id="ACC-12",
            dimension="Translation-text claim and release authority",
            weight=14,
            evidence_maturity_pct=release_readiness,
            certification_readiness_pct=release_readiness,
            hard_blocked=True,
            primary_metric=(
                f"{fmt_int(claim['translation_text_allowed_now_count'])} currently "
                "text-authorized claim rows"
            ),
            supporting_metrics=[
                f"{fmt_int(claim['required_claim_row_count'])} required claim rows",
                f"{fmt_int(claim['blocked_or_review_claim_count'])} blocked/review claim rows",
                f"{fmt_int(unit_heatmap['blocked_unit_count'])} blocked units in heatmap",
                f"{fmt_int(synthesis['critical_blocker_count'])} critical blockers",
            ],
            blocking_gap=(
                "No claim family has current translation-text authority because source, "
                "semantic/referent, review, model, and release gates remain open."
            ),
            next_action=(
                "Keep claim families in notes/source packets until source approval, "
                "human review, and release authority are recorded."
            ),
            source_keys=("claim_traceability", "unit_heatmap", "synthesis"),
        ),
    ]


def gate_row(
    gate_id: str,
    gate: str,
    status: str,
    current_value: str,
    target_value: str,
    blocker_effect: str,
    source_keys: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "gate": gate,
        "status": status,
        "current_value": current_value,
        "target_value": target_value,
        "blocker_effect": blocker_effect,
        "source_artifacts": source_artifacts(*source_keys),
    }


def build_gate_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    morphology = data["morphology_gap"]["summary"]
    semantic = data["semantic_referent"]["summary"]
    claim = data["claim_traceability"]["summary"]
    source_ladder = data["source_ladder"]["summary"]
    review = data["review_workbook"]["summary"]
    interpretive = data["interpretive_control"]["summary"]
    model = data["model_training"]["summary"]
    authority_path = data["authority_path"]["summary"]
    unit_heatmap = data["unit_heatmap"]["summary"]

    return [
        gate_row(
            "GATE-01",
            "Source approval",
            "blocked",
            f"{fmt_int(source_ladder['source_approval_count'])} approved",
            "source approval decisions for all required source families",
            "No external source lane can authorize wording or training use.",
            ("source_ladder",),
        ),
        gate_row(
            "GATE-02",
            "Whole-Tanakh morphology",
            "blocked",
            (
                f"{fmt_int(morphology['local_non_psalm_books_with_hebrew_morphology'])}/"
                f"{fmt_int(morphology['uxlc_non_psalm_book_count'])} non-Psalm books"
            ),
            "approved local morphology for all required non-Psalm context",
            "Non-Psalm lexeme claims remain surface-form context only.",
            ("morphology_gap", "morphology_acquisition"),
        ),
        gate_row(
            "GATE-03",
            "Semantic role and referent enrichment",
            "blocked",
            (
                f"semantic {fmt_pct(semantic['semantic_role_coverage_pct'])}; "
                f"referent {fmt_pct(semantic['referent_coverage_pct'])}"
            ),
            "semantic and referent coverage sufficient for high-risk claims",
            "Discourse, antecedent, speaker, and addressee claims cannot be certified.",
            ("semantic_referent",),
        ),
        gate_row(
            "GATE-04",
            "Jewish/Christian separated review",
            "blocked",
            (
                f"{fmt_int(interpretive['completed_packet_review_count'])}/"
                f"{fmt_int(interpretive['packet_count'])} packets reviewed"
            ),
            "all separated reception packets reviewed and source-approved",
            "Reception claims must stay outside translation wording.",
            ("interpretive_control", "reception_divergence"),
        ),
        gate_row(
            "GATE-05",
            "Model benchmark coverage",
            "blocked",
            f"{fmt_pct(model['valid_model_task_coverage_pct'])} valid task coverage",
            "near-complete expanded benchmark coverage with clean anchors",
            "Local model output remains proposal evidence only.",
            ("model_training",),
        ),
        gate_row(
            "GATE-06",
            "Claim translation-text authority",
            "blocked",
            f"{fmt_int(claim['translation_text_allowed_now_count'])} allowed now",
            "all required claim rows either text-authorized or explicitly excluded",
            "Claims can route review, but cannot authorize translation wording.",
            ("claim_traceability",),
        ),
        gate_row(
            "GATE-07",
            "Human review completion",
            "blocked",
            (
                f"{fmt_int(review['completed_review_row_count'])}/"
                f"{fmt_int(review['total_review_row_count'])} rows"
            ),
            "signed decisions for required reviewer rows",
            "No certification can be signed without reviewer identity and decision rows.",
            ("review_workbook",),
        ),
        gate_row(
            "GATE-08",
            "Blocked unit clearance",
            "blocked",
            f"{fmt_int(unit_heatmap['blocked_unit_count'])} blocked units",
            "0 blocked high-risk units before release",
            "Every high-risk unit remains blocked for canonical authority.",
            ("unit_heatmap", "claim_traceability"),
        ),
        gate_row(
            "GATE-09",
            "Release authority",
            "blocked",
            (
                f"{fmt_int(authority_path['blocked_phase_count'])}/"
                f"{fmt_int(authority_path['phase_count'])} phases blocked"
            ),
            "all phases cleared and release reviewer signoff recorded",
            "No canonical rendering may be promoted from this evidence alone.",
            ("authority_path", "synthesis"),
        ),
    ]


def build_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    synthesis_units = {
        str(row["unit_id"]): row for row in data["synthesis"].get("priority_unit_rows", [])
    }
    rows = []
    for source_row in data["source_ladder"].get("unit_rows", [])[:25]:
        unit_id = str(source_row["unit_id"])
        synthesis_row = synthesis_units.get(unit_id, {})
        rows.append(
            {
                "rank": len(rows) + 1,
                "unit_id": unit_id,
                "ref": source_row["ref"],
                "source_authority_gap_score": source_row["source_authority_gap_score"],
                "source_authority_readiness_pct": source_row["source_authority_readiness_pct"],
                "evidence_ladder_stage": source_row["evidence_ladder_stage"],
                "chief_blocker": source_row["chief_blocker"],
                "packet_priority_score": source_row["packet_priority_score"],
                "interpretive_control_score": source_row["interpretive_control_score"],
                "packet_family_count": source_row["packet_family_count"],
                "source_approval_count": source_row["source_approval_count"],
                "packet_review_row_count": source_row["packet_review_row_count"],
                "completed_review_row_count": source_row["completed_review_row_count"],
                "jewish_christian_separation_required": source_row[
                    "jewish_christian_separation_required"
                ],
                "textual_witness_pressure": source_row["textual_witness_pressure"],
                "ancient_culture_pressure": source_row["ancient_culture_pressure"],
                "cross_reference_three_division": source_row["cross_reference_three_division"],
                "required_roles": synthesis_row.get("required_roles", ""),
                "next_action": source_row["next_action"],
            }
        )
    return rows


def build_role_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "reviewer_role": row["reviewer_role"],
            "total_review_row_count": row["total_review_row_count"],
            "packet_review_row_count": row["packet_review_row_count"],
            "source_acquisition_review_row_count": row["source_acquisition_review_row_count"],
            "critical_packet_review_row_count": row["critical_packet_review_row_count"],
            "highest_packet_review_row_count": row["highest_packet_review_row_count"],
            "unit_count": row["unit_count"],
            "status": row["status"],
        }
        for rank, row in enumerate(data["review_workbook"].get("review_role_rows", []), start=1)
    ]


def build_visual_data(
    dimension_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    role_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts = Counter(str(row["status"]) for row in dimension_rows)
    gate_counts = Counter(str(row["status"]) for row in gate_rows)
    return {
        "dimension_score_rows": [
            {
                "dimension": row["dimension"],
                "evidence_maturity_pct": row["evidence_maturity_pct"],
                "certification_readiness_pct": row["certification_readiness_pct"],
                "status": row["status"],
            }
            for row in dimension_rows
        ],
        "dimension_status_counts": [
            {"status": status, "count": count} for status, count in sorted(status_counts.items())
        ],
        "gate_status_counts": [
            {"status": status, "count": count} for status, count in sorted(gate_counts.items())
        ],
        "top_unit_gap_rows": [
            {
                "ref": row["ref"],
                "source_authority_gap_score": row["source_authority_gap_score"],
                "packet_review_row_count": row["packet_review_row_count"],
            }
            for row in unit_rows[:12]
        ],
        "review_role_workload_rows": [
            {
                "reviewer_role": row["reviewer_role"],
                "total_review_row_count": row["total_review_row_count"],
                "critical_packet_review_row_count": row["critical_packet_review_row_count"],
            }
            for row in role_rows
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    dimension_rows = build_dimension_rows(data)
    gate_rows = build_gate_rows(data)
    unit_rows = build_unit_rows(data)
    role_rows = build_role_rows(data)
    visual_data = build_visual_data(dimension_rows, gate_rows, unit_rows, role_rows)

    blocked_dimensions = [row for row in dimension_rows if row["status"] == "blocked"]
    hard_blocked_dimensions = [row for row in dimension_rows if row["hard_blocked"]]
    blocked_gates = [row for row in gate_rows if row["status"] == "blocked"]
    release_authorized_dimensions = [
        row for row in dimension_rows if row["certification_readiness_pct"] >= 95
    ]
    top_dimension_gap = min(
        dimension_rows,
        key=lambda row: (float(row["certification_readiness_pct"]), -float(row["weight"])),
    )
    top_unit = unit_rows[0] if unit_rows else {}

    summary = {
        "dimension_count": len(dimension_rows),
        "gate_count": len(gate_rows),
        "blocked_dimension_count": len(blocked_dimensions),
        "hard_blocked_dimension_count": len(hard_blocked_dimensions),
        "blocked_gate_count": len(blocked_gates),
        "weighted_evidence_maturity_pct": weighted_mean(dimension_rows, "evidence_maturity_pct"),
        "weighted_certification_readiness_pct": weighted_mean(
            dimension_rows, "certification_readiness_pct"
        ),
        "release_authorized_dimension_count": len(release_authorized_dimensions),
        "review_role_count": len(role_rows),
        "total_review_row_count": data["review_workbook"]["summary"]["total_review_row_count"],
        "completed_review_row_count": data["review_workbook"]["summary"][
            "completed_review_row_count"
        ],
        "review_completion_pct": data["review_workbook"]["summary"]["review_completion_pct"],
        "source_approval_count": data["source_ladder"]["summary"]["source_approval_count"],
        "text_authorized_claim_row_count": data["claim_traceability"]["summary"][
            "translation_text_allowed_now_count"
        ],
        "required_claim_row_count": data["claim_traceability"]["summary"][
            "required_claim_row_count"
        ],
        "semantic_role_coverage_pct": data["semantic_referent"]["summary"][
            "semantic_role_coverage_pct"
        ],
        "referent_coverage_pct": data["semantic_referent"]["summary"]["referent_coverage_pct"],
        "local_non_psalm_morphology_book_count": data["morphology_gap"]["summary"][
            "local_non_psalm_books_with_hebrew_morphology"
        ],
        "target_non_psalm_morphology_book_count": data["morphology_gap"]["summary"][
            "uxlc_non_psalm_book_count"
        ],
        "model_valid_task_coverage_pct": data["model_training"]["summary"][
            "valid_model_task_coverage_pct"
        ],
        "top_dimension_gap_id": top_dimension_gap["dimension_id"],
        "top_dimension_gap": top_dimension_gap["dimension"],
        "top_unit_ref": top_unit.get("ref", ""),
        "top_unit_gap_score": top_unit.get("source_authority_gap_score", 0),
        "certification_status": "blocked_not_certifiable",
        "authority_verdict": (
            "Evidence is extensive enough to prioritize scholarly work, but the "
            "translation system is not accuracy-certifiable: source approvals, "
            "semantic/referent enrichment, Jewish/Christian review lanes, local model "
            "benchmark coverage, human review, and release authority remain blocked."
        ),
    }

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "translation accuracy certification matrix generated; not signoff",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": AUTHORITY_POLICY,
        "summary": summary,
        "dimension_rows": dimension_rows,
        "gate_rows": gate_rows,
        "unit_rows": unit_rows,
        "role_rows": role_rows,
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
    rows: list[dict[str, Any]],
    label_key: str,
    value_key: str,
    *,
    value_suffix: str = "%",
    max_value: float = 100.0,
) -> str:
    rendered = []
    for row in rows:
        value = float(row[value_key])
        width = 0.0 if not max_value else clamp(value / max_value * 100.0)
        rendered.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{escape(str(row[label_key]))}</div>
              <div class="bar-track"><div class="bar-fill" style="width: {width:.2f}%"></div></div>
              <div class="bar-value">{value:.2f}{escape(value_suffix)}</div>
            </div>
            """
        )
    return "".join(rendered)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    dimensions = report["dimension_rows"]
    gates = report["gate_rows"]
    units = report["unit_rows"]
    roles = report["role_rows"]
    visual = report["visual_data"]

    dimension_table = [
        [
            row["dimension_id"],
            row["dimension"],
            f"{row['evidence_maturity_pct']:.2f}%",
            f"{row['certification_readiness_pct']:.2f}%",
            row["status"],
            row["primary_metric"],
            row["blocking_gap"],
        ]
        for row in dimensions
    ]
    gate_table = [
        [
            row["gate_id"],
            row["gate"],
            row["status"],
            row["current_value"],
            row["target_value"],
            row["blocker_effect"],
        ]
        for row in gates
    ]
    unit_table = [
        [
            row["rank"],
            row["ref"],
            row["source_authority_gap_score"],
            row["source_authority_readiness_pct"],
            row["chief_blocker"],
            row["packet_review_row_count"],
            row["jewish_christian_separation_required"],
            row["textual_witness_pressure"],
            row["ancient_culture_pressure"],
        ]
        for row in units[:15]
    ]
    role_table = [
        [
            row["rank"],
            row["reviewer_role"],
            row["total_review_row_count"],
            row["critical_packet_review_row_count"],
            row["highest_packet_review_row_count"],
            row["status"],
        ]
        for row in roles
    ]

    max_unit_gap = max(
        [float(row["source_authority_gap_score"]) for row in visual["top_unit_gap_rows"]] or [1.0]
    )
    max_role_rows = max(
        [float(row["total_review_row_count"]) for row in visual["review_role_workload_rows"]]
        or [1.0]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Translation Accuracy Certification Matrix</title>
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
      grid-template-columns: minmax(170px, 1.3fr) minmax(140px, 2fr) 90px;
      gap: 10px;
      align-items: center;
      margin: 10px 0;
      font-size: 0.9rem;
    }}
    .bar-label {{
      color: var(--ink);
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
  <h1>Translation Accuracy Certification Matrix</h1>
  <p class="lede">
    This report turns the broader doctoral research portfolio into a signoff-oriented
    ledger for Hebrew-to-English Psalms translation accuracy. It distinguishes evidence
    maturity from certification authority across Hebrew token evidence, whole-Old-Testament
    context, ancient culture, poetic form, textual witnesses, Jewish and Christian
    interpretation lanes, local model evidence, human review, and release gates.
  </p>
  <div class="callout">
    <strong>Authority boundary:</strong> {escape(report["authority_policy"])}
  </div>

  <section class="metric-grid" aria-label="Headline metrics">
    {
        metric_cards(
            [
                (
                    "Certification Status",
                    summary["certification_status"],
                    summary["authority_verdict"],
                ),
                (
                    "Evidence Maturity",
                    f"{summary['weighted_evidence_maturity_pct']:.2f}%",
                    "Weighted evidence maturity across certification dimensions.",
                ),
                (
                    "Certification Readiness",
                    f"{summary['weighted_certification_readiness_pct']:.2f}%",
                    "Readiness after source, semantic, review, model, and release blockers.",
                ),
                (
                    "Blocked Gates",
                    f"{fmt_int(summary['blocked_gate_count'])}/{fmt_int(summary['gate_count'])}",
                    "Non-negotiable gates still blocking accuracy certification.",
                ),
                (
                    "Review Completion",
                    f"{summary['review_completion_pct']:.2f}%",
                    f"{fmt_int(summary['completed_review_row_count'])} of "
                    f"{fmt_int(summary['total_review_row_count'])} rows complete.",
                ),
                (
                    "Text-Authorized Claims",
                    fmt_int(summary["text_authorized_claim_row_count"]),
                    f"{fmt_int(summary['required_claim_row_count'])} required rows remain gated.",
                ),
                (
                    "Top Dimension Gap",
                    summary["top_dimension_gap"],
                    summary["top_dimension_gap_id"],
                ),
                (
                    "Top Unit Gap",
                    summary["top_unit_ref"],
                    f"source gap score {summary['top_unit_gap_score']}",
                ),
            ]
        )
    }
  </section>

  <section>
    <h2>Visual Certification Readiness</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Dimension Evidence Maturity</h3>
        {
        bar_rows(
            visual["dimension_score_rows"],
            "dimension",
            "evidence_maturity_pct",
        )
    }
      </div>
      <div class="panel">
        <h3>Dimension Certification Readiness</h3>
        {
        bar_rows(
            visual["dimension_score_rows"],
            "dimension",
            "certification_readiness_pct",
        )
    }
      </div>
      <div class="panel">
        <h3>Top Unit Source Gaps</h3>
        {
        bar_rows(
            visual["top_unit_gap_rows"],
            "ref",
            "source_authority_gap_score",
            value_suffix="",
            max_value=max_unit_gap,
        )
    }
      </div>
      <div class="panel">
        <h3>Reviewer Workload</h3>
        {
        bar_rows(
            visual["review_role_workload_rows"],
            "reviewer_role",
            "total_review_row_count",
            value_suffix="",
            max_value=max_role_rows,
        )
    }
      </div>
    </div>
  </section>

  <section>
    <h2>Accuracy Dimensions</h2>
    {
        table(
            [
                "ID",
                "Dimension",
                "Evidence",
                "Readiness",
                "Status",
                "Primary metric",
                "Blocking gap",
            ],
            dimension_table,
        )
    }
  </section>

  <section>
    <h2>Certification Gates</h2>
    {table(["ID", "Gate", "Status", "Current", "Target", "Blocker effect"], gate_table)}
  </section>

  <section>
    <h2>Highest-Priority Unit Gaps</h2>
    {
        table(
            [
                "Rank",
                "Ref",
                "Source gap",
                "Source readiness",
                "Chief blocker",
                "Review rows",
                "J/C split",
                "Witness",
                "Culture",
            ],
            unit_table,
        )
    }
  </section>

  <section>
    <h2>Reviewer Role Workload</h2>
    {table(["Rank", "Role", "Rows", "Critical rows", "Highest rows", "Status"], role_table)}
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
    parser.add_argument("--dimension-csv-output", type=Path, default=DEFAULT_DIMENSION_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--role-csv-output", type=Path, default=DEFAULT_ROLE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    args = parser.parse_args()

    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.dimension_csv_output, report["dimension_rows"])
    write_csv(args.gate_csv_output, report["gate_rows"])
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.role_csv_output, report["role_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")

    for path in [
        args.json_output,
        args.dimension_csv_output,
        args.gate_csv_output,
        args.unit_csv_output,
        args.role_csv_output,
        args.html_output,
    ]:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
