from __future__ import annotations

import argparse
import csv
import gzip
import html
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"

BIBLIOGRAPHY_PATH = REPORT_ROOT / "doctoral_bibliography_provenance.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "doctoral_source_verification.json"
DEFAULT_SOURCE_CSV_OUTPUT = REPORT_ROOT / "doctoral_source_verification_sources.csv"
DEFAULT_TERM_CSV_OUTPUT = REPORT_ROOT / "doctoral_source_verification_terms.csv"
DEFAULT_GAP_CSV_OUTPUT = REPORT_ROOT / "doctoral_source_verification_gaps.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "doctoral_source_verification.html"

VERIFY_BYTES = 512_000
DEFAULT_TIMEOUT_SECONDS = 12.0

TERM_PATTERNS = {
    "public_domain": ["public domain", "pd"],
    "cc_by_4_0": ["cc by 4.0", "cc-by-4.0", "creative commons attribution 4.0"],
    "cc_by_nc_4_0": ["cc by-nc 4.0", "cc-by-nc-4.0", "noncommercial"],
    "cc_by_sa_4_0": ["cc by-sa 4.0", "cc-by-sa-4.0", "sharealike"],
    "license": ["license", "licence", "licensing"],
    "commercial": ["commercial", "non-commercial", "noncommercial"],
    "per_text": ["per-text", "per text", "each text"],
    "morphology": ["morphology", "morphological"],
    "semantic_role": ["semantic role", "semantic roles"],
    "referent": ["referent", "participant"],
    "commentary": ["commentary", "commentaries"],
    "api": ["api", "export"],
    "open_data": ["open data", "open corpus", "openly"],
}

LICENSE_EXPECTATION_TERMS = {
    "public domain": ["public_domain"],
    "cc by 4.0": ["cc_by_4_0", "license"],
    "cc by-nc": ["cc_by_nc_4_0", "license"],
    "cc by-sa": ["cc_by_sa_4_0", "license"],
    "per-text": ["per_text", "license"],
    "per text": ["per_text", "license"],
    "custom": ["license"],
    "restricted": ["license"],
    "open corpus": ["open_data", "license"],
    "open data": ["open_data", "license"],
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


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def decode_body(raw: bytes, headers: Any) -> str:
    if str(headers.get("Content-Encoding", "")).lower() == "gzip":
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    content_type = str(headers.get("Content-Type", ""))
    charset = "utf-8"
    match = re.search(r"charset=([\w.-]+)", content_type, flags=re.I)
    if match:
        charset = match.group(1)
    return raw.decode(charset, errors="replace")


def extract_title(text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
    if not match:
        return ""
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return html.unescape(title)[:240]


def detect_terms(text: str) -> list[str]:
    lowered = text.lower()
    detected = []
    for term_id, patterns in TERM_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            detected.append(term_id)
    return detected


def expected_license_terms(license_or_access: str) -> list[str]:
    lowered = license_or_access.lower()
    expected: set[str] = set()
    for needle, terms in LICENSE_EXPECTATION_TERMS.items():
        if needle in lowered:
            expected.update(terms)
    if "license" in lowered:
        expected.add("license")
    return sorted(expected)


def license_claim_status(expected: list[str], detected: list[str], url: str) -> str:
    if not url:
        return "not_applicable_no_url"
    if not expected:
        return "no_specific_license_term_expected"
    if set(expected).intersection(detected):
        return "term_detected_needs_review"
    return "term_not_detected_needs_review"


def fetch_url(url: str, timeout_seconds: float) -> dict[str, Any]:
    if not url:
        return {
            "reachable": False,
            "http_status": "",
            "final_url": "",
            "content_type": "",
            "title": "",
            "detected_terms": [],
            "error_type": "no_url",
            "error": "No official URL supplied.",
            "elapsed_ms": 0.0,
        }

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "AlephTav-source-verification/1.0 (research provenance check; no bulk download)"
            ),
            "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.2",
        },
        method="GET",
    )
    started = time.perf_counter()
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds, context=context) as response:
            raw = response.read(VERIFY_BYTES)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            text = decode_body(raw, response.headers)
            return {
                "reachable": 200 <= int(response.status) < 400,
                "http_status": int(response.status),
                "final_url": response.geturl(),
                "content_type": response.headers.get("Content-Type", ""),
                "title": extract_title(text),
                "detected_terms": detect_terms(text),
                "error_type": "",
                "error": "",
                "elapsed_ms": elapsed_ms,
            }
    except urllib.error.HTTPError as error:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        body = error.read(VERIFY_BYTES)
        text = decode_body(body, error.headers)
        return {
            "reachable": 200 <= int(error.code) < 400,
            "http_status": int(error.code),
            "final_url": error.geturl(),
            "content_type": error.headers.get("Content-Type", ""),
            "title": extract_title(text),
            "detected_terms": detect_terms(text),
            "error_type": "http_error",
            "error": str(error),
            "elapsed_ms": elapsed_ms,
        }
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "reachable": False,
            "http_status": "",
            "final_url": "",
            "content_type": "",
            "title": "",
            "detected_terms": [],
            "error_type": type(error).__name__,
            "error": str(error)[:500],
            "elapsed_ms": elapsed_ms,
        }


