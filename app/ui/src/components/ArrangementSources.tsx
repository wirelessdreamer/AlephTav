import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

import type {
  ArrangementView,
  BriefingGreekSources,
  ComparisonTableRow,
  CoverageUnit,
  StudyToken,
  SungLine,
  SourceChoice,
} from '../types';
import { LIBERTY_HINTS, LIBERTY_LABELS, verseOf } from './arrangementShared';
import { Fidelity } from './RebuildReview';
import { ArrangementGreekSource } from './ArrangementGreekSource';
import { SourceLicenses } from './SourceLicenses';
import { WordContextCard, placeCard, type HoveredWord } from './WordContextCard';
import './ArrangementSources.css';

interface Band {
  key: string;
  unitId: string;
  position: number;
  kind: string;
  dashed: boolean;
  d: string;
  language: 'he' | 'grc';
  scope?: 'phrase' | 'line';
}

/** Only saved phrase hints split a line; dictionary resemblance never assigns an origin. */
function OriginText({ text, choices }: { text: string; choices: SourceChoice[] }) {
  if (!choices.length) return <>{text}</>;
  const phrases = choices.flatMap(choice => choice.hebrew_phrases ?? []);
  const edges = [...new Set([0, text.length, ...phrases.flatMap(p => [p.start, p.end])])].sort((a, b) => a - b);
  return <>{edges.slice(0, -1).map((start, index) => {
    const end = edges[index + 1];
    const shared = phrases.some(p => p.start <= start && p.end >= end);
    return <span key={start} className={`arr-origin-phrase arr-origin-phrase--${shared ? 'both' : 'grc'}`}
      data-phrase-start={start} data-phrase-end={end}
      title={shared ? 'Hebrew phrase hint + recorded Greek reading (proposed)' : 'Recorded Greek reading (proposed; line scope)'}>{text.slice(start, end)}</span>;
  })}</>;
}

/** A ribbon from a span of the verse block to a span of the sung line. */
function ribbon(left: number, right: number, a1: number, a2: number, b1: number, b2: number) {
  const mid = (left + right) / 2;
  return (
    `M${left} ${a1} C${mid} ${a1} ${mid} ${b1} ${right} ${b1} ` +
    `L${right} ${b2} C${mid} ${b2} ${mid} ${a2} ${left} ${a2} Z`
  );
}

/** The verse column's gap, 0.5rem. */
const VERSE_GAP = 8;

/**
 * Tops for verse blocks of these heights, kept in order and VERSE_GAP apart, each as near
 * the top it wants as the order allows: a least-squares fit, by pooling adjacent verses
 * that would cross. A verse that wants no place sits just below the one before it.
 */
function spread(
  heights: number[],
  wanted: Array<{ top: number; weight: number } | null>,
): number[] {
  // Measured from where each block sits when packed tight, keeping the order only asks
  // that no block be shifted less than the one before it.
  const packed: number[] = [];
  let offset = 0;
  for (const height of heights) {
    packed.push(offset);
    offset += height + VERSE_GAP;
  }
  const pools: Array<{ shift: number; weight: number; size: number }> = [];
  let previous = 0;
  wanted.forEach((want, index) => {
    const shift = want ? want.top - packed[index] : previous;
    previous = shift;
    let pool = { shift, weight: want?.weight ?? 0.001, size: 1 };
    while (pools.length > 0 && pools[pools.length - 1].shift > pool.shift) {
      const before = pools.pop()!;
      const weight = before.weight + pool.weight;
      pool = {
        shift: (before.shift * before.weight + pool.shift * pool.weight) / weight,
        weight,
        size: before.size + pool.size,
      };
    }
    pools.push(pool);
  });
  return pools
    .flatMap((pool) => Array<number>(pool.size).fill(Math.max(0, pool.shift)))
    .map((shift, index) => packed[index] + shift);
}

/** A hovered verse (its unit id) or sung line ('line:12'), and where on screen it is. */
interface Spot {
  key: string;
  top: number;
  bottom: number;
  left: number;
  pinned?: boolean;
}

function spotOf(key: string, element: HTMLElement): Spot {
  const rect = element.getBoundingClientRect();
  return {
    key,
    top: rect.top,
    bottom: rect.bottom,
    left: Math.max(8, Math.min(rect.left, window.innerWidth - 440)),
  };
}

const GAP = 8;

/** How often the song carries a word, as the class that colours it. */
function carried(count: number) {
  return count === 0 ? 'is-dropped' : count > 1 ? 'is-repeated' : undefined;
}

type HebrewInspect = (word: HoveredWord | null, origin?: HTMLElement) => void;

