# Audit Policy

Every content mutation must create an `AuditRecord` with hashes, rationale, trigger links, and checks.

Required report outputs:

- uncovered tokens
- unaligned spans
- drift flags
- provenance gaps
- canonical changes since previous release

Release export must include `AUDIT_REPORT` and `OPEN_CONCERNS`.
