export type Layer =
  | 'gloss'
  | 'literal'
  | 'phrase'
  | 'concept'
  | 'lyric'
  | 'metered_lyric'
  | 'parallelism_lyric';

export type DrawerTab = 'concordance' | 'workflow' | 'search' | 'witnesses' | 'source_map' | 'audit' | 'compare';

export interface Token {
  token_id: string;
  surface: string;
  normalized: string;
  transliteration: string | null;
  greek?: string | null;
  greek_strong?: string | null;
  lemma: string | null;
  strong: string | null;
  morph_code?: string | null;
  morph_readable: string | null;
  part_of_speech?: string | null;
  stem?: string | null;
  syntax_role: string | null;
  semantic_role: string | null;
  referent: string | null;
  word_sense: string | null;
  gloss_parts: string[];
  display_gloss: string | null;
  compiler_features: Record<string, unknown>;
  ref: string;
  same_psalm_occurrence_refs?: string[];
  corpus_occurrence_refs?: string[];
  psalms_occurrence_refs?: string[];
  enrichment_sources?: Record<string, { status: string; available_fields: string[]; missing_fields: string[] }>;
  missing_enrichments?: string[];
}

export interface Alignment {
  alignment_id: string;
  unit_id: string;
  layer: Layer;
  source_token_ids: string[];
  target_span_ids: string[];
  alignment_type: string;
  confidence: number;
  notes: string;
  created_by?: string;
  created_via?: string;
}

export interface RenderingSpan {
  span_id: string;
  text: string;
  token_start: number;
  token_end: number;
}

export interface PreservedSourceImage {
  label: string;
  source_id?: string;
  token_ids?: string[];
  note?: string;
}

export interface TranslationBasis {
  basis_type: 'hebrew_to_english' | 'septuagint_greek_to_english';
  source_ids: string[];
  source_language: string;
  source_version: string;
  basis_note: string;
}

export interface SourceAnchor {
  anchor_text: string;
  source_language: string;
  source_text: string;
  token_ids?: string[];
  basis_note: string;
}

export interface ComposerQualityFilter {
  threshold: number;
  candidate_count_before_filter: number;
  surfaceable_candidate_count: number;
  suppressed_candidate_count: number;
  production_ready?: boolean;
  rejection_reason?: string | null;
  fallback_used: boolean;
  seed_match_used?: boolean;
}

export interface Rendering {
  rendering_id: string;
  unit_id: string;
  layer: Layer;
  status: string;
  text: string;
  style_tags: string[];
  target_spans: RenderingSpan[];
  alignment_ids: string[];
  drift_flags: DriftFlag[];
  metrics: Record<string, number>;
  rationale: string;
  variation_basis?: string[];
  preserved_source_images?: PreservedSourceImage[];
  differentiator?: string | null;
  grounding_confidence?: number | null;
  delivery_profile?: string | null;
  source_anchor?: SourceAnchor | null;
  translation_basis?: TranslationBasis | null;
  provenance: { source_ids: string[]; generator: string; translation_basis?: TranslationBasis | null };
  style_goal?: string | null;
  metric_profile?: string | null;
  issue_links?: string[];
  pr_links?: string[];
  review_signoff?: {
    status: string;
    approval_count: number;
    alternate_approval_count: number;
    required_approvals: { alternate?: number; canonical?: number };
    approvers: Array<{ reviewer: string; reviewer_role: string }>;
    alternate_approvers: Array<{ reviewer: string; reviewer_role: string }>;
    reviewer_roles: string[];
    release_required_role: string;
    has_release_signoff: boolean;
    release_signoff: { reviewer?: string; role?: string; timestamp?: string };
    eligible_for_alternate: boolean;
    eligible_for_canonical: boolean;
    publication_ready: boolean;
    latest_decision: string | null;
    updated_at: string | null;
  };
}

export interface ReviewDecision {
  decision_id: string;
  target_id: string;
  reviewer_role: string;
  reviewer: string;
  decision: string;
  notes: string;
  timestamp: string;
}

