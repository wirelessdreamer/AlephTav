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
EXPANDED_SUITE_PATH = ROOT / "reports" / "research" / "contextual_expanded_benchmark_suite.json"
ATLAS_PATH = ROOT / "reports" / "research" / "contextual_pressure_atlas.json"
WITNESS_READINESS_PATH = ROOT / "reports" / "research" / "witness_reception_readiness.json"
CANONICAL_CONTEXT_PATH = ROOT / "reports" / "research" / "canonical_context_network.json"
REVIEW_PLAN_PATH = (
    ROOT / "reports" / "research" / "contextual_expanded_benchmark_review_signoff_plan.json"
)
RUBRIC_PATH = ROOT / "docs" / "research" / "psalms_contextual_evaluation_rubric.json"

DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "reception_interpretation_boundary.json"
DEFAULT_UNIT_CSV_OUTPUT = (
    ROOT / "reports" / "research" / "reception_interpretation_boundary_units.csv"
)
DEFAULT_FRAME_CSV_OUTPUT = (
    ROOT / "reports" / "research" / "reception_interpretation_boundary_frames.csv"
)
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "reception_interpretation_boundary.html"

RECEPTION_TAGS = {
    "jewish_christian_reception",
    "jewish_christian_reception_cases",
    "reception_history",
    "messianic_interpretation",
    "liturgical_afterlife",
}
TEXTUAL_TAGS = {
    "textual_witness",
    "textual_witness_cases",
    "textual_sensitivity",
    "lexical_ambiguity",
    "license_provenance_adversarial_cases",
}
CULTURE_TAGS = {
    "royal_psalm",
    "nations",
    "anthropology",
    "creation_hymn",
    "temple_liturgy",
    "imprecation",
    "violence",
    "trauma_context",
    "fear_of_yhwh",
    "torah_walk",
    "divine_beings",
    "melchizedek",
}
THEOLOGY_TAGS = {
    "divine_name_policy",
    "divine_title",
    "sonship",
    "messianic_interpretation",
    "divine_speech",
    "divine_address",
    "priesthood",
    "creation_hymn",
}

