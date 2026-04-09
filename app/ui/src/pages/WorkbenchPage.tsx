import { useMemo, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';

import { BottomDrawer } from '../components/BottomDrawer';
import { EnglishPane } from '../components/EnglishPane';
import { HebrewPane } from '../components/HebrewPane';
import { InspectorRail } from '../components/InspectorRail';
import { useCurrentPsalm, useOpenConcerns, useProject, usePsalms, useTokenCard, useUnit } from '../hooks/useWorkbench';
import type { Alignment, Layer, Psalm, Rendering } from '../types';

export function WorkbenchPage() {
  const [selectedPsalmId, setSelectedPsalmId] = useState<string | null>('ps001');
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>('ps001.v001.a');
  const [activeLayer, setActiveLayer] = useState<Layer>('literal');
  const [granularity, setGranularity] = useState<'colon' | 'verse'>('colon');
  const [hoveredTokenId, setHoveredTokenId] = useState<string | null>(null);
  const [pinnedTokenId, setPinnedTokenId] = useState<string | null>(null);

  const { data: project } = useProject();
  const { data: psalms } = usePsalms();
  const { data: unit } = useUnit(selectedUnitId);
  const { data: concerns } = useOpenConcerns();

  const tokenId = pinnedTokenId ?? hoveredTokenId;
  const { data: tokenCard } = useTokenCard(tokenId);

  const currentPsalm = useCurrentPsalm(psalms, selectedPsalmId);

  const linkedTokenIds = useMemo(() => {
    if (!unit) return [];
    return unit.alignments
      .filter((alignment: Alignment) => alignment.layer === activeLayer || activeLayer === 'literal')
      .flatMap((alignment: Alignment) => alignment.source_token_ids);
  }, [unit, activeLayer]);

  const linkedRenderingIds = useMemo(() => {
    if (!unit) return [];
    return unit.renderings
      .filter((rendering: Rendering) => rendering.layer === activeLayer)
      .map((rendering: Rendering) => rendering.rendering_id);
  }, [unit, activeLayer]);

  const hebrewRef = useRef<HTMLDivElement>(null);
  const englishRef = useRef<HTMLDivElement>(null);

  const syncScroll = (source: 'hebrew' | 'english') => {
    const from = source === 'hebrew' ? hebrewRef.current : englishRef.current;
    const to = source === 'hebrew' ? englishRef.current : hebrewRef.current;
    if (!from || !to) return;
    const percent = from.scrollTop / Math.max(from.scrollHeight - from.clientHeight, 1);
    to.scrollTop = percent * Math.max(to.scrollHeight - to.clientHeight, 0);
  };

  const handlePsalmChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextPsalmId = event.target.value;
    setSelectedPsalmId(nextPsalmId);
    const nextPsalm = psalms?.find((psalm: Psalm) => psalm.psalm_id === nextPsalmId);
    setSelectedUnitId(nextPsalm?.unit_ids[0] ?? null);
  };

  const handleUnitChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setSelectedUnitId(event.target.value);
  };

  const handleGranularityChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setGranularity(event.target.value as 'colon' | 'verse');
  };

  return (
    <main className="workbench-shell">
      <header className="topbar">
        <div>
          <h1>{project?.title ?? 'Psalms Copyleft Workbench'}</h1>
          <p className="subtle">Local-first Hebrew-source translation, alignment, review, audit, and export.</p>
        </div>
        <div className="topbar-controls">
          <label className="compact-field">
            <span>Psalm</span>
            <select value={selectedPsalmId ?? ''} onChange={handlePsalmChange}>
              {psalms?.map((psalm: Psalm) => (
                <option key={psalm.psalm_id} value={psalm.psalm_id}>
                  {psalm.title}
                </option>
              ))}
            </select>
          </label>
          <label className="compact-field">
            <span>Unit</span>
            <select value={selectedUnitId ?? ''} onChange={handleUnitChange}>
              {currentPsalm?.unit_ids.map((unitId) => (
                <option key={unitId} value={unitId}>
                  {unitId}
                </option>
              ))}
            </select>
          </label>
          <label className="compact-field">
            <span>Granularity</span>
            <select value={granularity} onChange={handleGranularityChange}>
              <option value="colon">colon</option>
              <option value="verse">verse</option>
            </select>
          </label>
        </div>
      </header>
      <section className="status-strip">
        <span className="status-pill">Human review required for canonical promotion</span>
        <span className="status-pill">Divine name policy: {project?.divine_name_policy}</span>
        <span className="status-pill warning">Warnings: {(concerns?.open_drift_flags.length ?? 0) + (concerns?.uncovered_tokens.length ?? 0)}</span>
      </section>
      <section className="workspace-grid">
        <div className="scroll-panel" ref={hebrewRef} onScroll={() => syncScroll('hebrew')}>
          <HebrewPane
            tokens={unit?.tokens ?? []}
            activeTokenId={tokenId}
            highlightedTokenIds={linkedTokenIds}
            onHoverToken={setHoveredTokenId}
            onPinToken={setPinnedTokenId}
          />
        </div>
        <div className="scroll-panel" ref={englishRef} onScroll={() => syncScroll('english')}>
          <EnglishPane
            renderings={unit?.renderings ?? []}
            activeLayer={activeLayer}
            highlightedRenderingIds={linkedRenderingIds}
            onSelectLayer={setActiveLayer}
          />
        </div>
        <InspectorRail tokenCard={tokenCard} unit={unit} project={project} concerns={concerns} />
      </section>
      <BottomDrawer unit={unit} concerns={concerns} concordanceSeed={tokenCard?.lemma} />
    </main>
  );
}
