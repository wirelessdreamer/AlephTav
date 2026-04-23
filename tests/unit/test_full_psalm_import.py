from __future__ import annotations

from app.services import ingest_service, registry_service
from tests.support import bootstrap_fixture_repo


def test_vendored_import_seeds_full_psalms_corpus() -> None:
    try:
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
        assert manifests["kjv"]["license"] == "Public Domain"
        assert manifests["kjv"]["allowed_for_generation"] is False
        assert manifests["asv"]["allowed_for_export"] is True
        assert manifests["web"]["import_hash"] != "fixture-web"

        verse_two = registry_service.load_unit("ps001.v002.a")
        witnesses = {item["source_id"]: item for item in verse_two["witnesses"]}
        assert set(witnesses) == {"kjv", "asv", "web"}
        assert witnesses["kjv"]["text"].startswith("But his delight")
        assert "law of the LORD" in witnesses["kjv"]["text"]
        assert witnesses["asv"]["text"].startswith("But his delight is in the law")
        assert witnesses["web"]["text"].startswith("but his delight is in")
        assert "On his law he meditates day and night" in witnesses["web"]["text"]

        first_token = verse_two["tokens"][0]
        second_token = verse_two["tokens"][1]
        assert first_token["gloss_parts"] == ["(dm)"]
        assert first_token["display_gloss"] == "but"
        assert first_token["compiler_features"]["conjunction_role"] == "contrastive"
        assert second_token["gloss_parts"] == ["(if)"]
        assert second_token["display_gloss"] == "rather"
        assert "(" not in first_token["display_gloss"]
        assert "(" not in second_token["display_gloss"]
    finally:
        bootstrap_fixture_repo()
