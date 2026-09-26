import { Fragment, useEffect, useMemo, useRef, useState } from 'react';

import type {
  ComparisonTableRow,
  PsalmAnalysisSection,
  VerseNote,
  WordNote,
  WordSuggestions,
} from '../types';
import { ChoicePreview, type PreviewSpread, type PreviewTarget } from './ChoicePreview';
import { InContext } from './InContext';
import {
  choiceInContext,
  layerLabel,
  phraseInContext,
  pickedChoice,
  positionHint,
  type VerseCodex,
} from './verseActions';
import { useWordPick, WordChoices } from './WordChoices';

/** A word that matters in the psalm: what it says now, what was offered, what was picked. */
export interface WordSummaryItem {
  key: string;
  row: ComparisonTableRow;
  verse: string;
  tokenIds: string[];
  surface: string;
  transliteration: string;
  /** The analysis's verdict on how the word is rendered now. */
  note: WordNote | null;
  choices: WordSuggestions | null;
  picks: Array<{ choice: string; status: VerseNote['status'] }>;
}

function overlaps(a: string[], b: string[]): boolean {
  return a.some((id) => b.includes(id));
}

function summarise(rows: ComparisonTableRow[]): WordSummaryItem[] {
  const items: WordSummaryItem[] = [];
  for (const row of rows) {
    const [, verseNumber] = row.display_reference.split(':');
    const verse = verseNumber ? `v. ${verseNumber}` : 'heading';
    const tokens = row.tokens ?? [];
    const position = (ids: string[]) => tokens.findIndex((token) => ids.includes(token.token_id));
    const inRow: WordSummaryItem[] = [];
    const itemFor = (tokenIds: string[]): WordSummaryItem => {
      const existing = inRow.find((item) => overlaps(item.tokenIds, tokenIds));
      if (existing) return existing;
      const words = tokens.filter((token) => tokenIds.includes(token.token_id));
      const item: WordSummaryItem = {
        key: `${row.mt_reference}|${tokenIds.join(',')}`,
        row,
        verse,
        tokenIds,
        surface: words.map((token) => token.surface).join(' '),
        transliteration: words.map((token) => token.transliteration ?? '').join(' ').trim(),
        note: null,
        choices: null,
        picks: [],
      };
      inRow.push(item);
      return item;
    };

    for (const token of tokens) {
      if (token.note) {
        const item = itemFor(token.note.token_ids);
        item.note ??= token.note;
        if (token.note.transliteration) item.transliteration = token.note.transliteration;
      }
    }
    for (const entry of row.word_choices ?? []) {
      if (entry.suggestions.length > 0) itemFor(entry.token_ids).choices = entry;
    }
    for (const note of row.verse_notes ?? []) {
      if (note.token_ids?.length) {
        itemFor(note.token_ids).picks.push({ choice: pickedChoice(note.text), status: note.status });
      }
    }
    inRow.sort((a, b) => position(a.tokenIds) - position(b.tokenIds));
    items.push(...inRow);
  }
  return items;
}

/** Words the batch should ask about: no choices yet, or an outdated list of them. */
export function needsChoices(item: WordSummaryItem): boolean {
  return !item.choices || Boolean(item.choices.outdated);
}

export interface WordBatchProgress {
  label: string;
  done: number;
  total: number;
  elapsed: string;
  stopping: boolean;
  onStop: () => void;
}

interface Props {
  psalmId: string;
  translationId: string | null;
  rows: ComparisonTableRow[];
  englishLayer: string;
  codex: Pick<VerseCodex, 'ready' | 'hint' | 'busy'>;
  /** Ask for one word's choices; rejects with the reason when Codex fails. */
  onSuggest: (row: ComparisonTableRow, tokenIds: string[]) => Promise<void>;
  /** Ask for choices for every listed word, one Codex turn each. */
  onSuggestAll: (items: WordSummaryItem[]) => void;
  /** Set while the batch runs. */
  progress: WordBatchProgress | null;
  /** Open the word's verse with the word selected. */
  onOpenWord: (row: ComparisonTableRow, tokenId: string) => void;
  /** Every row of the psalm, unfiltered, for the passage around a hovered choice. */
  contextRows: ComparisonTableRow[];
  sections: PsalmAnalysisSection[];
}

