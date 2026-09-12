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
CONTENT_ROOT = ROOT / "content" / "psalms"
REPORT_ROOT = ROOT / "reports" / "research"

CLAIM_MATRIX_PATH = REPORT_ROOT / "translation_claim_evidence_matrix.json"
WITNESS_DIVERGENCE_PATH = REPORT_ROOT / "witness_divergence_report.json"
RECEPTION_BOUNDARY_PATH = REPORT_ROOT / "reception_interpretation_boundary.json"

DEFAULT_JSON_OUTPUT = REPORT_ROOT / "divine_name_policy_report.json"
DEFAULT_TOKEN_CSV_OUTPUT = REPORT_ROOT / "divine_name_policy_tokens.csv"
DEFAULT_UNIT_CSV_OUTPUT = REPORT_ROOT / "divine_name_policy_units.csv"
DEFAULT_PSALM_CSV_OUTPUT = REPORT_ROOT / "divine_name_policy_psalms.csv"
DEFAULT_MARKER_CSV_OUTPUT = REPORT_ROOT / "divine_name_policy_markers.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "divine_name_policy_report.html"

ENGLISH_WITNESS_SOURCES = ["kjv", "asv", "web"]
HEBREW_PREFIXES = "ובלמכשה"

DIVINE_RENDERING_PATTERNS = {
    "LORD": re.compile(r"\bLORD\b"),
    "Jehovah": re.compile(r"\bJehovah\b", flags=re.I),
    "Lord": re.compile(r"\bLord\b"),
    "God": re.compile(r"\bGod\b"),
    "GOD": re.compile(r"\bGOD\b"),
    "Yah": re.compile(r"\bYah\b", flags=re.I),
    "Most High": re.compile(r"\bMost High\b", flags=re.I),
    "Almighty": re.compile(r"\bAlmighty\b", flags=re.I),
}

CATEGORY_LABELS = {
    "yhwh": "YHWH / tetragrammaton",
    "yah": "Yah",
    "elohim": "Elohim / God",
    "el": "El / God",
    "adonai": "Adonai / Lord",
    "elyon": "Elyon / Most High",
    "shaddai": "Shaddai / Almighty",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def maybe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_json(path)


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


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def strip_prefixes(value: str) -> str:
    stripped = value
    while len(stripped) > 1 and stripped[0] in HEBREW_PREFIXES:
        stripped = stripped[1:]
    return stripped


def token_gloss_text(token: dict[str, Any]) -> str:
    features = token.get("compiler_features", {})
    parts = [str(token.get("display_gloss", ""))]
    parts.extend(str(item) for item in token.get("gloss_parts", []))
    parts.extend(str(item) for item in features.get("english_parts", []))
    return " ".join(parts)


def divine_categories(token: dict[str, Any]) -> list[str]:
    lemma = str(token.get("lemma", ""))
    normalized = str(token.get("normalized", ""))
    stripped = strip_prefixes(normalized)
    gloss = token_gloss_text(token).lower()
    surface = str(token.get("surface", ""))
    features = token.get("compiler_features", {})
    categories: set[str] = set()

    if lemma == "יהוה" or "יהוה" in normalized or features.get("divine_name"):
        categories.add("yhwh")
    if lemma == "יָהּ" or (stripped == "יה" and "yah" in gloss):
        categories.add("yah")
    if lemma == "אֱלֹהִים" or "אלה" in normalized:
        categories.add("elohim")
    if lemma == "אֵל" or (stripped == "אל" and "god" in gloss):
        categories.add("el")
    if "אדנ" in normalized or ("lord" in gloss and "אד" in surface):
        categories.add("adonai")
    if lemma == "עֶלְיוֹן" or "עליון" in normalized or "most high" in gloss:
        categories.add("elyon")
    if "שדי" in normalized or "almighty" in gloss:
        categories.add("shaddai")
    return sorted(categories, key=lambda key: list(CATEGORY_LABELS).index(key))


def witness_texts(unit: dict[str, Any]) -> dict[str, str]:
    rows: dict[str, str] = {}
    for witness in unit.get("witnesses", []):
        source_id = str(witness.get("source_id", ""))
        if source_id in ENGLISH_WITNESS_SOURCES:
            rows[source_id] = str(witness.get("text", ""))
    return rows


def divine_renderings(text: str) -> list[str]:
    return sorted(
        label for label, pattern in DIVINE_RENDERING_PATTERNS.items() if pattern.search(text)
    )


def text_excerpt(text: str, limit: int = 150) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def claim_lookup(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["unit_id"]): row for row in report.get("unit_claim_rows", []) if row.get("unit_id")
    }


