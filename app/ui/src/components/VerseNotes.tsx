import { useState } from 'react';

import {
  useAddVerseNote,
  useRemoveVerseNote,
  useUpdateVerseNote,
} from '../hooks/useComparisonAssessments';
import type { VerseNote } from '../types';
import { layerLabel, shortTime, type VerseCodex } from './verseActions';

interface Props {
  psalmId: string;
  /** The translation a new note belongs to; null is the psalm's main one. */
  translationId: string | null;
  unitId: string;
  notes: VerseNote[];
  englishLayer: string;
  /** Text quoted from the accuracy or liberties note, waiting to go into a new note. */
  quote: string;
  onClearQuote: () => void;
  composerId: string;
  hasPendingRebuild: boolean;
  codex: VerseCodex;
}

type AppliesTo = VerseNote['applies_to'];

function appliesLabel(appliesTo: AppliesTo, englishLayer: string): string {
  if (appliesTo === 'literal') return 'Literal';
  if (appliesTo === 'english') return layerLabel(englishLayer);
  return 'Literal and ' + layerLabel(englishLayer).toLowerCase();
}

function NoteCard({
  note,
  number,
  englishLayer,
  psalmId,
  unitId,
}: {
  note: VerseNote;
  number: number;
  englishLayer: string;
  psalmId: string;
  unitId: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(note.text);
  const update = useUpdateVerseNote(psalmId);
  const remove = useRemoveVerseNote(psalmId);

  return (
    <li className={`note-card note-card--${note.status}`}>
      <div className="note-card__head">
        <span className="chip chip-gold">Note {number}</span>
        <span className="chip">{appliesLabel(note.applies_to, englishLayer)}</span>
        <span className="chip">{note.kind === 'instruction' ? 'Instruction for rebuild' : 'Comment'}</span>
        {note.status === 'addressed' ? <span className="chip chip-good">Addressed</span> : null}
        <span className="verse-actions__spacer" />
        {!editing ? (
          <>
            <button type="button" className="btn-sm" onClick={() => setEditing(true)}>
              Edit
            </button>
            <button
              type="button"
              className="btn-sm"
              disabled={remove.isPending}
              onClick={() => remove.mutate({ unitId, noteId: note.note_id })}
            >
              Remove
            </button>
          </>
        ) : null}
      </div>
      {editing ? (
        <div className="note-card__edit">
          <textarea
            aria-label={`Edit note ${number}`}
            value={draft}
            rows={2}
            onChange={(event) => setDraft(event.target.value)}
          />
          <div className="verse-edit-actions">
            <button
              type="button"
              disabled={!draft.trim() || update.isPending}
              onClick={() =>
                update.mutate(
                  { unitId, noteId: note.note_id, text: draft },
                  { onSuccess: () => setEditing(false) },
                )
              }
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => {
                setDraft(note.text);
                setEditing(false);
              }}
            >
              Cancel
            </button>
            {note.status === 'addressed' ? (
              <button
                type="button"
                onClick={() => update.mutate({ unitId, noteId: note.note_id, status: 'open' })}
              >
                Reopen
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="note-card__text">{note.text}</p>
      )}
      {note.quote ? <blockquote className="note-card__quote">“{note.quote}”</blockquote> : null}
      <span className="note-card__meta">
        {note.created_by} · {shortTime(note.created_at)}
      </span>
      {update.isError || remove.isError ? (
        <p className="comparison-error">{String(update.error ?? remove.error)}</p>
      ) : null}
    </li>
  );
}

/** A reviewer's notes on the verse, a composer, and the rebuild they feed. */
export function VerseNotes({
  psalmId,
  translationId,
  unitId,
  notes,
  englishLayer,
  quote,
  onClearQuote,
  composerId,
  hasPendingRebuild,
  codex,
}: Props) {
  const [text, setText] = useState('');
  const [appliesTo, setAppliesTo] = useState<AppliesTo>('english');
  const [kind, setKind] = useState<VerseNote['kind']>('instruction');
  const add = useAddVerseNote(psalmId, translationId);

  const open = notes.filter((note) => note.status === 'open');
  const addressed = notes.filter((note) => note.status === 'addressed');
  const instructions = open.filter((note) => note.kind === 'instruction');
  const count = (layer: 'literal' | 'english') =>
    instructions.filter((note) => note.applies_to === layer || note.applies_to === 'both').length;
  const literalCount = count('literal');
  const englishCount = count('english');

  const [rebuildLiteral, setRebuildLiteral] = useState<boolean | null>(null);
  const [rebuildEnglish, setRebuildEnglish] = useState<boolean | null>(null);
  const [reanalyse, setReanalyse] = useState(true);
  // Until the reviewer touches a box, a layer is rebuilt when a note targets it.
  const literalOn = rebuildLiteral ?? literalCount > 0;
  const englishOn = rebuildEnglish ?? englishCount > 0;
  const layers = [
    ...(literalOn ? (['literal'] as const) : []),
    ...(englishOn ? (['english'] as const) : []),
  ];
  const sending = new Set(
    instructions
      .filter(
        (note) =>
          (literalOn && note.applies_to !== 'english') ||
          (englishOn && note.applies_to !== 'literal'),
      )
      .map((note) => note.note_id),
  ).size;

  const blocked = hasPendingRebuild
    ? 'Decide on the rebuild above first.'
    : !codex.ready
      ? codex.hint
      : codex.busy
        ? 'Codex is busy with another task.'
        : layers.length === 0
          ? 'Choose at least one layer to rebuild.'
          : undefined;
  const layerNames = layers.map((layer) =>
    layer === 'literal' ? 'literal' : layerLabel(englishLayer).toLowerCase(),
  );

  function save() {
    add.mutate(
      { unitId, text, applies_to: appliesTo, kind, quote: quote || undefined },
      {
        onSuccess: () => {
          setText('');
          onClearQuote();
        },
      },
    );
  }

  return (
    <section className="verse-notes" aria-label="Notes on this verse">
      <div className="verse-notes__main">
        <div className="verse-notes__title">
          <h4 className="verse-label">Your notes on this verse</h4>
          <span className="verse-notes__hint">
            Saved with the verse and recorded in its audit trail
          </span>
        </div>

        {open.length > 0 ? (
          <ol className="verse-notes__list">
            {open.map((note) => (
              <NoteCard
                key={note.note_id}
                note={note}
                number={notes.indexOf(note) + 1}
                englishLayer={englishLayer}
                psalmId={psalmId}
                unitId={unitId}
              />
            ))}
          </ol>
        ) : null}

        <div className="verse-notes__composer">
          <label htmlFor={composerId} className="verse-label">
            New note
          </label>
          {quote ? (
            <div className="verse-notes__quote-draft">
              <blockquote className="note-card__quote">“{quote}”</blockquote>
              <button type="button" className="btn-sm" onClick={onClearQuote} aria-label="Remove quote">
                ×
              </button>
            </div>
          ) : null}
          <textarea
            id={composerId}
            rows={2}
            value={text}
            placeholder="Tell the translator what to change, or leave yourself a comment…"
            onChange={(event) => setText(event.target.value)}
          />
          <div className="verse-actions">
            <span className="verse-notes__hint">Applies to</span>
            <div className="segmented" role="group" aria-label="Applies to">
              {(['literal', 'english', 'both'] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={appliesTo === value}
                  onClick={() => setAppliesTo(value)}
                >
                  {value === 'literal' ? 'Literal' : value === 'english' ? layerLabel(englishLayer) : 'Both'}
                </button>
              ))}
            </div>
            <div className="segmented" role="group" aria-label="Kind of note">
              <button type="button" aria-pressed={kind === 'instruction'} onClick={() => setKind('instruction')}>
                Instruction for rebuild
              </button>
              <button type="button" aria-pressed={kind === 'comment'} onClick={() => setKind('comment')}>
                Comment only
              </button>
            </div>
            <span className="verse-actions__spacer" />
            <button type="button" disabled={!text.trim() || add.isPending} onClick={save}>
              {add.isPending ? 'Saving…' : 'Save note'}
            </button>
          </div>
          {add.isError ? <p className="comparison-error">{String(add.error)}</p> : null}
        </div>

        {addressed.length > 0 ? (
          <details className="verse-notes__addressed">
            <summary>
              {addressed.length} addressed note{addressed.length === 1 ? '' : 's'}
            </summary>
            <ol className="verse-notes__list">
              {addressed.map((note) => (
                <NoteCard
                  key={note.note_id}
                  note={note}
                  number={notes.indexOf(note) + 1}
                  englishLayer={englishLayer}
                  psalmId={psalmId}
                  unitId={unitId}
                />
              ))}
            </ol>
          </details>
        ) : null}
      </div>

      <aside className="rebuild-panel" aria-label="Rebuild with your notes">
        <h4 className="rebuild-panel__title">Rebuild with your notes</h4>
        <p className="note-prose">
          Codex retranslates with the psalm's guidance, your instructions and the Hebrew. The
          current text stays until you choose.
        </p>
        <fieldset className="rebuild-panel__options">
          <legend className="verse-label">Rebuild</legend>
          <label>
            <input
              type="checkbox"
              checked={englishOn}
              onChange={(event) => setRebuildEnglish(event.target.checked)}
            />
            {layerLabel(englishLayer)} <span className="verse-notes__hint">· {englishCount} note{englishCount === 1 ? '' : 's'}</span>
          </label>
          <label>
            <input
              type="checkbox"
              checked={literalOn}
              onChange={(event) => setRebuildLiteral(event.target.checked)}
            />
            Literal <span className="verse-notes__hint">· {literalCount} note{literalCount === 1 ? '' : 's'}</span>
          </label>
          <label className="rebuild-panel__reanalyse">
            <input
              type="checkbox"
              checked={reanalyse}
              onChange={(event) => setReanalyse(event.target.checked)}
            />
            Re-analyse the verse afterwards
          </label>
        </fieldset>
        <p className="rebuild-panel__blind">
          The accuracy audit never sees your notes. It judges the rebuilt text against the Hebrew on
          its own, the same way it ignores the psalm's guidance.
        </p>
        <button
          type="button"
          className="btn-primary"
          disabled={Boolean(blocked)}
          title={blocked}
          onClick={() => codex.rebuild({ layers: [...layers], reanalyse })}
        >
          Rebuild {layerNames.join(' and ') || 'verse'}
          {sending > 0 ? ` with ${sending} note${sending === 1 ? '' : 's'}` : ''}
        </button>
        {blocked && hasPendingRebuild ? <p className="verse-notes__hint">{blocked}</p> : null}
      </aside>
    </section>
  );
}

export default VerseNotes;
