import { useVerseHistory } from '../hooks/useComparisonAssessments';
import { RequestStatus } from './RequestStatus';
import { Diff } from './RebuildReview';
import { layerLabel, shortTime } from './verseActions';
import { TranslationContextDetails, TranslationContextHistory } from './TranslationContextHistory';

const STATUS_LABEL = { pending: 'Waiting for a decision', accepted: 'Kept', discarded: 'Discarded' };

/** Everything that happened to a verse, newest first, with each rebuild's changes. */
export function VerseHistoryPanel({ unitId, translationId }: { unitId: string; translationId: string | null }) {
  const { data, isLoading, error, refetch } = useVerseHistory(unitId, translationId);
  if (isLoading || error) return <RequestStatus loading={isLoading} error={error}
    label={isLoading ? 'Loading history…' : 'Could not load history.'} onRetry={() => void refetch()} />;
  if (!data) return null;

  return (
    <div className="verse-history">
      <section aria-label="History">
        {data.events.length === 0 ? <p className="verse-notes__hint">No verse history recorded yet.</p> : null}
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
        <TranslationContextHistory events={data.translation_history ?? []} />
        <section className="translation-context-history" aria-label="Context used for translations">
          <h4>Context used for each translation</h4>
          {data.translation_contexts?.map(item => <details key={item.rendering_id}>
            <summary>{layerLabel(item.layer)} · {shortTime(item.created_at)} · {item.rendering_id}</summary>
            {!item.complete ? <p>Only guidance was recorded for this older rendering.</p> : null}
            <TranslationContextDetails event={{ ...item.context, kind: 'guidance',
              audit_id: '', created_at: item.created_at, created_by: '', summary: '' }} />
            <p className="basis">History: {item.context.history_ids.join(', ') || 'No linked history recorded.'}</p>
          </details>)}
        </section>
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
