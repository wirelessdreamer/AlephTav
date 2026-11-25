import { Fragment, useId, useState } from 'react';

import { useTranslationChoices } from '../hooks/useTranslationChoices';
import type { ArrangementView, IntentionalTranslationChoice } from '../types';
import { RequestStatus } from './RequestStatus';
import { followContextFootnote } from './TranslationChoices';

interface Footnote {
  number: number;
  entry: IntentionalTranslationChoice;
}

const concernsLine = (note: Footnote, lineId: string) =>
  note.entry.choice.targets.some(target => target.id === lineId);

/** The setting as a plain lyric sheet: title, then each section's label and sung lines. */
function lyricSheet(view: ArrangementView, notes: Footnote[]): string {
  const blocks: string[] = [view.arrangement.title];
  let sectionId: string | null = null;
  for (const sung of view.sung) {
    if (sung.section_id !== sectionId) {
      sectionId = sung.section_id;
      blocks.push(`\n[${sung.section_label || sung.kind}]`);
    }
    blocks.push(sung.line.text + notes.filter(note => concernsLine(note, sung.line.line_id))
      .map(note => `[${note.number}]`).join(''));
  }
  if (notes.length) blocks.push('\nContext footnotes', ...notes.map(note =>
    `[${note.number}] ${note.entry.choice.context_note}`));
  return blocks.join('\n');
}

/** The song setting as raw text, in sung order with repeats written out, to copy. */
export function ArrangementText({ view }: { view: ArrangementView }) {
  const { arrangement, sung } = view;
  const { query } = useTranslationChoices(arrangement.psalm_id, arrangement.translation_id ?? null,
    { arrangementId: arrangement.arrangement_id });
  const scope = useId();
  const noteId = (number: number) => `${scope}-context-note-${number}`;
  const referenceId = (number: number, position: number) => `${scope}-context-reference-${number}-${position}`;
  const context = sung.map(item => item.line.text).join('\n');
  // Both independently fetched views must agree before a note is attached to live lyrics.
  const notes: Footnote[] = (query.error || query.isFetching ? [] : query.data?.choices ?? []).filter(entry =>
    entry.target_state === 'current' && !entry.superseded_by_audit_id && entry.choice.context_note.trim() &&
    entry.choice.targets.length > 0 && entry.choice.targets.every(target =>
      target.kind === 'arrangement_line' && target.arrangement_id === arrangement.arrangement_id &&
      (target.translation_id ?? null) === (arrangement.translation_id ?? null) &&
      target.layer === arrangement.layer && target.context_text === context &&
      sung.some(item => item.line.line_id === target.id && item.line.text === target.text) &&
      query.data?.targets.some(current => current.kind === target.kind && current.id === target.id &&
        current.arrangement_id === target.arrangement_id && current.revision.value === target.revision.value)))
    .sort((left, right) => {
      const first = (entry: IntentionalTranslationChoice) => sung.findIndex(item =>
        entry.choice.targets.some(target => target.id === item.line.line_id));
      return first(left) - first(right) || left.audit_id.localeCompare(right.audit_id);
    }).map((entry, index) => ({ number: index + 1, entry }));
  const text = lyricSheet(view, notes);
  const [copied, setCopied] = useState<{ text: string; status: 'yes' | 'failed' } | null>(null);
  const copyAvailable = Boolean(query.data) && !query.error && !query.isFetching;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied({ text, status: 'yes' });
    } catch {
      setCopied({ text, status: 'failed' });
    }
  };

  return (
    <div className="arr-text">
      <div className="arr-text__actions">
        <button
          type="button"
          className="btn-primary"
          disabled={!copyAvailable}
          onClick={() => void copy()}
        >
          {notes.length ? 'Copy text with footnotes' : 'Copy text'}
        </button>
        <span className="subtle" aria-live="polite">
          {copyAvailable && copied?.text === text ? (copied.status === 'yes' ? 'Copied.' : 'Copy failed; select the text instead.') : ''}
        </span>
      </div>
      <RequestStatus loading={query.isFetching} error={query.error}
        label={query.isFetching ? 'Loading context footnotes before copying…' : 'Could not load context footnotes. Copy is unavailable until they can be checked.'}
        onRetry={() => void query.refetch()} />
      <pre className="arr-text__sheet">{notes.length ? <>
        {arrangement.title}{sung.map((item, index) => <Fragment key={item.position}>
          {index === 0 || sung[index - 1].section_id !== item.section_id ?
            `\n\n[${item.section_label || item.kind}]` : ''}
          {'\n'}{item.line.text}{notes.filter(note => concernsLine(note, item.line.line_id)).map(note =>
            <sup key={note.number}><a id={referenceId(note.number, item.position)} href={`#${noteId(note.number)}`}
              aria-label={`Context footnote ${note.number} for lyric line ${item.position}`}
              onClick={event => followContextFootnote(event, noteId(note.number))}>[{note.number}]</a></sup>)}
        </Fragment>)}
      </> : lyricSheet(view, [])}</pre>
      {notes.length ? <section aria-label="Context footnotes">
        <h3>Context footnotes</h3>
        <ol>{notes.map(note => <li key={note.entry.audit_id} id={noteId(note.number)} tabIndex={-1}>
          <p className="note-prose">{note.entry.choice.context_note}</p>
          {sung.filter(item => concernsLine(note, item.line.line_id)).map((item, index) =>
            <span key={item.position}>{index > 0 ? ' · ' : ''}<a href={`#${referenceId(note.number, item.position)}`}
              aria-label={`Back to lyric line ${item.position} from footnote ${note.number}`}
              onClick={event => followContextFootnote(event, referenceId(note.number, item.position))}>
              Back to line {item.position}</a></span>)}
        </li>)}</ol>
      </section> : null}
    </div>
  );
}

export default ArrangementText;
