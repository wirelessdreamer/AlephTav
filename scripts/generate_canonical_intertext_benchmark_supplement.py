from __future__ import annotations

import argparse
import html
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from generate_local_model_benchmark_suite import (
    BENCHMARK_LAYERS,
    estimate_task_chars,
    task_rubric,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"
CONTENT_ROOT = ROOT / "content" / "psalms"
MODEL_DATA_PATH = ROOT / "docs" / "research" / "local_translation_model_data.json"
ATLAS_PATH = REPORT_ROOT / "canonical_cross_reference_atlas.json"
EXPANDED_SUITE_PATH = REPORT_ROOT / "contextual_expanded_benchmark_suite.json"
RECEPTION_SUITE_PATH = REPORT_ROOT / "reception_signal_benchmark_supplement_suite.json"
OUTPUT_SCHEMA_PATH = ROOT / "app" / "llm" / "contracts" / "generation_output.schema.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "canonical_intertext_benchmark_supplement_suite.json"
DEFAULT_JSONL_OUTPUT = REPORT_ROOT / "canonical_intertext_benchmark_supplement_tasks.jsonl"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "canonical_intertext_benchmark_supplement_suite.html"

DEFAULT_LIMIT = 30
SUPPLEMENT_SEED_BASE = 2026061640

DOMAIN_TAGS = {
    "anthropology_body": {"anthropology", "body_imagery"},
    "covenant_torah_wisdom": {"covenant", "torah_psalm", "wisdom"},
    "creation_cosmos_nature": {"creation_hymn", "cosmos", "nature_imagery"},
    "death_sheol_mortality": {"afterlife_mortality", "death_shadow"},
    "justice_enemy_violence": {"enemy_violence", "imprecation", "justice"},
    "kingship_davidic_political": {"royal_psalm", "messianic_interpretation"},
    "nations_geography_identity": {"nations", "land_geography", "identity"},
    "temple_cult_sacred_space": {"temple_cult_liturgy", "zion", "priesthood"},
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


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


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
        "version_title": witness.get("versionTitle"),
        "source_version": witness.get("source_version"),
        "text": witness.get("text"),
    }


def suite_unit_ids(suite: dict[str, Any]) -> set[str]:
    return {str(task.get("unit_id")) for task in suite.get("tasks", [])}


def derive_benchmark_tags(atlas_row: dict[str, Any]) -> list[str]:
    tags = {"canonical_intertext", "canonical_intertext_supplement", "whole_tanakh_context"}
    if atlas_row.get("has_torah_evidence"):
        tags.add("torah_context")
    if atlas_row.get("has_prophets_evidence"):
        tags.add("prophets_context")
    if atlas_row.get("has_non_psalm_writings_evidence"):
        tags.add("writings_context")
    for domain_id in atlas_row.get("domain_ids", []):
        tags.update(DOMAIN_TAGS.get(str(domain_id), set()))
    if atlas_row.get("ancient_culture_pressure"):
        tags.add("ancient_cultural_context")
    if atlas_row.get("reception_sensitive"):
        tags.add("jewish_christian_reception")
    if atlas_row.get("textual_witness_pressure"):
        tags.add("textual_witness")
    if atlas_row.get("divine_name_overlap"):
        tags.add("divine_name_policy")
    if atlas_row.get("superscription_context_overlap"):
        tags.add("superscription_context")
    return sorted(tags)


def locked_inputs_for_unit(unit: dict[str, Any], atlas_row: dict[str, Any]) -> dict[str, Any]:
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
        "canonical_intertext_context": {
            "priority_score": atlas_row.get("priority_score"),
            "anchor_token_count": atlas_row.get("anchor_token_count"),
            "anchor_token_pct": atlas_row.get("anchor_token_pct"),
            "high_value_anchor_count": atlas_row.get("high_value_anchor_count"),
            "medium_value_anchor_count": atlas_row.get("medium_value_anchor_count"),
            "low_value_anchor_count": atlas_row.get("low_value_anchor_count"),
            "outside_division_counts": atlas_row.get("outside_division_counts", {}),
            "outside_book_counts": atlas_row.get("outside_book_counts", {}),
            "has_torah_evidence": atlas_row.get("has_torah_evidence"),
            "has_prophets_evidence": atlas_row.get("has_prophets_evidence"),
            "has_non_psalm_writings_evidence": atlas_row.get("has_non_psalm_writings_evidence"),
            "has_three_division_evidence": atlas_row.get("has_three_division_evidence"),
            "domain_ids": atlas_row.get("domain_ids", []),
            "domain_labels": atlas_row.get("domain_labels", []),
            "top_anchor_forms": atlas_row.get("top_anchor_forms", []),
            "boundary_flags": {
                "ancient_culture_pressure": atlas_row.get("ancient_culture_pressure"),
                "reception_sensitive": atlas_row.get("reception_sensitive"),
                "textual_witness_pressure": atlas_row.get("textual_witness_pressure"),
                "divine_name_overlap": atlas_row.get("divine_name_overlap"),
                "superscription_context_overlap": atlas_row.get("superscription_context_overlap"),
            },
        },
        "witnesses": [compact_witness(witness) for witness in unit.get("witnesses", [])],
        "evidence_policy": {
            "canonical_basis": "UXLC/WLC-derived Hebrew source tokens",
            "whole_tanakh_boundary": (
                "Non-Psalm anchors are surface-form context and retrieval cues; "
                "they are not lemma proof, diachronic proof, or translation authority."
            ),
            "division_boundary": (
                "Torah, Prophets, and non-Psalm Writings evidence must be cited as "
                "contextual pressure outside the translation string."
            ),
            "witness_boundary": "Witnesses are evidence only, not canonical basis.",
            "supplement_boundary": (
                "This task tests local models on whole-Tanakh intertext pressure "
                "outside current expanded and reception-signal benchmark coverage."
            ),
        },
    }


