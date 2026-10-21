import { Fragment, useState } from 'react';

import { studyUrl, useGreekStudy, type WordCard } from '../hooks/useGreekStudy';
import { useWordCardPosition } from '../hooks/useWordCardPosition';
import type { BriefingGreekSources, BriefingQuestion, ComparisonTableRow } from '../types';
import { GreekPreviewWordDetails, sourceParts } from './ArrangementGreekSource';
import { WordContextCard, placeCard, type HoveredWord } from './WordContextCard';

function GreekTooltip({ hovered, sources }: {
  hovered: HoveredWord; sources: BriefingGreekSources;
}) {
  const position = useWordCardPosition<HTMLDivElement>(hovered);
  const unit = Object.values(sources.by_mt_unit).flatMap(mapping => mapping.units)
    .find(candidate => candidate.tokens.some(token => token.token_id === hovered.tokenId));
  const token = unit?.tokens.find(candidate => candidate.token_id === hovered.tokenId);
  return <div ref={position.ref} role="tooltip" className="occurrence-card briefing-greek-tooltip"
    style={position.style}>
    {sources.study_snapshot_id && sources.policy_revision_id
      ? <GreekStudyTooltip hovered={hovered} sources={sources} />
      : token && unit ? <GreekPreviewWordDetails token={token} reference={unit.ref} sources={sources} /> : null}
  </div>;
}

function GreekStudyTooltip({ hovered, sources }: {
  hovered: HoveredWord; sources: BriefingGreekSources;
}) {
  const card = useGreekStudy<WordCard>(studyUrl(
    `/greek/tokens/${encodeURIComponent(hovered.tokenId)}/card`, {
      study_snapshot_id: sources.study_snapshot_id, policy_revision_id: sources.policy_revision_id,
    },
  ), sources.study_snapshot_id ?? '');
  return <>
    {card.loading ? <p>Loading Greek word…</p> : null}
    {card.error ? <p>{card.error}</p> : null}
    {card.data ? <>
      <strong lang="grc">{card.data.token.surface}</strong>
      {card.data.analyses.length === 0 ? <p>Lexical analysis unresolved.</p> : null}
      {card.data.analyses.map(item => <div key={item.analysis_id}>
        <p><span lang="grc">{item.lemma}</span> · {item.status}</p>
        <p>{item.scheme} {item.raw_tag}</p>
        <p>{Object.entries(item.features ?? {}).map(([key, value]) => `${key}: ${value}`).join(' · ')}</p>
        <p>{item.identifiers?.map(id => `${id.scheme}: ${id.value}`).join(' · ')}</p>
      </div>)}
      {card.data.dictionary_entries.map(entry => <div key={entry.entry_id}>
        <p><span lang="grc">{entry.headword}</span> · {entry.gloss || 'No dictionary gloss recorded.'}</p>
      </div>)}
      <p>{card.data.counts.total_matches} source occurrences</p>
    </> : null}
  </>;
}

