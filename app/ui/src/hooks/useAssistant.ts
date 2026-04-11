import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type {
  AssistantActionDefinition,
  AssistantActionPreview,
  AssistantExecuteResponse,
  AssistantMessageResponse,
  AssistantSettings,
  AssistantSession,
  SpeechTranscriptionResponse,
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

async function postForm<T>(url: string, formData: FormData): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

export function useAssistantTools() {
  return useQuery({
    queryKey: ['assistant-tools'],
    queryFn: () => getJson<AssistantActionDefinition[]>('/assistant/tools'),
  });
}

export function useAssistantSettings() {
  return useQuery({
    queryKey: ['assistant-settings'],
    queryFn: () => getJson<AssistantSettings>('/assistant/settings'),
  });
}

export function useSaveAssistantSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) => patchJson<AssistantSettings>('/assistant/settings', payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['assistant-settings'], data);
    },
  });
}

export function useCreateAssistantSession() {
  return useMutation({
    mutationFn: () => postJson<AssistantSession>('/assistant/sessions', {}),
  });
}

export function useAssistantMessage(sessionId: string | null) {
  return useMutation({
    mutationFn: (payload: { message: string; context: Record<string, unknown> }) =>
      postJson<AssistantMessageResponse>(`/assistant/sessions/${sessionId}/messages`, payload),
  });
}

export function usePreviewAssistantAction() {
  return useMutation({
    mutationFn: (payload: { action_id: string; input: Record<string, unknown> }) =>
      postJson<AssistantActionPreview>('/assistant/actions/preview', payload),
  });
}

export function useExecuteAssistantAction() {
  return useMutation({
    mutationFn: (payload: { action_id: string; input: Record<string, unknown>; confirmation_token?: string }) =>
      postJson<AssistantExecuteResponse>('/assistant/actions/execute', payload),
  });
}

export function useSpeechTranscription() {
  return useMutation({
    mutationFn: ({ file, prompt }: { file: File; prompt?: string }) => {
      const formData = new FormData();
      formData.append('file', file);
      if (prompt) {
        formData.append('prompt', prompt);
      }
      return postForm<SpeechTranscriptionResponse>('/speech/transcriptions', formData);
    },
  });
}