def witness_divergence_lookup(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["unit_id"]): row for row in report.get("unit_rows", []) if row.get("unit_id")}


def build_token_row(
    unit: dict[str, Any], token: dict[str, Any], categories: list[str]
) -> dict[str, Any]:
    return {
        "unit_id": unit["unit_id"],
        "ref": unit.get("ref", ""),
        "psalm_id": unit["psalm_id"],
        "token_id": token.get("token_id", ""),
        "categories": categories,
        "primary_category": categories[0] if categories else "",
        "category_labels": [CATEGORY_LABELS[category] for category in categories],
        "lemma": token.get("lemma", ""),
        "normalized": token.get("normalized", ""),
        "surface": token.get("surface", ""),
        "display_gloss": token.get("display_gloss", ""),
        "part_of_speech": token.get("part_of_speech", ""),
        "morph_code": token.get("morph_code", ""),
        "compiler_divine_name": bool(token.get("compiler_features", {}).get("divine_name")),
    }


def unit_marker_flags(
    *,
    category_counts: Counter[str],
    witness_profiles: dict[str, list[str]],
    claim: dict[str, Any],
    witness_divergence: dict[str, Any],
) -> list[str]:
    markers = []
    nonempty_profiles = {tuple(value) for value in witness_profiles.values() if value}
    if len(nonempty_profiles) > 1:
        markers.append("english_witness_divine_rendering_disagreement")
    if "yhwh" in category_counts and "adonai" in category_counts:
        markers.append("yhwh_adonai_lord_stack")
    if len(category_counts) > 1:
        markers.append("multiple_divine_title_categories")
    if "yhwh" in category_counts and any("Jehovah" in value for value in witness_profiles.values()):
        markers.append("jehovah_vs_lord_policy_pressure")
    if claim.get("reception_sensitive"):
        markers.append("reception_sensitive_divine_title")
    if claim.get("theology_pressure"):
        markers.append("theology_pressure_divine_title")
    if claim.get("textual_witness_pressure"):
        markers.append("textual_witness_divine_title")
    if "divine_name_rendering_disagreement" in witness_divergence.get("marker_flags", []):
        markers.append("witness_divergence_report_flag")
    if not witness_divergence.get("complete_english_witness_set", True):
        markers.append("incomplete_english_witness_set")
    return markers


def priority_score(
    *,
    title_token_count: int,
    category_counts: Counter[str],
    markers: list[str],
    claim: dict[str, Any],
    witness_divergence: dict[str, Any],
) -> float:
    score = title_token_count * 4.0
    score += len(category_counts) * 8.0
    score += float(category_counts.get("yhwh", 0)) * 2.0
    if "english_witness_divine_rendering_disagreement" in markers:
        score += 26.0
    if "yhwh_adonai_lord_stack" in markers:
        score += 26.0
    if "multiple_divine_title_categories" in markers:
        score += 14.0
    if "jehovah_vs_lord_policy_pressure" in markers:
        score += 12.0
    if "reception_sensitive_divine_title" in markers:
        score += 12.0
    if "theology_pressure_divine_title" in markers:
        score += 10.0
    if "textual_witness_divine_title" in markers:
        score += 8.0
    score += min(28.0, float(claim.get("claim_risk_score") or 0) / 8.0)
    score += min(24.0, float(witness_divergence.get("priority_score") or 0) / 7.0)
    return round(score, 2)


