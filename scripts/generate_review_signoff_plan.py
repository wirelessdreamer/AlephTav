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
RUBRIC_PATH = ROOT / "docs" / "research" / "reviewer_signoff_rubric.json"
SUITE_PATH = ROOT / "reports" / "research" / "local_model_benchmark_suite.json"
AUDIT_PATH = ROOT / "reports" / "research" / "local_model_benchmark_result_audit.json"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "research" / "review_signoff_plan.json"
DEFAULT_CSV_OUTPUT = ROOT / "reports" / "research" / "review_signoff_template.csv"
DEFAULT_HTML_OUTPUT = ROOT / "reports" / "research" / "review_signoff_plan.html"


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


def project_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def role_map(rubric: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(role["role"]): role for role in rubric["human_reviewer_roles"]}


def required_roles_for_task(task: dict[str, Any], rubric: dict[str, Any]) -> list[str]:
    tags = set(str(tag) for tag in task.get("benchmark_tags", []))
    layer = str(task.get("layer"))
    roles = []
    for role in rubric["human_reviewer_roles"]:
        name = str(role["role"])
        if role.get("required_for_release"):
            continue
        if layer in role.get("required_for_layers", []):
            roles.append(name)
            continue
        required_tags = set(str(tag) for tag in role.get("required_for_tags", []))
        if tags & required_tags:
            roles.append(name)
    return sorted(set(roles))


def review_intensity(required_roles: list[str], tags: list[str]) -> str:
    sensitive_tags = {
        "reception_history",
        "jewish_christian_reception",
        "messianic_interpretation",
        "textual_witness",
        "lexical_dispute",
        "imprecation",
        "violence",
    }
    if len(required_roles) >= 5 or sensitive_tags & set(tags):
        return "high"
    if len(required_roles) >= 4:
        return "medium"
    return "standard"


