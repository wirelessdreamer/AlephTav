from __future__ import annotations

import argparse
import html
import json
import unicodedata
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "docs" / "research" / "local_translation_benchmark_seed.json"
RUBRIC_PATH = ROOT / "docs" / "research" / "psalms_contextual_evaluation_rubric.json"
CONTENT_ROOT = ROOT / "content" / "psalms"
UXLC_ZIP_PATH = ROOT / "data" / "raw" / "uxlc" / "Tanach.xml.zip"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "psalms_seed_context_packets.json"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "psalms_seed_context_packets.html"

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

MAX_REF_SAMPLES = 12


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
    if value is None:
        return False
    if value == "":
        return False
    if value == []:
        return False
    if value == {}:
        return False
    return True


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
                                "sample_refs": [],
                                "outside_psalms_sample_refs": [],
                            },
                        )
                        entry["tanakh_count"] += 1
                        entry["division_counts"][division] += 1
                        entry["book_counts"][book_name] += 1
                        add_sample(entry["sample_refs"], ref)
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
            "book_counts": dict(entry["book_counts"].most_common(12)),
            "sample_refs": entry["sample_refs"],
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


def case_studies_by_unit(rubric: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(case["unit_id"]): case for case in rubric.get("case_studies", []) if case.get("unit_id")
    }


def unit_path(content_root: Path, unit_id: str) -> Path:
    psalm_id = unit_id.split(".")[0]
    return content_root / psalm_id / f"{unit_id}.json"


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


