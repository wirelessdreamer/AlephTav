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
  english_parts?: string[] | null;
  gloss_fragments?: string[] | null;
  raw_classes?: string[] | null;
  raw_pos?: string[] | null;
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
const HEBREW_RE = /[\u0590-\u05FF]/;
const CONJUNCTION_PREFIXES = new Set(['and', 'or', 'but']);
const POSSESSIVE_WORDS = new Set(['my', 'your', 'his', 'her', 'its', 'our', 'their']);
const SUBJECT_PRONOUNS = new Set(['i', 'you', 'he', 'she', 'it', 'we', 'they']);
const OBJECT_PRONOUNS = new Set(['me', 'him', 'her', 'us', 'them', 'whom']);
const ARTICLES = new Set(['the', 'a', 'an']);
const PREPOSITIONS = new Set(['in', 'on', 'by', 'with', 'from', 'to', 'of', 'for', 'at', 'under', 'over']);
const LOCATIVE_PREPOSITION_ROLES = new Set(['in', 'on', 'at', 'by', 'with', 'under', 'over', 'beside']);
const SUPERSCRIPTION_KEYWORD_RE = /\b(choirmaster|chief musician|director|psalm|song|prayer|maskil|miktam|shiggaion|david|asaph|jeduthun|korah|solomon|moses|nathan|prophet|bathsheba|doe|morning|lilies|gittith|sheminith|alamoth|ascents|degrees|flutes?|instruments?|lyre)\b/i;
const SPOKEN_CUE_RE = /^(yahweh|o god|my god|why|how blessed|blessed|not)\b/i;
const NEGATIVE_CHAIN_RE = /^(?:nor|not|and not|or not)\s+(.+)$/i;
const INHERITED_NEGATION_RE = /\b(?:who\s+)?(does not|doesn't|do not|don't|will not|won't|shall not|cannot|can't)\b/i;

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

function modernizeBeatitudeLead(text: string): string {
  return normalizeComposerText(text)
    .replace(/^How blessed is the man\b/i, 'Blessed is the one')
    .replace(/^Blessed is the man\b/i, 'Blessed is the one')
    .replace(/^How blessed is the one\b/i, 'Blessed is the one');
}

function contractNegativeEnglish(text: string): string {
  return normalizeComposerText(text)
    .replace(/\bdoes not\b/gi, "doesn't")
    .replace(/\bdo not\b/gi, "don't")
    .replace(/\bwill not\b/gi, "won't")
    .replace(/\bcannot\b/gi, "can't");
}

function inheritedNegativeAuxiliary(previousText: string, level: ComposerLevel): string {
  const inherited = normalizeComposerText(previousText).match(INHERITED_NEGATION_RE)?.[1];
  if (inherited) {
    return inherited;
  }
  return level === 'phrase' ? 'does not' : "doesn't";
}

function rewriteContinuingNegative(text: string, previousText: string, level: ComposerLevel): string {
  const normalized = normalizeComposerText(text);
  const match = normalized.match(NEGATIVE_CHAIN_RE);
  if (!match) {
    return normalized;
  }
  const remainder = normalizeComposerText(match[1]);
  if (!remainder) {
    return normalized;
  }
  const auxiliary = inheritedNegativeAuxiliary(previousText, level);
  const connector = previousText ? 'and' : '';
  return normalizeComposerText([connector, auxiliary, remainder].filter(Boolean).join(' '));
}

function modernizeChoiceText(level: ComposerLevel, text: string, previousText: string): string {
  let normalized = modernizeBeatitudeLead(text);
  normalized = rewriteContinuingNegative(normalized, previousText, level);
  if (level !== 'phrase') {
    normalized = contractNegativeEnglish(normalized);
  }
  return sentenceCase(normalized);
}

function finalizeChoiceSequence(level: ComposerLevel, choices: ComposerSeedChoice[]): ComposerSeedChoice[] {
  return choices.reduce<ComposerSeedChoice[]>((finalized, choice) => {
    const previousText = finalized[finalized.length - 1]?.text ?? '';
    const text = modernizeChoiceText(level, choice.text, previousText);
    finalized.push({
      ...choice,
      text,
      label: text,
    });
    return finalized;
  }, []);
}

function inflateFeatures(token: Token): CompilerFeatures {
  return (token.compiler_features ?? {}) as CompilerFeatures;
}

function featureParts(token: Token): string[] {
  const parts = inflateFeatures(token).english_parts;
  return Array.isArray(parts) ? parts.filter((item): item is string => Boolean(item?.trim())).map((item) => normalizeComposerText(item)) : [];
}

function glossFragments(token: Token): string[] {
  const fragments = inflateFeatures(token).gloss_fragments;
  return Array.isArray(fragments)
    ? fragments.filter((item): item is string => Boolean(item?.trim())).map((item) => normalizeComposerText(item))
    : [];
}

function rawClasses(token: Token): string[] {
  const classes = inflateFeatures(token).raw_classes;
  return Array.isArray(classes) ? classes.filter((item): item is string => Boolean(item?.trim())).map((item) => item.toLowerCase()) : [];
}

function rawPos(token: Token): string[] {
  const positions = inflateFeatures(token).raw_pos;
  return Array.isArray(positions) ? positions.filter((item): item is string => Boolean(item?.trim())).map((item) => item.toLowerCase()) : [];
}

function startsWithConjunction(text: string): boolean {
  return CONJUNCTION_PREFIXES.has(normalizeComposerText(text).split(' ')[0]?.toLowerCase() ?? '');
}

