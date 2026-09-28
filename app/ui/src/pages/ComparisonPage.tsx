import { useEffect, useState } from 'react';

import { useAppRuntime } from '../app/AppContext';
import { MoveTranslationDialog } from '../components/MoveTranslationDialog';
import { TranslationComparisonTable } from '../components/TranslationComparisonTable';
import {
  useCollections,
  useCreateCollection,
  useCreateTranslation,
  useMoveTranslation,
  useRenameCollection,
} from '../hooks/useTranslations';
import { usePsalms } from '../hooks/useWorkbench';
import type { PsalmSummary } from '../types';

/** Select values for the actions listed after the projects and the psalms. */
const NEW_PROJECT = '__new__';
const RENAME_PROJECT = '__rename__';
const ADD_PSALM = '__add__';

/** An API error's detail, else its text. */
function detail(error: Error): string {
  try {
    const parsed = JSON.parse(error.message) as { detail?: unknown };
    if (typeof parsed.detail === 'string') return parsed.detail;
  } catch {
    // Not JSON: already readable.
  }
  return error.message;
}

/**
 * The primary editorial surface: one psalm's Hebrew beside its literal and
 * chosen English rendering, with accuracy and creative-liberty notes. A project is
 * chosen first; the psalm's translation in it is the one shown.
 */
