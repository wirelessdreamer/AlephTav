# WIP

  ## In Progress

  ### aeab6
  - Prompt: the panels on the right are disorganized and on top of each other.
  make a plan to organize them and make them usable:
  - Base ref: `main`
  - Plan mode: `true`
  - Auto review: `commit`
  - Session: none attached

  ### 56ce7
  - Prompt: when i click on items on the left side, i get a 404
  - Base ref: `main`
  - Plan mode: `true`
  - Auto review: `commit`
  - Session: `idle` (`agentId: codex`)

  ### 1ffb3
  - Prompt: when shutting down setup.sh make sure we don't let processes holding
  8000 or 5173 open stay around, that creates startup issues
  - Base ref: `main`
  - Plan mode: `true`
  - Auto review: `commit`
  - Session: `running` (`agentId: codex`, `pid: 1173101`)

  ## Review

  ### d51ec
  - Title: Add first-load progress state for Psalms workbench
  - Summary: Add explicit loading, empty, and error states during initial `/
  project` and `/psalms` fetches so the Psalm selector does not appear broken on
  startup.
  - Acceptance criteria:
    - visible page-level loading state during initial load
    - disable selector until Psalms list is ready
    - inline startup status with longer-wait messaging
    - clear empty-state if `/psalms` is empty
    - clear error state if `/project` or `/psalms` fails
    - clear loading once data is ready
  - Base ref: `main`
  - Plan mode: `false`
  - Auto review: `false`
  - Session: `idle` (`agentId: codex`)

  ## Dependencies
  - None