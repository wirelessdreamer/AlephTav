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

SOURCE_PATHS = {
    "defense_exhibit": REPORT_ROOT / "doctoral_defense_exhibit_pack.json",
    "contextual_source_packets": REPORT_ROOT / "contextual_source_packet_roadmap.json",
    "canonical_cross_reference": REPORT_ROOT / "canonical_cross_reference_atlas.json",
    "cultural_atlas": REPORT_ROOT / "cultural_historical_domain_atlas.json",
    "divine_name_policy": REPORT_ROOT / "divine_name_policy_report.json",
    "superscription_context": REPORT_ROOT / "superscription_context_report.json",
    "poetic_rhetorical": REPORT_ROOT / "poetic_rhetorical_pressure_atlas.json",
    "witness_divergence": REPORT_ROOT / "witness_divergence_report.json",
    "interpretive_control": REPORT_ROOT / "interpretive_tradition_control_matrix.json",
    "source_ladder": REPORT_ROOT / "source_authority_ladder_matrix.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "hebrew_token_defense_matrix.json"
DEFAULT_TOKEN_CSV_OUTPUT = REPORT_ROOT / "hebrew_token_defense_tokens.csv"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "hebrew_token_defense_units.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "hebrew_token_defense_matrix.html"
CRITICAL_TOKEN_SCORE = 180.0

AUTHORITY_POLICY = (
    "The Hebrew token defense matrix is an evidence index for reviewer analysis. "
    "It traces high-risk exhibit units down to token-level Hebrew, morphology, "
    "whole-Tanakh anchors, cultural domains, and control flags, but it does not "
    "approve wording, sources, interpretation, model output, or release status."
)


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


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "yes", "1"}
    return bool(value)


def listify(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        if "; " in value:
            return [part.strip() for part in value.split("; ") if part.strip()]
        if value:
            return [value]
    return []


def list_join(values: list[Any], limit: int | None = None) -> str:
    if limit is not None:
        values = values[:limit]
    return "; ".join(str(value) for value in values if str(value))


def by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key)}


def unit_path(unit_id: str) -> Path:
    psalm_id = unit_id.split(".")[0]
    return CONTENT_ROOT / psalm_id / f"{unit_id}.json"


def load_unit(unit_id: str) -> dict[str, Any]:
    path = unit_path(unit_id)
    if not path.exists():
        return {}
    return load_json(path)


