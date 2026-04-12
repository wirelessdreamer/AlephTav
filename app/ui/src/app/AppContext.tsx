import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { PropsWithChildren } from 'react';

import type { DrawerTab, Layer } from '../types';

export type AppRoute = 'welcome' | 'workbench';

export interface WorkbenchSelectionState {
  psalmId: string | null;
  unitId: string | null;
  layer: Layer;
  granularity: 'colon' | 'verse';
}

export interface WorkbenchUiState {
  drawerTab: DrawerTab;
  selectedTokenIds: string[];
  selectedSpanIds: string[];
  selectedAlignmentId: string | null;
  compareLeftId: string | null;
  compareRightId: string | null;
  hoveredTokenId: string | null;
  hoveredSpanId: string | null;
  pinnedTokenId: string | null;
}

interface AppRuntimeValue {
  route: AppRoute;
  navigate: (route: AppRoute) => void;
  workbenchSelection: WorkbenchSelectionState;
  updateWorkbenchSelection: (patch: Partial<WorkbenchSelectionState>) => void;
  workbenchUi: WorkbenchUiState;
  updateWorkbenchUi: (patch: Partial<WorkbenchUiState>) => void;
  toggleWorkbenchTokenSelection: (tokenId: string) => void;
  toggleWorkbenchSpanSelection: (spanId: string) => void;
  clearWorkbenchSelections: () => void;
  assistantContext: {
    route: AppRoute;
    workbench: WorkbenchSelectionState;
    ui: WorkbenchUiState;
  };
  applyClientAction: (actionId: string, payload: Record<string, unknown>) => void;
}

const AppRuntimeContext = createContext<AppRuntimeValue | null>(null);

function resolveRoute(): AppRoute {
  const { hash, pathname } = window.location;
  if (hash.startsWith('#/workbench') || pathname.endsWith('/workbench')) {
    return 'workbench';
  }
  return 'welcome';
}

const DEFAULT_SELECTION: WorkbenchSelectionState = {
  psalmId: 'ps001',
  unitId: 'ps001.v001.a',
  layer: 'literal',
  granularity: 'colon',
};

const DEFAULT_UI_STATE: WorkbenchUiState = {
  drawerTab: 'concordance',
  selectedTokenIds: [],
  selectedSpanIds: [],
  selectedAlignmentId: null,
  compareLeftId: null,
  compareRightId: null,
  hoveredTokenId: null,
  hoveredSpanId: null,
  pinnedTokenId: null,
};

function toggleValue(values: string[], nextValue: string) {
  return values.includes(nextValue) ? values.filter((value) => value !== nextValue) : [...values, nextValue];
}

