from __future__ import annotations

import argparse
import csv
import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw"
REPORT_ROOT = ROOT / "reports" / "research"
DOC_ROOT = ROOT / "docs" / "research"

WITNESS_PATH = REPORT_ROOT / "witness_reception_readiness.json"
MORPHOLOGY_GAP_PATH = REPORT_ROOT / "whole_tanakh_morphology_gap.json"
LEXEME_PATH = REPORT_ROOT / "lexeme_context_readiness.json"
CANONICAL_CONTEXT_PATH = REPORT_ROOT / "canonical_context_network.json"
CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
ADJUDICATION_PATH = REPORT_ROOT / "interpretive_adjudication_matrix.json"
CASEBOOK_PATH = REPORT_ROOT / "scholarly_casebook.json"
MODEL_GAP_PATH = REPORT_ROOT / "model_evidence_gap_report.json"
LAYER_CONSISTENCY_PATH = REPORT_ROOT / "layer_consistency_report.json"
LOCAL_SELECTION_PATH = REPORT_ROOT / "local_model_selection_roadmap.json"
AUTHORITY_PATH = REPORT_ROOT / "scholarly_authority_readiness.json"
MODEL_DATA_PATH = DOC_ROOT / "local_translation_model_data.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "scholarly_source_maturity_report.json"
DEFAULT_LANE_CSV_OUTPUT = REPORT_ROOT / "scholarly_source_maturity_lanes.csv"
DEFAULT_SOURCE_CSV_OUTPUT = REPORT_ROOT / "scholarly_source_maturity_sources.csv"
DEFAULT_GAP_CSV_OUTPUT = REPORT_ROOT / "scholarly_source_maturity_gaps.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "scholarly_source_maturity_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "scholarly_source_maturity_report.html"


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


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def score_band(score: float) -> str:
    if score >= 85.0:
        return "strong"
    if score >= 60.0:
        return "prototype"
    if score > 0.0:
        return "partial"
    return "blocked"


def gate_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("gate")): row for row in rows if row.get("gate")}


def source_manifest_rows() -> list[dict[str, Any]]:
    rows = []
    for path in sorted(RAW_ROOT.glob("*/manifest.json")):
        data = load_json(path)
        source_id = str(data.get("source_id") or path.parent.name)
        rows.append(
            {
                "source_id": source_id,
                "name": data.get("name", ""),
                "language": data.get("source_language") or "",
                "basis_role": data.get("basis_role") or "",
                "license": data.get("license") or "",
                "version": data.get("version") or "",
                "version_pinned": bool(data.get("version_pinned")),
                "allowed_for_display": bool(data.get("allowed_for_display")),
                "allowed_for_export": bool(data.get("allowed_for_export")),
                "allowed_for_generation": bool(data.get("allowed_for_generation")),
                "manifest_path": str(path.relative_to(ROOT)),
            }
        )
    return rows


def policy_by_source(witness: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("source_id")): row
        for row in witness.get("source_policy_rows", [])
        if row.get("source_id")
    }


def enrich_source_rows(
    manifest_rows: list[dict[str, Any]],
    witness: dict[str, Any],
    model_data: dict[str, Any],
) -> list[dict[str, Any]]:
    policy_rows = policy_by_source(witness)
    hierarchy = model_data.get("source_hierarchy", [])
    hierarchy_by_source: dict[str, list[str]] = {}
    for row in hierarchy:
        source_text = str(row.get("source") or "").lower()
        for source in manifest_rows:
            source_id = str(source["source_id"])
            name = str(source["name"]).lower()
            if source_id in source_text or source_text in name:
                hierarchy_by_source.setdefault(source_id, []).append(str(row.get("role") or ""))

    role_map = {
        "uxlc": ["hebrew_source_corpus", "whole_tanakh_surface_context"],
        "oshb": ["psalm_morphology_lexeme"],
        "macula": ["psalm_morphology_lexeme", "syntax_enrichment"],
        "lxx": ["textual_witnesses", "alternate_ideation_source"],
        "asv": ["english_witness"],
        "kjv": ["english_witness"],
        "web": ["english_witness"],
        "sefaria": ["english_witness", "restricted_witness"],
    }
    rows = []
    for source in manifest_rows:
        source_id = str(source["source_id"])
        policy = policy_rows.get(source_id, {})
        generation_allowed = bool(source["allowed_for_generation"])
        witness_records = int(policy.get("witness_records") or 0)
        if generation_allowed:
            generation_policy = "allowed_by_manifest"
        elif source_id in {"asv", "kjv", "web", "sefaria"}:
            generation_policy = "display_witness_not_generation_basis"
        else:
            generation_policy = "enrichment_or_source_not_generation_basis"
        rows.append(
            {
                **source,
                "witness_records": witness_records,
                "policy_generation": bool(policy.get("generation", generation_allowed)),
                "policy_display": bool(policy.get("display", source["allowed_for_display"])),
                "policy_export": bool(policy.get("export", source["allowed_for_export"])),
                "generation_policy": generation_policy,
                "used_in_lanes": role_map.get(source_id, []),
                "source_hierarchy_roles": hierarchy_by_source.get(source_id, []),
            }
        )
    return rows


