import { useEffect } from 'react';

import { useAppRuntime } from '../app/AppContext';
import { TranslationComparisonTable } from '../components/TranslationComparisonTable';
import { usePsalms } from '../hooks/useWorkbench';
import type { PsalmSummary } from '../types';

/**
 * The primary editorial surface: one psalm's Hebrew beside its literal and
 * chosen English rendering, with accuracy and creative-liberty notes.
 */
export function ComparisonPage() {
  const { workbenchSelection, updateWorkbenchSelection } = useAppRuntime();
  const psalmsQuery = usePsalms();
  const psalms = (psalmsQuery.data ?? []) as PsalmSummary[];
  const selectedPsalmId = workbenchSelection.psalmId;

  // Land on the first psalm rather than an empty screen.
  useEffect(() => {
    if (!selectedPsalmId && psalms.length > 0) {
      updateWorkbenchSelection({ psalmId: psalms[0].psalm_id });
    }
  }, [psalms, selectedPsalmId, updateWorkbenchSelection]);

  return (
    <main className="comparison-shell">
      <header className="comparison-shell__header">
        <div>
          <p className="eyebrow">Translation comparison</p>
          <h1>{psalms.find((p) => p.psalm_id === selectedPsalmId)?.title ?? 'Select a psalm'}</h1>
        </div>
        <label className="compact-field">
          <span>Psalm</span>
          <select
            value={selectedPsalmId ?? ''}
            onChange={(event) =>
              updateWorkbenchSelection({ psalmId: event.target.value, unitId: null })
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
      </header>

      <TranslationComparisonTable psalmId={selectedPsalmId ?? null} />
    </main>
  );
}

export default ComparisonPage;
