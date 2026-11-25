# Audit Policy

Every content mutation must create an `AuditRecord` with hashes, rationale, trigger links, and checks.

[Intentional translation choices](TRANSLATION_CHOICES.md) record deliberate
wording decisions, their reasons, and explicit limitations in supporting context.
These append-only, revision-bound statements preserve uncertainty and previous
entries; recording intent leaves translation text and review authority unchanged.

Required report outputs:

- uncovered tokens
- unaligned spans
- drift flags
- provenance gaps
- canonical changes since previous release

Release export must include `AUDIT_REPORT` and `OPEN_CONCERNS`.
