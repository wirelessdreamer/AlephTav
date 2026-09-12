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
RUBRIC_PATH = ROOT / "docs" / "research" / "reviewer_signoff_rubric.json"
SUITE_PATH = ROOT / "reports" / "research" / "local_model_benchmark_suite.json"
CONTEXT_MATRIX_PATH = ROOT / "reports" / "research" / "benchmark_context_reception_matrix.json"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "model_cross_exam_protocol.json"
DEFAULT_JSONL_OUTPUT = ROOT / "reports" / "research" / "model_cross_exam_packets.jsonl"
DEFAULT_CSV_OUTPUT = ROOT / "reports" / "research" / "model_cross_exam_execution_matrix.csv"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "model_cross_exam_protocol.html"

JUDGE_BASE_PROBES = {
    "codex_secondary": [
        "Does the candidate conform to the required JSON schema and task identity?",
        "Are all token_id references valid for this unit and layer?",
        "Are alignment hints specific enough to audit against source tokens?",
        "Does the rationale introduce unsupported source, context, or witness claims?",
        "Does the output preserve the requested layer instead of drifting styles?",
    ],
    "claude_secondary": [
        "Does the rationale distinguish translation from interpretation?",
        "Does the wording preserve poetic pressure without flattening source imagery?",
        "Are Jewish and Christian reception claims separated when relevant?",
        "Does the candidate overstate theology beyond the Hebrew evidence?",
        "What concerns should be routed to human reviewers first?",
    ],
    "hebrew_specialist_model": [
        "Are lemma, morphology, stem, suffix, and construct claims plausible?",
        "Is there any modern-Hebrew interference in the proposed reading?",
        "Does the English reflect Biblical Hebrew syntax and discourse structure?",
        "Are lexical ambiguities acknowledged rather than silently resolved?",
        "Which source-language claims require a human Hebrew reviewer?",
    ],
}

DOMAIN_PROBES = {
    "anthropology_body": [
        "Check whether body, soul, heart, or spirit terms were over-abstracted.",
        "Require a rationale if embodied Hebrew imagery is softened in English.",
    ],
    "covenant_mercy": [
        "Check whether mercy, faithfulness, and covenant language is grounded.",
        "Reject covenantal claims that are not supported by the local token evidence.",
    ],
    "creation_cosmos": [
        "Check whether creation or cosmic imagery is preserved before abstraction.",
        "Verify that whole-canon echoes are cited as context, not as lexical proof.",
    ],
    "divine_names_titles": [
        "Check divine names and titles against project naming policy.",
        "Flag any theology-driven smoothing of YHWH, Elohim, Adonai, or titles.",
    ],
    "jewish_christian_reception": [
        "Require separate Jewish, Christian, and academic-critical reception notes.",
        "Reject reception-history conclusions embedded inside translation text.",
    ],
    "lament_enemy_justice": [
        "Check whether lament, enemy, and justice rhetoric is preserved accurately.",
        "Flag sanitizing or intensifying violence, vengeance, or imprecation.",
    ],
    "nations_zion_exile": [
        "Check nations, Zion, land, and exile terms for historical-context drift.",
        "Require perspective tags for later liturgical or theological reuse.",
    ],
    "royal_kingship": [
        "Check royal, Davidic, sonship, throne, or priestly claims carefully.",
        "Keep ancient royal ideology separate from later messianic readings.",
    ],
    "temple_cult_liturgy": [
        "Check temple, cultic, musical, and liturgical terms against source evidence.",
        "Flag modern worship-language imports that erase ancient setting.",
    ],
    "textual_witness_pressure": [
        "Confirm witnesses are labeled as witnesses, never canonical Hebrew source.",
        "Flag English witness wording copied into the candidate without provenance.",
    ],
    "wisdom_torah": [
        "Check Torah, wisdom, way, righteous, wicked, and fear-language precision.",
        "Require broader-canon context to be cited as context, not overclaimed.",
    ],
}

