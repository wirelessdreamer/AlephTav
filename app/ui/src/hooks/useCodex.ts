import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { CodexModel, CodexRun, CodexRunEvents, CodexSession, CodexStatus } from '../types';

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

/** Codex is local-only, so status is polled rather than cached indefinitely. */
export function useCodexStatus(enabled = true) {
  return useQuery({
    queryKey: ['codex-status'],
    queryFn: () => getJson<CodexStatus>('/codex/status'),
    enabled,
    refetchInterval: 30_000,
  });
}

export function useCodexModels(enabled: boolean) {
  return useQuery({
    queryKey: ['codex-models'],
    queryFn: () => getJson<CodexModel[]>('/codex/models'),
    enabled,
  });
}

export function useConnectCodex() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => postJson<CodexStatus>('/codex/connect', {}),
    onSuccess: (status) => {
      queryClient.setQueryData(['codex-status'], status);
      queryClient.invalidateQueries({ queryKey: ['codex-models'] });
    },
  });
}

/** Hands off to Codex's own ChatGPT sign-in; no API key is ever requested. */
export function useCodexLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => postJson<{ started: boolean; auth_url_present: boolean }>('/codex/login', {}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['codex-status'] }),
  });
}

export function useCodexSessions(psalmId: string | null) {
  const query = psalmId ? `?psalm_id=${encodeURIComponent(psalmId)}` : '';
  return useQuery({
    queryKey: ['codex-sessions', psalmId],
    queryFn: () => getJson<CodexSession[]>(`/codex/sessions${query}`),
  });
}

export function useCreateCodexSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      psalm_id: string;
      unit_id?: string | null;
      layer?: string;
      model?: string;
      purpose?: string;
    }) => postJson<CodexSession>('/codex/sessions', payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['codex-sessions'] }),
  });
}

export function useStartCodexTurn() {
  return useMutation({
    mutationFn: ({
      sessionId,
      ...payload
    }: {
      sessionId: string;
      unit_id: string;
      layer: string;
      candidate_count?: number;
      style_profile?: string;
      meter_target?: string;
      constraints?: string[];
    }) => postJson<CodexRun>(`/codex/sessions/${sessionId}/turns`, payload),
  });
}

export function useCancelCodexRun() {
  return useMutation({
    mutationFn: (runId: string) => postJson<CodexRun>(`/codex/runs/${runId}/cancel`, {}),
  });
}

export function useCodexRunEvents(runId: string | null) {
  return useQuery({
    queryKey: ['codex-run-events', runId],
    queryFn: () => getJson<CodexRunEvents>(`/codex/runs/${runId}/events`),
    enabled: Boolean(runId),
  });
}

/** Saves validated candidates as proposed renderings; never canonical. */
export function useSaveCodexCandidates() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, createdBy }: { runId: string; createdBy?: string }) =>
      postJson<unknown[]>(`/codex/runs/${runId}/save-candidates`, { created_by: createdBy }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['psalm'] });
      queryClient.invalidateQueries({ queryKey: ['comparison-table'] });
    },
  });
}
