from __future__ import annotations

import argparse
import html
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODEL_DATA_PATH = ROOT / "docs" / "research" / "local_translation_model_data.json"
SEED_DATA_PATH = ROOT / "docs" / "research" / "local_translation_benchmark_seed.json"
DEFAULT_OUTPUT_PATH = ROOT / "reports" / "research" / "local_translation_model_report.html"

DIMENSION_LABELS = {
    "local_fit": "Local fit",
    "hebrew_evidence": "Hebrew evidence",
    "context_fit": "Context fit",
    "structured_output": "Structured output",
    "fine_tune_tractability": "Fine-tune tractability",
    "license_governance_fit": "License/governance",
}

PALETTE = [
    "#2f6f73",
    "#7c5b2f",
    "#58508d",
    "#9b3d3d",
    "#4f6f9f",
    "#6f7f3f",
    "#8b5e83",
    "#3f5f4f",
]


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def model_short_name(model: str) -> str:
    replacements = {
        "google/gemma-4-12B-it": "Gemma 4 12B",
        "google/gemma-4-26B-A4B-it": "Gemma 4 26B-A4B",
        "dicta-il/DictaLM-3.0-Nemotron-12B-Instruct": "DictaLM 12B",
        "dicta-il/DictaLM-3.0-24B-Thinking": "DictaLM 24B",
        "Qwen/Qwen3-14B": "Qwen3 14B",
        "Qwen/Qwen3.6-35B-A3B": "Qwen3.6 35B-A3B",
        "mistralai/Mistral-Small-3.2-24B-Instruct-2506": "Mistral Small 3.2",
        "meta-llama/Llama-3.1-8B-Instruct": "Llama 3.1 8B",
    }
    return replacements.get(model, model.split("/")[-1])


def svg_bar_chart(candidates: list[dict[str, Any]]) -> str:
    width = 980
    height = 360
    left = 64
    right = 24
    top = 26
    bottom = 96
    chart_w = width - left - right
    chart_h = height - top - bottom
    max_score = 5.0
    bar_gap = 12
    bar_w = (chart_w - bar_gap * (len(candidates) - 1)) / len(candidates)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Model readiness prior bar chart">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for tick in range(0, 6):
        y = top + chart_h - (tick / max_score) * chart_h
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" '
            'stroke="#d7dde2" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" '
            'font-size="12" fill="#39434d">'
            f"{tick}</text>"
        )
    for index, item in enumerate(candidates):
        score = float(item["mean"])
        x = left + index * (bar_w + bar_gap)
        bar_h = (score / max_score) * chart_h
        y = top + chart_h - bar_h
        color = PALETTE[index % len(PALETTE)]
        label = model_short_name(item["model"])
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'rx="3" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" '
            'font-size="12" font-weight="700" fill="#24313a">'
            f"{score:.2f}</text>"
        )
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{top + chart_h + 22:.1f}" '
            'text-anchor="middle" font-size="11" fill="#24313a">'
            f"{esc(label)}</text>"
        )
    parts.append(
        f'<line x1="{left}" y1="{top + chart_h}" x2="{width - right}" y2="{top + chart_h}" '
        'stroke="#60707d" stroke-width="1.4"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


def svg_heatmap(candidates: list[dict[str, Any]], dimensions: list[str]) -> str:
    cell_w = 126
    cell_h = 32
    left = 190
    top = 72
    width = left + cell_w * len(dimensions) + 28
    height = top + cell_h * len(candidates) + 36
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Model score heatmap">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for col, dimension in enumerate(dimensions):
        x = left + col * cell_w + cell_w / 2
        label = DIMENSION_LABELS.get(dimension, dimension)
        parts.append(
            f'<text x="{x:.1f}" y="18" text-anchor="middle" font-size="11" '
            'fill="#24313a" transform="rotate(-28 '
            f'{x:.1f} 18)">{esc(label)}</text>'
        )
    for row, item in enumerate(candidates):
        y = top + row * cell_h
        parts.append(
            f'<text x="{left - 12}" y="{y + 21}" text-anchor="end" font-size="12" '
            'fill="#24313a">'
            f"{esc(model_short_name(item['model']))}</text>"
        )
        for col, dimension in enumerate(dimensions):
            value = float(item[dimension])
            intensity = int(245 - value / 5 * 92)
            color = f"rgb({intensity},{224 - int(value * 14)},{205 - int(value * 18)})"
            x = left + col * cell_w
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w - 3}" height="{cell_h - 3}" '
                f'rx="3" fill="{color}" stroke="#ffffff"/>'
            )
            parts.append(
                f'<text x="{x + cell_w / 2:.1f}" y="{y + 20}" text-anchor="middle" '
                'font-size="12" font-weight="700" fill="#24313a">'
                f"{value:.0f}</text>"
            )
    parts.append("</svg>")
    return "".join(parts)


