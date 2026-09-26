import { useState } from 'react';

import { useDecideRebuild } from '../hooks/useComparisonAssessments';
import type { AccuracyRating, Rebuild, VerseNote } from '../types';
import { layerLabel, shortTime, type VerseCodex } from './verseActions';
import { diffWords } from './wordDiff';

const TONE: Record<AccuracyRating, 'close' | 'interpret' | 'caution'> = {
  literal: 'close',
  very_close: 'close',
  close: 'close',
  adapted: 'interpret',
  interpretive: 'interpret',
  omission: 'caution',
  no_source_basis: 'caution',
};

export function Fidelity({ rating }: { rating: AccuracyRating | null }) {
  if (!rating) return <span className="fidelity">Not assessed</span>;
  return <span className={`fidelity fidelity--${TONE[rating]}`}>{rating.replace(/_/g, ' ')}</span>;
}

export function Diff({ before, after, side }: { before: string; after: string; side: 'before' | 'after' }) {
  return (
    <p className="verse-text rebuild-diff">
      {diffWords(before, after).map((part, index) => {
        if (part.kind === 'same') return <span key={index}>{part.text}</span>;
        if (part.kind === 'remove') {
          return side === 'before' ? <del key={index}>{part.text}</del> : null;
        }
        return side === 'after' ? <ins key={index}>{part.text}</ins> : null;
      })}
    </p>
  );
}

interface Props {
  psalmId: string;
  unitId: string;
  rebuild: Rebuild;
  notes: VerseNote[];
  /** The verse's current fidelity, to show beside the rebuilt text's. */
  currentRating: AccuracyRating | null;
  codex: VerseCodex;
  /** Discard, then take the reviewer to the note composer. */
  onRevise: () => void;
}

/** A held rebuild beside the current text, the notes it answered, and its blind audit. */
export function RebuildReview({
  psalmId,
  unitId,
  rebuild,
  notes,
  currentRating,
  codex,
  onRevise,
}: Props) {
  const decide = useDecideRebuild(psalmId);
  const responses = new Map(rebuild.note_responses.map((item) => [item.note_id, item.response]));
  const [addressed, setAddressed] = useState<Set<string>>(
    () => new Set(rebuild.note_ids.filter((noteId) => responses.has(noteId))),
  );
  const layers = Object.entries(rebuild.texts);
  const replacesAll = layers.every(([, text]) => text.replaces_current);
  const analysis = rebuild.analysis;

  const choose = (decision: 'accept' | 'discard', after?: () => void) =>
    decide.mutate(
      { unitId, rebuildId: rebuild.rebuild_id, decision, addressedNoteIds: [...addressed] },
      { onSuccess: after },
    );

  return (
    <section className="rebuild-review" aria-label="Rebuilt verse">
      <div className="rebuild-review__head">
        <h4 className="rebuild-panel__title">
          Rebuilt with {rebuild.note_ids.length} note{rebuild.note_ids.length === 1 ? '' : 's'}
        </h4>
        <span className="verse-notes__hint">{shortTime(rebuild.created_at)}</span>
        <span className="verse-actions__spacer" />
        {analysis ? (
          <span className="rebuild-review__fidelity">
            <Fidelity rating={currentRating} /> <span aria-hidden="true">→</span>{' '}
            <Fidelity rating={analysis.accuracy_rating} />
          </span>
        ) : null}
      </div>

      {layers.map(([layer, text]) => (
        <div key={layer} className="rebuild-review__pair">
          <div className="rebuild-review__side">
            <h5 className="verse-label">Current {layerLabel(layer).toLowerCase()}</h5>
            <Diff before={text.previous ?? ''} after={text.rebuilt ?? ''} side="before" />
          </div>
          <div className="rebuild-review__side rebuild-review__side--new">
            <h5 className="verse-label">Rebuilt {layerLabel(layer).toLowerCase()} · proposed</h5>
            <Diff before={text.previous ?? ''} after={text.rebuilt ?? ''} side="after" />
          </div>
          {!text.replaces_current ? (
            <p className="rebuild-review__warning">
              The current {layer} has been reviewed, so keeping the rebuild adds it as a proposal
              for review rather than replacing what is shown.
            </p>
          ) : null}
        </div>
      ))}
      {!('literal' in rebuild.texts) ? (
        <p className="verse-notes__hint">Literal unchanged: it was not rebuilt.</p>
      ) : null}

      {rebuild.note_ids.length > 0 ? (
        <div className="rebuild-review__notes">
          <div className="verse-notes__title">
            <h5 className="verse-label">Your notes against the rebuild</h5>
            <span className="verse-notes__hint">
              The translator's account is its own report; you decide whether each note is addressed
            </span>
          </div>
          {rebuild.note_ids.map((noteId) => {
            const note = notes.find((item) => item.note_id === noteId);
            const number = note ? notes.indexOf(note) + 1 : '?';
            return (
              <div key={noteId} className="rebuild-review__check">
                <span className="chip chip-gold">Note {number}</span>
                <p className="note-card__text">{note?.text ?? noteId}</p>
                <p className="note-prose">
                  <span className="verse-label">Translator says</span>
                  {responses.get(noteId) ?? 'No account given.'}
                </p>
                <label>
                  <input
                    type="checkbox"
                    checked={addressed.has(noteId)}
                    onChange={(event) =>
                      setAddressed((current) => {
                        const next = new Set(current);
                        if (event.target.checked) next.add(noteId);
                        else next.delete(noteId);
                        return next;
                      })
                    }
                  />{' '}
                  Addressed
                </label>
              </div>
            );
          })}
        </div>
      ) : null}

      {analysis ? (
        <div className="rebuild-review__analysis">
          <div>
            <h5 className="verse-label">New analysis · blind to your notes</h5>
            <Fidelity rating={analysis.accuracy_rating} />
          </div>
          <div>
            <h5 className="verse-label">Accuracy</h5>
            <p className="note-prose">{analysis.accuracy_note}</p>
          </div>
          <div>
            <h5 className="verse-label">Creative liberties</h5>
            <p className="note-prose">{analysis.creative_liberties_note}</p>
          </div>
        </div>
      ) : (
        <div className="verse-actions">
          <span className="verse-notes__hint">The rebuilt text has not been analysed yet.</span>
          <button
            type="button"
            disabled={!codex.ready || codex.busy}
            title={codex.hint}
            onClick={codex.analyseRebuild}
          >
            Analyse rebuilt text
          </button>
        </div>
      )}

      <div className="rebuild-review__decide">
        <span className="verse-notes__hint">
          Whichever you keep stays proposed. Canonical still needs 2 qualified approvals.
        </span>
        <span className="verse-actions__spacer" />
        <button type="button" disabled={decide.isPending} onClick={() => choose('discard', onRevise)}>
          Revise notes and rebuild again
        </button>
        <button type="button" disabled={decide.isPending} onClick={() => choose('discard')}>
          Discard rebuilt
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={decide.isPending}
          onClick={() => choose('accept')}
        >
          {replacesAll ? 'Use rebuilt' : 'Keep rebuilt as a proposal'}
        </button>
      </div>
      {decide.isError ? <p className="comparison-error">{String(decide.error)}</p> : null}
    </section>
  );
}

export default RebuildReview;
