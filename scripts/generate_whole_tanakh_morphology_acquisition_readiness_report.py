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

MORPHOLOGY_GAP_PATH = REPORT_ROOT / "whole_tanakh_morphology_gap.json"
SOURCE_ACQUISITION_PATH = REPORT_ROOT / "contextual_source_acquisition_plan.json"
BIBLIOGRAPHY_PATH = REPORT_ROOT / "doctoral_bibliography_provenance.json"
SOURCE_MATURITY_PATH = REPORT_ROOT / "scholarly_source_maturity_report.json"
SOURCE_VERIFICATION_PATH = REPORT_ROOT / "doctoral_source_verification.json"
LEXEME_READINESS_PATH = REPORT_ROOT / "lexeme_context_readiness.json"
OSHB_ALIGNMENT_PILOT_PATH = REPORT_ROOT / "oshb_whole_tanakh_alignment_pilot.json"
OSHB_EXCEPTION_REVIEW_PATH = REPORT_ROOT / "oshb_alignment_exception_review.json"
OSHB_EXCEPTION_TAXONOMY_PATH = REPORT_ROOT / "oshb_exception_taxonomy.json"
OSHB_MAPPING_RULE_SIMULATION_PATH = REPORT_ROOT / "oshb_mapping_rule_simulation.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "whole_tanakh_morphology_acquisition_readiness.json"
DEFAULT_CANDIDATE_CSV_OUTPUT = (
    REPORT_ROOT / "whole_tanakh_morphology_acquisition_readiness_candidates.csv"
)
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "whole_tanakh_morphology_acquisition_readiness_gates.csv"
DEFAULT_LOCAL_INVENTORY_CSV_OUTPUT = (
    REPORT_ROOT / "whole_tanakh_morphology_acquisition_readiness_local_inventory.csv"
)
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "whole_tanakh_morphology_acquisition_readiness.html"

MORPHOLOGY_CANDIDATE_IDS = {
    "oshb_morphhb_whole_tanakh",
    "stepbible_data_tahot_lexicons",
    "macula_hebrew_full_semantics",
    "etcbc_bhsa_text_fabric",
}

RECOMMENDED_SEQUENCE = {
    "oshb_morphhb_whole_tanakh": {
        "rank": 1,
        "phase": "phase_1_primary_morphology",
        "recommendation": "first_import",
        "why": (
            "Directly extends the existing Psalms OSHB enrichment path into a "
            "whole-Tanakh morphology/lemma index."
        ),
    },
    "stepbible_data_tahot_lexicons": {
        "rank": 2,
        "phase": "phase_1b_parallel_lexical_semantic_enrichment",
        "recommendation": "parallel_enrichment_after_license_manifest",
        "why": (
            "Highest broad acquisition priority and useful for tagged lexical, "
            "semantic, and variant-aware controls."
        ),
    },
    "macula_hebrew_full_semantics": {
        "rank": 3,
        "phase": "phase_2_semantic_role_referent_enrichment",
        "recommendation": "semantic_role_and_referent_import",
        "why": (
            "Targets the current zero-coverage semantic-role and participant-referent "
            "gap after core morphology alignment is stable."
        ),
    },
    "etcbc_bhsa_text_fabric": {
        "rank": 4,
        "phase": "phase_3_research_only_comparator",
        "recommendation": "research_only_until_license_decision",
        "why": (
            "Strong scholarly comparator, but CC BY-NC posture blocks release-path "
            "authority unless legal/release policy changes."
        ),
    },
}

OFFICIAL_SOURCE_FACTS = {
    "oshb_morphhb_whole_tanakh": {
        "official_url": "https://github.com/openscriptures/morphhb",
        "license_url": "https://github.com/openscriptures/morphhb/blob/master/LICENSE.md",
        "observed_scope": (
            "Open Scriptures describes morphhb as Hebrew Bible lemma and morphology "
            "data, with files under wlc."
        ),
        "license_posture": (
            "WLC text is presented as public domain; OSHB morphology is presented "
            "under CC BY 4.0 attribution terms."
        ),
        "verification_basis": "official GitHub README and license file checked 2026-06-16",
    },
    "stepbible_data_tahot_lexicons": {
        "official_url": "https://github.com/STEPBible/STEPBible-Data",
        "license_url": "https://github.com/STEPBible/STEPBible-Data",
        "observed_scope": (
            "Repository describes downloadable tab-separated Bible-study datasets, "
            "including tagged Hebrew/Greek resources and lexicons."
        ),
        "license_posture": (
            "Repository README presents STEPBible Data under CC BY 4.0 terms with "
            "project attribution requirements."
        ),
        "verification_basis": "official GitHub README checked 2026-06-16",
    },
    "macula_hebrew_full_semantics": {
        "official_url": "https://github.com/Clear-Bible/macula-hebrew",
        "license_url": "https://github.com/Clear-Bible/macula-hebrew",
        "observed_scope": (
            "MACULA Hebrew describes morphology, syntax trees, word sense, semantic "
            "roles, participant referents, glosses, and multiple export variants."
        ),
        "license_posture": (
            "Composite open data with component licenses; component review is required "
            "before release-path import or display."
        ),
        "verification_basis": "official GitHub README and Tools.Bible overview checked 2026-06-16",
    },
    "etcbc_bhsa_text_fabric": {
        "official_url": "https://github.com/ETCBC/bhsa",
        "license_url": "https://github.com/ETCBC/bhsa",
        "observed_scope": (
            "BHSA describes a Text-Fabric representation of the Hebrew Bible with "
            "linguistic annotations and reproducible query tooling."
        ),
        "license_posture": (
            "CC BY-NC 4.0; commercial/release use requires explicit policy approval "
            "or separate consent."
        ),
        "verification_basis": "official GitHub README checked 2026-06-16",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_json(path)


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


def source_rows_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("source_id", "")): row for row in rows}


