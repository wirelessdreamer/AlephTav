from __future__ import annotations

import atexit
import json
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO
from urllib import error, request
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.errors import GenerationError


@dataclass
class ManagedRuntime:
    runtime_id: str
    process: subprocess.Popen[str]
    log_path: Path
    log_handle: TextIO


_LOCK = threading.RLock()
_RUNTIMES: dict[str, ManagedRuntime] = {}
_ATEXIT_REGISTERED = False


def _runtime_id(profile: dict[str, Any]) -> str:
    return str(profile.get("model_profile_id") or profile.get("model") or "llama.cpp")


def is_managed_profile(profile: dict[str, Any]) -> bool:
    return str(profile.get("adapter", "")) == "llama.cpp" and bool(profile.get("managed_process"))


def _base_url(profile: dict[str, Any]) -> str:
    return str(profile.get("base_url", "")).rstrip("/")


def _health_url(profile: dict[str, Any]) -> str:
    base_url = _base_url(profile)
    if base_url.endswith("/v1"):
        return f"{base_url}/health"
    return f"{base_url}/v1/health"


def _parse_host_port(profile: dict[str, Any]) -> tuple[str, int]:
    parsed = urlparse(_base_url(profile))
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8080
    return host, port


def _resolve_binary(profile: dict[str, Any]) -> str:
    settings = get_settings()
    configured = str(profile.get("server_binary_path", "") or "").strip()
    candidates: list[Path] = []

    if configured:
        configured_path = Path(configured)
        if configured_path.is_absolute():
            candidates.append(configured_path)
        else:
            candidates.append(settings.root_dir / configured_path)
            resolved = shutil.which(configured)
            if resolved:
                return resolved

    for relative in (
        "data/runtime/llama.cpp/llama-server",
        "data/runtime/llama.cpp/llama-server.exe",
        "vendor/llama.cpp/llama-server",
        "vendor/llama.cpp/llama-server.exe",
        "bin/llama-server",
        "bin/llama-server.exe",
    ):
        candidates.append(settings.root_dir / relative)

    resolved = shutil.which("llama-server") or shutil.which("llama-server.exe")
    if resolved:
        return resolved

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    raise GenerationError(
        "Managed llama.cpp runtime is enabled, but no llama-server binary was found. "
        "Set server_binary_path or bundle llama-server into the workspace."
    )


def _resolve_model_args(profile: dict[str, Any]) -> list[str]:
    settings = get_settings()
    model_path = str(profile.get("model_path", "") or "").strip()
    hf_model = str(profile.get("hf_model", "") or "").strip()

    if model_path:
        candidate = Path(model_path)
        if not candidate.is_absolute():
            candidate = settings.root_dir / candidate
        return ["-m", str(candidate)]
    if hf_model:
        return ["-hf", hf_model]
    raise GenerationError(
        "Managed llama.cpp runtime requires either model_path or hf_model in the model profile."
    )


def _command(profile: dict[str, Any]) -> list[str]:
    host, port = _parse_host_port(profile)
    command = [_resolve_binary(profile), *_resolve_model_args(profile), "--host", host, "--port", str(port)]

    if "context_size" in profile:
        command.extend(["-c", str(int(profile["context_size"]))])
    if "gpu_layers" in profile:
        command.extend(["-ngl", str(int(profile["gpu_layers"]))])
    if "batch_size" in profile:
        command.extend(["-ub", str(int(profile["batch_size"]))])
    if "parallel_slots" in profile:
        command.extend(["-np", str(int(profile["parallel_slots"]))])
    if "threads" in profile:
        command.extend(["-t", str(int(profile["threads"]))])
    if profile.get("embedding"):
        command.append("--embedding")
    return command


def _runtime_log_path(profile: dict[str, Any]) -> Path:
    settings = get_settings()
    log_dir = settings.caches_dir / "llama.cpp"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{_runtime_id(profile)}.log"


def _start_runtime_locked(profile: dict[str, Any]) -> ManagedRuntime:
    log_path = _runtime_log_path(profile)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n=== starting managed llama.cpp runtime for {_runtime_id(profile)} ===\n")
        handle.write(" ".join(_command(profile)) + "\n")

    log_handle = log_path.open("a", encoding="utf-8")
    process = subprocess.Popen(
        _command(profile),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return ManagedRuntime(runtime_id=_runtime_id(profile), process=process, log_path=log_path, log_handle=log_handle)


def _health_ok(profile: dict[str, Any], timeout_seconds: float = 1.0) -> bool:
    try:
        with request.urlopen(_health_url(profile), timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, json.JSONDecodeError):
        return False
    return payload.get("status") == "ok"


def ensure_runtime(profile: dict[str, Any]) -> None:
    if not is_managed_profile(profile):
        return

    _register_atexit_once()
    runtime_id = _runtime_id(profile)
    with _LOCK:
        runtime = _RUNTIMES.get(runtime_id)
        if runtime is not None and runtime.process.poll() is None and _health_ok(profile):
            return
        if runtime is not None:
            _stop_runtime_locked(runtime_id)
        _RUNTIMES[runtime_id] = _start_runtime_locked(profile)

    deadline = time.time() + float(profile.get("runtime_start_timeout_seconds", 45))
    while time.time() < deadline:
        with _LOCK:
            runtime = _RUNTIMES.get(runtime_id)
            if runtime is None:
                break
            return_code = runtime.process.poll()
        if return_code is not None:
            raise GenerationError(
                f"Managed llama.cpp runtime exited before becoming healthy for {runtime_id}. "
                f"Check {_runtime_log_path(profile)}"
            )
        if _health_ok(profile):
            return
        time.sleep(0.25)

    raise GenerationError(
        f"Managed llama.cpp runtime did not become healthy in time for {runtime_id}. "
        f"Check {_runtime_log_path(profile)}"
    )


def _stop_runtime_locked(runtime_id: str) -> None:
    runtime = _RUNTIMES.pop(runtime_id, None)
    if runtime is None:
        return
    if runtime.process.poll() is not None:
        runtime.log_handle.close()
        return
    runtime.process.terminate()
    try:
        runtime.process.wait(timeout=5)
    except subprocess.TimeoutExpired:  # pragma: no cover
        runtime.process.kill()
        runtime.process.wait(timeout=5)
    runtime.log_handle.close()


def shutdown_all() -> None:
    with _LOCK:
        runtime_ids = list(_RUNTIMES.keys())
        for runtime_id in runtime_ids:
            _stop_runtime_locked(runtime_id)


def _register_atexit_once() -> None:
    global _ATEXIT_REGISTERED
    if _ATEXIT_REGISTERED:
        return
    atexit.register(shutdown_all)
    _ATEXIT_REGISTERED = True
