import type { ContextRun } from './verseActions';

/**
 * A verse line (or lines) with the word under discussion marked, or ``fallback``
 * (the bare phrase) when the line is not known.
 */
export function InContext({ runs, fallback }: { runs: ContextRun[] | null; fallback?: string }) {
  if (!runs) return fallback ? <span className="in-context">{fallback}</span> : null;
  return (
    <span className="in-context">
      {runs.map((run, index) =>
        run.marked ? <mark key={index}>{run.text}</mark> : <span key={index}>{run.text}</span>,
      )}
    </span>
  );
}

export default InContext;
