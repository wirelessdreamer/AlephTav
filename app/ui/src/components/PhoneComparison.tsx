import { useEffect, useState, type ReactNode } from 'react';
import { RequestStatus } from './RequestStatus';

import { useAppRuntime } from '../app/AppContext';
import { useComparisonTable } from '../hooks/useComparisonAssessments';
import type { Collection, PsalmSummary } from '../types';
import { PhoneCompare } from './PhoneCompare';
import { PhoneEvidence } from './PhoneEvidence';
import { PhoneReview } from './PhoneReview';

/** The one English layer the workbench makes and shows, as on the desktop table. */
const ENGLISH_LAYER = 'lyric';

type Screen = 'compare' | 'evidence' | 'review';

const HEADINGS: Record<Screen, string> = {
  compare: 'Verse comparison',
  evidence: 'Word evidence',
  review: 'Translation review',
};

interface Props {
  psalms: PsalmSummary[];
  collections: Collection[];
  collection: Collection | undefined;
  psalmId: string | null;
  translationId: string | null;
  startupNotice?: ReactNode;
  onFullWorkbench: () => void;
}

/**
 * The comparison surface on a phone. The desktop accordion puts a verse, its
 * evidence and its review in one scrolling row; on a phone they are three screens
 * over the same verse, reached from the bar at the bottom. Everything here reads
 * the same comparison table the desktop does.
 */
export function PhoneComparison({
  psalms,
  collections,
  collection,
  psalmId,
  translationId,
  startupNotice,
  onFullWorkbench,
}: Props) {
  const { workbenchSelection, updateWorkbenchSelection } = useAppRuntime();
  const [screen, setScreen] = useState<Screen>('compare');
  const [tokenId, setTokenId] = useState<string | null>(null);
  const { data, isLoading, isFetching, error, refetch } = useComparisonTable(
    psalmId,
    'literal',
    ENGLISH_LAYER,
    translationId,
  );

  const rows = data?.rows ?? [];
  const found = rows.findIndex((candidate) =>
    candidate.unit_ids.includes(workbenchSelection.unitId ?? ''),
  );
  const index = found < 0 ? 0 : found;
  const row = rows[index] ?? null;
  const token = row?.tokens.find((item) => item.token_id === tokenId) ?? row?.tokens[0] ?? null;
  const psalmTitle = psalms.find((psalm) => psalm.psalm_id === psalmId)?.title ?? psalmId ?? '';

  // Keep the shared selection on the verse being read, so leaving the phone
  // layout opens the desktop accordion at the same place.
  useEffect(() => {
    const unitId = row?.unit_ids[0];
    if (unitId && unitId !== workbenchSelection.unitId) {
      updateWorkbenchSelection({ unitId });
    }
  }, [row, workbenchSelection.unitId, updateWorkbenchSelection]);

  function step(by: number) {
    const next = rows[index + by];
    if (!next) return;
    setTokenId(null);
    updateWorkbenchSelection({ unitId: next.unit_ids[0] });
  }

  function openEvidence(nextTokenId?: string) {
    if (nextTokenId) setTokenId(nextTokenId);
    setScreen('evidence');
  }

  return (
    <main className="comparison-shell comparison-shell--phone">
      <header className="phone-brand">
        <a className="phone-brand__mark" href="#/" aria-label="AlephTav home">
          את
        </a>
        <div>
          <p className="phone-brand__name">AlephTav</p>
          <p className="phone-brand__eyebrow">Translation comparison</p>
        </div>
      </header>
      <button type="button" onClick={onFullWorkbench}>Full workbench</button>

      <div className="phone-context">
        <label className="phone-picker">
          <span>Project</span>
          <select
            value={collection?.collection_id ?? ''}
            onChange={(event) =>
              updateWorkbenchSelection({ collectionId: event.target.value, unitId: null })
            }
          >
            {collections.map((item) => (
              <option key={item.collection_id} value={item.collection_id}>
                {item.title}
              </option>
            ))}
          </select>
        </label>
        <label className="phone-picker phone-picker--psalm">
          <span>Psalm</span>
          <select
            value={psalmId ?? ''}
            onChange={(event) =>
              updateWorkbenchSelection({ psalmId: event.target.value, unitId: null })
            }
          >
            {(collection?.members ?? []).map((member) => (
              <option key={member.psalm_id} value={member.psalm_id}>
                {psalms.find((psalm) => psalm.psalm_id === member.psalm_id)?.title ?? member.title}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="phone-title">
        <h1>{HEADINGS[screen]}</h1>
        {row ? (
          <div className="phone-stepper">
            <button
              type="button"
              onClick={() => step(-1)}
              disabled={index === 0}
              aria-label="Previous verse"
            >
              ‹
            </button>
            <span>{row.display_reference}</span>
            <button
              type="button"
              onClick={() => step(1)}
              disabled={index >= rows.length - 1}
              aria-label="Next verse"
            >
              ›
            </button>
          </div>
        ) : null}
      </div>

      <div className="phone-main">
        {startupNotice}
        <RequestStatus loading={isLoading || isFetching} error={error}
          label={isLoading ? `Loading ${psalmTitle}…` : isFetching ? 'Updating comparison…' : 'Could not load comparison.'}
          onRetry={() => void refetch()} />
        {psalmId && !isLoading && !error && !row ? (
          <p className="phone-hint">This psalm has no verses in this translation yet.</p>
        ) : null}
        {collection && !psalmId ? <p className="phone-hint">Choose a psalm in this project to compare.</p> : null}

        {row && screen === 'compare' ? (
          <PhoneCompare
            row={row}
            englishLayer={ENGLISH_LAYER}
            selectedTokenId={token?.token_id ?? null}
            onSelectToken={openEvidence}
            onOpenEvidence={() => openEvidence()}
            onOpenReview={() => setScreen('review')}
          />
        ) : null}

        {row && screen === 'evidence' ? (
          <PhoneEvidence row={row} token={token} onBack={() => setScreen('compare')} />
        ) : null}

        {row && screen === 'review' ? (
          <PhoneReview
            row={row}
            psalmId={psalmId}
            translationId={translationId}
            englishLayer={ENGLISH_LAYER}
            onOpenEvidence={() => openEvidence()}
          />
        ) : null}
      </div>

      <nav className="phone-nav" aria-label="Verse workflow">
        {(['compare', 'evidence', 'review'] as Screen[]).map((value) => (
          <button
            type="button"
            key={value}
            className={screen === value ? 'is-current' : undefined}
            aria-current={screen === value ? 'page' : undefined}
            onClick={() => setScreen(value)}
          >
            {value === 'compare' ? 'Compare' : value === 'evidence' ? 'Evidence' : 'Review'}
          </button>
        ))}
      </nav>
    </main>
  );
}