LAYER_PROBES = {
    "gloss": [
        "Prefer token-level lexical control over smooth English.",
        "Flag any expansion that hides morphology or source-token granularity.",
    ],
    "literal": [
        "Prefer source-order and clause logic over idiomatic smoothing.",
        "Flag any missing drift note for unavoidable English restructuring.",
    ],
}

ROLE_ALIASES = {
    "hebrew": ("Hebrew",),
    "lexical": ("lexical",),
    "alignment": ("alignment",),
    "lyric": ("lyric",),
    "poetic": ("lyric",),
    "theology": ("theology",),
    "reception": ("theology",),
    "ancient_cultural_context": ("theology",),
    "canonical_context": ("Hebrew",),
    "textual": ("Hebrew", "alignment"),
    "textual_witness": ("Hebrew", "alignment"),
}

JUDGE_OUTPUT_CONTRACT = {
    "verdict": "pass | concerns | reject | not_assessable",
    "score_0_5": "integer or decimal in the review scale",
    "gate_failures": ["short stable failure codes"],
    "concerns": ["specific concerns tied to token_id, field, or claim"],
    "required_human_roles": ["lexical", "Hebrew", "alignment", "lyric", "theology"],
    "evidence_notes": ["brief notes with task evidence references"],
    "confidence_0_1": "model critic confidence, advisory only",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def project_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [str(key) for key in value]
    if isinstance(value, str):
        if ";" in value:
            return [part.strip() for part in value.split(";") if part.strip()]
        return [value] if value else []
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def context_by_unit(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in matrix.get("unit_rows", [])}


def task_tokens(task: dict[str, Any]) -> list[dict[str, Any]]:
    source = task.get("generation_input", {}).get("locked_inputs", {}).get("source", {})
    rows = []
    for token in source.get("tokens") or []:
        rows.append(
            {
                "token_id": token.get("token_id"),
                "surface": token.get("surface"),
                "lemma": token.get("lemma"),
                "display_gloss": token.get("display_gloss"),
                "part_of_speech": token.get("part_of_speech"),
                "surface_outside_psalms_count": token.get("surface_outside_psalms_count"),
                "lemma_form_outside_psalms_count": token.get("lemma_form_outside_psalms_count"),
            }
        )
    return rows


def context_domains(context: dict[str, Any]) -> list[str]:
    domains = set(string_list(context.get("context_domains", {})))
    domains.update(string_list(context.get("signal_labels", [])))
    domains.update(string_list(context.get("cultural_domain_labels", [])))
    domains.update(string_list(context.get("domain_labels", [])))
    return sorted(domains)


def reception_signal_context(task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    locked = task.get("generation_input", {}).get("locked_inputs", {})
    task_context = locked.get("reception_signal_context") or {}
    signal_ids = task_context.get("signal_ids") or context.get("signal_ids") or []
    signal_labels = task_context.get("signal_labels") or context.get("signal_labels") or []
    report_flags = task_context.get("report_flags") or context.get("report_flags") or []
    review_roles = (
        task_context.get("recommended_review_roles")
        or context.get("recommended_review_roles")
        or []
    )
    return {
        "score": task_context.get(
            "signal_priority_score",
            context.get("reception_signal_priority_score"),
        ),
        "pressure_band": task_context.get("pressure_band") or context.get("pressure_band"),
        "signal_family_count": task_context.get(
            "signal_family_count",
            context.get("signal_family_count"),
        ),
        "signal_ids": [str(item) for item in signal_ids],
        "signal_labels": [str(item) for item in signal_labels],
        "report_flags": [str(item) for item in report_flags],
        "recommended_review_roles": [str(item) for item in review_roles],
        "known_reception_sensitive": task_context.get(
            "known_reception_sensitive",
            context.get("known_reception_sensitive"),
        ),
        "known_jewish_christian_separation": task_context.get(
            "known_jewish_christian_separation",
            context.get("known_jewish_christian_separation"),
        ),
        "witness_divergence_pct": task_context.get(
            "witness_divergence_pct",
            context.get("witness_divergence_pct"),
        ),
        "token_evidence": task_context.get("token_evidence") or context.get("token_evidence", []),
    }


def canonical_intertext_context(
    task: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    locked = task.get("generation_input", {}).get("locked_inputs", {})
    task_context = locked.get("canonical_intertext_context") or {}
    return {
        "score": task_context.get("priority_score", context.get("priority_score")),
        "anchor_token_count": task_context.get(
            "anchor_token_count",
            context.get("anchor_token_count"),
        ),
        "anchor_token_pct": task_context.get("anchor_token_pct", context.get("anchor_token_pct")),
        "high_value_anchor_count": task_context.get(
            "high_value_anchor_count",
            context.get("high_value_anchor_count"),
        ),
        "outside_division_counts": task_context.get("outside_division_counts")
        or context.get("outside_division_counts", {}),
        "outside_book_counts": task_context.get("outside_book_counts")
        or context.get("outside_book_counts", {}),
        "has_torah_evidence": task_context.get(
            "has_torah_evidence",
            context.get("has_torah_evidence"),
        ),
        "has_prophets_evidence": task_context.get(
            "has_prophets_evidence",
            context.get("has_prophets_evidence"),
        ),
        "has_non_psalm_writings_evidence": task_context.get(
            "has_non_psalm_writings_evidence",
            context.get("has_non_psalm_writings_evidence"),
        ),
        "has_three_division_evidence": task_context.get(
            "has_three_division_evidence",
            context.get("has_three_division_evidence"),
        ),
        "domain_ids": [
            str(item)
            for item in (task_context.get("domain_ids") or context.get("domain_ids") or [])
        ],
        "domain_labels": [
            str(item)
            for item in (task_context.get("domain_labels") or context.get("domain_labels") or [])
        ],
        "top_anchor_forms": task_context.get("top_anchor_forms")
        or context.get("top_anchor_forms", []),
        "boundary_flags": task_context.get("boundary_flags") or {},
    }


def normalized_human_roles(raw_roles: list[str]) -> list[str]:
    roles = []
    for role in raw_roles:
        aliases = ROLE_ALIASES.get(str(role).strip().lower(), ())
        roles.extend(aliases)
    return roles


def review_roles(context: dict[str, Any], task: dict[str, Any]) -> list[str]:
    roles = normalized_human_roles(list(context.get("review_roles") or []))
    signal_context = reception_signal_context(task, context)
    intertext_context = canonical_intertext_context(task, context)
    roles.extend(normalized_human_roles(signal_context["recommended_review_roles"]))
    if intertext_context["anchor_token_count"]:
        roles.extend(["Hebrew", "alignment"])
    if not roles:
        roles = ["lexical", "Hebrew", "alignment"]
    tags = set(str(tag) for tag in task.get("benchmark_tags", []))
    if tags & {"parallelism", "metaphor", "doxology", "imprecation", "lament"}:
        roles.append("lyric")
    if tags & {
        "reception_history",
        "jewish_christian_reception",
        "messianic_interpretation",
        "theology",
        "anthropology",
        "divine_beings",
        "ethical_reception",
    }:
        roles.append("theology")
    if tags & {"canonical_intertext", "whole_tanakh_context", "canonical_intertext_supplement"}:
        roles.extend(["Hebrew", "alignment"])
    order = ["lexical", "Hebrew", "alignment", "lyric", "theology"]
    return sorted(set(roles), key=lambda role: order.index(role))


def packet_priority(task: dict[str, Any], context: dict[str, Any]) -> str:
    tags = set(str(tag) for tag in task.get("benchmark_tags", []))
    signal_context = reception_signal_context(task, context)
    intertext_context = canonical_intertext_context(task, context)
    if signal_context["pressure_band"] in {"critical", "highest"}:
        return "high"
    if (
        float(intertext_context["score"] or 0) >= 250
        or int(intertext_context["high_value_anchor_count"] or 0) >= 3
    ):
        return "high"
    if context.get("context_pressure_intensity") == "high":
        return "high"
    if tags & {
        "reception_history",
        "jewish_christian_reception",
        "reception_signal_supplement",
        "textual_witness",
        "messianic_interpretation",
        "imprecation",
        "violence",
        "canonical_intertext_supplement",
    }:
        return "high"
    if context.get("context_pressure_intensity") == "medium":
        return "medium"
    return "standard"


def dynamic_probes(
    *,
    judge_id: str,
    task: dict[str, Any],
    context: dict[str, Any],
) -> list[str]:
    probes = list(JUDGE_BASE_PROBES.get(judge_id, []))
    probes.extend(LAYER_PROBES.get(str(task.get("layer")), []))
    signal_context = reception_signal_context(task, context)
    intertext_context = canonical_intertext_context(task, context)
    for domain in context_domains(context):
        probes.extend(DOMAIN_PROBES.get(domain, []))
    for label in signal_context["signal_labels"]:
        probes.append(
            f"Treat the {label} signal as review routing evidence, not as a translation warrant."
        )
    if signal_context["known_jewish_christian_separation"] or (
        "jewish_christian_reception" in task.get("benchmark_tags", [])
    ):
        probes.append(
            "Separate Jewish, Christian, and academic-critical claims before "
            "scoring any reception-sensitive wording."
        )
    if signal_context["report_flags"]:
        probes.append(
            "Check every report flag against the candidate rationale and reject "
            "unsupported inference from routing flags."
        )
    if intertext_context["anchor_token_count"]:
        probes.append(
            "Treat non-Psalm surface-form anchors as contextual retrieval evidence, "
            "not as lemma proof or direct intertextual dependence."
        )
        probes.append(
            "Check that Torah, Prophets, and non-Psalm Writings evidence is kept "
            "outside the translation string unless the Hebrew source itself requires it."
        )
        probes.append(
            "Reject any rationale that lets broader-canon context override the local "
            "Psalm syntax, morphology, or token-level alignment."
        )
    if intertext_context["has_three_division_evidence"]:
        probes.append(
            "Name which canon division is being used for context and avoid collapsing "
            "Torah, Prophets, and Writings into one undifferentiated claim."
        )
    if float(task.get("outside_psalms_context_pct") or 0.0) >= 75.0:
        probes.append("Check that whole-Tanakh context is cited as form-level context only.")
    if context.get("reception_profile", {}).get("sensitive"):
        probes.append("Name the reception frame before criticizing any theological claim.")
    seen = set()
    unique = []
    for probe in probes:
        if probe not in seen:
            seen.add(probe)
            unique.append(probe)
    return unique


def packet_for_task_judge(
    task: dict[str, Any],
    judge: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    source = task.get("generation_input", {}).get("locked_inputs", {}).get("source", {})
    domains = context_domains(context)
    reception = context.get("reception_profile") or {}
    signal_context = reception_signal_context(task, context)
    intertext_context = canonical_intertext_context(task, context)
    pressure_score = context.get(
        "context_pressure_score",
        signal_context["score"] or intertext_context["score"],
    )
    pressure_intensity = context.get(
        "context_pressure_intensity",
        signal_context["pressure_band"] or packet_priority(task, context),
    )
    domain_count = context.get(
        "domain_count",
        signal_context["signal_family_count"] or len(intertext_context["domain_ids"]),
    )
    return {
        "packet_id": f"cross.{task['task_id']}.{judge['judge_id']}",
        "task_id": task["task_id"],
        "unit_id": task["unit_id"],
        "ref": task["ref"],
        "layer": task["layer"],
        "judge_id": judge["judge_id"],
        "judge_type": judge["judge_type"],
        "authority": judge["authority"],
        "priority": packet_priority(task, context),
        "judge_focus": judge["focus"],
        "benchmark_tags": task.get("benchmark_tags", []),
        "context_pressure": {
            "score": pressure_score,
            "intensity": pressure_intensity,
            "domain_count": domain_count,
            "domains": domains,
            "surface_outside_context_pct": context.get("context_coverage", {}).get(
                "surface_outside_context_pct"
            ),
        },
        "reception_signal_context": signal_context,
        "canonical_intertext_context": intertext_context,
        "reception_profile": {
            "sensitive": reception.get(
                "sensitive",
                bool(signal_context["known_reception_sensitive"])
                or bool(intertext_context["boundary_flags"].get("reception_sensitive")),
            ),
            "label": reception.get("label"),
            "required_frames": reception.get("required_frames", []),
        },
        "required_human_roles": review_roles(context, task),
        "source_evidence": {
            "source_hebrew": source.get("source_hebrew"),
            "token_count": source.get("token_count"),
            "tokens": task_tokens(task),
        },
        "candidate_placeholder": {
            "model_profile_id": "<model under review>",
            "candidate_index": "<1-based candidate index>",
            "candidate_output": "<generation_output.schema.json object>",
            "runtime": "<optional runtime metadata>",
        },
        "probe_questions": dynamic_probes(
            judge_id=judge["judge_id"],
            task=task,
            context=context,
        ),
        "judge_output_contract": JUDGE_OUTPUT_CONTRACT,
    }


def build_packets(
    suite: dict[str, Any],
    rubric: dict[str, Any],
    context_rows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    packets = []
    for task in suite["tasks"]:
        context = context_rows.get(str(task["unit_id"]), {})
        for judge in rubric["model_cross_examination"]:
            packets.append(packet_for_task_judge(task, judge, context))
    return packets


def execution_matrix(
    packets: list[dict[str, Any]],
    suite: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    models = [str(model) for model in suite["recommended_bakeoff_models"]]
    candidate_count = int(suite["summary"]["candidate_count_per_task"])
    for packet in packets:
        for model in models:
            for candidate_index in range(1, candidate_count + 1):
                rows.append(
                    {
                        "packet_id": packet["packet_id"],
                        "task_id": packet["task_id"],
                        "unit_id": packet["unit_id"],
                        "ref": packet["ref"],
                        "layer": packet["layer"],
                        "judge_id": packet["judge_id"],
                        "model_profile_id": model,
                        "candidate_index": candidate_index,
                        "priority": packet["priority"],
                        "context_intensity": packet["context_pressure"]["intensity"],
                        "reception_sensitive": packet["reception_profile"]["sensitive"],
                        "reception_signal_band": packet["reception_signal_context"][
                            "pressure_band"
                        ],
                        "signal_family_count": packet["reception_signal_context"][
                            "signal_family_count"
                        ],
                        "canonical_intertext_score": packet["canonical_intertext_context"]["score"],
                        "anchor_token_count": packet["canonical_intertext_context"][
                            "anchor_token_count"
                        ],
                        "high_value_anchor_count": packet["canonical_intertext_context"][
                            "high_value_anchor_count"
                        ],
                        "three_division_evidence": packet["canonical_intertext_context"][
                            "has_three_division_evidence"
                        ],
                        "domain_count": packet["context_pressure"]["domain_count"],
                        "probe_count": len(packet["probe_questions"]),
                    }
                )
    return rows


def summarize(
    packets: list[dict[str, Any]],
    matrix_rows: list[dict[str, Any]],
    exec_rows: list[dict[str, Any]],
    suite: dict[str, Any],
    rubric: dict[str, Any],
) -> dict[str, Any]:
    judge_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    layer_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    signal_band_counts: Counter[str] = Counter()
    canonical_domain_counts: Counter[str] = Counter()
    canonical_book_counts: Counter[str] = Counter()
    reception_packets = 0
    canonical_packets = 0
    three_division_packets = 0
    high_packets = 0
    probe_total = 0
    for packet in packets:
        judge_counts[packet["judge_id"]] += 1
        priority_counts[packet["priority"]] += 1
        layer_counts[packet["layer"]] += 1
        role_counts.update(packet["required_human_roles"])
        domain_counts.update(packet["context_pressure"]["domains"])
        signal_counts.update(packet["reception_signal_context"]["signal_ids"])
        band = packet["reception_signal_context"]["pressure_band"]
        if band:
            signal_band_counts[str(band)] += 1
        intertext = packet["canonical_intertext_context"]
        if intertext["anchor_token_count"]:
            canonical_packets += 1
        if intertext["has_three_division_evidence"]:
            three_division_packets += 1
        canonical_domain_counts.update(intertext["domain_ids"])
        canonical_book_counts.update(str(book) for book in intertext["outside_book_counts"])
        probe_total += len(packet["probe_questions"])
        if packet["reception_profile"]["sensitive"]:
            reception_packets += 1
        if packet["priority"] == "high":
            high_packets += 1
    judge_count = len(rubric["model_cross_examination"])
    return {
        "task_count": int(suite["summary"]["task_count"]),
        "judge_count": judge_count,
        "packet_count": len(packets),
        "execution_row_count": len(exec_rows),
        "planned_model_count": len(suite["recommended_bakeoff_models"]),
        "candidate_count_per_task": int(suite["summary"]["candidate_count_per_task"]),
        "context_matrix_unit_count": len(matrix_rows),
        "high_priority_packets": high_packets,
        "reception_sensitive_packets": reception_packets,
        "canonical_intertext_packets": canonical_packets,
        "three_division_intertext_packets": three_division_packets,
        "probe_question_count": probe_total,
        "mean_probe_questions_per_packet": round(probe_total / len(packets), 2),
        "judge_packet_counts": dict(judge_counts.most_common()),
        "priority_counts": dict(priority_counts.most_common()),
        "layer_counts": dict(layer_counts.most_common()),
        "domain_packet_counts": dict(domain_counts.most_common()),
        "human_role_packet_counts": dict(role_counts.most_common()),
        "reception_signal_packet_counts": dict(signal_counts.most_common()),
        "reception_signal_band_packet_counts": dict(signal_band_counts.most_common()),
        "canonical_domain_packet_counts": dict(canonical_domain_counts.most_common()),
        "canonical_book_packet_counts": dict(canonical_book_counts.most_common(20)),
    }


def build_protocol(
    *,
    rubric_path: Path,
    suite_path: Path,
    context_matrix_path: Path,
) -> dict[str, Any]:
    rubric = load_json(rubric_path)
    suite = load_json(suite_path)
    matrix = load_json(context_matrix_path)
    context_rows = context_by_unit(matrix)
    packets = build_packets(suite, rubric, context_rows)
    exec_rows = execution_matrix(packets, suite)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated model cross-examination protocol; advisory only",
        "source_paths": {
            "rubric": project_path(rubric_path),
            "benchmark_suite": project_path(suite_path),
            "context_matrix": project_path(context_matrix_path),
        },
        "authority_policy": {
            "model_judges_are_authoritative": False,
            "required_use": (
                "Use Codex, Claude, and Hebrew-specialist critiques for triage "
                "and disagreement discovery only. Human role review remains "
                "the signoff authority."
            ),
        },
        "summary": summarize(
            packets,
            matrix.get("unit_rows", []),
            exec_rows,
            suite,
            rubric,
        ),
        "judge_output_contract": JUDGE_OUTPUT_CONTRACT,
        "model_cross_examination": rubric["model_cross_examination"],
        "packets": packets,
        "execution_matrix": exec_rows,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
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


def rows_from_counter(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
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
    left = 300
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


def render_html(protocol: dict[str, Any]) -> str:
    summary = protocol["summary"]
    mean_probe_note = f"{summary['mean_probe_questions_per_packet']:.2f} per packet."
    sample_rows = []
    for packet in protocol["packets"][:18]:
        intertext = packet["canonical_intertext_context"]
        context_label = (
            ", ".join(intertext["domain_labels"][:4])
            or ", ".join(packet["reception_signal_context"]["signal_labels"][:4])
            or ", ".join(packet["context_pressure"]["domains"][:4])
        )
        signal_or_anchor = (
            f"{intertext['anchor_token_count']} anchors"
            if intertext["anchor_token_count"]
            else packet["reception_signal_context"]["pressure_band"] or ""
        )
        sample_rows.append(
            [
                packet["packet_id"],
                packet["ref"],
                packet["layer"],
                packet["judge_id"],
                packet["priority"],
                packet["context_pressure"]["intensity"],
                len(packet["probe_questions"]),
                signal_or_anchor,
                context_label,
            ]
        )
    judge_rows = [
        [
            judge["judge_id"],
            judge["authority"],
            "; ".join(judge["focus"]),
        ]
        for judge in protocol["model_cross_examination"]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Model Cross-Examination Protocol</title>
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
    svg {{ width: 100%; height: auto; display: block; }}
    table {{ border-collapse: collapse; width: 100%; margin: 14px 0 24px; font-size: 13px; }}
    th, td {{ border: 1px solid var(--line); padding: 9px 10px; vertical-align: top; }}
    th {{ background: var(--band); text-align: left; }}
    code {{ font-family: Consolas, Monaco, monospace; }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AlephTav Model Cross-Examination Protocol</h1>
    <p class="lede">
      Advisory model-critic packets for Codex, Claude, and a Hebrew-specialist
      model. Each packet combines benchmark task evidence, context/reception
      routing, judge focus, and explicit probe questions. Model critiques are
      evidence for triage only; human review remains the signoff authority.
    </p>
    <p class="meta">Generated {esc(protocol["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Protocol Summary</h2>
      {
        metric_cards(
            [
                ("Tasks", fmt_int(summary["task_count"]), "Benchmark tasks covered."),
                ("Packets", fmt_int(summary["packet_count"]), "Task-by-judge packets."),
                (
                    "Execution rows",
                    fmt_int(summary["execution_row_count"]),
                    "Model, candidate, judge combinations.",
                ),
                (
                    "Probe questions",
                    fmt_int(summary["probe_question_count"]),
                    f"Mean {mean_probe_note}",
                ),
            ]
        )
    }
      <div class="warning">
        These packets are intentionally advisory. They are designed to find
        disagreement, unsupported claims, and reviewer routing issues, not to
        approve a translation.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["judge_packet_counts"], "judge"),
            label_key="judge",
            value_key="count",
            aria_label="Packets by model judge",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["priority_counts"], "priority"),
            label_key="priority",
            value_key="count",
            aria_label="Packets by priority",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["domain_packet_counts"], "domain"),
            label_key="domain",
            value_key="count",
            aria_label="Context domains across cross-exam packets",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["reception_signal_packet_counts"], "signal"),
            label_key="signal",
            value_key="count",
            aria_label="Reception signal families across cross-exam packets",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["canonical_domain_packet_counts"], "domain"),
            label_key="domain",
            value_key="count",
            aria_label="Canonical intertext domains across cross-exam packets",
            color="#355f7c",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["canonical_book_packet_counts"], "book"),
            label_key="book",
            value_key="count",
            aria_label="Canonical intertext book presence across cross-exam packets",
            color="#6f5d2f",
        )
    }</div>
    </section>

    <section>
      <h2>Model Critics</h2>
      {table(["Judge", "Authority", "Focus"], judge_rows)}
    </section>

    <section>
      <h2>Sample Packets</h2>
      {
        table(
            [
                "Packet",
                "Reference",
                "Layer",
                "Judge",
                "Priority",
                "Context",
                "Probe count",
                "Signal/anchors",
                "Signals or domains",
            ],
            sample_rows,
        )
    }
    </section>

    <section>
      <h2>Execution Files</h2>
      <p>
        Packet JSONL: <code>reports/research/model_cross_exam_packets.jsonl</code>
      </p>
      <p>
        Execution CSV:
        <code>reports/research/model_cross_exam_execution_matrix.csv</code>
      </p>
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate advisory model cross-examination packets."
    )
    parser.add_argument("--rubric", type=Path, default=RUBRIC_PATH)
    parser.add_argument("--suite", type=Path, default=SUITE_PATH)
    parser.add_argument("--context-matrix", type=Path, default=CONTEXT_MATRIX_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--jsonl-output", type=Path, default=DEFAULT_JSONL_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol = build_protocol(
        rubric_path=args.rubric,
        suite_path=args.suite,
        context_matrix_path=args.context_matrix,
    )
    write_json(args.json_output, protocol)
    write_jsonl(args.jsonl_output, protocol["packets"])
    write_csv(args.csv_output, protocol["execution_matrix"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(protocol), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.jsonl_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