def packet_for_seed_unit(
    seed_unit: dict[str, Any],
    *,
    content_root: Path,
    form_index: dict[str, Any],
    case_studies: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    unit_id = str(seed_unit["unit_id"])
    data = load_json(unit_path(content_root, unit_id))
    token_rows = []
    missing_enrichments: Counter[str] = Counter()
    surface_matches = 0
    surface_outside_matches = 0
    lemma_form_matches = 0
    lemma_form_outside_matches = 0
    outside_context_refs = 0
    high_context_tokens = []

    for token in data.get("tokens") or []:
        surface_query = normalize_hebrew_form(token.get("surface"))
        lemma_query = normalize_hebrew_form(token.get("lemma"))
        surface_context = context_summary(form_index, surface_query)
        lemma_form_context = context_summary(form_index, lemma_query)
        if surface_context["matched"]:
            surface_matches += 1
        if surface_context["outside_psalms_count"]:
            surface_outside_matches += 1
            outside_context_refs += int(surface_context["outside_psalms_count"])
        if lemma_form_context["matched"]:
            lemma_form_matches += 1
        if lemma_form_context["outside_psalms_count"]:
            lemma_form_outside_matches += 1

        missing_enrichments.update(str(item) for item in token.get("missing_enrichments", []))
        token_row = {
            "token_id": token.get("token_id"),
            "surface": token.get("surface"),
            "lemma": token.get("lemma"),
            "display_gloss": token.get("display_gloss"),
            "part_of_speech": token.get("part_of_speech"),
            "surface_query": surface_query,
            "lemma_form_query": lemma_query,
            "surface_context": surface_context,
            "lemma_form_context": lemma_form_context,
            "evidence_warning": (
                "lemma_form_context matches normalized lemma text against UXLC surface forms; "
                "it is not lemma-aware semantic evidence"
            ),
        }
        token_rows.append(token_row)
        if surface_context["outside_psalms_count"]:
            high_context_tokens.append(
                {
                    "token_id": token.get("token_id"),
                    "surface": token.get("surface"),
                    "display_gloss": token.get("display_gloss"),
                    "surface_query": surface_query,
                    "outside_psalms_count": surface_context["outside_psalms_count"],
                    "outside_psalms_sample_refs": surface_context["outside_psalms_sample_refs"],
                }
            )

    token_count = len(data.get("tokens") or [])
    case = case_studies.get(unit_id, {})
    return {
        "unit_id": unit_id,
        "ref": data.get("ref") or seed_unit.get("ref"),
        "benchmark_tags": seed_unit.get("benchmark_tags", []),
        "why_in_seed": seed_unit.get("why_in_seed"),
        "contextual_case_layers": case.get("layers", []),
        "contextual_case_reason": case.get("why"),
        "token_count": token_count,
        "source_hebrew": data.get("source_hebrew"),
        "witness_summary": witness_summary(data),
        "coverage": {
            "surface_form_matches": surface_matches,
            "surface_form_match_pct": pct(surface_matches, token_count),
            "surface_forms_with_outside_psalms_context": surface_outside_matches,
            "surface_outside_context_pct": pct(surface_outside_matches, token_count),
            "lemma_form_matches": lemma_form_matches,
            "lemma_form_match_pct": pct(lemma_form_matches, token_count),
            "lemma_forms_with_outside_psalms_context": lemma_form_outside_matches,
            "lemma_outside_context_pct": pct(lemma_form_outside_matches, token_count),
            "outside_psalms_surface_occurrence_total": outside_context_refs,
        },
        "missing_enrichment_counts": dict(sorted(missing_enrichments.items())),
        "high_context_tokens": sorted(
            high_context_tokens,
            key=lambda row: int(row["outside_psalms_count"]),
            reverse=True,
        )[:8],
        "tokens": token_rows,
    }


def aggregate_packets(packets: list[dict[str, Any]]) -> dict[str, Any]:
    tag_counts: Counter[str] = Counter()
    witness_sources: Counter[str] = Counter()
    missing_enrichments: Counter[str] = Counter()
    high_context_forms: Counter[str] = Counter()
    total_tokens = 0
    surface_matches = 0
    surface_outside = 0
    lemma_matches = 0
    lemma_outside = 0

    for packet in packets:
        tag_counts.update(str(tag) for tag in packet.get("benchmark_tags", []))
        witness_sources.update(packet["witness_summary"]["sources"])
        missing_enrichments.update(packet["missing_enrichment_counts"])
        total_tokens += int(packet["token_count"])
        coverage = packet["coverage"]
        surface_matches += int(coverage["surface_form_matches"])
        surface_outside += int(coverage["surface_forms_with_outside_psalms_context"])
        lemma_matches += int(coverage["lemma_form_matches"])
        lemma_outside += int(coverage["lemma_forms_with_outside_psalms_context"])
        for token in packet["high_context_tokens"]:
            high_context_forms[str(token["surface_query"])] += int(token["outside_psalms_count"])

    return {
        "seed_unit_count": len(packets),
        "seed_token_count": total_tokens,
        "surface_form_matches": surface_matches,
        "surface_form_match_pct": pct(surface_matches, total_tokens),
        "surface_forms_with_outside_psalms_context": surface_outside,
        "surface_outside_context_pct": pct(surface_outside, total_tokens),
        "lemma_form_matches": lemma_matches,
        "lemma_form_match_pct": pct(lemma_matches, total_tokens),
        "lemma_forms_with_outside_psalms_context": lemma_outside,
        "lemma_outside_context_pct": pct(lemma_outside, total_tokens),
        "benchmark_tag_counts": dict(tag_counts.most_common()),
        "witness_source_counts": dict(witness_sources.most_common()),
        "missing_enrichment_counts": dict(missing_enrichments.most_common()),
        "high_context_surface_forms": [
            {"surface_query": form, "outside_psalms_weight": count}
            for form, count in high_context_forms.most_common(30)
        ],
    }


def build_report(
    *,
    seed_path: Path,
    rubric_path: Path,
    content_root: Path,
    uxlc_zip_path: Path,
) -> dict[str, Any]:
    seed = load_json(seed_path)
    rubric = load_json(rubric_path)
    index = build_form_index(uxlc_zip_path)
    case_studies = case_studies_by_unit(rubric)
    packets = [
        packet_for_seed_unit(
            unit,
            content_root=content_root,
            form_index=index["forms"],
            case_studies=case_studies,
        )
        for unit in seed.get("seed_units", [])
    ]
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated seed context packets; form-level context, not benchmark results",
        "source_paths": {
            "seed_manifest": "docs/research/local_translation_benchmark_seed.json",
            "contextual_rubric": "docs/research/psalms_contextual_evaluation_rubric.json",
            "content_root": "content/psalms",
            "uxlc_zip": "data/raw/uxlc/Tanach.xml.zip",
        },
        "normalization": {
            "method": "NFKD; remove combining marks, Hebrew punctuation, and whitespace",
            "warning": (
                "Surface context is form-level evidence; lemma_form_context is a "
                "normalized-form lookup, not lemma-aware semantic retrieval."
            ),
        },
        "uxlc_form_index_summary": index["summary"],
        "aggregate": aggregate_packets(packets),
        "packets": packets,
    }


