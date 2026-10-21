import { useEffect, type RefObject } from 'react';

/** Pinned word studies stay open inside the card and dismiss on an outside click. */
export function useWordStudyDismissal(
  card: RefObject<HTMLElement>, pinned: boolean, onDismiss?: () => void,
) {
  useEffect(() => {
    if (!pinned || !onDismiss) return;
    const outside = (event: MouseEvent) => {
      if (event.target instanceof Node && !card.current?.contains(event.target)) onDismiss();
    };
    document.addEventListener('click', outside, true);
    return () => document.removeEventListener('click', outside, true);
  }, [card, pinned, onDismiss]);
}
