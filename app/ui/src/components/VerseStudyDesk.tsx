import { useEffect, useMemo, useState, type KeyboardEvent, type ReactNode } from 'react';

import { useAssistantMessage, useCreateAssistantSession } from '../hooks/useAssistant';
import type { AssistantMessage, ComparisonTableRow, StudyToken } from '../types';

export type VerseStudyTab = 'chat' | 'evidence' | 'notes';

const QUICK_PROMPTS = [
  'Walk me through the Hebrew clauses in this verse.',
  'Explain the most difficult translation choice.',
  'Compare the literal and lyric renderings.',
];

interface EvidenceItem {
  key: string;
  label: string;
  detail: string;
  body?: string;
}

interface Props {
  row: ComparisonTableRow;
  englishLayer: string;
  psalmId: string;
  translationId: string | null;
  selectedToken: StudyToken | null;
  activeTab: VerseStudyTab;
  onTabChange: (tab: VerseStudyTab) => void;
  notesPanel: ReactNode;
}

function errorDetail(error: unknown): string {
  if (!(error instanceof Error)) return 'Study chat failed.';
  try {
    const parsed = JSON.parse(error.message) as { detail?: unknown };
    if (typeof parsed.detail === 'string') return parsed.detail;
  } catch {
    // The message is already readable.
  }
  return error.message;
}

function EvidenceList({ items, compact = false }: { items: EvidenceItem[]; compact?: boolean }) {
  return (
    <div className={`verse-study-evidence${compact ? ' verse-study-evidence--compact' : ''}`}>
      {items.map((item) => (
        <article key={item.key} className="verse-study-evidence__item">
          <span className="verse-study-evidence__check" aria-hidden="true">
            ✓
          </span>
          <div>
            <strong>{item.label}</strong>
            <span>{item.detail}</span>
            {!compact && item.body ? <p>{item.body}</p> : null}
          </div>
        </article>
      ))}
    </div>
  );
}

