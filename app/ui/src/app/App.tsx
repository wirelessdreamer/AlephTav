import { AppRuntimeProvider, useAppRuntime } from './AppContext';
import { AssistantPanel } from '../components/AssistantPanel';
import { WelcomePage } from '../pages/WelcomePage';
import { WorkbenchPage } from '../pages/WorkbenchPage';

function AppContent() {
  const { route, assistantUi } = useAppRuntime();
  return (
    <div className={`app-shell app-shell--assistant-${assistantUi.placement} app-shell--assistant-${assistantUi.visibility}`}>
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
