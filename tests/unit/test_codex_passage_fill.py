"""Translating several verses of a psalm in one Codex turn per layer.

A verse per turn cannot see the verses after it, so meter, recurring terms and
parallelism drift across verse boundaries. The passage fill sends the whole psalm
as context and still saves one audited, proposed rendering per unit.
"""

from __future__ import annotations

import json
import re
from collections import deque
from copy import deepcopy
from typing import Any

import pytest

from app.core.errors import ValidationError
from app.llm.strict_schema import strict_output_schema
from app.services import codex_app_server_service as codex
from app.services import codex_translation_service as translation
from app.services import registry_service

UNIT_ID = "ps001.v001.a"
SECOND_ID = "ps001.v002.a"


@pytest.fixture(autouse=True)
def _restore_psalm():
    """Passages need a second verse; put the fixture psalm back afterwards."""
    translation._store_path().unlink(missing_ok=True)
    meta = registry_service.load_psalm_meta("ps001")
    first = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_psalm_meta("ps001", meta)
    registry_service.save_unit(first)
    registry_service.unit_path(SECOND_ID).unlink(missing_ok=True)
    translation._store_path().unlink(missing_ok=True)


def _add_second_verse(keep_renderings: bool = False) -> None:
    unit = deepcopy(registry_service.load_unit(UNIT_ID))
    unit["unit_id"] = SECOND_ID
    unit["ref"] = "Psalm 1:2"
    unit["source_hebrew"] = "כִּי אִם בְּתוֹרַת יְהוָה חֶפְצוֹ"
    if not keep_renderings:
        unit["renderings"] = []
        unit["canonical_rendering_ids"] = []
        unit["alternate_rendering_ids"] = []
    registry_service.save_unit(unit)
    meta = registry_service.load_psalm_meta("ps001")
    meta["unit_ids"] = [*meta["unit_ids"], SECOND_ID]
    registry_service.save_psalm_meta("ps001", meta)


def _entry(unit_id: str, layer: str) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "layer": layer,
        "candidates": [
            {
                "text": f"{layer} for {unit_id}",
                "rationale": "tracks the Hebrew",
                "alignment_hints": [],
                "drift_flags": [],
                "metrics": {},
                "variation_basis": ["hebrew_source"],
                "preserved_source_images": [],
                "differentiator": "d",
                "grounding_confidence": 0.9,
                "translation_basis": {
                    "basis_type": "hebrew_to_english",
                    "source_ids": ["oshb"],
                    "source_language": "he",
                    "source_version": "1.0",
                    "basis_note": "Hebrew source",
                },
                "delivery_profile": "sung",
                "source_anchor": {
                    "anchor_text": "a",
                    "source_language": "he",
                    "source_text": "b",
                    "basis_note": "c",
                },
                "accuracy_note": "Tracks the Hebrew clause order.",
                "creative_liberties_note": "Contracted for singability.",
                "literalness": "close",
            }
        ],
    }


class PassageTransport:
    """Answers each turn with an entry for every unit the prompt asks for."""

    def __init__(self, omit: set[str] | None = None, raw_reply: str | None = None) -> None:
        self.omit = omit or set()
        self.raw_reply = raw_reply
        self.sent: list[dict[str, Any]] = []
        self._inbox: deque[str] = deque()
        self.turn = 0

    def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)
        method = message.get("method")
        if method == "thread/start":
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {"thread": {"id": "th"}}})
        elif method == "turn/start":
            self.turn += 1
            turn_id = f"turn-{self.turn}"
            reply = self.raw_reply or json.dumps(self._reply(message["params"]["input"][0]["text"]))
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {"turn": {"id": turn_id}}})
            self._push(
                {
                    "jsonrpc": "2.0",
                    "method": "item/completed",
                    "params": {"item": {"type": "agentMessage", "text": reply}},
                }
            )
            self._push(
                {"jsonrpc": "2.0", "method": "turn/completed", "params": {"turn": {"id": turn_id}}}
            )
        elif "id" in message:
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {}})

    def _reply(self, prompt: str) -> dict[str, Any]:
        layer = re.search(r"Required output layer: (\S+)", prompt).group(1)  # type: ignore[union-attr]
        units = re.search(r"Units to translate, in order: (.+)", prompt).group(1)  # type: ignore[union-attr]
        return {
            "psalm_id": "ps001",
            "layer": layer,
            "units": [_entry(u, layer) for u in units.split(", ") if u not in self.omit],
        }

    def _push(self, obj: dict[str, Any]) -> None:
        self._inbox.append(json.dumps(obj))

    def readline(self) -> str:
        return self._inbox.popleft() + "\n" if self._inbox else ""

    def close(self) -> None:
        pass

    def turns(self) -> list[dict[str, Any]]:
        return [m["params"] for m in self.sent if m.get("method") == "turn/start"]


def _session(transport: PassageTransport) -> tuple[codex.CodexAppServerClient, str]:
    client = codex.CodexAppServerClient(transport=transport)
    return client, translation.create_session(client, psalm_id="ps001")["session_id"]


