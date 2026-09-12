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
DOC_ROOT = ROOT / "docs" / "research"

SOURCE_PATHS = {
    "model_data": DOC_ROOT / "local_translation_model_data.json",
    "local_model_selection": REPORT_ROOT / "local_model_selection_roadmap.json",
    "runtime_readiness": REPORT_ROOT / "local_runtime_readiness.json",
    "asset_inventory": REPORT_ROOT / "local_model_asset_inventory.json",
    "contextual_real_model_evidence": REPORT_ROOT / "contextual_real_model_evidence_matrix.json",
    "model_evidence_gap": REPORT_ROOT / "model_evidence_gap_report.json",
    "quality_triage": REPORT_ROOT / "model_output_quality_triage.json",
    "layer_consistency": REPORT_ROOT / "layer_consistency_report.json",
    "gemma_schema_repair": REPORT_ROOT / "gemma_schema_repair_report.json",
    "authority": REPORT_ROOT / "scholarly_authority_readiness.json",
    "doctoral_synthesis": REPORT_ROOT / "doctoral_translation_synthesis.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "local_model_doctoral_bakeoff_matrix.json"
DEFAULT_CANDIDATE_CSV_OUTPUT = REPORT_ROOT / "local_model_doctoral_bakeoff_candidates.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "local_model_doctoral_bakeoff_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "local_model_doctoral_bakeoff_matrix.html"


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


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 2)


def score_0_5(value: Any) -> float:
    try:
        return clamp(float(value) / 5.0 * 100.0)
    except (TypeError, ValueError):
        return 0.0


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row.get(key, "")): row for row in rows if row.get(key)}


def source_labels(model_row: dict[str, Any], source_rows: list[dict[str, Any]]) -> list[str]:
    source_map = by_key(source_rows, "id")
    labels: list[str] = []
    for source_id in model_row.get("source_ids", []):
        source = source_map.get(str(source_id), {})
        labels.append(str(source.get("url") or source_id))
    return labels


def status_band(row: dict[str, Any]) -> str:
    if row["local_asset_status"] == "not_recommended":
        return "baseline_only"
    if row["local_asset_status"] == "missing_local_asset":
        return "acquire_exact_asset"
    if row["local_asset_status"] == "near_family_asset_present":
        return "exact_asset_missing"
    if row["contextual_source_anchor_issue_count"] or row["repair_source_anchor_issue_count"]:
        return "anchor_repair_required"
    if row["weak_layer_pair_count"]:
        return "layer_repair_required"
    if (
        row["contextual_clean_source_anchored_pct"] >= 80
        and row["effective_schema_valid_pct"] >= 95
    ):
        return "current_bakeoff_baseline"
    return "smoke_only"


