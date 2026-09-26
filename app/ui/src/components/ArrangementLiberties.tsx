import { type FocusEvent, type MouseEvent, useMemo, useState } from 'react';

import type { ArrangementEdit } from '../hooks/useArrangements';
import type {
  ArrangementView,
  ComparisonTableRow,
  Liberty,
  LibertyKind,
  PsalmAnalysisSection,
} from '../types';
import {
  LIBERTY_HINTS,
  LIBERTY_LABELS,
  REVIEWER_ROLES,
  type Reviewer,
  loadReviewer,
  saveReviewer,
  verseOf,
} from './arrangementShared';
import { type HoveredWord, WordContextCard, placeCard } from './WordContextCard';

interface Props {
  view: ArrangementView;
  edit: (change: ArrangementEdit) => Promise<unknown>;
  pending: boolean;
  /** The psalm's verses as the comparison table shows them, for a hovered word's context. */
  rows: ComparisonTableRow[];
  sections: PsalmAnalysisSection[];
  englishLayer: string;
}

/** What makes a Hebrew word show its context card while hovered or focused. */
type WordHover = (tokenId: string) => {
  tabIndex?: number;
  onMouseEnter?: (event: MouseEvent<HTMLElement>) => void;
  onFocus?: (event: FocusEvent<HTMLElement>) => void;
  onMouseLeave?: () => void;
  onBlur?: () => void;
};

const RULE_ORDER: LibertyKind[] = [
  'repeated',
  'reordered',
  'compressed',
  'expanded',
  'added',
  'dropped',
];

function LibertyRow({
  item,
  words,
  wordHover,
  reviewer,
  pending,
  edit,
}: {
  item: Liberty;
  /** The Hebrew words the liberty concerns, in order. */
  words: Array<{ token_id: string; surface: string }>;
  wordHover: WordHover;
  reviewer: Reviewer;
  pending: boolean;
  edit: Props['edit'];
}) {
  const [why, setWhy] = useState('');
  const needsWhy = item.kind === 'dropped' && !item.rationale;
  const alreadyMine = item.approvals.some((a) => a.reviewer === reviewer.name);
  const canApprove =
    item.required > 0 && !item.settled && Boolean(reviewer.name.trim()) && !alreadyMine;

  function approve() {
    if (item.kind === 'dropped') {
      void edit({
        method: 'POST',
        path: 'omissions/approvals',
        body: {
          unit_id: item.unit_id,
          token_ids: item.token_ids,
          reviewer: reviewer.name,
          reviewer_role: reviewer.role,
          rationale: why,
        },
      });
    } else {
      void edit({
        method: 'POST',
        path: `lines/${item.line_id}/approvals`,
        body: { reviewer: reviewer.name, reviewer_role: reviewer.role },
      });
    }
    setWhy('');
  }

  return (
    <tr className={item.settled ? 'is-settled' : undefined}>
      <td>
        <span className="verse-notes__hint">{item.kind === 'dropped' ? item.ref : item.label}</span>
        <span className="arr-lib__text">{item.text || '—'}</span>
      </td>
      <td>
        <span className={`arr-kind-chip arr-kind--${item.kind}`} title={LIBERTY_HINTS[item.kind]}>
          {LIBERTY_LABELS[item.kind]}
        </span>
      </td>
      <td lang="he" dir="rtl" className="hebrew arr-lib__he">
        {words.length > 0
          ? words.map((word, index) => (
              <span key={word.token_id}>
                {index > 0 ? ' ' : null}
                <span className="arr-lib__word" {...wordHover(word.token_id)}>
                  {word.surface}
                </span>
              </span>
            ))
          : item.hebrew}
      </td>
      <td className="arr-lib__why">
        {item.rationale ||
          (needsWhy ? (
            <input
              aria-label="Why this Hebrew is left out"
              placeholder="Why is it left out?"
              value={why}
              onChange={(event) => setWhy(event.target.value)}
            />
          ) : (
            <span className="verse-notes__hint">No reason given</span>
          ))}
      </td>
      <td className="arr-lib__review">
        <span className={`arr-review arr-review--${item.settled ? 'settled' : item.required > 1 ? 'two' : 'one'}`}>
          {item.required === 0
            ? 'Allowed'
            : item.settled
              ? 'Approved'
              : `${item.approvals.length} of ${item.required} approval${item.required === 1 ? '' : 's'}`}
        </span>
        {item.approvals.length > 0 ? (
          <span className="verse-notes__hint">
            {item.approvals.map((a) => `${a.reviewer} (${a.reviewer_role})`).join(', ')}
          </span>
        ) : null}
        {canApprove ? (
          <button
            type="button"
            className="btn-sm btn-primary"
            disabled={pending || (needsWhy && !why.trim())}
            title={needsWhy && !why.trim() ? 'Say why it is left out first' : undefined}
            onClick={approve}
          >
            Approve
          </button>
        ) : null}
      </td>
    </tr>
  );
}