def lane_row(
    *,
    lane: str,
    label: str,
    evidence_score_pct: float,
    authority_score_pct: float,
    evidence: str,
    blocking_gap: str,
    next_action: str,
    source_ids: list[str],
    status: str | None = None,
    generation_policy: str = "not_applicable",
    signed_source_synthesis: bool = False,
    reviewer_signoff_required: bool = True,
) -> dict[str, Any]:
    return {
        "lane": lane,
        "label": label,
        "evidence_score_pct": round(evidence_score_pct, 2),
        "authority_score_pct": round(authority_score_pct, 2),
        "evidence_status": score_band(evidence_score_pct),
        "authority_status": status or score_band(authority_score_pct),
        "evidence": evidence,
        "blocking_gap": blocking_gap,
        "next_action": next_action,
        "source_ids": source_ids,
        "generation_policy": generation_policy,
        "signed_source_synthesis": signed_source_synthesis,
        "reviewer_signoff_required": reviewer_signoff_required,
    }


def build_lane_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    witness = data["witness"]["summary"]
    morph = data["morphology_gap"]["summary"]
    lexeme = data["lexeme"]["summary"]
    canonical = data["canonical_context"]["summary"]
    claims = data["claim_matrix"]["summary"]
    adjudication = data["adjudication"]["summary"]
    casebook = data["casebook"]["summary"]
    model_gap = data["model_gap"]["summary"]
    layer = data["layer_consistency"]["summary"]
    local_selection = data["local_selection"]["summary"]
    authority_gates = gate_by_id(data["authority"]["gate_rows"])

    source_gate = authority_gates.get("source_corpus_governance", {})
    lex_gate = authority_gates.get("lexical_morphology_traceability", {})
    whole_gate = authority_gates.get("whole_tanakh_context", {})
    witness_gate = authority_gates.get("witness_reception_provenance", {})
    culture_gate = authority_gates.get("context_culture_atlas_coverage", {})

    return [
        lane_row(
            lane="hebrew_source_corpus",
            label="Hebrew Source Corpus",
            evidence_score_pct=float(source_gate.get("score_pct", 95.0)),
            authority_score_pct=float(source_gate.get("score_pct", 95.0)),
            evidence=(
                f"{morph['psalm_token_count']} Psalm token records; "
                f"{lexeme['unit_count']} Psalm units; source corpus governance gate "
                f"{float(source_gate.get('score_pct', 0.0)):.2f}%."
            ),
            blocking_gap=str(
                source_gate.get(
                    "blocking_gap",
                    "No canonical renderings or release approvals are implied by source control.",
                )
            ),
            next_action=str(
                source_gate.get(
                    "next_action",
                    "Keep source-token anchoring mandatory for every generated proposal.",
                )
            ),
            source_ids=["uxlc", "oshb", "macula"],
            generation_policy="hebrew_basis_only",
            signed_source_synthesis=True,
            reviewer_signoff_required=True,
        ),
        lane_row(
            lane="psalm_morphology_lexeme",
            label="Psalm Morphology and Lexeme Traceability",
            evidence_score_pct=float(lex_gate.get("score_pct", 0.0)),
            authority_score_pct=float(lex_gate.get("score_pct", 0.0)),
            evidence=(
                f"Psalm Strong coverage {lexeme['strong_coverage_pct']:.2f}%; "
                f"lemma coverage {lexeme['lemma_coverage_pct']:.2f}%; "
                f"semantic_role {lexeme['semantic_role_coverage_pct']:.2f}%; "
                f"referent {lexeme['referent_coverage_pct']:.2f}%."
            ),
            blocking_gap=str(
                lex_gate.get(
                    "blocking_gap",
                    "Semantic-role and referent coverage remain absent.",
                )
            ),
            next_action=str(
                lex_gate.get(
                    "next_action",
                    "Add semantic-role and referent evidence before high-trust claims.",
                )
            ),
            source_ids=["oshb", "macula"],
            generation_policy="enrichment_not_generation_basis",
            signed_source_synthesis=False,
            reviewer_signoff_required=True,
        ),
        lane_row(
            lane="whole_tanakh_context",
            label="Whole-Tanakh Lexical Context",
            evidence_score_pct=float(whole_gate.get("score_pct", 0.0)),
            authority_score_pct=0.0,
            evidence=(
                f"{morph['uxlc_book_count']} UXLC books; "
                f"{morph['local_non_psalm_books_with_hebrew_morphology']} non-Psalm "
                "books with local Hebrew morphology; "
                f"{canonical['content_token_outside_context_pct']:.2f}% expanded "
                "content-token outside-Psalms surface evidence."
            ),
            blocking_gap=(
                "Whole-Tanakh context is surface-form evidence, not a lemma, Strong, "
                "syntax, or sense index outside Psalms."
            ),
            next_action=(
                "Build or license a whole-Tanakh morphology and lemma index before "
                "treating canonical parallels as lexical proof."
            ),
            source_ids=["uxlc"],
            generation_policy="surface_context_only",
            signed_source_synthesis=False,
            reviewer_signoff_required=True,
        ),
        lane_row(
            lane="textual_witnesses",
            label="Textual Witnesses",
            evidence_score_pct=float(witness["complete_expected_witness_set_pct"]),
            authority_score_pct=float(witness_gate.get("score_pct", 0.0)),
            evidence=(
                f"{witness['witness_record_count']} witness rows; "
                f"LXX coverage {witness['lxx_coverage_pct']:.2f}%; "
                f"English coverage {witness['english_witness_coverage_pct']:.2f}%; "
                f"{witness['witness_source_generation_block_count']} witness sources "
                "blocked from generation."
            ),
            blocking_gap=str(
                witness_gate.get(
                    "blocking_gap",
                    "English witnesses are display/comparison evidence, not generation basis.",
                )
            ),
            next_action=str(
                witness_gate.get(
                    "next_action",
                    "Use witnesses only as labeled evidence and audit leakage into outputs.",
                )
            ),
            source_ids=["lxx", "asv", "kjv", "web", "sefaria"],
            generation_policy="lxx_allowed_english_witnesses_blocked",
            signed_source_synthesis=False,
            reviewer_signoff_required=True,
        ),
        lane_row(
            lane="ancient_cultural_context",
            label="Ancient Cultural Context",
            evidence_score_pct=float(culture_gate.get("score_pct", 0.0)),
            authority_score_pct=0.0,
            evidence=(
                f"{claims['ancient_culture_pressure_unit_count']} expanded units carry "
                "ancient-culture pressure; casebook covers "
                f"{casebook['case_count']} high-risk cases."
            ),
            blocking_gap=(
                "The repository has routing tags and reviewer questions, not signed "
                "substantive cultural-source synthesis."
            ),
            next_action=(
                "Attach dated source notes and reviewer decisions for ancient Near "
                "Eastern, cultic, royal, wisdom, and genre claims."
            ),
            source_ids=[],
            generation_policy="routing_only",
            signed_source_synthesis=False,
            reviewer_signoff_required=True,
        ),
        lane_row(
            lane="jewish_reception",
            label="Jewish Reception",
            evidence_score_pct=0.0,
            authority_score_pct=0.0,
            evidence=(
                f"{adjudication['jewish_christian_separation_unit_count']} expanded "
                "units require Jewish/Christian separation; "
                f"{casebook['reception_case_count']} casebook cases are "
                "reception-sensitive."
            ),
            blocking_gap=(
                "Jewish reception is routed separately, but no signed Jewish-source "
                "synthesis or rabbinic/medieval/modern viewpoint decision is present."
            ),
            next_action=(
                "Create Jewish reception packets with source citations, viewpoint "
                "boundaries, and reviewer signoff."
            ),
            source_ids=[],
            generation_policy="unsigned_reception_not_translation_basis",
            signed_source_synthesis=False,
            reviewer_signoff_required=True,
        ),
        lane_row(
            lane="christian_reception",
            label="Christian Reception",
            evidence_score_pct=0.0,
            authority_score_pct=0.0,
            evidence=(
                f"{adjudication['jewish_christian_separation_unit_count']} expanded "
                "units require Christian/Jewish separation; "
                f"{claims['theology_pressure_unit_count']} expanded units carry "
                "theology pressure."
            ),
            blocking_gap=(
                "Christian reception is routed separately, but no signed patristic, "
                "confessional, academic, or modern viewpoint decision is present."
            ),
            next_action=(
                "Create Christian reception packets with source citations, viewpoint "
                "boundaries, and reviewer signoff."
            ),
            source_ids=[],
            generation_policy="unsigned_reception_not_translation_basis",
            signed_source_synthesis=False,
            reviewer_signoff_required=True,
        ),
        lane_row(
            lane="academic_comparison",
            label="Academic Comparative Controls",
            evidence_score_pct=0.0,
            authority_score_pct=0.0,
            evidence=(
                f"{adjudication['highest_priority_unit_count']} highest-priority units; "
                f"{adjudication['textual_witness_pressure_unit_count']} textual-witness "
                "pressure units."
            ),
            blocking_gap=(
                "The current reports identify academic-comparison need, but do not "
                "contain a signed scholarly literature synthesis."
            ),
            next_action=(
                "Add scoped critical-commentary comparison notes as evidence packets, "
                "not as automatic wording authority."
            ),
            source_ids=[],
            generation_policy="comparison_only_after_review",
            signed_source_synthesis=False,
            reviewer_signoff_required=True,
        ),
        lane_row(
            lane="local_model_output",
            label="Local Model Output",
            evidence_score_pct=float(model_gap["schema_valid_expected_pct"]),
            authority_score_pct=0.0,
            evidence=(
                f"{model_gap['schema_valid_result_count']} schema-valid rows out of "
                f"{model_gap['expected_result_count']} expected expanded runs; "
                f"{model_gap['high_risk_without_schema_valid_count']} high-risk units "
                "lack schema-valid local output. Best runnable candidate: "
                f"{local_selection['best_runnable_candidate']}."
            ),
            blocking_gap=(
                "Local model output is proposal evidence only; source-anchor, layer, "
                "coverage, and human review gates are not certified."
            ),
            next_action=(
                "Finish the model bakeoff only after schema, source-anchor, and layer "
                "gates are stable across candidates."
            ),
            source_ids=[],
            generation_policy="proposal_only",
            signed_source_synthesis=False,
            reviewer_signoff_required=True,
        ),
        lane_row(
            lane="layer_contracts",
            label="Layer Contract Evidence",
            evidence_score_pct=pct(
                int(layer["schema_valid_pair_count"])
                - int(layer["weak_layer_differentiation_pair_count"]),
                int(layer["schema_valid_pair_count"]),
            ),
            authority_score_pct=0.0,
            evidence=(
                f"{layer['schema_valid_pair_count']} schema-valid paired rows; "
                f"{layer['exact_duplicate_pair_count']} exact duplicates; "
                f"{layer['weak_layer_differentiation_pair_count']} weak "
                "differentiation pairs; mean overlap "
                f"{layer['mean_word_jaccard_pct']:.2f}%."
            ),
            blocking_gap=(
                "Gloss and literal outputs are not separated well enough for "
                "authority-level evaluation."
            ),
            next_action=(
                "Keep layer remediation in the prompt/runtime test loop until paired "
                "output gates pass."
            ),
            source_ids=[],
            generation_policy="model_contract_gate",
            signed_source_synthesis=False,
            reviewer_signoff_required=True,
        ),
        lane_row(
            lane="human_review_signoff",
            label="Human Review Signoff",
            evidence_score_pct=0.0,
            authority_score_pct=0.0,
            evidence=(
                "Projected review rows exist, but completed role-specific reviewer "
                "scores and release decisions are absent."
            ),
            blocking_gap="No human signoff data exists for authority certification.",
            next_action=(
                "Collect Hebrew, lexical, alignment, theology/reception, and release "
                "review decisions with audit records."
            ),
            source_ids=[],
            generation_policy="review_required",
            signed_source_synthesis=False,
            reviewer_signoff_required=True,
        ),
        lane_row(
            lane="release_authority",
            label="Release Authority",
            evidence_score_pct=0.0,
            authority_score_pct=0.0,
            evidence=(
                "Generated reports are review packets; they do not approve canonical "
                "renderings or release text."
            ),
            blocking_gap=(
                "Release authority requires completed reviews, audit records, license "
                "checks, and canonical-content governance."
            ),
            next_action="Do not represent generated model output as authoritative translation.",
            source_ids=[],
            generation_policy="blocked_until_release_signoff",
            signed_source_synthesis=False,
            reviewer_signoff_required=True,
        ),
    ]


