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

OSHB_EXCEPTION_TAXONOMY_PATH = REPORT_ROOT / "oshb_exception_taxonomy.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "oshb_mapping_rule_simulation.json"
DEFAULT_RULE_CSV_OUTPUT = REPORT_ROOT / "oshb_mapping_rule_simulation_rules.csv"
DEFAULT_PACKET_CSV_OUTPUT = REPORT_ROOT / "oshb_mapping_rule_simulation_packets.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "oshb_mapping_rule_simulation.html"

LANE_ORDER = {
    "rule_candidate_after_review": 0,
    "targeted_rule_review": 1,
    "manual_exception_review": 2,
    "textual_witness_review": 3,
}


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


def simulation_for_row(row: dict[str, Any]) -> dict[str, str]:
    cause = str(row["cause_family"])
    severity = str(row["severity"])
    similarity = float(row["sequence_similarity_pct"])
    overlap = float(row["window_overlap_pct"])
    segmentation_marker = bool(row["oshb_segmentation_marker"])

    if cause == "oshb_compound_or_clitic_segmentation":
        if severity == "medium" and similarity >= 90.0 and overlap >= 50.0:
            return {
                "candidate_rule_id": "RULE-01",
                "candidate_rule": "collapse_oshb_slash_segmented_clitics_to_uxlc_token",
                "automation_lane": "rule_candidate_after_review",
                "confidence_band": "high",
                "review_requirement": "spot_check_mapping_rule_then_alignment_signoff",
            }
        if severity in {"medium", "high"} and similarity >= 80.0 and segmentation_marker:
            return {
                "candidate_rule_id": "RULE-01",
                "candidate_rule": "collapse_oshb_slash_segmented_clitics_to_uxlc_token",
                "automation_lane": "targeted_rule_review",
                "confidence_band": "medium",
                "review_requirement": "book_level_rule_review_before_mapping",
            }
        return {
            "candidate_rule_id": "RULE-01",
            "candidate_rule": "collapse_oshb_slash_segmented_clitics_to_uxlc_token",
            "automation_lane": "manual_exception_review",
            "confidence_band": "low",
            "review_requirement": "row_level_alignment_review",
        }

    if cause == "shared_context_segmentation_gap":
        if similarity >= 85.0 and overlap >= 50.0:
            return {
                "candidate_rule_id": "RULE-02",
                "candidate_rule": "shared_context_segmentation_bridge",
                "automation_lane": "targeted_rule_review",
                "confidence_band": "medium",
                "review_requirement": "confirm_token_grouping_and_source_map",
            }
        return {
            "candidate_rule_id": "RULE-02",
            "candidate_rule": "shared_context_segmentation_bridge",
            "automation_lane": "manual_exception_review",
            "confidence_band": "low",
            "review_requirement": "row_level_alignment_review",
        }

    if cause == "major_text_or_verse_alignment_gap":
        return {
            "candidate_rule_id": "RULE-03",
            "candidate_rule": "manual_text_or_verse_alignment_exception",
            "automation_lane": "manual_exception_review",
            "confidence_band": "none",
            "review_requirement": "manual_source_text_and_verse_map_adjudication",
        }

    if cause == "same_count_substitution_or_orthography":
        return {
            "candidate_rule_id": "RULE-04",
            "candidate_rule": "same_count_orthography_or_variant_check",
            "automation_lane": "textual_witness_review",
            "confidence_band": "none",
            "review_requirement": "compare_source_map_and_textual_witness",
        }

    return {
        "candidate_rule_id": "RULE-05",
        "candidate_rule": "multi_token_variant_or_segmentation_exception",
        "automation_lane": "manual_exception_review",
        "confidence_band": "low",
        "review_requirement": "manual_alignment_and_variant_review",
    }


def enrich_packets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packets = []
    for row in rows:
        simulation = simulation_for_row(row)
        packets.append(
            {
                **row,
                **simulation,
                "requires_psalm_regression": row["book"] == "Psalms",
                "requires_aramaic_review": row["book"] in {"Daniel", "Ezra"},
                "source_approval_required": True,
                "review_signoff_required": True,
                "simulated_mapping_status": "candidate_not_approved",
                "reviewer_rule_decision": "",
                "reviewer_rule_notes": "",
            }
        )
    return packets


