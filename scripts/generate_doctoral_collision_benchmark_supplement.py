from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from generate_local_model_benchmark_suite import (
    BENCHMARK_LAYERS,
    counter_rows,
    estimate_task_chars,
    metric_cards,
    svg_horizontal_bars,
    table,
    task_rubric,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"
CONTENT_ROOT = ROOT / "content" / "psalms"
MODEL_DATA_PATH = ROOT / "docs" / "research" / "local_translation_model_data.json"
COLLISION_PACKETS_PATH = REPORT_ROOT / "doctoral_collision_review_packets.json"
OUTPUT_SCHEMA_PATH = ROOT / "app" / "llm" / "contracts" / "generation_output.schema.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "doctoral_collision_benchmark_supplement_suite.json"
DEFAULT_JSONL_OUTPUT = REPORT_ROOT / "doctoral_collision_benchmark_supplement_tasks.jsonl"
DEFAULT_CSV_OUTPUT = REPORT_ROOT / "doctoral_collision_benchmark_supplement_tasks.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "doctoral_collision_benchmark_supplement_suite.html"

SUPPLEMENT_SEED_BASE = 2026061640

DOMAIN_TAGS = {
    "Nations, Geography, and Identity": {"nations", "land_geography", "identity"},
    "Creation, Cosmos, and Nature": {"creation_cosmos", "creation_hymn"},
    "Covenant, Torah, and Wisdom": {"covenant", "torah_psalm", "wisdom"},
    "Kingship, Davidic, and Political Order": {"royal_psalm", "kingdom"},
    "Justice, Enemy, and Violence": {"lament", "enemy_violence", "imprecation"},
    "Temple, Cult, and Sacred Space": {"temple_cult_liturgy", "zion"},
    "Poverty, Affliction, and Social Order": {"lament", "righteous_sufferer"},
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def unit_path(unit_id: str) -> Path:
    psalm_id = unit_id.split(".")[0]
    return CONTENT_ROOT / psalm_id / f"{unit_id}.json"


def compact_task_token(token: dict[str, Any]) -> dict[str, Any]:
    features = token.get("compiler_features") or {}
    return {
        "token_id": token.get("token_id"),
        "surface": token.get("surface"),
        "normalized": token.get("normalized"),
        "lemma": token.get("lemma"),
        "strong": token.get("strong"),
        "morph_code": token.get("morph_code"),
        "morph_readable": token.get("morph_readable"),
        "display_gloss": token.get("display_gloss"),
        "word_sense": token.get("word_sense"),
        "part_of_speech": token.get("part_of_speech"),
        "stem": token.get("stem"),
        "syntax_role": token.get("syntax_role"),
        "semantic_role": token.get("semantic_role"),
        "referent": token.get("referent"),
        "psalms_occurrence_refs": token.get("psalms_occurrence_refs") or [],
        "corpus_occurrence_refs": token.get("corpus_occurrence_refs") or [],
        "greek": token.get("greek"),
        "missing_enrichments": token.get("missing_enrichments") or [],
        "compiler_features": {
            "component_count": features.get("component_count"),
            "construct_state": features.get("construct_state"),
            "divine_name": features.get("divine_name"),
            "suffix_pronoun": features.get("suffix_pronoun"),
            "preposition_role": features.get("preposition_role"),
            "discourse_marker": features.get("discourse_marker"),
            "conjunction_role": features.get("conjunction_role"),
            "english_parts": features.get("english_parts") or [],
            "gloss_fragments": features.get("gloss_fragments") or [],
        },
    }


def compact_witness(witness: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": witness.get("source_id"),
        "language": witness.get("language"),
        "witness_role": witness.get("witness_role"),
        "version_title": witness.get("versionTitle") or witness.get("version_title"),
        "source_version": witness.get("source_version"),
        "text": witness.get("text"),
    }


def decisions_by_packet(decision_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in decision_rows:
        grouped[str(row["packet_id"])].append(row)
    return grouped


def derive_benchmark_tags(packet: dict[str, Any]) -> list[str]:
    tags = {
        "doctoral_collision",
        "doctoral_collision_supplement",
        "whole_tanakh_context",
        "canonical_intertext",
        "source_control",
        "review_signoff_required",
    }
    if int(packet.get("canonical_high_value_anchor_count") or 0):
        tags.add("high_value_anchor")
    for label in packet.get("cultural_domain_labels", []):
        tags.update(DOMAIN_TAGS.get(str(label), set()))
    if "textual_witness" in packet.get("required_decision_lanes", []):
        tags.add("textual_witness")
    if "divine_name_policy" in packet.get("required_decision_lanes", []):
        tags.add("divine_name_policy")
    if "poetic_rhetorical" in packet.get("required_decision_lanes", []):
        tags.add("parallelism")
        tags.add("source_image_pressure")
        tags.add("poetic_rhetorical_pressure")
    reception_lanes = {"jewish_reception", "christian_reception", "academic_comparison"}
    if reception_lanes.intersection(packet.get("required_decision_lanes", [])):
        tags.add("reception_history")
        tags.add("jewish_christian_reception")
    if safe_float(packet.get("witness_divergence_pct")) >= 40:
        tags.add("textual_sensitivity")
    if "ancient_near_eastern_context" in packet.get("packet_families", []):
        tags.add("ancient_cultural_context")
    if "release_authority" in packet.get("required_decision_lanes", []):
        tags.add("authority_blocked")
    return sorted(tags)


def compact_decision(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": row.get("decision_id"),
        "lane_id": row.get("lane_id"),
        "lane": row.get("lane"),
        "reviewer_role": row.get("reviewer_role"),
        "current_data": row.get("current_data"),
        "decision_prompt": row.get("decision_prompt"),
        "forbidden_shortcut": row.get("forbidden_shortcut"),
        "authority_effect": row.get("authority_effect"),
        "status": row.get("status"),
    }


def locked_inputs_for_packet(
    *,
    unit: dict[str, Any],
    packet: dict[str, Any],
    packet_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    tokens = unit.get("tokens", [])
    return {
        "source": {
            "unit_id": unit["unit_id"],
            "ref": unit["ref"],
            "source_hebrew": unit["source_hebrew"],
            "source_transliteration": unit.get("source_transliteration"),
            "token_count": len(tokens),
            "tokens": [compact_task_token(token) for token in tokens],
        },
        "doctoral_collision_context": {
            "packet_id": packet.get("packet_id"),
            "rank": packet.get("rank"),
            "integration_pressure_score": packet.get("integration_pressure_score"),
            "integration_pressure_band": packet.get("integration_pressure_band"),
            "active_lens_count": packet.get("active_lens_count"),
            "active_lens_labels": packet.get("active_lens_labels", []),
            "required_decision_count": packet.get("required_decision_count"),
            "required_decision_lanes": packet.get("required_decision_lanes", []),
            "required_review_roles": packet.get("required_review_roles", []),
            "weakest_required_lanes": packet.get("weakest_required_lanes", []),
            "blocking_lane_count": packet.get("blocking_lane_count"),
            "unit_authority_score_pct": packet.get("unit_authority_score_pct"),
            "canonical_anchor_token_count": packet.get("canonical_anchor_token_count"),
            "canonical_anchor_token_pct": packet.get("canonical_anchor_token_pct"),
            "canonical_high_value_anchor_count": packet.get("canonical_high_value_anchor_count"),
            "outside_division_counts": packet.get("outside_division_counts", {}),
            "outside_book_counts": packet.get("outside_book_counts", {}),
            "top_anchor_forms": packet.get("top_anchor_forms"),
            "cultural_domain_labels": packet.get("cultural_domain_labels", []),
            "cultural_domain_counts": packet.get("cultural_domain_counts", {}),
            "cultural_top_lemmas": packet.get("cultural_top_lemmas", {}),
            "witness_divergence_pct": packet.get("witness_divergence_pct"),
            "witness_marker_flags": packet.get("witness_marker_flags", []),
            "english_witness_excerpts": {
                "kjv": packet.get("kjv_excerpt"),
                "asv": packet.get("asv_excerpt"),
                "web": packet.get("web_excerpt"),
            },
            "divine_title_token_count": packet.get("divine_title_token_count"),
            "divine_name_categories": packet.get("divine_name_categories", []),
            "divine_witness_profiles": packet.get("divine_witness_profiles", {}),
            "divine_witness_disagreement": packet.get("divine_witness_disagreement"),
            "poetic_pressure_band": packet.get("poetic_pressure_band"),
            "poetic_priority_score": packet.get("poetic_priority_score"),
            "poetic_feature_flags": packet.get("poetic_feature_flags", []),
            "reception_priority_score": packet.get("reception_priority_score"),
            "reception_required_frames": packet.get("reception_required_frames", []),
            "reception_case_family_labels": packet.get("reception_case_family_labels", []),
            "packet_families": packet.get("packet_families", []),
            "claim_controls": packet.get("claim_controls", []),
            "allowed_claim_lanes": packet.get("allowed_claim_lanes", {}),
            "pending_decisions": [compact_decision(row) for row in packet_decisions],
        },
        "witnesses": [compact_witness(witness) for witness in unit.get("witnesses", [])],
        "evidence_policy": {
            "canonical_basis": "UXLC/WLC-derived Hebrew source tokens",
            "translation_text_boundary": (
                "Visible translation text may use only the Hebrew source basis and approved "
                "project policies; reception and academic claims belong in tagged rationale."
            ),
            "whole_tanakh_boundary": (
                "Whole-Tanakh anchors are retrieval and review-routing evidence; they are "
                "not lemma proof, allusion proof, or independent wording authority."
            ),
            "witness_boundary": (
                "English witnesses and the LXX are comparison evidence only; they must not "
                "silently override the Hebrew source."
            ),
            "reception_boundary": (
                "Jewish, Christian, liturgical, and academic frames must remain separated "
                "unless a signed reviewer decision authorizes a labeled comparison."
            ),
            "signoff_boundary": (
                "Collision packet decisions are pending. This benchmark can test model "
                "behavior but cannot approve source use, interpretation, canonical wording, "
                "training data, or release."
            ),
        },
    }


def task_for_layer(
    *,
    unit: dict[str, Any],
    packet: dict[str, Any],
    packet_decisions: list[dict[str, Any]],
    layer_def: dict[str, Any],
    task_index: int,
) -> dict[str, Any]:
    layer = str(layer_def["layer"])
    task_id = f"bench.collision.{unit['unit_id']}.{layer}"
    tags = derive_benchmark_tags(packet)
    generation_input = {
        "unit_id": unit["unit_id"],
        "layer": layer,
        "locked_inputs": locked_inputs_for_packet(
            unit=unit,
            packet=packet,
            packet_decisions=packet_decisions,
        ),
        "style_profile": layer_def["style_profile"],
        "candidate_count": 3,
        "seed": SUPPLEMENT_SEED_BASE + task_index,
        "model_profile_id": "{model_profile_id}",
    }
    benchmark = {
        "task_id": task_id,
        "prompt_file": layer_def["prompt_file"],
        "required_output_schema": "app/llm/contracts/generation_output.schema.json",
        "rubric": task_rubric(tags, layer),
        "must_check": [
            "JSON schema validity",
            "valid unit_id and layer",
            "valid token IDs in alignment_hints and preserved_source_images",
            "translation_basis uses Hebrew source unless explicitly testing LXX",
            "English witnesses are labeled witnesses and blocked as generation sources",
            "whole-Tanakh anchors are contextual pressure, not lexical proof",
            "Jewish, Christian, and academic frames remain separated in rationale",
            "no reception-history claim appears inside the translation text",
            "divine-name/title rendering follows project policy rather than witness majority",
            "pending reviewer decisions are not represented as signoff",
        ],
        "supplement_reason": (
            "Generated from doctoral collision review packets to test local models on "
            "units where Hebrew basis, whole-Tanakh context, cultural domains, textual "
            "witnesses, divine-name policy, poetics, and reception frames collide."
        ),
    }
    task = {
        "task_id": task_id,
        "packet_id": packet["packet_id"],
        "unit_id": unit["unit_id"],
        "ref": unit["ref"],
        "layer": layer,
        "benchmark_tags": tags,
        "token_count": len(unit.get("tokens", [])),
        "integration_pressure_score": packet.get("integration_pressure_score", 0),
        "integration_pressure_band": packet.get("integration_pressure_band", ""),
        "active_lens_count": packet.get("active_lens_count", 0),
        "required_decision_count": packet.get("required_decision_count", 0),
        "required_decision_lanes": packet.get("required_decision_lanes", []),
        "required_review_roles": packet.get("required_review_roles", []),
        "canonical_anchor_token_count": packet.get("canonical_anchor_token_count", 0),
        "canonical_high_value_anchor_count": packet.get("canonical_high_value_anchor_count", 0),
        "witness_divergence_pct": packet.get("witness_divergence_pct", 0),
        "divine_name_categories": packet.get("divine_name_categories", []),
        "poetic_pressure_band": packet.get("poetic_pressure_band", ""),
        "reception_required_frames": packet.get("reception_required_frames", []),
        "source_priority": "doctoral_collision_review_packets",
        "generation_input": generation_input,
        "benchmark": benchmark,
    }
    task["estimated_payload_chars"] = estimate_task_chars(generation_input, benchmark)
    return task


def make_tasks(collision_report: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    tasks: list[dict[str, Any]] = []
    errors: list[str] = []
    decisions = decisions_by_packet(collision_report.get("decision_rows", []))
    task_index = 0
    for packet in collision_report.get("packet_rows", []):
        unit_id = str(packet["unit_id"])
        path = unit_path(unit_id)
        if not path.exists():
            errors.append(f"{packet['packet_id']}: missing unit content {path.relative_to(ROOT)}")
            continue
        unit = load_json(path)
        packet_decisions = decisions.get(str(packet["packet_id"]), [])
        for layer_def in BENCHMARK_LAYERS:
            task_index += 1
            tasks.append(
                task_for_layer(
                    unit=unit,
                    packet=packet,
                    packet_decisions=packet_decisions,
                    layer_def=layer_def,
                    task_index=task_index,
                )
            )
    return tasks, errors


def validate_task_shape(task: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    generation_input = task.get("generation_input") or {}
    required = [
        "unit_id",
        "layer",
        "locked_inputs",
        "style_profile",
        "candidate_count",
        "seed",
        "model_profile_id",
    ]
    for field in required:
        if field not in generation_input:
            errors.append(f"{task.get('task_id')}: missing generation_input.{field}")
    if generation_input.get("layer") != task.get("layer"):
        errors.append(f"{task.get('task_id')}: layer mismatch")
    if generation_input.get("unit_id") != task.get("unit_id"):
        errors.append(f"{task.get('task_id')}: unit_id mismatch")
    source = generation_input.get("locked_inputs", {}).get("source", {})
    token_ids = [
        str(token.get("token_id") or "")
        for token in source.get("tokens", [])
        if token.get("token_id")
    ]
    if len(token_ids) != len(set(token_ids)):
        errors.append(f"{task.get('task_id')}: duplicate source token IDs")
    if int(task.get("token_count") or 0) != int(source.get("token_count") or 0):
        errors.append(f"{task.get('task_id')}: token_count mismatch")
    if not task.get("packet_id"):
        errors.append(f"{task.get('task_id')}: missing packet_id")
    return errors


def summarize(
    *,
    tasks: list[dict[str, Any]],
    collision_report: dict[str, Any],
    model_data: dict[str, Any],
) -> dict[str, Any]:
    chars = [int(task["estimated_payload_chars"]) for task in tasks]
    layer_counts = Counter(str(task["layer"]) for task in tasks)
    tag_counts: Counter[str] = Counter()
    lane_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    band_counts: Counter[str] = Counter()
    units = {str(task["unit_id"]) for task in tasks}
    for task in tasks:
        tag_counts.update(str(tag) for tag in task.get("benchmark_tags", []))
        lane_counts.update(str(lane) for lane in task.get("required_decision_lanes", []))
        role_counts.update(str(role) for role in task.get("required_review_roles", []))
        band_counts[str(task.get("integration_pressure_band", ""))] += 1

    planned_models = model_data.get("recommended_bakeoff_models", [])
    packet_summary = collision_report.get("summary", {})
    return {
        "source_collision_packet_count": packet_summary.get("collision_packet_count", 0),
        "selected_collision_unit_count": len(units),
        "task_count": len(tasks),
        "layer_counts": dict(sorted(layer_counts.items())),
        "token_instances": sum(int(task["token_count"]) for task in tasks),
        "candidate_count_per_task": 3,
        "planned_model_count": len(planned_models),
        "planned_model_runs": len(tasks) * len(planned_models),
        "source_pending_decision_count": packet_summary.get("pending_decision_count", 0),
        "task_lane_evaluation_count": sum(
            len(task.get("required_decision_lanes", [])) for task in tasks
        ),
        "mean_decisions_per_task": round(
            statistics.mean(float(task.get("required_decision_count") or 0) for task in tasks),
            2,
        )
        if tasks
        else 0,
        "jewish_christian_task_count": sum(
            1 for task in tasks if "jewish_christian_reception" in task["benchmark_tags"]
        ),
        "divine_name_task_count": sum(
            1 for task in tasks if "divine_name_policy" in task["benchmark_tags"]
        ),
        "poetic_rhetorical_task_count": sum(
            1 for task in tasks if "poetic_rhetorical_pressure" in task["benchmark_tags"]
        ),
        "textual_witness_task_count": sum(
            1 for task in tasks if "textual_witness" in task["benchmark_tags"]
        ),
        "top_selected_packet_id": packet_summary.get("top_packet_id", ""),
        "top_selected_unit": packet_summary.get("top_unit_id", ""),
        "top_selected_ref": packet_summary.get("top_ref", ""),
        "top_selected_integration_pressure_score": packet_summary.get(
            "top_integration_pressure_score",
            0,
        ),
        "mean_integration_pressure_score": packet_summary.get(
            "mean_integration_pressure_score",
            0,
        ),
        "estimated_payload_chars": {
            "min": min(chars) if chars else 0,
            "max": max(chars) if chars else 0,
            "mean": round(statistics.mean(chars), 2) if chars else 0,
            "median": round(statistics.median(chars), 2) if chars else 0,
        },
        "benchmark_tag_counts": dict(tag_counts.most_common()),
        "decision_lane_task_counts": dict(lane_counts.most_common()),
        "review_role_task_counts": dict(role_counts.most_common()),
        "pressure_band_task_counts": dict(band_counts.most_common()),
        "authority_verdict": (
            "collision_benchmark_not_authority: generated gloss/literal tasks test model "
            "behavior against pending collision packets only; they do not approve sources, "
            "interpretation, canonical wording, model training data, or release."
        ),
    }


def build_visual_data(
    *,
    tasks: list[dict[str, Any]],
    collision_report: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    seen_packets: set[str] = set()
    packet_pressure_rows: list[dict[str, Any]] = []
    for task in tasks:
        packet_id = str(task["packet_id"])
        if packet_id in seen_packets:
            continue
        seen_packets.add(packet_id)
        packet_pressure_rows.append(
            {
                "label": task["ref"],
                "value": safe_float(task.get("integration_pressure_score")),
            }
        )
    return {
        "packet_pressure_rows": packet_pressure_rows,
        "lane_workload_rows": collision_report.get("visual_data", {}).get(
            "lane_workload_rows",
            [],
        ),
        "role_workload_rows": collision_report.get("visual_data", {}).get(
            "role_workload_rows",
            [],
        ),
        "tag_rows": counter_rows(summary["benchmark_tag_counts"], "tag"),
        "task_lane_rows": counter_rows(summary["decision_lane_task_counts"], "lane"),
        "layer_rows": counter_rows(summary["layer_counts"], "layer"),
    }


def build_suite(
    *,
    model_data_path: Path,
    collision_packets_path: Path,
    output_schema_path: Path,
) -> dict[str, Any]:
    model_data = load_json(model_data_path)
    collision_report = load_json(collision_packets_path)
    output_schema = load_json(output_schema_path)
    tasks, load_errors = make_tasks(collision_report)
    validation_errors = load_errors
    for task in tasks:
        validation_errors.extend(validate_task_shape(task))
    summary = summarize(
        tasks=tasks,
        collision_report=collision_report,
        model_data=model_data,
    )
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": (
            "generated doctoral collision benchmark supplement; tasks are ready for local "
            "model runs but not scored"
        ),
        "source_paths": {
            "model_data": str(model_data_path.relative_to(ROOT)),
            "doctoral_collision_review_packets": str(collision_packets_path.relative_to(ROOT)),
            "unit_content_root": "content/psalms",
            "generation_output_schema": str(output_schema_path.relative_to(ROOT)),
        },
        "selection": {
            "method": (
                "all doctoral collision review packets, expanded into gloss and literal "
                "benchmark layers"
            ),
            "selected_packet_ids": [
                str(packet["packet_id"]) for packet in collision_report.get("packet_rows", [])
            ],
            "selected_unit_ids": [
                str(packet["unit_id"]) for packet in collision_report.get("packet_rows", [])
            ],
        },
        "output_schema_title": output_schema.get("title"),
        "recommended_bakeoff_models": model_data.get("recommended_bakeoff_models", []),
        "summary": summary,
        "validation_errors": validation_errors,
        "visual_data": build_visual_data(
            tasks=tasks,
            collision_report=collision_report,
            summary=summary,
        ),
        "tasks": tasks,
    }


def csv_task_rows(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for task in tasks:
        rows.append(
            {
                "task_id": task["task_id"],
                "packet_id": task["packet_id"],
                "unit_id": task["unit_id"],
                "ref": task["ref"],
                "layer": task["layer"],
                "token_count": task["token_count"],
                "integration_pressure_score": task["integration_pressure_score"],
                "integration_pressure_band": task["integration_pressure_band"],
                "active_lens_count": task["active_lens_count"],
                "required_decision_count": task["required_decision_count"],
                "required_decision_lanes": task["required_decision_lanes"],
                "required_review_roles": task["required_review_roles"],
                "benchmark_tags": task["benchmark_tags"],
                "witness_divergence_pct": task["witness_divergence_pct"],
                "estimated_payload_chars": task["estimated_payload_chars"],
            }
        )
    return rows


def render_html(suite: dict[str, Any]) -> str:
    summary = suite["summary"]
    visual = suite["visual_data"]
    task_rows = [
        [
            task["task_id"],
            task["ref"],
            task["layer"],
            f"{float(task['integration_pressure_score']):.2f}",
            task["active_lens_count"],
            task["required_decision_count"],
            "; ".join(task["required_decision_lanes"]),
            "; ".join(task["required_review_roles"]),
            fmt_int(task["estimated_payload_chars"]),
        ]
        for task in suite["tasks"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Doctoral Collision Benchmark Supplement</title>
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
    <h1>Doctoral Collision Benchmark Supplement</h1>
    <p class="lede">
      Gloss and literal tasks for the Psalm units where Hebrew basis,
      whole-Tanakh context, cultural domains, textual witnesses, divine-name
      policy, poetics, and reception frames collide. The tasks are model
      evaluation workload, not review completion.
    </p>
    <p class="meta">Generated {suite["generated_on"]}.</p>
  </header>
  <main>
    <section>
      <h2>Supplement Inventory</h2>
      <div class="warning">{summary["authority_verdict"]}</div>
      {
        metric_cards(
            [
                ("Tasks", fmt_int(summary["task_count"]), "Runnable gloss/literal tasks."),
                (
                    "Collision units",
                    fmt_int(summary["selected_collision_unit_count"]),
                    "All packetized collision units selected.",
                ),
                (
                    "Planned runs",
                    fmt_int(summary["planned_model_runs"]),
                    "Tasks multiplied by planned bakeoff models.",
                ),
                (
                    "Pending decisions",
                    fmt_int(summary["source_pending_decision_count"]),
                    "Source reviewer decisions still unsigned.",
                ),
                (
                    "J/C tasks",
                    fmt_int(summary["jewish_christian_task_count"]),
                    "Tasks requiring separated Jewish and Christian frames.",
                ),
                (
                    "Divine-name tasks",
                    fmt_int(summary["divine_name_task_count"]),
                    "Tasks with divine-name/title policy pressure.",
                ),
                (
                    "Poetic tasks",
                    fmt_int(summary["poetic_rhetorical_task_count"]),
                    "Tasks with source-image or rhetoric pressure.",
                ),
                (
                    "Top packet",
                    summary["top_selected_ref"],
                    f"Score {float(summary['top_selected_integration_pressure_score']):.2f}.",
                ),
            ]
        )
    }
    </section>
    <section>
      <h2>Pressure And Workload</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["packet_pressure_rows"],
            label_key="label",
            value_key="value",
            aria_label="Collision benchmark packet pressure",
            color="#7c5b2f",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["task_lane_rows"],
            label_key="lane",
            value_key="count",
            aria_label="Collision benchmark task lane counts",
            color="#2f6f73",
            limit=20,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["tag_rows"],
            label_key="tag",
            value_key="count",
            aria_label="Collision benchmark tag counts",
            color="#9b3d3d",
            limit=20,
        )
    }</div>
    </section>
    <section>
      <h2>Task Inventory</h2>
      {
        table(
            [
                "Task",
                "Ref",
                "Layer",
                "Pressure",
                "Lenses",
                "Decisions",
                "Lanes",
                "Roles",
                "Payload Chars",
            ],
            task_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate benchmark tasks for doctoral collision review packets."
    )
    parser.add_argument("--model-data", type=Path, default=MODEL_DATA_PATH)
    parser.add_argument("--collision-packets", type=Path, default=COLLISION_PACKETS_PATH)
    parser.add_argument("--output-schema", type=Path, default=OUTPUT_SCHEMA_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--jsonl-output", type=Path, default=DEFAULT_JSONL_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suite = build_suite(
        model_data_path=args.model_data,
        collision_packets_path=args.collision_packets,
        output_schema_path=args.output_schema,
    )
    write_json(args.json_output, suite)
    write_jsonl(args.jsonl_output, suite["tasks"])
    write_csv(args.csv_output, csv_task_rows(suite["tasks"]))
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(suite), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.jsonl_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
