# Resume Plan — Agentic Workflow Scaffolding

> Standing project context lives in [`../CLAUDE.md`](../CLAUDE.md). This file
> is a **temporal handoff** for continuing the scaffolding work that was
> started in a Cowork session on 2026-05-07.
>
> When Claude Code reads this in a new session, the right behavior is:
> work top-down through the steps below, marking each [ ] → [x] as it goes,
> committing after each green step.

---

## How to use this file

1. Read [`../CLAUDE.md`](../CLAUDE.md) first (architecture + policy).
2. Run the **first-run verification** in §1 — that confirms the scaffolding
   itself works end to end.
3. Walk §2 → §6 in order. Each step is independently shippable.
4. When a step lands, edit this file and tick the checkbox so the next
   session knows what's done.
5. If a step is blocked, leave a `> NOTE:` line under it and continue with
   the next independent step.

---

## 0. What was already built (do not redo)

Claude in Cowork built the scaffolding listed below on 2026-05-07. Spot-check
these exist, but assume the content is correct unless something demonstrably
breaks.

- `CLAUDE.md` — project guide (architecture, policy, daily commands).
- `AGENTS.md` — 1-line pointer to CLAUDE.md.
- `.claude/settings.json` — permissions, env, hooks block.
- `.claude/agents/` — `validator`, `audit-trail-writer`, `alignment-reviewer`,
  `llm-prompt-editor`, `release-checklist`.
- `.claude/commands/` — 14 slash commands wrapping `scripts/` and the
  `psalms-workbench` CLI.
- `.claude/hooks/` — `deny_dangerous_bash.py`, `ruff_after_edit.py`,
  `validate_after_content_edit.py`, `prompt_change_warning.py`,
  `canonical_reminder.py`.
- `SCAFFOLD_PLAN.md` (root) — the original scaffolding proposal. Safe to
  delete once §1 is green.

---

## 1. First-run verification (do this before anything else)

The Cowork session could not reach the WSL share via its sandboxed shell, so
no live verification ran. Do it here.

- [ ] **Settings parses as JSON**
  ```bash
  python -c "import json; json.load(open('.claude/settings.json')); print('ok')"
  ```
- [ ] **All hook scripts compile**
  ```bash
  python -m py_compile .claude/hooks/*.py
  ```
- [ ] **Hooks fire on a no-op edit.** Open any `app/**/*.py` file, add a
  trailing newline, save. Confirm the `ruff_after_edit.py` hook runs (no
  errors) and the post-edit ruff check passes.
- [ ] **Slash commands resolve.** Run `/validate`, `/lint`, `/test-unit` from
  inside Claude Code and confirm each invokes the right command.
- [ ] **Subagents are discoverable.** `/agents` should list `validator`,
  `audit-trail-writer`, `alignment-reviewer`, `llm-prompt-editor`,
  `release-checklist`.
- [ ] **`deny_dangerous_bash.py` actually denies.** Try a sentinel command
  like `rm -rf /tmp/sentinel-does-not-exist` — Claude Code should report the
  PreToolUse block.

If anything above is red, fix the offending file under `.claude/` before
moving on. The plan below assumes §1 is green.

---

## 2. Close the CI gap (highest value, ~1 hr)

`.github/settings.yml` requires the `validate`, `test`, and `audit` status
checks on `main`, but `.github/workflows/` does not exist. Today the local
hooks + pre-commit are the only enforcement.

- [ ] **Create `.github/workflows/validate.yml`**
  - Trigger: `pull_request` and `push` to `main`.
  - Steps: checkout → setup Python 3.11 → `pip install -e .[dev]` →
    `python scripts/validate_content.py` → `ruff check .` →
    `ruff format --check .` → `mypy app`.
- [ ] **Create `.github/workflows/test.yml`**
  - Same triggers. Runs `python -m pytest tests/unit -q` and
    `python -m pytest tests/integration -q`. Cache pip + the
    `data/derived/` build between runs (only the indexes, not raw).
  - Add a separate job for `python -m pytest tests/golden -q` so a slow
    golden run doesn't block fast unit feedback.
- [ ] **Create `.github/workflows/audit.yml`**
  - Same triggers. Runs `psalms-workbench audit-licenses` and
    `psalms-workbench generate-audit-report`. Uploads
    `reports/audit/**` as a workflow artifact.
