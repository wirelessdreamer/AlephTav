from __future__ import annotations

import argparse
import csv
import html
import json
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "reports" / "research" / "benchmark_100_expansion_plan.json"
RUBRIC_PATH = ROOT / "docs" / "research" / "psalms_contextual_evaluation_rubric.json"
CONTENT_ROOT = ROOT / "content" / "psalms"
UXLC_ZIP_PATH = ROOT / "data" / "raw" / "uxlc" / "Tanach.xml.zip"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "benchmark_context_reception_matrix.json"
DEFAULT_CSV_OUTPUT = ROOT / "reports" / "research" / "benchmark_context_reception_matrix.csv"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "benchmark_context_reception_matrix.html"

PUNCTUATION = {
    "\u05be",
    "\u05c0",
    "\u05c3",
    "\u05c6",
    " ",
    "\t",
    "\n",
}

DIVISIONS = {
    "Genesis": "Torah",
    "Exodus": "Torah",
    "Leviticus": "Torah",
    "Numbers": "Torah",
    "Deuteronomy": "Torah",
    "Joshua": "Former Prophets",
    "Judges": "Former Prophets",
    "1 Samuel": "Former Prophets",
    "2 Samuel": "Former Prophets",
    "1 Kings": "Former Prophets",
    "2 Kings": "Former Prophets",
    "Isaiah": "Latter Prophets",
    "Jeremiah": "Latter Prophets",
    "Ezekiel": "Latter Prophets",
    "Hosea": "The Twelve",
    "Joel": "The Twelve",
    "Amos": "The Twelve",
    "Obadiah": "The Twelve",
    "Jonah": "The Twelve",
    "Micah": "The Twelve",
    "Nahum": "The Twelve",
    "Habakkuk": "The Twelve",
    "Zephaniah": "The Twelve",
    "Haggai": "The Twelve",
    "Zechariah": "The Twelve",
    "Malachi": "The Twelve",
    "Psalms": "Writings",
    "Proverbs": "Writings",
    "Job": "Writings",
    "Song of Songs": "Writings",
    "Ruth": "Writings",
    "Lamentations": "Writings",
    "Ecclesiastes": "Writings",
    "Esther": "Writings",
    "Daniel": "Writings",
    "Ezra": "Writings",
    "Nehemiah": "Writings",
    "1 Chronicles": "Writings",
    "2 Chronicles": "Writings",
}

MAX_REF_SAMPLES = 8
MAX_DOMAIN_EVIDENCE = 8

RECEPTION_PSALMS = {
    "ps002": {
        "label": "royal sonship and messianic reception",
        "frames": [
            "source_hebrew_plain_sense",
            "ancient_royal_ideology",
            "jewish_reception",
            "christian_reception",
            "academic_critical_comparison",
        ],
    },
    "ps008": {
        "label": "human vocation and later theological reuse",
        "frames": [
            "source_hebrew_plain_sense",
            "creation_anthropology",
            "jewish_reception",
            "christian_reception",
            "academic_critical_comparison",
        ],
    },
    "ps016": {
        "label": "life, death, and resurrection reception",
        "frames": [
            "source_hebrew_plain_sense",
            "mortality_language",
            "jewish_reception",
            "christian_reception",
            "academic_critical_comparison",
        ],
    },
    "ps022": {
        "label": "suffering lament and later liturgical reception",
        "frames": [
            "source_hebrew_plain_sense",
            "lament_genre",
            "jewish_reception",
            "christian_reception",
            "academic_critical_comparison",
        ],
    },
    "ps045": {
        "label": "royal wedding and divine/royal address",
        "frames": [
            "source_hebrew_plain_sense",
            "ancient_royal_ideology",
            "jewish_reception",
            "christian_reception",
            "academic_critical_comparison",
        ],
    },
    "ps069": {
        "label": "lament, zeal, and reception reuse",
        "frames": [
            "source_hebrew_plain_sense",
            "lament_genre",
            "jewish_reception",
            "christian_reception",
            "academic_critical_comparison",
        ],
    },
    "ps072": {
        "label": "royal justice and universal nations language",
        "frames": [
            "source_hebrew_plain_sense",
            "ancient_royal_ideology",
            "jewish_reception",
            "christian_reception",
            "academic_critical_comparison",
        ],
    },
    "ps089": {
        "label": "Davidic covenant and royal crisis",
        "frames": [
            "source_hebrew_plain_sense",
            "davidic_covenant",
            "jewish_reception",
            "christian_reception",
            "academic_critical_comparison",
        ],
    },
    "ps110": {
        "label": "royal oracle, priesthood, and messianic reception",
        "frames": [
            "source_hebrew_plain_sense",
            "ancient_royal_ideology",
            "jewish_reception",
            "christian_reception",
            "academic_critical_comparison",
        ],
    },
    "ps118": {
        "label": "liturgical procession and later reception reuse",
        "frames": [
            "source_hebrew_plain_sense",
            "temple_liturgy",
            "jewish_reception",
            "christian_reception",
            "academic_critical_comparison",
        ],
    },
}

