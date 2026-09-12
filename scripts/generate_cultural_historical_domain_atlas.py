from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = ROOT / "content" / "psalms"
REPORT_ROOT = ROOT / "reports" / "research"

CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
RECEPTION_BOUNDARY_PATH = REPORT_ROOT / "reception_interpretation_boundary.json"
WITNESS_DIVERGENCE_PATH = REPORT_ROOT / "witness_divergence_report.json"
DIVINE_NAME_PATH = REPORT_ROOT / "divine_name_policy_report.json"
SUPERSCRIPTION_PATH = REPORT_ROOT / "superscription_context_report.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "cultural_historical_domain_atlas.json"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "cultural_historical_domain_atlas.html"
DEFAULT_TOKEN_CSV_OUTPUT = REPORT_ROOT / "cultural_historical_domain_atlas_tokens.csv"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "cultural_historical_domain_atlas_units.csv"
DEFAULT_DOMAIN_CSV_OUTPUT = REPORT_ROOT / "cultural_historical_domain_atlas_domains.csv"
DEFAULT_PSALM_CSV_OUTPUT = REPORT_ROOT / "cultural_historical_domain_atlas_psalms.csv"
DEFAULT_COOCCURRENCE_CSV_OUTPUT = REPORT_ROOT / "cultural_historical_domain_atlas_cooccurrence.csv"

ENGLISH_WITNESS_SOURCES = ["kjv", "asv", "web"]

