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
    "corpus_profile": REPORT_ROOT / "psalms_corpus_profile.json",
    "lexeme": REPORT_ROOT / "lexeme_context_readiness.json",
    "morphology_gap": REPORT_ROOT / "whole_tanakh_morphology_gap.json",
    "morphology_acquisition": (REPORT_ROOT / "whole_tanakh_morphology_acquisition_readiness.json"),
    "oshb_alignment_pilot": REPORT_ROOT / "oshb_whole_tanakh_alignment_pilot.json",
    "oshb_exception_review": REPORT_ROOT / "oshb_alignment_exception_review.json",
    "oshb_exception_taxonomy": REPORT_ROOT / "oshb_exception_taxonomy.json",
    "oshb_mapping_rule_simulation": REPORT_ROOT / "oshb_mapping_rule_simulation.json",
    "morphology_unlock_matrix": REPORT_ROOT / "whole_tanakh_morphology_unlock_matrix.json",
    "critical_unit_morphology_unlock": REPORT_ROOT / "critical_unit_morphology_unlock_plan.json",
    "canonical_context": REPORT_ROOT / "canonical_context_network.json",
    "canonical_cross_reference": REPORT_ROOT / "canonical_cross_reference_atlas.json",
    "canonical_intertext_benchmark": (
        REPORT_ROOT / "canonical_intertext_benchmark_supplement_suite.json"
    ),
    "canonical_intertext_benchmark_cross_exam": (
        REPORT_ROOT / "canonical_intertext_benchmark_supplement_cross_exam_protocol.json"
    ),
    "canonical_intertext_benchmark_dry_run_audit": (
        REPORT_ROOT / "canonical_intertext_benchmark_supplement_dry_run_audit.json"
    ),
    "canonical_intertext_benchmark_review": (
        REPORT_ROOT / "canonical_intertext_benchmark_supplement_review_signoff_plan.json"
    ),
    "canonical_intertext_real_smoke": (REPORT_ROOT / "canonical_intertext_real_smoke_report.json"),
    "witness": REPORT_ROOT / "witness_reception_readiness.json",
    "witness_divergence": REPORT_ROOT / "witness_divergence_report.json",
    "divine_name_policy": REPORT_ROOT / "divine_name_policy_report.json",
    "superscription_context": REPORT_ROOT / "superscription_context_report.json",
    "cultural_historical_atlas": REPORT_ROOT / "cultural_historical_domain_atlas.json",
    "poetic_rhetorical_atlas": REPORT_ROOT / "poetic_rhetorical_pressure_atlas.json",
    "corpus_reception_signal": REPORT_ROOT / "corpus_reception_signal_atlas.json",
    "reception_signal_benchmark": (
        REPORT_ROOT / "reception_signal_benchmark_supplement_suite.json"
    ),
    "reception_signal_benchmark_cross_exam": (
        REPORT_ROOT / "reception_signal_benchmark_supplement_cross_exam_protocol.json"
    ),
    "reception_signal_benchmark_dry_run_audit": (
        REPORT_ROOT / "reception_signal_benchmark_supplement_dry_run_audit.json"
    ),
    "reception_signal_benchmark_review": (
        REPORT_ROOT / "reception_signal_benchmark_supplement_review_signoff_plan.json"
    ),
    "reception_signal_real_smoke": REPORT_ROOT / "reception_signal_real_smoke_report.json",
    "reception_boundary": REPORT_ROOT / "reception_interpretation_boundary.json",
    "reception_divergence": REPORT_ROOT / "reception_divergence_atlas.json",
    "reception_source_packets": REPORT_ROOT / "reception_source_packet_workbook.json",
    "interpretive_tradition_control": (REPORT_ROOT / "interpretive_tradition_control_matrix.json"),
    "claim_matrix": REPORT_ROOT / "translation_claim_evidence_matrix.json",
    "claim_traceability": REPORT_ROOT / "translation_claim_traceability_audit.json",
    "translation_accuracy_certification": (
        REPORT_ROOT / "translation_accuracy_certification_matrix.json"
    ),
    "critical_unit_decision_dossier": REPORT_ROOT / "critical_unit_decision_dossier.json",
    "critical_unit_review_execution": REPORT_ROOT / "critical_unit_review_execution_plan.json",
    "critical_unit_model_cross_exam": REPORT_ROOT / "critical_unit_model_cross_exam_plan.json",
    "context_integration": REPORT_ROOT / "doctoral_context_integration_matrix.json",
    "collision_packets": REPORT_ROOT / "doctoral_collision_review_packets.json",
    "collision_benchmark": REPORT_ROOT / "doctoral_collision_benchmark_supplement_suite.json",
    "collision_benchmark_cross_exam": (
        REPORT_ROOT / "doctoral_collision_benchmark_supplement_cross_exam_protocol.json"
    ),
    "collision_benchmark_dry_run_audit": (
        REPORT_ROOT / "doctoral_collision_benchmark_supplement_dry_run_audit.json"
    ),
    "collision_benchmark_review": (
        REPORT_ROOT / "doctoral_collision_benchmark_supplement_review_signoff_plan.json"
    ),
    "collision_real_smoke": REPORT_ROOT / "doctoral_collision_real_smoke_report.json",
    "contextual_real_model_evidence_matrix": (
        REPORT_ROOT / "contextual_real_model_evidence_matrix.json"
    ),
    "adjudication": REPORT_ROOT / "interpretive_adjudication_matrix.json",
    "source_maturity": REPORT_ROOT / "scholarly_source_maturity_report.json",
    "source_packets": REPORT_ROOT / "contextual_source_packet_roadmap.json",
    "source_acquisition": REPORT_ROOT / "contextual_source_acquisition_plan.json",
    "bibliography": REPORT_ROOT / "doctoral_bibliography_provenance.json",
    "source_verification": REPORT_ROOT / "doctoral_source_verification.json",
    "source_authority_ladder": REPORT_ROOT / "source_authority_ladder_matrix.json",
    "unit_heatmap": REPORT_ROOT / "doctoral_unit_authority_heatmap.json",
    "priority_dossier_atlas": REPORT_ROOT / "doctoral_priority_dossier_atlas.json",
    "doctoral_defense_exhibit": REPORT_ROOT / "doctoral_defense_exhibit_pack.json",
    "hebrew_token_defense": REPORT_ROOT / "hebrew_token_defense_matrix.json",
    "semantic_referent_roadmap": REPORT_ROOT / "semantic_referent_enrichment_roadmap.json",
    "review_workbook": REPORT_ROOT / "contextual_review_signoff_workbook.json",
    "authority": REPORT_ROOT / "scholarly_authority_readiness.json",
    "authority_critical_path": REPORT_ROOT / "authority_critical_path_report.json",
    "local_selection": REPORT_ROOT / "local_model_selection_roadmap.json",
    "local_model_doctoral_bakeoff": REPORT_ROOT / "local_model_doctoral_bakeoff_matrix.json",
    "model_training_certification": REPORT_ROOT / "model_training_certification_roadmap.json",
    "model_gap": REPORT_ROOT / "model_evidence_gap_report.json",
    "quality_triage": REPORT_ROOT / "model_output_quality_triage.json",
    "layer_consistency": REPORT_ROOT / "layer_consistency_report.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "doctoral_translation_synthesis.json"
DEFAULT_REQUIREMENT_CSV_OUTPUT = REPORT_ROOT / "doctoral_translation_synthesis_requirements.csv"
DEFAULT_BLOCKER_CSV_OUTPUT = REPORT_ROOT / "doctoral_translation_synthesis_blockers.csv"
DEFAULT_BOUNDARY_CSV_OUTPUT = REPORT_ROOT / "doctoral_translation_synthesis_boundaries.csv"
DEFAULT_PRIORITY_UNIT_CSV_OUTPUT = REPORT_ROOT / "doctoral_translation_synthesis_priority_units.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "doctoral_translation_synthesis.html"

STATUS_ORDER = {
    "blocked": 0,
    "not started": 1,
    "weak": 2,
    "prototype": 3,
    "usable with caveats": 4,
    "strong": 5,
}

SEVERITY_ORDER = {
    "critical": 0,
    "hard": 1,
    "high": 2,
    "medium": 3,
    "watch": 4,
}


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


def fmt_pct(value: Any) -> str:
    return f"{float(value):.2f}%"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def clamp(value: int | float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


def weighted_mean(rows: list[dict[str, Any]]) -> float:
    total_weight = sum(float(row["weight"]) for row in rows)
    if not total_weight:
        return 0.0
    weighted = sum(float(row["weight"]) * float(row["score_pct"]) for row in rows)
    return round(weighted / total_weight, 2)


def authority_gate_map(authority: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["gate"]): row for row in authority.get("gate_rows", [])}


def field_coverage(report: dict[str, Any], field: str) -> float:
    for row in report.get("field_coverage", []):
        if row.get("field") == field:
            return float(row.get("coverage_pct") or 0)
    return float(report.get("summary", {}).get(f"{field}_coverage_pct") or 0)


def status_from_score(score: float, *, blocked: bool = False) -> str:
    if blocked:
        return "blocked"
    if score >= 85:
        return "strong"
    if score >= 70:
        return "usable with caveats"
    if score >= 45:
        return "prototype"
    if score > 0:
        return "weak"
    return "not started"


def requirement_row(
    *,
    requirement_id: str,
    requirement: str,
    weight: int,
    score_pct: float,
    evidence: str,
    blocking_gap: str,
    next_action: str,
    source_artifacts: list[str],
    status: str | None = None,
    hard_blocked: bool = False,
) -> dict[str, Any]:
    score = clamp(score_pct)
    resolved_status = (
        status if status is not None else status_from_score(score, blocked=hard_blocked)
    )
    return {
        "requirement_id": requirement_id,
        "requirement": requirement,
        "weight": weight,
        "score_pct": score,
        "status": resolved_status,
        "evidence": evidence,
        "blocking_gap": blocking_gap,
        "next_action": next_action,
        "source_artifacts": source_artifacts,
    }


def source_artifact_names(*keys: str) -> list[str]:
    return [str(SOURCE_PATHS[key].relative_to(ROOT)) for key in keys]


