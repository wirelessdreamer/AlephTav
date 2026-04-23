import { AppRuntimeProvider, useAppRuntime } from './AppContext';
import { AssistantPanel } from '../components/AssistantPanel';
import { WelcomePage } from '../pages/WelcomePage';
import { WorkbenchPage } from '../pages/WorkbenchPage';

function AppContent() {
  const { route, assistantUi } = useAppRuntime();
  const showShellAssistant = route !== 'workbench' || assistantUi.placement === 'footer';

  return (
    <div
      className={`app-shell ${
        showShellAssistant
          ? `app-shell--assistant-${assistantUi.placement} app-shell--assistant-${assistantUi.visibility}`
          : 'app-shell--workbench'
      }`}
    >
      <div className="app-shell__page">{route === 'workbench' ? <WorkbenchPage /> : <WelcomePage />}</div>
      {showShellAssistant ? <AssistantPanel /> : null}
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
