from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = ROOT / "content" / "psalms"
RAW_ROOT = ROOT / "data" / "raw"
ATLAS_PATH = ROOT / "reports" / "research" / "contextual_pressure_atlas.json"
INTEGRATED_SUITE_PATH = ROOT / "reports" / "research" / "integrated_benchmark_suite.json"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "witness_reception_readiness.json"
DEFAULT_UNIT_CSV_OUTPUT = ROOT / "reports" / "research" / "witness_reception_units.csv"
DEFAULT_FRAME_CSV_OUTPUT = ROOT / "reports" / "research" / "reception_frame_routing.csv"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "witness_reception_readiness.html"

EXPECTED_WITNESS_SOURCES = ["lxx", "kjv", "asv", "web"]
RECEPTION_TAGS = {
    "reception_history",
    "jewish_christian_reception",
    "jewish_christian_reception_cases",
    "messianic_interpretation",
    "liturgical_afterlife",
    "ethical_reception",
}
TEXTUAL_TAGS = {
    "textual_witness",
    "textual_witness_cases",
    "textual_sensitivity",
    "lexical_dispute",
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


def manifest_rows(raw_root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(raw_root.glob("*/manifest.json")):
        manifest = load_json(path)
        rows.append(
            {
                "source_id": manifest.get("source_id", path.parent.name),
                "name": manifest.get("name", ""),
                "source_language": manifest.get("source_language", ""),
                "basis_role": manifest.get("basis_role", ""),
                "license": manifest.get("license", ""),
                "version": manifest.get("version", ""),
                "allowed_for_display": bool(manifest.get("allowed_for_display")),
                "allowed_for_export": bool(manifest.get("allowed_for_export")),
                "allowed_for_generation": bool(manifest.get("allowed_for_generation")),
                "version_pinned": bool(manifest.get("version_pinned", True)),
                "notes": manifest.get("notes", ""),
                "manifest_path": str(path.relative_to(ROOT)),
            }
        )
    return rows


def scan_witness_units(content_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    unit_rows = []
    source_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    psalm_counts: Counter[str] = Counter()
    witness_record_count = 0
    for path in sorted(content_root.glob("ps*/*.v*.json")):
        unit = load_json(path)
        witnesses = unit.get("witnesses", [])
        sources = Counter()
        languages = Counter()
        roles = Counter()
        for witness in witnesses:
            source_id = str(witness.get("source_id") or "")
            language = str(witness.get("language") or "")
            role = str(witness.get("witness_role") or "")
            source_counts[source_id] += 1
            language_counts[language] += 1
            role_counts[role] += 1
            sources[source_id] += 1
            languages[language] += 1
            roles[role] += 1
            witness_record_count += 1
        missing_sources = [source for source in EXPECTED_WITNESS_SOURCES if source not in sources]
        unit_id = str(unit["unit_id"])
        psalm_id = unit_id.split(".")[0]
        psalm_counts[psalm_id] += 1
        unit_rows.append(
            {
                "unit_id": unit_id,
                "ref": unit.get("ref", ""),
                "psalm_id": psalm_id,
                "witness_count": len(witnesses),
                "source_counts": dict(sources.most_common()),
                "language_counts": dict(languages.most_common()),
                "role_counts": dict(roles.most_common()),
                "has_lxx": "lxx" in sources,
                "english_witness_count": sum(
                    count for language, count in languages.items() if language == "en"
                ),
                "missing_expected_witness_sources": missing_sources,
                "complete_expected_witness_set": not missing_sources,
            }
        )
    summary = {
        "unit_count": len(unit_rows),
        "psalm_count": len(psalm_counts),
        "witness_record_count": witness_record_count,
        "source_counts": dict(source_counts.most_common()),
        "language_counts": dict(language_counts.most_common()),
        "role_counts": dict(role_counts.most_common()),
        "units_with_lxx": sum(1 for row in unit_rows if row["has_lxx"]),
        "units_with_english_witness": sum(
            1 for row in unit_rows if int(row["english_witness_count"]) > 0
        ),
        "units_with_complete_expected_witness_set": sum(
            1 for row in unit_rows if row["complete_expected_witness_set"]
        ),
    }
    summary["lxx_coverage_pct"] = pct(summary["units_with_lxx"], summary["unit_count"])
    summary["english_witness_coverage_pct"] = pct(
        summary["units_with_english_witness"],
        summary["unit_count"],
    )
    summary["complete_expected_witness_set_pct"] = pct(
        summary["units_with_complete_expected_witness_set"],
        summary["unit_count"],
    )
    return unit_rows, summary


def load_integrated_unit_tags(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    suite = load_json(path)
    units: dict[str, dict[str, Any]] = {}
    for task in suite.get("tasks", []):
        unit_id = str(task["unit_id"])
        row = units.setdefault(
            unit_id,
            {
                "unit_id": unit_id,
                "ref": task["ref"],
                "task_count": 0,
                "layers": set(),
                "benchmark_tags": Counter(),
            },
        )
        row["task_count"] += 1
        row["layers"].add(str(task["layer"]))
        row["benchmark_tags"].update(str(tag) for tag in task.get("benchmark_tags", []))
    for row in units.values():
        row["layers"] = sorted(row["layers"])
        row["benchmark_tags"] = dict(row["benchmark_tags"].most_common())
    return units


def atlas_rows(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if not path.exists():
        return {}, {}
    atlas = load_json(path)
    rows = {str(row["unit_id"]): row for row in atlas.get("priority_unit_rows", [])}
    return atlas.get("summary", {}), rows


def frame_rows(
    atlas_by_unit: dict[str, dict[str, Any]],
    integrated_units: dict[str, dict[str, Any]],
    witness_by_unit: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for unit_id, atlas in atlas_by_unit.items():
        integrated = integrated_units.get(unit_id, {})
        witness = witness_by_unit.get(unit_id, {})
        tags = integrated.get("benchmark_tags", {})
        reception_by_tag = any(tag in RECEPTION_TAGS for tag in tags)
        textual_by_tag = any(tag in TEXTUAL_TAGS for tag in tags)
        if not (
            atlas.get("reception_sensitive")
            or "textual_witness_pressure" in atlas.get("domains", [])
            or unit_id in integrated_units
        ):
            continue
        rows.append(
            {
                "unit_id": unit_id,
                "ref": atlas.get("ref", integrated.get("ref", "")),
                "integrated_task_count": integrated.get("task_count", 0),
                "reception_sensitive": bool(atlas.get("reception_sensitive")) or reception_by_tag,
                "textual_witness_pressure": (
                    "textual_witness_pressure" in atlas.get("domains", []) or textual_by_tag
                ),
                "priority_score": atlas.get("priority_score", 0),
                "domains": atlas.get("domains", []),
                "required_frames": atlas.get("required_frames", []),
                "review_roles": atlas.get("review_roles", []),
                "witness_count": witness.get("witness_count", 0),
                "complete_expected_witness_set": bool(witness.get("complete_expected_witness_set")),
                "missing_expected_witness_sources": witness.get(
                    "missing_expected_witness_sources",
                    [],
                ),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            bool(row["reception_sensitive"]),
            bool(row["textual_witness_pressure"]),
            float(row["priority_score"]),
            int(row["integrated_task_count"]),
        ),
        reverse=True,
    )


def source_policy_rows(
    manifests: list[dict[str, Any]],
    used_source_counts: dict[str, int],
) -> list[dict[str, Any]]:
    source_ids = set(EXPECTED_WITNESS_SOURCES) | {"sefaria", "uxlc", "oshb", "macula"}
    rows = []
    for manifest in manifests:
        source_id = str(manifest["source_id"])
        if source_id not in source_ids and source_id not in used_source_counts:
            continue
        rows.append(
            {
                "source_id": source_id,
                "name": manifest["name"],
                "language": manifest["source_language"],
                "basis_role": manifest["basis_role"],
                "license": manifest["license"],
                "version": manifest["version"],
                "witness_records": used_source_counts.get(source_id, 0),
                "display": manifest["allowed_for_display"],
                "export": manifest["allowed_for_export"],
                "generation": manifest["allowed_for_generation"],
                "version_pinned": manifest["version_pinned"],
            }
        )
    return sorted(rows, key=lambda row: str(row["source_id"]))


def summarize(
    witness_summary: dict[str, Any],
    source_policies: list[dict[str, Any]],
    atlas_summary: dict[str, Any],
    frame_rows_list: list[dict[str, Any]],
    integrated_units: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    integrated_unit_ids = set(integrated_units)
    integrated_reception_units = {
        unit_id
        for unit_id, row in integrated_units.items()
        if any(tag in RECEPTION_TAGS for tag in row["benchmark_tags"])
    }
    integrated_textual_units = {
        unit_id
        for unit_id, row in integrated_units.items()
        if any(tag in TEXTUAL_TAGS for tag in row["benchmark_tags"])
    }
    policy_generation_false = [
        row["source_id"]
        for row in source_policies
        if row["witness_records"] and not row["generation"]
    ]
    return {
        **witness_summary,
        "source_policy_count": len(source_policies),
        "witness_sources_not_allowed_for_generation": policy_generation_false,
        "witness_source_generation_block_count": len(policy_generation_false),
        "atlas_reception_sensitive_units": atlas_summary.get(
            "reception_sensitive_unit_count",
            0,
        ),
        "atlas_textual_witness_pressure_units": atlas_summary.get(
            "textual_witness_pressure_unit_count",
            0,
        ),
        "integrated_unit_count": len(integrated_unit_ids),
        "integrated_reception_sensitive_units": len(integrated_reception_units),
        "integrated_textual_witness_units": len(integrated_textual_units),
        "routing_row_count": len(frame_rows_list),
    }


def build_report(
    content_root: Path,
    raw_root: Path,
    atlas_path: Path,
    integrated_suite_path: Path,
) -> dict[str, Any]:
    manifests = manifest_rows(raw_root)
    unit_rows, witness_summary = scan_witness_units(content_root)
    witness_by_unit = {row["unit_id"]: row for row in unit_rows}
    integrated_units = load_integrated_unit_tags(integrated_suite_path)
    atlas_summary, atlas_by_unit = atlas_rows(atlas_path)
    routing_rows = frame_rows(atlas_by_unit, integrated_units, witness_by_unit)
    policies = source_policy_rows(manifests, witness_summary["source_counts"])
    frame_counter: Counter[str] = Counter()
    domain_counter: Counter[str] = Counter()
    for row in routing_rows:
        frame_counter.update(row["required_frames"])
        domain_counter.update(row["domains"])
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated witness and reception readiness audit",
        "source_paths": {
            "content_root": "content/psalms",
            "raw_root": "data/raw",
            "contextual_pressure_atlas": "reports/research/contextual_pressure_atlas.json",
            "integrated_suite": "reports/research/integrated_benchmark_suite.json",
        },
        "summary": summarize(
            witness_summary,
            policies,
            atlas_summary,
            routing_rows,
            integrated_units,
        ),
        "source_policy_rows": policies,
        "source_counts": witness_summary["source_counts"],
        "language_counts": witness_summary["language_counts"],
        "role_counts": witness_summary["role_counts"],
        "required_frame_counts": dict(frame_counter.most_common()),
        "routing_domain_counts": dict(domain_counter.most_common()),
        "witness_unit_rows": unit_rows,
        "reception_frame_rows": routing_rows,
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


def flatten_unit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for row in rows:
        flattened.append(
            {
                "unit_id": row["unit_id"],
                "ref": row["ref"],
                "witness_count": row["witness_count"],
                "sources": "; ".join(row["source_counts"].keys()),
                "languages": "; ".join(row["language_counts"].keys()),
                "has_lxx": row["has_lxx"],
                "english_witness_count": row["english_witness_count"],
                "complete_expected_witness_set": row["complete_expected_witness_set"],
                "missing_expected_witness_sources": "; ".join(
                    row["missing_expected_witness_sources"]
                ),
            }
        )
    return flattened


def flatten_frame_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = []
    for row in rows:
        flattened.append(
            {
                "unit_id": row["unit_id"],
                "ref": row["ref"],
                "integrated_task_count": row["integrated_task_count"],
                "reception_sensitive": row["reception_sensitive"],
                "textual_witness_pressure": row["textual_witness_pressure"],
                "priority_score": row["priority_score"],
                "domains": "; ".join(row["domains"]),
                "required_frames": "; ".join(row["required_frames"]),
                "review_roles": "; ".join(row["review_roles"]),
                "witness_count": row["witness_count"],
                "complete_expected_witness_set": row["complete_expected_witness_set"],
                "missing_expected_witness_sources": "; ".join(
                    row["missing_expected_witness_sources"]
                ),
            }
        )
    return flattened


def rows_from_counter(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
    return [
        {label_key: key or "(blank)", "count": value}
        for key, value in sorted(counter.items(), key=lambda item: item[1], reverse=True)
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
    policy_rows = [
        [
            row["source_id"],
            row["basis_role"],
            row["license"],
            row["witness_records"],
            row["display"],
            row["export"],
            row["generation"],
        ]
        for row in report["source_policy_rows"]
    ]
    frame_rows = [
        [
            row["unit_id"],
            row["ref"],
            row["reception_sensitive"],
            row["textual_witness_pressure"],
            ", ".join(row["required_frames"]),
            row["witness_count"],
        ]
        for row in report["reception_frame_rows"][:35]
    ]
    source_chart = rows_from_counter(report["source_counts"], "source")
    frame_chart = rows_from_counter(report["required_frame_counts"], "frame")
    domain_chart = rows_from_counter(report["routing_domain_counts"], "domain")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Witness and Reception Readiness</title>
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
    <h1>AlephTav Witness and Reception Readiness</h1>
    <p class="lede">
      Provenance-focused audit of witness coverage, license boundaries, and
      reception-sensitive routing. Counts are derived from current Psalm unit
      JSON, raw source manifests, the contextual pressure atlas, and the
      integrated benchmark suite.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Witness Snapshot</h2>
      {
        metric_cards(
            [
                (
                    "Witness rows",
                    fmt_int(summary["witness_record_count"]),
                    (
                        f'''{fmt_int(summary["unit_count"])} Psalm units; '''
                        f'''{summary["psalm_count"]} Psalms.'''
                    ),
                ),
                (
                    "LXX coverage",
                    f'''{summary["lxx_coverage_pct"]:.2f}%''',
                    f'''{fmt_int(summary["units_with_lxx"])} units with Greek witness.''',
                ),
                (
                    "English coverage",
                    f'''{summary["english_witness_coverage_pct"]:.2f}%''',
                    "Units with at least one public-domain English witness.",
                ),
                (
                    "Complete set",
                    f'''{summary["complete_expected_witness_set_pct"]:.2f}%''',
                    "Units with LXX, KJV, ASV, and WEB witness rows.",
                ),
                (
                    "Reception units",
                    fmt_int(summary["atlas_reception_sensitive_units"]),
                    "100-unit atlas rows needing Jewish/Christian routing.",
                ),
                (
                    "Textual pressure",
                    fmt_int(summary["atlas_textual_witness_pressure_units"]),
                    "100-unit atlas rows needing witness/provenance care.",
                ),
                (
                    "Integrated reception",
                    fmt_int(summary["integrated_reception_sensitive_units"]),
                    "Integrated benchmark units with reception tags.",
                ),
                (
                    "Generation blocks",
                    fmt_int(summary["witness_source_generation_block_count"]),
                    "Used witness sources not allowed for generation.",
                ),
            ]
        )
    }
      <div class="warning">
        Witnesses are evidence, not canonical source text. Public-domain English
        witnesses are display/export evidence in this repo but are not approved
        as generation sources; reception frames must remain tagged viewpoints.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            source_chart,
            label_key="source",
            value_key="count",
            aria_label="Witness source counts",
            color="#2f6f73",
        )
    }</div>
    </section>

    <section>
      <h2>Source Policy</h2>
      {
        table(
            [
                "Source",
                "Basis role",
                "License",
                "Witness rows",
                "Display",
                "Export",
                "Generation",
            ],
            policy_rows,
        )
    }
    </section>

    <section>
      <h2>Reception Routing</h2>
      <div class="chart">{
        svg_horizontal_bars(
            frame_chart,
            label_key="frame",
            value_key="count",
            aria_label="Required reception frame counts",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            domain_chart,
            label_key="domain",
            value_key="count",
            aria_label="Reception routing domain counts",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            [
                "Unit",
                "Reference",
                "Reception",
                "Textual",
                "Required frames",
                "Witness rows",
            ],
            frame_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate witness and reception readiness report.")
    parser.add_argument("--content-root", type=Path, default=CONTENT_ROOT)
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    parser.add_argument("--atlas", type=Path, default=ATLAS_PATH)
    parser.add_argument("--suite", type=Path, default=INTEGRATED_SUITE_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--frame-csv-output", type=Path, default=DEFAULT_FRAME_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.content_root, args.raw_root, args.atlas, args.suite)
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, flatten_unit_rows(report["witness_unit_rows"]))
    write_csv(
        args.frame_csv_output,
        flatten_frame_rows(report["reception_frame_rows"]),
    )
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.frame_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