def build_unit_row(
    unit: dict[str, Any],
    token_rows: list[dict[str, Any]],
    claim: dict[str, Any],
    witness_divergence: dict[str, Any],
) -> dict[str, Any]:
    category_counts = Counter()
    for row in token_rows:
        category_counts.update(row["categories"])
    source_texts = witness_texts(unit)
    witness_profiles = {source: divine_renderings(text) for source, text in source_texts.items()}
    markers = unit_marker_flags(
        category_counts=category_counts,
        witness_profiles=witness_profiles,
        claim=claim,
        witness_divergence=witness_divergence,
    )
    score = priority_score(
        title_token_count=len(token_rows),
        category_counts=category_counts,
        markers=markers,
        claim=claim,
        witness_divergence=witness_divergence,
    )
    return {
        "unit_id": unit["unit_id"],
        "ref": unit.get("ref", ""),
        "psalm_id": unit["psalm_id"],
        "divine_title_token_count": len(token_rows),
        "category_counts": dict(category_counts.most_common()),
        "categories": sorted(category_counts),
        "has_yhwh": "yhwh" in category_counts,
        "has_adonai": "adonai" in category_counts,
        "has_elohim": "elohim" in category_counts,
        "has_multiple_categories": len(category_counts) > 1,
        "english_witness_profiles": witness_profiles,
        "english_witness_divine_rendering_disagreement": (
            "english_witness_divine_rendering_disagreement" in markers
        ),
        "marker_flags": markers,
        "marker_count": len(markers),
        "claim_risk_score": claim.get("claim_risk_score", 0),
        "claim_risk_band": claim.get("claim_risk_band", ""),
        "reception_sensitive": bool(claim.get("reception_sensitive")),
        "textual_witness_pressure": bool(claim.get("textual_witness_pressure")),
        "theology_pressure": bool(claim.get("theology_pressure")),
        "required_frames": claim.get("required_frames", []),
        "witness_divergence_priority_score": witness_divergence.get("priority_score", 0),
        "witness_divergence_pct": witness_divergence.get("mean_english_witness_divergence_pct", 0),
        "priority_score": score,
        "kjv_excerpt": text_excerpt(source_texts.get("kjv", "")),
        "asv_excerpt": text_excerpt(source_texts.get("asv", "")),
        "web_excerpt": text_excerpt(source_texts.get("web", "")),
        "token_ids": [row["token_id"] for row in token_rows],
        "token_surfaces": [row["surface"] for row in token_rows],
        "token_glosses": [row["display_gloss"] for row in token_rows],
    }