def build_requirement_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    corpus = data["corpus_profile"]["summary"]
    lexeme_report = data["lexeme"]
    lexeme = lexeme_report["summary"]
    morph_gap = data["morphology_gap"]["summary"]
    morph_acquisition = data["morphology_acquisition"]["summary"]
    oshb_pilot = data["oshb_alignment_pilot"]["summary"]
    oshb_exception = data["oshb_exception_review"]["summary"]
    oshb_taxonomy = data["oshb_exception_taxonomy"]["summary"]
    oshb_simulation = data["oshb_mapping_rule_simulation"]["summary"]
    critical_morph_unlock = data["critical_unit_morphology_unlock"]["summary"]
    canonical = data["canonical_context"]["summary"]
    cross_reference = data["canonical_cross_reference"]["summary"]
    canonical_intertext_benchmark = data["canonical_intertext_benchmark"]["summary"]
    canonical_intertext_cross_exam = data["canonical_intertext_benchmark_cross_exam"]["summary"]
    canonical_intertext_dry_run = data["canonical_intertext_benchmark_dry_run_audit"]["summary"]
    canonical_intertext_review = data["canonical_intertext_benchmark_review"]["summary"]
    canonical_intertext_real_smoke = data["canonical_intertext_real_smoke"]["summary"]
    witness = data["witness"]["summary"]
    witness_divergence = data["witness_divergence"]["summary"]
    divine_name = data["divine_name_policy"]["summary"]
    superscription = data["superscription_context"]["summary"]
    cultural = data["cultural_historical_atlas"]["summary"]
    poetic = data["poetic_rhetorical_atlas"]["summary"]
    context_integration = data["context_integration"]["summary"]
    collision_packets = data["collision_packets"]["summary"]
    collision_benchmark = data["collision_benchmark"]["summary"]
    collision_benchmark_cross_exam = data["collision_benchmark_cross_exam"]["summary"]
    collision_benchmark_dry_run = data["collision_benchmark_dry_run_audit"]["summary"]
    collision_benchmark_review = data["collision_benchmark_review"]["summary"]
    collision_real_smoke = data["collision_real_smoke"]["summary"]
    corpus_reception_signal = data["corpus_reception_signal"]["summary"]
    corpus_signal_new_candidates = corpus_reception_signal[
        "new_high_pressure_expansion_candidate_count"
    ]
    reception = data["reception_boundary"]["summary"]
    reception_divergence = data["reception_divergence"]["summary"]
    reception_source_packets = data["reception_source_packets"]["summary"]
    interpretive_control = data["interpretive_tradition_control"]["summary"]
    interpretive_forbidden_claim_units = fmt_int(
        interpretive_control["translation_text_forbidden_reception_claim_units"]
    )
    claim = data["claim_matrix"]["summary"]
    packets = data["source_packets"]["summary"]
    acquisition = data["source_acquisition"]["summary"]
    bibliography = data["bibliography"]["summary"]
    source_verification = data["source_verification"]["summary"]
    source_authority_ladder = data["source_authority_ladder"]["summary"]
    review = data["review_workbook"]["summary"]
    priority_dossier_atlas = data["priority_dossier_atlas"]["summary"]
    translation_accuracy = data["translation_accuracy_certification"]["summary"]
    critical_unit_decision = data["critical_unit_decision_dossier"]["summary"]
    critical_unit_review_execution = data["critical_unit_review_execution"]["summary"]
    critical_unit_model_cross_exam = data["critical_unit_model_cross_exam"]["summary"]
    source_maturity = data["source_maturity"]["summary"]
    local_selection = data["local_selection"]["summary"]
    local_bakeoff = data["local_model_doctoral_bakeoff"]["summary"]
    model_training_certification = data["model_training_certification"]["summary"]
    model_gap = data["model_gap"]["summary"]
    reception_signal_benchmark = data["reception_signal_benchmark"]["summary"]
    reception_signal_cross_exam = data["reception_signal_benchmark_cross_exam"]["summary"]
    reception_signal_dry_run = data["reception_signal_benchmark_dry_run_audit"]["summary"]
    reception_signal_review = data["reception_signal_benchmark_review"]["summary"]
    reception_signal_real_smoke = data["reception_signal_real_smoke"]["summary"]
    quality = data["quality_triage"]["summary"]
    layer = data["layer_consistency"]["summary"]
    gates = authority_gate_map(data["authority"])

    local_gate = gates.get("local_runtime_assets", {})
    lexical_gate = gates.get("lexical_morphology_traceability", {})
    whole_tanakh_gate = gates.get("whole_tanakh_context", {})
    witness_gate = gates.get("witness_reception_provenance", {})
    context_gate = gates.get("context_culture_atlas_coverage", {})
    cross_exam_gate = gates.get("benchmark_cross_exam_plumbing", {})
    real_model_gate = gates.get("real_model_evidence", {})
    signoff_gate = gates.get("human_signoff", {})
    release_gate = gates.get("release_authority", {})
    source_gate = gates.get("source_corpus_governance", {})

    reception_score = min(
        65.0,
        float(witness_gate.get("score_pct", 0)),
        pct(
            reception["both_jewish_christian_frame_unit_count"]
            + reception["high_boundary_risk_unit_count"],
            max(1, reception["reception_sensitive_unit_count"] * 2),
        )
        + 40.0,
    )
    acquisition_score = pct(
        acquisition["candidate_count"] - acquisition["blocked_gate_count"],
        acquisition["candidate_count"],
    )
    source_policy_score = min(
        float(source_gate.get("score_pct", 0)),
        source_maturity["mean_evidence_score_pct"] + 35.0,
        acquisition_score + 25.0,
    )

    return [
        requirement_row(
            requirement_id="REQ-01",
            requirement="Governed Hebrew source corpus and immutable provenance",
            weight=9,
            score_pct=source_gate.get("score_pct", 0),
            status=source_gate.get("status"),
            evidence=(
                f"{fmt_int(corpus['unit_count'])} Psalm units, "
                f"{fmt_int(corpus['total_token_records'])} Hebrew token records, "
                f"{fmt_int(corpus['witness_records'])} witness records."
            ),
            blocking_gap=str(source_gate.get("blocking_gap", "")),
            next_action=str(source_gate.get("next_action", "")),
            source_artifacts=source_artifact_names("corpus_profile", "authority"),
        ),
        requirement_row(
            requirement_id="REQ-02",
            requirement="Token-level Hebrew, lemma, Strong, and alignment traceability",
            weight=12,
            score_pct=lexical_gate.get("score_pct", 0),
            status=lexical_gate.get("status"),
            evidence=(
                f"Lemma {fmt_pct(lexeme['lemma_coverage_pct'])}; "
                f"Strong {fmt_pct(lexeme['strong_coverage_pct'])}; "
                f"syntax role {fmt_pct(field_coverage(lexeme_report, 'syntax_role'))}; "
                f"semantic role {fmt_pct(lexeme['semantic_role_coverage_pct'])}; "
                f"referent {fmt_pct(lexeme['referent_coverage_pct'])}."
            ),
            blocking_gap=str(lexical_gate.get("blocking_gap", "")),
            next_action=str(lexical_gate.get("next_action", "")),
            source_artifacts=source_artifact_names(
                "lexeme",
                "claim_matrix",
                "claim_traceability",
                "authority",
            ),
        ),
        requirement_row(
            requirement_id="REQ-03",
            requirement="Whole-Tanakh context beyond Psalms",
            weight=11,
            score_pct=whole_tanakh_gate.get("score_pct", 0),
            status=whole_tanakh_gate.get("status"),
            evidence=(
                f"{fmt_int(morph_gap['uxlc_book_count'])} UXLC books profiled; "
                f"{fmt_int(morph_gap['local_non_psalm_books_with_hebrew_morphology'])} "
                "non-Psalm books have local Hebrew morphology; "
                f"{fmt_pct(canonical['content_token_outside_context_pct'])} "
                "content-token outside-Psalms surface evidence in the benchmark network; "
                f"{fmt_int(cross_reference['cross_reference_unit_count'])} full-corpus "
                "Psalm units have UXLC surface-form anchors, including "
                f"{fmt_int(cross_reference['three_division_unit_count'])} with Torah, "
                "Prophets, and non-Psalm Writings evidence; canonical-intertext "
                "supplement locks "
                f"{fmt_int(canonical_intertext_benchmark['selected_intertext_unit_count'])} "
                "three-division units into "
                f"{fmt_int(canonical_intertext_benchmark['task_count'])} tasks. "
                "Morphology acquisition readiness recommends "
                f"{morph_acquisition['recommended_first_import_candidate']} first, with "
                f"{fmt_int(morph_acquisition['blocked_gate_count'])} blocked gates and "
                f"{fmt_int(morph_acquisition['not_started_gate_count'])} not-started gates. "
                "OSHB alignment pilot maps "
                f"{fmt_int(oshb_pilot['mapped_book_count'])} remote books and "
                f"{fmt_int(oshb_pilot['remote_oshb_word_count'])} OSHB words against "
                f"{fmt_int(oshb_pilot['local_uxlc_word_count'])} UXLC words, with "
                f"{fmt_pct(oshb_pilot['mean_sequence_similarity_pct'])} mean normalized "
                "verse similarity. The exception workbook now separates "
                f"{fmt_int(oshb_exception['token_count_exception_verse_count'])} "
                "token-count exceptions from "
                f"{fmt_int(oshb_exception['sequence_only_exception_verse_count'])} "
                "sequence-only exceptions. Taxonomy groups the exception queue into "
                f"{fmt_int(oshb_taxonomy['taxonomy_cause_count'])} cause families and "
                f"{fmt_int(oshb_taxonomy['review_batch_count'])} reviewer batches. "
                "Mapping-rule simulation routes "
                f"{fmt_int(oshb_simulation['candidate_rule_reduction_row_count'])} rows "
                "into candidate rule lanes, with "
                f"{fmt_int(oshb_simulation['manual_residual_row_count'])} manual/textual "
                "residual rows. The critical-unit morphology unlock plan isolates "
                f"{fmt_int(critical_morph_unlock['critical_unit_count'])} critical units, "
                "projects "
                f"{fmt_int(critical_morph_unlock['projected_review_ready_critical_unit_count'])} "
                "review-ready after approval/import, and raises the mean critical-unit "
                f"whole-Tanakh score from "
                f"{fmt_pct(critical_morph_unlock['mean_current_whole_tanakh_score_pct'])} "
                "to "
                f"{fmt_pct(critical_morph_unlock['mean_projected_review_ready_score_pct'])}."
            ),
            blocking_gap=str(whole_tanakh_gate.get("blocking_gap", "")),
            next_action=str(whole_tanakh_gate.get("next_action", "")),
            source_artifacts=source_artifact_names(
                "morphology_gap",
                "morphology_acquisition",
                "oshb_alignment_pilot",
                "oshb_exception_review",
                "oshb_exception_taxonomy",
                "oshb_mapping_rule_simulation",
                "critical_unit_morphology_unlock",
                "canonical_context",
                "canonical_cross_reference",
                "canonical_intertext_benchmark",
            ),
        ),
        requirement_row(
            requirement_id="REQ-04",
            requirement="Ancient cultural and historical context controls",
            weight=9,
            score_pct=context_gate.get("score_pct", 0),
            status=context_gate.get("status"),
            evidence=(
                f"{fmt_int(packets['ancient_culture_packet_unit_count'])} of "
                f"{fmt_int(packets['unit_count'])} expanded units need ancient-culture "
                "source packets; "
                f"{fmt_int(packets['family_assignment_count'])} source-family assignments; "
                f"{fmt_int(superscription['context_unit_count'])} Psalm units carry "
                "superscription/performance/liturgical markers, including "
                f"{fmt_int(superscription['historical_notice_unit_count'])} historical "
                "notices and "
                f"{fmt_int(superscription['technical_term_unit_count'])} technical terms; "
                f"{fmt_int(cultural['domain_unit_count'])} units carry cultural/historical "
                f"domain markers across {fmt_int(cultural['domain_count'])} domains; "
                f"{fmt_int(poetic['high_pressure_unit_count'])} units carry high "
                "poetic/rhetorical pressure. The integration matrix joins "
                f"{fmt_int(context_integration['unit_count'])} Psalm units across "
                f"{fmt_int(context_integration['lens_count'])} context lenses and "
                f"flags {fmt_int(context_integration['high_pressure_unit_count'])} "
                "high-pressure units plus "
                f"{fmt_int(context_integration['doctoral_collision_unit_count'])} "
                "canon/culture/witness/reception collision units. Collision packets "
                f"turn those into {fmt_int(collision_packets['decision_row_count'])} "
                "pending reviewer decision rows across "
                f"{fmt_int(collision_packets['lane_count'])} lanes."
            ),
            blocking_gap=str(context_gate.get("blocking_gap", "")),
            next_action=str(context_gate.get("next_action", "")),
            source_artifacts=source_artifact_names(
                "source_packets",
                "claim_matrix",
                "superscription_context",
                "cultural_historical_atlas",
                "poetic_rhetorical_atlas",
                "context_integration",
                "collision_packets",
                "authority",
            ),
        ),
        requirement_row(
            requirement_id="REQ-05",
            requirement="Textual witness handling without overriding Hebrew basis",
            weight=8,
            score_pct=witness_gate.get("score_pct", 0),
            status=witness_gate.get("status"),
            evidence=(
                f"LXX coverage {fmt_pct(witness['lxx_coverage_pct'])}; "
                f"English witness coverage {fmt_pct(witness['english_witness_coverage_pct'])}; "
                f"{fmt_int(claim['textual_witness_pressure_unit_count'])} units carry "
                "textual-witness pressure controls; "
                f"mean English-witness divergence "
                f"{fmt_pct(witness_divergence['mean_english_witness_divergence_pct'])}; "
                f"{fmt_int(witness_divergence['high_divergence_unit_count'])} units "
                "are high-divergence; "
                f"{fmt_int(divine_name['witness_disagreement_unit_count'])} divine-title "
                "units have English witness rendering disagreement."
            ),
            blocking_gap=str(witness_gate.get("blocking_gap", "")),
            next_action=str(witness_gate.get("next_action", "")),
            source_artifacts=source_artifact_names(
                "witness",
                "witness_divergence",
                "divine_name_policy",
                "claim_matrix",
                "authority",
            ),
        ),
        requirement_row(
            requirement_id="REQ-06",
            requirement="Separated Jewish, Christian, and academic interpretive lanes",
            weight=10,
            score_pct=reception_score,
            evidence=(
                f"{fmt_int(reception['reception_sensitive_unit_count'])} reception-sensitive "
                "expanded units; "
                f"{fmt_int(reception['both_jewish_christian_frame_unit_count'])} require both "
                "Jewish and Christian frames; "
                f"{fmt_int(claim['jewish_christian_separation_unit_count'])} claim rows require "
                "explicit separation; reception divergence atlas top priority "
                f"{reception_divergence['top_priority_ref']} "
                f"({float(reception_divergence['top_priority_score']):.2f}); "
                f"{fmt_int(corpus_reception_signal['signal_unit_count'])} full-corpus "
                "units carry reception signal routing, including "
                f"{fmt_int(corpus_signal_new_candidates)} "
                "new high-pressure expansion candidates. The integration matrix flags "
                f"{fmt_int(context_integration['jewish_christian_separation_unit_count'])} "
                "full-corpus Jewish/Christian separation units and "
                f"{fmt_int(context_integration['multi_lens_unit_count'])} "
                "six-plus-lens review units. Collision packets include "
                f"{fmt_int(collision_packets['jewish_christian_packet_count'])} "
                "Jewish/Christian packet units and "
                f"{fmt_int(collision_packets['pending_decision_count'])} "
                "pending review decisions. The reception source packet workbook turns "
                f"{fmt_int(reception_source_packets['split_lane_unit_count'])} split-lane "
                "units into "
                f"{fmt_int(reception_source_packets['packet_count'])} separated Jewish, "
                "Christian, and academic packet rows. The interpretive tradition control "
                "matrix joins "
                f"{fmt_int(interpretive_control['unit_count'])} high-risk control units, "
                f"{fmt_int(interpretive_control['ancient_culture_pressure_unit_count'])} "
                "ancient-culture units, "
                f"{fmt_int(interpretive_control['textual_witness_pressure_unit_count'])} "
                "textual-witness units, and "
                f"{interpretive_forbidden_claim_units} "
                "reception-claim units that must stay out of translation wording."
            ),
            blocking_gap=(
                "Reception controls are routed, but Jewish and Christian source packets are not "
                "signed and cannot become translation wording authority."
            ),
            next_action=(
                "Fill the separated Jewish, Christian, and academic packet rows with cited "
                "source notes, then require Hebrew and theology reviewer signoff."
            ),
            source_artifacts=source_artifact_names(
                "reception_boundary",
                "reception_divergence",
                "reception_source_packets",
                "interpretive_tradition_control",
                "corpus_reception_signal",
                "adjudication",
                "claim_matrix",
                "context_integration",
                "collision_packets",
            ),
        ),
        requirement_row(
            requirement_id="REQ-07",
            requirement="Source acquisition, license, and reviewer-governed evidence packets",
            weight=9,
            score_pct=source_policy_score,
            evidence=(
                f"{fmt_int(bibliography['bibliography_source_count'])} bibliography rows; "
                f"{fmt_int(acquisition['candidate_count'])} source candidates; "
                f"{fmt_int(acquisition['machine_readable_candidate_count'])} machine-readable; "
                f"{fmt_int(acquisition['low_license_risk_candidate_count'])} low license risk; "
                "morphology-specific candidates "
                f"{fmt_int(morph_acquisition['morphology_candidate_count'])}, including "
                f"{fmt_int(morph_acquisition['low_license_risk_candidate_count'])} "
                "low-license-risk candidates and "
                f"{fmt_int(morph_acquisition['research_only_candidate_count'])} "
                "research-only candidate; OSHB pilot remote morphology coverage "
                f"{fmt_pct(oshb_pilot['remote_oshb_morph_coverage_pct'])} across "
                f"{fmt_int(oshb_pilot['mapped_non_psalm_book_count'])} non-Psalm books, "
                "but source approval remains "
                f"{oshb_pilot['source_approval_status']}; "
                f"{fmt_int(bibliography['blocked_authority_lane_count'])} source lanes "
                "authority-blocked; "
                f"{fmt_int(source_verification['reachable_url_count'])} of "
                f"{fmt_int(source_verification['url_source_count'])} official URLs reachable; "
                f"{fmt_int(source_verification['gap_count'])} verification gaps; "
                f"{fmt_int(source_verification['source_approval_count'])} source approvals. "
                "Reception source packets identify "
                f"{fmt_int(reception_source_packets['distinct_candidate_source_count'])} "
                "distinct Jewish/Christian/academic candidate source IDs, with "
                f"{fmt_int(reception_source_packets['reachable_candidate_source_count'])} "
                "reachable but "
                f"{fmt_int(reception_source_packets['source_approval_count'])} approved. "
                "The source authority ladder maps "
                f"{fmt_int(source_authority_ladder['unit_count'])} high-risk units to "
                f"{fmt_int(source_authority_ladder['source_family_count'])} source families, "
                f"{fmt_int(source_authority_ladder['candidate_reachable_count'])} reachable "
                "candidate sources, "
                f"{fmt_int(source_authority_ladder['critical_gap_unit_count'])} critical "
                "source-authority gaps, and "
                f"{fmt_int(source_authority_ladder['source_approval_count'])} source approvals."
            ),
            blocking_gap=(
                "Source candidates are identified, but license, provenance, and release decisions "
                "are still review templates rather than approvals."
            ),
            next_action=(
                "Create source manifests for approved candidates and complete license/provenance "
                "review rows before importing external data."
            ),
            source_artifacts=source_artifact_names(
                "source_acquisition",
                "morphology_acquisition",
                "oshb_alignment_pilot",
                "source_maturity",
                "bibliography",
                "source_verification",
                "source_authority_ladder",
                "reception_source_packets",
            ),
        ),
        requirement_row(
            requirement_id="REQ-08",
            requirement="Local model viability on 3090-class hardware or less",
            weight=7,
            score_pct=local_gate.get("score_pct", 0),
            status=local_gate.get("status"),
            evidence=(
                f"{fmt_int(local_selection['ready_local_candidate_count'])} of "
                f"{fmt_int(local_selection['candidate_count'])} candidates are ready locally; "
                f"best runnable candidate: {local_selection['best_runnable_candidate']}; "
                f"Gemma 4 26B repaired schema-valid rate "
                f"{fmt_pct(local_selection['gemma4_26b_repair_schema_valid_pct'])}. "
                "The doctoral bakeoff matrix ranks "
                f"{local_bakeoff['best_current_bakeoff_baseline']} as current measured "
                "baseline, "
                f"{local_bakeoff['best_trainable_base_if_asset_added']} as trainable "
                "target after exact asset intake, and "
                f"{local_bakeoff['best_hebrew_specialist_candidate']} as Hebrew-specialist "
                "challenger. The model training certification roadmap adds "
                f"{fmt_int(model_training_certification['candidate_count'])} candidates, "
                f"{fmt_int(model_training_certification['public_3090_known_fit_count'])} "
                "public 3090-fit rows, "
                f"{model_training_certification['recommended_frontier_intake']} as frontier "
                "intake, and "
                f"{fmt_int(model_training_certification['claim_text_allowed_now'])} "
                "text-authorized claim rows. The critical unit model cross-exam plan "
                "scopes "
                f"{fmt_int(critical_unit_model_cross_exam['planned_model_count'])} "
                "planned model profiles over "
                f"{fmt_int(critical_unit_model_cross_exam['critical_task_count'])} "
                "critical tasks."
            ),
            blocking_gap=str(local_gate.get("blocking_gap", "")),
            next_action=str(local_gate.get("next_action", "")),
            source_artifacts=source_artifact_names(
                "local_selection",
                "local_model_doctoral_bakeoff",
                "model_training_certification",
                "critical_unit_model_cross_exam",
                "authority",
            ),
        ),
        requirement_row(
            requirement_id="REQ-09",
            requirement="Exhaustive benchmark and cross-examination evidence",
            weight=9,
            score_pct=min(
                float(cross_exam_gate.get("score_pct", 0)),
                float(real_model_gate.get("score_pct", 0)),
            ),
            status=real_model_gate.get("status"),
            evidence=(
                f"{fmt_int(model_gap['expected_result_count'])} expected model rows; "
                f"{fmt_int(model_gap['submitted_result_count'])} submitted; "
                f"schema-valid expected coverage "
                f"{fmt_pct(model_gap['schema_valid_expected_pct'])}; "
                f"{fmt_int(model_gap['unit_without_schema_valid_count'])} units lack "
                "schema-valid evidence; "
                f"{fmt_int(reception_signal_benchmark['task_count'])} reception-signal "
                "supplement tasks add "
                f"{fmt_int(reception_signal_benchmark['planned_model_runs'])} planned "
                "model runs; "
                f"{fmt_int(reception_signal_cross_exam['packet_count'])} advisory "
                "cross-exam packets and "
                f"{fmt_int(reception_signal_cross_exam['execution_row_count'])} "
                "execution rows are generated; dry-run schema validity is "
                f"{fmt_pct(reception_signal_dry_run['schema_valid_pct'])}; "
                "real reception-signal smoke has "
                f"{fmt_int(reception_signal_real_smoke['attempt_count'])} attempts, "
                f"{fmt_int(reception_signal_real_smoke['schema_valid_attempt_count'])} "
                "schema-valid attempts, "
                f"{fmt_int(reception_signal_real_smoke['valid_model_task_count'])} "
                "valid model-task rows, and "
                f"{fmt_int(reception_signal_real_smoke['source_anchor_issue_count'])} "
                "source-anchor issue; "
                f"{fmt_int(canonical_intertext_benchmark['task_count'])} canonical-intertext "
                "tasks add "
                f"{fmt_int(canonical_intertext_benchmark['planned_model_runs'])} planned "
                "runs, "
                f"{fmt_int(canonical_intertext_cross_exam['packet_count'])} cross-exam "
                "packets, and "
                f"{fmt_int(canonical_intertext_cross_exam['execution_row_count'])} "
                "execution rows; canonical dry-run schema validity is "
                f"{fmt_pct(canonical_intertext_dry_run['schema_valid_pct'])}. Real "
                "canonical-intertext smoke has "
                f"{fmt_int(canonical_intertext_real_smoke['attempt_count'])} attempts, "
                f"{fmt_int(canonical_intertext_real_smoke['schema_valid_attempt_count'])} "
                "schema-valid attempts, "
                f"{fmt_int(canonical_intertext_real_smoke['valid_model_task_count'])} "
                "valid model-task rows, and "
                f"{fmt_int(canonical_intertext_real_smoke['source_anchor_issue_count'])} "
                "source-anchor issue; "
                f"{fmt_int(collision_benchmark['task_count'])} collision benchmark "
                "tasks add "
                f"{fmt_int(collision_benchmark['planned_model_runs'])} planned runs "
                "from "
                f"{fmt_int(collision_benchmark['selected_collision_unit_count'])} "
                "cross-lens collision units; collision companions add "
                f"{fmt_int(collision_benchmark_cross_exam['packet_count'])} advisory "
                "cross-exam packets, "
                f"{fmt_int(collision_benchmark_cross_exam['execution_row_count'])} "
                "execution rows, and dry-run schema validity "
                f"{fmt_pct(collision_benchmark_dry_run['schema_valid_pct'])}. Real "
                "collision smoke now has "
                f"{fmt_int(collision_real_smoke['attempt_count'])} attempts, "
                f"{fmt_int(collision_real_smoke['schema_valid_attempt_count'])} "
                "schema-valid attempts, "
                f"{fmt_int(collision_real_smoke['clean_schema_valid_attempt_count'])} "
                "clean source-anchored attempts, and "
                f"{fmt_int(collision_real_smoke['source_anchor_issue_count'])} "
                "source-anchor issues. The critical unit model cross-exam plan isolates "
                f"{fmt_int(critical_unit_model_cross_exam['critical_task_count'])} "
                "critical-unit tasks, "
                f"{fmt_int(critical_unit_model_cross_exam['expected_model_result_count'])} "
                "expected model-task rows, "
                f"{fmt_int(critical_unit_model_cross_exam['submitted_model_result_count'])} "
                "submitted, "
                f"{fmt_int(critical_unit_model_cross_exam['missing_model_result_count'])} "
                "missing, and "
                f"{fmt_int(critical_unit_model_cross_exam['cross_exam_execution_row_count'])} "
                "planned advisory cross-exam rows."
            ),
            blocking_gap=str(real_model_gate.get("blocking_gap", "")),
            next_action=str(real_model_gate.get("next_action", "")),
            source_artifacts=source_artifact_names(
                "model_gap",
                "quality_triage",
                "model_training_certification",
                "reception_signal_benchmark",
                "reception_signal_benchmark_cross_exam",
                "reception_signal_benchmark_dry_run_audit",
                "reception_signal_real_smoke",
                "canonical_intertext_benchmark",
                "canonical_intertext_benchmark_cross_exam",
                "canonical_intertext_benchmark_dry_run_audit",
                "canonical_intertext_real_smoke",
                "collision_benchmark",
                "collision_benchmark_cross_exam",
                "collision_benchmark_dry_run_audit",
                "collision_real_smoke",
                "critical_unit_model_cross_exam",
                "authority",
            ),
        ),
        requirement_row(
            requirement_id="REQ-10",
            requirement="Layer differentiation from gloss through lyric without semantic drift",
            weight=7,
            score_pct=max(0.0, 100.0 - float(layer["mean_word_jaccard_pct"]) / 2.0),
            evidence=(
                f"{fmt_int(layer['schema_valid_pair_count'])} schema-valid layer pairs; "
                f"{fmt_int(layer['exact_duplicate_pair_count'])} exact duplicates; "
                f"{fmt_int(layer['weak_layer_differentiation_pair_count'])} weak "
                "differentiation pairs; mean word Jaccard "
                f"{fmt_pct(layer['mean_word_jaccard_pct'])}; "
                f"{fmt_int(poetic['volitive_token_count'])} volitive tokens and "
                f"{fmt_int(poetic['adjacent_parallelism_proxy_unit_count'])} adjacent "
                "parallelism-proxy units require style-aware layer review."
            ),
            blocking_gap=(
                "Layer outputs remain too similar in many pairs, so lyric and concept layers are "
                "not yet reliable style-separated evidence."
            ),
            next_action=(
                "Run the grammatical-literal repair prompts across the expanded suite and re-score "
                "layer differentiation before reviewer signoff."
            ),
            source_artifacts=source_artifact_names(
                "layer_consistency",
                "quality_triage",
                "poetic_rhetorical_atlas",
            ),
        ),
        requirement_row(
            requirement_id="REQ-11",
            requirement="Human scholarly signoff and release accountability",
            weight=11,
            score_pct=signoff_gate.get("score_pct", review["review_completion_pct"]),
            status="blocked",
            hard_blocked=True,
            evidence=(
                f"{fmt_int(review['total_review_row_count'])} review rows generated; "
                f"{fmt_int(review['completed_review_row_count'])} completed; "
                f"completion {fmt_pct(review['review_completion_pct'])}; "
                f"{fmt_int(review['blocked_gate_count'])} signoff gates blocked; "
                f"{fmt_int(priority_dossier_atlas['unit_count'])} integrated dossier "
                "units queued for doctoral review; reception-signal supplement review "
                "adds "
                f"{fmt_int(reception_signal_review['projected_human_review_rows'])} "
                "projected human rows; canonical-intertext review adds "
                f"{fmt_int(canonical_intertext_review['projected_human_review_rows'])} "
                "projected human rows; collision benchmark review adds "
                f"{fmt_int(collision_benchmark_review['projected_human_review_rows'])} "
                "projected human rows; the critical unit decision dossier carries "
                f"{fmt_int(critical_unit_decision['total_packet_review_row_count'])} "
                "packet review rows with "
                f"{fmt_int(critical_unit_decision['completed_review_row_count'])} "
                "completed. The critical unit review execution plan converts these into "
                f"{fmt_int(critical_unit_review_execution['total_role_review_row_count'])} "
                "role/source rows across "
                f"{fmt_int(critical_unit_review_execution['blocked_wave_count'])} blocked "
                f"waves and {fmt_int(critical_unit_review_execution['blocked_gate_count'])} "
                "blocked execution gates."
            ),
            blocking_gap=str(signoff_gate.get("blocking_gap", "")),
            next_action=str(signoff_gate.get("next_action", "")),
            source_artifacts=source_artifact_names(
                "priority_dossier_atlas",
                "review_workbook",
                "reception_signal_benchmark_review",
                "canonical_intertext_benchmark_review",
                "collision_benchmark_review",
                "critical_unit_decision_dossier",
                "critical_unit_review_execution",
                "authority",
            ),
        ),
        requirement_row(
            requirement_id="REQ-12",
            requirement="Canonical/release authority",
            weight=10,
            score_pct=release_gate.get("score_pct", 0),
            status="blocked",
            hard_blocked=True,
            evidence=(
                "Authority readiness "
                f"{fmt_pct(data['authority']['summary']['authority_readiness_score_pct'])}; "
                f"hard blockers: {', '.join(data['authority']['summary']['hard_blockers'])}; "
                f"{fmt_int(quality['contextual_review_required_count'])} model outputs require "
                "contextual review. The translation accuracy certification matrix shows "
                f"{fmt_pct(translation_accuracy['weighted_evidence_maturity_pct'])} "
                "weighted evidence maturity, "
                f"{fmt_pct(translation_accuracy['weighted_certification_readiness_pct'])} "
                "certification readiness, "
                f"{fmt_int(translation_accuracy['blocked_gate_count'])} blocked gates, and "
                f"{fmt_int(translation_accuracy['release_authorized_dimension_count'])} "
                "release-authorized dimensions. The critical unit decision dossier adds "
                f"{fmt_int(critical_unit_decision['unit_count'])} decision units, "
                f"{fmt_int(critical_unit_decision['blocked_lane_row_count'])} blocked lanes, "
                f"{fmt_int(critical_unit_decision['text_blocked_unit_count'])} text-blocked "
                f"units, and top unit {critical_unit_decision['top_decision_ref']}. "
                "The critical unit review execution plan shows "
                f"{fmt_int(critical_unit_review_execution['gate_count'])} execution gates, "
                f"{fmt_int(critical_unit_review_execution['blocked_gate_count'])} blocked, "
                f"with {fmt_pct(critical_unit_review_execution['review_completion_pct'])} "
                "critical-unit review completion."
            ),
            blocking_gap=str(release_gate.get("blocking_gap", "")),
            next_action=str(release_gate.get("next_action", "")),
            source_artifacts=source_artifact_names(
                "authority",
                "review_workbook",
                "quality_triage",
                "translation_accuracy_certification",
                "critical_unit_decision_dossier",
                "critical_unit_review_execution",
            ),
        ),
    ]


