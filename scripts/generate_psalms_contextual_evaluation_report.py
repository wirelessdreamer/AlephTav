from __future__ import annotations

import argparse
import html
import json
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RUBRIC_PATH = ROOT / "docs" / "research" / "psalms_contextual_evaluation_rubric.json"
CORPUS_PROFILE_PATH = ROOT / "reports" / "research" / "psalms_corpus_profile.json"
UXLC_ZIP_PATH = ROOT / "data" / "raw" / "uxlc" / "Tanach.xml.zip"
CONTENT_ROOT = ROOT / "content" / "psalms"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "psalms_contextual_evaluation.json"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "psalms_contextual_evaluation.html"

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

CONTRACT_STATUS = {
    "source_basis": "available",
    "psalms_concordance": "available",
    "tanakh_context": "partial",
    "poetic_form": "seed-only",
    "cultural_setting": "missing",
    "textual_witnesses": "partial",
    "reception_history": "seed-only",
    "review_requirements": "policy-only",
}

STATUS_SCORE = {
    "available": 5,
    "partial": 3,
    "seed-only": 2,
    "policy-only": 2,
    "missing": 0,
}

PALETTE = {
    "available": "#2f6f73",
    "partial": "#7c5b2f",
    "seed-only": "#58508d",
    "policy-only": "#4f6f9f",
    "missing": "#9b3d3d",
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


def canonical_book_file(name: str) -> bool:
    if not name.startswith("Books/") or not name.endswith(".xml"):
        return False
    if name.endswith(".DH.xml"):
        return False
    if name.endswith("TanachHeader.xml") or name.endswith("TanachIndex.xml"):
        return False
    return True


def parse_uxlc_inventory(zip_path: Path) -> dict[str, Any]:
    rows = []
    totals = Counter()
    division_totals: dict[str, Counter[str]] = defaultdict(Counter)

    with zipfile.ZipFile(zip_path) as archive:
        names = sorted(name for name in archive.namelist() if canonical_book_file(name))
        for name in names:
            root = ET.fromstring(archive.read(name))
            book = root.find("./tanach/book")
            names_el = book.find("names") if book is not None else None
            display = names_el.findtext("name") if names_el is not None else Path(name).stem
            division = DIVISIONS.get(str(display), "Unmapped")
            counts = {
                "chapters": len(root.findall(".//c")),
                "verses": len(root.findall(".//v")),
                "words": len(root.findall(".//w")),
                "ketiv": len(root.findall(".//k")),
                "qere": len(root.findall(".//q")),
            }
            row = {
                "book": display,
                "file": name,
                "division": division,
                **counts,
            }
            rows.append(row)
            totals["books"] += 1
            for key, value in counts.items():
                totals[key] += value
                division_totals[division][key] += value
            division_totals[division]["books"] += 1

    return {
        "source_path": "data/raw/uxlc/Tanach.xml.zip",
        "summary": dict(sorted(totals.items())),
        "by_division": [
            {"division": division, **dict(counts)}
            for division, counts in sorted(division_totals.items())
        ],
        "books": rows,
    }


def scan_current_psalm_context(content_root: Path) -> dict[str, Any]:
    occurrence_books: Counter[str] = Counter()
    occurrence_ref_count = 0
    tokens_with_refs = 0
    max_refs = 0
    unit_count = 0
    token_count = 0
    witness_roles: Counter[str] = Counter()
    witness_sources: Counter[str] = Counter()
    witness_languages: Counter[str] = Counter()

    for path in sorted(content_root.glob("ps*/ps*.v*.json")):
        data = load_json(path)
        unit_count += 1
        tokens = data.get("tokens") or []
        token_count += len(tokens)
        for witness in data.get("witnesses") or []:
            witness_roles[str(witness.get("witness_role") or "unknown")] += 1
            witness_sources[str(witness.get("source_id") or "unknown")] += 1
            witness_languages[str(witness.get("language") or "unknown")] += 1
        for token in tokens:
            refs = token.get("corpus_occurrence_refs") or []
            if refs:
                tokens_with_refs += 1
            max_refs = max(max_refs, len(refs))
            occurrence_ref_count += len(refs)
            for ref in refs:
                text = str(ref)
                key = text.split()[0] if " " in text else text.split(".")[0]
                occurrence_books[key] += 1

    return {
        "unit_count": unit_count,
        "token_count": token_count,
        "tokens_with_corpus_occurrence_refs": tokens_with_refs,
        "corpus_occurrence_ref_count": occurrence_ref_count,
        "max_refs_per_token": max_refs,
        "occurrence_ref_books": dict(sorted(occurrence_books.items())),
        "witness_roles": dict(sorted(witness_roles.items())),
        "witness_sources": dict(sorted(witness_sources.items())),
        "witness_languages": dict(sorted(witness_languages.items())),
    }


def layer_summary(rubric: dict[str, Any]) -> list[dict[str, Any]]:
    layers = []
    for layer in rubric["context_layers"]:
        readiness = float(layer["readiness"])
        weight = float(layer["weight"])
        layers.append(
            {
                "id": layer["id"],
                "label": layer["label"],
                "readiness": readiness,
                "weight": weight,
                "weighted_readiness": round(readiness * weight, 2),
                "weighted_gap": round((5 - readiness) * weight, 2),
                "current_evidence": layer["current_evidence"],
                "required_next_evidence": layer["required_next_evidence"],
                "evaluation_questions": layer["evaluation_questions"],
                "failure_modes": layer["failure_modes"],
            }
        )
    return layers


def case_study_matrix(rubric: dict[str, Any]) -> dict[str, Any]:
    layers = [layer["id"] for layer in rubric["context_layers"]]
    layer_labels = {layer["id"]: layer["label"] for layer in rubric["context_layers"]}
    layer_counts: Counter[str] = Counter()
    rows = []
    for case in rubric["case_studies"]:
        covered = set(case["layers"])
        layer_counts.update(covered)
        rows.append(
            {
                "unit_id": case["unit_id"],
                "ref": case["ref"],
                "layer_coverage": {layer: layer in covered for layer in layers},
                "covered_layer_count": len(covered),
                "why": case["why"],
                "rubric_flags": case["rubric_flags"],
            }
        )
    return {
        "layers": [{"id": layer, "label": layer_labels[layer]} for layer in layers],
        "layer_counts": dict(sorted(layer_counts.items())),
        "case_count": len(rows),
        "rows": rows,
    }


def contract_rows(rubric: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in rubric["context_packet_contract"]:
        field = item["field"]
        status = CONTRACT_STATUS.get(field, "missing")
        rows.append(
            {
                "field": field,
                "required": bool(item["required"]),
                "description": item["description"],
                "current_status": status,
                "status_score": STATUS_SCORE[status],
            }
        )
    return rows


def build_report(
    rubric_path: Path,
    corpus_profile_path: Path,
    uxlc_zip_path: Path,
    content_root: Path,
) -> dict[str, Any]:
    rubric = load_json(rubric_path)
    corpus_profile = load_json(corpus_profile_path) if corpus_profile_path.exists() else {}
    layers = layer_summary(rubric)
    total_weight = sum(float(layer["weight"]) for layer in layers)
    weighted_readiness = sum(float(layer["weighted_readiness"]) for layer in layers)
    weighted_gap = sum(float(layer["weighted_gap"]) for layer in layers)
    weighted_mean = round(weighted_readiness / total_weight, 2) if total_weight else 0.0

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated contextual evaluation report; not a benchmark result",
        "rubric_source": "docs/research/psalms_contextual_evaluation_rubric.json",
        "corpus_profile_source": "reports/research/psalms_corpus_profile.json",
        "summary": {
            "context_layer_count": len(layers),
            "case_study_count": len(rubric["case_studies"]),
            "weighted_readiness_mean": weighted_mean,
            "weighted_gap_total": round(weighted_gap, 2),
        },
        "uxlc_inventory": parse_uxlc_inventory(uxlc_zip_path),
        "current_psalm_context": scan_current_psalm_context(content_root),
        "corpus_profile_summary": corpus_profile.get("summary", {}),
        "context_layers": layers,
        "context_packet_contract": contract_rows(rubric),
        "case_study_matrix": case_study_matrix(rubric),
        "citations": rubric["citations"],
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
    max_value: float | None = None,
) -> str:
    rows = rows[:limit]
    row_h = 28
    left = 240
    right = 48
    top = 24
    height = top * 2 + row_h * max(1, len(rows))
    actual_max = max((float(row[value_key]) for row in rows), default=1.0)
    chart_max = max_value if max_value is not None else actual_max
    chart_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, row in enumerate(rows):
        value = float(row[value_key])
        y = top + index * row_h
        bar_w = chart_w * value / chart_max if chart_max else 0
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


def svg_layer_readiness(layers: list[dict[str, Any]]) -> str:
    return svg_horizontal_bars(
        layers,
        label_key="label",
        value_key="readiness",
        aria_label="Context layer readiness scores",
        color="#2f6f73",
        max_value=5,
    )


def svg_layer_gaps(layers: list[dict[str, Any]]) -> str:
    rows = sorted(layers, key=lambda row: float(row["weighted_gap"]), reverse=True)
    return svg_horizontal_bars(
        rows,
        label_key="label",
        value_key="weighted_gap",
        aria_label="Weighted contextual gap scores",
        color="#9b3d3d",
    )


def svg_division_inventory(report: dict[str, Any]) -> str:
    rows = sorted(
        report["uxlc_inventory"]["by_division"],
        key=lambda row: int(row["words"]),
        reverse=True,
    )
    return svg_horizontal_bars(
        rows,
        label_key="division",
        value_key="words",
        aria_label="UXLC words by Tanakh division",
        color="#58508d",
    )


def svg_contract_status(rows: list[dict[str, Any]]) -> str:
    width = 980
    row_h = 38
    left = 240
    top = 26
    right = 40
    height = top * 2 + row_h * len(rows)
    slot_w = (width - left - right) / 5
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Context packet status by field">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, row in enumerate(rows):
        y = top + index * row_h
        score = int(row["status_score"])
        status = row["current_status"]
        parts.append(
            f'<text x="{left - 12}" y="{y + 23}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row["field"])}</text>'
        )
        for slot in range(5):
            fill = PALETTE[status] if slot < score else "#edf0f2"
            x = left + slot * slot_w
            parts.append(
                f'<rect x="{x:.1f}" y="{y + 7}" width="{slot_w - 5:.1f}" '
                f'height="18" rx="3" fill="{fill}" stroke="#ffffff"/>'
            )
        parts.append(
            f'<text x="{width - right}" y="{y + 23}" text-anchor="end" '
            f'font-size="12" font-weight="700" fill="#24313a">{esc(status)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def svg_case_heatmap(matrix: dict[str, Any]) -> str:
    layers = matrix["layers"]
    rows = matrix["rows"]
    cell_w = 78
    cell_h = 28
    left = 128
    top = 148
    width = left + cell_w * len(layers) + 26
    height = top + cell_h * len(rows) + 32
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Case study layer coverage heatmap">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for col, layer in enumerate(layers):
        x = left + col * cell_w + cell_w / 2
        parts.append(
            f'<text x="{x:.1f}" y="122" text-anchor="start" font-size="11" '
            f'fill="#24313a" transform="rotate(-42 {x:.1f} 122)">'
            f"{esc(layer['label'])}</text>"
        )
    for row_index, case in enumerate(rows):
        y = top + row_index * cell_h
        parts.append(
            f'<text x="{left - 10}" y="{y + 18}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(case["unit_id"])}</text>'
        )
        for col, layer in enumerate(layers):
            x = left + col * cell_w
            covered = bool(case["layer_coverage"][layer["id"]])
            fill = "#2f6f73" if covered else "#edf0f2"
            label = "1" if covered else ""
            parts.append(
                f'<rect x="{x}" y="{y + 3}" width="{cell_w - 4}" height="20" '
                f'rx="3" fill="{fill}" stroke="#ffffff"/>'
            )
            if label:
                parts.append(
                    f'<text x="{x + cell_w / 2:.1f}" y="{y + 18}" '
                    'text-anchor="middle" font-size="12" font-weight="700" '
                    f'fill="#ffffff">{label}</text>'
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


def citation_list(citations: list[dict[str, Any]]) -> str:
    items = []
    for citation in citations:
        url = citation["url"]
        href = "../../" + url if url.startswith("docs/") else url
        items.append(f'<li><a href="{esc(href)}">{esc(citation["label"])}</a></li>')
    return '<ul class="citations">' + "".join(items) + "</ul>"


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    uxlc = report["uxlc_inventory"]["summary"]
    current = report["current_psalm_context"]
    layers = report["context_layers"]
    contract = report["context_packet_contract"]
    matrix = report["case_study_matrix"]
    corpus = report["corpus_profile_summary"]
    occurrence_books = ", ".join(current["occurrence_ref_books"].keys()) or "none"

    layer_rows = [
        [
            layer["label"],
            f"{layer['readiness']:.0f}/5",
            f"{layer['weight']:.1f}",
            f"{layer['weighted_gap']:.2f}",
            "; ".join(layer["required_next_evidence"]),
        ]
        for layer in layers
    ]
    contract_table_rows = [
        [
            row["field"],
            "yes" if row["required"] else "no",
            row["current_status"],
            row["description"],
        ]
        for row in contract
    ]
    case_rows = [
        [
            row["unit_id"],
            row["ref"],
            row["covered_layer_count"],
            ", ".join(row["rubric_flags"]),
            row["why"],
        ]
        for row in matrix["rows"]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Psalms Contextual Evaluation</title>
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
    .citations {{ columns: 2; }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
      .citations {{ columns: 1; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AlephTav Psalms Contextual Evaluation</h1>
    <p class="lede">
      A generated report defining how Psalms translation should be assessed
      beyond the Psalm line itself: source Hebrew, morphology, Psalm-local and
      whole-Tanakh context, poetic form, ancient setting, textual witnesses,
      Jewish and Christian reception, and review governance.
    </p>
    <p class="meta">
      Generated {esc(report["generated_on"])} from the contextual rubric,
      current Psalms content, the corpus profile, and the UXLC Tanakh archive.
    </p>
  </header>
  <main>
    <section>
      <h2>Context Readiness</h2>
      {
        metric_cards(
            [
                (
                    "Context layers",
                    fmt_int(summary["context_layer_count"]),
                    "Scholarly evidence layers in the rubric.",
                ),
                (
                    "Stress cases",
                    fmt_int(summary["case_study_count"]),
                    "Seed units mapped to contextual evaluation layers.",
                ),
                (
                    "Weighted readiness",
                    f'''{summary["weighted_readiness_mean"]:.2f}/5''',
                    "Current evidence maturity after layer weights.",
                ),
                (
                    "Weighted gap",
                    f'''{summary["weighted_gap_total"]:.2f}''',
                    "Remaining weighted work before release-grade assessment.",
                ),
            ]
        )
    }
      <div class="warning">
        Current evidence is strong for source control and Psalm-local context,
        but weak for whole-Tanakh retrieval, structured cultural setting, and
        versioned reception history. Those must be built before any local model
        can be treated as an authoritative translation aid.
      </div>
      <div class="chart">{svg_layer_readiness(layers)}</div>
      <div class="chart">{svg_layer_gaps(layers)}</div>
      {
        table(
            ["Layer", "Readiness", "Weight", "Weighted gap", "Required next evidence"],
            layer_rows,
        )
    }
    </section>

    <section>
      <h2>Available Source Inventory</h2>
      {
        metric_cards(
            [
                (
                    "UXLC books",
                    fmt_int(uxlc["books"]),
                    "Canonical book XML files in the raw archive.",
                ),
                (
                    "UXLC chapters",
                    fmt_int(uxlc["chapters"]),
                    "Chapters available for derived indexing.",
                ),
                ("UXLC verses", fmt_int(uxlc["verses"]), "Verses available for derived indexing."),
                (
                    "UXLC words",
                    fmt_int(uxlc["words"]),
                    "Word elements available for lexical indexing.",
                ),
            ]
        )
    }
      <div class="chart">{svg_division_inventory(report)}</div>
      <div class="note">
        Current generated Psalm packets have {fmt_int(current["corpus_occurrence_ref_count"])}
        corpus occurrence references, but those references currently point only
        to {esc(occurrence_books)}. The raw UXLC archive can support a whole-
        Tanakh index, but that index has not yet been built into the model
        evidence packets.
      </div>
      {
        metric_cards(
            [
                (
                    "Psalm units",
                    fmt_int(current["unit_count"]),
                    "Current content units available to the workbench.",
                ),
                (
                    "Psalm tokens",
                    fmt_int(current["token_count"]),
                    "Current content token records.",
                ),
                (
                    "Tokens with occurrence refs",
                    fmt_int(current["tokens_with_corpus_occurrence_refs"]),
                    "Tokens carrying Psalm-local occurrence references.",
                ),
                (
                    "Witness records",
                    fmt_int(corpus.get("witness_records", 0)),
                    "Witness rows reported by the corpus profile.",
                ),
            ]
        )
    }
    </section>

    <section>
      <h2>Context Packet Contract</h2>
      <p>
        The local model should receive an evidence packet with these fields for
        every benchmarked unit. A field marked partial, seed-only, policy-only,
        or missing is not yet release-grade evidence.
      </p>
      <div class="chart">{svg_contract_status(contract)}</div>
      {table(["Field", "Required", "Current status", "Description"], contract_table_rows)}
    </section>

    <section>
      <h2>Stress Case Matrix</h2>
      <p>
        These cases turn known translation and interpretation risks into
        explicit benchmark probes. A good model can translate the Hebrew line,
        name the contextual pressure, and keep reception history out of the
        translation unless the selected layer permits interpretive expansion.
      </p>
      <div class="chart">{svg_case_heatmap(matrix)}</div>
      {table(["Unit", "Reference", "Layers", "Flags", "Reason"], case_rows)}
    </section>

    <section>
      <h2>Citations</h2>
      {citation_list(report["citations"])}
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the Psalms contextual evaluation report."
    )
    parser.add_argument("--rubric", type=Path, default=RUBRIC_PATH)
    parser.add_argument("--corpus-profile", type=Path, default=CORPUS_PROFILE_PATH)
    parser.add_argument("--uxlc-zip", type=Path, default=UXLC_ZIP_PATH)
    parser.add_argument("--content-root", type=Path, default=CONTENT_ROOT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        args.rubric,
        args.corpus_profile,
        args.uxlc_zip,
        args.content_root,
    )
    write_json(args.json_output, report)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
