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
CONTENT_ROOT = ROOT / "content" / "psalms"
RAW_ROOT = ROOT / "data" / "raw"
UXLC_ZIP_PATH = RAW_ROOT / "uxlc" / "Tanach.xml.zip"
OSHB_PSALMS_PATH = RAW_ROOT / "oshb" / "Ps.xml"
MACULA_LOWFAT_ROOT = RAW_ROOT / "macula" / "lowfat"
EXPANDED_SUITE_PATH = ROOT / "reports" / "research" / "contextual_expanded_benchmark_suite.json"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "whole_tanakh_morphology_gap.json"
DEFAULT_SOURCE_CSV_OUTPUT = (
    ROOT / "reports" / "research" / "whole_tanakh_morphology_gap_sources.csv"
)
DEFAULT_LEXEME_CSV_OUTPUT = (
    ROOT / "reports" / "research" / "whole_tanakh_morphology_gap_lexemes.csv"
)
DEFAULT_UNIT_CSV_OUTPUT = ROOT / "reports" / "research" / "whole_tanakh_morphology_gap_units.csv"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "whole_tanakh_morphology_gap.html"

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

HIGH_RISK_TAGS = {
    "anthropology",
    "divine_name_policy",
    "hesed",
    "imprecation",
    "jewish_christian_reception",
    "lexical_dispute",
    "messianic_interpretation",
    "reception_history",
    "textual_witness",
    "violence",
}

