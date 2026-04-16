import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  ConcordanceResult,
  OpenConcerns,
  PinnedLexicalCardState,
  Project,
  Psalm,
  PsalmCloudResponse,
  PsalmVisualFlow,
  Rendering,
  RenderingComparison,
  RetrievalResponse,
  SearchResult,
  TokenCard,
  Unit,
  Witness,
} from '../types';

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed for ${url}`);
  }
  return response.json() as Promise<T>;
}

async function putJson<T>(url: string, payload: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Request failed for ${url}`);
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

async function deleteJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { method: 'DELETE' });
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

export function useProject() {
  return useQuery({ queryKey: ['project'], queryFn: () => getJson<Project>('/project') });
}

export function usePsalms() {
  return useQuery({ queryKey: ['psalms'], queryFn: () => getJson<Psalm[]>('/psalms') });
}

export function usePsalm(psalmId: string | null) {
  return useQuery({
    queryKey: ['psalm', psalmId],
    queryFn: () => getJson<Psalm>(`/psalms/${psalmId}`),
    enabled: Boolean(psalmId),
  });
}

export function usePsalmVisualFlow(psalmId: string | null) {
  return useQuery({
    queryKey: ['psalm-visual-flow', psalmId],
    queryFn: () => getJson<PsalmVisualFlow>(`/psalms/${psalmId}/visual-flow`),
    enabled: Boolean(psalmId),
  });
}

export function usePsalmCloud(psalmId: string | null, scope = 'selected_psalm', limit = 24) {
  return useQuery({
    queryKey: ['psalm-cloud', psalmId, scope, limit],
    queryFn: () => getJson<PsalmCloudResponse>(`/psalms/${psalmId}/cloud?scope=${encodeURIComponent(scope)}&limit=${limit}`),
    enabled: Boolean(psalmId),
  });
}

export function usePsalmRetrieval(psalmId: string | null, nodeId: string | null, scope = 'selected_psalm', includeCrossPsalm = true, limit = 12) {
  return useQuery({
    queryKey: ['psalm-retrieval', psalmId, nodeId, scope, includeCrossPsalm, limit],
    queryFn: () =>
      getJson<RetrievalResponse>(
        `/psalms/${psalmId}/retrieval?${new URLSearchParams({
          node_id: nodeId ?? '',
          scope,
          include_cross_psalm: String(includeCrossPsalm),
          limit: String(limit),
        }).toString()}`,
      ),
    enabled: Boolean(psalmId && nodeId),
  });
}

export function useUnit(unitId: string | null) {
  return useQuery({
    queryKey: ['unit', unitId],
    queryFn: () => getJson<Unit>(`/units/${unitId}`),
    enabled: Boolean(unitId),
  });
}

export function useTokenCard(tokenId: string | null) {
  return useQuery({
    queryKey: ['token', tokenId],
    queryFn: () => getJson<TokenCard>(`/tokens/${tokenId}`),
    enabled: Boolean(tokenId),
  });
}

export function useOpenConcerns() {
  return useQuery({ queryKey: ['open-concerns'], queryFn: () => getJson<OpenConcerns>('/reports/open-concerns') });
}

export function useConcordance(query: string, field = 'lemma') {
  return useQuery({
    queryKey: ['concordance', query, field],
    queryFn: () => getJson<ConcordanceResult[]>(`/search/concordance?query=${encodeURIComponent(query)}&field=${field}`),
    enabled: query.trim().length > 0,
  });
}

export function usePinnedLexicalCard() {
  return useQuery({
    queryKey: ['pinned-lexical-card'],
    queryFn: () => getJson<PinnedLexicalCardState>('/state/lexical-card'),
  });
}

export function useSetPinnedLexicalCard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tokenId: string | null) => putJson<PinnedLexicalCardState>('/state/lexical-card', { token_id: tokenId }),
    onSuccess: (data) => {
      queryClient.setQueryData(['pinned-lexical-card'], data);
    },
  });
}

export function useCreateAlignment(unitId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: unknown) => postJson('/alignments', payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['unit', unitId] }),
        queryClient.invalidateQueries({ queryKey: ['open-concerns'] }),
      ]);
    },
  });
}

export function useDeleteAlignment(unitId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alignmentId: string) => deleteJson(`/alignments/${alignmentId}`),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['unit', unitId] }),
        queryClient.invalidateQueries({ queryKey: ['open-concerns'] }),
      ]);
    },
  });
}

export function useUpdateAlignment(unitId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alignmentId, payload }: { alignmentId: string; payload: unknown }) =>
      patchJson(`/alignments/${alignmentId}`, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['unit', unitId] }),
        queryClient.invalidateQueries({ queryKey: ['open-concerns'] }),
      ]);
    },
  });
}

export function useCreateRendering(unitId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: unknown) => postJson(`/units/${unitId}/renderings`, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['unit', unitId] }),
        queryClient.invalidateQueries({ queryKey: ['open-concerns'] }),
      ]);
    },
  });
}

