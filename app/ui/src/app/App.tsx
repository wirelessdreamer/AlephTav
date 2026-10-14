import { AppRuntimeProvider, useAppRuntime } from './AppContext';
import { AssistantPanel } from '../components/AssistantPanel';
import { ComparisonPage } from '../pages/ComparisonPage';
import { useIsPhone } from '../hooks/useIsPhone';
import { WelcomePage } from '../pages/WelcomePage';

function AppContent() {
  const { route, assistantUi } = useAppRuntime();
  const phone = useIsPhone();
  // The phone layout owns the screen: the assistant panel is a desktop surface,
  // and docked into a phone viewport it covers the psalm it is meant to help with.
  const showShellAssistant =
    !(phone && route === 'workbench') &&
    (route !== 'workbench' || assistantUi.placement === 'footer');

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
