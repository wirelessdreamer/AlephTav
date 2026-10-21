import { useLayoutEffect, useRef, useState, type CSSProperties } from 'react';

import type { HoveredWord } from '../components/WordContextCard';

const GAP = 8;

/** Measure the real card, keeping the word clear and long dictionary entries scrollable. */
export function useWordCardPosition<T extends HTMLElement>(word: HoveredWord) {
  const ref = useRef<T>(null);
  const [position, setPosition] = useState<{ top: number; left: number; maxHeight: number } | null>(null);
  useLayoutEffect(() => {
    const measure = () => {
      const card = ref.current;
      if (!card) return;
      const below = Math.max(0, window.innerHeight - word.bottom - GAP * 2);
      const above = Math.max(0, word.top - GAP * 2);
      const height = Math.min(card.scrollHeight + card.offsetHeight - card.clientHeight, window.innerHeight * 0.7);
      const useBelow = height <= below || below >= above;
      const maxHeight = Math.min(window.innerHeight * 0.7, useBelow ? below : above);
      const next = {
        top: useBelow ? word.bottom + GAP : word.top - GAP - Math.min(height, maxHeight),
        left: Math.max(GAP, Math.min(word.left, window.innerWidth - card.offsetWidth - GAP)),
        maxHeight,
      };
      setPosition(current => current?.top === next.top && current.left === next.left
        && current.maxHeight === next.maxHeight ? current : next);
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (ref.current) observer.observe(ref.current);
    window.addEventListener('resize', measure);
    return () => { observer.disconnect(); window.removeEventListener('resize', measure); };
  }, [word]);
  const style: CSSProperties = {
    top: position?.top ?? word.bottom + GAP,
    left: position?.left ?? word.left,
    maxHeight: position?.maxHeight,
    maxWidth: `calc(100vw - ${GAP * 2}px)`,
    visibility: position === null ? 'hidden' : undefined,
  };
  return { ref, style };
}
