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
    "lexeme": REPORT_ROOT / "lexeme_context_readiness.json",
    "hebrew_token_defense": REPORT_ROOT / "hebrew_token_defense_matrix.json",
    "canonical_cross_reference": REPORT_ROOT / "canonical_cross_reference_atlas.json",
    "cultural_atlas": REPORT_ROOT / "cultural_historical_domain_atlas.json",
    "divine_name_policy": REPORT_ROOT / "divine_name_policy_report.json",
    "superscription_context": REPORT_ROOT / "superscription_context_report.json",
    "priority_dossier": REPORT_ROOT / "doctoral_priority_dossier_atlas.json",
    "source_ladder": REPORT_ROOT / "source_authority_ladder_matrix.json",
    "morphology_unlock": REPORT_ROOT / "whole_tanakh_morphology_unlock_matrix.json",
}

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "semantic_referent_enrichment_roadmap.json"
DEFAULT_TOKEN_CSV_OUTPUT = REPORT_ROOT / "semantic_referent_enrichment_tokens.csv"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "semantic_referent_enrichment_units.csv"
DEFAULT_LANE_CSV_OUTPUT = REPORT_ROOT / "semantic_referent_enrichment_lanes.csv"
DEFAULT_GAP_CSV_OUTPUT = REPORT_ROOT / "semantic_referent_enrichment_gaps.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "semantic_referent_enrichment_roadmap.html"

CRITICAL_ENRICHMENT_SCORE = 225.0

AUTHORITY_POLICY = (
    "The semantic/referent enrichment roadmap is a derived prioritization queue. "
    "It identifies where semantic-role, referent, syntax, stem, and discourse "
    "enrichment would most improve Hebrew-to-English review quality, but it does "
    "not import source data, approve sources, assign final referents, alter "
    "canonical content, certify model output, or authorize release."
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


def list_join(values: list[Any], limit: int | None = None) -> str:
    if limit is not None:
        values = values[:limit]
    return "; ".join(str(value) for value in values if str(value))


def by_key(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key)}


