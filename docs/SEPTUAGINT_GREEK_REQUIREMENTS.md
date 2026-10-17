# Septuagint (Greek Psalter) Support Requirements

Status: draft for owner review, 2026-10-16. Nothing here is implemented yet.
Section 15 lists the decisions the owner must make before Phase 1 starts.

## 1. Goal

Add the Greek Septuagint (LXX) Psalter to AlephTav as a second source text alongside the
Masoretic Hebrew (MT), so the workbench can:

1. **Translate Greek to English** with the same layered passes, token-anchored alignment,
   review, and audit trail used for Hebrew.
2. **Compare Hebrew and Greek** word by word, with a reviewed Hebrew↔Greek alignment and
   visual difference views that show *where* the two texts differ and *what kind* of
   difference it is.
3. **Support expert analysis**: explain each divergence (translation technique, different
   Hebrew parent text, different vocalization, interpretation, inner-Greek corruption),
   profile the Greek translator's technique across the Psalter, and trace reception
   (for example, New Testament quotations that follow the LXX).
4. **Give Greek words a lexical stack that matches the Hebrew one**: lemma, morphology,
   Strong's-style IDs, open lexicon entries, concordance, and Hebrew equivalents.

### Scope

- In scope: LXX Psalms 1–151 (Psalm 151 exists only in Greek), MT Psalms 1–150 as the
  comparison partner.
- Out of scope for this phase: other books, the Odes, Hexaplaric revisions (Aquila,
  Symmachus, Theodotion), the Dead Sea Scrolls, Vulgate/Peshitta, and full NT text. The data
  model must not block them (see §14, Phase 7).

### Design principles

- **The Greek is a source text, not a witness.** It gets its own units, tokens, renderings,
  and canonical slots. English translations of the LXX (Brenton and others) are witnesses.
- **Observation is stored apart from inference.** "The Greek has no word for this Hebrew
  word" is an observation from the alignment. "The translator's Hebrew text lacked it" is a
  hypothesis with a confidence, a rationale, and a reviewer.
- **Edition matters.** The LXX is not one text. Every Greek claim names the edition and
  witness it rests on.
- **No license laundering.** A dataset derived from restricted data stays restricted,
  whatever license tag sits on the derivative's repository.

## 2. What exists today

The repo already has an early LXX layer, but it rests on a weaker base than its labels
suggest. Every Greek string comes from the `greek` / `greekstrong` attributes in MACULA
Hebrew, which give the LXX equivalent of each **Hebrew** word.

| Area | Today | Problem |
|---|---|---|
| Greek per Hebrew token | `greek`, `greek_strong` on 18,289 of 19,587 tokens (`full_psalm_import_service.py:525-573`) | Inflected forms, not lemmas. Multi-part forms keep only the **last** Strong's number (`ὀφθαλμούς μου` → 3450 = μου). Bare digits in real data, `G3107` in fixtures. Blank for LXX-only words (every διάψαλμα). Typos carried over from upstream (`ψυξῇ`, `ἥχει`, `πᾶσι [110.10` at ps111.v010, `θοῦ [140.3` at ps141.v003). |
| Unit "LXX witness" | `source_id: "lxx"`, `versionTitle: "Septuagint Greek"` on all 2,527 units (`_load_lxx_verses`, 578-593) | **Not an LXX text.** It joins the token Greek in Hebrew word order and drops Greek words that have no Hebrew match. Its references are always MT, so ps010.v001 says "Psalm 10:1" although in the Greek that verse is LXX 9:22. |
| Source manifest `lxx` | `LXX_SOURCE` (103-112): license "CC BY 4.0", generation, display and export enabled | No LXX edition is named. Research (§4.4) suggests MACULA's Greek is a Rahlfs-type text, probably from the restricted CCAT line. Its provenance is unconfirmed upstream. |
| Versification | `content/versification.json`, built by `scripts/build_versification.py` | Psalm level only. No verse-level MT↔LXX map, no Psalm 151. |
| Basis `septuagint_greek_to_english` | Generation and composer paths, with `basis_blur` checks | The Codex path (`codex_translation_service.py:714-740`) skips the check. 0 of 365 saved renderings use the basis. The UI label and filter live only in `WorkbenchPage` / `BottomDrawer`, which `App.tsx` no longer mounts. |
| Alignment | Hebrew tokens → English spans only | No Greek token IDs exist, so Hebrew↔Greek links exist only implicitly through `token.greek`. |
| Lexical stack | Greek appears only in the word card and "readings elsewhere" | No Greek lemma, morphology, lexicon, concordance or index columns. |
| Codex briefing | Asks where the MT and LXX differ (`codex_briefing_service.py:133`) | It supplies no LXX data, so the answers come from model memory. |
| Small defects | — | `VerseDetail.tsx:292` adds a second `G` prefix ("GG3107"). Language codes vary (`he`, `hebrew`, `Hebrew`). |

### FR-0: Baseline corrections (before or alongside Phase 1)

- **FR-0.1** Stop calling the joined MACULA string "Septuagint Greek". Relabel it as
  *MACULA Greek correspondences (Hebrew word order — not the LXX text)* and give it its own
  `witness_role`. The change goes through the import service, so it writes audit records.
- **FR-0.2** Prompts must not present that string as the Septuagint verse. Until a real
  Greek text is imported, send per-token correspondences labeled as such.
- **FR-0.3** Normalize Greek Strong's to the `G`-prefixed form and keep **every** part of
  a multi-part correspondence (a list), not just the last.
- **FR-0.4** Fix the `GG` display bug.
- **FR-0.5** Give the Codex rendering path the same `basis_blur` validation that the
  generation and composer paths have.
- **FR-0.6** Make language codes an enum (`he`, `grc`, `en`) and normalize existing values
  through an audited migration.
