import { Fragment, useEffect, useRef, useState } from 'react';

import { studyUrl, useGreekStudy, type WordCard } from '../hooks/useGreekStudy';
import { useWordCardPosition } from '../hooks/useWordCardPosition';
import { useWordStudyDismissal } from '../hooks/useWordStudyDismissal';
import type { BriefingGreekSources } from '../types';
import { placeCard, type HoveredWord } from './WordContextCard';

type GreekUnit = BriefingGreekSources['by_mt_unit'][string]['units'][number];
type Word = HoveredWord & { pinned: boolean };

export function GreekPreviewWordDetails({ token, reference, sources }: {
  token: GreekUnit['tokens'][number]; reference: string; sources: BriefingGreekSources;
}) {
  return <>
    <strong lang="grc">{token.surface}</strong>
    <p>{reference} · {sources.edition_id} {sources.text_revision_id}</p>
    {token.lookup_status === 'possible_variant' ? <p>Possible reading — source review needed.</p> : null}
    {token.lookup_status === 'related_entry' ? <p>Related-word context — exact entry unresolved.</p> : null}
    {token.lookup_status === 'mark_variant' ? <p>Possible accent or breathing variant — needs review.</p> : null}
    <p>{token.gloss || (sources.lexical_preview
      ? token.analyses?.length ? 'A lemma was found, but no matching dictionary meaning was found.'
        : 'No matching dictionary entry was found for this word form.'
      : 'No Greek word meaning is loaded for this source.')}</p>
    {token.analyses?.map((item, index) => <div key={index}>
      <p><span lang="grc">{item.lemma}</span> · {item.status}</p>
      <p>{item.scheme} {item.raw_tag}</p>
      {item.lookup_note ? <p>{item.lookup_note}</p> : null}
      <p>{Object.entries(item.features).filter(([, value]) => value)
        .map(([key, value]) => `${key.replace(/_/g, ' ')}: ${value}`).join(' · ')}</p>
    </div>)}
    {token.dictionary_entries?.map(entry => <div key={entry.entry_id}>
      <p><span lang="grc">{entry.headword}</span> · {entry.gloss}</p>
    </div>)}
  </>;
}

function GreekWordStudy({ word, sources, onClose, onCloseOutside }: {
  word: Word; sources: BriefingGreekSources; onClose: () => void; onCloseOutside: () => void;
}) {
  const close = useRef<HTMLButtonElement>(null);
  const position = useWordCardPosition<HTMLElement>(word);
  useWordStudyDismissal(position.ref, word.pinned, onCloseOutside);
  const localUnit = Object.values(sources.by_mt_unit).flatMap(mapping => mapping.units)
    .find(unit => unit.tokens.some(token => token.token_id === word.tokenId));
  const localToken = localUnit?.tokens.find(token => token.token_id === word.tokenId);
  const result = useGreekStudy<WordCard>(sources.preview ? null : studyUrl(`/greek/tokens/${encodeURIComponent(word.tokenId)}/card`, {
    study_snapshot_id: sources.study_snapshot_id, policy_revision_id: sources.policy_revision_id,
  }), `${sources.study_snapshot_id}|${sources.policy_revision_id}`);
  useEffect(() => { if (word.pinned) close.current?.focus(); }, [word.pinned]);
  return <aside ref={position.ref} className="occurrence-card arr-source-word-card"
    role={word.pinned ? 'dialog' : 'tooltip'} aria-label="Greek word study"
    style={position.style}
    onClick={(event) => event.stopPropagation()} onKeyDown={(event) => {
      if (event.key === 'Escape') { event.stopPropagation(); onClose(); }
    }}>
    {word.pinned ? <button type="button" ref={close} onClick={onClose}>Close Greek word study</button> : null}
    {sources.preview && localToken && localUnit ? <GreekPreviewWordDetails
      token={localToken} reference={localUnit.ref} sources={sources} /> : null}
    {result.loading ? <p role="status">Loading Greek word…</p> : null}
    {result.error ? <p role="alert">{result.error}</p> : null}
    {result.data ? <>
      <strong lang="grc" dir="ltr">{result.data.token.surface}</strong>
      {result.data.analyses.length === 0 ? <p>Lexical analysis unresolved.</p> : null}
      {result.data.analyses.map(analysis => <div key={analysis.analysis_id}>
        <p><span lang="grc" dir="ltr">{analysis.lemma ?? 'Unresolved lemma'}</span> · {analysis.status}</p>
        <p>{analysis.scheme} {analysis.raw_tag}</p>
        <p>{Object.entries(analysis.features ?? {}).map(([key, value]) => `${key}: ${value}`).join(' · ')}</p>
        <p>{analysis.identifiers?.map(id => `${id.scheme}: ${id.value}`).join(' · ')}</p>
      </div>)}
      {result.data.dictionary_entries.map(entry => <div key={entry.entry_id}>
        <p><span lang="grc">{entry.headword}</span> · {entry.gloss || 'No dictionary gloss recorded.'}</p>
      </div>)}
      <p>{result.data.counts.total_matches} source occurrences</p>
    </> : null}
  </aside>;
}

