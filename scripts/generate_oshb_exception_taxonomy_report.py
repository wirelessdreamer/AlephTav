from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"

OSHB_EXCEPTION_REVIEW_PATH = REPORT_ROOT / "oshb_alignment_exception_review.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "oshb_exception_taxonomy.json"
DEFAULT_CAUSE_CSV_OUTPUT = REPORT_ROOT / "oshb_exception_taxonomy_causes.csv"
DEFAULT_BATCH_CSV_OUTPUT = REPORT_ROOT / "oshb_exception_taxonomy_batches.csv"
DEFAULT_REVIEW_CSV_OUTPUT = REPORT_ROOT / "oshb_exception_taxonomy_review_packets.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "oshb_exception_taxonomy.html"

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
TARGET_BATCH_SIZE = 25


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


def slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.lower())
    return value.strip("_") or "item"


def osis_sort_key(osis_id: str) -> tuple[int, int, str]:
    parts = osis_id.split(".")
    chapter = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    verse = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return chapter, verse, osis_id


def token_list(row: dict[str, Any], key: str) -> list[str]:
    value = row.get(key, [])
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [part.strip() for part in value.split(";") if part.strip()]
    return []


def token_direction(row: dict[str, Any]) -> str:
    oshb = int(row["oshb_token_count"])
    uxlc = int(row["uxlc_token_count"])
    if oshb > uxlc:
        return "oshb_more_tokens"
    if uxlc > oshb:
        return "uxlc_more_tokens"
    return "same_token_count"


def window_overlap_pct(row: dict[str, Any]) -> float:
    left = set(token_list(row, "oshb_window"))
    right = set(token_list(row, "uxlc_window"))
    if not left and not right:
        return 0.0
    return pct(len(left & right), len(left | right))


def has_segmentation_marker(row: dict[str, Any]) -> bool:
    surface = " ".join(token_list(row, "oshb_surface_window"))
    return "/" in surface


def cause_family(row: dict[str, Any]) -> str:
    delta = int(row["token_delta"])
    similarity = float(row["sequence_similarity_pct"])
    overlap = window_overlap_pct(row)
    direction = token_direction(row)
    if row["mismatch_type"] != "token_count" or delta == 0:
        return "same_count_substitution_or_orthography"
    if similarity < 70 or delta >= 5:
        return "major_text_or_verse_alignment_gap"
    if direction == "oshb_more_tokens" and has_segmentation_marker(row):
        return "oshb_compound_or_clitic_segmentation"
    if overlap >= 35:
        return "shared_context_segmentation_gap"
    if delta == 1:
        return "minor_token_count_segmentation"
    return "multi_token_variant_or_segmentation"


def review_intensity(row: dict[str, Any]) -> str:
    if row["severity"] == "critical":
        return "manual_primary_review"
    if row["book"] == "Psalms":
        return "manual_psalm_regression_review"
    if row["book"] in {"Daniel", "Ezra"}:
        return "manual_aramaic_alignment_review"
    if row["exception_class"] == "minor_segmentation_gap":
        return "sample_then_rule_candidate"
    return "targeted_manual_review"