def verification_rows_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("source_id", "")): row for row in rows}


def local_path_inventory() -> dict[str, dict[str, Any]]:
    macula_lowfat = ROOT / "data" / "raw" / "macula" / "lowfat"
    return {
        "uxlc": {
            "local_path": "data/raw/uxlc/Tanach.xml.zip",
            "exists": (ROOT / "data" / "raw" / "uxlc" / "Tanach.xml.zip").exists(),
            "local_file_count": 1,
        },
        "oshb": {
            "local_path": "data/raw/oshb/Ps.xml",
            "exists": (ROOT / "data" / "raw" / "oshb" / "Ps.xml").exists(),
            "local_file_count": 1,
        },
        "macula": {
            "local_path": "data/raw/macula/lowfat",
            "exists": macula_lowfat.exists(),
            "local_file_count": len(sorted(macula_lowfat.glob("*-Psa-*-lowfat.xml"))),
        },
        "lxx": {
            "local_path": "data/raw/lxx",
            "exists": (ROOT / "data" / "raw" / "lxx").exists(),
            "local_file_count": len(sorted((ROOT / "data" / "raw" / "lxx").glob("*"))),
        },
        "asv": {
            "local_path": "data/raw/asv",
            "exists": (ROOT / "data" / "raw" / "asv").exists(),
            "local_file_count": len(sorted((ROOT / "data" / "raw" / "asv").glob("*"))),
        },
        "kjv": {
            "local_path": "data/raw/kjv",
            "exists": (ROOT / "data" / "raw" / "kjv").exists(),
            "local_file_count": len(sorted((ROOT / "data" / "raw" / "kjv").glob("*"))),
        },
        "web": {
            "local_path": "data/raw/web",
            "exists": (ROOT / "data" / "raw" / "web").exists(),
            "local_file_count": len(sorted((ROOT / "data" / "raw" / "web").glob("*"))),
        },
    }


def build_local_inventory_rows(morphology_gap: dict[str, Any]) -> list[dict[str, Any]]:
    paths = local_path_inventory()
    rows = []
    for row in morphology_gap.get("source_rows", []):
        source_id = str(row.get("source_id", ""))
        path_info = paths.get(source_id, {})
        rows.append(
            {
                "source_id": source_id,
                "name": row.get("name", ""),
                "local_path": path_info.get("local_path", ""),
                "exists": bool(path_info.get("exists", False)),
                "local_file_count": path_info.get("local_file_count", 0),
                "evidence_role": row.get("evidence_role", ""),
                "book_scope": row.get("book_scope", ""),
                "morphology_scope": row.get("morphology_scope", ""),
                "book_count_with_morphology": row.get("book_count_with_morphology", 0),
                "non_psalm_book_count_with_morphology": row.get(
                    "non_psalm_book_count_with_morphology",
                    0,
                ),
                "word_or_file_count": row.get("word_or_file_count", 0),
                "allowed_for_generation": bool(row.get("allowed_for_generation")),
                "authority_use": (
                    "primary Hebrew text"
                    if source_id == "uxlc"
                    else "enrichment/witness only; not authority without review"
                ),
            }
        )
    return rows


def build_candidate_rows(
    source_acquisition: dict[str, Any],
    bibliography: dict[str, Any],
    source_verification: dict[str, Any],
) -> list[dict[str, Any]]:
    bibliography_by_id = source_rows_by_id(bibliography.get("bibliography_rows", []))
    verification_by_id = verification_rows_by_id(source_verification.get("source_rows", []))
    rows = []
    for candidate in source_acquisition.get("candidate_rows", []):
        candidate_id = str(candidate.get("candidate_id", ""))
        if candidate_id not in MORPHOLOGY_CANDIDATE_IDS:
            continue
        sequence = RECOMMENDED_SEQUENCE[candidate_id]
        facts = OFFICIAL_SOURCE_FACTS[candidate_id]
        bibliography_row = bibliography_by_id.get(candidate_id, {})
        verification = verification_by_id.get(candidate_id, {})
        rows.append(
            {
                "recommended_rank": sequence["rank"],
                "candidate_id": candidate_id,
                "label": candidate.get("label", ""),
                "recommendation": sequence["recommendation"],
                "phase": sequence["phase"],
                "priority_score": candidate.get("priority_score", 0.0),
                "priority_band": candidate.get("priority_band", ""),
                "license_risk": candidate.get("license_risk", ""),
                "license_or_access": candidate.get("license_or_access", ""),
                "machine_readable": bool(candidate.get("machine_readable")),
                "current_repo_status": candidate.get("current_repo_status", ""),
                "acquisition_status": candidate.get("acquisition_status", ""),
                "packet_unit_count": candidate.get("packet_unit_count", 0),
                "highest_priority_family_unit_count": candidate.get(
                    "highest_priority_family_unit_count",
                    0,
                ),
                "source_families": candidate.get("source_families", []),
                "top_refs": candidate.get("top_refs", []),
                "official_url": facts["official_url"],
                "license_url": facts["license_url"],
                "observed_scope": facts["observed_scope"],
                "verified_license_posture": facts["license_posture"],
                "verification_basis": facts["verification_basis"],
                "reachable": verification.get("reachable", ""),
                "verification_status": verification.get("verification_status", ""),
                "license_claim_status": verification.get("license_claim_status", ""),
                "authority_status": bibliography_row.get(
                    "authority_status",
                    "candidate_not_approved",
                ),
                "generation_policy": bibliography_row.get(
                    "generation_policy",
                    "candidate_not_generation_basis_until_manifested",
                ),
                "why_this_sequence": sequence["why"],
                "authority_boundary": bibliography_row.get(
                    "authority_boundary",
                    (
                        "Candidate evidence cannot be used for generation, display, "
                        "export, or authority until manifested and reviewed."
                    ),
                ),
            }
        )
    return sorted(rows, key=lambda row: int(row["recommended_rank"]))