- [ ] Confirm all three job names match the contexts in
  `.github/settings.yml` exactly: `validate`, `test`, `audit`. Branch
  protection won't recognize them otherwise.
- [ ] Update `CLAUDE.md` "Known gaps" section to note the workflows now
  exist.

> NOTE: the `.github/` directory is CODEOWNERS-gated to `@repo-admins`. The
> `.claude/settings.json` `ask` rule already requires user confirmation for
> `Write(./.github/workflows/**)` — that's intentional, not a bug.

---

## 3. Fill in the missing translation-pass prompts (medium value)

`app/llm/prompts/` contains only `pass_01_gloss.md` and `pass_02_literal.md`.
The PR template enumerates seven layers. The remaining five prompts are
needed before those passes can run.

For each layer below, use the `llm-prompt-editor` subagent and follow the
shape of the existing two files (strict JSON output, explicit alignment hint
constraints, no doctrinal additions):

- [ ] `app/llm/prompts/pass_03_phrase.md` — phrase-level rendering. Allow
      many-to-many alignment but require that every Hebrew token still maps
      to *some* phrase span.
- [ ] `app/llm/prompts/pass_04_concept.md` — concept-level. Document where
      it may collapse multiple phrases into a single concept; require an
      audit trace anyway.
- [ ] `app/llm/prompts/pass_05_lyric.md` — lyric. Style profiles in
      `docs/STYLE_PROFILES.md` apply; alignment is best-effort but a trace
      is still produced.
- [ ] `app/llm/prompts/pass_06_metered_lyric.md` — metered. Adds metrical
      constraints; same alignment-trace requirement.
- [ ] `app/llm/prompts/pass_07_parallelism_lyric.md` — parallelism-aware
      lyric. Must preserve Hebrew parallelism structure (synonymous,
      antithetic, synthetic) at clause level.

After each prompt lands:

- [ ] Run `/test-golden` to see what changed.
- [ ] Only run `/refresh-goldens` if the prompt change is intended to
      change goldens. Commit prompt + goldens together.

---

## 4. Optional: translation-pipeline subagents (lower priority)

These were intentionally **not** built in the scaffolding because the user
did not request pipeline agents. Build them only if generating one full
psalm end-to-end is becoming repetitive in chat.

- [ ] `.claude/agents/gloss-runner.md` — runs pass 01 only, validates JSON
      against the contract under `app/llm/contracts/`, reports anomalies.
- [ ] `.claude/agents/literal-runner.md` — same for pass 02.
- [ ] `.claude/agents/full-stack-runner.md` — orchestrates passes 01→07 for
      one unit, stops on the first failure, hands off to
      `audit-trail-writer` at the end.

Skip this section unless you've actually felt the friction it removes.

---

## 5. Optional: MCP servers (low priority)

If we want Claude to write GitHub issues / PRs directly instead of through
the `psalms-workbench link-*` CLI:

- [ ] Add `.claude/mcp.json` (project-scoped) with the GitHub MCP server.
- [ ] Update `.claude/settings.json` to allow specific MCP tools, not all.
- [ ] Document the new flow in `CLAUDE.md` so it doesn't surprise reviewers.

Don't do this just because we can. The CLI route already produces audit
records; an MCP path that bypasses the CLI would silently skip those.

---

## 6. Cleanup

- [ ] Delete `SCAFFOLD_PLAN.md` at the repo root once §1 is green and §2 is
      either landed or has its own tracking issue.
- [ ] Remove this `.claude/PLAN.md` once everything above is checked off.
      It's a temporal handoff, not a permanent doc.

---

## Constraints (reminder, not exhaustive)

- All standing rules in [`../CLAUDE.md`](../CLAUDE.md) "Things you must
  never do" still apply during this work.
- Do not edit `data/raw/`. Do not bypass `validate_content.py`. Do not
  modify canonical renderings as part of this scaffolding work — none of
  the steps above require it.
- `.github/CODEOWNERS`, `.github/settings.yml`, `LICENSE-code`,
  `LICENSE-text-template`, `NOTICE-template` need explicit user
  confirmation before edits — the `ask` rules in
  `.claude/settings.json` enforce this.
