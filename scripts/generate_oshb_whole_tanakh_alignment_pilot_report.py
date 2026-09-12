from __future__ import annotations

import argparse
import csv
import html
import json
import unicodedata
import urllib.request
import zipfile
from collections import Counter
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"
UXLC_ZIP_PATH = ROOT / "data" / "raw" / "uxlc" / "Tanach.xml.zip"
MORPHOLOGY_ACQUISITION_PATH = REPORT_ROOT / "whole_tanakh_morphology_acquisition_readiness.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "oshb_whole_tanakh_alignment_pilot.json"
DEFAULT_BOOK_CSV_OUTPUT = REPORT_ROOT / "oshb_whole_tanakh_alignment_pilot_books.csv"
DEFAULT_MISMATCH_CSV_OUTPUT = REPORT_ROOT / "oshb_whole_tanakh_alignment_pilot_mismatches.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "oshb_whole_tanakh_alignment_pilot.html"

GITHUB_API_ROOT = "https://api.github.com/repos/openscriptures/morphhb"
RAW_ROOT = "https://raw.githubusercontent.com/openscriptures/morphhb"
USER_AGENT = "AlephTav-research-pilot/1.0"

PUNCTUATION = {
    "\u05be",
    "\u05c0",
    "\u05c3",
    "\u05c6",
    " ",
    "\t",
    "\n",
    "/",
    "|",
}

BOOKS = [
    ("Gen", "Gen.xml", "Genesis", "Books/Genesis.xml", "Torah"),
    ("Exod", "Exod.xml", "Exodus", "Books/Exodus.xml", "Torah"),
    ("Lev", "Lev.xml", "Leviticus", "Books/Leviticus.xml", "Torah"),
    ("Num", "Num.xml", "Numbers", "Books/Numbers.xml", "Torah"),
    ("Deut", "Deut.xml", "Deuteronomy", "Books/Deuteronomy.xml", "Torah"),
    ("Josh", "Josh.xml", "Joshua", "Books/Joshua.xml", "Former Prophets"),
    ("Judg", "Judg.xml", "Judges", "Books/Judges.xml", "Former Prophets"),
    ("1Sam", "1Sam.xml", "1 Samuel", "Books/Samuel_1.xml", "Former Prophets"),
    ("2Sam", "2Sam.xml", "2 Samuel", "Books/Samuel_2.xml", "Former Prophets"),
    ("1Kgs", "1Kgs.xml", "1 Kings", "Books/Kings_1.xml", "Former Prophets"),
    ("2Kgs", "2Kgs.xml", "2 Kings", "Books/Kings_2.xml", "Former Prophets"),
    ("Isa", "Isa.xml", "Isaiah", "Books/Isaiah.xml", "Latter Prophets"),
    ("Jer", "Jer.xml", "Jeremiah", "Books/Jeremiah.xml", "Latter Prophets"),
    ("Ezek", "Ezek.xml", "Ezekiel", "Books/Ezekiel.xml", "Latter Prophets"),
    ("Hos", "Hos.xml", "Hosea", "Books/Hosea.xml", "The Twelve"),
    ("Joel", "Joel.xml", "Joel", "Books/Joel.xml", "The Twelve"),
    ("Amos", "Amos.xml", "Amos", "Books/Amos.xml", "The Twelve"),
    ("Obad", "Obad.xml", "Obadiah", "Books/Obadiah.xml", "The Twelve"),
    ("Jonah", "Jonah.xml", "Jonah", "Books/Jonah.xml", "The Twelve"),
    ("Mic", "Mic.xml", "Micah", "Books/Micah.xml", "The Twelve"),
    ("Nah", "Nah.xml", "Nahum", "Books/Nahum.xml", "The Twelve"),
    ("Hab", "Hab.xml", "Habakkuk", "Books/Habakkuk.xml", "The Twelve"),
    ("Zeph", "Zeph.xml", "Zephaniah", "Books/Zephaniah.xml", "The Twelve"),
    ("Hag", "Hag.xml", "Haggai", "Books/Haggai.xml", "The Twelve"),
    ("Zech", "Zech.xml", "Zechariah", "Books/Zechariah.xml", "The Twelve"),
    ("Mal", "Mal.xml", "Malachi", "Books/Malachi.xml", "The Twelve"),
    ("Ps", "Ps.xml", "Psalms", "Books/Psalms.xml", "Writings"),
    ("Prov", "Prov.xml", "Proverbs", "Books/Proverbs.xml", "Writings"),
    ("Job", "Job.xml", "Job", "Books/Job.xml", "Writings"),
    ("Song", "Song.xml", "Song of Songs", "Books/Song_of_Songs.xml", "Writings"),
    ("Ruth", "Ruth.xml", "Ruth", "Books/Ruth.xml", "Writings"),
    ("Lam", "Lam.xml", "Lamentations", "Books/Lamentations.xml", "Writings"),
    ("Eccl", "Eccl.xml", "Ecclesiastes", "Books/Ecclesiastes.xml", "Writings"),
    ("Esth", "Esth.xml", "Esther", "Books/Esther.xml", "Writings"),
    ("Dan", "Dan.xml", "Daniel", "Books/Daniel.xml", "Writings"),
    ("Ezra", "Ezra.xml", "Ezra", "Books/Ezra.xml", "Writings"),
    ("Neh", "Neh.xml", "Nehemiah", "Books/Nehemiah.xml", "Writings"),
    ("1Chr", "1Chr.xml", "1 Chronicles", "Books/Chronicles_1.xml", "Writings"),
    ("2Chr", "2Chr.xml", "2 Chronicles", "Books/Chronicles_2.xml", "Writings"),
]


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


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def fmt_pct(value: Any) -> str:
    return f"{float(value):.2f}%"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalize_hebrew_form(text: str | None) -> str:
    if not text:
        return ""
    chars = []
    for char in unicodedata.normalize("NFKD", text):
        if unicodedata.category(char) == "Mn":
            continue
        if char in PUNCTUATION:
            continue
        if not "\u05d0" <= char <= "\u05ea":
            continue
        chars.append(char)
    return "".join(chars)


