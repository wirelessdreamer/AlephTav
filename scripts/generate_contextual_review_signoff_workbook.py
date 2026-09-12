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

PACKET_ROADMAP_PATH = REPORT_ROOT / "contextual_source_packet_roadmap.json"
SOURCE_ACQUISITION_PATH = REPORT_ROOT / "contextual_source_acquisition_plan.json"
MODEL_REVIEW_PLAN_PATH = REPORT_ROOT / "contextual_expanded_benchmark_review_signoff_plan.json"
ADJUDICATION_PATH = REPORT_ROOT / "interpretive_adjudication_matrix.json"
AUTHORITY_PATH = REPORT_ROOT / "scholarly_authority_readiness.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "contextual_review_signoff_workbook.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "contextual_review_signoff_units.csv"
DEFAULT_PACKET_CSV_OUTPUT = REPORT_ROOT / "contextual_review_signoff_packet_rows.csv"
DEFAULT_SOURCE_CSV_OUTPUT = REPORT_ROOT / "contextual_review_signoff_source_rows.csv"
DEFAULT_ROLE_CSV_OUTPUT = REPORT_ROOT / "contextual_review_signoff_roles.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "contextual_review_signoff_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "contextual_review_signoff_workbook.html"

LICENSE_REVIEW_ROLES = ["license", "provenance", "release"]
SOURCE_FAMILY_EXTRA_ROLES = {
    "jewish_reception_sources": ["theology"],
    "christian_reception_sources": ["theology"],
    "academic_critical_comparison": ["Hebrew", "theology"],
    "ancient_near_eastern_context": ["Hebrew", "theology"],
    "whole_tanakh_lemma_context": ["Hebrew", "lexical"],
    "morphology_lexeme": ["Hebrew", "lexical"],
    "textual_witness_variants": ["Hebrew", "alignment", "theology"],
    "divine_name_title_policy": ["Hebrew", "theology", "release"],
    "human_release_signoff": ["release"],
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


def family_map(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["source_family"]): row
        for row in packet.get("source_family_rows", [])
        if row.get("source_family")
    }


def unit_map(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in packet.get("unit_rows", []) if row.get("unit_id")}


def acquisition_roles(candidate: dict[str, Any]) -> list[str]:
    roles = set(LICENSE_REVIEW_ROLES)
    for family in candidate.get("source_families", []):
        roles.update(SOURCE_FAMILY_EXTRA_ROLES.get(str(family), []))
    if str(candidate.get("license_risk", "")).startswith("high"):
        roles.add("legal")
    if "per_text" in str(candidate.get("license_risk", "")):
        roles.add("legal")
    return sorted(roles)


def build_packet_review_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    families = family_map(packet)
    rows = []
    for unit in packet.get("unit_rows", []):
        unit_id = str(unit["unit_id"])
        for family_id in unit.get("packet_families", []):
            family = families.get(str(family_id), {})
            for role in sorted(set(family.get("review_roles", []))):
                rows.append(
                    {
                        "review_row_id": f"srcpkt.{unit_id}.{family_id}.{role}",
                        "review_type": "source_packet",
                        "status": "pending",
                        "unit_id": unit_id,
                        "ref": unit.get("ref", ""),
                        "packet_family": family_id,
                        "packet_family_label": family.get("label", family_id),
                        "reviewer_role": role,
                        "packet_priority_score": unit.get("packet_priority_score", 0.0),
                        "packet_priority_band": unit.get("packet_priority_band", ""),
                        "required_artifacts": family.get("required_artifacts", []),
                        "source_classes": family.get("source_classes", []),
                        "authority_boundary": family.get("authority_boundary", ""),
                        "jewish_christian_separation_required": bool(
                            unit.get("jewish_christian_separation_required")
                        ),
                        "textual_witness_pressure": bool(unit.get("textual_witness_pressure")),
                        "ancient_culture_pressure": bool(unit.get("ancient_culture_pressure")),
                        "reviewer_id": "",
                        "decision": "",
                        "score_0_5": "",
                        "confidence_0_1": "",
                        "evidence_notes": "",
                        "required_corrections": "",
                        "gate_failures": "",
                        "created_at": "",
                    }
                )
    return rows