function hebrewWordEvents(tokenId: string, onHover?: HebrewInspect, label?: string) {
  if (!onHover) return {};
  return {
    tabIndex: 0,
    role: 'button',
    'aria-label': label,
    'aria-haspopup': 'dialog' as const,
    onMouseEnter: (event: React.MouseEvent<HTMLElement>) => onHover(placeCard(tokenId, event.currentTarget)),
    onFocus: (event: React.FocusEvent<HTMLElement>) => onHover(placeCard(tokenId, event.currentTarget)),
    onMouseLeave: () => onHover(null), onBlur: () => onHover(null),
    onClick: (event: React.MouseEvent<HTMLElement>) => {
      event.stopPropagation();
      onHover({ ...placeCard(tokenId, event.currentTarget), pinned: true }, event.currentTarget);
    },
    onKeyDown: (event: React.KeyboardEvent<HTMLElement>) => {
      if (event.key === 'Escape') { event.stopPropagation(); onHover(null); }
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault(); event.stopPropagation();
        onHover({ ...placeCard(tokenId, event.currentTarget), pinned: true }, event.currentTarget);
      }
    },
  };
}

/** A verse word by word: each Hebrew word with its transliteration and gloss beneath. */
function VerseWords({
  unit,
  studyOf,
  onWordHover,
}: {
  unit: CoverageUnit;
  studyOf: Map<string, StudyToken>;
  onWordHover?: HebrewInspect;
}) {
  return (
    <div className="arr-verse__words" dir="rtl" lang="he">
      {unit.tokens.map((token) => {
        const study = studyOf.get(token.token_id);
        return (
          <span key={token.token_id} className="arr-verse__word">
            <span className={`interlinear__he ${carried(token.count) ?? ''}`}
              data-hebrew-token={token.token_id}
              {...hebrewWordEvents(token.token_id, onWordHover, `Study Hebrew ${token.surface} · ${unit.ref}`)}>{token.surface}</span>
            <span className="interlinear__tr" dir="ltr">
              {study?.transliteration ?? ' '}
            </span>
            <span className="interlinear__gl" dir="ltr">
              {study?.display_gloss ?? token.gloss ?? ' '}
            </span>
          </span>
        );
      })}
    </div>
  );
}

/** A verse's literal rendering, when it has one. */
function Literal({ row }: { row: ComparisonTableRow | undefined }) {
  if (!row?.literal_text) return null;
  return (
    <div className="arr-verse__literal">
      <span className="verse-label">Literal</span>
      <span>{row.literal_text}</span>
    </div>
  );
}

interface ArrangementContextNote {
  lineId: string;
  text: string;
  rationale: string;
  section: string;
  unanchored: boolean;
}

function ArrangementContext({ notes }: { notes: ArrangementContextNote[] | undefined }) {
  if (!notes?.length) return null;
  return <section className="arr-verse__context" aria-label="Arrangement context">
    <h5 className="arr-source-label">Context</h5>
    {notes.map(note => <div key={note.lineId} className="arr-context-note">
      <span className="arr-context-note__scope">{note.section}{note.unanchored ? ' · added line; no source anchor' : ''}</span>
      <blockquote>{note.text}</blockquote>
      <p>{note.rationale}</p>
    </div>)}
  </section>;
}

/**
 * A verse's direct translation, word by word and literal, then its fidelity with the
 * accuracy and creative-liberties notes of its assessment.
 */
function Assessment({
  reference,
  units,
  row,
  studyOf,
  layer,
  greekSources,
}: {
  reference: string;
  units: CoverageUnit[];
  row: ComparisonTableRow | undefined;
  studyOf: Map<string, StudyToken>;
  layer: string;
  greekSources?: BriefingGreekSources;
}) {
  const assessed = Boolean(
    row && (row.accuracy_rating || row.accuracy_note || row.creative_liberties_note),
  );
  return (
    <div className="source-card__section">
      <div className="occurrence-card__head">
        <strong>{reference}</strong>
        <Fidelity rating={row?.accuracy_rating ?? null} />
        {assessed ? <span className="occurrence-card__mt">{layer}</span> : null}
        {row?.stale ? (
          <span className="stale-badge" title="The rendering has changed since this analysis ran">
            stale
          </span>
        ) : null}
      </div>
      {units.map((unit) => (
        <div key={unit.unit_id} className="arr-source-pair">
          <div>
            <h5 className="arr-source-label">Hebrew (MT) · {unit.ref}</h5>
            <VerseWords unit={unit} studyOf={studyOf} />
          </div>
          <ArrangementGreekSource unitId={unit.unit_id} sources={greekSources} interactive={false} />
        </div>
      ))}
      <Literal row={row} />
      {assessed ? (
        <>
          <h5 className="verse-label">Accuracy</h5>
          <p>{row?.accuracy_note || 'Not noted.'}</p>
          <h5 className="verse-label">Creative liberties</h5>
          <p>{row?.creative_liberties_note || 'None noted.'}</p>
        </>
      ) : null}
    </div>
  );
}

/**
 * What a hovered verse or sung line departs from: a verse's accuracy and creative
 * liberties with the lines that sing it, or a line's liberty with its verses' assessments.
 */