export function AppRuntimeProvider({ children }: PropsWithChildren) {
  const [route, setRoute] = useState<AppRoute>(resolveRoute);
  const [workbenchSelection, setWorkbenchSelection] = useState<WorkbenchSelectionState>(DEFAULT_SELECTION);
  const [workbenchUi, setWorkbenchUi] = useState<WorkbenchUiState>(DEFAULT_UI_STATE);

  useEffect(() => {
    const syncRoute = () => setRoute(resolveRoute());
    window.addEventListener('hashchange', syncRoute);
    window.addEventListener('popstate', syncRoute);
    return () => {
      window.removeEventListener('hashchange', syncRoute);
      window.removeEventListener('popstate', syncRoute);
    };
  }, []);

  const navigate = (nextRoute: AppRoute) => {
    window.location.hash = nextRoute === 'workbench' ? '#/workbench' : '#/';
    setRoute(nextRoute);
  };

  const updateWorkbenchSelection = (patch: Partial<WorkbenchSelectionState>) => {
    setWorkbenchSelection((existing) => ({ ...existing, ...patch }));
  };

  const updateWorkbenchUi = (patch: Partial<WorkbenchUiState>) => {
    setWorkbenchUi((existing) => ({ ...existing, ...patch }));
  };

  const toggleWorkbenchTokenSelection = (tokenId: string) => {
    setWorkbenchUi((existing) => ({
      ...existing,
      selectedTokenIds: toggleValue(existing.selectedTokenIds, tokenId),
    }));
  };

  const toggleWorkbenchSpanSelection = (spanId: string) => {
    setWorkbenchUi((existing) => ({
      ...existing,
      selectedSpanIds: toggleValue(existing.selectedSpanIds, spanId),
    }));
  };

  const clearWorkbenchSelections = () => {
    setWorkbenchUi((existing) => ({
      ...existing,
      selectedTokenIds: [],
      selectedSpanIds: [],
      selectedAlignmentId: null,
    }));
  };

  const applyClientAction = (actionId: string, payload: Record<string, unknown>) => {
    if (actionId === 'navigate.route') {
      navigate(String(payload.route) === 'workbench' ? 'workbench' : 'welcome');
      return;
    }
    if (actionId === 'navigate.unit') {
      navigate('workbench');
      updateWorkbenchSelection({
        psalmId: String(payload.psalm_id),
        unitId: String(payload.unit_id),
        layer: typeof payload.layer === 'string' ? (payload.layer as Layer) : workbenchSelection.layer,
      });
      return;
    }
    if (actionId === 'navigate.layer') {
      navigate('workbench');
      updateWorkbenchSelection({ layer: String(payload.layer) as Layer });
      return;
    }
    if (actionId === 'workbench.set_granularity') {
      updateWorkbenchSelection({ granularity: String(payload.granularity) as 'colon' | 'verse' });
      return;
    }
    if (actionId === 'workbench.set_drawer_tab') {
      updateWorkbenchUi({ drawerTab: String(payload.tab) as DrawerTab });
      return;
    }
    if (actionId === 'workbench.set_compare_target') {
      const side = String(payload.side);
      const renderingId = payload.rendering_id ? String(payload.rendering_id) : null;
      updateWorkbenchUi(side === 'left' ? { compareLeftId: renderingId } : { compareRightId: renderingId });
      return;
    }
    if (actionId === 'workbench.pin_token') {
      updateWorkbenchUi({ pinnedTokenId: String(payload.token_id) });
      return;
    }
    if (actionId === 'workbench.clear_pinned_token') {
      updateWorkbenchUi({ pinnedTokenId: null });
      return;
    }
    if (actionId === 'workbench.toggle_token_selection') {
      toggleWorkbenchTokenSelection(String(payload.token_id));
      return;
    }
    if (actionId === 'workbench.toggle_span_selection') {
      toggleWorkbenchSpanSelection(String(payload.span_id));
      return;
    }
    if (actionId === 'workbench.clear_selection') {
      clearWorkbenchSelections();
      return;
    }
    if (actionId === 'workbench.select_alignment') {
      updateWorkbenchUi({ selectedAlignmentId: payload.alignment_id ? String(payload.alignment_id) : null });
      return;
    }
  };

  const assistantContext = useMemo(
    () => ({
      route,
      workbench: workbenchSelection,
      ui: workbenchUi,
    }),
    [route, workbenchSelection, workbenchUi],
  );

  const value = useMemo(
    () => ({
      route,
      navigate,
      workbenchSelection,
      updateWorkbenchSelection,
      workbenchUi,
      updateWorkbenchUi,
      toggleWorkbenchTokenSelection,
      toggleWorkbenchSpanSelection,
      clearWorkbenchSelections,
      assistantContext,
      applyClientAction,
    }),
    [route, workbenchSelection, workbenchUi, assistantContext],
  );

  return <AppRuntimeContext.Provider value={value}>{children}</AppRuntimeContext.Provider>;
}

export function useAppRuntime() {
  const value = useContext(AppRuntimeContext);
  if (!value) {
    throw new Error('useAppRuntime must be used inside AppRuntimeProvider');
  }
  return value;
}
