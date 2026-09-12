from __future__ import annotations

import argparse
import csv
import html
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"
MODEL_DATA_PATH = ROOT / "docs" / "research" / "local_translation_model_data.json"
SUITE_PATH = REPORT_ROOT / "local_model_benchmark_suite.json"
REAL_AUDIT_PATH = REPORT_ROOT / "local_model_benchmark_result_audit.json"
DRY_AUDIT_PATH = REPORT_ROOT / "local_model_benchmark_dry_run_audit.json"
DEFAULT_JSON_OUTPUT = REPORT_ROOT / "local_runtime_readiness.json"
DEFAULT_CSV_OUTPUT = REPORT_ROOT / "local_runtime_memory_plan.csv"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "local_runtime_readiness.html"

TARGET_VRAM_GB = 24.0
RESERVED_VRAM_GB = 2.0
MAX_CACHE_FILES = 8000
MODEL_EXTENSIONS = {".gguf", ".safetensors", ".bin", ".pt", ".pth", ".onnx"}

COMMANDS = [
    "python3",
    "nvidia-smi",
    "nvcc",
    "ollama",
    "llama-cli",
    "llama.cpp",
    "vllm",
]

PYTHON_PACKAGES = [
    "torch",
    "transformers",
    "vllm",
    "llama_cpp",
    "huggingface_hub",
    "accelerate",
    "peft",
    "bitsandbytes",
    "jsonschema",
]

MODEL_SPECS = {
    "google/gemma-4-12B-it": {
        "params_b": 12.0,
        "active_b": 12.0,
        "role": "first_trainable_base_candidate",
    },
    "dicta-il/DictaLM-3.0-Nemotron-12B-Instruct": {
        "params_b": 12.0,
        "active_b": 12.0,
        "role": "hebrew_specialist_challenger",
    },
    "google/gemma-4-26B-A4B-it": {
        "params_b": 26.0,
        "active_b": 4.0,
        "role": "strong_local_inference_candidate",
    },
    "dicta-il/DictaLM-3.0-24B-Thinking": {
        "params_b": 24.0,
        "active_b": 24.0,
        "role": "hebrew_specialist_high_quality_comparator",
    },
    "Qwen/Qwen3-14B": {
        "params_b": 14.8,
        "active_b": 14.8,
        "role": "multilingual_reasoning_challenger",
    },
    "mistralai/Mistral-Small-3.2-24B-Instruct-2506": {
        "params_b": 24.0,
        "active_b": 24.0,
        "role": "legacy_local_structured_output_comparator",
    },
    "Qwen/Qwen3.6-35B-A3B": {
        "params_b": 35.0,
        "active_b": 3.0,
        "role": "stretch_comparator",
    },
    "meta-llama/Llama-3.1-8B-Instruct": {
        "params_b": 8.0,
        "active_b": 8.0,
        "role": "local_baseline_only",
    },
}

