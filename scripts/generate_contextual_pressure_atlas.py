from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"
MATRIX_PATH = REPORT_ROOT / "benchmark_context_reception_matrix.json"
RUBRIC_PATH = ROOT / "docs" / "research" / "psalms_contextual_evaluation_rubric.json"
DEFAULT_JSON_OUTPUT = REPORT_ROOT / "contextual_pressure_atlas.json"
DEFAULT_CSV_OUTPUT = REPORT_ROOT / "contextual_pressure_priority_units.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "contextual_pressure_atlas.html"

DOMAIN_GROUPS = {
    "royal_kingship": "ancient_culture",
    "temple_cult_liturgy": "ancient_culture",
    "wisdom_torah": "ancient_culture",
    "lament_enemy_justice": "ancient_culture",
    "covenant_mercy": "ancient_culture",
    "creation_cosmos": "ancient_culture",
    "anthropology_body": "ancient_culture",
    "nations_zion_exile": "ancient_culture",
    "divine_names_titles": "source_theology_control",
    "textual_witness_pressure": "textual_provenance",
    "jewish_christian_reception": "reception_boundary",
}

GROUP_LABELS = {
    "ancient_culture": "Ancient culture and canonical setting",
    "source_theology_control": "Source-theology control",
    "textual_provenance": "Textual witness and provenance",
    "reception_boundary": "Jewish/Christian reception boundary",
}

