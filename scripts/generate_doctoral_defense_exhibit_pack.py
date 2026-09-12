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

SOURCE_PATHS = {
    "source_ladder": REPORT_ROOT / "source_authority_ladder_matrix.json",
    "interpretive_control": REPORT_ROOT / "interpretive_tradition_control_matrix.json",
    "priority_dossier": REPORT_ROOT / "doctoral_priority_dossier_atlas.json",
    "unit_heatmap": REPORT_ROOT / "doctoral_unit_authority_heatmap.json",
    "context_integration": REPORT_ROOT / "doctoral_context_integration_matrix.json",
    "canonical_cross_reference": REPORT_ROOT / "canonical_cross_reference_atlas.json",
    "cultural_atlas": REPORT_ROOT / "cultural_historical_domain_atlas.json",
    "witness_divergence": REPORT_ROOT / "witness_divergence_report.json",
    "divine_name_policy": REPORT_ROOT / "divine_name_policy_report.json",
    "superscription_context": REPORT_ROOT / "superscription_context_report.json",
    "poetic_rhetorical": REPORT_ROOT / "poetic_rhetorical_pressure_atlas.json",
    "contextual_model_evidence": REPORT_ROOT / "contextual_real_model_evidence_matrix.json",
    "authority_critical_path": REPORT_ROOT / "authority_critical_path_report.json",
    "doctoral_synthesis": REPORT_ROOT / "doctoral_translation_synthesis.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "doctoral_defense_exhibit_pack.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "doctoral_defense_exhibit_units.csv"
DEFAULT_DIMENSION_CSV_OUTPUT = REPORT_ROOT / "doctoral_defense_exhibit_dimensions.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "doctoral_defense_exhibit_pack.html"
CRITICAL_EXHIBIT_SCORE = 1200.0

AUTHORITY_POLICY = (
    "The defense exhibit pack is a visual evidence index for scholarly review. It joins "
    "existing source, Hebrew, witness, culture, reception, model, and signoff reports, "
    "but it does not approve sources, decide interpretation, authorize model training, "
    "or change canonical translation text."
)


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


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "yes", "1"}
    return bool(value)


def listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        if "; " in value:
            return [part.strip() for part in value.split("; ") if part.strip()]
        if value:
            return [value]
    return []


def list_join(values: list[Any], limit: int | None = None) -> str:
    if limit is not None:
        values = values[:limit]
    return "; ".join(str(value) for value in values if str(value))


def by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key)}


