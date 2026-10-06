import { useState, type ReactNode } from 'react';

import { useOccurrenceContext } from '../hooks/useComparisonAssessments';
import type { ComparisonTableRow, StudyToken, VerseNote } from '../types';
import { RebuildReview } from './RebuildReview';
import { positionHint, type RebuildProgress, type VerseCodex } from './verseActions';
import { VerseHistoryPanel } from './VerseHistoryPanel';
import { VerseNotes } from './VerseNotes';
import { VerseStudyDesk, type VerseStudyTab } from './VerseStudyDesk';
import { WordChoices } from './WordChoices';

/** Lexical fields shown in the word tray, in order. Absent fields are skipped. */
const WORD_FIELDS: Array<[keyof StudyToken, string]> = [
  ['lemma', 'Lemma'],
  ['strong', "Strong's"],
  ['morph_readable', 'Morphology'],
  ['part_of_speech', 'Part of speech'],
  ['stem', 'Stem'],
  ['greek', 'LXX'],
];

/** A note can span several tokens; list it once, under its first word. */
function notedWords(tokens: StudyToken[]): StudyToken[] {
  const seen = new Set<string>();
  return tokens.filter((token) => {
    if (!token.note) return false;
    const key = token.note.token_ids.join(',');
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

interface Hovered {
  ref: string;
  /** Viewport position of the card; fixed so the tray's edges never clip it. */
  top: number;
  left: number;
  above: boolean;
}

/** The card shown while an occurrence is hovered or focused. */
function OccurrenceCard({
  tokenId,
  hovered,
  englishLayer,
}: {
  tokenId: string;
  hovered: Hovered;
  englishLayer: string;
}) {
  const { data, isLoading, error } = useOccurrenceContext(tokenId, hovered.ref, englishLayer);
  const layer = englishLayer.replace(/_/g, ' ');

  return (
    <div
      id={`occurrence-${tokenId}`}
      role="tooltip"
      className={`occurrence-card${hovered.above ? ' occurrence-card--above' : ''}`}
      style={{ top: hovered.top, left: hovered.left }}
    >
      {isLoading ? <p className="word-tray__hint">Loading {hovered.ref}…</p> : null}
      {error ? <p className="comparison-error">{String(error)}</p> : null}
      {data ? (
        <>
          <div className="occurrence-card__head">
            <strong>{data.display_reference}</strong>
            {data.display_reference !== data.ref ? (
              <span className="occurrence-card__mt">MT {data.ref}</span>
            ) : null}
          </div>

          <p className="occurrence-card__hebrew" dir="rtl" lang="he">
            {data.tokens.map((word, index) => (
              <span key={word.token_id}>
                {index > 0 ? ' ' : null}
                {word.match ? <mark>{word.surface}</mark> : word.surface}
              </span>
            ))}
          </p>
          <p className="occurrence-card__gloss">
            {data.tokens.map((word, index) => (
              <span key={word.token_id}>
                {index > 0 ? ' · ' : null}
                {word.match ? <mark>{word.gloss ?? '?'}</mark> : (word.gloss ?? '?')}
              </span>
            ))}
          </p>

          {data.matches.map((match) => (
            <dl key={match.token_id} className="word-tray__fields occurrence-card__form">
              <div>
                <dt>Form</dt>
                <dd>
                  <span lang="he" className="hebrew">
                    {match.surface}
                  </span>{' '}
                  <span className="translit">{match.transliteration}</span>
                </dd>
              </div>
              {match.display_gloss ? (
                <div>
                  <dt>Gloss</dt>
                  <dd>{match.display_gloss}</dd>
                </div>
              ) : null}
              {match.morph_readable || match.part_of_speech ? (
                <div>
                  <dt>Morphology</dt>
                  <dd>
                    {[match.part_of_speech, match.stem, match.morph_readable]
                      .filter(Boolean)
                      .join(' · ')}
                  </dd>
                </div>
              ) : null}
              {match.greek ? (
                <div>
                  <dt>LXX</dt>
                  <dd>{match.greek}</dd>
                </div>
              ) : null}
            </dl>
          ))}

          {data.literal_text || data.english_text ? (
            <div className="occurrence-card__renderings">
              {data.literal_text ? (
                <div>
                  <h5 className="verse-label">Literal</h5>
                  <p>{data.literal_text}</p>
                </div>
              ) : null}
              {data.english_text ? (
                <div>
                  <h5 className="verse-label">{layer}</h5>
                  <p>{data.english_text}</p>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="word-tray__hint">This verse has no literal or {layer} rendering yet.</p>
          )}
        </>
      ) : null}
    </div>
  );
}

function Occurrences({ token, englishLayer }: { token: StudyToken; englishLayer: string }) {
  const [hovered, setHovered] = useState<Hovered | null>(null);

  if (token.occurrence_count === 0) return <div className="word-tray__occurrences" />;

  const show = (ref: string, element: HTMLElement) => {
    const rect = element.getBoundingClientRect();
    // The tray sits low on the page, so open upwards unless there is no room.
    const above = rect.top > window.innerHeight / 2;
    setHovered({
      ref,
      above,
      top: above ? rect.top - 8 : rect.bottom + 8,
      left: Math.max(8, Math.min(rect.left - 160, window.innerWidth - 440)),
    });
  };
  const hide = () => setHovered(null);

  return (
    <div className="word-tray__occurrences">
      <span className="verse-label">{token.occurrence_count} occurrences in other psalms</span>
      <ul>
        {token.occurrence_refs.map((ref) => (
          <li key={ref}>
            <button
              type="button"
              className="occurrence"
              aria-describedby={hovered?.ref === ref ? `occurrence-${token.token_id}` : undefined}
              onMouseEnter={(event) => show(ref, event.currentTarget)}
              onFocus={(event) => show(ref, event.currentTarget)}
              onMouseLeave={hide}
              onBlur={hide}
              onKeyDown={(event) => {
                if (event.key === 'Escape') hide();
              }}
            >
              {ref.replace(/^Psalm /, '')}
            </button>
          </li>
        ))}
        {token.occurrence_count > token.occurrence_refs.length ? (
          <li className="occurrence-more">
            +{token.occurrence_count - token.occurrence_refs.length} more
          </li>
        ) : null}
      </ul>
      {hovered ? (
        <OccurrenceCard tokenId={token.token_id} hovered={hovered} englishLayer={englishLayer} />
      ) : null}
    </div>
  );
}

function WordTray({
  token,
  noted,
  englishLayer,
  onSelect,
  psalmId,
  translationId,
  unitId,
  notes,
  codex,
  englishText,
  hint,
}: {
  token: StudyToken | null;
  noted: StudyToken[];
  englishLayer: string;
  onSelect: (tokenId: string) => void;
  psalmId: string;
  translationId: string | null;
  unitId: string;
  notes: VerseNote[];
  codex: VerseCodex;
  englishText: string | null;
  /** Where the selected word sits in its verse, 0 to 1. */
  hint?: number;
}) {
  if (!token) {
    return (
      <section className="word-tray word-tray--empty" aria-label="Word study">
        {noted.length > 0 ? (
          <>
            <h4 className="verse-label">Noted words · pick one to study</h4>
            <div className="word-tray__noted">
              {noted.map((word) => (
                <button
                  key={word.token_id}
                  type="button"
                  className="noted-word"
                  onClick={() => onSelect(word.token_id)}
                >
                  <span className="noted-word__head">
                    <span lang="he" dir="rtl" className="hebrew">
                      {word.surface}
                    </span>
                    <span className="translit">{word.note?.transliteration}</span>
                    <span className={`verdict verdict-${word.note?.verdict}`}>
                      {word.note?.verdict.replace(/_/g, ' ')}
                    </span>
                  </span>
                  <span>
                    {word.note?.lexical_gloss} <span className="arrow">→</span>{' '}
                    {word.note?.rendered_as}
                  </span>
                </button>
              ))}
            </div>
          </>
        ) : (
          <p className="word-tray__hint">Select a Hebrew word above to study it.</p>
        )}
      </section>
    );
  }

  const fields = WORD_FIELDS.filter(([key]) => token[key]);
  const note = token.note;
  return (
    <section className="word-tray" aria-label={`Word study for ${token.surface}`}>
      <div className="word-tray__word">
        <span lang="he" dir="rtl" className="hebrew word-tray__surface">
          {token.surface}
        </span>
        <span className="translit">
          {token.transliteration}
          {token.display_gloss ? `, “${token.display_gloss}”` : null}
        </span>
        {note ? (
          <span className={`verdict verdict-${note.verdict}`}>
            {note.verdict.replace(/_/g, ' ')}
          </span>
        ) : null}
      </div>

      <dl className="word-tray__fields">
        {fields.map(([key, label]) => (
          <div key={key as string}>
            <dt>{label}</dt>
            <dd lang={key === 'lemma' ? 'he' : undefined}>
              {String(token[key])}
              {key === 'greek' && token.greek_strong ? ` · G${token.greek_strong}` : null}
            </dd>
          </div>
        ))}
      </dl>

      <div className="word-tray__note">
        {note ? (
          <>
            <p className="word-tray__range">Range: {note.lexical_gloss}</p>
            <p className="word-tray__rendered">
              <span className="arrow">→</span> <strong>{note.rendered_as}</strong>
            </p>
            <p className="word-tray__prose">{note.note}</p>
          </>
        ) : (
          <p className="word-tray__hint">The analysis made no note about this word.</p>
        )}
      </div>

      <Occurrences key={token.token_id} token={token} englishLayer={englishLayer} />

      <WordChoices
        key={`choices-${token.token_id}`}
        psalmId={psalmId}
        translationId={translationId}
        unitId={unitId}
        token={token}
        englishLayer={englishLayer}
        englishText={englishText}
        positionHint={hint}
        notes={notes}
        codex={codex}
      />
    </section>
  );
}

interface Props {
  row: ComparisonTableRow;
  englishLayer: string;
  selectedTokenId: string | null;
  onSelectToken: (tokenId: string | null) => void;
  onOpenRendering?: (renderingId: string) => void;
  /** Replaces the accuracy and liberties columns while notes are being edited. */
  notesEditor: ReactNode | null;
  /** Verse-level actions and badges, shown between the text and the word tray. */
  actions: ReactNode;
  /** Literal backbone and non-source material, when the evidence is toggled on. */
  evidence: ReactNode | null;
  psalmId: string;
  /** The translation shown; null is the psalm's main one. */
  translationId: string | null;
  codex: VerseCodex;
  /** Set while a rebuild of this verse is running. */
  rebuildProgress: RebuildProgress | null;
  /** Save a human edit of this verse's text; absent when editing is not offered. */
  onSaveText?: (edit: { layer: 'literal' | 'english'; text: string }) => Promise<unknown>;
}

/** Quote the reader's selection inside ``element``, or all of it when nothing is selected. */
function quoteFrom(element: HTMLElement | null): string {
  const selection = window.getSelection();
  const selected = selection?.toString().trim() ?? '';
  if (selected && element && selection?.anchorNode && element.contains(selection.anchorNode)) {
    return selected;
  }
  return element?.textContent?.trim() ?? '';
}

function Progress({ progress }: { progress: RebuildProgress }) {
  const steps = ['Rebuild with your notes', 'Re-analyse the rebuilt text', 'Compare and choose'];
  const shown = progress.total >= 2 ? steps : [steps[0], steps[2]];
  return (
    <section className="rebuild-progress" aria-label="Rebuild in progress" role="status">
      <div className="verse-actions">
        <h4 className="verse-label">Rebuild in progress</h4>
        <span className="verse-actions__spacer" />
        <button type="button" disabled={progress.stopping} onClick={progress.onStop}>
          {progress.stopping ? 'Stopping…' : 'Stop'}
        </button>
      </div>
      <ol className="rebuild-progress__steps">
        {shown.map((label, index) => {
          const state =
            index + 1 < progress.step ? 'done' : index + 1 === progress.step ? 'active' : 'waiting';
          return (
            <li key={label} className={`rebuild-progress__step is-${state}`}>
              <span className="chip">{index + 1}</span>
              <span>
                <strong>{label}</strong>
                <span className="verse-notes__hint">
                  {state === 'active'
                    ? `${progress.label} · ${progress.elapsed}`
                    : state === 'done'
                      ? 'Done'
                      : index === 1
                        ? "Queued · the audit won't see your notes"
                        : 'Nothing changes until you pick a version'}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="verse-notes__hint">
        If Codex goes silent for 10 minutes the rebuild stops on its own and says so.
      </p>
    </section>
  );
}

/**
 * The open verse: the Hebrew word by word, the four texts side by side, and a
 * study tray for the selected word.
 */
export function VerseDetail({
  row,
  englishLayer,
  selectedTokenId,
  onSelectToken,
  onOpenRendering,
  notesEditor,
  actions,
  evidence,
  psalmId,
  translationId,
  codex,
  rebuildProgress,
  onSaveText,
}: Props) {
  const tokens = row.tokens ?? [];
  const selected = tokens.find((token) => token.token_id === selectedTokenId) ?? null;
  const noteIds = new Set(selected?.note?.token_ids ?? []);
  const unitId = row.unit_ids[0];
  const notes = row.verse_notes ?? [];
  const composerId = `note-composer-${unitId}`;
  const [tab, setTab] = useState<'verse' | 'history'>('verse');
  const [studyTab, setStudyTab] = useState<VerseStudyTab>('chat');
  const [quote, setQuote] = useState('');

  const focusComposer = () => {
    setTab('verse');
    setStudyTab('notes');
    window.setTimeout(() => {
      const composer = document.getElementById(composerId);
      composer?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      composer?.focus();
    }, 50);
  };
  const quoteButton = (id: string) => (
    <button
      type="button"
      className="btn-sm quote-button"
      // Keep the reader's selection: a click would otherwise clear it first.
      onMouseDown={(event) => event.preventDefault()}
      onClick={() => {
        setQuote(quoteFrom(document.getElementById(id)));
        focusComposer();
      }}
    >
      Quote in a note
    </button>
  );

  const text = (value: string | null, renderingId: string | undefined, missing: string) => {
    if (!value) return <p className="cell-missing">{missing}</p>;
    if (onOpenRendering && renderingId) {
      return (
        <button
          type="button"
          className="verse-text link-button"
          onClick={() => onOpenRendering(renderingId)}
        >
          {value}
        </button>
      );
    }
    return <p className="verse-text">{value}</p>;
  };

  const [editingLayer, setEditingLayer] = useState<'literal' | 'english' | null>(null);
  const [draftText, setDraftText] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const saveEdit = async () => {
    if (!onSaveText || !editingLayer) return;
    setSaving(true);
    setSaveError(null);
    try {
      await onSaveText({ layer: editingLayer, text: draftText.trim() });
      setEditingLayer(null);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  };

  /** The text, or the box editing it, for one of the two English-side columns. */
  const textOrEditor = (layer: 'literal' | 'english', value: string | null, missing: string) => {
    const renderingId =
      layer === 'literal' ? row.literal_rendering_ids[0] : row.english_rendering_ids[0];
    if (editingLayer !== layer) return text(value, renderingId, missing);
    const status = layer === 'literal' ? row.literal_status : row.english_status;
    const proposes = !renderingId || !(status === 'draft' || status === 'proposed');
    return (
      <div className="verse-edit">
        <label className="visually-hidden" htmlFor={`edit-${layer}-${unitId}`}>
          Edit the {layer} text of {row.display_reference}
        </label>
        <textarea
          id={`edit-${layer}-${unitId}`}
          rows={4}
          value={draftText}
          onChange={(event) => setDraftText(event.target.value)}
        />
        <p className="verse-notes__hint">
          {proposes
            ? 'Saved as a new proposal, because reviewed text only changes through review.'
            : 'Saved over the current text, which is still a draft.'}{' '}
          The verse then needs analysing again.
        </p>
        <div className="verse-edit__actions">
          <button
            type="button"
            className="btn-primary"
            disabled={saving || !draftText.trim()}
            onClick={() => void saveEdit()}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
          <button
            type="button"
            className="btn-sm"
            disabled={saving}
            onClick={() => setEditingLayer(null)}
          >
            Cancel
          </button>
        </div>
        {saveError ? <p className="comparison-error">{saveError}</p> : null}
      </div>
    );
  };

  const editButton = (layer: 'literal' | 'english', value: string | null) =>
    onSaveText && editingLayer !== layer ? (
      <button
        type="button"
        className="btn-sm"
        onClick={() => {
          setEditingLayer(layer);
          setDraftText(value ?? '');
          setSaveError(null);
        }}
      >
        Edit
      </button>
    ) : null;

  const openNotes = notes.filter((note) => note.status === 'open').length;

  return (
    <div
      className="verse-detail"
      // Clicking off the words clears the selection; the word study below keeps it.
      onPointerDown={(event) => {
        if (!selectedTokenId) return;
        const target = event.target as HTMLElement;
        if (!target.closest('.interlinear__word, .word-tray, .verse-study-desk')) {
          onSelectToken(null);
        }
      }}
    >
      <div className="segmented verse-tabs" role="tablist" aria-label="Verse views">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'verse'}
          aria-pressed={tab === 'verse'}
          onClick={() => setTab('verse')}
        >
          Verse{openNotes > 0 ? ` · ${openNotes} note${openNotes === 1 ? '' : 's'}` : ''}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'history'}
          aria-pressed={tab === 'history'}
          onClick={() => setTab('history')}
        >
          History
        </button>
      </div>

      {tab === 'history' ? <VerseHistoryPanel unitId={unitId} /> : null}

      {tab === 'verse' && rebuildProgress ? <Progress progress={rebuildProgress} /> : null}

      {tab === 'verse' && row.pending_rebuild && !rebuildProgress ? (
        <RebuildReview
          key={row.pending_rebuild.rebuild_id}
          psalmId={psalmId}
          unitId={unitId}
          rebuild={row.pending_rebuild}
          notes={notes}
          currentRating={row.accuracy_rating}
          codex={codex}
          onRevise={focusComposer}
        />
      ) : null}

      {tab === 'verse' ? (
        <>
      {tokens.length > 0 ? (
        <div className="interlinear" dir="rtl" lang="he">
          {tokens.map((token) => {
            const isSelected = token.token_id === selectedTokenId || noteIds.has(token.token_id);
            return (
              <button
                key={token.token_id}
                type="button"
                className={[
                  'interlinear__word',
                  token.note ? 'is-noted' : '',
                  isSelected ? 'is-selected' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                aria-pressed={isSelected}
                aria-label={[token.surface, token.transliteration, token.display_gloss]
                  .filter(Boolean)
                  .join(' — ')}
                // Any highlighted word, not just the one clicked, is the selection to clear.
                onClick={() => onSelectToken(isSelected ? null : token.token_id)}
              >
                <span className="interlinear__he">{token.surface}</span>
                <span className="interlinear__tr" dir="ltr">
                  {token.transliteration ?? ' '}
                </span>
                <span className="interlinear__gl" dir="ltr">
                  {token.display_gloss ?? ' '}
                </span>
              </button>
            );
          })}
        </div>
      ) : (
        <p className="interlinear interlinear--plain" dir="rtl" lang="he">
          {row.hebrew_text}
        </p>
      )}

      <div className="verse-columns">
        <div>
          <h4 className="verse-label">Literal {editButton('literal', row.literal_text)}</h4>
          {textOrEditor('literal', row.literal_text, 'No literal rendering selected')}
        </div>
        <div>
          <h4 className="verse-label">
            {englishLayer.replace(/_/g, ' ')} {editButton('english', row.english_text)}
          </h4>
          {textOrEditor(
            'english',
            row.english_text,
            `No ${englishLayer.replace(/_/g, ' ')} rendering selected`,
          )}
        </div>
        {notesEditor ?? (
          <>
            <div>
              <h4 className="verse-label">Accuracy</h4>
              <p className="verse-note" id={`accuracy-${unitId}`}>
                {row.accuracy_note || 'Not assessed yet.'}
              </p>
              {row.accuracy_note ? quoteButton(`accuracy-${unitId}`) : null}
            </div>
            <div>
              <h4 className="verse-label">Creative liberties</h4>
              <p className="verse-note" id={`liberties-${unitId}`}>
                {row.creative_liberties_note || 'None noted.'}
              </p>
              {row.creative_liberties_note ? quoteButton(`liberties-${unitId}`) : null}
            </div>
          </>
        )}
      </div>

      {evidence}

      <div className="verse-actions">{actions}</div>

      <WordTray
        token={selected}
        noted={notedWords(tokens)}
        englishLayer={englishLayer}
        onSelect={onSelectToken}
        psalmId={psalmId}
        translationId={translationId}
        unitId={unitId}
        notes={notes}
        codex={codex}
        englishText={row.english_text}
        hint={
          selected
            ? positionHint(
                selected.note?.token_ids ?? [selected.token_id],
                tokens.map((t) => t.token_id),
              )
            : undefined
        }
      />

      <VerseStudyDesk
        key={`${unitId}-${translationId ?? 'main'}-${englishLayer}`}
        row={row}
        englishLayer={englishLayer}
        psalmId={psalmId}
        translationId={translationId}
        selectedToken={selected}
        activeTab={studyTab}
        onTabChange={setStudyTab}
        notesPanel={
          <VerseNotes
            psalmId={psalmId}
            translationId={translationId}
            unitId={unitId}
            notes={notes}
            englishLayer={englishLayer}
            quote={quote}
            onClearQuote={() => setQuote('')}
            composerId={composerId}
            hasPendingRebuild={Boolean(row.pending_rebuild)}
            codex={codex}
          />
        }
      />
        </>
      ) : null}
    </div>
  );
}

export default VerseDetail;