export function useApproveRendering(unitId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ renderingId, payload }: { renderingId: string; payload: unknown }) =>
      postJson(`/review/${renderingId}/approve`, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['unit', unitId] });
    },
  });
}

export function useReviewAction(unitId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ renderingId, action, payload }: { renderingId: string; action: 'approve' | 'request-changes' | 'accept-alternate' | 'reject'; payload: unknown }) =>
      postJson(`/review/${renderingId}/${action}`, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['unit', unitId] }),
        queryClient.invalidateQueries({ queryKey: ['alternates', unitId] }),
      ]);
    },
  });
}

export function usePromoteRendering(unitId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ renderingId, payload }: { renderingId: string; payload: unknown }) =>
      postJson(`/renderings/${renderingId}/promote`, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['unit', unitId] }),
        queryClient.invalidateQueries({ queryKey: ['open-concerns'] }),
      ]);
    },
  });
}

export function useExportRelease() {
  return useMutation({
    mutationFn: (payload: unknown) => postJson<{ path: string }>('/export/release', payload),
  });
}

export function useAdvancedSearch(query: string, scope = 'all', includeWitnesses = false) {
  return useQuery({
    queryKey: ['advanced-search', query, scope, includeWitnesses],
    queryFn: () =>
      getJson<SearchResult[]>(
        `/search/advanced?query=${encodeURIComponent(query)}&scope=${encodeURIComponent(scope)}&include_witnesses=${includeWitnesses}`,
      ),
    enabled: query.trim().length > 0,
  });
}

export function useSearchPreset(name: string | null, releaseId?: string) {
  return useQuery({
    queryKey: ['search-preset', name, releaseId],
    queryFn: () =>
      getJson<SearchResult[]>(
        `/search/presets/${name}${releaseId ? `?release_id=${encodeURIComponent(releaseId)}` : ''}`,
      ),
    enabled: Boolean(name) && (name !== 'units_changed_since_release' || Boolean(releaseId?.trim())),
  });
}

export function useUnitWitnesses(unitId: string | null) {
  return useQuery({
    queryKey: ['unit-witnesses', unitId],
    queryFn: () => getJson<Witness[]>(`/units/${unitId}/witnesses`),
    enabled: Boolean(unitId),
  });
}

export function useAlternates(unitId: string | null, layer?: string, styleFilter?: string, releaseApprovedOnly = false) {
  return useQuery({
    queryKey: ['alternates', unitId, layer, styleFilter, releaseApprovedOnly],
    queryFn: () =>
      getJson<Rendering[]>(
        `/units/${unitId}/alternates?${new URLSearchParams({
          ...(layer ? { layer } : {}),
          ...(styleFilter ? { style_filter: styleFilter } : {}),
          release_approved_only: String(releaseApprovedOnly),
        }).toString()}`,
      ),
    enabled: Boolean(unitId),
  });
}

export function useRenderingComparison(unitId: string | null, leftId: string | null, rightId: string | null) {
  return useQuery({
    queryKey: ['rendering-compare', unitId, leftId, rightId],
    queryFn: () =>
      getJson<RenderingComparison>(
        `/units/${unitId}/renderings/compare?${new URLSearchParams({ left_id: leftId ?? '', right_id: rightId ?? '' }).toString()}`,
      ),
    enabled: Boolean(unitId && leftId && rightId),
  });
}

function invalidateUnitRenderings(queryClient: ReturnType<typeof useQueryClient>, unitId: string | null) {
  if (!unitId) {
    return;
  }
  queryClient.invalidateQueries({ queryKey: ['unit', unitId] });
  queryClient.invalidateQueries({ queryKey: ['alternates', unitId] });
  queryClient.invalidateQueries({ queryKey: ['rendering-compare', unitId] });
}

export function useAddAlternate(unitId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) => postJson<Rendering>(`/units/${unitId}/alternates`, payload),
    onSuccess: () => invalidateUnitRenderings(queryClient, unitId),
  });
}

export function useAlternateLifecycleAction(unitId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ renderingId, action, payload }: { renderingId: string; action: 'accept' | 'reject' | 'deprecate' | 'promote'; payload?: Record<string, unknown> }) =>
      postJson<Rendering>(`/alternates/${renderingId}/${action}`, payload ?? {}),
    onSuccess: () => invalidateUnitRenderings(queryClient, unitId),
  });
}

export function useDemoteRendering(unitId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (renderingId: string) => postJson<Rendering>(`/renderings/${renderingId}/demote`, {}),
    onSuccess: () => invalidateUnitRenderings(queryClient, unitId),
  });
}

export function useUpdateRendering(unitId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ renderingId, payload }: { renderingId: string; payload: Record<string, unknown> }) =>
      patchJson<Rendering>(`/renderings/${renderingId}`, payload),
    onSuccess: () => invalidateUnitRenderings(queryClient, unitId),
  });
}

export function useCurrentPsalm(psalms: Psalm[] | undefined, psalmId: string | null): Psalm | undefined {
  return useMemo(() => psalms?.find((psalm) => psalm.psalm_id === psalmId), [psalms, psalmId]);
}
