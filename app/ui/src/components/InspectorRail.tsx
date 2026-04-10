import type { OpenConcerns, Project, TokenCard, Unit } from '../types';

interface InspectorRailProps {
  tokenCard?: TokenCard;
  unit?: Unit;
  project?: Project;
  concerns?: OpenConcerns;
  onUnpinToken: () => void;
}

export function InspectorRail({ tokenCard, unit, project, concerns, onUnpinToken }: InspectorRailProps) {
  const unitFlags = concerns?.open_drift_flags.filter((flag) => flag.unit_id === unit?.unit_id) ?? [];
  const unitUncovered = concerns?.uncovered_tokens.filter((flag) => flag.unit_id === unit?.unit_id) ?? [];
  const handleCopyReference = async () => {
    if (!tokenCard || !navigator.clipboard) return;
    await navigator.clipboard.writeText(tokenCard.copy_reference);
  };

  return (
    <aside className="inspector-rail">
      <section className="inspector-card">
        <h3>Inspector</h3>
        {!tokenCard ? <p className="empty-state">Hover or pin a Hebrew token to inspect lexical details.</p> : null}
        {tokenCard ? (
          <>
            <h4>{tokenCard.surface}</h4>
            <p className="subtle">{tokenCard.copy_reference}</p>
            <div className="tab-row">
              <button type="button" className="tab" onClick={() => void handleCopyReference()}>
                Copy ref
              </button>
              <button type="button" className="tab" onClick={onUnpinToken}>
                Unpin
              </button>
            </div>
            <dl className="detail-grid">
              <dt>Lemma</dt>
              <dd>{tokenCard.lemma}</dd>
              <dt>Strong's</dt>
              <dd>{tokenCard.strong}</dd>
              <dt>Morphology</dt>
              <dd>{tokenCard.morph_readable}</dd>
              <dt>Syntax</dt>
              <dd>{tokenCard.syntax_role}</dd>
              <dt>Semantic</dt>
              <dd>{tokenCard.semantic_role}</dd>
              <dt>Sense</dt>
              <dd>{tokenCard.word_sense}</dd>
              <dt>Psalm matches</dt>
              <dd>{tokenCard.counts.same_psalms}</dd>
              <dt>Corpus matches</dt>
              <dd>{tokenCard.counts.wider_corpus}</dd>
            </dl>
            <div className="tag-row">
              {tokenCard.gloss_list.map((gloss) => (
                <span key={gloss} className="tag">
                  {gloss}
                </span>
              ))}
            </div>
            <ul className="simple-list">
              {tokenCard.nearby_usage_examples.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </>
        ) : null}
      </section>
      <section className="inspector-card">
        <h3>Source & license</h3>
        <ul className="source-list">
          {project?.source_manifests.map((source) => (
            <li key={source.source_id}>
              <strong>{source.source_id}</strong> — {source.version}
              <div className="subtle">{source.license}</div>
              {!source.allowed_for_export ? <div className="warning-inline">Restricted witness/export blocked</div> : null}
            </li>
          ))}
        </ul>
      </section>
      <section className="inspector-card">
        <h3>Warnings</h3>
        <p>{unitFlags.length} drift flags, {unitUncovered.length} uncovered token(s)</p>
        {unit?.witnesses?.length ? <div className="warning-inline">Witness text present and version-pinned separately.</div> : null}
      </section>
    </aside>
  );
}