def task_for_layer(
    *,
    unit: dict[str, Any],
    atlas_row: dict[str, Any],
    layer_def: dict[str, Any],
    task_index: int,
) -> dict[str, Any]:
    layer = str(layer_def["layer"])
    task_id = f"bench.{unit['unit_id']}.{layer}"
    tags = derive_benchmark_tags(atlas_row)
    generation_input = {
        "unit_id": unit["unit_id"],
        "layer": layer,
        "locked_inputs": locked_inputs_for_unit(unit, atlas_row),
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
            "whole-Tanakh anchors cited as context only, never as lexical proof",
            "no Torah/Prophets/Writings context claim inside the translation text",
            "no Jewish/Christian interpretation collapse in rationale or notes",
            "witnesses labeled as witnesses, never as canonical Hebrew basis",
        ],
        "supplement_reason": (
            "Generated from canonical cross-reference atlas rows with high-value "
            "non-Psalm anchors and three-division evidence outside existing suites."
        ),
    }
    task = {
        "task_id": task_id,
        "unit_id": unit["unit_id"],
        "ref": unit["ref"],
        "layer": layer,
        "benchmark_tags": tags,
        "token_count": len(unit.get("tokens", [])),
        "canonical_intertext_priority_score": atlas_row.get("priority_score", 0),
        "anchor_token_count": atlas_row.get("anchor_token_count", 0),
        "anchor_token_pct": atlas_row.get("anchor_token_pct", 0),
        "high_value_anchor_count": atlas_row.get("high_value_anchor_count", 0),
        "domain_ids": atlas_row.get("domain_ids", []),
        "source_priority": "canonical_cross_reference_atlas",
        "generation_input": generation_input,
        "benchmark": benchmark,
    }
    task["estimated_payload_chars"] = estimate_task_chars(generation_input, benchmark)
    return task


