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

OSHB_ALIGNMENT_PILOT_PATH = REPORT_ROOT / "oshb_whole_tanakh_alignment_pilot.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "oshb_alignment_exception_review.json"
DEFAULT_BOOK_CSV_OUTPUT = REPORT_ROOT / "oshb_alignment_exception_review_books.csv"
DEFAULT_SAMPLE_CSV_OUTPUT = REPORT_ROOT / "oshb_alignment_exception_review_samples.csv"
DEFAULT_REVIEW_CSV_OUTPUT = REPORT_ROOT / "oshb_alignment_exception_review_rows.csv"
DEFAULT_GATE_CSV_OUTPUT = REPORT_ROOT / "oshb_alignment_exception_review_gates.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "oshb_alignment_exception_review.html"

ARAMAIC_BOOKS = {"Daniel", "Ezra"}


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


def as_int(row: dict[str, Any], key: str) -> int:
    return int(float(row.get(key) or 0))


def as_float(row: dict[str, Any], key: str) -> float:
    return float(row.get(key) or 0.0)


def classify_sample(row: dict[str, Any]) -> dict[str, Any]:
    oshb_count = as_int(row, "oshb_token_count")
    uxlc_count = as_int(row, "uxlc_token_count")
    token_delta = abs(oshb_count - uxlc_count)
    similarity = as_float(row, "sequence_similarity_pct")
    mismatch_type = str(row.get("mismatch_type") or "")
    book = str(row.get("book") or "")

    if mismatch_type.startswith("missing_"):
        exception_class = "missing_verse_or_reference"
        severity = "critical"
    elif token_delta >= 8 or similarity < 70:
        exception_class = "major_token_count_or_text_gap"
        severity = "critical"
    elif token_delta >= 3 or similarity < 85:
        exception_class = "multi_token_segmentation_or_variant_gap"
        severity = "high"
    elif token_delta:
        exception_class = "minor_segmentation_gap"
        severity = "medium"
    else:
        exception_class = "sequence_substitution"
        severity = "medium"

    review_lanes = ["alignment", "hebrew_morphology"]
    if severity in {"critical", "high"}:
        review_lanes.append("textual_witness")
    if book in ARAMAIC_BOOKS:
        review_lanes.append("aramaic_lexical")
    if book == "Psalms":
        review_lanes.append("psalm_regression")
    review_lanes.extend(["source_provenance", "release_boundary"])

    return {
        "book": book,
        "division": row.get("division", ""),
        "osis_id": row.get("osis_id", ""),
        "mismatch_type": mismatch_type,
        "exception_class": exception_class,
        "severity": severity,
        "oshb_token_count": oshb_count,
        "uxlc_token_count": uxlc_count,
        "token_delta": token_delta,
        "sequence_similarity_pct": similarity,
        "first_difference_index": as_int(row, "first_difference_index"),
        "review_lanes": review_lanes,
        "recommended_action": recommended_sample_action(exception_class, severity),
        "oshb_surface_window": row.get("oshb_surface_window", []),
        "uxlc_surface_window": row.get("uxlc_surface_window", []),
        "oshb_window": row.get("oshb_window", []),
        "uxlc_window": row.get("uxlc_window", []),
    }


def recommended_sample_action(exception_class: str, severity: str) -> str:
    if exception_class == "missing_verse_or_reference":
        return "check_verse_map_before_import"
    if severity == "critical":
        return "manual_text_and_alignment_adjudication"
    if severity == "high":
        return "manual_alignment_review_before_auto_mapping"
    return "candidate_for_rule_based_alignment_after_sampling"


def book_priority(row: dict[str, Any], samples: list[dict[str, Any]]) -> str:
    exact_pct = as_float(row, "exact_sequence_match_pct")
    mismatch_count = as_int(row, "mismatch_verse_count")
    mean_similarity = as_float(row, "mean_sequence_similarity_pct")
    has_critical_sample = any(sample["severity"] == "critical" for sample in samples)
    if row.get("book") == "Psalms":
        return "critical_psalm_regression_review"
    if exact_pct < 90 or mean_similarity < 99 or has_critical_sample:
        return "critical"
    if exact_pct < 95 or mismatch_count >= 50:
        return "high"
    if mismatch_count:
        return "moderate"
    return "low"


