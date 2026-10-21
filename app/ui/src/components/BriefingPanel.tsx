import { Fragment, useEffect, useId, useState } from 'react';
import { useBriefingDecisions } from '../hooks/useBriefingDecisions';

import type { BriefingGreekSources, BriefingQuestion, ComparisonTableRow, PsalmBriefing, TranslationContextEvent } from '../types';
import { BriefingSources } from './BriefingSources';
import { SourceLicenses } from './SourceLicenses';
import { TranslationContextHistory } from './TranslationContextHistory';

interface Props {
  psalmId: string | null;
  translationId: string | null;
  beforeAction: React.MutableRefObject<(() => Promise<boolean>) | null>;
  briefing: PsalmBriefing | null | undefined;
  /** The guidance saved now, to tell whether the briefing was made under it. */
  savedGuidance: string;
  codex: { ready: boolean; hint?: string; busy: boolean };
  onPrepare: () => void;
  rows: ComparisonTableRow[];
  greekSources?: BriefingGreekSources;
  sourcesLoading?: boolean;
  history: TranslationContextEvent[];
  englishLayer: string;
}

/** One of the options, or the translator's own words. */
type Answer = { option: number } | { own: string };

const BACKGROUND: Array<[keyof PsalmBriefing['background'], string]> = [
  ['authorship', 'Authorship'],
  ['setting', 'Setting'],
  ['form', 'Form'],
  ['themes', 'Themes'],
  ['reception', 'Reception'],
];

const LINK = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;

/** Codex cites its sources as Markdown links; show them as links. */
function withLinks(text: string) {
  return text.split(LINK).map((part, index, parts) => {
    // With two groups, split() yields text, label, url, text, label, url, ...
    if (index % 3 === 1) {
      return (
        <a key={index} href={parts[index + 1]} target="_blank" rel="noreferrer">
          {part}
        </a>
      );
    }
    return index % 3 === 2 ? null : part;
  });
}

function where(question: BriefingQuestion): string {
  const { verses } = question;
  if (verses.length === 0) return '';
  return ` (${verses.length === 1 ? 'v.' : 'vv.'} ${verses.join(', ')})`;
}

/**
 * Background on the psalm and the decisions it leaves to the translator, read before
 * translating. Saved answers and notes directly instruct the translation.
 */
