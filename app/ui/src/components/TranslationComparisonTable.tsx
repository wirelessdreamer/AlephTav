import { Fragment, useEffect, useMemo, useRef, useState } from 'react';

import {
  useAnalyzePsalm,
  useAnalyzeVerse,
  useCodexStatus,
  useCreateCodexSession,
  useFillComparisonRow,
  useSaveTranslationGuidance,
  useTranslationGuidance,
} from '../hooks/useCodex';
import {
  useComparisonTable,
  useCreateComparisonAssessment,
  useReviseComparisonAssessment,
} from '../hooks/useComparisonAssessments';
import { HebrewStudyText } from './HebrewStudyText';
import type {
  AccuracyRating,
  ComparisonStatus,
  ComparisonTableRow,
  CreatedVia,
  PsalmAnalysis,
  PsalmAnalysisSection,
} from '../types';

const ACCURACY_RATINGS: AccuracyRating[] = [
  'literal',
  'very_close',
  'close',
  'adapted',
  'interpretive',
  'omission',
  'no_source_basis',
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

/** Severity grouping for the row stripe, so fidelity reads before the prose. */
const RATING_TONE: Record<AccuracyRating, 'close' | 'interpret' | 'caution'> = {
  literal: 'close',
  very_close: 'close',
  close: 'close',
  adapted: 'interpret',
  interpretive: 'interpret',
  omission: 'caution',
  no_source_basis: 'caution',
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

type BatchKind = 'translate' | 'analyse';

const BATCH_WORDS: Record<BatchKind, { active: string; noun: string }> = {
  translate: { active: 'Translating', noun: 'Translation' },
  analyse: { active: 'Analysing', noun: 'Analysis' },
};

/** One Codex call in a batch. `run` resolves to an error message, or null on success. */
interface BatchStep {
  label: string;
  unitId: string | null;
  run: () => Promise<string | null>;
}

interface BatchProgress {
  kind: BatchKind;
  done: number;
  total: number;
  label: string;
  unitId: string | null;
  stopping: boolean;
}

interface BatchReport {
  kind: BatchKind;
  succeeded: number;
  total: number;
  stopped: boolean;
  failures: { label: string; error: string }[];
}

/** API errors arrive as FastAPI `{"detail": ...}` bodies, sometimes inside a run's error. */
function readableError(message: string): string {
  try {
    const parsed: unknown = JSON.parse(message);
    if (parsed && typeof parsed === 'object' && 'detail' in parsed) {
      const { detail } = parsed as { detail: unknown };
      return typeof detail === 'string' ? detail : JSON.stringify(detail);
    }
  } catch {
    // Not JSON: the message is already readable.
  }
  return message;
}

/**
 * Codex endpoints answer 200 even when the run failed, reporting it in
 * `status` / `error`. Resolve to that failure (or a thrown one), or null.
 */
async function failureOf(
  call: () => Promise<{ status: string; error: string | null }>,
): Promise<string | null> {
  try {
    const result = await call();
    if (result.status === 'completed') return null;
    return readableError(result.error ?? `Codex run ended as ${result.status.replace(/_/g, ' ')}`);
  } catch (error) {
    return readableError(error instanceof Error ? error.message : String(error));
  }
}

/** Group identical errors so a systemic failure reads once, not once per verse. */
function groupFailures(failures: BatchReport['failures']) {
  const groups = new Map<string, string[]>();
  for (const { label, error } of failures) {
    groups.set(error, [...(groups.get(error) ?? []), label]);
  }
  return [...groups].map(([error, labels]) => ({ error, labels }));
}

interface Props {
  psalmId: string | null;
  onOpenRendering?: (renderingId: string) => void;
}

export function TranslationComparisonTable({ psalmId, onOpenRendering }: Props) {
  const [englishLayer, setEnglishLayer] = useState('lyric');
  const [gutterWidth, setGutterWidth] = useState<GutterWidth>(32);
  const [statusFilter, setStatusFilter] = useState<ComparisonStatus | ''>('');
  const [ratingFilter, setRatingFilter] = useState<AccuracyRating | ''>('');
  const [editing, setEditing] = useState<string | null>(null);
  const [draftAccuracy, setDraftAccuracy] = useState('');
  const [draftLiberties, setDraftLiberties] = useState('');
  const [draftRating, setDraftRating] = useState<AccuracyRating | ''>('');

  const [guidanceDraft, setGuidanceDraft] = useState('');
  const [guidanceOpen, setGuidanceOpen] = useState(false);
  const [batch, setBatch] = useState<BatchProgress | null>(null);
  const [report, setReport] = useState<BatchReport | null>(null);
  const stopRequested = useRef(false);

  const { data, isLoading, error } = useComparisonTable(psalmId, 'literal', englishLayer);
  const createAssessment = useCreateComparisonAssessment(psalmId);
  const reviseAssessment = useReviseComparisonAssessment(psalmId);

  const [expanded, setExpanded] = useState<string | null>(null);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [analysisTab, setAnalysisTab] = useState<
    'summary' | 'architecture' | 'guardrails' | 'epistemics' | 'sources'
  >('summary');

  const { data: codexStatus } = useCodexStatus();
  const { data: guidance } = useTranslationGuidance(psalmId);
  const saveGuidance = useSaveTranslationGuidance(psalmId);
  const createSession = useCreateCodexSession();
  const fillRow = useFillComparisonRow();
  const analyzeVerse = useAnalyzeVerse(psalmId);
  const analyzePsalm = useAnalyzePsalm(psalmId);
  const codexReady = codexStatus?.status === 'ready';
  const analysis = data?.analysis ?? null;

  useEffect(() => {
    setGuidanceDraft(guidance?.translation_guidance ?? '');
  }, [guidance?.translation_guidance, psalmId]);

  /** Reuse one Codex thread per psalm so context carries across rows. */
  const sessionRef = useRef<string | null>(null);
  useEffect(() => {
    sessionRef.current = null;
    setReport(null);
  }, [psalmId]);

  async function ensureSession(): Promise<string> {
    if (sessionRef.current) return sessionRef.current;
    const session = await createSession.mutateAsync({
      psalm_id: psalmId as string,
      layer: englishLayer,
    });
    sessionRef.current = session.session_id;
    return session.session_id;
  }

  /** Run Codex steps one at a time, showing the step in flight and reporting the outcome. */
  async function runBatch(kind: BatchKind, steps: BatchStep[]) {
    stopRequested.current = false;
    setReport(null);
    const failures: BatchReport['failures'] = [];
    let done = 0;
    try {
      for (const step of steps) {
        if (stopRequested.current) break;
        setBatch({
          kind,
          done,
          total: steps.length,
          label: step.label,
          unitId: step.unitId,
          stopping: false,
        });
        const error = await step.run();
        if (error) failures.push({ label: step.label, error });
        done += 1;
      }
    } finally {
      setBatch(null);
      setReport({
        kind,
        succeeded: done - failures.length,
        total: steps.length,
        stopped: done < steps.length,
        failures,
      });
    }
  }

  function translateStep(row: ComparisonTableRow): BatchStep {
    const unitId = row.unit_ids[0];
    return {
      label: row.display_reference,
      unitId,
      run: () =>
        failureOf(async () =>
          fillRow.mutateAsync({
            unitId,
            session_id: await ensureSession(),
            english_layer: englishLayer,
          }),
        ),
    };
  }

  function analyseStep(row: ComparisonTableRow): BatchStep {
    const unitId = row.unit_ids[0];
    return {
      label: row.display_reference,
      unitId,
      run: () =>
        failureOf(async () =>
          analyzeVerse.mutateAsync({
            unitId,
            session_id: await ensureSession(),
            english_layer: englishLayer,
          }),
        ),
    };
  }

  function analysePsalm(targets: ComparisonTableRow[]) {
    return runBatch('analyse', [
      ...targets.map(analyseStep),
      // The psalm-scope turn last, so sections describe the audited verses.
      {
        label: `${data?.title ?? 'The psalm'} as a whole`,
        unitId: null,
        run: () =>
          failureOf(async () =>
            analyzePsalm.mutateAsync({
              session_id: await ensureSession(),
              english_layer: englishLayer,
            }),
          ),
      },
    ]);
  }

  const rows = useMemo(() => {
    const all = data?.rows ?? [];
    return all.filter((row) => {
      if (statusFilter && row.assessment_status !== statusFilter) return false;
      if (ratingFilter && row.accuracy_rating !== ratingFilter) return false;
      return true;
    });
  }, [data, statusFilter, ratingFilter]);

  /** The section a row starts, so a band can be rendered above it. */
  function sectionOpening(row: ComparisonTableRow): PsalmAnalysisSection | null {
    if (!analysis) return null;
    const verse = Number(row.unit_ids[0]?.split('.')[1]?.replace('v', ''));
    return analysis.sections.find((s) => s.first_verse === verse) ?? null;
  }

  function seamAfter(row: ComparisonTableRow) {
    if (!analysis) return null;
    const verse = Number(row.unit_ids[0]?.split('.')[1]?.replace('v', ''));
    return analysis.structural_seams.find((s) => s.after_verse === verse) ?? null;
  }

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
          <div className="comparison-generate">
            <button
              type="button"
              aria-expanded={guidanceOpen}
              onClick={() => setGuidanceOpen((open) => !open)}
            >
              {guidance?.translation_guidance ? 'Guidance ✓' : 'Guidance'}
            </button>
            {batch ? (
              <>
                <span className="batch-progress" role="status">
                  {batch.stopping
                    ? `Stopping after ${batch.label}…`
                    : `${BATCH_WORDS[batch.kind].active} ${batch.label} ` +
                      `(${batch.done + 1} of ${batch.total})…`}
                </span>
                <button
                  type="button"
                  disabled={batch.stopping}
                  onClick={() => {
                    stopRequested.current = true;
                    setBatch((current) => current && { ...current, stopping: true });
                  }}
                >
                  {batch.stopping ? 'Stopping…' : 'Stop'}
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  disabled={!codexReady || fillRow.isPending}
                  title={codexReady ? undefined : 'Connect Codex in the assistant panel first'}
                  onClick={() =>
                    void runBatch('translate', rows.filter((row) => row.incomplete).map(translateStep))
                  }
                >
                  Translate psalm
                </button>
                <button
                  type="button"
                  disabled={!codexReady || analyzeVerse.isPending}
                  title={
                    codexReady
                      ? 'Audit the existing renderings against the Hebrew'
                      : 'Connect Codex in the assistant panel first'
                  }
                  onClick={() => void analysePsalm(rows.filter((row) => !row.incomplete))}
                >
                  Analyse psalm
                </button>
              </>
            )}
          </div>
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

      {report ? (
        <div
          className={`batch-report${report.failures.length > 0 ? ' has-failures' : ''}`}
          role="status"
        >
          <p>
            {report.total === 0
              ? 'Nothing to translate: every verse shown already has literal and English renderings.'
              : `${BATCH_WORDS[report.kind].noun} ${report.stopped ? 'stopped' : 'finished'}: ` +
                `${report.succeeded} of ${report.total} succeeded` +
                (report.failures.length > 0 ? `, ${report.failures.length} failed.` : '.')}
          </p>
          {groupFailures(report.failures).map(({ error, labels }) => (
            <p key={error} className="comparison-error">
              {labels.length > 3
                ? `${labels.slice(0, 3).join(', ')} and ${labels.length - 3} more`
                : labels.join(', ')}
              : {error}
            </p>
          ))}
          <button type="button" onClick={() => setReport(null)}>
            Dismiss
          </button>
        </div>
      ) : null}

      {guidanceOpen ? (
        <section className="guidance-panel" aria-label="Translation guidance">
          <label htmlFor="translation-guidance">
            How this psalm should be translated. Codex reads this before the source, and it
            outranks the generic layer prompts. Saved with the psalm, so it is versioned.
          </label>
          <textarea
            id="translation-guidance"
            value={guidanceDraft}
            rows={6}
            placeholder={
              'e.g. Keep the lament raw — do not resolve doubt into confident devotion.\n' +
              'Render YHWH as "the LORD". Keep bones, throat and grave visible.\n' +
              'Short breath-based lines; no "behold" or archaic verb forms.'
            }
            onChange={(event) => setGuidanceDraft(event.target.value)}
          />
          <div className="guidance-actions">
            <button
              type="button"
              disabled={saveGuidance.isPending}
              onClick={() => saveGuidance.mutate(guidanceDraft)}
            >
              {saveGuidance.isPending ? 'Saving…' : 'Save guidance'}
            </button>
            <button
              type="button"
              onClick={() => setGuidanceDraft(guidance?.translation_guidance ?? '')}
            >
              Revert
            </button>
            {saveGuidance.isError ? (
              <span className="comparison-error">{String(saveGuidance.error)}</span>
            ) : null}
          </div>
        </section>
      ) : null}


      {analysis ? (
        <section className="analysis-panel" aria-label="Psalm analysis">
          <header className="analysis-panel__head">
            <button
              type="button"
              aria-expanded={analysisOpen}
              onClick={() => setAnalysisOpen((open) => !open)}
            >
              {analysisOpen ? '▾' : '▸'} Analysis
            </button>
            <span className={`status-badge status-${analysis.status}`}>{analysis.status}</span>
            <span className="provenance-badge via-codex">
              {VIA_LABELS[analysis.created_via] ?? analysis.created_via}
            </span>
            {data?.canonical_numbering ? (
              <span className="numbering">
                MT {data.canonical_numbering.mt} · LXX/Vulg{' '}
                {data.canonical_numbering.septuagint.join(', ')}
              </span>
            ) : null}
          </header>

          {analysisOpen ? (
            <>
              <div className="tabs" role="tablist">
                {(
                  [
                    ['summary', 'What this setting does'],
                    ['architecture', 'Architecture'],
                    ['guardrails', 'Historical guardrails'],
                    ['epistemics', 'Known / not known'],
                    ['sources', 'Method and sources'],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    role="tab"
                    className="tab"
                    aria-selected={analysisTab === key}
                    onClick={() => setAnalysisTab(key)}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {analysisTab === 'summary' ? <p className="analysis-prose">{analysis.summary}</p> : null}

              {analysisTab === 'architecture' ? (
                <div className="arch">
                  {analysis.sections.map((section) => (
                    <div key={`${section.first_verse}-${section.last_verse}`} className="arch__row">
                      <span className="arch__vv">
                        vv. {section.first_verse}–{section.last_verse}
                      </span>
                      <span>{section.theme}</span>
                      <span className="arch__sec">{section.title}</span>
                    </div>
                  ))}
                  {analysis.structural_seams.length > 0 ? (
                    <p className="analysis-prose">
                      Seams:{' '}
                      {analysis.structural_seams
                        .map(
                          (seam) =>
                            `${seam.marker} after v.${seam.after_verse}` +
                            (seam.aligns_with_section ? ' (section ends here)' : ''),
                        )
                        .join(' · ')}
                    </p>
                  ) : null}
                </div>
              ) : null}

              {analysisTab === 'guardrails' ? (
                <dl className="analysis-defs">
                  <dt>Heading</dt>
                  <dd>{analysis.guardrails.heading_attribution}</dd>
                  <dt>Setting</dt>
                  <dd>{analysis.guardrails.cultic_setting}</dd>
                </dl>
              ) : null}

              {analysisTab === 'epistemics' ? (
                <div className="epistemic">
                  <div className="known">
                    <h4>Known from the text</h4>
                    <ul>
                      {analysis.epistemics.known_from_text.map((item) => (
                        <li key={item.claim}>
                          {item.claim} <span className="basis">{item.basis}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="unknown">
                    <h4>Not known from the text</h4>
                    <ul>
                      {analysis.epistemics.not_known_from_text.map((item) => (
                        <li key={item.claim}>
                          {item.claim} <span className="basis">{item.why_not}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : null}

              {analysisTab === 'sources' ? (
                <>
                  <p className="analysis-prose">{analysis.method}</p>
                  {analysis.citations.length > 0 ? (
                    <ul className="citations">
                      {analysis.citations.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="analysis-prose subtle-note">
                      No sources beyond the supplied evidence were cited.
                    </p>
                  )}
                </>
              ) : null}
            </>
          ) : null}
        </section>
      ) : null}

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
              const band = sectionOpening(row);
              const seam = seamAfter(row);
              const tone = row.accuracy_rating ? RATING_TONE[row.accuracy_rating] : null;
              const isOpen = expanded === key;
              return (
                <Fragment key={key}>
                {band ? (
                  <tr className="band">
                    <td colSpan={7}>
                      <div className="band__head">
                        <span className="band__title">{band.title}</span>
                        <span className="band__range">
                          vv. {band.first_verse}–{band.last_verse}
                        </span>
                        <span className="band__theme">{band.theme}</span>
                      </div>
                      {band.arc_note ? <p className="band__note">{band.arc_note}</p> : null}
                    </td>
                  </tr>
                ) : null}
                <tr
                  className={[
                    'comparison-row',
                    row.incomplete ? 'incomplete' : '',
                    row.stale ? 'is-stale' : '',
                    tone ? `r-${tone}` : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  <th scope="row" className="col-reference">
                    <span className="reference-display">{row.display_reference}</span>
                    {row.mt_reference !== row.display_reference && (
                      <span className="reference-mt">MT {row.mt_reference}</span>
                    )}
                    {batch?.unitId === row.unit_ids[0] && (
                      <span className="row-progress">{BATCH_WORDS[batch.kind].active}…</span>
                    )}
                    <button
                      type="button"
                      className="link-button"
                      disabled={!codexReady || fillRow.isPending || Boolean(batch)}
                      title={codexReady ? undefined : 'Connect Codex in the assistant panel first'}
                      onClick={() => void runBatch('translate', [translateStep(row)])}
                    >
                      {row.incomplete ? 'Translate verse' : 'Regenerate'}
                    </button>
                    {!row.incomplete && (
                      <button
                        type="button"
                        className="link-button"
                        disabled={!codexReady || analyzeVerse.isPending || Boolean(batch)}
                        onClick={() => void runBatch('analyse', [analyseStep(row)])}
                      >
                        {row.stale ? 'Re-analyse' : 'Analyse'}
                      </button>
                    )}
                    {((row.literal_backbone?.length ?? 0) > 0 ||
                      (row.non_source_material?.length ?? 0) > 0) && (
                      <button
                        type="button"
                        className="link-button"
                        aria-expanded={isOpen}
                        onClick={() => setExpanded(isOpen ? null : key)}
                      >
                        {isOpen ? 'Hide evidence' : 'Evidence'}
                      </button>
                    )}
                    {row.assessment_status && (
                      <span className={`status-badge status-${row.assessment_status}`}>
                        {STATUS_LABELS[row.assessment_status]}
                      </span>
                    )}
                    {row.stale && (
                      <span
                        className="stale-badge"
                        title="The rendering has changed since this analysis ran"
                      >
                        Stale
                      </span>
                    )}
                    {row.created_via && (
                      <span className={`provenance-badge via-${row.created_via}`}>
                        {VIA_LABELS[row.created_via]}
                      </span>
                    )}
                  </th>

                  <td className="col-hebrew" data-label="Hebrew (MT)">
                    <HebrewStudyText tokens={row.tokens ?? []} text={row.hebrew_text} />
                  </td>

                  <td aria-hidden="true" className="col-gutter" />

                  <td className="col-literal" data-label="Literal translation">
                    {row.literal_text ? (
                      onOpenRendering ? (
                        <button
                          type="button"
                          className="cell-text link-button"
                          onClick={() => onOpenRendering(row.literal_rendering_ids[0])}
                        >
                          {row.literal_text}
                        </button>
                      ) : (
                        <span className="cell-text">{row.literal_text}</span>
                      )
                    ) : (
                      <span className="cell-missing">No literal rendering selected</span>
                    )}
                  </td>

                  <td className="col-english" data-label="English used">
                    {row.english_text ? (
                      onOpenRendering ? (
                        <button
                          type="button"
                          className="cell-text link-button"
                          onClick={() => onOpenRendering(row.english_rendering_ids[0])}
                        >
                          {row.english_text}
                        </button>
                      ) : (
                        <span className="cell-text">{row.english_text}</span>
                      )
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
                {isOpen ? (
                  <tr className="detail">
                    <td colSpan={7}>
                      <div className="detail__grid">
                        {(row.literal_backbone?.length ?? 0) > 0 ? (
                          <div className="detail__col">
                            <h4>Literal backbone</h4>
                            <ul className="backbone">
                              {(row.literal_backbone ?? []).map((line) => (
                                <li key={line}>{line}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {(row.non_source_material?.length ?? 0) > 0 ? (
                          <div className="detail__col">
                            <h4>Not in the psalm</h4>
                            <ul className="backbone">
                              {(row.non_source_material ?? []).map((item) => (
                                <li key={item.text}>
                                  <strong>{item.text}</strong>{' '}
                                  <span className="pill addition">
                                    {item.kind.replace(/_/g, ' ')}
                                  </span>
                                  {item.note ? <> — {item.note}</> : null}
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ) : null}
                {seam ? (
                  <tr className="seam-row">
                    <td colSpan={7}>
                      <span className="selah">
                        {seam.marker}
                        {seam.aligns_with_section ? ' · section ends here' : ''}
                      </span>
                    </td>
                  </tr>
                ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default TranslationComparisonTable;
