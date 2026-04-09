import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import type { OpenConcerns, Project, Psalm, TokenCard, Unit } from '../types';

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
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
    queryFn: () => getJson<Array<Record<string, string>>>(`/search/concordance?query=${encodeURIComponent(query)}&field=${field}`),
    enabled: query.trim().length > 0,
  });
}

export function useCurrentPsalm(psalms: Psalm[] | undefined, psalmId: string | null): Psalm | undefined {
  return useMemo(() => psalms?.find((psalm) => psalm.psalm_id === psalmId), [psalms, psalmId]);
}
