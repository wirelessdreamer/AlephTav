import { useEffect, useState } from 'react';

import { WelcomePage } from '../pages/WelcomePage';
import { WorkbenchPage } from '../pages/WorkbenchPage';

function resolveRoute() {
  const { hash, pathname } = window.location;
  if (hash.startsWith('#/workbench')) {
    return 'workbench';
  }
  if (pathname.endsWith('/workbench')) {
    return 'workbench';
  }
  return 'welcome';
}

export function App() {
  const [route, setRoute] = useState(resolveRoute);

  useEffect(() => {
    const syncRoute = () => setRoute(resolveRoute());
    window.addEventListener('hashchange', syncRoute);
    window.addEventListener('popstate', syncRoute);
    return () => {
      window.removeEventListener('hashchange', syncRoute);
      window.removeEventListener('popstate', syncRoute);
    };
  }, []);

  return route === 'workbench' ? <WorkbenchPage /> : <WelcomePage />;
}
