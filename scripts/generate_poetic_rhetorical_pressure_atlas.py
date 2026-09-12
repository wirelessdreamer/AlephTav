from __future__ import annotations

import argparse
import csv
import html
import json
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = ROOT / "content" / "psalms"
REPORT_ROOT = ROOT / "reports" / "research"

WITNESS_DIVERGENCE_PATH = REPORT_ROOT / "witness_divergence_report.json"
DIVINE_NAME_PATH = REPORT_ROOT / "divine_name_policy_report.json"
SUPERSCRIPTION_PATH = REPORT_ROOT / "superscription_context_report.json"
CULTURAL_ATLAS_PATH = REPORT_ROOT / "cultural_historical_domain_atlas.json"
CROSS_REFERENCE_PATH = REPORT_ROOT / "canonical_cross_reference_atlas.json"
CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
RECEPTION_BOUNDARY_PATH = REPORT_ROOT / "reception_interpretation_boundary.json"
RECEPTION_DIVERGENCE_PATH = REPORT_ROOT / "reception_divergence_atlas.json"
PRIORITY_DOSSIER_PATH = REPORT_ROOT / "doctoral_priority_dossier_atlas.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "poetic_rhetorical_pressure_atlas.json"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "poetic_rhetorical_pressure_atlas.html"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "poetic_rhetorical_pressure_atlas_units.csv"
DEFAULT_PSALM_CSV_OUTPUT = REPORT_ROOT / "poetic_rhetorical_pressure_atlas_psalms.csv"
DEFAULT_FEATURE_CSV_OUTPUT = REPORT_ROOT / "poetic_rhetorical_pressure_atlas_features.csv"

CONTENT_POS = {"noun", "verb", "adjective", "adverb", "pronoun"}
VOLITIVE_MOOD_CODES = {"v", "j", "h"}