def build_gate_rows(
    morphology_gap: dict[str, Any],
    lexeme_readiness: dict[str, Any],
    source_acquisition: dict[str, Any],
    source_maturity: dict[str, Any],
    source_verification: dict[str, Any],
    oshb_pilot: dict[str, Any],
    oshb_exception_review: dict[str, Any],
    oshb_exception_taxonomy: dict[str, Any],
    oshb_mapping_rule_simulation: dict[str, Any],
) -> list[dict[str, Any]]:
    gap = morphology_gap["summary"]
    lexeme = lexeme_readiness["summary"]
    acquisition = source_acquisition["summary"]
    maturity = source_maturity["summary"]
    verification = source_verification["summary"]
    pilot_summary = oshb_pilot.get("summary", {})
    pilot_exists = bool(pilot_summary)
    exception_summary = oshb_exception_review.get("summary", {})
    exception_exists = bool(exception_summary)
    taxonomy_summary = oshb_exception_taxonomy.get("summary", {})
    taxonomy_exists = bool(taxonomy_summary)
    simulation_summary = oshb_mapping_rule_simulation.get("summary", {})
    simulation_exists = bool(simulation_summary)
    target_non_psalm = int(gap["uxlc_non_psalm_book_count"])
    local_non_psalm = int(gap["local_non_psalm_books_with_hebrew_morphology"])
    return [
        {
            "gate_id": "MORPH-G01",
            "gate": "Source approval and license/provenance decision",
            "status": "blocked",
            "score_pct": 0.0,
            "evidence": (
                f"{verification['source_approval_count']} source approvals recorded; "
                f"{verification['gap_count']} live verification gaps remain."
            ),
            "exit_criterion": (
                "Approved source manifest records license, attribution, import role, "
                "display/export policy, and release constraints."
            ),
            "next_action": (
                "Review OSHB, STEPBible, MACULA, and BHSA candidate rows; approve only "
                "sources whose terms fit the intended release path."
            ),
        },
        {
            "gate_id": "MORPH-G02",
            "gate": "Whole-Tanakh morphology source imported",
            "status": "blocked",
            "score_pct": pct(local_non_psalm, target_non_psalm),
            "evidence": (
                f"{local_non_psalm} of {target_non_psalm} non-Psalm books have local "
                "Hebrew morphology."
            ),
            "exit_criterion": (
                "All 38 non-Psalm Tanakh books have local token-level morphology, "
                "lemma, and alignment metadata available for audit."
            ),
            "next_action": (
                "Import OSHB morphhb whole-Tanakh data into a derived, version-pinned "
                "index outside data/raw."
            ),
        },
        {
            "gate_id": "MORPH-G03",
            "gate": "Version pin, hash, and reproducible importer",
            "status": "pilot_partial" if pilot_exists else "not_started",
            "score_pct": 40.0 if pilot_exists else 0.0,
            "evidence": (
                (
                    "OSHB pilot pins remote commit "
                    f"{pilot_summary.get('remote_commit_sha', '')}; "
                    "a reproducible derived importer and manifest are still absent."
                )
                if pilot_exists
                else (
                    f"{acquisition['candidate_count']} acquisition candidates exist, but "
                    "whole-Tanakh morphology candidate manifests are not imported."
                )
            ),
            "exit_criterion": (
                "Importer records upstream commit/release, content hash, parser version, "
                "and generated index checksum."
            ),
            "next_action": (
                "Create a non-raw derived importer and manifest for the approved "
                "whole-Tanakh morphology source."
            ),
        },
        {
            "gate_id": "MORPH-G04",
            "gate": "UXLC-to-morphology token alignment",
            "status": "pilot_partial" if pilot_exists else "not_started",
            "score_pct": (
                float(pilot_summary.get("exact_sequence_match_pct") or 0) if pilot_exists else 0.0
            ),
            "evidence": (
                (
                    "OSHB pilot maps "
                    f"{pilot_summary.get('mapped_book_count', 0)} books with "
                    f"{float(pilot_summary.get('mean_sequence_similarity_pct') or 0):.2f}% "
                    "mean normalized verse similarity, but "
                    f"{pilot_summary.get('mismatch_sample_row_count', 0)} exception "
                    "verses still need review."
                    + (
                        " The exception workbook separates "
                        f"{exception_summary.get('token_count_exception_verse_count', 0)} "
                        "token-count exceptions from "
                        f"{exception_summary.get('sequence_only_exception_verse_count', 0)} "
                        "sequence-only exceptions."
                        if exception_exists
                        else ""
                    )
                )
                if pilot_exists
                else (
                    "Current outside-Psalms context is normalized UXLC surface form only; "
                    "no local outside-Psalms Strong/lemma alignment exists."
                )
            ),
            "exit_criterion": (
                "Verse/book/token alignment reconciles ketiv/qere, punctuation, "
                "compound forms, morphology segmentation, and canonical IDs."
            ),
            "next_action": (
                "Build verse-level alignment first, then token-level exception reports "
                "for reviewers."
            ),
        },
        {
            "gate_id": "MORPH-G05",
            "gate": "Semantic role and referent enrichment",
            "status": "blocked",
            "score_pct": min(
                float(lexeme.get("semantic_role_coverage_pct", 0)),
                float(lexeme.get("referent_coverage_pct", 0)),
            ),
            "evidence": (
                f"Semantic-role coverage {fmt_pct(lexeme['semantic_role_coverage_pct'])}; "
                f"referent coverage {fmt_pct(lexeme['referent_coverage_pct'])}."
            ),
            "exit_criterion": (
                "Semantic-role and participant-referent fields are populated for "
                "review-relevant tokens and marked as enrichment, not source basis."
            ),
            "next_action": (
                "After morphology alignment, import MACULA semantic-role/referent "
                "fields where license and component provenance are approved."
            ),
        },
        {
            "gate_id": "MORPH-G06",
            "gate": "Whole-canon lexeme/sense query layer",
            "status": "not_started",
            "score_pct": 0.0,
            "evidence": (
                "Outside Strong context remains "
                f"{fmt_pct(gap['outside_strong_context_token_pct'])}; "
                f"surface-form bridge is {fmt_pct(gap['surface_outside_context_token_pct'])}."
            ),
            "exit_criterion": (
                "The benchmark can query canonical distribution by lemma, Strong key, "
                "morphology, sense, division, and aligned source token."
            ),
            "next_action": (
                "Materialize a derived whole-Tanakh lexeme index and expose it to "
                "context packet generation."
            ),
        },
        {
            "gate_id": "MORPH-G07",
            "gate": "Reviewer exception queue and signoff",
            "status": "blocked",
            "score_pct": 0.0,
            "evidence": (
                (
                    "OSHB exception workbook exports "
                    f"{
                        exception_summary.get(
                            'review_row_count',
                            exception_summary.get('sample_row_count', 0),
                        )
                    } "
                    "review rows for "
                    f"{exception_summary.get('mismatch_verse_count', 0)} remaining "
                    "exception verses; "
                    + (
                        "full enumeration is complete. "
                        if int(exception_summary.get("unexported_exception_row_count", 0)) == 0
                        else (
                            f"{exception_summary.get('unexported_exception_row_count', 0)} "
                            "exception rows still need full enumeration. "
                        )
                    )
                )
                if exception_exists
                else ""
            )
            + (
                (
                    "Exception taxonomy groups those rows into "
                    f"{taxonomy_summary.get('taxonomy_cause_count', 0)} cause families "
                    f"and {taxonomy_summary.get('review_batch_count', 0)} queued "
                    "review batches. "
                )
                if taxonomy_exists
                else ""
            )
            + (
                (
                    "Mapping-rule simulation routes "
                    f"{simulation_summary.get('candidate_rule_reduction_row_count', 0)} "
                    "rows into candidate rule lanes and leaves "
                    f"{simulation_summary.get('manual_residual_row_count', 0)} "
                    "manual/textual residual rows. "
                )
                if simulation_exists
                else ""
            )
            + (
                f"{maturity['blocked_authority_lane_count']} authority lanes remain "
                "blocked in source maturity; no source approval can be inferred."
            ),
            "exit_criterion": (
                "Hebrew, lexical, alignment, provenance, license, and release reviewers "
                "sign off importer exceptions and source use."
            ),
            "next_action": (
                "Generate exception queues for token mismatches, source conflicts, "
                "ambiguous lemmas, and release-policy decisions."
            ),
        },
        {
            "gate_id": "MORPH-G08",
            "gate": "Authority boundary enforcement",
            "status": "blocked",
            "score_pct": 0.0,
            "evidence": (
                "No generated morphology import, source packet, or model output is "
                "canonical authority without human release signoff."
            ),
            "exit_criterion": (
                "Reports, prompts, and model scorers label source roles correctly and "
                "block candidate data from becoming silent translation authority."
            ),
            "next_action": (
                "Keep generated evidence in review lanes until source-use and release gates pass."
            ),
        },
    ]


