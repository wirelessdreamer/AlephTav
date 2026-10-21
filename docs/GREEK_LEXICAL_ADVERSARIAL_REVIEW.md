# Greek lexical implementation plan adversarial review

Date: 2026-10-17. Status: completed; all twelve findings addressed in the revised plan.
This is an independent AI review of a design, not a Greek specialist sign-off, license
determination, implementation test result, or approval to change canonical content.

## Review scope and evidence

Three reviewers received the same frozen candidate and reviewed it independently, without
the planning researchers' conversation history. Their scopes were architecture and failure
safety, Greek data and reference semantics, and product delivery and acceptance. Each read
`CLAUDE.md` first and could inspect current code and primary upstream evidence. The task
was to find concrete counterexamples and minimum corrections, not feature wish lists.

The [original review candidate](planning/greek_lexical_review_candidate.md) has SHA-256
`de7e1d8498e7b66a827556895e065c45104185c454a7849b2052f2d262b2b673`.
Candidate line numbers below refer to that retained snapshot. The revised technical plan
reviewed in the second pass has SHA-256
`21b75b5039857d12fc2205535d252de0e21ea4df003fd34e597c9b75db98e7ca`.
The final plan adds completion metadata; its checksum is in
[the validation record](planning/greek_lexical_validation.json).

Validation included direct temporary-workspace probes of ID routing, Greek schema rejection,
destructive rebuild failure and weak anchor membership checks. Research inspected pinned
upstream artifacts, source formats, counts, identifier relations, tag schemes and license
notices. These constrain the plan; they do not establish that future importers or runtime
gates work already.

## Findings and corrections

There were no P0 findings, five P1 findings and seven P2 findings. All are closed at the
plan level. Their associated implementation tests still need to be written and passed.

| ID | Severity and candidate lines | Concrete failure | Correction in final plan |
|---|---|---|---|
| A1 | P1; 238–241, 257–273 | Canonical r2 could activate while queries used catalog r1; an old builder could overwrite a newer publication | Sections 5–7 use a single complete study snapshot and predecessor comparison under a publication lock, with fault/concurrent-builder tests |
| A2 | P1; 225–236, 268–285, 329–331 | Retained catalogs, cached cards or rollback could revive a source after permission revocation | Section 7 applies current policy to every retained snapshot, invalidates caches by policy revision and prevents rollback from restoring permissions |
| A3 | P1; 142–151, 340–350 | An MT source correction could change an accepted bridge endpoint while its Hebrew token ID stayed the same | Sections 5, 7 and 8 retain source-only MT snapshots. W2 defines the contract, W4 captures it and W9 binds endpoints to snapshot plus token ID |
| A4 | P2; 144–145, 158–160, 185–197, 212–215 | A shared lexeme/crosswalk edit could change already reviewed analysis meaning | Section 5 retains immutable lexical sets, explicit merge/split mappings and affected-analysis/approval reevaluation |
| A5 | P2; 257–261, 363, 433–438 | Operational-table copies could lose concurrent job writes or remain subject to derived cleanup | Section 7 chooses durable local storage, writer quiescence, transactional copy/verification, an idempotent marker and recoverable routing switch |
| A6 | P2; 212–216, 401 | An earlier approval could still count after request_changes on the same payload | Section 5 uses each reviewer's latest applicable decision, including withdrawal/rejection effects, with a same-hash regression |
| D1 | P2; 299, 324–327, 397 | English/KJV dictionary references could be mistaken for LXX/MT numbering, producing wrong links | Section 8 retains citation baselines and original labels, maps title offsets and tests TBESG G0020/G0082 against Swete 44:16/50:8 |
| D2 | P2; 187–196, 280–284 | A two-token G1508 expression could count twice; G2504 components could create imaginary printed words | Sections 5 and 7 define expression occurrences, separate physical-token/match totals and opt-in component expansion with explicit fixtures |
| U1 | P1; 280–285 | Homographs and competing analyses could merge definitions, duplicate hits or disagree with card counts | Section 7 defines typed query identity, analysis scope/selection, deduplication, unresolved coverage and a shared count/page predicate |
| U2 | P1; 312–315 | Project membership could reject outside-project occurrence navigation, including empty projects/Ps151 | Section 8 separates source navigation from translation ownership, shows missing-English states and preserves both MT9 and MT10 |
| U3 | P2; 298–301, 329–331 | A rebuild between the card and first occurrence request could mix old counts with new pages | Section 8 requires the card's study snapshot on dependent calls, including first pages; stale views restart coherently |
| U4 | P2; 368, 377–379 | Release B promised distributions without a service owner or counting denominator | W9 and section 8 own the distribution API/view, count accepted groups with opposite-side signatures, and test exact group/token/coverage totals |

The author also strengthened coverage and sampling gates. Release A cannot pass solely on
a tiny accurate subset: it has token/dictionary coverage targets, a proportional expert
sample and a separately reported adversarial set. These remain proposed acceptance targets,
not measured quality.

## Second review pass

Each reviewer checked the revised technical-plan hash against their original findings.

| Reviewer scope | Recheck result | Remaining design findings reported |
|---|---|---|
| Architecture and failure safety | A1–A6 closed; corresponding failure cases included in acceptance | None within that review's scope |
| Greek data and reference semantics | D1–D2 closed; citation baselines, occurrence cardinality and quality-target qualifications checked | None within that review's scope |
| Product delivery and acceptance | U1–U4 closed; membership, navigation, snapshots and distribution ownership checked | None within that review's scope |

The second pass reported no remaining P1 design contradiction. This bounded review is not
proof that no future issue exists. Changes to technical choices, sources or scope require
the affected plan and tests to be reviewed again.

## Remaining implementation gates

The plan is specific enough to implement its foundations. Full release still requires:

1. Owner/schema-owner agreement on edition-qualified IDs, package audits, intake policy and
   source capabilities. Existing raw immutability remains in force.
2. An immutable Swete package with released bytes, licensing/attribution, provenance,
   edition exceptions and owner sampling. Current modified sibling HEAD is not that package;
   the source bounding-box requirement also needs resolution.
3. Source-specific license-lineage decisions, especially Middle Liddell/Perseus material.
   A repository badge cannot substitute for those decisions.
4. Qualified Greek review capacity, measured annotation coverage/accuracy and reviewed bridge
   gold data. Proposed seeds supply none of those approvals.
5. Passing future failure-injection, interface, accessibility, policy, export and performance
   tests. Executed planning probes validate current constraints, not future implementations.

No application feature, source import, schema or canonical-content change was made during
this planning/review task. Deliverables are the plan, this review, retained candidate and
machine-readable evidence.
