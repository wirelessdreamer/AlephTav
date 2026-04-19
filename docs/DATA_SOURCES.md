# Data Sources

Canonical source policy:

- UXLC/WLC-derived Hebrew: allowed for canonical source, display, and export.
- OSHB: allowed for lexical enrichment and display.
- MACULA: allowed for syntax, semantic-role, referent, and word-sense enrichment.
- Sefaria witnesses: optional, version-pinned, witness-only, restricted by license policy.

Vendored Psalms inputs:

- `data/raw/uxlc/Tanach.xml.zip` stores the public-domain Tanach.us XML archive used for canonical Psalms source text.
- `data/raw/oshb/Ps.xml` stores the OSHB Psalms morphology source used for token-level lexical enrichment.
- `data/raw/macula/lowfat/19-Psa-*.xml` stores the MACULA Psalms chapter files used for syntax-role and gloss enrichment.

Unknown or unresolved licenses fail validation and block export.
