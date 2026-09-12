# Codex-Backed Translation Flow and Comparison Table Requirements

## 1. Goal

Add an optional, local-only Codex provider to AlephTav so the translation workbench can use the user’s already-authenticated local Codex account to create, revise, compare, and audit Hebrew-to-English translation candidates.

The feature must support the same disciplined workflow used for Psalm 51:

1. Preserve the Hebrew source and token evidence.
2. Produce a literal English baseline.
3. Produce a selected English rendering, including singable or metered variants.
4. Explain translation accuracy and creative liberties verse by verse.
5. Keep every generated suggestion reviewable, editable, auditable, and non-canonical until approved.

This is an assistant for translation judgment, not an automatic publication system.

## 2. Architectural decision

### Use Codex App Server locally

AlephTav must integrate with a locally installed, already-authenticated Codex client through `codex app-server` over stdio.

Do not attempt to reuse the user’s Codex/ChatGPT subscription by placing a Codex credential in AlephTav’s existing OpenAI-compatible model adapter. That adapter expects an API-style `/chat/completions` service and API key, while Codex App Server owns local ChatGPT authentication, threads, approval requests, and streamed agent events.

The React browser UI communicates only with AlephTav’s FastAPI backend. The FastAPI backend owns the local Codex subprocess and JSON-RPC connection.

### Local-only boundary

Codex integration is available only while AlephTav is running on the same computer as Codex. It is not available on the GitHub Pages welcome site or any remotely hosted AlephTav deployment.

A remotely hosted future version must use a separately configured hosted provider; it must never attempt to tunnel, copy, or expose the user’s local Codex credentials.

## 3. Provider requirements

### FR-1: Codex provider lifecycle

AlephTav shall add a `codex-app-server` provider alongside the existing local model adapters.

The backend shall:

- Discover whether the `codex` executable is available.
- Start a managed `codex app-server` subprocess using stdio.
- Perform the required JSON-RPC initialization handshake.
- Check account state without exposing account credentials to the browser.
- Reuse the existing local Codex sign-in when available.
- Present a clear local status: `available`, `not installed`, `not signed in`, `connecting`, `ready`, `busy`, `error`.
- Shut down the managed subprocess gracefully when AlephTav stops.

The provider must default to stdio. Do not expose an unauthenticated local WebSocket listener.

### FR-2: Authentication

The UI shall provide a “Connect Codex” settings action.

If Codex is already signed in, AlephTav shall show only:

- Connected status
- Authentication mode
- Plan type when supplied by Codex
- Available model selection, if available

If Codex is not signed in, AlephTav shall offer an explicit “Sign in with ChatGPT through Codex” action that opens Codex’s managed browser login flow.

AlephTav must never:

- Read or display Codex OAuth tokens.
- Copy Codex credentials into its own settings file.
- Ask the user to paste a ChatGPT session token.
- Automatically log the user out of Codex.

API-key configuration remains a separate, opt-in provider path and must not be presented as necessary for local Codex account use.

### FR-3: Translation sessions and continuity

A Codex translation session shall map to one Codex thread.

Persist the following local metadata:

- AlephTav assistant session ID
- Opaque Codex thread ID
- Current Codex turn ID
- Selected model
- Provider version
- Generation purpose
- Unit or psalm scope
- Prompt-template version
- Start and completion time
- Final status

The user must be able to resume a translation conversation for a Psalm without re-explaining the translation policy, source basis, selected style profile, or meter target.

Do not persist authentication payloads, raw credentials, or browser login URLs after authentication completes.

### FR-4: Generation inputs

Every Codex translation request must include only the evidence required for the task:

- Psalm and unit reference
- Hebrew source text
- Hebrew token IDs and ordered token surfaces
- Lemma, morphology, gloss, and lexical notes when available
- Locked upstream layers
- Existing literal rendering, when producing later layers
- Selected translation basis and source manifests
- Style profile
- Meter target, if applicable
- Required output layer
- Candidate count
- Explicit constraints such as “direct translation,” “preserve divine-name policy,” or “do not force call-and-response”

The prompt must explicitly distinguish:

- Hebrew source meaning
- Literal baseline
- Singability or metrical adaptation
- Accuracy commentary
- Creative liberties

For Psalm headings, the request must preserve MT numbering separately from user-facing English numbering. This prevents headings such as Psalm 51’s superscription from being silently mistaken for verse one.

### FR-5: Structured Codex output

Codex-generated work must validate against AlephTav’s existing generation contract before it is saved as a rendering.

