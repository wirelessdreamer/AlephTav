"""Validate retained bridge evidence and count groups without inventing token pairs.

These pure operations do not accept, publish, or supersede an alignment set.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.core.errors import ValidationError


def validate_endpoints(
    bridge: dict[str, Any],
    mt_tokens: dict[str, Any],
    greek_tokens: dict[str, Any],
    *,
    mt_snapshot_id: str,
    study_snapshot_id: str,
) -> None:
    if (
        bridge.get("mt_snapshot_id") != mt_snapshot_id
        or bridge.get("study_snapshot_id") != study_snapshot_id
    ):
        raise ValidationError("Bridge endpoints belong to a different immutable snapshot")
    owned: dict[str, set[str]] = {"mt": set(), "greek": set()}
    group_ids: set[str] = set()
    for group in bridge["groups"]:
        if group["group_id"] in group_ids:
            raise ValidationError("Duplicate bridge group")
        group_ids.add(group["group_id"])
        if not group["mt_token_ids"] and not group["greek_token_ids"]:
            raise ValidationError("Both-empty bridge group")
        for side, tokens in (("mt", mt_tokens), ("greek", greek_tokens)):
            ids = group[f"{side}_token_ids"]
            if len(ids) != len(set(ids)) or any(token not in tokens for token in ids):
                raise ValidationError("Duplicate or nonexistent bridge endpoint")
            if group.get("status") == "accepted":
                if owned[side].intersection(ids):
                    raise ValidationError("Overlapping accepted bridge ownership")
                owned[side].update(ids)
        if group.get("status") == "accepted":
            expected = (
                "greek_plus"
                if not group["mt_token_ids"]
                else ("hebrew_minus" if not group["greek_token_ids"] else "linked")
            )
            if group.get("observation") != expected:
                raise ValidationError("Accepted plus/minus requires an explicit observation")
    if bridge.get("aligned") and any(
        owned[side] != set(tokens) for side, tokens in (("mt", mt_tokens), ("greek", greek_tokens))
    ):
        raise ValidationError("Aligned accepted set requires exactly-one endpoint coverage")


def distribution(
    bridge: dict[str, Any],
    mt_tokens: dict[str, Any],
    greek_tokens: dict[str, Any],
    *,
    mt_snapshot_id: str,
    study_snapshot_id: str,
    source_side: str,
    lexeme_id: str,
) -> dict[str, Any]:
    """Count accepted group observations and opposite-side lexeme multisets.

    Tokens supply snapshot-bound reviewed ``lexeme_id`` values. Unresolved opposite
    analyses are represented explicitly rather than silently dropped from a signature.
    Caller must check current source permissions and accepted-set review eligibility.
    """
    validate_endpoints(
        bridge,
        mt_tokens,
        greek_tokens,
        mt_snapshot_id=mt_snapshot_id,
        study_snapshot_id=study_snapshot_id,
    )
    if source_side not in {"mt", "greek"}:
        raise ValidationError("Unknown bridge side")
    source = mt_tokens if source_side == "mt" else greek_tokens
    opposite = greek_tokens if source_side == "mt" else mt_tokens
    opposite_side = "greek" if source_side == "mt" else "mt"
    outcomes: Counter[tuple[tuple[str, int], ...]] = Counter()
    selected_groups = []
    selected_source: set[str] = set()
    selected_opposite: set[str] = set()
    accepted_source: set[str] = set()
    unresolved = proposed = plus = minus = 0
    for group in bridge["groups"]:
        source_ids = group[f"{source_side}_token_ids"]
        matching = [token for token in source_ids if source[token].get("lexeme_id") == lexeme_id]
        if group.get("status") != "accepted":
            if matching:
                proposed += group.get("status") == "proposed"
                unresolved += group.get("status") != "proposed"
            continue
        accepted_source.update(source_ids)
        if not matching:
            continue
        opposite_ids = group[f"{opposite_side}_token_ids"]
        signature = tuple(
            sorted(
                Counter(
                    opposite[token].get("lexeme_id") or "<unresolved>" for token in opposite_ids
                ).items()
            )
        )
        outcomes[signature] += 1
        selected_groups.append(group["group_id"])
        selected_source.update(matching)
        selected_opposite.update(opposite_ids)
        plus += group["observation"] == "greek_plus"
        minus += group["observation"] == "hebrew_minus"
    population = {token for token, data in source.items() if data.get("lexeme_id") == lexeme_id}
    return {
        "set_id": bridge["set_id"],
        "mt_snapshot_id": mt_snapshot_id,
        "study_snapshot_id": study_snapshot_id,
        "source_side": source_side,
        "lexeme_id": lexeme_id,
        "counting_unit": "accepted_alignment_group",
        "alignment_group_count": len(selected_groups),
        "distinct_source_tokens": len(selected_source),
        "distinct_opposite_tokens": len(selected_opposite),
        "coverage": {
            "source_lexeme_tokens": len(population),
            "accepted_source_lexeme_tokens": len(population & accepted_source),
            "unresolved_source_lexeme_tokens": len(population - accepted_source),
        },
        "greek_plus_groups": plus,
        "hebrew_minus_groups": minus,
        "proposed_groups": proposed,
        "unresolved_groups": unresolved,
        "outcomes": [
            {
                "opposite_lexeme_multiset": [
                    {"lexeme_id": lexeme, "multiplicity": count} for lexeme, count in signature
                ],
                "group_count": count,
            }
            for signature, count in sorted(outcomes.items())
        ],
    }
