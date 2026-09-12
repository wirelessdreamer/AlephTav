from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

build_adapter = import_module("app.llm.adapters").build_adapter
GenerationRequest = import_module("app.llm.base").GenerationRequest


SUITE_PATH = ROOT / "reports" / "research" / "local_model_benchmark_suite.json"
OUTPUT_SCHEMA_PATH = ROOT / "app" / "llm" / "contracts" / "generation_output.schema.json"
DEFAULT_OUTPUT_PATH = ROOT / "reports" / "research" / "local_model_benchmark_results.jsonl"
DEFAULT_DRY_RUN_OUTPUT_PATH = (
    ROOT / "reports" / "research" / "local_model_benchmark_dry_run_results.jsonl"
)

LAYER_CONTRACTS = {
    "gloss": {
        "delivery_profile": "lexical gloss",
        "differentiator": "pipe-separated source-order lexical gloss",
        "text_placeholder": "token gloss | token gloss | token gloss",
        "rules": [
            "Render token-by-token lexical value, not a polished sentence.",
            "Use pipe separators between lexical units.",
            "If the source has more than one token, text must include pipe separators.",
            "Preserve Hebrew source order.",
            "Each pipe segment should be a short lexical gloss, not a clause.",
            "Do not rearrange into standard English grammar.",
            "Do not add English function words unless a source token requires them.",
            "Allow compact or awkward English.",
            "Do not add reception-history or doctrinal smoothing.",
        ],
    },
    "literal": {
        "delivery_profile": "literal translation",
        "differentiator": "readable grammatical literal sentence",
        "text_placeholder": "Readable literal English candidate text",
        "rules": [
            "Render readable grammatical English from the Hebrew source tokens.",
            "Use normal English clause order where English grammar requires it.",
            "Use punctuation to mark direct speech, apposition, and clause boundaries.",
            "Text must be a complete English sentence or sentence sequence.",
            "Do not use pipe separators.",
            "Do not output a token list or source-order gloss.",
            "Preserve source images, divine names, and core Hebrew argument structure.",
            "Add only minimal English function words required for grammar.",
            "Do not paraphrase into reception-history or doctrinal interpretation.",
        ],
    },
}


