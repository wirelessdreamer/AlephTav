import type { ComparisonTableRow, StudyToken } from '../types';
import { referenceLabel } from './phoneShared';

/** Lexical fields in the order the verse detail shows them, plus the roles. */
const FIELDS: Array<[keyof StudyToken, string]> = [
  ['morph_readable', 'Form'],
  ['part_of_speech', 'Part of speech'],
  ['stem', 'Stem'],
  ['word_sense', 'Sense'],
  ['semantic_role', 'Role'],
  ['syntax_role', 'Syntax'],
  ['referent', 'Referent'],
  ['greek', 'LXX'],
];

/** The literal text with the span this word renders marked, where the links say. */
function AlignedSpan({ row, token }: { row: ComparisonTableRow; token: StudyToken }) {
  const links = row.literal_links ?? [];
  const link = links.find((item) => item.token_ids.includes(token.token_id));
  if (!row.literal_text) return null;

  const at = link ? row.literal_text.indexOf(link.text) : -1;
  return (
    <section className="phone-card">
      <div className="phone-card__head">
        <span className="phone-label phone-label--gold">Aligned English span</span>
        {link ? (
          <span className="phone-tag">{link.token_ids.length > 1 ? 'Grouped' : 'Word'}</span>
        ) : null}
      </div>
      <p className="phone-text phone-text--literal">
        {at < 0 ? (
          row.literal_text
        ) : (
          <>
            {row.literal_text.slice(0, at)}
            <mark>{link?.text}</mark>
            {row.literal_text.slice(at + (link?.text.length ?? 0))}
          </>
        )}
      </p>
      <p className="phone-caption">
        {link
          ? 'The alignment recorded for this verse links this word to the marked span.'
          : 'No span is aligned to this word yet; the whole literal rendering is shown.'}
      </p>
    </section>
  );
}

interface Props {
  row: ComparisonTableRow;
  token: StudyToken | null;
  onBack: () => void;
}

/**
 * One Hebrew word, with everything the corpus records about it. Hover has no
 * phone equivalent, so the word chosen on the compare screen is shown here whole.
 */
export function PhoneEvidence({ row, token, onBack }: Props) {
  if (!token) {
    return (
      <section className="phone-card">
        <p className="phone-hint">This verse records no Hebrew words.</p>
      </section>
    );
  }

  const fields = FIELDS.filter(([field]) => typeof token[field] === 'string' && token[field]);
  const note = token.note;

  return (
    <>
      <section className="phone-card phone-card--source">
        <div className="phone-card__head">
          <span className="phone-label phone-label--gold">Selected source token</span>
          <span className="phone-tag">{referenceLabel(row)}</span>
        </div>
        <div className="phone-word">
          <div>
            {token.transliteration ? <strong>{token.transliteration}</strong> : null}
            <p className="phone-word__ids">
              {token.strong ? `Strong's ${token.strong}` : null}
              {token.strong && token.lemma ? ' · ' : null}
              {token.lemma ? (
                <>
                  lemma{' '}
                  <span lang="he" dir="rtl">
                    {token.lemma}
                  </span>
                </>
              ) : null}
            </p>
          </div>
          <span className="phone-word__hebrew" lang="he" dir="rtl">
            {token.surface}
          </span>
        </div>
        {token.display_gloss ? <p className="phone-definition">{token.display_gloss}</p> : null}
        {fields.length > 0 ? (
          <dl className="phone-details">
            {fields.map(([field, label]) => (
              <div key={field}>
                <dt>{label}</dt>
                <dd>{String(token[field])}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </section>

      <AlignedSpan row={row} token={token} />

      {note ? (
        <section className="phone-card">
          <div className="phone-card__head">
            <span className="phone-label">Analysis note</span>
            <span className={`phone-tag verdict-${note.verdict}`}>
              {note.verdict.replace(/_/g, ' ')}
            </span>
          </div>
          <p className="phone-text phone-text--literal">
            {note.lexical_gloss} → <strong>{note.rendered_as}</strong>
          </p>
          <p className="phone-caption">{note.note}</p>
        </section>
      ) : null}

      {token.occurrence_count > 0 ? (
        <section className="phone-card">
          <div className="phone-card__head">
            <span className="phone-label">Elsewhere in the corpus</span>
            <span className="phone-tag">{token.occurrence_count}</span>
          </div>
          <p className="phone-caption">{token.occurrence_refs.slice(0, 12).join(' · ')}</p>
        </section>
      ) : null}

      <button type="button" className="phone-back" onClick={onBack}>
        ← Return to the verse
      </button>
    </>
  );
}
