import { useMemo, useState } from 'react';

import {
  useComparisonTable,
  useCreateComparisonAssessment,
  useReviseComparisonAssessment,
} from '../hooks/useComparisonAssessments';
import type {
  AccuracyRating,
  ComparisonStatus,
  ComparisonTableRow,
  CreatedVia,
} from '../types';

const ACCURACY_RATINGS: AccuracyRating[] = [
  'literal',
  'very_close',
  'close',
  'adapted',
  'interpretive',
  'omission',
];

const STATUS_LABELS: Record<ComparisonStatus, string> = {
  draft: 'Draft',
  proposed: 'Proposed',
  reviewed: 'Reviewed',
  accepted_as_alternate: 'Accepted alternate',
  canonical: 'Canonical',
  rejected: 'Rejected',
  superseded: 'Superseded',
};

const VIA_LABELS: Record<CreatedVia, string> = {
  human: 'Human authored',
  codex: 'Codex suggested',
  local_model: 'Other local model suggested',
  deterministic: 'Deterministically composed',
};

const GUTTER_WIDTHS = [24, 32, 48] as const;
type GutterWidth = (typeof GUTTER_WIDTHS)[number];

const ENGLISH_LAYERS = ['lyric', 'metered_lyric', 'parallelism_lyric', 'concept', 'phrase'];

