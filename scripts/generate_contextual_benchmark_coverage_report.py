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
REPORT_ROOT = ROOT / "reports" / "research"
ATLAS_PATH = REPORT_ROOT / "contextual_pressure_atlas.json"
INTEGRATED_SUITE_PATH = REPORT_ROOT / "integrated_benchmark_suite.json"
DOSSIER_PATH = REPORT_ROOT / "priority_unit_dossiers.json"
DEFAULT_JSON_OUTPUT = REPORT_ROOT / "contextual_benchmark_coverage.json"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "contextual_benchmark_coverage_units.csv"
DEFAULT_DOMAIN_CSV_OUTPUT = REPORT_ROOT / "contextual_benchmark_coverage_domains.csv"
DEFAULT_NEXT_CSV_OUTPUT = REPORT_ROOT / "contextual_benchmark_next_units.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "contextual_benchmark_coverage.html"


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


def load_integrated_units(path: Path) -> dict[str, dict[str, Any]]:
    suite = load_json(path)
    units: dict[str, dict[str, Any]] = {}
    for task in suite.get("tasks", []):
        unit_id = str(task["unit_id"])
        row = units.setdefault(
            unit_id,
            {
                "unit_id": unit_id,
                "ref": task.get("ref", ""),
                "task_count": 0,
                "layers": set(),
                "benchmark_tags": Counter(),
                "task_sources": Counter(),
            },
        )
        row["task_count"] += 1
        row["layers"].add(str(task.get("layer", "")))
        row["benchmark_tags"].update(str(tag) for tag in task.get("benchmark_tags", []))
        source = task.get("source") or task.get("task_source") or "integrated"
        row["task_sources"][str(source)] += 1
    for row in units.values():
        row["layers"] = sorted(row["layers"])
        row["benchmark_tags"] = dict(row["benchmark_tags"].most_common())
        row["task_sources"] = dict(row["task_sources"].most_common())
    return units


