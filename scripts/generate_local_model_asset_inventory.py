from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "research"
MODEL_DATA_PATH = ROOT / "docs" / "research" / "local_translation_model_data.json"
RUNTIME_PATH = REPORT_ROOT / "local_runtime_readiness.json"
DEFAULT_JSON_OUTPUT = REPORT_ROOT / "local_model_asset_inventory.json"
DEFAULT_CSV_OUTPUT = REPORT_ROOT / "local_model_asset_inventory.csv"
DEFAULT_PROFILE_OUTPUT = REPORT_ROOT / "local_model_profile_suggestions.json"
DEFAULT_HTML_OUTPUT = REPORT_ROOT / "local_model_asset_inventory.html"

MODEL_EXTENSIONS = {".gguf", ".safetensors", ".bin", ".pt", ".pth", ".onnx", ".ckpt"}
TEXT_MODEL_HINTS = {
    "gemma",
    "dictalm",
    "dicta",
    "qwen",
    "mistral",
    "llama",
    "cydonia",
    "nemotron",
}
NON_TEXT_HINTS = {
    "flux",
    "ideogram",
    "sdxl",
    "animagine",
    "chatterbox",
    "clip",
    "siglip",
    "yourmt3",
    "mr-mt3",
    "mv-adapter",
}

RECOMMENDED_ALIASES = {
    "google/gemma-4-26B-A4B-it": ["gemma4:26b", "library/gemma4:26b"],
    "mistralai/Mistral-Small-3.2-24B-Instruct-2506": [
        "mistral-small-3.2-24b-instruct-2506",
        "mistral-small-3.2-24b",
        "unsloth/mistral-small-3.2-24b-instruct-2506-gguf",
    ],
    "google/gemma-4-12B-it": ["gemma4:12b", "gemma-4-12b"],
    "dicta-il/DictaLM-3.0-Nemotron-12B-Instruct": [
        "dictalm-3.0-nemotron-12b",
        "dictalm-3.0-12b",
    ],
    "dicta-il/DictaLM-3.0-24B-Thinking": ["dictalm-3.0-24b-thinking"],
    "Qwen/Qwen3-14B": ["qwen3-14b"],
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
    return f"{float(value):.3f} GiB"


def pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round(float(part) / float(total) * 100, 2)


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def cache_roots() -> list[dict[str, Path]]:
    home = Path.home()
    return [
        {"label": "wsl_huggingface_hub", "path": home / ".cache" / "huggingface" / "hub"},
        {"label": "wsl_ollama_models", "path": home / ".ollama" / "models"},
        {"label": "windows_ollama_models", "path": Path("/mnt/c/Users/dreamer/.ollama/models")},
        {
            "label": "windows_huggingface_hub",
            "path": Path("/mnt/c/Users/dreamer/.cache/huggingface/hub"),
        },
    ]


def classify_modality(name: str) -> str:
    lowered = name.lower()
    if any(hint in lowered for hint in NON_TEXT_HINTS):
        return "non_text_or_multimodal"
    if any(hint in lowered for hint in TEXT_MODEL_HINTS):
        return "text_or_text_capable"
    return "unknown"


def recommended_match(name: str, recommended: list[str]) -> dict[str, Any]:
    normalized = normalize_name(name)
    exact = []
    family = []
    for model in recommended:
        aliases = [model, *RECOMMENDED_ALIASES.get(model, [])]
        for alias in aliases:
            alias_norm = normalize_name(alias)
            if alias_norm and alias_norm in normalized:
                exact.append(model)
                break
        model_family = normalize_name(model.split("/")[-1].split("-")[0])
        if model_family and model_family in normalized:
            family.append(model)
    return {
        "exact_or_alias": sorted(set(exact)),
        "family_or_near": sorted(set(family) - set(exact)),
    }


def manifest_model_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root / "manifests")
    parts = list(relative.parts)
    tag = parts[-1]
    repo_parts = parts[:-1]
    if len(repo_parts) >= 3 and repo_parts[0] == "registry.ollama.ai":
        if repo_parts[1] == "library":
            return f"{repo_parts[2]}:{tag}"
        return f"{'/'.join(repo_parts[1:])}:{tag}"
    return f"{'/'.join(repo_parts)}:{tag}"


