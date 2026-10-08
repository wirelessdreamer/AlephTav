import type { AccuracyRating, ComparisonStatus, CreatedVia } from '../types';

export const ACCURACY_RATINGS: AccuracyRating[] = [
  'literal',
  'very_close',
  'close',
  'adapted',
  'interpretive',
  'omission',
  'no_source_basis',
];

export const STATUS_LABELS: Record<ComparisonStatus, string> = {
  draft: 'Draft',
  proposed: 'Proposed',
  reviewed: 'Reviewed',
  accepted_as_alternate: 'Accepted alternate',
  canonical: 'Canonical',
  rejected: 'Rejected',
  superseded: 'Superseded',
};

export const VIA_LABELS: Record<CreatedVia, string> = {
  human: 'Human authored',
  codex: 'Codex suggested',
  local_model: 'Other local model suggested',
  deterministic: 'Deterministically composed',
};

/** Severity grouping for the row stripe, so fidelity reads before the prose. */
export const RATING_TONE: Record<AccuracyRating, 'close' | 'interpret' | 'caution'> = {
  literal: 'close',
  very_close: 'close',
  close: 'close',
  adapted: 'interpret',
  interpretive: 'interpret',
  omission: 'caution',
  no_source_basis: 'caution',
};