/** A read-only, verse-scoped assistant with the evidence and notes beside it. */
export function VerseStudyDesk({
  row,
  englishLayer,
  psalmId,
  translationId,
  selectedToken,
  activeTab,
  onTabChange,
  notesPanel,
}: Props) {
  const unitId = row.unit_ids[0];
  const openNotes = useMemo(
    () => row.verse_notes.filter((note) => note.status === 'open'),
    [row.verse_notes],
  );
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [draft, setDraft] = useState('');
  const createSession = useCreateAssistantSession();
  const sendMessage = useAssistantMessage(sessionId);

  useEffect(() => {
    if (
      activeTab !== 'chat' ||
      sessionId ||
      createSession.isPending ||
      createSession.isSuccess
    ) {
      return;
    }
    createSession.mutate(undefined, {
      onSuccess: (session) => setSessionId(session.session_id),
    });
  }, [activeTab, createSession, sessionId]);

  const evidence = useMemo<EvidenceItem[]>(() => {
    const items: EvidenceItem[] = [
      {
        key: 'hebrew',
        label: 'Hebrew source',
        detail: `${row.tokens.length} token${row.tokens.length === 1 ? '' : 's'} with lexical data`,
        body: row.hebrew_text,
      },
    ];
    if (row.literal_text) {
      items.push({
        key: 'literal',
        label: 'Literal rendering',
        detail: row.literal_rendering_ids[0] ?? 'Current literal text',
        body: row.literal_text,
      });
    }
    if (row.english_text) {
      items.push({
        key: 'english',
        label: `${englishLayer.replace(/_/g, ' ')} rendering`,
        detail: row.english_rendering_ids[0] ?? 'Current selected text',
        body: row.english_text,
      });
    }
    if (row.accuracy_rating || row.accuracy_note || row.creative_liberties_note) {
      items.push({
        key: 'assessment',
        label: 'Comparison assessment',
        detail: row.accuracy_rating?.replace(/_/g, ' ') ?? 'Unrated',
        body: [row.accuracy_note, row.creative_liberties_note].filter(Boolean).join(' '),
      });
    }
    if (selectedToken) {
      items.push({
        key: 'selected-token',
        label: `Selected word · ${selectedToken.surface}`,
        detail: [selectedToken.transliteration, selectedToken.display_gloss]
          .filter(Boolean)
          .join(' · '),
        body: [selectedToken.word_sense, selectedToken.note?.note].filter(Boolean).join(' '),
      });
    }
    if (openNotes.length > 0) {
      items.push({
        key: 'notes',
        label: 'Open verse notes',
        detail: `${openNotes.length} note${openNotes.length === 1 ? '' : 's'} in context`,
        body: openNotes.map((note) => note.text).join(' '),
      });
    }
    return items;
  }, [englishLayer, openNotes, row, selectedToken]);

  const assistantContext = useMemo<Record<string, unknown>>(
    () => ({
      route: 'workbench',
      workbench: {
        psalmId,
        unitId,
        translationId,
        layer: englishLayer,
      },
      ui: {
        surface: 'verse-study-desk',
        tab: activeTab,
        selectedTokenId: selectedToken?.token_id ?? null,
      },
      study: {
        unit_id: unitId,
        reference: row.display_reference,
        mt_reference: row.mt_reference,
        hebrew_text: row.hebrew_text,
        tokens: row.tokens.map((token) => ({
          token_id: token.token_id,
          surface: token.surface,
          transliteration: token.transliteration,
          lemma: token.lemma,
          strong: token.strong,
          morphology: token.morph_readable,
          part_of_speech: token.part_of_speech,
          stem: token.stem,
          gloss: token.display_gloss,
          word_sense: token.word_sense,
          semantic_role: token.semantic_role,
          syntax_role: token.syntax_role,
          referent: token.referent,
          greek: token.greek,
          note: token.note
            ? {
                token_ids: token.note.token_ids,
                lexical_gloss: token.note.lexical_gloss,
                rendered_as: token.note.rendered_as,
                verdict: token.note.verdict,
                note: token.note.note,
              }
            : null,
        })),
        literal_text: row.literal_text,
        english_layer: englishLayer,
        english_text: row.english_text,
        accuracy_rating: row.accuracy_rating,
        accuracy_note: row.accuracy_note,
        creative_liberties_note: row.creative_liberties_note,
        selected_token_id: selectedToken?.token_id ?? null,
        open_notes: openNotes.map((note) => ({
          note_id: note.note_id,
          text: note.text,
          quote: note.quote,
          applies_to: note.applies_to,
          kind: note.kind,
          token_ids: note.token_ids ?? [],
        })),
      },
    }),
    [activeTab, englishLayer, openNotes, psalmId, row, selectedToken, translationId, unitId],
  );

  const handleSend = (override?: string) => {
    const content = (override ?? draft).trim();
    if (!sessionId || !content || sendMessage.isPending) return;
    const userMessage: AssistantMessage = {
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, userMessage]);
    setDraft('');
    sendMessage.mutate(
      { message: content, context: assistantContext },
      {
        onSuccess: ({ message }) => setMessages((current) => [...current, message]),
        onError: (error) =>
          setMessages((current) => [
            ...current,
            {
              role: 'assistant',
              content: errorDetail(error),
              created_at: new Date().toISOString(),
            },
          ]),
      },
    );
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <section className="verse-study-desk" aria-label={`Study desk for ${row.display_reference}`}>
      <header className="verse-study-desk__header">
        <div>
          <h4>Study desk</h4>
          <p>
            {row.display_reference}
            {row.display_reference !== row.mt_reference ? ` · MT ${row.mt_reference}` : ''} ·
            read-only contextual study
          </p>
        </div>
        {selectedToken ? (
          <span className="verse-study-desk__selection">
            Selected: <b lang="he">{selectedToken.surface}</b>
          </span>
        ) : null}
      </header>

      <div className="verse-study-desk__tabs" role="tablist" aria-label="Study desk views">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'chat'}
          aria-pressed={activeTab === 'chat'}
          onClick={() => onTabChange('chat')}
        >
          Chat{messages.length > 0 ? ` · ${messages.length}` : ''}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'evidence'}
          aria-pressed={activeTab === 'evidence'}
          onClick={() => onTabChange('evidence')}
        >
          Evidence · {evidence.length}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'notes'}
          aria-pressed={activeTab === 'notes'}
          onClick={() => onTabChange('notes')}
        >
          Notes{openNotes.length > 0 ? ` · ${openNotes.length}` : ''}
        </button>
      </div>

      {activeTab === 'chat' ? (
        <div className="verse-study-desk__chat" role="tabpanel">
          <div className="verse-study-desk__conversation">
            <div className="verse-study-desk__scope">
              <span className="verse-label">Conversation scope</span>
              <strong>
                {row.display_reference} · Hebrew + literal + {englishLayer.replace(/_/g, ' ')}
                {selectedToken ? ' + selected word' : ''}
              </strong>
            </div>

            <div className="verse-study-thread" aria-live="polite">
              {messages.length === 0 ? (
                <article className="verse-study-message verse-study-message--assistant">
                  <span className="verse-label">AlephTav</span>
                  <p>
                    Ask for clarification, lexical detail, literary structure, or a comparison of
                    the current renderings. Answers use the evidence listed beside this thread.
                  </p>
                  <div className="verse-study-prompts">
                    {QUICK_PROMPTS.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        disabled={!sessionId || sendMessage.isPending}
                        onClick={() => handleSend(prompt)}
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </article>
              ) : null}
              {messages.map((message, index) => (
                <article
                  key={`${message.created_at}-${index}`}
                  className={`verse-study-message verse-study-message--${message.role}`}
                >
                  <span className="verse-label">{message.role === 'user' ? 'You' : 'AlephTav'}</span>
                  <p>{message.content}</p>
                  {message.tool_results?.map((result, resultIndex) =>
                    result.error ? (
                      <p key={`${result.action_id}-${resultIndex}`} className="comparison-error">
                        {result.error}
                      </p>
                    ) : null,
                  )}
                </article>
              ))}
              {sendMessage.isPending ? (
                <p className="verse-study-thread__status" role="status">
                  Studying the verse…
                </p>
              ) : null}
            </div>

            <div className="verse-study-composer">
              <label className="visually-hidden" htmlFor={`study-question-${unitId}`}>
                Ask about {row.display_reference}
              </label>
              <textarea
                id={`study-question-${unitId}`}
                rows={3}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Ask a follow-up about ${row.display_reference}…`}
              />
              <div>
                <span>{sessionId ? 'Ctrl/⌘ + Enter to send' : 'Connecting study chat…'}</span>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={!sessionId || !draft.trim() || sendMessage.isPending}
                  onClick={() => handleSend()}
                >
                  Send
                </button>
              </div>
            </div>
          </div>

          <aside className="verse-study-desk__evidence-summary" aria-label="Evidence supplied to chat">
            <h5 className="verse-label">Evidence supplied to chat</h5>
            <EvidenceList items={evidence} compact />
            <button type="button" className="btn-ghost" onClick={() => onTabChange('evidence')}>
              Open evidence trail
            </button>
          </aside>
        </div>
      ) : null}

      {activeTab === 'evidence' ? (
        <div className="verse-study-desk__evidence" role="tabpanel">
          <div className="verse-study-desk__scope">
            <span className="verse-label">Current context snapshot</span>
            <strong>These sources are included with every question in this verse thread.</strong>
          </div>
          <EvidenceList items={evidence} />
        </div>
      ) : null}

      {activeTab === 'notes' ? (
        <div className="verse-study-desk__notes" role="tabpanel">
          {notesPanel}
        </div>
      ) : null}
    </section>
  );
}

export default VerseStudyDesk;
