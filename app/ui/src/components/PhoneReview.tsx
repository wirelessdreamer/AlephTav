import { useState } from 'react';

import {
  useCreateComparisonAssessment,
  useReviseComparisonAssessment,
} from '../hooks/useComparisonAssessments';
import type { AccuracyRating, ComparisonTableRow } from '../types';
import { ACCURACY_RATINGS, RATING_TONE, STATUS_LABELS, VIA_LABELS } from './comparisonLabels';
import { PhoneWarnings, statusLabel } from './phoneShared';

interface Props {
  row: ComparisonTableRow;
  psalmId: string | null;
  translationId: string | null;
  englishLayer: string;
  onOpenEvidence: () => void;
}

/**
 * What a reviewer needs before judging the English: the rendering, the source it
 * answers to, the warnings against it, and the rules that govern accepting it. The
 * assessment written here is the same record the desktop table writes.
 */
export function PhoneReview({ row, psalmId, translationId, englishLayer, onOpenEvidence }: Props) {
  const createAssessment = useCreateComparisonAssessment(psalmId);
  const reviseAssessment = useReviseComparisonAssessment(psalmId);
  const [editing, setEditing] = useState(false);
  const [rating, setRating] = useState<AccuracyRating | ''>(row.accuracy_rating ?? '');
  const [accuracyNote, setAccuracyNote] = useState(row.accuracy_note);
  const [libertiesNote, setLibertiesNote] = useState(row.creative_liberties_note);
  const saving = createAssessment.isPending || reviseAssessment.isPending;
  const error = createAssessment.error ?? reviseAssessment.error;
  const tone = row.accuracy_rating ? RATING_TONE[row.accuracy_rating] : null;
  const openNotes = row.verse_notes.filter((note) => note.status === 'open');

  function startEditing() {
    setRating(row.accuracy_rating ?? '');
    setAccuracyNote(row.accuracy_note);
    setLibertiesNote(row.creative_liberties_note);
    createAssessment.reset();
    reviseAssessment.reset();
    setEditing(true);
  }

  function save() {
    const payload = {
      accuracy_note: accuracyNote,
      creative_liberties_note: libertiesNote,
      accuracy_rating: rating || null,
    };
    const done = { onSuccess: () => setEditing(false) };
    if (row.comparison_id) {
      reviseAssessment.mutate(
        { comparisonId: row.comparison_id, unit_id: row.unit_ids[0], ...payload },
        done,
      );
    } else {
      createAssessment.mutate(
        {
          unit_id: row.unit_ids[0],
          literal_rendering_id: row.literal_rendering_ids[0] ?? null,
          english_rendering_id: row.english_rendering_ids[0] ?? null,
          status: 'draft',
          translation_id: translationId,
          ...payload,
        },
        done,
      );
    }
  }

  return (
    <>
      <section className="phone-card">
        <div className="phone-card__head">
          <span className="phone-label phone-label--gold">Rendering under review</span>
          {row.assessment_status ? (
            <span className={`phone-tag phone-tag--${row.assessment_status}`}>
              {STATUS_LABELS[row.assessment_status]} · {englishLayer.replace(/_/g, ' ')}
            </span>
          ) : null}
        </div>
        <p className="phone-text">{row.english_text ?? 'No English rendering yet.'}</p>
        <p className="phone-provenance">
          {row.created_via ? VIA_LABELS[row.created_via] : 'Source unrecorded'}
          <span className="phone-dot" aria-hidden="true" />
          {row.display_reference}
        </p>
      </section>

      <section className="phone-card phone-card--source">
        <div className="phone-card__head">
          <span className="phone-label">Compare with the source</span>
          <button type="button" className="phone-chip" onClick={onOpenEvidence}>
            Word evidence ↗
          </button>
        </div>
        <p className="phone-source-line" lang="he" dir="rtl">
          {row.hebrew_text}
        </p>
        <p className="phone-text phone-text--literal">
          {row.literal_text ?? 'No literal rendering yet.'}
        </p>
      </section>

      <PhoneWarnings row={row} />

      <section className="phone-card">
        <div className="phone-card__head">
          <span className="phone-label">Fidelity assessment</span>
          {row.accuracy_rating ? (
            <span className={`phone-tag phone-fidelity--${tone}`}>
              {row.accuracy_rating.replace(/_/g, ' ')}
            </span>
          ) : null}
        </div>
        {editing ? (
          <div className="phone-form">
            <label>
              <span>Accuracy</span>
              <select
                value={rating}
                onChange={(event) => setRating(event.target.value as AccuracyRating | '')}
              >
                <option value="">Not rated</option>
                {ACCURACY_RATINGS.map((value) => (
                  <option key={value} value={value}>
                    {value.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Accuracy note</span>
              <textarea
                rows={3}
                value={accuracyNote}
                onChange={(event) => setAccuracyNote(event.target.value)}
              />
            </label>
            <label>
              <span>Creative liberties</span>
              <textarea
                rows={3}
                value={libertiesNote}
                onChange={(event) => setLibertiesNote(event.target.value)}
              />
            </label>
            {error ? <p className="comparison-error">{String(error)}</p> : null}
            <div className="phone-actions">
              <button type="button" onClick={() => setEditing(false)} disabled={saving}>
                Cancel
              </button>
              <button
                type="button"
                className="phone-action--primary"
                onClick={save}
                disabled={saving}
              >
                {saving ? 'Saving…' : 'Save assessment'}
              </button>
            </div>
          </div>
        ) : (
          <>
            <p className="phone-text phone-text--literal">
              {row.accuracy_note || 'No accuracy note recorded.'}
            </p>
            {row.creative_liberties_note ? (
              <p className="phone-caption">Liberties: {row.creative_liberties_note}</p>
            ) : null}
            <button type="button" className="phone-wide" onClick={startEditing}>
              {row.comparison_id ? 'Revise assessment' : 'Record assessment'}
            </button>
          </>
        )}
      </section>

      <section className="phone-card">
        <p className="phone-label">Review requirements</p>
        <p className="phone-requirement">
          <span className="phone-requirement__mark" aria-hidden="true">
            ○
          </span>
          <span>Accepting an alternate takes one qualified reviewer approval.</span>
        </p>
        <p className="phone-requirement">
          <span className="phone-requirement__mark" aria-hidden="true">
            ○
          </span>
          <span>Promoting to canonical, or changing canonical text, takes two.</span>
        </p>
        <p className="phone-requirement">
          <span className="phone-requirement__mark" aria-hidden="true">
            ○
          </span>
          <span>Every change writes an audit record naming who made it and why.</span>
        </p>
        <p className="phone-caption">
          Approvals themselves are recorded on a desktop; this screen records the assessment.
        </p>
      </section>

      {openNotes.length > 0 ? (
        <section className="phone-card">
          <div className="phone-card__head">
            <span className="phone-label">Open notes</span>
            <span className="phone-tag">{openNotes.length}</span>
          </div>
          {openNotes.map((note) => (
            <p className="phone-note" key={note.note_id}>
              <strong>{note.kind}</strong> · {note.applies_to}
              <br />
              {note.text}
            </p>
          ))}
        </section>
      ) : null}

      {statusLabel(row.english_status) ? (
        <p className="phone-caption">
          The English rendering itself is {statusLabel(row.english_status)?.toLowerCase()}.
        </p>
      ) : null}
    </>
  );
}