def task_review_rows(
    suite: dict[str, Any],
    rubric: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for task in suite["tasks"]:
        roles = required_roles_for_task(task, rubric)
        tags = [str(tag) for tag in task.get("benchmark_tags", [])]
        rows.append(
            {
                "task_id": task["task_id"],
                "unit_id": task["unit_id"],
                "ref": task["ref"],
                "layer": task["layer"],
                "required_roles": roles,
                "required_role_count": len(roles),
                "intensity": review_intensity(roles, tags),
                "benchmark_tags": tags,
                "candidate_count": int(task["generation_input"]["candidate_count"]),
            }
        )
    return rows


def build_review_templates(
    task_rows: list[dict[str, Any]],
    suite: dict[str, Any],
    rubric: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    models = [str(model) for model in suite["recommended_bakeoff_models"]]
    human_rows = []
    cross_exam_rows = []
    for task in task_rows:
        for model in models:
            for candidate_index in range(1, int(task["candidate_count"]) + 1):
                for role in task["required_roles"]:
                    human_rows.append(
                        {
                            "task_id": task["task_id"],
                            "unit_id": task["unit_id"],
                            "ref": task["ref"],
                            "layer": task["layer"],
                            "model_profile_id": model,
                            "candidate_index": candidate_index,
                            "reviewer_role": role,
                            "reviewer_id": "",
                            "score_0_5": "",
                            "gate_failures": "",
                            "required_corrections": "",
                            "confidence_0_1": "",
                            "evidence_notes": "",
                            "created_at": "",
                        }
                    )
                for judge in rubric["model_cross_examination"]:
                    cross_exam_rows.append(
                        {
                            "task_id": task["task_id"],
                            "unit_id": task["unit_id"],
                            "ref": task["ref"],
                            "layer": task["layer"],
                            "model_profile_id": model,
                            "candidate_index": candidate_index,
                            "judge_id": judge["judge_id"],
                            "judge_type": judge["judge_type"],
                            "authority": judge["authority"],
                            "focus": "; ".join(judge["focus"]),
                            "score_0_5": "",
                            "concerns": "",
                            "created_at": "",
                        }
                    )
    return human_rows, cross_exam_rows


def summarize(
    task_rows: list[dict[str, Any]],
    human_rows: list[dict[str, Any]],
    cross_exam_rows: list[dict[str, Any]],
    suite: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    role_counts: Counter[str] = Counter()
    intensity_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    for task in task_rows:
        role_counts.update(task["required_roles"])
        intensity_counts[task["intensity"]] += 1
        tag_counts.update(task["benchmark_tags"])
    model_count = len(suite["recommended_bakeoff_models"])
    candidate_count = int(suite["summary"]["candidate_count_per_task"])
    return {
        "task_count": len(task_rows),
        "planned_model_count": model_count,
        "candidate_count_per_task": candidate_count,
        "projected_candidate_outputs": len(task_rows) * model_count * candidate_count,
        "projected_human_review_rows": len(human_rows),
        "projected_model_cross_exam_rows": len(cross_exam_rows),
        "required_role_counts_by_task": dict(role_counts.most_common()),
        "task_intensity_counts": dict(intensity_counts.most_common()),
        "benchmark_tag_counts": dict(tag_counts.most_common()),
        "real_submitted_model_results": audit["summary"]["submitted_result_count"],
        "real_missing_model_results": audit["summary"]["missing_expected_result_count"],
    }


def build_plan(
    rubric_path: Path,
    suite_path: Path,
    audit_path: Path,
) -> dict[str, Any]:
    rubric = load_json(rubric_path)
    suite = load_json(suite_path)
    audit = load_json(audit_path)
    task_rows = task_review_rows(suite, rubric)
    human_rows, cross_exam_rows = build_review_templates(task_rows, suite, rubric)
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated review signoff plan; no completed reviews yet",
        "source_paths": {
            "rubric": project_path(rubric_path),
            "benchmark_suite": project_path(suite_path),
            "result_audit": project_path(audit_path),
        },
        "thresholds": rubric["approval_thresholds"],
        "score_scale": rubric["score_scale"],
        "summary": summarize(task_rows, human_rows, cross_exam_rows, suite, audit),
        "human_reviewer_roles": rubric["human_reviewer_roles"],
        "model_cross_examination": rubric["model_cross_examination"],
        "task_review_plan": task_rows,
        "human_review_template_rows": human_rows,
        "model_cross_exam_template_rows": cross_exam_rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


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


def render_html(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    role_rows = [
        [
            role["role"],
            ", ".join(role.get("required_for_layers", [])),
            ", ".join(role.get("required_for_tags", [])),
            "; ".join(role["gate_failures"]),
        ]
        for role in plan["human_reviewer_roles"]
    ]
    task_rows = [
        [
            row["task_id"],
            row["ref"],
            row["layer"],
            row["intensity"],
            ", ".join(row["required_roles"]),
        ]
        for row in plan["task_review_plan"]
    ]
    judge_rows = [
        [
            judge["judge_id"],
            judge["judge_type"],
            judge["authority"],
            "; ".join(judge["focus"]),
        ]
        for judge in plan["model_cross_examination"]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Review Signoff Plan</title>
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
    <h1>AlephTav Review Signoff Plan</h1>
    <p class="lede">
      Projected human review and model cross-examination plan for the generated
      local model benchmark suite. Model critics are advisory only; human roles
      remain the approval authority.
    </p>
    <p class="meta">Generated {esc(plan["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Projected Workload</h2>
      {
        metric_cards(
            [
                (
                    "Tasks",
                    fmt_int(summary["task_count"]),
                    "Benchmark tasks requiring review routing.",
                ),
                (
                    "Candidate outputs",
                    fmt_int(summary["projected_candidate_outputs"]),
                    "Projected model candidates across all planned model-task runs.",
                ),
                (
                    "Human review rows",
                    fmt_int(summary["projected_human_review_rows"]),
                    "Projected role-specific human review records.",
                ),
                (
                    "Model critiques",
                    fmt_int(summary["projected_model_cross_exam_rows"]),
                    "Advisory model cross-examination records.",
                ),
            ]
        )
    }
      <div class="warning">
        This is a signoff plan, not completed review evidence. Real model
        outputs are still missing, and no human reviews have been recorded.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["required_role_counts_by_task"], "role"),
            label_key="role",
            value_key="count",
            aria_label="Required reviewer roles by task",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["task_intensity_counts"], "intensity"),
            label_key="intensity",
            value_key="count",
            aria_label="Task intensity counts",
            color="#7c5b2f",
        )
    }</div>
    </section>

    <section>
      <h2>Human Reviewer Roles</h2>
      {table(["Role", "Layers", "Tags", "Gate failures"], role_rows)}
    </section>

    <section>
      <h2>Model Cross-Examination</h2>
      {table(["Judge", "Type", "Authority", "Focus"], judge_rows)}
    </section>

    <section>
      <h2>Task Routing</h2>
      {table(["Task", "Reference", "Layer", "Intensity", "Required roles"], task_rows)}
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate benchmark review signoff plan and CSV template."
    )
    parser.add_argument("--rubric", type=Path, default=RUBRIC_PATH)
    parser.add_argument("--suite", type=Path, default=SUITE_PATH)
    parser.add_argument("--audit", type=Path, default=AUDIT_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan = build_plan(args.rubric, args.suite, args.audit)
    write_json(args.json_output, plan)
    write_csv(args.csv_output, plan["human_review_template_rows"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(plan), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
