from __future__ import annotations

import argparse
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
UXLC_ZIP_PATH = ROOT / "data" / "raw" / "uxlc" / "Tanach.xml.zip"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "tanakh_lexical_context.json"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "tanakh_lexical_context.html"

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


def normalize_hebrew_form(text: str) -> str:
    chars = []
    for char in unicodedata.normalize("NFKD", text):
        if unicodedata.category(char) == "Mn":
            continue
        if char in PUNCTUATION:
            continue
        chars.append(char)
    return "".join(chars)


def load_book_words(archive: zipfile.ZipFile, name: str) -> tuple[str, list[str]]:
    root = ET.fromstring(archive.read(name))
    book = root.find("./tanach/book")
    names_el = book.find("names") if book is not None else None
    display = names_el.findtext("name") if names_el is not None else Path(name).stem
    words = []
    for word in root.findall(".//w"):
        text = "".join(word.itertext())
        normalized = normalize_hebrew_form(text)
        if normalized:
            words.append(normalized)
    return str(display), words


def form_rows(
    psalms_counter: Counter[str],
    tanakh_counter: Counter[str],
    division_counters: dict[str, Counter[str]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    rows = []
    for form, count in psalms_counter.most_common(limit):
        tanakh_count = tanakh_counter[form]
        outside_psalms = tanakh_count - count
        rows.append(
            {
                "form": form,
                "psalms_count": count,
                "tanakh_count": tanakh_count,
                "outside_psalms_count": outside_psalms,
                "pct_occurrences_in_psalms": pct(count, tanakh_count),
                "division_counts": {
                    division: counter[form]
                    for division, counter in sorted(division_counters.items())
                    if counter[form]
                },
            }
        )
    return rows


def high_context_rows(
    psalms_counter: Counter[str],
    tanakh_counter: Counter[str],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    candidates = []
    for form, psalms_count in psalms_counter.items():
        outside_count = tanakh_counter[form] - psalms_count
        if psalms_count < 2 or outside_count < 20:
            continue
        score = outside_count * (1 + psalms_count / 10)
        candidates.append(
            {
                "form": form,
                "psalms_count": psalms_count,
                "outside_psalms_count": outside_count,
                "tanakh_count": tanakh_counter[form],
                "context_score": round(score, 2),
            }
        )
    return sorted(
        candidates,
        key=lambda row: (
            float(row["context_score"]),
            int(row["tanakh_count"]),
            str(row["form"]),
        ),
        reverse=True,
    )[:limit]


def build_report(zip_path: Path) -> dict[str, Any]:
    book_rows = []
    tanakh_counter: Counter[str] = Counter()
    psalms_counter: Counter[str] = Counter()
    division_counters: dict[str, Counter[str]] = defaultdict(Counter)
    division_totals: Counter[str] = Counter()

    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(name for name in archive.namelist() if canonical_book_file(name))
        for name in names:
            book, words = load_book_words(archive, name)
            division = DIVISIONS.get(book, "Unmapped")
            counter = Counter(words)
            tanakh_counter.update(counter)
            division_counters[division].update(counter)
            division_totals[division] += len(words)
            if book == "Psalms":
                psalms_counter.update(counter)
            book_rows.append(
                {
                    "book": book,
                    "division": division,
                    "word_elements": len(words),
                    "distinct_normalized_forms": len(counter),
                }
            )

    psalm_unique_forms = [
        form for form in psalms_counter if tanakh_counter[form] == psalms_counter[form]
    ]
    psalm_shared_forms = [
        form for form in psalms_counter if tanakh_counter[form] > psalms_counter[form]
    ]

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated read-only UXLC form-level profile; not lemma analysis",
        "source_path": "data/raw/uxlc/Tanach.xml.zip",
        "normalization": {
            "method": "NFKD; remove combining marks, Hebrew punctuation, and whitespace",
            "warning": "Counts are normalized surface forms, not OSHB lemmas or senses.",
        },
        "summary": {
            "book_count": len(book_rows),
            "tanakh_word_elements": sum(row["word_elements"] for row in book_rows),
            "tanakh_distinct_forms": len(tanakh_counter),
            "psalms_word_elements": sum(psalms_counter.values()),
            "psalms_distinct_forms": len(psalms_counter),
            "psalm_forms_shared_outside_psalms": len(psalm_shared_forms),
            "psalm_forms_unique_to_psalms": len(psalm_unique_forms),
            "pct_psalm_forms_shared_outside_psalms": pct(
                len(psalm_shared_forms),
                len(psalms_counter),
            ),
        },
        "division_totals": [
            {"division": division, "word_elements": count}
            for division, count in sorted(division_totals.items())
        ],
        "book_rows": sorted(book_rows, key=lambda row: int(row["word_elements"]), reverse=True),
        "top_psalms_forms": form_rows(
            psalms_counter,
            tanakh_counter,
            division_counters,
            limit=50,
        ),
        "high_context_forms": high_context_rows(
            psalms_counter,
            tanakh_counter,
            limit=50,
        ),
        "psalm_unique_form_samples": sorted(psalm_unique_forms)[:100],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


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
    row_h = 28
    left = 220
    right = 54
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
            f'font-weight="700" fill="#24313a">{fmt_int(value)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def svg_psalm_form_context(rows: list[dict[str, Any]]) -> str:
    rows = rows[:25]
    width = 980
    row_h = 28
    left = 120
    right = 44
    top = 24
    height = top * 2 + row_h * len(rows)
    max_value = max((int(row["tanakh_count"]) for row in rows), default=1)
    chart_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Psalm forms with outside-Psalms context">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, row in enumerate(rows):
        y = top + index * row_h
        ps_count = int(row["psalms_count"])
        outside_count = int(row["outside_psalms_count"])
        total = int(row["tanakh_count"])
        ps_w = chart_w * ps_count / max_value
        outside_w = chart_w * outside_count / max_value
        parts.append(
            f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" '
            f'font-size="15" class="hebrew">{esc(row["form"])}</text>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{outside_w:.1f}" '
            'height="18" rx="3" fill="#cbd3d9"/>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{ps_w:.1f}" height="18" rx="3" fill="#2f6f73"/>'
        )
        parts.append(
            f'<text x="{left + outside_w + 8:.1f}" y="{y + 18}" '
            f'font-size="12" font-weight="700" fill="#24313a">{fmt_int(total)}</text>'
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
    top_forms = report["top_psalms_forms"][:30]
    high_context = report["high_context_forms"][:30]
    book_rows = [
        [
            row["book"],
            row["division"],
            fmt_int(row["word_elements"]),
            fmt_int(row["distinct_normalized_forms"]),
        ]
        for row in report["book_rows"][:25]
    ]
    form_rows = [
        [
            f'<span class="hebrew">{esc(row["form"])}</span>',
            fmt_int(row["psalms_count"]),
            fmt_int(row["tanakh_count"]),
            fmt_int(row["outside_psalms_count"]),
            f"{row['pct_occurrences_in_psalms']:.2f}%",
        ]
        for row in top_forms
    ]
    context_rows = [
        [
            f'<span class="hebrew">{esc(row["form"])}</span>',
            fmt_int(row["psalms_count"]),
            fmt_int(row["outside_psalms_count"]),
            fmt_int(row["tanakh_count"]),
            f"{float(row['context_score']):.2f}",
        ]
        for row in high_context
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Whole-Tanakh Lexical Context Profile</title>
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
    .note {{
      background: #fff8e9;
      border-left: 4px solid var(--accent2);
      padding: 13px 15px;
      margin: 18px 0;
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
    .hebrew {{
      direction: rtl;
      unicode-bidi: isolate;
      font-family: "SBL Hebrew", "Times New Roman", serif;
    }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AlephTav Whole-Tanakh Lexical Context Profile</h1>
    <p class="lede">
      A read-only, form-level profile of the UXLC Tanakh archive for building
      broader lexical context around Psalms translation. This is deliberately
      not a lemma or semantic-sense report; it is a reproducible baseline for
      future whole-Tanakh retrieval work.
    </p>
    <p class="meta">
      Generated {esc(report["generated_on"])} from data/raw/uxlc/Tanach.xml.zip.
      Normalization: {esc(report["normalization"]["method"])}.
    </p>
  </header>
  <main>
    <section>
      <h2>Inventory</h2>
      {
        metric_cards(
            [
                ("Books", fmt_int(summary["book_count"]), "Canonical UXLC book XML files scanned."),
                (
                    "Tanakh word elements",
                    fmt_int(summary["tanakh_word_elements"]),
                    "UXLC w-elements across canonical books.",
                ),
                (
                    "Distinct forms",
                    fmt_int(summary["tanakh_distinct_forms"]),
                    "Normalized surface forms across the Tanakh.",
                ),
                (
                    "Psalms forms shared",
                    f'''{summary["pct_psalm_forms_shared_outside_psalms"]:.2f}%''',
                    "Distinct Psalm forms also seen outside Psalms.",
                ),
            ]
        )
    }
      <div class="warning">
        This profile strips pointing and cantillation for counting. It should
        guide retrieval engineering, but translation scoring still needs
        lemma-aware OSHB/MACULA evidence and human review.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            report["division_totals"],
            label_key="division",
            value_key="word_elements",
            aria_label="Tanakh word elements by division",
            color="#58508d",
        )
    }</div>
      {table(["Book", "Division", "Word elements", "Distinct forms"], book_rows)}
    </section>

    <section>
      <h2>Psalms In Whole-Tanakh Context</h2>
      {
        metric_cards(
            [
                (
                    "Psalms word elements",
                    fmt_int(summary["psalms_word_elements"]),
                    "UXLC w-elements in Psalms.",
                ),
                (
                    "Psalms distinct forms",
                    fmt_int(summary["psalms_distinct_forms"]),
                    "Normalized Psalm forms.",
                ),
                (
                    "Shared forms",
                    fmt_int(summary["psalm_forms_shared_outside_psalms"]),
                    "Psalm forms also appearing elsewhere.",
                ),
                (
                    "Psalm-unique forms",
                    fmt_int(summary["psalm_forms_unique_to_psalms"]),
                    "Psalm forms not seen elsewhere by this normalization.",
                ),
            ]
        )
    }
      <div class="chart">{svg_psalm_form_context(top_forms)}</div>
      {
        table(
            [
                "Form",
                "Psalms count",
                "Tanakh count",
                "Outside Psalms",
                "Occurrences in Psalms",
            ],
            form_rows,
        )
    }
    </section>

    <section>
      <h2>High-Context Retrieval Candidates</h2>
      <p>
        These normalized forms appear in Psalms and frequently outside Psalms.
        They are good early targets for a whole-Tanakh context retriever, though
        each still needs lemma and sense disambiguation before translation use.
      </p>
      <div class="chart">{
        svg_horizontal_bars(
            high_context,
            label_key="form",
            value_key="context_score",
            aria_label="High-context form candidates",
            color="#7c5b2f",
            limit=25,
        )
    }</div>
      {
        table(
            ["Form", "Psalms count", "Outside Psalms", "Tanakh count", "Context score"],
            context_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a whole-Tanakh lexical context profile from UXLC."
    )
    parser.add_argument("--uxlc-zip", type=Path, default=UXLC_ZIP_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.uxlc_zip)
    write_json(args.json_output, report)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