def rows_from_counter(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
    return [
        {label_key: label, "count": count}
        for label, count in sorted(counter.items(), key=lambda item: item[1], reverse=True)
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
    row_h = 28
    left = 250
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
        label = str(row[label_key])
        parts.append(
            f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(label)}</text>'
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


def svg_unit_context_density(packets: list[dict[str, Any]]) -> str:
    rows = [
        {
            "unit_id": packet["unit_id"],
            "pct": packet["coverage"]["surface_outside_context_pct"],
        }
        for packet in packets
    ]
    rows = sorted(rows, key=lambda row: float(row["pct"]), reverse=True)
    return svg_horizontal_bars(
        rows,
        label_key="unit_id",
        value_key="pct",
        aria_label="Seed unit outside-Psalms surface context percentage",
        color="#2f6f73",
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
    aggregate = report["aggregate"]
    packets = report["packets"]
    unit_rows = [
        [
            packet["unit_id"],
            packet["ref"],
            fmt_int(packet["token_count"]),
            f"{packet['coverage']['surface_outside_context_pct']:.2f}%",
            fmt_int(packet["coverage"]["outside_psalms_surface_occurrence_total"]),
            ", ".join(packet["benchmark_tags"]),
        ]
        for packet in packets
    ]
    high_context_rows = [
        [
            f'<span class="hebrew">{esc(row["surface_query"])}</span>',
            fmt_int(row["outside_psalms_weight"]),
        ]
        for row in aggregate["high_context_surface_forms"][:25]
    ]
    sample_rows = []
    for packet in packets:
        for token in packet["high_context_tokens"][:3]:
            sample_rows.append(
                [
                    packet["unit_id"],
                    token["token_id"],
                    f'<span class="hebrew">{esc(token["surface"])}</span>',
                    token["display_gloss"],
                    fmt_int(token["outside_psalms_count"]),
                    "; ".join(token["outside_psalms_sample_refs"][:5]),
                ]
            )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Psalms Seed Context Packets</title>
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
      font-size: 15px;
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
    <h1>AlephTav Psalms Seed Context Packets</h1>
    <p class="lede">
      Generated evidence packets for the current benchmark seed units. These
      packets join unit tokens, witness summaries, benchmark tags, contextual
      rubric case data, and whole-Tanakh normalized-form context from UXLC.
    </p>
    <p class="meta">
      Generated {esc(report["generated_on"])}. {esc(report["normalization"]["warning"])}
    </p>
  </header>
  <main>
    <section>
      <h2>Aggregate Coverage</h2>
      {
        metric_cards(
            [
                (
                    "Seed units",
                    fmt_int(aggregate["seed_unit_count"]),
                    "Benchmark units with generated context packets.",
                ),
                (
                    "Seed tokens",
                    fmt_int(aggregate["seed_token_count"]),
                    "Token records inside the seed packets.",
                ),
                (
                    "Surface matches",
                    f'''{aggregate["surface_form_match_pct"]:.2f}%''',
                    "Seed tokens matching a normalized UXLC surface form.",
                ),
                (
                    "Outside-Psalms context",
                    f'''{aggregate["surface_outside_context_pct"]:.2f}%''',
                    "Seed tokens whose surface form appears outside Psalms.",
                ),
            ]
        )
    }
      <div class="warning">
        This is a context-packet prototype, not a translation benchmark result.
        Surface-form evidence is useful for retrieval, but final scoring still
        needs lemma-aware morphology, sense disambiguation, witness boundaries,
        and human review.
      </div>
      <div class="chart">{svg_unit_context_density(packets)}</div>
      {
        table(
            [
                "Unit",
                "Reference",
                "Tokens",
                "Outside context",
                "Outside occurrence total",
                "Benchmark tags",
            ],
            unit_rows,
        )
    }
    </section>

    <section>
      <h2>Context Signals</h2>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(aggregate["benchmark_tag_counts"], "tag"),
            label_key="tag",
            value_key="count",
            aria_label="Benchmark tag counts",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(aggregate["witness_source_counts"], "source"),
            label_key="source",
            value_key="count",
            aria_label="Witness source counts",
            color="#58508d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            aggregate["high_context_surface_forms"],
            label_key="surface_query",
            value_key="outside_psalms_weight",
            aria_label="High-context seed surface forms",
            color="#7c5b2f",
            limit=25,
        )
    }</div>
      {table(["Surface form", "Outside-Psalms weight"], high_context_rows)}
    </section>

    <section>
      <h2>Token Examples</h2>
      <p>
        The examples below are high-context seed tokens with outside-Psalms
        form matches. These references are retrieval leads, not proof of sense.
      </p>
      {
        table(
            [
                "Unit",
                "Token",
                "Surface",
                "Display gloss",
                "Outside count",
                "Sample outside refs",
            ],
            sample_rows[:60],
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate seed context packets for Psalms benchmark units."
    )
    parser.add_argument("--seed-path", type=Path, default=SEED_PATH)
    parser.add_argument("--rubric-path", type=Path, default=RUBRIC_PATH)
    parser.add_argument("--content-root", type=Path, default=CONTENT_ROOT)
    parser.add_argument("--uxlc-zip", type=Path, default=UXLC_ZIP_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        seed_path=args.seed_path,
        rubric_path=args.rubric_path,
        content_root=args.content_root,
        uxlc_zip_path=args.uxlc_zip,
    )
    write_json(args.json_output, report)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
