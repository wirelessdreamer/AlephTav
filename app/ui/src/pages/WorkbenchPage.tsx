import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';

import { useAppRuntime } from '../app/AppContext';
import { BottomDrawer } from '../components/BottomDrawer';
import { InspectorRail } from '../components/InspectorRail';
import {
  useAlternateLifecycleAction,
  useCurrentPsalm,
  useDemoteRendering,
  useOpenConcerns,
  usePsalm,
  usePinnedLexicalCard,
  useProject,
  usePsalmCloud,
  usePsalmRetrieval,
  usePsalmVisualFlow,
  usePsalms,
  useSetPinnedLexicalCard,
  useTokenCard,
  useUnit,
} from '../hooks/useWorkbench';
import {
  getAvailableCorpusLayers,
  getDefaultPsalmSelection,
  getPreferredSelectableLayer,
  getSelectableLayers,
  getSelectablePsalmOptions,
  resolveLayerState,
  sortRenderingsByStatus,
} from '../lib/layers';
import type { Alignment, CloudNode, Psalm, RetrievalHit, RenderingSpan, Token, TokenCard, VisualFlowUnit } from '../types';

export function WorkbenchPage() {
  const {
    workbenchSelection,
    updateWorkbenchSelection,
    workbenchUi,
    updateWorkbenchUi,
    toggleWorkbenchTokenSelection,
    toggleWorkbenchSpanSelection,
    clearWorkbenchSelections,
  } = useAppRuntime();
  const selectedPsalmId = workbenchSelection.psalmId;
  const selectedUnitId = workbenchSelection.unitId;
  const activeLayer = workbenchSelection.layer;
  const granularity = workbenchSelection.granularity;
  const hoveredTokenId = workbenchUi.hoveredTokenId;
  const hoveredSpanId = workbenchUi.hoveredSpanId;
  const selectedTokenIds = workbenchUi.selectedTokenIds;
  const selectedSpanIds = workbenchUi.selectedSpanIds;
  const selectedAlignmentId = workbenchUi.selectedAlignmentId;
  const compareLeftId = workbenchUi.compareLeftId;
  const compareRightId = workbenchUi.compareRightId;
  const [selectedCloudNodeId, setSelectedCloudNodeId] = useState<string | null>(null);

  const projectQuery = useProject();
  const psalmsQuery = usePsalms();
  const { data: psalms } = psalmsQuery;
  const selectablePsalms = useMemo(() => getSelectablePsalmOptions(psalms), [psalms]);
  const selectedPsalm = useCurrentPsalm(selectablePsalms, selectedPsalmId);
  const defaultPsalm = useMemo(
    () => getDefaultPsalmSelection(selectablePsalms, selectedPsalmId),
    [selectablePsalms, selectedPsalmId],
  );
  const effectivePsalmId = selectedPsalm?.psalm_id ?? defaultPsalm?.psalm_id ?? null;
  const currentPsalmQuery = usePsalm(effectivePsalmId);
  const visualFlowQuery = usePsalmVisualFlow(effectivePsalmId);
  const cloudQuery = usePsalmCloud(effectivePsalmId);
  const retrievalQuery = usePsalmRetrieval(effectivePsalmId, selectedCloudNodeId);
  const unitQuery = useUnit(selectedUnitId);
  const concernsQuery = useOpenConcerns();
  const pinnedLexicalCardQuery = usePinnedLexicalCard();
  const { data: project } = projectQuery;
  const { data: currentPsalm } = currentPsalmQuery;
  const { data: visualFlow } = visualFlowQuery;
  const { data: unit } = unitQuery;
  const { data: concerns } = concernsQuery;
  const { data: pinnedLexicalCard } = pinnedLexicalCardQuery;
  const setPinnedLexicalCard = useSetPinnedLexicalCard();
  const alternateAction = useAlternateLifecycleAction(selectedUnitId);
  const demoteRendering = useDemoteRendering(selectedUnitId);

  const pinnedTokenId = workbenchUi.pinnedTokenId ?? pinnedLexicalCard?.token_id ?? null;
  const [pinOverrideTokenId, setPinOverrideTokenId] = useState<string | null | undefined>(undefined);
  const effectivePinnedTokenId = pinOverrideTokenId !== undefined ? pinOverrideTokenId : pinnedTokenId;
  const hoveredToken = useTokenCard(!effectivePinnedTokenId ? hoveredTokenId : null);
  const pendingPinnedToken = useTokenCard(
    pinOverrideTokenId !== undefined && pinOverrideTokenId !== null && pinOverrideTokenId !== pinnedTokenId ? pinOverrideTokenId : null,
  );
  const tokenCard = pinnedLexicalCard?.token ?? pendingPinnedToken.data ?? hoveredToken.data;
  const [displayedTokenCard, setDisplayedTokenCard] = useState<TokenCard | undefined>(undefined);
  const tokenId = displayedTokenCard?.token_id ?? tokenCard?.token_id ?? hoveredTokenId;

  const bootstrapError = projectQuery.error ?? psalmsQuery.error ?? currentPsalmQuery.error ?? visualFlowQuery.error;
  const unitError = unitQuery.error;
  const unitMap = useMemo(
    () => new Map((currentPsalm?.units ?? []).map((item) => [item.unit_id, item])),
    [currentPsalm?.units],
  );

  const activeAlignments = useMemo(() => unit?.alignments.filter((alignment: Alignment) => alignment.layer === activeLayer) ?? [], [unit, activeLayer]);
  const selectedUnitLayerState = useMemo(() => resolveLayerState(unit, activeLayer), [unit, activeLayer]);
  const selectableLayers = useMemo(
    () => getSelectableLayers(getAvailableCorpusLayers(selectablePsalms)),
    [selectablePsalms],
  );
  const selectedWorkflowLayer = useMemo(
    () => getPreferredSelectableLayer(activeLayer, selectableLayers),
    [activeLayer, selectableLayers],
  );

  const activeAlignment = useMemo(
    () => activeAlignments.find((alignment: Alignment) => alignment.alignment_id === selectedAlignmentId) ?? null,
    [activeAlignments, selectedAlignmentId],
  );

  const tokenToAlignments = useMemo(() => {
    const mapping = new Map<string, Alignment[]>();
    activeAlignments.forEach((alignment) => {
      alignment.source_token_ids.forEach((alignmentTokenId) => {
        mapping.set(alignmentTokenId, [...(mapping.get(alignmentTokenId) ?? []), alignment]);
      });
    });
    return mapping;
  }, [activeAlignments]);

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
      (spanToAlignments.get(spanId) ?? []).forEach((alignment) => alignment.source_token_ids.forEach((alignmentTokenId) => ids.add(alignmentTokenId)));
    });
    if (hoveredSpanId) {
      (spanToAlignments.get(hoveredSpanId) ?? []).forEach((alignment) => alignment.source_token_ids.forEach((alignmentTokenId) => ids.add(alignmentTokenId)));
    }
    activeAlignment?.source_token_ids.forEach((alignmentTokenId) => ids.add(alignmentTokenId));
    return [...ids];
  }, [activeAlignment, hoveredSpanId, selectedTokenIds, selectedSpanIds, spanToAlignments]);

  const highlightedSpanIds = useMemo(() => {
    const ids = new Set<string>(selectedSpanIds);
    selectedTokenIds.forEach((selectedTokenId) => {
      (tokenToAlignments.get(selectedTokenId) ?? []).forEach((alignment) => alignment.target_span_ids.forEach((spanId) => ids.add(spanId)));
    });
    if (hoveredTokenId) {
      (tokenToAlignments.get(hoveredTokenId) ?? []).forEach((alignment) => alignment.target_span_ids.forEach((spanId) => ids.add(spanId)));
    }
    activeAlignment?.target_span_ids.forEach((spanId) => ids.add(spanId));
    return [...ids];
  }, [activeAlignment, hoveredTokenId, selectedSpanIds, selectedTokenIds, tokenToAlignments]);

  const cloudNodes = cloudQuery.data?.nodes ?? visualFlow?.cloud_nodes ?? [];
  const activeCloudNode = useMemo(
    () => cloudNodes.find((node) => node.node_id === selectedCloudNodeId) ?? retrievalQuery.data?.node ?? null,
    [cloudNodes, retrievalQuery.data?.node, selectedCloudNodeId],
  );

  const retrievalHitsByUnit = useMemo(() => {
    const grouped = new Map<string, RetrievalHit[]>();
    (retrievalQuery.data?.hits ?? []).forEach((hit) => {
      grouped.set(hit.unit_id, [...(grouped.get(hit.unit_id) ?? []), hit]);
    });
    return grouped;
  }, [retrievalQuery.data?.hits]);

  useEffect(() => {
    updateWorkbenchUi({
      hoveredTokenId: null,
      hoveredSpanId: null,
      selectedTokenIds: [],
      selectedSpanIds: [],
      selectedAlignmentId: null,
    });
  }, [selectedUnitId, activeLayer]);

  useEffect(() => {
    setSelectedCloudNodeId(null);
  }, [selectedPsalmId]);

  useEffect(() => {
    if (!selectablePsalms.length) {
      return;
    }
    const nextPsalm = getDefaultPsalmSelection(selectablePsalms, selectedPsalmId);
    if (!nextPsalm) {
      return;
    }
    const nextUnitId = nextPsalm.unit_ids[0] ?? null;
    if (nextPsalm.psalm_id !== selectedPsalmId || !workbenchSelection.unitId || !nextPsalm.unit_ids.includes(workbenchSelection.unitId)) {
      updateWorkbenchSelection({
        psalmId: nextPsalm.psalm_id,
        unitId: nextUnitId,
      });
    }
  }, [selectablePsalms, selectedPsalmId, updateWorkbenchSelection, workbenchSelection.unitId]);

  useEffect(() => {
    if (!currentPsalm) {
      return;
    }
    if (!selectedUnitId || !currentPsalm.unit_ids.includes(selectedUnitId)) {
      updateWorkbenchSelection({ unitId: currentPsalm.unit_ids[0] ?? null });
    }
  }, [currentPsalm, selectedUnitId, updateWorkbenchSelection]);

  useEffect(() => {
    if (activeLayer !== selectedWorkflowLayer) {
      updateWorkbenchSelection({ layer: selectedWorkflowLayer });
    }
  }, [activeLayer, selectedWorkflowLayer, updateWorkbenchSelection]);

  useEffect(() => {
    if (!selectedAlignmentId) {
      return;
    }
    if (!activeAlignments.some((alignment) => alignment.alignment_id === selectedAlignmentId)) {
      updateWorkbenchUi({ selectedAlignmentId: null });
    }
  }, [activeAlignments, selectedAlignmentId]);

  useEffect(() => {
    if (!activeAlignment) {
      return;
    }
    updateWorkbenchUi({
      selectedTokenIds: activeAlignment.source_token_ids,
      selectedSpanIds: activeAlignment.target_span_ids,
    });
  }, [activeAlignment]);

  useEffect(() => {
    setPinOverrideTokenId(undefined);
  }, [pinnedTokenId]);

  useEffect(() => {
    if (pinnedLexicalCard?.token_id && workbenchUi.pinnedTokenId === null) {
      updateWorkbenchUi({ pinnedTokenId: pinnedLexicalCard.token_id });
    }
  }, [pinnedLexicalCard?.token_id]);

  useEffect(() => {
    if (tokenCard) {
      setDisplayedTokenCard(tokenCard);
      return;
    }
    if (!effectivePinnedTokenId && !hoveredTokenId) {
      setDisplayedTokenCard(undefined);
    }
  }, [effectivePinnedTokenId, hoveredTokenId, tokenCard]);

  useEffect(() => {
    if (!unit) {
      return;
    }
    const renderingIds = new Set(unit.renderings.map((rendering) => rendering.rendering_id));
    const patch: {
      compareLeftId?: string | null;
      compareRightId?: string | null;
    } = {};
    if (compareLeftId && !renderingIds.has(compareLeftId)) {
      patch.compareLeftId = null;
    }
    if (compareRightId && !renderingIds.has(compareRightId)) {
      patch.compareRightId = null;
    }
    if (Object.keys(patch).length > 0) {
      updateWorkbenchUi(patch);
    }
  }, [compareLeftId, compareRightId, unit, updateWorkbenchUi]);

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
    const nextPsalm = selectablePsalms.find((psalm: Psalm) => psalm.psalm_id === nextPsalmId);
    updateWorkbenchSelection({
      psalmId: nextPsalmId,
      unitId: nextPsalm?.unit_ids[0] ?? null,
    });
  };

  const handleUnitChange = (event: ChangeEvent<HTMLSelectElement>) => {
    updateWorkbenchSelection({ unitId: event.target.value });
  };

  const handleNavigateToUnit = (unitId: string, psalmId: string) => {
    updateWorkbenchSelection({ psalmId, unitId });
  };

  const handleGranularityChange = (event: ChangeEvent<HTMLSelectElement>) => {
    updateWorkbenchSelection({ granularity: event.target.value as 'colon' | 'verse' });
  };

  const handlePinToken = (nextTokenId: string) => {
    const tokenIdToPersist = effectivePinnedTokenId === nextTokenId ? null : nextTokenId;
    setPinOverrideTokenId(tokenIdToPersist);
    updateWorkbenchUi({ pinnedTokenId: tokenIdToPersist });
    setPinnedLexicalCard.mutate(tokenIdToPersist);
  };

  const handleUnpinToken = () => {
    setPinOverrideTokenId(null);
    updateWorkbenchUi({ pinnedTokenId: null });
    setPinnedLexicalCard.mutate(null);
  };

  const ensureSelectedUnit = (unitId: string) => {
    if (selectedUnitId !== unitId) {
      updateWorkbenchSelection({ unitId });
    }
  };

  const handleToggleToken = (unitId: string, nextTokenId: string) => {
    ensureSelectedUnit(unitId);
    toggleWorkbenchTokenSelection(nextTokenId);
  };

  const handleToggleSpan = (unitId: string, spanId: string) => {
    ensureSelectedUnit(unitId);
    toggleWorkbenchSpanSelection(spanId);
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

  return (
    <main className="workbench-shell">
      <header className="topbar">
        <div>
          <h1>{project?.title ?? 'Psalms Copyleft Workbench'}</h1>
          <p className="subtle">Visual Hebrew-to-literal flow with phrase and concept retrieval.</p>
        </div>
        <div className="topbar-controls">
          <label className="compact-field">
            <span>Psalm</span>
            <select value={effectivePsalmId ?? ''} onChange={handlePsalmChange}>
              {selectablePsalms.map((psalm: Psalm) => (
                <option key={psalm.psalm_id} value={psalm.psalm_id}>
                  {psalm.title}
                </option>
              ))}
            </select>
          </label>
          <label className="compact-field">
            <span>Unit</span>
            <select value={selectedUnitId ?? ''} onChange={handleUnitChange}>
              {currentPsalm?.unit_ids.map((unitIdOption) => (
                <option key={unitIdOption} value={unitIdOption}>
                  {unitIdOption}
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
          <label className="compact-field">
            <span>Workflow layer</span>
            <select value={selectedWorkflowLayer} onChange={(event) => updateWorkbenchSelection({ layer: event.target.value as typeof activeLayer })}>
              {selectableLayers.map((layer) => (
                <option key={layer} value={layer}>
                  {layer}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>
      <section className="status-strip">
        <span className="status-pill">Human review required for canonical promotion</span>
        <span className="status-pill">Divine name policy: {project?.divine_name_policy}</span>
        <span className="status-pill">Retrieval: {visualFlow?.embedding_model ?? 'loading'} </span>
        <span className="status-pill warning">Warnings: {(concerns?.open_drift_flags.length ?? 0) + (concerns?.uncovered_tokens.length ?? 0)}</span>
        {unitError ? <span className="status-pill warning">Unit load failed: {(unitError as Error).message}</span> : null}
      </section>
      <section className="visual-cloud-panel">
        <div className="horizontal-between visual-cloud-header">
          <div>
            <h2>Phrase And Concept Cloud</h2>
            <p className="subtle">Choose a node to drive the literal-first right pane. Same-Psalm hits are ranked ahead of cross-Psalm support.</p>
          </div>
          {activeCloudNode ? (
            <button type="button" className="tab" onClick={() => setSelectedCloudNodeId(null)}>
              Clear filter
            </button>
          ) : null}
        </div>
        <div className="cloud-band" aria-label="Phrase and concept cloud">
          {cloudNodes.map((node: CloudNode) => (
            <button
              key={node.node_id}
              type="button"
              className={`cloud-node cloud-node-${node.kind} ${selectedCloudNodeId === node.node_id ? 'active' : ''}`}
              style={{ fontSize: `${1 + Math.min(node.weight * 0.09, 1.1)}rem` }}
              onClick={() => setSelectedCloudNodeId((existing) => (existing === node.node_id ? null : node.node_id))}
            >
              <span>{node.label}</span>
              <small>{node.support_count}</small>
            </button>
          ))}
        </div>
        <div className="visual-cloud-summary subtle">
          {activeCloudNode
            ? `${activeCloudNode.label} selected · ${retrievalQuery.data?.hits.length ?? 0} ranked phrase/rendering hits`
            : 'No cloud node selected. The right pane is showing the default literal-first flow for the selected Psalm.'}
        </div>
      </section>
      <section className="workspace-grid">
        <div className="scroll-panel" ref={hebrewRef} onScroll={() => syncScroll('hebrew')}>
          <section className="pane pane-hebrew">
            <header className="pane-header">
              <h2>Hebrew Source</h2>
              <span className="subtle">Full Psalm canvas with the active unit pinned into inspector and workflow tools.</span>
            </header>
            <div className="visual-unit-list">
              {visualFlow?.units.map((visualUnit: VisualFlowUnit) => {
                const selected = visualUnit.unit_id === selectedUnitId;
                return (
                  <article key={visualUnit.unit_id} className={`flow-unit-card ${selected ? 'active' : ''}`}>
                    <button type="button" className="flow-unit-header" onClick={() => ensureSelectedUnit(visualUnit.unit_id)}>
                      <strong>{visualUnit.ref}</strong>
                      <span className="subtle">{visualUnit.unit_id}</span>
                    </button>
                    <div className="hebrew-token-grid" dir="rtl">
                      {visualUnit.tokens.map((token: Token) => {
                        const active = selected && tokenId === token.token_id;
                        const linked = selected && highlightedTokenIds.includes(token.token_id);
                        const tokenSelected = selected && selectedTokenIds.includes(token.token_id);
                        return (
                          <button
                            key={token.token_id}
                            className={`hebrew-token ${active ? 'active' : ''} ${linked ? 'linked' : ''} ${tokenSelected ? 'selected' : ''}`}
                            onMouseEnter={() => {
                              ensureSelectedUnit(visualUnit.unit_id);
                              updateWorkbenchUi({ hoveredTokenId: token.token_id });
                            }}
                            onMouseLeave={() => updateWorkbenchUi({ hoveredTokenId: null })}
                            onClick={() => {
                              handleToggleToken(visualUnit.unit_id, token.token_id);
                              handlePinToken(token.token_id);
                            }}
                            type="button"
                            title={`${token.token_id} • ${token.surface} • ${token.lemma} • ${token.strong}`}
                            aria-pressed={tokenSelected}
                          >
                            <span className="surface">{token.surface}</span>
                            <span className="token-meta">{token.token_id}</span>
                          </button>
                        );
                      })}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        </div>
        <div className="scroll-panel" ref={englishRef} onScroll={() => syncScroll('english')}>
          <section className="pane pane-english">
            <header className="pane-header">
              <h2>Layered English Flow</h2>
              <span className="subtle">The selected workflow layer stays active; when that layer is missing, the nearest populated audited layer is shown instead.</span>
            </header>
            {unit && selectedUnitLayerState.notice ? <p className="subtle">{selectedUnitLayerState.notice}</p> : null}
            <div className="visual-unit-list">
              {visualFlow?.units.map((visualUnit: VisualFlowUnit) => {
                const selected = visualUnit.unit_id === selectedUnitId;
                const contentUnit = unitMap.get(visualUnit.unit_id);
                const layerState = resolveLayerState(contentUnit, activeLayer);
                const renderedItems = sortRenderingsByStatus(
                  (contentUnit?.renderings ?? []).filter((rendering) => rendering.layer === layerState.renderLayer),
                );
                const retrievalHits = retrievalHitsByUnit.get(visualUnit.unit_id) ?? [];
                return (
                  <article key={visualUnit.unit_id} className={`flow-unit-card flow-unit-card-translation ${selected ? 'active' : ''}`}>
                    <button type="button" className="flow-unit-header" onClick={() => ensureSelectedUnit(visualUnit.unit_id)}>
                      <strong>{visualUnit.ref}</strong>
                      <span className="subtle">{layerState.renderLayer ?? 'No rendered layer'}</span>
                    </button>
                    {layerState.notice ? <p className="subtle">{layerState.notice}</p> : null}
                    {renderedItems.length > 0 ? (
                      renderedItems.map((rendering) => (
                        <div key={rendering.rendering_id} className={`rendering-card ${selected ? 'linked' : ''}`}>
                          <div className="horizontal-between">
                            <strong>{rendering.layer}</strong>
                            <span className="subtle">{rendering.status}</span>
                          </div>
                          <p className="rendering-text">{rendering.text}</p>
                          <div className="rendering-span-row" aria-label={`Rendering spans for ${rendering.rendering_id}`}>
                            {rendering.target_spans.map((span: RenderingSpan) => {
                              const linked = selected && highlightedSpanIds.includes(span.span_id);
                              const spanSelected = selected && selectedSpanIds.includes(span.span_id);
                              const active = selected && hoveredSpanId === span.span_id;
                              return (
                                <button
                                  key={span.span_id}
                                  type="button"
                                  className={`rendering-span ${linked ? 'linked' : ''} ${spanSelected ? 'selected' : ''} ${active ? 'active' : ''}`}
                                  onMouseEnter={() => {
                                    ensureSelectedUnit(visualUnit.unit_id);
                                    updateWorkbenchUi({ hoveredSpanId: span.span_id });
                                  }}
                                  onMouseLeave={() => updateWorkbenchUi({ hoveredSpanId: null })}
                                  onClick={() => handleToggleSpan(visualUnit.unit_id, span.span_id)}
                                  aria-pressed={spanSelected}
                                  title={span.span_id}
                                >
                                  {span.text}
                                </button>
                              );
                            })}
                          </div>
                          <div className="inline-actions">
                            <button type="button" className="tab" onClick={() => updateWorkbenchUi({ compareLeftId: rendering.rendering_id })}>
                              Compare left
                            </button>
                            <button type="button" className="tab" onClick={() => updateWorkbenchUi({ compareRightId: rendering.rendering_id })}>
                              Compare right
                            </button>
                            {rendering.status === 'canonical' ? (
                              <button type="button" className="tab" onClick={() => demoteRendering.mutate(rendering.rendering_id)}>
                                Demote
                              </button>
                            ) : (
                              <>
                                <button type="button" className="tab" onClick={() => handleAcceptAlternate(rendering.rendering_id)}>
                                  Accept
                                </button>
                                <button type="button" className="tab" onClick={() => handlePromoteAlternate(rendering.rendering_id)}>
                                  Promote
                                </button>
                                <button type="button" className="tab" onClick={() => handleDeprecateAlternate(rendering.rendering_id)}>
                                  Deprecate
                                </button>
                                <button type="button" className="tab" onClick={() => handleRejectAlternate(rendering.rendering_id)}>
                                  Reject
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="empty-state">No translation candidate available for this unit yet.</p>
                    )}
                    <div className="support-row" aria-label={`Supporting nodes for ${visualUnit.unit_id}`}>
                      {visualUnit.supporting_nodes.map((node) => (
                        <button key={node.node_id} type="button" className="tag support-tag" onClick={() => setSelectedCloudNodeId(node.node_id)}>
                          {node.kind}: {node.label}
                        </button>
                      ))}
                    </div>
                    {selectedCloudNodeId ? (
                      <div className="retrieval-stack">
                        <div className="horizontal-between">
                          <strong>Retrieved support</strong>
                          <span className="subtle">{retrievalHits.length} hit(s)</span>
                        </div>
                        {retrievalHits.length > 0 ? (
                          retrievalHits.slice(0, 3).map((hit) => <RetrievedHit key={hit.hit_id} hit={hit} onCompare={(renderingId) => updateWorkbenchUi({ compareRightId: renderingId })} />)
                        ) : (
                          <p className="empty-state">No ranked matches for this unit under the active cloud node.</p>
                        )}
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </section>
        </div>
        <InspectorRail tokenCard={displayedTokenCard} unit={unit} project={project} concerns={concerns} onUnpinToken={handleUnpinToken} />
      </section>
      <BottomDrawer
        unit={unit}
        concerns={concerns}
        tokenCard={displayedTokenCard}
        concordanceSeed={displayedTokenCard?.lemma ?? undefined}
        tab={workbenchUi.drawerTab}
        onTabChange={(tab) => updateWorkbenchUi({ drawerTab: tab })}
        onNavigateToUnit={handleNavigateToUnit}
        activeLayer={activeLayer}
        resolvedLayer={selectedUnitLayerState.renderLayer}
        layerNotice={selectedUnitLayerState.notice}
        selectableLayers={selectableLayers}
        selectedTokenIds={selectedTokenIds}
        selectedSpanIds={selectedSpanIds}
        selectedAlignmentId={selectedAlignmentId}
        onSelectedAlignmentChange={(alignmentId) => updateWorkbenchUi({ selectedAlignmentId: alignmentId })}
        onClearAlignmentSelection={clearWorkbenchSelections}
        compareLeftId={compareLeftId}
        compareRightId={compareRightId}
        onCompareLeftChange={(renderingId) => updateWorkbenchUi({ compareLeftId: renderingId })}
        onCompareRightChange={(renderingId) => updateWorkbenchUi({ compareRightId: renderingId })}
      />
    </main>
  );
}

function RetrievedHit({ hit, onCompare }: { hit: RetrievalHit; onCompare: (renderingId: string) => void }) {
  return (
    <article className="retrieval-hit-card">
      <div className="horizontal-between">
        <strong>{hit.scope === 'same_psalm' ? hit.ref : `${hit.ref} · cross-Psalm`}</strong>
        <span className="subtle">score {hit.explanation.final_score.toFixed(2)}</span>
      </div>
      <p className="result-snippet">{hit.label}</p>
      <div className="result-meta">
        <span>{hit.layer}</span>
        <span>{hit.status}</span>
        {hit.rendering_id ? (
          <button type="button" className="link-button" onClick={() => onCompare(hit.rendering_id!)}>
            Send to compare
          </button>
        ) : null}
      </div>
      <p className="subtle">
        vector {hit.explanation.vector_score.toFixed(2)} · overlap {hit.explanation.phrase_concept_overlap.toFixed(2)} · literal priority {hit.explanation.literal_priority.toFixed(2)}
      </p>
    </article>
  );
}
