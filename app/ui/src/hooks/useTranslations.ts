import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { Collection, PsalmTranslation } from '../types';

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

async function sendJson<T>(url: string, payload: unknown, method = 'POST'): Promise<T> {
  const response = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

/** Every project, the default one first, with the psalms it has a translation of. */
export function useCollections() {
  return useQuery({
    queryKey: ['collections'],
    queryFn: () => getJson<Collection[]>('/collections'),
  });
}

export function useCreateCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (title: string) => sendJson<Collection>('/collections', { title }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['collections'] }),
  });
}

export function useRenameCollection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ collectionId, title }: { collectionId: string; title: string }) =>
      sendJson<Collection>(`/collections/${collectionId}`, { title }, 'PATCH'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['collections'] }),
  });
}

/** A new translation of a psalm, in a project that has none of it yet. */
export function useCreateTranslation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      psalmId,
      ...payload
    }: {
      psalmId: string;
      title: string;
      collection_id: string;
      created_via?: 'human' | 'import';
    }) => sendJson<PsalmTranslation>(`/psalms/${psalmId}/translations`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['collections'] }),
  });
}

/** Put a translation (null for the psalm's main one) in another project. */
export function useMoveTranslation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      psalmId,
      ...payload
    }: {
      psalmId: string;
      translation_id: string | null;
      collection_id: string;
    }) => sendJson<PsalmTranslation>(`/psalms/${psalmId}/translations/move`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['collections'] }),
  });
}
