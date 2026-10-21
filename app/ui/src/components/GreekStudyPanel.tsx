import { useEffect, useRef, useState } from 'react';
import { RequestStatus } from './RequestStatus';

import {
  studyUrl, useGreekStudy, type Attribution, type ConcordanceQuery, type Edition,
  type Entry, type GreekUnit, type Occurrences, type Presentation, type WordCard,
} from '../hooks/useGreekStudy';
import './GreekStudyPanel.css';

function AttributionText({ value }: { value?: Attribution }) {
  return value ? <p className="greek-study__attribution">{value.required_attribution} · {value.license}</p>
    : <p>Attribution unavailable; dictionary entry is not release ready.</p>;
}

/** Upstream markup is never HTML. Unknown nodes render only escaped text. */
function SafeTree({ nodes }: { nodes: Presentation[] }) {
  return <>{nodes.map((node, i) => {
    const content = <>{node.text ?? ''}{node.children ? <SafeTree nodes={node.children} /> : null}</>;
    if (node.type === 'emphasis') return <em key={i}>{content}</em>;
    if (node.type === 'strong') return <strong key={i}>{content}</strong>;
    if (node.type === 'paragraph') return <p key={i}>{content}</p>;
    return <span key={i}>{content}</span>;
  })}</>;
}

function DictionaryEntry({ entryId, card, context }: { entryId: string; card: WordCard; context: string }) {
  const entry = useGreekStudy<{ entry: Entry }>(studyUrl(`/greek/lexicon/entries/${encodeURIComponent(entryId)}`, {
    study_snapshot_id: card.study_snapshot_id, policy_revision_id: card.policy_revision_id,
  }), context);
  return <section aria-label="Dictionary entry">
    {entry.loading ? <p role="status">Loading entry…</p> : null}
    {entry.error ? <p role="alert">{entry.error}</p> : null}
    {entry.data ? <>
      <h4 lang="grc">{entry.data.entry.headword}</h4>
      <SafeTree nodes={Array.isArray(entry.data.entry.presentation) ? entry.data.entry.presentation
        : entry.data.entry.presentation ? [entry.data.entry.presentation] : []} />
      <AttributionText value={entry.data.entry.attribution} />
      {entry.data.entry.citations?.map((citation, i) => <p key={i}>
        {citation.original_label} · {citation.baseline} · external/unresolved reference
      </p>)}
    </> : null}
  </section>;
}

