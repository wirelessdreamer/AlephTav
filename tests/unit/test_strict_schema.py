"""Strict structured-output form of the output contracts sent to Codex.

Codex forwards a turn's output schema to the model API in strict mode, which rejected the
generation contract outright ("array schema missing items") and so failed every translation
turn before the model ran.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from importlib import resources
from typing import Any

import pytest

from app.llm.strict_schema import strict_output_schema

CONTRACTS = (
    "generation_output.schema.json",
    "verse_analysis_output.schema.json",
    "psalm_analysis_output.schema.json",
)


def _contract(name: str) -> dict[str, Any]:
    text = resources.files("app.llm.contracts").joinpath(name).read_text(encoding="utf-8")
    return json.loads(text)


def _nodes(schema: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield schema
    for sub in schema.get("properties", {}).values():
        yield from _nodes(sub)
    if "items" in schema:
        yield from _nodes(schema["items"])
    for sub in schema.get("anyOf", []):
        yield from _nodes(sub)


@pytest.mark.parametrize("name", CONTRACTS)
def test_every_object_and_array_meets_strict_mode(name: str) -> None:
    for node in _nodes(strict_output_schema(_contract(name))):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert node["required"] == list(node["properties"])
        if node.get("type") == "array":
            assert "items" in node


def test_optional_properties_become_required_and_the_contract_is_untouched() -> None:
    contract = {
        "type": "object",
        "required": ["text"],
        "properties": {"text": {"type": "string"}, "note": {"type": "string"}},
    }
    before = copy.deepcopy(contract)

    strict = strict_output_schema(contract)

    assert strict["required"] == ["text", "note"]
    assert strict["additionalProperties"] is False
    assert contract == before


def test_untyped_arrays_hold_strings_and_free_form_objects_are_closed() -> None:
    strict = strict_output_schema(
        {
            "type": "object",
            "properties": {"hints": {"type": "array"}, "metrics": {"type": "object"}},
        }
    )

    assert strict["properties"]["hints"]["items"] == {"type": "string"}
    assert strict["properties"]["metrics"] == {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }


@pytest.mark.parametrize("name", CONTRACTS[1:])
def test_contracts_already_in_strict_form_pass_through_unchanged(name: str) -> None:
    assert strict_output_schema(_contract(name)) == _contract(name)
