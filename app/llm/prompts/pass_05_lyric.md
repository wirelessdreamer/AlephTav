# Pass 05 Lyric

Lyric layer should translate directly from Hebrew-aware inputs and may emit explicitly labeled Septuagint-derived alternates when Greek source data is present.
Do not route through witness English.
Preserve speaker/addressee, scene, imagery, and parallelism while recording concessions.
When the style profile allows artistic latitude, modernize diction before flattening images into explanation.
If the target voice is doubtful or contested, allow strained address rather than auto-resolving into confident devotion.
Sparse, breath-based lineation is allowed when it helps the pressure land more truthfully; short lines and strategic breaks are better than padded prose.

## High-freedom performative voice

Apply the techniques below when `style_profile.style_profile_id == "antiphonal_performative"`, or when `style_profile.lyric_freedom >= 0.85` and `style_profile.idiom_modernity >= 0.8`. Otherwise ignore this section.

When the source posture is petition or lament and `style_profile.emotional_directness >= 0.9`, the **default delivery shape** is dyadic micro-stanzas: 2-5 word lines paired into couplets, each couplet a single breath. A petition like `אַל / verb-with-suffix / prep-phrase` lands as two lines, not one — verb-and-object on line 1, prep-phrase on line 2. Do not write long explanatory sentences in this mode; trust the silence between lines to carry the pressure.

Positive exemplar for Psalm 6:2 (`יְהוָה אַל־בְּאַפְּךָ תוֹכִיחֵנִי וְאַל־בַּחֲמָתְךָ תְיַסְּרֵנִי`):

```
LORD —
don't rebuke me in anger

don't press me down
in your wrath
```

Note the moves: (a) the divine name is lifted onto its own pre-line with an em-dash breath break, not folded into the sentence; (b) the parallel `וְאַל` half resets to a fresh stanza rather than continuing with "and"; (c) the prepositional phrase moves to line 2 of each couplet; (d) the petition contracts (`don't`, not `do not`). Mirror these moves whenever Hebrew negative petition appears with this profile.

- **Antiphonal echo refrains.** After a fuller line, a striking 2-4 word fragment may be repeated on its own short line as an echo ("evil", "open grave", "Stand guard", "run for cover to you"). Use sparingly — at most one echo per stanza, never on every line. The echo must reuse words actually present in the preceding line; never invent new content. Echoes do not require new `alignment_hints` since they re-anchor to the same source tokens — note that fact in `rationale`.
- **Anaphora across lines or stanzas.** Repeat the opening word/phrase of consecutive units to build pressure ("Every morning — you hear me / Every morning — I lay it before you / Every morning — I wait, and you answer"; "If I go quiet… / If I sink…"). Anaphora is preferred over filler when a Hebrew triplet wants rhetorical weight.
- **Conversational vocatives and imperatives.** Direct address is loud and contemporary ("Listen, God!", "How long, LORD?", "Turn, LORD —", "Go — get away from me"). Contractions ("don't", "I'm", "they're") are allowed.
- **Em-dash breath breaks and dyadic micro-stanzas.** When the source posture is petition or lament, prefer 2-5 word lines paired in dyadic stanzas with em-dashes for breath ("My bones — / they shake inside me"). When the source posture is declaration or celebration, allow longer lines beside short refrains.
- **Coined epithets for agent-of-X formulas.** Hebrew construct chains like `אִישׁ דָּמִים` or `אִישׁ מִרְמָה` may become personified compound nouns ("Blood-Thirsty", "Truth-Bender"), capitalized as proper nouns. Document the source phrase in `preserved_source_images` and keep `alignment_hints` to the source tokens.
- **Modernized scene-mechanics.** Swap opaque Hebrew images for present-day scene equivalents that preserve the mechanic ("enemy lines" for watchful adversaries; "Kick them out!" for `הַאֲשִׁימֵם`). Do not erase the source image — record it in `preserved_source_images`. If the swap shifts agency, theological certainty, or emotional mechanism, raise a `drift_flags` entry.
- **Variable line length is the default.** Pair short refrains beside fuller verses. Singable, not metered — do not enforce a syllable count when `target_syllables == 0`.
- **Imagery preservation is non-negotiable.** Coined epithets and modernized scene-mechanics may *replace* English idiom but must *retain* the Hebrew image. Bones, throat, grave, tears, sanctuary, blood, seed — keep them visible.

If a candidate uses two or more of the techniques above, list them in `differentiator` (e.g., "antiphonal echoes + coined epithets"). If a candidate is conservative and avoids these techniques even though the profile allows them, list it in `differentiator` as "literal-leaning alternate" so the reviewer can compare.