def selected_intertext_rows(
    *,
    atlas: dict[str, Any],
    expanded_suite: dict[str, Any],
    reception_suite: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    covered = suite_unit_ids(expanded_suite) | suite_unit_ids(reception_suite)
    rows = [
        row
        for row in atlas.get("unit_rows", [])
        if str(row.get("unit_id")) not in covered
        and row.get("has_three_division_evidence")
        and int(row.get("high_value_anchor_count") or 0) > 0
    ]
    rows.sort(
        key=lambda row: (
            float(row.get("priority_score") or 0),
            int(row.get("high_value_anchor_count") or 0),
            float(row.get("anchor_token_pct") or 0),
        ),
        reverse=True,
    )
    return rows[:limit]


def make_tasks(selected_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    tasks: list[dict[str, Any]] = []
    errors: list[str] = []
    task_index = 0
    layers_by_name = {str(layer["layer"]): layer for layer in BENCHMARK_LAYERS}
    for atlas_row in selected_rows:
        unit_id = str(atlas_row["unit_id"])
        path = unit_path(unit_id)
        if not path.exists():
            errors.append(f"{unit_id}: missing content unit {path.relative_to(ROOT)}")
            continue
        unit = load_json(path)
        for layer in ("gloss", "literal"):
            task_index += 1
            tasks.append(
                task_for_layer(
                    unit=unit,
                    atlas_row=atlas_row,
                    layer_def=layers_by_name[layer],
                    task_index=task_index,
                )
            )
    return tasks, errors


def validate_task_shape(task: dict[str, Any]) -> list[str]:
    errors = []
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
    return errors


def summarize(
    *,
    tasks: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
    atlas: dict[str, Any],
    expanded_suite: dict[str, Any],
    reception_suite: dict[str, Any],
    model_data: dict[str, Any],
) -> dict[str, Any]:
    chars = [int(task["estimated_payload_chars"]) for task in tasks]
    layer_counts = Counter(str(task["layer"]) for task in tasks)
    tags: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    books: Counter[str] = Counter()
    units = {str(task["unit_id"]) for task in tasks}
    for task in tasks:
        tags.update(str(tag) for tag in task.get("benchmark_tags", []))
        domains.update(str(domain) for domain in task.get("domain_ids", []))
    for row in selected_rows:
        books.update(str(book) for book in row.get("outside_book_counts", {}))
    planned_models = model_data.get("recommended_bakeoff_models", [])
    existing_units = suite_unit_ids(expanded_suite) | suite_unit_ids(reception_suite)
    source_candidates = [
        row
        for row in atlas.get("unit_rows", [])
        if row.get("has_three_division_evidence")
        and int(row.get("high_value_anchor_count") or 0) > 0
    ]
    return {
        "source_three_division_high_value_candidate_count": len(source_candidates),
        "existing_covered_unit_count": len(existing_units),
        "selected_intertext_unit_count": len(units),
        "task_count": len(tasks),
        "layer_counts": dict(sorted(layer_counts.items())),
        "token_instances": sum(int(task["token_count"]) for task in tasks),
        "candidate_count_per_task": 3,
        "planned_model_count": len(planned_models),
        "planned_model_runs": len(tasks) * len(planned_models),
        "remaining_intertext_candidate_count": max(0, len(source_candidates) - len(units)),
        "selected_three_division_unit_count": sum(
            1 for row in selected_rows if row.get("has_three_division_evidence")
        ),
        "selected_textual_witness_pressure_count": sum(
            1 for row in selected_rows if row.get("textual_witness_pressure")
        ),
        "selected_reception_sensitive_count": sum(
            1 for row in selected_rows if row.get("reception_sensitive")
        ),
        "selected_ancient_culture_pressure_count": sum(
            1 for row in selected_rows if row.get("ancient_culture_pressure")
        ),
        "top_selected_unit": selected_rows[0]["unit_id"] if selected_rows else "",
        "top_selected_ref": selected_rows[0]["ref"] if selected_rows else "",
        "top_selected_priority_score": selected_rows[0]["priority_score"] if selected_rows else 0,
        "estimated_payload_chars": {
            "min": min(chars) if chars else 0,
            "max": max(chars) if chars else 0,
            "mean": round(statistics.mean(chars), 2) if chars else 0,
            "median": round(statistics.median(chars), 2) if chars else 0,
        },
        "benchmark_tag_counts": dict(tags.most_common()),
        "domain_counts": dict(domains.most_common()),
        "book_presence_counts": dict(books.most_common(20)),
    }


def build_suite(
    *,
    model_data_path: Path,
    atlas_path: Path,
    expanded_suite_path: Path,
    reception_suite_path: Path,
    output_schema_path: Path,
    limit: int,
) -> dict[str, Any]:
    model_data = load_json(model_data_path)
    atlas = load_json(atlas_path)
    expanded_suite = load_json(expanded_suite_path)
    reception_suite = load_json(reception_suite_path)
    output_schema = load_json(output_schema_path)
    selected_rows = selected_intertext_rows(
        atlas=atlas,
        expanded_suite=expanded_suite,
        reception_suite=reception_suite,
        limit=limit,
    )
    tasks, load_errors = make_tasks(selected_rows)
    validation_errors = load_errors
    for task in tasks:
        validation_errors.extend(validate_task_shape(task))
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": (
            "generated canonical intertext benchmark supplement; tasks are ready "
            "for local model runs"
        ),
        "source_paths": {
            "model_data": str(model_data_path.relative_to(ROOT)),
            "canonical_cross_reference_atlas": str(atlas_path.relative_to(ROOT)),
            "contextual_expanded_benchmark_suite": str(expanded_suite_path.relative_to(ROOT)),
            "reception_signal_benchmark_supplement": str(reception_suite_path.relative_to(ROOT)),
            "generation_output_schema": str(output_schema_path.relative_to(ROOT)),
        },
        "selection": {
            "method": (
                "top canonical cross-reference rows with high-value anchors and "
                "Torah/Prophets/Writings evidence, excluding existing expanded and "
                "reception-signal benchmark units"
            ),
            "requested_limit": limit,
            "selected_unit_ids": [str(row["unit_id"]) for row in selected_rows],
        },
        "output_schema_title": output_schema.get("title"),
        "recommended_bakeoff_models": model_data.get("recommended_bakeoff_models", []),
        "summary": summarize(
            tasks=tasks,
            selected_rows=selected_rows,
            atlas=atlas,
            expanded_suite=expanded_suite,
            reception_suite=reception_suite,
            model_data=model_data,
        ),
        "validation_errors": validation_errors,
        "tasks": tasks,
    }