- **FR-0.7** Record the MACULA Greek provenance as unconfirmed in the manifest and link
  the upstream question (Clear-Bible/macula-hebrew issue #145). Whether generation and
  export stay enabled until it is answered is decision **D1**.

## 3. Greek reference systems: the "Strong's" landscape

This section maps the Greek equivalents of tools the owner already knows from Hebrew study.

### 3.1 The three things to know

1. **Strong's Greek numbers (G1–G5624) cover only the New Testament.** Many words in the
   Greek Psalter have no Strong's number: διάψαλμα (the Greek for *selah*), ψαλτήριον,
   ἀντιλήμπτωρ ("helper", a Psalter favorite), and others.
2. **STEPBible's Extended Strong's fill that gap** under CC BY 4.0. Range G6100–G9979
   covers LXX words absent from the NT (adopted from the Apostolic Bible Polyglot), and
   G20000+ covers LXX words outside that tagging. For example: διάψαλμα G6908,
   ψαλτήριον G9783, ἀντιλήπτωρ G6367. They also add disambiguation suffixes
   (`G2264G` = one specific Herod) and name links to Hebrew numbers.
3. **The Greek counterpart of *Strong's Exhaustive Concordance* is Hatch–Redpath**
   (1897–1906, public domain). For every Greek word it lists each LXX occurrence and the
   **Hebrew word it translates there**, which Strong's never did. No usable digital dataset
   exists, but the workbench can generate its own Hatch–Redpath-style concordance from its
   reviewed alignment (FR-L.3). That would make it an open dataset that does not exist
   today.

### 3.2 Reference table

| System | What it is | Example ID | Covers the LXX? | Hebrew↔Greek link? | License | Role here |
|---|---|---|---|---|---|---|
| Strong's Greek | KJV-NT dictionary numbers | G5568 ψαλμός | NT words only | "of Hebrew origin" notes only | Public domain | Legacy key, derived not stored |
| **STEPBible Extended Strong's + TBESG** | Strong's extended to LXX vocabulary, with a brief lexicon | G6908, G9783, G2264G | **Yes** | Names link to Hebrew numbers; Abbott-Smith notes say "in LXX chiefly for מִזְמוֹר" | CC BY 4.0 | **Primary Greek cross-reference ID** |
| TFLSJ | Full LSJ entries keyed to Extended Strong's | same | Yes | No | Says CC BY 4.0 but derives from LSJ; treat as CC BY-SA | Long-form lexicon |
| TEGMC / Robinson codes | Greek morphology code scheme (`V-AAI-3S`) | V-AAI-3S | Applies to the LXX | — | CC BY 4.0 / public domain | Canonical morphology codes |
| TBESH | Extended Strong's for Hebrew | H4210 מִזְמוֹר | — | Hebrew side of the bridge | CC BY 4.0 | Hebrew↔Greek ID bridge |
| **Hatch–Redpath** | LXX concordance with numbered Hebrew equivalents per entry; † marks doubtful | page + column, "136c" | Yes | **Yes, per occurrence** | Public domain (scans only) | Model for FR-L.3; optional hand-keyed page refs |
| Dos Santos, *Expanded Hebrew Index* | Hebrew → Hatch–Redpath index | page/column | — | Hebrew → Greek | Scan is CC BY-NC-ND | Reference only |
| Muraoka, *Two-way Index* (2010) | Hebrew↔Greek LXX index with counts | — | Yes | Yes | © | Reference only; FR-L.4 builds our own |
| CATSS Parallel (Tov) | Scholarly standard MT↔LXX aligned text | `)$RY ⇄ MAKA/RIOS` | Yes | Yes, phrase level | CCAT non-commercial, registration required | **Do not vendor**; reference only |
| CATSS/CCAT morphology | Tagged Rahlfs | N2 NSM | Yes | No | CCAT terms | **Do not vendor** |
| GELS (Muraoka), LEH, HTLS | Septuagint lexicons | page refs | Yes | Limited | © | Cite page numbers only |
| LSJ | Classical Greek lexicon, cites the LXX | entry key | Yes | No | Perseus TEI CC BY-SA 4.0 | Lexicon text |
| Abbott-Smith | NT lexicon with LXX Hebrew-equivalent notes | headword | NT words | Partial | Public domain | Lexicon text |
| Dodson, Thayer | NT lexicons keyed to Strong's | Strong's | NT | No | Public domain | Low value |
| Louw–Nida / UBS SDGNT | Semantic domains for NT Greek | LN 33.112 | NT only; has an `InLXX` flag | No | CC BY-SA 4.0 | Optional domain field for NT-attested words |
| UBS SDBH | Semantic domains for Hebrew | 15-digit sense ID | — | No | CC BY-SA 4.0 | Hebrew-side domain (future) |
| Goodrick–Kohlenberger | NIV-era numbers | G/K 6068 | NT | No | Numbers via CC BY-SA crosswalk | Optional crosswalk |
| Apostolic Bible Polyglot | Strong's extended by decimals | G303.1 | Yes | Interlinear | © | Not stored; STEPBible's G6100+ covers it |
| Rahlfs manuscript numbers | Sigla for Greek Psalter witnesses | Ra 2110 (P.Bodmer XXIV), B, S, A | Yes | — | Facts | `witness_sigla` on variants |
| TVTMS | Verse-level versification map incl. Greek Psalms | `Ps.116:10-19 = LXX Ps.115:1-10` | Yes, incl. Ps 151 | — | CC BY 4.0 | **Versification source** |
| NETS "interlinear paradigm" | A method, not an ID: read the Greek in light of its Hebrew parent | — | — | — | — | Reading mode `as_produced` (FR-T.2) |

## 4. Sources and licensing

The license allow-list (`app/core/license_rules.py`) is Public Domain, CC BY 4.0,
CC BY-SA 4.0, Open Scriptural Data, plus the restricted `Custom-Restricted-Witness`
category. **Every source recommended below for vendoring already fits that list.** No
license-rule change is needed for the recommended path.

**Owner context (2026-10-16):** the project is open source and non-commercial, and its
outputs carry no usage restrictions. What that means for restricted sources:

- **It satisfies CCAT's non-commercial clause for the owner's own use.** The owner can
  register a CCAT user declaration and study Rahlfs and the CATSS parallel text locally
  (FR-S.5).
- **It does not allow committing CCAT-derived text to the public repository.** CCAT also
  requires every recipient to register and the distributor to control access, which a
  public repository cannot do.
- **Unrestricted outputs are the reason non-commercial inputs must stay out.** CC BY-SA
  lets anyone, including commercial users, reuse what the workbench publishes. Data that
  forbids commercial use can't pass through that license.

### 4.1 Greek base text

There is **no openly licensed digital Rahlfs text**. Every digital Rahlfs 1935 found
descends from CCAT/CATSS (non-commercial, registration required): Eliran Wong's repo
(CC BY-NC-SA plus the CCAT declaration), CenterBLC Text-Fabric (tagged MIT, but inherits
Wong's terms), the SWORD `LXX` module, OpenScriptorium, and STEPBible's planned TAGOT.

| Source | Content | License | Verdict |
|---|---|---|---|
| **Swete** (First1KGreek TEI, `tlg0527.tlg027`) | Diplomatic text of Codex Vaticanus (B); switches to Sinaiticus (S) after Ps 105:26, where B has a gap; Ps 1–151 | CC BY-SA 4.0 | **Vendor as base text** (recommended, D2). It is OCR text with errors, including Latin letters inside Greek words (`ΜΑΚAPΙΟΣ`), and it has no morphology. |
| Brenton Greek (eBible `grcbrent`) | Sixtine/Vaticanus-type text | Public domain | **Vendor as a second witness.** Two B-type texts disagreeing points to OCR errors (FR-S.4). |
| QuantForge `lxx` | Swete plus Morpheus morphology and lemmas, not derived from CCAT | Data CC BY-SA 4.0 | **Vendor as a morphology seed** after review. Its tags ignore context (ὁδῷ tagged masculine), and it is a single-maintainer project. |
| Rahlfs 1935 / Rahlfs–Hanhart 2006 (any digital form) | The standard eclectic text | CCAT-derived / © DBG | **Local restricted witness only** (FR-S.5) |
| **Göttingen *Psalmi cum Odis* (Rahlfs 1931)** | The critical text of the Greek Psalter, with apparatus. NETS Psalms translates it, and Rahlfs' 1935 handbook reuses its Psalms text. | Public domain in Germany/EU since 2006. Under a conservative reading, US public domain from 2027-01-01. Scans only. | **Transcribe it ourselves and release under CC BY-SA 4.0** (§4.5). Not legal advice. |
| Tischendorf (1850–87) | Sixtine text with variants from A, S and others | Public domain; scans only | Reference |
| Holmes–Parsons (1798–1827) | Large collection of manuscript variants | Public domain; scans only | Reference |
| Baber (1816–28) | Letter-for-letter printing of Codex Alexandrinus | Public domain; scans only | Reference (A witness) |
| Lagarde, *Psalterii graeci quinquagena prima* (1892) | Critical text of Psalms 1–50 | Public domain; scans only | Reference |
| Codex Sinaiticus Project XML | Manuscript transcription | CC BY-NC-SA 3.0 | Local restricted witness only |
| Field, *Hexapla* (1875) | Aquila/Symmachus/Theodotion fragments | Public domain, scans only | Future (Phase 7) |

### 4.2 English witnesses for the Greek

| Source | License | Verdict |
|---|---|---|
| Brenton English (1844/1851, eBible `eng-Brenton`, LXX numbering) | Public domain | Vendor as English witness |
| LXX2012 ("Updated Brenton") | Public domain (edits dedicated to the public domain) | Vendor as English witness; check its verse numbering |
| Thomson (1808) | Public domain, scans only | Future, after our own OCR |
| NETS (Pietersma, Psalms) | © IOSCS; quotation capped (≤250 verses, never a whole book) | Reference only: cite by verse |
| Lexham English Septuagint | No open license found | Reference only |

As with the Hebrew policy, English witnesses are for display and comparison only. They are
**never generation inputs**.

### 4.3 Versification and lexical data

| Source | License | Verdict |
|---|---|---|
| **STEPBible TVTMS** | CC BY 4.0 | **Primary verse-level MT↔LXX map** (handles title verses and Ps 151) |
| Copenhagen Alliance `lxx.json` (nida-institute/versification) | CC BY-SA 4.0 | Cross-check; any disagreement with TVTMS is recorded |
| Paratext `lxx.vrs` (SIL libpalaso) | MIT | Not needed. MIT is not on the allow-list (D7). |
| STEPBible TBESG, TFLSJ, TEGMC, TIPNR, TBESH | CC BY 4.0 (treat TFLSJ as CC BY-SA) | Vendor; credit STEPBible and log every change |
| LSJ (PerseusDL lexica TEI) | CC BY-SA 4.0 | Vendor |
| Abbott-Smith TEI | Public domain | Vendor |
| Strong's Greek (OpenScriptures JSON) | Public domain text; CC BY-SA digitization | Vendor |
| UBS SDGNT | CC BY-SA 4.0 | Optional (NT-attested lemmas only) |
| jtauber greek-lemma-mappings | CC BY-SA 4.0 | Optional crosswalk (G/K, Dodson, Abbott-Smith keys) |
| OpenScriptures Greek Word List / LxxLemmas | CC BY 4.0, but its lemmas correct CCAT lemmas | Hold until its lineage is reviewed |

### 4.4 The MACULA Greek question

MACULA Hebrew's LICENSE lists "Greek equivalents drawn from the Septuagint" under Biblica's
CC BY 4.0. A research spot check of 14 psalms (2,275 Greek tokens) found 51 readings shared
only with Rahlfs (e.g. Δαυιδ, where Swete has Δαυείδ) and none shared only with Swete. That
points to a Rahlfs-type, probably CCAT-lineage, source. Whether Clear made the alignment
itself or took it from CATSS is unanswered upstream (Clear-Bible/macula-hebrew issue #145,
opened 2026-10-07).

Requirement: keep MACULA's correspondences as an **alignment seed** (FR-A.2), with
attribution and a `provenance_status: upstream-unconfirmed` flag, and resolve D1 before any
release that exports text generated from them.

### 4.5 Open transcription of Rahlfs' 1931 Psalter

No openly licensed digital Rahlfs exists. The owner has decided to build one:

- **What:** a new transcription of the main Greek text of *Psalmi cum Odis* (Göttingen,
  1931), Psalms 1–151.
- **License:** released under CC BY-SA 4.0.
- **Use here:** it becomes AlephTav's critical Greek base text. Swete stays as the
  Vaticanus witness.
- **Later:** the apparatus and the Odes come in later versions.

**Source scan.** Internet Archive item `PsalmiCumOdis`. Its title page reads "Göttingen,
Vandenhoeck & Ruprecht, 1931", printed by Hubert & Co. It has 369 page images at 600 ppi
and is in the open "community" collection. The Archive's own OCR maps Greek to Latin
letters and is unusable.

#### FR-O: Transcription requirements

- **FR-O.1 Provenance.**
  - Pin every page image by checksum and record the source URL.
  - Store page/line/bounding-box coordinates for every word, so any word can be checked
    against its image.
  - Do not redistribute the scans themselves; scripts fetch them.
- **FR-O.2 Clean room.** Never copy or paste text from the CCAT/CATSS line or any text
  derived from it (Wong, CenterBLC, SWORD, OpenScriptorium). The text must derive from the
  1931 page images alone. Other texts may only flag places to re-read on the image.
- **FR-O.3 Independent readings.** Each line gets at least three readings, and no pass
  sees another pass's output:
  - a non-LLM OCR engine (Tesseract with a polytonic Greek model)
  - two separate vision-model transcriptions, using different prompts or models
  - character-level consensus; every disagreement goes to an adjudication queue resolved
    against the image
- **FR-O.4 Checks against other Greek texts** (after the fact, word by word, through the
  verse alignment):
  - **Swete (B):** when our text differs from Swete, Rahlfs' own apparatus on that page
    should record B's reading there. If it doesn't, the spot is a suspected transcription
    error.
  - **Brenton Greek:** the same check, as a second witness.
  - **MACULA Greek** (a Rahlfs-type text): flagging only, subject to D1.
  - **Orthography differences** expected between editions (Δαυιδ/Δαυείδ, movable ν,
    elision) are classified, not flagged.
- **FR-O.5 Linguistic checks.** Every word must:
  - parse as a valid Greek form (morphology lookup)
  - follow accent and breathing rules: one accent unless an enclitic follows, a breathing
    on every word-initial vowel and ρ, iota subscript where the form requires it
  - fit the verse numbering

  Failures are flagged.
- **FR-O.6 Adversarial review** by reviewers that did not transcribe. Each gets the page
  image and the proposed text, and its job is to find errors, not to confirm:
  1. **Character reviewer:** accents, breathings, iota subscripts, punctuation, verse
     numbers, line and word breaks.
  2. **Contamination reviewer:** looks for spots where the text was "normalized" toward a
     remembered or reference reading instead of the print. Canary readings must come out
     exactly as printed; Rahlfs prints ὠτία at 39:7, where B, S and A read σῶμα.
  3. **Calibration:** plant known errors in a sample to measure each reviewer's detection
     rate, and publish the rates.
- **FR-O.7 Human sign-off.** The owner checks a stratified sample of verses against the
  images. The release states the measured error rate with a confidence bound. The target is
  ≤ 1 error per 10,000 characters, counting accents and breathings.
- **FR-O.8 Release package.**
  - **Formats:** TEI XML, a word table (verse, word, page, line, box), and JSON for
    AlephTav import.
  - **Legal and affiliation:** a README stating the source edition, the legal note (§4.1),
    and that the project is not affiliated with or endorsed by the Göttingen Academy or the
    publisher.
  - **Upkeep:** an errata process, versioned releases with checksums.
  - **Hosting:** its own repository, so others can use it without AlephTav. AlephTav
    vendors it under `data/raw/` like any upstream.
- **FR-O.9 Release gate.** Do not publish before 2027-01-01 (the conservative US date).
  Decision D10 covers whether work starts before then.
- **FR-O.10 Rules from the Swete tuning run** (2026-10-17: 203 pages, 0.002 estimated
  errors per 10,000 characters; see `rahlfs1931-psalter/reports/swete_psalter_full_run.md`):
  - **Stained pages** are read from the grayscale original. Thresholding them corrupts
    every reader's view at once.
  - **Automatic corrections** need the print to match the independent reference too, and
    the span to sit on one line. Insertions, deletions and "both wrong" items are checked by
    hand.
  - **Misprint versus damaged type:** a complete sort of another letter is a misprint and is
    kept. A broken form of the required letter is transcribed as that letter. Both are
    logged in a type register.
  - **Manuscript signs** (¶, §) go to a sigla register, never into the text.

### FR-S: Source requirements

- **FR-S.1** Each new source gets a manifest (`schemas/source_manifest.schema.json`) with
  license, pinned upstream commit or version, upstream URL, import hash, a provenance-chain
  note, and generation/display/export flags. `docs/DATA_SOURCES.md` lists each one.
- **FR-S.2** Add a `provenance_status` field (`confirmed`, `upstream-unconfirmed`,
  `disputed`). This is a schema change, so it goes through CODEOWNERS.
- **FR-S.3** Vendored files live under `data/raw/<source>/` and stay read-only. Corrections
  are made in the imported content layer, never in `data/raw/`.
- **FR-S.4** Swete OCR correction is a reviewed, audited content mutation. The importer
  flags Latin or Cyrillic homoglyphs and Swete/Brenton disagreements as correction
  candidates. A reviewer accepts each correction, and each one records its evidence.
- **FR-S.5** Restricted witnesses (Rahlfs via CCAT, Codex Sinaiticus XML) may be registered
  by the user from a copy they obtained themselves under that source's terms. Their text is
  stored outside committed content (a git-ignored local folder) and labeled
  `Custom-Restricted-Witness`. It is shown only for display and comparison, and is never
  used for generation or export. Validation fails if such text appears in `content/`.
- **FR-S.6** Exports containing Greek text or anything derived from Swete or LSJ carry
  CC BY-SA 4.0 attribution. Changes to `NOTICE-template` need explicit owner confirmation
  (CODEOWNERS).

## 5. Corpus identity and versification

- **FR-V0.1 Greek units are first-class units** (recommended, D3), stored under
  `content/lxx/psalms/psNNN/` with **LXX numbering**. Greek-only material (Psalm 151,
  Greek-only titles) then fits naturally, and the one-canonical-per-unit-per-layer rule holds
  without any policy change.
- **FR-V0.2 ID scheme**: Greek unit `lxx.ps022.v001.a`, Greek token `lxx.ps022.v001.t001`.
  The `lxx.` prefix ensures no MT-number parser can misread a Greek ID. IDs are immutable,
  as for Hebrew.
- **FR-V0.3 Verse-level map** `content/versification_lxx.json`, generated from TVTMS by
  `scripts/build_versification.py` (with `--check`) and cross-checked against Copenhagen.
  Each MT verse maps to LXX verse(s) with one relation: `identical`, `renumbered`, `merged`,
  `split`, `title_shift`, `greek_only`, `hebrew_only`.
- **FR-V0.4** The map must handle at least:

  | MT | LXX | Relation |
  |---|---|---|
  | 9:1–21 + 10:1–18 | 9:1–21 + 9:22–39 | merged (one acrostic) |
  | 11–113 | 10–112 | renumbered (−1) |
  | 114:1–8 + 115:1–18 | 113:1–8 + 113:9–26 | merged |
  | 116:1–9 / 116:10–19 | 114:1–9 / 115:1–10 | split |
  | 117–146 | 116–145 | renumbered (−1) |
  | 147:1–11 / 147:12–20 | 146:1–11 / 147:1–9 | split |
  | 148–150 | 148–150 | identical |
  | — | 151 | greek_only ("outside the number") |
  | final הַלְלוּ־יָהּ of several psalms (e.g. MT 104:35) | Αλληλουια title of the next psalm (LXX 104:1 = MT 105) | title_shift across a psalm boundary |

- **FR-V0.5 Title verses**: store the edition's own verse number and a normalized number
  that counts a title as verse 1, as WLC does. (Paratext `.vrs` files use verse 0.) Display
  follows the project's numbering preference.
- **FR-V0.6 Labels are mandatory.** Wherever both corpora appear, show the corpus with
  every number ("MT 23 · LXX 22"). Never show a bare number that could belong to either.
- **FR-V0.7 Psalm correspondence groups**: one group key joins MT 9 + 10 with LXX 9,
  MT 114 + 115 with LXX 113, and so on. Projects, translations and comparison views use the
  group key, so a merged or split psalm is never orphaned.

## 6. Greek data model

### 6.1 Greek unit

Fields match the Hebrew unit where they can: `unit_id`, `corpus: "lxx"`, `psalm_id`
(LXX), `ref` ("LXX Psalm 22:1"), `mt_refs[]`, `source_greek` (NFC), `edition_id`,
`segmentation_type`, `tokens`, `token_ids`, `witnesses` (Brenton English, LXX2012,
registered local witnesses), `variants[]`, `renderings`, `alignments` (Greek tokens →
English spans; same contract as Hebrew), `cross_alignment_ids`, `status`, and the audit,
review and link arrays.

`variants[]` records edition and witness differences at a token span:
`{span_token_ids, reading, witness_sigla[], source_id, note}`. Swete's marginal notes on
which manuscripts are extant are imported here.

### 6.2 Greek token

| Field | Required | Source | Notes |
|---|---|---|---|
| `token_id` | yes | own | `lxx.psNNN.vVVV.tTTT` |
| `surface` | yes | edition (corrected) | NFC |
| `normalized` | yes | derived | Search key: lowercase, final sigma folded, accents and breathings stripped, grave changed to acute |
| `lemma` | yes | morphology seed + review | NFC, accented dictionary form; the primary lexical key |
| `morph_code` + parsed features | yes | TEGMC/Robinson-style codes | part of speech, case, number, gender, tense, voice, mood, person, degree |
| `ext_strong` | yes, or `null` with a `lexical_gap` flag | STEPBible TBESG | e.g. `G6908`. Plain Strong's is derived (≤ G5624) and not stored separately. |
| `gloss` | yes | TBESG / Abbott-Smith / reviewed | short English gloss |
| `transliteration` | yes | derived | SBL style |
| `lsj_key`, `abbott_smith_key` | optional | lexicon indexes | |
| `ln_domain`, `sdgnt_lexid` | optional | UBS SDGNT | only where the lemma is NT-attested |
| `hr_ref` | optional | hand-keyed | Hatch–Redpath page + column |
| `gk` | optional | crosswalk | low value |
| `enrichment_sources` | yes | — | extends the enum beyond `oshb` and `macula` (schema change) |
| `morph_source`, `morph_confidence` | yes | — | `quantforge`, `llm`, `manual` |

**FR-D.1 Unicode rules**: store NFC, which maps oxia to tonos. Normalize the elision mark
to one code point. Normalize iota adscript and subscript (MACULA has `ὠιδὴ` for ᾠδή). Reject
Latin or Cyrillic homoglyphs in Greek fields.

**FR-D.2** Hebrew tokens keep MACULA's `greek` and `greek_strong`, renamed in meaning to
*MACULA LXX hint*. They store the full list of parts (FR-0.3) and are used only as an
alignment seed.

## 7. Hebrew↔Greek alignment (the bridge)

This is the core new dataset. Every comparison and expert view reads from it.

- **FR-A.1 New contract** `schemas/cross_alignment.schema.json`.
  `alignment.schema.json` is a mandatory contract and is **not** loosened. Fields:

  ```text
  cross_alignment_id
  mt_unit_ids[]            lxx_unit_ids[]
  hebrew_token_ids[]       greek_token_ids[]      (either may be empty: minus / plus)
  structure                one_to_one | one_to_many | many_to_one | many_to_many
                           | hebrew_only (minus) | greek_only (plus)
  relation                 equivalent | grammatical_shift | lexical_shift | plus | minus
                           | transposition | doublet | uncertain        (observation)
  feature_diffs[]          computed: person, number, gender, tense/conjugation, voice, …
  explanations[]           hypotheses (see FR-E.1); empty is allowed
  provenance               macula_seed | auto_aligner:<model@version> | codex | human
  confidence               0..1
  status                   proposed | reviewed | accepted
  reviewer_ids[], audit_ids[]
  ```

- **FR-A.2 Seeding pipeline.** All seeded rows enter as `proposed`; nothing is
  auto-accepted.
  1. MACULA hint: match each Hebrew token's Greek against the Greek tokens of the mapped LXX
     verse(s) by normalized lemma and form.
  2. ID bridge: Extended Strong's and TBESG Hebrew-equivalent notes.
  3. Statistical or LLM aligner for the rest, recording model and version.
  4. Tokens left unmatched become `plus` / `minus` candidates.
- **FR-A.3** Alignments may cross verse and psalm boundaries (the Hallelujah title shifts,
  LXX 9 spanning MT 9–10).
- **FR-A.4 Coverage rule.** A verse counts as *aligned* when every Hebrew token is in
  exactly one cross alignment (possibly `minus`) and every Greek token is in exactly one
  (possibly `plus`). Before then, a gap is a warning; after, it is a validation error.
- **FR-A.5 Gold set.** Hand-align MT Ps 1, 2, 8, 9–10, 23, 51, 110 and 117 first. Measure
  seed precision and recall against it, and publish the numbers in the audit reports.
- **FR-A.6** The cross alignment is original work. It is released under CC BY-SA 4.0
  because the Greek side is Swete. Rows seeded from MACULA keep MACULA attribution and its
  provenance flag.

## 8. Greek → English translation

There are two different things, and the UI must never blur them:

| | LXX-informed alternate of the MT | Translation of the LXX |
|---|---|---|
| Lives on | MT unit | LXX unit |
| Basis | `septuagint_greek_to_english` (existing) | `septuagint_greek_to_english` |
| Anchored to | Hebrew tokens, **plus** the cross-alignment IDs that justify the Greek pressure | Greek token IDs |
| Canonical | Competes for the MT unit's canonical; keeps its "LXX-informed" label if promoted | Own canonical slot per Greek unit per layer |

- **FR-T.1 Layers.** The same seven layers run on Greek units. Pass 01 (gloss) and Pass 02
  (literal) need strict JSON and alignment hints to Greek token IDs.
- **FR-T.2 Prompts** (edited through `llm-prompt-editor`): new `pass_01_gloss_grc.md` and
  `pass_02_literal_grc.md`, plus Greek sections in passes 03–07. Rules:
  - **Translate the Greek, not the Hebrew behind it.** A new drift flag `mt_leak` fires
    when the English follows the MT at a span the cross alignment marks as divergent.
  - **Reading mode** is stored on every Greek-basis rendering and shown in the UI (default:
    D4):
    - `as_produced` (the NETS "interlinear paradigm"): where the Greek is a Hebraism, read
      it in light of its Hebrew parent. LXX 94:11 εἰ εἰσελεύσονται is the Hebrew oath
      formula, so it becomes "they shall not enter".
    - `as_received`: read the Greek as a Greek reader without the Hebrew would. Keep the
      conditional form and note the idiom.
  - **Divine name:** a Greek policy separate from the MT's YHWH policy. κύριος → "the
    Lord"; κύριος τῶν δυνάμεων for YHWH ṣebaʾot. Flag places where κύριος does not stand
    for YHWH, and places where YHWH is not κύριος.
  - **Fixed terms with alternates:** εἰς τὸ τέλος (for לַמְנַצֵּחַ), ψαλμός, ᾠδή, ὕμνος,
    Αλληλουια, διάψαλμα.
  - Keep Greek tense and aspect. Do not silently normalize them to Hebrew time reference.
  - Proper names come from the Greek form (Δαυιδ → David).
- **FR-T.3 Locked inputs** for a Greek-basis pass: the Greek unit text and tokens (lemma,
  morphology, gloss, `ext_strong`), plus the cross alignment and MT literal **labeled "for
  comparison — do not translate"**. Brenton and other English witnesses are never inputs.
- **FR-T.4 Validation** across all paths (generation, composer, Codex): source language
  `grc`; `lxx` in `source_ids`; anchor token IDs must be Greek IDs; anchor text in Greek
  script only.
- **FR-T.5** Greek-basis renderings belong to a translation (`translation_id`), like all
  English text. How LXX-based translations sit in projects is decision D6.

## 9. Comparison and visual difference analysis

- **FR-C.1 Source switch** in the mounted workbench (`ComparisonPage`): **MT**, **LXX**, or
  **Parallel**.
- **FR-C.2 Bridge view** (one verse): a Hebrew row (RTL) above a Greek row (LTR), joined
  by alignment ribbons.

  ```text
   MT 22:17   כִּי סְבָבוּנִי כְּלָבִים ... כָּאֲרִי  יָדַי וְרַגְלָי
                  │        │              ┆ (lexical shift)  │
   LXX 21:17  ὅτι ἐκύκλωσάν με κύνες ... ὤρυξαν  χεῖράς μου καὶ πόδας
  ```

  - Each ribbon is colored **and** patterned by relation. Pluses and minuses appear as
    marked gaps.
  - **Solid** marks are observations; **dashed** marks are hypotheses.
  - The hover card (reusing the source map's card) shows both lemmas, Strong's and Extended
    Strong's, glosses, the morphology diff, the relation, the hypotheses with confidence,
    and the review status.
  - Two alternative layouts: **interlinear in Hebrew order** (Greek stacked under each
    Hebrew word, Greek order shown by small numbers and transposition marks) and
    **interlinear in Greek order**.
- **FR-C.3 Highlighting rules:** only non-`equivalent` relations are colored.
  Grammatical shifts are subtle; lexical shifts, pluses and minuses are strong. A legend is
  always visible. The palette is safe for color blindness, and every color has a text
  equivalent.
- **FR-C.4 English diff without noise:** a word diff (reusing `wordDiff.ts`) of the MT
  literal against the LXX literal. Each diff span links to its cross alignment.
  - Spans over `equivalent` source pairs are grey ("translator variation").
  - Spans over divergent pairs are colored ("the sources differ").
  - This keeps English wording choices from looking like textual differences.
- **FR-C.5 Divergence profile:** a per-verse score built from observations only:
  (2·plus + 2·minus + 2·lexical_shift + grammatical_shift + transposition) ÷ max(Hebrew
  tokens, Greek tokens).
  - The weights are documented in the report.
  - The score is drawn as a strip along each psalm, and as a heatmap grid over the whole
    Psalter in either numbering; clicking opens the verse.
  - The score is precomputed into `data/derived/`.
- **FR-C.6 Lexeme correspondence explorer:**
  - For a Hebrew lemma: the distribution of its Greek equivalents across the Psalter
    (ranked bars, optional flow diagram), drillable to every occurrence in context.
  - The reverse for a Greek lemma.
  - A consistency index, and filters by psalm and by Psalter book (I–V).
- **FR-C.7 Structure map:** psalm boundaries and numbering side by side (9–10, 113–116,
  146–147, 151), the Hallelujah title shifts, and a title table (MT title | LXX title |
  difference).
- **FR-C.8 Comparison table extension:** optional columns *Greek (LXX)* (LTR,
  `lang="grc"`), *LXX literal*, and *MT↔LXX note*. The default five-column layout from
  `CODEX_TRANSLATION_COMPARISON_REQUIREMENTS.md` is unchanged. Markdown, CSV and print
  exports include the Greek.
- **FR-C.9 Typography:** bundle a polytonic Greek font (Gentium Plus, SIL OFL) and mark
  Greek text `lang="grc"`. Users can toggle accents and breathings, transliteration, and
  Greek or Hebrew word order.
- **FR-C.10 Keyboard and screen readers:**
  - Arrow keys move between aligned pairs.
  - Each pair has a spoken summary, e.g. "Hebrew כָּאֲרִי, 'like a lion'; Greek ὤρυξαν,
    'they dug'; lexical shift; hypothesis: different reading, confidence 0.6, proposed."

## 10. Expert analysis

- **FR-E.1 Divergence dossier** for each verse that has a divergence
  (`schemas/divergence_analysis.schema.json`):

  ```text
  analysis_id, mt_refs[], lxx_refs[], cross_alignment_ids[]
  observation_summary            generated deterministically from the alignment
  hypotheses[]
    cause      translation_technique | idiom | de_metaphorization | harmonization
               | exegetical | theological | different_vorlage | different_vocalization
               | graphic_confusion | metathesis | different_word_division
               | etymologizing | inner_greek_corruption | edition_choice | unknown
    confidence 0..1
    rationale
    retroverted_hebrew?          always labeled a hypothesis; consonantal, optional vowels
    evidence[]                   {type: corpus_token | edition_variant | lexicon_entry
                                  | parallel_passage | external_citation, ref}
    counter_evidence[]
  significance                   {meaning, english_translation, reception}
  reception_refs[]               e.g. Heb 10:5; references only, no quoted commentary
  recommended_handling           none | footnote | alternate | adopt_with_note
  status, created_by, created_via, reviewer_ids[], audit_ids[]
  ```

- **FR-E.2 Evidence rules** (enforced by the contract and by prompts):
  - A claim about a manuscript or edition must cite a vendored or locally registered
    witness entry. Anything else is tagged `external_unverified` and shown with a warning.
    Example: claims about the Naḥal Ḥever reading at Ps 22:17 are external until such a
    witness is registered.
  - A retroversion is never written into the Hebrew source or an MT canonical rendering.
  - Contested places get neutral treatment: Jewish and Christian reception are reported,
    not adjudicated. A hypothesis whose cause is `theological` needs a theology reviewer.
  - Copyrighted scholarship (NETS, GELS, commentaries) is cited, not quoted beyond fair
    limits.
  - LLM output enters as `proposed` and must validate against the contract.
- **FR-E.3 Translation-technique profile.** A deterministic, rebuildable report per psalm,
  per Psalter book and for the whole Psalter, computed from **reviewed** alignments using
  Tov's and Barr's criteria for literalness:
  1. *Lexical consistency* (stereotyping): for each Hebrew lemma with three or more
     occurrences, the share taken by its most common Greek equivalent.
  2. *Quantitative representation*: percentage of one-to-one alignments, the Greek/Hebrew
     element ratio, and plus and minus rates.
  3. *Word order*: Kendall τ between Hebrew order and aligned Greek order, per verse.
  4. *Segmentation*: how often pronominal suffixes, prefixed prepositions and
     conjunctions, and the article are represented.
  5. *Verb mapping matrix*: Hebrew conjugation (qatal, yiqtol, wayyiqtol, weqatal,
     imperative, infinitive, participle) × Greek tense and mood.
  6. *Divine names and epithets*: how often YHWH becomes κύριος, the exceptions, and
     whether metaphorical epithets (צוּר, סֶלַע, מָגֵן, מְצוּדָה, מָעוֹז) are kept or
     de-metaphorized (MT 18:3 צוּרִי → LXX 17:3 βοηθός μου).
- **FR-E.4 Edition sensitivity.** Where Swete, Brenton and a registered Rahlfs witness
  differ, show a variant table and flag any dossier whose conclusion depends on the edition
  (LXX 39:7, Appendix A #8).
- **FR-E.5 Expert briefing upgrade.** `codex_briefing_service` supplies the real Greek
  text, cross alignment, divergence list and technique profile, and asks for dossiers in the
  FR-E.1 contract. The model no longer answers from memory.
- **FR-E.6 Reception pointers.** Curated references to NT quotations of the Psalms (seed:
  Ps 2:7; 8:3, 5–7; 16:8–11; 22:2; 40:7–9; 95:7–11; 110:1, 4; 118:22), each marked as
  agreeing with the LXX, the MT, both, or neither. The NT text itself is Phase 7.
- **FR-E.7 English impact.** Each dossier states whether the selected English rendering is
  affected, links to that row's accuracy and liberty notes in the comparison table, and can
  create a footnote or alternate through the existing audited services.

## 11. Greek lexical study tools

- **FR-L.1 Greek word card,** mirroring the Hebrew one:
  - surface, lemma, parsed morphology, gloss
  - Extended Strong's (with plain Strong's where ≤ G5624), the TBESG brief entry, and the
    LSJ and Abbott-Smith entries
  - the Hebrew equivalent at this spot and across the Psalter
  - frequency in the LXX Psalms, and whether the word is NT-attested
- **FR-L.2 Greek concordance:** search by lemma, Extended Strong's, morphology features or
  surface, accent-insensitive, with keyword-in-context results. It is backed by new derived
  SQLite tables (`greek_token_index`, `cross_alignment_index`, `greek_occurrence_index`)
  built by `scripts/build_indexes.py`.
- **FR-L.3 Hatch–Redpath view:** for a Greek lemma, a numbered list of its Hebrew
  equivalents, then every occurrence tagged with its number.
  - "No Hebrew counterpart" marks pluses.
  - "Doubtful" marks alignments below a confidence threshold, playing the role of
    Hatch–Redpath's †.
  - It is generated from our own data, so it is an open concordance.
- **FR-L.4 Two-way index:** Hebrew lemma or Strong's → Greek renderings with counts, and
  Greek lemma → Hebrew sources with counts, over the Psalms.
- **FR-L.5 Strong's bridge:** a co-occurrence table of H-numbers and G-numbers, Extended
  Strong's included.
- **FR-L.6 Key-term notes** (curated; lexical and Greek review):
  - נֶפֶשׁ/ψυχή, תּוֹרָה/νόμος, חֶסֶד/ἔλεος, שְׁאוֹל/ᾅδης, כָּבוֹד/δόξα
  - צְדָקָה/δικαιοσύνη and ἐλεημοσύνη (MT 24:5 = LXX 23:5)
  - יְהוָה/κύριος, צְבָאוֹת/τῶν δυνάμεων, סֶלָה/διάψαλμα, לַמְנַצֵּחַ/εἰς τὸ τέλος
  - עוֹלָם/αἰών, מָשִׁיחַ/χριστός
- **FR-L.7** Show lexicon text only from open sources: TBESG/TFLSJ (attributed), LSJ
  (CC BY-SA), Abbott-Smith (public domain). GELS, LEH and BDAG appear as page citations at
  most.

## 12. Review, audit and provenance

- **FR-R.1** Add a **Greek reviewer** role. This changes `docs/REVIEW_POLICY.md` and is
  decision D5. Proposed counts:

  | Change | Approvals |
  |---|---|
  | Greek-unit alternate | 1, by a Greek reviewer |
  | Greek-unit canonical | 2, at least one of them a Greek reviewer |
  | Cross alignment acceptance | alignment reviewer + Greek reviewer |
  | Dossier with a theological cause | adds a theology reviewer |

- **FR-R.2** Every mutation writes an `AuditRecord` under the existing schema, unchanged.
  This covers Greek content, OCR corrections, cross alignments, dossiers and key-term
  notes.
- **FR-R.3** Provenance badges distinguish Human, Codex, Deterministic, Other local model,
  and **Seeded from MACULA**.
- **FR-R.4** Release export may include Greek-basis renderings only when every source in
  their chain allows export. Restricted local witnesses are never exported (existing
  `FORBIDDEN_FOR_EXPORT`).

## 13. API, MCP, CLI, validation and tests

Indicative API surface:

```text
GET    /lxx/psalms                      GET  /lxx/psalms/{psalm_id}
GET    /lxx/units/{unit_id}             GET  /versification/map?mt=…|lxx=…
GET    /units/{mt_unit_id}/parallel     (MT unit + mapped Greek + cross alignments)
POST   /cross-alignments                PATCH /cross-alignments/{id}
GET    /greek/lexicon/lemma/{lemma}     GET  /greek/lexicon/strong/{ext_strong}
GET    /greek/concordance               GET  /lexemes/correspondence?hebrew_lemma=|greek_lemma=
GET    /psalms/{id}/divergence-profile
GET    /divergence-analyses?unit=…      POST /divergence-analyses   PATCH /divergence-analyses/{id}
GET    /reports/translation-technique?scope=psalm|book|psalter
```

- **FR-X.1** Each new route gets an MCP tool in `app/api/mcp_server.py` or an `EXCLUDED`
  entry (the existing test enforces this).
- **FR-X.2 CLI commands:** `import-lxx`, `build-lxx-versification`,
  `seed-cross-alignment`, `analyze-divergence <unit>`,
  `generate-translation-technique-report`. `translate-unit` accepts Greek unit IDs.
- **FR-X.3 `validate_content.py` additions:**
  - Greek token schema, NFC, no homoglyphs
  - ordered, unique Greek IDs
  - every Greek unit mapped to MT verses (except `greek_only`)
  - cross-alignment referential integrity and the coverage rule (FR-A.4)
  - allowed licenses on every manifest
  - no restricted witness text in `content/`
- **FR-X.4 Audit report additions:** uncovered Greek tokens, unaligned Hebrew tokens in the
  cross alignment, plus/minus counts, and dossier coverage.
- **FR-X.5 Tests:**
  - A Greek fixture in `tests/support.py`: LXX 1, part of LXX 9 (merge), LXX 113 (join),
    LXX 114–115 (split), LXX 151. It needs no network.
  - Unit tests for versification, normalization and coverage.
  - Integration tests for the routes.
  - Goldens from Appendix A.
  - UI unit tests for the bridge view, and e2e tests for the source switch.

## 14. Phasing and acceptance

| Phase | Delivers | Done when |
|---|---|---|
| 0 | FR-0 corrections; decisions D1–D9 | Owner has answered D1–D9; FR-0 tests pass |
| 1 | Swete, Brenton Greek and English, LXX2012, TVTMS and Copenhagen vendored; Greek units imported read-only; Parallel view without ribbons | All 151 LXX psalms imported; every MT verse maps; the merge, split and Ps 151 tests pass; zero homoglyphs remain |
| 1b | Open Rahlfs 1931 transcription (§4.5), released no earlier than 2027-01-01, then vendored as the critical base text | FR-O.3–O.7 met; measured error rate published; release tagged with checksums |
| 2 | Morphology and lexicon (QuantForge seed + review, STEPBible); Greek word card; concordance | 100% of tokens have a lemma and morphology; every token has `ext_strong` or an explicit `lexical_gap` flag; a reviewed sample's accuracy is published |
| 3 | Cross alignment: seeding, review UI, coverage reports | Gold set fully reviewed; seed precision and recall published |
| 4 | Greek → English layers | Gloss and literal for the gold psalms; `mt_leak` check and Codex parity in tests |
| 5 | Visual difference views (FR-C) | Bridge, diff, profile, explorer and structure views pass accessibility checks |
| 6 | Expert analysis (FR-E) and lexical tools (FR-L) | Every Appendix A case is flagged and has a reviewed dossier; technique report builds from scratch |
| 7 (future) | Other books; Göttingen text; Hexaplaric fragments; NT quotation alignment (SBLGNT / MACULA Greek); Vulgate, Peshitta and DSS witnesses; the Odes | — |

## 15. Decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| D1 | MACULA Greek provenance is unconfirmed (§4.4). Keep the `lxx` manifest enabled for generation and export? | Keep it as an alignment seed and for display; turn off generation and export of the joined witness until Clear answers |
| D2 | Base Greek text | Swete (CC BY-SA) as the base until our Rahlfs 1931 transcription (§4.5) is released, then Rahlfs 1931 as the base and Swete as the Vaticanus witness. Brenton Greek as a cross-check. |
| D3 | Greek as separate units, or attached to MT units | Separate first-class units |
| D4 | Default reading mode | `as_produced`, with `as_received` one click away |
| D5 | Add a Greek reviewer role and the counts in FR-R.1 | Yes |
| D6 | How LXX-based translations fit projects (one translation per psalm per project) | A translation records `source_corpus` (`mt` or `lxx`); a project holds one translation per psalm correspondence group |
| D7 | Add MIT and CC0 to the allow-list | Not needed for the recommended path; defer |
| D8 | Psalm 151 now; the Odes later | Yes |
| D9 | Morphology: QuantForge seed + review, or fresh LLM-assisted tagging + review | QuantForge seed; measure its error rate in Phase 2 before committing to it |
| D10 | Rahlfs 1931 transcription (§4.5): when work starts, which texts may flag errors, and where the dataset lives | Owner's call; publication waits until 2027-01-01 either way |

## Appendix A: Psalms divergence casebook (golden seed)

Check each entry against the vendored edition before using it as a golden. Categories are
hypotheses, not verdicts.

| # | MT | LXX | Hebrew | Greek | Observation | Likely category | Reception |
|---|---|---|---|---|---|---|---|
| 1 | 2:9 | 2:9 | תְּרֹעֵם "break them" | ποιμανεῖς αὐτούς "shepherd them" | lexical shift | different vocalization (רעע / רעה) | Rev 2:27; 12:5; 19:15 |
| 2 | 2:12 | 2:12 | נַשְּׁקוּ־בַר | δράξασθε παιδείας "take hold of instruction" | lexical shift | exegetical; the Hebrew is itself disputed | debated |
| 3 | 8:3 | 8:3 | יִסַּדְתָּ עֹז "founded strength" | κατηρτίσω αἶνον "prepared praise" | lexical shift | interpretive | Matt 21:16 |
| 4 | 8:6 | 8:6 | מֵאֱלֹהִים | παρ᾽ ἀγγέλους "than angels" | lexical shift | exegetical | Heb 2:7 |
| 5 | 16:10 | 15:10 | שַׁחַת "pit" | διαφθοράν "corruption" | lexical shift | etymologizing (שׁחת "destroy") | Acts 2:27; 13:35 |
| 6 | 18:3 | 17:3 | צוּרִי "my rock" | βοηθός μου "my helper" | lexical shift | de-metaphorization of a divine epithet | — |
| 7 | 22:17 | 21:17 | כָּאֲרִי "like a lion" | ὤρυξαν "they dug" | lexical shift | different reading (contested; external evidence must be flagged) | debated |
| 8 | 40:7 | 39:7 | אָזְנַיִם כָּרִיתָ לִּי "ears you dug for me" | Rahlfs ὠτία "ears"; the major uncials (B, S, A) σῶμα "body" | edition-sensitive | inner-Greek corruption / edition choice | Heb 10:5 (σῶμα) |
| 9 | 95:11 | 94:11 | אִם־יְבֹאוּן | εἰ εἰσελεύσονται | equivalent (Hebraism) | idiom: oath formula; a reading-mode test | Heb 3:11; 4:3, 5 |
| 10 | 110:3 | 109:3 | יַלְדֻתֶיךָ "your youth" | ἐξεγέννησά σε "I begot you" | lexical and grammatical shift | different vocalization | — |
| 11 | 14:3 | 13:3 | — | long plus in many Greek witnesses, matching Rom 3:13–18 | plus | edition-sensitive; check how the vendored text prints it | Rom 3:13–18 |
| 12 | 96:10 | 95:10 | — | "ἀπὸ τοῦ ξύλου" in some later witnesses and in Justin Martyr; not in the main Greek tradition | variant only | test: never presented as the LXX text | patristic |
| 13 | 104:35 | 104:1 (= MT 105) | הַלְלוּ־יָהּ | Αλληλουια | cross-psalm alignment | title shift | — |
| 14 | 9 + 10 | 9 | — | — | merged psalm | versification | — |
| 15 | — | 151 | — | whole psalm ("outside the number") | Greek-only | versification | — |
| 16 | 24:1; 27:1; 93:1; 96:1 | 23:1; 26:1; 92:1; 95:1 | short or no title | τῆς μιᾶς σαββάτων; πρὸ τοῦ χρισθῆναι; εἰς τὴν ἡμέραν τοῦ προσαββάτου; ὅτε ὁ οἶκος ᾠκοδομεῖτο μετὰ τὴν αἰχμαλωσίαν | title plus | liturgical / historical framing | — |
| 17 | 24:5 | 23:5 | צְדָקָה "righteousness" | ἐλεημοσύνην "mercy" | lexical shift | translation technique | — |

## Appendix B: Glossary

- **LXX / Old Greek (OG):** the Greek translation of the Hebrew Bible. "Old Greek" means
  the original translation, as distinct from later revisions.
- **MT:** the Masoretic Text, the workbench's Hebrew source.
- **Vorlage:** the Hebrew text the Greek translator worked from. It may differ from the MT.
- **Retroversion:** reconstructing the Vorlage from the Greek. Always a hypothesis.
- **Plus / minus:** material present only in the Greek / only in the Hebrew.
- **Stereotyping:** rendering a Hebrew word with the same Greek word everywhere.
- **Hebraism:** Greek wording that copies a Hebrew construction.
- **Diplomatic vs. critical edition:** a diplomatic edition prints one manuscript (Swete
  prints B). A critical edition reconstructs the earliest text from many witnesses (Rahlfs,
  Göttingen).
- **Sigla:** manuscript labels. B = Vaticanus, S (ℵ) = Sinaiticus, A = Alexandrinus,
  Ra 2110 = P.Bodmer XXIV.
- **Recension:** a later revision of the Greek: *kaige*, Hexaplaric (Origen), Lucianic.
- **Interlinear paradigm:** the NETS view that the Greek was produced to be read alongside
  its Hebrew parent.
- **Hatch–Redpath:** the standard LXX concordance, with a Hebrew equivalent for each
  citation.
- **Extended Strong's:** STEPBible's extension of Strong's numbers to LXX vocabulary.
- **TVTMS:** STEPBible's versification mapping tables.

## Appendix C: Source URLs

- Swete TEI: https://github.com/OpenGreekAndLatin/First1KGreek (`data/tlg0527/tlg027/`)
- QuantForge LXX: https://github.com/QuantForgeSoftware/lxx
- Brenton Greek / English, LXX2012: https://ebible.org/grcbrent/ ,
  https://ebible.org/eng-Brenton/ , https://ebible.org/eng-lxx2012/
- STEPBible data (TBESG, TFLSJ, TEGMC, TIPNR, TBESH, TVTMS):
  https://github.com/STEPBible/STEPBible-Data
- Copenhagen Alliance versification: https://github.com/nida-institute/versification
- UBS open dictionaries (SDGNT, SDBH): https://github.com/ubsicap/ubs-open-license
- LSJ TEI: https://github.com/PerseusDL/lexica
- Greek lemma crosswalk: https://github.com/jtauber/greek-lemma-mappings
- MACULA Hebrew license: https://github.com/Clear-Bible/macula-hebrew/blob/main/LICENSE.md ;
  provenance question: https://github.com/Clear-Bible/macula-hebrew/issues/145
- CCAT terms (why Rahlfs and CATSS are not vendored):
  https://ccat.sas.upenn.edu/gopher/text/religion/biblical/
- Hatch–Redpath scans: archive.org items `HatchRedpath1`–`HatchRedpath3`
- Rahlfs 1931 *Psalmi cum Odis* scan: https://archive.org/details/PsalmiCumOdis
- NETS copyright terms: https://ccat.sas.upenn.edu/nets/edition/
