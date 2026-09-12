from __future__ import annotations

import argparse
import csv
import html
import json
import math
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = ROOT / "content" / "psalms"
UXLC_ZIP_PATH = ROOT / "data" / "raw" / "uxlc" / "Tanach.xml.zip"
EXPANDED_SUITE_PATH = ROOT / "reports" / "research" / "contextual_expanded_benchmark_suite.json"
ATLAS_PATH = ROOT / "reports" / "research" / "contextual_pressure_atlas.json"

DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "canonical_context_network.json"
DEFAULT_UNIT_CSV_OUTPUT = ROOT / "reports" / "research" / "canonical_context_unit_network.csv"
DEFAULT_DOMAIN_CSV_OUTPUT = ROOT / "reports" / "research" / "canonical_context_domain_network.csv"
DEFAULT_BOOK_CSV_OUTPUT = ROOT / "reports" / "research" / "canonical_context_book_network.csv"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "canonical_context_network.html"

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

PUNCTUATION = {
    "\u05be",
    "\u05c0",
    "\u05c3",
    "\u05c6",
    " ",
    "\t",
    "\n",
}

CONTENT_POS = {"noun", "verb", "adjective", "adverb"}
PROPHET_DIVISIONS = {"Former Prophets", "Latter Prophets", "The Twelve"}
MAX_SAMPLE_REFS = 10
MAX_ANCHORS_PER_UNIT = 8
HIGH_VALUE_MAX_OUTSIDE = 250


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


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


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
    if name.endswith("TanachHeader.xml") or name.endswith("TanachIndex.xml"):
        return False
    return True


def add_sample(samples: list[str], value: str, limit: int = MAX_SAMPLE_REFS) -> None:
    if value and value not in samples and len(samples) < limit:
        samples.append(value)


def serialize_counter(counter: Counter[str], limit: int | None = None) -> dict[str, int]:
    pairs = counter.most_common(limit)
    return {key: value for key, value in pairs}


def find_source_version(root: ET.Element) -> dict[str, str]:
    edition = root.find(".//edition")
    if edition is None:
        return {}
    return {
        "version": edition.findtext("version") or "",
        "date": edition.findtext("date") or "",
        "build": edition.findtext("build") or "",
        "build_datetime": edition.findtext("buildDateTime") or "",
    }


