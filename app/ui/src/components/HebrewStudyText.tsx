import { useCallback, useEffect, useRef, useState } from 'react';

import type { StudyToken } from '../types';

interface Anchor {
  token: StudyToken;
  top: number;
  left: number;
  pinned: boolean;
}

/** Field order for the card body. Absent fields are skipped entirely. */
const DETAIL_ROWS: Array<[keyof StudyToken, string]> = [
  ['lemma', 'Lemma'],
  ['strong', "Strong's"],
  ['morph_readable', 'Morphology'],
  ['part_of_speech', 'Part of speech'],
  ['stem', 'Stem'],
  ['word_sense', 'Word sense'],
  ['semantic_role', 'Semantic role'],
  ['syntax_role', 'Syntax role'],
  ['referent', 'Referent'],
  ['greek', 'LXX Greek'],
  ['greek_strong', 'Greek Strong'],
];

function StudyCard({ anchor, onClose }: { anchor: Anchor; onClose: () => void }) {
  const { token } = anchor;
  const rows = DETAIL_ROWS.filter(([key]) => token[key]);

  return (
    <div
      className="study-card"
      role={anchor.pinned ? 'dialog' : 'tooltip'}
      aria-label={`Study card for ${token.surface}`}
      style={{ top: anchor.top, left: anchor.left }}
    >
      <div className="study-card__head">
        <span className="study-card__surface" dir="rtl" lang="he">
          {token.surface}
        </span>
        {anchor.pinned ? (
          <button type="button" className="study-card__close" onClick={onClose} aria-label="Close">
            ×
          </button>
        ) : null}
      </div>

      {token.transliteration ? (
        <p className="study-card__translit">{token.transliteration}</p>
      ) : null}

      {token.display_gloss ? <p className="study-card__gloss">{token.display_gloss}</p> : null}

      {rows.length > 0 ? (
        <dl className="study-card__details">
          {rows.map(([key, label]) => (
            <div key={key as string}>
              <dt>{label}</dt>
              <dd dir={key === 'lemma' ? 'rtl' : undefined}>{String(token[key])}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {token.note ? (
        <div className={`study-card__note verdict-${token.note.verdict}`}>
          <h5>
            Translation note
            <span className="verdict-chip">{token.note.verdict.replace(/_/g, ' ')}</span>
          </h5>
          <p className="study-card__rendered">
            <span className="study-card__lexical">{token.note.lexical_gloss}</span>
            {' → '}
            <strong>{token.note.rendered_as}</strong>
          </p>
          <p>{token.note.note}</p>
        </div>
      ) : null}

      {token.occurrence_count > 0 ? (
        <p className="study-card__occurrences">
          <strong>{token.occurrence_count}</strong> occurrence(s)
          {token.occurrence_refs.length > 0 ? `: ${token.occurrence_refs.join(' · ')}` : null}
          {token.occurrence_count > token.occurrence_refs.length ? ' …' : null}
        </p>
      ) : null}

      {!anchor.pinned ? <p className="study-card__hint">Click the word to keep this open</p> : null}
    </div>
  );
}

interface Props {
  tokens: StudyToken[];
  /** Fallback when a row has no per-token data. */
  text: string;
}

/**
 * Hebrew rendered word by word, each word a hover/focus study target.
 *
 * The card is positioned from the word's bounding rect and rendered fixed, so
 * the table's horizontal scroll container cannot clip it.
 */
export function HebrewStudyText({ tokens, text }: Props) {
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const containerRef = useRef<HTMLSpanElement | null>(null);

  const show = useCallback((token: StudyToken, element: HTMLElement, pinned: boolean) => {
    const rect = element.getBoundingClientRect();
    setAnchor({
      token,
      // Below the word, nudged left so a wide card stays on screen.
      top: Math.min(rect.bottom + 6, window.innerHeight - 24),
      left: Math.max(8, Math.min(rect.left - 120, window.innerWidth - 340)),
      pinned,
    });
  }, []);

  const clearIfUnpinned = useCallback(() => {
    setAnchor((current) => (current && current.pinned ? current : null));
  }, []);

  useEffect(() => {
    if (!anchor?.pinned) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setAnchor(null);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [anchor?.pinned]);

  if (tokens.length === 0) {
    return (
      <span dir="rtl" lang="he">
        {text}
      </span>
    );
  }

  return (
    <>
      <span className="hebrew-study" dir="rtl" lang="he" ref={containerRef}>
        {tokens.map((token) => (
          <button
            key={token.token_id}
            type="button"
            className={[
              'study-word',
              // A quiet underline marks the words the analysis remarked on, so
              // the language lab is discoverable without hovering every word.
              token.note ? 'study-word--noted' : '',
              anchor?.token.token_id === token.token_id && anchor.pinned
                ? 'study-word--pinned'
                : '',
            ]
              .filter(Boolean)
              .join(' ')}
            onMouseEnter={(event) => show(token, event.currentTarget, false)}
            onMouseLeave={clearIfUnpinned}
            onFocus={(event) => show(token, event.currentTarget, false)}
            onBlur={clearIfUnpinned}
            onClick={(event) => show(token, event.currentTarget, true)}
            aria-label={token.display_gloss ? `${token.surface} — ${token.display_gloss}` : token.surface}
          >
            {token.surface}
          </button>
        ))}
      </span>
      {anchor ? <StudyCard anchor={anchor} onClose={() => setAnchor(null)} /> : null}
    </>
  );
}

export default HebrewStudyText;
