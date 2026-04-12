import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, KeyboardEvent } from 'react';

import { useAppRuntime } from '../app/AppContext';
import {
  useAssistantMessage,
  useAssistantSettings,
  useAssistantTools,
  useCreateAssistantSession,
  useExecuteAssistantAction,
  useSaveAssistantSettings,
  useSpeechTranscription,
} from '../hooks/useAssistant';
import { useSetPinnedLexicalCard } from '../hooks/useWorkbench';
import type { AssistantActionPreview, AssistantMessage, AssistantSettings } from '../types';

function formatToolResult(result: unknown) {
  const json = JSON.stringify(result ?? null, null, 2);
  if (json.length <= 320) {
    return json;
  }
  return `${json.slice(0, 317)}...`;
}

const QUICK_PROMPTS = [
  'Open the workbench and show unresolved drift.',
  'Pin the current token and open concordance.',
  'Compare canonical and alternate renderings for this unit.',
];

export function AssistantPanel() {
  const { assistantContext, applyClientAction } = useAppRuntime();
  const [isExpanded, setIsExpanded] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [apiKeyDraft, setApiKeyDraft] = useState('');
  const [baseUrlDraft, setBaseUrlDraft] = useState('');
  const [whisperModelDraft, setWhisperModelDraft] = useState('');
  const [assistantModelDraft, setAssistantModelDraft] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const createSession = useCreateAssistantSession();
  const sendMessage = useAssistantMessage(sessionId);
  const executeAction = useExecuteAssistantAction();
  const toolsQuery = useAssistantTools();
  const settingsQuery = useAssistantSettings();
  const saveSettings = useSaveAssistantSettings();
  const transcription = useSpeechTranscription();
  const setPinnedLexicalCard = useSetPinnedLexicalCard();

  useEffect(() => {
    if (sessionId || createSession.isPending || createSession.isSuccess) {
      return;
    }
    createSession.mutate(undefined, {
      onSuccess: (session) => setSessionId(session.session_id),
    });
  }, [createSession, sessionId]);

  useEffect(() => {
    const settings = settingsQuery.data;
    if (!settings) {
      return;
    }
    setBaseUrlDraft(settings.openai.base_url);
    setWhisperModelDraft(settings.openai.whisper_model);
    setAssistantModelDraft(settings.assistant.model_profile_id ?? '');
  }, [settingsQuery.data]);

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current?.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const pendingCount = useMemo(
    () => messages.reduce((count, message) => count + (message.pending_actions?.length ?? 0), 0),
    [messages],
  );

  const speechSettings = settingsQuery.data?.providers.speech_to_text;
  const canUseMicrophone = Boolean(speechSettings?.available) && typeof navigator !== 'undefined' && 'mediaDevices' in navigator;

  const appendTranscript = (text: string) => {
    setDraft((existing) => `${existing}${existing ? '\n' : ''}${text}`.trim());
  };

  const runClientAction = (actionId: string, payload: Record<string, unknown>) => {
    applyClientAction(actionId, payload);
    if (actionId === 'workbench.pin_token') {
      void setPinnedLexicalCard.mutateAsync(String(payload.token_id));
    }
    if (actionId === 'workbench.clear_pinned_token') {
      void setPinnedLexicalCard.mutateAsync(null);
    }
  };

  const handleSend = (messageOverride?: string) => {
    const nextMessage = (messageOverride ?? draft).trim();
    if (!sessionId || !nextMessage) {
      return;
    }
    const userMessage: AssistantMessage = {
      role: 'user',
      content: nextMessage,
      created_at: new Date().toISOString(),
    };
    setMessages((existing) => [...existing, userMessage]);
    setDraft('');
    sendMessage.mutate(
      {
        message: nextMessage,
        context: assistantContext,
      },
      {
        onSuccess: ({ message }) => {
          setMessages((existing) => [...existing, message]);
          message.client_actions?.forEach((action) => runClientAction(action.action_id, action.payload));
        },
        onError: (error) => {
          setMessages((existing) => [
            ...existing,
            {
              role: 'assistant',
              content: error instanceof Error ? error.message : 'Assistant request failed.',
              created_at: new Date().toISOString(),
            },
          ]);
        },
      },
    );
  };

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      handleSend();
    }
  };

  const handleConfirmAction = (preview: AssistantActionPreview) => {
    executeAction.mutate(
      {
        action_id: preview.action_id,
        input: preview.input,
        confirmation_token: preview.confirmation_token,
      },
      {
        onSuccess: (response) => {
          setMessages((existing) =>
            existing.map((message) =>
              message.pending_actions?.some((item) => item.confirmation_token === preview.confirmation_token)
                ? {
                    ...message,
                    pending_actions: (message.pending_actions ?? []).filter(
                      (item) => item.confirmation_token !== preview.confirmation_token,
                    ),
                    tool_results: [
                      ...(message.tool_results ?? []),
                      {
                        action_id: response.action_id,
                        kind: response.kind,
                        summary: response.summary,
                        result: response.result,
                      },
                    ],
                  }
                : message,
            ),
          );
        },
      },
    );
  };

  const handleAudioSelection = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    transcription.mutate(
      { file },
      {
        onSuccess: (result) => appendTranscript(result.text),
      },
    );
    event.target.value = '';
  };

  const handleToggleRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }
    if (!canUseMicrophone) {
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaStreamRef.current = stream;
    audioChunksRef.current = [];
    const recorder = new MediaRecorder(stream);
    mediaRecorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunksRef.current.push(event.data);
      }
    };
    recorder.onstop = () => {
      const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' });
      const file = new File([blob], 'assistant-recording.webm', { type: blob.type || 'audio/webm' });
      transcription.mutate(
        { file },
        {
          onSettled: () => {
            mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
            mediaStreamRef.current = null;
          },
          onSuccess: (result) => appendTranscript(result.text),
        },
      );
    };
    recorder.start();
    setIsRecording(true);
  };

  const handleSaveSettings = (settings: AssistantSettings | undefined) => {
    saveSettings.mutate({
      assistant: {
        model_profile_id: assistantModelDraft || settings?.assistant.model_profile_id || null,
      },
      openai: {
        ...(apiKeyDraft.trim() ? { api_key: apiKeyDraft.trim() } : {}),
        base_url: baseUrlDraft.trim() || settings?.openai.base_url || 'https://api.openai.com/v1',
        whisper_model: whisperModelDraft.trim() || settings?.openai.whisper_model || 'whisper-1',
      },
    });
    setApiKeyDraft('');
  };

  return (
    <aside className={`assistant-panel${isExpanded ? ' assistant-panel--expanded' : ''}`}>
      <div className="assistant-panel__bar">
        <div>
          <p className="eyebrow">Assistant</p>
          <strong>Conversational Control Surface</strong>
          <p className="assistant-panel__meta">
            {toolsQuery.data?.length ?? 0} actions {' • '} {pendingCount} pending write{pendingCount === 1 ? '' : 's'}
          </p>
        </div>
        <div className="assistant-panel__actions">
          <button type="button" className="link-button" onClick={() => setIsSettingsOpen((existing) => !existing)}>
            Settings
          </button>
          <button type="button" className="link-button" onClick={() => setIsExpanded((existing) => !existing)}>
            {isExpanded ? 'Collapse' : 'Expand'}
          </button>
        </div>
      </div>

      {isExpanded ? (
        <div className="assistant-panel__body">
          <div className="assistant-panel__main">
            <div className="assistant-context">
              <span className="tag">Route: {assistantContext.route}</span>
              <span className="tag">Unit: {assistantContext.workbench.unitId ?? 'none'}</span>
              <span className="tag">Layer: {assistantContext.workbench.layer}</span>
              <span className="tag">Tab: {assistantContext.ui.drawerTab}</span>
            </div>

            <div className="assistant-thread">
              {messages.length === 0 ? (
                <article className="assistant-message assistant-message--assistant">
                  <p>Use chat to inspect project data, navigate the workbench, manage selections, or stage writes for confirmation.</p>
                  <div className="assistant-quick-prompts">
                    {QUICK_PROMPTS.map((prompt) => (
                      <button key={prompt} type="button" className="tab" onClick={() => handleSend(prompt)}>
                        {prompt}
                      </button>
                    ))}
                  </div>
                </article>
              ) : null}
              {messages.map((message, index) => (
                <article key={`${message.created_at}-${index}`} className={`assistant-message assistant-message--${message.role}`}>
                  <p>{message.content}</p>
                  {message.client_actions?.map((action, actionIndex) => (
                    <div key={`${action.action_id}-${actionIndex}`} className="assistant-card assistant-card--client">
                      <strong>{action.summary}</strong>
                    </div>
                  ))}
                  {message.tool_results?.map((result, resultIndex) => (
                    <div key={`${result.action_id}-${resultIndex}`} className="assistant-card">
                      <strong>{result.summary ?? result.action_id}</strong>
                      <pre>{result.error ?? formatToolResult(result.result)}</pre>
                    </div>
                  ))}
                  {message.pending_actions?.map((preview) => (
                    <div key={preview.confirmation_token} className="assistant-card assistant-card--pending">
                      <strong>{preview.summary}</strong>
                      <pre>{preview.input_preview}</pre>
                      <button type="button" className="hero-link hero-link-primary" onClick={() => handleConfirmAction(preview)}>
                        Confirm write
                      </button>
                    </div>
                  ))}
                </article>
              ))}
            </div>

            <div className="assistant-composer">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleComposerKeyDown}
                placeholder="Ask the app to inspect, navigate, select, compare, review, transcribe, or prepare a change."
                rows={3}
              />
              <div className="assistant-composer__actions">
                <div className="assistant-composer__tools">
                  <button type="button" className="link-button" onClick={() => fileInputRef.current?.click()}>
                    Upload audio
                  </button>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => void handleToggleRecording()}
                    disabled={!canUseMicrophone || transcription.isPending}
                  >
                    {isRecording ? 'Stop recording' : 'Record audio'}
                  </button>
                </div>
                <button type="button" className="hero-link hero-link-primary" onClick={() => handleSend()} disabled={!sessionId || sendMessage.isPending}>
                  Send
                </button>
              </div>
              <input ref={fileInputRef} type="file" accept="audio/*" hidden onChange={handleAudioSelection} />
            </div>
          </div>

          <aside className="assistant-sidebar">
            <section className="assistant-settings assistant-sidebar__section">
              <div className="horizontal-between">
                <strong>Providers</strong>
                <span className="subtle">
                  {speechSettings?.provider ?? 'speech'}: {speechSettings?.auth_status ?? 'unknown'}
                </span>
              </div>
              <p className="subtle">
                OpenAI account linking is reserved for a future provider-supported flow. Whisper transcription currently uses configured API credentials.
              </p>
              <label>
                <span>Assistant model profile</span>
                <input value={assistantModelDraft} onChange={(event) => setAssistantModelDraft(event.target.value)} placeholder="demo-local" />
              </label>
              <label>
                <span>OpenAI base URL</span>
                <input value={baseUrlDraft} onChange={(event) => setBaseUrlDraft(event.target.value)} placeholder="https://api.openai.com/v1" />
              </label>
              <label>
                <span>Whisper model</span>
                <input value={whisperModelDraft} onChange={(event) => setWhisperModelDraft(event.target.value)} placeholder="whisper-1" />
              </label>
              {isSettingsOpen ? (
                <>
                  <label>
                    <span>OpenAI API key</span>
                    <input
                      type="password"
                      value={apiKeyDraft}
                      onChange={(event) => setApiKeyDraft(event.target.value)}
                      placeholder={settingsQuery.data?.openai.has_api_key ? 'Stored locally' : 'sk-...'}
                    />
                  </label>
                  <button type="button" className="hero-link hero-link-primary" onClick={() => handleSaveSettings(settingsQuery.data)}>
                    Save assistant settings
                  </button>
                </>
              ) : null}
            </section>

            <section className="assistant-sidebar__section">
              <strong>Context Snapshot</strong>
              <pre>{formatToolResult(assistantContext)}</pre>
            </section>
          </aside>
        </div>
      ) : null}
    </aside>
  );
}