ACROSTIC_PSALM_PROFILES: dict[str, dict[str, str]] = {
    "ps009": {
        "profile": "traditional_partial_or_paired_acrostic",
        "review_note": "Treat with Psalm 10 and verify stanza boundaries before wording impact.",
    },
    "ps010": {
        "profile": "traditional_partial_or_paired_acrostic",
        "review_note": "Treat with Psalm 9 and verify stanza boundaries before wording impact.",
    },
    "ps025": {
        "profile": "traditional_irregular_alphabetic_acrostic",
        "review_note": (
            "Review alphabetic pressure, omissions, and additions before lyric handling."
        ),
    },
    "ps034": {
        "profile": "traditional_irregular_alphabetic_acrostic",
        "review_note": (
            "Review alphabetic pressure, omissions, and additions before lyric handling."
        ),
    },
    "ps037": {
        "profile": "traditional_alphabetic_acrostic",
        "review_note": "Review stanza grouping and repeated wisdom vocabulary.",
    },
    "ps111": {
        "profile": "traditional_alphabetic_acrostic",
        "review_note": "Review compact alphabetic cola before lyric layer decisions.",
    },
    "ps112": {
        "profile": "traditional_alphabetic_acrostic",
        "review_note": "Review compact alphabetic cola before lyric layer decisions.",
    },
    "ps119": {
        "profile": "large_stanza_alphabetic_acrostic",
        "review_note": "Preserve stanza, Torah vocabulary, and repeated lexeme strategy.",
    },
    "ps145": {
        "profile": "traditional_alphabetic_acrostic_with_textual_pressure",
        "review_note": "Review alphabetic structure and textual-witness implications.",
    },
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def maybe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_json(path)


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


def fmt_pct(value: Any) -> str:
    return f"{float(value):.2f}%"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def unit_lookup(report: dict[str, Any], row_key: str) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in report.get(row_key, []) if row.get("unit_id")}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def text_excerpt(text: str, limit: int = 155) -> str:
    compact = clean_text(text)
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def witness_texts(unit: dict[str, Any]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for witness in unit.get("witnesses", []):
        source_id = str(witness.get("source_id", ""))
        if source_id in {"kjv", "asv", "web"}:
            texts[source_id] = clean_text(witness.get("text", ""))
    return texts


def morph_parts(token: dict[str, Any]) -> list[str]:
    return [part for part in str(token.get("morph_code") or "").split("/") if part]


def is_volitive_verb(token: dict[str, Any]) -> bool:
    for part in morph_parts(token):
        if part.startswith("V") and len(part) > 2 and part[2].lower() in VOLITIVE_MOOD_CODES:
            return True
    readable = str(token.get("morph_readable") or "").lower()
    return any(term in readable for term in ("imperative", "jussive", "cohortative"))


def suffix_pronoun(token: dict[str, Any]) -> dict[str, Any]:
    features = token.get("compiler_features") or {}
    value = features.get("suffix_pronoun")
    return value if isinstance(value, dict) else {}


def lemma_label(token: dict[str, Any]) -> str:
    lemma = clean_text(token.get("lemma", ""))
    strong = clean_text(token.get("strong", ""))
    gloss = clean_text(token.get("display_gloss", ""))
    if lemma and token.get("part_of_speech") != "suffix":
        return lemma
    if strong and gloss:
        return f"{strong} {gloss}"
    return strong or gloss


def normalized_label(token: dict[str, Any]) -> str:
    normalized = clean_text(token.get("normalized", ""))
    if normalized:
        return normalized
    return clean_text(token.get("surface", ""))


def hebrew_initial_letter(unit: dict[str, Any]) -> str:
    for token in unit.get("tokens", []):
        if token.get("part_of_speech") not in CONTENT_POS:
            continue
        for char in str(token.get("surface") or ""):
            if unicodedata.category(char).startswith("M"):
                continue
            codepoint = ord(char)
            if 0x05D0 <= codepoint <= 0x05EA:
                return char
    return ""


def content_lemma_set(row: dict[str, Any]) -> set[str]:
    return set(row.get("_content_lemmas", []))


def adjacent_overlap(left: dict[str, Any], right: dict[str, Any]) -> tuple[int, float]:
    left_lemmas = content_lemma_set(left)
    right_lemmas = content_lemma_set(right)
    if not left_lemmas or not right_lemmas:
        return 0, 0.0
    intersection = left_lemmas & right_lemmas
    union = left_lemmas | right_lemmas
    return len(intersection), round(len(intersection) / len(union), 4)


def base_unit_row(path: Path) -> dict[str, Any]:
    unit = load_json(path)
    tokens = unit.get("tokens", [])
    content_tokens = [token for token in tokens if token.get("part_of_speech") in CONTENT_POS]
    lemmas = [lemma_label(token) for token in content_tokens if lemma_label(token)]
    normalized = [normalized_label(token) for token in content_tokens if normalized_label(token)]
    lemma_counts: Counter[str] = Counter(lemmas)
    form_counts: Counter[str] = Counter(normalized)
    repeated_lemmas = [
        {"lemma": lemma, "count": count} for lemma, count in lemma_counts.most_common() if count > 1
    ]
    repeated_forms = [
        {"form": form, "count": count} for form, count in form_counts.most_common() if count > 1
    ]
    volitive_tokens = [token for token in tokens if is_volitive_verb(token)]
    suffixes = [suffix_pronoun(token) for token in tokens if suffix_pronoun(token)]
    second_person = [
        suffix for suffix in suffixes if str(suffix.get("person", "")).lower() == "second"
    ]
    first_person = [
        suffix for suffix in suffixes if str(suffix.get("person", "")).lower() == "first"
    ]
    construct_count = sum(
        1 for token in tokens if bool((token.get("compiler_features") or {}).get("construct_state"))
    )
    same_psalm_echo_count = sum(
        1 for token in content_tokens if len(token.get("same_psalm_occurrence_refs") or []) > 1
    )
    discourse_marker_count = sum(
        1 for token in tokens if (token.get("compiler_features") or {}).get("discourse_marker")
    )
    conjunction_count = sum(
        1
        for token in tokens
        if token.get("part_of_speech") == "conjunction"
        or str(token.get("morph_code") or "").startswith("C/")
    )
    verb_count = sum(1 for token in tokens if token.get("part_of_speech") == "verb")
    psalm_id = str(unit.get("psalm_id", ""))
    acrostic_profile = ACROSTIC_PSALM_PROFILES.get(psalm_id, {})
    texts = witness_texts(unit)
    return {
        "unit_id": unit["unit_id"],
        "ref": unit.get("ref", ""),
        "psalm_id": psalm_id,
        "source_hebrew": unit.get("source_hebrew", ""),
        "token_count": len(tokens),
        "content_token_count": len(content_tokens),
        "verb_token_count": verb_count,
        "verb_density_pct": pct(verb_count, len(tokens)),
        "volitive_token_count": len(volitive_tokens),
        "volitive_surfaces": [token.get("surface", "") for token in volitive_tokens],
        "volitive_glosses": [token.get("display_gloss", "") for token in volitive_tokens],
        "suffix_pronoun_token_count": len(suffixes),
        "second_person_suffix_token_count": len(second_person),
        "first_person_suffix_token_count": len(first_person),
        "construct_state_token_count": construct_count,
        "same_psalm_echo_token_count": same_psalm_echo_count,
        "discourse_marker_token_count": discourse_marker_count,
        "conjunction_token_count": conjunction_count,
        "repeated_lemma_type_count": len(repeated_lemmas),
        "repeated_lemma_token_excess": sum(row["count"] - 1 for row in repeated_lemmas),
        "repeated_form_type_count": len(repeated_forms),
        "repeated_form_token_excess": sum(row["count"] - 1 for row in repeated_forms),
        "top_repeated_lemmas": repeated_lemmas[:12],
        "top_repeated_forms": repeated_forms[:12],
        "initial_hebrew_letter": hebrew_initial_letter(unit),
        "acrostic_psalm_proxy": bool(acrostic_profile),
        "acrostic_profile": acrostic_profile.get("profile", ""),
        "acrostic_review_note": acrostic_profile.get("review_note", ""),
        "kjv_excerpt": text_excerpt(texts.get("kjv", "")),
        "asv_excerpt": text_excerpt(texts.get("asv", "")),
        "web_excerpt": text_excerpt(texts.get("web", "")),
        "_content_lemmas": lemmas,
    }


def add_adjacent_features(rows: list[dict[str, Any]]) -> None:
    by_psalm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_psalm[str(row["psalm_id"])].append(row)
    for psalm_rows in by_psalm.values():
        for index, row in enumerate(psalm_rows):
            prev_count, prev_jaccard = (0, 0.0)
            next_count, next_jaccard = (0, 0.0)
            if index > 0:
                prev_count, prev_jaccard = adjacent_overlap(row, psalm_rows[index - 1])
            if index < len(psalm_rows) - 1:
                next_count, next_jaccard = adjacent_overlap(row, psalm_rows[index + 1])
            row["previous_unit_lemma_overlap_count"] = prev_count
            row["previous_unit_lemma_jaccard"] = prev_jaccard
            row["next_unit_lemma_overlap_count"] = next_count
            row["next_unit_lemma_jaccard"] = next_jaccard
            row["adjacent_lemma_overlap_count"] = max(prev_count, next_count)
            row["adjacent_lemma_jaccard"] = max(prev_jaccard, next_jaccard)


def feature_flags(
    row: dict[str, Any],
    *,
    witness: dict[str, Any],
    divine: dict[str, Any],
    superscription: dict[str, Any],
    cultural: dict[str, Any],
    cross_reference: dict[str, Any],
    claim: dict[str, Any],
    reception_boundary: dict[str, Any],
    reception_divergence: dict[str, Any],
    dossier: dict[str, Any],
) -> list[str]:
    flags = []
    if int(row["repeated_lemma_token_excess"]) >= 2:
        flags.append("high_lemma_repetition")
    if int(row["same_psalm_echo_token_count"]) >= 3:
        flags.append("same_psalm_echo_pressure")
    if (
        int(row["adjacent_lemma_overlap_count"]) >= 2
        or float(row["adjacent_lemma_jaccard"]) >= 0.25
    ):
        flags.append("adjacent_parallelism_proxy")
    if int(row["volitive_token_count"]):
        flags.append("volitive_mood_pressure")
    if int(row["second_person_suffix_token_count"]) >= 2 or (
        int(row["second_person_suffix_token_count"]) and int(row["volitive_token_count"])
    ):
        flags.append("second_person_address_pressure")
    if int(row["verb_token_count"]) >= 3 and float(row["verb_density_pct"]) >= 35:
        flags.append("dense_verbal_sequence")
    if int(row["construct_state_token_count"]) >= 2:
        flags.append("construct_chain_pressure")
    if int(row["conjunction_token_count"]) >= 3:
        flags.append("conjunction_chain_pressure")
    if bool(row["acrostic_psalm_proxy"]):
        flags.append("acrostic_psalm_proxy")
    if float(witness.get("mean_english_witness_divergence_pct") or 0) >= 55:
        flags.append("high_english_witness_divergence")
    if divine:
        flags.append("divine_name_policy_overlap")
    if superscription:
        flags.append("superscription_or_performance_overlap")
    if int(cultural.get("domain_count") or 0) >= 3 or cultural.get("ancient_culture_pressure"):
        flags.append("cultural_historical_overlap")
    if int(cross_reference.get("anchor_token_count") or 0) >= 5:
        flags.append("whole_tanakh_anchor_pressure")
    if claim.get("reception_sensitive") or reception_boundary.get("reception_sensitive"):
        flags.append("reception_sensitive")
    if reception_divergence.get("jewish_christian_separation_required"):
        flags.append("jewish_christian_reception_split")
    if dossier:
        flags.append("doctoral_dossier_overlap")
    return sorted(dict.fromkeys(flags))


def priority_score(
    row: dict[str, Any],
    *,
    witness: dict[str, Any],
    divine: dict[str, Any],
    superscription: dict[str, Any],
    cultural: dict[str, Any],
    cross_reference: dict[str, Any],
    claim: dict[str, Any],
    reception_boundary: dict[str, Any],
    reception_divergence: dict[str, Any],
    dossier: dict[str, Any],
    flags: list[str],
) -> float:
    score = float(row["content_token_count"]) * 1.4
    score += float(row["repeated_lemma_token_excess"]) * 5.0
    score += float(row["repeated_lemma_type_count"]) * 4.0
    score += float(row["repeated_form_token_excess"]) * 2.5
    score += float(row["same_psalm_echo_token_count"]) * 1.6
    score += float(row["adjacent_lemma_overlap_count"]) * 4.0
    score += float(row["adjacent_lemma_jaccard"]) * 45.0
    score += float(row["volitive_token_count"]) * 8.0
    score += float(row["second_person_suffix_token_count"]) * 5.0
    score += float(row["first_person_suffix_token_count"]) * 2.5
    score += float(row["construct_state_token_count"]) * 3.0
    score += float(row["conjunction_token_count"]) * 1.5
    score += float(row["verb_density_pct"]) / 5.0
    if row["acrostic_psalm_proxy"]:
        score += 16.0
    score += min(20.0, float(witness.get("mean_english_witness_divergence_pct") or 0) / 3.0)
    score += min(26.0, float(witness.get("priority_score") or 0) / 6.0)
    score += float(divine.get("divine_title_token_count") or 0) * 9.0
    score += float(superscription.get("context_token_count") or 0) * 6.0
    score += float(cultural.get("domain_count") or 0) * 7.0
    score += min(26.0, float(cross_reference.get("priority_score") or 0) / 14.0)
    score += float(cross_reference.get("high_value_anchor_count") or 0) * 3.0
    score += min(18.0, float(claim.get("claim_risk_score") or 0) / 10.0)
    score += min(18.0, float(reception_boundary.get("boundary_risk_score") or 0) / 10.0)
    if claim.get("ancient_culture_pressure") or reception_boundary.get("ancient_culture_pressure"):
        score += 9.0
    if claim.get("textual_witness_pressure") or reception_boundary.get("textual_witness_pressure"):
        score += 8.0
    if claim.get("reception_sensitive") or reception_boundary.get("reception_sensitive"):
        score += 10.0
    if reception_divergence.get("jewish_christian_separation_required"):
        score += 18.0
    if dossier:
        score += 20.0
        score += min(18.0, float(dossier.get("doctoral_dossier_priority_score") or 0) / 35.0)
    score += min(18.0, max(0, len(flags) - 2) * 2.5)
    return round(score, 2)


def pressure_band(score: float) -> str:
    if score >= 180:
        return "critical"
    if score >= 150:
        return "highest"
    if score >= 115:
        return "high"
    if score >= 80:
        return "elevated"
    return "watch"


def build_unit_rows(
    witnesses: dict[str, dict[str, Any]],
    divine_units: dict[str, dict[str, Any]],
    superscription_units: dict[str, dict[str, Any]],
    cultural_units: dict[str, dict[str, Any]],
    cross_reference_units: dict[str, dict[str, Any]],
    claims: dict[str, dict[str, Any]],
    reception_boundaries: dict[str, dict[str, Any]],
    reception_divergences: dict[str, dict[str, Any]],
    dossiers: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [base_unit_row(path) for path in sorted(CONTENT_ROOT.glob("ps*/*.v*.json"))]
    add_adjacent_features(rows)
    final_rows = []
    for row in rows:
        unit_id = str(row["unit_id"])
        witness = witnesses.get(unit_id, {})
        divine = divine_units.get(unit_id, {})
        superscription = superscription_units.get(unit_id, {})
        cultural = cultural_units.get(unit_id, {})
        cross_reference = cross_reference_units.get(unit_id, {})
        claim = claims.get(unit_id, {})
        reception_boundary = reception_boundaries.get(unit_id, {})
        reception_divergence = reception_divergences.get(unit_id, {})
        dossier = dossiers.get(unit_id, {})
        flags = feature_flags(
            row,
            witness=witness,
            divine=divine,
            superscription=superscription,
            cultural=cultural,
            cross_reference=cross_reference,
            claim=claim,
            reception_boundary=reception_boundary,
            reception_divergence=reception_divergence,
            dossier=dossier,
        )
        score = priority_score(
            row,
            witness=witness,
            divine=divine,
            superscription=superscription,
            cultural=cultural,
            cross_reference=cross_reference,
            claim=claim,
            reception_boundary=reception_boundary,
            reception_divergence=reception_divergence,
            dossier=dossier,
            flags=flags,
        )
        visible_row = {key: value for key, value in row.items() if not key.startswith("_")}
        visible_row.update(
            {
                "feature_flags": flags,
                "feature_flag_count": len(flags),
                "poetic_rhetorical_priority_score": score,
                "pressure_band": pressure_band(score),
                "witness_divergence_pct": witness.get(
                    "mean_english_witness_divergence_pct",
                    0,
                ),
                "witness_priority_score": witness.get("priority_score", 0),
                "divine_name_overlap": bool(divine),
                "divine_title_token_count": divine.get("divine_title_token_count", 0),
                "superscription_context_overlap": bool(superscription),
                "superscription_context_token_count": superscription.get(
                    "context_token_count",
                    0,
                ),
                "cultural_domain_count": cultural.get("domain_count", 0),
                "cultural_domain_labels": cultural.get("domain_labels", []),
                "cross_reference_anchor_token_count": cross_reference.get(
                    "anchor_token_count",
                    0,
                ),
                "cross_reference_high_value_anchor_count": cross_reference.get(
                    "high_value_anchor_count",
                    0,
                ),
                "reception_sensitive": bool(
                    claim.get("reception_sensitive")
                    or reception_boundary.get("reception_sensitive")
                    or reception_divergence.get("reception_sensitive")
                ),
                "jewish_christian_separation_required": bool(
                    reception_divergence.get("jewish_christian_separation_required")
                    or dossier.get("jewish_christian_separation_required")
                ),
                "claim_risk_score": claim.get("claim_risk_score", 0),
                "boundary_risk_score": reception_boundary.get("boundary_risk_score", 0),
                "doctoral_dossier_overlap": bool(dossier),
                "unit_authority_score_pct": dossier.get("unit_authority_score_pct", ""),
                "recommended_review_roles": recommended_review_roles(flags),
            }
        )
        final_rows.append(visible_row)
    return sorted(
        final_rows,
        key=lambda item: float(item["poetic_rhetorical_priority_score"]),
        reverse=True,
    )


def recommended_review_roles(flags: list[str]) -> list[str]:
    roles = {"Hebrew", "poetic"}
    if "high_english_witness_divergence" in flags:
        roles.update({"textual", "alignment"})
    if "divine_name_policy_overlap" in flags or "jewish_christian_reception_split" in flags:
        roles.update({"theology", "reception"})
    if "cultural_historical_overlap" in flags or "superscription_or_performance_overlap" in flags:
        roles.add("ancient_cultural_context")
    if "whole_tanakh_anchor_pressure" in flags:
        roles.add("canonical_context")
    if "second_person_address_pressure" in flags:
        roles.add("lyric")
    return sorted(roles)


def build_psalm_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        grouped[str(row["psalm_id"])].append(row)
    rows = []
    for psalm_id, psalm_units in grouped.items():
        scores = [float(row["poetic_rhetorical_priority_score"]) for row in psalm_units]
        feature_counts: Counter[str] = Counter()
        initial_letters: Counter[str] = Counter()
        for row in psalm_units:
            feature_counts.update(row["feature_flags"])
            if row["initial_hebrew_letter"]:
                initial_letters[str(row["initial_hebrew_letter"])] += 1
        top = max(psalm_units, key=lambda row: float(row["poetic_rhetorical_priority_score"]))
        acrostic_profile = ACROSTIC_PSALM_PROFILES.get(psalm_id, {})
        rows.append(
            {
                "psalm_id": psalm_id,
                "unit_count": len(psalm_units),
                "mean_poetic_rhetorical_score": mean(scores),
                "max_poetic_rhetorical_score": max(scores) if scores else 0.0,
                "high_pressure_unit_count": sum(
                    1
                    for row in psalm_units
                    if row["pressure_band"] in {"critical", "highest", "high"}
                ),
                "volitive_unit_count": sum(
                    1 for row in psalm_units if int(row["volitive_token_count"]) > 0
                ),
                "repetition_unit_count": sum(
                    1 for row in psalm_units if int(row["repeated_lemma_token_excess"]) > 0
                ),
                "adjacent_parallelism_proxy_unit_count": sum(
                    1 for row in psalm_units if "adjacent_parallelism_proxy" in row["feature_flags"]
                ),
                "acrostic_psalm_proxy": bool(acrostic_profile),
                "acrostic_profile": acrostic_profile.get("profile", ""),
                "distinct_initial_hebrew_letter_count": len(initial_letters),
                "top_initial_hebrew_letters": dict(initial_letters.most_common(8)),
                "top_unit_id": top["unit_id"],
                "top_ref": top["ref"],
                "top_priority_score": top["poetic_rhetorical_priority_score"],
                "top_feature_flags": top["feature_flags"],
            }
        )
    return sorted(rows, key=lambda row: float(row["mean_poetic_rhetorical_score"]), reverse=True)


def build_feature_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    score_sums: Counter[str] = Counter()
    top_refs: dict[str, tuple[str, float]] = {}
    for row in unit_rows:
        score = float(row["poetic_rhetorical_priority_score"])
        for flag in row["feature_flags"]:
            counts[flag] += 1
            score_sums[flag] += int(score * 100)
            if flag not in top_refs or score > top_refs[flag][1]:
                top_refs[flag] = (str(row["ref"]), score)
    return [
        {
            "feature": feature,
            "unit_count": count,
            "unit_pct": pct(count, len(unit_rows)),
            "mean_priority_score": round(score_sums[feature] / count / 100, 2),
            "top_ref": top_refs.get(feature, ("", 0.0))[0],
            "top_priority_score": top_refs.get(feature, ("", 0.0))[1],
        }
        for feature, count in counts.most_common()
    ]


def chart_rows(rows: list[dict[str, Any]], label_key: str, value_key: str) -> list[dict[str, Any]]:
    return [{"label": str(row[label_key]), "value": row[value_key]} for row in rows]


def build_report() -> dict[str, Any]:
    witness_report = maybe_load_json(WITNESS_DIVERGENCE_PATH)
    divine_report = maybe_load_json(DIVINE_NAME_PATH)
    superscription_report = maybe_load_json(SUPERSCRIPTION_PATH)
    cultural_report = maybe_load_json(CULTURAL_ATLAS_PATH)
    cross_reference_report = maybe_load_json(CROSS_REFERENCE_PATH)
    claim_report = maybe_load_json(CLAIM_MATRIX_PATH)
    reception_boundary_report = maybe_load_json(RECEPTION_BOUNDARY_PATH)
    reception_divergence_report = maybe_load_json(RECEPTION_DIVERGENCE_PATH)
    dossier_report = maybe_load_json(PRIORITY_DOSSIER_PATH)

    unit_rows = build_unit_rows(
        unit_lookup(witness_report, "unit_rows"),
        unit_lookup(divine_report, "unit_rows"),
        unit_lookup(superscription_report, "unit_rows"),
        unit_lookup(cultural_report, "unit_rows"),
        unit_lookup(cross_reference_report, "unit_rows"),
        unit_lookup(claim_report, "unit_claim_rows"),
        unit_lookup(reception_boundary_report, "unit_boundary_rows"),
        unit_lookup(reception_divergence_report, "unit_rows"),
        unit_lookup(dossier_report, "unit_rows"),
    )
    psalm_rows = build_psalm_rows(unit_rows)
    feature_rows = build_feature_rows(unit_rows)
    high_pressure_rows = [
        row for row in unit_rows if row["pressure_band"] in {"critical", "highest", "high"}
    ]
    acrostic_rows = [row for row in unit_rows if row["acrostic_psalm_proxy"]]
    volitive_rows = [row for row in unit_rows if int(row["volitive_token_count"]) > 0]
    repetition_rows = [row for row in unit_rows if int(row["repeated_lemma_token_excess"]) > 0]
    adjacent_rows = [
        row for row in unit_rows if "adjacent_parallelism_proxy" in row["feature_flags"]
    ]
    second_person_rows = [
        row for row in unit_rows if "second_person_address_pressure" in row["feature_flags"]
    ]
    critical_rows = [row for row in unit_rows if row["pressure_band"] == "critical"]
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "poetic/rhetorical pressure atlas generated; not literary signoff",
        "source_paths": {
            "content_root": "content/psalms",
            "witness_divergence": str(WITNESS_DIVERGENCE_PATH.relative_to(ROOT)),
            "divine_name_policy": str(DIVINE_NAME_PATH.relative_to(ROOT)),
            "superscription_context": str(SUPERSCRIPTION_PATH.relative_to(ROOT)),
            "cultural_historical_atlas": str(CULTURAL_ATLAS_PATH.relative_to(ROOT)),
            "canonical_cross_reference": str(CROSS_REFERENCE_PATH.relative_to(ROOT)),
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
            "reception_boundary": str(RECEPTION_BOUNDARY_PATH.relative_to(ROOT)),
            "reception_divergence": str(RECEPTION_DIVERGENCE_PATH.relative_to(ROOT)),
            "priority_dossier": str(PRIORITY_DOSSIER_PATH.relative_to(ROOT)),
        },
        "method": {
            "boundary": (
                "This atlas measures translation-pressure signals from local token fields, "
                "adjacent lemma overlap, and previously generated review-routing reports. "
                "It is not meter analysis, formal parallelism signoff, genre dating, "
                "authorship proof, or canonical rendering authority."
            ),
            "volitive_rule": (
                "Volitive mood pressure is inferred from observed Hebrew morph codes whose "
                "verbal form marker is imperative, jussive, or cohortative."
            ),
            "parallelism_rule": (
                "Adjacent parallelism is a lexical-overlap proxy across neighboring Psalm "
                "units, not a cola-level syntactic parallelism judgment."
            ),
            "acrostic_rule": (
                "Acrostic flags are conventional Psalm-level review proxies and require "
                "human confirmation of stanza boundaries before wording impact."
            ),
            "review_roles": [
                "Hebrew",
                "poetic",
                "lyric",
                "alignment",
                "textual",
                "theology",
                "reception",
                "ancient_cultural_context",
                "canonical_context",
            ],
        },
        "summary": {
            "unit_count": len(unit_rows),
            "psalm_count": len(psalm_rows),
            "high_pressure_unit_count": len(high_pressure_rows),
            "critical_pressure_unit_count": len(critical_rows),
            "high_pressure_unit_pct": pct(len(high_pressure_rows), len(unit_rows)),
            "mean_poetic_rhetorical_priority_score": mean(
                [float(row["poetic_rhetorical_priority_score"]) for row in unit_rows]
            ),
            "volitive_unit_count": len(volitive_rows),
            "volitive_token_count": sum(int(row["volitive_token_count"]) for row in unit_rows),
            "repetition_unit_count": len(repetition_rows),
            "lemma_repetition_token_excess": sum(
                int(row["repeated_lemma_token_excess"]) for row in unit_rows
            ),
            "adjacent_parallelism_proxy_unit_count": len(adjacent_rows),
            "second_person_address_unit_count": len(second_person_rows),
            "acrostic_proxy_psalm_count": len(ACROSTIC_PSALM_PROFILES),
            "acrostic_proxy_unit_count": len(acrostic_rows),
            "divine_name_overlap_unit_count": sum(
                1 for row in unit_rows if row["divine_name_overlap"]
            ),
            "superscription_overlap_unit_count": sum(
                1 for row in unit_rows if row["superscription_context_overlap"]
            ),
            "reception_sensitive_unit_count": sum(
                1 for row in unit_rows if row["reception_sensitive"]
            ),
            "jewish_christian_separation_unit_count": sum(
                1 for row in unit_rows if row["jewish_christian_separation_required"]
            ),
            "doctoral_dossier_overlap_unit_count": sum(
                1 for row in unit_rows if row["doctoral_dossier_overlap"]
            ),
            "feature_type_count": len(feature_rows),
            "top_priority_unit": unit_rows[0]["unit_id"] if unit_rows else "",
            "top_priority_ref": unit_rows[0]["ref"] if unit_rows else "",
            "top_priority_score": (
                unit_rows[0]["poetic_rhetorical_priority_score"] if unit_rows else 0.0
            ),
            "top_priority_band": unit_rows[0]["pressure_band"] if unit_rows else "",
            "status": "generated_not_signoff",
        },
        "unit_rows": unit_rows,
        "psalm_rows": psalm_rows,
        "feature_rows": feature_rows,
        "visual_data": {
            "top_unit_priority": chart_rows(
                unit_rows[:25],
                "ref",
                "poetic_rhetorical_priority_score",
            ),
            "top_psalm_priority": chart_rows(
                psalm_rows[:25],
                "psalm_id",
                "mean_poetic_rhetorical_score",
            ),
            "feature_counts": chart_rows(feature_rows, "feature", "unit_count"),
            "acrostic_psalm_priority": chart_rows(
                [row for row in psalm_rows if row["acrostic_psalm_proxy"]],
                "psalm_id",
                "mean_poetic_rhetorical_score",
            ),
        },
    }


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#355f7c",
    width: int = 980,
    limit: int = 20,
) -> str:
    rows = rows[:limit]
    row_h = 30
    left = 330
    right = 90
    top = 24
    height = top * 2 + row_h * max(1, len(rows))
    max_value = max((float(row.get(value_key) or 0) for row in rows), default=1.0)
    chart_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, row in enumerate(rows):
        value = float(row.get(value_key) or 0)
        y = top + index * row_h
        bar_w = chart_w * value / max_value if max_value else 0.0
        parts.append(
            f'<text x="{left - 12}" y="{y + 19}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row.get(label_key, ""))}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="19" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 19}" '
            f'font-size="12" font-weight="700" fill="#24313a">{value:g}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def metric_cards(cards: list[tuple[str, str, str]]) -> str:
    return (
        '<div class="metric-grid">'
        + "".join(
            f"""
            <article class="metric-card">
              <h3>{esc(label)}</h3>
              <p class="metric-value">{esc(value)}</p>
              <p>{esc(note)}</p>
            </article>
            """
            for label, value, note in cards
        )
        + "</div>"
    )


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    feature_rows = [
        [
            row["feature"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["feature_rows"]
    ]
    priority_rows = [
        [
            index + 1,
            row["ref"],
            row["pressure_band"],
            f"{row['poetic_rhetorical_priority_score']:.2f}",
            row["volitive_token_count"],
            row["repeated_lemma_token_excess"],
            row["adjacent_lemma_overlap_count"],
            "; ".join(row["feature_flags"]),
            "; ".join(item["lemma"] for item in row["top_repeated_lemmas"][:6]),
        ]
        for index, row in enumerate(report["unit_rows"][:40])
    ]
    psalm_rows = [
        [
            row["psalm_id"],
            row["unit_count"],
            row["high_pressure_unit_count"],
            f"{row['mean_poetic_rhetorical_score']:.2f}",
            row["acrostic_profile"],
            row["distinct_initial_hebrew_letter_count"],
            row["top_ref"],
        ]
        for row in report["psalm_rows"][:35]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Poetic and Rhetorical Translation Pressure Atlas</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #53616f;
      --line: #c9d1d9;
      --panel: #f8fafc;
      --accent: #355f7c;
      --accent-2: #6f5d2f;
      --warn: #9b3d3d;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #fff;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{ max-width: 1260px; margin: 0 auto; padding: 34px 24px 58px; }}
    h1, h2, h3 {{ line-height: 1.15; margin: 0; }}
    h1 {{ font-size: 2.08rem; max-width: 1040px; }}
    h2 {{ margin-top: 36px; font-size: 1.45rem; }}
    h3 {{
      color: var(--muted);
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    p {{ color: var(--muted); margin: 8px 0 0; }}
    .lede {{ max-width: 1040px; font-size: 1.05rem; }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
      gap: 12px;
      margin-top: 24px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 16px;
    }}
    .metric-value {{
      color: var(--ink);
      font-size: 1.7rem;
      font-weight: 700;
      margin-top: 6px;
    }}
    .grid-2 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(390px, 1fr));
      gap: 20px;
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 0.84rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #f4f7fa; color: var(--muted); }}
    svg {{ width: 100%; height: auto; display: block; }}
    .callout {{
      border-left: 4px solid var(--warn);
      background: #fff7f5;
      padding: 12px 16px;
      margin-top: 20px;
    }}
    .callout strong {{ color: var(--warn); }}
    footer {{ margin-top: 32px; color: var(--muted); font-size: 0.85rem; }}
  </style>
</head>
<body>
<main>
  <h1>Poetic and Rhetorical Translation Pressure Atlas</h1>
  <p class="lede">
    This report quantifies translation-review pressure from local Hebrew token
    evidence: repeated lemmas/forms, verbal mood, suffix address, construct
    chains, same-Psalm echoes, adjacent lexical overlap, acrostic proxies,
    witness divergence, divine-name policy, superscriptions, cultural domains,
    whole-Tanakh anchors, and reception-routing reports.
  </p>
  <div class="callout">
    <strong>Authority boundary:</strong> {esc(report["method"]["boundary"])}
  </div>

  {
        metric_cards(
            [
                (
                    "Psalm Units",
                    fmt_int(summary["unit_count"]),
                    "Verse units scanned from canonical content JSON.",
                ),
                (
                    "High Pressure",
                    fmt_int(summary["high_pressure_unit_count"]),
                    f"{fmt_pct(summary['high_pressure_unit_pct'])} of units.",
                ),
                (
                    "Volitive Tokens",
                    fmt_int(summary["volitive_token_count"]),
                    f"{fmt_int(summary['volitive_unit_count'])} units.",
                ),
                (
                    "Repetition Units",
                    fmt_int(summary["repetition_unit_count"]),
                    "Units with repeated content lemmas.",
                ),
                (
                    "Adjacent Proxy",
                    fmt_int(summary["adjacent_parallelism_proxy_unit_count"]),
                    "Neighboring-unit lemma overlap.",
                ),
                (
                    "Top Unit",
                    summary["top_priority_ref"],
                    f"Score {summary['top_priority_score']:.2f}.",
                ),
            ]
        )
    }

  <section>
    <h2>Visual Pressure</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Top Unit Priority</h3>
        {
        svg_horizontal_bars(
            visual["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top poetic and rhetorical priority units",
            color="#355f7c",
        )
    }
      </div>
      <div class="panel">
        <h3>Top Psalm Mean Priority</h3>
        {
        svg_horizontal_bars(
            visual["top_psalm_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top Psalms by mean poetic and rhetorical pressure",
            color="#6f5d2f",
        )
    }
      </div>
      <div class="panel">
        <h3>Feature Counts</h3>
        {
        svg_horizontal_bars(
            visual["feature_counts"],
            label_key="label",
            value_key="value",
            aria_label="Poetic and rhetorical feature counts",
            color="#2f6f73",
        )
    }
      </div>
      <div class="panel">
        <h3>Acrostic Psalm Priority</h3>
        {
        svg_horizontal_bars(
            visual["acrostic_psalm_priority"],
            label_key="label",
            value_key="value",
            aria_label="Acrostic proxy Psalm priority",
            color="#9b3d3d",
        )
    }
      </div>
    </div>
  </section>

  <section>
    <h2>Feature Summary</h2>
    {table(["Feature", "Units", "Unit %", "Mean Score", "Top Ref"], feature_rows)}
  </section>

  <section>
    <h2>Highest Priority Units</h2>
    {
        table(
            [
                "Rank",
                "Ref",
                "Band",
                "Score",
                "Volitives",
                "Lemma Excess",
                "Adjacent Overlap",
                "Flags",
                "Repeated Lemmas",
            ],
            priority_rows,
        )
    }
  </section>

  <section>
    <h2>Psalm-Level Pressure</h2>
    {
        table(
            [
                "Psalm",
                "Units",
                "High-Pressure Units",
                "Mean Score",
                "Acrostic Profile",
                "Initial Letters",
                "Top Ref",
            ],
            psalm_rows,
        )
    }
  </section>

  <footer>
    Generated {esc(report["generated_at"])} from local content and generated
    review-routing reports. No canonical text was modified.
  </footer>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate poetic/rhetorical translation pressure atlas."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--psalm-csv-output", type=Path, default=DEFAULT_PSALM_CSV_OUTPUT)
    parser.add_argument("--feature-csv-output", type=Path, default=DEFAULT_FEATURE_CSV_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.psalm_csv_output, report["psalm_rows"])
    write_csv(args.feature_csv_output, report["feature_rows"])


if __name__ == "__main__":
    main()
