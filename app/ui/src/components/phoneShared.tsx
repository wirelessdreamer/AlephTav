import type { ComparisonTableRow } from '../types';
import { STATUS_LABELS } from './comparisonLabels';

/** A rendering's own status, which is a bare string on the comparison row. */
export function statusLabel(status: string | null): string | null {
  if (!status) return null;
  return STATUS_LABELS[status as keyof typeof STATUS_LABELS] ?? status.replace(/_/g, ' ');
}

/** The verse reference as the row names it, with the MT reference when it differs. */
export function referenceLabel(row: ComparisonTableRow): string {
  return row.display_reference === row.mt_reference
    ? `${row.mt_reference} · MT`
    : `${row.display_reference} · MT ${row.mt_reference}`;
}

/**
 * Everything the reader should see before trusting the English: material with no
 * source behind it, a verse still untranslated, and analysis left behind by an edit.
 */
export function PhoneWarnings({ row }: { row: ComparisonTableRow }) {
  const added = row.non_source_material ?? [];
  if (added.length === 0 && !row.stale && !row.incomplete) return null;

  return (
    <div className="phone-warnings">
      {added.map((item) => (
        <p className="phone-warning" key={`${item.kind}-${item.text}`}>
          <span className="phone-warning__icon" aria-hidden="true">
            △
          </span>
          <span>
            <strong>{item.kind.replace(/_/g, ' ')}</strong>
            <br />
            “{item.text}”{item.note ? ` — ${item.note}` : ' adds meaning to the source clause.'}
          </span>
        </p>
      ))}
      {row.stale ? (
        <p className="phone-warning">
          <span className="phone-warning__icon" aria-hidden="true">
            △
          </span>
          <span>
            <strong>Analysis is stale</strong>
            <br />
            The text changed after this verse was last analysed.
          </span>
        </p>
      ) : null}
      {row.incomplete ? (
        <p className="phone-warning">
          <span className="phone-warning__icon" aria-hidden="true">
            △
          </span>
          <span>
            <strong>Not translated yet</strong>
            <br />
            This verse has no English rendering in this translation.
          </span>
        </p>
      ) : null}
    </div>
  );
}
