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
CONTENT_ROOT = ROOT / "content" / "psalms"
REPORT_ROOT = ROOT / "reports" / "research"

ADJUDICATION_PATH = REPORT_ROOT / "interpretive_adjudication_matrix.json"
DOSSIER_PATH = REPORT_ROOT / "priority_unit_dossiers.json"
QUALITY_TRIAGE_PATH = REPORT_ROOT / "model_output_quality_triage.json"
LAYER_CONSISTENCY_PATH = REPORT_ROOT / "layer_consistency_report.json"
CANONICAL_CONTEXT_PATH = REPORT_ROOT / "canonical_context_network.json"
CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "scholarly_casebook.json"
DEFAULT_CASE_CSV_OUTPUT = REPORT_ROOT / "scholarly_casebook_cases.csv"
DEFAULT_DOMAIN_CSV_OUTPUT = REPORT_ROOT / "scholarly_casebook_domains.csv"
DEFAULT_LANE_CSV_OUTPUT = REPORT_ROOT / "scholarly_casebook_lanes.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "scholarly_casebook.html"

DEFAULT_LIMIT = 12
LANES = [
    "hebrew_source",
    "morphology_lexeme",
    "whole_tanakh_context",
    "textual_witness",
    "ancient_culture",
    "jewish_reception",
    "christian_reception",
    "academic_comparison",
    "local_model_output",
    "layer_separation",
    "human_signoff",
]