def build_gap_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    witness = data["witness"]["summary"]
    morph = data["morphology_gap"]["summary"]
    lexeme = data["lexeme"]["summary"]
    claims = data["claim_matrix"]["summary"]
    adjudication = data["adjudication"]["summary"]
    model_gap = data["model_gap"]["summary"]
    layer = data["layer_consistency"]["summary"]
    authority = data["authority"]["summary"]

    return [
        {
            "gap": "whole_tanakh_morphology",
            "severity": "hard_blocker",
            "evidence": (
                f"{morph['local_non_psalm_books_with_hebrew_morphology']} non-Psalm "
                "books have local Hebrew morphology; outside Strong-context coverage "
                f"{morph['outside_strong_context_token_pct']:.2f}%."
            ),
            "required_before_authority": (
                "Whole-Tanakh lemma/Strong/morphology index or explicit downgrade of "
                "all canonical parallels to surface-form evidence."
            ),
        },
        {
            "gap": "semantic_role_referent",
            "severity": "high",
            "evidence": (
                f"semantic_role coverage {lexeme['semantic_role_coverage_pct']:.2f}%; "
                f"referent coverage {lexeme['referent_coverage_pct']:.2f}%."
            ),
            "required_before_authority": (
                "Semantic role and referent enrichment, or reviewer-signed decisions "
                "that isolate every claim depending on those fields."
            ),
        },
        {
            "gap": "reception_source_synthesis",
            "severity": "hard_blocker",
            "evidence": (
                f"{claims['jewish_christian_separation_unit_count']} units require "
                "Jewish/Christian separation; no signed source synthesis exists."
            ),
            "required_before_authority": (
                "Separate Jewish, Christian, and academic source packets with review "
                "decisions and boundaries."
            ),
        },
        {
            "gap": "english_witness_generation_policy",
            "severity": "policy_control",
            "evidence": (
                f"{witness['witness_source_generation_block_count']} witness sources "
                "are not allowed for generation: "
                + ", ".join(witness["witness_sources_not_allowed_for_generation"])
                + "."
            ),
            "required_before_authority": (
                "Keep English witnesses out of generation basis; use them only as "
                "labeled comparison evidence."
            ),
        },
        {
            "gap": "local_model_evidence_coverage",
            "severity": "hard_blocker",
            "evidence": (
                f"{model_gap['schema_valid_result_count']} schema-valid rows out of "
                f"{model_gap['expected_result_count']} expected expanded runs; "
                f"{model_gap['unit_without_schema_valid_count']} units lack any "
                "schema-valid local output."
            ),
            "required_before_authority": (
                "Complete candidate bakeoff, cross-examination, and model-output "
                "triage before relying on model proposals."
            ),
        },
        {
            "gap": "layer_contract_reliability",
            "severity": "high",
            "evidence": (
                f"{layer['exact_duplicate_pair_count']} exact duplicate pairs and "
                f"{layer['weak_layer_differentiation_pair_count']} weak pairs across "
                f"{layer['paired_unit_model_count']} paired rows."
            ),
            "required_before_authority": (
                "Passing paired-layer audit across selected local candidates."
            ),
        },
        {
            "gap": "human_review_signoff",
            "severity": "hard_blocker",
            "evidence": (
                f"Adjudication failed gates: {', '.join(adjudication['failed_gates'])}. "
                f"Authority hard blockers: {', '.join(authority['hard_blockers'])}."
            ),
            "required_before_authority": (
                "Completed reviewer records by role, plus release signoff and audit trail."
            ),
        },
    ]