function Card({ tokenId, edition, context, onClose, onNavigate }: {
  tokenId: string; edition: Edition; context: string; onClose: () => void;
  onNavigate: (psalm: number) => void;
}) {
  const card = useGreekStudy<WordCard>(studyUrl(`/greek/tokens/${encodeURIComponent(tokenId)}/card`, edition), context);
  const [entryId, setEntryId] = useState<string | null>(null);
  const [queryOverride, setQueryOverride] = useState<ConcordanceQuery | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const query = queryOverride ?? card.data?.query;
  // The very first page is bound to the card, as are all subsequent pages.
  const occurrences = useGreekStudy<Occurrences>(query ? studyUrl('/greek/concordance', {
    ...query, cursor, page_size: 50,
  }) : null, `${context}|${tokenId}`);
  const chooseQuery = (value: ConcordanceQuery) => { setCursor(null); setQueryOverride(value); };
  return <aside className="greek-study__card" aria-label="Greek word study" onKeyDown={(event) => {
    if (event.key === 'Escape') { event.stopPropagation(); onClose(); }
  }}>
    <button type="button" onClick={onClose}>Close word study</button>
    {card.loading ? <p role="status">Loading word…</p> : null}
    {card.error ? <p role="alert">{card.error}</p> : null}
    {card.data ? <>
      <h3 lang="grc" dir="ltr">{card.data.token.surface}</h3>
      <p>{edition.edition_id} · {edition.text_revision_id} · {card.data.token.token_id}</p>
      {card.data.source_attribution?.map((source) => <p key={source.source_id}>
        Source: {source.attribution} · {source.license}
      </p>)}
      {card.data.analyses.length === 0 ? <p>Lexical and morphological analysis unresolved.</p> : null}
      {card.data.analyses.map((analysis) => <section key={analysis.analysis_id}>
        <p>Dictionary lemma: <span lang="grc">{analysis.lemma ?? 'unresolved'}</span> · {analysis.status}</p>
        <p>Occurrence parsing: {analysis.scheme ?? 'unresolved'} {analysis.raw_tag ?? ''}</p>
        <p>{Object.entries(analysis.features ?? {}).map(([key, value]) => `${key}: ${value}`).join(' · ')}</p>
        {analysis.lexeme_id ? <button type="button" onClick={() => chooseQuery({
          ...card.data!.query, query_kind: 'lexeme_id', value: analysis.lexeme_id!, identifier_scheme: null,
        })}>Occurrences of this lexeme</button> : null}
        {analysis.identifiers?.map((identifier) => <button type="button"
          key={`${identifier.scheme}:${identifier.value}`} onClick={() => chooseQuery({
            ...card.data!.query, query_kind: 'identifier', value: identifier.value,
            identifier_scheme: identifier.scheme,
          })}>{identifier.scheme}: {identifier.value}</button>)}
      </section>)}
      <button type="button" onClick={() => chooseQuery(card.data!.query)}>Exact surface occurrences</button>
      {card.data.dictionary_entries.length === 0 ? <p>No permitted dictionary entry linked.</p> : null}
      {card.data.dictionary_entries.map((entry) => <section key={entry.entry_id}>
        <button type="button" onClick={() => setEntryId(entry.entry_id)}>Read {entry.headword}</button>
        <AttributionText value={entry.attribution} />
      </section>)}
      {entryId ? <DictionaryEntry entryId={entryId} card={card.data} context={context} /> : null}
      <h4>Corpus occurrences</h4>
      {query ? <>
        <label>Analysis scope <select value={query.analysis_scope} onChange={(event) => chooseQuery({
          ...query, analysis_scope: event.target.value as ConcordanceQuery['analysis_scope'],
        })}><option value="all">All candidates</option><option value="reviewed">Reviewed</option>
          <option value="proposed">Proposed</option></select></label>
        <label>Analysis selection <select value={query.analysis_selection} onChange={(event) => chooseQuery({
          ...query, analysis_selection: event.target.value as ConcordanceQuery['analysis_selection'],
        })}><option value="possible">Possible analyses</option><option value="selected">Reviewed selected analysis</option></select></label>
      </> : null}
      {occurrences.loading ? <p role="status">Loading occurrences…</p> : null}
      {occurrences.error ? <p role="alert">{occurrences.error}</p> : null}
      {occurrences.data ? <>
        <p>{occurrences.data.total_matches} matches · {occurrences.data.total_tokens} physical tokens · {occurrences.data.total_verses} verses</p>
        <p>{occurrences.data.coverage.unresolved} unresolved. {occurrences.data.coverage.statement}</p>
        <ul>{occurrences.data.matches.map((hit) => <li key={hit.occurrence_id}>
          <button type="button" onClick={() => onNavigate(hit.psalm)}>Greek Psalm {hit.psalm}:{hit.verse} · {hit.surface}</button>
        </li>)}</ul>
        {cursor ? <button type="button" onClick={() => setCursor(null)}>First page</button> : null}
        {occurrences.data.next_cursor ? <button type="button" onClick={() => setCursor(occurrences.data!.next_cursor)}>Next occurrences</button> : null}
      </> : null}
      <p>Hebrew correspondence unresolved unless an accepted reviewed bridge is available.</p>
    </> : null}
  </aside>;
}