DOMAIN_DEFINITIONS: dict[str, dict[str, Any]] = {
    "covenant_torah_wisdom": {
        "label": "Covenant, Torah, and Wisdom",
        "description": (
            "Instruction, testimony, command, covenant, righteous life, wisdom, and "
            "faithful covenant vocabulary."
        ),
        "strongs": {
            "H1285",
            "H1697",
            "H1870",
            "H2451",
            "H2617",
            "H2706",
            "H4687",
            "H4941",
            "H530",
            "H5713",
            "H6662",
            "H8451",
        },
        "lemmas": {
            "בְּרִית",
            "דָּבָר",
            "דֶּרֶךְ",
            "חֶסֶד",
            "חָכְמָה",
            "חֹק",
            "מִצְוָה",
            "מִשְׁפָּט",
            "עֵדוּת",
            "פִּקּוּד",
            "צַדִּיק",
            "צֶדֶק",
            "תּוֹרָה",
        },
        "gloss_terms": {
            "commandment",
            "covenant",
            "faithfulness",
            "law",
            "precept",
            "righteous",
            "statute",
            "testimony",
            "torah",
            "way",
            "wisdom",
            "word",
        },
        "review_roles": ["Hebrew", "ancient_cultural_context", "theology"],
        "weight": 1.25,
    },
    "temple_cult_sacred_space": {
        "label": "Temple, Cult, and Sacred Space",
        "description": (
            "Sacred house/temple, altar, sacrifice, priesthood, gates, courts, holiness, "
            "and worship-space vocabulary."
        ),
        "strongs": {
            "H1004",
            "H1964",
            "H2077",
            "H2691",
            "H3548",
            "H4196",
            "H4503",
            "H4720",
            "H6942",
            "H6944",
            "H8179",
            "H8426",
        },
        "lemmas": {
            "בַּיִת",
            "זֶבַח",
            "חָצֵר",
            "חֲנֻכָּה",
            "הֵיכָל",
            "מִזְבֵּחַ",
            "מִנְחָה",
            "מִקְדָּשׁ",
            "קֹדֶשׁ",
            "קָדַשׁ",
            "כֹּהֵן",
            "שַׁעַר",
            "תֹּודָה",
        },
        "gloss_terms": {
            "altar",
            "court",
            "dedication",
            "gate",
            "holy",
            "house",
            "offering",
            "priest",
            "sacred",
            "sacrifice",
            "sanctuary",
            "temple",
            "thanksgiving",
        },
        "review_roles": ["Hebrew", "ancient_cultural_context", "theology"],
        "weight": 1.2,
    },
    "kingship_davidic_political": {
        "label": "Kingship, Davidic, and Political Order",
        "description": (
            "Royal, enthronement, Davidic, anointed, ruler, throne, judgment, and "
            "political-authority vocabulary."
        ),
        "strongs": {
            "H1732",
            "H3678",
            "H4427",
            "H4428",
            "H4475",
            "H4899",
            "H4910",
            "H5057",
            "H8199",
            "H8269",
        },
        "lemmas": {
            "דָּוִד",
            "כִּסֵּא",
            "מֶלֶךְ",
            "מָלַךְ",
            "מֶמְשָׁלָה",
            "מָשִׁיחַ",
            "מָשַׁל",
            "נָגִיד",
            "שַׂר",
            "שָׁפַט",
        },
        "gloss_terms": {
            "anointed",
            "david",
            "judge",
            "king",
            "kingdom",
            "prince",
            "reign",
            "rule",
            "throne",
        },
        "review_roles": ["Hebrew", "ancient_cultural_context", "theology"],
        "weight": 1.25,
    },
    "nations_geography_identity": {
        "label": "Nations, Geography, and Identity",
        "description": (
            "Israel, Jacob, Zion, Jerusalem, nations, peoples, land, mountain, and named "
            "foreign people/place vocabulary."
        ),
        "strongs": {
            "H123",
            "H1471",
            "H2022",
            "H3290",
            "H3389",
            "H3478",
            "H4714",
            "H5971",
            "H6430",
            "H6726",
            "H776",
        },
        "lemmas": {
            "אֱדוֹם",
            "אֶרֶץ",
            "גּוֹי",
            "הַר",
            "יִשְׂרָאֵל",
            "יַעֲקֹב",
            "יְרוּשָׁלִַם",
            "מִצְרַיִם",
            "עַם",
            "פְּלִשְׁתִּי",
            "צִיּוֹן",
        },
        "gloss_terms": {
            "edom",
            "egypt",
            "israel",
            "jacob",
            "jerusalem",
            "land",
            "mount",
            "nation",
            "people",
            "philistine",
            "zion",
        },
        "review_roles": ["Hebrew", "ancient_cultural_context", "reception"],
        "weight": 1.15,
    },
    "creation_cosmos_nature": {
        "label": "Creation, Cosmos, and Nature",
        "description": (
            "Heavens, earth, sea, waters, rivers, mountains, sun, moon, stars, fire, "
            "wind/spirit, and creation-order vocabulary."
        ),
        "strongs": {
            "H776",
            "H784",
            "H1254",
            "H2022",
            "H3220",
            "H3394",
            "H3556",
            "H4325",
            "H5104",
            "H7307",
            "H8064",
            "H8121",
        },
        "lemmas": {
            "אֶרֶץ",
            "אֵשׁ",
            "בָּרָא",
            "הַר",
            "יָם",
            "יָרֵחַ",
            "כּוֹכָב",
            "מַיִם",
            "נָהָר",
            "רוּחַ",
            "שָׁמַיִם",
            "שֶׁמֶשׁ",
        },
        "gloss_terms": {
            "created",
            "earth",
            "fire",
            "heaven",
            "moon",
            "mountain",
            "river",
            "sea",
            "star",
            "sun",
            "water",
            "wind",
        },
        "review_roles": ["Hebrew", "ancient_cultural_context", "poetic"],
        "weight": 1.0,
    },
    "justice_enemy_violence": {
        "label": "Justice, Enemy, and Violence",
        "description": (
            "Wicked/righteous contrast, enemies, adversaries, blood, sword, bow, war, "
            "vengeance, judgment, and conflict vocabulary."
        ),
        "strongs": {
            "H1818",
            "H2719",
            "H341",
            "H4421",
            "H4941",
            "H5358",
            "H6662",
            "H6862",
            "H7198",
            "H7563",
            "H8199",
        },
        "lemmas": {
            "אוֹיֵב",
            "דָּם",
            "חֶרֶב",
            "מִלְחָמָה",
            "מִשְׁפָּט",
            "נָקַם",
            "צַדִּיק",
            "צַר",
            "קֶשֶׁת",
            "רָשָׁע",
            "שָׁפַט",
        },
        "gloss_terms": {
            "adversary",
            "blood",
            "bow",
            "enemy",
            "judge",
            "judgment",
            "revenge",
            "righteous",
            "sword",
            "war",
            "wicked",
        },
        "review_roles": ["Hebrew", "ancient_cultural_context", "theology"],
        "weight": 1.15,
    },
    "poverty_affliction_social_order": {
        "label": "Poverty, Affliction, and Social Order",
        "description": (
            "Poor, afflicted, needy, lowly, orphan, widow, sojourner, oppression, and "
            "social vulnerability vocabulary."
        ),
        "strongs": {
            "H34",
            "H490",
            "H1616",
            "H1800",
            "H3490",
            "H6041",
            "H6031",
            "H6231",
        },
        "lemmas": {
            "אֶבְיוֹן",
            "אַלְמָנָה",
            "גֵּר",
            "דַּל",
            "יָתוֹם",
            "עָנִי",
            "עָנָה",
            "עָשַׁק",
        },
        "gloss_terms": {
            "afflict",
            "lowly",
            "needy",
            "oppress",
            "orphan",
            "poor",
            "sojourner",
            "widow",
        },
        "review_roles": ["Hebrew", "ancient_cultural_context", "theology"],
        "weight": 1.1,
    },
    "death_sheol_mortality": {
        "label": "Death, Sheol, and Mortality",
        "description": (
            "Death, Sheol, grave, pit, dust, descent, perish/corruption, and mortality vocabulary."
        ),
        "strongs": {
            "H6",
            "H7585",
            "H4194",
            "H6913",
            "H953",
            "H6083",
            "H3381",
            "H7845",
        },
        "lemmas": {
            "אָבַד",
            "שְׁאוֹל",
            "מָוֶת",
            "קֶבֶר",
            "בּוֹר",
            "עָפָר",
            "יָרַד",
            "שָׁחַת",
        },
        "gloss_terms": {
            "death",
            "destroy",
            "dust",
            "grave",
            "pit",
            "perish",
            "sheol",
        },
        "review_roles": ["Hebrew", "ancient_cultural_context", "theology", "reception"],
        "weight": 1.15,
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
    return re.sub(r"\s+", " ", str(value or "")).strip()


def token_text(token: dict[str, Any]) -> str:
    features = token.get("compiler_features", {})
    parts = [
        token.get("lemma", ""),
        token.get("normalized", ""),
        token.get("surface", ""),
        token.get("display_gloss", ""),
        token.get("strong", ""),
    ]
    parts.extend(token.get("gloss_parts", []))
    parts.extend(features.get("english_parts", []))
    return " ".join(clean_text(part).lower() for part in parts if part is not None)


def token_domains(token: dict[str, Any]) -> list[str]:
    lemma = str(token.get("lemma") or "")
    strong = str(token.get("strong") or "")
    domains = []
    for domain_id, definition in DOMAIN_DEFINITIONS.items():
        if strong in definition["strongs"] or lemma in definition["lemmas"]:
            domains.append(domain_id)
    return domains


def lemma_label(token: dict[str, Any]) -> str:
    lemma = str(token.get("lemma") or "")
    if lemma and lemma not in {"הוּא", "None"}:
        return lemma
    strong = str(token.get("strong") or "")
    gloss = clean_text(token.get("display_gloss", ""))
    if strong and gloss:
        return f"{strong} {gloss}"
    if strong:
        return strong
    return lemma


def witness_texts(unit: dict[str, Any]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for witness in unit.get("witnesses", []):
        source_id = str(witness.get("source_id", ""))
        if source_id in ENGLISH_WITNESS_SOURCES:
            texts[source_id] = clean_text(witness.get("text", ""))
    return texts


def text_excerpt(text: str, limit: int = 155) -> str:
    compact = clean_text(text)
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def unit_lookup(report: dict[str, Any], row_key: str) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in report.get(row_key, []) if row.get("unit_id")}


def build_token_row(
    unit: dict[str, Any],
    token: dict[str, Any],
    domain_id: str,
) -> dict[str, Any]:
    definition = DOMAIN_DEFINITIONS[domain_id]
    return {
        "unit_id": unit["unit_id"],
        "ref": unit.get("ref", ""),
        "psalm_id": unit["psalm_id"],
        "token_id": token.get("token_id", ""),
        "domain_id": domain_id,
        "domain_label": definition["label"],
        "lemma": token.get("lemma", ""),
        "lemma_label": lemma_label(token),
        "normalized": token.get("normalized", ""),
        "surface": token.get("surface", ""),
        "display_gloss": token.get("display_gloss", ""),
        "strong": token.get("strong", ""),
        "part_of_speech": token.get("part_of_speech", ""),
        "morph_code": token.get("morph_code", ""),
    }


def unit_marker_flags(
    *,
    domain_counts: Counter[str],
    claim: dict[str, Any],
    reception: dict[str, Any],
    witness: dict[str, Any],
    divine: dict[str, Any],
    superscription: dict[str, Any],
) -> list[str]:
    markers = []
    if len(domain_counts) >= 3:
        markers.append("multi_domain_context_pressure")
    if (
        "temple_cult_sacred_space" in domain_counts
        and "kingship_davidic_political" in domain_counts
    ):
        markers.append("royal_cult_intersection")
    if "covenant_torah_wisdom" in domain_counts and "justice_enemy_violence" in domain_counts:
        markers.append("justice_torah_intersection")
    if (
        "nations_geography_identity" in domain_counts
        and "kingship_davidic_political" in domain_counts
    ):
        markers.append("nations_kingship_intersection")
    if "death_sheol_mortality" in domain_counts and "reception_sensitive" in claim.get(
        "claim_controls", []
    ):
        markers.append("death_reception_interpretation_pressure")
    if claim.get("ancient_culture_pressure"):
        markers.append("claim_matrix_ancient_culture_pressure")
    if claim.get("reception_sensitive") or reception.get("reception_sensitive"):
        markers.append("reception_sensitive")
    if claim.get("textual_witness_pressure") or reception.get("textual_witness_pressure"):
        markers.append("textual_witness_pressure")
    if float(witness.get("mean_english_witness_divergence_pct") or 0) >= 55:
        markers.append("high_english_witness_divergence")
    if divine:
        markers.append("divine_name_policy_overlap")
    if superscription:
        markers.append("superscription_context_overlap")
    return sorted(dict.fromkeys(markers))


def priority_score(
    *,
    token_count: int,
    domain_counts: Counter[str],
    markers: list[str],
    claim: dict[str, Any],
    reception: dict[str, Any],
    witness: dict[str, Any],
) -> float:
    score = token_count * 2.4
    for domain_id, count in domain_counts.items():
        score += count * float(DOMAIN_DEFINITIONS[domain_id]["weight"]) * 2.2
    score += len(domain_counts) * 9.0
    if "multi_domain_context_pressure" in markers:
        score += 18.0
    if "royal_cult_intersection" in markers:
        score += 14.0
    if "justice_torah_intersection" in markers:
        score += 12.0
    if "nations_kingship_intersection" in markers:
        score += 12.0
    if "death_reception_interpretation_pressure" in markers:
        score += 12.0
    if claim.get("ancient_culture_pressure"):
        score += 16.0
    if claim.get("reception_sensitive") or reception.get("reception_sensitive"):
        score += 14.0
    if claim.get("textual_witness_pressure") or reception.get("textual_witness_pressure"):
        score += 10.0
    score += min(34.0, float(claim.get("claim_risk_score") or 0) / 7.0)
    score += min(24.0, float(reception.get("boundary_risk_score") or 0) / 6.0)
    score += min(24.0, float(witness.get("priority_score") or 0) / 7.0)
    return round(score, 2)


def build_unit_row(
    unit: dict[str, Any],
    token_rows: list[dict[str, Any]],
    claim: dict[str, Any],
    reception: dict[str, Any],
    witness: dict[str, Any],
    divine: dict[str, Any],
    superscription: dict[str, Any],
) -> dict[str, Any]:
    domain_counts: Counter[str] = Counter(row["domain_id"] for row in token_rows)
    lemma_counts: Counter[str] = Counter(
        str(row["lemma_label"]) for row in token_rows if row["lemma_label"]
    )
    texts = witness_texts(unit)
    markers = unit_marker_flags(
        domain_counts=domain_counts,
        claim=claim,
        reception=reception,
        witness=witness,
        divine=divine,
        superscription=superscription,
    )
    score = priority_score(
        token_count=len(token_rows),
        domain_counts=domain_counts,
        markers=markers,
        claim=claim,
        reception=reception,
        witness=witness,
    )
    domain_ids = [domain_id for domain_id, _count in domain_counts.most_common()]
    return {
        "unit_id": unit["unit_id"],
        "ref": unit.get("ref", ""),
        "psalm_id": unit["psalm_id"],
        "domain_token_count": len(token_rows),
        "domain_count": len(domain_counts),
        "domain_ids": domain_ids,
        "domain_labels": [DOMAIN_DEFINITIONS[domain_id]["label"] for domain_id in domain_ids],
        "domain_counts": dict(domain_counts.most_common()),
        "top_lemmas": dict(lemma_counts.most_common(12)),
        "marker_flags": markers,
        "marker_count": len(markers),
        "claim_risk_score": claim.get("claim_risk_score", 0),
        "claim_risk_band": claim.get("claim_risk_band", ""),
        "boundary_risk_score": reception.get("boundary_risk_score", 0),
        "ancient_culture_pressure": bool(
            claim.get("ancient_culture_pressure") or reception.get("ancient_culture_pressure")
        ),
        "reception_sensitive": bool(
            claim.get("reception_sensitive") or reception.get("reception_sensitive")
        ),
        "textual_witness_pressure": bool(
            claim.get("textual_witness_pressure") or reception.get("textual_witness_pressure")
        ),
        "required_frames": claim.get("required_frames") or reception.get("required_frames", []),
        "witness_divergence_pct": witness.get("mean_english_witness_divergence_pct", 0),
        "witness_divergence_priority_score": witness.get("priority_score", 0),
        "divine_name_overlap": bool(divine),
        "superscription_context_overlap": bool(superscription),
        "priority_score": score,
        "source_hebrew": unit.get("source_hebrew", ""),
        "kjv_excerpt": text_excerpt(texts.get("kjv", "")),
        "asv_excerpt": text_excerpt(texts.get("asv", "")),
        "web_excerpt": text_excerpt(texts.get("web", "")),
        "token_ids": [row["token_id"] for row in token_rows],
        "token_surfaces": [row["surface"] for row in token_rows],
        "token_glosses": [row["display_gloss"] for row in token_rows],
    }


def build_rows(
    claims: dict[str, dict[str, Any]],
    receptions: dict[str, dict[str, Any]],
    witnesses: dict[str, dict[str, Any]],
    divine_units: dict[str, dict[str, Any]],
    superscription_units: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    token_rows = []
    unit_rows = []
    unit_count = 0
    for path in sorted(CONTENT_ROOT.glob("ps*/*.v*.json")):
        unit = load_json(path)
        unit_count += 1
        unit_token_rows = []
        for token in unit.get("tokens", []):
            for domain_id in token_domains(token):
                row = build_token_row(unit, token, domain_id)
                unit_token_rows.append(row)
                token_rows.append(row)
        if unit_token_rows:
            unit_id = str(unit["unit_id"])
            unit_rows.append(
                build_unit_row(
                    unit,
                    unit_token_rows,
                    claims.get(unit_id, {}),
                    receptions.get(unit_id, {}),
                    witnesses.get(unit_id, {}),
                    divine_units.get(unit_id, {}),
                    superscription_units.get(unit_id, {}),
                )
            )
    return token_rows, unit_rows, unit_count


def build_domain_rows(
    token_rows: list[dict[str, Any]], unit_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    token_counts: Counter[str] = Counter(row["domain_id"] for row in token_rows)
    unit_counts: Counter[str] = Counter()
    psalms_by_domain: dict[str, set[str]] = defaultdict(set)
    high_priority: Counter[str] = Counter()
    reception_sensitive: Counter[str] = Counter()
    ancient_culture: Counter[str] = Counter()
    textual_witness: Counter[str] = Counter()
    lemma_counts_by_domain: dict[str, Counter[str]] = defaultdict(Counter)

    for token in token_rows:
        lemma_counts_by_domain[token["domain_id"]][str(token["lemma_label"])] += 1
    for unit in unit_rows:
        for domain_id in unit["domain_ids"]:
            unit_counts[domain_id] += 1
            psalms_by_domain[domain_id].add(str(unit["psalm_id"]))
            if float(unit["priority_score"]) >= 90:
                high_priority[domain_id] += 1
            if unit["reception_sensitive"]:
                reception_sensitive[domain_id] += 1
            if unit["ancient_culture_pressure"]:
                ancient_culture[domain_id] += 1
            if unit["textual_witness_pressure"]:
                textual_witness[domain_id] += 1

    rows = []
    for domain_id, definition in DOMAIN_DEFINITIONS.items():
        top_lemmas = [
            {"lemma": lemma, "count": count}
            for lemma, count in lemma_counts_by_domain[domain_id].most_common(12)
            if lemma
        ]
        rows.append(
            {
                "domain_id": domain_id,
                "label": definition["label"],
                "description": definition["description"],
                "token_count": token_counts[domain_id],
                "unit_count": unit_counts[domain_id],
                "unit_pct": pct(unit_counts[domain_id], len(unit_rows)),
                "psalm_count": len(psalms_by_domain[domain_id]),
                "high_priority_unit_count": high_priority[domain_id],
                "ancient_culture_pressure_unit_count": ancient_culture[domain_id],
                "reception_sensitive_unit_count": reception_sensitive[domain_id],
                "textual_witness_pressure_unit_count": textual_witness[domain_id],
                "review_roles": definition["review_roles"],
                "top_lemmas": top_lemmas,
            }
        )
    return sorted(rows, key=lambda row: int(row["token_count"]), reverse=True)


def build_psalm_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in unit_rows:
        grouped[str(unit["psalm_id"])].append(unit)
    rows = []
    for psalm_id, psalm_units in grouped.items():
        domain_counts: Counter[str] = Counter()
        marker_counts: Counter[str] = Counter()
        for unit in psalm_units:
            domain_counts.update(unit["domain_counts"])
            marker_counts.update(unit["marker_flags"])
        top = sorted(psalm_units, key=lambda row: float(row["priority_score"]), reverse=True)[0]
        rows.append(
            {
                "psalm_id": psalm_id,
                "domain_unit_count": len(psalm_units),
                "domain_token_count": sum(int(unit["domain_token_count"]) for unit in psalm_units),
                "distinct_domain_count": len(domain_counts),
                "domain_counts": dict(domain_counts.most_common()),
                "marker_counts": dict(marker_counts.most_common()),
                "reception_sensitive_unit_count": sum(
                    1 for unit in psalm_units if unit["reception_sensitive"]
                ),
                "ancient_culture_pressure_unit_count": sum(
                    1 for unit in psalm_units if unit["ancient_culture_pressure"]
                ),
                "mean_priority_score": mean(
                    [float(unit["priority_score"]) for unit in psalm_units]
                ),
                "top_unit_id": top["unit_id"],
                "top_ref": top["ref"],
                "top_priority_score": top["priority_score"],
            }
        )
    return sorted(rows, key=lambda row: float(row["mean_priority_score"]), reverse=True)


def build_cooccurrence_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pair_counts: Counter[tuple[str, str]] = Counter()
    priority_sums: Counter[tuple[str, str]] = Counter()
    for unit in unit_rows:
        for left, right in combinations(sorted(unit["domain_ids"]), 2):
            pair_counts[(left, right)] += 1
            priority_sums[(left, right)] += int(float(unit["priority_score"]) * 100)
    rows = []
    for (left, right), count in pair_counts.most_common():
        rows.append(
            {
                "left_domain_id": left,
                "left_label": DOMAIN_DEFINITIONS[left]["label"],
                "right_domain_id": right,
                "right_label": DOMAIN_DEFINITIONS[right]["label"],
                "unit_count": count,
                "mean_priority_score": round(priority_sums[(left, right)] / count / 100, 2),
            }
        )
    return rows


def build_marker_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for unit in unit_rows:
        counts.update(unit["marker_flags"])
    return [
        {"marker": marker, "unit_count": count, "unit_pct": pct(count, len(unit_rows))}
        for marker, count in counts.most_common()
    ]


def chart_rows(rows: list[dict[str, Any]], label_key: str, value_key: str) -> list[dict[str, Any]]:
    return [{"label": str(row[label_key]), "value": row[value_key]} for row in rows]


def serializable_domain_definitions() -> dict[str, dict[str, Any]]:
    definitions = {}
    for domain_id, definition in DOMAIN_DEFINITIONS.items():
        definitions[domain_id] = {
            key: sorted(value) if isinstance(value, set) else value
            for key, value in definition.items()
        }
    return definitions


def build_report() -> dict[str, Any]:
    claim_report = maybe_load_json(CLAIM_MATRIX_PATH)
    reception_report = maybe_load_json(RECEPTION_BOUNDARY_PATH)
    witness_report = maybe_load_json(WITNESS_DIVERGENCE_PATH)
    divine_report = maybe_load_json(DIVINE_NAME_PATH)
    superscription_report = maybe_load_json(SUPERSCRIPTION_PATH)
    token_rows, unit_rows, unit_count = build_rows(
        unit_lookup(claim_report, "unit_claim_rows"),
        unit_lookup(reception_report, "unit_boundary_rows"),
        unit_lookup(witness_report, "unit_rows"),
        unit_lookup(divine_report, "unit_rows"),
        unit_lookup(superscription_report, "unit_rows"),
    )
    priority_rows = sorted(unit_rows, key=lambda row: float(row["priority_score"]), reverse=True)
    domain_rows = build_domain_rows(token_rows, priority_rows)
    psalm_rows = build_psalm_rows(priority_rows)
    cooccurrence_rows = build_cooccurrence_rows(priority_rows)
    marker_rows = build_marker_rows(priority_rows)
    high_priority_rows = [row for row in priority_rows if float(row["priority_score"]) >= 90]
    reception_rows = [row for row in priority_rows if row["reception_sensitive"]]
    ancient_culture_rows = [row for row in priority_rows if row["ancient_culture_pressure"]]
    textual_rows = [row for row in priority_rows if row["textual_witness_pressure"]]
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "cultural historical domain atlas generated; not cultural interpretation signoff",
        "source_paths": {
            "content_root": "content/psalms",
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
            "reception_boundary": str(RECEPTION_BOUNDARY_PATH.relative_to(ROOT)),
            "witness_divergence": str(WITNESS_DIVERGENCE_PATH.relative_to(ROOT)),
            "divine_name_policy": str(DIVINE_NAME_PATH.relative_to(ROOT)),
            "superscription_context": str(SUPERSCRIPTION_PATH.relative_to(ROOT)),
        },
        "method": {
            "boundary": (
                "Domain labels are lexeme/Strong/gloss routing heuristics for reviewer "
                "workload. They do not prove cultural background, dating, authorship, "
                "intertextual dependence, or Jewish/Christian interpretation."
            ),
            "domain_definitions": serializable_domain_definitions(),
            "review_roles": [
                "Hebrew",
                "ancient_cultural_context",
                "textual",
                "theology",
                "reception",
                "poetic",
            ],
        },
        "summary": {
            "unit_count": unit_count,
            "domain_unit_count": len(priority_rows),
            "domain_unit_pct": pct(len(priority_rows), unit_count),
            "domain_token_count": len(token_rows),
            "domain_count": len(DOMAIN_DEFINITIONS),
            "psalm_with_domain_count": len(psalm_rows),
            "high_priority_unit_count": len(high_priority_rows),
            "ancient_culture_pressure_unit_count": len(ancient_culture_rows),
            "reception_sensitive_unit_count": len(reception_rows),
            "textual_witness_pressure_unit_count": len(textual_rows),
            "cooccurrence_pair_count": len(cooccurrence_rows),
            "marker_type_count": len(marker_rows),
            "top_priority_unit": priority_rows[0]["unit_id"] if priority_rows else "",
            "top_priority_ref": priority_rows[0]["ref"] if priority_rows else "",
            "top_priority_score": priority_rows[0]["priority_score"] if priority_rows else 0.0,
            "top_priority_domains": priority_rows[0]["domain_labels"] if priority_rows else [],
            "status": "generated_not_signoff",
        },
        "domain_rows": domain_rows,
        "unit_rows": priority_rows,
        "token_rows": token_rows,
        "psalm_rows": psalm_rows,
        "cooccurrence_rows": cooccurrence_rows,
        "marker_rows": marker_rows,
        "visual_data": {
            "domain_token_counts": chart_rows(domain_rows, "label", "token_count"),
            "domain_unit_counts": chart_rows(domain_rows, "label", "unit_count"),
            "domain_high_priority_counts": chart_rows(
                domain_rows, "label", "high_priority_unit_count"
            ),
            "marker_counts": chart_rows(marker_rows, "marker", "unit_count"),
            "top_unit_priority": chart_rows(priority_rows[:20], "ref", "priority_score"),
            "top_psalm_priority": chart_rows(psalm_rows[:20], "psalm_id", "mean_priority_score"),
            "cooccurrence_counts": [
                {
                    "label": f"{row['left_label']} + {row['right_label']}",
                    "value": row["unit_count"],
                }
                for row in cooccurrence_rows[:20]
            ],
        },
    }


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
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 19}" font-size="12" '
            f'font-weight="700" fill="#24313a">{value:g}</text>'
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
    domain_rows = [
        [
            row["label"],
            row["token_count"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            row["psalm_count"],
            row["high_priority_unit_count"],
            row["ancient_culture_pressure_unit_count"],
            row["reception_sensitive_unit_count"],
            ", ".join(item["lemma"] for item in row["top_lemmas"][:8]),
        ]
        for row in report["domain_rows"]
    ]
    priority_rows = [
        [
            index + 1,
            row["ref"],
            f"{row['priority_score']:.2f}",
            row["domain_token_count"],
            "; ".join(row["domain_labels"]),
            "; ".join(row["marker_flags"]),
            row["kjv_excerpt"],
            row["asv_excerpt"],
            row["web_excerpt"],
        ]
        for index, row in enumerate(report["unit_rows"][:35])
    ]
    psalm_rows = [
        [
            row["psalm_id"],
            row["domain_unit_count"],
            row["domain_token_count"],
            row["distinct_domain_count"],
            row["ancient_culture_pressure_unit_count"],
            row["reception_sensitive_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["psalm_rows"][:35]
    ]
    cooccurrence_rows = [
        [
            row["left_label"],
            row["right_label"],
            row["unit_count"],
            f"{row['mean_priority_score']:.2f}",
        ]
        for row in report["cooccurrence_rows"][:30]
    ]
    marker_rows = [
        [row["marker"], row["unit_count"], f"{row['unit_pct']:.2f}%"]
        for row in report["marker_rows"]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cultural and Historical Domain Atlas</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #53616f;
      --line: #c9d1d9;
      --panel: #f8fafc;
      --accent: #2f6f73;
      --accent-2: #7c5b2f;
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
    h1 {{ font-size: 2.12rem; max-width: 1020px; }}
    h2 {{ margin-top: 36px; font-size: 1.45rem; }}
    h3 {{
      color: var(--muted);
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    p {{ color: var(--muted); margin: 8px 0 0; }}
    .lede {{ max-width: 1020px; font-size: 1.05rem; }}
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
  <h1>Cultural and Historical Domain Atlas for Psalm Translation Review</h1>
  <p class="lede">
    This report routes Psalm units into cultural and historical review domains
    using local Hebrew token lemmas, Strong identifiers, glosses, English
    witness excerpts, and existing reception/source-pressure reports.
  </p>
  <div class="callout">
    <strong>Authority boundary:</strong> {esc(report["method"]["boundary"])}
  </div>

  {
        metric_cards(
            [
                (
                    "Domain Units",
                    fmt_int(summary["domain_unit_count"]),
                    f"{fmt_pct(summary['domain_unit_pct'])} of Psalm units.",
                ),
                (
                    "Domain Tokens",
                    fmt_int(summary["domain_token_count"]),
                    f"{fmt_int(summary['domain_count'])} review domains.",
                ),
                (
                    "High Priority",
                    fmt_int(summary["high_priority_unit_count"]),
                    "Units scoring 90+ in this atlas.",
                ),
                (
                    "Ancient Culture",
                    fmt_int(summary["ancient_culture_pressure_unit_count"]),
                    "Cross-linked to claim/reception pressure.",
                ),
                (
                    "Reception",
                    fmt_int(summary["reception_sensitive_unit_count"]),
                    "Units already routed for reception separation.",
                ),
                (
                    "Top Unit",
                    summary["top_priority_ref"],
                    f"Priority score {summary['top_priority_score']:.2f}.",
                ),
            ]
        )
    }

  <section>
    <h2>Visual Domain Pressure</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Token Counts by Domain</h3>
        {
        svg_horizontal_bars(
            visual["domain_token_counts"],
            label_key="label",
            value_key="value",
            aria_label="Cultural domain token counts",
            color="#2f6f73",
        )
    }
      </div>
      <div class="panel">
        <h3>Unit Counts by Domain</h3>
        {
        svg_horizontal_bars(
            visual["domain_unit_counts"],
            label_key="label",
            value_key="value",
            aria_label="Cultural domain unit counts",
            color="#7c5b2f",
        )
    }
      </div>
      <div class="panel">
        <h3>Top Domain Co-Occurrences</h3>
        {
        svg_horizontal_bars(
            visual["cooccurrence_counts"],
            label_key="label",
            value_key="value",
            aria_label="Cultural domain co-occurrence counts",
            color="#9b3d3d",
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
            aria_label="Top cultural domain priority units",
            color="#2f6f73",
        )
    }
      </div>
    </div>
  </section>

  <section>
    <h2>Domain Summary</h2>
    {
        table(
            [
                "Domain",
                "Tokens",
                "Units",
                "Unit %",
                "Psalms",
                "High Priority",
                "Ancient Culture",
                "Reception",
                "Top Lemmas",
            ],
            domain_rows,
        )
    }
  </section>

  <section>
    <h2>Marker Summary</h2>
    {table(["Marker", "Unit Count", "Unit %"], marker_rows)}
  </section>

  <section>
    <h2>Highest Priority Units</h2>
    {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Tokens",
                "Domains",
                "Markers",
                "KJV",
                "ASV",
                "WEB",
            ],
            priority_rows,
        )
    }
  </section>

  <section>
    <h2>Psalm Summary</h2>
    {
        table(
            [
                "Psalm",
                "Units",
                "Tokens",
                "Domains",
                "Ancient Culture",
                "Reception",
                "Mean Priority",
                "Top Ref",
            ],
            psalm_rows,
        )
    }
  </section>

  <section>
    <h2>Domain Co-Occurrence</h2>
    {table(["Left Domain", "Right Domain", "Units", "Mean Priority"], cooccurrence_rows)}
  </section>

  <footer>
    Generated {esc(report["generated_at"])} from current local unit JSON and
    research reports. No canonical content is changed by this report.
  </footer>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a cultural and historical domain atlas for Psalm units."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument("--token-csv-output", type=Path, default=DEFAULT_TOKEN_CSV_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--domain-csv-output", type=Path, default=DEFAULT_DOMAIN_CSV_OUTPUT)
    parser.add_argument("--psalm-csv-output", type=Path, default=DEFAULT_PSALM_CSV_OUTPUT)
    parser.add_argument(
        "--cooccurrence-csv-output",
        type=Path,
        default=DEFAULT_COOCCURRENCE_CSV_OUTPUT,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.token_csv_output, report["token_rows"])
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.domain_csv_output, report["domain_rows"])
    write_csv(args.psalm_csv_output, report["psalm_rows"])
    write_csv(args.cooccurrence_csv_output, report["cooccurrence_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")


if __name__ == "__main__":
    main()
