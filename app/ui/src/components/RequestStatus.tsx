/** Visible feedback belongs beside the content being requested, including failures. */
export function RequestStatus({ loading, label, error, onRetry }: {
  loading?: boolean;
  label: string;
  error?: unknown;
  onRetry?: () => void;
}) {
  if (loading) return <div className="request-status" role="status">
    <span className="request-status__spinner" aria-hidden="true" />{label}
  </div>;
  if (!error) return null;
  return <div className="request-status request-status--error" role="alert">
    <span>{label} {error instanceof Error ? error.message : String(error)}</span>
    {onRetry ? <button type="button" onClick={onRetry}>Retry</button> : null}
  </div>;
}
