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

ADJUDICATION_PATH = REPORT_ROOT / "interpretive_adjudication_matrix.json"
BOUNDARY_PATH = REPORT_ROOT / "reception_interpretation_boundary.json"
CANONICAL_CONTEXT_PATH = REPORT_ROOT / "canonical_context_network.json"
WITNESS_PATH = REPORT_ROOT / "witness_reception_readiness.json"
CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
SOURCE_MATURITY_PATH = REPORT_ROOT / "scholarly_source_maturity_report.json"
CASEBOOK_PATH = REPORT_ROOT / "scholarly_casebook.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "contextual_source_packet_roadmap.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "contextual_source_packet_units.csv"
DEFAULT_FAMILY_CSV_OUTPUT = REPORT_ROOT / "contextual_source_packet_families.csv"
DEFAULT_ROLE_CSV_OUTPUT = REPORT_ROOT / "contextual_source_packet_roles.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "contextual_source_packet_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "contextual_source_packet_roadmap.html"

SOURCE_FAMILIES: dict[str, dict[str, Any]] = {
    "hebrew_source_tokens": {
        "label": "Hebrew Source Tokens",
        "status": "available_needs_review",
        "source_classes": ["UXLC/WLC Hebrew", "OSHB token morphology", "MACULA enrichment"],
        "roles": ["Hebrew", "lexical", "alignment"],
        "authority_boundary": "Translation wording must be anchored here before other frames.",
        "required_artifacts": [
            "token list",
            "morphology notes",
            "alignment rationale",
        ],
    },
    "morphology_lexeme": {
        "label": "Morphology and Lexeme Control",
        "status": "prototype",
        "source_classes": ["OSHB morphology", "MACULA lemma/gloss enrichment"],
        "roles": ["Hebrew", "lexical"],
        "authority_boundary": "Strong/lemma evidence is Psalm-local; semantic role is absent.",
        "required_artifacts": [
            "lemma and Strong notes",
            "morphology ambiguity notes",
            "semantic-role gap note",
        ],
    },
    "whole_tanakh_lemma_context": {
        "label": "Whole-Tanakh Lemma Context",
        "status": "blocked_surface_only",
        "source_classes": ["UXLC surface-form search", "future whole-Tanakh morphology index"],
        "roles": ["Hebrew", "lexical"],
        "authority_boundary": "Current cross-canon evidence is surface-form, not lemma proof.",
        "required_artifacts": [
            "surface-context hits",
            "division/book spread",
            "explicit no-lemma-proof warning",
        ],
    },
    "textual_witness_variants": {
        "label": "Textual Witness Variants",
        "status": "evidence_ready_needs_review",
        "source_classes": ["LXX Greek", "ASV", "KJV", "WEB", "restricted Sefaria witness"],
        "roles": ["Hebrew", "alignment", "theology"],
        "authority_boundary": "Witnesses must stay labeled and cannot silently replace Hebrew.",
        "required_artifacts": [
            "witness table",
            "variant pressure note",
            "generation-source policy note",
        ],
    },
    "ancient_near_eastern_context": {
        "label": "Ancient Cultural Context",
        "status": "routing_only",
        "source_classes": [
            "ancient royal ideology",
            "temple and cultic setting",
            "lament and justice conventions",
            "creation and anthropology context",
        ],
        "roles": ["Hebrew", "theology"],
        "authority_boundary": "Cultural explanation may inform rationale, not override tokens.",
        "required_artifacts": [
            "historical setting note",
            "genre/cultural claim boundary",
            "reviewer decision",
        ],
    },
    "jewish_reception_sources": {
        "label": "Jewish Reception Sources",
        "status": "missing_signed_synthesis",
        "source_classes": [
            "Second Temple and rabbinic reception",
            "medieval Jewish commentary",
            "modern Jewish academic interpretation",
        ],
        "roles": ["theology"],
        "authority_boundary": "Jewish reception must be separate from Christian reception.",
        "required_artifacts": [
            "Jewish reception note",
            "source-scope boundary",
            "reviewer signoff",
        ],
    },
    "christian_reception_sources": {
        "label": "Christian Reception Sources",
        "status": "missing_signed_synthesis",
        "source_classes": [
            "New Testament use",
            "patristic reception",
            "confessional and modern Christian interpretation",
        ],
        "roles": ["theology"],
        "authority_boundary": "Christian reception must be separate from Jewish reception.",
        "required_artifacts": [
            "Christian reception note",
            "source-scope boundary",
            "reviewer signoff",
        ],
    },
    "academic_critical_comparison": {
        "label": "Academic Critical Comparison",
        "status": "missing_signed_synthesis",
        "source_classes": [
            "critical commentaries",
            "philological articles",
            "translation-history comparison",
        ],
        "roles": ["Hebrew", "theology"],
        "authority_boundary": "Academic comparison is evidence, not automatic wording authority.",
        "required_artifacts": [
            "scholarly comparison note",
            "minority/majority view distinction",
            "translation impact decision",
        ],
    },
    "divine_name_title_policy": {
        "label": "Divine Name and Title Policy",
        "status": "review_required",
        "source_classes": ["project divine-name policy", "Hebrew title morphology"],
        "roles": ["Hebrew", "theology", "release"],
        "authority_boundary": "Divine-name handling must be policy-stable across layers.",
        "required_artifacts": [
            "divine-name token list",
            "policy decision",
            "layer consistency check",
        ],
    },
    "poetic_genre_form": {
        "label": "Poetic and Genre Form",
        "status": "review_required",
        "source_classes": ["Hebrew poetics", "lament genre", "parallelism and meter analysis"],
        "roles": ["Hebrew", "lyric"],
        "authority_boundary": "Poetic decisions must not erase lexical or alignment evidence.",
        "required_artifacts": [
            "poetic form note",
            "parallelism note",
            "style-layer boundary",
        ],
    },
    "human_release_signoff": {
        "label": "Human and Release Signoff",
        "status": "blocked_missing_review",
        "source_classes": ["review service", "audit records", "release checklist"],
        "roles": ["Hebrew", "lexical", "alignment", "theology", "release"],
        "authority_boundary": "No generated packet is authority without human approval.",
        "required_artifacts": [
            "role review rows",
            "audit record",
            "release signoff",
        ],
    },
}

