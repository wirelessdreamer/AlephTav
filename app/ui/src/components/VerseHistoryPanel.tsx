import { useVerseHistory } from '../hooks/useComparisonAssessments';
import { Diff } from './RebuildReview';
import { layerLabel, shortTime } from './verseActions';

const STATUS_LABEL = { pending: 'Waiting for a decision', accepted: 'Kept', discarded: 'Discarded' };

/** Everything that happened to a verse, newest first, with each rebuild's changes. */
export function VerseHistoryPanel({ unitId }: { unitId: string }) {
  const { data, isLoading, error } = useVerseHistory(unitId);
  if (isLoading) return <p className="verse-notes__hint">Loading history…</p>;
  if (error) return <p className="comparison-error">{String(error)}</p>;
  if (!data) return null;

  return (
    <div className="verse-history">
      <section aria-label="History">
        <ol className="verse-history__timeline">
          {data.events.map((event) => (
            <li key={event.audit_id}>
              <span className="verse-history__when">{shortTime(event.created_at)}</span>
              <span className="verse-history__dot" aria-hidden="true" />
              <span className="verse-history__what">
                <strong>{event.summary}</strong>{' '}
                <span className="verse-notes__hint">· {event.created_by}</span>
                {event.rationale && event.rationale !== event.summary ? (
                  <span className="note-prose">{event.rationale}</span>
                ) : null}
                <span className="verse-history__id">{event.audit_id}</span>
              </span>
            </li>
          ))}
        </ol>
      </section>

      <aside className="verse-history__rebuilds" aria-label="Rebuilds">
        <h4 className="verse-label">Rebuilds</h4>
        {data.rebuilds.length === 0 ? (
          <p className="verse-notes__hint">This verse has not been rebuilt with notes.</p>
        ) : (
          data.rebuilds.map((rebuild) => (
            <div key={rebuild.rebuild_id} className="verse-history__rebuild">
              <div className="verse-actions">
                <strong>{shortTime(rebuild.created_at)}</strong>
                <span className="chip">{STATUS_LABEL[rebuild.status]}</span>
                <span className="verse-notes__hint">
                  {rebuild.note_ids.length} note{rebuild.note_ids.length === 1 ? '' : 's'}
                </span>
              </div>
              {Object.entries(rebuild.texts).map(([layer, text]) => (
                <div key={layer}>
                  <h5 className="verse-label">{layerLabel(layer)}</h5>
                  <Diff before={text.previous ?? ''} after={text.rebuilt ?? ''} side="after" />
                </div>
              ))}
            </div>
          ))
        )}
      </aside>
    </div>
  );
}

export default VerseHistoryPanel;
