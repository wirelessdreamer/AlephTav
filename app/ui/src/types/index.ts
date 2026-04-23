export type Layer =
  | 'gloss'
  | 'literal'
  | 'phrase'
  | 'concept'
  | 'lyric'
  | 'metered_lyric'
  | 'parallelism_lyric';

export type DrawerTab = 'concordance' | 'workflow' | 'search' | 'witnesses' | 'audit' | 'compare';

export interface Token {
  token_id: string;
  surface: string;
  normalized: string;
  transliteration: string | null;
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
  provenance: { source_ids: string[]; generator: string };
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
  witnesses: Array<{ source_id: string; versionTitle: string; language: string; ref: string; source_url: string; text: string }>;
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
  language: string;
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
    }>;
  } | null;
}

export interface Psalm {
  psalm_id: string;
  title: string;
  unit_ids: string[];
  units: Unit[];
}

export interface Project {
  project_id: string;
  title: string;
  divine_name_policy: string;
  source_manifests: Array<{
    source_id: string;
    name: string;
    version: string;
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
  candidates: Array<{
    text: string;
    rationale: string;
    alignment_hints: string[];
    drift_flags: string[];
    metrics: Record<string, unknown>;
  }>;
}

export interface ComposerSuggestionResponse {
  unit_id: string;
  stage: 'phrase' | 'concept' | 'lyric';
  available: boolean;
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

export interface PsalmVisualFlow {
  psalm_id: string;
  title: string;
  retrieval_status: string;
  embedding_model: string;
  embedding_version: string;
  units: VisualFlowUnit[];
  cloud_nodes: CloudNode[];
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
