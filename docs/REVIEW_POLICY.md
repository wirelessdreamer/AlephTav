# Review Policy

Reviewer roles:

- lexical reviewer
- Hebrew reviewer
- alignment reviewer
- lyric reviewer
- theology reviewer
- release reviewer

Merge policy:

- Alternate addition: at least 1 qualified approval.
- Canonical promotion/change: at least 2 qualified approvals.
- Release: release reviewer signoff plus passing audit workflows.

Song settings (arrangements):

A song setting may span verses, sing a section again, and depart from the Hebrew.
Each line names the Hebrew tokens it renders and how it departs from them. Before a
setting is accepted, each departure needs approvals from distinct qualified reviewers:

- Tracks the Hebrew, reordered within its words, or a section sung again: none.
- Compressed, expanded, or added (renders nothing in the Hebrew there): 1.
- Hebrew the setting does not carry: 2, the first stating why it is left out.

Editing a line clears its approvals. A project can change these counts under
`review_policy.arrangement_required_approvals` in `project.json`.
