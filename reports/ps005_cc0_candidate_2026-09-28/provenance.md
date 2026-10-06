# Psalm 5 candidate provenance and review record

## Saved result

- Collection: Bone and Ash (`col.0001`).
- Translation: `tr.ps005.0003` (current membership; generation occurred under
  `tr.ps005.0002`).
- Status: proposed only.
- Lyric renderings: `rnd.ps005.v001.a.lyric.alt.0001`, then
  `rnd.ps005.v002.a.lyric.alt.0003` through `rnd.ps005.v013.a.lyric.alt.0003`.
- Arrangement: `arr.ps005.0003`, “Psalm 5 — At First Light (Hebrew-First Meter Draft).”
- Intended output license: CC0 1.0. This intent is recorded in each new rendering's provenance.
  It is not a legal-clearance claim and does not relabel the repository's source packages.
- No candidate was accepted, approved, published, exported, or promoted.

## Project transfer

On 2026-09-28, the prior imported Psalm 5 translation `tr.ps005.0002` moved intact to
`col.0002` (“Imported translation”), whose output-text license was conservatively set to
All Rights Reserved because the import's source rights are unrecorded. Its twelve imported
renderings, twelve comparison assessments, psalm analysis `anl.ps005.0002`, arrangement
`arr.ps005.0002`, guidance, generation links, and prior audits remain together.

Bone and Ash received the new translation container `tr.ps005.0003`. The thirteen fresh
renderings and `arr.ps005.0003` were reassigned without changing their ids, text, status, source
basis, generation-run links, or provenance. Transfer audits were appended: the translation move
and replacement creation are `aud.ps005.v001.a.0011` and `.0012`; fresh rendering moves are
`.0013` for verse 1 and `.0006` for verses 2–13; the arrangement move is `.0014`; and the fresh
translation-guidance audit is `.0015`. Historical generation-session metadata still records the
translation container in which generation occurred; the transfer audits provide the canonical
membership bridge.

## Isolated generation inputs

The accepted generator session was `cxs.54b5828eac0b`. Existing Psalm 5 English renderings,
translation guidance, published English witnesses, old song words, and source enrichments were not
supplied to the generator. The arrangement's saved guidance snapshot says this explicitly; the exact
submitted prompts are authoritative and are preserved in `generation_prompts.json`.

Allowed source:

- UXLC biblical Hebrew, pinned repository version `vendored-2026.04`.
- Repository import SHA-256:
  `420930bdb5275e6fe79533116e9ff2b61e1881a7d38e299c85b6314ecd641c1d`.
- Psalm 5 qere reading-packet SHA-256:
  `f325b532d1b19dc34fa17738c3ec1012eaf6e7eb526b6653908de1fa4e8b1b2e`.
- The repository manifest marks this source locally generation-allowed. The tanach.us notice offers
  the biblical Hebrew text for copying/use without restriction; that statement is not generalized to
  other site files or ancillary metadata.

Excluded from generation:

- OSHB morphology and lexical metadata.
- Macula morphology, syntax, glosses, and related enrichments.
- LXX/Greek material.
- KJV, ASV, WEB, modern English editions, stored AlephTav English renderings, inherited Psalm 5/6
  prompt examples, and the old vocal transcript.

Psalm 5:9 source correction:

- The canonical imported unit omits the UXLC ketiv/qere node because the importer reads word nodes
  only. The isolated reading packet restored qere `הַיְשַׁ֖ר` and retained ketiv `הושר` in the
  rationale. The canonical source file was not repaired or edited in this task.

## Accepted generation lineage

| Stage | Run | Revision of | Prompt SHA-256 | Result |
|---|---|---|---|---|
| Fresh literal baseline | `cxr.c6ebec48edb4` | `cxr.8493be871a12` | `f47beeb02e88e3c01bf713179a87541b272584ea5e9fce1971f14b63f4bc7251` | Completed; isolation validation passed; retained in run cache, not saved as content |
| Corrected lyric | `cxr.fc5ebd4220b1` | `cxr.117b1f997f08` | `fe2db6b75606024aafb87e68c178c4db0088e9242bfa28196d85976fb916991d` | Completed; isolation validation passed; 13 proposed renderings saved |
| Final arrangement | `cxr.0791c0203810` | `cxr.da191c26cba6` | `0f6378f63c442e797234ebf89d5501db52156018f62461939ec3ea3963b21e95` | Completed; isolation validation passed; proposed arrangement saved |

Provider/model: Codex app-server provider, `gpt-6-astra`. Exact base instructions and all accepted
input prompts are in `generation_prompts.json`. Rejected or superseded run ids, prompt hashes, and
errors are indexed there as well. The derived session cache retains their full submitted prompts.

