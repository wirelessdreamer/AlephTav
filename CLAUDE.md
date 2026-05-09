# CLAUDE.md — Psalms Copyleft Workbench

This file is the first thing Claude (and any other agent) should read when
working in this repo. Read it in full before opening other files.

---

## What this repo is

Local-first workbench for translating the Hebrew Psalms into English with full
lexical traceability, layered renderings, alignment review, audit trail, and
release export. Canonical text is committed JSON under `content/`. Derived
artifacts (SQLite indexes, caches, reports) live under `data/derived/` and
`reports/` and are rebuildable from the canonical content plus `data/raw/`.

GitHub Pages welcome site: https://wirelessdreamer.github.io/AlephTav/

---

## Architecture at a glance

- `app/api/` — FastAPI app (`app.api.main:app`). Routers live in
  `app/api/routes/`. Errors map to HTTP via `app/api/deps.py:raise_as_http`.
- `app/cli.py` — Typer CLI exposed as `psalms-workbench`. Most user-facing
  operations have a CLI command; prefer them over ad-hoc scripts.
- `app/services/` — All business logic. Routes and the CLI both call into
  these. Mutations *must* go through services so audit records get written.
- `app/llm/` — Local-model adapters (`ollama`, `vllm`, `llamacpp`,
  `openai_compatible`), prompts under `app/llm/prompts/`, JSON contracts under
  `app/llm/contracts/`.
- `app/db/` — SQLAlchemy models and session for the derived index database
  (`data/derived/indexes/workbench.sqlite3`).
- `app/ui/` — React + Vite + TypeScript workbench UI.
- `schemas/` — JSON Schemas. `audit_record.schema.json` and
  `alignment.schema.json` are mandatory contracts; do not loosen without
  going through CODEOWNERS.
- `scripts/` — Operational scripts (seed, import, build indexes, validate,
  refresh goldens, generate reports). Most are reachable via the CLI too.
- `tests/` — `unit/`, `integration/`, `golden/`. See "Testing" below.

The settings module (`app/core/config.py`) reads `ALEPHTAV_ROOT_DIR` from the
environment; tests point this at a temp workspace via `conftest.py`.

---

## Translation model — non-obvious rules

These rules are policy, not preference. Get them wrong and a release will be
blocked.

### Layered passes

A unit can have renderings at multiple layers, in this order from most
literal to most lyrical:

`gloss` → `literal` → `phrase` → `concept` → `lyric` → `metered_lyric` →
`parallelism_lyric`

Every layer must preserve token-anchored alignment back to the Hebrew source
to the extent the target style permits. Prompts under `app/llm/prompts/`
encode the layer-specific rules — read the relevant prompt before editing
generation behavior. Pass 01 (gloss) and Pass 02 (literal) require strict
JSON output and explicit alignment hints.

### Canonical vs alternate

Each unit has at most one **canonical** rendering per layer. Other accepted
renderings are **alternates**.

- Adding an alternate: 1 qualified reviewer approval.
- Promoting an alternate to canonical, or modifying a canonical: **2**
  qualified approvals.
- Release: release reviewer signoff plus passing audit workflows.

Reviewer roles: `lexical`, `Hebrew`, `alignment`, `lyric`, `theology`,
`release`. See `docs/REVIEW_POLICY.md`.

### Audit records are mandatory

Every content mutation must produce an `AuditRecord` matching
`schemas/audit_record.schema.json`. The record carries `before_hash`,
`after_hash`, `summary`, `rationale`, `triggered_by_issue` /
`triggered_by_pr`, `created_by`, `checks`, and `review_signoff`.

If a service mutates content without writing an audit record, that is a bug —
fix the service, do not paper over it. See `app/services/audit_service.py`
and `app/services/github_link_service.py` for the pattern.

### License and provenance

Source license rules live in `app/core/license_rules.py`. Outputs that fail
the audit raise `LicensePolicyError` (→ HTTP 400). `data/raw/` is the
vendored upstream corpus and is **read-only** to all tooling, including
agents.

---

## Daily commands

Activate the venv first (`source .venv/bin/activate`).