def build_gate_rows(
    source_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    data: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    source_count = len(source_rows)
    pinned_count = sum(1 for row in source_rows if row["version_pinned"])
    generation_allowed_count = sum(1 for row in source_rows if row["allowed_for_generation"])
    evidence_strong_count = sum(1 for row in lane_rows if row["evidence_score_pct"] >= 85.0)
    authority_ready_count = sum(1 for row in lane_rows if row["authority_score_pct"] >= 85.0)
    model_gap = data["model_gap"]["summary"]
    return [
        {
            "gate": "source_inventory_policy",
            "score_pct": pct(pinned_count, source_count),
            "status": "partial" if pinned_count < source_count else "pass",
            "evidence": (
                f"{source_count} source manifests; {pinned_count} version-pinned; "
                f"{generation_allowed_count} allowed for generation by manifest."
            ),
            "next_action": "Pin every source version field and keep data/raw read-only.",
        },
        {
            "gate": "evidence_lane_maturity",
            "score_pct": pct(evidence_strong_count, len(lane_rows)),
            "status": "partial",
            "evidence": f"{evidence_strong_count} of {len(lane_rows)} lanes have strong evidence.",
            "next_action": "Raise prototype and blocked lanes with source-backed packets.",
        },
        {
            "gate": "authority_lane_maturity",
            "score_pct": pct(authority_ready_count, len(lane_rows)),
            "status": "blocked",
            "evidence": (
                f"{authority_ready_count} of {len(lane_rows)} lanes are authority-ready "
                "under current rules."
            ),
            "next_action": "Do not sign off authority claims until blocked lanes pass.",
        },
        {
            "gate": "reception_source_signoff",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": (
                "Jewish, Christian, and academic comparison lanes have no signed synthesis."
            ),
            "next_action": "Create and review separate reception source packets.",
        },
        {
            "gate": "model_certification",
            "score_pct": float(model_gap["schema_valid_expected_pct"]),
            "status": "blocked",
            "evidence": (
                f"{model_gap['schema_valid_result_count']} of "
                f"{model_gap['expected_result_count']} planned expanded rows are "
                "schema-valid."
            ),
            "next_action": "Complete bakeoff and cross-examination before certification.",
        },
        {
            "gate": "human_release_signoff",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": "No completed human release signoff rows are present.",
            "next_action": "Collect role-based reviewer and release approvals.",
        },
    ]


