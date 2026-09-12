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
    "local_bakeoff": REPORT_ROOT / "local_model_doctoral_bakeoff_matrix.json",
    "local_selection": REPORT_ROOT / "local_model_selection_roadmap.json",
    "model_gap": REPORT_ROOT / "model_evidence_gap_report.json",
    "contextual_model": REPORT_ROOT / "contextual_real_model_evidence_matrix.json",
    "claim_traceability": REPORT_ROOT / "translation_claim_traceability_audit.json",
    "semantic_referent": REPORT_ROOT / "semantic_referent_enrichment_roadmap.json",
    "source_ladder": REPORT_ROOT / "source_authority_ladder_matrix.json",
    "authority_path": REPORT_ROOT / "authority_critical_path_report.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "model_training_certification_roadmap.json"
DEFAULT_CANDIDATE_CSV_OUTPUT = REPORT_ROOT / "model_training_certification_candidates.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "model_training_certification_gates.csv"
DEFAULT_PHASE_CSV_OUTPUT = REPORT_ROOT / "model_training_certification_phases.csv"
DEFAULT_SOURCE_CSV_OUTPUT = REPORT_ROOT / "model_training_certification_sources.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "model_training_certification_roadmap.html"

TARGET_GPU_PROFILE = {
    "label": "RTX 3090-class target",
    "target_vram_gb": 24.0,
    "policy": (
        "Treat 24 GB VRAM as the local target ceiling. Prefer quantized inference "
        "and LoRA/QLoRA adapters; do not plan full fine-tuning on this hardware."
    ),
}

