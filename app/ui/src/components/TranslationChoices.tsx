import { useId, useRef, useState, type FormEvent, type MouseEvent } from 'react';

import { TranslationChoiceError, useTranslationChoices } from '../hooks/useTranslationChoices';
import type { IntentionalTranslationChoice, TranslationChoice, TranslationChoiceTarget } from '../types';
import { RequestStatus } from './RequestStatus';
import { layerLabel } from './verseActions';

const contextLabel = (status: TranslationChoice['context_status']) => status === 'provided_by_translator'
  ? 'Context supplied by translator' : 'Supporting context not established';
const targetKey = (target: Pick<TranslationChoiceTarget, 'kind' | 'id' | 'arrangement_id'>) =>
  JSON.stringify([target.kind, target.arrangement_id ?? null, target.id]);
const fieldStyle = { boxSizing: 'border-box' as const };
const captureTarget = (target: TranslationChoiceTarget): TranslationChoiceTarget =>
  ({ ...target, revision: { ...target.revision } });

/** Move within the page without replacing the workbench's hash-router location. */
export function followContextFootnote(event: MouseEvent<HTMLAnchorElement>, targetId: string) {
  event.preventDefault();
  const target = event.currentTarget.ownerDocument.getElementById(targetId);
  target?.focus();
  target?.scrollIntoView({ block: 'nearest' });
}

/** Reused in briefing history; a recorded explanation does not establish source authority. */
export function TranslationChoiceDetails({ choice, targetState, supersededBy }: {
  choice: TranslationChoice;
  targetState?: IntentionalTranslationChoice['target_state'];
  supersededBy?: string | null;
}) {
  const scope = useId();
  const noteId = `${scope}-context-footnote`;
  return <div className="translation-context-details">
    <p className="note-prose"><strong>Intentional choice</strong>{'\n'}{choice.decision}</p>
    <p className="note-prose"><strong>Reason recorded</strong>{'\n'}{choice.rationale}</p>
    <p><strong>{contextLabel(choice.context_status)}</strong></p>
    {choice.context_status === 'provided_by_translator' ?
      <p className="verse-notes__hint">This records supplied context; it does not verify a source claim.</p> : null}
    <ul>{choice.targets.map((target, index) => <li key={targetKey(target)}>
      <span>{layerLabel(target.layer)} · {target.id}</span>
      <p className="note-prose">{target.text}{choice.context_note ? <sup><a
        id={`${scope}-context-reference-${index}`} href={`#${noteId}`}
        aria-label={`Context footnote 1 for ${target.id}`}
        onClick={event => followContextFootnote(event, noteId)}>[1]</a></sup> : null}</p>
      {target.context_text ? <details><summary>Context captured with this target</summary>
        <p className="note-prose">{target.context_text}</p></details> : null}
    </li>)}</ul>
    {choice.context_note ? <ol aria-label="Recorded context footnotes"><li id={noteId} tabIndex={-1}>
      <strong>Recorded context footnote</strong>
      <p className="note-prose">{choice.context_note}</p>
      {choice.targets.map((target, index) => <span key={targetKey(target)}>{index > 0 ? ' · ' : ''}<a
        href={`#${scope}-context-reference-${index}`} aria-label={`Back to ${target.id}`}
        onClick={event => followContextFootnote(event, `${scope}-context-reference-${index}`)}>
        Back to {target.id}</a></span>)}
    </li></ol> : null}
    {targetState ? <p className="basis">{targetState === 'current' ? 'Recorded targets are current.' :
      targetState === 'changed' ? 'Target text or context has changed since this record.' :
        'A recorded target is no longer available.'}</p> : null}
    {choice.supersedes_audit_id ? <p className="basis">Corrects record {choice.supersedes_audit_id}</p> : null}
    {supersededBy ? <p className="basis">Correction recorded as {supersededBy}</p> : null}
    <p className="verse-notes__hint">This explanation does not count as review or publication approval.</p>
  </div>;
}

interface Props {
  psalmId: string;
  translationId: string | null;
  unitId?: string;
  arrangementId?: string;
}

