import { useId, useState } from 'react';

import {
  useAddVerseNote,
  useRemoveVerseNote,
  useWordSuggestions,
} from '../hooks/useComparisonAssessments';
import type { StudyToken, VerseNote } from '../types';
import { InContext } from './InContext';
import {
  choiceInContext,
  choiceNoteText,
  layerLabel,
  pickedChoice,
  type VerseCodex,
} from './verseActions';

/** Shown until "more" is asked for; the translator covers the whole range, up to twenty. */
const TOP = 3;

/** Open pick notes for a word: at most one should stand at a time. */
export function openPicks(notes: VerseNote[], tokenIds: string[]): VerseNote[] {
  return notes.filter(
    (note) => note.status === 'open' && note.token_ids?.some((id) => tokenIds.includes(id)),
  );
}

/**
 * Pick a rendering for a word, as an instruction for the next rebuild. A new pick
 * replaces the word's earlier open pick; picking the current one again clears it.
 */
export function useWordPick(psalmId: string, translationId: string | null) {
  const add = useAddVerseNote(psalmId, translationId);
  const remove = useRemoveVerseNote(psalmId);

  async function toggle(options: {
    unitId: string;
    tokenIds: string[];
    name: string;
    surface: string;
    choice: string;
    notes: VerseNote[];
  }) {
    const current = openPicks(options.notes, options.tokenIds);
    const already = current.some((note) => pickedChoice(note.text) === options.choice);
    for (const note of current) {
      await remove.mutateAsync({ unitId: options.unitId, noteId: note.note_id });
    }
    if (already) return;
    await add.mutateAsync({
      unitId: options.unitId,
      text: choiceNoteText(options.name, options.surface, options.choice),
      applies_to: 'english',
      kind: 'instruction',
      token_ids: options.tokenIds,
    });
  }

  return {
    toggle,
    pending: add.isPending || remove.isPending,
    error: add.error ?? remove.error,
  };
}

interface Props {
  psalmId: string;
  translationId: string | null;
  unitId: string;
  token: StudyToken;
  englishLayer: string;
  notes: VerseNote[];
  codex: Pick<VerseCodex, 'ready' | 'hint' | 'busy' | 'suggest'>;
  /** The word's tokens and how to name it, when it spans more than ``token``. */
  tokenIds?: string[];
  surface?: string;
  /** The verse's current English, so each choice can be shown in its line. */
  englishText?: string | null;
  /** Where the word sits in its verse (0 to 1), to place it among repeated phrases. */
  positionHint?: number;
}

/**
 * Ranked renderings for a word that matters, each one a click away from being an
 * instruction for the next rebuild, plus room for the reviewer's own.
 */
export function WordChoices({
  psalmId,
  translationId,
  unitId,
  token,
  englishLayer,
  notes,
  codex,
  tokenIds: givenTokenIds,
  surface: givenSurface,
  englishText,
  positionHint,
}: Props) {
  // A note can cover a bound phrase; suggestions are for the whole of it.
  const tokenIds = givenTokenIds ?? token.note?.token_ids ?? [token.token_id];
  const surface = givenSurface ?? token.surface;
  const { data } = useWordSuggestions(unitId, tokenIds, englishLayer, translationId);
  const pick = useWordPick(psalmId, translationId);
  const [showAll, setShowAll] = useState(false);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [own, setOwn] = useState('');
  const ownId = useId();

  const suggestions = data?.suggestions ?? [];
  const shown = showAll ? suggestions : suggestions.slice(0, TOP);
  const name = token.note?.transliteration || token.transliteration || token.surface;
  const queued = openPicks(notes, tokenIds);
  const picked = new Set(queued.map((note) => pickedChoice(note.text)));

  async function ask() {
    setAsking(true);
    setAskError(null);
    try {
      await codex.suggest(tokenIds);
    } catch (error) {
      setAskError(error instanceof Error ? error.message : String(error));
    } finally {
      setAsking(false);
    }
  }

  function use(choice: string) {
    void pick.toggle({ unitId, tokenIds, name, surface, choice, notes }).catch(() => undefined);
  }

  return (
    <section className="word-choices" aria-label={`Choices for ${name}`}>
      <div className="verse-actions">
        <h4 className="verse-label">Choices for the {layerLabel(englishLayer).toLowerCase()}</h4>
        <span className="verse-actions__spacer" />
        {suggestions.length > 0 ? (
          <button
            type="button"
            className="btn-sm"
            disabled={asking || !codex.ready || codex.busy}
            title={codex.hint}
            onClick={() => void ask()}
          >
            {asking ? 'Asking Codex…' : 'Suggest again'}
          </button>
        ) : null}
      </div>

      {data?.outdated ? (
        <p className="rebuild-review__warning">
          {data.outdated_reason === 'prompt'
            ? 'This is an older, narrower list. Suggest again to cover the whole range; every choice here is kept.'
            : `These were suggested under earlier psalm guidance${data.guidance ? ` (“${data.guidance}”)` : ''}. Suggest again to fit the current guidance.`}
        </p>
      ) : null}

      {suggestions.length === 0 ? (
        <div className="verse-actions">
          <span className="verse-notes__hint">
            Codex offers at least three renderings for this word, best first.
          </span>
          <button
            type="button"
            disabled={asking || !codex.ready || codex.busy}
            title={codex.hint}
            onClick={() => void ask()}
          >
            {asking ? 'Asking Codex…' : 'Suggest renderings'}
          </button>
        </div>
      ) : (
        <ol className="word-choices__list">
          {shown.map((choice, index) => (
            <li key={choice.text} className={picked.has(choice.text) ? 'is-picked' : undefined}>
              <span className="word-choices__rank">{index + 1}</span>
              <span className="word-choices__body">
                <strong className="word-choices__text">
                  <InContext
                    runs={choiceInContext(choice, englishText, token.note?.rendered_as, positionHint)}
                    fallback={choice.text}
                  />
                </strong>
                <span className="verse-notes__hint">
                  {choice.sense}
                  {choice.earlier ? ' · from an earlier list' : null}
                </span>
                <span className="note-prose">{choice.rationale}</span>
                {choice.fit ? <span className="word-choices__fit">{choice.fit}</span> : null}
              </span>
              <button
                type="button"
                className="btn-sm"
                aria-pressed={picked.has(choice.text)}
                disabled={pick.pending}
                onClick={() => use(choice.text)}
              >
                {picked.has(choice.text) ? 'Picked · undo' : 'Use in next rebuild'}
              </button>
            </li>
          ))}
        </ol>
      )}
      {suggestions.length > TOP ? (
        <button type="button" className="btn-sm btn-ghost" onClick={() => setShowAll((all) => !all)}>
          {showAll ? 'Show top 3' : `Show ${suggestions.length - TOP} more`}
        </button>
      ) : null}

      <div className="verse-actions word-choices__own">
        <label htmlFor={ownId} className="verse-notes__hint">
          Or your own
        </label>
        <input
          id={ownId}
          value={own}
          placeholder={`How should ${name} read?`}
          onChange={(event) => setOwn(event.target.value)}
        />
        <button
          type="button"
          disabled={!own.trim() || pick.pending}
          onClick={() => {
            use(own.trim());
            setOwn('');
          }}
        >
          Use in next rebuild
        </button>
      </div>

      {queued.length > 0 ? (
        <p className="verse-notes__hint">
          Queued for the next rebuild: {queued.map((note) => note.text).join(' · ')}
        </p>
      ) : null}
      {askError || pick.error ? (
        <p className="comparison-error">{askError ?? String(pick.error)}</p>
      ) : null}
    </section>
  );
}

export default WordChoices;
