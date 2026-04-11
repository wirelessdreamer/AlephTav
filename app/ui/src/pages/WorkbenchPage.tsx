import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';

import { BottomDrawer } from '../components/BottomDrawer';
import { EnglishPane } from '../components/EnglishPane';
import { HebrewPane } from '../components/HebrewPane';
import { InspectorRail } from '../components/InspectorRail';
import {
  useAlternateLifecycleAction,
  useCurrentPsalm,
  useDemoteRendering,
  useOpenConcerns,
  usePinnedLexicalCard,
  useProject,
  usePsalms,
  useSetPinnedLexicalCard,
  useTokenCard,
  useUnit,
} from '../hooks/useWorkbench';
import type { Alignment, Layer, Psalm, Rendering, TokenCard } from '../types';

export function WorkbenchPage() {
  const [selectedPsalmId, setSelectedPsalmId] = useState<string | null>('ps001');
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>('ps001.v001.a');
  const [activeLayer, setActiveLayer] = useState<Layer>('literal');
  const [granularity, setGranularity] = useState<'colon' | 'verse'>('colon');
  const [hoveredTokenId, setHoveredTokenId] = useState<string | null>(null);
  const [hoveredSpanId, setHoveredSpanId] = useState<string | null>(null);
  const [selectedTokenIds, setSelectedTokenIds] = useState<string[]>([]);
  const [selectedSpanIds, setSelectedSpanIds] = useState<string[]>([]);
  const [selectedAlignmentId, setSelectedAlignmentId] = useState<string | null>(null);
  const [compareLeftId, setCompareLeftId] = useState<string | null>(null);
  const [compareRightId, setCompareRightId] = useState<string | null>(null);

  const projectQuery = useProject();
  const psalmsQuery = usePsalms();
  const unitQuery = useUnit(selectedUnitId);
  const concernsQuery = useOpenConcerns();
  const pinnedLexicalCardQuery = usePinnedLexicalCard();
  const { data: project } = projectQuery;
  const { data: psalms } = psalmsQuery;
  const { data: unit } = unitQuery;
  const { data: concerns } = concernsQuery;
  const { data: pinnedLexicalCard } = pinnedLexicalCardQuery;
  const setPinnedLexicalCard = useSetPinnedLexicalCard();
  const alternateAction = useAlternateLifecycleAction(selectedUnitId);
  const demoteRendering = useDemoteRendering(selectedUnitId);

  const pinnedTokenId = pinnedLexicalCard?.token_id ?? null;
  const [pinOverrideTokenId, setPinOverrideTokenId] = useState<string | null | undefined>(undefined);
  const effectivePinnedTokenId = pinOverrideTokenId !== undefined ? pinOverrideTokenId : pinnedTokenId;
  const hoveredToken = useTokenCard(!effectivePinnedTokenId ? hoveredTokenId : null);
  const pendingPinnedToken = useTokenCard(
    pinOverrideTokenId !== undefined && pinOverrideTokenId !== null && pinOverrideTokenId !== pinnedTokenId ? pinOverrideTokenId : null,
  );
  const tokenCard = pinnedLexicalCard?.token ?? pendingPinnedToken.data ?? hoveredToken.data;
  const [displayedTokenCard, setDisplayedTokenCard] = useState<TokenCard | undefined>(undefined);
  const tokenId = displayedTokenCard?.token_id ?? tokenCard?.token_id ?? hoveredTokenId;

  const currentPsalm = useCurrentPsalm(psalms, selectedPsalmId);
  const bootstrapError = projectQuery.error ?? psalmsQuery.error;
  const unitError = unitQuery.error;

  if (bootstrapError) {
    return (
      <main className="workbench-shell workbench-shell--empty">
        <section className="empty-state-card">
          <p className="eyebrow">Workbench Unavailable</p>
          <h1>Start the local API before opening the workbench.</h1>
          <p className="subtle">
            The workbench expects the FastAPI backend on <code>127.0.0.1:8000</code>. GitHub Pages can show the welcome page, but the live editor remains local-only. Use the repo setup script to verify dependencies, rebuild local data, and launch both services.
          </p>
          <pre>
            <code>{['./setup.sh', '.\\setup.ps1'].join('\n')}</code>
          </pre>
          <div className="hero-actions">
            <a className="hero-link hero-link-primary" href="#/">
              Back to welcome page
            </a>
          </div>
        </section>
      </main>
    );
  }

  const activeAlignments = useMemo(() => unit?.alignments.filter((alignment: Alignment) => alignment.layer === activeLayer) ?? [], [unit, activeLayer]);

  const activeAlignment = useMemo(
    () => activeAlignments.find((alignment: Alignment) => alignment.alignment_id === selectedAlignmentId) ?? null,
    [activeAlignments, selectedAlignmentId],
  );

  const tokenToAlignments = useMemo(() => {
    const mapping = new Map<string, Alignment[]>();
    activeAlignments.forEach((alignment) => {
      alignment.source_token_ids.forEach((tokenId) => {
        mapping.set(tokenId, [...(mapping.get(tokenId) ?? []), alignment]);
      });
    });
    return mapping;
  }, [unit, activeLayer]);

  const spanToAlignments = useMemo(() => {
    const mapping = new Map<string, Alignment[]>();
    activeAlignments.forEach((alignment) => {
      alignment.target_span_ids.forEach((spanId) => {
        mapping.set(spanId, [...(mapping.get(spanId) ?? []), alignment]);
      });
    });
    return mapping;
  }, [activeAlignments]);

  const highlightedTokenIds = useMemo(() => {
    const ids = new Set<string>(selectedTokenIds);
    selectedSpanIds.forEach((spanId) => {
      (spanToAlignments.get(spanId) ?? []).forEach((alignment) => alignment.source_token_ids.forEach((tokenId) => ids.add(tokenId)));
    });
    if (hoveredSpanId) {
      (spanToAlignments.get(hoveredSpanId) ?? []).forEach((alignment) => alignment.source_token_ids.forEach((tokenId) => ids.add(tokenId)));
    }
    activeAlignment?.source_token_ids.forEach((tokenId) => ids.add(tokenId));
    return [...ids];
  }, [activeAlignment, hoveredSpanId, selectedTokenIds, selectedSpanIds, spanToAlignments]);

  const highlightedSpanIds = useMemo(() => {
    const ids = new Set<string>(selectedSpanIds);
    selectedTokenIds.forEach((tokenId) => {
      (tokenToAlignments.get(tokenId) ?? []).forEach((alignment) => alignment.target_span_ids.forEach((spanId) => ids.add(spanId)));
    });
    if (hoveredTokenId) {
      (tokenToAlignments.get(hoveredTokenId) ?? []).forEach((alignment) => alignment.target_span_ids.forEach((spanId) => ids.add(spanId)));
    }
    activeAlignment?.target_span_ids.forEach((spanId) => ids.add(spanId));
    return [...ids];
  }, [activeAlignment, hoveredTokenId, selectedSpanIds, selectedTokenIds, tokenToAlignments]);

  const highlightedRenderingIds = useMemo(() => {
    if (!unit) return [];
    const spans = new Set(highlightedSpanIds);
    return unit.renderings
      .filter((rendering: Rendering) => rendering.layer === activeLayer)
      .filter((rendering: Rendering) => rendering.target_spans.some((span) => spans.has(span.span_id)))
      .map((rendering: Rendering) => rendering.rendering_id);
  }, [unit, activeLayer, highlightedSpanIds]);

  useEffect(() => {
    setHoveredTokenId(null);
    setHoveredSpanId(null);
    setSelectedTokenIds([]);
    setSelectedSpanIds([]);
    setSelectedAlignmentId(null);
  }, [selectedUnitId, activeLayer]);

  useEffect(() => {
    if (!selectedAlignmentId) {
      return;
    }
    if (!activeAlignments.some((alignment) => alignment.alignment_id === selectedAlignmentId)) {
      setSelectedAlignmentId(null);
    }
  }, [activeAlignments, selectedAlignmentId]);

  useEffect(() => {
    if (!activeAlignment) {
      return;
    }
    setSelectedTokenIds(activeAlignment.source_token_ids);
    setSelectedSpanIds(activeAlignment.target_span_ids);
  }, [activeAlignment]);

  useEffect(() => {
    setPinOverrideTokenId(undefined);
  }, [pinnedTokenId]);

  useEffect(() => {
    if (tokenCard) {
      setDisplayedTokenCard(tokenCard);
      return;
    }
    if (!effectivePinnedTokenId && !hoveredTokenId) {
      setDisplayedTokenCard(undefined);
    }
  }, [effectivePinnedTokenId, hoveredTokenId, tokenCard]);

  const hebrewRef = useRef<HTMLDivElement>(null);
  const englishRef = useRef<HTMLDivElement>(null);
  const syncingPaneRef = useRef<'hebrew' | 'english' | null>(null);

  const syncScroll = (source: 'hebrew' | 'english') => {
    if (syncingPaneRef.current === source) {
      syncingPaneRef.current = null;
      return;
    }
    const from = source === 'hebrew' ? hebrewRef.current : englishRef.current;
    const to = source === 'hebrew' ? englishRef.current : hebrewRef.current;
    if (!from || !to) return;
    const percent = from.scrollTop / Math.max(from.scrollHeight - from.clientHeight, 1);
    syncingPaneRef.current = source === 'hebrew' ? 'english' : 'hebrew';
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

  const handleNavigateToUnit = (unitId: string, psalmId: string) => {
    setSelectedPsalmId(psalmId);
    setSelectedUnitId(unitId);
  };

  const handleGranularityChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setGranularity(event.target.value as 'colon' | 'verse');
  };

  const handlePinToken = (nextTokenId: string) => {
    const tokenIdToPersist = effectivePinnedTokenId === nextTokenId ? null : nextTokenId;
    setPinOverrideTokenId(tokenIdToPersist);
    setPinnedLexicalCard.mutate(tokenIdToPersist);
  };

  const handleUnpinToken = () => {
    setPinOverrideTokenId(null);
    setPinnedLexicalCard.mutate(null);
  };

  const handleToggleToken = (tokenId: string) => {
    setSelectedTokenIds((existing) => (existing.includes(tokenId) ? existing.filter((item) => item !== tokenId) : [...existing, tokenId]));
  };

  const handleToggleSpan = (spanId: string) => {
    setSelectedSpanIds((existing) => (existing.includes(spanId) ? existing.filter((item) => item !== spanId) : [...existing, spanId]));
  };

  const handlePromoteAlternate = (renderingId: string) => {
    alternateAction.mutate({ renderingId, action: 'promote', payload: { reviewer: 'ui', reviewer_role: 'release reviewer' } });
  };

  const handleAcceptAlternate = (renderingId: string) => {
    alternateAction.mutate({ renderingId, action: 'accept', payload: { created_by: 'ui' } });
  };

  const handleRejectAlternate = (renderingId: string) => {
    alternateAction.mutate({ renderingId, action: 'reject', payload: { created_by: 'ui' } });
  };

  const handleDeprecateAlternate = (renderingId: string) => {
    alternateAction.mutate({ renderingId, action: 'deprecate', payload: { created_by: 'ui' } });
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
        {unitError ? <span className="status-pill warning">Unit load failed: {(unitError as Error).message}</span> : null}
      </section>
      <section className="workspace-grid">
        <div className="scroll-panel" ref={hebrewRef} onScroll={() => syncScroll('hebrew')}>
          <HebrewPane
            tokens={unit?.tokens ?? []}
            activeTokenId={tokenId}
            highlightedTokenIds={highlightedTokenIds}
            selectedTokenIds={selectedTokenIds}
            onHoverToken={setHoveredTokenId}
            onPinToken={handlePinToken}
            onToggleToken={handleToggleToken}
          />
        </div>
        <div className="scroll-panel" ref={englishRef} onScroll={() => syncScroll('english')}>
          <EnglishPane
            renderings={unit?.renderings ?? []}
            activeLayer={activeLayer}
            project={project}
            highlightedRenderingIds={highlightedRenderingIds}
            highlightedSpanIds={highlightedSpanIds}
            selectedSpanIds={selectedSpanIds}
            hoveredSpanId={hoveredSpanId}
            onSelectLayer={setActiveLayer}
            onHoverSpan={setHoveredSpanId}
            onToggleSpan={handleToggleSpan}
            onCompareLeft={setCompareLeftId}
            onCompareRight={setCompareRightId}
            onPromoteAlternate={handlePromoteAlternate}
            onDemoteCanonical={(renderingId) => demoteRendering.mutate(renderingId)}
            onAcceptAlternate={handleAcceptAlternate}
            onRejectAlternate={handleRejectAlternate}
            onDeprecateAlternate={handleDeprecateAlternate}
          />
        </div>
        <InspectorRail tokenCard={displayedTokenCard} unit={unit} project={project} concerns={concerns} onUnpinToken={handleUnpinToken} />
      </section>
      <BottomDrawer
        unit={unit}
        concerns={concerns}
        tokenCard={displayedTokenCard}
        concordanceSeed={displayedTokenCard?.lemma ?? undefined}
        onNavigateToUnit={handleNavigateToUnit}
        activeLayer={activeLayer}
        selectedTokenIds={selectedTokenIds}
        selectedSpanIds={selectedSpanIds}
        selectedAlignmentId={selectedAlignmentId}
        onSelectedAlignmentChange={setSelectedAlignmentId}
        onClearAlignmentSelection={() => {
          setSelectedAlignmentId(null);
          setSelectedTokenIds([]);
          setSelectedSpanIds([]);
        }}
        compareLeftId={compareLeftId}
        compareRightId={compareRightId}
        onCompareLeftChange={setCompareLeftId}
        onCompareRightChange={setCompareRightId}
      />
    </main>
  );
}
