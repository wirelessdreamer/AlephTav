import type { ComparisonTableRow } from '../types';
import { RATING_TONE, STATUS_LABELS, VIA_LABELS } from './comparisonLabels';
import { PhoneWarnings, referenceLabel, statusLabel } from './phoneShared';

interface Props {
  row: ComparisonTableRow;
  englishLayer: string;
  selectedTokenId: string | null;
  onSelectToken: (tokenId: string) => void;
  onOpenEvidence: () => void;
  onOpenReview: () => void;
}

/**
 * The verse itself: its Hebrew words, the literal rendering under them, and the
 * English being worked on, with every warning that bears on it. Tapping a word
 * carries it to the evidence screen, which is how a phone replaces hover.
 */
export function PhoneCompare({
  row,
  englishLayer,
  selectedTokenId,
  onSelectToken,
  onOpenEvidence,
  onOpenReview,
}: Props) {
  const tone = row.accuracy_rating ? RATING_TONE[row.accuracy_rating] : null;

  return (
    <>
      <section className="phone-card phone-card--source">
        <div className="phone-card__head">
          <span className="phone-label phone-label--gold">Hebrew source</span>
          <span className="phone-tag">{referenceLabel(row)}</span>
        </div>
        <div className="phone-tokens" dir="rtl" lang="he">
          {row.tokens.map((token) => (
            <button
              type="button"
              key={token.token_id}
              className={`phone-token${
                token.token_id === selectedTokenId ? ' phone-token--selected' : ''
              }`}
              aria-pressed={token.token_id === selectedTokenId}
              onClick={() => onSelectToken(token.token_id)}
            >
              <span className="phone-token__hebrew">{token.surface}</span>
              {token.display_gloss ? (
                <span className="phone-token__gloss" lang="en" dir="ltr">
                  {token.display_gloss}
                </span>
              ) : null}
            </button>
          ))}
        </div>
        <p className="phone-hint">Tap a word for its lexical and morphology evidence.</p>
      </section>

      <section className="phone-card">
        <div className="phone-card__head">
          <span className="phone-label">Literal rendering</span>
          {statusLabel(row.literal_status) ? (
            <span className="phone-tag">{statusLabel(row.literal_status)} · literal</span>
          ) : null}
        </div>
        <p className="phone-text phone-text--literal">
          {row.literal_text ?? 'No literal rendering yet.'}
        </p>
      </section>

      <section className="phone-card">
        <div className="phone-card__head">
          <span className="phone-label phone-label--gold">
            English rendering · {englishLayer.replace(/_/g, ' ')}
          </span>
          {row.assessment_status ? (
            <span className={`phone-tag phone-tag--${row.assessment_status}`}>
              {STATUS_LABELS[row.assessment_status]}
            </span>
          ) : null}
        </div>
        <p className="phone-text">{row.english_text ?? 'No English rendering yet.'}</p>
        <p className="phone-provenance">
          {row.created_via ? VIA_LABELS[row.created_via] : 'Source unrecorded'}
          {row.generator_provider ? (
            <>
              <span className="phone-dot" aria-hidden="true" />
              {row.generator_provider}
            </>
          ) : null}
          {row.accuracy_rating ? (
            <>
              <span className="phone-dot" aria-hidden="true" />
              <span className={`phone-fidelity phone-fidelity--${tone}`}>
                {row.accuracy_rating.replace(/_/g, ' ')}
              </span>
            </>
          ) : null}
        </p>
      </section>

      <PhoneWarnings row={row} />

      <div className="phone-actions">
        <button type="button" onClick={onOpenEvidence}>
          ↗ Word evidence
        </button>
        <button type="button" className="phone-action--primary" onClick={onOpenReview}>
          Review rendering →
        </button>
      </div>

      <p className="phone-caption">
        Hebrew, literal and proposed English stay together as you read this verse.
      </p>
    </>
  );
}
