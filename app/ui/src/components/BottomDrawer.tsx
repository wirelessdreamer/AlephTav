import { useEffect, useMemo, useState } from 'react';
import type { ChangeEvent } from 'react';

import {
  useAddAlternate,
  useAdvancedSearch,
  useAlternates,
  useConcordance,
  useCreateAlignment,
  useCreateRendering,
  useDeleteAlignment,
  useExportRelease,
  usePromoteRendering,
  useProject,
  useReviewAction,
  useRenderingComparison,
  useSearchPreset,
  useUpdateAlignment,
  useUnitWitnesses,
} from '../hooks/useWorkbench';
import { getPreferredSelectableLayer, getSelectableLayers } from '../lib/layers';
import type { Alignment, DrawerTab, Layer, OpenConcerns, TokenCard, Unit } from '../types';
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
  tab: DrawerTab;
  onTabChange: (tab: DrawerTab) => void;
  activeLayer: Layer;
  resolvedLayer: Layer | null;
  layerNotice: string | null;
  selectableLayers: Layer[];
  selectedTokenIds: string[];
  selectedSpanIds: string[];
  selectedAlignmentId: string | null;
  onSelectedAlignmentChange: (alignmentId: string | null) => void;
  onClearAlignmentSelection: () => void;
  onNavigateToUnit: (unitId: string, psalmId: string) => void;
  compareLeftId: string | null;
  compareRightId: string | null;
  onCompareLeftChange: (renderingId: string | null) => void;
  onCompareRightChange: (renderingId: string | null) => void;
}

const alternateFilters = [
  ['most_literal', 'Most literal'],
  ['best_lyric_flow', 'Best lyric flow'],
  ['best_meter_fit', 'Best meter fit'],
  ['best_imagery_preservation', 'Best imagery preservation'],
  ['formal', 'Formal'],
  ['contemporary', 'Contemporary'],
] as const;