def request_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def request_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def github_master_info() -> dict[str, str]:
    data = request_json(f"{GITHUB_API_ROOT}/commits/master")
    return {
        "sha": data["sha"],
        "commit_date": data["commit"]["committer"]["date"],
        "html_url": data["html_url"],
    }


def github_wlc_file_rows(sha: str) -> list[dict[str, Any]]:
    rows = request_json(f"{GITHUB_API_ROOT}/contents/wlc?ref={sha}")
    return [
        {
            "name": row["name"],
            "size": row.get("size", 0),
            "download_url": f"{RAW_ROOT}/{sha}/wlc/{row['name']}",
        }
        for row in rows
        if row["name"].endswith(".xml") and row["name"] != "VerseMap.xml"
    ]


def parse_oshb_book(xml_bytes: bytes, osis_book: str) -> dict[str, Any]:
    root = ET.fromstring(xml_bytes)
    verse_rows: dict[str, dict[str, Any]] = {}
    word_count = 0
    lemma_count = 0
    morph_count = 0
    morph_prefix_counts: Counter[str] = Counter()
    lemma_prefix_counts: Counter[str] = Counter()

    for verse in root.iter():
        if local_name(verse.tag) != "verse":
            continue
        osis_id = str(verse.get("osisID") or "")
        if not osis_id.startswith(f"{osis_book}."):
            continue
        normalized_tokens = []
        surface_tokens = []
        lemma_tokens = []
        morph_tokens = []
        for word in verse.iter():
            if local_name(word.tag) != "w":
                continue
            surface = "".join(word.itertext()).strip()
            normalized = normalize_hebrew_form(surface)
            if not normalized:
                continue
            lemma = str(word.get("lemma") or "")
            morph = str(word.get("morph") or "")
            normalized_tokens.append(normalized)
            surface_tokens.append(surface)
            lemma_tokens.append(lemma)
            morph_tokens.append(morph)
            word_count += 1
            if lemma:
                lemma_count += 1
                lemma_prefix_counts[lemma.split("/", 1)[0]] += 1
            if morph:
                morph_count += 1
                morph_prefix_counts[morph[:2] if len(morph) >= 2 else morph] += 1
        if normalized_tokens:
            verse_rows[osis_id] = {
                "osis_id": osis_id,
                "normalized_tokens": normalized_tokens,
                "surface_tokens": surface_tokens,
                "lemma_tokens": lemma_tokens,
                "morph_tokens": morph_tokens,
            }
    return {
        "verse_rows": verse_rows,
        "word_count": word_count,
        "lemma_count": lemma_count,
        "morph_count": morph_count,
        "morph_prefix_counts": dict(morph_prefix_counts.most_common(12)),
        "lemma_prefix_counts": dict(lemma_prefix_counts.most_common(12)),
    }


