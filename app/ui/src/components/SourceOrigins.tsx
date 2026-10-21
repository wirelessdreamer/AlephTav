import { useId, useRef, useState } from 'react';

import type { ArrangementView, ComparisonTableRow } from '../types';
import { BriefingSources } from './BriefingSources';
import { SourceLicenses } from './SourceLicenses';
import './SourceOrigins.css';

/** Saved decisions remain beneath the source-to-song map, without duplicating the song. */
export function SourceOrigins({ view, rows, englishLayer }: {
  view: ArrangementView; rows: ComparisonTableRow[]; englishLayer: string;
}) {
  const choices = view.source_choices ?? [];
  const [selected, setSelected] = useState<string | null>(null);
  const detailId = useId();
  const origin = useRef<HTMLButtonElement | null>(null);
  const active = choices.find(choice => choice.choice_id === selected);
  if (!choices.length) return null;
  function close() { setSelected(null); origin.current?.focus(); }
  return <section className="source-origins" aria-label="Source decisions beneath the flow map"
    onKeyDown={event => { if (event.key === 'Escape' && !(event.target as HTMLElement).closest('.briefing-sources')) { event.stopPropagation(); close(); } }}>
    <details className="source-decision-trail">
      <summary>Decision trail · {choices.length} Greek source choice{choices.length === 1 ? '' : 's'}</summary>
      <div className="source-decision-trail__table"><table>
        <thead><tr><th>Verse</th><th>Saved decision → English phrase</th><th>Source</th><th><span className="sr-only">Compare</span></th></tr></thead>
        <tbody>{choices.map(choice => <tr key={choice.choice_id}>
          <td>{choice.mt_reference}</td><td>{choice.decisions.map(note => note.answer).join(' ') || 'Source choice recorded in the setting’s note.'}<q>{choice.text}</q></td>
          <td><span className="source-origin-badge source-origin-badge--gr">LXX</span>{choice.hebrew_phrases?.length ? <span className="source-origin-badge source-origin-badge--he">+ MT phrases</span> : null}<span className="source-decision-trail__reference">{choice.greek_reference}</span></td>
          <td><button type="button" aria-expanded={selected === choice.choice_id} aria-controls={detailId}
            onClick={event => { origin.current = event.currentTarget; setSelected(selected === choice.choice_id ? null : choice.choice_id); }}
            aria-label={`View source choice for ${choice.mt_reference}`}>View sources</button></td>
        </tr>)}</tbody>
      </table></div>
      <div id={detailId}>
        {active ? <section className="source-origin-detail" aria-label={`Source choice for ${active.mt_reference}`}>
          <header><h4>{active.mt_reference} <span className="source-origin-badge source-origin-badge--gr">Recorded Greek reading · proposed</span></h4>
            <button type="button" onClick={close}>Close source detail</button></header>
          <p className="source-origin-detail__phrase">“{active.text}”</p>
          {active.hebrew_phrases?.length ? <p className="source-origin-detail__note">Hebrew phrase hints retained: {active.hebrew_phrases.map(phrase => `“${phrase.text}”`).join(' · ')}.</p> : null}
          {active.decisions.length ? <div className="source-origin-detail__decisions">
            <h5>Saved briefing decision</h5>
            {active.decisions.map(note => <div key={`${note.briefing_run_id}:${note.question_index}`}>
              <p>{note.answer}</p>{note.notes ? <p className="source-origin-detail__note">{note.notes}</p> : null}
            </div>)}
            <span className="source-origin-detail__scope">Recorded with the verse translation</span>
          </div> : <p className="source-origin-detail__note">This source choice is recorded in the setting’s note; no matching saved briefing answer is attached.</p>}
          <BriefingSources question={{ topic: 'Source choice', verses: [Number(active.unit_id.split('.')[1].slice(1))],
            question: '', background: '', options: [] }} rows={rows} greek={view.greek_sources} englishLayer={englishLayer} />
          <details className="source-origin-detail__record"><summary>Recorded source note</summary><p>{active.rationale}</p></details>
          <div className="source-origin-detail__scope">{active.greek_reference} · {active.edition_id} {active.text_revision_id} · Proposed source choice</div>
        </section> : null}
      </div>
    </details>
    <SourceLicenses sources={view.greek_sources} />
  </section>;
}