def build_rows(
    claim_rows: dict[str, dict[str, Any]],
    witness_rows: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    token_rows = []
    unit_rows = []
    for path in sorted(CONTENT_ROOT.glob("ps*/*.v*.json")):
        unit = load_json(path)
        unit_token_rows = []
        for token in unit.get("tokens", []):
            categories = divine_categories(token)
            if not categories:
                continue
            row = build_token_row(unit, token, categories)
            unit_token_rows.append(row)
            token_rows.append(row)
        if unit_token_rows:
            unit_rows.append(
                build_unit_row(
                    unit,
                    unit_token_rows,
                    claim_rows.get(str(unit["unit_id"]), {}),
                    witness_rows.get(str(unit["unit_id"]), {}),
                )
            )
    return token_rows, unit_rows


def build_psalm_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in unit_rows:
        grouped[str(row["psalm_id"])].append(row)
    rows = []
    for psalm_id, psalm_units in grouped.items():
        category_counts: Counter[str] = Counter()
        for unit in psalm_units:
            category_counts.update(unit["category_counts"])
        top = sorted(psalm_units, key=lambda row: float(row["priority_score"]), reverse=True)[0]
        rows.append(
            {
                "psalm_id": psalm_id,
                "divine_title_unit_count": len(psalm_units),
                "divine_title_token_count": sum(
                    int(unit["divine_title_token_count"]) for unit in psalm_units
                ),
                "category_counts": dict(category_counts.most_common()),
                "yhwh_token_count": category_counts.get("yhwh", 0),
                "elohim_token_count": category_counts.get("elohim", 0),
                "adonai_token_count": category_counts.get("adonai", 0),
                "witness_disagreement_unit_count": sum(
                    1
                    for unit in psalm_units
                    if unit["english_witness_divine_rendering_disagreement"]
                ),
                "mean_priority_score": mean(
                    [float(unit["priority_score"]) for unit in psalm_units]
                ),
                "top_unit_id": top["unit_id"],
                "top_ref": top["ref"],
                "top_priority_score": top["priority_score"],
            }
        )
    return sorted(rows, key=lambda row: float(row["mean_priority_score"]), reverse=True)


def build_marker_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in unit_rows:
        counts.update(row["marker_flags"])
    return [
        {"marker": marker, "unit_count": count, "unit_pct": pct(count, len(unit_rows))}
        for marker, count in counts.most_common()
    ]


def category_token_rows(token_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in token_rows:
        counts.update(row["categories"])
    return [
        {
            "category": category,
            "label": CATEGORY_LABELS[category],
            "token_count": count,
        }
        for category, count in counts.most_common()
    ]


def category_unit_rows(unit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in unit_rows:
        counts.update(row["categories"])
    return [
        {
            "category": category,
            "label": CATEGORY_LABELS[category],
            "unit_count": count,
        }
        for category, count in counts.most_common()
    ]


def chart_rows(rows: list[dict[str, Any]], label_key: str, value_key: str) -> list[dict[str, Any]]:
    return [{"label": str(row[label_key]), "value": row[value_key]} for row in rows]


def build_report() -> dict[str, Any]:
    claim_matrix = maybe_load_json(CLAIM_MATRIX_PATH)
    witness_divergence = maybe_load_json(WITNESS_DIVERGENCE_PATH)
    reception_boundary = maybe_load_json(RECEPTION_BOUNDARY_PATH)
    token_rows, unit_rows = build_rows(
        claim_lookup(claim_matrix),
        witness_divergence_lookup(witness_divergence),
    )
    psalm_rows = build_psalm_rows(unit_rows)
    marker_rows = build_marker_rows(unit_rows)
    category_tokens = category_token_rows(token_rows)
    category_units = category_unit_rows(unit_rows)
    priority_rows = sorted(unit_rows, key=lambda row: float(row["priority_score"]), reverse=True)
    witness_disagreement_rows = [
        row for row in unit_rows if row["english_witness_divine_rendering_disagreement"]
    ]
    yhwh_adonai_rows = [row for row in unit_rows if "yhwh_adonai_lord_stack" in row["marker_flags"]]
    reception_rows = [row for row in unit_rows if row["reception_sensitive"]]
    theology_rows = [row for row in unit_rows if row["theology_pressure"]]

    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "divine name policy pressure generated; not rendering approval",
        "source_paths": {
            "content_root": "content/psalms",
            "claim_matrix": str(CLAIM_MATRIX_PATH.relative_to(ROOT)),
            "witness_divergence": str(WITNESS_DIVERGENCE_PATH.relative_to(ROOT)),
            "reception_boundary": str(RECEPTION_BOUNDARY_PATH.relative_to(ROOT)),
        },
        "method": {
            "boundary": (
                "Hebrew divine-name/title tokens and English witness renderings route "
                "review; they do not decide canonical rendering policy."
            ),
            "categories": CATEGORY_LABELS,
            "review_roles": ["Hebrew", "theology", "alignment", "release"],
            "reception_boundary_status": reception_boundary.get("status", ""),
        },
        "summary": {
            "unit_count": 2527,
            "divine_title_unit_count": len(unit_rows),
            "divine_title_unit_pct": pct(len(unit_rows), 2527),
            "divine_title_token_count": len(token_rows),
            "category_count": len(category_tokens),
            "yhwh_token_count": sum(
                int(row["token_count"]) for row in category_tokens if row["category"] == "yhwh"
            ),
            "elohim_token_count": sum(
                int(row["token_count"]) for row in category_tokens if row["category"] == "elohim"
            ),
            "adonai_token_count": sum(
                int(row["token_count"]) for row in category_tokens if row["category"] == "adonai"
            ),
            "witness_disagreement_unit_count": len(witness_disagreement_rows),
            "witness_disagreement_unit_pct": pct(len(witness_disagreement_rows), len(unit_rows)),
            "yhwh_adonai_lord_stack_unit_count": len(yhwh_adonai_rows),
            "reception_sensitive_divine_unit_count": len(reception_rows),
            "theology_pressure_divine_unit_count": len(theology_rows),
            "marker_type_count": len(marker_rows),
            "psalm_with_divine_title_count": len(psalm_rows),
            "top_priority_unit": priority_rows[0]["unit_id"] if priority_rows else "",
            "top_priority_ref": priority_rows[0]["ref"] if priority_rows else "",
            "top_priority_score": priority_rows[0]["priority_score"] if priority_rows else 0.0,
            "top_priority_markers": priority_rows[0]["marker_flags"] if priority_rows else [],
            "status": "generated_not_policy_approval",
        },
        "token_rows": token_rows,
        "unit_rows": priority_rows,
        "psalm_rows": psalm_rows,
        "marker_rows": marker_rows,
        "category_token_rows": category_tokens,
        "category_unit_rows": category_units,
        "visual_data": {
            "category_token_counts": chart_rows(category_tokens, "label", "token_count"),
            "category_unit_counts": chart_rows(category_units, "label", "unit_count"),
            "marker_counts": chart_rows(marker_rows, "marker", "unit_count"),
            "top_unit_priority": chart_rows(priority_rows[:20], "ref", "priority_score"),
            "top_psalm_priority": chart_rows(psalm_rows[:20], "psalm_id", "mean_priority_score"),
        },
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
    row_h = 29
    left = 290
    right = 90
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
        bar_w = chart_w * value / max_value if max_value else 0.0
        parts.append(
            f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" '
            f'font-size="12" fill="#24313a">{esc(row.get(label_key, ""))}</text>'
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


def metric_cards(cards: list[tuple[str, str, str]]) -> str:
    return (
        '<div class="metric-grid">'
        + "".join(
            f"""
            <article class="metric-card">
              <h3>{esc(label)}</h3>
              <p class="metric-value">{esc(value)}</p>
              <p>{esc(note)}</p>
            </article>
            """
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


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    visual = report["visual_data"]
    priority_rows = [
        [
            index + 1,
            row["ref"],
            f"{row['priority_score']:.2f}",
            row["divine_title_token_count"],
            ", ".join(row["categories"]),
            ", ".join(row["marker_flags"]),
            row["kjv_excerpt"],
            row["asv_excerpt"],
            row["web_excerpt"],
        ]
        for index, row in enumerate(report["unit_rows"][:35])
    ]
    psalm_rows = [
        [
            row["psalm_id"],
            row["divine_title_unit_count"],
            row["divine_title_token_count"],
            row["yhwh_token_count"],
            row["elohim_token_count"],
            row["adonai_token_count"],
            row["witness_disagreement_unit_count"],
            f"{row['mean_priority_score']:.2f}",
            row["top_ref"],
        ]
        for row in report["psalm_rows"][:35]
    ]
    marker_rows = [
        [row["marker"], row["unit_count"], f"{row['unit_pct']:.2f}%"]
        for row in report["marker_rows"]
    ]
    category_rows = [[row["label"], row["token_count"]] for row in report["category_token_rows"]]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Divine Name Policy Pressure Report</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #53616f;
      --line: #c9d1d9;
      --panel: #f8fafc;
      --accent: #2f6f73;
      --accent-2: #7c5b2f;
      --warn: #a12727;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background: #fff;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 1260px;
      margin: 0 auto;
      padding: 34px 24px 58px;
    }}
    h1, h2, h3 {{
      line-height: 1.15;
      margin: 0;
    }}
    h1 {{ font-size: 2.15rem; max-width: 1000px; }}
    h2 {{ margin-top: 36px; font-size: 1.45rem; }}
    h3 {{
      color: var(--muted);
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    p {{ color: var(--muted); margin: 8px 0 0; }}
    .lede {{ max-width: 1000px; font-size: 1.05rem; }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
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
      grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
      gap: 20px;
      margin-top: 18px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 0.84rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: #f4f7fa; color: var(--muted); }}
    svg {{ width: 100%; height: auto; display: block; }}
    .callout {{
      border-left: 4px solid var(--warn);
      background: #fff7f5;
      padding: 12px 16px;
      margin-top: 20px;
    }}
    .callout strong {{ color: var(--warn); }}
    footer {{
      margin-top: 32px;
      color: var(--muted);
      font-size: 0.85rem;
    }}
  </style>
</head>
<body>
<main>
  <h1>Divine Name and Title Policy Pressure Report</h1>
  <p class="lede">
    This report identifies Hebrew divine-name and divine-title tokens in the
    Psalm unit corpus, compares KJV/ASV/WEB English witness renderings, and
    cross-references current claim-matrix pressure so divine-name decisions are
    routed to Hebrew, theology, alignment, and release review.
  </p>
  <div class="callout">
    <strong>Authority boundary:</strong>
    {esc(report["method"]["boundary"])}
  </div>

  {
        metric_cards(
            [
                (
                    "Divine Title Units",
                    fmt_int(summary["divine_title_unit_count"]),
                    f"{fmt_pct(summary['divine_title_unit_pct'])} of Psalm units.",
                ),
                (
                    "Title Tokens",
                    fmt_int(summary["divine_title_token_count"]),
                    f"{fmt_int(summary['yhwh_token_count'])} YHWH tokens.",
                ),
                (
                    "Witness Disagreement",
                    fmt_int(summary["witness_disagreement_unit_count"]),
                    f"{fmt_pct(summary['witness_disagreement_unit_pct'])} of title units.",
                ),
                (
                    "YHWH + Adonai",
                    fmt_int(summary["yhwh_adonai_lord_stack_unit_count"]),
                    "Units with Lord/LORD policy-stack pressure.",
                ),
                (
                    "Reception Units",
                    fmt_int(summary["reception_sensitive_divine_unit_count"]),
                    "Reception-sensitive divine-title units.",
                ),
                (
                    "Top Unit",
                    summary["top_priority_ref"],
                    f"Priority score {summary['top_priority_score']:.2f}.",
                ),
            ]
        )
    }

  <section>
    <h2>Visual Policy Pressure</h2>
    <div class="grid-2">
      <div class="panel">
        <h3>Token Counts by Category</h3>
        {
        svg_horizontal_bars(
            visual["category_token_counts"],
            label_key="label",
            value_key="value",
            aria_label="Divine title token counts by category",
            color="#2f6f73",
        )
    }
      </div>
      <div class="panel">
        <h3>Unit Counts by Category</h3>
        {
        svg_horizontal_bars(
            visual["category_unit_counts"],
            label_key="label",
            value_key="value",
            aria_label="Divine title unit counts by category",
            color="#7c5b2f",
        )
    }
      </div>
      <div class="panel">
        <h3>Marker Counts</h3>
        {
        svg_horizontal_bars(
            visual["marker_counts"],
            label_key="label",
            value_key="value",
            aria_label="Divine title policy marker counts",
            color="#9b3d3d",
        )
    }
      </div>
      <div class="panel">
        <h3>Top Unit Priority</h3>
        {
        svg_horizontal_bars(
            visual["top_unit_priority"],
            label_key="label",
            value_key="value",
            aria_label="Top divine title priority units",
            color="#2f6f73",
        )
    }
      </div>
    </div>
  </section>

  <section>
    <h2>Category Counts</h2>
    {table(["Category", "Token Count"], category_rows)}
  </section>

  <section>
    <h2>Policy Markers</h2>
    {table(["Marker", "Unit Count", "Unit %"], marker_rows)}
  </section>

  <section>
    <h2>Highest Priority Units</h2>
    {
        table(
            [
                "Rank",
                "Ref",
                "Priority",
                "Tokens",
                "Categories",
                "Markers",
                "KJV",
                "ASV",
                "WEB",
            ],
            priority_rows,
        )
    }
  </section>

  <section>
    <h2>Psalm Summary</h2>
    {
        table(
            [
                "Psalm",
                "Units",
                "Tokens",
                "YHWH",
                "Elohim",
                "Adonai",
                "Witness Disagreement",
                "Mean Priority",
                "Top Ref",
            ],
            psalm_rows,
        )
    }
  </section>

  <footer>
    Generated {esc(report["generated_at"])} from current local unit JSON.
  </footer>
</main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate divine name policy pressure report.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--token-csv-output", type=Path, default=DEFAULT_TOKEN_CSV_OUTPUT)
    parser.add_argument("--unit-csv-output", type=Path, default=DEFAULT_UNIT_CSV_OUTPUT)
    parser.add_argument("--psalm-csv-output", type=Path, default=DEFAULT_PSALM_CSV_OUTPUT)
    parser.add_argument("--marker-csv-output", type=Path, default=DEFAULT_MARKER_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report()
    write_json(args.json_output, report)
    write_csv(args.token_csv_output, report["token_rows"])
    write_csv(args.unit_csv_output, report["unit_rows"])
    write_csv(args.psalm_csv_output, report["psalm_rows"])
    write_csv(args.marker_csv_output, report["marker_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")


if __name__ == "__main__":
    main()
