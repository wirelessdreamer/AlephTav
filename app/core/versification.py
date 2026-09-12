"""Masoretic-to-English verse numbering, from the committed versification table.

The corpus stores Masoretic numbering, in which a superscription is counted as
one or two verses. English editions print that heading unnumbered, so English
verse N is Masoretic verse N + offset. The offsets are derived in
``scripts/build_versification.py`` and committed, rather than recalled.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


@lru_cache(maxsize=1)
def _table() -> dict[str, Any]:
    path = get_settings().content_dir / "versification.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("psalms", {})


def invalidate() -> None:
    """Drop the cache; used by tests that rebuild a workspace."""
    _table.cache_clear()


def entry(psalm_id: str) -> dict[str, Any] | None:
    return _table().get(psalm_id)


def display_offset(psalm_id: str) -> int:
    record = entry(psalm_id)
    return int(record["display_verse_offset"]) if record else 0


def canonical_numbering(psalm_id: str) -> dict[str, Any] | None:
    """Masoretic, Septuagint and Vulgate numbers for a psalm."""
    record = entry(psalm_id)
    if not record:
        return None
    return {
        "mt": record["mt"],
        "septuagint": record["septuagint"],
        "vulgate": record["vulgate"],
    }


def display_reference(psalm_id: str, mt_reference: str, mt_verse: int) -> str:
    """The user-facing reference for a Masoretic verse.

    Returns the MT reference unchanged when the psalm has no superscription.
    Verses consumed by the superscription have no English verse number at all,
    so they are labelled as the heading rather than given a misleading one.
    """
    offset = display_offset(psalm_id)
    if offset == 0:
        return mt_reference
    book = mt_reference.rsplit(":", 1)[0] if ":" in mt_reference else mt_reference
    if mt_verse <= offset:
        return f"{book} (heading)"
    return f"{book}:{mt_verse - offset}"
