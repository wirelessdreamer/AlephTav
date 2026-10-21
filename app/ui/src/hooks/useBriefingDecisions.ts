import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import type { BriefingAnnotation, PsalmBriefing, TranslationContextEvent } from '../types';

type Decisions = Record<number, BriefingAnnotation>;

/** The audit trail is authoritative; the local outbox protects edits until acknowledged. */
export function useBriefingDecisions(psalmId: string | null, translationId: string | null,
  briefing: PsalmBriefing | null | undefined, history: TranslationContextEvent[]) {
  const key = `aleph-tav.briefing-decisions:${psalmId}|${translationId ?? 'main'}|${briefing?.run_id}`;
  const client = useQueryClient();
  const [pending, setPending] = useState<Decisions>(() => {
    try { return JSON.parse(localStorage.getItem(key) ?? '{}'); } catch { return {}; }
  });
  const pendingRef = useRef(pending);
  const [decisions, setDecisions] = useState<Decisions>(() => {
    const recorded: Decisions = {};
    const direct: Decisions = {};
    for (const event of history) for (const note of event.annotations ?? []) {
      if (note.briefing_run_id === briefing?.run_id) {
        recorded[note.question_index] = note;
        if (event.kind === 'briefing_decision') direct[note.question_index] = note;
      }
    }
    return { ...recorded, ...direct, ...pending };
  });
  const [error, setError] = useState<string | null>(null);
  const saving = useRef<Promise<boolean> | null>(null);

  const store = useCallback((next: Decisions) => {
    pendingRef.current = next;
    if (Object.keys(next).length) localStorage.setItem(key, JSON.stringify(next));
    else localStorage.removeItem(key);
    setPending(next);
  }, [key]);

  const flush = useCallback((): Promise<boolean> => {
    if (saving.current) return saving.current;
    if (!psalmId || !briefing) return Promise.resolve(true);
    const request = (async () => {
    try {
      // Serialize writes so a slow earlier request cannot overwrite a later answer.
      while (Object.keys(pendingRef.current).length) {
        const note = Object.values(pendingRef.current)[0];
        const response = await fetch(`/psalms/${psalmId}/briefing-decisions`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ translation_id: translationId, annotation: note }),
          keepalive: true,
        });
        if (!response.ok) throw new Error(await response.text());
        // Keep a newer edit made while this request was in flight.
        if (JSON.stringify(pendingRef.current[note.question_index]) === JSON.stringify(note)) {
          const next = { ...pendingRef.current };
          delete next[note.question_index];
          store(next);
        }
        void client.invalidateQueries({ queryKey: ['briefing', psalmId, translationId] });
        void client.invalidateQueries({ queryKey: ['verse-history'] });
      }
      setError(null);
      return true;
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
      return false;
    } finally { saving.current = null; }
    })();
    saving.current = request;
    void request.then(() => { if (saving.current === request) saving.current = null; });
    return request;
  }, [psalmId, translationId, briefing, client, store]);

  useEffect(() => {
    if (error || !Object.keys(pending).length) return;
    const timer = window.setTimeout(() => void flush(), 400);
    return () => window.clearTimeout(timer);
  }, [pending, error, flush]);

  useEffect(() => () => { void flush(); }, [flush]);

  function update(index: number, patch: Partial<Pick<BriefingAnnotation, 'answer' | 'notes'>>) {
    if (!briefing) return;
    const note: BriefingAnnotation = {
      ...(decisions[index] ?? { answer: '', notes: '' }), ...patch,
      briefing_run_id: briefing.run_id, question_index: index,
      question: briefing.questions[index],
    };
    // Write synchronously, before a navigation or reload can discard React state.
    store({ ...pendingRef.current, [index]: note });
    setDecisions(previous => ({ ...previous, [index]: note }));
    setError(null);
  }

  return { decisions, update, error, pending: Object.keys(pending).length > 0,
    flush, retry: () => { setError(null); void flush(); } };
}
