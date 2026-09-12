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

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "model_output_quality_triage.json"
DEFAULT_CANDIDATE_CSV_OUTPUT = REPORT_ROOT / "model_output_quality_triage_candidates.csv"
DEFAULT_MODEL_CSV_OUTPUT = REPORT_ROOT / "model_output_quality_triage_models.csv"
DEFAULT_FLAG_CSV_OUTPUT = REPORT_ROOT / "model_output_quality_triage_flags.csv"
DEFAULT_DOMAIN_CSV_OUTPUT = REPORT_ROOT / "model_output_quality_triage_domains.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "model_output_quality_triage.html"

WORD_RE = re.compile(r"[a-z][a-z'_-]*")
HEBREW_MARKS_RE = re.compile(r"[\u0591-\u05c7]")

STOPWORDS = {
    "a",
    "all",
    "am",
    "an",
    "and",
    "are",
    "as",
    "be",
    "but",
    "by",
    "for",
    "from",
    "he",
    "her",
    "his",
    "i",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "she",
    "that",
    "the",
    "their",
    "them",
    "they",
    "to",
    "we",
    "who",
    "will",
    "with",
    "you",
    "your",
}

RECEPTION_TERMS = {
    "apostle",
    "christ",
    "christian",
    "church",
    "jesus",
    "jewish",
    "judaism",
    "messiah",
    "messianic",
    "rabbinic",
}

WITNESS_TERMS = {
    "dead sea",
    "dss",
    "greek",
    "lxx",
    "septuagint",
    "syriac",
    "targum",
    "vulgate",
}

DIVINE_NAME_TERMS = {
    "god",
    "lord",
    "yah",
    "yahweh",
}

DIVINE_NAME_SURFACES = {"יהוה", "יה", "אדני", "אלהים", "אלוהים", "אל"}

