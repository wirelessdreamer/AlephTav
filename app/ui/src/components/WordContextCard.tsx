import { useLayoutEffect, useRef, useState } from 'react';

import type { ComparisonTableRow, PsalmAnalysisSection, SungLine } from '../types';
import { literalMarks, positionHint } from './verseActions';

/** A hovered Hebrew word and where on screen the word is. */
export interface HoveredWord {
  tokenId: string;
  /** The word's top and bottom edges; the card goes below it, or above when that fits better. */
  top: number;
  bottom: number;
  left: number;
}

export function placeCard(tokenId: string, element: HTMLElement): HoveredWord {
  const rect = element.getBoundingClientRect();
  return {
    tokenId,
    top: rect.top,
    bottom: rect.bottom,
    left: Math.max(8, Math.min(rect.left - 160, window.innerWidth - 440)),
  };
}

const GAP = 8;

function verseNumber(row: ComparisonTableRow): number {
  return Number(row.unit_ids[0]?.split('.')[1]?.replace('v', ''));
}

interface Props {
  hovered: HoveredWord;
  /** The verse the word belongs to, as the comparison table shows it. */
  row: ComparisonTableRow;
  sections: PsalmAnalysisSection[];
  /** The setting's lines in sung order, to find the ones that carry the word. */
  sung: SungLine[];
  englishLayer: string;
}

/**
 * Everything about one Hebrew word of the psalm: the word itself and the analysis note
 * on it, its verse with the word marked, the verse's literal and English, the section
 * it belongs to, and the lines of the setting that sing it.
 */
export function WordContextCard({ hovered, row, sections, sung, englishLayer }: Props) {
  const card = useRef<HTMLDivElement>(null);
  const [top, setTop] = useState<number | null>(null);
  // Placed once its height is known, before it is painted: below the word when it fits,
  // else above, else as far up as keeps it on screen.
  useLayoutEffect(() => {
    const height = card.current?.offsetHeight ?? 0;
    const below = hovered.bottom + GAP;
    const above = hovered.top - GAP - height;
    if (below + height <= window.innerHeight - GAP) setTop(below);
    else if (above >= GAP) setTop(above);
    else setTop(Math.max(GAP, window.innerHeight - height - GAP));
  }, [hovered]);
  const token = (row.tokens ?? []).find((candidate) => candidate.token_id === hovered.tokenId);
  if (!token) return null;
  const verse = verseNumber(row);
  const section = sections.find((s) => verse >= s.first_verse && verse <= s.last_verse);
  const layer = englishLayer.replace(/_/g, ' ');
  const morphology = [token.part_of_speech, token.stem, token.morph_readable]
    .filter(Boolean)
    .join(' · ');
  const verseTokens = (row.tokens ?? []).map((word) => word.token_id);
  // The phrase Codex aligned the word to, when it gave one, placed in the verse and
  // the word placed in the phrase, so repeated words are told apart.
  const link = (row.literal_links ?? []).find((item) => item.token_ids.includes(token.token_id));
  const literal = literalMarks(
    row.literal_text,
    link && {
      text: link.text,
      hint: positionHint(link.token_ids, verseTokens),
      within:
        link.token_ids.length > 1
          ? link.token_ids.indexOf(token.token_id) / (link.token_ids.length - 1)
          : undefined,
    },
    token.display_gloss,
    positionHint([token.token_id], verseTokens),
  );

  // One entry per written line, however many times the setting sings it.
  const singings = new Map<string, { label: string; text: string; times: number }>();
  for (const item of sung) {
    if (!item.line.anchors.some((anchor) => anchor.token_ids.includes(token.token_id))) continue;
    const entry = singings.get(item.line.line_id);
    if (entry) entry.times += 1;
    else singings.set(item.line.line_id, { label: item.section_label, text: item.line.text, times: 1 });
  }

  return (
    <div
      ref={card}
      role="tooltip"
      className="occurrence-card word-context"
      style={{
        top: top ?? hovered.bottom + GAP,
        left: hovered.left,
        visibility: top === null ? 'hidden' : undefined,
      }}
    >
      <div className="occurrence-card__head">
        <strong>{row.display_reference}</strong>
        {section ? <span className="occurrence-card__mt">{section.theme}</span> : null}
      </div>

      <p className="word-context__word">
        <span lang="he" dir="rtl" className="hebrew">
          {token.surface}
        </span>
        {token.transliteration ? <span className="translit">{token.transliteration}</span> : null}
        {token.display_gloss ? <span>“{token.display_gloss}”</span> : null}
      </p>

      <dl className="word-tray__fields occurrence-card__form">
        {token.lemma ? (
          <div>
            <dt>Lemma</dt>
            <dd>
              <span lang="he" className="hebrew">
                {token.lemma}
              </span>
              {token.strong ? ` · ${token.strong}` : null}
            </dd>
          </div>
        ) : null}
        {morphology ? (
          <div>
            <dt>Morphology</dt>
            <dd>{morphology}</dd>
          </div>
        ) : null}
        {token.greek ? (
          <div>
            <dt>LXX</dt>
            <dd>{token.greek}</dd>
          </div>
        ) : null}
      </dl>

      {token.note ? (
        <p className="word-context__note">
          <span className="in-context__label">Analysis </span>
          {token.note.lexical_gloss} → <strong>{token.note.rendered_as}</strong>{' '}
          <span className={`verdict verdict-${token.note.verdict}`}>
            {token.note.verdict.replace(/_/g, ' ')}
          </span>
          <span className="word-context__prose">{token.note.note}</span>
        </p>
      ) : null}

      <p className="occurrence-card__hebrew" dir="rtl" lang="he">
        {(row.tokens ?? []).map((word, index) => (
          <span key={word.token_id}>
            {index > 0 ? ' ' : null}
            {word.token_id === token.token_id ? <mark>{word.surface}</mark> : word.surface}
          </span>
        ))}
      </p>

      {row.literal_text || row.english_text ? (
        <div className="occurrence-card__renderings">
          {row.literal_text ? (
            <div>
              <h5 className="verse-label">Literal</h5>
              <p>
                {literal
                  ? literal.map((run, index) =>
                      run.marked ? <mark key={index}>{run.text}</mark> : <span key={index}>{run.text}</span>,
                    )
                  : row.literal_text}
              </p>
            </div>
          ) : null}
          {row.english_text ? (
            <div>
              <h5 className="verse-label">{layer}</h5>
              <p>{row.english_text}</p>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="word-tray__hint">This verse has no literal or {layer} rendering yet.</p>
      )}

      <div className="word-context__sung">
        <h5 className="verse-label">In this setting</h5>
        {singings.size === 0 ? (
          <p className="word-tray__hint">No line sings this word.</p>
        ) : (
          <ul>
            {[...singings].map(([lineId, entry]) => (
              <li key={lineId}>
                <span className="in-context__label">
                  {entry.label}
                  {entry.times > 1 ? ` · sung ${entry.times} times` : ''}{' '}
                </span>
                {entry.text}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default WordContextCard;
