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
UXLC_ZIP_PATH = ROOT / "data" / "raw" / "uxlc" / "Tanach.xml.zip"
INTEGRATED_SUITE_PATH = ROOT / "reports" / "research" / "integrated_benchmark_suite.json"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "lexeme_context_readiness.json"
DEFAULT_LEXEME_CSV_OUTPUT = ROOT / "reports" / "research" / "lexeme_context_readiness.csv"
DEFAULT_UNIT_CSV_OUTPUT = ROOT / "reports" / "research" / "benchmark_lexeme_context_readiness.csv"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "lexeme_context_readiness.html"

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

FIELD_LABELS = [
    ("strong", "Strong"),
    ("lemma", "Lemma"),
    ("morph_code", "Morph code"),
    ("part_of_speech", "Part of speech"),
    ("word_sense", "Word sense"),
    ("syntax_role", "Syntax role"),
    ("greek", "Greek witness"),
    ("greek_strong", "Greek Strong"),
    ("stem", "Verbal stem"),
    ("semantic_role", "Semantic role"),
    ("referent", "Referent"),
]

PUNCTUATION = {
    "\u05be",
    "\u05c0",
    "\u05c3",
    "\u05c6",
    " ",
    "\t",
    "\n",
}

HIGH_RISK_TAGS = {
    "reception_history",
    "jewish_christian_reception",
    "messianic_interpretation",
    "textual_witness",
    "lexical_dispute",
    "imprecation",
    "violence",
    "divine_name_policy",
    "anthropology",
    "hesed",
}


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


def has_value(value: Any) -> bool:
    return value not in (None, "", [], {})


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


def add_sample(samples: list[str], value: str, limit: int = 10) -> None:
    if value and value not in samples and len(samples) < limit:
        samples.append(value)


def build_tanakh_form_index(zip_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    form_index: dict[str, dict[str, Any]] = {}
    book_rows = []
    division_totals: Counter[str] = Counter()
    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(name for name in archive.namelist() if canonical_book_file(name))
        for name in names:
            root = ET.fromstring(archive.read(name))
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
                                "outside_sample_refs": [],
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
        entry["book_counts"] = dict(entry["book_counts"].most_common(12))
    summary = {
        "book_count": len(book_rows),
        "tanakh_word_elements": sum(row["word_elements"] for row in book_rows),
        "tanakh_distinct_forms": len(form_index),
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


def token_field(token: dict[str, Any], field: str) -> Any:
    return token.get(field)


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
                "word_sense": token.get("word_sense", ""),
                "syntax_role": token.get("syntax_role", ""),
                "semantic_role": token.get("semantic_role", ""),
                "referent": token.get("referent", ""),
                "stem": token.get("stem", ""),
                "greek": token.get("greek", ""),
                "greek_strong": token.get("greek_strong", ""),
                "surface_tanakh_count": surface_entry.get("tanakh_count", 0),
                "surface_outside_psalms_count": surface_entry.get(
                    "outside_psalms_count",
                    0,
                ),
                "lemma_form_tanakh_count": lemma_entry.get("tanakh_count", 0),
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


def load_benchmark_unit_tags(path: Path) -> dict[str, dict[str, Any]]:
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
                "ref": task["ref"],
                "layers": set(),
                "benchmark_tags": Counter(),
                "task_count": 0,
            },
        )
        row["layers"].add(str(task["layer"]))
        row["benchmark_tags"].update(str(tag) for tag in task.get("benchmark_tags", []))
        row["task_count"] += 1
    for row in rows.values():
        row["layers"] = sorted(row["layers"])
        row["benchmark_tags"] = dict(row["benchmark_tags"].most_common())
    return rows