/** Every Hebrew word's coverage, and every departure with the approvals it needs. */
export function ArrangementLiberties({
  view,
  edit,
  pending,
  rows,
  sections,
  englishLayer,
}: Props) {
  const [reviewer, setReviewer] = useState<Reviewer>(loadReviewer);
  const [hovered, setHovered] = useState<HoveredWord | null>(null);
  const { coverage, liberties, required_approvals: rules, summary, arrangement } = view;
  const open = liberties.filter((item) => !item.settled);
  const settled = liberties.filter((item) => item.settled);

  /** Each Hebrew word's verse, and each word's surface and each line's words by id. */
  const { rowOf, surfaceOf, lineWords } = useMemo(
    () => ({
      rowOf: new Map(
        rows.flatMap((row) => (row.tokens ?? []).map((token) => [token.token_id, row] as const)),
      ),
      surfaceOf: new Map(
        coverage.units.flatMap((unit) =>
          unit.tokens.map((token) => [token.token_id, token.surface] as const),
        ),
      ),
      lineWords: new Map(
        arrangement.sections.flatMap((section) =>
          section.lines.map(
            (line) => [line.line_id, line.anchors.flatMap((anchor) => anchor.token_ids)] as const,
          ),
        ),
      ),
    }),
    [rows, coverage, arrangement],
  );
  const hoveredRow = hovered ? rowOf.get(hovered.tokenId) : undefined;

  const wordHover: WordHover = (tokenId) =>
    rowOf.has(tokenId)
      ? {
          tabIndex: 0,
          onMouseEnter: (event) => setHovered(placeCard(tokenId, event.currentTarget)),
          onFocus: (event) => setHovered(placeCard(tokenId, event.currentTarget)),
          onMouseLeave: () => setHovered(null),
          onBlur: () => setHovered(null),
        }
      : {};

  /** The words a liberty concerns: its line's anchors, or the Hebrew it leaves out. */
  function wordsOf(item: Liberty) {
    const ids = item.token_ids ?? (item.line_id ? lineWords.get(item.line_id) : undefined) ?? [];
    return ids.map((id) => ({ token_id: id, surface: surfaceOf.get(id) ?? '' }));
  }

  function updateReviewer(next: Reviewer) {
    setReviewer(next);
    saveReviewer(next);
  }

  return (
    <div className="arr-liberties">
      <section className="arr-panel" aria-label="Hebrew coverage">
        <header className="arr-panel__head">
          <h3 className="verse-label">Every Hebrew word, and how often the song carries it</h3>
          <span className="arr-chip">{coverage.totals.words} words</span>
          <span className="arr-chip">{coverage.totals.once} once</span>
          <span className="arr-chip arr-chip--gold">{coverage.totals.repeated} repeated</span>
          <span className="arr-chip arr-chip--dropped">{coverage.totals.dropped} not carried</span>
        </header>
        {coverage.units.map((unit) => (
          <div key={unit.unit_id} className="arr-cover-words" dir="rtl">
            <span dir="ltr" className="arr-cover__v">
              {verseOf(unit.unit_id)}
            </span>
            {unit.tokens.map((token) => (
              <span
                key={token.token_id}
                lang="he"
                title={rowOf.has(token.token_id) ? undefined : token.gloss}
                className={`arr-word${token.count === 0 ? ' is-dropped' : token.count > 1 ? ' is-repeated' : ''}`}
                {...wordHover(token.token_id)}
              >
                {token.surface}
                {token.count > 1 ? <span dir="ltr">×{token.count}</span> : null}
              </span>
            ))}
          </div>
        ))}
      </section>

      <div className="arr-liberties__grid">
        <section className="arr-panel" aria-label="Liberties">
          <header className="arr-panel__head">
            <h3 className="verse-label">Liberties</h3>
            <span className="verse-notes__hint">
              {open.length === 0 ? 'Every liberty is settled.' : `${open.length} open`}
            </span>
          </header>
          {liberties.length === 0 ? (
            <p className="verse-notes__hint">The setting tracks the Hebrew throughout.</p>
          ) : (
            <table className="arr-lib">
              <thead>
                <tr>
                  <th>Line</th>
                  <th>Kind</th>
                  <th>Hebrew</th>
                  <th>Why</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {[...open, ...settled].map((item) => (
                  <LibertyRow
                    key={item.key}
                    item={item}
                    words={wordsOf(item)}
                    wordHover={wordHover}
                    reviewer={reviewer}
                    pending={pending}
                    edit={edit}
                  />
                ))}
              </tbody>
            </table>
          )}
        </section>

        <aside className="arr-liberties__aside">
          <section className="arr-panel">
            <h3 className="verse-label">Reviewing as</h3>
            <input
              aria-label="Your name"
              placeholder="Your name"
              value={reviewer.name}
              onChange={(event) => updateReviewer({ ...reviewer, name: event.target.value })}
            />
            <select
              aria-label="Your reviewer role"
              value={reviewer.role}
              onChange={(event) => updateReviewer({ ...reviewer, role: event.target.value })}
            >
              {REVIEWER_ROLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
          </section>
          <section className="arr-panel">
            <h3 className="verse-label">Approvals each kind needs</h3>
            {RULE_ORDER.map((kind) => (
              <div key={kind} className="arr-rule">
                <span>{LIBERTY_HINTS[kind]}</span>
                <span className={`arr-review arr-review--${rules[kind] === 0 ? 'settled' : rules[kind] > 1 ? 'two' : 'one'}`}>
                  {rules[kind] === 0 ? 'Allowed' : `${rules[kind]} approval${rules[kind] === 1 ? '' : 's'}`}
                </span>
              </div>
            ))}
            <p className="verse-notes__hint">
              Set in docs/REVIEW_POLICY.md. Editing a line clears its approvals.
            </p>
          </section>
          <section className="arr-panel">
            <h3 className="verse-label">The setting</h3>
            <p className="verse-notes__hint">
              {arrangement.status === 'accepted'
                ? 'Accepted.'
                : summary.open === 0
                  ? 'Every liberty is settled; the setting can be accepted.'
                  : `${summary.open} liberties must be settled before the setting is accepted.`}
            </p>
            {arrangement.status !== 'accepted' ? (
              <button
                type="button"
                className="btn-primary"
                disabled={pending || summary.open > 0}
                onClick={() => void edit({ method: 'PATCH', path: '', body: { status: 'accepted' } })}
              >
                Accept the setting
              </button>
            ) : null}
          </section>
        </aside>
      </div>

      {hovered && hoveredRow ? (
        <WordContextCard
          hovered={hovered}
          row={hoveredRow}
          sections={sections}
          sung={view.sung}
          englishLayer={englishLayer}
        />
      ) : null}
    </div>
  );
}

export default ArrangementLiberties;
