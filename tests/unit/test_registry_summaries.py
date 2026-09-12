"""Unit tests for the slim psalm-summary and corpus-layer registry helpers."""

from __future__ import annotations

import pytest

from app.services import registry_service


def test_list_psalm_summaries_returns_slim_records_without_units() -> None:
    summaries = registry_service.list_psalm_summaries()

    assert summaries, "fixture corpus should produce at least one summary"

    # IDs match the full id listing and are sorted.
    summary_ids = [item["psalm_id"] for item in summaries]
    assert summary_ids == registry_service.list_psalm_ids()

    # Every summary carries id/title/unit_ids and nothing else heavy.
    for summary in summaries:
        assert set(summary) == {"psalm_id", "title", "unit_ids"}
        assert isinstance(summary["unit_ids"], list)
        # Critically: the summary must NOT include nested units. That is the
        # entire point of this endpoint — keeping it cheap.
        assert "units" not in summary

    # The first fixture psalm (ps001) should match what load_psalm reports.
    full = registry_service.load_psalm("ps001")
    ps001 = next(item for item in summaries if item["psalm_id"] == "ps001")
    assert ps001["title"] == full["title"]
    assert ps001["unit_ids"] == full["unit_ids"]


def test_get_corpus_layers_returns_distinct_rendering_layers() -> None:
    layers = registry_service.get_corpus_layers()

    # The fixture seeds renderings — we should at least see the canonical
    # gloss/literal layers that pass_01 and pass_02 emit.
    assert isinstance(layers, list)
    assert all(isinstance(item, str) for item in layers)
    # Whatever the fixture seeds, every entry should be distinct.
    assert len(layers) == len(set(layers))


@pytest.mark.no_seeded_repo
def test_get_corpus_layers_returns_empty_when_db_missing(tmp_path, monkeypatch) -> None:
    """If the derived index DB hasn't been built, return [] instead of raising."""
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    # Also clear any in-memory cache lingering from a prior test run.
    registry_service.invalidate_summary_cache()
    assert registry_service.get_corpus_layers() == []


def test_build_summary_cache_persists_both_caches_to_disk() -> None:
    """After build, on-disk JSON files exist with the expected slim payload."""
    result = registry_service.build_summary_cache()

    summary_path = registry_service._summary_cache_path()
    layers_path = registry_service._layers_cache_path()
    assert summary_path.exists(), "summary cache file must be written"
    assert layers_path.exists(), "layers cache file must be written"

    summaries = registry_service.read_json(summary_path)
    layers = registry_service.read_json(layers_path)
    assert isinstance(summaries, list)
    assert isinstance(layers, list)
    assert result == {"psalms": len(summaries), "layers": len(layers)}

    # Each persisted summary stays slim — nested units are forbidden here.
    for entry in summaries:
        assert set(entry) == {"psalm_id", "title", "unit_ids"}
        assert "units" not in entry


def test_list_psalm_summaries_serves_from_in_memory_cache_after_first_call() -> None:
    """Once warmed, the in-memory mirror returns identity-equal results."""
    # Warm explicitly so we know the state.
    registry_service.build_summary_cache()
    first = registry_service.list_psalm_summaries()
    second = registry_service.list_psalm_summaries()
    # Same object, not just same content: this proves the cache is hit and
    # we are not re-reading or re-computing.
    assert first is second


def test_list_psalm_summaries_loads_from_disk_when_memory_empty() -> None:
    """After invalidating only the in-memory mirror, disk cache should serve."""
    registry_service.build_summary_cache()
    # Snapshot the disk-persisted summaries.
    snapshot = registry_service.read_json(registry_service._summary_cache_path())

    # Wipe just the in-memory cache (not the disk file) and re-call.
    registry_service._summary_cache = None
    registry_service._layers_cache = None
    served = registry_service.list_psalm_summaries()

    assert served == snapshot
    # Second call should now hit the in-memory cache populated from disk.
    assert registry_service.list_psalm_summaries() is served


def test_invalidate_summary_cache_clears_both_memory_and_disk() -> None:
    registry_service.build_summary_cache()
    assert registry_service._summary_cache_path().exists()
    assert registry_service._layers_cache_path().exists()

    registry_service.invalidate_summary_cache()

    assert registry_service._summary_cache is None
    assert registry_service._layers_cache is None
    assert not registry_service._summary_cache_path().exists()
    assert not registry_service._layers_cache_path().exists()