def build_blocker_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    lexeme = data["lexeme"]["summary"]
    morph_gap = data["morphology_gap"]["summary"]
    morph_acquisition = data["morphology_acquisition"]["summary"]
    oshb_pilot = data["oshb_alignment_pilot"]["summary"]
    oshb_exception = data["oshb_exception_review"]["summary"]
    oshb_taxonomy = data["oshb_exception_taxonomy"]["summary"]
    oshb_simulation = data["oshb_mapping_rule_simulation"]["summary"]
    morph_unlock = data["morphology_unlock_matrix"]["summary"]
    critical_morph_unlock = data["critical_unit_morphology_unlock"]["summary"]
    model_gap = data["model_gap"]["summary"]
    review = data["review_workbook"]["summary"]
    witness_divergence = data["witness_divergence"]["summary"]
    divine_name = data["divine_name_policy"]["summary"]
    superscription = data["superscription_context"]["summary"]
    cultural = data["cultural_historical_atlas"]["summary"]
    poetic = data["poetic_rhetorical_atlas"]["summary"]
    corpus_reception_signal = data["corpus_reception_signal"]["summary"]
    corpus_signal_new_candidates = corpus_reception_signal[
        "new_high_pressure_expansion_candidate_count"
    ]
    reception_signal_benchmark = data["reception_signal_benchmark"]["summary"]
    reception_signal_benchmark_units = fmt_int(
        reception_signal_benchmark["selected_reception_signal_unit_count"]
    )
    reception_signal_cross_exam = data["reception_signal_benchmark_cross_exam"]["summary"]
    reception_signal_dry_run = data["reception_signal_benchmark_dry_run_audit"]["summary"]
    reception_signal_review = data["reception_signal_benchmark_review"]["summary"]
    reception_signal_real_smoke = data["reception_signal_real_smoke"]["summary"]
    reception_signal_missing_model_tasks = fmt_int(
        reception_signal_real_smoke["missing_model_task_count_after_smoke"]
    )
    canonical_intertext_benchmark = data["canonical_intertext_benchmark"]["summary"]
    canonical_intertext_benchmark_units = fmt_int(
        canonical_intertext_benchmark["selected_intertext_unit_count"]
    )
    canonical_intertext_remaining_candidates = fmt_int(
        canonical_intertext_benchmark["remaining_intertext_candidate_count"]
    )
    canonical_intertext_cross_exam = data["canonical_intertext_benchmark_cross_exam"]["summary"]
    canonical_intertext_dry_run = data["canonical_intertext_benchmark_dry_run_audit"]["summary"]
    canonical_intertext_review = data["canonical_intertext_benchmark_review"]["summary"]
    canonical_intertext_real_smoke = data["canonical_intertext_real_smoke"]["summary"]
    canonical_intertext_missing_model_tasks = fmt_int(
        canonical_intertext_real_smoke["missing_model_task_count_after_smoke"]
    )
    cross_reference = data["canonical_cross_reference"]["summary"]
    reception_divergence = data["reception_divergence"]["summary"]
    reception_source_packets = data["reception_source_packets"]["summary"]
    interpretive_control = data["interpretive_tradition_control"]["summary"]
    interpretive_forbidden_claim_units = fmt_int(
        interpretive_control["translation_text_forbidden_reception_claim_units"]
    )
    claim_traceability = data["claim_traceability"]["summary"]
    translation_accuracy = data["translation_accuracy_certification"]["summary"]
    critical_unit_decision = data["critical_unit_decision_dossier"]["summary"]
    critical_unit_review_execution = data["critical_unit_review_execution"]["summary"]
    critical_unit_model_cross_exam = data["critical_unit_model_cross_exam"]["summary"]
    context_integration = data["context_integration"]["summary"]
    collision_packets = data["collision_packets"]["summary"]
    collision_benchmark = data["collision_benchmark"]["summary"]
    collision_benchmark_cross_exam = data["collision_benchmark_cross_exam"]["summary"]
    collision_benchmark_dry_run = data["collision_benchmark_dry_run_audit"]["summary"]
    collision_benchmark_review = data["collision_benchmark_review"]["summary"]
    collision_real_smoke = data["collision_real_smoke"]["summary"]
    contextual_real_model_evidence = data["contextual_real_model_evidence_matrix"]["summary"]
    priority_dossier_atlas = data["priority_dossier_atlas"]["summary"]
    acquisition = data["source_acquisition"]["summary"]
    source_verification = data["source_verification"]["summary"]
    source_authority_ladder = data["source_authority_ladder"]["summary"]
    hebrew_token_defense = data["hebrew_token_defense"]["summary"]
    semantic_referent = data["semantic_referent_roadmap"]["summary"]
    source_maturity = data["source_maturity"]["summary"]
    layer = data["layer_consistency"]["summary"]
    quality = data["quality_triage"]["summary"]
    local_selection = data["local_selection"]["summary"]
    local_bakeoff = data["local_model_doctoral_bakeoff"]["summary"]
    model_training_certification = data["model_training_certification"]["summary"]
    public_training_fit_count = fmt_int(
        model_training_certification["public_3090_training_or_probable_fit_count"]
    )
    authority_path = data["authority_critical_path"]["summary"]

    rows = [
        {
            "blocker_id": "BLK-01",
            "severity": "critical",
            "blocker": "Human scholarly review is not completed.",
            "evidence": (
                f"{fmt_int(review['completed_review_row_count'])} of "
                f"{fmt_int(review['total_review_row_count'])} review rows are completed. "
                "The authority critical path has "
                f"{fmt_int(authority_path['blocked_phase_count'])} blocked phases, "
                f"{fmt_int(authority_path['blocked_gate_row_count'])} blocked gates, "
                f"{fmt_int(authority_path['projected_model_human_review_rows'])} "
                "projected model-human review rows, and top reviewer load "
                f"{authority_path['top_reviewer_role']} with "
                f"{fmt_int(authority_path['top_reviewer_role_row_count'])} rows."
            ),
            "affected_requirement_ids": [
                "REQ-04",
                "REQ-05",
                "REQ-06",
                "REQ-07",
                "REQ-11",
                "REQ-12",
            ],
            "next_action": (
                "Assign reviewers and complete source-packet, source-acquisition, and release rows."
            ),
        },
        {
            "blocker_id": "BLK-02",
            "severity": "critical",
            "blocker": "Release authority is blocked.",
            "evidence": (
                "Authority hard blockers are "
                + ", ".join(data["authority"]["summary"]["hard_blockers"])
                + "."
            ),
            "affected_requirement_ids": ["REQ-11", "REQ-12"],
            "next_action": (
                "Do not promote generated outputs to canonical until review and audit "
                "records exist."
            ),
        },
        {
            "blocker_id": "BLK-03",
            "severity": "hard",
            "blocker": "Whole-Tanakh morphology is not available beyond Psalms.",
            "evidence": (
                f"{fmt_int(morph_gap['local_non_psalm_books_with_hebrew_morphology'])} "
                "non-Psalm books have local Hebrew morphology; outside Strong context "
                f"{fmt_pct(morph_gap['outside_strong_context_token_pct'])}; "
                "first recommended import is "
                f"{morph_acquisition['recommended_first_import_candidate']}; "
                "OSHB pilot estimates "
                f"{fmt_int(oshb_pilot['estimated_non_psalm_morphology_books_if_approved'])} "
                "non-Psalm books could be covered if approved. The unlock matrix "
                "projects "
                f"{fmt_int(morph_unlock['unlockable_priority_unit_count'])} priority "
                "units could become review-ready after approval/import, with "
                f"{fmt_int(morph_unlock['exception_review_row_count'])} exception rows, "
                f"{fmt_pct(morph_unlock['candidate_rule_reduction_pct'])} candidate "
                "rule reduction, and source approval still absent. The critical-unit "
                "morphology plan narrows the immediate authority impact to "
                f"{fmt_int(critical_morph_unlock['critical_unit_count'])} critical units, "
                "with "
                f"{fmt_int(critical_morph_unlock['projected_review_ready_critical_unit_count'])} "
                "projected review-ready after approval/import."
            ),
            "affected_requirement_ids": ["REQ-02", "REQ-03"],
            "next_action": (
                "Extend OSHB or comparable whole-Tanakh morphology into the local index."
            ),
        },
        {
            "blocker_id": "BLK-04",
            "severity": "hard",
            "blocker": "Real model evidence is too sparse for authority claims.",
            "evidence": (
                f"{fmt_int(model_gap['submitted_result_count'])} submitted rows out of "
                f"{fmt_int(model_gap['expected_result_count'])}; schema-valid expected coverage "
                f"{fmt_pct(model_gap['schema_valid_expected_pct'])}. The contextual "
                "real-model matrix adds "
                f"{fmt_int(contextual_real_model_evidence['attempt_count'])} measured "
                "canonical/reception/collision attempts with "
                f"{fmt_int(contextual_real_model_evidence['clean_source_anchored_count'])} "
                "clean source-anchored rows, "
                f"{fmt_int(contextual_real_model_evidence['source_anchor_issue_count'])} "
                "source-anchor issues, and only "
                f"{fmt_pct(contextual_real_model_evidence['valid_model_task_coverage_pct'])} "
                "contextual planned-row coverage. The doctoral bakeoff matrix keeps "
                f"{local_bakeoff['best_current_bakeoff_baseline']} as the current measured "
                "baseline, but only "
                f"{fmt_pct(local_bakeoff['contextual_valid_model_task_coverage_pct'])} "
                "of contextual planned rows are covered. The model training certification "
                "roadmap keeps certification "
                f"{model_training_certification['certification_status']}, with "
                f"{fmt_pct(model_training_certification['valid_model_task_coverage_pct'])} "
                "valid model-task coverage."
            ),
            "affected_requirement_ids": ["REQ-08", "REQ-09", "REQ-12"],
            "next_action": (
                "Run the expanded benchmark suite across selected local and cross-exam models."
            ),
        },
        {
            "blocker_id": "BLK-05",
            "severity": "high",
            "blocker": "Layer differentiation remains weak.",
            "evidence": (
                f"{fmt_int(layer['exact_duplicate_pair_count'])} exact duplicate pairs and "
                f"{fmt_int(layer['weak_layer_differentiation_pair_count'])} weak pairs; "
                f"mean Jaccard {fmt_pct(layer['mean_word_jaccard_pct'])}."
            ),
            "affected_requirement_ids": ["REQ-09", "REQ-10"],
            "next_action": (
                "Apply the layer remediation prompts, then compare repaired outputs with reviewers."
            ),
        },
        {
            "blocker_id": "BLK-06",
            "severity": "high",
            "blocker": "Source acquisition is planned but not approved.",
            "evidence": (
                f"{fmt_int(acquisition['candidate_count'])} candidates; "
                f"{fmt_int(acquisition['blocked_gate_count'])} blocked gates; "
                f"{fmt_int(acquisition['high_license_risk_candidate_count'])} "
                "high-license-risk candidates. The source authority ladder shows "
                f"{fmt_int(source_authority_ladder['critical_gap_unit_count'])} "
                "critical unit-level source gaps, "
                f"{fmt_int(source_authority_ladder['candidate_reachable_count'])} of "
                f"{fmt_int(source_authority_ladder['candidate_source_count'])} reachable "
                "candidate sources, and "
                f"{fmt_int(source_authority_ladder['source_approval_count'])} source approvals."
            ),
            "affected_requirement_ids": ["REQ-04", "REQ-06", "REQ-07"],
            "next_action": (
                "Complete license/provenance triage before ingesting external contextual sources."
            ),
        },
        {
            "blocker_id": "BLK-07",
            "severity": "high",
            "blocker": "Source maturity is not authority maturity.",
            "evidence": (
                f"{fmt_int(source_maturity['strong_evidence_lane_count'])} strong evidence lanes "
                f"out of {fmt_int(source_maturity['lane_count'])}; "
                f"{fmt_int(source_maturity['blocked_authority_lane_count'])} "
                "authority-blocked lanes; "
                f"mean authority score {fmt_pct(source_maturity['mean_authority_score_pct'])}. "
                "The source ladder's mean unit source-readiness score is "
                f"{fmt_pct(source_authority_ladder['mean_source_authority_readiness_pct'])}, "
                "with "
                f"{fmt_int(source_authority_ladder['completed_review_row_count'])} completed "
                "review rows."
            ),
            "affected_requirement_ids": ["REQ-04", "REQ-05", "REQ-06", "REQ-07", "REQ-12"],
            "next_action": (
                "Convert source lanes into signed source packets with role-specific decisions."
            ),
        },
        {
            "blocker_id": "BLK-08",
            "severity": "medium",
            "blocker": "Semantic role and referent enrichment are absent.",
            "evidence": (
                f"Semantic role {fmt_pct(lexeme['semantic_role_coverage_pct'])}; "
                f"referent {fmt_pct(lexeme['referent_coverage_pct'])}. The Hebrew "
                "token defense matrix shows "
                f"{fmt_int(hebrew_token_defense['missing_semantic_role_token_count'])} of "
                f"{fmt_int(hebrew_token_defense['token_count'])} exhibit tokens missing "
                "semantic role and "
                f"{fmt_int(hebrew_token_defense['missing_referent_token_count'])} missing "
                "referent enrichment. The semantic/referent roadmap expands that to "
                f"{fmt_int(semantic_referent['missing_semantic_role_token_count'])} of "
                f"{fmt_int(semantic_referent['token_count'])} Psalm tokens missing "
                "semantic role, "
                f"{fmt_int(semantic_referent['missing_referent_token_count'])} missing "
                "referent, and "
                f"{fmt_int(semantic_referent['critical_enrichment_token_count'])} "
                "critical enrichment tokens."
            ),
            "affected_requirement_ids": ["REQ-02", "REQ-03"],
            "next_action": (
                "Add referent and semantic-role enrichment before making high-trust "
                "discourse claims."
            ),
        },
        {
            "blocker_id": "BLK-09",
            "severity": "watch",
            "blocker": "Gemma-family schema repair is promising but not authoritative.",
            "evidence": (
                f"{local_selection['best_runnable_candidate']} is locally runnable; "
                f"Gemma repair schema-valid rate "
                f"{fmt_pct(local_selection['gemma4_26b_repair_schema_valid_pct'])}; "
                "failed gates include "
                + ", ".join(local_selection["gemma4_26b_repair_failed_gates"])
                + ". The doctoral bakeoff matrix marks Gemma 4 26B as "
                f"{local_bakeoff['gemma4_26b_status']}, selects "
                f"{local_bakeoff['best_trainable_base_if_asset_added']} as the best "
                "trainable target after exact asset intake, and selects "
                f"{local_bakeoff['best_hebrew_specialist_candidate']} as the Hebrew-specialist "
                "challenger."
            ),
            "affected_requirement_ids": ["REQ-08", "REQ-09"],
            "next_action": (
                "Keep Gemma in the bake-off, but require source-anchor and layer gates "
                "before trust."
            ),
        },
        {
            "blocker_id": "BLK-10",
            "severity": "watch",
            "blocker": "Most valid model outputs still need contextual review.",
            "evidence": (
                f"{fmt_int(quality['contextual_review_required_count'])} of "
                f"{fmt_int(quality['candidate_row_count'])} triage candidates require "
                "contextual review."
            ),
            "affected_requirement_ids": ["REQ-09", "REQ-11", "REQ-12"],
            "next_action": "Use quality triage as reviewer queue input, not as release proof.",
        },
    ]
    if source_verification["gap_count"]:
        rows.append(
            {
                "blocker_id": "BLK-11",
                "severity": "medium",
                "blocker": "Live source verification still has unresolved URL gaps.",
                "evidence": (
                    f"{fmt_int(source_verification['reachable_url_count'])} of "
                    f"{fmt_int(source_verification['url_source_count'])} official URLs "
                    f"reachable; {fmt_int(source_verification['gap_count'])} verification "
                    f"gaps; {fmt_int(source_verification['source_approval_count'])} "
                    "source approvals."
                ),
                "affected_requirement_ids": ["REQ-07", "REQ-12"],
                "next_action": (
                    "Resolve unreachable or missing official source pages, then record "
                    "license/provenance decisions in review rows."
                ),
            }
        )
    if witness_divergence["high_priority_unit_count"]:
        rows.append(
            {
                "blocker_id": "BLK-12",
                "severity": "watch",
                "blocker": "English witness divergence adds reviewer adjudication pressure.",
                "evidence": (
                    f"Mean English-witness divergence is "
                    f"{fmt_pct(witness_divergence['mean_english_witness_divergence_pct'])}; "
                    f"{fmt_int(witness_divergence['high_divergence_unit_count'])} units "
                    "are high-divergence; "
                    f"{fmt_int(witness_divergence['divine_name_disagreement_unit_count'])} "
                    "units have divine-name rendering disagreement."
                ),
                "affected_requirement_ids": ["REQ-05", "REQ-06", "REQ-12"],
                "next_action": (
                    "Route high-divergence and divine-name-disagreement units to Hebrew, "
                    "theology, and alignment reviewers before canonical wording decisions."
                ),
            }
        )
    if divine_name["witness_disagreement_unit_count"]:
        rows.append(
            {
                "blocker_id": "BLK-13",
                "severity": "watch",
                "blocker": "Divine-name and divine-title policy is not yet signed off.",
                "evidence": (
                    f"{fmt_int(divine_name['divine_title_unit_count'])} Psalm units "
                    f"contain divine-name/title tokens; "
                    f"{fmt_int(divine_name['witness_disagreement_unit_count'])} "
                    "have English witness rendering disagreement; "
                    f"{fmt_int(divine_name['yhwh_adonai_lord_stack_unit_count'])} "
                    "have YHWH plus Adonai/Lord stack pressure."
                ),
                "affected_requirement_ids": ["REQ-02", "REQ-05", "REQ-06", "REQ-12"],
                "next_action": (
                    "Finalize divine-name/title rendering policy and require Hebrew, "
                    "theology, alignment, and release review for priority rows."
                ),
            }
        )
    if superscription["context_unit_count"]:
        rows.append(
            {
                "blocker_id": "BLK-14",
                "severity": "watch",
                "blocker": "Superscription and liturgical context is routed but not signed off.",
                "evidence": (
                    f"{fmt_int(superscription['context_unit_count'])} Psalm units contain "
                    "superscription, performance, attribution, liturgical, or historical "
                    f"context markers; {fmt_int(superscription['historical_notice_unit_count'])} "
                    "carry historical-notice pressure; "
                    f"{fmt_int(superscription['technical_term_unit_count'])} include technical "
                    "heading terms. Top priority: "
                    f"{superscription['top_priority_ref']} "
                    f"({float(superscription['top_priority_score']):.2f})."
                ),
                "affected_requirement_ids": ["REQ-04", "REQ-05", "REQ-06", "REQ-12"],
                "next_action": (
                    "Route top superscription rows to Hebrew, ancient-culture, textual, "
                    "and theology reviewers before allowing heading evidence to affect "
                    "translation wording or notes."
                ),
            }
        )
    if cultural["domain_unit_count"]:
        rows.append(
            {
                "blocker_id": "BLK-15",
                "severity": "watch",
                "blocker": "Cultural and historical domain routing is not reviewer signoff.",
                "evidence": (
                    f"{fmt_int(cultural['domain_unit_count'])} Psalm units carry "
                    "cultural/historical domain markers; "
                    f"{fmt_int(cultural['domain_token_count'])} domain-token assignments; "
                    f"{fmt_int(cultural['high_priority_unit_count'])} high-priority "
                    "domain units. Top priority: "
                    f"{cultural['top_priority_ref']} "
                    f"({float(cultural['top_priority_score']):.2f})."
                ),
                "affected_requirement_ids": ["REQ-04", "REQ-06", "REQ-07", "REQ-12"],
                "next_action": (
                    "Use the cultural atlas to assign ancient-context and reception "
                    "review packets; do not use domain tags as proof of historical "
                    "background or interpretive authority."
                ),
            }
        )
    if cross_reference["cross_reference_unit_count"]:
        rows.append(
            {
                "blocker_id": "BLK-16",
                "severity": "watch",
                "blocker": "Whole-Tanakh cross-reference evidence is surface-form only.",
                "evidence": (
                    f"{fmt_int(cross_reference['cross_reference_unit_count'])} Psalm units "
                    "have UXLC normalized surface-form anchors outside Psalms; "
                    f"{fmt_int(cross_reference['three_division_unit_count'])} have Torah, "
                    "Prophets, and non-Psalm Writings evidence; "
                    f"{fmt_int(cross_reference['high_value_anchor_unit_count'])} include "
                    "rarer multi-division anchors. Top priority: "
                    f"{cross_reference['top_priority_ref']} "
                    f"({float(cross_reference['top_priority_score']):.2f})."
                ),
                "affected_requirement_ids": ["REQ-03", "REQ-04", "REQ-12"],
                "next_action": (
                    "Use cross-reference anchors for reviewer research queues, then add "
                    "lemma/sense-aware whole-Tanakh morphology before treating them as "
                    "translation authority."
                ),
            }
        )
    if reception_divergence["jewish_christian_separation_unit_count"]:
        rows.append(
            {
                "blocker_id": "BLK-17",
                "severity": "watch",
                "blocker": "Jewish and Christian reception lanes are routed but unsigned.",
                "evidence": (
                    f"{fmt_int(reception_divergence['unit_count'])} expanded units have "
                    "direct reception-boundary analysis; "
                    f"{fmt_int(reception_divergence['jewish_christian_separation_unit_count'])} "
                    "require separated Jewish/Christian lanes; "
                    f"{fmt_int(reception_divergence['academic_comparison_unit_count'])} "
                    "require academic comparison; top priority: "
                    f"{reception_divergence['top_priority_ref']} "
                    f"({float(reception_divergence['top_priority_score']):.2f}). "
                    "The reception source packet workbook now expands "
                    f"{fmt_int(reception_source_packets['split_lane_unit_count'])} "
                    "split-lane units into "
                    f"{fmt_int(reception_source_packets['packet_count'])} Jewish, "
                    "Christian, and academic packet rows, but completed packet reviews "
                    f"remain {fmt_int(reception_source_packets['completed_packet_review_count'])}. "
                    "The interpretive tradition control matrix keeps "
                    f"{interpretive_forbidden_claim_units} "
                    "reception-claim units out of translation wording, routes "
                    f"{fmt_int(interpretive_control['packet_count'])} packets, and still has "
                    f"{fmt_int(interpretive_control['source_approval_count'])} source approvals."
                ),
                "affected_requirement_ids": ["REQ-06", "REQ-07", "REQ-12"],
                "next_action": (
                    "Fill and sign the Jewish, Christian, and academic packet rows, "
                    "then keep reception claims out of translation wording unless Hebrew "
                    "and theology reviewers explicitly approve the impact."
                ),
            }
        )
    if priority_dossier_atlas["unit_count"]:
        rows.append(
            {
                "blocker_id": "BLK-18",
                "severity": "watch",
                "blocker": "Integrated priority dossiers are a queue, not signoff.",
                "evidence": (
                    f"{fmt_int(priority_dossier_atlas['unit_count'])} units are in the "
                    "doctoral dossier atlas; "
                    f"{fmt_int(priority_dossier_atlas['critical_unit_count'])} are critical; "
                    f"{fmt_int(priority_dossier_atlas['jewish_christian_separation_unit_count'])} "
                    "require separated Jewish/Christian lanes; mean authority score "
                    f"{fmt_pct(priority_dossier_atlas['mean_authority_score_pct'])}. "
                    f"Top priority: {priority_dossier_atlas['top_priority_ref']} "
                    f"({float(priority_dossier_atlas['top_priority_score']):.2f})."
                ),
                "affected_requirement_ids": ["REQ-04", "REQ-06", "REQ-09", "REQ-11", "REQ-12"],
                "next_action": (
                    "Use the dossier atlas as the doctoral review assignment queue; "
                    "collect role decisions, corrections, and release signoff before "
                    "accepting any generated wording."
                ),
            }
        )
    if poetic["high_pressure_unit_count"]:
        rows.append(
            {
                "blocker_id": "BLK-19",
                "severity": "watch",
                "blocker": "Poetic and rhetorical pressure is routed but not signed off.",
                "evidence": (
                    f"{fmt_int(poetic['high_pressure_unit_count'])} Psalm units are "
                    "high poetic/rhetorical pressure; "
                    f"{fmt_int(poetic['volitive_unit_count'])} contain volitive mood "
                    "pressure; "
                    f"{fmt_int(poetic['adjacent_parallelism_proxy_unit_count'])} have "
                    "adjacent lexical-overlap parallelism proxies; top priority: "
                    f"{poetic['top_priority_ref']} "
                    f"({float(poetic['top_priority_score']):.2f})."
                ),
                "affected_requirement_ids": ["REQ-04", "REQ-10", "REQ-11", "REQ-12"],
                "next_action": (
                    "Route high-pressure rows to Hebrew, poetic, lyric, alignment, "
                    "and relevant textual/theology reviewers before accepting lyric "
                    "or parallelism-layer wording."
                ),
            }
        )
    if corpus_signal_new_candidates:
        rows.append(
            {
                "blocker_id": "BLK-20",
                "severity": "watch",
                "blocker": "Corpus-wide reception signals are routed but unsigned.",
                "evidence": (
                    f"{fmt_int(corpus_reception_signal['signal_unit_count'])} Psalm "
                    "units carry reception signal routing; "
                    f"{fmt_int(corpus_reception_signal['high_pressure_unit_count'])} "
                    "are high pressure; "
                    f"{fmt_int(corpus_signal_new_candidates)} "
                    "high-pressure candidates are outside the explicit reception-divergence "
                    "rows. Top priority: "
                    f"{corpus_reception_signal['top_priority_ref']} "
                    f"({float(corpus_reception_signal['top_priority_score']):.2f})."
                ),
                "affected_requirement_ids": ["REQ-06", "REQ-07", "REQ-11", "REQ-12"],
                "next_action": (
                    "Expand separated Jewish, Christian, academic, Hebrew-source, and "
                    "textual-witness review packets for the high-pressure corpus signal queue."
                ),
            }
        )
    if reception_signal_benchmark["task_count"]:
        rows.append(
            {
                "blocker_id": "BLK-21",
                "severity": "watch",
                "blocker": (
                    "Reception-signal supplement has real smoke evidence but no scaled "
                    "model evidence or source signoff."
                ),
                "evidence": (
                    f"{fmt_int(reception_signal_benchmark['task_count'])} supplement "
                    "tasks cover "
                    f"{reception_signal_benchmark_units} "
                    "new reception-signal units and "
                    f"{fmt_int(reception_signal_benchmark['planned_model_runs'])} planned "
                    "model runs; dry-run audit has "
                    f"{fmt_int(reception_signal_dry_run['schema_valid_result_count'])} "
                    "schema-valid placeholder rows; "
                    f"{fmt_int(reception_signal_cross_exam['packet_count'])} advisory "
                    "cross-exam packets and "
                    f"{fmt_int(reception_signal_review['projected_human_review_rows'])} "
                    "human review rows are projected; "
                    f"{fmt_int(reception_signal_real_smoke['attempt_count'])} real "
                    "smoke attempts produced "
                    f"{fmt_int(reception_signal_real_smoke['schema_valid_attempt_count'])} "
                    "schema-valid attempts and "
                    f"{fmt_int(reception_signal_real_smoke['valid_model_task_count'])} "
                    "valid model-task rows, with "
                    f"{fmt_int(reception_signal_real_smoke['source_anchor_issue_count'])} "
                    "source-anchor issue; "
                    f"{reception_signal_missing_model_tasks} planned model-task rows "
                    "remain missing."
                ),
                "affected_requirement_ids": ["REQ-06", "REQ-09", "REQ-11", "REQ-12"],
                "next_action": (
                    "Run the reception-signal supplement across selected local and "
                    "cross-exam models, then score schema validity, source anchoring, "
                    "reception separation, and reviewer workload."
                ),
            }
        )
    if canonical_intertext_benchmark["task_count"]:
        rows.append(
            {
                "blocker_id": "BLK-22",
                "severity": "watch",
                "blocker": (
                    "Canonical-intertext supplement has real smoke evidence but no scaled "
                    "model evidence or source signoff."
                ),
                "evidence": (
                    f"{fmt_int(canonical_intertext_benchmark['task_count'])} supplement "
                    "tasks cover "
                    f"{canonical_intertext_benchmark_units} "
                    "three-division whole-Tanakh units and "
                    f"{fmt_int(canonical_intertext_benchmark['planned_model_runs'])} planned "
                    "model runs; dry-run audit has "
                    f"{fmt_int(canonical_intertext_dry_run['schema_valid_result_count'])} "
                    "schema-valid placeholder rows; "
                    f"{fmt_int(canonical_intertext_cross_exam['packet_count'])} advisory "
                    "cross-exam packets and "
                    f"{fmt_int(canonical_intertext_review['projected_human_review_rows'])} "
                    "human review rows are projected; "
                    f"{fmt_int(canonical_intertext_real_smoke['attempt_count'])} real "
                    "smoke attempts produced "
                    f"{fmt_int(canonical_intertext_real_smoke['schema_valid_attempt_count'])} "
                    "schema-valid attempts and "
                    f"{fmt_int(canonical_intertext_real_smoke['valid_model_task_count'])} "
                    "valid model-task rows, with "
                    f"{fmt_int(canonical_intertext_real_smoke['source_anchor_issue_count'])} "
                    "source-anchor issue; "
                    f"{canonical_intertext_missing_model_tasks} "
                    "planned model-task rows remain missing; "
                    f"{canonical_intertext_remaining_candidates} "
                    "eligible high-value candidates remain outside this supplement."
                ),
                "affected_requirement_ids": ["REQ-03", "REQ-09", "REQ-11", "REQ-12"],
                "next_action": (
                    "Run the canonical-intertext supplement across selected local and "
                    "cross-exam models, then require reviewers to keep surface-form "
                    "anchors as context unless Hebrew morphology, syntax, and source "
                    "signoff justify a translation effect."
                ),
            }
        )
    if morph_acquisition["blocked_gate_count"] or morph_acquisition["not_started_gate_count"]:
        rows.append(
            {
                "blocker_id": "BLK-23",
                "severity": "hard",
                "blocker": (
                    "Whole-Tanakh morphology acquisition readiness is generated, "
                    "but no import or source approval gate has passed."
                ),
                "evidence": (
                    f"{fmt_int(morph_acquisition['morphology_candidate_count'])} "
                    "morphology candidates are ranked; "
                    f"{fmt_int(morph_acquisition['low_license_risk_candidate_count'])} "
                    "are low license risk; "
                    f"{fmt_int(morph_acquisition['blocked_gate_count'])} gates are "
                    "blocked and "
                    f"{fmt_int(morph_acquisition['not_started_gate_count'])} gates are "
                    "not started. Local non-Psalm morphology coverage remains "
                    f"{fmt_pct(morph_acquisition['local_non_psalm_morphology_coverage_pct'])}. "
                    "OSHB pilot mean sequence similarity is "
                    f"{fmt_pct(oshb_pilot['mean_sequence_similarity_pct'])}, but "
                    f"{fmt_int(oshb_exception['mismatch_verse_count'])} exception "
                    "verses require review; "
                    + (
                        "all are enumerated as reviewer rows, but none are signed off."
                        if int(oshb_exception["unexported_exception_row_count"]) == 0
                        else (
                            f"{fmt_int(oshb_exception['unexported_exception_row_count'])} "
                            "of them still need full row enumeration."
                        )
                    )
                    + " Taxonomy identifies "
                    f"{fmt_int(oshb_taxonomy['top_cause_row_count'])} rows in the top "
                    f"cause family, {oshb_taxonomy['top_cause_family']}, and "
                    f"{fmt_int(oshb_taxonomy['review_batch_count'])} queued batches. "
                    f"{fmt_pct(oshb_simulation['candidate_rule_reduction_pct'])} of rows "
                    "are rule-routable in simulation. The unlock matrix projects "
                    f"{fmt_int(morph_unlock['unlockable_priority_unit_count'])} "
                    "priority units could become review-ready after approval/import, "
                    "with "
                    f"{fmt_int(morph_unlock['manual_residual_row_count'])} manual "
                    "residual rows, but no mapping rule or source approval is approved."
                    " The critical-unit morphology plan keeps the same "
                    f"{fmt_int(critical_morph_unlock['exception_review_row_count'])} exception "
                    "rows and "
                    f"{fmt_int(critical_morph_unlock['review_batch_count'])} review batches, "
                    "but specifically projects "
                    "{} critical units to review-ready after approval/import.".format(
                        fmt_int(critical_morph_unlock["projected_review_ready_critical_unit_count"])
                    )
                ),
                "affected_requirement_ids": ["REQ-02", "REQ-03", "REQ-07", "REQ-12"],
                "next_action": (
                    "Approve source terms, build a version-pinned derived importer, "
                    "align imported morphology to UXLC tokens, and route exceptions "
                    "to Hebrew, lexical, alignment, provenance, license, and release reviewers."
                ),
            }
        )
    if context_integration["doctoral_collision_unit_count"]:
        rows.append(
            {
                "blocker_id": "BLK-24",
                "severity": "high",
                "blocker": "Integrated context collision units are routed but not adjudicated.",
                "evidence": (
                    f"The context integration matrix joins "
                    f"{fmt_int(context_integration['unit_count'])} Psalm units across "
                    f"{fmt_int(context_integration['lens_count'])} lenses. It flags "
                    f"{fmt_int(context_integration['high_pressure_unit_count'])} "
                    "high-pressure units, "
                    f"{fmt_int(context_integration['multi_lens_unit_count'])} "
                    "six-plus-lens units, and "
                    f"{fmt_int(context_integration['doctoral_collision_unit_count'])} "
                    "canon/culture/witness/reception collision units. Top unit: "
                    f"{context_integration['top_ref']} "
                    f"({float(context_integration['top_integration_pressure_score']):.2f}). "
                    f"The collision packet report expands these into "
                    f"{fmt_int(collision_packets['decision_row_count'])} pending decision "
                    f"rows across {fmt_int(collision_packets['lane_count'])} lanes; "
                    f"the collision benchmark adds "
                    f"{fmt_int(collision_benchmark['task_count'])} gloss/literal tasks "
                    f"and {fmt_int(collision_benchmark['planned_model_runs'])} planned "
                    "model runs; "
                    f"completed decisions remain "
                    f"{fmt_int(collision_packets['completed_decision_count'])}."
                ),
                "affected_requirement_ids": ["REQ-03", "REQ-04", "REQ-05", "REQ-06", "REQ-11"],
                "next_action": (
                    "Create reviewer packets for the collision units and require separated "
                    "Hebrew, cultural, textual-witness, Jewish, Christian, academic, and "
                    "release decisions before any wording authority is inferred."
                ),
            }
        )
    if collision_benchmark["task_count"]:
        rows.append(
            {
                "blocker_id": "BLK-25",
                "severity": "high",
                "blocker": "Collision benchmark tasks exist but have no scored model evidence.",
                "evidence": (
                    f"The collision supplement generated "
                    f"{fmt_int(collision_benchmark['task_count'])} tasks across "
                    f"{fmt_int(collision_benchmark['selected_collision_unit_count'])} "
                    "collision units, including "
                    f"{fmt_int(collision_benchmark['jewish_christian_task_count'])} "
                    "Jewish/Christian separation tasks, "
                    f"{fmt_int(collision_benchmark['divine_name_task_count'])} "
                    "divine-name tasks, and "
                    f"{fmt_int(collision_benchmark['poetic_rhetorical_task_count'])} "
                    "poetic/rhetorical tasks. Planned model runs total "
                    f"{fmt_int(collision_benchmark['planned_model_runs'])}. Companion "
                    "artifacts now add "
                    f"{fmt_int(collision_benchmark_cross_exam['packet_count'])} advisory "
                    "cross-exam packets, "
                    f"{fmt_int(collision_benchmark_cross_exam['execution_row_count'])} "
                    "execution rows, "
                    f"{fmt_int(collision_benchmark_dry_run['schema_valid_result_count'])} "
                    "schema-valid dry-run rows, and "
                    f"{fmt_int(collision_benchmark_review['projected_human_review_rows'])} "
                    "projected human review rows. The real smoke report adds "
                    f"{fmt_int(collision_real_smoke['attempt_count'])} attempts with "
                    f"{fmt_int(collision_real_smoke['schema_valid_attempt_count'])} "
                    "schema-valid rows and "
                    f"{fmt_int(collision_real_smoke['source_anchor_issue_count'])} "
                    "source-anchor issues, but scaled model coverage and signed review "
                    "decisions remain absent."
                ),
                "affected_requirement_ids": ["REQ-08", "REQ-09", "REQ-11", "REQ-12"],
                "next_action": (
                    "Run the collision benchmark against the approved local bakeoff models, "
                    "score source anchoring and reception separation, then route failures to "
                    "the pending collision packet lanes."
                ),
            }
        )
    if claim_traceability["required_claim_row_count"]:
        rows.append(
            {
                "blocker_id": "BLK-26",
                "severity": "high",
                "blocker": "Claim traceability does not equal translation-text authority.",
                "evidence": (
                    f"{fmt_int(claim_traceability['required_claim_row_count'])} "
                    "required claim rows are traceable across "
                    f"{fmt_int(claim_traceability['unit_count'])} high-pressure units, "
                    "but "
                    f"{fmt_int(claim_traceability['translation_text_allowed_now_count'])} "
                    "are currently allowed in translation text. "
                    f"{fmt_int(claim_traceability['notes_or_packets_only_claim_count'])} "
                    "claims must remain notes/source-packet-only; "
                    f"{fmt_int(claim_traceability['source_approval_missing_claim_count'])} "
                    "required rows still lack source approval and "
                    f"{fmt_int(claim_traceability['human_review_missing_claim_count'])} "
                    "still lack human review. Top traceability pressure: "
                    f"{claim_traceability['top_traceability_ref']} with "
                    f"{fmt_int(claim_traceability['top_traceability_blocking_gate_count'])} "
                    "blocking gates."
                ),
                "affected_requirement_ids": [
                    "REQ-04",
                    "REQ-05",
                    "REQ-06",
                    "REQ-07",
                    "REQ-12",
                ],
                "next_action": (
                    "Use the traceability audit to keep reception, culture, witness, "
                    "model, semantic, and release claims out of translation wording until "
                    "source approval, semantic/referent enrichment, human review, and "
                    "release signoff exist."
                ),
            }
        )
    if model_training_certification["candidate_count"]:
        rows.append(
            {
                "blocker_id": "BLK-27",
                "severity": "high",
                "blocker": "Local model training is plannable but not certifiable.",
                "evidence": (
                    f"{fmt_int(model_training_certification['candidate_count'])} candidates "
                    "are ranked for local model training and certification, including "
                    f"{fmt_int(model_training_certification['public_3090_known_fit_count'])} "
                    "public 3090-fit rows and "
                    f"{public_training_fit_count} training-or-probable-fit rows. "
                    "Valid contextual model-task coverage is "
                    f"{fmt_pct(model_training_certification['valid_model_task_coverage_pct'])}; "
                    "clean source-anchored evidence is "
                    f"{fmt_pct(model_training_certification['clean_source_anchored_pct'])}; "
                    f"{fmt_int(model_training_certification['claim_text_allowed_now'])} "
                    "claim rows are text-authorized now; "
                    f"{fmt_int(model_training_certification['source_approval_count'])} source "
                    "approvals and "
                    f"{fmt_int(model_training_certification['completed_review_row_count'])} "
                    "completed review rows exist."
                ),
                "affected_requirement_ids": ["REQ-08", "REQ-09", "REQ-11", "REQ-12"],
                "next_action": (
                    "Use the roadmap to run asset intake and benchmark gates, but keep "
                    "training, adapters, model certification, and release blocked until "
                    "source, benchmark, semantic/referent, review, and release gates pass."
                ),
            }
        )
    if translation_accuracy["blocked_gate_count"]:
        rows.append(
            {
                "blocker_id": "BLK-28",
                "severity": "high",
                "blocker": "Accuracy certification readiness is far below evidence maturity.",
                "evidence": (
                    "The translation accuracy certification matrix scores weighted "
                    "evidence maturity at "
                    f"{fmt_pct(translation_accuracy['weighted_evidence_maturity_pct'])}, "
                    "but weighted certification readiness at "
                    f"{fmt_pct(translation_accuracy['weighted_certification_readiness_pct'])}. "
                    f"{fmt_int(translation_accuracy['blocked_gate_count'])} of "
                    f"{fmt_int(translation_accuracy['gate_count'])} gates are blocked; "
                    f"{fmt_int(translation_accuracy['release_authorized_dimension_count'])} "
                    "dimensions are release-authorized; top dimension gap is "
                    f"{translation_accuracy['top_dimension_gap']} and top unit gap is "
                    f"{translation_accuracy['top_unit_ref']}."
                ),
                "affected_requirement_ids": [
                    "REQ-02",
                    "REQ-03",
                    "REQ-04",
                    "REQ-05",
                    "REQ-06",
                    "REQ-08",
                    "REQ-09",
                    "REQ-11",
                    "REQ-12",
                ],
                "next_action": (
                    "Use the accuracy matrix as the signoff ledger: clear source, "
                    "whole-Tanakh morphology, semantic/referent, Jewish/Christian, "
                    "model, human-review, blocked-unit, claim-authority, and release "
                    "gates before claiming translation accuracy certification."
                ),
            }
        )
    if critical_unit_decision["blocked_lane_row_count"]:
        rows.append(
            {
                "blocker_id": "BLK-29",
                "severity": "high",
                "blocker": "Critical units are triaged but not decidable.",
                "evidence": (
                    f"{fmt_int(critical_unit_decision['unit_count'])} critical decision "
                    "units are queued; "
                    f"{fmt_int(critical_unit_decision['blocked_lane_row_count'])} "
                    "decision lanes are blocked; "
                    f"{fmt_int(critical_unit_decision['text_blocked_unit_count'])} "
                    "units are text-blocked; "
                    f"{fmt_int(critical_unit_decision['clean_model_evidence_unit_count'])} "
                    "units have clean source-anchored model evidence; "
                    f"{fmt_int(critical_unit_decision['completed_review_row_count'])} "
                    "review rows are complete. Top unit "
                    f"{critical_unit_decision['top_decision_ref']} scores "
                    f"{critical_unit_decision['top_decision_pressure_score']:.2f}."
                ),
                "affected_requirement_ids": [
                    "REQ-02",
                    "REQ-03",
                    "REQ-04",
                    "REQ-05",
                    "REQ-06",
                    "REQ-08",
                    "REQ-09",
                    "REQ-11",
                    "REQ-12",
                ],
                "next_action": (
                    "Use the critical unit decision dossier as the per-unit decision "
                    "ledger: clear source approval, whole-Tanakh morphology, "
                    "semantic/referent, Jewish/Christian separation, model evidence, "
                    "human signoff, claim admissibility, and release lanes before "
                    "treating any listed unit as decidable."
                ),
            }
        )
    if critical_unit_review_execution["blocked_gate_count"]:
        rows.append(
            {
                "blocker_id": "BLK-30",
                "severity": "high",
                "blocker": "Critical-unit review execution is planned but unassigned.",
                "evidence": (
                    f"{fmt_int(critical_unit_review_execution['critical_unit_count'])} "
                    "critical units require execution review; "
                    f"{fmt_int(critical_unit_review_execution['total_role_review_row_count'])} "
                    "role/source rows are queued; "
                    f"{fmt_int(critical_unit_review_execution['completed_role_review_row_count'])} "
                    "are complete; "
                    f"{fmt_int(critical_unit_review_execution['blocked_wave_count'])} of "
                    f"{fmt_int(critical_unit_review_execution['wave_count'])} waves are blocked; "
                    f"{fmt_int(critical_unit_review_execution['blocked_gate_count'])} of "
                    f"{fmt_int(critical_unit_review_execution['gate_count'])} execution gates "
                    "are blocked. Top workload role is "
                    f"{critical_unit_review_execution['top_role']} with "
                    f"{fmt_int(critical_unit_review_execution['top_role_review_rows'])} rows; "
                    f"top wave {critical_unit_review_execution['top_wave']} carries "
                    f"{fmt_int(critical_unit_review_execution['top_wave_review_rows'])} rows."
                ),
                "affected_requirement_ids": [
                    "REQ-02",
                    "REQ-03",
                    "REQ-04",
                    "REQ-05",
                    "REQ-06",
                    "REQ-08",
                    "REQ-09",
                    "REQ-11",
                    "REQ-12",
                ],
                "next_action": (
                    "Use the execution plan as the review work order: assign named "
                    "reviewers, clear wave dependencies in order, record decisions and "
                    "scores, then run release review only after all execution gates pass."
                ),
            }
        )
    if critical_unit_model_cross_exam["missing_model_result_count"]:
        rows.append(
            {
                "blocker_id": "BLK-31",
                "severity": "hard",
                "blocker": "Critical-unit model cross-exam coverage is mostly missing.",
                "evidence": (
                    f"{fmt_int(critical_unit_model_cross_exam['critical_task_count'])} "
                    "critical tasks require model evidence; "
                    f"{fmt_int(critical_unit_model_cross_exam['submitted_model_result_count'])} "
                    "of "
                    f"{fmt_int(critical_unit_model_cross_exam['expected_model_result_count'])} "
                    "model-task rows are submitted; "
                    f"{fmt_int(critical_unit_model_cross_exam['missing_model_result_count'])} "
                    "are missing; "
                    f"{fmt_int(critical_unit_model_cross_exam['expected_candidate_output_count'])} "
                    "candidate outputs are expected; "
                    f"{fmt_int(critical_unit_model_cross_exam['cross_exam_execution_row_count'])} "
                    "Codex/Claude/Hebrew-specialist advisory judge rows are planned but not "
                    "authority-scored."
                ),
                "affected_requirement_ids": [
                    "REQ-08",
                    "REQ-09",
                    "REQ-10",
                    "REQ-11",
                    "REQ-12",
                ],
                "next_action": (
                    "Run the critical-unit model-task matrix across all planned local "
                    "profiles, generate three candidates per model-task row, execute "
                    "Codex, Claude, and Hebrew-specialist advisory cross-exam, then route "
                    "concerns to human reviewers before any model-authority claim."
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            SEVERITY_ORDER[str(row["severity"])],
            row["blocker_id"],
        ),
    )


def build_boundary_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    claim_policy = data["claim_matrix"].get("policy", {})
    source_policy = data["source_maturity"].get("policy", {})
    packet_policy = data["source_packets"].get("policy", {})
    review_policy = data["review_workbook"].get("policy", {})
    verification_policy = data["source_verification"].get("method", {})
    morphology_acquisition_policy = data["morphology_acquisition"].get("method", {})
    oshb_pilot_boundary = data["oshb_alignment_pilot"].get("source_boundary", {})
    oshb_exception_boundary = data["oshb_exception_review"].get("source_boundary", {})
    oshb_taxonomy_boundary = data["oshb_exception_taxonomy"].get("source_boundary", {})
    oshb_simulation_boundary = data["oshb_mapping_rule_simulation"].get("source_boundary", {})
    morph_unlock_policy = data["morphology_unlock_matrix"].get("authority_policy", "")
    critical_morph_unlock_policy = data["critical_unit_morphology_unlock"].get(
        "authority_policy",
        "",
    )
    authority_path_policy = data["authority_critical_path"].get("authority_policy", "")
    local_bakeoff_policy = (
        data["local_model_doctoral_bakeoff"].get("method", {}).get("authority_boundary", "")
    )
    model_training_certification_policy = data["model_training_certification"].get(
        "authority_policy", ""
    )
    translation_accuracy_policy = data["translation_accuracy_certification"].get(
        "authority_policy", ""
    )
    critical_unit_decision_policy = data["critical_unit_decision_dossier"].get(
        "authority_policy", ""
    )
    critical_unit_review_execution_policy = data["critical_unit_review_execution"].get(
        "authority_policy", ""
    )
    critical_unit_model_cross_exam_policy = data["critical_unit_model_cross_exam"].get(
        "authority_policy", ""
    )
    divine_policy = data["divine_name_policy"].get("method", {})
    superscription_policy = data["superscription_context"].get("method", {})
    cultural_policy = data["cultural_historical_atlas"].get("method", {})
    cross_reference_policy = data["canonical_cross_reference"].get("method", {})
    reception_divergence_policy = data["reception_divergence"].get("method", {})
    reception_source_packet_policy = data["reception_source_packets"].get("policy", {})
    interpretive_control_policy = data["interpretive_tradition_control"].get("authority_policy", "")
    source_ladder_policy = data["source_authority_ladder"].get("authority_policy", "")
    defense_exhibit_policy = data["doctoral_defense_exhibit"].get("authority_policy", "")
    token_defense_policy = data["hebrew_token_defense"].get("authority_policy", "")
    semantic_referent_policy = data["semantic_referent_roadmap"].get("authority_policy", "")
    claim_traceability_policy = data["claim_traceability"].get("authority_policy", "")
    priority_dossier_policy = data["priority_dossier_atlas"].get("method", {})
    poetic_policy = data["poetic_rhetorical_atlas"].get("method", {})
    corpus_reception_signal_policy = data["corpus_reception_signal"].get("method", {})
    context_integration_policy = data["context_integration"].get("method", {})
    collision_packet_policy = data["collision_packets"].get("method", {})
    collision_benchmark_summary = data["collision_benchmark"].get("summary", {})
    return [
        {
            "boundary_id": "BND-01",
            "boundary": "Hebrew source basis",
            "rule": claim_policy.get(
                "translation_text_basis", source_policy.get("primary_basis", "")
            ),
            "authority_effect": "Translation wording must be grounded in Hebrew token evidence.",
            "source_artifact": str(SOURCE_PATHS["claim_matrix"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-02",
            "boundary": "Whole-Tanakh context",
            "rule": claim_policy.get(
                "surface_context_boundary", packet_policy.get("whole_tanakh", "")
            ),
            "authority_effect": (
                "Current broader-canon evidence is context, not lemma-proof authority."
            ),
            "source_artifact": str(SOURCE_PATHS["morphology_gap"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-03",
            "boundary": "Witnesses",
            "rule": claim_policy.get("witness_boundary", packet_policy.get("witnesses", "")),
            "authority_effect": (
                "LXX and English witnesses inform comparison but cannot silently override Hebrew."
            ),
            "source_artifact": str(SOURCE_PATHS["witness"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-04",
            "boundary": "Jewish and Christian reception",
            "rule": claim_policy.get(
                "reception_boundary", source_policy.get("reception_boundary", "")
            ),
            "authority_effect": (
                "Reception belongs in labeled notes unless signed review justifies wording impact."
            ),
            "source_artifact": str(SOURCE_PATHS["reception_boundary"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-05",
            "boundary": "Generated source packets",
            "rule": packet_policy.get("authority", ""),
            "authority_effect": "Packet rows are workload and evidence routing, not signoff.",
            "source_artifact": str(SOURCE_PATHS["source_packets"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-06",
            "boundary": "Review workbook",
            "rule": review_policy.get("authority_boundary", ""),
            "authority_effect": (
                "Review rows become authority only after reviewer identity, decision, "
                "score, and notes."
            ),
            "source_artifact": str(SOURCE_PATHS["review_workbook"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-07",
            "boundary": "Model output",
            "rule": source_policy.get("model_boundary", ""),
            "authority_effect": "Local model output is proposal evidence, not a source.",
            "source_artifact": str(SOURCE_PATHS["source_maturity"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-08",
            "boundary": "Live source verification",
            "rule": verification_policy.get("boundary", ""),
            "authority_effect": (
                "Reachability and keyword hits route review, but do not approve source use."
            ),
            "source_artifact": str(SOURCE_PATHS["source_verification"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-09",
            "boundary": "Divine-name and title policy",
            "rule": divine_policy.get("boundary", ""),
            "authority_effect": (
                "Divine-name/title token evidence routes review, but does not select "
                "canonical LORD, Jehovah, Yahweh, God, or Lord renderings."
            ),
            "source_artifact": str(SOURCE_PATHS["divine_name_policy"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-10",
            "boundary": "Superscription and liturgical context",
            "rule": superscription_policy.get("boundary", ""),
            "authority_effect": (
                "Heading, performance, attribution, and historical-notice markers route "
                "review but do not settle authorship, historical provenance, or canonical "
                "rendering choices."
            ),
            "source_artifact": str(SOURCE_PATHS["superscription_context"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-11",
            "boundary": "Cultural and historical domain atlas",
            "rule": cultural_policy.get("boundary", ""),
            "authority_effect": (
                "Lexeme/Strong/gloss domain tags route cultural, historical, poetic, and "
                "reception review; they do not prove dating, authorship, intertextual "
                "dependency, or Jewish/Christian interpretation."
            ),
            "source_artifact": str(SOURCE_PATHS["cultural_historical_atlas"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-12",
            "boundary": "Canonical cross-reference atlas",
            "rule": cross_reference_policy.get("boundary", ""),
            "authority_effect": (
                "Normalized UXLC surface-form anchors route broader-canon research, but "
                "they do not prove lemma identity, sense, allusion, dependence, or "
                "translation wording authority."
            ),
            "source_artifact": str(SOURCE_PATHS["canonical_cross_reference"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-13",
            "boundary": "Reception divergence atlas",
            "rule": reception_divergence_policy.get("boundary", ""),
            "authority_effect": (
                "Separated Jewish, Christian, and academic lanes route reviewer work; "
                "they do not decide interpretive correctness or authorize translation "
                "wording without signed Hebrew and theology review."
            ),
            "source_artifact": str(SOURCE_PATHS["reception_divergence"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-14",
            "boundary": "Doctoral priority dossier atlas",
            "rule": priority_dossier_policy.get("boundary", ""),
            "authority_effect": (
                "Integrated dossiers combine evidence into review assignments; they do "
                "not approve canonical rendering, source use, reception interpretation, "
                "or model output."
            ),
            "source_artifact": str(SOURCE_PATHS["priority_dossier_atlas"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-15",
            "boundary": "Poetic and rhetorical pressure atlas",
            "rule": poetic_policy.get("boundary", ""),
            "authority_effect": (
                "Repetition, volitive mood, suffix-address, adjacent-overlap, acrostic, "
                "and rhetoric-pressure metrics route literary review; they do not prove "
                "formal parallelism, meter, stanza structure, genre, or English wording."
            ),
            "source_artifact": str(SOURCE_PATHS["poetic_rhetorical_atlas"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-16",
            "boundary": "Corpus reception signal atlas",
            "rule": corpus_reception_signal_policy.get("boundary", ""),
            "authority_effect": (
                "Royal, sonship, priesthood, Torah, death/Sheol, nations, affliction, "
                "violence, and divine-name signal families route separated reception "
                "review; they do not decide Jewish, Christian, or academic interpretation."
            ),
            "source_artifact": str(SOURCE_PATHS["corpus_reception_signal"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-17",
            "boundary": "Reception signal benchmark supplement",
            "rule": (
                "Supplement tasks are locked-input evaluation prompts derived from "
                "corpus reception signal candidates; they are not model results, "
                "review decisions, source approvals, or canonical translation evidence."
            ),
            "authority_effect": (
                "The supplement expands local-model and cross-exam coverage only after "
                "models are run and outputs are scored against source anchoring, "
                "schema validity, and reception-separation gates."
            ),
            "source_artifact": str(SOURCE_PATHS["reception_signal_benchmark"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-18",
            "boundary": "Reception signal companion artifacts",
            "rule": (
                "Dry-run audit rows, advisory model-judge packets, execution matrices, "
                "and review templates validate evaluation plumbing and workload only."
            ),
            "authority_effect": (
                "These artifacts improve benchmark readiness, but they do not prove "
                "translation accuracy, reception interpretation, human signoff, or "
                "canonical release authority."
            ),
            "source_artifact": "; ".join(
                source_artifact_names(
                    "reception_signal_benchmark_cross_exam",
                    "reception_signal_benchmark_dry_run_audit",
                    "reception_signal_benchmark_review",
                )
            ),
        },
        {
            "boundary_id": "BND-19",
            "boundary": "Reception signal real smoke evidence",
            "rule": (
                "Real local model smoke rows are measured outputs from full "
                "reception-context prompts, not full benchmark coverage, source approval, "
                "Jewish/Christian interpretive adjudication, reviewer signoff, or "
                "canonical rendering authority."
            ),
            "authority_effect": (
                "Smoke rows may guide runtime and prompt decisions, but schema-valid "
                "JSON cannot authorize reception claims, theological interpretation, "
                "translation wording, Gemma/Mistral model approval, or release decisions."
            ),
            "source_artifact": str(SOURCE_PATHS["reception_signal_real_smoke"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-20",
            "boundary": "Canonical intertext benchmark supplement",
            "rule": (
                "Supplement tasks are locked-input evaluation prompts derived from "
                "whole-Tanakh UXLC surface-form anchors across Torah, Prophets, and "
                "non-Psalm Writings; anchors are contextual retrieval cues only."
            ),
            "authority_effect": (
                "The supplement tests whether models preserve local Hebrew alignment "
                "while naming broader-canon context; it does not prove allusion, "
                "direct dependence, lemma identity, diachronic sequence, or canonical "
                "translation wording authority."
            ),
            "source_artifact": str(SOURCE_PATHS["canonical_intertext_benchmark"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-21",
            "boundary": "Canonical intertext companion artifacts",
            "rule": (
                "Dry-run audit rows, advisory judge packets, execution matrices, and "
                "review templates validate canonical-intertext evaluation plumbing and "
                "workload only."
            ),
            "authority_effect": (
                "These artifacts improve cross-exam readiness, but they do not prove "
                "translation accuracy, whole-canon interpretation, human signoff, or "
                "canonical release authority."
            ),
            "source_artifact": "; ".join(
                source_artifact_names(
                    "canonical_intertext_benchmark_cross_exam",
                    "canonical_intertext_benchmark_dry_run_audit",
                    "canonical_intertext_benchmark_review",
                )
            ),
        },
        {
            "boundary_id": "BND-22",
            "boundary": "Canonical intertext real smoke evidence",
            "rule": (
                "Real local model smoke rows are measured outputs for a bounded "
                "canonical-intertext probe, not full benchmark coverage, source "
                "approval, reviewer signoff, or canonical rendering authority."
            ),
            "authority_effect": (
                "Smoke rows may guide runtime and prompt decisions, but a valid JSON "
                "row cannot authorize translation wording, broader-canon claims, "
                "Gemma/Mistral model approval, or release decisions."
            ),
            "source_artifact": str(
                SOURCE_PATHS["canonical_intertext_real_smoke"].relative_to(ROOT)
            ),
        },
        {
            "boundary_id": "BND-23",
            "boundary": "Whole-Tanakh morphology acquisition readiness",
            "rule": morphology_acquisition_policy.get(
                "boundary",
                (
                    "Morphology source acquisition readiness ranks candidates and "
                    "gates only; it is not source approval, import approval, reviewer "
                    "signoff, or translation authority."
                ),
            ),
            "authority_effect": (
                "OSHB, STEPBible, MACULA, and BHSA candidate facts may guide import "
                "planning, but no candidate may become generation, display, export, "
                "or canonical wording authority until manifested, aligned, audited, "
                "and signed off."
            ),
            "source_artifact": str(SOURCE_PATHS["morphology_acquisition"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-24",
            "boundary": "OSHB whole-Tanakh alignment pilot",
            "rule": oshb_pilot_boundary.get(
                "forbidden_use",
                (
                    "The OSHB pilot is a remote-in-memory alignment feasibility audit; "
                    "it is not source approval, raw-source import, generation basis, "
                    "display/export permission, or canonical wording authority."
                ),
            ),
            "authority_effect": (
                "Pilot alignment metrics can guide importer design and reviewer "
                "exception queues, but they cannot authorize morphology-backed "
                "translation claims until a derived importer, source manifest, "
                "license/provenance approval, and reviewer signoff exist."
            ),
            "source_artifact": str(SOURCE_PATHS["oshb_alignment_pilot"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-25",
            "boundary": "OSHB alignment exception review",
            "rule": oshb_exception_boundary.get(
                "forbidden_use",
                (
                    "The OSHB exception workbook is a derived review queue; it is not "
                    "source approval, morphology import approval, reviewer signoff, "
                    "display/export permission, or canonical wording authority."
                ),
            ),
            "authority_effect": (
                "Exception rows can route Hebrew, alignment, provenance, and release "
                "review, but they cannot authorize model training data, morphology-backed "
                "translation claims, or canonical rendering decisions until all rows are "
                "enumerated and signed off."
            ),
            "source_artifact": str(SOURCE_PATHS["oshb_exception_review"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-26",
            "boundary": "OSHB exception taxonomy and batches",
            "rule": oshb_taxonomy_boundary.get(
                "forbidden_use",
                (
                    "The OSHB exception taxonomy is deterministic review routing; it is "
                    "not source approval, morphology import approval, reviewer signoff, "
                    "display/export permission, or canonical wording authority."
                ),
            ),
            "authority_effect": (
                "Cause families and review batches reduce reviewer workload, but they "
                "cannot authorize mapping rules, model training data, morphology-backed "
                "translation claims, or canonical rendering decisions until signed "
                "review and source approval exist."
            ),
            "source_artifact": str(SOURCE_PATHS["oshb_exception_taxonomy"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-27",
            "boundary": "OSHB candidate mapping-rule simulation",
            "rule": oshb_simulation_boundary.get(
                "forbidden_use",
                (
                    "The OSHB mapping-rule simulation is deterministic triage; it is not "
                    "source approval, importer rule approval, morphology import, model "
                    "training authorization, or canonical wording authority."
                ),
            ),
            "authority_effect": (
                "Candidate rule counts can guide reviewer workload and importer design, "
                "but they cannot authorize automated mapping, morphology-backed "
                "translation claims, model training data, or release decisions without "
                "source approval and signed review."
            ),
            "source_artifact": str(SOURCE_PATHS["oshb_mapping_rule_simulation"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-28",
            "boundary": "Doctoral context integration matrix",
            "rule": context_integration_policy.get(
                "score_boundary",
                (
                    "Integrated context pressure is deterministic reviewer routing only; "
                    "it is not a translation-quality score or authority certification."
                ),
            ),
            "authority_effect": (
                "Cross-lens collision rows can prioritize Hebrew, cultural, textual, "
                "reception, Jewish, Christian, academic, and release review, but they "
                "cannot authorize canonical wording or interpretive adjudication."
            ),
            "source_artifact": str(SOURCE_PATHS["context_integration"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-29",
            "boundary": "Doctoral collision review packets",
            "rule": collision_packet_policy.get(
                "packet_boundary",
                (
                    "Collision packets organize review decisions only; they do not "
                    "approve source use, interpretation, translation wording, model "
                    "training data, or release."
                ),
            ),
            "authority_effect": (
                "Pending decision rows can structure review across Hebrew, whole-Tanakh, "
                "culture, witness, Jewish, Christian, academic, poetic, and release "
                "lanes, but they cannot authorize canonical wording until signed."
            ),
            "source_artifact": str(SOURCE_PATHS["collision_packets"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-30",
            "boundary": "Doctoral collision benchmark supplement",
            "rule": collision_benchmark_summary.get(
                "authority_verdict",
                (
                    "Collision benchmark tasks are generated evaluation prompts; they are "
                    "not source approval, model-result evidence, reviewer signoff, model "
                    "training authorization, or canonical wording authority."
                ),
            ),
            "authority_effect": (
                "The supplement can drive local bakeoff and cross-exam runs for the hardest "
                "collision units, but it cannot raise authority readiness until real outputs "
                "are scored and pending reviewer lanes are signed."
            ),
            "source_artifact": str(SOURCE_PATHS["collision_benchmark"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-31",
            "boundary": "Doctoral collision benchmark companion artifacts",
            "rule": (
                "Dry-run audit rows, advisory model-judge packets, execution matrices, "
                "and review templates validate collision-benchmark plumbing and workload "
                "only."
            ),
            "authority_effect": (
                "These artifacts improve audit readiness, but they do not prove Hebrew "
                "translation accuracy, broader-canon interpretation, Jewish/Christian "
                "reception adjudication, human signoff, or canonical release authority."
            ),
            "source_artifact": "; ".join(
                source_artifact_names(
                    "collision_benchmark_cross_exam",
                    "collision_benchmark_dry_run_audit",
                    "collision_benchmark_review",
                )
            ),
        },
        {
            "boundary_id": "BND-32",
            "boundary": "Reception source packet workbook",
            "rule": reception_source_packet_policy.get(
                "authority_boundary",
                (
                    "Reception packet rows are source-acquisition and reviewer workload only "
                    "until citations, license/provenance review, reviewer identity, decisions, "
                    "and release signoff exist."
                ),
            ),
            "authority_effect": (
                "Separated Jewish, Christian, and academic rows can organize research and "
                "review, but they cannot authorize interpretive conclusions, translation "
                "wording, model training data, or canonical release."
            ),
            "source_artifact": str(SOURCE_PATHS["reception_source_packets"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-33",
            "boundary": "Doctoral collision real smoke evidence",
            "rule": (
                "Real local model smoke rows measure a bounded Psalm 22:28 collision probe; "
                "they are not scaled benchmark coverage, source approval, reviewer signoff, "
                "Jewish/Christian adjudication, or canonical wording authority."
            ),
            "authority_effect": (
                "Smoke rows can guide prompt/runtime and model-selection decisions, but "
                "schema-valid JSON cannot authorize translation wording, reception claims, "
                "Gemma/Mistral approval, or release decisions."
            ),
            "source_artifact": str(SOURCE_PATHS["collision_real_smoke"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-34",
            "boundary": "Contextual real model evidence matrix",
            "rule": (
                "The contextual matrix consolidates real local smoke rows across "
                "canonical-intertext, reception-sensitive, and collision lanes; it "
                "compares model behavior but does not provide scaled benchmark completion, "
                "source approval, reviewer decisions, or release authority."
            ),
            "authority_effect": (
                "The matrix can rank local-model prompt/runtime risk and expose source-anchor "
                "failures, but it cannot certify a model, approve interpretive claims, or "
                "authorize canonical Hebrew-to-English translation wording."
            ),
            "source_artifact": str(
                SOURCE_PATHS["contextual_real_model_evidence_matrix"].relative_to(ROOT)
            ),
        },
        {
            "boundary_id": "BND-35",
            "boundary": "Whole-Tanakh morphology unlock matrix",
            "rule": morph_unlock_policy
            or (
                "The unlock matrix estimates importer/source-review impact from OSHB "
                "pilot and mapping-simulation data only; it is not source approval, "
                "morphology import, reviewer signoff, or canonical translation authority."
            ),
            "authority_effect": (
                "Projected review-ready unit counts and exception reductions may "
                "prioritize source approval, importer, and reviewer work, but they "
                "cannot authorize model training data, morphology-backed claims, or "
                "canonical Hebrew-to-English wording."
            ),
            "source_artifact": str(SOURCE_PATHS["morphology_unlock_matrix"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-36",
            "boundary": "Local model doctoral bakeoff matrix",
            "rule": local_bakeoff_policy
            or (
                "The local model bakeoff matrix is triage over local assets, measured "
                "outputs, source-anchor behavior, Hebrew/context fit, and authority "
                "blockers; it is not model approval or translation authority."
            ),
            "authority_effect": (
                "Bakeoff scores can choose the next runnable baseline, trainable target, "
                "and Hebrew-specialist challenger, but cannot certify a model, approve "
                "generated wording, or replace source and reviewer signoff."
            ),
            "source_artifact": str(SOURCE_PATHS["local_model_doctoral_bakeoff"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-37",
            "boundary": "Authority critical path report",
            "rule": authority_path_policy
            or (
                "The authority critical path orders blocker-clearance work only; it is "
                "not source approval, morphology import, model approval, human signoff, "
                "or canonical translation authority."
            ),
            "authority_effect": (
                "Critical-path phases, reviewer loads, and top-unit queues can organize "
                "work, but they cannot clear a source, model, reviewer, or release gate "
                "without the underlying signed records."
            ),
            "source_artifact": str(SOURCE_PATHS["authority_critical_path"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-38",
            "boundary": "Interpretive tradition control matrix",
            "rule": interpretive_control_policy
            or (
                "The matrix separates Jewish, Christian, academic, witness, culture, "
                "and Hebrew-source controls for review only; it is not source approval "
                "or translation authority."
            ),
            "authority_effect": (
                "The matrix can join reception-sensitive controls and source-packet "
                "workload, but it cannot decide interpretation, approve sources, "
                "authorize model training, or change canonical translation text."
            ),
            "source_artifact": str(
                SOURCE_PATHS["interpretive_tradition_control"].relative_to(ROOT)
            ),
        },
        {
            "boundary_id": "BND-39",
            "boundary": "Source authority ladder matrix",
            "rule": source_ladder_policy
            or (
                "The source authority ladder measures provenance, source reachability, "
                "license risk, review workload, and source-family coverage; it is not "
                "source approval or translation authority."
            ),
            "authority_effect": (
                "The ladder can prioritize source acquisition and review for high-risk "
                "Psalm units, but it cannot approve sources, decide interpretation, "
                "authorize model training, or change canonical translation text."
            ),
            "source_artifact": str(SOURCE_PATHS["source_authority_ladder"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-40",
            "boundary": "Doctoral defense exhibit pack",
            "rule": defense_exhibit_policy
            or (
                "The defense exhibit pack is a visual evidence index for scholarly review; "
                "it is not source approval, interpretation adjudication, model approval, "
                "or translation authority."
            ),
            "authority_effect": (
                "The exhibits can focus committee review on high-pressure Psalm units, "
                "but they cannot approve sources, decide Jewish/Christian reception, "
                "certify model output, or alter canonical translation text."
            ),
            "source_artifact": str(SOURCE_PATHS["doctoral_defense_exhibit"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-41",
            "boundary": "Hebrew token defense matrix",
            "rule": token_defense_policy
            or (
                "The Hebrew token defense matrix is a token-level evidence index; "
                "it is not source approval, wording approval, interpretation "
                "adjudication, model approval, or release authority."
            ),
            "authority_effect": (
                "The matrix can support token-level review traceability for Hebrew "
                "surface, lemma, morphology, anchors, culture, witnesses, and controls, "
                "but it cannot authorize translation wording, source use, interpretation, "
                "model output, or release status."
            ),
            "source_artifact": str(SOURCE_PATHS["hebrew_token_defense"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-42",
            "boundary": "Semantic/referent enrichment roadmap",
            "rule": semantic_referent_policy
            or (
                "The semantic/referent enrichment roadmap is a derived prioritization queue; "
                "it is not imported source data, source approval, final referent assignment, "
                "canonical content, model approval, or release authority."
            ),
            "authority_effect": (
                "The roadmap can prioritize semantic-role, referent, syntax, stem, "
                "and discourse enrichment work, but it cannot establish semantic roles, "
                "assign antecedents, decide interpretation, or authorize translation wording."
            ),
            "source_artifact": str(SOURCE_PATHS["semantic_referent_roadmap"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-43",
            "boundary": "Translation claim traceability audit",
            "rule": claim_traceability_policy
            or (
                "The translation claim traceability audit routes claim families into "
                "permitted review locations; it is not source approval, interpretation "
                "adjudication, model certification, wording approval, or release authority."
            ),
            "authority_effect": (
                "The audit can route claim families into translation drafts, notes, "
                "source packets, benchmark candidates, or release gates, but it cannot "
                "approve source use, decide interpretation, authorize wording, certify "
                "model output, or release canonical content."
            ),
            "source_artifact": str(SOURCE_PATHS["claim_traceability"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-44",
            "boundary": "Model training certification roadmap",
            "rule": model_training_certification_policy
            or (
                "The model training certification roadmap ranks local-base, QLoRA, "
                "benchmark, cross-exam, and release-readiness work only; it is not "
                "model approval, source approval, training-data approval, reviewer "
                "signoff, canonical wording approval, or release authority."
            ),
            "authority_effect": (
                "The roadmap can prioritize model intake, training experiments, and "
                "benchmark expansion, but it cannot certify a model, authorize source "
                "use, approve generated wording, replace human review, or release "
                "canonical translation text."
            ),
            "source_artifact": str(SOURCE_PATHS["model_training_certification"].relative_to(ROOT)),
        },
        {
            "boundary_id": "BND-45",
            "boundary": "Translation accuracy certification matrix",
            "rule": translation_accuracy_policy
            or (
                "The translation accuracy certification matrix is a signoff-oriented "
                "evidence ledger only; it is not source approval, interpretation "
                "adjudication, model certification, wording approval, or release authority."
            ),
            "authority_effect": (
                "The matrix can expose evidence maturity, blocked gates, reviewer load, "
                "and priority unit gaps, but it cannot certify accuracy, approve sources, "
                "settle Jewish/Christian interpretation, authorize generated wording, "
                "or release canonical translation text."
            ),
            "source_artifact": str(
                SOURCE_PATHS["translation_accuracy_certification"].relative_to(ROOT)
            ),
        },
        {
            "boundary_id": "BND-46",
            "boundary": "Critical unit decision dossier",
            "rule": critical_unit_decision_policy
            or (
                "The critical unit decision dossier is a committee triage artifact only; "
                "it is not source approval, interpretation adjudication, model "
                "certification, wording approval, or release authority."
            ),
            "authority_effect": (
                "The dossier can identify blocked lanes, claim admissibility, review "
                "workload, model-evidence gaps, and next actions for critical Psalm "
                "units, but it cannot approve sources, settle Jewish or Christian "
                "interpretation, authorize generated wording, or release canonical "
                "translation text."
            ),
            "source_artifact": str(
                SOURCE_PATHS["critical_unit_decision_dossier"].relative_to(ROOT)
            ),
        },
        {
            "boundary_id": "BND-47",
            "boundary": "Critical unit review execution plan",
            "rule": critical_unit_review_execution_policy
            or (
                "The critical unit review execution plan is workload routing only; it "
                "is not reviewer assignment, reviewer signoff, source approval, model "
                "certification, wording approval, or release authority."
            ),
            "authority_effect": (
                "The plan can sequence reviewer roles, waves, lane dependencies, and "
                "release gates, but it cannot assign real reviewers, prove completed "
                "review, authorize source use, approve model output, or release "
                "canonical translation text."
            ),
            "source_artifact": str(
                SOURCE_PATHS["critical_unit_review_execution"].relative_to(ROOT)
            ),
        },
        {
            "boundary_id": "BND-48",
            "boundary": "Critical unit model cross-exam plan",
            "rule": critical_unit_model_cross_exam_policy
            or (
                "The critical unit model cross-exam plan is benchmark and advisory-judge "
                "execution routing only; it is not model certification, human review, "
                "source approval, wording approval, or release authority."
            ),
            "authority_effect": (
                "The plan can quantify missing model-task rows, candidate-output depth, "
                "Codex/Claude/Hebrew-specialist judge workload, and model evidence gates, "
                "but it cannot certify a model, approve generated wording, replace human "
                "review, or release canonical translation text."
            ),
            "source_artifact": str(
                SOURCE_PATHS["critical_unit_model_cross_exam"].relative_to(ROOT)
            ),
        },
        {
            "boundary_id": "BND-49",
            "boundary": "Critical unit morphology unlock plan",
            "rule": critical_morph_unlock_policy
            or (
                "The critical unit morphology unlock plan is source-import and "
                "reviewer-workload routing only; it is not source approval, "
                "morphology import, reviewer signoff, or canonical wording authority."
            ),
            "authority_effect": (
                "Critical-unit projected review-ready counts can prioritize OSHB or "
                "comparable source approval, importer design, and exception review, "
                "but cannot authorize morphology-backed claims, model training data, "
                "or canonical Hebrew-to-English wording."
            ),
            "source_artifact": str(
                SOURCE_PATHS["critical_unit_morphology_unlock"].relative_to(ROOT)
            ),
        },
    ]


def build_priority_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    unit_claims = {
        str(row["unit_id"]): row for row in data["claim_matrix"].get("unit_claim_rows", [])
    }
    rows = []
    for unit in data["review_workbook"].get("unit_rows", [])[:25]:
        claim = unit_claims.get(str(unit["unit_id"]), {})
        rows.append(
            {
                "rank": len(rows) + 1,
                "unit_id": unit["unit_id"],
                "ref": unit["ref"],
                "packet_priority_score": unit["packet_priority_score"],
                "packet_priority_band": unit["packet_priority_band"],
                "claim_risk_score": claim.get("claim_risk_score", ""),
                "packet_family_count": unit["packet_family_count"],
                "packet_review_row_count": unit["packet_review_row_count"],
                "jewish_christian_separation_required": unit[
                    "jewish_christian_separation_required"
                ],
                "textual_witness_pressure": unit["textual_witness_pressure"],
                "ancient_culture_pressure": unit["ancient_culture_pressure"],
                "required_roles": unit["distinct_reviewer_roles"],
                "status": unit["status"],
            }
        )
    return rows


def build_visual_data(
    data: dict[str, dict[str, Any]],
    requirement_rows: list[dict[str, Any]],
    blocker_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    claim = data["claim_matrix"]["summary"]
    claim_traceability = data["claim_traceability"]["summary"]
    translation_accuracy = data["translation_accuracy_certification"]["summary"]
    critical_unit_decision = data["critical_unit_decision_dossier"]["summary"]
    critical_unit_review_execution = data["critical_unit_review_execution"]["summary"]
    critical_unit_model_cross_exam = data["critical_unit_model_cross_exam"]["summary"]
    critical_morph_unlock = data["critical_unit_morphology_unlock"]["summary"]
    model_training_certification = data["model_training_certification"]["summary"]
    review_roles = data["review_workbook"].get("review_role_rows", [])
    severity_counts = Counter(str(row["severity"]) for row in blocker_rows)
    status_counts = Counter(str(row["status"]) for row in requirement_rows)
    pressure_rows = [
        {
            "pressure": "high-risk claim units",
            "unit_count": claim["high_risk_unit_count"],
        },
        {
            "pressure": "theology-pressure units",
            "unit_count": claim["theology_pressure_unit_count"],
        },
        {
            "pressure": "textual-witness units",
            "unit_count": claim["textual_witness_pressure_unit_count"],
        },
        {
            "pressure": "ancient-culture units",
            "unit_count": claim["ancient_culture_pressure_unit_count"],
        },
        {
            "pressure": "reception-sensitive units",
            "unit_count": claim["reception_sensitive_unit_count"],
        },
        {
            "pressure": "Jewish/Christian separation units",
            "unit_count": claim["jewish_christian_separation_unit_count"],
        },
        {
            "pressure": "traceable required claim rows",
            "unit_count": claim_traceability["required_claim_row_count"],
        },
        {
            "pressure": "currently text-authorized claim rows",
            "unit_count": claim_traceability["translation_text_allowed_now_count"],
        },
        {
            "pressure": "claim rows outside translation text",
            "unit_count": claim_traceability["claim_outside_translation_text_count"],
        },
        {
            "pressure": "accuracy certification dimensions",
            "unit_count": translation_accuracy["dimension_count"],
        },
        {
            "pressure": "accuracy certification blocked gates",
            "unit_count": translation_accuracy["blocked_gate_count"],
        },
        {
            "pressure": "release-authorized dimensions",
            "unit_count": translation_accuracy["release_authorized_dimension_count"],
        },
        {
            "pressure": "critical decision dossier units",
            "unit_count": critical_unit_decision["unit_count"],
        },
        {
            "pressure": "critical decision blocked lanes",
            "unit_count": critical_unit_decision["blocked_lane_row_count"],
        },
        {
            "pressure": "critical decision text-blocked units",
            "unit_count": critical_unit_decision["text_blocked_unit_count"],
        },
        {
            "pressure": "critical review execution rows",
            "unit_count": critical_unit_review_execution["total_role_review_row_count"],
        },
        {
            "pressure": "critical review blocked waves",
            "unit_count": critical_unit_review_execution["blocked_wave_count"],
        },
        {
            "pressure": "critical review blocked gates",
            "unit_count": critical_unit_review_execution["blocked_gate_count"],
        },
        {
            "pressure": "critical model cross-exam tasks",
            "unit_count": critical_unit_model_cross_exam["critical_task_count"],
        },
        {
            "pressure": "critical model missing rows",
            "unit_count": critical_unit_model_cross_exam["missing_model_result_count"],
        },
        {
            "pressure": "critical model judge rows",
            "unit_count": critical_unit_model_cross_exam["cross_exam_execution_row_count"],
        },
        {
            "pressure": "critical morphology unlock units",
            "unit_count": critical_morph_unlock["critical_unit_count"],
        },
        {
            "pressure": "critical morphology projected ready",
            "unit_count": critical_morph_unlock["projected_review_ready_critical_unit_count"],
        },
        {
            "pressure": "critical morphology exception rows",
            "unit_count": critical_morph_unlock["exception_review_row_count"],
        },
        {
            "pressure": "training certification candidates",
            "unit_count": model_training_certification["candidate_count"],
        },
        {
            "pressure": "public 3090-fit model rows",
            "unit_count": model_training_certification["public_3090_known_fit_count"],
        },
        {
            "pressure": "model training text-authorized claim rows",
            "unit_count": model_training_certification["claim_text_allowed_now"],
        },
        {
            "pressure": "superscription context units",
            "unit_count": data["superscription_context"]["summary"]["context_unit_count"],
        },
        {
            "pressure": "historical heading units",
            "unit_count": data["superscription_context"]["summary"]["historical_notice_unit_count"],
        },
        {
            "pressure": "technical heading units",
            "unit_count": data["superscription_context"]["summary"]["technical_term_unit_count"],
        },
        {
            "pressure": "cultural domain units",
            "unit_count": data["cultural_historical_atlas"]["summary"]["domain_unit_count"],
        },
        {
            "pressure": "high-priority cultural units",
            "unit_count": data["cultural_historical_atlas"]["summary"]["high_priority_unit_count"],
        },
        {
            "pressure": "poetic/rhetorical high-pressure units",
            "unit_count": data["poetic_rhetorical_atlas"]["summary"]["high_pressure_unit_count"],
        },
        {
            "pressure": "volitive mood units",
            "unit_count": data["poetic_rhetorical_atlas"]["summary"]["volitive_unit_count"],
        },
        {
            "pressure": "adjacent parallelism-proxy units",
            "unit_count": data["poetic_rhetorical_atlas"]["summary"][
                "adjacent_parallelism_proxy_unit_count"
            ],
        },
        {
            "pressure": "canonical cross-ref units",
            "unit_count": data["canonical_cross_reference"]["summary"][
                "cross_reference_unit_count"
            ],
        },
        {
            "pressure": "three-division cross-ref units",
            "unit_count": data["canonical_cross_reference"]["summary"]["three_division_unit_count"],
        },
        {
            "pressure": "morphology acquisition candidates",
            "unit_count": data["morphology_acquisition"]["summary"]["morphology_candidate_count"],
        },
        {
            "pressure": "morphology acquisition blocked gates",
            "unit_count": data["morphology_acquisition"]["summary"]["blocked_gate_count"],
        },
        {
            "pressure": "morphology acquisition not-started gates",
            "unit_count": data["morphology_acquisition"]["summary"]["not_started_gate_count"],
        },
        {
            "pressure": "OSHB pilot mapped books",
            "unit_count": data["oshb_alignment_pilot"]["summary"]["mapped_book_count"],
        },
        {
            "pressure": "OSHB pilot mismatch verses",
            "unit_count": data["oshb_alignment_pilot"]["summary"]["mismatch_sample_row_count"],
        },
        {
            "pressure": "canonical-intertext supplement units",
            "unit_count": data["canonical_intertext_benchmark"]["summary"][
                "selected_intertext_unit_count"
            ],
        },
        {
            "pressure": "canonical-intertext supplement tasks",
            "unit_count": data["canonical_intertext_benchmark"]["summary"]["task_count"],
        },
        {
            "pressure": "canonical-intertext cross-exam packets",
            "unit_count": data["canonical_intertext_benchmark_cross_exam"]["summary"][
                "packet_count"
            ],
        },
        {
            "pressure": "canonical-intertext dry-run valid rows",
            "unit_count": data["canonical_intertext_benchmark_dry_run_audit"]["summary"][
                "schema_valid_result_count"
            ],
        },
        {
            "pressure": "canonical-intertext real smoke attempts",
            "unit_count": data["canonical_intertext_real_smoke"]["summary"]["attempt_count"],
        },
        {
            "pressure": "canonical-intertext valid smoke rows",
            "unit_count": data["canonical_intertext_real_smoke"]["summary"][
                "valid_model_task_count"
            ],
        },
        {
            "pressure": "canonical-intertext smoke anchor issues",
            "unit_count": data["canonical_intertext_real_smoke"]["summary"][
                "source_anchor_issue_count"
            ],
        },
        {
            "pressure": "canonical-intertext projected review rows",
            "unit_count": data["canonical_intertext_benchmark_review"]["summary"][
                "projected_human_review_rows"
            ],
        },
        {
            "pressure": "reception divergence units",
            "unit_count": data["reception_divergence"]["summary"]["unit_count"],
        },
        {
            "pressure": "Jewish/Christian split-lane units",
            "unit_count": data["reception_divergence"]["summary"][
                "jewish_christian_separation_unit_count"
            ],
        },
        {
            "pressure": "corpus reception signal units",
            "unit_count": data["corpus_reception_signal"]["summary"]["signal_unit_count"],
        },
        {
            "pressure": "high-pressure reception signal units",
            "unit_count": data["corpus_reception_signal"]["summary"]["high_pressure_unit_count"],
        },
        {
            "pressure": "new reception expansion candidates",
            "unit_count": data["corpus_reception_signal"]["summary"][
                "new_high_pressure_expansion_candidate_count"
            ],
        },
        {
            "pressure": "reception-signal supplement units",
            "unit_count": data["reception_signal_benchmark"]["summary"][
                "selected_reception_signal_unit_count"
            ],
        },
        {
            "pressure": "reception-signal supplement tasks",
            "unit_count": data["reception_signal_benchmark"]["summary"]["task_count"],
        },
        {
            "pressure": "reception-signal cross-exam packets",
            "unit_count": data["reception_signal_benchmark_cross_exam"]["summary"]["packet_count"],
        },
        {
            "pressure": "reception-signal dry-run valid rows",
            "unit_count": data["reception_signal_benchmark_dry_run_audit"]["summary"][
                "schema_valid_result_count"
            ],
        },
        {
            "pressure": "reception-signal real smoke attempts",
            "unit_count": data["reception_signal_real_smoke"]["summary"]["attempt_count"],
        },
        {
            "pressure": "reception-signal valid smoke rows",
            "unit_count": data["reception_signal_real_smoke"]["summary"]["valid_model_task_count"],
        },
        {
            "pressure": "reception-signal smoke anchor issues",
            "unit_count": data["reception_signal_real_smoke"]["summary"][
                "source_anchor_issue_count"
            ],
        },
        {
            "pressure": "reception-signal projected review rows",
            "unit_count": data["reception_signal_benchmark_review"]["summary"][
                "projected_human_review_rows"
            ],
        },
        {
            "pressure": "doctoral dossier queue units",
            "unit_count": data["priority_dossier_atlas"]["summary"]["unit_count"],
        },
        {
            "pressure": "critical dossier queue units",
            "unit_count": data["priority_dossier_atlas"]["summary"]["critical_unit_count"],
        },
    ]
    return {
        "requirement_score_rows": [
            {
                "requirement_id": row["requirement_id"],
                "requirement": row["requirement"],
                "score_pct": row["score_pct"],
                "status": row["status"],
            }
            for row in requirement_rows
        ],
        "requirement_status_counts": [
            {"status": status, "count": count}
            for status, count in sorted(
                status_counts.items(),
                key=lambda item: STATUS_ORDER.get(item[0], 99),
            )
        ],
        "blocker_severity_counts": [
            {"severity": severity, "count": count}
            for severity, count in sorted(
                severity_counts.items(),
                key=lambda item: SEVERITY_ORDER.get(item[0], 99),
            )
        ],
        "contextual_pressure_rows": pressure_rows,
        "review_role_workload_rows": review_roles,
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    requirement_rows = build_requirement_rows(data)
    blocker_rows = build_blocker_rows(data)
    boundary_rows = build_boundary_rows(data)
    priority_unit_rows = build_priority_unit_rows(data)
    visual_data = build_visual_data(data, requirement_rows, blocker_rows)
    authority = data["authority"]["summary"]
    review = data["review_workbook"]["summary"]
    claim = data["claim_matrix"]["summary"]
    claim_traceability = data["claim_traceability"]["summary"]
    translation_accuracy = data["translation_accuracy_certification"]["summary"]
    critical_unit_decision = data["critical_unit_decision_dossier"]["summary"]
    critical_unit_review_execution = data["critical_unit_review_execution"]["summary"]
    critical_unit_model_cross_exam = data["critical_unit_model_cross_exam"]["summary"]
    source_maturity = data["source_maturity"]["summary"]
    local_selection = data["local_selection"]["summary"]
    local_bakeoff = data["local_model_doctoral_bakeoff"]["summary"]
    model_training_certification = data["model_training_certification"]["summary"]
    authority_path = data["authority_critical_path"]["summary"]
    model_gap = data["model_gap"]["summary"]
    source_acquisition = data["source_acquisition"]["summary"]
    morph_acquisition = data["morphology_acquisition"]["summary"]
    oshb_pilot = data["oshb_alignment_pilot"]["summary"]
    oshb_exception = data["oshb_exception_review"]["summary"]
    oshb_taxonomy = data["oshb_exception_taxonomy"]["summary"]
    oshb_simulation = data["oshb_mapping_rule_simulation"]["summary"]
    morph_unlock = data["morphology_unlock_matrix"]["summary"]
    critical_morph_unlock = data["critical_unit_morphology_unlock"]["summary"]
    bibliography = data["bibliography"]["summary"]
    source_verification = data["source_verification"]["summary"]
    source_authority_ladder = data["source_authority_ladder"]["summary"]
    witness_divergence = data["witness_divergence"]["summary"]
    divine_name = data["divine_name_policy"]["summary"]
    superscription = data["superscription_context"]["summary"]
    cultural = data["cultural_historical_atlas"]["summary"]
    poetic = data["poetic_rhetorical_atlas"]["summary"]
    corpus_reception_signal = data["corpus_reception_signal"]["summary"]
    reception_signal_benchmark = data["reception_signal_benchmark"]["summary"]
    reception_signal_cross_exam = data["reception_signal_benchmark_cross_exam"]["summary"]
    reception_signal_dry_run = data["reception_signal_benchmark_dry_run_audit"]["summary"]
    reception_signal_review = data["reception_signal_benchmark_review"]["summary"]
    reception_signal_real_smoke = data["reception_signal_real_smoke"]["summary"]
    canonical_intertext_benchmark = data["canonical_intertext_benchmark"]["summary"]
    canonical_intertext_cross_exam = data["canonical_intertext_benchmark_cross_exam"]["summary"]
    canonical_intertext_dry_run = data["canonical_intertext_benchmark_dry_run_audit"]["summary"]
    canonical_intertext_review = data["canonical_intertext_benchmark_review"]["summary"]
    canonical_intertext_real_smoke = data["canonical_intertext_real_smoke"]["summary"]
    cross_reference = data["canonical_cross_reference"]["summary"]
    reception_divergence = data["reception_divergence"]["summary"]
    reception_source_packets = data["reception_source_packets"]["summary"]
    interpretive_control = data["interpretive_tradition_control"]["summary"]
    context_integration = data["context_integration"]["summary"]
    collision_packets = data["collision_packets"]["summary"]
    collision_benchmark = data["collision_benchmark"]["summary"]
    collision_benchmark_cross_exam = data["collision_benchmark_cross_exam"]["summary"]
    collision_benchmark_dry_run = data["collision_benchmark_dry_run_audit"]["summary"]
    collision_benchmark_review = data["collision_benchmark_review"]["summary"]
    collision_real_smoke = data["collision_real_smoke"]["summary"]
    contextual_real_model_evidence = data["contextual_real_model_evidence_matrix"]["summary"]
    priority_dossier_atlas = data["priority_dossier_atlas"]["summary"]
    doctoral_defense_exhibit = data["doctoral_defense_exhibit"]["summary"]
    hebrew_token_defense = data["hebrew_token_defense"]["summary"]
    semantic_referent = data["semantic_referent_roadmap"]["summary"]
    unit_heatmap = data["unit_heatmap"]["summary"]

    blocked_requirements = [
        row
        for row in requirement_rows
        if row["status"] in {"blocked", "not started"} or row["score_pct"] < 45
    ]
    prototype_requirements = [
        row
        for row in requirement_rows
        if row["status"] in {"prototype", "weak", "usable with caveats"}
    ]
    strong_requirements = [row for row in requirement_rows if row["status"] == "strong"]
    weighted_score = weighted_mean(requirement_rows)

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "doctoral translation synthesis generated; not authority signoff",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_boundary": {
            "current_state": "not_authoritative",
            "reason": (
                "The synthesis aggregates evidence and blockers, but no human review rows or "
                "release authority gates are complete."
            ),
            "canonical_boundary": "No canonical rendering may change from this report alone.",
        },
        "summary": {
            "doctoral_synthesis_score_pct": weighted_score,
            "underlying_authority_readiness_score_pct": authority["authority_readiness_score_pct"],
            "requirement_count": len(requirement_rows),
            "strong_requirement_count": len(strong_requirements),
            "prototype_requirement_count": len(prototype_requirements),
            "blocked_requirement_count": len(blocked_requirements),
            "blocker_count": len(blocker_rows),
            "critical_blocker_count": sum(
                1 for row in blocker_rows if row["severity"] == "critical"
            ),
            "source_boundary_count": len(boundary_rows),
            "priority_unit_count": len(priority_unit_rows),
            "bibliography_source_count": bibliography["bibliography_source_count"],
            "bibliography_candidate_source_count": bibliography["candidate_source_count"],
            "bibliography_blocked_authority_lane_count": bibliography[
                "blocked_authority_lane_count"
            ],
            "bibliography_gap_count": bibliography["gap_count"],
            "source_verification_source_count": source_verification["source_count"],
            "source_verification_url_source_count": source_verification["url_source_count"],
            "source_verification_reachable_url_count": source_verification["reachable_url_count"],
            "source_verification_reachable_url_pct": source_verification["reachable_url_pct"],
            "source_verification_gap_count": source_verification["gap_count"],
            "source_verification_source_approval_count": source_verification[
                "source_approval_count"
            ],
            "source_authority_ladder_unit_count": source_authority_ladder["unit_count"],
            "source_authority_ladder_critical_gap_unit_count": source_authority_ladder[
                "critical_gap_unit_count"
            ],
            "source_authority_ladder_mean_readiness_pct": source_authority_ladder[
                "mean_source_authority_readiness_pct"
            ],
            "source_authority_ladder_source_family_count": source_authority_ladder[
                "source_family_count"
            ],
            "source_authority_ladder_family_without_candidate_count": (
                source_authority_ladder["family_without_candidate_count"]
            ),
            "source_authority_ladder_candidate_source_count": source_authority_ladder[
                "candidate_source_count"
            ],
            "source_authority_ladder_candidate_reachable_count": source_authority_ladder[
                "candidate_reachable_count"
            ],
            "source_authority_ladder_source_approval_count": source_authority_ladder[
                "source_approval_count"
            ],
            "source_authority_ladder_total_review_row_count": source_authority_ladder[
                "total_review_row_count"
            ],
            "source_authority_ladder_completed_review_row_count": source_authority_ladder[
                "completed_review_row_count"
            ],
            "source_authority_ladder_top_ref": source_authority_ladder["top_gap_ref"],
            "source_authority_ladder_top_score": source_authority_ladder["top_gap_score"],
            "witness_divergence_unit_count": witness_divergence["unit_count"],
            "witness_divergence_complete_english_unit_count": witness_divergence[
                "complete_english_witness_unit_count"
            ],
            "witness_divergence_mean_pct": witness_divergence[
                "mean_english_witness_divergence_pct"
            ],
            "witness_divergence_p90_pct": witness_divergence["p90_english_witness_divergence_pct"],
            "witness_divergence_high_unit_count": witness_divergence["high_divergence_unit_count"],
            "witness_divergence_divine_name_disagreement_count": witness_divergence[
                "divine_name_disagreement_unit_count"
            ],
            "divine_name_policy_unit_count": divine_name["divine_title_unit_count"],
            "divine_name_policy_token_count": divine_name["divine_title_token_count"],
            "divine_name_policy_yhwh_token_count": divine_name["yhwh_token_count"],
            "divine_name_policy_elohim_token_count": divine_name["elohim_token_count"],
            "divine_name_policy_witness_disagreement_count": divine_name[
                "witness_disagreement_unit_count"
            ],
            "divine_name_policy_yhwh_adonai_stack_count": divine_name[
                "yhwh_adonai_lord_stack_unit_count"
            ],
            "divine_name_policy_top_ref": divine_name["top_priority_ref"],
            "divine_name_policy_top_score": divine_name["top_priority_score"],
            "superscription_context_unit_count": superscription["context_unit_count"],
            "superscription_context_unit_pct": superscription["context_unit_pct"],
            "superscription_context_token_count": superscription["context_token_count"],
            "superscription_context_historical_notice_count": superscription[
                "historical_notice_unit_count"
            ],
            "superscription_context_technical_term_count": superscription[
                "technical_term_unit_count"
            ],
            "superscription_context_musical_direction_count": superscription[
                "musical_direction_unit_count"
            ],
            "superscription_context_performance_marker_count": superscription[
                "performance_marker_unit_count"
            ],
            "superscription_context_top_ref": superscription["top_priority_ref"],
            "superscription_context_top_score": superscription["top_priority_score"],
            "cultural_historical_domain_unit_count": cultural["domain_unit_count"],
            "cultural_historical_domain_unit_pct": cultural["domain_unit_pct"],
            "cultural_historical_domain_token_count": cultural["domain_token_count"],
            "cultural_historical_domain_count": cultural["domain_count"],
            "cultural_historical_high_priority_unit_count": cultural["high_priority_unit_count"],
            "cultural_historical_ancient_culture_unit_count": cultural[
                "ancient_culture_pressure_unit_count"
            ],
            "cultural_historical_reception_sensitive_unit_count": cultural[
                "reception_sensitive_unit_count"
            ],
            "cultural_historical_textual_witness_unit_count": cultural[
                "textual_witness_pressure_unit_count"
            ],
            "cultural_historical_top_ref": cultural["top_priority_ref"],
            "cultural_historical_top_score": cultural["top_priority_score"],
            "poetic_rhetorical_high_pressure_unit_count": poetic["high_pressure_unit_count"],
            "poetic_rhetorical_critical_pressure_unit_count": poetic[
                "critical_pressure_unit_count"
            ],
            "poetic_rhetorical_high_pressure_unit_pct": poetic["high_pressure_unit_pct"],
            "poetic_rhetorical_volitive_unit_count": poetic["volitive_unit_count"],
            "poetic_rhetorical_volitive_token_count": poetic["volitive_token_count"],
            "poetic_rhetorical_repetition_unit_count": poetic["repetition_unit_count"],
            "poetic_rhetorical_adjacent_parallelism_proxy_count": poetic[
                "adjacent_parallelism_proxy_unit_count"
            ],
            "poetic_rhetorical_second_person_address_unit_count": poetic[
                "second_person_address_unit_count"
            ],
            "poetic_rhetorical_acrostic_proxy_unit_count": poetic["acrostic_proxy_unit_count"],
            "poetic_rhetorical_top_ref": poetic["top_priority_ref"],
            "poetic_rhetorical_top_score": poetic["top_priority_score"],
            "corpus_reception_signal_unit_count": corpus_reception_signal["signal_unit_count"],
            "corpus_reception_signal_unit_pct": corpus_reception_signal["signal_unit_pct"],
            "corpus_reception_signal_token_count": corpus_reception_signal["signal_token_count"],
            "corpus_reception_signal_family_count": corpus_reception_signal["signal_family_count"],
            "corpus_reception_signal_high_pressure_unit_count": corpus_reception_signal[
                "high_pressure_unit_count"
            ],
            "corpus_reception_signal_critical_pressure_unit_count": corpus_reception_signal[
                "critical_pressure_unit_count"
            ],
            "corpus_reception_signal_known_divergence_unit_count": corpus_reception_signal[
                "known_reception_divergence_unit_count"
            ],
            "corpus_reception_signal_known_split_unit_count": corpus_reception_signal[
                "known_jewish_christian_separation_unit_count"
            ],
            "corpus_reception_signal_new_candidate_count": corpus_reception_signal[
                "new_high_pressure_expansion_candidate_count"
            ],
            "corpus_reception_signal_top_ref": corpus_reception_signal["top_priority_ref"],
            "corpus_reception_signal_top_score": corpus_reception_signal["top_priority_score"],
            "reception_signal_benchmark_unit_count": reception_signal_benchmark[
                "selected_reception_signal_unit_count"
            ],
            "reception_signal_benchmark_task_count": reception_signal_benchmark["task_count"],
            "reception_signal_benchmark_planned_runs": reception_signal_benchmark[
                "planned_model_runs"
            ],
            "reception_signal_benchmark_remaining_candidate_count": reception_signal_benchmark[
                "remaining_reception_signal_candidate_count"
            ],
            "reception_signal_benchmark_top_ref": reception_signal_benchmark["top_selected_ref"],
            "reception_signal_benchmark_top_score": reception_signal_benchmark[
                "top_selected_priority_score"
            ],
            "reception_signal_benchmark_cross_exam_packets": reception_signal_cross_exam[
                "packet_count"
            ],
            "reception_signal_benchmark_cross_exam_rows": reception_signal_cross_exam[
                "execution_row_count"
            ],
            "reception_signal_benchmark_dry_run_valid": reception_signal_dry_run[
                "schema_valid_result_count"
            ],
            "reception_signal_benchmark_dry_run_missing": reception_signal_dry_run[
                "missing_expected_result_count"
            ],
            "reception_signal_benchmark_review_human_rows": reception_signal_review[
                "projected_human_review_rows"
            ],
            "reception_signal_benchmark_review_model_rows": reception_signal_review[
                "projected_model_cross_exam_rows"
            ],
            "reception_signal_real_smoke_attempt_count": reception_signal_real_smoke[
                "attempt_count"
            ],
            "reception_signal_real_smoke_model_count": reception_signal_real_smoke["model_count"],
            "reception_signal_real_smoke_schema_valid_attempt_count": (
                reception_signal_real_smoke["schema_valid_attempt_count"]
            ),
            "reception_signal_real_smoke_schema_valid_attempt_pct": (
                reception_signal_real_smoke["schema_valid_attempt_pct"]
            ),
            "reception_signal_real_smoke_valid_model_task_count": (
                reception_signal_real_smoke["valid_model_task_count"]
            ),
            "reception_signal_real_smoke_valid_model_task_coverage_pct": (
                reception_signal_real_smoke["valid_model_task_coverage_pct"]
            ),
            "reception_signal_real_smoke_missing_model_task_count": (
                reception_signal_real_smoke["missing_model_task_count_after_smoke"]
            ),
            "reception_signal_real_smoke_source_anchor_issue_count": (
                reception_signal_real_smoke["source_anchor_issue_count"]
            ),
            "reception_signal_real_smoke_reception_leak_term_count": (
                reception_signal_real_smoke["reception_leak_term_count"]
            ),
            "reception_signal_real_smoke_clean_best_model": reception_signal_real_smoke[
                "clean_best_model_profile"
            ],
            "reception_signal_real_smoke_fastest_valid_model": (
                reception_signal_real_smoke["fastest_valid_model_profile"]
            ),
            "canonical_intertext_benchmark_unit_count": canonical_intertext_benchmark[
                "selected_intertext_unit_count"
            ],
            "canonical_intertext_benchmark_task_count": canonical_intertext_benchmark["task_count"],
            "canonical_intertext_benchmark_planned_runs": canonical_intertext_benchmark[
                "planned_model_runs"
            ],
            "canonical_intertext_benchmark_remaining_candidate_count": (
                canonical_intertext_benchmark["remaining_intertext_candidate_count"]
            ),
            "canonical_intertext_benchmark_top_ref": canonical_intertext_benchmark[
                "top_selected_ref"
            ],
            "canonical_intertext_benchmark_top_score": canonical_intertext_benchmark[
                "top_selected_priority_score"
            ],
            "canonical_intertext_benchmark_cross_exam_packets": (
                canonical_intertext_cross_exam["packet_count"]
            ),
            "canonical_intertext_benchmark_cross_exam_rows": canonical_intertext_cross_exam[
                "execution_row_count"
            ],
            "canonical_intertext_benchmark_dry_run_valid": canonical_intertext_dry_run[
                "schema_valid_result_count"
            ],
            "canonical_intertext_benchmark_dry_run_missing": canonical_intertext_dry_run[
                "missing_expected_result_count"
            ],
            "canonical_intertext_benchmark_review_human_rows": canonical_intertext_review[
                "projected_human_review_rows"
            ],
            "canonical_intertext_benchmark_review_model_rows": canonical_intertext_review[
                "projected_model_cross_exam_rows"
            ],
            "canonical_intertext_real_smoke_attempt_count": canonical_intertext_real_smoke[
                "attempt_count"
            ],
            "canonical_intertext_real_smoke_model_count": canonical_intertext_real_smoke[
                "model_count"
            ],
            "canonical_intertext_real_smoke_schema_valid_attempt_count": (
                canonical_intertext_real_smoke["schema_valid_attempt_count"]
            ),
            "canonical_intertext_real_smoke_schema_valid_attempt_pct": (
                canonical_intertext_real_smoke["schema_valid_attempt_pct"]
            ),
            "canonical_intertext_real_smoke_valid_model_task_count": (
                canonical_intertext_real_smoke["valid_model_task_count"]
            ),
            "canonical_intertext_real_smoke_valid_model_task_coverage_pct": (
                canonical_intertext_real_smoke["valid_model_task_coverage_pct"]
            ),
            "canonical_intertext_real_smoke_missing_model_task_count": (
                canonical_intertext_real_smoke["missing_model_task_count_after_smoke"]
            ),
            "canonical_intertext_real_smoke_source_anchor_issue_count": (
                canonical_intertext_real_smoke["source_anchor_issue_count"]
            ),
            "canonical_intertext_real_smoke_clean_best_model": canonical_intertext_real_smoke[
                "clean_best_model_profile"
            ],
            "canonical_intertext_real_smoke_fastest_valid_model": (
                canonical_intertext_real_smoke["fastest_valid_model_profile"]
            ),
            "canonical_cross_reference_unit_count": cross_reference["cross_reference_unit_count"],
            "canonical_cross_reference_unit_pct": cross_reference["cross_reference_unit_pct"],
            "canonical_cross_reference_anchor_token_count": cross_reference["anchor_token_count"],
            "canonical_cross_reference_anchor_token_pct": cross_reference["anchor_token_pct"],
            "canonical_cross_reference_three_division_unit_count": cross_reference[
                "three_division_unit_count"
            ],
            "canonical_cross_reference_high_value_anchor_unit_count": cross_reference[
                "high_value_anchor_unit_count"
            ],
            "canonical_cross_reference_top_ref": cross_reference["top_priority_ref"],
            "canonical_cross_reference_top_score": cross_reference["top_priority_score"],
            "reception_divergence_unit_count": reception_divergence["unit_count"],
            "reception_divergence_sensitive_unit_count": reception_divergence[
                "reception_sensitive_unit_count"
            ],
            "reception_divergence_jewish_christian_unit_count": reception_divergence[
                "jewish_christian_separation_unit_count"
            ],
            "reception_divergence_academic_comparison_unit_count": reception_divergence[
                "academic_comparison_unit_count"
            ],
            "reception_divergence_signal_count": reception_divergence["signal_count"],
            "reception_divergence_top_ref": reception_divergence["top_priority_ref"],
            "reception_divergence_top_score": reception_divergence["top_priority_score"],
            "reception_source_packet_unit_count": reception_source_packets["split_lane_unit_count"],
            "reception_source_packet_count": reception_source_packets["packet_count"],
            "reception_source_packet_candidate_source_count": reception_source_packets[
                "distinct_candidate_source_count"
            ],
            "reception_source_packet_reachable_source_count": reception_source_packets[
                "reachable_candidate_source_count"
            ],
            "reception_source_packet_reachable_pct": reception_source_packets[
                "packet_with_reachable_candidate_pct"
            ],
            "reception_source_packet_source_approval_count": reception_source_packets[
                "source_approval_count"
            ],
            "reception_source_packet_completed_review_count": reception_source_packets[
                "completed_packet_review_count"
            ],
            "reception_source_packet_blocked_gate_count": reception_source_packets[
                "blocked_gate_count"
            ],
            "interpretive_control_unit_count": interpretive_control["unit_count"],
            "interpretive_control_split_unit_count": interpretive_control[
                "jewish_christian_separation_unit_count"
            ],
            "interpretive_control_reception_sensitive_unit_count": interpretive_control[
                "reception_sensitive_unit_count"
            ],
            "interpretive_control_ancient_culture_unit_count": interpretive_control[
                "ancient_culture_pressure_unit_count"
            ],
            "interpretive_control_textual_witness_unit_count": interpretive_control[
                "textual_witness_pressure_unit_count"
            ],
            "interpretive_control_forbidden_text_unit_count": interpretive_control[
                "translation_text_forbidden_reception_claim_units"
            ],
            "interpretive_control_packet_count": interpretive_control["packet_count"],
            "interpretive_control_source_approval_count": interpretive_control[
                "source_approval_count"
            ],
            "interpretive_control_completed_packet_review_count": interpretive_control[
                "completed_packet_review_count"
            ],
            "interpretive_control_top_ref": interpretive_control["top_control_ref"],
            "interpretive_control_top_score": interpretive_control["top_control_score"],
            "context_integration_unit_count": context_integration["unit_count"],
            "context_integration_lens_count": context_integration["lens_count"],
            "context_integration_high_pressure_unit_count": context_integration[
                "high_pressure_unit_count"
            ],
            "context_integration_multi_lens_unit_count": context_integration[
                "multi_lens_unit_count"
            ],
            "context_integration_doctoral_collision_unit_count": context_integration[
                "doctoral_collision_unit_count"
            ],
            "context_integration_top_ref": context_integration["top_ref"],
            "context_integration_top_score": context_integration["top_integration_pressure_score"],
            "collision_packet_count": collision_packets["collision_packet_count"],
            "collision_decision_row_count": collision_packets["decision_row_count"],
            "collision_pending_decision_count": collision_packets["pending_decision_count"],
            "collision_lane_count": collision_packets["lane_count"],
            "collision_reviewer_role_count": collision_packets["reviewer_role_count"],
            "collision_jewish_christian_packet_count": collision_packets[
                "jewish_christian_packet_count"
            ],
            "collision_completion_pct": collision_packets["completion_pct"],
            "collision_top_ref": collision_packets["top_ref"],
            "collision_top_score": collision_packets["top_integration_pressure_score"],
            "collision_benchmark_task_count": collision_benchmark["task_count"],
            "collision_benchmark_unit_count": collision_benchmark["selected_collision_unit_count"],
            "collision_benchmark_planned_runs": collision_benchmark["planned_model_runs"],
            "collision_benchmark_jewish_christian_task_count": collision_benchmark[
                "jewish_christian_task_count"
            ],
            "collision_benchmark_divine_name_task_count": collision_benchmark[
                "divine_name_task_count"
            ],
            "collision_benchmark_poetic_task_count": collision_benchmark[
                "poetic_rhetorical_task_count"
            ],
            "collision_benchmark_top_ref": collision_benchmark["top_selected_ref"],
            "collision_benchmark_top_score": collision_benchmark[
                "top_selected_integration_pressure_score"
            ],
            "collision_benchmark_cross_exam_packet_count": collision_benchmark_cross_exam[
                "packet_count"
            ],
            "collision_benchmark_cross_exam_execution_row_count": (
                collision_benchmark_cross_exam["execution_row_count"]
            ),
            "collision_benchmark_dry_schema_valid_result_count": (
                collision_benchmark_dry_run["schema_valid_result_count"]
            ),
            "collision_benchmark_dry_schema_valid_pct": collision_benchmark_dry_run[
                "schema_valid_pct"
            ],
            "collision_benchmark_review_projected_human_rows": collision_benchmark_review[
                "projected_human_review_rows"
            ],
            "collision_benchmark_review_projected_cross_exam_rows": collision_benchmark_review[
                "projected_model_cross_exam_rows"
            ],
            "collision_real_smoke_attempt_count": collision_real_smoke["attempt_count"],
            "collision_real_smoke_model_count": collision_real_smoke["model_count"],
            "collision_real_smoke_schema_valid_attempt_count": collision_real_smoke[
                "schema_valid_attempt_count"
            ],
            "collision_real_smoke_clean_attempt_count": collision_real_smoke[
                "clean_schema_valid_attempt_count"
            ],
            "collision_real_smoke_source_anchor_issue_count": collision_real_smoke[
                "source_anchor_issue_count"
            ],
            "collision_real_smoke_missing_model_task_count": collision_real_smoke[
                "missing_model_task_count_after_smoke"
            ],
            "collision_real_smoke_clean_best_model": collision_real_smoke[
                "clean_best_model_profile"
            ],
            "contextual_real_model_attempt_count": contextual_real_model_evidence["attempt_count"],
            "contextual_real_model_lane_count": contextual_real_model_evidence["lane_count"],
            "contextual_real_model_schema_valid_count": contextual_real_model_evidence[
                "schema_valid_attempt_count"
            ],
            "contextual_real_model_clean_count": contextual_real_model_evidence[
                "clean_source_anchored_count"
            ],
            "contextual_real_model_anchor_issue_count": contextual_real_model_evidence[
                "source_anchor_issue_count"
            ],
            "contextual_real_model_valid_model_task_coverage_pct": (
                contextual_real_model_evidence["valid_model_task_coverage_pct"]
            ),
            "contextual_real_model_missing_count": contextual_real_model_evidence[
                "missing_model_task_count_after_smoke"
            ],
            "contextual_real_model_best_clean_model": contextual_real_model_evidence[
                "best_clean_model_profile"
            ],
            "priority_dossier_atlas_unit_count": priority_dossier_atlas["unit_count"],
            "priority_dossier_atlas_critical_unit_count": priority_dossier_atlas[
                "critical_unit_count"
            ],
            "priority_dossier_atlas_highest_unit_count": priority_dossier_atlas[
                "highest_unit_count"
            ],
            "priority_dossier_atlas_jewish_christian_unit_count": priority_dossier_atlas[
                "jewish_christian_separation_unit_count"
            ],
            "priority_dossier_atlas_textual_witness_unit_count": priority_dossier_atlas[
                "textual_witness_pressure_unit_count"
            ],
            "priority_dossier_atlas_mean_authority_score_pct": priority_dossier_atlas[
                "mean_authority_score_pct"
            ],
            "priority_dossier_atlas_top_ref": priority_dossier_atlas["top_priority_ref"],
            "priority_dossier_atlas_top_score": priority_dossier_atlas["top_priority_score"],
            "defense_exhibit_unit_count": doctoral_defense_exhibit["exhibit_unit_count"],
            "defense_exhibit_critical_unit_count": doctoral_defense_exhibit[
                "critical_exhibit_unit_count"
            ],
            "defense_exhibit_mean_score": doctoral_defense_exhibit["mean_defense_exhibit_score"],
            "defense_exhibit_mean_authority_pct": doctoral_defense_exhibit[
                "mean_unit_authority_score_pct"
            ],
            "defense_exhibit_source_unapproved_unit_count": doctoral_defense_exhibit[
                "source_unapproved_unit_count"
            ],
            "defense_exhibit_unsigned_review_unit_count": doctoral_defense_exhibit[
                "unsigned_review_unit_count"
            ],
            "defense_exhibit_jewish_christian_unit_count": doctoral_defense_exhibit[
                "jewish_christian_separation_unit_count"
            ],
            "defense_exhibit_clean_model_unit_count": doctoral_defense_exhibit[
                "clean_model_attempt_unit_count"
            ],
            "defense_exhibit_top_ref": doctoral_defense_exhibit["top_exhibit_ref"],
            "defense_exhibit_top_score": doctoral_defense_exhibit["top_exhibit_score"],
            "token_defense_unit_count": hebrew_token_defense["unit_count"],
            "token_defense_token_count": hebrew_token_defense["token_count"],
            "token_defense_critical_token_count": hebrew_token_defense["critical_token_count"],
            "token_defense_critical_threshold": hebrew_token_defense[
                "critical_token_score_threshold"
            ],
            "token_defense_anchor_token_count": hebrew_token_defense["anchor_token_count"],
            "token_defense_high_anchor_token_count": hebrew_token_defense[
                "high_anchor_token_count"
            ],
            "token_defense_cultural_domain_token_count": hebrew_token_defense[
                "cultural_domain_token_count"
            ],
            "token_defense_divine_name_token_count": hebrew_token_defense[
                "divine_name_token_count"
            ],
            "token_defense_missing_semantic_role_token_count": hebrew_token_defense[
                "missing_semantic_role_token_count"
            ],
            "token_defense_missing_referent_token_count": hebrew_token_defense[
                "missing_referent_token_count"
            ],
            "token_defense_source_approved_token_count": hebrew_token_defense[
                "source_approved_token_count"
            ],
            "token_defense_review_completed_token_count": hebrew_token_defense[
                "review_completed_token_count"
            ],
            "token_defense_top_token_ref": hebrew_token_defense["top_token_ref"],
            "token_defense_top_token_surface": hebrew_token_defense["top_token_surface"],
            "token_defense_top_token_score": hebrew_token_defense["top_token_score"],
            "semantic_referent_token_count": semantic_referent["token_count"],
            "semantic_referent_unit_count": semantic_referent["unit_count"],
            "semantic_referent_critical_token_count": semantic_referent[
                "critical_enrichment_token_count"
            ],
            "semantic_referent_critical_unit_count": semantic_referent[
                "critical_enrichment_unit_count"
            ],
            "semantic_referent_critical_threshold": semantic_referent[
                "critical_enrichment_score_threshold"
            ],
            "semantic_referent_semantic_role_coverage_pct": semantic_referent[
                "semantic_role_coverage_pct"
            ],
            "semantic_referent_referent_coverage_pct": semantic_referent["referent_coverage_pct"],
            "semantic_referent_missing_semantic_role_count": semantic_referent[
                "missing_semantic_role_token_count"
            ],
            "semantic_referent_missing_referent_count": semantic_referent[
                "missing_referent_token_count"
            ],
            "semantic_referent_source_approved_token_count": semantic_referent[
                "source_approved_token_count"
            ],
            "semantic_referent_review_completed_token_count": semantic_referent[
                "review_completed_token_count"
            ],
            "semantic_referent_top_token_ref": semantic_referent["top_token_ref"],
            "semantic_referent_top_token_surface": semantic_referent["top_token_surface"],
            "semantic_referent_top_token_score": semantic_referent["top_token_score"],
            "unit_heatmap_unit_count": unit_heatmap["unit_count"],
            "unit_heatmap_mean_score_pct": unit_heatmap["mean_unit_authority_score_pct"],
            "unit_heatmap_blocked_unit_count": unit_heatmap["blocked_unit_count"],
            "unit_heatmap_blocked_unit_pct": unit_heatmap["blocked_unit_pct"],
            "unit_heatmap_top_gap_ref": unit_heatmap["top_gap_ref"],
            "unit_heatmap_top_gap_score_pct": unit_heatmap["top_gap_score_pct"],
            "review_workbook_total_rows": review["total_review_row_count"],
            "review_workbook_completed_rows": review["completed_review_row_count"],
            "review_completion_pct": review["review_completion_pct"],
            "high_risk_claim_unit_count": claim["high_risk_unit_count"],
            "jewish_christian_separation_unit_count": claim[
                "jewish_christian_separation_unit_count"
            ],
            "ancient_culture_unit_count": claim["ancient_culture_pressure_unit_count"],
            "textual_witness_unit_count": claim["textual_witness_pressure_unit_count"],
            "claim_traceability_unit_count": claim_traceability["unit_count"],
            "claim_traceability_claim_row_count": claim_traceability["claim_row_count"],
            "claim_traceability_required_claim_row_count": claim_traceability[
                "required_claim_row_count"
            ],
            "claim_traceability_notes_only_claim_count": claim_traceability[
                "notes_or_packets_only_claim_count"
            ],
            "claim_traceability_blocked_or_review_claim_count": claim_traceability[
                "blocked_or_review_claim_count"
            ],
            "claim_traceability_translation_text_allowed_now_count": claim_traceability[
                "translation_text_allowed_now_count"
            ],
            "claim_traceability_allowed_after_review_count": claim_traceability[
                "translation_text_allowed_after_review_count"
            ],
            "claim_traceability_source_approval_missing_count": claim_traceability[
                "source_approval_missing_claim_count"
            ],
            "claim_traceability_human_review_missing_count": claim_traceability[
                "human_review_missing_claim_count"
            ],
            "claim_traceability_outside_translation_text_count": claim_traceability[
                "claim_outside_translation_text_count"
            ],
            "claim_traceability_top_ref": claim_traceability["top_traceability_ref"],
            "claim_traceability_top_gate_count": claim_traceability[
                "top_traceability_blocking_gate_count"
            ],
            "translation_accuracy_dimension_count": translation_accuracy["dimension_count"],
            "translation_accuracy_gate_count": translation_accuracy["gate_count"],
            "translation_accuracy_blocked_gate_count": translation_accuracy["blocked_gate_count"],
            "translation_accuracy_evidence_maturity_pct": translation_accuracy[
                "weighted_evidence_maturity_pct"
            ],
            "translation_accuracy_certification_readiness_pct": translation_accuracy[
                "weighted_certification_readiness_pct"
            ],
            "translation_accuracy_release_authorized_dimension_count": translation_accuracy[
                "release_authorized_dimension_count"
            ],
            "translation_accuracy_top_dimension_gap": translation_accuracy["top_dimension_gap"],
            "translation_accuracy_top_unit_ref": translation_accuracy["top_unit_ref"],
            "critical_unit_decision_unit_count": critical_unit_decision["unit_count"],
            "critical_unit_decision_critical_or_highest_unit_count": critical_unit_decision[
                "critical_or_highest_unit_count"
            ],
            "critical_unit_decision_blocked_lane_count": critical_unit_decision[
                "blocked_lane_row_count"
            ],
            "critical_unit_decision_text_blocked_count": critical_unit_decision[
                "text_blocked_unit_count"
            ],
            "critical_unit_decision_clean_model_count": critical_unit_decision[
                "clean_model_evidence_unit_count"
            ],
            "critical_unit_decision_jewish_christian_count": critical_unit_decision[
                "jewish_christian_separation_unit_count"
            ],
            "critical_unit_decision_review_rows": critical_unit_decision[
                "total_packet_review_row_count"
            ],
            "critical_unit_decision_completed_reviews": critical_unit_decision[
                "completed_review_row_count"
            ],
            "critical_unit_decision_mean_authority_pct": critical_unit_decision[
                "mean_unit_authority_score_pct"
            ],
            "critical_unit_decision_top_ref": critical_unit_decision["top_decision_ref"],
            "critical_unit_decision_top_score": critical_unit_decision[
                "top_decision_pressure_score"
            ],
            "critical_unit_review_execution_unit_count": critical_unit_review_execution[
                "critical_unit_count"
            ],
            "critical_unit_review_execution_total_rows": critical_unit_review_execution[
                "total_role_review_row_count"
            ],
            "critical_unit_review_execution_completed_rows": critical_unit_review_execution[
                "completed_role_review_row_count"
            ],
            "critical_unit_review_execution_completion_pct": critical_unit_review_execution[
                "review_completion_pct"
            ],
            "critical_unit_review_execution_blocked_wave_count": (
                critical_unit_review_execution["blocked_wave_count"]
            ),
            "critical_unit_review_execution_blocked_gate_count": (
                critical_unit_review_execution["blocked_gate_count"]
            ),
            "critical_unit_review_execution_top_role": critical_unit_review_execution["top_role"],
            "critical_unit_review_execution_top_role_rows": critical_unit_review_execution[
                "top_role_review_rows"
            ],
            "critical_unit_review_execution_top_wave": critical_unit_review_execution["top_wave"],
            "critical_unit_review_execution_top_wave_rows": critical_unit_review_execution[
                "top_wave_review_rows"
            ],
            "critical_unit_model_cross_exam_task_count": critical_unit_model_cross_exam[
                "critical_task_count"
            ],
            "critical_unit_model_cross_exam_expected_rows": critical_unit_model_cross_exam[
                "expected_model_result_count"
            ],
            "critical_unit_model_cross_exam_submitted_rows": critical_unit_model_cross_exam[
                "submitted_model_result_count"
            ],
            "critical_unit_model_cross_exam_missing_rows": critical_unit_model_cross_exam[
                "missing_model_result_count"
            ],
            "critical_unit_model_cross_exam_coverage_pct": critical_unit_model_cross_exam[
                "model_result_coverage_pct"
            ],
            "critical_unit_model_cross_exam_candidate_outputs": critical_unit_model_cross_exam[
                "expected_candidate_output_count"
            ],
            "critical_unit_model_cross_exam_judge_rows": critical_unit_model_cross_exam[
                "cross_exam_execution_row_count"
            ],
            "critical_unit_model_cross_exam_judges": critical_unit_model_cross_exam["judge_count"],
            "critical_unit_model_cross_exam_probe_questions": critical_unit_model_cross_exam[
                "probe_question_count"
            ],
            "critical_unit_model_cross_exam_top_model": critical_unit_model_cross_exam[
                "top_missing_model"
            ],
            "source_maturity_mean_authority_score_pct": source_maturity["mean_authority_score_pct"],
            "source_maturity_blocked_authority_lane_count": source_maturity[
                "blocked_authority_lane_count"
            ],
            "source_acquisition_candidate_count": source_acquisition["candidate_count"],
            "source_acquisition_blocked_gate_count": source_acquisition["blocked_gate_count"],
            "morphology_acquisition_candidate_count": morph_acquisition[
                "morphology_candidate_count"
            ],
            "morphology_acquisition_low_license_risk_candidate_count": morph_acquisition[
                "low_license_risk_candidate_count"
            ],
            "morphology_acquisition_research_only_candidate_count": morph_acquisition[
                "research_only_candidate_count"
            ],
            "morphology_acquisition_local_non_psalm_book_count": morph_acquisition[
                "local_non_psalm_morphology_book_count"
            ],
            "morphology_acquisition_target_non_psalm_book_count": morph_acquisition[
                "target_non_psalm_book_count"
            ],
            "morphology_acquisition_blocked_gate_count": morph_acquisition["blocked_gate_count"],
            "morphology_acquisition_not_started_gate_count": morph_acquisition[
                "not_started_gate_count"
            ],
            "morphology_acquisition_recommended_first_import_candidate": (
                morph_acquisition["recommended_first_import_candidate"]
            ),
            "morphology_acquisition_recommended_semantic_candidate": morph_acquisition[
                "recommended_semantic_enrichment_candidate"
            ],
            "oshb_alignment_pilot_mapped_book_count": oshb_pilot["mapped_book_count"],
            "oshb_alignment_pilot_mapped_non_psalm_book_count": oshb_pilot[
                "mapped_non_psalm_book_count"
            ],
            "oshb_alignment_pilot_remote_word_count": oshb_pilot["remote_oshb_word_count"],
            "oshb_alignment_pilot_morph_coverage_pct": oshb_pilot["remote_oshb_morph_coverage_pct"],
            "oshb_alignment_pilot_exact_sequence_match_pct": oshb_pilot["exact_sequence_match_pct"],
            "oshb_alignment_pilot_mean_sequence_similarity_pct": oshb_pilot[
                "mean_sequence_similarity_pct"
            ],
            "oshb_alignment_pilot_mismatch_row_count": oshb_pilot["mismatch_sample_row_count"],
            "oshb_alignment_pilot_source_approval_status": oshb_pilot["source_approval_status"],
            "oshb_exception_review_mismatch_verse_count": oshb_exception["mismatch_verse_count"],
            "oshb_exception_review_token_count_exception_verse_count": oshb_exception[
                "token_count_exception_verse_count"
            ],
            "oshb_exception_review_sequence_only_exception_verse_count": oshb_exception[
                "sequence_only_exception_verse_count"
            ],
            "oshb_exception_review_sample_row_count": oshb_exception["sample_row_count"],
            "oshb_exception_review_review_row_count": oshb_exception.get(
                "review_row_count", oshb_exception["sample_row_count"]
            ),
            "oshb_exception_review_unexported_exception_row_count": oshb_exception[
                "unexported_exception_row_count"
            ],
            "oshb_exception_review_critical_book_count": oshb_exception["critical_book_count"],
            "oshb_exception_taxonomy_cause_count": oshb_taxonomy["taxonomy_cause_count"],
            "oshb_exception_taxonomy_review_batch_count": oshb_taxonomy["review_batch_count"],
            "oshb_exception_taxonomy_top_cause_family": oshb_taxonomy["top_cause_family"],
            "oshb_exception_taxonomy_top_cause_row_count": oshb_taxonomy["top_cause_row_count"],
            "oshb_exception_taxonomy_segmentation_marker_pct": oshb_taxonomy[
                "segmentation_marker_pct"
            ],
            "oshb_mapping_rule_simulation_rule_candidate_after_review_count": (
                oshb_simulation["rule_candidate_after_review_count"]
            ),
            "oshb_mapping_rule_simulation_targeted_rule_review_count": oshb_simulation[
                "targeted_rule_review_count"
            ],
            "oshb_mapping_rule_simulation_candidate_rule_reduction_pct": oshb_simulation[
                "candidate_rule_reduction_pct"
            ],
            "oshb_mapping_rule_simulation_manual_residual_row_count": oshb_simulation[
                "manual_residual_row_count"
            ],
            "morph_unlock_pilot_non_psalm_book_count": morph_unlock[
                "pilot_mapped_non_psalm_book_count"
            ],
            "morph_unlock_exception_review_row_count": morph_unlock["exception_review_row_count"],
            "morph_unlock_candidate_rule_reduction_pct": morph_unlock[
                "candidate_rule_reduction_pct"
            ],
            "morph_unlock_high_confidence_rule_candidate_count": morph_unlock[
                "high_confidence_rule_candidate_count"
            ],
            "morph_unlock_manual_residual_row_count": morph_unlock["manual_residual_row_count"],
            "morph_unlock_unlockable_priority_unit_count": morph_unlock[
                "unlockable_priority_unit_count"
            ],
            "morph_unlock_projected_review_ready_score_pct": morph_unlock[
                "projected_review_ready_whole_tanakh_score_pct"
            ],
            "morph_unlock_top_exception_book": morph_unlock["top_exception_book"],
            "critical_morph_unlock_unit_count": critical_morph_unlock["critical_unit_count"],
            "critical_morph_unlock_projected_ready_count": critical_morph_unlock[
                "projected_review_ready_critical_unit_count"
            ],
            "critical_morph_unlock_current_score_pct": critical_morph_unlock[
                "mean_current_whole_tanakh_score_pct"
            ],
            "critical_morph_unlock_projected_score_pct": critical_morph_unlock[
                "mean_projected_review_ready_score_pct"
            ],
            "critical_morph_unlock_score_delta_pct": critical_morph_unlock[
                "mean_projected_score_delta_pct"
            ],
            "critical_morph_unlock_imported_books": critical_morph_unlock[
                "current_local_non_psalm_morphology_book_count"
            ],
            "critical_morph_unlock_target_books": critical_morph_unlock[
                "target_non_psalm_book_count"
            ],
            "critical_morph_unlock_exception_rows": critical_morph_unlock[
                "exception_review_row_count"
            ],
            "critical_morph_unlock_review_batches": critical_morph_unlock["review_batch_count"],
            "critical_morph_unlock_top_book": critical_morph_unlock["top_book"],
            "critical_morph_unlock_top_unit": critical_morph_unlock["top_unit_ref"],
            "model_expected_result_count": model_gap["expected_result_count"],
            "model_submitted_result_count": model_gap["submitted_result_count"],
            "model_schema_valid_expected_pct": model_gap["schema_valid_expected_pct"],
            "recommended_local_base": local_selection["best_runnable_candidate"],
            "best_public_hebrew_specialist": local_selection["best_public_hebrew_specialist"],
            "local_bakeoff_candidate_count": local_bakeoff["candidate_count"],
            "local_bakeoff_exact_local_asset_count": local_bakeoff["exact_local_asset_count"],
            "local_bakeoff_best_current_baseline": local_bakeoff["best_current_bakeoff_baseline"],
            "local_bakeoff_best_current_score_pct": local_bakeoff["best_current_bakeoff_score_pct"],
            "local_bakeoff_best_trainable_base": local_bakeoff[
                "best_trainable_base_if_asset_added"
            ],
            "local_bakeoff_best_hebrew_specialist": local_bakeoff[
                "best_hebrew_specialist_candidate"
            ],
            "local_bakeoff_contextual_coverage_pct": local_bakeoff[
                "contextual_valid_model_task_coverage_pct"
            ],
            "local_bakeoff_contextual_anchor_issue_count": local_bakeoff[
                "contextual_source_anchor_issue_count"
            ],
            "model_training_certification_candidate_count": model_training_certification[
                "candidate_count"
            ],
            "model_training_certification_public_fit_count": model_training_certification[
                "public_3090_known_fit_count"
            ],
            "model_training_certification_status": model_training_certification[
                "certification_status"
            ],
            "model_training_certification_frontier_intake": model_training_certification[
                "recommended_frontier_intake"
            ],
            "model_training_certification_claim_text_now": model_training_certification[
                "claim_text_allowed_now"
            ],
            "model_training_certification_context_coverage_pct": model_training_certification[
                "valid_model_task_coverage_pct"
            ],
            "model_training_certification_clean_anchor_pct": model_training_certification[
                "clean_source_anchored_pct"
            ],
            "model_training_certification_projected_review_rows": model_training_certification[
                "projected_model_human_review_rows"
            ],
            "authority_path_phase_count": authority_path["phase_count"],
            "authority_path_blocked_phase_count": authority_path["blocked_phase_count"],
            "authority_path_blocked_gate_count": authority_path["blocked_gate_row_count"],
            "authority_path_review_row_count": authority_path["review_row_count"],
            "authority_path_projected_model_human_review_rows": authority_path[
                "projected_model_human_review_rows"
            ],
            "authority_path_top_reviewer_role": authority_path["top_reviewer_role"],
            "authority_path_top_reviewer_role_row_count": authority_path[
                "top_reviewer_role_row_count"
            ],
            "authority_path_top_gap_ref": authority_path["top_gap_ref"],
            "top_priority_unit": review["top_unit"],
            "top_priority_ref": review["top_ref"],
            "top_priority_score": review["top_packet_priority_score"],
        },
        "requirement_rows": requirement_rows,
        "blocker_rows": blocker_rows,
        "source_boundary_rows": boundary_rows,
        "priority_unit_rows": priority_unit_rows,
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


def bar_rows(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    max_value: float | None = None,
    suffix: str = "",
) -> str:
    if max_value is None:
        max_value = max((float(row.get(value_key) or 0) for row in rows), default=100.0)
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
    requirements = report["requirement_rows"]
    blockers = report["blocker_rows"]
    boundaries = report["source_boundary_rows"]
    priority_units = report["priority_unit_rows"]
    visual = report["visual_data"]

    requirement_table = [
        [
            row["requirement_id"],
            row["requirement"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["blocking_gap"],
        ]
        for row in requirements
    ]
    blocker_table = [
        [
            row["blocker_id"],
            row["severity"],
            row["blocker"],
            row["evidence"],
            ", ".join(row["affected_requirement_ids"]),
            row["next_action"],
        ]
        for row in blockers
    ]
    boundary_table = [
        [
            row["boundary_id"],
            row["boundary"],
            row["rule"],
            row["authority_effect"],
            row["source_artifact"],
        ]
        for row in boundaries
    ]
    priority_table = [
        [
            row["rank"],
            row["unit_id"],
            row["ref"],
            row["packet_priority_score"],
            row["packet_priority_band"],
            row["claim_risk_score"],
            row["packet_review_row_count"],
            ", ".join(row["required_roles"]),
            row["status"],
        ]
        for row in priority_units[:15]
    ]
    role_workload = [
        {
            "role": row["reviewer_role"],
            "total_review_rows": row["total_review_row_count"],
        }
        for row in visual["review_role_workload_rows"]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Doctoral Translation Synthesis</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #53616f;
      --line: #c9d1d9;
      --panel: #f8fafc;
      --accent: #2868a8;
      --accent-2: #9b3d2e;
      --ok: #2f7d46;
      --warn: #b36b00;
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
      font-size: 2.2rem;
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
      max-width: 1000px;
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
      padding: 16px;
      background: var(--panel);
    }}
    .metric-value {{
      color: var(--ink);
      font-size: 1.8rem;
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
      grid-template-columns: minmax(140px, 1.2fr) minmax(140px, 2fr) 90px;
      gap: 10px;
      align-items: center;
      margin: 10px 0;
      font-size: 0.92rem;
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
      font-size: 0.9rem;
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
  <h1>Doctoral Translation Synthesis: Hebrew Psalms to English Authority Readiness</h1>
  <p class="lede">
    This report synthesizes the current hard-data evidence for a local,
    conversational Hebrew-to-English Psalms translation model. It treats Hebrew
    token evidence as primary, separates textual witnesses from source authority,
    and keeps Jewish, Christian, and academic reception lanes distinct.
  </p>
  <div class="callout">
    <strong>Authority boundary:</strong>
    This is a synthesis and audit artifact, not a reviewer signoff. Current state:
    {esc(report["authority_boundary"]["current_state"])}.
    {esc(report["authority_boundary"]["reason"])}
  </div>

  <section class="metric-grid" aria-label="Headline metrics">
    {
        metric_cards(
            [
                (
                    "Synthesis Score",
                    f"{summary['doctoral_synthesis_score_pct']:.2f}%",
                    "Weighted across explicit authority requirements.",
                ),
                (
                    "Underlying Authority",
                    f"{summary['underlying_authority_readiness_score_pct']:.2f}%",
                    "From the scholarly authority readiness audit.",
                ),
                (
                    "Blocked Requirements",
                    fmt_int(summary["blocked_requirement_count"]),
                    f"{fmt_int(summary['critical_blocker_count'])} critical blockers remain.",
                ),
                (
                    "Review Completion",
                    f"{summary['review_completion_pct']:.2f}%",
                    f"{fmt_int(summary['review_workbook_completed_rows'])} of "
                    f"{fmt_int(summary['review_workbook_total_rows'])} rows complete.",
                ),
                (
                    "Critical Path",
                    (
                        f"{fmt_int(summary['authority_path_blocked_phase_count'])}/"
                        f"{fmt_int(summary['authority_path_phase_count'])}"
                    ),
                    (f"{fmt_int(summary['authority_path_blocked_gate_count'])} blocked gates."),
                ),
                (
                    "Accuracy Certification",
                    f"{summary['translation_accuracy_certification_readiness_pct']:.2f}%",
                    (
                        f"{fmt_int(summary['translation_accuracy_blocked_gate_count'])}/"
                        f"{fmt_int(summary['translation_accuracy_gate_count'])} gates blocked; "
                        f"{summary['translation_accuracy_evidence_maturity_pct']:.2f}% "
                        "evidence maturity."
                    ),
                ),
                (
                    "Decision Dossier",
                    fmt_int(summary["critical_unit_decision_unit_count"]),
                    (
                        f"{fmt_int(summary['critical_unit_decision_blocked_lane_count'])} "
                        "blocked lanes; top "
                        f"{summary['critical_unit_decision_top_ref']}."
                    ),
                ),
                (
                    "Review Execution",
                    fmt_int(summary["critical_unit_review_execution_total_rows"]),
                    (
                        f"{fmt_int(summary['critical_unit_review_execution_blocked_gate_count'])} "
                        "blocked gates; top role "
                        f"{summary['critical_unit_review_execution_top_role']}."
                    ),
                ),
                (
                    "Model Cross-Exam",
                    (
                        f"{fmt_int(summary['critical_unit_model_cross_exam_submitted_rows'])}/"
                        f"{fmt_int(summary['critical_unit_model_cross_exam_expected_rows'])}"
                    ),
                    (
                        f"{fmt_int(summary['critical_unit_model_cross_exam_missing_rows'])} "
                        "missing rows; top missing model "
                        f"{summary['critical_unit_model_cross_exam_top_model']}."
                    ),
                ),
                (
                    "Text-Blocked Units",
                    fmt_int(summary["critical_unit_decision_text_blocked_count"]),
                    (
                        f"{fmt_int(summary['critical_unit_decision_clean_model_count'])} "
                        "units have clean source-anchored model evidence."
                    ),
                ),
                (
                    "High-Risk Units",
                    fmt_int(summary["high_risk_claim_unit_count"]),
                    "Claim matrix units requiring elevated controls.",
                ),
                (
                    "Morph Import Plan",
                    summary["morphology_acquisition_recommended_first_import_candidate"],
                    f"{fmt_int(summary['morphology_acquisition_local_non_psalm_book_count'])} "
                    f"of {fmt_int(summary['morphology_acquisition_target_non_psalm_book_count'])} "
                    "non-Psalm books have local morphology.",
                ),
                (
                    "OSHB Pilot",
                    f"{summary['oshb_alignment_pilot_mean_sequence_similarity_pct']:.2f}%",
                    f"{fmt_int(summary['oshb_alignment_pilot_mapped_non_psalm_book_count'])} "
                    "non-Psalm books mapped; not source-approved.",
                ),
                (
                    "Morph Unlock",
                    fmt_int(summary["morph_unlock_unlockable_priority_unit_count"]),
                    (
                        f"{summary['morph_unlock_candidate_rule_reduction_pct']:.2f}% "
                        "candidate rule reduction; projected only."
                    ),
                ),
                (
                    "Critical Morph Unlock",
                    fmt_int(summary["critical_morph_unlock_projected_ready_count"]),
                    (
                        f"{summary['critical_morph_unlock_current_score_pct']:.2f}% -> "
                        f"{summary['critical_morph_unlock_projected_score_pct']:.2f}% "
                        "critical-unit score; projected only."
                    ),
                ),
                (
                    "Recommended Local Base",
                    summary["recommended_local_base"],
                    "Runnable candidate, not approved authority.",
                ),
                (
                    "Bakeoff Baseline",
                    summary["local_bakeoff_best_current_baseline"],
                    (
                        f"{summary['local_bakeoff_best_current_score_pct']:.2f}% "
                        "doctoral bakeoff score."
                    ),
                ),
                (
                    "Training Certification",
                    summary["model_training_certification_status"],
                    (
                        f"{fmt_int(summary['model_training_certification_candidate_count'])} "
                        "candidate rows; "
                        f"{fmt_int(summary['model_training_certification_public_fit_count'])} "
                        "public 3090-fit."
                    ),
                ),
                (
                    "Frontier Intake",
                    summary["model_training_certification_frontier_intake"],
                    (
                        f"{summary['model_training_certification_context_coverage_pct']:.2f}% "
                        "valid contextual coverage; "
                        f"{fmt_int(summary['model_training_certification_claim_text_now'])} "
                        "text-authorized claim rows."
                    ),
                ),
            ]
        )
    }
  </section>

  <section>
    <h2>Visual Readiness</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Requirement Scores</h3>
        {
        bar_rows(
            visual["requirement_score_rows"],
            label_key="requirement_id",
            value_key="score_pct",
            max_value=100,
            suffix="%",
        )
    }
      </div>
      <div class="panel">
        <h3>Contextual Pressure Units</h3>
        {bar_rows(visual["contextual_pressure_rows"], label_key="pressure", value_key="unit_count")}
      </div>
      <div class="panel">
        <h3>Review Workload by Role</h3>
        {bar_rows(role_workload, label_key="role", value_key="total_review_rows")}
      </div>
      <div class="panel">
        <h3>Blocker Severity</h3>
        {bar_rows(visual["blocker_severity_counts"], label_key="severity", value_key="count")}
      </div>
    </div>
  </section>

  <section>
    <h2>Requirement Audit</h2>
    {table(["ID", "Requirement", "Score", "Status", "Evidence", "Blocking Gap"], requirement_table)}
  </section>

  <section>
    <h2>Ranked Blockers</h2>
    {
        table(
            ["ID", "Severity", "Blocker", "Evidence", "Affected Requirements", "Next Action"],
            blocker_table,
        )
    }
  </section>

  <section>
    <h2>Source and Interpretation Boundaries</h2>
    {table(["ID", "Boundary", "Rule", "Authority Effect", "Artifact"], boundary_table)}
  </section>

  <section>
    <h2>Priority Unit Queue</h2>
    {
        table(
            [
                "Rank",
                "Unit",
                "Reference",
                "Packet Score",
                "Band",
                "Claim Risk",
                "Review Rows",
                "Roles",
                "Status",
            ],
            priority_table,
        )
    }
  </section>

  <footer>
    Generated {esc(report["generated_on"])} from current local research artifacts.
    Canonical content and data/raw were not modified.
  </footer>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the doctoral translation synthesis report.",
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument(
        "--requirements-csv-output", type=Path, default=DEFAULT_REQUIREMENT_CSV_OUTPUT
    )
    parser.add_argument("--blockers-csv-output", type=Path, default=DEFAULT_BLOCKER_CSV_OUTPUT)
    parser.add_argument("--boundaries-csv-output", type=Path, default=DEFAULT_BOUNDARY_CSV_OUTPUT)
    parser.add_argument(
        "--priority-units-csv-output", type=Path, default=DEFAULT_PRIORITY_UNIT_CSV_OUTPUT
    )
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.requirements_csv_output, report["requirement_rows"])
    write_csv(args.blockers_csv_output, report["blocker_rows"])
    write_csv(args.boundaries_csv_output, report["source_boundary_rows"])
    write_csv(args.priority_units_csv_output, report["priority_unit_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")


if __name__ == "__main__":
    main()