def build_source_review_rows(acquisition: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for candidate in acquisition.get("candidate_rows", []):
        candidate_id = str(candidate["candidate_id"])
        for role in acquisition_roles(candidate):
            rows.append(
                {
                    "review_row_id": f"srcacq.{candidate_id}.{role}",
                    "review_type": "source_acquisition",
                    "status": "pending",
                    "candidate_id": candidate_id,
                    "candidate_label": candidate.get("label", ""),
                    "reviewer_role": role,
                    "priority_score": candidate.get("priority_score", 0.0),
                    "priority_band": candidate.get("priority_band", ""),
                    "packet_unit_count": candidate.get("packet_unit_count", 0),
                    "source_families": candidate.get("source_families", []),
                    "license_risk": candidate.get("license_risk", ""),
                    "license_or_access": candidate.get("license_or_access", ""),
                    "official_url": candidate.get("official_url", ""),
                    "acquisition_status": candidate.get("acquisition_status", ""),
                    "reviewer_id": "",
                    "decision": "",
                    "score_0_5": "",
                    "confidence_0_1": "",
                    "evidence_notes": "",
                    "required_corrections": "",
                    "gate_failures": "",
                    "created_at": "",
                }
            )
    return rows


def build_unit_rows(
    packet: dict[str, Any],
    packet_reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    review_counts: Counter[str] = Counter()
    role_counts: dict[str, Counter[str]] = {}
    family_counts: dict[str, Counter[str]] = {}
    for row in packet_reviews:
        unit_id = str(row["unit_id"])
        review_counts.update([unit_id])
        role_counts.setdefault(unit_id, Counter()).update([str(row["reviewer_role"])])
        family_counts.setdefault(unit_id, Counter()).update([str(row["packet_family"])])

    rows = []
    for unit in packet.get("unit_rows", []):
        unit_id = str(unit["unit_id"])
        rows.append(
            {
                "unit_id": unit_id,
                "ref": unit.get("ref", ""),
                "packet_priority_score": unit.get("packet_priority_score", 0.0),
                "packet_priority_band": unit.get("packet_priority_band", ""),
                "packet_family_count": unit.get("packet_family_count", 0),
                "packet_review_row_count": review_counts.get(unit_id, 0),
                "distinct_reviewer_roles": sorted(role_counts.get(unit_id, Counter()).keys()),
                "packet_families": sorted(family_counts.get(unit_id, Counter()).keys()),
                "reception_sensitive": bool(unit.get("reception_sensitive")),
                "jewish_christian_separation_required": bool(
                    unit.get("jewish_christian_separation_required")
                ),
                "textual_witness_pressure": bool(unit.get("textual_witness_pressure")),
                "ancient_culture_pressure": bool(unit.get("ancient_culture_pressure")),
                "status": "pending_source_packet_review",
            }
        )
    return sorted(rows, key=lambda row: float(row["packet_priority_score"]), reverse=True)


def build_role_rows(
    packet_reviews: list[dict[str, Any]],
    source_reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    role_rows: dict[str, dict[str, Any]] = {}
    for row in packet_reviews:
        role = str(row["reviewer_role"])
        target = role_rows.setdefault(
            role,
            {
                "reviewer_role": role,
                "packet_review_row_count": 0,
                "source_acquisition_review_row_count": 0,
                "critical_packet_review_row_count": 0,
                "highest_packet_review_row_count": 0,
                "units": set(),
                "packet_families": set(),
            },
        )
        target["packet_review_row_count"] += 1
        target["units"].add(str(row["unit_id"]))
        target["packet_families"].add(str(row["packet_family"]))
        if row.get("packet_priority_band") == "critical":
            target["critical_packet_review_row_count"] += 1
        if row.get("packet_priority_band") == "highest":
            target["highest_packet_review_row_count"] += 1
    for row in source_reviews:
        role = str(row["reviewer_role"])
        target = role_rows.setdefault(
            role,
            {
                "reviewer_role": role,
                "packet_review_row_count": 0,
                "source_acquisition_review_row_count": 0,
                "critical_packet_review_row_count": 0,
                "highest_packet_review_row_count": 0,
                "units": set(),
                "packet_families": set(),
            },
        )
        target["source_acquisition_review_row_count"] += 1

    rows = []
    for role, row in role_rows.items():
        rows.append(
            {
                "reviewer_role": role,
                "total_review_row_count": int(row["packet_review_row_count"])
                + int(row["source_acquisition_review_row_count"]),
                "packet_review_row_count": row["packet_review_row_count"],
                "source_acquisition_review_row_count": row["source_acquisition_review_row_count"],
                "critical_packet_review_row_count": row["critical_packet_review_row_count"],
                "highest_packet_review_row_count": row["highest_packet_review_row_count"],
                "unit_count": len(row["units"]),
                "packet_family_count": len(row["packet_families"]),
                "status": "pending_assignment",
            }
        )
    return sorted(rows, key=lambda item: int(item["total_review_row_count"]), reverse=True)


def build_gate_rows(
    packet_reviews: list[dict[str, Any]],
    source_reviews: list[dict[str, Any]],
    model_review: dict[str, Any],
    authority: dict[str, Any],
) -> list[dict[str, Any]]:
    model_summary = model_review.get("summary", {})
    authority_summary = authority.get("summary", {})
    return [
        {
            "gate": "workbook_generated",
            "score_pct": 100.0,
            "status": "pass",
            "evidence": (
                f"{len(packet_reviews)} packet review rows and {len(source_reviews)} "
                "source-acquisition rows generated."
            ),
            "next_action": "Assign reviewer IDs and collect decisions.",
        },
        {
            "gate": "source_packet_reviews_completed",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": f"{len(packet_reviews)} source-packet review rows are pending.",
            "next_action": "Complete role-specific review rows before authority claims.",
        },
        {
            "gate": "source_acquisition_reviews_completed",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": f"{len(source_reviews)} source-acquisition review rows are pending.",
            "next_action": "Complete license/provenance/source acquisition decisions.",
        },
        {
            "gate": "model_output_reviews_completed",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": (
                f"{model_summary.get('projected_human_review_rows', 0)} model-output "
                "human review rows are projected by the expanded review plan."
            ),
            "next_action": "Run candidate bakeoff and fill model review templates.",
        },
        {
            "gate": "human_signoff_authority_gate",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": (
                "Authority hard blockers remain: "
                + ", ".join(authority_summary.get("hard_blockers", []))
                + "."
            ),
            "next_action": "Do not mark any generated output as authoritative.",
        },
        {
            "gate": "release_authority_gate",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": "Release signoff and audit records are absent.",
            "next_action": (
                "Execute release reviewer workflow only after source/model reviews pass."
            ),
        },
    ]


def summarize(
    unit_rows: list[dict[str, Any]],
    packet_reviews: list[dict[str, Any]],
    source_reviews: list[dict[str, Any]],
    role_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    model_review: dict[str, Any],
) -> dict[str, Any]:
    model_summary = model_review.get("summary", {})
    return {
        "unit_count": len(unit_rows),
        "packet_review_row_count": len(packet_reviews),
        "source_acquisition_review_row_count": len(source_reviews),
        "total_review_row_count": len(packet_reviews) + len(source_reviews),
        "completed_review_row_count": 0,
        "review_completion_pct": 0.0,
        "reviewer_role_count": len(role_rows),
        "critical_unit_count": sum(
            1 for row in unit_rows if row["packet_priority_band"] == "critical"
        ),
        "highest_unit_count": sum(
            1 for row in unit_rows if row["packet_priority_band"] == "highest"
        ),
        "jewish_christian_unit_count": sum(
            1 for row in unit_rows if row["jewish_christian_separation_required"]
        ),
        "textual_witness_unit_count": sum(
            1 for row in unit_rows if row["textual_witness_pressure"]
        ),
        "ancient_culture_unit_count": sum(
            1 for row in unit_rows if row["ancient_culture_pressure"]
        ),
        "model_projected_human_review_rows": model_summary.get("projected_human_review_rows", 0),
        "model_projected_cross_exam_rows": model_summary.get("projected_model_cross_exam_rows", 0),
        "gate_count": len(gate_rows),
        "blocked_gate_count": sum(1 for row in gate_rows if row["status"] == "blocked"),
        "top_unit": unit_rows[0]["unit_id"] if unit_rows else "",
        "top_ref": unit_rows[0]["ref"] if unit_rows else "",
        "top_packet_priority_score": unit_rows[0]["packet_priority_score"] if unit_rows else 0.0,
        "status": "review_signoff_workbook_generated_not_reviewed",
    }


def build_report() -> dict[str, Any]:
    packet = load_json(PACKET_ROADMAP_PATH)
    acquisition = load_json(SOURCE_ACQUISITION_PATH)
    model_review = load_json(MODEL_REVIEW_PLAN_PATH)
    adjudication = load_json(ADJUDICATION_PATH)
    authority = load_json(AUTHORITY_PATH)
    packet_reviews = build_packet_review_rows(packet)
    source_reviews = build_source_review_rows(acquisition)
    units = build_unit_rows(packet, packet_reviews)
    roles = build_role_rows(packet_reviews, source_reviews)
    gates = build_gate_rows(packet_reviews, source_reviews, model_review, authority)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "contextual review signoff workbook generated; no reviews completed",
        "source_paths": {
            "packet_roadmap": str(PACKET_ROADMAP_PATH.relative_to(ROOT)),
            "source_acquisition": str(SOURCE_ACQUISITION_PATH.relative_to(ROOT)),
            "model_review_plan": str(MODEL_REVIEW_PLAN_PATH.relative_to(ROOT)),
            "adjudication": str(ADJUDICATION_PATH.relative_to(ROOT)),
            "authority": str(AUTHORITY_PATH.relative_to(ROOT)),
        },
        "policy": {
            "review_boundary": (
                "Rows are templates until reviewer_id, decision, score, and notes exist."
            ),
            "authority_boundary": "Generated workbook rows are not approvals.",
            "canonical_boundary": "No canonical rendering may change from this report alone.",
            "source_boundary": "Source acquisition rows require license/provenance decisions.",
        },
        "summary": summarize(units, packet_reviews, source_reviews, roles, gates, model_review),
        "unit_rows": units,
        "packet_review_rows": packet_reviews,
        "source_acquisition_review_rows": source_reviews,
        "review_role_rows": roles,
        "gate_rows": gates,
        "adjudication_failed_gates": adjudication.get("summary", {}).get("failed_gates", []),
    }


