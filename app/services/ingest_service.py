from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services import audit_service, registry_service


FIXTURE_UNITS: list[dict[str, Any]] = [
    {
        "psalm_id": "ps001",
        "unit_id": "ps001.v001.a",
        "ref": "Psalm 1:1a",
        "segmentation_type": "colon",
        "source_hebrew": "אַשְׁרֵי הָאִישׁ",
        "source_transliteration": "ashrei ha-ish",
        "token_ids": ["ps001.v001.t001", "ps001.v001.t002"],
        "concept_ids": ["cpt.ps001.v001.a.0001"],
        "status": "under_review",
        "current_layer_state": {"locked_layers": ["gloss"], "latest_layer": "literal"},
        "canonical_rendering_ids": ["rnd.ps001.v001.a.gloss.can.0001", "rnd.ps001.v001.a.literal.can.0001"],
        "alternate_rendering_ids": ["rnd.ps001.v001.a.lyric.alt.0001"],
        "audit_ids": [],
        "issue_links": [],
        "pr_links": [],
        "tokens": [
            {
                "token_id": "ps001.v001.t001",
                "ref": "Psalm 1:1a#1",
                "surface": "אַשְׁרֵי",
                "normalized": "אשרי",
                "transliteration": "ashrei",
                "lemma": "אשר",
                "strong": "H835",
                "morph_code": "Tm",
                "morph_readable": "interjection of blessing",
                "part_of_speech": "particle",
                "syntax_role": "predicate",
                "semantic_role": "blessing",
                "referent": "the righteous",
                "word_sense": "fortunate/blessed",
                "occurrence_index": 1,
                "corpus_occurrence_refs": ["Psalm 32:1"],
                "psalms_occurrence_refs": ["Psalm 32:1"],
            },
            {
                "token_id": "ps001.v001.t002",
                "ref": "Psalm 1:1a#2",
                "surface": "הָאִישׁ",
                "normalized": "האיש",
                "transliteration": "ha-ish",
                "lemma": "איש",
                "strong": "H376",
                "morph_code": "Td/Ncmsa",
                "morph_readable": "article + noun masculine singular absolute",
                "part_of_speech": "noun",
                "syntax_role": "subject",
                "semantic_role": "agent",
                "referent": "the man",
                "word_sense": "man/person",
                "occurrence_index": 1,
                "corpus_occurrence_refs": ["Psalm 37:23"],
                "psalms_occurrence_refs": ["Psalm 37:23"],
            },
        ],
        "alignments": [
            {
                "alignment_id": "aln.ps001.v001.a.gloss.0001",
                "unit_id": "ps001.v001.a",
                "layer": "gloss",
                "source_token_ids": ["ps001.v001.t001"],
                "target_span_ids": ["spn.ps001.v001.a.gloss.0001"],
                "alignment_type": "direct",
                "confidence": 0.97,
                "created_by": "seed",
                "created_via": "fixture",
                "notes": "ashrei -> blessed",
            },
            {
                "alignment_id": "aln.ps001.v001.a.gloss.0002",
                "unit_id": "ps001.v001.a",
                "layer": "gloss",
                "source_token_ids": ["ps001.v001.t002"],
                "target_span_ids": ["spn.ps001.v001.a.gloss.0002"],
                "alignment_type": "direct",
                "confidence": 0.95,
                "created_by": "seed",
                "created_via": "fixture",
                "notes": "ha-ish -> the man",
            },
        ],
        "renderings": [
            {
                "rendering_id": "rnd.ps001.v001.a.gloss.can.0001",
                "unit_id": "ps001.v001.a",
                "layer": "gloss",
                "status": "canonical",
                "text": "Blessed — the man",
                "style_tags": ["gloss", "study_literal"],
                "target_spans": [
                    {"span_id": "spn.ps001.v001.a.gloss.0001", "text": "Blessed", "token_start": 0, "token_end": 0},
                    {"span_id": "spn.ps001.v001.a.gloss.0002", "text": "the man", "token_start": 2, "token_end": 3},
                ],
                "alignment_ids": ["aln.ps001.v001.a.gloss.0001", "aln.ps001.v001.a.gloss.0002"],
                "drift_flags": [],
                "metrics": {"tokens": 3},
                "rationale": "Gloss-level lexical rendering.",
                "provenance": {"source_ids": ["uxlc", "oshb", "macula"], "generator": "human-seed"},
            },
            {
                "rendering_id": "rnd.ps001.v001.a.literal.can.0001",
                "unit_id": "ps001.v001.a",
                "layer": "literal",
                "status": "canonical",
                "text": "Happy is the man",
                "style_tags": ["literal", "study_literal"],
                "target_spans": [
                    {"span_id": "spn.ps001.v001.a.literal.0001", "text": "Happy", "token_start": 0, "token_end": 0},
                    {"span_id": "spn.ps001.v001.a.literal.0002", "text": "the man", "token_start": 2, "token_end": 3},
                ],
                "alignment_ids": ["aln.ps001.v001.a.gloss.0001", "aln.ps001.v001.a.gloss.0002"],
                "drift_flags": [],
                "metrics": {"syllables": 5},
                "rationale": "Literal English line for review.",
                "provenance": {"source_ids": ["uxlc", "oshb", "macula"], "generator": "human-seed"},
            },
            {
                "rendering_id": "rnd.ps001.v001.a.lyric.alt.0001",
                "unit_id": "ps001.v001.a",
                "layer": "lyric",
                "status": "accepted_as_alternate",
                "text": "Blessed is the one",
                "style_tags": ["lyric", "formal_liturgical"],
                "target_spans": [
                    {"span_id": "spn.ps001.v001.a.lyric.0001", "text": "Blessed is the one", "token_start": 0, "token_end": 3}
                ],
                "alignment_ids": ["aln.ps001.v001.a.gloss.0001", "aln.ps001.v001.a.gloss.0002"],
                "drift_flags": ["semantic_overcompression:low"],
                "metrics": {"syllables": 5, "parallelism_preservation": 0.84},
                "rationale": "Compact singable alternate.",
                "provenance": {"source_ids": ["uxlc", "oshb", "macula"], "generator": "human-seed"},
            },
        ],
        "audit_records": [],
        "review_decisions": [
            {
                "decision_id": "rev.ps001.v001.a.0001",
                "target_id": "rnd.ps001.v001.a.literal.can.0001",
                "reviewer_role": "Hebrew reviewer",
                "reviewer": "seed-reviewer-1",
                "decision": "approve",
                "notes": "Literal line acceptable.",
                "timestamp": "2026-04-09T00:00:00Z",
            },
            {
                "decision_id": "rev.ps001.v001.a.0002",
                "target_id": "rnd.ps001.v001.a.literal.can.0001",
                "reviewer_role": "alignment reviewer",
                "reviewer": "seed-reviewer-2",
                "decision": "approve",
                "notes": "Alignment coverage complete.",
                "timestamp": "2026-04-09T00:01:00Z",
            },
        ],
        "witnesses": [
            {
                "source_id": "sefaria",
                "versionTitle": "Fixture Witness",
                "language": "en",
                "ref": "Psalms 1:1",
                "source_url": "https://www.sefaria.org/Psalms.1.1",
                "text": "Optional witness text stored separately.",
            }
        ],
    },
    {
        "psalm_id": "ps019",
        "unit_id": "ps019.v001.a",
        "ref": "Psalm 19:1a",
        "segmentation_type": "colon",
        "source_hebrew": "הַשָּׁמַיִם מְסַפְּרִים",
        "source_transliteration": "ha-shamayim mesapperim",
        "token_ids": ["ps019.v001.t001", "ps019.v001.t002"],
        "concept_ids": ["cpt.ps019.v001.a.0001"],
        "status": "draft",
        "current_layer_state": {"locked_layers": [], "latest_layer": "literal"},
        "canonical_rendering_ids": ["rnd.ps019.v001.a.literal.can.0001"],
        "alternate_rendering_ids": [],
        "audit_ids": [],
        "issue_links": [],
        "pr_links": [],
        "tokens": [
            {
                "token_id": "ps019.v001.t001",
                "ref": "Psalm 19:1a#1",
                "surface": "הַשָּׁמַיִם",
                "normalized": "השמים",
                "transliteration": "ha-shamayim",
                "lemma": "שמים",
                "strong": "H8064",
                "morph_code": "Td/Ncmpa",
                "morph_readable": "article + noun masculine plural absolute",
                "part_of_speech": "noun",
                "syntax_role": "subject",
                "semantic_role": "agent",
                "referent": "heavens",
                "word_sense": "sky/heavens",
                "occurrence_index": 1,
                "corpus_occurrence_refs": ["Genesis 1:1"],
                "psalms_occurrence_refs": ["Psalm 8:3"],
            },
            {
                "token_id": "ps019.v001.t002",
                "ref": "Psalm 19:1a#2",
                "surface": "מְסַפְּרִים",
                "normalized": "מספרים",
                "transliteration": "mesapperim",
                "lemma": "ספר",
                "strong": "H5608",
                "morph_code": "Vprmpa",
                "morph_readable": "verb participle piel masculine plural absolute",
                "part_of_speech": "verb",
                "syntax_role": "predicate",
                "semantic_role": "communication",
                "referent": "heavens",
                "word_sense": "declare/tell",
                "occurrence_index": 1,
                "corpus_occurrence_refs": ["Psalm 71:15"],
                "psalms_occurrence_refs": ["Psalm 71:15"],
            },
        ],
        "alignments": [
            {
                "alignment_id": "aln.ps019.v001.a.literal.0001",
                "unit_id": "ps019.v001.a",
                "layer": "literal",
                "source_token_ids": ["ps019.v001.t001", "ps019.v001.t002"],
                "target_span_ids": ["spn.ps019.v001.a.literal.0001"],
                "alignment_type": "grouped",
                "confidence": 0.96,
                "created_by": "seed",
                "created_via": "fixture",
                "notes": "Predicate phrase rendered together.",
            }
        ],
        "renderings": [
            {
                "rendering_id": "rnd.ps019.v001.a.literal.can.0001",
                "unit_id": "ps019.v001.a",
                "layer": "literal",
                "status": "canonical",
                "text": "The heavens are declaring",
                "style_tags": ["literal", "study_literal"],
                "target_spans": [
                    {"span_id": "spn.ps019.v001.a.literal.0001", "text": "The heavens are declaring", "token_start": 0, "token_end": 3}
                ],
                "alignment_ids": ["aln.ps019.v001.a.literal.0001"],
                "drift_flags": [],
                "metrics": {"syllables": 8},
                "rationale": "Initial literal line.",
                "provenance": {"source_ids": ["uxlc", "oshb", "macula"], "generator": "human-seed"},
            }
        ],
        "audit_records": [],
        "review_decisions": [],
        "witnesses": [],
    },
    {
        "psalm_id": "ps023",
        "unit_id": "ps023.v001.a",
        "ref": "Psalm 23:1a",
        "segmentation_type": "colon",
        "source_hebrew": "יְהוָה רֹעִי",
        "source_transliteration": "yhwh ro'i",
        "token_ids": ["ps023.v001.t001", "ps023.v001.t002"],
        "concept_ids": ["cpt.ps023.v001.a.0001"],
        "status": "under_review",
        "current_layer_state": {"locked_layers": ["gloss", "literal"], "latest_layer": "lyric"},
        "canonical_rendering_ids": ["rnd.ps023.v001.a.literal.can.0001"],
        "alternate_rendering_ids": ["rnd.ps023.v001.a.lyric.alt.0001"],
        "audit_ids": [],
        "issue_links": [],
        "pr_links": [],
        "tokens": [
            {
                "token_id": "ps023.v001.t001",
                "ref": "Psalm 23:1a#1",
                "surface": "יְהוָה",
                "normalized": "יהוה",
                "transliteration": "yhwh",
                "lemma": "יהוה",
                "strong": "H3068",
                "morph_code": "Np",
                "morph_readable": "proper noun divine name",
                "part_of_speech": "proper_noun",
                "syntax_role": "subject",
                "semantic_role": "deity",
                "referent": "the LORD",
                "word_sense": "divine name",
                "occurrence_index": 1,
                "corpus_occurrence_refs": ["Genesis 2:4"],
                "psalms_occurrence_refs": ["Psalm 27:1"],
            },
            {
                "token_id": "ps023.v001.t002",
                "ref": "Psalm 23:1a#2",
                "surface": "רֹעִי",
                "normalized": "רעי",
                "transliteration": "ro'i",
                "lemma": "רעה",
                "strong": "H7462",
                "morph_code": "Ncmsg+Sp1cs",
                "morph_readable": "noun masculine singular construct + suffix first common singular",
                "part_of_speech": "noun",
                "syntax_role": "predicate",
                "semantic_role": "caregiver",
                "referent": "my shepherd",
                "word_sense": "shepherd",
                "occurrence_index": 1,
                "corpus_occurrence_refs": ["Genesis 48:15"],
                "psalms_occurrence_refs": ["Psalm 80:1"],
            },
        ],
        "alignments": [
            {
                "alignment_id": "aln.ps023.v001.a.literal.0001",
                "unit_id": "ps023.v001.a",
                "layer": "literal",
                "source_token_ids": ["ps023.v001.t001", "ps023.v001.t002"],
                "target_span_ids": ["spn.ps023.v001.a.literal.0001"],
                "alignment_type": "grouped",
                "confidence": 0.98,
                "created_by": "seed",
                "created_via": "fixture",
                "notes": "Predicate nominal sentence.",
            }
        ],
        "renderings": [
            {
                "rendering_id": "rnd.ps023.v001.a.literal.can.0001",
                "unit_id": "ps023.v001.a",
                "layer": "literal",
                "status": "canonical",
                "text": "The LORD is my shepherd",
                "style_tags": ["literal", "study_literal"],
                "target_spans": [
                    {"span_id": "spn.ps023.v001.a.literal.0001", "text": "The LORD is my shepherd", "token_start": 0, "token_end": 4}
                ],
                "alignment_ids": ["aln.ps023.v001.a.literal.0001"],
                "drift_flags": [],
                "metrics": {"syllables": 6},
                "rationale": "Literal canonical line.",
                "provenance": {"source_ids": ["uxlc", "oshb", "macula"], "generator": "human-seed"},
            },
            {
                "rendering_id": "rnd.ps023.v001.a.lyric.alt.0001",
                "unit_id": "ps023.v001.a",
                "layer": "lyric",
                "status": "proposed",
                "text": "The LORD, my shepherd, stays near",
                "style_tags": ["lyric", "metered_common_meter"],
                "target_spans": [
                    {"span_id": "spn.ps023.v001.a.lyric.0001", "text": "The LORD, my shepherd, stays near", "token_start": 0, "token_end": 5}
                ],
                "alignment_ids": ["aln.ps023.v001.a.literal.0001"],
                "drift_flags": ["editorial_expansion:medium"],
                "metrics": {"syllables": 8, "singability_score": 0.74},
                "rationale": "Alternate candidate for common meter development.",
                "provenance": {"source_ids": ["uxlc", "oshb", "macula"], "generator": "human-seed"},
            }
        ],
        "audit_records": [],
        "review_decisions": [],
        "witnesses": [],
    },
]