def verification_status(row: dict[str, Any], fetch: dict[str, Any], claim_status: str) -> str:
    if not row.get("official_url"):
        if row.get("source_id") == "internal_review_audit_service":
            return "internal_workflow_no_url"
        return "no_url_needs_manual_bibliography"
    if not fetch["reachable"]:
        return "unreachable_needs_manual_review"
    if claim_status == "term_not_detected_needs_review":
        return "reachable_license_term_not_detected"
    return "reachable_needs_license_review"


def build_source_rows(timeout_seconds: float) -> list[dict[str, Any]]:
    bibliography = load_json(BIBLIOGRAPHY_PATH)
    rows = []
    for source in bibliography.get("bibliography_rows", []):
        fetch = fetch_url(str(source.get("official_url", "")), timeout_seconds)
        expected = expected_license_terms(str(source.get("license_or_access", "")))
        detected = list(fetch["detected_terms"])
        claim_status = license_claim_status(
            expected,
            detected,
            str(source.get("official_url", "")),
        )
        rows.append(
            {
                "bibliography_id": source["bibliography_id"],
                "source_class": source["source_class"],
                "source_id": source["source_id"],
                "label": source["label"],
                "tier": source["tier"],
                "license_or_access": source["license_or_access"],
                "license_risk": source["license_risk"],
                "official_url": source["official_url"],
                "reachable": fetch["reachable"],
                "http_status": fetch["http_status"],
                "final_url": fetch["final_url"],
                "content_type": fetch["content_type"],
                "title": fetch["title"],
                "expected_license_terms": expected,
                "detected_terms": detected,
                "license_claim_status": claim_status,
                "verification_status": verification_status(source, fetch, claim_status),
                "error_type": fetch["error_type"],
                "error": fetch["error"],
                "elapsed_ms": fetch["elapsed_ms"],
                "authority_status": source["authority_status"],
                "generation_policy": source["generation_policy"],
                "authority_boundary": source["authority_boundary"],
            }
        )
    return rows


def build_term_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source in source_rows:
        for term in source["detected_terms"]:
            rows.append(
                {
                    "bibliography_id": source["bibliography_id"],
                    "source_id": source["source_id"],
                    "term": term,
                    "license_claim_status": source["license_claim_status"],
                    "verification_status": source["verification_status"],
                }
            )
    return rows


def build_gap_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source in source_rows:
        status = source["verification_status"]
        if status in {"reachable_needs_license_review", "internal_workflow_no_url"}:
            continue
        if status == "reachable_license_term_not_detected":
            severity = "license_review"
            next_action = "Open the official URL and verify license/provenance manually."
        elif status == "unreachable_needs_manual_review":
            severity = "reachability"
            next_action = (
                "Retry source URL, find a stable official landing page, or remove candidate."
            )
        else:
            severity = "bibliography"
            next_action = "Add an official URL or mark as internal/manual workflow."
        rows.append(
            {
                "gap_id": f"verify.{source['source_id']}",
                "source_id": source["source_id"],
                "source_class": source["source_class"],
                "severity": severity,
                "label": source["label"],
                "evidence": (
                    f"status={status}; http={source['http_status']}; "
                    f"terms={', '.join(source['detected_terms']) or 'none'}"
                ),
                "official_url": source["official_url"],
                "next_action": next_action,
            }
        )
    return rows


