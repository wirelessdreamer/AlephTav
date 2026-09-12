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
CONTENT_ROOT = ROOT / "content" / "psalms"
REPORT_ROOT = ROOT / "reports" / "research"

RECEPTION_BOUNDARY_PATH = REPORT_ROOT / "reception_interpretation_boundary.json"
ADJUDICATION_PATH = REPORT_ROOT / "interpretive_adjudication_matrix.json"
CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
SOURCE_PACKETS_PATH = REPORT_ROOT / "contextual_source_packet_roadmap.json"
CASEBOOK_PATH = REPORT_ROOT / "scholarly_casebook.json"
WITNESS_DIVERGENCE_PATH = REPORT_ROOT / "witness_divergence_report.json"
DIVINE_NAME_PATH = REPORT_ROOT / "divine_name_policy_report.json"
SUPER_CONTEXT_PATH = REPORT_ROOT / "superscription_context_report.json"
CULTURAL_ATLAS_PATH = REPORT_ROOT / "cultural_historical_domain_atlas.json"
CANONICAL_CROSS_REFERENCE_PATH = REPORT_ROOT / "canonical_cross_reference_atlas.json"
REVIEW_WORKBOOK_PATH = REPORT_ROOT / "contextual_review_signoff_workbook.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "reception_divergence_atlas.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "reception_divergence_atlas_units.csv"
DEFAULT_DOMAIN_CSV_OUTPUT = REPORT_ROOT / "reception_divergence_atlas_domains.csv"
DEFAULT_FRAME_CSV_OUTPUT = REPORT_ROOT / "reception_divergence_atlas_frames.csv"
DEFAULT_SIGNAL_CSV_OUTPUT = REPORT_ROOT / "reception_divergence_atlas_signals.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "reception_divergence_atlas.html"

CASE_FAMILY_RULES = [
    (
        "royal_sonship_messianic_reception_pressure",
        "Royal, Sonship, and Messianic Reception Pressure",
        ["royal", "sonship", "king", "kingship", "davidic", "zion"],
    ),
    (
        "lament_suffering_righteous_pressure",
        "Lament, Enemy, and Suffering Righteousness",
        ["lament", "enemy", "violence", "affliction", "wicked", "righteous"],
    ),
    (
        "nations_zion_universalism_pressure",
        "Nations, Zion, and Universal Worship",
        ["nations", "zion", "geography", "identity", "foreign", "people"],
    ),
    (
        "temple_liturgy_cult_pressure",
        "Temple, Liturgy, and Cultic Setting",
        ["temple", "cult", "liturgy", "sacred", "performance", "superscription"],
    ),
    (
        "torah_wisdom_covenant_pressure",
        "Torah, Wisdom, Covenant, and Hesed",
        ["torah", "wisdom", "covenant", "hesed", "mercy", "law"],
    ),
    (
        "divine_name_title_theology_pressure",
        "Divine Name, Title, and Theology Policy",
        ["divine", "yhwh", "adonai", "elohim", "theology", "lord", "name"],
    ),
    (
        "creation_anthropology_pressure",
        "Creation, Cosmos, and Anthropology",
        ["creation", "cosmos", "anthropology", "body", "soul", "heart"],
    ),
    (
        "textual_witness_reception_pressure",
        "Textual Witness and Reception Boundary",
        ["witness", "lxx", "septuagint", "variant", "textual"],
    ),
]


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


def family_labels(row: dict[str, Any]) -> list[str]:
    tokens: set[str] = set()
    for key in [
        "domains",
        "domain_groups",
        "benchmark_tags",
        "required_frames",
        "claim_controls",
        "packet_families",
    ]:
        value = row.get(key, [])
        if isinstance(value, list):
            for item in value:
                term = str(item).lower()
                tokens.update(term.replace("-", "_").split("_"))
    if row.get("divine_name_overlap"):
        tokens.add("divine")
    if row.get("superscription_context_overlap"):
        tokens.update({"superscription", "performance"})
    labels = []
    for family_id, label, keywords in CASE_FAMILY_RULES:
        if family_id == "textual_witness_reception_pressure":
            if row.get("textual_witness_pressure"):
                labels.append(label)
            continue
        if family_id == "divine_name_title_theology_pressure":
            if row.get("theology_pressure") or row.get("divine_name_overlap"):
                labels.append(label)
            continue
        if any(keyword in tokens for keyword in keywords):
            labels.append(label)
    if row.get("jewish_christian_separation_required"):
        labels.insert(0, "Explicit Jewish/Christian Separation")
    return list(dict.fromkeys(labels))


