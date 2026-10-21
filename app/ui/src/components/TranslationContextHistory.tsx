import type { TranslationContextEvent } from '../types';
import { shortTime } from './verseActions';

export function TranslationContextDetails({ event }: { event: TranslationContextEvent }) {
  return <div className="translation-context-details">
    {event.previous_guidance !== undefined ? <details>
      <summary>Previous guidance</summary><p className="note-prose">{event.previous_guidance || '(none)'}</p>
    </details> : null}
    <p className="note-prose"><strong>Guidance at this step</strong>{'\n'}{event.guidance || '(none)'}</p>
    {event.inferences ? <>
      <p>Suggestions inferred from the existing translation, not recovered user answers.
        They guide translation only after you choose to use them.</p>
      <ol>{event.inferences.items.map(item => <li key={item.question_index}>
        <strong>{item.topic} · {item.confidence}</strong>
        <p>{item.answer ?? 'Unresolved'}</p><p>{item.evidence}</p><p>{item.rationale}</p>
      </li>)}</ol>
    </> : null}
    {event.annotations?.length ? <h5>Recorded briefing decisions and notes</h5> : null}
    {event.annotations?.map((note, index) => <div key={index}>
      <strong>{note.question?.topic}</strong>
      <p>{note.question?.question}</p>
      {note.answer ? <p className="note-prose">Decision: {note.answer}</p> : null}
      {note.notes ? <p className="note-prose">Notes: {note.notes}</p> : null}
      <span className="basis">Briefing {note.briefing_run_id} · question {note.question_index + 1}</span>
    </div>)}
    {event.briefing ? <details>
      <summary>Full briefing at this step · {shortTime(event.briefing.created_at ?? event.created_at)}</summary>
      <dl>{Object.entries(event.briefing.background).map(([label, text]) => <div key={label}>
        <dt>{label}</dt><dd>{text}</dd>
      </div>)}</dl>
      <ol>{event.briefing.questions.map((question, index) => <li key={index}>
        <strong>{question.topic}</strong><p>{question.question}</p><p>{question.background}</p>
        <ul>{question.options.map(option => <li key={option.choice}>
          {option.choice} · {option.held_by} · {option.effect}
        </li>)}</ul>
      </li>)}</ol>
    </details> : null}
  </div>;
}

export function TranslationContextHistory({ events }: { events: TranslationContextEvent[] }) {
  return <details className="translation-context-history">
    <summary>Briefing &amp; guidance history ({events.length})</summary>
    {events.length === 0 ? <p>Prepared briefings and saved guidance, decisions, and notes will appear here.</p> : null}
    <ol>{[...events].reverse().map(event => <li key={event.audit_id}>
      <details><summary>{shortTime(event.created_at)} · {event.summary} · {event.created_by}</summary>
        <TranslationContextDetails event={event} />
        <span className="basis">{event.audit_id}</span>
      </details>
    </li>)}</ol>
  </details>;
}