Extend the output contract to support:

- Candidate text
- Rationale
- Alignment hints
- Drift flags
- Grounding confidence
- Translation-basis metadata
- Preserved Hebrew images or key terms
- Literalness assessment
- Meter and prosody information, when relevant
- Accuracy note
- Creative-liberty note

If the output is invalid, AlephTav must preserve the failed run as an auditable error and show a retry action. It must not create partial or malformed renderings.

### FR-6: No autonomous content publication

Codex-generated renderings shall always enter AlephTav as `proposed`.

Codex may suggest:

- New literal renderings
- Phrase and concept renderings
- Lyric and metered-lyric renderings
- Accuracy notes
- Creative-liberty notes
- Alignment hints
- Revision rationales

Codex may not:

- Promote a candidate to canonical.
- Accept or reject its own candidate.
- Alter source Hebrew.
- Change licensing or source manifests.
- Export a release.
- Write directly to content files.

All content changes continue through AlephTav’s existing rendering, review, and audit services.

### FR-7: Tool and approval safety

Translation turns must run in text-generation mode.

If Codex requests command execution or file modification during a translation turn, AlephTav shall deny the request, record the event, and tell the user that translation mode does not permit system changes.

Future tool-enabled modes may be designed separately, but they must require explicit user approval and expose only narrowly scoped AlephTav actions.

## 4. Five-column comparison table

### Semantic columns

The comparison view shall use these five meaningful columns:

1. Hebrew (MT)
2. Literal translation
3. English used
4. Translation accuracy
5. Creative liberties

The visual table shall also include one intentionally blank gutter column between Hebrew and Literal translation. This is a layout-only column, not a sixth data field.

Visual order:

```text
[ Hebrew — RTL ] [ blank gutter ] [ Literal ] [ English used ] [ Accuracy ] [ Creative liberties ]
```

### FR-8: Table row contract

Add a `ComparisonAssessment` entity. It evaluates a chosen English rendering against a literal rendering for a single source unit or verse.

Required fields:

```text
comparison_id
psalm_id
unit_id
mt_reference
display_reference
hebrew_text
literal_rendering_id
english_rendering_id
accuracy_rating
accuracy_note
creative_liberties_note
status
created_by
created_via
generator_provider
generation_run_id
reviewer_id
reviewed_at
revision_of
audit_ids
```

`accuracy_rating` values:

```text
literal
very_close
close
adapted
interpretive
omission
```

For a verse split into multiple AlephTav units, the table must combine units in canonical source order while retaining links to the individual unit IDs.

### FR-9: Column mapping

| Table area | AlephTav source |
|---|---|
| Hebrew (MT) | `PsalmUnit.source_hebrew`, rendered RTL |
| Literal translation | Chosen canonical or selected `literal` rendering |
| English used | Chosen `lyric`, `metered_lyric`, `parallelism_lyric`, or other selected rendering |
| Translation accuracy | `ComparisonAssessment.accuracy_rating` and `accuracy_note` |
| Creative liberties | `ComparisonAssessment.creative_liberties_note` |
| Blank gutter | UI-only fixed-width spacer; never persisted |

### FR-10: Table interaction

The comparison table shall support:

- Psalm-wide and selected-verse scope.
- Selection of literal and English-used renderings.
- Filtering by layer, status, reviewer, and accuracy rating.
- Inline review of accuracy and liberty notes.
- Click-to-open Hebrew token evidence.
- Click-to-open the linked literal or English rendering.
- Highlighting aligned source tokens and target spans.
- Candidate switching without losing the assessment history.
- Clear labels for `draft`, `proposed`, `reviewed`, `accepted alternate`, and `canonical`.
- Export to Markdown, CSV, and print-friendly PDF.

### FR-11: Layout and accessibility

The table must be implemented as a semantic HTML table in the React application.

Layout requirements:

- Hebrew cells use `dir="rtl"` and right alignment.
- Literal, English, accuracy, and liberties cells use left alignment.
- The gutter is a fixed-width, empty, `aria-hidden` column.
- Default gutter width: 32 px; user-adjustable to 24 px, 32 px, or 48 px.
- Long Hebrew and English text wraps within its own cell without colliding with adjacent columns.
- Song line breaks are preserved with CSS whitespace rules, not raw HTML line-break tags.
- The table scrolls horizontally on narrow screens.
- Header row remains visible while scrolling.
- On small screens, each row may switch to a labeled stacked-card view.
- Keyboard users can enter a row, open evidence, edit notes, and select candidates without a mouse.

