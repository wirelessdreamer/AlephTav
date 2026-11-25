import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { IntentionalTranslationChoice, RecordTranslationChoice, TranslationChoicesView } from '../types';

export class TranslationChoiceError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
  }
}

async function result<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    let message = body;
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === 'string') message = parsed.detail;
    } catch { /* The server may return plain text. */ }
    throw new TranslationChoiceError(message || 'Request failed.', response.status);
  }
  return response.json() as Promise<T>;
}

export function useTranslationChoices(psalmId: string, translationId: string | null,
  scope: { unitId?: string; arrangementId?: string }) {
  const client = useQueryClient();
  const base = `/psalms/${encodeURIComponent(psalmId)}/translation-choices`;
  const params = new URLSearchParams();
  if (translationId) params.set('translation_id', translationId);
  if (scope.unitId) params.set('unit_id', scope.unitId);
  if (scope.arrangementId) params.set('arrangement_id', scope.arrangementId);
  const query = useQuery({
    queryKey: ['translation-choices', psalmId, translationId, scope.unitId, scope.arrangementId],
    queryFn: async () => result<TranslationChoicesView>(await fetch(`${base}?${params}`)),
  });
  const save = useMutation({
    mutationFn: async (body: RecordTranslationChoice) => result<IntentionalTranslationChoice>(await fetch(base, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['translation-choices', psalmId] }),
        client.invalidateQueries({ queryKey: ['verse-history'] }),
        client.invalidateQueries({ queryKey: ['briefing', psalmId] }),
      ]);
    },
  });
  return { query, save };
}
