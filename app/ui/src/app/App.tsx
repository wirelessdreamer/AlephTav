import { AppRuntimeProvider, useAppRuntime } from './AppContext';
import { AssistantPanel } from '../components/AssistantPanel';
import { ComparisonPage } from '../pages/ComparisonPage';
import { WelcomePage } from '../pages/WelcomePage';

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
