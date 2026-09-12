from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"

SOURCE_REPORTS = [
    {
        "lane_id": "canonical_intertext",
        "lane_label": "Canonical Intertext",
        "context_focus": "Broader Old Testament surface-form pressure",
        "path": REPORT_ROOT / "canonical_intertext_real_smoke_report.json",
    },
    {
        "lane_id": "reception_signal",
        "lane_label": "Reception Signal",
        "context_focus": "Jewish/Christian reception-sensitive pressure",
        "path": REPORT_ROOT / "reception_signal_real_smoke_report.json",
    },
    {
        "lane_id": "doctoral_collision",
        "lane_label": "Doctoral Collision",
        "context_focus": "Cross-lens canon/culture/witness/reception collision pressure",
        "path": REPORT_ROOT / "doctoral_collision_real_smoke_report.json",
    },
]

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "contextual_real_model_evidence_matrix.json"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "contextual_real_model_evidence_matrix.html"
DEFAULT_CSV_OUTPUT = REPORT_ROOT / "contextual_real_model_evidence_matrix_attempts.csv"


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


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def planned_model_task_count(summary: dict[str, Any]) -> int:
    return int(
        summary.get("expected_model_task_count")
        or summary.get("suite_planned_model_runs")
        or (
            int(summary.get("attempt_count", 0))
            + int(summary.get("missing_model_task_count_after_smoke", 0))
        )
    )


def covered_model_task_count(summary: dict[str, Any]) -> int:
    return int(
        summary.get("valid_model_task_count") or summary.get("schema_valid_attempt_count") or 0
    )


