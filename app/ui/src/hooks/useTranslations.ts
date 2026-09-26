import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { PsalmTranslation } from '../types';

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

/** A psalm's translations: its main one (translation_id null) first. */
export function useTranslations(psalmId: string | null) {
  return useQuery({
    queryKey: ['translations', psalmId],
    queryFn: () => getJson<PsalmTranslation[]>(`/psalms/${psalmId}/translations`),
    enabled: Boolean(psalmId),
  });
}

export function useCreateTranslation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      psalmId,
      ...payload
    }: {
      psalmId: string;
      title: string;
      created_via?: 'human' | 'import';
    }) => postJson<PsalmTranslation>(`/psalms/${psalmId}/translations`, payload),
    onSuccess: (translation) =>
      queryClient.invalidateQueries({ queryKey: ['translations', translation.psalm_id] }),
  });
}