def build_rule_rows(packet_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in packet_rows:
        key = (
            str(row["candidate_rule_id"]),
            str(row["candidate_rule"]),
            str(row["automation_lane"]),
        )
        groups.setdefault(key, []).append(row)

    rows = []
    total = len(packet_rows)
    for (rule_id, rule, lane), items in groups.items():
        confidence_counts = Counter(str(row["confidence_band"]) for row in items)
        cause_counts = Counter(str(row["cause_family"]) for row in items)
        rows.append(
            {
                "candidate_rule_id": rule_id,
                "candidate_rule": rule,
                "automation_lane": lane,
                "row_count": len(items),
                "row_pct": pct(len(items), total),
                "high_confidence_count": confidence_counts.get("high", 0),
                "medium_confidence_count": confidence_counts.get("medium", 0),
                "low_confidence_count": confidence_counts.get("low", 0),
                "manual_none_confidence_count": confidence_counts.get("none", 0),
                "critical_count": sum(1 for row in items if row["severity"] == "critical"),
                "high_severity_count": sum(1 for row in items if row["severity"] == "high"),
                "medium_severity_count": sum(1 for row in items if row["severity"] == "medium"),
                "psalm_regression_count": sum(
                    1 for row in items if row["requires_psalm_regression"]
                ),
                "aramaic_review_count": sum(1 for row in items if row["requires_aramaic_review"]),
                "segmentation_marker_count": sum(
                    1 for row in items if row["oshb_segmentation_marker"]
                ),
                "dominant_cause_family": cause_counts.most_common(1)[0][0],
                "source_approval_required": True,
                "review_signoff_required": True,
                "authority_status": "candidate_not_approved",
                "next_action": next_action_for_lane(lane),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row["candidate_rule_id"]),
            LANE_ORDER.get(str(row["automation_lane"]), 99),
            -int(row["row_count"]),
        ),
    )


def next_action_for_lane(lane: str) -> str:
    if lane == "rule_candidate_after_review":
        return "derive_candidate_rule_fixture_then_spot_check_before_any_import"
    if lane == "targeted_rule_review":
        return "route_book_level_rule_batches_to_alignment_and_hebrew_reviewers"
    if lane == "textual_witness_review":
        return "compare_same_count_rows_against_textual_witness_and_source_map"
    return "keep_as_manual_exception_until_text_and_alignment_are_adjudicated"


