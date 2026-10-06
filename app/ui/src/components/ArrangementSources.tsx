import { Fragment, useLayoutEffect, useMemo, useRef, useState } from 'react';

import type {
  ArrangementView,
  ComparisonTableRow,
  CoverageUnit,
  StudyToken,
  SungLine,
} from '../types';
import { LIBERTY_HINTS, LIBERTY_LABELS, verseOf } from './arrangementShared';
import { Fidelity } from './RebuildReview';

interface Band {
  key: string;
  unitId: string;
  position: number;
  kind: string;
  dashed: boolean;
  d: string;
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

/**
 * A card squeezed smaller than this is useless, so it may overlap a block taller than the
 * window rather than collapse to nothing.
 */
const MIN_CARD = 160;

/** How often the song carries a word, as the class that colours it. */
function carried(count: number) {
  return count === 0 ? 'is-dropped' : count > 1 ? 'is-repeated' : undefined;
}

/** A verse word by word: each Hebrew word with its transliteration and gloss beneath. */
function VerseWords({
  unit,
  studyOf,
}: {
  unit: CoverageUnit;
  studyOf: Map<string, StudyToken>;
}) {
  return (
    <div className="arr-verse__words" dir="rtl" lang="he">
      {unit.tokens.map((token) => {
        const study = studyOf.get(token.token_id);
        return (
          <span key={token.token_id} className="arr-verse__word">
            <span className={`interlinear__he ${carried(token.count) ?? ''}`}>{token.surface}</span>
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
}: {
  reference: string;
  /** The units whose words to show; null leaves out the direct translation. */
  units: CoverageUnit[] | null;
  row: ComparisonTableRow | undefined;
  studyOf: Map<string, StudyToken>;
  layer: string;
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
      {units ? (
        <>
          {units.map((unit) => (
            <VerseWords key={unit.unit_id} unit={unit} studyOf={studyOf} />
          ))}
          <Literal row={row} />
        </>
      ) : null}
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
  closed,
  layer,
}: {
  spot: Spot;
  sung: SungLine[];
  unitOf: Map<string, CoverageUnit>;
  rowOf: Map<string, ComparisonTableRow>;
  studyOf: Map<string, StudyToken>;
  /** Verses collapsed to their Hebrew on the page. */
  closed: ReadonlySet<string>;
  layer: string;
}) {
  const card = useRef<HTMLDivElement>(null);
  const [place, setPlace] = useState<{ top: number; maxHeight: number } | null>(null);
  // Below the hovered block when it fits, else above. When neither fits it takes the
  // roomier side and gives up the height it cannot have, scrolling inside instead of
  // covering the block being read.
  useLayoutEffect(() => {
    const height = card.current?.scrollHeight ?? 0;
    const below = Math.max(MIN_CARD, window.innerHeight - spot.bottom - GAP * 2);
    const above = Math.max(MIN_CARD, spot.top - GAP * 2);
    if (height <= below) setPlace({ top: spot.bottom + GAP, maxHeight: below });
    else if (height <= above) setPlace({ top: spot.top - GAP - height, maxHeight: above });
    else if (below >= above) setPlace({ top: spot.bottom + GAP, maxHeight: below });
    else setPlace({ top: GAP, maxHeight: above });
  }, [spot]);

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
      role="tooltip"
      className="occurrence-card source-card"
      style={{
        top: place?.top ?? spot.bottom + GAP,
        left: spot.left,
        maxHeight: place?.maxHeight,
        visibility: place === null ? 'hidden' : undefined,
      }}
    >
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
          // A verse opened on the page already shows its direct translation.
          units={line || closed.has(spot.key) ? verse.units : null}
          row={verse.row}
          studyOf={studyOf}
          layer={layer}
        />
      ))}

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
}: {
  view: ArrangementView;
  /** The psalm's verses as the comparison table shows them, for their assessments. */
  rows: ComparisonTableRow[];
  englishLayer: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const verseColumn = useRef<HTMLDivElement>(null);
  const unitBlocks = useRef(new Map<string, HTMLElement>());
  const lineRows = useRef(new Map<number, HTMLElement>());
  const [bands, setBands] = useState<Band[]>([]);
  /** Each verse's top in the verse column, beside the lines that sing it, once measured. */
  const [layout, setLayout] = useState<{ tops: number[]; height: number } | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [spot, setSpot] = useState<Spot | null>(null);
  /** Verses collapsed to their Hebrew; the rest show their words with glosses, and their literal. */
  const [closed, setClosed] = useState<ReadonlySet<string>>(new Set());
  const { coverage, sung } = view;
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

  function enter(key: string, element: HTMLElement) {
    setHover(key);
    setSpot(spotOf(key, element));
  }

  function toggle(unitId: string) {
    setSpot(null);
    setClosed((current) => {
      const next = new Set(current);
      if (!next.delete(unitId)) next.add(unitId);
      return next;
    });
  }

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
          return row ? [(row.top + row.bottom) / 2 - column.top] : [];
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
      setLayout(last < 0 ? null : { tops, height: tops[last] + heights[last] });
      const topOf = new Map(
        coverage.units.map((unit, index) => [unit.unit_id, column.top - box.top + tops[index]]),
      );
      // Each verse's ribbons leave it in the order its words are sung.
      const perUnit = new Map<string, Array<{ position: number; kind: string; dashed: boolean }>>();
      for (const item of sung) {
        for (const anchor of item.line.anchors) {
          const list = perUnit.get(anchor.unit_id) ?? [];
          list.push({
            position: item.position,
            kind: item.repeat ? 'repeated' : item.line.liberty,
            dashed: item.line.liberty === 'added',
          });
          perUnit.set(anchor.unit_id, list);
        }
      }
      const next: Band[] = [];
      for (const [unitId, list] of perUnit) {
        const block = unitBlocks.current.get(unitId)?.getBoundingClientRect();
        const blockTop = topOf.get(unitId);
        if (!block || blockTop === undefined) continue;
        const top = blockTop + 6;
        const slot = (block.height - 12) / list.length;
        list.forEach((entry, index) => {
          const row = lineRows.current.get(entry.position)?.getBoundingClientRect();
          if (!row) return;
          next.push({
            key: `${unitId}:${entry.position}`,
            unitId,
            position: entry.position,
            kind: entry.kind,
            dashed: entry.dashed,
            d: ribbon(
              left,
              right,
              top + index * slot + 0.5,
              top + (index + 1) * slot - 0.5,
              row.top - box.top + 3,
              row.bottom - box.top - 3,
            ),
          });
        });
      }
      setBands(next);
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (container.current) observer.observe(container.current);
    return () => observer.disconnect();
    // Opening or closing a verse moves the blocks below it even when the map keeps its height.
  }, [sung, coverage, closed]);