SOURCE_CONTROL_QUESTIONS = {
    "source_hebrew_plain_sense": (
        "What can be justified from the Hebrew unit and token evidence before "
        "later reception claims are introduced?"
    ),
    "ancient_royal_ideology": (
        "Does royal language belong to court, Davidic, or wider ancient Near "
        "Eastern kingship idiom before later messianic framing?"
    ),
    "creation_anthropology": (
        "Does the translation preserve human vocation and creaturely limits "
        "without importing a later doctrinal anthropology?"
    ),
    "mortality_language": (
        "Does death, Sheol, pit, or corruption language stay within the Hebrew "
        "image system unless a reception note is explicitly marked?"
    ),
    "lament_genre": (
        "Does the rendering preserve complaint, enemy rhetoric, and appeal for "
        "justice without smoothing the ethical discomfort?"
    ),
    "davidic_covenant": (
        "Does covenantal royal language stay distinguishable from later Jewish "
        "and Christian messianic interpretation?"
    ),
    "temple_liturgy": (
        "Does the rendering preserve procession, sanctuary, sacrifice, or praise "
        "setting before devotional afterlife is applied?"
    ),
    "jewish_reception": (
        "Which Jewish interpretive frame is being reported, and is it clearly "
        "separated from the source translation?"
    ),
    "christian_reception": (
        "Which Christian interpretive frame is being reported, and is it clearly "
        "separated from the source translation?"
    ),
    "academic_critical_comparison": (
        "What does the comparison say about the gap between source reading, "
        "historical setting, and later reception?"
    ),
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


def join_values(values: list[Any] | tuple[Any, ...] | set[Any]) -> str:
    return "; ".join(str(value) for value in values)


def domain_label(matrix: dict[str, Any], domain: str) -> str:
    for row in matrix.get("unit_rows", []):
        data = row.get("context_domains", {}).get(domain)
        if data:
            return str(data.get("label") or domain)
    return domain.replace("_", " ").title()


def unit_domain_groups(row: dict[str, Any]) -> set[str]:
    domains = row.get("context_domains", {})
    return {DOMAIN_GROUPS.get(domain, "other") for domain in domains}


def outside_division_count(row: dict[str, Any]) -> int:
    divisions = row.get("context_coverage", {}).get("outside_context_division_counts", {})
    return sum(1 for value in divisions.values() if int(value) > 0)


def priority_score(row: dict[str, Any]) -> float:
    score = float(row.get("context_pressure_score") or 0.0)
    score += 1.2 * int(row.get("domain_count") or 0)
    if row.get("context_pressure_intensity") == "high":
        score += 4.0
    if row.get("reception_profile", {}).get("sensitive"):
        score += 5.0
    if "textual_witness_pressure" in row.get("context_domains", {}):
        score += 3.0
    if outside_division_count(row) >= 5:
        score += 2.0
    return round(score, 2)


def top_context_tokens(row: dict[str, Any], limit: int = 3) -> list[str]:
    tokens = row.get("context_coverage", {}).get("high_context_tokens", [])
    values = []
    for token in tokens[:limit]:
        values.append(
            f"{token.get('token_id')} {token.get('surface_query')} "
            f"outside={token.get('outside_psalms_count')}"
        )
    return values


def build_domain_rows(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    rows = matrix["unit_rows"]
    domain_rows = []
    domains = sorted({domain for row in rows for domain in row.get("context_domains", {})})
    for domain in domains:
        matching = [row for row in rows if domain in row.get("context_domains", {})]
        division_counts: Counter[str] = Counter()
        review_roles: Counter[str] = Counter()
        model_controls: Counter[str] = Counter()
        evidence: Counter[str] = Counter()
        for row in matching:
            coverage = row.get("context_coverage", {})
            division_counts.update(coverage.get("outside_context_division_counts", {}))
            review_roles.update(row.get("review_roles", []))
            model_controls.update(row.get("model_controls", []))
            for item in row.get("context_domains", {}).get(domain, {}).get("evidence", []):
                evidence[str(item).split(":", 2)[0]] += 1
        outside_total = sum(int(value) for value in division_counts.values())
        top_division = division_counts.most_common(1)[0][0] if division_counts else ""
        domain_rows.append(
            {
                "domain": domain,
                "label": domain_label(matrix, domain),
                "group": DOMAIN_GROUPS.get(domain, "other"),
                "group_label": GROUP_LABELS.get(DOMAIN_GROUPS.get(domain, ""), "Other"),
                "unit_count": len(matching),
                "unit_pct": pct(len(matching), len(rows)),
                "token_count": sum(int(row.get("token_count") or 0) for row in matching),
                "high_pressure_units": sum(
                    1 for row in matching if row["context_pressure_intensity"] == "high"
                ),
                "reception_sensitive_units": sum(
                    1 for row in matching if row["reception_profile"]["sensitive"]
                ),
                "textual_witness_units": sum(
                    1
                    for row in matching
                    if "textual_witness_pressure" in row.get("context_domains", {})
                ),
                "outside_occurrence_total": outside_total,
                "top_outside_division": top_division,
                "outside_division_counts": dict(division_counts.most_common()),
                "review_role_counts": dict(review_roles.most_common()),
                "top_model_controls": [item for item, _count in model_controls.most_common(5)],
                "top_evidence_prefixes": [item for item, _count in evidence.most_common(6)],
            }
        )
    return sorted(domain_rows, key=lambda row: (-row["unit_count"], row["domain"]))


def build_unit_group_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    group_to_units: dict[str, set[str]] = defaultdict(set)
    group_to_tokens: Counter[str] = Counter()
    for row in rows:
        for group in unit_domain_groups(row):
            group_to_units[group].add(row["unit_id"])
            group_to_tokens[group] += int(row.get("token_count") or 0)
    return [
        {
            "group": group,
            "label": GROUP_LABELS.get(group, "Other"),
            "unit_count": len(units),
            "unit_pct": pct(len(units), len(rows)),
            "token_count": group_to_tokens[group],
        }
        for group, units in sorted(group_to_units.items())
    ]


def build_cooccurrence_rows(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    pair_counts: Counter[tuple[str, str]] = Counter()
    high_counts: Counter[tuple[str, str]] = Counter()
    reception_counts: Counter[tuple[str, str]] = Counter()
    for row in matrix["unit_rows"]:
        domains = sorted(row.get("context_domains", {}))
        for index, first in enumerate(domains):
            for second in domains[index + 1 :]:
                pair = (first, second)
                pair_counts[pair] += 1
                if row["context_pressure_intensity"] == "high":
                    high_counts[pair] += 1
                if row["reception_profile"]["sensitive"]:
                    reception_counts[pair] += 1
    rows = []
    for (first, second), count in pair_counts.most_common():
        rows.append(
            {
                "first_domain": first,
                "second_domain": second,
                "first_label": domain_label(matrix, first),
                "second_label": domain_label(matrix, second),
                "unit_count": count,
                "high_pressure_units": high_counts[(first, second)],
                "reception_sensitive_units": reception_counts[(first, second)],
            }
        )
    return rows


def build_frame_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame_counts: Counter[str] = Counter()
    sensitive_counts: Counter[str] = Counter()
    for row in rows:
        frames = row.get("reception_profile", {}).get("required_frames", [])
        frame_counts.update(frames)
        if row.get("reception_profile", {}).get("sensitive"):
            sensitive_counts.update(frames)
    return [
        {
            "frame": frame,
            "unit_count": count,
            "sensitive_unit_count": sensitive_counts[frame],
            "control_question": SOURCE_CONTROL_QUESTIONS.get(
                frame,
                "What source-bounded claim must reviewers verify for this frame?",
            ),
        }
        for frame, count in frame_counts.most_common()
    ]


def build_priority_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority_rows = []
    for row in rows:
        domains = sorted(row.get("context_domains", {}))
        coverage = row.get("context_coverage", {})
        priority_rows.append(
            {
                "unit_id": row["unit_id"],
                "ref": row["ref"],
                "psalm_id": row["psalm_id"],
                "primary_stratum": row["primary_stratum"],
                "token_count": row["token_count"],
                "context_pressure_score": row["context_pressure_score"],
                "context_pressure_intensity": row["context_pressure_intensity"],
                "priority_score": priority_score(row),
                "domain_count": row["domain_count"],
                "domains": domains,
                "domain_groups": sorted(unit_domain_groups(row)),
                "reception_sensitive": row["reception_profile"]["sensitive"],
                "reception_label": row["reception_profile"]["label"],
                "required_frames": row["reception_profile"]["required_frames"],
                "review_roles": row["review_roles"],
                "model_controls": row["model_controls"],
                "surface_outside_context_pct": coverage["surface_outside_context_pct"],
                "outside_division_count": outside_division_count(row),
                "outside_context_division_counts": coverage["outside_context_division_counts"],
                "top_context_tokens": top_context_tokens(row),
                "witness_count": row.get("witness_summary", {}).get("count", 0),
                "greek_coverage_pct": row.get("plan_greek_coverage_pct"),
                "source_hebrew": row.get("source_hebrew"),
            }
        )
    return sorted(
        priority_rows,
        key=lambda item: (-item["priority_score"], item["unit_id"]),
    )


def build_axis_rows(
    *,
    matrix: dict[str, Any],
    rows: list[dict[str, Any]],
    priority_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ancient_units = [row for row in rows if "ancient_culture" in unit_domain_groups(row)]
    textual_units = [
        row for row in rows if "textual_witness_pressure" in row.get("context_domains", {})
    ]
    reception_units = [row for row in rows if row.get("reception_profile", {}).get("sensitive")]
    broad_units = [row for row in rows if outside_division_count(row) >= 5]
    high_priority_units = [row for row in priority_rows if row["priority_score"] >= 22.0]
    return [
        {
            "axis": "Hebrew source control",
            "unit_count": len(rows),
            "evidence": (
                f"{matrix['summary']['token_count']} token records across "
                f"{len(rows)} selected benchmark units."
            ),
            "review_question": SOURCE_CONTROL_QUESTIONS["source_hebrew_plain_sense"],
        },
        {
            "axis": "Whole-Tanakh canonical context",
            "unit_count": len(broad_units),
            "evidence": (
                f"{len(broad_units)} units have outside-Psalms form context "
                "in all five Tanakh divisions tracked by the report."
            ),
            "review_question": (
                "Which outside-Psalms forms are relevant context, and which are "
                "only high-frequency noise?"
            ),
        },
        {
            "axis": "Ancient culture and setting",
            "unit_count": len(ancient_units),
            "evidence": (
                "Units hit at least one royal, temple, wisdom, lament, covenant, "
                "creation, anthropology, nations, Zion, or exile domain."
            ),
            "review_question": (
                "What historically plausible setting is needed to prevent a "
                "flat modern English rendering?"
            ),
        },
        {
            "axis": "Textual witness and provenance",
            "unit_count": len(textual_units),
            "evidence": (
                f"{len(textual_units)} units are tagged for witness or license "
                "pressure, often due to Greek coverage or familiar Psalm status."
            ),
            "review_question": (
                "Which evidence is Hebrew source text, which is witness data, "
                "and which is only reception or familiar English phrasing?"
            ),
        },
        {
            "axis": "Jewish/Christian reception boundary",
            "unit_count": len(reception_units),
            "evidence": (
                f"{len(reception_units)} units require separate Jewish, "
                "Christian, and academic-comparison frames."
            ),
            "review_question": (
                "Can the translation stand as source-bounded English before "
                "Jewish and Christian interpretation notes are compared?"
            ),
        },
        {
            "axis": "Priority review stack",
            "unit_count": len(high_priority_units),
            "evidence": (
                f"{len(high_priority_units)} units score at least 22.0 on the "
                "atlas priority heuristic."
            ),
            "review_question": (
                "Which units should receive human review before more local "
                "model calls are trusted as benchmark evidence?"
            ),
        },
    ]


def build_report(matrix_path: Path, rubric_path: Path) -> dict[str, Any]:
    matrix = load_json(matrix_path)
    rubric = load_json(rubric_path)
    rows = matrix["unit_rows"]
    domain_rows = build_domain_rows(matrix)
    unit_group_rows = build_unit_group_rows(rows)
    cooccurrence_rows = build_cooccurrence_rows(matrix)
    frame_rows = build_frame_rows(rows)
    priority_rows = build_priority_rows(rows)
    axis_rows = build_axis_rows(
        matrix=matrix,
        rows=rows,
        priority_rows=priority_rows,
    )
    summary = matrix["summary"]
    high_priority_count = sum(1 for row in priority_rows if row["priority_score"] >= 22.0)
    broad_context_count = sum(1 for row in rows if outside_division_count(row) >= 5)
    ancient_context_count = sum(1 for row in rows if "ancient_culture" in unit_domain_groups(row))
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": (
            "generated contextual pressure atlas from benchmark matrix; "
            "heuristic routing, not final interpretation"
        ),
        "source_paths": {
            "context_reception_matrix": str(matrix_path.relative_to(ROOT)),
            "contextual_rubric": str(rubric_path.relative_to(ROOT)),
        },
        "selection_method": {
            "principles": [
                "Keep Hebrew translation, historical setting, and reception separate.",
                "Use only existing project evidence and read-only upstream counts.",
                "Treat domain hits as review-routing evidence, not conclusions.",
                "Prioritize units where multiple interpretive pressures overlap.",
            ],
            "limitations": [
                "Whole-Tanakh evidence is normalized surface-form evidence.",
                "Ancient culture domains are lexical and Psalm-class proxies.",
                "Jewish and Christian reception frames are routing categories.",
                "No proprietary commentary or lexicon text is ingested.",
            ],
            "rubric_context_layer_count": len(rubric.get("context_layers", [])),
            "rubric_case_study_count": len(rubric.get("case_studies", [])),
        },
        "summary": {
            "unit_count": summary["unit_count"],
            "token_count": summary["token_count"],
            "domain_count": len(domain_rows),
            "domain_group_count": len(unit_group_rows),
            "ancient_context_unit_count": ancient_context_count,
            "broad_canonical_context_unit_count": broad_context_count,
            "high_pressure_unit_count": summary["high_pressure_units"],
            "reception_sensitive_unit_count": summary["reception_sensitive_units"],
            "textual_witness_pressure_unit_count": summary["textual_witness_pressure_units"],
            "high_priority_review_unit_count": high_priority_count,
            "surface_outside_context_pct": summary["surface_outside_context_pct"],
            "surface_form_match_pct": summary["surface_form_match_pct"],
            "outside_context_division_counts": summary["outside_context_division_counts"],
            "top_priority_unit": priority_rows[0]["unit_id"] if priority_rows else None,
            "top_priority_score": priority_rows[0]["priority_score"] if priority_rows else 0,
        },
        "axis_rows": axis_rows,
        "domain_rows": domain_rows,
        "domain_group_rows": unit_group_rows,
        "frame_rows": frame_rows,
        "cooccurrence_rows": cooccurrence_rows,
        "priority_unit_rows": priority_rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "unit_id",
        "ref",
        "psalm_id",
        "primary_stratum",
        "context_pressure_score",
        "context_pressure_intensity",
        "priority_score",
        "domain_count",
        "domains",
        "domain_groups",
        "reception_sensitive",
        "reception_label",
        "required_frames",
        "review_roles",
        "surface_outside_context_pct",
        "outside_division_count",
        "witness_count",
        "greek_coverage_pct",
        "top_context_tokens",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{key: row.get(key) for key in fieldnames},
                    "domains": join_values(row["domains"]),
                    "domain_groups": join_values(row["domain_groups"]),
                    "required_frames": join_values(row["required_frames"]),
                    "review_roles": join_values(row["review_roles"]),
                    "top_context_tokens": join_values(row["top_context_tokens"]),
                }
            )


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
    left = 310
    right = 58
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


def svg_cooccurrence_heatmap(rows: list[dict[str, Any]]) -> str:
    domains = []
    for row in rows:
        for key in ["first_domain", "second_domain"]:
            if row[key] not in domains:
                domains.append(row[key])
    domains = domains[:9]
    lookup = {(row["first_domain"], row["second_domain"]): int(row["unit_count"]) for row in rows}
    lookup.update({(b, a): value for (a, b), value in list(lookup.items())})
    cell = 54
    left = 210
    top = 150
    width = left + cell * len(domains) + 24
    height = top + cell * len(domains) + 30
    max_value = max(lookup.values(), default=1)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Domain co-occurrence heatmap">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, domain in enumerate(domains):
        label = domain.replace("_", " ")
        x = left + index * cell + cell / 2
        parts.append(
            f'<text transform="translate({x:.1f} {top - 10}) rotate(-45)" '
            f'text-anchor="start" font-size="11" fill="#24313a">{esc(label)}</text>'
        )
        y = top + index * cell + cell / 2 + 4
        parts.append(
            f'<text x="{left - 10}" y="{y:.1f}" text-anchor="end" '
            f'font-size="11" fill="#24313a">{esc(label)}</text>'
        )
    for y_index, first in enumerate(domains):
        for x_index, second in enumerate(domains):
            value = lookup.get((first, second), 0) if first != second else 0
            alpha = 0.12 + 0.78 * value / max_value if value else 0.04
            x = left + x_index * cell
            y = top + y_index * cell
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell - 2}" height="{cell - 2}" '
                f'fill="rgba(47,111,115,{alpha:.2f})"/>'
            )
            if value:
                parts.append(
                    f'<text x="{x + cell / 2:.1f}" y="{y + cell / 2 + 4:.1f}" '
                    f'text-anchor="middle" font-size="12" font-weight="700" '
                    f'fill="#1f2a33">{value}</text>'
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
        cells = []
        for cell in row:
            if str(cell).startswith("<"):
                cells.append(f"<td>{cell}</td>")
            else:
                cells.append(f"<td>{esc(cell)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    domain_chart_rows = [
        {"label": row["label"], "unit_count": row["unit_count"]} for row in report["domain_rows"]
    ]
    group_chart_rows = [
        {"label": row["label"], "unit_count": row["unit_count"]}
        for row in report["domain_group_rows"]
    ]
    division_rows = [
        {"division": key, "count": value}
        for key, value in summary["outside_context_division_counts"].items()
    ]
    frame_rows = [
        [row["frame"], row["unit_count"], row["sensitive_unit_count"], row["control_question"]]
        for row in report["frame_rows"]
    ]
    axis_rows = [
        [row["axis"], row["unit_count"], row["evidence"], row["review_question"]]
        for row in report["axis_rows"]
    ]
    domain_rows = [
        [
            row["label"],
            row["group_label"],
            row["unit_count"],
            row["high_pressure_units"],
            row["reception_sensitive_units"],
            row["textual_witness_units"],
            row["top_outside_division"],
        ]
        for row in report["domain_rows"]
    ]
    priority_rows = [
        [
            row["ref"],
            row["unit_id"],
            row["priority_score"],
            row["context_pressure_intensity"],
            row["domain_count"],
            join_values(row["domains"]),
            "yes" if row["reception_sensitive"] else "no",
            join_values(row["review_roles"]),
        ]
        for row in report["priority_unit_rows"][:25]
    ]
    cooccurrence_rows = [
        [
            row["first_label"],
            row["second_label"],
            row["unit_count"],
            row["high_pressure_units"],
            row["reception_sensitive_units"],
        ]
        for row in report["cooccurrence_rows"][:25]
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Contextual Pressure Atlas</title>
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
    <h1>AlephTav Contextual Pressure Atlas</h1>
    <p class="lede">
      Doctoral-style routing atlas for the 100-unit Psalms benchmark. It shows
      where Hebrew-to-English translation requires broader Tanakh form context,
      ancient cultural setting, textual witness control, and separated Jewish
      and Christian reception frames.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Atlas Summary</h2>
      {
        metric_cards(
            [
                ("Units", fmt_int(summary["unit_count"]), "Benchmark units routed."),
                ("Tokens", fmt_int(summary["token_count"]), "Token records under review."),
                (
                    "Ancient context",
                    fmt_int(summary["ancient_context_unit_count"]),
                    "Units with culture or setting domains.",
                ),
                (
                    "Broad canon",
                    fmt_int(summary["broad_canonical_context_unit_count"]),
                    "Units with outside-Psalms context in all five divisions.",
                ),
                (
                    "Reception",
                    fmt_int(summary["reception_sensitive_unit_count"]),
                    "Units requiring separated Jewish/Christian frames.",
                ),
                (
                    "Textual pressure",
                    fmt_int(summary["textual_witness_pressure_unit_count"]),
                    "Units requiring witness/provenance controls.",
                ),
                (
                    "Priority",
                    fmt_int(summary["high_priority_review_unit_count"]),
                    "Units above the atlas priority threshold.",
                ),
                (
                    "Outside context",
                    f'''{summary["surface_outside_context_pct"]:.2f}%''',
                    "Token forms with outside-Psalms context.",
                ),
            ]
        )
    }
      <div class="warning">
        Domain hits are review-routing evidence, not interpretive conclusions.
        The atlas separates translation, historical setting, and reception
        before any model output can be treated as approved.
      </div>
    </section>

    <section>
      <h2>Interpretive Axes</h2>
      {table(["Axis", "Units", "Evidence", "Review Question"], axis_rows)}
    </section>

    <section>
      <h2>Context Domains</h2>
      <div class="chart">{
        svg_horizontal_bars(
            domain_chart_rows,
            label_key="label",
            value_key="unit_count",
            aria_label="Benchmark unit counts by context domain",
            color="#2f6f73",
        )
    }</div>
      {
        table(
            [
                "Domain",
                "Group",
                "Units",
                "High",
                "Reception",
                "Textual",
                "Top Outside Division",
            ],
            domain_rows,
        )
    }
    </section>

    <section>
      <h2>Canonical Breadth</h2>
      <div class="chart">{
        svg_horizontal_bars(
            division_rows,
            label_key="division",
            value_key="count",
            aria_label="Outside-Psalms form context by Tanakh division",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            group_chart_rows,
            label_key="label",
            value_key="unit_count",
            aria_label="Context domain group counts",
            color="#4f6f38",
        )
    }</div>
    </section>

    <section>
      <h2>Reception Frames</h2>
      {table(["Frame", "Units", "Sensitive Units", "Control Question"], frame_rows)}
    </section>

    <section>
      <h2>Domain Co-Occurrence</h2>
      <div class="chart">{svg_cooccurrence_heatmap(report["cooccurrence_rows"])}</div>
      {
        table(
            ["First Domain", "Second Domain", "Units", "High", "Reception"],
            cooccurrence_rows,
        )
    }
    </section>

    <section>
      <h2>Priority Units</h2>
      {
        table(
            [
                "Ref",
                "Unit",
                "Priority",
                "Intensity",
                "Domains",
                "Domain List",
                "Reception",
                "Review Roles",
            ],
            priority_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate contextual pressure atlas for the benchmark set."
    )
    parser.add_argument("--matrix", type=Path, default=MATRIX_PATH)
    parser.add_argument("--rubric", type=Path, default=RUBRIC_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.matrix, args.rubric)
    write_json(args.json_output, report)
    write_csv(args.csv_output, report["priority_unit_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
