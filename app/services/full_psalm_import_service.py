from __future__ import annotations

import hashlib
import io
import re
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from app.core.config import get_settings
from app.services import registry_service


HEBREW_MARKS_RE = re.compile(r"[\u0591-\u05C7]")
OSIS_NS = {"osis": "http://www.bibletechnologies.net/2003/OSIS/namespace"}
MACULA_REF_RE = re.compile(r"^PSA\s+(?P<psalm>\d+):(?P<verse>\d+)!(?P<word>\d+)$")
STRONG_DIGITS_RE = re.compile(r"(\d+)")
PARENTHETICAL_GLOSS_RE = re.compile(r"^\(.*\)$")
WITNESS_LINE_RE = re.compile(r"^(?P<book>[1-3A-Z]{3})\s+(?P<chapter>\d+):(?P<verse>\d+)\s+(?P<text>.+)$")
OSHB_FIELDS = ("lemma", "strong", "morph_code", "morph_readable", "part_of_speech", "stem")
MACULA_FIELDS = ("syntax_role", "semantic_role", "referent", "word_sense")
POS_MAP = {
    "A": "adjective",
    "C": "conjunction",
    "D": "adverb",
    "I": "interjection",
    "N": "noun",
    "P": "pronoun",
    "R": "preposition",
    "S": "suffix",
    "T": "particle",
    "V": "verb",
}
STEM_MAP = {
    "q": "qal",
    "N": "niphal",
    "p": "piel",
    "P": "pual",
    "h": "hiphil",
    "H": "hophal",
    "t": "hithpael",
}
SOURCE_IMPORTED_AT = "2026-04-17T00:00:00Z"
MAX_SAME_PSALM_OCCURRENCES = 12
MAX_CROSS_PSALM_OCCURRENCES = 24
POSSESSIVE_WORDS = {"my", "mine", "your", "yours", "his", "her", "hers", "its", "our", "ours", "their", "theirs"}
TEMPORAL_WORDS = {"day", "night", "morning", "evening"}
WITNESS_SOURCES = {
    "kjv": {
        "source_id": "kjv",
        "name": "King James (Authorized) Version",
        "version": "eng-kjv2006",
        "license": "Public Domain",
        "upstream_url": "https://ebible.org/find/details.php?id=eng-kjv2006",
        "archive_name": "eng-kjv2006_vpl.zip",
        "entry_name": "eng-kjv2006_vpl.txt",
        "versionTitle": "King James Version",
        "source_url_template": "https://ebible.org/eng-kjv2006/PSA{psalm:03d}.htm",
        "notes": "Public-domain English witness imported from eBible.org VPL chapter files",
    },
    "asv": {
        "source_id": "asv",
        "name": "American Standard Version (1901)",
        "version": "eng-asv",
        "license": "Public Domain",
        "upstream_url": "https://ebible.org/find/details.php?id=eng-asv",
        "archive_name": "eng-asv_vpl.zip",
        "entry_name": "eng-asv_vpl.txt",
        "versionTitle": "American Standard Version",
        "source_url_template": "https://ebible.org/eng-asv/PSA{psalm:03d}.htm",
        "notes": "Public-domain English witness imported from eBible.org VPL chapter files",
    },
    "web": {
        "source_id": "web",
        "name": "World English Bible",
        "version": "engwebp",
        "license": "Public Domain",
        "upstream_url": "https://ebible.org/bible/details.php?all=1&id=engwebp",
        "archive_name": "engwebp_vpl.zip",
        "entry_name": "engwebp_vpl.txt",
        "versionTitle": "World English Bible",
        "source_url_template": "https://ebible.org/engwebp/PSA{psalm:03d}.htm",
        "notes": "Public-domain English witness imported from eBible.org VPL chapter files",
    },
}


def _normalized_hebrew(text: str) -> str:
    return HEBREW_MARKS_RE.sub("", text)


def _psalm_id(number: int) -> str:
    return f"ps{number:03d}"


