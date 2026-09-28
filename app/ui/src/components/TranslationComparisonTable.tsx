import { Fragment, useEffect, useMemo, useRef, useState } from 'react';

import {
  useAnalyzePsalm,
  useAnalyseRebuild,
  useAnalyzeVerse,
  useCodexStatus,
  useConnectCodex,
  useCreateCodexSession,
  useFillPsalmPassage,
  useIdentifyPsalm,
  useImportTranslation,
  useInterruptCodexSession,
  useRebuildVerse,
  useSaveTranslationGuidance,
  useSuggestWordRenderings,
  useTranslationGuidance,
} from '../hooks/useCodex';
import {
  useComparisonTable,
  useCreateComparisonAssessment,
  useReviseComparisonAssessment,
} from '../hooks/useComparisonAssessments';
import { useArrangeImport, useDraftArrangement } from '../hooks/useArrangements';
import {
  useCollections,
  useCreateCollection,
  useCreateTranslation,
} from '../hooks/useTranslations';
import { type ArrangementPane, ArrangementWorkspace } from './ArrangementWorkspace';
import {
  type ImportOptions,
  type ImportRequest,
  type ImportStep,
  ImportTranslationDialog,
} from './ImportTranslationDialog';
import { VerseDetail } from './VerseDetail';
import { WordSummary, type WordSummaryItem } from './WordSummary';
import type {
  AccuracyRating,
  ComparisonStatus,
  ComparisonTableRow,
  CreatedVia,
  ImportResult,
  PsalmAnalysis,
  PsalmAnalysisSection,
  PsalmSummary,
  SimilarTranslation,
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

const CLOSENESS_LABELS: Record<SimilarTranslation['closeness'], string> = {
  reproduces: 'reproduced',
  adapts: 'adapted',
  echoes: 'echoed in places',
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

type BatchKind = 'translate' | 'analyse' | 'rebuild' | 'suggest' | 'arrange' | 'import';

const BATCH_WORDS: Record<BatchKind, { active: string; noun: string }> = {
  translate: { active: 'Translating', noun: 'Translation' },
  analyse: { active: 'Analysing', noun: 'Analysis' },
  rebuild: { active: 'Rebuilding', noun: 'Rebuild' },
  suggest: { active: 'Suggesting choices for', noun: 'Word choices' },
  arrange: { active: 'Drafting a song setting of', noun: 'Song setting' },
  import: { active: 'Import:', noun: 'Import' },
};

interface BatchFailure {
  label: string;
  error: string;
}

/** One Codex call in a batch, covering `rows` table rows. `run` resolves to the rows that failed. */
interface BatchStep {
  label: string;
  unitIds: string[];
  rows: number;
  run: () => Promise<BatchFailure[]>;
}

interface BatchProgress {
  kind: BatchKind;
  done: number;
  total: number;
  label: string;
  unitIds: string[];
  stopping: boolean;
  startedAt: number;
}

/** m:ss, so a slow or stalled Codex turn is visible rather than indistinguishable from progress. */
function elapsed(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

interface BatchReport {
  kind: BatchKind;
  succeeded: number;
  total: number;
  stopped: boolean;
  failures: BatchFailure[];
}

/** Most rows sent to Codex in one turn; longer psalms are split into passages. */
const PASSAGE_LIMIT = 12;

function verseNumber(row: ComparisonTableRow): number {
  return Number(row.unit_ids[0]?.split('.')[1]?.replace('v', ''));
}

/**
 * Split rows into the passages Codex translates one turn at a time: the psalm's
 * analysed sections when it has them, and never more than PASSAGE_LIMIT rows.
 */
function passages(
  rows: ComparisonTableRow[],
  sections: PsalmAnalysisSection[] = [],
): ComparisonTableRow[][] {
  const groups: ComparisonTableRow[][] = [];
  let section: PsalmAnalysisSection | undefined;
  for (const row of rows) {
    const verse = verseNumber(row);
    const rowSection = sections.find((s) => verse >= s.first_verse && verse <= s.last_verse);
    const current = groups[groups.length - 1];
    if (!current || current.length >= PASSAGE_LIMIT || rowSection !== section) {
      groups.push([row]);
    } else {
      current.push(row);
    }
    section = rowSection;
  }
  return groups;
}

/** Whether the verse has notes the next rebuild would follow. */
function hasOpenInstructions(row: ComparisonTableRow): boolean {
  return (row.verse_notes ?? []).some(
    (note) => note.status === 'open' && note.kind === 'instruction',
  );
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

/** Codex endpoints answer 200 even when the run failed, reporting it in `status` / `error`. */
function runFailure(result: { status: string; error: string | null }): string | null {
  if (result.status === 'completed') return null;
  return readableError(result.error ?? `Codex run ended as ${result.status.replace(/_/g, ' ')}`);
}

function thrownFailure(error: unknown): string {
  return readableError(error instanceof Error ? error.message : String(error));
}

/** The failure a Codex call reported or threw, or null when it completed. */
async function failureOf(
  call: () => Promise<{ status: string; error: string | null }>,
): Promise<string | null> {
  try {
    return runFailure(await call());
  } catch (error) {
    return thrownFailure(error);
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

/** An import waiting for the page to show the psalm and translation it goes into. */
interface QueuedImport {
  psalmId: string;
  translationId: string | null;
  text: string;
  options: ImportOptions;
}

interface Props {
  psalmId: string | null;
  /** The translation on show; null is the psalm's main translation. */
  translationId: string | null;
  /** The project on show, where an import goes unless another is chosen. */
  collectionId: string | null;
  /** Every psalm, for the import dialog to pick from. */
  psalms: PsalmSummary[];
  onOpenRendering?: (renderingId: string) => void;
  /** The import dialog, opened from the page header. */
  importOpen?: boolean;
  onImportClose?: () => void;
  /** Show a psalm's translation in a project, as an import does once it knows where it goes. */
  onShowTranslation: (psalmId: string, collectionId: string) => void;
}

export function TranslationComparisonTable({
  psalmId,
  translationId,
  collectionId,
  psalms,
  onOpenRendering,
  importOpen = false,
  onImportClose,
  onShowTranslation,
}: Props) {
  /** The one English layer the workbench makes and shows. */
  const englishLayer = 'lyric';
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
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!batch) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [batch]);

  const { data, isLoading, error } = useComparisonTable(
    psalmId,
    'literal',
    englishLayer,
    translationId,
  );
  const createAssessment = useCreateComparisonAssessment(psalmId);
  const reviseAssessment = useReviseComparisonAssessment(psalmId);

  /** The one verse open in the accordion, and the word studied within it. */
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [selectedTokenId, setSelectedTokenId] = useState<string | null>(null);
  const [evidenceFor, setEvidenceFor] = useState<string | null>(null);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [analysisTab, setAnalysisTab] = useState<
    'summary' | 'architecture' | 'guardrails' | 'epistemics' | 'similar' | 'sources'
  >('summary');

  const { data: codexStatus } = useCodexStatus();
  const connectCodex = useConnectCodex();
  const { data: guidance } = useTranslationGuidance(psalmId, translationId);
  const saveGuidance = useSaveTranslationGuidance(psalmId, translationId);
  const createSession = useCreateCodexSession();
  const fillPassage = useFillPsalmPassage(psalmId);
  const interruptSession = useInterruptCodexSession();
  const analyzeVerse = useAnalyzeVerse(psalmId);
  const rebuildVerse = useRebuildVerse(psalmId);
  const analyseRebuild = useAnalyseRebuild(psalmId);
  const suggestWords = useSuggestWordRenderings();
  const analyzePsalm = useAnalyzePsalm(psalmId);
  const draftArrangement = useDraftArrangement(psalmId);
  const importTranslation = useImportTranslation(psalmId);
  const arrangeImport = useArrangeImport(psalmId);
  const identifyPsalm = useIdentifyPsalm();
  const collections = useCollections();
  const createCollection = useCreateCollection();
  const createTranslation = useCreateTranslation();
  const [importSteps, setImportSteps] = useState<ImportStep[]>([]);
  const [importRunning, setImportRunning] = useState(false);
  const [queuedImport, setQueuedImport] = useState<QueuedImport | null>(null);
  /** Verse by verse, or the psalm as a song setting free of the verse boundaries. */
  const [pane, setPane] = useState<'verses' | ArrangementPane>('verses');
  const [arrangementId, setArrangementId] = useState<string | null>(null);
  const codexReady = codexStatus?.status === 'ready';
  /** Why Codex actions are disabled, in the server's words. */
  const codexHint = codexReady ? undefined : (codexStatus?.detail ?? 'Codex is not connected');
  const analysis = data?.analysis ?? null;

  useEffect(() => {
    setGuidanceDraft(guidance?.translation_guidance ?? '');
  }, [guidance?.translation_guidance, psalmId, translationId]);

  /**
   * Reuse one Codex thread per translation of a psalm so context carries across rows,
   * and never across translations, whose English would leak into each other.
   */
  const sessionRef = useRef<string | null>(null);
  useEffect(() => {
    sessionRef.current = null;
    setReport(null);
    setArrangementId(null);
  }, [psalmId, translationId]);

  async function ensureSession(): Promise<string> {
    if (sessionRef.current) return sessionRef.current;
    const session = await createSession.mutateAsync({
      psalm_id: psalmId as string,
      translation_id: translationId,
      layer: englishLayer,
    });
    sessionRef.current = session.session_id;
    return session.session_id;
  }

  /** Run Codex steps one at a time, showing the step in flight and reporting the outcome. */
  async function runBatch(kind: BatchKind, steps: BatchStep[]) {
    stopRequested.current = false;
    setReport(null);
    const failures: BatchFailure[] = [];
    let done = 0;
    let rowsDone = 0;
    try {
      for (const step of steps) {
        if (stopRequested.current) break;
        setBatch({
          kind,
          done,
          total: steps.length,
          label: step.label,
          unitIds: step.unitIds,
          stopping: false,
          startedAt: Date.now(),
        });
        failures.push(...(await step.run()));
        done += 1;
        rowsDone += step.rows;
      }
    } finally {
      setBatch(null);
      setReport({
        kind,
        succeeded: rowsDone - failures.length,
        total: steps.reduce((sum, step) => sum + step.rows, 0),
        // Stop also interrupts the step in flight, so it can end without a step left over.
        stopped: stopRequested.current,
        failures,
      });
    }
  }

  function stopBatch() {
    stopRequested.current = true;
    setBatch((current) => current && { ...current, stopping: true });
    // Stop the turn in flight as well, rather than waiting for Codex to end it.
    if (sessionRef.current) interruptSession.mutate(sessionRef.current);
  }

  /** Translate rows together, one Codex turn per layer, with the whole psalm as context. */
  function passageStep(passage: ComparisonTableRow[]): BatchStep {
    const unitIds = passage.flatMap((row) => row.unit_ids);
    const first = passage[0].display_reference;
    const last = passage[passage.length - 1].display_reference;
    const chapter = first.slice(0, first.lastIndexOf(':') + 1);
    const everyRow = (error: string) =>
      passage.map((row) => ({ label: row.display_reference, error }));
    return {
      label:
        passage.length === 1
          ? first
          : `${first}–${last.startsWith(chapter) ? last.slice(chapter.length) : last}`,
      unitIds,
      rows: passage.length,
      run: async () => {
        try {
          const result = await fillPassage.mutateAsync({
            session_id: await ensureSession(),
            unit_ids: unitIds,
            english_layer: englishLayer,
          });
          const failure = runFailure(result);
          if (failure) return everyRow(failure);
          // Units Codex left out; one entry per row even when a row has several units.
          const failed = new Map<string, string>();
          for (const { unit_id, error } of result.failed_units) {
            const row = passage.find((candidate) => candidate.unit_ids.includes(unit_id));
            failed.set(row?.display_reference ?? unit_id, readableError(error));
          }
          return [...failed].map(([label, error]) => ({ label, error }));
        } catch (error) {
          return everyRow(thrownFailure(error));
        }
      },
    };
  }

  /** Audit a held rebuild; skipped when the rebuild before it did not produce one. */
  function analyseRebuildStep(row: ComparisonTableRow, when: () => boolean = () => true): BatchStep {
    const unitId = row.unit_ids[0];
    const label = `${row.display_reference}, rebuilt text`;
    return {
      label,
      unitIds: [unitId],
      rows: 1,
      run: async () => {
        if (!when()) return [];
        const error = await failureOf(async () =>
          analyseRebuild.mutateAsync({ unitId, session_id: await ensureSession() }),
        );
        return error ? [{ label, error }] : [];
      },
    };
  }

  function rebuildRow(
    row: ComparisonTableRow,
    layers: Array<'literal' | 'english'>,
    reanalyse: boolean,
  ) {
    const unitId = row.unit_ids[0];
    const label = `${row.display_reference} with your notes`;
    let rebuilt = false;
    const rebuild: BatchStep = {
      label,
      unitIds: [unitId],
      rows: 1,
      run: async () => {
        const error = await failureOf(async () =>
          rebuildVerse.mutateAsync({
            unitId,
            session_id: await ensureSession(),
            english_layer: englishLayer,
            layers,
          }),
        );
        rebuilt = !error;
        return error ? [{ label, error }] : [];
      },
    };
    void runBatch(
      'rebuild',
      reanalyse ? [rebuild, analyseRebuildStep(row, () => rebuilt)] : [rebuild],
    );
  }

  async function suggestFor(row: ComparisonTableRow, tokenIds: string[]) {
    const result = await suggestWords.mutateAsync({
      unitId: row.unit_ids[0],
      session_id: await ensureSession(),
      token_ids: tokenIds,
      layer: englishLayer,
    });
    const failure = runFailure({ status: result.status ?? 'completed', error: result.error ?? null });
    if (failure) throw new Error(failure);
  }

  /** One Codex turn: ranked choices for one word, under the psalm's guidance. */
  function suggestStep(item: WordSummaryItem): BatchStep {
    const label = `${item.verse} ${item.transliteration || item.surface}`;
    return {
      label,
      unitIds: [item.row.unit_ids[0]],
      rows: 1,
      run: async () => {
        try {
          await suggestFor(item.row, item.tokenIds);
          return [];
        } catch (error) {
          return [{ label, error: thrownFailure(error) }];
        }
      },
    };
  }

  function analyseStep(row: ComparisonTableRow): BatchStep {
    const unitId = row.unit_ids[0];
    return {
      label: row.display_reference,
      unitIds: [unitId],
      rows: 1,
      run: async () => {
        const error = await failureOf(async () =>
          analyzeVerse.mutateAsync({
            unitId,
            session_id: await ensureSession(),
            english_layer: englishLayer,
          }),
        );
        return error ? [{ label: row.display_reference, error }] : [];
      },
    };
  }

  function analysePsalm(targets: ComparisonTableRow[]) {
    const wholeLabel = `${data?.title ?? 'The psalm'} as a whole`;
    return runBatch('analyse', [
      ...targets.map(analyseStep),
      // The psalm-scope turn last, so sections describe the audited verses.
      {
        label: wholeLabel,
        unitIds: [],
        rows: 1,
        run: async () => {
          const error = await failureOf(async () =>
            analyzePsalm.mutateAsync({
              session_id: await ensureSession(),
              english_layer: englishLayer,
            }),
          );
          return error ? [{ label: wholeLabel, error }] : [];
        },
      },
    ]);
  }

  /** One Codex turn writes a whole-psalm setting, stored as a proposal and then shown. */
  function draftSetting() {
    const label = `${data?.title ?? 'the psalm'}`;
    return runBatch('arrange', [
      {
        label,
        unitIds: [],
        rows: 1,
        run: async () => {
          const error = await failureOf(async () => {
            const result = await draftArrangement.mutateAsync({
              session_id: await ensureSession(),
              layer: englishLayer,
            });
            if (result.view) setArrangementId(result.view.arrangement.arrangement_id);
            return result;
          });
          return error ? [{ label, error }] : [];
        },
      },
    ]);
  }

  function markImport(key: string, patch: Partial<ImportStep>) {
    setImportSteps((list) => list.map((step) => (step.key === key ? { ...step, ...patch } : step)));
  }

  /**
   * Import a pasted translation: place it (one Codex turn), read it as a song setting
   * (one turn), then analyse each placed verse and the psalm. Each turn is a batch step,
   * so the toolbar progress and Stop work as for any other batch; the dialog shows the
   * same run as a checklist.
   */
  async function runImport(text: string, options: ImportOptions) {
    // After the step that made the translation, when the import made one.
    setImportSteps((made) => [
      ...made,
      { key: 'read', label: 'Reading the translation and placing it verse by verse', status: 'pending' },
      ...(options.arrange
        ? [{ key: 'arrange', label: 'Analysing it as a song setting', status: 'pending' as const }]
        : []),
      ...(options.analyse
        ? [
            { key: 'verses', label: 'Analysing each placed verse', status: 'pending' as const },
            { key: 'psalm', label: 'Analysing the psalm as a whole', status: 'pending' as const },
          ]
        : []),
    ]);
    setImportRunning(true);
    const steps: BatchStep[] = [];

    const arrangeStep: BatchStep = {
      label: 'analysing the song setting',
      unitIds: [],
      rows: 1,
      run: async () => {
        markImport('arrange', { status: 'running' });
        const error = await failureOf(async () => {
          const result = await arrangeImport.mutateAsync({
            session_id: await ensureSession(),
            text,
            layer: englishLayer,
          });
          if (result.view) {
            setArrangementId(result.view.arrangement.arrangement_id);
            const { summary, arrangement } = result.view;
            markImport('arrange', {
              status: 'done',
              detail:
                `${summary.sung_lines} lines sung in ${arrangement.sections.length} sections · ` +
                (summary.open === 0 ? 'nothing to review' : `${summary.open} liberties to review`),
            });
          }
          return result;
        });
        if (error) markImport('arrange', { status: 'failed', detail: error });
        return error ? [{ label: 'Song setting', error }] : [];
      },
    };

    function verseSteps(placed: ImportResult['renderings']): BatchStep[] {
      let failures = 0;
      return placed.map((verse, index) => ({
        label: `analysing ${verse.ref}`,
        unitIds: [verse.unit_id],
        rows: 1,
        run: async () => {
          markImport('verses', {
            status: 'running',
            detail: `${index + 1} of ${placed.length} · ${verse.ref}`,
          });
          const error = await failureOf(async () =>
            analyzeVerse.mutateAsync({
              unitId: verse.unit_id,
              session_id: await ensureSession(),
              english_layer: englishLayer,
            }),
          );
          if (error) failures += 1;
          if (index === placed.length - 1) {
            markImport('verses', {
              status: failures > 0 ? 'failed' : 'done',
              detail:
                `${placed.length - failures} of ${placed.length} analysed` +
                (failures > 0 ? `, ${failures} failed` : ''),
            });
          }
          return error ? [{ label: verse.ref, error }] : [];
        },
      }));
    }

    const psalmStep: BatchStep = {
      label: 'analysing the psalm as a whole',
      unitIds: [],
      rows: 1,
      run: async () => {
        markImport('psalm', { status: 'running' });
        const error = await failureOf(async () =>
          analyzePsalm.mutateAsync({
            session_id: await ensureSession(),
            english_layer: englishLayer,
          }),
        );
        markImport('psalm', error ? { status: 'failed', detail: error } : { status: 'done' });
        return error ? [{ label: 'The psalm as a whole', error }] : [];
      },
    };

    steps.push({
      label: 'reading the pasted translation',
      unitIds: [],
      rows: 1,
      run: async () => {
        markImport('read', { status: 'running' });
        let result: ImportResult;
        try {
          result = await importTranslation.mutateAsync({
            session_id: await ensureSession(),
            text,
            layer: englishLayer,
          });
        } catch (error) {
          const message = thrownFailure(error);
          markImport('read', { status: 'failed', detail: message });
          return [{ label: 'Import', error: message }];
        }
        const failure = runFailure(result);
        if (failure) {
          markImport('read', { status: 'failed', detail: failure });
          return [{ label: 'Import', error: failure }];
        }
        const held = result.renderings.filter((r) => !r.shown).length;
        const unchanged = result.renderings.filter((r) => r.unchanged).length;
        const count = result.renderings.length;
        markImport('read', {
          status: 'done',
          detail:
            `${count} verse${count === 1 ? '' : 's'} placed` +
            (unchanged > 0 ? ` · ${unchanged} already there` : '') +
            (held > 0 ? ` · ${held} kept behind reviewed text` : '') +
            (result.guidance_added ? ' · guidance added' : ''),
          notes: [
            ...(result.guidance_added ? [`Guidance added: ${result.guidance_added}`] : []),
            ...result.unplaced.map((item) => `Not placed: “${item.text}” (${item.reason})`),
            ...(result.missing.length > 0 ? [`Not in the paste: ${result.missing.join(', ')}`] : []),
          ],
        });
        // Later steps are added now, once it is known what was placed.
        if (options.arrange) steps.push(arrangeStep);
        if (options.analyse) {
          const shown = result.renderings.filter((r) => r.shown);
          if (shown.length === 0) {
            markImport('verses', {
              status: 'skipped',
              detail: 'No placed verse is on show, so there is nothing new to analyse.',
            });
          }
          steps.push(...verseSteps(shown), psalmStep);
        }
        return [];
      },
    });

    await runBatch('import', steps);
    const stopped = stopRequested.current;
    setImportRunning(false);
    setImportSteps((list) =>
      list.map((step) => {
        if (step.status === 'running') {
          const where = step.detail ? ` at ${step.detail}` : '';
          return { ...step, status: 'skipped', detail: stopped ? `Stopped${where}.` : 'Did not finish.' };
        }
        if (step.status === 'pending') {
          return { ...step, status: 'skipped', detail: stopped ? 'Stopped before it ran.' : 'Not run.' };
        }
        return step;
      }),
    );
  }

  /**
   * Start an import from the dialog: make the project it goes into, if it is new, and the
   * psalm's translation there, if the project has none; show that translation, and run the
   * import once it is shown, so the import's Codex thread and every step belong to it.
   */
  async function startImport({ text, psalmId: target, target: into, options }: ImportRequest) {
    setImportRunning(true);
    setImportSteps([]);
    /** One making step, shown as it goes; null when it failed, which ends the import. */
    async function make<T>(key: string, label: string, work: () => Promise<T>) {
      setImportSteps((made) => [...made, { key, label, status: 'running' }]);
      try {
        const result = await work();
        markImport(key, { status: 'done' });
        return result;
      } catch (error) {
        markImport(key, { status: 'failed', detail: thrownFailure(error) });
        setImportRunning(false);
        return null;
      }
    }
    const project =
      into.kind === 'new-project'
        ? await make('project', `Making the project “${into.title}”`, () =>
            createCollection.mutateAsync(into.title),
          )
        : (collections.data ?? []).find((c) => c.collection_id === into.collectionId);
    if (!project) {
      setImportRunning(false);
      return;
    }
    const held = (collections.data ?? [])
      .find((c) => c.collection_id === project.collection_id)
      ?.members.find((m) => m.psalm_id === target);
    let intoId: string | null;
    if (held) {
      intoId = held.translation_id;
    } else {
      const made = await make('create', `Making its translation in “${project.title}”`, () =>
        createTranslation.mutateAsync({
          psalmId: target,
          title: project.title,
          collection_id: project.collection_id,
          created_via: 'import',
        }),
      );
      if (!made) return;
      intoId = made.translation_id;
    }
    onShowTranslation(target, project.collection_id);
    setQueuedImport({ psalmId: target, translationId: intoId, text, options });
  }

  // Declared after the session reset above, so a switch of translation resets it first.
  useEffect(() => {
    if (!queuedImport) return;
    if (queuedImport.psalmId !== psalmId || queuedImport.translationId !== translationId) return;
    setQueuedImport(null);
    void runImport(queuedImport.text, queuedImport.options);
  }, [queuedImport, psalmId, translationId]);

  const identifyError = identifyPsalm.isError
    ? thrownFailure(identifyPsalm.error)
    : identifyPsalm.data
      ? runFailure(identifyPsalm.data)
      : null;

  const importDialog = (
    <ImportTranslationDialog
      key="import"
      open={importOpen}
      psalms={psalms}
      collections={collections.data ?? []}
      collectionId={collectionId}
      codex={{ ready: codexReady, hint: codexHint, busy: Boolean(batch) }}
      identify={{
        run: (text) => identifyPsalm.mutate(text),
        pending: identifyPsalm.isPending,
        result: identifyError ? null : (identifyPsalm.data ?? null),
        error: identifyError,
      }}
      steps={importSteps}
      running={importRunning}
      stopping={Boolean(batch?.stopping)}
      elapsed={batch && batch.kind === 'import' ? elapsed(now - batch.startedAt) : null}
      onRun={(request) => void startImport(request)}
      onStop={stopBatch}
      onReset={() => {
        setImportSteps([]);
        identifyPsalm.reset();
      }}
      onClose={() => onImportClose?.()}
      onOpen={(next) => {
        setPane(next);
        onImportClose?.();
      }}
    />
  );

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
        translation_id: translationId,
        ...payload,
      });
    }
    setEditing(null);
  }

  // The dialog stays mounted, keyed, while an import switches psalm and the table loads.
  if (!psalmId || isLoading || error) {
    return (
      <section aria-label="Translation comparison">
        <p className={`comparison-empty${error ? ' comparison-error' : ''}`}>
          {!psalmId ? 'Select a psalm to compare.' : isLoading ? 'Loading comparison…' : String(error)}
        </p>
        {importDialog}
      </section>
    );
  }
  /** Exports of two translations of a psalm do not overwrite each other. */
  const exportName = translationId ?? psalmId;

  return (
    <section className="comparison-view" aria-label="Translation comparison">
      <header className="comparison-toolbar">
        <div className="segmented comparison-panes" role="group" aria-label="View">
          {(
            [
              ['verses', 'Verses'],
              ['arrangement', 'Arrangement'],
              ['sources', 'Sources'],
              ['liberties', 'Liberties'],
              ['text', 'Raw text'],
            ] as const
          ).map(([key, label]) => (
            <button key={key} type="button" aria-pressed={pane === key} onClick={() => setPane(key)}>
              {label}
            </button>
          ))}
        </div>
        {pane === 'verses' && analysis && analysis.sections.length > 0 ? (
          <nav className="section-jumps" aria-label="Sections">
            {analysis.sections.map((section) => (
              <button
                key={section.first_verse}
                type="button"
                onClick={() =>
                  document
                    .getElementById(`section-${section.first_verse}`)
                    ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                }
              >
                {section.title}
              </button>
            ))}
          </nav>
        ) : null}
        <div className="comparison-controls">
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
                    ? `Stopping ${batch.label}…`
                    : `${BATCH_WORDS[batch.kind].active} ${batch.label} ` +
                      `(${batch.done + 1} of ${batch.total}) · ${elapsed(now - batch.startedAt)}`}
                </span>
                <button
                  type="button"
                  disabled={batch.stopping}
                  onClick={stopBatch}
                >
                  {batch.stopping ? 'Stopping…' : 'Stop'}
                </button>
              </>
            ) : (
              <>
                {codexStatus?.status === 'available' ? (
                  <button
                    type="button"
                    disabled={connectCodex.isPending}
                    onClick={() => connectCodex.mutate()}
                  >
                    {connectCodex.isPending ? 'Connecting…' : 'Connect Codex'}
                  </button>
                ) : null}
                {connectCodex.isError ? (
                  <span className="comparison-error">
                    {readableError(connectCodex.error.message)}
                  </span>
                ) : null}
                <button
                  type="button"
                  disabled={!codexReady || fillPassage.isPending}
                  title={codexHint}
                  onClick={() =>
                    void runBatch(
                      'translate',
                      passages(
                        rows.filter((row) => row.incomplete),
                        analysis?.sections,
                      ).map(passageStep),
                    )
                  }
                >
                  Translate psalm
                </button>
                <button
                  type="button"
                  disabled={!codexReady || analyzeVerse.isPending}
                  title={codexHint ?? 'Audit the existing renderings against the Hebrew'}
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
              onClick={() =>
                download(`${exportName}-comparison.md`, toMarkdown(rows), 'text/markdown')
              }
            >
              Export Markdown
            </button>
            <button
              type="button"
              onClick={() => download(`${exportName}-comparison.csv`, toCsv(rows), 'text/csv')}
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
            How this translation of the psalm should be made. Codex reads this before the source,
            and it outranks the generic layer prompts. Saved with the translation, so it is
            versioned.
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


      {pane !== 'verses' ? (
        <ArrangementWorkspace
          psalmId={psalmId}
          translationId={translationId}
          rows={data?.rows ?? []}
          sections={analysis?.sections ?? []}
          pane={pane}
          englishLayer={englishLayer}
          selectedId={arrangementId}
          onSelect={setArrangementId}
          codex={{
            ready: codexReady,
            hint: codexHint,
            busy: Boolean(batch),
            draft: () => void draftSetting(),
          }}
        />
      ) : null}

      {pane === 'verses' && analysis ? (
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
                    ['similar', 'Similar translations'],
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

              {analysisTab === 'similar' ? (
                !analysis.similar_translations ? (
                  <p className="analysis-prose subtle-note">
                    This analysis ran before translations were compared. Analyse the psalm again to
                    compare it.
                  </p>
                ) : analysis.similar_translations.length === 0 ? (
                  <p className="analysis-prose subtle-note">
                    No existing translation stood out as close to this English.
                  </p>
                ) : (
                  <ul className="similar-translations">
                    {analysis.similar_translations.map((item) => (
                      <li key={item.translation}>
                        <strong>{item.translation}</strong> {CLOSENESS_LABELS[item.closeness]}
                        {item.basis === 'recalled' ? (
                          <em> · recalled by Codex, not checked against its text</em>
                        ) : null}
                        <span className="basis">{item.evidence}</span>
                      </li>
                    ))}
                  </ul>
                )
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

      {pane === 'verses' ? (
      <>
      <WordSummary
        psalmId={psalmId}
        translationId={translationId}
        rows={rows}
        contextRows={data?.rows ?? []}
        sections={analysis?.sections ?? []}
        englishLayer={englishLayer}
        codex={{ ready: codexReady, hint: codexHint, busy: Boolean(batch) }}
        onSuggest={suggestFor}
        onSuggestAll={(items) => void runBatch('suggest', items.map(suggestStep))}
        progress={
          batch && batch.kind === 'suggest'
            ? {
                label: batch.label,
                done: batch.done,
                total: batch.total,
                elapsed: elapsed(now - batch.startedAt),
                stopping: batch.stopping,
                onStop: stopBatch,
              }
            : null
        }
        onOpenWord={(row, tokenId) => {
          const key = row.unit_ids.join('+');
          setOpenKey(key);
          setSelectedTokenId(tokenId);
          window.setTimeout(
            () =>
              document
                .getElementById(`verse-row-${key}`)
                ?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
            50,
          );
        }}
      />

      <section className="verse-list" aria-label="Verses">
        <div className="verse-list__head" aria-hidden="true">
          <span>Verse</span>
          <span className="verse-list__he">Hebrew</span>
          <span>{englishLayer.replace(/_/g, ' ')}</span>
          <span>Fidelity</span>
        </div>
        {rows.map((row) => {
          const key = row.unit_ids.join('+');
          const isEditing = editing === row.unit_ids[0];
          const band = sectionOpening(row);
          const seam = seamAfter(row);
          const tone = row.accuracy_rating ? RATING_TONE[row.accuracy_rating] : null;
          const isOpen = openKey === key;
          const [, verse] = row.display_reference.split(':');
          const inFlight = batch?.unitIds.includes(row.unit_ids[0]) ? batch.kind : null;
          const hasEvidence =
            (row.literal_backbone?.length ?? 0) > 0 || (row.non_source_material?.length ?? 0) > 0;
          const noteCount = new Set(
            (row.tokens ?? []).flatMap((token) =>
              token.note ? [token.note.token_ids.join(',')] : [],
            ),
          ).size;
          return (
            <Fragment key={key}>
              {band ? (
                <div className="verse-band" id={`section-${band.first_verse}`}>
                  <div className="verse-band__head">
                    <span className="verse-band__range">
                      {band.first_verse === band.last_verse
                        ? `v. ${band.first_verse}`
                        : `vv. ${band.first_verse}–${band.last_verse}`}
                    </span>
                    <span className="verse-band__theme">{band.theme}</span>
                  </div>
                  {band.arc_note ? <p className="verse-band__note">{band.arc_note}</p> : null}
                </div>
              ) : null}
              <div
                id={`verse-row-${key}`}
                className={[
                  'verse',
                  isOpen ? 'is-open' : '',
                  row.incomplete ? 'incomplete' : '',
                  row.stale ? 'is-stale' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                <button
                  type="button"
                  className="verse-row"
                  aria-expanded={isOpen}
                  aria-controls={`verse-${key}`}
                  onClick={() => {
                    setOpenKey(isOpen ? null : key);
                    setSelectedTokenId(null);
                  }}
                >
                  <span className="verse-row__n">{verse ?? 'Heading'}</span>
                  {isOpen ? (
                    <span className="verse-row__meta">
                      {row.display_reference}
                      {row.mt_reference !== row.display_reference
                        ? ` · MT ${row.mt_reference}`
                        : ''}
                      {noteCount > 0 ? ` · ${noteCount} word note${noteCount === 1 ? '' : 's'}` : ''}
                      {row.created_via ? ` · ${VIA_LABELS[row.created_via]}` : ''}
                    </span>
                  ) : (
                    <>
                      <span className="verse-row__he" dir="rtl" lang="he">
                        {row.hebrew_text}
                      </span>
                      <span className="verse-row__en">
                        {row.english_text ? (
                          row.english_text.replace(/\n/g, ' ')
                        ) : (
                          <em className="cell-missing">Not translated</em>
                        )}
                      </span>
                    </>
                  )}
                  <span className="verse-row__fidelity">
                    {inFlight ? (
                      <span className="row-progress">{BATCH_WORDS[inFlight].active}…</span>
                    ) : (
                      <span className={`fidelity${tone ? ` fidelity--${tone}` : ''}`}>
                        {row.accuracy_rating
                          ? row.accuracy_rating.replace(/_/g, ' ')
                          : row.incomplete
                            ? 'Not translated'
                            : 'Not assessed'}
                      </span>
                    )}
                    {row.stale ? (
                      <span
                        className="stale-badge"
                        title="The rendering has changed since this analysis ran"
                      >
                        Stale
                      </span>
                    ) : null}
                  </span>
                  <svg
                    className="verse-row__chevron"
                    aria-hidden="true"
                    width="14"
                    height="14"
                    viewBox="0 0 12 12"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  >
                    <path d={isOpen ? 'M3 7.5l3-3 3 3' : 'M3 4.5l3 3 3-3'} />
                  </svg>
                </button>

                {isOpen ? (
                  <div id={`verse-${key}`}>
                    <VerseDetail
                      row={row}
                      englishLayer={englishLayer}
                      selectedTokenId={selectedTokenId}
                      onSelectToken={setSelectedTokenId}
                      onOpenRendering={onOpenRendering}
                      psalmId={psalmId}
                      translationId={translationId}
                      codex={{
                        ready: codexReady,
                        hint: codexHint,
                        busy: Boolean(batch),
                        rebuild: ({ layers, reanalyse }) => rebuildRow(row, layers, reanalyse),
                        analyseRebuild: () =>
                          void runBatch('analyse', [analyseRebuildStep(row)]),
                        suggest: (tokenIds) => suggestFor(row, tokenIds),
                      }}
                      rebuildProgress={
                        batch && batch.kind === 'rebuild' && batch.unitIds.includes(row.unit_ids[0])
                          ? {
                              step: batch.done + 1,
                              total: batch.total,
                              label: batch.label,
                              elapsed: elapsed(now - batch.startedAt),
                              stopping: batch.stopping,
                              onStop: stopBatch,
                            }
                          : null
                      }
                      notesEditor={
                        isEditing ? (
                          <>
                            <div>
                              <h4 className="verse-label">Accuracy</h4>
                              <select
                                aria-label="Accuracy rating"
                                value={draftRating}
                                onChange={(e) =>
                                  setDraftRating(e.target.value as AccuracyRating | '')
                                }
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
                            </div>
                            <div>
                              <h4 className="verse-label">Creative liberties</h4>
                              <textarea
                                aria-label="Creative liberties note"
                                value={draftLiberties}
                                onChange={(e) => setDraftLiberties(e.target.value)}
                              />
                              <div className="verse-edit-actions">
                                <button type="button" onClick={() => saveEdit(row)}>
                                  Save
                                </button>
                                <button type="button" onClick={() => setEditing(null)}>
                                  Cancel
                                </button>
                              </div>
                            </div>
                          </>
                        ) : null
                      }
                      evidence={
                        evidenceFor === key ? (
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
                        ) : null
                      }
                      actions={
                        <>
                          {row.assessment_status ? (
                            <span className={`status-badge status-${row.assessment_status}`}>
                              {STATUS_LABELS[row.assessment_status]}
                            </span>
                          ) : null}
                          <span className="verse-actions__spacer" />
                          <button
                            type="button"
                            disabled={!codexReady || fillPassage.isPending || Boolean(batch)}
                            title={codexHint}
                            onClick={() => void runBatch('translate', [passageStep([row])])}
                          >
                            {row.incomplete
                              ? 'Translate verse'
                              : hasOpenInstructions(row)
                                ? 'Regenerate without notes'
                                : 'Regenerate'}
                          </button>
                          {!row.incomplete ? (
                            <button
                              type="button"
                              disabled={!codexReady || analyzeVerse.isPending || Boolean(batch)}
                              onClick={() => void runBatch('analyse', [analyseStep(row)])}
                            >
                              {row.stale ? 'Re-analyse' : 'Analyse'}
                            </button>
                          ) : null}
                          {hasEvidence ? (
                            <button
                              type="button"
                              aria-expanded={evidenceFor === key}
                              onClick={() => setEvidenceFor(evidenceFor === key ? null : key)}
                            >
                              {evidenceFor === key ? 'Hide evidence' : 'Evidence'}
                            </button>
                          ) : null}
                          {!isEditing ? (
                            <button type="button" onClick={() => beginEdit(row)}>
                              Edit assessment
                            </button>
                          ) : null}
                        </>
                      }
                    />
                  </div>
                ) : null}
              </div>
              {seam ? (
                <p className="verse-seam">
                  <span className="selah">
                    {seam.marker}
                    {seam.aligns_with_section ? ' · section ends here' : ''}
                  </span>
                </p>
              ) : null}
            </Fragment>
          );
        })}
      </section>
      </>
      ) : null}
      {importDialog}
    </section>
  );
}

export default TranslationComparisonTable;
