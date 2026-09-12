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

SOURCE_PATHS = {
    "context_integration": REPORT_ROOT / "doctoral_context_integration_matrix.json",
    "canonical_cross_reference": REPORT_ROOT / "canonical_cross_reference_atlas.json",
    "translation_claim_matrix": REPORT_ROOT / "translation_claim_evidence_matrix.json",
    "cultural_historical_atlas": REPORT_ROOT / "cultural_historical_domain_atlas.json",
    "witness_divergence": REPORT_ROOT / "witness_divergence_report.json",
    "reception_divergence": REPORT_ROOT / "reception_divergence_atlas.json",
    "divine_name_policy": REPORT_ROOT / "divine_name_policy_report.json",
    "superscription_context": REPORT_ROOT / "superscription_context_report.json",
    "poetic_rhetorical_atlas": REPORT_ROOT / "poetic_rhetorical_pressure_atlas.json",
    "doctoral_priority_dossier": REPORT_ROOT / "doctoral_priority_dossier_atlas.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "doctoral_collision_review_packets.json"
DEFAULT_PACKET_CSV_OUTPUT = REPORT_ROOT / "doctoral_collision_review_packets_units.csv"
DEFAULT_DECISION_CSV_OUTPUT = REPORT_ROOT / "doctoral_collision_review_packets_decisions.csv"
DEFAULT_LANE_CSV_OUTPUT = REPORT_ROOT / "doctoral_collision_review_packets_lanes.csv"
DEFAULT_ROLE_CSV_OUTPUT = REPORT_ROOT / "doctoral_collision_review_packets_roles.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "doctoral_collision_review_packets.html"

DECISION_LANES = {
    "hebrew_basis": {
        "label": "Hebrew basis and lexical control",
        "reviewer_role": "Hebrew; lexical; alignment",
        "decision_prompt": (
            "Identify which Hebrew tokens directly govern the English wording and record "
            "any morphology, syntax, or alignment uncertainty."
        ),
        "forbidden_shortcut": "Do not let English witnesses or reception frames choose wording.",
        "authority_effect": "May constrain wording only after token-aligned reviewer signoff.",
    },
    "whole_tanakh_anchor": {
        "label": "Whole-Tanakh anchor adjudication",
        "reviewer_role": "Hebrew; lexical",
        "decision_prompt": (
            "Check whether broader-canon surface anchors are relevant context, lexical "
            "parallel, idiom support, or unrelated form overlap."
        ),
        "forbidden_shortcut": "Do not treat UXLC surface-form matches as lemma or allusion proof.",
        "authority_effect": "May support rationale notes; wording impact needs Hebrew signoff.",
    },
    "cultural_historical": {
        "label": "Cultural and historical context",
        "reviewer_role": "Hebrew; theology",
        "decision_prompt": (
            "State which ancient cultural, political, cultic, geography, or genre domains "
            "are actually relevant to the unit."
        ),
        "forbidden_shortcut": "Do not convert domain tags into historical claims without sources.",
        "authority_effect": "May route source-packet work and explanatory notes after signoff.",
    },
    "textual_witness": {
        "label": "Textual witness handling",
        "reviewer_role": "Hebrew; alignment",
        "decision_prompt": (
            "Record whether witness divergence reflects translation style, textual variant, "
            "divine-name policy, expansion, or real interpretive pressure."
        ),
        "forbidden_shortcut": "Do not silently override the Hebrew source with witness wording.",
        "authority_effect": "May require notes or textual cautions after reviewer decision.",
    },
    "divine_name_policy": {
        "label": "Divine-name/title policy",
        "reviewer_role": "Hebrew; theology; release",
        "decision_prompt": (
            "Apply the approved divine-name/title policy or identify what policy decision "
            "is still missing for this unit."
        ),
        "forbidden_shortcut": "Do not infer LORD/Jehovah/God renderings from one witness alone.",
        "authority_effect": "May affect visible wording only after theology and release signoff.",
    },
    "poetic_rhetorical": {
        "label": "Poetic/rhetorical preservation",
        "reviewer_role": "Hebrew; lyric; alignment",
        "decision_prompt": (
            "Decide which repetitions, parallelism cues, discourse markers, or volitives "
            "must be preserved in each English layer."
        ),
        "forbidden_shortcut": "Do not improve style at the expense of token alignment.",
        "authority_effect": "May constrain phrase, lyric, metered, and parallelism layers.",
    },
    "jewish_reception": {
        "label": "Jewish reception frame",
        "reviewer_role": "theology; release",
        "decision_prompt": (
            "Record the Jewish interpretive frame separately from Christian and academic "
            "frames, with source boundaries and wording impact."
        ),
        "forbidden_shortcut": "Do not merge Jewish and Christian readings into one claim.",
        "authority_effect": "May inform labeled notes after source packet and reviewer signoff.",
    },
    "christian_reception": {
        "label": "Christian reception frame",
        "reviewer_role": "theology; release",
        "decision_prompt": (
            "Record the Christian interpretive frame separately from Jewish and academic "
            "frames, with source boundaries and wording impact."
        ),
        "forbidden_shortcut": "Do not import later Christian readings into Hebrew wording.",
        "authority_effect": "May inform labeled notes after source packet and reviewer signoff.",
    },
    "academic_comparison": {
        "label": "Academic critical comparison",
        "reviewer_role": "Hebrew; theology; release",
        "decision_prompt": (
            "Compare plain Hebrew, cultural context, textual witness pressure, and "
            "reception claims without collapsing them into one translation claim."
        ),
        "forbidden_shortcut": "Do not let academic comparison stand in for source approval.",
        "authority_effect": "May adjudicate notes and reviewer rationale, not release alone.",
    },
    "release_authority": {
        "label": "Release authority and audit",
        "reviewer_role": "release",
        "decision_prompt": (
            "Confirm whether all required source, Hebrew, alignment, theology, and layer "
            "decisions are complete before any canonical wording is allowed."
        ),
        "forbidden_shortcut": "Do not treat generated packet rows as review completion.",
        "authority_effect": "Only a signed release decision can authorize canonical output.",
    },
}


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


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    return [value]


def join_values(values: Any, *, limit: int | None = None) -> str:
    items = [str(value) for value in as_list(values) if str(value)]
    if limit is not None:
        items = items[:limit]
    return "; ".join(items)


def rows_by_unit(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in rows}


def safe_int(row: dict[str, Any], key: str, default: int = 0) -> int:
    value = row.get(key, default)
    if value in {None, ""}:
        return default
    return int(value)


def safe_float(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    if value in {None, ""}:
        return default
    return float(value)


def display_top_anchor_forms(canonical: dict[str, Any], limit: int = 6) -> str:
    labels = []
    for item in as_list(canonical.get("top_anchor_forms"))[:limit]:
        if isinstance(item, dict):
            form = item.get("form", "")
            gloss = item.get("gloss", "")
            count = item.get("outside_count", item.get("count", ""))
            bits = [str(part) for part in [form, gloss] if part]
            label = " / ".join(bits)
            if count != "":
                label = f"{label} ({count})" if label else str(count)
            labels.append(label)
        else:
            labels.append(str(item))
    return "; ".join(label for label in labels if label)


def top_mapping(mapping: Any, limit: int = 6) -> str:
    if not isinstance(mapping, dict):
        return ""
    rows = sorted(mapping.items(), key=lambda item: item[1], reverse=True)[:limit]
    return "; ".join(f"{key} ({value})" for key, value in rows)


def collision_units(context_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in context_matrix.get("unit_rows", []):
        if (
            row.get("whole_tanakh_three_division")
            and row.get("cultural_historical_domain")
            and row.get("textual_witness_pressure")
            and (row.get("reception_sensitive") or row.get("jewish_christian_separation"))
        ):
            rows.append(row)
    return sorted(rows, key=lambda item: float(item["integration_pressure_score"]), reverse=True)


def required_lanes_for_packet(
    *,
    context: dict[str, Any],
    divine: dict[str, Any],
    poetic: dict[str, Any],
) -> list[str]:
    lanes = [
        "hebrew_basis",
        "whole_tanakh_anchor",
        "cultural_historical",
        "textual_witness",
    ]
    if safe_int(divine, "divine_title_token_count") > 0:
        lanes.append("divine_name_policy")
    if context.get("poetic_rhetorical_pressure") or poetic.get("pressure_band"):
        lanes.append("poetic_rhetorical")
    if context.get("jewish_christian_separation"):
        lanes.extend(["jewish_reception", "christian_reception"])
    if context.get("academic_comparison_required"):
        lanes.append("academic_comparison")
    lanes.append("release_authority")
    return lanes


def build_packet_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    context_rows = collision_units(data["context_integration"])
    canonical_rows = rows_by_unit(data["canonical_cross_reference"].get("unit_rows", []))
    claim_rows = rows_by_unit(data["translation_claim_matrix"].get("unit_claim_rows", []))
    cultural_rows = rows_by_unit(data["cultural_historical_atlas"].get("unit_rows", []))
    witness_rows = rows_by_unit(data["witness_divergence"].get("unit_rows", []))
    reception_rows = rows_by_unit(data["reception_divergence"].get("unit_rows", []))
    divine_rows = rows_by_unit(data["divine_name_policy"].get("unit_rows", []))
    superscription_rows = rows_by_unit(data["superscription_context"].get("unit_rows", []))
    poetic_rows = rows_by_unit(data["poetic_rhetorical_atlas"].get("unit_rows", []))
    dossier_rows = rows_by_unit(data["doctoral_priority_dossier"].get("unit_rows", []))

    packets = []
    for index, context in enumerate(context_rows, start=1):
        unit_id = str(context["unit_id"])
        canonical = canonical_rows.get(unit_id, {})
        claim = claim_rows.get(unit_id, {})
        cultural = cultural_rows.get(unit_id, {})
        witness = witness_rows.get(unit_id, {})
        reception = reception_rows.get(unit_id, {})
        divine = divine_rows.get(unit_id, {})
        superscription = superscription_rows.get(unit_id, {})
        poetic = poetic_rows.get(unit_id, {})
        dossier = dossier_rows.get(unit_id, {})
        required_lanes = required_lanes_for_packet(
            context=context,
            divine=divine,
            poetic=poetic,
        )
        packet_id = f"collision_{index:02d}_{unit_id}"
        packets.append(
            {
                "packet_id": packet_id,
                "rank": index,
                "unit_id": unit_id,
                "ref": context.get("ref", ""),
                "psalm_id": context.get("psalm_id", ""),
                "integration_pressure_score": context["integration_pressure_score"],
                "integration_pressure_band": context["integration_pressure_band"],
                "active_lens_count": context["active_lens_count"],
                "active_lens_labels": context.get("active_lens_labels", []),
                "required_review_roles": context.get("required_review_roles", []),
                "required_decision_lanes": required_lanes,
                "required_decision_count": len(required_lanes),
                "review_status": "queued_not_signed_off",
                "authority_status": "not_authority",
                "source_hebrew": context.get("source_hebrew", ""),
                "canonical_anchor_token_count": safe_int(canonical, "anchor_token_count"),
                "canonical_anchor_token_pct": safe_float(canonical, "anchor_token_pct"),
                "canonical_high_value_anchor_count": safe_int(
                    canonical,
                    "high_value_anchor_count",
                ),
                "outside_division_counts": canonical.get("outside_division_counts", {}),
                "outside_book_counts": canonical.get("outside_book_counts", {}),
                "top_anchor_forms": display_top_anchor_forms(canonical),
                "cultural_domain_labels": cultural.get("domain_labels", []),
                "cultural_domain_counts": cultural.get("domain_counts", {}),
                "cultural_top_lemmas": cultural.get("top_lemmas", {}),
                "witness_divergence_pct": safe_float(
                    witness,
                    "mean_english_witness_divergence_pct",
                ),
                "witness_marker_flags": witness.get("marker_flags", []),
                "kjv_excerpt": witness.get("kjv_excerpt", ""),
                "asv_excerpt": witness.get("asv_excerpt", ""),
                "web_excerpt": witness.get("web_excerpt", ""),
                "divine_title_token_count": safe_int(divine, "divine_title_token_count"),
                "divine_name_categories": divine.get("categories", []),
                "divine_witness_profiles": divine.get("english_witness_profiles", {}),
                "divine_witness_disagreement": bool(
                    divine.get("english_witness_divine_rendering_disagreement")
                ),
                "superscription_context_token_count": safe_int(
                    superscription,
                    "context_token_count",
                ),
                "superscription_categories": superscription.get("categories", []),
                "poetic_pressure_band": poetic.get("pressure_band", ""),
                "poetic_priority_score": safe_float(
                    poetic,
                    "poetic_rhetorical_priority_score",
                ),
                "poetic_feature_flags": poetic.get("feature_flags", []),
                "reception_priority_score": safe_float(
                    reception,
                    "reception_divergence_priority_score",
                ),
                "reception_required_frames": reception.get("required_frames", []),
                "reception_case_family_labels": reception.get("case_family_labels", []),
                "packet_families": dossier.get("packet_families", []),
                "weakest_required_lanes": dossier.get("weakest_required_lanes", []),
                "blocking_lane_count": safe_int(dossier, "blocking_lane_count"),
                "unit_authority_score_pct": safe_float(dossier, "unit_authority_score_pct"),
                "claim_controls": claim.get("claim_controls", []),
                "allowed_claim_lanes": claim.get("allowed_claim_lanes", {}),
                "next_action": dossier.get(
                    "next_action",
                    "Create separated review decisions before authority is inferred.",
                ),
            }
        )
    return packets


def decision_current_data(packet: dict[str, Any], lane_id: str) -> str:
    if lane_id == "hebrew_basis":
        return (
            f"Hebrew source tokens present; claim controls: "
            f"{join_values(packet['claim_controls'], limit=8)}"
        )
    if lane_id == "whole_tanakh_anchor":
        return (
            f"{packet['canonical_anchor_token_count']} anchor tokens; "
            f"{packet['canonical_high_value_anchor_count']} high-value anchors; "
            f"divisions {top_mapping(packet['outside_division_counts'])}; "
            f"anchors {packet['top_anchor_forms']}"
        )
    if lane_id == "cultural_historical":
        return (
            f"Domains: {join_values(packet['cultural_domain_labels'], limit=8)}; "
            f"top lemmas: {top_mapping(packet['cultural_top_lemmas'])}"
        )
    if lane_id == "textual_witness":
        return (
            f"English witness divergence {packet['witness_divergence_pct']:.2f}%; "
            f"markers: {join_values(packet['witness_marker_flags'], limit=8)}"
        )
    if lane_id == "divine_name_policy":
        return (
            f"{packet['divine_title_token_count']} divine-title token(s); "
            f"categories {join_values(packet['divine_name_categories'])}; "
            f"witness profiles {packet['divine_witness_profiles']}"
        )
    if lane_id == "poetic_rhetorical":
        return (
            f"Band {packet['poetic_pressure_band']}; "
            f"score {packet['poetic_priority_score']:.2f}; "
            f"features {join_values(packet['poetic_feature_flags'], limit=8)}"
        )
    if lane_id in {"jewish_reception", "christian_reception", "academic_comparison"}:
        return (
            f"Frames: {join_values(packet['reception_required_frames'], limit=8)}; "
            f"case families: {join_values(packet['reception_case_family_labels'], limit=8)}"
        )
    if lane_id == "release_authority":
        return (
            f"{packet['blocking_lane_count']} blocking lane(s); unit authority score "
            f"{packet['unit_authority_score_pct']:.2f}%; weakest lanes "
            f"{join_values(packet['weakest_required_lanes'], limit=8)}"
        )
    return ""


def build_decision_rows(packet_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for packet in packet_rows:
        for lane_index, lane_id in enumerate(packet["required_decision_lanes"], start=1):
            lane = DECISION_LANES[lane_id]
            rows.append(
                {
                    "decision_id": f"{packet['packet_id']}_{lane_index:02d}_{lane_id}",
                    "packet_id": packet["packet_id"],
                    "unit_id": packet["unit_id"],
                    "ref": packet["ref"],
                    "lane_id": lane_id,
                    "lane": lane["label"],
                    "reviewer_role": lane["reviewer_role"],
                    "current_data": decision_current_data(packet, lane_id),
                    "decision_prompt": lane["decision_prompt"],
                    "forbidden_shortcut": lane["forbidden_shortcut"],
                    "authority_effect": lane["authority_effect"],
                    "status": "pending_not_signed_off",
                    "reviewer": "",
                    "decision": "",
                    "notes": "",
                    "signed_off_at": "",
                }
            )
    return rows


def build_lane_rows(decision_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in decision_rows:
        grouped.setdefault(str(row["lane_id"]), []).append(row)
    rows = []
    for lane_id, rows_for_lane in grouped.items():
        lane = DECISION_LANES[lane_id]
        rows.append(
            {
                "lane_id": lane_id,
                "lane": lane["label"],
                "decision_row_count": len(rows_for_lane),
                "unit_count": len({row["unit_id"] for row in rows_for_lane}),
                "reviewer_role": lane["reviewer_role"],
                "pending_count": sum(
                    1 for row in rows_for_lane if row["status"].startswith("pending")
                ),
                "control": lane["forbidden_shortcut"],
            }
        )
    return sorted(rows, key=lambda row: int(row["decision_row_count"]), reverse=True)


def build_role_rows(decision_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    units: dict[str, set[str]] = {}
    for row in decision_rows:
        for role in str(row["reviewer_role"]).split(";"):
            role = role.strip()
            if not role:
                continue
            counts[role] += 1
            units.setdefault(role, set()).add(str(row["unit_id"]))
    return [
        {
            "reviewer_role": role,
            "decision_row_count": count,
            "unit_count": len(units[role]),
            "status": "pending_not_signed_off",
        }
        for role, count in counts.most_common()
    ]


def build_psalm_rows(packet_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for packet in packet_rows:
        grouped.setdefault(str(packet["psalm_id"]), []).append(packet)
    rows = []
    for psalm_id, packets in grouped.items():
        top = max(packets, key=lambda row: float(row["integration_pressure_score"]))
        rows.append(
            {
                "psalm_id": psalm_id,
                "psalm": f"Psalm {int(psalm_id.removeprefix('ps'))}",
                "packet_count": len(packets),
                "decision_row_count": sum(int(row["required_decision_count"]) for row in packets),
                "mean_integration_pressure_score": mean(
                    [float(row["integration_pressure_score"]) for row in packets]
                ),
                "top_ref": top["ref"],
                "top_integration_pressure_score": top["integration_pressure_score"],
            }
        )
    return sorted(rows, key=lambda row: float(row["top_integration_pressure_score"]), reverse=True)


def csv_packet_rows(packet_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for packet in packet_rows:
        row = dict(packet)
        for key, value in list(row.items()):
            if isinstance(value, list):
                row[key] = join_values(value)
            elif isinstance(value, dict):
                row[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        rows.append(row)
    return rows


def build_summary(
    packet_rows: list[dict[str, Any]],
    decision_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    role_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    top = packet_rows[0] if packet_rows else {}
    jc_count = sum(1 for row in packet_rows if "jewish_reception" in row["required_decision_lanes"])
    divine_count = sum(
        1 for row in packet_rows if "divine_name_policy" in row["required_decision_lanes"]
    )
    poetic_count = sum(
        1 for row in packet_rows if "poetic_rhetorical" in row["required_decision_lanes"]
    )
    return {
        "collision_packet_count": len(packet_rows),
        "decision_row_count": len(decision_rows),
        "lane_count": len(lane_rows),
        "reviewer_role_count": len(role_rows),
        "pending_decision_count": sum(
            1 for row in decision_rows if row["status"] == "pending_not_signed_off"
        ),
        "completed_decision_count": 0,
        "completion_pct": 0.0,
        "jewish_christian_packet_count": jc_count,
        "divine_name_policy_packet_count": divine_count,
        "poetic_rhetorical_packet_count": poetic_count,
        "mean_decisions_per_packet": mean(
            [float(row["required_decision_count"]) for row in packet_rows]
        ),
        "mean_integration_pressure_score": mean(
            [float(row["integration_pressure_score"]) for row in packet_rows]
        ),
        "top_packet_id": top.get("packet_id", ""),
        "top_unit_id": top.get("unit_id", ""),
        "top_ref": top.get("ref", ""),
        "top_integration_pressure_score": top.get("integration_pressure_score", 0.0),
        "source_artifact_count": len(SOURCE_PATHS),
        "authority_verdict": (
            "collision_packets_not_authority: packets and decision rows are reviewer "
            "workload scaffolding only; no source approval, interpretive adjudication, "
            "canonical wording, or release signoff is recorded."
        ),
    }


def build_visual_data(
    packet_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    role_rows: list[dict[str, Any]],
    psalm_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "packet_pressure_rows": [
            {"label": row["ref"], "value": row["integration_pressure_score"]} for row in packet_rows
        ],
        "lane_workload_rows": [
            {"label": row["lane"], "value": row["decision_row_count"]} for row in lane_rows
        ],
        "role_workload_rows": [
            {"label": row["reviewer_role"], "value": row["decision_row_count"]} for row in role_rows
        ],
        "psalm_packet_rows": [
            {"label": row["psalm"], "value": row["decision_row_count"]} for row in psalm_rows
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    packet_rows = build_packet_rows(data)
    decision_rows = build_decision_rows(packet_rows)
    lane_rows = build_lane_rows(decision_rows)
    role_rows = build_role_rows(decision_rows)
    psalm_rows = build_psalm_rows(packet_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "doctoral collision review packets generated; not signed off",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "method": {
            "collision_definition": (
                "Unit has whole-Tanakh three-division evidence, cultural/historical "
                "domain evidence, textual-witness pressure, and either reception "
                "sensitivity or Jewish/Christian separation in the context integration matrix."
            ),
            "packet_boundary": (
                "Packets organize review decisions only; they do not approve source use, "
                "interpretation, translation wording, model training data, or release."
            ),
            "decision_lanes": DECISION_LANES,
        },
        "summary": build_summary(packet_rows, decision_rows, lane_rows, role_rows),
        "packet_rows": packet_rows,
        "decision_rows": decision_rows,
        "lane_rows": lane_rows,
        "role_rows": role_rows,
        "psalm_rows": psalm_rows,
        "visual_data": build_visual_data(packet_rows, lane_rows, role_rows, psalm_rows),
    }


def metric_cards(cards: list[tuple[str, str, str]]) -> str:
    return (
        '<div class="grid">'
        + "".join(
            (
                '<div class="card">'
                f'<div class="metric">{esc(value)}</div>'
                f'<div class="label">{esc(label)}</div>'
                f"<p>{esc(note)}</p>"
                "</div>"
            )
            for label, value, note in cards
        )
        + "</div>"
    )


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        body_rows.append("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    limit: int = 20,
) -> str:
    chart_rows = rows[:limit]
    width = 980
    left = 260
    right = 60
    bar_height = 20
    gap = 10
    height = 40 + len(chart_rows) * (bar_height + gap)
    max_value = max([float(row[value_key]) for row in chart_rows] or [1.0])
    items = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    usable_width = width - left - right
    for index, row in enumerate(chart_rows):
        y = 24 + index * (bar_height + gap)
        value = float(row[value_key])
        bar_width = 0 if max_value == 0 else value / max_value * usable_width
        label = str(row[label_key])
        if len(label) > 42:
            label = label[:39] + "..."
        items.append(
            f'<text x="{left - 12}" y="{y + 15}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(label)}</text>'
        )
        items.append(
            f'<rect x="{left}" y="{y}" width="{bar_width:.1f}" height="{bar_height}" '
            f'rx="3" fill="{color}"/>'
        )
        items.append(
            f'<text x="{left + bar_width + 8:.1f}" y="{y + 15}" '
            f'font-size="12" font-weight="700" fill="#24313a">{value:g}</text>'
        )
    items.append("</svg>")
    return "".join(items)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    packet_table_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['integration_pressure_score']:.2f}",
            row["active_lens_count"],
            row["required_decision_count"],
            join_values(row["required_review_roles"]),
            join_values(row["cultural_domain_labels"], limit=5),
            f"{row['witness_divergence_pct']:.2f}%",
            join_values(row["reception_required_frames"], limit=6),
            row["next_action"],
        ]
        for row in report["packet_rows"]
    ]
    decision_table_rows = [
        [
            row["ref"],
            row["lane"],
            row["reviewer_role"],
            row["current_data"],
            row["decision_prompt"],
            row["status"],
        ]
        for row in report["decision_rows"][:80]
    ]
    lane_table_rows = [
        [
            row["lane"],
            row["decision_row_count"],
            row["unit_count"],
            row["reviewer_role"],
            row["control"],
        ]
        for row in report["lane_rows"]
    ]
    role_table_rows = [
        [
            row["reviewer_role"],
            row["decision_row_count"],
            row["unit_count"],
            row["status"],
        ]
        for row in report["role_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Doctoral Collision Review Packets</title>
  <style>
    :root {{
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
      background: #fff;
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
    <h1>Doctoral Collision Review Packets</h1>
    <p class="lede">
      Reviewer packet scaffold for the Psalm units where broader-canon anchors,
      cultural/historical domains, textual-witness pressure, and reception
      sensitivity collide. Rows are pending decisions, not approvals.
    </p>
    <p class="meta">
      Generated {esc(report["generated_on"])} from {len(SOURCE_PATHS)} source artifacts.
    </p>
  </header>
  <main>
    <section>
      <h2>Summary</h2>
      <div class="warning">{esc(summary["authority_verdict"])}</div>
      {
        metric_cards(
            [
                (
                    "Packets",
                    f"{summary['collision_packet_count']:,}",
                    "Cross-lens units requiring packetized review.",
                ),
                (
                    "Decision rows",
                    f"{summary['decision_row_count']:,}",
                    "Every row is pending signoff.",
                ),
                ("Lanes", f"{summary['lane_count']:,}", "Distinct review decision lanes."),
                (
                    "Reviewer roles",
                    f"{summary['reviewer_role_count']:,}",
                    "Roles needed across packets.",
                ),
                (
                    "J/C packets",
                    f"{summary['jewish_christian_packet_count']:,}",
                    "Require separated Jewish and Christian lanes.",
                ),
                (
                    "Divine-name packets",
                    f"{summary['divine_name_policy_packet_count']:,}",
                    "Need explicit divine-name/title policy review.",
                ),
                (
                    "Poetic packets",
                    f"{summary['poetic_rhetorical_packet_count']:,}",
                    "Need poetic or layer-preservation review.",
                ),
                (
                    "Top packet",
                    summary["top_ref"],
                    f"Score {summary['top_integration_pressure_score']:.2f}.",
                ),
            ]
        )
    }
    </section>

    <section>
      <h2>Packet Pressure</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["packet_pressure_rows"],
            label_key="label",
            value_key="value",
            aria_label="Collision packet integration pressure",
            color="#7c5b2f",
            limit=20,
        )
    }</div>
      {
        table(
            [
                "Rank",
                "Ref",
                "Score",
                "Lenses",
                "Decisions",
                "Roles",
                "Culture Domains",
                "Witness Div.",
                "Reception Frames",
                "Next Action",
            ],
            packet_table_rows,
        )
    }
    </section>

    <section>
      <h2>Decision Workload</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["lane_workload_rows"],
            label_key="label",
            value_key="value",
            aria_label="Collision packet decision workload by lane",
            color="#2f6f73",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["role_workload_rows"],
            label_key="label",
            value_key="value",
            aria_label="Collision packet decision workload by reviewer role",
            color="#8a6426",
            limit=12,
        )
    }</div>
      {
        table(
            ["Lane", "Decisions", "Units", "Reviewer Roles", "Control"],
            lane_table_rows,
        )
    }
      {
        table(
            ["Reviewer Role", "Decision Rows", "Units", "Status"],
            role_table_rows,
        )
    }
    </section>

    <section>
      <h2>Pending Decisions</h2>
      {
        table(
            ["Ref", "Lane", "Reviewer Role", "Current Data", "Decision Prompt", "Status"],
            decision_table_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate reviewer packets for integrated doctoral context collision units."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--packet-csv-output", type=Path, default=DEFAULT_PACKET_CSV_OUTPUT)
    parser.add_argument("--decision-csv-output", type=Path, default=DEFAULT_DECISION_CSV_OUTPUT)
    parser.add_argument("--lane-csv-output", type=Path, default=DEFAULT_LANE_CSV_OUTPUT)
    parser.add_argument("--role-csv-output", type=Path, default=DEFAULT_ROLE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.packet_csv_output, csv_packet_rows(report["packet_rows"]))
    write_csv(args.decision_csv_output, report["decision_rows"])
    write_csv(args.lane_csv_output, report["lane_rows"])
    write_csv(args.role_csv_output, report["role_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.packet_csv_output}")
    print(f"Wrote {args.decision_csv_output}")
    print(f"Wrote {args.lane_csv_output}")
    print(f"Wrote {args.role_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
