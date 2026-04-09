import type { ChangeEvent } from 'react';

import type { Layer, Rendering } from '../types';

interface EnglishPaneProps {
  renderings: Rendering[];
  activeLayer: Layer;
  highlightedRenderingIds: string[];
  onSelectLayer: (layer: Layer) => void;
}

const layers: Layer[] = ['gloss', 'literal', 'phrase', 'concept', 'lyric', 'metered_lyric', 'parallelism_lyric'];

export function EnglishPane({ renderings, activeLayer, highlightedRenderingIds, onSelectLayer }: EnglishPaneProps) {
  const filtered = renderings.filter((rendering) => rendering.layer === activeLayer);

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
