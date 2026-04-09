from __future__ import annotations

from typing import Any

ALLOWED_LICENSES = {
    "Public Domain",
    "CC BY 4.0",
    "CC BY-SA 4.0",
    "Open Scriptural Data",
    "Custom-Restricted-Witness",
}

FORBIDDEN_FOR_GENERATION = {"Custom-Restricted-Witness"}
FORBIDDEN_FOR_EXPORT = {"Custom-Restricted-Witness"}


def evaluate_manifest(entry: dict[str, Any]) -> dict[str, Any]:
    license_name = entry.get("license", "UNKNOWN")
    allowed = license_name in ALLOWED_LICENSES
    warnings: list[str] = []
    if not allowed:
        warnings.append("unknown_license")
    if license_name in FORBIDDEN_FOR_GENERATION and entry.get("allowed_for_generation", False):
        warnings.append("forbidden_for_generation")
    if license_name in FORBIDDEN_FOR_EXPORT and entry.get("allowed_for_export", False):
        warnings.append("forbidden_for_export")
    return {
        "source_id": entry.get("source_id"),
        "license": license_name,
        "allowed": allowed and not warnings,
        "warnings": warnings,
    }
