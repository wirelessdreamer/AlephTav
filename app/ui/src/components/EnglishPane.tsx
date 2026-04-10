import type { ChangeEvent } from 'react';

import type { Layer, Rendering } from '../types';

interface EnglishPaneProps {
  renderings: Rendering[];
  activeLayer: Layer;
  highlightedRenderingIds: string[];
  onSelectLayer: (layer: Layer) => void;
  onCompareLeft: (renderingId: string) => void;
  onCompareRight: (renderingId: string) => void;
  onPromoteAlternate: (renderingId: string) => void;
  onDemoteCanonical: (renderingId: string) => void;
  onAcceptAlternate: (renderingId: string) => void;
  onRejectAlternate: (renderingId: string) => void;
  onDeprecateAlternate: (renderingId: string) => void;
}

const layers: Layer[] = ['gloss', 'literal', 'phrase', 'concept', 'lyric', 'metered_lyric', 'parallelism_lyric'];

export function EnglishPane({
  renderings,
  activeLayer,
  highlightedRenderingIds,
  onSelectLayer,
  onCompareLeft,
  onCompareRight,
  onPromoteAlternate,
  onDemoteCanonical,
  onAcceptAlternate,
  onRejectAlternate,
  onDeprecateAlternate,
}: EnglishPaneProps) {
  const filtered = renderings
    .filter((rendering) => rendering.layer === activeLayer)
    .sort((left, right) => {
      if (left.status === right.status) {
        return left.rendering_id.localeCompare(right.rendering_id);
      }
      if (left.status === 'canonical') return -1;
      if (right.status === 'canonical') return 1;
      return left.status.localeCompare(right.status);
    });

  const handleLayerChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onSelectLayer(event.target.value as Layer);
  };

  return (
    <section className="pane pane-english">
      <header className="pane-header horizontal-between">
        <div>
          <h2>English renderings</h2>
          <span className="subtle">Canonical plus alternate renderings by layer</span>
        </div>
        <label className="compact-field">
          <span>Layer</span>
          <select value={activeLayer} onChange={handleLayerChange}>
            {layers.map((layer) => (
              <option key={layer} value={layer}>
                {layer}
              </option>
            ))}
          </select>
        </label>
      </header>
      <div className="rendering-list">
        {filtered.length === 0 ? <p className="empty-state">No renderings for this layer yet.</p> : null}
        {filtered.map((rendering) => (
          <article key={rendering.rendering_id} className={`rendering-card ${highlightedRenderingIds.includes(rendering.rendering_id) ? 'linked' : ''}`}>
            <div className="horizontal-between">
              <strong>{rendering.status}</strong>
              <span className="subtle">{rendering.rendering_id}</span>
            </div>
            <p className="rendering-text">{rendering.text}</p>
            <div className="tag-row">
              {rendering.style_tags.map((tag) => (
                <span key={tag} className="tag">
                  {tag}
                </span>
              ))}
            </div>
            {rendering.style_goal || rendering.metric_profile ? (
              <p className="subtle">
                {rendering.style_goal ? `goal: ${rendering.style_goal}` : null}
                {rendering.style_goal && rendering.metric_profile ? ' • ' : null}
                {rendering.metric_profile ? `metric: ${rendering.metric_profile}` : null}
              </p>
            ) : null}
            <div className="inline-actions">
              <button type="button" className="tab" onClick={() => onCompareLeft(rendering.rendering_id)}>
                Compare left
              </button>
              <button type="button" className="tab" onClick={() => onCompareRight(rendering.rendering_id)}>
                Compare right
              </button>
              {rendering.status === 'canonical' ? (
                <button type="button" className="tab" onClick={() => onDemoteCanonical(rendering.rendering_id)}>
                  Demote
                </button>
              ) : (
                <>
                  <button type="button" className="tab" onClick={() => onAcceptAlternate(rendering.rendering_id)}>
                    Accept
                  </button>
                  <button type="button" className="tab" onClick={() => onPromoteAlternate(rendering.rendering_id)}>
                    Promote
                  </button>
                  <button type="button" className="tab" onClick={() => onDeprecateAlternate(rendering.rendering_id)}>
                    Deprecate
                  </button>
                  <button type="button" className="tab" onClick={() => onRejectAlternate(rendering.rendering_id)}>
                    Reject
                  </button>
                </>
              )}
            </div>
            {rendering.drift_flags.length > 0 ? (
              <div className="warning-box">
                {rendering.drift_flags.map((flag) => (
                  <span key={flag}>{flag}</span>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