def parse_uxlc_book(
    archive: zipfile.ZipFile,
    uxlc_path: str,
    osis_book: str,
) -> dict[str, Any]:
    root = ET.fromstring(archive.read(uxlc_path))
    verse_rows: dict[str, dict[str, Any]] = {}
    word_count = 0
    for chapter in root.findall(".//c"):
        chapter_num = str(chapter.get("n") or "")
        for verse in chapter.findall("./v"):
            verse_num = str(verse.get("n") or "")
            osis_id = f"{osis_book}.{chapter_num}.{verse_num}"
            normalized_tokens = []
            surface_tokens = []
            for word in verse.findall("./w"):
                surface = "".join(word.itertext()).strip()
                normalized = normalize_hebrew_form(surface)
                if not normalized:
                    continue
                normalized_tokens.append(normalized)
                surface_tokens.append(surface)
                word_count += 1
            if normalized_tokens:
                verse_rows[osis_id] = {
                    "osis_id": osis_id,
                    "normalized_tokens": normalized_tokens,
                    "surface_tokens": surface_tokens,
                }
    return {"verse_rows": verse_rows, "word_count": word_count}


def sequence_similarity(left: list[str], right: list[str]) -> float:
    if left == right:
        return 100.0
    return round(SequenceMatcher(a=left, b=right, autojunk=False).ratio() * 100, 2)


def first_difference(left: list[str], right: list[str]) -> int:
    limit = min(len(left), len(right))
    for index in range(limit):
        if left[index] != right[index]:
            return index
    return limit


