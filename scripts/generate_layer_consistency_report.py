from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"

SUITE_PATH = REPORT_ROOT / "contextual_expanded_benchmark_suite.json"
RESULTS_PATH = REPORT_ROOT / "contextual_expanded_benchmark_results.jsonl"
AUDIT_PATH = REPORT_ROOT / "contextual_expanded_benchmark_result_audit.json"
CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "layer_consistency_report.json"
DEFAULT_PAIR_CSV_OUTPUT = REPORT_ROOT / "layer_consistency_pairs.csv"
DEFAULT_MODEL_CSV_OUTPUT = REPORT_ROOT / "layer_consistency_models.csv"
DEFAULT_FLAG_CSV_OUTPUT = REPORT_ROOT / "layer_consistency_flags.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "layer_consistency_report.html"

WORD_RE = re.compile(r"[a-z][a-z'_-]*")
HEBREW_MARKS_RE = re.compile(r"[\u0591-\u05c7]")
DIVINE_NAME_SURFACES = {"יהוה", "יה", "אדני", "אלהים", "אלוהים", "אל"}
DIVINE_NAME_WORDS = {
    "adonai",
    "el",
    "elohim",
    "god",
    "lord",
    "yah",
    "yhwh",
    "yahweh",
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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            row = json.loads(text)
            row["_line_number"] = line_number
            rows.append(row)
    return rows


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    return f"{int(value):,}"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def rel(path: Path) -> str:
    resolved = path.resolve()
    return str(resolved.relative_to(ROOT)) if resolved.is_relative_to(ROOT) else str(path)


def words(text: str) -> list[str]:
    return [word.strip("'_-").lower() for word in WORD_RE.findall(text.lower())]


def word_set(text: str) -> set[str]:
    return set(words(text))


def normalized_text(text: str) -> str:
    return " ".join(words(text))


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return round(len(left & right) / len(left | right), 4)


def strip_hebrew_marks(text: str) -> str:
    return HEBREW_MARKS_RE.sub("", text)


def source_has_divine_name(task: dict[str, Any]) -> bool:
    source = task["generation_input"]["locked_inputs"]["source"]
    for token in source.get("tokens", []):
        surface = strip_hebrew_marks(str(token.get("surface") or ""))
        lemma = strip_hebrew_marks(str(token.get("lemma") or ""))
        gloss = str(token.get("display_gloss") or "").lower()
        if surface in DIVINE_NAME_SURFACES or lemma in DIVINE_NAME_SURFACES:
            return True
        if any(term in gloss for term in ("yhwh", "yahweh", "lord", "god")):
            return True
    return False


def divine_name_renderings(text: str) -> list[str]:
    text_words = word_set(text)
    return sorted(text_words & DIVINE_NAME_WORDS)


def task_by_id(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(task["task_id"]): task for task in suite.get("tasks", [])}


def scored_by_pair(audit: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows = {}
    for row in audit.get("scored_results", []):
        task_id = str(row.get("task_id") or "")
        model = str(row.get("model_profile_id") or "")
        if task_id and model:
            rows[(task_id, model)] = row
    return rows


def claim_by_unit(claim_matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["unit_id"]): row
        for row in claim_matrix.get("unit_claim_rows", [])
        if row.get("unit_id")
    }


def first_candidate_text(result: dict[str, Any]) -> str:
    output = result.get("output")
    if not isinstance(output, dict):
        return ""
    candidates = output.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return ""
    return str(candidate.get("text") or "")


def layer_pair_groups(
    *,
    suite: dict[str, Any],
    results: list[dict[str, Any]],
) -> tuple[dict[tuple[str, str], dict[str, dict[str, Any]]], list[dict[str, Any]]]:
    tasks = task_by_id(suite)
    groups: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    unpaired = []
    for result in results:
        task = tasks.get(str(result.get("task_id") or ""))
        if not task:
            continue
        layer = str(task.get("layer") or "")
        if layer not in {"gloss", "literal"}:
            continue
        key = (str(task["unit_id"]), str(result.get("model_profile_id") or ""))
        groups[key][layer] = result
    for (unit_id, model), layers in groups.items():
        if not {"gloss", "literal"} <= set(layers):
            unpaired.append(
                {
                    "unit_id": unit_id,
                    "model_profile_id": model,
                    "available_layers": sorted(layers),
                    "missing_layers": sorted({"gloss", "literal"} - set(layers)),
                }
            )
    return groups, unpaired


def pair_flags(
    *,
    exact_duplicate: bool,
    similarity_pct: float,
    word_delta: int,
    gloss_word_count: int,
    literal_word_count: int,
    source_divine_name: bool,
    gloss_divine: list[str],
    literal_divine: list[str],
    claim: dict[str, Any],
    both_schema_valid: bool,
) -> list[str]:
    flags = []
    if not both_schema_valid:
        flags.append("schema_failure_blocks_layer_assessment")
    if exact_duplicate:
        flags.append("exact_gloss_literal_duplicate")
    elif similarity_pct >= 90:
        flags.append("near_gloss_literal_duplicate")
    if similarity_pct >= 75 and abs(word_delta) <= 1:
        flags.append("weak_layer_differentiation")
    if gloss_word_count > literal_word_count:
        flags.append("gloss_longer_than_literal")
    if source_divine_name:
        if not gloss_divine or not literal_divine:
            flags.append("divine_name_missing_in_one_layer")
        if set(gloss_divine) != set(literal_divine):
            flags.append("divine_name_rendering_differs_by_layer")
        elif gloss_divine or literal_divine:
            flags.append("divine_name_policy_review")
    if claim.get("reception_sensitive"):
        flags.append("reception_sensitive_pair")
    if claim.get("textual_witness_pressure"):
        flags.append("textual_witness_pressure_pair")
    if claim.get("ancient_culture_pressure"):
        flags.append("ancient_culture_pressure_pair")
    if claim.get("claim_risk_band") == "high":
        flags.append("high_claim_risk_pair")
    return sorted(set(flags))


def pair_risk_score(flags: list[str], similarity_pct: float, claim: dict[str, Any]) -> float:
    weights = {
        "schema_failure_blocks_layer_assessment": 60,
        "exact_gloss_literal_duplicate": 35,
        "near_gloss_literal_duplicate": 25,
        "weak_layer_differentiation": 20,
        "gloss_longer_than_literal": 8,
        "divine_name_missing_in_one_layer": 30,
        "divine_name_rendering_differs_by_layer": 20,
        "divine_name_policy_review": 6,
        "reception_sensitive_pair": 6,
        "textual_witness_pressure_pair": 6,
        "ancient_culture_pressure_pair": 5,
        "high_claim_risk_pair": 8,
    }
    score = sum(weights.get(flag, 0) for flag in flags)
    if similarity_pct >= 70:
        score += (similarity_pct - 70) * 0.35
    score += min(15.0, float(claim.get("claim_risk_score") or 0) / 18)
    return round(min(100.0, score), 2)


def pair_status(score: float, flags: list[str]) -> str:
    if "schema_failure_blocks_layer_assessment" in flags:
        return "structure_failure"
    if score >= 70:
        return "high_priority_layer_review"
    if score >= 45:
        return "moderate_layer_review"
    if flags:
        return "contextual_layer_review"
    return "low_layer_risk"


def build_pair_rows(
    *,
    suite: dict[str, Any],
    results: list[dict[str, Any]],
    audit: dict[str, Any],
    claim_matrix: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tasks = task_by_id(suite)
    scored = scored_by_pair(audit)
    claims = claim_by_unit(claim_matrix)
    groups, unpaired = layer_pair_groups(suite=suite, results=results)
    rows = []
    for (unit_id, model), layers in groups.items():
        if not {"gloss", "literal"} <= set(layers):
            continue
        gloss = layers["gloss"]
        literal = layers["literal"]
        gloss_task = tasks[str(gloss["task_id"])]
        literal_task = tasks[str(literal["task_id"])]
        claim = claims.get(unit_id, {})
        gloss_score = scored.get((str(gloss["task_id"]), model), {})
        literal_score = scored.get((str(literal["task_id"]), model), {})
        both_schema_valid = bool(gloss_score.get("schema_valid")) and bool(
            literal_score.get("schema_valid")
        )
        gloss_text = first_candidate_text(gloss)
        literal_text = first_candidate_text(literal)
        normalized_gloss = normalized_text(gloss_text)
        normalized_literal = normalized_text(literal_text)
        similarity = jaccard(word_set(gloss_text), word_set(literal_text))
        similarity_pct = round(similarity * 100, 2)
        source_divine = source_has_divine_name(gloss_task) or source_has_divine_name(literal_task)
        gloss_divine = divine_name_renderings(gloss_text)
        literal_divine = divine_name_renderings(literal_text)
        gloss_word_count = len(words(gloss_text))
        literal_word_count = len(words(literal_text))
        word_delta = literal_word_count - gloss_word_count
        flags = pair_flags(
            exact_duplicate=normalized_gloss == normalized_literal,
            similarity_pct=similarity_pct,
            word_delta=word_delta,
            gloss_word_count=gloss_word_count,
            literal_word_count=literal_word_count,
            source_divine_name=source_divine,
            gloss_divine=gloss_divine,
            literal_divine=literal_divine,
            claim=claim,
            both_schema_valid=both_schema_valid,
        )
        score = pair_risk_score(flags, similarity_pct, claim)
        rows.append(
            {
                "unit_id": unit_id,
                "ref": gloss_task.get("ref"),
                "model_profile_id": model,
                "both_schema_valid": both_schema_valid,
                "layer_status": pair_status(score, flags),
                "layer_risk_score": score,
                "gloss_task_id": gloss.get("task_id"),
                "literal_task_id": literal.get("task_id"),
                "gloss_text": gloss_text,
                "literal_text": literal_text,
                "gloss_word_count": gloss_word_count,
                "literal_word_count": literal_word_count,
                "literal_minus_gloss_words": word_delta,
                "word_jaccard_pct": similarity_pct,
                "exact_duplicate": normalized_gloss == normalized_literal,
                "source_has_divine_name": source_divine,
                "gloss_divine_renderings": gloss_divine,
                "literal_divine_renderings": literal_divine,
                "claim_risk_band": claim.get("claim_risk_band"),
                "claim_risk_score": claim.get("claim_risk_score"),
                "reception_sensitive": bool(claim.get("reception_sensitive")),
                "textual_witness_pressure": bool(claim.get("textual_witness_pressure")),
                "ancient_culture_pressure": bool(claim.get("ancient_culture_pressure")),
                "domains": claim.get("domains") or [],
                "required_frames": claim.get("required_frames") or [],
                "flags": flags,
            }
        )
    rows.sort(
        key=lambda row: (
            -float(row["layer_risk_score"]),
            row["ref"],
            row["model_profile_id"],
        )
    )
    return rows, unpaired


def summarize(rows: list[dict[str, Any]], unpaired: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: Counter[str] = Counter(str(row["layer_status"]) for row in rows)
    flag_counts: Counter[str] = Counter()
    for row in rows:
        flag_counts.update(str(flag) for flag in row.get("flags", []))
    valid_rows = [row for row in rows if row["both_schema_valid"]]
    return {
        "paired_unit_model_count": len(rows),
        "unpaired_unit_model_count": len(unpaired),
        "schema_valid_pair_count": len(valid_rows),
        "exact_duplicate_pair_count": sum(1 for row in rows if row["exact_duplicate"]),
        "near_duplicate_pair_count": sum(
            1 for row in rows if row["word_jaccard_pct"] >= 90 and not row["exact_duplicate"]
        ),
        "weak_layer_differentiation_pair_count": sum(
            1 for row in rows if "weak_layer_differentiation" in row["flags"]
        ),
        "divine_name_pair_count": sum(1 for row in rows if row["source_has_divine_name"]),
        "divine_name_inconsistent_pair_count": sum(
            1 for row in rows if "divine_name_rendering_differs_by_layer" in row["flags"]
        ),
        "mean_word_jaccard_pct": round(
            sum(float(row["word_jaccard_pct"]) for row in valid_rows) / len(valid_rows),
            2,
        )
        if valid_rows
        else 0.0,
        "mean_literal_minus_gloss_words": round(
            sum(float(row["literal_minus_gloss_words"]) for row in valid_rows) / len(valid_rows),
            2,
        )
        if valid_rows
        else 0.0,
        "mean_layer_risk_score": round(
            sum(float(row["layer_risk_score"]) for row in rows) / len(rows),
            2,
        )
        if rows
        else 0.0,
        "status_counts": dict(status_counts.most_common()),
        "flag_counts": dict(flag_counts.most_common()),
        "top_layer_risk_unit": rows[0]["unit_id"] if rows else None,
        "top_layer_risk_ref": rows[0]["ref"] if rows else None,
        "top_layer_risk_score": rows[0]["layer_risk_score"] if rows else 0.0,
    }


def model_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["model_profile_id"])].append(row)
    output = []
    for model, items in grouped.items():
        valid = [row for row in items if row["both_schema_valid"]]
        output.append(
            {
                "model_profile_id": model,
                "paired_unit_model_count": len(items),
                "schema_valid_pair_count": len(valid),
                "exact_duplicate_pair_count": sum(1 for row in items if row["exact_duplicate"]),
                "weak_layer_differentiation_pair_count": sum(
                    1 for row in items if "weak_layer_differentiation" in row["flags"]
                ),
                "divine_name_inconsistent_pair_count": sum(
                    1 for row in items if "divine_name_rendering_differs_by_layer" in row["flags"]
                ),
                "mean_word_jaccard_pct": round(
                    sum(float(row["word_jaccard_pct"]) for row in valid) / len(valid),
                    2,
                )
                if valid
                else 0.0,
                "mean_layer_risk_score": round(
                    sum(float(row["layer_risk_score"]) for row in items) / len(items),
                    2,
                ),
            }
        )
    output.sort(key=lambda row: (-row["mean_layer_risk_score"], row["model_profile_id"]))
    return output


def flag_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter.update(str(flag) for flag in row.get("flags", []))
    return [{"flag": flag, "pair_count": count} for flag, count in counter.most_common()]


def build_report(
    *,
    suite_path: Path,
    results_path: Path,
    audit_path: Path,
    claim_matrix_path: Path,
) -> dict[str, Any]:
    suite = load_json(suite_path)
    pair_rows, unpaired_rows = build_pair_rows(
        suite=suite,
        results=load_jsonl(results_path),
        audit=load_json(audit_path),
        claim_matrix=load_json(claim_matrix_path),
    )
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "layer consistency audit; heuristic review routing, not translation signoff",
        "source_paths": {
            "suite": rel(suite_path),
            "results": rel(results_path),
            "audit": rel(audit_path),
            "claim_matrix": rel(claim_matrix_path),
        },
        "method_notes": [
            "Only unit/model pairs with both gloss and literal rows are layer-compared.",
            "Similarity uses English word-set Jaccard overlap, not semantic equivalence.",
            "Divine-name flags inspect visible English renderings, not final policy approval.",
            "Scores prioritize human review; they are not accuracy scores.",
        ],
        "summary": summarize(pair_rows, unpaired_rows),
        "model_rows": model_rows(pair_rows),
        "flag_rows": flag_rows(pair_rows),
        "pair_rows": pair_rows,
        "unpaired_rows": unpaired_rows,
    }


