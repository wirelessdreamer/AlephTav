---
description: Link a GitHub pull request to a unit and write the audit record.
argument-hint: <unit_id> <pr_number>
allowed-tools: Bash(psalms-workbench link-pr:*)
---

Link PR `#$2` to unit `$1`. Writes an `AuditRecord` automatically via
`github_link_service`.

!`psalms-workbench link-pr $1 $2`
