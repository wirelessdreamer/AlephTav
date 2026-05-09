from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services import registry_service
from app.services.full_psalm_import_service import import_vendored_psalms


ROOT = Path(__file__).resolve().parents[1]
KNOWN_BAD_PATTERNS = (
    r"\(dm\)",
    r"\(if\)",
    r"\bperson the\b",
    r"\bthe person\b",
    r"\bhis his\b",
    r"\b(i|he|she|they|we|you|my|your|his|her|our|their)\s+\1\b",
    r"[\u0590-\u05FF]",
)
SUPERSCRIPTION_KEYWORD_RE = re.compile(
    r"\b(choirmaster|chief musician|director|psalm|song|prayer|maskil|miktam|shiggaion|david|asaph|jeduthun|korah|solomon|moses|nathan|prophet|bathsheba|doe|morning|lilies|gittith|sheminith|alamoth|ascents|degrees)\b",
    flags=re.IGNORECASE,
)
SPOKEN_CUE_RE = re.compile(
    r"^(yahweh|o\b|my god|why|how blessed|blessed|the heavens|have mercy|save|hear|give ear|judge)\b",
    flags=re.IGNORECASE,
)


@dataclass(slots=True)
class ComposerChoiceRow:
    label: str
    start: int
    end: int


@dataclass(slots=True)
class ComposerUnitOutput:
    unit_id: str
    ref: str
    source_text: str
    token_count: int
    phrase: list[ComposerChoiceRow]
    concept: list[ComposerChoiceRow]
    lyric: list[ComposerChoiceRow]


@dataclass(slots=True)
class AuditIssue:
    code: str
    severity: str
    stage: str | None
    message: str
    details: dict[str, Any]


def bootstrap_vendored_repo() -> None:
    settings = get_settings()
    shutil.rmtree(settings.content_dir, ignore_errors=True)
    settings.db_path.unlink(missing_ok=True)
    settings.assistant_settings_file.unlink(missing_ok=True)
    registry_service.bootstrap_project()
    import_vendored_psalms()


