import { useEffect, useState } from 'react';
import type { ChangeEvent } from 'react';

import {
  useAddAlternate,
  useAdvancedSearch,
  useApproveRendering,
  useAlternates,
  useConcordance,
  useCreateAlignment,
  useCreateRendering,
  useDeleteAlignment,
  useExportRelease,
  usePromoteRendering,
  useRenderingComparison,
  useSearchPreset,
  useUnitWitnesses,
} from '../hooks/useWorkbench';
import type { Layer, OpenConcerns, TokenCard, Unit } from '../types';

type DrawerTab = 'concordance' | 'workflow' | 'search' | 'witnesses' | 'audit' | 'compare';
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
  activeLayer: Layer;
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
  onNavigateToUnit,
  activeLayer,
  compareLeftId,
  compareRightId,
  onCompareLeftChange,
  onCompareRightChange,
}: BottomDrawerProps) {
  const [tab, setTab] = useState<DrawerTab>('concordance');
  const [concordanceField, setConcordanceField] = useState('lemma');
  const [concordanceQuery, setConcordanceQuery] = useState(concordanceSeed ?? '');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchScope, setSearchScope] = useState<SearchScope>('all');
  const [includeWitnesses, setIncludeWitnesses] = useState(false);
  const [presetName, setPresetName] = useState<PresetName>(null);
  const [releaseId, setReleaseId] = useState('');
  const [alignmentSpanText, setAlignmentSpanText] = useState('');
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

  const concordance = useConcordance(concordanceQuery, concordanceField);
  const advancedSearch = useAdvancedSearch(searchQuery, searchScope, includeWitnesses);
  const preset = useSearchPreset(presetName, presetName === 'units_changed_since_release' ? releaseId : undefined);
  const witnesses = useUnitWitnesses(unit?.unit_id ?? null);
  const createAlignment = useCreateAlignment(unit?.unit_id ?? null);
  const deleteAlignment = useDeleteAlignment(unit?.unit_id ?? null);
  const createRendering = useCreateRendering(unit?.unit_id ?? null);
  const approveRendering = useApproveRendering(unit?.unit_id ?? null);
  const promoteRendering = usePromoteRendering(unit?.unit_id ?? null);
  const exportRelease = useExportRelease();
  const alternates = useAlternates(unit?.unit_id ?? null, activeLayer, alternateFilter || undefined, releaseApprovedOnly);
  const addAlternate = useAddAlternate(unit?.unit_id ?? null);
  const comparison = useRenderingComparison(unit?.unit_id ?? null, compareLeftId, compareRightId);

  useEffect(() => {
    if (!concordanceSeed) {
      return;
    }
    setConcordanceQuery((existing) => existing || concordanceSeed);
  }, [concordanceSeed]);

  const unresolvedDriftCount = concerns?.open_drift_flags.filter((item) => item.unit_id === unit?.unit_id).length ?? 0;
  const uncoveredCount = concerns?.uncovered_tokens.filter((item) => item.unit_id === unit?.unit_id).length ?? 0;
  const activeLayerCanonical = unit?.renderings.find((item) => item.layer === activeLayer && item.status === 'canonical') ?? null;
  const availableCompareRenderings = unit?.renderings ?? [];

  const handleNavigate = (unitId: string, psalmId: string) => {
    onNavigateToUnit(unitId, psalmId);
  };

  const handlePreset = (nextPreset: PresetName) => {
    setPresetName(nextPreset);
    if (tab !== 'search') {
      setTab('search');
    }
  };

  const workflowAlternates = unit?.renderings.filter((item) => item.status !== 'canonical') ?? [];
  const workflowAlignments = unit?.alignments.filter((item) => item.layer === activeLayer) ?? [];

  useEffect(() => {
    if (!selectedAlternateId && workflowAlternates.length > 0) {
      setSelectedAlternateId(workflowAlternates[0].rendering_id);
    }
  }, [selectedAlternateId, workflowAlternates]);

  const handleCreateAlignment = async () => {
    if (!unit) return;
    const spanText = alignmentSpanText.trim() || `Linked ${activeLayer} span`;
    const payload = {
      unit_id: unit.unit_id,
      layer: activeLayer,
      source_token_ids: unit.token_ids,
      target_span_ids: [`spn.${unit.unit_id}.${activeLayer}.${workflowAlignments.length + 1}`],
      alignment_type: unit.token_ids.length > 1 ? 'grouped' : 'direct',
      confidence: 0.9,
      notes: spanText,
    };
    try {
      const response = (await createAlignment.mutateAsync(payload)) as { alignment_id: string };
      setWorkflowMessage(`Alignment created: ${response.alignment_id}`);
      setAlignmentSpanText('');
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : 'Alignment creation failed');
    }
  };

  const handleDeleteLatestAlignment = async () => {
    const latest = workflowAlignments[workflowAlignments.length - 1];
    if (!latest) return;
    try {
      await deleteAlignment.mutateAsync(latest.alignment_id);
      setWorkflowMessage(`Alignment deleted: ${latest.alignment_id}`);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : 'Alignment deletion failed');
    }
  };

  const handleAddAlternate = async () => {
    if (!unit || !alternateText.trim()) return;
    try {
      const rendering = (await createRendering.mutateAsync({
        layer: alternateLayer,
        text: alternateText.trim(),
        status: 'proposed',
        rationale: 'UI workflow alternate',
        created_by: 'ui-workflow',
        style_tags: [alternateLayer, 'workflow'],
      })) as { rendering_id: string };
      setWorkflowMessage(`Alternate added: ${rendering.rendering_id}`);
      setAlternateText('');
      setSelectedAlternateId(rendering.rendering_id);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : 'Alternate creation failed');
    }
  };

  const handlePromoteAlternate = async () => {
    if (!selectedAlternateId) return;
    try {
      await approveRendering.mutateAsync({
        renderingId: selectedAlternateId,
        payload: { reviewer: 'ui-reviewer-a', reviewer_role: 'alignment reviewer', notes: 'UI approval A' },
      });
      await approveRendering.mutateAsync({
        renderingId: selectedAlternateId,
        payload: { reviewer: 'ui-reviewer-b', reviewer_role: 'Hebrew reviewer', notes: 'UI approval B' },
      });
      const response = (await promoteRendering.mutateAsync({
        renderingId: selectedAlternateId,
        payload: { reviewer: 'ui-release', reviewer_role: 'release reviewer' },
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
            <button key={item} type="button" className={tab === item ? 'tab active' : 'tab'} onClick={() => setTab(item)}>
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
              <h4>Create alignment</h4>
              <p className="subtle">Create a quick alignment covering the current unit for the active layer.</p>
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
                <button type="button" className="tab" onClick={() => void handleCreateAlignment()}>
                  Create alignment
                </button>
                <button type="button" className="tab" onClick={() => void handleDeleteLatestAlignment()} disabled={!workflowAlignments.length}>
                  Delete latest alignment
                </button>
              </div>
              <p className="subtle">Current {activeLayer} alignments: {workflowAlignments.length}</p>
            </article>
            <article className="compare-card">
              <h4>Add alternate</h4>
              <label className="compact-field">
                <span>Alternate layer</span>
                <select aria-label="Alternate layer" value={alternateLayer} onChange={(event) => setAlternateLayer(event.target.value as Layer)}>
                  <option value="gloss">gloss</option>
                  <option value="literal">literal</option>
                  <option value="phrase">phrase</option>
                  <option value="concept">concept</option>
                  <option value="lyric">lyric</option>
                  <option value="metered_lyric">metered_lyric</option>
                  <option value="parallelism_lyric">parallelism_lyric</option>
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
              <h4>Promote alternate</h4>
              <label className="compact-field">
                <span>Alternate rendering</span>
                <select
                  aria-label="Alternate rendering"
                  value={selectedAlternateId}
                  onChange={(event) => setSelectedAlternateId(event.target.value)}
                  disabled={!workflowAlternates.length}
                >
                  {workflowAlternates.map((item) => (
                    <option key={item.rendering_id} value={item.rendering_id}>
                      {item.rendering_id}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" className="tab" onClick={() => void handlePromoteAlternate()} disabled={!selectedAlternateId}>
                Approve and promote alternate
              </button>
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
                  <li key={decision.decision_id}>{decision.timestamp} - {decision.reviewer_role}: {decision.decision}</li>
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