def _psalm_meta(units: list[dict[str, Any]]) -> dict[str, Any]:
    psalm_id = units[0]["psalm_id"]
    return {
        "psalm_id": psalm_id,
        "title": f"Psalm {int(psalm_id[2:])}",
        "unit_ids": [unit["unit_id"] for unit in units],
    }


def import_fixture_psalms() -> list[dict[str, Any]]:
    registry_service.bootstrap_project()
    imported: list[dict[str, Any]] = []
    psalm_groups: dict[str, list[dict[str, Any]]] = {}
    for unit in FIXTURE_UNITS:
        seeded = deepcopy(unit)
        initial_hash = registry_service.file_hash({"unit_id": seeded["unit_id"], "seed": True})
        final_hash = registry_service.file_hash(seeded)
        audit_service.create_audit_record(
            seeded,
            before_hash=initial_hash,
            after_hash=final_hash,
            summary="Seed fixture unit",
            rationale="Bootstrap milestone fixtures",
            created_by="import-psalms",
            change_type="create",
        )
        registry_service.save_unit(seeded)
        psalm_groups.setdefault(seeded["psalm_id"], []).append(seeded)
        imported.append(seeded)
    for psalm_id, units in psalm_groups.items():
        registry_service.write_json(registry_service.psalm_dir(psalm_id) / f"{psalm_id}.meta.json", _psalm_meta(units))
    return imported


def attach_fixture_annotations() -> int:
    count = 0
    for unit in registry_service.list_units():
        if any(token.get("morph_readable") for token in unit.get("tokens", [])):
            count += 1
            continue
        for token in unit.get("tokens", []):
            token["morph_readable"] = token.get("morph_code", "unknown")
        registry_service.save_unit(unit)
        count += 1
    return count