def family_ids(labels: list[str]) -> list[str]:
    label_to_id = {label: family_id for family_id, label, _keywords in CASE_FAMILY_RULES}
    label_to_id["Explicit Jewish/Christian Separation"] = "explicit_jewish_christian_separation"
    return [label_to_id[label] for label in labels if label in label_to_id]


def priority_score(
    *,
    reception: dict[str, Any],
    claim: dict[str, Any],
    adjudication: dict[str, Any],
    witness: dict[str, Any],
    packet: dict[str, Any],
    cross_reference: dict[str, Any],
    divine: dict[str, Any],
    superscription: dict[str, Any],
) -> float:
    score = float(reception.get("boundary_risk_score") or 0)
    score += min(260.0, float(claim.get("claim_risk_score") or 0)) * 0.22
    score += min(360.0, float(adjudication.get("adjudication_priority_score") or 0)) * 0.16
    score += min(180.0, float(witness.get("priority_score") or 0)) * 0.16
    score += min(480.0, float(packet.get("packet_priority_score") or 0)) * 0.08
    if reception.get("has_jewish_reception_frame") and reception.get(
        "has_christian_reception_frame"
    ):
        score += 30.0
    if reception.get("has_academic_comparison_frame"):
        score += 10.0
    if reception.get("textual_witness_pressure"):
        score += 10.0
    if reception.get("ancient_culture_pressure"):
        score += 8.0
    if reception.get("theology_pressure"):
        score += 8.0
    if divine:
        score += 8.0
    if superscription:
        score += 5.0
    if cross_reference.get("has_three_division_evidence"):
        score += min(
            22.0,
            float(cross_reference.get("high_value_anchor_count") or 0) * 3.0
            + float(cross_reference.get("anchor_token_count") or 0) * 0.7,
        )
    return round(score, 2)