FAMILIAR_LICENSE_PSALMS = {
    "ps001",
    "ps023",
    "ps051",
    "ps091",
    "ps103",
    "ps121",
    "ps137",
    "ps150",
}

DOMAIN_DEFS = {
    "royal_kingship": {
        "label": "Royal and kingship context",
        "strongs": {
            "H4428",
            "H1732",
            "H4899",
            "H3678",
            "H4467",
            "H4427",
        },
        "tags": {
            "royal_psalm",
            "messianic_interpretation",
            "sonship",
            "nations",
            "priesthood",
            "melchizedek",
        },
        "psalms": {"ps002", "ps045", "ps072", "ps089", "ps110"},
        "gloss_terms": {"king", "david", "anointed", "throne", "kingdom"},
    },
    "temple_cult_liturgy": {
        "label": "Temple, cult, and liturgical setting",
        "strongs": {
            "H1964",
            "H1004",
            "H2077",
            "H4210",
            "H7892",
            "H5329",
            "H5542",
            "H6944",
            "H3548",
        },
        "tags": {
            "doxology",
            "liturgical_closure",
            "liturgical_afterlife",
            "short_psalm",
            "universal_praise",
        },
        "psalms": {"ps029", "ps047", "ps096", "ps100", "ps118", "ps150"},
        "gloss_terms": {"temple", "house", "sacrifice", "psalm", "song"},
    },
    "wisdom_torah": {
        "label": "Wisdom, Torah, and moral contrast",
        "strongs": {
            "H835",
            "H8451",
            "H1870",
            "H7563",
            "H6662",
            "H3372",
            "H4687",
            "H2706",
            "H6490",
            "H5715",
            "H4941",
        },
        "tags": {
            "wisdom",
            "torah_psalm",
            "divine_instruction_terms",
            "fear_of_yhwh",
            "blessing_formula",
            "torah_walk",
        },
        "psalms": {"ps001", "ps019", "ps037", "ps112", "ps119", "ps128"},
        "gloss_terms": {"blessed", "law", "way", "wicked", "righteous"},
    },
    "lament_enemy_justice": {
        "label": "Lament, enemies, and justice rhetoric",
        "strongs": {
            "H341",
            "H7563",
            "H6862",
            "H8130",
            "H4194",
            "H7585",
            "H1832",
            "H4941",
            "H5359",
            "H6664",
        },
        "tags": {
            "lament",
            "imprecation",
            "violence",
            "trauma_context",
            "suffering_lament",
            "justice",
            "vengeance",
        },
        "psalms": {"ps003", "ps007", "ps013", "ps022", "ps051", "ps069", "ps137"},
        "gloss_terms": {"enemy", "wicked", "death", "sheol", "justice"},
    },
    "covenant_mercy": {
        "label": "Covenant, mercy, and faithfulness",
        "strongs": {"H2617", "H571", "H1285", "H2142", "H530", "H7349"},
        "tags": {"hesed", "mercy", "theology"},
        "psalms": {"ps013", "ps051", "ps089", "ps103", "ps105", "ps106"},
        "gloss_terms": {"mercy", "lovingkindness", "truth", "covenant"},
    },
    "creation_cosmos": {
        "label": "Creation, cosmos, and natural order",
        "strongs": {"H8064", "H776", "H3220", "H8121", "H3394", "H3556", "H8415"},
        "tags": {"creation_hymn", "creator_argument"},
        "psalms": {"ps008", "ps019", "ps033", "ps104", "ps136", "ps148"},
        "gloss_terms": {"heaven", "earth", "sea", "sun", "moon", "stars"},
    },
    "anthropology_body": {
        "label": "Body, soul, heart, and anthropology",
        "strongs": {
            "H5315",
            "H3820",
            "H3824",
            "H7307",
            "H1320",
            "H6106",
            "H3027",
            "H6440",
            "H5869",
            "H6310",
        },
        "tags": {"anthropology", "body_imagery", "heart", "spirit", "breath_life"},
        "psalms": {"ps008", "ps023", "ps051", "ps103", "ps139", "ps150"},
        "gloss_terms": {"soul", "heart", "spirit", "flesh", "hand", "face"},
    },
    "nations_zion_exile": {
        "label": "Nations, Zion, land, and exile memory",
        "strongs": {"H1471", "H5971", "H6726", "H3389", "H894", "H776"},
        "tags": {"nations", "universal_praise", "trauma_context"},
        "psalms": {"ps002", "ps047", "ps069", "ps072", "ps096", "ps137"},
        "gloss_terms": {"nations", "peoples", "zion", "jerusalem", "babylon"},
    },
    "divine_names_titles": {
        "label": "Divine names, titles, and naming policy",
        "strongs": {"H3068", "H430", "H136", "H410", "H113", "H5945"},
        "tags": {"divine_name_policy", "divine_title", "divine_address", "theology"},
        "psalms": set(),
        "gloss_terms": {"yhwh", "lord", "god", "most high", "adonai"},
    },
    "textual_witness_pressure": {
        "label": "Textual witness and provenance pressure",
        "strongs": set(),
        "tags": {"textual_witness", "textual_sensitivity", "lexical_dispute"},
        "psalms": set(),
        "gloss_terms": set(),
    },
    "jewish_christian_reception": {
        "label": "Jewish/Christian reception-history sensitivity",
        "strongs": set(),
        "tags": {
            "reception_history",
            "jewish_christian_reception",
            "messianic_interpretation",
            "liturgical_afterlife",
        },
        "psalms": set(RECEPTION_PSALMS),
        "gloss_terms": set(),
    },
}