def summarize(
    taxonomy: dict[str, Any],
    rule_rows: list[dict[str, Any]],
    packet_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    lane_counts = Counter(str(row["automation_lane"]) for row in packet_rows)
    confidence_counts = Counter(str(row["confidence_band"]) for row in packet_rows)
    source_summary = taxonomy["summary"]
    rule_candidate_count = lane_counts.get("rule_candidate_after_review", 0)
    targeted_count = lane_counts.get("targeted_rule_review", 0)
    manual_count = lane_counts.get("manual_exception_review", 0)
    textual_count = lane_counts.get("textual_witness_review", 0)
    return {
        "remote_commit_sha": source_summary["remote_commit_sha"],
        "remote_commit_date": source_summary["remote_commit_date"],
        "exception_row_count": len(packet_rows),
        "candidate_rule_group_count": len(rule_rows),
        "rule_candidate_after_review_count": rule_candidate_count,
        "rule_candidate_after_review_pct": pct(rule_candidate_count, len(packet_rows)),
        "targeted_rule_review_count": targeted_count,
        "targeted_rule_review_pct": pct(targeted_count, len(packet_rows)),
        "manual_exception_review_count": manual_count,
        "manual_exception_review_pct": pct(manual_count, len(packet_rows)),
        "textual_witness_review_count": textual_count,
        "textual_witness_review_pct": pct(textual_count, len(packet_rows)),
        "high_confidence_rule_candidate_count": confidence_counts.get("high", 0),
        "medium_confidence_rule_candidate_count": confidence_counts.get("medium", 0),
        "low_confidence_or_manual_count": (
            confidence_counts.get("low", 0) + confidence_counts.get("none", 0)
        ),
        "candidate_rule_reduction_row_count": rule_candidate_count + targeted_count,
        "candidate_rule_reduction_pct": pct(
            rule_candidate_count + targeted_count,
            len(packet_rows),
        ),
        "manual_residual_row_count": manual_count + textual_count,
        "manual_residual_pct": pct(manual_count + textual_count, len(packet_rows)),
        "psalm_rule_candidate_row_count": sum(
            1
            for row in packet_rows
            if row["requires_psalm_regression"]
            and row["automation_lane"] in {"rule_candidate_after_review", "targeted_rule_review"}
        ),
        "aramaic_rule_candidate_row_count": sum(
            1
            for row in packet_rows
            if row["requires_aramaic_review"]
            and row["automation_lane"] in {"rule_candidate_after_review", "targeted_rule_review"}
        ),
        "source_approval_status": source_summary["source_approval_status"],
        "authority_verdict": (
            "simulation_generated_not_import_rule: candidate mapping-rule counts are "
            "deterministic triage evidence only; no OSHB source approval, importer rule, "
            "reviewer decision, or release signoff is recorded."
        ),
    }


def build_visual_data(
    rule_rows: list[dict[str, Any]],
    packet_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    lane_counts = Counter(str(row["automation_lane"]) for row in packet_rows)
    rule_counts = Counter(str(row["candidate_rule"]) for row in packet_rows)
    return {
        "automation_lane_rows": [
            {"label": label, "value": count} for label, count in lane_counts.most_common()
        ],
        "rule_count_rows": [
            {"label": label, "value": count} for label, count in rule_counts.most_common()
        ],
        "rule_group_rows": [
            {
                "label": f"{row['candidate_rule_id']} {row['automation_lane']}",
                "value": row["row_count"],
            }
            for row in rule_rows
        ],
    }


def build_report() -> dict[str, Any]:
    taxonomy = load_json(OSHB_EXCEPTION_TAXONOMY_PATH)
    packet_rows = enrich_packets(taxonomy["review_packet_rows"])
    rule_rows = build_rule_rows(packet_rows)
    summary = summarize(taxonomy, rule_rows, packet_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "oshb_mapping_rule_simulation_generated_not_approval",
        "source_paths": {
            "oshb_exception_taxonomy": str(OSHB_EXCEPTION_TAXONOMY_PATH.relative_to(ROOT)),
        },
        "source_boundary": {
            "scope": (
                "Derived simulation of candidate OSHB-to-UXLC mapping rules over "
                "taxonomy review packets."
            ),
            "forbidden_use": (
                "This report does not approve OSHB source use, import morphology, "
                "authorize mapping rules, train a model, change canonical wording, or "
                "record reviewer/release signoff."
            ),
            "approval_state": "source_approval_not_recorded",
        },
        "method": {
            "rule_basis": (
                "Rules are simulated from deterministic taxonomy fields: cause family, "
                "severity, sequence similarity, window overlap, and OSHB segmentation "
                "markers."
            ),
            "high_confidence_candidate": (
                "OSHB compound/clitic segmentation rows with medium severity, sequence "
                "similarity >= 90, and window overlap >= 50."
            ),
            "targeted_candidate": (
                "OSHB segmentation rows with medium/high severity, sequence similarity "
                ">= 80, and explicit OSHB slash segmentation marker, plus selected "
                "shared-context segmentation rows."
            ),
        },
        "summary": summary,
        "rule_rows": rule_rows,
        "packet_rows": packet_rows,
        "visual_data": build_visual_data(rule_rows, packet_rows),
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
    left = 330
    right = 110
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
    rule_rows = [
        [
            row["candidate_rule_id"],
            row["candidate_rule"],
            row["automation_lane"],
            row["row_count"],
            f"{row['row_pct']:.2f}%",
            row["high_confidence_count"],
            row["medium_confidence_count"],
            row["critical_count"],
            row["psalm_regression_count"],
            row["aramaic_review_count"],
            row["authority_status"],
            row["next_action"],
        ]
        for row in report["rule_rows"]
    ]
    packet_rows = [
        [
            row["batch_id"],
            row["book"],
            row["osis_id"],
            row["candidate_rule_id"],
            row["automation_lane"],
            row["confidence_band"],
            row["severity"],
            row["cause_family"],
            f"{row['sequence_similarity_pct']:.2f}%",
            f"{row['window_overlap_pct']:.2f}%",
        ]
        for row in report["packet_rows"][:100]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OSHB Mapping Rule Simulation</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #596875;
      --line: #cfd7de;
      --panel: #f7f9fb;
      --accent: #2f6f73;
      --gold: #8a6426;
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
    main {{ max-width: 1240px; margin: 0 auto; padding: 30px 34px 56px; }}
    h1 {{ margin: 0 0 12px; font-size: 34px; letter-spacing: 0; }}
    h2 {{
      margin: 34px 0 14px;
      font-size: 22px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }}
    p {{ margin: 0 0 13px; }}
    .lede {{ max-width: 1010px; font-size: 17px; color: #33414c; }}
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
    <h1>OSHB Mapping Rule Simulation</h1>
    <p class="lede">
      Deterministic simulation of candidate mapping rules over the OSHB exception
      taxonomy. It estimates which segmentation exceptions could become importer
      rules after source approval and human review, and which rows remain manual.
    </p>
    <p class="meta">
      Generated {esc(report["generated_on"])} from OSHB commit
      {esc(summary["remote_commit_sha"])} dated {esc(summary["remote_commit_date"])}.
    </p>
  </header>
  <main>
    <section>
      <h2>Simulation Verdict</h2>
      {
        render_cards(
            [
                (
                    "Rule candidates",
                    fmt_int(summary["rule_candidate_after_review_count"]),
                    f"{fmt_pct(summary['rule_candidate_after_review_pct'])} high-confidence.",
                ),
                (
                    "Targeted review",
                    fmt_int(summary["targeted_rule_review_count"]),
                    f"{fmt_pct(summary['targeted_rule_review_pct'])} medium-confidence.",
                ),
                (
                    "Manual residual",
                    fmt_int(summary["manual_residual_row_count"]),
                    f"{fmt_pct(summary['manual_residual_pct'])} remain manual/textual.",
                ),
                (
                    "Potential reduction",
                    fmt_pct(summary["candidate_rule_reduction_pct"]),
                    "Could be rule-routed after approval and signoff.",
                ),
                (
                    "Psalm candidates",
                    fmt_int(summary["psalm_rule_candidate_row_count"]),
                    "Require Psalm regression review.",
                ),
                (
                    "Aramaic candidates",
                    fmt_int(summary["aramaic_rule_candidate_row_count"]),
                    "Require Daniel/Ezra review.",
                ),
                (
                    "Source approval",
                    summary["source_approval_status"],
                    "No source approval is recorded.",
                ),
                (
                    "Rule status",
                    "not approved",
                    "No importer rule is authorized.",
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
      <h2>Automation Lanes</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["automation_lane_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB mapping-rule simulation rows by automation lane",
            color="#2f6f73",
            limit=12,
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            visual["rule_count_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB mapping-rule simulation rows by candidate rule",
            color="#8a6426",
            limit=12,
        )
    }</div>
    </section>

    <section>
      <h2>Candidate Rules</h2>
      {
        table(
            [
                "Rule",
                "Name",
                "Lane",
                "Rows",
                "Pct",
                "High Conf",
                "Medium Conf",
                "Critical",
                "Psalm",
                "Aramaic",
                "Authority",
                "Next Action",
            ],
            rule_rows,
        )
    }
    </section>

    <section>
      <h2>Packet Sample</h2>
      {
        table(
            [
                "Batch",
                "Book",
                "OSIS",
                "Rule",
                "Lane",
                "Confidence",
                "Severity",
                "Cause",
                "Similarity",
                "Overlap",
            ],
            packet_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def flatten_rule_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return rows


def flatten_packet_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "batch_id",
        "book",
        "division",
        "osis_id",
        "severity",
        "cause_family",
        "candidate_rule_id",
        "candidate_rule",
        "automation_lane",
        "confidence_band",
        "review_requirement",
        "mismatch_type",
        "oshb_token_count",
        "uxlc_token_count",
        "token_delta",
        "sequence_similarity_pct",
        "window_overlap_pct",
        "requires_psalm_regression",
        "requires_aramaic_review",
        "source_approval_required",
        "review_signoff_required",
        "simulated_mapping_status",
        "reviewer_rule_decision",
        "reviewer_rule_notes",
    ]
    return [{key: row.get(key, "") for key in keys} for row in rows]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate OSHB candidate mapping-rule simulation.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--rule-csv-output", type=Path, default=DEFAULT_RULE_CSV_OUTPUT)
    parser.add_argument("--packet-csv-output", type=Path, default=DEFAULT_PACKET_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.rule_csv_output, flatten_rule_rows(report["rule_rows"]))
    write_csv(args.packet_csv_output, flatten_packet_rows(report["packet_rows"]))
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.rule_csv_output}")
    print(f"Wrote {args.packet_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
