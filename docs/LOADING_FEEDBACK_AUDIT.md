# Loading feedback audit

Audited the application mounted by `app/ui/src/app/App.tsx`: Welcome, comparison,
Verses and word study, Arrangement, Sources, Liberties, Raw text, guidance,
briefing, import, history, Greek source study, and both assistant surfaces.
Checked initial requests, dependent requests, mutations, background refreshes,
errors, retries, and genuine empty results. No corpus or translation data changed.

## Findings resolved

| Surface | Previous gap | Result |
| --- | --- | --- |
| Application startup | Empty root until JavaScript starts | Static loading notice and JavaScript-disabled explanation |
| Project / Psalm selection | Disabled controls and false “no psalms” / “select a psalm” while bootstrapping; failures hidden | Visible project and Psalm loading messages, explicit failures, Retry; comparison waits for a project |
| Comparison | Initial loading was plain text; failed refresh replaced previously loaded content | Visible spinner with task description and Retry; cached comparison remains during refresh and refresh failures |
| Arrangement / Sources / Liberties / Raw text | Setting list had feedback, but the subsequent selected-setting request rendered nothing | Feedback for both requests; Retry for either failure; visible refresh and save feedback; genuine empty settings explained |
| Guidance | Empty editable textarea before saved guidance arrived | Loading / error / Retry; editing, Save and Revert disabled until saved guidance is available |
| Briefing history | Loading text but no recovery for history failure | Shared loading / failure feedback with working Retry; Greek context retains its separate loading and recovery |
| Word choices | Missing data treated as “no suggestions” during request or failure | Loading / error / Retry; empty-suggestion prompt appears only after successful loading |
| Verse history | Plain loading message and unrecoverable error | Shared loading / error / Retry and explicit empty history |
| Greek editions | No UI while discovering editions; unavailable without recovery | Loading / error / Retry; successful empty edition list explained |
| Greek reader navigation | Blank Psalm selector while fetching navigation list | Loading label and disabled selector until available; empty editions / reader results explained |
| Assistant visibility | Desktop shell unmounted assistant when it moved from footer to side, although comparison has no embedded replacement | Assistant remains mounted in the shell at either placement |
| Assistant session setup (global and verse) | No setup feedback; failures could trigger repeated creation; Strict Mode could duplicate or orphan initialization | One guarded initialization, explicit pending / error / Retry; closed global assistant defers session creation |
| Assistant conversation / actions / audio | Waiting response, confirmed action execution, transcription and failures lacked visible feedback | Task-specific pending and failure messages |
| Assistant settings / tools | Missing configuration looked empty and editable; failures hidden | Loading / error / Retry; configuration writes blocked until saved settings arrive; save feedback |
| Codex panel | Connection / model errors and intermediate session creation were silent | Connection, sign-in, session, model, generation, stop and candidate-save feedback; failures visible; query retries available |
| Rebuild review | Decision buttons disabled without explanation during save | Visible decision-save status |
| Hebrew occurrence preview | Loading text lacked status semantics | Loading announced as status |

Shared `RequestStatus` presents task text, an accessible status or alert, optional
Retry, and a spinner that respects reduced-motion preferences. It does not report
unrelated background polling as a global loading screen.

## Existing feedback retained

- Import identification and import pipeline already show stage progress and errors.
- Whole-Psalm translation, analysis, rebuilding and drafting already show batch
  progress, elapsed time, results, cancellation and failures.
- Briefing decision autosave already distinguishes saving, saved, and unsaved
  edits with retry; it remains independent of Greek dictionary loading.
- Greek word cards, dictionary entries, occurrence queries and source readings
  already display pending and error states; their content and lexical identity
  checks remain intact.
- Verse text editing and adding notes already expose saving labels and failures.
- Welcome contains static content and does not await application data.

The older `WorkbenchPage`, `BottomDrawer`, and `InspectorRail` implementation is
not mounted by the current router. Its existing source-map loading messages were
inspected; no new routes or inactive editor workflows were introduced.

## Verification

`tests/e2e/loading-feedback.spec.ts` uses controlled delayed and failing authored
requests to exercise bootstrap, comparison, the two-stage Sources load, protected
guidance, Greek discovery recovery, history, word choices, cached comparison
refresh failure, and assistant setup/retry/response. The assistant initialization
test also starts with the panel open under React Strict Mode.

Run with the existing fixture-only Playwright configuration. The broader fixture
suite covers briefing persistence, Greek studies, source flow, word mouseovers,
outside dismissal, responsive layout and scroll following. Production build and
canonical content validation are required alongside browser verification.

Verified result: all 43 fixture browser tests passed, including ten loading and
recovery tests; production TypeScript/Vite build passed; content validation
checked 2,694 files with zero errors. Provider generation and content-writing
operations were not run against the user's corpus for this UI audit.

The merged phone interface uses the same startup and comparison feedback. Its
Full workbench button retains access to Sources, arrangements, briefing and
advanced editing; Phone view returns to the focused reading interface. The
choice persists across reloads. Desktop assistant feedback remains available,
while the phone interface retains its screen without an assistant overlay.