DEFAULT_REVIEW_ROLES = ["lexical", "Hebrew", "alignment"]


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def canonical_book_file(name: str) -> bool:
    if not name.startswith("Books/") or not name.endswith(".xml"):
        return False
    if name.endswith(".DH.xml"):
        return False
    if name.endswith("TanachHeader.xml") or name.endswith("TanachIndex.xml"):
        return False
    return True


def normalize_hebrew_form(text: str | None) -> str:
    if not text:
        return ""
    chars = []
    for char in unicodedata.normalize("NFKD", text):
        if unicodedata.category(char) == "Mn":
            continue
        if char in PUNCTUATION:
            continue
        chars.append(char)
    return "".join(chars)


def add_sample(samples: list[str], ref: str) -> None:
    if len(samples) < MAX_REF_SAMPLES and ref not in samples:
        samples.append(ref)


def build_form_index(zip_path: Path) -> dict[str, Any]:
    index: dict[str, dict[str, Any]] = {}
    summary = Counter()

    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(name for name in archive.namelist() if canonical_book_file(name))
        for name in names:
            root = ET.fromstring(archive.read(name))
            book = root.find("./tanach/book")
            names_el = book.find("names") if book is not None else None
            book_name = names_el.findtext("name") if names_el is not None else Path(name).stem
            book_name = str(book_name)
            division = DIVISIONS.get(book_name, "Unmapped")
            summary["book_count"] += 1
            for chapter in root.findall(".//c"):
                chapter_num = str(chapter.get("n") or "")
                summary["chapter_count"] += 1
                for verse in chapter.findall("./v"):
                    verse_num = str(verse.get("n") or "")
                    ref = f"{book_name} {chapter_num}:{verse_num}"
                    summary["verse_count"] += 1
                    for word in verse.findall("./w"):
                        normalized = normalize_hebrew_form("".join(word.itertext()))
                        if not normalized:
                            continue
                        summary["word_elements"] += 1
                        entry = index.setdefault(
                            normalized,
                            {
                                "form": normalized,
                                "tanakh_count": 0,
                                "psalms_count": 0,
                                "outside_psalms_count": 0,
                                "division_counts": Counter(),
                                "book_counts": Counter(),
                                "outside_psalms_sample_refs": [],
                            },
                        )
                        entry["tanakh_count"] += 1
                        entry["division_counts"][division] += 1
                        entry["book_counts"][book_name] += 1
                        if book_name == "Psalms":
                            entry["psalms_count"] += 1
                        else:
                            entry["outside_psalms_count"] += 1
                            add_sample(entry["outside_psalms_sample_refs"], ref)

    serializable = {}
    for form, entry in index.items():
        serializable[form] = {
            "form": form,
            "tanakh_count": entry["tanakh_count"],
            "psalms_count": entry["psalms_count"],
            "outside_psalms_count": entry["outside_psalms_count"],
            "division_counts": dict(sorted(entry["division_counts"].items())),
            "book_counts": dict(entry["book_counts"].most_common(10)),
            "outside_psalms_sample_refs": entry["outside_psalms_sample_refs"],
        }
    summary["distinct_forms"] = len(serializable)
    return {"summary": dict(summary), "forms": serializable}


