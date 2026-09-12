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
REPORT_ROOT = ROOT / "reports" / "research"

PACKET_ROADMAP_PATH = REPORT_ROOT / "contextual_source_packet_roadmap.json"
SOURCE_MATURITY_PATH = REPORT_ROOT / "scholarly_source_maturity_report.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "contextual_source_acquisition_plan.json"
DEFAULT_CANDIDATE_CSV_OUTPUT = REPORT_ROOT / "contextual_source_acquisition_candidates.csv"
DEFAULT_PHASE_CSV_OUTPUT = REPORT_ROOT / "contextual_source_acquisition_phases.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "contextual_source_acquisition_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "contextual_source_acquisition_plan.html"

CANDIDATE_SOURCES: list[dict[str, Any]] = [
    {
        "candidate_id": "oshb_morphhb_whole_tanakh",
        "label": "Open Scriptures Hebrew Bible whole-Tanakh morphology",
        "source_families": ["morphology_lexeme", "whole_tanakh_lemma_context"],
        "evidence_role": (
            "Whole-Tanakh morphology, Strong/lemma normalization, and Psalm-to-canon "
            "lexeme controls."
        ),
        "official_url": "https://github.com/openscriptures/morphhb",
        "license_or_access": "CC BY 4.0 for morphology data; WLC text public domain.",
        "license_risk": "low",
        "machine_readable": True,
        "current_repo_status": "present_for_psalm_enrichment_not_full_tanakh_index",
        "acquisition_status": "extend_existing_source",
        "priority_band": "critical",
        "provenance_fact": (
            "The OSHB license page identifies WLC as public domain and morphology under "
            "Creative Commons Attribution 4.0."
        ),
    },
    {
        "candidate_id": "macula_hebrew_full_semantics",
        "label": "MACULA Hebrew full semantic-role and referent fields",
        "source_families": ["hebrew_source_tokens", "morphology_lexeme"],
        "evidence_role": (
            "Syntax trees, word-sense data, semantic roles, participant referents, and "
            "token-level enrichment."
        ),
        "official_url": "https://github.com/Clear-Bible/macula-hebrew",
        "license_or_access": "Composite open data with component licenses; many fields CC BY 4.0.",
        "license_risk": "medium",
        "machine_readable": True,
        "current_repo_status": "present_but_semantic_role_and_referent_missing_in_packets",
        "acquisition_status": "field_import_and_license_review_required",
        "priority_band": "critical",
        "provenance_fact": (
            "The MACULA Hebrew README lists semantic roles and participant referents as "
            "dataset components and points to component copyright statements."
        ),
    },
    {
        "candidate_id": "stepbible_data_tahot_lexicons",
        "label": "STEPBible Data TAHOT and lexical datasets",
        "source_families": [
            "whole_tanakh_lemma_context",
            "textual_witness_variants",
            "divine_name_title_policy",
        ],
        "evidence_role": (
            "Tagged Hebrew/Greek data, lexicons, semantic tags, and variant-aware "
            "Bible-study datasets."
        ),
        "official_url": "https://github.com/STEPBible/STEPBible-Data",
        "license_or_access": "Repository README presents STEPBible Data under CC BY 4.0 terms.",
        "license_risk": "low",
        "machine_readable": True,
        "current_repo_status": "absent",
        "acquisition_status": "candidate_for_import",
        "priority_band": "critical",
        "provenance_fact": (
            "The STEPBible Data repository describes downloadable tab-separated datasets "
            "and TAHOT as Leningrad Codex data with morphology and semantic tags."
        ),
    },
    {
        "candidate_id": "etcbc_bhsa_text_fabric",
        "label": "ETCBC BHSA Text-Fabric Hebrew Bible annotations",
        "source_families": ["whole_tanakh_lemma_context", "morphology_lexeme"],
        "evidence_role": (
            "Research-grade whole-Hebrew-Bible linguistic annotations and reproducible "
            "query workflow."
        ),
        "official_url": "https://etcbc.github.io/bhsa/",
        "license_or_access": "CC BY-NC 4.0; commercial use requires consent.",
        "license_risk": "high_noncommercial",
        "machine_readable": True,
        "current_repo_status": "absent",
        "acquisition_status": "research_only_until_license_decision",
        "priority_band": "high",
        "provenance_fact": (
            "The BHSA project describes a Text-Fabric Hebrew Bible database with "
            "linguistic annotations and a CC BY-NC 4.0 license."
        ),
    },
    {
        "candidate_id": "sefaria_export_commentary_links",
        "label": "Sefaria Export and API for Jewish reception packets",
        "source_families": ["jewish_reception_sources", "academic_critical_comparison"],
        "evidence_role": (
            "Jewish textual witnesses, commentary paths, intertextual links, and "
            "per-text version metadata."
        ),
        "official_url": "https://github.com/Sefaria/Sefaria-Export",
        "license_or_access": "Per-text license field; no single repository-wide text license.",
        "license_risk": "medium_per_text_license",
        "machine_readable": True,
        "current_repo_status": "restricted_witness_snapshot_only",
        "acquisition_status": "per_text_license_and_scope_review_required",
        "priority_band": "critical",
        "provenance_fact": (
            "Sefaria Export documents a public GCS text corpus and notes each text has "
            "its own license field."
        ),
    },
    {
        "candidate_id": "sblgnt_nt_reception",
        "label": "SBL Greek New Testament for Christian reception anchors",
        "source_families": ["christian_reception_sources"],
        "evidence_role": (
            "New Testament Greek anchors for Psalm reception and quotation/allusion review."
        ),
        "official_url": "https://sblgnt.com/",
        "license_or_access": "CC BY 4.0.",
        "license_risk": "low",
        "machine_readable": True,
        "current_repo_status": "absent",
        "acquisition_status": "candidate_for_import",
        "priority_band": "high",
        "provenance_fact": (
            "The SBLGNT site describes the text as freely available and licensed under "
            "Creative Commons Attribution 4.0."
        ),
    },
    {
        "candidate_id": "opengnt_morphology",
        "label": "Open Greek New Testament morphology and alignment aids",
        "source_families": ["christian_reception_sources", "academic_critical_comparison"],
        "evidence_role": (
            "Greek morphology and intertextual data for checking Christian reception claims."
        ),
        "official_url": "https://github.com/eliranwong/OpenGNT",
        "license_or_access": "CC BY-SA 4.0 for the main OpenGNT text.",
        "license_risk": "medium_sharealike",
        "machine_readable": True,
        "current_repo_status": "absent",
        "acquisition_status": "candidate_for_review",
        "priority_band": "medium",
        "provenance_fact": "The OpenGNT repository states the main text is CC BY-SA 4.0.",
    },
    {
        "candidate_id": "ccel_christian_classics",
        "label": "Christian Classics Ethereal Library reception corpus",
        "source_families": ["christian_reception_sources"],
        "evidence_role": (
            "Patristic, medieval, Reformation, and later Christian interpretation in "
            "public-domain or permissioned editions."
        ),
        "official_url": "https://www.ccel.org/about/copyright.html",
        "license_or_access": (
            "Most editions are based on US public-domain books, but introductions, "
            "formatting, and some works carry restrictions."
        ),
        "license_risk": "medium_public_domain_jurisdiction_and_formatting",
        "machine_readable": False,
        "current_repo_status": "absent",
        "acquisition_status": "manual_citation_or_permission_review_required",
        "priority_band": "medium",
        "provenance_fact": (
            "CCEL's copyright page says most editions are based on public-domain books "
            "in the US, while special contents and some works may be restricted."
        ),
    },
    {
        "candidate_id": "oracc_ane_context",
        "label": "ORACC ancient Near Eastern context corpus",
        "source_families": ["ancient_near_eastern_context"],
        "evidence_role": (
            "Open cuneiform corpora for royal ideology, temple/cult, lament, wisdom, "
            "creation, and cultural background controls."
        ),
        "official_url": "https://oracc.museum.upenn.edu/",
        "license_or_access": (
            "Open corpus project; open-data pages describe Creative Commons terms."
        ),
        "license_risk": "medium_project_specific_license",
        "machine_readable": True,
        "current_repo_status": "absent",
        "acquisition_status": "candidate_for_context_notes_not_translation_basis",
        "priority_band": "high",
        "provenance_fact": (
            "ORACC describes itself as a richly annotated cuneiform corpus with open "
            "licensing for scholarly reuse."
        ),
    },
    {
        "candidate_id": "licensed_academic_commentary_bibliography",
        "label": "Licensed academic commentary and article bibliography",
        "source_families": ["academic_critical_comparison"],
        "evidence_role": (
            "Peer-reviewed philology, translation history, and disputed-interpretation "
            "adjudication."
        ),
        "official_url": "",
        "license_or_access": (
            "Manual bibliography; many sources will be copyrighted or database-licensed."
        ),
        "license_risk": "high_manual_rights_management",
        "machine_readable": False,
        "current_repo_status": "absent",
        "acquisition_status": "bibliography_required_not_bulk_import",
        "priority_band": "critical",
        "provenance_fact": (
            "No open corpus substitute is currently identified for signed academic "
            "critical comparison."
        ),
    },
    {
        "candidate_id": "internal_review_audit_service",
        "label": "Internal review service and audit records",
        "source_families": ["human_release_signoff"],
        "evidence_role": "Role-specific human signoff and release authority.",
        "official_url": "",
        "license_or_access": "Internal project workflow.",
        "license_risk": "none_internal",
        "machine_readable": True,
        "current_repo_status": "planned_no_completed_signoff_rows",
        "acquisition_status": "workflow_execution_required",
        "priority_band": "critical",
        "provenance_fact": (
            "Generated research reports are not reviewer approval or release signoff."
        ),
    },
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
    return round(float(part) / float(total) * 100, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def rows_by_family(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["source_family"]): row for row in rows if row.get("source_family")}


def units_by_family(unit_rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for row in unit_rows:
        unit_id = str(row["unit_id"])
        for family in row.get("packet_families", []):
            grouped[str(family)].add(unit_id)
    return grouped


def candidate_priority_score(
    candidate: dict[str, Any],
    family_rows: dict[str, dict[str, Any]],
) -> float:
    score = 0.0
    for family in candidate["source_families"]:
        row = family_rows.get(family, {})
        score += float(row.get("unit_count") or 0)
        score += float(row.get("highest_priority_unit_count") or 0) * 1.5
        status = str(row.get("status") or "")
        if status.startswith(("blocked", "missing", "routing_only")):
            score += 30.0
    if candidate["priority_band"] == "critical":
        score += 35.0
    elif candidate["priority_band"] == "high":
        score += 20.0
    elif candidate["priority_band"] == "medium":
        score += 8.0
    if candidate["license_risk"].startswith("high"):
        score += 10.0
    return round(score, 2)


def build_candidate_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    family_rows = rows_by_family(packet.get("source_family_rows", []))
    family_units = units_by_family(packet.get("unit_rows", []))
    rows = []
    for candidate in CANDIDATE_SOURCES:
        impacted_units: set[str] = set()
        top_refs: list[str] = []
        highest_priority_count = 0
        for family in candidate["source_families"]:
            impacted_units.update(family_units.get(family, set()))
            row = family_rows.get(family, {})
            if row.get("top_ref"):
                top_refs.append(str(row["top_ref"]))
            highest_priority_count += int(row.get("highest_priority_unit_count") or 0)
        candidate_row = {
            **candidate,
            "packet_unit_count": len(impacted_units),
            "highest_priority_family_unit_count": highest_priority_count,
            "top_refs": sorted(set(top_refs)),
            "priority_score": candidate_priority_score(candidate, family_rows),
        }
        rows.append(candidate_row)
    return sorted(rows, key=lambda row: float(row["priority_score"]), reverse=True)


def build_phase_rows(candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {row["candidate_id"]: row for row in candidate_rows}
    phase_specs = [
        {
            "phase": "1_whole_tanakh_morphology_and_semantics",
            "label": "Whole-Tanakh morphology and semantic controls",
            "candidate_ids": [
                "oshb_morphhb_whole_tanakh",
                "macula_hebrew_full_semantics",
                "stepbible_data_tahot_lexicons",
            ],
            "exit_gate": (
                "non-Psalm Hebrew morphology and semantic-role/referent coverage available."
            ),
        },
        {
            "phase": "2_jewish_christian_reception_lanes",
            "label": "Separated Jewish and Christian reception packets",
            "candidate_ids": [
                "sefaria_export_commentary_links",
                "sblgnt_nt_reception",
                "opengnt_morphology",
                "ccel_christian_classics",
            ],
            "exit_gate": "Reception source packets cite separate Jewish and Christian evidence.",
        },
        {
            "phase": "3_ancient_cultural_context",
            "label": "Ancient Near Eastern cultural context packets",
            "candidate_ids": ["oracc_ane_context"],
            "exit_gate": "Cultural claims are source-backed and isolated from translation wording.",
        },
        {
            "phase": "4_academic_critical_comparison",
            "label": "Academic critical comparison bibliography",
            "candidate_ids": ["licensed_academic_commentary_bibliography"],
            "exit_gate": "Scholarly comparison notes distinguish evidence from authority.",
        },
        {
            "phase": "5_review_and_release_signoff",
            "label": "Human review and release authority",
            "candidate_ids": ["internal_review_audit_service"],
            "exit_gate": "Role-specific reviewer approvals and audit records exist.",
        },
    ]
    rows = []
    for rank, phase in enumerate(phase_specs, start=1):
        candidates = [by_id[item] for item in phase["candidate_ids"] if item in by_id]
        impacted_units = max((int(row["packet_unit_count"]) for row in candidates), default=0)
        rows.append(
            {
                "rank": rank,
                "phase": phase["phase"],
                "label": phase["label"],
                "candidate_count": len(candidates),
                "candidate_ids": [row["candidate_id"] for row in candidates],
                "max_packet_unit_count": impacted_units,
                "mean_priority_score": mean([float(row["priority_score"]) for row in candidates]),
                "high_license_risk_count": sum(
                    1 for row in candidates if str(row["license_risk"]).startswith("high")
                ),
                "machine_readable_count": sum(1 for row in candidates if row["machine_readable"]),
                "exit_gate": phase["exit_gate"],
            }
        )
    return rows


def build_gate_rows(
    candidate_rows: list[dict[str, Any]],
    packet_summary: dict[str, Any],
    maturity_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    low_license = sum(1 for row in candidate_rows if row["license_risk"] == "low")
    machine = sum(1 for row in candidate_rows if row["machine_readable"])
    high_license = sum(1 for row in candidate_rows if str(row["license_risk"]).startswith("high"))
    per_text = sum(1 for row in candidate_rows if "per_text" in str(row["license_risk"]))
    return [
        {
            "gate": "machine_readable_source_candidates",
            "score_pct": pct(machine, len(candidate_rows)),
            "status": "partial",
            "evidence": (
                f"{machine} of {len(candidate_rows)} acquisition candidates are machine-readable."
            ),
            "next_action": "Prioritize machine-readable corpora before manual-only sources.",
        },
        {
            "gate": "low_license_risk_candidates",
            "score_pct": pct(low_license, len(candidate_rows)),
            "status": "partial",
            "evidence": f"{low_license} of {len(candidate_rows)} candidates have low license risk.",
            "next_action": "Run per-source license review before import or display.",
        },
        {
            "gate": "high_or_per_text_license_review",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": (
                f"{high_license} high-risk candidates and {per_text} per-text-license "
                "candidate require review."
            ),
            "next_action": (
                "Do not ingest restricted or per-text licensed sources without manifests."
            ),
        },
        {
            "gate": "whole_tanakh_morphology_gap",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": (
                "Current local non-Psalm Hebrew morphology books: "
                f"{maturity_summary['whole_tanakh_non_psalm_morphology_book_count']}."
            ),
            "next_action": "Acquire/import a whole-Tanakh morphology source before lemma claims.",
        },
        {
            "gate": "reception_packet_gap",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": (
                f"{packet_summary['jewish_christian_packet_unit_count']} units require "
                "separated Jewish/Christian packet work."
            ),
            "next_action": "Build signed source packets before reception affects translation.",
        },
        {
            "gate": "human_signoff_gap",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": "No generated source-acquisition row is human review signoff.",
            "next_action": "Execute reviewer and release workflows after source acquisition.",
        },
    ]


def summarize(
    candidate_rows: list[dict[str, Any]],
    phase_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    packet_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "candidate_count": len(candidate_rows),
        "machine_readable_candidate_count": sum(
            1 for row in candidate_rows if row["machine_readable"]
        ),
        "low_license_risk_candidate_count": sum(
            1 for row in candidate_rows if row["license_risk"] == "low"
        ),
        "high_license_risk_candidate_count": sum(
            1 for row in candidate_rows if str(row["license_risk"]).startswith("high")
        ),
        "per_text_license_candidate_count": sum(
            1 for row in candidate_rows if "per_text" in str(row["license_risk"])
        ),
        "critical_candidate_count": sum(
            1 for row in candidate_rows if row["priority_band"] == "critical"
        ),
        "source_family_count": packet_summary["source_family_count"],
        "packet_unit_count": packet_summary["unit_count"],
        "packet_family_assignment_count": packet_summary["family_assignment_count"],
        "blocked_or_routing_source_family_count": packet_summary[
            "blocked_or_routing_source_family_count"
        ],
        "phase_count": len(phase_rows),
        "gate_count": len(gate_rows),
        "blocked_gate_count": sum(1 for row in gate_rows if row["status"] == "blocked"),
        "top_candidate_id": candidate_rows[0]["candidate_id"] if candidate_rows else "",
        "top_candidate_label": candidate_rows[0]["label"] if candidate_rows else "",
        "top_candidate_priority_score": (
            candidate_rows[0]["priority_score"] if candidate_rows else 0.0
        ),
        "status": "source_acquisition_plan_generated_not_source_approval",
    }


def build_report() -> dict[str, Any]:
    packet = load_json(PACKET_ROADMAP_PATH)
    maturity = load_json(SOURCE_MATURITY_PATH)
    candidate_rows = build_candidate_rows(packet)
    phase_rows = build_phase_rows(candidate_rows)
    gate_rows = build_gate_rows(candidate_rows, packet["summary"], maturity["summary"])
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "contextual source acquisition plan generated; not source approval",
        "source_paths": {
            "packet_roadmap": str(PACKET_ROADMAP_PATH.relative_to(ROOT)),
            "source_maturity": str(SOURCE_MATURITY_PATH.relative_to(ROOT)),
        },
        "policy": {
            "no_raw_mutation": "This report does not download or alter data/raw.",
            "license_boundary": "Every external source needs a manifest before local import.",
            "authority_boundary": "Acquired source evidence still requires reviewer signoff.",
            "reception_boundary": "Jewish and Christian evidence must remain separated.",
        },
        "summary": summarize(candidate_rows, phase_rows, gate_rows, packet["summary"]),
        "candidate_rows": candidate_rows,
        "phase_rows": phase_rows,
        "gate_rows": gate_rows,
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
    candidates = report["candidate_rows"]
    phases = report["phase_rows"]
    gates = report["gate_rows"]
    candidate_table = [
        [
            row["label"],
            row["priority_band"],
            row["priority_score"],
            row["packet_unit_count"],
            row["license_risk"],
            row["machine_readable"],
            row["acquisition_status"],
            row["official_url"],
        ]
        for row in candidates
    ]
    phase_table = [
        [
            row["rank"],
            row["label"],
            row["candidate_count"],
            row["max_packet_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["machine_readable_count"],
            row["high_license_risk_count"],
            row["exit_gate"],
        ]
        for row in phases
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
    provenance_table = [
        [
            row["label"],
            row["license_or_access"],
            row["provenance_fact"],
            row["official_url"],
        ]
        for row in candidates
    ]

    # Ruff's formatter rewrites nested dict-access f-strings here into Python
    # 3.12-only quote syntax. The project currently compiles under Python 3.11.
    # fmt: off
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Contextual Source Acquisition Plan</title>
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
    a {{ color: var(--accent); text-decoration: none; font-weight: 700; }}
    a:hover {{ text-decoration: underline; }}
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
    <h1>AlephTav Contextual Source Acquisition Plan</h1>
    <p class="lede">
      Candidate source register for closing the contextual packet gaps: whole-Tanakh
      morphology, semantic roles, Jewish and Christian reception, ancient Near Eastern
      context, academic comparison, and reviewer signoff.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}. Not source approval.</p>
  </header>
  <main>
    <section>
      <h2>Acquisition Summary</h2>
      {
        metric_cards(
            [
                (
                    "Candidates",
                    fmt_int(summary["candidate_count"]),
                    f'{fmt_int(summary["machine_readable_candidate_count"])} machine-readable.',
                ),
                (
                    "Packet Units",
                    fmt_int(summary["packet_unit_count"]),
                    f'{fmt_int(summary["packet_family_assignment_count"])} packet assignments.',
                ),
                (
                    "Low-Risk License",
                    fmt_int(summary["low_license_risk_candidate_count"]),
                    (
                        f'{fmt_int(summary["high_license_risk_candidate_count"])} '
                        "high-risk candidates."
                    ),
                ),
                (
                    "Critical",
                    fmt_int(summary["critical_candidate_count"]),
                    "Candidates marked critical by packet impact.",
                ),
                (
                    "Source Families",
                    fmt_int(summary["source_family_count"]),
                    (
                        f'{fmt_int(summary["blocked_or_routing_source_family_count"])} '
                        "blocked/routing-only."
                    ),
                ),
                (
                    "Phases",
                    fmt_int(summary["phase_count"]),
                    "Sequenced acquisition and signoff phases.",
                ),
                (
                    "Blocked Gates",
                    fmt_int(summary["blocked_gate_count"]),
                    "License, morphology, reception, and signoff blockers.",
                ),
                (
                    "Top Candidate",
                    summary["top_candidate_label"],
                    f'Score {summary["top_candidate_priority_score"]:.2f}.',
                ),
            ]
        )
    }
      <div class="warning">
        This is not permission to ingest or generate from any external source.
        Every source needs a manifest, license review, and source-specific
        acquisition decision before it becomes part of the local workbench.
      </div>
    </section>

    <section>
      <h2>Candidate Priorities</h2>
      <div class="chart">{
        svg_bar_chart(
            candidates,
            label_key="label",
            value_key="priority_score",
            aria_label="Source acquisition priority score",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_bar_chart(
            candidates,
            label_key="label",
            value_key="packet_unit_count",
            aria_label="Packet units affected by source candidate",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Candidate",
                "Priority",
                "Score",
                "Units",
                "License Risk",
                "Machine",
                "Status",
                "URL",
            ],
            candidate_table,
        )
    }
    </section>

    <section>
      <h2>Acquisition Phases</h2>
      {
        table(
            [
                "Rank",
                "Phase",
                "Sources",
                "Unit Reach",
                "Mean Score",
                "Machine",
                "High Risk",
                "Exit Gate",
            ],
            phase_table,
        )
    }
    </section>

    <section>
      <h2>Gates</h2>
      {table(["Gate", "Score", "Status", "Evidence", "Next Action"], gate_table)}
    </section>

    <section>
      <h2>Provenance Notes</h2>
      {table(["Candidate", "License or Access", "Primary-Page Fact", "URL"], provenance_table)}
    </section>
  </main>
</body>
</html>
"""
    # fmt: on


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate contextual source acquisition plan.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--candidate-csv-output", type=Path, default=DEFAULT_CANDIDATE_CSV_OUTPUT)
    parser.add_argument("--phase-csv-output", type=Path, default=DEFAULT_PHASE_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    args = parse_args()
    report = build_report()
    json_output = resolve(args.json_output)
    candidate_csv_output = resolve(args.candidate_csv_output)
    phase_csv_output = resolve(args.phase_csv_output)
    gate_csv_output = resolve(args.gate_csv_output)
    html_output = resolve(args.html_output)
    write_json(json_output, report)
    write_csv(candidate_csv_output, report["candidate_rows"])
    write_csv(phase_csv_output, report["phase_rows"])
    write_csv(gate_csv_output, report["gate_rows"])
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(render_html(report), encoding="utf-8")
    print(json_output)
    print(candidate_csv_output)
    print(phase_csv_output)
    print(gate_csv_output)
    print(html_output)


if __name__ == "__main__":
    main()
