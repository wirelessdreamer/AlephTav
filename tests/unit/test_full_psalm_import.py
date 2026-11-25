from __future__ import annotations

from app.services import full_psalm_import_service, ingest_service, registry_service
from tests.support import bootstrap_fixture_repo


def test_reimporting_keeps_translation_work_and_refreshes_the_source() -> None:
    # Restarting the daemon re-runs this import; it used to delete content/psalms first,
    # taking every uncommitted translation, analysis and audit record with it.
    try:
        ingest_service.import_vendored_psalms()
        unit = registry_service.load_unit("ps001.v002.a")
        raw = registry_service.read_json(registry_service.unit_path("ps001.v002.a"))
        rendering = {"rendering_id": "rnd.ps001.v002.a.lyric.alt.0001", "text": "his joy"}
        raw["renderings"] = [rendering]
        raw["verse_notes"] = [{"note_id": "vn.ps001.v002.a.0001", "text": "keep the and"}]
        raw["audit_records"] = [{"audit_id": "aud.ps001.v002.a.0001"}]
        raw["status"] = "reviewed"
        raw["tokens"][0]["display_gloss"] = "stale gloss"
        registry_service.write_json(registry_service.unit_path("ps001.v002.a"), raw)
        meta_path = registry_service.psalm_dir("ps001") / "ps001.meta.json"
        meta = registry_service.read_json(meta_path)
        meta["translation_guidance"] = "target 6/8 meter"
        meta["analyses"] = [{"psalm_analysis_id": "pan.ps001.0001"}]
        registry_service.write_json(meta_path, meta)

        ingest_service.import_vendored_psalms()

        after = registry_service.read_json(registry_service.unit_path("ps001.v002.a"))
        assert after["renderings"] == [rendering]
        assert after["verse_notes"][0]["text"] == "keep the and"
        assert after["audit_records"][0] == {"audit_id": "aud.ps001.v002.a.0001"}
        # Refreshing the stale gloss is a content change, so it is audited.
        refresh = after["audit_records"][1]
        assert refresh["audit_id"] == "aud.ps001.v002.a.0002"
        assert refresh["change_type"] == "import"
        assert refresh["before_hash"] != refresh["after_hash"]
        assert len(after["audit_records"]) == 2
        assert after["status"] == "reviewed"
        # What the corpus owns is refreshed.
        assert after["tokens"][0]["display_gloss"] == unit["tokens"][0]["display_gloss"]
        assert after["source_hebrew"] == unit["source_hebrew"]
        meta_after = registry_service.read_json(meta_path)
        assert meta_after["translation_guidance"] == "target 6/8 meter"
        assert meta_after["analyses"] == [{"psalm_analysis_id": "pan.ps001.0001"}]
        assert meta_after["unit_ids"] == meta["unit_ids"]
    finally:
        bootstrap_fixture_repo()


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
        assert manifests["lxx"]["allowed_for_generation"] is True
        assert manifests["lxx"]["source_language"] == "grc"
        assert manifests["kjv"]["license"] == "Public Domain"
        assert manifests["kjv"]["allowed_for_generation"] is False
        assert manifests["asv"]["allowed_for_export"] is True
        assert manifests["web"]["import_hash"] != "fixture-web"

        verse_two = registry_service.load_unit("ps001.v002.a")
        witnesses = {item["source_id"]: item for item in verse_two["witnesses"]}
        assert set(witnesses) == {"kjv", "asv", "web", "lxx"}
        assert witnesses["kjv"]["text"].startswith("But his delight")
        assert "law of the LORD" in witnesses["kjv"]["text"]
        assert witnesses["asv"]["text"].startswith("But his delight is in the law")
        assert witnesses["web"]["text"].startswith("but his delight is in")
        assert "On his law he meditates day and night" in witnesses["web"]["text"]
        assert witnesses["lxx"]["language"] == "grc"
        assert witnesses["lxx"]["witness_role"] == "septuagint_greek"
        assert witnesses["lxx"]["source_version"] == "macula-lxx-2026.04"
        assert witnesses["lxx"]["text"]

        first_token = verse_two["tokens"][0]
        second_token = verse_two["tokens"][1]
        assert first_token["greek"] is not None
        assert second_token["greek"] is not None
        assert first_token["gloss_parts"] == ["(dm)"]
        assert first_token["display_gloss"] == "but"
        assert first_token["compiler_features"]["conjunction_role"] == "contrastive"
        assert second_token["gloss_parts"] == ["(if)"]
        assert second_token["display_gloss"] == "rather"
        assert "(" not in first_token["display_gloss"]
        assert "(" not in second_token["display_gloss"]
    finally:
        bootstrap_fixture_repo()


def test_ketiv_reads_as_its_qere_and_later_words_keep_their_own_enrichment() -> None:
    # MACULA numbers each qere word after its ketiv and has nothing at the ketiv's number;
    # OSHB puts the qere in a note. Joining on the OSHB position shifted every later gloss
    # back one word, so the Selah of Psalm 24:6 read "O Jacob".
    oshb = full_psalm_import_service._load_oshb_tokens()
    macula = full_psalm_import_service._load_macula_words()

    def glosses(psalm: int, verse: int) -> list[str | None]:
        unit = full_psalm_import_service._build_unit(
            psalm, verse, "", oshb[(psalm, verse)], macula, {}
        )
        assert unit["token_ids"] == [
            f"ps{psalm:03d}.v{verse:03d}.t{index:03d}"
            for index in range(1, len(oshb[(psalm, verse)]) + 1)
        ]
        return [token["display_gloss"] for token in unit["tokens"]]

    # t003 is the ketiv דרשו.
    assert glosses(24, 6) == [
        "this",
        "is the generation",
        "of those who seek him",
        "those who seek",
        "(of) your face",
        "O Jacob",
        "Selah",
    ]
    # Two ketivs in one verse; the second (t005) is read as two qere words.
    assert glosses(10, 10) == [
        "he is crushed",
        "he is bowed down",
        "and he falls",
        "among ones his mighty",
        "an army of disheartened people",
    ]
