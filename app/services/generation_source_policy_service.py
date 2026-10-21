"""Ephemeral model-input projection; historical source records stay untouched."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.errors import LicensePolicyError
from app.services.source_capability_service import effective_capabilities, policy_revision


def model_token(token: dict[str, Any]) -> dict[str, Any]:
    projected = deepcopy(token)
    if not effective_capabilities("macula", "greek")["generation"]:
        projected.pop("greek", None)
        projected.pop("greek_strong", None)
    return projected


def model_unit(unit: dict[str, Any]) -> dict[str, Any]:
    current_policy = policy_revision()
    projected = deepcopy(unit)
    allow_hints = effective_capabilities("macula", "greek")["generation"]
    for token in projected.get("tokens", []):
        if not allow_hints:
            token.pop("greek", None)
            token.pop("greek_strong", None)
    projected["witnesses"] = [
        witness
        for witness in projected.get("witnesses", [])
        if effective_capabilities(str(witness.get("source_id") or ""))["generation"]
    ]
    if policy_revision() != current_policy:
        raise LicensePolicyError("Source generation policy changed while projecting model inputs")
    return projected