def context_summary(form_index: dict[str, Any], query: str) -> dict[str, Any]:
    entry = form_index.get(query)
    if not entry:
        return {
            "query": query,
            "matched": False,
            "tanakh_count": 0,
            "psalms_count": 0,
            "outside_psalms_count": 0,
            "division_counts": {},
            "book_counts": {},
            "outside_psalms_sample_refs": [],
        }
    return {
        "query": query,
        "matched": True,
        "tanakh_count": entry["tanakh_count"],
        "psalms_count": entry["psalms_count"],
        "outside_psalms_count": entry["outside_psalms_count"],
        "division_counts": entry["division_counts"],
        "book_counts": entry["book_counts"],
        "outside_psalms_sample_refs": entry["outside_psalms_sample_refs"],
    }


def unit_path(unit_id: str) -> Path:
    psalm_id = unit_id.split(".")[0]
    return CONTENT_ROOT / psalm_id / f"{unit_id}.json"


def witness_summary(data: dict[str, Any]) -> dict[str, Any]:
    roles: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    for witness in data.get("witnesses") or []:
        roles[str(witness.get("witness_role") or "unknown")] += 1
        sources[str(witness.get("source_id") or "unknown")] += 1
        languages[str(witness.get("language") or "unknown")] += 1
    return {
        "count": sum(roles.values()),
        "roles": dict(sorted(roles.items())),
        "sources": dict(sorted(sources.items())),
        "languages": dict(sorted(languages.items())),
    }


def token_text(token: dict[str, Any]) -> str:
    values = [
        token.get("display_gloss"),
        token.get("word_sense"),
        " ".join(str(part) for part in token.get("gloss_parts") or []),
    ]
    features = token.get("compiler_features") or {}
    values.append(" ".join(str(part) for part in features.get("english_parts") or []))
    values.append(" ".join(str(part) for part in features.get("gloss_fragments") or []))
    return " ".join(str(value).lower() for value in values if value)