def priority_score(row: dict[str, Any], samples: list[dict[str, Any]]) -> float:
    exact_pct = as_float(row, "exact_sequence_match_pct")
    token_pct = as_float(row, "token_count_match_pct")
    mismatch_count = as_int(row, "mismatch_verse_count")
    both = as_int(row, "both_sources_verse_count")
    critical_samples = sum(1 for sample in samples if sample["severity"] == "critical")
    high_samples = sum(1 for sample in samples if sample["severity"] == "high")
    psalm_bonus = 18.0 if row.get("book") == "Psalms" else 0.0
    return round(
        (100.0 - exact_pct) * 1.9
        + (100.0 - token_pct) * 1.2
        + pct(mismatch_count, both) * 1.5
        + critical_samples * 2.0
        + high_samples
        + psalm_bonus,
        2,
    )


def build_book_rows(
    pilot_book_rows: list[dict[str, Any]],
    sample_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    samples_by_book: dict[str, list[dict[str, Any]]] = {}
    for sample in sample_rows:
        samples_by_book.setdefault(str(sample["book"]), []).append(sample)

    rows = []
    for row in pilot_book_rows:
        book = str(row["book"])
        samples = samples_by_book.get(book, [])
        both = as_int(row, "both_sources_verse_count")
        exact = as_int(row, "exact_sequence_match_verse_count")
        token = as_int(row, "token_count_match_verse_count")
        mismatch_count = as_int(row, "mismatch_verse_count")
        token_count_exception_count = max(both - token, 0)
        sequence_only_exception_count = max(mismatch_count - token_count_exception_count, 0)
        priority = book_priority(row, samples)
        rows.append(
            {
                "book": book,
                "division": row["division"],
                "both_sources_verse_count": both,
                "exact_sequence_match_verse_count": exact,
                "exact_sequence_match_pct": as_float(row, "exact_sequence_match_pct"),
                "token_count_match_pct": as_float(row, "token_count_match_pct"),
                "mean_sequence_similarity_pct": as_float(row, "mean_sequence_similarity_pct"),
                "mismatch_verse_count": mismatch_count,
                "token_count_exception_verse_count": token_count_exception_count,
                "sequence_only_exception_verse_count": sequence_only_exception_count,
                "mismatch_verse_pct": pct(mismatch_count, both),
                "sample_row_count": len(samples),
                "critical_sample_count": sum(
                    1 for sample in samples if sample["severity"] == "critical"
                ),
                "high_sample_count": sum(1 for sample in samples if sample["severity"] == "high"),
                "priority": priority,
                "exception_pressure_score": priority_score(row, samples),
                "review_lanes": book_review_lanes(book, priority),
                "recommended_action": recommended_book_action(priority),
            }
        )
    return sorted(rows, key=lambda item: item["exception_pressure_score"], reverse=True)


def book_review_lanes(book: str, priority: str) -> list[str]:
    lanes = ["alignment", "hebrew_morphology", "source_provenance"]
    if priority.startswith("critical"):
        lanes.extend(["textual_witness", "release_boundary"])
    if book in ARAMAIC_BOOKS:
        lanes.append("aramaic_lexical")
    if book == "Psalms":
        lanes.append("psalm_regression")
    return lanes


def recommended_book_action(priority: str) -> str:
    if priority == "critical_psalm_regression_review":
        return "review_before_any_psalm_regeneration_or_import_change"
    if priority == "critical":
        return "manual_exception_packet_before_derived_import"
    if priority == "high":
        return "targeted_alignment_review_before_auto_mapping"
    if priority == "moderate":
        return "sample_review_then_rule_based_mapping_candidate"
    return "eligible_after_source_approval_and_spot_check"


def build_division_rows(book_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in book_rows:
        groups.setdefault(str(row["division"]), []).append(row)

    rows = []
    for division, items in sorted(groups.items()):
        both = sum(as_int(row, "both_sources_verse_count") for row in items)
        mismatch = sum(as_int(row, "mismatch_verse_count") for row in items)
        token_exceptions = sum(as_int(row, "token_count_exception_verse_count") for row in items)
        weighted_similarity = (
            sum(
                row["mean_sequence_similarity_pct"] * row["both_sources_verse_count"]
                for row in items
            )
            / both
            if both
            else 0.0
        )
        rows.append(
            {
                "division": division,
                "book_count": len(items),
                "mismatch_verse_count": mismatch,
                "mismatch_verse_pct": pct(mismatch, both),
                "token_count_exception_verse_count": token_exceptions,
                "mean_sequence_similarity_pct": round(weighted_similarity, 2),
                "critical_book_count": sum(
                    1 for row in items if str(row["priority"]).startswith("critical")
                ),
                "high_book_count": sum(1 for row in items if row["priority"] == "high"),
            }
        )
    return rows


def build_gate_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "gate_id": "EXC-G01",
            "gate": "Hebrew-letter normalization sanity",
            "status": "pilot_partial",
            "evidence": (
                "The OSHB pilot now strips non-Hebrew annotation markers before "
                f"comparison and reports {fmt_pct(summary['exact_sequence_match_pct'])} "
                "exact verse-token matches."
            ),
            "next_action": "Lock the normalization rule into the future derived importer.",
        },
        {
            "gate_id": "EXC-G02",
            "gate": "Full exception enumeration",
            "status": (
                "review_required"
                if int(summary["unexported_exception_row_count"]) == 0
                else "blocked"
            ),
            "evidence": (
                (
                    f"All {fmt_int(summary['mismatch_verse_count'])} exception verses "
                    "are exported as reviewer rows."
                )
                if int(summary["unexported_exception_row_count"]) == 0
                else (
                    f"{fmt_int(summary['mismatch_verse_count'])} exception verses remain, "
                    f"but only {fmt_int(summary['review_row_count'])} reviewer rows "
                    "are exported."
                )
            ),
            "next_action": (
                "Route every reviewer row through Hebrew morphology, alignment, "
                "source-provenance, and release-boundary signoff."
            ),
        },
        {
            "gate_id": "EXC-G03",
            "gate": "Token-count exception review",
            "status": "review_required",
            "evidence": (
                f"{fmt_int(summary['token_count_exception_verse_count'])} verses have "
                "OSHB/UXLC token-count differences."
            ),
            "next_action": (
                "Route token-count exceptions to Hebrew morphology and alignment reviewers."
            ),
        },
        {
            "gate_id": "EXC-G04",
            "gate": "Sequence-only exception review",
            "status": "review_required",
            "evidence": (
                f"{fmt_int(summary['sequence_only_exception_verse_count'])} verses have "
                "same-count token substitutions after Hebrew-letter normalization."
            ),
            "next_action": (
                "Review same-count substitutions for orthography, variant, or source-map cause."
            ),
        },
        {
            "gate_id": "EXC-G05",
            "gate": "Source license and provenance approval",
            "status": "blocked",
            "evidence": f"OSHB source approval remains {summary['source_approval_status']}.",
            "next_action": (
                "Record source terms, attribution, version pin, and release policy decision."
            ),
        },
        {
            "gate_id": "EXC-G06",
            "gate": "Reviewer signoff and release boundary",
            "status": "blocked",
            "evidence": "This workbook creates review assignments; it records no approvals.",
            "next_action": (
                "Collect Hebrew, alignment, provenance, and release signoff before "
                "authority claims."
            ),
        },
    ]


