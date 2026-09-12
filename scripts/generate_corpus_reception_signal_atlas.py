from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import combinations
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
POETIC_ATLAS_PATH = REPORT_ROOT / "poetic_rhetorical_pressure_atlas.json"
PRIORITY_DOSSIER_PATH = REPORT_ROOT / "doctoral_priority_dossier_atlas.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "corpus_reception_signal_atlas.json"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "corpus_reception_signal_atlas.html"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "corpus_reception_signal_atlas_units.csv"
DEFAULT_PSALM_CSV_OUTPUT = REPORT_ROOT / "corpus_reception_signal_atlas_psalms.csv"
DEFAULT_SIGNAL_CSV_OUTPUT = REPORT_ROOT / "corpus_reception_signal_atlas_signals.csv"
DEFAULT_COOCCURRENCE_CSV_OUTPUT = REPORT_ROOT / "corpus_reception_signal_atlas_cooccurrence.csv"
DEFAULT_EXPANSION_CSV_OUTPUT = REPORT_ROOT / "corpus_reception_signal_atlas_expansion_queue.csv"

SIGNAL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "royal_davidic_anointed": {
        "label": "Royal, Davidic, and Anointed Vocabulary",
        "description": (
            "King, reign, ruler, judge, throne, David, and anointed vocabulary that "
            "often requires separated royal, historical, and reception review."
        ),
        "strongs": {"H1732", "H3678", "H4427", "H4428", "H4899", "H4910", "H5057", "H8199"},
        "review_roles": ["Hebrew", "ancient_cultural_context", "reception", "theology"],
        "weight": 1.35,
    },
    "sonship_generation": {
        "label": "Sonship, Generation, and Descent Vocabulary",
        "description": (
            "Son, beget/birth, father/ancestor, and seed vocabulary that can affect "
            "lineage, adoption, corporate identity, and reception-sensitive readings."
        ),
        "strongs": {"H1", "H1121", "H2233", "H3205"},
        "review_roles": ["Hebrew", "reception", "theology"],
        "weight": 1.25,
    },
    "priesthood_zion_sacred_space": {
        "label": "Priesthood, Zion, and Sacred Space",
        "description": (
            "Priesthood, Melchizedek, Zion, Jerusalem, sanctuary, holiness, house, "
            "and temple vocabulary requiring cultic and reception-context review."
        ),
        "strongs": {"H1004", "H1964", "H3389", "H3548", "H4442", "H4720", "H6726", "H6944"},
        "review_roles": ["Hebrew", "ancient_cultural_context", "reception", "theology"],
        "weight": 1.25,
    },
    "torah_covenant_wisdom": {
        "label": "Torah, Covenant, and Wisdom Vocabulary",
        "description": (
            "Law/Torah, covenant, word, commandment, statute, testimony, precept, "
            "wisdom, and way vocabulary needing covenantal and reception-lane controls."
        ),
        "strongs": {
            "H1285",
            "H1697",
            "H1870",
            "H2451",
            "H2706",
            "H4687",
            "H5713",
            "H6490",
            "H8451",
        },
        "review_roles": ["Hebrew", "ancient_cultural_context", "reception", "theology"],
        "weight": 1.18,
    },
    "death_sheol_mortality": {
        "label": "Death, Sheol, Pit, and Mortality",
        "description": (
            "Death, Sheol, grave, pit, dust, descent, perish, and corruption "
            "vocabulary that can create afterlife, deliverance, and resurrection-pressure review."
        ),
        "strongs": {"H6", "H7585", "H4194", "H6913", "H953", "H6083", "H3381", "H7845"},
        "review_roles": ["Hebrew", "ancient_cultural_context", "reception", "theology"],
        "weight": 1.25,
    },
    "nations_kingdom_earth": {
        "label": "Nations, Kingdom, Earth, Israel, and Zion",
        "description": (
            "Nations, peoples, earth/land, kingdom, Israel, Jacob, Zion, and king "
            "vocabulary needing geography, political, canonical, and reception controls."
        ),
        "strongs": {"H1471", "H3290", "H3478", "H4428", "H4467", "H5971", "H6726", "H776"},
        "review_roles": ["Hebrew", "ancient_cultural_context", "canonical_context", "reception"],
        "weight": 1.12,
    },
    "affliction_righteous_sufferer": {
        "label": "Affliction, Righteousness, Wickedness, and Oppression",
        "description": (
            "Poor/afflicted/needy, righteous, righteousness, wicked, unrighteousness, "
            "enemy/foe, and distress vocabulary requiring social, moral, and reception review."
        ),
        "strongs": {"H34", "H341", "H6041", "H6662", "H6664", "H6862", "H7563", "H5766"},
        "review_roles": ["Hebrew", "ancient_cultural_context", "reception", "theology"],
        "weight": 1.1,
    },
    "imprecation_enemy_violence": {
        "label": "Enemy, Violence, Blood, Weapon, and Vengeance",
        "description": (
            "Enemy, wicked, blood, sword, bow, vengeance, evil, and distress vocabulary "
            "that can require imprecation, justice, and reception-sensitive review."
        ),
        "strongs": {"H341", "H7563", "H1818", "H2719", "H7198", "H5358", "H5359", "H7451", "H6862"},
        "review_roles": ["Hebrew", "ancient_cultural_context", "reception", "theology"],
        "weight": 1.08,
    },
    "divine_name_title_policy": {
        "label": "Divine Name and Title Policy",
        "description": (
            "YHWH, Elohim, Adonai/Lord, El/God, Eloah, and Most High vocabulary "
            "requiring explicit rendering-policy and reception-lane controls."
        ),
        "strongs": {"H3068", "H430", "H136", "H410", "H433", "H5945"},
        "review_roles": ["Hebrew", "alignment", "reception", "theology"],
        "weight": 1.3,
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


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def text_excerpt(text: str, limit: int = 155) -> str:
    compact = clean_text(text)
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def unit_lookup(report: dict[str, Any], row_key: str) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in report.get(row_key, []) if row.get("unit_id")}


