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

CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
RECEPTION_BOUNDARY_PATH = REPORT_ROOT / "reception_interpretation_boundary.json"
WITNESS_PATH = REPORT_ROOT / "witness_reception_readiness.json"
CANONICAL_CONTEXT_PATH = REPORT_ROOT / "canonical_context_network.json"
MORPHOLOGY_GAP_PATH = REPORT_ROOT / "whole_tanakh_morphology_gap.json"
REVIEW_PLAN_PATH = REPORT_ROOT / "contextual_expanded_benchmark_review_signoff_plan.json"
QUALITY_TRIAGE_PATH = REPORT_ROOT / "model_output_quality_triage.json"
LAYER_CONSISTENCY_PATH = REPORT_ROOT / "layer_consistency_report.json"
AUTHORITY_PATH = REPORT_ROOT / "scholarly_authority_readiness.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "interpretive_adjudication_matrix.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "interpretive_adjudication_units.csv"
DEFAULT_LANE_CSV_OUTPUT = REPORT_ROOT / "interpretive_adjudication_lanes.csv"
DEFAULT_DOMAIN_CSV_OUTPUT = REPORT_ROOT / "interpretive_adjudication_domains.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "interpretive_adjudication_gates.csv"
DEFAULT_ROLE_CSV_OUTPUT = REPORT_ROOT / "interpretive_adjudication_roles.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "interpretive_adjudication_matrix.html"

LANE_LABELS = {
    "hebrew_source": "Hebrew Source Basis",
    "morphology_lexeme": "Morphology and Lexeme",
    "whole_tanakh_context": "Whole-Tanakh Context",
    "textual_witness": "Textual Witnesses",
    "ancient_culture": "Ancient Cultural Context",
    "jewish_reception": "Jewish Reception",
    "christian_reception": "Christian Reception",
    "academic_comparison": "Academic Comparison",
    "local_model_output": "Local Model Output",
    "layer_separation": "Layer Separation",
    "human_signoff": "Human Signoff",
}