/** Choices shown in their line; the rest are short, their line on hover. */
const LINED = 3;

const SPREADS: Array<[PreviewSpread, string]> = [
  [2, '±2 verses'],
  [5, '±5 verses'],
  [10, '±10 verses'],
  ['all', 'Whole psalm'],
];
const SPREAD_KEY = 'alephtav.choice-preview.spread';

function savedSpread(): PreviewSpread {
  try {
    const value = window.localStorage.getItem(SPREAD_KEY);
    const found = SPREADS.find(([spread]) => String(spread) === value);
    return found ? found[0] : 5;
  } catch {
    return 5;
  }
}

/**
 * Every word choice in the psalm in one place: the analysis, the options, and the
 * reviewer's picks. Choices can be generated for every word at once and picked here,
 * then reviewed in each verse.
 */
export function WordSummary({
  psalmId,
  translationId,
  rows,
  englishLayer,
  codex,
  onSuggest,
  onSuggestAll,
  progress,
  onOpenWord,
  contextRows,
  sections,
}: Props) {
  const [open, setOpen] = useState(false);
  const [details, setDetails] = useState<string | null>(null);
  const items = useMemo(() => summarise(rows), [rows]);
  const pick = useWordPick(psalmId, translationId);
  const [spread, setSpread] = useState<PreviewSpread>(savedSpread);
  const [preview, setPreview] = useState<{
    target: PreviewTarget;
    top: number;
    left: number;
    width: number;
  } | null>(null);
  const hideTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!preview) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPreview(null);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [preview]);

  if (items.length === 0) return null;

  const chooseSpread = (value: PreviewSpread) => {
    setSpread(value);
    try {
      window.localStorage.setItem(SPREAD_KEY, String(value));
    } catch {
      // A remembered preference only; the default serves without it.
    }
  };
  const keepPreview = () => window.clearTimeout(hideTimer.current);
  // A short grace period lets the pointer travel from the choice onto the card.
  const hidePreview = () => {
    hideTimer.current = window.setTimeout(() => setPreview(null), 200);
  };
  const showPreview = (target: PreviewTarget, element: HTMLElement) => {
    keepPreview();
    // Beside the row's choices, on the roomier side, so moving between them never
    // crosses the card.
    const group = (element.closest('.word-summary__chips') ?? element).getBoundingClientRect();
    const roomLeft = group.left - 24;
    const roomRight = window.innerWidth - group.right - 24;
    const width = Math.min(960, window.innerWidth - 24, Math.max(320, roomLeft, roomRight));
    const beside = roomLeft >= roomRight ? group.left - 12 - width : group.right + 12;
    const left = Math.max(12, Math.min(beside, window.innerWidth - width - 12));
    // The card moves itself up once it knows its height.
    const top = Math.max(12, element.getBoundingClientRect().top - 120);
    setPreview({ target, top, left, width });
  };

  const missing = items.filter(needsChoices);
  const offered = items.filter((item) => item.choices).length;
  const queued = items.filter((item) => item.picks.some((p) => p.status === 'open')).length;
  const layer = layerLabel(englishLayer).toLowerCase();
  const blocked = !codex.ready ? codex.hint : codex.busy ? 'Codex is busy with another task.' : undefined;

  return (
    <section className="analysis-panel" aria-label="Word analysis">
      <header className="analysis-panel__head">
        <button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
          {open ? '▾' : '▸'} Word analysis: choices that matter
        </button>
        <span className="numbering">
          {items.length} word{items.length === 1 ? '' : 's'} · {offered} with choices ·{' '}
          {queued} pick{queued === 1 ? '' : 's'} queued
        </span>
      </header>

      {open || progress ? (
        <div className="word-summary__batch">
          {progress ? (
            <>
              <span className="batch-progress" role="status">
                {progress.stopping
                  ? 'Stopping…'
                  : `Suggesting choices for ${progress.label} (${progress.done + 1} of ${progress.total}) · ${progress.elapsed}`}
              </span>
              <button type="button" disabled={progress.stopping} onClick={progress.onStop}>
                {progress.stopping ? 'Stopping…' : 'Stop'}
              </button>
            </>
          ) : (
            <>
              <div className="segmented" role="group" aria-label="Context shown when hovering a choice">
                {SPREADS.map(([value, label]) => (
                  <button
                    key={String(value)}
                    type="button"
                    aria-pressed={spread === value}
                    onClick={() => chooseSpread(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <span className="verse-notes__hint">
                {missing.length > 0
                  ? `${missing.length} word${missing.length === 1 ? ' needs' : 's need'} choices for the ${layer}: none yet, or an older list (made under earlier guidance, or before choices covered the whole range).`
                  : `Every word has choices for the ${layer}. Pick one per word, then review each in its verse.`}
              </span>
              {missing.length > 0 ? (
                <button
                  type="button"
                  className="btn-primary"
                  disabled={Boolean(blocked)}
                  title={blocked}
                  onClick={() => {
                    setOpen(true);
                    onSuggestAll(missing);
                  }}
                >
                  Suggest choices for {missing.length} word{missing.length === 1 ? '' : 's'}
                </button>
              ) : null}
            </>
          )}
        </div>
      ) : null}

      {open ? (
        <div className="word-summary" role="table" aria-label="Word choices in this psalm">
          <div className="word-summary__row word-summary__row--head" role="row">
            <span role="columnheader">Word</span>
            <span role="columnheader">{layerLabel(englishLayer)} now</span>
            <span role="columnheader">Choices · click to pick</span>
            <span role="columnheader">Your pick</span>
          </div>
          {items.map((item) => {
            const picked = new Set(
              item.picks.filter((p) => p.status === 'open').map((p) => p.choice),
            );
            const suggestions = item.choices?.suggestions ?? [];
            const token = (item.row.tokens ?? []).find((t) => t.token_id === item.tokenIds[0]);
            const expanded = details === item.key;
            const englishText = item.row.english_text;
            const previewOf = (choice: WordSuggestions['suggestions'][number]): PreviewTarget => ({
              row: item.row,
              tokenIds: item.tokenIds,
              verse: item.verse,
              surface: item.surface,
              transliteration: item.transliteration,
              note: item.note,
              choice,
              hint,
              picked: picked.has(choice.text),
            });
            const hint = positionHint(
              item.tokenIds,
              (item.row.tokens ?? []).map((t) => t.token_id),
            );
            const unitId = item.row.unit_ids[0];
            const choiceButton = (
              choice: WordSuggestions['suggestions'][number],
              compact: boolean,
            ) => (
              <button
                key={choice.text}
                type="button"
                className={`word-summary__choice${compact ? ' is-compact' : ''}${picked.has(choice.text) ? ' is-picked' : ''}`}
                aria-pressed={picked.has(choice.text)}
                aria-label={`Pick “${choice.text}”`}
                disabled={pick.pending}
                onMouseEnter={(event) => showPreview(previewOf(choice), event.currentTarget)}
                onFocus={(event) => showPreview(previewOf(choice), event.currentTarget)}
                onMouseLeave={hidePreview}
                onBlur={hidePreview}
                onClick={() =>
                  void pick
                    .toggle({
                      unitId,
                      tokenIds: item.tokenIds,
                      name: item.transliteration || item.surface,
                      surface: item.surface,
                      choice: choice.text,
                      notes: item.row.verse_notes ?? [],
                    })
                    .catch(() => undefined)
                }
              >
                {/* The line shows the choice in place; alone when short or no line is known. */}
                {compact ? (
                  choice.text
                ) : (
                  <InContext
                    runs={choiceInContext(choice, englishText, item.note?.rendered_as, hint)}
                    fallback={choice.text}
                  />
                )}
              </button>
            );
            return (
              <Fragment key={item.key}>
                <div
                  className={`word-summary__row${expanded ? ' is-expanded' : ''}`}
                  role="row"
                >
                  <span role="cell" className="word-summary__word">
                    <span className="word-summary__verse">{item.verse}</span>
                    <span lang="he" dir="rtl" className="hebrew">
                      {item.surface}
                    </span>
                    <span className="translit">{item.transliteration}</span>
                    <span className="word-summary__links">
                      <button
                        type="button"
                        className="btn-sm"
                        onClick={() => onOpenWord(item.row, item.tokenIds[0])}
                      >
                        Review in verse
                      </button>
                      {token ? (
                        <button
                          type="button"
                          className="btn-sm btn-ghost"
                          aria-expanded={expanded}
                          onClick={() => setDetails(expanded ? null : item.key)}
                        >
                          {expanded ? 'Hide details' : 'Details'}
                        </button>
                      ) : null}
                    </span>
                  </span>

                  <span role="cell" className="word-summary__now">
                    {item.note ? (
                      <>
                        <span>
                          <strong>{item.note.rendered_as}</strong>{' '}
                          <span className={`verdict verdict-${item.note.verdict}`}>
                            {item.note.verdict.replace(/_/g, ' ')}
                          </span>
                        </span>
                        <InContext runs={phraseInContext(englishText, item.note.rendered_as, hint)} />
                        <span className="verse-notes__hint">Range: {item.note.lexical_gloss}</span>
                        <span className="note-prose">{item.note.note}</span>
                      </>
                    ) : (
                      <span className="verse-notes__hint">Not remarked on by the analysis.</span>
                    )}
                  </span>

                  <span role="cell" className="word-summary__choices">
                    {suggestions.length > 0 ? (
                      <>
                        <span className="word-summary__chips">
                          {suggestions.slice(0, LINED).map((choice) => choiceButton(choice, false))}
                        </span>
                        {suggestions.length > LINED ? (
                          <span className="word-summary__more">
                            {suggestions.slice(LINED).map((choice) => choiceButton(choice, true))}
                          </span>
                        ) : null}
                        {item.choices?.outdated ? (
                          <span className="word-summary__outdated">
                            {item.choices.outdated_reason === 'prompt'
                              ? 'an older, narrower list'
                              : 'made under earlier guidance'}
                          </span>
                        ) : null}
                      </>
                    ) : (
                      <span className="verse-notes__hint">
                        {progress ? 'Waiting…' : 'None asked for yet'}
                      </span>
                    )}
                  </span>

                  <span role="cell" className="word-summary__pick">
                    {item.picks.length > 0 ? (
                      item.picks.map((p) => (
                        <span key={`${p.choice}-${p.status}`}>
                          <strong>“{p.choice}”</strong>{' '}
                          <span className={`chip${p.status === 'addressed' ? ' chip-good' : ''}`}>
                            {p.status === 'addressed' ? 'applied' : 'queued for rebuild'}
                          </span>
                        </span>
                      ))
                    ) : (
                      <span className="verse-notes__hint">—</span>
                    )}
                  </span>
                </div>
                {expanded && token ? (
                  <div className="word-summary__details">
                    <WordChoices
                      psalmId={psalmId}
                      translationId={translationId}
                      unitId={unitId}
                      token={token}
                      tokenIds={item.tokenIds}
                      surface={item.surface}
                      englishLayer={englishLayer}
                      notes={item.row.verse_notes ?? []}
                      englishText={englishText}
                      positionHint={hint}
                      codex={{ ...codex, suggest: (ids) => onSuggest(item.row, ids) }}
                    />
                  </div>
                ) : null}
              </Fragment>
            );
          })}
          {pick.error ? <p className="comparison-error">{String(pick.error)}</p> : null}
        </div>
      ) : null}
      {preview ? (
        <ChoicePreview
          target={preview.target}
          rows={contextRows}
          sections={sections}
          englishLayer={englishLayer}
          spread={spread}
          top={preview.top}
          left={preview.left}
          width={preview.width}
          onEnter={keepPreview}
          onLeave={hidePreview}
        />
      ) : null}
    </section>
  );
}

export default WordSummary;
