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
CONTENT_ROOT = ROOT / "content" / "psalms"
ATLAS_PATH = REPORT_ROOT / "contextual_pressure_atlas.json"
MATRIX_PATH = REPORT_ROOT / "benchmark_context_reception_matrix.json"
SUITE_PATH = REPORT_ROOT / "local_model_benchmark_suite.json"
CROSS_EXAM_PATH = REPORT_ROOT / "model_cross_exam_protocol.json"
DEFAULT_JSON_OUTPUT = REPORT_ROOT / "priority_unit_dossiers.json"
DEFAULT_JSONL_OUTPUT = REPORT_ROOT / "priority_unit_dossiers.jsonl"
DEFAULT_CSV_OUTPUT = REPORT_ROOT / "priority_unit_dossier_index.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "priority_unit_dossiers.html"

DEFAULT_LIMIT = 25
EXPECTED_TASK_LAYERS = ["gloss", "literal"]

DOMAIN_REVIEW_QUESTIONS = {
    "royal_kingship": (
        "What ancient royal or Davidic-covenant setting must be checked before "
        "a later messianic reading is reported?"
    ),
    "temple_cult_liturgy": (
        "Does the unit contain sanctuary, procession, sacrifice, praise, or "
        "priestly language that affects the English register?"
    ),
    "wisdom_torah": ("Which Torah, wisdom, or moral-contrast terms need whole-canon control?"),
    "lament_enemy_justice": (
        "Does the rendering preserve lament, enemy rhetoric, and justice appeal "
        "without ethically smoothing the text?"
    ),
    "covenant_mercy": (
        "Which covenant, mercy, remembrance, or faithfulness terms need lexical "
        "and theological review?"
    ),
    "creation_cosmos": (
        "Which creation, cosmic, or natural-order images require source-image preservation?"
    ),
    "anthropology_body": (
        "Which body, soul, heart, face, hand, or breath terms must remain visible "
        "rather than being abstracted?"
    ),
    "nations_zion_exile": (
        "How do nations, Zion, land, exile, or universal-praise terms affect the "
        "historical setting?"
    ),
    "divine_names_titles": ("Which divine names or titles require project naming-policy control?"),
    "textual_witness_pressure": (
        "Which evidence is Hebrew source, which is witness data, and which is "
        "only familiar or reception wording?"
    ),
    "jewish_christian_reception": (
        "Can Jewish and Christian reception be compared without allowing either "
        "viewpoint to rewrite the source translation?"
    ),
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


def join_values(values: list[Any] | tuple[Any, ...] | set[Any]) -> str:
    return "; ".join(str(value) for value in values)


def unit_path(unit_id: str) -> Path:
    psalm_id = unit_id.split(".")[0]
    return CONTENT_ROOT / psalm_id / f"{unit_id}.json"


def compact_token(token: dict[str, Any]) -> dict[str, Any]:
    features = token.get("compiler_features") or {}
    return {
        "token_id": token.get("token_id"),
        "surface": token.get("surface"),
        "lemma": token.get("lemma"),
        "strong": token.get("strong"),
        "morph_code": token.get("morph_code"),
        "morph_readable": token.get("morph_readable"),
        "part_of_speech": token.get("part_of_speech"),
        "stem": token.get("stem"),
        "display_gloss": token.get("display_gloss"),
        "word_sense": token.get("word_sense"),
        "syntax_role": token.get("syntax_role"),
        "semantic_role": token.get("semantic_role"),
        "referent": token.get("referent"),
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


def source_summary(tokens: list[dict[str, Any]]) -> dict[str, Any]:
    missing: Counter[str] = Counter()
    strong_count = 0
    lemma_count = 0
    divine_name_count = 0
    suffix_count = 0
    construct_count = 0
    for token in tokens:
        if token.get("strong"):
            strong_count += 1
        if token.get("lemma"):
            lemma_count += 1
        missing.update(str(item) for item in token.get("missing_enrichments") or [])
        features = token.get("compiler_features") or {}
        if features.get("divine_name"):
            divine_name_count += 1
        if features.get("suffix_pronoun"):
            suffix_count += 1
        if features.get("construct_state"):
            construct_count += 1
    token_count = len(tokens)
    return {
        "token_count": token_count,
        "lemma_coverage_pct": pct(lemma_count, token_count),
        "strong_coverage_pct": pct(strong_count, token_count),
        "missing_enrichment_counts": dict(missing.most_common()),
        "divine_name_tokens": divine_name_count,
        "suffix_pronoun_tokens": suffix_count,
        "construct_state_tokens": construct_count,
    }


def index_by_unit(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in rows}


def tasks_by_unit(suite: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in suite.get("tasks", []):
        grouped[str(task["unit_id"])].append(task)
    return dict(grouped)


def packets_by_unit(cross_exam: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for packet in cross_exam.get("packets", []):
        grouped[str(packet["unit_id"])].append(packet)
    return dict(grouped)


def reviewer_questions(
    *,
    priority_row: dict[str, Any],
    matrix_row: dict[str, Any],
    frame_questions: dict[str, str],
) -> list[str]:
    questions = []
    for frame in priority_row.get("required_frames", []):
        question = frame_questions.get(str(frame))
        if question:
            questions.append(f"{frame}: {question}")
    for domain in priority_row.get("domains", []):
        question = DOMAIN_REVIEW_QUESTIONS.get(str(domain))
        if question:
            questions.append(f"{domain}: {question}")
    if float(priority_row.get("surface_outside_context_pct") or 0.0) >= 75.0:
        questions.append(
            "whole_tanakh_context: Which high-frequency outside-Psalms forms "
            "are relevant context, and which should be discounted as noise?"
        )
    if matrix_row.get("context_pressure_intensity") == "high":
        questions.append(
            "priority_control: Which claims must be blocked until Hebrew, "
            "lexical, alignment, and theology review are complete?"
        )
    return list(dict.fromkeys(questions))


def decision_gates(
    *,
    priority_row: dict[str, Any],
    tasks: list[dict[str, Any]],
    cross_packets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    task_layers = {str(task.get("layer")) for task in tasks}
    missing_layers = [layer for layer in EXPECTED_TASK_LAYERS if layer not in task_layers]
    gates = [
        {
            "gate": "Hebrew source control",
            "status": "required",
            "evidence": "Every translation claim must cite unit token evidence.",
        },
        {
            "gate": "Witness boundary",
            "status": "required"
            if "textual_witness_pressure" in priority_row.get("domains", [])
            else "standard",
            "evidence": "Witness text must not be treated as canonical Hebrew source.",
        },
        {
            "gate": "Reception separation",
            "status": "required" if priority_row.get("reception_sensitive") else "standard",
            "evidence": "Jewish and Christian readings must stay tagged as reception.",
        },
    ]
    gates.append(
        {
            "gate": "Benchmark task coverage",
            "status": "ready" if not missing_layers else "gap",
            "evidence": (
                "Task layers present: "
                f"{join_values(sorted(task_layers)) or 'none'}; "
                f"missing: {join_values(missing_layers) or 'none'}."
            ),
        }
    )
    gates.append(
        {
            "gate": "Model cross-exam packets",
            "status": "ready" if cross_packets else "gap",
            "evidence": f"{len(cross_packets)} advisory judge packets found.",
        }
    )
    return gates


def build_dossier(
    *,
    priority_rank: int,
    priority_row: dict[str, Any],
    matrix_row: dict[str, Any],
    frame_questions: dict[str, str],
    unit_tasks: list[dict[str, Any]],
    unit_packets: list[dict[str, Any]],
) -> dict[str, Any]:
    content = load_json(unit_path(priority_row["unit_id"]))
    tokens = content.get("tokens") or []
    witnesses = content.get("witnesses") or []
    task_layers = sorted({str(task.get("layer")) for task in unit_tasks})
    packet_judges = sorted({str(packet.get("judge_id")) for packet in unit_packets})
    return {
        "priority_rank": priority_rank,
        "unit_id": priority_row["unit_id"],
        "ref": priority_row["ref"],
        "psalm_id": priority_row["psalm_id"],
        "primary_stratum": priority_row["primary_stratum"],
        "status": content.get("status"),
        "source_hebrew": content.get("source_hebrew"),
        "source_summary": source_summary(tokens),
        "priority": {
            "score": priority_row["priority_score"],
            "context_pressure_score": priority_row["context_pressure_score"],
            "intensity": priority_row["context_pressure_intensity"],
            "domain_count": priority_row["domain_count"],
            "surface_outside_context_pct": priority_row["surface_outside_context_pct"],
            "outside_division_count": priority_row["outside_division_count"],
        },
        "context_domains": matrix_row.get("context_domains", {}),
        "domain_groups": priority_row.get("domain_groups", []),
        "reception_profile": matrix_row.get("reception_profile", {}),
        "review_roles": matrix_row.get("review_roles", []),
        "model_controls": matrix_row.get("model_controls", []),
        "reviewer_questions": reviewer_questions(
            priority_row=priority_row,
            matrix_row=matrix_row,
            frame_questions=frame_questions,
        ),
        "decision_gates": decision_gates(
            priority_row=priority_row,
            tasks=unit_tasks,
            cross_packets=unit_packets,
        ),
        "context_coverage": {
            "surface_form_match_pct": matrix_row["context_coverage"]["surface_form_match_pct"],
            "surface_outside_context_pct": matrix_row["context_coverage"][
                "surface_outside_context_pct"
            ],
            "outside_context_division_counts": matrix_row["context_coverage"][
                "outside_context_division_counts"
            ],
            "high_context_tokens": matrix_row["context_coverage"]["high_context_tokens"],
            "missing_enrichment_counts": matrix_row["context_coverage"][
                "missing_enrichment_counts"
            ],
        },
        "tokens": [compact_token(token) for token in tokens],
        "witnesses": [compact_witness(witness) for witness in witnesses],
        "benchmark": {
            "task_count": len(unit_tasks),
            "task_ids": [task["task_id"] for task in unit_tasks],
            "task_layers": task_layers,
            "missing_task_layers": [
                layer for layer in EXPECTED_TASK_LAYERS if layer not in task_layers
            ],
            "cross_exam_packet_count": len(unit_packets),
            "cross_exam_packet_ids": [packet["packet_id"] for packet in unit_packets],
            "cross_exam_judges": packet_judges,
        },
    }


def build_dossiers(
    *,
    atlas: dict[str, Any],
    matrix: dict[str, Any],
    suite: dict[str, Any],
    cross_exam: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    matrix_rows = index_by_unit(matrix["unit_rows"])
    suite_units = tasks_by_unit(suite)
    packet_units = packets_by_unit(cross_exam)
    frame_questions = {
        str(row["frame"]): str(row["control_question"]) for row in atlas.get("frame_rows", [])
    }
    dossiers = []
    for rank, priority_row in enumerate(atlas["priority_unit_rows"][:limit], start=1):
        unit_id = str(priority_row["unit_id"])
        dossiers.append(
            build_dossier(
                priority_rank=rank,
                priority_row=priority_row,
                matrix_row=matrix_rows[unit_id],
                frame_questions=frame_questions,
                unit_tasks=suite_units.get(unit_id, []),
                unit_packets=packet_units.get(unit_id, []),
            )
        )
    return dossiers


def summarize(dossiers: list[dict[str, Any]], atlas: dict[str, Any]) -> dict[str, Any]:
    roles: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    frames: Counter[str] = Counter()
    witness_sources: Counter[str] = Counter()
    gate_statuses: Counter[str] = Counter()
    token_count = 0
    high_pressure = 0
    reception = 0
    textual = 0
    with_tasks = 0
    with_cross_exam = 0
    for dossier in dossiers:
        token_count += int(dossier["source_summary"]["token_count"])
        roles.update(dossier["review_roles"])
        domains.update(dossier["context_domains"].keys())
        frames.update(dossier["reception_profile"].get("required_frames", []))
        witness_sources.update(str(w["source_id"]) for w in dossier["witnesses"])
        gate_statuses.update(gate["status"] for gate in dossier["decision_gates"])
        if dossier["priority"]["intensity"] == "high":
            high_pressure += 1
        if dossier["reception_profile"].get("sensitive"):
            reception += 1
        if "textual_witness_pressure" in dossier["context_domains"]:
            textual += 1
        if dossier["benchmark"]["task_count"]:
            with_tasks += 1
        if dossier["benchmark"]["cross_exam_packet_count"]:
            with_cross_exam += 1
    return {
        "dossier_count": len(dossiers),
        "source_priority_pool_count": len(atlas["priority_unit_rows"]),
        "token_count": token_count,
        "high_pressure_dossiers": high_pressure,
        "reception_sensitive_dossiers": reception,
        "textual_witness_pressure_dossiers": textual,
        "dossiers_with_benchmark_tasks": with_tasks,
        "dossiers_without_benchmark_tasks": len(dossiers) - with_tasks,
        "dossiers_with_cross_exam_packets": with_cross_exam,
        "dossiers_without_cross_exam_packets": len(dossiers) - with_cross_exam,
        "review_role_counts": dict(roles.most_common()),
        "domain_counts": dict(domains.most_common()),
        "reception_frame_counts": dict(frames.most_common()),
        "witness_source_counts": dict(witness_sources.most_common()),
        "decision_gate_status_counts": dict(gate_statuses.most_common()),
        "top_priority_unit": dossiers[0]["unit_id"] if dossiers else None,
        "top_priority_score": dossiers[0]["priority"]["score"] if dossiers else 0,
    }


def build_report(
    *,
    atlas_path: Path,
    matrix_path: Path,
    suite_path: Path,
    cross_exam_path: Path,
    limit: int,
) -> dict[str, Any]:
    atlas = load_json(atlas_path)
    matrix = load_json(matrix_path)
    suite = load_json(suite_path)
    cross_exam = load_json(cross_exam_path)
    dossiers = build_dossiers(
        atlas=atlas,
        matrix=matrix,
        suite=suite,
        cross_exam=cross_exam,
        limit=limit,
    )
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": (
            "generated priority unit dossiers; reviewer packets, not final "
            "interpretation or approved translation"
        ),
        "source_paths": {
            "contextual_pressure_atlas": str(atlas_path.relative_to(ROOT)),
            "context_reception_matrix": str(matrix_path.relative_to(ROOT)),
            "benchmark_suite": str(suite_path.relative_to(ROOT)),
            "cross_exam_protocol": str(cross_exam_path.relative_to(ROOT)),
            "content_root": "content/psalms",
        },
        "selection_method": {
            "limit": limit,
            "sort": "contextual_pressure_atlas.priority_unit_rows priority_score desc",
            "principles": [
                "Show token-level Hebrew evidence before interpretive frames.",
                "Expose witness text as witness evidence, not canonical source.",
                "Keep Jewish and Christian reception as separated review frames.",
                "Flag benchmark and cross-examination coverage gaps.",
            ],
        },
        "summary": summarize(dossiers, atlas),
        "dossiers": dossiers,
    }


def write_csv(path: Path, dossiers: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "priority_rank",
        "unit_id",
        "ref",
        "priority_score",
        "intensity",
        "domain_count",
        "domains",
        "reception_sensitive",
        "textual_witness_pressure",
        "review_roles",
        "token_count",
        "surface_outside_context_pct",
        "task_count",
        "missing_task_layers",
        "cross_exam_packet_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for dossier in dossiers:
            writer.writerow(
                {
                    "priority_rank": dossier["priority_rank"],
                    "unit_id": dossier["unit_id"],
                    "ref": dossier["ref"],
                    "priority_score": dossier["priority"]["score"],
                    "intensity": dossier["priority"]["intensity"],
                    "domain_count": dossier["priority"]["domain_count"],
                    "domains": join_values(sorted(dossier["context_domains"])),
                    "reception_sensitive": dossier["reception_profile"].get("sensitive"),
                    "textual_witness_pressure": (
                        "textual_witness_pressure" in dossier["context_domains"]
                    ),
                    "review_roles": join_values(dossier["review_roles"]),
                    "token_count": dossier["source_summary"]["token_count"],
                    "surface_outside_context_pct": dossier["priority"][
                        "surface_outside_context_pct"
                    ],
                    "task_count": dossier["benchmark"]["task_count"],
                    "missing_task_layers": join_values(dossier["benchmark"]["missing_task_layers"]),
                    "cross_exam_packet_count": dossier["benchmark"]["cross_exam_packet_count"],
                }
            )


def packet_rows(dossiers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for dossier in dossiers:
        rows.append(
            {
                "packet_id": f"priority_dossier.{dossier['unit_id']}",
                "unit_id": dossier["unit_id"],
                "ref": dossier["ref"],
                "priority_rank": dossier["priority_rank"],
                "priority": dossier["priority"],
                "source_hebrew": dossier["source_hebrew"],
                "source_summary": dossier["source_summary"],
                "context_domains": dossier["context_domains"],
                "reception_profile": dossier["reception_profile"],
                "review_roles": dossier["review_roles"],
                "model_controls": dossier["model_controls"],
                "reviewer_questions": dossier["reviewer_questions"],
                "decision_gates": dossier["decision_gates"],
                "tokens": dossier["tokens"],
                "witnesses": dossier["witnesses"],
                "benchmark": dossier["benchmark"],
            }
        )
    return rows


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
    color: str = "#2f6f73",
    width: int = 980,
    limit: int = 20,
) -> str:
    rows = rows[:limit]
    row_h = 29
    left = 310
    right = 58
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
            f'<text x="{left - 12}" y="{y + 19}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row[label_key])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="19" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 19}" font-size="12" '
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
        cells = []
        for cell in row:
            if str(cell).startswith("<"):
                cells.append(f"<td>{cell}</td>")
            else:
                cells.append(f"<td>{esc(cell)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_dossier_section(dossier: dict[str, Any]) -> str:
    domain_rows = [
        [
            data["label"],
            data["hit_count"],
            join_values(data["evidence"]),
        ]
        for data in dossier["context_domains"].values()
    ]
    token_rows = [
        [
            token["token_id"],
            token["surface"],
            token["lemma"] or "",
            token["strong"] or "",
            token["morph_code"] or "",
            token["display_gloss"] or "",
            token["greek"] or "",
            join_values(token["missing_enrichments"]),
        ]
        for token in dossier["tokens"]
    ]
    witness_rows = [
        [
            witness["source_id"],
            witness["language"],
            witness["witness_role"],
            witness["version_title"],
            witness["text"],
        ]
        for witness in dossier["witnesses"]
    ]
    high_context_rows = [
        [
            token["token_id"],
            token["surface"],
            token["display_gloss"],
            token["surface_query"],
            token["outside_psalms_count"],
            join_values(token["outside_psalms_sample_refs"]),
        ]
        for token in dossier["context_coverage"]["high_context_tokens"]
    ]
    question_rows = [[item] for item in dossier["reviewer_questions"]]
    gate_rows = [
        [gate["gate"], gate["status"], gate["evidence"]] for gate in dossier["decision_gates"]
    ]
    return f"""
    <section class="dossier">
      <h2>{esc(dossier["priority_rank"])}. {esc(dossier["ref"])} / {esc(dossier["unit_id"])}</h2>
      <p class="hebrew" dir="rtl">{esc(dossier["source_hebrew"])}</p>
      {
        metric_cards(
            [
                (
                    "Priority",
                    f'''{dossier["priority"]["score"]:.2f}''',
                    f'''{dossier["priority"]["intensity"]} pressure.''',
                ),
                (
                    "Domains",
                    dossier["priority"]["domain_count"],
                    join_values(dossier["domain_groups"]),
                ),
                (
                    "Tokens",
                    dossier["source_summary"]["token_count"],
                    (f'''{dossier["source_summary"]["lemma_coverage_pct"]:.2f}% lemma coverage.'''),
                ),
                (
                    "Tasks",
                    dossier["benchmark"]["task_count"],
                    (
                        "Missing "
                        f'''{join_values(dossier["benchmark"]["missing_task_layers"]) or "none"}.'''
                    ),
                ),
            ]
        )
    }
      <h3>Review Gates</h3>
      {table(["Gate", "Status", "Evidence"], gate_rows)}
      <h3>Context Domains</h3>
      {table(["Domain", "Hits", "Evidence"], domain_rows)}
      <h3>High-Context Tokens</h3>
      {
        table(
            ["Token", "Surface", "Gloss", "Query", "Outside Psalms", "Sample Refs"],
            high_context_rows,
        )
    }
      <h3>Source Tokens</h3>
      {
        table(
            ["Token", "Surface", "Lemma", "Strong", "Morph", "Gloss", "Greek", "Missing"],
            token_rows,
        )
    }
      <h3>Witnesses</h3>
      {table(["Source", "Lang", "Role", "Version", "Text"], witness_rows)}
      <h3>Reviewer Questions</h3>
      {table(["Question"], question_rows)}
    </section>
    """


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    priority_chart_rows = [
        {
            "label": f"{dossier['priority_rank']}. {dossier['unit_id']}",
            "score": dossier["priority"]["score"],
        }
        for dossier in report["dossiers"]
    ]
    domain_chart_rows = counter_rows(summary["domain_counts"], "domain")
    role_chart_rows = counter_rows(summary["review_role_counts"], "role")
    frame_chart_rows = counter_rows(summary["reception_frame_counts"], "frame")
    index_rows = [
        [
            dossier["priority_rank"],
            dossier["ref"],
            dossier["unit_id"],
            dossier["priority"]["score"],
            dossier["priority"]["intensity"],
            dossier["priority"]["domain_count"],
            "yes" if dossier["reception_profile"].get("sensitive") else "no",
            dossier["benchmark"]["task_count"],
            dossier["benchmark"]["cross_exam_packet_count"],
        ]
        for dossier in report["dossiers"]
    ]
    dossier_sections = "".join(render_dossier_section(row) for row in report["dossiers"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Priority Unit Dossiers</title>
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
    main {{ max-width: 1240px; margin: 0 auto; padding: 30px 34px 54px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    h3 {{ margin: 24px 0 10px; font-size: 17px; }}
    p {{ margin: 0 0 13px; }}
    .lede {{ max-width: 990px; font-size: 17px; color: #33414c; }}
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
    .hebrew {{
      font-size: 24px;
      line-height: 1.8;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfc;
    }}
    .dossier {{ border-top: 3px solid var(--accent); padding-top: 4px; }}
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
    <h1>AlephTav Priority Unit Dossiers</h1>
    <p class="lede">
      Reviewer-ready dossiers for the highest-priority Psalms benchmark units.
      Each dossier keeps Hebrew token evidence, witness boundaries,
      whole-Tanakh form context, cultural domains, and Jewish/Christian
      reception frames visible before translation approval.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Dossier Summary</h2>
      {
        metric_cards(
            [
                ("Dossiers", fmt_int(summary["dossier_count"]), "Top priority units."),
                ("Tokens", fmt_int(summary["token_count"]), "Source tokens displayed."),
                (
                    "High pressure",
                    fmt_int(summary["high_pressure_dossiers"]),
                    "Dossiers with high context pressure.",
                ),
                (
                    "Reception",
                    fmt_int(summary["reception_sensitive_dossiers"]),
                    "Dossiers requiring separated reception frames.",
                ),
                (
                    "Textual",
                    fmt_int(summary["textual_witness_pressure_dossiers"]),
                    "Dossiers with witness/provenance pressure.",
                ),
                (
                    "Task gaps",
                    fmt_int(summary["dossiers_without_benchmark_tasks"]),
                    "Dossiers not yet in the generated task suite.",
                ),
                (
                    "Cross-exam gaps",
                    fmt_int(summary["dossiers_without_cross_exam_packets"]),
                    "Dossiers without advisory judge packets.",
                ),
                (
                    "Top unit",
                    summary["top_priority_unit"],
                    f'''Score {summary["top_priority_score"]:.2f}.''',
                ),
            ]
        )
    }
      <div class="warning">
        These dossiers are evidence packets for review. They do not approve a
        translation and do not resolve Jewish or Christian interpretive claims.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            priority_chart_rows,
            label_key="label",
            value_key="score",
            aria_label="Priority score by dossier",
            color="#2f6f73",
        )
    }</div>
    </section>

    <section>
      <h2>Coverage Charts</h2>
      <div class="chart">{
        svg_horizontal_bars(
            domain_chart_rows,
            label_key="domain",
            value_key="count",
            aria_label="Domain counts in priority dossiers",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            role_chart_rows,
            label_key="role",
            value_key="count",
            aria_label="Required review roles in priority dossiers",
            color="#4f6f38",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            frame_chart_rows,
            label_key="frame",
            value_key="count",
            aria_label="Reception frame counts in priority dossiers",
            color="#5f5c8a",
        )
    }</div>
    </section>

    <section>
      <h2>Dossier Index</h2>
      {
        table(
            [
                "Rank",
                "Ref",
                "Unit",
                "Priority",
                "Intensity",
                "Domains",
                "Reception",
                "Tasks",
                "Cross-Exam",
            ],
            index_rows,
        )
    }
    </section>
    {dossier_sections}
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate reviewer-ready priority unit dossiers.")
    parser.add_argument("--atlas", type=Path, default=ATLAS_PATH)
    parser.add_argument("--matrix", type=Path, default=MATRIX_PATH)
    parser.add_argument("--suite", type=Path, default=SUITE_PATH)
    parser.add_argument("--cross-exam", type=Path, default=CROSS_EXAM_PATH)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--jsonl-output", type=Path, default=DEFAULT_JSONL_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        atlas_path=args.atlas,
        matrix_path=args.matrix,
        suite_path=args.suite,
        cross_exam_path=args.cross_exam,
        limit=args.limit,
    )
    write_json(args.json_output, report)
    write_jsonl(args.jsonl_output, packet_rows(report["dossiers"]))
    write_csv(args.csv_output, report["dossiers"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.jsonl_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
