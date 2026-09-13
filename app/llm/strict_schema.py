"""Derive the strict structured-output form of an output contract.

Codex forwards a turn's output schema to the model API in strict mode, which rejects
schemas that plain JSON Schema accepts: every object must list all of its properties as
required and forbid any others, and every array must say what it holds. The contracts stay
as they are, because they also validate local-model output and the payload Codex returns;
Codex is sent this stricter form instead. Anything that satisfies the strict form also
satisfies the contract it came from.
"""

from __future__ import annotations

from typing import Any


def strict_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a strict-mode copy of ``schema``. The input is never modified."""
    return _strict(schema)


def _strict(schema: dict[str, Any]) -> dict[str, Any]:
    node = dict(schema)
    if "properties" in node:
        node["properties"] = {name: _strict(sub) for name, sub in node["properties"].items()}
    if "items" in node:
        node["items"] = _strict(node["items"])
    if "anyOf" in node:
        node["anyOf"] = [_strict(sub) for sub in node["anyOf"]]

    if node.get("type") == "object":
        # Strict mode has no optional properties. Any value the model gives a property the
        # contract leaves optional is still valid against the contract.
        node["properties"] = node.get("properties", {})
        node["required"] = list(node["properties"])
        node["additionalProperties"] = False
    elif node.get("type") == "array" and "items" not in node:
        node["items"] = {"type": "string"}
    return node