/** A scope change remounts the form so drafts cannot move to another translation. */
export function TranslationChoices(props: Props) {
  return <ChoicePanel key={JSON.stringify([props.psalmId, props.translationId, props.unitId, props.arrangementId])}
    {...props} />;
}

function ChoicePanel({ psalmId, translationId, unitId, arrangementId }: Props) {
  const { query, save } = useTranslationChoices(psalmId, translationId, { unitId, arrangementId });
  // Selection binds the draft to the version the recorder explicitly saw/chose.
  const [selected, setSelected] = useState<TranslationChoiceTarget[]>([]);
  const [decision, setDecision] = useState('');
  const [rationale, setRationale] = useState('');
  const [contextStatus, setContextStatus] = useState<TranslationChoice['context_status']>('not_established');
  const [contextNote, setContextNote] = useState('');
  const [recorder, setRecorder] = useState('');
  const [supersedes, setSupersedes] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const submitting = useRef(false);
  const targets = query.data?.targets ?? [];
  const choices = query.data?.choices ?? [];
  const currentTarget = (selectedTarget: TranslationChoiceTarget) =>
    targets.find(target => targetKey(target) === targetKey(selectedTarget));
  const missing = selected.some(target => !currentTarget(target));
  const changed = selected.filter(target => {
    const current = currentTarget(target);
    return current && current.revision.value !== target.revision.value;
  });
  const stale = error instanceof TranslationChoiceError && (error.status === 409 ||
    /target changed|already has a correction/i.test(error.message));

  const correct = (entry: IntentionalTranslationChoice) => {
    setDecision(entry.choice.decision);
    setRationale(entry.choice.rationale);
    setContextStatus(entry.choice.context_status);
    setContextNote(entry.choice.context_note);
    setSelected(entry.choice.targets.flatMap(target => {
      const current = currentTarget(target);
      return current ? [captureTarget(current)] : [];
    }));
    setSupersedes(entry.audit_id);
    setError(null);
    setSaved(false);
  };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting.current || !selected.length || missing || changed.length || stale) return;
    submitting.current = true;
    setError(null);
    setSaved(false);
    try {
      await save.mutateAsync({ translation_id: translationId,
        targets: selected.map(target => ({ kind: target.kind, id: target.id,
          ...(target.arrangement_id ? { arrangement_id: target.arrangement_id } : {}),
          expected_revision: target.revision.value })),
        decision, rationale, context_status: contextStatus, context_note: contextNote,
        created_by: recorder, supersedes_audit_id: supersedes });
      setSelected([]);
      setDecision('');
      setRationale('');
      setContextStatus('not_established');
      setContextNote('');
      setSupersedes(null);
      setSaved(true);
    } catch (failure) {
      setError(failure);
    } finally {
      submitting.current = false;
    }
  };

  return <details className="translation-context-history">
    <summary>Intentional translation choices ({choices.length})</summary>
    <p>Record a deliberate wording choice and what is known about its supporting context.
      The record date is when this explanation is saved, not the original decision date.</p>
    <RequestStatus loading={query.isLoading} error={query.error}
      label={query.isLoading ? 'Loading translation choices…' : 'Could not load translation choices.'}
      onRetry={() => void query.refetch()} />
    {query.data ? <>
      <form onSubmit={event => void submit(event)} aria-label="Record intentional translation choice">
        <fieldset disabled={save.isPending} style={{ minWidth: 0 }}>
          <legend>{supersedes ? `Append correction to ${supersedes}` : 'Record a choice'}</legend>
          <fieldset style={{ minWidth: 0 }}><legend>Selected wording (choose 1–20)</legend>
            <div style={{ maxHeight: '20rem', overflowY: 'auto' }}>
            {targets.length === 0 ? <p>No current targets in this view.</p> : null}
            {targets.map(target => <p key={targetKey(target)}><label className="checkbox-field">
              <input type="checkbox" checked={selected.some(item => targetKey(item) === targetKey(target))}
                disabled={selected.length >= 20 && !selected.some(item => targetKey(item) === targetKey(target))}
                onChange={event => setSelected(old => event.target.checked ? [...old, captureTarget(target)] :
                  old.filter(item => targetKey(item) !== targetKey(target)))} />{' '}
              {layerLabel(target.layer)} · {target.id}: {target.text}
            </label></p>)}</div>
          </fieldset>
          {missing ? <div role="alert"><p>A selected target is missing. Refresh targets or clear the selection before continuing.</p>
            <button type="button" onClick={() => setSelected([])}>Clear selection</button></div> : null}
          {changed.length ? <div role="alert">
            <p>Selected wording or its context has changed. Check both versions before using the current wording for this choice.</p>
            <ul>{changed.map(target => {
              const current = currentTarget(target)!;
              return <li key={targetKey(target)}><strong>{target.id}</strong>
                <p className="note-prose">Selected: {target.text}</p>
                <p className="note-prose">Current: {current.text}</p>
                <details><summary>Compare the selected and current context</summary>
                  <p className="note-prose">Selected context: {target.context_text}</p>
                  <p className="note-prose">Current context: {current.context_text}</p>
                </details></li>;
            })}</ul>
            <button type="button" disabled={missing || query.isFetching} onClick={() => {
              setSelected(old => old.flatMap(target => {
                const current = currentTarget(target);
                return current ? [captureTarget(current)] : [];
              }));
              setError(null);
            }}>Use current wording for selected targets</button>
          </div> : null}
          <p><label>Intentional choice<br /><textarea required style={fieldStyle} maxLength={2000} value={decision}
            onChange={event => setDecision(event.target.value)} /></label></p>
          <p><label>Reason for this choice<br /><textarea required style={fieldStyle} maxLength={8000} value={rationale}
            onChange={event => setRationale(event.target.value)} /></label></p>
          <p className="verse-notes__hint">If the original reason is unknown, say “Original reason was not recorded.”</p>
          <p><label>Supporting context<br /><select style={fieldStyle} value={contextStatus}
            onChange={event => setContextStatus(event.target.value as TranslationChoice['context_status'])}>
            <option value="not_established">Supporting context not established</option>
            <option value="provided_by_translator">Context supplied by translator</option>
          </select></label></p>
          <p><label>Context note<br /><textarea required style={fieldStyle} maxLength={4000} value={contextNote}
            onChange={event => setContextNote(event.target.value)} /></label></p>
          {contextStatus === 'not_established' ?
            <p className="verse-notes__hint">State what supporting context remains unknown.</p> : null}
          <p><label>Recorded by<br /><input required style={fieldStyle} maxLength={200} value={recorder}
            onChange={event => setRecorder(event.target.value)} /></label></p>
          <button type="submit" disabled={!selected.length || missing || changed.length > 0 ||
            !decision.trim() || !rationale.trim() || !recorder.trim() ||
            !contextNote.trim() || stale || query.isFetching}>
            {save.isPending ? 'Saving choice…' : supersedes ? 'Append correction' : 'Record choice'}
          </button>{' '}
          {supersedes ? <button type="button" onClick={() => { setSupersedes(null); setError(null); }}>
            Record as a new choice instead</button> : null}
        </fieldset>
      </form>
      {error ? <div role="alert">
        <p>{stale ? 'The target or record has changed. Refresh targets, check the wording, and save again.' :
          `Could not save this choice. ${error instanceof Error ? error.message : String(error)}`}</p>
      </div> : null}
      <button type="button" disabled={save.isPending || query.isFetching} onClick={() => {
        void query.refetch().then(result => { if (!result.error) setError(null); });
      }}>Refresh targets</button>
      {saved ? <p role="status">Choice recorded.</p> : null}
      <ol>{[...choices].reverse().map(entry => <li key={entry.audit_id}>
        <details><summary>Recorded {entry.created_at} · {entry.created_by} · {entry.choice.decision}</summary>
          <TranslationChoiceDetails choice={entry.choice} targetState={entry.target_state}
            supersededBy={entry.superseded_by_audit_id} />
          <span className="basis">{entry.audit_id}</span>
          {!entry.superseded_by_audit_id ? <p><button type="button" disabled={save.isPending || query.isFetching ||
            entry.choice.targets.some(old => !targets.some(current => targetKey(current) === targetKey(old)))}
            title="A correction uses the current versions of all recorded targets."
            onClick={() => correct(entry)}>Append a correction</button></p> : null}
        </details>
      </li>)}</ol>
    </> : null}
  </details>;
}
