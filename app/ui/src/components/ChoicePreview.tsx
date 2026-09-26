import { useLayoutEffect, useRef, useState } from 'react';

import type {
  ComparisonTableRow,
  PsalmAnalysisSection,
  WordNote,
  WordSuggestion,
} from '../types';
import { InContext } from './InContext';
import { choiceInVerse, layerLabel, phraseInContext, type ContextRun } from './verseActions';

/** How many verses either side of the word's verse the preview shows; 'all' is the psalm. */
export type PreviewSpread = 2 | 5 | 10 | 'all';

export interface PreviewTarget {
  row: ComparisonTableRow;
  tokenIds: string[];
  verse: string;
  surface: string;
  transliteration: string;
  note: WordNote | null;
  choice: WordSuggestion;
  hint: number | undefined;
  picked: boolean;
}

interface Props {
  target: PreviewTarget;
  /** Every row of the psalm, in order, for the surrounding passage. */
  rows: ComparisonTableRow[];
  sections: PsalmAnalysisSection[];
  englishLayer: string;
  spread: PreviewSpread;
  top: number;
  left: number;
  width: number;
  onEnter: () => void;
  onLeave: () => void;
}

/** From this width the why and the passage sit side by side, each scrolling on its own. */
const WIDE = 600;

function verseNumber(row: ComparisonTableRow): number {
  return Number(row.unit_ids[0]?.split('.')[1]?.replace('v', ''));
}

/** Runs keep their line breaks here; the passage is read as lines, not one string. */
function Lines({ runs }: { runs: ContextRun[] }) {
  return (
    <span className="choice-preview__lines">
      {runs.map((run, index) =>
        run.marked ? <mark key={index}>{run.text}</mark> : <span key={index}>{run.text}</span>,
      )}
    </span>
  );
}

/**
 * Everything around a word choice: why the choice was offered, the section it
 * belongs to, the Hebrew and literal of its verse, and the passage it sits in with
 * the choice swapped in.
 */
