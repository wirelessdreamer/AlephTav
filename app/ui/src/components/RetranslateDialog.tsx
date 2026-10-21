import { useEffect, useId, useRef } from 'react';

/** What a retranslation would replace, and what makes it worth a second look. */
export interface PendingRetranslation {
  /** Verses whose English on show a new proposal would replace. */
  verses: number;
  /** Verses with reviewed English, which a new proposal would not replace. */
  kept: number;
  /** The guidance box holds edits that are not saved. */
  unsavedGuidance: boolean;
  /** Every verse's English was made under the guidance saved now. */
  sameGuidance: boolean;
}

interface Props {
  /** The retranslation to confirm; null keeps the dialog closed. */
  retranslation: PendingRetranslation | null;
  onConfirm: () => void;
  onCancel: () => void;
}

const verseCount = (count: number) => `${count} verse${count === 1 ? '' : 's'}`;

/** Asks before Codex writes new English over a psalm that already has it. */
export function RetranslateDialog({ retranslation, onConfirm, onCancel }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (retranslation && !element.open) element.showModal();
    if (!retranslation && element.open) element.close();
  }, [retranslation]);

  return (
    <dialog
      ref={dialog}
      className="import-dialog confirm-dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
    >
      <header className="import-dialog__head">
        <h2 id={titleId}>Retranslate this psalm?</h2>
        <button type="button" className="btn-sm btn-ghost" aria-label="Close" onClick={onCancel}>
          ×
        </button>
      </header>
      {retranslation ? (
        <div className="confirm-dialog__body">
          <p>
            Codex writes new English for {verseCount(retranslation.verses)}, replacing the English
            shown now. The current text stays on each verse as an earlier proposal.
          </p>
          {retranslation.kept > 0 ? (
            <p>
              {verseCount(retranslation.kept)} with reviewed English keep it and are not
              retranslated.
            </p>
          ) : null}
          {retranslation.unsavedGuidance ? (
            <p className="confirm-dialog__warning">
              Your guidance edits are not saved. Codex follows the saved guidance, so save first if
              the new English should follow your edits.
            </p>
          ) : null}
          {retranslation.sameGuidance ? (
            <p className="confirm-dialog__warning">
              The saved guidance has not changed since this English was made.
            </p>
          ) : null}
          <div className="import-dialog__actions">
            <button type="button" onClick={onCancel}>
              Cancel
            </button>
            <button type="button" className="btn-primary" onClick={onConfirm}>
              Retranslate
            </button>
          </div>
        </div>
      ) : null}
    </dialog>
  );
}

export default RetranslateDialog;