export interface Unit {
  psalm_id: string;
  unit_id: string;
  ref: string;
  source_hebrew: string;
  source_transliteration: string;
  segmentation_type: string;
  status: string;
  token_ids: string[];
  tokens: Token[];
  alignments: Alignment[];
  renderings: Rendering[];
  review_decisions: ReviewDecision[];
  issue_links: string[];
  pr_links: string[];
  current_layer_state?: {
    latest_layer?: Layer | null;
    locked_layers?: Layer[];
  };
  witnesses: Array<{
    source_id: string;
    versionTitle: string;
    source_version?: string;
    language: string;
    witness_role?: string;
    ref: string;
    source_url: string;
    text: string;
  }>;
  coverage?: {
    uncovered_tokens: string[];
    unaligned_spans: string[];
    unaligned_renderings: string[];
    low_confidence_alignments: string[];
  };
}

export interface Witness {
  source_id: string;
  versionTitle: string;
  source_version?: string;
  language: string;
  witness_role?: string;
  ref: string;
  source_url: string;
  text: string;
  unit_id: string;
  psalm_id: string;
  canonical_ref: string;
  namespace: 'witness';
}

export interface GenerationJob {
  job_id: string;
  unit_id: string;
  layer: Layer;
  status: string;
  input_hash: string;
  model_profile: string;
  prompt_version: string;
  seed: number;
  runtime_metadata: {
    adapter: string;
    completed_at?: string;
    candidate_count: number;
    production_ready?: boolean;
    quality_filter?: ComposerQualityFilter;
    created_rendering_ids: string[];
    downstream_layers: Layer[];
    [key: string]: unknown;
  };
  output: {
    unit_id: string;
    layer: Layer;
    candidates: Array<{
      text: string;
      rationale: string;
      alignment_hints: string[];
      drift_flags: DriftFlag[];
      metrics: Record<string, number>;
      variation_basis: string[];
      preserved_source_images: PreservedSourceImage[];
      differentiator: string;
      grounding_confidence: number;
      translation_basis: TranslationBasis;
      delivery_profile?: string | null;
      source_anchor?: SourceAnchor | null;
    }>;
  } | null;
}

export interface Psalm {
  psalm_id: string;
  title: string;
  unit_ids: string[];
  units: Unit[];
}

/**
 * Slim per-psalm record returned by `GET /psalms`. Used to populate the picker
 * without fetching every unit. For the full payload (including `units`), call
 * `GET /psalms/{psalm_id}` via `usePsalm`.
 */
export interface PsalmSummary {
  psalm_id: string;
  title: string;
  unit_ids: string[];
}

export interface SourceTranslationMapToken {
  token_id: string;
  surface: string;
  transliteration: string | null;
  lemma: string | null;
  gloss: string | null;
  source_role: string | null;
  semantic_role: string | null;
  anchors: string[];
  visible_anchors: string[];
  alignments: Array<{
    alignment_id: string;
    type: string;
    confidence: number;
    target_text: string | null;
    notes: string;
  }>;
  status: 'explicit' | 'lexical_estimate' | 'unmapped';
  fidelity_weight: number;
}

export interface SourceTranslationMapUnit {
  unit_id: string;
  ref: string;
  source_hebrew: string;
  source_transliteration: string | null;
  rendering: {
    rendering_id: string;
    status: string;
    layer: Layer;
    text: string;
    source_kind: 'saved' | 'witness';
    source_label: string;
    witness: Unit['witnesses'][number] | null;
    translation_basis: TranslationBasis | null;
    rationale: string;
  } | null;
  summary: {
    state: 'mapped' | 'untranslated';
    selection_message?: string;
    source_token_count: number;
    explicitly_mapped_tokens: number;
    lexically_visible_tokens: number;
    unmapped_tokens: number;
    structural_coverage: number;
    visible_anchor_coverage: number;
    fidelity_estimate: number | null;
  };
  tokens: SourceTranslationMapToken[];
  creative_liberties: Array<{
    kind: string;
    severity: string;
    token_id: string | null;
    label: string;
    detail: string;
  }>;
}

export interface SourceTranslationMapRepetition {
  lemma: string;
  label: string;
  glosses: string[];
  count: number;
  occurrences: Array<{
    unit_id: string;
    ref: string;
    token_id: string;
    surface: string;
    gloss: string | null;
    anchors: string[];
  }>;
  explicitly_mapped_count: number;
  visible_anchor_count: number;
  preservation: 'structurally_preserved' | 'lexically_visible' | 'partially_visible' | 'not_visible';
}