def load_dossier_units(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = load_json(path)
    rows = {}
    for dossier in data.get("dossiers", []):
        rows[str(dossier["unit_id"])] = {
            "priority_rank": dossier.get("priority_rank"),
            "priority_score": dossier.get("priority", {}).get("score", 0),
            "has_original_benchmark_tasks": bool(
                dossier.get("benchmark_coverage", {}).get("has_benchmark_tasks")
            ),
            "has_original_cross_exam_packets": bool(
                dossier.get("benchmark_coverage", {}).get("has_cross_exam_packets")
            ),
        }
    return rows


def atlas_unit_rows(
    atlas: dict[str, Any],
    integrated_units: dict[str, dict[str, Any]],
    dossier_units: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for rank, atlas_row in enumerate(atlas.get("priority_unit_rows", []), start=1):
        unit_id = str(atlas_row["unit_id"])
        integrated = integrated_units.get(unit_id)
        covered = integrated is not None
        domains = [str(domain) for domain in atlas_row.get("domains", [])]
        domain_groups = [str(group) for group in atlas_row.get("domain_groups", [])]
        frames = [str(frame) for frame in atlas_row.get("required_frames", [])]
        textual = "textual_witness_pressure" in domains
        reception = bool(atlas_row.get("reception_sensitive"))
        dossier = dossier_units.get(unit_id, {})
        priority_score = float(atlas_row.get("priority_score", 0))
        gap_score = 0.0
        if not covered:
            gap_score = priority_score
            if atlas_row.get("context_pressure_intensity") == "high":
                gap_score += 8
            if reception:
                gap_score += 8
            if textual:
                gap_score += 5
            gap_score += max(0, int(atlas_row.get("domain_count", 0)) - 3) * 1.5
        rows.append(
            {
                "priority_rank": rank,
                "unit_id": unit_id,
                "ref": atlas_row.get("ref", ""),
                "psalm_id": atlas_row.get("psalm_id", ""),
                "primary_stratum": atlas_row.get("primary_stratum", ""),
                "covered_by_integrated_benchmark": covered,
                "integrated_task_count": integrated.get("task_count", 0) if integrated else 0,
                "integrated_layers": integrated.get("layers", []) if integrated else [],
                "integrated_benchmark_tags": integrated.get("benchmark_tags", {})
                if integrated
                else {},
                "top25_dossier": unit_id in dossier_units,
                "dossier_priority_rank": dossier.get("priority_rank", ""),
                "priority_score": priority_score,
                "context_pressure_score": atlas_row.get("context_pressure_score", 0),
                "context_pressure_intensity": atlas_row.get(
                    "context_pressure_intensity",
                    "",
                ),
                "domain_count": atlas_row.get("domain_count", 0),
                "domains": domains,
                "domain_groups": domain_groups,
                "reception_sensitive": reception,
                "textual_witness_pressure": textual,
                "required_frames": frames,
                "review_roles": atlas_row.get("review_roles", []),
                "surface_outside_context_pct": atlas_row.get(
                    "surface_outside_context_pct",
                    0,
                ),
                "outside_division_count": atlas_row.get("outside_division_count", 0),
                "coverage_gap_score": round(gap_score, 2),
            }
        )
    return rows


def count_covered(rows: list[dict[str, Any]], predicate: Any) -> tuple[int, int]:
    subset = [row for row in rows if predicate(row)]
    covered = sum(1 for row in subset if row["covered_by_integrated_benchmark"])
    return len(subset), covered


def grouped_coverage_rows(
    rows: list[dict[str, Any]],
    *,
    group_key: str,
    label_key: str,
) -> list[dict[str, Any]]:
    totals: Counter[str] = Counter()
    covered: Counter[str] = Counter()
    for row in rows:
        values = row[group_key]
        if isinstance(values, list):
            labels = [str(value) for value in values]
        else:
            labels = [str(values)]
        for label in labels:
            totals[label] += 1
            if row["covered_by_integrated_benchmark"]:
                covered[label] += 1
    return [
        {
            label_key: label,
            "unit_count": total,
            "covered_count": covered[label],
            "uncovered_count": total - covered[label],
            "coverage_pct": pct(covered[label], total),
        }
        for label, total in totals.most_common()
    ]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    covered_count = sum(1 for row in rows if row["covered_by_integrated_benchmark"])
    high_total, high_covered = count_covered(
        rows,
        lambda row: row["context_pressure_intensity"] == "high",
    )
    reception_total, reception_covered = count_covered(
        rows,
        lambda row: row["reception_sensitive"],
    )
    textual_total, textual_covered = count_covered(
        rows,
        lambda row: row["textual_witness_pressure"],
    )
    top25_total, top25_covered = count_covered(rows, lambda row: row["top25_dossier"])
    broad_total, broad_covered = count_covered(
        rows,
        lambda row: "source_theology_control" in row["domain_groups"],
    )
    ancient_total, ancient_covered = count_covered(
        rows,
        lambda row: "ancient_culture" in row["domain_groups"],
    )
    next_units = [row for row in rows if not row["covered_by_integrated_benchmark"]]
    next_units = sorted(
        next_units,
        key=lambda row: (
            float(row["coverage_gap_score"]),
            float(row["priority_score"]),
            str(row["unit_id"]),
        ),
        reverse=True,
    )
    return {
        "atlas_unit_count": len(rows),
        "integrated_covered_unit_count": covered_count,
        "uncovered_unit_count": len(rows) - covered_count,
        "coverage_pct": pct(covered_count, len(rows)),
        "high_pressure_unit_count": high_total,
        "high_pressure_covered_count": high_covered,
        "high_pressure_coverage_pct": pct(high_covered, high_total),
        "reception_sensitive_unit_count": reception_total,
        "reception_sensitive_covered_count": reception_covered,
        "reception_sensitive_coverage_pct": pct(reception_covered, reception_total),
        "textual_witness_pressure_unit_count": textual_total,
        "textual_witness_pressure_covered_count": textual_covered,
        "textual_witness_pressure_coverage_pct": pct(textual_covered, textual_total),
        "top25_dossier_unit_count": top25_total,
        "top25_dossier_covered_count": top25_covered,
        "top25_dossier_coverage_pct": pct(top25_covered, top25_total),
        "source_theology_control_unit_count": broad_total,
        "source_theology_control_covered_count": broad_covered,
        "source_theology_control_coverage_pct": pct(broad_covered, broad_total),
        "ancient_culture_unit_count": ancient_total,
        "ancient_culture_covered_count": ancient_covered,
        "ancient_culture_coverage_pct": pct(ancient_covered, ancient_total),
        "next_unit_count": len(next_units),
        "top_next_unit": next_units[0]["unit_id"] if next_units else "",
        "top_next_unit_gap_score": next_units[0]["coverage_gap_score"] if next_units else 0,
    }


def build_report(
    atlas_path: Path,
    integrated_suite_path: Path,
    dossier_path: Path,
) -> dict[str, Any]:
    atlas = load_json(atlas_path)
    integrated_units = load_integrated_units(integrated_suite_path)
    dossier_units = load_dossier_units(dossier_path)
    rows = atlas_unit_rows(atlas, integrated_units, dossier_units)
    domain_rows = grouped_coverage_rows(rows, group_key="domains", label_key="domain")
    group_rows = grouped_coverage_rows(
        rows,
        group_key="domain_groups",
        label_key="domain_group",
    )
    stratum_rows = grouped_coverage_rows(
        rows,
        group_key="primary_stratum",
        label_key="stratum",
    )
    frame_rows = grouped_coverage_rows(
        rows,
        group_key="required_frames",
        label_key="frame",
    )
    next_rows = [row for row in rows if not row["covered_by_integrated_benchmark"]]
    next_rows = sorted(
        next_rows,
        key=lambda row: (
            float(row["coverage_gap_score"]),
            float(row["priority_score"]),
            str(row["unit_id"]),
        ),
        reverse=True,
    )
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated contextual benchmark coverage and gap analysis",
        "source_paths": {
            "contextual_pressure_atlas": str(atlas_path.relative_to(ROOT)),
            "integrated_suite": str(integrated_suite_path.relative_to(ROOT)),
            "priority_dossiers": str(dossier_path.relative_to(ROOT)),
        },
        "summary": summarize(rows),
        "domain_coverage_rows": domain_rows,
        "domain_group_coverage_rows": group_rows,
        "stratum_coverage_rows": stratum_rows,
        "required_frame_coverage_rows": frame_rows,
        "unit_coverage_rows": rows,
        "next_unit_rows": next_rows[:40],
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
                "priority_rank": row["priority_rank"],
                "unit_id": row["unit_id"],
                "ref": row["ref"],
                "primary_stratum": row["primary_stratum"],
                "covered_by_integrated_benchmark": row["covered_by_integrated_benchmark"],
                "integrated_task_count": row["integrated_task_count"],
                "top25_dossier": row["top25_dossier"],
                "priority_score": row["priority_score"],
                "context_pressure_intensity": row["context_pressure_intensity"],
                "domain_count": row["domain_count"],
                "domains": "; ".join(row["domains"]),
                "domain_groups": "; ".join(row["domain_groups"]),
                "reception_sensitive": row["reception_sensitive"],
                "textual_witness_pressure": row["textual_witness_pressure"],
                "required_frames": "; ".join(row["required_frames"]),
                "review_roles": "; ".join(row["review_roles"]),
                "surface_outside_context_pct": row["surface_outside_context_pct"],
                "outside_division_count": row["outside_division_count"],
                "coverage_gap_score": row["coverage_gap_score"],
            }
        )
    return flattened


