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

CORPUS_PROFILE_PATH = REPORT_ROOT / "psalms_corpus_profile.json"
LEXEME_READINESS_PATH = REPORT_ROOT / "lexeme_context_readiness.json"
WHOLE_TANAKH_MORPHOLOGY_GAP_PATH = REPORT_ROOT / "whole_tanakh_morphology_gap.json"
TRANSLATION_CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
CANONICAL_CONTEXT_NETWORK_PATH = REPORT_ROOT / "canonical_context_network.json"
WITNESS_READINESS_PATH = REPORT_ROOT / "witness_reception_readiness.json"
RECEPTION_BOUNDARY_PATH = REPORT_ROOT / "reception_interpretation_boundary.json"
ATLAS_PATH = REPORT_ROOT / "contextual_pressure_atlas.json"
COVERAGE_PATH = REPORT_ROOT / "contextual_benchmark_coverage.json"
EXPANDED_SUITE_PATH = REPORT_ROOT / "contextual_expanded_benchmark_suite.json"
EXPANDED_CROSS_EXAM_PATH = REPORT_ROOT / "contextual_expanded_benchmark_cross_exam_protocol.json"
EXPANDED_REVIEW_PATH = REPORT_ROOT / "contextual_expanded_benchmark_review_signoff_plan.json"
INTEGRATED_REAL_AUDIT_PATH = REPORT_ROOT / "integrated_benchmark_result_audit.json"
MODEL_EVIDENCE_GAP_PATH = REPORT_ROOT / "model_evidence_gap_report.json"
MODEL_OUTPUT_QUALITY_TRIAGE_PATH = REPORT_ROOT / "model_output_quality_triage.json"
LAYER_CONSISTENCY_PATH = REPORT_ROOT / "layer_consistency_report.json"
LAYER_REMEDIATION_PATH = REPORT_ROOT / "layer_remediation_plan.json"
LAYER_REMEDIATION_EXPERIMENT_PATH = REPORT_ROOT / "layer_remediation_experiment_report.json"
BASE_REAL_AUDIT_PATH = REPORT_ROOT / "local_model_benchmark_result_audit.json"
RUNTIME_PATH = REPORT_ROOT / "local_runtime_readiness.json"
ASSET_PATH = REPORT_ROOT / "local_model_asset_inventory.json"
DASHBOARD_PATH = REPORT_ROOT / "research_portfolio_dashboard.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "scholarly_authority_readiness.json"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "scholarly_authority_gate_rows.csv"
DEFAULT_RISK_CSV_OUTPUT = REPORT_ROOT / "scholarly_authority_risk_register.csv"
DEFAULT_DOMAIN_CSV_OUTPUT = REPORT_ROOT / "scholarly_authority_domain_coverage.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "scholarly_authority_readiness.html"


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


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def field_coverage(corpus: dict[str, Any], field: str) -> float:
    for row in corpus.get("enrichment", {}).get("token_field_coverage", []):
        if row.get("field") == field:
            return float(row.get("pct_present") or 0)
    return 0.0


def expanded_unit_ids(expanded: dict[str, Any]) -> set[str]:
    return {str(task["unit_id"]) for task in expanded.get("tasks", [])}