def summarize(
    source_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    data: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    witness = data["witness"]["summary"]
    morph = data["morphology_gap"]["summary"]
    lexeme = data["lexeme"]["summary"]
    model_gap = data["model_gap"]["summary"]

    hard_gap_count = sum(1 for row in gap_rows if row["severity"] == "hard_blocker")
    blocked_gate_count = sum(1 for row in gate_rows if row["status"] == "blocked")
    return {
        "source_count": len(source_rows),
        "version_pinned_source_count": sum(1 for row in source_rows if row["version_pinned"]),
        "generation_allowed_source_count": sum(
            1 for row in source_rows if row["allowed_for_generation"]
        ),
        "display_allowed_source_count": sum(1 for row in source_rows if row["allowed_for_display"]),
        "export_allowed_source_count": sum(1 for row in source_rows if row["allowed_for_export"]),
        "witness_source_generation_block_count": witness["witness_source_generation_block_count"],
        "lane_count": len(lane_rows),
        "strong_evidence_lane_count": sum(
            1 for row in lane_rows if row["evidence_score_pct"] >= 85.0
        ),
        "blocked_authority_lane_count": sum(
            1 for row in lane_rows if row["authority_score_pct"] < 40.0
        ),
        "mean_evidence_score_pct": mean([float(row["evidence_score_pct"]) for row in lane_rows]),
        "mean_authority_score_pct": mean([float(row["authority_score_pct"]) for row in lane_rows]),
        "gate_count": len(gate_rows),
        "blocked_gate_count": blocked_gate_count,
        "hard_gap_count": hard_gap_count,
        "lxx_coverage_pct": witness["lxx_coverage_pct"],
        "english_witness_coverage_pct": witness["english_witness_coverage_pct"],
        "psalm_strong_coverage_pct": lexeme["strong_coverage_pct"],
        "psalm_lemma_coverage_pct": lexeme["lemma_coverage_pct"],
        "semantic_role_coverage_pct": lexeme["semantic_role_coverage_pct"],
        "referent_coverage_pct": lexeme["referent_coverage_pct"],
        "whole_tanakh_non_psalm_morphology_book_count": morph[
            "local_non_psalm_books_with_hebrew_morphology"
        ],
        "whole_tanakh_outside_strong_context_pct": morph["outside_strong_context_token_pct"],
        "model_schema_valid_expected_pct": model_gap["schema_valid_expected_pct"],
        "model_units_without_schema_valid": model_gap["unit_without_schema_valid_count"],
        "status": "source_maturity_generated_not_reviewer_signoff",
    }


def build_report() -> dict[str, Any]:
    data = {
        "witness": load_json(WITNESS_PATH),
        "morphology_gap": load_json(MORPHOLOGY_GAP_PATH),
        "lexeme": load_json(LEXEME_PATH),
        "canonical_context": load_json(CANONICAL_CONTEXT_PATH),
        "claim_matrix": load_json(CLAIM_MATRIX_PATH),
        "adjudication": load_json(ADJUDICATION_PATH),
        "casebook": load_json(CASEBOOK_PATH),
        "model_gap": load_json(MODEL_GAP_PATH),
        "layer_consistency": load_json(LAYER_CONSISTENCY_PATH),
        "local_selection": load_json(LOCAL_SELECTION_PATH),
        "authority": load_json(AUTHORITY_PATH),
        "model_data": load_json(MODEL_DATA_PATH),
    }
    source_rows = enrich_source_rows(
        source_manifest_rows(),
        data["witness"],
        data["model_data"],
    )
    lane_rows = build_lane_rows(data)
    gap_rows = build_gap_rows(data)
    gate_rows = build_gate_rows(source_rows, lane_rows, data)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "scholarly source maturity generated; not reviewer signoff",
        "source_paths": {
            "raw_root": str(RAW_ROOT.relative_to(ROOT)),
            "witness": str(WITNESS_PATH.relative_to(ROOT)),
            "morphology_gap": str(MORPHOLOGY_GAP_PATH.relative_to(ROOT)),
            "lexeme": str(LEXEME_PATH.relative_to(ROOT)),
            "canonical_context": str(CANONICAL_CONTEXT_PATH.relative_to(ROOT)),
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
            "adjudication": str(ADJUDICATION_PATH.relative_to(ROOT)),
            "casebook": str(CASEBOOK_PATH.relative_to(ROOT)),
            "model_gap": str(MODEL_GAP_PATH.relative_to(ROOT)),
            "layer_consistency": str(LAYER_CONSISTENCY_PATH.relative_to(ROOT)),
            "local_selection": str(LOCAL_SELECTION_PATH.relative_to(ROOT)),
            "authority": str(AUTHORITY_PATH.relative_to(ROOT)),
            "model_data": str(MODEL_DATA_PATH.relative_to(ROOT)),
        },
        "policy": {
            "primary_basis": "Hebrew source tokens and alignment govern translation proposals.",
            "witness_boundary": (
                "English witnesses are comparison evidence and are not generation basis."
            ),
            "reception_boundary": (
                "Jewish, Christian, and academic reception lanes require separate signed "
                "source synthesis before affecting wording claims."
            ),
            "model_boundary": "Local model outputs are proposal evidence, never authority.",
        },
        "summary": summarize(source_rows, lane_rows, gap_rows, gate_rows, data),
        "source_rows": source_rows,
        "lane_rows": lane_rows,
        "gap_rows": gap_rows,
        "gate_rows": gate_rows,
    }