def build_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    claim_by_unit = lookup(data["claim_matrix"]["unit_claim_rows"])
    adjudication_by_unit = lookup(data["adjudication"]["unit_rows"])
    witness_by_unit = lookup(data["witness_divergence"]["unit_rows"])
    divine_by_unit = lookup(data["divine_name_policy"]["unit_rows"])
    superscription_by_unit = lookup(data["superscription_context"]["unit_rows"])
    cultural_by_unit = lookup(data["cultural_atlas"]["unit_rows"])
    cross_reference_by_unit = lookup(data["canonical_cross_reference"]["unit_rows"])
    packet_by_unit = lookup(data["source_packets"]["unit_rows"])
    casebook_by_unit = lookup(data["casebook"]["cases"])

    rows = []
    for reception in data["reception_boundary"]["unit_boundary_rows"]:
        unit_id = str(reception["unit_id"])
        claim = claim_by_unit.get(unit_id, {})
        adjudication = adjudication_by_unit.get(unit_id, {})
        witness = witness_by_unit.get(unit_id, {})
        divine = divine_by_unit.get(unit_id, {})
        superscription = superscription_by_unit.get(unit_id, {})
        cultural = cultural_by_unit.get(unit_id, {})
        cross_reference = cross_reference_by_unit.get(unit_id, {})
        packet = packet_by_unit.get(unit_id, {})
        casebook = casebook_by_unit.get(unit_id, {})
        content = unit_content(unit_id)

        merged = {
            **reception,
            "domain_groups": adjudication.get("domain_groups", claim.get("domain_groups", [])),
            "packet_families": packet.get("packet_families", []),
            "divine_name_overlap": bool(divine),
            "superscription_context_overlap": bool(superscription),
            "jewish_christian_separation_required": bool(
                adjudication.get("jewish_christian_separation_required")
                or claim.get("has_jewish_reception_frame")
                and claim.get("has_christian_reception_frame")
                or reception.get("has_jewish_reception_frame")
                and reception.get("has_christian_reception_frame")
            ),
        }
        labels = family_labels(merged)
        score = priority_score(
            reception=reception,
            claim=claim,
            adjudication=adjudication,
            witness=witness,
            packet=packet,
            cross_reference=cross_reference,
            divine=divine,
            superscription=superscription,
        )
        rows.append(
            {
                "unit_id": unit_id,
                "ref": reception.get("ref", ""),
                "psalm_id": unit_id.split(".", 1)[0],
                "source_hebrew": content.get("source_hebrew", ""),
                "reception_divergence_priority_score": score,
                "boundary_risk_score": reception.get("boundary_risk_score", 0),
                "claim_risk_score": claim.get("claim_risk_score", 0),
                "adjudication_priority_score": adjudication.get("adjudication_priority_score", 0),
                "packet_priority_score": packet.get("packet_priority_score", 0),
                "witness_divergence_priority_score": witness.get("priority_score", 0),
                "mean_english_witness_divergence_pct": witness.get(
                    "mean_english_witness_divergence_pct", 0
                ),
                "jewish_christian_separation_required": merged[
                    "jewish_christian_separation_required"
                ],
                "has_jewish_reception_frame": bool(reception.get("has_jewish_reception_frame")),
                "has_christian_reception_frame": bool(
                    reception.get("has_christian_reception_frame")
                ),
                "has_academic_comparison_frame": bool(
                    reception.get("has_academic_comparison_frame")
                ),
                "reception_sensitive": bool(reception.get("reception_sensitive")),
                "textual_witness_pressure": bool(reception.get("textual_witness_pressure")),
                "ancient_culture_pressure": bool(reception.get("ancient_culture_pressure")),
                "theology_pressure": bool(reception.get("theology_pressure")),
                "divine_name_overlap": bool(divine),
                "superscription_context_overlap": bool(superscription),
                "casebook_case": bool(casebook),
                "complete_expected_witness_set": bool(
                    reception.get("complete_expected_witness_set")
                ),
                "required_frames": reception.get("required_frames", []),
                "required_review_roles": reception.get("required_review_roles", []),
                "domains": reception.get("domains", []),
                "domain_groups": merged["domain_groups"],
                "benchmark_tags": reception.get("benchmark_tags", []),
                "claim_controls": reception.get("claim_controls", []),
                "packet_families": packet.get("packet_families", []),
                "case_family_ids": family_ids(labels),
                "case_family_labels": labels,
                "lane_statuses": adjudication.get("lane_statuses", {}),
                "blocked_lane_count": adjudication.get("blocked_lane_count", 0),
                "review_lane_count": adjudication.get("review_lane_count", 0),
                "schema_valid_model_candidate_count": adjudication.get(
                    "schema_valid_model_candidate_count", 0
                ),
                "layer_risk_score": adjudication.get("layer_risk_score", 0),
                "layer_flags": adjudication.get("layer_flags", []),
                "cross_reference_anchor_token_count": cross_reference.get("anchor_token_count", 0),
                "cross_reference_high_value_anchor_count": cross_reference.get(
                    "high_value_anchor_count", 0
                ),
                "cross_reference_three_division": bool(
                    cross_reference.get("has_three_division_evidence")
                ),
                "top_anchor_forms": cross_reference.get("top_anchor_forms", []),
                "top_anchor_form_labels": [
                    f"{anchor['form']} ({anchor['anchor_strength']}, "
                    f"{anchor['outside_psalms_count']})"
                    for anchor in cross_reference.get("top_anchor_forms", [])[:5]
                ],
                "cultural_domain_labels": cultural.get("domain_labels", []),
                "authority_boundary": (
                    "Separated reception lanes route review only; translation text remains "
                    "controlled by Hebrew token evidence until signed reviewer decisions exist."
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: float(row["reception_divergence_priority_score"]),
        reverse=True,
    )


def build_domain_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        for domain in row["domains"]:
            buckets[str(domain)].append(row)
    rows = []
    for domain, rows_for_domain in buckets.items():
        top = max(
            rows_for_domain,
            key=lambda item: float(item["reception_divergence_priority_score"]),
        )
        rows.append(
            {
                "domain": domain,
                "unit_count": len(rows_for_domain),
                "separation_required_unit_count": sum(
                    1 for row in rows_for_domain if row["jewish_christian_separation_required"]
                ),
                "reception_sensitive_unit_count": sum(
                    1 for row in rows_for_domain if row["reception_sensitive"]
                ),
                "textual_witness_pressure_unit_count": sum(
                    1 for row in rows_for_domain if row["textual_witness_pressure"]
                ),
                "ancient_culture_pressure_unit_count": sum(
                    1 for row in rows_for_domain if row["ancient_culture_pressure"]
                ),
                "mean_reception_divergence_priority_score": mean(
                    [float(row["reception_divergence_priority_score"]) for row in rows_for_domain]
                ),
                "top_ref": top["ref"],
                "top_score": top["reception_divergence_priority_score"],
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            float(row["mean_reception_divergence_priority_score"]),
            int(row["unit_count"]),
        ),
        reverse=True,
    )


def build_frame_rows(
    data: dict[str, dict[str, Any]],
    unit_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_unit = {row["unit_id"]: row for row in unit_rows}
    frame_meta: dict[str, dict[str, Any]] = {}
    frame_units: dict[str, set[str]] = defaultdict(set)
    for row in data["reception_boundary"]["unit_frame_rows"]:
        frame = str(row["frame"])
        frame_units[frame].add(str(row["unit_id"]))
        frame_meta.setdefault(
            frame,
            {
                "frame": frame,
                "lane": row.get("lane", ""),
                "allowed_location": row.get("allowed_location", ""),
                "boundary": row.get("boundary", ""),
            },
        )
    rows = []
    for frame, unit_ids in frame_units.items():
        selected = [by_unit[unit_id] for unit_id in unit_ids if unit_id in by_unit]
        rows.append(
            {
                **frame_meta[frame],
                "unit_count": len(selected),
                "separation_required_unit_count": sum(
                    1 for row in selected if row["jewish_christian_separation_required"]
                ),
                "mean_reception_divergence_priority_score": mean(
                    [float(row["reception_divergence_priority_score"]) for row in selected]
                ),
            }
        )
    return sorted(rows, key=lambda row: int(row["unit_count"]), reverse=True)


def build_signal_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signal_units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    signal_ids: dict[str, str] = {}
    for row in unit_rows:
        for signal_id, label in zip(
            row["case_family_ids"],
            row["case_family_labels"],
            strict=False,
        ):
            signal_ids[label] = signal_id
            signal_units[label].append(row)
    rows = []
    for label, selected in signal_units.items():
        top = max(
            selected,
            key=lambda item: float(item["reception_divergence_priority_score"]),
        )
        rows.append(
            {
                "signal_id": signal_ids[label],
                "signal_label": label,
                "unit_count": len(selected),
                "unit_pct": pct(len(selected), len(unit_rows)),
                "separation_required_unit_count": sum(
                    1 for row in selected if row["jewish_christian_separation_required"]
                ),
                "mean_reception_divergence_priority_score": mean(
                    [float(row["reception_divergence_priority_score"]) for row in selected]
                ),
                "top_ref": top["ref"],
                "top_score": top["reception_divergence_priority_score"],
            }
        )
    return sorted(rows, key=lambda row: int(row["unit_count"]), reverse=True)


def build_psalm_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    psalm_units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        psalm_units[row["psalm_id"]].append(row)
    rows = []
    for psalm_id, selected in psalm_units.items():
        top = max(
            selected,
            key=lambda item: float(item["reception_divergence_priority_score"]),
        )
        rows.append(
            {
                "psalm_id": psalm_id,
                "unit_count": len(selected),
                "separation_required_unit_count": sum(
                    1 for row in selected if row["jewish_christian_separation_required"]
                ),
                "reception_sensitive_unit_count": sum(
                    1 for row in selected if row["reception_sensitive"]
                ),
                "mean_reception_divergence_priority_score": mean(
                    [float(row["reception_divergence_priority_score"]) for row in selected]
                ),
                "top_ref": top["ref"],
                "top_score": top["reception_divergence_priority_score"],
            }
        )
    return sorted(
        rows,
        key=lambda row: float(row["mean_reception_divergence_priority_score"]),
        reverse=True,
    )


def build_boundary_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    claim_summary = data["claim_matrix"]["summary"]
    packet_summary = data["source_packets"]["summary"]
    review_summary = data["review_workbook"]["summary"]
    return [
        {
            "boundary_id": "RCP-BND-01",
            "boundary": "Reception cannot control translation wording by itself.",
            "evidence": (
                f"{claim_summary['translation_text_reception_forbidden_unit_count']} "
                "expanded units forbid reception claims in translation text."
            ),
            "next_action": "Keep reception evidence in labeled rationale or notes.",
        },
        {
            "boundary_id": "RCP-BND-02",
            "boundary": "Jewish and Christian reception must be separated.",
            "evidence": (
                f"{claim_summary['jewish_christian_separation_unit_count']} claim rows and "
                f"{packet_summary['jewish_christian_packet_unit_count']} packet rows require "
                "separate Jewish and Christian handling."
            ),
            "next_action": "Create distinct Jewish, Christian, and academic source packets.",
        },
        {
            "boundary_id": "RCP-BND-03",
            "boundary": "Human signoff is absent.",
            "evidence": (
                f"{review_summary['completed_review_row_count']} of "
                f"{review_summary['total_review_row_count']} review rows are complete."
            ),
            "next_action": "Assign Hebrew, theology, reception, and release reviewers.",
        },
    ]


def build_visual_data(
    unit_rows: list[dict[str, Any]],
    domain_rows: list[dict[str, Any]],
    frame_rows: list[dict[str, Any]],
    signal_rows: list[dict[str, Any]],
    data: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "scope_counts": [
            {
                "label": "Explicit reception-boundary units",
                "value": data["reception_boundary"]["summary"]["unit_count"],
            },
            {
                "label": "Jewish/Christian separation units",
                "value": sum(1 for row in unit_rows if row["jewish_christian_separation_required"]),
            },
            {
                "label": "Full-corpus cultural reception proxies",
                "value": data["cultural_atlas"]["summary"]["reception_sensitive_unit_count"],
            },
            {
                "label": "Full-corpus cross-reference units",
                "value": data["canonical_cross_reference"]["summary"]["cross_reference_unit_count"],
            },
        ],
        "signal_unit_counts": [
            {"label": row["signal_label"], "value": row["unit_count"]} for row in signal_rows
        ],
        "frame_unit_counts": [
            {"label": row["frame"], "value": row["unit_count"]} for row in frame_rows
        ],
        "domain_mean_priority": [
            {
                "label": row["domain"],
                "value": row["mean_reception_divergence_priority_score"],
            }
            for row in domain_rows[:12]
        ],
        "top_unit_priority": [
            {
                "label": row["ref"],
                "value": row["reception_divergence_priority_score"],
            }
            for row in unit_rows[:20]
        ],
    }


def build_report() -> dict[str, Any]:
    data = {
        "reception_boundary": load_json(RECEPTION_BOUNDARY_PATH),
        "adjudication": load_json(ADJUDICATION_PATH),
        "claim_matrix": load_json(CLAIM_MATRIX_PATH),
        "source_packets": load_json(SOURCE_PACKETS_PATH),
        "casebook": load_json(CASEBOOK_PATH),
        "witness_divergence": load_json(WITNESS_DIVERGENCE_PATH),
        "divine_name_policy": load_json(DIVINE_NAME_PATH),
        "superscription_context": load_json(SUPER_CONTEXT_PATH),
        "cultural_atlas": load_json(CULTURAL_ATLAS_PATH),
        "canonical_cross_reference": load_json(CANONICAL_CROSS_REFERENCE_PATH),
        "review_workbook": load_json(REVIEW_WORKBOOK_PATH),
    }
    unit_rows = build_unit_rows(data)
    domain_rows = build_domain_rows(unit_rows)
    frame_rows = build_frame_rows(data, unit_rows)
    signal_rows = build_signal_rows(unit_rows)
    psalm_rows = build_psalm_rows(unit_rows)
    boundary_rows = build_boundary_rows(data)
    visual_data = build_visual_data(unit_rows, domain_rows, frame_rows, signal_rows, data)

    separation_count = sum(1 for row in unit_rows if row["jewish_christian_separation_required"])
    top = unit_rows[0] if unit_rows else {}
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "reception divergence atlas generated; not interpretive signoff",
        "source_paths": {
            "reception_boundary": str(RECEPTION_BOUNDARY_PATH.relative_to(ROOT)),
            "adjudication": str(ADJUDICATION_PATH.relative_to(ROOT)),
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
            "source_packets": str(SOURCE_PACKETS_PATH.relative_to(ROOT)),
            "casebook": str(CASEBOOK_PATH.relative_to(ROOT)),
            "witness_divergence": str(WITNESS_DIVERGENCE_PATH.relative_to(ROOT)),
            "divine_name_policy": str(DIVINE_NAME_PATH.relative_to(ROOT)),
            "superscription_context": str(SUPER_CONTEXT_PATH.relative_to(ROOT)),
            "cultural_atlas": str(CULTURAL_ATLAS_PATH.relative_to(ROOT)),
            "canonical_cross_reference": str(CANONICAL_CROSS_REFERENCE_PATH.relative_to(ROOT)),
            "review_workbook": str(REVIEW_WORKBOOK_PATH.relative_to(ROOT)),
        },
        "method": {
            "scope": (
                "Direct Jewish/Christian divergence rows are limited to the expanded "
                "reception-boundary corpus. Full-corpus cultural and cross-reference rows "
                "are routing context only."
            ),
            "boundary": (
                "The atlas identifies review pressure and separated interpretive lanes. "
                "It does not decide Jewish interpretation, Christian interpretation, "
                "messianic meaning, canonical wording, or source approval."
            ),
            "priority_formula": (
                "Weighted combination of boundary risk, claim risk, adjudication priority, "
                "witness divergence, packet priority, separated reception frames, textual "
                "witness pressure, theology/culture pressure, divine-name overlap, "
                "superscription overlap, and whole-Tanakh surface-form anchor breadth."
            ),
        },
        "summary": {
            "unit_count": len(unit_rows),
            "reception_sensitive_unit_count": sum(
                1 for row in unit_rows if row["reception_sensitive"]
            ),
            "jewish_christian_separation_unit_count": separation_count,
            "jewish_christian_separation_unit_pct": pct(separation_count, len(unit_rows)),
            "academic_comparison_unit_count": sum(
                1 for row in unit_rows if row["has_academic_comparison_frame"]
            ),
            "textual_witness_pressure_unit_count": sum(
                1 for row in unit_rows if row["textual_witness_pressure"]
            ),
            "ancient_culture_pressure_unit_count": sum(
                1 for row in unit_rows if row["ancient_culture_pressure"]
            ),
            "theology_pressure_unit_count": sum(1 for row in unit_rows if row["theology_pressure"]),
            "divine_name_overlap_unit_count": sum(
                1 for row in unit_rows if row["divine_name_overlap"]
            ),
            "superscription_overlap_unit_count": sum(
                1 for row in unit_rows if row["superscription_context_overlap"]
            ),
            "casebook_case_count": sum(1 for row in unit_rows if row["casebook_case"]),
            "signal_count": len(signal_rows),
            "frame_count": len(frame_rows),
            "domain_count": len(domain_rows),
            "psalm_count": len(psalm_rows),
            "mean_reception_divergence_priority_score": mean(
                [float(row["reception_divergence_priority_score"]) for row in unit_rows]
            ),
            "top_priority_unit": top.get("unit_id", ""),
            "top_priority_ref": top.get("ref", ""),
            "top_priority_score": top.get("reception_divergence_priority_score", 0),
            "full_corpus_cultural_reception_proxy_unit_count": data["cultural_atlas"]["summary"][
                "reception_sensitive_unit_count"
            ],
            "full_corpus_cross_reference_unit_count": data["canonical_cross_reference"]["summary"][
                "cross_reference_unit_count"
            ],
            "completed_review_row_count": data["review_workbook"]["summary"][
                "completed_review_row_count"
            ],
            "total_review_row_count": data["review_workbook"]["summary"]["total_review_row_count"],
        },
        "unit_rows": unit_rows,
        "domain_rows": domain_rows,
        "frame_rows": frame_rows,
        "signal_rows": signal_rows,
        "psalm_rows": psalm_rows,
        "boundary_rows": boundary_rows,
        "packet_family_rows": data["source_packets"]["source_family_rows"],
        "gate_rows": data["source_packets"]["gate_rows"],
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
    limit: int = 18,
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
    top_units = [
        [
            row["ref"],
            f"{row['reception_divergence_priority_score']:.2f}",
            row["jewish_christian_separation_required"],
            "; ".join(row["case_family_labels"]),
            "; ".join(row["required_frames"]),
            "; ".join(row["domains"]),
            "; ".join(row["top_anchor_form_labels"]),
            row["source_hebrew"],
        ]
        for row in report["unit_rows"][:20]
    ]
    signal_rows = [
        [
            row["signal_label"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["separation_required_unit_count"],
            f"{row['mean_reception_divergence_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["signal_rows"]
    ]
    frame_rows = [
        [
            row["frame"],
            row["lane"],
            row["unit_count"],
            row["separation_required_unit_count"],
            f"{row['mean_reception_divergence_priority_score']:.2f}",
            row["allowed_location"],
        ]
        for row in report["frame_rows"]
    ]
    domain_rows = [
        [
            row["domain"],
            row["unit_count"],
            row["separation_required_unit_count"],
            row["reception_sensitive_unit_count"],
            f"{row['mean_reception_divergence_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["domain_rows"]
    ]
    packet_rows = [
        [
            row["label"],
            row["status"],
            row["unit_count"],
            row["jewish_christian_unit_count"],
            row["top_ref"],
            "; ".join(row["review_roles"]),
            row["authority_boundary"],
        ]
        for row in report["packet_family_rows"]
    ]
    boundary_rows = [
        [row["boundary_id"], row["boundary"], row["evidence"], row["next_action"]]
        for row in report["boundary_rows"]
    ]
    gate_rows = [
        [
            row["gate"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in report["gate_rows"]
    ]
    scope_chart = bar_chart(
        visual["scope_counts"],
        label_key="label",
        value_key="value",
        title="Evidence Scope",
    )
    signal_chart = bar_chart(
        visual["signal_unit_counts"],
        label_key="label",
        value_key="value",
        title="Reception Signal Families",
    )
    frame_chart = bar_chart(
        visual["frame_unit_counts"],
        label_key="label",
        value_key="value",
        title="Required Interpretive Frames",
    )
    domain_chart = bar_chart(
        visual["domain_mean_priority"],
        label_key="label",
        value_key="value",
        title="Domain Mean Priority",
    )
    top_unit_chart = bar_chart(
        visual["top_unit_priority"],
        label_key="label",
        value_key="value",
        title="Top Unit Priority",
    )
    separation_note = f"{summary['jewish_christian_separation_unit_pct']:.2f}% require split lanes."
    top_priority_note = f"Score {summary['top_priority_score']:.2f}."
    review_note = f"of {fmt_int(summary['total_review_row_count'])} review rows."
    # Ruff can rewrite nested dict-access f-strings in the embedded HTML into
    # Python 3.12-only quote syntax. This project currently compiles on 3.11.
    # fmt: off
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reception Divergence Atlas</title>
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
    main {{ max-width: 1180px; margin: 0 auto; padding: 30px 34px 54px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    h3 {{ margin: 18px 0 10px; font-size: 15px; }}
    p {{ margin: 0 0 13px; }}
    .lede {{ max-width: 960px; font-size: 17px; color: #33414c; }}
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
      grid-template-columns: minmax(190px, 280px) minmax(220px, 1fr) 80px;
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
    <h1>Reception Divergence Atlas</h1>
    <p class="lede">
      Quantified review atlas for Psalms units where Jewish, Christian, academic,
      textual-witness, ancient-cultural, and Hebrew-source lanes must be separated
      before translation wording can be authorized.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Readiness Snapshot</h2>
      <div class="metric-grid">
        {
        metric_cards(
            [
                (
                    "Explicit units",
                    fmt_int(summary["unit_count"]),
                    "Expanded reception-boundary corpus under direct frame analysis.",
                ),
                (
                    "Separation units",
                    fmt_int(summary["jewish_christian_separation_unit_count"]),
                    separation_note,
                ),
                (
                    "Academic comparison",
                    fmt_int(summary["academic_comparison_unit_count"]),
                    "Units requiring an academic critical comparison lane.",
                ),
                (
                    "Top priority",
                    summary["top_priority_ref"],
                    top_priority_note,
                ),
                (
                    "Textual witness",
                    fmt_int(summary["textual_witness_pressure_unit_count"]),
                    "Units where reception must be separated from witness evidence.",
                ),
                (
                    "Divine overlap",
                    fmt_int(summary["divine_name_overlap_unit_count"]),
                    "Units also carrying divine-name or divine-title policy pressure.",
                ),
                (
                    "Casebook cases",
                    fmt_int(summary["casebook_case_count"]),
                    "High-risk cases already expanded into scholarly packets.",
                ),
                (
                    "Review complete",
                    fmt_int(summary["completed_review_row_count"]),
                    review_note,
                ),
            ]
        )
    }
      </div>
      <div class="warning">
        This report measures review pressure, not interpretive correctness. Jewish
        reception, Christian reception, and academic comparison lanes must be
        separately sourced and signed before they influence translation wording.
      </div>
      <div class="chart">
        {scope_chart}
      </div>
    </section>

    <section>
      <h2>Visual Evidence</h2>
      <div class="chart">
        {signal_chart}
      </div>
      <div class="chart">
        {frame_chart}
      </div>
      <div class="chart">
        {domain_chart}
      </div>
      <div class="chart">
        {top_unit_chart}
      </div>
    </section>

    <section>
      <h2>Top Review Units</h2>
      {
        table(
            [
                "Ref",
                "Priority",
                "Split Lanes",
                "Signal Families",
                "Required Frames",
                "Domains",
                "Top Cross-Refs",
                "Hebrew",
            ],
            top_units,
        )
    }
    </section>

    <section>
      <h2>Signal Families</h2>
      {
        table(
            ["Signal", "Units", "Unit %", "Split-Lane Units", "Mean Priority", "Top Ref"],
            signal_rows,
        )
    }
    </section>

    <section>
      <h2>Frames And Domains</h2>
      {
        table(
            ["Frame", "Lane", "Units", "Split-Lane Units", "Mean Priority", "Allowed Location"],
            frame_rows,
        )
    }
      {
        table(
            ["Domain", "Units", "Split-Lane Units", "Reception Units", "Mean Priority", "Top Ref"],
            domain_rows,
        )
    }
    </section>

    <section>
      <h2>Source Packet And Boundary Gates</h2>
      {
        table(
            [
                "Family",
                "Status",
                "Units",
                "Jewish/Christian Units",
                "Top Ref",
                "Review Roles",
                "Authority Boundary",
            ],
            packet_rows,
        )
    }
      {table(["Boundary ID", "Boundary", "Evidence", "Next Action"], boundary_rows)}
      {table(["Gate", "Score", "Status", "Evidence", "Next Action"], gate_rows)}
    </section>
  </main>
</body>
</html>
"""
    # fmt: on


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a reception divergence review atlas.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--domain-csv-output", type=Path, default=DEFAULT_DOMAIN_CSV_OUTPUT)
    parser.add_argument("--frame-csv-output", type=Path, default=DEFAULT_FRAME_CSV_OUTPUT)
    parser.add_argument("--signal-csv-output", type=Path, default=DEFAULT_SIGNAL_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.domain_csv_output, report["domain_rows"])
    write_csv(args.frame_csv_output, report["frame_rows"])
    write_csv(args.signal_csv_output, report["signal_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
