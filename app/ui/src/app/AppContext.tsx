import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
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

export interface AssistantUiState {
  visibility: 'open' | 'closed';
  placement: 'side' | 'footer';
}

interface AppRuntimeValue {
  route: AppRoute;
  navigate: (route: AppRoute) => void;
  workbenchSelection: WorkbenchSelectionState;
  updateWorkbenchSelection: (patch: Partial<WorkbenchSelectionState>) => void;
  workbenchUi: WorkbenchUiState;
  updateWorkbenchUi: (patch: Partial<WorkbenchUiState>) => void;
  assistantUi: AssistantUiState;
  updateAssistantUi: (patch: Partial<AssistantUiState>) => void;
  toggleWorkbenchTokenSelection: (tokenId: string) => void;
  toggleWorkbenchSpanSelection: (spanId: string) => void;
  clearWorkbenchSelections: () => void;
  assistantContext: {
    route: AppRoute;
    workbench: WorkbenchSelectionState;
    ui: WorkbenchUiState;
    assistant: AssistantUiState;
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

const ASSISTANT_UI_STORAGE_KEY = 'aleph-tav.assistant-ui';

function getDefaultAssistantUiState(): AssistantUiState {
  if (typeof window === 'undefined') {
    return { visibility: 'open', placement: 'side' };
  }
  return { visibility: 'open', placement: window.innerWidth <= 720 ? 'footer' : 'side' };
}

function resolveAssistantUiState(): AssistantUiState {
  if (typeof window === 'undefined') {
    return getDefaultAssistantUiState();
  }
  try {
    const raw = window.localStorage.getItem(ASSISTANT_UI_STORAGE_KEY);
    if (!raw) {
      return getDefaultAssistantUiState();
    }
    const parsed = JSON.parse(raw) as Partial<AssistantUiState>;
    return {
      visibility: parsed.visibility === 'closed' ? 'closed' : 'open',
      placement: parsed.placement === 'footer' ? 'footer' : getDefaultAssistantUiState().placement,
    };
  } catch {
    return getDefaultAssistantUiState();
  }
}

function toggleValue(values: string[], nextValue: string) {
  return values.includes(nextValue) ? values.filter((value) => value !== nextValue) : [...values, nextValue];
}

export function AppRuntimeProvider({ children }: PropsWithChildren) {
  const [route, setRoute] = useState<AppRoute>(resolveRoute);
  const [workbenchSelection, setWorkbenchSelection] = useState<WorkbenchSelectionState>(DEFAULT_SELECTION);
  const [workbenchUi, setWorkbenchUi] = useState<WorkbenchUiState>(DEFAULT_UI_STATE);
  const [assistantUi, setAssistantUi] = useState<AssistantUiState>(resolveAssistantUiState);

  useEffect(() => {
    const syncRoute = () => setRoute(resolveRoute());
    window.addEventListener('hashchange', syncRoute);
    window.addEventListener('popstate', syncRoute);
    return () => {
      window.removeEventListener('hashchange', syncRoute);
      window.removeEventListener('popstate', syncRoute);
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(ASSISTANT_UI_STORAGE_KEY, JSON.stringify(assistantUi));
  }, [assistantUi]);

  const navigate = useCallback((nextRoute: AppRoute) => {
    window.location.hash = nextRoute === 'workbench' ? '#/workbench' : '#/';
    setRoute(nextRoute);
  }, []);

  const updateWorkbenchSelection = useCallback((patch: Partial<WorkbenchSelectionState>) => {
    setWorkbenchSelection((existing) => ({ ...existing, ...patch }));
  }, []);

  const updateWorkbenchUi = useCallback((patch: Partial<WorkbenchUiState>) => {
    setWorkbenchUi((existing) => ({ ...existing, ...patch }));
  }, []);

  const updateAssistantUi = useCallback((patch: Partial<AssistantUiState>) => {
    setAssistantUi((existing) => ({ ...existing, ...patch }));
  }, []);

  const toggleWorkbenchTokenSelection = useCallback((tokenId: string) => {
    setWorkbenchUi((existing) => ({
      ...existing,
      selectedTokenIds: toggleValue(existing.selectedTokenIds, tokenId),
    }));
  }, []);

  const toggleWorkbenchSpanSelection = useCallback((spanId: string) => {
    setWorkbenchUi((existing) => ({
      ...existing,
      selectedSpanIds: toggleValue(existing.selectedSpanIds, spanId),
    }));
  }, []);

  const clearWorkbenchSelections = useCallback(() => {
    setWorkbenchUi((existing) => ({
      ...existing,
      selectedTokenIds: [],
      selectedSpanIds: [],
      selectedAlignmentId: null,
    }));
  }, []);

  const applyClientAction = useCallback((actionId: string, payload: Record<string, unknown>) => {
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
  }, [clearWorkbenchSelections, navigate, toggleWorkbenchSpanSelection, toggleWorkbenchTokenSelection, updateWorkbenchSelection, updateWorkbenchUi, workbenchSelection.layer]);

  const assistantContext = useMemo(
    () => ({
      route,
      workbench: workbenchSelection,
      ui: workbenchUi,
      assistant: assistantUi,
    }),
    [assistantUi, route, workbenchSelection, workbenchUi],
  );

  const value = useMemo(
    () => ({
      route,
      navigate,
      workbenchSelection,
      updateWorkbenchSelection,
      workbenchUi,
      updateWorkbenchUi,
      assistantUi,
      updateAssistantUi,
      toggleWorkbenchTokenSelection,
      toggleWorkbenchSpanSelection,
      clearWorkbenchSelections,
      assistantContext,
      applyClientAction,
    }),
    [route, workbenchSelection, workbenchUi, assistantUi, assistantContext],
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
