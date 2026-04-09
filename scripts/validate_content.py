from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services import registry_service


def _load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema_name: str) -> Draft202012Validator:
    settings = get_settings()
    base_uri = settings.schemas_dir.resolve().as_uri() + "/"
    schema = _load_schema(settings.schemas_dir / schema_name)
    resolver = RefResolver(base_uri=base_uri, referrer=schema)
    return Draft202012Validator(schema, resolver=resolver)


def _deterministic_text(payload: Any) -> str:
    return registry_service.deterministic_json(payload)


def validate_all_content() -> dict[str, Any]:
    settings = get_settings()
    errors: list[str] = []
    validated_files: list[str] = []
    unit_validator = _validator("unit.schema.json")
    project_validator = _validator("project.schema.json")

    if settings.project_file.exists():
        project = registry_service.read_json(settings.project_file)
        for error in project_validator.iter_errors(project):
            errors.append(f"project.json: {error.message}")
        if settings.project_file.read_text(encoding="utf-8") != _deterministic_text(project):
            errors.append("project.json: non-deterministic serialization")
        validated_files.append(str(settings.project_file.relative_to(settings.root_dir)))
    else:
        errors.append("content/project.json missing")

    seen_ids: dict[str, set[str]] = {key: set() for key in ["unit", "token", "alignment", "rendering", "audit", "concept"]}

    for path in sorted(settings.psalms_dir.glob("ps*/ps*.json")):
        if path.name.endswith(".meta.json"):
            validated_files.append(str(path.relative_to(settings.root_dir)))
            continue
        unit = registry_service.read_json(path)
        for error in unit_validator.iter_errors(unit):
            errors.append(f"{path.relative_to(settings.root_dir)}: {error.message}")
        if path.read_text(encoding="utf-8") != _deterministic_text(unit):
            errors.append(f"{path.relative_to(settings.root_dir)}: non-deterministic serialization")
        if path.stem != unit.get("unit_id"):
            errors.append(f"{path.relative_to(settings.root_dir)}: filename does not match unit_id")
        _register_unique(seen_ids["unit"], unit.get("unit_id"), errors, f"duplicate unit_id in {path}")
        for value in unit.get("concept_ids", []):
            _register_unique(seen_ids["concept"], value, errors, f"duplicate concept_id {value}")
        for token in unit.get("tokens", []):
            _register_unique(seen_ids["token"], token["token_id"], errors, f"duplicate token_id {token['token_id']}")
        for alignment in unit.get("alignments", []):
            _register_unique(seen_ids["alignment"], alignment["alignment_id"], errors, f"duplicate alignment_id {alignment['alignment_id']}")
        for rendering in unit.get("renderings", []):
            _register_unique(seen_ids["rendering"], rendering["rendering_id"], errors, f"duplicate rendering_id {rendering['rendering_id']}")
        for audit in unit.get("audit_records", []):
            _register_unique(seen_ids["audit"], audit["audit_id"], errors, f"duplicate audit_id {audit['audit_id']}")
        if len(unit.get("token_ids", [])) != len(unit.get("tokens", [])):
            errors.append(f"{path.relative_to(settings.root_dir)}: token_ids length mismatch")
        if sorted(unit.get("audit_ids", [])) != sorted(audit["audit_id"] for audit in unit.get("audit_records", [])):
            errors.append(f"{path.relative_to(settings.root_dir)}: audit_ids do not mirror audit_records")
        validated_files.append(str(path.relative_to(settings.root_dir)))

    return {"validated_files": validated_files, "errors": errors}


def _register_unique(bucket: set[str], value: str | None, errors: list[str], message: str) -> None:
    if value is None:
        return
    if value in bucket:
        errors.append(message)
    bucket.add(value)


def main() -> None:
    result = validate_all_content()
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["errors"] else 0)


if __name__ == "__main__":
    main()
