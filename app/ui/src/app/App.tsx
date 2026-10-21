import { AppRuntimeProvider, useAppRuntime } from './AppContext';
import { AssistantPanel } from '../components/AssistantPanel';
import { ComparisonPage } from '../pages/ComparisonPage';
import { useIsPhone } from '../hooks/useIsPhone';
import { WelcomePage } from '../pages/WelcomePage';

function AppContent() {
  const { route, assistantUi } = useAppRuntime();
  const phone = useIsPhone();
  const showShellAssistant = !(phone && route === 'workbench');

  return (
    <div
      className={showShellAssistant ? `app-shell app-shell--assistant-${assistantUi.placement} app-shell--assistant-${assistantUi.visibility}` : 'app-shell app-shell--workbench'}
    >
      <div className="app-shell__page">{route === 'workbench' ? <ComparisonPage /> : <WelcomePage />}</div>
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
