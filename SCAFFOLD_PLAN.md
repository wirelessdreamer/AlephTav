# Agentic-Workflow Scaffolding Plan

Status: **draft for review** — no other files created yet.

This plan proposes scaffolding for Claude Code (and Cowork desktop) inside the
Psalms Copyleft Workbench repo, derived from a deep scan of the actual code,
docs, and policies. Nothing here is generic; every file is justified by
something already in the repo.

---

## 1. What the scan found

**Stack**

- Python 3.11+, FastAPI app at `app/api/main.py`, Typer CLI at `app/cli.py`
  (entry point `psalms-workbench`).
- SQLAlchemy + SQLite for derived indexes (`data/derived/indexes/workbench.sqlite3`).
- React + Vite + TypeScript UI under `app/ui/`.
- Local LLM adapters under `app/llm/adapters/` (ollama, vllm, llamacpp,
  openai_compatible).
- Translation passes: `pass_01_gloss`, `pass_02_literal` (more expected per the
  PR template — phrase, concept, lyric, metered_lyric, parallelism_lyric).
- Tests split into `tests/unit/`, `tests/integration/`, `tests/golden/`, with
  pytest markers `no_seeded_repo` and `corpus_audit`.
- Lint/format: ruff (line-length 100, py311, rules E/F/I/B/UP). Types: mypy
  (`check_untyped_defs`).
- Pre-commit: ruff + ruff-format + `python scripts/validate_content.py`.
- Setup scripts `setup.sh` / `setup.ps1` orchestrate venv → deps →
  `seed_project` → `import_psalms` → `build_indexes` → `validate_content` →
  uvicorn + Vite.

**Policy the scaffolding has to respect**

- Every content mutation must produce an `AuditRecord` (`schemas/audit_record.schema.json`,
  `docs/AUDIT_POLICY.md`).
- Canonical promotions require **2 qualified approvals**; alternates require 1
  (`docs/REVIEW_POLICY.md`).
- Release export must include `LICENSE`, `NOTICE`, `SOURCES`, `AUDIT_REPORT`,
  `OPEN_CONCERNS` (`docs/RELEASE_PROCESS.md`).
- CODEOWNERS gates content/, schemas/, app/llm/, .github/workflows/, docs/.
- Branch protection in `.github/settings.yml` requires the `validate`, `test`,
  and `audit` workflow checks — but **no `.github/workflows/` directory exists
  yet** (gap, flagged but out of scope for this scaffolding).

**Gaps relevant to this work**

- No `CLAUDE.md` at the repo root.
- No `.claude/` directory.
- No agent guidance for the canonical/alternate distinction, the layered
  translation passes, or the audit-record requirement — all of which an
  unsupervised agent will get wrong.

---

## 2. Files I propose to create

All paths are relative to the repo root.

### 2a. Top-level project guide

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Single source of truth Claude reads first. Explains: what this repo is, the canonical-vs-alternate model, the layered passes, the audit-record requirement, where the LLM prompts live, the test layout, ruff/mypy/pytest commands, and "things you must never do" (e.g., write to `data/raw/`, edit canonical renderings without 2 approvals, bypass `validate_content.py`). |

### 2b. `.claude/settings.json`

Project-scoped Claude Code settings. Concretely:

- Permissions: allow `Bash(python -m pytest:*)`, `Bash(python scripts/validate_content.py)`,
  `Bash(python scripts/build_indexes.py)`, `Bash(ruff:*)`, `Bash(mypy:*)`,
  `Bash(npm run *)`, `Bash(psalms-workbench *)`. Deny destructive ones
  (`rm -rf`, anything touching `data/raw/`, `git push --force`).
- `enableAllProjectMcpServers: false` (explicit opt-in only).
- `env`: surface `ALEPHTAV_ROOT_DIR` so subagents inherit the right root.
- `additionalDirectories`: `app/llm/prompts/`, `schemas/`, `docs/` — read-mostly
  context Claude should be able to reach.

### 2c. Subagents — `.claude/agents/`

Small focused agents matching the actual roles in REVIEW_POLICY.md and the
existing service boundaries. Each is a single markdown file with frontmatter.

| File | Role | When Claude invokes it |
|---|---|---|
| `validator.md` | Runs `validate_content.py`, ruff, mypy, pytest with the right markers. Reports a punch list. | Before claiming any change is done. |
| `audit-trail-writer.md` | Drafts an `AuditRecord` JSON consistent with `audit_record.schema.json` for a proposed change. Refuses if `triggered_by_issue`/`triggered_by_pr` are missing for canonical changes. | Whenever a service mutates content and a human/agent forgot to add the record. |
| `alignment-reviewer.md` | Reads `schemas/alignment.schema.json`, checks alignment coverage and unaligned spans on a change. | When edits touch `app/services/alignment_service.py` or content under `content/psalms/`. |
| `llm-prompt-editor.md` | Edits files under `app/llm/prompts/` only. Knows that prompts must return strict JSON, preserve token anchors, and avoid doctrinal additions. | When a user asks to refine a translation pass. |
| `release-checklist.md` | Walks through `docs/RELEASE_PROCESS.md` step by step, runs each gate, reports which are red. | Before tagging a release. |

(Five is the right number for this repo. More would dilute; fewer would miss
the canonical/alternate enforcement that needs its own surface.)

### 2d. Slash commands — `.claude/commands/`