function SourceCard({
  spot,
  sung,
  unitOf,
  rowOf,
  studyOf,
  layer,
  greekSources,
  onKeep,
  onLeave,
  onClose,
}: {
  spot: Spot;
  sung: SungLine[];
  unitOf: Map<string, CoverageUnit>;
  rowOf: Map<string, ComparisonTableRow>;
  studyOf: Map<string, StudyToken>;
  layer: string;
  greekSources?: BriefingGreekSources;
  onKeep: () => void;
  onLeave: () => void;
  onClose: () => void;
}) {
  const card = useRef<HTMLDivElement>(null);
  const [place, setPlace] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null);
  // Dock at the visible map's top, moving upward if needed to fit the complete card.
  // Only content taller than the viewport should need its own scrollbar.
  useLayoutEffect(() => {
    const measure = () => {
      const height = card.current ? card.current.scrollHeight + card.current.offsetHeight - card.current.clientHeight : 0;
      const sources = card.current?.closest('.arr-sources');
      const mapTop = sources?.querySelector('.arr-sources__map')?.getBoundingClientRect().top ?? GAP;
      const top = Math.max(GAP, Math.min(Math.max(GAP, mapTop), window.innerHeight - GAP - height));
      const maxHeight = Math.max(1, window.innerHeight - GAP - top);
      const gutter = sources?.querySelector('.arr-sources__gutter')?.getBoundingClientRect();
      const song = sources?.querySelector('.arr-sources__song')?.getBoundingClientRect();
      // Use the ribbon space on desktop. If it is too narrow, borrow space from
      // the source side, keeping the English column unobscured at every width.
      const inGutter = gutter !== undefined && gutter.width >= 260 + GAP * 2;
      const start = inGutter ? Math.max(GAP, gutter.left + GAP) : GAP;
      const end = Math.max(start + 1, Math.min(song ? song.left - GAP : window.innerWidth - GAP, window.innerWidth - GAP));
      const preferred = 26 * parseFloat(getComputedStyle(document.documentElement).fontSize);
      const width = Math.min(preferred, end - start);
      const next = {
        top,
        left: inGutter ? start + (end - start - width) / 2 : end - width,
        width,
        maxHeight,
      };
      setPlace(current => current?.top === next.top && current.left === next.left
        && current.width === next.width && current.maxHeight === next.maxHeight ? current : next);
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (card.current) observer.observe(card.current);
    const gutter = card.current?.closest('.arr-sources')?.querySelector('.arr-sources__gutter');
    if (gutter) observer.observe(gutter);
    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, true);
    return () => { observer.disconnect(); window.removeEventListener('resize', measure); window.removeEventListener('scroll', measure, true); };
  }, [spot, greekSources]);
  useEffect(() => {
    if (spot.pinned && place !== null) card.current?.focus({ preventScroll: true });
  }, [spot.pinned, place !== null]);
  useEffect(() => {
    if (!spot.pinned) return;
    const closeOutside = (event: MouseEvent) => {
      if (event.target instanceof Node && !card.current?.contains(event.target)) onClose();
    };
    document.addEventListener('click', closeOutside, true);
    return () => document.removeEventListener('click', closeOutside, true);
  }, [spot.pinned, onClose]);

  const line = sung.find((item) => `line:${item.position}` === spot.key);
  const unitIds = line
    ? [...new Set(line.line.anchors.map((anchor) => anchor.unit_id))].sort(
        (a, b) => verseOf(a) - verseOf(b),
      )
    : [spot.key];
  // One assessment per verse row, with the words of each of its units the line draws on.
  const verses: Array<{
    key: string;
    reference: string;
    units: CoverageUnit[];
    row?: ComparisonTableRow;
  }> = [];
  for (const unitId of unitIds) {
    const row = rowOf.get(unitId);
    const unit = unitOf.get(unitId);
    const key = row ? row.unit_ids.join('+') : unitId;
    const known = verses.find((verse) => verse.key === key);
    if (known) {
      if (unit) known.units.push(unit);
      continue;
    }
    verses.push({
      key,
      reference: row?.display_reference ?? unit?.ref ?? unitId,
      units: unit ? [unit] : [],
      row,
    });
  }
  // A hovered verse's lines, one entry per written line however often it is sung.
  const singings = new Map<string, { item: SungLine; times: number }>();
  if (!line) {
    for (const item of sung) {
      if (!item.line.anchors.some((anchor) => anchor.unit_id === spot.key)) continue;
      const entry = singings.get(item.line.line_id);
      if (entry) entry.times += 1;
      else singings.set(item.line.line_id, { item, times: 1 });
    }
  }

  return (
    <div
      ref={card}
      role={spot.pinned ? 'dialog' : 'tooltip'}
      aria-label="Source evidence"
      tabIndex={spot.pinned ? 0 : undefined}
      className="occurrence-card source-card"
      onMouseEnter={onKeep}
      onMouseLeave={onLeave}
      onFocus={onKeep}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) onLeave(); }}
      onKeyDown={(event) => { if (event.key === 'Escape') { event.stopPropagation(); onClose(); } }}
      style={{
        top: place?.top ?? spot.bottom + GAP,
        left: place?.left ?? spot.left,
        width: place?.width,
        maxHeight: place?.maxHeight,
        visibility: place === null ? 'hidden' : undefined,
      }}
    >
      {spot.pinned ? <div className="source-card__controls">
        <button type="button" onClick={onClose}>Close source details</button>
      </div> : null}
      {line ? (
        <div className="source-card__section">
          <div className="occurrence-card__head">
            <strong>Line {line.position}</strong>
            <span className="occurrence-card__mt">
              {line.section_label}
              {line.time > 1 ? ` · time ${line.time}` : ''}
            </span>
          </div>
          <p className="source-card__text">{line.line.text}</p>
          <div className="source-card__kinds">
            <span className={`arr-kind-chip arr-kind--${line.line.liberty}`}>
              {LIBERTY_LABELS[line.line.liberty]}
            </span>
            {line.repeat ? (
              <span className="arr-kind-chip arr-kind--repeated">{LIBERTY_LABELS.repeated}</span>
            ) : null}
            <span className="in-context__label">{LIBERTY_HINTS[line.line.liberty]}</span>
          </div>
          {line.line.rationale ? (
            <p>{line.line.rationale}</p>
          ) : line.line.liberty !== 'tracks' ? (
            <p className="word-tray__hint">No reason given.</p>
          ) : null}
        </div>
      ) : null}

      {verses.map((verse) => (
        <Assessment
          key={verse.key}
          reference={verse.reference}
          units={verse.units}
          row={verse.row}
          studyOf={studyOf}
          layer={layer}
          greekSources={greekSources}
        />
      ))}
      {verses.length === 0 ? <p>No Hebrew source anchors; Greek correspondence is unavailable.</p> : null}

      {line ? null : (
        <div className="source-card__section">
          <h5 className="verse-label">In this setting</h5>
          {singings.size === 0 ? (
            <p className="word-tray__hint">No line sings this verse.</p>
          ) : (
            <ul>
              {[...singings].map(([lineId, { item, times }]) => (
                <li key={lineId}>
                  <span className={`arr-kind-chip arr-kind--${item.line.liberty}`}>
                    {LIBERTY_LABELS[item.line.liberty]}
                  </span>{' '}
                  <span className="source-card__text">{item.line.text}</span>
                  {times > 1 ? <span className="in-context__label"> · sung {times} times</span> : null}
                  {item.line.rationale ? <p>{item.line.rationale}</p> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

/** Ribbons from each Hebrew verse to every line that sings it. */
export function ArrangementSources({
  view,
  rows,
  englishLayer,
  showLicenses = true,
}: {
  view: ArrangementView;
  /** The psalm's verses as the comparison table shows them, for their assessments. */
  rows: ComparisonTableRow[];
  englishLayer: string;
  showLicenses?: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const verseColumn = useRef<HTMLDivElement>(null);
  const songColumn = useRef<HTMLDivElement>(null);
  const songOffset = useRef(0);
  const redrawRibbons = useRef<() => void>(() => {});
  const unitBlocks = useRef(new Map<string, HTMLElement>());
  const lineRows = useRef(new Map<number, HTMLElement>());
  const [bands, setBands] = useState<Band[]>([]);
  /** Each verse's top in the verse column, beside the lines that sing it, once measured. */
  const [layout, setLayout] = useState<{ tops: number[]; height: number } | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [readingUnit, setReadingUnit] = useState<string | null>(null);
  const [spot, setSpot] = useState<Spot | null>(null);
  const [hebrewWord, setHebrewWord] = useState<HoveredWord | null>(null);
  const hebrewOrigin = useRef<HTMLElement | null>(null);
  const suppressHebrewFocus = useRef(false);
  const sourceOrigin = useRef<HTMLElement | null>(null);
  const suppressFocus = useRef(false);
  const leaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Collapsed verses retain both source texts, while hiding their lexical/literal aids. */
  const [closed, setClosed] = useState<ReadonlySet<string>>(new Set());
  const { coverage, sung } = view;
  const contextOf = useMemo(() => {
    const notes = new Map<string, ArrangementContextNote[]>();
    // Written sections avoid duplicating notes for every sung repeat. An unanchored
    // line is placed beside its preceding (or next) anchored line as stanza context,
    // without creating source anchors or ribbons for that addition.
    for (const section of view.arrangement.sections) {
      section.lines.forEach((line, index) => {
        if (!line.rationale.trim()) return;
        const unanchored = line.anchors.length === 0;
        const neighbour = unanchored
          ? [...section.lines.slice(0, index)].reverse().find(candidate => candidate.anchors.length)
            ?? section.lines.slice(index + 1).find(candidate => candidate.anchors.length)
          : line;
        for (const unitId of new Set(neighbour?.anchors.map(anchor => anchor.unit_id) ?? [])) {
          const entries = notes.get(unitId) ?? [];
          entries.push({ lineId: line.line_id, text: line.text, rationale: line.rationale,
            section: section.label, unanchored });
          notes.set(unitId, entries);
        }
      });
    }
    return notes;
  }, [view.arrangement]);
  const rowOf = useMemo(
    () => new Map(rows.flatMap((row) => row.unit_ids.map((id) => [id, row] as const))),
    [rows],
  );
  const studyOf = useMemo(
    () =>
      new Map(rows.flatMap((row) => (row.tokens ?? []).map((token) => [token.token_id, token] as const))),
    [rows],
  );
  const unitOf = useMemo(
    () => new Map(coverage.units.map((unit) => [unit.unit_id, unit] as const)),
    [coverage],
  );

  function keepCard() {
    if (leaveTimer.current !== null) clearTimeout(leaveTimer.current);
    leaveTimer.current = null;
  }

  function leaveCard() {
    keepCard();
    leaveTimer.current = setTimeout(() => setSpot(current => current?.pinned ? current : null), 180);
  }

  function closeCard(returnFocus = true) {
    keepCard();
    setSpot(null);
    if (returnFocus) {
      suppressFocus.current = true;
      sourceOrigin.current?.focus({ preventScroll: true });
      suppressFocus.current = false;
    }
  }

  useEffect(() => () => { if (leaveTimer.current !== null) clearTimeout(leaveTimer.current); }, []);

  function enter(key: string, element: HTMLElement, pinned = false) {
    if (suppressFocus.current || (spot?.pinned && !pinned)) return;
    keepCard();
    sourceOrigin.current = element.querySelector<HTMLElement>('.arr-verse__read') ?? element;
    setHover(key);
    setSpot({ ...spotOf(key, element), pinned });
  }

  function toggle(unitId: string) {
    closeCard(false);
    setClosed((current) => {
      const next = new Set(current);
      if (!next.delete(unitId)) next.add(unitId);
      return next;
    });
  }

  useEffect(() => {
    const song = songColumn.current;
    const map = container.current;
    if (!song || !map) return;
    let frame = 0;
    let goal = songOffset.current;
    let changed = true;
    let previousTime = 0;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const animate = (time: number) => {
      frame = 0;
      const readingEnglish = song.matches(':hover') || song.contains(document.activeElement);
      goal = Math.max(0, Math.min(goal, map.clientHeight - song.offsetHeight));
      if (readingEnglish) goal = Math.max(0, Math.min(songOffset.current, map.clientHeight - song.offsetHeight));
      if (changed) {
        changed = false;
        const bounds = map.getBoundingClientRect();
        const readingY = window.innerHeight * .35;
        const active = coverage.units.map(unit => ({ unit, box: unitBlocks.current.get(unit.unit_id)?.getBoundingClientRect() }))
          .filter(item => item.box && item.box.bottom > 0 && item.box.top < window.innerHeight)
          .sort((a, b) => {
            const distance = (box: DOMRect) => Math.max(box.top - readingY, readingY - box.bottom, 0);
            return distance(a.box!) - distance(b.box!);
          })[0];
        setReadingUnit(active?.unit.unit_id ?? null);
        if (bounds.top >= 32) goal = 0;
        else if (bounds.bottom > 0 && !readingEnglish) {
          if (active?.box) {
            const linked = sung.filter(item => item.line.anchors.some(anchor => anchor.unit_id === active.unit.unit_id));
            const first = linked.find(item => !item.repeat) ?? linked[0];
            if (first) {
              // Keep the first contiguous occurrence together; a later reprise should
              // not pull this verse's translation toward the end of the song.
              const group = [first];
              for (const item of linked.filter(item => item.position > first.position)) {
                if (item.position !== group[group.length - 1].position + 1) break;
                group.push(item);
              }
              const rows = group.flatMap(item => {
                const row = lineRows.current.get(item.position)?.getBoundingClientRect();
                return row ? [row] : [];
              });
              if (rows.length) {
                const sourceMiddle = (Math.max(0, active.box.top) + Math.min(window.innerHeight, active.box.bottom)) / 2;
                const englishMiddle = (rows[0].top + rows[rows.length - 1].bottom) / 2;
                goal = Math.max(0, Math.min(map.clientHeight - song.offsetHeight,
                  songOffset.current + sourceMiddle - englishMiddle));
              }
            }
          }
        }
      }
      const elapsed = previousTime ? Math.min(64, time - previousTime) : 16;
      previousTime = time;
      const difference = goal - songOffset.current;
      songOffset.current = reduced.matches || Math.abs(difference) < .5
        ? goal : songOffset.current + difference * (1 - Math.exp(-elapsed / 140));
      song.style.setProperty('--arr-song-offset', `${songOffset.current}px`);
      redrawRibbons.current();
      if (Math.abs(goal - songOffset.current) > .1) frame = requestAnimationFrame(animate);
      else previousTime = 0;
    };
    const schedule = () => {
      changed = true;
      if (!frame) frame = requestAnimationFrame(animate);
    };
    const observer = new ResizeObserver(schedule);
    observer.observe(map);
    observer.observe(song);
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    song.addEventListener('pointerleave', schedule);
    song.addEventListener('focusout', schedule);
    schedule();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      song.removeEventListener('pointerleave', schedule);
      song.removeEventListener('focusout', schedule);
    };
  }, [coverage, sung, closed]);

  useLayoutEffect(() => {
    const measure = () => {
      const box = container.current?.getBoundingClientRect();
      const column = verseColumn.current?.getBoundingClientRect();
      const firstUnit = unitBlocks.current.values().next().value;
      const firstLine = lineRows.current.values().next().value;
      if (!box || !column || !firstUnit || !firstLine) {
        setBands([]);
        setLayout(null);
        return;
      }
      const left = firstUnit.getBoundingClientRect().right - box.left;
      const right = firstLine.getBoundingClientRect().left - box.left;

      // Each verse beside the median of the lines that sing it, so a reprise of a few lines
      // does not drag it away from where most of it is sung; repeats do not pull.
      const heights = coverage.units.map(
        (unit) => unitBlocks.current.get(unit.unit_id)?.getBoundingClientRect().height ?? 0,
      );
      const wanted = coverage.units.map((unit, index) => {
        const singing = sung.filter((item) =>
          item.line.anchors.some((anchor) => anchor.unit_id === unit.unit_id),
        );
        const first = singing.some((item) => !item.repeat)
          ? singing.filter((item) => !item.repeat)
          : singing;
        const middles = first.flatMap((item) => {
          const row = lineRows.current.get(item.position)?.getBoundingClientRect();
          return row ? [(row.top + row.bottom) / 2 - column.top - songOffset.current] : [];
        });
        if (middles.length === 0) return null;
        const half = middles.length / 2;
        const median = Number.isInteger(half)
          ? (middles[half - 1] + middles[half]) / 2
          : middles[Math.floor(half)];
        return { top: median - heights[index] / 2, weight: middles.length };
      });
      const tops = spread(heights, wanted);
      const last = tops.length - 1;
      setLayout(current => {
        if (last < 0) return null;
        const height = tops[last] + heights[last];
        return current?.height === height && current.tops.length === tops.length && tops.every((top, index) => Math.abs(top - current.tops[index]) < .1)
          ? current : { tops, height };
      });
      const topOf = new Map(
        coverage.units.map((unit, index) => [unit.unit_id, column.top - box.top + tops[index]]),
      );
      // Each verse's ribbons leave it in the order its words are sung.
      const perUnit = new Map<string, Array<{ position: number; kind: string; dashed: boolean; line: SungLine['line'] }>>();
      for (const item of sung) {
        for (const anchor of item.line.anchors) {
          const list = perUnit.get(anchor.unit_id) ?? [];
          list.push({
            position: item.position,
            kind: item.repeat ? 'repeated' : item.line.liberty,
            dashed: item.line.liberty === 'added',
            line: item.line,
          });
          perUnit.set(anchor.unit_id, list);
        }
      }
      const next: Band[] = [];
      for (const [unitId, list] of perUnit) {
        const block = unitBlocks.current.get(unitId)?.getBoundingClientRect();
        const blockTop = topOf.get(unitId);
        if (!block || blockTop === undefined) continue;
        const sourceBlock = unitBlocks.current.get(unitId)!;
        const hebrewBlock = sourceBlock.querySelector('.arr-source-hebrew')!.getBoundingClientRect();
        const top = blockTop + hebrewBlock.top - block.top;
        const slot = hebrewBlock.height / list.length;
        list.forEach((entry, index) => {
          const rowElement = lineRows.current.get(entry.position);
          const row = rowElement?.getBoundingClientRect();
          if (!row) return;
          const choices = (view.source_choices ?? []).filter(choice => choice.line_id === entry.line.line_id && choice.unit_id === unitId);
          if (!choices.length) next.push({
            key: `${unitId}:${entry.position}`,
            unitId,
            position: entry.position,
            kind: entry.kind,
            dashed: entry.dashed,
            language: 'he',
            d: ribbon(
              left,
              right,
              top + index * slot + 0.5,
              top + (index + 1) * slot - 0.5,
              row.top - box.top + 3,
              row.bottom - box.top - 3,
            ),
          });
          for (const choice of choices) {
            const greekBlock = [...sourceBlock.querySelectorAll<HTMLElement>('.arr-greek-unit')]
              .find(element => element.dataset.sourceReference === choice.greek_reference)?.getBoundingClientRect();
            if (greekBlock) next.push({
              key: `${choice.choice_id}:${entry.position}:grc`, unitId, position: entry.position,
              kind: entry.kind, dashed: false, language: 'grc', scope: 'line',
              d: ribbon(left, right, blockTop + greekBlock.top - block.top + 3,
                blockTop + greekBlock.bottom - block.top - 3, row.top - box.top + 3, row.bottom - box.top - 3),
            });
            for (const phrase of choice.hebrew_phrases ?? []) {
              const words = [...sourceBlock.querySelectorAll<HTMLElement>('[data-hebrew-token]')]
                .filter(element => phrase.token_ids.includes(element.dataset.hebrewToken ?? ''))
                .map(element => element.getBoundingClientRect());
              const target = [...rowElement!.querySelectorAll<HTMLElement>('[data-phrase-start]')]
                .filter(element => Number(element.dataset.phraseStart) >= phrase.start && Number(element.dataset.phraseEnd) <= phrase.end)
                .flatMap(element => [...element.getClientRects()]);
              if (!words.length || !target.length) continue;
              next.push({
                key: `${choice.choice_id}:${entry.position}:he:${phrase.start}`, unitId, position: entry.position,
                kind: entry.kind, dashed: false, language: 'he', scope: 'phrase',
                d: ribbon(left, right, blockTop + Math.min(...words.map(r => r.top)) - block.top,
                  blockTop + Math.max(...words.map(r => r.bottom)) - block.top,
                  Math.min(...target.map(r => r.top)) - box.top, Math.max(...target.map(r => r.bottom)) - box.top),
              });
            }
          }
        });
      }
      setBands(next);
    };
    redrawRibbons.current = measure;
    measure();
    const observer = new ResizeObserver(measure);
    if (container.current) observer.observe(container.current);
    for (const block of unitBlocks.current.values()) observer.observe(block);
    for (const line of lineRows.current.values()) observer.observe(line);
    return () => { observer.disconnect(); redrawRibbons.current = () => {}; };
    // Opening or closing a verse moves the blocks below it even when the map keeps its height.
  }, [sung, coverage, closed, view.greek_sources, view.source_choices]);

  const lit = (band: Band) =>
    hover === null || hover === band.unitId || hover === `line:${band.position}`;
  const added = sung.filter((item) => item.line.anchors.length === 0).length;
  const repeatedVerses = coverage.units.filter((u) => u.tokens.some((t) => t.count > 1)).length;
  const hebrewRow = rows.find(row => row.tokens.some(token => token.token_id === hebrewWord?.tokenId));
  function inspectHebrew(word: HoveredWord | null, origin?: HTMLElement) {
    if (suppressHebrewFocus.current || (hebrewWord?.pinned && !word?.pinned)) return;
    if (word) closeCard(false);
    if (origin) hebrewOrigin.current = origin;
    setHebrewWord(word);
  }
  function closeHebrew(returnFocus = true) {
    setHebrewWord(null);
    if (returnFocus) {
      suppressHebrewFocus.current = true;
      hebrewOrigin.current?.focus({ preventScroll: true });
      suppressHebrewFocus.current = false;
    }
  }

  return (
    <div className="arr-sources">
      <div className="arr-origin-legend" aria-label="Source language connections">
        <span className="arr-origin-key arr-origin-key--he">Hebrew (MT)</span>
        <span className="arr-origin-key arr-origin-key--grc">Greek (LXX)</span>
        <span className="arr-origin-key arr-origin-key--both">Both in a phrase</span>
      </div>
      <p className="arr-source-coverage-scope">Ribbons flow from source languages to the English setting. Greek links follow recorded choices at line scope; shared highlights add explicit Hebrew phrase hints. Proposed, pending review. Word colours and coverage counts still trace Hebrew anchors.</p>
      <div className="arr-legend" aria-label="Line treatments">
        {(['tracks', 'compressed', 'expanded', 'reordered', 'repeated', 'added'] as const).map((kind) => (
          <span key={kind} className={`arr-kind-chip arr-kind--${kind}`}>
            {LIBERTY_LABELS[kind]}
          </span>
        ))}
        <span className="arr-kind-chip arr-kind--dropped">Not carried</span>
      </div>

      <div className="arr-sources__map" ref={container} onMouseLeave={() => setHover(null)}>
        <svg className="arr-sources__ribbons" aria-hidden="true">
          {bands.map((band) => (
            <path
              key={band.key}
              d={band.d}
              data-language={band.language} data-position={band.position} data-scope={band.scope ?? 'line'}
              className={`arr-band arr-band--${band.kind} arr-band--${band.language}${band.dashed ? ' is-dashed' : ''}${lit(band) ? '' : ' is-dim'}`}
            />
          ))}
        </svg>

        <div className="arr-sources__hebrew">
          <span className="verse-label">Hebrew (MT) + Greek (LXX) · MT verse order</span>
          <div
            ref={verseColumn}
            className={`arr-sources__verses${layout ? ' is-spread' : ''}`}
            style={layout ? { height: layout.height } : undefined}
          >
            {coverage.units.map((unit, index) => {
              const open = !closed.has(unit.unit_id);
              return (
                <div
                  key={unit.unit_id}
                  ref={(element) => {
                    if (element) unitBlocks.current.set(unit.unit_id, element);
                    else unitBlocks.current.delete(unit.unit_id);
                  }}
                  role="group"
                  aria-label={`Sources for ${unit.ref}`}
                  className={`arr-verse${hover === unit.unit_id ? ' is-hover' : ''}${open ? ' is-open' : ''}`}
                  onMouseEnter={(event) => enter(unit.unit_id, event.currentTarget)}
                  onMouseLeave={leaveCard}
                  onKeyDown={(event) => {
                    if (event.key === 'Escape') { closeCard(); setHover(null); }
                  }}
                  style={layout ? { top: layout.tops[index] } : undefined}
                >
                  <div className="arr-source-pair">
                    <div className="arr-source-hebrew">
                      <h5 className="arr-source-label">Hebrew (MT) · {unit.ref}</h5>
                      {open ? (
                        <div className="arr-verse__open">
                          <VerseWords unit={unit} studyOf={studyOf} onWordHover={inspectHebrew} />
                          <Literal row={rowOf.get(unit.unit_id)} />
                        </div>
                      ) : (
                        <p lang="he" dir="rtl" className="hebrew">
                          {unit.tokens.map((token) => (
                            <Fragment key={token.token_id}>
                              <span className={carried(token.count)} data-hebrew-token={token.token_id} {...hebrewWordEvents(token.token_id, inspectHebrew, `Study Hebrew ${token.surface} · ${unit.ref}`)}>
                                {token.surface}
                              </span>{' '}
                            </Fragment>
                          ))}
                        </p>
                      )}
                    </div>
                    <ArrangementGreekSource
                      unitId={unit.unit_id}
                      sources={view.greek_sources}
                      compact={!open}
                      onInspect={() => { closeCard(false); closeHebrew(false); }}
                    />
                    {open ? <ArrangementContext notes={contextOf.get(unit.unit_id)} /> : null}
                  </div>
                  <div className="arr-verse__actions">
                    <button
                      type="button"
                      className="arr-verse__read"
                      aria-label={`Read source evidence for ${unit.ref}`}
                      aria-haspopup="dialog"
                      aria-expanded={Boolean(spot?.pinned && spot.key === unit.unit_id)}
                      onClick={(event) => enter(unit.unit_id, event.currentTarget, true)}
                    >
                      Read sources
                    </button>
                    <button
                      type="button"
                      className="arr-verse__n arr-verse__toggle"
                      aria-label={`${open ? 'Collapse' : 'Expand'} source details for ${unit.ref}`}
                      aria-expanded={open}
                      onClick={() => toggle(unit.unit_id)}
                      onFocus={(event) => enter(unit.unit_id, event.currentTarget.closest('.arr-verse') as HTMLElement)}
                      onBlur={leaveCard}
                    >
                      {verseOf(unit.unit_id)}<span aria-hidden="true">{open ? ' ▾' : ' ▸'}</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="arr-sources__gutter" aria-hidden="true" />

        <div className="arr-sources__song" ref={songColumn}>
          <span className="verse-label">Song · as sung</span>
          {sung.map((item, index) => {
            const first = index === 0 || sung[index - 1].section_id !== item.section_id;
            const matchesReading = item.line.anchors.some(anchor => anchor.unit_id === readingUnit);
            return (
              <Fragment key={item.position}>
                {first ? (
                  <span className={`arr-sung__section${item.repeat ? ' is-repeat' : ''}`}>
                    {item.repeat ? '↻ ' : ''}
                    {item.section_label}
                    {item.time > 1 ? ` · time ${item.time}` : ''}
                  </span>
                ) : null}
                <div
                  ref={(element) => {
                    if (element) lineRows.current.set(item.position, element);
                    else lineRows.current.delete(item.position);
                  }}
                  className={`arr-sung${matchesReading ? ' is-reading' : ''}${item.repeat ? ' is-repeat' : ''}${item.line.anchors.length === 0 ? ' is-added' : ''}${hover === `line:${item.position}` ? ' is-hover' : ''}`}
                  data-reading-source={matchesReading ? readingUnit : undefined}
                  onMouseEnter={(event) => enter(`line:${item.position}`, event.currentTarget)}
                  onMouseLeave={leaveCard}
                  role="button"
                  tabIndex={0}
                  aria-label={`Source evidence for song line ${item.position}`}
                  aria-haspopup="dialog"
                  aria-expanded={Boolean(spot?.pinned && spot.key === `line:${item.position}`)}
                  onFocus={(event) => enter(`line:${item.position}`, event.currentTarget)}
                  onBlur={leaveCard}
                  onClick={(event) => enter(`line:${item.position}`, event.currentTarget, true)}
                  onKeyDown={(event) => {
                    if (event.key === 'Escape') { closeCard(); setHover(null); }
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault(); enter(`line:${item.position}`, event.currentTarget, true);
                    }
                  }}
                >
                  <span className="arr-line__n">{item.position}</span>
                  <span className="arr-sung__text"><OriginText text={item.line.text} choices={(view.source_choices ?? []).filter(choice => choice.line_id === item.line.line_id)} /></span>
                </div>
              </Fragment>
            );
          })}
        </div>
      </div>

      <p className="arr-sources__summary">
        {coverage.units.length} verse{coverage.units.length === 1 ? '' : 's'} → {sung.length} lines sung
        {repeatedVerses > 0 ? ` · ${repeatedVerses} verse${repeatedVerses === 1 ? '' : 's'} sung more than once` : ''}
        {added > 0 ? ` · ${added} line${added === 1 ? '' : 's'} with no Hebrew` : ''}
        {coverage.totals.dropped > 0 ? ` · ${coverage.totals.dropped} Hebrew words not carried` : ''}
      </p>
      {showLicenses ? <SourceLicenses sources={view.greek_sources} /> : null}
      {hebrewWord && hebrewRow ? <WordContextCard hovered={hebrewWord} row={hebrewRow}
        sections={[]} sung={sung} englishLayer={englishLayer} showSetting={false}
        onClose={() => closeHebrew()} onCloseOutside={() => closeHebrew(false)} /> : null}

      {spot ? (
        <SourceCard
          spot={spot}
          sung={sung}
          unitOf={unitOf}
          rowOf={rowOf}
          studyOf={studyOf}
          layer={englishLayer.replace(/_/g, ' ')}
          greekSources={view.greek_sources}
          onKeep={keepCard}
          onLeave={leaveCard}
          onClose={() => closeCard()}
        />
      ) : null}
    </div>
  );
}

export default ArrangementSources;
