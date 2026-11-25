"""Validate review evidence and describe bindings without granting publication authority."""

from __future__ import annotations

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]
from referencing import Registry

from app.core.errors import ValidationError

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_FORMATS = FormatChecker()


@_FORMATS.checks("date-time", raises=ValueError)
def _valid_datetime(value: Any) -> bool:
    # Keep calendar validation available without jsonschema's optional format extras.
    if not isinstance(value, str):
        return True
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.utcoffset() is not None


@lru_cache(maxsize=2)
def _validator(version: str) -> Draft202012Validator:
    name = (
        "review_decision_v1.schema.json"
        if version == "legacy"
        else "review_decision_v2.schema.json"
    )
    schema = json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))
    # An empty Registry has no remote retrieval. Both standalone contracts use only
    # their own local definitions; the workspace cannot substitute its schemas.
    return Draft202012Validator(schema, registry=Registry(), format_checker=_FORMATS)


def is_legacy_review_decision(record: Any) -> bool:
    """Cheap version discriminator only; this does not establish schema validity."""
    return isinstance(record, dict) and "contract_version" not in record


def validate_review_decision(record: Any) -> str:
    """Return ``legacy`` or ``v2`` for a valid record; never authenticate its claims."""
    version = "legacy" if is_legacy_review_decision(record) else "v2"
    error = next(_validator(version).iter_errors(record), None)
    if error is not None:
        location = ".".join(str(part) for part in error.absolute_path) or "record"
        # Do not echo notes, display names, or other untrusted record values.
        raise ValidationError(
            f"Invalid review decision: {location[:160]} violates {error.validator}"
        )
    return version


def _valid_current_binding(payload_digest: Any, policy_revision: Any) -> bool:
    return (
        isinstance(payload_digest, dict)
        and payload_digest.keys() == {"version", "algorithm", "value"}
        and payload_digest.get("version") == 2
        and payload_digest.get("algorithm") == "sha256"
        and isinstance(payload_digest.get("value"), str)
        and _SHA256.fullmatch(payload_digest["value"]) is not None
        and isinstance(policy_revision, str)
        and _SHA256.fullmatch(policy_revision) is not None
    )


def classify_review_evidence(
    record: Any,
    *,
    payload_digest: dict[str, Any] | None,
    policy_revision: str | None,
) -> dict[str, Any]:
    """Describe applicability only. Matching bindings are not proof of human review."""
    result: dict[str, Any] = {"counts_for_publication": False}
    try:
        version = validate_review_decision(record)
    except ValidationError as error:
        return {**result, "status": "invalid", "reason": str(error)}
    if version == "legacy":
        return {**result, "status": "legacy_requires_reattestation"}
    if not _valid_current_binding(payload_digest, policy_revision):
        return {**result, "status": "binding_unavailable"}
    if record["payload_digest"] != payload_digest:
        return {**result, "status": "payload_mismatch"}
    if record["policy_revision"] != policy_revision:
        return {**result, "status": "policy_mismatch"}
    return {**result, "status": "binding_current_unverified"}
