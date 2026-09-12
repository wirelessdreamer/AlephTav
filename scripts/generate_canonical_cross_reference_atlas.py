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
REPORT_ROOT = ROOT / "reports" / "research"
UXLC_ZIP_PATH = ROOT / "data" / "raw" / "uxlc" / "Tanach.xml.zip"

CULTURAL_ATLAS_PATH = REPORT_ROOT / "cultural_historical_domain_atlas.json"
CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
RECEPTION_BOUNDARY_PATH = REPORT_ROOT / "reception_interpretation_boundary.json"
WITNESS_DIVERGENCE_PATH = REPORT_ROOT / "witness_divergence_report.json"
SUPER_CONTEXT_PATH = REPORT_ROOT / "superscription_context_report.json"
DIVINE_NAME_PATH = REPORT_ROOT / "divine_name_policy_report.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "canonical_cross_reference_atlas.json"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "canonical_cross_reference_atlas.html"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "canonical_cross_reference_atlas_units.csv"
DEFAULT_ANCHOR_CSV_OUTPUT = REPORT_ROOT / "canonical_cross_reference_atlas_anchors.csv"
DEFAULT_BOOK_CSV_OUTPUT = REPORT_ROOT / "canonical_cross_reference_atlas_books.csv"
DEFAULT_DOMAIN_CSV_OUTPUT = REPORT_ROOT / "canonical_cross_reference_atlas_domains.csv"
DEFAULT_DIVISION_CSV_OUTPUT = REPORT_ROOT / "canonical_cross_reference_atlas_divisions.csv"

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

PROPHET_DIVISIONS = {"Former Prophets", "Latter Prophets", "The Twelve"}
CONTENT_POS = {"noun", "verb", "adjective", "adverb"}
PUNCTUATION = {"\u05be", "\u05c0", "\u05c3", "\u05c6", " ", "\t", "\n"}
MAX_REF_SAMPLES = 8
MAX_ANCHORS_PER_UNIT = 8
HIGH_VALUE_OUTSIDE_MAX = 75
MEDIUM_VALUE_OUTSIDE_MAX = 250


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


def add_sample(samples: list[str], value: str) -> None:
    if value and value not in samples and len(samples) < MAX_REF_SAMPLES:
        samples.append(value)


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
            book_counter: Counter[str] = Counter()
            word_count = 0

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
                        book_counter[normalized] += 1
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
                    "distinct_normalized_forms": len(book_counter),
                }
            )

    serializable_index = {}
    for form, entry in form_index.items():
        serializable_index[form] = {
            **entry,
            "division_counts": Counter(entry["division_counts"]),
            "outside_division_counts": Counter(entry["outside_division_counts"]),
            "book_counts": Counter(entry["book_counts"]),
            "outside_book_counts": Counter(entry["outside_book_counts"]),
            "outside_refs_by_division": {
                key: list(value) for key, value in entry["outside_refs_by_division"].items()
            },
            "outside_refs_by_book": {
                key: list(value) for key, value in entry["outside_refs_by_book"].items()
            },
        }

    summary = {
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
    return serializable_index, summary


def unit_lookup(report: dict[str, Any], row_key: str) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in report.get(row_key, []) if row.get("unit_id")}


def load_context_reports() -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "cultural": unit_lookup(maybe_load_json(CULTURAL_ATLAS_PATH), "unit_rows"),
        "claim": unit_lookup(maybe_load_json(CLAIM_MATRIX_PATH), "unit_claim_rows"),
        "reception": unit_lookup(maybe_load_json(RECEPTION_BOUNDARY_PATH), "unit_boundary_rows"),
        "witness": unit_lookup(maybe_load_json(WITNESS_DIVERGENCE_PATH), "unit_rows"),
        "superscription": unit_lookup(maybe_load_json(SUPER_CONTEXT_PATH), "unit_rows"),
        "divine": unit_lookup(maybe_load_json(DIVINE_NAME_PATH), "unit_rows"),
    }


def is_content_token(token: dict[str, Any]) -> bool:
    return str(token.get("part_of_speech") or "").lower() in CONTENT_POS


def division_flags(outside_divisions: Counter[str]) -> dict[str, bool]:
    return {
        "has_torah_evidence": outside_divisions["Torah"] > 0,
        "has_prophets_evidence": any(
            outside_divisions[division] > 0 for division in PROPHET_DIVISIONS
        ),
        "has_non_psalm_writings_evidence": outside_divisions["Writings"] > 0,
    }


