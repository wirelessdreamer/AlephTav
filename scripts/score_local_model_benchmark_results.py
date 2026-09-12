from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "reports" / "research" / "local_model_benchmark_suite.json"
RESULTS_PATH = ROOT / "reports" / "research" / "local_model_benchmark_results.jsonl"
OUTPUT_SCHEMA_PATH = ROOT / "app" / "llm" / "contracts" / "generation_output.schema.json"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "local_model_benchmark_result_audit.json"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "local_model_benchmark_result_audit.html"

TOKEN_RE = re.compile(r"ps\d{3}\.v\d{3}\.t\d{3}")
HEBREW_RE = re.compile(r"[\u0590-\u05ff]")
RECEPTION_TERMS = {
    "christ",
    "christian",
    "church",
    "messiah",
    "messianic",
    "rabbinic",
    "jewish",
    "judaism",
    "jesus",
    "apostle",
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


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"results file not found: {path}"]
    rows = []
    errors = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: JSON decode error: {exc}")
                continue
            if not isinstance(row, dict):
                errors.append(f"line {line_number}: expected object")
                continue
            row["_line_number"] = line_number
            rows.append(row)
    return rows, errors


def task_by_id(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(task["task_id"]): task for task in suite.get("tasks", [])}


def valid_token_ids(task: dict[str, Any]) -> set[str]:
    tokens = task["generation_input"]["locked_inputs"]["source"]["tokens"]
    return {str(token["token_id"]) for token in tokens if token.get("token_id")}