PUBLIC_MODEL_FACTS: list[dict[str, Any]] = [
    {
        "model": "google/gemma-4-12B-it",
        "short_name": "Gemma 4 12B",
        "public_role": "primary trainable base candidate",
        "params_b": 12.0,
        "activated_params_b": "",
        "context_tokens": "",
        "known_q4_memory_gb": 6.7,
        "known_qlora_vram_gb": "",
        "public_fit_basis": "Google Gemma 4 docs list 12B Q4_0 memory at 6.7 GB.",
        "public_fact": (
            "Gemma 4 ships in E2B, E4B, 12B, 26B A4B, and 31B sizes; the 12B "
            "Q4_0 memory estimate is well below the 24 GB target."
        ),
        "source_urls": "https://ai.google.dev/gemma/docs/core",
    },
    {
        "model": "google/gemma-4-26B-A4B-it",
        "short_name": "Gemma 4 26B-A4B",
        "public_role": "strong local inference candidate",
        "params_b": 26.0,
        "activated_params_b": 4.0,
        "context_tokens": "",
        "known_q4_memory_gb": 14.4,
        "known_qlora_vram_gb": "",
        "public_fit_basis": "Google Gemma 4 docs list 26B A4B Q4_0 memory at 14.4 GB.",
        "public_fact": (
            "Gemma 4 26B A4B is a mixture-of-experts model; Q4_0 inference fits the "
            "24 GB target, but this repo still records source-anchor and layer blockers."
        ),
        "source_urls": "https://ai.google.dev/gemma/docs/core",
    },
    {
        "model": "google/gemma-4-31B-it",
        "short_name": "Gemma 4 31B",
        "public_role": "frontier local inference challenger",
        "params_b": 31.0,
        "activated_params_b": "",
        "context_tokens": "",
        "known_q4_memory_gb": 17.5,
        "known_qlora_vram_gb": "",
        "public_fit_basis": "Google Gemma 4 docs list 31B Q4_0 memory at 17.5 GB.",
        "public_fact": (
            "Gemma 4 31B is above the current bakeoff list but has a documented Q4_0 "
            "memory estimate below the 24 GB target."
        ),
        "source_urls": "https://ai.google.dev/gemma/docs/core",
    },
    {
        "model": "google/gemma-3-27b-it",
        "short_name": "Gemma 3 27B",
        "public_role": "legacy Gemma frontier comparator",
        "params_b": 27.0,
        "activated_params_b": "",
        "context_tokens": 128000,
        "known_q4_memory_gb": "",
        "known_qlora_vram_gb": "",
        "public_fit_basis": (
            "Model card gives 128K context and 140+ language support; local quantized "
            "asset and exact VRAM measurement are still required."
        ),
        "public_fact": (
            "Gemma 3 27B is a multilingual open-weight candidate with 128K context; "
            "it should be treated as an intake candidate until measured locally."
        ),
        "source_urls": "https://huggingface.co/google/gemma-3-27b-it",
    },
    {
        "model": "Qwen/Qwen3-30B-A3B-Instruct-2507",
        "short_name": "Qwen3 30B-A3B 2507",
        "public_role": "frontier MoE QLoRA challenger",
        "params_b": 30.5,
        "activated_params_b": 3.3,
        "context_tokens": 262144,
        "known_q4_memory_gb": "",
        "known_qlora_vram_gb": 17.5,
        "public_fit_basis": (
            "Qwen model card lists 30.5B total/3.3B activated and 262,144 context; "
            "Unsloth documents Qwen3-30B-A3B QLoRA at 17.5 GB VRAM."
        ),
        "public_fact": (
            "This is the strongest 3090-class MoE training challenger, but it is not "
            "in the current bakeoff and would need exact asset, disk/RAM, and benchmark intake."
        ),
        "source_urls": (
            "https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507; "
            "https://unsloth.ai/docs/models/tutorials/qwen3-how-to-run-and-fine-tune"
        ),
    },
    {
        "model": "dicta-il/DictaLM-3.0-Nemotron-12B-Instruct",
        "short_name": "DictaLM 12B",
        "public_role": "Hebrew specialist challenger",
        "params_b": 12.0,
        "activated_params_b": "",
        "context_tokens": "",
        "known_q4_memory_gb": "",
        "known_qlora_vram_gb": "",
        "public_fit_basis": (
            "Dicta describes this as a 12B Hebrew/English open-weight model; exact "
            "local quantization must be acquired and measured."
        ),
        "public_fact": (
            "DictaLM 3.0 is the strongest Hebrew-specialist challenger in the current "
            "plan, but no exact local asset is present yet."
        ),
        "source_urls": "https://huggingface.co/dicta-il/DictaLM-3.0-Nemotron-12B-Instruct",
    },
    {
        "model": "facebook/nllb-200-3.3B",
        "short_name": "NLLB-200 3.3B",
        "public_role": "machine translation baseline",
        "params_b": 3.3,
        "activated_params_b": "",
        "context_tokens": "",
        "known_q4_memory_gb": "",
        "known_qlora_vram_gb": "",
        "public_fit_basis": (
            "NLLB-200 is a single-sentence MT research baseline, not a conversational "
            "authority model."
        ),
        "public_fact": (
            "Useful as a translation comparator for Hebrew-to-English candidates, but "
            "not sufficient for Psalms-level context, reception, or release authority."
        ),
        "source_urls": "https://huggingface.co/facebook/nllb-200-3.3B",
    },
    {
        "model": "google/madlad400-10b-mt",
        "short_name": "MADLAD-400 10B MT",
        "public_role": "machine translation baseline",
        "params_b": 10.0,
        "activated_params_b": "",
        "context_tokens": "",
        "known_q4_memory_gb": "",
        "known_qlora_vram_gb": "",
        "public_fit_basis": (
            "MADLAD-400-10B-MT is a multilingual MT model; local execution and Hebrew "
            "coverage must be verified in the repo benchmark."
        ),
        "public_fact": (
            "Useful as a broad MT comparator, but it cannot supply scholarly context, "
            "source provenance, Jewish/Christian separation, or reviewer signoff."
        ),
        "source_urls": "https://huggingface.co/google/madlad400-10b-mt",
    },
    {
        "model": "CohereLabs/aya-expanse-32b",
        "short_name": "Aya Expanse 32B",
        "public_role": "multilingual judge/comparator",
        "params_b": 32.0,
        "activated_params_b": "",
        "context_tokens": 128000,
        "known_q4_memory_gb": "",
        "known_qlora_vram_gb": "",
        "public_fit_basis": (
            "Cohere docs list Aya Expanse 32B with 128K context; license and local "
            "quantized execution must be reviewed before local use."
        ),
        "public_fact": (
            "A useful multilingual comparison model, but not a first-choice local "
            "training base until license, asset, and benchmark gates pass."
        ),
        "source_urls": "https://docs.cohere.com/docs/aya-expanse",
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
            writer.writerow(
                {
                    key: "; ".join(value) if isinstance(value, list) else value
                    for key, value in row.items()
                }
            )


def pct(numerator: float, denominator: float) -> float:
    return round((numerator / denominator * 100.0), 2) if denominator else 0.0


def fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def fit_status(fact: dict[str, Any]) -> tuple[str, float]:
    target_vram = float(TARGET_GPU_PROFILE["target_vram_gb"])
    q4_memory = fact.get("known_q4_memory_gb")
    qlora_vram = fact.get("known_qlora_vram_gb")
    params = fact.get("params_b")
    if isinstance(q4_memory, int | float) and q4_memory <= target_vram:
        return "fits_3090_known_q4", 100.0
    if isinstance(qlora_vram, int | float) and qlora_vram <= target_vram:
        return "fits_3090_known_qlora", 90.0
    if isinstance(params, int | float) and params <= 12:
        return "probable_q4_fit_verify_asset", 70.0
    return "unknown_or_requires_exact_local_measurement", 35.0


def authority_status(summary: dict[str, Any]) -> str:
    if summary["claim_text_allowed_now"] > 0:
        return "review_limited_candidate"
    return "blocked_no_translation_text_authority"


def row_float(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def build_public_source_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, fact in enumerate(PUBLIC_MODEL_FACTS, start=1):
        fit, fit_score = fit_status(fact)
        rows.append(
            {
                "rank": index,
                "model": fact["model"],
                "short_name": fact["short_name"],
                "public_role": fact["public_role"],
                "params_b": fact["params_b"],
                "activated_params_b": fact["activated_params_b"],
                "context_tokens": fact["context_tokens"],
                "known_q4_memory_gb": fact["known_q4_memory_gb"],
                "known_qlora_vram_gb": fact["known_qlora_vram_gb"],
                "fit_status": fit,
                "fit_score_pct": fit_score,
                "public_fit_basis": fact["public_fit_basis"],
                "public_fact": fact["public_fact"],
                "source_urls": fact["source_urls"],
            }
        )
    return rows


def build_summary(
    data: dict[str, dict[str, Any]], public_source_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    bakeoff = data["local_bakeoff"]["summary"]
    model_gap = data["model_gap"]["summary"]
    contextual = data["contextual_model"]["summary"]
    claim_traceability = data["claim_traceability"]["summary"]
    semantic = data["semantic_referent"]["summary"]
    source_ladder = data["source_ladder"]["summary"]
    authority_path = data["authority_path"]["summary"]

    public_fit_count = sum(
        1 for row in public_source_rows if str(row["fit_status"]).startswith("fits_3090_known")
    )
    public_training_fit_count = sum(
        1
        for row in public_source_rows
        if row["fit_status"] in {"fits_3090_known_qlora", "probable_q4_fit_verify_asset"}
    )

    return {
        "candidate_count": bakeoff["candidate_count"]
        + len(
            {
                row["model"]
                for row in public_source_rows
                if row["model"]
                not in {candidate["model"] for candidate in data["local_bakeoff"]["candidate_rows"]}
            }
        ),
        "current_bakeoff_candidate_count": bakeoff["candidate_count"],
        "public_source_candidate_count": len(public_source_rows),
        "public_3090_known_fit_count": public_fit_count,
        "public_3090_training_or_probable_fit_count": public_training_fit_count,
        "exact_local_asset_count": bakeoff["exact_local_asset_count"],
        "missing_local_asset_count": bakeoff["missing_local_asset_count"],
        "q4_fit_model_count": bakeoff["q4_fit_model_count"],
        "qlora_possible_model_count": bakeoff["qlora_possible_model_count"],
        "planned_model_task_count": contextual["planned_model_task_count"],
        "measured_contextual_attempt_count": contextual["attempt_count"],
        "valid_model_task_coverage_pct": contextual["valid_model_task_coverage_pct"],
        "clean_source_anchored_pct": contextual["clean_source_anchored_pct"],
        "source_anchor_issue_count": contextual["source_anchor_issue_count"],
        "expanded_expected_result_count": model_gap["expected_result_count"],
        "expanded_missing_expected_result_count": model_gap["missing_expected_result_count"],
        "expanded_schema_valid_expected_pct": model_gap["schema_valid_expected_pct"],
        "claim_text_allowed_now": claim_traceability["translation_text_allowed_now_count"],
        "claim_text_allowed_after_review": claim_traceability[
            "translation_text_allowed_after_review_count"
        ],
        "required_claim_row_count": claim_traceability["required_claim_row_count"],
        "notes_or_packets_only_claim_count": claim_traceability[
            "notes_or_packets_only_claim_count"
        ],
        "source_approval_count": source_ladder["source_approval_count"],
        "completed_review_row_count": source_ladder["completed_review_row_count"],
        "total_review_row_count": source_ladder["total_review_row_count"],
        "review_completion_pct": source_ladder["review_completion_pct"],
        "semantic_role_coverage_pct": semantic["semantic_role_coverage_pct"],
        "referent_coverage_pct": semantic["referent_coverage_pct"],
        "missing_semantic_role_token_count": semantic["missing_semantic_role_token_count"],
        "missing_referent_token_count": semantic["missing_referent_token_count"],
        "projected_model_human_review_rows": authority_path["projected_model_human_review_rows"],
        "projected_cross_exam_rows": authority_path["projected_cross_exam_rows"],
        "recommended_baseline": bakeoff["best_current_bakeoff_baseline"],
        "recommended_trainable_base": bakeoff["best_trainable_base_if_asset_added"],
        "recommended_hebrew_specialist": bakeoff["best_hebrew_specialist_candidate"],
        "recommended_frontier_intake": "Qwen/Qwen3-30B-A3B-Instruct-2507",
        "certification_status": "blocked_not_authority",
        "authority_verdict": (
            "Local model training can be planned on 3090-class hardware, but no model can "
            "be certified as authoritative until source approval, semantic/referent "
            "enrichment, benchmark coverage, source-anchor integrity, human review, and "
            "release gates pass."
        ),
    }


def build_candidate_rows(
    data: dict[str, dict[str, Any]],
    public_source_rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
    fact_by_model = {row["model"]: row for row in public_source_rows}
    bakeoff_rows = data["local_bakeoff"]["candidate_rows"]
    bakeoff_by_model = {row["model"]: row for row in bakeoff_rows}
    all_models = list(bakeoff_by_model)
    all_models.extend(
        row["model"] for row in public_source_rows if row["model"] not in bakeoff_by_model
    )

    rows: list[dict[str, Any]] = []
    for model in all_models:
        bakeoff = bakeoff_by_model.get(model, {})
        fact = fact_by_model.get(model, {})
        fit = str(fact.get("fit_status", "local_bakeoff_only_verify_public_specs"))
        fit_score = float(fact.get("fit_score_pct", 50.0))
        measured_count = int(bakeoff.get("measured_result_count") or 0)
        contextual_attempts = int(bakeoff.get("contextual_attempt_count") or 0)
        local_asset_status = str(bakeoff.get("local_asset_status", "not_in_current_bakeoff"))
        schema_score = row_float(bakeoff, "effective_schema_valid_pct")
        source_anchor_score = row_float(bakeoff, "contextual_clean_source_anchored_pct")
        hebrew_score = row_float(bakeoff, "hebrew_score_pct") or (
            80.0 if "Dicta" in model else 50.0
        )
        public_prior = row_float(bakeoff, "public_prior_pct") or fit_score
        evidence_depth = min(100.0, contextual_attempts * 8.0)
        readiness = round(
            public_prior * 0.18
            + fit_score * 0.14
            + schema_score * 0.16
            + source_anchor_score * 0.16
            + hebrew_score * 0.16
            + evidence_depth * 0.10
            + row_float(bakeoff, "fine_tune_score_pct") * 0.10,
            2,
        )
        if summary["claim_text_allowed_now"] == 0:
            certification = "blocked_no_translation_text_authority"
        elif measured_count == 0:
            certification = "candidate_intake_required"
        else:
            certification = "measured_but_not_release_authorized"

        if model == summary["recommended_baseline"]:
            training_action = "Keep as measured local baseline; repair weak layers before scaling."
        elif model == summary["recommended_trainable_base"]:
            training_action = (
                "Acquire exact asset, run smoke matrix, then consider LoRA only after source gates."
            )
        elif model == summary["recommended_hebrew_specialist"]:
            training_action = (
                "Acquire exact local asset and run Hebrew specialist smoke/cross-exam probes."
            )
        elif model == summary["recommended_frontier_intake"]:
            training_action = (
                "Add as frontier MoE intake candidate; verify disk/RAM conversion "
                "path and 3090 QLoRA."
            )
        elif "nllb" in model.lower() or "madlad" in model.lower():
            training_action = "Use as MT comparator only; do not treat as conversational authority."
        else:
            training_action = str(
                bakeoff.get("current_action")
                or "Acquire exact local asset and run schema/source-anchor benchmark intake."
            )

        rows.append(
            {
                "rank": len(rows) + 1,
                "model": model,
                "short_name": bakeoff.get("short_name") or fact.get("short_name", model),
                "role": bakeoff.get("role") or fact.get("public_role", "frontier_candidate"),
                "local_asset_status": local_asset_status,
                "fit_status": fit,
                "fit_score_pct": fit_score,
                "known_q4_memory_gb": fact.get("known_q4_memory_gb", ""),
                "known_qlora_vram_gb": fact.get("known_qlora_vram_gb", ""),
                "context_tokens": fact.get("context_tokens", ""),
                "measured_result_count": measured_count,
                "contextual_attempt_count": contextual_attempts,
                "effective_schema_valid_pct": schema_score,
                "clean_source_anchored_pct": source_anchor_score,
                "hebrew_score_pct": hebrew_score,
                "training_readiness_score_pct": readiness,
                "certification_status": certification,
                "authority_boundary": authority_status(summary),
                "training_action": training_action,
                "public_fact": fact.get("public_fact", bakeoff.get("public_fact", "")),
                "source_urls": fact.get("source_urls", bakeoff.get("source_urls", "")),
            }
        )

    return sorted(
        rows,
        key=lambda row: (
            0 if row["model"] == summary["recommended_baseline"] else 1,
            -float(row["training_readiness_score_pct"]),
            row["rank"],
        ),
    )


def build_gate_rows(
    data: dict[str, dict[str, Any]], summary: dict[str, Any]
) -> list[dict[str, Any]]:
    bakeoff_gates = {row["gate"]: row for row in data["local_bakeoff"]["gate_rows"]}
    rows = [
        {
            "gate": "source_approval",
            "status": "blocked",
            "score_pct": 0.0,
            "evidence": (
                f"{fmt_int(summary['source_approval_count'])} approved source rows; "
                f"{fmt_int(summary['total_review_row_count'])} review rows remain unsigned."
            ),
            "next_action": (
                "Approve source families and license/provenance boundaries before "
                "training data use."
            ),
            "blocks_certification": True,
        },
        {
            "gate": "claim_text_authority",
            "status": "blocked",
            "score_pct": 0.0,
            "evidence": (
                f"{fmt_int(summary['claim_text_allowed_now'])} required claim rows are "
                "currently allowed in translation text; "
                f"{fmt_int(summary['claim_text_allowed_after_review'])} could become "
                "text-eligible after review."
            ),
            "next_action": (
                "Keep model outputs draft-only until claim-family gates and review signoff pass."
            ),
            "blocks_certification": True,
        },
        {
            "gate": "semantic_referent_enrichment",
            "status": "blocked",
            "score_pct": min(
                summary["semantic_role_coverage_pct"], summary["referent_coverage_pct"]
            ),
            "evidence": (
                f"Semantic-role coverage {summary['semantic_role_coverage_pct']:.2f}%; "
                f"referent coverage {summary['referent_coverage_pct']:.2f}%; "
                f"{fmt_int(summary['missing_semantic_role_token_count'])} tokens missing "
                "semantic role."
            ),
            "next_action": (
                "Enrich semantic roles, referents, syntax, and discourse anchors before training."
            ),
            "blocks_certification": True,
        },
        {
            "gate": "benchmark_coverage",
            "status": "smoke_only",
            "score_pct": summary["valid_model_task_coverage_pct"],
            "evidence": (
                f"{fmt_int(summary['measured_contextual_attempt_count'])} measured contextual "
                f"attempts against {fmt_int(summary['planned_model_task_count'])} planned "
                "model-task rows."
            ),
            "next_action": "Run the expanded benchmark across selected local candidates.",
            "blocks_certification": True,
        },
        {
            "gate": "source_anchor_integrity",
            "status": bakeoff_gates.get("source_anchor_integrity", {}).get("status", "blocked"),
            "score_pct": summary["clean_source_anchored_pct"],
            "evidence": (
                f"{summary['clean_source_anchored_pct']:.2f}% clean source-anchored attempts; "
                f"{fmt_int(summary['source_anchor_issue_count'])} source-anchor issues."
            ),
            "next_action": (
                "Block certification until token references and source claims stay aligned."
            ),
            "blocks_certification": True,
        },
        {
            "gate": "layer_differentiation",
            "status": bakeoff_gates.get("layer_differentiation", {}).get("status", "blocked"),
            "score_pct": bakeoff_gates.get("layer_differentiation", {}).get("score_pct", 0.0),
            "evidence": bakeoff_gates.get("layer_differentiation", {}).get(
                "evidence", "Layer differentiation evidence not found."
            ),
            "next_action": (
                "Repair gloss/literal/phrase/concept/lyric layer separation before scaling."
            ),
            "blocks_certification": True,
        },
        {
            "gate": "3090_training_fit",
            "status": "partial",
            "score_pct": pct(
                summary["public_3090_known_fit_count"] + summary["qlora_possible_model_count"],
                summary["public_source_candidate_count"]
                + summary["current_bakeoff_candidate_count"],
            ),
            "evidence": (
                f"{fmt_int(summary['public_3090_known_fit_count'])} public candidates have "
                "documented 3090-class fit facts; "
                f"{fmt_int(summary['qlora_possible_model_count'])} current bakeoff candidates "
                "are QLoRA possible."
            ),
            "next_action": "Keep inference quantized and restrict training to adapter experiments.",
            "blocks_certification": False,
        },
        {
            "gate": "human_release_authority",
            "status": "blocked",
            "score_pct": summary["review_completion_pct"],
            "evidence": (
                f"{fmt_int(summary['completed_review_row_count'])} of "
                f"{fmt_int(summary['total_review_row_count'])} review rows complete; "
                f"{fmt_int(summary['projected_model_human_review_rows'])} projected "
                "model-human review rows."
            ),
            "next_action": "Complete reviewer signoff and release authority before certification.",
            "blocks_certification": True,
        },
    ]
    return rows


def build_phase_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "phase": "1",
            "label": "Govern source and claim authority",
            "status": "blocked",
            "readiness_pct": 0.0,
            "evidence": (
                f"{fmt_int(summary['source_approval_count'])} source approvals; "
                f"{fmt_int(summary['claim_text_allowed_now'])} claim rows text-authorized."
            ),
            "exit_criteria": (
                "Approved source families and claim-family text authority records exist."
            ),
            "next_action": "Record source approvals and keep all model outputs draft-only.",
        },
        {
            "phase": "2",
            "label": "Enrich Hebrew semantics and broader-canon context",
            "status": "blocked",
            "readiness_pct": min(
                summary["semantic_role_coverage_pct"], summary["referent_coverage_pct"]
            ),
            "evidence": (
                f"{fmt_int(summary['missing_semantic_role_token_count'])} tokens lack "
                "semantic roles; "
                f"{fmt_int(summary['missing_referent_token_count'])} tokens lack referents."
            ),
            "exit_criteria": (
                "Critical tokens have semantic role, referent, syntax, and review rows."
            ),
            "next_action": "Complete semantic/referent enrichment for high-pressure units.",
        },
        {
            "phase": "3",
            "label": "Complete benchmark evidence",
            "status": "smoke_only",
            "readiness_pct": summary["valid_model_task_coverage_pct"],
            "evidence": (
                f"{fmt_int(summary['measured_contextual_attempt_count'])} attempts cover "
                f"{summary['valid_model_task_coverage_pct']:.2f}% of planned rows."
            ),
            "exit_criteria": "All planned model-task rows have schema-valid scored outputs.",
            "next_action": "Run the benchmark matrix after prompt/layer repair.",
        },
        {
            "phase": "4",
            "label": "Acquire exact local assets",
            "status": "partial",
            "readiness_pct": pct(
                summary["exact_local_asset_count"], summary["current_bakeoff_candidate_count"]
            ),
            "evidence": (
                f"{fmt_int(summary['exact_local_asset_count'])} exact local assets; "
                f"{fmt_int(summary['missing_local_asset_count'])} current candidates missing."
            ),
            "exit_criteria": (
                "Exact quantized assets exist for baseline, trainable, Hebrew, and MT lanes."
            ),
            "next_action": (
                "Acquire exact Gemma, Dicta, Qwen, TranslateGemma, and MT comparator assets."
            ),
        },
        {
            "phase": "5",
            "label": "Repair schema, source anchoring, and layer behavior",
            "status": "blocked",
            "readiness_pct": summary["clean_source_anchored_pct"],
            "evidence": (
                f"{summary['clean_source_anchored_pct']:.2f}% clean source anchoring; "
                f"{fmt_int(summary['source_anchor_issue_count'])} anchor issues."
            ),
            "exit_criteria": "Models pass schema, source-anchor, and layer-differentiation gates.",
            "next_action": "Rerun repaired prompts before any adapter training.",
        },
        {
            "phase": "6",
            "label": "Run adapter-only training pilots",
            "status": "blocked_preconditions",
            "readiness_pct": 0.0,
            "evidence": (
                f"{fmt_int(summary['qlora_possible_model_count'])} current candidates are "
                "QLoRA possible, but source/review gates are blocked."
            ),
            "exit_criteria": (
                "Adapter dataset is source-approved, review-routed, and benchmark-held-out."
            ),
            "next_action": "Plan LoRA/QLoRA only; do not full fine-tune or merge adapters yet.",
        },
        {
            "phase": "7",
            "label": "Cross-exam model outputs",
            "status": "blocked",
            "readiness_pct": 0.0,
            "evidence": (
                f"{fmt_int(summary['projected_cross_exam_rows'])} projected cross-exam rows; "
                f"{fmt_int(summary['projected_model_human_review_rows'])} projected "
                "model-human review rows."
            ),
            "exit_criteria": (
                "Codex, Claude, local challengers, and human reviewers converge on scored rows."
            ),
            "next_action": "Generate cross-exam packets after benchmark coverage is complete.",
        },
        {
            "phase": "8",
            "label": "Certify release use",
            "status": "blocked",
            "readiness_pct": 0.0,
            "evidence": (
                "Release authority is blocked and no model output can authorize canonical wording."
            ),
            "exit_criteria": (
                "Release reviewer signoff, audit records, and canonical approval records exist."
            ),
            "next_action": "Keep model claims advisory until release gates pass.",
        },
    ]


def build_visual_data(
    candidate_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    phase_rows: list[dict[str, Any]],
    public_source_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "candidate_readiness_rows": [
            {"label": row["short_name"], "value": row["training_readiness_score_pct"]}
            for row in candidate_rows[:12]
        ],
        "gate_score_rows": [{"label": row["gate"], "value": row["score_pct"]} for row in gate_rows],
        "phase_readiness_rows": [
            {"label": row["label"], "value": row["readiness_pct"]} for row in phase_rows
        ],
        "public_fit_rows": [
            {"label": row["short_name"], "value": row["fit_score_pct"]}
            for row in public_source_rows
        ],
        "certification_status_rows": [
            {"label": status, "value": count}
            for status, count in Counter(
                row["certification_status"] for row in candidate_rows
            ).items()
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    public_source_rows = build_public_source_rows()
    summary = build_summary(data, public_source_rows)
    candidate_rows = build_candidate_rows(data, public_source_rows, summary)
    gate_rows = build_gate_rows(data, summary)
    phase_rows = build_phase_rows(summary)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "model training certification roadmap generated; not model approval",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "target_gpu_profile": TARGET_GPU_PROFILE,
        "authority_policy": (
            "This roadmap ranks model-training and certification work only. It does not "
            "approve a model, authorize training data, approve source use, replace human "
            "review, or authorize canonical Hebrew-to-English translation wording."
        ),
        "summary": summary,
        "candidate_rows": candidate_rows,
        "gate_rows": gate_rows,
        "phase_rows": phase_rows,
        "public_source_rows": public_source_rows,
        "visual_data": build_visual_data(
            candidate_rows,
            gate_rows,
            phase_rows,
            public_source_rows,
        ),
    }


def table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    head = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def metric_cards(cards: list[tuple[str, Any, str]]) -> str:
    return (
        '<div class="metrics">'
        + "\n".join(
            '<div class="metric">'
            f"<strong>{escape(str(value))}</strong>"
            f"<span>{escape(label)}</span>"
            f"<small>{escape(detail)}</small>"
            "</div>"
            for label, value, detail in cards
        )
        + "</div>"
    )


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str = "label",
    value_key: str = "value",
    width: int = 900,
    row_height: int = 30,
    color: str = "#2f6f73",
    limit: int = 12,
) -> str:
    chart_rows = rows[:limit]
    if not chart_rows:
        return ""
    values = [float(row.get(value_key) or 0.0) for row in chart_rows]
    maximum = max(values) or 1.0
    label_width = 280
    bar_width = width - label_width - 90
    height = row_height * len(chart_rows) + 24
    parts = [
        f'<svg role="img" aria-label="Roadmap chart" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg">'
    ]
    for index, row in enumerate(chart_rows):
        y = index * row_height + 20
        value = float(row.get(value_key) or 0.0)
        label = str(row.get(label_key, ""))
        bar = value / maximum * bar_width
        parts.append(f'<text x="0" y="{y + 14}" font-size="12">{escape(label)}</text>')
        parts.append(
            f'<rect x="{label_width}" y="{y}" width="{bar:.2f}" height="18" '
            f'rx="3" fill="{color}" />'
        )
        parts.append(
            f'<text x="{label_width + bar + 8:.2f}" y="{y + 14}" font-size="12">{value:.2f}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    candidates = [
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
        for row in report["candidate_rows"]
    ]
    gates = [
        [
            row["gate"],
            row["status"],
            f"{float(row['score_pct']):.2f}%",
            "yes" if row["blocks_certification"] else "no",
            row["evidence"],
            row["next_action"],
        ]
        for row in report["gate_rows"]
    ]
    phases = [
        [
            row["phase"],
            row["label"],
            row["status"],
            f"{float(row['readiness_pct']):.2f}%",
            row["evidence"],
            row["exit_criteria"],
            row["next_action"],
        ]
        for row in report["phase_rows"]
    ]
    sources = [
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
        for row in report["public_source_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Model Training Certification Roadmap</title>
  <style>
    :root {{
      --ink: #263238;
      --muted: #667073;
      --line: #d7dedf;
      --panel: #f7faf9;
      --accent: #2f6f73;
      --warn: #8a6426;
      --bad: #9b3d3d;
    }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #ffffff;
    }}
    header {{
      padding: 28px 36px;
      background: #edf4f2;
      border-bottom: 1px solid var(--line);
    }}
    main {{ padding: 28px 36px 56px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin-top: 28px; }}
    .subtitle {{ color: var(--muted); max-width: 1050px; line-height: 1.45; }}
    .warning {{
      border-left: 5px solid var(--bad);
      background: #fbf1ef;
      padding: 12px 14px;
      margin: 14px 0;
      line-height: 1.45;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px;
      margin: 16px 0;
    }}
    .metric {{
      border: 1px solid var(--line);
      background: var(--panel);
      padding: 12px;
      border-radius: 6px;
    }}
    .metric strong {{ display: block; font-size: 1.55rem; }}
    .metric span {{ display: block; font-weight: 700; margin-top: 4px; }}
    .metric small {{ display: block; color: var(--muted); margin-top: 4px; }}
    .chart {{
      border: 1px solid var(--line);
      background: #fff;
      padding: 10px;
      overflow-x: auto;
      margin: 12px 0;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 12px 0 18px;
      font-size: 0.9rem;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 7px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #edf4f2; }}
  </style>
</head>
<body>
<header>
  <h1>Model Training Certification Roadmap</h1>
  <p class="subtitle">
    A 3090-class local-model plan for Hebrew-to-English Psalms work, grounded in
    current benchmark evidence, claim-family authority, source approval state,
    semantic/referent gaps, and human-review gates.
  </p>
</header>
<main>
  <section>
    <h2>Authority State</h2>
    <div class="warning">
      {escape(report["authority_policy"])}
    </div>
    {
        metric_cards(
            [
                (
                    "Certification",
                    summary["certification_status"],
                    "Current model authority state.",
                ),
                (
                    "Text-authorized claims",
                    summary["claim_text_allowed_now"],
                    "Required claim rows currently allowed in translation text.",
                ),
                (
                    "Context coverage",
                    f"{summary['valid_model_task_coverage_pct']:.2f}%",
                    "Valid measured model-task coverage.",
                ),
                (
                    "Clean source anchoring",
                    f"{summary['clean_source_anchored_pct']:.2f}%",
                    "Clean contextual attempts.",
                ),
                ("Source approvals", summary["source_approval_count"], "Approved source rows."),
                (
                    "Review completion",
                    f"{summary['review_completion_pct']:.2f}%",
                    "Completed review rows.",
                ),
            ]
        )
    }
  </section>

  <section>
    <h2>Candidate Readiness</h2>
    <div class="chart">{
        svg_horizontal_bars(visual["candidate_readiness_rows"], color="#2f6f73")
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
            candidates,
        )
    }
  </section>

  <section>
    <h2>Certification Gates</h2>
    <div class="chart">{svg_horizontal_bars(visual["gate_score_rows"], color="#9b3d3d")}</div>
    {table(["Gate", "Status", "Score", "Blocks", "Evidence", "Next Action"], gates)}
  </section>

  <section>
    <h2>Execution Phases</h2>
    <div class="chart">{svg_horizontal_bars(visual["phase_readiness_rows"], color="#8a6426")}</div>
    {table(["Phase", "Label", "Status", "Readiness", "Evidence", "Exit", "Next Action"], phases)}
  </section>

  <section>
    <h2>Public Model Facts</h2>
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
            sources,
        )
    }
  </section>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate model training certification roadmap.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--candidate-csv-output", type=Path, default=DEFAULT_CANDIDATE_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--phase-csv-output", type=Path, default=DEFAULT_PHASE_CSV_OUTPUT)
    parser.add_argument("--source-csv-output", type=Path, default=DEFAULT_SOURCE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.candidate_csv_output, report["candidate_rows"])
    write_csv(args.gate_csv_output, report["gate_rows"])
    write_csv(args.phase_csv_output, report["phase_rows"])
    write_csv(args.source_csv_output, report["public_source_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.candidate_csv_output}")
    print(f"Wrote {args.gate_csv_output}")
    print(f"Wrote {args.phase_csv_output}")
    print(f"Wrote {args.source_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