def build_report(timeout_seconds: float) -> dict[str, Any]:
    source_rows = build_source_rows(timeout_seconds)
    term_rows = build_term_rows(source_rows)
    gap_rows = build_gap_rows(source_rows)
    url_rows = [row for row in source_rows if row["official_url"]]
    candidate_rows = [
        row for row in source_rows if row["source_class"] == "source_acquisition_candidate"
    ]
    reachable_rows = [row for row in url_rows if row["reachable"]]
    claim_detected_rows = [
        row for row in source_rows if row["license_claim_status"] == "term_detected_needs_review"
    ]
    status_counts = Counter(str(row["verification_status"]) for row in source_rows)
    risk_counts = Counter(str(row["license_risk"]) for row in source_rows)
    status_count_rows = count_rows(dict(status_counts.most_common()), "status", "count")
    risk_count_rows = count_rows(dict(risk_counts.most_common()), "license_risk", "count")
    gap_count_rows = gap_severity_rows(gap_rows)

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "doctoral source verification generated; not license approval",
        "source_paths": {"bibliography": str(BIBLIOGRAPHY_PATH.relative_to(ROOT))},
        "method": {
            "boundary": (
                "HTTP reachability and keyword detection are evidence routing, not legal approval."
            ),
            "byte_limit": VERIFY_BYTES,
            "timeout_seconds": timeout_seconds,
            "mutation_boundary": "This report does not download source corpora or alter data/raw.",
        },
        "summary": {
            "source_count": len(source_rows),
            "url_source_count": len(url_rows),
            "reachable_url_count": len(reachable_rows),
            "reachable_url_pct": pct(len(reachable_rows), len(url_rows)),
            "candidate_source_count": len(candidate_rows),
            "candidate_reachable_count": sum(1 for row in candidate_rows if row["reachable"]),
            "local_manifest_source_count": sum(
                1 for row in source_rows if row["source_class"] == "local_manifest"
            ),
            "no_url_count": sum(1 for row in source_rows if not row["official_url"]),
            "license_term_detected_count": len(claim_detected_rows),
            "license_term_detected_pct": pct(len(claim_detected_rows), len(source_rows)),
            "gap_count": len(gap_rows),
            "reachable_license_review_count": status_counts.get(
                "reachable_needs_license_review", 0
            ),
            "license_term_not_detected_count": status_counts.get(
                "reachable_license_term_not_detected", 0
            ),
            "unreachable_count": status_counts.get("unreachable_needs_manual_review", 0),
            "source_approval_count": 0,
            "status_counts": dict(status_counts.most_common()),
            "license_risk_counts": dict(risk_counts.most_common()),
            "status": "verification_generated_not_approval",
        },
        "source_rows": source_rows,
        "term_rows": term_rows,
        "gap_rows": gap_rows,
        "visual_data": {
            "status_counts": status_count_rows,
            "license_risk_counts": risk_count_rows,
            "gap_severity_counts": gap_count_rows,
        },
    }


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def metric_cards(cards: list[tuple[str, str, str]]) -> str:
    return "\n".join(
        f"""
        <article class="metric-card">
          <h3>{esc(label)}</h3>
          <p class="metric-value">{esc(value)}</p>
          <p>{esc(note)}</p>
        </article>
        """
        for label, value, note in cards
    )


def clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def bar_rows(
    rows: list[dict[str, Any]],
    *,
    label_key: str,
    value_key: str,
    max_value: float | None = None,
    suffix: str = "",
) -> str:
    if max_value is None:
        max_value = max((float(row.get(value_key) or 0) for row in rows), default=1.0)
    if not max_value:
        max_value = 1.0
    output = []
    for row in rows:
        value = float(row.get(value_key) or 0)
        width = clamp(value / max_value * 100)
        output.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{esc(row.get(label_key, ""))}</div>
              <div class="bar-track">
                <div class="bar-fill" style="width: {width}%"></div>
              </div>
              <div class="bar-value">{esc(f"{value:.2f}{suffix}")}</div>
            </div>
            """
        )
    return "\n".join(output)


def count_rows(mapping: dict[str, Any], label_key: str, value_key: str) -> list[dict[str, Any]]:
    return [{label_key: key, value_key: value} for key, value in mapping.items()]


def gap_severity_rows(gap_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(row["severity"]) for row in gap_rows)
    return [{"severity": key, "count": value} for key, value in counts.most_common()]


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    status_rows = count_rows(summary["status_counts"], "status", "count")
    risk_rows = count_rows(summary["license_risk_counts"], "license_risk", "count")
    source_rows = [
        [
            row["source_id"],
            row["source_class"],
            row["label"],
            row["license_risk"],
            row["verification_status"],
            row["http_status"],
            row["license_claim_status"],
            ", ".join(row["detected_terms"]),
            row["official_url"],
        ]
        for row in report["source_rows"]
    ]
    gap_rows = [
        [
            row["gap_id"],
            row["severity"],
            row["label"],
            row["evidence"],
            row["official_url"],
            row["next_action"],
        ]
        for row in report["gap_rows"]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Doctoral Source Verification</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #53616f;
      --line: #c9d1d9;
      --panel: #f8fafc;
      --accent: #2868a8;
      --accent-2: #7c5b2f;
      --bad: #a12727;
    }}
    body {{
      margin: 0;
      background: #fff;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 32px 24px 56px;
    }}
    h1, h2, h3 {{
      line-height: 1.15;
      margin: 0;
    }}
    h1 {{
      font-size: 2.1rem;
      max-width: 980px;
    }}
    h2 {{
      margin-top: 36px;
      font-size: 1.45rem;
    }}
    h3 {{
      color: var(--muted);
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    p {{
      color: var(--muted);
      margin: 8px 0 0;
    }}
    .lede {{
      max-width: 980px;
      font-size: 1.05rem;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 24px;
    }}
    .metric-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 16px;
    }}
    .metric-value {{
      color: var(--ink);
      font-size: 1.7rem;
      font-weight: 700;
      margin-top: 6px;
    }}
    .grid-2 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 20px;
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: minmax(170px, 1.2fr) minmax(140px, 2fr) 86px;
      gap: 10px;
      align-items: center;
      margin: 10px 0;
      font-size: 0.92rem;
    }}
    .bar-track {{
      height: 12px;
      background: #edf1f5;
      border-radius: 4px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
    }}
    .bar-value {{
      color: var(--muted);
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 0.86rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f4f7fa;
      color: var(--muted);
    }}
    .callout {{
      border-left: 4px solid var(--bad);
      background: #fff7f5;
      padding: 12px 16px;
      margin-top: 20px;
    }}
    .callout strong {{
      color: var(--bad);
    }}
    footer {{
      margin-top: 32px;
      color: var(--muted);
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>
<main>
  <h1>Doctoral Source Verification Snapshot</h1>
  <p class="lede">
    This report checks the official URLs already present in the bibliography
    apparatus and records reachability, redirect targets, titles, detected
    license/provenance terms, and verification gaps.
  </p>
  <div class="callout">
    <strong>Boundary:</strong>
    {esc(report["method"]["boundary"])}
    {esc(report["method"]["mutation_boundary"])}
  </div>

  <section class="metric-grid" aria-label="Source verification metrics">
    {
        metric_cards(
            [
                (
                    "URL Sources",
                    fmt_int(summary["url_source_count"]),
                    f"{fmt_int(summary['reachable_url_count'])} reachable.",
                ),
                (
                    "Reachability",
                    f"{summary['reachable_url_pct']:.2f}%",
                    "HTTP 2xx/3xx official URL responses.",
                ),
                (
                    "License Terms",
                    fmt_int(summary["license_term_detected_count"]),
                    "Detected terms still require review.",
                ),
                (
                    "Verification Gaps",
                    fmt_int(summary["gap_count"]),
                    f"{fmt_int(summary['unreachable_count'])} unreachable.",
                ),
                (
                    "Approvals",
                    fmt_int(summary["source_approval_count"]),
                    "Verification is not approval.",
                ),
            ]
        )
    }
  </section>

  <section>
    <h2>Visual Verification</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Status Counts</h3>
        {bar_rows(status_rows, label_key="status", value_key="count")}
      </div>
      <div class="panel">
        <h3>License Risk Counts</h3>
        {bar_rows(risk_rows, label_key="license_risk", value_key="count")}
      </div>
    </div>
  </section>

  <section>
    <h2>Source Verification Rows</h2>
    {
        table(
            ["ID", "Class", "Label", "Risk", "Status", "HTTP", "Claim", "Terms", "URL"], source_rows
        )
    }
  </section>

  <section>
    <h2>Verification Gaps</h2>
    {table(["ID", "Severity", "Label", "Evidence", "URL", "Next Action"], gap_rows)}
  </section>

  <footer>
    Generated {esc(report["generated_at"])}. Fetch limit:
    {fmt_int(report["method"]["byte_limit"])} bytes per URL.
  </footer>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate live source URL verification report.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--source-csv-output", type=Path, default=DEFAULT_SOURCE_CSV_OUTPUT)
    parser.add_argument("--term-csv-output", type=Path, default=DEFAULT_TERM_CSV_OUTPUT)
    parser.add_argument("--gap-csv-output", type=Path, default=DEFAULT_GAP_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.timeout_seconds)
    write_json(args.json_output, report)
    write_csv(args.source_csv_output, report["source_rows"])
    write_csv(args.term_csv_output, report["term_rows"])
    write_csv(args.gap_csv_output, report["gap_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")


if __name__ == "__main__":
    main()