QUANTIZATION_BITS = {
    "fp16": 16.0,
    "q8": 8.0,
    "q6": 6.0,
    "q5": 5.0,
    "q4": 4.0,
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


def fmt_gb(value: int | float) -> str:
    return f"{float(value):.2f} GB"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def run_command(args: list[str], timeout: int = 10) -> dict[str, Any]:
    path = shutil.which(args[0])
    result: dict[str, Any] = {
        "command": args,
        "path": path,
        "available": bool(path),
        "returncode": None,
        "stdout": "",
        "stderr": "",
    }
    if not path:
        return result
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 - report probe failures verbatim.
        result["stderr"] = str(exc)
        return result
    result["returncode"] = completed.returncode
    result["stdout"] = completed.stdout.strip()
    result["stderr"] = completed.stderr.strip()
    return result


def command_inventory() -> list[dict[str, Any]]:
    rows = []
    for name in COMMANDS:
        path = shutil.which(name)
        rows.append({"command": name, "available": bool(path), "path": path})
    return rows


def package_inventory() -> list[dict[str, Any]]:
    rows = []
    for name in PYTHON_PACKAGES:
        available = bool(importlib.util.find_spec(name))
        version = None
        if available:
            try:
                version = importlib.metadata.version(name.replace("_", "-"))
            except importlib.metadata.PackageNotFoundError:
                try:
                    version = importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError:
                    version = "unknown"
        rows.append({"package": name, "available": available, "version": version})
    return rows


def parse_gpu_csv(text: str) -> list[dict[str, Any]]:
    rows = []
    for line in text.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        memory_mb = None
        try:
            memory_mb = int(float(parts[1]))
        except ValueError:
            pass
        rows.append(
            {
                "name": parts[0],
                "memory_total_mb": memory_mb,
                "memory_total_gb": round(memory_mb / 1024, 2) if memory_mb else None,
                "driver_version": parts[2],
            }
        )
    return rows


def gpu_inventory() -> dict[str, Any]:
    query = run_command(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    full = run_command(["nvidia-smi"], timeout=10)
    gpus = parse_gpu_csv(query["stdout"]) if query["returncode"] == 0 else []
    cuda_match = re.search(r"CUDA Version:\s*([0-9.]+)", full.get("stdout", ""))
    return {
        "nvidia_smi_available": bool(query["available"]),
        "query_returncode": query["returncode"],
        "gpus": gpus,
        "gpu_count": len(gpus),
        "max_vram_gb": max(
            (float(gpu["memory_total_gb"] or 0.0) for gpu in gpus),
            default=0.0,
        ),
        "driver_version": gpus[0]["driver_version"] if gpus else None,
        "cuda_version_from_nvidia_smi": cuda_match.group(1) if cuda_match else None,
        "query_error": query["stderr"],
        "nvidia_smi_head": "\n".join(full.get("stdout", "").splitlines()[:12]),
    }


def cache_dirs() -> list[dict[str, str]]:
    home = Path.home()
    return [
        {"label": "project_caches", "path": str(ROOT / "data" / "derived" / "caches")},
        {
            "label": "project_llama_cpp",
            "path": str(ROOT / "data" / "derived" / "caches" / "llama.cpp"),
        },
        {"label": "wsl_huggingface_hub", "path": str(home / ".cache" / "huggingface" / "hub")},
        {"label": "wsl_ollama_models", "path": str(home / ".ollama" / "models")},
        {
            "label": "windows_ollama_models",
            "path": "/mnt/c/Users/dreamer/.ollama/models",
        },
        {
            "label": "windows_huggingface_hub",
            "path": "/mnt/c/Users/dreamer/.cache/huggingface/hub",
        },
    ]


def summarize_cache_dir(path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "file_count_seen": 0,
        "truncated": False,
        "total_bytes_seen": 0,
        "model_file_count": 0,
        "model_bytes_seen": 0,
        "extension_counts": {},
        "model_file_samples": [],
    }
    if not path.exists():
        return summary
    ext_counts: Counter[str] = Counter()
    for root, _dirs, files in os.walk(path):
        for filename in files:
            if summary["file_count_seen"] >= MAX_CACHE_FILES:
                summary["truncated"] = True
                break
            file_path = Path(root) / filename
            try:
                stat = file_path.stat()
            except OSError:
                continue
            ext = file_path.suffix.lower() or "<none>"
            ext_counts[ext] += 1
            summary["file_count_seen"] += 1
            summary["total_bytes_seen"] += stat.st_size
            if ext in MODEL_EXTENSIONS:
                summary["model_file_count"] += 1
                summary["model_bytes_seen"] += stat.st_size
                if len(summary["model_file_samples"]) < 12:
                    summary["model_file_samples"].append(str(file_path))
        if summary["truncated"]:
            break
    summary["total_gb_seen"] = round(summary["total_bytes_seen"] / (1024**3), 3)
    summary["model_gb_seen"] = round(summary["model_bytes_seen"] / (1024**3), 3)
    summary["extension_counts"] = dict(ext_counts.most_common(12))
    return summary


def cache_inventory() -> list[dict[str, Any]]:
    rows = []
    for item in cache_dirs():
        summary = summarize_cache_dir(Path(item["path"]))
        summary["label"] = item["label"]
        rows.append(summary)
    return rows


def estimate_params_b(model_id: str) -> float:
    spec = MODEL_SPECS.get(model_id)
    if spec:
        return float(spec["params_b"])
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)B", model_id)
    if match:
        return float(match.group(1))
    return 12.0


def overhead_gb(params_b: float, quant: str) -> float:
    base = 3.5
    if params_b > 20:
        base = 5.5
    if params_b > 30:
        base = 6.5
    if quant == "fp16":
        base += 1.5
    return base


def qlora_training_estimate_gb(params_b: float) -> float:
    weight_gb = params_b * QUANTIZATION_BITS["q4"] / 8.0
    if params_b <= 12:
        overhead = 10.0
    elif params_b <= 15:
        overhead = 12.0
    elif params_b <= 26:
        overhead = 18.0
    else:
        overhead = 24.0
    return round(weight_gb + overhead, 2)


def training_status(params_b: float) -> str:
    estimate = qlora_training_estimate_gb(params_b)
    if params_b <= 14.8 and estimate <= TARGET_VRAM_GB - 0.5:
        return "possible_with_qlora_context_caps"
    if params_b <= 26:
        return "inference_first_or_rented_gpu_for_training"
    return "not_3090_default"


def memory_plan(model_data: dict[str, Any]) -> list[dict[str, Any]]:
    models = [row["model"] for row in model_data.get("candidate_scores", [])]
    rows = []
    for model_id in models:
        params_b = estimate_params_b(model_id)
        active_b = float(MODEL_SPECS.get(model_id, {}).get("active_b", params_b))
        role = str(MODEL_SPECS.get(model_id, {}).get("role", "candidate"))
        qlora_gb = qlora_training_estimate_gb(params_b)
        for quant, bits in QUANTIZATION_BITS.items():
            weight_gb = params_b * bits / 8.0
            overhead = overhead_gb(params_b, quant)
            total = round(weight_gb + overhead, 2)
            fits = total <= TARGET_VRAM_GB - RESERVED_VRAM_GB
            rows.append(
                {
                    "model": model_id,
                    "role": role,
                    "params_b": params_b,
                    "active_b": active_b,
                    "quantization": quant,
                    "estimated_weight_gb": round(weight_gb, 2),
                    "estimated_runtime_overhead_gb": overhead,
                    "estimated_total_gb": total,
                    "fits_24gb_with_2gb_headroom": fits,
                    "qlora_training_estimate_gb": qlora_gb,
                    "training_status": training_status(params_b),
                }
            )
    return rows


def gate_status(
    *,
    gpu: dict[str, Any],
    commands: list[dict[str, Any]],
    packages: list[dict[str, Any]],
    caches: list[dict[str, Any]],
    dry_audit: dict[str, Any],
    real_audit: dict[str, Any],
) -> list[dict[str, Any]]:
    command_map = {row["command"]: row for row in commands}
    package_map = {row["package"]: row for row in packages}
    model_files = sum(int(row["model_file_count"]) for row in caches)
    runtime_available = any(
        command_map.get(name, {}).get("available") for name in ["ollama", "llama-cli", "vllm"]
    )
    python_runtime_available = any(
        package_map.get(name, {}).get("available") for name in ["vllm", "llama_cpp", "transformers"]
    )
    return [
        {
            "gate": "nvidia_gpu_detected",
            "passed": gpu["gpu_count"] > 0,
            "evidence": f"{gpu['gpu_count']} GPU(s) detected by nvidia-smi.",
        },
        {
            "gate": "target_vram_20gb_or_more",
            "passed": float(gpu["max_vram_gb"]) >= 20.0,
            "evidence": f"Maximum detected VRAM: {gpu['max_vram_gb']:.2f} GB.",
        },
        {
            "gate": "local_runtime_available",
            "passed": bool(runtime_available or python_runtime_available),
            "evidence": "Detected Ollama, llama.cpp, vLLM, llama-cpp-python, or transformers.",
        },
        {
            "gate": "model_cache_present",
            "passed": model_files > 0,
            "evidence": f"Detected {model_files} model-like local cache files.",
        },
        {
            "gate": "benchmark_runner_present",
            "passed": (ROOT / "scripts" / "run_local_model_benchmark_suite.py").exists(),
            "evidence": "Benchmark runner script exists.",
        },
        {
            "gate": "dry_run_verified",
            "passed": int(dry_audit["summary"]["schema_valid_result_count"]) > 0,
            "evidence": (
                f"{dry_audit['summary']['schema_valid_result_count']} dry-run "
                "rows passed schema validation."
            ),
        },
        {
            "gate": "real_model_results_present",
            "passed": int(real_audit["summary"]["submitted_result_count"]) > 0,
            "evidence": (
                f"{real_audit['summary']['submitted_result_count']} real model "
                "result rows submitted."
            ),
        },
    ]


def summarize_report(
    *,
    gpu: dict[str, Any],
    commands: list[dict[str, Any]],
    packages: list[dict[str, Any]],
    caches: list[dict[str, Any]],
    memory_rows: list[dict[str, Any]],
    gates: list[dict[str, Any]],
) -> dict[str, Any]:
    installed_commands = sum(1 for row in commands if row["available"])
    installed_packages = sum(1 for row in packages if row["available"])
    model_files = sum(int(row["model_file_count"]) for row in caches)
    model_gb = sum(float(row.get("model_gb_seen") or 0.0) for row in caches)
    q4_fit_models = {
        row["model"]
        for row in memory_rows
        if row["quantization"] == "q4" and row["fits_24gb_with_2gb_headroom"]
    }
    q5_fit_models = {
        row["model"]
        for row in memory_rows
        if row["quantization"] == "q5" and row["fits_24gb_with_2gb_headroom"]
    }
    qlora_possible = {
        row["model"]
        for row in memory_rows
        if row["quantization"] == "q4"
        and row["training_status"] == "possible_with_qlora_context_caps"
    }
    passed_gates = sum(1 for gate in gates if gate["passed"])
    return {
        "gpu_count": gpu["gpu_count"],
        "max_vram_gb": gpu["max_vram_gb"],
        "installed_command_count": installed_commands,
        "checked_command_count": len(commands),
        "installed_python_package_count": installed_packages,
        "checked_python_package_count": len(packages),
        "model_cache_file_count": model_files,
        "model_cache_gb_seen": round(model_gb, 3),
        "q4_fit_model_count": len(q4_fit_models),
        "q5_fit_model_count": len(q5_fit_models),
        "qlora_possible_model_count": len(qlora_possible),
        "readiness_gate_count": len(gates),
        "readiness_gate_pass_count": passed_gates,
        "readiness_gate_pass_pct": pct(passed_gates, len(gates)),
    }


def build_report(
    *,
    model_data_path: Path,
    suite_path: Path,
    dry_audit_path: Path,
    real_audit_path: Path,
) -> dict[str, Any]:
    model_data = load_json(model_data_path)
    suite = load_json(suite_path)
    dry_audit = load_json(dry_audit_path)
    real_audit = load_json(real_audit_path)
    gpu = gpu_inventory()
    commands = command_inventory()
    packages = package_inventory()
    caches = cache_inventory()
    memory_rows = memory_plan(model_data)
    gates = gate_status(
        gpu=gpu,
        commands=commands,
        packages=packages,
        caches=caches,
        dry_audit=dry_audit,
        real_audit=real_audit,
    )
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated local runtime readiness audit; no inference run",
        "source_paths": {
            "model_data": "docs/research/local_translation_model_data.json",
            "benchmark_suite": "reports/research/local_model_benchmark_suite.json",
            "dry_run_audit": "reports/research/local_model_benchmark_dry_run_audit.json",
            "real_result_audit": "reports/research/local_model_benchmark_result_audit.json",
        },
        "machine": {
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
            "python_executable": sys.executable,
            "cwd": str(ROOT),
        },
        "hardware_target": model_data["hardware_target"],
        "benchmark_scope": suite["summary"],
        "gpu_inventory": gpu,
        "command_inventory": commands,
        "python_package_inventory": packages,
        "cache_inventory": caches,
        "memory_plan_method": {
            "warning": (
                "Memory figures are planning estimates, not measured benchmark "
                "results. They use parameter count, quantization bits, and a "
                "simple runtime overhead allowance for 3090-class screening."
            ),
            "target_vram_gb": TARGET_VRAM_GB,
            "reserved_vram_gb": RESERVED_VRAM_GB,
        },
        "memory_plan": memory_rows,
        "readiness_gates": gates,
        "summary": summarize_report(
            gpu=gpu,
            commands=commands,
            packages=packages,
            caches=caches,
            memory_rows=memory_rows,
            gates=gates,
        ),
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
    row_h = 29
    left = 300
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


def svg_gate_status(gates: list[dict[str, Any]]) -> str:
    rows = [{"gate": gate["gate"], "value": 1 if gate["passed"] else 0} for gate in gates]
    return svg_horizontal_bars(
        rows,
        label_key="gate",
        value_key="value",
        aria_label="Runtime readiness gate status",
        color="#2f6f73",
    )


def svg_memory_plan(rows: list[dict[str, Any]]) -> str:
    q4_rows = [
        {
            "model": row["model"].split("/")[-1],
            "gb": row["estimated_total_gb"],
        }
        for row in rows
        if row["quantization"] == "q4"
    ]
    q4_rows.sort(key=lambda row: float(row["gb"]), reverse=True)
    return svg_horizontal_bars(
        q4_rows,
        label_key="model",
        value_key="gb",
        aria_label="Estimated q4 runtime memory by model",
        color="#7c5b2f",
    )


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
    gpu_rows = [
        [
            gpu["name"],
            fmt_gb(gpu["memory_total_gb"] or 0),
            gpu["driver_version"],
        ]
        for gpu in report["gpu_inventory"]["gpus"]
    ] or [["No GPU detected", "0.00 GB", "n/a"]]
    gate_rows = [
        [
            gate["gate"],
            "pass" if gate["passed"] else "fail",
            gate["evidence"],
        ]
        for gate in report["readiness_gates"]
    ]
    command_rows = [
        [
            row["command"],
            "yes" if row["available"] else "no",
            row["path"] or "",
        ]
        for row in report["command_inventory"]
    ]
    cache_rows = [
        [
            row["label"],
            row["path"],
            "yes" if row["exists"] else "no",
            row["file_count_seen"],
            row["model_file_count"],
            row.get("model_gb_seen", 0.0),
            "yes" if row["truncated"] else "no",
        ]
        for row in report["cache_inventory"]
    ]
    memory_rows = [
        [
            row["model"].split("/")[-1],
            row["quantization"],
            row["params_b"],
            row["estimated_total_gb"],
            "yes" if row["fits_24gb_with_2gb_headroom"] else "no",
            row["training_status"],
        ]
        for row in report["memory_plan"]
        if row["quantization"] in {"q4", "q5", "fp16"}
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Local Runtime Readiness</title>
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
    <h1>AlephTav Local Runtime Readiness</h1>
    <p class="lede">
      Hardware, runtime, cache, and 3090-class memory planning audit for the
      local Hebrew-to-English model benchmark. This report records local facts
      and planning estimates; it is not a model-quality result.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Readiness Summary</h2>
      {
        metric_cards(
            [
                ("GPU count", fmt_int(summary["gpu_count"]), "Detected by nvidia-smi."),
                ("Max VRAM", fmt_gb(summary["max_vram_gb"]), "Largest detected GPU."),
                (
                    "Gates passed",
                    f'''{summary["readiness_gate_pass_count"]}/{summary["readiness_gate_count"]}''',
                    f'''{summary["readiness_gate_pass_pct"]:.2f}% runtime readiness.''',
                ),
                (
                    "Model cache",
                    fmt_int(summary["model_cache_file_count"]),
                    f'''{summary["model_cache_gb_seen"]:.3f} GiB model-like files seen.''',
                ),
            ]
        )
    }
      <div class="warning">
        Memory estimates are planning heuristics. Real acceptance still requires
        measured model runs with model hash, quantization, prompt hash, seed,
        runtime, VRAM, benchmark score, and human review.
      </div>
      <div class="chart">{svg_gate_status(report["readiness_gates"])}</div>
      <div class="chart">{svg_memory_plan(report["memory_plan"])}</div>
    </section>

    <section>
      <h2>GPU Inventory</h2>
      {table(["GPU", "Memory", "Driver"], gpu_rows)}
    </section>

    <section>
      <h2>Readiness Gates</h2>
      {table(["Gate", "Status", "Evidence"], gate_rows)}
    </section>

    <section>
      <h2>Runtime Commands</h2>
      {table(["Command", "Available", "Path"], command_rows)}
    </section>

    <section>
      <h2>Model Cache Scan</h2>
      {
        table(
            [
                "Cache",
                "Path",
                "Exists",
                "Files seen",
                "Model files",
                "Model GiB",
                "Truncated",
            ],
            cache_rows,
        )
    }
    </section>

    <section>
      <h2>3090-Class Memory Plan</h2>
      {
        table(
            [
                "Model",
                "Quant",
                "Params B",
                "Estimated GB",
                "Fits 24GB",
                "Training status",
            ],
            memory_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate local runtime readiness report for model benchmark."
    )
    parser.add_argument("--model-data", type=Path, default=MODEL_DATA_PATH)
    parser.add_argument("--suite", type=Path, default=SUITE_PATH)
    parser.add_argument("--dry-audit", type=Path, default=DRY_AUDIT_PATH)
    parser.add_argument("--real-audit", type=Path, default=REAL_AUDIT_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        model_data_path=args.model_data,
        suite_path=args.suite,
        dry_audit_path=args.dry_audit,
        real_audit_path=args.real_audit,
    )
    write_json(args.json_output, report)
    write_csv(args.csv_output, report["memory_plan"])
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