def svg_bar_chart(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    width: int = 1100,
    limit: int = 18,
) -> str:
    rows = rows[:limit]
    row_h = 30
    left = 280
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


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    units = report["unit_rows"]
    roles = report["review_role_rows"]
    gates = report["gate_rows"]
    packet_rows = report["packet_review_rows"]
    source_rows = report["source_acquisition_review_rows"]
    unit_table = [
        [
            row["ref"],
            row["unit_id"],
            f"{row['packet_priority_score']:.2f}",
            row["packet_priority_band"],
            row["packet_review_row_count"],
            "; ".join(row["distinct_reviewer_roles"]),
        ]
        for row in units[:20]
    ]
    role_table = [
        [
            row["reviewer_role"],
            row["total_review_row_count"],
            row["packet_review_row_count"],
            row["source_acquisition_review_row_count"],
            row["unit_count"],
            row["packet_family_count"],
            row["status"],
        ]
        for row in roles
    ]
    gate_table = [
        [
            row["gate"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in gates
    ]
    packet_preview = [
        [
            row["review_row_id"],
            row["ref"],
            row["packet_family_label"],
            row["reviewer_role"],
            row["packet_priority_band"],
            row["status"],
        ]
        for row in packet_rows[:20]
    ]
    source_preview = [
        [
            row["review_row_id"],
            row["candidate_label"],
            row["reviewer_role"],
            row["license_risk"],
            row["priority_band"],
            row["status"],
        ]
        for row in source_rows[:20]
    ]

    # Ruff's formatter rewrites nested dict-access f-strings here into Python
    # 3.12-only quote syntax. The project currently compiles under Python 3.11.
    # fmt: off
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Contextual Review Signoff Workbook</title>
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
    main {{ max-width: 1220px; margin: 0 auto; padding: 30px 34px 54px; }}
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
    <h1>AlephTav Contextual Review Signoff Workbook</h1>
    <p class="lede">
      Pending role-based review rows for source packets and source acquisition.
      This workbook bridges the contextual packet roadmap, source acquisition
      plan, model-review workload, and authority gates into executable reviewer
      templates.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}. No reviews completed.</p>
  </header>
  <main>
    <section>
      <h2>Workbook Summary</h2>
      {
        metric_cards(
            [
                (
                    "Units",
                    fmt_int(summary["unit_count"]),
                    f'{fmt_int(summary["packet_review_row_count"])} packet review rows.',
                ),
                (
                    "Source Rows",
                    fmt_int(summary["source_acquisition_review_row_count"]),
                    "License/provenance/acquisition review rows.",
                ),
                (
                    "Completion",
                    f'{summary["review_completion_pct"]:.2f}%',
                    "Generated templates only; no signed reviews.",
                ),
                (
                    "Roles",
                    fmt_int(summary["reviewer_role_count"]),
                    "Reviewer role queues represented.",
                ),
                (
                    "Critical Units",
                    fmt_int(summary["critical_unit_count"]),
                    f'{fmt_int(summary["highest_unit_count"])} highest-priority units.',
                ),
                (
                    "Reception",
                    fmt_int(summary["jewish_christian_unit_count"]),
                    "Units requiring separated Jewish/Christian review.",
                ),
                (
                    "Model Reviews",
                    fmt_int(summary["model_projected_human_review_rows"]),
                    "Projected model-output human review rows remain separate.",
                ),
                (
                    "Blocked Gates",
                    fmt_int(summary["blocked_gate_count"]),
                    "No authority signoff yet.",
                ),
            ]
        )
    }
      <div class="warning">
        Every row in this workbook is pending. It is a review-control artifact,
        not a reviewer decision, source approval, canonical rendering change, or
        release signoff.
      </div>
    </section>

    <section>
      <h2>Reviewer Workload</h2>
      <div class="chart">{
        svg_bar_chart(
            roles,
            label_key="reviewer_role",
            value_key="total_review_row_count",
            aria_label="Review rows by reviewer role",
            color="#2f6f73",
        )
    }</div>
      {
        table(
            ["Role", "Total", "Packet Rows", "Source Rows", "Units", "Families", "Status"],
            role_table,
        )
    }
    </section>

    <section>
      <h2>Priority Units</h2>
      {table(["Ref", "Unit", "Score", "Band", "Review Rows", "Roles"], unit_table)}
    </section>

    <section>
      <h2>Workbook Gates</h2>
      {table(["Gate", "Score", "Status", "Evidence", "Next Action"], gate_table)}
    </section>

    <section>
      <h2>Packet Review Preview</h2>
      {table(["Review Row", "Ref", "Packet Family", "Role", "Band", "Status"], packet_preview)}
    </section>

    <section>
      <h2>Source Acquisition Review Preview</h2>
      {table(["Review Row", "Candidate", "Role", "License Risk", "Band", "Status"], source_preview)}
    </section>
  </main>
</body>
</html>
"""
    # fmt: on


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate contextual review signoff workbook.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--packet-csv-output", type=Path, default=DEFAULT_PACKET_CSV_OUTPUT)
    parser.add_argument("--source-csv-output", type=Path, default=DEFAULT_SOURCE_CSV_OUTPUT)
    parser.add_argument("--role-csv-output", type=Path, default=DEFAULT_ROLE_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    args = parse_args()
    report = build_report()
    json_output = resolve(args.json_output)
    unit_csv_output = resolve(args.unit_csv_output)
    packet_csv_output = resolve(args.packet_csv_output)
    source_csv_output = resolve(args.source_csv_output)
    role_csv_output = resolve(args.role_csv_output)
    gate_csv_output = resolve(args.gate_csv_output)
    html_output = resolve(args.html_output)
    write_json(json_output, report)
    write_csv(unit_csv_output, report["unit_rows"])
    write_csv(packet_csv_output, report["packet_review_rows"])
    write_csv(source_csv_output, report["source_acquisition_review_rows"])
    write_csv(role_csv_output, report["review_role_rows"])
    write_csv(gate_csv_output, report["gate_rows"])
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(render_html(report), encoding="utf-8")
    print(json_output)
    print(unit_csv_output)
    print(packet_csv_output)
    print(source_csv_output)
    print(role_csv_output)
    print(gate_csv_output)
    print(html_output)


if __name__ == "__main__":
    main()
