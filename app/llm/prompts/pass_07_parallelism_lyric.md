# Pass 07 Parallelism Lyric

Return strict JSON only. Preserve Hebrew clause-level parallelism (synonymous, antithetic, synthetic) and keep alignment hints explicit.
Parallelism lyric should sound like production-ready Psalm lyric writing, not a study note.
Use ordinary direct speech, concrete image pressure, and intentional repetition where the source movement supports it.
Do not flatten parallel lines into explanation, strengthen faith posture beyond the source, or reuse inherited English witness wording.
If Septuagint Greek produces a distinct parallel pressure, label it as a separate basis instead of blending it into the Hebrew candidate.

## High-freedom performative voice

Apply the techniques below when `style_profile.style_profile_id == "antiphonal_performative"`, or when `style_profile.lyric_freedom >= 0.85` and `style_profile.idiom_modernity >= 0.8`. Otherwise ignore this section. The strict-JSON output contract still rules — these techniques shape the `text` field, not the schema.

- **Antiphonal echoes pair naturally with synonymous parallelism.** When the Hebrew has a parallel pair, the second member may render as an echoed half-line of the first ("evil" echoing "delights in evil"; "open grave" echoing "Their throat is an open grave"). The echo must reuse words from its companion line and must not invent new content; record this as a parallelism preservation, not a drift, in `rationale`. Both members still need `alignment_hints` to their source tokens.
- **Antithetic parallelism keeps both poles loud.** Do not soften the contrast for cadence. If the source contrasts wicked-vs-righteous or fall-vs-stand, both halves remain present and both halves are tagged in `alignment_hints`.
- **Synthetic parallelism may use anaphora.** When the second member extends or explains the first, repeat the opening word/phrase across both ("Every morning — … / Every morning — …"). Anaphora is preferred over filler.
- **Conversational vocatives, em-dash breath breaks, and dyadic micro-stanzas** are permitted, including 2-5 word lines for petition/lament. Variable line length is the default — singable, not metered.
- **Dyadic micro-stanza is the default delivery shape** when `style_profile.emotional_directness >= 0.9` and the source posture is petition or lament. A parallel `אַל ... וְאַל ...` pair renders as two stanzas separated by a blank line, not as one comma-spliced sentence. The vocative (`יהוה`, `אדני`) lifts onto its own pre-line with an em-dash; the prepositional phrase moves to its own line; contractions (`don't`, `won't`) replace `do not`. Both halves still receive their own `alignment_hints`. See the Psalm 6:2 exemplar in `pass_05_lyric.md`.
- **Coined epithets for agent-of-X formulas** (`אִישׁ דָּמִים` → "Blood-Thirsty"; `אִישׁ מִרְמָה` → "Truth-Bender") are permitted and capitalized as proper nouns. Document the source phrase in `preserved_source_images`.
- **Modernized scene-mechanics** (swap opaque Hebrew images for present-day equivalents while keeping the source image in `preserved_source_images`) are permitted. If the swap shifts agency, theological certainty, or emotional mechanism, raise a `drift_flags` entry.
- **Imagery preservation is non-negotiable.** Even at high lyric freedom, parallelism must continue to anchor concrete Hebrew images — not be replaced by English explanation.