def layer_contract_for(layer: str) -> dict[str, Any]:
    return LAYER_CONTRACTS.get(layer, LAYER_CONTRACTS["literal"])


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def iter_selected_tasks(
    suite: dict[str, Any],
    *,
    task_id: str | None,
    layer: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    tasks = []
    for task in suite.get("tasks", []):
        if task_id and task["task_id"] != task_id:
            continue
        if layer and task["layer"] != layer:
            continue
        tasks.append(task)
        if limit is not None and len(tasks) >= limit:
            break
    return tasks


def prompt_for_task(task: dict[str, Any]) -> str:
    generation_input = task["generation_input"]
    benchmark = task["benchmark"]
    layer_contract = layer_contract_for(str(task.get("layer") or ""))
    payload = {
        "generation_input": generation_input,
        "layer_contract": layer_contract,
        "benchmark": {
            "task_id": benchmark["task_id"],
            "must_check": benchmark["must_check"],
            "rubric": benchmark["rubric"],
        },
        "output_contract": (
            "Return strict JSON matching app/llm/contracts/generation_output.schema.json. "
            "Do not wrap it in markdown."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def dry_run_candidate(task: dict[str, Any], index: int) -> dict[str, Any]:
    source = task["generation_input"]["locked_inputs"]["source"]
    token_ids = [token["token_id"] for token in source["tokens"] if token.get("token_id")]
    image_tokens = token_ids[: min(4, len(token_ids))]
    return {
        "text": f"[dry-run placeholder {index} for {task['ref']} {task['layer']}]",
        "rationale": (
            "Dry-run placeholder only. This validates result plumbing and must "
            "not be treated as a model translation."
        ),
        "alignment_hints": token_ids,
        "drift_flags": [
            {
                "code": "dry_run_placeholder",
                "severity": "high",
                "confidence": 1.0,
                "message": "Not a real model output.",
            }
        ],
        "metrics": {
            "dry_run": True,
            "token_count": len(token_ids),
        },
        "variation_basis": ["dry_run_pipeline_validation"],
        "preserved_source_images": [
            {
                "label": "source-token-inventory",
                "source_id": "uxlc",
                "token_ids": image_tokens,
                "note": "Placeholder image preservation for pipeline validation.",
            }
        ],
        "differentiator": "dry-run placeholder",
        "grounding_confidence": 0.0,
        "delivery_profile": str(task["layer"]),
        "source_anchor": {
            "anchor_text": str(task["ref"]),
            "source_language": "he",
            "source_text": str(source.get("source_hebrew") or ""),
            "token_ids": token_ids,
            "basis_note": "Dry-run placeholder source anchor for schema validation.",
        },
        "translation_basis": {
            "basis_type": "hebrew_to_english",
            "source_ids": ["uxlc", "oshb", "macula"],
            "source_language": "he",
            "source_version": "benchmark-placeholder",
            "basis_note": "Dry-run placeholder; no translation was attempted.",
        },
    }


def dry_run_output(task: dict[str, Any]) -> dict[str, Any]:
    candidate_count = int(task["generation_input"].get("candidate_count") or 1)
    return {
        "unit_id": task["unit_id"],
        "layer": task["layer"],
        "candidates": [dry_run_candidate(task, index) for index in range(1, candidate_count + 1)],
    }


def model_profile_id(profile: dict[str, Any], fallback: str | None = None) -> str:
    return str(
        profile.get("model_profile_id")
        or profile.get("profile_id")
        or fallback
        or profile.get("model")
        or "unknown-model-profile"
    )


def run_dry_tasks(tasks: list[dict[str, Any]], profile_id: str) -> list[dict[str, Any]]:
    rows = []
    for task in tasks:
        started = time.perf_counter()
        output = dry_run_output(task)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        rows.append(
            {
                "task_id": task["task_id"],
                "model_profile_id": profile_id,
                "generated_on": datetime.now(UTC).isoformat(),
                "output": output,
                "runtime": {
                    "dry_run": True,
                    "elapsed_ms": elapsed_ms,
                    "adapter": "dry-run",
                    "model": "dry-run-placeholder",
                },
            }
        )
    return rows


def run_model_tasks(
    tasks: list[dict[str, Any]],
    *,
    profile: dict[str, Any],
    contract: dict[str, Any],
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    adapter = build_adapter(profile)
    profile_id = model_profile_id(profile)
    rows = []
    for task in tasks:
        prompt = prompt_for_task(task)
        started = time.perf_counter()
        error_message = None
        output: dict[str, Any] | None = None
        raw_text = ""
        runtime: dict[str, Any] = {}
        try:
            response = adapter.generate_json(
                GenerationRequest(
                    prompt=prompt,
                    contract=contract,
                    model=str(profile["model"]),
                    seed=int(task["generation_input"]["seed"]),
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=(
                        "You are a local Hebrew-to-English Psalms benchmark model. "
                        "Return strict JSON only."
                    ),
                    candidate_count=int(task["generation_input"]["candidate_count"]),
                    timeout_seconds=timeout_seconds,
                    metadata={"task_id": task["task_id"]},
                )
            )
            output = response.payload
            raw_text = response.raw_text
            runtime = dict(response.runtime_metadata)
        except Exception as exc:  # pragma: no cover - depends on local model runtime
            error_message = f"{type(exc).__name__}: {exc}"
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        runtime.update(
            {
                "elapsed_ms": elapsed_ms,
                "adapter": adapter.name,
                "model": str(profile["model"]),
                "prompt_estimated_words": adapter.estimate_context(prompt),
            }
        )
        row = {
            "task_id": task["task_id"],
            "model_profile_id": profile_id,
            "generated_on": datetime.now(UTC).isoformat(),
            "runtime": runtime,
        }
        if output is not None:
            row["output"] = output
        if raw_text:
            row["raw_text"] = raw_text
        if error_message:
            row["error"] = error_message
        rows.append(row)
    return rows


def validate_outputs(rows: list[dict[str, Any]], contract: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(contract)
    errors = []
    for row in rows:
        output = row.get("output")
        if not isinstance(output, dict):
            errors.append(f"{row.get('task_id')}: missing output")
            continue
        for error in sorted(validator.iter_errors(output), key=lambda item: item.path):
            errors.append(f"{row.get('task_id')}: {error.message}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local model benchmark tasks and write result JSONL."
    )
    parser.add_argument("--suite", type=Path, default=SUITE_PATH)
    parser.add_argument("--model-profile", type=Path)
    parser.add_argument("--output-schema", type=Path, default=OUTPUT_SCHEMA_PATH)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--task-id")
    parser.add_argument("--layer", choices=["gloss", "literal"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dry-run-profile-id", default="dry-run-placeholder")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1536)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--allow-validation-errors", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suite = load_json(args.suite)
    contract = load_json(args.output_schema)
    tasks = iter_selected_tasks(
        suite,
        task_id=args.task_id,
        layer=args.layer,
        limit=args.limit,
    )
    if not tasks:
        raise SystemExit("No benchmark tasks matched the selection.")

    if args.dry_run:
        output_path = args.output or DEFAULT_DRY_RUN_OUTPUT_PATH
        rows = run_dry_tasks(tasks, args.dry_run_profile_id)
    else:
        if args.model_profile is None:
            raise SystemExit("--model-profile is required unless --dry-run is used.")
        output_path = args.output or DEFAULT_OUTPUT_PATH
        profile = load_json(args.model_profile)
        rows = run_model_tasks(
            tasks,
            profile=profile,
            contract=contract,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
        )

    validation_errors = validate_outputs(rows, contract)
    if validation_errors and not args.allow_validation_errors:
        preview = "\n".join(validation_errors[:8])
        raise SystemExit(f"Generated outputs failed schema validation:\n{preview}")
    write_jsonl(output_path, rows)
    print(f"Wrote {output_path}")
    print(f"Result rows: {len(rows)}")
    if validation_errors:
        print(f"Validation errors: {len(validation_errors)}")


if __name__ == "__main__":
    main()