def anchor_strength(entry: dict[str, Any]) -> str:
    outside = int(entry["outside_psalms_count"])
    outside_divisions = Counter(entry["outside_division_counts"])
    flags = division_flags(outside_divisions)
    division_count = sum(1 for present in flags.values() if present)
    if 0 < outside <= HIGH_VALUE_OUTSIDE_MAX and division_count >= 2:
        return "high"
    if outside <= MEDIUM_VALUE_OUTSIDE_MAX and division_count >= 2:
        return "medium"
    if outside > 0:
        return "low"
    return "none"


def anchor_score(entry: dict[str, Any], token: dict[str, Any]) -> float:
    outside = int(entry["outside_psalms_count"])
    if outside <= 0:
        return 0.0
    outside_divisions = Counter(entry["outside_division_counts"])
    flags = division_flags(outside_divisions)
    score = 16.0
    score += sum(7.0 for present in flags.values() if present)
    score += min(16.0, math.log1p(outside) * 2.0)
    if outside <= HIGH_VALUE_OUTSIDE_MAX:
        score += 13.0
    elif outside <= MEDIUM_VALUE_OUTSIDE_MAX:
        score += 6.0
    elif outside > 1000:
        score -= 7.0
    if is_content_token(token):
        score += 6.0
    return round(score, 2)


def build_anchor_row(
    unit: dict[str, Any],
    token: dict[str, Any],
    entry: dict[str, Any],
) -> dict[str, Any]:
    outside_divisions = Counter(entry["outside_division_counts"])
    outside_books = Counter(entry["outside_book_counts"])
    refs_by_division = entry["outside_refs_by_division"]
    refs_by_book = entry["outside_refs_by_book"]
    top_books = outside_books.most_common(8)
    return {
        "unit_id": unit["unit_id"],
        "ref": unit.get("ref", ""),
        "psalm_id": unit["psalm_id"],
        "token_id": token.get("token_id", ""),
        "surface": token.get("surface", ""),
        "normalized": normalize_hebrew_form(token.get("surface") or token.get("normalized")),
        "lemma": token.get("lemma", ""),
        "display_gloss": token.get("display_gloss", ""),
        "strong": token.get("strong", ""),
        "part_of_speech": token.get("part_of_speech", ""),
        "outside_psalms_count": int(entry["outside_psalms_count"]),
        "tanakh_count": int(entry["tanakh_count"]),
        "outside_division_counts": dict(outside_divisions.most_common()),
        "outside_book_counts": dict(top_books),
        "has_torah_evidence": outside_divisions["Torah"] > 0,
        "has_prophets_evidence": any(
            outside_divisions[division] > 0 for division in PROPHET_DIVISIONS
        ),
        "has_non_psalm_writings_evidence": outside_divisions["Writings"] > 0,
        "outside_torah_refs": refs_by_division.get("Torah", []),
        "outside_prophets_refs": [
            ref
            for division in ["Former Prophets", "Latter Prophets", "The Twelve"]
            for ref in refs_by_division.get(division, [])
        ][:MAX_REF_SAMPLES],
        "outside_writings_refs": refs_by_division.get("Writings", []),
        "top_book_refs": {book: refs_by_book.get(book, []) for book, _count in top_books},
        "anchor_strength": anchor_strength(entry),
        "anchor_score": anchor_score(entry, token),
    }


def unit_priority_score(
    *,
    anchor_rows: list[dict[str, Any]],
    cultural: dict[str, Any],
    claim: dict[str, Any],
    reception: dict[str, Any],
    witness: dict[str, Any],
    superscription: dict[str, Any],
    divine: dict[str, Any],
) -> float:
    if not anchor_rows:
        return 0.0
    score = sum(float(row["anchor_score"]) for row in anchor_rows[:MAX_ANCHORS_PER_UNIT]) / 2.0
    score += len(anchor_rows) * 1.5
    score += 12.0 if any(row["anchor_strength"] == "high" for row in anchor_rows) else 0.0
    score += min(24.0, float(cultural.get("priority_score") or 0) / 8.0)
    score += min(22.0, float(claim.get("claim_risk_score") or 0) / 9.0)
    score += min(18.0, float(reception.get("boundary_risk_score") or 0) / 7.0)
    score += min(18.0, float(witness.get("priority_score") or 0) / 9.0)
    if claim.get("ancient_culture_pressure") or reception.get("ancient_culture_pressure"):
        score += 12.0
    if claim.get("reception_sensitive") or reception.get("reception_sensitive"):
        score += 12.0
    if claim.get("textual_witness_pressure") or reception.get("textual_witness_pressure"):
        score += 8.0
    if superscription:
        score += 7.0
    if divine:
        score += 6.0
    return round(score, 2)