def index_by_token(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    indexed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        token_id = str(row.get("token_id", ""))
        if token_id:
            indexed[token_id].append(row)
    return indexed


def unit_flag_token_ids(data: dict[str, dict[str, Any]], artifact: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for row in data[artifact].get("unit_rows", []):
        token_ids = {str(token_id) for token_id in row.get("token_ids", []) if token_id}
        if token_ids:
            result[str(row["unit_id"])] = token_ids
    return result


def build_indexes(data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "exhibit_by_unit": by_key(data["defense_exhibit"].get("unit_rows", []), "unit_id"),
        "packet_by_unit": by_key(data["contextual_source_packets"].get("unit_rows", []), "unit_id"),
        "control_by_unit": by_key(data["interpretive_control"].get("unit_rows", []), "unit_id"),
        "source_by_unit": by_key(data["source_ladder"].get("unit_rows", []), "unit_id"),
        "witness_by_unit": by_key(data["witness_divergence"].get("unit_rows", []), "unit_id"),
        "poetic_by_unit": by_key(data["poetic_rhetorical"].get("unit_rows", []), "unit_id"),
        "anchor_by_token": by_key(
            data["canonical_cross_reference"].get("anchor_rows", []), "token_id"
        ),
        "culture_by_token": index_by_token(data["cultural_atlas"].get("token_rows", [])),
        "divine_token_ids": unit_flag_token_ids(data, "divine_name_policy"),
        "superscription_token_ids": unit_flag_token_ids(data, "superscription_context"),
    }


def token_control_flags(
    token: dict[str, Any],
    unit: dict[str, Any],
    exhibit: dict[str, Any],
    anchor: dict[str, Any],
    culture_rows: list[dict[str, Any]],
    is_divine: bool,
    is_superscription: bool,
) -> list[str]:
    flags = ["cite_token_id_evidence_for_lexical_claims"]
    missing = set(token.get("missing_enrichments", []))
    compiler = token.get("compiler_features", {})
    if anchor:
        flags.append("whole_tanakh_surface_anchor_is_context_not_lemma_proof")
    if culture_rows:
        flags.append("cultural_domain_claim_requires_source_note")
    if is_divine or compiler.get("divine_name"):
        flags.append("divine_name_policy_review_required")
    if is_superscription:
        flags.append("superscription_context_is_review_input_not_authorship_proof")
    if "macula:semantic_role" in missing:
        flags.append("semantic_role_missing")
    if "macula:referent" in missing:
        flags.append("referent_missing")
    if "macula:syntax_role" in missing:
        flags.append("syntax_role_missing")
    if "oshb:stem" in missing:
        flags.append("stem_missing")
    if compiler.get("construct_state"):
        flags.append("construct_chain_requires_alignment_review")
    if compiler.get("suffix_pronoun"):
        flags.append("suffix_pronoun_requires_referent_review")
    if boolish(exhibit.get("translation_text_forbidden_reception_claim")):
        flags.append("reception_claim_must_not_enter_translation_text")
    if boolish(exhibit.get("textual_witness_pressure")):
        flags.append("witness_variants_must_not_override_hebrew_silently")
    if boolish(exhibit.get("ancient_culture_pressure")):
        flags.append("ancient_culture_claim_requires_tagged_rationale")
    if unit.get("status") != "reviewed":
        flags.append("unit_not_reviewed")
    return sorted(set(flags))


def token_score(
    token: dict[str, Any],
    exhibit: dict[str, Any],
    anchor: dict[str, Any],
    culture_rows: list[dict[str, Any]],
    is_divine: bool,
    is_superscription: bool,
    flags: list[str],
) -> float:
    compiler = token.get("compiler_features", {})
    score = 0.0
    score += as_float(exhibit.get("defense_exhibit_score")) * 0.025
    score += as_float(anchor.get("anchor_score")) * 1.25
    score += int(anchor.get("outside_psalms_count") or 0) ** 0.5
    score += len(culture_rows) * 18
    score += len(token.get("missing_enrichments", [])) * 4
    score += 30 if is_divine or compiler.get("divine_name") else 0
    score += 18 if is_superscription else 0
    score += 12 if compiler.get("construct_state") else 0
    score += 12 if compiler.get("suffix_pronoun") else 0
    score += 10 if token.get("part_of_speech") == "verb" else 0
    score += 10 if boolish(exhibit.get("jewish_christian_separation_required")) else 0
    score += 8 if boolish(exhibit.get("textual_witness_pressure")) else 0
    score += 8 if boolish(exhibit.get("ancient_culture_pressure")) else 0
    score += len(flags) * 2
    return round(score, 2)


def build_token_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    indexes = build_indexes(data)
    token_rows: list[dict[str, Any]] = []
    for exhibit in data["defense_exhibit"].get("unit_rows", []):
        unit_id = str(exhibit["unit_id"])
        unit = load_unit(unit_id)
        if not unit:
            continue
        control = indexes["control_by_unit"].get(unit_id, {})
        source = indexes["source_by_unit"].get(unit_id, {})
        witness = indexes["witness_by_unit"].get(unit_id, {})
        poetic = indexes["poetic_by_unit"].get(unit_id, {})
        divine_ids = indexes["divine_token_ids"].get(unit_id, set())
        superscription_ids = indexes["superscription_token_ids"].get(unit_id, set())
        for position, token in enumerate(unit.get("tokens", []), start=1):
            token_id = str(token["token_id"])
            anchor = indexes["anchor_by_token"].get(token_id, {})
            culture_rows = indexes["culture_by_token"].get(token_id, [])
            is_divine = token_id in divine_ids or boolish(
                token.get("compiler_features", {}).get("divine_name")
            )
            is_superscription = token_id in superscription_ids
            flags = token_control_flags(
                token, unit, exhibit, anchor, culture_rows, is_divine, is_superscription
            )
            domain_labels = sorted({str(row["domain_label"]) for row in culture_rows})
            outside_divisions = anchor.get("outside_division_counts", {})
            token_rows.append(
                {
                    "unit_rank": exhibit["rank"],
                    "token_rank": 0,
                    "unit_id": unit_id,
                    "ref": unit["ref"],
                    "token_position": position,
                    "token_id": token_id,
                    "surface": token.get("surface", ""),
                    "normalized": token.get("normalized", ""),
                    "lemma": token.get("lemma", ""),
                    "strong": token.get("strong", ""),
                    "display_gloss": token.get("display_gloss", ""),
                    "transliteration": token.get("transliteration", ""),
                    "part_of_speech": token.get("part_of_speech", ""),
                    "morph_code": token.get("morph_code", ""),
                    "morph_readable": token.get("morph_readable", ""),
                    "stem": token.get("stem") or "",
                    "syntax_role": token.get("syntax_role") or "",
                    "semantic_role": token.get("semantic_role") or "",
                    "referent": token.get("referent") or "",
                    "word_sense": token.get("word_sense") or "",
                    "greek": token.get("greek") or "",
                    "greek_strong": token.get("greek_strong") or "",
                    "missing_enrichments": list_join(token.get("missing_enrichments", [])),
                    "missing_enrichment_count": len(token.get("missing_enrichments", [])),
                    "compiler_construct_state": boolish(
                        token.get("compiler_features", {}).get("construct_state")
                    ),
                    "compiler_suffix_pronoun": (
                        token.get("compiler_features", {}).get("suffix_pronoun") or ""
                    ),
                    "compiler_preposition_role": (
                        token.get("compiler_features", {}).get("preposition_role") or ""
                    ),
                    "is_divine_name_token": is_divine,
                    "is_superscription_token": is_superscription,
                    "same_psalm_occurrence_count": len(token.get("same_psalm_occurrence_refs", [])),
                    "psalms_occurrence_count": len(token.get("psalms_occurrence_refs", [])),
                    "outside_psalms_count": int(anchor.get("outside_psalms_count") or 0),
                    "tanakh_count": int(anchor.get("tanakh_count") or 0),
                    "anchor_strength": anchor.get("anchor_strength", ""),
                    "anchor_score": as_float(anchor.get("anchor_score")),
                    "has_torah_evidence": boolish(anchor.get("has_torah_evidence")),
                    "has_prophets_evidence": boolish(anchor.get("has_prophets_evidence")),
                    "has_non_psalm_writings_evidence": boolish(
                        anchor.get("has_non_psalm_writings_evidence")
                    ),
                    "outside_division_counts": outside_divisions,
                    "top_book_refs": anchor.get("top_book_refs", {}),
                    "cultural_domain_count": len(domain_labels),
                    "cultural_domain_labels": list_join(domain_labels),
                    "witness_divergence_pct": as_float(
                        witness.get(
                            "mean_english_witness_divergence_pct",
                            exhibit.get("witness_divergence_pct"),
                        )
                    ),
                    "poetic_pressure_band": poetic.get(
                        "pressure_band", exhibit.get("poetic_pressure_band", "")
                    ),
                    "unit_defense_exhibit_score": exhibit["defense_exhibit_score"],
                    "unit_authority_score_pct": exhibit["unit_authority_score_pct"],
                    "source_ladder_stage": source.get(
                        "evidence_ladder_stage", exhibit.get("source_ladder_stage", "")
                    ),
                    "source_approval_count": exhibit["source_approval_count"],
                    "completed_review_row_count": exhibit["completed_review_row_count"],
                    "jewish_christian_separation_required": boolish(
                        exhibit.get("jewish_christian_separation_required")
                    ),
                    "reception_sensitive": boolish(exhibit.get("reception_sensitive")),
                    "translation_text_forbidden_reception_claim": boolish(
                        control.get(
                            "translation_text_forbidden_reception_claim",
                            exhibit.get("translation_text_forbidden_reception_claim"),
                        )
                    ),
                    "token_control_flags": flags,
                    "token_control_count": len(flags),
                    "token_defense_score": token_score(
                        token, exhibit, anchor, culture_rows, is_divine, is_superscription, flags
                    ),
                    "translation_note": (
                        "Token requires reviewer-visible evidence before it can support "
                        "translation wording or interpretive notes."
                    ),
                    "authority_boundary": AUTHORITY_POLICY,
                }
            )
    token_rows.sort(key=lambda row: (-float(row["token_defense_score"]), row["token_id"]))
    for index, row in enumerate(token_rows, start=1):
        row["token_rank"] = index
    return token_rows


def build_unit_rows(token_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in token_rows:
        grouped[str(row["unit_id"])].append(row)
    unit_rows: list[dict[str, Any]] = []
    for unit_id, rows in grouped.items():
        rows.sort(key=lambda row: int(row["token_position"]))
        top_rows = sorted(rows, key=lambda row: -float(row["token_defense_score"]))[:6]
        unit_rows.append(
            {
                "unit_id": unit_id,
                "ref": rows[0]["ref"],
                "token_count": len(rows),
                "mean_token_defense_score": mean(
                    [float(row["token_defense_score"]) for row in rows]
                ),
                "max_token_defense_score": max(float(row["token_defense_score"]) for row in rows),
                "critical_token_count": sum(
                    1 for row in rows if float(row["token_defense_score"]) >= CRITICAL_TOKEN_SCORE
                ),
                "anchor_token_count": sum(1 for row in rows if row["anchor_strength"]),
                "cultural_domain_token_count": sum(
                    1 for row in rows if int(row["cultural_domain_count"]) > 0
                ),
                "divine_name_token_count": sum(1 for row in rows if row["is_divine_name_token"]),
                "missing_semantic_role_token_count": sum(
                    1 for row in rows if "semantic_role_missing" in row["token_control_flags"]
                ),
                "missing_referent_token_count": sum(
                    1 for row in rows if "referent_missing" in row["token_control_flags"]
                ),
                "source_approval_count": rows[0]["source_approval_count"],
                "completed_review_row_count": rows[0]["completed_review_row_count"],
                "jewish_christian_separation_required": rows[0][
                    "jewish_christian_separation_required"
                ],
                "top_token_ids": list_join([row["token_id"] for row in top_rows]),
                "top_token_surfaces": list_join([row["surface"] for row in top_rows]),
                "top_token_glosses": list_join([row["display_gloss"] for row in top_rows]),
                "authority_boundary": AUTHORITY_POLICY,
            }
        )
    unit_rows.sort(key=lambda row: (-float(row["mean_token_defense_score"]), row["ref"]))
    for index, row in enumerate(unit_rows, start=1):
        row["rank"] = index
    return unit_rows


def build_control_rows(token_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    top_by_control: dict[str, dict[str, Any]] = {}
    for row in token_rows:
        for flag in row["token_control_flags"]:
            counts[flag] += 1
            if (
                flag not in top_by_control
                or row["token_defense_score"] > top_by_control[flag]["token_defense_score"]
            ):
                top_by_control[flag] = row
    return [
        {
            "control": control,
            "token_count": count,
            "token_pct": pct(count, len(token_rows)),
            "top_ref": top_by_control[control]["ref"],
            "top_token_id": top_by_control[control]["token_id"],
            "top_surface": top_by_control[control]["surface"],
            "top_score": top_by_control[control]["token_defense_score"],
        }
        for control, count in counts.most_common()
    ]


def build_summary(
    token_rows: list[dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    top = token_rows[0] if token_rows else {}
    return {
        "unit_count": len(unit_rows),
        "token_count": len(token_rows),
        "critical_token_score_threshold": CRITICAL_TOKEN_SCORE,
        "critical_token_count": sum(
            1 for row in token_rows if float(row["token_defense_score"]) >= CRITICAL_TOKEN_SCORE
        ),
        "mean_token_defense_score": mean([float(row["token_defense_score"]) for row in token_rows]),
        "anchor_token_count": sum(1 for row in token_rows if row["anchor_strength"]),
        "high_anchor_token_count": sum(1 for row in token_rows if row["anchor_strength"] == "high"),
        "cultural_domain_token_count": sum(
            1 for row in token_rows if int(row["cultural_domain_count"]) > 0
        ),
        "divine_name_token_count": sum(1 for row in token_rows if row["is_divine_name_token"]),
        "superscription_token_count": sum(
            1 for row in token_rows if row["is_superscription_token"]
        ),
        "construct_state_token_count": sum(
            1 for row in token_rows if row["compiler_construct_state"]
        ),
        "missing_semantic_role_token_count": sum(
            1 for row in token_rows if "semantic_role_missing" in row["token_control_flags"]
        ),
        "missing_referent_token_count": sum(
            1 for row in token_rows if "referent_missing" in row["token_control_flags"]
        ),
        "source_approved_token_count": sum(
            1 for row in token_rows if int(row["source_approval_count"]) > 0
        ),
        "review_completed_token_count": sum(
            1 for row in token_rows if int(row["completed_review_row_count"]) > 0
        ),
        "control_count": len(control_rows),
        "top_token_id": top.get("token_id", ""),
        "top_token_ref": top.get("ref", ""),
        "top_token_surface": top.get("surface", ""),
        "top_token_gloss": top.get("display_gloss", ""),
        "top_token_score": top.get("token_defense_score", 0.0),
        "authority_verdict": (
            "Token evidence is sufficiently detailed for reviewer triage, but no token-level "
            "claim is authoritative until source approval, semantic/referent gaps, packet review, "
            "and release gates are resolved."
        ),
    }


def build_visual_data(
    token_rows: list[dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    pos_counts = Counter(str(row["part_of_speech"] or "unknown") for row in token_rows)
    domain_counts: Counter[str] = Counter()
    missing_counts: Counter[str] = Counter()
    for row in token_rows:
        domain_counts.update(listify(row["cultural_domain_labels"]))
        missing_counts.update(listify(row["missing_enrichments"]))
    return {
        "top_token_rows": [
            {"label": f"{row['ref']} {row['surface']}", "value": row["token_defense_score"]}
            for row in token_rows[:25]
        ],
        "unit_mean_rows": [
            {"label": row["ref"], "value": row["mean_token_defense_score"]}
            for row in unit_rows[:20]
        ],
        "control_rows": [
            {"label": row["control"], "value": row["token_count"]} for row in control_rows[:20]
        ],
        "pos_rows": [{"label": label, "value": count} for label, count in pos_counts.most_common()],
        "domain_rows": [
            {"label": label, "value": count} for label, count in domain_counts.most_common()
        ],
        "missing_rows": [
            {"label": label, "value": count} for label, count in missing_counts.most_common()
        ],
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    token_rows = build_token_rows(data)
    unit_rows = build_unit_rows(token_rows)
    control_rows = build_control_rows(token_rows)
    summary = build_summary(token_rows, unit_rows, control_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "Hebrew token defense matrix generated; not authority signoff",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": AUTHORITY_POLICY,
        "summary": summary,
        "token_rows": token_rows,
        "unit_rows": unit_rows,
        "control_rows": control_rows,
        "visual_data": build_visual_data(token_rows, unit_rows, control_rows),
    }


def metric_cards(cards: list[tuple[str, Any, str]]) -> str:
    return "\n".join(
        f"""
        <article class="metric">
          <div class="metric-label">{esc(label)}</div>
          <div class="metric-value">{esc(value)}</div>
          <p>{esc(detail)}</p>
        </article>
        """
        for label, value, detail in cards
    )


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    color: str = "#2f6f73",
    limit: int = 18,
) -> str:
    rows = rows[:limit]
    if not rows:
        return "<p>No rows.</p>"
    max_value = max(float(row["value"]) for row in rows) or 1.0
    width = 940
    row_height = 28
    label_width = 360
    bar_width = width - label_width - 90
    height = 34 + len(rows) * row_height
    parts = [(f'<svg role="img" aria-label="horizontal bar chart" viewBox="0 0 {width} {height}">')]
    for index, row in enumerate(rows):
        y = 24 + index * row_height
        value = float(row["value"])
        bar = value / max_value * bar_width
        parts.append(
            f'<text x="0" y="{y + 14}" font-size="12" fill="#263238">{esc(row["label"])}</text>'
        )
        parts.append(
            f'<rect x="{label_width}" y="{y}" width="{bar:.1f}" height="18" '
            f'rx="3" fill="{color}"></rect>'
        )
        parts.append(
            f'<text x="{label_width + bar + 8:.1f}" y="{y + 14}" '
            f'font-size="12" fill="#263238">{value:.2f}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    token_rows = [
        [
            row["token_rank"],
            row["ref"],
            row["surface"],
            row["lemma"],
            row["strong"],
            row["display_gloss"],
            row["part_of_speech"],
            row["morph_code"],
            f"{row['token_defense_score']:.2f}",
            row["anchor_strength"],
            row["outside_psalms_count"],
            row["cultural_domain_labels"],
            row["missing_enrichments"],
            row["token_control_flags"],
        ]
        for row in report["token_rows"][:45]
    ]
    unit_rows = [
        [
            row["rank"],
            row["ref"],
            row["token_count"],
            f"{row['mean_token_defense_score']:.2f}",
            f"{row['max_token_defense_score']:.2f}",
            row["critical_token_count"],
            row["anchor_token_count"],
            row["cultural_domain_token_count"],
            row["divine_name_token_count"],
            row["missing_semantic_role_token_count"],
            row["top_token_surfaces"],
        ]
        for row in report["unit_rows"][:25]
    ]
    control_rows = [
        [
            row["control"],
            row["token_count"],
            f"{row['token_pct']:.2f}%",
            row["top_ref"],
            row["top_surface"],
            f"{row['top_score']:.2f}",
        ]
        for row in report["control_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Hebrew Token Defense Matrix</title>
  <style>
    body {{
      margin: 0;
      background: #f7f5ef;
      color: #263238;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }}
    header, main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    header {{ padding-top: 42px; }}
    h1 {{ margin: 0 0 8px; font-size: 34px; letter-spacing: 0; }}
    h2 {{ margin-top: 34px; font-size: 22px; letter-spacing: 0; }}
    p {{ line-height: 1.5; }}
    .warning {{
      border-left: 5px solid #9b3d3d;
      background: #fff8f2;
      padding: 14px 16px;
      margin: 18px 0;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 18px 0;
    }}
    .metric, .chart {{
      border: 1px solid #d7d1c2;
      background: #fff;
      border-radius: 8px;
    }}
    .metric {{ padding: 14px; }}
    .metric-label {{ font-size: 12px; text-transform: uppercase; color: #607d8b; }}
    .metric-value {{ font-size: 28px; font-weight: 700; margin-top: 6px; }}
    .metric p {{ margin: 6px 0 0; font-size: 13px; }}
    .chart {{ overflow-x: auto; padding: 12px; margin: 14px 0; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 14px 0 24px;
      background: #fff;
      border: 1px solid #d7d1c2;
      font-size: 13px;
    }}
    th, td {{ border-bottom: 1px solid #e5dfd2; padding: 8px; vertical-align: top; }}
    th {{ text-align: left; background: #eee7d7; }}
    td {{ max-width: 360px; }}
  </style>
</head>
<body>
<header>
  <h1>Hebrew Token Defense Matrix</h1>
  <p>
    Token-level evidence for the doctoral defense exhibits: Hebrew surface,
    lemma, Strong, morphology, whole-Tanakh anchors, cultural domains, witness
    pressure, and authority controls.
  </p>
  <div class="warning">{esc(report["authority_policy"])}</div>
  <section class="metrics">
    {
        metric_cards(
            [
                ("Units", summary["unit_count"], "Defense exhibit units with token rows."),
                ("Tokens", summary["token_count"], "Hebrew tokens across exhibit units."),
                (
                    "Critical Tokens",
                    summary["critical_token_count"],
                    f"Token defense score >= {summary['critical_token_score_threshold']:.0f}.",
                ),
                (
                    "Anchors",
                    summary["anchor_token_count"],
                    f"{summary['high_anchor_token_count']} high-strength anchors.",
                ),
                (
                    "Culture Tokens",
                    summary["cultural_domain_token_count"],
                    "Tokens carrying cultural/historical domain markers.",
                ),
                (
                    "Divine Name",
                    summary["divine_name_token_count"],
                    "Tokens requiring divine-name/title policy review.",
                ),
                (
                    "Semantic Gaps",
                    summary["missing_semantic_role_token_count"],
                    "Tokens missing semantic-role enrichment.",
                ),
                (
                    "Top Token",
                    summary["top_token_surface"],
                    (f"{summary['top_token_ref']}; score {float(summary['top_token_score']):.2f}."),
                ),
            ]
        )
    }
  </section>
</header>
<main>
  <section>
    <h2>Token Frontier</h2>
    <div class="chart">{svg_horizontal_bars(visual["top_token_rows"], color="#9b3d3d")}</div>
    <div class="chart">{svg_horizontal_bars(visual["unit_mean_rows"], color="#2f6f73")}</div>
    <div class="chart">{svg_horizontal_bars(visual["control_rows"], color="#7c5b2f")}</div>
    {
        table(
            [
                "Rank",
                "Ref",
                "Surface",
                "Lemma",
                "Strong",
                "Gloss",
                "POS",
                "Morph",
                "Score",
                "Anchor",
                "Outside Psalms",
                "Culture Domains",
                "Missing",
                "Controls",
            ],
            token_rows,
        )
    }
  </section>
  <section>
    <h2>Unit Token Summary</h2>
    {
        table(
            [
                "Rank",
                "Ref",
                "Tokens",
                "Mean Score",
                "Max Score",
                "Critical",
                "Anchors",
                "Culture",
                "Divine",
                "Semantic Gaps",
                "Top Tokens",
            ],
            unit_rows,
        )
    }
  </section>
  <section>
    <h2>Control Distribution</h2>
    <div class="chart">{svg_horizontal_bars(visual["pos_rows"], color="#2f6f73")}</div>
    <div class="chart">{svg_horizontal_bars(visual["domain_rows"], color="#7c5b2f")}</div>
    <div class="chart">{svg_horizontal_bars(visual["missing_rows"], color="#9b3d3d")}</div>
    {table(["Control", "Tokens", "Pct", "Top Ref", "Top Surface", "Top Score"], control_rows)}
  </section>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Hebrew token defense matrix.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--token-csv-output", type=Path, default=DEFAULT_TOKEN_CSV_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.token_csv_output, report["token_rows"])
    write_csv(args.unit_csv_output, report["unit_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.token_csv_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