def collect_token_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, str):
        refs.update(TOKEN_RE.findall(value))
    elif isinstance(value, list):
        for item in value:
            refs.update(collect_token_refs(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in {"token_id", "source_token_id"} and isinstance(item, str):
                refs.add(item)
            elif key in {"token_ids", "source_token_ids", "tokens"}:
                refs.update(collect_token_refs(item))
            else:
                refs.update(collect_token_refs(item))
    return refs


def alignment_score(coverage_pct: float) -> int:
    if coverage_pct >= 90:
        return 5
    if coverage_pct >= 75:
        return 4
    if coverage_pct >= 50:
        return 3
    if coverage_pct >= 25:
        return 2
    if coverage_pct > 0:
        return 1
    return 0


def translation_basis_score(candidate: dict[str, Any]) -> tuple[int, list[str]]:
    basis = candidate.get("translation_basis") or {}
    flags = []
    score = 0
    if basis.get("basis_type") == "hebrew_to_english":
        score += 2
    else:
        flags.append("basis_type_not_hebrew_to_english")
    source_ids = [str(item).lower() for item in basis.get("source_ids", [])]
    if any("uxlc" in item or "wlc" in item for item in source_ids):
        score += 2
    else:
        flags.append("source_ids_missing_uxlc_or_wlc")
    source_language = str(basis.get("source_language") or "").lower()
    if "hebrew" in source_language or source_language in {"he", "hbo"}:
        score += 1
    else:
        flags.append("source_language_not_hebrew")
    return score, flags


def reception_text_flags(text: str) -> list[str]:
    lowered = text.lower()
    return sorted(term for term in RECEPTION_TERMS if term in lowered)


def candidate_auto_checks(
    candidate: dict[str, Any],
    *,
    task: dict[str, Any],
    candidate_index: int,
) -> dict[str, Any]:
    allowed = valid_token_ids(task)
    task_source = str(
        task["generation_input"]["locked_inputs"]["source"].get("source_hebrew") or ""
    )
    source_anchor = candidate.get("source_anchor") or {}
    anchor_source_text = str(source_anchor.get("source_text") or "")
    refs = collect_token_refs(candidate.get("alignment_hints", []))
    refs.update(collect_token_refs(candidate.get("preserved_source_images", [])))
    invalid_refs = sorted(ref for ref in refs if ref not in allowed)
    coverage_pct = pct(len(refs & allowed), len(allowed))
    basis_score, basis_flags = translation_basis_score(candidate)
    text = str(candidate.get("text") or "")
    reception_flags = reception_text_flags(text)
    drift_flags = candidate.get("drift_flags") or []
    preserved_images = candidate.get("preserved_source_images") or []
    grounding = candidate.get("grounding_confidence")
    grounding_score = 0
    if isinstance(grounding, int | float):
        grounding_score = round(max(0.0, min(1.0, float(grounding))) * 5, 2)
    source_anchor_matches = bool(anchor_source_text) and anchor_source_text == task_source
    source_anchor_has_hebrew = bool(HEBREW_RE.search(anchor_source_text))
    source_anchor_flags = []
    if not source_anchor_matches:
        source_anchor_flags.append("source_anchor_text_mismatch")
    if task_source and not source_anchor_has_hebrew:
        source_anchor_flags.append("source_anchor_missing_hebrew_chars")

    return {
        "candidate_index": candidate_index,
        "alignment_token_ref_count": len(refs),
        "alignment_coverage_pct": coverage_pct,
        "invalid_token_refs": invalid_refs,
        "alignment_score_0_5": alignment_score(coverage_pct),
        "translation_basis_score_0_5": basis_score,
        "translation_basis_flags": basis_flags,
        "reception_terms_in_translation_text": reception_flags,
        "drift_flag_count": len(drift_flags),
        "preserved_source_image_count": len(preserved_images),
        "grounding_confidence": grounding,
        "grounding_score_0_5": grounding_score,
        "source_anchor_text_matches_task": source_anchor_matches,
        "source_anchor_has_hebrew_chars": source_anchor_has_hebrew,
        "source_anchor_flags": source_anchor_flags,
    }


def score_result(
    result: dict[str, Any],
    *,
    task: dict[str, Any] | None,
    validator: Draft202012Validator,
) -> dict[str, Any]:
    errors = []
    task_id = str(result.get("task_id") or "")
    model_profile_id = str(result.get("model_profile_id") or "")
    output = result.get("output")

    if task is None:
        errors.append("unknown_task_id")
    if not model_profile_id:
        errors.append("missing_model_profile_id")
    if not isinstance(output, dict):
        errors.append("missing_or_invalid_output")
        output = {}

    schema_errors = [
        error.message for error in sorted(validator.iter_errors(output), key=lambda item: item.path)
    ]
    if schema_errors:
        errors.extend(f"schema: {message}" for message in schema_errors)

    if task is not None and output:
        if output.get("unit_id") != task["unit_id"]:
            errors.append("output_unit_id_mismatch")
        if output.get("layer") != task["layer"]:
            errors.append("output_layer_mismatch")

    candidate_checks = []
    if task is not None and isinstance(output.get("candidates"), list):
        for index, candidate in enumerate(output["candidates"], start=1):
            if isinstance(candidate, dict):
                candidate_checks.append(
                    candidate_auto_checks(candidate, task=task, candidate_index=index)
                )

    schema_valid = not schema_errors and isinstance(result.get("output"), dict)
    alignment_scores = [item["alignment_score_0_5"] for item in candidate_checks]
    basis_scores = [item["translation_basis_score_0_5"] for item in candidate_checks]
    invalid_ref_count = sum(len(item["invalid_token_refs"]) for item in candidate_checks)
    reception_leak_count = sum(
        len(item["reception_terms_in_translation_text"]) for item in candidate_checks
    )
    source_anchor_issue_count = sum(len(item["source_anchor_flags"]) for item in candidate_checks)
    for check in candidate_checks:
        for flag in check["source_anchor_flags"]:
            errors.append(flag)

    return {
        "task_id": task_id,
        "model_profile_id": model_profile_id,
        "line_number": result.get("_line_number"),
        "known_task": task is not None,
        "schema_valid": schema_valid,
        "error_count": len(errors),
        "errors": errors,
        "candidate_count": len(candidate_checks),
        "mean_alignment_score_0_5": round(sum(alignment_scores) / len(alignment_scores), 2)
        if alignment_scores
        else 0,
        "mean_translation_basis_score_0_5": round(sum(basis_scores) / len(basis_scores), 2)
        if basis_scores
        else 0,
        "invalid_token_ref_count": invalid_ref_count,
        "reception_leak_term_count": reception_leak_count,
        "source_anchor_issue_count": source_anchor_issue_count,
        "candidate_checks": candidate_checks,
        "runtime": result.get("runtime") or {},
    }


def expected_pairs(suite: dict[str, Any]) -> set[tuple[str, str]]:
    models = [str(model) for model in suite.get("recommended_bakeoff_models", [])]
    tasks = [str(task["task_id"]) for task in suite.get("tasks", [])]
    return {(task_id, model) for task_id in tasks for model in models}


def summarize(
    suite: dict[str, Any],
    rows: list[dict[str, Any]],
    scored: list[dict[str, Any]],
    load_errors: list[str],
) -> dict[str, Any]:
    expected = expected_pairs(suite)
    submitted = {
        (str(item["task_id"]), str(item["model_profile_id"]))
        for item in scored
        if item["task_id"] and item["model_profile_id"]
    }
    duplicate_counter: Counter[tuple[str, str]] = Counter(
        (str(row.get("task_id")), str(row.get("model_profile_id")))
        for row in rows
        if row.get("task_id") and row.get("model_profile_id")
    )
    duplicates = [
        {"task_id": task_id, "model_profile_id": model, "count": count}
        for (task_id, model), count in duplicate_counter.items()
        if count > 1
    ]
    schema_valid = sum(1 for item in scored if item["schema_valid"])
    known_task = sum(1 for item in scored if item["known_task"])
    model_counts: Counter[str] = Counter(str(item["model_profile_id"]) for item in scored)
    error_counts: Counter[str] = Counter()
    source_anchor_issues = sum(int(item.get("source_anchor_issue_count") or 0) for item in scored)
    for item in scored:
        for error in item["errors"]:
            error_counts[str(error).split(":")[0]] += 1
    return {
        "expected_result_count": len(expected),
        "submitted_result_count": len(rows),
        "scored_result_count": len(scored),
        "submitted_expected_result_count": len(submitted & expected),
        "missing_expected_result_count": len(expected - submitted),
        "unexpected_result_count": len(submitted - expected),
        "schema_valid_result_count": schema_valid,
        "schema_valid_pct": pct(schema_valid, len(scored)),
        "known_task_result_count": known_task,
        "known_task_pct": pct(known_task, len(scored)),
        "duplicate_result_count": len(duplicates),
        "load_error_count": len(load_errors),
        "model_result_counts": dict(model_counts.most_common()),
        "error_category_counts": dict(error_counts.most_common()),
        "source_anchor_issue_count": source_anchor_issues,
        "duplicates": duplicates[:50],
    }


def build_audit(
    suite_path: Path,
    results_path: Path,
    output_schema_path: Path,
) -> dict[str, Any]:
    suite = load_json(suite_path)
    output_schema = load_json(output_schema_path)
    validator = Draft202012Validator(output_schema)
    rows, load_errors = load_jsonl(results_path)
    tasks = task_by_id(suite)
    scored = [
        score_result(row, task=tasks.get(str(row.get("task_id") or "")), validator=validator)
        for row in rows
    ]
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "benchmark result audit; automated checks only, not human review",
        "source_paths": {
            "suite": str(suite_path.relative_to(ROOT))
            if suite_path.is_relative_to(ROOT)
            else str(suite_path),
            "results": str(results_path.relative_to(ROOT))
            if results_path.is_relative_to(ROOT)
            else str(results_path),
            "output_schema": str(output_schema_path.relative_to(ROOT))
            if output_schema_path.is_relative_to(ROOT)
            else str(output_schema_path),
        },
        "summary": summarize(suite, rows, scored, load_errors),
        "load_errors": load_errors,
        "scored_results": scored,
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
    row_h = 28
    left = 260
    right = 60
    top = 24
    height = top * 2 + row_h * max(1, len(rows))
    max_value = max((float(row[value_key]) for row in rows), default=1.0)
    chart_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(aria_label)}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    if not rows:
        parts.append(
            f'<text x="{width / 2}" y="{height / 2}" text-anchor="middle" '
            'font-size="13" fill="#667581">No rows</text>'
        )
        parts.append("</svg>")
        return "".join(parts)
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


def rows_from_counter(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
    return [
        {label_key: key, "count": value}
        for key, value in sorted(counter.items(), key=lambda item: item[1], reverse=True)
    ]


def completion_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"metric": "expected", "count": summary["expected_result_count"]},
        {"metric": "submitted", "count": summary["submitted_result_count"]},
        {"metric": "schema-valid", "count": summary["schema_valid_result_count"]},
        {"metric": "missing", "count": summary["missing_expected_result_count"]},
    ]


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


