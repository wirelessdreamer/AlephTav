/** Codex work an open verse can start. The table owns the session and the batch runner. */
export interface VerseCodex {
  ready: boolean;
  /** Why Codex actions are disabled, when they are. */
  hint?: string;
  /** Another Codex batch is running. */
  busy: boolean;
  rebuild: (options: { layers: Array<'literal' | 'english'>; reanalyse: boolean }) => void;
  analyseRebuild: () => void;
  suggest: (tokenIds: string[]) => Promise<void>;
}

/** Progress of a rebuild running for this verse. */
export interface RebuildProgress {
  step: number;
  total: number;
  label: string;
  elapsed: string;
  stopping: boolean;
  onStop: () => void;
}

/** A picked word choice is saved as an instruction note in this form. */
export function choiceNoteText(name: string, surface: string, choice: string): string {
  return `Render ${name} (${surface}) as “${choice}”.`;
}

/** The choice a pick note names, or the note as written when it is not a pick. */
export function pickedChoice(text: string): string {
  return text.match(/as “(.+?)”/)?.[1] ?? text;
}

/** Verse text split into runs, the word under discussion marked. */
export type ContextRun = { text: string; marked: boolean };

type Range = [number, number];

/** Curly and straight apostrophes are the same letter when looking a phrase up. */
function fold(text: string): string {
  return text.toLowerCase().replace(/[’‘]/g, "'");
}

function occurrences(text: string, part: string): number[] {
  const haystack = fold(text);
  const needle = fold(part);
  const found: number[] = [];
  for (let at = haystack.indexOf(needle); at >= 0; at = haystack.indexOf(needle, at + 1)) {
    found.push(at);
  }
  return found;
}

/**
 * Where ``phrase`` stands in ``text``. A phrase like "won't walk; won't stand" is
 * found part by part, in order. A phrase that occurs more than once is taken where
 * ``hint`` (the word's relative position in the Hebrew verse, 0 to 1) points.
 */
function findRanges(text: string, phrase: string, hint?: number): Range[] | null {
  const parts = phrase.split(/\s*;\s*/).filter(Boolean);
  if (parts.length > 1) {
    const ranges: Range[] = [];
    let from = 0;
    for (const part of parts) {
      const at = occurrences(text, part).find((index) => index >= from);
      if (at === undefined) return null;
      ranges.push([at, at + part.length]);
      from = at + part.length;
    }
    return ranges;
  }
  const found = occurrences(text, phrase);
  if (found.length === 0) return null;
  const target = (hint ?? 0) * text.length;
  const at = found.reduce((best, index) =>
    Math.abs(index - target) < Math.abs(best - target) ? index : best,
  );
  return [[at, at + phrase.length]];
}

/** The lines of ``text`` the ranges fall in, as runs with the ranges marked. */
function linesAround(text: string, ranges: Range[]): ContextRun[] {
  const lineStart = (index: number) => text.lastIndexOf('\n', index - 1) + 1;
  const lineEnd = (index: number) => {
    const next = text.indexOf('\n', index);
    return next < 0 ? text.length : next;
  };
  const runs: ContextRun[] = [];
  let cursor = -1;
  for (const [start, end] of ranges) {
    const from = lineStart(start);
    if (cursor < 0) cursor = from;
    else if (from > cursor) {
      // Carry on to the end of the line, then pick up at the next line with a mark.
      runs.push({ text: text.slice(cursor, lineEnd(cursor)), marked: false });
      runs.push({ text: ' / ', marked: false });
      cursor = from;
    }
    runs.push({ text: text.slice(cursor, start), marked: false });
    runs.push({ text: text.slice(start, end), marked: true });
    cursor = end;
  }
  if (cursor >= 0) runs.push({ text: text.slice(cursor, lineEnd(cursor)), marked: false });
  return runs
    .filter((run) => run.text)
    .map((run) => ({ ...run, text: run.text.replace(/\n/g, ' / ') }));
}

/** The line(s) of ``text`` that hold ``phrase``, with it marked; null when not there. */
export function phraseInContext(
  text: string | null | undefined,
  phrase: string | null | undefined,
  hint?: number,
): ContextRun[] | null {
  if (!text || !phrase) return null;
  const ranges = findRanges(text, phrase, hint);
  return ranges ? linesAround(text, ranges) : null;
}