function dedupeAdjacentWords(text: string): string {
  return normalizeComposerText(text).replace(
    /\b(i|you|he|she|it|we|they|me|him|her|us|them|my|your|his|its|our|their)\s+\1\b/gi,
    '$1',
  );
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function reorderPossessiveParts(parts: string[]): string[] {
  if (parts.length < 2) {
    return parts;
  }
  const lastPart = parts[parts.length - 1] ?? '';
  const last = lastPart.toLowerCase();
  if (!POSSESSIVE_WORDS.has(last)) {
    return parts;
  }
  const stem = parts.slice(0, -1);
  if (stem.length > 1 && CONJUNCTION_PREFIXES.has(stem[0].toLowerCase()) && PREPOSITIONS.has(stem[1].toLowerCase())) {
    return [stem[0], stem[1], lastPart, ...stem.slice(2)];
  }
  if (stem.length > 0 && PREPOSITIONS.has(stem[0].toLowerCase())) {
    return [stem[0], lastPart, ...stem.slice(1)];
  }
  return [lastPart, ...stem];
}

function reorderArticleTail(parts: string[]): string[] {
  if (parts.length >= 2 && ARTICLES.has(parts[parts.length - 1]?.toLowerCase() ?? '')) {
    const tail = parts[parts.length - 1];
    return [tail, ...parts.slice(0, -1)];
  }
  return parts;
}

function cleanTokenCandidate(text: string): string {
  return dedupeAdjacentWords(
    normalizeComposerText(text)
      .replace(/\[(.*?)\]/g, '$1')
      .replace(/^(am|are|is|was)\s+(?=(in|on|to|from|with|for|of|upon|under|over|out of|according to)\b)/i, '')
      .replace(/\b(the|a|an)\s+\1\b/gi, '$1')
      .replace(/\b(of|in|on|to|from|with|for)\s+\1\b/gi, '$1'),
  );
}

function buildTokenCandidates(token: Token): string[] {
  const parts = featureParts(token);
  const reorderedParts = reorderArticleTail(reorderPossessiveParts(parts));
  const fragments = glossFragments(token);
  const normalizedSense = cleanTokenCandidate(token.display_gloss ?? token.word_sense ?? token.transliteration ?? token.normalized);
  const joinedParts = cleanTokenCandidate(parts.join(' '));
  const joinedReorderedParts = cleanTokenCandidate(reorderedParts.join(' '));
  const joinedFragments = cleanTokenCandidate(fragments.join(' '));
  const individualFragments = fragments.map((fragment) => cleanTokenCandidate(fragment));
  const candidates = new Set<string>();

  if (normalizedSense) {
    candidates.add(normalizedSense);
  }
  if (joinedParts) {
    candidates.add(joinedParts);
  }
  if (joinedReorderedParts) {
    candidates.add(joinedReorderedParts);
  }
  if (joinedFragments) {
    candidates.add(joinedFragments);
  }
  for (const fragment of individualFragments) {
    if (fragment) {
      candidates.add(fragment);
    }
  }

  if (token.part_of_speech === 'verb' && SUBJECT_PRONOUNS.has(individualFragments[0]?.toLowerCase() ?? '') && individualFragments[1]) {
    candidates.add(cleanTokenCandidate(`${individualFragments[0]} ${individualFragments.slice(1).join(' ')}`));
  }
  const fragmentWords = normalizeComposerText(joinedFragments).split(' ').filter(Boolean);
  const trailingFragmentWord = fragmentWords[fragmentWords.length - 1]?.toLowerCase() ?? '';
  if (token.part_of_speech === 'verb' && SUBJECT_PRONOUNS.has(trailingFragmentWord)) {
    const reorderedWords = [...fragmentWords];
    const subject = reorderedWords.pop();
    if (subject) {
      candidates.add(cleanTokenCandidate(`${subject} ${reorderedWords.join(' ')}`));
    }
  }
  if (inflateFeatures(token).suffix_pronoun?.text) {
    const pronoun = inflateFeatures(token).suffix_pronoun?.text?.toLowerCase();
    const longerFragment = individualFragments.find(
      (fragment) => words(fragment).length >= 2 && (!pronoun || new RegExp(`\\b${escapeRegExp(pronoun)}\\b`, 'i').test(fragment)),
    );
    if (longerFragment) {
      candidates.add(longerFragment);
    }
  }
  return [...candidates].filter(Boolean);
}

function scoreTokenCandidate(token: Token, text: string): number {
  const lowered = normalizeComposerText(text).toLowerCase();
  const features = inflateFeatures(token);
  let score = 0;

  if (!lowered) {
    return Number.NEGATIVE_INFINITY;
  }
  if (HEBREW_RE.test(text)) {
    score -= 80;
  }
  if (/\((dm|if)\)/i.test(lowered)) {
    score -= 60;
  }
  if (/\b(i|you|he|she|it|we|they|me|him|her|us|them|my|your|his|its|our|their)\s+\1\b/i.test(lowered)) {
    score -= 40;
  }
  if (/\b(am|are|is|was)\b$/.test(lowered)) {
    score -= 24;
  }
  if (/^(am|are|is|was)\s+(?!i\b|you\b|he\b|she\b|it\b|we\b|they\b)/.test(lowered)) {
    score -= 10;
  }
  if (/\b(the|a|an|and|or|but|of|to|in|on|with|from|for)\b$/.test(lowered)) {
    score -= 16;
  }
  if (/\b[a-z][a-z'/-]*\s+(the|a|an)\b$/.test(lowered) && !lowered.startsWith('to the ')) {
    score -= 12;
  }
  if (/^(am|are|is|was)\s/.test(lowered) && token.part_of_speech !== 'verb') {
    score -= 10;
  }
  if (/\bthe\b/.test(lowered)) {
    score += 3;
  }
  if (/\bcounsel\b/.test(lowered)) {
    score += 4;
  }

  score += Math.min(words(text).length, 4);
  if (token.part_of_speech === 'verb') {
    if (/^(i|you|he|she|it|we|they)\b/.test(lowered)) {
      score += 12;
    }
    if (/\b(i|you|he|she|it|we|they)\b$/.test(lowered)) {
      score -= 12;
    }
  }
  if ((token.part_of_speech === 'noun' || token.part_of_speech === 'adjective') && /^(my|your|his|her|its|our|their)\b/.test(lowered)) {
    score += 10;
  }
  if (features.preposition_role && /^(as for|according to|out of|in return for|belongs to|in|on|by|with|from|to|of|for|at|under|over|upon|toward|towards)\b/.test(lowered)) {
    score += 8;
  }
  if (features.conjunction_role === 'additive' && lowered.startsWith('and ')) {
    score += 6;
  }
  if (features.conjunction_role === 'contrastive' && /^(but|instead)\b/.test(lowered)) {
    score += 6;
  }
  if (features.divine_name && /\b(yahweh|lord)\b/i.test(text)) {
    score += 6;
  }
  if (features.suffix_pronoun?.text) {
    const pronoun = features.suffix_pronoun.text.toLowerCase();
    const occurrences = (lowered.match(new RegExp(`\\b${escapeRegExp(pronoun)}\\b`, 'g')) ?? []).length;
    if (occurrences === 1) {
      score += 6;
    }
    if (occurrences > 1) {
      score -= 18;
    }
  }
  return score;
}

function tokenGlossText(token: Token, { preserveLeadingConjunction = true }: { preserveLeadingConjunction?: boolean } = {}): string {
  const features = inflateFeatures(token);
  const parts = featureParts(token);
  const joinedFragments = cleanTokenCandidate(glossFragments(token).join(' '));
  if (
    features.preposition_role
    && features.suffix_pronoun?.text
    && !isVerbToken(token)
    && joinedFragments
    && (
      parts.length <= 2
      || /inner|inside|midst|within/i.test(joinedFragments)
    )
  ) {
    return joinedFragments;
  }
  if (
    features.suffix_pronoun?.text
    && parts.length >= 3
    && PREPOSITIONS.has(parts[0]?.toLowerCase() ?? '')
    && OBJECT_PRONOUNS.has(parts[parts.length - 1]?.toLowerCase() ?? '')
  ) {
    return cleanTokenCandidate(parts.join(' '));
  }
  if (
    features.suffix_pronoun?.text
    && parts.length >= 2
    && !isVerbToken(token)
    && !PREPOSITIONS.has(parts[0]?.toLowerCase() ?? '')
    && !CONJUNCTION_PREFIXES.has(parts[0]?.toLowerCase() ?? '')
  ) {
    return cleanTokenCandidate(reorderPossessiveParts(parts).join(' ').replace(/\b([A-Za-z][A-Za-z'’-]*)['’]s\b/gi, '$1'));
  }
  const candidates = buildTokenCandidates(token);
  let candidate = candidates
    .sort((left, right) => scoreTokenCandidate(token, right) - scoreTokenCandidate(token, left))[0]
    ?? cleanTokenCandidate(token.display_gloss ?? token.word_sense ?? token.transliteration ?? token.normalized);

  if (features.discourse_marker === 'parenthetical_only_gloss' && featureParts(token).length > 0) {
    candidate = cleanTokenCandidate(featureParts(token).join(' '));
  }
  if (/^(person the|the person)$/i.test(candidate) && featureParts(token).length >= 2) {
    candidate = cleanTokenCandidate(featureParts(token).join(' '));
  }
  if (features.divine_name && /^lord$/i.test(candidate) && glossFragments(token).some((fragment) => /\byahweh\b/i.test(fragment))) {
    candidate = cleanTokenCandidate(glossFragments(token).find((fragment) => /\byahweh\b/i.test(fragment)) ?? candidate);
  }
  if (HEBREW_RE.test(candidate)) {
    candidate = cleanTokenCandidate(token.transliteration ?? token.normalized);
  }
  if (!preserveLeadingConjunction && startsWithConjunction(candidate)) {
    candidate = cleanTokenCandidate(candidate.replace(/^(and|or|but)\s+/i, ''));
  }
  return candidate;
}

function tokenMeaning(token: Token): string {
  const normalizedSense = tokenGlossText(token);
  const lowered = normalizedSense.toLowerCase();
  const parts = featureParts(token);
  const joinedFragments = cleanTokenCandidate(glossFragments(token).join(' '));
  if (!normalizedSense) {
    return token.transliteration ?? token.normalized;
  }
  if (
    inflateFeatures(token).suffix_pronoun?.text
    && parts.length >= 2
    && !PREPOSITIONS.has(parts[0]?.toLowerCase() ?? '')
    && !CONJUNCTION_PREFIXES.has(parts[0]?.toLowerCase() ?? '')
  ) {
    return normalizeComposerText(reorderPossessiveParts(parts).join(' '))
      .replace(/\b([A-Za-z][A-Za-z'’-]*)['’]s\b/gi, '$1')
      .replace(/lord\(s\)/i, 'Lord');
  }
  if (parts[0]?.toLowerCase() === 'the' && parts[1]?.toLowerCase() === 'man') {
    return 'the man';
  }
  if (lowered === 'person' || lowered === 'person the' || lowered === 'the person') {
    if (parts[0]?.toLowerCase() === 'the' && parts[1]?.toLowerCase() === 'man') {
      return 'the man';
    }
    return token.normalized.startsWith('ה') ? 'the man' : 'person';
  }
  if (/person/.test(lowered) && parts[0]?.toLowerCase() === 'the' && parts[1]?.toLowerCase() === 'man') {
    return 'the man';
  }
  const possessiveAuxiliary = normalizedSense.match(/^(am|are|is|was)\s+(my|your|his|her|its|our|their)\s+(.+)$/i);
  if (possessiveAuxiliary) {
    return normalizeComposerText(`${possessiveAuxiliary[2]} ${possessiveAuxiliary[3]}`);
  }
  if (/\badvice\b/.test(lowered) && /\bcounsel\b/.test(joinedFragments)) {
    return joinedFragments;
  }
  if ((/\bin law\b/.test(lowered) || /\bin way\b/.test(lowered) || /\bin seat\b/.test(lowered)) && /\bthe\b/.test(joinedFragments)) {
    return joinedFragments;
  }
  if (lowered === 'how!') {
    return 'How';
  }
  if (/lord\(s\)/i.test(normalizedSense)) {
    return normalizeComposerText(normalizedSense.replace(/lord\(s\)/i, 'Lord'));
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

function startsWithPronounVerb(text: string): { subject: string; remainder: string } | null {
  const match = text.match(/^(i|you|he|she|it|we|they)\s+(.+)$/i);
  return match ? { subject: match[1], remainder: match[2] } : null;
}

function isRelativeToken(token: Token): boolean {
  return rawClasses(token).includes('rel') || tokenMeaning(token).toLowerCase() === 'who';
}

function isNegationToken(token: Token): boolean {
  const lowered = tokenGlossText(token, { preserveLeadingConjunction: true }).toLowerCase();
  return lowered === 'not' || lowered === 'nor' || lowered === 'no';
}

function negationWord(token: Token): string {
  return featureParts(token).some((item) => item.toLowerCase() === 'nor') ? 'nor' : 'not';
}

function isVerbToken(token: Token): boolean {
  return token.part_of_speech === 'verb' || rawPos(token).includes('verb') || rawClasses(token).includes('verb');
}

function isPronounToken(token: Token): boolean {
  return token.part_of_speech === 'pronoun' || rawPos(token).includes('pronoun') || rawPos(token).includes('suffix') || rawClasses(token).includes('pron');
}

function isDivineNameToken(token: Token): boolean {
  return Boolean(inflateFeatures(token).divine_name);
}

function baseVerbText(token: Token): string {
  const parts = featureParts(token);
  const preferred = parts.find((item) => !/^(he|she|it|they)$/i.test(item));
  const candidate = normalizeComposerText(preferred ?? tokenMeaning(token)).replace(/^(he|she|it|they)\s+/i, '');
  return candidate || normalizeComposerText(token.surface);
}

function finiteVerbText(token: Token): string {
  const literal = tokenGlossText(token);
  const stripped = startsWithPronounVerb(literal);
  return normalizeComposerText(stripped ? `${stripped.subject} ${stripped.remainder}` : literal)
    .replace(/^(am|are|is|was)\s+/i, '')
    .toLowerCase();
}

function verseNumber(unit: Unit): number {
  const match = unit.unit_id.match(/\.v(\d+)\./);
  return match ? Number(match[1]) : 0;
}

function isPrepositionalLead(token: Token): boolean {
  const features = inflateFeatures(token);
  return Boolean(features.preposition_role) && Boolean(tokenGlossText(token, { preserveLeadingConjunction: false }));
}

function isSelahToken(token: Token): boolean {
  return /^selah$/i.test(tokenMeaning(token));
}

function isExclamationToken(token: Token): boolean {
  return /^(how|why)!?$/i.test(tokenMeaning(token));
}

function isVocativeLikeToken(token: Token): boolean {
  return /^o\s+/i.test(tokenMeaning(token)) || isDivineNameToken(token);
}

function isComplementToken(token: Token): boolean {
  return !isRelativeToken(token) && !isNegationToken(token) && !isVerbToken(token) && !isPrepositionalLead(token);
}

function prepositionalPhraseText(token: Token, { includeConjunction = false }: { includeConjunction?: boolean } = {}): string {
  return tokenGlossText(token, { preserveLeadingConjunction: includeConjunction });
}

function complementText(token: Token): string {
  const text = tokenGlossText(token, { preserveLeadingConjunction: false });
  if (/^of wicked people$/i.test(text)) {
    return 'of the wicked';
  }
  if (/^the majestic ones$/i.test(text)) {
    return 'the noble ones';
  }
  return text;
}

function temporalPairText(tokens: Token[], startIndex: number): { text: string; consumed: number } | null {
  const current = tokens[startIndex];
  const next = tokens[startIndex + 1];
  if (!inflateFeatures(current).temporal_pair_candidate || !next || !inflateFeatures(next).temporal_pair_candidate) {
    return null;
  }
  const currentText = tokenGlossText(current, { preserveLeadingConjunction: false }).replace(/^by\s+/i, '').toLowerCase();
  const nextText = tokenGlossText(next, { preserveLeadingConjunction: false }).replace(/^and\s+/i, '').toLowerCase();
  return { text: `day and night`.replace('day', currentText).replace('night', nextText), consumed: 2 };
}

function renderPpGroup(tokens: Token[]): string {
  if (tokens.length === 0) {
    return '';
  }
  const [head, ...tail] = tokens;
  return normalizeComposerText([prepositionalPhraseText(head), renderComplementSequence(tail)].filter(Boolean).join(' '));
}

function renderComplementSequence(tokens: Token[]): string {
  const phrases: string[] = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (!token) {
      continue;
    }
    const current = complementText(token);
    const next = tokens[index + 1];
    if (inflateFeatures(token).construct_state && next && isComplementToken(next)) {
      const nextText = complementText(next);
      if (nextText) {
        phrases.push(nextText.startsWith('of ') ? `${current} ${nextText}` : `${current} of ${nextText}`);
        index += 1;
        continue;
      }
    }
    if (current) {
      phrases.push(current);
    }
  }
  return normalizeComposerText(phrases.join(' '));
}

function renderTail(tokens: Token[]): string {
  const phrases: string[] = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const temporal = temporalPairText(tokens, index);
    if (temporal) {
      phrases.push(temporal.text);
      index += temporal.consumed - 1;
      continue;
    }
    if (isPrepositionalLead(tokens[index])) {
      const group = [tokens[index]];
      while (tokens[index + 1] && isComplementToken(tokens[index + 1]) && !inflateFeatures(tokens[index + 1]).temporal_pair_candidate) {
        group.push(tokens[index + 1]);
        index += 1;
      }
      phrases.push(renderPpGroup(group));
      continue;
    }
    if (isComplementToken(tokens[index])) {
      const group = [tokens[index]];
      while (tokens[index + 1] && isComplementToken(tokens[index + 1]) && !isPrepositionalLead(tokens[index + 1]) && !inflateFeatures(tokens[index + 1]).temporal_pair_candidate) {
        group.push(tokens[index + 1]);
        index += 1;
      }
      phrases.push(renderComplementSequence(group));
      continue;
    }
    if (isNegationToken(tokens[index]) && tokens[index + 1] && isVerbToken(tokens[index + 1])) {
      phrases.push(`${negationWord(tokens[index])} ${baseVerbText(tokens[index + 1])}`);
      index += 1;
      continue;
    }
    if (isVerbToken(tokens[index])) {
      phrases.push(finiteVerbText(tokens[index]));
      continue;
    }
  }
  return normalizeComposerText(phrases.join(' '));
}

function renderImperativeVocativeChunk(tokens: Token[]): string | null {
  if (!tokens[0] || !isVerbToken(tokens[0]) || tokens.length < 2) {
    return null;
  }
  const vocative = tokens.find((token, index) => index > 0 && /^o\s+/i.test(glossFragments(token)[0] ?? tokenMeaning(token)));
  if (!vocative) {
    return null;
  }
  const others = tokens.filter((token) => token !== vocative);
  const object = renderTail(others.slice(1));
  if (!object) {
    return null;
  }
  const address = complementText(vocative);
  return normalizeComposerText(`${baseVerbText(tokens[0])} ${object}, ${address}`);
}

function renderBeatitudeChunk(tokens: Token[]): string | null {
  if (tokens.length < 2 || !tokenMeaning(tokens[0]).toLowerCase().startsWith('how blessed')) {
    return null;
  }
  const subject = tokenMeaning(tokens[1]).toLowerCase();
  if (!subject) {
    return null;
  }
  return normalizeComposerText(`how blessed is ${subject}`);
}

function renderRelativeChunk(tokens: Token[]): string | null {
  if (!tokens[0] || !isRelativeToken(tokens[0])) {
    return null;
  }
  let index = 1;
  const parts = ['who'];
  if (tokens[index] && isNegationToken(tokens[index]) && tokens[index + 1] && isVerbToken(tokens[index + 1])) {
    parts.push('does not', baseVerbText(tokens[index + 1]));
    index += 2;
  } else if (tokens[index] && isVerbToken(tokens[index])) {
    parts.push(baseVerbText(tokens[index]));
    index += 1;
  }
  const tail = renderTail(tokens.slice(index));
  if (tail) {
    parts.push(tail);
  }
  return normalizeComposerText(parts.join(' '));
}

function renderContrastiveChunk(tokens: Token[]): string | null {
  if (!tokens[0] || inflateFeatures(tokens[0]).conjunction_role !== 'contrastive') {
    return null;
  }
  let index = 1;
  while (tokens[index] && inflateFeatures(tokens[index]).conjunction_role === 'contrastive') {
    index += 1;
  }
  const subject = tokens.slice(index).find((token) => Boolean(inflateFeatures(token).suffix_pronoun?.text));
  if (!subject) {
    return null;
  }
  const tailTokens = tokens.slice(index).filter((token) => token !== subject);
  const subjectText = tokenGlossText(subject).toLowerCase();
  const tail = renderTail(tailTokens);
  if (!tail) {
    return normalizeComposerText(`instead, ${subjectText}`);
  }
  return normalizeComposerText(`instead, ${subjectText} is ${tail}`);
}

function renderNegatedSubjectVerbChunk(tokens: Token[]): string | null {
  if (!tokens[0]) {
    return null;
  }
  let index = 0;
  const lead: string[] = [];
  if (!isVerbToken(tokens[0]) && !isNegationToken(tokens[0]) && !isRelativeToken(tokens[0])) {
    lead.push(tokenMeaning(tokens[0]).toLowerCase());
    index += 1;
  }
  if (!tokens[index] || !isNegationToken(tokens[index]) || !tokens[index + 1] || !isVerbToken(tokens[index + 1])) {
    return null;
  }
  const verb = tokenGlossText(tokens[index + 1]);
  const tail = renderTail(tokens.slice(index + 2));
  return normalizeComposerText(`${lead.join(' ')} ${tokenMeaning(tokens[index]).toLowerCase()} ${verb}${tail ? ` ${tail}` : ''}`);
}

function renderBelongsToChunk(tokens: Token[]): string | null {
  if (!tokens[0]) {
    return null;
  }
  const head = tokenGlossText(tokens[0]);
  if (!/^belongs to /i.test(head)) {
    return null;
  }
  const owner = cleanTokenCandidate(head.replace(/^belongs to /i, ''));
  const tail = renderTail(tokens.slice(1));
  if (!tail) {
    return null;
  }
  return normalizeComposerText(`to ${owner} belongs ${tail}`);
}

function renderForSakeChunk(tokens: Token[]): string | null {
  if (!tokens[0] || !isPrepositionalLead(tokens[0])) {
    return null;
  }
  const head = tokenGlossText(tokens[0], { preserveLeadingConjunction: false });
  if (!/sake/i.test(head)) {
    return null;
  }
  const tail = renderTail(tokens.slice(1));
  if (!tail) {
    return null;
  }
  return normalizeComposerText(`for the sake of ${tail}`);
}

function renderDisjunctiveOfferingChunk(tokens: Token[]): string | null {
  if (!tokens[0] || inflateFeatures(tokens[0]).conjunction_role !== 'disjunctive' || !isVerbToken(tokens[0])) {
    return null;
  }
  if (!tokens[1] || !isComplementToken(tokens[1]) || !tokens[2] || !isNegationToken(tokens[2]) || !tokens[3] || !isVerbToken(tokens[3])) {
    return null;
  }
  const offering = renderComplementSequence([tokens[1]]);
  const clause = cleanTokenCandidate(glossFragments(tokens[3]).join(' ')) || tokenGlossText(tokens[3]);
  return normalizeComposerText(`${offering} ${tokenMeaning(tokens[2]).toLowerCase()} ${clause}`);
}

function renderVocativeChunk(tokens: Token[]): string | null {
  if (!tokens[0] || !isVocativeLikeToken(tokens[0])) {
    return null;
  }
  if (tokens.length === 1) {
    return tokenMeaning(tokens[0]);
  }
  const tail = renderTail(tokens.slice(1));
  if (!tail) {
    return tokenMeaning(tokens[0]);
  }
  return normalizeComposerText(`${tokenMeaning(tokens[0])}, ${tail}`);
}

function renderExclamatoryChunk(tokens: Token[]): string | null {
  if (!tokens[0] || !isExclamationToken(tokens[0]) || tokens.length < 2) {
    return null;
  }
  const adjective = tokenMeaning(tokens[1]).toLowerCase();
  const tail = renderTail(tokens.slice(2));
  if (!tail) {
    return normalizeComposerText(`${tokenMeaning(tokens[0])} ${adjective}`);
  }
  return normalizeComposerText(`${tokenMeaning(tokens[0])} ${adjective} is ${tail}`);
}

function renderNegatedPrepositionalChunk(tokens: Token[]): string | null {
  if (!tokens[0] || !isPrepositionalLead(tokens[0])) {
    return null;
  }
  let index = 1;
  const group = [tokens[0]];
  while (tokens[index] && isComplementToken(tokens[index])) {
    group.push(tokens[index]);
    index += 1;
  }
  if (!tokens[index] || !isNegationToken(tokens[index]) || !tokens[index + 1] || !isVerbToken(tokens[index + 1])) {
    return null;
  }
  const clause = `${negationWord(tokens[index])} ${baseVerbText(tokens[index + 1])} ${renderPpGroup(group)}`;
  const tail = renderTail(tokens.slice(index + 2));
  return normalizeComposerText(`${clause}${tail ? ` ${tail}` : ''}`);
}

function renderPrepositionalVerbChunk(tokens: Token[]): string | null {
  if (!tokens[0] || !isPrepositionalLead(tokens[0])) {
    return null;
  }
  let index = 1;
  const group = [tokens[0]];
  while (tokens[index] && isComplementToken(tokens[index])) {
    group.push(tokens[index]);
    index += 1;
  }
  if (!tokens[index] || !isVerbToken(tokens[index])) {
    return null;
  }
  const lead = inflateFeatures(tokens[0]).conjunction_role === 'additive' ? 'and ' : '';
  const clause = `${lead}${renderPpGroup(group)} ${finiteVerbText(tokens[index])}`;
  const tail = renderTail(tokens.slice(index + 1));
  return normalizeComposerText(`${clause}${tail ? ` ${tail}` : ''}`);
}

function renderVerbalChunk(tokens: Token[]): string | null {
  if (!tokens[0] || !isVerbToken(tokens[0])) {
    return null;
  }
  const head = finiteVerbText(tokens[0]);
  const tail = renderTail(tokens.slice(1));
  return normalizeComposerText(`${head}${tail ? ` ${tail}` : ''}`);
}

function isSuperscriptionLikeUnit(unit: Unit): boolean {
  const currentVerse = verseNumber(unit);
  if (currentVerse < 1 || currentVerse > 4 || unit.tokens.length === 0 || unit.tokens.length > 14) {
    return false;
  }

  const texts = unit.tokens.map((token) => tokenMeaning(token).toLowerCase());
  const joined = texts.join(' ');
  const hasMetadataCue = SUPERSCRIPTION_KEYWORD_RE.test(joined) || texts[0]?.startsWith('when');
  const hasSpokenCue = texts.some((text) => SPOKEN_CUE_RE.test(text)) || texts.some((text) => /^(i|we|you)\b/.test(text));

  return hasMetadataCue && !hasSpokenCue;
}

function buildSuperscriptionRanges(unit: Unit, level: ComposerLevel = 'phrase'): Array<{ start: number; end: number }> | null {
  if (!isSuperscriptionLikeUnit(unit) || unit.tokens.length < 2) {
    return null;
  }

  if (level !== 'phrase') {
    const titleStart = unit.tokens.findIndex((token) =>
      /^(a )?(psalm|song|prayer|maskil|miktam|shiggaion)\b/i.test(tokenMeaning(token)),
    );
    if (titleStart > 0) {
      return [
        { start: 0, end: titleStart - 1 },
        { start: titleStart, end: unit.tokens.length - 1 },
      ];
    }
  }

  const ranges: Array<{ start: number; end: number }> = [];
  let currentStart = 0;

  for (let index = 1; index < unit.tokens.length; index += 1) {
    const token = unit.tokens[index];
    const previous = unit.tokens[index - 1];
    const currentText = tokenMeaning(token).toLowerCase();
    const currentFeatures = inflateFeatures(token);
    const previousFeatures = inflateFeatures(previous);
    const currentLength = index - currentStart;
    const startsNewHeaderClause =
      currentText.startsWith('when')
      || /^(a )?(psalm|song|prayer|maskil|miktam|shiggaion)\b/.test(currentText)
      || (Boolean(currentFeatures.preposition_role) && !currentText.startsWith('of '));

    if (startsNewHeaderClause && currentLength >= 1 && !previousFeatures.construct_state) {
      ranges.push({ start: currentStart, end: index - 1 });
      currentStart = index;
    }
  }

  ranges.push({ start: currentStart, end: unit.tokens.length - 1 });
  return ranges.length > 1 ? ranges : null;
}

function properCaseSuperscriptionText(text: string): string {
  return normalizeComposerText(text)
    .replace(/\bdavid\b/g, 'David')
    .replace(/\basaph\b/g, 'Asaph')
    .replace(/\bsolomon\b/g, 'Solomon')
    .replace(/\bmoses\b/g, 'Moses')
    .replace(/\bnathan\b/g, 'Nathan')
    .replace(/\bbath-?sheba\b/gi, 'Bath-sheba');
}

function renderSuperscriptionChunk(tokens: Token[], level: ComposerLevel = 'phrase'): string | null {
  if (tokens.length === 0) {
    return null;
  }
  const raw = normalizeComposerText(tokens.map((token) => tokenMeaning(token)).join(' ')).toLowerCase();
  if (!SUPERSCRIPTION_KEYWORD_RE.test(raw)) {
    return null;
  }
  const hasDirector = /(choirmaster|chief musician|director)/.test(raw);
  const hasFlutes = /\bflutes?\b/.test(raw);
  if (hasDirector && hasFlutes && level !== 'phrase') {
    return 'for the choir director, with flutes';
  }
  if (hasDirector) {
    return level === 'phrase' ? 'to the choirmaster' : 'for the choir director';
  }
  if (hasFlutes) {
    return level === 'phrase' ? 'to the flutes' : 'with flutes';
  }
  if (/^(on|upon)\b/.test(raw) && /(doe|dawn|morning|lilies|gittith|sheminith|alamoth)/.test(raw)) {
    return 'according to the doe of dawn';
  }
  if (/^(on|upon|with)\b/.test(raw) && /(flutes?|instruments?|lyre)/.test(raw)) {
    const normalized = raw.replace(/^upon\b/i, 'on');
    return properCaseSuperscriptionText(level === 'phrase' ? normalized : normalized.replace(/^on\b/i, 'with'));
  }
  if (/^(a )?(psalm|song|prayer|maskil|miktam|shiggaion)\b/.test(raw)) {
    return properCaseSuperscriptionText(raw);
  }
  if (/^(when|after|concerning)\b/.test(raw)) {
    return properCaseSuperscriptionText(raw);
  }
  return null;
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
      rewrittenParts.push(`does not ${nextVerb.remainder}`);
      index += 1;
      continue;
    }
    rewrittenParts.push(current);
  }

  return dedupeAdjacentWords(normalizeComposerText(rewrittenParts.join(' ')))
    .replace(/\bwho not\b/gi, 'who does not')
    .replace(/\bthat not\b/gi, 'that does not')
    .replace(/\bthe man who does not\b/gi, 'the man who does not')
    .replace(/\bof Yahweh\b/g, 'of Yahweh')
    .replace(/\bday and night\b/gi, 'day and night')
    .replace(/\b(person|people) the\b/gi, 'the $1');
}

function toPhraseText(chunk: CompilerChunk): string {
  const text =
    renderSuperscriptionChunk(chunk.tokens, 'phrase') ??
    renderImperativeVocativeChunk(chunk.tokens) ??
    renderBeatitudeChunk(chunk.tokens) ??
    renderRelativeChunk(chunk.tokens) ??
    renderContrastiveChunk(chunk.tokens) ??
    renderNegatedSubjectVerbChunk(chunk.tokens) ??
    renderBelongsToChunk(chunk.tokens) ??
    renderForSakeChunk(chunk.tokens) ??
    renderDisjunctiveOfferingChunk(chunk.tokens) ??
    renderVocativeChunk(chunk.tokens) ??
    renderExclamatoryChunk(chunk.tokens) ??
    renderNegatedPrepositionalChunk(chunk.tokens) ??
    renderPrepositionalVerbChunk(chunk.tokens) ??
    renderVerbalChunk(chunk.tokens) ??
    joinChunkTexts(chunk.tokens).toLowerCase();
  return sentenceCase(normalizeComposerText(text));
}

function toConceptText(chunk: CompilerChunk): string {
  const superscription = renderSuperscriptionChunk(chunk.tokens, 'idea');
  if (superscription) {
    const rewritten = superscription
      .replace(/^to the choirmaster\b/i, 'For the choir director')
      .replace(/^according to\b/i, 'Set to')
      .replace(/\ba psalm of david\b/i, 'A psalm of David');
    return sentenceCase(normalizeComposerText(rewritten));
  }
  const phrase = toPhraseText(chunk)
    .replace(/\bhow blessed is the man\b/gi, 'Blessed is the one')
    .replace(/\bhow blessed is the one\b/gi, 'Blessed is the one')
    .replace(/\bwho does not walk in the counsel of the wicked\b/gi, 'who does not follow the counsel of the wicked')
    .replace(/\bnor stand in the way of sinners\b/gi, 'nor stand in the path of sinners')
    .replace(/\bnor sit in the seat of mockers\b/gi, 'nor sit among mockers')
    .replace(/\binstead, his delight is in the law of Yahweh\b/gi, "Instead, he delights in Yahweh's law")
    .replace(/\band in his law he meditates day and night\b/gi, 'He meditates on his law day and night')
    .replace(/\bto ([A-Z][a-z]+) belongs\b/g, '$1 holds')
    .replace(/\bhow majestic is\b/gi, 'Majestic is')
    .replace(/\blaw of Yahweh\b/g, "Yahweh's law")
    .replace(/\bthe man\b/gi, 'the one');
  return sentenceCase(normalizeComposerText(phrase));
}

function toLyricText(chunk: CompilerChunk): string {
  const superscription = renderSuperscriptionChunk(chunk.tokens, 'lyric');
  if (superscription) {
    const rewritten = superscription
      .replace(/^to the choirmaster\b/i, 'For the choir director')
      .replace(/^according to the\b/i, 'Set to the')
      .replace(/\ba psalm of david\b/i, 'A psalm of David');
    return sentenceCase(normalizeComposerText(rewritten));
  }
  const concept = toConceptText(chunk)
    .replace(/\bBlessed is the one\b/gi, 'How blessed is the one')
    .replace(/\bwho does not follow the counsel of the wicked\b/gi, 'who does not walk with the wicked')
    .replace(/\bnor stand in the path of sinners\b/gi, 'nor stand with sinners')
    .replace(/\bnor sit among mockers\b/gi, 'nor sit among mockers')
    .replace(/\bInstead, he delights in Yahweh's law\b/gi, "His delight is in Yahweh's law")
    .replace(/\bHe meditates on his law day and night\b/gi, 'He dwells on his law day and night')
    .replace(/\bMajestic is\b/gi, 'How majestic is')
    .replace(/\bholds deliverance\b/gi, 'is salvation');
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
  const currentChunk = tokens.slice(currentStart, index);
  const currentHasVerb = currentChunk.some((candidate) => isVerbToken(candidate));
  const currentHasPreposition = currentChunk.some((candidate) => isPrepositionalLead(candidate));
  const currentHasVocative = currentChunk.some((candidate) => isVocativeLikeToken(candidate));
  const currentAllContrastive = currentChunk.length > 0 && currentChunk.every((candidate) => inflateFeatures(candidate).conjunction_role === 'contrastive');

  if (previousFeatures.temporal_pair_candidate && currentFeatures.temporal_pair_candidate) {
    return false;
  }
  if (currentChunk.length > 0 && currentChunk.every((candidate) => inflateFeatures(candidate).temporal_pair_candidate) && isVerbToken(token)) {
    return false;
  }
  if (isSelahToken(token)) {
    return currentLength >= 1;
  }
  if (currentText.startsWith('of ')) {
    return false;
  }
  if (isRelativeToken(token) && currentLength >= 1) {
    return true;
  }
  if (isExclamationToken(token) && currentLength >= 1) {
    return true;
  }
  if (currentFeatures.conjunction_role === 'contrastive' && currentLength >= 2) {
    return true;
  }
  if (currentFeatures.conjunction_role === 'additive' && currentHasVerb && currentLength >= 3 && !currentFeatures.temporal_pair_candidate) {
    return true;
  }
  if ((currentFeatures.conjunction_role === 'additive' || currentFeatures.conjunction_role === 'disjunctive') && currentFeatures.preposition_role && currentLength >= 2) {
    return true;
  }
  if ((currentFeatures.conjunction_role === 'additive' || currentFeatures.conjunction_role === 'disjunctive') && (isVerbToken(token) || isPronounToken(token)) && currentLength >= 2) {
    return true;
  }
  if (previousFeatures.construct_state) {
    return false;
  }
  if (
    currentFeatures.preposition_role
    && currentHasVerb
    && currentHasPreposition
    && currentLength >= 3
  ) {
    return true;
  }
  if (
    currentFeatures.preposition_role
    && currentLength >= 2
    && !currentAllContrastive
    && !(isVerbToken(previous) || isNegationToken(previous))
    && (currentHasVocative || !currentHasVerb || currentHasPreposition || currentLength >= 4)
  ) {
    return true;
  }
  if (
    isVerbToken(token)
    && currentLength >= 2
    && !currentHasVerb
    && currentHasPreposition
    && currentChunk.length <= 2
    && LOCATIVE_PREPOSITION_ROLES.has((inflateFeatures(currentChunk[0]).preposition_role ?? '').toLowerCase())
  ) {
    return false;
  }
  if (isVerbToken(token) && currentLength >= 2 && !currentHasVerb && !isNegationToken(previous) && (currentHasPreposition || currentHasVocative)) {
    return true;
  }
  if (isVerbToken(token) && isVerbToken(previous) && currentLength >= 2 && /^(i|you|he|she|it|we|they)\b/i.test(tokenGlossText(previous))) {
    return true;
  }
  if (isVerbToken(token) && currentHasVerb && currentLength >= 4) {
    return true;
  }
  if (isVocativeLikeToken(token) && currentLength >= 2 && !currentHasVerb) {
    return true;
  }
  if (currentLength >= 6) {
    return true;
  }
  return false;
}

function buildChunks(unit: Unit, level: ComposerLevel = 'phrase'): CompilerChunk[] {
  if (unit.tokens.length === 0) {
    return [];
  }
  const customRanges = buildSuperscriptionRanges(unit, level);
  const ranges: Array<{ start: number; end: number }> = customRanges ? [...customRanges] : [];
  let currentStart = 0;
  if (!customRanges) {
    for (let index = 1; index < unit.tokens.length; index += 1) {
      if (shouldBreakBefore(unit.tokens, index, currentStart)) {
        ranges.push({ start: currentStart, end: index - 1 });
        currentStart = index;
      }
    }
    ranges.push({ start: currentStart, end: unit.tokens.length - 1 });
  }

  if (!customRanges && ranges.length >= 2) {
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

  const phraseChunks = buildChunks(unit, 'phrase');
  const ideaChunks = buildChunks(unit, 'idea');
  const lyricChunks = buildChunks(unit, 'lyric');
  const phraseChoices = finalizeChoiceSequence('phrase', phraseChunks.map((chunk) => {
    const text = toPhraseText(chunk);
    return buildChoice('phrase', chunk, text, displayConfidence(chunk.confidence, chunk.confidenceReasons));
  }));
  const ideaChoices = finalizeChoiceSequence('idea', ideaChunks.map((chunk) => {
    const text = toConceptText(chunk);
    return buildChoice('idea', chunk, text, displayConfidence(chunk.confidence, chunk.confidenceReasons));
  }));
  const lyricChoices = finalizeChoiceSequence('lyric', lyricChunks.map((chunk) => {
    const text = toLyricText(chunk);
    return buildChoice('lyric', chunk, text, displayConfidence(chunk.confidence, chunk.confidenceReasons));
  }));

  return {
    wordChoices,
    phraseChoices,
    ideaChoices,
    lyricChoices,
    phraseSuggestionChunks: phraseChunks.map((chunk, index) => buildSuggestionChunk(chunk, phraseChoices[index]?.text ?? toPhraseText(chunk))),
    ideaSuggestionChunks: ideaChunks.map((chunk, index) => buildSuggestionChunk(chunk, ideaChoices[index]?.text ?? toConceptText(chunk))),
    lyricSuggestionChunks: lyricChunks.map((chunk, index) => buildSuggestionChunk(chunk, lyricChoices[index]?.text ?? toLyricText(chunk))),
  };
}