def projected_domain_rows(
    coverage: dict[str, Any],
    expanded_units: set[str],
) -> list[dict[str, Any]]:
    domain_units: dict[str, set[str]] = {}
    integrated_units: dict[str, set[str]] = {}
    expanded_domain_units: dict[str, set[str]] = {}
    for row in coverage.get("unit_coverage_rows", []):
        unit_id = str(row["unit_id"])
        for domain in row.get("domains", []):
            domain_text = str(domain)
            domain_units.setdefault(domain_text, set()).add(unit_id)
            if row.get("covered_by_integrated_benchmark"):
                integrated_units.setdefault(domain_text, set()).add(unit_id)
            if unit_id in expanded_units:
                expanded_domain_units.setdefault(domain_text, set()).add(unit_id)
    rows = []
    for domain, units in domain_units.items():
        total = len(units)
        integrated_count = len(integrated_units.get(domain, set()))
        expanded_count = len(expanded_domain_units.get(domain, set()))
        rows.append(
            {
                "domain": domain,
                "unit_count": total,
                "integrated_covered_count": integrated_count,
                "expanded_covered_count": expanded_count,
                "expanded_uncovered_count": max(0, total - expanded_count),
                "integrated_coverage_pct": pct(integrated_count, total),
                "expanded_coverage_pct": pct(expanded_count, total),
                "coverage_gain_pct": round(
                    pct(expanded_count, total) - pct(integrated_count, total),
                    2,
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            float(row["expanded_coverage_pct"]),
            -int(row["unit_count"]),
        ),
    )


def status_for_score(score: float, gate: str) -> str:
    if gate in {"real_model_evidence", "human_signoff", "release_authority"}:
        if score == 0:
            return "not started"
    if score >= 85:
        return "strong"
    if score >= 70:
        return "usable with caveats"
    if score >= 45:
        return "prototype"
    if score > 0:
        return "weak"
    return "not started"


def gate_row(
    *,
    gate: str,
    label: str,
    weight: int,
    score_pct: float,
    evidence: str,
    blocking_gap: str,
    next_action: str,
) -> dict[str, Any]:
    score = clamp(score_pct)
    return {
        "gate": gate,
        "label": label,
        "weight": weight,
        "score_pct": score,
        "weighted_points": round(score * weight / 100, 2),
        "status": status_for_score(score, gate),
        "evidence": evidence,
        "blocking_gap": blocking_gap,
        "next_action": next_action,
    }


def build_gate_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    corpus = data["corpus_profile"]
    corpus_summary = corpus["summary"]
    lexeme = data["lexeme_readiness"]["summary"]
    morph_gap = data["whole_tanakh_morphology_gap"]["summary"]
    canonical_context = data["canonical_context_network"]["summary"]
    witness = data["witness_readiness"]["summary"]
    reception_boundary = data["reception_boundary"]["summary"]
    claim_matrix = data["translation_claim_matrix"]["summary"]
    atlas = data["contextual_pressure_atlas"]["summary"]
    coverage = data["contextual_benchmark_coverage"]["summary"]
    expanded = data["expanded_suite"]["summary"]
    cross_exam = data["expanded_cross_exam"]["summary"]
    review = data["expanded_review"]["summary"]
    integrated_real = data["integrated_real_audit"]["summary"]
    model_gap = data["model_evidence_gap"]["summary"]
    quality_triage = data["model_output_quality_triage"]["summary"]
    layer_consistency = data["layer_consistency"]["summary"]
    base_real = data["base_real_audit"]["summary"]
    runtime = data["runtime"]["summary"]
    assets = data["asset_inventory"]["summary"]

    lexical_score = mean(
        [
            field_coverage(corpus, "lemma"),
            field_coverage(corpus, "strong"),
            field_coverage(corpus, "morph_code"),
            field_coverage(corpus, "part_of_speech"),
            field_coverage(corpus, "word_sense"),
            field_coverage(corpus, "display_gloss"),
            field_coverage(corpus, "stem"),
            field_coverage(corpus, "syntax_role"),
            field_coverage(corpus, "semantic_role"),
            field_coverage(corpus, "referent"),
        ]
    )
    tanakh_score = mean(
        [
            float(lexeme["surface_outside_context_token_pct"]),
            float(lexeme["lemma_form_outside_context_token_pct"]),
            float(canonical_context["surface_outside_context_token_pct"]),
            float(canonical_context["content_token_outside_context_pct"]),
            float(canonical_context["units_with_three_division_evidence_pct"]),
            float(morph_gap["outside_strong_context_token_pct"]),
            100.0 if lexeme["whole_tanakh_lemma_index_available"] else 0.0,
        ]
    )
    witness_score = mean(
        [
            float(witness["lxx_coverage_pct"]),
            float(witness["english_witness_coverage_pct"]),
            float(witness["complete_expected_witness_set_pct"]),
            pct(
                witness["integrated_reception_sensitive_units"],
                max(1, witness["atlas_reception_sensitive_units"]),
            ),
            pct(
                witness["integrated_textual_witness_units"],
                max(1, witness["atlas_textual_witness_pressure_units"]),
            ),
            float(reception_boundary["complete_witness_set_pct"]),
            pct(
                reception_boundary["jewish_christian_separation_control_unit_count"],
                max(1, reception_boundary["reception_sensitive_unit_count"]),
            ),
            pct(
                reception_boundary["witness_boundary_control_unit_count"],
                max(1, reception_boundary["unit_count"]),
            ),
        ]
    )
    context_score = mean(
        [
            float(coverage["high_pressure_coverage_pct"]),
            float(coverage["reception_sensitive_coverage_pct"]),
            float(coverage["textual_witness_pressure_coverage_pct"]),
            float(coverage["ancient_culture_coverage_pct"]),
            float(coverage["source_theology_control_coverage_pct"]),
            float(expanded["projected_atlas_coverage_after_pct"]),
        ]
    )
    expected_packets = int(expanded["task_count"]) * 3
    benchmark_score = mean(
        [
            float(expanded["projected_atlas_coverage_after_pct"]),
            100.0 if int(cross_exam["packet_count"]) == expected_packets else 0.0,
            100.0 if int(expanded["planned_model_count"]) >= 5 else 60.0,
            100.0 if int(review["projected_human_review_rows"]) > 0 else 0.0,
        ]
    )
    runtime_score = mean(
        [
            float(runtime["readiness_gate_pass_pct"]),
            float(assets["recommended_asset_coverage_pct"]),
            pct(
                runtime["qlora_possible_model_count"],
                max(1, assets["recommended_model_count"]),
            ),
        ]
    )
    source_anchor_issues = int(integrated_real.get("source_anchor_issue_count") or 0)
    layer_valid_pairs = max(1, int(layer_consistency["schema_valid_pair_count"]))
    layer_divine_pairs = max(1, int(layer_consistency["divine_name_pair_count"]))
    layer_contract_score = mean(
        [
            max(
                0.0,
                100.0
                - pct(
                    layer_consistency["weak_layer_differentiation_pair_count"],
                    layer_valid_pairs,
                ),
            ),
            max(
                0.0,
                100.0
                - pct(
                    layer_consistency["exact_duplicate_pair_count"],
                    layer_valid_pairs,
                ),
            ),
            max(
                0.0,
                100.0
                - pct(
                    layer_consistency["divine_name_inconsistent_pair_count"],
                    layer_divine_pairs,
                ),
            ),
        ]
    )
    real_score = mean(
        [
            pct(
                integrated_real["submitted_expected_result_count"],
                max(1, integrated_real["expected_result_count"]),
            ),
            float(integrated_real["schema_valid_pct"]),
            float(model_gap["schema_valid_expected_pct"]),
            pct(
                model_gap["unit_with_schema_valid_count"],
                max(1, model_gap["expanded_unit_count"]),
            ),
            pct(
                quality_triage["schema_valid_candidate_count"],
                max(1, quality_triage["candidate_row_count"]),
            ),
            max(
                0.0,
                100.0 - float(quality_triage["mean_valid_missing_source_keyword_pct"]),
            ),
            layer_contract_score,
            0.0 if source_anchor_issues else 100.0,
            pct(
                base_real["submitted_expected_result_count"],
                max(1, base_real["expected_result_count"]),
            ),
        ]
    )
    real_blocking_gap = (
        "Real benchmark coverage is still tiny and current valid rows have source-anchor issues."
        if source_anchor_issues
        else (
            "Real benchmark coverage is still tiny; most integrated and "
            "expanded model-task rows remain unsubmitted."
        )
    )
    rows = [
        gate_row(
            gate="source_corpus_governance",
            label="Source Corpus and Policy Control",
            weight=10,
            score_pct=95.0 if corpus_summary["unit_count"] else 0.0,
            evidence=(
                f"{fmt_int(corpus_summary['unit_count'])} Psalm units, "
                f"{fmt_int(corpus_summary['total_token_records'])} token records, "
                f"{fmt_int(corpus_summary['witness_records'])} witness records."
            ),
            blocking_gap="No canonical renderings exist yet, so authority cannot be release-level.",
            next_action="Keep model outputs as alternates until review/audit records exist.",
        ),
        gate_row(
            gate="lexical_morphology_traceability",
            label="Lexical and Morphological Traceability",
            weight=13,
            score_pct=lexical_score,
            evidence=(
                f"Lemma {field_coverage(corpus, 'lemma'):.2f}%, "
                f"Strong {field_coverage(corpus, 'strong'):.2f}%, "
                f"syntax_role {field_coverage(corpus, 'syntax_role'):.2f}%."
            ),
            blocking_gap="semantic_role and referent coverage are 0.00%.",
            next_action="Add or derive semantic-role/referent evidence before high-trust claims.",
        ),
        gate_row(
            gate="whole_tanakh_context",
            label="Whole-Tanakh Context Control",
            weight=12,
            score_pct=tanakh_score,
            evidence=(
                "Surface outside-Psalms context "
                f"{lexeme['surface_outside_context_token_pct']:.2f}%; "
                f"lemma-form outside context "
                f"{lexeme['lemma_form_outside_context_token_pct']:.2f}%; "
                f"{canonical_context['unit_count']} expanded units in the "
                "canonical context network; "
                f"{morph_gap['local_non_psalm_books_with_hebrew_morphology']} "
                "non-Psalm books with local Hebrew morphology."
            ),
            blocking_gap=(
                "Whole-Tanakh Strong/lemma index is not available; outside-Psalms "
                "context is surface-form evidence, not lexeme proof."
            ),
            next_action="Build lemma-aware Tanakh retrieval instead of relying on surface forms.",
        ),
        gate_row(
            gate="witness_reception_provenance",
            label="Witness and Reception Provenance",
            weight=12,
            score_pct=witness_score,
            evidence=(
                f"LXX {witness['lxx_coverage_pct']:.2f}%, English witnesses "
                f"{witness['english_witness_coverage_pct']:.2f}%, "
                f"{reception_boundary['reception_sensitive_unit_count']} expanded "
                "reception-sensitive units with boundary controls."
            ),
            blocking_gap="English witnesses are blocked as generation sources by policy.",
            next_action="Use witnesses only as labeled evidence and audit leakage into outputs.",
        ),
        gate_row(
            gate="context_culture_atlas_coverage",
            label="Culture, Canon, Text, and Reception Atlas Coverage",
            weight=13,
            score_pct=context_score,
            evidence=(
                f"{atlas['ancient_context_unit_count']} ancient-context units in atlas; "
                "expanded suite projects "
                f"{expanded['projected_atlas_coverage_after_pct']:.2f}% coverage; "
                f"{claim_matrix['high_risk_unit_count']} high-risk claim-control rows."
            ),
            blocking_gap=(
                f"{expanded['contextual_gap_remaining_unit_count']} atlas units remain uncovered "
                "after the gap supplement."
            ),
            next_action="Generate the next contextual-gap supplement for remaining atlas breadth.",
        ),
        gate_row(
            gate="benchmark_cross_exam_plumbing",
            label="Benchmark and Cross-Examination Plumbing",
            weight=12,
            score_pct=benchmark_score,
            evidence=(
                f"{expanded['task_count']} expanded tasks, "
                f"{cross_exam['packet_count']} judge packets, "
                f"{cross_exam['execution_row_count']} execution rows."
            ),
            blocking_gap="Plumbing is ready, but it is not model quality evidence.",
            next_action="Run real local model rows across the expanded suite.",
        ),
        gate_row(
            gate="local_runtime_assets",
            label="Local Runtime and Asset Readiness",
            weight=8,
            score_pct=runtime_score,
            evidence=(
                f"{runtime['readiness_gate_pass_count']}/{runtime['readiness_gate_count']} "
                f"runtime gates pass; {assets['recommended_models_with_local_assets']} "
                f"of {assets['recommended_model_count']} recommended models have local assets."
            ),
            blocking_gap="Recommended local asset coverage is incomplete.",
            next_action="Download or quantize missing recommended model assets.",
        ),
        gate_row(
            gate="real_model_evidence",
            label="Real Local Model Evidence",
            weight=10,
            score_pct=real_score,
            evidence=(
                f"{integrated_real['submitted_result_count']} submitted integrated real rows "
                f"of {integrated_real['expected_result_count']} expected; "
                f"{model_gap['unit_without_schema_valid_count']} of "
                f"{model_gap['expanded_unit_count']} expanded units lack "
                f"schema-valid rows; {quality_triage['schema_valid_candidate_count']} "
                f"of {quality_triage['candidate_row_count']} candidate rows are "
                "eligible for text triage; layer audit has "
                f"{layer_consistency['exact_duplicate_pair_count']} exact "
                "gloss/literal duplicates and "
                f"{layer_consistency['weak_layer_differentiation_pair_count']} "
                "weak differentiation pairs; "
                f"{source_anchor_issues} source-anchor issues."
            ),
            blocking_gap=real_blocking_gap,
            next_action=(
                "Run the local bake-off, score real JSONL outputs, and route "
                "triaged rows to human reviewers."
            ),
        ),
        gate_row(
            gate="human_signoff",
            label="Human Review and Signoff Evidence",
            weight=7,
            score_pct=0.0,
            evidence=(
                f"{review['projected_human_review_rows']} expanded-suite human review rows "
                "are projected; completed rows are not present."
            ),
            blocking_gap="No completed human review/signoff rows exist.",
            next_action=(
                "Route scored model outputs to Hebrew, lexical, alignment, "
                "lyric, and theology reviewers."
            ),
        ),
        gate_row(
            gate="release_authority",
            label="Release-Level Translation Authority",
            weight=3,
            score_pct=0.0,
            evidence=(
                f"{corpus_summary['units_with_renderings']} units currently have renderings "
                "in canonical content."
            ),
            blocking_gap="No canonical renderings or release signoff exist.",
            next_action=(
                "Accept model output only as reviewed alternates before canonical promotion."
            ),
        ),
    ]
    return rows


def risk_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    lexeme = data["lexeme_readiness"]["summary"]
    morph_gap = data["whole_tanakh_morphology_gap"]["summary"]
    canonical_context = data["canonical_context_network"]["summary"]
    reception_boundary = data["reception_boundary"]["summary"]
    claim_matrix = data["translation_claim_matrix"]["summary"]
    witness = data["witness_readiness"]["summary"]
    coverage = data["contextual_benchmark_coverage"]["summary"]
    expanded = data["expanded_suite"]["summary"]
    integrated_real = data["integrated_real_audit"]["summary"]
    model_gap = data["model_evidence_gap"]["summary"]
    quality_triage = data["model_output_quality_triage"]["summary"]
    layer_consistency = data["layer_consistency"]["summary"]
    layer_remediation = data["layer_remediation"]["summary"]
    layer_experiment = data["layer_remediation_experiment"]["summary"]
    review = data["expanded_review"]["summary"]
    assets = data["asset_inventory"]["summary"]
    real_submitted = int(integrated_real["submitted_result_count"])
    return [
        {
            "risk": (
                "Real local model benchmark evidence is still too sparse"
                if real_submitted
                else "No real local model benchmark evidence yet"
            ),
            "severity": "high" if real_submitted else "critical",
            "evidence": (
                f"{integrated_real['submitted_result_count']} submitted rows; "
                f"{integrated_real['missing_expected_result_count']} missing expected rows; "
                f"{model_gap['high_risk_without_schema_valid_count']} high-risk "
                "expanded units lack schema-valid real output."
            ),
            "mitigation": "Run the seven-model bake-off and score all JSONL outputs.",
        },
        {
            "risk": "Automated quality triage is not human translation signoff",
            "severity": "high",
            "evidence": (
                f"{quality_triage['schema_valid_candidate_count']} schema-valid "
                f"candidate rows; {quality_triage['contextual_review_required_count']} "
                "valid rows carry contextual review flags; "
                f"{quality_triage['structure_failure_count']} structure failures."
            ),
            "mitigation": (
                "Use the triage report to prioritize Hebrew, lexical, alignment, "
                "theology, and reception-boundary review."
            ),
        },
        {
            "risk": "Layer contracts are not yet reliable in real model outputs",
            "severity": "high",
            "evidence": (
                f"{layer_consistency['paired_unit_model_count']} paired "
                "gloss/literal rows; "
                f"{layer_consistency['exact_duplicate_pair_count']} exact "
                "duplicates; "
                f"{layer_consistency['weak_layer_differentiation_pair_count']} "
                "weak differentiation pairs; mean word overlap "
                f"{layer_consistency['mean_word_jaccard_pct']:.2f}%."
            ),
            "mitigation": (
                "Tune layer prompts and structured decoding, then re-run paired "
                "gloss/literal audits before reviewer signoff."
            ),
        },
        {
            "risk": "Layer remediation has not yet been proven by rerun evidence",
            "severity": "high",
            "evidence": (
                f"{layer_remediation['action_count']} remediation actions and "
                f"{layer_remediation['retry_task_count']} retry tasks are defined; "
                "runner layer contracts are "
                + ("present" if layer_remediation["runner_contract_ready"] else "missing")
                + f"; {layer_experiment['generated_attempt_count']} retry attempts "
                "have been audited, with failed gates: "
                + ", ".join(layer_experiment["failed_gates"])
                + "."
            ),
            "mitigation": (
                "Do not run the full retry queue until the single-pair weak "
                "differentiation gate passes; then rescore and regenerate the layer audit."
            ),
        },
        {
            "risk": "No completed human signoff evidence",
            "severity": "critical",
            "evidence": (
                f"{review['projected_human_review_rows']} review rows are projected, "
                "but completed rows are absent."
            ),
            "mitigation": (
                "Collect role-specific Hebrew, lexical, alignment, lyric, and theology decisions."
            ),
        },
        {
            "risk": "Whole-Tanakh context is still form-level",
            "severity": "high",
            "evidence": (
                f"Surface outside context {lexeme['surface_outside_context_token_pct']:.2f}%; "
                f"canonical context network covers {canonical_context['unit_count']} units; "
                f"{morph_gap['local_non_psalm_books_with_hebrew_morphology']} non-Psalm "
                "books have local Hebrew morphology."
            ),
            "mitigation": "Build Strong/lemma-level Tanakh context retrieval with cited examples.",
        },
        {
            "risk": "Cross-canon retrieval can overstate shared sense",
            "severity": "high",
            "evidence": (
                f"{canonical_context['review_queue_unit_count']} context-network units "
                "carry review flags even though retrieval coverage is high."
            ),
            "mitigation": (
                "Require reviewer notes for high-frequency forms, intertexts, "
                "and reception-sensitive claims."
            ),
        },
        {
            "risk": "Semantic-role and referent fields are absent",
            "severity": "high",
            "evidence": (
                f"semantic_role {lexeme['semantic_role_coverage_pct']:.2f}%; "
                f"referent {lexeme['referent_coverage_pct']:.2f}%."
            ),
            "mitigation": "Add semantic/referent enrichment or require human reviewer flags.",
        },
        {
            "risk": "Contextual atlas breadth remains incomplete",
            "severity": "high",
            "evidence": (
                f"Integrated coverage {coverage['coverage_pct']:.2f}%; expanded projected "
                f"coverage {expanded['projected_atlas_coverage_after_pct']:.2f}%."
            ),
            "mitigation": "Generate another supplement for the remaining 44 uncovered atlas units.",
        },
        {
            "risk": "English witness leakage into generation",
            "severity": "medium",
            "evidence": (
                "Generation-blocked witness sources in use: "
                + ", ".join(witness["witness_sources_not_allowed_for_generation"])
                + "."
            ),
            "mitigation": (
                "Keep witnesses labeled and audit translation_basis plus wording similarity."
            ),
        },
        {
            "risk": "Reception boundary controls are planned but not signed off",
            "severity": "medium",
            "evidence": (
                f"{reception_boundary['reception_sensitive_unit_count']} expanded units "
                "require reception separation; claim matrix maps "
                f"{claim_matrix['high_risk_unit_count']} high-risk claim rows; "
                "completed reviewer signoff is absent."
            ),
            "mitigation": (
                "Score model rationales for Jewish/Christian separation and keep "
                "reception claims outside translation text."
            ),
        },
        {
            "risk": "Recommended model assets are incomplete locally",
            "severity": "medium",
            "evidence": (
                f"{assets['recommended_models_with_local_assets']} of "
                f"{assets['recommended_model_count']} recommended models have local assets."
            ),
            "mitigation": (
                "Acquire missing quantized or full precision assets before full bake-off."
            ),
        },
    ]


def build_report(
    corpus_profile_path: Path,
    lexeme_readiness_path: Path,
    whole_tanakh_morphology_gap_path: Path,
    translation_claim_matrix_path: Path,
    canonical_context_network_path: Path,
    witness_readiness_path: Path,
    reception_boundary_path: Path,
    atlas_path: Path,
    coverage_path: Path,
    expanded_suite_path: Path,
    expanded_cross_exam_path: Path,
    expanded_review_path: Path,
    integrated_real_audit_path: Path,
    model_evidence_gap_path: Path,
    model_output_quality_triage_path: Path,
    layer_consistency_path: Path,
    layer_remediation_path: Path,
    layer_remediation_experiment_path: Path,
    base_real_audit_path: Path,
    runtime_path: Path,
    asset_path: Path,
    dashboard_path: Path,
) -> dict[str, Any]:
    data = {
        "corpus_profile": load_json(corpus_profile_path),
        "lexeme_readiness": load_json(lexeme_readiness_path),
        "whole_tanakh_morphology_gap": load_json(whole_tanakh_morphology_gap_path),
        "translation_claim_matrix": load_json(translation_claim_matrix_path),
        "canonical_context_network": load_json(canonical_context_network_path),
        "witness_readiness": load_json(witness_readiness_path),
        "reception_boundary": load_json(reception_boundary_path),
        "contextual_pressure_atlas": load_json(atlas_path),
        "contextual_benchmark_coverage": load_json(coverage_path),
        "expanded_suite": load_json(expanded_suite_path),
        "expanded_cross_exam": load_json(expanded_cross_exam_path),
        "expanded_review": load_json(expanded_review_path),
        "integrated_real_audit": load_json(integrated_real_audit_path),
        "model_evidence_gap": load_json(model_evidence_gap_path),
        "model_output_quality_triage": load_json(model_output_quality_triage_path),
        "layer_consistency": load_json(layer_consistency_path),
        "layer_remediation": load_json(layer_remediation_path),
        "layer_remediation_experiment": load_json(layer_remediation_experiment_path),
        "base_real_audit": load_json(base_real_audit_path),
        "runtime": load_json(runtime_path),
        "asset_inventory": load_json(asset_path),
        "dashboard": load_json(dashboard_path),
    }
    gates = build_gate_rows(data)
    risks = risk_rows(data)
    domains = projected_domain_rows(
        data["contextual_benchmark_coverage"],
        expanded_unit_ids(data["expanded_suite"]),
    )
    total_weight = sum(int(row["weight"]) for row in gates)
    weighted_score = round(
        sum(float(row["weighted_points"]) for row in gates) / total_weight * 100,
        2,
    )
    hard_blockers = [
        row
        for row in gates
        if row["gate"] in {"real_model_evidence", "human_signoff", "release_authority"}
        and float(row["score_pct"]) == 0
    ]
    summary = {
        "authority_readiness_score_pct": weighted_score,
        "gate_count": len(gates),
        "hard_blocker_count": len(hard_blockers),
        "hard_blockers": [row["gate"] for row in hard_blockers],
        "expanded_task_count": data["expanded_suite"]["summary"]["task_count"],
        "expanded_unit_count": data["expanded_suite"]["summary"]["unit_count"],
        "expanded_planned_model_runs": data["expanded_suite"]["summary"]["planned_model_runs"],
        "expanded_projected_atlas_coverage_pct": data["expanded_suite"]["summary"][
            "projected_atlas_coverage_after_pct"
        ],
        "real_submitted_integrated_rows": data["integrated_real_audit"]["summary"][
            "submitted_result_count"
        ],
        "real_expected_integrated_rows": data["integrated_real_audit"]["summary"][
            "expected_result_count"
        ],
        "real_integrated_source_anchor_issues": data["integrated_real_audit"]["summary"].get(
            "source_anchor_issue_count", 0
        ),
        "model_evidence_gap_schema_valid_expected_pct": data["model_evidence_gap"]["summary"][
            "schema_valid_expected_pct"
        ],
        "model_evidence_gap_units_without_valid": data["model_evidence_gap"]["summary"][
            "unit_without_schema_valid_count"
        ],
        "model_evidence_gap_high_risk_without_valid": data["model_evidence_gap"]["summary"][
            "high_risk_without_schema_valid_count"
        ],
        "model_evidence_gap_top_unit": data["model_evidence_gap"]["summary"]["top_gap_unit"],
        "model_evidence_gap_top_no_real_unit": data["model_evidence_gap"]["summary"][
            "top_no_real_model_evidence_unit"
        ],
        "quality_triage_candidate_rows": data["model_output_quality_triage"]["summary"][
            "candidate_row_count"
        ],
        "quality_triage_schema_valid_candidates": data["model_output_quality_triage"]["summary"][
            "schema_valid_candidate_count"
        ],
        "quality_triage_contextual_review_required": data["model_output_quality_triage"]["summary"][
            "contextual_review_required_count"
        ],
        "quality_triage_structure_failures": data["model_output_quality_triage"]["summary"][
            "structure_failure_count"
        ],
        "quality_triage_mean_review_priority_score": data["model_output_quality_triage"]["summary"][
            "mean_review_priority_score"
        ],
        "layer_consistency_paired_count": data["layer_consistency"]["summary"][
            "paired_unit_model_count"
        ],
        "layer_consistency_schema_valid_pairs": data["layer_consistency"]["summary"][
            "schema_valid_pair_count"
        ],
        "layer_consistency_exact_duplicates": data["layer_consistency"]["summary"][
            "exact_duplicate_pair_count"
        ],
        "layer_consistency_weak_differentiation_pairs": data["layer_consistency"]["summary"][
            "weak_layer_differentiation_pair_count"
        ],
        "layer_consistency_mean_word_jaccard_pct": data["layer_consistency"]["summary"][
            "mean_word_jaccard_pct"
        ],
        "layer_consistency_divine_name_inconsistent_pairs": data["layer_consistency"]["summary"][
            "divine_name_inconsistent_pair_count"
        ],
        "layer_remediation_action_count": data["layer_remediation"]["summary"]["action_count"],
        "layer_remediation_retry_task_count": data["layer_remediation"]["summary"][
            "retry_task_count"
        ],
        "layer_remediation_retry_pair_count": data["layer_remediation"]["summary"][
            "retry_pair_count"
        ],
        "layer_remediation_runner_contract_ready": data["layer_remediation"]["summary"][
            "runner_contract_ready"
        ],
        "layer_experiment_best_attempt": data["layer_remediation_experiment"]["summary"][
            "best_attempt_label"
        ],
        "layer_experiment_best_schema_valid_pct": data["layer_remediation_experiment"]["summary"][
            "best_attempt_schema_valid_pct"
        ],
        "layer_experiment_best_weak_diff": data["layer_remediation_experiment"]["summary"][
            "best_attempt_weak_layer_differentiation_pair_count"
        ],
        "layer_experiment_failed_gate_count": data["layer_remediation_experiment"]["summary"][
            "failed_gate_count"
        ],
        "layer_experiment_failed_gates": data["layer_remediation_experiment"]["summary"][
            "failed_gates"
        ],
        "projected_human_review_rows": data["expanded_review"]["summary"][
            "projected_human_review_rows"
        ],
        "witness_lxx_coverage_pct": data["witness_readiness"]["summary"]["lxx_coverage_pct"],
        "witness_english_coverage_pct": data["witness_readiness"]["summary"][
            "english_witness_coverage_pct"
        ],
        "reception_boundary_reception_units": data["reception_boundary"]["summary"][
            "reception_sensitive_unit_count"
        ],
        "reception_boundary_textual_units": data["reception_boundary"]["summary"][
            "textual_witness_pressure_unit_count"
        ],
        "reception_boundary_high_risk_units": data["reception_boundary"]["summary"][
            "high_boundary_risk_unit_count"
        ],
        "translation_claim_high_risk_units": data["translation_claim_matrix"]["summary"][
            "high_risk_unit_count"
        ],
        "translation_claim_jewish_christian_units": data["translation_claim_matrix"]["summary"][
            "jewish_christian_separation_unit_count"
        ],
        "translation_claim_outside_strong_supported_unit_pct": data["translation_claim_matrix"][
            "summary"
        ]["outside_strong_supported_unit_pct"],
        "reception_boundary_avg_risk_score": data["reception_boundary"]["summary"][
            "avg_boundary_risk_score"
        ],
        "lexeme_strong_coverage_pct": data["lexeme_readiness"]["summary"]["strong_coverage_pct"],
        "lexeme_lemma_coverage_pct": data["lexeme_readiness"]["summary"]["lemma_coverage_pct"],
        "whole_tanakh_non_psalm_morphology_book_count": data["whole_tanakh_morphology_gap"][
            "summary"
        ]["local_non_psalm_books_with_hebrew_morphology"],
        "whole_tanakh_outside_strong_context_token_pct": data["whole_tanakh_morphology_gap"][
            "summary"
        ]["outside_strong_context_token_pct"],
        "canonical_context_content_token_pct": data["canonical_context_network"]["summary"][
            "content_token_outside_context_pct"
        ],
        "canonical_context_three_division_unit_pct": data["canonical_context_network"]["summary"][
            "units_with_three_division_evidence_pct"
        ],
        "canonical_context_review_queue_units": data["canonical_context_network"]["summary"][
            "review_queue_unit_count"
        ],
        "whole_tanakh_lemma_index_available": data["lexeme_readiness"]["summary"][
            "whole_tanakh_lemma_index_available"
        ],
        "domain_count": len(domains),
        "lowest_projected_domain": domains[0]["domain"] if domains else "",
        "lowest_projected_domain_coverage_pct": domains[0]["expanded_coverage_pct"]
        if domains
        else 0.0,
    }
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated scholarly authority readiness audit",
        "source_paths": {
            "corpus_profile": str(corpus_profile_path.relative_to(ROOT)),
            "lexeme_readiness": str(lexeme_readiness_path.relative_to(ROOT)),
            "whole_tanakh_morphology_gap": str(whole_tanakh_morphology_gap_path.relative_to(ROOT)),
            "translation_claim_matrix": str(translation_claim_matrix_path.relative_to(ROOT)),
            "canonical_context_network": str(canonical_context_network_path.relative_to(ROOT)),
            "witness_readiness": str(witness_readiness_path.relative_to(ROOT)),
            "reception_boundary": str(reception_boundary_path.relative_to(ROOT)),
            "contextual_pressure_atlas": str(atlas_path.relative_to(ROOT)),
            "contextual_benchmark_coverage": str(coverage_path.relative_to(ROOT)),
            "expanded_suite": str(expanded_suite_path.relative_to(ROOT)),
            "expanded_cross_exam": str(expanded_cross_exam_path.relative_to(ROOT)),
            "expanded_review": str(expanded_review_path.relative_to(ROOT)),
            "integrated_real_audit": str(integrated_real_audit_path.relative_to(ROOT)),
            "model_evidence_gap": str(model_evidence_gap_path.relative_to(ROOT)),
            "model_output_quality_triage": str(model_output_quality_triage_path.relative_to(ROOT)),
            "layer_consistency": str(layer_consistency_path.relative_to(ROOT)),
            "layer_remediation": str(layer_remediation_path.relative_to(ROOT)),
            "layer_remediation_experiment": str(
                layer_remediation_experiment_path.relative_to(ROOT)
            ),
            "runtime": str(runtime_path.relative_to(ROOT)),
            "asset_inventory": str(asset_path.relative_to(ROOT)),
            "dashboard": str(dashboard_path.relative_to(ROOT)),
        },
        "summary": summary,
        "gate_rows": gates,
        "risk_register": risks,
        "domain_coverage_rows": domains,
    }