export function ChoicePreview({
  target,
  rows,
  sections,
  englishLayer,
  spread,
  top,
  left,
  width,
  onEnter,
  onLeave,
}: Props) {
  const { row, choice, note } = target;
  const wide = width >= WIDE;
  const card = useRef<HTMLDivElement>(null);
  const passageList = useRef<HTMLOListElement>(null);
  const [placedTop, setPlacedTop] = useState(top);
  // Placed once its height is known: kept on screen, and a target verse past the
  // fold of the passage (a long stretch of psalm) scrolled into the middle of it.
  useLayoutEffect(() => {
    const element = card.current;
    const scroller = wide ? passageList.current : element;
    if (!element || !scroller) return;
    setPlacedTop(Math.max(12, Math.min(top, window.innerHeight - element.offsetHeight - 12)));
    scroller.scrollTop = 0;
    const verse = scroller.querySelector<HTMLElement>('.choice-preview__verse-row.is-target');
    if (!verse) return;
    const box = verse.getBoundingClientRect();
    const view = scroller.getBoundingClientRect();
    if (box.bottom > view.bottom) {
      scroller.scrollTop = box.top - view.top - (scroller.clientHeight - box.height) / 2;
    }
  }, [top, target, spread, wide]);
  const at = rows.findIndex((candidate) => candidate.unit_ids[0] === row.unit_ids[0]);
  const from = spread === 'all' ? 0 : Math.max(0, at - spread);
  const to = spread === 'all' ? rows.length - 1 : Math.min(rows.length - 1, at + spread);
  const passage = at >= 0 ? rows.slice(from, to + 1) : [row];
  const sectionStarting = (verse: number) => sections.find((s) => s.first_verse === verse);
  const section = sections.find(
    (s) => verseNumber(row) >= s.first_verse && verseNumber(row) <= s.last_verse,
  );
  // The section the passage opens inside, when it does not start at the passage's top.
  const openSection =
    passage.length > 0 && !sectionStarting(verseNumber(passage[0]))
      ? sections.find(
          (s) =>
            verseNumber(passage[0]) >= s.first_verse && verseNumber(passage[0]) <= s.last_verse,
        )
      : undefined;
  const swapped = choiceInVerse(choice, row.english_text, note?.rendered_as, target.hint);
  const current = phraseInContext(row.english_text, note?.rendered_as, target.hint);
  const layer = layerLabel(englishLayer).toLowerCase();

  return (
    <div
      ref={card}
      className={`choice-preview${wide ? ' is-wide' : ''}`}
      role="tooltip"
      style={{ top: placedTop, left, width }}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
    >
      <div className="choice-preview__aside">
        <div className="choice-preview__head">
          <span className="choice-preview__verse">{target.verse}</span>
          <span lang="he" dir="rtl" className="hebrew">
            {target.surface}
          </span>
          <span className="translit">{target.transliteration}</span>
          <span className="arrow">→</span>
          <strong className="choice-preview__choice">{choice.text}</strong>
          {target.picked ? <span className="chip chip-gold">your pick</span> : null}
          {choice.earlier ? <span className="chip">from an earlier list</span> : null}
        </div>

        <dl className="choice-preview__why">
          {choice.sense ? (
            <>
              <dt>Sense</dt>
              <dd>{choice.sense}</dd>
            </>
          ) : null}
          {choice.rationale ? (
            <>
              <dt>Gains and losses</dt>
              <dd>{choice.rationale}</dd>
            </>
          ) : null}
          {choice.fit ? (
            <>
              <dt>Fit</dt>
              <dd className="choice-preview__fit">{choice.fit}</dd>
            </>
          ) : null}
        </dl>

        {note ? (
          <p className="choice-preview__analysis">
            <span className="in-context__label">Now </span>
            <strong>{note.rendered_as}</strong>{' '}
            <span className={`verdict verdict-${note.verdict}`}>
              {note.verdict.replace(/_/g, ' ')}
            </span>{' '}
            · range: {note.lexical_gloss}
          </p>
        ) : null}

        {section ? (
          <p className="choice-preview__section">
            <span className="verse-band__range">
              {section.first_verse === section.last_verse
                ? `v. ${section.first_verse}`
                : `vv. ${section.first_verse}–${section.last_verse}`}
            </span>{' '}
            {section.theme}
          </p>
        ) : null}

        <span lang="he" dir="rtl" className="choice-preview__hebrew">
          {(row.tokens ?? []).map((token) => (
            <span key={token.token_id}>
              {target.tokenIds.includes(token.token_id) ? (
                <mark>{token.surface}</mark>
              ) : (
                token.surface
              )}{' '}
            </span>
          ))}
        </span>
        {row.literal_text ? (
          <span className="choice-preview__literal">
            <span className="in-context__label">Literal </span>
            {row.literal_text}
          </span>
        ) : null}
      </div>

      <ol
        ref={passageList}
        className="choice-preview__passage"
        aria-label={`The ${layer} around ${target.verse}`}
      >
        {openSection && openSection !== section ? (
          <li className="choice-preview__band">{openSection.theme}</li>
        ) : null}
        {passage.map((candidate) => {
          const number = verseNumber(candidate);
          const starts = sectionStarting(number);
          const isTarget = candidate.unit_ids[0] === row.unit_ids[0];
          return [
            starts && candidate !== passage[0] ? (
              <li key={`band-${number}`} className="choice-preview__band">
                {starts.theme}
                {starts.arc_note ? <span className="note-prose">{starts.arc_note}</span> : null}
              </li>
            ) : null,
            <li
              key={candidate.unit_ids[0]}
              className={`choice-preview__verse-row${isTarget ? ' is-target' : ''}`}
            >
              <span className="choice-preview__number">{number}</span>
              <span className="choice-preview__text">
                {isTarget && swapped ? (
                  <Lines runs={swapped} />
                ) : (
                  <span className="choice-preview__lines">
                    {candidate.english_text ?? <em className="cell-missing">Not translated</em>}
                  </span>
                )}
                {isTarget && current ? (
                  <span className="choice-preview__was">
                    now: <InContext runs={current} />
                  </span>
                ) : null}
              </span>
            </li>,
          ];
        })}
      </ol>
    </div>
  );
}

export default ChoicePreview;