def counter_rows(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
    return [
        {label_key: key, "count": value}
        for key, value in sorted(counter.items(), key=lambda item: item[1], reverse=True)
    ]


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#355f7c",
    width: int = 980,
    limit: int = 20,
) -> str:
    rows = rows[:limit]
    row_h = 28
    left = 310
    right = 70
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
            f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row[label_key])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="18" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 18}" font-size="12" '
            f'font-weight="700" fill="#24313a">{value:g}</text>'
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
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>")
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_html(suite: dict[str, Any]) -> str:
    summary = suite["summary"]
    top_selected_note = f"{float(summary['top_selected_priority_score']):.2f}."
    task_rows = [
        [
            task["task_id"],
            task["ref"],
            task["layer"],
            f"{float(task['canonical_intertext_priority_score']):.2f}",
            task["anchor_token_count"],
            f"{float(task['anchor_token_pct']):.2f}%",
            task["high_value_anchor_count"],
            "; ".join(task["domain_ids"]),
            fmt_int(task["estimated_payload_chars"]),
        ]
        for task in suite["tasks"]
    ]
    selected_score_rows = [
        {
            "unit": unit_id,
            "score": next(
                float(task["canonical_intertext_priority_score"])
                for task in suite["tasks"]
                if task["unit_id"] == unit_id
            ),
        }
        for unit_id in suite["selection"]["selected_unit_ids"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Canonical Intertext Benchmark Supplement</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2a33;
      --muted: #667581;
      --line: #d7dde2;
      --band: #f5f7f8;
      --accent: #355f7c;
      --accent2: #6f5d2f;
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
    <h1>AlephTav Canonical Intertext Benchmark Supplement</h1>
    <p class="lede">
      Gloss and literal benchmark tasks for high-priority Psalm units with
      whole-Tanakh surface-form anchors across Torah, Prophets, and non-Psalm
      Writings. These tasks test whether local models can use broader canon
      context without turning retrieval cues into translation authority.
    </p>
    <p class="meta">Generated {esc(suite["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Summary</h2>
      {
        metric_cards(
            [
                (
                    "Units",
                    fmt_int(summary["selected_intertext_unit_count"]),
                    "Selected high-value intertext units.",
                ),
                ("Tasks", fmt_int(summary["task_count"]), "Runnable gloss/literal tasks."),
                (
                    "Planned runs",
                    fmt_int(summary["planned_model_runs"]),
                    "Tasks multiplied by bakeoff models.",
                ),
                (
                    "Remaining",
                    fmt_int(summary["remaining_intertext_candidate_count"]),
                    "Three-division high-value candidates left after selection.",
                ),
                (
                    "Top unit",
                    summary["top_selected_ref"],
                    f"Score {top_selected_note}",
                ),
            ]
        )
    }
      <div class="warning">
        Canonical cross-references are surface-form context only. This supplement
        does not prove lemma identity, diachronic dependence, theological reading,
        or translation wording authority.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            selected_score_rows,
            label_key="unit",
            value_key="score",
            aria_label="Selected canonical intertext priority scores",
            color="#355f7c",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(summary["domain_counts"], "domain"),
            label_key="domain",
            value_key="count",
            aria_label="Selected canonical intertext domain counts",
            color="#6f5d2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            counter_rows(summary["book_presence_counts"], "book"),
            label_key="book",
            value_key="count",
            aria_label="Selected canonical intertext book presence counts",
            color="#5b6f2f",
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
                "Score",
                "Anchors",
                "Anchor %",
                "High-Value",
                "Domains",
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
        description="Generate canonical intertext benchmark supplement tasks."
    )
    parser.add_argument("--model-data", type=Path, default=MODEL_DATA_PATH)
    parser.add_argument("--atlas", type=Path, default=ATLAS_PATH)
    parser.add_argument("--expanded-suite", type=Path, default=EXPANDED_SUITE_PATH)
    parser.add_argument("--reception-suite", type=Path, default=RECEPTION_SUITE_PATH)
    parser.add_argument("--output-schema", type=Path, default=OUTPUT_SCHEMA_PATH)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--jsonl-output", type=Path, default=DEFAULT_JSONL_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suite = build_suite(
        model_data_path=args.model_data,
        atlas_path=args.atlas,
        expanded_suite_path=args.expanded_suite,
        reception_suite_path=args.reception_suite,
        output_schema_path=args.output_schema,
        limit=args.limit,
    )
    write_json(args.json_output, suite)
    write_jsonl(args.jsonl_output, suite["tasks"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(suite), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.jsonl_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