def normalized_attempt_rows(source: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in report.get("attempt_rows", []):
        task_id = str(row.get("task_id") or "")
        ref = str(row.get("ref") or "")
        schema_valid = bool(row.get("schema_valid"))
        anchor_issues = int(row.get("source_anchor_issue_count") or 0)
        reception_leaks = int(row.get("reception_leak_term_count") or 0)
        rows.append(
            {
                "lane_id": source["lane_id"],
                "lane_label": source["lane_label"],
                "context_focus": source["context_focus"],
                "attempt_id": row.get("attempt_id", ""),
                "label": row.get("label", ""),
                "model_profile_id": row.get("model_profile_id", ""),
                "model_family": row.get("model_family", ""),
                "task_id": task_id,
                "unit_id": row.get("unit_id", ""),
                "ref": ref,
                "layer": row.get("layer", ""),
                "schema_valid": schema_valid,
                "clean_source_anchored": schema_valid and anchor_issues == 0,
                "candidate_count": int(row.get("candidate_count") or 0),
                "error_count": int(row.get("error_count") or 0),
                "errors": row.get("errors") or [],
                "source_anchor_issue_count": anchor_issues,
                "reception_leak_term_count": reception_leaks,
                "invalid_token_ref_count": int(row.get("invalid_token_ref_count") or 0),
                "elapsed_ms": float(row.get("elapsed_ms") or 0.0),
                "mean_alignment_score_0_5": float(row.get("mean_alignment_score_0_5") or 0.0),
                "mean_translation_basis_score_0_5": float(
                    row.get("mean_translation_basis_score_0_5") or 0.0
                ),
                "candidate_text": str(row.get("candidate_text") or ""),
                "source_anchor_text": str(row.get("source_anchor_text") or ""),
                "result_path": str(row.get("result_path") or ""),
                "audit_path": str(row.get("audit_path") or ""),
            }
        )
    return rows


def build_lane_rows(source_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source in source_reports:
        report = load_json(source["path"])
        summary = report["summary"]
        planned = planned_model_task_count(summary)
        valid = covered_model_task_count(summary)
        rows.append(
            {
                "lane_id": source["lane_id"],
                "lane_label": source["lane_label"],
                "context_focus": source["context_focus"],
                "source_report": str(source["path"].relative_to(ROOT)),
                "planned_model_task_count": planned,
                "attempt_count": int(summary.get("attempt_count") or 0),
                "model_count": int(summary.get("model_count") or 0),
                "unique_task_real_evidence_count": int(
                    summary.get("unique_task_real_evidence_count") or summary.get("task_count") or 0
                ),
                "schema_valid_attempt_count": int(summary.get("schema_valid_attempt_count") or 0),
                "schema_valid_attempt_pct": float(summary.get("schema_valid_attempt_pct") or 0.0),
                "clean_schema_valid_attempt_count": int(
                    summary.get("clean_schema_valid_attempt_count") or 0
                ),
                "clean_schema_valid_attempt_pct": float(
                    summary.get("clean_schema_valid_attempt_pct") or 0.0
                ),
                "valid_model_task_count": valid,
                "valid_model_task_coverage_pct": pct(valid, planned),
                "missing_model_task_count_after_smoke": int(
                    summary.get("missing_model_task_count_after_smoke") or 0
                ),
                "source_anchor_issue_count": int(summary.get("source_anchor_issue_count") or 0),
                "reception_leak_term_count": int(summary.get("reception_leak_term_count") or 0),
                "clean_best_model_profile": summary.get("clean_best_model_profile") or "",
                "fastest_valid_model_profile": summary.get("fastest_valid_model_profile") or "",
            }
        )
    return rows


def build_model_rows(attempt_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in attempt_rows:
        groups[str(row["model_profile_id"])].append(row)
    rows = []
    for model, model_attempts in groups.items():
        schema_valid = sum(1 for row in model_attempts if row["schema_valid"])
        clean = sum(1 for row in model_attempts if row["clean_source_anchored"])
        anchor_issues = sum(int(row["source_anchor_issue_count"]) for row in model_attempts)
        reception_leaks = sum(int(row["reception_leak_term_count"]) for row in model_attempts)
        lanes = sorted({str(row["lane_label"]) for row in model_attempts})
        clean_lanes = sorted(
            {
                str(row["lane_label"])
                for row in model_attempts
                if row["schema_valid"] and int(row["source_anchor_issue_count"]) == 0
            }
        )
        rows.append(
            {
                "model_profile_id": model,
                "model_family": model_attempts[0].get("model_family") or model,
                "attempt_count": len(model_attempts),
                "schema_valid_attempt_count": schema_valid,
                "schema_valid_pct": pct(schema_valid, len(model_attempts)),
                "clean_source_anchored_count": clean,
                "clean_source_anchored_pct": pct(clean, len(model_attempts)),
                "source_anchor_issue_count": anchor_issues,
                "reception_leak_term_count": reception_leaks,
                "mean_elapsed_ms": mean([float(row["elapsed_ms"]) for row in model_attempts]),
                "mean_alignment_score_0_5": mean(
                    [float(row["mean_alignment_score_0_5"]) for row in model_attempts]
                ),
                "mean_translation_basis_score_0_5": mean(
                    [float(row["mean_translation_basis_score_0_5"]) for row in model_attempts]
                ),
                "lane_count": len(lanes),
                "lanes_covered": lanes,
                "clean_lane_count": len(clean_lanes),
                "clean_lanes": clean_lanes,
                "evidence_role": evidence_role(clean, anchor_issues, len(model_attempts)),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -int(row["clean_source_anchored_count"]),
            int(row["source_anchor_issue_count"]),
            float(row["mean_elapsed_ms"]),
        ),
    )


def evidence_role(clean_count: int, anchor_issue_count: int, attempt_count: int) -> str:
    if attempt_count and clean_count == attempt_count:
        return "clean-current-local-comparator"
    if clean_count and anchor_issue_count == 0:
        return "clean-with-runtime-budget-caveat"
    if clean_count and anchor_issue_count:
        return "usable-with-anchor-review"
    if anchor_issue_count:
        return "anchor-repair-required-before-authority-use"
    return "insufficient-evidence"


def build_model_lane_rows(attempt_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in attempt_rows:
        groups[(str(row["model_profile_id"]), str(row["lane_id"]))].append(row)
    rows = []
    for (model, lane_id), group in groups.items():
        schema_valid = sum(1 for row in group if row["schema_valid"])
        clean = sum(1 for row in group if row["clean_source_anchored"])
        rows.append(
            {
                "model_profile_id": model,
                "lane_id": lane_id,
                "lane_label": group[0]["lane_label"],
                "attempt_count": len(group),
                "schema_valid_attempt_count": schema_valid,
                "schema_valid_pct": pct(schema_valid, len(group)),
                "clean_source_anchored_count": clean,
                "clean_source_anchored_pct": pct(clean, len(group)),
                "source_anchor_issue_count": sum(
                    int(row["source_anchor_issue_count"]) for row in group
                ),
                "reception_leak_term_count": sum(
                    int(row["reception_leak_term_count"]) for row in group
                ),
                "mean_elapsed_ms": mean([float(row["elapsed_ms"]) for row in group]),
                "task_refs": sorted({str(row["ref"]) for row in group if row.get("ref")}),
            }
        )
    return sorted(rows, key=lambda row: (row["lane_id"], row["model_profile_id"]))


def build_summary(
    lane_rows: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
    attempt_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    planned_total = sum(int(row["planned_model_task_count"]) for row in lane_rows)
    valid_total = sum(int(row["valid_model_task_count"]) for row in lane_rows)
    clean_total = sum(1 for row in attempt_rows if row["clean_source_anchored"])
    best_model = model_rows[0]["model_profile_id"] if model_rows else ""
    fastest_clean = sorted(
        [row for row in attempt_rows if row["clean_source_anchored"] and row["elapsed_ms"]],
        key=lambda row: float(row["elapsed_ms"]),
    )
    return {
        "lane_count": len(lane_rows),
        "model_count": len(model_rows),
        "planned_model_task_count": planned_total,
        "attempt_count": len(attempt_rows),
        "unique_task_real_evidence_count": len({row["task_id"] for row in attempt_rows}),
        "schema_valid_attempt_count": sum(1 for row in attempt_rows if row["schema_valid"]),
        "schema_valid_attempt_pct": pct(
            sum(1 for row in attempt_rows if row["schema_valid"]),
            len(attempt_rows),
        ),
        "clean_source_anchored_count": clean_total,
        "clean_source_anchored_pct": pct(clean_total, len(attempt_rows)),
        "source_anchor_issue_count": sum(
            int(row["source_anchor_issue_count"]) for row in attempt_rows
        ),
        "reception_leak_term_count": sum(
            int(row["reception_leak_term_count"]) for row in attempt_rows
        ),
        "valid_model_task_count": valid_total,
        "valid_model_task_coverage_pct": pct(valid_total, planned_total),
        "missing_model_task_count_after_smoke": sum(
            int(row["missing_model_task_count_after_smoke"]) for row in lane_rows
        ),
        "best_clean_model_profile": best_model,
        "fastest_clean_model_profile": (
            fastest_clean[0]["model_profile_id"] if fastest_clean else ""
        ),
        "fastest_clean_elapsed_ms": round(float(fastest_clean[0]["elapsed_ms"]), 2)
        if fastest_clean
        else 0.0,
        "lane_with_most_missing_rows": max(
            lane_rows,
            key=lambda row: int(row["missing_model_task_count_after_smoke"]),
        )["lane_label"]
        if lane_rows
        else "",
        "authority_verdict": (
            "Real local model evidence has expanded across canonical-intertext, "
            "reception-sensitive, and collision lanes, but the measured coverage is "
            "still a smoke matrix rather than authority-level model certification."
        ),
    }


def build_visual_data(
    lane_rows: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "lane_attempt_rows": [
            {"label": row["lane_label"], "value": row["attempt_count"]} for row in lane_rows
        ],
        "lane_valid_coverage_rows": [
            {"label": row["lane_label"], "value": row["valid_model_task_coverage_pct"]}
            for row in lane_rows
        ],
        "lane_missing_rows": [
            {"label": row["lane_label"], "value": row["missing_model_task_count_after_smoke"]}
            for row in lane_rows
        ],
        "lane_anchor_issue_rows": [
            {"label": row["lane_label"], "value": row["source_anchor_issue_count"]}
            for row in lane_rows
        ],
        "model_clean_rows": [
            {"label": row["model_profile_id"], "value": row["clean_source_anchored_count"]}
            for row in model_rows
        ],
        "model_anchor_issue_rows": [
            {"label": row["model_profile_id"], "value": row["source_anchor_issue_count"]}
            for row in model_rows
        ],
        "model_elapsed_rows": [
            {
                "label": row["model_profile_id"],
                "value": round(float(row["mean_elapsed_ms"]) / 1000, 2),
            }
            for row in model_rows
        ],
    }


def build_report() -> dict[str, Any]:
    attempt_rows: list[dict[str, Any]] = []
    source_paths: dict[str, str] = {}
    for source in SOURCE_REPORTS:
        report = load_json(source["path"])
        source_paths[source["lane_id"]] = str(source["path"].relative_to(ROOT))
        attempt_rows.extend(normalized_attempt_rows(source, report))
    lane_rows = build_lane_rows(SOURCE_REPORTS)
    model_rows = build_model_rows(attempt_rows)
    model_lane_rows = build_model_lane_rows(attempt_rows)
    summary = build_summary(lane_rows, model_rows, attempt_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "contextual real model evidence matrix generated; not authority signoff",
        "source_paths": source_paths,
        "authority_policy": (
            "This matrix compares measured local smoke outputs only. It cannot approve "
            "a translation, replace source review, or satisfy release authority."
        ),
        "summary": summary,
        "lane_rows": lane_rows,
        "model_rows": model_rows,
        "model_lane_rows": model_lane_rows,
        "attempt_rows": attempt_rows,
        "visual_data": build_visual_data(lane_rows, model_rows),
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
    left = 310
    right = 70
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
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="19" rx="3" fill="{color}"/>'
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
    visual = report["visual_data"]
    attempt_note = (
        f"{fmt_int(summary['unique_task_real_evidence_count'])} unique tasks "
        f"across {fmt_int(summary['lane_count'])} lanes."
    )
    schema_note = f"{summary['schema_valid_attempt_pct']:.2f}% of local smoke attempts."
    clean_note = f"{summary['clean_source_anchored_pct']:.2f}% without source-anchor issues."
    anchor_note = f"{fmt_int(summary['reception_leak_term_count'])} reception leak terms flagged."
    coverage_value = f"{summary['valid_model_task_coverage_pct']:.2f}%"
    coverage_note = (
        f"{fmt_int(summary['valid_model_task_count'])} valid model-task rows "
        f"out of {fmt_int(summary['planned_model_task_count'])} planned."
    )
    missing_note = f"Most missing rows: {summary['lane_with_most_missing_rows']}."
    fastest_note = (
        f"{float(summary['fastest_clean_elapsed_ms']) / 1000:.2f}s fastest clean attempt."
    )
    lane_rows = [
        [
            row["lane_label"],
            row["context_focus"],
            fmt_int(row["planned_model_task_count"]),
            fmt_int(row["attempt_count"]),
            fmt_int(row["schema_valid_attempt_count"]),
            fmt_int(row["clean_schema_valid_attempt_count"]),
            f"{row['valid_model_task_coverage_pct']:.2f}%",
            fmt_int(row["missing_model_task_count_after_smoke"]),
            fmt_int(row["source_anchor_issue_count"]),
            row["clean_best_model_profile"],
        ]
        for row in report["lane_rows"]
    ]
    model_rows = [
        [
            row["model_profile_id"],
            fmt_int(row["attempt_count"]),
            fmt_int(row["schema_valid_attempt_count"]),
            f"{row['schema_valid_pct']:.2f}%",
            fmt_int(row["clean_source_anchored_count"]),
            f"{row['clean_source_anchored_pct']:.2f}%",
            fmt_int(row["source_anchor_issue_count"]),
            f"{float(row['mean_elapsed_ms']) / 1000:.2f}s",
            "; ".join(row["clean_lanes"]),
            row["evidence_role"],
        ]
        for row in report["model_rows"]
    ]
    model_lane_rows = [
        [
            row["lane_label"],
            row["model_profile_id"],
            fmt_int(row["attempt_count"]),
            fmt_int(row["schema_valid_attempt_count"]),
            fmt_int(row["clean_source_anchored_count"]),
            fmt_int(row["source_anchor_issue_count"]),
            f"{float(row['mean_elapsed_ms']) / 1000:.2f}s",
            "; ".join(row["task_refs"]),
        ]
        for row in report["model_lane_rows"]
    ]
    attempt_rows = [
        [
            row["lane_label"],
            row["model_profile_id"],
            row["ref"],
            row["layer"],
            "yes" if row["schema_valid"] else "no",
            "yes" if row["clean_source_anchored"] else "no",
            fmt_int(row["source_anchor_issue_count"]),
            fmt_int(row["reception_leak_term_count"]),
            f"{float(row['elapsed_ms']) / 1000:.2f}s",
            row["candidate_text"],
        ]
        for row in report["attempt_rows"]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Contextual Real Model Evidence Matrix</title>
  <style>
    :root {{
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
      background: #fff;
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
    <h1>Contextual Real Model Evidence Matrix</h1>
    <p class="lede">
      Consolidated real local-model evidence across broader Old Testament
      canonical-intertext pressure, reception-sensitive Jewish/Christian
      pressure, and cross-lens doctoral collision pressure. This is measured
      smoke evidence, not reviewer signoff or translation authority.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Measured State</h2>
      {
        metric_cards(
            [
                (
                    "Attempts",
                    fmt_int(summary["attempt_count"]),
                    attempt_note,
                ),
                (
                    "Schema-valid",
                    fmt_int(summary["schema_valid_attempt_count"]),
                    schema_note,
                ),
                (
                    "Clean anchored",
                    fmt_int(summary["clean_source_anchored_count"]),
                    clean_note,
                ),
                (
                    "Anchor issues",
                    fmt_int(summary["source_anchor_issue_count"]),
                    anchor_note,
                ),
                (
                    "Coverage",
                    coverage_value,
                    coverage_note,
                ),
                (
                    "Missing",
                    fmt_int(summary["missing_model_task_count_after_smoke"]),
                    missing_note,
                ),
                (
                    "Best clean model",
                    summary["best_clean_model_profile"],
                    "Ranked by clean source-anchored attempts, then anchor issues.",
                ),
                (
                    "Fastest clean",
                    summary["fastest_clean_model_profile"],
                    fastest_note,
                ),
            ]
        )
    }
      <div class="warning">{esc(summary["authority_verdict"])}</div>
    </section>

    <section>
      <h2>Lane Coverage</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["lane_attempt_rows"],
            label_key="label",
            value_key="value",
            aria_label="Real local-model attempts by contextual lane",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["lane_valid_coverage_rows"],
            label_key="label",
            value_key="value",
            aria_label="Valid model-task coverage percentage by contextual lane",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["lane_missing_rows"],
            label_key="label",
            value_key="value",
            aria_label="Missing planned model-task rows by contextual lane",
            color="#9b3d3d",
        )
    }</div>
      {
        table(
            [
                "Lane",
                "Context Focus",
                "Planned",
                "Attempts",
                "Schema Valid",
                "Clean",
                "Coverage",
                "Missing",
                "Anchor Issues",
                "Clean Best",
            ],
            lane_rows,
        )
    }
    </section>

    <section>
      <h2>Model Comparison</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["model_clean_rows"],
            label_key="label",
            value_key="value",
            aria_label="Clean source-anchored attempts by local model",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["model_anchor_issue_rows"],
            label_key="label",
            value_key="value",
            aria_label="Source-anchor issues by local model",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["model_elapsed_rows"],
            label_key="label",
            value_key="value",
            aria_label="Mean elapsed seconds by local model",
            color="#7c5b2f",
        )
    }</div>
      {
        table(
            [
                "Model",
                "Attempts",
                "Schema Valid",
                "Schema %",
                "Clean",
                "Clean %",
                "Anchor Issues",
                "Mean Elapsed",
                "Clean Lanes",
                "Evidence Role",
            ],
            model_rows,
        )
    }
      {
        table(
            [
                "Lane",
                "Model",
                "Attempts",
                "Schema Valid",
                "Clean",
                "Anchor Issues",
                "Mean Elapsed",
                "Task Refs",
            ],
            model_lane_rows,
        )
    }
    </section>

    <section>
      <h2>Attempt Rows</h2>
      {
        table(
            [
                "Lane",
                "Model",
                "Ref",
                "Layer",
                "Schema Valid",
                "Clean",
                "Anchor Issues",
                "Reception Leaks",
                "Elapsed",
                "Candidate Text",
            ],
            attempt_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a consolidated contextual real-model evidence matrix."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.csv_output, report["attempt_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