def render_html(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    result_rows = [
        [
            item["task_id"],
            item["model_profile_id"],
            "yes" if item["schema_valid"] else "no",
            fmt_int(item["candidate_count"]),
            f"{item['mean_alignment_score_0_5']:.2f}",
            f"{item['mean_translation_basis_score_0_5']:.2f}",
            fmt_int(item["invalid_token_ref_count"]),
            fmt_int(item["reception_leak_term_count"]),
            fmt_int(item["source_anchor_issue_count"]),
        ]
        for item in audit["scored_results"][:100]
    ]
    if not result_rows:
        result_rows = [["No submitted model results yet", "", "", "", "", "", "", "", ""]]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Local Model Benchmark Result Audit</title>
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
    <h1>AlephTav Local Model Benchmark Result Audit</h1>
    <p class="lede">
      Automated validation for local model benchmark outputs. It checks JSON
      schema validity, task identity, token references, translation basis,
      obvious reception leakage, and runtime metadata presence. Human review is
      still required for linguistic, poetic, cultural, and theological scoring.
    </p>
    <p class="meta">
      Generated {esc(audit["generated_on"])} from {esc(audit["source_paths"]["results"])}.
    </p>
  </header>
  <main>
    <section>
      <h2>Run Completion</h2>
      {
        metric_cards(
            [
                (
                    "Expected results",
                    fmt_int(summary["expected_result_count"]),
                    "Benchmark tasks multiplied by planned models.",
                ),
                (
                    "Submitted results",
                    fmt_int(summary["submitted_result_count"]),
                    "JSONL model-output rows loaded.",
                ),
                (
                    "Schema valid",
                    f'''{summary["schema_valid_pct"]:.2f}%''',
                    "Submitted rows passing generation_output schema.",
                ),
                (
                    "Missing expected",
                    fmt_int(summary["missing_expected_result_count"]),
                    "Expected model-task rows not submitted yet.",
                ),
                (
                    "Anchor issues",
                    fmt_int(summary["source_anchor_issue_count"]),
                    "Candidate source anchors not matching source Hebrew.",
                ),
            ]
        )
    }
      <div class="warning">
        This report is an automated audit, not a translation-quality verdict.
        It can reject malformed or poorly grounded outputs, but it cannot sign
        off accuracy without reviewer scoring.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            completion_rows(summary),
            label_key="metric",
            value_key="count",
            aria_label="Benchmark result completion",
            color="#2f6f73",
        )
    }</div>
    </section>

    <section>
      <h2>Error Profile</h2>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["error_category_counts"], "error"),
            label_key="error",
            value_key="count",
            aria_label="Benchmark result error categories",
            color="#9b3d3d",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["model_result_counts"], "model"),
            label_key="model",
            value_key="count",
            aria_label="Submitted results by model",
            color="#58508d",
        )
    }</div>
    </section>

    <section>
      <h2>Scored Rows</h2>
      {
        table(
            [
                "Task",
                "Model",
                "Schema valid",
                "Candidates",
                "Alignment",
                "Basis",
                "Bad token refs",
                "Reception terms",
                "Anchor issues",
            ],
            result_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score local model benchmark result JSONL with automated checks."
    )
    parser.add_argument("--suite", type=Path, default=SUITE_PATH)
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--output-schema", type=Path, default=OUTPUT_SCHEMA_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = build_audit(args.suite, args.results, args.output_schema)
    write_json(args.json_output, audit)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(audit), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
