import { AppRuntimeProvider, useAppRuntime } from './AppContext';
import { AssistantPanel } from '../components/AssistantPanel';
import { WelcomePage } from '../pages/WelcomePage';
import { WorkbenchPage } from '../pages/WorkbenchPage';

function AppContent() {
  const { route } = useAppRuntime();
  return (
    <div className="app-shell">
      <div className="app-shell__page">{route === 'workbench' ? <WorkbenchPage /> : <WelcomePage />}</div>
      <AssistantPanel />
    </div>
  );
}

export function App() {
  return (
    <AppRuntimeProvider>
      <AppContent />
    </AppRuntimeProvider>
  );
}