def flatten_domain_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "domain": row.get("domain", row.get("domain_group", row.get("stratum", ""))),
            "unit_count": row["unit_count"],
            "covered_count": row["covered_count"],
            "uncovered_count": row["uncovered_count"],
            "coverage_pct": row["coverage_pct"],
        }
        for row in rows
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
    left = 290
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
    domain_rows = [
        [
            row["domain"],
            row["unit_count"],
            row["covered_count"],
            row["uncovered_count"],
            f"{row['coverage_pct']:.2f}%",
        ]
        for row in report["domain_coverage_rows"]
    ]
    stratum_rows = [
        [
            row["stratum"],
            row["unit_count"],
            row["covered_count"],
            row["uncovered_count"],
            f"{row['coverage_pct']:.2f}%",
        ]
        for row in report["stratum_coverage_rows"]
    ]
    next_rows = [
        [
            row["unit_id"],
            row["ref"],
            row["primary_stratum"],
            row["priority_score"],
            row["coverage_gap_score"],
            ", ".join(row["domains"][:5]),
        ]
        for row in report["next_unit_rows"][:35]
    ]
    next_chart_rows = [
        {
            "unit": f"{row['unit_id']} {row['ref']}",
            "gap_score": row["coverage_gap_score"],
        }
        for row in report["next_unit_rows"][:20]
    ]
    uncovered_domain_rows = sorted(
        report["domain_coverage_rows"],
        key=lambda row: (int(row["uncovered_count"]), int(row["unit_count"])),
        reverse=True,
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Contextual Benchmark Coverage</title>
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
    <h1>AlephTav Contextual Benchmark Coverage</h1>
    <p class="lede">
      Coverage and gap analysis comparing the 100-unit contextual pressure atlas
      with the 72-task integrated runnable benchmark. The goal is to identify
      which cultural, canonical, textual, and reception-sensitive units still
      need benchmark tasks before model performance claims are defensible.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Coverage Snapshot</h2>
      {
        metric_cards(
            [
                (
                    "Atlas coverage",
                    f'''{summary["coverage_pct"]:.2f}%''',
                    (
                        f'''{fmt_int(summary["integrated_covered_unit_count"])} of '''
                        f'''{fmt_int(summary["atlas_unit_count"])} atlas units covered.'''
                    ),
                ),
                (
                    "Uncovered",
                    fmt_int(summary["uncovered_unit_count"]),
                    "Atlas units still without integrated benchmark tasks.",
                ),
                (
                    "Top 25 dossiers",
                    f'''{summary["top25_dossier_coverage_pct"]:.2f}%''',
                    "Highest-priority dossier units now covered by integrated tasks.",
                ),
                (
                    "High pressure",
                    f'''{summary["high_pressure_coverage_pct"]:.2f}%''',
                    (
                        f'''{fmt_int(summary["high_pressure_covered_count"])} of '''
                        f'''{fmt_int(summary["high_pressure_unit_count"])} high-pressure units.'''
                    ),
                ),
                (
                    "Reception",
                    f'''{summary["reception_sensitive_coverage_pct"]:.2f}%''',
                    "Jewish/Christian reception-sensitive atlas units covered.",
                ),
                (
                    "Textual",
                    f'''{summary["textual_witness_pressure_coverage_pct"]:.2f}%''',
                    "Textual-witness/provenance-pressure units covered.",
                ),
                (
                    "Ancient culture",
                    f'''{summary["ancient_culture_coverage_pct"]:.2f}%''',
                    "Ancient cultural-domain atlas units covered.",
                ),
                (
                    "Next unit",
                    summary["top_next_unit"],
                    f'''Gap score {summary["top_next_unit_gap_score"]:.2f}.''',
                ),
            ]
        )
    }
      <div class="warning">
        The integrated benchmark is reviewer-ready for its selected units, but
        it is not yet a full 100-unit contextual benchmark. Remaining gaps should
        guide the next supplement before claiming broad translation authority.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            next_chart_rows,
            label_key="unit",
            value_key="gap_score",
            aria_label="Top uncovered benchmark units by gap score",
            color="#9b3d3d",
        )
    }</div>
    </section>

    <section>
      <h2>Domain Coverage</h2>
      <div class="chart">{
        svg_horizontal_bars(
            uncovered_domain_rows,
            label_key="domain",
            value_key="uncovered_count",
            aria_label="Uncovered unit counts by contextual domain",
            color="#7c5b2f",
        )
    }</div>
      {table(["Domain", "Units", "Covered", "Uncovered", "Coverage"], domain_rows)}
    </section>

    <section>
      <h2>Stratum Coverage</h2>
      {table(["Stratum", "Units", "Covered", "Uncovered", "Coverage"], stratum_rows)}
    </section>

    <section>
      <h2>Next Units</h2>
      {
        table(
            ["Unit", "Reference", "Stratum", "Priority", "Gap score", "Domains"],
            next_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate contextual benchmark coverage and gap analysis."
    )
    parser.add_argument("--atlas", type=Path, default=ATLAS_PATH)
    parser.add_argument("--suite", type=Path, default=INTEGRATED_SUITE_PATH)
    parser.add_argument("--dossiers", type=Path, default=DOSSIER_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument(
        "--domain-csv-output",
        type=Path,
        default=DEFAULT_DOMAIN_CSV_OUTPUT,
    )
    parser.add_argument("--next-csv-output", type=Path, default=DEFAULT_NEXT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.atlas, args.suite, args.dossiers)
    write_json(args.json_output, report)
    write_csv(args.unit_csv_output, flatten_unit_rows(report["unit_coverage_rows"]))
    write_csv(args.domain_csv_output, flatten_domain_rows(report["domain_coverage_rows"]))
    write_csv(args.next_csv_output, flatten_unit_rows(report["next_unit_rows"]))
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.unit_csv_output}")
    print(f"Wrote {args.domain_csv_output}")
    print(f"Wrote {args.next_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
