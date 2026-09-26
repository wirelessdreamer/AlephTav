import { useEffect, useId, useMemo, useRef, useState } from 'react';

import type { Collection, PsalmIdentification, PsalmSummary } from '../types';
import type { ArrangementPane } from './ArrangementWorkspace';

export interface ImportStep {
  key: string;
  label: string;
  status: 'pending' | 'running' | 'done' | 'failed' | 'skipped';
  detail?: string;
  notes?: string[];
}

export interface ImportOptions {
  arrange: boolean;
  analyse: boolean;
}

/**
 * Where a paste goes: a project, as the psalm's translation there (made if it has none),
 * or a new project with this name.
 */
export type ImportTarget =
  | { kind: 'project'; collectionId: string }
  | { kind: 'new-project'; title: string };

export interface ImportRequest {
  text: string;
  psalmId: string;
  target: ImportTarget;
  options: ImportOptions;
}

interface Props {
  open: boolean;
  psalms: PsalmSummary[];
  collections: Collection[];
  /** The project on show, which the import goes into unless another is chosen. */
  collectionId: string | null;
  codex: { ready: boolean; hint?: string; busy: boolean };
  /** Asking Codex which psalm the paste is; the table runs the turn. */
  identify: {
    run: (text: string) => void;
    pending: boolean;
    result: PsalmIdentification | null;
    /** Why identifying failed, readably. */
    error: string | null;
  };
  steps: ImportStep[];
  running: boolean;
  stopping: boolean;
  /** How long the step in flight has been running. */
  elapsed: string | null;
  onRun: (request: ImportRequest) => void;
  onStop: () => void;
  onReset: () => void;
  onClose: () => void;
  onOpen: (pane: 'verses' | ArrangementPane) => void;
}

/** A first look at the paste, before Codex reads it in full. */
function inspect(text: string) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const headings = lines.filter(
    (line) =>
      /^\[[^\]]+\]$/.test(line) ||
      /^(verse|chorus|refrain|bridge|intro|outro|pre-?chorus|tag|stanza|coda)\b[\s\d.:()-]*$/i.test(line),
  ).length;
  const numbered = lines.filter((line) => /^(\(?\d{1,3}[).:]?\s+\S|v\.?\s?\d{1,3}\b)/i.test(line)).length;
  const guidance = lines.filter(
    (line) =>
      /^(meter|metre|tune|key|tempo|time|capo|style|guidance|note|notes|translator'?s? notes?|sing)\s*[:–-]/i.test(
        line,
      ) || /^\d+\/\d+(\s+(time|meter|metre))?$/i.test(line),
  ).length;
  return { lines: lines.length, headings, numbered, guidance };
}

const STATUS_MARK: Record<ImportStep['status'], string> = {
  pending: '○',
  running: '◐',
  done: '✓',
  failed: '!',
  skipped: '–',
};

/** The target select's value for a new project; an existing one is its id. */
const NEW_PROJECT = '__new__';
const FALLBACK_TITLE = 'Imported translation';

/**
 * Paste an existing translation, say which psalm it is (or have Codex say), and where it
 * goes; Codex places it, then it is analysed, step by step.
 */