def witness_texts(unit: dict[str, Any]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for witness in unit.get("witnesses", []):
        source_id = str(witness.get("source_id", ""))
        if source_id in {"kjv", "asv", "web"}:
            texts[source_id] = clean_text(witness.get("text", ""))
    return texts


def token_label(token: dict[str, Any]) -> str:
    strong = clean_text(token.get("strong", ""))
    lemma = clean_text(token.get("lemma", ""))
    gloss = clean_text(token.get("display_gloss", ""))
    surface = clean_text(token.get("surface", ""))
    parts = [part for part in [strong, lemma, surface, gloss] if part]
    return " ".join(parts)


def token_signal_rows(unit: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for token in unit.get("tokens", []):
        strong = str(token.get("strong") or "")
        for signal_id, definition in SIGNAL_DEFINITIONS.items():
            if strong in definition["strongs"]:
                rows.append(
                    {
                        "signal_id": signal_id,
                        "signal_label": definition["label"],
                        "token_id": token.get("token_id", ""),
                        "strong": strong,
                        "lemma": token.get("lemma", ""),
                        "surface": token.get("surface", ""),
                        "display_gloss": token.get("display_gloss", ""),
                        "part_of_speech": token.get("part_of_speech", ""),
                        "morph_code": token.get("morph_code", ""),
                        "token_label": token_label(token),
                    }
                )
    return rows


def report_signal_flags(
    *,
    claim: dict[str, Any],
    reception_boundary: dict[str, Any],
    reception_divergence: dict[str, Any],
    witness: dict[str, Any],
    divine: dict[str, Any],
    superscription: dict[str, Any],
    cultural: dict[str, Any],
    cross_reference: dict[str, Any],
    poetic: dict[str, Any],
    dossier: dict[str, Any],
) -> list[str]:
    flags = []
    if claim.get("reception_sensitive") or reception_boundary.get("reception_sensitive"):
        flags.append("existing_reception_sensitive_control")
    if reception_divergence.get("jewish_christian_separation_required") or dossier.get(
        "jewish_christian_separation_required"
    ):
        flags.append("existing_jewish_christian_split_control")
    if reception_divergence:
        flags.append("existing_reception_divergence_row")
    if claim.get("textual_witness_pressure") or reception_boundary.get("textual_witness_pressure"):
        flags.append("textual_witness_pressure_control")
    if float(witness.get("mean_english_witness_divergence_pct") or 0) >= 55:
        flags.append("high_english_witness_divergence")
    if divine:
        flags.append("divine_name_report_overlap")
    if superscription:
        flags.append("superscription_or_attribution_overlap")
    if int(cultural.get("domain_count") or 0) >= 3 or cultural.get("reception_sensitive"):
        flags.append("multi_domain_cultural_reception_overlap")
    if int(cross_reference.get("anchor_token_count") or 0) >= 5:
        flags.append("whole_tanakh_anchor_pressure")
    if poetic.get("pressure_band") in {"critical", "highest", "high"}:
        flags.append("poetic_rhetorical_high_pressure")
    if dossier:
        flags.append("doctoral_dossier_overlap")
    return sorted(dict.fromkeys(flags))


def priority_score(
    *,
    token_rows: list[dict[str, Any]],
    signal_counts: Counter[str],
    flags: list[str],
    claim: dict[str, Any],
    reception_boundary: dict[str, Any],
    reception_divergence: dict[str, Any],
    witness: dict[str, Any],
    divine: dict[str, Any],
    superscription: dict[str, Any],
    cultural: dict[str, Any],
    cross_reference: dict[str, Any],
    poetic: dict[str, Any],
    dossier: dict[str, Any],
) -> float:
    score = len(token_rows) * 2.0
    for signal_id, count in signal_counts.items():
        score += count * float(SIGNAL_DEFINITIONS[signal_id]["weight"]) * 5.0
    score += len(signal_counts) * 12.0
    score += max(0, len(signal_counts) - 1) * 8.0
    score += min(24.0, float(claim.get("claim_risk_score") or 0) / 8.0)
    score += min(24.0, float(reception_boundary.get("boundary_risk_score") or 0) / 8.0)
    score += min(28.0, float(witness.get("priority_score") or 0) / 6.0)
    score += min(18.0, float(witness.get("mean_english_witness_divergence_pct") or 0) / 4.0)
    score += float(divine.get("divine_title_token_count") or 0) * 8.0
    score += float(superscription.get("context_token_count") or 0) * 5.0
    score += float(cultural.get("domain_count") or 0) * 5.0
    score += min(22.0, float(cross_reference.get("priority_score") or 0) / 16.0)
    score += min(18.0, float(poetic.get("poetic_rhetorical_priority_score") or 0) / 14.0)
    if claim.get("reception_sensitive") or reception_boundary.get("reception_sensitive"):
        score += 16.0
    if reception_divergence:
        score += 20.0
    if reception_divergence.get("jewish_christian_separation_required") or dossier.get(
        "jewish_christian_separation_required"
    ):
        score += 28.0
    if dossier:
        score += 18.0
        score += min(16.0, float(dossier.get("doctoral_dossier_priority_score") or 0) / 40.0)
    score += min(18.0, max(0, len(flags) - 2) * 2.5)
    return round(score, 2)


def pressure_band(score: float) -> str:
    if score >= 190:
        return "critical"
    if score >= 155:
        return "highest"
    if score >= 120:
        return "high"
    if score >= 80:
        return "elevated"
    return "watch"


def recommended_review_roles(signal_ids: list[str], flags: list[str]) -> list[str]:
    roles = {"Hebrew", "reception"}
    for signal_id in signal_ids:
        roles.update(SIGNAL_DEFINITIONS[signal_id]["review_roles"])
    if "whole_tanakh_anchor_pressure" in flags:
        roles.add("canonical_context")
    if "high_english_witness_divergence" in flags or "textual_witness_pressure_control" in flags:
        roles.add("textual")
    if "poetic_rhetorical_high_pressure" in flags:
        roles.add("poetic")
    if "divine_name_report_overlap" in flags:
        roles.update({"alignment", "theology"})
    return sorted(roles)


def build_unit_row(
    unit: dict[str, Any],
    *,
    witnesses: dict[str, dict[str, Any]],
    divine_units: dict[str, dict[str, Any]],
    superscription_units: dict[str, dict[str, Any]],
    cultural_units: dict[str, dict[str, Any]],
    cross_reference_units: dict[str, dict[str, Any]],
    claims: dict[str, dict[str, Any]],
    reception_boundaries: dict[str, dict[str, Any]],
    reception_divergences: dict[str, dict[str, Any]],
    poetic_units: dict[str, dict[str, Any]],
    dossiers: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    unit_id = str(unit["unit_id"])
    token_rows = token_signal_rows(unit)
    signal_counts: Counter[str] = Counter(row["signal_id"] for row in token_rows)
    claim = claims.get(unit_id, {})
    reception_boundary = reception_boundaries.get(unit_id, {})
    reception_divergence = reception_divergences.get(unit_id, {})
    witness = witnesses.get(unit_id, {})
    divine = divine_units.get(unit_id, {})
    superscription = superscription_units.get(unit_id, {})
    cultural = cultural_units.get(unit_id, {})
    cross_reference = cross_reference_units.get(unit_id, {})
    poetic = poetic_units.get(unit_id, {})
    dossier = dossiers.get(unit_id, {})
    flags = report_signal_flags(
        claim=claim,
        reception_boundary=reception_boundary,
        reception_divergence=reception_divergence,
        witness=witness,
        divine=divine,
        superscription=superscription,
        cultural=cultural,
        cross_reference=cross_reference,
        poetic=poetic,
        dossier=dossier,
    )
    if not token_rows and not flags:
        return None
    score = priority_score(
        token_rows=token_rows,
        signal_counts=signal_counts,
        flags=flags,
        claim=claim,
        reception_boundary=reception_boundary,
        reception_divergence=reception_divergence,
        witness=witness,
        divine=divine,
        superscription=superscription,
        cultural=cultural,
        cross_reference=cross_reference,
        poetic=poetic,
        dossier=dossier,
    )
    signal_ids = [signal_id for signal_id, _count in signal_counts.most_common()]
    texts = witness_texts(unit)
    return {
        "unit_id": unit_id,
        "ref": unit.get("ref", ""),
        "psalm_id": unit.get("psalm_id", ""),
        "signal_token_count": len(token_rows),
        "signal_family_count": len(signal_counts),
        "signal_ids": signal_ids,
        "signal_labels": [SIGNAL_DEFINITIONS[signal_id]["label"] for signal_id in signal_ids],
        "signal_counts": dict(signal_counts.most_common()),
        "token_evidence": token_rows[:24],
        "top_token_labels": [row["token_label"] for row in token_rows[:16]],
        "report_flags": flags,
        "report_flag_count": len(flags),
        "reception_signal_priority_score": score,
        "pressure_band": pressure_band(score),
        "known_reception_divergence_unit": bool(reception_divergence),
        "known_reception_sensitive": bool(
            claim.get("reception_sensitive")
            or reception_boundary.get("reception_sensitive")
            or reception_divergence.get("reception_sensitive")
        ),
        "known_jewish_christian_separation": bool(
            reception_divergence.get("jewish_christian_separation_required")
            or dossier.get("jewish_christian_separation_required")
        ),
        "claim_risk_score": claim.get("claim_risk_score", 0),
        "boundary_risk_score": reception_boundary.get("boundary_risk_score", 0),
        "witness_divergence_pct": witness.get("mean_english_witness_divergence_pct", 0),
        "divine_title_token_count": divine.get("divine_title_token_count", 0),
        "superscription_context_token_count": superscription.get("context_token_count", 0),
        "cultural_domain_count": cultural.get("domain_count", 0),
        "cultural_domain_labels": cultural.get("domain_labels", []),
        "cross_reference_anchor_token_count": cross_reference.get("anchor_token_count", 0),
        "poetic_rhetorical_priority_score": poetic.get(
            "poetic_rhetorical_priority_score",
            0,
        ),
        "doctoral_dossier_overlap": bool(dossier),
        "recommended_review_roles": recommended_review_roles(signal_ids, flags),
        "source_hebrew": unit.get("source_hebrew", ""),
        "kjv_excerpt": text_excerpt(texts.get("kjv", "")),
        "asv_excerpt": text_excerpt(texts.get("asv", "")),
        "web_excerpt": text_excerpt(texts.get("web", "")),
    }


def build_unit_rows(
    witnesses: dict[str, dict[str, Any]],
    divine_units: dict[str, dict[str, Any]],
    superscription_units: dict[str, dict[str, Any]],
    cultural_units: dict[str, dict[str, Any]],
    cross_reference_units: dict[str, dict[str, Any]],
    claims: dict[str, dict[str, Any]],
    reception_boundaries: dict[str, dict[str, Any]],
    reception_divergences: dict[str, dict[str, Any]],
    poetic_units: dict[str, dict[str, Any]],
    dossiers: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    rows = []
    unit_count = 0
    for path in sorted(CONTENT_ROOT.glob("ps*/*.v*.json")):
        unit_count += 1
        unit = load_json(path)
        row = build_unit_row(
            unit,
            witnesses=witnesses,
            divine_units=divine_units,
            superscription_units=superscription_units,
            cultural_units=cultural_units,
            cross_reference_units=cross_reference_units,
            claims=claims,
            reception_boundaries=reception_boundaries,
            reception_divergences=reception_divergences,
            poetic_units=poetic_units,
            dossiers=dossiers,
        )
        if row:
            rows.append(row)
    rows.sort(key=lambda item: float(item["reception_signal_priority_score"]), reverse=True)
    return rows, unit_count


def build_signal_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unit_counts: Counter[str] = Counter()
    token_counts: Counter[str] = Counter()
    score_sums: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    known_counts: Counter[str] = Counter()
    top_refs: dict[str, tuple[str, float]] = {}
    for row in unit_rows:
        score = float(row["reception_signal_priority_score"])
        for signal_id, count in row["signal_counts"].items():
            unit_counts[signal_id] += 1
            token_counts[signal_id] += int(count)
            score_sums[signal_id] += int(score * 100)
            if row["known_jewish_christian_separation"]:
                split_counts[signal_id] += 1
            if row["known_reception_divergence_unit"]:
                known_counts[signal_id] += 1
            if signal_id not in top_refs or score > top_refs[signal_id][1]:
                top_refs[signal_id] = (str(row["ref"]), score)
    rows = []
    for signal_id, definition in SIGNAL_DEFINITIONS.items():
        count = unit_counts[signal_id]
        rows.append(
            {
                "signal_id": signal_id,
                "label": definition["label"],
                "description": definition["description"],
                "token_count": token_counts[signal_id],
                "unit_count": count,
                "unit_pct": pct(count, len(unit_rows)),
                "known_reception_divergence_unit_count": known_counts[signal_id],
                "known_jewish_christian_split_count": split_counts[signal_id],
                "mean_priority_score": (
                    round(score_sums[signal_id] / count / 100, 2) if count else 0.0
                ),
                "top_ref": top_refs.get(signal_id, ("", 0.0))[0],
                "top_priority_score": top_refs.get(signal_id, ("", 0.0))[1],
                "review_roles": definition["review_roles"],
            }
        )
    return sorted(rows, key=lambda row: int(row["unit_count"]), reverse=True)


def build_psalm_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        grouped[str(row["psalm_id"])].append(row)
    rows = []
    for psalm_id, psalm_units in grouped.items():
        signal_counts: Counter[str] = Counter()
        flag_counts: Counter[str] = Counter()
        for row in psalm_units:
            signal_counts.update(row["signal_counts"])
            flag_counts.update(row["report_flags"])
        top = max(psalm_units, key=lambda row: float(row["reception_signal_priority_score"]))
        rows.append(
            {
                "psalm_id": psalm_id,
                "signal_unit_count": len(psalm_units),
                "signal_token_count": sum(int(row["signal_token_count"]) for row in psalm_units),
                "signal_family_count": len(signal_counts),
                "signal_counts": dict(signal_counts.most_common()),
                "report_flag_counts": dict(flag_counts.most_common()),
                "known_reception_divergence_unit_count": sum(
                    1 for row in psalm_units if row["known_reception_divergence_unit"]
                ),
                "known_jewish_christian_split_count": sum(
                    1 for row in psalm_units if row["known_jewish_christian_separation"]
                ),
                "high_pressure_unit_count": sum(
                    1
                    for row in psalm_units
                    if row["pressure_band"] in {"critical", "highest", "high"}
                ),
                "mean_priority_score": mean(
                    [float(row["reception_signal_priority_score"]) for row in psalm_units]
                ),
                "top_unit_id": top["unit_id"],
                "top_ref": top["ref"],
                "top_priority_score": top["reception_signal_priority_score"],
            }
        )
    return sorted(rows, key=lambda row: float(row["mean_priority_score"]), reverse=True)


def build_cooccurrence_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pair_counts: Counter[tuple[str, str]] = Counter()
    score_sums: Counter[tuple[str, str]] = Counter()
    split_counts: Counter[tuple[str, str]] = Counter()
    for row in unit_rows:
        signal_ids = sorted(row["signal_ids"])
        for left, right in combinations(signal_ids, 2):
            pair = (left, right)
            pair_counts[pair] += 1
            score_sums[pair] += int(float(row["reception_signal_priority_score"]) * 100)
            if row["known_jewish_christian_separation"]:
                split_counts[pair] += 1
    rows = []
    for (left, right), count in pair_counts.most_common():
        rows.append(
            {
                "left_signal_id": left,
                "left_label": SIGNAL_DEFINITIONS[left]["label"],
                "right_signal_id": right,
                "right_label": SIGNAL_DEFINITIONS[right]["label"],
                "unit_count": count,
                "known_jewish_christian_split_count": split_counts[(left, right)],
                "mean_priority_score": round(score_sums[(left, right)] / count / 100, 2),
            }
        )
    return rows


def build_expansion_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expansion = []
    for row in unit_rows:
        if row["known_reception_divergence_unit"]:
            continue
        if row["pressure_band"] not in {"critical", "highest", "high"}:
            continue
        expansion.append(
            {
                "rank": len(expansion) + 1,
                "unit_id": row["unit_id"],
                "ref": row["ref"],
                "pressure_band": row["pressure_band"],
                "reception_signal_priority_score": row["reception_signal_priority_score"],
                "signal_family_count": row["signal_family_count"],
                "signal_ids": row["signal_ids"],
                "report_flags": row["report_flags"],
                "recommended_review_roles": row["recommended_review_roles"],
                "next_action": (
                    "Create separated Jewish, Christian, academic, Hebrew-source, "
                    "and textual-witness source-packet rows before interpretation impact."
                ),
            }
        )
    return expansion


def chart_rows(rows: list[dict[str, Any]], label_key: str, value_key: str) -> list[dict[str, Any]]:
    return [{"label": str(row[label_key]), "value": row[value_key]} for row in rows]


def serializable_signal_definitions() -> dict[str, dict[str, Any]]:
    return {
        signal_id: {
            key: sorted(value) if isinstance(value, set) else value
            for key, value in definition.items()
        }
        for signal_id, definition in SIGNAL_DEFINITIONS.items()
    }


def build_report() -> dict[str, Any]:
    witness_report = maybe_load_json(WITNESS_DIVERGENCE_PATH)
    divine_report = maybe_load_json(DIVINE_NAME_PATH)
    superscription_report = maybe_load_json(SUPERSCRIPTION_PATH)
    cultural_report = maybe_load_json(CULTURAL_ATLAS_PATH)
    cross_reference_report = maybe_load_json(CROSS_REFERENCE_PATH)
    claim_report = maybe_load_json(CLAIM_MATRIX_PATH)
    reception_boundary_report = maybe_load_json(RECEPTION_BOUNDARY_PATH)
    reception_divergence_report = maybe_load_json(RECEPTION_DIVERGENCE_PATH)
    poetic_report = maybe_load_json(POETIC_ATLAS_PATH)
    dossier_report = maybe_load_json(PRIORITY_DOSSIER_PATH)
    unit_rows, unit_count = build_unit_rows(
        unit_lookup(witness_report, "unit_rows"),
        unit_lookup(divine_report, "unit_rows"),
        unit_lookup(superscription_report, "unit_rows"),
        unit_lookup(cultural_report, "unit_rows"),
        unit_lookup(cross_reference_report, "unit_rows"),
        unit_lookup(claim_report, "unit_claim_rows"),
        unit_lookup(reception_boundary_report, "unit_boundary_rows"),
        unit_lookup(reception_divergence_report, "unit_rows"),
        unit_lookup(poetic_report, "unit_rows"),
        unit_lookup(dossier_report, "unit_rows"),
    )
    signal_rows = build_signal_rows(unit_rows)
    psalm_rows = build_psalm_rows(unit_rows)
    cooccurrence_rows = build_cooccurrence_rows(unit_rows)
    expansion_rows = build_expansion_rows(unit_rows)
    high_pressure = [
        row for row in unit_rows if row["pressure_band"] in {"critical", "highest", "high"}
    ]
    critical_rows = [row for row in unit_rows if row["pressure_band"] == "critical"]
    known_divergence_rows = [row for row in unit_rows if row["known_reception_divergence_unit"]]
    known_split_rows = [row for row in unit_rows if row["known_jewish_christian_separation"]]
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "corpus reception signal atlas generated; not interpretive signoff",
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
            "poetic_rhetorical_atlas": str(POETIC_ATLAS_PATH.relative_to(ROOT)),
            "priority_dossier": str(PRIORITY_DOSSIER_PATH.relative_to(ROOT)),
        },
        "method": {
            "boundary": (
                "Signal families are lexeme/Strong/report-overlap routing evidence. "
                "They do not prove Jewish interpretation, Christian interpretation, "
                "messianic meaning, historical setting, intertextual dependence, or "
                "translation wording authority."
            ),
            "signal_definitions": serializable_signal_definitions(),
            "review_roles": [
                "Hebrew",
                "ancient_cultural_context",
                "canonical_context",
                "textual",
                "alignment",
                "poetic",
                "reception",
                "theology",
            ],
        },
        "summary": {
            "unit_count": unit_count,
            "signal_unit_count": len(unit_rows),
            "signal_unit_pct": pct(len(unit_rows), unit_count),
            "signal_token_count": sum(int(row["signal_token_count"]) for row in unit_rows),
            "signal_family_count": len(SIGNAL_DEFINITIONS),
            "psalm_with_signal_count": len(psalm_rows),
            "high_pressure_unit_count": len(high_pressure),
            "critical_pressure_unit_count": len(critical_rows),
            "high_pressure_unit_pct": pct(len(high_pressure), unit_count),
            "known_reception_divergence_unit_count": len(known_divergence_rows),
            "known_jewish_christian_separation_unit_count": len(known_split_rows),
            "new_high_pressure_expansion_candidate_count": len(expansion_rows),
            "cooccurrence_pair_count": len(cooccurrence_rows),
            "mean_priority_score": mean(
                [float(row["reception_signal_priority_score"]) for row in unit_rows]
            ),
            "top_priority_unit": unit_rows[0]["unit_id"] if unit_rows else "",
            "top_priority_ref": unit_rows[0]["ref"] if unit_rows else "",
            "top_priority_score": unit_rows[0]["reception_signal_priority_score"]
            if unit_rows
            else 0.0,
            "top_priority_band": unit_rows[0]["pressure_band"] if unit_rows else "",
            "status": "generated_not_signoff",
        },
        "signal_rows": signal_rows,
        "unit_rows": unit_rows,
        "psalm_rows": psalm_rows,
        "cooccurrence_rows": cooccurrence_rows,
        "expansion_queue_rows": expansion_rows,
        "visual_data": {
            "signal_unit_counts": chart_rows(signal_rows, "label", "unit_count"),
            "signal_token_counts": chart_rows(signal_rows, "label", "token_count"),
            "top_unit_priority": chart_rows(
                unit_rows[:25],
                "ref",
                "reception_signal_priority_score",
            ),
            "top_psalm_priority": chart_rows(psalm_rows[:25], "psalm_id", "mean_priority_score"),
            "top_expansion_candidates": chart_rows(
                expansion_rows[:25],
                "ref",
                "reception_signal_priority_score",
            ),
            "cooccurrence_counts": [
                {
                    "label": f"{row['left_label']} + {row['right_label']}",
                    "value": row["unit_count"],
                }
                for row in cooccurrence_rows[:25]
            ],
        },
    }


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#5b6f2f",
    width: int = 980,
    limit: int = 20,
) -> str:
    rows = rows[:limit]
    row_h = 30
    left = 360
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
    signal_rows = [
        [
            row["label"],
            row["token_count"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["known_reception_divergence_unit_count"],
            row["known_jewish_christian_split_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["signal_rows"]
    ]
    priority_rows = [
        [
            index + 1,
            row["ref"],
            row["pressure_band"],
            f"{row['reception_signal_priority_score']:.2f}",
            row["signal_family_count"],
            "; ".join(row["signal_labels"]),
            "; ".join(row["report_flags"]),
            "; ".join(row["recommended_review_roles"]),
        ]
        for index, row in enumerate(report["unit_rows"][:40])
    ]
    psalm_rows = [
        [
            row["psalm_id"],
            row["signal_unit_count"],
            row["signal_token_count"],
            row["signal_family_count"],
            row["known_jewish_christian_split_count"],
            row["high_pressure_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["psalm_rows"][:35]
    ]
    expansion_rows = [
        [
            row["rank"],
            row["ref"],
            row["pressure_band"],
            f"{row['reception_signal_priority_score']:.2f}",
            row["signal_family_count"],
            "; ".join(row["signal_ids"]),
            "; ".join(row["recommended_review_roles"]),
        ]
        for row in report["expansion_queue_rows"][:40]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Corpus Reception Signal Atlas</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #53616f;
      --line: #c9d1d9;
      --panel: #f8fafc;
      --accent: #5b6f2f;
      --accent-2: #355f7c;
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
  <h1>Corpus-Wide Reception Signal Atlas</h1>
  <p class="lede">
    This report expands reception review routing from the benchmark units to
    the full Psalms corpus using local Hebrew Strong identifiers, existing
    witness divergence, divine-name, superscription, cultural, whole-Tanakh,
    poetic, and dossier evidence.
  </p>
  <div class="callout">
    <strong>Authority boundary:</strong> {esc(report["method"]["boundary"])}
  </div>

  {
        metric_cards(
            [
                (
                    "Signal Units",
                    fmt_int(summary["signal_unit_count"]),
                    f"{fmt_pct(summary['signal_unit_pct'])} of Psalm units.",
                ),
                (
                    "Signal Tokens",
                    fmt_int(summary["signal_token_count"]),
                    f"{fmt_int(summary['signal_family_count'])} signal families.",
                ),
                (
                    "High Pressure",
                    fmt_int(summary["high_pressure_unit_count"]),
                    f"{fmt_pct(summary['high_pressure_unit_pct'])} of all units.",
                ),
                (
                    "Known Split",
                    fmt_int(summary["known_jewish_christian_separation_unit_count"]),
                    "Already flagged in explicit reception rows.",
                ),
                (
                    "Expansion Queue",
                    fmt_int(summary["new_high_pressure_expansion_candidate_count"]),
                    "High-pressure candidates outside explicit reception rows.",
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
    <h2>Visual Signal Pressure</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Signal Unit Counts</h3>
        {
        svg_horizontal_bars(
            visual["signal_unit_counts"],
            label_key="label",
            value_key="value",
            aria_label="Reception signal unit counts",
            color="#5b6f2f",
        )
    }
      </div>
      <div class="panel">
        <h3>Top Unit Priority</h3>
        {
        svg_horizontal_bars(
            visual["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top reception signal priority units",
            color="#355f7c",
        )
    }
      </div>
      <div class="panel">
        <h3>Top Expansion Candidates</h3>
        {
        svg_horizontal_bars(
            visual["top_expansion_candidates"],
            label_key="label",
            value_key="value",
            aria_label="Top reception expansion candidates",
            color="#9b3d3d",
        )
    }
      </div>
      <div class="panel">
        <h3>Signal Co-Occurrences</h3>
        {
        svg_horizontal_bars(
            visual["cooccurrence_counts"],
            label_key="label",
            value_key="value",
            aria_label="Reception signal co-occurrence counts",
            color="#6f5d2f",
        )
    }
      </div>
    </div>
  </section>

  <section>
    <h2>Signal Summary</h2>
    {
        table(
            [
                "Signal",
                "Tokens",
                "Units",
                "Unit %",
                "Known Reception Rows",
                "Known Split Rows",
                "Mean Score",
                "Top Ref",
            ],
            signal_rows,
        )
    }
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
                "Families",
                "Signals",
                "Report Flags",
                "Review Roles",
            ],
            priority_rows,
        )
    }
  </section>

  <section>
    <h2>Reception Expansion Queue</h2>
    {
        table(
            ["Rank", "Ref", "Band", "Score", "Families", "Signals", "Review Roles"],
            expansion_rows,
        )
    }
  </section>

  <section>
    <h2>Psalm-Level Signal Pressure</h2>
    {
        table(
            [
                "Psalm",
                "Units",
                "Tokens",
                "Families",
                "Known Split",
                "High Pressure",
                "Mean Score",
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
    parser = argparse.ArgumentParser(description="Generate corpus reception signal atlas.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--psalm-csv-output", type=Path, default=DEFAULT_PSALM_CSV_OUTPUT)
    parser.add_argument("--signal-csv-output", type=Path, default=DEFAULT_SIGNAL_CSV_OUTPUT)
    parser.add_argument(
        "--cooccurrence-csv-output",
        type=Path,
        default=DEFAULT_COOCCURRENCE_CSV_OUTPUT,
    )
    parser.add_argument("--expansion-csv-output", type=Path, default=DEFAULT_EXPANSION_CSV_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.psalm_csv_output, report["psalm_rows"])
    write_csv(args.signal_csv_output, report["signal_rows"])
    write_csv(args.cooccurrence_csv_output, report["cooccurrence_rows"])
    write_csv(args.expansion_csv_output, report["expansion_queue_rows"])


if __name__ == "__main__":
    main()