LANE_LABELS = {
    "hebrew_source": "Hebrew",
    "morphology_lexeme": "Morph/Lex",
    "whole_tanakh_context": "Tanakh",
    "textual_witness": "Witness",
    "ancient_culture": "Culture",
    "jewish_reception": "Jewish",
    "christian_reception": "Christian",
    "academic_comparison": "Academic",
    "local_model_output": "Model",
    "layer_separation": "Layer",
    "human_signoff": "Signoff",
}


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
    return round(float(part) / float(total) * 100, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def rows_by_unit(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in rows if row.get("unit_id")}


def unit_path(unit_id: str) -> Path:
    psalm_id = unit_id.split(".")[0]
    return CONTENT_ROOT / psalm_id / f"{unit_id}.json"


def load_unit(unit_id: str) -> dict[str, Any]:
    path = unit_path(unit_id)
    return load_json(path) if path.exists() else {}


def compact_token(token: dict[str, Any]) -> dict[str, Any]:
    features = token.get("compiler_features") or {}
    return {
        "token_id": token.get("token_id"),
        "surface": token.get("surface"),
        "lemma": token.get("lemma"),
        "strong": token.get("strong"),
        "morph_code": token.get("morph_code"),
        "part_of_speech": token.get("part_of_speech"),
        "display_gloss": token.get("display_gloss"),
        "semantic_role": token.get("semantic_role"),
        "referent": token.get("referent"),
        "divine_name": bool(features.get("divine_name")),
        "construct_state": bool(features.get("construct_state")),
        "suffix_pronoun": features.get("suffix_pronoun"),
        "missing_enrichments": token.get("missing_enrichments") or [],
    }


def source_summary(tokens: list[dict[str, Any]]) -> dict[str, Any]:
    missing = Counter()
    strong_count = 0
    lemma_count = 0
    divine_name_count = 0
    for token in tokens:
        if token.get("strong"):
            strong_count += 1
        if token.get("lemma"):
            lemma_count += 1
        missing.update(str(item) for item in token.get("missing_enrichments") or [])
        if (token.get("compiler_features") or {}).get("divine_name"):
            divine_name_count += 1
    token_count = len(tokens)
    return {
        "token_count": token_count,
        "lemma_coverage_pct": pct(lemma_count, token_count),
        "strong_coverage_pct": pct(strong_count, token_count),
        "divine_name_token_count": divine_name_count,
        "missing_enrichment_counts": dict(missing.most_common()),
    }


def witness_summary(witnesses: list[dict[str, Any]]) -> dict[str, Any]:
    sources = Counter(str(row.get("source_id") or "unknown") for row in witnesses)
    languages = Counter(str(row.get("language") or "unknown") for row in witnesses)
    return {
        "witness_count": len(witnesses),
        "source_counts": dict(sources.most_common()),
        "language_counts": dict(languages.most_common()),
        "has_lxx": bool(sources.get("lxx")),
        "english_witness_count": int(languages.get("en", 0)),
        "witness_excerpts": [
            {
                "source_id": row.get("source_id"),
                "language": row.get("language"),
                "role": row.get("witness_role"),
                "text_excerpt": str(row.get("text") or "")[:180],
            }
            for row in witnesses
        ],
    }


def quality_by_unit(quality: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in quality.get("candidate_rows", []):
        grouped.setdefault(str(row["unit_id"]), []).append(row)
    return grouped


def model_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    model_counts = Counter(str(row.get("model_profile_id") or "unknown") for row in rows)
    status_counts = Counter(str(row.get("quality_status") or "unknown") for row in rows)
    valid_rows = [row for row in rows if row.get("schema_valid")]
    return {
        "candidate_row_count": len(rows),
        "schema_valid_candidate_count": len(valid_rows),
        "model_counts": dict(model_counts.most_common()),
        "quality_status_counts": dict(status_counts.most_common()),
        "max_review_priority_score": max(
            (float(row.get("review_priority_score") or 0.0) for row in rows),
            default=0.0,
        ),
        "outputs": [
            {
                "task_id": row.get("task_id"),
                "layer": row.get("layer"),
                "model_profile_id": row.get("model_profile_id"),
                "schema_valid": bool(row.get("schema_valid")),
                "quality_status": row.get("quality_status"),
                "review_priority_score": row.get("review_priority_score"),
                "candidate_text_excerpt": str(row.get("candidate_text") or "")[:220],
                "flags": row.get("flags", []),
            }
            for row in rows[:8]
        ],
    }


def case_rows(
    *,
    adjudication: dict[str, Any],
    dossiers: dict[str, Any],
    quality: dict[str, Any],
    layers: dict[str, Any],
    canonical: dict[str, Any],
    claim_matrix: dict[str, Any],
    limit: int,
) -> list[dict[str, Any]]:
    dossier_by_unit = rows_by_unit(dossiers.get("dossiers", []))
    quality_rows = quality_by_unit(quality)
    layer_by_unit = rows_by_unit(layers.get("pair_rows", []))
    canonical_by_unit = rows_by_unit(canonical.get("unit_network_rows", []))
    claim_by_unit = rows_by_unit(claim_matrix.get("unit_claim_rows", []))
    cases = []
    for rank, row in enumerate(adjudication.get("unit_rows", [])[:limit], start=1):
        unit_id = str(row["unit_id"])
        unit = load_unit(unit_id)
        tokens = unit.get("tokens", [])
        witnesses = unit.get("witnesses", [])
        dossier = dossier_by_unit.get(unit_id, {})
        canonical_row = canonical_by_unit.get(unit_id, {})
        claim_row = claim_by_unit.get(unit_id, {})
        layer = layer_by_unit.get(unit_id, {})
        model = model_summary(quality_rows.get(unit_id, []))
        lane_statuses = row.get("lane_statuses", {})
        reception_status = (
            "separation_required_no_signed_viewpoint_decision"
            if row.get("jewish_christian_separation_required")
            else "not_required_for_this_unit"
        )
        cases.append(
            {
                "rank": rank,
                "unit_id": unit_id,
                "ref": row.get("ref") or unit.get("ref", ""),
                "source_hebrew": unit.get("source_hebrew") or dossier.get("source_hebrew", ""),
                "source_summary": source_summary(tokens),
                "tokens": [compact_token(token) for token in tokens],
                "witness_summary": witness_summary(witnesses),
                "adjudication": {
                    "priority_score": row["adjudication_priority_score"],
                    "priority_band": row["adjudication_priority_band"],
                    "lane_statuses": lane_statuses,
                    "blocked_lane_count": row["blocked_lane_count"],
                    "review_lane_count": row["review_lane_count"],
                    "basis_statuses": row.get("basis_statuses", {}),
                    "claim_controls": row.get("claim_controls", []),
                },
                "context": {
                    "domains": row.get("domains", []),
                    "domain_groups": row.get("domain_groups", []),
                    "benchmark_tags": row.get("benchmark_tags", []),
                    "required_frames": row.get("required_frames", []),
                    "required_review_roles": row.get("required_review_roles", []),
                    "reviewer_questions": dossier.get("reviewer_questions", [])[:18],
                    "decision_gates": dossier.get("decision_gates", []),
                    "content_token_outside_context_pct": row["content_token_outside_context_pct"],
                    "surface_outside_context_pct": row["surface_outside_context_pct"],
                    "outside_strong_context_pct": row["outside_strong_context_pct"],
                    "outside_division_counts": canonical_row.get("outside_division_counts", {}),
                    "top_anchor_tokens": canonical_row.get("top_anchor_tokens", []),
                },
                "reception_viewpoints": {
                    "status": reception_status,
                    "jewish_lane": lane_statuses.get("jewish_reception"),
                    "christian_lane": lane_statuses.get("christian_reception"),
                    "academic_comparison_lane": lane_statuses.get("academic_comparison"),
                    "substantive_source_note": (
                        "The repository currently routes Jewish and Christian "
                        "reception separately, but no completed reviewer decision "
                        "or signed reception-source synthesis is present."
                    ),
                },
                "model_evidence": model,
                "layer_evidence": {
                    "pair_present": bool(layer),
                    "layer_risk_score": layer.get("layer_risk_score", 0.0),
                    "word_jaccard_pct": layer.get("word_jaccard_pct", 0.0),
                    "exact_duplicate": bool(layer.get("exact_duplicate")),
                    "flags": layer.get("flags", []),
                    "gloss_text": layer.get("gloss_text", ""),
                    "literal_text": layer.get("literal_text", ""),
                },
                "claim_evidence": {
                    "claim_risk_score": claim_row.get("claim_risk_score", 0.0),
                    "claim_risk_band": claim_row.get("claim_risk_band", ""),
                    "allowed_claim_lanes": claim_row.get("allowed_claim_lanes", {}),
                },
            }
        )
    return cases


def summarize(cases: list[dict[str, Any]]) -> dict[str, Any]:
    domain_counts = Counter()
    lane_counts = Counter()
    blocked_counts = Counter()
    missing_counts = Counter()
    for case in cases:
        domain_counts.update(case["context"]["domains"])
        for lane, status in case["adjudication"]["lane_statuses"].items():
            lane_counts.update([f"{lane}:{status}"])
            if status in {"layer_blocked", "human_signoff_missing", "missing_model_output"}:
                blocked_counts.update([lane])
        missing_counts.update(case["source_summary"]["missing_enrichment_counts"])
    return {
        "case_count": len(cases),
        "top_case_unit": cases[0]["unit_id"] if cases else "",
        "top_case_ref": cases[0]["ref"] if cases else "",
        "total_token_count": sum(int(case["source_summary"]["token_count"]) for case in cases),
        "mean_adjudication_priority_score": mean(
            [float(case["adjudication"]["priority_score"]) for case in cases]
        ),
        "reception_case_count": sum(
            1
            for case in cases
            if case["reception_viewpoints"]["status"]
            == "separation_required_no_signed_viewpoint_decision"
        ),
        "textual_witness_case_count": sum(
            1 for case in cases if "textual_witness_pressure" in case["context"]["domains"]
        ),
        "layer_blocker_case_count": sum(1 for case in cases if case["layer_evidence"]["flags"]),
        "cases_with_schema_valid_model_output": sum(
            1 for case in cases if int(case["model_evidence"]["schema_valid_candidate_count"]) > 0
        ),
        "domain_counts": dict(domain_counts.most_common()),
        "blocked_lane_counts": dict(blocked_counts.most_common()),
        "lane_status_counts": dict(lane_counts.most_common()),
        "missing_enrichment_counts": dict(missing_counts.most_common()),
        "status": "casebook_generated_not_reviewer_signoff",
    }


def build_report(limit: int) -> dict[str, Any]:
    data = {
        "adjudication": load_json(ADJUDICATION_PATH),
        "dossiers": load_json(DOSSIER_PATH),
        "quality": load_json(QUALITY_TRIAGE_PATH),
        "layers": load_json(LAYER_CONSISTENCY_PATH),
        "canonical": load_json(CANONICAL_CONTEXT_PATH),
        "claim_matrix": load_json(CLAIM_MATRIX_PATH),
    }
    cases = case_rows(
        adjudication=data["adjudication"],
        dossiers=data["dossiers"],
        quality=data["quality"],
        layers=data["layers"],
        canonical=data["canonical"],
        claim_matrix=data["claim_matrix"],
        limit=limit,
    )
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "scholarly casebook generated; not reviewer signoff",
        "source_paths": {
            "adjudication": str(ADJUDICATION_PATH.relative_to(ROOT)),
            "dossiers": str(DOSSIER_PATH.relative_to(ROOT)),
            "quality_triage": str(QUALITY_TRIAGE_PATH.relative_to(ROOT)),
            "layer_consistency": str(LAYER_CONSISTENCY_PATH.relative_to(ROOT)),
            "canonical_context": str(CANONICAL_CONTEXT_PATH.relative_to(ROOT)),
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
        },
        "policy": {
            "translation_basis": "Hebrew source tokens and alignment remain primary.",
            "witnesses": "Witnesses are displayed as evidence, not generation basis.",
            "reception": (
                "Jewish and Christian lanes are separated; unsigned reception "
                "synthesis cannot affect translation wording."
            ),
            "model_outputs": "Local model rows are proposal evidence only.",
        },
        "summary": summarize(cases),
        "cases": cases,
    }


def flatten_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        rows.append(
            {
                "rank": case["rank"],
                "unit_id": case["unit_id"],
                "ref": case["ref"],
                "priority_score": case["adjudication"]["priority_score"],
                "priority_band": case["adjudication"]["priority_band"],
                "token_count": case["source_summary"]["token_count"],
                "domains": case["context"]["domains"],
                "required_frames": case["context"]["required_frames"],
                "required_review_roles": case["context"]["required_review_roles"],
                "reception_viewpoint_status": case["reception_viewpoints"]["status"],
                "witness_count": case["witness_summary"]["witness_count"],
                "schema_valid_model_outputs": case["model_evidence"][
                    "schema_valid_candidate_count"
                ],
                "model_candidate_rows": case["model_evidence"]["candidate_row_count"],
                "layer_flags": case["layer_evidence"]["flags"],
                "blocked_lanes": [
                    lane
                    for lane, status in case["adjudication"]["lane_statuses"].items()
                    if status in {"layer_blocked", "human_signoff_missing", "missing_model_output"}
                ],
            }
        )
    return rows


def counter_rows(counter: dict[str, int], key: str) -> list[dict[str, Any]]:
    return [
        {key: item, "count": count}
        for item, count in sorted(counter.items(), key=lambda pair: pair[1], reverse=True)
    ]


def svg_bar_chart(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    width: int = 1100,
    limit: int = 16,
) -> str:
    rows = rows[:limit]
    row_h = 30
    left = 270
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


def lane_heatmap(cases: list[dict[str, Any]]) -> str:
    colors = {
        "review_planned": "#58508d",
        "review_required": "#58508d",
        "partial_psalm_only": "#7c5b2f",
        "surface_only": "#7c5b2f",
        "evidence_ready": "#2f6f73",
        "layer_blocked": "#9b3d3d",
        "missing_model_output": "#9b3d3d",
        "human_signoff_missing": "#9b3d3d",
        "not_required": "#d8e0e6",
    }
    header = (
        "<tr><th>Case</th>"
        + "".join(f"<th>{esc(LANE_LABELS[lane])}</th>" for lane in LANES)
        + "</tr>"
    )
    rows = []
    for case in cases:
        cells = [
            f"<td><strong>{esc(case['ref'])}</strong><br><span>{esc(case['unit_id'])}</span></td>"
        ]
        for lane in LANES:
            status = str(case["adjudication"]["lane_statuses"].get(lane, "not_required"))
            color = colors.get(status, "#d8e0e6")
            cells.append(
                f'<td style="background:{color}; color:#fff; font-size:11px;">{esc(status)}</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<table class="heatmap"><thead>'
        + header
        + "</thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


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
        + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
        + "</tbody></table>"
    )


def render_case(case: dict[str, Any]) -> str:
    controls_text = "; ".join(case["adjudication"]["claim_controls"][:8])
    token_rows = [
        [
            esc(token["surface"]),
            esc(token["lemma"]),
            esc(token["strong"]),
            esc(token["display_gloss"]),
            esc(token["part_of_speech"]),
            esc(", ".join(token["missing_enrichments"][:3])),
        ]
        for token in case["tokens"][:18]
    ]
    witness_rows = [
        [
            esc(row["source_id"]),
            esc(row["language"]),
            esc(row["role"]),
            esc(row["text_excerpt"]),
        ]
        for row in case["witness_summary"]["witness_excerpts"]
    ]
    model_rows = [
        [
            esc(row["model_profile_id"]),
            esc(row["layer"]),
            esc(row["schema_valid"]),
            esc(row["quality_status"]),
            esc(row["candidate_text_excerpt"]),
        ]
        for row in case["model_evidence"]["outputs"]
    ]
    return f"""
    <article class="case">
      <h3>{esc(case["rank"])}. {esc(case["ref"])} <span>{esc(case["unit_id"])}</span></h3>
      <p class="hebrew" dir="rtl">{esc(case["source_hebrew"])}</p>
      <div class="case-grid">
        <div>
          <h4>Adjudication</h4>
          <p><strong>Score:</strong> {case["adjudication"]["priority_score"]:.2f}
          ({esc(case["adjudication"]["priority_band"])}).</p>
          <p><strong>Basis:</strong> {esc(case["adjudication"]["basis_statuses"])}</p>
          <p><strong>Controls:</strong> {esc(controls_text)}</p>
        </div>
        <div>
          <h4>Context</h4>
          <p><strong>Domains:</strong> {esc("; ".join(case["context"]["domains"]))}</p>
          <p><strong>Frames:</strong> {esc("; ".join(case["context"]["required_frames"]))}</p>
          <p><strong>Roles:</strong> {esc("; ".join(case["context"]["required_review_roles"]))}</p>
        </div>
        <div>
          <h4>Reception Boundary</h4>
          <p>{esc(case["reception_viewpoints"]["substantive_source_note"])}</p>
          <p><strong>Status:</strong> {esc(case["reception_viewpoints"]["status"])}</p>
        </div>
        <div>
          <h4>Model and Layer Evidence</h4>
          <p><strong>Model rows:</strong> {case["model_evidence"]["schema_valid_candidate_count"]}/
          {case["model_evidence"]["candidate_row_count"]} schema-valid.</p>
          <p><strong>Layer flags:</strong> {esc("; ".join(case["layer_evidence"]["flags"]))}</p>
        </div>
      </div>
      <h4>Token Evidence</h4>
      {table(["Surface", "Lemma", "Strong", "Gloss", "POS", "Missing"], token_rows)}
      <h4>Witness Excerpts</h4>
      {table(["Source", "Lang", "Role", "Excerpt"], witness_rows)}
      <h4>Model Output Excerpts</h4>
      {table(["Model", "Layer", "Schema", "Status", "Excerpt"], model_rows)}
    </article>
    """


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    cases = report["cases"]
    domain_rows = counter_rows(summary["domain_counts"], "domain")
    blocked_rows = counter_rows(summary["blocked_lane_counts"], "lane")
    case_index = table(
        ["Rank", "Unit", "Score", "Domains", "Model", "Layer Flags"],
        [
            [
                f'<span class="num">{case["rank"]}</span>',
                f"<strong>{esc(case['ref'])}</strong><br><span>{esc(case['unit_id'])}</span>",
                f'<span class="num">{float(case["adjudication"]["priority_score"]):.2f}</span>',
                esc("; ".join(case["context"]["domains"][:6])),
                (
                    f"{case['model_evidence']['schema_valid_candidate_count']}/"
                    f"{case['model_evidence']['candidate_row_count']} valid"
                ),
                esc("; ".join(case["layer_evidence"]["flags"][:5])),
            ]
            for case in cases
        ],
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Scholarly Casebook</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2a33;
      --muted: #64727d;
      --line: #d8e0e6;
      --band: #f4f7f8;
      --accent: #2f6f73;
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
    main {{ max-width: 1240px; margin: 0 auto; padding: 30px 34px 54px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    h3 {{ margin: 0 0 10px; font-size: 20px; }}
    h3 span, td span {{ color: var(--muted); font-size: 12px; font-weight: 400; }}
    h4 {{ margin: 18px 0 8px; font-size: 15px; }}
    p {{ margin: 0 0 13px; }}
    .lede {{ max-width: 980px; font-size: 17px; color: #33414c; }}
    .meta {{ color: var(--muted); font-size: 13px; margin-top: 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 22px 0; }}
    .card {{ border: 1px solid var(--line); border-radius: 6px; padding: 16px; background: #fff; }}
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
    .case {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 18px;
      margin: 20px 0;
    }}
    .case-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
    .hebrew {{ font-size: 24px; line-height: 1.8; margin: 10px 0 18px; }}
    svg {{ width: 100%; height: auto; display: block; }}
    table {{ border-collapse: collapse; width: 100%; margin: 14px 0 24px; font-size: 13px; }}
    th, td {{ border: 1px solid var(--line); padding: 9px 10px; vertical-align: top; }}
    th {{ background: var(--band); text-align: left; }}
    .heatmap th, .heatmap td {{ text-align: center; min-width: 82px; }}
    .heatmap td:first-child, .heatmap th:first-child {{ text-align: left; min-width: 150px; }}
    .num {{ text-align: right; white-space: nowrap; }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid, .case-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AlephTav Scholarly Casebook</h1>
    <p class="lede">
      High-risk case studies combining Hebrew token evidence, witness boundaries,
      whole-Tanakh context limits, Jewish/Christian reception routing, model output,
      layer-separation evidence, and reviewer questions.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}. Not reviewer signoff.</p>
  </header>
  <main>
    <section>
      <h2>Casebook Summary</h2>
      {
        metric_cards(
            [
                ("Cases", fmt_int(summary["case_count"]), "Top adjudication units included."),
                (
                    "Reception Cases",
                    fmt_int(summary["reception_case_count"]),
                    "Jewish/Christian lanes required but unsigned.",
                ),
                (
                    "Layer Blockers",
                    fmt_int(summary["layer_blocker_case_count"]),
                    "Cases with model layer warning flags.",
                ),
                (
                    "Tokens",
                    fmt_int(summary["total_token_count"]),
                    "Hebrew source token records inspected.",
                ),
            ]
        )
    }
      <div class="warning">
        <strong>Boundary:</strong> this casebook is evidence routing. It does not
        settle Jewish or Christian interpretation, and it does not approve any
        model rendering as authoritative.
      </div>
    </section>

    <section>
      <h2>Case Index</h2>
      {case_index}
    </section>

    <section>
      <h2>Lane Heatmap</h2>
      <div class="chart">{lane_heatmap(cases)}</div>
    </section>

    <section>
      <h2>Domain and Blocker Counts</h2>
      <div class="chart">{
        svg_bar_chart(
            domain_rows,
            label_key="domain",
            value_key="count",
            aria_label="Casebook domain counts",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_bar_chart(
            blocked_rows,
            label_key="lane",
            value_key="count",
            aria_label="Blocked lane counts",
            color="#9b3d3d",
        )
    }</div>
    </section>

    <section>
      <h2>Cases</h2>
      {"".join(render_case(case) for case in cases)}
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate scholarly casebook report.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--case-csv-output", type=Path, default=DEFAULT_CASE_CSV_OUTPUT)
    parser.add_argument("--domain-csv-output", type=Path, default=DEFAULT_DOMAIN_CSV_OUTPUT)
    parser.add_argument("--lane-csv-output", type=Path, default=DEFAULT_LANE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    args = parse_args()
    report = build_report(limit=args.limit)
    json_output = resolve(args.json_output)
    case_csv_output = resolve(args.case_csv_output)
    domain_csv_output = resolve(args.domain_csv_output)
    lane_csv_output = resolve(args.lane_csv_output)
    html_output = resolve(args.html_output)
    write_json(json_output, report)
    write_csv(case_csv_output, flatten_cases(report["cases"]))
    write_csv(domain_csv_output, counter_rows(report["summary"]["domain_counts"], "domain"))
    write_csv(lane_csv_output, counter_rows(report["summary"]["blocked_lane_counts"], "lane"))
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(render_html(report), encoding="utf-8")
    print(json_output)
    print(case_csv_output)
    print(domain_csv_output)
    print(lane_csv_output)
    print(html_output)


if __name__ == "__main__":
    main()
