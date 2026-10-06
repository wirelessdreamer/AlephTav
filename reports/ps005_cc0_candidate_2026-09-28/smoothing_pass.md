# Psalm 5 natural-delivery smoothing pass

Date: 2026-09-28  
Status: proposed; not accepted, approved, published, or exported  
Translation: `tr.ps005.0003` (Bone and Ash, intended `CC0-1.0`)  
Arrangement: `arr.ps005.0005`  

## Outcome

This revision relaxes the earlier meter targets in favor of ordinary English word order, complete
clauses, and breathable sung phrases. It is a Hebrew-first revision based on the vendored UXLC
source (`vendored-2026.04`) and the preceding fresh candidate. The archived imported song was not
used as a wording source.

All thirteen lyric units passed source-anchor validation. An independent Hebrew-fidelity review
then checked the final wording unit by unit and returned `pass` with no required corrections.

## Reviewed lyric renderings

### Psalm 5:1 — `rnd.ps005.v001.a.lyric.alt.0002`

> For the director, for the neḥiloth.  
> A psalm of David.

### Psalm 5:2 — `rnd.ps005.v002.a.lyric.alt.0004`

> Listen to my words, Yahweh;  
> understand my murmuring.

### Psalm 5:3 — `rnd.ps005.v003.a.lyric.alt.0004`

> Listen to my cry for help,  
> my King and my God,  
> for I pray to you.

### Psalm 5:4 — `rnd.ps005.v004.a.lyric.alt.0004`

> Yahweh, in the morning you will hear my voice;  
> in the morning I will make ready for you  
> and keep watch in expectation.

### Psalm 5:5 — `rnd.ps005.v005.a.lyric.alt.0004`

> For you are not a God who delights in wickedness;  
> evil will not dwell with you.

### Psalm 5:6 — `rnd.ps005.v006.a.lyric.alt.0004`

> The boastful will not stand in your sight;  
> you hate all who do wrong.

### Psalm 5:7 — `rnd.ps005.v007.a.lyric.alt.0004`

> You will destroy those who lie;  
> Yahweh will abhor a man who sheds blood and deceives.

### Psalm 5:8 — `rnd.ps005.v008.a.lyric.alt.0004`

> But in your abundant loyal love,  
> I will enter your house.  
> I will bow toward your holy temple  
> in fear of you.

### Psalm 5:9 — `rnd.ps005.v009.a.lyric.alt.0004`

> Yahweh, lead me in your righteousness  
> because my foes are watching me;  
> make your path straight before me.

### Psalm 5:10 — `rnd.ps005.v010.a.lyric.alt.0004`

> For there is nothing true in his mouth;  
> their inward parts are full of destruction.  
> Their throat is an open grave;  
> they flatter with their smooth tongue.

### Psalm 5:11 — `rnd.ps005.v011.a.lyric.alt.0004`

> Find them guilty, God;  
> let them fall because of their plans.  
> Cast them out for their many offenses,  
> for they rebelled against you.

### Psalm 5:12 — `rnd.ps005.v012.a.lyric.alt.0004`

> And let all who take refuge in you rejoice;  
> let them sing for joy forever.  
> Cover them,  
> and let those who love your name exult in you.

### Psalm 5:13 — `rnd.ps005.v013.a.lyric.alt.0004`

> For you bless the one who is righteous, Yahweh;  
> you surround him with favor like a shield.

## Arrangement disposition

`arr.ps005.0005`, titled *Psalm 5 — At First Light (Smooth Delivery Draft)*, preserves the existing
13-section form but no longer treats the inherited syllable and stress slots as hard limits. It has
35 Hebrew-anchored vocal lines plus two instrumental directions. Every Psalm 5:2–13 token is
covered; the five-token superscription has its own rendering above and is intentionally omitted
from the sung setting.

The arrangement validator found no source-boundary errors, unanchored vocal lines, words outside
the reviewed lyric inventory, stranded grammatical endings, or missing source tokens.

## Provenance and review

- Final lyric generation run: `cxr.83deb9238ec3`
- Lyric prompt SHA-256: `951100d243ff918f2877a04d387ce6596e5924dfb01b6c406b98ae46f3fb254b`
- Independent accuracy review: `cxr.9811d0b4c038` — `pass`
- Review prompt SHA-256: `03760c55d6fb83d02335736072a06962be5a95f97a5bb80e01e33ee5b9957eb2`
- Arrangement generation run: `cxr.c7062119452a`
- Arrangement prompt SHA-256: `b9329711d524aaf45bcb42f5d629d582ed22fa073ea0e25c0152b422fc136338`
- Generation model: `gpt-6-astra`
- Provider: Codex app server

An accidental duplicate arrangement created during a concurrent save retry was removed through an
audited service operation (`aud.ps005.v001.a.0020`). The surviving arrangement is
`arr.ps005.0005`, whose guidance contains the lyric and accuracy-review run IDs.

## Verification

- Content validation: 2,679 files checked, zero errors.
- Unit tests: 262 passed.
- Focused lint: passed.
- Independent Hebrew review: all 13 units passed, no required corrections.

Exact word-to-note, stress, sustained-note, and melody fit were not reverified against the audio.
This pass intentionally privileges natural delivery over exact adherence to the prior meter map and
still needs a listening audition before acceptance.