def build_phase_rows(
    candidate_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gates_by_phase = {
        "phase_1_primary_morphology": ["MORPH-G01", "MORPH-G02", "MORPH-G03", "MORPH-G04"],
        "phase_1b_parallel_lexical_semantic_enrichment": [
            "MORPH-G01",
            "MORPH-G03",
            "MORPH-G06",
        ],
        "phase_2_semantic_role_referent_enrichment": [
            "MORPH-G01",
            "MORPH-G03",
            "MORPH-G05",
        ],
        "phase_3_research_only_comparator": ["MORPH-G01", "MORPH-G08"],
    }
    candidate_by_phase = {str(row["phase"]): row for row in candidate_rows}
    gate_by_id = {str(row["gate_id"]): row for row in gate_rows}
    rows = []
    for phase, gate_ids in gates_by_phase.items():
        candidate = candidate_by_phase.get(phase, {})
        related_gates = [gate_by_id[gate_id] for gate_id in gate_ids if gate_id in gate_by_id]
        blocked = sum(1 for gate in related_gates if gate["status"] == "blocked")
        not_started = sum(1 for gate in related_gates if gate["status"] == "not_started")
        mean_score = (
            round(
                sum(float(gate["score_pct"]) for gate in related_gates) / len(related_gates),
                2,
            )
            if related_gates
            else 0.0
        )
        rows.append(
            {
                "phase": phase,
                "rank": candidate.get("recommended_rank", 99),
                "primary_candidate_id": candidate.get("candidate_id", ""),
                "primary_candidate_label": candidate.get("label", ""),
                "status": "blocked" if blocked else "not_started" if not_started else "ready",
                "mean_gate_score_pct": mean_score,
                "blocked_gate_count": blocked,
                "not_started_gate_count": not_started,
                "gate_ids": gate_ids,
                "exit_criterion": "; ".join(str(gate["exit_criterion"]) for gate in related_gates),
            }
        )
    return sorted(rows, key=lambda row: int(row["rank"]))


def build_visual_data(
    morphology_gap: dict[str, Any],
    candidate_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    gap = morphology_gap["summary"]
    target_non_psalm = int(gap["uxlc_non_psalm_book_count"])
    local_non_psalm = int(gap["local_non_psalm_books_with_hebrew_morphology"])
    license_counts = Counter(str(row["license_risk"]) for row in candidate_rows)
    gate_status_counts = Counter(str(row["status"]) for row in gate_rows)
    return {
        "coverage_rows": [
            {
                "label": "whole-Tanakh Hebrew text books",
                "count": gap["uxlc_book_count"],
                "target": gap["uxlc_book_count"],
                "pct": 100.0,
            },
            {
                "label": "Psalm books with local morphology",
                "count": gap["local_books_with_hebrew_morphology"],
                "target": 1,
                "pct": 100.0 if gap["local_books_with_hebrew_morphology"] else 0.0,
            },
            {
                "label": "non-Psalm books with local morphology",
                "count": local_non_psalm,
                "target": target_non_psalm,
                "pct": pct(local_non_psalm, target_non_psalm),
            },
            {
                "label": "outside-Psalms Strong context",
                "count": gap["outside_strong_context_token_pct"],
                "target": 100,
                "pct": gap["outside_strong_context_token_pct"],
            },
            {
                "label": "outside-Psalms surface bridge",
                "count": gap["surface_outside_context_token_pct"],
                "target": 100,
                "pct": gap["surface_outside_context_token_pct"],
            },
        ],
        "candidate_priority_rows": [
            {
                "label": row["label"],
                "candidate_id": row["candidate_id"],
                "priority_score": row["priority_score"],
                "recommended_rank": row["recommended_rank"],
                "license_risk": row["license_risk"],
            }
            for row in candidate_rows
        ],
        "license_risk_rows": [
            {"license_risk": license_risk, "candidate_count": count}
            for license_risk, count in sorted(license_counts.items())
        ],
        "gate_status_rows": [
            {"status": status, "gate_count": count}
            for status, count in sorted(gate_status_counts.items())
        ],
        "gate_score_rows": [
            {
                "gate": row["gate"],
                "score_pct": row["score_pct"],
                "status": row["status"],
            }
            for row in gate_rows
        ],
    }


def summarize(
    *,
    morphology_gap: dict[str, Any],
    lexeme_readiness: dict[str, Any],
    candidate_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    phase_rows: list[dict[str, Any]],
    local_inventory_rows: list[dict[str, Any]],
    oshb_pilot: dict[str, Any],
    oshb_exception_review: dict[str, Any],
    oshb_exception_taxonomy: dict[str, Any],
    oshb_mapping_rule_simulation: dict[str, Any],
) -> dict[str, Any]:
    gap = morphology_gap["summary"]
    lexeme = lexeme_readiness["summary"]
    blocked_gate_count = sum(1 for row in gate_rows if row["status"] == "blocked")
    not_started_gate_count = sum(1 for row in gate_rows if row["status"] == "not_started")
    pilot_partial_gate_count = sum(1 for row in gate_rows if row["status"] == "pilot_partial")
    low_risk = sum(1 for row in candidate_rows if row["license_risk"] == "low")
    research_only = sum(
        1
        for row in candidate_rows
        if row["recommendation"] == "research_only_until_license_decision"
    )
    first_import = next(row for row in candidate_rows if row["recommendation"] == "first_import")
    semantic_enrichment = next(
        row
        for row in candidate_rows
        if row["recommendation"] == "semantic_role_and_referent_import"
    )
    pilot_summary = oshb_pilot.get("summary", {})
    exception_summary = oshb_exception_review.get("summary", {})
    taxonomy_summary = oshb_exception_taxonomy.get("summary", {})
    simulation_summary = oshb_mapping_rule_simulation.get("summary", {})
    return {
        "whole_tanakh_text_book_count": gap["uxlc_book_count"],
        "target_non_psalm_book_count": gap["uxlc_non_psalm_book_count"],
        "psalm_morphology_book_count": gap["local_books_with_hebrew_morphology"],
        "local_non_psalm_morphology_book_count": gap[
            "local_non_psalm_books_with_hebrew_morphology"
        ],
        "local_non_psalm_morphology_coverage_pct": gap["local_non_psalm_morphology_book_pct"],
        "local_non_psalm_morphology_gap_book_count": (
            int(gap["uxlc_non_psalm_book_count"])
            - int(gap["local_non_psalm_books_with_hebrew_morphology"])
        ),
        "outside_strong_context_token_pct": gap["outside_strong_context_token_pct"],
        "surface_outside_context_token_pct": gap["surface_outside_context_token_pct"],
        "psalm_strong_coverage_pct": gap["psalm_token_strong_coverage_pct"],
        "psalm_lemma_coverage_pct": gap["psalm_token_lemma_coverage_pct"],
        "semantic_role_coverage_pct": lexeme["semantic_role_coverage_pct"],
        "referent_coverage_pct": lexeme["referent_coverage_pct"],
        "local_inventory_source_count": len(local_inventory_rows),
        "morphology_candidate_count": len(candidate_rows),
        "machine_readable_candidate_count": sum(
            1 for row in candidate_rows if row["machine_readable"]
        ),
        "low_license_risk_candidate_count": low_risk,
        "research_only_candidate_count": research_only,
        "blocked_gate_count": blocked_gate_count,
        "not_started_gate_count": not_started_gate_count,
        "pilot_partial_gate_count": pilot_partial_gate_count,
        "phase_count": len(phase_rows),
        "recommended_first_import_candidate": first_import["candidate_id"],
        "recommended_first_import_label": first_import["label"],
        "recommended_semantic_enrichment_candidate": semantic_enrichment["candidate_id"],
        "recommended_semantic_enrichment_label": semantic_enrichment["label"],
        "oshb_alignment_pilot_exists": bool(pilot_summary),
        "oshb_alignment_pilot_mapped_book_count": pilot_summary.get("mapped_book_count", 0),
        "oshb_alignment_pilot_mapped_non_psalm_book_count": pilot_summary.get(
            "mapped_non_psalm_book_count",
            0,
        ),
        "oshb_alignment_pilot_mean_sequence_similarity_pct": pilot_summary.get(
            "mean_sequence_similarity_pct",
            0.0,
        ),
        "oshb_alignment_pilot_exact_sequence_match_pct": pilot_summary.get(
            "exact_sequence_match_pct",
            0.0,
        ),
        "oshb_alignment_pilot_mismatch_row_count": pilot_summary.get(
            "mismatch_sample_row_count",
            0,
        ),
        "oshb_exception_review_exists": bool(exception_summary),
        "oshb_exception_review_mismatch_verse_count": exception_summary.get(
            "mismatch_verse_count",
            0,
        ),
        "oshb_exception_review_token_count_exception_verse_count": exception_summary.get(
            "token_count_exception_verse_count",
            0,
        ),
        "oshb_exception_review_sequence_only_exception_verse_count": exception_summary.get(
            "sequence_only_exception_verse_count",
            0,
        ),
        "oshb_exception_review_sample_row_count": exception_summary.get("sample_row_count", 0),
        "oshb_exception_review_review_row_count": exception_summary.get(
            "review_row_count",
            exception_summary.get("sample_row_count", 0),
        ),
        "oshb_exception_review_unexported_exception_row_count": exception_summary.get(
            "unexported_exception_row_count",
            0,
        ),
        "oshb_exception_review_critical_book_count": exception_summary.get(
            "critical_book_count",
            0,
        ),
        "oshb_exception_taxonomy_exists": bool(taxonomy_summary),
        "oshb_exception_taxonomy_cause_count": taxonomy_summary.get("taxonomy_cause_count", 0),
        "oshb_exception_taxonomy_review_batch_count": taxonomy_summary.get(
            "review_batch_count",
            0,
        ),
        "oshb_exception_taxonomy_top_cause_family": taxonomy_summary.get(
            "top_cause_family",
            "",
        ),
        "oshb_exception_taxonomy_top_cause_row_count": taxonomy_summary.get(
            "top_cause_row_count",
            0,
        ),
        "oshb_exception_taxonomy_segmentation_marker_pct": taxonomy_summary.get(
            "segmentation_marker_pct",
            0.0,
        ),
        "oshb_mapping_rule_simulation_exists": bool(simulation_summary),
        "oshb_mapping_rule_simulation_rule_candidate_after_review_count": (
            simulation_summary.get("rule_candidate_after_review_count", 0)
        ),
        "oshb_mapping_rule_simulation_targeted_rule_review_count": simulation_summary.get(
            "targeted_rule_review_count",
            0,
        ),
        "oshb_mapping_rule_simulation_candidate_rule_reduction_pct": simulation_summary.get(
            "candidate_rule_reduction_pct",
            0.0,
        ),
        "oshb_mapping_rule_simulation_manual_residual_row_count": simulation_summary.get(
            "manual_residual_row_count",
            0,
        ),
        "authority_verdict": (
            "not_ready: local non-Psalm morphology is zero, source approval is zero, "
            "and import/alignment/reviewer gates are not complete."
        ),
        "source_boundary_status": gap["source_boundary_status"],
        "status": "readiness_generated_not_source_approval",
    }


def build_report() -> dict[str, Any]:
    morphology_gap = load_json(MORPHOLOGY_GAP_PATH)
    source_acquisition = load_json(SOURCE_ACQUISITION_PATH)
    bibliography = load_json(BIBLIOGRAPHY_PATH)
    source_maturity = load_json(SOURCE_MATURITY_PATH)
    source_verification = load_json(SOURCE_VERIFICATION_PATH)
    lexeme_readiness = load_json(LEXEME_READINESS_PATH)
    oshb_pilot = load_optional_json(OSHB_ALIGNMENT_PILOT_PATH)
    oshb_exception_review = load_optional_json(OSHB_EXCEPTION_REVIEW_PATH)
    oshb_exception_taxonomy = load_optional_json(OSHB_EXCEPTION_TAXONOMY_PATH)
    oshb_mapping_rule_simulation = load_optional_json(OSHB_MAPPING_RULE_SIMULATION_PATH)

    local_inventory_rows = build_local_inventory_rows(morphology_gap)
    candidate_rows = build_candidate_rows(
        source_acquisition,
        bibliography,
        source_verification,
    )
    gate_rows = build_gate_rows(
        morphology_gap,
        lexeme_readiness,
        source_acquisition,
        source_maturity,
        source_verification,
        oshb_pilot,
        oshb_exception_review,
        oshb_exception_taxonomy,
        oshb_mapping_rule_simulation,
    )
    phase_rows = build_phase_rows(candidate_rows, gate_rows)
    visual_data = build_visual_data(morphology_gap, candidate_rows, gate_rows)
    summary = summarize(
        morphology_gap=morphology_gap,
        lexeme_readiness=lexeme_readiness,
        candidate_rows=candidate_rows,
        gate_rows=gate_rows,
        phase_rows=phase_rows,
        local_inventory_rows=local_inventory_rows,
        oshb_pilot=oshb_pilot,
        oshb_exception_review=oshb_exception_review,
        oshb_exception_taxonomy=oshb_exception_taxonomy,
        oshb_mapping_rule_simulation=oshb_mapping_rule_simulation,
    )
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "whole-Tanakh morphology acquisition readiness generated",
        "source_paths": {
            "whole_tanakh_morphology_gap": str(MORPHOLOGY_GAP_PATH.relative_to(ROOT)),
            "contextual_source_acquisition_plan": str(SOURCE_ACQUISITION_PATH.relative_to(ROOT)),
            "doctoral_bibliography_provenance": str(BIBLIOGRAPHY_PATH.relative_to(ROOT)),
            "scholarly_source_maturity_report": str(SOURCE_MATURITY_PATH.relative_to(ROOT)),
            "doctoral_source_verification": str(SOURCE_VERIFICATION_PATH.relative_to(ROOT)),
            "lexeme_context_readiness": str(LEXEME_READINESS_PATH.relative_to(ROOT)),
            "oshb_whole_tanakh_alignment_pilot": (
                str(OSHB_ALIGNMENT_PILOT_PATH.relative_to(ROOT))
                if OSHB_ALIGNMENT_PILOT_PATH.exists()
                else ""
            ),
            "oshb_alignment_exception_review": (
                str(OSHB_EXCEPTION_REVIEW_PATH.relative_to(ROOT))
                if OSHB_EXCEPTION_REVIEW_PATH.exists()
                else ""
            ),
            "oshb_exception_taxonomy": (
                str(OSHB_EXCEPTION_TAXONOMY_PATH.relative_to(ROOT))
                if OSHB_EXCEPTION_TAXONOMY_PATH.exists()
                else ""
            ),
            "oshb_mapping_rule_simulation": (
                str(OSHB_MAPPING_RULE_SIMULATION_PATH.relative_to(ROOT))
                if OSHB_MAPPING_RULE_SIMULATION_PATH.exists()
                else ""
            ),
        },
        "method": {
            "boundary": (
                "This report ranks source-acquisition readiness only. It does not "
                "approve source use, edit canonical renderings, or import external data."
            ),
            "candidate_selection": (
                "Restricted to whole-Tanakh morphology, lexeme, semantic-role, and "
                "research-grade Hebrew annotation candidates already present in the "
                "contextual source-acquisition plan."
            ),
            "recommendation_logic": (
                "First import favors direct fit, license posture, existing local pipeline "
                "continuity, and lower alignment blast radius over broad candidate score alone."
            ),
            "pilot_boundary": (
                "OSHB alignment pilot evidence can reduce technical uncertainty, but "
                "does not approve source use, import raw data, or authorize translation "
                "wording."
            ),
        },
        "summary": summary,
        "local_inventory_rows": local_inventory_rows,
        "candidate_rows": candidate_rows,
        "gate_rows": gate_rows,
        "phase_rows": phase_rows,
        "visual_data": visual_data,
    }


def metric_cards(cards: list[tuple[str, Any, str]]) -> str:
    return (
        '<div class="grid">'
        + "".join(
            '<article class="card">'
            f'<div class="metric">{esc(value)}</div>'
            f'<div class="label">{esc(label)}</div>'
            f"<p>{esc(note)}</p>"
            "</article>"
            for label, value, note in cards
        )
        + "</div>"
    )


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    width: int = 1040,
    limit: int = 18,
) -> str:
    rows = rows[:limit]
    row_h = 32
    left = 360
    right = 100
    top = 24
    height = top * 2 + row_h * max(1, len(rows))
    max_value = max((float(row.get(value_key) or 0) for row in rows), default=1.0)
    chart_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, row in enumerate(rows):
        value = float(row.get(value_key) or 0)
        y = top + index * row_h
        bar_w = chart_w * value / max_value if max_value else 0
        parts.append(
            f'<text x="{left - 12}" y="{y + 20}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row.get(label_key, ""))}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 5}" width="{bar_w:.1f}" height="19" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 20}" font-size="12" '
            f'font-weight="700" fill="#24313a">{value:g}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    local_rows = report["local_inventory_rows"]
    candidate_rows = report["candidate_rows"]
    gate_rows = report["gate_rows"]
    phase_rows = report["phase_rows"]

    local_table = [
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
        for row in local_rows
    ]
    candidate_table = [
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
        for row in candidate_rows
    ]
    gate_table = [
        [
            row["gate_id"],
            row["gate"],
            row["status"],
            f"{float(row['score_pct']):.2f}%",
            row["evidence"],
            row["exit_criterion"],
            row["next_action"],
        ]
        for row in gate_rows
    ]
    phase_table = [
        [
            row["rank"],
            row["phase"],
            row["primary_candidate_label"],
            row["status"],
            f"{float(row['mean_gate_score_pct']):.2f}%",
            row["blocked_gate_count"],
            row["not_started_gate_count"],
            ", ".join(row["gate_ids"]),
        ]
        for row in phase_rows
    ]
    source_fact_table = [
        [
            row["label"],
            row["official_url"],
            row["observed_scope"],
            row["verified_license_posture"],
            row["verification_basis"],
        ]
        for row in candidate_rows
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Whole-Tanakh Morphology Acquisition Readiness</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #596875;
      --line: #cfd7de;
      --panel: #f7f9fb;
      --accent: #2f6f73;
      --accent2: #805a2b;
      --bad: #a12727;
      --warn: #a96600;
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
    main {{ max-width: 1220px; margin: 0 auto; padding: 30px 34px 56px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    p {{ margin: 0 0 13px; }}
    a {{ color: #245e91; }}
    .lede {{ max-width: 1000px; font-size: 17px; color: #33414c; }}
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
      background: #fff4f4;
      border-left: 4px solid var(--bad);
      padding: 13px 15px;
      margin: 18px 0;
    }}
    .note {{
      background: #f8fbfb;
      border-left: 4px solid var(--accent);
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
    th {{ background: var(--panel); text-align: left; }}
    code {{ background: #eef2f5; padding: 1px 4px; border-radius: 3px; }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Whole-Tanakh Morphology Acquisition Readiness</h1>
    <p class="lede">
      A hard-data acquisition plan for moving AlephTav from Psalm-only Hebrew
      morphology to auditable whole-Tanakh morphology, lemma, semantic-role,
      and referent context. This report ranks candidate imports and gates, but
      it does not approve source use or change translation authority.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Readiness Verdict</h2>
      {
        metric_cards(
            [
                (
                    "Non-Psalm morph books",
                    fmt_int(summary["local_non_psalm_morphology_book_count"]),
                    f"Target is {fmt_int(summary['target_non_psalm_book_count'])} non-Psalm books.",
                ),
                (
                    "Surface bridge",
                    fmt_pct(summary["surface_outside_context_token_pct"]),
                    "Useful context, but not lemma or sense authority.",
                ),
                (
                    "Outside Strong context",
                    fmt_pct(summary["outside_strong_context_token_pct"]),
                    "True outside-Psalms Strong evidence currently local.",
                ),
                (
                    "Candidate sources",
                    fmt_int(summary["morphology_candidate_count"]),
                    f"{fmt_int(summary['machine_readable_candidate_count'])} are machine-readable.",
                ),
                (
                    "Low-risk candidates",
                    fmt_int(summary["low_license_risk_candidate_count"]),
                    "Still require source manifests and approvals.",
                ),
                (
                    "Blocked gates",
                    fmt_int(summary["blocked_gate_count"]),
                    f"{fmt_int(summary['not_started_gate_count'])} additional gates "
                    "are not started.",
                ),
                (
                    "Pilot-partial gates",
                    fmt_int(summary["pilot_partial_gate_count"]),
                    "Technical pilot evidence exists but does not close approval gates.",
                ),
                (
                    "OSHB pilot",
                    f"{float(summary['oshb_alignment_pilot_mean_sequence_similarity_pct']):.2f}%",
                    f"{fmt_int(summary['oshb_alignment_pilot_mapped_non_psalm_book_count'])} "
                    "non-Psalm books mapped.",
                ),
                (
                    "First import",
                    summary["recommended_first_import_candidate"],
                    summary["recommended_first_import_label"],
                ),
                (
                    "Semantic enrichment",
                    summary["recommended_semantic_enrichment_candidate"],
                    summary["recommended_semantic_enrichment_label"],
                ),
            ]
        )
    }
      <div class="warning">
        <strong>Authority boundary:</strong>
        {esc(summary["authority_verdict"])}
      </div>
      <div class="note">
        <strong>Sequence logic:</strong>
        OSHB is recommended first because it directly extends the existing
        Psalm morphology pipeline. STEPBible remains a high-value parallel
        lexical/semantic import; MACULA targets semantic roles and referents;
        BHSA stays research-only under its noncommercial posture.
      </div>
    </section>

    <section>
      <h2>Coverage Baseline</h2>
      <div class="chart">
        {
        svg_horizontal_bars(
            visual["coverage_rows"],
            label_key="label",
            value_key="pct",
            aria_label="Current whole-Tanakh morphology coverage percentages",
            color="#2f6f73",
        )
    }
      </div>
    </section>

    <section>
      <h2>Candidate Priority</h2>
      <div class="chart">
        {
        svg_horizontal_bars(
            visual["candidate_priority_rows"],
            label_key="label",
            value_key="priority_score",
            aria_label="Morphology candidate priority scores",
            color="#805a2b",
        )
    }
      </div>
      {
        table(
            [
                "rank",
                "candidate",
                "recommendation",
                "priority",
                "license risk",
                "repo status",
                "authority status",
                "sequence rationale",
            ],
            candidate_table,
        )
    }
    </section>

    <section>
      <h2>Import Gates</h2>
      <div class="chart">
        {
        svg_horizontal_bars(
            visual["gate_score_rows"],
            label_key="gate",
            value_key="score_pct",
            aria_label="Morphology import gate scores",
            color="#a12727",
        )
    }
      </div>
      {
        table(
            [
                "gate",
                "name",
                "status",
                "score",
                "evidence",
                "exit criterion",
                "next action",
            ],
            gate_table,
        )
    }
    </section>

    <section>
      <h2>Phased Work Plan</h2>
      {
        table(
            [
                "rank",
                "phase",
                "primary candidate",
                "status",
                "mean gate score",
                "blocked",
                "not started",
                "gates",
            ],
            phase_table,
        )
    }
    </section>

    <section>
      <h2>Local Inventory</h2>
      {
        table(
            [
                "source",
                "path",
                "exists",
                "files",
                "book scope",
                "morphology scope",
                "non-Psalm morph books",
                "authority use",
            ],
            local_table,
        )
    }
    </section>

    <section>
      <h2>Official Source Facts</h2>
      {
        table(
            [
                "candidate",
                "official URL",
                "observed scope",
                "license posture",
                "verification basis",
            ],
            source_fact_table,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate whole-Tanakh morphology acquisition readiness report."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument(
        "--candidate-csv-output",
        type=Path,
        default=DEFAULT_CANDIDATE_CSV_OUTPUT,
    )
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument(
        "--local-inventory-csv-output",
        type=Path,
        default=DEFAULT_LOCAL_INVENTORY_CSV_OUTPUT,
    )
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.candidate_csv_output, report["candidate_rows"])
    write_csv(args.gate_csv_output, report["gate_rows"])
    write_csv(args.local_inventory_csv_output, report["local_inventory_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.candidate_csv_output}")
    print(f"Wrote {args.gate_csv_output}")
    print(f"Wrote {args.local_inventory_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