def _unit_id(psalm_number: int, verse_number: int) -> str:
    return f"{_psalm_id(psalm_number)}.v{verse_number:03d}.a"


def _token_id(unit_id: str, index: int) -> str:
    head = ".".join(unit_id.split(".")[:2])
    return f"{head}.t{index:03d}"


def _ref(psalm_number: int, verse_number: int) -> str:
    return f"Psalm {psalm_number}:{verse_number}"


def _collapse_whitespace(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def _clean_hebrew_word(value: str | None) -> str:
    return "".join((value or "").split())


def _clean_oshb_surface(value: str | None) -> str:
    return _collapse_whitespace((value or "").replace("/", ""))


def _clean_transliteration(parts: list[str]) -> str | None:
    value = "".join(part for part in parts if part)
    value = _collapse_whitespace(value)
    return value or None


def _clean_gloss_part(value: str | None) -> str | None:
    normalized = _collapse_whitespace(value)
    return normalized or None


def _clean_display_fragment(value: str | None) -> str | None:
    normalized = _collapse_whitespace(value)
    if not normalized:
        return None
    if PARENTHETICAL_GLOSS_RE.match(normalized):
        return None
    normalized = normalized.replace("[is].", "").replace("[was].", "")
    normalized = normalized.replace("[", "").replace("]", "")
    normalized = normalized.replace(".", " ")
    normalized = _collapse_whitespace(normalized)
    return normalized or None


def _clean_witness_text(value: str) -> str:
    cleaned = value.replace("¶", " ")
    cleaned = re.sub(r"[\*\u2020\u2021]+", "", cleaned)
    return _collapse_whitespace(cleaned)


def _component_display_fragment(component: dict[str, Any]) -> str | None:
    gloss = _clean_display_fragment(component.get("gloss"))
    if gloss:
        return gloss
    return _clean_display_fragment(component.get("english"))


def _derive_display_gloss(components: list[dict[str, Any]]) -> str | None:
    conjunctions: list[str] = []
    prepositions: list[str] = []
    bases: list[str] = []
    suffixes: list[str] = []
    postfixes: list[str] = []
    for component in components:
        fragment = _component_display_fragment(component)
        if not fragment:
            continue
        pos = (component.get("pos") or "").casefold()
        if pos == "conjunction":
            conjunctions.append(fragment)
        elif pos == "preposition":
            prepositions.append(fragment)
        elif pos == "suffix":
            suffixes.append(fragment)
        elif pos == "particle":
            postfixes.append(fragment)
        else:
            bases.append(fragment)
    if suffixes and bases:
        anchor_index = len(bases) - 1 if prepositions else 0
        bases[anchor_index] = f"{suffixes[0]} {bases[anchor_index]}"
    ordered = [*conjunctions[:1], *prepositions[:1], *bases, *postfixes]
    if not ordered:
        ordered = [_clean_display_fragment(component.get("english")) for component in components]
    display = _collapse_whitespace(" ".join(part for part in ordered if part))
    return display or None


def _derive_compiler_features(components: list[dict[str, Any]], word_sense: str | None, display_gloss: str | None) -> dict[str, Any]:
    english_parts = [_clean_display_fragment(component.get("english")) for component in components]
    gloss_parts = [_clean_display_fragment(component.get("gloss")) for component in components]
    conjunction_text = " ".join(part for part in english_parts if part).casefold()
    conjunction_role = None
    if any((component.get("pos") or "").casefold() == "conjunction" for component in components):
        if any(word in conjunction_text for word in ("but", "rather")):
            conjunction_role = "contrastive"
        elif "and" in conjunction_text:
            conjunction_role = "additive"
        elif "or" in conjunction_text:
            conjunction_role = "disjunctive"
        else:
            conjunction_role = "conjunctive"
    preposition_role = next(
        (
            fragment.casefold()
            for component in components
            if (component.get("pos") or "").casefold() == "preposition"
            for fragment in [_clean_display_fragment(component.get("english"))]
            if fragment
        ),
        None,
    )
    suffix_component = next((component for component in components if (component.get("pos") or "").casefold() == "suffix"), None)
    suffix_pronoun = None
    if suffix_component is not None:
        suffix_pronoun = {
            "text": _clean_display_fragment(suffix_component.get("english")) or _clean_display_fragment(suffix_component.get("gloss")),
            "person": suffix_component.get("person"),
            "number": suffix_component.get("number"),
            "gender": suffix_component.get("gender"),
        }
    feature_text = " ".join(part for part in [display_gloss, word_sense, *english_parts, *gloss_parts] if part).casefold()
    return {
        "component_count": len(components),
        "english_parts": [part for part in english_parts if part],
        "gloss_fragments": [part for part in gloss_parts if part],
        "raw_pos": [component.get("pos") for component in components if component.get("pos")],
        "raw_classes": [component.get("class") for component in components if component.get("class")],
        "discourse_marker": "parenthetical_only_gloss" if word_sense and PARENTHETICAL_GLOSS_RE.match(word_sense) else None,
        "conjunction_role": conjunction_role,
        "preposition_role": preposition_role,
        "construct_state": any(component.get("state") == "construct" for component in components),
        "suffix_pronoun": suffix_pronoun,
        "divine_name": any(component.get("lemma") == "יהוה" or component.get("strongnumberx") == "3068" for component in components),
        "temporal_pair_candidate": any(word in feature_text for word in TEMPORAL_WORDS),
    }


def _parse_strong_number(raw: str | None) -> str | None:
    if not raw:
        return None
    chunk = raw.split("/")[-1]
    match = STRONG_DIGITS_RE.search(chunk)
    if not match:
        return None
    return f"H{int(match.group(1))}"


def _parse_oshb_morph(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw[1:] if raw.startswith("H") else raw


def _derive_pos_from_morph(morph_code: str | None) -> str | None:
    if not morph_code:
        return None
    leaf = morph_code.split("/")[-1]
    if not leaf:
        return None
    return POS_MAP.get(leaf[0])


def _derive_stem_from_morph(morph_code: str | None) -> str | None:
    if not morph_code:
        return None
    leaf = morph_code.split("/")[-1]
    if not leaf.startswith("V") or len(leaf) < 2:
        return None
    return STEM_MAP.get(leaf[1])


def _hash_paths(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load_uxlc_verses() -> dict[tuple[int, int], str]:
    path = get_settings().raw_dir / "uxlc" / "Tanach.xml.zip"
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("Books/Psalms.xml"))
    verses: dict[tuple[int, int], str] = {}
    for chapter in root.findall("tanach/book/c"):
        psalm_number = int(chapter.attrib["n"])
        for verse in chapter.findall("v"):
            verse_number = int(verse.attrib["n"])
            surfaces = [_clean_hebrew_word(word.text) for word in verse.findall("w")]
            text = " ".join(part for part in surfaces if part).replace("־ ", "־").strip()
            verses[(psalm_number, verse_number)] = text
    return verses


def _load_oshb_tokens() -> dict[tuple[int, int], list[dict[str, Any]]]:
    path = get_settings().raw_dir / "oshb" / "Ps.xml"
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    tokens_by_verse: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for chapter in root.findall(".//osis:chapter", OSIS_NS):
        psalm_number = int(chapter.attrib["osisID"].split(".")[1])
        for verse in chapter.findall("osis:verse", OSIS_NS):
            verse_number = int(verse.attrib["osisID"].split(".")[2])
            tokens: list[dict[str, Any]] = []
            word_index = 0
            for child in verse:
                if child.tag != f"{{{OSIS_NS['osis']}}}w":
                    continue
                word_index += 1
                morph_code = _parse_oshb_morph(child.attrib.get("morph"))
                tokens.append(
                    {
                        "word_number": word_index,
                        "surface": _clean_oshb_surface("".join(child.itertext())),
                        "lemma": child.attrib.get("lemma"),
                        "strong": _parse_strong_number(child.attrib.get("lemma")),
                        "morph_code": morph_code,
                        "morph_readable": morph_code,
                        "part_of_speech": _derive_pos_from_morph(morph_code),
                        "stem": _derive_stem_from_morph(morph_code),
                    }
                )
            tokens_by_verse[(psalm_number, verse_number)] = tokens
    return tokens_by_verse


def _load_macula_groups() -> dict[tuple[int, int, int], dict[str, Any]]:
    grouped: dict[tuple[int, int, int], dict[str, Any]] = {}
    for path in sorted((get_settings().raw_dir / "macula" / "lowfat").glob("19-Psa-*-lowfat.xml")):
        root = ET.fromstring(path.read_text(encoding="utf-8"))
        for word in root.iter("w"):
            raw_ref = word.attrib.get("ref")
            if not raw_ref:
                continue
            match = MACULA_REF_RE.match(raw_ref)
            if not match:
                continue
            key = (int(match.group("psalm")), int(match.group("verse")), int(match.group("word")))
            bucket = grouped.setdefault(
                key,
                {
                    "transliterations": [],
                    "lemmas": [],
                    "roles": [],
                    "glosses": [],
                    "components": [],
                    "pos": [],
                    "stems": [],
                },
            )
            transliteration = _collapse_whitespace(word.attrib.get("transliteration"))
            if transliteration:
                bucket["transliterations"].append(transliteration)
            lemma = _collapse_whitespace(word.attrib.get("lemma"))
            if lemma:
                bucket["lemmas"].append(lemma)
            role = _collapse_whitespace(word.attrib.get("role"))
            if role:
                bucket["roles"].append(role)
            gloss = _collapse_whitespace(word.attrib.get("gloss"))
            if gloss:
                bucket["glosses"].append(gloss)
            pos = _collapse_whitespace(word.attrib.get("pos"))
            if pos:
                bucket["pos"].append(pos)
            stem = _collapse_whitespace(word.attrib.get("stem"))
            if stem:
                bucket["stems"].append(stem)
            bucket["components"].append(
                {
                    "english": _collapse_whitespace(word.attrib.get("english")),
                    "gloss": gloss,
                    "pos": pos,
                    "class": _collapse_whitespace(word.attrib.get("class")),
                    "state": _collapse_whitespace(word.attrib.get("state")),
                    "person": _collapse_whitespace(word.attrib.get("person")),
                    "number": _collapse_whitespace(word.attrib.get("number")),
                    "gender": _collapse_whitespace(word.attrib.get("gender")),
                    "lemma": lemma,
                    "strongnumberx": _collapse_whitespace(word.attrib.get("strongnumberx")),
                }
            )
    normalized: dict[tuple[int, int, int], dict[str, Any]] = {}
    for key, payload in grouped.items():
        gloss_parts = [part for part in (_clean_gloss_part(item) for item in payload["glosses"]) if part]
        word_sense = payload["glosses"][-1] if payload["glosses"] else None
        display_gloss = _derive_display_gloss(payload["components"])
        normalized[key] = {
            "transliteration": _clean_transliteration(payload["transliterations"]),
            "lemma": payload["lemmas"][-1] if payload["lemmas"] else None,
            "syntax_role": payload["roles"][0] if payload["roles"] else None,
            "semantic_role": None,
            "referent": None,
            "word_sense": word_sense,
            "gloss_parts": gloss_parts,
            "display_gloss": display_gloss,
            "compiler_features": _derive_compiler_features(payload["components"], word_sense, display_gloss),
            "part_of_speech": payload["pos"][-1] if payload["pos"] else None,
            "stem": payload["stems"][-1] if payload["stems"] else None,
        }
    return normalized


def _load_witness_verses(source_id: str) -> dict[tuple[int, int], str]:
    config = WITNESS_SOURCES[source_id]
    archive_path = get_settings().raw_dir / source_id / config["archive_name"]
    verses: dict[tuple[int, int], str] = {}
    with zipfile.ZipFile(archive_path) as archive:
        with archive.open(config["entry_name"]) as handle:
            stream = io.TextIOWrapper(handle, encoding="utf-8")
            for raw_line in stream:
                line = _collapse_whitespace(raw_line)
                if not line:
                    continue
                match = WITNESS_LINE_RE.match(line)
                if not match or match.group("book") != "PSA":
                    continue
                psalm_number = int(match.group("chapter"))
                verse_number = int(match.group("verse"))
                verses[(psalm_number, verse_number)] = _clean_witness_text(match.group("text"))
    return verses


def _build_enrichment_sources(token: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    oshb_available = [field for field in OSHB_FIELDS if token.get(field) is not None]
    macula_available = [field for field in MACULA_FIELDS if token.get(field) is not None]
    enrichment_sources = {
        "oshb": {
            "status": "complete" if len(oshb_available) == len(OSHB_FIELDS) else ("partial" if oshb_available else "missing"),
            "available_fields": oshb_available,
            "missing_fields": [field for field in OSHB_FIELDS if field not in oshb_available],
        },
        "macula": {
            "status": "complete" if len(macula_available) == len(MACULA_FIELDS) else ("partial" if macula_available else "missing"),
            "available_fields": macula_available,
            "missing_fields": [field for field in MACULA_FIELDS if field not in macula_available],
        },
    }
    missing = [
        f"{source_id}:{field}"
        for source_id, payload in enrichment_sources.items()
        for field in payload["missing_fields"]
    ]
    return enrichment_sources, missing


def _build_unit(
    psalm_number: int,
    verse_number: int,
    source_hebrew: str,
    oshb_tokens: list[dict[str, Any]],
    macula_groups: dict[tuple[int, int, int], dict[str, Any]],
    witness_verses: dict[str, dict[tuple[int, int], str]],
) -> dict[str, Any]:
    unit_id = _unit_id(psalm_number, verse_number)
    ref = _ref(psalm_number, verse_number)
    tokens: list[dict[str, Any]] = []
    if not oshb_tokens:
        oshb_tokens = [
            {
                "word_number": index,
                "surface": surface,
                "lemma": None,
                "strong": None,
                "morph_code": None,
                "morph_readable": None,
                "part_of_speech": None,
                "stem": None,
            }
            for index, surface in enumerate(source_hebrew.split(), start=1)
        ]
    for oshb_token in oshb_tokens:
        word_number = oshb_token["word_number"]
        macula = macula_groups.get((psalm_number, verse_number, word_number), {})
        token = {
            "token_id": _token_id(unit_id, word_number),
            "ref": f"{ref}#{word_number}",
            "surface": oshb_token["surface"],
            "normalized": _normalized_hebrew(oshb_token["surface"]),
            "transliteration": macula.get("transliteration"),
            "lemma": macula.get("lemma"),
            "strong": oshb_token.get("strong"),
            "morph_code": oshb_token.get("morph_code"),
            "morph_readable": oshb_token.get("morph_readable"),
            "part_of_speech": oshb_token.get("part_of_speech") or macula.get("part_of_speech"),
            "stem": oshb_token.get("stem") or macula.get("stem"),
            "syntax_role": macula.get("syntax_role"),
            "semantic_role": macula.get("semantic_role"),
            "referent": macula.get("referent"),
            "word_sense": macula.get("word_sense"),
            "gloss_parts": macula.get("gloss_parts", []),
            "display_gloss": macula.get("display_gloss"),
            "compiler_features": macula.get("compiler_features", {}),
            "occurrence_index": 1,
            "same_psalm_occurrence_refs": [],
            "corpus_occurrence_refs": [],
            "psalms_occurrence_refs": [],
        }
        enrichment_sources, missing_enrichments = _build_enrichment_sources(token)
        token["enrichment_sources"] = enrichment_sources
        token["missing_enrichments"] = missing_enrichments
        tokens.append(token)
    transliteration = " ".join(token["transliteration"] for token in tokens if token.get("transliteration")).strip()
    witnesses = []
    for source_id, config in WITNESS_SOURCES.items():
        text = witness_verses.get(source_id, {}).get((psalm_number, verse_number))
        if not text:
            continue
        witnesses.append(
            {
                "source_id": source_id,
                "versionTitle": config["versionTitle"],
                "language": "en",
                "ref": ref,
                "source_url": config["source_url_template"].format(psalm=psalm_number),
                "text": text,
            }
        )
    return {
        "psalm_id": _psalm_id(psalm_number),
        "unit_id": unit_id,
        "ref": ref,
        "segmentation_type": "verse",
        "source_hebrew": source_hebrew,
        "source_transliteration": transliteration,
        "token_ids": [token["token_id"] for token in tokens],
        "concept_ids": [f"cpt.{unit_id}.0001"],
        "status": "draft",
        "current_layer_state": {"locked_layers": [], "latest_layer": "source"},
        "canonical_rendering_ids": [],
        "alternate_rendering_ids": [],
        "audit_ids": [],
        "issue_links": [],
        "pr_links": [],
        "tokens": tokens,
        "alignments": [],
        "renderings": [],
        "audit_records": [],
        "review_decisions": [],
        "witnesses": witnesses,
    }


def _apply_occurrence_refs(units: list[dict[str, Any]]) -> None:
    occurrences: dict[str, list[dict[str, str]]] = defaultdict(list)
    for unit in units:
        for token in unit["tokens"]:
            key = token.get("lemma") or token.get("normalized") or token.get("surface")
            if not key:
                continue
            occurrences[key].append({"psalm_id": unit["psalm_id"], "ref": unit["ref"], "token_id": token["token_id"]})
    unique_refs_by_key: dict[str, dict[str, Any]] = {}
    for key, items in occurrences.items():
        by_psalm: dict[str, list[str]] = defaultdict(list)
        cross_psalm: list[str] = []
        for item in items:
            ref = item["ref"]
            psalm_refs = by_psalm[item["psalm_id"]]
            if ref not in psalm_refs:
                psalm_refs.append(ref)
            if ref not in cross_psalm:
                cross_psalm.append(ref)
        unique_refs_by_key[key] = {"by_psalm": by_psalm, "all_refs": cross_psalm}
    counters: dict[str, int] = defaultdict(int)
    for unit in units:
        for token in unit["tokens"]:
            key = token.get("lemma") or token.get("normalized") or token.get("surface")
            counters[key] += 1
            token["occurrence_index"] = counters[key]
            ref_groups = unique_refs_by_key[key]
            same_psalm = [ref for ref in ref_groups["by_psalm"].get(unit["psalm_id"], []) if ref != unit["ref"]]
            cross_psalm = [
                ref
                for ref in ref_groups["all_refs"]
                if ref != unit["ref"] and ref not in ref_groups["by_psalm"].get(unit["psalm_id"], [])
            ]
            token["same_psalm_occurrence_refs"] = same_psalm[:MAX_SAME_PSALM_OCCURRENCES]
            token["psalms_occurrence_refs"] = cross_psalm[:MAX_CROSS_PSALM_OCCURRENCES]
            token["corpus_occurrence_refs"] = cross_psalm[:MAX_CROSS_PSALM_OCCURRENCES]


def _psalm_meta(psalm_number: int, units: list[dict[str, Any]]) -> dict[str, Any]:
    psalm_id = _psalm_id(psalm_number)
    return {
        "psalm_id": psalm_id,
        "title": f"Psalm {psalm_number}",
        "unit_ids": [unit["unit_id"] for unit in units],
    }


def _sync_source_manifests() -> None:
    settings = get_settings()
    project = registry_service.project_template()
    macula_files = sorted((settings.raw_dir / "macula" / "lowfat").glob("19-Psa-*-lowfat.xml"))
    manifests = [
        {
            "source_id": "uxlc",
            "name": "UXLC/WLC Derived Hebrew",
            "version": "vendored-2026.04",
            "license": "Public Domain",
            "upstream_url": "https://www.tanach.us/Books/Tanach.xml.zip",
            "imported_at": SOURCE_IMPORTED_AT,
            "import_hash": _hash_paths([settings.raw_dir / "uxlc" / "Tanach.xml.zip"]),
            "allowed_for_generation": True,
            "allowed_for_display": True,
            "allowed_for_export": True,
            "notes": "Canonical Hebrew source vendored from Tanach.us",
        },
        {
            "source_id": "oshb",
            "name": "Open Scriptures Hebrew Bible",
            "version": "vendored-2018.12.15",
            "license": "Open Scriptural Data",
            "upstream_url": "https://github.com/openscriptures/morphhb/blob/master/wlc/Ps.xml",
            "imported_at": SOURCE_IMPORTED_AT,
            "import_hash": _hash_paths([settings.raw_dir / "oshb" / "Ps.xml"]),
            "allowed_for_generation": False,
            "allowed_for_display": True,
            "allowed_for_export": True,
            "notes": "Morphology and token-level lexical enrichment for Psalms",
        },
        {
            "source_id": "macula",
            "name": "MACULA Hebrew",
            "version": "vendored-2026.04",
            "license": "CC BY 4.0",
            "upstream_url": "https://github.com/Clear-Bible/macula-hebrew/tree/main/WLC/lowfat",
            "imported_at": SOURCE_IMPORTED_AT,
            "import_hash": _hash_paths(macula_files),
            "allowed_for_generation": False,
            "allowed_for_display": True,
            "allowed_for_export": True,
            "notes": "Syntax-role and lexical gloss enrichment for Psalms",
        },
    ]
    for source_id, config in WITNESS_SOURCES.items():
        manifests.append(
            {
                "source_id": source_id,
                "name": config["name"],
                "version": config["version"],
                "license": config["license"],
                "upstream_url": config["upstream_url"],
                "imported_at": SOURCE_IMPORTED_AT,
                "import_hash": _hash_paths([settings.raw_dir / source_id / config["archive_name"]]),
                "allowed_for_generation": False,
                "allowed_for_display": True,
                "allowed_for_export": True,
                "notes": config["notes"],
            }
        )
    project["allowed_sources"] = [item["source_id"] for item in manifests]
    project["source_manifests"] = manifests
    registry_service.save_project(project)


def import_vendored_psalms() -> list[dict[str, Any]]:
    settings = get_settings()
    registry_service.bootstrap_project()
    _sync_source_manifests()
    shutil.rmtree(settings.psalms_dir, ignore_errors=True)
    settings.psalms_dir.mkdir(parents=True, exist_ok=True)

    uxlc_verses = _load_uxlc_verses()
    oshb_tokens = _load_oshb_tokens()
    macula_groups = _load_macula_groups()
    witness_verses = {source_id: _load_witness_verses(source_id) for source_id in WITNESS_SOURCES}

    units: list[dict[str, Any]] = []
    by_psalm: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for psalm_number in range(1, 151):
        verse_numbers = sorted(verse for candidate_psalm, verse in uxlc_verses if candidate_psalm == psalm_number)
        for verse_number in verse_numbers:
            unit = _build_unit(
                psalm_number=psalm_number,
                verse_number=verse_number,
                source_hebrew=uxlc_verses[(psalm_number, verse_number)],
                oshb_tokens=oshb_tokens.get((psalm_number, verse_number), []),
                macula_groups=macula_groups,
                witness_verses=witness_verses,
            )
            units.append(unit)
            by_psalm[psalm_number].append(unit)

    _apply_occurrence_refs(units)

    for unit in units:
        registry_service.save_unit(unit)
    for psalm_number, psalm_units in by_psalm.items():
        psalm_id = _psalm_id(psalm_number)
        registry_service.write_json(registry_service.psalm_dir(psalm_id) / f"{psalm_id}.meta.json", _psalm_meta(psalm_number, psalm_units))
    return units
