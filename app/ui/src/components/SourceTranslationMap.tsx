import type { PsalmSourceTranslationMap, SourceTranslationMapToken, SourceTranslationMapUnit } from '../types';

interface SourceTranslationMapProps {
  data?: PsalmSourceTranslationMap;
  isLoading: boolean;
  error: Error | null;
  onNavigateToUnit: (unitId: string, psalmId: string) => void;
}

function percent(value: number | null): string {
  return value === null ? 'Not scored' : `${Math.round(value * 100)}%`;
}

function mappingLabel(token: SourceTranslationMapToken): string {
  if (token.status === 'explicit') {
    const types = [...new Set(token.alignments.map((alignment) => alignment.type.replace(/_/g, ' ')))];
    return `Mapped: ${types.join(', ')}`;
  }
  if (token.status === 'lexical_estimate') {
    return `Lexical anchor: ${token.visible_anchors.join(', ')}`;
  }
  return 'No visible mapping';
}

function SourceToken({ token }: { token: SourceTranslationMapToken }) {
  const targetText = token.alignments.map((alignment) => alignment.target_text).filter(Boolean).join(' / ');
  return (
    <li className={`source-map-token source-map-token--${token.status}`}>
      <div className="source-map-token__source">
        <strong dir="rtl">{token.surface}</strong>
        <span>{token.gloss ?? 'No lexical gloss'}</span>
      </div>
      <div className="source-map-token__mapping">
        <span>{mappingLabel(token)}</span>
        {targetText ? <small>Target span: {targetText}</small> : null}
        {token.source_role ? <small>Role: {token.source_role}</small> : null}
      </div>
    </li>
  );
}

function UnitMap({ unit, psalmId, onNavigateToUnit }: { unit: SourceTranslationMapUnit; psalmId: string; onNavigateToUnit: SourceTranslationMapProps['onNavigateToUnit'] }) {
  const { summary } = unit;
  return (
    <details className="source-map-unit" open={summary.state === 'mapped'}>
      <summary>
        <span>{unit.ref}</span>
        <span className={`source-map-unit__state source-map-unit__state--${summary.state}`}>
          {summary.state === 'mapped' ? `${percent(summary.fidelity_estimate)} source fidelity estimate` : 'No selected translation'}
        </span>
      </summary>
      <div className="source-map-unit__body">
        <div className="source-map-unit__texts">
          <div>
            <p className="eyebrow">Hebrew source</p>
            <p className="source-map-hebrew" dir="rtl">{unit.source_hebrew}</p>
            {unit.source_transliteration ? <p className="subtle">{unit.source_transliteration}</p> : null}
          </div>
          <div>
            <p className="eyebrow">Translation</p>
            {unit.rendering ? (
              <>
                <p className="source-map-translation">{unit.rendering.text}</p>
                <p className="subtle">
                  {unit.rendering.source_kind === 'witness' ? unit.rendering.source_label : unit.rendering.layer}
                  {' • '}{unit.rendering.status}
                </p>
              </>
            ) : (
              <p className="empty-state">{summary.selection_message ?? 'No selected translation is available for this verse.'}</p>
            )}
          </div>
        </div>
        <div className="source-map-unit__metrics">
          <span className="tag">Explicit structure: {percent(summary.structural_coverage)}</span>
          <span className="tag">Visible anchors: {percent(summary.visible_anchor_coverage)}</span>
          <span className="tag">Unmapped: {summary.unmapped_tokens}</span>
          <button type="button" className="link-button" onClick={() => onNavigateToUnit(unit.unit_id, psalmId)}>Open verse</button>
        </div>
        {unit.tokens.length ? (
          <ul className="source-map-token-list">
            {unit.tokens.map((token) => <SourceToken key={token.token_id} token={token} />)}
          </ul>
        ) : null}
        {unit.creative_liberties.length ? (
          <section className="source-map-liberties">
            <strong>Creative liberties and review cues</strong>
            <ul className="simple-list compact-list">
              {unit.creative_liberties.map((liberty, index) => (
                <li key={`${liberty.kind}-${liberty.token_id ?? index}`}>
                  <span className={`source-map-severity source-map-severity--${liberty.severity}`}>{liberty.severity}</span>
                  <strong>{liberty.label}</strong>: {liberty.detail}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </details>
  );
}

export function SourceTranslationMap({ data, isLoading, error, onNavigateToUnit }: SourceTranslationMapProps) {
  if (isLoading) {
    return <p className="empty-state">Mapping Hebrew structure to the selected translation…</p>;
  }
  if (error) {
    return <p className="empty-state">The source map could not load: {error.message}</p>;
  }
  if (!data) {
    return <p className="empty-state">Choose a Psalm to map its source and translation.</p>;
  }

  const { summary } = data;
  return (
    <div className="source-map">
      <header className="source-map__header">
        <div>
          <p className="eyebrow">Source → Translation Map</p>
          <h3>{data.title}</h3>
          <p className="subtle">Target: {data.translation_target.label}</p>
          <p className="subtle">{data.score_basis}</p>
        </div>
        <div className="source-map-score-grid">
          <div><strong>{summary.translated_units}/{summary.total_units}</strong><span>target verses</span></div>
          <div><strong>{percent(summary.structural_coverage)}</strong><span>explicit structure</span></div>
          <div><strong>{percent(summary.visible_anchor_coverage)}</strong><span>visible anchors</span></div>
          <div><strong>{percent(summary.fidelity_estimate)}</strong><span>fidelity estimate</span></div>
        </div>
      </header>

      {data.translation_target.read_only ? (
        <section className="source-map-summary source-map-summary--witness">
          <strong>Read-only witness comparison</strong>
          <p>{data.translation_target.label} is shown for comparison only. It has no project alignments, so the map does not treat lexical matches as structural proof.</p>
        </section>
      ) : null}

      <section className="source-map-summary">
        <strong>How to read this</strong>
        <p>Green tokens have a saved source-to-target alignment. Blue tokens have a lexical match only. Gray tokens need an alignment or a human judgement; they are not automatically errors.</p>
      </section>

      <section className="source-map-repetitions">
        <div>
          <h4>Repeated Hebrew lemmas</h4>
          {data.repetitions.length ? (
            <ul className="simple-list compact-list">
              {data.repetitions.slice(0, 16).map((repetition) => (
                <li key={repetition.lemma}>
                  <strong dir="rtl">{repetition.lemma}</strong> × {repetition.count} • {repetition.preservation.replace(/_/g, ' ')}
                  {repetition.glosses.length ? <span className="subtle"> — {repetition.glosses.join(' / ')}</span> : null}
                  <span className="subtle"> ({repetition.visible_anchor_count}/{repetition.count} visibly carried)</span>
                </li>
              ))}
            </ul>
          ) : <p className="empty-state">No repeated lexical anchors were detected in this Psalm.</p>}
        </div>
        <div>
          <h4>Possible added repetition</h4>
          {data.possible_added_repetitions.length ? (
            <ul className="simple-list compact-list">
              {data.possible_added_repetitions.map((item) => <li key={item.word}><strong>{item.word}</strong> × {item.count} — {item.detail}</li>)}
            </ul>
          ) : <p className="empty-state">No repeated target words need a stylistic review cue.</p>}
        </div>
      </section>

      <section className="source-map-units">
        {data.units.map((unit) => <UnitMap key={unit.unit_id} unit={unit} psalmId={data.psalm_id} onNavigateToUnit={onNavigateToUnit} />)}
      </section>
    </div>
  );
}
