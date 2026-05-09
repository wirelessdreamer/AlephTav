from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import re
from typing import Any
import zipfile

from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.license_rules import evaluate_manifest

PUBLIC_DOMAIN_WITNESS_SOURCES: tuple[dict[str, str], ...] = (
    {"source_id": "kjv", "versionTitle": "King James Version", "zip_name": "eng-kjv2006_vpl.zip"},
    {"source_id": "asv", "versionTitle": "American Standard Version", "zip_name": "eng-asv_vpl.zip"},
    {"source_id": "web", "versionTitle": "World English Bible", "zip_name": "engwebp_vpl.zip"},
)
PSALM_REF_RE = re.compile(r"^Psalm\s+(\d+):(\d+)[a-z]?$", re.IGNORECASE)
PSALM_VPL_RE = re.compile(r"^PSA\s+(\d+):(\d+)\s+(.+)$")


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
        "default_composer_model_profile": "composer-local",
        "local_model_profiles": [
            {
                "model_profile_id": "demo-local",
                "adapter": "openai-compatible",
                "base_url": "http://127.0.0.1:11434/v1",
                "model": "local-demo",
                "temperature": 0.0,
                "max_tokens": 384,
                "timeout_seconds": 30,
            },
            {
                "model_profile_id": "composer-local",
                "adapter": "llama.cpp",
                "base_url": "http://127.0.0.1:8080/v1",
                "model": "local-composer",
                "managed_process": True,
                "server_binary_path": "llama-server",
                "model_path": "models/local-composer.gguf",
                "temperature": 0.2,
                "max_tokens": 768,
                "timeout_seconds": 45,
                "runtime_start_timeout_seconds": 45,
                "response_format_mode": "json_schema",
                "response_format_fallback": "json_object",
                "context_size": 8192,
                "parallel_slots": 2,
                "batch_size": 1024,
                "top_p": 0.9,
                "min_p": 0.05,
                "repeat_penalty": 1.05,
            }
        ],
        "allowed_sources": ["uxlc", "oshb", "macula", "lxx", "kjv", "asv", "web", "sefaria"],
        "style_profiles": [
            {
                "style_profile_id": "formal_liturgical",
                "literalness": 0.7,
                "lyric_freedom": 0.4,
                "target_syllables": 9,
                "rhyme_mode": "off",
                "register": "liturgical",
                "parallelism_priority": "high",
                "source_anchor_mode": "hebrew_imagery",
                "metaphor_mode": "source_metaphor_first",
                "imagery_preservation": 0.9,
                "idiom_modernity": 0.28,
                "emotional_directness": 0.38,
                "faith_posture": "confessional",
                "divine_name_rendering": "preserve_distinction",
            },
            {
                "style_profile_id": "study_literal",
                "literalness": 0.95,
                "lyric_freedom": 0.1,
                "target_syllables": 0,
                "rhyme_mode": "off",
                "register": "formal",
                "parallelism_priority": "high",
                "source_anchor_mode": "token_literal",
                "metaphor_mode": "minimal",
                "imagery_preservation": 1.0,
                "idiom_modernity": 0.12,
                "emotional_directness": 0.18,
                "faith_posture": "observational",
                "divine_name_rendering": "preserve_distinction",
            },
            {
                "style_profile_id": "dynamic_equivalent",
                "literalness": 0.74,
                "lyric_freedom": 0.48,
                "target_syllables": 0,
                "rhyme_mode": "off",
                "register": "contemporary literary",
                "parallelism_priority": "high",
                "source_anchor_mode": "scene_preserving",
                "metaphor_mode": "source_metaphor_first",
                "imagery_preservation": 0.82,
                "idiom_modernity": 0.68,
                "emotional_directness": 0.58,
                "faith_posture": "observational",
                "divine_name_rendering": "contemporary_title",
            },
            {
                "style_profile_id": "metered_common_meter",
                "literalness": 0.55,
                "lyric_freedom": 0.7,
                "target_syllables": 8,
                "rhyme_mode": "off",
                "register": "literary",
                "parallelism_priority": "high",
                "source_anchor_mode": "scene_preserving",
                "metaphor_mode": "source_metaphor_first",
                "imagery_preservation": 0.76,
                "idiom_modernity": 0.54,
                "emotional_directness": 0.66,
                "faith_posture": "observational",
                "divine_name_rendering": "contemporary_title",
            },
            {
                "style_profile_id": "performative_free",
                "literalness": 0.62,
                "lyric_freedom": 0.86,
                "target_syllables": 8,
                "rhyme_mode": "off",
                "register": "contemporary performative",
                "parallelism_priority": "high",
                "source_anchor_mode": "hebrew_imagery",
                "metaphor_mode": "symbolic_equivalent",
                "imagery_preservation": 0.84,
                "idiom_modernity": 0.86,
                "emotional_directness": 0.9,
                "faith_posture": "observational",
                "divine_name_rendering": "contemporary_title",
            },
            {
                "style_profile_id": "source_imagist",
                "literalness": 0.78,
                "lyric_freedom": 0.52,
                "target_syllables": 0,
                "rhyme_mode": "off",
                "register": "lean poetic",
                "parallelism_priority": "high",
                "source_anchor_mode": "hebrew_imagery",
                "metaphor_mode": "source_metaphor_first",
                "imagery_preservation": 0.96,
                "idiom_modernity": 0.72,
                "emotional_directness": 0.72,
                "faith_posture": "observational",
                "divine_name_rendering": "preserve_distinction",
            },
            {
                "style_profile_id": "doubter_lament",
                "literalness": 0.64,
                "lyric_freedom": 0.82,
                "target_syllables": 8,
                "rhyme_mode": "off",
                "register": "contemporary intimate",
                "parallelism_priority": "high",
                "source_anchor_mode": "hebrew_imagery",
                "metaphor_mode": "symbolic_equivalent",
                "imagery_preservation": 0.92,
                "idiom_modernity": 0.88,
                "emotional_directness": 0.94,
                "faith_posture": "contested",
                "divine_name_rendering": "flexible_address",
            },
        ],
        "divine_name_policy": "preserve source distinctions",
        "review_policy": {
            "canonical_required_approvals": 2,
            "alternate_required_approvals": 1,
            "release_required_role": "release reviewer",
            "reviewer_roles": [
                "lexical reviewer",
                "Hebrew reviewer",
                "alignment reviewer",
                "lyric reviewer",
                "theology reviewer",
                "release reviewer",
            ],
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
            "source_language": "he",
            "basis_role": "canonical_source",
            "version_pinned": True,
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
            "source_language": "he",
            "basis_role": "lexical_enrichment",
            "version_pinned": True,
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
            "source_language": "he",
            "basis_role": "lexical_enrichment",
            "version_pinned": True,
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
            "source_id": "lxx",
            "name": "Septuagint Greek (MACULA-aligned witness)",
            "version": "fixture-2026.04",
            "source_language": "grc",
            "basis_role": "alternate_ideation_source",
            "version_pinned": True,
            "license": "CC BY 4.0",
            "upstream_url": "https://github.com/Clear-Bible/macula-hebrew",
            "imported_at": "2026-04-17T00:00:00Z",
            "import_hash": "fixture-lxx",
            "allowed_for_generation": True,
            "allowed_for_display": True,
            "allowed_for_export": True,
            "notes": "Version-pinned Septuagint Greek witness aligned through MACULA data for explicit ideation.",
        },
        {
            "source_id": "sefaria",
            "name": "Sefaria Witness Snapshot",
            "version": "fixture-2026.04",
            "source_language": "en",
            "basis_role": "english_witness",
            "version_pinned": True,
            "license": "Custom-Restricted-Witness",
            "upstream_url": "https://developers.sefaria.org/",
            "imported_at": "2026-04-09T00:00:00Z",
            "import_hash": "fixture-sefaria",
            "allowed_for_generation": False,
            "allowed_for_display": True,
            "allowed_for_export": False,
            "notes": "Witness-only and version-pinned",
        },
        {
            "source_id": "kjv",
            "name": "King James (Authorized) Version",
            "version": "eng-kjv2006",
            "source_language": "en",
            "basis_role": "english_witness",
            "version_pinned": True,
            "license": "Public Domain",
            "upstream_url": "https://ebible.org/find/details.php?id=eng-kjv2006",
            "imported_at": "2026-04-17T00:00:00Z",
            "import_hash": "fixture-kjv",
            "allowed_for_generation": False,
            "allowed_for_display": True,
            "allowed_for_export": True,
            "notes": "Public-domain English witness imported from eBible.org VPL chapter files",
        },
        {
            "source_id": "asv",
            "name": "American Standard Version (1901)",
            "version": "eng-asv",
            "source_language": "en",
            "basis_role": "english_witness",
            "version_pinned": True,
            "license": "Public Domain",
            "upstream_url": "https://ebible.org/find/details.php?id=eng-asv",
            "imported_at": "2026-04-17T00:00:00Z",
            "import_hash": "fixture-asv",
            "allowed_for_generation": False,
            "allowed_for_display": True,
            "allowed_for_export": True,
            "notes": "Public-domain English witness imported from eBible.org VPL chapter files",
        },
        {
            "source_id": "web",
            "name": "World English Bible",
            "version": "engwebp",
            "source_language": "en",
            "basis_role": "english_witness",
            "version_pinned": True,
            "license": "Public Domain",
            "upstream_url": "https://ebible.org/bible/details.php?all=1&id=engwebp",
            "imported_at": "2026-04-17T00:00:00Z",
            "import_hash": "fixture-web",
            "allowed_for_generation": False,
            "allowed_for_display": True,
            "allowed_for_export": True,
            "notes": "Public-domain English witness imported from eBible.org VPL chapter files",
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


def _witness_manifest(source_id: str) -> dict[str, Any] | None:
    project = load_project()
    return next((item for item in project.get("source_manifests", []) if item.get("source_id") == source_id), None)


def _psalm_ref_key(ref: str) -> tuple[int, int] | None:
    match = PSALM_REF_RE.match(str(ref).strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


@lru_cache(maxsize=len(PUBLIC_DOMAIN_WITNESS_SOURCES))
def _load_public_domain_witness_map(source_id: str) -> dict[tuple[int, int], str]:
    config = next((item for item in PUBLIC_DOMAIN_WITNESS_SOURCES if item["source_id"] == source_id), None)
    if config is None:
        return {}
    zip_path = get_settings().raw_dir / source_id / config["zip_name"]
    if not zip_path.exists():
        return {}

    with zipfile.ZipFile(zip_path) as archive:
        text_name = next((name for name in archive.namelist() if name.lower().endswith("_vpl.txt")), None)
        if text_name is None:
            return {}
        lines = archive.read(text_name).decode("utf-8", errors="ignore").splitlines()

    witness_map: dict[tuple[int, int], str] = {}
    for line in lines:
        match = PSALM_VPL_RE.match(line.strip())
        if not match:
            continue
        psalm_number = int(match.group(1))
        verse_number = int(match.group(2))
        text = match.group(3).strip()
        if text:
            witness_map[(psalm_number, verse_number)] = text
    return witness_map


def _augment_public_domain_witnesses(unit: dict[str, Any]) -> dict[str, Any]:
    ref_key = _psalm_ref_key(str(unit.get("ref") or ""))
    if ref_key is None:
        return unit

    existing = list(unit.get("witnesses") or [])
    existing_source_ids = {str(item.get("source_id") or "").strip() for item in existing}
    augmented = list(existing)

    for config in PUBLIC_DOMAIN_WITNESS_SOURCES:
        source_id = config["source_id"]
        if source_id in existing_source_ids:
            continue
        witness_text = _load_public_domain_witness_map(source_id).get(ref_key)
        if not witness_text:
            continue
        manifest = _witness_manifest(source_id)
        augmented.append(
            {
                "source_id": source_id,
                "versionTitle": config["versionTitle"],
                "source_version": manifest.get("version") if manifest else None,
                "language": "en",
                "witness_role": "english_witness",
                "ref": f"Psalms {ref_key[0]}:{ref_key[1]}",
                "source_url": manifest.get("upstream_url", "") if manifest else "",
                "text": witness_text,
            }
        )
    if augmented == existing:
        return unit
    unit["witnesses"] = augmented
    return unit


def list_units() -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for path in list_unit_paths():
        if path.name.endswith(".meta.json"):
            continue
        units.append(_augment_public_domain_witnesses(read_json(path)))
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
    return _augment_public_domain_witnesses(read_json(path))


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
