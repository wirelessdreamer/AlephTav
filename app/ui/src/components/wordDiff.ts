export interface DiffPart {
  text: string;
  kind: 'same' | 'add' | 'remove';
}

/**
 * Word-level diff of two renderings (longest common subsequence). Whitespace,
 * including the line breaks a lyric depends on, travels with the word before it.
 */
export function diffWords(before: string, after: string): DiffPart[] {
  const a = before.match(/\S+\s*/g) ?? [];
  const b = after.match(/\S+\s*/g) ?? [];
  const key = (word: string) => word.trim();
  const lengths = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      lengths[i][j] =
        key(a[i]) === key(b[j])
          ? lengths[i + 1][j + 1] + 1
          : Math.max(lengths[i + 1][j], lengths[i][j + 1]);
    }
  }
  const parts: DiffPart[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (key(a[i]) === key(b[j])) {
      parts.push({ text: b[j], kind: 'same' });
      i += 1;
      j += 1;
    } else if (lengths[i + 1][j] >= lengths[i][j + 1]) {
      parts.push({ text: a[i], kind: 'remove' });
      i += 1;
    } else {
      parts.push({ text: b[j], kind: 'add' });
      j += 1;
    }
  }
  for (; i < a.length; i += 1) parts.push({ text: a[i], kind: 'remove' });
  for (; j < b.length; j += 1) parts.push({ text: b[j], kind: 'add' });
  return parts;
}
