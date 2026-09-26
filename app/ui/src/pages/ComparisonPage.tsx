import { useEffect, useState } from 'react';

import { useAppRuntime } from '../app/AppContext';
import { TranslationComparisonTable } from '../components/TranslationComparisonTable';
import { useCreateTranslation, useTranslations } from '../hooks/useTranslations';
import { usePsalms } from '../hooks/useWorkbench';
import type { PsalmSummary } from '../types';

/** The translation select's value for "New translation…"; the main translation's is ''. */
const NEW_TRANSLATION = '__new__';

/**
 * The primary editorial surface: one psalm's Hebrew beside its literal and
 * chosen English rendering, with accuracy and creative-liberty notes.
 */
export function ComparisonPage() {
  const { workbenchSelection, updateWorkbenchSelection } = useAppRuntime();
  const psalmsQuery = usePsalms();
  const psalms = (psalmsQuery.data ?? []) as PsalmSummary[];
  const selectedPsalmId = workbenchSelection.psalmId;
  const translationId = workbenchSelection.translationId;
  const translationsQuery = useTranslations(selectedPsalmId);
  const createTranslation = useCreateTranslation();
  const [importOpen, setImportOpen] = useState(false);
  /** Naming a new translation, in place of the translation picker. */
  const [naming, setNaming] = useState(false);
  const [newTitle, setNewTitle] = useState('');

  // Land on the first psalm rather than an empty screen.
  useEffect(() => {
    if (!selectedPsalmId && psalms.length > 0) {
      updateWorkbenchSelection({ psalmId: psalms[0].psalm_id });
    }
  }, [psalms, selectedPsalmId, updateWorkbenchSelection]);

  function stopNaming() {
    setNaming(false);
    setNewTitle('');
    createTranslation.reset();
  }

  return (
    <main className="comparison-shell">
      <header className="comparison-shell__header">
        <div className="comparison-shell__title">
          <a className="brand-home" href="#/" aria-label="AlephTav home">
            <img src="./brand/alephtav-mark-small.svg" alt="" width="44" height="44" />
          </a>
          <div>
            <p className="eyebrow">Translation comparison</p>
            <h1>{psalms.find((p) => p.psalm_id === selectedPsalmId)?.title ?? 'Select a psalm'}</h1>
          </div>
        </div>
        <button
          type="button"
          className="comparison-shell__import"
          disabled={psalms.length === 0}
          onClick={() => setImportOpen(true)}
        >
          Import translation
        </button>
        <label className="compact-field">
          <span>Psalm</span>
          <select
            value={selectedPsalmId ?? ''}
            onChange={(event) =>
              updateWorkbenchSelection({
                psalmId: event.target.value,
                translationId: null,
                unitId: null,
              })
            }
            disabled={psalmsQuery.isLoading}
          >
            {psalmsQuery.isLoading ? <option value="">Loading Psalms…</option> : null}
            {!psalmsQuery.isLoading && psalms.length === 0 ? (
              <option value="">No Psalms available</option>
            ) : null}
            {psalms.map((psalm) => (
              <option key={psalm.psalm_id} value={psalm.psalm_id}>
                {psalm.title}
              </option>
            ))}
          </select>
        </label>
        {naming && selectedPsalmId ? (
          <form
            className="translation-new"
            onSubmit={(event) => {
              event.preventDefault();
              const title = newTitle.trim();
              if (!title) return;
              createTranslation.mutate(
                { psalmId: selectedPsalmId, title },
                {
                  onSuccess: (created) => {
                    updateWorkbenchSelection({ translationId: created.translation_id, unitId: null });
                    stopNaming();
                  },
                },
              );
            }}
          >
            <label className="compact-field">
              <span>New translation</span>
              <input
                autoFocus
                value={newTitle}
                placeholder="Its name"
                onChange={(event) => setNewTitle(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') stopNaming();
                }}
              />
            </label>
            <button type="submit" disabled={!newTitle.trim() || createTranslation.isPending}>
              {createTranslation.isPending ? 'Creating…' : 'Create'}
            </button>
            <button type="button" onClick={stopNaming}>
              Cancel
            </button>
            {createTranslation.isError ? (
              <span className="comparison-error">{createTranslation.error.message}</span>
            ) : null}
          </form>
        ) : (
          <label className="compact-field">
            <span>Translation</span>
            <select
              value={translationId ?? ''}
              onChange={(event) => {
                if (event.target.value === NEW_TRANSLATION) {
                  setNaming(true);
                } else {
                  updateWorkbenchSelection({ translationId: event.target.value || null, unitId: null });
                }
              }}
              disabled={!selectedPsalmId || translationsQuery.isLoading}
            >
              {translationsQuery.isLoading ? (
                <option value={translationId ?? ''}>Loading translations…</option>
              ) : null}
              {(translationsQuery.data ?? []).map((translation) => (
                <option key={translation.translation_id ?? ''} value={translation.translation_id ?? ''}>
                  {translation.title}
                </option>
              ))}
              <option value={NEW_TRANSLATION}>New translation…</option>
            </select>
          </label>
        )}
      </header>

      <TranslationComparisonTable
        psalmId={selectedPsalmId ?? null}
        translationId={translationId}
        psalms={psalms}
        importOpen={importOpen}
        onImportClose={() => setImportOpen(false)}
        onShowTranslation={(psalmId, id) =>
          updateWorkbenchSelection({ psalmId, translationId: id, unitId: null })
        }
      />
    </main>
  );
}

export default ComparisonPage;