def model_evidence_by_unit(data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in data["contextual_model_evidence"].get("attempt_rows", []):
        grouped[str(row.get("unit_id", ""))].append(row)
    result: dict[str, dict[str, Any]] = {}
    for unit_id, rows in grouped.items():
        valid = [row for row in rows if row.get("schema_valid")]
        clean = [row for row in rows if row.get("clean_source_anchored")]
        result[unit_id] = {
            "model_attempt_count": len(rows),
            "schema_valid_model_attempt_count": len(valid),
            "clean_source_anchored_attempt_count": len(clean),
            "source_anchor_issue_count": sum(
                int(row.get("source_anchor_issue_count") or 0) for row in rows
            ),
            "model_profile_ids": sorted({str(row.get("model_profile_id", "")) for row in rows}),
            "model_lanes": sorted({str(row.get("lane_label", "")) for row in rows}),
            "best_alignment_score_0_5": max(
                [as_float(row.get("mean_alignment_score_0_5")) for row in rows] or [0.0]
            ),
            "best_translation_basis_score_0_5": max(
                [as_float(row.get("mean_translation_basis_score_0_5")) for row in rows] or [0.0]
            ),
        }
    return result


def candidate_unit_ids(data: dict[str, dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for artifact_key, row_key, limit in [
        ("source_ladder", "unit_rows", 35),
        ("interpretive_control", "unit_rows", 35),
        ("priority_dossier", "unit_rows", 50),
        ("unit_heatmap", "queue_rows", 30),
        ("context_integration", "unit_rows", 35),
    ]:
        for row in data[artifact_key].get(row_key, [])[:limit]:
            unit_id = str(row.get("unit_id", ""))
            if unit_id and unit_id not in ids:
                ids.append(unit_id)
    return ids


def row_maps(data: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "source": by_key(data["source_ladder"].get("unit_rows", []), "unit_id"),
        "control": by_key(data["interpretive_control"].get("unit_rows", []), "unit_id"),
        "dossier": by_key(data["priority_dossier"].get("unit_rows", []), "unit_id"),
        "heatmap": by_key(data["unit_heatmap"].get("unit_rows", []), "unit_id"),
        "heatmap_queue": by_key(data["unit_heatmap"].get("queue_rows", []), "unit_id"),
        "integration": by_key(data["context_integration"].get("unit_rows", []), "unit_id"),
        "cross_reference": by_key(
            data["canonical_cross_reference"].get("unit_rows", []), "unit_id"
        ),
        "culture": by_key(data["cultural_atlas"].get("unit_rows", []), "unit_id"),
        "witness": by_key(data["witness_divergence"].get("unit_rows", []), "unit_id"),
        "divine": by_key(data["divine_name_policy"].get("unit_rows", []), "unit_id"),
        "superscription": by_key(data["superscription_context"].get("unit_rows", []), "unit_id"),
        "poetic": by_key(data["poetic_rhetorical"].get("unit_rows", []), "unit_id"),
    }


def evidence_score(
    source: dict[str, Any],
    control: dict[str, Any],
    dossier: dict[str, Any],
    heatmap: dict[str, Any],
    integration: dict[str, Any],
    witness: dict[str, Any],
    model: dict[str, Any],
) -> float:
    authority_score = as_float(
        heatmap.get("unit_authority_score_pct", dossier.get("unit_authority_score_pct", 0.0))
    )
    return round(
        as_float(source.get("source_authority_gap_score")) * 0.55
        + as_float(control.get("interpretive_control_score")) * 0.45
        + as_float(dossier.get("doctoral_dossier_priority_score")) * 0.45
        + as_float(integration.get("integration_pressure_score")) * 0.70
        + as_float(heatmap.get("gap_priority_score")) * 0.75
        + as_float(witness.get("mean_english_witness_divergence_pct")) * 0.80
        + max(0.0, 100.0 - authority_score) * 1.30
        + (35 if not int(source.get("source_approval_count") or 0) else 0)
        + (30 if not int(source.get("completed_review_row_count") or 0) else 0)
        + (20 if not int(model.get("clean_source_anchored_attempt_count") or 0) else 0),
        2,
    )


def build_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    maps = row_maps(data)
    model_map = model_evidence_by_unit(data)
    rows: list[dict[str, Any]] = []
    for unit_id in candidate_unit_ids(data):
        source = maps["source"].get(unit_id, {})
        control = maps["control"].get(unit_id, {})
        dossier = maps["dossier"].get(unit_id, {})
        heatmap = maps["heatmap"].get(unit_id, maps["heatmap_queue"].get(unit_id, {}))
        integration = maps["integration"].get(unit_id, {})
        cross_ref = maps["cross_reference"].get(unit_id, {})
        culture = maps["culture"].get(unit_id, {})
        witness = maps["witness"].get(unit_id, {})
        divine = maps["divine"].get(unit_id, {})
        superscription = maps["superscription"].get(unit_id, {})
        poetic = maps["poetic"].get(unit_id, {})
        model = model_map.get(unit_id, {})
        ref = (
            source.get("ref")
            or control.get("ref")
            or dossier.get("ref")
            or integration.get("ref")
            or heatmap.get("ref")
            or unit_id
        )
        source_hebrew = (
            source.get("source_hebrew")
            or control.get("source_hebrew")
            or dossier.get("source_hebrew")
            or integration.get("source_hebrew")
            or cross_ref.get("source_hebrew")
            or poetic.get("source_hebrew")
            or ""
        )
        required_roles = sorted(
            set(listify(source.get("required_review_roles")))
            | set(listify(integration.get("required_review_roles")))
            | set(listify(dossier.get("required_review_roles")))
        )
        weakest_lanes = listify(
            heatmap.get("weakest_required_lanes", dossier.get("weakest_required_lanes", []))
        )
        row = {
            "rank": 0,
            "unit_id": unit_id,
            "ref": ref,
            "source_hebrew": source_hebrew,
            "defense_exhibit_score": evidence_score(
                source, control, dossier, heatmap, integration, witness, model
            ),
            "unit_authority_score_pct": as_float(
                heatmap.get("unit_authority_score_pct", dossier.get("unit_authority_score_pct"))
            ),
            "source_authority_gap_score": as_float(source.get("source_authority_gap_score")),
            "source_authority_readiness_pct": as_float(
                source.get("source_authority_readiness_pct")
            ),
            "source_ladder_stage": source.get("evidence_ladder_stage", ""),
            "chief_source_blocker": source.get("chief_blocker", ""),
            "source_approval_count": int(source.get("source_approval_count") or 0),
            "packet_review_row_count": int(
                source.get(
                    "packet_review_row_count",
                    dossier.get(
                        "packet_review_row_count",
                        heatmap.get("packet_review_row_count", 0),
                    ),
                )
                or 0
            ),
            "completed_review_row_count": int(source.get("completed_review_row_count") or 0),
            "interpretive_control_score": as_float(control.get("interpretive_control_score")),
            "translation_text_forbidden_reception_claim": boolish(
                control.get("translation_text_forbidden_reception_claim")
            ),
            "reception_sensitive": boolish(
                control.get("reception_sensitive", integration.get("reception_sensitive"))
            ),
            "jewish_christian_separation_required": boolish(
                control.get(
                    "jewish_christian_separation_required",
                    integration.get("jewish_christian_separation"),
                )
            ),
            "academic_comparison_required": boolish(
                control.get(
                    "has_academic_comparison_frame",
                    integration.get("academic_comparison_required"),
                )
            ),
            "ancient_culture_pressure": boolish(
                control.get("ancient_culture_pressure", integration.get("ancient_culture_pressure"))
            ),
            "textual_witness_pressure": boolish(
                control.get("textual_witness_pressure", integration.get("textual_witness_pressure"))
            ),
            "theology_pressure": boolish(control.get("theology_pressure")),
            "integration_pressure_score": as_float(integration.get("integration_pressure_score")),
            "active_lens_count": int(integration.get("active_lens_count") or 0),
            "active_lens_labels": list_join(listify(integration.get("active_lens_labels")), 14),
            "cross_reference_anchor_token_count": int(
                cross_ref.get(
                    "anchor_token_count",
                    integration.get("canonical_anchor_token_count", 0),
                )
                or 0
            ),
            "cross_reference_three_division": boolish(
                cross_ref.get(
                    "has_three_division_evidence",
                    integration.get("whole_tanakh_three_division"),
                )
            ),
            "top_anchor_forms": list_join(
                listify(dossier.get("top_anchor_form_labels"))
                or listify(cross_ref.get("top_anchor_forms"))
                or listify(integration.get("canonical_top_anchor_forms")),
                8,
            ),
            "cultural_domain_count": int(
                culture.get("domain_count", integration.get("cultural_domain_count", 0)) or 0
            ),
            "cultural_domain_labels": list_join(
                listify(culture.get("domain_labels"))
                or listify(integration.get("cultural_domain_labels")),
                8,
            ),
            "witness_divergence_pct": as_float(
                witness.get(
                    "mean_english_witness_divergence_pct",
                    integration.get("witness_divergence_pct"),
                )
            ),
            "witness_marker_flags": list_join(
                listify(witness.get("marker_flags"))
                or listify(integration.get("witness_marker_flags")),
                8,
            ),
            "divine_name_categories": list_join(
                listify(divine.get("categories"))
                or listify(integration.get("divine_name_categories")),
                6,
            ),
            "superscription_categories": list_join(
                listify(superscription.get("categories"))
                or listify(integration.get("superscription_categories")),
                6,
            ),
            "poetic_pressure_band": poetic.get(
                "pressure_band", integration.get("poetic_pressure_band", "")
            ),
            "poetic_feature_flags": list_join(
                listify(poetic.get("feature_flags"))
                or listify(integration.get("poetic_feature_flags")),
                8,
            ),
            "model_attempt_count": int(model.get("model_attempt_count") or 0),
            "schema_valid_model_attempt_count": int(
                model.get("schema_valid_model_attempt_count") or 0
            ),
            "clean_source_anchored_attempt_count": int(
                model.get("clean_source_anchored_attempt_count") or 0
            ),
            "model_source_anchor_issue_count": int(model.get("source_anchor_issue_count") or 0),
            "model_profile_ids": list_join(model.get("model_profile_ids", []), 4),
            "best_model_alignment_score_0_5": as_float(model.get("best_alignment_score_0_5")),
            "best_model_translation_basis_score_0_5": as_float(
                model.get("best_translation_basis_score_0_5")
            ),
            "required_review_roles": list_join(required_roles),
            "weakest_required_lanes": list_join(weakest_lanes, 8),
            "packet_families": source.get(
                "packet_families", list_join(dossier.get("packet_families", []), 12)
            ),
            "candidate_source_ids": source.get("candidate_source_ids", ""),
            "claim_controls": source.get("claim_controls", control.get("claim_controls", "")),
            "kjv_excerpt": witness.get("kjv_excerpt", dossier.get("kjv_excerpt", "")),
            "asv_excerpt": witness.get("asv_excerpt", dossier.get("asv_excerpt", "")),
            "web_excerpt": witness.get("web_excerpt", dossier.get("web_excerpt", "")),
            "exhibit_thesis": (
                "High-value defense exhibit: pressure is cross-domain, but authority remains "
                "blocked until source approvals, packet reviews, and release signoff exist."
            ),
            "next_action": source.get("next_action", dossier.get("next_action", "")),
            "authority_boundary": AUTHORITY_POLICY,
        }
        rows.append(row)
    rows.sort(key=lambda row: (-float(row["defense_exhibit_score"]), row["ref"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_dimension_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dimensions = [
        ("source_unapproved", "Source approval missing", "source_approval_count", 0),
        ("review_unsigned", "Packet review unsigned", "completed_review_row_count", 0),
        (
            "whole_tanakh",
            "Whole-Tanakh three-division context",
            "cross_reference_three_division",
            True,
        ),
        ("ancient_culture", "Ancient culture pressure", "ancient_culture_pressure", True),
        ("textual_witness", "Textual witness pressure", "textual_witness_pressure", True),
        ("reception", "Reception-sensitive", "reception_sensitive", True),
        (
            "jewish_christian",
            "Jewish/Christian separation",
            "jewish_christian_separation_required",
            True,
        ),
        ("academic", "Academic comparison", "academic_comparison_required", True),
        ("theology", "Theology pressure", "theology_pressure", True),
        (
            "model_missing",
            "No clean source-anchored model attempt",
            "clean_source_anchored_attempt_count",
            0,
        ),
    ]
    rows = []
    for dimension_id, label, key, target in dimensions:
        if isinstance(target, bool):
            matching = [row for row in unit_rows if boolish(row.get(key)) is target]
        else:
            matching = [row for row in unit_rows if int(row.get(key) or 0) == target]
        top = matching[0] if matching else {}
        rows.append(
            {
                "dimension_id": dimension_id,
                "label": label,
                "unit_count": len(matching),
                "unit_pct": pct(len(matching), len(unit_rows)),
                "top_ref": top.get("ref", ""),
                "top_score": top.get("defense_exhibit_score", 0.0),
            }
        )
    return rows


def build_role_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    role_units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        for role in listify(row.get("required_review_roles")):
            role_units[role].append(row)
    rows = []
    for role, rows_for_role in role_units.items():
        top = rows_for_role[0]
        rows.append(
            {
                "reviewer_role": role,
                "unit_count": len(rows_for_role),
                "critical_unit_count": sum(
                    1
                    for row in rows_for_role
                    if row["defense_exhibit_score"] >= CRITICAL_EXHIBIT_SCORE
                ),
                "mean_score": mean([float(row["defense_exhibit_score"]) for row in rows_for_role]),
                "top_ref": top["ref"],
                "top_score": top["defense_exhibit_score"],
            }
        )
    rows.sort(key=lambda row: (-int(row["unit_count"]), row["reviewer_role"]))
    return rows


def build_blocker_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocker_counts = Counter(
        row["chief_source_blocker"] for row in unit_rows if row["chief_source_blocker"]
    )
    lane_counts: Counter[str] = Counter()
    for row in unit_rows:
        lane_counts.update(listify(row.get("weakest_required_lanes")))
    rows = [
        {
            "blocker_type": "source_ladder",
            "blocker": blocker,
            "unit_count": count,
            "unit_pct": pct(count, len(unit_rows)),
        }
        for blocker, count in blocker_counts.most_common()
    ]
    rows.extend(
        {
            "blocker_type": "weakest_lane",
            "blocker": lane,
            "unit_count": count,
            "unit_pct": pct(count, len(unit_rows)),
        }
        for lane, count in lane_counts.most_common()
    )
    return rows


def build_summary(
    unit_rows: list[dict[str, Any]], data: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    top = unit_rows[0] if unit_rows else {}
    model_summary = data["contextual_model_evidence"]["summary"]
    authority = data["authority_critical_path"]["summary"]
    return {
        "exhibit_unit_count": len(unit_rows),
        "critical_exhibit_unit_count": sum(
            1 for row in unit_rows if row["defense_exhibit_score"] >= CRITICAL_EXHIBIT_SCORE
        ),
        "mean_defense_exhibit_score": mean(
            [float(row["defense_exhibit_score"]) for row in unit_rows]
        ),
        "mean_unit_authority_score_pct": mean(
            [float(row["unit_authority_score_pct"]) for row in unit_rows]
        ),
        "source_unapproved_unit_count": sum(
            1 for row in unit_rows if not row["source_approval_count"]
        ),
        "unsigned_review_unit_count": sum(
            1 for row in unit_rows if not row["completed_review_row_count"]
        ),
        "jewish_christian_separation_unit_count": sum(
            1 for row in unit_rows if row["jewish_christian_separation_required"]
        ),
        "ancient_culture_pressure_unit_count": sum(
            1 for row in unit_rows if row["ancient_culture_pressure"]
        ),
        "textual_witness_pressure_unit_count": sum(
            1 for row in unit_rows if row["textual_witness_pressure"]
        ),
        "whole_tanakh_three_division_unit_count": sum(
            1 for row in unit_rows if row["cross_reference_three_division"]
        ),
        "clean_model_attempt_unit_count": sum(
            1 for row in unit_rows if row["clean_source_anchored_attempt_count"]
        ),
        "model_valid_task_coverage_pct": model_summary["valid_model_task_coverage_pct"],
        "authority_blocked_phase_count": authority["blocked_phase_count"],
        "authority_blocked_gate_count": authority["blocked_gate_row_count"],
        "review_completion_pct": authority["review_completion_pct"],
        "top_exhibit_unit": top.get("unit_id", ""),
        "top_exhibit_ref": top.get("ref", ""),
        "top_exhibit_score": top.get("defense_exhibit_score", 0.0),
        "top_exhibit_authority_pct": top.get("unit_authority_score_pct", 0.0),
        "authority_verdict": (
            "The defense exhibits identify the strongest research pressure points, but every "
            "exhibit remains non-authoritative until source approval, review signoff, model "
            "coverage, and release authority are complete."
        ),
    }


def build_visual_data(
    unit_rows: list[dict[str, Any]],
    dimension_rows: list[dict[str, Any]],
    role_rows: list[dict[str, Any]],
    blocker_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "top_exhibit_rows": [
            {"label": row["ref"], "value": row["defense_exhibit_score"]} for row in unit_rows[:20]
        ],
        "authority_gap_rows": [
            {"label": row["ref"], "value": 100 - row["unit_authority_score_pct"]}
            for row in unit_rows[:20]
        ],
        "source_gap_rows": [
            {"label": row["ref"], "value": row["source_authority_gap_score"]}
            for row in unit_rows[:20]
        ],
        "dimension_rows": [
            {"label": row["label"], "value": row["unit_count"]} for row in dimension_rows
        ],
        "role_rows": [
            {"label": row["reviewer_role"], "value": row["unit_count"]} for row in role_rows
        ],
        "blocker_rows": [
            {"label": row["blocker"], "value": row["unit_count"]} for row in blocker_rows[:14]
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    unit_rows = build_unit_rows(data)
    dimension_rows = build_dimension_rows(unit_rows)
    role_rows = build_role_rows(unit_rows)
    blocker_rows = build_blocker_rows(unit_rows)
    summary = build_summary(unit_rows, data)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "doctoral defense exhibit pack generated; not authority signoff",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": AUTHORITY_POLICY,
        "summary": summary,
        "unit_rows": unit_rows,
        "dimension_rows": dimension_rows,
        "role_rows": role_rows,
        "blocker_rows": blocker_rows,
        "visual_data": build_visual_data(unit_rows, dimension_rows, role_rows, blocker_rows),
    }


def metric_cards(cards: list[tuple[str, Any, str]]) -> str:
    return "\n".join(
        f"""
        <article class="metric">
          <div class="metric-label">{esc(label)}</div>
          <div class="metric-value">{esc(value)}</div>
          <p>{esc(detail)}</p>
        </article>
        """
        for label, value, detail in cards
    )


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    color: str = "#2f6f73",
    limit: int = 18,
) -> str:
    rows = rows[:limit]
    if not rows:
        return "<p>No rows.</p>"
    max_value = max(float(row["value"]) for row in rows) or 1.0
    width = 940
    row_height = 28
    label_width = 330
    bar_width = width - label_width - 90
    height = 34 + len(rows) * row_height
    parts = [(f'<svg role="img" aria-label="horizontal bar chart" viewBox="0 0 {width} {height}">')]
    for index, row in enumerate(rows):
        y = 24 + index * row_height
        value = float(row["value"])
        bar = value / max_value * bar_width
        parts.append(
            f'<text x="0" y="{y + 14}" font-size="12" fill="#263238">{esc(row["label"])}</text>'
        )
        parts.append(
            f'<rect x="{label_width}" y="{y}" width="{bar:.1f}" height="18" '
            f'rx="3" fill="{color}"></rect>'
        )
        parts.append(
            f'<text x="{label_width + bar + 8:.1f}" y="{y + 14}" '
            f'font-size="12" fill="#263238">{value:.2f}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def evidence_badges(row: dict[str, Any]) -> str:
    badges = [
        ("Whole Tanakh", row["cross_reference_three_division"]),
        ("Culture", row["ancient_culture_pressure"]),
        ("Witness", row["textual_witness_pressure"]),
        ("Reception", row["reception_sensitive"]),
        ("J/C Split", row["jewish_christian_separation_required"]),
        ("Academic", row["academic_comparison_required"]),
        ("Theology", row["theology_pressure"]),
        ("Clean Model", bool(row["clean_source_anchored_attempt_count"])),
    ]
    return "".join(
        f'<span class="badge {"on" if active else "off"}">{esc(label)}</span>'
        for label, active in badges
    )


def render_exhibit_cards(rows: list[dict[str, Any]], limit: int = 8) -> str:
    cards = []
    for row in rows[:limit]:
        cards.append(
            f"""
            <article class="exhibit">
              <div class="exhibit-top">
                <h3>{esc(row["rank"])}. {esc(row["ref"])}</h3>
                <div class="score">{float(row["defense_exhibit_score"]):.2f}</div>
              </div>
              <p class="hebrew" dir="rtl" lang="he">{esc(row["source_hebrew"])}</p>
              <div class="badges">{evidence_badges(row)}</div>
              <div class="facts">
                <p><strong>Authority:</strong> {float(row["unit_authority_score_pct"]):.2f}%,
                source stage {esc(row["source_ladder_stage"])}, blocker
                {esc(row["chief_source_blocker"])}.</p>
                <p><strong>Context:</strong> {esc(row["active_lens_labels"])}</p>
                <p><strong>Anchors:</strong> {esc(row["top_anchor_forms"])}</p>
                <p><strong>Culture:</strong> {esc(row["cultural_domain_labels"])}</p>
                <p><strong>Witnesses:</strong> divergence
                {float(row["witness_divergence_pct"]):.2f}%; {esc(row["witness_marker_flags"])}</p>
                <p><strong>Reception:</strong> frames require separation:
                {esc(row["translation_text_forbidden_reception_claim"])} forbidden-in-text flag.</p>
                <p><strong>Model:</strong> {row["clean_source_anchored_attempt_count"]} clean
                source-anchored attempts from {row["model_attempt_count"]} attempts;
                {row["model_source_anchor_issue_count"]} source-anchor issues.</p>
                <p><strong>Review:</strong> {row["packet_review_row_count"]} packet rows,
                {row["completed_review_row_count"]} completed; roles
                {esc(row["required_review_roles"])}.</p>
              </div>
              <p class="boundary">{esc(row["exhibit_thesis"])}</p>
            </article>
            """
        )
    return "\n".join(cards)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    unit_rows = [
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
            row["witness_divergence_pct"],
            row["clean_source_anchored_attempt_count"],
            row["required_review_roles"],
        ]
        for row in report["unit_rows"][:30]
    ]
    dimension_rows = [
        [
            row["label"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["top_ref"],
            f"{row['top_score']:.2f}",
        ]
        for row in report["dimension_rows"]
    ]
    role_rows = [
        [
            row["reviewer_role"],
            row["unit_count"],
            row["critical_unit_count"],
            f"{row['mean_score']:.2f}",
            row["top_ref"],
            f"{row['top_score']:.2f}",
        ]
        for row in report["role_rows"]
    ]
    blocker_rows = [
        [row["blocker_type"], row["blocker"], row["unit_count"], f"{row['unit_pct']:.2f}%"]
        for row in report["blocker_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Doctoral Defense Exhibit Pack</title>
  <style>
    body {{
      margin: 0;
      background: #f6f4ee;
      color: #263238;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }}
    header, main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    header {{ padding-top: 42px; }}
    h1 {{ margin: 0 0 8px; font-size: 34px; letter-spacing: 0; }}
    h2 {{ margin-top: 34px; font-size: 22px; letter-spacing: 0; }}
    h3 {{ margin: 0; font-size: 18px; letter-spacing: 0; }}
    p {{ line-height: 1.5; }}
    .warning {{
      border-left: 5px solid #9b3d3d;
      background: #fff8f2;
      padding: 14px 16px;
      margin: 18px 0;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 18px 0;
    }}
    .metric, .exhibit, .chart {{
      border: 1px solid #d7d1c2;
      background: #fff;
      border-radius: 8px;
    }}
    .metric {{ padding: 14px; }}
    .metric-label {{ font-size: 12px; text-transform: uppercase; color: #607d8b; }}
    .metric-value {{ font-size: 28px; font-weight: 700; margin-top: 6px; }}
    .metric p {{ margin: 6px 0 0; font-size: 13px; }}
    .chart {{ overflow-x: auto; padding: 12px; margin: 14px 0; }}
    .exhibit {{ padding: 16px; margin: 14px 0; }}
    .exhibit-top {{ display: flex; justify-content: space-between; gap: 18px; }}
    .score {{ font-size: 24px; font-weight: 700; color: #9b3d3d; }}
    .hebrew {{ font-size: 24px; margin: 12px 0; line-height: 1.8; }}
    .badges {{ display: flex; gap: 6px; flex-wrap: wrap; margin: 10px 0; }}
    .badge {{
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 12px;
      border: 1px solid #d7d1c2;
    }}
    .badge.on {{ background: #e6f0ed; color: #225b5f; }}
    .badge.off {{ background: #f3eee4; color: #7a6a53; }}
    .facts p {{ margin: 6px 0; }}
    .boundary {{ color: #6c4f2a; font-weight: 600; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 14px 0 24px;
      background: #fff;
      border: 1px solid #d7d1c2;
      font-size: 13px;
    }}
    th, td {{ border-bottom: 1px solid #e5dfd2; padding: 8px; vertical-align: top; }}
    th {{ text-align: left; background: #eee7d7; }}
    td {{ max-width: 340px; }}
  </style>
</head>
<body>
<header>
  <h1>Doctoral Defense Exhibit Pack</h1>
  <p>
    Committee-style exhibits for the highest-pressure Psalms translation units,
    joining Hebrew source, whole-Tanakh context, ancient culture, witnesses,
    Jewish/Christian reception, model evidence, and review blockers.
  </p>
  <div class="warning">{esc(report["authority_policy"])}</div>
  <section class="metrics">
    {
        metric_cards(
            [
                (
                    "Exhibits",
                    summary["exhibit_unit_count"],
                    f"{summary['critical_exhibit_unit_count']} critical exhibit units.",
                ),
                (
                    "Mean Score",
                    f"{summary['mean_defense_exhibit_score']:.2f}",
                    "Composite pressure score for defense ordering.",
                ),
                (
                    "Mean Authority",
                    f"{summary['mean_unit_authority_score_pct']:.2f}%",
                    "Current unit authority score across exhibit set.",
                ),
                (
                    "Source Approval",
                    summary["source_unapproved_unit_count"],
                    "Exhibit units still lacking source approval.",
                ),
                (
                    "Review Signoff",
                    summary["unsigned_review_unit_count"],
                    "Exhibit units with no completed packet review.",
                ),
                (
                    "J/C Split",
                    summary["jewish_christian_separation_unit_count"],
                    "Exhibit units requiring separated reception lanes.",
                ),
                (
                    "Clean Model",
                    summary["clean_model_attempt_unit_count"],
                    "Exhibit units with clean source-anchored model evidence.",
                ),
                (
                    "Top Exhibit",
                    summary["top_exhibit_ref"],
                    f"{float(summary['top_exhibit_score']):.2f}.",
                ),
            ]
        )
    }
  </section>
</header>
<main>
  <section>
    <h2>Exhibit Frontier</h2>
    <div class="chart">{svg_horizontal_bars(visual["top_exhibit_rows"], color="#9b3d3d")}</div>
    <div class="chart">{svg_horizontal_bars(visual["authority_gap_rows"], color="#7c5b2f")}</div>
    <div class="chart">{svg_horizontal_bars(visual["dimension_rows"], color="#2f6f73")}</div>
    {render_exhibit_cards(report["unit_rows"])}
  </section>
  <section>
    <h2>Exhibit Table</h2>
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
                "Done",
                "Witness %",
                "Clean Model",
                "Roles",
            ],
            unit_rows,
        )
    }
  </section>
  <section>
    <h2>Dimensions, Roles, And Blockers</h2>
    <div class="chart">{svg_horizontal_bars(visual["role_rows"], color="#2f6f73")}</div>
    <div class="chart">{svg_horizontal_bars(visual["blocker_rows"], color="#9b3d3d")}</div>
    {table(["Dimension", "Units", "Pct", "Top Ref", "Top Score"], dimension_rows)}
    {table(["Role", "Units", "Critical", "Mean Score", "Top Ref", "Top Score"], role_rows)}
    {table(["Type", "Blocker", "Units", "Pct"], blocker_rows)}
  </section>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate doctoral defense exhibit pack.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--dimension-csv-output", type=Path, default=DEFAULT_DIMENSION_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.dimension_csv_output, report["dimension_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.dimension_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