def score_candidate(
    selection_row: dict[str, Any],
    prior_row: dict[str, Any],
    contextual_row: dict[str, Any],
    evidence_gap_row: dict[str, Any],
    layer_row: dict[str, Any],
) -> dict[str, Any]:
    public_prior_pct = float(selection_row.get("public_prior_pct") or 0.0)
    local_asset_score_pct = float(selection_row.get("local_asset_score_pct") or 0.0)
    effective_schema_valid_pct = float(selection_row.get("effective_schema_valid_pct") or 0.0)
    contextual_clean_pct = float(contextual_row.get("clean_source_anchored_pct") or 0.0)
    evidence_depth_pct = float(selection_row.get("evidence_depth_pct") or 0.0)
    hebrew_score_pct = score_0_5(prior_row.get("hebrew_evidence"))
    context_score_pct = score_0_5(prior_row.get("context_fit"))
    fine_tune_score_pct = score_0_5(prior_row.get("fine_tune_tractability"))
    license_score_pct = score_0_5(prior_row.get("license_governance_fit"))
    submitted_expected_pct = float(evidence_gap_row.get("submitted_expected_pct") or 0.0)
    weak_layer_count = int(layer_row.get("weak_layer_differentiation_pair_count") or 0)
    contextual_anchor_issues = int(contextual_row.get("source_anchor_issue_count") or 0)
    repair_anchor_issues = int(selection_row.get("schema_repair_source_anchor_issue_count") or 0)
    failed_gate_count = len(selection_row.get("schema_repair_failed_gates") or [])
    penalty = (
        min(20.0, contextual_anchor_issues * 2.0)
        + min(12.0, repair_anchor_issues * 3.0)
        + min(10.0, weak_layer_count * 0.5)
        + min(15.0, failed_gate_count * 4.0)
    )
    score = (
        public_prior_pct * 0.16
        + local_asset_score_pct * 0.17
        + effective_schema_valid_pct * 0.13
        + contextual_clean_pct * 0.14
        + evidence_depth_pct * 0.08
        + hebrew_score_pct * 0.10
        + context_score_pct * 0.08
        + fine_tune_score_pct * 0.07
        + license_score_pct * 0.04
        + submitted_expected_pct * 0.03
        - penalty
    )
    return {
        "doctoral_bakeoff_score_pct": clamp(score),
        "score_penalty_pct": round(penalty, 2),
        "public_prior_pct": round(public_prior_pct, 2),
        "local_asset_score_pct": round(local_asset_score_pct, 2),
        "effective_schema_valid_pct": round(effective_schema_valid_pct, 2),
        "contextual_clean_source_anchored_pct": round(contextual_clean_pct, 2),
        "evidence_depth_pct": round(evidence_depth_pct, 2),
        "hebrew_score_pct": hebrew_score_pct,
        "context_score_pct": context_score_pct,
        "fine_tune_score_pct": fine_tune_score_pct,
        "license_score_pct": license_score_pct,
        "submitted_expected_pct": round(submitted_expected_pct, 2),
        "weak_layer_pair_count": weak_layer_count,
        "contextual_source_anchor_issue_count": contextual_anchor_issues,
        "repair_source_anchor_issue_count": repair_anchor_issues,
        "failed_repair_gate_count": failed_gate_count,
    }


