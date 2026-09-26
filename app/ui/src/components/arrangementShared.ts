import type { LibertyKind, LineAnchor, LineLiberty, SectionKind } from '../types';

export const LINE_LIBERTIES: LineLiberty[] = ['tracks', 'compressed', 'expanded', 'reordered', 'added'];

export const SECTION_KINDS: SectionKind[] = [
  'verse',
  'chorus',
  'refrain',
  'bridge',
  'intro',
  'outro',
  'other',
];

export const LIBERTY_LABELS: Record<LibertyKind, string> = {
  tracks: 'Tracks',
  compressed: 'Compressed',
  expanded: 'Expanded',
  reordered: 'Reordered',
  added: 'Added',
  repeated: 'Repeated',
  dropped: 'Not carried',
};

export const LIBERTY_HINTS: Record<LibertyKind, string> = {
  tracks: 'Renders its Hebrew closely',
  compressed: 'Folds its Hebrew together or leaves part out',
  expanded: 'Adds to its Hebrew',
  reordered: 'Changes the order of its Hebrew',
  added: 'Not in the Hebrew there',
  repeated: 'A section sung again',
  dropped: 'Hebrew no line carries',
};

export const REVIEWER_ROLES = [
  'lexical reviewer',
  'Hebrew reviewer',
  'alignment reviewer',
  'lyric reviewer',
  'theology reviewer',
  'release reviewer',
];

/** 3 for 'ps001.v003.a'. */
export function verseOf(unitId: string): number {
  return Number(unitId.split('.')[1]?.replace('v', ''));
}

/** Where a line's Hebrew comes from, as verse numbers: '1', '1–2', '3, 5'. */
export function anchorRefs(anchors: LineAnchor[]): string {
  const verses = [...new Set(anchors.map((a) => verseOf(a.unit_id)))].sort((a, b) => a - b);
  if (verses.length === 0) return '';
  const runs: string[] = [];
  let start = verses[0];
  let previous = verses[0];
  for (const verse of [...verses.slice(1), Number.NaN]) {
    if (verse === previous + 1) {
      previous = verse;
      continue;
    }
    runs.push(start === previous ? String(start) : `${start}–${previous}`);
    start = verse;
    previous = verse;
  }
  return runs.join(', ');
}

/** English syllables, roughly: vowel groups, less a silent final e or -ed. A hint only. */
export function syllables(text: string): number {
  return (text.toLowerCase().match(/[a-z]+/g) ?? []).reduce((sum, word) => {
    if (word.length <= 3) return sum + 1;
    const trimmed = word.replace(/(?:[^laeiouytd]ed|[^laeiouy]es|[^laeiouy]e)$/, '').replace(/^y/, '');
    return sum + Math.max(1, trimmed.match(/[aeiouy]{1,2}/g)?.length ?? 1);
  }, 0);
}

export interface Reviewer {
  name: string;
  role: string;
}

const REVIEWER_KEY = 'alephtav.reviewer';

export function loadReviewer(): Reviewer {
  try {
    const saved = JSON.parse(window.localStorage.getItem(REVIEWER_KEY) ?? 'null') as Reviewer | null;
    if (saved && typeof saved.name === 'string' && REVIEWER_ROLES.includes(saved.role)) return saved;
  } catch {
    // A remembered convenience only.
  }
  return { name: '', role: 'lyric reviewer' };
}

export function saveReviewer(reviewer: Reviewer): void {
  try {
    window.localStorage.setItem(REVIEWER_KEY, JSON.stringify(reviewer));
  } catch {
    // A remembered convenience only.
  }
}
