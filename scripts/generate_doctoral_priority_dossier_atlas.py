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
CONTENT_ROOT = ROOT / "content" / "psalms"
REPORT_ROOT = ROOT / "reports" / "research"

SOURCE_PATHS = {
    "priority_dossiers": REPORT_ROOT / "priority_unit_dossiers.json",
    "casebook": REPORT_ROOT / "scholarly_casebook.json",
    "unit_heatmap": REPORT_ROOT / "doctoral_unit_authority_heatmap.json",
    "review_workbook": REPORT_ROOT / "contextual_review_signoff_workbook.json",
    "reception_divergence": REPORT_ROOT / "reception_divergence_atlas.json",
    "canonical_cross_reference": REPORT_ROOT / "canonical_cross_reference_atlas.json",
    "cultural_atlas": REPORT_ROOT / "cultural_historical_domain_atlas.json",
    "witness_divergence": REPORT_ROOT / "witness_divergence_report.json",
    "divine_name_policy": REPORT_ROOT / "divine_name_policy_report.json",
    "superscription_context": REPORT_ROOT / "superscription_context_report.json",
    "claim_matrix": REPORT_ROOT / "translation_claim_evidence_matrix.json",
    "adjudication": REPORT_ROOT / "interpretive_adjudication_matrix.json",
    "source_packets": REPORT_ROOT / "contextual_source_packet_roadmap.json",
    "model_gap": REPORT_ROOT / "model_evidence_gap_report.json",
    "quality_triage": REPORT_ROOT / "model_output_quality_triage.json",
    "layer_consistency": REPORT_ROOT / "layer_consistency_report.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "doctoral_priority_dossier_atlas.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "doctoral_priority_dossier_atlas_units.csv"
DEFAULT_ROLE_CSV_OUTPUT = REPORT_ROOT / "doctoral_priority_dossier_atlas_roles.csv"
DEFAULT_LANE_CSV_OUTPUT = REPORT_ROOT / "doctoral_priority_dossier_atlas_lanes.csv"
DEFAULT_DOMAIN_CSV_OUTPUT = REPORT_ROOT / "doctoral_priority_dossier_atlas_domains.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "doctoral_priority_dossier_atlas.html"

TARGET_UNIT_COUNT = 50
MAX_TABLE_UNITS = 30


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
    return round(float(part) / float(total) * 100.0, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def lookup(rows: list[dict[str, Any]], key: str = "unit_id") -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if key in row}


def unit_content(unit_id: str) -> dict[str, Any]:
    psalm_id = unit_id.split(".", 1)[0]
    path = CONTENT_ROOT / psalm_id / f"{unit_id}.json"
    if not path.exists():
        return {}
    return load_json(path)


def token_summary(unit: dict[str, Any]) -> dict[str, Any]:
    tokens = unit.get("tokens", [])
    missing: Counter[str] = Counter()
    pos_counts: Counter[str] = Counter()
    for token in tokens:
        pos_counts[str(token.get("part_of_speech") or "unknown")] += 1
        for gap in token.get("missing_enrichments", []):
            missing[str(gap)] += 1
    token_count = len(tokens)
    lemma_count = sum(1 for token in tokens if token.get("lemma"))
    strong_count = sum(1 for token in tokens if token.get("strong"))
    return {
        "token_count": token_count,
        "lemma_coverage_pct": pct(lemma_count, token_count),
        "strong_coverage_pct": pct(strong_count, token_count),
        "divine_name_token_count": sum(1 for token in tokens if token.get("divine_name")),
        "construct_state_token_count": sum(
            1
            for token in tokens
            if token.get("construct_state")
            or token.get("compiler_features", {}).get("construct_state")
        ),
        "suffix_pronoun_token_count": sum(
            1
            for token in tokens
            if token.get("suffix_pronoun")
            or token.get("compiler_features", {}).get("suffix_pronoun")
        ),
        "missing_enrichment_counts": dict(missing.most_common()),
        "part_of_speech_counts": dict(pos_counts.most_common()),
    }


def collect_candidate_units(data: dict[str, dict[str, Any]]) -> set[str]:
    unit_ids: set[str] = set()
    for row in data["priority_dossiers"].get("dossiers", [])[:40]:
        unit_ids.add(str(row["unit_id"]))
    for row in data["unit_heatmap"].get("queue_rows", [])[:40]:
        unit_ids.add(str(row["unit_id"]))
    for row in data["reception_divergence"].get("unit_rows", [])[:30]:
        unit_ids.add(str(row["unit_id"]))
    for row in data["canonical_cross_reference"].get("unit_rows", [])[:30]:
        unit_ids.add(str(row["unit_id"]))
    for row in data["cultural_atlas"].get("unit_rows", [])[:30]:
        unit_ids.add(str(row["unit_id"]))
    for row in data["witness_divergence"].get("priority_rows", [])[:30]:
        unit_ids.add(str(row["unit_id"]))
    for row in data["divine_name_policy"].get("unit_rows", [])[:30]:
        unit_ids.add(str(row["unit_id"]))
    for row in data["superscription_context"].get("unit_rows", [])[:30]:
        unit_ids.add(str(row["unit_id"]))
    for row in data["casebook"].get("cases", [])[:20]:
        unit_ids.add(str(row["unit_id"]))
    return unit_ids


def normalized_score(value: Any, max_value: float) -> float:
    if not max_value:
        return 0.0
    return min(1.0, max(0.0, float(value or 0) / max_value))


def build_unit_row(unit_id: str, data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    priority = lookup(data["priority_dossiers"].get("dossiers", []))
    heatmap = lookup(data["unit_heatmap"].get("unit_rows", []))
    heatmap_queue = lookup(data["unit_heatmap"].get("queue_rows", []))
    review = lookup(data["review_workbook"].get("unit_rows", []))
    reception = lookup(data["reception_divergence"].get("unit_rows", []))
    cross_ref = lookup(data["canonical_cross_reference"].get("unit_rows", []))
    cultural = lookup(data["cultural_atlas"].get("unit_rows", []))
    witness = lookup(data["witness_divergence"].get("unit_rows", []))
    divine = lookup(data["divine_name_policy"].get("unit_rows", []))
    superscription = lookup(data["superscription_context"].get("unit_rows", []))
    claim = lookup(data["claim_matrix"].get("unit_claim_rows", []))
    adjudication = lookup(data["adjudication"].get("unit_rows", []))
    packets = lookup(data["source_packets"].get("unit_rows", []))
    casebook = lookup(data["casebook"].get("cases", []))
    model_gap = lookup(data["model_gap"].get("unit_gap_rows", []))
    quality = lookup(data["quality_triage"].get("candidate_rows", []), key="unit_id")
    layer = lookup(data["layer_consistency"].get("pair_rows", []), key="unit_id")

    dossier = priority.get(unit_id, {})
    heat = heatmap.get(unit_id, {})
    queue = heatmap_queue.get(unit_id, {})
    review_row = review.get(unit_id, {})
    reception_row = reception.get(unit_id, {})
    cross = cross_ref.get(unit_id, {})
    cultural_row = cultural.get(unit_id, {})
    witness_row = witness.get(unit_id, {})
    divine_row = divine.get(unit_id, {})
    super_row = superscription.get(unit_id, {})
    claim_row = claim.get(unit_id, {})
    adjudication_row = adjudication.get(unit_id, {})
    packet_row = packets.get(unit_id, {})
    case = casebook.get(unit_id, {})
    model_row = model_gap.get(unit_id, {})
    quality_row = quality.get(unit_id, {})
    layer_row = layer.get(unit_id, {})
    content = unit_content(unit_id)

    score = 0.0
    score += normalized_score(dossier.get("priority", {}).get("score"), 60) * 90
    score += normalized_score(queue.get("gap_priority_score"), 200) * 80
    score += normalized_score(reception_row.get("reception_divergence_priority_score"), 340) * 80
    score += normalized_score(cross.get("priority_score"), 390) * 70
    score += normalized_score(cultural_row.get("priority_score"), 220) * 55
    score += normalized_score(witness_row.get("priority_score"), 170) * 45
    score += normalized_score(claim_row.get("claim_risk_score"), 230) * 45
    score += normalized_score(packet_row.get("packet_priority_score"), 480) * 45
    score += float(heat.get("blocking_lane_count") or queue.get("blocking_lane_count") or 0) * 12
    score += 20 if reception_row.get("jewish_christian_separation_required") else 0
    score += 16 if bool(divine_row) else 0
    score += 10 if bool(super_row) else 0
    score += 12 if bool(case) else 0
    token_data = token_summary(content)
    source_hebrew = content.get("source_hebrew") or dossier.get("source_hebrew", "")
    required_roles = sorted(
        set(review_row.get("distinct_reviewer_roles", []))
        | set(packet_row.get("required_review_roles", []))
        | set(reception_row.get("required_review_roles", []))
        | set(claim_row.get("required_review_roles", []))
    )
    packet_families = (
        review_row.get("packet_families")
        or packet_row.get("packet_families")
        or dossier.get("source_packet_requirements", [])
    )
    domains = sorted(
        set(dossier.get("context_domains", {}).keys())
        | set(reception_row.get("domains", []))
        | set(cultural_row.get("domain_ids", []))
        | set(claim_row.get("domains", []))
    )
    weakest_lanes = heat.get("weakest_required_lanes") or queue.get("weakest_required_lanes", [])
    next_action = (
        queue.get("next_action")
        or heat.get("next_action")
        or (
            "Create reviewer packet, collect role decisions, and keep generated text "
            "non-authoritative."
        )
    )
    return {
        "unit_id": unit_id,
        "ref": (
            content.get("ref")
            or dossier.get("ref")
            or heat.get("ref")
            or reception_row.get("ref")
            or cross.get("ref")
            or unit_id
        ),
        "psalm_id": unit_id.split(".", 1)[0],
        "source_hebrew": source_hebrew,
        "doctoral_dossier_priority_score": round(score, 2),
        "unit_authority_score_pct": heat.get("unit_authority_score_pct", ""),
        "blocking_lane_count": heat.get("blocking_lane_count", queue.get("blocking_lane_count", 0)),
        "weakest_required_lanes": weakest_lanes,
        "next_action": next_action,
        "packet_priority_score": packet_row.get(
            "packet_priority_score", review_row.get("packet_priority_score", 0)
        ),
        "packet_priority_band": packet_row.get(
            "packet_priority_band", review_row.get("packet_priority_band", "")
        ),
        "packet_family_count": len(packet_families),
        "packet_families": packet_families,
        "packet_review_row_count": review_row.get("packet_review_row_count", ""),
        "required_review_roles": required_roles,
        "domain_count": len(domains),
        "domains": domains,
        "cultural_domain_labels": cultural_row.get("domain_labels", []),
        "cultural_priority_score": cultural_row.get("priority_score", 0),
        "cultural_marker_flags": cultural_row.get("marker_flags", []),
        "reception_sensitive": bool(
            reception_row.get("reception_sensitive")
            or claim_row.get("reception_sensitive")
            or cultural_row.get("reception_sensitive")
        ),
        "jewish_christian_separation_required": bool(
            reception_row.get("jewish_christian_separation_required")
            or claim_row.get("has_jewish_reception_frame")
            and claim_row.get("has_christian_reception_frame")
        ),
        "reception_divergence_priority_score": reception_row.get(
            "reception_divergence_priority_score", 0
        ),
        "reception_case_family_labels": reception_row.get("case_family_labels", []),
        "required_frames": sorted(
            set(reception_row.get("required_frames", []))
            | set(claim_row.get("required_frames", []))
            | set(dossier.get("reception_frames", []))
        ),
        "textual_witness_pressure": bool(
            reception_row.get("textual_witness_pressure")
            or claim_row.get("textual_witness_pressure")
            or cultural_row.get("textual_witness_pressure")
        ),
        "ancient_culture_pressure": bool(
            reception_row.get("ancient_culture_pressure")
            or claim_row.get("ancient_culture_pressure")
            or cultural_row.get("ancient_culture_pressure")
        ),
        "theology_pressure": bool(
            reception_row.get("theology_pressure") or claim_row.get("theology_pressure")
        ),
        "cross_reference_anchor_token_count": cross.get("anchor_token_count", 0),
        "cross_reference_anchor_token_pct": cross.get("anchor_token_pct", 0),
        "cross_reference_high_value_anchor_count": cross.get("high_value_anchor_count", 0),
        "cross_reference_three_division": bool(cross.get("has_three_division_evidence")),
        "top_anchor_form_labels": cross.get("top_anchor_form_labels")
        or [
            f"{anchor['form']} ({anchor['anchor_strength']}, {anchor['outside_psalms_count']})"
            for anchor in cross.get("top_anchor_forms", [])[:5]
        ],
        "witness_priority_score": witness_row.get("priority_score", 0),
        "mean_english_witness_divergence_pct": witness_row.get(
            "mean_english_witness_divergence_pct", 0
        ),
        "witness_marker_flags": witness_row.get("marker_flags", []),
        "kjv_excerpt": witness_row.get("kjv_excerpt", ""),
        "asv_excerpt": witness_row.get("asv_excerpt", ""),
        "web_excerpt": witness_row.get("web_excerpt", ""),
        "divine_name_overlap": bool(divine_row),
        "divine_name_categories": divine_row.get("categories", []),
        "divine_name_marker_flags": divine_row.get("marker_flags", []),
        "superscription_overlap": bool(super_row),
        "superscription_categories": super_row.get("categories", []),
        "superscription_marker_flags": super_row.get("marker_flags", []),
        "claim_risk_score": claim_row.get("claim_risk_score", 0),
        "claim_controls": claim_row.get("claim_controls", []),
        "adjudication_priority_score": adjudication_row.get("adjudication_priority_score", 0),
        "lane_statuses": adjudication_row.get("lane_statuses", {}),
        "casebook_case": bool(case),
        "model_schema_valid_expected_pct": model_row.get(
            "schema_valid_expected_pct",
            heat.get("schema_valid_expected_pct", ""),
        ),
        "model_status": model_row.get("status", ""),
        "quality_review_priority_score": quality_row.get("review_priority_score", 0),
        "layer_risk_score": layer_row.get(
            "layer_risk_score", adjudication_row.get("layer_risk_score", 0)
        ),
        "layer_flags": layer_row.get("flag_reasons", adjudication_row.get("layer_flags", [])),
        **token_data,
        "authority_boundary": (
            "Dossier priority is a review queue. It does not approve wording, "
            "source use, reception interpretation, or model output."
        ),
    }


def build_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [build_unit_row(unit_id, data) for unit_id in collect_candidate_units(data)]
    rows.sort(key=lambda row: float(row["doctoral_dossier_priority_score"]), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
        if index <= 10:
            row["dossier_band"] = "critical"
        elif index <= 25:
            row["dossier_band"] = "highest"
        elif index <= TARGET_UNIT_COUNT:
            row["dossier_band"] = "high"
        else:
            row["dossier_band"] = "watch"
    return rows[:TARGET_UNIT_COUNT]


def build_role_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    role_units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        for role in row["required_review_roles"]:
            role_units[str(role)].append(row)
    rows = []
    for role, selected in role_units.items():
        rows.append(
            {
                "reviewer_role": role,
                "unit_count": len(selected),
                "critical_unit_count": sum(
                    1 for row in selected if row["dossier_band"] == "critical"
                ),
                "split_lane_unit_count": sum(
                    1 for row in selected if row["jewish_christian_separation_required"]
                ),
                "mean_priority_score": mean(
                    [float(row["doctoral_dossier_priority_score"]) for row in selected]
                ),
                "top_ref": selected[0]["ref"],
            }
        )
    return sorted(rows, key=lambda row: int(row["unit_count"]), reverse=True)


def build_lane_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lane_units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        for lane in row["weakest_required_lanes"]:
            lane_units[str(lane)].append(row)
    rows = []
    for lane, selected in lane_units.items():
        rows.append(
            {
                "lane": lane,
                "unit_count": len(selected),
                "critical_unit_count": sum(
                    1 for row in selected if row["dossier_band"] == "critical"
                ),
                "mean_priority_score": mean(
                    [float(row["doctoral_dossier_priority_score"]) for row in selected]
                ),
                "top_ref": selected[0]["ref"],
                "next_action": selected[0]["next_action"],
            }
        )
    return sorted(rows, key=lambda row: int(row["unit_count"]), reverse=True)


def build_domain_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    domain_units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        for domain in row["domains"]:
            domain_units[str(domain)].append(row)
    rows = []
    for domain, selected in domain_units.items():
        rows.append(
            {
                "domain": domain,
                "unit_count": len(selected),
                "critical_unit_count": sum(
                    1 for row in selected if row["dossier_band"] == "critical"
                ),
                "split_lane_unit_count": sum(
                    1 for row in selected if row["jewish_christian_separation_required"]
                ),
                "textual_witness_unit_count": sum(
                    1 for row in selected if row["textual_witness_pressure"]
                ),
                "mean_priority_score": mean(
                    [float(row["doctoral_dossier_priority_score"]) for row in selected]
                ),
                "top_ref": selected[0]["ref"],
            }
        )
    return sorted(rows, key=lambda row: int(row["unit_count"]), reverse=True)


def build_source_family_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    family_units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        for family in row["packet_families"]:
            family_units[str(family)].append(row)
    rows = []
    for family, selected in family_units.items():
        rows.append(
            {
                "packet_family": family,
                "unit_count": len(selected),
                "critical_unit_count": sum(
                    1 for row in selected if row["dossier_band"] == "critical"
                ),
                "split_lane_unit_count": sum(
                    1 for row in selected if row["jewish_christian_separation_required"]
                ),
                "mean_priority_score": mean(
                    [float(row["doctoral_dossier_priority_score"]) for row in selected]
                ),
                "top_ref": selected[0]["ref"],
            }
        )
    return sorted(rows, key=lambda row: int(row["unit_count"]), reverse=True)


def build_visual_data(
    unit_rows: list[dict[str, Any]],
    role_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    domain_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    band_counts = Counter(row["dossier_band"] for row in unit_rows)
    return {
        "dossier_band_counts": [
            {"label": band, "value": count}
            for band, count in sorted(
                band_counts.items(),
                key=lambda item: ["critical", "highest", "high", "watch"].index(item[0]),
            )
        ],
        "top_unit_priority": [
            {"label": row["ref"], "value": row["doctoral_dossier_priority_score"]}
            for row in unit_rows[:20]
        ],
        "role_workload": [
            {"label": row["reviewer_role"], "value": row["unit_count"]} for row in role_rows
        ],
        "weakest_lane_counts": [
            {"label": row["lane"], "value": row["unit_count"]} for row in lane_rows
        ],
        "domain_counts": [
            {"label": row["domain"], "value": row["unit_count"]} for row in domain_rows[:18]
        ],
        "packet_family_counts": [
            {"label": row["packet_family"], "value": row["unit_count"]} for row in family_rows[:18]
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    unit_rows = build_unit_rows(data)
    role_rows = build_role_rows(unit_rows)
    lane_rows = build_lane_rows(unit_rows)
    domain_rows = build_domain_rows(unit_rows)
    family_rows = build_source_family_rows(unit_rows)
    visual_data = build_visual_data(unit_rows, role_rows, lane_rows, domain_rows, family_rows)
    top = unit_rows[0] if unit_rows else {}
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "doctoral priority dossier atlas generated; not review signoff",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "method": {
            "selection": (
                "Union of top units from priority dossiers, authority heatmap queue, "
                "reception divergence, whole-Tanakh cross-reference, cultural atlas, "
                "witness divergence, divine-name pressure, superscription context, and "
                "scholarly casebook."
            ),
            "boundary": (
                "The atlas is a reviewer work queue. It does not approve canonical "
                "rendering, source use, reception interpretation, or local model output."
            ),
            "target_unit_count": TARGET_UNIT_COUNT,
        },
        "summary": {
            "unit_count": len(unit_rows),
            "critical_unit_count": sum(1 for row in unit_rows if row["dossier_band"] == "critical"),
            "highest_unit_count": sum(1 for row in unit_rows if row["dossier_band"] == "highest"),
            "high_unit_count": sum(1 for row in unit_rows if row["dossier_band"] == "high"),
            "reception_sensitive_unit_count": sum(
                1 for row in unit_rows if row["reception_sensitive"]
            ),
            "jewish_christian_separation_unit_count": sum(
                1 for row in unit_rows if row["jewish_christian_separation_required"]
            ),
            "textual_witness_pressure_unit_count": sum(
                1 for row in unit_rows if row["textual_witness_pressure"]
            ),
            "ancient_culture_pressure_unit_count": sum(
                1 for row in unit_rows if row["ancient_culture_pressure"]
            ),
            "divine_name_overlap_unit_count": sum(
                1 for row in unit_rows if row["divine_name_overlap"]
            ),
            "superscription_overlap_unit_count": sum(
                1 for row in unit_rows if row["superscription_overlap"]
            ),
            "casebook_case_count": sum(1 for row in unit_rows if row["casebook_case"]),
            "mean_priority_score": mean(
                [float(row["doctoral_dossier_priority_score"]) for row in unit_rows]
            ),
            "mean_authority_score_pct": mean(
                [
                    float(row["unit_authority_score_pct"])
                    for row in unit_rows
                    if row["unit_authority_score_pct"] != ""
                ]
            ),
            "role_count": len(role_rows),
            "weakest_lane_count": len(lane_rows),
            "domain_count": len(domain_rows),
            "packet_family_count": len(family_rows),
            "top_priority_unit": top.get("unit_id", ""),
            "top_priority_ref": top.get("ref", ""),
            "top_priority_score": top.get("doctoral_dossier_priority_score", 0),
            "top_priority_next_action": top.get("next_action", ""),
        },
        "unit_rows": unit_rows,
        "role_rows": role_rows,
        "lane_rows": lane_rows,
        "domain_rows": domain_rows,
        "packet_family_rows": family_rows,
        "visual_data": visual_data,
    }


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


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def bar_chart(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    title: str,
    limit: int = 20,
) -> str:
    rows = rows[:limit]
    if not rows:
        return ""
    max_value = max(float(row[value_key]) for row in rows) or 1.0
    parts = [f"<h3>{esc(title)}</h3>", '<div class="bar-list">']
    for row in rows:
        value = float(row[value_key])
        width = max(2.0, value / max_value * 100.0)
        parts.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{esc(row[label_key])}</div>
              <div class="bar-track"><div class="bar-fill" style="width: {width:.2f}%"></div></div>
              <div class="bar-value">{esc(f"{value:g}")}</div>
            </div>
            """
        )
    parts.append("</div>")
    return "\n".join(parts)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    top_unit_rows = [
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
        for row in report["unit_rows"][:MAX_TABLE_UNITS]
    ]
    evidence_rows = [
        [
            row["rank"],
            row["ref"],
            row["source_hebrew"],
            row["token_count"],
            f"{row['lemma_coverage_pct']:.2f}%",
            f"{row['strong_coverage_pct']:.2f}%",
            row["cross_reference_anchor_token_count"],
            "; ".join(row["top_anchor_form_labels"]),
            row["mean_english_witness_divergence_pct"],
        ]
        for row in report["unit_rows"][:20]
    ]
    reception_rows = [
        [
            row["rank"],
            row["ref"],
            row["jewish_christian_separation_required"],
            row["reception_sensitive"],
            "; ".join(row["reception_case_family_labels"]),
            "; ".join(row["required_frames"]),
            "; ".join(row["domains"][:8]),
        ]
        for row in report["unit_rows"][:20]
    ]
    role_rows = [
        [
            row["reviewer_role"],
            row["unit_count"],
            row["critical_unit_count"],
            row["split_lane_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["role_rows"]
    ]
    lane_rows = [
        [
            row["lane"],
            row["unit_count"],
            row["critical_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
            row["next_action"],
        ]
        for row in report["lane_rows"]
    ]
    domain_rows = [
        [
            row["domain"],
            row["unit_count"],
            row["critical_unit_count"],
            row["split_lane_unit_count"],
            row["textual_witness_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["domain_rows"][:20]
    ]
    family_rows = [
        [
            row["packet_family"],
            row["unit_count"],
            row["critical_unit_count"],
            row["split_lane_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["packet_family_rows"][:20]
    ]
    band_chart = bar_chart(
        visual["dossier_band_counts"],
        label_key="label",
        value_key="value",
        title="Dossier Bands",
    )
    top_chart = bar_chart(
        visual["top_unit_priority"],
        label_key="label",
        value_key="value",
        title="Top Unit Priority",
    )
    role_chart = bar_chart(
        visual["role_workload"],
        label_key="label",
        value_key="value",
        title="Reviewer Role Workload",
    )
    lane_chart = bar_chart(
        visual["weakest_lane_counts"],
        label_key="label",
        value_key="value",
        title="Weakest Required Lanes",
    )
    domain_chart = bar_chart(
        visual["domain_counts"],
        label_key="label",
        value_key="value",
        title="Domain Coverage",
    )
    family_chart = bar_chart(
        visual["packet_family_counts"],
        label_key="label",
        value_key="value",
        title="Source Packet Families",
    )
    dossier_note = (
        f"{fmt_int(summary['critical_unit_count'])} critical; "
        f"{fmt_int(summary['highest_unit_count'])} highest."
    )
    # Ruff can rewrite nested dict-access f-strings in the embedded HTML into
    # Python 3.12-only quote syntax. This project currently compiles on 3.11.
    # fmt: off
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Doctoral Priority Dossier Atlas</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2a33;
      --muted: #667581;
      --line: #d8dee4;
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
      background: #fff;
      line-height: 1.48;
    }}
    header {{
      padding: 42px 54px 34px;
      border-bottom: 1px solid var(--line);
      background: #f7f9fa;
    }}
    main {{ max-width: 1220px; margin: 0 auto; padding: 30px 34px 54px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    h3 {{ margin: 18px 0 10px; font-size: 15px; }}
    p {{ margin: 0 0 13px; }}
    .lede {{ max-width: 980px; font-size: 17px; color: #33414c; }}
    .meta {{ color: var(--muted); font-size: 13px; margin-top: 12px; }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin: 18px 0;
    }}
    .metric-card {{ border: 1px solid var(--line); border-radius: 6px; padding: 16px; }}
    .metric-card h3 {{
      margin: 0 0 8px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .05em;
    }}
    .metric-value {{ margin: 0 0 8px; font-size: 30px; font-weight: 700; color: var(--accent); }}
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
      background: #fff;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(190px, 290px) minmax(220px, 1fr) 80px;
      gap: 10px;
      align-items: center;
      min-height: 28px;
      font-size: 13px;
    }}
    .bar-label {{ color: #2c3942; }}
    .bar-track {{ height: 18px; background: var(--band); border: 1px solid var(--line); }}
    .bar-fill {{ height: 100%; background: var(--accent); }}
    .bar-value {{ font-weight: 700; }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 14px 0 24px;
      font-size: 13px;
    }}
    th, td {{ border: 1px solid var(--line); padding: 9px 10px; vertical-align: top; }}
    th {{ background: var(--band); text-align: left; }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .metric-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .bar-row {{ grid-template-columns: 1fr; gap: 4px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Doctoral Priority Dossier Atlas</h1>
    <p class="lede">
      Integrated reviewer queue combining Hebrew token evidence, whole-Tanakh
      surface-form anchors, cultural domains, textual witnesses, Jewish/Christian
      reception lanes, authority heatmap gaps, model/layer risks, and source-packet
      workload.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Queue Snapshot</h2>
      <div class="metric-grid">
        {metric_cards([
            (
                "Dossier units",
                fmt_int(summary["unit_count"]),
                dossier_note,
            ),
            (
                "Split lanes",
                fmt_int(summary["jewish_christian_separation_unit_count"]),
                "Require separated Jewish/Christian reception review.",
            ),
            (
                "Textual witness",
                fmt_int(summary["textual_witness_pressure_unit_count"]),
                "Need witness handling without overriding Hebrew.",
            ),
            (
                "Ancient culture",
                fmt_int(summary["ancient_culture_pressure_unit_count"]),
                "Need ancient-setting source packets.",
            ),
            (
                "Divine names",
                fmt_int(summary["divine_name_overlap_unit_count"]),
                "Overlap divine-name/title policy pressure.",
            ),
            (
                "Casebook",
                fmt_int(summary["casebook_case_count"]),
                "Already in high-risk scholarly casebook.",
            ),
            (
                "Top unit",
                summary["top_priority_ref"],
                f'Score {summary["top_priority_score"]:.2f}.',
            ),
            (
                "Mean authority",
                f'{summary["mean_authority_score_pct"]:.2f}%',
                "Mean unit authority score among dossier queue.",
            ),
        ])}
      </div>
      <div class="warning">
        This atlas is a reviewer queue. It does not approve translation wording,
        source use, reception interpretation, or model output.
      </div>
      <div class="chart">{band_chart}</div>
      <div class="chart">{top_chart}</div>
    </section>

    <section>
      <h2>Queue Workload</h2>
      <div class="chart">{role_chart}</div>
      <div class="chart">{lane_chart}</div>
      <div class="chart">{family_chart}</div>
      {table(
          ["Role", "Units", "Critical", "Split-Lane", "Mean Priority", "Top Ref"],
          role_rows,
      )}
      {table(
          ["Weak Lane", "Units", "Critical", "Mean Priority", "Top Ref", "Next Action"],
          lane_rows,
      )}
      {table(
          ["Packet Family", "Units", "Critical", "Split-Lane", "Mean Priority", "Top Ref"],
          family_rows,
      )}
    </section>

    <section>
      <h2>Domain And Evidence Distribution</h2>
      <div class="chart">{domain_chart}</div>
      {table(
          [
              "Domain",
              "Units",
              "Critical",
              "Split-Lane",
              "Textual Witness",
              "Mean Priority",
              "Top Ref",
          ],
          domain_rows,
      )}
    </section>

    <section>
      <h2>Top Dossier Queue</h2>
      {table(
          [
              "Rank",
              "Ref",
              "Band",
              "Priority",
              "Authority %",
              "Blocking Lanes",
              "Weakest Lanes",
              "Roles",
              "Packet Families",
              "Next Action",
          ],
          top_unit_rows,
      )}
    </section>

    <section>
      <h2>Hebrew And Canonical Evidence</h2>
      {table(
          [
              "Rank",
              "Ref",
              "Hebrew",
              "Tokens",
              "Lemma",
              "Strong",
              "Cross-Ref Anchors",
              "Top Anchor Forms",
              "Witness Div %",
          ],
          evidence_rows,
      )}
    </section>

    <section>
      <h2>Reception And Cultural Pressure</h2>
      {table(
          [
              "Rank",
              "Ref",
              "Split Lanes",
              "Reception",
              "Reception Families",
              "Required Frames",
              "Domains",
          ],
          reception_rows,
      )}
    </section>
  </main>
</body>
</html>
"""
    # fmt: on


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an integrated doctoral priority dossier atlas."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--role-csv-output", type=Path, default=DEFAULT_ROLE_CSV_OUTPUT)
    parser.add_argument("--lane-csv-output", type=Path, default=DEFAULT_LANE_CSV_OUTPUT)
    parser.add_argument("--domain-csv-output", type=Path, default=DEFAULT_DOMAIN_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.role_csv_output, report["role_rows"])
    write_csv(args.lane_csv_output, report["lane_rows"])
    write_csv(args.domain_csv_output, report["domain_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
