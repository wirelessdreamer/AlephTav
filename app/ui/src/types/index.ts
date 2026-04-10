export type Layer =
  | 'gloss'
  | 'literal'
  | 'phrase'
  | 'concept'
  | 'lyric'
  | 'metered_lyric'
  | 'parallelism_lyric';

export interface Token {
  token_id: string;
  surface: string;
  normalized: string;
  transliteration: string | null;
  lemma: string | null;
  strong: string | null;
  morph_readable: string | null;
  stem?: string | null;
  syntax_role: string | null;
  semantic_role: string | null;
  referent: string | null;
  word_sense: string | null;
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
  drift_flags: string[];
  metrics: Record<string, number>;
  rationale: string;
  provenance: { source_ids: string[]; generator: string };
  style_goal?: string | null;
  metric_profile?: string | null;
  issue_links?: string[];
  pr_links?: string[];
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
  witnesses: Array<{ source_id: string; versionTitle: string; language: string; ref: string; source_url: string; text: string }>;
  coverage?: { uncovered_tokens: string[]; unaligned_renderings: string[] };
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
  occurrence_index: number;
  gloss_list: string[];
  query_field: string;
}

export interface PinnedLexicalCardState {
  token_id: string | null;
  updated_at: string | null;
  token: TokenCard | null;
}

export interface OpenConcerns {
  uncovered_tokens: Array<{ unit_id: string; token_id: string }>;
  unaligned_spans: Array<{ unit_id: string; rendering_id: string }>;
  open_drift_flags: Array<{ unit_id: string; rendering_id: string; flag: string }>;
  provenance_gaps: Array<{ unit_id: string; rendering_id: string }>;
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