def svg_tag_chart(seed_units: list[dict[str, Any]]) -> str:
    counter: Counter[str] = Counter()
    for unit in seed_units:
        counter.update(unit.get("benchmark_tags", []))
    top_tags = counter.most_common(16)
    width = 980
    row_h = 28
    left = 230
    top = 24
    right = 38
    height = top * 2 + row_h * len(top_tags)
    max_count = max((count for _, count in top_tags), default=1)
    chart_w = width - left - right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Benchmark seed tag frequency">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for index, (tag, count) in enumerate(top_tags):
        y = top + index * row_h
        bar_w = chart_w * count / max_count
        parts.append(
            f'<text x="{left - 12}" y="{y + 18}" text-anchor="end" font-size="12" '
            'fill="#24313a">'
            f"{esc(tag)}</text>"
        )
        parts.append(
            f'<rect x="{left}" y="{y + 4}" width="{bar_w:.1f}" height="18" rx="3" fill="#2f6f73"/>'
        )
        parts.append(
            f'<text x="{left + bar_w + 8:.1f}" y="{y + 18}" font-size="12" '
            'font-weight="700" fill="#24313a">'
            f"{count}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def svg_token_distribution(seed_units: list[dict[str, Any]]) -> str:
    width = 980
    height = 320
    left = 58
    right = 20
    top = 24
    bottom = 84
    chart_w = width - left - right
    chart_h = height - top - bottom
    max_tokens = max((int(unit["token_count"]) for unit in seed_units), default=1)
    bar_gap = 6
    bar_w = (chart_w - bar_gap * (len(seed_units) - 1)) / len(seed_units)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Benchmark seed token counts">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for tick in range(0, max_tokens + 1, max(1, math.ceil(max_tokens / 5))):
        y = top + chart_h - (tick / max_tokens) * chart_h
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#d7dde2"/>'
        )
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" '
            'font-size="11" fill="#39434d">'
            f"{tick}</text>"
        )
    for index, unit in enumerate(seed_units):
        count = int(unit["token_count"])
        x = left + index * (bar_w + bar_gap)
        bar_h = chart_h * count / max_tokens
        y = top + chart_h - bar_h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            'rx="2" fill="#7c5b2f"/>'
        )
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{top + chart_h + 18}" '
            'text-anchor="middle" font-size="9" fill="#24313a" transform="rotate(55 '
            f'{x + bar_w / 2:.1f} {top + chart_h + 18})">'
            f"{esc(unit['unit_id'])}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def score_table(candidates: list[dict[str, Any]], dimensions: list[str]) -> str:
    headers = ["Model", "Role", *[DIMENSION_LABELS.get(d, d) for d in dimensions], "Mean"]
    rows = []
    for item in candidates:
        values = [
            (
                f"<td><strong>{esc(model_short_name(item['model']))}</strong><br>"
                f"<span>{esc(item['model'])}</span></td>"
            ),
            f"<td>{esc(item['role'])}</td>",
            *[f'<td class="num">{esc(item[dimension])}</td>' for dimension in dimensions],
            f'<td class="num"><strong>{float(item["mean"]):.2f}</strong></td>',
        ]
        rows.append("<tr>" + "".join(values) + "</tr>")
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{esc(header)}</th>" for header in headers)
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def seed_table(seed_units: list[dict[str, Any]]) -> str:
    rows = []
    for unit in seed_units:
        rows.append(
            "<tr>"
            f"<td><strong>{esc(unit['unit_id'])}</strong><br><span>{esc(unit['ref'])}</span></td>"
            f'<td class="num">{esc(unit["token_count"])}</td>'
            f"<td>{esc(', '.join(unit.get('benchmark_tags', [])))}</td>"
            f"<td>{esc(unit['why_in_seed'])}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Unit</th><th>Tokens</th><th>Tags</th><th>Benchmark reason</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def citation_list(citations: list[dict[str, Any]]) -> str:
    items = []
    for citation in citations:
        url = citation["url"]
        if url.startswith("docs/"):
            href = "../../" + url
        else:
            href = url
        items.append(f'<li><a href="{esc(href)}">{esc(citation["id"])}</a></li>')
    return '<ul class="citations">' + "".join(items) + "</ul>"


def render_html(model_data: dict[str, Any], seed_data: dict[str, Any]) -> str:
    candidates = sorted(model_data["candidate_scores"], key=lambda item: item["mean"], reverse=True)
    dimensions = model_data["score_dimensions"]
    seed_units = seed_data["seed_units"]
    corpus = model_data["current_corpus_scan"]
    generated = model_data["generated_on"]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Local Translation Model Research Dashboard</title>
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
    h3 {{ margin: 22px 0 10px; font-size: 17px; }}
    p {{ margin: 0 0 13px; }}
    .lede {{ max-width: 980px; font-size: 17px; color: #33414c; }}
    .meta {{ color: var(--muted); font-size: 13px; margin-top: 12px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 22px 0; }}
    .card {{ border: 1px solid var(--line); border-radius: 6px; padding: 16px; background: #fff; }}
    .metric {{ font-size: 30px; font-weight: 700; color: var(--accent); }}
    .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .05em;
    }}
    .note {{
      background: #fff8e9;
      border-left: 4px solid var(--accent2);
      padding: 13px 15px;
      margin: 18px 0;
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
    td span {{ color: var(--muted); font-size: 11px; }}
    .num {{ text-align: right; white-space: nowrap; }}
    .flow {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 10px;
      margin: 16px 0 22px;
    }}
    .flow div {{
      min-height: 92px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      background: #fff;
      position: relative;
    }}
    .flow div strong {{ display: block; margin-bottom: 7px; }}
    .flow div:not(:last-child)::after {{
      content: ">";
      position: absolute;
      right: -13px;
      top: 36px;
      color: var(--muted);
      font-weight: 700;
    }}
    .citations {{ columns: 2; }}
    @media (max-width: 900px) {{
      header {{ padding: 30px 24px; }}
      main {{ padding: 24px 18px; }}
      .grid {{ grid-template-columns: repeat(2, 1fr); }}
      .flow {{ grid-template-columns: 1fr; }}
      .flow div:not(:last-child)::after {{ display: none; }}
      .citations {{ columns: 1; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>AlephTav Local Translation Model Research Dashboard</h1>
    <p class="lede">
      A visual baseline for selecting and evaluating a local Hebrew-to-English
      Psalms translation model on 3090-class hardware. The report separates hard
      corpus facts and public model facts from preliminary readiness priors that
      must be replaced by measured local benchmark runs.
    </p>
    <p class="meta">
      Generated {esc(generated)} from docs/research/local_translation_model_data.json
      and docs/research/local_translation_benchmark_seed.json.
    </p>
  </header>
  <main>
    <section>
      <h2>Current Worktree Evidence</h2>
      <div class="grid">
        <div class="card">
          <div class="metric">{esc(corpus["psalm_count"])}</div>
          <div class="label">Psalm directories</div>
        </div>
        <div class="card">
          <div class="metric">{esc(corpus["unit_count"])}</div>
          <div class="label">Verse/unit JSON files</div>
        </div>
        <div class="card">
          <div class="metric">{esc(corpus["total_token_records"])}</div>
          <div class="label">Token records</div>
        </div>
        <div class="card">
          <div class="metric">{esc(corpus["units_with_renderings"])}</div>
          <div class="label">Units with renderings</div>
        </div>
      </div>
      <div class="warning">
        <strong>Interpretation:</strong> the canonical content currently has
        source-token data but no completed rendering corpus. The first model
        assessment must therefore benchmark source-packet generation, alignment,
        provenance, and review quality rather than agreement with a finished
        English translation.
      </div>
    </section>

    <section>
      <h2>Model Readiness Prior</h2>
      <p>
        Scores below are preliminary priors on a 1-5 scale. They are grounded in
        public model data and AlephTav requirements, but they are not measured
        benchmark results.
      </p>
      <div class="chart">{svg_bar_chart(candidates)}</div>
      <div class="chart">{svg_heatmap(candidates, dimensions)}</div>
      {score_table(candidates, dimensions)}
    </section>

    <section>
      <h2>Translation Authority Model</h2>
      <div class="flow">
        <div>
          <strong>Canonical Hebrew</strong>
          UXLC/WLC-derived source text remains the canonical basis.
        </div>
        <div>
          <strong>Linguistic Enrichment</strong>
          OSHB morphology and MACULA syntax/roles provide token-level evidence.
        </div>
        <div>
          <strong>Context Expansion</strong>
          Whole-Tanakh usage, textual witnesses, and cultural setting are
          retrieved as evidence.
        </div>
        <div>
          <strong>Local LLM</strong>
          The model generates candidate JSON, rationale, alignment hints, and
          drift flags.
        </div>
        <div>
          <strong>Review Signoff</strong>
          Human reviewer roles and audit gates decide acceptance or promotion.
        </div>
      </div>
    </section>

    <section>
      <h2>Benchmark Seed Coverage</h2>
      <p>
        The seed manifest contains {len(seed_units)} real unit IDs from the
        current corpus. It is intentionally skewed toward interpretive stress
        cases so generic translation fluency cannot pass as scholarly competence.
      </p>
      <div class="chart">{svg_tag_chart(seed_units)}</div>
      <div class="chart">{svg_token_distribution(seed_units)}</div>
      {seed_table(seed_units)}
    </section>

    <section>
      <h2>Minimum Benchmark Protocol</h2>
      <ol>
        <li>
          Run the same evidence packet through every configured local model with
          fixed seed, prompt hash, model hash, runtime, quantization, and context
          length.
        </li>
        <li>
          Validate JSON schema, provenance, allowed sources, token IDs, alignment
          hints, and drift flags before any reviewer sees the candidate.
        </li>
        <li>
          Score morphology, syntax, poetic parallelism, whole-Tanakh context,
          textual witnesses, Jewish/Christian reception tagging, and local
          performance separately.
        </li>
        <li>
          Use automatic MT metrics only as regression signals. Human review and
          alignment audit remain decisive.
        </li>
        <li>Publish a model card for every accepted adapter or quantized runtime profile.</li>
      </ol>
    </section>

    <section>
      <h2>Sources</h2>
      {citation_list(model_data["citations"])}
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the local model research HTML report.")
    parser.add_argument("--model-data", type=Path, default=MODEL_DATA_PATH)
    parser.add_argument("--seed-data", type=Path, default=SEED_DATA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_data = load_json(args.model_data)
    seed_data = load_json(args.seed_data)
    output_path = args.output
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(model_data, seed_data), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
