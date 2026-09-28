import { useEffect, useState } from 'react';

import {
  type ArrangementEdit,
  isMissingRoute,
  useArrangementView,
  useArrangements,
  useCreateArrangement,
  useEditArrangement,
} from '../hooks/useArrangements';
import type { Arrangement, ComparisonTableRow, PsalmAnalysisSection } from '../types';
import { ArrangementEditor } from './ArrangementEditor';
import { ArrangementLiberties } from './ArrangementLiberties';
import { ArrangementSources } from './ArrangementSources';
import { ArrangementText } from './ArrangementText';

export type ArrangementPane = 'arrangement' | 'sources' | 'liberties' | 'text';

interface Props {
  psalmId: string;
  /** The translation whose settings are shown; null is the psalm's main one. */
  translationId: string | null;
  /** The psalm's verses as the comparison table shows them, and its analysed sections. */
  rows: ComparisonTableRow[];
  sections: PsalmAnalysisSection[];
  pane: ArrangementPane;
  englishLayer: string;
  selectedId: string | null;
  onSelect: (arrangementId: string) => void;
  codex: { ready: boolean; hint?: string; busy: boolean; draft: () => void };
}

function readable(error: unknown): string {
  if (isMissingRoute(error)) {
    return 'The API running now started before song settings were added. Restart it to use them.';
  }
  const message = error instanceof Error ? error.message : String(error);
  try {
    const parsed = JSON.parse(message) as { detail?: unknown };
    if (typeof parsed.detail === 'string') return parsed.detail;
  } catch {
    // Not JSON: already readable.
  }
  return message;
}

/** The newest setting for this layer that is still in play, else the newest of all. */
function preferred(arrangements: Arrangement[], layer: string): string | null {
  const last = (list: Arrangement[]) => list[list.length - 1];
  const live = arrangements.filter((a) => a.status !== 'superseded');
  const forLayer = live.filter((a) => a.layer === layer);
  return (last(forLayer) ?? last(live) ?? last(arrangements))?.arrangement_id ?? null;
}

/** Song settings of the psalm: arrange, trace to the Hebrew, and review the liberties. */
export function ArrangementWorkspace({
  psalmId,
  translationId,
  rows,
  sections,
  pane,
  englishLayer,
  selectedId,
  onSelect,
  codex,
}: Props) {
  const list = useArrangements(psalmId, translationId);
  const arrangements = list.data?.arrangements ?? [];
  const refrains = list.data?.refrains ?? [];
  const current =
    selectedId && arrangements.some((a) => a.arrangement_id === selectedId)
      ? selectedId
      : preferred(arrangements, englishLayer);
  const view = useArrangementView(psalmId, current);
  const edit = useEditArrangement(psalmId, current);
  const create = useCreateArrangement(psalmId, translationId);
  const [title, setTitle] = useState('');
  const arrangement = view.data?.arrangement;
  useEffect(() => setTitle(arrangement?.title ?? ''), [arrangement?.title]);

  const apply = (change: ArrangementEdit) => edit.mutateAsync(change).catch(() => undefined);
  const draftTitle = codex.busy ? 'Codex is busy with another task.' : codex.hint;

  const actions = (
    <>
      <button
        type="button"
        className="btn-primary"
        disabled={!codex.ready || codex.busy}
        title={draftTitle ?? 'One Codex turn writes a whole-psalm setting under the guidance'}
        onClick={codex.draft}
      >
        {arrangements.length === 0 ? 'Draft with Codex' : 'Draft another with Codex'}
      </button>
      <button
        type="button"
        disabled={create.isPending}
        onClick={() =>
          void create
            .mutateAsync({ layer: englishLayer })
            .then((created) => onSelect(created.arrangement.arrangement_id))
            .catch(() => undefined)
        }
      >
        New empty setting
      </button>
    </>
  );

  return (
    <section className="arr-workspace" aria-label="Song setting">
      {refrains.length > 0 ? (
        <div className="arr-refrains" role="note">
          <span className="arr-section__repeat" aria-hidden="true">
            ↻
          </span>
          <span>
            The Hebrew repeats{' '}
            {refrains.slice(0, 2).map((refrain, index) => (
              <span key={refrain.text}>
                {index > 0 ? ' and ' : ''}
                <span lang="he" className="hebrew arr-refrains__he">
                  {refrain.text}
                </span>{' '}
                in {refrain.instances.length} verses
                {refrain.variants > 1 ? ` (${refrain.variants} spellings)` : ''}
              </span>
            ))}
            {refrains.length > 2 ? `, and ${refrains.length - 2} more` : ''}. A Codex draft sings each the
            same way every time unless there is a reason not to.
          </span>
        </div>
      ) : null}

      {list.isLoading ? <p className="comparison-empty">Loading song settings…</p> : null}
      {list.error ? <p className="comparison-error">{readable(list.error)}</p> : null}

      {!list.isLoading && !list.error && arrangements.length === 0 ? (
        <div className="arr-empty">
          <h2>No song setting yet</h2>
          <p>
            A setting is free of the verse boundaries: sections can span verses, a chorus is written
            once and sung again, and lines can compress, reorder or add. Every line names the Hebrew it
            renders and how it departs from it, and the departures are reviewed.
          </p>
          <div className="arr-empty__actions">{actions}</div>
        </div>
      ) : null}

      {arrangement ? (
        <header className="arr-head">
          {arrangements.length > 1 ? (
            <select
              aria-label="Song setting"
              value={current ?? ''}
              onChange={(event) => onSelect(event.target.value)}
            >
              {arrangements.map((a) => (
                <option key={a.arrangement_id} value={a.arrangement_id}>
                  {a.title} · {a.status} · {a.layer.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          ) : null}
          <input
            className="arr-head__title"
            aria-label="Setting title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            onBlur={() => {
              if (title.trim() && title !== arrangement.title)
                void apply({ method: 'PATCH', path: '', body: { title } });
            }}
          />
          <span className={`status-badge status-${arrangement.status}`}>{arrangement.status}</span>
          <span className="arr-chip">
            {{ codex: 'Codex draft', import: 'imported', human: 'written here' }[arrangement.created_via]} ·{' '}
            {arrangement.layer.replace(/_/g, ' ')}
          </span>
          {arrangement.guidance ? (
            <span className="arr-chip" title={arrangement.guidance}>
              under guidance
            </span>
          ) : null}
          <span className="arr-head__spacer" />
          {actions}
        </header>
      ) : null}

      {edit.error ? <p className="comparison-error">{readable(edit.error)}</p> : null}
      {create.error ? <p className="comparison-error">{readable(create.error)}</p> : null}
      {view.error ? <p className="comparison-error">{readable(view.error)}</p> : null}

      {view.data ? (
        pane === 'arrangement' ? (
          <ArrangementEditor view={view.data} edit={apply} pending={edit.isPending} />
        ) : pane === 'sources' ? (
          <ArrangementSources view={view.data} rows={rows} englishLayer={englishLayer} />
        ) : pane === 'text' ? (
          <ArrangementText view={view.data} />
        ) : (
          <ArrangementLiberties
            view={view.data}
            edit={apply}
            pending={edit.isPending}
            rows={rows}
            sections={sections}
            englishLayer={englishLayer}
          />
        )
      ) : null}
    </section>
  );
}

export default ArrangementWorkspace;
