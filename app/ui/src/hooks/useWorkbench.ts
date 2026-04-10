import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  ConcordanceResult,
  OpenConcerns,
  PinnedLexicalCardState,
  Project,
  Psalm,
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

export function useProject() {
  return useQuery({ queryKey: ['project'], queryFn: () => getJson<Project>('/project') });
}

export function usePsalms() {
  return useQuery({ queryKey: ['psalms'], queryFn: () => getJson<Psalm[]>('/psalms') });
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

export function useCurrentPsalm(psalms: Psalm[] | undefined, psalmId: string | null): Psalm | undefined {
  return useMemo(() => psalms?.find((psalm) => psalm.psalm_id === psalmId), [psalms, psalmId]);
}