/**
 * How a choice reads in its verse: the line Codex wrote for it, or else the current
 * text with the choice put where the current rendering stands.
 */
export function choiceInContext(
  choice: { text: string; line?: string },
  englishText: string | null | undefined,
  renderedAs: string | null | undefined,
  hint?: number,
): ContextRun[] | null {
  if (choice.line) {
    return phraseInContext(choice.line, choice.text) ?? [{ text: choice.line, marked: false }];
  }
  const swapped = substitute(choice, englishText, renderedAs, hint);
  return swapped ? linesAround(swapped.text, swapped.placed) : null;
}

/** A replacement for a capitalised phrase starts with a capital too: "Its leaves" → "Its foliage". */
function matchCapital(original: string, replacement: string): string {
  const first = original.charAt(0);
  return first === first.toLowerCase()
    ? replacement
    : replacement.charAt(0).toUpperCase() + replacement.slice(1);
}

/** The current text with the choice where the current rendering stands. */
function substitute(
  choice: { text: string; line?: string },
  englishText: string | null | undefined,
  renderedAs: string | null | undefined,
  hint?: number,
): { text: string; placed: Range[] } | null {
  if (!englishText || !renderedAs) return null;
  const ranges = findRanges(englishText, renderedAs, hint);
  if (!ranges) return null;
  if (choice.line) {
    // Codex rewrote the line(s) holding the word: put them in place of the old ones.
    const start = englishText.lastIndexOf('\n', ranges[0][0] - 1) + 1;
    const next = englishText.indexOf('\n', ranges[ranges.length - 1][1]);
    const end = next < 0 ? englishText.length : next;
    const inLine = findRanges(choice.line, choice.text) ?? [[0, choice.line.length]];
    return {
      text: englishText.slice(0, start) + choice.line + englishText.slice(end),
      placed: inLine.map(([from, to]): Range => [from + start, to + start]),
    };
  }
  const parts = choice.text.split(/\s*;\s*/).filter(Boolean);
  const replacements = parts.length === ranges.length ? parts : [choice.text];
  if (replacements.length !== ranges.length) return null;
  let text = '';
  let cursor = 0;
  const placed: Range[] = [];
  ranges.forEach(([start, end], index) => {
    text += englishText.slice(cursor, start);
    const replacement = matchCapital(englishText.slice(start, end), replacements[index]);
    placed.push([text.length, text.length + replacement.length]);
    text += replacement;
    cursor = end;
  });
  text += englishText.slice(cursor);
  return { text, placed };
}

/**
 * The whole verse as it would read with the choice, the choice marked and the
 * line breaks kept. Null when the current rendering cannot be found in the text.
 */
export function choiceInVerse(
  choice: { text: string; line?: string },
  englishText: string | null | undefined,
  renderedAs: string | null | undefined,
  hint?: number,
): ContextRun[] | null {
  const swapped = substitute(choice, englishText, renderedAs, hint);
  if (!swapped) return null;
  const runs: ContextRun[] = [];
  let cursor = 0;
  for (const [start, end] of swapped.placed) {
    runs.push({ text: swapped.text.slice(cursor, start), marked: false });
    runs.push({ text: swapped.text.slice(start, end), marked: true });
    cursor = end;
  }
  runs.push({ text: swapped.text.slice(cursor), marked: false });
  return runs.filter((run) => run.text);
}

/** Gloss words too common to point at one place in a line. */
const GLOSS_STOP_WORDS = new Set(
  'a an and the of in to for with by on at from is are be as this that these those it he she they we you i his her their its my your our them him me us who which o'.split(
    ' ',
  ),
);

/**
 * Whole words of ``text`` between ``from`` and ``to`` that share a content word with
 * ``gloss``, each taken where it stands nearest ``hint`` (0 to 1 along the text).
 */