def coverage_rows(token_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(token_rows)
    rows = []
    for field, label in FIELD_LABELS:
        count = sum(1 for token in token_rows if has_value(token_field(token, field)))
        rows.append(
            {
                "field": field,
                "label": label,
                "present_count": count,
                "missing_count": total - count,
                "coverage_pct": pct(count, total),
            }
        )
    return rows


def source_gate_rows(
    token_rows: list[dict[str, Any]],
    tanakh_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    total = len(token_rows)
    strong_count = sum(1 for token in token_rows if has_value(token["strong"]))
    lemma_count = sum(1 for token in token_rows if has_value(token["lemma"]))
    outside_count = sum(1 for token in token_rows if int(token["surface_outside_psalms_count"]) > 0)
    semantic_count = sum(1 for token in token_rows if has_value(token["semantic_role"]))
    referent_count = sum(1 for token in token_rows if has_value(token["referent"]))
    return [
        {
            "gate": "Whole-Tanakh Hebrew text",
            "status": "pass",
            "evidence": (
                f"{tanakh_summary['book_count']} canonical UXLC book files; "
                f"{tanakh_summary['tanakh_word_elements']} word elements."
            ),
        },
        {
            "gate": "Psalm token lemma/Strong enrichment",
            "status": "pass",
            "evidence": (
                f"{strong_count} of {total} Psalm tokens have Strong IDs; "
                f"{lemma_count} have lemmas."
            ),
        },
        {
            "gate": "Outside-Psalms form bridge",
            "status": "prototype",
            "evidence": (
                f"{outside_count} of {total} Psalm tokens have normalized surface "
                "forms attested outside Psalms."
            ),
        },
        {
            "gate": "Whole-Tanakh lemma/Strong index",
            "status": "missing",
            "evidence": "Current OSHB and MACULA manifests are Psalm-scoped enrichment.",
        },
        {
            "gate": "Semantic-role and referent enrichment",
            "status": "missing",
            "evidence": (
                f"{semantic_count} semantic-role values and {referent_count} "
                f"referent values are present across {total} Psalm tokens."
            ),
        },
    ]


def aggregate_lexeme_rows(
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
        lemma_counts = Counter(str(token["lemma"]) for token in tokens if token["lemma"])
        form_counts = Counter(str(token["normalized"]) for token in tokens if token["normalized"])
        gloss_counts = Counter(
            str(token["display_gloss"]) for token in tokens if token["display_gloss"]
        )
        tokens_by_form = {
            str(token["normalized"]): token for token in tokens if token["normalized"]
        }
        outside_total = sum(
            int(token["surface_outside_psalms_count"])
            for form, token in tokens_by_form.items()
            if form
        )
        outside_token_count = sum(
            1 for token in tokens if int(token["surface_outside_psalms_count"]) > 0
        )
        outside_divisions: Counter[str] = Counter()
        for token in tokens_by_form.values():
            outside_divisions.update(token["outside_division_counts"])
        unit_ids = {str(token["unit_id"]) for token in tokens}
        benchmark_unit_ids = sorted(unit_id for unit_id in unit_ids if unit_id in benchmark_units)
        tag_counts: Counter[str] = Counter()
        for unit_id in benchmark_unit_ids:
            tag_counts.update(benchmark_units[unit_id]["benchmark_tags"])
        high_risk_tag_count = sum(
            count for tag, count in tag_counts.items() if tag in HIGH_RISK_TAGS
        )
        semantic_count = sum(1 for token in tokens if has_value(token["semantic_role"]))
        referent_count = sum(1 for token in tokens if has_value(token["referent"]))
        bridge_status = "usable form bridge; not lemma proof"
        if outside_total == 0:
            bridge_status = "no outside-Psalms surface evidence"
        elif len(form_counts) > 8 or len(lemma_counts) > 3:
            bridge_status = "ambiguous multi-form bridge"
        pressure_score = round(
            len(tokens)
            + min(outside_total, 2000) / 25
            + len(benchmark_unit_ids) * 4
            + high_risk_tag_count * 2,
            2,
        )
        rows.append(
            {
                "strong": strong,
                "token_count": len(tokens),
                "unit_count": len(unit_ids),
                "benchmark_unit_count": len(benchmark_unit_ids),
                "lemma_samples": dict(lemma_counts.most_common(5)),
                "normalized_form_count": len(form_counts),
                "normalized_form_samples": dict(form_counts.most_common(6)),
                "display_gloss_samples": dict(gloss_counts.most_common(6)),
                "tokens_with_outside_form_context": outside_token_count,
                "outside_form_context_pct": pct(outside_token_count, len(tokens)),
                "outside_form_occurrence_evidence": outside_total,
                "outside_context_division_counts": dict(outside_divisions.most_common()),
                "semantic_role_coverage_pct": pct(semantic_count, len(tokens)),
                "referent_coverage_pct": pct(referent_count, len(tokens)),
                "benchmark_tags": dict(tag_counts.most_common(12)),
                "bridge_status": bridge_status,
                "context_pressure_score": pressure_score,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            float(row["context_pressure_score"]),
            int(row["token_count"]),
            str(row["strong"]),
        ),
        reverse=True,
    )


def benchmark_unit_rows(
    unit_tokens: dict[str, list[dict[str, Any]]],
    benchmark_units: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for unit_id, benchmark in sorted(benchmark_units.items()):
        tokens = unit_tokens.get(unit_id, [])
        total = len(tokens)
        strong_count = sum(1 for token in tokens if has_value(token["strong"]))
        lemma_count = sum(1 for token in tokens if has_value(token["lemma"]))
        outside_count = sum(1 for token in tokens if int(token["surface_outside_psalms_count"]) > 0)
        semantic_count = sum(1 for token in tokens if has_value(token["semantic_role"]))
        referent_count = sum(1 for token in tokens if has_value(token["referent"]))
        tags = benchmark["benchmark_tags"]
        high_risk_tags = sorted(tag for tag in tags if tag in HIGH_RISK_TAGS)
        risk_score = round(
            (100 - pct(outside_count, total))
            + (100 - pct(semantic_count, total)) / 4
            + (100 - pct(referent_count, total)) / 4
            + len(high_risk_tags) * 8,
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
                "outside_form_context_pct": pct(outside_count, total),
                "semantic_role_coverage_pct": pct(semantic_count, total),
                "referent_coverage_pct": pct(referent_count, total),
                "high_risk_tags": high_risk_tags,
                "benchmark_tags": tags,
                "readiness_status": (
                    "form-bridge only; needs whole-Tanakh morphology"
                    if total
                    else "missing unit tokens"
                ),
                "lexeme_context_risk_score": risk_score,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            float(row["lexeme_context_risk_score"]),
            str(row["unit_id"]),
        ),
        reverse=True,
    )


def summarize(
    token_rows: list[dict[str, Any]],
    lexeme_rows: list[dict[str, Any]],
    unit_rows: list[dict[str, Any]],
    tanakh_summary: dict[str, Any],
) -> dict[str, Any]:
    total = len(token_rows)
    unit_ids = {str(token["unit_id"]) for token in token_rows}
    psalm_ids = {str(token["unit_id"]).split(".")[0] for token in token_rows}
    strong_count = sum(1 for token in token_rows if has_value(token["strong"]))
    lemma_count = sum(1 for token in token_rows if has_value(token["lemma"]))
    outside_count = sum(1 for token in token_rows if int(token["surface_outside_psalms_count"]) > 0)
    lemma_form_outside_count = sum(
        1 for token in token_rows if int(token["lemma_form_outside_psalms_count"]) > 0
    )
    semantic_count = sum(1 for token in token_rows if has_value(token["semantic_role"]))
    referent_count = sum(1 for token in token_rows if has_value(token["referent"]))
    benchmark_high_risk = sum(1 for row in unit_rows if row["high_risk_tags"])
    return {
        "psalm_count": len(psalm_ids),
        "unit_count": len(unit_ids),
        "token_count": total,
        "distinct_strong_keys": len({token["strong"] for token in token_rows if token["strong"]}),
        "distinct_lemmas": len({token["lemma"] for token in token_rows if token["lemma"]}),
        "distinct_normalized_forms": len(
            {token["normalized"] for token in token_rows if token["normalized"]}
        ),
        "strong_coverage_pct": pct(strong_count, total),
        "lemma_coverage_pct": pct(lemma_count, total),
        "surface_outside_context_token_pct": pct(outside_count, total),
        "lemma_form_outside_context_token_pct": pct(lemma_form_outside_count, total),
        "semantic_role_coverage_pct": pct(semantic_count, total),
        "referent_coverage_pct": pct(referent_count, total),
        "tanakh_book_count": tanakh_summary["book_count"],
        "tanakh_word_elements": tanakh_summary["tanakh_word_elements"],
        "tanakh_distinct_forms": tanakh_summary["tanakh_distinct_forms"],
        "lexeme_row_count": len(lexeme_rows),
        "benchmark_unit_count": len(unit_rows),
        "benchmark_units_with_high_risk_tags": benchmark_high_risk,
        "whole_tanakh_lemma_index_available": False,
    }


def build_report(
    content_root: Path,
    uxlc_zip_path: Path,
    integrated_suite_path: Path,
) -> dict[str, Any]:
    form_index, tanakh_summary = build_tanakh_form_index(uxlc_zip_path)
    token_rows, unit_tokens = scan_psalm_tokens(content_root, form_index)
    benchmark_units = load_benchmark_unit_tags(integrated_suite_path)
    lexeme_rows = aggregate_lexeme_rows(token_rows, benchmark_units)
    unit_rows = benchmark_unit_rows(unit_tokens, benchmark_units)
    source_gates = source_gate_rows(token_rows, tanakh_summary)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated lexeme context readiness audit; form bridge is not lemma proof",
        "source_paths": {
            "content_root": "content/psalms",
            "uxlc_zip": "data/raw/uxlc/Tanach.xml.zip",
            "integrated_suite": "reports/research/integrated_benchmark_suite.json",
            "oshb_manifest": "data/raw/oshb/manifest.json",
            "macula_manifest": "data/raw/macula/manifest.json",
        },
        "normalization": {
            "method": "NFKD; remove combining marks, Hebrew punctuation, and whitespace",
            "warning": (
                "Whole-Tanakh counts are normalized surface-form evidence. "
                "They do not prove lemma identity, sense identity, or syntax."
            ),
        },
        "summary": summarize(token_rows, lexeme_rows, unit_rows, tanakh_summary),
        "source_gates": source_gates,
        "field_coverage": coverage_rows(token_rows),
        "tanakh_source_summary": tanakh_summary,
        "top_lexeme_context_rows": lexeme_rows[:100],
        "benchmark_unit_rows": unit_rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def flatten_lexeme_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for row in rows:
        flattened.append(
            {
                "strong": row["strong"],
                "token_count": row["token_count"],
                "unit_count": row["unit_count"],
                "benchmark_unit_count": row["benchmark_unit_count"],
                "lemma_samples": "; ".join(row["lemma_samples"].keys()),
                "normalized_form_count": row["normalized_form_count"],
                "tokens_with_outside_form_context": row["tokens_with_outside_form_context"],
                "outside_form_context_pct": row["outside_form_context_pct"],
                "outside_form_occurrence_evidence": row["outside_form_occurrence_evidence"],
                "bridge_status": row["bridge_status"],
                "context_pressure_score": row["context_pressure_score"],
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
                "outside_form_context_pct": row["outside_form_context_pct"],
                "semantic_role_coverage_pct": row["semantic_role_coverage_pct"],
                "referent_coverage_pct": row["referent_coverage_pct"],
                "high_risk_tags": "; ".join(row["high_risk_tags"]),
                "readiness_status": row["readiness_status"],
                "lexeme_context_risk_score": row["lexeme_context_risk_score"],
            }
        )
    return flattened


def rows_for_bar(
    rows: list[dict[str, Any]],
    label_key: str,
    value_key: str,
) -> list[dict[str, Any]]:
    return [{"label": row[label_key], "value": row[value_key]} for row in rows]


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
    left = 280
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
            f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row[label_key])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="18" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 18}" font-size="12" '
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
    field_rows = rows_for_bar(report["field_coverage"], "label", "coverage_pct")
    lexeme_chart_rows = [
        {
            "strong": f"{row['strong']} {'/'.join(row['lemma_samples'].keys())}",
            "score": row["context_pressure_score"],
        }
        for row in report["top_lexeme_context_rows"][:20]
    ]
    unit_chart_rows = [
        {
            "unit": f"{row['unit_id']} {row['ref']}",
            "risk": row["lexeme_context_risk_score"],
        }
        for row in report["benchmark_unit_rows"][:20]
    ]
    gate_rows = [[row["gate"], row["status"], row["evidence"]] for row in report["source_gates"]]
    top_lexeme_rows = [
        [
            row["strong"],
            "; ".join(row["lemma_samples"].keys()),
            row["token_count"],
            row["outside_form_context_pct"],
            row["outside_form_occurrence_evidence"],
            row["bridge_status"],
        ]
        for row in report["top_lexeme_context_rows"][:30]
    ]
    unit_rows = [
        [
            row["unit_id"],
            row["ref"],
            row["outside_form_context_pct"],
            row["semantic_role_coverage_pct"],
            ", ".join(row["high_risk_tags"]),
            row["readiness_status"],
        ]
        for row in report["benchmark_unit_rows"][:30]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Lexeme Context Readiness</title>
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
    <h1>AlephTav Lexeme Context Readiness</h1>
    <p class="lede">
      Hard-data audit of the current lexical evidence boundary. Psalm tokens
      have lemma and Strong enrichment, and UXLC supplies whole-Tanakh Hebrew
      surface forms. The current project still lacks a whole-Tanakh morphology
      index, so outside-Psalms context remains a form bridge rather than
      lemma/sense proof.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Readiness Snapshot</h2>
      {
        metric_cards(
            [
                (
                    "Psalm tokens",
                    fmt_int(summary["token_count"]),
                    (
                        f'''{fmt_int(summary["unit_count"])} units across '''
                        f'''{summary["psalm_count"]} Psalms.'''
                    ),
                ),
                (
                    "Strong coverage",
                    f'''{summary["strong_coverage_pct"]:.2f}%''',
                    f'''{fmt_int(summary["distinct_strong_keys"])} distinct Strong keys.''',
                ),
                (
                    "Lemma coverage",
                    f'''{summary["lemma_coverage_pct"]:.2f}%''',
                    f'''{fmt_int(summary["distinct_lemmas"])} distinct lemma strings.''',
                ),
                (
                    "Outside forms",
                    f'''{summary["surface_outside_context_token_pct"]:.2f}%''',
                    "Psalm tokens with outside-Psalms surface-form evidence.",
                ),
                (
                    "Tanakh words",
                    fmt_int(summary["tanakh_word_elements"]),
                    f'''{summary["tanakh_book_count"]} canonical UXLC book files.''',
                ),
                (
                    "Integrated units",
                    fmt_int(summary["benchmark_unit_count"]),
                    (
                        f'''{fmt_int(summary["benchmark_units_with_high_risk_tags"])} '''
                        "carry high-risk benchmark tags."
                    ),
                ),
                (
                    "Semantic roles",
                    f'''{summary["semantic_role_coverage_pct"]:.2f}%''',
                    "Current MACULA semantic-role coverage in Psalm tokens.",
                ),
                (
                    "Whole-Tanakh lemma",
                    "0",
                    "No current whole-Tanakh morphology/Strong index is vendored.",
                ),
            ]
        )
    }
      <div class="warning">
        This report intentionally separates form evidence from lexeme authority.
        A model may cite outside-Psalms forms as context, but should not claim
        whole-Tanakh lemma or sense support until a full morphology index exists.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            field_rows,
            label_key="label",
            value_key="value",
            aria_label="Psalm token lexical field coverage",
            color="#2f6f73",
            limit=12,
        )
    }</div>
    </section>

    <section>
      <h2>Source Gates</h2>
      {table(["Gate", "Status", "Evidence"], gate_rows)}
    </section>

    <section>
      <h2>Lexeme Pressure</h2>
      <div class="chart">{
        svg_horizontal_bars(
            lexeme_chart_rows,
            label_key="strong",
            value_key="score",
            aria_label="Top Strong-key context pressure scores",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Strong",
                "Lemma samples",
                "Psalm tokens",
                "Outside-form %",
                "Outside-form evidence",
                "Bridge status",
            ],
            top_lexeme_rows,
        )
    }
    </section>

    <section>
      <h2>Integrated Benchmark Units</h2>
      <div class="chart">{
        svg_horizontal_bars(
            unit_chart_rows,
            label_key="unit",
            value_key="risk",
            aria_label="Integrated benchmark lexeme-context risk scores",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            [
                "Unit",
                "Reference",
                "Outside-form %",
                "Semantic-role %",
                "High-risk tags",
                "Readiness",
            ],
            unit_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Psalm lexeme and whole-Tanakh context readiness report."
    )
    parser.add_argument("--content-root", type=Path, default=CONTENT_ROOT)
    parser.add_argument("--uxlc-zip", type=Path, default=UXLC_ZIP_PATH)
    parser.add_argument("--suite", type=Path, default=INTEGRATED_SUITE_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--lexeme-csv-output", type=Path, default=DEFAULT_LEXEME_CSV_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.content_root, args.uxlc_zip, args.suite)
    write_json(args.json_output, report)
    write_csv(
        args.lexeme_csv_output,
        flatten_lexeme_rows(report["top_lexeme_context_rows"]),
    )
    write_csv(args.unit_csv_output, flatten_unit_rows(report["benchmark_unit_rows"]))
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.lexeme_csv_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
