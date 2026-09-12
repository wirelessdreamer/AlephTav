import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  AccuracyRating,
  ComparisonAssessment,
  ComparisonStatus,
  ComparisonTable,
} from '../types';

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(url: string, payload: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

async function patchJson<T>(url: string, payload: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export function useComparisonTable(
  psalmId: string | null,
  literalLayer = 'literal',
  englishLayer = 'lyric',
) {
  const query = new URLSearchParams({
    literal_layer: literalLayer,
    english_layer: englishLayer,
  });
  return useQuery({
    queryKey: ['comparison-table', psalmId, literalLayer, englishLayer],
    queryFn: () => getJson<ComparisonTable>(`/psalms/${psalmId}/comparison-table?${query}`),
    enabled: Boolean(psalmId),
  });
}

export function useComparisonAssessments(
  psalmId: string | null,
  filters: {
    status?: ComparisonStatus;
    accuracyRating?: AccuracyRating;
    reviewerId?: string;
    includeSuperseded?: boolean;
  } = {},
) {
  const query = new URLSearchParams();
  if (filters.status) query.set('status', filters.status);
  if (filters.accuracyRating) query.set('accuracy_rating', filters.accuracyRating);
  if (filters.reviewerId) query.set('reviewer_id', filters.reviewerId);
  if (filters.includeSuperseded) query.set('include_superseded', 'true');

  return useQuery({
    queryKey: ['comparison-assessments', psalmId, filters],
    queryFn: () =>
      getJson<ComparisonAssessment[]>(`/psalms/${psalmId}/comparison-assessments?${query}`),
    enabled: Boolean(psalmId),
  });
}

function useInvalidateComparisons(psalmId: string | null) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ['comparison-table', psalmId] });
    queryClient.invalidateQueries({ queryKey: ['comparison-assessments', psalmId] });
  };
}

export function useCreateComparisonAssessment(psalmId: string | null) {
  const invalidate = useInvalidateComparisons(psalmId);
  return useMutation({
    mutationFn: (payload: {
      unit_id: string;
      literal_rendering_id?: string | null;
      english_rendering_id?: string | null;
      accuracy_rating?: AccuracyRating | null;
      accuracy_note?: string;
      creative_liberties_note?: string;
      status?: ComparisonStatus;
      created_by?: string;
      created_via?: string;
    }) => postJson<ComparisonAssessment>('/comparison-assessments', payload),
    onSuccess: invalidate,
  });
}

/**
 * Revising never edits in place: the API supersedes the original and returns a
 * linked successor, so the assessment history is preserved.
 */
export function useReviseComparisonAssessment(psalmId: string | null) {
  const invalidate = useInvalidateComparisons(psalmId);
  return useMutation({
    mutationFn: ({
      comparisonId,
      ...payload
    }: {
      comparisonId: string;
      unit_id: string;
      accuracy_rating?: AccuracyRating | null;
      accuracy_note?: string;
      creative_liberties_note?: string;
      status?: ComparisonStatus;
      reviewer_id?: string;
      created_by?: string;
    }) => patchJson<ComparisonAssessment>(`/comparison-assessments/${comparisonId}`, payload),
    onSuccess: invalidate,
  });
}