/** Preserve the actual verse punctuation; never synthesize text from dictionary forms. */
export function sourceParts(unit: GreekUnit) {
  const parts: Array<{ before: string; token: GreekUnit['tokens'][number] }> = [];
  let offset = 0;
  for (const token of unit.tokens) {
    const start = unit.source_greek.indexOf(token.surface, offset);
    if (!token.surface || start < 0) return null;
    parts.push({ before: unit.source_greek.slice(offset, start), token });
    offset = start + token.surface.length;
  }
  return { parts, after: unit.source_greek.slice(offset) };
}

/** One MT unit's explicitly mapped Greek sources, also retained when the MT card collapses. */
export function ArrangementGreekSource({ unitId, sources, compact = false, interactive = true, onInspect }: {
  unitId: string; sources?: BriefingGreekSources; compact?: boolean; interactive?: boolean;
  onInspect?: () => void;
}) {
  const [word, setWord] = useState<Word | null>(null);
  const origin = useRef<HTMLButtonElement | null>(null);
  const suppressFocus = useRef(false);
  const mapping = sources?.available ? sources.by_mt_unit[unitId] : undefined;
  const canInspect = interactive && Boolean(sources?.lexical_preview || (sources?.study_snapshot_id && sources.policy_revision_id));
  useEffect(() => setWord(null), [unitId, sources?.study_snapshot_id, sources?.policy_revision_id]);
  function close(returnFocus = true) {
    setWord(null);
    if (returnFocus) {
      suppressFocus.current = true;
      origin.current?.focus();
      suppressFocus.current = false;
    }
  }
  return <div className="arr-verse__greek" aria-label="Greek LXX source">
    <h5 className="arr-source-label" title={sources?.preview ? sources.message : undefined}>
      Greek (LXX){sources?.edition_id ? ` · ${sources.edition_id} ${sources.text_revision_id ?? ''}` : ''}
      {sources?.preview ? ' · unreviewed preview' : ''}
    </h5>
    {!sources?.available ? <p className="arr-source-state">{sources?.message ?? 'Greek source evidence is unavailable.'}</p> : null}
    {sources?.available && !mapping ? <p className="arr-source-state">
      No {sources.preview ? 'proposed' : 'reviewed'} Greek correspondence recorded for this Hebrew verse.
    </p> : null}
    {mapping?.units.length === 0 ? <p className="arr-source-state">
      Mapping: {mapping.relations.join(', ') || 'unresolved'}. No corresponding Greek text recorded in this edition.
    </p> : null}
    {mapping?.units.map(unit => {
      const parts = sourceParts(unit);
      const interlinear = !compact && parts && unit.tokens.some(token => token.gloss);
      const renderWord = (token: GreekUnit['tokens'][number]) => canInspect ? <button
        type="button" className="arr-greek-word" aria-label={`Study Greek ${token.surface} · ${unit.ref}`}
        onFocus={(event) => { if (suppressFocus.current) return; onInspect?.(); if (!word?.pinned) setWord({ ...placeCard(token.token_id, event.currentTarget), pinned: false }); }}
        onBlur={() => { if (!word?.pinned) setWord(null); }}
        onMouseEnter={(event) => { onInspect?.(); if (!word?.pinned) setWord({ ...placeCard(token.token_id, event.currentTarget), pinned: false }); }}
        onMouseLeave={() => { if (!word?.pinned) setWord(null); }}
        onClick={(event) => {
          event.stopPropagation(); origin.current = event.currentTarget; onInspect?.();
          setWord({ ...placeCard(token.token_id, event.currentTarget), pinned: true });
        }} onKeyDown={(event) => { if (event.key === 'Escape') { event.stopPropagation(); close(); } }}>
        {token.surface}
      </button> : token.surface;
      return <div key={unit.unit_id} className="arr-greek-unit" data-source-reference={unit.ref}>
        <p className="arr-source-ref">{unit.ref}{unit.partial ? ' · partial correspondence; full Greek verse shown' : ''}</p>
        {interlinear ? <div lang="grc" dir="ltr" className="arr-greek-text arr-greek-interlinear" aria-label="Greek word-by-word meanings">
          {parts.parts.map(({ token }, index) => <span key={token.token_id} className="arr-greek-token">
            <span className="arr-greek-surface">{index === 0 ? parts.parts[0].before : ''}{renderWord(token)}{parts.parts[index + 1]?.before ?? parts.after}</span>
            <span className="interlinear__gl" lang="en" dir="ltr">{token.gloss || 'Meaning unavailable'}</span>
          </span>)}
        </div> : <p lang="grc" dir="ltr" className="arr-greek-text">{canInspect && parts ? <>
          {parts.parts.map(({ before, token }) => <Fragment key={token.token_id}>{before}{renderWord(token)}</Fragment>)}{parts.after}
        </> : unit.source_greek}</p>}
        {!compact && !interlinear && unit.tokens.some(token => token.gloss) ? <>
          <p className="arr-greek-literal"><span className="verse-label">Greek word-by-word aid </span>{unit.literal_text || 'Lexical glosses unresolved.'}</p>
        </> : null}
      </div>;
    })}
    {word && sources?.available ? <GreekWordStudy key={word.tokenId} word={word} sources={sources} onClose={() => close()} onCloseOutside={() => close(false)} /> : null}
  </div>;
}