export function ImportTranslationDialog({
  open,
  psalms,
  collections,
  collectionId,
  codex,
  identify,
  steps,
  running,
  stopping,
  elapsed,
  onRun,
  onStop,
  onReset,
  onClose,
  onOpen,
}: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState('');
  const [arrange, setArrange] = useState(true);
  const [analyse, setAnalyse] = useState(true);
  /** Never assumed from the psalm on screen: identified by Codex or picked. */
  const [psalmId, setPsalmId] = useState('');
  const [target, setTarget] = useState(collectionId ?? NEW_PROJECT);
  const [title, setTitle] = useState('');
  /** Once the reviewer names the new project, Codex's title no longer replaces it. */
  const [titleTouched, setTitleTouched] = useState(false);
  const textId = useId();
  const psalmSelectId = useId();
  const targetId = useId();
  const titleId = useId();
  const seen = useMemo(() => inspect(text), [text]);
  const started = steps.length > 0;
  const failed = steps.some((step) => step.status === 'failed');

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);

  // Opened, it offers the project on show.
  useEffect(() => {
    if (open) setTarget(collectionId ?? NEW_PROJECT);
  }, [open]);

  // Codex's answer fills in the psalm, and the paste's own title for a new project.
  useEffect(() => {
    const found = identify.result;
    if (!found) return;
    if (found.psalm_id) setPsalmId(found.psalm_id);
    if (found.title && !titleTouched) setTitle(found.title);
    // Only a new answer does this, not a later edit of the title.
  }, [identify.result]);

  const blocked = !codex.ready ? codex.hint : codex.busy && !running ? 'Codex is busy with another task.' : undefined;
  const psalmTitle = (id: string) => psalms.find((psalm) => psalm.psalm_id === id)?.title ?? id;
  const found = identify.result;
  /** The psalm's translation already in the chosen project, which the paste then goes into. */
  const held = collections
    .find((c) => c.collection_id === target)
    ?.members.find((m) => m.psalm_id === psalmId);

  function reset() {
    setText('');
    setPsalmId('');
    setTarget(collectionId ?? NEW_PROJECT);
    setTitle('');
    setTitleTouched(false);
    onReset();
  }

  return (
    <dialog
      ref={dialog}
      className="import-dialog"
      aria-labelledby={`${textId}-title`}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <header className="import-dialog__head">
        <h2 id={`${textId}-title`}>
          {started && psalmId ? `Import a translation of ${psalmTitle(psalmId)}` : 'Import a translation'}
        </h2>
        <button type="button" className="btn-sm btn-ghost" aria-label="Close" onClick={onClose}>
          ×
        </button>
      </header>

      {!started ? (
        <form
          className="import-dialog__form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!text.trim() || !psalmId || blocked) return;
            onRun({
              text,
              psalmId,
              target:
                target === NEW_PROJECT
                  ? { kind: 'new-project', title: title.trim() || FALLBACK_TITLE }
                  : { kind: 'project', collectionId: target },
              options: { arrange, analyse },
            });
          }}
        >
          <label htmlFor={textId} className="verse-notes__hint">
            Paste the whole translation. Verse numbers, section headings such as “Chorus”, and notes
            such as “Meter: 6/8” can stay in: Codex places each part and keeps every word as pasted.
          </label>
          <textarea
            id={textId}
            value={text}
            rows={14}
            placeholder={'Meter: 6/8\n\n[Verse 1]\n1 How happy the one who won’t walk…\n\n[Chorus]\n…'}
            onChange={(event) => setText(event.target.value)}
          />
          <p className="import-dialog__seen" aria-live="polite">
            {seen.lines === 0
              ? 'Nothing pasted yet.'
              : `A first look: ${seen.lines} line${seen.lines === 1 ? '' : 's'}` +
                (seen.numbered ? ` · ${seen.numbered} numbered` : '') +
                (seen.headings ? ` · ${seen.headings} section heading${seen.headings === 1 ? '' : 's'}` : '') +
                (seen.guidance ? ` · ${seen.guidance} guidance line${seen.guidance === 1 ? '' : 's'}` : '') +
                '. Codex reads it in full.'}
          </p>
          <fieldset className="import-dialog__psalm">
            <legend>Which psalm is this?</legend>
            <div className="import-dialog__psalm-choice">
              <button
                type="button"
                disabled={!text.trim() || Boolean(blocked) || identify.pending}
                title={blocked}
                onClick={() => identify.run(text)}
              >
                {identify.pending ? 'Identifying…' : 'Identify it with Codex'}
              </button>
              <label htmlFor={psalmSelectId}>or pick it</label>
              <select
                id={psalmSelectId}
                value={psalmId}
                onChange={(event) => setPsalmId(event.target.value)}
              >
                <option value="">Choose a psalm…</option>
                {psalms.map((psalm) => (
                  <option key={psalm.psalm_id} value={psalm.psalm_id}>
                    {psalm.title}
                  </option>
                ))}
              </select>
            </div>
            <div aria-live="polite">
              {identify.error ? <p className="comparison-error">{identify.error}</p> : null}
              {found && !identify.error ? (
                <p className="import-dialog__found">
                  {found.psalm_id
                    ? `Codex reads it as ${psalmTitle(found.psalm_id)} (${found.confidence} confidence). `
                    : 'Codex could not match it to a psalm; pick one above. '}
                  {found.reason}
                  {found.alternatives.length > 0 ? (
                    <span className="import-dialog__alternatives">
                      {' '}
                      It could also be{' '}
                      {found.alternatives.map((id, index) => (
                        <span key={id}>
                          {index > 0 ? ', ' : ''}
                          <button type="button" onClick={() => setPsalmId(id)}>
                            {psalmTitle(id)}
                          </button>
                        </span>
                      ))}
                      .
                    </span>
                  ) : null}
                </p>
              ) : null}
            </div>
          </fieldset>
          <div className="import-dialog__options">
            <label htmlFor={targetId}>
              Import it into
              <select id={targetId} value={target} onChange={(event) => setTarget(event.target.value)}>
                {collections.map((collection) => (
                  <option key={collection.collection_id} value={collection.collection_id}>
                    {collection.title}
                  </option>
                ))}
                <option value={NEW_PROJECT}>A new project</option>
              </select>
            </label>
            {target !== NEW_PROJECT && psalmId ? (
              <span className="verse-notes__hint">
                {held
                  ? `into its translation of ${psalmTitle(psalmId)}`
                  : `as a new translation of ${psalmTitle(psalmId)}`}
              </span>
            ) : null}
            {target === NEW_PROJECT ? (
              <label htmlFor={titleId}>
                named
                <input
                  id={titleId}
                  value={title}
                  placeholder={FALLBACK_TITLE}
                  onChange={(event) => {
                    setTitle(event.target.value);
                    setTitleTouched(true);
                  }}
                />
              </label>
            ) : null}
            <label>
              <input type="checkbox" checked={arrange} onChange={(e) => setArrange(e.target.checked)} />
              Analyse it as a song setting (sections, repeats, liberties)
            </label>
            <label>
              <input type="checkbox" checked={analyse} onChange={(e) => setAnalyse(e.target.checked)} />
              Analyse each verse and the psalm afterwards
            </label>
          </div>
          <p className="verse-notes__hint">
            Guidance found in the paste is added to the translation’s guidance. Each verse is saved
            as a proposal; a verse with reviewed text keeps showing it.
          </p>
          <div className="import-dialog__actions">
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={!text.trim() || !psalmId || Boolean(blocked)}
              title={blocked ?? (psalmId ? undefined : 'Say which psalm this is first')}
            >
              Import
            </button>
          </div>
        </form>
      ) : (
        <div className="import-dialog__progress">
          <ol className="import-steps" aria-live="polite">
            {steps.map((step) => (
              <li key={step.key} className={`import-step is-${step.status}`}>
                <span className="import-step__mark" aria-hidden="true">
                  {STATUS_MARK[step.status]}
                </span>
                <div className="import-step__body">
                  <span className="import-step__label">
                    {step.label}
                    {step.status === 'running' && elapsed ? (
                      <span className="import-step__time"> · {elapsed}</span>
                    ) : null}
                  </span>
                  {step.detail ? <span className="import-step__detail">{step.detail}</span> : null}
                  {step.notes && step.notes.length > 0 ? (
                    <ul className="import-step__notes">
                      {step.notes.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
          <div className="import-dialog__actions">
            {running ? (
              <>
                <span className="verse-notes__hint">
                  You can close this; the import keeps running and the toolbar shows where it is.
                </span>
                <button type="button" disabled={stopping} onClick={onStop}>
                  {stopping ? 'Stopping…' : 'Stop'}
                </button>
                <button type="button" onClick={onClose}>
                  Close
                </button>
              </>
            ) : (
              <>
                <span className="verse-notes__hint">
                  {failed ? 'Finished with problems; see the steps above.' : 'Finished.'}
                </span>
                <button type="button" onClick={() => onOpen('verses')}>
                  Show the verses
                </button>
                {steps.some((s) => s.key === 'arrange' && s.status === 'done') ? (
                  <>
                    <button type="button" onClick={() => onOpen('arrangement')}>
                      Open the song setting
                    </button>
                    <button type="button" onClick={() => onOpen('liberties')}>
                      Review its liberties
                    </button>
                  </>
                ) : null}
                <button type="button" onClick={reset}>
                  Import another
                </button>
                <button type="button" className="btn-primary" onClick={onClose}>
                  Close
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </dialog>
  );
}

export default ImportTranslationDialog;