def token_feature_counts(tokens: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for token in tokens:
        features = token.get("compiler_features") or {}
        if int(features.get("component_count") or 0) > 1:
            counts["multi_component"] += 1
        for key in [
            "construct_state",
            "divine_name",
            "suffix_pronoun",
            "temporal_pair_candidate",
        ]:
            if features.get(key):
                counts[key] += 1
        for key in ["preposition_role", "discourse_marker", "conjunction_role"]:
            if features.get(key):
                counts[key] += 1
    return counts


def add_domain_hit(
    hits: dict[str, list[str]],
    domain: str,
    evidence: str,
) -> None:
    if evidence not in hits[domain]:
        hits[domain].append(evidence)


def domain_hits_for_unit(
    *,
    data: dict[str, Any],
    plan_row: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    hits: dict[str, list[str]] = defaultdict(list)
    psalm_id = str(plan_row["psalm_id"])
    tags = {str(tag) for tag in plan_row.get("benchmark_tags") or []}
    tokens = data.get("tokens") or []

    for domain, definition in DOMAIN_DEFS.items():
        if psalm_id in definition["psalms"]:
            add_domain_hit(hits, domain, f"psalm_class:{psalm_id}")
        for tag in sorted(tags & definition["tags"]):
            add_domain_hit(hits, domain, f"benchmark_tag:{tag}")

    if plan_row["primary_stratum"] == "textual_witness_cases":
        add_domain_hit(
            hits,
            "textual_witness_pressure",
            "benchmark_stratum:textual_witness_cases",
        )
    if plan_row["primary_stratum"] == "jewish_christian_reception_cases":
        add_domain_hit(
            hits,
            "jewish_christian_reception",
            "benchmark_stratum:jewish_christian_reception_cases",
        )
    if psalm_id in FAMILIAR_LICENSE_PSALMS:
        add_domain_hit(hits, "textual_witness_pressure", f"familiar_psalm:{psalm_id}")

    for token in tokens:
        strong = str(token.get("strong") or "")
        text = token_text(token)
        features = token.get("compiler_features") or {}
        for domain, definition in DOMAIN_DEFS.items():
            if strong and strong in definition["strongs"]:
                add_domain_hit(
                    hits,
                    domain,
                    f"{token.get('token_id')}:strong:{strong}",
                )
            for term in definition["gloss_terms"]:
                if term in text:
                    add_domain_hit(
                        hits,
                        domain,
                        f"{token.get('token_id')}:gloss:{term}",
                    )
        if features.get("divine_name"):
            add_domain_hit(
                hits,
                "divine_names_titles",
                f"{token.get('token_id')}:compiler:divine_name",
            )

    if float(plan_row.get("greek_coverage_pct") or 0.0) < 100.0:
        add_domain_hit(
            hits,
            "textual_witness_pressure",
            f"greek_coverage:{plan_row.get('greek_coverage_pct')}%",
        )

    return {
        domain: {
            "label": DOMAIN_DEFS[domain]["label"],
            "hit_count": len(evidence),
            "evidence": evidence[:MAX_DOMAIN_EVIDENCE],
        }
        for domain, evidence in sorted(hits.items())
        if evidence
    }


def token_context_coverage(
    *,
    tokens: list[dict[str, Any]],
    form_index: dict[str, Any],
) -> dict[str, Any]:
    surface_matches = 0
    surface_outside = 0
    outside_total = 0
    division_counts: Counter[str] = Counter()
    missing_enrichments: Counter[str] = Counter()
    high_context_tokens = []

    for token in tokens:
        query = normalize_hebrew_form(token.get("surface"))
        summary = context_summary(form_index, query)
        if summary["matched"]:
            surface_matches += 1
        outside_count = int(summary["outside_psalms_count"])
        if outside_count:
            surface_outside += 1
            outside_total += outside_count
            division_counts.update(summary["division_counts"])
            high_context_tokens.append(
                {
                    "token_id": token.get("token_id"),
                    "surface": token.get("surface"),
                    "display_gloss": token.get("display_gloss"),
                    "surface_query": query,
                    "outside_psalms_count": outside_count,
                    "outside_psalms_sample_refs": summary["outside_psalms_sample_refs"],
                }
            )
        missing_enrichments.update(str(item) for item in token.get("missing_enrichments", []))

    token_count = len(tokens)
    return {
        "surface_form_matches": surface_matches,
        "surface_form_match_pct": pct(surface_matches, token_count),
        "surface_forms_with_outside_psalms_context": surface_outside,
        "surface_outside_context_pct": pct(surface_outside, token_count),
        "outside_psalms_surface_occurrence_total": outside_total,
        "outside_context_division_counts": dict(division_counts.most_common()),
        "missing_enrichment_counts": dict(missing_enrichments.most_common()),
        "high_context_tokens": sorted(
            high_context_tokens,
            key=lambda row: int(row["outside_psalms_count"]),
            reverse=True,
        )[:8],
    }


def reception_profile(psalm_id: str, domain_hits: dict[str, Any]) -> dict[str, Any]:
    if psalm_id in RECEPTION_PSALMS:
        profile = RECEPTION_PSALMS[psalm_id]
        return {
            "sensitive": True,
            "label": profile["label"],
            "required_frames": profile["frames"],
        }
    if "jewish_christian_reception" in domain_hits:
        return {
            "sensitive": True,
            "label": "benchmark-tagged reception-history sensitivity",
            "required_frames": [
                "source_hebrew_plain_sense",
                "jewish_reception",
                "christian_reception",
                "academic_critical_comparison",
            ],
        }
    return {
        "sensitive": False,
        "label": "no special reception-history class detected",
        "required_frames": ["source_hebrew_plain_sense"],
    }


def review_roles_for_unit(
    plan_row: dict[str, Any],
    domain_hits: dict[str, Any],
    reception: dict[str, Any],
) -> list[str]:
    roles = list(DEFAULT_REVIEW_ROLES)
    if plan_row["primary_stratum"] == "poetic_parallelism_traps":
        roles.append("lyric")
    if reception["sensitive"]:
        roles.append("theology")
    if "divine_names_titles" in domain_hits or "anthropology_body" in domain_hits:
        roles.append("theology")
    if "temple_cult_liturgy" in domain_hits:
        roles.append("theology")
    return sorted(set(roles), key=["lexical", "Hebrew", "alignment", "lyric", "theology"].index)


def model_controls_for_unit(
    domain_hits: dict[str, Any],
    reception: dict[str, Any],
) -> list[str]:
    controls = [
        "cite token_id evidence for every lexical claim",
        "separate translation claims from interpretive or reception claims",
    ]
    if "textual_witness_pressure" in domain_hits:
        controls.append("label witnesses as witnesses, never as canonical Hebrew source")
    if reception["sensitive"]:
        controls.append("compare Jewish and Christian reception as tagged viewpoints")
    if "divine_names_titles" in domain_hits:
        controls.append("apply project divine-name policy before stylistic smoothing")
    if "anthropology_body" in domain_hits:
        controls.append("avoid abstracting body/soul/heart terms without rationale")
    if "wisdom_torah" in domain_hits:
        controls.append("check Torah/wisdom vocabulary across the broader canon")
    return controls


def pressure_score(
    *,
    plan_row: dict[str, Any],
    domain_hits: dict[str, Any],
    context_coverage: dict[str, Any],
    reception: dict[str, Any],
) -> float:
    score = min(6.0, float(plan_row.get("feature_pressure") or 0) / 2.0)
    score += 1.8 * len(domain_hits)
    if reception["sensitive"]:
        score += 4.0
    if "textual_witness_pressure" in domain_hits:
        score += 2.5
    if float(context_coverage["surface_outside_context_pct"]) >= 75.0:
        score += 1.5
    return round(score, 2)


def pressure_intensity(score: float) -> str:
    if score >= 16.0:
        return "high"
    if score >= 9.0:
        return "medium"
    return "standard"


def unit_matrix_row(
    plan_row: dict[str, Any],
    *,
    form_index: dict[str, Any],
) -> dict[str, Any]:
    data = load_json(unit_path(plan_row["unit_id"]))
    tokens = data.get("tokens") or []
    domain_hits = domain_hits_for_unit(data=data, plan_row=plan_row)
    context_coverage = token_context_coverage(tokens=tokens, form_index=form_index)
    reception = reception_profile(str(plan_row["psalm_id"]), domain_hits)
    score = pressure_score(
        plan_row=plan_row,
        domain_hits=domain_hits,
        context_coverage=context_coverage,
        reception=reception,
    )
    return {
        "unit_id": plan_row["unit_id"],
        "ref": plan_row["ref"],
        "psalm_id": plan_row["psalm_id"],
        "primary_stratum": plan_row["primary_stratum"],
        "source": plan_row["source"],
        "token_count": len(tokens),
        "source_hebrew": data.get("source_hebrew"),
        "feature_pressure": plan_row["feature_pressure"],
        "feature_counts": plan_row.get("feature_counts", {}),
        "token_feature_counts": dict(token_feature_counts(tokens).most_common()),
        "witness_summary": witness_summary(data),
        "plan_witness_count": plan_row.get("witness_count"),
        "plan_greek_coverage_pct": plan_row.get("greek_coverage_pct"),
        "context_coverage": context_coverage,
        "context_domains": domain_hits,
        "domain_count": len(domain_hits),
        "reception_profile": reception,
        "review_roles": review_roles_for_unit(plan_row, domain_hits, reception),
        "model_controls": model_controls_for_unit(domain_hits, reception),
        "context_pressure_score": score,
        "context_pressure_intensity": pressure_intensity(score),
        "benchmark_tags": plan_row.get("benchmark_tags", []),
        "selection_reason": plan_row.get("selection_reason"),
    }


def aggregate_matrix(rows: list[dict[str, Any]], form_summary: dict[str, Any]) -> dict[str, Any]:
    domain_counts: Counter[str] = Counter()
    domain_hit_counts: Counter[str] = Counter()
    intensity_counts: Counter[str] = Counter()
    stratum_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    review_role_counts: Counter[str] = Counter()
    reception_psalms: Counter[str] = Counter()
    missing_enrichment_counts: Counter[str] = Counter()
    outside_divisions: Counter[str] = Counter()
    total_tokens = 0
    surface_matches = 0
    surface_outside = 0
    high_pressure_units = 0
    reception_units = 0
    textual_units = 0

    for row in rows:
        total_tokens += int(row["token_count"])
        coverage = row["context_coverage"]
        surface_matches += int(coverage["surface_form_matches"])
        surface_outside += int(coverage["surface_forms_with_outside_psalms_context"])
        intensity_counts[row["context_pressure_intensity"]] += 1
        stratum_counts[row["primary_stratum"]] += 1
        source_counts[row["source"]] += 1
        review_role_counts.update(row["review_roles"])
        missing_enrichment_counts.update(coverage["missing_enrichment_counts"])
        outside_divisions.update(coverage["outside_context_division_counts"])
        if row["context_pressure_intensity"] == "high":
            high_pressure_units += 1
        if row["reception_profile"]["sensitive"]:
            reception_units += 1
            reception_psalms[row["psalm_id"]] += 1
        if "textual_witness_pressure" in row["context_domains"]:
            textual_units += 1
        for domain, data in row["context_domains"].items():
            domain_counts[domain] += 1
            domain_hit_counts[domain] += int(data["hit_count"])

    return {
        "unit_count": len(rows),
        "token_count": total_tokens,
        "surface_form_matches": surface_matches,
        "surface_form_match_pct": pct(surface_matches, total_tokens),
        "surface_forms_with_outside_psalms_context": surface_outside,
        "surface_outside_context_pct": pct(surface_outside, total_tokens),
        "high_pressure_units": high_pressure_units,
        "reception_sensitive_units": reception_units,
        "textual_witness_pressure_units": textual_units,
        "domain_counts": dict(domain_counts.most_common()),
        "domain_hit_counts": dict(domain_hit_counts.most_common()),
        "intensity_counts": dict(intensity_counts.most_common()),
        "stratum_counts": dict(stratum_counts.most_common()),
        "source_counts": dict(source_counts.most_common()),
        "review_role_counts": dict(review_role_counts.most_common()),
        "reception_psalm_counts": dict(reception_psalms.most_common()),
        "missing_enrichment_counts": dict(missing_enrichment_counts.most_common()),
        "outside_context_division_counts": dict(outside_divisions.most_common()),
        "uxlc_form_index_summary": form_summary,
    }


def build_report(
    *,
    plan_path: Path,
    rubric_path: Path,
    uxlc_zip_path: Path,
) -> dict[str, Any]:
    plan = load_json(plan_path)
    rubric = load_json(rubric_path)
    index = build_form_index(uxlc_zip_path)
    rows = [unit_matrix_row(row, form_index=index["forms"]) for row in plan["selected_units"]]
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": (
            "generated benchmark context/reception matrix; heuristic routing, "
            "not expert interpretation"
        ),
        "source_paths": {
            "benchmark_plan": "reports/research/benchmark_100_expansion_plan.json",
            "contextual_rubric": "docs/research/psalms_contextual_evaluation_rubric.json",
            "content_root": "content/psalms",
            "uxlc_zip": "data/raw/uxlc/Tanach.xml.zip",
        },
        "normalization": {
            "method": "NFKD; remove combining marks, Hebrew punctuation, and whitespace",
            "warning": (
                "Whole-Tanakh context counts are normalized surface-form counts, "
                "not lemma-aware sense evidence."
            ),
        },
        "selection_method": {
            "principles": [
                "Keep translation, interpretation, and reception categories separate.",
                "Route sensitive units to review roles; do not assert final readings.",
                "Use project corpus features, witnesses, Psalm class, and UXLC forms.",
                "Treat Jewish and Christian reception as tagged viewpoints for review.",
            ],
            "limitations": [
                "Domain detection is heuristic and must be audited by reviewers.",
                "Ancient cultural context is routed by lexical and Psalm-class proxies.",
                "Raw UXLC form context is read-only and remains form-level evidence.",
                "No proprietary commentaries or lexicons are ingested.",
            ],
            "rubric_context_layer_count": len(rubric.get("context_layers", [])),
            "rubric_case_study_count": len(rubric.get("case_studies", [])),
        },
        "summary": aggregate_matrix(rows, index["summary"]),
        "domain_definitions": {
            key: {
                "label": value["label"],
                "strong_count": len(value["strongs"]),
                "tag_count": len(value["tags"]),
                "psalm_class_count": len(value["psalms"]),
                "gloss_term_count": len(value["gloss_terms"]),
            }
            for key, value in DOMAIN_DEFS.items()
        },
        "unit_rows": rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "unit_id",
        "ref",
        "primary_stratum",
        "source",
        "token_count",
        "context_pressure_score",
        "context_pressure_intensity",
        "domain_count",
        "context_domains",
        "reception_sensitive",
        "required_reception_frames",
        "review_roles",
        "surface_outside_context_pct",
        "witness_count",
        "greek_coverage_pct",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "unit_id": row["unit_id"],
                    "ref": row["ref"],
                    "primary_stratum": row["primary_stratum"],
                    "source": row["source"],
                    "token_count": row["token_count"],
                    "context_pressure_score": row["context_pressure_score"],
                    "context_pressure_intensity": row["context_pressure_intensity"],
                    "domain_count": row["domain_count"],
                    "context_domains": ";".join(row["context_domains"]),
                    "reception_sensitive": row["reception_profile"]["sensitive"],
                    "required_reception_frames": ";".join(
                        row["reception_profile"]["required_frames"]
                    ),
                    "review_roles": ";".join(row["review_roles"]),
                    "surface_outside_context_pct": row["context_coverage"][
                        "surface_outside_context_pct"
                    ],
                    "witness_count": row["witness_summary"]["count"],
                    "greek_coverage_pct": row["plan_greek_coverage_pct"],
                }
            )


