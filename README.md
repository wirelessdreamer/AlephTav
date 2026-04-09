# Psalms Copyleft Workbench

Local-first workbench for Hebrew-source Psalms translation, alignment, review, audit, and release packaging.

## What is included

- Git-friendly JSON content as canonical source of truth.
- SQLite-derived indexes for concordance, lexical cards, and jobs.
- FastAPI backend and Typer CLI.
- React + TypeScript workbench UI.
- Schema validation, license auditing, audit trails, issue/PR linkage, and release bundles.

## Quick start

### Backend

```bash
python -m venv .venv
source /home/dreamer/src/AlphaOmega/.venv/bin/activate
pip install -e .[dev]
python scripts/seed_project.py
python scripts/import_psalms.py
python scripts/build_indexes.py
python scripts/validate_content.py
uvicorn app.api.main:app --reload
```

### UI

```bash
npm install
npm run dev
```

### CLI

```bash
psalms-workbench validate-content
psalms-workbench audit-licenses
psalms-workbench export-release --release-id v0.1.0
```

## Branch protection

The committed `.github/settings.yml` and `docs/RELEASE_PROCESS.md` capture the intended GitHub protection rules for `main`: required approvals, required CODEOWNERS review, and required passing workflows.