def summarize(
    pilot: dict[str, Any],
    book_rows: list[dict[str, Any]],
    sample_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    pilot_summary = pilot["summary"]
    both = sum(row["both_sources_verse_count"] for row in book_rows)
    mismatch = sum(row["mismatch_verse_count"] for row in book_rows)
    token_exceptions = sum(row["token_count_exception_verse_count"] for row in book_rows)
    sequence_only = sum(row["sequence_only_exception_verse_count"] for row in book_rows)
    class_counts = Counter(str(row["exception_class"]) for row in sample_rows)
    severity_counts = Counter(str(row["severity"]) for row in sample_rows)
    priority_counts = Counter(str(row["priority"]) for row in book_rows)
    psalm_row = next(row for row in book_rows if row["book"] == "Psalms")
    return {
        "remote_commit_sha": pilot_summary["remote_commit_sha"],
        "remote_commit_date": pilot_summary["remote_commit_date"],
        "mapped_book_count": pilot_summary["mapped_book_count"],
        "mapped_non_psalm_book_count": pilot_summary["mapped_non_psalm_book_count"],
        "both_sources_verse_count": both,
        "exact_sequence_match_verse_count": pilot_summary["exact_sequence_match_verse_count"],
        "exact_sequence_match_pct": pilot_summary["exact_sequence_match_pct"],
        "mean_sequence_similarity_pct": pilot_summary["mean_sequence_similarity_pct"],
        "mismatch_verse_count": mismatch,
        "mismatch_verse_pct": pct(mismatch, both),
        "token_count_exception_verse_count": token_exceptions,
        "token_count_exception_pct": pct(token_exceptions, both),
        "sequence_only_exception_verse_count": sequence_only,
        "sequence_only_exception_pct": pct(sequence_only, both),
        "review_row_count": len(sample_rows),
        "sample_row_count": len(sample_rows),
        "unexported_exception_row_count": max(mismatch - len(sample_rows), 0),
        "critical_sample_count": severity_counts.get("critical", 0),
        "high_sample_count": severity_counts.get("high", 0),
        "medium_sample_count": severity_counts.get("medium", 0),
        "sample_exception_class_counts": dict(class_counts.most_common()),
        "book_priority_counts": dict(priority_counts.most_common()),
        "critical_book_count": sum(
            1 for row in book_rows if str(row["priority"]).startswith("critical")
        ),
        "high_book_count": priority_counts.get("high", 0),
        "psalms_exception_verse_count": psalm_row["mismatch_verse_count"],
        "psalms_exception_pressure_score": psalm_row["exception_pressure_score"],
        "top_exception_book": book_rows[0]["book"] if book_rows else "",
        "top_exception_book_score": book_rows[0]["exception_pressure_score"] if book_rows else 0.0,
        "source_approval_status": pilot_summary["source_approval_status"],
        "authority_verdict": (
            "exception_review_generated_not_authority: the OSHB pilot is cleaner after "
            "Hebrew-letter normalization, and exception rows are enumerable, but source "
            "approval, adjudication, and reviewer signoff are still incomplete."
        ),
    }


def build_visual_data(
    book_rows: list[dict[str, Any]],
    sample_rows: list[dict[str, Any]],
    division_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    class_counts = Counter(str(row["exception_class"]) for row in sample_rows)
    priority_counts = Counter(str(row["priority"]) for row in book_rows)
    gate_counts = Counter(str(row["status"]) for row in gate_rows)
    return {
        "book_pressure_rows": [
            {
                "label": row["book"],
                "value": row["exception_pressure_score"],
                "priority": row["priority"],
            }
            for row in book_rows
        ],
        "book_mismatch_rows": [
            {
                "label": row["book"],
                "value": row["mismatch_verse_count"],
                "priority": row["priority"],
            }
            for row in sorted(
                book_rows, key=lambda item: item["mismatch_verse_count"], reverse=True
            )
        ],
        "sample_class_rows": [
            {"label": label, "value": count} for label, count in class_counts.most_common()
        ],
        "book_priority_rows": [
            {"label": label, "value": count} for label, count in priority_counts.most_common()
        ],
        "gate_status_rows": [
            {"label": label, "value": count} for label, count in gate_counts.most_common()
        ],
        "division_exception_rows": [
            {"label": row["division"], "value": row["mismatch_verse_count"]}
            for row in sorted(
                division_rows,
                key=lambda item: item["mismatch_verse_count"],
                reverse=True,
            )
        ],
    }


def build_report() -> dict[str, Any]:
    pilot = load_json(OSHB_ALIGNMENT_PILOT_PATH)
    sample_rows = [classify_sample(row) for row in pilot["mismatch_rows"]]
    book_rows = build_book_rows(pilot["book_rows"], sample_rows)
    division_rows = build_division_rows(book_rows)
    summary = summarize(pilot, book_rows, sample_rows)
    gate_rows = build_gate_rows(summary)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "oshb_alignment_exception_review_generated_not_source_approval",
        "source_paths": {
            "oshb_alignment_pilot": str(OSHB_ALIGNMENT_PILOT_PATH.relative_to(ROOT)),
        },
        "source_boundary": {
            "scope": (
                "Derived exception-review workbook over the research-only OSHB alignment pilot."
            ),
            "forbidden_use": (
                "This report does not approve OSHB use, import morphology, alter raw source "
                "data, change canonical renderings, or authorize release."
            ),
            "approval_state": "source_approval_not_recorded",
        },
        "method": {
            "exception_basis": (
                "Book-level counts come from all verse comparisons in the OSHB pilot; "
                "review rows come from the complete exported mismatch row set."
            ),
            "review_routing": (
                "Rows are routed by token-count pressure, sequence similarity, book, "
                "and current authority boundary."
            ),
        },
        "summary": summary,
        "gate_rows": gate_rows,
        "division_rows": division_rows,
        "book_rows": book_rows,
        "sample_rows": sorted(
            sample_rows,
            key=lambda row: (
                {"critical": 0, "high": 1, "medium": 2}.get(str(row["severity"]), 9),
                float(row["sequence_similarity_pct"]),
                row["book"],
                row["osis_id"],
            ),
        ),
        "visual_data": build_visual_data(book_rows, sample_rows, division_rows, gate_rows),
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
    left = 275
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
    gate_rows = [
        [
            row["gate_id"],
            row["gate"],
            row["status"],
            row["evidence"],
            row["next_action"],
        ]
        for row in report["gate_rows"]
    ]
    division_rows = [
        [
            row["division"],
            row["book_count"],
            row["mismatch_verse_count"],
            f"{row['mismatch_verse_pct']:.2f}%",
            row["token_count_exception_verse_count"],
            f"{row['mean_sequence_similarity_pct']:.2f}%",
            row["critical_book_count"],
            row["high_book_count"],
        ]
        for row in report["division_rows"]
    ]
    book_rows = [
        [
            row["book"],
            row["division"],
            row["priority"],
            f"{row['exception_pressure_score']:.2f}",
            row["mismatch_verse_count"],
            f"{row['mismatch_verse_pct']:.2f}%",
            row["token_count_exception_verse_count"],
            row["sequence_only_exception_verse_count"],
            row["sample_row_count"],
            row["recommended_action"],
        ]
        for row in report["book_rows"]
    ]
    sample_rows = [
        [
            row["book"],
            row["osis_id"],
            row["severity"],
            row["exception_class"],
            row["oshb_token_count"],
            row["uxlc_token_count"],
            row["token_delta"],
            f"{row['sequence_similarity_pct']:.2f}%",
            ", ".join(row["review_lanes"]),
            " ".join(row["oshb_surface_window"]),
            " ".join(row["uxlc_surface_window"]),
        ]
        for row in report["sample_rows"][:90]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OSHB Alignment Exception Review</title>
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
    <h1>OSHB Alignment Exception Review</h1>
    <p class="lede">
      Reviewer-facing exception queue for the OSHB whole-Tanakh alignment pilot.
      It converts remaining OSHB-to-UXLC token differences into book priorities,
      gate status, sample classes, and role-based review lanes before any
      morphology import or authority claim.
    </p>
    <p class="meta">
      Generated {esc(report["generated_on"])} from OSHB commit
      {esc(summary["remote_commit_sha"])} dated {esc(summary["remote_commit_date"])}.
    </p>
  </header>
  <main>
    <section>
      <h2>Exception Verdict</h2>
      {
        render_cards(
            [
                (
                    "Remaining exceptions",
                    fmt_int(summary["mismatch_verse_count"]),
                    f"{fmt_pct(summary['mismatch_verse_pct'])} of compared verses.",
                ),
                (
                    "Exact matches",
                    fmt_pct(summary["exact_sequence_match_pct"]),
                    f"{fmt_int(summary['exact_sequence_match_verse_count'])} exact verses.",
                ),
                (
                    "Token-count exceptions",
                    fmt_int(summary["token_count_exception_verse_count"]),
                    f"{fmt_pct(summary['token_count_exception_pct'])} of compared verses.",
                ),
                (
                    "Sequence-only exceptions",
                    fmt_int(summary["sequence_only_exception_verse_count"]),
                    f"{fmt_pct(summary['sequence_only_exception_pct'])} of compared verses.",
                ),
                (
                    "Review rows",
                    fmt_int(summary["review_row_count"]),
                    f"{fmt_int(summary['unexported_exception_row_count'])} remain unexported.",
                ),
                (
                    "Critical books",
                    fmt_int(summary["critical_book_count"]),
                    "Includes any Psalm regression review lane.",
                ),
                (
                    "Psalms exceptions",
                    fmt_int(summary["psalms_exception_verse_count"]),
                    "Must be reviewed before local Psalm morphology changes.",
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
      <h2>Book Exception Pressure</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["book_pressure_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception review pressure by book",
            color="#8a6426",
            limit=20,
        )
    }</div>
    </section>

    <section>
      <h2>Exception Classes</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["sample_class_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception sample classes",
            color="#2f6f73",
            limit=12,
        )
    }</div>
    </section>

    <section>
      <h2>Gate Status</h2>
      <div class="chart">{
        svg_horizontal_bars(
            visual["gate_status_rows"],
            label_key="label",
            value_key="value",
            aria_label="OSHB exception review gate statuses",
            color="#a12727",
            limit=8,
        )
    }</div>
      {
        table(
            ["Gate", "Name", "Status", "Evidence", "Next Action"],
            gate_rows,
        )
    }
    </section>

    <section>
      <h2>Division Summary</h2>
      {
        table(
            [
                "Division",
                "Books",
                "Mismatch Verses",
                "Mismatch %",
                "Token Count Exceptions",
                "Mean Similarity",
                "Critical Books",
                "High Books",
            ],
            division_rows,
        )
    }
    </section>

    <section>
      <h2>Book Review Queue</h2>
      {
        table(
            [
                "Book",
                "Division",
                "Priority",
                "Pressure",
                "Mismatch Verses",
                "Mismatch %",
                "Token Count Exceptions",
                "Sequence-only",
                "Sample Rows",
                "Action",
            ],
            book_rows,
        )
    }
    </section>

    <section>
      <h2>Highest-Risk Review Rows</h2>
      {
        table(
            [
                "Book",
                "OSIS",
                "Severity",
                "Class",
                "OSHB Tokens",
                "UXLC Tokens",
                "Delta",
                "Similarity",
                "Review Lanes",
                "OSHB Window",
                "UXLC Window",
            ],
            sample_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def flatten_book_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "book",
        "division",
        "priority",
        "exception_pressure_score",
        "both_sources_verse_count",
        "exact_sequence_match_pct",
        "mean_sequence_similarity_pct",
        "mismatch_verse_count",
        "mismatch_verse_pct",
        "token_count_exception_verse_count",
        "sequence_only_exception_verse_count",
        "sample_row_count",
        "critical_sample_count",
        "high_sample_count",
        "review_lanes",
        "recommended_action",
    ]
    return [{key: row.get(key, "") for key in keys} for row in rows]


def flatten_sample_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "book",
        "division",
        "osis_id",
        "severity",
        "exception_class",
        "mismatch_type",
        "oshb_token_count",
        "uxlc_token_count",
        "token_delta",
        "sequence_similarity_pct",
        "first_difference_index",
        "review_lanes",
        "recommended_action",
        "oshb_surface_window",
        "uxlc_surface_window",
    ]
    return [{key: row.get(key, "") for key in keys} for row in rows]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate OSHB alignment exception-review workbook."
    )
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--book-csv-output", type=Path, default=DEFAULT_BOOK_CSV_OUTPUT)
    parser.add_argument("--sample-csv-output", type=Path, default=DEFAULT_SAMPLE_CSV_OUTPUT)
    parser.add_argument("--review-csv-output", type=Path, default=DEFAULT_REVIEW_CSV_OUTPUT)
    parser.add_argument("--gate-csv-output", type=Path, default=DEFAULT_GATE_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.book_csv_output, flatten_book_rows(report["book_rows"]))
    write_csv(args.sample_csv_output, flatten_sample_rows(report["sample_rows"]))
    write_csv(args.review_csv_output, flatten_sample_rows(report["sample_rows"]))
    write_csv(args.gate_csv_output, report["gate_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.book_csv_output}")
    print(f"Wrote {args.sample_csv_output}")
    print(f"Wrote {args.review_csv_output}")
    print(f"Wrote {args.gate_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
