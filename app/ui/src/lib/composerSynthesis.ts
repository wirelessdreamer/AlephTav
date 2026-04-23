import type { Token, Unit } from '../types';

export type ComposerLevel = 'word' | 'phrase' | 'idea' | 'lyric';

export interface ComposerSeedChoice {
  id: string;
  label: string;
  text: string;
  tokenStart: number;
  tokenEnd: number;
  tokenId?: string;
  description: string;
  confidence: number;
  confidenceReasons: string[];
}

export interface ComposerSuggestionChunk {
  chunk_id: string;
  start: number;
  end: number;
  text: string;
  source_text: string;
  confidence: number;
  confidence_reasons: string[];
}

export interface DeterministicComposerPlan {
  wordChoices: ComposerSeedChoice[];
  phraseChoices: ComposerSeedChoice[];
  ideaChoices: ComposerSeedChoice[];
  lyricChoices: ComposerSeedChoice[];
  phraseSuggestionChunks: ComposerSuggestionChunk[];
  ideaSuggestionChunks: ComposerSuggestionChunk[];
  lyricSuggestionChunks: ComposerSuggestionChunk[];
}

type CompilerFeatures = {
  conjunction_role?: string | null;
  preposition_role?: string | null;
  construct_state?: boolean;
  suffix_pronoun?: { text?: string | null; person?: string | null; number?: string | null; gender?: string | null } | null;
  divine_name?: boolean;
  temporal_pair_candidate?: boolean;
  discourse_marker?: string | null;
};

type CompilerChunk = {
  id: string;
  start: number;
  end: number;
  tokens: Token[];
  confidence: number;
  confidenceReasons: string[];
};