export interface PsalmSourceTranslationMap {
  psalm_id: string;
  title: string;
  layer: Layer;
  translation_target: {
    kind: 'saved' | 'witness';
    label: string;
    rendering_status: string | null;
    witness_source_id: string | null;
    version_title: string | null;
    read_only: boolean;
  };
  score_basis: string;
  summary: {
    total_units: number;
    translated_units: number;
    total_source_tokens: number;
    explicitly_mapped_tokens: number;
    lexically_visible_tokens: number;
    structural_coverage: number;
    visible_anchor_coverage: number;
    fidelity_estimate: number | null;
  };
  units: SourceTranslationMapUnit[];
  repetitions: SourceTranslationMapRepetition[];
  possible_added_repetitions: Array<{
    word: string;
    count: number;
    label: string;
    detail: string;
  }>;
}

export interface Project {
  project_id: string;
  title: string;
  divine_name_policy: string;
  source_manifests: Array<{
    source_id: string;
    name: string;
    version: string;
    source_language?: string;
    basis_role?: string;
    version_pinned?: boolean;
    license: string;
    upstream_url?: string;
    allowed_for_generation: boolean;
    allowed_for_display: boolean;
    allowed_for_export: boolean;
    notes: string;
  }>;
  style_profiles: Array<{
    style_profile_id: string;
    literalness: number;
    lyric_freedom: number;
    target_syllables: number;
    rhyme_mode: string;
    register: string;
    parallelism_priority: string;
    source_anchor_mode: string;
    metaphor_mode: string;
    imagery_preservation: number;
    idiom_modernity: number;
    emotional_directness: number;
    faith_posture: string;
    divine_name_rendering?: string;
  }>;
  review_policy: {
    canonical_required_approvals: number;
    alternate_required_approvals: number;
    release_required_role: string;
    reviewer_roles: string[];
  };
}

export interface TokenCard extends Token {
  gloss_list: string[];
  nearby_usage_examples: string[];
  copy_reference: string;
  same_psalm: string[];
  same_psalms: string[];
  wider_corpus: string[];
  counts: {
    same_psalm: number;
    same_psalms: number;
    wider_corpus: number;
  };
  concordance_entry: {
    lemma: { value: string | null; match_count: number };
    strong: { value: string | null; match_count: number };
  };
}

export interface ConcordanceResult {
  token_id: string;
  unit_id: string;
  psalm_id: string;
  ref: string;
  surface: string;
  normalized: string;
  transliteration: string | null;
  lemma: string | null;
  strong: string | null;
  morph_code: string | null;
  morph_readable: string | null;
  part_of_speech: string | null;
  stem: string | null;
  syntax_role: string | null;
  semantic_role: string | null;
  referent: string | null;
  word_sense: string | null;
  gloss_parts: string[];
  display_gloss: string | null;
  compiler_features: Record<string, unknown>;
  occurrence_index: number;
  gloss_list: string[];
  query_field: string;
}

export interface PinnedLexicalCardState {
  token_id: string | null;
  updated_at: string | null;
  token: TokenCard | null;
}

export interface ComposerSuggestionChunk {
  chunk_id: string;
  quality_filter?: ComposerQualityFilter;
  candidates: Array<{
    text: string;
    rationale: string;
    alignment_hints: string[];
    drift_flags: string[];
    metrics: Record<string, unknown>;
    variation_basis: string[];
    preserved_source_images: PreservedSourceImage[];
    differentiator: string;
    grounding_confidence: number;
    translation_basis: TranslationBasis;
    delivery_profile: string;
    source_anchor: SourceAnchor;
  }>;
}

export interface ComposerSuggestionResponse {
  unit_id: string;
  stage: 'phrase' | 'concept' | 'lyric';
  available: boolean;
  status?: 'production_ready' | 'rejected' | 'unavailable' | string;
  chunks: ComposerSuggestionChunk[];
}

export interface OpenConcerns {
  uncovered_tokens: Array<{ unit_id: string; token_id: string }>;
  unaligned_spans: Array<{ unit_id: string; rendering_id: string | null; span_id: string }>;
  open_drift_flags: Array<{ unit_id: string; rendering_id: string; status?: string; flag: DriftFlag }>;
  provenance_gaps: Array<{ unit_id: string; rendering_id: string; status?: string }>;
  low_confidence_alignments: Array<{ unit_id: string; alignment_id: string }>;
}

export interface DriftFlag {
  code: string;
  severity: 'low' | 'medium' | 'high';
  confidence: number;
  message: string;
}