def compile_composer_module(temp_dir: Path) -> Path:
    out_dir = temp_dir / "composer-build"
    tsc_path = ROOT / "node_modules" / ".bin" / "tsc"
    subprocess.run(
        [
            str(tsc_path),
            "app/ui/src/lib/composerSynthesis.ts",
            "--target",
            "ES2020",
            "--module",
            "commonjs",
            "--skipLibCheck",
            "--outDir",
            str(out_dir),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return out_dir / "lib" / "composerSynthesis.js"


def collect_all_unit_ids() -> list[str]:
    return sorted(
        unit_path.stem
        for unit_path in (ROOT / "content" / "psalms").glob("ps*/ps*.json")
        if ".v" in unit_path.stem
    )


def build_composer_outputs(unit_ids: list[str], temp_dir: Path, batch_size: int = 400) -> dict[str, ComposerUnitOutput]:
    module_path = compile_composer_module(temp_dir)
    runner_path = temp_dir / "composer-runner.js"
    runner_path.write_text(
        """
const fs = require("fs");
const path = require("path");

const modulePath = process.argv[2];
const unitIds = JSON.parse(process.argv[3]);
const root = process.argv[4];
const { buildDeterministicComposer } = require(modulePath);

function serializeChoice(choice) {
  return {
    label: choice.label,
    start: choice.tokenStart ?? 0,
    end: choice.tokenEnd ?? choice.tokenStart ?? 0,
  };
}

const payload = {};
for (const unitId of unitIds) {
  const psalmId = unitId.split(".")[0];
  const unitPath = path.join(root, "content", "psalms", psalmId, `${unitId}.json`);
  const unit = JSON.parse(fs.readFileSync(unitPath, "utf8"));
  const plan = buildDeterministicComposer(unit);
  payload[unitId] = {
    unit_id: unit.unit_id,
    ref: unit.ref,
    source_text: unit.source || "",
    token_count: unit.tokens.length,
    phrase: plan.phraseChoices.map(serializeChoice),
    concept: plan.ideaChoices.map(serializeChoice),
    lyric: plan.lyricChoices.map(serializeChoice),
  };
}

process.stdout.write(JSON.stringify(payload));
        """.strip(),
        encoding="utf-8",
    )

    outputs: dict[str, ComposerUnitOutput] = {}
    for start in range(0, len(unit_ids), batch_size):
        batch_ids = unit_ids[start:start + batch_size]
        completed = subprocess.run(
            [
                "node",
                str(runner_path),
                str(module_path),
                json.dumps(batch_ids),
                str(ROOT),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        outputs.update({
            unit_id: ComposerUnitOutput(
                unit_id=data["unit_id"],
                ref=data["ref"],
                source_text=data["source_text"],
                token_count=data["token_count"],
                phrase=[ComposerChoiceRow(**choice) for choice in data["phrase"]],
                concept=[ComposerChoiceRow(**choice) for choice in data["concept"]],
                lyric=[ComposerChoiceRow(**choice) for choice in data["lyric"]],
            )
            for unit_id, data in payload.items()
        })
    return outputs


def _is_superscription_like(output: ComposerUnitOutput) -> bool:
    verse_match = re.search(r":(\d+)$", output.ref)
    verse_number = int(verse_match.group(1)) if verse_match else 0
    if verse_number > 4:
        return False
    lowered = " ".join(choice.label for choice in output.phrase).lower()
    return bool(lowered) and bool(SUPERSCRIPTION_KEYWORD_RE.search(lowered)) and not bool(SPOKEN_CUE_RE.search(lowered))


def _identical_rows(left: list[ComposerChoiceRow], right: list[ComposerChoiceRow]) -> bool:
    return [choice.label for choice in left] == [choice.label for choice in right]


def audit_composer_outputs(outputs: dict[str, ComposerUnitOutput]) -> dict[str, Any]:
    issue_counts: Counter[str] = Counter()
    issue_unit_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    flagged_units: list[dict[str, Any]] = []

    for unit_id in sorted(outputs.keys()):
        output = outputs[unit_id]
        stage_rows = {
            "phrase": output.phrase,
            "concept": output.concept,
            "lyric": output.lyric,
        }
        stage_counts = {stage: len(rows) for stage, rows in stage_rows.items()}
        issues: list[AuditIssue] = []

        for stage, rows in stage_rows.items():
            if not rows:
                issues.append(AuditIssue("empty_stage", "high", stage, f"{stage} emitted no choices", {}))
                continue

            joined = " || ".join(choice.label for choice in rows)
            for pattern in KNOWN_BAD_PATTERNS:
                if re.search(pattern, joined, flags=re.IGNORECASE):
                    issues.append(
                        AuditIssue(
                            "artifact_pattern",
                            "high",
                            stage,
                            f"{stage} matched known bad pattern {pattern!r}",
                            {"pattern": pattern},
                        )
                    )
            if len(rows) == 1 and output.token_count >= 6:
                issues.append(
                    AuditIssue(
                        "collapsed_long_unit",
                        "high",
                        stage,
                        f"{stage} collapsed a {output.token_count}-token unit into one choice",
                        {"token_count": output.token_count},
                    )
                )

            widest_span = max((choice.end - choice.start + 1) for choice in rows)
            if output.token_count >= 8 and widest_span >= max(6, output.token_count - 1):
                issues.append(
                    AuditIssue(
                        "dominant_wide_chunk",
                        "medium",
                        stage,
                        f"{stage} contains an oversized chunk covering {widest_span}/{output.token_count} tokens",
                        {"widest_span": widest_span, "token_count": output.token_count},
                    )
                )

        if len(set(stage_counts.values())) > 1:
            issues.append(
                AuditIssue(
                    "chunk_count_divergence",
                    "medium",
                    None,
                    "stage chunk counts diverged",
                    stage_counts,
                )
            )

        if _is_superscription_like(output) and stage_counts["phrase"] < 2:
            issues.append(
                AuditIssue(
                    "underchunked_superscription",
                    "high",
                    "phrase",
                    "superscription unit did not break into multiple phrase choices",
                    {"token_count": output.token_count},
                )
            )

        if _identical_rows(output.phrase, output.concept) and _identical_rows(output.concept, output.lyric):
            severity = "high" if stage_counts["phrase"] == 1 and output.token_count >= 5 else "medium"
            issues.append(
                AuditIssue(
                    "stage_identity_all",
                    severity,
                    None,
                    "phrase, concept, and lyric rows are identical",
                    {"token_count": output.token_count, **stage_counts},
                )
            )
        else:
            if _identical_rows(output.phrase, output.concept):
                issues.append(
                    AuditIssue(
                        "stage_identity_phrase_concept",
                        "low",
                        None,
                        "phrase and concept rows are identical",
                        stage_counts,
                    )
                )
            if _identical_rows(output.concept, output.lyric):
                issues.append(
                    AuditIssue(
                        "stage_identity_concept_lyric",
                        "low",
                        None,
                        "concept and lyric rows are identical",
                        stage_counts,
                    )
                )

        if stage_counts["phrase"] == stage_counts["concept"] == stage_counts["lyric"] == 1 and output.token_count >= 5:
            issues.append(
                AuditIssue(
                    "single_path_unit",
                    "high",
                    None,
                    "all creative stages expose only one line-wide path",
                    {"token_count": output.token_count},
                )
            )

        if issues:
            unit_issue_codes = {issue.code for issue in issues}
            for issue in issues:
                issue_counts[issue.code] += 1
                severity_counts[issue.severity] += 1
            for code in unit_issue_codes:
                issue_unit_counts[code] += 1
            flagged_units.append(
                {
                    "unit_id": output.unit_id,
                    "ref": output.ref,
                    "token_count": output.token_count,
                    "phrase_count": stage_counts["phrase"],
                    "concept_count": stage_counts["concept"],
                    "lyric_count": stage_counts["lyric"],
                    "phrase": [choice.label for choice in output.phrase],
                    "concept": [choice.label for choice in output.concept],
                    "lyric": [choice.label for choice in output.lyric],
                    "issues": [asdict(issue) for issue in issues],
                }
            )

    flagged_units.sort(
        key=lambda item: (
            -sum(1 for issue in item["issues"] if issue["severity"] == "high"),
            -len(item["issues"]),
            item["unit_id"],
        )
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "psalm_count": 150,
        "unit_count": len(outputs),
        "flagged_unit_count": len(flagged_units),
        "issue_counts": dict(issue_counts.most_common()),
        "issue_unit_counts": dict(issue_unit_counts.most_common()),
        "severity_counts": dict(severity_counts.most_common()),
        "flagged_units": flagged_units,
    }


def write_audit_reports(report: dict[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    top_issue_lines = "\n".join(
        f"| `{code}` | {count} |"
        for code, count in report["issue_unit_counts"].items()
    ) or "| none | 0 |"

    instance_issue_lines = "\n".join(
        f"| `{code}` | {count} |"
        for code, count in report["issue_counts"].items()
    ) or "| none | 0 |"

    sample_units = report["flagged_units"][:25]
    sample_lines = []
    for unit in sample_units:
        issue_codes = ", ".join(issue["code"] for issue in unit["issues"])
        sample_lines.append(
            f"- `{unit['unit_id']}` ({unit['ref']}) - {issue_codes}\n"
            f"  - phrase: {' || '.join(unit['phrase'])}\n"
            f"  - concept: {' || '.join(unit['concept'])}\n"
            f"  - lyric: {' || '.join(unit['lyric'])}"
        )

    md_path.write_text(
        "\n".join(
            [
                "# Composer Quality Audit",
                "",
                f"- Generated: {report['generated_at']}",
                f"- Psalms scanned: {report['psalm_count']}",
                f"- Units scanned: {report['unit_count']}",
                f"- Flagged units: {report['flagged_unit_count']}",
                "",
                "## Issue Counts",
                "",
                "| Issue | Affected Units |",
                "| --- | ---: |",
                top_issue_lines,
                "",
                "## Issue Instance Counts",
                "",
                "| Issue | Raw Instances |",
                "| --- | ---: |",
                instance_issue_lines,
                "",
                "## Severity Counts",
                "",
                "| Severity | Count |",
                "| --- | ---: |",
                *[f"| {severity} | {count} |" for severity, count in report["severity_counts"].items()],
                "",
                "## Top Flagged Units",
                "",
                *(sample_lines or ["- none"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
