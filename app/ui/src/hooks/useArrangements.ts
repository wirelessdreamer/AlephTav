import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ArrangementDraft, ArrangementList, ArrangementView } from '../types';

async function sendJson<T>(url: string, method: string, payload?: unknown): Promise<T> {
  const response = await fetch(url, {
    method,
    headers: payload === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

const base = (psalmId: string) => `/psalms/${psalmId}/arrangements`;

/** The API answered with FastAPI's bare 404: it has no such route, so it predates it. */
export function isMissingRoute(error: unknown): boolean {
  return error instanceof Error && error.message.trim() === '{"detail":"Not Found"}';
}

/** Retrying cannot help an API that lacks the route. */
const retry = (failures: number, error: unknown) => !isMissingRoute(error) && failures < 2;

/** One translation's song settings, with the refrains the psalm's Hebrew repeats. */
export function useArrangements(psalmId: string | null, translationId: string | null) {
  const query = translationId ? `?translation_id=${encodeURIComponent(translationId)}` : '';
  return useQuery({
    queryKey: ['arrangements', psalmId, translationId],
    queryFn: () => sendJson<ArrangementList>(`${base(psalmId as string)}${query}`, 'GET'),
    enabled: Boolean(psalmId),
    retry,
  });
}

/** One setting as sung, with its coverage of the Hebrew and its liberties. */
export function useArrangementView(psalmId: string | null, arrangementId: string | null) {
  return useQuery({
    queryKey: ['arrangement', psalmId, arrangementId],
    queryFn: () =>
      sendJson<ArrangementView>(`${base(psalmId as string)}/${arrangementId}`, 'GET'),
    enabled: Boolean(psalmId && arrangementId),
    retry,
  });
}

export interface ArrangementEdit {
  method: 'POST' | 'PATCH' | 'DELETE';
  /** Below the arrangement: '' for the setting itself, 'sections', 'lines/ln.0001', … */
  path: string;
  body?: unknown;
}

/** Every edit answers with the setting's new view, which replaces the cached one. */
export function useEditArrangement(psalmId: string | null, arrangementId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ method, path, body }: ArrangementEdit) =>
      sendJson<ArrangementView>(
        `${base(psalmId as string)}/${arrangementId}${path ? `/${path}` : ''}`,
        method,
        body ?? (method === 'DELETE' ? undefined : {}),
      ),
    onSuccess: (view) => {
      queryClient.setQueryData(['arrangement', psalmId, arrangementId], view);
      void queryClient.invalidateQueries({ queryKey: ['arrangements', psalmId] });
    },
  });
}

export function useCreateArrangement(psalmId: string | null, translationId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { layer: string; title?: string }) =>
      sendJson<ArrangementView>(base(psalmId as string), 'POST', {
        ...payload,
        translation_id: translationId,
      }),
    onSuccess: (view) => {
      queryClient.setQueryData(['arrangement', psalmId, view.arrangement.arrangement_id], view);
      void queryClient.invalidateQueries({ queryKey: ['arrangements', psalmId] });
    },
  });
}

/** One Codex turn: a pasted translation read as a setting, its lines kept as pasted. */
export function useArrangeImport(psalmId: string | null) {
  return useSettingTurn(psalmId, 'import');
}

/** One Codex turn: a whole-psalm setting, stored as a proposal. */
export function useDraftArrangement(psalmId: string | null) {
  return useSettingTurn(psalmId, 'draft');
}

function useSettingTurn(psalmId: string | null, kind: 'draft' | 'import') {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { session_id: string; layer: string; text?: string }) =>
      sendJson<ArrangementDraft>(
        `/codex/psalms/${psalmId as string}/arrangements/${kind}`,
        'POST',
        payload,
      ),
    onSuccess: (result) => {
      if (result.view) {
        queryClient.setQueryData(
          ['arrangement', psalmId, result.view.arrangement.arrangement_id],
          result.view,
        );
      }
      void queryClient.invalidateQueries({ queryKey: ['arrangements', psalmId] });
    },
  });
}