def blob_path_for_digest(root: Path, digest: str) -> Path:
    algorithm, value = digest.split(":", 1)
    if algorithm != "sha256":
        return root / "blobs" / digest.replace(":", "-")
    return root / "blobs" / f"sha256-{value}"


def parse_ollama_manifests(root: Path, recommended: list[str]) -> list[dict[str, Any]]:
    manifests = root / "manifests"
    rows = []
    if not manifests.exists():
        return rows
    for path in sorted(manifests.rglob("*")):
        if not path.is_file():
            continue
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        model_layers = [
            layer
            for layer in manifest.get("layers", [])
            if layer.get("mediaType") == "application/vnd.ollama.image.model"
        ]
        if not model_layers:
            continue
        layer = model_layers[0]
        model_name = manifest_model_name(path, root)
        blob_path = blob_path_for_digest(root, str(layer["digest"]))
        size = int(layer.get("size") or (blob_path.stat().st_size if blob_path.exists() else 0))
        details = {}
        api_name = model_name
        rows.append(
            {
                "asset_id": model_name,
                "source": "ollama_manifest",
                "runtime": "ollama",
                "path": str(path),
                "blob_path": str(blob_path),
                "exists": blob_path.exists(),
                "size_bytes": size,
                "size_gb": round(size / (1024**3), 3),
                "format": "gguf",
                "model_name": api_name,
                "family": details.get("family"),
                "parameter_size": details.get("parameter_size"),
                "quantization": details.get("quantization_level"),
                "context_length": details.get("context_length"),
                "modality": classify_modality(model_name),
                "recommended_match": recommended_match(model_name, recommended),
            }
        )
    return rows


def hf_repo_from_path(path: Path) -> str | None:
    for parent in [path, *path.parents]:
        name = parent.name
        if name.startswith("models--"):
            parts = name.removeprefix("models--").split("--")
            if len(parts) >= 2:
                return "/".join(parts[:2])
    return None


def scan_huggingface_files(root: Path, recommended: list[str]) -> list[dict[str, Any]]:
    rows = []
    if not root.exists():
        return rows
    for dirpath, _dirs, files in os.walk(root):
        for filename in files:
            path = Path(dirpath) / filename
            if path.suffix.lower() not in MODEL_EXTENSIONS:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            repo = hf_repo_from_path(path) or "unknown"
            asset_id = f"{repo}/{filename}"
            runtime = "llama.cpp" if path.suffix.lower() == ".gguf" else "transformers"
            rows.append(
                {
                    "asset_id": asset_id,
                    "source": "huggingface_cache",
                    "runtime": runtime,
                    "path": str(path),
                    "blob_path": "",
                    "exists": True,
                    "size_bytes": size,
                    "size_gb": round(size / (1024**3), 3),
                    "format": path.suffix.lower().lstrip("."),
                    "model_name": repo,
                    "family": None,
                    "parameter_size": None,
                    "quantization": infer_quantization(path.name),
                    "context_length": None,
                    "modality": classify_modality(asset_id),
                    "recommended_match": recommended_match(asset_id, recommended),
                }
            )
    return rows


def infer_quantization(name: str) -> str | None:
    match = re.search(r"(Q[0-9]_[A-Z_]+|Q[0-9]|UD-Q[0-9]_[A-Z_]+)", name, re.I)
    return match.group(1) if match else None


