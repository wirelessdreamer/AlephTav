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
SUITE_PATH = REPORT_ROOT / "contextual_expanded_benchmark_suite.json"
ATLAS_PATH = REPORT_ROOT / "contextual_pressure_atlas.json"
RECEPTION_BOUNDARY_PATH = REPORT_ROOT / "reception_interpretation_boundary.json"
CANONICAL_CONTEXT_PATH = REPORT_ROOT / "canonical_context_network.json"
MORPHOLOGY_GAP_PATH = REPORT_ROOT / "whole_tanakh_morphology_gap.json"
WITNESS_PATH = REPORT_ROOT / "witness_reception_readiness.json"
REVIEW_PLAN_PATH = REPORT_ROOT / "contextual_expanded_benchmark_review_signoff_plan.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "translation_claim_evidence_matrix.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "translation_claim_evidence_matrix_units.csv"
DEFAULT_CONTROL_CSV_OUTPUT = REPORT_ROOT / "translation_claim_evidence_matrix_controls.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "translation_claim_evidence_matrix.html"

HIGH_RISK_TAGS = {
    "anthropology",
    "divine_name_policy",
    "hesed",
    "imprecation",
    "jewish_christian_reception",
    "lexical_dispute",
    "messianic_interpretation",
    "reception_history",
    "textual_witness",
    "violence",
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


def unique(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def rows_by_unit(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in rows}


def suite_unit_rows(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
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
                "source_task_counts": Counter(),
            },
        )
        row["task_count"] += 1
        row["layers"].add(str(task.get("layer", "")))
        row["benchmark_tags"].update(str(tag) for tag in task.get("benchmark_tags", []))
        row["source_task_counts"].update([str(task.get("source_suite", ""))])
    for row in rows.values():
        row["layers"] = sorted(row["layers"])
        row["benchmark_tags"] = dict(row["benchmark_tags"].most_common())
        row["source_task_counts"] = dict(row["source_task_counts"].most_common())
    return rows


def review_rows_by_unit(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for task in plan.get("task_review_plan", []):
        unit_id = str(task["unit_id"])
        row = rows.setdefault(
            unit_id,
            {
                "unit_id": unit_id,
                "required_roles": set(),
                "intensity_counts": Counter(),
                "task_count": 0,
            },
        )
        row["task_count"] += 1
        row["required_roles"].update(str(role) for role in task.get("required_roles", []))
        row["intensity_counts"].update([str(task.get("intensity", "standard"))])
    for row in rows.values():
        row["required_roles"] = sorted(row["required_roles"])
        row["intensity_counts"] = dict(row["intensity_counts"].most_common())
    return rows


def basis_statuses(
    *,
    canonical: dict[str, Any],
    morph: dict[str, Any],
    witness: dict[str, Any],
    reception: dict[str, Any],
) -> dict[str, str]:
    content_context_pct = float(canonical.get("content_token_outside_context_pct") or 0)
    outside_strong_pct = float(morph.get("outside_strong_context_pct") or 0)
    if outside_strong_pct > 0:
        tanakh_status = "lemma/Strong evidence available"
    elif content_context_pct > 0:
        tanakh_status = "surface bridge only"
    else:
        tanakh_status = "weak or absent"

    strong_pct = float(morph.get("strong_coverage_pct") or 0)
    if strong_pct >= 95:
        morphology_status = "Psalm morphology strong; non-Psalm morphology absent"
    elif strong_pct > 0:
        morphology_status = "Psalm morphology partial; non-Psalm morphology absent"
    else:
        morphology_status = "morphology weak or absent"

    witness_status = (
        "complete labeled witnesses"
        if witness.get("complete_expected_witness_set")
        else "missing expected witnesses"
    )
    if reception.get("has_jewish_reception_frame") and reception.get(
        "has_christian_reception_frame"
    ):
        reception_status = "Jewish/Christian separation required"
    elif reception.get("reception_sensitive"):
        reception_status = "reception-sensitive"
    else:
        reception_status = "plain-sense primary"

    return {
        "hebrew_source": "required translation basis",
        "morphology": morphology_status,
        "whole_tanakh": tanakh_status,
        "witness": witness_status,
        "reception": reception_status,
    }


def controls_for_unit(
    *,
    atlas: dict[str, Any],
    reception: dict[str, Any],
    morph: dict[str, Any],
    witness: dict[str, Any],
) -> list[str]:
    controls = [
        "translation_text_must_use_hebrew_source_basis",
        "cite_token_id_evidence_for_lexical_claims",
        "whole_tanakh_surface_matches_must_not_be_called_lemma_proof",
    ]
    controls.extend(str(item) for item in reception.get("claim_controls", []))
    controls.extend(str(item) for item in atlas.get("model_controls", []))
    if float(morph.get("outside_strong_context_pct") or 0) == 0:
        controls.append("non_psalm_strong_claims_are_unsupported_locally")
    if witness.get("english_witness_count", 0):
        controls.append("english_witnesses_are_blocked_generation_sources")
    if reception.get("reception_sensitive"):
        controls.append("reception_claims_must_stay_out_of_translation_text")
    if reception.get("textual_witness_pressure"):
        controls.append("textual_witness_variants_must_not_silently_override_hebrew")
    if reception.get("ancient_culture_pressure"):
        controls.append("ancient_culture_claims_require_tagged_rationale")
    if reception.get("theology_pressure"):
        controls.append("theological_terms_require_policy_and_reviewer_check")
    return sorted(unique(controls))


def allowed_claim_lanes(row: dict[str, Any]) -> dict[str, list[str]]:
    translation_text = ["Hebrew source rendering with token-aligned basis"]
    rationale = [
        "Hebrew lexical and morphology evidence",
        "labeled UXLC surface-form context",
        "labeled textual witnesses",
    ]
    reviewer_notes = [
        "whole-Tanakh lemma/sense adjudication",
        "source-image and poetic-risk adjudication",
    ]
    if row["reception_sensitive"]:
        rationale.append("separate Jewish and Christian reception summaries")
        reviewer_notes.append("theology/reception boundary decision")
    if row["ancient_culture_pressure"]:
        rationale.append("tagged ancient-cultural setting claim")
    if row["textual_witness_pressure"]:
        rationale.append("witness variant discussion without source override")
    forbidden_translation_text = [
        "unlabeled reception-history claims",
        "English-witness wording as generation basis",
        "whole-Tanakh lemma/sense claims from surface-form matches",
    ]
    return {
        "translation_text_allowed": translation_text,
        "rationale_allowed": rationale,
        "reviewer_notes_required": reviewer_notes,
        "translation_text_forbidden": forbidden_translation_text,
    }


def risk_band(score: float) -> str:
    if score >= 95:
        return "high"
    if score >= 70:
        return "medium"
    return "standard"


def build_unit_row(
    unit: dict[str, Any],
    *,
    atlas: dict[str, Any],
    reception: dict[str, Any],
    canonical: dict[str, Any],
    morph: dict[str, Any],
    witness: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    tags = sorted(unit.get("benchmark_tags", {}).keys())
    high_risk_tags = sorted(tag for tag in tags if tag in HIGH_RISK_TAGS)
    domains = sorted(
        set(atlas.get("domains", []))
        | set(reception.get("domains", []))
        | set(canonical.get("domains", []))
    )
    domain_groups = sorted(
        set(atlas.get("domain_groups", [])) | set(canonical.get("domain_groups", []))
    )
    required_frames = sorted(
        set(atlas.get("required_frames", [])) | set(reception.get("required_frames", []))
    )
    required_roles = sorted(
        set(review.get("required_roles", []))
        | set(reception.get("required_review_roles", []))
        | set(atlas.get("review_roles", []))
    )
    statuses = basis_statuses(
        canonical=canonical,
        morph=morph,
        witness=witness,
        reception=reception,
    )
    row = {
        "unit_id": unit["unit_id"],
        "ref": unit["ref"],
        "task_count": unit["task_count"],
        "layers": unit["layers"],
        "benchmark_tags": tags,
        "high_risk_tags": high_risk_tags,
        "domains": domains,
        "domain_groups": domain_groups,
        "required_frames": required_frames,
        "required_review_roles": required_roles,
        "review_intensity_counts": review.get("intensity_counts", {}),
        "reception_sensitive": bool(reception.get("reception_sensitive")),
        "textual_witness_pressure": bool(reception.get("textual_witness_pressure")),
        "ancient_culture_pressure": bool(reception.get("ancient_culture_pressure")),
        "theology_pressure": bool(reception.get("theology_pressure")),
        "has_jewish_reception_frame": bool(reception.get("has_jewish_reception_frame")),
        "has_christian_reception_frame": bool(reception.get("has_christian_reception_frame")),
        "has_academic_comparison_frame": bool(reception.get("has_academic_comparison_frame")),
        "complete_expected_witness_set": bool(witness.get("complete_expected_witness_set")),
        "witness_count": int(witness.get("witness_count") or reception.get("witness_count") or 0),
        "english_witness_count": int(
            witness.get("english_witness_count") or reception.get("english_witness_count") or 0
        ),
        "has_lxx": bool(witness.get("has_lxx") or reception.get("has_lxx")),
        "content_token_outside_context_pct": float(
            canonical.get("content_token_outside_context_pct") or 0
        ),
        "surface_outside_context_pct": float(
            canonical.get("surface_outside_context_pct")
            or morph.get("surface_outside_context_pct")
            or atlas.get("surface_outside_context_pct")
            or 0
        ),
        "outside_strong_context_pct": float(morph.get("outside_strong_context_pct") or 0),
        "morphology_gap_risk_score": float(morph.get("morphology_gap_risk_score") or 0),
        "boundary_risk_score": float(reception.get("boundary_risk_score") or 0),
        "context_priority_score": float(atlas.get("priority_score") or 0),
        "basis_statuses": statuses,
    }
    row["claim_controls"] = controls_for_unit(
        atlas=atlas,
        reception=reception,
        morph=morph,
        witness=witness,
    )
    row["allowed_claim_lanes"] = allowed_claim_lanes(row)
    row["claim_risk_score"] = round(
        row["boundary_risk_score"]
        + row["morphology_gap_risk_score"] / 3
        + row["context_priority_score"] / 2
        + len(high_risk_tags) * 3
        + (10 if row["reception_sensitive"] else 0)
        + (8 if row["textual_witness_pressure"] else 0)
        + (8 if row["ancient_culture_pressure"] else 0),
        2,
    )
    row["claim_risk_band"] = risk_band(float(row["claim_risk_score"]))
    return row


def build_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    suite_units = suite_unit_rows(data["suite"])
    atlas_rows = rows_by_unit(data["atlas"].get("priority_unit_rows", []))
    reception_rows = rows_by_unit(data["reception"].get("unit_boundary_rows", []))
    canonical_rows = rows_by_unit(data["canonical"].get("unit_network_rows", []))
    morph_rows = rows_by_unit(data["morphology"].get("benchmark_unit_rows", []))
    witness_rows = rows_by_unit(data["witness"].get("witness_unit_rows", []))
    review_rows = review_rows_by_unit(data["review_plan"])
    rows = []
    for unit_id, unit in suite_units.items():
        rows.append(
            build_unit_row(
                unit,
                atlas=atlas_rows.get(unit_id, {}),
                reception=reception_rows.get(unit_id, {}),
                canonical=canonical_rows.get(unit_id, {}),
                morph=morph_rows.get(unit_id, {}),
                witness=witness_rows.get(unit_id, {}),
                review=review_rows.get(unit_id, {}),
            )
        )
    return sorted(
        rows,
        key=lambda row: (
            float(row["claim_risk_score"]),
            str(row["unit_id"]),
        ),
        reverse=True,
    )


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    risk_bands = Counter(str(row["claim_risk_band"]) for row in rows)
    control_counts: Counter[str] = Counter()
    frame_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    basis_counts: Counter[str] = Counter()
    for row in rows:
        control_counts.update(row["claim_controls"])
        frame_counts.update(row["required_frames"])
        role_counts.update(row["required_review_roles"])
        basis_counts.update(row["basis_statuses"].values())
    return {
        "unit_count": len(rows),
        "high_risk_unit_count": risk_bands["high"],
        "medium_risk_unit_count": risk_bands["medium"],
        "standard_risk_unit_count": risk_bands["standard"],
        "avg_claim_risk_score": round(
            sum(float(row["claim_risk_score"]) for row in rows) / max(1, len(rows)),
            2,
        ),
        "reception_sensitive_unit_count": sum(1 for row in rows if row["reception_sensitive"]),
        "jewish_christian_separation_unit_count": sum(
            1
            for row in rows
            if row["has_jewish_reception_frame"] and row["has_christian_reception_frame"]
        ),
        "ancient_culture_pressure_unit_count": sum(
            1 for row in rows if row["ancient_culture_pressure"]
        ),
        "textual_witness_pressure_unit_count": sum(
            1 for row in rows if row["textual_witness_pressure"]
        ),
        "theology_pressure_unit_count": sum(1 for row in rows if row["theology_pressure"]),
        "complete_witness_unit_count": sum(
            1 for row in rows if row["complete_expected_witness_set"]
        ),
        "complete_witness_unit_pct": pct(
            sum(1 for row in rows if row["complete_expected_witness_set"]),
            len(rows),
        ),
        "surface_bridge_unit_count": sum(
            1 for row in rows if row["basis_statuses"]["whole_tanakh"] == "surface bridge only"
        ),
        "outside_strong_supported_unit_count": sum(
            1 for row in rows if float(row["outside_strong_context_pct"]) > 0
        ),
        "outside_strong_supported_unit_pct": pct(
            sum(1 for row in rows if float(row["outside_strong_context_pct"]) > 0),
            len(rows),
        ),
        "translation_text_reception_forbidden_unit_count": sum(
            1
            for row in rows
            if "reception_claims_must_stay_out_of_translation_text" in row["claim_controls"]
        ),
        "risk_band_counts": dict(risk_bands.most_common()),
        "claim_control_counts": dict(control_counts.most_common()),
        "required_frame_counts": dict(frame_counts.most_common()),
        "required_role_counts": dict(role_counts.most_common()),
        "basis_status_counts": dict(basis_counts.most_common()),
        "top_claim_risk_unit": rows[0]["unit_id"] if rows else "",
        "top_claim_risk_score": rows[0]["claim_risk_score"] if rows else 0.0,
    }


def control_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter.update(row["claim_controls"])
    return [
        {"claim_control": control, "unit_count": count} for control, count in counter.most_common()
    ]


def flatten_unit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for row in rows:
        flattened.append(
            {
                "unit_id": row["unit_id"],
                "ref": row["ref"],
                "claim_risk_score": row["claim_risk_score"],
                "claim_risk_band": row["claim_risk_band"],
                "task_count": row["task_count"],
                "layers": "; ".join(row["layers"]),
                "benchmark_tags": "; ".join(row["benchmark_tags"]),
                "domains": "; ".join(row["domains"]),
                "required_frames": "; ".join(row["required_frames"]),
                "required_review_roles": "; ".join(row["required_review_roles"]),
                "basis_hebrew_source": row["basis_statuses"]["hebrew_source"],
                "basis_morphology": row["basis_statuses"]["morphology"],
                "basis_whole_tanakh": row["basis_statuses"]["whole_tanakh"],
                "basis_witness": row["basis_statuses"]["witness"],
                "basis_reception": row["basis_statuses"]["reception"],
                "claim_controls": "; ".join(row["claim_controls"]),
                "reception_sensitive": row["reception_sensitive"],
                "textual_witness_pressure": row["textual_witness_pressure"],
                "ancient_culture_pressure": row["ancient_culture_pressure"],
                "theology_pressure": row["theology_pressure"],
                "complete_expected_witness_set": row["complete_expected_witness_set"],
                "content_token_outside_context_pct": row["content_token_outside_context_pct"],
                "outside_strong_context_pct": row["outside_strong_context_pct"],
            }
        )
    return flattened


def build_report(
    suite_path: Path,
    atlas_path: Path,
    reception_boundary_path: Path,
    canonical_context_path: Path,
    morphology_gap_path: Path,
    witness_path: Path,
    review_plan_path: Path,
) -> dict[str, Any]:
    data = {
        "suite": load_json(suite_path),
        "atlas": load_json(atlas_path),
        "reception": load_json(reception_boundary_path),
        "canonical": load_json(canonical_context_path),
        "morphology": load_json(morphology_gap_path),
        "witness": load_json(witness_path),
        "review_plan": load_json(review_plan_path),
    }
    rows = build_rows(data)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated translation claim evidence matrix",
        "source_paths": {
            "suite": str(suite_path.relative_to(ROOT)),
            "atlas": str(atlas_path.relative_to(ROOT)),
            "reception_boundary": str(reception_boundary_path.relative_to(ROOT)),
            "canonical_context": str(canonical_context_path.relative_to(ROOT)),
            "morphology_gap": str(morphology_gap_path.relative_to(ROOT)),
            "witness": str(witness_path.relative_to(ROOT)),
            "review_plan": str(review_plan_path.relative_to(ROOT)),
        },
        "policy": {
            "translation_text_basis": "Hebrew token evidence and alignment only",
            "surface_context_boundary": (
                "Whole-Tanakh UXLC surface-form matches are context evidence, "
                "not lemma, Strong, morphology, or sense proof."
            ),
            "witness_boundary": (
                "English witnesses and LXX are labeled evidence; English witnesses "
                "are blocked as generation sources."
            ),
            "reception_boundary": (
                "Jewish and Christian reception claims must be separated and kept "
                "outside translation text."
            ),
        },
        "summary": summarize(rows),
        "claim_control_rows": control_rows(rows),
        "unit_claim_rows": rows,
    }


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
    row_h = 30
    left = 330
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
            f'font-size="12" fill="#24313a">{esc(row[label_key])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="18" rx="3" fill="{color}"/>'
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
        body.append("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>")
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    high_rows = report["unit_claim_rows"][:30]
    risk_rows = rows_from_counter(summary["risk_band_counts"], "risk_band")
    control_chart_rows = report["claim_control_rows"][:20]
    frame_rows = rows_from_counter(summary["required_frame_counts"], "frame")
    basis_rows = rows_from_counter(summary["basis_status_counts"], "basis_status")
    matrix_rows = [
        [
            row["unit_id"],
            row["ref"],
            row["claim_risk_band"],
            row["claim_risk_score"],
            "; ".join(row["high_risk_tags"]),
            row["basis_statuses"]["whole_tanakh"],
            row["basis_statuses"]["reception"],
            "; ".join(row["required_review_roles"]),
            "; ".join(row["claim_controls"][:6]),
        ]
        for row in high_rows
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Translation Claim Evidence Matrix</title>
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
    <h1>AlephTav Translation Claim Evidence Matrix</h1>
    <p class="lede">
      Unit-level control ledger for what a local translation model may claim in
      translation text, rationale, witness notes, and reviewer-facing
      commentary. It joins Hebrew token evidence, whole-Tanakh surface context,
      morphology gaps, textual witnesses, ancient-cultural pressure, and
      Jewish/Christian reception boundaries.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Claim-Control Snapshot</h2>
      {
        metric_cards(
            [
                (
                    "Units",
                    fmt_int(summary["unit_count"]),
                    "Contextual expanded benchmark units.",
                ),
                (
                    "High risk",
                    fmt_int(summary["high_risk_unit_count"]),
                    f'''Medium risk: {fmt_int(summary["medium_risk_unit_count"])}.''',
                ),
                (
                    "Reception-sensitive",
                    fmt_int(summary["reception_sensitive_unit_count"]),
                    (
                        f'''{fmt_int(summary["jewish_christian_separation_unit_count"])} '''
                        "need Jewish/Christian separation."
                    ),
                ),
                (
                    "Ancient culture",
                    fmt_int(summary["ancient_culture_pressure_unit_count"]),
                    "Units needing cultural-setting rationale.",
                ),
                (
                    "Textual witness",
                    fmt_int(summary["textual_witness_pressure_unit_count"]),
                    "Units needing witness-boundary controls.",
                ),
                (
                    "Complete witnesses",
                    f'''{summary["complete_witness_unit_pct"]:.2f}%''',
                    "Expected witness set available.",
                ),
                (
                    "Surface bridge",
                    fmt_int(summary["surface_bridge_unit_count"]),
                    "Whole-Tanakh context is surface-form only.",
                ),
                (
                    "Outside Strong",
                    f'''{summary["outside_strong_supported_unit_pct"]:.2f}%''',
                    "Units with true outside-Psalms Strong support.",
                ),
            ]
        )
    }
      <div class="warning">
        The matrix permits whole-Tanakh context only when labeled as surface-form
        evidence unless a future full morphology index supplies non-Psalm
        lemma/Strong support.
      </div>
    </section>
    <section>
      <h2>Risk and Basis</h2>
      <div class="chart">{
        svg_horizontal_bars(
            risk_rows,
            label_key="risk_band",
            value_key="count",
            aria_label="Claim risk bands",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            basis_rows,
            label_key="basis_status",
            value_key="count",
            aria_label="Claim basis status counts",
            color="#7c5b2f",
        )
    }</div>
    </section>
    <section>
      <h2>Required Controls</h2>
      <div class="chart">{
        svg_horizontal_bars(
            control_chart_rows,
            label_key="claim_control",
            value_key="unit_count",
            aria_label="Claim-control counts",
            color="#2f6f73",
        )
    }</div>
    </section>
    <section>
      <h2>Required Frames</h2>
      <div class="chart">{
        svg_horizontal_bars(
            frame_rows,
            label_key="frame",
            value_key="count",
            aria_label="Required interpretive frame counts",
            color="#58508d",
        )
    }</div>
    </section>
    <section>
      <h2>Highest-Risk Unit Matrix</h2>
      {
        table(
            [
                "Unit",
                "Ref",
                "Risk",
                "Score",
                "High-risk tags",
                "Whole-Tanakh basis",
                "Reception basis",
                "Review roles",
                "First controls",
            ],
            matrix_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate unit-level translation claim evidence matrix."
    )
    parser.add_argument("--suite", type=Path, default=SUITE_PATH)
    parser.add_argument("--atlas", type=Path, default=ATLAS_PATH)
    parser.add_argument("--reception-boundary", type=Path, default=RECEPTION_BOUNDARY_PATH)
    parser.add_argument("--canonical-context", type=Path, default=CANONICAL_CONTEXT_PATH)
    parser.add_argument("--morphology-gap", type=Path, default=MORPHOLOGY_GAP_PATH)
    parser.add_argument("--witness", type=Path, default=WITNESS_PATH)
    parser.add_argument("--review-plan", type=Path, default=REVIEW_PLAN_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument(
        "--control-csv-output",
        type=Path,
        default=DEFAULT_CONTROL_CSV_OUTPUT,
    )
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        args.suite,
        args.atlas,
        args.reception_boundary,
        args.canonical_context,
        args.morphology_gap,
        args.witness,
        args.review_plan,
    )
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, flatten_unit_rows(report["unit_claim_rows"]))
    write_csv(args.control_csv_output, report["claim_control_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.control_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
