from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / ".run"
STATE_PATH = RUN_DIR / "rebuild-state.json"


@dataclass(frozen=True)
class Evaluation:
    mode: str
    signature: str
    tracked_files: list[Path]
    output_files: list[Path]
    is_current: bool
    reason: str


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iter_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
            continue
        if path.is_dir():
            files.extend(sorted(item for item in path.rglob("*") if item.is_file()))
    return sorted({item.resolve() for item in files})


def _tracked_roots(mode: str) -> list[Path]:
    common = [
        ROOT / "app" / "core" / "config.py",
        ROOT / "app" / "services" / "audit_service.py",
        ROOT / "app" / "services" / "concordance_service.py",
        ROOT / "app" / "services" / "ingest_service.py",
        ROOT / "app" / "services" / "registry_service.py",
        ROOT / "app" / "services" / "report_service.py",
        ROOT / "app" / "services" / "review_service.py",
    ]
    if mode == "fixture":
        return common + [
            ROOT / "scripts" / "bootstrap_fixture_repo.py",
            ROOT / "tests" / "support.py",
        ]
    return common + [
        ROOT / "app" / "services" / "full_psalm_import_service.py",
        ROOT / "scripts" / "build_indexes.py",
        ROOT / "scripts" / "import_psalms.py",
        ROOT / "scripts" / "seed_project.py",
        ROOT / "scripts" / "validate_content.py",
        ROOT / "data" / "raw",
        ROOT / "schemas",
    ]


def _psalm_output_files() -> list[Path]:
    psalms_dir = ROOT / "content" / "psalms"
    preferred = [
        psalms_dir / "ps001" / "ps001.meta.json",
        psalms_dir / "ps001" / "ps001.v001.a.json",
    ]
    existing = [path for path in preferred if path.exists()]
    if existing:
        return existing
    return sorted(psalms_dir.glob("ps*/*.json"))[:2]


def _output_files(mode: str) -> list[Path]:
    outputs = [
        ROOT / "content" / "project.json",
        ROOT / "data" / "derived" / "indexes" / "workbench.sqlite3",
        *(_psalm_output_files()),
    ]
    if mode == "fixture":
        vector_index = ROOT / "data" / "derived" / "indexes" / "vector" / "visual_flow_index.json"
        outputs.append(vector_index)
    return outputs


def _signature_for(files: list[Path]) -> str:
    manifest: list[dict[str, Any]] = []
    for path in files:
        stat = path.stat()
        manifest.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
    payload = json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return sha256(payload).hexdigest()


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {"version": 1, "states": {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "states": {}}


def _write_state(payload: dict[str, Any]) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _outputs_exist(outputs: list[Path]) -> tuple[bool, str]:
    missing = [str(path.relative_to(ROOT)).replace("\\", "/") for path in outputs if not path.exists()]
    if missing:
        return False, f"missing outputs: {', '.join(missing)}"
    return True, "outputs present"


def _outputs_are_fresh_enough(tracked_files: list[Path], output_files: list[Path]) -> bool:
    if not tracked_files or not output_files:
        return False
    newest_input = max(path.stat().st_mtime_ns for path in tracked_files)
    oldest_output = min(path.stat().st_mtime_ns for path in output_files)
    return oldest_output >= newest_input


def evaluate(mode: str) -> Evaluation:
    tracked_files = _iter_files(_tracked_roots(mode))
    output_files = _output_files(mode)
    signature = _signature_for(tracked_files)
    outputs_ok, outputs_reason = _outputs_exist(output_files)
    if not outputs_ok:
        return Evaluation(mode, signature, tracked_files, output_files, False, outputs_reason)

    state = _load_state()
    stored = state.get("states", {}).get(mode)
    if stored and stored.get("signature") == signature:
        return Evaluation(mode, signature, tracked_files, output_files, True, f"tracked rebuild state is current for {mode}")

    if _outputs_are_fresh_enough(tracked_files, output_files):
        return Evaluation(mode, signature, tracked_files, output_files, True, f"existing outputs are newer than tracked inputs for {mode}")

    return Evaluation(mode, signature, tracked_files, output_files, False, f"tracked inputs changed for {mode}")


def cmd_check(mode: str) -> int:
    evaluation = evaluate(mode)
    print(evaluation.reason)
    return 0 if evaluation.is_current else 1


def cmd_mark(mode: str) -> int:
    evaluation = evaluate(mode)
    outputs_ok, outputs_reason = _outputs_exist(evaluation.output_files)
    if not outputs_ok:
        print(outputs_reason)
        return 1

    state = _load_state()
    state.setdefault("version", 1)
    states = state.setdefault("states", {})
    states[mode] = {
        "signature": evaluation.signature,
        "tracked_file_count": len(evaluation.tracked_files),
        "output_files": [str(path.relative_to(ROOT)).replace("\\", "/") for path in evaluation.output_files],
        "recorded_at": _now_iso(),
    }
    _write_state(state)
    print(f"recorded rebuild state for {mode}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Track whether setup rebuild outputs are current.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("check", "mark"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--mode", choices=("full", "fixture"), required=True)

    args = parser.parse_args()
    if args.command == "check":
        return cmd_check(args.mode)
    return cmd_mark(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())