STATUS_GROUPS = {
    "evidence_ready": "ready",
    "review_planned": "review",
    "review_required": "review",
    "surface_only": "partial",
    "partial_psalm_only": "partial",
    "model_partial_unreviewed": "partial",
    "missing_model_output": "blocked",
    "layer_blocked": "blocked",
    "human_signoff_missing": "blocked",
    "not_required": "not_required",
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


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def rows_by_unit(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in rows if row.get("unit_id")}


def status_group(status: str) -> str:
    return STATUS_GROUPS.get(status, "review")


def review_plan_by_unit(review_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for task in review_plan.get("task_review_plan", []):
        unit_id = str(task["unit_id"])
        row = rows.setdefault(
            unit_id,
            {
                "unit_id": unit_id,
                "required_roles": set(),
                "task_count": 0,
                "task_intensity_counts": Counter(),
            },
        )
        row["task_count"] += 1
        row["required_roles"].update(str(role) for role in task.get("required_roles", []))
        row["task_intensity_counts"].update([str(task.get("intensity") or "standard")])
    for row in rows.values():
        row["required_roles"] = sorted(row["required_roles"])
        row["task_intensity_counts"] = dict(row["task_intensity_counts"].most_common())
    return rows


def human_review_rows_by_role(review_plan: dict[str, Any]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in review_plan.get("human_review_template_rows", []):
        counter.update([str(row.get("reviewer_role") or "unknown")])
    return dict(counter.most_common())


def quality_rows_by_unit(quality: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for candidate in quality.get("candidate_rows", []):
        unit_id = str(candidate["unit_id"])
        row = rows.setdefault(
            unit_id,
            {
                "unit_id": unit_id,
                "model_candidate_count": 0,
                "schema_valid_model_candidate_count": 0,
                "structure_failure_count": 0,
                "source_anchor_issue_count": 0,
                "status_counts": Counter(),
                "flag_counts": Counter(),
                "max_review_priority_score": 0.0,
            },
        )
        row["model_candidate_count"] += 1
        if candidate.get("schema_valid"):
            row["schema_valid_model_candidate_count"] += 1
        if str(candidate.get("quality_status") or "").startswith("structure_failure"):
            row["structure_failure_count"] += 1
        row["source_anchor_issue_count"] += int(candidate.get("source_anchor_issue_count") or 0)
        row["status_counts"].update([str(candidate.get("quality_status") or "unknown")])
        row["flag_counts"].update(str(flag) for flag in candidate.get("flags", []))
        row["max_review_priority_score"] = max(
            float(row["max_review_priority_score"]),
            float(candidate.get("review_priority_score") or 0.0),
        )
    for row in rows.values():
        row["status_counts"] = dict(row["status_counts"].most_common())
        row["flag_counts"] = dict(row["flag_counts"].most_common())
    return rows


def layer_rows_by_unit(layer: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return rows_by_unit(layer.get("pair_rows", []))


def lane_statuses(
    *,
    claim: dict[str, Any],
    reception: dict[str, Any],
    witness: dict[str, Any],
    canonical: dict[str, Any],
    morph: dict[str, Any],
    review: dict[str, Any],
    quality: dict[str, Any],
    layer: dict[str, Any],
) -> dict[str, str]:
    required_roles = set(review.get("required_roles", [])) | set(
        claim.get("required_review_roles", [])
    )
    basis_statuses = claim.get("basis_statuses", {})
    has_model = int(quality.get("model_candidate_count") or 0) > 0
    valid_model = int(quality.get("schema_valid_model_candidate_count") or 0) > 0
    layer_blocked = bool(
        layer.get("exact_duplicate")
        or "weak_layer_differentiation" in layer.get("flags", [])
        or "divine_name_rendering_differs_by_layer" in layer.get("flags", [])
    )
    statuses = {
        "hebrew_source": (
            "review_planned"
            if required_roles & {"Hebrew", "alignment", "lexical"}
            else "review_required"
        ),
        "morphology_lexeme": (
            "partial_psalm_only"
            if "non-Psalm morphology absent" in str(basis_statuses.get("morphology", ""))
            else "evidence_ready"
        ),
        "whole_tanakh_context": (
            "surface_only"
            if float(canonical.get("content_token_outside_context_pct") or 0.0) > 0.0
            else "review_required"
        ),
        "textual_witness": (
            "review_required"
            if claim.get("textual_witness_pressure")
            else "evidence_ready"
            if witness.get("complete_expected_witness_set")
            else "review_required"
        ),
        "ancient_culture": (
            "review_required" if claim.get("ancient_culture_pressure") else "not_required"
        ),
        "jewish_reception": (
            "review_required" if claim.get("has_jewish_reception_frame") else "not_required"
        ),
        "christian_reception": (
            "review_required" if claim.get("has_christian_reception_frame") else "not_required"
        ),
        "academic_comparison": (
            "review_required" if claim.get("has_academic_comparison_frame") else "not_required"
        ),
        "local_model_output": (
            "layer_blocked"
            if has_model and layer_blocked
            else "model_partial_unreviewed"
            if valid_model
            else "missing_model_output"
        ),
        "layer_separation": (
            "layer_blocked"
            if layer_blocked
            else "review_required"
            if has_model
            else "missing_model_output"
        ),
        "human_signoff": "human_signoff_missing",
    }
    if reception.get("reception_sensitive") and statuses["jewish_reception"] == "not_required":
        statuses["jewish_reception"] = "review_required"
    if reception.get("reception_sensitive") and statuses["christian_reception"] == "not_required":
        statuses["christian_reception"] = "review_required"
    return statuses


def unit_priority_score(
    claim: dict[str, Any],
    reception: dict[str, Any],
    quality: dict[str, Any],
    layer: dict[str, Any],
    statuses: dict[str, str],
) -> float:
    score = float(claim.get("claim_risk_score") or 0.0)
    score += float(reception.get("boundary_risk_score") or 0.0) * 0.35
    score += float(quality.get("max_review_priority_score") or 0.0) * 0.25
    if layer.get("exact_duplicate"):
        score += 12
    if "weak_layer_differentiation" in layer.get("flags", []):
        score += 10
    score += sum(4 for status in statuses.values() if status_group(status) == "blocked")
    score += sum(2 for status in statuses.values() if status_group(status) == "review")
    return round(score, 2)


def priority_band(score: float) -> str:
    if score >= 170:
        return "highest"
    if score >= 130:
        return "high"
    if score >= 95:
        return "medium"
    return "standard"


def build_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    claim_rows = rows_by_unit(data["claim_matrix"].get("unit_claim_rows", []))
    reception_rows = rows_by_unit(data["reception_boundary"].get("unit_boundary_rows", []))
    witness_rows = rows_by_unit(data["witness"].get("witness_unit_rows", []))
    canonical_rows = rows_by_unit(data["canonical_context"].get("unit_network_rows", []))
    morph_rows = rows_by_unit(data["morphology_gap"].get("benchmark_unit_rows", []))
    review_rows = review_plan_by_unit(data["review_plan"])
    quality_rows = quality_rows_by_unit(data["quality_triage"])
    layer_rows = layer_rows_by_unit(data["layer_consistency"])
    output = []
    for unit_id, claim in sorted(claim_rows.items()):
        reception = reception_rows.get(unit_id, {})
        witness = witness_rows.get(unit_id, {})
        canonical = canonical_rows.get(unit_id, {})
        morph = morph_rows.get(unit_id, {})
        review = review_rows.get(unit_id, {})
        quality = quality_rows.get(unit_id, {})
        layer = layer_rows.get(unit_id, {})
        statuses = lane_statuses(
            claim=claim,
            reception=reception,
            witness=witness,
            canonical=canonical,
            morph=morph,
            review=review,
            quality=quality,
            layer=layer,
        )
        score = unit_priority_score(claim, reception, quality, layer, statuses)
        status_counts = Counter(status_group(status) for status in statuses.values())
        output.append(
            {
                "unit_id": unit_id,
                "ref": claim.get("ref", reception.get("ref", "")),
                "task_count": int(claim.get("task_count") or 0),
                "layers": claim.get("layers", []),
                "domains": claim.get("domains", []),
                "domain_groups": claim.get("domain_groups", []),
                "benchmark_tags": claim.get("benchmark_tags", []),
                "required_frames": claim.get("required_frames", []),
                "required_review_roles": sorted(
                    set(claim.get("required_review_roles", []))
                    | set(review.get("required_roles", []))
                ),
                "claim_risk_score": float(claim.get("claim_risk_score") or 0.0),
                "boundary_risk_score": float(reception.get("boundary_risk_score") or 0.0),
                "adjudication_priority_score": score,
                "adjudication_priority_band": priority_band(score),
                "lane_statuses": statuses,
                "ready_lane_count": status_counts["ready"],
                "partial_lane_count": status_counts["partial"],
                "review_lane_count": status_counts["review"],
                "blocked_lane_count": status_counts["blocked"],
                "not_required_lane_count": status_counts["not_required"],
                "reception_sensitive": bool(claim.get("reception_sensitive")),
                "jewish_christian_separation_required": bool(
                    claim.get("has_jewish_reception_frame")
                    and claim.get("has_christian_reception_frame")
                ),
                "textual_witness_pressure": bool(claim.get("textual_witness_pressure")),
                "ancient_culture_pressure": bool(claim.get("ancient_culture_pressure")),
                "theology_pressure": bool(claim.get("theology_pressure")),
                "complete_expected_witness_set": bool(
                    witness.get("complete_expected_witness_set")
                    or claim.get("complete_expected_witness_set")
                ),
                "witness_count": int(
                    witness.get("witness_count") or claim.get("witness_count") or 0
                ),
                "english_witness_count": int(
                    witness.get("english_witness_count") or claim.get("english_witness_count") or 0
                ),
                "content_token_outside_context_pct": float(
                    canonical.get("content_token_outside_context_pct")
                    or claim.get("content_token_outside_context_pct")
                    or 0.0
                ),
                "surface_outside_context_pct": float(
                    morph.get("surface_outside_context_pct")
                    or claim.get("surface_outside_context_pct")
                    or 0.0
                ),
                "outside_strong_context_pct": float(
                    morph.get("outside_strong_context_pct")
                    or claim.get("outside_strong_context_pct")
                    or 0.0
                ),
                "model_candidate_count": int(quality.get("model_candidate_count") or 0),
                "schema_valid_model_candidate_count": int(
                    quality.get("schema_valid_model_candidate_count") or 0
                ),
                "model_structure_failure_count": int(quality.get("structure_failure_count") or 0),
                "model_source_anchor_issue_count": int(
                    quality.get("source_anchor_issue_count") or 0
                ),
                "model_max_review_priority_score": float(
                    quality.get("max_review_priority_score") or 0.0
                ),
                "layer_pair_present": bool(layer),
                "layer_risk_score": float(layer.get("layer_risk_score") or 0.0),
                "layer_exact_duplicate": bool(layer.get("exact_duplicate")),
                "layer_flags": layer.get("flags", []),
                "basis_statuses": claim.get("basis_statuses", {}),
                "claim_controls": claim.get("claim_controls", []),
            }
        )
    return sorted(
        output,
        key=lambda row: (
            float(row["adjudication_priority_score"]),
            int(row["blocked_lane_count"]),
            str(row["unit_id"]),
        ),
        reverse=True,
    )


def lane_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for lane, label in LANE_LABELS.items():
        statuses = [str(row["lane_statuses"].get(lane, "not_required")) for row in unit_rows]
        groups = Counter(status_group(status) for status in statuses)
        status_counts = Counter(statuses)
        required_count = len(unit_rows) - groups["not_required"]
        rows.append(
            {
                "lane": lane,
                "label": label,
                "required_unit_count": required_count,
                "ready_unit_count": groups["ready"],
                "partial_unit_count": groups["partial"],
                "review_unit_count": groups["review"],
                "blocked_unit_count": groups["blocked"],
                "not_required_unit_count": groups["not_required"],
                "dominant_status": status_counts.most_common(1)[0][0] if statuses else "",
                "status_counts": dict(status_counts.most_common()),
            }
        )
    return sorted(
        rows, key=lambda row: (row["blocked_unit_count"], row["required_unit_count"]), reverse=True
    )


def domain_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        for domain in row.get("domains", []) or ["unclassified"]:
            grouped[str(domain)].append(row)
    rows = []
    for domain, values in grouped.items():
        rows.append(
            {
                "domain": domain,
                "unit_count": len(values),
                "avg_adjudication_priority_score": mean(
                    [float(row["adjudication_priority_score"]) for row in values]
                ),
                "highest_priority_unit_count": sum(
                    1 for row in values if row["adjudication_priority_band"] == "highest"
                ),
                "reception_sensitive_unit_count": sum(
                    1 for row in values if row["reception_sensitive"]
                ),
                "jewish_christian_unit_count": sum(
                    1 for row in values if row["jewish_christian_separation_required"]
                ),
                "textual_witness_unit_count": sum(
                    1 for row in values if row["textual_witness_pressure"]
                ),
                "ancient_culture_unit_count": sum(
                    1 for row in values if row["ancient_culture_pressure"]
                ),
                "model_evidence_unit_count": sum(
                    1 for row in values if row["schema_valid_model_candidate_count"] > 0
                ),
                "layer_blocked_unit_count": sum(
                    1
                    for row in values
                    if row["lane_statuses"]["layer_separation"] == "layer_blocked"
                ),
            }
        )
    return sorted(rows, key=lambda row: row["avg_adjudication_priority_score"], reverse=True)


def role_rows(unit_rows: list[dict[str, Any]], review_plan: dict[str, Any]) -> list[dict[str, Any]]:
    unit_counter: Counter[str] = Counter()
    highest_counter: Counter[str] = Counter()
    for row in unit_rows:
        for role in row.get("required_review_roles", []):
            unit_counter.update([str(role)])
            if row["adjudication_priority_band"] == "highest":
                highest_counter.update([str(role)])
    human_rows = human_review_rows_by_role(review_plan)
    roles = sorted(set(unit_counter) | set(human_rows))
    return [
        {
            "reviewer_role": role,
            "unit_count": unit_counter[role],
            "highest_priority_unit_count": highest_counter[role],
            "projected_human_review_rows": human_rows.get(role, 0),
        }
        for role in roles
    ]


def gate_rows(
    unit_rows: list[dict[str, Any]],
    data: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    authority = data["authority"]["summary"]
    expanded_review = data["review_plan"]["summary"]
    quality = data["quality_triage"]["summary"]
    layer = data["layer_consistency"]["summary"]
    all_units = len(unit_rows)
    clean_layer_pairs = int(layer["schema_valid_pair_count"]) - int(
        layer["weak_layer_differentiation_pair_count"]
    )
    return [
        {
            "gate": "hebrew_source_basis",
            "status": "planned_review",
            "score_pct": 0.0,
            "evidence": (
                f"{all_units} expanded units require Hebrew, lexical, and alignment "
                "review before authority claims."
            ),
            "next_action": "Collect role-specific reviewer scores, not just model output.",
        },
        {
            "gate": "witness_provenance",
            "status": "evidence_ready",
            "score_pct": pct(
                sum(1 for row in unit_rows if row["complete_expected_witness_set"]),
                all_units,
            ),
            "evidence": (
                "Expanded units have complete labeled witness sets; English witnesses "
                "remain blocked as generation sources."
            ),
            "next_action": "Keep witness readings in tagged notes, never translation basis.",
        },
        {
            "gate": "jewish_christian_boundary",
            "status": "review_required",
            "score_pct": 0.0,
            "evidence": (
                f"{sum(1 for row in unit_rows if row['jewish_christian_separation_required'])} "
                "expanded units require separated Jewish and Christian reception lanes."
            ),
            "next_action": "Add human theology/reception adjudication rows for both lanes.",
        },
        {
            "gate": "whole_tanakh_context",
            "status": "surface_only",
            "score_pct": data["canonical_context"]["summary"]["content_token_outside_context_pct"],
            "evidence": (
                "Whole-Tanakh context is currently surface-form evidence; local "
                "non-Psalm morphology remains absent."
            ),
            "next_action": "Do not treat surface matches as lemma/sense proof.",
        },
        {
            "gate": "local_model_output",
            "status": "partial",
            "score_pct": pct(
                quality["schema_valid_candidate_count"],
                data["authority"]["summary"]["expanded_planned_model_runs"],
            ),
            "evidence": (
                f"{quality['schema_valid_candidate_count']} schema-valid candidate rows "
                f"exist out of {authority['expanded_planned_model_runs']} planned runs."
            ),
            "next_action": "Expand only after layer and source-anchor gates are stable.",
        },
        {
            "gate": "layer_separation",
            "status": "fail",
            "score_pct": pct(clean_layer_pairs, layer["paired_unit_model_count"]),
            "evidence": (
                f"{layer['weak_layer_differentiation_pair_count']} weak layer pairs and "
                f"{layer['exact_duplicate_pair_count']} exact duplicates remain."
            ),
            "next_action": "Require gloss/literal separation before content quality scoring.",
        },
        {
            "gate": "human_signoff",
            "status": "blocked",
            "score_pct": 0.0,
            "evidence": (
                f"{expanded_review['projected_human_review_rows']} projected human "
                "review rows exist, but completed reviewer scores are absent."
            ),
            "next_action": "Use model output as proposals only until signoff is complete.",
        },
        {
            "gate": "release_authority",
            "status": "blocked",
            "score_pct": 0.0,
            "evidence": "Authority report hard blockers: " + ", ".join(authority["hard_blockers"]),
            "next_action": "No local model is authoritative until release gates pass.",
        },
    ]


def summarize(
    unit_rows: list[dict[str, Any]],
    lane_summary: list[dict[str, Any]],
    gates: list[dict[str, Any]],
) -> dict[str, Any]:
    band_counts = Counter(str(row["adjudication_priority_band"]) for row in unit_rows)
    lane_blockers = sum(int(row["blocked_unit_count"]) for row in lane_summary)
    failed_gates = [row["gate"] for row in gates if row["status"] in {"fail", "blocked"}]
    return {
        "unit_count": len(unit_rows),
        "highest_priority_unit_count": band_counts["highest"],
        "high_priority_unit_count": band_counts["high"],
        "medium_priority_unit_count": band_counts["medium"],
        "standard_priority_unit_count": band_counts["standard"],
        "avg_adjudication_priority_score": mean(
            [float(row["adjudication_priority_score"]) for row in unit_rows]
        ),
        "reception_sensitive_unit_count": sum(1 for row in unit_rows if row["reception_sensitive"]),
        "jewish_christian_separation_unit_count": sum(
            1 for row in unit_rows if row["jewish_christian_separation_required"]
        ),
        "textual_witness_pressure_unit_count": sum(
            1 for row in unit_rows if row["textual_witness_pressure"]
        ),
        "ancient_culture_pressure_unit_count": sum(
            1 for row in unit_rows if row["ancient_culture_pressure"]
        ),
        "units_with_schema_valid_model_output": sum(
            1 for row in unit_rows if row["schema_valid_model_candidate_count"] > 0
        ),
        "units_with_layer_blockers": sum(
            1 for row in unit_rows if row["lane_statuses"]["layer_separation"] == "layer_blocked"
        ),
        "lane_count": len(lane_summary),
        "lane_blocker_count": lane_blockers,
        "gate_count": len(gates),
        "failed_gate_count": len(failed_gates),
        "failed_gates": failed_gates,
        "top_adjudication_unit": unit_rows[0]["unit_id"] if unit_rows else "",
        "top_adjudication_ref": unit_rows[0]["ref"] if unit_rows else "",
        "top_adjudication_score": unit_rows[0]["adjudication_priority_score"] if unit_rows else 0.0,
        "status": "adjudication_matrix_generated_not_signoff",
    }


def build_report() -> dict[str, Any]:
    data = {
        "claim_matrix": load_json(CLAIM_MATRIX_PATH),
        "reception_boundary": load_json(RECEPTION_BOUNDARY_PATH),
        "witness": load_json(WITNESS_PATH),
        "canonical_context": load_json(CANONICAL_CONTEXT_PATH),
        "morphology_gap": load_json(MORPHOLOGY_GAP_PATH),
        "review_plan": load_json(REVIEW_PLAN_PATH),
        "quality_triage": load_json(QUALITY_TRIAGE_PATH),
        "layer_consistency": load_json(LAYER_CONSISTENCY_PATH),
        "authority": load_json(AUTHORITY_PATH),
    }
    units = build_unit_rows(data)
    lanes = lane_rows(units)
    domains = domain_rows(units)
    roles = role_rows(units, data["review_plan"])
    gates = gate_rows(units, data)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "interpretive adjudication matrix; not human signoff",
        "source_paths": {
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
            "reception_boundary": str(RECEPTION_BOUNDARY_PATH.relative_to(ROOT)),
            "witness": str(WITNESS_PATH.relative_to(ROOT)),
            "canonical_context": str(CANONICAL_CONTEXT_PATH.relative_to(ROOT)),
            "morphology_gap": str(MORPHOLOGY_GAP_PATH.relative_to(ROOT)),
            "review_plan": str(REVIEW_PLAN_PATH.relative_to(ROOT)),
            "quality_triage": str(QUALITY_TRIAGE_PATH.relative_to(ROOT)),
            "layer_consistency": str(LAYER_CONSISTENCY_PATH.relative_to(ROOT)),
            "authority": str(AUTHORITY_PATH.relative_to(ROOT)),
        },
        "policy": {
            "translation_text": "Hebrew token-aligned source basis only.",
            "textual_witnesses": (
                "LXX and English witnesses are labeled evidence; English witnesses "
                "are not generation sources."
            ),
            "reception": (
                "Jewish and Christian reception lanes are separated and excluded "
                "from translation wording."
            ),
            "whole_tanakh": (
                "Whole-Tanakh surface context may guide review questions but is not "
                "lemma or sense proof without morphology."
            ),
            "authority": "No model output becomes authoritative without human signoff.",
        },
        "summary": summarize(units, lanes, gates),
        "gate_rows": gates,
        "lane_rows": lanes,
        "domain_rows": domains,
        "role_rows": roles,
        "unit_rows": units,
    }


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    width: int = 1080,
    limit: int = 18,
) -> str:
    rows = rows[:limit]
    row_h = 31
    left = 300
    right = 80
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
            f'<text x="{left - 12}" y="{y + 20}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row[label_key])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 5}" width="{bar_w:.1f}" height="18" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 20}" font-size="12" '
            f'font-weight="700" fill="#24313a">{value:g}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def svg_lane_stack(rows: list[dict[str, Any]]) -> str:
    width = 1120
    row_h = 34
    left = 230
    right = 30
    top = 28
    height = top * 2 + row_h * len(rows)
    chart_w = width - left - right
    colors = {
        "ready_unit_count": "#2f6f73",
        "partial_unit_count": "#7c5b2f",
        "review_unit_count": "#58508d",
        "blocked_unit_count": "#9b3d3d",
    }
    labels = {
        "ready_unit_count": "ready",
        "partial_unit_count": "partial",
        "review_unit_count": "review",
        "blocked_unit_count": "blocked",
    }
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Adjudication lane status stack">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, row in enumerate(rows):
        y = top + index * row_h
        total = max(1, int(row["required_unit_count"]))
        x = left
        parts.append(
            f'<text x="{left - 12}" y="{y + 22}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row["label"])}</text>'
        )
        for key, color in colors.items():
            value = int(row[key])
            width_part = chart_w * value / total
            parts.append(
                f'<rect x="{x:.1f}" y="{y + 7}" width="{width_part:.1f}" '
                f'height="18" rx="2" fill="{color}"/>'
            )
            if width_part >= 32:
                parts.append(
                    f'<text x="{x + width_part / 2:.1f}" y="{y + 21}" '
                    'text-anchor="middle" font-size="10" fill="#ffffff">'
                    f"{value}</text>"
                )
            x += width_part
        parts.append(
            f'<text x="{width - right}" y="{y + 22}" text-anchor="end" '
            'font-size="11" fill="#5d6972">'
            + ", ".join(f"{labels[key]} {row[key]}" for key in colors)
            + "</text>"
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
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
        + "</tbody></table>"
    )


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lanes = report["lane_rows"]
    domains = report["domain_rows"]
    gates = report["gate_rows"]
    roles = report["role_rows"]
    units = report["unit_rows"]
    top_units = units[:18]
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
    lane_table = table(
        ["Lane", "Required", "Ready", "Partial", "Review", "Blocked", "Dominant status"],
        [
            [
                esc(row["label"]),
                f'<span class="num">{row["required_unit_count"]}</span>',
                f'<span class="num">{row["ready_unit_count"]}</span>',
                f'<span class="num">{row["partial_unit_count"]}</span>',
                f'<span class="num">{row["review_unit_count"]}</span>',
                f'<span class="num">{row["blocked_unit_count"]}</span>',
                esc(row["dominant_status"]),
            ]
            for row in lanes
        ],
    )
    domain_table = table(
        ["Domain", "Units", "Avg Priority", "Reception", "J/C", "Textual", "Layer Blocked"],
        [
            [
                esc(row["domain"]),
                f'<span class="num">{row["unit_count"]}</span>',
                f'<span class="num">{float(row["avg_adjudication_priority_score"]):.2f}</span>',
                f'<span class="num">{row["reception_sensitive_unit_count"]}</span>',
                f'<span class="num">{row["jewish_christian_unit_count"]}</span>',
                f'<span class="num">{row["textual_witness_unit_count"]}</span>',
                f'<span class="num">{row["layer_blocked_unit_count"]}</span>',
            ]
            for row in domains
        ],
    )
    role_table = table(
        ["Role", "Units", "Highest Priority Units", "Projected Review Rows"],
        [
            [
                esc(row["reviewer_role"]),
                f'<span class="num">{row["unit_count"]}</span>',
                f'<span class="num">{row["highest_priority_unit_count"]}</span>',
                f'<span class="num">{row["projected_human_review_rows"]}</span>',
            ]
            for row in sorted(
                roles,
                key=lambda item: int(item["projected_human_review_rows"]),
                reverse=True,
            )
        ],
    )
    unit_table = table(
        [
            "Unit",
            "Score",
            "Band",
            "Domains",
            "Frames",
            "Blocked",
            "Model Rows",
            "Layer Flags",
        ],
        [
            [
                f"<strong>{esc(row['ref'])}</strong><br><span>{esc(row['unit_id'])}</span>",
                f'<span class="num">{float(row["adjudication_priority_score"]):.2f}</span>',
                esc(row["adjudication_priority_band"]),
                esc("; ".join(row["domains"][:7])),
                esc("; ".join(row["required_frames"][:6])),
                f'<span class="num">{row["blocked_lane_count"]}</span>',
                (
                    f'<span class="num">{row["schema_valid_model_candidate_count"]}/'
                    f"{row['model_candidate_count']}</span>"
                ),
                esc("; ".join(row["layer_flags"])),
            ]
            for row in top_units
        ],
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Interpretive Adjudication Matrix</title>
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
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AlephTav Interpretive Adjudication Matrix</h1>
    <p class="lede">
      Unit-level routing for Hebrew source control, textual witnesses, ancient
      cultural context, Jewish reception, Christian reception, local model output,
      layer separation, and human signoff. This report measures adjudication
      pressure; it does not make interpretive decisions.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}. Not human signoff.</p>
  </header>
  <main>
    <section>
      <h2>Adjudication State</h2>
      {
        metric_cards(
            [
                (
                    "Expanded Units",
                    fmt_int(summary["unit_count"]),
                    "Contextual expanded units in scope.",
                ),
                (
                    "J/C Separation",
                    fmt_int(summary["jewish_christian_separation_unit_count"]),
                    "Units requiring separated Jewish and Christian lanes.",
                ),
                (
                    "Layer Blockers",
                    fmt_int(summary["units_with_layer_blockers"]),
                    "Units where paired model layers still fail separation.",
                ),
                (
                    "Failed Gates",
                    fmt_int(summary["failed_gate_count"]),
                    ", ".join(summary["failed_gates"]),
                ),
            ]
        )
    }
      <div class="warning">
        <strong>Critical reading:</strong> the matrix confirms that model output is
        not the hard part by itself. The blocking evidence is human signoff,
        layer separation, and explicit handling of reception and contextual claims.
      </div>
    </section>

    <section>
      <h2>Lane Status</h2>
      <div class="chart">{svg_lane_stack(lanes)}</div>
      {lane_table}
    </section>

    <section>
      <h2>Adjudication Gates</h2>
      {gate_table}
    </section>

    <section>
      <h2>Domain Pressure</h2>
      <div class="chart">{
        svg_horizontal_bars(
            domains,
            label_key="domain",
            value_key="avg_adjudication_priority_score",
            aria_label="Average adjudication priority by domain",
            color="#7c5b2f",
        )
    }</div>
      {domain_table}
    </section>

    <section>
      <h2>Reviewer Load</h2>
      {role_table}
    </section>

    <section>
      <h2>Top Units</h2>
      {unit_table}
    </section>
  </main>
</body>
</html>
"""


def flatten_unit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for row in rows:
        flattened.append(
            {
                "unit_id": row["unit_id"],
                "ref": row["ref"],
                "adjudication_priority_score": row["adjudication_priority_score"],
                "adjudication_priority_band": row["adjudication_priority_band"],
                "claim_risk_score": row["claim_risk_score"],
                "boundary_risk_score": row["boundary_risk_score"],
                "domains": row["domains"],
                "required_frames": row["required_frames"],
                "required_review_roles": row["required_review_roles"],
                "lane_statuses": row["lane_statuses"],
                "blocked_lane_count": row["blocked_lane_count"],
                "review_lane_count": row["review_lane_count"],
                "reception_sensitive": row["reception_sensitive"],
                "jewish_christian_separation_required": row["jewish_christian_separation_required"],
                "textual_witness_pressure": row["textual_witness_pressure"],
                "ancient_culture_pressure": row["ancient_culture_pressure"],
                "complete_expected_witness_set": row["complete_expected_witness_set"],
                "schema_valid_model_candidate_count": row["schema_valid_model_candidate_count"],
                "model_candidate_count": row["model_candidate_count"],
                "layer_pair_present": row["layer_pair_present"],
                "layer_exact_duplicate": row["layer_exact_duplicate"],
                "layer_flags": row["layer_flags"],
            }
        )
    return flattened


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate interpretive adjudication matrix.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--lane-csv-output", type=Path, default=DEFAULT_LANE_CSV_OUTPUT)
    parser.add_argument("--domain-csv-output", type=Path, default=DEFAULT_DOMAIN_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--role-csv-output", type=Path, default=DEFAULT_ROLE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    args = parse_args()
    report = build_report()
    json_output = resolve(args.json_output)
    unit_csv_output = resolve(args.unit_csv_output)
    lane_csv_output = resolve(args.lane_csv_output)
    domain_csv_output = resolve(args.domain_csv_output)
    gate_csv_output = resolve(args.gate_csv_output)
    role_csv_output = resolve(args.role_csv_output)
    html_output = resolve(args.html_output)
    write_json(json_output, report)
    write_csv(unit_csv_output, flatten_unit_rows(report["unit_rows"]))
    write_csv(lane_csv_output, report["lane_rows"])
    write_csv(domain_csv_output, report["domain_rows"])
    write_csv(gate_csv_output, report["gate_rows"])
    write_csv(role_csv_output, report["role_rows"])
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(render_html(report), encoding="utf-8")
    print(json_output)
    print(unit_csv_output)
    print(lane_csv_output)
    print(domain_csv_output)
    print(gate_csv_output)
    print(role_csv_output)
    print(html_output)


if __name__ == "__main__":
    main()
