import { useEffect, useState } from 'react';

/** The phone layout boundary. The stylesheet switches on the same width. */
export const PHONE_QUERY = '(max-width: 720px)';

/** True while the viewport is phone-sized, following resizes and rotation. */
export function useIsPhone(): boolean {
  const [phone, setPhone] = useState(() => window.matchMedia(PHONE_QUERY).matches);

  useEffect(() => {
    const query = window.matchMedia(PHONE_QUERY);
    const sync = () => setPhone(query.matches);
    sync();
    query.addEventListener('change', sync);
    return () => query.removeEventListener('change', sync);
  }, []);

  return phone;
}
