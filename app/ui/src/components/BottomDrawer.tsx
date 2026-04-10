import { useEffect, useMemo, useState } from 'react';
import type { ChangeEvent } from 'react';

import { useConcordance } from '../hooks/useWorkbench';
import type { OpenConcerns, Unit } from '../types';

type DrawerTab = 'concordance' | 'audit' | 'compare';

interface BottomDrawerProps {
  unit?: Unit;
  concerns?: OpenConcerns;
  concordanceSeed?: string;
}

export function BottomDrawer({ unit, concerns, concordanceSeed }: BottomDrawerProps) {
  const [tab, setTab] = useState<DrawerTab>('concordance');
  const [query, setQuery] = useState(concordanceSeed ?? '');
  const [field, setField] = useState<'lemma' | 'strong'>('lemma');
  const concordance = useConcordance(query, field);

  const alternates = useMemo(
    () => unit?.renderings.filter((rendering) => rendering.status === 'accepted_as_alternate' || rendering.status === 'proposed') ?? [],
    [unit],
  );

  const handleQueryChange = (event: ChangeEvent<HTMLInputElement>) => {
    setQuery(event.target.value);
  };

  const handleFieldChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setField(event.target.value as 'lemma' | 'strong');
  };

  useEffect(() => {
    if (!concordanceSeed) return;
    if (field === 'lemma' && !query.trim()) {
      setQuery(concordanceSeed);
    }
  }, [concordanceSeed, field, query]);

  return (
    <section className="bottom-drawer">
      <header className="drawer-header">
        <div className="tab-row">
          {(['concordance', 'audit', 'compare'] as DrawerTab[]).map((item) => (
            <button key={item} type="button" className={tab === item ? 'tab active' : 'tab'} onClick={() => setTab(item)}>
              {item}
            </button>
          ))}
        </div>
      </header>
      {tab === 'concordance' ? (
        <div className="drawer-panel">
          <div className="tab-row">
            <label className="compact-field">
              <span>Query</span>
              <input value={query} onChange={handleQueryChange} placeholder="e.g. רעה or H7462" />
            </label>
            <label className="compact-field">
              <span>Field</span>
              <select value={field} onChange={handleFieldChange}>
                <option value="lemma">lemma</option>
                <option value="strong">strong</option>
              </select>
            </label>
          </div>
          <ul className="simple-list">
            {concordance.data?.map((item) => (
              <li key={item.token_id}>{item.ref} — {item.surface} / {item.lemma} / {item.strong}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {tab === 'audit' ? (
        <div className="drawer-panel">
          <h4>Audit trail</h4>
          <ul className="simple-list">
            {unit?.review_decisions.map((decision) => (
              <li key={decision.decision_id}>{decision.timestamp} — {decision.reviewer_role}: {decision.decision}</li>
            ))}
          </ul>
          <div className="warning-box">
            <div>Uncovered tokens: {concerns?.uncovered_tokens.filter((item) => item.unit_id === unit?.unit_id).length ?? 0}</div>
            <div>Unaligned spans: {concerns?.unaligned_spans.filter((item) => item.unit_id === unit?.unit_id).length ?? 0}</div>
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
            {alternates.length === 0 ? <p className="empty-state">No alternates for compare.</p> : alternates.map((item) => <p key={item.rendering_id}>{item.layer}: {item.text}</p>)}
          </article>
        </div>
      ) : null}
    </section>
  );
}