def svg_bar_chart(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    width: int = 1100,
    limit: int = 18,
) -> str:
    rows = rows[:limit]
    row_h = 30
    left = 285
    right = 70
    top = 24
    height = top * 2 + row_h * max(1, len(rows))
    max_value = max((float(row[value_key]) for row in rows), default=100.0)
    max_value = max(max_value, 100.0)
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
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="18" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 19}" font-size="12" '
            f'font-weight="700" fill="#24313a">{value:.2f}%</text>'
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


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lane_rows = report["lane_rows"]
    source_rows = report["source_rows"]
    gate_rows = report["gate_rows"]
    gap_rows = report["gap_rows"]
    lane_table_rows = [
        [
            row["label"],
            f"{row['evidence_score_pct']:.2f}%",
            f"{row['authority_score_pct']:.2f}%",
            row["authority_status"],
            row["evidence"],
            row["blocking_gap"],
        ]
        for row in lane_rows
    ]
    source_table_rows = [
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
            "; ".join(row["used_in_lanes"]),
        ]
        for row in source_rows
    ]
    gate_table_rows = [
        [
            row["gate"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in gate_rows
    ]
    gap_table_rows = [
        [
            row["gap"],
            row["severity"],
            row["evidence"],
            row["required_before_authority"],
        ]
        for row in gap_rows
    ]
    # Ruff's formatter rewrites nested dict-access f-strings here into Python
    # 3.12-only quote syntax. The project currently compiles under Python 3.11.
    # fmt: off
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Scholarly Source Maturity</title>
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
    main {{ max-width: 1220px; margin: 0 auto; padding: 30px 34px 54px; }}
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
    <h1>AlephTav Scholarly Source Maturity</h1>
    <p class="lede">
      Provenance and authority audit for the Hebrew-to-English translation
      research stack. Evidence maturity tracks what the repository can show;
      authority maturity tracks what is signed off enough to support
      translation claims.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}. Not reviewer signoff.</p>
  </header>
  <main>
    <section>
      <h2>Maturity Summary</h2>
      {
        metric_cards(
            [
                (
                    "Sources",
                    fmt_int(summary["source_count"]),
                    (
                        f'{fmt_int(summary["version_pinned_source_count"])} '
                        "version-pinned source manifests."
                    ),
                ),
                (
                    "Evidence score",
                    f'{summary["mean_evidence_score_pct"]:.2f}%',
                    (
                        f'{fmt_int(summary["strong_evidence_lane_count"])} '
                        "strong evidence lanes."
                    ),
                ),
                (
                    "Authority score",
                    f'{summary["mean_authority_score_pct"]:.2f}%',
                    (
                        f'{fmt_int(summary["blocked_authority_lane_count"])} lanes '
                        "remain authority-blocked."
                    ),
                ),
                (
                    "Blocked gates",
                    fmt_int(summary["blocked_gate_count"]),
                    f'{fmt_int(summary["hard_gap_count"])} hard gaps remain.',
                ),
                (
                    "Psalm lexemes",
                    f'{summary["psalm_strong_coverage_pct"]:.2f}%',
                    (
                        f'Lemma {summary["psalm_lemma_coverage_pct"]:.2f}%; '
                        f'referent {summary["referent_coverage_pct"]:.2f}%.'
                    ),
                ),
                (
                    "Tanakh morph",
                    fmt_int(summary["whole_tanakh_non_psalm_morphology_book_count"]),
                    (
                        "non-Psalm morph books; outside Strong context "
                        f'{summary["whole_tanakh_outside_strong_context_pct"]:.2f}%.'
                    ),
                ),
                (
                    "Witnesses",
                    f'{summary["english_witness_coverage_pct"]:.2f}%',
                    (
                        f'LXX {summary["lxx_coverage_pct"]:.2f}%; '
                        f'{fmt_int(summary["witness_source_generation_block_count"])} '
                        "generation-blocked witness sources."
                    ),
                ),
                (
                    "Model evidence",
                    f'{summary["model_schema_valid_expected_pct"]:.2f}%',
                    (
                        f'{fmt_int(summary["model_units_without_schema_valid"])} units '
                        "lack schema-valid local output."
                    ),
                ),
            ]
        )
    }
      <div class="warning">
        Evidence is not the same as authority. The source corpus and witness
        inventory are useful, but whole-Tanakh lemma evidence, reception-source
        synthesis, model certification, and human signoff still block any claim
        that a local model is authoritative.
      </div>
    </section>

    <section>
      <h2>Lane Scores</h2>
      <div class="chart">{
        svg_bar_chart(
            lane_rows,
            label_key="label",
            value_key="evidence_score_pct",
            aria_label="Evidence maturity score by lane",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_bar_chart(
            lane_rows,
            label_key="label",
            value_key="authority_score_pct",
            aria_label="Authority maturity score by lane",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            [
                "Lane",
                "Evidence",
                "Authority",
                "Status",
                "Evidence",
                "Blocking Gap",
            ],
            lane_table_rows,
        )
    }
    </section>

    <section>
      <h2>Source Inventory</h2>
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
                "Lanes",
            ],
            source_table_rows,
        )
    }
    </section>

    <section>
      <h2>Certification Gates</h2>
      <div class="chart">{
        svg_bar_chart(
            gate_rows,
            label_key="gate",
            value_key="score_pct",
            aria_label="Source maturity certification gates",
            color="#7c5b2f",
        )
    }</div>
      {table(["Gate", "Score", "Status", "Evidence", "Next Action"], gate_table_rows)}
    </section>

    <section>
      <h2>Hard Gaps</h2>
      {table(["Gap", "Severity", "Evidence", "Required Before Authority"], gap_table_rows)}
    </section>
  </main>
</body>
</html>
"""
    # fmt: on


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate scholarly source maturity report.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--lane-csv-output", type=Path, default=DEFAULT_LANE_CSV_OUTPUT)
    parser.add_argument("--source-csv-output", type=Path, default=DEFAULT_SOURCE_CSV_OUTPUT)
    parser.add_argument("--gap-csv-output", type=Path, default=DEFAULT_GAP_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    args = parse_args()
    report = build_report()
    json_output = resolve(args.json_output)
    lane_csv_output = resolve(args.lane_csv_output)
    source_csv_output = resolve(args.source_csv_output)
    gap_csv_output = resolve(args.gap_csv_output)
    gate_csv_output = resolve(args.gate_csv_output)
    html_output = resolve(args.html_output)
    write_json(json_output, report)
    write_csv(lane_csv_output, report["lane_rows"])
    write_csv(source_csv_output, report["source_rows"])
    write_csv(gap_csv_output, report["gap_rows"])
    write_csv(gate_csv_output, report["gate_rows"])
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(render_html(report), encoding="utf-8")
    print(json_output)
    print(lane_csv_output)
    print(source_csv_output)
    print(gap_csv_output)
    print(gate_csv_output)
    print(html_output)


if __name__ == "__main__":
    main()