TERM_SYNONYMS = {
    "earth": {"earth", "land"},
    "faithfulness": {"faithfulness", "faithful", "truth", "true"},
    "god": {"god", "gods"},
    "lord": {"lord", "yahweh"},
    "lovingkindness": {"love", "mercy", "kindness", "steadfast", "faithful"},
    "people": {"people", "peoples", "nation", "nations"},
    "righteousness": {"righteousness", "right", "justice", "justly"},
    "soul": {"soul", "life", "self", "throat"},
    "yahweh": {"yahweh", "lord"},
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


def fmt_pct(value: Any) -> str:
    return f"{float(value):.2f}%"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def words(text: str) -> list[str]:
    return [item.lower().strip("'_-") for item in WORD_RE.findall(text.lower())]


def stem(word: str) -> str:
    for suffix in ("ing", "edly", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def word_set(text: str) -> set[str]:
    output = set()
    for word in words(text):
        output.add(word)
        output.add(stem(word))
    return output


def source_terms(tokens: list[dict[str, Any]]) -> list[str]:
    terms: set[str] = set()
    for token in tokens:
        gloss = str(token.get("display_gloss") or "")
        for word in words(gloss):
            if word not in STOPWORDS and len(word) > 2:
                terms.add(stem(word))
    return sorted(terms)


def term_present(term: str, haystack: set[str]) -> bool:
    candidates = {term, stem(term)}
    candidates.update(TERM_SYNONYMS.get(term, set()))
    candidates.update(stem(item) for item in TERM_SYNONYMS.get(term, set()))
    return bool(candidates & haystack)


def strip_hebrew_marks(text: str) -> str:
    return HEBREW_MARKS_RE.sub("", text)


def has_divine_name(tokens: list[dict[str, Any]]) -> bool:
    for token in tokens:
        surface = strip_hebrew_marks(str(token.get("surface") or ""))
        lemma = strip_hebrew_marks(str(token.get("lemma") or ""))
        gloss = str(token.get("display_gloss") or "").lower()
        if surface in DIVINE_NAME_SURFACES or lemma in DIVINE_NAME_SURFACES:
            return True
        if "yhwh" in gloss or "yahweh" in gloss or "lord" in gloss:
            return True
    return False


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


def candidate_check(scored: dict[str, Any], index: int) -> dict[str, Any]:
    checks = scored.get("candidate_checks") or []
    if 0 <= index < len(checks) and isinstance(checks[index], dict):
        return checks[index]
    return {}


def text_review_flags(
    *,
    text: str,
    layer: str,
    source_token_count: int,
    source_keyword_count: int,
    missing_source_terms_pct: float,
    source_has_divine_name: bool,
    claim: dict[str, Any],
) -> list[str]:
    flags = []
    text_words = words(text)
    lowered = text.lower()
    if source_token_count and len(text_words) < max(2, source_token_count * 0.35):
        flags.append("translation_suspiciously_short")
    if source_token_count and len(text_words) > max(24, source_token_count * 3.2):
        flags.append("translation_suspiciously_long")
    if layer == "gloss" and source_token_count and len(text_words) > source_token_count * 2.5:
        flags.append("gloss_layer_too_sentence_like")
    if source_keyword_count >= 3 and missing_source_terms_pct >= 45:
        flags.append("high_source_gloss_keyword_gap")
    if source_has_divine_name and not (word_set(text) & DIVINE_NAME_TERMS):
        flags.append("divine_name_not_visible_in_translation")
    if source_has_divine_name and ("lord" in word_set(text) or "god" in word_set(text)):
        flags.append("divine_name_policy_review")
    if any(term in lowered for term in RECEPTION_TERMS):
        flags.append("reception_language_in_translation_text")
    if any(term in lowered for term in WITNESS_TERMS):
        flags.append("witness_language_in_translation_text")
    if claim.get("reception_sensitive"):
        flags.append("reception_sensitive_unit_requires_human_boundary_review")
    if claim.get("textual_witness_pressure"):
        flags.append("textual_witness_pressure_requires_human_review")
    if claim.get("ancient_culture_pressure"):
        flags.append("ancient_culture_pressure_requires_human_review")
    if claim.get("claim_risk_band") == "high":
        flags.append("high_claim_risk_unit")
    return sorted(set(flags))


def review_priority_score(
    *,
    schema_valid: bool,
    missing_source_terms_pct: float,
    flags: list[str],
    alignment_score: float,
    basis_score: float,
    claim: dict[str, Any],
    source_anchor_issue_count: int,
) -> float:
    if not schema_valid:
        return 100.0
    score = missing_source_terms_pct * 0.45
    score += max(0.0, 5.0 - alignment_score) * 8
    score += max(0.0, 5.0 - basis_score) * 8
    score += min(25.0, float(claim.get("claim_risk_score") or 0) / 10)
    if source_anchor_issue_count:
        score += 50
    flag_weights = {
        "translation_suspiciously_short": 12,
        "translation_suspiciously_long": 10,
        "gloss_layer_too_sentence_like": 6,
        "high_source_gloss_keyword_gap": 18,
        "divine_name_not_visible_in_translation": 25,
        "divine_name_policy_review": 6,
        "reception_language_in_translation_text": 35,
        "witness_language_in_translation_text": 35,
        "reception_sensitive_unit_requires_human_boundary_review": 8,
        "textual_witness_pressure_requires_human_review": 8,
        "ancient_culture_pressure_requires_human_review": 6,
        "high_claim_risk_unit": 8,
    }
    score += sum(flag_weights.get(flag, 0) for flag in flags)
    return round(min(score, 100.0), 2)


def quality_status(*, schema_valid: bool, score: float, flags: list[str]) -> str:
    if not schema_valid:
        return "structure_failure_not_quality_triaged"
    if score >= 70:
        return "high_priority_human_review"
    if score >= 45:
        return "moderate_priority_human_review"
    if flags:
        return "contextual_review_required"
    return "low_automated_triage_risk"


def build_candidate_rows(
    *,
    suite: dict[str, Any],
    results: list[dict[str, Any]],
    audit: dict[str, Any],
    claim_matrix: dict[str, Any],
) -> list[dict[str, Any]]:
    tasks = task_by_id(suite)
    scored_rows = scored_by_pair(audit)
    claims = claim_by_unit(claim_matrix)
    rows = []
    for result in results:
        task_id = str(result.get("task_id") or "")
        model = str(result.get("model_profile_id") or "")
        task = tasks.get(task_id, {})
        unit_id = str(task.get("unit_id") or (result.get("output") or {}).get("unit_id") or "")
        claim = claims.get(unit_id, {})
        scored = scored_rows.get((task_id, model), {})
        schema_valid = bool(scored.get("schema_valid"))
        output = result.get("output") if isinstance(result.get("output"), dict) else {}
        candidates = output.get("candidates") if isinstance(output.get("candidates"), list) else []
        if not candidates:
            rows.append(
                build_single_candidate_row(
                    result=result,
                    task=task,
                    claim=claim,
                    scored=scored,
                    candidate={},
                    candidate_index=0,
                    schema_valid=False,
                    structure_error=str(result.get("error") or "; ".join(scored.get("errors", []))),
                )
            )
            continue
        for index, candidate in enumerate(candidates, start=1):
            rows.append(
                build_single_candidate_row(
                    result=result,
                    task=task,
                    claim=claim,
                    scored=scored,
                    candidate=candidate if isinstance(candidate, dict) else {},
                    candidate_index=index,
                    schema_valid=schema_valid,
                    structure_error="",
                )
            )
    rows.sort(
        key=lambda row: (
            -float(row["review_priority_score"]),
            row["ref"],
            row["model_profile_id"],
            row["layer"],
        )
    )
    return rows


def build_single_candidate_row(
    *,
    result: dict[str, Any],
    task: dict[str, Any],
    claim: dict[str, Any],
    scored: dict[str, Any],
    candidate: dict[str, Any],
    candidate_index: int,
    schema_valid: bool,
    structure_error: str,
) -> dict[str, Any]:
    source = (task.get("generation_input") or {}).get("locked_inputs", {}).get("source", {})
    tokens = source.get("tokens") if isinstance(source.get("tokens"), list) else []
    expected_terms = source_terms(tokens)
    raw_preview = " ".join(str(result.get("raw_text") or "").split())[:260]
    text = str(candidate.get("text") or "") if schema_valid else raw_preview
    text_terms = word_set(text)
    missing_terms = (
        [term for term in expected_terms if not term_present(term, text_terms)]
        if schema_valid
        else []
    )
    missing_terms_pct = pct(len(missing_terms), len(expected_terms)) if schema_valid else 0.0
    check = candidate_check(scored, candidate_index - 1)
    alignment_score = float(check.get("alignment_score_0_5") or 0)
    basis_score = float(check.get("translation_basis_score_0_5") or 0)
    source_anchor_issue_count = int(scored.get("source_anchor_issue_count") or 0)
    source_has_divine_name = has_divine_name(tokens)
    if schema_valid:
        flags = text_review_flags(
            text=text,
            layer=str(task.get("layer") or ""),
            source_token_count=len(tokens),
            source_keyword_count=len(expected_terms),
            missing_source_terms_pct=missing_terms_pct,
            source_has_divine_name=source_has_divine_name,
            claim=claim,
        )
    else:
        flags = ["structure_failure_blocks_quality_triage"]
        if claim.get("claim_risk_band") == "high":
            flags.append("structure_failure_on_high_claim_unit")
    if source_anchor_issue_count:
        flags.append("source_anchor_issue")
    if schema_valid and alignment_score < 5:
        flags.append("alignment_below_full_coverage")
    if schema_valid and basis_score < 5:
        flags.append("translation_basis_below_full_score")
    score = review_priority_score(
        schema_valid=schema_valid,
        missing_source_terms_pct=missing_terms_pct,
        flags=flags,
        alignment_score=alignment_score,
        basis_score=basis_score,
        claim=claim,
        source_anchor_issue_count=source_anchor_issue_count,
    )
    return {
        "task_id": result.get("task_id"),
        "unit_id": task.get("unit_id") or (result.get("output") or {}).get("unit_id"),
        "ref": task.get("ref"),
        "layer": task.get("layer"),
        "model_profile_id": result.get("model_profile_id"),
        "runtime_model": (result.get("runtime") or {}).get("model"),
        "line_number": result.get("_line_number"),
        "candidate_index": candidate_index,
        "schema_valid": schema_valid,
        "quality_status": quality_status(schema_valid=schema_valid, score=score, flags=flags),
        "review_priority_score": score,
        "candidate_text": text,
        "candidate_word_count": len(words(text)) if schema_valid else 0,
        "source_token_count": len(tokens),
        "source_keyword_count": len(expected_terms),
        "missing_source_keyword_count": len(missing_terms),
        "missing_source_keyword_pct": missing_terms_pct,
        "missing_source_keywords": missing_terms[:18],
        "alignment_score_0_5": alignment_score,
        "translation_basis_score_0_5": basis_score,
        "source_anchor_issue_count": source_anchor_issue_count,
        "source_has_divine_name": source_has_divine_name,
        "claim_risk_band": claim.get("claim_risk_band"),
        "claim_risk_score": claim.get("claim_risk_score"),
        "reception_sensitive": bool(claim.get("reception_sensitive")),
        "textual_witness_pressure": bool(claim.get("textual_witness_pressure")),
        "ancient_culture_pressure": bool(claim.get("ancient_culture_pressure")),
        "domains": claim.get("domains") or [],
        "required_frames": claim.get("required_frames") or [],
        "flags": sorted(set(flags)),
        "structure_error": structure_error,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid_rows = [row for row in rows if row["schema_valid"]]
    high_priority = [row for row in rows if row["quality_status"] == "high_priority_human_review"]
    structure_failures = [row for row in rows if not row["schema_valid"]]
    flag_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    for row in rows:
        status_counts[str(row["quality_status"])] += 1
        flag_counts.update(str(flag) for flag in row.get("flags", []))
    return {
        "candidate_row_count": len(rows),
        "schema_valid_candidate_count": len(valid_rows),
        "structure_failure_count": len(structure_failures),
        "high_priority_human_review_count": len(high_priority),
        "contextual_review_required_count": sum(1 for row in valid_rows if row.get("flags")),
        "mean_review_priority_score": round(
            sum(float(row["review_priority_score"]) for row in rows) / len(rows),
            2,
        )
        if rows
        else 0.0,
        "mean_valid_missing_source_keyword_pct": round(
            sum(float(row["missing_source_keyword_pct"]) for row in valid_rows) / len(valid_rows),
            2,
        )
        if valid_rows
        else 0.0,
        "status_counts": dict(status_counts.most_common()),
        "flag_counts": dict(flag_counts.most_common()),
        "top_review_priority_task": rows[0]["task_id"] if rows else None,
        "top_review_priority_ref": rows[0]["ref"] if rows else None,
        "top_review_priority_score": rows[0]["review_priority_score"] if rows else 0.0,
    }


def model_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["model_profile_id"])].append(row)
    output = []
    for model, items in grouped.items():
        valid = [row for row in items if row["schema_valid"]]
        output.append(
            {
                "model_profile_id": model,
                "candidate_rows": len(items),
                "schema_valid_candidate_rows": len(valid),
                "schema_valid_pct": pct(len(valid), len(items)),
                "structure_failure_rows": sum(1 for row in items if not row["schema_valid"]),
                "high_priority_human_review_rows": sum(
                    1 for row in items if row["quality_status"] == "high_priority_human_review"
                ),
                "contextual_review_required_rows": sum(1 for row in valid if row.get("flags")),
                "mean_review_priority_score": round(
                    sum(float(row["review_priority_score"]) for row in items) / len(items),
                    2,
                ),
                "mean_missing_source_keyword_pct": round(
                    sum(float(row["missing_source_keyword_pct"]) for row in valid) / len(valid),
                    2,
                )
                if valid
                else 0.0,
                "source_anchor_issue_count": sum(
                    int(row["source_anchor_issue_count"]) for row in items
                ),
            }
        )
    output.sort(key=lambda row: (-row["mean_review_priority_score"], row["model_profile_id"]))
    return output


def flag_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    high_counter: Counter[str] = Counter()
    for row in rows:
        counter.update(str(flag) for flag in row.get("flags", []))
        if row["quality_status"] == "high_priority_human_review":
            high_counter.update(str(flag) for flag in row.get("flags", []))
    return [
        {
            "flag": flag,
            "candidate_rows": count,
            "high_priority_rows": high_counter[flag],
        }
        for flag, count in counter.most_common()
    ]


def domain_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        domains = row.get("domains") or ["unclassified"]
        for domain in domains:
            grouped[str(domain)].append(row)
    output = []
    for domain, items in grouped.items():
        output.append(
            {
                "domain": domain,
                "candidate_rows": len(items),
                "high_priority_rows": sum(
                    1 for row in items if row["quality_status"] == "high_priority_human_review"
                ),
                "mean_review_priority_score": round(
                    sum(float(row["review_priority_score"]) for row in items) / len(items),
                    2,
                ),
                "structure_failure_rows": sum(1 for row in items if not row["schema_valid"]),
            }
        )
    output.sort(key=lambda row: (-row["mean_review_priority_score"], row["domain"]))
    return output


def build_report(
    *,
    suite_path: Path,
    results_path: Path,
    audit_path: Path,
    claim_matrix_path: Path,
) -> dict[str, Any]:
    suite = load_json(suite_path)
    audit = load_json(audit_path)
    claim_matrix = load_json(claim_matrix_path)
    rows = build_candidate_rows(
        suite=suite,
        results=load_jsonl(results_path),
        audit=audit,
        claim_matrix=claim_matrix,
    )
    models = model_rows(rows)
    flags = flag_rows(rows)
    domains = domain_rows(rows)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "automated quality triage; heuristic review routing, not human signoff",
        "source_paths": {
            "suite": str(suite_path.relative_to(ROOT)),
            "results": str(results_path.relative_to(ROOT)),
            "audit": str(audit_path.relative_to(ROOT)),
            "claim_matrix": str(claim_matrix_path.relative_to(ROOT)),
        },
        "method_notes": [
            "Schema-invalid rows are counted as structure failures, not translation candidates.",
            (
                "Source keyword checks use generated display_gloss terms and "
                "simple English token matching."
            ),
            "Context flags come from the translation claim evidence matrix.",
            "Scores prioritize human review; they are not accuracy scores.",
        ],
        "summary": summarize(rows),
        "model_rows": models,
        "flag_rows": flags,
        "domain_rows": domains,
        "candidate_rows": rows,
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
    left = 350
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
            row["candidate_rows"],
            row["schema_valid_candidate_rows"],
            f"{row['schema_valid_pct']:.2f}%",
            row["structure_failure_rows"],
            row["high_priority_human_review_rows"],
            f"{row['mean_review_priority_score']:.2f}",
            f"{row['mean_missing_source_keyword_pct']:.2f}%",
        ]
        for row in report["model_rows"]
    ]
    candidate_table = [
        [
            row["ref"],
            row["layer"],
            row["model_profile_id"],
            row["quality_status"],
            f"{row['review_priority_score']:.2f}",
            row["candidate_text"][:180],
            ", ".join(row["flags"][:8]),
            ", ".join(row["missing_source_keywords"][:8]),
        ]
        for row in report["candidate_rows"][:30]
    ]
    domain_table = [
        [
            row["domain"],
            row["candidate_rows"],
            row["high_priority_rows"],
            f"{row['mean_review_priority_score']:.2f}",
            row["structure_failure_rows"],
        ]
        for row in report["domain_rows"][:20]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Model Output Quality Triage</title>
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
    <h1>AlephTav Model Output Quality Triage</h1>
    <p class="lede">
      Automated review-routing for real local model outputs. It combines schema
      status, source-token gloss coverage, divine-name visibility, source-anchor
      checks, and contextual claim pressure. It is a triage instrument, not a
      human Hebrew translation verdict.
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
                    "Candidate rows",
                    fmt_int(summary["candidate_row_count"]),
                    "Submitted candidates and structure failures.",
                ),
                (
                    "Schema-valid candidates",
                    fmt_int(summary["schema_valid_candidate_count"]),
                    "Rows eligible for automated quality triage.",
                ),
                (
                    "High-priority review",
                    fmt_int(summary["high_priority_human_review_count"]),
                    "Rows whose heuristic risk demands early human review.",
                ),
                (
                    "Mean priority",
                    f'''{summary["mean_review_priority_score"]:.2f}''',
                    "Heuristic review priority, not an accuracy score.",
                ),
            ]
        )
    }
      <div class="warning">
        This report deliberately refuses publication-quality conclusions. It
        surfaces rows and domains that need qualified human review.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["flag_counts"], "flag"),
            label_key="flag",
            value_key="count",
            aria_label="Quality triage flag frequency",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            report["model_rows"],
            label_key="model_profile_id",
            value_key="mean_review_priority_score",
            aria_label="Mean review priority by model",
            color="#2f6f73",
        )
    }</div>
    </section>

    <section>
      <h2>Model Triage</h2>
      {
        table(
            [
                "Model",
                "Rows",
                "Schema-valid",
                "Valid %",
                "Structure failures",
                "High-priority",
                "Mean priority",
                "Mean missing keywords",
            ],
            model_table,
        )
    }
    </section>

    <section>
      <h2>Domain Pressure</h2>
      {
        table(
            ["Domain", "Rows", "High-priority", "Mean priority", "Structure failures"],
            domain_table,
        )
    }
    </section>

    <section>
      <h2>Top Review Rows</h2>
      {
        table(
            [
                "Ref",
                "Layer",
                "Model",
                "Status",
                "Priority",
                "Candidate text",
                "Flags",
                "Missing source keywords",
            ],
            candidate_table,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate model output quality triage report.")
    parser.add_argument("--suite", type=Path, default=SUITE_PATH)
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--audit", type=Path, default=AUDIT_PATH)
    parser.add_argument("--claim-matrix", type=Path, default=CLAIM_MATRIX_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--candidate-csv-output", type=Path, default=DEFAULT_CANDIDATE_CSV_OUTPUT)
    parser.add_argument("--model-csv-output", type=Path, default=DEFAULT_MODEL_CSV_OUTPUT)
    parser.add_argument("--flag-csv-output", type=Path, default=DEFAULT_FLAG_CSV_OUTPUT)
    parser.add_argument("--domain-csv-output", type=Path, default=DEFAULT_DOMAIN_CSV_OUTPUT)
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
    write_csv(args.candidate_csv_output, report["candidate_rows"])
    write_csv(args.model_csv_output, report["model_rows"])
    write_csv(args.flag_csv_output, report["flag_rows"])
    write_csv(args.domain_csv_output, report["domain_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.candidate_csv_output}")
    print(f"Wrote {args.model_csv_output}")
    print(f"Wrote {args.flag_csv_output}")
    print(f"Wrote {args.domain_csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
