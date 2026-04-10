from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.license_rules import evaluate_manifest


def deterministic_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(deterministic_json(payload), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(payload: Any) -> str:
    return hashlib.sha256(deterministic_json(payload).encode("utf-8")).hexdigest()


def project_template() -> dict[str, Any]:
    return {
        "project_id": "proj.main",
        "title": "Psalms Copyleft Workbench",
        "output_text_license": "CC BY-SA 4.0",
        "code_license": "MIT",
        "model_backend": "local-only",
        "default_model_profile": "demo-local",
        "local_model_profiles": [
            {
                "model_profile_id": "demo-local",
                "adapter": "openai-compatible",
                "base_url": "http://127.0.0.1:11434/v1",
                "model": "local-demo",
                "temperature": 0.0,
                "max_tokens": 384,
                "timeout_seconds": 30,
            }
        ],
        "allowed_sources": ["uxlc", "oshb", "macula", "sefaria"],
        "style_profiles": [
            {
                "style_profile_id": "formal_liturgical",
                "literalness": 0.7,
                "lyric_freedom": 0.4,
                "target_syllables": 9,
                "rhyme_mode": "off",
                "register": "liturgical",
                "parallelism_priority": "high",
            },
            {
                "style_profile_id": "study_literal",
                "literalness": 0.95,
                "lyric_freedom": 0.1,
                "target_syllables": 0,
                "rhyme_mode": "off",
                "register": "formal",
                "parallelism_priority": "high",
            },
            {
                "style_profile_id": "metered_common_meter",
                "literalness": 0.55,
                "lyric_freedom": 0.7,
                "target_syllables": 8,
                "rhyme_mode": "off",
                "register": "literary",
                "parallelism_priority": "high",
            },
        ],
        "divine_name_policy": "preserve source distinctions",
        "review_policy": {
            "canonical_required_approvals": 2,
            "alternate_required_approvals": 1,
            "release_required_role": "release reviewer",
        },
        "release_channel": "local-dev",
        "source_manifests": [],
    }


def manifest_template() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "uxlc",
            "name": "UXLC/WLC Derived Hebrew",
            "version": "fixture-2026.04",
            "license": "Public Domain",
            "upstream_url": "https://tanach.us/",
            "imported_at": "2026-04-09T00:00:00Z",
            "import_hash": "fixture-uxlc",
            "allowed_for_generation": True,
            "allowed_for_display": True,
            "allowed_for_export": True,
            "notes": "Canonical Hebrew source",
        },
        {
            "source_id": "oshb",
            "name": "Open Scriptures Hebrew Bible",
            "version": "fixture-2026.04",
            "license": "Open Scriptural Data",
            "upstream_url": "https://github.com/openscriptures/morphhb",
            "imported_at": "2026-04-09T00:00:00Z",
            "import_hash": "fixture-oshb",
            "allowed_for_generation": False,
            "allowed_for_display": True,
            "allowed_for_export": True,
            "notes": "Morphology and readable morphology only",
        },
        {
            "source_id": "macula",
            "name": "MACULA Hebrew",
            "version": "fixture-2026.04",
            "license": "CC BY 4.0",
            "upstream_url": "https://github.com/Clear-Bible/macula-hebrew",
            "imported_at": "2026-04-09T00:00:00Z",
            "import_hash": "fixture-macula",
            "allowed_for_generation": False,
            "allowed_for_display": True,
            "allowed_for_export": True,
            "notes": "Syntax and semantic enrichment",
        },
        {
            "source_id": "sefaria",
            "name": "Sefaria Witness Snapshot",
            "version": "fixture-2026.04",
            "license": "Custom-Restricted-Witness",
            "upstream_url": "https://developers.sefaria.org/",
            "imported_at": "2026-04-09T00:00:00Z",
            "import_hash": "fixture-sefaria",
            "allowed_for_generation": False,
            "allowed_for_display": True,
            "allowed_for_export": False,
            "notes": "Witness-only and version-pinned",
        },
    ]


def bootstrap_project() -> dict[str, Any]:
    settings = get_settings()
    project = project_template()
    project["source_manifests"] = manifest_template()
    write_json(settings.project_file, project)
    for entry in project["source_manifests"]:
        write_json(settings.raw_dir / entry["source_id"] / "manifest.json", entry)
    return project


def load_project() -> dict[str, Any]:
    settings = get_settings()
    if not settings.project_file.exists():
        return bootstrap_project()
    return read_json(settings.project_file)


def save_project(project: dict[str, Any]) -> None:
    settings = get_settings()
    write_json(settings.project_file, project)
    for entry in project.get("source_manifests", []):
        write_json(settings.raw_dir / entry["source_id"] / "manifest.json", entry)


def psalm_dir(psalm_id: str) -> Path:
    return get_settings().psalms_dir / psalm_id


def list_psalm_ids() -> list[str]:
    return sorted(path.name for path in get_settings().psalms_dir.iterdir() if path.is_dir())


def list_unit_paths() -> list[Path]:
    return sorted(get_settings().psalms_dir.glob("ps*/ps*.json"))


def list_units() -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for path in list_unit_paths():
        if path.name.endswith(".meta.json"):
            continue
        units.append(read_json(path))
    return units


def load_psalm(psalm_id: str) -> dict[str, Any]:
    meta = psalm_dir(psalm_id) / f"{psalm_id}.meta.json"
    if not meta.exists():
        raise NotFoundError(f"Psalm not found: {psalm_id}")
    payload = read_json(meta)
    payload["units"] = [load_unit(unit_id) for unit_id in payload.get("unit_ids", [])]
    return payload


def unit_path(unit_id: str) -> Path:
    psalm_id = unit_id.split(".")[0]
    return psalm_dir(psalm_id) / f"{unit_id}.json"


def load_unit(unit_id: str) -> dict[str, Any]:
    path = unit_path(unit_id)
    if not path.exists():
        raise NotFoundError(f"Unit not found: {unit_id}")
    return read_json(path)


def save_unit(unit: dict[str, Any]) -> None:
    write_json(unit_path(unit["unit_id"]), unit)


def update_unit(unit_id: str, mutator) -> dict[str, Any]:
    unit = load_unit(unit_id)
    before = deepcopy(unit)
    updated = mutator(unit)
    if updated is None:
        updated = unit
    save_unit(updated)
    return before, updated


def audit_licenses() -> dict[str, Any]:
    manifests = []
    for path in sorted(get_settings().raw_dir.glob("*/manifest.json")):
        manifests.append(read_json(path))
    evaluations = [evaluate_manifest(entry) for entry in manifests]
    status = "ok" if all(item["allowed"] for item in evaluations) else "error"
    return {"status": status, "evaluations": evaluations}