The first literal attempt changed one Hebrew pointing mark in a source anchor and was rejected before
save. The first lyric/arrangement chain was also left unsaved after Hebrew, overlap, and meter audits
found correctable issues. Corrections were made through new provider runs; generated wording was not
hand-edited into content.

## Meter source and final audit

- Structural source: existing `arr.ps005.0002`, numeric/structural data only.
- Meter artifact: `meter_target.json`.
- Meter artifact SHA-256:
  `eb7f9d44dd82b08b18f081a2c5ccb90e0c5d160c8841351ee70df5703ec23881`.
- The old arrangement wording was not placed in the meter artifact or any generation prompt.

Final arrangement audit:

- 13 sections, 55 records, 53 vocal slots, and 2 instrumental directions.
- Voice mapping 53/53; delivery mapping 16/16.
- Psalm 5:2–13 token coverage 106/106; unknown tokens 0.
- Superscription omission coverage 5/5; a separate fresh lyric candidate exists for it.
- 15/15 tag/echo slots are token and word subsets of their parent lines.
- Source-boundary mismatches 0; non-null `repeat_of` values 0.
- 36/53 slots are within the target syllable range; 40/53 are within the target stress range;
  30/53 match both exactly.
- Claimed total is 362 syllables versus target 344–351. The app heuristic is 367 versus the inherited
  UI total 356.
- No slot differs by more than ±2 syllables or ±1 stress. The Bridge is the main remaining audition
  debt: all four slots miss at least one numeric target.

These counts are text heuristics, not verified musical scansion.

## User-supplied vocal stem

Only this explicitly authorized file was examined:

`D:\Psalms\Piano Psalms\Psalm 5 - Every Morning - Piano Stems\Psalm 5 - Every Morning - Piano (Vocals).wav`

- Before/after SHA-256:
  `c9c517ba3ea3b256eaa44e42406b2664b5cdd5fa36e707cbe1a87a0418c3e84d`.
- Format: 264.680 seconds, stereo, 48,000 Hz, 16-bit PCM.
- Method: 20 ms stereo RMS frames every 10 ms, reference gate −40 dBFS, gaps up to 0.40 s joined,
  with −35/−45 dBFS sensitivity checks.
- Fifteen threshold-dependent activity islands were measured. They are not lyric slots.
- No transcript or old lyric words entered the generator.
- Available local tooling could not reliably verify word alignment, sung syllables, linguistic stress,
  held notes, melodic repetitions, tempo, or exact melody fit.

See `vocal_stem_timing.md` and `vocal_activity_regions.csv` for the retained numeric evidence and
method limits. Exact performance fit remains a user listening check.

## Hebrew fidelity review

Independent review verdict: pass, with disclosed low-severity liberties.

- The prior Psalm 5:10 ungrammatical plural and Psalm 5:11 collapse of two Hebrew roots were corrected.
- Psalm 5:9 uses the qere and restores the hostile force of the watchers without adding a scene.
- Psalm 5:12's repeated English “shelter” consolidates two distinct Hebrew roots and “delight” is less
  exuberant than “exult”; both are low-severity lyric choices, not hidden omissions.
- `Yahweh` is explicitly recorded as an uncertain two-syllable vocalization choice.
- Speaker/addressee, number shifts, causal links, severe judgment, and principal images were preserved.

This is an AI-assisted review, not qualified-human approval.

## Post-generation overlap screen

The comparison was performed only after isolated generation. The earlier dense CSB/LSV-like cluster
across the closing verses was materially removed. No distinctive Message-style imagery was found.
Residual similarities remain:

- Psalm 5:10 has an isolated literal tongue-smoothing phrase.
- Psalm 5:12 follows the source's formal clause sequence and retains a short shelter/protection frame.
- Psalm 5:13 retains the short phrase “with favor, like a shield.”
- Source-constrained formal similarities remain in the cry, boastful, house, and temple lines.

This was a bounded screen against MSG, NASB2020, ESV, NIV, CSB, NRSVue, NLT, KJV, ASV, WEB, and an
LSV result surfaced by exact search. It was not an exhaustive licensed-corpus search, plagiarism
determination, or legal opinion. The candidate must not be described as guaranteed unencumbered or
zero-overlap.

## Storage and validation

- Each new rendering is proposed, currently tagged `tr.ps005.0003`, records intended CC0 output, source isolation,
  prompt hash, model/run lineage, translation basis, computed lyric metrics, and one audit record.
- `arr.ps005.0003` is proposed and has two audit records: creation and the schema-enum provenance-label
  correction. Its saved guidance snapshot accurately states that inherited guidance was not a generator
  input.
- Existing renderings and `arr.ps005.0001`/`arr.ps005.0002` remain object-identical to `HEAD`.
- `scripts/validate_content.py`: 2,679 files validated, zero errors.