| Task | Command |
|---|---|
| Validate content | `python scripts/validate_content.py` |
| Rebuild derived indexes | `python scripts/build_indexes.py` |
| Generate audit reports | `psalms-workbench generate-audit-report` |
| Generate release report | `psalms-workbench generate-release-report <release_id>` |
| Translate a unit | `psalms-workbench translate-unit <unit_id> <layer>` |
| Add alternate | `psalms-workbench add-alternate <unit_id> <layer> "<text>" "<rationale>"` |
| Promote alternate | `psalms-workbench promote-alternate <rendering_id>` |
| Link issue / PR | `psalms-workbench link-issue <unit_id> <#>` / `link-pr` |
| Fixture-only fast bootstrap | `./setup.sh --fixture --skip-start` |
| Run API | `python -m uvicorn app.api.main:app --host 127.0.0.1 --port 43174 --reload` |

Slash-command shortcuts for these live in `.claude/commands/` (see below).

---

## Testing

```bash
python -m pytest tests/unit -q          # fast, run constantly
python -m pytest tests/integration -q   # FastAPI + service flows
python -m pytest tests/golden -q        # translation/quality goldens
python -m pytest -m corpus_audit        # full-corpus audit pass (slow)
npm test                                 # UI unit tests
npm run test:e2e                         # Playwright e2e
```

Markers: `no_seeded_repo` (skips fixture bootstrap),
`corpus_audit` (writes reports instead of hard-failing).

`tests/conftest.py` auto-bootstraps a fixture repo into a temp workspace per
session via `tests/support.py`. Tests must not depend on a real
`content/psalms/` corpus unless they declare `corpus_audit`.

---

## Lint, format, types

- `ruff check .` and `ruff format --check .` — line length 100, target
  py311, rules `E,F,I,B,UP`.
- `mypy app` — `check_untyped_defs=True`. New code should be typed.
- Pre-commit (`.pre-commit-config.yaml`) runs ruff, ruff-format, and
  `validate_content.py` on every commit. Don't bypass it.

`.claude/hooks/` enforces the same gates on edits Claude makes — see
"Hooks" below.

---

## Things you must never do

- **Never edit `data/raw/`.** It's the vendored upstream Hebrew corpus.
- **Never edit a canonical rendering without 2 qualified approvals** logged
  via the review service. If you need to make a change, add an alternate
  first.
- **Never bypass `validate_content.py`** — if it fails, fix the content,
  don't disable the check.
- **Never skip writing an `AuditRecord`** for a content mutation.
- **Never commit secrets, large model files, or anything under
  `data/derived/`.** That directory is rebuildable.
- **Never `git push --force` to `main`** or any release branch.
- **Never edit `.github/CODEOWNERS`, `.github/settings.yml`, `LICENSE-code`,
  `LICENSE-text-template`, or `NOTICE-template` without explicit user
  confirmation in chat.** These are CODEOWNERS-gated for a reason.

---

## When in doubt, ask

If the user's request seems to imply changing canonical content, modifying
schemas, or touching license/CODEOWNERS, stop and ask before acting. The
cost of a wrong canonical change is much higher than the cost of one
clarifying question.

---

## Subagents available

Defined in `.claude/agents/`:

- `validator` — runs the lint + type + content + test gates and reports.
- `audit-trail-writer` — drafts an `AuditRecord` for a proposed change.
- `alignment-reviewer` — checks alignment coverage on edits.
- `llm-prompt-editor` — edits files under `app/llm/prompts/` only.
- `release-checklist` — walks through `docs/RELEASE_PROCESS.md` step by step.

## Slash commands available

Defined in `.claude/commands/`. Notable: `/validate`, `/lint`, `/fix-lint`,
`/test-unit`, `/test-integration`, `/test-golden`, `/rebuild-indexes`,
`/audit-report`, `/release-report`, `/translate-unit`, `/refresh-goldens`,
`/seed-fixture`, `/link-issue`, `/link-pr`.

---

## Known gaps (informational)

- `.github/settings.yml` requires the `validate`, `test`, and `audit` status
  checks on `main`, but `.github/workflows/` does not exist yet. The local
  `validate_content.py` and pytest suites are the substitute today; adding
  those workflows is a separate task.