def enrich_rows(review_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for row in review_rows:
        cause = cause_family(row)
        lanes = list(row.get("review_lanes", []))
        enriched.append(
            {
                **row,
                "cause_family": cause,
                "token_count_direction": token_direction(row),
                "window_overlap_pct": window_overlap_pct(row),
                "oshb_segmentation_marker": has_segmentation_marker(row),
                "review_intensity": review_intensity(row),
                "requires_psalm_regression": row["book"] == "Psalms",
                "requires_aramaic_review": row["book"] in {"Daniel", "Ezra"},
                "requires_release_boundary": "release_boundary" in lanes,
                "review_packet_status": "queued_not_signed_off",
                "reviewer_decision": "",
                "adjudicated_cause": "",
                "approved_mapping_rule": "",
                "reviewer": "",
                "signed_off_at": "",
                "review_notes": "",
            }
        )
    return enriched


def build_cause_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row["cause_family"]), []).append(row)
    cause_rows = []
    total = len(rows)
    for cause, items in groups.items():
        severity_counts = Counter(str(row["severity"]) for row in items)
        direction_counts = Counter(str(row["token_count_direction"]) for row in items)
        books = sorted({str(row["book"]) for row in items})
        cause_rows.append(
            {
                "cause_family": cause,
                "row_count": len(items),
                "row_pct": pct(len(items), total),
                "critical_count": severity_counts.get("critical", 0),
                "high_count": severity_counts.get("high", 0),
                "medium_count": severity_counts.get("medium", 0),
                "oshb_more_token_count": direction_counts.get("oshb_more_tokens", 0),
                "uxlc_more_token_count": direction_counts.get("uxlc_more_tokens", 0),
                "same_token_count": direction_counts.get("same_token_count", 0),
                "psalm_regression_count": sum(
                    1 for row in items if row["requires_psalm_regression"]
                ),
                "aramaic_review_count": sum(1 for row in items if row["requires_aramaic_review"]),
                "segmentation_marker_count": sum(
                    1 for row in items if row["oshb_segmentation_marker"]
                ),
                "book_count": len(books),
                "books": books,
                "review_intensity": cause_review_intensity(items),
                "recommended_batching": recommended_cause_batching(cause),
            }
        )
    return sorted(cause_rows, key=lambda row: (-int(row["row_count"]), row["cause_family"]))


def cause_review_intensity(rows: list[dict[str, Any]]) -> str:
    if any(row["severity"] == "critical" for row in rows):
        return "manual_primary_review"
    if any(row["requires_psalm_regression"] for row in rows):
        return "manual_psalm_regression_review"
    if any(row["requires_aramaic_review"] for row in rows):
        return "manual_aramaic_alignment_review"
    return "targeted_alignment_review"


def recommended_cause_batching(cause: str) -> str:
    if cause == "major_text_or_verse_alignment_gap":
        return "assign_individually_or_small_batches"
    if cause == "same_count_substitution_or_orthography":
        return "compare_against_textual_witness_and_source_map"
    if "segmentation" in cause:
        return "batch_by_book_and_candidate_mapping_rule"
    return "batch_by_book_then_review_lane"


def build_batch_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row["book"]),
            str(row["cause_family"]),
            str(row["severity"]),
            str(row["review_intensity"]),
        )
        grouped.setdefault(key, []).append(row)

    batch_rows = []
    packet_rows = []
    batch_rank = 0
    for key, items in sorted(
        grouped.items(),
        key=lambda item: (
            item[0][0],
            item[0][1],
            SEVERITY_ORDER.get(item[0][2], 99),
            item[0][3],
        ),
    ):
        book, cause, severity, intensity = key
        items = sorted(items, key=lambda row: osis_sort_key(str(row["osis_id"])))
        for offset in range(0, len(items), TARGET_BATCH_SIZE):
            chunk = items[offset : offset + TARGET_BATCH_SIZE]
            batch_rank += 1
            batch_id = f"oshb_exc_{batch_rank:03d}_{slug(book)}_{slug(cause)}"
            if len(items) > TARGET_BATCH_SIZE:
                batch_id = f"{batch_id}_{offset // TARGET_BATCH_SIZE + 1:02d}"
            lanes = sorted({lane for row in chunk for lane in row.get("review_lanes", [])})
            batch_rows.append(
                {
                    "batch_id": batch_id,
                    "book": book,
                    "division": chunk[0]["division"],
                    "cause_family": cause,
                    "severity": severity,
                    "review_intensity": intensity,
                    "row_count": len(chunk),
                    "first_osis_id": chunk[0]["osis_id"],
                    "last_osis_id": chunk[-1]["osis_id"],
                    "token_count_exception_count": sum(
                        1 for row in chunk if row["mismatch_type"] == "token_count"
                    ),
                    "sequence_only_exception_count": sum(
                        1 for row in chunk if row["mismatch_type"] != "token_count"
                    ),
                    "psalm_regression_count": sum(
                        1 for row in chunk if row["requires_psalm_regression"]
                    ),
                    "aramaic_review_count": sum(
                        1 for row in chunk if row["requires_aramaic_review"]
                    ),
                    "segmentation_marker_count": sum(
                        1 for row in chunk if row["oshb_segmentation_marker"]
                    ),
                    "review_lanes": lanes,
                    "status": "queued_not_signed_off",
                    "next_action": batch_next_action(cause, intensity),
                }
            )
            for row in chunk:
                packet_rows.append(
                    {
                        "batch_id": batch_id,
                        "book": row["book"],
                        "division": row["division"],
                        "osis_id": row["osis_id"],
                        "severity": row["severity"],
                        "cause_family": row["cause_family"],
                        "exception_class": row["exception_class"],
                        "mismatch_type": row["mismatch_type"],
                        "oshb_token_count": row["oshb_token_count"],
                        "uxlc_token_count": row["uxlc_token_count"],
                        "token_delta": row["token_delta"],
                        "sequence_similarity_pct": row["sequence_similarity_pct"],
                        "window_overlap_pct": row["window_overlap_pct"],
                        "oshb_segmentation_marker": row["oshb_segmentation_marker"],
                        "review_lanes": row["review_lanes"],
                        "review_packet_status": row["review_packet_status"],
                        "reviewer_decision": row["reviewer_decision"],
                        "adjudicated_cause": row["adjudicated_cause"],
                        "approved_mapping_rule": row["approved_mapping_rule"],
                        "reviewer": row["reviewer"],
                        "signed_off_at": row["signed_off_at"],
                        "review_notes": row["review_notes"],
                        "oshb_surface_window": row["oshb_surface_window"],
                        "uxlc_surface_window": row["uxlc_surface_window"],
                    }
                )
    return batch_rows, packet_rows