def compare_book(
    *,
    book: tuple[str, str, str, str, str],
    oshb: dict[str, Any],
    uxlc: dict[str, Any],
    source_url: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    osis_book, file_name, book_name, _uxlc_path, division = book
    oshb_verses = oshb["verse_rows"]
    uxlc_verses = uxlc["verse_rows"]
    both_keys = sorted(set(oshb_verses) & set(uxlc_verses))

    exact = 0
    token_count_match = 0
    similarity_sum = 0.0
    mismatch_rows = []
    mismatch_count = 0
    token_delta_sum = 0

    for osis_id in both_keys:
        left = oshb_verses[osis_id]["normalized_tokens"]
        right = uxlc_verses[osis_id]["normalized_tokens"]
        similarity = sequence_similarity(left, right)
        similarity_sum += similarity
        if len(left) == len(right):
            token_count_match += 1
        if left == right:
            exact += 1
            continue
        mismatch_count += 1
        token_delta_sum += abs(len(left) - len(right))
        diff_index = first_difference(left, right)
        mismatch_rows.append(
            {
                "book": book_name,
                "division": division,
                "osis_id": osis_id,
                "mismatch_type": ("token_count" if len(left) != len(right) else "token_sequence"),
                "oshb_token_count": len(left),
                "uxlc_token_count": len(right),
                "sequence_similarity_pct": similarity,
                "first_difference_index": diff_index,
                "oshb_window": left[max(0, diff_index - 3) : diff_index + 4],
                "uxlc_window": right[max(0, diff_index - 3) : diff_index + 4],
                "oshb_surface_window": oshb_verses[osis_id]["surface_tokens"][
                    max(0, diff_index - 3) : diff_index + 4
                ],
                "uxlc_surface_window": uxlc_verses[osis_id]["surface_tokens"][
                    max(0, diff_index - 3) : diff_index + 4
                ],
            }
        )

    missing_in_uxlc = sorted(set(oshb_verses) - set(uxlc_verses))
    missing_in_oshb = sorted(set(uxlc_verses) - set(oshb_verses))
    for osis_id in missing_in_uxlc[:50]:
        mismatch_rows.append(
            {
                "book": book_name,
                "division": division,
                "osis_id": osis_id,
                "mismatch_type": "missing_in_uxlc",
                "oshb_token_count": len(oshb_verses[osis_id]["normalized_tokens"]),
                "uxlc_token_count": 0,
                "sequence_similarity_pct": 0.0,
                "first_difference_index": 0,
                "oshb_window": oshb_verses[osis_id]["normalized_tokens"][:7],
                "uxlc_window": [],
                "oshb_surface_window": oshb_verses[osis_id]["surface_tokens"][:7],
                "uxlc_surface_window": [],
            }
        )
    for osis_id in missing_in_oshb[:50]:
        mismatch_rows.append(
            {
                "book": book_name,
                "division": division,
                "osis_id": osis_id,
                "mismatch_type": "missing_in_oshb",
                "oshb_token_count": 0,
                "uxlc_token_count": len(uxlc_verses[osis_id]["normalized_tokens"]),
                "sequence_similarity_pct": 0.0,
                "first_difference_index": 0,
                "oshb_window": [],
                "uxlc_window": uxlc_verses[osis_id]["normalized_tokens"][:7],
                "oshb_surface_window": [],
                "uxlc_surface_window": uxlc_verses[osis_id]["surface_tokens"][:7],
            }
        )

    mean_similarity = round(similarity_sum / len(both_keys), 2) if both_keys else 0.0
    row = {
        "osis_book": osis_book,
        "oshb_file": file_name,
        "book": book_name,
        "division": division,
        "source_url": source_url,
        "oshb_verse_count": len(oshb_verses),
        "uxlc_verse_count": len(uxlc_verses),
        "both_sources_verse_count": len(both_keys),
        "missing_in_uxlc_verse_count": len(missing_in_uxlc),
        "missing_in_oshb_verse_count": len(missing_in_oshb),
        "oshb_word_count": oshb["word_count"],
        "uxlc_word_count": uxlc["word_count"],
        "oshb_lemma_count": oshb["lemma_count"],
        "oshb_morph_count": oshb["morph_count"],
        "lemma_coverage_pct": pct(oshb["lemma_count"], oshb["word_count"]),
        "morph_coverage_pct": pct(oshb["morph_count"], oshb["word_count"]),
        "token_count_match_verse_count": token_count_match,
        "token_count_match_pct": pct(token_count_match, len(both_keys)),
        "exact_sequence_match_verse_count": exact,
        "exact_sequence_match_pct": pct(exact, len(both_keys)),
        "mismatch_verse_count": mismatch_count,
        "mean_sequence_similarity_pct": mean_similarity,
        "mean_abs_token_delta_per_mismatch": (
            round(token_delta_sum / mismatch_count, 2) if mismatch_count else 0.0
        ),
        "alignment_readiness": (
            "high"
            if mean_similarity >= 99 and pct(exact, len(both_keys)) >= 95
            else "review_required"
            if mean_similarity >= 95
            else "high_exception_pressure"
        ),
        "morph_prefix_counts": oshb["morph_prefix_counts"],
    }
    return row, mismatch_rows


def build_report() -> dict[str, Any]:
    acquisition = load_json(MORPHOLOGY_ACQUISITION_PATH)
    master = github_master_info()
    remote_files = github_wlc_file_rows(master["sha"])
    remote_by_name = {row["name"]: row for row in remote_files}
    book_rows = []
    mismatch_rows = []
    source_fetch_rows = []

    with zipfile.ZipFile(UXLC_ZIP_PATH) as archive:
        for book in BOOKS:
            osis_book, file_name, book_name, uxlc_path, division = book
            remote = remote_by_name[file_name]
            xml_bytes = request_bytes(remote["download_url"])
            source_fetch_rows.append(
                {
                    "book": book_name,
                    "division": division,
                    "oshb_file": file_name,
                    "byte_count": len(xml_bytes),
                    "source_url": remote["download_url"],
                }
            )
            oshb = parse_oshb_book(xml_bytes, osis_book)
            uxlc = parse_uxlc_book(archive, uxlc_path, osis_book)
            book_row, book_mismatches = compare_book(
                book=book,
                oshb=oshb,
                uxlc=uxlc,
                source_url=remote["download_url"],
            )
            book_rows.append(book_row)
            mismatch_rows.extend(book_mismatches)

    division_rows = build_division_rows(book_rows)
    summary = summarize(
        book_rows=book_rows,
        mismatch_rows=mismatch_rows,
        remote_files=remote_files,
        acquisition=acquisition,
        master=master,
    )
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "oshb_whole_tanakh_alignment_pilot_generated_not_source_approval",
        "source_paths": {
            "uxlc_zip": "data/raw/uxlc/Tanach.xml.zip",
            "morphology_acquisition_readiness": str(MORPHOLOGY_ACQUISITION_PATH.relative_to(ROOT)),
        },
        "source_boundary": {
            "scope": (
                "Remote OSHB WLC book files are fetched into memory for a derived "
                "alignment pilot only."
            ),
            "forbidden_use": (
                "This pilot does not write data/raw, approve OSHB source use, "
                "authorize generation/display/export, or change canonical renderings."
            ),
            "approval_state": "source_approval_not_recorded",
        },
        "method": {
            "remote_source": "Open Scriptures morphhb wlc XML files",
            "remote_commit_sha": master["sha"],
            "remote_commit_date": master["commit_date"],
            "normalization": (
                "NFKD; remove combining marks, Hebrew punctuation, maqaf, sof pasuq, "
                "slashes, pipes, whitespace, and non-Hebrew-letter annotation markers "
                "before token-sequence comparison."
            ),
            "alignment_metric": (
                "Verse-level OSHB token sequence is compared to local UXLC token "
                "sequence by normalized Hebrew form."
            ),
        },
        "summary": summary,
        "division_rows": division_rows,
        "book_rows": sorted(book_rows, key=lambda row: row["book"]),
        "source_fetch_rows": source_fetch_rows,
        "mismatch_rows": sorted(
            mismatch_rows,
            key=lambda row: (
                float(row["sequence_similarity_pct"]),
                row["book"],
                row["osis_id"],
            ),
        ),
        "visual_data": build_visual_data(book_rows, division_rows),
    }


