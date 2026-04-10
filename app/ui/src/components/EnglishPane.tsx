import type { ChangeEvent } from 'react';

import type { Layer, Rendering } from '../types';

interface EnglishPaneProps {
  renderings: Rendering[];
  activeLayer: Layer;
  highlightedRenderingIds: string[];
  highlightedSpanIds: string[];
  selectedSpanIds: string[];
  hoveredSpanId: string | null;
  onSelectLayer: (layer: Layer) => void;
  onHoverSpan: (spanId: string | null) => void;
  onToggleSpan: (spanId: string) => void;
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
  highlightedSpanIds,
  selectedSpanIds,
  hoveredSpanId,
  onSelectLayer,
  onHoverSpan,
  onToggleSpan,
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
            <div className="rendering-span-row" aria-label={`Rendering spans for ${rendering.rendering_id}`}>
              {rendering.target_spans.length > 0 ? (
                rendering.target_spans.map((span) => {
                  const linked = highlightedSpanIds.includes(span.span_id);
                  const selected = selectedSpanIds.includes(span.span_id);
                  const active = hoveredSpanId === span.span_id;
                  return (
                    <button
                      key={span.span_id}
                      type="button"
                      className={`rendering-span ${linked ? 'linked' : ''} ${selected ? 'selected' : ''} ${active ? 'active' : ''}`}
                      onMouseEnter={() => onHoverSpan(span.span_id)}
                      onMouseLeave={() => onHoverSpan(null)}
                      onClick={() => onToggleSpan(span.span_id)}
                      aria-pressed={selected}
                      title={span.span_id}
                    >
                      {span.text}
                    </button>
                  );
                })
              ) : (
                <p className="rendering-text">{rendering.text}</p>
              )}
            </div>
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
                  <span key={`${flag.code}-${flag.severity}`}>{flag.code}:{flag.severity}</span>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
