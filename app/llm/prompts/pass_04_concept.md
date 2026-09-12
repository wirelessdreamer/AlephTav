# Pass 04 Concept

Concept layer may combine spans but must preserve semantic roles, scene logic, and image flow.
Support both Hebrew-to-English and, when explicitly present, Septuagint-Greek-to-English ideation paths without blurring their source identity.
Modernize idiom before replacing Hebrew imagery with abstraction.
If a figurative rewrite changes audience posture, theological certainty, or emotional mechanism, note the drift risk.

## High-freedom performative voice

Apply the techniques below when `style_profile.style_profile_id == "antiphonal_performative"`, or when `style_profile.lyric_freedom >= 0.85` and `style_profile.idiom_modernity >= 0.8`. Otherwise ignore this section and stay closer to the literal scene.

- **Conversational vocatives.** Direct address with imperative urgency is welcome ("Listen, God!", "How long, LORD?"). Contractions are allowed.
- **Modernized scene-mechanics.** When a Hebrew image is opaque to a modern English reader, swap in a present-day equivalent that keeps the same scene mechanic — for example "enemy lines" for `שׁוֹרְרָי` (watchful adversaries), "Kick them out!" for `הַאֲשִׁימֵם`, "Let the party last all night!" for `יִרְנְנוּ`. Never erase the underlying Hebrew image; record it in `preserved_source_images` and keep `alignment_hints` to the source tokens. If the swap changes the agent, certainty, or theological mechanism, raise a `drift_flags` entry.
- **Coined epithets for agent-of-X formulas.** Hebrew construct chains like `אִישׁ דָּמִים` (man of bloods) or `אִישׁ מִרְמָה` (man of deceit) may be rendered as personified compound nouns ("Blood-Thirsty", "Truth-Bender") and capitalized as proper nouns. Coined epithets are *more* faithful than abstractions like "violent person" — they preserve the Hebrew agent-noun structure. Document the source phrase in `preserved_source_images`.
- **Coined divine titles** are allowed when `divine_name_rendering` is `flexible_address` ("King-God" for `מַלְכִּי וֵאלֹהָי`). Note the source pair in `preserved_source_images`.
- **Imagery preservation is non-negotiable.** Even at high lyric freedom, do not collapse a concrete Hebrew image (bones, throat, grave, tears, sanctuary) into bare emotion. Modernize the diction around the image; keep the image.