def rows_from_counter(counter: dict[str, int], label_key: str) -> list[dict[str, Any]]:
    return [
        {label_key: key, "count": value}
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
    limit: int = 18,
) -> str:
    rows = rows[:limit]
    row_h = 29
    left = 340
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
    model_table = [
        [
            row["model_profile_id"],
            row["paired_unit_model_count"],
            row["schema_valid_pair_count"],
            row["exact_duplicate_pair_count"],
            row["weak_layer_differentiation_pair_count"],
            row["divine_name_inconsistent_pair_count"],
            f"{row['mean_word_jaccard_pct']:.2f}%",
            f"{row['mean_layer_risk_score']:.2f}",
        ]
        for row in report["model_rows"]
    ]
    pair_table = [
        [
            row["ref"],
            row["model_profile_id"],
            row["layer_status"],
            f"{row['layer_risk_score']:.2f}",
            f"{row['word_jaccard_pct']:.2f}%",
            row["literal_minus_gloss_words"],
            row["gloss_text"][:120],
            row["literal_text"][:120],
            ", ".join(row["flags"][:8]),
        ]
        for row in report["pair_rows"][:30]
    ]
    unpaired_table = [
        [
            row["unit_id"],
            row["model_profile_id"],
            ", ".join(row["available_layers"]),
            ", ".join(row["missing_layers"]),
        ]
        for row in report["unpaired_rows"][:30]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Layer Consistency Audit</title>
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
    .lede {{ max-width: 990px; font-size: 17px; color: #33414c; }}
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
    <h1>AlephTav Layer Consistency Audit</h1>
    <p class="lede">
      Paired gloss/literal review over real local model outputs. It checks
      whether the two layers are meaningfully differentiated, whether literal
      is shorter than gloss, and whether visible divine-name renderings remain
      consistent across paired layers. It is a routing audit, not signoff.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Summary</h2>
      {
        metric_cards(
            [
                (
                    "Paired unit/model rows",
                    fmt_int(summary["paired_unit_model_count"]),
                    "Rows with both gloss and literal outputs.",
                ),
                (
                    "Schema-valid pairs",
                    fmt_int(summary["schema_valid_pair_count"]),
                    "Pairs eligible for layer comparison.",
                ),
                (
                    "Weak differentiation",
                    fmt_int(summary["weak_layer_differentiation_pair_count"]),
                    "Pairs with high overlap and little length change.",
                ),
                (
                    "Mean word overlap",
                    f'''{summary["mean_word_jaccard_pct"]:.2f}%''',
                    "Word-set Jaccard across valid pairs.",
                ),
            ]
        )
    }
      <div class="warning">
        High overlap may be appropriate for some short units, but systematic
        duplication means the model is not using the layer contract.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["flag_counts"], "flag"),
            label_key="flag",
            value_key="count",
            aria_label="Layer consistency flag frequency",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            report["model_rows"],
            label_key="model_profile_id",
            value_key="mean_word_jaccard_pct",
            aria_label="Mean gloss literal word overlap by model",
            color="#2f6f73",
        )
    }</div>
    </section>

    <section>
      <h2>Model Summary</h2>
      {
        table(
            [
                "Model",
                "Pairs",
                "Valid pairs",
                "Exact dupes",
                "Weak diff",
                "Divine-name diff",
                "Mean overlap",
                "Mean risk",
            ],
            model_table,
        )
    }
    </section>

    <section>
      <h2>Top Layer Review Rows</h2>
      {
        table(
            [
                "Ref",
                "Model",
                "Status",
                "Risk",
                "Overlap",
                "Literal-gloss words",
                "Gloss text",
                "Literal text",
                "Flags",
            ],
            pair_table,
        )
    }
    </section>

    <section>
      <h2>Unpaired Rows</h2>
      {table(["Unit", "Model", "Available", "Missing"], unpaired_table)}
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate layer consistency report.")
    parser.add_argument("--suite", type=Path, default=SUITE_PATH)
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--audit", type=Path, default=AUDIT_PATH)
    parser.add_argument("--claim-matrix", type=Path, default=CLAIM_MATRIX_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--pair-csv-output", type=Path, default=DEFAULT_PAIR_CSV_OUTPUT)
    parser.add_argument("--model-csv-output", type=Path, default=DEFAULT_MODEL_CSV_OUTPUT)
    parser.add_argument("--flag-csv-output", type=Path, default=DEFAULT_FLAG_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        suite_path=args.suite,
        results_path=args.results,
        audit_path=args.audit,
        claim_matrix_path=args.claim_matrix,
    )
    write_json(args.json_output, report)
    write_csv(args.pair_csv_output, report["pair_rows"])
    write_csv(args.model_csv_output, report["model_rows"])
    write_csv(args.flag_csv_output, report["flag_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.pair_csv_output}")
    print(f"Wrote {args.model_csv_output}")
    print(f"Wrote {args.flag_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
