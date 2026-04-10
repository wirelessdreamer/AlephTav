import { useEffect, useState } from 'react';
import type { ChangeEvent } from 'react';

import { useAdvancedSearch, useConcordance, useSearchPreset, useUnitWitnesses } from '../hooks/useWorkbench';
import type { OpenConcerns, TokenCard, Unit } from '../types';

type DrawerTab = 'concordance' | 'search' | 'witnesses' | 'audit' | 'compare';
type SearchScope =
  | 'all'
  | 'hebrew_surface'
  | 'normalized_hebrew'
  | 'lemma'
  | 'strong'
  | 'morphology'
  | 'english_renderings'
  | 'audit_notes'
  | 'issue_links';
type PresetName = 'alternates_meter_fit' | 'units_with_unresolved_drift' | 'units_changed_since_release' | null;

interface BottomDrawerProps {
  unit?: Unit;
  concerns?: OpenConcerns;
  tokenCard?: TokenCard;
  concordanceSeed?: string;
  onNavigateToUnit: (unitId: string, psalmId: string) => void;
}

export function BottomDrawer({ unit, concerns, tokenCard, concordanceSeed, onNavigateToUnit }: BottomDrawerProps) {
  const [tab, setTab] = useState<DrawerTab>('concordance');
  const [concordanceField, setConcordanceField] = useState('lemma');
  const [concordanceQuery, setConcordanceQuery] = useState(concordanceSeed ?? '');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchScope, setSearchScope] = useState<SearchScope>('all');
  const [includeWitnesses, setIncludeWitnesses] = useState(false);
  const [presetName, setPresetName] = useState<PresetName>(null);
  const [releaseId, setReleaseId] = useState('');

  const concordance = useConcordance(concordanceQuery, concordanceField);
  const advancedSearch = useAdvancedSearch(searchQuery, searchScope, includeWitnesses);
  const preset = useSearchPreset(presetName, presetName === 'units_changed_since_release' ? releaseId : undefined);
  const witnesses = useUnitWitnesses(unit?.unit_id ?? null);

  useEffect(() => {
    if (!concordanceSeed) {
      return;
    }
    setConcordanceQuery((existing) => existing || concordanceSeed);
  }, [concordanceSeed]);

  const unresolvedDriftCount = concerns?.open_drift_flags.filter((item) => item.unit_id === unit?.unit_id).length ?? 0;
  const uncoveredCount = concerns?.uncovered_tokens.filter((item) => item.unit_id === unit?.unit_id).length ?? 0;

  const handleNavigate = (unitId: string, psalmId: string) => {
    onNavigateToUnit(unitId, psalmId);
  };

  const handlePreset = (nextPreset: PresetName) => {
    setPresetName(nextPreset);
    if (tab !== 'search') {
      setTab('search');
    }
  };

  return (
    <section className="bottom-drawer">
      <header className="drawer-header">
        <div className="tab-row">
          {(['concordance', 'search', 'witnesses', 'audit', 'compare'] as DrawerTab[]).map((item) => (
            <button key={item} type="button" className={tab === item ? 'tab active' : 'tab'} onClick={() => setTab(item)}>
              {item}
            </button>
          ))}
        </div>
      </header>
      {tab === 'concordance' ? (
        <div className="drawer-panel">
          <div className="field-row">
            <label className="compact-field">
              <span>Concordance query</span>
              <input value={concordanceQuery} onChange={(event) => setConcordanceQuery(event.target.value)} placeholder="e.g. רעה or H7462" />
            </label>
            <label className="compact-field">
              <span>Field</span>
              <select value={concordanceField} onChange={(event) => setConcordanceField(event.target.value)}>
                <option value="surface">surface</option>
                <option value="normalized">normalized</option>
                <option value="lemma">lemma</option>
                <option value="strong">strong</option>
                <option value="morphology">morphology</option>
                <option value="stem">stem</option>
                <option value="syntax_role">syntax role</option>
              </select>
            </label>
          </div>
          {tokenCard ? (
            <div className="inline-actions">
              <button type="button" className="tab" onClick={() => { setConcordanceField('lemma'); setConcordanceQuery(tokenCard.lemma ?? tokenCard.surface); }}>
                Pivot lemma
              </button>
              <button type="button" className="tab" onClick={() => { setConcordanceField('strong'); setConcordanceQuery(tokenCard.strong ?? tokenCard.surface); }}>
                Pivot Strong's
              </button>
              <button type="button" className="tab" onClick={() => { setConcordanceField('surface'); setConcordanceQuery(tokenCard.surface); }}>
                Exact form
              </button>
            </div>
          ) : null}
          <div className="result-grid">
            <article className="compare-card">
              <h4>Occurrences</h4>
              <ul className="simple-list">
                {concordance.data?.map((item) => (
                  <li key={item.token_id}>
                    <button type="button" className="link-button" onClick={() => handleNavigate(item.unit_id, item.unit_id.split('.')[0])}>
                      {item.ref}
                    </button>
                    <span> {item.surface} / {item.lemma ?? '—'} / {item.strong ?? '—'}</span>
                  </li>
                ))}
                {!concordance.data?.length ? <li className="empty-state">No concordance matches yet.</li> : null}
              </ul>
            </article>
            <article className="compare-card">
              <h4>Token pivot</h4>
              {!tokenCard ? <p className="empty-state">Pin a token to see every occurrence in Psalms and the wider corpus.</p> : null}
              {tokenCard ? (
                <>
                  <p className="subtle">{tokenCard.copy_reference}</p>
                  <div className="mini-section">
                    <strong>In Psalms</strong>
                    <ul className="simple-list">
                      {tokenCard.same_psalms?.map((ref) => <li key={ref}>{ref}</li>)}
                      {!tokenCard.same_psalms?.length ? <li className="empty-state">No additional Psalms references recorded.</li> : null}
                    </ul>
                  </div>
                  <div className="mini-section">
                    <strong>Wider corpus</strong>
                    <ul className="simple-list">
                      {tokenCard.wider_corpus?.map((ref) => <li key={ref}>{ref}</li>)}
                      {!tokenCard.wider_corpus?.length ? <li className="empty-state">No wider corpus references recorded.</li> : null}
                    </ul>
                  </div>
                </>
              ) : null}
            </article>
          </div>
        </div>
      ) : null}
      {tab === 'search' ? (
        <div className="drawer-panel">
          <div className="field-row">
            <label className="compact-field search-field-wide">
              <span>Advanced search</span>
              <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search source, renderings, audit, or links" />
            </label>
            <label className="compact-field">
              <span>Scope</span>
              <select value={searchScope} onChange={(event) => setSearchScope(event.target.value as SearchScope)}>
                <option value="all">all canonical</option>
                <option value="hebrew_surface">Hebrew surface</option>
                <option value="normalized_hebrew">normalized Hebrew</option>
                <option value="lemma">lemma</option>
                <option value="strong">Strong's</option>
                <option value="morphology">morphology</option>
                <option value="english_renderings">English renderings</option>
                <option value="audit_notes">audit notes</option>
                <option value="issue_links">issue-linked units</option>
              </select>
            </label>
          </div>
          <label className="checkbox-field">
            <input type="checkbox" checked={includeWitnesses} onChange={(event: ChangeEvent<HTMLInputElement>) => setIncludeWitnesses(event.target.checked)} />
            <span>Include witness namespace results</span>
          </label>
          <div className="inline-actions">
            <button type="button" className={presetName === 'alternates_meter_fit' ? 'tab active' : 'tab'} onClick={() => handlePreset('alternates_meter_fit')}>
              Meter-fit alternates
            </button>
            <button type="button" className={presetName === 'units_with_unresolved_drift' ? 'tab active' : 'tab'} onClick={() => handlePreset('units_with_unresolved_drift')}>
              Unresolved drift
            </button>
            <button type="button" className={presetName === 'units_changed_since_release' ? 'tab active' : 'tab'} onClick={() => handlePreset('units_changed_since_release')}>
              Changed since release
            </button>
            <button type="button" className={presetName === null ? 'tab active' : 'tab'} onClick={() => setPresetName(null)}>
              Clear preset
            </button>
          </div>
          {presetName === 'units_changed_since_release' ? (
            <label className="compact-field">
              <span>Release id or ISO timestamp</span>
              <input value={releaseId} onChange={(event) => setReleaseId(event.target.value)} placeholder="e.g. 2026-04-09T14:44:04+00:00" />
            </label>
          ) : null}
          <ul className="simple-list search-results">
            {(presetName ? preset.data : advancedSearch.data)?.map((item) => (
              <li key={`${item.kind}-${item.label}-${item.ref}`} className={`search-result-card ${item.namespace === 'witness' ? 'witness-result' : ''}`}>
                <div className="horizontal-between">
                  <strong>{item.label}</strong>
                  <span className="subtle">{item.scope}</span>
                </div>
                <p className="result-snippet">{item.snippet}</p>
                <div className="result-meta">
                  <span>{item.ref}</span>
                  <span>{item.namespace}</span>
                  <button type="button" className="link-button" onClick={() => handleNavigate(item.unit_id, item.psalm_id)}>
                    Open unit
                  </button>
                </div>
              </li>
            ))}
            {!(presetName ? preset.data : advancedSearch.data)?.length ? <li className="empty-state">No search results yet.</li> : null}
          </ul>
        </div>
      ) : null}
      {tab === 'witnesses' ? (
        <div className="drawer-panel">
          <div className="warning-box">
            <div>Witnesses are version-pinned, display-only context.</div>
            <div>They are not blended into canonical source or export paths.</div>
          </div>
          <ul className="simple-list">
            {witnesses.data?.map((witness) => (
              <li key={`${witness.source_id}-${witness.versionTitle}-${witness.ref}`} className="search-result-card witness-result">
                <div className="horizontal-between">
                  <strong>{witness.versionTitle}</strong>
                  <span className="subtle">{witness.source_id}</span>
                </div>
                <p className="result-snippet">{witness.text}</p>
                <div className="result-meta">
                  <span>{witness.ref}</span>
                  <span>{witness.language}</span>
                  <a href={witness.source_url} target="_blank" rel="noreferrer">source</a>
                </div>
              </li>
            ))}
            {!witnesses.data?.length ? <li className="empty-state">No witness material attached to this unit.</li> : null}
          </ul>
        </div>
      ) : null}
      {tab === 'audit' ? (
        <div className="drawer-panel">
          <div className="result-grid">
            <article className="compare-card">
              <h4>Review trail</h4>
              <ul className="simple-list">
                {unit?.review_decisions.map((decision) => (
                  <li key={decision.decision_id}>{decision.timestamp} - {decision.reviewer_role}: {decision.decision}</li>
                ))}
                {!unit?.review_decisions.length ? <li className="empty-state">No review decisions recorded.</li> : null}
              </ul>
            </article>
            <article className="compare-card">
              <h4>Open concerns</h4>
              <div className="warning-box">
                <div>Uncovered tokens: {uncoveredCount}</div>
                <div>Drift flags: {unresolvedDriftCount}</div>
                <div>Unaligned spans: {concerns?.unaligned_spans.filter((item) => item.unit_id === unit?.unit_id).length ?? 0}</div>
              </div>
            </article>
          </div>
        </div>
      ) : null}
      {tab === 'compare' ? (
        <div className="drawer-panel compare-grid">
          <article className="compare-card">
            <h4>Canonical</h4>
            {unit?.renderings.filter((item) => item.status === 'canonical').map((item) => (
              <p key={item.rendering_id}>{item.layer}: {item.text}</p>
            ))}
          </article>
          <article className="compare-card">
            <h4>Alternates</h4>
            {unit?.renderings.filter((item) => item.status !== 'canonical').length ? (
              unit?.renderings.filter((item) => item.status !== 'canonical').map((item) => <p key={item.rendering_id}>{item.layer}: {item.text}</p>)
            ) : (
              <p className="empty-state">No alternates for compare.</p>
            )}
          </article>
          <article className="compare-card">
            <h4>Witness layer</h4>
            {witnesses.data?.length ? (
              witnesses.data.map((item) => <p key={`${item.source_id}-${item.ref}`}>{item.versionTitle}: {item.text}</p>)
            ) : (
              <p className="empty-state">No witness material for compare.</p>
            )}
          </article>
        </div>
      ) : null}
    </section>
  );
}