PUNCTUATION = {
    "\u05be",
    "\u05c0",
    "\u05c3",
    "\u05c6",
    " ",
    "\t",
    "\n",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


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


def canonical_book_file(name: str) -> bool:
    if not name.startswith("Books/") or not name.endswith(".xml"):
        return False
    if name.endswith(".DH.xml"):
        return False
    return not (name.endswith("TanachHeader.xml") or name.endswith("TanachIndex.xml"))


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def add_sample(samples: list[str], value: str, limit: int = 10) -> None:
    if value and value not in samples and len(samples) < limit:
        samples.append(value)


def manifest_row(source_id: str, manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        return {
            "source_id": source_id,
            "name": source_id,
            "version": "",
            "license": "",
            "allowed_for_generation": False,
            "scope": "missing",
        }
    manifest = load_json(manifest_path)
    return {
        "source_id": source_id,
        "name": manifest.get("name", source_id),
        "version": manifest.get("version", ""),
        "license": manifest.get("license", ""),
        "allowed_for_generation": bool(manifest.get("allowed_for_generation")),
        "scope": manifest.get("notes", ""),
    }


def uxlc_version(root: ET.Element) -> dict[str, str]:
    edition = root.find(".//edition")
    if edition is None:
        return {"version": "", "date": "", "build": "", "build_datetime": ""}
    return {
        "version": edition.findtext("version") or "",
        "date": edition.findtext("date") or "",
        "build": edition.findtext("build") or "",
        "build_datetime": edition.findtext("buildDateTime") or "",
    }


def build_uxlc_form_index(zip_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    form_index: dict[str, dict[str, Any]] = {}
    book_rows = []
    division_totals: Counter[str] = Counter()
    word_attr_counts: Counter[str] = Counter()
    words_with_morph_attrs = 0
    source_version: dict[str, str] = {}
    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(name for name in archive.namelist() if canonical_book_file(name))
        for name in names:
            root = ET.fromstring(archive.read(name))
            if not source_version:
                source_version = uxlc_version(root)
            book = root.find("./tanach/book")
            names_el = book.find("names") if book is not None else None
            book_name = names_el.findtext("name") if names_el is not None else Path(name).stem
            book_name = str(book_name)
            division = DIVISIONS.get(book_name, "Unmapped")
            word_count = 0
            local_forms: Counter[str] = Counter()
            for chapter in root.findall(".//c"):
                chapter_num = str(chapter.get("n") or "")
                for verse in chapter.findall("./v"):
                    verse_num = str(verse.get("n") or "")
                    ref = f"{book_name} {chapter_num}:{verse_num}"
                    for word in verse.findall("./w"):
                        for attr in word.attrib:
                            word_attr_counts[attr] += 1
                        if {"lemma", "strong", "morph"} & set(word.attrib):
                            words_with_morph_attrs += 1
                        normalized = normalize_hebrew_form("".join(word.itertext()))
                        if not normalized:
                            continue
                        word_count += 1
                        local_forms[normalized] += 1
                        entry = form_index.setdefault(
                            normalized,
                            {
                                "tanakh_count": 0,
                                "psalms_count": 0,
                                "outside_psalms_count": 0,
                                "division_counts": Counter(),
                                "outside_division_counts": Counter(),
                                "outside_sample_refs": [],
                            },
                        )
                        entry["tanakh_count"] += 1
                        entry["division_counts"][division] += 1
                        if book_name == "Psalms":
                            entry["psalms_count"] += 1
                        else:
                            entry["outside_psalms_count"] += 1
                            entry["outside_division_counts"][division] += 1
                            add_sample(entry["outside_sample_refs"], ref)
            division_totals[division] += word_count
            book_rows.append(
                {
                    "book": book_name,
                    "division": division,
                    "word_elements": word_count,
                    "distinct_normalized_forms": len(local_forms),
                }
            )
    for entry in form_index.values():
        entry["division_counts"] = dict(sorted(entry["division_counts"].items()))
        entry["outside_division_counts"] = dict(sorted(entry["outside_division_counts"].items()))
    summary = {
        "book_count": len(book_rows),
        "non_psalm_book_count": sum(1 for row in book_rows if row["book"] != "Psalms"),
        "word_elements": sum(int(row["word_elements"]) for row in book_rows),
        "distinct_normalized_forms": len(form_index),
        "word_attribute_counts": dict(word_attr_counts.most_common()),
        "word_elements_with_lemma_strong_or_morph_attrs": words_with_morph_attrs,
        "source_version": source_version,
        "division_totals": [
            {"division": division, "word_elements": count}
            for division, count in sorted(division_totals.items())
        ],
        "book_rows": sorted(
            book_rows,
            key=lambda row: int(row["word_elements"]),
            reverse=True,
        ),
    }
    return form_index, summary


def count_oshb_words(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"book_count": 0, "word_count": 0, "word_count_with_lemma": 0}
    root = ET.parse(path).getroot()
    word_count = 0
    lemma_count = 0
    morph_count = 0
    attr_counts: Counter[str] = Counter()
    for elem in root.iter():
        if local_name(elem.tag) != "w":
            continue
        word_count += 1
        attr_counts.update(elem.attrib.keys())
        if elem.get("lemma"):
            lemma_count += 1
        if elem.get("morph"):
            morph_count += 1
    return {
        "book_count": 1,
        "word_count": word_count,
        "word_count_with_lemma": lemma_count,
        "word_count_with_morph": morph_count,
        "word_attribute_counts": dict(attr_counts.most_common()),
    }


def count_macula_files(root: Path) -> dict[str, Any]:
    files = sorted(root.glob("*-Psa-*-lowfat.xml"))
    return {
        "book_count": 1 if files else 0,
        "psalm_file_count": len(files),
    }


def load_benchmark_units(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    suite = load_json(path)
    rows: dict[str, dict[str, Any]] = {}
    for task in suite.get("tasks", []):
        unit_id = str(task["unit_id"])
        row = rows.setdefault(
            unit_id,
            {
                "unit_id": unit_id,
                "ref": task.get("ref", ""),
                "layers": set(),
                "benchmark_tags": Counter(),
                "task_count": 0,
            },
        )
        row["layers"].add(str(task.get("layer", "")))
        row["benchmark_tags"].update(str(tag) for tag in task.get("benchmark_tags", []))
        row["task_count"] += 1
    for row in rows.values():
        row["layers"] = sorted(row["layers"])
        row["benchmark_tags"] = dict(row["benchmark_tags"].most_common())
    return rows


def scan_psalm_tokens(
    content_root: Path,
    form_index: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    token_rows = []
    unit_tokens: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(content_root.glob("ps*/*.v*.json")):
        unit = load_json(path)
        unit_id = str(unit["unit_id"])
        for token in unit.get("tokens", []):
            normalized = str(token.get("normalized") or normalize_hebrew_form(token.get("surface")))
            lemma_form = normalize_hebrew_form(token.get("lemma"))
            surface_entry = form_index.get(normalized, {})
            lemma_entry = form_index.get(lemma_form, {}) if lemma_form else {}
            row = {
                "unit_id": unit_id,
                "ref": unit.get("ref", ""),
                "token_id": token.get("token_id", ""),
                "surface": token.get("surface", ""),
                "normalized": normalized,
                "lemma": token.get("lemma", ""),
                "lemma_form": lemma_form,
                "strong": token.get("strong", ""),
                "display_gloss": token.get("display_gloss", ""),
                "part_of_speech": token.get("part_of_speech", ""),
                "morph_code": token.get("morph_code", ""),
                "surface_outside_psalms_count": surface_entry.get(
                    "outside_psalms_count",
                    0,
                ),
                "lemma_form_outside_psalms_count": lemma_entry.get(
                    "outside_psalms_count",
                    0,
                ),
                "outside_division_counts": surface_entry.get(
                    "outside_division_counts",
                    {},
                ),
                "outside_sample_refs": surface_entry.get("outside_sample_refs", []),
            }
            token_rows.append(row)
            unit_tokens[unit_id].append(row)
    return token_rows, dict(unit_tokens)


def build_source_rows(
    uxlc_summary: dict[str, Any],
    oshb_summary: dict[str, Any],
    macula_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    source_rows = {
        "uxlc": manifest_row("uxlc", RAW_ROOT / "uxlc" / "manifest.json"),
        "oshb": manifest_row("oshb", RAW_ROOT / "oshb" / "manifest.json"),
        "macula": manifest_row("macula", RAW_ROOT / "macula" / "manifest.json"),
        "lxx": manifest_row("lxx", RAW_ROOT / "lxx" / "manifest.json"),
        "asv": manifest_row("asv", RAW_ROOT / "asv" / "manifest.json"),
        "kjv": manifest_row("kjv", RAW_ROOT / "kjv" / "manifest.json"),
        "web": manifest_row("web", RAW_ROOT / "web" / "manifest.json"),
    }
    rows.append(
        {
            **source_rows["uxlc"],
            "evidence_role": "whole-Tanakh Hebrew text",
            "book_scope": f"{uxlc_summary['book_count']} Tanakh books",
            "morphology_scope": "none in local XML word attributes",
            "book_count_with_morphology": 0,
            "non_psalm_book_count_with_morphology": 0,
            "word_or_file_count": uxlc_summary["word_elements"],
        }
    )
    rows.append(
        {
            **source_rows["oshb"],
            "evidence_role": "Psalm lemma/Strong/morph enrichment",
            "book_scope": "Psalms only",
            "morphology_scope": "lemma and morph attributes in Ps.xml",
            "book_count_with_morphology": oshb_summary["book_count"],
            "non_psalm_book_count_with_morphology": 0,
            "word_or_file_count": oshb_summary["word_count"],
        }
    )
    rows.append(
        {
            **source_rows["macula"],
            "evidence_role": "Psalm syntax/word-sense enrichment",
            "book_scope": "Psalms only",
            "morphology_scope": "150 Psalm lowfat files",
            "book_count_with_morphology": macula_summary["book_count"],
            "non_psalm_book_count_with_morphology": 0,
            "word_or_file_count": macula_summary["psalm_file_count"],
        }
    )
    for source_id in ["lxx", "asv", "kjv", "web"]:
        rows.append(
            {
                **source_rows[source_id],
                "evidence_role": "witness, not Hebrew morphology",
                "book_scope": "witness source",
                "morphology_scope": "not a Hebrew lemma/Strong source",
                "book_count_with_morphology": 0,
                "non_psalm_book_count_with_morphology": 0,
                "word_or_file_count": 0,
            }
        )
    return rows


def lexeme_rows(
    token_rows: list[dict[str, Any]],
    benchmark_units: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for token in token_rows:
        strong = str(token.get("strong") or "")
        if strong:
            groups[strong].append(token)

    rows = []
    for strong, tokens in groups.items():
        unit_ids = {str(token["unit_id"]) for token in tokens}
        benchmark_unit_ids = sorted(unit_id for unit_id in unit_ids if unit_id in benchmark_units)
        tag_counts: Counter[str] = Counter()
        for unit_id in benchmark_unit_ids:
            tag_counts.update(benchmark_units[unit_id]["benchmark_tags"])
        high_risk_tag_count = sum(
            count for tag, count in tag_counts.items() if tag in HIGH_RISK_TAGS
        )
        lemma_counts = Counter(str(token["lemma"]) for token in tokens if token["lemma"])
        gloss_counts = Counter(
            str(token["display_gloss"]) for token in tokens if token["display_gloss"]
        )
        normalized_forms = {
            str(token["normalized"]): token for token in tokens if token["normalized"]
        }
        outside_surface_occurrences = sum(
            int(token["surface_outside_psalms_count"]) for token in normalized_forms.values()
        )
        outside_divisions: Counter[str] = Counter()
        for token in normalized_forms.values():
            outside_divisions.update(token["outside_division_counts"])
        tokens_with_surface = sum(
            1 for token in tokens if int(token["surface_outside_psalms_count"]) > 0
        )
        tokens_with_lemma_form = sum(
            1 for token in tokens if int(token["lemma_form_outside_psalms_count"]) > 0
        )
        pressure_score = round(
            len(tokens)
            + min(outside_surface_occurrences, 3000) / 20
            + len(benchmark_unit_ids) * 8
            + high_risk_tag_count * 5
            + (20 if outside_surface_occurrences else 0),
            2,
        )
        rows.append(
            {
                "strong": strong,
                "lemma_samples": dict(lemma_counts.most_common(5)),
                "display_gloss_samples": dict(gloss_counts.most_common(5)),
                "psalm_token_count": len(tokens),
                "unit_count": len(unit_ids),
                "benchmark_unit_count": len(benchmark_unit_ids),
                "benchmark_high_risk_tag_count": high_risk_tag_count,
                "tokens_with_surface_context": tokens_with_surface,
                "surface_context_token_pct": pct(tokens_with_surface, len(tokens)),
                "tokens_with_lemma_form_context": tokens_with_lemma_form,
                "lemma_form_context_token_pct": pct(tokens_with_lemma_form, len(tokens)),
                "outside_surface_occurrence_evidence": outside_surface_occurrences,
                "outside_strong_occurrence_evidence": 0,
                "outside_context_division_counts": dict(outside_divisions.most_common()),
                "benchmark_tags": dict(tag_counts.most_common(12)),
                "morphology_boundary": (
                    "outside-Psalms context is surface-form only; no non-Psalm "
                    "Strong/lemma index is local"
                ),
                "review_pressure_score": pressure_score,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            float(row["review_pressure_score"]),
            int(row["psalm_token_count"]),
            str(row["strong"]),
        ),
        reverse=True,
    )


def unit_rows(
    unit_tokens: dict[str, list[dict[str, Any]]],
    benchmark_units: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for unit_id, benchmark in sorted(benchmark_units.items()):
        tokens = unit_tokens.get(unit_id, [])
        total = len(tokens)
        strong_count = sum(1 for token in tokens if token.get("strong"))
        lemma_count = sum(1 for token in tokens if token.get("lemma"))
        surface_count = sum(
            1 for token in tokens if int(token.get("surface_outside_psalms_count") or 0) > 0
        )
        lemma_form_count = sum(
            1 for token in tokens if int(token.get("lemma_form_outside_psalms_count") or 0) > 0
        )
        tags = benchmark["benchmark_tags"]
        high_risk_tags = sorted(tag for tag in tags if tag in HIGH_RISK_TAGS)
        risk_score = round(
            (100 - pct(0, max(1, strong_count)))
            + len(high_risk_tags) * 9
            + pct(surface_count, total) / 4,
            2,
        )
        rows.append(
            {
                "unit_id": unit_id,
                "ref": benchmark["ref"],
                "task_count": benchmark["task_count"],
                "layers": benchmark["layers"],
                "token_count": total,
                "strong_coverage_pct": pct(strong_count, total),
                "lemma_coverage_pct": pct(lemma_count, total),
                "surface_outside_context_pct": pct(surface_count, total),
                "lemma_form_outside_context_pct": pct(lemma_form_count, total),
                "outside_strong_context_pct": 0.0,
                "high_risk_tags": high_risk_tags,
                "review_need": (
                    "surface bridge needs human lemma/sense adjudication"
                    if total
                    else "missing unit tokens"
                ),
                "morphology_gap_risk_score": risk_score,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            float(row["morphology_gap_risk_score"]),
            str(row["unit_id"]),
        ),
        reverse=True,
    )


def summarize(
    *,
    uxlc_summary: dict[str, Any],
    oshb_summary: dict[str, Any],
    macula_summary: dict[str, Any],
    token_rows: list[dict[str, Any]],
    lexemes: list[dict[str, Any]],
    units: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(token_rows)
    strong_count = sum(1 for token in token_rows if token.get("strong"))
    lemma_count = sum(1 for token in token_rows if token.get("lemma"))
    surface_count = sum(1 for token in token_rows if int(token["surface_outside_psalms_count"]) > 0)
    lemma_form_count = sum(
        1 for token in token_rows if int(token["lemma_form_outside_psalms_count"]) > 0
    )
    high_risk_units = sum(1 for row in units if row["high_risk_tags"])
    top = lexemes[0] if lexemes else {}
    return {
        "uxlc_book_count": uxlc_summary["book_count"],
        "uxlc_non_psalm_book_count": uxlc_summary["non_psalm_book_count"],
        "uxlc_word_elements": uxlc_summary["word_elements"],
        "uxlc_distinct_normalized_forms": uxlc_summary["distinct_normalized_forms"],
        "uxlc_word_elements_with_lemma_strong_or_morph_attrs": uxlc_summary[
            "word_elements_with_lemma_strong_or_morph_attrs"
        ],
        "oshb_psalm_book_count": oshb_summary["book_count"],
        "oshb_psalm_word_count": oshb_summary["word_count"],
        "macula_psalm_file_count": macula_summary["psalm_file_count"],
        "local_books_with_hebrew_morphology": 1 if oshb_summary["book_count"] else 0,
        "local_non_psalm_books_with_hebrew_morphology": 0,
        "local_non_psalm_morphology_book_pct": 0.0,
        "psalm_token_count": total,
        "psalm_token_strong_coverage_pct": pct(strong_count, total),
        "psalm_token_lemma_coverage_pct": pct(lemma_count, total),
        "surface_outside_context_token_pct": pct(surface_count, total),
        "lemma_form_outside_context_token_pct": pct(lemma_form_count, total),
        "outside_strong_context_token_pct": 0.0,
        "distinct_psalm_strong_keys": len(
            {str(token["strong"]) for token in token_rows if token.get("strong")}
        ),
        "lexeme_pressure_row_count": len(lexemes),
        "benchmark_unit_count": len(units),
        "benchmark_high_risk_unit_count": high_risk_units,
        "top_pressure_strong": top.get("strong", ""),
        "top_pressure_score": top.get("review_pressure_score", 0.0),
        "whole_tanakh_lemma_strong_index_available": False,
        "source_boundary_status": (
            "Outside-Psalms context is currently UXLC surface-form evidence, "
            "not whole-Tanakh lemma/Strong evidence."
        ),
        "source_version": uxlc_summary["source_version"],
    }


def build_report(
    content_root: Path,
    uxlc_zip_path: Path,
    oshb_psalms_path: Path,
    macula_lowfat_root: Path,
    integrated_suite_path: Path,
) -> dict[str, Any]:
    form_index, uxlc_summary = build_uxlc_form_index(uxlc_zip_path)
    oshb_summary = count_oshb_words(oshb_psalms_path)
    macula_summary = count_macula_files(macula_lowfat_root)
    benchmark_units = load_benchmark_units(integrated_suite_path)
    token_rows, unit_token_rows = scan_psalm_tokens(content_root, form_index)
    lexemes = lexeme_rows(token_rows, benchmark_units)
    units = unit_rows(unit_token_rows, benchmark_units)
    source_rows = build_source_rows(uxlc_summary, oshb_summary, macula_summary)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated whole-Tanakh morphology gap audit",
        "source_paths": {
            "content_root": "content/psalms",
            "uxlc_zip": "data/raw/uxlc/Tanach.xml.zip",
            "oshb_psalms": "data/raw/oshb/Ps.xml",
            "macula_lowfat": "data/raw/macula/lowfat",
            "expanded_suite": "reports/research/contextual_expanded_benchmark_suite.json",
        },
        "normalization": {
            "method": "NFKD; remove combining marks, Hebrew punctuation, and whitespace",
            "boundary": (
                "UXLC outside-Psalms matches are normalized surface forms. "
                "They are not treated as lemma, Strong, morphology, or sense proof."
            ),
        },
        "summary": summarize(
            uxlc_summary=uxlc_summary,
            oshb_summary=oshb_summary,
            macula_summary=macula_summary,
            token_rows=token_rows,
            lexemes=lexemes,
            units=units,
        ),
        "source_rows": source_rows,
        "uxlc_division_totals": uxlc_summary["division_totals"],
        "lexeme_pressure_rows": lexemes[:150],
        "benchmark_unit_rows": units,
    }


def flatten_source_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "source_id",
        "name",
        "version",
        "license",
        "allowed_for_generation",
        "evidence_role",
        "book_scope",
        "morphology_scope",
        "book_count_with_morphology",
        "non_psalm_book_count_with_morphology",
        "word_or_file_count",
    ]
    return [{key: row.get(key, "") for key in keys} for row in rows]


def flatten_lexeme_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for row in rows:
        flattened.append(
            {
                "strong": row["strong"],
                "lemma_samples": "; ".join(row["lemma_samples"].keys()),
                "display_gloss_samples": "; ".join(row["display_gloss_samples"].keys()),
                "psalm_token_count": row["psalm_token_count"],
                "unit_count": row["unit_count"],
                "benchmark_unit_count": row["benchmark_unit_count"],
                "surface_context_token_pct": row["surface_context_token_pct"],
                "lemma_form_context_token_pct": row["lemma_form_context_token_pct"],
                "outside_surface_occurrence_evidence": row["outside_surface_occurrence_evidence"],
                "outside_strong_occurrence_evidence": row["outside_strong_occurrence_evidence"],
                "review_pressure_score": row["review_pressure_score"],
            }
        )
    return flattened


def flatten_unit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for row in rows:
        flattened.append(
            {
                "unit_id": row["unit_id"],
                "ref": row["ref"],
                "task_count": row["task_count"],
                "layers": "; ".join(row["layers"]),
                "token_count": row["token_count"],
                "strong_coverage_pct": row["strong_coverage_pct"],
                "lemma_coverage_pct": row["lemma_coverage_pct"],
                "surface_outside_context_pct": row["surface_outside_context_pct"],
                "lemma_form_outside_context_pct": row["lemma_form_outside_context_pct"],
                "outside_strong_context_pct": row["outside_strong_context_pct"],
                "high_risk_tags": "; ".join(row["high_risk_tags"]),
                "review_need": row["review_need"],
                "morphology_gap_risk_score": row["morphology_gap_risk_score"],
            }
        )
    return flattened


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
        body.append("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>")
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    source_chart_rows = [
        {"label": "UXLC Hebrew text books", "value": summary["uxlc_book_count"]},
        {
            "label": "Local Hebrew morphology books",
            "value": summary["local_books_with_hebrew_morphology"],
        },
        {
            "label": "Non-Psalm morphology books",
            "value": summary["local_non_psalm_books_with_hebrew_morphology"],
        },
    ]
    token_chart_rows = [
        {"label": "Psalm Strong coverage", "value": summary["psalm_token_strong_coverage_pct"]},
        {"label": "Psalm lemma coverage", "value": summary["psalm_token_lemma_coverage_pct"]},
        {
            "label": "Outside surface-form context",
            "value": summary["surface_outside_context_token_pct"],
        },
        {
            "label": "Outside lemma-form context",
            "value": summary["lemma_form_outside_context_token_pct"],
        },
        {
            "label": "Outside Strong context",
            "value": summary["outside_strong_context_token_pct"],
        },
    ]
    pressure_chart_rows = [
        {
            "label": f"{row['strong']} {'/'.join(row['lemma_samples'].keys())}",
            "value": row["review_pressure_score"],
        }
        for row in report["lexeme_pressure_rows"][:20]
    ]
    source_rows = [
        [
            row["source_id"],
            row["evidence_role"],
            row["book_scope"],
            row["morphology_scope"],
            row["allowed_for_generation"],
        ]
        for row in report["source_rows"]
    ]
    lexeme_rows_html = [
        [
            row["strong"],
            "; ".join(row["lemma_samples"].keys()),
            row["psalm_token_count"],
            row["surface_context_token_pct"],
            row["outside_surface_occurrence_evidence"],
            row["outside_strong_occurrence_evidence"],
            row["review_pressure_score"],
        ]
        for row in report["lexeme_pressure_rows"][:30]
    ]
    unit_rows_html = [
        [
            row["unit_id"],
            row["ref"],
            row["surface_outside_context_pct"],
            row["outside_strong_context_pct"],
            ", ".join(row["high_risk_tags"]),
            row["review_need"],
        ]
        for row in report["benchmark_unit_rows"][:30]
    ]
    version = summary["source_version"]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Whole-Tanakh Morphology Gap</title>
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
    <h1>AlephTav Whole-Tanakh Morphology Gap</h1>
    <p class="lede">
      Hard-data boundary audit for whole-Tanakh lexical context. The project
      has full UXLC Hebrew text coverage and Psalm-level lemma/Strong
      enrichment, but no local non-Psalm lemma/Strong morphology index. This
      report quantifies where outside-Psalms context is a useful surface-form
      bridge and where it must not be treated as lexeme authority.
    </p>
    <p class="meta">
      Generated {esc(report["generated_on"])} from UXLC {esc(version.get("version", ""))}
      ({esc(version.get("date", ""))}, build {esc(version.get("build", ""))}).
    </p>
  </header>
  <main>
    <section>
      <h2>Boundary Snapshot</h2>
      {
        metric_cards(
            [
                (
                    "UXLC books",
                    fmt_int(summary["uxlc_book_count"]),
                    f'''{fmt_int(summary["uxlc_word_elements"])} Hebrew word elements.''',
                ),
                (
                    "Non-Psalm morph books",
                    fmt_int(summary["local_non_psalm_books_with_hebrew_morphology"]),
                    "Local lemma/Strong morphology outside Psalms.",
                ),
                (
                    "Psalm Strong coverage",
                    f'''{summary["psalm_token_strong_coverage_pct"]:.2f}%''',
                    f'''{fmt_int(summary["distinct_psalm_strong_keys"])} distinct Strong keys.''',
                ),
                (
                    "Outside Strong context",
                    f'''{summary["outside_strong_context_token_pct"]:.2f}%''',
                    "True non-Psalm Strong evidence available locally.",
                ),
                (
                    "Outside surface bridge",
                    f'''{summary["surface_outside_context_token_pct"]:.2f}%''',
                    "Psalm tokens with non-Psalm UXLC surface-form evidence.",
                ),
                (
                    "Integrated units",
                    fmt_int(summary["benchmark_unit_count"]),
                    f'''{fmt_int(summary["benchmark_high_risk_unit_count"])} high-risk units.''',
                ),
                (
                    "Top pressure key",
                    summary["top_pressure_strong"],
                    f'''Score {summary["top_pressure_score"]}.''',
                ),
                (
                    "UXLC morph attrs",
                    fmt_int(summary["uxlc_word_elements_with_lemma_strong_or_morph_attrs"]),
                    "Word elements carrying lemma/Strong/morph attributes.",
                ),
            ]
        )
    }
      <div class="warning">
        This is not a source failure; it is a source-boundary warning. A local
        translation model can use the whole-Tanakh surface network as contextual
        evidence, but human review must block claims that require non-Psalm
        lemma, Strong, morphology, or sense identity.
      </div>
    </section>

    <section>
      <h2>Source Coverage</h2>
      <div class="chart">{
        svg_horizontal_bars(
            source_chart_rows,
            label_key="label",
            value_key="value",
            aria_label="Local source book coverage",
            color="#2f6f73",
            limit=10,
        )
    }</div>
      {
        table(
            ["Source", "Role", "Book scope", "Morphology scope", "Generation allowed"],
            source_rows,
        )
    }
    </section>

    <section>
      <h2>Token Evidence</h2>
      <div class="chart">{
        svg_horizontal_bars(
            token_chart_rows,
            label_key="label",
            value_key="value",
            aria_label="Psalm token evidence coverage",
            color="#7c5b2f",
            limit=10,
        )
    }</div>
    </section>

    <section>
      <h2>Lexeme Pressure</h2>
      <div class="chart">{
        svg_horizontal_bars(
            pressure_chart_rows,
            label_key="label",
            value_key="value",
            aria_label="Top morphology-boundary lexeme pressure scores",
            color="#58508d",
        )
    }</div>
      {
        table(
            [
                "Strong",
                "Lemma samples",
                "Psalm tokens",
                "Surface context %",
                "Outside surface occurrences",
                "Outside Strong occurrences",
                "Pressure",
            ],
            lexeme_rows_html,
        )
    }
    </section>

    <section>
      <h2>Benchmark Unit Exposure</h2>
      {
        table(
            [
                "Unit",
                "Reference",
                "Surface context %",
                "Outside Strong %",
                "High-risk tags",
                "Review need",
            ],
            unit_rows_html,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate whole-Tanakh morphology source-boundary report."
    )
    parser.add_argument("--content-root", type=Path, default=CONTENT_ROOT)
    parser.add_argument("--uxlc-zip", type=Path, default=UXLC_ZIP_PATH)
    parser.add_argument("--oshb-psalms", type=Path, default=OSHB_PSALMS_PATH)
    parser.add_argument("--macula-lowfat", type=Path, default=MACULA_LOWFAT_ROOT)
    parser.add_argument("--expanded-suite", type=Path, default=EXPANDED_SUITE_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--source-csv-output", type=Path, default=DEFAULT_SOURCE_CSV_OUTPUT)
    parser.add_argument("--lexeme-csv-output", type=Path, default=DEFAULT_LEXEME_CSV_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        args.content_root,
        args.uxlc_zip,
        args.oshb_psalms,
        args.macula_lowfat,
        args.expanded_suite,
    )
    write_json(args.json_output, report)
    write_csv(args.source_csv_output, flatten_source_rows(report["source_rows"]))
    write_csv(args.lexeme_csv_output, flatten_lexeme_rows(report["lexeme_pressure_rows"]))
    write_csv(args.unit_csv_output, flatten_unit_rows(report["benchmark_unit_rows"]))
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.source_csv_output}")
    print(f"Wrote {args.lexeme_csv_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