def index_by_token(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    indexed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        token_id = str(row.get("token_id", ""))
        if token_id:
            indexed[token_id].append(row)
    return indexed


def content_unit_paths() -> list[Path]:
    return sorted(
        path for path in CONTENT_ROOT.glob("ps*/*.json") if not path.name.endswith(".meta.json")
    )


def build_indexes(data: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "defense_by_token": by_key(data["hebrew_token_defense"].get("token_rows", []), "token_id"),
        "anchor_by_token": by_key(
            data["canonical_cross_reference"].get("anchor_rows", []), "token_id"
        ),
        "culture_by_token": index_by_token(data["cultural_atlas"].get("token_rows", [])),
        "divine_by_token": by_key(data["divine_name_policy"].get("token_rows", []), "token_id"),
        "superscription_by_token": by_key(
            data["superscription_context"].get("token_rows", []), "token_id"
        ),
        "priority_by_unit": by_key(data["priority_dossier"].get("unit_rows", []), "unit_id"),
        "source_by_unit": by_key(data["source_ladder"].get("unit_rows", []), "unit_id"),
        "unlock_by_unit": by_key(data["morphology_unlock"].get("unit_rows", []), "unit_id"),
    }


def enrichment_lanes(
    *,
    token: dict[str, Any],
    missing: set[str],
    anchor: dict[str, Any],
    culture_rows: list[dict[str, Any]],
    is_divine: bool,
    is_superscription: bool,
) -> list[str]:
    compiler = token.get("compiler_features", {})
    lanes: list[str] = []
    if "macula:referent" in missing and (
        compiler.get("suffix_pronoun") or token.get("part_of_speech") in {"pronoun", "suffix"}
    ):
        lanes.append("referent_resolution")
    if "macula:semantic_role" in missing:
        lanes.append("semantic_role_labeling")
    if "macula:syntax_role" in missing:
        lanes.append("syntax_role_import")
    if "oshb:stem" in missing and token.get("part_of_speech") == "verb":
        lanes.append("verbal_stem_argument_review")
    if compiler.get("construct_state"):
        lanes.append("construct_chain_alignment")
    if is_divine or compiler.get("divine_name"):
        lanes.append("divine_name_referent_policy")
    if is_superscription:
        lanes.append("superscription_speaker_context")
    if anchor:
        lanes.append("whole_tanakh_anchor_sense_review")
    if culture_rows:
        lanes.append("cultural_domain_frame_review")
    if {"oshb:strong", "oshb:lemma", "macula:word_sense"} & missing:
        lanes.append("lexical_source_cleanup")
    return sorted(set(lanes))


def next_action_for_lanes(lanes: list[str]) -> str:
    if "lexical_source_cleanup" in lanes:
        return "Resolve lemma/Strong/sense source gaps before semantic or referent signoff."
    if "referent_resolution" in lanes:
        return "Assign antecedent/referent candidates, then route to Hebrew and theology review."
    if "verbal_stem_argument_review" in lanes:
        return "Import or review stem plus argument structure before approving discourse claims."
    if "whole_tanakh_anchor_sense_review" in lanes:
        return "Review whole-Tanakh anchor context as evidence, not lemma or sense proof."
    if "semantic_role_labeling" in lanes:
        return "Add semantic-role labels and validate against alignment and source packets."
    return "Queue for enrichment review after source approval."


def reviewer_roles_for_lanes(lanes: list[str]) -> list[str]:
    roles = {"Hebrew", "alignment"}
    if "divine_name_referent_policy" in lanes or "referent_resolution" in lanes:
        roles.add("theology")
    if "cultural_domain_frame_review" in lanes or "superscription_speaker_context" in lanes:
        roles.add("lexical")
    if "whole_tanakh_anchor_sense_review" in lanes:
        roles.add("release")
    return sorted(roles)


def token_score(
    *,
    token: dict[str, Any],
    missing: set[str],
    defense: dict[str, Any],
    anchor: dict[str, Any],
    culture_rows: list[dict[str, Any]],
    priority: dict[str, Any],
    source: dict[str, Any],
    is_divine: bool,
    is_superscription: bool,
    lanes: list[str],
) -> float:
    compiler = token.get("compiler_features", {})
    score = 0.0
    score += 35 if "macula:semantic_role" in missing else 0
    score += 35 if "macula:referent" in missing else 0
    score += 12 if "macula:syntax_role" in missing else 0
    score += 8 if "oshb:stem" in missing else 0
    score += 18 if {"oshb:strong", "oshb:lemma", "macula:word_sense"} & missing else 0
    score += 22 if compiler.get("suffix_pronoun") else 0
    score += 14 if compiler.get("construct_state") else 0
    score += 18 if token.get("part_of_speech") == "verb" else 0
    score += 8 if token.get("part_of_speech") in {"pronoun", "suffix"} else 0
    score += 20 if is_divine or compiler.get("divine_name") else 0
    score += 14 if is_superscription else 0
    score += len(culture_rows) * 10
    score += as_float(anchor.get("anchor_score")) * 0.75
    score += int(anchor.get("outside_psalms_count") or 0) ** 0.5
    score += as_float(defense.get("token_defense_score")) * 0.35
    score += as_float(priority.get("doctoral_dossier_priority_score")) * 0.04
    score += as_float(source.get("source_authority_gap_score")) * 0.03
    score += 12 if boolish(priority.get("jewish_christian_separation_required")) else 0
    score += 8 if boolish(priority.get("ancient_culture_pressure")) else 0
    score += 8 if boolish(priority.get("textual_witness_pressure")) else 0
    score += len(lanes) * 3
    return round(score, 2)


def build_token_rows(data: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    indexes = build_indexes(data)
    rows: list[dict[str, Any]] = []
    for unit_path in content_unit_paths():
        unit = load_json(unit_path)
        unit_id = str(unit["unit_id"])
        priority = indexes["priority_by_unit"].get(unit_id, {})
        source = indexes["source_by_unit"].get(unit_id, {})
        unlock = indexes["unlock_by_unit"].get(unit_id, {})
        for position, token in enumerate(unit.get("tokens", []), start=1):
            token_id = str(token["token_id"])
            missing = set(token.get("missing_enrichments", []))
            compiler = token.get("compiler_features", {})
            defense = indexes["defense_by_token"].get(token_id, {})
            anchor = indexes["anchor_by_token"].get(token_id, {})
            culture_rows = indexes["culture_by_token"].get(token_id, [])
            divine = indexes["divine_by_token"].get(token_id, {})
            superscription = indexes["superscription_by_token"].get(token_id, {})
            is_divine = bool(divine) or boolish(compiler.get("divine_name"))
            is_superscription = bool(superscription)
            lanes = enrichment_lanes(
                token=token,
                missing=missing,
                anchor=anchor,
                culture_rows=culture_rows,
                is_divine=is_divine,
                is_superscription=is_superscription,
            )
            row = {
                "unit_id": unit_id,
                "ref": unit.get("ref", ""),
                "psalm_id": unit.get("psalm_id", ""),
                "source_hebrew": unit.get("source_hebrew", ""),
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
                "stem": token.get("stem", ""),
                "syntax_role": token.get("syntax_role", ""),
                "semantic_role": token.get("semantic_role", ""),
                "referent": token.get("referent", ""),
                "word_sense": token.get("word_sense", ""),
                "missing_enrichments": sorted(missing),
                "missing_enrichment_count": len(missing),
                "missing_semantic_role": "macula:semantic_role" in missing,
                "missing_referent": "macula:referent" in missing,
                "missing_syntax_role": "macula:syntax_role" in missing,
                "missing_stem": "oshb:stem" in missing,
                "compiler_construct_state": boolish(compiler.get("construct_state")),
                "compiler_suffix_pronoun": boolish(compiler.get("suffix_pronoun")),
                "compiler_preposition_role": compiler.get("preposition_role", ""),
                "is_divine_name_token": is_divine,
                "is_superscription_token": is_superscription,
                "anchor_strength": anchor.get("anchor_strength", ""),
                "anchor_score": as_float(anchor.get("anchor_score")),
                "outside_psalms_count": int(anchor.get("outside_psalms_count") or 0),
                "has_three_division_evidence": bool(
                    anchor.get("has_torah_evidence")
                    and anchor.get("has_prophets_evidence")
                    and anchor.get("has_non_psalm_writings_evidence")
                ),
                "top_book_refs": anchor.get("top_book_refs", []),
                "cultural_domain_count": len(culture_rows),
                "cultural_domain_labels": sorted(
                    {
                        str(row.get("domain_label", ""))
                        for row in culture_rows
                        if row.get("domain_label")
                    }
                ),
                "in_defense_exhibit": bool(defense),
                "token_defense_score": as_float(defense.get("token_defense_score")),
                "dossier_priority_score": as_float(priority.get("doctoral_dossier_priority_score")),
                "dossier_band": priority.get("dossier_band", ""),
                "jewish_christian_separation_required": boolish(
                    priority.get("jewish_christian_separation_required")
                ),
                "ancient_culture_pressure": boolish(priority.get("ancient_culture_pressure")),
                "textual_witness_pressure": boolish(priority.get("textual_witness_pressure")),
                "source_authority_gap_score": as_float(source.get("source_authority_gap_score")),
                "source_authority_readiness_pct": as_float(
                    source.get("source_authority_readiness_pct")
                ),
                "source_approval_count": int(source.get("source_approval_count") or 0),
                "completed_review_row_count": int(source.get("completed_review_row_count") or 0),
                "morphology_unlock_status": unlock.get("unlock_status", ""),
                "projected_whole_tanakh_score_delta_pct": as_float(
                    unlock.get("projected_lane_score_delta_pct")
                ),
                "enrichment_lanes": lanes,
                "enrichment_lane_count": len(lanes),
                "required_review_roles": reviewer_roles_for_lanes(lanes),
                "recommended_next_action": next_action_for_lanes(lanes),
                "authority_boundary": AUTHORITY_POLICY,
            }
            row["enrichment_priority_score"] = token_score(
                token=token,
                missing=missing,
                defense=defense,
                anchor=anchor,
                culture_rows=culture_rows,
                priority=priority,
                source=source,
                is_divine=is_divine,
                is_superscription=is_superscription,
                lanes=lanes,
            )
            rows.append(row)
    rows.sort(key=lambda row: (-float(row["enrichment_priority_score"]), row["token_id"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_unit_rows(token_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in token_rows:
        grouped[str(row["unit_id"])].append(row)
    rows: list[dict[str, Any]] = []
    for unit_id, tokens in grouped.items():
        top_tokens = sorted(tokens, key=lambda row: -float(row["enrichment_priority_score"]))[:6]
        roles = sorted({role for row in tokens for role in row["required_review_roles"]})
        lanes = Counter(lane for row in tokens for lane in row["enrichment_lanes"])
        rows.append(
            {
                "unit_id": unit_id,
                "ref": tokens[0]["ref"],
                "psalm_id": tokens[0]["psalm_id"],
                "source_hebrew": tokens[0]["source_hebrew"],
                "token_count": len(tokens),
                "missing_semantic_role_token_count": sum(
                    1 for row in tokens if row["missing_semantic_role"]
                ),
                "missing_referent_token_count": sum(1 for row in tokens if row["missing_referent"]),
                "missing_syntax_role_token_count": sum(
                    1 for row in tokens if row["missing_syntax_role"]
                ),
                "missing_stem_token_count": sum(1 for row in tokens if row["missing_stem"]),
                "suffix_pronoun_token_count": sum(
                    1 for row in tokens if row["compiler_suffix_pronoun"]
                ),
                "construct_state_token_count": sum(
                    1 for row in tokens if row["compiler_construct_state"]
                ),
                "verb_token_count": sum(1 for row in tokens if row["part_of_speech"] == "verb"),
                "divine_name_token_count": sum(1 for row in tokens if row["is_divine_name_token"]),
                "superscription_token_count": sum(
                    1 for row in tokens if row["is_superscription_token"]
                ),
                "anchor_token_count": sum(1 for row in tokens if row["anchor_strength"]),
                "cultural_domain_token_count": sum(
                    1 for row in tokens if int(row["cultural_domain_count"]) > 0
                ),
                "defense_exhibit_token_count": sum(
                    1 for row in tokens if row["in_defense_exhibit"]
                ),
                "critical_enrichment_token_count": sum(
                    1
                    for row in tokens
                    if float(row["enrichment_priority_score"]) >= CRITICAL_ENRICHMENT_SCORE
                ),
                "mean_enrichment_priority_score": mean(
                    [float(row["enrichment_priority_score"]) for row in tokens]
                ),
                "max_enrichment_priority_score": max(
                    float(row["enrichment_priority_score"]) for row in tokens
                ),
                "source_approval_count": max(int(row["source_approval_count"]) for row in tokens),
                "completed_review_row_count": max(
                    int(row["completed_review_row_count"]) for row in tokens
                ),
                "required_review_roles": roles,
                "primary_enrichment_lanes": [lane for lane, _ in lanes.most_common(5)],
                "top_token_ids": list_join([row["token_id"] for row in top_tokens]),
                "top_token_surfaces": list_join([row["surface"] for row in top_tokens]),
                "top_token_glosses": list_join([row["display_gloss"] for row in top_tokens]),
                "top_next_action": top_tokens[0]["recommended_next_action"] if top_tokens else "",
                "authority_boundary": AUTHORITY_POLICY,
            }
        )
    rows.sort(key=lambda row: (-float(row["max_enrichment_priority_score"]), row["ref"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def build_lane_rows(token_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in token_rows:
        for lane in row["enrichment_lanes"]:
            grouped[lane].append(row)
    rows: list[dict[str, Any]] = []
    for lane, tokens in grouped.items():
        top = max(tokens, key=lambda row: float(row["enrichment_priority_score"]))
        roles = sorted({role for row in tokens for role in row["required_review_roles"]})
        rows.append(
            {
                "lane": lane,
                "token_count": len(tokens),
                "token_pct": pct(len(tokens), len(token_rows)),
                "unit_count": len({row["unit_id"] for row in tokens}),
                "critical_token_count": sum(
                    1
                    for row in tokens
                    if float(row["enrichment_priority_score"]) >= CRITICAL_ENRICHMENT_SCORE
                ),
                "mean_enrichment_priority_score": mean(
                    [float(row["enrichment_priority_score"]) for row in tokens]
                ),
                "top_ref": top["ref"],
                "top_token_id": top["token_id"],
                "top_surface": top["surface"],
                "top_score": top["enrichment_priority_score"],
                "required_review_roles": roles,
                "next_action": next_action_for_lanes([lane]),
                "authority_boundary": AUTHORITY_POLICY,
            }
        )
    rows.sort(
        key=lambda row: (-int(row["critical_token_count"]), -int(row["token_count"]), row["lane"])
    )
    return rows


def build_gap_rows(token_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gap_specs = [
        ("semantic_role", "macula:semantic_role", "Semantic Role", "Blocks discourse-role claims."),
        (
            "referent",
            "macula:referent",
            "Referent",
            "Blocks antecedent and speaker/addressee claims.",
        ),
        ("syntax_role", "macula:syntax_role", "Syntax Role", "Blocks clause-function review."),
        ("stem", "oshb:stem", "Stem", "Blocks verb-stem and argument-structure review."),
        ("strong", "oshb:strong", "Strong", "Blocks lexeme-level source joins."),
        ("lemma", "oshb:lemma", "Lemma", "Blocks lemma-level source joins."),
        ("word_sense", "macula:word_sense", "Word Sense", "Blocks sense-level adjudication."),
    ]
    rows: list[dict[str, Any]] = []
    for field, missing_key, label, authority_effect in gap_specs:
        missing_rows = [row for row in token_rows if missing_key in row["missing_enrichments"]]
        top = (
            max(missing_rows, key=lambda row: float(row["enrichment_priority_score"]))
            if missing_rows
            else {}
        )
        rows.append(
            {
                "field": field,
                "label": label,
                "missing_key": missing_key,
                "covered_token_count": len(token_rows) - len(missing_rows),
                "missing_token_count": len(missing_rows),
                "coverage_pct": pct(len(token_rows) - len(missing_rows), len(token_rows)),
                "missing_pct": pct(len(missing_rows), len(token_rows)),
                "top_ref": top.get("ref", ""),
                "top_token_id": top.get("token_id", ""),
                "top_surface": top.get("surface", ""),
                "top_score": top.get("enrichment_priority_score", 0.0),
                "authority_effect": authority_effect,
            }
        )
    return rows


def build_phase_rows(
    token_rows: list[dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    data: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    lexeme = data["lexeme"]["summary"]
    morph_unlock = data["morphology_unlock"]["summary"]
    high_priority_tokens = sum(
        1
        for row in token_rows
        if float(row["enrichment_priority_score"]) >= CRITICAL_ENRICHMENT_SCORE
    )
    source_approved = sum(1 for row in token_rows if int(row["source_approval_count"]) > 0)
    completed_review = sum(1 for row in token_rows if int(row["completed_review_row_count"]) > 0)
    return [
        {
            "phase_id": "SEM-01",
            "phase": "Approve enrichment source path",
            "status": "blocked",
            "evidence": (
                f"Semantic-role coverage {lexeme['semantic_role_coverage_pct']:.2f}%; "
                f"referent coverage {lexeme['referent_coverage_pct']:.2f}%; "
                f"{source_approved} enriched tokens have source approval."
            ),
            "token_count": len(token_rows),
            "unit_count": len(unit_rows),
            "next_action": (
                "Approve source/provenance path for semantic, referent, syntax, and stem data."
            ),
        },
        {
            "phase_id": "SEM-02",
            "phase": "Import or derive syntax/stem baseline",
            "status": "blocked",
            "evidence": (
                f"{morph_unlock['pilot_mapped_non_psalm_book_count']} non-Psalm books are "
                "pilot-mapped for OSHB morphology; "
                f"{morph_unlock['exception_review_row_count']} exception rows still need review."
            ),
            "token_count": sum(
                1 for row in token_rows if row["missing_syntax_role"] or row["missing_stem"]
            ),
            "unit_count": sum(
                1
                for row in unit_rows
                if row["missing_syntax_role_token_count"] or row["missing_stem_token_count"]
            ),
            "next_action": (
                "Complete source approval, importer, exception review, and Psalm regression."
            ),
        },
        {
            "phase_id": "SEM-03",
            "phase": "Resolve high-pressure referents",
            "status": "not started",
            "evidence": (
                f"{high_priority_tokens} tokens meet the critical enrichment threshold; "
                "referent-sensitive lanes include suffix pronouns, divine names, "
                "and superscriptions."
            ),
            "token_count": sum(
                row["token_count"]
                for row in lane_rows
                if row["lane"]
                in {
                    "referent_resolution",
                    "divine_name_referent_policy",
                    "superscription_speaker_context",
                }
            ),
            "unit_count": len(
                {
                    row["unit_id"]
                    for row in token_rows
                    if {
                        "referent_resolution",
                        "divine_name_referent_policy",
                        "superscription_speaker_context",
                    }
                    & set(row["enrichment_lanes"])
                }
            ),
            "next_action": "Batch top critical tokens for Hebrew, alignment, and theology review.",
        },
        {
            "phase_id": "SEM-04",
            "phase": "Add semantic-role labels and reviewer signoff",
            "status": "not started",
            "evidence": (
                f"{completed_review} tokens have completed review rows; "
                "semantic-role labels remain absent in current canonical content."
            ),
            "token_count": sum(1 for row in token_rows if row["missing_semantic_role"]),
            "unit_count": sum(1 for row in unit_rows if row["missing_semantic_role_token_count"]),
            "next_action": (
                "Review imported or model-proposed roles against token alignment "
                "and source packets."
            ),
        },
    ]


def build_visual_data(
    token_rows: list[dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    pos_counts = Counter(
        row["part_of_speech"] or "unknown" for row in token_rows if row["missing_referent"]
    )
    missing_counts = Counter()
    for row in token_rows:
        missing_counts.update(row["missing_enrichments"])
    return {
        "top_token_rows": [
            {
                "label": f"{row['ref']} {row['surface']}",
                "value": row["enrichment_priority_score"],
            }
            for row in token_rows[:20]
        ],
        "top_unit_rows": [
            {
                "label": row["ref"],
                "value": row["max_enrichment_priority_score"],
            }
            for row in unit_rows[:20]
        ],
        "lane_rows": [
            {
                "label": row["lane"],
                "value": row["critical_token_count"],
            }
            for row in lane_rows
        ],
        "gap_rows": [
            {
                "label": row["label"],
                "value": row["missing_token_count"],
            }
            for row in gap_rows
        ],
        "pos_referent_gap_rows": [
            {"label": label, "value": count} for label, count in pos_counts.most_common()
        ],
        "missing_enrichment_rows": [
            {"label": label, "value": count} for label, count in missing_counts.most_common()
        ],
    }


def build_summary(
    token_rows: list[dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    gap_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    top = token_rows[0] if token_rows else {}
    return {
        "unit_count": len(unit_rows),
        "token_count": len(token_rows),
        "critical_enrichment_score_threshold": CRITICAL_ENRICHMENT_SCORE,
        "critical_enrichment_token_count": sum(
            1
            for row in token_rows
            if float(row["enrichment_priority_score"]) >= CRITICAL_ENRICHMENT_SCORE
        ),
        "critical_enrichment_unit_count": sum(
            1 for row in unit_rows if int(row["critical_enrichment_token_count"]) > 0
        ),
        "mean_enrichment_priority_score": mean(
            [float(row["enrichment_priority_score"]) for row in token_rows]
        ),
        "missing_semantic_role_token_count": sum(
            1 for row in token_rows if row["missing_semantic_role"]
        ),
        "missing_referent_token_count": sum(1 for row in token_rows if row["missing_referent"]),
        "missing_syntax_role_token_count": sum(
            1 for row in token_rows if row["missing_syntax_role"]
        ),
        "missing_stem_token_count": sum(1 for row in token_rows if row["missing_stem"]),
        "semantic_role_coverage_pct": pct(
            sum(1 for row in token_rows if not row["missing_semantic_role"]),
            len(token_rows),
        ),
        "referent_coverage_pct": pct(
            sum(1 for row in token_rows if not row["missing_referent"]),
            len(token_rows),
        ),
        "suffix_pronoun_token_count": sum(
            1 for row in token_rows if row["compiler_suffix_pronoun"]
        ),
        "construct_state_token_count": sum(
            1 for row in token_rows if row["compiler_construct_state"]
        ),
        "verb_token_count": sum(1 for row in token_rows if row["part_of_speech"] == "verb"),
        "divine_name_token_count": sum(1 for row in token_rows if row["is_divine_name_token"]),
        "superscription_token_count": sum(
            1 for row in token_rows if row["is_superscription_token"]
        ),
        "anchor_token_count": sum(1 for row in token_rows if row["anchor_strength"]),
        "cultural_domain_token_count": sum(
            1 for row in token_rows if int(row["cultural_domain_count"]) > 0
        ),
        "defense_exhibit_token_count": sum(1 for row in token_rows if row["in_defense_exhibit"]),
        "source_approved_token_count": sum(
            1 for row in token_rows if row["source_approval_count"] > 0
        ),
        "review_completed_token_count": sum(
            1 for row in token_rows if row["completed_review_row_count"] > 0
        ),
        "lane_count": len(lane_rows),
        "gap_count": len(gap_rows),
        "top_token_id": top.get("token_id", ""),
        "top_token_ref": top.get("ref", ""),
        "top_token_surface": top.get("surface", ""),
        "top_token_gloss": top.get("display_gloss", ""),
        "top_token_score": top.get("enrichment_priority_score", 0.0),
        "top_unit_ref": unit_rows[0]["ref"] if unit_rows else "",
        "top_unit_score": unit_rows[0]["max_enrichment_priority_score"] if unit_rows else 0.0,
        "authority_verdict": (
            "Semantic/referent enrichment is fully blocked for authority claims until source "
            "approval, import or derivation, reviewer adjudication, audit, and release gates "
            "exist; the roadmap is only a prioritized work queue."
        ),
    }


def build_report() -> dict[str, Any]:
    data = {key: load_json(path) for key, path in SOURCE_PATHS.items()}
    token_rows = build_token_rows(data)
    unit_rows = build_unit_rows(token_rows)
    lane_rows = build_lane_rows(token_rows)
    gap_rows = build_gap_rows(token_rows)
    phase_rows = build_phase_rows(token_rows, unit_rows, lane_rows, data)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "semantic/referent enrichment roadmap generated; not authority signoff",
        "source_paths": {key: str(path.relative_to(ROOT)) for key, path in SOURCE_PATHS.items()},
        "authority_policy": AUTHORITY_POLICY,
        "summary": build_summary(token_rows, unit_rows, lane_rows, gap_rows),
        "token_rows": token_rows,
        "unit_rows": unit_rows,
        "lane_rows": lane_rows,
        "gap_rows": gap_rows,
        "phase_rows": phase_rows,
        "visual_data": build_visual_data(token_rows, unit_rows, lane_rows, gap_rows),
    }


def style_block() -> str:
    return """
    :root { color-scheme: light; --ink: #1f2528; --muted: #657076; --line: #d7dedf; }
    body {
      font-family: Inter, Arial, sans-serif;
      color: var(--ink);
      margin: 0;
      background: #f7f8f6;
    }
    header, section { max-width: 1240px; margin: 0 auto; padding: 28px 32px; }
    header { border-bottom: 1px solid var(--line); background: #ffffff; }
    h1, h2 { margin: 0 0 12px; letter-spacing: 0; }
    p { color: var(--muted); line-height: 1.5; }
    .warning {
      border-left: 4px solid #9b3d3d;
      background: #fff5f2;
      padding: 12px 14px;
      margin: 16px 0;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
    }
    .metric { background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
    .metric strong { display: block; font-size: 24px; margin-bottom: 4px; }
    .metric span { color: var(--muted); font-size: 13px; }
    .chart {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      margin: 16px 0;
      overflow-x: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      margin: 16px 0 28px;
      font-size: 13px;
    }
    th, td {
      border: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }
    th { background: #eaf0ef; }
    td { max-width: 340px; overflow-wrap: anywhere; }
    .hebrew { direction: rtl; font-family: "SBL Hebrew", "Ezra SIL", serif; font-size: 18px; }
    """


def metric_cards(items: list[tuple[str, Any, str]]) -> str:
    return (
        '<section class="metrics">'
        + "".join(
            f'<div class="metric"><span>{esc(label)}</span><strong>{esc(value)}</strong>'
            f"<span>{esc(note)}</span></div>"
            for label, value, note in items
        )
        + "</section>"
    )


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    limit: int = 12,
) -> str:
    rows = rows[:limit]
    width = 1060
    row_h = 32
    label_w = 330
    chart_w = width - label_w - 80
    height = max(44, 24 + row_h * len(rows))
    max_value = max([float(row.get(value_key) or 0) for row in rows] or [1.0])
    parts = [f'<svg role="img" aria-label="{esc(aria_label)}" width="{width}" height="{height}">']
    for idx, row in enumerate(rows):
        y = 18 + idx * row_h
        value = float(row.get(value_key) or 0)
        bar_w = 0 if not max_value else int(chart_w * value / max_value)
        parts.append(
            f'<text x="0" y="{y + 16}" font-size="12">{esc(row.get(label_key, ""))}</text>'
        )
        parts.append(
            f'<rect x="{label_w}" y="{y}" width="{bar_w}" height="20" fill="{color}"></rect>'
        )
        parts.append(
            f'<text x="{label_w + bar_w + 8}" y="{y + 15}" font-size="12">{value:g}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "".join(
        "<tr>"
        + "".join(
            f'<td class="{"hebrew" if header in {"Surface", "Hebrew"} else ""}">{esc(value)}</td>'
            for header, value in zip(headers, row, strict=False)
        )
        + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    token_rows = [
        [
            row["rank"],
            row["ref"],
            row["token_id"],
            row["surface"],
            row["lemma"],
            row["strong"],
            row["display_gloss"],
            row["part_of_speech"],
            row["morph_code"],
            f"{row['enrichment_priority_score']:.2f}",
            row["anchor_strength"] or "none",
            row["outside_psalms_count"],
            row["cultural_domain_count"],
            row["missing_enrichment_count"],
            "; ".join(row["enrichment_lanes"][:6]),
            row["recommended_next_action"],
        ]
        for row in report["token_rows"][:50]
    ]
    unit_rows = [
        [
            row["rank"],
            row["ref"],
            row["token_count"],
            f"{row['max_enrichment_priority_score']:.2f}",
            row["critical_enrichment_token_count"],
            row["suffix_pronoun_token_count"],
            row["verb_token_count"],
            row["anchor_token_count"],
            row["cultural_domain_token_count"],
            row["divine_name_token_count"],
            "; ".join(row["primary_enrichment_lanes"]),
            row["top_token_surfaces"],
        ]
        for row in report["unit_rows"][:30]
    ]
    lane_rows = [
        [
            row["lane"],
            row["token_count"],
            f"{row['token_pct']:.2f}%",
            row["unit_count"],
            row["critical_token_count"],
            f"{row['mean_enrichment_priority_score']:.2f}",
            row["top_ref"],
            row["top_surface"],
            "; ".join(row["required_review_roles"]),
            row["next_action"],
        ]
        for row in report["lane_rows"]
    ]
    gap_rows = [
        [
            row["label"],
            row["missing_token_count"],
            f"{row['missing_pct']:.2f}%",
            row["coverage_pct"],
            row["top_ref"],
            row["top_surface"],
            row["authority_effect"],
        ]
        for row in report["gap_rows"]
    ]
    phase_rows = [
        [
            row["phase_id"],
            row["phase"],
            row["status"],
            row["token_count"],
            row["unit_count"],
            row["evidence"],
            row["next_action"],
        ]
        for row in report["phase_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Semantic/Referent Enrichment Roadmap</title>
  <style>{style_block()}</style>
</head>
<body>
<header>
  <h1>Semantic/Referent Enrichment Roadmap</h1>
  <p>
    Corpus-wide roadmap for the missing enrichment layer that blocks high-trust
    discourse, referent, speaker/addressee, semantic-role, and verbal-argument
    claims in Hebrew-to-English Psalms translation.
  </p>
  <div class="warning">{esc(report["authority_policy"])}</div>
  {
        metric_cards(
            [
                ("Tokens", summary["token_count"], "Psalm Hebrew token records surveyed."),
                (
                    "Critical Tokens",
                    summary["critical_enrichment_token_count"],
                    f"Priority score >= {summary['critical_enrichment_score_threshold']:.0f}.",
                ),
                (
                    "Semantic Coverage",
                    f"{summary['semantic_role_coverage_pct']:.2f}%",
                    f"{summary['missing_semantic_role_token_count']} tokens missing.",
                ),
                (
                    "Referent Coverage",
                    f"{summary['referent_coverage_pct']:.2f}%",
                    f"{summary['missing_referent_token_count']} tokens missing.",
                ),
                (
                    "Suffix Pronouns",
                    summary["suffix_pronoun_token_count"],
                    "High-pressure referent-resolution tokens.",
                ),
                (
                    "Top Token",
                    summary["top_token_ref"],
                    f"{summary['top_token_surface']} {summary['top_token_score']:.2f}.",
                ),
            ]
        )
    }
</header>

<section>
  <h2>Priority Frontiers</h2>
  <div class="chart">{
        svg_horizontal_bars(
            visual["top_token_rows"],
            label_key="label",
            value_key="value",
            aria_label="Top semantic referent enrichment tokens",
            color="#9b3d3d",
        )
    }</div>
  <div class="chart">{
        svg_horizontal_bars(
            visual["top_unit_rows"],
            label_key="label",
            value_key="value",
            aria_label="Top semantic referent enrichment units",
            color="#2f6f73",
        )
    }</div>
  <div class="chart">{
        svg_horizontal_bars(
            visual["lane_rows"],
            label_key="label",
            value_key="value",
            aria_label="Critical tokens by semantic referent lane",
            color="#7c5b2f",
        )
    }</div>
  {
        table(
            [
                "Rank",
                "Ref",
                "Token",
                "Surface",
                "Lemma",
                "Strong",
                "Gloss",
                "POS",
                "Morph",
                "Score",
                "Anchor",
                "Outside Psalms",
                "Culture",
                "Missing",
                "Lanes",
                "Next Action",
            ],
            token_rows,
        )
    }
  {
        table(
            [
                "Rank",
                "Ref",
                "Tokens",
                "Max Score",
                "Critical",
                "Suffix",
                "Verbs",
                "Anchors",
                "Culture",
                "Divine",
                "Primary Lanes",
                "Top Surfaces",
            ],
            unit_rows,
        )
    }
</section>

<section>
  <h2>Gap And Lane Controls</h2>
  <div class="chart">{
        svg_horizontal_bars(
            visual["gap_rows"],
            label_key="label",
            value_key="value",
            aria_label="Missing enrichment counts",
            color="#9b3d3d",
        )
    }</div>
  <div class="chart">{
        svg_horizontal_bars(
            visual["pos_referent_gap_rows"],
            label_key="label",
            value_key="value",
            aria_label="Referent gaps by part of speech",
            color="#2f6f73",
        )
    }</div>
  {
        table(
            [
                "Field",
                "Missing",
                "Missing %",
                "Coverage %",
                "Top Ref",
                "Surface",
                "Authority Effect",
            ],
            gap_rows,
        )
    }
  {
        table(
            [
                "Lane",
                "Tokens",
                "Pct",
                "Units",
                "Critical",
                "Mean Score",
                "Top Ref",
                "Surface",
                "Roles",
                "Next Action",
            ],
            lane_rows,
        )
    }
  {table(["Phase", "Label", "Status", "Tokens", "Units", "Evidence", "Next Action"], phase_rows)}
</section>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--token-csv-output", type=Path, default=DEFAULT_TOKEN_CSV_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--lane-csv-output", type=Path, default=DEFAULT_LANE_CSV_OUTPUT)
    parser.add_argument("--gap-csv-output", type=Path, default=DEFAULT_GAP_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.token_csv_output, report["token_rows"])
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.lane_csv_output, report["lane_rows"])
    write_csv(args.gap_csv_output, report["gap_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.token_csv_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.lane_csv_output}")
    print(f"Wrote {args.gap_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
