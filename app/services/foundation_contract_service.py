"""Strict package contracts and source-only identity validation."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path, PureWindowsPath
from typing import Any

from jsonschema import Draft202012Validator, RefResolver  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.core.ids import parse_unit_id


def validate_contract(schema_name: str, payload: Any) -> None:
    directory = get_settings().schemas_dir
    schema = json.loads((directory / schema_name).read_text(encoding="utf-8"))
    resolver = RefResolver(base_uri=directory.resolve().as_uri() + "/", referrer=schema)
    Draft202012Validator(schema, resolver=resolver).validate(payload)


def workspace_path(value: str) -> Path:
    root = get_settings().root_dir.resolve()
    relative = Path(value)
    is_drive_path = bool(PureWindowsPath(value).drive)
    if relative.is_absolute() or is_drive_path or ".." in relative.parts or "\\" in value:
        raise ValueError("Package paths must be portable relative workspace paths")
    result = (root / relative).resolve()
    if not result.is_relative_to(root) or result == root:
        raise ValueError("Path escapes workspace")
    if result.is_relative_to(get_settings().raw_dir.resolve()):
        raise ValueError("Raw sources cannot be package installation targets")
    return result


def validate_greek_unit(unit: dict[str, Any]) -> None:
    validate_contract("greek_unit.schema.json", unit)
    identity = parse_unit_id(unit["unit_id"], require_versioned=True)
    if (identity.edition_id, identity.text_revision_id, identity.psalm_id) != (
        unit["edition_id"],
        unit["text_revision_id"],
        unit["psalm_id"],
    ):
        raise ValueError("Greek unit identity does not match its source revision")
    seen: set[str] = set()
    previous_end = 0
    for position, token in enumerate(unit["tokens"], 1):
        expected_prefix = unit["unit_id"].rsplit(".", 1)[0] + ".t"
        if not token["token_id"].startswith(expected_prefix) or token["token_id"] in seen:
            raise ValueError("Greek token identity must be unique and belong to this unit")
        seen.add(token["token_id"])
        start, end = token["text_span"]["start"], token["text_span"]["end"]
        if (
            token["position"] != position
            or start < previous_end
            or end <= start
            or unit["source_greek"][start:end] != token["surface"]
        ):
            raise ValueError("Greek token position/span does not resolve to source surface")
        if token["normalized"] != unicodedata.normalize("NFC", token["surface"]):
            raise ValueError("Greek normalized source surface must be NFC")
        previous_end = end
