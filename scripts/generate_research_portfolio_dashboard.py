from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"
DOC_ROOT = ROOT / "docs" / "research"
DEFAULT_JSON_OUTPUT = REPORT_ROOT / "research_portfolio_dashboard.json"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "research_portfolio_dashboard.html"

ARTIFACTS = {
    "model_data": DOC_ROOT / "local_translation_model_data.json",
    "benchmark_seed": DOC_ROOT / "local_translation_benchmark_seed.json",
    "contextual_rubric": DOC_ROOT / "psalms_contextual_evaluation_rubric.json",
    "corpus_profile": REPORT_ROOT / "psalms_corpus_profile.json",
    "contextual_evaluation": REPORT_ROOT / "psalms_contextual_evaluation.json",
    "tanakh_lexical": REPORT_ROOT / "tanakh_lexical_context.json",
    "lexeme_context_readiness": REPORT_ROOT / "lexeme_context_readiness.json",
    "whole_tanakh_morphology_gap": (REPORT_ROOT / "whole_tanakh_morphology_gap.json"),
    "whole_tanakh_morphology_acquisition": (
        REPORT_ROOT / "whole_tanakh_morphology_acquisition_readiness.json"
    ),
    "oshb_whole_tanakh_alignment_pilot": (REPORT_ROOT / "oshb_whole_tanakh_alignment_pilot.json"),
    "oshb_alignment_exception_review": REPORT_ROOT / "oshb_alignment_exception_review.json",
    "oshb_exception_taxonomy": REPORT_ROOT / "oshb_exception_taxonomy.json",
    "oshb_mapping_rule_simulation": REPORT_ROOT / "oshb_mapping_rule_simulation.json",
    "whole_tanakh_morphology_unlock_matrix": (
        REPORT_ROOT / "whole_tanakh_morphology_unlock_matrix.json"
    ),
    "critical_unit_morphology_unlock": REPORT_ROOT / "critical_unit_morphology_unlock_plan.json",
    "translation_claim_evidence_matrix": (REPORT_ROOT / "translation_claim_evidence_matrix.json"),
    "translation_claim_traceability": REPORT_ROOT / "translation_claim_traceability_audit.json",
    "translation_accuracy_certification": (
        REPORT_ROOT / "translation_accuracy_certification_matrix.json"
    ),
    "critical_unit_decision_dossier": REPORT_ROOT / "critical_unit_decision_dossier.json",
    "critical_unit_review_execution": REPORT_ROOT / "critical_unit_review_execution_plan.json",
    "critical_unit_model_cross_exam": REPORT_ROOT / "critical_unit_model_cross_exam_plan.json",
    "doctoral_context_integration": REPORT_ROOT / "doctoral_context_integration_matrix.json",
    "doctoral_collision_packets": REPORT_ROOT / "doctoral_collision_review_packets.json",
    "doctoral_collision_benchmark": (
        REPORT_ROOT / "doctoral_collision_benchmark_supplement_suite.json"
    ),
    "doctoral_collision_benchmark_cross_exam": (
        REPORT_ROOT / "doctoral_collision_benchmark_supplement_cross_exam_protocol.json"
    ),
    "doctoral_collision_benchmark_dry_run_audit": (
        REPORT_ROOT / "doctoral_collision_benchmark_supplement_dry_run_audit.json"
    ),
    "doctoral_collision_benchmark_review": (
        REPORT_ROOT / "doctoral_collision_benchmark_supplement_review_signoff_plan.json"
    ),
    "doctoral_collision_real_smoke": REPORT_ROOT / "doctoral_collision_real_smoke_report.json",
    "contextual_real_model_evidence_matrix": (
        REPORT_ROOT / "contextual_real_model_evidence_matrix.json"
    ),
    "canonical_context_network": REPORT_ROOT / "canonical_context_network.json",
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
    "canonical_intertext_real_smoke": REPORT_ROOT / "canonical_intertext_real_smoke_report.json",
    "seed_packets": REPORT_ROOT / "psalms_seed_context_packets.json",
    "witness_reception_readiness": (REPORT_ROOT / "witness_reception_readiness.json"),
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
    "reception_interpretation_boundary": (REPORT_ROOT / "reception_interpretation_boundary.json"),
    "reception_divergence": REPORT_ROOT / "reception_divergence_atlas.json",
    "reception_source_packets": REPORT_ROOT / "reception_source_packet_workbook.json",
    "interpretive_tradition_control": (REPORT_ROOT / "interpretive_tradition_control_matrix.json"),
    "interpretive_adjudication": REPORT_ROOT / "interpretive_adjudication_matrix.json",
    "scholarly_casebook": REPORT_ROOT / "scholarly_casebook.json",
    "scholarly_source_maturity": REPORT_ROOT / "scholarly_source_maturity_report.json",
    "contextual_source_packets": REPORT_ROOT / "contextual_source_packet_roadmap.json",
    "contextual_source_acquisition": REPORT_ROOT / "contextual_source_acquisition_plan.json",
    "doctoral_bibliography": REPORT_ROOT / "doctoral_bibliography_provenance.json",
    "doctoral_source_verification": REPORT_ROOT / "doctoral_source_verification.json",
    "source_authority_ladder": REPORT_ROOT / "source_authority_ladder_matrix.json",
    "doctoral_unit_heatmap": REPORT_ROOT / "doctoral_unit_authority_heatmap.json",
    "doctoral_priority_dossier_atlas": REPORT_ROOT / "doctoral_priority_dossier_atlas.json",
    "doctoral_defense_exhibit": REPORT_ROOT / "doctoral_defense_exhibit_pack.json",
    "hebrew_token_defense": REPORT_ROOT / "hebrew_token_defense_matrix.json",
    "semantic_referent_roadmap": REPORT_ROOT / "semantic_referent_enrichment_roadmap.json",
    "contextual_review_signoff": REPORT_ROOT / "contextual_review_signoff_workbook.json",
    "doctoral_synthesis": REPORT_ROOT / "doctoral_translation_synthesis.json",
    "authority_critical_path": REPORT_ROOT / "authority_critical_path_report.json",
    "benchmark_expansion": REPORT_ROOT / "benchmark_100_expansion_plan.json",
    "context_reception_matrix": REPORT_ROOT / "benchmark_context_reception_matrix.json",
    "contextual_pressure_atlas": REPORT_ROOT / "contextual_pressure_atlas.json",
    "contextual_benchmark_coverage": (REPORT_ROOT / "contextual_benchmark_coverage.json"),
    "contextual_gap_benchmark_supplement": (
        REPORT_ROOT / "contextual_gap_benchmark_supplement_suite.json"
    ),
    "contextual_gap_benchmark_supplement_cross_exam": (
        REPORT_ROOT / "contextual_gap_benchmark_supplement_cross_exam_protocol.json"
    ),
    "contextual_gap_benchmark_supplement_dry_run_audit": (
        REPORT_ROOT / "contextual_gap_benchmark_supplement_dry_run_audit.json"
    ),
    "contextual_gap_benchmark_supplement_review_signoff_plan": (
        REPORT_ROOT / "contextual_gap_benchmark_supplement_review_signoff_plan.json"
    ),
    "priority_unit_dossiers": REPORT_ROOT / "priority_unit_dossiers.json",
    "priority_benchmark_supplement": (REPORT_ROOT / "priority_benchmark_supplement_suite.json"),
    "priority_benchmark_supplement_cross_exam": (
        REPORT_ROOT / "priority_benchmark_supplement_cross_exam_protocol.json"
    ),
    "priority_benchmark_supplement_dry_run_audit": (
        REPORT_ROOT / "priority_benchmark_supplement_dry_run_audit.json"
    ),
    "integrated_benchmark_suite": REPORT_ROOT / "integrated_benchmark_suite.json",
    "integrated_benchmark_cross_exam": (
        REPORT_ROOT / "integrated_benchmark_cross_exam_protocol.json"
    ),
    "integrated_benchmark_dry_run_audit": (REPORT_ROOT / "integrated_benchmark_dry_run_audit.json"),
    "integrated_benchmark_result_audit": (REPORT_ROOT / "integrated_benchmark_result_audit.json"),
    "integrated_review_signoff_plan": (REPORT_ROOT / "integrated_review_signoff_plan.json"),
    "contextual_expanded_benchmark_suite": (
        REPORT_ROOT / "contextual_expanded_benchmark_suite.json"
    ),
    "contextual_expanded_benchmark_cross_exam": (
        REPORT_ROOT / "contextual_expanded_benchmark_cross_exam_protocol.json"
    ),
    "contextual_expanded_benchmark_dry_run_audit": (
        REPORT_ROOT / "contextual_expanded_benchmark_dry_run_audit.json"
    ),
    "contextual_expanded_benchmark_result_audit": (
        REPORT_ROOT / "contextual_expanded_benchmark_result_audit.json"
    ),
    "model_evidence_gap": REPORT_ROOT / "model_evidence_gap_report.json",
    "model_output_quality_triage": REPORT_ROOT / "model_output_quality_triage.json",
    "layer_consistency": REPORT_ROOT / "layer_consistency_report.json",
    "layer_remediation_plan": REPORT_ROOT / "layer_remediation_plan.json",
    "layer_remediation_experiment": (REPORT_ROOT / "layer_remediation_experiment_report.json"),
    "contextual_expanded_benchmark_review_signoff_plan": (
        REPORT_ROOT / "contextual_expanded_benchmark_review_signoff_plan.json"
    ),
    "scholarly_authority_readiness": (REPORT_ROOT / "scholarly_authority_readiness.json"),
    "benchmark_suite": REPORT_ROOT / "local_model_benchmark_suite.json",
    "cross_exam_protocol": REPORT_ROOT / "model_cross_exam_protocol.json",
    "runtime_readiness": REPORT_ROOT / "local_runtime_readiness.json",
    "model_asset_inventory": REPORT_ROOT / "local_model_asset_inventory.json",
    "local_model_selection": REPORT_ROOT / "local_model_selection_roadmap.json",
    "local_model_doctoral_bakeoff": REPORT_ROOT / "local_model_doctoral_bakeoff_matrix.json",
    "model_training_certification": REPORT_ROOT / "model_training_certification_roadmap.json",
    "gemma_schema_repair": REPORT_ROOT / "gemma_schema_repair_report.json",
    "structured_output_tuning": REPORT_ROOT / "structured_output_tuning_report.json",
    "real_model_smoke_test": REPORT_ROOT / "real_model_smoke_test_report.json",
    "result_audit": REPORT_ROOT / "local_model_benchmark_result_audit.json",
    "dry_run_audit": REPORT_ROOT / "local_model_benchmark_dry_run_audit.json",
    "review_signoff_plan": REPORT_ROOT / "review_signoff_plan.json",
}

HTML_REPORTS = [
    {
        "label": "Model Research Dashboard",
        "path": "local_translation_model_report.html",
        "purpose": "Model selection priors, source hierarchy, benchmark plan.",
    },
    {
        "label": "Psalms Corpus Profile",
        "path": "psalms_corpus_profile.html",
        "purpose": "Corpus inventory, enrichment coverage, feature pressure.",
    },
    {
        "label": "Contextual Evaluation",
        "path": "psalms_contextual_evaluation.html",
        "purpose": "Scholarly context readiness and stress-case matrix.",
    },
    {
        "label": "Tanakh Lexical Context",
        "path": "tanakh_lexical_context.html",
        "purpose": "Read-only UXLC whole-Tanakh normalized-form profile.",
    },
    {
        "label": "Lexeme Context Readiness",
        "path": "lexeme_context_readiness.html",
        "purpose": "Psalm lexeme coverage and whole-Tanakh context boundary audit.",
    },
    {
        "label": "Whole-Tanakh Morphology Gap",
        "path": "whole_tanakh_morphology_gap.html",
        "purpose": "Hard-data boundary between whole-Tanakh surface context and true morphology.",
    },
    {
        "label": "Whole-Tanakh Morphology Acquisition Readiness",
        "path": "whole_tanakh_morphology_acquisition_readiness.html",
        "purpose": (
            "Ranked OSHB, STEPBible, MACULA, and BHSA acquisition plan with "
            "license posture, import gates, and authority boundaries."
        ),
    },
    {
        "label": "OSHB Whole-Tanakh Alignment Pilot",
        "path": "oshb_whole_tanakh_alignment_pilot.html",
        "purpose": (
            "Remote-in-memory OSHB morphhb WLC alignment pilot against local UXLC, "
            "with book/division metrics and mismatch samples."
        ),
    },
    {
        "label": "OSHB Alignment Exception Review",
        "path": "oshb_alignment_exception_review.html",
        "purpose": (
            "Reviewer queue for remaining OSHB-to-UXLC token exceptions, gate status, "
            "book pressure, and source-approval boundaries."
        ),
    },
    {
        "label": "OSHB Exception Taxonomy",
        "path": "oshb_exception_taxonomy.html",
        "purpose": (
            "Deterministic cause-family grouping and reviewer batch packets for the "
            "complete OSHB exception queue."
        ),
    },
    {
        "label": "OSHB Mapping Rule Simulation",
        "path": "oshb_mapping_rule_simulation.html",
        "purpose": (
            "Deterministic estimate of rule-routable segmentation exceptions versus "
            "manual residual rows."
        ),
    },
    {
        "label": "Whole-Tanakh Morphology Unlock Matrix",
        "path": "whole_tanakh_morphology_unlock_matrix.html",
        "purpose": (
            "Impact matrix for OSHB-derived whole-Tanakh morphology import gates, "
            "exception risk, and priority-unit unlocks."
        ),
    },
    {
        "label": "Critical Unit Morphology Unlock Plan",
        "path": "critical_unit_morphology_unlock_plan.html",
        "purpose": (
            "Critical-unit slice of whole-Tanakh morphology import, OSHB exception "
            "review, mapping-rule simulation, Psalm regression, and release gates."
        ),
    },
    {
        "label": "Translation Claim Evidence Matrix",
        "path": "translation_claim_evidence_matrix.html",
        "purpose": "Unit-level controls for translation, context, witness, and reception claims.",
    },
    {
        "label": "Translation Claim Traceability Audit",
        "path": "translation_claim_traceability_audit.html",
        "purpose": (
            "Claim-family admissibility map for Hebrew, whole-Tanakh, culture, witness, "
            "reception, model, and release claims."
        ),
    },
    {
        "label": "Translation Accuracy Certification Matrix",
        "path": "translation_accuracy_certification_matrix.html",
        "purpose": (
            "Signoff-oriented evidence ledger across lexical, morphology, whole-OT, "
            "culture, witness, Jewish/Christian, model, review, and release gates."
        ),
    },
    {
        "label": "Critical Unit Decision Dossier",
        "path": "critical_unit_decision_dossier.html",
        "purpose": (
            "Committee-style decision-state ledger for highest-pressure units, blocked "
            "lanes, claim admissibility, review workload, and next certifiable actions."
        ),
    },
    {
        "label": "Critical Unit Review Execution Plan",
        "path": "critical_unit_review_execution_plan.html",
        "purpose": (
            "Role workload, review waves, lane dependencies, and release gates for the "
            "currently undecidable critical Psalm units."
        ),
    },
    {
        "label": "Critical Unit Model Cross-Exam Plan",
        "path": "critical_unit_model_cross_exam_plan.html",
        "purpose": (
            "Critical-unit model-task coverage, candidate-output depth, Codex/Claude/"
            "Hebrew-specialist advisory cross-exam rows, and blocked model gates."
        ),
    },
    {
        "label": "Doctoral Context Integration Matrix",
        "path": "doctoral_context_integration_matrix.html",
        "purpose": (
            "Full-unit joined matrix for broader-canon, culture, witness, divine-name, "
            "poetic, reception, and Jewish/Christian context pressure."
        ),
    },
    {
        "label": "Doctoral Collision Review Packets",
        "path": "doctoral_collision_review_packets.html",
        "purpose": (
            "Reviewer packet scaffold and pending decision rows for the hardest "
            "canon/culture/witness/reception collision units."
        ),
    },
    {
        "label": "Doctoral Collision Benchmark Supplement",
        "path": "doctoral_collision_benchmark_supplement_suite.html",
        "purpose": ("Gloss/literal benchmark tasks generated from cross-lens collision packets."),
    },
    {
        "label": "Doctoral Collision Cross-Exam Protocol",
        "path": "doctoral_collision_benchmark_supplement_cross_exam_protocol.html",
        "purpose": "Advisory model-critic packets for collision benchmark candidates.",
    },
    {
        "label": "Doctoral Collision Dry-Run Audit",
        "path": "doctoral_collision_benchmark_supplement_dry_run_audit.html",
        "purpose": "Schema-path audit for collision benchmark result ingestion.",
    },
    {
        "label": "Doctoral Collision Review Signoff Plan",
        "path": "doctoral_collision_benchmark_supplement_review_signoff_plan.html",
        "purpose": "Projected human review and model cross-exam workload.",
    },
    {
        "label": "Doctoral Collision Real Smoke",
        "path": "doctoral_collision_real_smoke_report.html",
        "purpose": (
            "Measured Mistral and Gemma smoke outputs for the top collision benchmark unit."
        ),
    },
    {
        "label": "Contextual Real Model Evidence Matrix",
        "path": "contextual_real_model_evidence_matrix.html",
        "purpose": (
            "Cross-lane measured local-model evidence for canonical, reception, "
            "and collision pressure."
        ),
    },
    {
        "label": "Canonical Context Network",
        "path": "canonical_context_network.html",
        "purpose": "Cross-canon surface-form network for expanded benchmark units.",
    },
    {
        "label": "Canonical Cross-Reference Atlas",
        "path": "canonical_cross_reference_atlas.html",
        "purpose": (
            "Full-corpus UXLC normalized surface-form anchors outside Psalms with Torah, "
            "Prophets, and non-Psalm Writings samples."
        ),
    },
    {
        "label": "Canonical Intertext Benchmark Supplement",
        "path": "canonical_intertext_benchmark_supplement_suite.html",
        "purpose": (
            "Runnable gloss/literal benchmark prompts for high-value Psalm units with "
            "Torah, Prophets, and non-Psalm Writings surface-form anchors."
        ),
    },
    {
        "label": "Canonical Intertext Cross-Exam Protocol",
        "path": "canonical_intertext_benchmark_supplement_cross_exam_protocol.html",
        "purpose": (
            "Advisory Codex, Claude, and Hebrew-specialist judge packets for the "
            "canonical-intertext supplement."
        ),
    },
    {
        "label": "Canonical Intertext Dry-Run Audit",
        "path": "canonical_intertext_benchmark_supplement_dry_run_audit.html",
        "purpose": "Pipeline-only schema and source-anchor audit for placeholder rows.",
    },
    {
        "label": "Canonical Intertext Review Signoff Plan",
        "path": "canonical_intertext_benchmark_supplement_review_signoff_plan.html",
        "purpose": (
            "Projected Hebrew, alignment, lexical, theology, and lyric review workload "
            "for the canonical-intertext supplement."
        ),
    },
    {
        "label": "Canonical Intertext Real Smoke Report",
        "path": "canonical_intertext_real_smoke_report.html",
        "purpose": (
            "Measured one-task Mistral and Gemma smoke evidence for the "
            "canonical-intertext supplement."
        ),
    },
    {
        "label": "Witness and Reception Readiness",
        "path": "witness_reception_readiness.html",
        "purpose": "Witness coverage, source policy, and reception-routing audit.",
    },
    {
        "label": "Witness Divergence",
        "path": "witness_divergence_report.html",
        "purpose": (
            "KJV, ASV, and WEB divergence, divine-name rendering, register, and review-risk data."
        ),
    },
    {
        "label": "Divine Name Policy Pressure",
        "path": "divine_name_policy_report.html",
        "purpose": (
            "Hebrew divine-name/title token counts, English witness renderings, "
            "and policy pressure."
        ),
    },
    {
        "label": "Superscription Context",
        "path": "superscription_context_report.html",
        "purpose": (
            "Psalm superscription, performance, attribution, liturgical, and "
            "historical-notice routing evidence."
        ),
    },
    {
        "label": "Cultural Historical Domain Atlas",
        "path": "cultural_historical_domain_atlas.html",
        "purpose": (
            "Full-corpus cultural, historical, social, cultic, royal, and reception "
            "domain routing evidence."
        ),
    },
    {
        "label": "Poetic Rhetorical Pressure Atlas",
        "path": "poetic_rhetorical_pressure_atlas.html",
        "purpose": (
            "Full-corpus repetition, verbal mood, address, adjacent lexical-overlap, "
            "acrostic, and literary review-routing pressure evidence."
        ),
    },
    {
        "label": "Corpus Reception Signal Atlas",
        "path": "corpus_reception_signal_atlas.html",
        "purpose": (
            "Full-corpus royal, sonship, priesthood, Torah, death/Sheol, nations, "
            "affliction, violence, and divine-name signal routing for separated "
            "Jewish, Christian, academic, Hebrew-source, and textual review."
        ),
    },
    {
        "label": "Reception Signal Benchmark Supplement",
        "path": "reception_signal_benchmark_supplement_suite.html",
        "purpose": (
            "Runnable gloss/literal benchmark prompts for high-pressure corpus "
            "reception signal candidates outside the contextual expanded suite."
        ),
    },
    {
        "label": "Reception Signal Cross-Exam Protocol",
        "path": "reception_signal_benchmark_supplement_cross_exam_protocol.html",
        "purpose": (
            "Advisory Codex, Claude, and Hebrew-specialist judge packets for the "
            "reception-signal supplement."
        ),
    },
    {
        "label": "Reception Signal Dry-Run Audit",
        "path": "reception_signal_benchmark_supplement_dry_run_audit.html",
        "purpose": "Pipeline-only schema and source-anchor audit for placeholder rows.",
    },
    {
        "label": "Reception Signal Review Signoff Plan",
        "path": "reception_signal_benchmark_supplement_review_signoff_plan.html",
        "purpose": (
            "Projected human review and advisory model-critique workload for the "
            "reception-signal supplement."
        ),
    },
    {
        "label": "Reception Signal Real Smoke Report",
        "path": "reception_signal_real_smoke_report.html",
        "purpose": (
            "Measured full-context Psalm 110:2 Mistral and Gemma smoke evidence for "
            "the reception-signal supplement."
        ),
    },
    {
        "label": "Reception Interpretation Boundary",
        "path": "reception_interpretation_boundary.html",
        "purpose": "Unit-level claim controls for Jewish/Christian/cultural frames.",
    },
    {
        "label": "Reception Divergence Atlas",
        "path": "reception_divergence_atlas.html",
        "purpose": (
            "Separated Jewish, Christian, academic, textual-witness, and Hebrew-source "
            "review pressure across reception-sensitive Psalms units."
        ),
    },
    {
        "label": "Reception Source Packet Workbook",
        "path": "reception_source_packet_workbook.html",
        "purpose": (
            "Separated Jewish, Christian, and academic source-packet workload for "
            "split-lane reception units."
        ),
    },
    {
        "label": "Interpretive Tradition Control Matrix",
        "path": "interpretive_tradition_control_matrix.html",
        "purpose": (
            "Joined Jewish, Christian, academic, witness, culture, and Hebrew-source "
            "controls for high-risk interpretive claims."
        ),
    },
    {
        "label": "Interpretive Adjudication Matrix",
        "path": "interpretive_adjudication_matrix.html",
        "purpose": (
            "Lane and gate matrix for Hebrew basis, witnesses, culture, "
            "Jewish/Christian reception, model evidence, and signoff."
        ),
    },
    {
        "label": "Scholarly Casebook",
        "path": "scholarly_casebook.html",
        "purpose": (
            "High-risk unit case studies combining Hebrew tokens, witnesses, "
            "context lanes, model evidence, and unresolved gates."
        ),
    },
    {
        "label": "Scholarly Source Maturity",
        "path": "scholarly_source_maturity_report.html",
        "purpose": (
            "Provenance and authority maturity audit across Hebrew, witness, "
            "context, reception, model, and signoff lanes."
        ),
    },
    {
        "label": "Contextual Source Packet Roadmap",
        "path": "contextual_source_packet_roadmap.html",
        "purpose": (
            "Unit-level packet workload for culture, whole-Tanakh, textual, "
            "Jewish, Christian, academic, and release-review source evidence."
        ),
    },
    {
        "label": "Contextual Source Acquisition Plan",
        "path": "contextual_source_acquisition_plan.html",
        "purpose": (
            "Cited source-candidate acquisition matrix with license risk, "
            "packet-unit impact, phases, and blocked gates."
        ),
    },
    {
        "label": "Doctoral Bibliography and Provenance",
        "path": "doctoral_bibliography_provenance.html",
        "purpose": (
            "Local manifests, external source candidates, license posture, source lanes, "
            "and authority boundaries."
        ),
    },
    {
        "label": "Doctoral Source Verification",
        "path": "doctoral_source_verification.html",
        "purpose": (
            "Live official-URL reachability, redirect, title, license-term, and gap snapshot."
        ),
    },
    {
        "label": "Source Authority Ladder Matrix",
        "path": "source_authority_ladder_matrix.html",
        "purpose": (
            "Unit-level ladder from source-family routing to reachability, license risk, "
            "source approval, packet review, and release blockers."
        ),
    },
    {
        "label": "Doctoral Unit Authority Heatmap",
        "path": "doctoral_unit_authority_heatmap.html",
        "purpose": (
            "Unit-by-lane readiness heatmap for Hebrew basis, whole-Tanakh context, "
            "witnesses, reception, models, review, and release authority."
        ),
    },
    {
        "label": "Doctoral Priority Dossier Atlas",
        "path": "doctoral_priority_dossier_atlas.html",
        "purpose": (
            "Integrated reviewer queue combining Hebrew tokens, whole-Tanakh anchors, "
            "culture, witnesses, reception lanes, model/layer risks, and signoff gaps."
        ),
    },
    {
        "label": "Doctoral Defense Exhibit Pack",
        "path": "doctoral_defense_exhibit_pack.html",
        "purpose": (
            "Committee-style visual exhibits for the highest-pressure units across Hebrew, "
            "whole-Tanakh, culture, witnesses, reception, model, and review blockers."
        ),
    },
    {
        "label": "Hebrew Token Defense Matrix",
        "path": "hebrew_token_defense_matrix.html",
        "purpose": (
            "Token-level evidence for Hebrew surface, lemma, Strong, morphology, "
            "whole-Tanakh anchors, culture, witnesses, and controls."
        ),
    },
    {
        "label": "Semantic/Referent Enrichment Roadmap",
        "path": "semantic_referent_enrichment_roadmap.html",
        "purpose": (
            "Corpus-wide prioritization queue for semantic-role, referent, syntax, "
            "stem, discourse, and reviewer enrichment gaps."
        ),
    },
    {
        "label": "Contextual Review Signoff Workbook",
        "path": "contextual_review_signoff_workbook.html",
        "purpose": (
            "Pending source-packet and source-acquisition review rows, role workload, "
            "and signoff gates."
        ),
    },
    {
        "label": "Doctoral Translation Synthesis",
        "path": "doctoral_translation_synthesis.html",
        "purpose": (
            "Integrated authority-readiness verdict across Hebrew basis, whole-Tanakh context, "
            "culture, witnesses, Jewish/Christian reception, local models, and signoff."
        ),
    },
    {
        "label": "Seed Context Packets",
        "path": "psalms_seed_context_packets.html",
        "purpose": "Evidence packets for benchmark seed units.",
    },
    {
        "label": "100-Unit Benchmark Expansion",
        "path": "benchmark_100_expansion_plan.html",
        "purpose": "Deterministic expansion from seed units to target strata.",
    },
    {
        "label": "Context and Reception Matrix",
        "path": "benchmark_context_reception_matrix.html",
        "purpose": "Context-pressure and reception-routing analysis for 100 units.",
    },
    {
        "label": "Contextual Pressure Atlas",
        "path": "contextual_pressure_atlas.html",
        "purpose": "Cultural, canonical, textual, and reception review atlas.",
    },
    {
        "label": "Contextual Benchmark Coverage",
        "path": "contextual_benchmark_coverage.html",
        "purpose": "Coverage and gap analysis against the 100-unit context atlas.",
    },
    {
        "label": "Contextual Gap Benchmark Supplement",
        "path": "contextual_gap_benchmark_supplement_suite.html",
        "purpose": "Runnable tasks for the highest-scoring uncovered atlas units.",
    },
    {
        "label": "Contextual Gap Cross-Exam",
        "path": "contextual_gap_benchmark_supplement_cross_exam_protocol.html",
        "purpose": "Advisory judge packets for contextual gap supplement tasks.",
    },
    {
        "label": "Contextual Gap Dry-Run Audit",
        "path": "contextual_gap_benchmark_supplement_dry_run_audit.html",
        "purpose": "Pipeline-only validation for contextual gap supplement tasks.",
    },
    {
        "label": "Contextual Gap Review Signoff Plan",
        "path": "contextual_gap_benchmark_supplement_review_signoff_plan.html",
        "purpose": "Human-review routing for contextual gap supplement tasks.",
    },
    {
        "label": "Priority Unit Dossiers",
        "path": "priority_unit_dossiers.html",
        "purpose": "Reviewer-ready packets for highest-priority Psalm units.",
    },
    {
        "label": "Priority Benchmark Supplement",
        "path": "priority_benchmark_supplement_suite.html",
        "purpose": "Supplemental tasks closing top-priority dossier coverage gaps.",
    },
    {
        "label": "Priority Supplement Cross-Exam",
        "path": "priority_benchmark_supplement_cross_exam_protocol.html",
        "purpose": "Advisory judge packets for supplemental priority tasks.",
    },
    {
        "label": "Priority Supplement Dry-Run Audit",
        "path": "priority_benchmark_supplement_dry_run_audit.html",
        "purpose": "Pipeline-only validation for supplemental priority tasks.",
    },
    {
        "label": "Integrated Benchmark Suite",
        "path": "integrated_benchmark_suite.html",
        "purpose": "Merged primary plus priority supplement local-model suite.",
    },
    {
        "label": "Integrated Benchmark Cross-Exam",
        "path": "integrated_benchmark_cross_exam_protocol.html",
        "purpose": "Advisory judge packets for the merged benchmark suite.",
    },
    {
        "label": "Integrated Benchmark Dry-Run Audit",
        "path": "integrated_benchmark_dry_run_audit.html",
        "purpose": "Pipeline-only validation for the merged benchmark suite.",
    },
    {
        "label": "Integrated Result Audit",
        "path": "integrated_benchmark_result_audit.html",
        "purpose": "Real local-model result coverage for the merged benchmark suite.",
    },
    {
        "label": "Integrated Review Signoff Plan",
        "path": "integrated_review_signoff_plan.html",
        "purpose": "Human-review routing and signoff workload for the merged suite.",
    },
    {
        "label": "Contextual Expanded Benchmark Suite",
        "path": "contextual_expanded_benchmark_suite.html",
        "purpose": "Merged integrated plus contextual-gap 112-task benchmark suite.",
    },
    {
        "label": "Contextual Expanded Cross-Exam",
        "path": "contextual_expanded_benchmark_cross_exam_protocol.html",
        "purpose": "Advisory judge packets for the expanded benchmark suite.",
    },
    {
        "label": "Contextual Expanded Dry-Run Audit",
        "path": "contextual_expanded_benchmark_dry_run_audit.html",
        "purpose": "Pipeline-only validation for the expanded benchmark suite.",
    },
    {
        "label": "Contextual Expanded Result Audit",
        "path": "contextual_expanded_benchmark_result_audit.html",
        "purpose": "Real local-model result coverage for the expanded benchmark suite.",
    },
    {
        "label": "Model Evidence Gap Report",
        "path": "model_evidence_gap_report.html",
        "purpose": "Unit-level gaps between high-risk translation claims and real model evidence.",
    },
    {
        "label": "Model Output Quality Triage",
        "path": "model_output_quality_triage.html",
        "purpose": "Heuristic review routing for real local model output text.",
    },
    {
        "label": "Layer Consistency Audit",
        "path": "layer_consistency_report.html",
        "purpose": "Paired gloss/literal differentiation and divine-name consistency audit.",
    },
    {
        "label": "Layer Remediation Plan",
        "path": "layer_remediation_plan.html",
        "purpose": "Action matrix and retry queue for measured layer-contract failures.",
    },
    {
        "label": "Layer Remediation Experiment",
        "path": "layer_remediation_experiment_report.html",
        "purpose": "Before/after paired retry evidence for layer-contract prompt fixes.",
    },
    {
        "label": "Contextual Expanded Review Signoff Plan",
        "path": "contextual_expanded_benchmark_review_signoff_plan.html",
        "purpose": "Human-review routing for the expanded benchmark suite.",
    },
    {
        "label": "Scholarly Authority Readiness",
        "path": "scholarly_authority_readiness.html",
        "purpose": "Gate-level audit of evidence required before authority claims.",
    },
    {
        "label": "Authority Critical Path",
        "path": "authority_critical_path_report.html",
        "purpose": (
            "Ordered blocker-clearance path for source approval, morphology import, "
            "model bakeoff, reviewer load, and release authority."
        ),
    },
    {
        "label": "Benchmark Suite",
        "path": "local_model_benchmark_suite.html",
        "purpose": "Generated gloss/literal tasks and scoring pressure.",
    },
    {
        "label": "Model Cross-Exam Protocol",
        "path": "model_cross_exam_protocol.html",
        "purpose": "Advisory Codex, Claude, and Hebrew-specialist judge packets.",
    },
    {
        "label": "Local Runtime Readiness",
        "path": "local_runtime_readiness.html",
        "purpose": "GPU, runtime, cache, and 3090-class memory planning audit.",
    },
    {
        "label": "Local Model Asset Inventory",
        "path": "local_model_asset_inventory.html",
        "purpose": "Local cache coverage and run-profile suggestions.",
    },
    {
        "label": "Local Model Selection Roadmap",
        "path": "local_model_selection_roadmap.html",
        "purpose": (
            "Current local-model decision matrix, certification gates, and execution phases."
        ),
    },
    {
        "label": "Local Model Doctoral Bakeoff Matrix",
        "path": "local_model_doctoral_bakeoff_matrix.html",
        "purpose": (
            "Joined model-base frontier for 3090-class local execution, Hebrew specialist "
            "intake, schema repair, source anchoring, and authority blockers."
        ),
    },
    {
        "label": "Model Training Certification Roadmap",
        "path": "model_training_certification_roadmap.html",
        "purpose": (
            "3090-class training, adapter, benchmark, source-approval, and release "
            "certification gates for local Hebrew-to-English model work."
        ),
    },
    {
        "label": "Gemma Schema Repair",
        "path": "gemma_schema_repair_report.html",
        "purpose": "Targeted Gemma 4 26B schema, source-anchor, and layer-gate repair evidence.",
    },
    {
        "label": "Structured Output Tuning",
        "path": "structured_output_tuning_report.html",
        "purpose": "Schema-validity comparison across local prompt/runtime attempts.",
    },
    {
        "label": "Real Model Smoke Test",
        "path": "real_model_smoke_test_report.html",
        "purpose": "Automated smoke metrics for submitted real local model rows.",
    },
    {
        "label": "Result Audit",
        "path": "local_model_benchmark_result_audit.html",
        "purpose": "Automated audit of real model benchmark results.",
    },
    {
        "label": "Dry-Run Audit",
        "path": "local_model_benchmark_dry_run_audit.html",
        "purpose": "Pipeline-only placeholder result validation.",
    },
    {
        "label": "Review Signoff Plan",
        "path": "review_signoff_plan.html",
        "purpose": "Human review routing and model cross-examination workload.",
    },
]


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def safe_get(data: dict[str, Any], *keys: str, default: Any = 0) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def canonical_intertext_context(task: dict[str, Any]) -> dict[str, Any]:
    context = safe_get(
        task,
        "generation_input",
        "locked_inputs",
        "canonical_intertext_context",
        default={},
    )
    return context if isinstance(context, dict) else {}


def canonical_anchor_form_labels(context: dict[str, Any], limit: int = 5) -> str:
    anchors = context.get("top_anchor_forms", [])
    if not isinstance(anchors, list):
        return ""
    labels = []
    for anchor in anchors[:limit]:
        if not isinstance(anchor, dict):
            continue
        labels.append(
            f"{anchor.get('form', '')} ({anchor.get('anchor_strength', '')}, "
            f"{anchor.get('outside_psalms_count', 0)})"
        )
    return "; ".join(labels)


def artifact_inventory() -> list[dict[str, Any]]:
    rows = []
    for key, path in ARTIFACTS.items():
        rows.append(
            {
                "key": key,
                "path": str(path.relative_to(ROOT)),
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    for report in HTML_REPORTS:
        path = REPORT_ROOT / report["path"]
        rows.append(
            {
                "key": report["label"],
                "path": str(path.relative_to(ROOT)),
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    return rows


def build_pipeline(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    real_audit = data["result_audit"]["summary"]
    dry_audit = data["dry_run_audit"]["summary"]
    review = data["review_signoff_plan"]["summary"]
    expansion = data["benchmark_expansion"]["summary"]
    context_matrix = data["context_reception_matrix"]["summary"]
    atlas = data["contextual_pressure_atlas"]["summary"]
    coverage = data["contextual_benchmark_coverage"]["summary"]
    contextual_gap = data["contextual_gap_benchmark_supplement"]["summary"]
    contextual_gap_cross_exam = data["contextual_gap_benchmark_supplement_cross_exam"]["summary"]
    contextual_gap_dry = data["contextual_gap_benchmark_supplement_dry_run_audit"]["summary"]
    contextual_gap_review = data["contextual_gap_benchmark_supplement_review_signoff_plan"][
        "summary"
    ]
    dossiers = data["priority_unit_dossiers"]["summary"]
    supplement = data["priority_benchmark_supplement"]["summary"]
    supplement_cross_exam = data["priority_benchmark_supplement_cross_exam"]["summary"]
    supplement_dry = data["priority_benchmark_supplement_dry_run_audit"]["summary"]
    lexeme = data["lexeme_context_readiness"]["summary"]
    morph_gap = data["whole_tanakh_morphology_gap"]["summary"]
    morph_acquisition = data["whole_tanakh_morphology_acquisition"]["summary"]
    oshb_pilot = data["oshb_whole_tanakh_alignment_pilot"]["summary"]
    oshb_exception = data["oshb_alignment_exception_review"]["summary"]
    oshb_taxonomy = data["oshb_exception_taxonomy"]["summary"]
    oshb_simulation = data["oshb_mapping_rule_simulation"]["summary"]
    morph_unlock = data["whole_tanakh_morphology_unlock_matrix"]["summary"]
    critical_unit_morphology_unlock = data["critical_unit_morphology_unlock"]["summary"]
    claim_matrix = data["translation_claim_evidence_matrix"]["summary"]
    claim_traceability = data["translation_claim_traceability"]["summary"]
    translation_accuracy_certification = data["translation_accuracy_certification"]["summary"]
    translation_accuracy_maturity = translation_accuracy_certification[
        "weighted_evidence_maturity_pct"
    ]
    translation_accuracy_readiness = translation_accuracy_certification[
        "weighted_certification_readiness_pct"
    ]
    critical_unit_decision = data["critical_unit_decision_dossier"]["summary"]
    critical_unit_review_execution = data["critical_unit_review_execution"]["summary"]
    critical_unit_model_cross_exam = data["critical_unit_model_cross_exam"]["summary"]
    context_integration = data["doctoral_context_integration"]["summary"]
    collision_packets = data["doctoral_collision_packets"]["summary"]
    collision_benchmark = data["doctoral_collision_benchmark"]["summary"]
    collision_benchmark_cross_exam = data["doctoral_collision_benchmark_cross_exam"]["summary"]
    collision_benchmark_dry_run = data["doctoral_collision_benchmark_dry_run_audit"]["summary"]
    collision_benchmark_review = data["doctoral_collision_benchmark_review"]["summary"]
    collision_real_smoke = data["doctoral_collision_real_smoke"]["summary"]
    contextual_real_model_evidence = data["contextual_real_model_evidence_matrix"]["summary"]
    context_network = data["canonical_context_network"]["summary"]
    cross_reference = data["canonical_cross_reference"]["summary"]
    canonical_intertext_benchmark = data["canonical_intertext_benchmark"]["summary"]
    canonical_intertext_cross_exam = data["canonical_intertext_benchmark_cross_exam"]["summary"]
    canonical_intertext_dry_run = data["canonical_intertext_benchmark_dry_run_audit"]["summary"]
    canonical_intertext_review = data["canonical_intertext_benchmark_review"]["summary"]
    canonical_intertext_real_smoke = data["canonical_intertext_real_smoke"]["summary"]
    witness = data["witness_reception_readiness"]["summary"]
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
    reception_boundary = data["reception_interpretation_boundary"]["summary"]
    reception_divergence = data["reception_divergence"]["summary"]
    reception_source_packets = data["reception_source_packets"]["summary"]
    interpretive_control = data["interpretive_tradition_control"]["summary"]
    interpretive_adjudication = data["interpretive_adjudication"]["summary"]
    scholarly_casebook = data["scholarly_casebook"]["summary"]
    source_maturity = data["scholarly_source_maturity"]["summary"]
    contextual_source_packets = data["contextual_source_packets"]["summary"]
    source_acquisition = data["contextual_source_acquisition"]["summary"]
    doctoral_bibliography = data["doctoral_bibliography"]["summary"]
    doctoral_source_verification = data["doctoral_source_verification"]["summary"]
    source_authority_ladder = data["source_authority_ladder"]["summary"]
    doctoral_unit_heatmap = data["doctoral_unit_heatmap"]["summary"]
    doctoral_priority_dossier_atlas = data["doctoral_priority_dossier_atlas"]["summary"]
    doctoral_defense_exhibit = data["doctoral_defense_exhibit"]["summary"]
    hebrew_token_defense = data["hebrew_token_defense"]["summary"]
    semantic_referent = data["semantic_referent_roadmap"]["summary"]
    review_signoff_workbook = data["contextual_review_signoff"]["summary"]
    doctoral_synthesis = data["doctoral_synthesis"]["summary"]
    authority_critical_path = data["authority_critical_path"]["summary"]
    integrated = data["integrated_benchmark_suite"]["summary"]
    integrated_cross_exam = data["integrated_benchmark_cross_exam"]["summary"]
    integrated_dry = data["integrated_benchmark_dry_run_audit"]["summary"]
    integrated_real_audit = data["integrated_benchmark_result_audit"]["summary"]
    integrated_review = data["integrated_review_signoff_plan"]["summary"]
    contextual_expanded = data["contextual_expanded_benchmark_suite"]["summary"]
    contextual_expanded_cross_exam = data["contextual_expanded_benchmark_cross_exam"]["summary"]
    contextual_expanded_dry = data["contextual_expanded_benchmark_dry_run_audit"]["summary"]
    contextual_expanded_real = data["contextual_expanded_benchmark_result_audit"]["summary"]
    model_evidence_gap = data["model_evidence_gap"]["summary"]
    quality_triage = data["model_output_quality_triage"]["summary"]
    layer_consistency = data["layer_consistency"]["summary"]
    layer_remediation = data["layer_remediation_plan"]["summary"]
    layer_experiment = data["layer_remediation_experiment"]["summary"]
    contextual_expanded_review = data["contextual_expanded_benchmark_review_signoff_plan"][
        "summary"
    ]
    authority = data["scholarly_authority_readiness"]["summary"]
    cross_exam = data["cross_exam_protocol"]["summary"]
    runtime = data["runtime_readiness"]["summary"]
    assets = data["model_asset_inventory"]["summary"]
    local_selection = data["local_model_selection"]["summary"]
    local_bakeoff = data["local_model_doctoral_bakeoff"]["summary"]
    model_training_certification = data["model_training_certification"]["summary"]
    gemma_repair = data["gemma_schema_repair"]["summary"]
    tuning = data["structured_output_tuning"]["summary"]
    smoke = data["real_model_smoke_test"]["summary"]
    expected_results = int(real_audit["expected_result_count"])
    submitted_results = int(real_audit["submitted_result_count"])
    dry_submitted = int(dry_audit["submitted_result_count"])
    integrated_expected_results = int(integrated_real_audit["expected_result_count"])
    integrated_submitted_results = int(integrated_real_audit["submitted_result_count"])
    stages = [
        {
            "stage": "Research Baseline",
            "status": "complete",
            "completion_pct": 100.0,
            "evidence": "Model priors and source hierarchy are documented.",
        },
        {
            "stage": "Corpus Profiling",
            "status": "complete",
            "completion_pct": 100.0,
            "evidence": "Psalms corpus profile generated from content/psalms.",
        },
        {
            "stage": "Context Rubric",
            "status": "complete",
            "completion_pct": 100.0,
            "evidence": "Nine contextual layers and stress cases are defined.",
        },
        {
            "stage": "Whole-Tanakh Form Context",
            "status": "prototype",
            "completion_pct": 55.0,
            "evidence": "UXLC form-level profile exists; lemma-aware retrieval remains open.",
        },
        {
            "stage": "Lexeme Context Readiness",
            "status": "boundary audited",
            "completion_pct": 62.0,
            "evidence": (
                f"{lexeme['strong_coverage_pct']:.2f}% Psalm Strong coverage; "
                f"{lexeme['surface_outside_context_token_pct']:.2f}% outside-form "
                "coverage; whole-Tanakh lemma index missing."
            ),
        },
        {
            "stage": "Whole-Tanakh Morphology Gap",
            "status": "boundary quantified",
            "completion_pct": 55.0,
            "evidence": (
                f"{morph_gap['uxlc_book_count']} UXLC books; "
                f"{morph_gap['local_non_psalm_books_with_hebrew_morphology']} "
                "non-Psalm books with local Hebrew morphology; "
                f"{morph_gap['outside_strong_context_token_pct']:.2f}% outside "
                "Strong-context coverage."
            ),
        },
        {
            "stage": "Whole-Tanakh Morphology Acquisition Readiness",
            "status": morph_acquisition["status"],
            "completion_pct": pct(
                morph_acquisition["local_non_psalm_morphology_book_count"],
                morph_acquisition["target_non_psalm_book_count"],
            ),
            "evidence": (
                f"{morph_acquisition['morphology_candidate_count']} morphology "
                "candidates ranked; first import "
                f"{morph_acquisition['recommended_first_import_candidate']}; "
                f"{morph_acquisition['blocked_gate_count']} blocked gates and "
                f"{morph_acquisition['pilot_partial_gate_count']} pilot-partial gates; "
                f"{morph_acquisition['not_started_gate_count']} not-started gate."
            ),
        },
        {
            "stage": "OSHB Whole-Tanakh Alignment Pilot",
            "status": data["oshb_whole_tanakh_alignment_pilot"]["status"],
            "completion_pct": oshb_pilot["mean_sequence_similarity_pct"],
            "evidence": (
                f"{oshb_pilot['mapped_book_count']} OSHB books mapped to UXLC; "
                f"{oshb_pilot['remote_oshb_word_count']} remote OSHB words; "
                f"{oshb_pilot['exact_sequence_match_pct']:.2f}% exact verse matches; "
                f"{oshb_pilot['mismatch_sample_row_count']} mismatch verses require review."
            ),
        },
        {
            "stage": "OSHB Alignment Exception Review",
            "status": data["oshb_alignment_exception_review"]["status"],
            "completion_pct": pct(
                oshb_exception.get("review_row_count", oshb_exception["sample_row_count"]),
                oshb_exception["mismatch_verse_count"],
            ),
            "evidence": (
                f"{oshb_exception['mismatch_verse_count']} exception verses remain; "
                f"{oshb_exception['token_count_exception_verse_count']} token-count "
                "exceptions; "
                f"{oshb_exception['sequence_only_exception_verse_count']} sequence-only "
                "exceptions; "
                + (
                    "all exception rows are exported, but reviewer signoff remains absent."
                    if int(oshb_exception["unexported_exception_row_count"]) == 0
                    else (
                        f"{oshb_exception['unexported_exception_row_count']} rows still "
                        "need full enumeration."
                    )
                )
            ),
        },
        {
            "stage": "OSHB Exception Taxonomy and Batches",
            "status": data["oshb_exception_taxonomy"]["status"],
            "completion_pct": 100.0,
            "evidence": (
                f"{oshb_taxonomy['taxonomy_cause_count']} cause families; "
                f"{oshb_taxonomy['review_batch_count']} queued review batches; "
                f"{oshb_taxonomy['top_cause_row_count']} rows in top cause "
                f"{oshb_taxonomy['top_cause_family']}; "
                f"{oshb_taxonomy['segmentation_marker_pct']:.2f}% carry OSHB "
                "segmentation markers."
            ),
        },
        {
            "stage": "OSHB Mapping Rule Simulation",
            "status": data["oshb_mapping_rule_simulation"]["status"],
            "completion_pct": oshb_simulation["candidate_rule_reduction_pct"],
            "evidence": (
                f"{oshb_simulation['rule_candidate_after_review_count']} high-confidence "
                "rule candidates; "
                f"{oshb_simulation['targeted_rule_review_count']} targeted-rule-review "
                "rows; "
                f"{oshb_simulation['manual_residual_row_count']} manual/textual residual "
                "rows. No rule is approved."
            ),
        },
        {
            "stage": "Whole-Tanakh Morphology Unlock Matrix",
            "status": data["whole_tanakh_morphology_unlock_matrix"]["status"],
            "completion_pct": 0.0,
            "evidence": (
                f"{morph_unlock['pilot_mapped_non_psalm_book_count']} non-Psalm books "
                "mapped in pilot; "
                f"{morph_unlock['candidate_rule_reduction_pct']:.2f}% candidate rule "
                "reduction; "
                f"{morph_unlock['unlockable_priority_unit_count']} priority units could "
                "become review-ready after approval/import; "
                f"{morph_unlock['manual_residual_row_count']} manual residual rows; "
                "source approval absent."
            ),
        },
        {
            "stage": "Critical Unit Morphology Unlock Plan",
            "status": data["critical_unit_morphology_unlock"]["status"],
            "completion_pct": critical_unit_morphology_unlock[
                "mean_current_whole_tanakh_score_pct"
            ],
            "evidence": "".join(
                [
                    f"{critical_unit_morphology_unlock['critical_unit_count']} critical units; ",
                    "{} projected review-ready after approval/import; ".format(
                        critical_unit_morphology_unlock[
                            "projected_review_ready_critical_unit_count"
                        ]
                    ),
                    "{} of {} non-Psalm books imported; ".format(
                        critical_unit_morphology_unlock[
                            "current_local_non_psalm_morphology_book_count"
                        ],
                        critical_unit_morphology_unlock["target_non_psalm_book_count"],
                    ),
                    "{} exception rows.".format(
                        critical_unit_morphology_unlock["exception_review_row_count"]
                    ),
                ]
            ),
        },
        {
            "stage": "Translation Claim Matrix",
            "status": "claim controls generated",
            "completion_pct": 70.0,
            "evidence": (
                f"{claim_matrix['unit_count']} units mapped; "
                f"{claim_matrix['high_risk_unit_count']} high-risk claim rows; "
                f"{claim_matrix['jewish_christian_separation_unit_count']} require "
                "Jewish/Christian separation."
            ),
        },
        {
            "stage": "Translation Claim Traceability Audit",
            "status": data["translation_claim_traceability"]["status"],
            "completion_pct": 0.0,
            "evidence": (
                f"{claim_traceability['required_claim_row_count']} required claim rows; "
                f"{claim_traceability['notes_or_packets_only_claim_count']} notes/packet-only "
                "claims; "
                f"{claim_traceability['translation_text_allowed_now_count']} currently "
                "allowed in translation text."
            ),
        },
        {
            "stage": "Translation Accuracy Certification Matrix",
            "status": data["translation_accuracy_certification"]["status"],
            "completion_pct": translation_accuracy_certification[
                "weighted_certification_readiness_pct"
            ],
            "evidence": (
                f"{translation_accuracy_certification['dimension_count']} dimensions; "
                f"{translation_accuracy_certification['blocked_gate_count']} blocked gates; "
                f"{translation_accuracy_maturity:.2f}% evidence maturity; "
                f"{translation_accuracy_readiness:.2f}% certification readiness."
            ),
        },
        {
            "stage": "Critical Unit Decision Dossier",
            "status": data["critical_unit_decision_dossier"]["status"],
            "completion_pct": critical_unit_decision["mean_unit_authority_score_pct"],
            "evidence": (
                f"{critical_unit_decision['unit_count']} decision units; "
                f"{critical_unit_decision['blocked_lane_row_count']} blocked decision lanes; "
                f"{critical_unit_decision['text_blocked_unit_count']} text-blocked units; "
                f"top unit {critical_unit_decision['top_decision_ref']}."
            ),
        },
        {
            "stage": "Critical Unit Review Execution Plan",
            "status": data["critical_unit_review_execution"]["status"],
            "completion_pct": critical_unit_review_execution["review_completion_pct"],
            "evidence": (
                f"{critical_unit_review_execution['critical_unit_count']} critical units; "
                f"{critical_unit_review_execution['total_role_review_row_count']} "
                "role/source rows; "
                f"{critical_unit_review_execution['blocked_wave_count']} blocked waves; "
                f"{critical_unit_review_execution['blocked_gate_count']} blocked gates."
            ),
        },
        {
            "stage": "Critical Unit Model Cross-Exam Plan",
            "status": data["critical_unit_model_cross_exam"]["status"],
            "completion_pct": critical_unit_model_cross_exam["model_result_coverage_pct"],
            "evidence": (
                f"{critical_unit_model_cross_exam['critical_task_count']} critical tasks; "
                f"{critical_unit_model_cross_exam['submitted_model_result_count']} of "
                f"{critical_unit_model_cross_exam['expected_model_result_count']} "
                "model-task rows submitted; "
                f"{critical_unit_model_cross_exam['cross_exam_execution_row_count']} "
                "planned advisory judge rows."
            ),
        },
        {
            "stage": "Doctoral Context Integration Matrix",
            "status": data["doctoral_context_integration"]["status"],
            "completion_pct": context_integration["high_pressure_unit_pct"],
            "evidence": (
                f"{context_integration['unit_count']} Psalm units joined across "
                f"{context_integration['lens_count']} context lenses; "
                f"{context_integration['high_pressure_unit_count']} high-pressure "
                "units; "
                f"{context_integration['doctoral_collision_unit_count']} doctoral "
                "collision units where canon, culture, witness, and reception overlap."
            ),
        },
        {
            "stage": "Doctoral Collision Review Packets",
            "status": data["doctoral_collision_packets"]["status"],
            "completion_pct": collision_packets["completion_pct"],
            "evidence": (
                f"{collision_packets['collision_packet_count']} collision packets; "
                f"{collision_packets['decision_row_count']} pending decision rows across "
                f"{collision_packets['lane_count']} lanes and "
                f"{collision_packets['reviewer_role_count']} reviewer roles."
            ),
        },
        {
            "stage": "Doctoral Collision Benchmark Supplement",
            "status": data["doctoral_collision_benchmark"]["status"],
            "completion_pct": 70.0,
            "evidence": (
                f"{collision_benchmark['task_count']} gloss/literal tasks cover "
                f"{collision_benchmark['selected_collision_unit_count']} collision units; "
                f"{collision_benchmark['planned_model_runs']} planned model runs; "
                f"{collision_benchmark['source_pending_decision_count']} source decision "
                "rows remain pending."
            ),
        },
        {
            "stage": "Doctoral Collision Cross-Exam and Review",
            "status": "advisory packets, dry-run audit, and review plan generated",
            "completion_pct": 70.0,
            "evidence": (
                f"{collision_benchmark_cross_exam['packet_count']} advisory packets and "
                f"{collision_benchmark_cross_exam['execution_row_count']} execution rows; "
                f"{collision_benchmark_dry_run['schema_valid_result_count']} schema-valid "
                "dry-run rows; "
                f"{collision_benchmark_review['projected_human_review_rows']} projected "
                "human review rows."
            ),
        },
        {
            "stage": "Doctoral Collision Real Smoke",
            "status": data["doctoral_collision_real_smoke"]["status"],
            "completion_pct": min(70.0, collision_real_smoke["clean_schema_valid_attempt_pct"]),
            "evidence": (
                f"{collision_real_smoke['attempt_count']} real attempts over "
                f"{collision_real_smoke['task_count']} tasks and "
                f"{collision_real_smoke['model_count']} models; "
                f"{collision_real_smoke['schema_valid_attempt_count']} schema-valid; "
                f"{collision_real_smoke['clean_schema_valid_attempt_count']} clean "
                "source-anchored; "
                f"{collision_real_smoke['source_anchor_issue_count']} source-anchor "
                "issues; "
                f"{collision_real_smoke['missing_model_task_count_after_smoke']} "
                "planned model-task rows still missing."
            ),
        },
        {
            "stage": "Contextual Real Model Evidence Matrix",
            "status": data["contextual_real_model_evidence_matrix"]["status"],
            "completion_pct": contextual_real_model_evidence["valid_model_task_coverage_pct"],
            "evidence": (
                f"{contextual_real_model_evidence['attempt_count']} real attempts across "
                f"{contextual_real_model_evidence['lane_count']} context lanes and "
                f"{contextual_real_model_evidence['model_count']} local models; "
                f"{contextual_real_model_evidence['clean_source_anchored_count']} clean "
                "source-anchored attempts; "
                f"{contextual_real_model_evidence['source_anchor_issue_count']} "
                "source-anchor issues; "
                f"{contextual_real_model_evidence['missing_model_task_count_after_smoke']} "
                "planned contextual model-task rows still missing."
            ),
        },
        {
            "stage": "Canonical Context Network",
            "status": "surface network generated",
            "completion_pct": context_network["content_token_outside_context_pct"],
            "evidence": (
                f"{context_network['unit_count']} expanded units; "
                f"{context_network['content_token_outside_context_pct']:.2f}% "
                "content-token outside-Psalms evidence; "
                f"{context_network['review_queue_unit_count']} units carry "
                "review flags."
            ),
        },
        {
            "stage": "Canonical Cross-Reference Atlas",
            "status": data["canonical_cross_reference"]["status"],
            "completion_pct": cross_reference["cross_reference_unit_pct"],
            "evidence": (
                f"{cross_reference['cross_reference_unit_count']} Psalm units have "
                "non-Psalm UXLC anchors; "
                f"{cross_reference['anchor_token_count']} anchor tokens; "
                f"{cross_reference['three_division_unit_count']} units have Torah, "
                "Prophets, and Writings evidence; top priority "
                f"{cross_reference['top_priority_ref']}."
            ),
        },
        {
            "stage": "Canonical Intertext Benchmark Supplement",
            "status": data["canonical_intertext_benchmark"]["status"],
            "completion_pct": pct(
                canonical_intertext_benchmark["selected_intertext_unit_count"],
                canonical_intertext_benchmark["source_three_division_high_value_candidate_count"],
            ),
            "evidence": (
                f"{canonical_intertext_benchmark['task_count']} gloss/literal tasks cover "
                f"{canonical_intertext_benchmark['selected_intertext_unit_count']} "
                "high-value three-division whole-Tanakh units; "
                f"{canonical_intertext_benchmark['planned_model_runs']} planned model runs; "
                f"{canonical_intertext_benchmark['remaining_intertext_candidate_count']} "
                "eligible candidates remain; top selected unit "
                f"{canonical_intertext_benchmark['top_selected_ref']}."
            ),
        },
        {
            "stage": "Canonical Intertext Cross-Exam and Review",
            "status": "protocol and dry-run audit generated; not real model evidence",
            "completion_pct": 70.0,
            "evidence": (
                f"{canonical_intertext_cross_exam['packet_count']} advisory packets; "
                f"{canonical_intertext_cross_exam['execution_row_count']} execution rows; "
                f"{canonical_intertext_dry_run['schema_valid_result_count']} dry-run "
                "schema-valid rows; "
                f"{canonical_intertext_review['projected_human_review_rows']} projected "
                "human review rows."
            ),
        },
        {
            "stage": "Canonical Intertext Real Smoke",
            "status": "one-task real local smoke generated; not scaled evidence",
            "completion_pct": canonical_intertext_real_smoke["valid_model_task_coverage_pct"],
            "evidence": (
                f"{canonical_intertext_real_smoke['attempt_count']} attempts across "
                f"{canonical_intertext_real_smoke['model_count']} local models; "
                f"{canonical_intertext_real_smoke['schema_valid_attempt_count']} "
                "schema-valid attempts; "
                f"{canonical_intertext_real_smoke['source_anchor_issue_count']} "
                "source-anchor issue; clean best "
                f"{canonical_intertext_real_smoke['clean_best_model_profile']}."
            ),
        },
        {
            "stage": "Seed Evidence Packets",
            "status": "prototype",
            "completion_pct": 70.0,
            "evidence": "All seed units have generated form-level context packets.",
        },
        {
            "stage": "100-Unit Benchmark Expansion",
            "status": "curation candidates generated",
            "completion_pct": 70.0,
            "evidence": (
                f"{expansion['selected_unit_count']} units selected; "
                f"{expansion['generated_expansion_units']} need review."
            ),
        },
        {
            "stage": "Context/Reception Matrix",
            "status": "heuristic routing generated",
            "completion_pct": 60.0,
            "evidence": (
                f"{context_matrix['high_pressure_units']} high-pressure units; "
                f"{context_matrix['reception_sensitive_units']} reception-sensitive."
            ),
        },
        {
            "stage": "Witness/Reception Readiness",
            "status": "boundary audited",
            "completion_pct": 72.0,
            "evidence": (
                f"{witness['witness_record_count']} witness rows; "
                f"{witness['lxx_coverage_pct']:.2f}% LXX coverage; "
                f"{witness['atlas_reception_sensitive_units']} reception-sensitive "
                "atlas units."
            ),
        },
        {
            "stage": "Witness Divergence",
            "status": data["witness_divergence"]["status"],
            "completion_pct": witness_divergence["complete_english_witness_unit_pct"],
            "evidence": (
                f"{witness_divergence['complete_english_witness_unit_count']} complete "
                "English-witness units; mean divergence "
                f"{witness_divergence['mean_english_witness_divergence_pct']:.2f}%; "
                f"{witness_divergence['high_divergence_unit_count']} high-divergence units; "
                f"{witness_divergence['divine_name_disagreement_unit_count']} divine-name "
                "rendering disagreements."
            ),
        },
        {
            "stage": "Divine Name Policy Pressure",
            "status": data["divine_name_policy"]["status"],
            "completion_pct": divine_name["divine_title_unit_pct"],
            "evidence": (
                f"{divine_name['divine_title_unit_count']} divine-title units; "
                f"{divine_name['divine_title_token_count']} title tokens; "
                f"{divine_name['yhwh_token_count']} YHWH tokens; "
                f"{divine_name['witness_disagreement_unit_count']} witness disagreements."
            ),
        },
        {
            "stage": "Superscription and Liturgical Context",
            "status": data["superscription_context"]["status"],
            "completion_pct": superscription["context_unit_pct"],
            "evidence": (
                f"{superscription['context_unit_count']} context units; "
                f"{superscription['context_token_count']} context tokens; "
                f"{superscription['historical_notice_unit_count']} historical notices; "
                f"{superscription['technical_term_unit_count']} technical heading terms; "
                f"top priority {superscription['top_priority_ref']}."
            ),
        },
        {
            "stage": "Cultural and Historical Domain Atlas",
            "status": data["cultural_historical_atlas"]["status"],
            "completion_pct": cultural["domain_unit_pct"],
            "evidence": (
                f"{cultural['domain_unit_count']} domain-bearing units; "
                f"{cultural['domain_token_count']} domain-token assignments; "
                f"{cultural['high_priority_unit_count']} high-priority review units; "
                f"top priority {cultural['top_priority_ref']}."
            ),
        },
        {
            "stage": "Poetic and Rhetorical Pressure Atlas",
            "status": data["poetic_rhetorical_atlas"]["status"],
            "completion_pct": poetic["high_pressure_unit_pct"],
            "evidence": (
                f"{poetic['high_pressure_unit_count']} high-pressure units; "
                f"{poetic['volitive_token_count']} volitive tokens; "
                f"{poetic['adjacent_parallelism_proxy_unit_count']} adjacent "
                "parallelism-proxy units; top priority "
                f"{poetic['top_priority_ref']}."
            ),
        },
        {
            "stage": "Corpus Reception Signal Atlas",
            "status": data["corpus_reception_signal"]["status"],
            "completion_pct": corpus_reception_signal["high_pressure_unit_pct"],
            "evidence": (
                f"{corpus_reception_signal['signal_unit_count']} signal-bearing units; "
                f"{corpus_reception_signal['high_pressure_unit_count']} high-pressure "
                "units; "
                f"{corpus_reception_signal['new_high_pressure_expansion_candidate_count']} "
                "new reception expansion candidates; top priority "
                f"{corpus_reception_signal['top_priority_ref']}."
            ),
        },
        {
            "stage": "Reception Signal Benchmark Supplement",
            "status": data["reception_signal_benchmark"]["status"],
            "completion_pct": pct(
                reception_signal_benchmark["selected_reception_signal_unit_count"],
                reception_signal_benchmark["source_expansion_candidate_count"],
            ),
            "evidence": (
                f"{reception_signal_benchmark['task_count']} gloss/literal tasks cover "
                f"{reception_signal_benchmark['selected_reception_signal_unit_count']} "
                "high-pressure reception-signal units; "
                f"{reception_signal_benchmark['planned_model_runs']} planned model runs; "
                f"{reception_signal_benchmark['remaining_reception_signal_candidate_count']} "
                "queue candidates remain; top selected unit "
                f"{reception_signal_benchmark['top_selected_ref']}."
            ),
        },
        {
            "stage": "Reception Signal Cross-Exam and Review",
            "status": "protocol and dry-run audit generated; not real model evidence",
            "completion_pct": 70.0,
            "evidence": (
                f"{reception_signal_cross_exam['packet_count']} advisory packets; "
                f"{reception_signal_cross_exam['execution_row_count']} execution rows; "
                f"{reception_signal_dry_run['schema_valid_result_count']} dry-run "
                "schema-valid rows; "
                f"{reception_signal_review['projected_human_review_rows']} projected "
                "human review rows."
            ),
        },
        {
            "stage": "Reception Signal Real Smoke",
            "status": "one-task full-context local smoke generated; not scaled evidence",
            "completion_pct": reception_signal_real_smoke["valid_model_task_coverage_pct"],
            "evidence": (
                f"{reception_signal_real_smoke['attempt_count']} attempts across "
                f"{reception_signal_real_smoke['model_count']} local models; "
                f"{reception_signal_real_smoke['schema_valid_attempt_count']} "
                "schema-valid attempts; "
                f"{reception_signal_real_smoke['source_anchor_issue_count']} "
                "source-anchor issue; clean best "
                f"{reception_signal_real_smoke['clean_best_model_profile']}."
            ),
        },
        {
            "stage": "Reception Interpretation Boundary",
            "status": "claim controls generated",
            "completion_pct": 100.0,
            "evidence": (
                f"{reception_boundary['reception_sensitive_unit_count']} "
                "reception-sensitive expanded units; "
                f"{reception_boundary['high_boundary_risk_unit_count']} high-risk "
                "boundary units."
            ),
        },
        {
            "stage": "Reception Divergence Atlas",
            "status": data["reception_divergence"]["status"],
            "completion_pct": reception_divergence["jewish_christian_separation_unit_pct"],
            "evidence": (
                f"{reception_divergence['unit_count']} expanded units have reception "
                "divergence review rows; "
                f"{reception_divergence['jewish_christian_separation_unit_count']} "
                "require separated Jewish/Christian lanes; "
                f"{reception_divergence['academic_comparison_unit_count']} require "
                f"academic comparison; top priority {reception_divergence['top_priority_ref']}."
            ),
        },
        {
            "stage": "Reception Source Packet Workbook",
            "status": data["reception_source_packets"]["status"],
            "completion_pct": 70.0,
            "evidence": (
                f"{reception_source_packets['split_lane_unit_count']} split-lane units; "
                f"{reception_source_packets['packet_count']} separated Jewish, Christian, "
                "and academic packet rows; "
                f"{reception_source_packets['reachable_candidate_source_count']} of "
                f"{reception_source_packets['distinct_candidate_source_count']} candidate "
                "source IDs reachable; "
                f"{reception_source_packets['source_approval_count']} approved."
            ),
        },
        {
            "stage": "Interpretive Tradition Control Matrix",
            "status": data["interpretive_tradition_control"]["status"],
            "completion_pct": 0.0,
            "evidence": (
                f"{interpretive_control['jewish_christian_separation_unit_count']} "
                "split-lane units; "
                f"{interpretive_control['packet_count']} reception packets; "
                f"{interpretive_control['source_approval_count']} source approvals; "
                f"{interpretive_control['completed_packet_review_count']} packet reviews "
                "completed."
            ),
        },
        {
            "stage": "Interpretive Adjudication Matrix",
            "status": interpretive_adjudication["status"],
            "completion_pct": pct(
                interpretive_adjudication["gate_count"]
                - interpretive_adjudication["failed_gate_count"],
                interpretive_adjudication["gate_count"],
            ),
            "evidence": (
                f"{interpretive_adjudication['unit_count']} units routed across "
                f"{interpretive_adjudication['lane_count']} adjudication lanes; "
                f"{interpretive_adjudication['jewish_christian_separation_unit_count']} "
                "require Jewish/Christian separation; failed gates: "
                + ", ".join(interpretive_adjudication["failed_gates"])
                + "."
            ),
        },
        {
            "stage": "Scholarly Casebook",
            "status": scholarly_casebook["status"],
            "completion_pct": pct(
                scholarly_casebook["case_count"] - scholarly_casebook["layer_blocker_case_count"],
                scholarly_casebook["case_count"],
            ),
            "evidence": (
                f"{scholarly_casebook['case_count']} high-risk cases; "
                f"{scholarly_casebook['reception_case_count']} require reception "
                f"separation; {scholarly_casebook['layer_blocker_case_count']} "
                "carry layer blockers; top case is "
                f"{scholarly_casebook['top_case_ref']}."
            ),
        },
        {
            "stage": "Scholarly Source Maturity",
            "status": source_maturity["status"],
            "completion_pct": source_maturity["mean_authority_score_pct"],
            "evidence": (
                f"{source_maturity['source_count']} source manifests; "
                f"{source_maturity['strong_evidence_lane_count']} strong evidence lanes; "
                f"{source_maturity['blocked_authority_lane_count']} authority-blocked lanes; "
                f"{source_maturity['blocked_gate_count']} blocked certification gates."
            ),
        },
        {
            "stage": "Contextual Source Packet Roadmap",
            "status": contextual_source_packets["status"],
            "completion_pct": pct(
                contextual_source_packets["gate_count"]
                - contextual_source_packets["blocked_gate_count"],
                contextual_source_packets["gate_count"],
            ),
            "evidence": (
                f"{contextual_source_packets['unit_count']} units mapped to "
                f"{contextual_source_packets['family_assignment_count']} source-family "
                "assignments; "
                f"{contextual_source_packets['blocked_or_routing_source_family_count']} "
                "source families are blocked or routing-only."
            ),
        },
        {
            "stage": "Contextual Source Acquisition Plan",
            "status": source_acquisition["status"],
            "completion_pct": pct(
                source_acquisition["candidate_count"] - source_acquisition["blocked_gate_count"],
                source_acquisition["candidate_count"],
            ),
            "evidence": (
                f"{source_acquisition['candidate_count']} source candidates; "
                f"{source_acquisition['machine_readable_candidate_count']} machine-readable; "
                f"{source_acquisition['low_license_risk_candidate_count']} low-license-risk; "
                f"{source_acquisition['blocked_gate_count']} acquisition gates blocked."
            ),
        },
        {
            "stage": "Doctoral Bibliography and Provenance",
            "status": doctoral_bibliography["status"],
            "completion_pct": pct(
                doctoral_bibliography["lane_count"]
                - doctoral_bibliography["blocked_authority_lane_count"],
                doctoral_bibliography["lane_count"],
            ),
            "evidence": (
                f"{doctoral_bibliography['bibliography_source_count']} source rows; "
                f"{doctoral_bibliography['local_manifest_source_count']} local manifests; "
                f"{doctoral_bibliography['candidate_source_count']} candidates; "
                f"{doctoral_bibliography['blocked_authority_lane_count']} blocked lanes."
            ),
        },
        {
            "stage": "Doctoral Source Verification",
            "status": data["doctoral_source_verification"]["status"],
            "completion_pct": doctoral_source_verification["reachable_url_pct"],
            "evidence": (
                f"{doctoral_source_verification['source_count']} source rows checked; "
                f"{doctoral_source_verification['reachable_url_count']} of "
                f"{doctoral_source_verification['url_source_count']} official URLs reachable; "
                f"{doctoral_source_verification['gap_count']} verification gaps; "
                f"{doctoral_source_verification['source_approval_count']} approvals."
            ),
        },
        {
            "stage": "Source Authority Ladder Matrix",
            "status": data["source_authority_ladder"]["status"],
            "completion_pct": source_authority_ladder["mean_source_authority_readiness_pct"],
            "evidence": (
                f"{source_authority_ladder['unit_count']} high-risk units; "
                f"{source_authority_ladder['critical_gap_unit_count']} critical gaps; "
                f"{source_authority_ladder['candidate_reachable_count']} of "
                f"{source_authority_ladder['candidate_source_count']} candidate sources "
                "reachable; "
                f"{source_authority_ladder['source_approval_count']} source approvals."
            ),
        },
        {
            "stage": "Doctoral Unit Authority Heatmap",
            "status": doctoral_unit_heatmap["status"],
            "completion_pct": doctoral_unit_heatmap["mean_unit_authority_score_pct"],
            "evidence": (
                f"{doctoral_unit_heatmap['unit_count']} units; "
                f"{doctoral_unit_heatmap['required_lane_row_count']} required lane rows; "
                f"{doctoral_unit_heatmap['blocked_unit_count']} blocked units; top gap "
                f"{doctoral_unit_heatmap['top_gap_ref']}."
            ),
        },
        {
            "stage": "Doctoral Priority Dossier Atlas",
            "status": data["doctoral_priority_dossier_atlas"]["status"],
            "completion_pct": doctoral_priority_dossier_atlas["mean_authority_score_pct"],
            "evidence": (
                f"{doctoral_priority_dossier_atlas['unit_count']} integrated dossier units; "
                f"{doctoral_priority_dossier_atlas['critical_unit_count']} critical; "
                f"{doctoral_priority_dossier_atlas['jewish_christian_separation_unit_count']} "
                "require separated Jewish/Christian lanes; top priority "
                f"{doctoral_priority_dossier_atlas['top_priority_ref']}."
            ),
        },
        {
            "stage": "Doctoral Defense Exhibit Pack",
            "status": data["doctoral_defense_exhibit"]["status"],
            "completion_pct": doctoral_defense_exhibit["mean_unit_authority_score_pct"],
            "evidence": (
                f"{doctoral_defense_exhibit['exhibit_unit_count']} exhibit units; "
                f"{doctoral_defense_exhibit['critical_exhibit_unit_count']} critical; "
                f"{doctoral_defense_exhibit['jewish_christian_separation_unit_count']} "
                "require separated Jewish/Christian lanes; top exhibit "
                f"{doctoral_defense_exhibit['top_exhibit_ref']}."
            ),
        },
        {
            "stage": "Hebrew Token Defense Matrix",
            "status": data["hebrew_token_defense"]["status"],
            "completion_pct": 0.0,
            "evidence": (
                f"{hebrew_token_defense['token_count']} tokens across "
                f"{hebrew_token_defense['unit_count']} exhibit units; "
                f"{hebrew_token_defense['anchor_token_count']} whole-Tanakh anchors; "
                f"{hebrew_token_defense['cultural_domain_token_count']} cultural-domain tokens; "
                f"{hebrew_token_defense['source_approved_token_count']} source-approved tokens."
            ),
        },
        {
            "stage": "Semantic/Referent Enrichment Roadmap",
            "status": data["semantic_referent_roadmap"]["status"],
            "completion_pct": semantic_referent["semantic_role_coverage_pct"],
            "evidence": (
                f"{semantic_referent['token_count']} Psalm tokens; "
                f"{semantic_referent['critical_enrichment_token_count']} critical "
                "enrichment tokens; semantic-role coverage "
                f"{semantic_referent['semantic_role_coverage_pct']:.2f}%; referent coverage "
                f"{semantic_referent['referent_coverage_pct']:.2f}%."
            ),
        },
        {
            "stage": "Contextual Review Signoff Workbook",
            "status": review_signoff_workbook["status"],
            "completion_pct": review_signoff_workbook["review_completion_pct"],
            "evidence": (
                f"{review_signoff_workbook['total_review_row_count']} review rows; "
                f"{review_signoff_workbook['packet_review_row_count']} source-packet rows; "
                f"{review_signoff_workbook['source_acquisition_review_row_count']} "
                "source-acquisition rows; "
                f"{review_signoff_workbook['completed_review_row_count']} completed."
            ),
        },
        {
            "stage": "Doctoral Translation Synthesis",
            "status": data["doctoral_synthesis"]["status"],
            "completion_pct": doctoral_synthesis["doctoral_synthesis_score_pct"],
            "evidence": (
                f"{doctoral_synthesis['requirement_count']} requirements; "
                f"{doctoral_synthesis['blocked_requirement_count']} blocked; "
                f"{doctoral_synthesis['blocker_count']} blockers; "
                f"{doctoral_synthesis['review_completion_pct']:.2f}% review completion."
            ),
        },
        {
            "stage": "Authority Critical Path",
            "status": data["authority_critical_path"]["status"],
            "completion_pct": authority_critical_path["review_completion_pct"],
            "evidence": (
                f"{authority_critical_path['blocked_phase_count']} of "
                f"{authority_critical_path['phase_count']} phases blocked; "
                f"{authority_critical_path['blocked_gate_row_count']} blocked gates; "
                f"{authority_critical_path['review_row_count']} review rows; "
                f"{authority_critical_path['projected_model_human_review_rows']} projected "
                "model-human review rows."
            ),
        },
        {
            "stage": "Contextual Pressure Atlas",
            "status": "generated",
            "completion_pct": 75.0,
            "evidence": (
                f"{atlas['ancient_context_unit_count']} ancient-context units; "
                f"{atlas['high_priority_review_unit_count']} priority review units."
            ),
        },
        {
            "stage": "Contextual Benchmark Coverage",
            "status": "gap analysis generated",
            "completion_pct": coverage["coverage_pct"],
            "evidence": (
                f"{coverage['integrated_covered_unit_count']} of "
                f"{coverage['atlas_unit_count']} atlas units covered; "
                f"{coverage['top25_dossier_coverage_pct']:.2f}% top-25 coverage."
            ),
        },
        {
            "stage": "Contextual Gap Supplement",
            "status": "generated and dry-run verified",
            "completion_pct": contextual_gap["projected_expanded_atlas_coverage_pct"],
            "evidence": (
                f"{contextual_gap['task_count']} tasks close "
                f"{contextual_gap['selected_gap_unit_count']} atlas gaps; "
                f"{contextual_gap_dry['schema_valid_result_count']} dry-run rows valid."
            ),
        },
        {
            "stage": "Contextual Gap Cross-Examination",
            "status": "protocol generated",
            "completion_pct": 70.0,
            "evidence": (
                f"{contextual_gap_cross_exam['packet_count']} packets and "
                f"{contextual_gap_cross_exam['execution_row_count']} execution rows; "
                f"{contextual_gap_review['projected_human_review_rows']} projected "
                "human review rows."
            ),
        },
        {
            "stage": "Priority Unit Dossiers",
            "status": "generated",
            "completion_pct": 70.0,
            "evidence": (
                f"{dossiers['dossier_count']} dossiers generated; "
                f"{dossiers['dossiers_without_benchmark_tasks']} need task coverage."
            ),
        },
        {
            "stage": "Priority Benchmark Supplement",
            "status": "generated and dry-run verified",
            "completion_pct": 82.0,
            "evidence": (
                f"{supplement['task_count']} tasks close "
                f"{supplement['closed_dossier_task_gap_count']} dossier gaps; "
                f"{supplement_dry['schema_valid_result_count']} dry-run rows valid."
            ),
        },
        {
            "stage": "Priority Supplement Cross-Exam",
            "status": "protocol generated",
            "completion_pct": 70.0,
            "evidence": (
                f"{supplement_cross_exam['packet_count']} packets and "
                f"{supplement_cross_exam['execution_row_count']} execution rows."
            ),
        },
        {
            "stage": "Integrated Benchmark Suite",
            "status": "merged and dry-run verified",
            "completion_pct": 88.0,
            "evidence": (
                f"{integrated['task_count']} tasks over "
                f"{integrated['unit_count']} units; "
                f"{integrated_dry['schema_valid_result_count']} dry-run rows valid."
            ),
        },
        {
            "stage": "Integrated Cross-Examination",
            "status": "protocol generated",
            "completion_pct": 75.0,
            "evidence": (
                f"{integrated_cross_exam['packet_count']} packets and "
                f"{integrated_cross_exam['execution_row_count']} execution rows."
            ),
        },
        {
            "stage": "Integrated Result Audit",
            "status": "started" if integrated_submitted_results else "not started",
            "completion_pct": pct(
                integrated_submitted_results,
                integrated_expected_results,
            ),
            "evidence": (
                f"Submitted {integrated_submitted_results} of "
                f"{integrated_expected_results} expected rows; "
                f"{integrated_real_audit['schema_valid_result_count']} schema-valid."
            ),
        },
        {
            "stage": "Integrated Review Signoff",
            "status": "planned",
            "completion_pct": 25.0,
            "evidence": (
                f"{integrated_review['projected_human_review_rows']} human rows and "
                f"{integrated_review['projected_model_cross_exam_rows']} advisory "
                "model rows."
            ),
        },
        {
            "stage": "Contextual Expanded Benchmark Suite",
            "status": "merged and dry-run verified",
            "completion_pct": contextual_expanded["projected_atlas_coverage_after_pct"],
            "evidence": (
                f"{contextual_expanded['task_count']} tasks over "
                f"{contextual_expanded['unit_count']} units; "
                f"{contextual_expanded_dry['schema_valid_result_count']} dry-run "
                "rows valid."
            ),
        },
        {
            "stage": "Contextual Expanded Cross-Examination",
            "status": "protocol generated",
            "completion_pct": 75.0,
            "evidence": (
                f"{contextual_expanded_cross_exam['packet_count']} packets and "
                f"{contextual_expanded_cross_exam['execution_row_count']} rows; "
                f"{contextual_expanded_review['projected_human_review_rows']} "
                "projected human review rows."
            ),
        },
        {
            "stage": "Contextual Expanded Result Audit",
            "status": (
                "started" if contextual_expanded_real["submitted_result_count"] else "not started"
            ),
            "completion_pct": pct(
                contextual_expanded_real["submitted_result_count"],
                contextual_expanded_real["expected_result_count"],
            ),
            "evidence": (
                f"{contextual_expanded_real['schema_valid_result_count']} of "
                f"{contextual_expanded_real['submitted_result_count']} submitted "
                "expanded rows are schema-valid; "
                f"{contextual_expanded_real['missing_expected_result_count']} missing."
            ),
        },
        {
            "stage": "Model Evidence Gap Report",
            "status": "gap crosswalk generated",
            "completion_pct": model_evidence_gap["schema_valid_expected_pct"],
            "evidence": (
                f"{model_evidence_gap['unit_without_schema_valid_count']} of "
                f"{model_evidence_gap['expanded_unit_count']} expanded units lack "
                "schema-valid real local output; "
                f"{model_evidence_gap['high_risk_without_schema_valid_count']} "
                "high-risk units remain without valid rows."
            ),
        },
        {
            "stage": "Model Output Quality Triage",
            "status": "heuristic review routing generated",
            "completion_pct": pct(
                quality_triage["schema_valid_candidate_count"],
                quality_triage["candidate_row_count"],
            ),
            "evidence": (
                f"{quality_triage['schema_valid_candidate_count']} of "
                f"{quality_triage['candidate_row_count']} candidate rows are "
                "eligible for text triage; "
                f"{quality_triage['structure_failure_count']} structure failures; "
                f"{quality_triage['contextual_review_required_count']} valid rows "
                "carry contextual review flags."
            ),
        },
        {
            "stage": "Layer Consistency Audit",
            "status": "paired-layer audit generated",
            "completion_pct": pct(
                layer_consistency["schema_valid_pair_count"],
                layer_consistency["paired_unit_model_count"],
            ),
            "evidence": (
                f"{layer_consistency['schema_valid_pair_count']} of "
                f"{layer_consistency['paired_unit_model_count']} paired rows "
                "are schema-valid; "
                f"{layer_consistency['weak_layer_differentiation_pair_count']} "
                "weak differentiation pairs; "
                f"{layer_consistency['exact_duplicate_pair_count']} exact duplicates."
            ),
        },
        {
            "stage": "Layer Remediation Plan",
            "status": (
                "retry gates generated"
                if layer_remediation["runner_contract_ready"]
                else "prompt contracts incomplete"
            ),
            "completion_pct": 100.0 if layer_remediation["runner_contract_ready"] else 50.0,
            "evidence": (
                f"{layer_remediation['action_count']} remediation actions; "
                f"{layer_remediation['retry_task_count']} retry tasks across "
                f"{layer_remediation['retry_pair_count']} paired rows; "
                "runner layer contracts are "
                + ("present" if layer_remediation["runner_contract_ready"] else "missing")
                + "."
            ),
        },
        {
            "stage": "Layer Remediation Experiment",
            "status": layer_experiment["experiment_status"],
            "completion_pct": pct(
                layer_experiment["gate_count"] - layer_experiment["failed_gate_count"],
                layer_experiment["gate_count"],
            ),
            "evidence": (
                f"{layer_experiment['generated_attempt_count']} retry attempts; "
                f"{layer_experiment['best_attempt_schema_valid_pct']:.2f}% "
                "schema-valid on best attempt; "
                f"{layer_experiment['failed_gate_count']} failed gate(s): "
                + ", ".join(layer_experiment["failed_gates"])
                + "."
            ),
        },
        {
            "stage": "Scholarly Authority Readiness",
            "status": "hard blockers identified",
            "completion_pct": authority["authority_readiness_score_pct"],
            "evidence": (
                f"{authority['gate_count']} gates scored; "
                f"{authority['hard_blocker_count']} hard blockers: "
                + ", ".join(authority["hard_blockers"])
                + "."
            ),
        },
        {
            "stage": "Benchmark Suite",
            "status": "ready",
            "completion_pct": 85.0,
            "evidence": "JSONL task suite exists for gloss and literal layers.",
        },
        {
            "stage": "Model Cross-Examination",
            "status": "protocol generated",
            "completion_pct": 55.0,
            "evidence": (
                f"{cross_exam['packet_count']} packets and "
                f"{cross_exam['execution_row_count']} execution rows."
            ),
        },
        {
            "stage": "Local Runtime Readiness",
            "status": "partially ready",
            "completion_pct": runtime["readiness_gate_pass_pct"],
            "evidence": (
                f"{runtime['readiness_gate_pass_count']} of "
                f"{runtime['readiness_gate_count']} gates pass; "
                f"max VRAM {runtime['max_vram_gb']:.2f} GB."
            ),
        },
        {
            "stage": "Local Model Assets",
            "status": "partial coverage",
            "completion_pct": assets["recommended_asset_coverage_pct"],
            "evidence": (
                f"{assets['recommended_models_with_local_assets']} of "
                f"{assets['recommended_model_count']} recommended models have "
                "exact or alias local assets."
            ),
        },
        {
            "stage": "Local Model Selection Roadmap",
            "status": local_selection["selection_status"],
            "completion_pct": pct(
                local_selection["ready_local_candidate_count"],
                local_selection["candidate_count"],
            ),
            "evidence": (
                f"{local_selection['ready_local_candidate_count']} of "
                f"{local_selection['candidate_count']} selection candidates are "
                "immediately runnable; "
                f"Gemma 4 26B baseline schema-valid rate was "
                f"{local_selection['gemma4_26b_baseline_schema_valid_pct']:.2f}% "
                f"with repair at {local_selection['gemma4_26b_repair_schema_valid_pct']:.2f}%; "
                f"Mistral baseline schema-valid rate is "
                f"{local_selection['mistral_schema_valid_pct']:.2f}%."
            ),
        },
        {
            "stage": "Local Model Doctoral Bakeoff Matrix",
            "status": data["local_model_doctoral_bakeoff"]["status"],
            "completion_pct": local_bakeoff["contextual_valid_model_task_coverage_pct"],
            "evidence": (
                f"Best current measured baseline: {local_bakeoff['best_current_bakeoff_baseline']} "
                f"at {local_bakeoff['best_current_bakeoff_score_pct']:.2f}%; "
                f"best trainable target if asset added: "
                f"{local_bakeoff['best_trainable_base_if_asset_added']}; "
                f"{local_bakeoff['exact_local_asset_count']} of "
                f"{local_bakeoff['candidate_count']} candidates have exact local assets; "
                f"{local_bakeoff['contextual_valid_model_task_coverage_pct']:.2f}% contextual "
                "planned-row coverage."
            ),
        },
        {
            "stage": "Model Training Certification Roadmap",
            "status": data["model_training_certification"]["status"],
            "completion_pct": model_training_certification["valid_model_task_coverage_pct"],
            "evidence": (
                f"{model_training_certification['candidate_count']} model candidates; "
                f"{model_training_certification['public_3090_known_fit_count']} public "
                "3090-fit rows; "
                f"{model_training_certification['claim_text_allowed_now']} claim rows "
                "currently text-authorized."
            ),
        },
        {
            "stage": "Gemma Schema Repair",
            "status": gemma_repair["recommended_status"],
            "completion_pct": pct(
                gemma_repair["gate_count"] - gemma_repair["failed_gate_count"],
                gemma_repair["gate_count"],
            ),
            "evidence": (
                f"Best attempt {gemma_repair['best_schema_attempt_label']} reached "
                f"{gemma_repair['best_schema_valid_pct']:.2f}% schema validity, but "
                f"{gemma_repair['best_source_anchor_issue_count']} source-anchor "
                "issue(s) and failed gates remain: " + ", ".join(gemma_repair["failed_gates"]) + "."
            ),
        },
        {
            "stage": "Structured Output Tuning",
            "status": "first valid local output",
            "completion_pct": tuning["schema_valid_pct"],
            "evidence": (
                f"{tuning['schema_valid_attempt_count']} of "
                f"{tuning['attempt_count']} local attempts are schema-valid."
            ),
        },
        {
            "stage": "Real Model Smoke Test",
            "status": "early rows audited",
            "completion_pct": smoke["schema_valid_pct"],
            "evidence": (
                f"{smoke['schema_valid_result_count']} of "
                f"{smoke['submitted_result_count']} submitted rows are "
                f"schema-valid; {real_audit['missing_expected_result_count']} "
                "expected rows are still missing."
            ),
        },
        {
            "stage": "Runner/Scorer Plumbing",
            "status": "dry-run verified",
            "completion_pct": 65.0 if dry_submitted else 45.0,
            "evidence": f"Dry-run rows submitted: {dry_submitted}.",
        },
        {
            "stage": "Real Model Results",
            "status": "started" if submitted_results else "not started",
            "completion_pct": pct(submitted_results, expected_results),
            "evidence": f"Submitted {submitted_results} of {expected_results} expected results.",
        },
        {
            "stage": "Human Review Signoff",
            "status": "planned",
            "completion_pct": 25.0,
            "evidence": (f"Projected human review rows: {review['projected_human_review_rows']}."),
        },
    ]
    return stages


def build_dashboard() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in ARTIFACTS.items()}
    corpus = data["corpus_profile"]["summary"]
    context = data["contextual_evaluation"]["summary"]
    tanakh = data["tanakh_lexical"]["summary"]
    lexeme = data["lexeme_context_readiness"]["summary"]
    context_network = data["canonical_context_network"]["summary"]
    cross_reference = data["canonical_cross_reference"]["summary"]
    canonical_intertext_benchmark = data["canonical_intertext_benchmark"]["summary"]
    canonical_intertext_cross_exam = data["canonical_intertext_benchmark_cross_exam"]["summary"]
    canonical_intertext_dry_run = data["canonical_intertext_benchmark_dry_run_audit"]["summary"]
    canonical_intertext_review = data["canonical_intertext_benchmark_review"]["summary"]
    canonical_intertext_real_smoke = data["canonical_intertext_real_smoke"]["summary"]
    witness = data["witness_reception_readiness"]["summary"]
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
    reception_boundary = data["reception_interpretation_boundary"]["summary"]
    reception_divergence = data["reception_divergence"]["summary"]
    reception_source_packets = data["reception_source_packets"]["summary"]
    interpretive_control = data["interpretive_tradition_control"]["summary"]
    interpretive_adjudication = data["interpretive_adjudication"]["summary"]
    scholarly_casebook = data["scholarly_casebook"]["summary"]
    source_maturity = data["scholarly_source_maturity"]["summary"]
    contextual_source_packets = data["contextual_source_packets"]["summary"]
    source_acquisition = data["contextual_source_acquisition"]["summary"]
    doctoral_bibliography = data["doctoral_bibliography"]["summary"]
    doctoral_source_verification = data["doctoral_source_verification"]["summary"]
    source_authority_ladder = data["source_authority_ladder"]["summary"]
    doctoral_unit_heatmap = data["doctoral_unit_heatmap"]["summary"]
    doctoral_priority_dossier_atlas = data["doctoral_priority_dossier_atlas"]["summary"]
    doctoral_defense_exhibit = data["doctoral_defense_exhibit"]["summary"]
    hebrew_token_defense = data["hebrew_token_defense"]["summary"]
    semantic_referent = data["semantic_referent_roadmap"]["summary"]
    review_signoff_workbook = data["contextual_review_signoff"]["summary"]
    doctoral_synthesis = data["doctoral_synthesis"]["summary"]
    authority_critical_path = data["authority_critical_path"]["summary"]
    packets = data["seed_packets"]["aggregate"]
    expansion = data["benchmark_expansion"]["summary"]
    context_matrix = data["context_reception_matrix"]["summary"]
    atlas = data["contextual_pressure_atlas"]["summary"]
    coverage = data["contextual_benchmark_coverage"]["summary"]
    contextual_gap = data["contextual_gap_benchmark_supplement"]["summary"]
    contextual_gap_cross_exam = data["contextual_gap_benchmark_supplement_cross_exam"]["summary"]
    contextual_gap_dry = data["contextual_gap_benchmark_supplement_dry_run_audit"]["summary"]
    contextual_gap_review = data["contextual_gap_benchmark_supplement_review_signoff_plan"][
        "summary"
    ]
    dossiers = data["priority_unit_dossiers"]["summary"]
    supplement = data["priority_benchmark_supplement"]["summary"]
    supplement_cross_exam = data["priority_benchmark_supplement_cross_exam"]["summary"]
    supplement_dry = data["priority_benchmark_supplement_dry_run_audit"]["summary"]
    integrated = data["integrated_benchmark_suite"]["summary"]
    integrated_cross_exam = data["integrated_benchmark_cross_exam"]["summary"]
    integrated_dry = data["integrated_benchmark_dry_run_audit"]["summary"]
    integrated_real_audit = data["integrated_benchmark_result_audit"]["summary"]
    integrated_review = data["integrated_review_signoff_plan"]["summary"]
    contextual_expanded = data["contextual_expanded_benchmark_suite"]["summary"]
    contextual_expanded_cross_exam = data["contextual_expanded_benchmark_cross_exam"]["summary"]
    contextual_expanded_dry = data["contextual_expanded_benchmark_dry_run_audit"]["summary"]
    contextual_expanded_real = data["contextual_expanded_benchmark_result_audit"]["summary"]
    model_evidence_gap = data["model_evidence_gap"]["summary"]
    quality_triage = data["model_output_quality_triage"]["summary"]
    layer_consistency = data["layer_consistency"]["summary"]
    layer_remediation = data["layer_remediation_plan"]["summary"]
    layer_experiment = data["layer_remediation_experiment"]["summary"]
    contextual_expanded_review = data["contextual_expanded_benchmark_review_signoff_plan"][
        "summary"
    ]
    authority = data["scholarly_authority_readiness"]["summary"]
    suite = data["benchmark_suite"]["summary"]
    cross_exam = data["cross_exam_protocol"]["summary"]
    runtime = data["runtime_readiness"]["summary"]
    assets = data["model_asset_inventory"]["summary"]
    local_selection = data["local_model_selection"]["summary"]
    local_bakeoff = data["local_model_doctoral_bakeoff"]["summary"]
    model_training_certification = data["model_training_certification"]["summary"]
    gemma_repair = data["gemma_schema_repair"]["summary"]
    tuning = data["structured_output_tuning"]["summary"]
    smoke = data["real_model_smoke_test"]["summary"]
    real_audit = data["result_audit"]["summary"]
    dry_audit = data["dry_run_audit"]["summary"]
    review = data["review_signoff_plan"]["summary"]
    morph_gap = data["whole_tanakh_morphology_gap"]["summary"]
    morph_acquisition = data["whole_tanakh_morphology_acquisition"]["summary"]
    oshb_pilot = data["oshb_whole_tanakh_alignment_pilot"]["summary"]
    oshb_exception = data["oshb_alignment_exception_review"]["summary"]
    oshb_taxonomy = data["oshb_exception_taxonomy"]["summary"]
    oshb_simulation = data["oshb_mapping_rule_simulation"]["summary"]
    morph_unlock = data["whole_tanakh_morphology_unlock_matrix"]["summary"]
    critical_unit_morphology_unlock = data["critical_unit_morphology_unlock"]["summary"]
    claim_matrix = data["translation_claim_evidence_matrix"]["summary"]
    claim_traceability = data["translation_claim_traceability"]["summary"]
    translation_accuracy_certification = data["translation_accuracy_certification"]["summary"]
    critical_unit_decision = data["critical_unit_decision_dossier"]["summary"]
    critical_unit_review_execution = data["critical_unit_review_execution"]["summary"]
    critical_unit_model_cross_exam = data["critical_unit_model_cross_exam"]["summary"]
    context_integration = data["doctoral_context_integration"]["summary"]
    collision_packets = data["doctoral_collision_packets"]["summary"]
    collision_benchmark = data["doctoral_collision_benchmark"]["summary"]
    collision_benchmark_cross_exam = data["doctoral_collision_benchmark_cross_exam"]["summary"]
    collision_benchmark_dry_run = data["doctoral_collision_benchmark_dry_run_audit"]["summary"]
    collision_benchmark_review = data["doctoral_collision_benchmark_review"]["summary"]
    collision_real_smoke = data["doctoral_collision_real_smoke"]["summary"]
    contextual_real_model_evidence = data["contextual_real_model_evidence_matrix"]["summary"]
    model_scores = data["model_data"]["candidate_scores"]
    top_model = max(model_scores, key=lambda item: float(item["mean"]))

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "integrated research portfolio dashboard",
        "headline": {
            "recommended_first_base": top_model["model"],
            "recommended_first_base_mean": top_model["mean"],
            "psalm_count": corpus["psalm_count"],
            "unit_count": corpus["unit_count"],
            "token_records": corpus["total_token_records"],
            "units_with_renderings": corpus["units_with_renderings"],
            "context_readiness_mean": context["weighted_readiness_mean"],
            "benchmark_expansion_unit_count": expansion["selected_unit_count"],
            "benchmark_expansion_new_units": expansion["generated_expansion_units"],
            "context_high_pressure_units": context_matrix["high_pressure_units"],
            "context_reception_sensitive_units": context_matrix["reception_sensitive_units"],
            "atlas_ancient_context_units": atlas["ancient_context_unit_count"],
            "atlas_broad_canonical_context_units": atlas["broad_canonical_context_unit_count"],
            "atlas_high_priority_review_units": atlas["high_priority_review_unit_count"],
            "atlas_top_priority_unit": atlas["top_priority_unit"],
            "atlas_top_priority_score": atlas["top_priority_score"],
            "contextual_coverage_pct": coverage["coverage_pct"],
            "contextual_covered_units": coverage["integrated_covered_unit_count"],
            "contextual_uncovered_units": coverage["uncovered_unit_count"],
            "contextual_top25_coverage_pct": coverage["top25_dossier_coverage_pct"],
            "contextual_reception_coverage_pct": coverage["reception_sensitive_coverage_pct"],
            "contextual_textual_coverage_pct": coverage["textual_witness_pressure_coverage_pct"],
            "contextual_top_next_unit": coverage["top_next_unit"],
            "contextual_top_next_unit_gap_score": coverage["top_next_unit_gap_score"],
            "contextual_gap_task_count": contextual_gap["task_count"],
            "contextual_gap_unit_count": contextual_gap["selected_gap_unit_count"],
            "contextual_gap_projected_coverage_pct": contextual_gap[
                "projected_expanded_atlas_coverage_pct"
            ],
            "contextual_gap_remaining_units": contextual_gap["remaining_uncovered_unit_count"],
            "contextual_gap_cross_exam_packets": contextual_gap_cross_exam["packet_count"],
            "contextual_gap_cross_exam_rows": contextual_gap_cross_exam["execution_row_count"],
            "contextual_gap_dry_valid": contextual_gap_dry["schema_valid_result_count"],
            "contextual_gap_review_human_rows": contextual_gap_review[
                "projected_human_review_rows"
            ],
            "priority_dossier_count": dossiers["dossier_count"],
            "priority_dossier_token_count": dossiers["token_count"],
            "priority_dossier_reception_count": dossiers["reception_sensitive_dossiers"],
            "priority_dossier_textual_count": dossiers["textual_witness_pressure_dossiers"],
            "priority_dossier_task_gap_count": dossiers["dossiers_without_benchmark_tasks"],
            "priority_dossier_cross_exam_gap_count": dossiers[
                "dossiers_without_cross_exam_packets"
            ],
            "priority_supplement_task_count": supplement["task_count"],
            "priority_supplement_unit_count": supplement["supplement_unit_count"],
            "priority_supplement_planned_runs": supplement["planned_model_runs"],
            "priority_supplement_closed_gaps": supplement["closed_dossier_task_gap_count"],
            "priority_supplement_cross_exam_packets": supplement_cross_exam["packet_count"],
            "priority_supplement_cross_exam_rows": supplement_cross_exam["execution_row_count"],
            "priority_supplement_dry_valid": supplement_dry["schema_valid_result_count"],
            "priority_supplement_dry_submitted": supplement_dry["submitted_result_count"],
            "integrated_task_count": integrated["task_count"],
            "integrated_unit_count": integrated["unit_count"],
            "integrated_planned_runs": integrated["planned_model_runs"],
            "integrated_token_instances": integrated["token_instances"],
            "integrated_cross_exam_packets": integrated_cross_exam["packet_count"],
            "integrated_cross_exam_rows": integrated_cross_exam["execution_row_count"],
            "integrated_dry_valid": integrated_dry["schema_valid_result_count"],
            "integrated_dry_submitted": integrated_dry["submitted_result_count"],
            "integrated_real_submitted_results": integrated_real_audit["submitted_result_count"],
            "integrated_real_missing_results": integrated_real_audit[
                "missing_expected_result_count"
            ],
            "integrated_real_schema_valid_results": integrated_real_audit[
                "schema_valid_result_count"
            ],
            "integrated_real_source_anchor_issues": integrated_real_audit.get(
                "source_anchor_issue_count",
                0,
            ),
            "integrated_review_candidate_outputs": integrated_review["projected_candidate_outputs"],
            "integrated_review_human_rows": integrated_review["projected_human_review_rows"],
            "integrated_review_model_cross_exam_rows": integrated_review[
                "projected_model_cross_exam_rows"
            ],
            "contextual_expanded_task_count": contextual_expanded["task_count"],
            "contextual_expanded_unit_count": contextual_expanded["unit_count"],
            "contextual_expanded_planned_runs": contextual_expanded["planned_model_runs"],
            "contextual_expanded_projected_coverage_pct": contextual_expanded[
                "projected_atlas_coverage_after_pct"
            ],
            "contextual_expanded_cross_exam_packets": contextual_expanded_cross_exam[
                "packet_count"
            ],
            "contextual_expanded_cross_exam_rows": contextual_expanded_cross_exam[
                "execution_row_count"
            ],
            "contextual_expanded_dry_valid": contextual_expanded_dry["schema_valid_result_count"],
            "contextual_expanded_real_submitted_results": contextual_expanded_real[
                "submitted_result_count"
            ],
            "contextual_expanded_real_schema_valid_results": contextual_expanded_real[
                "schema_valid_result_count"
            ],
            "contextual_expanded_real_missing_results": contextual_expanded_real[
                "missing_expected_result_count"
            ],
            "contextual_expanded_real_source_anchor_issues": contextual_expanded_real.get(
                "source_anchor_issue_count",
                0,
            ),
            "model_evidence_gap_expected_results": model_evidence_gap["expected_result_count"],
            "model_evidence_gap_submitted_results": model_evidence_gap["submitted_result_count"],
            "model_evidence_gap_schema_valid_expected_pct": model_evidence_gap[
                "schema_valid_expected_pct"
            ],
            "model_evidence_gap_units_without_valid": model_evidence_gap[
                "unit_without_schema_valid_count"
            ],
            "model_evidence_gap_high_risk_without_valid": model_evidence_gap[
                "high_risk_without_schema_valid_count"
            ],
            "model_evidence_gap_top_unit": model_evidence_gap["top_gap_unit"],
            "model_evidence_gap_top_score": model_evidence_gap["top_gap_priority_score"],
            "model_evidence_gap_top_no_real_unit": model_evidence_gap[
                "top_no_real_model_evidence_unit"
            ],
            "model_evidence_gap_top_no_real_ref": model_evidence_gap[
                "top_no_real_model_evidence_ref"
            ],
            "quality_triage_candidate_rows": quality_triage["candidate_row_count"],
            "quality_triage_schema_valid_candidates": quality_triage[
                "schema_valid_candidate_count"
            ],
            "quality_triage_structure_failures": quality_triage["structure_failure_count"],
            "quality_triage_contextual_review_required": quality_triage[
                "contextual_review_required_count"
            ],
            "quality_triage_mean_review_priority_score": quality_triage[
                "mean_review_priority_score"
            ],
            "quality_triage_top_review_priority_task": quality_triage["top_review_priority_task"],
            "quality_triage_top_review_priority_score": quality_triage["top_review_priority_score"],
            "layer_consistency_paired_count": layer_consistency["paired_unit_model_count"],
            "layer_consistency_schema_valid_pairs": layer_consistency["schema_valid_pair_count"],
            "layer_consistency_weak_differentiation_pairs": layer_consistency[
                "weak_layer_differentiation_pair_count"
            ],
            "layer_consistency_exact_duplicate_pairs": layer_consistency[
                "exact_duplicate_pair_count"
            ],
            "layer_consistency_divine_name_pairs": layer_consistency["divine_name_pair_count"],
            "layer_consistency_divine_name_inconsistent_pairs": layer_consistency[
                "divine_name_inconsistent_pair_count"
            ],
            "layer_consistency_mean_word_jaccard_pct": layer_consistency["mean_word_jaccard_pct"],
            "layer_consistency_top_layer_risk_unit": layer_consistency["top_layer_risk_unit"],
            "layer_consistency_top_layer_risk_ref": layer_consistency["top_layer_risk_ref"],
            "layer_consistency_top_layer_risk_score": layer_consistency["top_layer_risk_score"],
            "layer_remediation_action_count": layer_remediation["action_count"],
            "layer_remediation_critical_action_count": layer_remediation["critical_action_count"],
            "layer_remediation_high_action_count": layer_remediation["high_action_count"],
            "layer_remediation_retry_task_count": layer_remediation["retry_task_count"],
            "layer_remediation_retry_pair_count": layer_remediation["retry_pair_count"],
            "layer_remediation_runner_contract_ready": layer_remediation["runner_contract_ready"],
            "layer_remediation_top_retry_task": layer_remediation["top_retry_task"],
            "layer_remediation_top_retry_ref": layer_remediation["top_retry_ref"],
            "layer_experiment_generated_attempts": layer_experiment["generated_attempt_count"],
            "layer_experiment_best_attempt": layer_experiment["best_attempt_label"],
            "layer_experiment_best_schema_valid_pct": layer_experiment[
                "best_attempt_schema_valid_pct"
            ],
            "layer_experiment_best_exact_duplicates": layer_experiment[
                "best_attempt_exact_duplicate_pair_count"
            ],
            "layer_experiment_best_weak_diff": layer_experiment[
                "best_attempt_weak_layer_differentiation_pair_count"
            ],
            "layer_experiment_best_overlap_pct": layer_experiment[
                "best_attempt_mean_word_jaccard_pct"
            ],
            "layer_experiment_failed_gate_count": layer_experiment["failed_gate_count"],
            "layer_experiment_failed_gates": layer_experiment["failed_gates"],
            "layer_experiment_status": layer_experiment["experiment_status"],
            "contextual_expanded_review_human_rows": contextual_expanded_review[
                "projected_human_review_rows"
            ],
            "authority_readiness_score_pct": authority["authority_readiness_score_pct"],
            "authority_hard_blocker_count": authority["hard_blocker_count"],
            "authority_hard_blockers": authority["hard_blockers"],
            "authority_lowest_projected_domain": authority["lowest_projected_domain"],
            "authority_lowest_projected_domain_coverage_pct": authority[
                "lowest_projected_domain_coverage_pct"
            ],
            "lexeme_strong_coverage_pct": lexeme["strong_coverage_pct"],
            "lexeme_lemma_coverage_pct": lexeme["lemma_coverage_pct"],
            "lexeme_surface_outside_pct": lexeme["surface_outside_context_token_pct"],
            "lexeme_semantic_role_pct": lexeme["semantic_role_coverage_pct"],
            "lexeme_benchmark_high_risk_units": lexeme["benchmark_units_with_high_risk_tags"],
            "whole_tanakh_morphology_uxlc_books": morph_gap["uxlc_book_count"],
            "whole_tanakh_non_psalm_morphology_books": morph_gap[
                "local_non_psalm_books_with_hebrew_morphology"
            ],
            "whole_tanakh_outside_strong_context_pct": morph_gap[
                "outside_strong_context_token_pct"
            ],
            "whole_tanakh_surface_bridge_pct": morph_gap["surface_outside_context_token_pct"],
            "whole_tanakh_top_pressure_strong": morph_gap["top_pressure_strong"],
            "whole_tanakh_top_pressure_score": morph_gap["top_pressure_score"],
            "morphology_acquisition_candidate_count": morph_acquisition[
                "morphology_candidate_count"
            ],
            "morphology_acquisition_machine_readable_count": morph_acquisition[
                "machine_readable_candidate_count"
            ],
            "morphology_acquisition_low_license_risk_count": morph_acquisition[
                "low_license_risk_candidate_count"
            ],
            "morphology_acquisition_research_only_count": morph_acquisition[
                "research_only_candidate_count"
            ],
            "morphology_acquisition_blocked_gate_count": morph_acquisition["blocked_gate_count"],
            "morphology_acquisition_not_started_gate_count": morph_acquisition[
                "not_started_gate_count"
            ],
            "morphology_acquisition_pilot_partial_gate_count": morph_acquisition[
                "pilot_partial_gate_count"
            ],
            "morphology_acquisition_recommended_first_import": morph_acquisition[
                "recommended_first_import_candidate"
            ],
            "morphology_acquisition_recommended_semantic_enrichment": morph_acquisition[
                "recommended_semantic_enrichment_candidate"
            ],
            "morphology_acquisition_local_non_psalm_book_count": morph_acquisition[
                "local_non_psalm_morphology_book_count"
            ],
            "morphology_acquisition_target_non_psalm_book_count": morph_acquisition[
                "target_non_psalm_book_count"
            ],
            "oshb_alignment_pilot_mapped_book_count": oshb_pilot["mapped_book_count"],
            "oshb_alignment_pilot_mapped_non_psalm_book_count": oshb_pilot[
                "mapped_non_psalm_book_count"
            ],
            "oshb_alignment_pilot_remote_word_count": oshb_pilot["remote_oshb_word_count"],
            "oshb_alignment_pilot_morph_coverage_pct": oshb_pilot["remote_oshb_morph_coverage_pct"],
            "oshb_alignment_pilot_exact_sequence_match_pct": oshb_pilot["exact_sequence_match_pct"],
            "oshb_alignment_pilot_token_count_match_pct": oshb_pilot["token_count_match_pct"],
            "oshb_alignment_pilot_mean_sequence_similarity_pct": oshb_pilot[
                "mean_sequence_similarity_pct"
            ],
            "oshb_alignment_pilot_mismatch_row_count": oshb_pilot["mismatch_sample_row_count"],
            "oshb_alignment_pilot_source_approval_status": oshb_pilot["source_approval_status"],
            "oshb_exception_review_mismatch_verse_count": oshb_exception["mismatch_verse_count"],
            "oshb_exception_review_mismatch_verse_pct": oshb_exception["mismatch_verse_pct"],
            "oshb_exception_review_token_count_exception_verse_count": oshb_exception[
                "token_count_exception_verse_count"
            ],
            "oshb_exception_review_sequence_only_exception_verse_count": oshb_exception[
                "sequence_only_exception_verse_count"
            ],
            "oshb_exception_review_sample_row_count": oshb_exception["sample_row_count"],
            "oshb_exception_review_review_row_count": oshb_exception.get(
                "review_row_count",
                oshb_exception["sample_row_count"],
            ),
            "oshb_exception_review_unexported_exception_row_count": oshb_exception[
                "unexported_exception_row_count"
            ],
            "oshb_exception_review_critical_book_count": oshb_exception["critical_book_count"],
            "oshb_exception_review_high_book_count": oshb_exception["high_book_count"],
            "oshb_exception_review_psalms_exception_verse_count": oshb_exception[
                "psalms_exception_verse_count"
            ],
            "oshb_exception_review_top_exception_book": oshb_exception["top_exception_book"],
            "oshb_exception_review_top_exception_book_score": oshb_exception[
                "top_exception_book_score"
            ],
            "oshb_exception_taxonomy_cause_count": oshb_taxonomy["taxonomy_cause_count"],
            "oshb_exception_taxonomy_review_batch_count": oshb_taxonomy["review_batch_count"],
            "oshb_exception_taxonomy_review_packet_row_count": oshb_taxonomy[
                "review_packet_row_count"
            ],
            "oshb_exception_taxonomy_top_cause_family": oshb_taxonomy["top_cause_family"],
            "oshb_exception_taxonomy_top_cause_row_count": oshb_taxonomy["top_cause_row_count"],
            "oshb_exception_taxonomy_segmentation_marker_pct": oshb_taxonomy[
                "segmentation_marker_pct"
            ],
            "oshb_exception_taxonomy_manual_primary_review_row_count": oshb_taxonomy[
                "manual_primary_review_row_count"
            ],
            "oshb_exception_taxonomy_psalm_regression_row_count": oshb_taxonomy[
                "psalm_regression_row_count"
            ],
            "oshb_exception_taxonomy_aramaic_review_row_count": oshb_taxonomy[
                "aramaic_review_row_count"
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
            "oshb_mapping_rule_simulation_psalm_rule_candidate_row_count": oshb_simulation[
                "psalm_rule_candidate_row_count"
            ],
            "oshb_mapping_rule_simulation_aramaic_rule_candidate_row_count": oshb_simulation[
                "aramaic_rule_candidate_row_count"
            ],
            "morph_unlock_pilot_non_psalm_books": morph_unlock["pilot_mapped_non_psalm_book_count"],
            "morph_unlock_exception_rows": morph_unlock["exception_review_row_count"],
            "morph_unlock_rule_reduction_pct": morph_unlock["candidate_rule_reduction_pct"],
            "morph_unlock_high_confidence_rule_rows": morph_unlock[
                "high_confidence_rule_candidate_count"
            ],
            "morph_unlock_manual_residual_rows": morph_unlock["manual_residual_row_count"],
            "morph_unlock_unlockable_units": morph_unlock["unlockable_priority_unit_count"],
            "morph_unlock_projected_review_ready_score_pct": morph_unlock[
                "projected_review_ready_whole_tanakh_score_pct"
            ],
            "morph_unlock_top_exception_book": morph_unlock["top_exception_book"],
            "critical_unit_morphology_unlock_status": critical_unit_morphology_unlock[
                "certification_status"
            ],
            "critical_unit_morphology_unlock_unit_count": critical_unit_morphology_unlock[
                "critical_unit_count"
            ],
            "critical_unit_morphology_unlock_projected_ready_count": (
                critical_unit_morphology_unlock["projected_review_ready_critical_unit_count"]
            ),
            "critical_unit_morphology_unlock_current_score_pct": (
                critical_unit_morphology_unlock["mean_current_whole_tanakh_score_pct"]
            ),
            "critical_unit_morphology_unlock_projected_score_pct": (
                critical_unit_morphology_unlock["mean_projected_review_ready_score_pct"]
            ),
            "critical_unit_morphology_unlock_score_delta_pct": (
                critical_unit_morphology_unlock["mean_projected_score_delta_pct"]
            ),
            "critical_unit_morphology_unlock_imported_books": (
                critical_unit_morphology_unlock["current_local_non_psalm_morphology_book_count"]
            ),
            "critical_unit_morphology_unlock_target_books": critical_unit_morphology_unlock[
                "target_non_psalm_book_count"
            ],
            "critical_unit_morphology_unlock_exception_rows": critical_unit_morphology_unlock[
                "exception_review_row_count"
            ],
            "critical_unit_morphology_unlock_review_batches": critical_unit_morphology_unlock[
                "review_batch_count"
            ],
            "critical_unit_morphology_unlock_rule_reduction_pct": (
                critical_unit_morphology_unlock["candidate_rule_reduction_pct"]
            ),
            "critical_unit_morphology_unlock_top_unit": critical_unit_morphology_unlock[
                "top_unit_ref"
            ],
            "critical_unit_morphology_unlock_top_book": critical_unit_morphology_unlock["top_book"],
            "claim_matrix_unit_count": claim_matrix["unit_count"],
            "claim_matrix_high_risk_units": claim_matrix["high_risk_unit_count"],
            "claim_matrix_medium_risk_units": claim_matrix["medium_risk_unit_count"],
            "claim_matrix_reception_sensitive_units": claim_matrix[
                "reception_sensitive_unit_count"
            ],
            "claim_matrix_jewish_christian_units": claim_matrix[
                "jewish_christian_separation_unit_count"
            ],
            "claim_matrix_ancient_culture_units": claim_matrix[
                "ancient_culture_pressure_unit_count"
            ],
            "claim_matrix_textual_witness_units": claim_matrix[
                "textual_witness_pressure_unit_count"
            ],
            "claim_matrix_surface_bridge_units": claim_matrix["surface_bridge_unit_count"],
            "claim_matrix_outside_strong_supported_pct": claim_matrix[
                "outside_strong_supported_unit_pct"
            ],
            "claim_matrix_top_risk_unit": claim_matrix["top_claim_risk_unit"],
            "claim_matrix_top_risk_score": claim_matrix["top_claim_risk_score"],
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
            "translation_accuracy_certification_status": translation_accuracy_certification[
                "certification_status"
            ],
            "translation_accuracy_evidence_maturity_pct": translation_accuracy_certification[
                "weighted_evidence_maturity_pct"
            ],
            "translation_accuracy_certification_readiness_pct": (
                translation_accuracy_certification["weighted_certification_readiness_pct"]
            ),
            "translation_accuracy_blocked_gate_count": translation_accuracy_certification[
                "blocked_gate_count"
            ],
            "translation_accuracy_gate_count": translation_accuracy_certification["gate_count"],
            "translation_accuracy_blocked_dimension_count": translation_accuracy_certification[
                "blocked_dimension_count"
            ],
            "translation_accuracy_release_authorized_dimension_count": (
                translation_accuracy_certification["release_authorized_dimension_count"]
            ),
            "translation_accuracy_top_dimension_gap": translation_accuracy_certification[
                "top_dimension_gap"
            ],
            "translation_accuracy_top_unit_ref": translation_accuracy_certification["top_unit_ref"],
            "critical_unit_decision_status": critical_unit_decision["certification_status"],
            "critical_unit_decision_unit_count": critical_unit_decision["unit_count"],
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
            "critical_unit_review_execution_status": critical_unit_review_execution[
                "certification_status"
            ],
            "critical_unit_review_execution_unit_count": critical_unit_review_execution[
                "critical_unit_count"
            ],
            "critical_unit_review_execution_role_rows": critical_unit_review_execution[
                "total_role_review_row_count"
            ],
            "critical_unit_review_execution_completed_rows": critical_unit_review_execution[
                "completed_role_review_row_count"
            ],
            "critical_unit_review_execution_completion_pct": critical_unit_review_execution[
                "review_completion_pct"
            ],
            "critical_unit_review_execution_blocked_waves": critical_unit_review_execution[
                "blocked_wave_count"
            ],
            "critical_unit_review_execution_blocked_gates": critical_unit_review_execution[
                "blocked_gate_count"
            ],
            "critical_unit_review_execution_top_role": critical_unit_review_execution["top_role"],
            "critical_unit_review_execution_top_role_rows": critical_unit_review_execution[
                "top_role_review_rows"
            ],
            "critical_unit_review_execution_top_wave": critical_unit_review_execution["top_wave"],
            "critical_unit_review_execution_top_wave_rows": critical_unit_review_execution[
                "top_wave_review_rows"
            ],
            "critical_unit_model_cross_exam_status": critical_unit_model_cross_exam[
                "certification_status"
            ],
            "critical_unit_model_cross_exam_task_count": critical_unit_model_cross_exam[
                "critical_task_count"
            ],
            "critical_unit_model_cross_exam_planned_models": critical_unit_model_cross_exam[
                "planned_model_count"
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
            "critical_unit_model_cross_exam_top_unit": critical_unit_model_cross_exam[
                "top_missing_unit_ref"
            ],
            "context_integration_unit_count": context_integration["unit_count"],
            "context_integration_lens_count": context_integration["lens_count"],
            "context_integration_high_pressure_unit_count": context_integration[
                "high_pressure_unit_count"
            ],
            "context_integration_high_pressure_unit_pct": context_integration[
                "high_pressure_unit_pct"
            ],
            "context_integration_multi_lens_unit_count": context_integration[
                "multi_lens_unit_count"
            ],
            "context_integration_doctoral_collision_unit_count": context_integration[
                "doctoral_collision_unit_count"
            ],
            "context_integration_top_ref": context_integration["top_ref"],
            "context_integration_top_score": context_integration["top_integration_pressure_score"],
            "context_integration_jewish_christian_unit_count": context_integration[
                "jewish_christian_separation_unit_count"
            ],
            "collision_packet_count": collision_packets["collision_packet_count"],
            "collision_decision_row_count": collision_packets["decision_row_count"],
            "collision_pending_decision_count": collision_packets["pending_decision_count"],
            "collision_lane_count": collision_packets["lane_count"],
            "collision_reviewer_role_count": collision_packets["reviewer_role_count"],
            "collision_jewish_christian_packet_count": collision_packets[
                "jewish_christian_packet_count"
            ],
            "collision_divine_name_packet_count": collision_packets[
                "divine_name_policy_packet_count"
            ],
            "collision_poetic_packet_count": collision_packets["poetic_rhetorical_packet_count"],
            "collision_top_ref": collision_packets["top_ref"],
            "collision_top_score": collision_packets["top_integration_pressure_score"],
            "collision_benchmark_task_count": collision_benchmark["task_count"],
            "collision_benchmark_unit_count": collision_benchmark["selected_collision_unit_count"],
            "collision_benchmark_planned_runs": collision_benchmark["planned_model_runs"],
            "collision_benchmark_pending_decisions": collision_benchmark[
                "source_pending_decision_count"
            ],
            "collision_benchmark_jewish_christian_tasks": collision_benchmark[
                "jewish_christian_task_count"
            ],
            "collision_benchmark_divine_name_tasks": collision_benchmark["divine_name_task_count"],
            "collision_benchmark_poetic_tasks": collision_benchmark["poetic_rhetorical_task_count"],
            "collision_benchmark_top_ref": collision_benchmark["top_selected_ref"],
            "collision_benchmark_top_score": collision_benchmark[
                "top_selected_integration_pressure_score"
            ],
            "collision_benchmark_cross_exam_packets": collision_benchmark_cross_exam[
                "packet_count"
            ],
            "collision_benchmark_cross_exam_rows": collision_benchmark_cross_exam[
                "execution_row_count"
            ],
            "collision_benchmark_dry_run_valid": collision_benchmark_dry_run[
                "schema_valid_result_count"
            ],
            "collision_benchmark_dry_run_missing": collision_benchmark_dry_run[
                "missing_expected_result_count"
            ],
            "collision_benchmark_review_human_rows": collision_benchmark_review[
                "projected_human_review_rows"
            ],
            "collision_benchmark_review_model_rows": collision_benchmark_review[
                "projected_model_cross_exam_rows"
            ],
            "collision_real_smoke_attempt_count": collision_real_smoke["attempt_count"],
            "collision_real_smoke_model_count": collision_real_smoke["model_count"],
            "collision_real_smoke_task_count": collision_real_smoke["task_count"],
            "collision_real_smoke_schema_valid_attempt_count": collision_real_smoke[
                "schema_valid_attempt_count"
            ],
            "collision_real_smoke_schema_valid_attempt_pct": collision_real_smoke[
                "schema_valid_attempt_pct"
            ],
            "collision_real_smoke_clean_attempt_count": collision_real_smoke[
                "clean_schema_valid_attempt_count"
            ],
            "collision_real_smoke_clean_attempt_pct": collision_real_smoke[
                "clean_schema_valid_attempt_pct"
            ],
            "collision_real_smoke_source_anchor_issue_count": collision_real_smoke[
                "source_anchor_issue_count"
            ],
            "collision_real_smoke_reception_leak_term_count": collision_real_smoke[
                "reception_leak_term_count"
            ],
            "collision_real_smoke_missing_model_task_count": collision_real_smoke[
                "missing_model_task_count_after_smoke"
            ],
            "collision_real_smoke_clean_best_model": collision_real_smoke[
                "clean_best_model_profile"
            ],
            "collision_real_smoke_fastest_valid_model": collision_real_smoke[
                "fastest_valid_model_profile"
            ],
            "contextual_real_model_attempt_count": contextual_real_model_evidence["attempt_count"],
            "contextual_real_model_lane_count": contextual_real_model_evidence["lane_count"],
            "contextual_real_model_planned_count": contextual_real_model_evidence[
                "planned_model_task_count"
            ],
            "contextual_real_model_valid_count": contextual_real_model_evidence[
                "valid_model_task_count"
            ],
            "contextual_real_model_coverage_pct": contextual_real_model_evidence[
                "valid_model_task_coverage_pct"
            ],
            "contextual_real_model_schema_valid_count": contextual_real_model_evidence[
                "schema_valid_attempt_count"
            ],
            "contextual_real_model_clean_count": contextual_real_model_evidence[
                "clean_source_anchored_count"
            ],
            "contextual_real_model_clean_pct": contextual_real_model_evidence[
                "clean_source_anchored_pct"
            ],
            "contextual_real_model_anchor_issue_count": contextual_real_model_evidence[
                "source_anchor_issue_count"
            ],
            "contextual_real_model_missing_count": contextual_real_model_evidence[
                "missing_model_task_count_after_smoke"
            ],
            "contextual_real_model_best_clean_model": contextual_real_model_evidence[
                "best_clean_model_profile"
            ],
            "whole_tanakh_lemma_index_available": lexeme["whole_tanakh_lemma_index_available"],
            "canonical_context_unit_count": context_network["unit_count"],
            "canonical_context_content_token_pct": context_network[
                "content_token_outside_context_pct"
            ],
            "canonical_context_three_division_unit_pct": context_network[
                "units_with_three_division_evidence_pct"
            ],
            "canonical_context_review_queue_units": context_network["review_queue_unit_count"],
            "canonical_context_weak_network_units": context_network["weak_network_unit_count"],
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
            "witness_record_count": witness["witness_record_count"],
            "witness_lxx_coverage_pct": witness["lxx_coverage_pct"],
            "witness_english_coverage_pct": witness["english_witness_coverage_pct"],
            "witness_generation_block_count": witness["witness_source_generation_block_count"],
            "witness_reception_sensitive_units": witness["atlas_reception_sensitive_units"],
            "witness_integrated_reception_units": witness["integrated_reception_sensitive_units"],
            "witness_divergence_complete_english_units": witness_divergence[
                "complete_english_witness_unit_count"
            ],
            "witness_divergence_complete_english_pct": witness_divergence[
                "complete_english_witness_unit_pct"
            ],
            "witness_divergence_mean_pct": witness_divergence[
                "mean_english_witness_divergence_pct"
            ],
            "witness_divergence_p90_pct": witness_divergence["p90_english_witness_divergence_pct"],
            "witness_divergence_high_unit_count": witness_divergence["high_divergence_unit_count"],
            "witness_divergence_divine_name_disagreement_count": witness_divergence[
                "divine_name_disagreement_unit_count"
            ],
            "witness_divergence_top_ref": witness_divergence["top_priority_ref"],
            "witness_divergence_top_score": witness_divergence["top_priority_score"],
            "divine_name_policy_unit_count": divine_name["divine_title_unit_count"],
            "divine_name_policy_unit_pct": divine_name["divine_title_unit_pct"],
            "divine_name_policy_token_count": divine_name["divine_title_token_count"],
            "divine_name_policy_yhwh_token_count": divine_name["yhwh_token_count"],
            "divine_name_policy_elohim_token_count": divine_name["elohim_token_count"],
            "divine_name_policy_adonai_token_count": divine_name["adonai_token_count"],
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
            "corpus_reception_signal_critical_pressure_unit_count": (
                corpus_reception_signal["critical_pressure_unit_count"]
            ),
            "corpus_reception_signal_known_divergence_unit_count": (
                corpus_reception_signal["known_reception_divergence_unit_count"]
            ),
            "corpus_reception_signal_known_split_unit_count": (
                corpus_reception_signal["known_jewish_christian_separation_unit_count"]
            ),
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
            "reception_boundary_reception_units": reception_boundary[
                "reception_sensitive_unit_count"
            ],
            "reception_boundary_both_traditions_units": reception_boundary[
                "both_jewish_christian_frame_unit_count"
            ],
            "reception_boundary_high_risk_units": reception_boundary[
                "high_boundary_risk_unit_count"
            ],
            "reception_boundary_avg_risk_score": reception_boundary["avg_boundary_risk_score"],
            "reception_boundary_complete_witness_pct": reception_boundary[
                "complete_witness_set_pct"
            ],
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
            "reception_divergence_textual_witness_unit_count": reception_divergence[
                "textual_witness_pressure_unit_count"
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
            "reception_source_packet_blocked_gate_count": reception_source_packets[
                "blocked_gate_count"
            ],
            "interpretive_control_unit_count": interpretive_control["unit_count"],
            "interpretive_control_split_units": interpretive_control[
                "jewish_christian_separation_unit_count"
            ],
            "interpretive_control_reception_sensitive_units": interpretive_control[
                "reception_sensitive_unit_count"
            ],
            "interpretive_control_ancient_culture_units": interpretive_control[
                "ancient_culture_pressure_unit_count"
            ],
            "interpretive_control_textual_witness_units": interpretive_control[
                "textual_witness_pressure_unit_count"
            ],
            "interpretive_control_theology_units": interpretive_control[
                "theology_pressure_unit_count"
            ],
            "interpretive_control_forbidden_text_units": interpretive_control[
                "translation_text_forbidden_reception_claim_units"
            ],
            "interpretive_control_packet_count": interpretive_control["packet_count"],
            "interpretive_control_source_approval_count": interpretive_control[
                "source_approval_count"
            ],
            "interpretive_control_completed_packet_reviews": interpretive_control[
                "completed_packet_review_count"
            ],
            "interpretive_control_top_ref": interpretive_control["top_control_ref"],
            "interpretive_control_top_score": interpretive_control["top_control_score"],
            "interpretive_adjudication_unit_count": interpretive_adjudication["unit_count"],
            "interpretive_adjudication_highest_priority_units": interpretive_adjudication[
                "highest_priority_unit_count"
            ],
            "interpretive_adjudication_jewish_christian_units": interpretive_adjudication[
                "jewish_christian_separation_unit_count"
            ],
            "interpretive_adjudication_layer_blocker_units": interpretive_adjudication[
                "units_with_layer_blockers"
            ],
            "interpretive_adjudication_failed_gate_count": interpretive_adjudication[
                "failed_gate_count"
            ],
            "interpretive_adjudication_failed_gates": interpretive_adjudication["failed_gates"],
            "interpretive_adjudication_top_unit": interpretive_adjudication[
                "top_adjudication_unit"
            ],
            "interpretive_adjudication_top_ref": interpretive_adjudication["top_adjudication_ref"],
            "interpretive_adjudication_top_score": interpretive_adjudication[
                "top_adjudication_score"
            ],
            "scholarly_casebook_case_count": scholarly_casebook["case_count"],
            "scholarly_casebook_top_ref": scholarly_casebook["top_case_ref"],
            "scholarly_casebook_total_token_count": scholarly_casebook["total_token_count"],
            "scholarly_casebook_reception_case_count": scholarly_casebook["reception_case_count"],
            "scholarly_casebook_textual_witness_case_count": scholarly_casebook[
                "textual_witness_case_count"
            ],
            "scholarly_casebook_layer_blocker_case_count": scholarly_casebook[
                "layer_blocker_case_count"
            ],
            "scholarly_casebook_schema_valid_case_count": scholarly_casebook[
                "cases_with_schema_valid_model_output"
            ],
            "source_maturity_source_count": source_maturity["source_count"],
            "source_maturity_version_pinned_source_count": source_maturity[
                "version_pinned_source_count"
            ],
            "source_maturity_generation_allowed_source_count": source_maturity[
                "generation_allowed_source_count"
            ],
            "source_maturity_strong_evidence_lane_count": source_maturity[
                "strong_evidence_lane_count"
            ],
            "source_maturity_blocked_authority_lane_count": source_maturity[
                "blocked_authority_lane_count"
            ],
            "source_maturity_mean_evidence_score_pct": source_maturity["mean_evidence_score_pct"],
            "source_maturity_mean_authority_score_pct": source_maturity["mean_authority_score_pct"],
            "source_maturity_blocked_gate_count": source_maturity["blocked_gate_count"],
            "source_maturity_hard_gap_count": source_maturity["hard_gap_count"],
            "contextual_source_packet_unit_count": contextual_source_packets["unit_count"],
            "contextual_source_packet_family_count": contextual_source_packets[
                "source_family_count"
            ],
            "contextual_source_packet_assignment_count": contextual_source_packets[
                "family_assignment_count"
            ],
            "contextual_source_packet_avg_families": contextual_source_packets[
                "avg_packet_families_per_unit"
            ],
            "contextual_source_packet_critical_units": contextual_source_packets[
                "critical_packet_unit_count"
            ],
            "contextual_source_packet_reception_units": contextual_source_packets[
                "reception_packet_unit_count"
            ],
            "contextual_source_packet_jewish_christian_units": contextual_source_packets[
                "jewish_christian_packet_unit_count"
            ],
            "contextual_source_packet_textual_units": contextual_source_packets[
                "textual_witness_packet_unit_count"
            ],
            "contextual_source_packet_culture_units": contextual_source_packets[
                "ancient_culture_packet_unit_count"
            ],
            "contextual_source_packet_blocked_families": contextual_source_packets[
                "blocked_or_routing_source_family_count"
            ],
            "contextual_source_packet_blocked_gates": contextual_source_packets[
                "blocked_gate_count"
            ],
            "contextual_source_packet_top_ref": contextual_source_packets["top_packet_ref"],
            "contextual_source_packet_top_score": contextual_source_packets[
                "top_packet_priority_score"
            ],
            "source_acquisition_candidate_count": source_acquisition["candidate_count"],
            "source_acquisition_machine_readable_count": source_acquisition[
                "machine_readable_candidate_count"
            ],
            "source_acquisition_low_license_risk_count": source_acquisition[
                "low_license_risk_candidate_count"
            ],
            "source_acquisition_high_license_risk_count": source_acquisition[
                "high_license_risk_candidate_count"
            ],
            "source_acquisition_per_text_license_count": source_acquisition[
                "per_text_license_candidate_count"
            ],
            "source_acquisition_critical_count": source_acquisition["critical_candidate_count"],
            "source_acquisition_blocked_gates": source_acquisition["blocked_gate_count"],
            "source_acquisition_top_candidate": source_acquisition["top_candidate_label"],
            "source_acquisition_top_score": source_acquisition["top_candidate_priority_score"],
            "bibliography_source_count": doctoral_bibliography["bibliography_source_count"],
            "bibliography_local_manifest_count": doctoral_bibliography[
                "local_manifest_source_count"
            ],
            "bibliography_candidate_count": doctoral_bibliography["candidate_source_count"],
            "bibliography_machine_readable_candidate_count": doctoral_bibliography[
                "machine_readable_candidate_count"
            ],
            "bibliography_low_license_risk_candidate_count": doctoral_bibliography[
                "low_license_risk_candidate_count"
            ],
            "bibliography_blocked_authority_lane_count": doctoral_bibliography[
                "blocked_authority_lane_count"
            ],
            "bibliography_unsigned_or_blocked_lane_count": doctoral_bibliography[
                "unsigned_or_blocked_lane_count"
            ],
            "bibliography_gap_count": doctoral_bibliography["gap_count"],
            "bibliography_critical_gap_count": doctoral_bibliography["critical_gap_count"],
            "source_verification_source_count": doctoral_source_verification["source_count"],
            "source_verification_url_source_count": doctoral_source_verification[
                "url_source_count"
            ],
            "source_verification_reachable_url_count": doctoral_source_verification[
                "reachable_url_count"
            ],
            "source_verification_reachable_url_pct": doctoral_source_verification[
                "reachable_url_pct"
            ],
            "source_verification_gap_count": doctoral_source_verification["gap_count"],
            "source_verification_license_term_detected_count": doctoral_source_verification[
                "license_term_detected_count"
            ],
            "source_verification_source_approval_count": doctoral_source_verification[
                "source_approval_count"
            ],
            "source_authority_ladder_unit_count": source_authority_ladder["unit_count"],
            "source_authority_ladder_critical_gap_count": source_authority_ladder[
                "critical_gap_unit_count"
            ],
            "source_authority_ladder_mean_readiness_pct": source_authority_ladder[
                "mean_source_authority_readiness_pct"
            ],
            "source_authority_ladder_family_count": source_authority_ladder["source_family_count"],
            "source_authority_ladder_family_without_candidate_count": (
                source_authority_ladder["family_without_candidate_count"]
            ),
            "source_authority_ladder_candidate_count": source_authority_ladder[
                "candidate_source_count"
            ],
            "source_authority_ladder_candidate_reachable_count": source_authority_ladder[
                "candidate_reachable_count"
            ],
            "source_authority_ladder_source_approval_count": source_authority_ladder[
                "source_approval_count"
            ],
            "source_authority_ladder_total_review_rows": source_authority_ladder[
                "total_review_row_count"
            ],
            "source_authority_ladder_completed_review_rows": source_authority_ladder[
                "completed_review_row_count"
            ],
            "source_authority_ladder_top_ref": source_authority_ladder["top_gap_ref"],
            "source_authority_ladder_top_score": source_authority_ladder["top_gap_score"],
            "unit_heatmap_unit_count": doctoral_unit_heatmap["unit_count"],
            "unit_heatmap_mean_score_pct": doctoral_unit_heatmap["mean_unit_authority_score_pct"],
            "unit_heatmap_blocked_unit_count": doctoral_unit_heatmap["blocked_unit_count"],
            "unit_heatmap_blocked_unit_pct": doctoral_unit_heatmap["blocked_unit_pct"],
            "unit_heatmap_required_lane_rows": doctoral_unit_heatmap["required_lane_row_count"],
            "unit_heatmap_top_gap_ref": doctoral_unit_heatmap["top_gap_ref"],
            "unit_heatmap_top_gap_score_pct": doctoral_unit_heatmap["top_gap_score_pct"],
            "priority_dossier_atlas_unit_count": doctoral_priority_dossier_atlas["unit_count"],
            "priority_dossier_atlas_critical_unit_count": doctoral_priority_dossier_atlas[
                "critical_unit_count"
            ],
            "priority_dossier_atlas_highest_unit_count": doctoral_priority_dossier_atlas[
                "highest_unit_count"
            ],
            "priority_dossier_atlas_jewish_christian_unit_count": (
                doctoral_priority_dossier_atlas["jewish_christian_separation_unit_count"]
            ),
            "priority_dossier_atlas_textual_witness_unit_count": (
                doctoral_priority_dossier_atlas["textual_witness_pressure_unit_count"]
            ),
            "priority_dossier_atlas_mean_authority_score_pct": (
                doctoral_priority_dossier_atlas["mean_authority_score_pct"]
            ),
            "priority_dossier_atlas_top_ref": doctoral_priority_dossier_atlas["top_priority_ref"],
            "priority_dossier_atlas_top_score": doctoral_priority_dossier_atlas[
                "top_priority_score"
            ],
            "defense_exhibit_unit_count": doctoral_defense_exhibit["exhibit_unit_count"],
            "defense_exhibit_critical_unit_count": doctoral_defense_exhibit[
                "critical_exhibit_unit_count"
            ],
            "defense_exhibit_mean_score": doctoral_defense_exhibit["mean_defense_exhibit_score"],
            "defense_exhibit_mean_authority_pct": doctoral_defense_exhibit[
                "mean_unit_authority_score_pct"
            ],
            "defense_exhibit_source_unapproved_count": doctoral_defense_exhibit[
                "source_unapproved_unit_count"
            ],
            "defense_exhibit_unsigned_review_count": doctoral_defense_exhibit[
                "unsigned_review_unit_count"
            ],
            "defense_exhibit_jewish_christian_count": doctoral_defense_exhibit[
                "jewish_christian_separation_unit_count"
            ],
            "defense_exhibit_clean_model_count": doctoral_defense_exhibit[
                "clean_model_attempt_unit_count"
            ],
            "defense_exhibit_top_ref": doctoral_defense_exhibit["top_exhibit_ref"],
            "defense_exhibit_top_score": doctoral_defense_exhibit["top_exhibit_score"],
            "hebrew_token_defense_unit_count": hebrew_token_defense["unit_count"],
            "hebrew_token_defense_token_count": hebrew_token_defense["token_count"],
            "hebrew_token_defense_critical_token_count": hebrew_token_defense[
                "critical_token_count"
            ],
            "hebrew_token_defense_critical_threshold": hebrew_token_defense[
                "critical_token_score_threshold"
            ],
            "hebrew_token_defense_anchor_token_count": hebrew_token_defense["anchor_token_count"],
            "hebrew_token_defense_high_anchor_token_count": hebrew_token_defense[
                "high_anchor_token_count"
            ],
            "hebrew_token_defense_cultural_domain_token_count": hebrew_token_defense[
                "cultural_domain_token_count"
            ],
            "hebrew_token_defense_divine_name_token_count": hebrew_token_defense[
                "divine_name_token_count"
            ],
            "hebrew_token_defense_missing_semantic_role_token_count": hebrew_token_defense[
                "missing_semantic_role_token_count"
            ],
            "hebrew_token_defense_missing_referent_token_count": hebrew_token_defense[
                "missing_referent_token_count"
            ],
            "hebrew_token_defense_source_approved_token_count": hebrew_token_defense[
                "source_approved_token_count"
            ],
            "hebrew_token_defense_review_completed_token_count": hebrew_token_defense[
                "review_completed_token_count"
            ],
            "hebrew_token_defense_top_token_ref": hebrew_token_defense["top_token_ref"],
            "hebrew_token_defense_top_token_surface": hebrew_token_defense["top_token_surface"],
            "hebrew_token_defense_top_token_score": hebrew_token_defense["top_token_score"],
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
            "semantic_referent_suffix_pronoun_count": semantic_referent[
                "suffix_pronoun_token_count"
            ],
            "semantic_referent_anchor_token_count": semantic_referent["anchor_token_count"],
            "semantic_referent_cultural_domain_token_count": semantic_referent[
                "cultural_domain_token_count"
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
            "review_signoff_workbook_total_rows": review_signoff_workbook["total_review_row_count"],
            "review_signoff_workbook_packet_rows": review_signoff_workbook[
                "packet_review_row_count"
            ],
            "review_signoff_workbook_source_rows": review_signoff_workbook[
                "source_acquisition_review_row_count"
            ],
            "review_signoff_workbook_completed_rows": review_signoff_workbook[
                "completed_review_row_count"
            ],
            "review_signoff_workbook_completion_pct": review_signoff_workbook[
                "review_completion_pct"
            ],
            "review_signoff_workbook_role_count": review_signoff_workbook["reviewer_role_count"],
            "review_signoff_workbook_blocked_gates": review_signoff_workbook["blocked_gate_count"],
            "doctoral_synthesis_score_pct": doctoral_synthesis["doctoral_synthesis_score_pct"],
            "doctoral_synthesis_requirement_count": doctoral_synthesis["requirement_count"],
            "doctoral_synthesis_blocked_requirement_count": doctoral_synthesis[
                "blocked_requirement_count"
            ],
            "doctoral_synthesis_blocker_count": doctoral_synthesis["blocker_count"],
            "doctoral_synthesis_critical_blocker_count": doctoral_synthesis[
                "critical_blocker_count"
            ],
            "doctoral_synthesis_source_boundary_count": doctoral_synthesis["source_boundary_count"],
            "doctoral_synthesis_recommended_local_base": doctoral_synthesis[
                "recommended_local_base"
            ],
            "authority_path_phase_count": authority_critical_path["phase_count"],
            "authority_path_blocked_phase_count": authority_critical_path["blocked_phase_count"],
            "authority_path_blocked_gate_count": authority_critical_path["blocked_gate_row_count"],
            "authority_path_review_rows": authority_critical_path["review_row_count"],
            "authority_path_completed_review_rows": authority_critical_path[
                "completed_review_row_count"
            ],
            "authority_path_projected_model_review_rows": authority_critical_path[
                "projected_model_human_review_rows"
            ],
            "authority_path_top_reviewer_role": authority_critical_path["top_reviewer_role"],
            "authority_path_top_reviewer_role_rows": authority_critical_path[
                "top_reviewer_role_row_count"
            ],
            "authority_path_top_gap_ref": authority_critical_path["top_gap_ref"],
            "authority_path_source_approval_count": authority_critical_path[
                "source_approval_count"
            ],
            "benchmark_task_count": suite["task_count"],
            "planned_model_runs": suite["planned_model_runs"],
            "cross_exam_packet_count": cross_exam["packet_count"],
            "cross_exam_execution_rows": cross_exam["execution_row_count"],
            "runtime_gpu_count": runtime["gpu_count"],
            "runtime_max_vram_gb": runtime["max_vram_gb"],
            "runtime_gate_pass_count": runtime["readiness_gate_pass_count"],
            "runtime_gate_count": runtime["readiness_gate_count"],
            "asset_count": assets["asset_count"],
            "asset_recommended_local_count": assets["recommended_models_with_local_assets"],
            "asset_recommended_model_count": assets["recommended_model_count"],
            "asset_ready_profile_count": assets["ready_profile_count"],
            "asset_windows_ollama_reachable": assets["windows_ollama_reachable"],
            "asset_wsl_ollama_reachable": assets["wsl_ollama_reachable"],
            "selection_candidate_count": local_selection["candidate_count"],
            "selection_ready_local_candidate_count": local_selection["ready_local_candidate_count"],
            "selection_best_runnable_candidate": local_selection["best_runnable_candidate"],
            "selection_best_public_hebrew_specialist": local_selection[
                "best_public_hebrew_specialist"
            ],
            "selection_gemma4_26b_schema_valid_pct": local_selection["gemma4_26b_schema_valid_pct"],
            "selection_gemma4_26b_baseline_schema_valid_pct": local_selection[
                "gemma4_26b_baseline_schema_valid_pct"
            ],
            "selection_gemma4_26b_repair_schema_valid_pct": local_selection[
                "gemma4_26b_repair_schema_valid_pct"
            ],
            "selection_gemma4_26b_repair_source_anchor_issues": local_selection[
                "gemma4_26b_repair_source_anchor_issue_count"
            ],
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
            "local_bakeoff_contextual_attempt_count": local_bakeoff["contextual_attempt_count"],
            "local_bakeoff_contextual_coverage_pct": local_bakeoff[
                "contextual_valid_model_task_coverage_pct"
            ],
            "local_bakeoff_contextual_source_anchor_issues": local_bakeoff[
                "contextual_source_anchor_issue_count"
            ],
            "local_bakeoff_blocked_gate_count": local_bakeoff["blocked_gate_count"],
            "local_bakeoff_gemma4_26b_status": local_bakeoff["gemma4_26b_status"],
            "local_bakeoff_mistral_status": local_bakeoff["mistral_status"],
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
            "gemma_repair_best_attempt": gemma_repair["best_schema_attempt_label"],
            "gemma_repair_best_schema_valid_pct": gemma_repair["best_schema_valid_pct"],
            "gemma_repair_source_anchor_issues": gemma_repair["best_source_anchor_issue_count"],
            "gemma_repair_failed_gates": gemma_repair["failed_gates"],
            "selection_mistral_schema_valid_pct": local_selection["mistral_schema_valid_pct"],
            "selection_status": local_selection["selection_status"],
            "structured_attempt_count": tuning["attempt_count"],
            "structured_schema_valid_count": tuning["schema_valid_attempt_count"],
            "structured_schema_valid_pct": tuning["schema_valid_pct"],
            "smoke_submitted_results": smoke["submitted_result_count"],
            "smoke_schema_valid_results": smoke["schema_valid_result_count"],
            "smoke_schema_valid_pct": smoke["schema_valid_pct"],
            "smoke_valid_alignment_mean": smoke["valid_result_alignment_mean"],
            "smoke_valid_basis_mean": smoke["valid_result_translation_basis_mean"],
            "smoke_invalid_token_refs": smoke["valid_result_invalid_token_refs"],
            "smoke_source_anchor_issues": smoke.get(
                "valid_result_source_anchor_issues",
                smoke.get("source_anchor_issue_count", 0),
            ),
            "submitted_real_results": real_audit["submitted_result_count"],
            "missing_real_results": real_audit["missing_expected_result_count"],
            "projected_human_review_rows": review["projected_human_review_rows"],
            "projected_model_cross_exam_rows": review["projected_model_cross_exam_rows"],
        },
        "evidence": {
            "witness_records": corpus["witness_records"],
            "tanakh_word_elements": tanakh["tanakh_word_elements"],
            "tanakh_distinct_forms": tanakh["tanakh_distinct_forms"],
            "psalms_distinct_forms": tanakh["psalms_distinct_forms"],
            "pct_psalm_forms_shared_outside_psalms": tanakh[
                "pct_psalm_forms_shared_outside_psalms"
            ],
            "lexeme_distinct_strong_keys": lexeme["distinct_strong_keys"],
            "lexeme_distinct_lemmas": lexeme["distinct_lemmas"],
            "lexeme_distinct_normalized_forms": lexeme["distinct_normalized_forms"],
            "lexeme_lemma_form_outside_pct": lexeme["lemma_form_outside_context_token_pct"],
            "lexeme_referent_coverage_pct": lexeme["referent_coverage_pct"],
            "whole_tanakh_morphology_source_boundary": morph_gap["source_boundary_status"],
            "whole_tanakh_morphology_source_version": morph_gap["source_version"],
            "whole_tanakh_morphology_source_rows": data["whole_tanakh_morphology_gap"][
                "source_rows"
            ],
            "whole_tanakh_morphology_top_lexemes": data["whole_tanakh_morphology_gap"][
                "lexeme_pressure_rows"
            ][:15],
            "whole_tanakh_morphology_top_units": data["whole_tanakh_morphology_gap"][
                "benchmark_unit_rows"
            ][:15],
            "translation_claim_control_counts": claim_matrix["claim_control_counts"],
            "translation_claim_required_frame_counts": claim_matrix["required_frame_counts"],
            "translation_claim_basis_status_counts": claim_matrix["basis_status_counts"],
            "translation_claim_top_units": data["translation_claim_evidence_matrix"][
                "unit_claim_rows"
            ][:15],
            "context_integration_lens_rows": data["doctoral_context_integration"]["lens_rows"],
            "context_integration_priority_unit_rows": data["doctoral_context_integration"][
                "priority_unit_rows"
            ],
            "context_integration_psalm_rows": data["doctoral_context_integration"]["psalm_rows"],
            "context_integration_cooccurrence_rows": data["doctoral_context_integration"][
                "cooccurrence_rows"
            ],
            "context_integration_visual_data": data["doctoral_context_integration"]["visual_data"],
            "collision_packet_rows": data["doctoral_collision_packets"]["packet_rows"],
            "collision_decision_rows": data["doctoral_collision_packets"]["decision_rows"],
            "collision_lane_rows": data["doctoral_collision_packets"]["lane_rows"],
            "collision_role_rows": data["doctoral_collision_packets"]["role_rows"],
            "collision_visual_data": data["doctoral_collision_packets"]["visual_data"],
            "collision_benchmark_tasks": data["doctoral_collision_benchmark"]["tasks"],
            "collision_benchmark_visual_data": data["doctoral_collision_benchmark"]["visual_data"],
            "collision_benchmark_cross_exam_packets": data[
                "doctoral_collision_benchmark_cross_exam"
            ]["packets"],
            "collision_benchmark_cross_exam_execution": data[
                "doctoral_collision_benchmark_cross_exam"
            ]["execution_matrix"],
            "collision_benchmark_dry_run_results": data[
                "doctoral_collision_benchmark_dry_run_audit"
            ]["scored_results"],
            "collision_benchmark_review_plan": data["doctoral_collision_benchmark_review"][
                "task_review_plan"
            ],
            "collision_real_smoke_model_rows": data["doctoral_collision_real_smoke"]["model_rows"],
            "collision_real_smoke_attempt_rows": data["doctoral_collision_real_smoke"][
                "attempt_rows"
            ],
            "collision_real_smoke_visual_data": data["doctoral_collision_real_smoke"][
                "visual_data"
            ],
            "contextual_real_model_lane_rows": data["contextual_real_model_evidence_matrix"][
                "lane_rows"
            ],
            "contextual_real_model_model_rows": data["contextual_real_model_evidence_matrix"][
                "model_rows"
            ],
            "contextual_real_model_model_lane_rows": data["contextual_real_model_evidence_matrix"][
                "model_lane_rows"
            ],
            "contextual_real_model_attempt_rows": data["contextual_real_model_evidence_matrix"][
                "attempt_rows"
            ],
            "contextual_real_model_visual_data": data["contextual_real_model_evidence_matrix"][
                "visual_data"
            ],
            "canonical_context_source_version": context_network["source_version"],
            "canonical_context_domain_network": data["canonical_context_network"][
                "domain_network_rows"
            ],
            "canonical_context_division_evidence": data["canonical_context_network"][
                "division_evidence_rows"
            ],
            "canonical_context_book_evidence": data["canonical_context_network"][
                "book_evidence_rows"
            ][:15],
            "canonical_cross_reference_divisions": data["canonical_cross_reference"][
                "division_rows"
            ],
            "canonical_cross_reference_books": data["canonical_cross_reference"]["book_rows"],
            "canonical_cross_reference_domains": data["canonical_cross_reference"]["domain_rows"],
            "canonical_cross_reference_units": data["canonical_cross_reference"]["unit_rows"],
            "canonical_cross_reference_anchors": data["canonical_cross_reference"]["anchor_rows"],
            "canonical_cross_reference_visual_data": data["canonical_cross_reference"][
                "visual_data"
            ],
            "canonical_intertext_benchmark_tasks": data["canonical_intertext_benchmark"]["tasks"],
            "canonical_intertext_benchmark_domain_counts": canonical_intertext_benchmark[
                "domain_counts"
            ],
            "canonical_intertext_benchmark_book_counts": canonical_intertext_benchmark[
                "book_presence_counts"
            ],
            "canonical_intertext_benchmark_cross_exam_packets": data[
                "canonical_intertext_benchmark_cross_exam"
            ]["packets"],
            "canonical_intertext_benchmark_cross_exam_execution": data[
                "canonical_intertext_benchmark_cross_exam"
            ]["execution_matrix"],
            "canonical_intertext_benchmark_cross_exam_domain_counts": (
                canonical_intertext_cross_exam["canonical_domain_packet_counts"]
            ),
            "canonical_intertext_benchmark_cross_exam_book_counts": (
                canonical_intertext_cross_exam["canonical_book_packet_counts"]
            ),
            "canonical_intertext_benchmark_dry_run_results": data[
                "canonical_intertext_benchmark_dry_run_audit"
            ]["scored_results"],
            "canonical_intertext_benchmark_review_plan": data[
                "canonical_intertext_benchmark_review"
            ]["task_review_plan"],
            "canonical_intertext_real_smoke_model_rows": data["canonical_intertext_real_smoke"][
                "model_rows"
            ],
            "canonical_intertext_real_smoke_attempt_rows": data["canonical_intertext_real_smoke"][
                "attempt_rows"
            ],
            "witness_source_counts": data["witness_reception_readiness"]["source_counts"],
            "witness_language_counts": data["witness_reception_readiness"]["language_counts"],
            "witness_generation_block_sources": witness[
                "witness_sources_not_allowed_for_generation"
            ],
            "reception_frame_counts": data["witness_reception_readiness"]["required_frame_counts"],
            "witness_divergence_pairs": data["witness_divergence"]["source_pair_rows"],
            "witness_divergence_markers": data["witness_divergence"]["marker_rows"],
            "witness_divergence_priority_units": data["witness_divergence"]["priority_rows"],
            "witness_divergence_psalms": data["witness_divergence"]["psalm_rows"],
            "witness_divergence_visual_data": data["witness_divergence"]["visual_data"],
            "divine_name_policy_units": data["divine_name_policy"]["unit_rows"],
            "divine_name_policy_psalms": data["divine_name_policy"]["psalm_rows"],
            "divine_name_policy_markers": data["divine_name_policy"]["marker_rows"],
            "divine_name_policy_category_tokens": data["divine_name_policy"]["category_token_rows"],
            "divine_name_policy_visual_data": data["divine_name_policy"]["visual_data"],
            "superscription_context_units": data["superscription_context"]["unit_rows"],
            "superscription_context_psalms": data["superscription_context"]["psalm_rows"],
            "superscription_context_markers": data["superscription_context"]["marker_rows"],
            "superscription_context_category_tokens": data["superscription_context"][
                "category_token_rows"
            ],
            "superscription_context_visual_data": data["superscription_context"]["visual_data"],
            "cultural_historical_domain_rows": data["cultural_historical_atlas"]["domain_rows"],
            "cultural_historical_units": data["cultural_historical_atlas"]["unit_rows"],
            "cultural_historical_psalms": data["cultural_historical_atlas"]["psalm_rows"],
            "cultural_historical_markers": data["cultural_historical_atlas"]["marker_rows"],
            "cultural_historical_cooccurrence": data["cultural_historical_atlas"][
                "cooccurrence_rows"
            ],
            "cultural_historical_visual_data": data["cultural_historical_atlas"]["visual_data"],
            "poetic_rhetorical_units": data["poetic_rhetorical_atlas"]["unit_rows"],
            "poetic_rhetorical_psalms": data["poetic_rhetorical_atlas"]["psalm_rows"],
            "poetic_rhetorical_features": data["poetic_rhetorical_atlas"]["feature_rows"],
            "poetic_rhetorical_visual_data": data["poetic_rhetorical_atlas"]["visual_data"],
            "corpus_reception_signal_units": data["corpus_reception_signal"]["unit_rows"],
            "corpus_reception_signal_psalms": data["corpus_reception_signal"]["psalm_rows"],
            "corpus_reception_signal_signals": data["corpus_reception_signal"]["signal_rows"],
            "corpus_reception_signal_cooccurrence": data["corpus_reception_signal"][
                "cooccurrence_rows"
            ],
            "corpus_reception_signal_expansion": data["corpus_reception_signal"][
                "expansion_queue_rows"
            ],
            "corpus_reception_signal_visual_data": data["corpus_reception_signal"]["visual_data"],
            "reception_signal_benchmark_tasks": data["reception_signal_benchmark"]["tasks"],
            "reception_signal_benchmark_cross_exam_packets": data[
                "reception_signal_benchmark_cross_exam"
            ]["packets"],
            "reception_signal_benchmark_cross_exam_execution": data[
                "reception_signal_benchmark_cross_exam"
            ]["execution_matrix"],
            "reception_signal_benchmark_dry_run_results": data[
                "reception_signal_benchmark_dry_run_audit"
            ]["scored_results"],
            "reception_signal_benchmark_review_plan": data["reception_signal_benchmark_review"][
                "task_review_plan"
            ],
            "reception_signal_real_smoke_model_rows": data["reception_signal_real_smoke"][
                "model_rows"
            ],
            "reception_signal_real_smoke_attempt_rows": data["reception_signal_real_smoke"][
                "attempt_rows"
            ],
            "reception_boundary_frame_summary": data["reception_interpretation_boundary"][
                "frame_summary_rows"
            ],
            "reception_boundary_domain_rows": data["reception_interpretation_boundary"][
                "domain_boundary_rows"
            ],
            "reception_boundary_top_units": data["reception_interpretation_boundary"][
                "unit_boundary_rows"
            ][:12],
            "reception_divergence_units": data["reception_divergence"]["unit_rows"],
            "reception_divergence_domains": data["reception_divergence"]["domain_rows"],
            "reception_divergence_frames": data["reception_divergence"]["frame_rows"],
            "reception_divergence_signals": data["reception_divergence"]["signal_rows"],
            "reception_divergence_psalms": data["reception_divergence"]["psalm_rows"],
            "reception_divergence_boundaries": data["reception_divergence"]["boundary_rows"],
            "reception_divergence_packet_families": data["reception_divergence"][
                "packet_family_rows"
            ],
            "reception_divergence_visual_data": data["reception_divergence"]["visual_data"],
            "reception_source_packet_units": data["reception_source_packets"]["unit_rows"],
            "reception_source_packet_rows": data["reception_source_packets"]["packet_rows"],
            "reception_source_packet_sources": data["reception_source_packets"]["source_rows"],
            "reception_source_packet_gates": data["reception_source_packets"]["gate_rows"],
            "reception_source_packet_visual_data": data["reception_source_packets"]["visual_data"],
            "interpretive_control_unit_rows": data["interpretive_tradition_control"]["unit_rows"],
            "interpretive_control_lane_rows": data["interpretive_tradition_control"]["lane_rows"],
            "interpretive_control_packet_rows": data["interpretive_tradition_control"][
                "packet_rows"
            ],
            "interpretive_control_control_rows": data["interpretive_tradition_control"][
                "control_rows"
            ],
            "interpretive_control_visual_data": data["interpretive_tradition_control"][
                "visual_data"
            ],
            "interpretive_adjudication_gate_rows": data["interpretive_adjudication"]["gate_rows"],
            "interpretive_adjudication_lane_rows": data["interpretive_adjudication"]["lane_rows"],
            "interpretive_adjudication_domain_rows": data["interpretive_adjudication"][
                "domain_rows"
            ],
            "interpretive_adjudication_top_units": data["interpretive_adjudication"]["unit_rows"][
                :15
            ],
            "scholarly_casebook_cases": data["scholarly_casebook"]["cases"],
            "scholarly_casebook_domain_counts": scholarly_casebook["domain_counts"],
            "scholarly_casebook_blocked_lane_counts": scholarly_casebook["blocked_lane_counts"],
            "scholarly_casebook_missing_enrichment_counts": scholarly_casebook[
                "missing_enrichment_counts"
            ],
            "source_maturity_lanes": data["scholarly_source_maturity"]["lane_rows"],
            "source_maturity_sources": data["scholarly_source_maturity"]["source_rows"],
            "source_maturity_gates": data["scholarly_source_maturity"]["gate_rows"],
            "source_maturity_gaps": data["scholarly_source_maturity"]["gap_rows"],
            "contextual_source_packet_units": data["contextual_source_packets"]["unit_rows"],
            "contextual_source_packet_families": data["contextual_source_packets"][
                "source_family_rows"
            ],
            "contextual_source_packet_roles": data["contextual_source_packets"]["review_role_rows"],
            "contextual_source_packet_gates": data["contextual_source_packets"]["gate_rows"],
            "source_acquisition_candidates": data["contextual_source_acquisition"][
                "candidate_rows"
            ],
            "source_acquisition_phases": data["contextual_source_acquisition"]["phase_rows"],
            "source_acquisition_gates": data["contextual_source_acquisition"]["gate_rows"],
            "morphology_acquisition_candidates": data["whole_tanakh_morphology_acquisition"][
                "candidate_rows"
            ],
            "morphology_acquisition_gates": data["whole_tanakh_morphology_acquisition"][
                "gate_rows"
            ],
            "morphology_acquisition_phases": data["whole_tanakh_morphology_acquisition"][
                "phase_rows"
            ],
            "morphology_acquisition_local_inventory": data["whole_tanakh_morphology_acquisition"][
                "local_inventory_rows"
            ],
            "morphology_acquisition_visual_data": data["whole_tanakh_morphology_acquisition"][
                "visual_data"
            ],
            "oshb_alignment_pilot_division_rows": data["oshb_whole_tanakh_alignment_pilot"][
                "division_rows"
            ],
            "oshb_alignment_pilot_book_rows": data["oshb_whole_tanakh_alignment_pilot"][
                "book_rows"
            ],
            "oshb_alignment_pilot_mismatch_rows": data["oshb_whole_tanakh_alignment_pilot"][
                "mismatch_rows"
            ],
            "oshb_alignment_pilot_visual_data": data["oshb_whole_tanakh_alignment_pilot"][
                "visual_data"
            ],
            "oshb_exception_review_gate_rows": data["oshb_alignment_exception_review"]["gate_rows"],
            "oshb_exception_review_division_rows": data["oshb_alignment_exception_review"][
                "division_rows"
            ],
            "oshb_exception_review_book_rows": data["oshb_alignment_exception_review"]["book_rows"],
            "oshb_exception_review_sample_rows": data["oshb_alignment_exception_review"][
                "sample_rows"
            ],
            "oshb_exception_review_visual_data": data["oshb_alignment_exception_review"][
                "visual_data"
            ],
            "oshb_exception_taxonomy_cause_rows": data["oshb_exception_taxonomy"]["cause_rows"],
            "oshb_exception_taxonomy_batch_rows": data["oshb_exception_taxonomy"]["batch_rows"],
            "oshb_exception_taxonomy_review_packet_rows": data["oshb_exception_taxonomy"][
                "review_packet_rows"
            ],
            "oshb_exception_taxonomy_visual_data": data["oshb_exception_taxonomy"]["visual_data"],
            "oshb_mapping_rule_simulation_rule_rows": data["oshb_mapping_rule_simulation"][
                "rule_rows"
            ],
            "oshb_mapping_rule_simulation_packet_rows": data["oshb_mapping_rule_simulation"][
                "packet_rows"
            ],
            "oshb_mapping_rule_simulation_visual_data": data["oshb_mapping_rule_simulation"][
                "visual_data"
            ],
            "morph_unlock_phase_rows": data["whole_tanakh_morphology_unlock_matrix"]["phase_rows"],
            "morph_unlock_unit_rows": data["whole_tanakh_morphology_unlock_matrix"]["unit_rows"],
            "morph_unlock_book_rows": data["whole_tanakh_morphology_unlock_matrix"]["book_rows"],
            "morph_unlock_cause_rows": data["whole_tanakh_morphology_unlock_matrix"]["cause_rows"],
            "morph_unlock_rule_rows": data["whole_tanakh_morphology_unlock_matrix"]["rule_rows"],
            "morph_unlock_visual_data": data["whole_tanakh_morphology_unlock_matrix"][
                "visual_data"
            ],
            "critical_unit_morphology_unlock_unit_rows": data["critical_unit_morphology_unlock"][
                "unit_rows"
            ],
            "critical_unit_morphology_unlock_book_rows": data["critical_unit_morphology_unlock"][
                "book_rows"
            ],
            "critical_unit_morphology_unlock_phase_rows": data["critical_unit_morphology_unlock"][
                "phase_rows"
            ],
            "critical_unit_morphology_unlock_gate_rows": data["critical_unit_morphology_unlock"][
                "gate_rows"
            ],
            "critical_unit_morphology_unlock_visual_data": data["critical_unit_morphology_unlock"][
                "visual_data"
            ],
            "doctoral_bibliography_sources": data["doctoral_bibliography"]["bibliography_rows"],
            "doctoral_bibliography_lanes": data["doctoral_bibliography"]["lane_rows"],
            "doctoral_bibliography_families": data["doctoral_bibliography"]["source_family_rows"],
            "doctoral_bibliography_gaps": data["doctoral_bibliography"]["gap_rows"],
            "doctoral_bibliography_methods": data["doctoral_bibliography"]["method_rows"],
            "doctoral_bibliography_visual_data": data["doctoral_bibliography"]["visual_data"],
            "doctoral_source_verification_sources": data["doctoral_source_verification"][
                "source_rows"
            ],
            "doctoral_source_verification_terms": data["doctoral_source_verification"]["term_rows"],
            "doctoral_source_verification_gaps": data["doctoral_source_verification"]["gap_rows"],
            "doctoral_source_verification_visual_data": data["doctoral_source_verification"][
                "visual_data"
            ],
            "source_authority_ladder_unit_rows": data["source_authority_ladder"]["unit_rows"],
            "source_authority_ladder_family_rows": data["source_authority_ladder"]["family_rows"],
            "source_authority_ladder_source_rows": data["source_authority_ladder"]["source_rows"],
            "source_authority_ladder_lane_rows": data["source_authority_ladder"]["lane_rows"],
            "source_authority_ladder_gate_rows": data["source_authority_ladder"]["gate_rows"],
            "source_authority_ladder_visual_data": data["source_authority_ladder"]["visual_data"],
            "doctoral_unit_heatmap_units": data["doctoral_unit_heatmap"]["unit_rows"],
            "doctoral_unit_heatmap_lanes": data["doctoral_unit_heatmap"]["lane_rows"],
            "doctoral_unit_heatmap_lane_summary": data["doctoral_unit_heatmap"][
                "lane_summary_rows"
            ],
            "doctoral_unit_heatmap_queue": data["doctoral_unit_heatmap"]["queue_rows"],
            "doctoral_priority_dossier_units": data["doctoral_priority_dossier_atlas"]["unit_rows"],
            "doctoral_priority_dossier_roles": data["doctoral_priority_dossier_atlas"]["role_rows"],
            "doctoral_priority_dossier_lanes": data["doctoral_priority_dossier_atlas"]["lane_rows"],
            "doctoral_priority_dossier_domains": data["doctoral_priority_dossier_atlas"][
                "domain_rows"
            ],
            "doctoral_priority_dossier_packet_families": data["doctoral_priority_dossier_atlas"][
                "packet_family_rows"
            ],
            "doctoral_priority_dossier_visual_data": data["doctoral_priority_dossier_atlas"][
                "visual_data"
            ],
            "defense_exhibit_unit_rows": data["doctoral_defense_exhibit"]["unit_rows"],
            "defense_exhibit_dimension_rows": data["doctoral_defense_exhibit"]["dimension_rows"],
            "defense_exhibit_role_rows": data["doctoral_defense_exhibit"]["role_rows"],
            "defense_exhibit_blocker_rows": data["doctoral_defense_exhibit"]["blocker_rows"],
            "defense_exhibit_visual_data": data["doctoral_defense_exhibit"]["visual_data"],
            "hebrew_token_defense_token_rows": data["hebrew_token_defense"]["token_rows"],
            "hebrew_token_defense_unit_rows": data["hebrew_token_defense"]["unit_rows"],
            "hebrew_token_defense_control_rows": data["hebrew_token_defense"]["control_rows"],
            "hebrew_token_defense_visual_data": data["hebrew_token_defense"]["visual_data"],
            "claim_traceability_claim_rows": data["translation_claim_traceability"]["claim_rows"],
            "claim_traceability_unit_rows": data["translation_claim_traceability"]["unit_rows"],
            "claim_traceability_family_rows": data["translation_claim_traceability"]["family_rows"],
            "claim_traceability_gate_rows": data["translation_claim_traceability"]["gate_rows"],
            "claim_traceability_visual_data": data["translation_claim_traceability"]["visual_data"],
            "translation_accuracy_dimension_rows": data["translation_accuracy_certification"][
                "dimension_rows"
            ],
            "translation_accuracy_gate_rows": data["translation_accuracy_certification"][
                "gate_rows"
            ],
            "translation_accuracy_unit_rows": data["translation_accuracy_certification"][
                "unit_rows"
            ],
            "translation_accuracy_role_rows": data["translation_accuracy_certification"][
                "role_rows"
            ],
            "translation_accuracy_visual_data": data["translation_accuracy_certification"][
                "visual_data"
            ],
            "critical_unit_decision_unit_rows": data["critical_unit_decision_dossier"]["unit_rows"],
            "critical_unit_decision_lane_rows": data["critical_unit_decision_dossier"]["lane_rows"],
            "critical_unit_decision_claim_rows": data["critical_unit_decision_dossier"][
                "claim_rows"
            ],
            "critical_unit_decision_visual_data": data["critical_unit_decision_dossier"][
                "visual_data"
            ],
            "critical_unit_review_execution_wave_rows": data["critical_unit_review_execution"][
                "wave_rows"
            ],
            "critical_unit_review_execution_role_rows": data["critical_unit_review_execution"][
                "role_rows"
            ],
            "critical_unit_review_execution_unit_role_rows": data["critical_unit_review_execution"][
                "unit_role_rows"
            ],
            "critical_unit_review_execution_lane_rows": data["critical_unit_review_execution"][
                "lane_dependency_rows"
            ],
            "critical_unit_review_execution_gate_rows": data["critical_unit_review_execution"][
                "gate_rows"
            ],
            "critical_unit_review_execution_visual_data": data["critical_unit_review_execution"][
                "visual_data"
            ],
            "critical_unit_model_cross_exam_unit_rows": data["critical_unit_model_cross_exam"][
                "unit_rows"
            ],
            "critical_unit_model_cross_exam_model_rows": data["critical_unit_model_cross_exam"][
                "model_rows"
            ],
            "critical_unit_model_cross_exam_judge_rows": data["critical_unit_model_cross_exam"][
                "judge_rows"
            ],
            "critical_unit_model_cross_exam_task_rows": data["critical_unit_model_cross_exam"][
                "task_rows"
            ],
            "critical_unit_model_cross_exam_gate_rows": data["critical_unit_model_cross_exam"][
                "gate_rows"
            ],
            "critical_unit_model_cross_exam_visual_data": data["critical_unit_model_cross_exam"][
                "visual_data"
            ],
            "semantic_referent_token_rows": data["semantic_referent_roadmap"]["token_rows"],
            "semantic_referent_unit_rows": data["semantic_referent_roadmap"]["unit_rows"],
            "semantic_referent_lane_rows": data["semantic_referent_roadmap"]["lane_rows"],
            "semantic_referent_gap_rows": data["semantic_referent_roadmap"]["gap_rows"],
            "semantic_referent_phase_rows": data["semantic_referent_roadmap"]["phase_rows"],
            "semantic_referent_visual_data": data["semantic_referent_roadmap"]["visual_data"],
            "review_signoff_units": data["contextual_review_signoff"]["unit_rows"],
            "review_signoff_roles": data["contextual_review_signoff"]["review_role_rows"],
            "review_signoff_gates": data["contextual_review_signoff"]["gate_rows"],
            "review_signoff_packet_rows": data["contextual_review_signoff"]["packet_review_rows"],
            "review_signoff_source_rows": data["contextual_review_signoff"][
                "source_acquisition_review_rows"
            ],
            "doctoral_requirement_rows": data["doctoral_synthesis"]["requirement_rows"],
            "doctoral_blocker_rows": data["doctoral_synthesis"]["blocker_rows"],
            "doctoral_source_boundary_rows": data["doctoral_synthesis"]["source_boundary_rows"],
            "doctoral_priority_unit_rows": data["doctoral_synthesis"]["priority_unit_rows"],
            "doctoral_visual_data": data["doctoral_synthesis"]["visual_data"],
            "authority_path_phase_rows": data["authority_critical_path"]["phase_rows"],
            "authority_path_role_rows": data["authority_critical_path"]["review_role_rows"],
            "authority_path_unit_rows": data["authority_critical_path"]["unit_queue_rows"],
            "authority_path_gate_rows": data["authority_critical_path"]["gate_rows"],
            "authority_path_visual_data": data["authority_critical_path"]["visual_data"],
            "seed_unit_count": packets["seed_unit_count"],
            "seed_token_count": packets["seed_token_count"],
            "seed_surface_outside_context_pct": packets["surface_outside_context_pct"],
            "benchmark_expansion_distinct_psalms": expansion["distinct_psalms"],
            "benchmark_expansion_stratum_counts": expansion["stratum_counts"],
            "context_matrix_surface_outside_pct": context_matrix["surface_outside_context_pct"],
            "context_matrix_domain_counts": context_matrix["domain_counts"],
            "atlas_domain_count": atlas["domain_count"],
            "atlas_domain_group_count": atlas["domain_group_count"],
            "atlas_surface_outside_context_pct": atlas["surface_outside_context_pct"],
            "contextual_domain_coverage": data["contextual_benchmark_coverage"][
                "domain_coverage_rows"
            ],
            "contextual_stratum_coverage": data["contextual_benchmark_coverage"][
                "stratum_coverage_rows"
            ],
            "contextual_next_units": data["contextual_benchmark_coverage"]["next_unit_rows"][:10],
            "contextual_gap_layer_counts": contextual_gap["layer_counts"],
            "contextual_gap_domain_counts": contextual_gap["domain_counts"],
            "contextual_gap_tag_counts": contextual_gap["benchmark_tag_counts"],
            "contextual_gap_review_role_counts": contextual_gap_review[
                "required_role_counts_by_task"
            ],
            "priority_dossier_domain_counts": dossiers["domain_counts"],
            "priority_dossier_review_role_counts": dossiers["review_role_counts"],
            "priority_supplement_layer_counts": supplement["layer_counts"],
            "priority_supplement_domain_counts": supplement["domain_counts"],
            "integrated_layer_counts": integrated["layer_counts"],
            "integrated_source_task_counts": integrated["source_task_counts"],
            "integrated_benchmark_tag_counts": integrated["benchmark_tag_counts"],
            "contextual_expanded_layer_counts": contextual_expanded["layer_counts"],
            "contextual_expanded_source_task_counts": contextual_expanded["source_task_counts"],
            "contextual_expanded_benchmark_tag_counts": contextual_expanded["benchmark_tag_counts"],
            "contextual_expanded_review_role_counts": contextual_expanded_review[
                "required_role_counts_by_task"
            ],
            "contextual_expanded_real_expected_results": contextual_expanded_real[
                "expected_result_count"
            ],
            "contextual_expanded_real_schema_valid_count": contextual_expanded_real[
                "schema_valid_result_count"
            ],
            "contextual_expanded_real_source_anchor_issues": contextual_expanded_real.get(
                "source_anchor_issue_count",
                0,
            ),
            "model_evidence_gap_status_counts": model_evidence_gap["status_counts"],
            "model_evidence_gap_model_status_counts": model_evidence_gap["model_status_counts"],
            "model_evidence_gap_top_ref": model_evidence_gap["top_gap_ref"],
            "model_evidence_gap_top_no_real_score": model_evidence_gap[
                "top_no_real_model_evidence_priority_score"
            ],
            "layer_consistency_status_counts": layer_consistency["status_counts"],
            "layer_consistency_flag_counts": layer_consistency["flag_counts"],
            "layer_consistency_mean_literal_minus_gloss_words": layer_consistency[
                "mean_literal_minus_gloss_words"
            ],
            "layer_remediation_retry_flag_counts": layer_remediation["retry_flag_counts"],
            "layer_experiment_gate_rows": data["layer_remediation_experiment"]["gate_rows"],
            "layer_experiment_attempt_rows": data["layer_remediation_experiment"]["attempt_rows"],
            "authority_gate_rows": data["scholarly_authority_readiness"]["gate_rows"],
            "authority_risk_register": data["scholarly_authority_readiness"]["risk_register"],
            "authority_domain_coverage": data["scholarly_authority_readiness"][
                "domain_coverage_rows"
            ],
            "integrated_real_expected_results": integrated_real_audit["expected_result_count"],
            "integrated_result_schema_valid_count": integrated_real_audit[
                "schema_valid_result_count"
            ],
            "integrated_result_source_anchor_issues": integrated_real_audit.get(
                "source_anchor_issue_count",
                0,
            ),
            "integrated_review_role_counts": integrated_review["required_role_counts_by_task"],
            "integrated_review_intensity_counts": integrated_review["task_intensity_counts"],
            "cross_exam_probe_question_count": cross_exam["probe_question_count"],
            "cross_exam_high_priority_packets": cross_exam["high_priority_packets"],
            "runtime_q4_fit_model_count": runtime["q4_fit_model_count"],
            "runtime_q5_fit_model_count": runtime["q5_fit_model_count"],
            "runtime_qlora_possible_model_count": runtime["qlora_possible_model_count"],
            "runtime_model_cache_file_count": runtime["model_cache_file_count"],
            "runtime_model_cache_gb_seen": runtime["model_cache_gb_seen"],
            "asset_text_capable_count": assets["text_or_text_capable_asset_count"],
            "asset_text_gb": assets["text_asset_gb"],
            "asset_total_gb": assets["total_asset_gb"],
            "asset_suggested_profile_count": assets["suggested_profile_count"],
            "local_model_selection_candidates": data["local_model_selection"]["candidate_rows"],
            "local_model_selection_gates": data["local_model_selection"]["gate_rows"],
            "local_model_selection_phases": data["local_model_selection"]["phase_rows"],
            "local_bakeoff_candidate_rows": data["local_model_doctoral_bakeoff"]["candidate_rows"],
            "local_bakeoff_gate_rows": data["local_model_doctoral_bakeoff"]["gate_rows"],
            "local_bakeoff_phase_rows": data["local_model_doctoral_bakeoff"]["phase_rows"],
            "local_bakeoff_visual_data": data["local_model_doctoral_bakeoff"]["visual_data"],
            "model_training_certification_candidate_rows": data["model_training_certification"][
                "candidate_rows"
            ],
            "model_training_certification_gate_rows": data["model_training_certification"][
                "gate_rows"
            ],
            "model_training_certification_phase_rows": data["model_training_certification"][
                "phase_rows"
            ],
            "model_training_certification_source_rows": data["model_training_certification"][
                "public_source_rows"
            ],
            "model_training_certification_visual_data": data["model_training_certification"][
                "visual_data"
            ],
            "gemma_schema_repair_attempt_rows": data["gemma_schema_repair"]["attempt_rows"],
            "gemma_schema_repair_gate_rows": data["gemma_schema_repair"]["gate_rows"],
            "structured_error_category_counts": tuning["error_category_counts"],
            "smoke_valid_alignment_mean": smoke["valid_result_alignment_mean"],
            "smoke_valid_basis_mean": smoke["valid_result_translation_basis_mean"],
            "smoke_invalid_token_refs": smoke["valid_result_invalid_token_refs"],
            "smoke_source_anchor_issues": smoke.get(
                "valid_result_source_anchor_issues",
                smoke.get("source_anchor_issue_count", 0),
            ),
            "dry_run_schema_valid_count": dry_audit["schema_valid_result_count"],
        },
        "pipeline": build_pipeline(data),
        "artifact_inventory": artifact_inventory(),
        "html_reports": HTML_REPORTS,
        "open_gaps": [
            {
                "gap": "Authority-level readiness still has hard blockers.",
                "evidence": (
                    f"Scholarly readiness is "
                    f"{authority['authority_readiness_score_pct']:.2f}% with "
                    f"{authority['hard_blocker_count']} hard blockers: "
                    + ", ".join(authority["hard_blockers"])
                    + "."
                ),
            },
            {
                "gap": "Source maturity is evidence-rich but authority-blocked.",
                "evidence": (
                    f"The source maturity audit has "
                    f"{source_maturity['strong_evidence_lane_count']} strong evidence "
                    f"lanes out of {source_maturity['lane_count']}, but "
                    f"{source_maturity['blocked_authority_lane_count']} lanes are "
                    "authority-blocked. Mean authority maturity is "
                    f"{source_maturity['mean_authority_score_pct']:.2f}% with "
                    f"{source_maturity['blocked_gate_count']} blocked certification "
                    f"gates and {source_maturity['hard_gap_count']} hard gaps."
                ),
            },
            {
                "gap": "Whole-Tanakh morphology acquisition is ranked but not imported.",
                "evidence": (
                    f"{morph_acquisition['morphology_candidate_count']} morphology "
                    "candidates are ranked, with first import "
                    f"{morph_acquisition['recommended_first_import_candidate']}. "
                    f"{morph_acquisition['local_non_psalm_morphology_book_count']} of "
                    f"{morph_acquisition['target_non_psalm_book_count']} non-Psalm books "
                    "have local morphology; "
                    f"{morph_acquisition['blocked_gate_count']} gates are blocked and "
                    f"{morph_acquisition['not_started_gate_count']} gates are not started."
                ),
            },
            {
                "gap": "OSHB alignment pilot is feasible but not authority.",
                "evidence": (
                    f"The OSHB pilot maps {oshb_pilot['mapped_book_count']} books and "
                    f"{oshb_pilot['remote_oshb_word_count']} remote OSHB words to UXLC "
                    f"with {oshb_pilot['mean_sequence_similarity_pct']:.2f}% mean "
                    "normalized verse similarity. "
                    f"{oshb_pilot['mismatch_sample_row_count']} mismatch verses still "
                    "need importer exception review, and source approval remains "
                    f"{oshb_pilot['source_approval_status']}."
                ),
            },
            {
                "gap": "OSHB exception review is generated but incomplete.",
                "evidence": (
                    f"The exception workbook identifies "
                    f"{oshb_exception['mismatch_verse_count']} remaining exception verses: "
                    f"{oshb_exception['token_count_exception_verse_count']} token-count "
                    "exceptions and "
                    f"{oshb_exception['sequence_only_exception_verse_count']} sequence-only "
                    "exceptions. "
                    + (
                        f"All {
                            oshb_exception.get(
                                'review_row_count',
                                oshb_exception['sample_row_count'],
                            )
                        } "
                        "review rows are exported, but reviewer signoff is still absent."
                        if int(oshb_exception["unexported_exception_row_count"]) == 0
                        else (
                            f"{oshb_exception['sample_row_count']} rows are exported, but "
                            f"{oshb_exception['unexported_exception_row_count']} exception rows "
                            "still need full enumeration and reviewer signoff."
                        )
                    )
                ),
            },
            {
                "gap": "OSHB exception taxonomy batches are queued but unsigned.",
                "evidence": (
                    f"The taxonomy reduces {oshb_taxonomy['exception_row_count']} "
                    f"exception rows into {oshb_taxonomy['taxonomy_cause_count']} "
                    f"cause families and {oshb_taxonomy['review_batch_count']} queued "
                    f"review batches. Top cause {oshb_taxonomy['top_cause_family']} "
                    f"covers {oshb_taxonomy['top_cause_row_count']} rows; "
                    f"{oshb_taxonomy['segmentation_marker_pct']:.2f}% of rows carry "
                    "OSHB segmentation markers. No reviewer decision or source approval "
                    "is recorded."
                ),
            },
            {
                "gap": "OSHB mapping-rule simulation is not an approved importer rule.",
                "evidence": (
                    f"The simulation routes "
                    f"{oshb_simulation['candidate_rule_reduction_row_count']} rows "
                    "into candidate rule lanes, or "
                    f"{oshb_simulation['candidate_rule_reduction_pct']:.2f}% of "
                    "the exception queue, and leaves "
                    f"{oshb_simulation['manual_residual_row_count']} manual/textual "
                    "residual rows. No OSHB mapping rule, source approval, or reviewer "
                    "signoff is recorded."
                ),
            },
            {
                "gap": "Whole-Tanakh morphology unlock remains projected, not approved.",
                "evidence": (
                    "The unlock matrix projects "
                    f"{morph_unlock['unlockable_priority_unit_count']} priority units "
                    "could become review-ready after source approval and import, with "
                    f"{morph_unlock['pilot_mapped_non_psalm_book_count']} non-Psalm "
                    "pilot books, "
                    f"{morph_unlock['exception_review_row_count']} exception rows, "
                    f"{morph_unlock['candidate_rule_reduction_pct']:.2f}% candidate "
                    "rule reduction, and "
                    f"{morph_unlock['manual_residual_row_count']} manual residual rows. "
                    "It does not approve source use, importer behavior, or canonical "
                    "translation authority."
                ),
            },
            {
                "gap": "Contextual source packets are mapped but unsigned.",
                "evidence": (
                    f"The packet roadmap maps {contextual_source_packets['unit_count']} "
                    f"expanded units to {contextual_source_packets['family_assignment_count']} "
                    "source-family assignments. "
                    f"{contextual_source_packets['ancient_culture_packet_unit_count']} "
                    "units need ancient-culture packets, "
                    f"{contextual_source_packets['textual_witness_packet_unit_count']} "
                    "need textual-witness packet review, and "
                    f"{contextual_source_packets['jewish_christian_packet_unit_count']} "
                    "require separated Jewish/Christian packet work. "
                    f"{contextual_source_packets['blocked_gate_count']} packet gates "
                    "remain blocked."
                ),
            },
            {
                "gap": "Jewish and Christian reception lanes are separated but unsigned.",
                "evidence": (
                    f"The reception divergence atlas scores "
                    f"{reception_divergence['unit_count']} expanded units, including "
                    f"{reception_divergence['jewish_christian_separation_unit_count']} "
                    "that require explicit Jewish/Christian separation and "
                    f"{reception_divergence['academic_comparison_unit_count']} requiring "
                    "academic comparison. The reception source packet workbook generates "
                    f"{reception_source_packets['packet_count']} separated packet rows "
                    "from "
                    f"{reception_source_packets['split_lane_unit_count']} split-lane "
                    "units, but completed source-packet reviews remain "
                    f"{reception_source_packets['completed_packet_review_count']}. "
                    "The interpretive tradition control matrix joins those lanes with "
                    f"{interpretive_control['ancient_culture_pressure_unit_count']} "
                    "ancient-culture units and "
                    f"{interpretive_control['textual_witness_pressure_unit_count']} "
                    "textual-witness units while preserving "
                    f"{interpretive_control['source_approval_count']} source approvals."
                ),
            },
            {
                "gap": "Canonical cross-reference evidence is surface-form only.",
                "evidence": (
                    f"{cross_reference['cross_reference_unit_count']} Psalm units have "
                    "normalized UXLC surface-form anchors outside Psalms, including "
                    f"{cross_reference['three_division_unit_count']} with Torah, "
                    "Prophets, and non-Psalm Writings evidence. This routes "
                    "broader-canon review but does not prove lemma/sense identity "
                    "or allusion."
                ),
            },
            {
                "gap": "External source acquisition needs license and provenance gates.",
                "evidence": (
                    f"The acquisition plan identifies {source_acquisition['candidate_count']} "
                    "source candidates affecting "
                    f"{source_acquisition['packet_unit_count']} packet units. "
                    f"{source_acquisition['machine_readable_candidate_count']} candidates "
                    "are machine-readable, but only "
                    f"{source_acquisition['low_license_risk_candidate_count']} are low "
                    "license risk; "
                    f"{source_acquisition['blocked_gate_count']} acquisition gates are blocked."
                ),
            },
            {
                "gap": (
                    "Bibliography and provenance apparatus is generated but not source approval."
                ),
                "evidence": (
                    f"The bibliography apparatus has "
                    f"{doctoral_bibliography['bibliography_source_count']} source rows, "
                    f"{doctoral_bibliography['local_manifest_source_count']} local manifests, "
                    f"{doctoral_bibliography['candidate_source_count']} candidates, "
                    f"{doctoral_bibliography['blocked_authority_lane_count']} blocked "
                    "authority lanes, and "
                    f"{doctoral_bibliography['critical_gap_count']} critical gaps."
                ),
            },
            {
                "gap": "Live source verification is a routing signal, not approval.",
                "evidence": (
                    f"The verification snapshot checked "
                    f"{doctoral_source_verification['source_count']} source rows and found "
                    f"{doctoral_source_verification['reachable_url_count']} of "
                    f"{doctoral_source_verification['url_source_count']} official URLs "
                    "reachable. It still reports "
                    f"{doctoral_source_verification['gap_count']} verification gaps and "
                    f"{doctoral_source_verification['source_approval_count']} source "
                    "approvals."
                ),
            },
            {
                "gap": "Every expanded heatmap unit still has blocked authority lanes.",
                "evidence": (
                    f"The unit heatmap scores {doctoral_unit_heatmap['unit_count']} units "
                    f"across {doctoral_unit_heatmap['required_lane_row_count']} required "
                    "lane rows. Mean unit readiness is "
                    f"{doctoral_unit_heatmap['mean_unit_authority_score_pct']:.2f}%; "
                    f"{doctoral_unit_heatmap['blocked_unit_count']} units have blocked "
                    f"lanes. Top gap: {doctoral_unit_heatmap['top_gap_ref']}."
                ),
            },
            {
                "gap": "Integrated doctoral priority dossiers are still review assignments.",
                "evidence": (
                    f"The dossier atlas queues "
                    f"{doctoral_priority_dossier_atlas['unit_count']} units, including "
                    f"{doctoral_priority_dossier_atlas['critical_unit_count']} critical "
                    "units and "
                    f"{doctoral_priority_dossier_atlas['jewish_christian_separation_unit_count']} "
                    "requiring separated Jewish/Christian lanes. Mean authority score is "
                    f"{doctoral_priority_dossier_atlas['mean_authority_score_pct']:.2f}%."
                ),
            },
            {
                "gap": "Contextual review workbook is generated but entirely unsigned.",
                "evidence": (
                    f"The review workbook contains "
                    f"{review_signoff_workbook['total_review_row_count']} pending review "
                    f"rows, including {review_signoff_workbook['packet_review_row_count']} "
                    "source-packet rows and "
                    f"{review_signoff_workbook['source_acquisition_review_row_count']} "
                    "source-acquisition rows. Completed rows: "
                    f"{review_signoff_workbook['completed_review_row_count']}."
                ),
            },
            {
                "gap": "Doctoral synthesis verdict remains not-authoritative.",
                "evidence": (
                    f"The synthesis score is "
                    f"{doctoral_synthesis['doctoral_synthesis_score_pct']:.2f}% across "
                    f"{doctoral_synthesis['requirement_count']} requirements, with "
                    f"{doctoral_synthesis['blocked_requirement_count']} blocked requirements, "
                    f"{doctoral_synthesis['blocker_count']} blockers, and "
                    f"{doctoral_synthesis['critical_blocker_count']} critical blockers."
                ),
            },
            {
                "gap": "Full real local model bake-off is still incomplete.",
                "evidence": (
                    f"The contextual real-model matrix now consolidates "
                    f"{contextual_real_model_evidence['attempt_count']} measured "
                    "canonical, reception, and collision attempts with "
                    f"{contextual_real_model_evidence['clean_source_anchored_count']} "
                    "clean source-anchored rows and "
                    f"{contextual_real_model_evidence['source_anchor_issue_count']} "
                    "source-anchor issues, but only "
                    f"{contextual_real_model_evidence['valid_model_task_coverage_pct']:.2f}% "
                    "of planned contextual model-task rows are covered. "
                    f"{integrated_real_audit['schema_valid_result_count']} "
                    "schema-valid real rows exist, but "
                    f"{integrated_real_audit['missing_expected_result_count']} "
                    "integrated model-task rows remain unsubmitted and "
                    f"{integrated_real_audit.get('source_anchor_issue_count', 0)} "
                    "source-anchor issues are flagged. The expanded audit has "
                    f"{contextual_expanded_real['submitted_result_count']} of "
                    f"{contextual_expanded_real['expected_result_count']} rows "
                    "submitted."
                ),
            },
            {
                "gap": "Local model selection is executable but not settled.",
                "evidence": (
                    f"{local_selection['ready_local_candidate_count']} of "
                    f"{local_selection['candidate_count']} model-selection candidates "
                    "are runnable now. Gemma 4 26B has a local asset and its "
                    f"schema repair reaches "
                    f"{local_selection['gemma4_26b_repair_schema_valid_pct']:.2f}%, "
                    "but the repair report still flags "
                    f"{local_selection['gemma4_26b_repair_source_anchor_issue_count']} "
                    "source-anchor issue(s) and failed gates: "
                    + ", ".join(local_selection["gemma4_26b_repair_failed_gates"])
                    + f". Mistral Small 3.2 has "
                    f"{local_selection['mistral_schema_valid_pct']:.2f}% schema-valid "
                    "measured rows but remains blocked by the layer gate. The doctoral "
                    "bakeoff matrix ranks "
                    f"{local_bakeoff['best_current_bakeoff_baseline']} as the best "
                    "current measured baseline, "
                    f"{local_bakeoff['best_trainable_base_if_asset_added']} as the "
                    "best trainable target after exact asset intake, and "
                    f"{local_bakeoff['best_hebrew_specialist_candidate']} as the best "
                    "Hebrew-specialist challenger."
                ),
            },
            {
                "gap": "The expanded benchmark still does not cover the full 100-unit atlas.",
                "evidence": (
                    f"The integrated suite covers {coverage['integrated_covered_unit_count']} "
                    f"of {coverage['atlas_unit_count']} atlas units. The contextual "
                    f"gap supplement raises projected coverage to "
                    f"{contextual_gap['projected_expanded_atlas_coverage_pct']:.2f}%, "
                    f"leaving {contextual_gap['remaining_uncovered_unit_count']} units."
                ),
            },
            {
                "gap": "Whole-Tanakh context is form-level, not lemma/sense aware.",
                "evidence": (
                    f"Lexeme audit has {lexeme['strong_coverage_pct']:.2f}% "
                    "Psalm Strong coverage and the canonical context network maps "
                    f"{context_network['unit_count']} expanded units. The "
                    "morphology-gap audit finds "
                    f"{morph_gap['local_non_psalm_books_with_hebrew_morphology']} "
                    "non-Psalm books with local Hebrew morphology and "
                    f"{morph_gap['outside_strong_context_token_pct']:.2f}% "
                    "outside Strong-context coverage."
                ),
            },
            {
                "gap": "MACULA semantic_role and referent are absent in current packets.",
                "evidence": "Corpus profile reports 0% coverage for both fields.",
            },
            {
                "gap": "English witnesses are evidence, not generation sources.",
                "evidence": (
                    f"{witness['witness_source_generation_block_count']} used "
                    "witness sources are blocked from generation: "
                    + ", ".join(witness["witness_sources_not_allowed_for_generation"])
                    + "."
                ),
            },
            {
                "gap": "English witness divergence requires reviewer adjudication.",
                "evidence": (
                    f"Mean KJV/ASV/WEB divergence is "
                    f"{witness_divergence['mean_english_witness_divergence_pct']:.2f}%, "
                    f"with {witness_divergence['high_divergence_unit_count']} "
                    "high-divergence units and "
                    f"{witness_divergence['divine_name_disagreement_unit_count']} "
                    "divine-name rendering disagreements."
                ),
            },
            {
                "gap": "Divine-name and title rendering policy is not signed off.",
                "evidence": (
                    f"{divine_name['divine_title_unit_count']} Psalm units contain "
                    f"{divine_name['divine_title_token_count']} divine-name/title tokens. "
                    f"{divine_name['witness_disagreement_unit_count']} title-bearing units "
                    "have English witness rendering disagreement, including "
                    f"{divine_name['yhwh_adonai_lord_stack_unit_count']} YHWH plus "
                    "Adonai/Lord stack-pressure units."
                ),
            },
            {
                "gap": "Superscription and liturgical context is not signed off.",
                "evidence": (
                    f"{superscription['context_unit_count']} Psalm units contain "
                    "superscription, performance, attribution, liturgical, or "
                    "historical-notice markers. "
                    f"{superscription['historical_notice_unit_count']} carry historical "
                    f"notice pressure, {superscription['technical_term_unit_count']} "
                    "include technical heading terms, and the current top priority is "
                    f"{superscription['top_priority_ref']}."
                ),
            },
            {
                "gap": "Cultural and historical domain routing is not signoff.",
                "evidence": (
                    f"{cultural['domain_unit_count']} Psalm units carry cultural or "
                    f"historical domain markers across {cultural['domain_count']} domains, "
                    f"with {cultural['domain_token_count']} domain-token assignments and "
                    f"{cultural['high_priority_unit_count']} high-priority review units. "
                    f"Top priority: {cultural['top_priority_ref']}."
                ),
            },
            {
                "gap": "Corpus-wide reception signals are routing evidence, not signoff.",
                "evidence": (
                    f"{corpus_reception_signal['signal_unit_count']} Psalm units carry "
                    "reception signal routing across "
                    f"{corpus_reception_signal['signal_family_count']} signal families. "
                    f"{corpus_reception_signal['high_pressure_unit_count']} are "
                    "high-pressure and "
                    f"{corpus_reception_signal['new_high_pressure_expansion_candidate_count']} "
                    "are new high-pressure expansion candidates outside the explicit "
                    "reception-divergence rows."
                ),
            },
            {
                "gap": "Real model outputs are not yet honoring layer separation reliably.",
                "evidence": (
                    f"The layer audit found "
                    f"{layer_consistency['exact_duplicate_pair_count']} exact "
                    "gloss/literal duplicates and "
                    f"{layer_consistency['weak_layer_differentiation_pair_count']} "
                    "weakly differentiated pairs across "
                    f"{layer_consistency['paired_unit_model_count']} paired rows; "
                    f"mean word overlap is "
                    f"{layer_consistency['mean_word_jaccard_pct']:.2f}%."
                ),
            },
            {
                "gap": "Layer remediation still requires a passing rerun.",
                "evidence": (
                    f"The remediation plan defines "
                    f"{layer_remediation['action_count']} actions and "
                    f"{layer_remediation['retry_task_count']} retry tasks. Runner "
                    "layer contracts are "
                    + ("present" if layer_remediation["runner_contract_ready"] else "missing")
                    + "; a post-remediation paired rerun exists, but its best attempt "
                    f"still has {layer_experiment['failed_gate_count']} failed gate(s)."
                ),
            },
            {
                "gap": "Layer remediation experiment is only a partial improvement.",
                "evidence": (
                    f"The best retry attempt is {layer_experiment['best_attempt_label']} "
                    f"with {layer_experiment['best_attempt_schema_valid_pct']:.2f}% "
                    "schema validity and "
                    f"{layer_experiment['best_attempt_exact_duplicate_pair_count']} "
                    "exact duplicates, but "
                    f"{layer_experiment['best_attempt_weak_layer_differentiation_pair_count']} "
                    "weak-differentiation pair remains; failed gates: "
                    + ", ".join(layer_experiment["failed_gates"])
                    + "."
                ),
            },
            {
                "gap": "Interpretive adjudication is routed but not decided.",
                "evidence": (
                    f"The adjudication matrix routes "
                    f"{interpretive_adjudication['unit_count']} expanded units "
                    f"across {interpretive_adjudication['lane_count']} lanes. "
                    f"{interpretive_adjudication['jewish_christian_separation_unit_count']} "
                    "units require Jewish/Christian separation and "
                    f"{interpretive_adjudication['units_with_layer_blockers']} "
                    "have layer blockers. The interpretive tradition control matrix "
                    "keeps "
                    f"{interpretive_control['translation_text_forbidden_reception_claim_units']} "
                    "reception claim units out of translation wording until signoff; "
                    "failed gates: " + ", ".join(interpretive_adjudication["failed_gates"]) + "."
                ),
            },
            {
                "gap": "Casebook evidence is assembled but still unsigned.",
                "evidence": (
                    f"The scholarly casebook contains {scholarly_casebook['case_count']} "
                    f"high-risk cases over {scholarly_casebook['total_token_count']} "
                    "Hebrew source tokens. "
                    f"{scholarly_casebook['reception_case_count']} cases require "
                    "reception separation and "
                    f"{scholarly_casebook['layer_blocker_case_count']} carry layer "
                    "blockers, so these are review packets, not approved readings."
                ),
            },
            {
                "gap": "Reception and cultural interpretation controls are not signed off.",
                "evidence": (
                    f"The boundary ledger flags "
                    f"{reception_boundary['reception_sensitive_unit_count']} "
                    "reception-sensitive expanded units and "
                    f"{reception_boundary['high_boundary_risk_unit_count']} "
                    "high-risk boundary units. The claim matrix maps "
                    f"{claim_matrix['high_risk_unit_count']} high-risk claim rows, "
                    "but reviewer decisions are absent."
                ),
            },
            {
                "gap": "Integrated context pressure is routed but not adjudicated.",
                "evidence": (
                    f"The doctoral context integration matrix joins "
                    f"{context_integration['unit_count']} Psalm units across "
                    f"{context_integration['lens_count']} lenses. It flags "
                    f"{context_integration['high_pressure_unit_count']} high-pressure "
                    "units, "
                    f"{context_integration['multi_lens_unit_count']} six-plus-lens "
                    "units, and "
                    f"{context_integration['doctoral_collision_unit_count']} doctoral "
                    "collision units where broader-canon, culture, textual witness, "
                    "and reception pressures overlap. These are review routing rows, "
                    "not adjudicated translation decisions."
                ),
            },
            {
                "gap": "Collision packets are generated but entirely unsigned.",
                "evidence": (
                    f"The collision packet workbook turns "
                    f"{collision_packets['collision_packet_count']} cross-lens units "
                    f"into {collision_packets['decision_row_count']} pending decision "
                    f"rows across {collision_packets['lane_count']} review lanes and "
                    f"{collision_packets['reviewer_role_count']} reviewer roles. "
                    f"Completed decision rows remain "
                    f"{collision_packets['completed_decision_count']}."
                ),
            },
            {
                "gap": "Collision benchmark companion artifacts are generated but unscored.",
                "evidence": (
                    f"The collision benchmark supplement creates "
                    f"{collision_benchmark['task_count']} gloss/literal tasks and "
                    f"{collision_benchmark['planned_model_runs']} planned model runs from "
                    f"{collision_benchmark['selected_collision_unit_count']} collision units, "
                    f"with {collision_benchmark_cross_exam['packet_count']} advisory "
                    "cross-exam packets, "
                    f"{collision_benchmark_dry_run['schema_valid_result_count']} "
                    "schema-valid dry-run rows, and "
                    f"{collision_benchmark_review['projected_human_review_rows']} projected "
                    "human review rows. A bounded real smoke now adds "
                    f"{collision_real_smoke['attempt_count']} attempts, "
                    f"{collision_real_smoke['clean_schema_valid_attempt_count']} clean "
                    "source-anchored rows, and "
                    f"{collision_real_smoke['source_anchor_issue_count']} source-anchor "
                    "issues; scaled model scoring and human signoff remain missing."
                ),
            },
            {
                "gap": "Human review and signoff data do not exist yet.",
                "evidence": (
                    f"Integrated review plan projects "
                    f"{integrated_review['projected_human_review_rows']} human "
                    "rows, but completed reviewer scores are absent."
                ),
            },
        ],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


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
        cells = []
        for cell in row:
            if str(cell).startswith("<"):
                cells.append(f"<td>{cell}</td>")
            else:
                cells.append(f"<td>{esc(cell)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def artifact_rows(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in dashboard["artifact_inventory"]:
        rows.append(
            {
                "artifact": item["key"],
                "bytes_kib": round(int(item["bytes"]) / 1024, 1),
            }
        )
    return sorted(rows, key=lambda item: float(item["bytes_kib"]), reverse=True)


def render_html(dashboard: dict[str, Any]) -> str:
    headline = dashboard["headline"]
    evidence = dashboard["evidence"]
    collision_smoke_clean_pct = headline["collision_real_smoke_clean_attempt_pct"]
    canon_smoke_coverage = headline["canonical_intertext_real_smoke_valid_model_task_coverage_pct"]
    reception_smoke_coverage = headline["reception_signal_real_smoke_valid_model_task_coverage_pct"]
    report_rows = [
        [
            f'<a href="{esc(report["path"])}">{esc(report["label"])}</a>',
            report["purpose"],
        ]
        for report in dashboard["html_reports"]
    ]
    pipeline_rows = [
        [
            row["stage"],
            row["status"],
            f"{row['completion_pct']:.2f}%",
            row["evidence"],
        ]
        for row in dashboard["pipeline"]
    ]
    local_bakeoff_candidate_rows = [
        [
            row["rank"],
            row["short_name"],
            row["role"],
            f"{row['doctoral_bakeoff_score_pct']:.2f}%",
            row["status_band"],
            row["local_asset_status"],
            f"{row['effective_schema_valid_pct']:.2f}%",
            f"{row['contextual_clean_source_anchored_pct']:.2f}%",
            row["contextual_source_anchor_issue_count"],
            f"{row['hebrew_score_pct']:.2f}%",
            row["current_action"],
        ]
        for row in evidence["local_bakeoff_candidate_rows"]
    ]
    local_bakeoff_gate_rows = [
        [
            row["gate"],
            row["status"],
            f"{row['score_pct']:.2f}%",
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["local_bakeoff_gate_rows"]
    ]
    local_bakeoff_phase_rows = [
        [
            row["phase"],
            row["label"],
            row["entry_criteria"],
            row["exit_criteria"],
            row["models"],
            row["authority_boundary"],
        ]
        for row in evidence["local_bakeoff_phase_rows"]
    ]
    model_training_certification_candidate_rows = [
        [
            row["rank"],
            row["short_name"],
            row["role"],
            row["local_asset_status"],
            row["fit_status"],
            f"{row['training_readiness_score_pct']:.2f}%",
            row["certification_status"],
            row["training_action"],
        ]
        for row in evidence["model_training_certification_candidate_rows"][:14]
    ]
    model_training_certification_gate_rows = [
        [
            row["gate"],
            row["status"],
            f"{row['score_pct']:.2f}%",
            "yes" if row["blocks_certification"] else "no",
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["model_training_certification_gate_rows"]
    ]
    model_training_certification_phase_rows = [
        [
            row["phase"],
            row["label"],
            row["status"],
            f"{row['readiness_pct']:.2f}%",
            row["evidence"],
            row["exit_criteria"],
            row["next_action"],
        ]
        for row in evidence["model_training_certification_phase_rows"]
    ]
    model_training_certification_source_rows = [
        [
            row["short_name"],
            row["public_role"],
            row["params_b"],
            row["activated_params_b"],
            row["context_tokens"],
            row["known_q4_memory_gb"],
            row["known_qlora_vram_gb"],
            row["fit_status"],
            row["source_urls"],
        ]
        for row in evidence["model_training_certification_source_rows"]
    ]
    authority_gate_rows = [
        [
            row["label"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["blocking_gap"],
        ]
        for row in evidence["authority_gate_rows"]
    ]
    source_maturity_lane_rows = [
        [
            row["label"],
            f"{row['evidence_score_pct']:.2f}%",
            f"{row['authority_score_pct']:.2f}%",
            row["authority_status"],
            row["blocking_gap"],
        ]
        for row in evidence["source_maturity_lanes"]
    ]
    source_maturity_source_rows = [
        [
            row["source_id"],
            row["name"],
            row["language"],
            row["basis_role"],
            row["license"],
            row["version"],
            row["version_pinned"],
            row["allowed_for_generation"],
            row["witness_records"],
        ]
        for row in evidence["source_maturity_sources"]
    ]
    source_maturity_gate_rows = [
        [
            row["gate"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["source_maturity_gates"]
    ]
    witness_divergence_pair_rows = [
        [
            row["source_pair"],
            f"{row['mean_divergence_pct']:.2f}%",
            f"{row['median_divergence_pct']:.2f}%",
            f"{row['p90_divergence_pct']:.2f}%",
            row["high_divergence_unit_count"],
            f"{row['mean_token_delta']:.2f}",
        ]
        for row in evidence["witness_divergence_pairs"]
    ]
    witness_divergence_marker_rows = [
        [
            row["marker"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
        ]
        for row in evidence["witness_divergence_markers"]
    ]
    witness_divergence_priority_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['priority_score']:.2f}",
            f"{row['mean_divergence_pct']:.2f}%",
            f"{row['length_spread_pct']:.2f}%",
            "; ".join(row["marker_flags"]),
            row["kjv_excerpt"],
            row["asv_excerpt"],
            row["web_excerpt"],
        ]
        for row in evidence["witness_divergence_priority_units"][:20]
    ]
    witness_divergence_psalm_rows = [
        [
            row["psalm_id"],
            row["unit_count"],
            f"{row['mean_divergence_pct']:.2f}%",
            row["high_divergence_unit_count"],
            row["divine_name_disagreement_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["witness_divergence_psalms"][:25]
    ]
    divine_name_category_rows = [
        [
            row["label"],
            row["token_count"],
        ]
        for row in evidence["divine_name_policy_category_tokens"]
    ]
    divine_name_marker_rows = [
        [
            row["marker"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
        ]
        for row in evidence["divine_name_policy_markers"]
    ]
    divine_name_priority_rows = [
        [
            index + 1,
            row["ref"],
            f"{row['priority_score']:.2f}",
            row["divine_title_token_count"],
            "; ".join(row["categories"]),
            "; ".join(row["marker_flags"]),
            row["kjv_excerpt"],
            row["asv_excerpt"],
            row["web_excerpt"],
        ]
        for index, row in enumerate(evidence["divine_name_policy_units"][:20])
    ]
    divine_name_psalm_rows = [
        [
            row["psalm_id"],
            row["divine_title_unit_count"],
            row["divine_title_token_count"],
            row["yhwh_token_count"],
            row["elohim_token_count"],
            row["adonai_token_count"],
            row["witness_disagreement_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["divine_name_policy_psalms"][:25]
    ]
    superscription_category_rows = [
        [
            row["label"],
            row["token_count"],
        ]
        for row in evidence["superscription_context_category_tokens"]
    ]
    superscription_marker_rows = [
        [
            row["marker"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
        ]
        for row in evidence["superscription_context_markers"]
    ]
    superscription_priority_rows = [
        [
            index + 1,
            row["ref"],
            f"{row['priority_score']:.2f}",
            row["context_token_count"],
            "; ".join(row["categories"]),
            "; ".join(row["marker_flags"]),
            row["kjv_excerpt"],
            row["asv_excerpt"],
            row["web_excerpt"],
        ]
        for index, row in enumerate(evidence["superscription_context_units"][:20])
    ]
    superscription_psalm_rows = [
        [
            row["psalm_id"],
            row["context_unit_count"],
            row["context_token_count"],
            row["heading_or_extended_heading_unit_count"],
            row["historical_notice_unit_count"],
            row["technical_term_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["superscription_context_psalms"][:25]
    ]
    cultural_domain_rows = [
        [
            row["label"],
            row["token_count"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["psalm_count"],
            row["high_priority_unit_count"],
            row["ancient_culture_pressure_unit_count"],
            row["reception_sensitive_unit_count"],
            ", ".join(item["lemma"] for item in row["top_lemmas"][:8]),
        ]
        for row in evidence["cultural_historical_domain_rows"]
    ]
    cultural_marker_rows = [
        [
            row["marker"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
        ]
        for row in evidence["cultural_historical_markers"]
    ]
    cultural_priority_rows = [
        [
            index + 1,
            row["ref"],
            f"{row['priority_score']:.2f}",
            row["domain_token_count"],
            "; ".join(row["domain_labels"]),
            "; ".join(row["marker_flags"]),
            row["kjv_excerpt"],
            row["asv_excerpt"],
            row["web_excerpt"],
        ]
        for index, row in enumerate(evidence["cultural_historical_units"][:20])
    ]
    cultural_psalm_rows = [
        [
            row["psalm_id"],
            row["domain_unit_count"],
            row["domain_token_count"],
            row["distinct_domain_count"],
            row["ancient_culture_pressure_unit_count"],
            row["reception_sensitive_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["cultural_historical_psalms"][:25]
    ]
    cultural_cooccurrence_rows = [
        [
            row["left_label"],
            row["right_label"],
            row["unit_count"],
            f"{row['mean_priority_score']:.2f}",
        ]
        for row in evidence["cultural_historical_cooccurrence"][:25]
    ]
    poetic_feature_rows = [
        [
            row["feature"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["poetic_rhetorical_features"]
    ]
    poetic_priority_rows = [
        [
            index + 1,
            row["ref"],
            row["pressure_band"],
            f"{row['poetic_rhetorical_priority_score']:.2f}",
            row["volitive_token_count"],
            row["repeated_lemma_token_excess"],
            row["adjacent_lemma_overlap_count"],
            "; ".join(row["feature_flags"]),
        ]
        for index, row in enumerate(evidence["poetic_rhetorical_units"][:25])
    ]
    poetic_psalm_rows = [
        [
            row["psalm_id"],
            row["unit_count"],
            row["high_pressure_unit_count"],
            f"{row['mean_poetic_rhetorical_score']:.2f}",
            row["acrostic_profile"],
            row["distinct_initial_hebrew_letter_count"],
            row["top_ref"],
        ]
        for row in evidence["poetic_rhetorical_psalms"][:25]
    ]
    corpus_reception_signal_rows = [
        [
            row["label"],
            row["token_count"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["known_reception_divergence_unit_count"],
            row["known_jewish_christian_split_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["corpus_reception_signal_signals"]
    ]
    corpus_reception_priority_rows = [
        [
            index + 1,
            row["ref"],
            row["pressure_band"],
            f"{row['reception_signal_priority_score']:.2f}",
            row["signal_family_count"],
            "; ".join(row["signal_labels"]),
            "; ".join(row["report_flags"]),
            "; ".join(row["recommended_review_roles"]),
        ]
        for index, row in enumerate(evidence["corpus_reception_signal_units"][:25])
    ]
    corpus_reception_expansion_rows = [
        [
            row["rank"],
            row["ref"],
            row["pressure_band"],
            f"{row['reception_signal_priority_score']:.2f}",
            row["signal_family_count"],
            "; ".join(row["signal_ids"]),
            "; ".join(row["recommended_review_roles"]),
        ]
        for row in evidence["corpus_reception_signal_expansion"][:30]
    ]
    corpus_reception_psalm_rows = [
        [
            row["psalm_id"],
            row["signal_unit_count"],
            row["signal_token_count"],
            row["signal_family_count"],
            row["known_jewish_christian_split_count"],
            row["high_pressure_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["corpus_reception_signal_psalms"][:25]
    ]
    reception_signal_benchmark_chart_rows = [
        {
            "label": f"{task['ref']} {task['layer']}",
            "value": task["reception_signal_priority_score"],
        }
        for task in evidence["reception_signal_benchmark_tasks"]
        if task["layer"] == "gloss"
    ][:20]
    reception_signal_benchmark_task_rows = [
        [
            index + 1,
            task["task_id"],
            task["ref"],
            task["layer"],
            task["reception_pressure_band"],
            f"{task['reception_signal_priority_score']:.2f}",
            task["signal_family_count"],
            "; ".join(task["signal_ids"]),
            task["token_count"],
            fmt_int(task["estimated_payload_chars"]),
        ]
        for index, task in enumerate(evidence["reception_signal_benchmark_tasks"][:30])
    ]
    reception_signal_packet_signal_counts: Counter[str] = Counter()
    for packet in evidence["reception_signal_benchmark_cross_exam_packets"]:
        reception_signal_packet_signal_counts.update(
            packet["reception_signal_context"]["signal_ids"]
        )
    reception_signal_packet_signal_rows = [
        {"label": label, "value": count}
        for label, count in reception_signal_packet_signal_counts.most_common(12)
    ]
    reception_signal_cross_exam_rows = [
        [
            packet["packet_id"],
            packet["ref"],
            packet["layer"],
            packet["judge_id"],
            packet["priority"],
            packet["reception_signal_context"]["pressure_band"],
            len(packet["probe_questions"]),
            "; ".join(packet["reception_signal_context"]["signal_ids"][:4]),
        ]
        for packet in evidence["reception_signal_benchmark_cross_exam_packets"][:24]
    ]
    reception_signal_dry_run_rows = [
        [
            row["task_id"],
            row["model_profile_id"],
            "yes" if row["schema_valid"] else "no",
            row["candidate_count"],
            f"{row['mean_alignment_score_0_5']:.2f}",
            f"{row['mean_translation_basis_score_0_5']:.2f}",
            row["source_anchor_issue_count"],
        ]
        for row in evidence["reception_signal_benchmark_dry_run_results"]
    ]
    reception_signal_review_rows = [
        [
            row["task_id"],
            row["ref"],
            row["layer"],
            row["intensity"],
            row["required_role_count"],
            "; ".join(row["required_roles"]),
        ]
        for row in evidence["reception_signal_benchmark_review_plan"][:30]
    ]
    contextual_packet_family_rows = [
        [
            row["label"],
            row["status"],
            row["unit_count"],
            row["highest_priority_unit_count"],
            row["top_ref"],
            "; ".join(row["review_roles"]),
            row["authority_boundary"],
        ]
        for row in evidence["contextual_source_packet_families"]
    ]
    contextual_packet_role_rows = [
        [
            row["reviewer_role"],
            row["unit_count"],
            row["family_assignment_count"],
            row["highest_priority_unit_count"],
            row["authority_boundary"],
        ]
        for row in evidence["contextual_source_packet_roles"]
    ]
    contextual_packet_unit_rows = [
        [
            row["rank"],
            f"<strong>{esc(row['ref'])}</strong><br><span>{esc(row['unit_id'])}</span>",
            f"{row['packet_priority_score']:.2f}",
            row["packet_priority_band"],
            row["packet_family_count"],
            "; ".join(row["packet_families"][:10]),
        ]
        for row in evidence["contextual_source_packet_units"][:15]
    ]
    contextual_packet_gate_rows = [
        [
            row["gate"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["contextual_source_packet_gates"]
    ]
    source_acquisition_candidate_rows = [
        [
            row["label"],
            row["priority_band"],
            row["priority_score"],
            row["packet_unit_count"],
            row["license_risk"],
            row["machine_readable"],
            row["acquisition_status"],
        ]
        for row in evidence["source_acquisition_candidates"]
    ]
    source_acquisition_phase_rows = [
        [
            row["rank"],
            row["label"],
            row["candidate_count"],
            row["max_packet_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["machine_readable_count"],
            row["high_license_risk_count"],
            row["exit_gate"],
        ]
        for row in evidence["source_acquisition_phases"]
    ]
    source_acquisition_gate_rows = [
        [
            row["gate"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["source_acquisition_gates"]
    ]
    morphology_acquisition_candidate_rows = [
        [
            row["recommended_rank"],
            row["label"],
            row["recommendation"],
            row["priority_score"],
            row["license_risk"],
            row["current_repo_status"],
            row["authority_status"],
            row["why_this_sequence"],
        ]
        for row in evidence["morphology_acquisition_candidates"]
    ]
    morphology_acquisition_gate_rows = [
        [
            row["gate_id"],
            row["gate"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["morphology_acquisition_gates"]
    ]
    morphology_acquisition_phase_rows = [
        [
            row["rank"],
            row["phase"],
            row["primary_candidate_label"],
            row["status"],
            f"{row['mean_gate_score_pct']:.2f}%",
            row["blocked_gate_count"],
            row["not_started_gate_count"],
            "; ".join(row["gate_ids"]),
        ]
        for row in evidence["morphology_acquisition_phases"]
    ]
    morphology_acquisition_inventory_rows = [
        [
            row["source_id"],
            row["local_path"],
            row["exists"],
            row["local_file_count"],
            row["book_scope"],
            row["morphology_scope"],
            row["non_psalm_book_count_with_morphology"],
            row["authority_use"],
        ]
        for row in evidence["morphology_acquisition_local_inventory"]
    ]
    oshb_alignment_division_rows = [
        [
            row["division"],
            row["book_count"],
            row["oshb_word_count"],
            f"{row['exact_sequence_match_pct']:.2f}%",
            f"{row['token_count_match_pct']:.2f}%",
            f"{row['mean_sequence_similarity_pct']:.2f}%",
            row["mismatch_verse_count"],
        ]
        for row in evidence["oshb_alignment_pilot_division_rows"]
    ]
    oshb_alignment_book_rows = [
        [
            row["book"],
            row["division"],
            row["oshb_word_count"],
            row["uxlc_word_count"],
            f"{row['morph_coverage_pct']:.2f}%",
            f"{row['exact_sequence_match_pct']:.2f}%",
            f"{row['mean_sequence_similarity_pct']:.2f}%",
            row["mismatch_verse_count"],
            row["alignment_readiness"],
        ]
        for row in evidence["oshb_alignment_pilot_book_rows"]
    ]
    oshb_alignment_mismatch_rows = [
        [
            row["book"],
            row["osis_id"],
            row["mismatch_type"],
            row["oshb_token_count"],
            row["uxlc_token_count"],
            f"{row['sequence_similarity_pct']:.2f}%",
            row["first_difference_index"],
            " ".join(row["oshb_surface_window"]),
            " ".join(row["uxlc_surface_window"]),
        ]
        for row in evidence["oshb_alignment_pilot_mismatch_rows"][:40]
    ]
    oshb_exception_gate_rows = [
        [
            row["gate_id"],
            row["gate"],
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["oshb_exception_review_gate_rows"]
    ]
    oshb_exception_book_rows = [
        [
            row["book"],
            row["division"],
            row["priority"],
            f"{row['exception_pressure_score']:.2f}",
            row["mismatch_verse_count"],
            f"{row['mismatch_verse_pct']:.2f}%",
            row["token_count_exception_verse_count"],
            row["sequence_only_exception_verse_count"],
            row["sample_row_count"],
            row["recommended_action"],
        ]
        for row in evidence["oshb_exception_review_book_rows"]
    ]
    oshb_exception_sample_rows = [
        [
            row["book"],
            row["osis_id"],
            row["severity"],
            row["exception_class"],
            row["oshb_token_count"],
            row["uxlc_token_count"],
            row["token_delta"],
            f"{row['sequence_similarity_pct']:.2f}%",
            ", ".join(row["review_lanes"]),
        ]
        for row in evidence["oshb_exception_review_sample_rows"][:60]
    ]
    oshb_taxonomy_cause_rows = [
        [
            row["cause_family"],
            row["row_count"],
            f"{row['row_pct']:.2f}%",
            row["critical_count"],
            row["high_count"],
            row["medium_count"],
            row["segmentation_marker_count"],
            row["book_count"],
            row["review_intensity"],
            row["recommended_batching"],
        ]
        for row in evidence["oshb_exception_taxonomy_cause_rows"]
    ]
    oshb_taxonomy_batch_rows = [
        [
            row["batch_id"],
            row["book"],
            row["cause_family"],
            row["severity"],
            row["review_intensity"],
            row["row_count"],
            row["first_osis_id"],
            row["last_osis_id"],
            ", ".join(row["review_lanes"]),
            row["status"],
        ]
        for row in evidence["oshb_exception_taxonomy_batch_rows"][:80]
    ]
    oshb_mapping_rule_rows = [
        [
            row["candidate_rule_id"],
            row["candidate_rule"],
            row["automation_lane"],
            row["row_count"],
            f"{row['row_pct']:.2f}%",
            row["high_confidence_count"],
            row["medium_confidence_count"],
            row["low_confidence_count"],
            row["manual_none_confidence_count"],
            row["dominant_cause_family"],
            row["authority_status"],
            row["next_action"],
        ]
        for row in evidence["oshb_mapping_rule_simulation_rule_rows"]
    ]
    oshb_mapping_packet_rows = [
        [
            row["batch_id"],
            row["book"],
            row["osis_id"],
            row["severity"],
            row["candidate_rule_id"],
            row["automation_lane"],
            row["confidence_band"],
            row["review_requirement"],
            row["simulated_mapping_status"],
            "yes" if row["requires_psalm_regression"] else "no",
            "yes" if row["requires_aramaic_review"] else "no",
        ]
        for row in evidence["oshb_mapping_rule_simulation_packet_rows"][:80]
    ]
    morph_unlock_phase_rows = [
        [
            row["phase_id"],
            row["phase"],
            row["status"],
            row["evidence"],
            row["exit_criterion"],
        ]
        for row in evidence["morph_unlock_phase_rows"]
    ]
    morph_unlock_unit_rows = [
        [
            row["ref"],
            f"{row['current_lane_score_pct']:.2f}%",
            row["current_lane_status"],
            row["anchor_token_count"],
            row["high_value_anchor_count"],
            "yes" if row["has_three_division_evidence"] else "no",
            f"{row['projected_review_ready_score_pct_if_oshb_approved']:.2f}%",
            f"{row['projected_lane_score_delta_pct']:.2f}%",
            row["unlock_status"],
            "; ".join(row["top_outside_books"][:4]),
        ]
        for row in evidence["morph_unlock_unit_rows"][:25]
    ]
    morph_unlock_book_rows = [
        [
            row["book"],
            row["division"],
            row["priority"],
            f"{row['exception_pressure_score']:.2f}",
            row["mismatch_verse_count"],
            f"{row['exact_sequence_match_pct']:.2f}%",
            f"{row['candidate_rule_routable_pct']:.2f}%",
            row["manual_exception_count"],
            row["psalm_anchor_token_count"],
            row["recommended_action"],
        ]
        for row in evidence["morph_unlock_book_rows"][:25]
    ]
    morph_unlock_cause_rows = [
        [
            row["cause_family"],
            row["row_count"],
            f"{row['row_pct']:.2f}%",
            row["critical_count"],
            row["high_count"],
            row["psalm_regression_count"],
            row["aramaic_review_count"],
            row["segmentation_marker_count"],
            row["recommended_batching"],
        ]
        for row in evidence["morph_unlock_cause_rows"]
    ]
    morph_unlock_rule_rows = [
        [
            row["candidate_rule_id"],
            row["automation_lane"],
            row["row_count"],
            f"{row['row_pct']:.2f}%",
            row["high_confidence_count"],
            row["medium_confidence_count"],
            row["low_confidence_count"],
            row["manual_none_confidence_count"],
            row["psalm_regression_count"],
            row["aramaic_review_count"],
            row["authority_status"],
        ]
        for row in evidence["morph_unlock_rule_rows"]
    ]
    critical_unit_morphology_unlock_unit_rows = [
        [
            index,
            row["ref"],
            f"{row['morphology_gap_risk_score']:.2f}",
            f"{row['surface_outside_context_pct']:.2f}%",
            row["anchor_token_count"],
            row["high_value_anchor_count"],
            f"{row['current_lane_score_pct']:.2f}%",
            f"{row['projected_review_ready_score_pct']:.2f}%",
            f"{row['projected_lane_score_delta_pct']:.2f}%",
            "; ".join(row["top_outside_books"][:5]),
            row["unlock_status"],
        ]
        for index, row in enumerate(
            evidence["critical_unit_morphology_unlock_unit_rows"][:35],
            start=1,
        )
    ]
    critical_unit_morphology_unlock_book_rows = [
        [
            row["book"],
            row["division"],
            row["critical_unit_anchor_count"],
            row["priority"],
            row["mismatch_verse_count"],
            f"{row['exact_sequence_match_pct']:.2f}%",
            f"{row['exception_pressure_score']:.2f}",
            row["candidate_rule_routable_count"],
            row["manual_exception_count"],
            row["recommended_action"],
        ]
        for row in evidence["critical_unit_morphology_unlock_book_rows"][:25]
    ]
    critical_unit_morphology_unlock_phase_rows = [
        [
            row["phase_id"],
            row["phase"],
            row["status"],
            f"{row['completion_pct']:.2f}%",
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["critical_unit_morphology_unlock_phase_rows"]
    ]
    critical_unit_morphology_unlock_gate_rows = [
        [
            row["gate_id"],
            row["gate"],
            row["status"],
            row["current_value"],
            row["target_value"],
            row["blocking_gap"],
            row["next_action"],
        ]
        for row in evidence["critical_unit_morphology_unlock_gate_rows"]
    ]
    bibliography_lane_rows = [
        [
            row["label"],
            f"{row['evidence_score_pct']:.2f}%",
            f"{row['authority_score_pct']:.2f}%",
            row["present_source_count"],
            row["candidate_source_count"],
            row["authority_status"],
            row["blocking_gap"],
        ]
        for row in evidence["doctoral_bibliography_lanes"]
    ]
    bibliography_source_rows = [
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
        for row in evidence["doctoral_bibliography_sources"]
    ]
    bibliography_family_rows = [
        [
            row["label"],
            row["status"],
            row["unit_count"],
            row["candidate_source_count"],
            row["best_license_risk"],
            "; ".join(row["review_roles"]),
            row["authority_boundary"],
        ]
        for row in evidence["doctoral_bibliography_families"]
    ]
    bibliography_gap_rows = [
        [
            row["gap_id"],
            row["severity"],
            row["label"],
            row["evidence"],
            "; ".join(row["closing_sources"]),
            row["next_action"],
        ]
        for row in evidence["doctoral_bibliography_gaps"]
    ]
    bibliography_method_rows = [
        [
            row["method_id"],
            row["rule"],
            row["allowed_use"],
            row["forbidden_use"],
        ]
        for row in evidence["doctoral_bibliography_methods"]
    ]
    source_verification_source_rows = [
        [
            row["source_id"],
            row["source_class"],
            row["label"],
            row["license_risk"],
            row["verification_status"],
            row["http_status"],
            row["license_claim_status"],
            "; ".join(row["detected_terms"]),
            row["official_url"],
        ]
        for row in evidence["doctoral_source_verification_sources"]
    ]
    source_verification_gap_rows = [
        [
            row["gap_id"],
            row["severity"],
            row["label"],
            row["evidence"],
            row["official_url"],
            row["next_action"],
        ]
        for row in evidence["doctoral_source_verification_gaps"]
    ]
    source_ladder_unit_rows = [
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
        for row in evidence["source_authority_ladder_unit_rows"][:25]
    ]
    source_ladder_family_rows = [
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
        for row in evidence["source_authority_ladder_family_rows"]
    ]
    source_ladder_source_rows = [
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
        for row in evidence["source_authority_ladder_source_rows"]
    ]
    source_ladder_lane_rows = [
        [
            row["label"],
            f"{row['evidence_score_pct']:.2f}%",
            f"{row['authority_score_pct']:.2f}%",
            row["present_source_count"],
            row["candidate_source_count"],
            "yes" if row["blocked_or_unsigned"] else "no",
            row["blocking_gap"],
        ]
        for row in evidence["source_authority_ladder_lane_rows"]
    ]
    unit_heatmap_lane_rows = [
        [
            row["lane_label"],
            row["required_unit_count"],
            f"{row['mean_score_pct']:.2f}%",
            row["blocked_unit_count"],
            row["strong_or_review_ready_count"],
            row["top_blocking_gap"],
        ]
        for row in evidence["doctoral_unit_heatmap_lane_summary"]
    ]
    unit_heatmap_queue_rows = [
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
        for row in evidence["doctoral_unit_heatmap_queue"][:20]
    ]
    unit_heatmap_unit_rows = [
        [
            row["ref"],
            row["unit_id"],
            f"{row['unit_authority_score_pct']:.2f}%",
            row["blocking_lane_count"],
            row["required_lane_count"],
            row["packet_review_row_count"],
            row["schema_valid_expected_pct"],
            "; ".join(row["weakest_required_lanes"]),
        ]
        for row in evidence["doctoral_unit_heatmap_units"][:20]
    ]
    priority_dossier_role_rows = [
        [
            row["reviewer_role"],
            row["unit_count"],
            row["critical_unit_count"],
            row["split_lane_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["doctoral_priority_dossier_roles"]
    ]
    priority_dossier_lane_rows = [
        [
            row["lane"],
            row["unit_count"],
            row["critical_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
            row["next_action"],
        ]
        for row in evidence["doctoral_priority_dossier_lanes"]
    ]
    priority_dossier_domain_rows = [
        [
            row["domain"],
            row["unit_count"],
            row["critical_unit_count"],
            row["split_lane_unit_count"],
            row["textual_witness_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["doctoral_priority_dossier_domains"][:20]
    ]
    priority_dossier_family_rows = [
        [
            row["packet_family"],
            row["unit_count"],
            row["critical_unit_count"],
            row["split_lane_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["doctoral_priority_dossier_packet_families"][:20]
    ]
    priority_dossier_unit_rows = [
        [
            row["rank"],
            row["ref"],
            row["dossier_band"],
            f"{row['doctoral_dossier_priority_score']:.2f}",
            row["unit_authority_score_pct"],
            row["blocking_lane_count"],
            "; ".join(row["weakest_required_lanes"]),
            "; ".join(row["required_review_roles"]),
            "; ".join(row["packet_families"][:8]),
            row["next_action"],
        ]
        for row in evidence["doctoral_priority_dossier_units"][:25]
    ]
    defense_exhibit_unit_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['defense_exhibit_score']:.2f}",
            f"{row['unit_authority_score_pct']:.2f}%",
            f"{row['source_authority_gap_score']:.2f}",
            row["source_ladder_stage"],
            row["chief_source_blocker"],
            row["source_approval_count"],
            row["packet_review_row_count"],
            row["completed_review_row_count"],
            row["clean_source_anchored_attempt_count"],
            row["required_review_roles"],
        ]
        for row in evidence["defense_exhibit_unit_rows"][:25]
    ]
    defense_exhibit_dimension_rows = [
        [
            row["label"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["top_ref"],
            f"{row['top_score']:.2f}",
        ]
        for row in evidence["defense_exhibit_dimension_rows"]
    ]
    defense_exhibit_role_rows = [
        [
            row["reviewer_role"],
            row["unit_count"],
            row["critical_unit_count"],
            f"{row['mean_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["defense_exhibit_role_rows"]
    ]
    hebrew_token_defense_token_rows = [
        [
            row["token_rank"],
            row["ref"],
            row["token_id"],
            row["surface"],
            row["lemma"],
            row["strong"],
            row["display_gloss"],
            row["part_of_speech"],
            row["morph_code"],
            f"{row['token_defense_score']:.2f}",
            row["anchor_strength"] or "none",
            row["outside_psalms_count"],
            row["cultural_domain_count"],
            row["missing_enrichment_count"],
            row["token_control_count"],
            "; ".join(row["token_control_flags"][:6]),
        ]
        for row in evidence["hebrew_token_defense_token_rows"][:35]
    ]
    hebrew_token_defense_unit_rows = [
        [
            row["rank"],
            row["ref"],
            row["token_count"],
            f"{row['mean_token_defense_score']:.2f}",
            f"{row['max_token_defense_score']:.2f}",
            row["critical_token_count"],
            row["anchor_token_count"],
            row["cultural_domain_token_count"],
            row["divine_name_token_count"],
            row["missing_semantic_role_token_count"],
            row["missing_referent_token_count"],
            row["top_token_surfaces"],
            row["top_token_glosses"],
        ]
        for row in evidence["hebrew_token_defense_unit_rows"][:20]
    ]
    hebrew_token_defense_control_rows = [
        [
            row["control"],
            row["token_count"],
            f"{row['token_pct']:.2f}%",
            row["top_ref"],
            row["top_token_id"],
            row["top_surface"],
            f"{row['top_score']:.2f}",
        ]
        for row in evidence["hebrew_token_defense_control_rows"]
    ]
    semantic_referent_token_rows = [
        [
            row["rank"],
            row["ref"],
            row["token_id"],
            row["surface"],
            row["lemma"],
            row["strong"],
            row["display_gloss"],
            row["part_of_speech"],
            row["morph_code"],
            f"{row['enrichment_priority_score']:.2f}",
            row["anchor_strength"] or "none",
            row["outside_psalms_count"],
            row["cultural_domain_count"],
            row["missing_enrichment_count"],
            "; ".join(row["enrichment_lanes"][:5]),
            row["recommended_next_action"],
        ]
        for row in evidence["semantic_referent_token_rows"][:35]
    ]
    semantic_referent_unit_rows = [
        [
            row["rank"],
            row["ref"],
            row["token_count"],
            f"{row['max_enrichment_priority_score']:.2f}",
            row["critical_enrichment_token_count"],
            row["suffix_pronoun_token_count"],
            row["verb_token_count"],
            row["anchor_token_count"],
            row["cultural_domain_token_count"],
            row["divine_name_token_count"],
            "; ".join(row["primary_enrichment_lanes"][:5]),
            row["top_token_surfaces"],
        ]
        for row in evidence["semantic_referent_unit_rows"][:20]
    ]
    semantic_referent_lane_rows = [
        [
            row["lane"],
            row["token_count"],
            f"{row['token_pct']:.2f}%",
            row["unit_count"],
            row["critical_token_count"],
            f"{row['mean_enrichment_priority_score']:.2f}",
            row["top_ref"],
            row["top_surface"],
            "; ".join(row["required_review_roles"]),
            row["next_action"],
        ]
        for row in evidence["semantic_referent_lane_rows"]
    ]
    semantic_referent_gap_rows = [
        [
            row["label"],
            row["missing_token_count"],
            f"{row['missing_pct']:.2f}%",
            f"{row['coverage_pct']:.2f}%",
            row["top_ref"],
            row["top_surface"],
            row["authority_effect"],
        ]
        for row in evidence["semantic_referent_gap_rows"]
    ]
    semantic_referent_phase_rows = [
        [
            row["phase_id"],
            row["phase"],
            row["status"],
            row["token_count"],
            row["unit_count"],
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["semantic_referent_phase_rows"]
    ]
    review_signoff_role_rows = [
        [
            row["reviewer_role"],
            row["total_review_row_count"],
            row["packet_review_row_count"],
            row["source_acquisition_review_row_count"],
            row["unit_count"],
            row["packet_family_count"],
            row["status"],
        ]
        for row in evidence["review_signoff_roles"]
    ]
    review_signoff_unit_rows = [
        [
            row["ref"],
            row["unit_id"],
            f"{row['packet_priority_score']:.2f}",
            row["packet_priority_band"],
            row["packet_review_row_count"],
            "; ".join(row["distinct_reviewer_roles"]),
        ]
        for row in evidence["review_signoff_units"][:15]
    ]
    review_signoff_gate_rows = [
        [
            row["gate"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["review_signoff_gates"]
    ]
    authority_path_phase_rows = [
        [
            row["phase_id"],
            row["phase"],
            row["dependency_ids"],
            row["status"],
            f"{row['readiness_pct']:.2f}%",
            row["work_unit_count"],
            row["blocker_ids"],
            row["next_action"],
        ]
        for row in evidence["authority_path_phase_rows"]
    ]
    authority_path_role_rows = [
        [
            row["reviewer_role"],
            row["total_review_row_count"],
            row["critical_packet_review_row_count"],
            row["highest_packet_review_row_count"],
            f"{row['critical_or_highest_pct']:.2f}%",
            row["unit_count"],
            row["status"],
        ]
        for row in evidence["authority_path_role_rows"]
    ]
    authority_path_unit_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['unit_authority_score_pct']:.2f}%",
            f"{row['gap_priority_score']:.2f}",
            row["blocking_lane_count"],
            row["packet_review_row_count"],
            row["weakest_required_lanes"],
            row["next_action"],
        ]
        for row in evidence["authority_path_unit_rows"][:20]
    ]
    authority_path_gate_rows = [
        [
            row["source"],
            row["gate"],
            row["status"],
            f"{row['score_pct']:.2f}%",
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["authority_path_gate_rows"][:40]
    ]
    doctoral_requirement_rows = [
        [
            row["requirement_id"],
            row["requirement"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["blocking_gap"],
        ]
        for row in evidence["doctoral_requirement_rows"]
    ]
    doctoral_blocker_rows = [
        [
            row["blocker_id"],
            row["severity"],
            row["blocker"],
            row["evidence"],
            "; ".join(row["affected_requirement_ids"]),
            row["next_action"],
        ]
        for row in evidence["doctoral_blocker_rows"]
    ]
    doctoral_boundary_rows = [
        [
            row["boundary_id"],
            row["boundary"],
            row["rule"],
            row["authority_effect"],
            row["source_artifact"],
        ]
        for row in evidence["doctoral_source_boundary_rows"]
    ]
    doctoral_priority_unit_rows = [
        [
            row["rank"],
            row["ref"],
            row["unit_id"],
            f"{float(row['packet_priority_score']):.2f}",
            row["packet_priority_band"],
            row["packet_review_row_count"],
            "; ".join(row["required_roles"]),
        ]
        for row in evidence["doctoral_priority_unit_rows"][:15]
    ]
    canonical_domain_rows = [
        [
            row["domain"],
            row["expanded_unit_count"],
            f"{row['avg_content_token_outside_context_pct']:.2f}%",
            row["strong_network_unit_count"],
            row["weak_network_unit_count"],
            f"{row['torah_evidence_unit_pct']:.2f}%",
            f"{row['prophets_evidence_unit_pct']:.2f}%",
            row["review_queue_count"],
        ]
        for row in evidence["canonical_context_domain_network"][:10]
    ]
    canonical_cross_ref_division_rows = [
        [
            row["division_bucket"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            f"{row['mean_priority_score']:.2f}",
        ]
        for row in evidence["canonical_cross_reference_divisions"]
    ]
    canonical_cross_ref_book_rows = [
        [
            row["book"],
            row["division"],
            row["anchor_token_count"],
            row["unit_count"],
            row["outside_occurrence_sum"],
        ]
        for row in evidence["canonical_cross_reference_books"][:20]
    ]
    canonical_cross_ref_domain_rows = [
        [
            row["domain_label"],
            row["unit_count"],
            row["anchor_token_count"],
            row["three_division_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["canonical_cross_reference_domains"]
    ]
    canonical_cross_ref_priority_rows = [
        [
            index + 1,
            row["ref"],
            f"{row['priority_score']:.2f}",
            row["anchor_token_count"],
            row["high_value_anchor_count"],
            row["medium_value_anchor_count"],
            row["low_value_anchor_count"],
            "; ".join(row["domain_labels"][:5]),
            "; ".join(
                f"{anchor['form']} ({anchor['anchor_strength']}, {anchor['outside_psalms_count']})"
                for anchor in row["top_anchor_forms"][:5]
            ),
        ]
        for index, row in enumerate(evidence["canonical_cross_reference_units"][:20])
    ]
    canonical_cross_ref_anchor_rows = [
        [
            row["ref"],
            row["surface"],
            row["normalized"],
            row["display_gloss"],
            row["outside_psalms_count"],
            row["anchor_strength"],
            f"{row['anchor_score']:.2f}",
            "; ".join(row["outside_torah_refs"][:3]),
            "; ".join(row["outside_prophets_refs"][:3]),
            "; ".join(row["outside_writings_refs"][:3]),
        ]
        for row in sorted(
            evidence["canonical_cross_reference_anchors"],
            key=lambda item: float(item["anchor_score"]),
            reverse=True,
        )[:20]
    ]
    canonical_intertext_benchmark_chart_rows: list[dict[str, Any]] = []
    canonical_intertext_benchmark_task_rows: list[list[Any]] = []
    for index, task in enumerate(evidence["canonical_intertext_benchmark_tasks"]):
        context = canonical_intertext_context(task)
        if task["layer"] == "gloss" and len(canonical_intertext_benchmark_chart_rows) < 20:
            canonical_intertext_benchmark_chart_rows.append(
                {
                    "label": f"{task['ref']} {task['layer']}",
                    "value": task["canonical_intertext_priority_score"],
                }
            )
        if index < 30:
            domain_labels = context.get("domain_labels") or task.get("domain_ids", [])
            canonical_intertext_benchmark_task_rows.append(
                [
                    index + 1,
                    task["task_id"],
                    task["ref"],
                    task["layer"],
                    f"{task['canonical_intertext_priority_score']:.2f}",
                    task["anchor_token_count"],
                    task["high_value_anchor_count"],
                    "; ".join(str(label) for label in domain_labels),
                    canonical_anchor_form_labels(context),
                    task["token_count"],
                    fmt_int(task["estimated_payload_chars"]),
                ]
            )
    canonical_intertext_domain_rows = [
        [
            domain,
            count,
            evidence["canonical_intertext_benchmark_cross_exam_domain_counts"].get(domain, 0),
        ]
        for domain, count in sorted(
            evidence["canonical_intertext_benchmark_domain_counts"].items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]
    canonical_intertext_book_rows = [
        [
            book,
            count,
            evidence["canonical_intertext_benchmark_cross_exam_book_counts"].get(book, 0),
        ]
        for book, count in sorted(
            evidence["canonical_intertext_benchmark_book_counts"].items(),
            key=lambda item: item[1],
            reverse=True,
        )[:20]
    ]
    canonical_intertext_packet_domain_rows = [
        {"label": label, "value": count}
        for label, count in sorted(
            evidence["canonical_intertext_benchmark_cross_exam_domain_counts"].items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]
    canonical_intertext_packet_book_rows = [
        {"label": label, "value": count}
        for label, count in sorted(
            evidence["canonical_intertext_benchmark_cross_exam_book_counts"].items(),
            key=lambda item: item[1],
            reverse=True,
        )[:20]
    ]
    canonical_intertext_cross_exam_rows = []
    for packet in evidence["canonical_intertext_benchmark_cross_exam_packets"][:24]:
        context = packet["canonical_intertext_context"]
        top_books = sorted(
            context["outside_book_counts"].items(),
            key=lambda item: item[1],
            reverse=True,
        )[:4]
        canonical_intertext_cross_exam_rows.append(
            [
                packet["packet_id"],
                packet["ref"],
                packet["layer"],
                packet["judge_id"],
                packet["priority"],
                f"{context['score']:.2f}",
                len(packet["probe_questions"]),
                "; ".join(context["domain_labels"]),
                "; ".join(f"{book} ({count})" for book, count in top_books),
            ]
        )
    canonical_intertext_dry_run_rows = [
        [
            row["task_id"],
            row["model_profile_id"],
            "yes" if row["schema_valid"] else "no",
            row["candidate_count"],
            f"{row['mean_alignment_score_0_5']:.2f}",
            f"{row['mean_translation_basis_score_0_5']:.2f}",
            row["source_anchor_issue_count"],
        ]
        for row in evidence["canonical_intertext_benchmark_dry_run_results"]
    ]
    canonical_intertext_review_rows = [
        [
            row["task_id"],
            row["ref"],
            row["layer"],
            row["intensity"],
            row["required_role_count"],
            "; ".join(row["required_roles"]),
        ]
        for row in evidence["canonical_intertext_benchmark_review_plan"][:30]
    ]
    canonical_intertext_smoke_elapsed_rows = [
        {
            "label": row["label"],
            "value": round(float(row.get("elapsed_ms") or 0) / 1000, 2),
        }
        for row in evidence["canonical_intertext_real_smoke_attempt_rows"]
    ]
    canonical_intertext_smoke_anchor_rows = [
        {
            "label": row["model_profile_id"],
            "value": row["source_anchor_issue_count"],
        }
        for row in evidence["canonical_intertext_real_smoke_model_rows"]
    ]
    canonical_intertext_smoke_model_rows = [
        [
            row["model_profile_id"],
            row["attempt_count"],
            row["schema_valid_attempt_count"],
            f"{row['schema_valid_pct']:.2f}%",
            row["source_anchor_issue_count"],
            f"{float(row['mean_elapsed_ms']) / 1000:.2f}s",
            f"{row['mean_alignment_score_0_5']:.2f}",
            f"{row['mean_translation_basis_score_0_5']:.2f}",
        ]
        for row in evidence["canonical_intertext_real_smoke_model_rows"]
    ]
    canonical_intertext_smoke_attempt_rows = [
        [
            row["label"],
            row["model_profile_id"],
            row["task_id"],
            row["schema_valid"],
            row["candidate_count"],
            row["error_count"],
            "; ".join(row["errors"]),
            row["source_anchor_issue_count"],
            f"{float(row.get('elapsed_ms') or 0) / 1000:.2f}s",
            row["candidate_text"],
        ]
        for row in evidence["canonical_intertext_real_smoke_attempt_rows"]
    ]
    reception_signal_smoke_elapsed_rows = [
        {
            "label": row["label"],
            "value": round(float(row.get("elapsed_ms") or 0) / 1000, 2),
        }
        for row in evidence["reception_signal_real_smoke_attempt_rows"]
    ]
    reception_signal_smoke_anchor_rows = [
        {
            "label": row["model_profile_id"],
            "value": row["source_anchor_issue_count"],
        }
        for row in evidence["reception_signal_real_smoke_model_rows"]
    ]
    reception_signal_smoke_model_rows = [
        [
            row["model_profile_id"],
            row["attempt_count"],
            row["schema_valid_attempt_count"],
            row["clean_schema_valid_attempt_count"],
            f"{row['schema_valid_pct']:.2f}%",
            row["source_anchor_issue_count"],
            row["reception_leak_term_count"],
            f"{float(row['mean_elapsed_ms']) / 1000:.2f}s",
            f"{row['mean_alignment_score_0_5']:.2f}",
            f"{row['mean_translation_basis_score_0_5']:.2f}",
        ]
        for row in evidence["reception_signal_real_smoke_model_rows"]
    ]
    reception_signal_smoke_attempt_rows = [
        [
            row["label"],
            row["model_profile_id"],
            row["task_id"],
            row["schema_valid"],
            row["candidate_count"],
            row["error_count"],
            "; ".join(row["errors"]),
            row["source_anchor_issue_count"],
            row["reception_leak_term_count"],
            f"{float(row.get('elapsed_ms') or 0) / 1000:.2f}s",
            row["candidate_text"],
        ]
        for row in evidence["reception_signal_real_smoke_attempt_rows"]
    ]
    reception_frame_rows = [
        [
            row["frame"],
            row["unit_count"],
            row["lane"],
            row["allowed_location"],
        ]
        for row in evidence["reception_boundary_frame_summary"]
    ]
    reception_domain_rows = [
        [
            row["domain"],
            row["unit_count"],
            row["reception_sensitive_count"],
            row["textual_witness_pressure_count"],
            f"{row['avg_boundary_risk_score']:.2f}",
            row["high_boundary_risk_count"],
        ]
        for row in evidence["reception_boundary_domain_rows"][:10]
    ]
    reception_divergence_signal_rows = [
        [
            row["signal_label"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["separation_required_unit_count"],
            f"{row['mean_reception_divergence_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["reception_divergence_signals"]
    ]
    reception_divergence_frame_rows = [
        [
            row["frame"],
            row["lane"],
            row["unit_count"],
            row["separation_required_unit_count"],
            f"{row['mean_reception_divergence_priority_score']:.2f}",
            row["allowed_location"],
        ]
        for row in evidence["reception_divergence_frames"]
    ]
    reception_divergence_domain_rows = [
        [
            row["domain"],
            row["unit_count"],
            row["separation_required_unit_count"],
            row["reception_sensitive_unit_count"],
            row["textual_witness_pressure_unit_count"],
            f"{row['mean_reception_divergence_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in evidence["reception_divergence_domains"]
    ]
    reception_divergence_priority_rows = [
        [
            index + 1,
            row["ref"],
            f"{row['reception_divergence_priority_score']:.2f}",
            row["jewish_christian_separation_required"],
            "; ".join(row["case_family_labels"]),
            "; ".join(row["required_frames"]),
            "; ".join(row["top_anchor_form_labels"]),
            row["source_hebrew"],
        ]
        for index, row in enumerate(evidence["reception_divergence_units"][:20])
    ]
    reception_divergence_boundary_rows = [
        [row["boundary_id"], row["boundary"], row["evidence"], row["next_action"]]
        for row in evidence["reception_divergence_boundaries"]
    ]
    reception_source_packet_unit_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['reception_divergence_priority_score']:.2f}",
            f"{row['boundary_risk_score']:.2f}",
            f"{row['mean_english_witness_divergence_pct']:.2f}%",
            "; ".join(row["signal_ids"][:5]),
            "; ".join(row["case_family_labels"][:5]),
            "; ".join(row["required_lane_ids"]),
        ]
        for row in evidence["reception_source_packet_units"][:20]
    ]
    reception_source_packet_rows = [
        [
            row["packet_id"],
            row["ref"],
            row["lane_label"],
            row["candidate_count"],
            row["reachable_candidate_count"],
            row["best_license_risk"],
            row["status"],
        ]
        for row in evidence["reception_source_packet_rows"][:60]
    ]
    reception_source_packet_source_rows = [
        [
            row["lane_label"],
            row["source_id"],
            row["label"],
            row["license_risk"],
            "yes" if row["reachable"] else "no",
            row["verification_status"],
            row["packet_count"],
        ]
        for row in evidence["reception_source_packet_sources"]
    ]
    reception_source_packet_gate_rows = [
        [
            row["gate"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["reception_source_packet_gates"]
    ]
    interpretive_control_unit_rows = [
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
        for row in evidence["interpretive_control_unit_rows"][:20]
    ]
    interpretive_control_lane_rows = [
        [
            row["lane_label"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["packet_count"],
            row["reachable_candidate_count"],
            f"{row['mean_interpretive_control_score']:.2f}",
            row["top_ref"],
            row["review_status"],
        ]
        for row in evidence["interpretive_control_lane_rows"]
    ]
    interpretive_control_packet_rows = [
        [
            row["ref"],
            row["lane_label"],
            f"{row['priority_score']:.2f}",
            row["candidate_count"],
            row["reachable_candidate_count"],
            row["best_license_risk"],
            row["review_roles"],
            row["status"],
        ]
        for row in evidence["interpretive_control_packet_rows"][:45]
    ]
    interpretive_control_claim_rows = [
        [
            row["control"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["top_ref"],
            row["authority_effect"],
        ]
        for row in evidence["interpretive_control_control_rows"]
    ]
    claim_traceability_unit_rows = [
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
            "; ".join(row["top_blocking_gates"][:6]),
            "; ".join(row["required_claim_families"][:8]),
        ]
        for row in evidence["claim_traceability_unit_rows"][:25]
    ]
    claim_traceability_claim_rows = [
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
        for row in evidence["claim_traceability_claim_rows"][:60]
    ]
    claim_traceability_family_rows = [
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
        for row in evidence["claim_traceability_family_rows"]
    ]
    claim_traceability_gate_rows = [
        [
            row["gate"],
            row["claim_row_count"],
            f"{row['claim_row_pct']:.2f}%",
            row["unit_count"],
            row["top_ref"],
            row["top_family"],
            row["next_action"],
        ]
        for row in evidence["claim_traceability_gate_rows"]
    ]
    translation_accuracy_dimension_rows = [
        [
            row["dimension_id"],
            row["dimension"],
            f"{row['evidence_maturity_pct']:.2f}%",
            f"{row['certification_readiness_pct']:.2f}%",
            row["status"],
            row["primary_metric"],
            row["blocking_gap"],
        ]
        for row in evidence["translation_accuracy_dimension_rows"]
    ]
    translation_accuracy_gate_rows = [
        [
            row["gate_id"],
            row["gate"],
            row["status"],
            row["current_value"],
            row["target_value"],
            row["blocker_effect"],
        ]
        for row in evidence["translation_accuracy_gate_rows"]
    ]
    translation_accuracy_unit_rows = [
        [
            row["rank"],
            row["ref"],
            row["source_authority_gap_score"],
            row["source_authority_readiness_pct"],
            row["chief_blocker"],
            row["packet_review_row_count"],
            "yes" if row["jewish_christian_separation_required"] else "no",
            "yes" if row["textual_witness_pressure"] else "no",
            "yes" if row["ancient_culture_pressure"] else "no",
        ]
        for row in evidence["translation_accuracy_unit_rows"][:15]
    ]
    translation_accuracy_role_rows = [
        [
            row["rank"],
            row["reviewer_role"],
            row["total_review_row_count"],
            row["critical_packet_review_row_count"],
            row["highest_packet_review_row_count"],
            row["status"],
        ]
        for row in evidence["translation_accuracy_role_rows"]
    ]
    critical_unit_decision_unit_rows = [
        [
            index,
            row["ref"],
            f"{row['decision_pressure_score']:.2f}",
            row["decision_pressure_band"],
            f"{row['unit_authority_score_pct']:.2f}%",
            row["blocking_lane_count"],
            row["claim_blocking_gate_count"],
            row["translation_text_allowed_now_count"],
            row["clean_source_anchored_attempt_count"],
            "yes" if row["jewish_christian_separation_required"] else "no",
            row["next_action"],
        ]
        for index, row in enumerate(evidence["critical_unit_decision_unit_rows"][:20], start=1)
    ]
    critical_unit_decision_lane_rows = [
        [
            row["ref"],
            row["lane_label"],
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in evidence["critical_unit_decision_lane_rows"][:120]
    ]
    critical_unit_decision_claim_rows = [
        [
            row["ref"],
            row["family_label"],
            row["admissibility_status"],
            row["allowed_location"],
            "yes" if row["translation_text_allowed_now"] else "no",
            "yes" if row["translation_text_allowed_after_review"] else "no",
            row["blocking_gate_count"],
            "; ".join(row["blocking_gates"][:5]),
            row["evidence_summary"],
        ]
        for row in evidence["critical_unit_decision_claim_rows"][:120]
    ]
    critical_unit_review_execution_wave_rows = [
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
        for row in evidence["critical_unit_review_execution_wave_rows"]
    ]
    critical_unit_review_execution_role_rows = [
        [
            row["reviewer_role"],
            row["wave_id"],
            row["critical_unit_assignment_count"],
            row["total_review_row_count"],
            f"{row['completion_pct']:.2f}%",
            row["blocked_lane_count"],
            row["claim_blocking_gate_count"],
            row["top_ref"],
            row["next_action"],
        ]
        for row in evidence["critical_unit_review_execution_role_rows"]
    ]
    critical_unit_review_execution_gate_rows = [
        [
            row["gate_id"],
            row["gate"],
            row["status"],
            row["current_value"],
            row["target_value"],
            row["blocking_gap"],
            row["next_action"],
        ]
        for row in evidence["critical_unit_review_execution_gate_rows"]
    ]
    critical_unit_review_execution_unit_role_rows = [
        [
            index,
            row["ref"],
            row["reviewer_role"],
            row["wave_id"],
            f"{row['decision_pressure_score']:.2f}",
            row["packet_review_row_count"],
            row["blocked_lane_count"],
            row["claim_blocking_gate_count"],
            row["status"],
        ]
        for index, row in enumerate(
            evidence["critical_unit_review_execution_unit_role_rows"][:150],
            start=1,
        )
    ]
    critical_unit_model_cross_exam_unit_rows = [
        [
            index,
            row["ref"],
            f"{row['decision_pressure_score']:.2f}",
            row["task_count"],
            row["expected_model_result_count"],
            row["submitted_model_result_count"],
            row["missing_model_result_count"],
            row["expected_candidate_output_count"],
            row["cross_exam_execution_row_count"],
            "yes" if row["jewish_christian_separation_required"] else "no",
            row["status"],
        ]
        for index, row in enumerate(
            evidence["critical_unit_model_cross_exam_unit_rows"][:35],
            start=1,
        )
    ]
    critical_unit_model_cross_exam_model_rows = [
        [
            row["short_name"],
            row["model_profile_id"],
            row["local_asset_status"],
            f"{row['doctoral_bakeoff_score_pct']:.2f}",
            row["expected_model_result_count"],
            row["submitted_model_result_count"],
            row["missing_model_result_count"],
            row["schema_valid_result_count"],
            row["source_anchor_issue_count"],
            row["status_band"],
        ]
        for row in evidence["critical_unit_model_cross_exam_model_rows"]
    ]
    critical_unit_model_cross_exam_judge_rows = [
        [
            row["judge_id"],
            row["authority"],
            row["packet_count"],
            row["execution_row_count"],
            row["probe_question_count"],
            "; ".join(row["required_human_roles"]),
            row["status"],
        ]
        for row in evidence["critical_unit_model_cross_exam_judge_rows"]
    ]
    critical_unit_model_cross_exam_task_rows = [
        [
            row["task_id"],
            row["ref"],
            row["layer"],
            row["expected_model_result_count"],
            row["submitted_model_result_count"],
            row["missing_model_result_count"],
            row["cross_exam_execution_row_count"],
            row["status"],
        ]
        for row in evidence["critical_unit_model_cross_exam_task_rows"][:100]
    ]
    critical_unit_model_cross_exam_gate_rows = [
        [
            row["gate_id"],
            row["gate"],
            row["status"],
            row["current_value"],
            row["target_value"],
            row["blocking_gap"],
            row["next_action"],
        ]
        for row in evidence["critical_unit_model_cross_exam_gate_rows"]
    ]
    context_integration_lens_rows = [
        [
            row["label"],
            row["category"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["high_pressure_unit_count"],
            row["top_ref"],
            f"{row['top_integration_pressure_score']:.2f}",
            row["reviewer_role"],
        ]
        for row in evidence["context_integration_lens_rows"]
    ]
    context_integration_priority_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['integration_pressure_score']:.2f}",
            row["integration_pressure_band"],
            row["active_lens_count"],
            "; ".join(row["active_lens_labels"][:8]),
            "; ".join(row["required_review_roles"]),
            row["reception_required_frames"],
        ]
        for row in evidence["context_integration_priority_unit_rows"][:30]
    ]
    context_integration_psalm_rows = [
        [
            row["psalm"],
            row["unit_count"],
            row["high_pressure_unit_count"],
            f"{row['high_pressure_unit_pct']:.2f}%",
            f"{row['mean_active_lens_count']:.2f}",
            row["top_ref"],
            f"{row['top_integration_pressure_score']:.2f}",
            row["dominant_lenses"],
        ]
        for row in evidence["context_integration_psalm_rows"][:30]
    ]
    context_integration_cooccurrence_rows = [
        [
            row["lens_a_label"],
            row["lens_b_label"],
            row["unit_count"],
            f"{row['jaccard_pct']:.2f}%",
        ]
        for row in evidence["context_integration_cooccurrence_rows"][:30]
    ]
    collision_packet_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['integration_pressure_score']:.2f}",
            row["active_lens_count"],
            row["required_decision_count"],
            "; ".join(row["required_review_roles"]),
            "; ".join(row["cultural_domain_labels"][:6]),
            f"{row['witness_divergence_pct']:.2f}%",
            "; ".join(row["reception_required_frames"][:6]),
        ]
        for row in evidence["collision_packet_rows"]
    ]
    collision_lane_rows = [
        [
            row["lane"],
            row["decision_row_count"],
            row["unit_count"],
            row["reviewer_role"],
            row["control"],
        ]
        for row in evidence["collision_lane_rows"]
    ]
    collision_role_rows = [
        [
            row["reviewer_role"],
            row["decision_row_count"],
            row["unit_count"],
            row["status"],
        ]
        for row in evidence["collision_role_rows"]
    ]
    collision_decision_rows = [
        [
            row["ref"],
            row["lane"],
            row["reviewer_role"],
            row["current_data"],
            row["decision_prompt"],
            row["status"],
        ]
        for row in evidence["collision_decision_rows"][:80]
    ]
    collision_benchmark_chart_rows = [
        {
            "label": f"{task['ref']} {task['layer']}",
            "value": task["integration_pressure_score"],
        }
        for task in evidence["collision_benchmark_tasks"]
        if task["layer"] == "gloss"
    ][:20]
    collision_benchmark_task_rows = [
        [
            index + 1,
            task["task_id"],
            task["ref"],
            task["layer"],
            task["integration_pressure_band"],
            f"{task['integration_pressure_score']:.2f}",
            task["active_lens_count"],
            task["required_decision_count"],
            "; ".join(task["required_decision_lanes"]),
            task["token_count"],
            fmt_int(task["estimated_payload_chars"]),
        ]
        for index, task in enumerate(evidence["collision_benchmark_tasks"][:30])
    ]
    collision_benchmark_judge_rows = [
        {"label": label, "value": count}
        for label, count in Counter(
            packet["judge_id"] for packet in evidence["collision_benchmark_cross_exam_packets"]
        ).most_common()
    ]
    collision_benchmark_cross_exam_rows = [
        [
            packet["packet_id"],
            packet["ref"],
            packet["layer"],
            packet["judge_id"],
            packet["priority"],
            len(packet["probe_questions"]),
            "; ".join(packet["context_pressure"]["domains"][:5]),
            "; ".join(packet["required_human_roles"]),
        ]
        for packet in evidence["collision_benchmark_cross_exam_packets"][:24]
    ]
    collision_benchmark_dry_run_rows = [
        [
            row["task_id"],
            row["model_profile_id"],
            "yes" if row["schema_valid"] else "no",
            row["candidate_count"],
            f"{row['mean_alignment_score_0_5']:.2f}",
            f"{row['mean_translation_basis_score_0_5']:.2f}",
            row["source_anchor_issue_count"],
        ]
        for row in evidence["collision_benchmark_dry_run_results"]
    ]
    collision_benchmark_review_rows = [
        [
            row["task_id"],
            row["ref"],
            row["layer"],
            row["intensity"],
            row["required_role_count"],
            "; ".join(row["required_roles"]),
            row["candidate_count"],
        ]
        for row in evidence["collision_benchmark_review_plan"][:26]
    ]
    collision_smoke_model_rows = [
        [
            row["model_profile_id"],
            row["attempt_count"],
            row["schema_valid_attempt_count"],
            row["clean_schema_valid_attempt_count"],
            f"{row['schema_valid_pct']:.2f}%",
            row["source_anchor_issue_count"],
            row["reception_leak_term_count"],
            f"{float(row['mean_elapsed_ms']) / 1000:.2f}s",
            f"{row['mean_alignment_score_0_5']:.2f}",
            f"{row['mean_translation_basis_score_0_5']:.2f}",
        ]
        for row in evidence["collision_real_smoke_model_rows"]
    ]
    collision_smoke_attempt_rows = [
        [
            row["label"],
            row["task_id"],
            row["layer"],
            "yes" if row["schema_valid"] else "no",
            row["candidate_count"],
            row["source_anchor_issue_count"],
            row["reception_leak_term_count"],
            "; ".join(row["errors"]),
            f"{float(row.get('elapsed_ms') or 0) / 1000:.2f}s",
            row["candidate_text"],
        ]
        for row in evidence["collision_real_smoke_attempt_rows"]
    ]
    contextual_real_model_lane_rows = [
        [
            row["lane_label"],
            row["context_focus"],
            row["planned_model_task_count"],
            row["attempt_count"],
            row["schema_valid_attempt_count"],
            row["clean_schema_valid_attempt_count"],
            f"{row['valid_model_task_coverage_pct']:.2f}%",
            row["missing_model_task_count_after_smoke"],
            row["source_anchor_issue_count"],
            row["clean_best_model_profile"],
        ]
        for row in evidence["contextual_real_model_lane_rows"]
    ]
    contextual_real_model_model_rows = [
        [
            row["model_profile_id"],
            row["attempt_count"],
            row["schema_valid_attempt_count"],
            f"{row['schema_valid_pct']:.2f}%",
            row["clean_source_anchored_count"],
            f"{row['clean_source_anchored_pct']:.2f}%",
            row["source_anchor_issue_count"],
            f"{float(row['mean_elapsed_ms']) / 1000:.2f}s",
            "; ".join(row["clean_lanes"]),
            row["evidence_role"],
        ]
        for row in evidence["contextual_real_model_model_rows"]
    ]
    contextual_real_model_model_lane_rows = [
        [
            row["lane_label"],
            row["model_profile_id"],
            row["attempt_count"],
            row["schema_valid_attempt_count"],
            row["clean_source_anchored_count"],
            row["source_anchor_issue_count"],
            f"{float(row['mean_elapsed_ms']) / 1000:.2f}s",
            "; ".join(row["task_refs"]),
        ]
        for row in evidence["contextual_real_model_model_lane_rows"]
    ]
    gap_rows = [[gap["gap"], gap["evidence"]] for gap in dashboard["open_gaps"]]

    # Ruff's formatter rewrites nested dict-access f-strings here into Python
    # 3.12-only quote syntax. The project currently compiles under Python 3.11.
    # fmt: off
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Local Translation Research Portfolio</title>
  <style>
    :root {{
      color-scheme: light;
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
      background: #ffffff;
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
    a {{ color: var(--accent); text-decoration: none; font-weight: 700; }}
    a:hover {{ text-decoration: underline; }}
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
    <h1>AlephTav Local Translation Research Portfolio</h1>
    <p class="lede">
      Integrated status dashboard for local Hebrew-to-English Psalms model
      research. It links the model-selection evidence, corpus profile,
      contextual rubric, whole-Tanakh form profile, seed packets, benchmark
      suite, context/reception routing, cross-examination protocol, runner,
      scorer, and current result audit.
    </p>
    <p class="meta">Generated {esc(dashboard["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Current State</h2>
      {
        metric_cards(
            [
                (
                    "First base",
                    headline["recommended_first_base"].split("/")[-1],
                    f'Mean prior {headline["recommended_first_base_mean"]:.2f}/5.',
                ),
                (
                    "Corpus tokens",
                    fmt_int(headline["token_records"]),
                    (
                        f'{fmt_int(headline["unit_count"])} units across '
                        f'{headline["psalm_count"]} Psalms.'
                    ),
                ),
                (
                    "Expansion plan",
                    fmt_int(headline["benchmark_expansion_unit_count"]),
                    (
                        f'{fmt_int(headline["benchmark_expansion_new_units"])} '
                        "generated candidates need curation."
                    ),
                ),
                (
                    "Context readiness",
                    f'{headline["context_readiness_mean"]:.2f}/5',
                    "Weighted contextual evidence baseline.",
                ),
                (
                    "High pressure",
                    fmt_int(headline["context_high_pressure_units"]),
                    (
                        f'{fmt_int(headline["context_reception_sensitive_units"])} '
                        "units need reception routing."
                    ),
                ),
                (
                    "Witness rows",
                    fmt_int(headline["witness_record_count"]),
                    (
                        f'LXX {headline["witness_lxx_coverage_pct"]:.2f}%; '
                        f'English {headline["witness_english_coverage_pct"]:.2f}%.'
                    ),
                ),
                (
                    "Witness divergence",
                    f'{headline["witness_divergence_mean_pct"]:.2f}%',
                    (
                        f'P90 {headline["witness_divergence_p90_pct"]:.2f}%; '
                        f'{fmt_int(headline["witness_divergence_high_unit_count"])} '
                        "high-divergence units."
                    ),
                ),
                (
                    "Divine names",
                    fmt_int(headline["witness_divergence_divine_name_disagreement_count"]),
                    "English witness rendering disagreements.",
                ),
                (
                    "Divine-title units",
                    fmt_int(headline["divine_name_policy_unit_count"]),
                    (
                        f'{fmt_int(headline["divine_name_policy_token_count"])} '
                        "divine-name/title tokens."
                    ),
                ),
                (
                    "YHWH tokens",
                    fmt_int(headline["divine_name_policy_yhwh_token_count"]),
                    (
                        f'{fmt_int(headline["divine_name_policy_witness_disagreement_count"])} '
                        "title-bearing units with witness disagreement."
                    ),
                ),
                (
                    "Superscriptions",
                    fmt_int(headline["superscription_context_unit_count"]),
                    (
                        f'{fmt_int(headline["superscription_context_token_count"])} '
                        "heading, performance, and context tokens."
                    ),
                ),
                (
                    "Heading notices",
                    fmt_int(headline["superscription_context_historical_notice_count"]),
                    (
                        f'{fmt_int(headline["superscription_context_technical_term_count"])} '
                        "technical terms; top "
                        f'{headline["superscription_context_top_ref"]}.'
                    ),
                ),
                (
                    "Cultural domains",
                    fmt_int(headline["cultural_historical_domain_unit_count"]),
                    (
                        f'{fmt_int(headline["cultural_historical_domain_token_count"])} '
                        "domain-token assignments."
                    ),
                ),
                (
                    "Culture priority",
                    fmt_int(headline["cultural_historical_high_priority_unit_count"]),
                    (
                        f'{fmt_int(headline["cultural_historical_domain_count"])} domains; '
                        f'top {headline["cultural_historical_top_ref"]}.'
                    ),
                ),
                (
                    "Poetic pressure",
                    fmt_int(headline["poetic_rhetorical_high_pressure_unit_count"]),
                    (
                        f'{fmt_int(headline["poetic_rhetorical_volitive_token_count"])} '
                        "volitive tokens measured."
                    ),
                ),
                (
                    "Rhetoric priority",
                    fmt_int(headline["poetic_rhetorical_adjacent_parallelism_proxy_count"]),
                    (
                        "adjacent parallelism-proxy units; top "
                        f'{headline["poetic_rhetorical_top_ref"]}.'
                    ),
                ),
                (
                    "Reception signals",
                    fmt_int(headline["corpus_reception_signal_unit_count"]),
                    (
                        f'{fmt_int(headline["corpus_reception_signal_high_pressure_unit_count"])} '
                        "high-pressure units."
                    ),
                ),
                (
                    "Reception queue",
                    fmt_int(headline["corpus_reception_signal_new_candidate_count"]),
                    (
                        "new high-pressure candidates; top "
                        f'{headline["corpus_reception_signal_top_ref"]}.'
                    ),
                ),
                (
                    "Signal supplement",
                    fmt_int(headline["reception_signal_benchmark_task_count"]),
                    (
                        f'{fmt_int(headline["reception_signal_benchmark_unit_count"])} '
                        "units; "
                        f'{fmt_int(headline["reception_signal_benchmark_planned_runs"])} '
                        "planned model runs."
                    ),
                ),
                (
                    "Signal reviews",
                    fmt_int(headline["reception_signal_benchmark_cross_exam_packets"]),
                    (
                        f'{fmt_int(headline["reception_signal_benchmark_review_human_rows"])} '
                        "human rows; "
                        f'{fmt_int(headline["reception_signal_benchmark_dry_run_valid"])} '
                        "dry-run valid."
                    ),
                ),
                (
                    "Signal real smoke",
                    fmt_int(headline["reception_signal_real_smoke_valid_model_task_count"]),
                    (
                        f"{reception_smoke_coverage:.2f}% "
                        "model-task coverage; "
                        f'{fmt_int(headline["reception_signal_real_smoke_attempt_count"])} '
                        "attempts."
                    ),
                ),
                (
                    "Signal smoke gaps",
                    fmt_int(headline["reception_signal_real_smoke_missing_model_task_count"]),
                    (
                        "missing rows; clean best "
                        f'{headline["reception_signal_real_smoke_clean_best_model"]}.'
                    ),
                ),
                (
                    "Context atlas",
                    fmt_int(headline["atlas_ancient_context_units"]),
                    (
                        f'{fmt_int(headline["atlas_broad_canonical_context_units"])} '
                        "units have broad canonical context."
                    ),
                ),
                (
                    "Atlas covered",
                    f'{headline["contextual_coverage_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["contextual_uncovered_units"])} '
                        "100-unit atlas rows remain uncovered."
                    ),
                ),
                (
                    "Lexeme bridge",
                    f'{headline["lexeme_surface_outside_pct"]:.2f}%',
                    (
                        f'Strong {headline["lexeme_strong_coverage_pct"]:.2f}%; '
                        "whole-Tanakh lemma index missing."
                    ),
                ),
                (
                    "Morph gap",
                    fmt_int(headline["whole_tanakh_non_psalm_morphology_books"]),
                    (
                        "non-Psalm morph books; outside Strong context "
                        f'{headline["whole_tanakh_outside_strong_context_pct"]:.2f}%.'
                    ),
                ),
                (
                    "Canon network",
                    f'{headline["canonical_context_content_token_pct"]:.2f}%',
                    (
                        f'{headline["canonical_context_unit_count"]} expanded units; '
                        f'{headline["canonical_context_review_queue_units"]} '
                        "flagged for review."
                    ),
                ),
                (
                    "Canon refs",
                    fmt_int(headline["canonical_cross_reference_unit_count"]),
                    (
                        f'{fmt_int(headline["canonical_cross_reference_anchor_token_count"])} '
                        "UXLC anchor tokens."
                    ),
                ),
                (
                    "Three divisions",
                    fmt_int(headline["canonical_cross_reference_three_division_unit_count"]),
                    (
                        fmt_int(
                            headline[
                                "canonical_cross_reference_high_value_anchor_unit_count"
                            ]
                        )
                        + " high-value anchor units."
                    ),
                ),
                (
                    "Canon supplement",
                    fmt_int(headline["canonical_intertext_benchmark_task_count"]),
                    (
                        f'{fmt_int(headline["canonical_intertext_benchmark_unit_count"])} '
                        "units; "
                        f'{fmt_int(headline["canonical_intertext_benchmark_planned_runs"])} '
                        "planned model runs."
                    ),
                ),
                (
                    "Canon reviews",
                    fmt_int(headline["canonical_intertext_benchmark_cross_exam_packets"]),
                    (
                        f'{fmt_int(headline["canonical_intertext_benchmark_review_human_rows"])} '
                        "human rows; "
                        f'{fmt_int(headline["canonical_intertext_benchmark_dry_run_valid"])} '
                        "dry-run valid."
                    ),
                ),
                (
                    "Canon real smoke",
                    fmt_int(headline["canonical_intertext_real_smoke_valid_model_task_count"]),
                    (
                        f"{canon_smoke_coverage:.2f}% "
                        "model-task coverage; "
                        f'{fmt_int(headline["canonical_intertext_real_smoke_attempt_count"])} '
                        "attempts."
                    ),
                ),
                (
                    "Canon smoke gaps",
                    fmt_int(headline["canonical_intertext_real_smoke_missing_model_task_count"]),
                    (
                        "missing rows; clean best "
                        f'{headline["canonical_intertext_real_smoke_clean_best_model"]}.'
                    ),
                ),
                (
                    "Reception route",
                    fmt_int(headline["witness_reception_sensitive_units"]),
                    (
                        f'{fmt_int(headline["witness_integrated_reception_units"])} '
                        "integrated units carry reception tags."
                    ),
                ),
                (
                    "Boundary risk",
                    f'{headline["reception_boundary_avg_risk_score"]:.2f}',
                    (
                        f'{headline["reception_boundary_reception_units"]} reception units; '
                        f'{headline["reception_boundary_high_risk_units"]} high risk.'
                    ),
                ),
                (
                    "Reception split",
                    fmt_int(headline["reception_divergence_jewish_christian_unit_count"]),
                    (
                        fmt_int(
                            headline[
                                "reception_divergence_academic_comparison_unit_count"
                            ]
                        )
                        + " also require academic comparison."
                    ),
                ),
                (
                    "Reception top",
                    headline["reception_divergence_top_ref"],
                    f'Score {headline["reception_divergence_top_score"]:.2f}.',
                ),
                (
                    "Claim matrix",
                    fmt_int(headline["claim_matrix_high_risk_units"]),
                    (
                        f'{fmt_int(headline["claim_matrix_unit_count"])} units; '
                        f'{fmt_int(headline["claim_matrix_jewish_christian_units"])} '
                        "need Jewish/Christian separation."
                    ),
                ),
                (
                    "Claim authority",
                    fmt_int(headline["claim_traceability_translation_text_allowed_now_count"]),
                    (
                        "currently text-allowed; "
                        f'{fmt_int(headline["claim_traceability_allowed_after_review_count"])} '
                        "could be text-allowed after review."
                    ),
                ),
                (
                    "Context matrix",
                    fmt_int(headline["context_integration_high_pressure_unit_count"]),
                    (
                        f'{headline["context_integration_high_pressure_unit_pct"]:.2f}% '
                        "high-pressure across "
                        f'{fmt_int(headline["context_integration_lens_count"])} lenses.'
                    ),
                ),
                (
                    "Context collisions",
                    fmt_int(headline["context_integration_doctoral_collision_unit_count"]),
                    (
                        f'{fmt_int(headline["context_integration_multi_lens_unit_count"])} '
                        "units carry six or more lenses."
                    ),
                ),
                (
                    "Context top",
                    headline["context_integration_top_ref"],
                    f'Score {headline["context_integration_top_score"]:.2f}.',
                ),
                (
                    "Collision packets",
                    fmt_int(headline["collision_packet_count"]),
                    (
                        f'{fmt_int(headline["collision_decision_row_count"])} '
                        "pending decision rows."
                    ),
                ),
                (
                    "Collision lanes",
                    fmt_int(headline["collision_lane_count"]),
                    (
                        f'{fmt_int(headline["collision_reviewer_role_count"])} '
                        "reviewer roles required."
                    ),
                ),
                (
                    "Collision top",
                    headline["collision_top_ref"],
                    f'Score {headline["collision_top_score"]:.2f}.',
                ),
                (
                    "Collision tasks",
                    fmt_int(headline["collision_benchmark_task_count"]),
                    (
                        f'{fmt_int(headline["collision_benchmark_unit_count"])} units; '
                        f'{fmt_int(headline["collision_benchmark_planned_runs"])} '
                        "planned runs."
                    ),
                ),
                (
                    "Collision task mix",
                    fmt_int(headline["collision_benchmark_jewish_christian_tasks"]),
                    (
                        "J/C tasks; "
                        f'{fmt_int(headline["collision_benchmark_divine_name_tasks"])} '
                        "divine-name tasks."
                    ),
                ),
                (
                    "Collision smoke",
                    fmt_int(headline["collision_real_smoke_attempt_count"]),
                    (
                        f'{fmt_int(headline["collision_real_smoke_schema_valid_attempt_count"])} '
                        "schema-valid attempts across "
                        f'{fmt_int(headline["collision_real_smoke_model_count"])} models.'
                    ),
                ),
                (
                    "Collision clean",
                    f"{collision_smoke_clean_pct:.2f}%",
                    (
                        f'{fmt_int(headline["collision_real_smoke_clean_attempt_count"])} '
                        "clean source-anchored attempts; "
                        f'{fmt_int(headline["collision_real_smoke_source_anchor_issue_count"])} '
                        "anchor issues."
                    ),
                ),
                (
                    "Collision gaps",
                    fmt_int(headline["collision_real_smoke_missing_model_task_count"]),
                    (
                        "planned rows missing; clean best "
                        f'{headline["collision_real_smoke_clean_best_model"]}.'
                    ),
                ),
                (
                    "Context real matrix",
                    fmt_int(headline["contextual_real_model_attempt_count"]),
                    (
                        f'{fmt_int(headline["contextual_real_model_lane_count"])} '
                        "context lanes with measured local rows."
                    ),
                ),
                (
                    "Context clean",
                    f'{headline["contextual_real_model_clean_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["contextual_real_model_clean_count"])} '
                        "clean source-anchored rows; "
                        f'{fmt_int(headline["contextual_real_model_anchor_issue_count"])} '
                        "anchor issues."
                    ),
                ),
                (
                    "Context coverage",
                    f'{headline["contextual_real_model_coverage_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["contextual_real_model_valid_count"])} of '
                        f'{fmt_int(headline["contextual_real_model_planned_count"])} '
                        "planned contextual model-task rows."
                    ),
                ),
                (
                    "Context best",
                    headline["contextual_real_model_best_clean_model"],
                    f'{fmt_int(headline["contextual_real_model_missing_count"])} rows missing.',
                ),
                (
                    "Textual cover",
                    f'{headline["contextual_textual_coverage_pct"]:.2f}%',
                    (
                        f'Next {headline["contextual_top_next_unit"]} at '
                        f'{headline["contextual_top_next_unit_gap_score"]:.2f}.'
                    ),
                ),
                (
                    "Priority stack",
                    fmt_int(headline["atlas_high_priority_review_units"]),
                    (
                        f'Top unit {headline["atlas_top_priority_unit"]} '
                        f'at {headline["atlas_top_priority_score"]:.2f}.'
                    ),
                ),
                (
                    "Dossiers",
                    fmt_int(headline["priority_dossier_count"]),
                    (
                        f'{fmt_int(headline["priority_dossier_token_count"])} '
                        "source tokens in reviewer packets."
                    ),
                ),
                (
                    "Dossier gaps",
                    fmt_int(headline["priority_dossier_task_gap_count"]),
                    (
                        f'{fmt_int(headline["priority_dossier_cross_exam_gap_count"])} '
                        "also lack cross-exam packets."
                    ),
                ),
                (
                    "Supplement tasks",
                    fmt_int(headline["priority_supplement_task_count"]),
                    (
                        f'{fmt_int(headline["priority_supplement_closed_gaps"])} '
                        "dossier gaps closed."
                    ),
                ),
                (
                    "Supp. cross-exam",
                    fmt_int(headline["priority_supplement_cross_exam_packets"]),
                    (f'{fmt_int(headline["priority_supplement_cross_exam_rows"])} execution rows.'),
                ),
                (
                    "Integrated tasks",
                    fmt_int(headline["integrated_task_count"]),
                    (
                        f'{fmt_int(headline["integrated_unit_count"])} units; '
                        f'{fmt_int(headline["integrated_planned_runs"])} planned runs.'
                    ),
                ),
                (
                    "Integrated exam",
                    fmt_int(headline["integrated_cross_exam_packets"]),
                    (f'{fmt_int(headline["integrated_cross_exam_rows"])} execution rows.'),
                ),
                (
                    "Integrated real",
                    fmt_int(headline["integrated_real_submitted_results"]),
                    (
                        f'{fmt_int(headline["integrated_real_missing_results"])} '
                        "model-task rows still missing."
                    ),
                ),
                (
                    "Integrated signoff",
                    fmt_int(headline["integrated_review_human_rows"]),
                    (
                        f'{fmt_int(headline["integrated_review_model_cross_exam_rows"])} '
                        "advisory model rows."
                    ),
                ),
                (
                    "Gap supplement",
                    fmt_int(headline["contextual_gap_task_count"]),
                    (
                        f'{fmt_int(headline["contextual_gap_unit_count"])} units; '
                        f'{headline["contextual_gap_projected_coverage_pct"]:.2f}% '
                        "projected atlas coverage."
                    ),
                ),
                (
                    "Gap exam",
                    fmt_int(headline["contextual_gap_cross_exam_packets"]),
                    (
                        f'{fmt_int(headline["contextual_gap_cross_exam_rows"])} rows; '
                        f'{fmt_int(headline["contextual_gap_review_human_rows"])} '
                        "human review rows."
                    ),
                ),
                (
                    "Expanded tasks",
                    fmt_int(headline["contextual_expanded_task_count"]),
                    (
                        f'{fmt_int(headline["contextual_expanded_unit_count"])} units; '
                        f'{fmt_int(headline["contextual_expanded_planned_runs"])} '
                        "planned runs."
                    ),
                ),
                (
                    "Expanded real",
                    fmt_int(headline["contextual_expanded_real_submitted_results"]),
                    (
                        f'{fmt_int(headline["contextual_expanded_real_schema_valid_results"])} '
                        "schema-valid; "
                        f'{fmt_int(headline["contextual_expanded_real_missing_results"])} '
                        "missing."
                    ),
                ),
                (
                    "Expanded exam",
                    fmt_int(headline["contextual_expanded_cross_exam_packets"]),
                    (
                        f'{fmt_int(headline["contextual_expanded_cross_exam_rows"])} rows; '
                        f'{fmt_int(headline["contextual_expanded_review_human_rows"])} '
                        "human review rows."
                    ),
                ),
                (
                    "Layer pairs",
                    fmt_int(headline["layer_consistency_paired_count"]),
                    (
                        f'{fmt_int(headline["layer_consistency_schema_valid_pairs"])} '
                        "schema-valid paired gloss/literal outputs."
                    ),
                ),
                (
                    "Layer overlap",
                    f'{headline["layer_consistency_mean_word_jaccard_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["layer_consistency_exact_duplicate_pairs"])} '
                        "exact duplicates; "
                        f'{fmt_int(headline["layer_consistency_weak_differentiation_pairs"])} '
                        "weak differentiation pairs."
                    ),
                ),
                (
                    "Divine names",
                    fmt_int(headline["layer_consistency_divine_name_pairs"]),
                    (
                        f'{fmt_int(headline["layer_consistency_divine_name_inconsistent_pairs"])} '
                        "paired outputs differ in visible divine-name rendering."
                    ),
                ),
                (
                    "Layer actions",
                    fmt_int(headline["layer_remediation_action_count"]),
                    (
                        f'{fmt_int(headline["layer_remediation_retry_task_count"])} '
                        "retry tasks; runner contracts "
                        + (
                            "present"
                            if headline["layer_remediation_runner_contract_ready"]
                            else "missing"
                        )
                        + "."
                    ),
                ),
                (
                    "Layer retries",
                    fmt_int(headline["layer_remediation_retry_pair_count"]),
                    (
                        f'Top retry {headline["layer_remediation_top_retry_ref"]}; '
                        f'{fmt_int(headline["layer_remediation_critical_action_count"])} '
                        "critical action."
                    ),
                ),
                (
                    "Layer experiment",
                    headline["layer_experiment_best_attempt"],
                    (
                        f'{headline["layer_experiment_best_schema_valid_pct"]:.2f}% '
                        "schema-valid; "
                        f'{fmt_int(headline["layer_experiment_best_exact_duplicates"])} '
                        "exact duplicates."
                    ),
                ),
                (
                    "Experiment gates",
                    fmt_int(headline["layer_experiment_failed_gate_count"]),
                    (
                        "Failed: "
                        + (
                            ", ".join(headline["layer_experiment_failed_gates"])
                            if headline["layer_experiment_failed_gates"]
                            else "none"
                        )
                        + "."
                    ),
                ),
                (
                    "Authority score",
                    f'{headline["authority_readiness_score_pct"]:.2f}%',
                    (f'{fmt_int(headline["authority_hard_blocker_count"])} hard blockers remain.'),
                ),
                (
                    "Source authority",
                    f'{headline["source_maturity_mean_authority_score_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["source_maturity_blocked_authority_lane_count"])} '
                        "authority-blocked source lanes."
                    ),
                ),
                (
                    "Source evidence",
                    f'{headline["source_maturity_mean_evidence_score_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["source_maturity_strong_evidence_lane_count"])} '
                        "strong evidence lanes."
                    ),
                ),
                (
                    "Packet load",
                    fmt_int(headline["contextual_source_packet_assignment_count"]),
                    (
                        f'{headline["contextual_source_packet_avg_families"]:.2f} '
                        "source families per expanded unit."
                    ),
                ),
                (
                    "Packet blockers",
                    fmt_int(headline["contextual_source_packet_blocked_families"]),
                    (
                        f'{fmt_int(headline["contextual_source_packet_blocked_gates"])} '
                        "blocked packet gates."
                    ),
                ),
                (
                    "Packet top unit",
                    headline["contextual_source_packet_top_ref"],
                    f'Score {headline["contextual_source_packet_top_score"]:.2f}.',
                ),
                (
                    "Dossier queue",
                    fmt_int(headline["priority_dossier_atlas_unit_count"]),
                    (
                        f'{fmt_int(headline["priority_dossier_atlas_critical_unit_count"])} '
                        "critical integrated review units."
                    ),
                ),
                (
                    "Dossier split",
                    fmt_int(headline["priority_dossier_atlas_jewish_christian_unit_count"]),
                    (
                        f'{fmt_int(headline["priority_dossier_atlas_textual_witness_unit_count"])} '
                        "also carry textual-witness pressure."
                    ),
                ),
                (
                    "Dossier top",
                    headline["priority_dossier_atlas_top_ref"],
                    f'Score {headline["priority_dossier_atlas_top_score"]:.2f}.',
                ),
                (
                    "Source candidates",
                    fmt_int(headline["source_acquisition_candidate_count"]),
                    (
                        f'{fmt_int(headline["source_acquisition_machine_readable_count"])} '
                        "machine-readable candidates."
                    ),
                ),
                (
                    "License risk",
                    (
                        f'{headline["source_acquisition_low_license_risk_count"]}/'
                        f'{headline["source_acquisition_candidate_count"]}'
                    ),
                    (
                        f'{fmt_int(headline["source_acquisition_high_license_risk_count"])} '
                        "high-risk plus "
                        f'{fmt_int(headline["source_acquisition_per_text_license_count"])} '
                        "per-text candidate."
                    ),
                ),
                (
                    "Top source",
                    headline["source_acquisition_top_candidate"],
                    f'Score {headline["source_acquisition_top_score"]:.2f}.',
                ),
                (
                    "Morph candidates",
                    fmt_int(headline["morphology_acquisition_candidate_count"]),
                    (
                        f'{fmt_int(headline["morphology_acquisition_low_license_risk_count"])} '
                        "low-license-risk; first import "
                        f'{headline["morphology_acquisition_recommended_first_import"]}.'
                    ),
                ),
                (
                    "Morph gates",
                    (
                        f'{headline["morphology_acquisition_blocked_gate_count"]}/'
                        f'{headline["morphology_acquisition_pilot_partial_gate_count"]}/'
                        f'{headline["morphology_acquisition_not_started_gate_count"]}'
                    ),
                    "Blocked/pilot-partial/not-started morphology acquisition gates.",
                ),
                (
                    "Morph coverage",
                    (
                        f'{headline["morphology_acquisition_local_non_psalm_book_count"]}/'
                        f'{headline["morphology_acquisition_target_non_psalm_book_count"]}'
                    ),
                    "Non-Psalm books with local Hebrew morphology.",
                ),
                (
                    "OSHB pilot",
                    f'{headline["oshb_alignment_pilot_mean_sequence_similarity_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["oshb_alignment_pilot_mapped_non_psalm_book_count"])} '
                        "non-Psalm books mapped; not source-approved."
                    ),
                ),
                (
                    "OSHB exact verses",
                    f'{headline["oshb_alignment_pilot_exact_sequence_match_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["oshb_alignment_pilot_mismatch_row_count"])} '
                        "mismatch verses require review."
                    ),
                ),
                (
                    "OSHB exceptions",
                    fmt_int(headline["oshb_exception_review_mismatch_verse_count"]),
                    (
                        f'{fmt_int(headline[
                            "oshb_exception_review_token_count_exception_verse_count"
                        ])} '
                        "token-count exceptions."
                    ),
                ),
                (
                    "OSHB review rows",
                    fmt_int(headline["oshb_exception_review_review_row_count"]),
                    (
                        f'{fmt_int(headline[
                            "oshb_exception_review_unexported_exception_row_count"
                        ])} '
                        "rows remain unexported."
                    ),
                ),
                (
                    "OSHB causes",
                    fmt_int(headline["oshb_exception_taxonomy_cause_count"]),
                    (
                        f'{fmt_int(headline["oshb_exception_taxonomy_review_batch_count"])} '
                        "review batches queued."
                    ),
                ),
                (
                    "OSHB segmentation",
                    f'{headline["oshb_exception_taxonomy_segmentation_marker_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["oshb_exception_taxonomy_top_cause_row_count"])} '
                        "rows in top cause."
                    ),
                ),
                (
                    "OSHB rule-routing",
                    f'{headline["oshb_mapping_rule_simulation_candidate_rule_reduction_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline[
                            "oshb_mapping_rule_simulation_rule_candidate_after_review_count"
                        ])} '
                        "high-confidence rows; candidate only."
                    ),
                ),
                (
                    "OSHB residual",
                    fmt_int(headline["oshb_mapping_rule_simulation_manual_residual_row_count"]),
                    (
                        f'{fmt_int(headline[
                            "oshb_mapping_rule_simulation_targeted_rule_review_count"
                        ])} '
                        "targeted-rule review rows."
                    ),
                ),
                (
                    "Morph unlock units",
                    fmt_int(headline["morph_unlock_unlockable_units"]),
                    (
                        f'{headline[
                            "morph_unlock_projected_review_ready_score_pct"
                        ]:.2f}% '
                        "projected review-ready lane score."
                    ),
                ),
                (
                    "Morph unlock rules",
                    f'{headline["morph_unlock_rule_reduction_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["morph_unlock_high_confidence_rule_rows"])} '
                        "high-confidence rows; projected only."
                    ),
                ),
                (
                    "Morph unlock residual",
                    fmt_int(headline["morph_unlock_manual_residual_rows"]),
                    (
                        f'{fmt_int(headline["morph_unlock_exception_rows"])} '
                        "exception rows; top book "
                        f'{headline["morph_unlock_top_exception_book"]}.'
                    ),
                ),
                (
                    "Bibliography",
                    fmt_int(headline["bibliography_source_count"]),
                    (
                        f'{fmt_int(headline["bibliography_local_manifest_count"])} '
                        "local manifests."
                    ),
                ),
                (
                    "Bibliography candidates",
                    fmt_int(headline["bibliography_candidate_count"]),
                    (
                        f'{fmt_int(headline["bibliography_machine_readable_candidate_count"])} '
                        "machine-readable."
                    ),
                ),
                (
                    "Bibliography gaps",
                    fmt_int(headline["bibliography_gap_count"]),
                    (
                        f'{fmt_int(headline["bibliography_critical_gap_count"])} '
                        "critical gaps."
                    ),
                ),
                (
                    "Source URLs",
                    f'{headline["source_verification_reachable_url_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["source_verification_reachable_url_count"])} '
                        "reachable official URLs."
                    ),
                ),
                (
                    "Verification gaps",
                    fmt_int(headline["source_verification_gap_count"]),
                    (
                        f'{fmt_int(headline["source_verification_license_term_detected_count"])} '
                        "license/provenance term detections."
                    ),
                ),
                (
                    "Source approvals",
                    fmt_int(headline["source_verification_source_approval_count"]),
                    "Live verification is not source approval.",
                ),
                (
                    "Unit heatmap",
                    f'{headline["unit_heatmap_mean_score_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["unit_heatmap_unit_count"])} '
                        "units scored."
                    ),
                ),
                (
                    "Blocked units",
                    fmt_int(headline["unit_heatmap_blocked_unit_count"]),
                    (
                        f'{headline["unit_heatmap_blocked_unit_pct"]:.2f}% '
                        "of heatmap units."
                    ),
                ),
                (
                    "Top unit gap",
                    headline["unit_heatmap_top_gap_ref"],
                    f'Score {headline["unit_heatmap_top_gap_score_pct"]:.2f}%.',
                ),
                (
                    "Review workbook",
                    fmt_int(headline["review_signoff_workbook_total_rows"]),
                    (
                        f'{fmt_int(headline["review_signoff_workbook_packet_rows"])} '
                        "packet rows."
                    ),
                ),
                (
                    "Review complete",
                    f'{headline["review_signoff_workbook_completion_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["review_signoff_workbook_completed_rows"])} '
                        "completed rows."
                    ),
                ),
                (
                    "Review roles",
                    fmt_int(headline["review_signoff_workbook_role_count"]),
                    (
                        f'{fmt_int(headline["review_signoff_workbook_blocked_gates"])} '
                        "signoff gates blocked."
                    ),
                ),
                (
                    "Doctoral synthesis",
                    f'{headline["doctoral_synthesis_score_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["doctoral_synthesis_requirement_count"])} '
                        "requirements scored."
                    ),
                ),
                (
                    "Synthesis blockers",
                    fmt_int(headline["doctoral_synthesis_blocker_count"]),
                    (
                        f'{fmt_int(headline["doctoral_synthesis_critical_blocker_count"])} '
                        "critical blockers."
                    ),
                ),
                (
                    "Source boundaries",
                    fmt_int(headline["doctoral_synthesis_source_boundary_count"]),
                    (
                        "Current local base: "
                        f'{headline["doctoral_synthesis_recommended_local_base"]}.'
                    ),
                ),
                (
                    "Critical path",
                    (
                        f'{headline["authority_path_blocked_phase_count"]}/'
                        f'{headline["authority_path_phase_count"]}'
                    ),
                    (
                        f'{fmt_int(headline["authority_path_blocked_gate_count"])} '
                        "blocked gates."
                    ),
                ),
                (
                    "Path review rows",
                    fmt_int(headline["authority_path_review_rows"]),
                    (
                        f'{fmt_int(headline["authority_path_completed_review_rows"])} '
                        "completed."
                    ),
                ),
                (
                    "Top review load",
                    headline["authority_path_top_reviewer_role"],
                    (
                        f'{fmt_int(headline["authority_path_top_reviewer_role_rows"])} '
                        "rows."
                    ),
                ),
                (
                    "Path source approvals",
                    fmt_int(headline["authority_path_source_approval_count"]),
                    f'Top unit gap: {headline["authority_path_top_gap_ref"]}.',
                ),
                (
                    "Weakest domain",
                    headline["authority_lowest_projected_domain"],
                    (
                        f'{headline["authority_lowest_projected_domain_coverage_pct"]:.2f}% '
                        "projected expanded coverage."
                    ),
                ),
                (
                    "Cross-exam",
                    fmt_int(headline["cross_exam_packet_count"]),
                    (
                        f'{fmt_int(headline["cross_exam_execution_rows"])} '
                        "model/candidate/judge rows."
                    ),
                ),
                (
                    "Runtime gates",
                    (f'{headline["runtime_gate_pass_count"]}/{headline["runtime_gate_count"]}'),
                    f'Max detected VRAM {headline["runtime_max_vram_gb"]:.2f} GB.',
                ),
                (
                    "Local assets",
                    (
                        f'{headline["asset_recommended_local_count"]}/'
                        f'{headline["asset_recommended_model_count"]}'
                    ),
                    (
                        f'{fmt_int(headline["asset_ready_profile_count"])} '
                        "profiles runnable from WSL."
                    ),
                ),
                (
                    "Selection ready",
                    (
                        f'{headline["selection_ready_local_candidate_count"]}/'
                        f'{headline["selection_candidate_count"]}'
                    ),
                    f'Best runnable: {headline["selection_best_runnable_candidate"]}.',
                ),
                (
                    "Gemma probe",
                    f'{headline["selection_gemma4_26b_schema_valid_pct"]:.2f}%',
                    ("Gemma 4 26B measured schema-valid rate before prompt repair."),
                ),
                (
                    "Hebrew specialist",
                    "DictaLM",
                    (
                        f"Best public specialist target: "
                        f'{headline["selection_best_public_hebrew_specialist"]}.'
                    ),
                ),
                (
                    "Bakeoff baseline",
                    headline["local_bakeoff_best_current_baseline"],
                    (
                        f'{headline["local_bakeoff_best_current_score_pct"]:.2f}% '
                        "doctoral bakeoff score."
                    ),
                ),
                (
                    "Trainable target",
                    headline["local_bakeoff_best_trainable_base"],
                    "Best target after exact local asset intake.",
                ),
                (
                    "Training certification",
                    headline["model_training_certification_status"],
                    (
                        f'{fmt_int(headline["model_training_certification_candidate_count"])} '
                        "candidates; "
                        f'{fmt_int(headline["model_training_certification_public_fit_count"])} '
                        "public 3090-fit rows."
                    ),
                ),
                (
                    "Frontier intake",
                    headline["model_training_certification_frontier_intake"],
                    (
                        f'{headline["model_training_certification_context_coverage_pct"]:.2f}% '
                        "measured contextual coverage."
                    ),
                ),
                (
                    "Bakeoff coverage",
                    f'{headline["local_bakeoff_contextual_coverage_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["local_bakeoff_contextual_attempt_count"])} '
                        "contextual attempts; "
                        f'{fmt_int(headline[
                            "local_bakeoff_contextual_source_anchor_issues"
                        ])} '
                        "anchor issues."
                    ),
                ),
                (
                    "Schema-valid",
                    (
                        f'{headline["structured_schema_valid_count"]}/'
                        f'{headline["structured_attempt_count"]}'
                    ),
                    f'{headline["structured_schema_valid_pct"]:.2f}% local tuning attempts.',
                ),
                (
                    "Smoke valid",
                    (
                        f'{headline["smoke_schema_valid_results"]}/'
                        f'{headline["smoke_submitted_results"]}'
                    ),
                    (
                        f'{headline["smoke_schema_valid_pct"]:.2f}% real rows; '
                        f'{headline["smoke_source_anchor_issues"]} anchor issues.'
                    ),
                ),
                (
                    "Real results",
                    fmt_int(headline["submitted_real_results"]),
                    (f'{fmt_int(headline["missing_real_results"])} model-task rows still missing.'),
                ),
            ]
        )
    }
      <div class="warning">
        The system is now benchmark-ready, not authority-ready. Real local model
        runs and human reviewer signoff are still required before any model can
        be treated as a source of approved translation proposals.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            dashboard["pipeline"],
            label_key="stage",
            value_key="completion_pct",
            aria_label="Research pipeline completion",
            color="#2f6f73",
            limit=30,
        )
    }</div>
      {table(["Stage", "Status", "Completion", "Evidence"], pipeline_rows)}
    </section>

    <section>
      <h2>Local Model Doctoral Bakeoff Matrix</h2>
      <div class="warning">
        This matrix ranks local-model candidates for next bakeoff action only.
        It does not approve a model, authorize generated translation wording, or
        replace source approval, whole-Tanakh morphology, source-anchor checks,
        layer differentiation, human review, or release authority.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["local_bakeoff_visual_data"]["candidate_score_rows"],
            label_key="label",
            value_key="value",
            aria_label="Local model doctoral bakeoff scores",
            color="#2f6f73",
            limit=10,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["local_bakeoff_visual_data"]["clean_source_anchor_rows"],
            label_key="label",
            value_key="value",
            aria_label="Local model clean source-anchored contextual rows",
            color="#8a6426",
            limit=10,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["local_bakeoff_visual_data"]["gate_score_rows"],
            label_key="label",
            value_key="value",
            aria_label="Local model doctoral bakeoff gate scores",
            color="#9b3d3d",
            limit=12,
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Model",
                "Role",
                "Score",
                "Band",
                "Asset",
                "Schema",
                "Clean Anchors",
                "Anchor Issues",
                "Hebrew",
                "Action",
            ],
            local_bakeoff_candidate_rows,
        )
    }
      {table(["Gate", "Status", "Score", "Evidence", "Next Action"], local_bakeoff_gate_rows)}
      {
        table(
            ["Phase", "Label", "Entry", "Exit", "Models", "Boundary"],
            local_bakeoff_phase_rows,
        )
    }
    </section>

    <section>
      <h2>Model Training Certification Roadmap</h2>
      <div class="warning">
        This roadmap ranks local-model training and certification work only. It
        does not approve a model, authorize training data, approve source use,
        replace human review, or authorize canonical Hebrew-to-English wording.
      </div>
      {
        metric_cards(
            [
                (
                    "Candidates",
                    fmt_int(headline["model_training_certification_candidate_count"]),
                    (
                        fmt_int(headline["model_training_certification_public_fit_count"])
                        + " public 3090-fit rows."
                    ),
                ),
                (
                    "Certification",
                    headline["model_training_certification_status"],
                    "Current model authority state.",
                ),
                (
                    "Text authority",
                    fmt_int(headline["model_training_certification_claim_text_now"]),
                    "Claim rows currently allowed in translation text.",
                ),
                (
                    "Frontier intake",
                    headline["model_training_certification_frontier_intake"],
                    "Next 3090-class MoE challenger to intake.",
                ),
                (
                    "Clean anchors",
                    f'{headline["model_training_certification_clean_anchor_pct"]:.2f}%',
                    "Clean source-anchored contextual attempts.",
                ),
                (
                    "Projected review",
                    fmt_int(headline["model_training_certification_projected_review_rows"]),
                    "Projected model-human review rows.",
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["model_training_certification_visual_data"]["candidate_readiness_rows"],
            label_key="label",
            value_key="value",
            aria_label="Model training certification candidate readiness",
            color="#2f6f73",
            limit=12,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["model_training_certification_visual_data"]["gate_score_rows"],
            label_key="label",
            value_key="value",
            aria_label="Model training certification gate scores",
            color="#9b3d3d",
            limit=12,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["model_training_certification_visual_data"]["phase_readiness_rows"],
            label_key="label",
            value_key="value",
            aria_label="Model training certification phase readiness",
            color="#8a6426",
            limit=12,
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Model",
                "Role",
                "Local Asset",
                "3090 Fit",
                "Readiness",
                "Certification",
                "Action",
            ],
            model_training_certification_candidate_rows,
        )
    }
      {
        table(
            ["Gate", "Status", "Score", "Blocks", "Evidence", "Next Action"],
            model_training_certification_gate_rows,
        )
    }
      {
        table(
            ["Phase", "Label", "Status", "Readiness", "Evidence", "Exit", "Next Action"],
            model_training_certification_phase_rows,
        )
    }
      {
        table(
            [
                "Model",
                "Role",
                "Params B",
                "Active B",
                "Context",
                "Q4 GB",
                "QLoRA GB",
                "Fit",
                "Sources",
            ],
            model_training_certification_source_rows,
        )
    }
    </section>

    <section>
      <h2>Doctoral Context Integration Matrix</h2>
      <div class="warning">
        This matrix joins unit-level evidence across broader-canon anchors,
        cultural and historical domains, textual witnesses, divine-name policy,
        superscription context, poetic/rhetorical pressure, reception, and
        Jewish/Christian separation. It is reviewer routing evidence only.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["context_integration_visual_data"]["lens_coverage_rows"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral context integration lens coverage",
            color="#2f6f73",
            limit=18,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["context_integration_visual_data"]["top_unit_pressure_rows"],
            label_key="label",
            value_key="value",
            aria_label="Top integrated context pressure units",
            color="#7c5b2f",
            limit=20,
        )
    }</div>
      {
        table(
            [
                "Lens",
                "Category",
                "Units",
                "Pct",
                "High-Pressure Units",
                "Top Ref",
                "Top Score",
                "Reviewer Roles",
            ],
            context_integration_lens_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Score",
                "Band",
                "Lenses",
                "Lens Labels",
                "Reviewer Roles",
                "Reception Frames",
            ],
            context_integration_priority_rows,
        )
    }
      {
        table(
            [
                "Psalm",
                "Units",
                "High-Pressure",
                "High-Pressure Pct",
                "Mean Lens Count",
                "Top Ref",
                "Top Score",
                "Dominant Lenses",
            ],
            context_integration_psalm_rows,
        )
    }
      {
        table(
            ["Lens A", "Lens B", "Units", "Jaccard"],
            context_integration_cooccurrence_rows,
        )
    }
    </section>

    <section>
      <h2>Doctoral Collision Review Packets</h2>
      <div class="warning">
        These packets turn the highest cross-lens context collisions into
        pending reviewer decisions. They are workload scaffolding, not source
        approval, interpretive adjudication, canonical wording, or release
        signoff.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["collision_visual_data"]["packet_pressure_rows"],
            label_key="label",
            value_key="value",
            aria_label="Collision packet pressure scores",
            color="#7c5b2f",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["collision_visual_data"]["lane_workload_rows"],
            label_key="label",
            value_key="value",
            aria_label="Collision packet decision workload by lane",
            color="#2f6f73",
            limit=20,
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Ref",
                "Score",
                "Lenses",
                "Decisions",
                "Roles",
                "Culture Domains",
                "Witness Div.",
                "Reception Frames",
            ],
            collision_packet_rows,
        )
    }
      {
        table(
            ["Lane", "Decision Rows", "Units", "Reviewer Roles", "Control"],
            collision_lane_rows,
        )
    }
      {
        table(
            ["Reviewer Role", "Decision Rows", "Units", "Status"],
            collision_role_rows,
        )
    }
      {
        table(
            ["Ref", "Lane", "Reviewer Role", "Current Data", "Decision Prompt", "Status"],
            collision_decision_rows,
        )
    }
    </section>

    <section>
      <h2>Doctoral Collision Benchmark Supplement</h2>
      <div class="warning">
        These locked-input tasks test model handling of collision packets. They
        are not model results, cross-examination scores, reviewer decisions,
        source approvals, or canonical translation evidence.
      </div>
      {
        metric_cards(
            [
                (
                    "Tasks",
                    fmt_int(headline["collision_benchmark_task_count"]),
                    (
                        f'{fmt_int(headline["collision_benchmark_unit_count"])} '
                        "collision units in gloss/literal layers."
                    ),
                ),
                (
                    "Planned runs",
                    fmt_int(headline["collision_benchmark_planned_runs"]),
                    "Tasks multiplied by planned bakeoff models.",
                ),
                (
                    "Pending source decisions",
                    fmt_int(headline["collision_benchmark_pending_decisions"]),
                    "Reviewer decisions still unsigned in source packets.",
                ),
                (
                    "Top collision",
                    headline["collision_benchmark_top_ref"],
                    f'Score {headline["collision_benchmark_top_score"]:.2f}.',
                ),
            ]
        )
    }
      {
        metric_cards(
            [
                (
                    "Cross-exam packets",
                    fmt_int(headline["collision_benchmark_cross_exam_packets"]),
                    (
                        f'{fmt_int(headline["collision_benchmark_cross_exam_rows"])} '
                        "candidate-by-judge execution rows."
                    ),
                ),
                (
                    "Dry-run rows",
                    fmt_int(headline["collision_benchmark_dry_run_valid"]),
                    (
                        f'{fmt_int(headline["collision_benchmark_dry_run_missing"])} '
                        "expected model rows still absent."
                    ),
                ),
                (
                    "Human review rows",
                    fmt_int(headline["collision_benchmark_review_human_rows"]),
                    "Projected role-specific signoff workload.",
                ),
                (
                    "Model review rows",
                    fmt_int(headline["collision_benchmark_review_model_rows"]),
                    "Projected advisory model cross-examination workload.",
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            collision_benchmark_chart_rows,
            label_key="label",
            value_key="value",
            aria_label="Collision benchmark pressure by selected gloss task",
            color="#7c5b2f",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["collision_benchmark_visual_data"]["task_lane_rows"],
            label_key="lane",
            value_key="count",
            aria_label="Collision benchmark task counts by required lane",
            color="#2f6f73",
            limit=20,
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Task",
                "Ref",
                "Layer",
                "Band",
                "Score",
                "Lenses",
                "Decisions",
                "Lanes",
                "Tokens",
                "Payload Chars",
            ],
            collision_benchmark_task_rows,
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            collision_benchmark_judge_rows,
            label_key="label",
            value_key="value",
            aria_label="Collision benchmark cross-exam packets by judge",
            color="#2f6f73",
            limit=10,
        )
    }</div>
      {
        table(
            [
                "Packet",
                "Ref",
                "Layer",
                "Judge",
                "Priority",
                "Probes",
                "Context Domains",
                "Human Roles",
            ],
            collision_benchmark_cross_exam_rows,
        )
    }
      {
        table(
            [
                "Task",
                "Model",
                "Schema Valid",
                "Candidates",
                "Alignment Mean",
                "Basis Mean",
                "Anchor Issues",
            ],
            collision_benchmark_dry_run_rows,
        )
    }
      {
        table(
            ["Task", "Ref", "Layer", "Intensity", "Role Count", "Roles", "Candidates"],
            collision_benchmark_review_rows,
        )
    }
    </section>

    <section>
      <h2>Doctoral Collision Real Smoke</h2>
      <div class="warning">
        These are real local-model outputs for the top Psalm 22:28 collision
        smoke pair. They verify bounded runner/scorer behavior under collision
        pressure, but they do not establish scaled benchmark performance,
        reviewer signoff, source approval, or translation authority.
      </div>
      {
        metric_cards(
            [
                (
                    "Real attempts",
                    fmt_int(headline["collision_real_smoke_attempt_count"]),
                    (
                        f'{fmt_int(headline["collision_real_smoke_task_count"])} '
                        "tasks across "
                        f'{fmt_int(headline["collision_real_smoke_model_count"])} '
                        "local models."
                    ),
                ),
                (
                    "Schema valid",
                    fmt_int(headline["collision_real_smoke_schema_valid_attempt_count"]),
                    (
                        f'{headline["collision_real_smoke_schema_valid_attempt_pct"]:.2f}% '
                        "of submitted smoke attempts."
                    ),
                ),
                (
                    "Clean anchored",
                    fmt_int(headline["collision_real_smoke_clean_attempt_count"]),
                    (
                        f'{headline["collision_real_smoke_clean_attempt_pct"]:.2f}% '
                        "with no source-anchor issue."
                    ),
                ),
                (
                    "Anchor issues",
                    fmt_int(headline["collision_real_smoke_source_anchor_issue_count"]),
                    (
                        f'{fmt_int(headline["collision_real_smoke_reception_leak_term_count"])} '
                        "reception leak terms flagged."
                    ),
                ),
                (
                    "Missing rows",
                    fmt_int(headline["collision_real_smoke_missing_model_task_count"]),
                    "Planned collision model-task rows still absent.",
                ),
                (
                    "Clean best",
                    headline["collision_real_smoke_clean_best_model"] or "none",
                    (
                        "Fastest valid: "
                        f'{headline["collision_real_smoke_fastest_valid_model"] or "none"}.'
                    ),
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["collision_real_smoke_visual_data"]["model_elapsed_rows"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral collision real smoke elapsed seconds by model",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["collision_real_smoke_visual_data"]["model_anchor_issue_rows"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral collision real smoke source-anchor issues by model",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            [
                "Model",
                "Attempts",
                "Schema Valid",
                "Clean Valid",
                "Schema %",
                "Anchor Issues",
                "Reception Leaks",
                "Mean Elapsed",
                "Mean Alignment",
                "Mean Basis",
            ],
            collision_smoke_model_rows,
        )
    }
      {
        table(
            [
                "Attempt",
                "Task",
                "Layer",
                "Schema Valid",
                "Candidates",
                "Anchor Issues",
                "Reception Leaks",
                "Errors",
                "Elapsed",
                "Candidate Text",
            ],
            collision_smoke_attempt_rows,
        )
    }
    </section>

    <section>
      <h2>Contextual Real Model Evidence Matrix</h2>
      <div class="warning">
        This matrix consolidates measured local outputs across canonical
        intertext, reception-sensitive, and doctoral collision benchmark lanes.
        It is smoke evidence for model behavior under broader-context pressure;
        it is not source approval, reviewer adjudication, or release authority.
      </div>
      {
        metric_cards(
            [
                (
                    "Attempts",
                    fmt_int(headline["contextual_real_model_attempt_count"]),
                    (
                        f'{fmt_int(headline["contextual_real_model_lane_count"])} '
                        "context lanes with real local rows."
                    ),
                ),
                (
                    "Clean",
                    fmt_int(headline["contextual_real_model_clean_count"]),
                    (
                        f'{headline["contextual_real_model_clean_pct"]:.2f}% '
                        "clean source-anchored attempts."
                    ),
                ),
                (
                    "Anchor issues",
                    fmt_int(headline["contextual_real_model_anchor_issue_count"]),
                    "Source-anchor failures requiring model or prompt repair.",
                ),
                (
                    "Coverage",
                    f'{headline["contextual_real_model_coverage_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["contextual_real_model_valid_count"])} '
                        "valid rows over "
                        f'{fmt_int(headline["contextual_real_model_planned_count"])} '
                        "planned contextual model-task rows."
                    ),
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["contextual_real_model_visual_data"]["model_clean_rows"],
            label_key="label",
            value_key="value",
            aria_label="Contextual real model clean source-anchored rows",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["contextual_real_model_visual_data"]["model_anchor_issue_rows"],
            label_key="label",
            value_key="value",
            aria_label="Contextual real model source-anchor issues",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["contextual_real_model_visual_data"]["lane_missing_rows"],
            label_key="label",
            value_key="value",
            aria_label="Contextual lane missing planned model-task rows",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Lane",
                "Context Focus",
                "Planned",
                "Attempts",
                "Schema Valid",
                "Clean",
                "Coverage",
                "Missing",
                "Anchor Issues",
                "Clean Best",
            ],
            contextual_real_model_lane_rows,
        )
    }
      {
        table(
            [
                "Model",
                "Attempts",
                "Schema Valid",
                "Schema %",
                "Clean",
                "Clean %",
                "Anchor Issues",
                "Mean Elapsed",
                "Clean Lanes",
                "Evidence Role",
            ],
            contextual_real_model_model_rows,
        )
    }
      {
        table(
            [
                "Lane",
                "Model",
                "Attempts",
                "Schema Valid",
                "Clean",
                "Anchor Issues",
                "Mean Elapsed",
                "Task Refs",
            ],
            contextual_real_model_model_lane_rows,
        )
    }
    </section>

    <section>
      <h2>Evidence Scale</h2>
      {
        metric_cards(
            [
                (
                    "Witness records",
                    fmt_int(evidence["witness_records"]),
                    (
                        f'{fmt_int(len(evidence["witness_source_counts"]))} '
                        "witness source IDs attached to Psalm units."
                    ),
                ),
                (
                    "Tanakh words",
                    fmt_int(evidence["tanakh_word_elements"]),
                    "UXLC word elements available for form context.",
                ),
                (
                    "Strong keys",
                    fmt_int(evidence["lexeme_distinct_strong_keys"]),
                    (
                        f'{fmt_int(evidence["lexeme_distinct_lemmas"])} '
                        "Psalm lemma strings measured."
                    ),
                ),
                (
                    "Seed context",
                    f'{evidence["seed_surface_outside_context_pct"]:.2f}%',
                    "Seed tokens with outside-Psalms surface context.",
                ),
                (
                    "Planned runs",
                    fmt_int(headline["planned_model_runs"]),
                    "Model-task runs in the first bake-off.",
                ),
                (
                    "24GB q4 fit",
                    fmt_int(evidence["runtime_q4_fit_model_count"]),
                    (
                        f'{fmt_int(evidence["runtime_model_cache_file_count"])} '
                        "model-like cache files detected."
                    ),
                ),
                (
                    "Text assets",
                    fmt_int(evidence["asset_text_capable_count"]),
                    f'{evidence["asset_text_gb"]:.3f} GiB text-capable local assets.',
                ),
                (
                    "Human reviews",
                    fmt_int(headline["integrated_review_human_rows"]),
                    "Projected integrated role-specific signoff records.",
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            artifact_rows(dashboard),
            label_key="artifact",
            value_key="bytes_kib",
            aria_label="Research artifact sizes in KiB",
            color="#7c5b2f",
            limit=16,
        )
    }</div>
    </section>

    <section>
      <h2>Dashboards</h2>
      {table(["Dashboard", "Purpose"], report_rows)}
    </section>

    <section>
      <h2>Canonical Context Network</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["canonical_context_division_evidence"],
            label_key="division",
            value_key="unit_count_with_evidence",
            aria_label="Expanded units with non-Psalm evidence by Tanakh division",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["canonical_context_book_evidence"],
            label_key="book",
            value_key="unit_count_with_evidence",
            aria_label="Expanded units with non-Psalm evidence by book",
            color="#7c5b2f",
            limit=15,
        )
    }</div>
      {
        table(
            [
                "Domain",
                "Expanded Units",
                "Avg Content Context",
                "Strong Units",
                "Weak Units",
                "Torah",
                "Prophets",
                "Review Queue",
            ],
            canonical_domain_rows,
        )
    }
    </section>

    <section>
      <h2>Canonical Cross-Reference Atlas</h2>
      <div class="warning">
        This atlas uses normalized UXLC surface forms outside Psalms. It routes
        broader-canon research and reviewer queues; it does not prove lemma
        identity, sense, allusion, dependence, or translation authority.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["canonical_cross_reference_visual_data"]["division_unit_counts"],
            label_key="label",
            value_key="value",
            aria_label="Full-corpus Psalm units with non-Psalm anchors by division",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["canonical_cross_reference_visual_data"]["book_anchor_counts"],
            label_key="label",
            value_key="value",
            aria_label="Full-corpus anchor-token counts by non-Psalm book",
            color="#7c5b2f",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["canonical_cross_reference_visual_data"]["domain_mean_priority"],
            label_key="label",
            value_key="value",
            aria_label="Mean cross-reference priority by contextual domain",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["canonical_cross_reference_visual_data"]["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top full-corpus canonical cross-reference priority units",
            color="#2f6f73",
        )
    }</div>
      {
        table(
            ["Division Bucket", "Units", "Unit %", "Mean Priority"],
            canonical_cross_ref_division_rows,
        )
    }
      {
        table(
            ["Book", "Division", "Anchor Tokens", "Units", "Outside Occurrence Sum"],
            canonical_cross_ref_book_rows,
        )
    }
      {
        table(
            [
                "Domain",
                "Units",
                "Anchor Tokens",
                "Three-Division Units",
                "Mean Priority",
                "Top Ref",
            ],
            canonical_cross_ref_domain_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Anchors",
                "High",
                "Medium",
                "Low",
                "Domains",
                "Top Anchor Forms",
            ],
            canonical_cross_ref_priority_rows,
        )
    }
      {
        table(
            [
                "Ref",
                "Surface",
                "Normalized",
                "Gloss",
                "Outside Psalms",
                "Strength",
                "Score",
                "Torah Samples",
                "Prophets Samples",
                "Writings Samples",
            ],
            canonical_cross_ref_anchor_rows,
        )
    }
    </section>

    <section>
      <h2>Canonical Intertext Benchmark Supplement</h2>
      <div class="warning">
        These tasks use whole-Tanakh surface-form anchors as contextual retrieval
        cues only. They test whether models can preserve local Psalm Hebrew
        syntax and alignment while recognizing broader-canon pressure; they do
        not prove allusion, dependence, lemma identity, or translation authority.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            canonical_intertext_benchmark_chart_rows,
            label_key="label",
            value_key="value",
            aria_label="Canonical intertext supplement priority by selected gloss task",
            color="#2f6f73",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            canonical_intertext_packet_domain_rows,
            label_key="label",
            value_key="value",
            aria_label="Canonical intertext cross-exam packets by contextual domain",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            canonical_intertext_packet_book_rows,
            label_key="label",
            value_key="value",
            aria_label="Canonical intertext cross-exam book pressure",
            color="#7c5b2f",
            limit=20,
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Task",
                "Ref",
                "Layer",
                "Score",
                "Anchors",
                "High Anchors",
                "Domains",
                "Top Anchor Forms",
                "Tokens",
                "Payload Chars",
            ],
            canonical_intertext_benchmark_task_rows,
        )
    }
      {
        table(
            ["Domain", "Task Count", "Cross-Exam Packet Count"],
            canonical_intertext_domain_rows,
        )
    }
      {
        table(
            ["Book", "Task Presence Count", "Cross-Exam Packet Mentions"],
            canonical_intertext_book_rows,
        )
    }
      {
        table(
            [
                "Packet",
                "Ref",
                "Layer",
                "Judge",
                "Priority",
                "Score",
                "Probe Count",
                "Domains",
                "Top Books",
            ],
            canonical_intertext_cross_exam_rows,
        )
    }
      {
        table(
            [
                "Task",
                "Model",
                "Schema Valid",
                "Candidates",
                "Mean Alignment",
                "Mean Basis",
                "Anchor Issues",
            ],
            canonical_intertext_dry_run_rows,
        )
    }
      {
        table(
            ["Task", "Ref", "Layer", "Intensity", "Required Roles", "Roles"],
            canonical_intertext_review_rows,
        )
    }
    </section>

    <section>
      <h2>Canonical Intertext Real Smoke</h2>
      <div class="warning">
        These are real local-model outputs for one canonical-intertext smoke
        task. They are useful runtime and prompt evidence, but they do not
        establish scaled benchmark performance, source approval, reviewer
        signoff, or canonical translation authority.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            canonical_intertext_smoke_elapsed_rows,
            label_key="label",
            value_key="value",
            aria_label="Canonical intertext real smoke elapsed seconds",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            canonical_intertext_smoke_anchor_rows,
            label_key="label",
            value_key="value",
            aria_label="Canonical intertext real smoke source-anchor issues",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            [
                "Model",
                "Attempts",
                "Schema Valid",
                "Schema %",
                "Anchor Issues",
                "Mean Elapsed",
                "Mean Alignment",
                "Mean Basis",
            ],
            canonical_intertext_smoke_model_rows,
        )
    }
      {
        table(
            [
                "Attempt",
                "Model",
                "Task",
                "Schema Valid",
                "Candidates",
                "Errors",
                "Error Detail",
                "Anchor Issues",
                "Elapsed",
                "Candidate Text",
            ],
            canonical_intertext_smoke_attempt_rows,
        )
    }
    </section>

    <section>
      <h2>Witness Divergence</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["witness_divergence_visual_data"]["source_pair_divergence"],
            label_key="label",
            value_key="value",
            aria_label="English witness source-pair divergence",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["witness_divergence_visual_data"]["marker_counts"],
            label_key="label",
            value_key="value",
            aria_label="English witness divergence marker counts",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["witness_divergence_visual_data"]["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top English witness divergence priority units",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            ["Pair", "Mean Divergence", "Median", "P90", "High-Div Units", "Mean Token Delta"],
            witness_divergence_pair_rows,
        )
    }
      {
        table(
            ["Marker", "Unit Count", "Unit %"],
            witness_divergence_marker_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Divergence",
                "Length Spread",
                "Markers",
                "KJV",
                "ASV",
                "WEB",
            ],
            witness_divergence_priority_rows,
        )
    }
      {
        table(
            [
                "Psalm",
                "Units",
                "Mean Divergence",
                "High-Div Units",
                "Divine Name Disagreement",
                "Mean Priority",
                "Top Ref",
            ],
            witness_divergence_psalm_rows,
        )
    }
    </section>

    <section>
      <h2>Divine Name Policy Pressure</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["divine_name_policy_visual_data"]["category_token_counts"],
            label_key="label",
            value_key="value",
            aria_label="Divine name and title token counts by category",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["divine_name_policy_visual_data"]["marker_counts"],
            label_key="label",
            value_key="value",
            aria_label="Divine name policy marker counts",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["divine_name_policy_visual_data"]["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top divine name policy pressure units",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            ["Category", "Token Count"],
            divine_name_category_rows,
        )
    }
      {
        table(
            ["Marker", "Unit Count", "Unit %"],
            divine_name_marker_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Tokens",
                "Categories",
                "Markers",
                "KJV",
                "ASV",
                "WEB",
            ],
            divine_name_priority_rows,
        )
    }
      {
        table(
            [
                "Psalm",
                "Units",
                "Tokens",
                "YHWH",
                "Elohim",
                "Adonai",
                "Witness Disagreement",
                "Mean Priority",
                "Top Ref",
            ],
            divine_name_psalm_rows,
        )
    }
    </section>

    <section>
      <h2>Superscription, Performance, and Liturgical Context</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["superscription_context_visual_data"]["category_token_counts"],
            label_key="label",
            value_key="value",
            aria_label="Superscription context token counts by category",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["superscription_context_visual_data"]["marker_counts"],
            label_key="label",
            value_key="value",
            aria_label="Superscription context marker counts",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["superscription_context_visual_data"]["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top superscription context priority units",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            ["Category", "Token Count"],
            superscription_category_rows,
        )
    }
      {
        table(
            ["Marker", "Unit Count", "Unit %"],
            superscription_marker_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Tokens",
                "Categories",
                "Markers",
                "KJV",
                "ASV",
                "WEB",
            ],
            superscription_priority_rows,
        )
    }
      {
        table(
            [
                "Psalm",
                "Units",
                "Tokens",
                "Heading Units",
                "Historical",
                "Technical",
                "Mean Priority",
                "Top Ref",
            ],
            superscription_psalm_rows,
        )
    }
    </section>

    <section>
      <h2>Cultural and Historical Domain Atlas</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["cultural_historical_visual_data"]["domain_token_counts"],
            label_key="label",
            value_key="value",
            aria_label="Cultural historical domain token counts",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["cultural_historical_visual_data"]["domain_unit_counts"],
            label_key="label",
            value_key="value",
            aria_label="Cultural historical domain unit counts",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["cultural_historical_visual_data"]["cooccurrence_counts"],
            label_key="label",
            value_key="value",
            aria_label="Cultural historical domain co-occurrence counts",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["cultural_historical_visual_data"]["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top cultural historical priority units",
            color="#2f6f73",
        )
    }</div>
      {
        table(
            [
                "Domain",
                "Tokens",
                "Units",
                "Unit %",
                "Psalms",
                "High Priority",
                "Ancient Culture",
                "Reception",
                "Top Lemmas",
            ],
            cultural_domain_rows,
        )
    }
      {
        table(
            ["Marker", "Unit Count", "Unit %"],
            cultural_marker_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Tokens",
                "Domains",
                "Markers",
                "KJV",
                "ASV",
                "WEB",
            ],
            cultural_priority_rows,
        )
    }
      {
        table(
            [
                "Psalm",
                "Units",
                "Tokens",
                "Domains",
                "Ancient Culture",
                "Reception",
                "Mean Priority",
                "Top Ref",
            ],
            cultural_psalm_rows,
        )
    }
      {
        table(
            ["Left Domain", "Right Domain", "Units", "Mean Priority"],
            cultural_cooccurrence_rows,
        )
    }
    </section>

    <section>
      <h2>Poetic and Rhetorical Pressure Atlas</h2>
      <div class="warning">
        These rows route literary, poetic, lyric, and alignment review. They do
        not prove formal parallelism, meter, stanza structure, or final English
        wording.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["poetic_rhetorical_visual_data"]["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top poetic and rhetorical priority units",
            color="#355f7c",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["poetic_rhetorical_visual_data"]["feature_counts"],
            label_key="label",
            value_key="value",
            aria_label="Poetic and rhetorical feature counts",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["poetic_rhetorical_visual_data"]["top_psalm_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top Psalms by poetic and rhetorical pressure",
            color="#6f5d2f",
        )
    }</div>
      {
        table(
            ["Feature", "Units", "Unit %", "Mean Score", "Top Ref"],
            poetic_feature_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Band",
                "Score",
                "Volitives",
                "Lemma Excess",
                "Adjacent Overlap",
                "Flags",
            ],
            poetic_priority_rows,
        )
    }
      {
        table(
            [
                "Psalm",
                "Units",
                "High-Pressure Units",
                "Mean Score",
                "Acrostic Profile",
                "Initial Letters",
                "Top Ref",
            ],
            poetic_psalm_rows,
        )
    }
    </section>

    <section>
      <h2>Corpus Reception Signal Atlas</h2>
      <div class="warning">
        These rows route separated Jewish, Christian, academic, Hebrew-source,
        and textual-witness review. Signal families do not decide interpretation
        or authorize translation wording.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["corpus_reception_signal_visual_data"]["signal_unit_counts"],
            label_key="label",
            value_key="value",
            aria_label="Corpus reception signal unit counts",
            color="#5b6f2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["corpus_reception_signal_visual_data"]["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top corpus reception signal priority units",
            color="#355f7c",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["corpus_reception_signal_visual_data"]["top_expansion_candidates"],
            label_key="label",
            value_key="value",
            aria_label="Top corpus reception expansion candidates",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            [
                "Signal",
                "Tokens",
                "Units",
                "Unit %",
                "Known Reception Rows",
                "Known Split Rows",
                "Mean Score",
                "Top Ref",
            ],
            corpus_reception_signal_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Band",
                "Score",
                "Families",
                "Signals",
                "Report Flags",
                "Review Roles",
            ],
            corpus_reception_priority_rows,
        )
    }
      {
        table(
            ["Rank", "Ref", "Band", "Score", "Families", "Signals", "Review Roles"],
            corpus_reception_expansion_rows,
        )
    }
      {
        table(
            [
                "Psalm",
                "Units",
                "Tokens",
                "Families",
                "Known Split",
                "High Pressure",
                "Mean Score",
                "Top Ref",
            ],
            corpus_reception_psalm_rows,
        )
    }
    </section>

    <section>
      <h2>Reception Signal Benchmark Supplement</h2>
      <div class="warning">
        These are locked-input benchmark prompts for high-pressure corpus
        reception-signal candidates. They are not model results, review
        decisions, source approvals, or canonical translation evidence.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            reception_signal_benchmark_chart_rows,
            label_key="label",
            value_key="value",
            aria_label="Reception signal supplement priority scores",
            color="#7a4c22",
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Task",
                "Ref",
                "Layer",
                "Band",
                "Score",
                "Families",
                "Signals",
                "Tokens",
                "Payload Chars",
            ],
            reception_signal_benchmark_task_rows,
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            reception_signal_packet_signal_rows,
            label_key="label",
            value_key="value",
            aria_label="Reception signal cross-exam packet counts by signal family",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            [
                "Packet",
                "Ref",
                "Layer",
                "Judge",
                "Priority",
                "Band",
                "Probes",
                "Signals",
            ],
            reception_signal_cross_exam_rows,
        )
    }
      {
        table(
            [
                "Task",
                "Model",
                "Schema Valid",
                "Candidates",
                "Alignment",
                "Basis",
                "Anchor Issues",
            ],
            reception_signal_dry_run_rows,
        )
    }
      {
        table(
            ["Task", "Ref", "Layer", "Intensity", "Role Count", "Roles"],
            reception_signal_review_rows,
        )
      }
    </section>

    <section>
      <h2>Reception Signal Real Smoke</h2>
      <div class="warning">
        These are real full-context local-model outputs for one Psalm 110:2
        reception-signal smoke task. They test schema, Hebrew anchoring, and
        whether reception-history pressure leaks into translation text, but
        they do not establish scaled benchmark performance, Jewish/Christian
        adjudication, source approval, reviewer signoff, or canonical
        translation authority.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            reception_signal_smoke_elapsed_rows,
            label_key="label",
            value_key="value",
            aria_label="Reception signal real smoke elapsed seconds",
            color="#315f72",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            reception_signal_smoke_anchor_rows,
            label_key="label",
            value_key="value",
            aria_label="Reception signal real smoke source-anchor issues",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            [
                "Model",
                "Attempts",
                "Schema Valid",
                "Clean Valid",
                "Schema %",
                "Anchor Issues",
                "Reception Leaks",
                "Mean Elapsed",
                "Mean Alignment",
                "Mean Basis",
            ],
            reception_signal_smoke_model_rows,
        )
    }
      {
        table(
            [
                "Attempt",
                "Model",
                "Task",
                "Schema Valid",
                "Candidates",
                "Errors",
                "Error Detail",
                "Anchor Issues",
                "Reception Leaks",
                "Elapsed",
                "Candidate Text",
            ],
            reception_signal_smoke_attempt_rows,
        )
    }
    </section>

    <section>
      <h2>Reception Boundary</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["reception_boundary_domain_rows"],
            label_key="domain",
            value_key="avg_boundary_risk_score",
            aria_label="Reception and interpretation boundary risk by domain",
            color="#9b3d3d",
            limit=12,
        )
    }</div>
      {
        table(
            ["Frame", "Units", "Lane", "Allowed Location"],
            reception_frame_rows,
        )
    }
      {
        table(
            [
                "Domain",
                "Units",
                "Reception",
                "Textual Witness",
                "Avg Risk",
                "High Risk",
            ],
            reception_domain_rows,
        )
    }
    </section>

    <section>
      <h2>Reception Divergence Atlas</h2>
      <div class="warning">
        These rows measure separated reception review pressure. They do not decide
        Jewish interpretation, Christian interpretation, messianic meaning, or
        translation wording authority.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["reception_divergence_visual_data"]["signal_unit_counts"],
            label_key="label",
            value_key="value",
            aria_label="Reception divergence signal family counts",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["reception_divergence_visual_data"]["frame_unit_counts"],
            label_key="label",
            value_key="value",
            aria_label="Required reception divergence frame counts",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["reception_divergence_visual_data"]["domain_mean_priority"],
            label_key="label",
            value_key="value",
            aria_label="Reception divergence mean priority by domain",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["reception_divergence_visual_data"]["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top reception divergence priority units",
            color="#2f6f73",
        )
    }</div>
      {
        table(
            ["Signal", "Units", "Unit %", "Split-Lane Units", "Mean Priority", "Top Ref"],
            reception_divergence_signal_rows,
        )
    }
      {
        table(
            ["Frame", "Lane", "Units", "Split-Lane Units", "Mean Priority", "Allowed Location"],
            reception_divergence_frame_rows,
        )
    }
      {
        table(
            [
                "Domain",
                "Units",
                "Split-Lane Units",
                "Reception Units",
                "Textual Witness",
                "Mean Priority",
                "Top Ref",
            ],
            reception_divergence_domain_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Split Lanes",
                "Signal Families",
                "Required Frames",
                "Top Cross-Refs",
                "Hebrew",
            ],
            reception_divergence_priority_rows,
        )
    }
      {
        table(
            ["Boundary ID", "Boundary", "Evidence", "Next Action"],
            reception_divergence_boundary_rows,
        )
    }
    </section>

    <section>
      <h2>Reception Source Packet Workbook</h2>
      <div class="warning">
        These rows separate Jewish, Christian, and academic source work for
        high-pressure reception units. They are packet scaffolding only:
        no source approval, interpretive adjudication, translation wording
        authority, or human signoff is implied.
      </div>
      {
        metric_cards(
            [
                (
                    "Split-lane units",
                    fmt_int(headline["reception_source_packet_unit_count"]),
                    "Units requiring separated Jewish/Christian review.",
                ),
                (
                    "Packet rows",
                    fmt_int(headline["reception_source_packet_count"]),
                    "Jewish, Christian, and academic source-packet rows.",
                ),
                (
                    "Candidate sources",
                    fmt_int(headline["reception_source_packet_candidate_source_count"]),
                    (
                        f'{fmt_int(headline["reception_source_packet_reachable_source_count"])} '
                        "reachable candidate source IDs."
                    ),
                ),
                (
                    "Approvals",
                    fmt_int(headline["reception_source_packet_source_approval_count"]),
                    (
                        f'{fmt_int(headline["reception_source_packet_blocked_gate_count"])} '
                        "blocked gates remain."
                    ),
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["reception_source_packet_visual_data"]["top_unit_rows"],
            label_key="label",
            value_key="value",
            aria_label="Reception source packet top unit priority scores",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["reception_source_packet_visual_data"]["lane_packet_rows"],
            label_key="label",
            value_key="value",
            aria_label="Reception source packet workload by lane",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["reception_source_packet_visual_data"]["source_status_rows"],
            label_key="label",
            value_key="value",
            aria_label="Reception source candidate verification statuses",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Boundary Risk",
                "Witness Divergence",
                "Signals",
                "Case Families",
                "Packets",
            ],
            reception_source_packet_unit_rows,
        )
    }
      {
        table(
            [
                "Packet",
                "Ref",
                "Lane",
                "Candidates",
                "Reachable",
                "Best License Risk",
                "Status",
            ],
            reception_source_packet_rows,
        )
    }
      {
        table(
            [
                "Lane",
                "Source ID",
                "Label",
                "License Risk",
                "Reachable",
                "Verification",
                "Packets",
            ],
            reception_source_packet_source_rows,
        )
    }
      {
        table(
            ["Gate", "Score", "Status", "Evidence", "Next Action"],
            reception_source_packet_gate_rows,
        )
    }
    </section>

    <section>
      <h2>Interpretive Tradition Control Matrix</h2>
      <div class="warning">
        This joins Jewish, Christian, academic, culture, witness, and Hebrew-source
        controls for reception-sensitive claims. It is routing evidence only:
        no source approval, packet review, interpretive conclusion, or canonical
        translation authority is implied.
      </div>
      {
        metric_cards(
            [
                (
                    "Control units",
                    fmt_int(headline["interpretive_control_unit_count"]),
                    (
                        f'{fmt_int(headline["interpretive_control_split_units"])} '
                        "need Jewish/Christian separation."
                    ),
                ),
                (
                    "Reception-sensitive",
                    fmt_int(headline["interpretive_control_reception_sensitive_units"]),
                    (
                        f'{fmt_int(headline["interpretive_control_forbidden_text_units"])} '
                        "forbidden as translation wording."
                    ),
                ),
                (
                    "Culture/Witness",
                    (
                        f'{fmt_int(headline["interpretive_control_ancient_culture_units"])} / '
                        f'{fmt_int(headline["interpretive_control_textual_witness_units"])}'
                    ),
                    "Ancient-culture and textual-witness pressure units.",
                ),
                (
                    "Packet reviews",
                    fmt_int(headline["interpretive_control_completed_packet_reviews"]),
                    (
                        f'{fmt_int(headline["interpretive_control_packet_count"])} '
                        "packets remain routed."
                    ),
                ),
                (
                    "Source approvals",
                    fmt_int(headline["interpretive_control_source_approval_count"]),
                    "Approved sources for these separated packets.",
                ),
                (
                    "Top control",
                    headline["interpretive_control_top_ref"],
                    f'{float(headline["interpretive_control_top_score"]):.2f}.',
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["interpretive_control_visual_data"]["top_unit_rows"],
            label_key="label",
            value_key="value",
            aria_label="Interpretive tradition top control scores",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["interpretive_control_visual_data"]["lane_unit_rows"],
            label_key="label",
            value_key="value",
            aria_label="Interpretive tradition controls by lane",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["interpretive_control_visual_data"]["control_rows"],
            label_key="label",
            value_key="value",
            aria_label="Interpretive tradition claim controls",
            color="#7c5b2f",
        )
    }</div>
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
            interpretive_control_unit_rows,
        )
    }
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
                "Status",
            ],
            interpretive_control_lane_rows,
        )
    }
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
                "Status",
            ],
            interpretive_control_packet_rows,
        )
    }
      {
        table(
            ["Control", "Units", "Pct", "Top Ref", "Authority Effect"],
            interpretive_control_claim_rows,
        )
    }
    </section>

    <section>
      <h2>Translation Claim Traceability Audit</h2>
      <div class="warning">
        This audit routes claim families to draft text, notes, source packets,
        benchmark evidence, or release gates. It does not approve sources,
        resolve interpretation, certify model output, or authorize canonical
        translation wording.
      </div>
      {
        metric_cards(
            [
                (
                    "Required claims",
                    fmt_int(headline["claim_traceability_required_claim_row_count"]),
                    (
                        fmt_int(headline["claim_traceability_claim_row_count"])
                        + " total family rows across "
                        + fmt_int(headline["claim_traceability_unit_count"])
                        + " units."
                    ),
                ),
                (
                    "Text now",
                    fmt_int(headline["claim_traceability_translation_text_allowed_now_count"]),
                    "Currently authorized for translation text.",
                ),
                (
                    "Text after review",
                    fmt_int(headline["claim_traceability_allowed_after_review_count"]),
                    "Draft/text-eligible only after source and human review.",
                ),
                (
                    "Notes only",
                    fmt_int(headline["claim_traceability_notes_only_claim_count"]),
                    "Claims that must remain in notes or source packets.",
                ),
                (
                    "Missing source approval",
                    fmt_int(headline["claim_traceability_source_approval_missing_count"]),
                    "Required claim rows blocked by source approval.",
                ),
                (
                    "Top pressure",
                    headline["claim_traceability_top_ref"],
                    (
                        fmt_int(headline["claim_traceability_top_gate_count"])
                        + " blocking gates."
                    ),
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["claim_traceability_visual_data"]["top_unit_rows"],
            label_key="label",
            value_key="value",
            aria_label="Translation claim traceability top unit gate counts",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["claim_traceability_visual_data"]["family_blocked_rows"],
            label_key="label",
            value_key="value",
            aria_label="Translation claim traceability blocked families",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["claim_traceability_visual_data"]["gate_rows"],
            label_key="label",
            value_key="value",
            aria_label="Translation claim traceability blocking gates",
            color="#2f6f73",
        )
    }</div>
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
            claim_traceability_family_rows,
        )
    }
      {
        table(
            [
                "Gate",
                "Claim Rows",
                "Claim %",
                "Units",
                "Top Ref",
                "Top Family",
                "Next Action",
            ],
            claim_traceability_gate_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Risk",
                "Required Families",
                "Blocked/Review Families",
                "Notes-Only Families",
                "Text Now",
                "Text After Review",
                "Gate Count",
                "Top Gates",
                "Required Families",
            ],
            claim_traceability_unit_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Family",
                "Required",
                "Admissibility",
                "Allowed Location",
                "Text Now",
                "Evidence",
                "Grade",
                "Gates",
                "Evidence Summary",
            ],
            claim_traceability_claim_rows,
        )
      }
    </section>

    <section>
      <h2>Translation Accuracy Certification Matrix</h2>
      <div class="warning">
        This matrix is a signoff ledger, not a signoff. It separates evidence
        maturity from certification readiness across Hebrew, whole-OT,
        cultural, witness, Jewish/Christian, model, review, and release lanes.
      </div>
      {
        metric_cards(
            [
                (
                    "Certification",
                    headline["translation_accuracy_certification_status"],
                    "Current accuracy-certification state.",
                ),
                (
                    "Evidence maturity",
                    f'{headline["translation_accuracy_evidence_maturity_pct"]:.2f}%',
                    "Weighted maturity across accuracy dimensions.",
                ),
                (
                    "Readiness",
                    f'{headline["translation_accuracy_certification_readiness_pct"]:.2f}%',
                    "Readiness after hard authority blockers.",
                ),
                (
                    "Blocked gates",
                    (
                        f'{fmt_int(headline["translation_accuracy_blocked_gate_count"])}/'
                        f'{fmt_int(headline["translation_accuracy_gate_count"])}'
                    ),
                    "Non-negotiable gates still blocking certification.",
                ),
                (
                    "Authorized dimensions",
                    fmt_int(headline["translation_accuracy_release_authorized_dimension_count"]),
                    "Dimensions currently release-authorized.",
                ),
                (
                    "Top unit gap",
                    headline["translation_accuracy_top_unit_ref"],
                    f'Top gap: {headline["translation_accuracy_top_dimension_gap"]}.',
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["translation_accuracy_visual_data"]["dimension_score_rows"],
            label_key="dimension",
            value_key="evidence_maturity_pct",
            aria_label="Translation accuracy evidence maturity by dimension",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["translation_accuracy_visual_data"]["dimension_score_rows"],
            label_key="dimension",
            value_key="certification_readiness_pct",
            aria_label="Translation accuracy certification readiness by dimension",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["translation_accuracy_visual_data"]["top_unit_gap_rows"],
            label_key="ref",
            value_key="source_authority_gap_score",
            aria_label="Translation accuracy top unit source gaps",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "ID",
                "Dimension",
                "Evidence",
                "Readiness",
                "Status",
                "Primary Metric",
                "Blocking Gap",
            ],
            translation_accuracy_dimension_rows,
        )
    }
      {
        table(
            ["ID", "Gate", "Status", "Current", "Target", "Blocker Effect"],
            translation_accuracy_gate_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Source Gap",
                "Source Readiness",
                "Chief Blocker",
                "Review Rows",
                "J/C Split",
                "Witness",
                "Culture",
            ],
            translation_accuracy_unit_rows,
        )
    }
      {
        table(
            ["Rank", "Role", "Rows", "Critical Rows", "Highest Rows", "Status"],
            translation_accuracy_role_rows,
        )
    }
    </section>

    <section>
      <h2>Critical Unit Decision Dossier</h2>
      <div class="warning">
        This dossier is a committee triage ledger, not a decision. It shows
        which high-pressure units remain blocked by source, morphology,
        semantic/referent, Jewish/Christian, model, human-review, and release
        lanes before wording can be treated as decidable.
      </div>
      {
        metric_cards(
            [
                (
                    "Decision state",
                    headline["critical_unit_decision_status"],
                    "Current dossier-level decision status.",
                ),
                (
                    "Decision units",
                    fmt_int(headline["critical_unit_decision_unit_count"]),
                    (
                        f'{fmt_int(headline["critical_unit_decision_text_blocked_count"])} '
                        "currently text-blocked."
                    ),
                ),
                (
                    "Blocked lanes",
                    fmt_int(headline["critical_unit_decision_blocked_lane_count"]),
                    "Per-unit decision lanes still blocking adjudication.",
                ),
                (
                    "Mean authority",
                    f'{headline["critical_unit_decision_mean_authority_pct"]:.2f}%',
                    "Mean unit authority score across the dossier.",
                ),
                (
                    "Clean model units",
                    fmt_int(headline["critical_unit_decision_clean_model_count"]),
                    "Units with clean source-anchored model evidence.",
                ),
                (
                    "Top pressure",
                    headline["critical_unit_decision_top_ref"],
                    f'Score {headline["critical_unit_decision_top_score"]:.2f}.',
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_decision_visual_data"]["decision_pressure_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit decision pressure",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_decision_visual_data"]["authority_readiness_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit authority readiness",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_decision_visual_data"]["lane_blocker_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit blocked decision lanes",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_decision_visual_data"]["claim_gate_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit claim blocking gates",
            color="#584b87",
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Ref",
                "Pressure",
                "Band",
                "Authority",
                "Blocked Lanes",
                "Claim Gates",
                "Text Now",
                "Clean Model",
                "J/C Split",
                "Next Action",
            ],
            critical_unit_decision_unit_rows,
        )
    }
      {
        table(
            ["Ref", "Lane", "Status", "Evidence", "Next Action"],
            critical_unit_decision_lane_rows,
        )
    }
      {
        table(
            [
                "Ref",
                "Family",
                "Admissibility",
                "Allowed Location",
                "Text Now",
                "After Review",
                "Gate Count",
                "Gates",
                "Evidence",
            ],
            critical_unit_decision_claim_rows,
        )
    }
    </section>

    <section>
      <h2>Critical Unit Review Execution Plan</h2>
      <div class="warning">
        This is an execution queue, not review completion. It sequences the
        reviewer identities, source approvals, Hebrew/morphology work,
        reception separation, model cross-exam, human signoff, and release
        gates that must clear before critical units become authoritative.
      </div>
      {
        metric_cards(
            [
                (
                    "Execution state",
                    headline["critical_unit_review_execution_status"],
                    "Current review-execution state.",
                ),
                (
                    "Role/source rows",
                    fmt_int(headline["critical_unit_review_execution_role_rows"]),
                    (
                        f'{fmt_int(headline["critical_unit_review_execution_completed_rows"])} '
                        "completed."
                    ),
                ),
                (
                    "Completion",
                    f'{headline["critical_unit_review_execution_completion_pct"]:.2f}%',
                    "Critical-unit role/source review completion.",
                ),
                (
                    "Blocked waves",
                    fmt_int(headline["critical_unit_review_execution_blocked_waves"]),
                    "Execution waves currently blocked.",
                ),
                (
                    "Blocked gates",
                    fmt_int(headline["critical_unit_review_execution_blocked_gates"]),
                    "Review-execution gates currently blocked.",
                ),
                (
                    "Top workload",
                    headline["critical_unit_review_execution_top_role"],
                    (
                        f'{fmt_int(headline["critical_unit_review_execution_top_role_rows"])} '
                        "rows."
                    ),
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_review_execution_visual_data"]["role_workload_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit review execution workload by role",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_review_execution_visual_data"]["wave_workload_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit review execution workload by wave",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_review_execution_visual_data"]["lane_blocker_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit review execution blocked lanes",
            color="#9b3d3d",
        )
    }</div>
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
            critical_unit_review_execution_wave_rows,
        )
    }
      {
        table(
            [
                "Role",
                "Wave",
                "Units",
                "Total Rows",
                "Complete",
                "Blocked Lanes",
                "Claim Gates",
                "Top Unit",
                "Next Action",
            ],
            critical_unit_review_execution_role_rows,
        )
    }
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
            critical_unit_review_execution_gate_rows,
        )
    }
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
                "Status",
            ],
            critical_unit_review_execution_unit_role_rows,
        )
    }
    </section>

    <section>
      <h2>Critical Unit Model Cross-Exam Plan</h2>
      <div class="warning">
        This is a model-evidence execution matrix, not model certification. It
        scopes critical-unit gloss/literal tasks across planned local models,
        candidate outputs, Codex/Claude/Hebrew-specialist advisory judges, and
        source-anchor gates before any human-review or release claim.
      </div>
      {
        metric_cards(
            [
                (
                    "Model state",
                    headline["critical_unit_model_cross_exam_status"],
                    "Current critical-unit model evidence state.",
                ),
                (
                    "Critical tasks",
                    fmt_int(headline["critical_unit_model_cross_exam_task_count"]),
                    (
                        f'{fmt_int(headline["critical_unit_model_cross_exam_planned_models"])} '
                        "planned model profiles."
                    ),
                ),
                (
                    "Model rows",
                    (
                        f'{fmt_int(headline["critical_unit_model_cross_exam_submitted_rows"])}/'
                        f'{fmt_int(headline["critical_unit_model_cross_exam_expected_rows"])}'
                    ),
                    (
                        f'{headline["critical_unit_model_cross_exam_coverage_pct"]:.2f}% '
                        "submitted."
                    ),
                ),
                (
                    "Missing rows",
                    fmt_int(headline["critical_unit_model_cross_exam_missing_rows"]),
                    f'Top missing model {headline["critical_unit_model_cross_exam_top_model"]}.',
                ),
                (
                    "Candidate outputs",
                    fmt_int(headline["critical_unit_model_cross_exam_candidate_outputs"]),
                    "Expected at three candidates per model-task row.",
                ),
                (
                    "Judge rows",
                    fmt_int(headline["critical_unit_model_cross_exam_judge_rows"]),
                    (
                        f'{fmt_int(headline["critical_unit_model_cross_exam_judges"])} judges; '
                        f'{fmt_int(headline["critical_unit_model_cross_exam_probe_questions"])} '
                        "probe questions."
                    ),
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_model_cross_exam_visual_data"]["unit_missing_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit missing model task rows",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_model_cross_exam_visual_data"]["model_missing_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical model missing task rows",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_model_cross_exam_visual_data"]["judge_execution_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical model advisory judge execution rows",
            color="#2f6f73",
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Ref",
                "Pressure",
                "Tasks",
                "Expected Rows",
                "Submitted",
                "Missing",
                "Candidate Outputs",
                "Judge Rows",
                "J/C Split",
                "Status",
            ],
            critical_unit_model_cross_exam_unit_rows,
        )
    }
      {
        table(
            [
                "Model",
                "Profile",
                "Local Asset",
                "Bakeoff",
                "Expected Rows",
                "Submitted",
                "Missing",
                "Schema Valid",
                "Anchor Issues",
                "Status",
            ],
            critical_unit_model_cross_exam_model_rows,
        )
    }
      {
        table(
            [
                "Judge",
                "Authority",
                "Packets",
                "Execution Rows",
                "Probe Questions",
                "Human Roles",
                "Status",
            ],
            critical_unit_model_cross_exam_judge_rows,
        )
    }
      {
        table(
            [
                "Task",
                "Ref",
                "Layer",
                "Expected Rows",
                "Submitted",
                "Missing",
                "Judge Rows",
                "Status",
            ],
            critical_unit_model_cross_exam_task_rows,
        )
    }
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
            critical_unit_model_cross_exam_gate_rows,
        )
    }
    </section>

    <section>
      <h2>Source Maturity</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["source_maturity_lanes"],
            label_key="label",
            value_key="evidence_score_pct",
            aria_label="Source evidence maturity by lane",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["source_maturity_lanes"],
            label_key="label",
            value_key="authority_score_pct",
            aria_label="Source authority maturity by lane",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            ["Lane", "Evidence", "Authority", "Status", "Blocking Gap"],
            source_maturity_lane_rows,
        )
    }
      {
        table(
            [
                "ID",
                "Name",
                "Lang",
                "Role",
                "License",
                "Version",
                "Pinned",
                "Generation",
                "Witness Rows",
            ],
            source_maturity_source_rows,
        )
    }
      {table(["Gate", "Score", "Status", "Evidence", "Next Action"], source_maturity_gate_rows)}
    </section>

    <section>
      <h2>Contextual Source Packets</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["contextual_source_packet_families"],
            label_key="label",
            value_key="unit_count",
            aria_label="Contextual source packet units by family",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["contextual_source_packet_roles"],
            label_key="reviewer_role",
            value_key="unit_count",
            aria_label="Contextual source packet reviewer workload",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            ["Family", "Status", "Units", "Priority", "Top Unit", "Roles", "Boundary"],
            contextual_packet_family_rows,
        )
    }
      {
        table(
            ["Role", "Units", "Family Assignments", "Priority Units", "Boundary"],
            contextual_packet_role_rows,
        )
    }
      {
        table(
            ["Rank", "Unit", "Score", "Band", "Families", "Packet Families"],
            contextual_packet_unit_rows,
        )
    }
      {table(["Gate", "Score", "Status", "Evidence", "Next Action"], contextual_packet_gate_rows)}
    </section>

    <section>
      <h2>Source Acquisition</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["source_acquisition_candidates"],
            label_key="label",
            value_key="priority_score",
            aria_label="Contextual source acquisition candidate priority",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["source_acquisition_candidates"],
            label_key="label",
            value_key="packet_unit_count",
            aria_label="Contextual source acquisition packet-unit reach",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Candidate",
                "Priority",
                "Score",
                "Units",
                "License Risk",
                "Machine",
                "Status",
            ],
            source_acquisition_candidate_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Phase",
                "Sources",
                "Unit Reach",
                "Mean Score",
                "Machine",
                "High Risk",
                "Exit Gate",
            ],
            source_acquisition_phase_rows,
        )
      }
      {table(["Gate", "Score", "Status", "Evidence", "Next Action"], source_acquisition_gate_rows)}
    </section>

    <section>
      <h2>Whole-Tanakh Morphology Acquisition Readiness</h2>
      <div class="warning">
        This section ranks source-acquisition readiness only. It does not approve
        source use, import external data, or authorize translation wording.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["morphology_acquisition_visual_data"]["candidate_priority_rows"],
            label_key="label",
            value_key="priority_score",
            aria_label="Whole-Tanakh morphology acquisition candidate priority",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["morphology_acquisition_visual_data"]["gate_score_rows"],
            label_key="gate",
            value_key="score_pct",
            aria_label="Whole-Tanakh morphology acquisition gate scores",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Candidate",
                "Recommendation",
                "Score",
                "License Risk",
                "Repo Status",
                "Authority",
                "Rationale",
            ],
            morphology_acquisition_candidate_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Phase",
                "Primary Candidate",
                "Status",
                "Mean Score",
                "Blocked",
                "Not Started",
                "Gates",
            ],
            morphology_acquisition_phase_rows,
        )
    }
      {
        table(
            ["Gate", "Name", "Score", "Status", "Evidence", "Next Action"],
            morphology_acquisition_gate_rows,
        )
    }
      {
        table(
            [
                "Source",
                "Path",
                "Exists",
                "Files",
                "Book Scope",
                "Morphology Scope",
                "Non-Psalm Morph Books",
                "Authority Use",
            ],
            morphology_acquisition_inventory_rows,
        )
    }
    </section>

    <section>
      <h2>OSHB Whole-Tanakh Alignment Pilot</h2>
      <div class="warning">
        This pilot fetched OSHB WLC XML files into memory for derived alignment
        analysis only. It does not import raw source data, approve source use,
        or authorize morphology-backed translation claims.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["oshb_alignment_pilot_visual_data"]["book_exact_match_rows"],
            label_key="label",
            value_key="value",
            aria_label="Lowest OSHB to UXLC exact verse match percentages by book",
            color="#9b3d3d",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["oshb_alignment_pilot_visual_data"]["book_mismatch_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB to UXLC mismatch verse counts by book",
            color="#7c5b2f",
            limit=20,
        )
    }</div>
      {
        table(
            [
                "Division",
                "Books",
                "OSHB Words",
                "Exact Match",
                "Token Count",
                "Mean Similarity",
                "Mismatch Verses",
            ],
            oshb_alignment_division_rows,
        )
    }
      {
        table(
            [
                "Book",
                "Division",
                "OSHB Words",
                "UXLC Words",
                "Morph",
                "Exact Match",
                "Mean Similarity",
                "Mismatch Verses",
                "Readiness",
            ],
            oshb_alignment_book_rows,
        )
    }
      {
        table(
            [
                "Book",
                "OSIS",
                "Type",
                "OSHB Tokens",
                "UXLC Tokens",
                "Similarity",
                "First Difference",
                "OSHB Window",
                "UXLC Window",
            ],
            oshb_alignment_mismatch_rows,
        )
    }
    </section>

    <section>
      <h2>OSHB Alignment Exception Review</h2>
      <div class="warning">
        The exception workbook is a reviewer queue, not source approval. It keeps
        remaining OSHB-to-UXLC token exceptions visible before any whole-Tanakh
        morphology import, model-training use, display/export use, or canonical
        translation authority claim.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["oshb_exception_review_visual_data"]["book_pressure_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception pressure by book",
            color="#8a6426",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["oshb_exception_review_visual_data"]["sample_class_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception sample classes",
            color="#2f6f73",
            limit=12,
        )
    }</div>
      {
        table(
            ["Gate", "Name", "Status", "Evidence", "Next Action"],
            oshb_exception_gate_rows,
        )
    }
      {
        table(
            [
                "Book",
                "Division",
                "Priority",
                "Pressure",
                "Mismatch Verses",
                "Mismatch %",
                "Token Count Exceptions",
                "Sequence-only",
                "Review Rows",
                "Action",
            ],
            oshb_exception_book_rows,
        )
    }
      {
        table(
            [
                "Book",
                "OSIS",
                "Severity",
                "Class",
                "OSHB Tokens",
                "UXLC Tokens",
                "Delta",
                "Similarity",
                "Review Lanes",
            ],
            oshb_exception_sample_rows,
        )
    }
    </section>

    <section>
      <h2>OSHB Exception Taxonomy and Batches</h2>
      <div class="warning">
        The taxonomy groups exception rows for reviewer routing only. Cause
        families and batches do not approve OSHB source use, import mapping
        rules, model-training data, export/display permissions, or canonical
        translation wording.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["oshb_exception_taxonomy_visual_data"]["cause_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception cause-family counts",
            color="#2f6f73",
            limit=12,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["oshb_exception_taxonomy_visual_data"]["batch_book_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception review batches by book",
            color="#8a6426",
            limit=20,
        )
    }</div>
      {
        table(
            [
                "Cause",
                "Rows",
                "Pct",
                "Critical",
                "High",
                "Medium",
                "Segmentation Markers",
                "Books",
                "Review Intensity",
                "Batching",
            ],
            oshb_taxonomy_cause_rows,
        )
    }
      {
        table(
            [
                "Batch",
                "Book",
                "Cause",
                "Severity",
                "Intensity",
                "Rows",
                "First OSIS",
                "Last OSIS",
                "Review Lanes",
                "Status",
            ],
            oshb_taxonomy_batch_rows,
        )
    }
    </section>

    <section>
      <h2>OSHB Mapping Rule Simulation</h2>
      <div class="warning">
        This simulation estimates which exception rows look rule-routable after
        reviewer design and spot-checking. It does not approve any OSHB source
        use, importer behavior, display/export use, model-training data, or
        translation authority claim.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["oshb_mapping_rule_simulation_visual_data"]["automation_lane_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB mapping-rule simulation automation lanes",
            color="#2f6f73",
            limit=12,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["oshb_mapping_rule_simulation_visual_data"]["rule_group_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB mapping-rule simulation rule groups",
            color="#8a6426",
            limit=12,
        )
    }</div>
      {
        table(
            [
                "Rule",
                "Candidate",
                "Lane",
                "Rows",
                "Pct",
                "High",
                "Medium",
                "Low",
                "Manual",
                "Dominant Cause",
                "Authority",
                "Next Action",
            ],
            oshb_mapping_rule_rows,
        )
    }
      {
        table(
            [
                "Batch",
                "Book",
                "OSIS",
                "Severity",
                "Rule",
                "Lane",
                "Confidence",
                "Review Requirement",
                "Status",
                "Psalm Regression",
                "Aramaic Review",
            ],
            oshb_mapping_packet_rows,
        )
    }
    </section>

    <section>
      <h2>Whole-Tanakh Morphology Unlock Matrix</h2>
      <div class="warning">
        This matrix estimates impact if OSHB-derived whole-Tanakh morphology is
        source-approved, imported through a derived importer, and reviewer-signed.
        It is not source approval, import approval, model-training authorization,
        display/export permission, or canonical translation authority.
      </div>
      {
        metric_cards(
            [
                (
                    "Pilot non-Psalm books",
                    fmt_int(headline["morph_unlock_pilot_non_psalm_books"]),
                    "Current local non-Psalm morphology remains zero.",
                ),
                (
                    "Unlockable units",
                    fmt_int(headline["morph_unlock_unlockable_units"]),
                    (
                        f'{headline[
                            "morph_unlock_projected_review_ready_score_pct"
                        ]:.2f}% '
                        "projected review-ready lane score."
                    ),
                ),
                (
                    "Rule reduction",
                    f'{headline["morph_unlock_rule_reduction_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["morph_unlock_high_confidence_rule_rows"])} '
                        "high-confidence candidate rows."
                    ),
                ),
                (
                    "Manual residual",
                    fmt_int(headline["morph_unlock_manual_residual_rows"]),
                    (
                        f'{fmt_int(headline["morph_unlock_exception_rows"])} '
                        "exception rows remain routed."
                    ),
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["morph_unlock_visual_data"]["top_unit_unlock_rows"],
            label_key="label",
            value_key="value",
            aria_label="Priority units with projected whole-Tanakh morphology unlock delta",
            color="#2f6f73",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["morph_unlock_visual_data"]["top_book_exception_rows"],
            label_key="label",
            value_key="value",
            aria_label="Whole-Tanakh morphology unlock exception pressure by book",
            color="#8a6426",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["morph_unlock_visual_data"]["cause_rows"],
            label_key="label",
            value_key="value",
            aria_label="Whole-Tanakh morphology unlock exception cause rows",
            color="#9b3d3d",
            limit=12,
        )
    }</div>
      {
        table(
            ["Phase", "Name", "Status", "Evidence", "Exit Criterion"],
            morph_unlock_phase_rows,
        )
    }
      {
        table(
            [
                "Ref",
                "Current Score",
                "Current Status",
                "Anchors",
                "High-Value",
                "Three Divisions",
                "Projected Score",
                "Delta",
                "Unlock",
                "Top Outside Books",
            ],
            morph_unlock_unit_rows,
        )
    }
      {
        table(
            [
                "Book",
                "Division",
                "Priority",
                "Pressure",
                "Mismatch Verses",
                "Exact Match",
                "Rule-Routable",
                "Manual",
                "Psalm Anchor Tokens",
                "Action",
            ],
            morph_unlock_book_rows,
        )
    }
      {
        table(
            [
                "Cause",
                "Rows",
                "Pct",
                "Critical",
                "High",
                "Psalm Regression",
                "Aramaic",
                "Segmentation Markers",
                "Batching",
            ],
            morph_unlock_cause_rows,
        )
    }
      {
        table(
            [
                "Rule",
                "Lane",
                "Rows",
                "Pct",
                "High Conf.",
                "Medium Conf.",
                "Low Conf.",
                "Manual",
                "Psalm Regression",
                "Aramaic",
                "Authority",
            ],
            morph_unlock_rule_rows,
        )
    }
    </section>

    <section>
      <h2>Critical Unit Morphology Unlock Plan</h2>
      <div class="warning">
        This is the critical-unit slice of the whole-Tanakh morphology blocker.
        It shows projected review readiness only after source approval, derived
        import, exception adjudication, Psalm regression, and reviewer signoff.
      </div>
      {
        metric_cards(
            [
                (
                    "Morphology state",
                    headline["critical_unit_morphology_unlock_status"],
                    "Current critical-unit morphology authority state.",
                ),
                (
                    "Critical units",
                    fmt_int(headline["critical_unit_morphology_unlock_unit_count"]),
                    "{} projected review-ready after approval/import.".format(
                        fmt_int(
                            headline[
                                "critical_unit_morphology_unlock_projected_ready_count"
                            ]
                        )
                    ),
                ),
                (
                    "Score delta",
                    f'{headline["critical_unit_morphology_unlock_score_delta_pct"]:.2f}%',
                    (
                        f'{headline["critical_unit_morphology_unlock_current_score_pct"]:.2f}% '
                        "current mean whole-Tanakh score."
                    ),
                ),
                (
                    "Non-Psalm import",
                    (
                        f'{fmt_int(headline["critical_unit_morphology_unlock_imported_books"])}/'
                        f'{fmt_int(headline["critical_unit_morphology_unlock_target_books"])}'
                    ),
                    "Current imported non-Psalm morphology books.",
                ),
                (
                    "Exception rows",
                    fmt_int(headline["critical_unit_morphology_unlock_exception_rows"]),
                    (
                        f'{fmt_int(headline["critical_unit_morphology_unlock_review_batches"])} '
                        "review batches."
                    ),
                ),
                (
                    "Top pressure",
                    headline["critical_unit_morphology_unlock_top_unit"],
                    f'Top book {headline["critical_unit_morphology_unlock_top_book"]}.',
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_morphology_unlock_visual_data"]["unit_gap_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit morphology gap risk",
            color="#9b3d3d",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_morphology_unlock_visual_data"]["unit_delta_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit projected morphology unlock delta",
            color="#2f6f73",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["critical_unit_morphology_unlock_visual_data"]["book_anchor_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical unit morphology anchor books",
            color="#7c5b2f",
            limit=20,
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Ref",
                "Morph Risk",
                "Surface Context",
                "Anchors",
                "High-Value",
                "Current",
                "Projected",
                "Delta",
                "Top Books",
                "Status",
            ],
            critical_unit_morphology_unlock_unit_rows,
        )
    }
      {
        table(
            [
                "Book",
                "Division",
                "Critical Anchors",
                "Priority",
                "Mismatch Verses",
                "Exact Match",
                "Pressure",
                "Rule-Routable",
                "Manual",
                "Action",
            ],
            critical_unit_morphology_unlock_book_rows,
        )
    }
      {
        table(
            ["Phase", "Name", "Status", "Complete", "Evidence", "Next Action"],
            critical_unit_morphology_unlock_phase_rows,
        )
    }
      {
        table(
            ["Gate", "Name", "Status", "Current", "Target", "Blocking Gap", "Next Action"],
            critical_unit_morphology_unlock_gate_rows,
        )
    }
    </section>

    <section>
      <h2>Doctoral Bibliography and Provenance</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_bibliography_lanes"],
            label_key="label",
            value_key="authority_score_pct",
            aria_label="Bibliography lane authority scores",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_bibliography_families"],
            label_key="label",
            value_key="unit_count",
            aria_label="Bibliography source-family unit reach",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            ["ID", "Rule", "Allowed Use", "Forbidden Use"],
            bibliography_method_rows,
        )
    }
      {
        table(
            ["Lane", "Evidence", "Authority", "Present", "Candidates", "Status", "Gap"],
            bibliography_lane_rows,
        )
    }
      {
        table(
            ["Class", "ID", "Label", "Tier", "Risk", "Repo", "Authority", "URL"],
            bibliography_source_rows,
        )
    }
      {
        table(
            ["Family", "Status", "Units", "Candidates", "Best Risk", "Roles", "Boundary"],
            bibliography_family_rows,
        )
    }
      {
        table(
            ["ID", "Severity", "Label", "Evidence", "Closing Sources", "Next Action"],
            bibliography_gap_rows,
        )
    }
    </section>

    <section>
      <h2>Doctoral Source Verification</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_source_verification_visual_data"]["status_counts"],
            label_key="status",
            value_key="count",
            aria_label="Live source verification status counts",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_source_verification_visual_data"]["license_risk_counts"],
            label_key="license_risk",
            value_key="count",
            aria_label="Live source verification license risk counts",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "ID",
                "Class",
                "Label",
                "Risk",
                "Status",
                "HTTP",
                "Claim",
                "Terms",
                "URL",
            ],
            source_verification_source_rows,
        )
    }
      {
        table(
            ["ID", "Severity", "Label", "Evidence", "URL", "Next Action"],
            source_verification_gap_rows,
        )
    }
    </section>

    <section>
      <h2>Source Authority Ladder Matrix</h2>
      <div class="warning">
        This matrix joins unit packet families, source candidates, live verification,
        license risk, source approval, packet review, and release blockers. It is
        source-critical routing only; no source approval or translation authority is implied.
      </div>
      {
        metric_cards(
            [
                (
                    "Ladder units",
                    fmt_int(headline["source_authority_ladder_unit_count"]),
                    (
                        f'{fmt_int(headline["source_authority_ladder_critical_gap_count"])} '
                        "critical authority gaps."
                    ),
                ),
                (
                    "Mean readiness",
                    f'{headline["source_authority_ladder_mean_readiness_pct"]:.2f}%',
                    "Reachability, risk, approvals, and review completion.",
                ),
                (
                    "Source families",
                    fmt_int(headline["source_authority_ladder_family_count"]),
                    (
                        f'{fmt_int(headline["source_authority_ladder_family_without_candidate_count"])}'
                        " "
                        "lack candidate sources."
                    ),
                ),
                (
                    "Candidates",
                    fmt_int(headline["source_authority_ladder_candidate_count"]),
                    (
                        f'{fmt_int(headline["source_authority_ladder_candidate_reachable_count"])} '
                        "reachable."
                    ),
                ),
                (
                    "Approvals",
                    fmt_int(headline["source_authority_ladder_source_approval_count"]),
                    "Recorded source approvals.",
                ),
                (
                    "Top gap",
                    headline["source_authority_ladder_top_ref"],
                    f'{float(headline["source_authority_ladder_top_score"]):.2f}.',
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["source_authority_ladder_visual_data"]["top_unit_gap_rows"],
            label_key="label",
            value_key="value",
            aria_label="Source authority ladder top unit gaps",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["source_authority_ladder_visual_data"]["stage_rows"],
            label_key="label",
            value_key="value",
            aria_label="Source authority ladder evidence stages",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["source_authority_ladder_visual_data"]["family_unit_rows"],
            label_key="label",
            value_key="value",
            aria_label="Source authority ladder source families",
            color="#7c5b2f",
        )
    }</div>
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
            source_ladder_unit_rows,
        )
    }
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
            source_ladder_family_rows,
        )
    }
      {
        table(
            [
                "Source ID",
                "Class",
                "Label",
                "Risk",
                "Reachable",
                "Verification",
                "Approved",
                "Generation Policy",
            ],
            source_ladder_source_rows,
        )
    }
      {
        table(
            ["Lane", "Evidence", "Authority", "Present", "Candidates", "Blocked", "Gap"],
            source_ladder_lane_rows,
        )
    }
    </section>

    <section>
      <h2>Unit Authority Heatmap</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_unit_heatmap_lane_summary"],
            label_key="lane_label",
            value_key="mean_score_pct",
            aria_label="Unit authority heatmap mean lane scores",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_unit_heatmap_lane_summary"],
            label_key="lane_label",
            value_key="blocked_unit_count",
            aria_label="Unit authority heatmap blocked units by lane",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            ["Lane", "Required Units", "Mean Score", "Blocked", "Review Ready", "Top Gap"],
            unit_heatmap_lane_rows,
        )
    }
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
            unit_heatmap_queue_rows,
        )
    }
      {
        table(
            [
                "Ref",
                "Unit",
                "Score",
                "Blockers",
                "Required Lanes",
                "Packet Rows",
                "Model Valid %",
                "Weakest Lanes",
            ],
            unit_heatmap_unit_rows,
        )
    }
    </section>

    <section>
      <h2>Doctoral Priority Dossier Atlas</h2>
      <div class="warning">
        Integrated dossiers combine evidence into review assignments. They do
        not approve canonical rendering, source use, reception interpretation,
        or local model output.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_priority_dossier_visual_data"]["dossier_band_counts"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral priority dossier bands",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_priority_dossier_visual_data"]["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral priority dossier top units",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_priority_dossier_visual_data"]["role_workload"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral priority dossier reviewer role workload",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_priority_dossier_visual_data"]["weakest_lane_counts"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral priority dossier weakest lane counts",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_priority_dossier_visual_data"]["domain_counts"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral priority dossier domain counts",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_priority_dossier_visual_data"]["packet_family_counts"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral priority dossier packet family counts",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Ref",
                "Band",
                "Priority",
                "Authority %",
                "Blockers",
                "Weakest Lanes",
                "Roles",
                "Packet Families",
                "Next Action",
            ],
            priority_dossier_unit_rows,
        )
    }
      {
        table(
            ["Role", "Units", "Critical", "Split-Lane", "Mean Priority", "Top Ref"],
            priority_dossier_role_rows,
        )
    }
      {
        table(
            ["Weak Lane", "Units", "Critical", "Mean Priority", "Top Ref", "Next Action"],
            priority_dossier_lane_rows,
        )
    }
      {
        table(
            [
                "Domain",
                "Units",
                "Critical",
                "Split-Lane",
                "Textual Witness",
                "Mean Priority",
                "Top Ref",
            ],
            priority_dossier_domain_rows,
        )
    }
      {
        table(
            ["Packet Family", "Units", "Critical", "Split-Lane", "Mean Priority", "Top Ref"],
            priority_dossier_family_rows,
        )
    }
    </section>

    <section>
      <h2>Doctoral Defense Exhibit Pack</h2>
      <div class="warning">
        These are committee-style evidence exhibits for the strongest translation
        pressure points. They are visual review indexes only: source approval,
        packet review, model certification, and release authority remain separate gates.
      </div>
      {
        metric_cards(
            [
                (
                    "Exhibits",
                    fmt_int(headline["defense_exhibit_unit_count"]),
                    (
                        f'{fmt_int(headline["defense_exhibit_critical_unit_count"])} '
                        "critical exhibit units."
                    ),
                ),
                (
                    "Mean Score",
                    f'{float(headline["defense_exhibit_mean_score"]):.2f}',
                    "Composite cross-domain defense pressure.",
                ),
                (
                    "Mean Authority",
                    f'{float(headline["defense_exhibit_mean_authority_pct"]):.2f}%',
                    "Current authority score for exhibit units.",
                ),
                (
                    "Source Approval",
                    fmt_int(headline["defense_exhibit_source_unapproved_count"]),
                    "Exhibit units lacking source approval.",
                ),
                (
                    "Review Signoff",
                    fmt_int(headline["defense_exhibit_unsigned_review_count"]),
                    "Exhibit units with unsigned packet review.",
                ),
                (
                    "Top Exhibit",
                    headline["defense_exhibit_top_ref"],
                    f'{float(headline["defense_exhibit_top_score"]):.2f}.',
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["defense_exhibit_visual_data"]["top_exhibit_rows"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral defense exhibit top units",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["defense_exhibit_visual_data"]["dimension_rows"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral defense exhibit dimension counts",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["defense_exhibit_visual_data"]["blocker_rows"],
            label_key="label",
            value_key="value",
            aria_label="Doctoral defense exhibit blocker counts",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Ref",
                "Score",
                "Authority",
                "Source Gap",
                "Stage",
                "Blocker",
                "Approvals",
                "Review Rows",
                "Completed",
                "Clean Model",
                "Roles",
            ],
            defense_exhibit_unit_rows,
        )
    }
      {
        table(
            ["Dimension", "Units", "Pct", "Top Ref", "Top Score"],
            defense_exhibit_dimension_rows,
        )
    }
      {
        table(
            ["Role", "Units", "Critical", "Mean Score", "Top Ref"],
            defense_exhibit_role_rows,
        )
    }
    </section>

    <section>
      <h2>Hebrew Token Defense Matrix</h2>
      <div class="warning">
        Token rows are evidence indices for review. They do not approve source
        use, adjudicate interpretation, certify model output, or authorize
        canonical wording.
      </div>
      {
        metric_cards(
            [
                (
                    "Tokens",
                    fmt_int(headline["hebrew_token_defense_token_count"]),
                    (
                        f'{fmt_int(headline["hebrew_token_defense_unit_count"])} '
                        "defense exhibit units."
                    ),
                ),
                (
                    "Critical Tokens",
                    fmt_int(headline["hebrew_token_defense_critical_token_count"]),
                    (
                        "Defense score >= "
                        f'{float(headline["hebrew_token_defense_critical_threshold"]):.0f}.'
                    ),
                ),
                (
                    "Anchors",
                    fmt_int(headline["hebrew_token_defense_anchor_token_count"]),
                    (
                        f'{fmt_int(headline["hebrew_token_defense_high_anchor_token_count"])} '
                        "high-strength anchors."
                    ),
                ),
                (
                    "Culture Tags",
                    fmt_int(headline["hebrew_token_defense_cultural_domain_token_count"]),
                    "Tokens with cultural-domain evidence.",
                ),
                (
                    "Semantic Gaps",
                    fmt_int(headline["hebrew_token_defense_missing_semantic_role_token_count"]),
                    (
                        f'{fmt_int(headline["hebrew_token_defense_missing_referent_token_count"])} '
                        "also missing referent enrichment."
                    ),
                ),
                (
                    "Top Token",
                    headline["hebrew_token_defense_top_token_ref"],
                    (
                        f'{headline["hebrew_token_defense_top_token_surface"]} '
                        f'{float(headline["hebrew_token_defense_top_token_score"]):.2f}.'
                    ),
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["hebrew_token_defense_visual_data"]["top_token_rows"],
            label_key="label",
            value_key="value",
            aria_label="Hebrew token defense top tokens",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["hebrew_token_defense_visual_data"]["unit_mean_rows"],
            label_key="label",
            value_key="value",
            aria_label="Hebrew token defense unit means",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["hebrew_token_defense_visual_data"]["control_rows"],
            label_key="label",
            value_key="value",
            aria_label="Hebrew token defense control distribution",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Ref",
                "Token",
                "Surface",
                "Lemma",
                "Strong",
                "Gloss",
                "POS",
                "Morph",
                "Score",
                "Anchor",
                "Outside Psalms",
                "Culture",
                "Missing",
                "Controls",
                "Top Flags",
            ],
            hebrew_token_defense_token_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Tokens",
                "Mean",
                "Max",
                "Critical",
                "Anchors",
                "Culture",
                "Divine",
                "Semantic Gaps",
                "Referent Gaps",
                "Top Surfaces",
                "Top Glosses",
            ],
            hebrew_token_defense_unit_rows,
        )
    }
      {
        table(
            ["Control", "Tokens", "Pct", "Top Ref", "Top Token", "Surface", "Top Score"],
            hebrew_token_defense_control_rows,
        )
    }
    </section>

    <section>
      <h2>Semantic/Referent Enrichment Roadmap</h2>
      <div class="warning">
        This queue prioritizes missing semantic-role, referent, syntax, stem, and
        discourse enrichment. It is not imported source data, source approval,
        reviewer adjudication, canonical wording, model approval, or release authority.
      </div>
      {
        metric_cards(
            [
                (
                    "Tokens",
                    fmt_int(headline["semantic_referent_token_count"]),
                    (
                        f'{fmt_int(headline["semantic_referent_unit_count"])} '
                        "Psalm units surveyed."
                    ),
                ),
                (
                    "Critical Tokens",
                    fmt_int(headline["semantic_referent_critical_token_count"]),
                    (
                        "Score >= "
                        f'{float(headline["semantic_referent_critical_threshold"]):.0f}; '
                        f'{fmt_int(headline["semantic_referent_critical_unit_count"])} units.'
                    ),
                ),
                (
                    "Semantic Coverage",
                    f'{headline["semantic_referent_semantic_role_coverage_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["semantic_referent_missing_semantic_role_count"])} '
                        "tokens missing semantic roles."
                    ),
                ),
                (
                    "Referent Coverage",
                    f'{headline["semantic_referent_referent_coverage_pct"]:.2f}%',
                    (
                        f'{fmt_int(headline["semantic_referent_missing_referent_count"])} '
                        "tokens missing referents."
                    ),
                ),
                (
                    "Referent Pressure",
                    fmt_int(headline["semantic_referent_suffix_pronoun_count"]),
                    "Suffix-pronoun tokens need antecedent review.",
                ),
                (
                    "Top Token",
                    headline["semantic_referent_top_token_ref"],
                    (
                        f'{headline["semantic_referent_top_token_surface"]} '
                        f'{float(headline["semantic_referent_top_token_score"]):.2f}.'
                    ),
                ),
            ]
        )
    }
      <div class="chart">{
        svg_horizontal_bars(
            evidence["semantic_referent_visual_data"]["top_token_rows"],
            label_key="label",
            value_key="value",
            aria_label="Semantic referent enrichment top tokens",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["semantic_referent_visual_data"]["top_unit_rows"],
            label_key="label",
            value_key="value",
            aria_label="Semantic referent enrichment top units",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["semantic_referent_visual_data"]["lane_rows"],
            label_key="label",
            value_key="value",
            aria_label="Semantic referent critical tokens by lane",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Ref",
                "Token",
                "Surface",
                "Lemma",
                "Strong",
                "Gloss",
                "POS",
                "Morph",
                "Score",
                "Anchor",
                "Outside Psalms",
                "Culture",
                "Missing",
                "Lanes",
                "Next Action",
            ],
            semantic_referent_token_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Tokens",
                "Max Score",
                "Critical",
                "Suffix",
                "Verbs",
                "Anchors",
                "Culture",
                "Divine",
                "Primary Lanes",
                "Top Surfaces",
            ],
            semantic_referent_unit_rows,
        )
    }
      {
        table(
            [
                "Lane",
                "Tokens",
                "Pct",
                "Units",
                "Critical",
                "Mean Score",
                "Top Ref",
                "Surface",
                "Roles",
                "Next Action",
            ],
            semantic_referent_lane_rows,
        )
    }
      {
        table(
            ["Field", "Missing", "Missing %", "Coverage %", "Top Ref", "Surface", "Effect"],
            semantic_referent_gap_rows,
        )
    }
      {
        table(
            ["Phase", "Label", "Status", "Tokens", "Units", "Evidence", "Next Action"],
            semantic_referent_phase_rows,
        )
    }
    </section>

    <section>
      <h2>Review Signoff Workbook</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["review_signoff_roles"],
            label_key="reviewer_role",
            value_key="total_review_row_count",
            aria_label="Contextual review signoff rows by reviewer role",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["review_signoff_units"],
            label_key="ref",
            value_key="packet_review_row_count",
            aria_label="Source packet review rows by priority unit",
            color="#7c5b2f",
            limit=15,
        )
    }</div>
      {
        table(
            ["Role", "Total", "Packet Rows", "Source Rows", "Units", "Families", "Status"],
            review_signoff_role_rows,
        )
    }
      {
        table(
            ["Ref", "Unit", "Score", "Band", "Review Rows", "Roles"],
            review_signoff_unit_rows,
        )
      }
      {table(["Gate", "Score", "Status", "Evidence", "Next Action"], review_signoff_gate_rows)}
    </section>

    <section>
      <h2>Authority Critical Path</h2>
      <div class="warning">
        This section orders blocker-clearance work only. It does not approve
        source use, complete human review, approve model outputs, import
        morphology, or authorize canonical translation wording.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["authority_path_visual_data"]["phase_readiness_rows"],
            label_key="label",
            value_key="value",
            aria_label="Authority critical path phase readiness",
            color="#2f6f73",
            limit=10,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["authority_path_visual_data"]["phase_work_rows"],
            label_key="label",
            value_key="value",
            aria_label="Authority critical path phase work units",
            color="#8a6426",
            limit=10,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["authority_path_visual_data"]["unit_gap_rows"],
            label_key="label",
            value_key="value",
            aria_label="Authority critical path top unit gaps",
            color="#9b3d3d",
            limit=15,
        )
    }</div>
      {
        table(
            [
                "Phase",
                "Name",
                "Depends On",
                "Status",
                "Readiness",
                "Work Units",
                "Blockers",
                "Next Action",
            ],
            authority_path_phase_rows,
        )
    }
      {
        table(
            [
                "Role",
                "Rows",
                "Critical",
                "Highest",
                "Critical/Highest",
                "Units",
                "Status",
            ],
            authority_path_role_rows,
        )
    }
      {
        table(
            [
                "Rank",
                "Ref",
                "Authority Score",
                "Gap Score",
                "Blocking Lanes",
                "Review Rows",
                "Weakest Lanes",
                "Next Action",
            ],
            authority_path_unit_rows,
        )
    }
      {
        table(
            ["Source", "Gate", "Status", "Score", "Evidence", "Next Action"],
            authority_path_gate_rows,
        )
    }
    </section>

    <section>
      <h2>Doctoral Translation Synthesis</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_requirement_rows"],
            label_key="requirement_id",
            value_key="score_pct",
            aria_label="Doctoral synthesis requirement scores",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["doctoral_visual_data"]["contextual_pressure_rows"],
            label_key="pressure",
            value_key="unit_count",
            aria_label="Doctoral synthesis contextual pressure counts",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            ["ID", "Requirement", "Score", "Status", "Evidence", "Blocking Gap"],
            doctoral_requirement_rows,
        )
    }
      {
        table(
            ["ID", "Severity", "Blocker", "Evidence", "Requirements", "Next Action"],
            doctoral_blocker_rows,
        )
    }
      {
        table(
            ["ID", "Boundary", "Rule", "Authority Effect", "Artifact"],
            doctoral_boundary_rows,
        )
    }
      {
        table(
            ["Rank", "Ref", "Unit", "Score", "Band", "Review Rows", "Roles"],
            doctoral_priority_unit_rows,
        )
    }
    </section>

    <section>
      <h2>Authority Gates</h2>
      <div class="chart">{
        svg_horizontal_bars(
            evidence["authority_gate_rows"],
            label_key="label",
            value_key="score_pct",
            aria_label="Authority readiness scores by gate",
            color="#2f6f73",
        )
    }</div>
      {table(["Gate", "Score", "Status", "Blocking Gap"], authority_gate_rows)}
    </section>

    <section>
      <h2>Open Gaps</h2>
      {table(["Gap", "Evidence"], gap_rows)}
    </section>
  </main>
</body>
</html>
"""
    # fmt: on


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the integrated research portfolio dashboard."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dashboard = build_dashboard()
    write_json(args.json_output, dashboard)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(dashboard), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