def rows_from_counter(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
    return [
        {label_key: key, "count": value}
        for key, value in sorted(counter.items(), key=lambda item: item[1], reverse=True)
    ]


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
    left = 310
    right = 70
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
    gate_rows = [
        [
            row["label"],
            row["weight"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["blocking_gap"],
        ]
        for row in report["gate_rows"]
    ]
    risk_rows_for_table = [
        [row["severity"], row["risk"], row["evidence"], row["mitigation"]]
        for row in report["risk_register"]
    ]
    domain_rows = [
        [
            row["domain"],
            row["unit_count"],
            f"{row['integrated_coverage_pct']:.2f}%",
            f"{row['expanded_coverage_pct']:.2f}%",
            row["expanded_uncovered_count"],
        ]
        for row in report["domain_coverage_rows"]
    ]
    severity_counts = Counter(row["severity"] for row in report["risk_register"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Scholarly Authority Readiness</title>
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
    <h1>AlephTav Scholarly Authority Readiness</h1>
    <p class="lede">
      Gate-level audit of whether the local Hebrew-to-English Psalms model
      program is ready to make authoritative claims. Scores are derived from
      generated corpus, lexeme, whole-Tanakh, witness, context-atlas, benchmark,
      runtime, model-result, and review-signoff artifacts.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Authority Gates</h2>
      {
        metric_cards(
            [
                (
                    "Readiness score",
                    f'''{summary["authority_readiness_score_pct"]:.2f}%''',
                    "Weighted across evidence gates; hard blockers still apply.",
                ),
                (
                    "Hard blockers",
                    fmt_int(summary["hard_blocker_count"]),
                    ", ".join(summary["hard_blockers"]),
                ),
                (
                    "Expanded suite",
                    fmt_int(summary["expanded_task_count"]),
                    f'''{fmt_int(summary["expanded_unit_count"])} units; '''
                    f'''{fmt_int(summary["expanded_planned_model_runs"])} planned runs.''',
                ),
                (
                    "Projected atlas coverage",
                    f'''{summary["expanded_projected_atlas_coverage_pct"]:.2f}%''',
                    "Coverage after integrated plus contextual gap supplement.",
                ),
                (
                    "Real model rows",
                    fmt_int(summary["real_submitted_integrated_rows"]),
                    (
                        f'''Expected integrated rows: '''
                        f'''{fmt_int(summary["real_expected_integrated_rows"])}.'''
                    ),
                ),
                (
                    "High-risk model gaps",
                    fmt_int(summary["model_evidence_gap_high_risk_without_valid"]),
                    f'''{fmt_int(summary["model_evidence_gap_units_without_valid"])} expanded '''
                    "units lack schema-valid rows.",
                ),
                (
                    "Quality triage",
                    fmt_int(summary["quality_triage_schema_valid_candidates"]),
                    f'''{fmt_int(summary["quality_triage_contextual_review_required"])} '''
                    "valid rows carry contextual review flags.",
                ),
                (
                    "Layer contract",
                    fmt_int(summary["layer_consistency_paired_count"]),
                    f'''{fmt_int(summary["layer_consistency_exact_duplicates"])} exact '''
                    "duplicates; "
                    f'''{fmt_int(summary["layer_consistency_weak_differentiation_pairs"])} '''
                    "weakly differentiated pairs.",
                ),
                (
                    "Layer remediation",
                    fmt_int(summary["layer_remediation_retry_task_count"]),
                    f'''{fmt_int(summary["layer_remediation_action_count"])} actions; '''
                    "runner contracts "
                    + (
                        "present"
                        if summary["layer_remediation_runner_contract_ready"]
                        else "missing"
                    )
                    + ".",
                ),
                (
                    "Layer experiment",
                    summary["layer_experiment_best_attempt"],
                    f'''{summary["layer_experiment_best_schema_valid_pct"]:.2f}% schema; '''
                    f'''{fmt_int(summary["layer_experiment_failed_gate_count"])} failed gate.''',
                ),
                (
                    "Human review rows",
                    fmt_int(summary["projected_human_review_rows"]),
                    "Projected expanded-suite workload; no completed signoffs yet.",
                ),
                (
                    "Witness coverage",
                    f'''{summary["witness_lxx_coverage_pct"]:.2f}%''',
                    f'''English witnesses {summary["witness_english_coverage_pct"]:.2f}%.''',
                ),
                (
                    "Reception boundary",
                    fmt_int(summary["reception_boundary_reception_units"]),
                    f'''{fmt_int(summary["reception_boundary_high_risk_units"])} '''
                    "high-risk boundary units.",
                ),
                (
                    "Claim matrix",
                    fmt_int(summary["translation_claim_high_risk_units"]),
                    f'''{fmt_int(summary["translation_claim_jewish_christian_units"])} '''
                    "units require Jewish/Christian separation.",
                ),
                (
                    "Cross-canon context",
                    f'''{summary["canonical_context_content_token_pct"]:.2f}%''',
                    f'''{summary["canonical_context_three_division_unit_pct"]:.2f}% '''
                    "of units hit three divisions.",
                ),
                (
                    "Weakest domain",
                    summary["lowest_projected_domain"],
                    (
                        f'''{summary["lowest_projected_domain_coverage_pct"]:.2f}% projected '''
                        "coverage."
                    ),
                ),
            ]
        )
    }
      <div class="warning">
        This report intentionally does not call any model authoritative while
        full real local benchmark coverage, completed human signoff, and
        canonical rendering promotion evidence are absent.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            report["gate_rows"],
            label_key="label",
            value_key="score_pct",
            aria_label="Scholarly authority gate readiness scores",
            color="#2f6f73",
        )
    }</div>
    </section>
    <section>
      <h2>Risk Register</h2>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(dict(severity_counts), "severity"),
            label_key="severity",
            value_key="count",
            aria_label="Authority risk counts by severity",
            color="#9b3d3d",
        )
    }</div>
      {table(["Severity", "Risk", "Evidence", "Mitigation"], risk_rows_for_table)}
    </section>
    <section>
      <h2>Domain Coverage</h2>
      <div class="chart">{
        svg_horizontal_bars(
            report["domain_coverage_rows"],
            label_key="domain",
            value_key="expanded_coverage_pct",
            aria_label="Projected expanded benchmark coverage by context domain",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Domain",
                "Atlas Units",
                "Integrated Coverage",
                "Expanded Coverage",
                "Still Uncovered",
            ],
            domain_rows,
        )
    }
    </section>
    <section>
      <h2>Gate Evidence</h2>
      {
        table(
            [
                "Gate",
                "Weight",
                "Score",
                "Status",
                "Evidence",
                "Blocking Gap",
            ],
            gate_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate scholarly authority readiness audit.")
    parser.add_argument("--corpus-profile", type=Path, default=CORPUS_PROFILE_PATH)
    parser.add_argument("--lexeme-readiness", type=Path, default=LEXEME_READINESS_PATH)
    parser.add_argument(
        "--whole-tanakh-morphology-gap",
        type=Path,
        default=WHOLE_TANAKH_MORPHOLOGY_GAP_PATH,
    )
    parser.add_argument(
        "--translation-claim-matrix",
        type=Path,
        default=TRANSLATION_CLAIM_MATRIX_PATH,
    )
    parser.add_argument(
        "--canonical-context-network",
        type=Path,
        default=CANONICAL_CONTEXT_NETWORK_PATH,
    )
    parser.add_argument(
        "--witness-readiness",
        type=Path,
        default=WITNESS_READINESS_PATH,
    )
    parser.add_argument(
        "--reception-boundary",
        type=Path,
        default=RECEPTION_BOUNDARY_PATH,
    )
    parser.add_argument("--atlas", type=Path, default=ATLAS_PATH)
    parser.add_argument("--coverage", type=Path, default=COVERAGE_PATH)
    parser.add_argument("--expanded-suite", type=Path, default=EXPANDED_SUITE_PATH)
    parser.add_argument(
        "--expanded-cross-exam",
        type=Path,
        default=EXPANDED_CROSS_EXAM_PATH,
    )
    parser.add_argument("--expanded-review", type=Path, default=EXPANDED_REVIEW_PATH)
    parser.add_argument(
        "--integrated-real-audit",
        type=Path,
        default=INTEGRATED_REAL_AUDIT_PATH,
    )
    parser.add_argument(
        "--model-evidence-gap",
        type=Path,
        default=MODEL_EVIDENCE_GAP_PATH,
    )
    parser.add_argument(
        "--model-output-quality-triage",
        type=Path,
        default=MODEL_OUTPUT_QUALITY_TRIAGE_PATH,
    )
    parser.add_argument(
        "--layer-consistency",
        type=Path,
        default=LAYER_CONSISTENCY_PATH,
    )
    parser.add_argument(
        "--layer-remediation",
        type=Path,
        default=LAYER_REMEDIATION_PATH,
    )
    parser.add_argument(
        "--layer-remediation-experiment",
        type=Path,
        default=LAYER_REMEDIATION_EXPERIMENT_PATH,
    )
    parser.add_argument("--base-real-audit", type=Path, default=BASE_REAL_AUDIT_PATH)
    parser.add_argument("--runtime", type=Path, default=RUNTIME_PATH)
    parser.add_argument("--asset-inventory", type=Path, default=ASSET_PATH)
    parser.add_argument("--dashboard", type=Path, default=DASHBOARD_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--risk-csv-output", type=Path, default=DEFAULT_RISK_CSV_OUTPUT)
    parser.add_argument(
        "--domain-csv-output",
        type=Path,
        default=DEFAULT_DOMAIN_CSV_OUTPUT,
    )
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        corpus_profile_path=args.corpus_profile,
        lexeme_readiness_path=args.lexeme_readiness,
        whole_tanakh_morphology_gap_path=args.whole_tanakh_morphology_gap,
        translation_claim_matrix_path=args.translation_claim_matrix,
        canonical_context_network_path=args.canonical_context_network,
        witness_readiness_path=args.witness_readiness,
        reception_boundary_path=args.reception_boundary,
        atlas_path=args.atlas,
        coverage_path=args.coverage,
        expanded_suite_path=args.expanded_suite,
        expanded_cross_exam_path=args.expanded_cross_exam,
        expanded_review_path=args.expanded_review,
        integrated_real_audit_path=args.integrated_real_audit,
        model_evidence_gap_path=args.model_evidence_gap,
        model_output_quality_triage_path=args.model_output_quality_triage,
        layer_consistency_path=args.layer_consistency,
        layer_remediation_path=args.layer_remediation,
        layer_remediation_experiment_path=args.layer_remediation_experiment,
        base_real_audit_path=args.base_real_audit,
        runtime_path=args.runtime,
        asset_path=args.asset_inventory,
        dashboard_path=args.dashboard,
    )
    write_json(args.json_output, report)
    write_csv(args.gate_csv_output, report["gate_rows"])
    write_csv(args.risk_csv_output, report["risk_register"])
    write_csv(args.domain_csv_output, report["domain_coverage_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.gate_csv_output}")
    print(f"Wrote {args.risk_csv_output}")
    print(f"Wrote {args.domain_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
