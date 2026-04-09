# Release Process

1. Freeze `main` for release candidate.
2. Run validation, tests, license audit, and report generation.
3. Confirm no high-severity unresolved canonical drift.
4. Confirm reviewer signoff completeness.
5. Generate release bundle with `LICENSE`, `NOTICE`, `SOURCES`, `AUDIT_REPORT`, and `OPEN_CONCERNS`.

## Intended branch protection

- Require pull requests for `main`
- Require 2 approvals for canonical changes
- Require CODEOWNERS review
- Require `validate`, `test`, and `audit` workflows
- Dismiss stale reviews when the branch changes
