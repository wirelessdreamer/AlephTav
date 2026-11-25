"""Slow, rebuildable results kept as JSON under ``data/derived/cache``.

A result is stored under a key that fingerprints everything it derives from (input hashes,
the code that parses them), so a changed input or parser builds and stores a new one.
JSON rather than pickle: a cached file can never run code when read.
"""

from __future__ import annotations

import gc
import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import orjson

from app.core.config import get_settings
from app.services.immutable_file_service import atomic_write


@contextmanager
def paused_gc() -> Iterator[None]:
    """Building or reading millions of small objects runs about twice as fast without the
    cycle collector re-scanning them; nothing they hold is cyclic garbage."""
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()


def fingerprint(*parts: str | Path) -> str:
    """A key over strings and the bytes of files (a directory counts all its files)."""
    digest = hashlib.sha256()
    for part in parts:
        if isinstance(part, Path):
            files = sorted(part.rglob("*")) if part.is_dir() else [part]
            for path in files:
                if path.is_file():
                    digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
        else:
            digest.update(part.encode() + b"\0")
    return digest.hexdigest()


def load_or_build(name: str, key: str, build: Callable[[], Any]) -> Any:
    """The stored result for ``key``, else ``build()``'s, stored in place of older keys."""
    directory = get_settings().derived_dir / "cache" / name
    path = directory / f"{key}.json"
    with paused_gc():
        try:
            return orjson.loads(path.read_bytes())
        except (OSError, orjson.JSONDecodeError):
            pass
        value = build()
    atomic_write(path, orjson.dumps(value))
    for stale in directory.glob("*.json"):
        if stale != path:
            stale.unlink(missing_ok=True)
    return value