function download(filename: string, body: string, mime: string) {
  const url = URL.createObjectURL(new Blob([body], { type: mime }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function toMarkdown(rows: ComparisonTableRow[]): string {
  const header =
    '| Reference | Hebrew (MT) | Literal | English used | Accuracy | Creative liberties |';
  const divider = '| --- | --- | --- | --- | --- | --- |';
  const body = rows.map((row) => {
    const cells = [
      row.display_reference,
      row.hebrew_text,
      row.literal_text ?? '',
      row.english_text ?? '',
      [row.accuracy_rating ?? '', row.accuracy_note].filter(Boolean).join(' — '),
      row.creative_liberties_note,
    ];
    // Newlines would break the row; keep the text, flatten the layout only.
    return `| ${cells.map((cell) => cell.replace(/\n/g, '<br>').replace(/\|/g, '\\|')).join(' | ')} |`;
  });
  return [header, divider, ...body].join('\n');
}

function toCsv(rows: ComparisonTableRow[]): string {
  const escape = (value: string) => `"${value.replace(/"/g, '""')}"`;
  const header = [
    'mt_reference',
    'display_reference',
    'hebrew_text',
    'literal_text',
    'english_text',
    'accuracy_rating',
    'accuracy_note',
    'creative_liberties_note',
    'status',
    'created_via',
  ];
  const body = rows.map((row) =>
    [
      row.mt_reference,
      row.display_reference,
      row.hebrew_text,
      row.literal_text ?? '',
      row.english_text ?? '',
      row.accuracy_rating ?? '',
      row.accuracy_note,
      row.creative_liberties_note,
      row.assessment_status ?? '',
      row.created_via ?? '',
    ]
      .map(escape)
      .join(','),
  );
  return [header.join(','), ...body].join('\n');
}

interface Props {
  psalmId: string | null;
  onOpenEvidence?: (unitId: string) => void;
  onOpenRendering?: (renderingId: string) => void;
}

export function TranslationComparisonTable({ psalmId, onOpenEvidence, onOpenRendering }: Props) {
  const [englishLayer, setEnglishLayer] = useState('lyric');
  const [gutterWidth, setGutterWidth] = useState<GutterWidth>(32);
  const [statusFilter, setStatusFilter] = useState<ComparisonStatus | ''>('');
  const [ratingFilter, setRatingFilter] = useState<AccuracyRating | ''>('');
  const [editing, setEditing] = useState<string | null>(null);
  const [draftAccuracy, setDraftAccuracy] = useState('');
  const [draftLiberties, setDraftLiberties] = useState('');
  const [draftRating, setDraftRating] = useState<AccuracyRating | ''>('');

  const { data, isLoading, error } = useComparisonTable(psalmId, 'literal', englishLayer);
  const createAssessment = useCreateComparisonAssessment(psalmId);
  const reviseAssessment = useReviseComparisonAssessment(psalmId);

  const rows = useMemo(() => {
    const all = data?.rows ?? [];
    return all.filter((row) => {
      if (statusFilter && row.assessment_status !== statusFilter) return false;
      if (ratingFilter && row.accuracy_rating !== ratingFilter) return false;
      return true;
    });
  }, [data, statusFilter, ratingFilter]);

  function beginEdit(row: ComparisonTableRow) {
    setEditing(row.unit_ids[0]);
    setDraftAccuracy(row.accuracy_note);
    setDraftLiberties(row.creative_liberties_note);
    setDraftRating(row.accuracy_rating ?? '');
  }

  function saveEdit(row: ComparisonTableRow) {
    const payload = {
      accuracy_note: draftAccuracy,
      creative_liberties_note: draftLiberties,
      accuracy_rating: draftRating || null,
    };
    if (row.comparison_id) {
      reviseAssessment.mutate({
        comparisonId: row.comparison_id,
        unit_id: row.unit_ids[0],
        ...payload,
      });
    } else {
      createAssessment.mutate({
        unit_id: row.unit_ids[0],
        literal_rendering_id: row.literal_rendering_ids[0] ?? null,
        english_rendering_id: row.english_rendering_ids[0] ?? null,
        status: 'draft',
        ...payload,
      });
    }
    setEditing(null);
  }

  if (!psalmId) {
    return <p className="comparison-empty">Select a psalm to compare.</p>;
  }
  if (isLoading) {
    return <p className="comparison-empty">Loading comparison…</p>;
  }
  if (error) {
    return <p className="comparison-empty comparison-error">{String(error)}</p>;
  }

  return (
    <section className="comparison-view" aria-label="Translation comparison">
      <header className="comparison-toolbar">
        <h2>
          {data?.title} — translation comparison
        </h2>
        <div className="comparison-controls">
          <label>
            English layer
            <select value={englishLayer} onChange={(e) => setEnglishLayer(e.target.value)}>
              {ENGLISH_LAYERS.map((layer) => (
                <option key={layer} value={layer}>
                  {layer}
                </option>
              ))}
            </select>
          </label>
          <label>
            Status
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ComparisonStatus | '')}
            >
              <option value="">All</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Accuracy
            <select
              value={ratingFilter}
              onChange={(e) => setRatingFilter(e.target.value as AccuracyRating | '')}
            >
              <option value="">All</option>
              {ACCURACY_RATINGS.map((rating) => (
                <option key={rating} value={rating}>
                  {rating.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </label>
          <label>
            Gutter
            <select
              value={gutterWidth}
              onChange={(e) => setGutterWidth(Number(e.target.value) as GutterWidth)}
            >
              {GUTTER_WIDTHS.map((width) => (
                <option key={width} value={width}>
                  {width} px
                </option>
              ))}
            </select>
          </label>
          <div className="comparison-exports">
            <button
              type="button"
              onClick={() => download(`${psalmId}-comparison.md`, toMarkdown(rows), 'text/markdown')}
            >
              Export Markdown
            </button>
            <button
              type="button"
              onClick={() => download(`${psalmId}-comparison.csv`, toCsv(rows), 'text/csv')}
            >
              Export CSV
            </button>
            <button type="button" onClick={() => window.print()}>
              Print / PDF
            </button>
          </div>
        </div>
      </header>

      <div className="comparison-scroll">
        <table
          className="comparison-table"
          style={{ ['--gutter-width' as string]: `${gutterWidth}px` }}
        >
          <caption className="visually-hidden">
            Hebrew, literal translation, English used, translation accuracy and creative liberties
            for each verse.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="col-reference">
                Reference
              </th>
              <th scope="col" className="col-hebrew">
                Hebrew (MT)
              </th>
              {/* Layout-only spacer: never persisted, never announced. */}
              <th aria-hidden="true" className="col-gutter" />
              <th scope="col" className="col-literal">
                Literal translation
              </th>
              <th scope="col" className="col-english">
                English used
              </th>
              <th scope="col" className="col-accuracy">
                Translation accuracy
              </th>
              <th scope="col" className="col-liberties">
                Creative liberties
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const key = row.unit_ids.join('+');
              const isEditing = editing === row.unit_ids[0];
              return (
                <tr key={key} className={row.incomplete ? 'comparison-row incomplete' : 'comparison-row'}>
                  <th scope="row" className="col-reference">
                    <span className="reference-display">{row.display_reference}</span>
                    {row.mt_reference !== row.display_reference && (
                      <span className="reference-mt">MT {row.mt_reference}</span>
                    )}
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => onOpenEvidence?.(row.unit_ids[0])}
                    >
                      Token evidence
                    </button>
                    {row.assessment_status && (
                      <span className={`status-badge status-${row.assessment_status}`}>
                        {STATUS_LABELS[row.assessment_status]}
                      </span>
                    )}
                    {row.created_via && (
                      <span className={`provenance-badge via-${row.created_via}`}>
                        {VIA_LABELS[row.created_via]}
                      </span>
                    )}
                  </th>

                  <td className="col-hebrew" dir="rtl" lang="he" data-label="Hebrew (MT)">
                    {row.hebrew_text}
                  </td>

                  <td aria-hidden="true" className="col-gutter" />

                  <td className="col-literal" data-label="Literal translation">
                    {row.literal_text ? (
                      <button
                        type="button"
                        className="cell-text link-button"
                        onClick={() => onOpenRendering?.(row.literal_rendering_ids[0])}
                      >
                        {row.literal_text}
                      </button>
                    ) : (
                      <span className="cell-missing">No literal rendering selected</span>
                    )}
                  </td>

                  <td className="col-english" data-label="English used">
                    {row.english_text ? (
                      <button
                        type="button"
                        className="cell-text link-button"
                        onClick={() => onOpenRendering?.(row.english_rendering_ids[0])}
                      >
                        {row.english_text}
                      </button>
                    ) : (
                      <span className="cell-missing">No {englishLayer} rendering selected</span>
                    )}
                  </td>

                  <td className="col-accuracy" data-label="Translation accuracy">
                    {isEditing ? (
                      <>
                        <select
                          aria-label="Accuracy rating"
                          value={draftRating}
                          onChange={(e) => setDraftRating(e.target.value as AccuracyRating | '')}
                        >
                          <option value="">Unrated</option>
                          {ACCURACY_RATINGS.map((rating) => (
                            <option key={rating} value={rating}>
                              {rating.replace(/_/g, ' ')}
                            </option>
                          ))}
                        </select>
                        <textarea
                          aria-label="Accuracy note"
                          value={draftAccuracy}
                          onChange={(e) => setDraftAccuracy(e.target.value)}
                        />
                      </>
                    ) : (
                      <>
                        {row.accuracy_rating && (
                          <span className={`rating rating-${row.accuracy_rating}`}>
                            {row.accuracy_rating.replace(/_/g, ' ')}
                          </span>
                        )}
                        <span className="cell-text">{row.accuracy_note}</span>
                      </>
                    )}
                  </td>

                  <td className="col-liberties" data-label="Creative liberties">
                    {isEditing ? (
                      <>
                        <textarea
                          aria-label="Creative liberties note"
                          value={draftLiberties}
                          onChange={(e) => setDraftLiberties(e.target.value)}
                        />
                        <button type="button" onClick={() => saveEdit(row)}>
                          Save
                        </button>
                        <button type="button" onClick={() => setEditing(null)}>
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <span className="cell-text">{row.creative_liberties_note}</span>
                        <button type="button" className="link-button" onClick={() => beginEdit(row)}>
                          Edit notes
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default TranslationComparisonTable;