def rows_from_counter(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
    return [
        {label_key: label, "count": count}
        for label, count in sorted(counter.items(), key=lambda item: item[1], reverse=True)
    ]


def bucket_pressure(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = Counter(row["context_pressure_intensity"] for row in rows)
    order = {"high": 0, "medium": 1, "standard": 2}
    return [
        {"intensity": key, "count": value}
        for key, value in sorted(buckets.items(), key=lambda item: order[item[0]])
    ]


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
    row_h = 29
    left = 300
    right = 58
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
        label = str(row[label_key])
        parts.append(
            f'<text x="{left - 12}" y="{y + 19}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(label)}</text>'
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


def svg_pressure_units(rows: list[dict[str, Any]]) -> str:
    chart_rows = [
        {
            "unit": row["unit_id"],
            "score": row["context_pressure_score"],
        }
        for row in sorted(
            rows,
            key=lambda item: float(item["context_pressure_score"]),
            reverse=True,
        )[:30]
    ]
    return svg_horizontal_bars(
        chart_rows,
        label_key="unit",
        value_key="score",
        aria_label="Highest context pressure units",
        color="#7c5b2f",
        limit=30,
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
    rows = report["unit_rows"]
    top_rows = sorted(
        rows,
        key=lambda item: float(item["context_pressure_score"]),
        reverse=True,
    )[:30]
    unit_table = [
        [
            row["unit_id"],
            row["ref"],
            row["primary_stratum"],
            row["context_pressure_intensity"],
            row["context_pressure_score"],
            ", ".join(row["context_domains"]),
            row["reception_profile"]["label"],
            ", ".join(row["review_roles"]),
        ]
        for row in top_rows
    ]
    reception_rows = [
        [
            row["unit_id"],
            row["ref"],
            row["reception_profile"]["label"],
            ", ".join(row["reception_profile"]["required_frames"]),
        ]
        for row in rows
        if row["reception_profile"]["sensitive"]
    ]
    domain_rows = [
        [
            domain,
            DOMAIN_DEFS[domain]["label"],
            count,
            summary["domain_hit_counts"].get(domain, 0),
        ]
        for domain, count in summary["domain_counts"].items()
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Benchmark Context and Reception Matrix</title>
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
    main {{ max-width: 1180px; margin: 0 auto; padding: 30px 34px 54px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    p {{ margin: 0 0 13px; }}
    .lede {{ max-width: 990px; font-size: 17px; color: #33414c; }}
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
    <h1>AlephTav Benchmark Context and Reception Matrix</h1>
    <p class="lede">
      Context-pressure analysis for the 100-unit benchmark expansion. This
      report routes units by lexical domain, witness pressure, whole-Tanakh
      form context, and Jewish/Christian reception sensitivity while keeping
      translation claims separate from interpretive viewpoints.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Matrix Summary</h2>
      {
        metric_cards(
            [
                ("Units", fmt_int(summary["unit_count"]), "Benchmark expansion units analyzed."),
                (
                    "Tokens",
                    fmt_int(summary["token_count"]),
                    "Hebrew token records in analyzed units.",
                ),
                (
                    "Outside context",
                    f'''{summary["surface_outside_context_pct"]:.2f}%''',
                    "Tokens with non-Psalms normalized surface-form context.",
                ),
                (
                    "Reception units",
                    fmt_int(summary["reception_sensitive_units"]),
                    "Units requiring viewpoint-separated reception review.",
                ),
            ]
        )
    }
      <div class="warning">
        This matrix is a routing and pressure model, not an expert
        interpretation. Whole-Tanakh counts are form-level evidence only.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["domain_counts"], "domain"),
            label_key="domain",
            value_key="count",
            aria_label="Context domain coverage",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            bucket_pressure(rows),
            label_key="intensity",
            value_key="count",
            aria_label="Context pressure intensity counts",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["outside_context_division_counts"], "division"),
            label_key="division",
            value_key="count",
            aria_label="Outside-Psalms context division counts",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{svg_pressure_units(rows)}</div>
    </section>

    <section>
      <h2>Domain Definitions</h2>
      {
        table(
            ["Domain", "Label", "Units", "Evidence hits"],
            domain_rows,
        )
    }
    </section>

    <section>
      <h2>Reception Routing</h2>
      {
        table(
            ["Unit", "Reference", "Reception class", "Required frames"],
            reception_rows,
        )
    }
    </section>

    <section>
      <h2>Highest Context Pressure Units</h2>
      {
        table(
            [
                "Unit",
                "Reference",
                "Stratum",
                "Intensity",
                "Score",
                "Domains",
                "Reception profile",
                "Review roles",
            ],
            unit_table,
        )
    }
    </section>

    <section>
      <h2>Method Limits</h2>
      <p>{esc(report["normalization"]["warning"])}</p>
      <p>
        The matrix uses Strong IDs, benchmark tags, Psalm-class membership,
        witness counts, Greek coverage, compiler features, and normalized UXLC
        surface forms. It deliberately does not ingest proprietary commentary
        or assert final Jewish or Christian readings.
      </p>
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate benchmark context and reception matrix reports."
    )
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--rubric", type=Path, default=RUBRIC_PATH)
    parser.add_argument("--uxlc-zip", type=Path, default=UXLC_ZIP_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        plan_path=args.plan,
        rubric_path=args.rubric,
        uxlc_zip_path=args.uxlc_zip,
    )
    write_json(args.json_output, report)
    write_csv(args.csv_output, report["unit_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