export function ComparisonPage() {
  const { workbenchSelection, updateWorkbenchSelection } = useAppRuntime();
  const psalmsQuery = usePsalms();
  const psalms = (psalmsQuery.data ?? []) as PsalmSummary[];
  const collectionsQuery = useCollections();
  const collections = collectionsQuery.data ?? [];
  const collection =
    collections.find((c) => c.collection_id === workbenchSelection.collectionId) ?? collections[0];
  const members = collection?.members ?? [];
  const member = members.find((m) => m.psalm_id === workbenchSelection.psalmId);
  const psalmId = member?.psalm_id ?? null;
  const translationId = member?.translation_id ?? null;
  const createCollection = useCreateCollection();
  const renameCollection = useRenameCollection();
  const createTranslation = useCreateTranslation();
  const moveTranslation = useMoveTranslation();
  const [importOpen, setImportOpen] = useState(false);
  /** Naming a project, in place of the project picker: a new one, or this one anew. */
  const [naming, setNaming] = useState<'new' | 'rename' | null>(null);
  const [name, setName] = useState('');
  /** Picking a psalm to add to the project, in place of the psalm picker. */
  const [adding, setAdding] = useState(false);
  const [addPsalmId, setAddPsalmId] = useState('');
  /** The project the translation on show would move to, while the move awaits confirmation. */
  const [moveTarget, setMoveTarget] = useState<string | null>(null);

  const psalmTitle = (id: string) => psalms.find((p) => p.psalm_id === id)?.title ?? id;

  // Show a project that exists, and a psalm it has: the one chosen, else its first.
  useEffect(() => {
    if (!collection) return;
    if (collection.collection_id !== workbenchSelection.collectionId) {
      updateWorkbenchSelection({ collectionId: collection.collection_id });
    } else if (!member && members.length > 0) {
      updateWorkbenchSelection({ psalmId: members[0].psalm_id, unitId: null });
    }
  }, [collection, member, members, workbenchSelection.collectionId, updateWorkbenchSelection]);

  function stopNaming() {
    setNaming(null);
    setName('');
    createCollection.reset();
    renameCollection.reset();
  }

  function cancelMove() {
    setMoveTarget(null);
    moveTranslation.reset();
  }

  function stopAdding() {
    setAdding(false);
    setAddPsalmId('');
    createTranslation.reset();
  }

  const namingError = createCollection.error ?? renameCollection.error;
  const outside = psalms.filter((psalm) => !members.some((m) => m.psalm_id === psalm.psalm_id));

  return (
    <main className="comparison-shell">
      <header className="comparison-shell__header">
        <div className="comparison-shell__title">
          <a className="brand-home" href="#/" aria-label="AlephTav home">
            <img src="./brand/alephtav-mark-small.svg" alt="" width="44" height="44" />
          </a>
          <div>
            <p className="eyebrow">Translation comparison</p>
            <h1>{psalmId ? psalmTitle(psalmId) : (collection?.title ?? 'Select a project')}</h1>
          </div>
        </div>
        <button
          type="button"
          className="comparison-shell__import"
          disabled={psalms.length === 0 || !collection}
          onClick={() => setImportOpen(true)}
        >
          Import translation
        </button>

        {naming && collection ? (
          <form
            className="translation-new"
            onSubmit={(event) => {
              event.preventDefault();
              const title = name.trim();
              if (!title) return;
              if (naming === 'new') {
                createCollection.mutate(title, {
                  onSuccess: (created) => {
                    updateWorkbenchSelection({ collectionId: created.collection_id, unitId: null });
                    stopNaming();
                    setAdding(true);
                  },
                });
              } else {
                renameCollection.mutate(
                  { collectionId: collection.collection_id, title },
                  { onSuccess: stopNaming },
                );
              }
            }}
          >
            <label className="compact-field">
              <span>{naming === 'new' ? 'New project' : `Rename “${collection.title}”`}</span>
              <input
                autoFocus
                value={name}
                placeholder="Its name"
                onChange={(event) => setName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Escape') stopNaming();
                }}
              />
            </label>
            <button
              type="submit"
              disabled={!name.trim() || createCollection.isPending || renameCollection.isPending}
            >
              {naming === 'new' ? 'Create' : 'Rename'}
            </button>
            <button type="button" onClick={stopNaming}>
              Cancel
            </button>
            {namingError ? <span className="comparison-error">{detail(namingError)}</span> : null}
          </form>
        ) : (
          <label className="compact-field">
            <span>Project</span>
            <select
              value={collection?.collection_id ?? ''}
              disabled={!collection}
              onChange={(event) => {
                const value = event.target.value;
                if (value === NEW_PROJECT) {
                  setNaming('new');
                } else if (value === RENAME_PROJECT) {
                  setNaming('rename');
                  setName(collection?.title ?? '');
                } else {
                  stopAdding();
                  updateWorkbenchSelection({ collectionId: value, unitId: null });
                }
              }}
            >
              {collectionsQuery.isLoading ? <option value="">Loading projects…</option> : null}
              {collections.map((c) => (
                <option key={c.collection_id} value={c.collection_id}>
                  {c.title}
                </option>
              ))}
              <option value={NEW_PROJECT}>New project…</option>
              {collection && !collection.built_in ? (
                <option value={RENAME_PROJECT}>Rename “{collection.title}”…</option>
              ) : null}
            </select>
          </label>
        )}

        {adding && collection ? (
          <form
            className="translation-new"
            onSubmit={(event) => {
              event.preventDefault();
              if (!addPsalmId) return;
              createTranslation.mutate(
                { psalmId: addPsalmId, title: collection.title, collection_id: collection.collection_id },
                {
                  onSuccess: (created) => {
                    updateWorkbenchSelection({ psalmId: created.psalm_id, unitId: null });
                    stopAdding();
                  },
                },
              );
            }}
          >
            <label className="compact-field">
              <span>Add to “{collection.title}”</span>
              <select
                autoFocus
                value={addPsalmId}
                onChange={(event) => setAddPsalmId(event.target.value)}
              >
                <option value="">Choose a psalm…</option>
                {outside.map((psalm) => (
                  <option key={psalm.psalm_id} value={psalm.psalm_id}>
                    {psalm.title}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={!addPsalmId || createTranslation.isPending}>
              {createTranslation.isPending ? 'Adding…' : 'Add'}
            </button>
            <button type="button" onClick={stopAdding}>
              Cancel
            </button>
            {createTranslation.error ? (
              <span className="comparison-error">{detail(createTranslation.error)}</span>
            ) : null}
          </form>
        ) : (
          <label className="compact-field">
            <span>Psalm</span>
            <select
              value={psalmId ?? ''}
              disabled={!collection || psalmsQuery.isLoading}
              onChange={(event) => {
                if (event.target.value === ADD_PSALM) {
                  setAdding(true);
                } else {
                  updateWorkbenchSelection({ psalmId: event.target.value, unitId: null });
                }
              }}
            >
              {members.length === 0 ? <option value="">No psalms yet</option> : null}
              {members.map((m) => (
                <option key={m.psalm_id} value={m.psalm_id}>
                  {psalmTitle(m.psalm_id)}
                </option>
              ))}
              <option value={ADD_PSALM}>Add a psalm…</option>
            </select>
          </label>
        )}

        {psalmId && collection ? (
          <label className="compact-field">
            <span>Move this translation to</span>
            <select
              value=""
              disabled={moveTranslation.isPending || collections.length < 2}
              onChange={(event) => {
                if (event.target.value) setMoveTarget(event.target.value);
              }}
            >
              <option value="">{moveTranslation.isPending ? 'Moving…' : 'Choose a project…'}</option>
              {collections
                .filter((c) => c.collection_id !== collection.collection_id)
                .map((c) => {
                  const has = c.members.some((m) => m.psalm_id === psalmId);
                  return (
                    <option key={c.collection_id} value={c.collection_id} disabled={has}>
                      {c.title}
                      {has ? ` (has ${psalmTitle(psalmId)})` : ''}
                    </option>
                  );
                })}
            </select>
          </label>
        ) : null}
      </header>

      <MoveTranslationDialog
        move={
          psalmId && collection && moveTarget
            ? {
                psalm: psalmTitle(psalmId),
                from: collection.title,
                to: collections.find((c) => c.collection_id === moveTarget)?.title ?? moveTarget,
              }
            : null
        }
        moving={moveTranslation.isPending}
        error={moveTranslation.error ? detail(moveTranslation.error) : null}
        onCancel={cancelMove}
        onConfirm={() => {
          if (!psalmId || !moveTarget) return;
          moveTranslation.mutate(
            { psalmId, translation_id: translationId, collection_id: moveTarget },
            {
              onSuccess: () => {
                setMoveTarget(null);
                // Follow the translation to where it now is.
                updateWorkbenchSelection({ collectionId: moveTarget, unitId: null });
              },
            },
          );
        }}
      />

      <TranslationComparisonTable
        psalmId={psalmId}
        translationId={translationId}
        collectionId={collection?.collection_id ?? null}
        psalms={psalms}
        importOpen={importOpen}
        onImportClose={() => setImportOpen(false)}
        onShowTranslation={(shownPsalmId, collectionId) =>
          updateWorkbenchSelection({ psalmId: shownPsalmId, collectionId, unitId: null })
        }
      />
    </main>
  );
}

export default ComparisonPage;