function Reader({ edition, context, mtPsalmId, hasTranslation }: {
  edition: Edition; context: string; mtPsalmId: string | null; hasTranslation: boolean;
}) {
  const [psalm, setPsalm] = useState(mtPsalmId ? Number(mtPsalmId.replace('ps', '')) : 1);
  const [tokenId, setTokenId] = useState<string | null>(null);
  const origin = useRef<HTMLButtonElement | null>(null);
  const psalms = useGreekStudy<{ psalms: number[] }>(studyUrl('/lxx/psalms', edition), context);
  const units = useGreekStudy<{ units: GreekUnit[] }>(studyUrl('/lxx/reader', { ...edition, psalm }), context);
  const close = () => { setTokenId(null); origin.current?.focus(); };
  return <>
    <label>Greek source psalm <select value={psalm} onChange={(event) => {
      setPsalm(Number(event.target.value)); setTokenId(null);
    }} disabled={psalms.loading || !psalms.data}>{psalms.loading ? <option value={psalm}>Loading Greek psalms…</option> : null}{psalms.data?.psalms.map((number) => <option key={number} value={number}>Greek Psalm {number}</option>)}</select></label>
    {psalms.loading ? <RequestStatus loading label="Loading Greek psalm list…" /> : null}
    <p>Source navigation keeps this project’s translations unchanged.</p>
    {!hasTranslation || mtPsalmId !== `ps${String(psalm).padStart(3, '0')}` ?
      <p>No English translation in this project for this source view.</p> :
      <p>Hebrew and Greek numbering require an edition-specific correspondence map.</p>}
    {units.loading ? <p role="status">Loading Greek source…</p> : null}
    {units.data?.units.length === 0 ? <p>No Greek verses available for this source psalm.</p> : null}
    {psalms.data?.psalms.length === 0 ? <p>No psalms available in this Greek edition.</p> : null}
    {units.error || psalms.error ? <p role="alert">{units.error ?? psalms.error}</p> : null}
    {units.data?.units.map((unit) => <section key={unit.unit_id} lang="grc" dir="ltr">
      <h3>{unit.ref}</h3>
      <p className="greek-study__tokens">{unit.tokens.map((token) => <button key={token.token_id}
        type="button" aria-label={`${token.surface} · ${unit.ref}`} aria-pressed={tokenId === token.token_id}
        onClick={(event) => { origin.current = event.currentTarget; setTokenId(token.token_id); }}>
        {token.surface}
      </button>)}</p>
    </section>)}
    {tokenId ? <Card key={`${context}|${tokenId}`} tokenId={tokenId} edition={edition} context={context}
      onClose={close} onNavigate={(number) => { setPsalm(number); setTokenId(null); }} /> : null}
  </>;
}

/** Mounted from ComparisonPage; independent of project translation membership. */
export function GreekStudyPanel({ collectionId, mtPsalmId, hasTranslation, mode, onModeChange }: {
  collectionId: string | null; mtPsalmId: string | null; hasTranslation: boolean;
  mode: 'mt' | 'lxx' | 'parallel'; onModeChange: (mode: 'mt' | 'lxx' | 'parallel') => void;
}) {
  const [restart, setRestart] = useState(0);
  const [selected, setSelected] = useState('');
  const context = `${collectionId}|${restart}`;
  const editions = useGreekStudy<{ editions: Edition[] }>('/lxx/editions', context);
  const edition = editions.data?.editions.find((item) => item.study_snapshot_id === selected)
    ?? editions.data?.editions[0];
  useEffect(() => { if (!editions.loading && !edition) onModeChange('mt'); }, [editions.loading, edition, onModeChange]);
  if (!edition) return <>
    <RequestStatus loading={editions.loading} error={editions.error}
      label={editions.loading ? 'Loading Greek editions…' : 'Greek study unavailable.'}
      onRetry={() => setRestart(value => value + 1)} />
    {!editions.loading && !editions.error ? <p className="verse-notes__hint">No Greek study editions available.</p> : null}
  </>;
  return <section className="greek-study" aria-label="Greek source study">
    <h2>Greek source study</h2>
    <label>Source view <select value={mode} onChange={(event) => onModeChange(event.target.value as typeof mode)}>
      <option value="mt">Hebrew (MT)</option><option value="lxx">Greek (LXX)</option>
      <option value="parallel">Hebrew and Greek</option>
    </select></label>
    <label>Greek edition <select value={edition.study_snapshot_id} onChange={(event) => setSelected(event.target.value)}>
      {editions.data?.editions.map((item) => <option key={item.study_snapshot_id} value={item.study_snapshot_id}>
        {item.edition_id} · {item.text_revision_id}
      </option>)}
    </select></label>
    <button type="button" onClick={() => setRestart((value) => value + 1)}>Restart Greek study</button>
    {mode !== 'mt' ? <Reader key={`${context}|${edition.study_snapshot_id}`} edition={edition} context={context}
      mtPsalmId={mtPsalmId} hasTranslation={hasTranslation} /> : null}
  </section>;
}