export interface SearchResult {
  kind: string;
  namespace: 'canonical' | 'witness';
  scope: string;
  label: string;
  snippet: string;
  unit_id: string;
  psalm_id: string;
  ref: string;
  token_id?: string;
  rendering_id?: string;
  audit_id?: string;
  decision_id?: string;
  status?: string;
  layer?: string;
  source_id?: string;
  versionTitle?: string;
  language?: string;
  source_url?: string;
  witness_ref?: string;
}

export interface RenderingComparison {
  unit_id: string;
  left: Rendering;
  right: Rendering;
  comparison: {
    same_layer: boolean;
    left_is_canonical: boolean;
    right_is_canonical: boolean;
  };
}

export interface CloudNode {
  node_id: string;
  label: string;
  kind: 'phrase' | 'concept';
  psalm_id: string;
  source_text: string;
  weight: number;
  support_count: number;
  unit_ids: string[];
  concept_ids: string[];
}

export interface RetrievalExplanation {
  matched_concept_ids: string[];
  matched_phrase: string | null;
  vector_score: number;
  phrase_concept_overlap: number;
  literal_priority: number;
  approval_priority: number;
  scope_bonus: number;
  final_score: number;
}

export interface RetrievalHit {
  hit_id: string;
  unit_id: string;
  psalm_id: string;
  ref: string;
  label: string;
  layer: string;
  status: string;
  source_type: 'rendering' | 'phrase';
  rendering_id?: string;
  scope: 'same_psalm' | 'cross_psalm';
  explanation: RetrievalExplanation;
}

export interface VisualFlowUnit {
  unit_id: string;
  ref: string;
  source_hebrew: string;
  tokens: Token[];
  concept_ids: string[];
  default_rendering: Rendering | null;
  supporting_nodes: CloudNode[];
}

export type LyricCorrelationKind =
  | 'close_anchor'
  | 'interpretive_shift'
  | 'added_reframed'
  | 'added_repetition'
  | 'omitted_detail';

export interface PsalmLyricCorrelationRow {
  row_id: string;
  ref: string;
  section_label: string;
  source_unit_ids: string[];
  source_refs: string[];
  source_hebrew: string;
  source_close_english: string;
  source_english_label: string;
  source_scaffold_text: string;
  arrangement_label: string;
  lyric_text: string;
  lyric_status: string;
  lyric_layer: Layer | string | null;
  relationship_kind: LyricCorrelationKind;
  relationship_label: string;
  relationship_note: string;
  overlap_score: number;
}

export interface PsalmVisualFlow {
  psalm_id: string;
  title: string;
  retrieval_status: string;
  embedding_model: string;
  embedding_version: string;
  units: VisualFlowUnit[];
  cloud_nodes: CloudNode[];
  correlation_rows: PsalmLyricCorrelationRow[];
  correlation_summary: {
    row_count: number;
    mapped_row_count: number;
    source_only_row_count: number;
    relationship_counts: Record<LyricCorrelationKind | string, number>;
  };
}

export interface PsalmCloudResponse {
  psalm_id: string;
  scope: string;
  retrieval_status: string;
  embedding_model: string;
  embedding_version: string;
  nodes: CloudNode[];
}

export interface RetrievalResponse {
  psalm_id: string;
  node: CloudNode;
  scope: string;
  include_cross_psalm: boolean;
  retrieval_status: string;
  hits: RetrievalHit[];
}

export interface ConcordanceRow {
  token_id: string;
  unit_id: string;
  ref: string;
  surface: string;
  normalized: string;
  lemma: string | null;
  strong: string | null;
  morph_code: string | null;
  stem: string | null;
  syntax_role: string | null;
}

export interface AssistantActionDefinition {
  action_id: string;
  label: string;
  description: string;
  kind: 'read' | 'write' | 'client';
  requires_confirmation: boolean;
  input_schema: Record<string, unknown>;
  result_schema?: Record<string, unknown>;
  required_fields: string[];
}

export interface AssistantActionPreview {
  action_id: string;
  kind: 'write';
  summary: string;
  input: Record<string, unknown>;
  input_preview: string;
  confirmation_token: string;
  expires_at: string;
}

export interface AssistantToolResult {
  action_id: string;
  kind?: 'read' | 'write' | 'client';
  summary?: string;
  result?: unknown;
  error?: string;
}

