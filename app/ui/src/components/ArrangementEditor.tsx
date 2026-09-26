import { useEffect, useMemo, useState } from 'react';

import type { ArrangementEdit } from '../hooks/useArrangements';
import type {
  ArrangementLine,
  ArrangementSection,
  ArrangementView,
  CoverageUnit,
  LineAnchor,
  LineLiberty,
  SectionKind,
} from '../types';
import {
  LIBERTY_HINTS,
  LIBERTY_LABELS,
  LINE_LIBERTIES,
  SECTION_KINDS,
  anchorRefs,
  syllables,
  verseOf,
} from './arrangementShared';

interface Props {
  view: ArrangementView;
  edit: (change: ArrangementEdit) => Promise<unknown>;
  pending: boolean;
}

/** Pick the Hebrew words a line renders, verse by verse. */
function AnchorPicker({
  units,
  anchors,
  onSave,
  onCancel,
}: {
  units: CoverageUnit[];
  anchors: LineAnchor[];
  onSave: (anchors: LineAnchor[]) => void;
  onCancel: () => void;
}) {
  const [picked, setPicked] = useState(() => new Set(anchors.flatMap((a) => a.token_ids)));
  const [unitId, setUnitId] = useState(anchors[0]?.unit_id ?? units[0]?.unit_id ?? '');
  const unit = units.find((u) => u.unit_id === unitId);

  function toggle(tokenId: string) {
    setPicked((current) => {
      const next = new Set(current);
      if (next.has(tokenId)) next.delete(tokenId);
      else next.add(tokenId);
      return next;
    });
  }

  function save() {
    onSave(
      units
        .map((u) => ({
          unit_id: u.unit_id,
          token_ids: u.tokens.filter((t) => picked.has(t.token_id)).map((t) => t.token_id),
        }))
        .filter((a) => a.token_ids.length > 0),
    );
  }

  return (
    <div className="anchor-picker">
      <div className="anchor-picker__verses" role="group" aria-label="Verse">
        {units.map((u) => {
          const count = u.tokens.filter((t) => picked.has(t.token_id)).length;
          return (
            <button
              key={u.unit_id}
              type="button"
              aria-pressed={u.unit_id === unitId}
              onClick={() => setUnitId(u.unit_id)}
            >
              {verseOf(u.unit_id)}
              {count > 0 ? <span className="anchor-picker__count">{count}</span> : null}
            </button>
          );
        })}
      </div>
      {unit ? (
        <div className="anchor-picker__words" dir="rtl" role="group" aria-label={`Words of ${unit.ref}`}>
          {unit.tokens.map((token) => (
            <button
              key={token.token_id}
              type="button"
              aria-pressed={picked.has(token.token_id)}
              onClick={() => toggle(token.token_id)}
            >
              <span lang="he" className="hebrew">
                {token.surface}
              </span>
              <span dir="ltr" className="anchor-picker__gloss">
                {token.gloss}
              </span>
            </button>
          ))}
        </div>
      ) : null}
      <div className="anchor-picker__actions">
        <span className="verse-notes__hint">
          {picked.size === 0
            ? 'No words picked: the line will count as added.'
            : `${picked.size} word${picked.size === 1 ? '' : 's'} picked`}
        </span>
        <button type="button" onClick={() => setPicked(new Set())}>
          Clear
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="btn-primary" onClick={save}>
          Save words
        </button>
      </div>
    </div>
  );
}

function LineRow({
  line,
  number,
  units,
  pending,
  onSave,
  onRemove,
}: {
  line: ArrangementLine;
  number: number | undefined;
  units: CoverageUnit[];
  pending: boolean;
  onSave: (change: Partial<Pick<ArrangementLine, 'text' | 'liberty' | 'rationale' | 'anchors'>>) => void;
  onRemove: () => void;
}) {
  const [text, setText] = useState(line.text);
  const [rationale, setRationale] = useState(line.rationale);
  const [anchoring, setAnchoring] = useState(false);
  useEffect(() => setText(line.text), [line.text]);
  useEffect(() => setRationale(line.rationale), [line.rationale]);
  const refs = anchorRefs(line.anchors);

  return (
    <li className={`arr-line arr-line--${line.liberty}`}>
      <span className="arr-line__n">{number ?? ''}</span>
      <input
        className="arr-line__text"
        aria-label="Line"
        value={text}
        onChange={(event) => setText(event.target.value)}
        onBlur={() => {
          if (text.trim() && text !== line.text) onSave({ text });
          else setText(line.text);
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter') event.currentTarget.blur();
        }}
      />
      <button
        type="button"
        className="arr-source"
        aria-expanded={anchoring}
        title="The Hebrew words this line renders"
        onClick={() => setAnchoring((open) => !open)}
      >
        {refs ? `from ${refs}` : 'no source'}
      </button>
      <select
        className={`arr-kind arr-kind--${line.liberty}`}
        aria-label="How the line departs from the Hebrew"
        title={LIBERTY_HINTS[line.liberty]}
        value={line.liberty}
        disabled={pending}
        onChange={(event) => onSave({ liberty: event.target.value as LineLiberty })}
      >
        {LINE_LIBERTIES.map((liberty) => (
          <option key={liberty} value={liberty} disabled={line.anchors.length === 0 && liberty !== 'added'}>
            {LIBERTY_LABELS[liberty]}
          </option>
        ))}
      </select>
      <span className="arr-line__syl" title="Syllables, roughly">
        {syllables(text)}
      </span>
      <button type="button" className="btn-sm btn-ghost" aria-label="Remove line" onClick={onRemove}>
        ×
      </button>
      {line.liberty !== 'tracks' ? (
        <input
          className="arr-line__why"
          aria-label="Why this liberty"
          placeholder="Why this liberty? Reviewers read this."
          value={rationale}
          onChange={(event) => setRationale(event.target.value)}
          onBlur={() => {
            if (rationale !== line.rationale) onSave({ rationale });
          }}
        />
      ) : null}
      {line.approvals.length > 0 ? (
        <span className="arr-line__approved">
          Approved by {line.approvals.map((a) => `${a.reviewer} (${a.reviewer_role})`).join(', ')}
        </span>
      ) : null}
      {anchoring ? (
        <AnchorPicker
          units={units}
          anchors={line.anchors}
          onCancel={() => setAnchoring(false)}
          onSave={(anchors) => {
            onSave({ anchors });
            setAnchoring(false);
          }}
        />
      ) : null}
    </li>
  );
}

