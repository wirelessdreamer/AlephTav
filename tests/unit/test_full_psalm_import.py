from __future__ import annotations

from app.services import ingest_service, registry_service


def test_vendored_import_seeds_full_psalms_corpus() -> None:
    units = ingest_service.import_vendored_psalms()

    assert len(registry_service.list_psalm_ids()) == 150
    assert units[0]["psalm_id"] == "ps001"
    assert units[-1]["psalm_id"] == "ps150"

    psalm_1 = registry_service.load_psalm("ps001")
    assert psalm_1["title"] == "Psalm 1"
    assert len(psalm_1["units"]) == 6
    assert psalm_1["units"][0]["source_hebrew"].startswith("אַ֥שְֽׁרֵי־הָאִ֗ישׁ")
    assert psalm_1["units"][0]["tokens"][0]["strong"] == "H835"

    psalm_119 = registry_service.load_psalm("ps119")
    assert len(psalm_119["units"]) == 176

    psalm_150 = registry_service.load_psalm("ps150")
    assert psalm_150["units"][-1]["ref"] == "Psalm 150:6"

    project = registry_service.load_project()
    manifests = {item["source_id"]: item for item in project["source_manifests"]}
    assert manifests["uxlc"]["license"] == "Public Domain"
    assert manifests["uxlc"]["import_hash"] != "fixture-uxlc"
    assert manifests["oshb"]["import_hash"] != "fixture-oshb"
    assert manifests["macula"]["import_hash"] != "fixture-macula"