export interface AssistantClientAction {
  action_id: string;
  kind: 'client';
  summary: string;
  payload: Record<string, unknown>;
}

export interface AssistantMessage {
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  speakable_text?: string;
  tool_results?: AssistantToolResult[];
  pending_actions?: AssistantActionPreview[];
  client_actions?: AssistantClientAction[];
}

export interface AssistantSession {
  session_id: string;
  created_at: string;
  messages: AssistantMessage[];
}

export interface AssistantMessageResponse {
  session_id: string;
  message: AssistantMessage;
}

export interface AssistantExecuteResponse {
  action_id: string;
  kind: 'read' | 'write' | 'client';
  summary: string;
  result: unknown;
}

export interface AssistantSettings {
  assistant: {
    model_profile_id: string | null;
  };
  openai: {
    base_url: string;
    api_key: string;
    has_api_key: boolean;
    whisper_model: string;
  };
  voice: {
    output_enabled: boolean;
    output_provider: string | null;
    output_voice: string | null;
  };
  providers: {
    speech_to_text: {
      provider: string;
      available: boolean;
      auth_mode: 'api_key' | 'oauth_link';
      auth_status: 'configured' | 'not_configured' | 'unsupported';
      account_link_available: boolean;
    };
    voice_output: {
      available: boolean;
      enabled: boolean;
      provider: string | null;
      voice: string | null;
    };
  };
}

export interface SpeechTranscriptionResponse {
  text: string;
  provider: string;
  model: string;
  filename: string;
}

export type AccuracyRating =
  | 'literal'
  | 'very_close'
  | 'close'
  | 'adapted'
  | 'interpretive'
  | 'omission'
  /** The only value asserting the absence of a source relationship. */
  | 'no_source_basis';

export type WordNoteVerdict =
  | 'standard'
  | 'defensible'
  | 'expansion'
  | 'narrowing'
  | 'nonstandard'
  | 'unsupported'
  | 'omitted';

export interface WordNote {
  token_ids: string[];
  transliteration: string;
  lexical_gloss: string;
  rendered_as: string;
  verdict: WordNoteVerdict;
  note: string;
}

export interface NonSourceMaterial {
  text: string;
  kind: 'meter' | 'instrumentation' | 'vocal_assignment' | 'section_label' | 'dynamics' | 'other';
  note: string;
}

export type ComparisonStatus =
  | 'draft'
  | 'proposed'
  | 'reviewed'
  | 'accepted_as_alternate'
  | 'canonical'
  | 'rejected'
  | 'superseded';

/** How a piece of work was produced. Surfaced as a provenance badge. */
export type CreatedVia = 'human' | 'codex' | 'local_model' | 'deterministic';

export interface ComparisonAssessment {
  comparison_id: string;
  psalm_id: string;
  unit_id: string;
  mt_reference: string;
  display_reference: string;
  hebrew_text: string;
  literal_rendering_id: string | null;
  english_rendering_id: string | null;
  accuracy_rating: AccuracyRating | null;
  accuracy_note: string;
  creative_liberties_note: string;
  status: ComparisonStatus;
  created_by: string;
  created_via: CreatedVia;
  generator_provider: string | null;
  generation_run_id: string | null;
  reviewer_id: string | null;
  reviewed_at: string | null;
  revision_of: string | null;
  audit_ids: string[];
}

/**
 * One Hebrew word with everything the corpus knows about it. Empty fields are
 * omitted server-side, so absence means "not recorded" rather than "null".
 */
export interface StudyToken {
  token_id: string;
  surface: string;
  transliteration?: string;
  lemma?: string;
  strong?: string;
  morph_readable?: string;
  part_of_speech?: string;
  stem?: string;
  display_gloss?: string;
  gloss_parts?: string[];
  word_sense?: string;
  semantic_role?: string;
  syntax_role?: string;
  referent?: string;
  greek?: string;
  greek_strong?: string;
  ref?: string;
  occurrence_count: number;
  occurrence_refs: string[];
  /** Present only on words the analysis pass commented on. */
  note?: WordNote;
}