function AddLine({ onAdd, placeholder }: { onAdd: (text: string) => void; placeholder: string }) {
  const [text, setText] = useState('');
  return (
    <form
      className="arr-add-line"
      onSubmit={(event) => {
        event.preventDefault();
        if (!text.trim()) return;
        onAdd(text.trim());
        setText('');
      }}
    >
      <input
        aria-label="New line"
        value={text}
        placeholder={placeholder}
        onChange={(event) => setText(event.target.value)}
      />
      <button type="submit" disabled={!text.trim()}>
        Add line
      </button>
    </form>
  );
}

function SectionCard({
  section,
  index,
  view,
  numbers,
  pending,
  edit,
}: {
  section: ArrangementSection;
  index: number;
  view: ArrangementView;
  numbers: Map<string, number>;
  pending: boolean;
  edit: Props['edit'];
}) {
  const { arrangement } = view;
  const units = view.coverage.units;
  const [label, setLabel] = useState(section.label);
  useEffect(() => setLabel(section.label), [section.label]);
  const source = section.repeat_of
    ? arrangement.sections.find((s) => s.section_id === section.repeat_of)
    : null;
  const written = source ?? section;
  const refs = anchorRefs(written.lines.flatMap((line) => line.anchors));
  const timesSung =
    1 + arrangement.sections.filter((s) => s.repeat_of === written.section_id).length;
  const thisTime = view.sung.find((item) => item.section_id === section.section_id)?.time;

  const saveLine = (line: ArrangementLine) => (change: Partial<ArrangementLine>) =>
    void edit({ method: 'PATCH', path: `lines/${line.line_id}`, body: change });
  const removeLine = (line: ArrangementLine) => () =>
    void edit({ method: 'DELETE', path: `lines/${line.line_id}` });
  const addLine = (text: string) =>
    void edit({ method: 'POST', path: `sections/${section.section_id}/lines`, body: { text } });

  return (
    <article className={`arr-section${source ? ' is-repeat' : ''}${section.kind === 'chorus' || section.kind === 'refrain' ? ' is-chorus' : ''}`}>
      <header className="arr-section__head">
        {source ? <span className="arr-section__repeat" aria-hidden="true">↻</span> : null}
        <select
          aria-label="Section kind"
          value={section.kind}
          disabled={pending}
          onChange={(event) =>
            void edit({
              method: 'PATCH',
              path: `sections/${section.section_id}`,
              body: { kind: event.target.value as SectionKind },
            })
          }
        >
          {SECTION_KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {kind}
            </option>
          ))}
        </select>
        <input
          className="arr-section__label"
          aria-label="Section label"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          onBlur={() => {
            if (label !== section.label)
              void edit({ method: 'PATCH', path: `sections/${section.section_id}`, body: { label } });
          }}
        />
        {refs ? <span className="arr-chip">from {refs}</span> : null}
        {source ? (
          <span className="arr-chip arr-chip--gold">
            {source.label || 'section'} again · time {thisTime ?? 2}
          </span>
        ) : timesSung > 1 ? (
          <span className="arr-chip arr-chip--gold">sung {timesSung} times</span>
        ) : null}
        <span className="arr-section__spacer" />
        <button
          type="button"
          className="btn-sm btn-ghost"
          aria-label="Move section up"
          disabled={index === 0 || pending}
          onClick={() =>
            void edit({ method: 'PATCH', path: `sections/${section.section_id}`, body: { index: index - 1 } })
          }
        >
          ↑
        </button>
        <button
          type="button"
          className="btn-sm btn-ghost"
          aria-label="Move section down"
          disabled={index === arrangement.sections.length - 1 || pending}
          onClick={() =>
            void edit({ method: 'PATCH', path: `sections/${section.section_id}`, body: { index: index + 1 } })
          }
        >
          ↓
        </button>
        {!source ? (
          <button
            type="button"
            className="btn-sm"
            disabled={pending}
            onClick={() =>
              void edit({
                method: 'POST',
                path: 'sections',
                body: { kind: section.kind, label: section.label, repeat_of: section.section_id },
              })
            }
          >
            Sing again
          </button>
        ) : null}
        <button
          type="button"
          className="btn-sm btn-ghost"
          disabled={pending}
          onClick={() => void edit({ method: 'DELETE', path: `sections/${section.section_id}` })}
        >
          Remove
        </button>
      </header>

      {source ? (
        <p className="arr-section__echo">{source.lines.map((line) => line.text).join(' / ')}</p>
      ) : null}
      <ol className="arr-lines">
        {section.lines.map((line) => (
          <LineRow
            key={line.line_id}
            line={line}
            number={numbers.get(line.line_id)}
            units={units}
            pending={pending}
            onSave={saveLine(line)}
            onRemove={removeLine(line)}
          />
        ))}
      </ol>
      <AddLine
        onAdd={addLine}
        placeholder={source ? 'A line for this time only' : 'Write a line, then pick its Hebrew words'}
      />
    </article>
  );
}

