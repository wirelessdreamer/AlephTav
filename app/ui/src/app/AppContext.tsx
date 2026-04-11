import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { PropsWithChildren } from 'react';

import type { Layer } from '../types';

export type AppRoute = 'welcome' | 'workbench';

export interface WorkbenchSelectionState {
  psalmId: string | null;
  unitId: string | null;
  layer: Layer;
  granularity: 'colon' | 'verse';
}

interface AppRuntimeValue {
  route: AppRoute;
  navigate: (route: AppRoute) => void;
  workbenchSelection: WorkbenchSelectionState;
  updateWorkbenchSelection: (patch: Partial<WorkbenchSelectionState>) => void;
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

export function AppRuntimeProvider({ children }: PropsWithChildren) {
  const [route, setRoute] = useState<AppRoute>(resolveRoute);
  const [workbenchSelection, setWorkbenchSelection] = useState<WorkbenchSelectionState>(DEFAULT_SELECTION);

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
    }
  };

  const value = useMemo(
    () => ({ route, navigate, workbenchSelection, updateWorkbenchSelection, applyClientAction }),
    [route, workbenchSelection],
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
