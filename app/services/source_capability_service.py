"""Current source policy; retained catalogs never confer permissions."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.config import get_settings
from app.core.errors import LicensePolicyError
from app.core.license_rules import evaluate_manifest

CAPABILITIES = ("display", "export", "generation", "dictionary", "analysis")


class SourceUnavailableError(LicensePolicyError):
    """The current policy does not allow this source component/use."""


def _registry() -> dict[str, Any]:
    path = get_settings().content_dir / "source_registry.json"
    if not path.exists():
        return {"policy_revision_id": "legacy", "sources": []}
    from app.services.foundation_contract_service import validate_contract

    registry = json.loads(path.read_text(encoding="utf-8"))
    validate_contract("source_registry.schema.json", registry)
    identities = [source["source_id"] for source in registry["sources"]]
    if len(identities) != len(set(identities)):
        raise SourceUnavailableError("Duplicate current source policy identities")
    return registry


def policy_revision() -> str:
    # Bind caches to bytes as well as the human label: reusing a label cannot
    # accidentally make an old permissive cache eligible after revocation.
    registry = _registry()
    digest = hashlib.sha256(json.dumps(registry, sort_keys=True).encode()).hexdigest()[:24]
    return f"{registry['policy_revision_id']}:{digest}"


def approval_payload_hash(
    source_id: str,
    component: str,
    capabilities: dict[str, bool],
    package_hashes: dict[str, str] | None = None,
) -> str:
    from app.services.registry_service import file_hash

    payload: dict[str, Any] = {
        "source_id": source_id,
        "component": component,
        "capabilities": capabilities,
    }
    if package_hashes:
        payload["package_hashes"] = package_hashes
    return file_hash(payload)


def _approved(source_id: str, component: str, payload: dict[str, Any]) -> bool:
    if payload.get("status") != "approved":
        return False
    expected = approval_payload_hash(
        source_id,
        component,
        payload.get("capabilities", {}),
        payload.get("package_hashes"),
    )
    latest: dict[str, dict[str, Any]] = {}
    for decision in payload.get("approvals", []):
        # A later withdrawal applies even if its payload hash is unchanged.
        latest[decision["reviewer_id"]] = decision
    applicable = [
        decision
        for decision in latest.values()
        if decision.get("decision") == "approve" and decision.get("payload_hash") == expected
    ]
    if any(decision.get("decision") == "request_changes" for decision in latest.values()):
        return False
    owners = {d["reviewer_id"] for d in applicable if d.get("role") == "owner"}
    licenses = {d["reviewer_id"] for d in applicable if d.get("role") == "license"}
    return any(owner != reviewer for owner in owners for reviewer in licenses)


def effective_capabilities(source_id: str, component: str | None = None) -> dict[str, bool]:
    component = component or "text"
    denied = dict.fromkeys(CAPABILITIES, False)
    registry = _registry()
    source = next((s for s in registry.get("sources", []) if s["source_id"] == source_id), None)
    if source is not None:
        payload = source.get("components", {}).get(component)
        if payload is None or not _approved(source_id, component, payload):
            return denied
        return {name: payload.get("capabilities", {}).get(name) is True for name in CAPABILITIES}

    # Legacy MACULA Greek is never an approved edition, and its permissions
    # cannot be inherited from the unrelated Hebrew-enrichment component.
    if source_id == "lxx" or source_id.startswith("lxx.") or component == "greek":
        return denied
    settings = get_settings()
    if not settings.project_file.exists():
        return denied
    project = json.loads(settings.project_file.read_text(encoding="utf-8"))
    manifest = next(
        (s for s in project.get("source_manifests", []) if s["source_id"] == source_id), None
    )
    if manifest is None or manifest.get("source_language") == "grc":
        return denied
    if not evaluate_manifest(manifest)["allowed"]:
        return denied
    capabilities = {
        name: manifest.get(f"allowed_for_{name}") is True
        for name in ("display", "export", "generation")
    }
    if manifest.get("source_language") == "en" or manifest.get("basis_role") == "english_witness":
        capabilities["generation"] = False
    return {**denied, **capabilities}


def require_capability(source_id: str, capability: str, component: str | None = None) -> None:
    if capability not in CAPABILITIES:
        raise ValueError(f"Unknown source capability: {capability}")
    if not effective_capabilities(source_id, component)[capability]:
        raise SourceUnavailableError(
            f"Source unavailable for {capability}: {source_id}/{component or 'text'}"
        )


def require_package_capability(
    source_id: str,
    package_id: str,
    package_hash: str,
    capability: str,
    component: str | None = None,
) -> None:
    require_capability(source_id, capability, component)
    source = next((s for s in _registry()["sources"] if s["source_id"] == source_id), None)
    payload = source.get("components", {}).get(component or "text", {}) if source else {}
    if payload.get("package_hashes", {}).get(package_id) != package_hash:
        raise SourceUnavailableError("Source package revision has no applicable current approval")
