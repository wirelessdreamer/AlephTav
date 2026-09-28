import { useEffect, useId, useRef } from 'react';

/** A psalm's translation and the projects it would leave and join. */
export interface PendingMove {
  psalm: string;
  from: string;
  to: string;
}

interface Props {
  /** The move to confirm; null keeps the dialog closed. */
  move: PendingMove | null;
  moving: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Asks before a translation leaves its project for another. */
export function MoveTranslationDialog({ move, moving, error, onConfirm, onCancel }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (move && !element.open) element.showModal();
    if (!move && element.open) element.close();
  }, [move]);

  return (
    <dialog
      ref={dialog}
      className="import-dialog confirm-dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        if (!moving) onCancel();
      }}
    >
      <header className="import-dialog__head">
        <h2 id={titleId}>Move this translation?</h2>
        <button
          type="button"
          className="btn-sm btn-ghost"
          aria-label="Close"
          disabled={moving}
          onClick={onCancel}
        >
          ×
        </button>
      </header>
      {move ? (
        <div className="confirm-dialog__body">
          <p>
            {move.psalm} moves from “{move.from}” to “{move.to}”. Its English, guidance,
            assessments, analysis, song settings and verse notes go with it, and “{move.from}” no
            longer has {move.psalm}.
          </p>
          {error ? <p className="comparison-error">{error}</p> : null}
          <div className="import-dialog__actions">
            <button type="button" disabled={moving} onClick={onCancel}>
              Cancel
            </button>
            <button type="button" className="btn-primary" disabled={moving} onClick={onConfirm}>
              {moving ? 'Moving…' : 'Move'}
            </button>
          </div>
        </div>
      ) : null}
    </dialog>
  );
}

export default MoveTranslationDialog;