Thin wrappers over scripts and CLI commands you already have. Each is one
markdown file. The point is so Claude (and you) can do `/validate` instead of
remembering the script path.

| Command | What it runs |
|---|---|
| `/validate` | `python scripts/validate_content.py` |
| `/rebuild-indexes` | `python scripts/build_indexes.py` |
| `/audit-report` | `psalms-workbench generate-audit-report` |
| `/release-report $RELEASE_ID` | `psalms-workbench generate-release-report $RELEASE_ID` |
| `/translate-unit $UNIT_ID $LAYER` | `psalms-workbench translate-unit $UNIT_ID $LAYER` |
| `/refresh-goldens` | `python scripts/refresh_goldens.py` |
| `/seed-fixture` | `./setup.sh --fixture --skip-start` |
| `/test-unit` | `python -m pytest tests/unit -q` |
| `/test-integration` | `python -m pytest tests/integration -q` |
| `/test-golden` | `python -m pytest tests/golden -q` |
| `/lint` | `ruff check . && ruff format --check . && mypy app` |
| `/fix-lint` | `ruff check --fix . && ruff format .` |
| `/link-issue $UNIT_ID $ISSUE` | `psalms-workbench link-issue $UNIT_ID $ISSUE` |
| `/link-pr $UNIT_ID $PR` | `psalms-workbench link-pr $UNIT_ID $PR` |

### 2e. Hooks — `.claude/settings.json` `hooks` block

Quality gates that fire automatically:

- **PostToolUse → Edit/Write on `app/**/*.py` or `scripts/**/*.py`**: run
  `ruff check --fix` and `ruff format` on the touched file. Block on
  remaining errors (exit 2 → Claude sees the failure).
- **PostToolUse → Edit/Write on `content/**/*.json` or `schemas/**/*.json`**:
  run `python scripts/validate_content.py`. Block on failure.
- **PostToolUse → Edit/Write on `app/llm/prompts/**/*.md`**: warn that prompt
  changes require golden re-run; surface the `/refresh-goldens` command.
- **PreToolUse → Bash command**: deny commands that touch `data/raw/` or
  `.venv/`, deny `git push --force` to `main`.
- **PreToolUse → Edit/Write on `LICENSE-code`, `LICENSE-text-template`,
  `NOTICE-template`, `.github/CODEOWNERS`, `.github/settings.yml`**: require
  user confirmation in chat before proceeding (these have CODEOWNERS gates IRL).
- **UserPromptSubmit**: inject a one-line reminder of the canonical-vs-alternate
  rule when the user mentions "canonical", "promote", or "merge to main".

Hooks are written as small Python scripts under `.claude/hooks/` so they're
testable and don't depend on shell quoting. Each is < 30 lines.

### 2f. AGENTS.md (optional, recommended)

Single-file pointer that says "agentic tools should read CLAUDE.md". Useful
because some non-Claude agent frameworks default to looking for `AGENTS.md`.
Two-line file. No duplication.

---

## 3. Things I am explicitly **not** doing

To keep the scaffolding tight and not invent work:

- **Not adding GitHub Actions workflows.** `.github/settings.yml` references
  `validate`, `test`, `audit` checks but no workflows exist. That's a real gap
  but it's a separate task; I'll flag it in CLAUDE.md as a known issue rather
  than silently adding three workflow files.
- **Not adding MCP servers.** Cowork desktop and Claude Code can both work
  fine without project-local MCP configuration. If you later want a connector
  (e.g., GitHub MCP for issue/PR linking) we add it then.
- **Not editing `.pre-commit-config.yaml`.** It's already doing the right
  thing; the Claude hooks complement it, not replace it.
- **Not generating translation-pipeline subagents** (gloss / literal / phrase
  agents). You said scope = config + dev workflow + quality gates, not
  pipeline agents. I left placeholders only in `llm-prompt-editor.md`.

---

## 4. Layout preview

```
AlephTav/
├── CLAUDE.md                      ← new
├── AGENTS.md                      ← new (2 lines)
├── SCAFFOLD_PLAN.md               ← this file (delete after build)
└── .claude/
    ├── settings.json              ← permissions, env, hooks
    ├── agents/
    │   ├── validator.md
    │   ├── audit-trail-writer.md
    │   ├── alignment-reviewer.md
    │   ├── llm-prompt-editor.md
    │   └── release-checklist.md
    ├── commands/
    │   ├── validate.md
    │   ├── rebuild-indexes.md
    │   ├── audit-report.md
    │   ├── release-report.md
    │   ├── translate-unit.md
    │   ├── refresh-goldens.md
    │   ├── seed-fixture.md
    │   ├── test-unit.md
    │   ├── test-integration.md
    │   ├── test-golden.md
    │   ├── lint.md
    │   ├── fix-lint.md
    │   ├── link-issue.md
    │   └── link-pr.md
    └── hooks/
        ├── ruff_after_edit.py
        ├── validate_after_content_edit.py
        ├── prompt_change_warning.py
        ├── deny_dangerous_bash.py
        └── canonical_reminder.py
```

That's 1 root doc + 1 settings file + 5 agents + 14 commands + 5 hook scripts
= **26 small files**, each under 50 lines.

---

## 5. What I need from you

Reply with one of:

- **"build it"** → I create everything in §2 exactly as listed.
- **"build it but skip X / add Y"** → tell me which pieces to drop or add.
- **"adjust the plan"** → I revise this file before building.

After build, this `SCAFFOLD_PLAN.md` can be deleted (or kept as a record).