def windows_ollama_tags() -> dict[str, Any]:
    command = shutil.which("powershell.exe")
    if not command:
        return {"reachable": False, "error": "powershell.exe not available", "models": []}
    ps = (
        "try { "
        "Invoke-RestMethod -Uri http://127.0.0.1:11434/api/tags -TimeoutSec 2 "
        "| ConvertTo-Json -Depth 8 "
        "} catch { Write-Error $_.Exception.Message; exit 1 }"
    )
    try:
        completed = subprocess.run(
            [command, "-NoProfile", "-Command", ps],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception as exc:  # noqa: BLE001 - probe report.
        return {"reachable": False, "error": str(exc), "models": []}
    if completed.returncode != 0:
        return {
            "reachable": False,
            "error": completed.stderr.strip() or completed.stdout.strip(),
            "models": [],
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"reachable": False, "error": str(exc), "models": []}
    return {"reachable": True, "error": "", "models": payload.get("models", [])}


def wsl_ollama_reachability() -> dict[str, Any]:
    for url in ["http://127.0.0.1:11434/api/tags", "http://localhost:11434/api/tags"]:
        try:
            with request.urlopen(url, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return {"reachable": True, "url": url, "models": payload.get("models", [])}
        except (OSError, error.URLError, json.JSONDecodeError):
            continue
    return {"reachable": False, "url": None, "models": []}


def enrich_ollama_with_tags(
    assets: list[dict[str, Any]],
    tags: dict[str, Any],
    recommended: list[str],
) -> list[dict[str, Any]]:
    by_name = {str(model.get("name")): model for model in tags.get("models", [])}
    for asset in assets:
        if asset["source"] != "ollama_manifest":
            continue
        tag = by_name.get(str(asset["model_name"]))
        if not tag:
            continue
        details = tag.get("details") or {}
        asset["size_bytes"] = int(tag.get("size") or asset["size_bytes"])
        asset["size_gb"] = round(asset["size_bytes"] / (1024**3), 3)
        asset["family"] = details.get("family")
        asset["parameter_size"] = details.get("parameter_size")
        asset["quantization"] = details.get("quantization_level")
        asset["context_length"] = details.get("context_length")
        asset["capabilities"] = tag.get("capabilities", [])
        asset["digest"] = tag.get("digest")
        asset["recommended_match"] = recommended_match(asset["model_name"], recommended)
    return assets


def build_assets(
    recommended: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    assets = []
    tags = windows_ollama_tags()
    wsl = wsl_ollama_reachability()
    for root in cache_roots():
        path = root["path"]
        if "ollama" in root["label"]:
            for row in parse_ollama_manifests(path, recommended):
                row["cache_root_label"] = root["label"]
                assets.append(row)
        if "huggingface" in root["label"]:
            for row in scan_huggingface_files(path, recommended):
                row["cache_root_label"] = root["label"]
                assets.append(row)
    enrich_ollama_with_tags(assets, tags, recommended)
    return assets, tags, wsl


def recommended_coverage(
    assets: list[dict[str, Any]],
    recommended: list[str],
) -> list[dict[str, Any]]:
    rows = []
    for model in recommended:
        exact = []
        near = []
        for asset in assets:
            match = asset["recommended_match"]
            if model in match["exact_or_alias"]:
                exact.append(asset)
            elif model in match["family_or_near"]:
                near.append(asset)
        rows.append(
            {
                "model": model,
                "exact_or_alias_asset_count": len(exact),
                "near_family_asset_count": len(near),
                "best_asset": best_asset_name(exact or near),
                "status": coverage_status(exact, near),
            }
        )
    return rows


def best_asset_name(assets: list[dict[str, Any]]) -> str | None:
    if not assets:
        return None
    asset = max(assets, key=lambda item: float(item["size_gb"]))
    return str(asset["model_name"] or asset["asset_id"])


def coverage_status(exact: list[dict[str, Any]], near: list[dict[str, Any]]) -> str:
    if exact:
        return "local_asset_present"
    if near:
        return "near_family_asset_present"
    return "missing_local_asset"


def suggested_profiles(
    assets: list[dict[str, Any]],
    *,
    wsl_ollama: dict[str, Any],
    windows_ollama: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for asset in sorted(assets, key=lambda item: float(item["size_gb"]), reverse=True):
        matches = asset["recommended_match"]["exact_or_alias"]
        if not matches:
            continue
        if asset["runtime"] == "ollama":
            wsl_reachable = bool(wsl_ollama["reachable"])
            windows_reachable = bool(windows_ollama["reachable"])
            if wsl_reachable:
                status = "ready_via_wsl_http"
                blocker = ""
            elif windows_reachable:
                status = "ready_via_windows_ollama_bridge"
                blocker = ""
            else:
                status = "blocked_until_ollama_api_is_reachable"
                blocker = "Ollama assets exist, but no reachable Ollama API was detected."
            rows.append(
                {
                    "profile_id": f"ollama-{normalize_name(asset['model_name'])}",
                    "recommended_model": matches[0],
                    "adapter": "ollama",
                    "model": asset["model_name"],
                    "base_url": "http://127.0.0.1:11434",
                    "status": status,
                    "blocker": blocker,
                    "bridge_command": (
                        "python scripts/run_windows_ollama_benchmark_suite.py "
                        f"--model {asset['model_name']} --limit 1"
                    ),
                    "asset_size_gb": asset["size_gb"],
                }
            )
        elif asset["runtime"] == "llama.cpp":
            rows.append(
                {
                    "profile_id": f"llamacpp-{normalize_name(asset['model_name'])}",
                    "recommended_model": matches[0],
                    "adapter": "llama.cpp",
                    "model": asset["model_name"],
                    "base_url": "http://127.0.0.1:8080/v1",
                    "model_path": asset["path"],
                    "managed_process": True,
                    "status": "blocked_until_llama_server_binary_exists",
                    "blocker": "No llama-server binary is currently detected in WSL runtime audit.",
                    "asset_size_gb": asset["size_gb"],
                }
            )
    return rows


def summarize(
    *,
    assets: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    windows_ollama: dict[str, Any],
    wsl_ollama: dict[str, Any],
) -> dict[str, Any]:
    text_assets = [row for row in assets if row["modality"] == "text_or_text_capable"]
    exact_models = {
        model
        for row in coverage
        for model in [row["model"]]
        if row["status"] == "local_asset_present"
    }
    source_counts = Counter(str(row["source"]) for row in assets)
    runtime_counts = Counter(str(row["runtime"]) for row in assets)
    status_counts = Counter(str(row["status"]) for row in coverage)
    profile_status_counts = Counter(str(row["status"]) for row in profiles)
    ready_statuses = {"ready_via_wsl_http", "ready_via_windows_ollama_bridge"}
    return {
        "asset_count": len(assets),
        "text_or_text_capable_asset_count": len(text_assets),
        "total_asset_gb": round(sum(float(row["size_gb"]) for row in assets), 3),
        "text_asset_gb": round(sum(float(row["size_gb"]) for row in text_assets), 3),
        "recommended_model_count": len(coverage),
        "recommended_models_with_local_assets": len(exact_models),
        "recommended_asset_coverage_pct": pct(len(exact_models), len(coverage)),
        "suggested_profile_count": len(profiles),
        "ready_profile_count": sum(row["status"] in ready_statuses for row in profiles),
        "windows_ollama_reachable": bool(windows_ollama["reachable"]),
        "windows_ollama_model_count": len(windows_ollama.get("models", [])),
        "wsl_ollama_reachable": bool(wsl_ollama["reachable"]),
        "source_counts": dict(source_counts.most_common()),
        "runtime_counts": dict(runtime_counts.most_common()),
        "coverage_status_counts": dict(status_counts.most_common()),
        "profile_status_counts": dict(profile_status_counts.most_common()),
    }


def build_report(model_data_path: Path, runtime_path: Path) -> dict[str, Any]:
    model_data = load_json(model_data_path)
    runtime = load_json(runtime_path)
    recommended = [str(model) for model in model_data["recommended_bakeoff_models"]]
    assets, windows_ollama, wsl_ollama = build_assets(recommended)
    coverage = recommended_coverage(assets, recommended)
    profiles = suggested_profiles(
        assets,
        wsl_ollama=wsl_ollama,
        windows_ollama=windows_ollama,
    )
    return {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "status": "generated local model asset inventory; no inference run",
        "source_paths": {
            "model_data": "docs/research/local_translation_model_data.json",
            "runtime_readiness": "reports/research/local_runtime_readiness.json",
        },
        "runtime_context": {
            "runtime_summary": runtime["summary"],
            "windows_ollama": windows_ollama,
            "wsl_ollama": wsl_ollama,
        },
        "summary": summarize(
            assets=assets,
            coverage=coverage,
            profiles=profiles,
            windows_ollama=windows_ollama,
            wsl_ollama=wsl_ollama,
        ),
        "recommended_coverage": coverage,
        "assets": sorted(assets, key=lambda item: float(item["size_gb"]), reverse=True),
        "profile_suggestions": profiles,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "asset_id",
        "source",
        "runtime",
        "cache_root_label",
        "model_name",
        "size_gb",
        "format",
        "parameter_size",
        "quantization",
        "context_length",
        "modality",
        "exact_or_alias_matches",
        "near_family_matches",
        "path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{field: row.get(field, "") for field in fields},
                    "exact_or_alias_matches": ";".join(row["recommended_match"]["exact_or_alias"]),
                    "near_family_matches": ";".join(row["recommended_match"]["family_or_near"]),
                }
            )


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
    left = 330
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
    asset_rows = [
        [
            row["model_name"],
            row["source"],
            row["runtime"],
            row["size_gb"],
            row.get("parameter_size") or "",
            row.get("quantization") or "",
            ", ".join(row["recommended_match"]["exact_or_alias"]),
        ]
        for row in report["assets"][:30]
    ]
    coverage_rows = [
        [
            row["model"],
            row["status"],
            row["exact_or_alias_asset_count"],
            row["near_family_asset_count"],
            row["best_asset"] or "",
        ]
        for row in report["recommended_coverage"]
    ]
    profile_rows = [
        [
            row["profile_id"],
            row["recommended_model"],
            row["adapter"],
            row["model"],
            row["status"],
            row["blocker"],
        ]
        for row in report["profile_suggestions"]
    ]
    size_rows = [
        {"asset": row["model_name"][:60], "size_gb": row["size_gb"]}
        for row in report["assets"][:15]
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AlephTav Local Model Asset Inventory</title>
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
    <h1>AlephTav Local Model Asset Inventory</h1>
    <p class="lede">
      Local model-cache inventory for the Hebrew-to-English benchmark program.
      It distinguishes actual cached assets, recommended-model coverage,
      Windows Ollama availability, WSL benchmark reachability, and profile
      suggestions for real local inference.
    </p>
    <p class="meta">Generated {esc(report["generated_on"])}.</p>
  </header>
  <main>
    <section>
      <h2>Inventory Summary</h2>
      {
        metric_cards(
            [
                ("Assets", fmt_int(summary["asset_count"]), "Model-like local files or manifests."),
                (
                    "Text assets",
                    fmt_int(summary["text_or_text_capable_asset_count"]),
                    f'''{fmt_gb(summary["text_asset_gb"])} text-capable assets.''',
                ),
                (
                    "Coverage",
                    f'''{summary["recommended_models_with_local_assets"]}/'''
                    f'''{summary["recommended_model_count"]}''',
                    "Recommended bake-off models with local exact/alias assets.",
                ),
                (
                    "Profiles ready",
                    fmt_int(summary["ready_profile_count"]),
                    "Suggested profiles runnable from the current WSL runner.",
                ),
            ]
        )
    }
      <div class="warning">
        Windows Ollama is reachable from Windows, but WSL reachability is tested
        separately because the benchmark runner runs from WSL.
      </div>
      <div class="chart">{
        svg_horizontal_bars(
            size_rows,
            label_key="asset",
            value_key="size_gb",
            aria_label="Largest local model assets",
            color="#7c5b2f",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["coverage_status_counts"], "status"),
            label_key="status",
            value_key="count",
            aria_label="Recommended model local asset coverage",
            color="#2f6f73",
        )
    }</div>
      <div class="chart">{
        svg_horizontal_bars(
            rows_from_counter(summary["runtime_counts"], "runtime"),
            label_key="runtime",
            value_key="count",
            aria_label="Local model assets by runtime",
            color="#2f6f73",
        )
    }</div>
    </section>

    <section>
      <h2>Recommended Model Coverage</h2>
      {
        table(
            ["Recommended model", "Status", "Exact assets", "Near assets", "Best local asset"],
            coverage_rows,
        )
    }
    </section>

    <section>
      <h2>Profile Suggestions</h2>
      {
        table(
            ["Profile", "Recommended model", "Adapter", "Model", "Status", "Blocker"],
            profile_rows,
        )
    }
    </section>

    <section>
      <h2>Largest Assets</h2>
      {
        table(
            [
                "Model",
                "Source",
                "Runtime",
                "GiB",
                "Parameters",
                "Quant",
                "Recommended match",
            ],
            asset_rows,
        )
    }
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate local model asset inventory.")
    parser.add_argument("--model-data", type=Path, default=MODEL_DATA_PATH)
    parser.add_argument("--runtime-readiness", type=Path, default=RUNTIME_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--profile-output", type=Path, default=DEFAULT_PROFILE_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(args.model_data, args.runtime_readiness)
    write_json(args.json_output, report)
    write_csv(args.csv_output, report["assets"])
    write_json(
        args.profile_output,
        {
            "generated_on": report["generated_on"],
            "status": "generated profile suggestions; review before use",
            "profiles": report["profile_suggestions"],
        },
    )
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_html(report), encoding="utf-8")
    print(f"Wrote {args.json_output}")
    print(f"Wrote {args.csv_output}")
    print(f"Wrote {args.profile_output}")
    print(f"Wrote {args.html_output}")


if __name__ == "__main__":
    main()