export interface ComparisonTableRow {
  mt_reference: string;
  display_reference: string;
  unit_ids: string[];
  hebrew_text: string;
  tokens: StudyToken[];
  literal_text: string | null;
  literal_rendering_ids: string[];
  english_text: string | null;
  english_rendering_ids: string[];
  accuracy_rating: AccuracyRating | null;
  accuracy_note: string;
  creative_liberties_note: string;
  assessment_status: ComparisonStatus | null;
  created_via: CreatedVia | null;
  generator_provider: string | null;
  comparison_id: string | null;
  incomplete: boolean;
  literal_backbone: string[];
  non_source_material: NonSourceMaterial[];
  /** True when the audited rendering text has changed since this analysis ran. */
  stale: boolean;
}

export interface PsalmAnalysisSection {
  title: string;
  first_verse: number;
  last_verse: number;
  theme: string;
  arc_note: string;
}

export interface StructuralSeam {
  after_verse: number;
  marker: string;
  /** Whether an arrangement section ends here: a structural-fidelity signal. */
  aligns_with_section: boolean;
}

export interface PsalmAnalysis {
  psalm_analysis_id: string;
  psalm_id: string;
  summary: string;
  sections: PsalmAnalysisSection[];
  structural_seams: StructuralSeam[];
  guardrails: { heading_attribution: string; cultic_setting: string };
  epistemics: {
    known_from_text: Array<{ claim: string; basis: string }>;
    not_known_from_text: Array<{ claim: string; why_not: string }>;
  };
  non_source_material: NonSourceMaterial[];
  method: string;
  citations: string[];
  source_fingerprint: string | null;
  status: string;
  created_by: string;
  created_via: CreatedVia;
  generator_provider: string | null;
  generation_run_id: string | null;
  prompt_template_version: string;
  created_at: string;
  revision_of: string | null;
  audit_ids: string[];
}

/** Masoretic, Septuagint and Vulgate numbers, from the committed table. */
export interface CanonicalNumbering {
  mt: number;
  septuagint: number[];
  vulgate: number[];
}

export interface ComparisonTable {
  psalm_id: string;
  title: string;
  literal_layer: string;
  english_layer: string;
  canonical_numbering: CanonicalNumbering | null;
  analysis: PsalmAnalysis | null;
  rows: ComparisonTableRow[];
}

export interface VerseAnalysisResult {
  unit_id: string;
  status: CodexRun['status'];
  run_id: string | null;
  assessment: ComparisonAssessment | null;
  skipped: boolean;
  error: string | null;
}

export interface PsalmAnalysisResult {
  psalm_id: string;
  status: CodexRun['status'];
  run_id: string | null;
  analysis: PsalmAnalysis | null;
  skipped: boolean;
  error: string | null;
}

export type CodexStatusValue =
  | 'not_installed'
  | 'available'
  | 'connecting'
  | 'ready'
  | 'not_signed_in'
  | 'busy'
  | 'error';

/** Local Codex provider status. Never carries credentials. */
export interface CodexStatus {
  provider: string;
  status: CodexStatusValue;
  detail: string;
  local_only: boolean;
  auth_mode?: string | null;
  plan_type?: string | null;
}

export interface CodexSession {
  session_id: string;
  thread_id: string;
  current_turn_id: string | null;
  model: string;
  provider: string;
  provider_version: string;
  purpose: string;
  psalm_id: string;
  unit_id: string | null;
  layer: string;
  prompt_template_version: string;
  started_at: string;
  completed_at: string | null;
  status: string;
}

export interface CodexRun {
  run_id: string;
  session_id: string;
  thread_id: string;
  turn_id: string | null;
  unit_id: string;
  layer: string;
  provider: string;
  model: string;
  prompt_template_version: string;
  started_at: string;
  completed_at: string | null;
  status: 'running' | 'completed' | 'failed' | 'cancelled' | 'invalid_output';
  events: unknown[];
  denied_events: Array<{ method: string; params?: unknown }>;
  validation: Array<{ path: string; message: string }> | null;
  payload: unknown;
  error: string | null;
}

export interface CodexRunEvents {
  run_id: string;
  status: CodexRun['status'];
  events: unknown[];
  denied_events: Array<{ method: string; params?: unknown }>;
  validation: Array<{ path: string; message: string }> | null;
  error: string | null;
}

export interface TranslationGuidance {
  psalm_id: string;
  translation_guidance: string;
}

export interface RowFillResult {
  unit_id: string;
  status: CodexRun['status'];
  run_ids: string[];
  rendering_ids: string[];
  assessment: ComparisonAssessment | null;
  error: string | null;
}

export interface CodexModel {
  id?: string;
  model?: string;
  displayName?: string;
  [key: string]: unknown;
}