/** Actual MT verses and edition-mapped Greek, with the same Hebrew word context card. */
export function BriefingSources({ question, rows, greek, englishLayer }: {
  question: BriefingQuestion; rows: ComparisonTableRow[];
  greek: BriefingGreekSources | undefined; englishLayer: string;
}) {
  const [hovered, setHovered] = useState<(HoveredWord & { language: 'he' | 'grc' }) | null>(null);
  const relevant = question.verses.length === 0 ? rows : rows.filter(row => row.unit_ids.some(
    id => question.verses.includes(Number(id.split('.')[1]?.slice(1))),
  ));
  const hoveredRow = rows.find(row => row.tokens.some(token => token.token_id === hovered?.tokenId));
  function wordHover(tokenId: string, language: 'he' | 'grc') {
    return {
      tabIndex: 0,
      onMouseEnter: (event: React.MouseEvent<HTMLElement>) => setHovered({ ...placeCard(tokenId, event.currentTarget), language }),
      onFocus: (event: React.FocusEvent<HTMLElement>) => setHovered({ ...placeCard(tokenId, event.currentTarget), language }),
      onMouseLeave: () => setHovered(null), onBlur: () => setHovered(null),
      onKeyDown: (event: React.KeyboardEvent) => { if (event.key === 'Escape') setHovered(null); },
    };
  }
  return <details className="briefing-sources" open={question.verses.length > 0}
    onToggle={() => setHovered(null)}>
    <summary>Hebrew, Greek &amp; literal readings · {relevant.length} verse{relevant.length === 1 ? '' : 's'}</summary>
    {relevant.length === 0 ? <p>No source verses available for these references.</p> : null}
    {relevant.map(row => <section key={row.unit_ids.join(',')} className="briefing-source-verse"
      aria-label={`Sources for ${row.display_reference}`}>
      <h5>{row.display_reference}</h5>
      <div className="briefing-source-pair">
        <div>
          <h6>Hebrew (MT)</h6>
          <p className="briefing-source-words" lang="he" dir="rtl">
            {row.tokens.length === 0 ? row.hebrew_text : row.tokens.map(token => <span key={token.token_id} className="arr-lib__word"
              {...wordHover(token.token_id, 'he')}>{token.surface}{' '}</span>)}
          </p>
          <p className="briefing-hebrew-literal"><span className="verse-label">{row.literal_text ? 'Literal ' : 'Word-by-word literal '}</span>
            {row.literal_text || (row.tokens.some(token => token.display_gloss || token.gloss_parts?.length)
              ? row.tokens.map(token => token.display_gloss || token.gloss_parts?.join(' / ') || '?').join(' · ')
              : 'No Hebrew word meanings or literal translation recorded.')}
          </p>
        </div>
        <div>
          <h6>Greek (LXX){greek?.edition_id ? ` · ${greek.edition_id} ${greek.text_revision_id}` : ''}{greek?.preview ? ' · unreviewed preview' : ''}</h6>
          {!greek?.available ? <p>{greek?.message ?? 'Loading Greek source availability…'}</p> : null}
          {greek?.lexical_message ? <p>{greek.lexical_message}</p> : null}
          {greek?.available && row.unit_ids.every(id => !greek.by_mt_unit[id]) ?
            <p>No {greek.preview ? 'proposed' : 'reviewed'} Greek correspondence recorded for this Hebrew verse.</p> : null}
          {row.unit_ids.map(id => greek?.by_mt_unit[id] ? <div key={id}>
            {greek.by_mt_unit[id].units.length === 0 ? <p>Mapping: {greek.by_mt_unit[id].relations.join(', ')}. No corresponding Greek text.</p> : null}
            {greek.by_mt_unit[id].units.map(unit => {
              const parts = sourceParts(unit);
              return <div key={unit.unit_id}>
              <span className="verse-label">{unit.ref}{unit.partial ? ' · partial correspondence; full Greek verse shown' : ''}</span>
              <p className="briefing-source-words" lang="grc" dir="ltr">
                {parts ? <>{parts.parts.map(({ before, token }) => <Fragment key={token.token_id}>{before}<span className="arr-lib__word"
                  {...wordHover(token.token_id, 'grc')}>{token.surface}</span></Fragment>)}{parts.after}</> : unit.source_greek}
              </p>
              {unit.tokens.some(token => token.gloss) ? <>
                <p className="briefing-greek-literal"><span className="verse-label">Word-by-word literal aid </span>{unit.literal_text}</p>
              </> : <p className="briefing-greek-literal"><span className="verse-label">Literal </span>Greek word meanings are not loaded for this source; no literal translation recorded.</p>}
            </div>;
            })}
          </div> : null)}
        </div>
      </div>
    </section>)}
    {hovered?.language === 'he' && hoveredRow ? <WordContextCard hovered={hovered}
      row={hoveredRow} sections={[]} sung={[]} englishLayer={englishLayer} showSetting={false} /> : null}
    {hovered?.language === 'grc' && greek?.available ? <GreekTooltip hovered={hovered} sources={greek} /> : null}
  </details>;
}