def build_candidate_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    priors = by_key(data["model_data"].get("candidate_scores", []), "model")
    contextual = by_key(
        data["contextual_real_model_evidence"].get("model_rows", []), "model_profile_id"
    )
    evidence_gap = by_key(data["model_evidence_gap"].get("model_rows", []), "model_profile_id")
    layer = by_key(data["layer_consistency"].get("model_rows", []), "model_profile_id")
    quality = by_key(data["quality_triage"].get("model_rows", []), "model_profile_id")
    source_rows = data["local_model_selection"].get("source_rows", [])
    rows: list[dict[str, Any]] = []
    for selection in data["local_model_selection"].get("candidate_rows", []):
        model = str(selection["model"])
        prior = priors.get(model, {})
        contextual_row = contextual.get(model, {})
        evidence_gap_row = evidence_gap.get(model, {})
        layer_row = layer.get(model, {})
        quality_row = quality.get(model, {})
        score_bits = score_candidate(selection, prior, contextual_row, evidence_gap_row, layer_row)
        row = {
            "rank": 0,
            "model": model,
            "short_name": selection.get("short_name", model),
            "family": selection.get("family", prior.get("family", "")),
            "role": selection.get("role", prior.get("role", "")),
            "local_asset_status": selection.get("asset_status", ""),
            "best_local_asset": selection.get("best_local_asset", ""),
            "ready_profile_id": selection.get("ready_profile_id", ""),
            "measured_result_count": int(selection.get("measured_result_count") or 0),
            "contextual_attempt_count": int(contextual_row.get("attempt_count") or 0),
            "contextual_clean_source_anchored_count": int(
                contextual_row.get("clean_source_anchored_count") or 0
            ),
            "contextual_lane_count": int(contextual_row.get("lane_count") or 0),
            "clean_contextual_lanes": "; ".join(contextual_row.get("clean_lanes") or []),
            "mean_elapsed_ms": round(float(selection.get("mean_elapsed_ms") or 0.0), 2),
            "quality_structure_failure_count": int(quality_row.get("structure_failure_rows") or 0),
            "layer_exact_duplicate_pair_count": int(
                layer_row.get("exact_duplicate_pair_count") or 0
            ),
            "schema_repair_failed_gates": "; ".join(
                selection.get("schema_repair_failed_gates") or []
            ),
            "public_fact": selection.get("public_fact", ""),
            "hardware_note": selection.get("hardware_note", ""),
            "current_action": selection.get("current_action", ""),
            "source_urls": "; ".join(source_labels(selection, source_rows)),
        }
        row.update(score_bits)
        row["status_band"] = status_band(row)
        rows.append(row)
    rows.sort(key=lambda item: item["doctoral_bakeoff_score_pct"], reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_gate_rows(
    data: dict[str, dict[str, Any]], candidate_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    runtime = data["runtime_readiness"]["summary"]
    assets = data["asset_inventory"]["summary"]
    contextual = data["contextual_real_model_evidence"]["summary"]
    selection = data["local_model_selection"]["summary"]
    gemma_repair = data["gemma_schema_repair"]["summary"]
    layer = data["layer_consistency"]["summary"]
    authority = data["authority"]["summary"]
    exact_assets = sum(
        1 for row in candidate_rows if row["local_asset_status"] == "local_asset_present"
    )
    source_anchor_blocked = sum(
        1
        for row in candidate_rows
        if row["contextual_source_anchor_issue_count"] or row["repair_source_anchor_issue_count"]
    )
    return [
        {
            "gate": "3090_runtime_fit",
            "status": "partial",
            "score_pct": runtime["readiness_gate_pass_pct"],
            "evidence": (
                f"{runtime['gpu_count']} GPU visible; max VRAM "
                f"{runtime['max_vram_gb']:.2f} GB; {runtime['q4_fit_model_count']} "
                "candidate memory plans fit at Q4; "
                f"{runtime['qlora_possible_model_count']} QLoRA plans are possible."
            ),
            "next_action": (
                "Keep inference quantized; use adapter training only after source data gates pass."
            ),
        },
        {
            "gate": "exact_local_assets",
            "status": "partial",
            "score_pct": pct(exact_assets, len(candidate_rows)),
            "evidence": (
                f"{exact_assets} of {len(candidate_rows)} bakeoff candidates have exact local "
                f"assets; inventory coverage for recommended models is "
                f"{assets['recommended_asset_coverage_pct']:.2f}%."
            ),
            "next_action": (
                "Acquire exact DictaLM, Gemma 4 12B, and TranslateGemma assets before ranking them."
            ),
        },
        {
            "gate": "schema_admission",
            "status": "partial",
            "score_pct": selection["expanded_schema_valid_pct"],
            "evidence": (
                f"{selection['expanded_schema_valid_pct']:.2f}% expanded submitted rows are "
                "schema-valid, but Gemma required prompt/runtime repair."
            ),
            "next_action": (
                "Treat schema validity as admission only; score source anchoring separately."
            ),
        },
        {
            "gate": "contextual_real_evidence",
            "status": "smoke_only",
            "score_pct": contextual["valid_model_task_coverage_pct"],
            "evidence": (
                f"{contextual['attempt_count']} measured contextual attempts cover "
                f"{contextual['valid_model_task_coverage_pct']:.2f}% of planned rows; "
                f"{contextual['source_anchor_issue_count']} source-anchor issues remain."
            ),
            "next_action": "Run the expanded benchmark after prompt and layer gates pass.",
        },
        {
            "gate": "source_anchor_integrity",
            "status": "blocked",
            "score_pct": pct(len(candidate_rows) - source_anchor_blocked, len(candidate_rows)),
            "evidence": (
                f"{source_anchor_blocked} candidates have measured or repair-track source-anchor "
                "issues; Gemma contextual clean source-anchored count is still zero."
            ),
            "next_action": (
                "Block model approval until token references, source text, and claims stay aligned."
            ),
        },
        {
            "gate": "layer_differentiation",
            "status": "blocked",
            "score_pct": 0.0,
            "evidence": (
                f"{layer['weak_layer_differentiation_pair_count']} weak gloss/literal "
                "differentiation pairs and "
                f"{layer['exact_duplicate_pair_count']} exact duplicate pairs remain."
            ),
            "next_action": "Repair layer prompting and rerun paired gloss/literal probes.",
        },
        {
            "gate": "gemma_repair_track",
            "status": gemma_repair["recommended_status"],
            "score_pct": gemma_repair["best_schema_valid_pct"],
            "evidence": (
                f"Best Gemma repair attempt is {gemma_repair['best_schema_attempt_label']} with "
                f"{gemma_repair['best_schema_valid_pct']:.2f}% schema validity; "
                f"failed gates: {', '.join(gemma_repair['failed_gates'])}."
            ),
            "next_action": "Use Gemma 4 26B only in repair-track probes until failed gates clear.",
        },
        {
            "gate": "human_release_authority",
            "status": "blocked",
            "score_pct": 0.0,
            "evidence": (
                f"Authority readiness remains {authority['authority_readiness_score_pct']:.2f}% "
                f"with hard blockers: {', '.join(authority['hard_blockers'])}."
            ),
            "next_action": (
                "No local model can become authoritative without reviewer signoff and "
                "release gates."
            ),
        },
    ]


def build_phase_rows(
    data: dict[str, dict[str, Any]], candidate_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for phase in data["local_model_selection"].get("phase_rows", []):
        rows.append(
            {
                "phase": phase["phase"],
                "label": phase["label"],
                "entry_criteria": phase["entry_criteria"],
                "exit_criteria": phase["exit_criteria"],
                "models": phase["models"],
                "authority_boundary": "proposal and measurement only; no canonical authority",
            }
        )
    rows.append(
        {
            "phase": "5",
            "label": "Adapter Tuning Readiness",
            "entry_criteria": (
                "A base model has exact local asset, clean source anchors, passing layer gate, "
                "and source-approved training rows."
            ),
            "exit_criteria": (
                "LoRA/QLoRA adapter run is reproducible, version-pinned, and benchmarked "
                "against untouched base plus cross-exam models."
            ),
            "models": "; ".join(row["short_name"] for row in candidate_rows[:4]),
            "authority_boundary": (
                "adapter output remains proposal evidence until human review signs it"
            ),
        }
    )
    return rows


def build_summary(
    data: dict[str, dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    runtime = data["runtime_readiness"]["summary"]
    contextual = data["contextual_real_model_evidence"]["summary"]
    authority = data["authority"]["summary"]
    best_current = next(
        (row for row in candidate_rows if row["status_band"] == "current_bakeoff_baseline"),
        candidate_rows[0],
    )
    trainable_candidates = [
        row
        for row in candidate_rows
        if row["local_asset_status"] != "not_recommended" and row["status_band"] != "baseline_only"
    ]
    primary_trainable = [
        row for row in trainable_candidates if row["role"] == "primary_trainable_base_candidate"
    ]
    best_trainable = max(
        primary_trainable or trainable_candidates,
        key=lambda row: (
            row["fine_tune_score_pct"],
            row["public_prior_pct"],
            row["license_score_pct"],
            row["doctoral_bakeoff_score_pct"],
        ),
    )
    best_hebrew = max(
        candidate_rows,
        key=lambda row: (
            row["hebrew_score_pct"],
            row["doctoral_bakeoff_score_pct"],
        ),
    )
    return {
        "candidate_count": len(candidate_rows),
        "exact_local_asset_count": sum(
            1 for row in candidate_rows if row["local_asset_status"] == "local_asset_present"
        ),
        "near_family_asset_count": sum(
            1 for row in candidate_rows if row["local_asset_status"] == "near_family_asset_present"
        ),
        "missing_local_asset_count": sum(
            1 for row in candidate_rows if row["local_asset_status"] == "missing_local_asset"
        ),
        "ready_profile_count": sum(1 for row in candidate_rows if row["ready_profile_id"]),
        "max_vram_gb": runtime["max_vram_gb"],
        "q4_fit_model_count": runtime["q4_fit_model_count"],
        "qlora_possible_model_count": runtime["qlora_possible_model_count"],
        "contextual_attempt_count": contextual["attempt_count"],
        "contextual_clean_source_anchored_count": contextual["clean_source_anchored_count"],
        "contextual_source_anchor_issue_count": contextual["source_anchor_issue_count"],
        "contextual_valid_model_task_coverage_pct": contextual["valid_model_task_coverage_pct"],
        "mean_doctoral_bakeoff_score_pct": mean(
            [row["doctoral_bakeoff_score_pct"] for row in candidate_rows]
        ),
        "best_current_bakeoff_baseline": best_current["model"],
        "best_current_bakeoff_score_pct": best_current["doctoral_bakeoff_score_pct"],
        "best_trainable_base_if_asset_added": best_trainable["model"],
        "best_trainable_base_score_pct": best_trainable["doctoral_bakeoff_score_pct"],
        "best_hebrew_specialist_candidate": best_hebrew["model"],
        "best_hebrew_specialist_score_pct": best_hebrew["doctoral_bakeoff_score_pct"],
        "gemma4_26b_status": next(
            row["status_band"]
            for row in candidate_rows
            if row["model"] == "google/gemma-4-26B-A4B-it"
        ),
        "mistral_status": next(
            row["status_band"]
            for row in candidate_rows
            if row["model"] == "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
        ),
        "blocked_gate_count": sum(1 for row in gate_rows if row["status"] == "blocked"),
        "authority_hard_blockers": authority["hard_blockers"],
        "authority_readiness_score_pct": authority["authority_readiness_score_pct"],
        "authority_verdict": (
            "Local model selection is measurable and actionable, but no model is "
            "authoritative until source approval, whole-Tanakh morphology, source-anchor "
            "integrity, layer differentiation, human review, and release authority pass."
        ),
    }


def build_visual_data(
    candidate_rows: list[dict[str, Any]], gate_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    status_counts = Counter(row["status_band"] for row in candidate_rows)
    return {
        "candidate_score_rows": [
            {"label": row["short_name"], "value": row["doctoral_bakeoff_score_pct"]}
            for row in candidate_rows
        ],
        "local_asset_rows": [
            {"label": row["short_name"], "value": row["local_asset_score_pct"]}
            for row in candidate_rows
        ],
        "clean_source_anchor_rows": [
            {"label": row["short_name"], "value": row["contextual_clean_source_anchored_pct"]}
            for row in candidate_rows
        ],
        "hebrew_evidence_rows": [
            {"label": row["short_name"], "value": row["hebrew_score_pct"]} for row in candidate_rows
        ],
        "gate_score_rows": [{"label": row["gate"], "value": row["score_pct"]} for row in gate_rows],
        "status_band_rows": [
            {"label": label, "value": count}
            for label, count in sorted(status_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    candidate_rows = build_candidate_rows(data)
    gate_rows = build_gate_rows(data, candidate_rows)
    phase_rows = build_phase_rows(data, candidate_rows)
    summary = build_summary(data, candidate_rows, gate_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "local model doctoral bakeoff matrix generated; not model approval",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "method": {
            "authority_boundary": (
                "Scores combine public priors, local assets, measured outputs, source-anchor "
                "behavior, Hebrew/context fit, fine-tune tractability, and license posture. "
                "They are triage scores, not translation authority."
            ),
            "score_components": {
                "public_prior_pct": 0.16,
                "local_asset_score_pct": 0.17,
                "effective_schema_valid_pct": 0.13,
                "contextual_clean_source_anchored_pct": 0.14,
                "evidence_depth_pct": 0.08,
                "hebrew_score_pct": 0.10,
                "context_score_pct": 0.08,
                "fine_tune_score_pct": 0.07,
                "license_score_pct": 0.04,
                "submitted_expected_pct": 0.03,
                "penalties": (
                    "source-anchor issues, repair-track source-anchor issues, weak layer "
                    "pairs, and failed repair gates"
                ),
            },
        },
        "summary": summary,
        "candidate_rows": candidate_rows,
        "gate_rows": gate_rows,
        "phase_rows": phase_rows,
        "visual_data": build_visual_data(candidate_rows, gate_rows),
    }


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str = "label",
    value_key: str = "value",
    width: int = 920,
    row_height: int = 28,
    color: str = "#2f6f73",
    max_value: float | None = None,
    limit: int = 12,
) -> str:
    chart_rows = rows[:limit]
    if not chart_rows:
        return ""
    values = [float(row.get(value_key) or 0.0) for row in chart_rows]
    maximum = max_value or max(values) or 1.0
    label_width = 280
    bar_width = width - label_width - 80
    height = 28 + len(chart_rows) * row_height
    parts = [
        (
            f'<svg role="img" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
        )
    ]
    for index, row in enumerate(chart_rows):
        y = 22 + index * row_height
        label = str(row.get(label_key, ""))
        value = float(row.get(value_key) or 0.0)
        length = 0 if maximum <= 0 else value / maximum * bar_width
        parts.append(f'<text x="0" y="{y + 14}" font-size="12" fill="#263238">{esc(label)}</text>')
        parts.append(
            f'<rect x="{label_width}" y="{y}" width="{length:.2f}" height="18" '
            f'rx="3" fill="{color}" />'
        )
        parts.append(
            f'<text x="{label_width + length + 8:.2f}" y="{y + 14}" '
            f'font-size="12" fill="#263238">{value:.2f}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def metric_cards(cards: list[tuple[str, Any, str]]) -> str:
    return (
        '<div class="metrics">'
        + "".join(
            (
                '<div class="metric">'
                f'<div class="metric-label">{esc(label)}</div>'
                f'<div class="metric-value">{esc(value)}</div>'
                f'<div class="metric-note">{esc(note)}</div>'
                "</div>"
            )
            for label, value, note in cards
        )
        + "</div>"
    )


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    candidate_rows = [
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
            row["weak_layer_pair_count"],
            f"{row['hebrew_score_pct']:.2f}%",
            row["current_action"],
        ]
        for row in report["candidate_rows"]
    ]
    gate_rows = [
        [
            row["gate"],
            row["status"],
            f"{row['score_pct']:.2f}%",
            row["evidence"],
            row["next_action"],
        ]
        for row in report["gate_rows"]
    ]
    phase_rows = [
        [
            row["phase"],
            row["label"],
            row["entry_criteria"],
            row["exit_criteria"],
            row["models"],
            row["authority_boundary"],
        ]
        for row in report["phase_rows"]
    ]
    source_rows = [
        [
            row["short_name"],
            row["public_fact"],
            row["hardware_note"],
            row["source_urls"],
        ]
        for row in report["candidate_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Local Model Doctoral Bakeoff Matrix</title>
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
      line-height: 1.45;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 56px;
    }}
    h1, h2 {{
      margin: 0 0 12px;
    }}
    section {{
      margin-top: 28px;
      border-top: 1px solid var(--line);
      padding-top: 22px;
    }}
    .lede {{
      color: var(--muted);
      max-width: 980px;
      font-size: 1.03rem;
    }}
    .warning {{
      border-left: 4px solid var(--bad);
      padding: 12px 16px;
      background: #fff7f5;
      margin: 16px 0;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin: 18px 0;
    }}
    .metric {{
      border: 1px solid var(--line);
      background: var(--panel);
      padding: 12px;
      border-radius: 8px;
      min-height: 94px;
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .metric-value {{
      font-size: 1.42rem;
      font-weight: 700;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }}
    .metric-note {{
      margin-top: 7px;
      color: var(--muted);
      font-size: 0.88rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .chart {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #ffffff;
      margin-bottom: 16px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 0.88rem;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 7px 8px;
      vertical-align: top;
      text-align: left;
    }}
    th {{
      background: #edf3f2;
    }}
    td {{
      overflow-wrap: anywhere;
    }}
  </style>
</head>
<body>
<main>
  <h1>Local Model Doctoral Bakeoff Matrix</h1>
  <p class="lede">
    This report joins local runtime facts, exact asset availability, model priors,
    measured smoke outputs, schema repair status, source-anchor failures, Hebrew
    specialist value, and authority blockers. It is designed to answer which
    local base or comparator should be advanced next for a 3090-class Hebrew to
    English Psalms translation workbench.
  </p>
  <div class="warning">
    <strong>Authority boundary:</strong>
    {esc(summary["authority_verdict"])}
  </div>
  {
        metric_cards(
            [
                (
                    "Best current baseline",
                    summary["best_current_bakeoff_baseline"],
                    f"{summary['best_current_bakeoff_score_pct']:.2f}% bakeoff score.",
                ),
                (
                    "Best trainable target",
                    summary["best_trainable_base_if_asset_added"],
                    "Chosen by fine-tune tractability, prior, license, and current evidence.",
                ),
                (
                    "Best Hebrew specialist",
                    summary["best_hebrew_specialist_candidate"],
                    "Still needs exact local asset and smoke evidence if not runnable.",
                ),
                (
                    "Contextual coverage",
                    f"{summary['contextual_valid_model_task_coverage_pct']:.2f}%",
                    f"{summary['contextual_attempt_count']} measured contextual attempts.",
                ),
                (
                    "Exact local assets",
                    f"{summary['exact_local_asset_count']}/{summary['candidate_count']}",
                    f"{summary['ready_profile_count']} ready profiles.",
                ),
                (
                    "Visible VRAM",
                    f"{summary['max_vram_gb']:.2f} GB",
                    f"{summary['q4_fit_model_count']} Q4 fit plans; "
                    f"{summary['qlora_possible_model_count']} QLoRA possible.",
                ),
                (
                    "Source-anchor issues",
                    summary["contextual_source_anchor_issue_count"],
                    f"{summary['contextual_clean_source_anchored_count']} clean contextual rows.",
                ),
                (
                    "Authority blockers",
                    ", ".join(summary["authority_hard_blockers"]),
                    f"{summary['authority_readiness_score_pct']:.2f}% authority readiness.",
                ),
            ]
        )
    }
  <section>
    <h2>Candidate Frontier</h2>
    <div class="grid">
      <div class="chart">{
        svg_horizontal_bars(
            visual["candidate_score_rows"],
            color="#2f6f73",
            max_value=100,
            limit=10,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["clean_source_anchor_rows"],
            color="#8a6426",
            max_value=100,
            limit=10,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["local_asset_rows"],
            color="#2f6f73",
            max_value=100,
            limit=10,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["hebrew_evidence_rows"],
            color="#9b3d3d",
            max_value=100,
            limit=10,
        )
    }</div>
    </div>
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
                "Weak Layer Pairs",
                "Hebrew",
                "Action",
            ],
            candidate_rows,
        )
    }
  </section>
  <section>
    <h2>Decision Gates</h2>
    <div class="chart">{
        svg_horizontal_bars(
            visual["gate_score_rows"],
            color="#8a6426",
            max_value=100,
            limit=12,
        )
    }</div>
    {table(["Gate", "Status", "Score", "Evidence", "Next Action"], gate_rows)}
  </section>
  <section>
    <h2>Bakeoff Phases</h2>
    {
        table(
            [
                "Phase",
                "Label",
                "Entry Criteria",
                "Exit Criteria",
                "Models",
                "Boundary",
            ],
            phase_rows,
        )
    }
  </section>
  <section>
    <h2>Source Facts and Hardware Notes</h2>
    {table(["Model", "Public Fact", "Hardware Note", "Source URLs"], source_rows)}
  </section>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate local model doctoral bakeoff matrix.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--candidate-csv-output", type=Path, default=DEFAULT_CANDIDATE_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.candidate_csv_output, report["candidate_rows"])
    write_csv(args.gate_csv_output, report["gate_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.candidate_csv_output}")
    print(f"Wrote {args.gate_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