def build_tanakh_form_index(zip_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    form_index: dict[str, dict[str, Any]] = {}
    book_rows = []
    division_totals: Counter[str] = Counter()
    source_version: dict[str, str] = {}

    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(name for name in archive.namelist() if canonical_book_file(name))
        for name in names:
            root = ET.fromstring(archive.read(name))
            if not source_version:
                source_version = find_source_version(root)
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
                        normalized = normalize_hebrew_form("".join(word.itertext()))
                        if not normalized:
                            continue
                        word_count += 1
                        local_forms[normalized] += 1
                        entry = form_index.setdefault(
                            normalized,
                            {
                                "form": normalized,
                                "tanakh_count": 0,
                                "psalms_count": 0,
                                "outside_psalms_count": 0,
                                "division_counts": Counter(),
                                "outside_division_counts": Counter(),
                                "book_counts": Counter(),
                                "outside_book_counts": Counter(),
                                "outside_refs_by_division": defaultdict(list),
                                "outside_refs_by_book": defaultdict(list),
                            },
                        )
                        entry["tanakh_count"] += 1
                        entry["division_counts"][division] += 1
                        entry["book_counts"][book_name] += 1
                        if book_name == "Psalms":
                            entry["psalms_count"] += 1
                        else:
                            entry["outside_psalms_count"] += 1
                            entry["outside_division_counts"][division] += 1
                            entry["outside_book_counts"][book_name] += 1
                            add_sample(entry["outside_refs_by_division"][division], ref)
                            add_sample(entry["outside_refs_by_book"][book_name], ref)

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
        entry["division_counts"] = Counter(entry["division_counts"])
        entry["outside_division_counts"] = Counter(entry["outside_division_counts"])
        entry["book_counts"] = Counter(entry["book_counts"])
        entry["outside_book_counts"] = Counter(entry["outside_book_counts"])
        entry["outside_refs_by_division"] = {
            key: list(value) for key, value in entry["outside_refs_by_division"].items()
        }
        entry["outside_refs_by_book"] = {
            key: list(value) for key, value in entry["outside_refs_by_book"].items()
        }

    tanakh_summary = {
        "source_version": source_version,
        "book_count": len(book_rows),
        "word_elements": sum(row["word_elements"] for row in book_rows),
        "distinct_normalized_forms": len(form_index),
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
    return form_index, tanakh_summary


def load_suite_units(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    suite = load_json(path)
    units: dict[str, dict[str, Any]] = {}
    for task in suite.get("tasks", []):
        unit_id = str(task["unit_id"])
        row = units.setdefault(
            unit_id,
            {
                "unit_id": unit_id,
                "ref": task.get("ref", ""),
                "layers": set(),
                "benchmark_tags": Counter(),
                "task_count": 0,
                "suite_sources": Counter(),
            },
        )
        row["layers"].add(str(task.get("layer") or ""))
        row["benchmark_tags"].update(str(tag) for tag in task.get("benchmark_tags", []))
        row["suite_sources"].update([str(task.get("suite_source") or "unknown")])
        row["task_count"] += 1
    for row in units.values():
        row["layers"] = sorted(layer for layer in row["layers"] if layer)
        row["benchmark_tags"] = dict(row["benchmark_tags"].most_common())
        row["suite_sources"] = dict(row["suite_sources"].most_common())
    return units, suite.get("summary", {})


def load_atlas_units(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    atlas = load_json(path)
    return {
        str(row["unit_id"]): row
        for row in atlas.get("priority_unit_rows", [])
        if row.get("unit_id")
    }


def unit_path(content_root: Path, unit_id: str) -> Path:
    psalm_id = unit_id.split(".")[0]
    return content_root / psalm_id / f"{unit_id}.json"


def is_content_token(token: dict[str, Any]) -> bool:
    return str(token.get("part_of_speech") or "").lower() in CONTENT_POS


def token_anchor_score(
    token: dict[str, Any],
    surface_entry: dict[str, Any],
    lemma_entry: dict[str, Any],
) -> float:
    surface_outside = int(surface_entry.get("outside_psalms_count") or 0)
    lemma_outside = int(lemma_entry.get("outside_psalms_count") or 0)
    if not surface_outside and not lemma_outside:
        return 0.0
    divisions = set(surface_entry.get("outside_division_counts") or {})
    divisions.update(lemma_entry.get("outside_division_counts") or {})
    evidence = surface_outside or lemma_outside
    specificity = 90.0 / math.sqrt(max(1, evidence))
    content_bonus = 25.0 if is_content_token(token) else 0.0
    division_bonus = len(divisions) * 7.5
    lemma_bonus = 8.0 if lemma_outside and lemma_outside != surface_outside else 0.0
    high_frequency_penalty = max(0.0, (evidence - 500) / 35)
    return round(
        content_bonus + specificity + division_bonus + lemma_bonus - high_frequency_penalty,
        2,
    )


def token_evidence(
    token: dict[str, Any],
    form_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    surface_query = str(token.get("normalized") or normalize_hebrew_form(token.get("surface")))
    lemma_query = normalize_hebrew_form(token.get("lemma"))
    surface_entry = form_index.get(surface_query, {})
    lemma_entry = form_index.get(lemma_query, {}) if lemma_query else {}
    surface_outside = int(surface_entry.get("outside_psalms_count") or 0)
    lemma_outside = int(lemma_entry.get("outside_psalms_count") or 0)
    surface_divisions = Counter(surface_entry.get("outside_division_counts") or {})
    lemma_divisions = Counter(lemma_entry.get("outside_division_counts") or {})
    high_value_surface = (
        is_content_token(token)
        and surface_outside > 0
        and surface_outside <= HIGH_VALUE_MAX_OUTSIDE
    )
    high_value_lemma = (
        is_content_token(token) and lemma_outside > 0 and lemma_outside <= HIGH_VALUE_MAX_OUTSIDE
    )
    return {
        "token_id": token.get("token_id", ""),
        "surface": token.get("surface", ""),
        "lemma": token.get("lemma", ""),
        "display_gloss": token.get("display_gloss", ""),
        "part_of_speech": token.get("part_of_speech", ""),
        "surface_query": surface_query,
        "lemma_query": lemma_query,
        "surface_outside_psalms_count": surface_outside,
        "lemma_outside_psalms_count": lemma_outside,
        "surface_outside_division_counts": dict(surface_divisions.most_common()),
        "lemma_outside_division_counts": dict(lemma_divisions.most_common()),
        "surface_outside_book_counts": dict(
            Counter(surface_entry.get("outside_book_counts") or {}).most_common(8)
        ),
        "surface_sample_refs_by_division": surface_entry.get(
            "outside_refs_by_division",
            {},
        ),
        "high_value_surface_anchor": high_value_surface,
        "high_value_lemma_anchor": high_value_lemma,
        "content_token": is_content_token(token),
        "anchor_score": token_anchor_score(token, surface_entry, lemma_entry),
    }


def evidence_grade(row: dict[str, Any]) -> str:
    if int(row["token_count"]) == 0:
        return "missing unit tokens"
    if int(row["high_value_anchor_count"]) >= 3 and int(row["outside_division_count"]) >= 3:
        return "strong cross-canon surface network"
    if float(row["surface_outside_context_pct"]) >= 70 and int(row["outside_division_count"]) >= 3:
        return "broad surface evidence; needs sense control"
    if int(row["high_value_anchor_count"]) >= 1:
        return "thin anchor evidence"
    return "weak or missing cross-canon evidence"


def review_flags(row: dict[str, Any]) -> list[str]:
    flags = []
    tags = set(row.get("benchmark_tags", []))
    domains = set(row.get("domains", []))
    if row["evidence_grade"] == "weak or missing cross-canon evidence":
        flags.append("weak_cross_canon_evidence")
    if row["content_token_outside_context_pct"] < 50:
        flags.append("content_tokens_need_review")
    if row["function_token_context_share_pct"] >= 60:
        flags.append("function_word_dominated_context")
    if not row["has_torah_evidence"]:
        flags.append("no_torah_surface_bridge")
    if not row["has_prophets_evidence"]:
        flags.append("no_prophets_surface_bridge")
    if tags & {"messianic_interpretation", "intertextuality", "canonical_intertext"}:
        flags.append("interpretive_intertext_review")
    if "jewish_christian_reception" in domains or "reception_history" in tags:
        flags.append("reception_boundary_review")
    if "textual_witness_pressure" in domains or "textual_witness" in tags:
        flags.append("witness_boundary_review")
    return flags


def build_unit_row(
    unit_meta: dict[str, Any],
    atlas_row: dict[str, Any],
    content_root: Path,
    form_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    unit_id = str(unit_meta["unit_id"])
    path = unit_path(content_root, unit_id)
    unit = load_json(path) if path.exists() else {}
    token_rows = [token_evidence(token, form_index) for token in unit.get("tokens", [])]
    token_count = len(token_rows)
    content_token_count = sum(1 for token in token_rows if token["content_token"])
    surface_outside_count = sum(
        1 for token in token_rows if int(token["surface_outside_psalms_count"]) > 0
    )
    lemma_outside_count = sum(
        1 for token in token_rows if int(token["lemma_outside_psalms_count"]) > 0
    )
    content_surface_outside_count = sum(
        1
        for token in token_rows
        if token["content_token"] and int(token["surface_outside_psalms_count"]) > 0
    )
    high_value_anchor_count = sum(
        1
        for token in token_rows
        if token["high_value_surface_anchor"] or token["high_value_lemma_anchor"]
    )
    division_counts: Counter[str] = Counter()
    lemma_division_counts: Counter[str] = Counter()
    book_counts: Counter[str] = Counter()
    function_evidence_count = 0
    for token in token_rows:
        division_counts.update(token["surface_outside_division_counts"])
        lemma_division_counts.update(token["lemma_outside_division_counts"])
        book_counts.update(token["surface_outside_book_counts"])
        if not token["content_token"] and int(token["surface_outside_psalms_count"]) > 0:
            function_evidence_count += 1

    divisions = set(division_counts)
    prophets_hit = bool(divisions & PROPHET_DIVISIONS)
    anchors = sorted(
        [token for token in token_rows if float(token["anchor_score"]) > 0],
        key=lambda token: float(token["anchor_score"]),
        reverse=True,
    )[:MAX_ANCHORS_PER_UNIT]
    row = {
        "unit_id": unit_id,
        "ref": unit_meta.get("ref") or unit.get("ref", ""),
        "task_count": int(unit_meta.get("task_count") or 0),
        "layers": unit_meta.get("layers", []),
        "benchmark_tags": sorted(unit_meta.get("benchmark_tags", {}).keys()),
        "domains": atlas_row.get("domains", []),
        "domain_groups": atlas_row.get("domain_groups", []),
        "required_frames": atlas_row.get("required_frames", []),
        "token_count": token_count,
        "content_token_count": content_token_count,
        "surface_outside_token_count": surface_outside_count,
        "lemma_outside_token_count": lemma_outside_count,
        "content_surface_outside_token_count": content_surface_outside_count,
        "surface_outside_context_pct": pct(surface_outside_count, token_count),
        "lemma_outside_context_pct": pct(lemma_outside_count, token_count),
        "content_token_outside_context_pct": pct(
            content_surface_outside_count,
            content_token_count,
        ),
        "function_token_context_share_pct": pct(function_evidence_count, surface_outside_count),
        "high_value_anchor_count": high_value_anchor_count,
        "outside_division_count": len(divisions),
        "outside_division_counts": dict(division_counts.most_common()),
        "lemma_outside_division_counts": dict(lemma_division_counts.most_common()),
        "outside_book_counts": dict(book_counts.most_common(12)),
        "has_torah_evidence": "Torah" in divisions,
        "has_prophets_evidence": prophets_hit,
        "has_non_psalm_writings_evidence": "Writings" in divisions,
        "top_anchor_tokens": anchors,
        "source_hebrew": unit.get("source_hebrew", ""),
    }
    row["evidence_grade"] = evidence_grade(row)
    row["review_flags"] = review_flags(row)
    return row


def build_unit_rows(
    suite_units: dict[str, dict[str, Any]],
    atlas_units: dict[str, dict[str, Any]],
    content_root: Path,
    form_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        build_unit_row(
            unit_meta,
            atlas_units.get(unit_id, {}),
            content_root,
            form_index,
        )
        for unit_id, unit_meta in sorted(suite_units.items())
    ]
    return sorted(
        rows,
        key=lambda row: (
            row["evidence_grade"] == "weak or missing cross-canon evidence",
            len(row["review_flags"]),
            -float(row["surface_outside_context_pct"]),
            row["unit_id"],
        ),
        reverse=True,
    )


def domain_rows(
    unit_rows: list[dict[str, Any]],
    atlas_units: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    atlas_domain_units: dict[str, set[str]] = defaultdict(set)
    expanded_domain_units: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit_id, row in atlas_units.items():
        for domain in row.get("domains", []):
            atlas_domain_units[str(domain)].add(unit_id)
    for row in unit_rows:
        for domain in row.get("domains", []) or ["unclassified"]:
            expanded_domain_units[str(domain)].append(row)

    rows = []
    for domain in sorted(set(atlas_domain_units) | set(expanded_domain_units)):
        expanded_rows = expanded_domain_units.get(domain, [])
        atlas_count = len(atlas_domain_units.get(domain, set()))
        strong_count = sum(
            1
            for row in expanded_rows
            if row["evidence_grade"] == "strong cross-canon surface network"
        )
        weak_count = sum(
            1
            for row in expanded_rows
            if row["evidence_grade"] == "weak or missing cross-canon evidence"
        )
        rows.append(
            {
                "domain": domain,
                "atlas_unit_count": atlas_count,
                "expanded_unit_count": len(expanded_rows),
                "expanded_coverage_pct": pct(len(expanded_rows), atlas_count),
                "avg_surface_outside_context_pct": mean(
                    [float(row["surface_outside_context_pct"]) for row in expanded_rows]
                ),
                "avg_content_token_outside_context_pct": mean(
                    [float(row["content_token_outside_context_pct"]) for row in expanded_rows]
                ),
                "strong_network_unit_count": strong_count,
                "weak_network_unit_count": weak_count,
                "torah_evidence_unit_pct": pct(
                    sum(1 for row in expanded_rows if row["has_torah_evidence"]),
                    len(expanded_rows),
                ),
                "prophets_evidence_unit_pct": pct(
                    sum(1 for row in expanded_rows if row["has_prophets_evidence"]),
                    len(expanded_rows),
                ),
                "writings_evidence_unit_pct": pct(
                    sum(1 for row in expanded_rows if row["has_non_psalm_writings_evidence"]),
                    len(expanded_rows),
                ),
                "review_queue_count": sum(1 for row in expanded_rows if row["review_flags"]),
                "weakest_units": "; ".join(
                    row["unit_id"]
                    for row in sorted(
                        expanded_rows,
                        key=lambda unit: (
                            float(unit["content_token_outside_context_pct"]),
                            -len(unit["review_flags"]),
                        ),
                    )[:5]
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            float(row["avg_content_token_outside_context_pct"]),
            -int(row["review_queue_count"]),
            str(row["domain"]),
        ),
    )


def book_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    book_counts: Counter[str] = Counter()
    book_units: dict[str, set[str]] = defaultdict(set)
    for row in unit_rows:
        for book, count in row["outside_book_counts"].items():
            book_counts[book] += int(count)
            book_units[book].add(str(row["unit_id"]))
    rows = []
    for book, count in book_counts.most_common():
        rows.append(
            {
                "book": book,
                "division": DIVISIONS.get(book, "Unmapped"),
                "surface_occurrence_evidence": count,
                "unit_count_with_evidence": len(book_units[book]),
                "unit_coverage_pct": pct(len(book_units[book]), len(unit_rows)),
            }
        )
    return rows


def division_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    division_counts: Counter[str] = Counter()
    division_units: dict[str, set[str]] = defaultdict(set)
    for row in unit_rows:
        for division, count in row["outside_division_counts"].items():
            division_counts[division] += int(count)
            division_units[division].add(str(row["unit_id"]))
    return [
        {
            "division": division,
            "surface_occurrence_evidence": count,
            "unit_count_with_evidence": len(division_units[division]),
            "unit_coverage_pct": pct(len(division_units[division]), len(unit_rows)),
        }
        for division, count in division_counts.most_common()
    ]


def summarize(
    suite_summary: dict[str, Any],
    unit_rows: list[dict[str, Any]],
    tanakh_summary: dict[str, Any],
) -> dict[str, Any]:
    token_count = sum(int(row["token_count"]) for row in unit_rows)
    content_count = sum(int(row["content_token_count"]) for row in unit_rows)
    surface_count = sum(int(row["surface_outside_token_count"]) for row in unit_rows)
    lemma_count = sum(int(row["lemma_outside_token_count"]) for row in unit_rows)
    content_surface_count = sum(
        int(row["content_surface_outside_token_count"]) for row in unit_rows
    )
    high_value_anchor_units = sum(1 for row in unit_rows if row["high_value_anchor_count"])
    weak_units = [
        row for row in unit_rows if row["evidence_grade"] == "weak or missing cross-canon evidence"
    ]
    strong_units = [
        row for row in unit_rows if row["evidence_grade"] == "strong cross-canon surface network"
    ]
    three_division_units = sum(1 for row in unit_rows if int(row["outside_division_count"]) >= 3)
    return {
        "suite_task_count": suite_summary.get("task_count", 0),
        "suite_unit_count": suite_summary.get("unit_count", len(unit_rows)),
        "unit_count": len(unit_rows),
        "token_count": token_count,
        "content_token_count": content_count,
        "tanakh_book_count": tanakh_summary["book_count"],
        "tanakh_word_elements": tanakh_summary["word_elements"],
        "tanakh_distinct_forms": tanakh_summary["distinct_normalized_forms"],
        "surface_outside_context_token_pct": pct(surface_count, token_count),
        "lemma_form_outside_context_token_pct": pct(lemma_count, token_count),
        "content_token_outside_context_pct": pct(content_surface_count, content_count),
        "units_with_high_value_anchor_count": high_value_anchor_units,
        "units_with_high_value_anchor_pct": pct(high_value_anchor_units, len(unit_rows)),
        "units_with_torah_evidence_pct": pct(
            sum(1 for row in unit_rows if row["has_torah_evidence"]),
            len(unit_rows),
        ),
        "units_with_prophets_evidence_pct": pct(
            sum(1 for row in unit_rows if row["has_prophets_evidence"]),
            len(unit_rows),
        ),
        "units_with_non_psalm_writings_evidence_pct": pct(
            sum(1 for row in unit_rows if row["has_non_psalm_writings_evidence"]),
            len(unit_rows),
        ),
        "units_with_three_division_evidence_pct": pct(three_division_units, len(unit_rows)),
        "strong_network_unit_count": len(strong_units),
        "strong_network_unit_pct": pct(len(strong_units), len(unit_rows)),
        "weak_network_unit_count": len(weak_units),
        "weak_network_unit_pct": pct(len(weak_units), len(unit_rows)),
        "review_queue_unit_count": sum(1 for row in unit_rows if row["review_flags"]),
        "whole_tanakh_lemma_index_available": False,
        "source_version": tanakh_summary.get("source_version", {}),
    }


def csv_unit_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "unit_id": row["unit_id"],
            "ref": row["ref"],
            "task_count": row["task_count"],
            "token_count": row["token_count"],
            "content_token_count": row["content_token_count"],
            "surface_outside_context_pct": row["surface_outside_context_pct"],
            "lemma_outside_context_pct": row["lemma_outside_context_pct"],
            "content_token_outside_context_pct": row["content_token_outside_context_pct"],
            "high_value_anchor_count": row["high_value_anchor_count"],
            "outside_division_count": row["outside_division_count"],
            "has_torah_evidence": row["has_torah_evidence"],
            "has_prophets_evidence": row["has_prophets_evidence"],
            "has_non_psalm_writings_evidence": row["has_non_psalm_writings_evidence"],
            "evidence_grade": row["evidence_grade"],
            "review_flags": "|".join(row["review_flags"]),
            "domains": "|".join(row["domains"]),
            "benchmark_tags": "|".join(row["benchmark_tags"]),
        }
        for row in unit_rows
    ]


def build_report(
    content_root: Path,
    uxlc_zip_path: Path,
    expanded_suite_path: Path,
    atlas_path: Path,
) -> dict[str, Any]:
    form_index, tanakh_summary = build_tanakh_form_index(uxlc_zip_path)
    suite_units, suite_summary = load_suite_units(expanded_suite_path)
    atlas_units = load_atlas_units(atlas_path)
    units = build_unit_rows(suite_units, atlas_units, content_root, form_index)
    domains = domain_rows(units, atlas_units)
    books = book_rows(units)
    divisions = division_rows(units)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": (
            "generated canonical context network; surface-form evidence only, not lemma/sense proof"
        ),
        "source_paths": {
            "content_root": str(content_root.relative_to(ROOT)),
            "uxlc_zip": str(uxlc_zip_path.relative_to(ROOT)),
            "expanded_suite": str(expanded_suite_path.relative_to(ROOT)),
            "contextual_pressure_atlas": str(atlas_path.relative_to(ROOT)),
        },
        "normalization": {
            "method": "NFKD; remove combining marks, Hebrew punctuation, and whitespace",
            "evidence_boundary": (
                "Cross-canon links are normalized surface-form and lemma-form string "
                "bridges. They support retrieval and review routing, not automatic "
                "claims of shared sense, syntax, or interpretation."
            ),
        },
        "summary": summarize(suite_summary, units, tanakh_summary),
        "tanakh_source_summary": tanakh_summary,
        "division_evidence_rows": divisions,
        "book_evidence_rows": books,
        "domain_network_rows": domains,
        "unit_network_rows": units,
    }


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    width: int = 980,
    limit: int = 18,
) -> str:
    rows = rows[:limit]
    row_h = 30
    left = 280
    right = 90
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
            f'font-size="12" fill="#26323a">{esc(row[label_key])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="19" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 19}" font-size="12" '
            f'font-weight="700" fill="#26323a">{value:g}</text>'
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
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows
        )
        + "</tbody></table>"
    )


def render_anchor_summary(row: dict[str, Any]) -> str:
    anchors = []
    for token in row.get("top_anchor_tokens", [])[:4]:
        divisions = token.get("surface_sample_refs_by_division") or {}
        samples = []
        for division, refs in list(divisions.items())[:2]:
            samples.append(f"{division}: {', '.join(refs[:3])}")
        anchors.append(
            f"{token.get('surface', '')} / {token.get('display_gloss', '')} "
            f"({token.get('surface_outside_psalms_count', 0)} outside; "
            f"{'; '.join(samples)})"
        )
    return " | ".join(anchors)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    source_version = summary.get("source_version", {})
    domain_table_rows = [
        [
            row["domain"],
            row["atlas_unit_count"],
            row["expanded_unit_count"],
            f"{row['avg_content_token_outside_context_pct']:.2f}%",
            row["weak_network_unit_count"],
            f"{row['torah_evidence_unit_pct']:.2f}%",
            f"{row['prophets_evidence_unit_pct']:.2f}%",
            row["weakest_units"],
        ]
        for row in report["domain_network_rows"]
    ]
    review_rows = [
        [
            row["unit_id"],
            row["ref"],
            row["evidence_grade"],
            f"{row['content_token_outside_context_pct']:.2f}%",
            row["high_value_anchor_count"],
            ", ".join(row["review_flags"]),
            render_anchor_summary(row),
        ]
        for row in sorted(
            report["unit_network_rows"],
            key=lambda item: (
                len(item["review_flags"]),
                item["evidence_grade"] == "weak or missing cross-canon evidence",
            ),
            reverse=True,
        )[:30]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Canonical Context Network</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1f2b33;
      --muted: #63717a;
      --line: #d8dee3;
      --band: #f4f7f7;
      --accent: #2f6f73;
      --accent2: #6f5d2f;
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
      background: #f8faf9;
    }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 30px 34px 54px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    p {{ color: var(--muted); max-width: 980px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 14px;
      margin: 20px 0;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: #ffffff;
    }}
    .metric {{ font-size: 28px; font-weight: 800; color: var(--accent); }}
    .label {{ font-weight: 700; margin-top: 4px; }}
    .note {{
      border-left: 4px solid var(--accent2);
      background: var(--band);
      padding: 12px 14px;
      margin: 18px 0;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 14px 0 24px;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: var(--band); font-size: 12px; text-transform: uppercase; }}
    .chart {{ border: 1px solid var(--line); border-radius: 8px; overflow-x: auto; }}
    code {{ background: #eef2f2; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <header>
    <h1>Canonical Context Network</h1>
    <p>
      Cross-canon evidence for expanded Psalm benchmark units, generated from
      read-only UXLC normalized Hebrew forms and local Psalm token metadata.
    </p>
  </header>
  <main>
    {
        metric_cards(
            [
                (
                    "Expanded Units",
                    fmt_int(summary["unit_count"]),
                    "Unique benchmark units mapped.",
                ),
                (
                    "Surface Context",
                    f'''{summary["surface_outside_context_token_pct"]:.2f}%''',
                    "Tokens with matching normalized forms outside Psalms.",
                ),
                (
                    "Content Context",
                    f'''{summary["content_token_outside_context_pct"]:.2f}%''',
                    "Noun, verb, adjective, and adverb tokens with outside-Psalms form evidence.",
                ),
                (
                    "High-Value Anchor Units",
                    f'''{summary["units_with_high_value_anchor_pct"]:.2f}%''',
                    (
                        "Units with at least one content-token anchor under the high-frequency "
                        "ceiling."
                    ),
                ),
                (
                    "Three-Division Units",
                    f'''{summary["units_with_three_division_evidence_pct"]:.2f}%''',
                    "Units with surface evidence in at least three non-Psalm divisions.",
                ),
                (
                    "Weak Network Units",
                    fmt_int(summary["weak_network_unit_count"]),
                    "Units needing priority cross-canon review.",
                ),
            ]
        )
    }

    <div class="note">
      Evidence boundary: this report proves retrieval coverage and review pressure,
      not lemma identity, sense identity, or theological interpretation.
      Whole-Tanakh lemma indexing remains marked unavailable.
    </div>

    <h2>Source Profile</h2>
    {
        table(
            ["Source", "Value"],
            [
                ["UXLC version", source_version.get("version", "")],
                ["UXLC date", source_version.get("date", "")],
                ["UXLC build", source_version.get("build", "")],
                ["Tanakh books", summary["tanakh_book_count"]],
                ["Tanakh word elements", fmt_int(summary["tanakh_word_elements"])],
                ["Distinct normalized forms", fmt_int(summary["tanakh_distinct_forms"])],
            ],
        )
    }

    <h2>Division Evidence</h2>
    <div class="chart">
      {
        svg_horizontal_bars(
            report["division_evidence_rows"],
            label_key="division",
            value_key="unit_count_with_evidence",
            aria_label="Units with surface evidence by Tanakh division",
            color="#2f6f73",
        )
    }
    </div>

    <h2>Domain Network Coverage</h2>
    {
        table(
            [
                "Domain",
                "Atlas Units",
                "Expanded Units",
                "Avg Content Context",
                "Weak Units",
                "Torah",
                "Prophets",
                "Weakest Units",
            ],
            domain_table_rows,
        )
    }

    <h2>Top Book Bridges</h2>
    <div class="chart">
      {
        svg_horizontal_bars(
            report["book_evidence_rows"],
            label_key="book",
            value_key="unit_count_with_evidence",
            aria_label="Expanded units with evidence by non-Psalm book",
            color="#6f5d2f",
            limit=20,
        )
    }
    </div>

    <h2>Review Queue</h2>
    {
        table(
            [
                "Unit",
                "Reference",
                "Grade",
                "Content Context",
                "Anchors",
                "Review Flags",
                "Anchor Samples",
            ],
            review_rows,
        )
    }
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate cross-canon context network evidence for Psalm benchmark units."
    )
    parser.add_argument("--content-root", type=Path, default=CONTENT_ROOT)
    parser.add_argument("--uxlc-zip", type=Path, default=UXLC_ZIP_PATH)
    parser.add_argument("--expanded-suite", type=Path, default=EXPANDED_SUITE_PATH)
    parser.add_argument("--atlas", type=Path, default=ATLAS_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--domain-csv-output", type=Path, default=DEFAULT_DOMAIN_CSV_OUTPUT)
    parser.add_argument("--book-csv-output", type=Path, default=DEFAULT_BOOK_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    args = parser.parse_args()

    report = build_report(
        args.content_root,
        args.uxlc_zip,
        args.expanded_suite,
        args.atlas,
    )
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, csv_unit_rows(report["unit_network_rows"]))
    write_csv(args.domain_csv_output, report["domain_network_rows"])
    write_csv(args.book_csv_output, report["book_evidence_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")


if __name__ == "__main__":
    main()
