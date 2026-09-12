from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"
DOC_ROOT = ROOT / "docs" / "research"

MODEL_DATA_PATH = DOC_ROOT / "local_translation_model_data.json"
ASSET_INVENTORY_PATH = REPORT_ROOT / "local_model_asset_inventory.json"
RUNTIME_READINESS_PATH = REPORT_ROOT / "local_runtime_readiness.json"
EXPANDED_AUDIT_PATH = REPORT_ROOT / "contextual_expanded_benchmark_result_audit.json"
LAYER_EXPERIMENT_PATH = REPORT_ROOT / "layer_remediation_experiment_report.json"
AUTHORITY_PATH = REPORT_ROOT / "scholarly_authority_readiness.json"
GEMMA_REPAIR_PATH = REPORT_ROOT / "gemma_schema_repair_report.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "local_model_selection_roadmap.json"
DEFAULT_CANDIDATE_CSV_OUTPUT = REPORT_ROOT / "local_model_selection_candidates.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "local_model_selection_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "local_model_selection_roadmap.html"

PUBLIC_FACTS: dict[str, dict[str, Any]] = {
    "google/gemma-4-12B-it": {
        "public_fact": (
            "Gemma 4 family: open weights, native system prompts, thinking modes, "
            "multilingual support, and 128K context for small models."
        ),
        "hardware_note": (
            "Best first fine-tuning target if the 12B asset is added; current "
            "local asset inventory only has a near-family Gemma 4 26B asset."
        ),
        "source_ids": ["gemma4_overview", "gemma4_model_card"],
    },
    "google/translategemma-12b-it": {
        "public_fact": (
            "Translation-specialized Gemma-family comparator; useful for bilingual "
            "fidelity checks, but not sufficient by itself for biblical context."
        ),
        "hardware_note": "No local asset in the current inventory.",
        "source_ids": ["translategemma_blog", "translategemma_12b"],
    },
    "google/gemma-4-26B-A4B-it": {
        "public_fact": (
            "Gemma 4 26B-A4B is an MoE model with about 25.2B total parameters, "
            "about 3.8B active parameters, and 256K context in the model card."
        ),
        "hardware_note": (
            "A ready Windows Ollama GGUF asset is present as gemma4:26b, but "
            "baseline schema-mode evidence failed; chat/json/think=false repairs "
            "schema output while source-anchor and layer gates remain blocked."
        ),
        "source_ids": ["gemma4_overview", "gemma4_model_card"],
    },
    "dicta-il/DictaLM-3.0-Nemotron-12B-Instruct": {
        "public_fact": (
            "DictaLM 3.0 12B Instruct is trained on Hebrew and English text, "
            "supports tool calling, and is the lowest-friction Hebrew-specialist challenger."
        ),
        "hardware_note": (
            "No local asset is present. The model card uses the NVIDIA Open Model License, "
            "so governance review is required before production use."
        ),
        "source_ids": ["dictalm3_12b_instruct"],
    },
    "dicta-il/DictaLM-3.0-24B-Thinking": {
        "public_fact": (
            "DictaLM 3.0 24B Thinking is the flagship Hebrew/English reasoning model "
            "and is listed under Apache 2.0 on the Hugging Face model card."
        ),
        "hardware_note": (
            "No local asset is present. A GGUF exists upstream, so it should be "
            "downloaded only after the smoke-test protocol is fixed."
        ),
        "source_ids": ["dictalm3_24b_thinking", "dictalm3_24b_gguf"],
    },
    "Qwen/Qwen3-14B": {
        "public_fact": (
            "Qwen3 is a multilingual reasoning family; this slot is a moderate-size "
            "multilingual challenger rather than a Hebrew specialist."
        ),
        "hardware_note": "Only near-family local Qwen assets are present.",
        "source_ids": ["qwen3_14b", "qwen3_report"],
    },
    "mistralai/Mistral-Small-3.2-24B-Instruct-2506": {
        "public_fact": (
            "Mistral Small 3.2 has 128K context and structured-output support; "
            "Mistral now lists it as replaced by Small 4."
        ),
        "hardware_note": (
            "Ready Windows Ollama GGUF asset exists and has the best current "
            "measured schema-valid evidence, but layer differentiation remains blocked."
        ),
        "source_ids": ["mistral_small_32", "mistral_small_4"],
    },
    "meta-llama/Llama-3.1-8B-Instruct": {
        "public_fact": (
            "Small local baseline only. It is useful for runner regression tests, "
            "but it is not a Hebrew-specialist authority candidate."
        ),
        "hardware_note": "No recommended local asset is tracked in the current roadmap.",
        "source_ids": ["llama31_8b"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_json(path)


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


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def model_short_name(model: str) -> str:
    replacements = {
        "google/gemma-4-12B-it": "Gemma 4 12B",
        "google/translategemma-12b-it": "TranslateGemma 12B",
        "google/gemma-4-26B-A4B-it": "Gemma 4 26B-A4B",
        "dicta-il/DictaLM-3.0-Nemotron-12B-Instruct": "DictaLM 12B",
        "dicta-il/DictaLM-3.0-24B-Thinking": "DictaLM 24B",
        "Qwen/Qwen3-14B": "Qwen3 14B",
        "mistralai/Mistral-Small-3.2-24B-Instruct-2506": "Mistral Small 3.2",
    }
    return replacements.get(model, model.split("/")[-1])


def asset_score(status: str) -> float:
    return {
        "local_asset_present": 100.0,
        "near_family_asset_present": 45.0,
        "missing_local_asset": 0.0,
    }.get(status, 0.0)


def measured_rows_by_model(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "submitted_result_count": 0,
            "schema_valid_result_count": 0,
            "source_anchor_issue_count": 0,
            "error_count": 0,
            "elapsed_ms_total": 0.0,
            "elapsed_ms_count": 0,
            "tasks": [],
            "errors": [],
        }
    )
    for row in audit.get("scored_results", []):
        model = str(row.get("model_profile_id") or "")
        if not model:
            continue
        item = grouped[model]
        item["submitted_result_count"] += 1
        if row.get("schema_valid"):
            item["schema_valid_result_count"] += 1
        item["source_anchor_issue_count"] += int(row.get("source_anchor_issue_count") or 0)
        item["error_count"] += int(row.get("error_count") or 0)
        runtime = row.get("runtime") or {}
        elapsed = runtime.get("elapsed_ms")
        if isinstance(elapsed, int | float):
            item["elapsed_ms_total"] += float(elapsed)
            item["elapsed_ms_count"] += 1
        if len(item["tasks"]) < 8:
            item["tasks"].append(row.get("task_id"))
        if row.get("errors") and len(item["errors"]) < 8:
            item["errors"].extend(str(error) for error in row["errors"])
    results: dict[str, dict[str, Any]] = {}
    for model, item in grouped.items():
        submitted = int(item["submitted_result_count"])
        elapsed_count = int(item["elapsed_ms_count"])
        results[model] = {
            "submitted_result_count": submitted,
            "schema_valid_result_count": int(item["schema_valid_result_count"]),
            "schema_valid_pct": pct(item["schema_valid_result_count"], submitted),
            "source_anchor_issue_count": int(item["source_anchor_issue_count"]),
            "error_count": int(item["error_count"]),
            "mean_elapsed_ms": (
                round(float(item["elapsed_ms_total"]) / elapsed_count, 2) if elapsed_count else 0.0
            ),
            "sample_tasks": item["tasks"],
            "sample_errors": sorted(set(item["errors"]))[:8],
        }
    return results


def action_for_candidate(
    *,
    model: str,
    asset_status: str,
    measured: dict[str, Any] | None,
    gemma_repair: dict[str, Any] | None,
    is_hebrew_specialist: bool,
) -> str:
    if model == "google/gemma-4-26B-A4B-it" and gemma_repair:
        if float(gemma_repair.get("schema_valid_pct") or 0.0) >= 95.0:
            return (
                "Keep in prompt repair track: chat/json/think=false repairs schema, "
                "but source-anchor and weak-layer gates still block quality bakeoff."
            )
    if measured and float(measured["schema_valid_pct"]) < 80:
        return (
            "Prompt/runtime repair before broader bakeoff; current measured rows fail "
            "schema-mode output."
        )
    if measured and float(measured["schema_valid_pct"]) >= 95 and model.startswith("mistralai/"):
        return (
            "Keep as local baseline; do not scale authority claims until gloss/literal "
            "layer differentiation gate passes."
        )
    if asset_status == "local_asset_present":
        return "Run two-layer smoke test on priority stress cases, then score layer consistency."
    if is_hebrew_specialist:
        return "Acquire local quantized asset and run Hebrew-specialist smoke test."
    if asset_status == "near_family_asset_present":
        return "Optional comparator after exact asset is added; near-family asset is not proof."
    return "Defer until local asset and license review are complete."


def build_candidate_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    model_data = data["model_data"]
    asset_inventory = data["asset_inventory"]
    measured_by_model = measured_rows_by_model(data["expanded_audit"])
    repair_summary = data.get("gemma_repair", {}).get("summary", {})
    repair_attempts = {
        row["attempt_id"]: row for row in data.get("gemma_repair", {}).get("attempt_rows", [])
    }
    gemma_best_repair = repair_attempts.get(str(repair_summary.get("best_schema_attempt_id") or ""))
    coverage_by_model = {
        row["model"]: row for row in asset_inventory.get("recommended_coverage", [])
    }
    ready_profiles = {
        row["recommended_model"]: row for row in asset_inventory.get("profile_suggestions", [])
    }
    candidate_rows = []
    for candidate in model_data["candidate_scores"]:
        model = str(candidate["model"])
        if model not in PUBLIC_FACTS and model != "meta-llama/Llama-3.1-8B-Instruct":
            continue
        coverage = coverage_by_model.get(model, {})
        measured = measured_by_model.get(model)
        public_prior_pct = round(float(candidate["mean"]) / 5.0 * 100, 2)
        local_asset_pct = asset_score(str(coverage.get("status") or "missing_local_asset"))
        measured_pct = float(measured["schema_valid_pct"]) if measured else 0.0
        repair_schema_pct = (
            float(gemma_best_repair.get("schema_valid_pct") or 0.0)
            if model == "google/gemma-4-26B-A4B-it" and gemma_best_repair
            else 0.0
        )
        effective_schema_pct = max(measured_pct, repair_schema_pct)
        evidence_depth_pct = pct(
            int(measured["submitted_result_count"]) if measured else 0,
            int(data["expanded_audit"]["summary"]["expected_result_count"]),
        )
        composite = round(
            (public_prior_pct * 0.35)
            + (local_asset_pct * 0.25)
            + (effective_schema_pct * 0.25)
            + (evidence_depth_pct * 0.15),
            2,
        )
        is_hebrew_specialist = model.startswith("dicta-il/")
        action = action_for_candidate(
            model=model,
            asset_status=str(coverage.get("status") or "missing_local_asset"),
            measured=measured,
            gemma_repair=gemma_best_repair if model == "google/gemma-4-26B-A4B-it" else None,
            is_hebrew_specialist=is_hebrew_specialist,
        )
        ready_profile = ready_profiles.get(model, {})
        facts = PUBLIC_FACTS.get(model, {})
        candidate_rows.append(
            {
                "model": model,
                "short_name": model_short_name(model),
                "family": candidate.get("family", ""),
                "role": candidate.get("role", ""),
                "public_prior_mean_0_5": round(float(candidate["mean"]), 2),
                "public_prior_pct": public_prior_pct,
                "asset_status": coverage.get("status", "not_recommended"),
                "best_local_asset": coverage.get("best_asset") or "",
                "local_asset_score_pct": local_asset_pct,
                "ready_profile_id": ready_profile.get("profile_id", ""),
                "measured_result_count": int(measured["submitted_result_count"]) if measured else 0,
                "measured_schema_valid_pct": measured_pct,
                "effective_schema_valid_pct": effective_schema_pct,
                "schema_repair_result_count": (
                    int(gemma_best_repair.get("submitted_result_count") or 0)
                    if model == "google/gemma-4-26B-A4B-it" and gemma_best_repair
                    else 0
                ),
                "schema_repair_schema_valid_pct": repair_schema_pct,
                "schema_repair_source_anchor_issue_count": (
                    int(gemma_best_repair.get("source_anchor_issue_count") or 0)
                    if model == "google/gemma-4-26B-A4B-it" and gemma_best_repair
                    else 0
                ),
                "schema_repair_failed_gates": (
                    repair_summary.get("failed_gates", [])
                    if model == "google/gemma-4-26B-A4B-it"
                    else []
                ),
                "mean_elapsed_ms": float(measured["mean_elapsed_ms"]) if measured else 0.0,
                "source_anchor_issue_count": (
                    int(measured["source_anchor_issue_count"]) if measured else 0
                ),
                "evidence_depth_pct": evidence_depth_pct,
                "selection_score_pct": composite,
                "current_action": action,
                "public_fact": facts.get("public_fact", ""),
                "hardware_note": facts.get("hardware_note", ""),
                "source_ids": facts.get("source_ids", []),
                "sample_errors": measured.get("sample_errors", []) if measured else [],
            }
        )
    return sorted(
        candidate_rows,
        key=lambda row: (
            row["asset_status"] != "local_asset_present",
            -float(row["selection_score_pct"]),
            -float(row["public_prior_pct"]),
        ),
    )


def build_gate_rows(
    data: dict[str, dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    runtime = data["runtime_readiness"]["summary"]
    assets = data["asset_inventory"]["summary"]
    audit = data["expanded_audit"]["summary"]
    layer = data["layer_experiment"]["summary"]
    authority = data["authority"]["summary"]
    repair_summary = data.get("gemma_repair", {}).get("summary", {})
    ready_local_candidates = sum(
        1 for row in candidate_rows if row["asset_status"] == "local_asset_present"
    )
    gemma_row = next(
        (row for row in candidate_rows if row["model"] == "google/gemma-4-26B-A4B-it"),
        None,
    )
    mistral_row = next(
        (
            row
            for row in candidate_rows
            if row["model"] == "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
        ),
        None,
    )
    return [
        {
            "gate": "hardware_runtime",
            "status": "partial",
            "score_pct": runtime["readiness_gate_pass_pct"],
            "evidence": (
                f"{runtime['readiness_gate_pass_count']} of "
                f"{runtime['readiness_gate_count']} runtime gates pass; "
                f"{runtime['max_vram_gb']:.2f} GB max VRAM visible."
            ),
            "next_action": (
                "Install missing local training/serving packages only after "
                "smoke prompt gates pass."
            ),
        },
        {
            "gate": "local_asset_coverage",
            "status": "partial",
            "score_pct": assets["recommended_asset_coverage_pct"],
            "evidence": (
                f"{assets['recommended_models_with_local_assets']} of "
                f"{assets['recommended_model_count']} recommended models have exact "
                "or alias local assets."
            ),
            "next_action": (
                "Add DictaLM 12B/24B and a true Gemma 4 12B or TranslateGemma asset if used."
            ),
        },
        {
            "gate": "ready_bakeoff_profiles",
            "status": "started",
            "score_pct": pct(ready_local_candidates, max(1, len(candidate_rows))),
            "evidence": f"{ready_local_candidates} current candidates are immediately runnable.",
            "next_action": (
                "Run a small bakeoff only for runnable candidates after Gemma schema repair."
            ),
        },
        {
            "gate": "measured_schema_validity",
            "status": "partial",
            "score_pct": audit["schema_valid_pct"],
            "evidence": (
                f"{audit['schema_valid_result_count']} of "
                f"{audit['submitted_result_count']} submitted expanded rows are schema-valid."
            ),
            "next_action": "Treat schema validity as an admission gate, not a quality score.",
        },
        {
            "gate": "gemma4_26b_schema_probe",
            "status": "partial" if repair_summary else "fail",
            "score_pct": (
                float(repair_summary.get("best_schema_valid_pct") or 0.0)
                if repair_summary
                else float(gemma_row["measured_schema_valid_pct"])
                if gemma_row
                else 0.0
            ),
            "evidence": (
                "Gemma 4 26B baseline failed schema output, but chat/json/think=false "
                f"repair reached {float(repair_summary.get('best_schema_valid_pct') or 0.0):.2f}% "
                "schema validity while source-anchor and weak-layer gates remain blocked."
                if repair_summary
                else "Gemma 4 26B local rows are measured but currently fail schema output."
                if gemma_row
                else "No Gemma 4 26B local row found."
            ),
            "next_action": (
                "Do not compare Gemma quality until the repair report's source-anchor "
                "and layer gates pass."
                if repair_summary
                else "Repair prompt/template/max-token controls before comparing Gemma 4 quality."
            ),
        },
        {
            "gate": "mistral_layer_control",
            "status": "partial",
            "score_pct": 100.0 - pct(layer["failed_gate_count"], layer["gate_count"]),
            "evidence": (
                f"Mistral baseline has "
                f"{mistral_row['measured_schema_valid_pct'] if mistral_row else 0:.2f}% "
                "measured schema validity, but the layer experiment still fails "
                + ", ".join(layer["failed_gates"])
                + "."
            ),
            "next_action": (
                "Do not scale full retry queue until the layer gate is stricter and passed."
            ),
        },
        {
            "gate": "human_release_authority",
            "status": "blocked",
            "score_pct": 0.0,
            "evidence": (
                "Authority report still lists hard blockers: "
                + ", ".join(authority["hard_blockers"])
                + "."
            ),
            "next_action": (
                "Use local models for proposal and critique only until reviewer signoff exists."
            ),
        },
    ]


def build_phase_rows(candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "phase": "0",
            "label": "Prompt Repair",
            "entry_criteria": "At least one ready local Gemma 4 or Mistral profile.",
            "exit_criteria": (
                "Two stress units per model produce schema-valid gloss and literal rows."
            ),
            "models": "Gemma 4 26B-A4B, Mistral Small 3.2",
        },
        {
            "phase": "1",
            "label": "Hebrew Specialist Intake",
            "entry_criteria": "DictaLM asset downloaded and license reviewed.",
            "exit_criteria": (
                "DictaLM smoke rows pass schema, source-anchor, and no unsupported witness claims."
            ),
            "models": "DictaLM 12B, DictaLM 24B",
        },
        {
            "phase": "2",
            "label": "Layer Gate Bakeoff",
            "entry_criteria": "Schema pass rate >= 95% on smoke rows.",
            "exit_criteria": (
                "Zero exact gloss/literal duplicates and no conservative weak-layer failures."
            ),
            "models": ", ".join(row["short_name"] for row in candidate_rows[:4]),
        },
        {
            "phase": "3",
            "label": "Contextual Benchmark Expansion",
            "entry_criteria": "Layer gate passed on smoke set.",
            "exit_criteria": (
                "Expanded suite run completes with model hashes, timings, and audit artifacts."
            ),
            "models": "All surviving local candidates",
        },
        {
            "phase": "4",
            "label": "Human Adjudication",
            "entry_criteria": "Automated gates pass and candidate rows are review-routed.",
            "exit_criteria": "Qualified reviewer signoff, release authority, and audit trail.",
            "models": "No model is authoritative without this phase",
        },
    ]


def source_rows(model_data: dict[str, Any]) -> list[dict[str, Any]]:
    citation_by_id = {row["id"]: row["url"] for row in model_data.get("citations", [])}
    needed = sorted(
        {source_id for facts in PUBLIC_FACTS.values() for source_id in facts.get("source_ids", [])}
        | {
            "gemma4_overview",
            "mistral_small_32",
            "dictalm3_24b_thinking",
            "dictalm3_12b_instruct",
            "dictalm3_24b_gguf",
            "qwen3_report",
        }
    )
    fallback_urls = {
        "dictalm3_12b_instruct": "https://huggingface.co/dicta-il/DictaLM-3.0-Nemotron-12B-Instruct",
        "dictalm3_24b_gguf": "https://huggingface.co/dicta-il/DictaLM-3.0-24B-Thinking-GGUF",
    }
    rows = []
    for source_id in needed:
        rows.append(
            {
                "id": source_id,
                "url": citation_by_id.get(source_id) or fallback_urls.get(source_id, ""),
            }
        )
    return rows


def build_report() -> dict[str, Any]:
    data = {
        "model_data": load_json(MODEL_DATA_PATH),
        "asset_inventory": load_json(ASSET_INVENTORY_PATH),
        "runtime_readiness": load_json(RUNTIME_READINESS_PATH),
        "expanded_audit": load_json(EXPANDED_AUDIT_PATH),
        "layer_experiment": load_json(LAYER_EXPERIMENT_PATH),
        "authority": load_json(AUTHORITY_PATH),
        "gemma_repair": load_json_if_exists(GEMMA_REPAIR_PATH),
    }
    candidate_rows = build_candidate_rows(data)
    gate_rows = build_gate_rows(data, candidate_rows)
    phase_rows = build_phase_rows(candidate_rows)
    best_runnable = next(
        (row for row in candidate_rows if row["asset_status"] == "local_asset_present"),
        candidate_rows[0],
    )
    best_public_hebrew = max(
        (row for row in candidate_rows if row["model"].startswith("dicta-il/")),
        key=lambda row: float(row["public_prior_pct"]),
    )
    summary = {
        "candidate_count": len(candidate_rows),
        "ready_local_candidate_count": sum(
            1 for row in candidate_rows if row["asset_status"] == "local_asset_present"
        ),
        "near_family_candidate_count": sum(
            1 for row in candidate_rows if row["asset_status"] == "near_family_asset_present"
        ),
        "missing_local_candidate_count": sum(
            1 for row in candidate_rows if row["asset_status"] == "missing_local_asset"
        ),
        "other_candidate_count": sum(
            1
            for row in candidate_rows
            if row["asset_status"]
            not in {
                "local_asset_present",
                "near_family_asset_present",
                "missing_local_asset",
            }
        ),
        "best_runnable_candidate": best_runnable["model"],
        "best_runnable_action": best_runnable["current_action"],
        "best_public_hebrew_specialist": best_public_hebrew["model"],
        "expanded_submitted_rows": data["expanded_audit"]["summary"]["submitted_result_count"],
        "expanded_schema_valid_pct": data["expanded_audit"]["summary"]["schema_valid_pct"],
        "gemma4_26b_baseline_schema_valid_pct": next(
            (
                row["measured_schema_valid_pct"]
                for row in candidate_rows
                if row["model"] == "google/gemma-4-26B-A4B-it"
            ),
            0.0,
        ),
        "gemma4_26b_schema_valid_pct": next(
            (
                row["effective_schema_valid_pct"]
                for row in candidate_rows
                if row["model"] == "google/gemma-4-26B-A4B-it"
            ),
            0.0,
        ),
        "gemma4_26b_repair_schema_valid_pct": data["gemma_repair"]
        .get("summary", {})
        .get(
            "best_schema_valid_pct",
            0.0,
        ),
        "gemma4_26b_repair_source_anchor_issue_count": data["gemma_repair"]
        .get(
            "summary",
            {},
        )
        .get("best_source_anchor_issue_count", 0),
        "gemma4_26b_repair_failed_gates": data["gemma_repair"]
        .get("summary", {})
        .get(
            "failed_gates",
            [],
        ),
        "mistral_schema_valid_pct": next(
            (
                row["measured_schema_valid_pct"]
                for row in candidate_rows
                if row["model"] == "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
            ),
            0.0,
        ),
        "layer_experiment_status": data["layer_experiment"]["summary"]["experiment_status"],
        "failed_layer_gates": data["layer_experiment"]["summary"]["failed_gates"],
        "authority_readiness_score_pct": data["authority"]["summary"][
            "authority_readiness_score_pct"
        ],
        "authority_hard_blockers": data["authority"]["summary"]["hard_blockers"],
        "selection_status": "roadmap_generated_not_model_approval",
    }
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "local model selection roadmap; not model approval",
        "source_paths": {
            "model_data": str(MODEL_DATA_PATH.relative_to(ROOT)),
            "asset_inventory": str(ASSET_INVENTORY_PATH.relative_to(ROOT)),
            "runtime_readiness": str(RUNTIME_READINESS_PATH.relative_to(ROOT)),
            "expanded_result_audit": str(EXPANDED_AUDIT_PATH.relative_to(ROOT)),
            "layer_experiment": str(LAYER_EXPERIMENT_PATH.relative_to(ROOT)),
            "authority": str(AUTHORITY_PATH.relative_to(ROOT)),
            "gemma_repair": str(GEMMA_REPAIR_PATH.relative_to(ROOT)),
        },
        "summary": summary,
        "candidate_rows": candidate_rows,
        "gate_rows": gate_rows,
        "phase_rows": phase_rows,
        "source_rows": source_rows(data["model_data"]),
    }


def svg_candidate_chart(rows: list[dict[str, Any]]) -> str:
    width = 1180
    row_h = 44
    top = 42
    left = 190
    right = 30
    height = top + row_h * len(rows) + 36
    chart_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Local model selection score chart">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="0" y="18" font-size="14" font-weight="700" fill="#25313a">'
        "Selection score blends public prior, local asset, measured schema evidence, "
        "and evidence depth.</text>",
    ]
    for tick in range(0, 101, 20):
        x = left + chart_w * tick / 100
        parts.append(
            f'<line x1="{x:.1f}" y1="{top - 10}" x2="{x:.1f}" y2="{height - 28}" stroke="#d9e0e5"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{height - 10}" text-anchor="middle" '
            'font-size="11" fill="#5d6972">'
            f"{tick}</text>"
        )
    for index, row in enumerate(rows):
        y = top + index * row_h
        score = float(row["selection_score_pct"])
        asset = float(row["local_asset_score_pct"])
        measured = float(row["effective_schema_valid_pct"])
        public = float(row["public_prior_pct"])
        parts.append(
            f'<text x="{left - 12}" y="{y + 24}" text-anchor="end" '
            'font-size="12" fill="#25313a">'
            f"{esc(row['short_name'])}</text>"
        )
        x = left
        for value, color in [
            (public * 0.35, "#2f6f73"),
            (asset * 0.25, "#7c5b2f"),
            (measured * 0.25, "#58508d"),
            (float(row["evidence_depth_pct"]) * 0.15, "#9b3d3d"),
        ]:
            segment_w = chart_w * value / 100
            parts.append(
                f'<rect x="{x:.1f}" y="{y + 8}" width="{segment_w:.1f}" '
                f'height="20" rx="2" fill="{color}"/>'
            )
            x += segment_w
        parts.append(
            f'<text x="{left + chart_w * score / 100 + 7:.1f}" y="{y + 24}" '
            'font-size="12" font-weight="700" fill="#25313a">'
            f"{score:.1f}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def svg_gate_chart(rows: list[dict[str, Any]]) -> str:
    width = 1180
    height = 330
    left = 72
    top = 32
    bottom = 86
    right = 26
    chart_w = width - left - right
    chart_h = height - top - bottom
    bar_gap = 14
    bar_w = (chart_w - bar_gap * (len(rows) - 1)) / len(rows)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Certification gate scores">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for tick in range(0, 101, 25):
        y = top + chart_h - chart_h * tick / 100
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#d9e0e5"/>'
        )
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" '
            'font-size="11" fill="#5d6972">'
            f"{tick}</text>"
        )
    for index, row in enumerate(rows):
        score = float(row["score_pct"])
        x = left + index * (bar_w + bar_gap)
        bar_h = chart_h * score / 100
        y = top + chart_h - bar_h
        color = "#2f6f73" if score >= 85 else "#7c5b2f" if score >= 45 else "#9b3d3d"
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 7:.1f}" text-anchor="middle" '
            'font-size="11" font-weight="700" fill="#25313a">'
            f"{score:.0f}</text>"
        )
        label = str(row["gate"]).replace("_", " ")
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{top + chart_h + 20}" '
            'text-anchor="middle" font-size="10" fill="#25313a" '
            f'transform="rotate(34 {x + bar_w / 2:.1f} {top + chart_h + 20})">'
            f"{esc(label)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
        + "</tbody></table>"
    )


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    candidates = report["candidate_rows"]
    gates = report["gate_rows"]
    phases = report["phase_rows"]
    source_items = "".join(
        f'<li><a href="{esc(row["url"])}">{esc(row["id"])}</a></li>'
        for row in report["source_rows"]
        if row["url"]
    )
    candidate_table = table(
        [
            "Model",
            "Asset",
            "Measured rows",
            "Baseline schema",
            "Repair schema",
            "Anchor issues",
            "Selection",
            "Current action",
        ],
        [
            [
                f"<strong>{esc(row['short_name'])}</strong><br><span>{esc(row['model'])}</span>",
                f"{esc(row['asset_status'])}<br><span>{esc(row['best_local_asset'])}</span>",
                f'<span class="num">{row["measured_result_count"]}</span>',
                f'<span class="num">{float(row["measured_schema_valid_pct"]):.2f}%</span>',
                f'<span class="num">{float(row["schema_repair_schema_valid_pct"]):.2f}%</span>',
                f'<span class="num">{row["schema_repair_source_anchor_issue_count"]}</span>',
                f'<span class="num">{float(row["selection_score_pct"]):.2f}</span>',
                esc(row["current_action"]),
            ]
            for row in candidates
        ],
    )
    gate_table = table(
        ["Gate", "Status", "Score", "Evidence", "Next action"],
        [
            [
                esc(row["gate"]),
                esc(row["status"]),
                f'<span class="num">{float(row["score_pct"]):.2f}%</span>',
                esc(row["evidence"]),
                esc(row["next_action"]),
            ]
            for row in gates
        ],
    )
    phase_table = table(
        ["Phase", "Label", "Entry criteria", "Exit criteria", "Models"],
        [
            [
                esc(row["phase"]),
                esc(row["label"]),
                esc(row["entry_criteria"]),
                esc(row["exit_criteria"]),
                esc(row["models"]),
            ]
            for row in phases
        ],
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Local Model Selection Roadmap</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2a33;
      --muted: #64727d;
      --line: #d8e0e6;
      --band: #f4f7f8;
      --accent: #2f6f73;
      --warn: #9b3d3d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #fff;
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
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 22px 0; }}
    .card {{ border: 1px solid var(--line); border-radius: 6px; padding: 16px; background: #fff; }}
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
    td span {{ color: var(--muted); font-size: 11px; }}
    .num {{ text-align: right; white-space: nowrap; }}
    ul {{ margin-top: 8px; }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AlephTav Local Model Selection Roadmap</h1>
    <p class="lede">
      A hard-data decision layer for choosing the next local Hebrew-to-English
      Psalms model under 3090-class constraints. It separates public model facts,
      local asset availability, measured benchmark evidence, and certification gates.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}. This is not model approval.</p>
  </header>
  <main>
    <section>
      <h2>Current Decision State</h2>
      <div class="grid">
        <div class="card">
          <div class="metric">{summary["ready_local_candidate_count"]}</div>
          <div class="label">Runnable candidates</div>
        </div>
        <div class="card">
          <div class="metric">{summary["expanded_submitted_rows"]}</div>
          <div class="label">Measured expanded rows</div>
        </div>
        <div class="card">
          <div class="metric">{summary["expanded_schema_valid_pct"]:.2f}%</div>
          <div class="label">Submitted schema validity</div>
        </div>
        <div class="card">
          <div class="metric">{summary["authority_readiness_score_pct"]:.2f}%</div>
          <div class="label">Authority readiness</div>
        </div>
      </div>
      <div class="warning">
        <strong>Critical reading:</strong> Gemma 4 26B is locally runnable and
        strategically important. Its baseline expanded schema-valid rate was
        {summary["gemma4_26b_baseline_schema_valid_pct"]:.2f}%, and the repair
        path reaches {summary["gemma4_26b_repair_schema_valid_pct"]:.2f}% schema
        validity, but still has
        {summary["gemma4_26b_repair_source_anchor_issue_count"]} source-anchor
        issues and blocked gates:
        {esc(", ".join(summary["gemma4_26b_repair_failed_gates"]))}. Mistral Small 3.2 remains
        the measured local baseline at {summary["mistral_schema_valid_pct"]:.2f}%,
        but the layer experiment still fails {esc(", ".join(summary["failed_layer_gates"]))}.
      </div>
    </section>

    <section>
      <h2>Candidate Selection Matrix</h2>
      <div class="chart">{svg_candidate_chart(candidates)}</div>
      {candidate_table}
    </section>

    <section>
      <h2>Certification Gates</h2>
      <div class="chart">{svg_gate_chart(gates)}</div>
      {gate_table}
    </section>

    <section>
      <h2>Execution Phases</h2>
      {phase_table}
    </section>

    <section>
      <h2>Primary Sources</h2>
      <ul>{source_items}</ul>
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate local model selection roadmap report.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--candidate-csv-output", type=Path, default=DEFAULT_CANDIDATE_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    args = parse_args()
    report = build_report()
    json_output = resolve(args.json_output)
    candidate_csv_output = resolve(args.candidate_csv_output)
    gate_csv_output = resolve(args.gate_csv_output)
    html_output = resolve(args.html_output)
    write_json(json_output, report)
    write_csv(candidate_csv_output, report["candidate_rows"])
    write_csv(gate_csv_output, report["gate_rows"])
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(render_html(report), encoding="utf-8")
    print(json_output)
    print(candidate_csv_output)
    print(gate_csv_output)
    print(html_output)


if __name__ == "__main__":
    main()