function glossRanges(text: string, gloss: string, from: number, to: number, hint?: number): Range[] {
  const target = from + (hint ?? 0) * (to - from);
  const words = new Set(
    (fold(gloss).match(/[a-z']+/g) ?? []).filter((word) => !GLOSS_STOP_WORDS.has(word)),
  );
  const ranges: Range[] = [];
  for (const word of words) {
    const found: number[] = [];
    const pattern = new RegExp(`\\b${word}\\b`, 'g');
    const span = fold(text).slice(from, to);
    for (let match = pattern.exec(span); match; match = pattern.exec(span)) {
      found.push(from + match.index);
    }
    if (found.length === 0) continue;
    const at = found.reduce((best, index) =>
      Math.abs(index - target) < Math.abs(best - target) ? index : best,
    );
    ranges.push([at, at + word.length]);
  }
  return ranges.sort((a, b) => a[0] - b[0]);
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Where ``phrase`` stands in ``text``, as ``findRanges`` finds it, except that a space
 * in the phrase matches any run of spaces and line breaks: an aligned phrase can run
 * across the lines of a literal.
 */
function spansAcrossLines(text: string, phrase: string, hint?: number): Range[] | null {
  const haystack = fold(text);
  const matches = (part: string): Range[] => {
    const words = fold(part).trim().split(/\s+/).filter(Boolean);
    if (words.length === 0) return [];
    const pattern = new RegExp(words.map(escapeRegExp).join('\\s+'), 'g');
    return [...haystack.matchAll(pattern)].map((match): Range => [
      match.index ?? 0,
      (match.index ?? 0) + match[0].length,
    ]);
  };
  const parts = phrase.split(/\s*;\s*/).filter(Boolean);
  if (parts.length > 1) {
    const ranges: Range[] = [];
    let from = 0;
    for (const part of parts) {
      const next = matches(part).find(([start]) => start >= from);
      if (!next) return null;
      ranges.push(next);
      from = next[1];
    }
    return ranges;
  }
  const found = matches(phrase);
  if (found.length === 0) return null;
  const target = (hint ?? 0) * text.length;
  return [
    found.reduce((best, range) =>
      Math.abs(range[0] - target) < Math.abs(best[0] - target) ? range : best,
    ),
  ];
}

/**
 * The literal with a Hebrew word's rendering marked. ``link`` is the phrase Codex
 * aligned the word to: it is found first, then narrowed to the words in it that share
 * the word's gloss, or marked whole when none do. Without a link, the gloss's words
 * are looked for across the text. Null when nothing can be marked.
 */
export function literalMarks(
  text: string | null | undefined,
  link: { text: string; hint?: number; within?: number } | undefined,
  gloss: string | undefined,
  hint?: number,
): ContextRun[] | null {
  if (!text) return null;
  let ranges: Range[] = [];
  // "will … stand" is looked for part by part, as "will; stand" is.
  const phrase = link?.text
    .replace(/\s*(?:…|\.\.\.)\s*/g, '; ')
    .replace(/^[\s"“”'‘’(]+|[\s"“”'‘’).,;:!?]+$/g, '');
  // ``link.hint`` places the phrase in the verse; ``link.within`` the word in the phrase.
  const spans = phrase ? spansAcrossLines(text, phrase, link?.hint) : null;
  if (spans) {
    for (const [start, end] of spans) {
      const words = gloss ? glossRanges(text, gloss, start, end, link?.within) : [];
      ranges.push(...(words.length > 0 ? words : [[start, end] as Range]));
    }
  } else if (gloss) {
    ranges = glossRanges(text, gloss, 0, text.length, hint);
  }
  if (ranges.length === 0) return null;
  const runs: ContextRun[] = [];
  let cursor = 0;
  for (const [start, end] of ranges) {
    runs.push({ text: text.slice(cursor, start), marked: false });
    runs.push({ text: text.slice(start, end), marked: true });
    cursor = end;
  }
  runs.push({ text: text.slice(cursor), marked: false });
  return runs.filter((run) => run.text);
}

/** Where a word sits in its verse, 0 to 1, to pick between repeated phrases. */
export function positionHint(tokenIds: string[], allTokenIds: string[]): number | undefined {
  const at = allTokenIds.indexOf(tokenIds[0]);
  if (at < 0 || allTokenIds.length < 2) return undefined;
  return at / (allTokenIds.length - 1);
}

export function layerLabel(layer: string): string {
  const words = layer.replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function shortTime(iso: string | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