DOMAIN_FAMILY_MAP = {
    "anthropology_body": ["ancient_near_eastern_context"],
    "covenant_mercy": ["morphology_lexeme", "whole_tanakh_lemma_context"],
    "creation_cosmos": ["ancient_near_eastern_context"],
    "divine_names_titles": ["divine_name_title_policy"],
    "jewish_christian_reception": [
        "jewish_reception_sources",
        "christian_reception_sources",
        "academic_critical_comparison",
    ],
    "lament_enemy_justice": ["ancient_near_eastern_context", "poetic_genre_form"],
    "nations_zion_exile": ["ancient_near_eastern_context", "whole_tanakh_lemma_context"],
    "royal_kingship": ["ancient_near_eastern_context"],
    "temple_cult_liturgy": ["ancient_near_eastern_context"],
    "textual_witness_pressure": ["textual_witness_variants"],
    "wisdom_torah": ["whole_tanakh_lemma_context"],
}

FRAME_FAMILY_MAP = {
    "source_hebrew_control": ["hebrew_source_tokens"],
    "source_hebrew_plain_sense": ["hebrew_source_tokens"],
    "morphology_lexeme_control": ["morphology_lexeme"],
    "whole_tanakh_context": ["whole_tanakh_lemma_context"],
    "ancient_cultural_setting": ["ancient_near_eastern_context"],
    "ancient_royal_ideology": ["ancient_near_eastern_context"],
    "creation_anthropology": ["ancient_near_eastern_context"],
    "temple_liturgy": ["ancient_near_eastern_context"],
    "lament_genre": ["poetic_genre_form", "ancient_near_eastern_context"],
    "poetic_form_genre": ["poetic_genre_form"],
    "textual_witnesses": ["textual_witness_variants"],
    "reception_history": ["jewish_reception_sources", "christian_reception_sources"],
    "jewish_christian_reception": [
        "jewish_reception_sources",
        "christian_reception_sources",
    ],
    "jewish_reception": ["jewish_reception_sources"],
    "christian_reception": ["christian_reception_sources"],
    "academic_critical_comparison": ["academic_critical_comparison"],
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


def families_for_unit(row: dict[str, Any], boundary: dict[str, Any]) -> list[str]:
    families = {
        "hebrew_source_tokens",
        "morphology_lexeme",
        "whole_tanakh_lemma_context",
        "human_release_signoff",
    }
    if row.get("textual_witness_pressure"):
        families.add("textual_witness_variants")
    if row.get("ancient_culture_pressure"):
        families.add("ancient_near_eastern_context")
    if row.get("jewish_christian_separation_required") or boundary.get("reception_sensitive"):
        families.update(
            [
                "jewish_reception_sources",
                "christian_reception_sources",
                "academic_critical_comparison",
            ]
        )
    if row.get("theology_pressure"):
        families.add("divine_name_title_policy")
    for domain in row.get("domains", []):
        families.update(DOMAIN_FAMILY_MAP.get(str(domain), []))
    for frame in row.get("required_frames", []):
        families.update(FRAME_FAMILY_MAP.get(str(frame), []))
    return sorted(families)


def packet_band(score: float) -> str:
    if score >= 310.0:
        return "critical"
    if score >= 240.0:
        return "highest"
    if score >= 170.0:
        return "high"
    return "standard"


def build_unit_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    boundary_by_unit = rows_by_unit(data["boundary"].get("unit_boundary_rows", []))
    canonical_by_unit = rows_by_unit(data["canonical"].get("unit_network_rows", []))
    witness_by_unit = rows_by_unit(data["witness"].get("reception_frame_rows", []))
    units = []
    for rank, row in enumerate(data["adjudication"].get("unit_rows", []), start=1):
        unit_id = str(row["unit_id"])
        boundary = boundary_by_unit.get(unit_id, {})
        canonical = canonical_by_unit.get(unit_id, {})
        witness = witness_by_unit.get(unit_id, {})
        families = families_for_unit(row, boundary)
        packet_score = (
            float(row.get("adjudication_priority_score") or 0.0)
            + float(row.get("boundary_risk_score") or boundary.get("boundary_risk_score") or 0.0)
            + len(families) * 4.0
            + int(row.get("blocked_lane_count") or 0) * 8.0
        )
        units.append(
            {
                "rank": rank,
                "unit_id": unit_id,
                "ref": row.get("ref", ""),
                "packet_priority_score": round(packet_score, 2),
                "packet_priority_band": packet_band(packet_score),
                "adjudication_priority_score": row.get("adjudication_priority_score", 0.0),
                "adjudication_priority_band": row.get("adjudication_priority_band", ""),
                "boundary_risk_score": row.get(
                    "boundary_risk_score",
                    boundary.get("boundary_risk_score", 0.0),
                ),
                "packet_family_count": len(families),
                "packet_families": families,
                "domains": row.get("domains", []),
                "required_frames": row.get("required_frames", []),
                "required_review_roles": row.get("required_review_roles", []),
                "claim_controls": row.get("claim_controls", []),
                "lane_statuses": row.get("lane_statuses", {}),
                "blocked_lane_count": row.get("blocked_lane_count", 0),
                "review_lane_count": row.get("review_lane_count", 0),
                "reception_sensitive": bool(row.get("reception_sensitive")),
                "jewish_christian_separation_required": bool(
                    row.get("jewish_christian_separation_required")
                ),
                "textual_witness_pressure": bool(row.get("textual_witness_pressure")),
                "ancient_culture_pressure": bool(row.get("ancient_culture_pressure")),
                "complete_expected_witness_set": bool(row.get("complete_expected_witness_set")),
                "witness_count": row.get("witness_count", witness.get("witness_count", 0)),
                "content_token_outside_context_pct": row.get(
                    "content_token_outside_context_pct",
                    canonical.get("content_token_outside_context_pct", 0.0),
                ),
                "outside_division_count": canonical.get("outside_division_count", 0),
                "top_anchor_tokens": canonical.get("top_anchor_tokens", [])[:5],
                "source_hebrew": canonical.get("source_hebrew", ""),
                "case_study_reason": boundary.get("case_study_reason", ""),
            }
        )
    return sorted(units, key=lambda item: float(item["packet_priority_score"]), reverse=True)


def family_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        for family in row["packet_families"]:
            grouped[family].append(row)

    rows = []
    for family, catalog in SOURCE_FAMILIES.items():
        units = sorted(
            grouped.get(family, []),
            key=lambda item: float(item["packet_priority_score"]),
            reverse=True,
        )
        top = units[0] if units else {}
        role_set = sorted(catalog["roles"])
        rows.append(
            {
                "source_family": family,
                "label": catalog["label"],
                "status": catalog["status"],
                "unit_count": len(units),
                "highest_priority_unit_count": sum(
                    1 for unit in units if unit["packet_priority_band"] in {"critical", "highest"}
                ),
                "reception_sensitive_unit_count": sum(
                    1 for unit in units if unit["reception_sensitive"]
                ),
                "jewish_christian_unit_count": sum(
                    1 for unit in units if unit["jewish_christian_separation_required"]
                ),
                "textual_witness_unit_count": sum(
                    1 for unit in units if unit["textual_witness_pressure"]
                ),
                "ancient_culture_unit_count": sum(
                    1 for unit in units if unit["ancient_culture_pressure"]
                ),
                "top_unit": top.get("unit_id", ""),
                "top_ref": top.get("ref", ""),
                "top_packet_priority_score": top.get("packet_priority_score", 0.0),
                "review_roles": role_set,
                "source_classes": catalog["source_classes"],
                "required_artifacts": catalog["required_artifacts"],
                "authority_boundary": catalog["authority_boundary"],
            }
        )
    return sorted(rows, key=lambda item: int(item["unit_count"]), reverse=True)


def role_rows(
    unit_rows: list[dict[str, Any]],
    family_rows_: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    role_units: dict[str, set[str]] = defaultdict(set)
    role_family_assignments: Counter[str] = Counter()
    role_highest: Counter[str] = Counter()
    for family in family_rows_:
        for role in family["review_roles"]:
            role_family_assignments[role] += int(family["unit_count"])
    for unit in unit_rows:
        roles = set(unit.get("required_review_roles", []))
        for family in unit["packet_families"]:
            roles.update(SOURCE_FAMILIES[family]["roles"])
        for role in roles:
            role_units[str(role)].add(str(unit["unit_id"]))
            if unit["packet_priority_band"] in {"critical", "highest"}:
                role_highest[str(role)] += 1
    rows = []
    for role, units in sorted(role_units.items(), key=lambda item: len(item[1]), reverse=True):
        rows.append(
            {
                "reviewer_role": role,
                "unit_count": len(units),
                "family_assignment_count": role_family_assignments.get(role, 0),
                "highest_priority_unit_count": role_highest.get(role, 0),
                "authority_boundary": "Reviewer signoff is required before authority claims.",
            }
        )
    return rows


def gate_rows(
    unit_rows: list[dict[str, Any]],
    family_rows_: list[dict[str, Any]],
    data: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    source_summary = data["source_maturity"]["summary"]
    blocked_families = [
        row
        for row in family_rows_
        if str(row["status"]).startswith(("blocked", "missing", "routing_only"))
    ]
    jcx_units = sum(1 for row in unit_rows if row["jewish_christian_separation_required"])
    culture_units = sum(1 for row in unit_rows if row["ancient_culture_pressure"])
    textual_units = sum(1 for row in unit_rows if row["textual_witness_pressure"])
    return [
        {
            "gate": "packet_scope_complete",
            "score_pct": 100.0,
            "status": "pass",
            "evidence": f"{len(unit_rows)} expanded units mapped to source packet families.",
            "next_action": "Use the unit packet queue for reviewer assignment.",
        },
        {
            "gate": "whole_tanakh_lemma_source_available",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": (
                "Current source maturity reports "
                f"{source_summary['whole_tanakh_non_psalm_morphology_book_count']} "
                "non-Psalm morphology books."
            ),
            "next_action": "Acquire or build a whole-Tanakh morphology/lemma index.",
        },
        {
            "gate": "reception_source_packets_signed",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": f"{jcx_units} units require Jewish/Christian separation.",
            "next_action": "Create signed Jewish, Christian, and academic source packets.",
        },
        {
            "gate": "ancient_culture_packets_signed",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": f"{culture_units} units require ancient-cultural context packets.",
            "next_action": "Attach source-backed cultural notes and reviewer decisions.",
        },
        {
            "gate": "textual_witness_review_signed",
            "score_pct": 0.0,
            "status": "review_required",
            "evidence": f"{textual_units} units carry textual-witness pressure.",
            "next_action": "Review witness variants without using English witnesses as basis.",
        },
        {
            "gate": "source_family_blockers_closed",
            "score_pct": pct(len(family_rows_) - len(blocked_families), len(family_rows_)),
            "status": "blocked",
            "evidence": f"{len(blocked_families)} source families are blocked or routing-only.",
            "next_action": "Close source-family blockers before authority certification.",
        },
    ]


def summarize(
    unit_rows: list[dict[str, Any]],
    family_rows_: list[dict[str, Any]],
    role_rows_: list[dict[str, Any]],
    gate_rows_: list[dict[str, Any]],
) -> dict[str, Any]:
    family_assignments = sum(int(row["packet_family_count"]) for row in unit_rows)
    blocked_family_count = sum(
        1
        for row in family_rows_
        if str(row["status"]).startswith(("blocked", "missing", "routing_only"))
    )
    return {
        "unit_count": len(unit_rows),
        "source_family_count": len(family_rows_),
        "family_assignment_count": family_assignments,
        "avg_packet_families_per_unit": mean(
            [float(row["packet_family_count"]) for row in unit_rows]
        ),
        "critical_packet_unit_count": sum(
            1 for row in unit_rows if row["packet_priority_band"] == "critical"
        ),
        "highest_packet_unit_count": sum(
            1 for row in unit_rows if row["packet_priority_band"] == "highest"
        ),
        "reception_packet_unit_count": sum(1 for row in unit_rows if row["reception_sensitive"]),
        "jewish_christian_packet_unit_count": sum(
            1 for row in unit_rows if row["jewish_christian_separation_required"]
        ),
        "textual_witness_packet_unit_count": sum(
            1 for row in unit_rows if row["textual_witness_pressure"]
        ),
        "ancient_culture_packet_unit_count": sum(
            1 for row in unit_rows if row["ancient_culture_pressure"]
        ),
        "blocked_or_routing_source_family_count": blocked_family_count,
        "reviewer_role_count": len(role_rows_),
        "reviewer_unit_assignment_count": sum(int(row["unit_count"]) for row in role_rows_),
        "gate_count": len(gate_rows_),
        "blocked_gate_count": sum(1 for row in gate_rows_ if row["status"] == "blocked"),
        "top_packet_unit": unit_rows[0]["unit_id"] if unit_rows else "",
        "top_packet_ref": unit_rows[0]["ref"] if unit_rows else "",
        "top_packet_priority_score": unit_rows[0]["packet_priority_score"] if unit_rows else 0.0,
        "status": "contextual_source_packet_roadmap_generated_not_signoff",
    }


def build_report() -> dict[str, Any]:
    data = {
        "adjudication": load_json(ADJUDICATION_PATH),
        "boundary": load_json(BOUNDARY_PATH),
        "canonical": load_json(CANONICAL_CONTEXT_PATH),
        "witness": load_json(WITNESS_PATH),
        "claim_matrix": load_json(CLAIM_MATRIX_PATH),
        "source_maturity": load_json(SOURCE_MATURITY_PATH),
        "casebook": load_json(CASEBOOK_PATH),
    }
    units = build_unit_rows(data)
    families = family_rows(units)
    roles = role_rows(units, families)
    gates = gate_rows(units, families, data)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "contextual source packet roadmap generated; not reviewer signoff",
        "source_paths": {
            "adjudication": str(ADJUDICATION_PATH.relative_to(ROOT)),
            "boundary": str(BOUNDARY_PATH.relative_to(ROOT)),
            "canonical_context": str(CANONICAL_CONTEXT_PATH.relative_to(ROOT)),
            "witness": str(WITNESS_PATH.relative_to(ROOT)),
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
            "source_maturity": str(SOURCE_MATURITY_PATH.relative_to(ROOT)),
            "casebook": str(CASEBOOK_PATH.relative_to(ROOT)),
        },
        "policy": {
            "translation_basis": "Hebrew source packets are primary.",
            "whole_tanakh": "Current whole-Tanakh evidence is surface-form only.",
            "witnesses": "Witnesses require labeled notes and cannot override Hebrew silently.",
            "reception": "Jewish and Christian reception packets must remain separate.",
            "authority": "Packets are reviewer workload, not signoff.",
        },
        "summary": summarize(units, families, roles, gates),
        "unit_rows": units,
        "source_family_rows": families,
        "review_role_rows": roles,
        "gate_rows": gates,
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
    left = 300
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
    families = report["source_family_rows"]
    roles = report["review_role_rows"]
    gates = report["gate_rows"]
    top_units = [
        [
            row["rank"],
            f"<strong>{esc(row['ref'])}</strong><br><span>{esc(row['unit_id'])}</span>",
            f"{row['packet_priority_score']:.2f}",
            row["packet_priority_band"],
            row["packet_family_count"],
            "; ".join(row["packet_families"][:10]),
            "; ".join(row["required_frames"][:8]),
        ]
        for row in units[:20]
    ]
    family_table = [
        [
            row["label"],
            row["status"],
            row["unit_count"],
            row["highest_priority_unit_count"],
            row["top_ref"],
            "; ".join(row["review_roles"]),
            row["authority_boundary"],
        ]
        for row in families
    ]
    role_table = [
        [
            row["reviewer_role"],
            row["unit_count"],
            row["family_assignment_count"],
            row["highest_priority_unit_count"],
            row["authority_boundary"],
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

    # Ruff's formatter rewrites nested dict-access f-strings here into Python
    # 3.12-only quote syntax. The project currently compiles under Python 3.11.
    # fmt: off
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Contextual Source Packet Roadmap</title>
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
    td span {{ color: var(--muted); font-size: 12px; }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AlephTav Contextual Source Packet Roadmap</h1>
    <p class="lede">
      Unit-level roadmap for building the source packets required before
      contextual, cultural, whole-Tanakh, Jewish, Christian, academic, textual,
      and model-assisted claims can be considered for translation review.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}. Not reviewer signoff.</p>
  </header>
  <main>
    <section>
      <h2>Packet Summary</h2>
      {
        metric_cards(
            [
                (
                    "Units",
                    fmt_int(summary["unit_count"]),
                    f'{fmt_int(summary["family_assignment_count"])} source-family assignments.',
                ),
                (
                    "Avg Packets",
                    f'{summary["avg_packet_families_per_unit"]:.2f}',
                    "Mean packet families needed per expanded unit.",
                ),
                (
                    "Reception",
                    fmt_int(summary["reception_packet_unit_count"]),
                    (
                        f'{fmt_int(summary["jewish_christian_packet_unit_count"])} '
                        "require separated lanes."
                    ),
                ),
                (
                    "Culture",
                    fmt_int(summary["ancient_culture_packet_unit_count"]),
                    "Units needing ancient-cultural context packets.",
                ),
                (
                    "Textual",
                    fmt_int(summary["textual_witness_packet_unit_count"]),
                    "Units carrying textual-witness pressure.",
                ),
                (
                    "Blocked Families",
                    fmt_int(summary["blocked_or_routing_source_family_count"]),
                    f'{fmt_int(summary["blocked_gate_count"])} packet gates blocked.',
                ),
                (
                    "Review Roles",
                    fmt_int(summary["reviewer_role_count"]),
                    f'{fmt_int(summary["reviewer_unit_assignment_count"])} unit-role assignments.',
                ),
                (
                    "Top Unit",
                    summary["top_packet_ref"],
                    f'Score {summary["top_packet_priority_score"]:.2f}.',
                ),
            ]
        )
    }
      <div class="warning">
        This roadmap is a workload and provenance control. It does not approve
        any interpretation, does not merge Jewish and Christian reception, and
        does not allow cultural or witness evidence to override Hebrew source
        tokens.
      </div>
    </section>

    <section>
      <h2>Source Family Load</h2>
      <div class="chart">{
        svg_bar_chart(
            families,
            label_key="label",
            value_key="unit_count",
            aria_label="Source packet units by source family",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_bar_chart(
            families,
            label_key="label",
            value_key="highest_priority_unit_count",
            aria_label="Highest-priority source packet units by family",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            ["Family", "Status", "Units", "Priority", "Top Unit", "Roles", "Boundary"],
            family_table,
        )
    }
    </section>

    <section>
      <h2>Reviewer Workload</h2>
      <div class="chart">{
        svg_bar_chart(
            roles,
            label_key="reviewer_role",
            value_key="unit_count",
            aria_label="Reviewer workload units",
            color="#7c5b2f",
        )
    }</div>
      {table(["Role", "Units", "Family Assignments", "Priority Units", "Boundary"], role_table)}
    </section>

    <section>
      <h2>Priority Packet Queue</h2>
      {
        table(
            [
                "Rank",
                "Unit",
                "Score",
                "Band",
                "Families",
                "Packet Families",
                "Required Frames",
            ],
            top_units,
        )
    }
    </section>

    <section>
      <h2>Packet Gates</h2>
      {table(["Gate", "Score", "Status", "Evidence", "Next Action"], gate_table)}
    </section>
  </main>
</body>
</html>
"""
    # fmt: on


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate contextual source packet roadmap.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--family-csv-output", type=Path, default=DEFAULT_FAMILY_CSV_OUTPUT)
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
    family_csv_output = resolve(args.family_csv_output)
    role_csv_output = resolve(args.role_csv_output)
    gate_csv_output = resolve(args.gate_csv_output)
    html_output = resolve(args.html_output)
    write_json(json_output, report)
    write_csv(unit_csv_output, report["unit_rows"])
    write_csv(family_csv_output, report["source_family_rows"])
    write_csv(role_csv_output, report["review_role_rows"])
    write_csv(gate_csv_output, report["gate_rows"])
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(render_html(report), encoding="utf-8")
    print(json_output)
    print(unit_csv_output)
    print(family_csv_output)
    print(role_csv_output)
    print(gate_csv_output)
    print(html_output)


if __name__ == "__main__":
    main()
