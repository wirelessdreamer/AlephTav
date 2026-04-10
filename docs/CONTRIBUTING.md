# Contributing

1. Open a structured GitHub issue against the precise Psalm, unit, token, span, or alternate.
2. Create a branch from `main`.
3. Run `python scripts/validate_content.py` and `python scripts/build_indexes.py`.
4. Edit canonical JSON only for reviewed canonical work; alternates must remain alternate unless explicitly promoted.
5. Open a PR using the repository template and request the required reviewers.

Never bypass audit record creation, source manifest updates, or license checks.

## Main Worktree Hygiene For Task Handoffs

Detached-head task worktrees may cherry-pick commits back onto the base `main` worktree. Before handing off or receiving task commits:

1. Confirm the base worktree is not in an in-progress Git operation.
2. Check for `.git/MERGE_HEAD`, `.git/CHERRY_PICK_HEAD`, `.git/REVERT_HEAD`, `.git/sequencer`, `.git/rebase-apply`, and `.git/rebase-merge`.
3. Treat `.git/AUTO_MERGE` as temporary merge metadata. If it exists by itself, but none of the actual in-progress markers above exist and `git status` shows no unmerged paths, remove the stale `.git/AUTO_MERGE` file before the next handoff.
4. Preserve unrelated uncommitted user edits in the base worktree. Do not use destructive cleanup commands to clear handoff state.
5. If a local edit overlaps the incoming cherry-pick, resolve that conflict explicitly instead of discarding the local change.

Practical rule: only clear stale Git state after verifying that no active merge, cherry-pick, revert, or rebase is still in progress.
