from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "reports" / "research" / "local_model_benchmark_suite.json"
OUTPUT_SCHEMA_PATH = ROOT / "app" / "llm" / "contracts" / "generation_output.schema.json"
DEFAULT_OUTPUT_PATH = ROOT / "reports" / "research" / "local_model_benchmark_results.jsonl"

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


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if path.exists() else "w"
    with path.open(mode, encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def selected_tasks(
    suite: dict[str, Any],
    *,
    task_id: str | None,
    layer: str | None,
    limit: int | None,
    skip_pairs: set[tuple[str, str]],
    model_profile_id: str,
) -> list[dict[str, Any]]:
    tasks = []
    for task in suite.get("tasks", []):
        if task_id and task["task_id"] != task_id:
            continue
        if layer and task["layer"] != layer:
            continue
        if (str(task["task_id"]), model_profile_id) in skip_pairs:
            continue
        tasks.append(task)
        if limit is not None and len(tasks) >= limit:
            break
    return tasks


def existing_pairs(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    pairs = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError:
                continue
            task_id = str(row.get("task_id") or "")
            profile_id = str(row.get("model_profile_id") or "")
            if task_id and profile_id:
                pairs.add((task_id, profile_id))
    return pairs


def prompt_for_task(
    task: dict[str, Any],
    *,
    prompt_mode: str,
    candidate_count: int | None,
) -> str:
    if prompt_mode == "compact":
        return compact_prompt_for_task(task, candidate_count=candidate_count)
    generation_input = task["generation_input"]
    benchmark = task["benchmark"]
    layer_contract = layer_contract_for(str(task.get("layer") or ""))
    if candidate_count is not None:
        generation_input = {**generation_input, "candidate_count": candidate_count}
    strict_output_shape = strict_output_shape_for_task(task, layer_contract=layer_contract)
    payload = {
        "generation_input": generation_input,
        "layer_contract": layer_contract,
        "benchmark": {
            "task_id": benchmark["task_id"],
            "must_check": benchmark["must_check"],
            "rubric": benchmark["rubric"],
        },
        "strict_output_shape": strict_output_shape,
        "output_contract": [
            "Return strict JSON matching app/llm/contracts/generation_output.schema.json.",
            "The top-level object must have exactly these keys: unit_id, layer, candidates.",
            "Do not wrap or nest the result under generation_output, metadata, or any other key.",
            "Every candidate must include every key shown in strict_output_shape.",
            "Do not include candidate_id, candidate_text, candidate_tokens, notes, or metadata.",
            "Do not wrap the JSON in markdown.",
            "Do not include reception-history claims inside candidate text.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def strict_output_shape_for_task(
    task: dict[str, Any],
    *,
    layer_contract: dict[str, Any],
) -> dict[str, Any]:
    source = task["generation_input"]["locked_inputs"]["source"]
    token_ids = [
        str(token["token_id"]) for token in source.get("tokens", []) if token.get("token_id")
    ]
    return {
        "unit_id": task["unit_id"],
        "layer": task["layer"],
        "candidates": [
            {
                "text": layer_contract["text_placeholder"],
                "rationale": "Token-grounded Hebrew source rendering.",
                "alignment_hints": token_ids,
                "drift_flags": [],
                "metrics": {"structured_output_test": True},
                "variation_basis": ["hebrew_source"],
                "preserved_source_images": [
                    {
                        "label": "source-token-inventory",
                        "token_ids": token_ids,
                        "note": "Preserve source images without reception-history expansion.",
                    }
                ],
                "differentiator": layer_contract["differentiator"],
                "grounding_confidence": 0.5,
                "delivery_profile": layer_contract["delivery_profile"],
                "source_anchor": {
                    "anchor_text": task["ref"],
                    "source_language": "he",
                    "source_text": source.get("source_hebrew"),
                    "token_ids": token_ids,
                    "basis_note": "Hebrew source token inventory.",
                },
                "translation_basis": {
                    "basis_type": "hebrew_to_english",
                    "source_ids": ["uxlc", "oshb", "macula"],
                    "source_language": "he",
                    "source_version": "benchmark",
                    "basis_note": "Translate only from provided Hebrew evidence.",
                },
            }
        ],
    }


def compact_prompt_for_task(task: dict[str, Any], *, candidate_count: int | None) -> str:
    source = task["generation_input"]["locked_inputs"]["source"]
    layer_contract = layer_contract_for(str(task["layer"]))
    count = candidate_count or int(task["generation_input"].get("candidate_count") or 1)
    tokens = [
        {
            "token_id": token["token_id"],
            "surface": token.get("surface"),
            "lemma": token.get("lemma"),
            "gloss": token.get("display_gloss"),
            "part_of_speech": token.get("part_of_speech"),
        }
        for token in source.get("tokens", [])
    ]
    strict_output_shape = strict_output_shape_for_task(task, layer_contract=layer_contract)
    payload = {
        "task": {
            "task_id": task["task_id"],
            "unit_id": task["unit_id"],
            "ref": task["ref"],
            "layer": task["layer"],
            "candidate_count": count,
            "layer_contract": layer_contract,
        },
        "source": {
            "source_hebrew": source.get("source_hebrew"),
            "tokens": tokens,
        },
        "strict_output_shape": strict_output_shape,
        "rules": [
            "Return one JSON object only.",
            "Do not include markdown, commentary, thoughts, or XML.",
            "Use exactly the required top-level keys: unit_id, layer, candidates.",
            "Every candidate must include every key shown in strict_output_shape.",
            "Do not add optional object keys beyond the example.",
            "Use the task.layer_contract; gloss and literal are not interchangeable.",
            *layer_contract["rules"],
            "Keep text under 25 words and every other string under 12 words.",
            "Close the JSON immediately after the final required field.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def powershell_ollama_request(
    body: dict[str, Any],
    *,
    endpoint: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    powershell = shutil.which("powershell.exe")
    if not powershell:
        raise RuntimeError("powershell.exe is not available from WSL")
    script = (
        "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false); "
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
        "$OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
        "$body = [Console]::In.ReadToEnd(); "
        f"Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/{endpoint}' "
        "-Method Post -Body $body -ContentType 'application/json; charset=utf-8' "
        "| ConvertTo-Json -Depth 100"
    )
    encoded_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
    completed = subprocess.run(
        [powershell, "-NoProfile", "-Command", script],
        input=encoded_body,
        check=False,
        capture_output=True,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8-sig", errors="replace").strip()
        stdout = completed.stdout.decode("utf-8-sig", errors="replace").strip()
        raise RuntimeError(stderr or stdout)
    stdout = completed.stdout.decode("utf-8-sig")
    return json.loads(stdout)


def run_task(
    task: dict[str, Any],
    *,
    contract: dict[str, Any],
    ollama_model: str,
    model_profile_id: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
    prompt_mode: str,
    format_mode: str,
    api_mode: str,
    disable_thinking: bool,
    candidate_count: int | None,
) -> dict[str, Any]:
    request_format: Any = contract if format_mode == "schema" else "json"
    prompt = prompt_for_task(
        task,
        prompt_mode=prompt_mode,
        candidate_count=candidate_count,
    )
    system = (
        "You are a local Hebrew-to-English Psalms benchmark model. "
        "Return one complete JSON object only. Do not reveal thoughts."
    )
    options = {
        "seed": int(task["generation_input"]["seed"]),
        "temperature": temperature,
        "num_predict": max_tokens,
    }
    if api_mode == "chat":
        body = {
            "model": ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": request_format,
            "options": options,
        }
    else:
        body = {
            "model": ollama_model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "format": request_format,
            "options": options,
        }
    if disable_thinking:
        body["think"] = False
    started = time.perf_counter()
    row: dict[str, Any] = {
        "task_id": task["task_id"],
        "model_profile_id": model_profile_id,
        "generated_on": datetime.now(UTC).isoformat(),
        "runtime": {
            "adapter": "windows-ollama-bridge",
            "model": ollama_model,
            "prompt_mode": prompt_mode,
            "format_mode": format_mode,
            "api_mode": api_mode,
            "disable_thinking": disable_thinking,
            "requested_candidate_count": (
                candidate_count or int(task["generation_input"].get("candidate_count") or 1)
            ),
        },
    }
    try:
        response = powershell_ollama_request(
            body,
            endpoint=api_mode,
            timeout_seconds=timeout_seconds,
        )
        if api_mode == "chat":
            raw_text = str((response.get("message") or {}).get("content") or "")
        else:
            raw_text = str(response.get("response") or "")
        row["raw_text"] = raw_text
        row["runtime"].update(
            {
                "eval_count": response.get("eval_count"),
                "prompt_eval_count": response.get("prompt_eval_count"),
                "total_duration": response.get("total_duration"),
                "load_duration": response.get("load_duration"),
                "prompt_eval_duration": response.get("prompt_eval_duration"),
                "eval_duration": response.get("eval_duration"),
            }
        )
        try:
            row["output"] = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            row["error"] = f"JSONDecodeError: {exc}"
    except Exception as exc:  # noqa: BLE001 - preserve bridge/runtime failures.
        row["error"] = f"{type(exc).__name__}: {exc}"
    row["runtime"]["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run benchmark tasks through Windows Ollama from WSL."
    )
    parser.add_argument("--suite", type=Path, default=SUITE_PATH)
    parser.add_argument("--output-schema", type=Path, default=OUTPUT_SCHEMA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--task-id")
    parser.add_argument("--layer", choices=["gloss", "literal"])
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--model", default="gemma4:26b")
    parser.add_argument("--model-profile-id", default="google/gemma-4-26B-A4B-it")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1400)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--prompt-mode", choices=["full", "compact"], default="full")
    parser.add_argument("--format-mode", choices=["schema", "json"], default="schema")
    parser.add_argument("--api-mode", choices=["generate", "chat"], default="generate")
    parser.add_argument("--disable-thinking", action="store_true")
    parser.add_argument("--candidate-count", type=int)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--append", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suite = load_json(args.suite)
    contract = load_json(args.output_schema)
    skip_pairs = existing_pairs(args.output) if args.skip_existing else set()
    tasks = selected_tasks(
        suite,
        task_id=args.task_id,
        layer=args.layer,
        limit=args.limit,
        skip_pairs=skip_pairs,
        model_profile_id=args.model_profile_id,
    )
    rows = [
        run_task(
            task,
            contract=contract,
            ollama_model=args.model,
            model_profile_id=args.model_profile_id,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
            prompt_mode=args.prompt_mode,
            format_mode=args.format_mode,
            api_mode=args.api_mode,
            disable_thinking=args.disable_thinking,
            candidate_count=args.candidate_count,
        )
        for task in tasks
    ]
    if args.append:
        append_jsonl(args.output, rows)
    else:
        write_jsonl(args.output, rows)
    print(f"Wrote {args.output}")
    print(f"Result rows: {len(rows)}")


if __name__ == "__main__":
    main()