FRAME_POLICIES = {
    "source_hebrew_control": {
        "lane": "translation_basis",
        "allowed_location": "translation_text_and_rationale",
        "boundary": "Must preserve Hebrew grammar, tokens, and alignment before later frames.",
    },
    "source_hebrew_plain_sense": {
        "lane": "translation_basis",
        "allowed_location": "translation_text_and_rationale",
        "boundary": "Must be grounded in Hebrew tokens and alignment.",
    },
    "morphology_lexeme_control": {
        "lane": "translation_basis",
        "allowed_location": "translation_text_and_rationale",
        "boundary": "Must cite lexical or morphology evidence for disputed choices.",
    },
    "whole_tanakh_context": {
        "lane": "canonical_context",
        "allowed_location": "rationale_or_note",
        "boundary": "May retrieve cross-canon evidence; must not claim shared sense automatically.",
    },
    "ancient_cultural_setting": {
        "lane": "ancient_cultural_context",
        "allowed_location": "rationale_or_note",
        "boundary": "May explain ancient setting; must not override the Hebrew source basis.",
    },
    "ancient_royal_ideology": {
        "lane": "ancient_cultural_context",
        "allowed_location": "rationale_or_note",
        "boundary": "May explain royal/court imagery; must not settle later reception.",
    },
    "creation_anthropology": {
        "lane": "ancient_cultural_context",
        "allowed_location": "rationale_or_note",
        "boundary": "May explain anthropology/cosmos terms; must preserve token evidence.",
    },
    "temple_liturgy": {
        "lane": "ancient_cultural_context",
        "allowed_location": "rationale_or_note",
        "boundary": "May explain cultic/liturgical setting; witnesses stay labeled.",
    },
    "lament_genre": {
        "lane": "genre_context",
        "allowed_location": "rationale_or_note",
        "boundary": "May explain lament movement; do not soften hard source claims silently.",
    },
    "poetic_form_genre": {
        "lane": "genre_context",
        "allowed_location": "rationale_or_note",
        "boundary": "May explain poetic form; must preserve source image and alignment evidence.",
    },
    "textual_witnesses": {
        "lane": "textual_witness",
        "allowed_location": "tagged_note_only",
        "boundary": (
            "Witness readings must stay labeled and cannot silently replace the Hebrew basis."
        ),
    },
    "reception_history": {
        "lane": "reception_history",
        "allowed_location": "tagged_note_only",
        "boundary": "Must be separate from translation wording and source-basis claims.",
    },
    "jewish_christian_reception": {
        "lane": "reception_history",
        "allowed_location": "tagged_note_only",
        "boundary": "Must keep Jewish and Christian readings distinct.",
    },
    "jewish_reception": {
        "lane": "reception_history",
        "allowed_location": "tagged_note_only",
        "boundary": "Must be separate from Christian reception and translation wording.",
    },
    "christian_reception": {
        "lane": "reception_history",
        "allowed_location": "tagged_note_only",
        "boundary": "Must be separate from Jewish reception and translation wording.",
    },
    "academic_critical_comparison": {
        "lane": "critical_comparison",
        "allowed_location": "tagged_note_only",
        "boundary": "May compare views; must not override the Hebrew source basis.",
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


def unit_path(content_root: Path, unit_id: str) -> Path:
    psalm_id = unit_id.split(".")[0]
    return content_root / psalm_id / f"{unit_id}.json"


def case_studies_by_unit(rubric: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["unit_id"]): row for row in rubric.get("case_studies", []) if row.get("unit_id")
    }


def expanded_units(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for task in suite.get("tasks", []):
        unit_id = str(task["unit_id"])
        row = rows.setdefault(
            unit_id,
            {
                "unit_id": unit_id,
                "ref": task.get("ref", ""),
                "task_count": 0,
                "layers": set(),
                "benchmark_tags": Counter(),
                "suite_sources": Counter(),
                "contextual_case_layers": set(),
                "contextual_case_reason": "",
            },
        )
        row["task_count"] += 1
        row["layers"].add(str(task.get("layer") or ""))
        row["benchmark_tags"].update(str(tag) for tag in task.get("benchmark_tags", []))
        row["suite_sources"].update([str(task.get("suite_source") or "unknown")])
        context = task.get("generation_input", {}).get("locked_inputs", {}).get("context", {})
        row["contextual_case_layers"].update(
            str(layer) for layer in context.get("contextual_case_layers", [])
        )
        if not row["contextual_case_reason"] and context.get("contextual_case_reason"):
            row["contextual_case_reason"] = str(context["contextual_case_reason"])
    for row in rows.values():
        row["layers"] = sorted(layer for layer in row["layers"] if layer)
        row["benchmark_tags"] = dict(row["benchmark_tags"].most_common())
        row["suite_sources"] = dict(row["suite_sources"].most_common())
        row["contextual_case_layers"] = sorted(row["contextual_case_layers"])
    return rows


def atlas_by_unit(atlas: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["unit_id"]): row
        for row in atlas.get("priority_unit_rows", [])
        if row.get("unit_id")
    }


def canonical_context_by_unit(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["unit_id"]): row
        for row in context.get("unit_network_rows", [])
        if row.get("unit_id")
    }