def batch_next_action(cause: str, intensity: str) -> str:
    if intensity == "manual_primary_review":
        return "review_each_row_against_source_text_and_alignment_before_import_rules"
    if intensity == "manual_psalm_regression_review":
        return "review_before_any_psalm_morphology_or_generation_change"
    if intensity == "manual_aramaic_alignment_review":
        return "route_to_aramaic_capable_lexical_and_alignment_reviewers"
    if "segmentation" in cause:
        return "derive_candidate_mapping_rule_then_spot_check_before_signoff"
    return "review_batch_and_record_mapping_or_source_variant_decision"


def summarize(
    exception_report: dict[str, Any],
    rows: list[dict[str, Any]],
    cause_rows: list[dict[str, Any]],
    batch_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    severity_counts = Counter(str(row["severity"]) for row in rows)
    direction_counts = Counter(str(row["token_count_direction"]) for row in rows)
    intensity_counts = Counter(str(row["review_intensity"]) for row in rows)
    summary = exception_report["summary"]
    return {
        "remote_commit_sha": summary["remote_commit_sha"],
        "remote_commit_date": summary["remote_commit_date"],
        "exception_row_count": len(rows),
        "taxonomy_cause_count": len(cause_rows),
        "review_batch_count": len(batch_rows),
        "review_packet_row_count": len(rows),
        "review_packet_completion_pct": 0.0,
        "critical_row_count": severity_counts.get("critical", 0),
        "high_row_count": severity_counts.get("high", 0),
        "medium_row_count": severity_counts.get("medium", 0),
        "oshb_more_token_count": direction_counts.get("oshb_more_tokens", 0),
        "uxlc_more_token_count": direction_counts.get("uxlc_more_tokens", 0),
        "same_token_count": direction_counts.get("same_token_count", 0),
        "segmentation_marker_count": sum(1 for row in rows if row["oshb_segmentation_marker"]),
        "segmentation_marker_pct": pct(
            sum(1 for row in rows if row["oshb_segmentation_marker"]),
            len(rows),
        ),
        "psalm_regression_row_count": sum(1 for row in rows if row["requires_psalm_regression"]),
        "aramaic_review_row_count": sum(1 for row in rows if row["requires_aramaic_review"]),
        "manual_primary_review_row_count": intensity_counts.get("manual_primary_review", 0),
        "targeted_review_row_count": sum(
            count
            for label, count in intensity_counts.items()
            if label not in {"manual_primary_review"}
        ),
        "top_cause_family": cause_rows[0]["cause_family"] if cause_rows else "",
        "top_cause_row_count": cause_rows[0]["row_count"] if cause_rows else 0,
        "largest_batch_id": max(batch_rows, key=lambda row: int(row["row_count"]))["batch_id"]
        if batch_rows
        else "",
        "largest_batch_row_count": max(int(row["row_count"]) for row in batch_rows)
        if batch_rows
        else 0,
        "source_approval_status": summary["source_approval_status"],
        "authority_verdict": (
            "taxonomy_generated_not_signoff: deterministic grouping and review batches "
            "reduce the OSHB exception workload, but no source approval, reviewer "
            "decision, mapping rule, or release signoff is recorded."
        ),
    }


def build_visual_data(
    cause_rows: list[dict[str, Any]],
    batch_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts = Counter(str(row["status"]) for row in batch_rows)
    intensity_counts = Counter(str(row["review_intensity"]) for row in batch_rows)
    return {
        "cause_rows": [
            {"label": row["cause_family"], "value": row["row_count"]} for row in cause_rows
        ],
        "batch_book_rows": [
            {"label": book, "value": count}
            for book, count in Counter(str(row["book"]) for row in batch_rows).most_common()
        ],
        "batch_status_rows": [
            {"label": label, "value": count} for label, count in status_counts.most_common()
        ],
        "batch_intensity_rows": [
            {"label": label, "value": count} for label, count in intensity_counts.most_common()
        ],
    }


def build_report() -> dict[str, Any]:
    exception_report = load_json(OSHB_EXCEPTION_REVIEW_PATH)
    rows = enrich_rows(exception_report["sample_rows"])
    cause_rows = build_cause_rows(rows)
    batch_rows, packet_rows = build_batch_rows(rows)
    summary = summarize(exception_report, rows, cause_rows, batch_rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "oshb_exception_taxonomy_generated_not_signoff",
        "source_paths": {
            "oshb_alignment_exception_review": str(OSHB_EXCEPTION_REVIEW_PATH.relative_to(ROOT)),
        },
        "source_boundary": {
            "scope": (
                "Derived deterministic taxonomy and reviewer batching over complete "
                "OSHB exception rows."
            ),
            "forbidden_use": (
                "This report does not approve OSHB use, import morphology, create "
                "canonical wording, or record reviewer/release signoff."
            ),
            "approval_state": "source_approval_not_recorded",
        },
        "method": {
            "classification_basis": (
                "Rules use token-count direction, token delta, sequence similarity, "
                "window overlap, OSHB slash segmentation markers, book, and severity."
            ),
            "batching_basis": (
                "Rows are grouped by book, cause family, severity, and review intensity, "
                f"with a target maximum of {TARGET_BATCH_SIZE} rows per batch."
            ),
        },
        "summary": summary,
        "cause_rows": cause_rows,
        "batch_rows": batch_rows,
        "review_packet_rows": packet_rows,
        "visual_data": build_visual_data(cause_rows, batch_rows),
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
    left = 310
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
    cause_rows = [
        [
            row["cause_family"],
            row["row_count"],
            f"{row['row_pct']:.2f}%",
            row["critical_count"],
            row["high_count"],
            row["medium_count"],
            row["segmentation_marker_count"],
            row["book_count"],
            row["review_intensity"],
            row["recommended_batching"],
        ]
        for row in report["cause_rows"]
    ]
    batch_rows = [
        [
            row["batch_id"],
            row["book"],
            row["cause_family"],
            row["severity"],
            row["review_intensity"],
            row["row_count"],
            row["first_osis_id"],
            row["last_osis_id"],
            ", ".join(row["review_lanes"]),
            row["status"],
        ]
        for row in report["batch_rows"][:80]
    ]
    packet_rows = [
        [
            row["batch_id"],
            row["book"],
            row["osis_id"],
            row["severity"],
            row["cause_family"],
            row["oshb_token_count"],
            row["uxlc_token_count"],
            row["token_delta"],
            f"{row['sequence_similarity_pct']:.2f}%",
            f"{row['window_overlap_pct']:.2f}%",
            row["review_packet_status"],
        ]
        for row in report["review_packet_rows"][:100]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OSHB Exception Taxonomy and Review Batches</title>
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
    <h1>OSHB Exception Taxonomy and Review Batches</h1>
    <p class="lede">
      Deterministic taxonomy for the complete OSHB exception queue. This report
      groups all exception rows by token behavior, severity, book pressure, and
      review intensity so scholars can adjudicate importer rules without treating
      the pilot as source approval.
    </p>
    <p class="meta">
      Generated {esc(report["generated_on"])} from OSHB commit
      {esc(summary["remote_commit_sha"])} dated {esc(summary["remote_commit_date"])}.
    </p>
  </header>
  <main>
    <section>
      <h2>Taxonomy Verdict</h2>
      {
        render_cards(
            [
                (
                    "Exception rows",
                    fmt_int(summary["exception_row_count"]),
                    "Complete queue from the OSHB exception review.",
                ),
                (
                    "Cause families",
                    fmt_int(summary["taxonomy_cause_count"]),
                    "Deterministic rule groups.",
                ),
                (
                    "Review batches",
                    fmt_int(summary["review_batch_count"]),
                    f"Target batch size {TARGET_BATCH_SIZE}.",
                ),
                (
                    "Review completion",
                    fmt_pct(summary["review_packet_completion_pct"]),
                    "No human decisions are recorded.",
                ),
                (
                    "Manual primary rows",
                    fmt_int(summary["manual_primary_review_row_count"]),
                    "Critical rows requiring row-by-row adjudication.",
                ),
                (
                    "Psalm regression rows",
                    fmt_int(summary["psalm_regression_row_count"]),
                    "Must be reviewed before Psalm morphology changes.",
                ),
                (
                    "Aramaic rows",
                    fmt_int(summary["aramaic_review_row_count"]),
                    "Daniel/Ezra rows routed to Aramaic-capable review.",
                ),
                (
                    "Source approval",
                    summary["source_approval_status"],
                    "No approval is recorded by this report.",
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
      <h2>Cause Families</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["cause_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception cause-family counts",
            color="#2f6f73",
            limit=12,
        )
    }</div>
      {
        table(
            [
                "Cause",
                "Rows",
                "Pct",
                "Critical",
                "High",
                "Medium",
                "Segmentation Markers",
                "Books",
                "Review Intensity",
                "Batching",
            ],
            cause_rows,
        )
    }
    </section>

    <section>
      <h2>Reviewer Batches</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["batch_book_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception review batches by book",
            color="#8a6426",
            limit=20,
        )
    }</div>
      {
        table(
            [
                "Batch",
                "Book",
                "Cause",
                "Severity",
                "Intensity",
                "Rows",
                "First OSIS",
                "Last OSIS",
                "Review Lanes",
                "Status",
            ],
            batch_rows,
        )
    }
    </section>

    <section>
      <h2>Review Packet Sample</h2>
      {
        table(
            [
                "Batch",
                "Book",
                "OSIS",
                "Severity",
                "Cause",
                "OSHB Tokens",
                "UXLC Tokens",
                "Delta",
                "Similarity",
                "Window Overlap",
                "Status",
            ],
            packet_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def flatten_cause_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return rows


def flatten_batch_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return rows


def flatten_packet_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "batch_id",
        "book",
        "division",
        "osis_id",
        "severity",
        "cause_family",
        "exception_class",
        "mismatch_type",
        "oshb_token_count",
        "uxlc_token_count",
        "token_delta",
        "sequence_similarity_pct",
        "window_overlap_pct",
        "oshb_segmentation_marker",
        "review_lanes",
        "review_packet_status",
        "reviewer_decision",
        "adjudicated_cause",
        "approved_mapping_rule",
        "reviewer",
        "signed_off_at",
        "review_notes",
        "oshb_surface_window",
        "uxlc_surface_window",
    ]
    return [{key: row.get(key, "") for key in keys} for row in rows]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate OSHB exception taxonomy and reviewer batches."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--cause-csv-output", type=Path, default=DEFAULT_CAUSE_CSV_OUTPUT)
    parser.add_argument("--batch-csv-output", type=Path, default=DEFAULT_BATCH_CSV_OUTPUT)
    parser.add_argument("--review-csv-output", type=Path, default=DEFAULT_REVIEW_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.cause_csv_output, flatten_cause_rows(report["cause_rows"]))
    write_csv(args.batch_csv_output, flatten_batch_rows(report["batch_rows"]))
    write_csv(args.review_csv_output, flatten_packet_rows(report["review_packet_rows"]))
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.cause_csv_output}")
    print(f"Wrote {args.batch_csv_output}")
    print(f"Wrote {args.review_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