  const lit = (band: Band) =>
    hover === null || hover === band.unitId || hover === `line:${band.position}`;
  const added = sung.filter((item) => item.line.anchors.length === 0).length;
  const repeatedVerses = coverage.units.filter((u) => u.tokens.some((t) => t.count > 1)).length;

  return (
    <div className="arr-sources">
      <div className="arr-legend" aria-label="Ribbon colours">
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
              className={`arr-band arr-band--${band.kind}${band.dashed ? ' is-dashed' : ''}${lit(band) ? '' : ' is-dim'}`}
            />
          ))}
        </svg>

        <div className="arr-sources__hebrew">
          <span className="verse-label">Hebrew · in order</span>
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
                  role="button"
                  tabIndex={0}
                  aria-expanded={open}
                  className={`arr-verse${hover === unit.unit_id ? ' is-hover' : ''}${open ? ' is-open' : ''}`}
                  onMouseEnter={(event) => enter(unit.unit_id, event.currentTarget)}
                  onMouseLeave={() => setSpot(null)}
                  onClick={() => toggle(unit.unit_id)}
                  onKeyDown={(event) => {
                    if (event.key !== 'Enter' && event.key !== ' ') return;
                    event.preventDefault();
                    toggle(unit.unit_id);
                  }}
                  style={layout ? { top: layout.tops[index] } : undefined}
                >
                  {open ? (
                    <div className="arr-verse__open">
                      <VerseWords unit={unit} studyOf={studyOf} />
                      <Literal row={rowOf.get(unit.unit_id)} />
                    </div>
                  ) : (
                    <p lang="he" dir="rtl" className="hebrew">
                      {unit.tokens.map((token) => (
                        <Fragment key={token.token_id}>
                          <span title={token.gloss} className={carried(token.count)}>
                            {token.surface}
                          </span>{' '}
                        </Fragment>
                      ))}
                    </p>
                  )}
                  <span className="arr-verse__n">{verseOf(unit.unit_id)}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="arr-sources__gutter" aria-hidden="true" />

        <div className="arr-sources__song">
          <span className="verse-label">Song · as sung</span>
          {sung.map((item, index) => {
            const first = index === 0 || sung[index - 1].section_id !== item.section_id;
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
                  className={`arr-sung${item.repeat ? ' is-repeat' : ''}${item.line.anchors.length === 0 ? ' is-added' : ''}${hover === `line:${item.position}` ? ' is-hover' : ''}`}
                  onMouseEnter={(event) => enter(`line:${item.position}`, event.currentTarget)}
                  onMouseLeave={() => setSpot(null)}
                >
                  <span className="arr-line__n">{item.position}</span>
                  <span>{item.line.text}</span>
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

      {spot ? (
        <SourceCard
          spot={spot}
          sung={sung}
          unitOf={unitOf}
          rowOf={rowOf}
          studyOf={studyOf}
          closed={closed}
          layer={englishLayer.replace(/_/g, ' ')}
        />
      ) : null}
    </div>
  );
}

export default ArrangementSources;