export function BriefingPanel({
  psalmId, translationId, beforeAction,
  briefing,
  savedGuidance,
  codex,
  onPrepare,
  rows, greekSources, sourcesLoading = false, history, englishLayer,
}: Props) {
  const recorded = useBriefingDecisions(psalmId, translationId, briefing, history);
  const inferences = [...history].reverse().find(event =>
    event.inferences?.briefing_run_id === briefing?.run_id)?.inferences;
  useEffect(() => { beforeAction.current = recorded.flush; }, [beforeAction, recorded.flush]);
  const [ownAnswers, setOwnAnswers] = useState<Record<number, boolean>>({});
  const answers: Record<number, Answer> = {};
  const notes: Record<number, string> = {};
  for (const note of Object.values(recorded.decisions)) {
    const question = briefing?.questions[note.question_index];
    const option = question?.options.findIndex(item => item.choice === note.answer) ?? -1;
    if (note.answer || ownAnswers[note.question_index]) answers[note.question_index] =
      option >= 0 && !ownAnswers[note.question_index] ? { option } : { own: note.answer };
    notes[note.question_index] = note.notes;
  }
  const [collapsed, setCollapsed] = useState(false);
  const bodyId = useId();
  useEffect(() => { setCollapsed(false); }, [briefing?.run_id]);

  function answer(index: number, value: Answer | null) {
    setOwnAnswers(previous => ({ ...previous, [index]: Boolean(value && 'own' in value) }));
    recorded.update(index, { answer: value ? ('option' in value
      ? briefing!.questions[index].options[value.option].choice : value.own) : '' });
  }

  return (
    <section className="guidance-panel briefing-panel" aria-label="Translator's briefing">
      <div className="briefing-panel__head">
        <div className="briefing-panel__intro">
          <h3><button type="button" className="briefing-panel__toggle" aria-expanded={!collapsed}
            aria-controls={bodyId} onClick={() => setCollapsed(value => !value)}>
            <span aria-hidden="true">{collapsed ? '▸' : '▾'}</span>
            {briefing ? "Translator's briefing" : 'Start with a briefing'}
          </button></h3>
          <p>
            Explore the psalm's background and key translation choices with Codex. Answer the
            questions you want to settle. Saved answers and notes automatically guide translation.
          </p>
          {briefing && sourcesLoading ? <p role="status">Loading Greek reading context… Your saved answers are ready.</p> : null}
          {briefing ? <p className="briefing-saved-summary">
            {Object.values(recorded.decisions).filter(note => note.answer.trim()).length} of {briefing.questions.length} questions answered
            {' · '}{recorded.error ? 'Unsaved edits' : recorded.pending ? 'Saving…' : 'Saved'}
          </p> : null}
          {greekSources?.preview && !greekSources.generation_available ? <p className="briefing-source-limit">
            Greek readings are available for study. Generation from Greek is not enabled yet;
            Greek-dependent choices remain saved until that support is available.
          </p> : null}
        </div>
        <button
          type="button"
          className="btn-primary briefing-panel__prepare"
          disabled={!codex.ready || codex.busy}
          title={codex.hint}
          onClick={onPrepare}
        >
          {briefing ? 'Prepare again' : 'Prepare briefing'}
          <span aria-hidden="true">→</span>
        </button>
      </div>

      <div id={bodyId} hidden={collapsed} className="briefing-panel__body">
      {!briefing ? null : (
        <>
          {briefing.guidance !== savedGuidance ? (
            <p className="subtle-note">
              The guidance has changed since this briefing was prepared. Prepare it again to see
              only the questions still open.
            </p>
          ) : null}

          <h4>Background</h4>
          <dl className="analysis-defs">
            {BACKGROUND.map(([key, label]) => (
              <Fragment key={key}>
                <dt>{label}</dt>
                <dd>{withLinks(briefing.background[key])}</dd>
              </Fragment>
            ))}
          </dl>

          <h4>Questions for you</h4>
          <ol className="briefing-questions">
            {briefing.questions.map((question, index) => {
              const current = answers[index];
              const name = `briefing-${briefing.run_id}-${index}`;
              const inferred = inferences?.items.find(item => item.question_index === index);
              return (
                <li key={name}>
                  <fieldset>
                    <legend>
                      <strong>{question.topic}</strong>
                      {where(question)}
                    </legend>
                    <p className="briefing-question">{question.question}</p>
                    <p className="basis">{withLinks(question.background)}</p>
                    {inferred ? <details className="briefing-inference">
                      <summary>Inferred from existing translation · {inferred.confidence}</summary>
                      <p>{inferred.answer ?? 'The existing wording does not settle this question.'}</p>
                      <p>{inferred.evidence}</p><p>{inferred.rationale}</p>
                      <p>This is a suggestion from the wording, not a recovered original answer.</p>
                      {inferred.answer ? <button type="button" onClick={() => {
                        recorded.update(index, { answer: inferred.answer!, notes: [notes[index],
                          `Adopted inference from existing translation (${inferred.confidence} confidence). ${inferred.evidence}`,
                        ].filter(Boolean).join('\n') });
                      }}>Use this inferred answer</button> : null}
                    </details> : null}
                    <BriefingSources question={question} rows={rows} greek={greekSources} englishLayer={englishLayer} />
                    {question.options.map((option, choice) => (
                      <label key={option.choice} className="briefing-option">
                        <input
                          type="radio"
                          name={name}
                          checked={
                            current !== undefined && 'option' in current && current.option === choice
                          }
                          onChange={() => answer(index, { option: choice })}
                        />
                        <span>
                          {option.choice}
                          <span className="basis">
                            {withLinks(option.held_by)} · {withLinks(option.effect)}
                          </span>
                        </span>
                      </label>
                    ))}
                    <label className="briefing-option">
                      <input
                        type="radio"
                        name={name}
                        checked={current !== undefined && 'own' in current}
                        onChange={() => answer(index, { own: '' })}
                      />
                      <input
                        type="text"
                        aria-label={`Your own answer: ${question.topic}`}
                        placeholder="Your own answer"
                        value={current && 'own' in current ? current.own : ''}
                        onChange={(event) => answer(index, { own: event.target.value })}
                      />
                    </label>
                    {current ? (
                      <button
                        type="button"
                        className="btn-sm btn-ghost"
                        onClick={() => answer(index, null)}
                      >
                        Leave open
                      </button>
                    ) : null}
                    <label className="briefing-question-notes">
                      Notes on this question
                      <textarea rows={2} value={notes[index] ?? ''}
                        aria-label={`Notes: ${question.topic}`}
                        onChange={event => recorded.update(index, { notes: event.target.value })} />
                    </label>
                  </fieldset>
                </li>
              );
            })}
          </ol>

          <div role="status" className="briefing-save-status">
            {recorded.error ? <>Could not save to history. Your edits are kept on this device.
              <button type="button" onClick={recorded.retry}>Retry saving decisions</button>
              <span className="basis">{recorded.error}</span>
            </> : recorded.pending ? 'Saving briefing decisions…'
              : Object.values(recorded.decisions).some(note => note.answer.trim() || note.notes.trim())
                ? 'Briefing decisions saved.' : 'No briefing decisions selected yet. Answers and notes save automatically.'}
          </div>
        </>
      )}
      <TranslationContextHistory events={history} />
      {briefing ? <SourceLicenses sources={greekSources} /> : null}
      </div>
    </section>
  );
}

export default BriefingPanel;