## 5. UI requirements

### Main workbench placement

Add a dedicated `Translation comparison` view accessible from the primary workbench, not only from the existing two-rendering comparison drawer.

The existing compare drawer remains useful for detailed candidate-versus-candidate review. The new table is the Psalm-wide editorial surface.

### Codex panel

Extend the current assistant panel with:

- Provider selector: Local models or Codex
- Codex connection status
- Connect/sign-in action
- Session/thread indicator
- Model selector
- Run progress
- Stop generation action
- Retry action
- Clear explanation when Codex is unavailable
- A visible provenance badge on Codex-generated candidates

Recommended quick actions:

- “Create a literal translation”
- “Create direct 6/8 lyric candidates”
- “Explain accuracy and liberties”
- “Revise this line while preserving Hebrew imagery”
- “Compare selected lyric against literal baseline”

## 6. Backend and code targets

Add or extend these areas:

```text
app/llm/adapters/codex_app_server.py
app/services/codex_app_server_service.py
app/services/codex_translation_service.py
app/services/comparison_assessment_service.py
app/api/routes/codex.py
app/api/routes/comparisons.py
app/db/models.py
app/llm/contracts/generation_output.schema.json
app/ui/src/components/TranslationComparisonTable.tsx
app/ui/src/components/CodexConnectionPanel.tsx
app/ui/src/hooks/useCodex.ts
app/ui/src/hooks/useComparisonAssessments.ts
app/ui/src/types/index.ts
app/ui/src/styles.css
```

The Codex adapter must fit the existing generation pipeline but add streamed job progress. Its final result must normalize into AlephTav’s existing `GenerationResponse` and rendering-creation flow.

Recommended API surface:

```text
GET    /codex/status
POST   /codex/connect
POST   /codex/login
POST   /codex/sessions
POST   /codex/sessions/{session_id}/turns
POST   /codex/runs/{run_id}/cancel
GET    /codex/runs/{run_id}/events

GET    /psalms/{psalm_id}/comparison-table
POST   /comparison-assessments
PATCH  /comparison-assessments/{comparison_id}
```

## 7. Audit and provenance requirements

Every Codex-assisted output must record:

- Provider: `codex-app-server`
- Codex model
- Opaque Codex thread and turn IDs
- Prompt-template version
- Source manifest IDs
- Translation basis
- Style profile
- Meter target
- Generation timestamp
- Output-contract validation result
- Reviewer action and rationale

The UI must clearly distinguish:

```text
Human authored
Codex suggested
Deterministically composed
Other local model suggested
```

A review decision must never overwrite the original Codex output. Edits create a revision linked to the original rendering and assessment.

## 8. Failure behavior

| Condition | Required behavior |
|---|---|
| Codex executable missing | Show setup guidance; leave other local providers usable. |
| Codex not signed in | Show explicit local sign-in action; do not request an API key. |
| App Server disconnects | Mark active run failed or interrupted; preserve partial event log; offer retry. |
| Output fails schema validation | Do not save a rendering; show validation error and retry action. |
| Codex requests file or command access | Deny it in translation mode and log the event. |
| Rate limit reached | Show provider state and preserve the draft/request for retry. |
| Comparison lacks a literal or chosen English rendering | Show an incomplete row; do not invent text. |

## 9. Acceptance criteria

The feature is complete when all of the following are true:

- A locally signed-in Codex user can connect AlephTav without entering an API key.
- AlephTav can start and resume a Codex-backed Psalm translation session.
- A Codex run can generate proposed literal and metered-lyric candidates from Hebrew evidence.
- Generated candidates validate before entering the rendering store.
- Every candidate records Codex provenance and remains non-canonical until reviewed.
- Psalm-wide comparison displays Hebrew, a visible blank gutter, literal translation, English used, accuracy, and creative liberties.
- Hebrew is right-aligned and visually separated from left-aligned English.
- The table preserves the exact selected lyric text, including musical phrase markers and line breaks.
- Accuracy and liberty notes are editable, auditable, and tied to the specific literal/English rendering pair.
- Codex cannot silently modify files, source text, release artifacts, or review status.
- Existing Ollama, llama.cpp, vLLM, and OpenAI-compatible workflows continue to work unchanged.
- Backend unit tests, mocked App Server tests, contract tests, and browser end-to-end tests pass.
- No live ChatGPT/Codex account is required in automated CI.
