---
description: Link a GitHub issue to a unit and write the audit record.
argument-hint: <unit_id> <issue_number>
allowed-tools: Bash(psalms-workbench link-issue:*)
---

Link issue `#$2` to unit `$1`. Writes an `AuditRecord` automatically via
`github_link_service`.

!`psalms-workbench link-issue $1 $2`