const TOKEN_WORD_RE = /[A-Za-z][A-Za-z'/-]*/g;

export function normalizeComposerText(text: string): string {
  return text
    .replace(/[._]/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .trim();
}

export function sentenceCase(text: string): string {
  if (!text) {
    return '';
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function inflateFeatures(token: Token): CompilerFeatures {
  return (token.compiler_features ?? {}) as CompilerFeatures;
}

function tokenMeaning(token: Token): string {
  const normalizedSense = normalizeComposerText(token.display_gloss ?? token.word_sense ?? token.transliteration ?? token.surface);
  const lowered = normalizedSense.toLowerCase();
  if (!normalizedSense) {
    return token.surface;
  }
  if (lowered === 'person') {
    return token.normalized.startsWith('ה') ? 'the man' : 'person';
  }
  if (lowered.startsWith('how blessed')) {
    return 'How blessed';
  }
  if (lowered === 'but') {
    return 'But';
  }
  if (lowered === 'rather') {
    return 'Rather';
  }
  return normalizedSense;
}

function words(text: string): string[] {
  return (text.match(TOKEN_WORD_RE) ?? []).map((item) => item.toLowerCase());
}

function displayConfidence(confidence: number, reasons: string[]): string {
  return `confidence ${confidence.toFixed(2)}${reasons.length ? ` · ${reasons.join(' · ')}` : ''}`;
}

function startsWithPronounVerb(text: string): string | null {
  const match = text.match(/^(he|she|it|they)\s+(.+)$/i);
  return match ? match[2] : null;
}

function joinChunkTexts(tokens: Token[]): string {
  const parts = tokens.map((token) => tokenMeaning(token)).filter(Boolean);
  if (parts.length === 0) {
    return '';
  }

  const features = tokens.map((token) => inflateFeatures(token));
  const containsVerb = tokens.some((token) => token.part_of_speech === 'verb');
  let trailingPossessiveIndex = -1;
  tokens.forEach((token, index) => {
    const feature = features[index];
    if (feature.suffix_pronoun?.text && token.part_of_speech === 'noun') {
      trailingPossessiveIndex = index;
    }
  });
  if (!containsVerb && trailingPossessiveIndex === tokens.length - 1 && tokens.length >= 3) {
    const leadParts = parts.filter((_, index) => index < trailingPossessiveIndex && features[index].conjunction_role !== 'contrastive');
    const conjunctionLead = parts.find((_, index) => features[index].conjunction_role === 'contrastive');
    const trailing = parts[trailingPossessiveIndex];
    const reordered = `${conjunctionLead ? `${conjunctionLead}, ` : ''}${trailing} is ${leadParts.join(' ')}`;
    return normalizeComposerText(reordered);
  }

  const rewrittenParts: string[] = [];
  for (let index = 0; index < parts.length; index += 1) {
    const current = parts[index];
    const next = parts[index + 1] ?? '';
    const nextVerb = startsWithPronounVerb(next);
    if ((current.toLowerCase() === 'not' || current.toLowerCase() === 'no') && nextVerb) {
      rewrittenParts.push(`does not ${nextVerb}`);
      index += 1;
      continue;
    }
    rewrittenParts.push(current);
  }

  return normalizeComposerText(rewrittenParts.join(' '))
    .replace(/\bwho not\b/gi, 'who does not')
    .replace(/\bthat not\b/gi, 'that does not')
    .replace(/\bthe man who does not\b/gi, 'the man who does not')
    .replace(/\bof Yahweh\b/g, 'of Yahweh')
    .replace(/\bday and night\b/gi, 'day and night');
}

function toPhraseText(chunk: CompilerChunk): string {
  return sentenceCase(joinChunkTexts(chunk.tokens));
}

function toConceptText(chunk: CompilerChunk): string {
  const phrase = toPhraseText(chunk)
    .replace(/\bBut rather,\s*/i, 'Instead, ')
    .replace(/\bBut rather\s+/i, 'Instead, ')
    .replace(/\blaw of Yahweh\b/g, "Yahweh's law")
    .replace(/\bthe man\b/gi, 'the one')
    .replace(/\bin his law he meditates\b/gi, 'he meditates on his law')
    .replace(/\bby day and night\b/gi, 'day and night');
  return sentenceCase(normalizeComposerText(phrase));
}

function toLyricText(chunk: CompilerChunk): string {
  const concept = toConceptText(chunk)
    .replace(/\bInstead,\s+his delight is in\b/gi, 'His delight is in')
    .replace(/\bBlessed is the one\b/gi, 'How blessed is the one')
    .replace(/\bhe meditates on\b/gi, 'he dwells on')
    .replace(/\bday and night\b/gi, 'by day and night');
  return sentenceCase(normalizeComposerText(concept));
}

function buildConfidence(tokens: Token[]): { confidence: number; reasons: string[] } {
  let confidence = 0.62;
  const reasons: string[] = ['lexical compiler'];
  if (tokens.some((token) => Boolean(token.display_gloss))) {
    confidence += 0.08;
    reasons.push('normalized gloss');
  }
  if (tokens.some((token) => inflateFeatures(token).construct_state)) {
    confidence += 0.05;
    reasons.push('construct merged');
  }
  if (tokens.some((token) => Boolean(inflateFeatures(token).suffix_pronoun?.text))) {
    confidence += 0.05;
    reasons.push('suffix resolved');
  }
  if (tokens.some((token) => inflateFeatures(token).divine_name)) {
    confidence += 0.03;
    reasons.push('divine-name preserved');
  }
  if (tokens.some((token) => inflateFeatures(token).discourse_marker === 'parenthetical_only_gloss')) {
    confidence -= 0.08;
    reasons.push('discourse gloss normalized');
  }
  if (tokens.length >= 6) {
    confidence -= 0.05;
    reasons.push('wide chunk');
  }
  return {
    confidence: Math.max(0.35, Math.min(0.95, confidence)),
    reasons,
  };
}

function shouldBreakBefore(tokens: Token[], index: number, currentStart: number): boolean {
  const currentLength = index - currentStart;
  const token = tokens[index];
  const previous = tokens[index - 1];
  const currentFeatures = inflateFeatures(token);
  const previousFeatures = inflateFeatures(previous);
  const currentText = tokenMeaning(token).toLowerCase();

  if (previousFeatures.construct_state || currentText.startsWith('of ')) {
    return false;
  }
  if (previousFeatures.temporal_pair_candidate && currentFeatures.temporal_pair_candidate) {
    return false;
  }
  if (currentFeatures.conjunction_role === 'additive' && currentLength >= 3) {
    return true;
  }
  if (currentFeatures.preposition_role && currentLength >= 4) {
    return true;
  }
  if (currentLength >= 5) {
    return true;
  }
  return false;
}

function buildChunks(unit: Unit): CompilerChunk[] {
  if (unit.tokens.length === 0) {
    return [];
  }
  const ranges: Array<{ start: number; end: number }> = [];
  let currentStart = 0;
  for (let index = 1; index < unit.tokens.length; index += 1) {
    if (shouldBreakBefore(unit.tokens, index, currentStart)) {
      ranges.push({ start: currentStart, end: index - 1 });
      currentStart = index;
    }
  }
  ranges.push({ start: currentStart, end: unit.tokens.length - 1 });

  if (ranges.length >= 2) {
    for (let index = 0; index < ranges.length - 1; index += 1) {
      const current = ranges[index];
      const next = ranges[index + 1];
      if (current.end - current.start <= 0) {
        current.end = next.end;
        ranges.splice(index + 1, 1);
        index -= 1;
      }
    }
  }

  return ranges.map((range, index) => {
    const tokens = unit.tokens.slice(range.start, range.end + 1);
    const confidence = buildConfidence(tokens);
    return {
      id: `compiler-${unit.unit_id}-${index + 1}`,
      start: range.start,
      end: range.end,
      tokens,
      confidence: confidence.confidence,
      confidenceReasons: confidence.reasons,
    };
  });
}

function buildChoice(level: ComposerLevel, chunk: CompilerChunk, text: string, description: string): ComposerSeedChoice {
  return {
    id: `${level}-${chunk.id}`,
    label: text,
    text,
    tokenStart: chunk.start,
    tokenEnd: chunk.end,
    description,
    confidence: chunk.confidence,
    confidenceReasons: chunk.confidenceReasons,
  };
}

function buildSuggestionChunk(chunk: CompilerChunk, text: string): ComposerSuggestionChunk {
  return {
    chunk_id: chunk.id,
    start: chunk.start,
    end: chunk.end,
    text,
    source_text: chunk.tokens.map((token) => token.surface).join(' '),
    confidence: chunk.confidence,
    confidence_reasons: chunk.confidenceReasons,
  };
}

export function buildDeterministicComposer(unit: Unit): DeterministicComposerPlan {
  const wordChoices = unit.tokens.map((token, index) => {
    const confidence = buildConfidence([token]);
    const label = sentenceCase(tokenMeaning(token));
    return {
      id: `word-${token.token_id}`,
      label,
      text: tokenMeaning(token),
      tokenStart: index,
      tokenEnd: index,
      tokenId: token.token_id,
      description: displayConfidence(confidence.confidence, confidence.reasons),
      confidence: confidence.confidence,
      confidenceReasons: confidence.reasons,
    };
  });

  const chunks = buildChunks(unit);
  const phraseChoices = chunks.map((chunk) => {
    const text = toPhraseText(chunk);
    return buildChoice('phrase', chunk, text, displayConfidence(chunk.confidence, chunk.confidenceReasons));
  });
  const ideaChoices = chunks.map((chunk) => {
    const text = toConceptText(chunk);
    return buildChoice('idea', chunk, text, displayConfidence(chunk.confidence, chunk.confidenceReasons));
  });
  const lyricChoices = chunks.map((chunk) => {
    const text = toLyricText(chunk);
    return buildChoice('lyric', chunk, text, displayConfidence(chunk.confidence, chunk.confidenceReasons));
  });

  return {
    wordChoices,
    phraseChoices,
    ideaChoices,
    lyricChoices,
    phraseSuggestionChunks: chunks.map((chunk) => buildSuggestionChunk(chunk, toPhraseText(chunk))),
    ideaSuggestionChunks: chunks.map((chunk) => buildSuggestionChunk(chunk, toConceptText(chunk))),
    lyricSuggestionChunks: chunks.map((chunk) => buildSuggestionChunk(chunk, toLyricText(chunk))),
  };
}