def test_passage_prompt_carries_the_whole_psalm_the_guidance_and_the_layer_rules() -> None:
    _add_second_verse()
    translation.set_guidance("ps001", "Target 6/8 meter.")

    prompt = translation.build_passage_prompt("ps001", [SECOND_ID], "lyric")

    # The translator's guidance, then the project's lyric rules, then the evidence.
    assert prompt.index("Target 6/8 meter.") < prompt.index("## Layer instructions (lyric)")
    assert "# Pass 05 Lyric" in prompt
    assert prompt.index("## Layer instructions") < prompt.index("## The whole psalm")
    # Every verse is there for context; only the requested one is marked and evidenced,
    # and the verse already translated is shown so the passage stays continuous.
    assert registry_service.load_unit(UNIT_ID)["source_hebrew"] in prompt
    assert f"[{SECOND_ID}] <- translate" in prompt
    assert f"[{UNIT_ID}] <- translate" not in prompt
    assert "Current lyric:" in prompt
    assert f"## Evidence for {SECOND_ID}" in prompt
    assert f"## Evidence for {UNIT_ID}" not in prompt


def test_passage_fill_takes_one_turn_per_layer_and_saves_every_unit() -> None:
    _add_second_verse()  # no literal yet; the fixture verse already has one
    client, session_id = _session(PassageTransport())

    result = translation.fill_psalm_passage(client, session_id, "ps001", [UNIT_ID, SECOND_ID])

    assert result["status"] == translation.RUN_COMPLETED
    assert result["failed_units"] == []
    prompts = [turn["input"][0]["text"] for turn in client.transport.turns()]
    assert len(prompts) == len(result["run_ids"]) == 2
    assert f"Units to translate, in order: {SECOND_ID}\n" in prompts[0]
    assert f"Units to translate, in order: {UNIT_ID}, {SECOND_ID}\n" in prompts[1]
    # The literal just generated is the baseline for the lyric turn.
    assert f"literal for {SECOND_ID}" in prompts[1]

    units = [registry_service.load_unit(UNIT_ID), registry_service.load_unit(SECOND_ID)]
    created = [
        (unit["unit_id"], rendering)
        for unit in units
        for rendering in unit["renderings"]
        if rendering["rendering_id"] in result["rendering_ids"]
    ]
    assert sorted((unit_id, r["layer"]) for unit_id, r in created) == [
        (UNIT_ID, "lyric"),
        (SECOND_ID, "literal"),
        (SECOND_ID, "lyric"),
    ]
    assert all(r["status"] == "proposed" for _, r in created)
    # Each rendering is audited on its own unit.
    for unit in units:
        audited = {record["entity_id"] for record in unit["audit_records"]}
        mine = {r["rendering_id"] for unit_id, r in created if unit_id == unit["unit_id"]}
        assert mine <= audited


def test_units_left_out_of_the_reply_are_reported_and_the_rest_are_saved() -> None:
    _add_second_verse(keep_renderings=True)  # both have literals: one lyric turn
    client, session_id = _session(PassageTransport(omit={SECOND_ID}))

    result = translation.fill_psalm_passage(client, session_id, "ps001", [UNIT_ID, SECOND_ID])

    assert result["status"] == translation.RUN_COMPLETED
    assert [failure["unit_id"] for failure in result["failed_units"]] == [SECOND_ID]
    assert "no lyric rendering" in result["failed_units"][0]["error"]
    first_renderings = registry_service.load_unit(UNIT_ID)["renderings"]
    assert any(r["rendering_id"] in result["rendering_ids"] for r in first_renderings)
    second_renderings = registry_service.load_unit(SECOND_ID)["renderings"]
    assert not any(r["rendering_id"] in result["rendering_ids"] for r in second_renderings)


def test_a_passage_reply_that_is_not_json_saves_nothing() -> None:
    client, session_id = _session(PassageTransport(raw_reply="not json"))

    result = translation.fill_psalm_passage(client, session_id, "ps001", [UNIT_ID])

    assert result["status"] == translation.RUN_INVALID_OUTPUT
    assert result["rendering_ids"] == []


def test_passage_fill_refuses_units_from_another_psalm() -> None:
    client, session_id = _session(PassageTransport())

    with pytest.raises(ValidationError, match="ps019.v001.a"):
        translation.fill_psalm_passage(client, session_id, "ps001", ["ps019.v001.a"])
    assert client.transport.turns() == []


def test_codex_gets_the_passage_contract_in_strict_form() -> None:
    client, session_id = _session(PassageTransport())

    translation.fill_psalm_passage(client, session_id, "ps001", [UNIT_ID])

    [turn] = client.transport.turns()
    assert turn["outputSchema"] == strict_output_schema(translation.PASSAGE_VALIDATOR.schema)
    entry = turn["outputSchema"]["properties"]["units"]["items"]
    assert entry["required"] == list(entry["properties"])
    assert entry["additionalProperties"] is False