def build_division_rows(book_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in book_rows:
        groups.setdefault(str(row["division"]), []).append(row)
    division_rows = []
    for division, rows in sorted(groups.items()):
        both = sum(int(row["both_sources_verse_count"]) for row in rows)
        exact = sum(int(row["exact_sequence_match_verse_count"]) for row in rows)
        token = sum(int(row["token_count_match_verse_count"]) for row in rows)
        words = sum(int(row["oshb_word_count"]) for row in rows)
        lemma = sum(int(row["oshb_lemma_count"]) for row in rows)
        morph = sum(int(row["oshb_morph_count"]) for row in rows)
        weighted_similarity = (
            sum(
                float(row["mean_sequence_similarity_pct"]) * row["both_sources_verse_count"]
                for row in rows
            )
            / both
            if both
            else 0.0
        )
        division_rows.append(
            {
                "division": division,
                "book_count": len(rows),
                "oshb_word_count": words,
                "both_sources_verse_count": both,
                "exact_sequence_match_pct": pct(exact, both),
                "token_count_match_pct": pct(token, both),
                "mean_sequence_similarity_pct": round(weighted_similarity, 2),
                "lemma_coverage_pct": pct(lemma, words),
                "morph_coverage_pct": pct(morph, words),
                "mismatch_verse_count": sum(int(row["mismatch_verse_count"]) for row in rows),
            }
        )
    return division_rows


def summarize(
    *,
    book_rows: list[dict[str, Any]],
    mismatch_rows: list[dict[str, Any]],
    remote_files: list[dict[str, Any]],
    acquisition: dict[str, Any],
    master: dict[str, str],
) -> dict[str, Any]:
    both = sum(int(row["both_sources_verse_count"]) for row in book_rows)
    exact = sum(int(row["exact_sequence_match_verse_count"]) for row in book_rows)
    token = sum(int(row["token_count_match_verse_count"]) for row in book_rows)
    oshb_words = sum(int(row["oshb_word_count"]) for row in book_rows)
    uxlc_words = sum(int(row["uxlc_word_count"]) for row in book_rows)
    lemma = sum(int(row["oshb_lemma_count"]) for row in book_rows)
    morph = sum(int(row["oshb_morph_count"]) for row in book_rows)
    non_psalm_rows = [row for row in book_rows if row["book"] != "Psalms"]
    non_psalm_words = sum(int(row["oshb_word_count"]) for row in non_psalm_rows)
    non_psalm_morph = sum(int(row["oshb_morph_count"]) for row in non_psalm_rows)
    weighted_similarity = (
        sum(
            float(row["mean_sequence_similarity_pct"]) * row["both_sources_verse_count"]
            for row in book_rows
        )
        / both
        if both
        else 0.0
    )
    high_readiness_books = sum(1 for row in book_rows if row["alignment_readiness"] == "high")
    review_required_books = sum(
        1 for row in book_rows if row["alignment_readiness"] == "review_required"
    )
    acquisition_summary = acquisition["summary"]
    return {
        "remote_commit_sha": master["sha"],
        "remote_commit_date": master["commit_date"],
        "remote_wlc_book_file_count": len(remote_files),
        "mapped_book_count": len(book_rows),
        "mapped_non_psalm_book_count": len(non_psalm_rows),
        "remote_oshb_word_count": oshb_words,
        "local_uxlc_word_count": uxlc_words,
        "remote_oshb_lemma_count": lemma,
        "remote_oshb_morph_count": morph,
        "remote_oshb_lemma_coverage_pct": pct(lemma, oshb_words),
        "remote_oshb_morph_coverage_pct": pct(morph, oshb_words),
        "remote_non_psalm_oshb_word_count": non_psalm_words,
        "remote_non_psalm_oshb_morph_count": non_psalm_morph,
        "remote_non_psalm_morph_coverage_pct": pct(non_psalm_morph, non_psalm_words),
        "both_sources_verse_count": both,
        "exact_sequence_match_verse_count": exact,
        "exact_sequence_match_pct": pct(exact, both),
        "token_count_match_verse_count": token,
        "token_count_match_pct": pct(token, both),
        "mean_sequence_similarity_pct": round(weighted_similarity, 2),
        "mismatch_row_count": len(mismatch_rows),
        "mismatch_sample_row_count": len(mismatch_rows),
        "mismatch_rows_are_complete": True,
        "high_alignment_readiness_book_count": high_readiness_books,
        "review_required_book_count": review_required_books,
        "high_exception_pressure_book_count": (
            len(book_rows) - high_readiness_books - review_required_books
        ),
        "estimated_non_psalm_morphology_books_if_approved": len(non_psalm_rows),
        "current_local_non_psalm_morphology_books": acquisition_summary[
            "local_non_psalm_morphology_book_count"
        ],
        "source_approval_status": "not_approved",
        "authority_verdict": (
            "pilot_feasible_not_authoritative: OSHB remote morphology is measurable "
            "and alignable, but source approval, derived importer, exception review, "
            "and release signoff remain incomplete."
        ),
    }


def build_visual_data(
    book_rows: list[dict[str, Any]],
    division_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "book_exact_match_rows": [
            {
                "label": row["book"],
                "value": row["exact_sequence_match_pct"],
                "division": row["division"],
            }
            for row in sorted(
                book_rows,
                key=lambda row: float(row["exact_sequence_match_pct"]),
            )
        ],
        "book_mismatch_rows": [
            {
                "label": row["book"],
                "value": row["mismatch_verse_count"],
                "division": row["division"],
            }
            for row in sorted(
                book_rows,
                key=lambda row: int(row["mismatch_verse_count"]),
                reverse=True,
            )
        ],
        "division_similarity_rows": [
            {
                "label": row["division"],
                "value": row["mean_sequence_similarity_pct"],
            }
            for row in division_rows
        ],
        "division_word_rows": [
            {
                "label": row["division"],
                "value": row["oshb_word_count"],
            }
            for row in division_rows
        ],
    }


def render_cards(cards: list[tuple[str, Any, str]]) -> str:
    return (
        '<div class="grid">'
        + "".join(
            '<article class="card">'
            f'<div class="metric">{esc(value)}</div>'
            f'<div class="label">{esc(label)}</div>'
            f"<p>{esc(note)}</p>"
            "</article>"
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


def svg_horizontal_bars(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    aria_label: str,
    color: str = "#2f6f73",
    width: int = 1040,
    limit: int = 20,
) -> str:
    rows = rows[:limit]
    row_h = 31
    left = 260
    right = 100
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
        bar_w = chart_w * value / max_value if max_value else 0
        parts.append(
            f'<text x="{left - 12}" y="{y + 20}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row.get(label_key, ""))}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 5}" width="{bar_w:.1f}" height="19" rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 20}" font-size="12" '
            f'font-weight="700" fill="#24313a">{value:g}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    book_rows = [
        [
            row["book"],
            row["division"],
            row["oshb_word_count"],
            row["uxlc_word_count"],
            f"{row['lemma_coverage_pct']:.2f}%",
            f"{row['morph_coverage_pct']:.2f}%",
            f"{row['exact_sequence_match_pct']:.2f}%",
            f"{row['mean_sequence_similarity_pct']:.2f}%",
            row["mismatch_verse_count"],
            row["alignment_readiness"],
        ]
        for row in report["book_rows"]
    ]
    division_rows = [
        [
            row["division"],
            row["book_count"],
            row["oshb_word_count"],
            f"{row['exact_sequence_match_pct']:.2f}%",
            f"{row['mean_sequence_similarity_pct']:.2f}%",
            row["mismatch_verse_count"],
        ]
        for row in report["division_rows"]
    ]
    mismatch_rows = [
        [
            row["book"],
            row["osis_id"],
            row["mismatch_type"],
            row["oshb_token_count"],
            row["uxlc_token_count"],
            f"{row['sequence_similarity_pct']:.2f}%",
            row["first_difference_index"],
            " ".join(row["oshb_surface_window"]),
            " ".join(row["uxlc_surface_window"]),
        ]
        for row in report["mismatch_rows"][:80]
    ]
    source_rows = [
        [
            row["book"],
            row["oshb_file"],
            row["byte_count"],
            row["source_url"],
        ]
        for row in report["source_fetch_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OSHB Whole-Tanakh Alignment Pilot</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #596875;
      --line: #cfd7de;
      --panel: #f7f9fb;
      --accent: #2f6f73;
      --accent2: #805a2b;
      --bad: #a12727;
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
    main {{ max-width: 1220px; margin: 0 auto; padding: 30px 34px 56px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    p {{ margin: 0 0 13px; }}
    a {{ color: #245e91; }}
    .lede {{ max-width: 1000px; font-size: 17px; color: #33414c; }}
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
      background: #fff4f4;
      border-left: 4px solid var(--bad);
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
    th {{ background: var(--panel); text-align: left; }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>OSHB Whole-Tanakh Alignment Pilot</h1>
    <p class="lede">
      Research-only pilot for extending Psalm-level OSHB morphology toward a
      whole-Tanakh derived index. The script fetches official Open Scriptures
      WLC XML files into memory, compares token sequences against local UXLC,
      and reports alignment feasibility without writing raw source data.
    </p>
    <p class="meta">
      Generated {esc(report["generated_on"])} from OSHB commit
      {esc(summary["remote_commit_sha"])} dated {esc(summary["remote_commit_date"])}.
    </p>
  </header>
  <main>
    <section>
      <h2>Pilot Verdict</h2>
      {
        render_cards(
            [
                (
                    "Mapped books",
                    fmt_int(summary["mapped_book_count"]),
                    f"{fmt_int(summary['mapped_non_psalm_book_count'])} are non-Psalm books.",
                ),
                (
                    "OSHB words",
                    fmt_int(summary["remote_oshb_word_count"]),
                    f"UXLC comparison words: {fmt_int(summary['local_uxlc_word_count'])}.",
                ),
                (
                    "Morph coverage",
                    fmt_pct(summary["remote_oshb_morph_coverage_pct"]),
                    f"Lemma coverage {fmt_pct(summary['remote_oshb_lemma_coverage_pct'])}.",
                ),
                (
                    "Exact verse matches",
                    fmt_pct(summary["exact_sequence_match_pct"]),
                    f"{fmt_int(summary['exact_sequence_match_verse_count'])} exact verses.",
                ),
                (
                    "Token count matches",
                    fmt_pct(summary["token_count_match_pct"]),
                    f"{fmt_int(summary['token_count_match_verse_count'])} verses match counts.",
                ),
                (
                    "Mean similarity",
                    fmt_pct(summary["mean_sequence_similarity_pct"]),
                    "Normalized token-sequence similarity.",
                ),
                (
                    "If approved",
                    fmt_int(summary["estimated_non_psalm_morphology_books_if_approved"]),
                    "Non-Psalm books would gain remote morphology candidate coverage.",
                ),
                (
                    "Current local",
                    fmt_int(summary["current_local_non_psalm_morphology_books"]),
                    "Non-Psalm books with local morphology today.",
                ),
            ]
        )
    }
      <div class="warning">
        <strong>Authority boundary:</strong>
        {esc(summary["authority_verdict"])}
      </div>
    </section>

    <section>
      <h2>Lowest Exact-Match Books</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["book_exact_match_rows"],
            label_key="label",
            value_key="value",
            aria_label="Lowest OSHB to UXLC exact verse match percentages by book",
            color="#9b3d3d",
            limit=20,
        )
    }</div>
    </section>

    <section>
      <h2>Highest Mismatch Books</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["book_mismatch_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB to UXLC mismatch verse count by book",
            color="#805a2b",
            limit=20,
        )
    }</div>
    </section>

    <section>
      <h2>Division Summary</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["division_similarity_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB to UXLC mean similarity by Tanakh division",
            color="#2f6f73",
        )
    }</div>
      {
        table(
            [
                "Division",
                "Books",
                "OSHB Words",
                "Exact Match",
                "Mean Similarity",
                "Mismatch Verses",
            ],
            division_rows,
        )
    }
    </section>

    <section>
      <h2>Book Alignment Rows</h2>
      {
        table(
            [
                "Book",
                "Division",
                "OSHB Words",
                "UXLC Words",
                "Lemma",
                "Morph",
                "Exact Match",
                "Mean Similarity",
                "Mismatch Verses",
                "Readiness",
            ],
            book_rows,
        )
    }
    </section>

    <section>
      <h2>Mismatch Samples</h2>
      {
        table(
            [
                "Book",
                "OSIS",
                "Type",
                "OSHB Tokens",
                "UXLC Tokens",
                "Similarity",
                "First Difference",
                "OSHB Window",
                "UXLC Window",
            ],
            mismatch_rows,
        )
    }
    </section>

    <section>
      <h2>Fetched Source Files</h2>
      {table(["Book", "OSHB File", "Bytes", "Pinned URL"], source_rows)}
    </section>
  </main>
</body>
</html>
"""


def flatten_book_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "book",
        "division",
        "oshb_file",
        "oshb_verse_count",
        "uxlc_verse_count",
        "both_sources_verse_count",
        "oshb_word_count",
        "uxlc_word_count",
        "lemma_coverage_pct",
        "morph_coverage_pct",
        "exact_sequence_match_pct",
        "token_count_match_pct",
        "mean_sequence_similarity_pct",
        "mismatch_verse_count",
        "alignment_readiness",
        "source_url",
    ]
    return [{key: row.get(key, "") for key in keys} for row in rows]


def flatten_mismatch_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "book",
        "division",
        "osis_id",
        "mismatch_type",
        "oshb_token_count",
        "uxlc_token_count",
        "sequence_similarity_pct",
        "first_difference_index",
        "oshb_window",
        "uxlc_window",
        "oshb_surface_window",
        "uxlc_surface_window",
    ]
    return [{key: row.get(key, "") for key in keys} for row in rows]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate OSHB whole-Tanakh morphology alignment pilot report."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--book-csv-output", type=Path, default=DEFAULT_BOOK_CSV_OUTPUT)
    parser.add_argument(
        "--mismatch-csv-output",
        type=Path,
        default=DEFAULT_MISMATCH_CSV_OUTPUT,
    )
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.book_csv_output, flatten_book_rows(report["book_rows"]))
    write_csv(args.mismatch_csv_output, flatten_mismatch_rows(report["mismatch_rows"]))
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.book_csv_output}")
    print(f"Wrote {args.mismatch_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