export function BottomDrawer({
  unit,
  concerns,
  tokenCard,
  concordanceSeed,
  tab,
  onTabChange,
  onNavigateToUnit,
  activeLayer,
  resolvedLayer,
  layerNotice,
  selectableLayers,
  selectedTokenIds,
  selectedSpanIds,
  selectedAlignmentId,
  onSelectedAlignmentChange,
  onClearAlignmentSelection,
  compareLeftId,
  compareRightId,
  onCompareLeftChange,
  onCompareRightChange,
}: BottomDrawerProps) {
  const [concordanceField, setConcordanceField] = useState('lemma');
  const [concordanceQuery, setConcordanceQuery] = useState(concordanceSeed ?? '');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchScope, setSearchScope] = useState<SearchScope>('all');
  const [includeWitnesses, setIncludeWitnesses] = useState(false);
  const [presetName, setPresetName] = useState<PresetName>(null);
  const [releaseId, setReleaseId] = useState('');
  const [alignmentSpanText, setAlignmentSpanText] = useState('');
  const [alignmentType, setAlignmentType] = useState('direct');
  const [alignmentConfidence, setAlignmentConfidence] = useState('0.9');
  const [alternateLayer, setAlternateLayer] = useState<Layer>('lyric');
  const [alternateText, setAlternateText] = useState('');
  const [selectedAlternateId, setSelectedAlternateId] = useState('');
  const [workflowMessage, setWorkflowMessage] = useState('');
  const [alternateFilter, setAlternateFilter] = useState<string>('');
  const [releaseApprovedOnly, setReleaseApprovedOnly] = useState(false);
  const [alternateProposalText, setAlternateProposalText] = useState('');
  const [alternateRationale, setAlternateRationale] = useState('');
  const [alternateStyleGoal, setAlternateStyleGoal] = useState('');
  const [alternateMetricProfile, setAlternateMetricProfile] = useState('');
  const [alternateTags, setAlternateTags] = useState('');
  const [reviewerName, setReviewerName] = useState('ui-reviewer');
  const [reviewerRole, setReviewerRole] = useState('alignment reviewer');
  const [reviewNotes, setReviewNotes] = useState('');

  const { data: project } = useProject();
  const concordance = useConcordance(concordanceQuery, concordanceField);
  const advancedSearch = useAdvancedSearch(searchQuery, searchScope, includeWitnesses);
  const preset = useSearchPreset(presetName, presetName === 'units_changed_since_release' ? releaseId : undefined);
  const witnesses = useUnitWitnesses(unit?.unit_id ?? null);
  const createAlignment = useCreateAlignment(unit?.unit_id ?? null);
  const deleteAlignment = useDeleteAlignment(unit?.unit_id ?? null);
  const updateAlignment = useUpdateAlignment(unit?.unit_id ?? null);
  const createRendering = useCreateRendering(unit?.unit_id ?? null);
  const reviewAction = useReviewAction(unit?.unit_id ?? null);
  const promoteRendering = usePromoteRendering(unit?.unit_id ?? null);
  const exportRelease = useExportRelease();
  const alternatesLayer = resolvedLayer ?? activeLayer;
  const alternates = useAlternates(unit?.unit_id ?? null, alternatesLayer, alternateFilter || undefined, releaseApprovedOnly);
  const addAlternate = useAddAlternate(unit?.unit_id ?? null);
  const comparison = useRenderingComparison(unit?.unit_id ?? null, compareLeftId, compareRightId);
  const resolvedSelectableLayers = useMemo(() => getSelectableLayers(selectableLayers), [selectableLayers]);
  const selectedAlternateLayer = useMemo(
    () => getPreferredSelectableLayer(alternateLayer, resolvedSelectableLayers),
    [alternateLayer, resolvedSelectableLayers],
  );

  useEffect(() => {
    if (!concordanceSeed) {
      return;
    }
    setConcordanceQuery((existing) => existing || concordanceSeed);
  }, [concordanceSeed]);

  useEffect(() => {
    if (alternateLayer !== selectedAlternateLayer) {
      setAlternateLayer(selectedAlternateLayer);
    }
  }, [alternateLayer, selectedAlternateLayer]);

  const unresolvedDriftCount = concerns?.open_drift_flags.filter((item) => item.unit_id === unit?.unit_id).length ?? 0;
  const uncoveredCount = concerns?.uncovered_tokens.filter((item) => item.unit_id === unit?.unit_id).length ?? 0;
  const unalignedSpanCount = concerns?.unaligned_spans.filter((item) => item.unit_id === unit?.unit_id).length ?? 0;
  const lowConfidenceCount = concerns?.low_confidence_alignments.filter((item) => item.unit_id === unit?.unit_id).length ?? 0;
  const activeLayerCanonical = unit?.renderings.find((item) => item.layer === activeLayer && item.status === 'canonical') ?? null;
  const resolvedLayerCanonical = resolvedLayer ? unit?.renderings.find((item) => item.layer === resolvedLayer && item.status === 'canonical') ?? null : null;
  const availableCompareRenderings = unit?.renderings ?? [];

  const handleNavigate = (unitId: string, psalmId: string) => {
    onNavigateToUnit(unitId, psalmId);
  };

  const handlePreset = (nextPreset: PresetName) => {
    setPresetName(nextPreset);
    if (tab !== 'search') {
      onTabChange('search');
    }
  };

  const workflowAlternates = unit?.renderings.filter((item) => item.status !== 'canonical') ?? [];
  const workflowAlternatesForResolvedLayer = workflowAlternates.filter((item) => item.layer === alternatesLayer);
  const workflowAlignments = unit?.alignments.filter((item) => item.layer === activeLayer) ?? [];
  const selectedAlternate = workflowAlternatesForResolvedLayer.find((item) => item.rendering_id === selectedAlternateId) ?? null;
  const selectedAlignment = workflowAlignments.find((item) => item.alignment_id === selectedAlignmentId) ?? null;

  useEffect(() => {
    const alternateIds = new Set(workflowAlternatesForResolvedLayer.map((item) => item.rendering_id));
    if (selectedAlternateId && alternateIds.has(selectedAlternateId)) {
      return;
    }
    setSelectedAlternateId(workflowAlternatesForResolvedLayer[0]?.rendering_id ?? '');
  }, [selectedAlternateId, workflowAlternatesForResolvedLayer]);

  useEffect(() => {
    if (!unit) {
      return;
    }
    const renderingIds = new Set(unit.renderings.map((item) => item.rendering_id));
    const nextLeftId = compareLeftId && renderingIds.has(compareLeftId)
      ? compareLeftId
      : (activeLayerCanonical ?? resolvedLayerCanonical ?? unit.renderings[0] ?? null)?.rendering_id ?? null;
    if (nextLeftId !== compareLeftId) {
      onCompareLeftChange(nextLeftId);
    }
  }, [activeLayerCanonical, compareLeftId, onCompareLeftChange, resolvedLayerCanonical, unit]);

  useEffect(() => {
    if (!unit) {
      return;
    }
    const renderingIds = new Set(unit.renderings.map((item) => item.rendering_id));
    if (compareRightId && renderingIds.has(compareRightId)) {
      return;
    }
    const nextRightId =
      workflowAlternatesForResolvedLayer[0]?.rendering_id
      ?? availableCompareRenderings.find((item) => item.layer === alternatesLayer && item.rendering_id !== compareLeftId)?.rendering_id
      ?? availableCompareRenderings.find((item) => item.rendering_id !== compareLeftId)?.rendering_id
      ?? null;
    if (nextRightId !== compareRightId) {
      onCompareRightChange(nextRightId);
    }
  }, [
    alternatesLayer,
    availableCompareRenderings,
    compareLeftId,
    compareRightId,
    onCompareRightChange,
    unit,
    workflowAlternatesForResolvedLayer,
  ]);

  useEffect(() => {
    if (selectedAlignment) {
      setAlignmentSpanText(selectedAlignment.notes ?? '');
      setAlignmentType(selectedAlignment.alignment_type);
      setAlignmentConfidence(String(selectedAlignment.confidence));
      return;
    }
    setAlignmentType(selectedTokenIds.length > 1 ? 'grouped' : 'direct');
    setAlignmentConfidence('0.9');
    setAlignmentSpanText('');
  }, [selectedAlignment, selectedTokenIds.length, activeLayer]);

  const handleCreateAlignment = async () => {
    if (!unit || selectedTokenIds.length === 0 || selectedSpanIds.length === 0) return;
    const spanText = alignmentSpanText.trim() || `Linked ${activeLayer} span`;
    const payload = {
      unit_id: unit.unit_id,
      layer: activeLayer,
      source_token_ids: selectedTokenIds,
      target_span_ids: selectedSpanIds,
      alignment_type: alignmentType,
      confidence: Number(alignmentConfidence),
      notes: spanText,
    };
    try {
      const response = (await createAlignment.mutateAsync(payload)) as { alignment_id: string };
      setWorkflowMessage(`Alignment created: ${response.alignment_id}`);
      onSelectedAlignmentChange(response.alignment_id);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : 'Alignment creation failed');
    }
  };

  const handleUpdateAlignment = async () => {
    if (!selectedAlignment || selectedTokenIds.length === 0 || selectedSpanIds.length === 0) {
      return;
    }
    try {
      const response = (await updateAlignment.mutateAsync({
        alignmentId: selectedAlignment.alignment_id,
        payload: {
          layer: activeLayer,
          source_token_ids: selectedTokenIds,
          target_span_ids: selectedSpanIds,
          alignment_type: alignmentType,
          confidence: Number(alignmentConfidence),
          notes: alignmentSpanText.trim(),
        },
      })) as Alignment;
      setWorkflowMessage(`Alignment updated: ${response.alignment_id}`);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : 'Alignment update failed');
    }
  };

  const handleDeleteSelectedAlignment = async () => {
    const target = selectedAlignment ?? workflowAlignments[workflowAlignments.length - 1];
    if (!target) return;
    try {
      await deleteAlignment.mutateAsync(target.alignment_id);
      onClearAlignmentSelection();
      setWorkflowMessage(`Alignment deleted: ${target.alignment_id}`);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : 'Alignment deletion failed');
    }
  };

  const handleAddAlternate = async () => {
    if (!unit || !alternateText.trim()) return;
    try {
      const rendering = (await createRendering.mutateAsync({
        layer: selectedAlternateLayer,
        text: alternateText.trim(),
        status: 'proposed',
        rationale: 'UI workflow alternate',
        created_by: 'ui-workflow',
        style_tags: [selectedAlternateLayer, 'workflow'],
      })) as { rendering_id: string };
      setWorkflowMessage(`Alternate added: ${rendering.rendering_id}`);
      setAlternateText('');
      setSelectedAlternateId(rendering.rendering_id);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : 'Alternate creation failed');
    }
  };

  const reviewPayload = {
    reviewer: reviewerName.trim() || 'ui-reviewer',
    reviewer_role: reviewerRole,
    notes: reviewNotes.trim(),
  };

  const handleReviewAction = async (action: 'approve' | 'request-changes' | 'accept-alternate' | 'reject') => {
    if (!selectedAlternateId) return;
    try {
      await reviewAction.mutateAsync({ renderingId: selectedAlternateId, action, payload: reviewPayload });
      setWorkflowMessage(`Review action recorded: ${action}`);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : 'Review action failed');
    }
  };

  const handlePromoteAlternate = async () => {
    if (!selectedAlternateId) return;
    try {
      const response = (await promoteRendering.mutateAsync({
        renderingId: selectedAlternateId,
        payload: { reviewer: reviewerName.trim() || 'ui-release', reviewer_role: reviewerRole },
      })) as { rendering_id: string };
      setWorkflowMessage(`Alternate promoted: ${response.rendering_id}`);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : 'Alternate promotion failed');
    }
  };

  const handleExportRelease = async () => {
    if (!releaseId.trim()) return;
    try {
      const response = await exportRelease.mutateAsync({ release_id: releaseId.trim() });
      setWorkflowMessage(`Release exported: ${response.path}`);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : 'Release export failed');
    }
  };

  const handleProposeAlternate = () => {
    if (!alternateProposalText.trim() || !unit) {
      return;
    }
    addAlternate.mutate(
      {
        layer: activeLayer,
        text: alternateProposalText.trim(),
        rationale: alternateRationale.trim() || 'manual alternate proposal',
        style_goal: alternateStyleGoal.trim() || undefined,
        metric_profile: alternateMetricProfile.trim() || undefined,
        style_tags: alternateTags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
      },
      {
        onSuccess: (rendering) => {
          setAlternateProposalText('');
          setAlternateRationale('');
          onCompareRightChange(rendering.rendering_id);
          if (!compareLeftId && activeLayerCanonical) {
            onCompareLeftChange(activeLayerCanonical.rendering_id);
          }
        },
      },
    );
  };

  return (
    <section className="bottom-drawer">
      <header className="drawer-header">
        <div className="tab-row">
          {(['concordance', 'workflow', 'search', 'witnesses', 'audit', 'compare'] as DrawerTab[]).map((item) => (
            <button key={item} type="button" className={tab === item ? 'tab active' : 'tab'} onClick={() => onTabChange(item)}>
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
      {tab === 'workflow' ? (
        <div className="drawer-panel">
          <div className="result-grid workflow-grid">
            <article className="compare-card">
              <h4>Alignment editor</h4>
              <p className="subtle">Select Hebrew token(s) and English span(s), then create or revise an alignment for the active layer.</p>
              {layerNotice ? <p className="subtle">{layerNotice}</p> : null}
              <div className="mini-section">
                <strong>Selection</strong>
                <div className="tag-row">
                  {selectedTokenIds.map((tokenId) => (
                    <span key={tokenId} className="tag">
                      {tokenId}
                    </span>
                  ))}
                  {selectedSpanIds.map((spanId) => (
                    <span key={spanId} className="tag">
                      {spanId}
                    </span>
                  ))}
                  {!selectedTokenIds.length && !selectedSpanIds.length ? <span className="subtle">No tokens or spans selected yet.</span> : null}
                </div>
              </div>
              <label className="compact-field">
                <span>Alignment type</span>
                <select value={alignmentType} onChange={(event) => setAlignmentType(event.target.value)}>
                  <option value="direct">direct</option>
                  <option value="grouped">grouped</option>
                  <option value="idiom">idiom</option>
                  <option value="conceptual">conceptual</option>
                  <option value="editorial_expansion">editorial_expansion</option>
                  <option value="omission_accounted_for">omission_accounted_for</option>
                  <option value="uncertain">uncertain</option>
                </select>
              </label>
              <label className="compact-field">
                <span>Confidence</span>
                <input
                  aria-label="Alignment confidence"
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={alignmentConfidence}
                  onChange={(event) => setAlignmentConfidence(event.target.value)}
                />
              </label>
              <label className="compact-field">
                <span>Alignment notes</span>
                <input
                  aria-label="Alignment notes"
                  value={alignmentSpanText}
                  onChange={(event) => setAlignmentSpanText(event.target.value)}
                  placeholder={`Linked ${activeLayer} span`}
                />
              </label>
              <div className="inline-actions">
                <button
                  type="button"
                  className="tab"
                  onClick={() => void handleCreateAlignment()}
                  disabled={!selectedTokenIds.length || !selectedSpanIds.length}
                >
                  Create alignment
                </button>
                <button
                  type="button"
                  className="tab"
                  onClick={() => void handleUpdateAlignment()}
                  disabled={!selectedAlignmentId || !selectedTokenIds.length || !selectedSpanIds.length}
                >
                  Update alignment
                </button>
                <button type="button" className="tab" onClick={() => void handleDeleteSelectedAlignment()} disabled={!workflowAlignments.length}>
                  Delete selected alignment
                </button>
                <button type="button" className="tab" onClick={onClearAlignmentSelection}>
                  Clear selection
                </button>
              </div>
              <p className="subtle">Current {activeLayer} alignments: {workflowAlignments.length}</p>
              <div className="mini-section">
                <strong>Coverage</strong>
                <ul className="simple-list compact-list">
                  <li>{uncoveredCount} uncovered token(s)</li>
                  <li>{unalignedSpanCount} unaligned span(s)</li>
                  <li>{lowConfidenceCount} low-confidence alignment(s)</li>
                  <li>{unresolvedDriftCount} unresolved drift flag(s)</li>
                </ul>
              </div>
              <div className="mini-section">
                <strong>Existing alignments</strong>
                <ul className="simple-list compact-list">
                  {workflowAlignments.map((alignment) => (
                    <li key={alignment.alignment_id}>
                      <button
                        type="button"
                        className={selectedAlignmentId === alignment.alignment_id ? 'tab active' : 'tab'}
                        onClick={() => onSelectedAlignmentChange(alignment.alignment_id)}
                      >
                        {alignment.alignment_id} ({Math.round(alignment.confidence * 100)}%)
                      </button>
                    </li>
                  ))}
                  {!workflowAlignments.length ? <li className="empty-state">No alignments in this layer yet.</li> : null}
                </ul>
              </div>
            </article>
            <article className="compare-card">
              <h4>Add alternate</h4>
              <label className="compact-field">
                <span>Alternate layer</span>
                <select aria-label="Alternate layer" value={selectedAlternateLayer} onChange={(event) => setAlternateLayer(event.target.value as Layer)}>
                  {resolvedSelectableLayers.map((layer) => (
                    <option key={layer} value={layer}>
                      {layer}
                    </option>
                  ))}
                </select>
              </label>
              <label className="compact-field">
                <span>Alternate text</span>
                <input
                  aria-label="Alternate text"
                  value={alternateText}
                  onChange={(event) => setAlternateText(event.target.value)}
                  placeholder="Enter alternate rendering text"
                />
              </label>
              <button type="button" className="tab" onClick={() => void handleAddAlternate()} disabled={!alternateText.trim()}>
                Add alternate
              </button>
            </article>
            <article className="compare-card">
              <h4>Review actions</h4>
              <label className="compact-field">
                <span>Alternate rendering</span>
                <select
                  aria-label="Alternate rendering"
                  value={selectedAlternateId}
                  onChange={(event) => setSelectedAlternateId(event.target.value)}
                  disabled={!workflowAlternatesForResolvedLayer.length}
                >
                  {workflowAlternatesForResolvedLayer.map((item) => (
                    <option key={item.rendering_id} value={item.rendering_id}>
                      {item.rendering_id}
                    </option>
                  ))}
                </select>
              </label>
              <label className="compact-field">
                <span>Reviewer</span>
                <input value={reviewerName} onChange={(event) => setReviewerName(event.target.value)} placeholder="reviewer handle" />
              </label>
              <label className="compact-field">
                <span>Role</span>
                <select value={reviewerRole} onChange={(event) => setReviewerRole(event.target.value)}>
                  {(project?.review_policy.reviewer_roles ?? []).map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
              </label>
              <label className="compact-field">
                <span>Notes</span>
                <textarea value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} rows={3} placeholder="decision notes" />
              </label>
              <div className="inline-actions">
                <button type="button" className="tab" onClick={() => void handleReviewAction('approve')} disabled={!selectedAlternateId}>
                  Approve
                </button>
                <button type="button" className="tab" onClick={() => void handleReviewAction('request-changes')} disabled={!selectedAlternateId}>
                  Request changes
                </button>
                <button type="button" className="tab" onClick={() => void handleReviewAction('accept-alternate')} disabled={!selectedAlternateId}>
                  Accept as alternate
                </button>
                <button type="button" className="tab" onClick={() => void handleReviewAction('reject')} disabled={!selectedAlternateId}>
                  Reject
                </button>
                <button type="button" className="tab" onClick={() => void handlePromoteAlternate()} disabled={!selectedAlternateId}>
                  Promote to canonical
                </button>
              </div>
              <div className="warning-box">
                <div>Review status: {selectedAlternate?.review_signoff?.status ?? 'unreviewed'}</div>
                <div>
                  Alternate signoff: {selectedAlternate?.review_signoff?.alternate_approval_count ?? 0}/
                  {selectedAlternate?.review_signoff?.required_approvals?.alternate ?? project?.review_policy.alternate_required_approvals ?? 1}
                </div>
                <div>
                  Canonical signoff: {selectedAlternate?.review_signoff?.approval_count ?? 0}/
                  {selectedAlternate?.review_signoff?.required_approvals?.canonical ?? project?.review_policy.canonical_required_approvals ?? 2}
                </div>
                <div>Release signoff: {selectedAlternate?.review_signoff?.has_release_signoff ? 'recorded' : 'pending'}</div>
              </div>
            </article>
            <article className="compare-card">
              <h4>Export release</h4>
              <label className="compact-field">
                <span>Release id</span>
                <input aria-label="Release id" value={releaseId} onChange={(event) => setReleaseId(event.target.value)} placeholder="v0.1.0-ui" />
              </label>
              <button type="button" className="tab" onClick={() => void handleExportRelease()} disabled={!releaseId.trim()}>
                Export release
              </button>
            </article>
          </div>
          <div className="warning-box" aria-live="polite">
            <div>Workflow status</div>
            <div>{workflowMessage || 'No workflow action run yet.'}</div>
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
                  <li key={decision.decision_id}>{decision.timestamp} - {decision.reviewer_role} {decision.reviewer}: {decision.decision}</li>
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
            <h4>Compare left</h4>
            <label className="compact-field">
              <span>Rendering</span>
              <select value={compareLeftId ?? ''} onChange={(event) => onCompareLeftChange(event.target.value || null)}>
                <option value="">Select rendering</option>
                {availableCompareRenderings.map((item) => (
                  <option key={item.rendering_id} value={item.rendering_id}>
                    {item.layer} • {item.status} • {item.rendering_id}
                  </option>
                ))}
              </select>
            </label>
            {comparison.data?.left ? (
              <>
                <p className="subtle">{comparison.data.left.rendering_id}</p>
                <p>{comparison.data.left.text}</p>
              </>
            ) : (
              <p className="empty-state">Choose a left-side rendering.</p>
            )}
          </article>
          <article className="compare-card">
            <h4>Compare right</h4>
            <label className="compact-field">
              <span>Rendering</span>
              <select value={compareRightId ?? ''} onChange={(event) => onCompareRightChange(event.target.value || null)}>
                <option value="">Select rendering</option>
                {availableCompareRenderings.map((item) => (
                  <option key={item.rendering_id} value={item.rendering_id}>
                    {item.layer} • {item.status} • {item.rendering_id}
                  </option>
                ))}
              </select>
            </label>
            {comparison.data?.right ? (
              <>
                <p className="subtle">{comparison.data.right.rendering_id}</p>
                <p>{comparison.data.right.text}</p>
              </>
            ) : (
              <p className="empty-state">Choose a right-side rendering.</p>
            )}
          </article>
          <article className="compare-card">
            <h4>Compare notes</h4>
            {comparison.data ? (
              <>
                <p>{comparison.data.comparison.same_layer ? 'Same layer comparison' : 'Cross-layer comparison'}</p>
                <p className="subtle">
                  Left canonical: {comparison.data.comparison.left_is_canonical ? 'yes' : 'no'} • Right canonical: {comparison.data.comparison.right_is_canonical ? 'yes' : 'no'}
                </p>
                <div className="warning-box">
                  <div>Canonical vs alternate, alternate vs alternate, and layer vs layer are all supported.</div>
                  <div>Witness material remains isolated from canonical comparison state.</div>
                </div>
              </>
            ) : (
              <p className="empty-state">Pick any two renderings to compare side by side.</p>
            )}
          </article>
          <article className="compare-card">
            <h4>Alternate filters</h4>
            {layerNotice ? <p className="subtle">{layerNotice}</p> : null}
            <label className="compact-field">
              <span>View</span>
              <select value={alternateFilter} onChange={(event) => setAlternateFilter(event.target.value)}>
                <option value="">All alternates</option>
                {alternateFilters.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="checkbox-field">
              <input type="checkbox" checked={releaseApprovedOnly} onChange={(event) => setReleaseApprovedOnly(event.target.checked)} />
              <span>Release-approved only</span>
            </label>
            {resolvedLayer && resolvedLayer !== activeLayer ? <p className="subtle">Alternate list is showing {resolvedLayer} because {activeLayer} has no renderings for this unit.</p> : null}
            <ul className="simple-list">
              {alternates.data?.map((item) => (
                <li key={item.rendering_id} className="search-result-card">
                  <div className="horizontal-between">
                    <strong>{item.status}</strong>
                    <span className="subtle">{item.rendering_id}</span>
                  </div>
                  <p className="result-snippet">{item.text}</p>
                  <div className="result-meta">
                    <span>{item.layer}</span>
                    <button type="button" className="link-button" onClick={() => onCompareRightChange(item.rendering_id)}>
                      Send to compare
                    </button>
                  </div>
                </li>
              ))}
              {!alternates.data?.length ? <li className="empty-state">No alternates match the current filters.</li> : null}
            </ul>
          </article>
          <article className="compare-card">
            <h4>Add alternate</h4>
            <label className="compact-field">
              <span>Text</span>
              <textarea value={alternateProposalText} onChange={(event) => setAlternateProposalText(event.target.value)} rows={4} placeholder={`Add ${activeLayer} alternate text`} />
            </label>
            <label className="compact-field">
              <span>Rationale</span>
              <input value={alternateRationale} onChange={(event) => setAlternateRationale(event.target.value)} placeholder="Why this alternate should exist" />
            </label>
            <label className="compact-field">
              <span>Style goal</span>
              <input value={alternateStyleGoal} onChange={(event) => setAlternateStyleGoal(event.target.value)} placeholder="e.g. best_meter_fit" />
            </label>
            <label className="compact-field">
              <span>Metric profile</span>
              <input value={alternateMetricProfile} onChange={(event) => setAlternateMetricProfile(event.target.value)} placeholder="e.g. common_meter" />
            </label>
            <label className="compact-field">
              <span>Style tags</span>
              <input value={alternateTags} onChange={(event) => setAlternateTags(event.target.value)} placeholder="comma,separated,tags" />
            </label>
            <button type="button" className="tab" onClick={handleProposeAlternate}>
              Propose alternate
            </button>
          </article>
        </div>
      ) : null}
    </section>
  );
}
