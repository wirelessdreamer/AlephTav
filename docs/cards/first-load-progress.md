# First-Load Progress For Psalms Workbench

## Problem

On initial app load, the workbench can take a few seconds to fetch project metadata and the Psalms corpus. During that gap, the Psalm dropdown appears empty, which looks broken even when the data is still loading normally.

## Goal

Make first-load startup state explicit so users can tell the workbench is still loading corpus data rather than failing silently.

## Scope

- Add a page-level loading state for initial `/project` and `/psalms` hydration.
- Disable the Psalm selector until the Psalms list is ready.
- Show startup progress copy near the selector area, including a longer-wait message for large-corpus initialization.
- Add an explicit empty state when the Psalms list resolves successfully but contains no options.
- Add an explicit error state when Psalms bootstrap requests fail.

## Acceptance Criteria

- On first load, the workbench shows a visible loading state before Psalm options are available.
- The Psalm dropdown cannot be opened or changed while corpus data is still loading.
- If startup loading exceeds a short threshold, the UI shows a secondary progress message such as `Indexing large corpus... this can take a moment`.
- Once Psalms data resolves, the loading state clears and the selector is populated normally.
- If `/psalms` returns an empty list, the UI shows a clear empty-state message instead of a blank selector.
- If `/project` or `/psalms` fails, the UI shows a clear error state with enough context to distinguish failure from loading.

## Notes

- Prefer inline loading and status affordances over a blocking modal dialog.
- Keep the existing workbench layout intact; this is a startup-state improvement, not a redesign.
