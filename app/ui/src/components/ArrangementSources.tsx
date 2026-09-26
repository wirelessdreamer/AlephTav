import { Fragment, useLayoutEffect, useRef, useState } from 'react';

import type { ArrangementView } from '../types';
import { LIBERTY_LABELS, verseOf } from './arrangementShared';

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

/** Ribbons from each Hebrew verse to every line that sings it. */
export function ArrangementSources({ view }: { view: ArrangementView }) {
  const container = useRef<HTMLDivElement>(null);
  const unitBlocks = useRef(new Map<string, HTMLElement>());
  const lineRows = useRef(new Map<number, HTMLElement>());
  const [bands, setBands] = useState<Band[]>([]);
  const [hover, setHover] = useState<string | null>(null);
  const { coverage, sung } = view;

  useLayoutEffect(() => {
    const measure = () => {
      const box = container.current?.getBoundingClientRect();
      const firstUnit = unitBlocks.current.values().next().value;
      const firstLine = lineRows.current.values().next().value;
      if (!box || !firstUnit || !firstLine) {
        setBands([]);
        return;
      }
      const left = firstUnit.getBoundingClientRect().right - box.left;
      const right = firstLine.getBoundingClientRect().left - box.left;
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
        if (!block) continue;
        const top = block.top - box.top + 6;
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
  }, [sung, coverage]);

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
          {coverage.units.map((unit) => (
            <div
              key={unit.unit_id}
              ref={(element) => {
                if (element) unitBlocks.current.set(unit.unit_id, element);
                else unitBlocks.current.delete(unit.unit_id);
              }}
              className={`arr-verse${hover === unit.unit_id ? ' is-hover' : ''}`}
              onMouseEnter={() => setHover(unit.unit_id)}
            >
              <p lang="he" dir="rtl" className="hebrew">
                {unit.tokens.map((token) => (
                  <Fragment key={token.token_id}>
                    <span
                      title={token.gloss}
                      className={token.count === 0 ? 'is-dropped' : token.count > 1 ? 'is-repeated' : undefined}
                    >
                      {token.surface}
                    </span>{' '}
                  </Fragment>
                ))}
              </p>
              <span className="arr-verse__n">{verseOf(unit.unit_id)}</span>
            </div>
          ))}
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
                  onMouseEnter={() => setHover(`line:${item.position}`)}
                  title={item.line.rationale || undefined}
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
    </div>
  );
}

export default ArrangementSources;
