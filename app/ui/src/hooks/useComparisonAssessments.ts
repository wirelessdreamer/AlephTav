import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  AccuracyRating,
  ComparisonAssessment,
  ComparisonStatus,
  ComparisonTable,
  OccurrenceContext,
  Rebuild,
  VerseHistory,
  VerseNote,
  WordSuggestions,
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
  translationId: string | null = null,
) {
  const query = new URLSearchParams({
    literal_layer: literalLayer,
    english_layer: englishLayer,
  });
  if (translationId) query.set('translation_id', translationId);
  return useQuery({
    queryKey: ['comparison-table', psalmId, literalLayer, englishLayer, translationId],
    queryFn: () => getJson<ComparisonTable>(`/psalms/${psalmId}/comparison-table?${query}`),
    enabled: Boolean(psalmId),
  });
}

async function sendJson<T>(url: string, method: 'PATCH' | 'DELETE', payload?: unknown): Promise<T> {
  const response = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

/** Notes and rebuild decisions change the row, and the verse's history. */
function useRefreshVerse(psalmId: string | null) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ['comparison-table', psalmId] });
    queryClient.invalidateQueries({ queryKey: ['verse-history'] });
  };
}

/** A note belongs to the translation it is written in; null is the psalm's main one. */
export function useAddVerseNote(psalmId: string | null, translationId: string | null) {
  const refresh = useRefreshVerse(psalmId);
  return useMutation({
    mutationFn: ({
      unitId,
      ...payload
    }: {
      unitId: string;
      text: string;
      applies_to: VerseNote['applies_to'];
      kind: VerseNote['kind'];
      quote?: string;
      token_ids?: string[];
    }) =>
      postJson<VerseNote>(`/units/${unitId}/verse-notes`, {
        ...payload,
        translation_id: translationId,
      }),
    onSuccess: refresh,
  });
}

export function useUpdateVerseNote(psalmId: string | null) {
  const refresh = useRefreshVerse(psalmId);
  return useMutation({
    mutationFn: ({
      unitId,
      noteId,
      ...payload
    }: {
      unitId: string;
      noteId: string;
      text?: string;
      applies_to?: VerseNote['applies_to'];
      kind?: VerseNote['kind'];
      status?: VerseNote['status'];
    }) => sendJson<VerseNote>(`/units/${unitId}/verse-notes/${noteId}`, 'PATCH', payload),
    onSuccess: refresh,
  });
}

export function useRemoveVerseNote(psalmId: string | null) {
  const refresh = useRefreshVerse(psalmId);
  return useMutation({
    mutationFn: ({ unitId, noteId }: { unitId: string; noteId: string }) =>
      sendJson<VerseNote>(`/units/${unitId}/verse-notes/${noteId}`, 'DELETE'),
    onSuccess: refresh,
  });
}

export function useDecideRebuild(psalmId: string | null) {
  const refresh = useRefreshVerse(psalmId);
  return useMutation({
    mutationFn: ({
      unitId,
      rebuildId,
      decision,
      addressedNoteIds,
    }: {
      unitId: string;
      rebuildId: string;
      decision: 'accept' | 'discard';
      addressedNoteIds?: string[];
    }) =>
      postJson<Rebuild>(`/units/${unitId}/rebuilds/${rebuildId}/${decision}`, {
        addressed_note_ids: addressedNoteIds ?? [],
      }),
    onSuccess: refresh,
  });
}

export function useVerseHistory(unitId: string | null) {
  return useQuery({
    queryKey: ['verse-history', unitId],
    queryFn: () => getJson<VerseHistory>(`/units/${unitId}/verse-history`),
    enabled: Boolean(unitId),
  });
}

/** Suggestions already generated for a word; generating one is a Codex turn. */
export function useWordSuggestions(
  unitId: string,
  tokenIds: string[],
  layer: string,
  translationId: string | null,
) {
  const query = new URLSearchParams({ token_ids: tokenIds.join(','), layer });
  if (translationId) query.set('translation_id', translationId);
  return useQuery({
    queryKey: ['word-suggestions', unitId, tokenIds.join(','), layer, translationId],
    queryFn: () => getJson<WordSuggestions>(`/units/${unitId}/word-suggestions?${query}`),
    enabled: tokenIds.length > 0,
  });
}

/** Fetched on hover; a verse's context never changes while the page is open, so cache it. */
export function useOccurrenceContext(
  tokenId: string,
  ref: string | null,
  englishLayer = 'lyric',
) {
  const query = new URLSearchParams({ ref: ref ?? '', english_layer: englishLayer });
  return useQuery({
    queryKey: ['occurrence-context', tokenId, ref, englishLayer],
    queryFn: () =>
      getJson<OccurrenceContext>(`/tokens/${tokenId}/occurrence-context?${query}`),
    enabled: Boolean(ref),
    staleTime: Infinity,
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
      /** The translation whose English is assessed; null or absent for the main one. */
      translation_id?: string | null;
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