def review_plan_by_unit(review_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for task in review_plan.get("task_review_plan", []):
        unit_id = str(task["unit_id"])
        row = rows.setdefault(
            unit_id,
            {
                "unit_id": unit_id,
                "required_roles": set(),
                "task_intensity_counts": Counter(),
                "review_task_count": 0,
            },
        )
        row["required_roles"].update(str(role) for role in task.get("required_roles", []))
        row["task_intensity_counts"].update([str(task.get("intensity") or "standard")])
        row["review_task_count"] += 1
    for row in rows.values():
        row["required_roles"] = sorted(row["required_roles"])
        row["task_intensity_counts"] = dict(row["task_intensity_counts"].most_common())
    return rows


def load_unit_witnesses(content_root: Path, unit_id: str) -> list[dict[str, Any]]:
    path = unit_path(content_root, unit_id)
    if not path.exists():
        return []
    return load_json(path).get("witnesses", [])


def witness_summary(witnesses: list[dict[str, Any]]) -> dict[str, Any]:
    sources = Counter(str(row.get("source_id") or "unknown") for row in witnesses)
    languages = Counter(str(row.get("language") or "unknown") for row in witnesses)
    roles = Counter(str(row.get("witness_role") or "unknown") for row in witnesses)
    english_lengths = [
        len(str(row.get("text") or "").split()) for row in witnesses if row.get("language") == "en"
    ]
    lxx_lengths = [
        len(str(row.get("text") or "").split())
        for row in witnesses
        if row.get("source_id") == "lxx"
    ]
    return {
        "witness_count": len(witnesses),
        "source_counts": dict(sources.most_common()),
        "language_counts": dict(languages.most_common()),
        "role_counts": dict(roles.most_common()),
        "has_lxx": bool(sources.get("lxx")),
        "english_witness_count": int(languages.get("en", 0)),
        "english_witness_word_range": (
            f"{min(english_lengths)}-{max(english_lengths)}" if english_lengths else ""
        ),
        "lxx_word_count": lxx_lengths[0] if lxx_lengths else 0,
    }


def frame_rows_for_unit(unit_id: str, frames: list[str]) -> list[dict[str, Any]]:
    rows = []
    for frame in frames:
        policy = FRAME_POLICIES.get(
            frame,
            {
                "lane": "unclassified",
                "allowed_location": "review_required",
                "boundary": "No explicit frame policy exists.",
            },
        )
        rows.append(
            {
                "unit_id": unit_id,
                "frame": frame,
                "lane": policy["lane"],
                "allowed_location": policy["allowed_location"],
                "boundary": policy["boundary"],
            }
        )
    return rows


def claim_controls(
    tags: set[str],
    frames: set[str],
    domains: set[str],
) -> list[str]:
    controls = [
        "translation_text_must_use_hebrew_source_basis",
        "witnesses_must_be_labeled_as_witnesses",
    ]
    if frames & {"jewish_reception", "christian_reception"} or tags & RECEPTION_TAGS:
        controls.extend(
            [
                "jewish_and_christian_reception_must_be_separate",
                "reception_claims_must_stay_out_of_translation_text",
            ]
        )
    if tags & TEXTUAL_TAGS or "textual_witness_pressure" in domains:
        controls.append("textual_witness_variants_must_not_silently_override_hebrew")
    if frames & {"ancient_royal_ideology", "creation_anthropology", "temple_liturgy"}:
        controls.append("ancient_culture_claims_require_tagged_rationale")
    if tags & THEOLOGY_TAGS or "divine_names_titles" in domains:
        controls.append("theological_terms_require_policy_and_reviewer_check")
    return sorted(set(controls))


def boundary_risk_score(
    *,
    tags: set[str],
    frames: set[str],
    domains: set[str],
    complete_witness_set: bool,
    content_context_pct: float,
    review_flag_count: int,
    role_count: int,
) -> float:
    score = 0.0
    if tags & RECEPTION_TAGS or frames & {"jewish_reception", "christian_reception"}:
        score += 24
    if tags & TEXTUAL_TAGS or "textual_witness_pressure" in domains:
        score += 18
    if tags & CULTURE_TAGS:
        score += 10
    if tags & THEOLOGY_TAGS:
        score += 12
    if not complete_witness_set:
        score += 12
    score += max(0.0, (100.0 - content_context_pct) / 5)
    score += min(12.0, review_flag_count * 2.0)
    score += min(10.0, role_count * 1.5)
    score += min(8.0, len(domains) * 0.8)
    return round(min(score, 100.0), 2)


def risk_band(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "standard"


def build_unit_rows(
    content_root: Path,
    suite_units: dict[str, dict[str, Any]],
    atlas_units: dict[str, dict[str, Any]],
    context_units: dict[str, dict[str, Any]],
    review_units: dict[str, dict[str, Any]],
    case_units: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unit_rows = []
    frame_rows = []
    for unit_id, suite_unit in sorted(suite_units.items()):
        atlas_row = atlas_units.get(unit_id, {})
        context_row = context_units.get(unit_id, {})
        review_row = review_units.get(unit_id, {})
        case_row = case_units.get(unit_id, {})
        tags = set(suite_unit.get("benchmark_tags", {}).keys())
        domains = set(atlas_row.get("domains", []))
        frames = set(atlas_row.get("required_frames", []))
        frames.update(suite_unit.get("contextual_case_layers", []))
        if case_row:
            frames.update(str(layer) for layer in case_row.get("layers", []))
        if tags & {"jewish_christian_reception", "jewish_christian_reception_cases"}:
            frames.update(
                {
                    "jewish_christian_reception",
                    "jewish_reception",
                    "christian_reception",
                    "academic_critical_comparison",
                }
            )
        elif tags & {"reception_history", "liturgical_afterlife", "messianic_interpretation"}:
            frames.add("reception_history")
        frames.add("source_hebrew_plain_sense")

        witnesses = load_unit_witnesses(content_root, unit_id)
        witness = witness_summary(witnesses)
        complete_witness_set = witness["has_lxx"] and witness["english_witness_count"] >= 3
        review_roles = set(review_row.get("required_roles", []))
        review_roles.update(str(role) for role in atlas_row.get("review_roles", []))
        content_context_pct = float(
            context_row.get("content_token_outside_context_pct")
            or context_row.get("surface_outside_context_pct")
            or 0.0
        )
        controls = claim_controls(tags, frames, domains)
        score = boundary_risk_score(
            tags=tags,
            frames=frames,
            domains=domains,
            complete_witness_set=complete_witness_set,
            content_context_pct=content_context_pct,
            review_flag_count=len(context_row.get("review_flags", [])),
            role_count=len(review_roles),
        )
        unit_frames = sorted(frames)
        frame_rows.extend(frame_rows_for_unit(unit_id, unit_frames))
        unit_rows.append(
            {
                "unit_id": unit_id,
                "ref": suite_unit.get("ref") or atlas_row.get("ref", ""),
                "task_count": suite_unit["task_count"],
                "layers": suite_unit["layers"],
                "benchmark_tags": sorted(tags),
                "domains": sorted(domains),
                "domain_count": len(domains),
                "required_frames": unit_frames,
                "required_frame_count": len(unit_frames),
                "required_review_roles": sorted(review_roles),
                "required_review_role_count": len(review_roles),
                "claim_controls": controls,
                "claim_control_count": len(controls),
                "reception_sensitive": bool(
                    tags & RECEPTION_TAGS
                    or frames & {"jewish_reception", "christian_reception"}
                    or "jewish_christian_reception" in domains
                ),
                "textual_witness_pressure": bool(
                    tags & TEXTUAL_TAGS or "textual_witness_pressure" in domains
                ),
                "ancient_culture_pressure": bool(
                    tags & CULTURE_TAGS
                    or frames
                    & {
                        "ancient_royal_ideology",
                        "creation_anthropology",
                        "temple_liturgy",
                        "lament_genre",
                    }
                ),
                "theology_pressure": bool(tags & THEOLOGY_TAGS or "theology" in review_roles),
                "has_jewish_reception_frame": "jewish_reception" in frames,
                "has_christian_reception_frame": "christian_reception" in frames,
                "has_academic_comparison_frame": "academic_critical_comparison" in frames,
                "witness_count": witness["witness_count"],
                "witness_sources": witness["source_counts"],
                "witness_languages": witness["language_counts"],
                "has_lxx": witness["has_lxx"],
                "english_witness_count": witness["english_witness_count"],
                "complete_expected_witness_set": complete_witness_set,
                "english_witness_word_range": witness["english_witness_word_range"],
                "lxx_word_count": witness["lxx_word_count"],
                "content_token_outside_context_pct": content_context_pct,
                "context_review_flags": context_row.get("review_flags", []),
                "context_evidence_grade": context_row.get("evidence_grade", ""),
                "case_study_reason": case_row.get("why")
                or suite_unit.get("contextual_case_reason", ""),
                "boundary_risk_score": score,
                "boundary_risk_band": risk_band(score),
            }
        )
    return (
        sorted(
            unit_rows,
            key=lambda row: (
                float(row["boundary_risk_score"]),
                int(row["claim_control_count"]),
                str(row["unit_id"]),
            ),
            reverse=True,
        ),
        frame_rows,
    )


def frame_summary_rows(frame_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    units_by_frame: dict[str, set[str]] = defaultdict(set)
    lane_counts: Counter[str] = Counter()
    location_counts: Counter[str] = Counter()
    policy_by_frame: dict[str, dict[str, str]] = {}
    for row in frame_rows:
        units_by_frame[str(row["frame"])].add(str(row["unit_id"]))
        lane_counts[str(row["lane"])] += 1
        location_counts[str(row["allowed_location"])] += 1
        policy_by_frame[str(row["frame"])] = {
            "lane": str(row["lane"]),
            "allowed_location": str(row["allowed_location"]),
            "boundary": str(row["boundary"]),
        }
    return [
        {
            "frame": frame,
            "unit_count": len(units),
            "lane": policy_by_frame[frame]["lane"],
            "allowed_location": policy_by_frame[frame]["allowed_location"],
            "boundary": policy_by_frame[frame]["boundary"],
        }
        for frame, units in sorted(
            units_by_frame.items(),
            key=lambda item: (len(item[1]), item[0]),
            reverse=True,
        )
    ]


def summarize(unit_rows: list[dict[str, Any]], frame_rows: list[dict[str, Any]]) -> dict[str, Any]:
    reception_units = [row for row in unit_rows if row["reception_sensitive"]]
    textual_units = [row for row in unit_rows if row["textual_witness_pressure"]]
    culture_units = [row for row in unit_rows if row["ancient_culture_pressure"]]
    theology_units = [row for row in unit_rows if row["theology_pressure"]]
    both_reception = [
        row
        for row in unit_rows
        if row["has_jewish_reception_frame"] and row["has_christian_reception_frame"]
    ]
    complete_witness = [row for row in unit_rows if row["complete_expected_witness_set"]]
    high_risk = [row for row in unit_rows if row["boundary_risk_band"] == "high"]
    medium_risk = [row for row in unit_rows if row["boundary_risk_band"] == "medium"]
    return {
        "unit_count": len(unit_rows),
        "task_count": sum(int(row["task_count"]) for row in unit_rows),
        "frame_assignment_count": len(frame_rows),
        "distinct_frame_count": len({row["frame"] for row in frame_rows}),
        "reception_sensitive_unit_count": len(reception_units),
        "textual_witness_pressure_unit_count": len(textual_units),
        "ancient_culture_pressure_unit_count": len(culture_units),
        "theology_pressure_unit_count": len(theology_units),
        "both_jewish_christian_frame_unit_count": len(both_reception),
        "academic_comparison_unit_count": sum(
            1 for row in unit_rows if row["has_academic_comparison_frame"]
        ),
        "complete_witness_set_unit_count": len(complete_witness),
        "complete_witness_set_pct": pct(len(complete_witness), len(unit_rows)),
        "avg_boundary_risk_score": mean([float(row["boundary_risk_score"]) for row in unit_rows]),
        "high_boundary_risk_unit_count": len(high_risk),
        "medium_boundary_risk_unit_count": len(medium_risk),
        "standard_boundary_risk_unit_count": len(unit_rows) - len(high_risk) - len(medium_risk),
        "translation_text_forbidden_reception_claim_units": len(reception_units),
        "witness_boundary_control_unit_count": sum(
            1
            for row in unit_rows
            if "witnesses_must_be_labeled_as_witnesses" in row["claim_controls"]
        ),
        "jewish_christian_separation_control_unit_count": sum(
            1
            for row in unit_rows
            if "jewish_and_christian_reception_must_be_separate" in row["claim_controls"]
        ),
        "top_boundary_risk_unit": unit_rows[0]["unit_id"] if unit_rows else "",
        "top_boundary_risk_score": unit_rows[0]["boundary_risk_score"] if unit_rows else 0.0,
    }


def domain_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    domains: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        for domain in row["domains"] or ["unclassified"]:
            domains[str(domain)].append(row)
    rows = []
    for domain, values in domains.items():
        rows.append(
            {
                "domain": domain,
                "unit_count": len(values),
                "reception_sensitive_count": sum(1 for row in values if row["reception_sensitive"]),
                "textual_witness_pressure_count": sum(
                    1 for row in values if row["textual_witness_pressure"]
                ),
                "ancient_culture_pressure_count": sum(
                    1 for row in values if row["ancient_culture_pressure"]
                ),
                "avg_boundary_risk_score": mean(
                    [float(row["boundary_risk_score"]) for row in values]
                ),
                "high_boundary_risk_count": sum(
                    1 for row in values if row["boundary_risk_band"] == "high"
                ),
                "complete_witness_set_pct": pct(
                    sum(1 for row in values if row["complete_expected_witness_set"]),
                    len(values),
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            float(row["avg_boundary_risk_score"]),
            int(row["unit_count"]),
            str(row["domain"]),
        ),
        reverse=True,
    )


def csv_unit_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "unit_id": row["unit_id"],
            "ref": row["ref"],
            "task_count": row["task_count"],
            "boundary_risk_score": row["boundary_risk_score"],
            "boundary_risk_band": row["boundary_risk_band"],
            "reception_sensitive": row["reception_sensitive"],
            "textual_witness_pressure": row["textual_witness_pressure"],
            "ancient_culture_pressure": row["ancient_culture_pressure"],
            "theology_pressure": row["theology_pressure"],
            "required_frames": "|".join(row["required_frames"]),
            "claim_controls": "|".join(row["claim_controls"]),
            "required_review_roles": "|".join(row["required_review_roles"]),
            "complete_expected_witness_set": row["complete_expected_witness_set"],
            "content_token_outside_context_pct": row["content_token_outside_context_pct"],
            "benchmark_tags": "|".join(row["benchmark_tags"]),
            "domains": "|".join(row["domains"]),
        }
        for row in unit_rows
    ]


def build_report(
    content_root: Path,
    expanded_suite_path: Path,
    atlas_path: Path,
    witness_readiness_path: Path,
    canonical_context_path: Path,
    review_plan_path: Path,
    rubric_path: Path,
) -> dict[str, Any]:
    suite = load_json(expanded_suite_path)
    atlas = load_json(atlas_path)
    witness = load_json(witness_readiness_path)
    canonical_context = load_json(canonical_context_path)
    review_plan = load_json(review_plan_path)
    rubric = load_json(rubric_path)

    unit_rows, unit_frame_rows = build_unit_rows(
        content_root,
        expanded_units(suite),
        atlas_by_unit(atlas),
        canonical_context_by_unit(canonical_context),
        review_plan_by_unit(review_plan),
        case_studies_by_unit(rubric),
    )
    frame_summary = frame_summary_rows(unit_frame_rows)
    domains = domain_rows(unit_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated reception and interpretation boundary ledger",
        "source_paths": {
            "content_root": str(content_root.relative_to(ROOT)),
            "expanded_suite": str(expanded_suite_path.relative_to(ROOT)),
            "contextual_pressure_atlas": str(atlas_path.relative_to(ROOT)),
            "witness_readiness": str(witness_readiness_path.relative_to(ROOT)),
            "canonical_context_network": str(canonical_context_path.relative_to(ROOT)),
            "expanded_review_plan": str(review_plan_path.relative_to(ROOT)),
            "contextual_rubric": str(rubric_path.relative_to(ROOT)),
        },
        "evidence_policy": {
            "translation_basis": "Hebrew source tokens and alignment.",
            "witness_boundary": "LXX and English witnesses are evidence, not generation basis.",
            "reception_boundary": (
                "Jewish, Christian, liturgical, and academic reception claims "
                "must be tagged outside translation text."
            ),
            "cultural_boundary": (
                "Ancient culture frames can guide rationale and review, but do "
                "not authorize unsupported smoothing."
            ),
        },
        "source_summary": {
            "expanded_suite": suite.get("summary", {}),
            "witness_readiness": witness.get("summary", {}),
            "canonical_context_network": canonical_context.get("summary", {}),
            "review_plan": review_plan.get("summary", {}),
        },
        "summary": summarize(unit_rows, unit_frame_rows),
        "frame_summary_rows": frame_summary,
        "domain_boundary_rows": domains,
        "unit_boundary_rows": unit_rows,
        "unit_frame_rows": unit_frame_rows,
    }


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    width: int = 980,
    limit: int = 18,
) -> str:
    rows = rows[:limit]
    row_h = 30
    left = 290
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
            f'<text x="{left - 12}" y="{y + 19}" text-anchor="end" '
            f'font-size="12" fill="#26323a">{esc(row[label_key])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="19" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 19}" font-size="12" '
            f'font-weight="700" fill="#26323a">{value:g}</text>'
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
        + "".join(
            "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows
        )
        + "</tbody></table>"
    )


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    frame_rows = [
        [
            row["frame"],
            row["unit_count"],
            row["lane"],
            row["allowed_location"],
            row["boundary"],
        ]
        for row in report["frame_summary_rows"]
    ]
    domain_rows_for_table = [
        [
            row["domain"],
            row["unit_count"],
            row["reception_sensitive_count"],
            row["textual_witness_pressure_count"],
            row["ancient_culture_pressure_count"],
            f"{row['avg_boundary_risk_score']:.2f}",
            row["high_boundary_risk_count"],
        ]
        for row in report["domain_boundary_rows"]
    ]
    unit_rows = [
        [
            row["unit_id"],
            row["ref"],
            row["boundary_risk_band"],
            f"{row['boundary_risk_score']:.2f}",
            ", ".join(row["required_frames"]),
            ", ".join(row["claim_controls"]),
            row["case_study_reason"],
        ]
        for row in report["unit_boundary_rows"][:30]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Reception Interpretation Boundary</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2b33;
      --muted: #63717a;
      --line: #d8dee3;
      --band: #f4f7f7;
      --accent: #2f6f73;
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
      background: #f8faf9;
    }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 30px 34px 54px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    p {{ color: var(--muted); max-width: 980px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 14px;
      margin: 20px 0;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: #ffffff;
    }}
    .metric {{ font-size: 28px; font-weight: 800; color: var(--accent); }}
    .label {{ font-weight: 700; margin-top: 4px; }}
    .note {{
      border-left: 4px solid var(--accent2);
      background: var(--band);
      padding: 12px 14px;
      margin: 18px 0;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 14px 0 24px;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: var(--band); font-size: 12px; text-transform: uppercase; }}
    .chart {{ border: 1px solid var(--line); border-radius: 8px; overflow-x: auto; }}
    code {{ background: #eef2f2; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <header>
    <h1>Reception and Interpretation Boundary Ledger</h1>
    <p>
      Unit-level controls for keeping Hebrew-source translation claims,
      witnesses, ancient cultural framing, Jewish reception, Christian reception,
      and academic comparison in separate lanes.
    </p>
  </header>
  <main>
    {
        metric_cards(
            [
                (
                    "Expanded Units",
                    fmt_int(summary["unit_count"]),
                    "Unique benchmark units audited.",
                ),
                (
                    "Reception Units",
                    fmt_int(summary["reception_sensitive_unit_count"]),
                    "Units requiring reception-history separation.",
                ),
                (
                    "Both Traditions",
                    fmt_int(summary["both_jewish_christian_frame_unit_count"]),
                    "Units requiring distinct Jewish and Christian reception lanes.",
                ),
                (
                    "Textual Witness",
                    fmt_int(summary["textual_witness_pressure_unit_count"]),
                    "Units where witness boundaries need explicit review.",
                ),
                (
                    "Ancient Culture",
                    fmt_int(summary["ancient_culture_pressure_unit_count"]),
                    "Units with cultural, royal, cultic, lament, or anthropology pressure.",
                ),
                (
                    "Avg Risk",
                    f'''{summary["avg_boundary_risk_score"]:.2f}''',
                    "Heuristic boundary-control risk; not a quality score.",
                ),
                (
                    "Complete Witnesses",
                    f'''{summary["complete_witness_set_pct"]:.2f}%''',
                    "Expanded units with LXX plus three English witness rows.",
                ),
                (
                    "High Risk",
                    fmt_int(summary["high_boundary_risk_unit_count"]),
                    "Units requiring strict claim-boundary review.",
                ),
            ]
        )
    }

    <div class="note">
      Boundary policy: reception history and witness evidence can inform notes
      and review, but must not silently become the translation basis. Hebrew
      source tokens and alignment remain the translation basis.
    </div>

    <h2>Frame Policy</h2>
    {table(["Frame", "Units", "Lane", "Allowed Location", "Boundary"], frame_rows)}

    <h2>Domain Risk</h2>
    <div class="chart">
      {
        svg_horizontal_bars(
            report["domain_boundary_rows"],
            label_key="domain",
            value_key="avg_boundary_risk_score",
            aria_label="Average interpretation boundary risk by domain",
            color="#9b3d3d",
        )
    }
    </div>
    {
        table(
            [
                "Domain",
                "Units",
                "Reception",
                "Textual Witness",
                "Ancient Culture",
                "Avg Risk",
                "High Risk",
            ],
            domain_rows_for_table,
        )
    }

    <h2>Highest Boundary Risk Units</h2>
    {
        table(
            [
                "Unit",
                "Reference",
                "Band",
                "Score",
                "Required Frames",
                "Claim Controls",
                "Case Reason",
            ],
            unit_rows,
        )
    }
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate reception and interpretation boundary report."
    )
    parser.add_argument("--content-root", type=Path, default=CONTENT_ROOT)
    parser.add_argument("--expanded-suite", type=Path, default=EXPANDED_SUITE_PATH)
    parser.add_argument("--atlas", type=Path, default=ATLAS_PATH)
    parser.add_argument("--witness-readiness", type=Path, default=WITNESS_READINESS_PATH)
    parser.add_argument("--canonical-context", type=Path, default=CANONICAL_CONTEXT_PATH)
    parser.add_argument("--review-plan", type=Path, default=REVIEW_PLAN_PATH)
    parser.add_argument("--rubric", type=Path, default=RUBRIC_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--frame-csv-output", type=Path, default=DEFAULT_FRAME_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        args.content_root,
        args.expanded_suite,
        args.atlas,
        args.witness_readiness,
        args.canonical_context,
        args.review_plan,
        args.rubric,
    )
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, csv_unit_rows(report["unit_boundary_rows"]))
    write_csv(args.frame_csv_output, report["frame_summary_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")


if __name__ == "__main__":
    main()
