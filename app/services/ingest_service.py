from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from app.services import audit_service, registry_service


HEBREW_MARKS_RE = re.compile(r"[\u0591-\u05C7]")

OSHB_FIELDS = ("lemma", "strong", "morph_code", "morph_readable", "part_of_speech", "stem")
MACULA_FIELDS = ("syntax_role", "semantic_role", "referent", "word_sense")
ENRICHMENT_FIELDS = {"oshb": OSHB_FIELDS, "macula": MACULA_FIELDS}
STEM_MAP = {
    "q": "qal",
    "N": "niphal",
    "p": "piel",
    "P": "pual",
    "h": "hiphil",
    "H": "hophal",
    "t": "hithpael",
}
MISSING_ENRICHMENT_OVERRIDES = {
    "ps019.v001.t002": {"macula": ["referent"]},
}


FIXTURE_UNITS: list[dict[str, Any]] = [
    {
        "psalm_id": "ps001",
        "unit_id": "ps001.v001.a",
        "ref": "Psalm 1:1a",
        "segmentation_type": "colon",
        "source_hebrew": "אַשְׁרֵי הָאִישׁ",
        "source_transliteration": "ashrei ha-ish",
        "concept_ids": ["cpt.ps001.v001.a.0001"],
        "status": "under_review",
        "current_layer_state": {"locked_layers": ["gloss"], "latest_layer": "literal"},
        "canonical_rendering_ids": ["rnd.ps001.v001.a.gloss.can.0001", "rnd.ps001.v001.a.literal.can.0001"],
        "alternate_rendering_ids": ["rnd.ps001.v001.a.lyric.alt.0001"],
        "audit_ids": [],
        "issue_links": [],
        "pr_links": [],
        "seed_tokens": [
            {
                "surface": "אַשְׁרֵי",
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
                "same_psalm_occurrence_refs": ["Psalm 1:1b"],
                "corpus_occurrence_refs": ["Psalm 32:1"],
                "psalms_occurrence_refs": ["Psalm 32:1"],
            },
            {
                "surface": "הָאִישׁ",
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
                "same_psalm_occurrence_refs": ["Psalm 1:1b"],
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
                "text": "Blessed - the man",
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
                "drift_flags": [
                    {
                        "code": "semantic_overcompression",
                        "severity": "low",
                        "confidence": 0.5,
                        "message": "semantic overcompression",
                    },
                    {
                        "code": "parallelism_break",
                        "severity": "medium",
                        "confidence": 0.72,
                        "message": "Lyric line compresses a multi-span source into a single span.",
                    },
                ],
                "metrics": {
                    "syllables": 6,
                    "syllable_count": 6,
                    "stress_approximation": 0.75,
                    "line_length": 4,
                    "repetition_score": 0.0,
                    "singability_score": 0.56,
                    "parallelism_preservation": 0.84,
                    "parallelism_preservation_score": 0.59,
                },
                "rationale": "Compact singable alternate.",
                "provenance": {"source_ids": ["uxlc", "oshb", "macula"], "generator": "human-seed"},
            },
        ],
        "audit_records": [],
        "review_decisions": [
            {
                "decision_id": "rev.ps001.v001.a.0001",
                "target_id": "rnd.ps001.v001.a.gloss.can.0001",
                "reviewer_role": "Hebrew reviewer",
                "reviewer": "seed-reviewer-1",
                "decision": "approve",
                "notes": "Gloss line matches lexical payload.",
                "timestamp": "2026-04-09T00:00:00Z",
            },
            {
                "decision_id": "rev.ps001.v001.a.0002",
                "target_id": "rnd.ps001.v001.a.literal.can.0001",
                "reviewer_role": "Hebrew reviewer",
                "reviewer": "seed-reviewer-1",
                "decision": "approve",
                "notes": "Literal line acceptable.",
                "timestamp": "2026-04-09T00:01:00Z",
            },
            {
                "decision_id": "rev.ps001.v001.a.0003",
                "target_id": "rnd.ps001.v001.a.literal.can.0001",
                "reviewer_role": "alignment reviewer",
                "reviewer": "seed-reviewer-2",
                "decision": "approve",
                "notes": "Alignment coverage complete.",
                "timestamp": "2026-04-09T00:02:00Z",
            },
            {
                "decision_id": "rev.ps001.v001.a.0004",
                "target_id": "rnd.ps001.v001.a.lyric.alt.0001",
                "reviewer_role": "lyric reviewer",
                "reviewer": "seed-reviewer-3",
                "decision": "approve",
                "notes": "Alternate remains singable and traceable.",
                "timestamp": "2026-04-09T00:03:00Z",
            },
            {
                "decision_id": "rev.ps001.v001.a.0005",
                "target_id": "rnd.ps001.v001.a.literal.can.0001",
                "reviewer_role": "release reviewer",
                "reviewer": "release-seed",
                "decision": "approve",
                "notes": "Unit cleared for release bundle.",
                "timestamp": "2026-04-09T00:04:00Z",
            },
            {
                "decision_id": "rev.ps001.v001.a.0006",
                "target_id": "rnd.ps001.v001.a.gloss.can.0001",
                "reviewer_role": "alignment reviewer",
                "reviewer": "seed-reviewer-2",
                "decision": "approve",
                "notes": "Gloss alignment coverage is complete.",
                "timestamp": "2026-04-09T00:05:00Z",
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
        "concept_ids": ["cpt.ps019.v001.a.0001"],
        "status": "draft",
        "current_layer_state": {"locked_layers": [], "latest_layer": "literal"},
        "canonical_rendering_ids": ["rnd.ps019.v001.a.literal.can.0001"],
        "alternate_rendering_ids": [],
        "audit_ids": [],
        "issue_links": [],
        "pr_links": [],
        "seed_tokens": [
            {
                "surface": "הַשָּׁמַיִם",
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
                "same_psalm_occurrence_refs": [],
                "corpus_occurrence_refs": ["Genesis 1:1"],
                "psalms_occurrence_refs": ["Psalm 8:3"],
            },
            {
                "surface": "מְסַפְּרִים",
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
                "same_psalm_occurrence_refs": [],
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
        "review_decisions": [
            {
                "decision_id": "rev.ps019.v001.a.0001",
                "target_id": "rnd.ps019.v001.a.literal.can.0001",
                "reviewer_role": "Hebrew reviewer",
                "reviewer": "seed-reviewer-1",
                "decision": "approve",
                "notes": "Literal line preserves the clause faithfully.",
                "timestamp": "2026-04-09T00:10:00Z",
            },
            {
                "decision_id": "rev.ps019.v001.a.0002",
                "target_id": "rnd.ps019.v001.a.literal.can.0001",
                "reviewer_role": "alignment reviewer",
                "reviewer": "seed-reviewer-2",
                "decision": "approve",
                "notes": "Grouped span coverage is complete.",
                "timestamp": "2026-04-09T00:11:00Z",
            },
            {
                "decision_id": "rev.ps019.v001.a.0003",
                "target_id": "rnd.ps019.v001.a.literal.can.0001",
                "reviewer_role": "release reviewer",
                "reviewer": "release-seed",
                "decision": "approve",
                "notes": "Unit cleared for release bundle.",
                "timestamp": "2026-04-09T00:12:00Z",
            },
        ],
        "witnesses": [],
    },
    {
        "psalm_id": "ps023",
        "unit_id": "ps023.v001.a",
        "ref": "Psalm 23:1a",
        "segmentation_type": "colon",
        "source_hebrew": "יְהוָה רֹעִי",
        "source_transliteration": "yhwh ro'i",
        "concept_ids": ["cpt.ps023.v001.a.0001"],
        "status": "under_review",
        "current_layer_state": {"locked_layers": ["gloss", "literal"], "latest_layer": "lyric"},
        "canonical_rendering_ids": ["rnd.ps023.v001.a.literal.can.0001"],
        "alternate_rendering_ids": ["rnd.ps023.v001.a.lyric.alt.0001"],
        "audit_ids": [],
        "issue_links": [],
        "pr_links": [],
        "seed_tokens": [
            {
                "surface": "יְהוָה",
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
                "same_psalm_occurrence_refs": [],
                "corpus_occurrence_refs": ["Genesis 2:4"],
                "psalms_occurrence_refs": ["Psalm 27:1"],
            },
            {
                "surface": "רֹעִי",
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
                "same_psalm_occurrence_refs": [],
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
                "drift_flags": [
                    {
                        "code": "editorial_expansion",
                        "severity": "medium",
                        "confidence": 0.5,
                        "message": "editorial expansion",
                    }
                ],
                "metrics": {
                    "syllables": 7,
                    "syllable_count": 7,
                    "stress_approximation": 0.58,
                    "line_length": 6,
                    "repetition_score": 0.0,
                    "singability_score": 0.74,
                    "parallelism_preservation_score": 0.81,
                },
                "rationale": "Alternate candidate for common meter development.",
                "provenance": {"source_ids": ["uxlc", "oshb", "macula"], "generator": "human-seed"},
            },
        ],
        "audit_records": [],
        "review_decisions": [
            {
                "decision_id": "rev.ps023.v001.a.0001",
                "target_id": "rnd.ps023.v001.a.literal.can.0001",
                "reviewer_role": "Hebrew reviewer",
                "reviewer": "seed-reviewer-1",
                "decision": "approve",
                "notes": "Canonical line is faithful to the source naming policy.",
                "timestamp": "2026-04-09T00:20:00Z",
            },
            {
                "decision_id": "rev.ps023.v001.a.0002",
                "target_id": "rnd.ps023.v001.a.literal.can.0001",
                "reviewer_role": "alignment reviewer",
                "reviewer": "seed-reviewer-2",
                "decision": "approve",
                "notes": "Predicate sentence alignment is complete.",
                "timestamp": "2026-04-09T00:21:00Z",
            },
            {
                "decision_id": "rev.ps023.v001.a.0003",
                "target_id": "rnd.ps023.v001.a.literal.can.0001",
                "reviewer_role": "release reviewer",
                "reviewer": "release-seed",
                "decision": "approve",
                "notes": "Unit cleared for release bundle.",
                "timestamp": "2026-04-09T00:22:00Z",
            },
        ],
        "witnesses": [],
    },
    {
        "psalm_id": "ps051",
        "unit_id": "ps051.v001.a",
        "ref": "Psalm 51:1a",
        "segmentation_type": "colon",
        "source_hebrew": "חָנֵּנִי אֱלֹהִים",
        "source_transliteration": "chaneni elohim",
        "concept_ids": ["cpt.ps051.v001.a.0001"],
        "status": "under_review",
        "current_layer_state": {"locked_layers": ["gloss"], "latest_layer": "literal"},
        "canonical_rendering_ids": ["rnd.ps051.v001.a.literal.can.0001"],
        "alternate_rendering_ids": ["rnd.ps051.v001.a.phrase.alt.0001"],
        "audit_ids": [],
        "issue_links": [],
        "pr_links": [],
        "seed_tokens": [
            {
                "surface": "חָנֵּנִי",
                "transliteration": "chaneni",
                "lemma": "חנן",
                "strong": "H2603",
                "morph_code": "Vqami+Sp1cs",
                "morph_readable": "verb qal imperative masculine singular + suffix first common singular",
                "part_of_speech": "verb",
                "syntax_role": "predicate",
                "semantic_role": "petition",
                "referent": "me",
                "word_sense": "show favor/be gracious",
                "same_psalm_occurrence_refs": [],
                "corpus_occurrence_refs": ["Psalm 86:3"],
                "psalms_occurrence_refs": ["Psalm 86:3"],
            },
            {
                "surface": "אֱלֹהִים",
                "transliteration": "elohim",
                "lemma": "אלהים",
                "strong": "H430",
                "morph_code": "Ncmpa",
                "morph_readable": "noun masculine plural absolute",
                "part_of_speech": "noun",
                "syntax_role": "vocative",
                "semantic_role": "deity",
                "referent": "God",
                "word_sense": "God",
                "same_psalm_occurrence_refs": [],
                "corpus_occurrence_refs": ["Genesis 1:1"],
                "psalms_occurrence_refs": ["Psalm 50:6"],
            },
        ],
        "alignments": [
            {
                "alignment_id": "aln.ps051.v001.a.literal.0001",
                "unit_id": "ps051.v001.a",
                "layer": "literal",
                "source_token_ids": ["ps051.v001.t001", "ps051.v001.t002"],
                "target_span_ids": ["spn.ps051.v001.a.literal.0001"],
                "alignment_type": "grouped",
                "confidence": 0.97,
                "created_by": "seed",
                "created_via": "fixture",
                "notes": "Imperative petition preserved as a single English span.",
            }
        ],
        "renderings": [
            {
                "rendering_id": "rnd.ps051.v001.a.literal.can.0001",
                "unit_id": "ps051.v001.a",
                "layer": "literal",
                "status": "canonical",
                "text": "Be gracious to me, O God",
                "style_tags": ["literal", "study_literal"],
                "target_spans": [
                    {"span_id": "spn.ps051.v001.a.literal.0001", "text": "Be gracious to me, O God", "token_start": 0, "token_end": 5}
                ],
                "alignment_ids": ["aln.ps051.v001.a.literal.0001"],
                "drift_flags": [],
                "metrics": {"syllables": 8},
                "rationale": "Literal petition line for golden coverage.",
                "provenance": {"source_ids": ["uxlc", "oshb", "macula"], "generator": "human-seed"},
            },
            {
                "rendering_id": "rnd.ps051.v001.a.phrase.alt.0001",
                "unit_id": "ps051.v001.a",
                "layer": "phrase",
                "status": "proposed",
                "text": "God, show me mercy",
                "style_tags": ["phrase", "formal_liturgical"],
                "target_spans": [
                    {"span_id": "spn.ps051.v001.a.phrase.0001", "text": "God, show me mercy", "token_start": 0, "token_end": 3}
                ],
                "alignment_ids": ["aln.ps051.v001.a.literal.0001"],
                "drift_flags": [],
                "metrics": {"syllables": 5},
                "rationale": "Reviewable alternate with compact phrasing.",
                "provenance": {"source_ids": ["uxlc", "oshb", "macula"], "generator": "human-seed"},
            },
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


def _normalized_hebrew(text: str) -> str:
    return HEBREW_MARKS_RE.sub("", text)


def _token_id(unit_id: str, index: int) -> str:
    head = ".".join(unit_id.split(".")[:2])
    return f"{head}.t{index:03d}"


def _derive_stem(morph_code: str | None, part_of_speech: str | None) -> str | None:
    if not morph_code or part_of_speech != "verb" or not morph_code.startswith("V") or len(morph_code) < 2:
        return None
    return STEM_MAP.get(morph_code[1])


def _source_payload(token_id: str, source_id: str, seed_token: dict[str, Any]) -> dict[str, Any]:
    removed = set(MISSING_ENRICHMENT_OVERRIDES.get(token_id, {}).get(source_id, []))
    field_values: dict[str, Any] = {}
    for field in ENRICHMENT_FIELDS[source_id]:
        if field == "stem":
            value = _derive_stem(seed_token.get("morph_code"), seed_token.get("part_of_speech"))
        else:
            value = seed_token.get(field)
        if field in removed:
            value = None
        field_values[field] = value
    return field_values


def _applicable_fields(source_id: str, seed_token: dict[str, Any]) -> tuple[str, ...]:
    if source_id == "oshb" and seed_token.get("part_of_speech") != "verb":
        return tuple(field for field in OSHB_FIELDS if field != "stem")
    return ENRICHMENT_FIELDS[source_id]


def _source_status(available_fields: list[str], applicable_fields: tuple[str, ...]) -> str:
    if not applicable_fields:
        return "missing"
    if not available_fields:
        return "missing"
    if len(available_fields) == len(applicable_fields):
        return "complete"
    return "partial"


def _build_enriched_token(unit: dict[str, Any], seed_token: dict[str, Any], position: int) -> dict[str, Any]:
    token_id = _token_id(unit["unit_id"], position)
    oshb_payload = _source_payload(token_id, "oshb", seed_token)
    macula_payload = _source_payload(token_id, "macula", seed_token)
    token: dict[str, Any] = {
        "token_id": token_id,
        "ref": f"{unit['ref']}#{position}",
        "surface": seed_token["surface"],
        "normalized": _normalized_hebrew(seed_token["surface"]),
        "transliteration": seed_token.get("transliteration"),
        "lemma": oshb_payload.get("lemma"),
        "strong": oshb_payload.get("strong"),
        "morph_code": oshb_payload.get("morph_code"),
        "morph_readable": oshb_payload.get("morph_readable"),
        "part_of_speech": oshb_payload.get("part_of_speech"),
        "stem": oshb_payload.get("stem"),
        "syntax_role": macula_payload.get("syntax_role"),
        "semantic_role": macula_payload.get("semantic_role"),
        "referent": macula_payload.get("referent"),
        "word_sense": macula_payload.get("word_sense"),
        "occurrence_index": 1,
        "same_psalm_occurrence_refs": seed_token.get("same_psalm_occurrence_refs", []),
        "corpus_occurrence_refs": seed_token.get("corpus_occurrence_refs", []),
        "psalms_occurrence_refs": seed_token.get("psalms_occurrence_refs", []),
    }
    enrichment_sources: dict[str, dict[str, Any]] = {}
    missing_enrichments: list[str] = []
    for source_id, payload in (("oshb", oshb_payload), ("macula", macula_payload)):
        applicable_fields = _applicable_fields(source_id, seed_token)
        available_fields = [field for field in applicable_fields if payload.get(field) is not None]
        missing_fields = [field for field in applicable_fields if payload.get(field) is None]
        enrichment_sources[source_id] = {
            "status": _source_status(available_fields, applicable_fields),
            "available_fields": available_fields,
            "missing_fields": missing_fields,
        }
        missing_enrichments.extend(f"{source_id}:{field}" for field in missing_fields)
    token["enrichment_sources"] = enrichment_sources
    token["missing_enrichments"] = missing_enrichments
    return token


def _tokenize_and_enrich(unit: dict[str, Any]) -> dict[str, Any]:
    token_surfaces = unit["source_hebrew"].split()
    seed_tokens = unit.pop("seed_tokens")
    if len(token_surfaces) != len(seed_tokens):
        raise ValueError(f"Tokenization mismatch for {unit['unit_id']}: {len(token_surfaces)} surfaces vs {len(seed_tokens)} seed tokens")
    enriched_tokens = []
    for index, (surface, seed_token) in enumerate(zip(token_surfaces, seed_tokens, strict=True), start=1):
        seed_payload = {**seed_token, "surface": surface}
        enriched_tokens.append(_build_enriched_token(unit, seed_payload, index))
    unit["token_ids"] = [token["token_id"] for token in enriched_tokens]
    unit["tokens"] = enriched_tokens
    return unit


def import_fixture_psalms() -> list[dict[str, Any]]:
    registry_service.bootstrap_project()
    imported: list[dict[str, Any]] = []
    psalm_groups: dict[str, list[dict[str, Any]]] = {}
    for unit in FIXTURE_UNITS:
        seeded = _tokenize_and_enrich(deepcopy(unit))
        initial_hash = registry_service.file_hash({"unit_id": seeded["unit_id"], "seed": True})
        final_hash = registry_service.file_hash(seeded)
        fixture_timestamp = f"2026-04-09T00:00:{len(imported):02d}Z"
        audit_service.create_audit_record(
            seeded,
            before_hash=initial_hash,
            after_hash=final_hash,
            summary="Seed fixture unit",
            rationale="Bootstrap milestone fixtures with OSHB and MACULA enrichment",
            created_by="import-psalms",
            change_type="create",
            created_at=fixture_timestamp,
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
        updated = False
        for token in unit.get("tokens", []):
            if token.get("morph_readable"):
                continue
            token["morph_readable"] = token.get("morph_code", "unknown")
            if "oshb:morph_readable" in token.get("missing_enrichments", []):
                token["missing_enrichments"] = [item for item in token["missing_enrichments"] if item != "oshb:morph_readable"]
                source = token.setdefault("enrichment_sources", {}).setdefault(
                    "oshb",
                    {"status": "partial", "available_fields": [], "missing_fields": []},
                )
                if "morph_readable" not in source["available_fields"]:
                    source["available_fields"].append("morph_readable")
                source["missing_fields"] = [field for field in source["missing_fields"] if field != "morph_readable"]
                source["status"] = _source_status(
                    source["available_fields"],
                    tuple(field for field in _applicable_fields("oshb", token) if field != "morph_readable" or token.get("morph_readable") is not None),
                )
            updated = True
        if updated:
            registry_service.save_unit(unit)
            count += 1
    return count
