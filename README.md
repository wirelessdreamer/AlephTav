# Psalms Copyleft Workbench

Local-first workbench for Hebrew-source Psalms translation, lexical inspection, alignment, review, audit, and release packaging.

GitHub Pages welcome site: https://wirelessdreamer.github.io/AlephTav/

## What the project includes

- Git-friendly JSON content as the canonical text source of truth
- SQLite-derived indexes for concordance, lexical cards, witnesses, and jobs
- FastAPI backend plus a Typer CLI
- React + TypeScript workbench UI for lexical analysis and translation review
- Audit, provenance, review, and release-export workflows

## Quick demo run

This is the fastest path to a working local demo with the fixture dataset used by the UI tests and screenshots.

### 1. Create the environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
npm install
```

### 2. Seed fixture data

```bash
python scripts/bootstrap_fixture_repo.py
```

### 3. Start the backend

```bash
source .venv/bin/activate
uvicorn app.api.main:app --reload
```

### 4. Start the UI

```bash
npm run dev
```

Open:

- `http://127.0.0.1:5173/` for the welcome page
- `http://127.0.0.1:5173/workbench` or `http://127.0.0.1:5173/#/workbench` for the live workbench

## Full content rebuild

Use this path when you want to regenerate the local project state from the repo scripts instead of using the fixture bootstrap.

```bash
source .venv/bin/activate
python scripts/seed_project.py
python scripts/import_psalms.py
python scripts/build_indexes.py
python scripts/validate_content.py
uvicorn app.api.main:app --reload
```

## Common commands

### CLI

```bash
psalms-workbench validate-content
psalms-workbench audit-licenses
psalms-workbench export-release --release-id v0.1.0
```

### Tests

```bash
npm test
npm run test:e2e
```

### Refresh documentation screenshots

```bash
npm run capture:screenshots
```

When Playwright can launch in your environment, this writes:

- `app/ui/public/screenshots/lexical-analysis.png`
- `app/ui/public/screenshots/translation-workflow.png`

The repo also includes committed SVG reference views used by the welcome page and GitHub-rendered docs:

- `app/ui/public/screenshots/lexical-analysis.svg`
- `app/ui/public/screenshots/translation-workflow.svg`

## What the workbench looks like

### Lexical analysis

![Lexical analysis reference view](app/ui/public/screenshots/lexical-analysis.svg)

### Translation workflow

![Translation workflow reference view](app/ui/public/screenshots/translation-workflow.svg)

## Documentation

- [`docs/README.md`](docs/README.md): documentation index
- [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md): contributor workflow
- [`docs/TRANSLATION_POLICY.md`](docs/TRANSLATION_POLICY.md): canonical vs alternate policy
- [`docs/AUDIT_POLICY.md`](docs/AUDIT_POLICY.md): audit requirements and reports
- [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md): upstream source and license policy
- [`docs/RELEASE_PROCESS.md`](docs/RELEASE_PROCESS.md): release workflow and protections

## Branch protection

The committed `.github/settings.yml` and `docs/RELEASE_PROCESS.md` capture the intended GitHub protection rules for `main`: required approvals, required CODEOWNERS review, and required passing workflows.
