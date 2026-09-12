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

RECEPTION_DIVERGENCE_PATH = REPORT_ROOT / "reception_divergence_atlas.json"
CORPUS_RECEPTION_SIGNAL_PATH = REPORT_ROOT / "corpus_reception_signal_atlas.json"
SOURCE_PACKET_PATH = REPORT_ROOT / "contextual_source_packet_roadmap.json"
BIBLIOGRAPHY_PATH = REPORT_ROOT / "doctoral_bibliography_provenance.json"
SOURCE_VERIFICATION_PATH = REPORT_ROOT / "doctoral_source_verification.json"
PRIORITY_DOSSIER_PATH = REPORT_ROOT / "doctoral_priority_dossier_atlas.json"
REVIEW_WORKBOOK_PATH = REPORT_ROOT / "contextual_review_signoff_workbook.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "reception_source_packet_workbook.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "reception_source_packet_units.csv"
DEFAULT_PACKET_CSV_OUTPUT = REPORT_ROOT / "reception_source_packet_rows.csv"
DEFAULT_SOURCE_CSV_OUTPUT = REPORT_ROOT / "reception_source_packet_sources.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "reception_source_packet_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "reception_source_packet_workbook.html"

LANES: dict[str, dict[str, Any]] = {
    "jewish_reception": {
        "label": "Jewish Reception",
        "source_family": "jewish_reception_sources",
        "review_roles": ["theology"],
        "required_note_fields": [
            "Jewish source citation",
            "period and tradition frame",
            "plain-sense versus reception distinction",
            "translation-impact decision",
            "reviewer signoff",
        ],
        "review_questions": [
            "Which Jewish sources are actually cited, and what period/tradition do they represent?",
            "Does the Jewish reception note affect English wording, or only a labeled note?",
            "Has the note avoided importing later Christian reception into the Jewish lane?",
        ],
    },
    "christian_reception": {
        "label": "Christian Reception",
        "source_family": "christian_reception_sources",
        "review_roles": ["theology"],
        "required_note_fields": [
            "Christian source citation",
            "New Testament, patristic, confessional, or modern frame",
            "quote/allusion/doctrine distinction",
            "translation-impact decision",
            "reviewer signoff",
        ],
        "review_questions": [
            (
                "Which Christian sources are actually cited, and are quotation/allusion "
                "claims separated?"
            ),
            "Does the Christian reception note affect English wording, or only a labeled note?",
            (
                "Has the note avoided retrojecting later Christian theology into "
                "Hebrew-source wording?"
            ),
        ],
    },
    "academic_comparison": {
        "label": "Academic Critical Comparison",
        "source_family": "academic_critical_comparison",
        "review_roles": ["Hebrew", "theology"],
        "required_note_fields": [
            "Critical source citation",
            "philological or historical claim",
            "majority/minority or uncertainty marker",
            "translation-impact decision",
            "reviewer signoff",
        ],
        "review_questions": [
            "Which critical sources are cited, and what claim is philological versus historical?",
            "Does academic comparison clarify the Hebrew, the reception history, or both?",
            "Is the conclusion scoped as evidence rather than automatic wording authority?",
        ],
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
    return round(float(part) / float(total) * 100.0, 2)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if key in row}


def candidates_for_family(
    *,
    family: dict[str, Any],
    bibliography_by_source: dict[str, dict[str, Any]],
    verification_by_source: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for source_id in family.get("candidate_ids", []):
        bibliography = bibliography_by_source.get(str(source_id), {})
        verification = verification_by_source.get(str(source_id), {})
        rows.append(
            {
                "source_id": source_id,
                "label": bibliography.get("label", source_id),
                "source_class": bibliography.get("source_class", ""),
                "tier": bibliography.get("tier", ""),
                "language": bibliography.get("language", ""),
                "license_or_access": bibliography.get("license_or_access", ""),
                "license_risk": bibliography.get(
                    "license_risk",
                    family.get("best_license_risk", ""),
                ),
                "machine_readable": bool(bibliography.get("machine_readable", False)),
                "official_url": bibliography.get(
                    "official_url",
                    verification.get("official_url", ""),
                ),
                "reachable": bool(verification.get("reachable", False)),
                "verification_status": verification.get("verification_status", "not_verified"),
                "license_claim_status": verification.get("license_claim_status", ""),
                "authority_status": bibliography.get("authority_status", ""),
                "generation_policy": bibliography.get("generation_policy", ""),
            }
        )
    return rows


def packet_status(candidate_rows: list[dict[str, Any]]) -> str:
    if not candidate_rows:
        return "blocked_no_candidate_source"
    if any(row["reachable"] for row in candidate_rows):
        return "source_candidates_reachable_review_unsigned"
    return "blocked_source_verification_needed"


def unit_status(row: dict[str, Any]) -> str:
    if row.get("jewish_christian_separation_required"):
        return "split_lane_source_packets_ready_for_review"
    return "reception_packet_watchlist"


def required_lane_ids(row: dict[str, Any]) -> list[str]:
    lane_ids = ["jewish_reception", "christian_reception"]
    if row.get("has_academic_comparison_frame") or "academic_critical_comparison" in row.get(
        "required_frames",
        [],
    ):
        lane_ids.append("academic_comparison")
    return lane_ids


def build_unit_rows(
    *,
    reception: dict[str, Any],
    signals_by_unit: dict[str, dict[str, Any]],
    source_packets_by_unit: dict[str, dict[str, Any]],
    priority_by_unit: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for row in reception.get("unit_rows", []):
        if not row.get("jewish_christian_separation_required"):
            continue
        unit_id = str(row["unit_id"])
        signal = signals_by_unit.get(unit_id, {})
        source_packet = source_packets_by_unit.get(unit_id, {})
        priority = priority_by_unit.get(unit_id, {})
        rows.append(
            {
                "rank": len(rows) + 1,
                "unit_id": unit_id,
                "ref": row["ref"],
                "psalm_id": row["psalm_id"],
                "source_hebrew": row.get("source_hebrew", ""),
                "reception_divergence_priority_score": row["reception_divergence_priority_score"],
                "boundary_risk_score": row["boundary_risk_score"],
                "claim_risk_score": row["claim_risk_score"],
                "packet_priority_score": row["packet_priority_score"],
                "doctoral_dossier_priority_score": priority.get(
                    "doctoral_dossier_priority_score",
                    "",
                ),
                "unit_authority_score_pct": priority.get("unit_authority_score_pct", ""),
                "mean_english_witness_divergence_pct": row["mean_english_witness_divergence_pct"],
                "required_frames": row.get("required_frames", []),
                "required_review_roles": row.get("required_review_roles", []),
                "case_family_labels": row.get("case_family_labels", []),
                "domains": row.get("domains", []),
                "cultural_domain_labels": row.get("cultural_domain_labels", []),
                "signal_ids": signal.get("signal_ids", []),
                "signal_labels": signal.get("signal_labels", []),
                "report_flags": signal.get("report_flags", []),
                "top_token_labels": signal.get("top_token_labels", []),
                "top_anchor_form_labels": row.get("top_anchor_form_labels", []),
                "kjv_excerpt": signal.get("kjv_excerpt", ""),
                "asv_excerpt": signal.get("asv_excerpt", ""),
                "web_excerpt": signal.get("web_excerpt", ""),
                "packet_families": row.get("packet_families", []),
                "source_packet_family_count": source_packet.get("packet_family_count", ""),
                "required_lane_ids": required_lane_ids(row),
                "packet_count": len(required_lane_ids(row)),
                "status": unit_status(row),
                "authority_boundary": row.get(
                    "authority_boundary",
                    "Separated reception lanes route review only.",
                ),
            }
        )
    return sorted(
        rows,
        key=lambda item: float(item["reception_divergence_priority_score"]),
        reverse=True,
    )


def build_packet_rows(
    *,
    unit_rows: list[dict[str, Any]],
    source_families: dict[str, dict[str, Any]],
    bibliography_by_source: dict[str, dict[str, Any]],
    verification_by_source: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for unit in unit_rows:
        for lane_id in unit["required_lane_ids"]:
            lane = LANES[lane_id]
            family = source_families.get(lane["source_family"], {})
            candidate_rows = candidates_for_family(
                family=family,
                bibliography_by_source=bibliography_by_source,
                verification_by_source=verification_by_source,
            )
            rows.append(
                {
                    "packet_id": f"reception_source.{unit['unit_id']}.{lane_id}",
                    "unit_id": unit["unit_id"],
                    "ref": unit["ref"],
                    "lane_id": lane_id,
                    "lane_label": lane["label"],
                    "priority_score": unit["reception_divergence_priority_score"],
                    "source_family": lane["source_family"],
                    "candidate_source_ids": [row["source_id"] for row in candidate_rows],
                    "reachable_candidate_count": sum(
                        1 for row in candidate_rows if row["reachable"]
                    ),
                    "candidate_count": len(candidate_rows),
                    "best_license_risk": family.get("best_license_risk", ""),
                    "review_roles": lane["review_roles"],
                    "required_note_fields": lane["required_note_fields"],
                    "review_questions": lane["review_questions"],
                    "hebrew_controls": [
                        "translation_text_must_use_hebrew_source_basis",
                        "reception_claims_must_stay_out_of_translation_text",
                        "jewish_and_christian_reception_must_be_separate",
                    ],
                    "context_inputs": {
                        "required_frames": unit["required_frames"],
                        "signal_ids": unit["signal_ids"],
                        "case_family_labels": unit["case_family_labels"],
                        "top_anchor_form_labels": unit["top_anchor_form_labels"],
                        "witness_divergence_pct": unit["mean_english_witness_divergence_pct"],
                    },
                    "status": packet_status(candidate_rows),
                    "authority_boundary": (
                        "This packet can route source work and reviewer questions only; "
                        "it cannot authorize translation wording without Hebrew, theology, "
                        "and release signoff."
                    ),
                }
            )
    return rows


def build_source_rows(
    *,
    packet_rows: list[dict[str, Any]],
    source_families: dict[str, dict[str, Any]],
    bibliography_by_source: dict[str, dict[str, Any]],
    verification_by_source: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    packet_counts_by_lane_source: Counter[tuple[str, str]] = Counter()
    for packet in packet_rows:
        for source_id in packet["candidate_source_ids"]:
            packet_counts_by_lane_source[(packet["lane_id"], source_id)] += 1

    rows = []
    for lane_id, lane in LANES.items():
        family = source_families.get(lane["source_family"], {})
        for source in candidates_for_family(
            family=family,
            bibliography_by_source=bibliography_by_source,
            verification_by_source=verification_by_source,
        ):
            rows.append(
                {
                    "lane_id": lane_id,
                    "lane_label": lane["label"],
                    "source_family": lane["source_family"],
                    "source_id": source["source_id"],
                    "label": source["label"],
                    "source_class": source["source_class"],
                    "tier": source["tier"],
                    "language": source["language"],
                    "license_or_access": source["license_or_access"],
                    "license_risk": source["license_risk"],
                    "machine_readable": source["machine_readable"],
                    "reachable": source["reachable"],
                    "verification_status": source["verification_status"],
                    "license_claim_status": source["license_claim_status"],
                    "authority_status": source["authority_status"],
                    "generation_policy": source["generation_policy"],
                    "packet_count": packet_counts_by_lane_source[(lane_id, source["source_id"])],
                    "official_url": source["official_url"],
                }
            )
    return rows


def build_gate_rows(
    *,
    summary_source_verification: dict[str, Any],
    review_summary: dict[str, Any],
    packet_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_count = len({row["source_id"] for row in source_rows})
    reachable_count = len({row["source_id"] for row in source_rows if row["reachable"]})
    packet_count = len(packet_rows)
    reachable_packet_count = sum(1 for row in packet_rows if row["reachable_candidate_count"])
    completed_reviews = int(review_summary.get("completed_review_row_count", 0))
    total_reviews = int(review_summary.get("total_review_row_count", 0))
    return [
        {
            "gate": "separated_lane_packets",
            "score_pct": 100.0 if packet_count else 0.0,
            "status": "generated",
            "evidence": f"{packet_count} Jewish, Christian, and academic packet rows generated.",
            "next_action": "Attach source notes and reviewer decisions to each packet row.",
        },
        {
            "gate": "source_candidate_reachability",
            "score_pct": pct(reachable_count, source_count),
            "status": "partial",
            "evidence": (
                f"{reachable_count} of {source_count} distinct lane source candidates "
                "are reachable."
            ),
            "next_action": "Resolve unreachable/no-URL candidates before source approval.",
        },
        {
            "gate": "packet_candidate_reachability",
            "score_pct": pct(reachable_packet_count, packet_count),
            "status": "partial",
            "evidence": (
                f"{reachable_packet_count} of {packet_count} packets have at least "
                "one reachable candidate source."
            ),
            "next_action": (
                "Add official source URLs or manual bibliography records for blocked packets."
            ),
        },
        {
            "gate": "source_approval",
            "score_pct": 0.0,
            "status": "blocked",
            "evidence": (
                f"{summary_source_verification.get('source_approval_count', 0)} source "
                "approvals are recorded."
            ),
            "next_action": (
                "Complete license/provenance review before using reception notes as evidence."
            ),
        },
        {
            "gate": "human_reception_signoff",
            "score_pct": pct(completed_reviews, total_reviews),
            "status": "blocked",
            "evidence": (
                f"{completed_reviews} of {total_reviews} review workbook rows are completed."
            ),
            "next_action": (
                "Collect theology, Hebrew, and release decisions with reviewer identity."
            ),
        },
    ]


def summarize(
    *,
    unit_rows: list[dict[str, Any]],
    packet_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    lane_counts = Counter(row["lane_id"] for row in packet_rows)
    status_counts = Counter(row["status"] for row in packet_rows)
    source_ids = {row["source_id"] for row in source_rows}
    reachable_ids = {row["source_id"] for row in source_rows if row["reachable"]}
    machine_readable_ids = {row["source_id"] for row in source_rows if row["machine_readable"]}
    blocked_gates = [row["gate"] for row in gate_rows if row["status"] == "blocked"]
    top = unit_rows[0] if unit_rows else {}
    return {
        "split_lane_unit_count": len(unit_rows),
        "packet_count": len(packet_rows),
        "jewish_packet_count": lane_counts["jewish_reception"],
        "christian_packet_count": lane_counts["christian_reception"],
        "academic_packet_count": lane_counts["academic_comparison"],
        "distinct_candidate_source_count": len(source_ids),
        "reachable_candidate_source_count": len(reachable_ids),
        "machine_readable_candidate_source_count": len(machine_readable_ids),
        "packet_with_reachable_candidate_count": sum(
            1 for row in packet_rows if row["reachable_candidate_count"]
        ),
        "packet_with_reachable_candidate_pct": pct(
            sum(1 for row in packet_rows if row["reachable_candidate_count"]),
            len(packet_rows),
        ),
        "source_approval_count": 0,
        "completed_packet_review_count": 0,
        "blocked_gate_count": len(blocked_gates),
        "blocked_gates": blocked_gates,
        "packet_status_counts": dict(status_counts.most_common()),
        "lane_packet_counts": dict(lane_counts.most_common()),
        "top_ref": top.get("ref", ""),
        "top_unit": top.get("unit_id", ""),
        "top_priority_score": top.get("reception_divergence_priority_score", 0),
        "authority_verdict": (
            "reception_source_packets_not_authority: separated Jewish, Christian, and "
            "academic packets route source acquisition and review only; they do not "
            "approve interpretation, translation wording, model training data, or release."
        ),
    }


def visual_data(
    *,
    unit_rows: list[dict[str, Any]],
    packet_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    family_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    source_status_counts = Counter(row["verification_status"] for row in source_rows)
    for unit in unit_rows:
        family_counts.update(unit["case_family_labels"])
        signal_counts.update(unit["signal_ids"])
    return {
        "top_unit_rows": [
            {
                "label": f"{row['ref']} ({row['unit_id']})",
                "value": row["reception_divergence_priority_score"],
            }
            for row in unit_rows[:15]
        ],
        "lane_packet_rows": [
            {"label": LANES[lane_id]["label"], "value": count}
            for lane_id, count in Counter(row["lane_id"] for row in packet_rows).most_common()
        ],
        "case_family_rows": [
            {"label": label, "value": count} for label, count in family_counts.most_common(12)
        ],
        "signal_rows": [
            {"label": label, "value": count} for label, count in signal_counts.most_common(12)
        ],
        "source_status_rows": [
            {"label": label, "value": count} for label, count in source_status_counts.most_common()
        ],
    }


def build_workbook() -> dict[str, Any]:
    reception = load_json(RECEPTION_DIVERGENCE_PATH)
    signals = load_json(CORPUS_RECEPTION_SIGNAL_PATH)
    source_packets = load_json(SOURCE_PACKET_PATH)
    bibliography = load_json(BIBLIOGRAPHY_PATH)
    verification = load_json(SOURCE_VERIFICATION_PATH)
    priority = load_json(PRIORITY_DOSSIER_PATH)
    review = load_json(REVIEW_WORKBOOK_PATH)

    signals_by_unit = by_key(signals.get("unit_rows", []), "unit_id")
    source_packets_by_unit = by_key(source_packets.get("unit_rows", []), "unit_id")
    priority_by_unit = by_key(priority.get("unit_rows", []), "unit_id")
    source_families = by_key(bibliography.get("source_family_rows", []), "source_family")
    bibliography_by_source = by_key(bibliography.get("bibliography_rows", []), "source_id")
    verification_by_source = by_key(verification.get("source_rows", []), "source_id")

    unit_rows = build_unit_rows(
        reception=reception,
        signals_by_unit=signals_by_unit,
        source_packets_by_unit=source_packets_by_unit,
        priority_by_unit=priority_by_unit,
    )
    packet_rows = build_packet_rows(
        unit_rows=unit_rows,
        source_families=source_families,
        bibliography_by_source=bibliography_by_source,
        verification_by_source=verification_by_source,
    )
    source_rows = build_source_rows(
        packet_rows=packet_rows,
        source_families=source_families,
        bibliography_by_source=bibliography_by_source,
        verification_by_source=verification_by_source,
    )
    gate_rows = build_gate_rows(
        summary_source_verification=verification["summary"],
        review_summary=review["summary"],
        packet_rows=packet_rows,
        source_rows=source_rows,
    )
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated separated reception source packet workbook; unsigned",
        "source_paths": {
            "reception_divergence": rel(RECEPTION_DIVERGENCE_PATH),
            "corpus_reception_signal": rel(CORPUS_RECEPTION_SIGNAL_PATH),
            "source_packets": rel(SOURCE_PACKET_PATH),
            "bibliography": rel(BIBLIOGRAPHY_PATH),
            "source_verification": rel(SOURCE_VERIFICATION_PATH),
            "priority_dossier": rel(PRIORITY_DOSSIER_PATH),
            "review_workbook": rel(REVIEW_WORKBOOK_PATH),
        },
        "policy": {
            "translation_basis": "Hebrew source tokens and signed alignment review remain primary.",
            "reception_boundary": (
                "Jewish, Christian, and academic packets must remain separated and labeled."
            ),
            "authority_boundary": (
                "Packet rows are source-acquisition and reviewer workload only until citations, "
                "license/provenance review, reviewer identity, decisions, and release "
                "signoff exist."
            ),
        },
        "summary": summarize(
            unit_rows=unit_rows,
            packet_rows=packet_rows,
            source_rows=source_rows,
            gate_rows=gate_rows,
        ),
        "unit_rows": unit_rows,
        "packet_rows": packet_rows,
        "source_rows": source_rows,
        "gate_rows": gate_rows,
        "visual_data": visual_data(
            unit_rows=unit_rows,
            packet_rows=packet_rows,
            source_rows=source_rows,
        ),
    }


def bar_rows(rows: list[dict[str, Any]], *, label: str, value: str, max_rows: int = 20) -> str:
    if not rows:
        return ""
    max_value = max(float(row[value] or 0) for row in rows[:max_rows]) or 1.0
    parts = []
    for row in rows[:max_rows]:
        width = max(2.0, float(row[value] or 0) / max_value * 100.0)
        parts.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{esc(row[label])}</div>
              <div class="bar-track"><div class="bar" style="width:{width:.2f}%"></div></div>
              <div class="bar-value">{esc(row[value])}</div>
            </div>"""
        )
    return "\n".join(parts)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(workbook: dict[str, Any]) -> str:
    summary = workbook["summary"]
    unit_rows = [
        [
            row["rank"],
            row["ref"],
            f"{row['reception_divergence_priority_score']:.2f}",
            f"{row['boundary_risk_score']:.2f}",
            f"{row['mean_english_witness_divergence_pct']:.2f}%",
            "; ".join(row["signal_ids"][:5]),
            "; ".join(row["case_family_labels"][:5]),
            "; ".join(row["required_lane_ids"]),
        ]
        for row in workbook["unit_rows"][:20]
    ]
    packet_rows = [
        [
            row["packet_id"],
            row["ref"],
            row["lane_label"],
            row["candidate_count"],
            row["reachable_candidate_count"],
            row["best_license_risk"],
            row["status"],
        ]
        for row in workbook["packet_rows"][:60]
    ]
    source_rows = [
        [
            row["lane_label"],
            row["source_id"],
            row["label"],
            row["license_risk"],
            "yes" if row["reachable"] else "no",
            row["verification_status"],
            row["packet_count"],
        ]
        for row in workbook["source_rows"]
    ]
    gate_rows = [
        [
            row["gate"],
            f"{row['score_pct']:.2f}%",
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in workbook["gate_rows"]
    ]
    visual = workbook["visual_data"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Reception Source Packet Workbook</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      margin: 32px;
      color: #17201b;
    }}
    h1, h2 {{ color: #173d3f; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px;
    }}
    .card {{
      border: 1px solid #ccd7d2;
      border-radius: 8px;
      padding: 14px;
      background: #f8fbfa;
    }}
    .metric {{ font-size: 1.8rem; font-weight: 700; }}
    .warning {{
      border-left: 5px solid #9b3d3d;
      padding: 12px 14px;
      background: #fff5f4;
      margin: 18px 0;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(180px, 1.1fr) 3fr 80px;
      gap: 10px;
      align-items: center;
      margin: 8px 0;
    }}
    .bar-track {{
      height: 18px;
      background: #e7ece9;
      border-radius: 4px;
      overflow: hidden;
    }}
    .bar {{ height: 100%; background: #2f6f73; }}
    table {{ border-collapse: collapse; width: 100%; margin: 18px 0 30px; font-size: 0.9rem; }}
    th, td {{ border: 1px solid #d7dfdc; padding: 7px 8px; vertical-align: top; }}
    th {{ background: #edf4f2; text-align: left; }}
    td {{ max-width: 420px; }}
  </style>
</head>
<body>
  <h1>Reception Source Packet Workbook</h1>
  <p>
    Separated Jewish, Christian, and academic source-packet workload for
    reception-sensitive Psalms units. This is hard-data routing from existing
    reports; it is not interpretive adjudication or translation authority.
  </p>
  <div class="warning">{esc(summary["authority_verdict"])}</div>
  <section class="grid">
    <div class="card">
      <div class="metric">{fmt_int(summary["split_lane_unit_count"])}</div>
      <p>split-lane units</p>
    </div>
    <div class="card">
      <div class="metric">{fmt_int(summary["packet_count"])}</div>
      <p>Jewish, Christian, and academic packets</p>
    </div>
    <div class="card">
      <div class="metric">{fmt_int(summary["distinct_candidate_source_count"])}</div>
      <p>distinct candidate source IDs</p>
    </div>
    <div class="card">
      <div class="metric">{summary["packet_with_reachable_candidate_pct"]:.2f}%</div>
      <p>packets with reachable source candidates</p>
    </div>
    <div class="card">
      <div class="metric">{fmt_int(summary["source_approval_count"])}</div>
      <p>source approvals recorded</p>
    </div>
    <div class="card">
      <div class="metric">{fmt_int(summary["blocked_gate_count"])}</div>
      <p>blocked gates</p>
    </div>
  </section>

  <h2>Top Reception Packet Units</h2>
  {bar_rows(visual["top_unit_rows"], label="label", value="value")}

  <h2>Packet Workload by Lane</h2>
  {bar_rows(visual["lane_packet_rows"], label="label", value="value")}

  <h2>Case Families</h2>
  {bar_rows(visual["case_family_rows"], label="label", value="value")}

  <h2>Split-Lane Units</h2>
  {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Boundary Risk",
                "Witness Divergence",
                "Signals",
                "Case Families",
                "Packets",
            ],
            unit_rows,
        )
    }

  <h2>Packet Rows</h2>
  {
        table(
            [
                "Packet",
                "Ref",
                "Lane",
                "Candidates",
                "Reachable",
                "Best License Risk",
                "Status",
            ],
            packet_rows,
        )
    }

  <h2>Source Candidates</h2>
  {
        table(
            [
                "Lane",
                "Source ID",
                "Label",
                "License Risk",
                "Reachable",
                "Verification",
                "Packets",
            ],
            source_rows,
        )
    }

  <h2>Gates</h2>
  {table(["Gate", "Score", "Status", "Evidence", "Next Action"], gate_rows)}
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate separated reception source packet workbook."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--packet-csv-output", type=Path, default=DEFAULT_PACKET_CSV_OUTPUT)
    parser.add_argument("--source-csv-output", type=Path, default=DEFAULT_SOURCE_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workbook = build_workbook()
    write_json(args.json_output, workbook)
    write_csv(args.unit_csv_output, workbook["unit_rows"])
    write_csv(args.packet_csv_output, workbook["packet_rows"])
    write_csv(args.source_csv_output, workbook["source_rows"])
    write_csv(args.gate_csv_output, workbook["gate_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(workbook), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.packet_csv_output}")
    print(f"Wrote {args.source_csv_output}")
    print(f"Wrote {args.gate_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