def build_unit_row(
    unit: dict[str, Any],
    anchor_rows: list[dict[str, Any]],
    context: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    unit_id = str(unit["unit_id"])
    cultural = context["cultural"].get(unit_id, {})
    claim = context["claim"].get(unit_id, {})
    reception = context["reception"].get(unit_id, {})
    witness = context["witness"].get(unit_id, {})
    superscription = context["superscription"].get(unit_id, {})
    divine = context["divine"].get(unit_id, {})
    outside_divisions: Counter[str] = Counter()
    outside_books: Counter[str] = Counter()
    strength_counts: Counter[str] = Counter(row["anchor_strength"] for row in anchor_rows)
    for anchor in anchor_rows:
        outside_divisions.update(anchor["outside_division_counts"])
        outside_books.update(anchor["outside_book_counts"])
    flags = division_flags(outside_divisions)
    selected_anchors = sorted(anchor_rows, key=lambda row: float(row["anchor_score"]), reverse=True)
    priority = unit_priority_score(
        anchor_rows=selected_anchors,
        cultural=cultural,
        claim=claim,
        reception=reception,
        witness=witness,
        superscription=superscription,
        divine=divine,
    )
    return {
        "unit_id": unit_id,
        "ref": unit.get("ref", ""),
        "psalm_id": unit["psalm_id"],
        "content_token_count": sum(
            1 for token in unit.get("tokens", []) if is_content_token(token)
        ),
        "anchor_token_count": len(anchor_rows),
        "anchor_token_pct": pct(
            len(anchor_rows),
            sum(1 for token in unit.get("tokens", []) if is_content_token(token)),
        ),
        "high_value_anchor_count": strength_counts["high"],
        "medium_value_anchor_count": strength_counts["medium"],
        "low_value_anchor_count": strength_counts["low"],
        "outside_division_counts": dict(outside_divisions.most_common()),
        "outside_book_counts": dict(outside_books.most_common(12)),
        **flags,
        "has_three_division_evidence": all(flags.values()),
        "domain_ids": cultural.get("domain_ids", []),
        "domain_labels": cultural.get("domain_labels", []),
        "cultural_priority_score": cultural.get("priority_score", 0),
        "claim_risk_score": claim.get("claim_risk_score", 0),
        "boundary_risk_score": reception.get("boundary_risk_score", 0),
        "witness_divergence_priority_score": witness.get("priority_score", 0),
        "ancient_culture_pressure": bool(
            claim.get("ancient_culture_pressure") or reception.get("ancient_culture_pressure")
        ),
        "reception_sensitive": bool(
            claim.get("reception_sensitive") or reception.get("reception_sensitive")
        ),
        "textual_witness_pressure": bool(
            claim.get("textual_witness_pressure") or reception.get("textual_witness_pressure")
        ),
        "divine_name_overlap": bool(divine),
        "superscription_context_overlap": bool(superscription),
        "priority_score": priority,
        "top_anchor_forms": [
            {
                "form": row["normalized"],
                "gloss": row["display_gloss"],
                "outside_psalms_count": row["outside_psalms_count"],
                "anchor_strength": row["anchor_strength"],
                "anchor_score": row["anchor_score"],
            }
            for row in selected_anchors[:MAX_ANCHORS_PER_UNIT]
        ],
        "source_hebrew": unit.get("source_hebrew", ""),
    }


def build_rows(
    form_index: dict[str, dict[str, Any]],
    context: dict[str, dict[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    unit_rows = []
    anchor_rows = []
    unit_count = 0
    content_token_count = 0
    for path in sorted(CONTENT_ROOT.glob("ps*/*.v*.json")):
        unit = load_json(path)
        unit_count += 1
        local_anchor_rows = []
        seen_token_forms: set[tuple[str, str]] = set()
        for token in unit.get("tokens", []):
            if not is_content_token(token):
                continue
            content_token_count += 1
            normalized = normalize_hebrew_form(token.get("surface") or token.get("normalized"))
            entry = form_index.get(normalized)
            if not normalized or not entry or int(entry["outside_psalms_count"]) <= 0:
                continue
            key = (str(token.get("token_id")), normalized)
            if key in seen_token_forms:
                continue
            seen_token_forms.add(key)
            anchor = build_anchor_row(unit, token, entry)
            local_anchor_rows.append(anchor)
            anchor_rows.append(anchor)
        if local_anchor_rows:
            unit_rows.append(build_unit_row(unit, local_anchor_rows, context))
    return unit_rows, anchor_rows, unit_count, content_token_count


def build_division_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for label, key in [
        ("Torah", "has_torah_evidence"),
        ("Prophets", "has_prophets_evidence"),
        ("Non-Psalm Writings", "has_non_psalm_writings_evidence"),
        ("All Three", "has_three_division_evidence"),
    ]:
        selected = [row for row in unit_rows if row[key]]
        rows.append(
            {
                "division_bucket": label,
                "unit_count": len(selected),
                "unit_pct": pct(len(selected), len(unit_rows)),
                "mean_priority_score": mean([float(row["priority_score"]) for row in selected]),
            }
        )
    return rows


def build_book_rows(anchor_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anchor_counts: Counter[str] = Counter()
    occurrence_sums: Counter[str] = Counter()
    units_by_book: dict[str, set[str]] = defaultdict(set)
    for anchor in anchor_rows:
        for book, count in anchor["outside_book_counts"].items():
            anchor_counts[book] += 1
            occurrence_sums[book] += int(count)
            units_by_book[book].add(str(anchor["unit_id"]))
    rows = []
    for book, count in anchor_counts.most_common():
        rows.append(
            {
                "book": book,
                "division": DIVISIONS.get(book, "Unmapped"),
                "anchor_token_count": count,
                "outside_occurrence_sum": occurrence_sums[book],
                "unit_count": len(units_by_book[book]),
            }
        )
    return rows


def build_domain_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    labels: dict[str, str] = {}
    for unit in unit_rows:
        for domain_id, label in zip(unit["domain_ids"], unit["domain_labels"], strict=False):
            grouped[str(domain_id)].append(unit)
            labels[str(domain_id)] = str(label)
    rows = []
    for domain_id, units in grouped.items():
        rows.append(
            {
                "domain_id": domain_id,
                "domain_label": labels.get(domain_id, domain_id),
                "unit_count": len(units),
                "anchor_token_count": sum(int(unit["anchor_token_count"]) for unit in units),
                "three_division_unit_count": sum(
                    1 for unit in units if unit["has_three_division_evidence"]
                ),
                "torah_unit_count": sum(1 for unit in units if unit["has_torah_evidence"]),
                "prophets_unit_count": sum(1 for unit in units if unit["has_prophets_evidence"]),
                "writings_unit_count": sum(
                    1 for unit in units if unit["has_non_psalm_writings_evidence"]
                ),
                "mean_priority_score": mean([float(unit["priority_score"]) for unit in units]),
                "top_ref": max(units, key=lambda unit: float(unit["priority_score"]))["ref"],
            }
        )
    return sorted(rows, key=lambda row: float(row["mean_priority_score"]), reverse=True)


def chart_rows(rows: list[dict[str, Any]], label_key: str, value_key: str) -> list[dict[str, Any]]:
    return [{"label": str(row[label_key]), "value": row[value_key]} for row in rows]


def build_report() -> dict[str, Any]:
    form_index, tanakh_summary = build_tanakh_form_index(UXLC_ZIP_PATH)
    context = load_context_reports()
    unit_rows, anchor_rows, unit_count, content_token_count = build_rows(form_index, context)
    priority_rows = sorted(unit_rows, key=lambda row: float(row["priority_score"]), reverse=True)
    division_rows = build_division_rows(priority_rows)
    book_rows = build_book_rows(anchor_rows)
    domain_rows = build_domain_rows(priority_rows)
    three_division_rows = [row for row in priority_rows if row["has_three_division_evidence"]]
    high_value_rows = [row for row in priority_rows if int(row["high_value_anchor_count"]) > 0]
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "canonical cross-reference atlas generated; surface-form evidence only",
        "source_paths": {
            "uxlc": str(UXLC_ZIP_PATH.relative_to(ROOT)),
            "content_root": "content/psalms",
            "cultural_historical_atlas": str(CULTURAL_ATLAS_PATH.relative_to(ROOT)),
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
            "reception_boundary": str(RECEPTION_BOUNDARY_PATH.relative_to(ROOT)),
        },
        "method": {
            "boundary": (
                "UXLC evidence is normalized surface-form cross-reference evidence. It is "
                "not whole-Tanakh lemma, Strong, morphology, semantic-role, allusion, or "
                "intertextual-dependence proof."
            ),
            "normalization": (
                "NFKD; remove combining marks, Hebrew punctuation, whitespace, and compare "
                "normalized surface forms."
            ),
            "high_value_anchor_rule": (
                f"Outside-Psalms count between 1 and {HIGH_VALUE_OUTSIDE_MAX}, with at least "
                "two major non-Psalm division buckets represented. Medium anchors allow "
                f"up to {MEDIUM_VALUE_OUTSIDE_MAX} outside-Psalms occurrences."
            ),
        },
        "tanakh_source_summary": tanakh_summary,
        "summary": {
            "unit_count": unit_count,
            "content_token_count": content_token_count,
            "cross_reference_unit_count": len(priority_rows),
            "cross_reference_unit_pct": pct(len(priority_rows), unit_count),
            "anchor_token_count": len(anchor_rows),
            "anchor_token_pct": pct(len(anchor_rows), content_token_count),
            "three_division_unit_count": len(three_division_rows),
            "three_division_unit_pct": pct(len(three_division_rows), len(priority_rows)),
            "high_value_anchor_unit_count": len(high_value_rows),
            "torah_evidence_unit_count": sum(
                1 for row in priority_rows if row["has_torah_evidence"]
            ),
            "prophets_evidence_unit_count": sum(
                1 for row in priority_rows if row["has_prophets_evidence"]
            ),
            "non_psalm_writings_evidence_unit_count": sum(
                1 for row in priority_rows if row["has_non_psalm_writings_evidence"]
            ),
            "book_evidence_count": len(book_rows),
            "domain_row_count": len(domain_rows),
            "top_priority_unit": priority_rows[0]["unit_id"] if priority_rows else "",
            "top_priority_ref": priority_rows[0]["ref"] if priority_rows else "",
            "top_priority_score": priority_rows[0]["priority_score"] if priority_rows else 0.0,
            "status": "generated_not_signoff",
        },
        "division_rows": division_rows,
        "book_rows": book_rows,
        "domain_rows": domain_rows,
        "unit_rows": priority_rows,
        "anchor_rows": sorted(
            anchor_rows, key=lambda row: float(row["anchor_score"]), reverse=True
        ),
        "visual_data": {
            "division_unit_counts": chart_rows(division_rows, "division_bucket", "unit_count"),
            "book_anchor_counts": chart_rows(book_rows[:20], "book", "anchor_token_count"),
            "domain_mean_priority": chart_rows(domain_rows, "domain_label", "mean_priority_score"),
            "top_unit_priority": chart_rows(priority_rows[:20], "ref", "priority_score"),
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
    left = 280
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
    division_rows = [
        [
            row["division_bucket"],
            row["unit_count"],
            f"{row['unit_pct']:.2f}%",
            f"{row['mean_priority_score']:.2f}",
        ]
        for row in report["division_rows"]
    ]
    book_rows = [
        [
            row["book"],
            row["division"],
            row["anchor_token_count"],
            row["outside_occurrence_sum"],
            row["unit_count"],
        ]
        for row in report["book_rows"][:30]
    ]
    domain_rows = [
        [
            row["domain_label"],
            row["unit_count"],
            row["anchor_token_count"],
            row["three_division_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["domain_rows"]
    ]
    priority_rows = [
        [
            index + 1,
            row["ref"],
            f"{row['priority_score']:.2f}",
            row["anchor_token_count"],
            row["high_value_anchor_count"],
            row["has_three_division_evidence"],
            "; ".join(row["domain_labels"]),
            row["source_hebrew"],
        ]
        for index, row in enumerate(report["unit_rows"][:35])
    ]
    anchor_rows = [
        [
            row["ref"],
            row["surface"],
            row["display_gloss"],
            row["outside_psalms_count"],
            row["anchor_strength"],
            row["outside_division_counts"],
            row["outside_torah_refs"],
            row["outside_prophets_refs"],
            row["outside_writings_refs"],
        ]
        for row in report["anchor_rows"][:50]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Canonical Cross-Reference Atlas</title>
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
    h1 {{ font-size: 2.12rem; max-width: 1040px; }}
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
      font-size: 0.82rem;
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
  <h1>Canonical Cross-Reference Atlas for Psalm Translation Review</h1>
  <p class="lede">
    This report expands beyond the benchmark units and measures Psalm content
    tokens against the read-only UXLC Tanakh surface-form corpus, with sample
    non-Psalm references by Torah, Prophets, and non-Psalm Writings.
  </p>
  <div class="callout">
    <strong>Authority boundary:</strong> {esc(report["method"]["boundary"])}
  </div>

  {
        metric_cards(
            [
                (
                    "Cross-Ref Units",
                    fmt_int(summary["cross_reference_unit_count"]),
                    f"{fmt_pct(summary['cross_reference_unit_pct'])} of Psalm units.",
                ),
                (
                    "Anchor Tokens",
                    fmt_int(summary["anchor_token_count"]),
                    f"{fmt_pct(summary['anchor_token_pct'])} of content tokens.",
                ),
                (
                    "Three Divisions",
                    fmt_int(summary["three_division_unit_count"]),
                    f"{fmt_pct(summary['three_division_unit_pct'])} of cross-ref units.",
                ),
                (
                    "High-Value Anchors",
                    fmt_int(summary["high_value_anchor_unit_count"]),
                    "Units with rarer multi-division anchors.",
                ),
                (
                    "Books",
                    fmt_int(summary["book_evidence_count"]),
                    "Non-Psalm books touched by anchor forms.",
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
    <h2>Visual Cross-Reference Pressure</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Division Evidence</h3>
        {
        svg_horizontal_bars(
            visual["division_unit_counts"],
            label_key="label",
            value_key="value",
            aria_label="Canonical cross-reference division evidence",
            color="#2f6f73",
        )
    }
      </div>
      <div class="panel">
        <h3>Top Non-Psalm Books</h3>
        {
        svg_horizontal_bars(
            visual["book_anchor_counts"],
            label_key="label",
            value_key="value",
            aria_label="Canonical cross-reference top books",
            color="#7c5b2f",
        )
    }
      </div>
      <div class="panel">
        <h3>Domain Mean Priority</h3>
        {
        svg_horizontal_bars(
            visual["domain_mean_priority"],
            label_key="label",
            value_key="value",
            aria_label="Canonical cross-reference mean priority by domain",
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
            aria_label="Canonical cross-reference top unit priority",
            color="#2f6f73",
        )
    }
      </div>
    </div>
  </section>

  <section>
    <h2>Division Summary</h2>
    {table(["Division Bucket", "Units", "Unit %", "Mean Priority"], division_rows)}
  </section>

  <section>
    <h2>Top Non-Psalm Books</h2>
    {table(["Book", "Division", "Anchor Tokens", "Outside Occurrence Sum", "Units"], book_rows)}
  </section>

  <section>
    <h2>Domain Summary</h2>
    {
        table(
            [
                "Domain",
                "Units",
                "Anchors",
                "Three-Division Units",
                "Mean Priority",
                "Top Ref",
            ],
            domain_rows,
        )
    }
  </section>

  <section>
    <h2>Priority Units</h2>
    {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Anchors",
                "High-Value",
                "Three Divisions",
                "Domains",
                "Hebrew",
            ],
            priority_rows,
        )
    }
  </section>

  <section>
    <h2>Top Anchor Samples</h2>
    {
        table(
            [
                "Ref",
                "Surface",
                "Gloss",
                "Outside Count",
                "Strength",
                "Divisions",
                "Torah Samples",
                "Prophets Samples",
                "Writings Samples",
            ],
            anchor_rows,
        )
    }
  </section>

  <footer>
    Generated {esc(report["generated_at"])} from current local unit JSON and
    read-only UXLC data. No canonical content or data/raw files were modified.
  </footer>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a canonical cross-reference atlas from UXLC surface forms."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--anchor-csv-output", type=Path, default=DEFAULT_ANCHOR_CSV_OUTPUT)
    parser.add_argument("--book-csv-output", type=Path, default=DEFAULT_BOOK_CSV_OUTPUT)
    parser.add_argument("--domain-csv-output", type=Path, default=DEFAULT_DOMAIN_CSV_OUTPUT)
    parser.add_argument("--division-csv-output", type=Path, default=DEFAULT_DIVISION_CSV_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.anchor_csv_output, report["anchor_rows"])
    write_csv(args.book_csv_output, report["book_rows"])
    write_csv(args.domain_csv_output, report["domain_rows"])
    write_csv(args.division_csv_output, report["division_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")


if __name__ == "__main__":
    main()