/** Sections of lines, written once and sung as often as the song needs. */
export function ArrangementEditor({ view, edit, pending }: Props) {
  const { arrangement, coverage, summary } = view;
  const [kind, setKind] = useState<SectionKind>('verse');
  const [label, setLabel] = useState('');

  /** Lines numbered where they are first sung. */
  const numbers = useMemo(() => {
    const map = new Map<string, number>();
    let n = 0;
    for (const item of view.sung) {
      if (!map.has(item.line.line_id)) map.set(item.line.line_id, (n += 1));
    }
    return map;
  }, [view.sung]);

  return (
    <div className="arr-editor">
      <div className="arr-editor__sections">
        {arrangement.sections.length === 0 ? (
          <p className="comparison-empty">No sections yet. Add a verse or chorus below.</p>
        ) : null}
        {arrangement.sections.map((section, index) => (
          <SectionCard
            key={section.section_id}
            section={section}
            index={index}
            view={view}
            numbers={numbers}
            pending={pending}
            edit={edit}
          />
        ))}
        <form
          className="arr-add-section"
          onSubmit={(event) => {
            event.preventDefault();
            void edit({
              method: 'POST',
              path: 'sections',
              body: { kind, label: label.trim() || kind.charAt(0).toUpperCase() + kind.slice(1) },
            });
            setLabel('');
          }}
        >
          <select aria-label="New section kind" value={kind} onChange={(e) => setKind(e.target.value as SectionKind)}>
            {SECTION_KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
          <input
            aria-label="New section label"
            placeholder="Label, e.g. Verse 2"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
          />
          <button type="submit" disabled={pending}>
            Add section
          </button>
        </form>
      </div>

      <aside className="arr-editor__aside">
        <section className="arr-panel">
          <h3 className="verse-label">Where each verse is sung</h3>
          {coverage.units.map((unit) => {
            const most = Math.max(0, ...unit.tokens.map((t) => t.count));
            const dropped = unit.tokens.filter((t) => t.count === 0).length;
            return (
              <div key={unit.unit_id} className="arr-cover">
                <span className="arr-cover__v">{verseOf(unit.unit_id)}</span>
                <span className="arr-cover__bar" aria-hidden="true">
                  {unit.tokens.map((t) => (
                    <span
                      key={t.token_id}
                      className={t.count === 0 ? 'is-dropped' : t.count > 1 ? 'is-repeated' : ''}
                    />
                  ))}
                </span>
                <span className="arr-cover__note">
                  {most === 0 ? 'not sung' : `sung ${most}×`}
                  {dropped > 0 && most > 0 ? ` · ${dropped} word${dropped === 1 ? '' : 's'} not carried` : ''}
                </span>
              </div>
            );
          })}
        </section>
        <section className="arr-panel">
          <h3 className="verse-label">Kinds of change</h3>
          <div className="arr-kinds">
            {(['tracks', 'compressed', 'expanded', 'reordered', 'repeated', 'added', 'dropped'] as const)
              .filter((k) => (summary.by_kind[k] ?? 0) > 0)
              .map((k) => (
                <span key={k} className={`arr-kind-chip arr-kind--${k}`} title={LIBERTY_HINTS[k]}>
                  {LIBERTY_LABELS[k]} {summary.by_kind[k]}
                </span>
              ))}
          </div>
          <p className="verse-notes__hint">
            {summary.sung_lines} lines sung · {summary.open === 0 ? 'every liberty settled' : `${summary.open} liberties open`}
          </p>
        </section>
      </aside>
    </div>
  );
}

export default ArrangementEditor;
