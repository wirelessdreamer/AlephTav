import { Fragment, useEffect, useMemo, useState } from 'react';
import type { ChangeEvent, ReactNode } from 'react';

import { useAppRuntime } from '../app/AppContext';
import { AssistantPanel } from '../components/AssistantPanel';
import { BottomDrawer } from '../components/BottomDrawer';
import {
  useAlternateLifecycleAction,
  useCreateRendering,
  useCurrentPsalm,
  useDemoteRendering,
  useGenerateJob,
  useOpenConcerns,
  usePsalm,
  usePinnedLexicalCard,
  useProject,
  usePsalmCloud,
  usePsalmRetrieval,
  usePsalmVisualFlow,
  usePsalms,
  useSetPinnedLexicalCard,
  useTokenCard,
  useUnit,
} from '../hooks/useWorkbench';
import {
  getAvailableCorpusLayers,
  getDefaultPsalmSelection,
  getPreferredSelectableLayer,
  getSelectableLayers,
  getSelectablePsalmOptions,
  resolveLayerState,
  sortRenderingsByStatus,
} from '../lib/layers';
import type { Alignment, CloudNode, Layer, OpenConcerns, Psalm, Rendering, RenderingSpan, RetrievalHit, Token, TokenCard, Unit, VisualFlowUnit } from '../types';

type ComposerChoiceLevel = 'word' | 'phrase' | 'idea' | 'lyric';

type ComposerChoice = {
  id: string;
  label: string;
  tokenStart?: number;
  tokenEnd?: number;
  tokenId?: string;
  description?: string;
  text: string;
};
type WorkingVerseSegment = {
  level: ComposerChoiceLevel;
  choice: ComposerChoice;
};


type WorkingVerseState = {
  sequence: WorkingVerseSegment[];
  selectedByLevel: Partial<Record<ComposerChoiceLevel, ComposerChoice>>;
  workingText: string;
  completed: boolean;
  cursorTokenIndex?: number;
};

type ChapterDraftItem = {
  unitId: string;
  refLabel: string;
  verseNumber: number;
  text: string;
  words: string[];
  active: boolean;
  completionState: 'approved' | 'in-progress' | 'not-started';
};

const COMPOSER_LEVEL_ORDER: ComposerChoiceLevel[] = ['word', 'phrase', 'idea', 'lyric'];

const PUBLIC_DOMAIN_WITNESS_CONFIGS = [
  {
    key: 'kjv',
    laneLabel: 'KJV',
    sourceId: 'kjv',
    versionTitle: 'King James Version',
    aliases: ['kjv', 'king james version', 'king james'],
  },
  {
    key: 'asv',
    laneLabel: 'ASV',
    sourceId: 'asv',
    versionTitle: 'American Standard Version',
    aliases: ['asv', 'american standard version', 'american standard'],
  },
  {
    key: 'web',
    laneLabel: 'WEB',
    sourceId: 'web',
    versionTitle: 'World English Bible',
    aliases: ['web', 'world english bible', 'web version'],
  },
] as const;

type PublicDomainWitnessConfig = (typeof PUBLIC_DOMAIN_WITNESS_CONFIGS)[number];
type PublicDomainWitnessKey = PublicDomainWitnessConfig['key'];
type UnitWitness = Unit['witnesses'][number];

const PSALM_ONE_PUBLIC_DOMAIN_WITNESSES: Record<string, Record<PublicDomainWitnessKey, string>> = {
  'Psalm 1:1': {
    kjv: 'Blessed is the man that walketh not in the counsel of the ungodly, nor standeth in the way of sinners, nor sitteth in the seat of the scornful.',
    asv: 'Blessed is the man that walketh not in the counsel of the wicked, Nor standeth in the way of sinners, Nor sitteth in the seat of scoffers:',
    web: 'Blessed is the man who does not walk in the counsel of the wicked, nor stand on the path of sinners, nor sit in the seat of scoffers;',
  },
  'Psalm 1:2': {
    kjv: 'But his delight is in the law of the LORD; and in his law doth he meditate day and night.',
    asv: 'But his delight is in the law of Jehovah; And on his law doth he meditate day and night.',
    web: 'but his delight is in Yahweh\'s law. On his law he meditates day and night.',
  },
  'Psalm 1:3': {
    kjv: 'And he shall be like a tree planted by the rivers of water, that bringeth forth his fruit in his season; his leaf also shall not wither; and whatsoever he doeth shall prosper.',
    asv: 'And he shall be like a tree planted by the streams of water, That bringeth forth its fruit in its season, Whose leaf also doth not wither; And whatsoever he doeth shall prosper.',
    web: 'He will be like a tree planted by the streams of water, that produces its fruit in its season, whose leaf also does not wither. Whatever he does shall prosper.',
  },
  'Psalm 1:4': {
    kjv: 'The ungodly are not so: but are like the chaff which the wind driveth away.',
    asv: 'The wicked are not so, But are like the chaff which the wind driveth away.',
    web: 'The wicked are not so, but are like the chaff which the wind drives away.',
  },
  'Psalm 1:5': {
    kjv: 'Therefore the ungodly shall not stand in the judgment, nor sinners in the congregation of the righteous.',
    asv: 'Therefore the wicked shall not stand in the judgment, Nor sinners in the congregation of the righteous.',
    web: 'Therefore the wicked shall not stand in the judgment, nor sinners in the congregation of the righteous.',
  },
  'Psalm 1:6': {
    kjv: 'For the LORD knoweth the way of the righteous: but the way of the ungodly shall perish.',
    asv: 'For Jehovah knoweth the way of the righteous; But the way of the wicked shall perish.',
    web: 'For Yahweh knows the way of the righteous, but the way of the wicked shall perish.',
  },
};

function normalizeComposerText(text: string): string {
  return text
    .replace(/[._]/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .trim();
}

function sentenceCase(text: string): string {
  if (!text) {
    return '';
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function buildTokenMeaning(token: Token): string {
  const normalizedSense = normalizeComposerText(token.word_sense ?? token.transliteration ?? token.surface);
  const lowered = normalizedSense.toLowerCase();

  if (lowered === 'person') {
    return token.normalized.startsWith('ה') ? 'the man' : 'person';
  }

  if (lowered.startsWith('how blessed')) {
    return 'How blessed';
  }

  return normalizedSense || token.surface;
}

function assembleComposerText(sequence: WorkingVerseSegment[]): string {
  const text = sequence
    .map((segment) => normalizeComposerText(segment.choice.text))
    .filter(Boolean)
    .join(' ')
    .replace(/\s+/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .trim();

  return sentenceCase(text);
}

function dedupeComposerChoices<T extends ComposerChoice>(choices: T[]): T[] {
  const seen = new Set<string>();
  return choices.filter((choice) => {
    const key = `${choice.tokenStart ?? -1}:${choice.tokenEnd ?? -1}:${choice.text.toLowerCase()}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function latestChoicesByLevel(sequence: WorkingVerseSegment[]): Partial<Record<ComposerChoiceLevel, ComposerChoice>> {
  return sequence.reduce<Partial<Record<ComposerChoiceLevel, ComposerChoice>>>((accumulator, segment) => {
    accumulator[segment.level] = segment.choice;
    return accumulator;
  }, {});
}

function choiceRange(choice: ComposerChoice) {
  const start = choice.tokenStart ?? -1;
  const end = choice.tokenEnd ?? start;
  return { start: Math.min(start, end), end: Math.max(start, end) };
}

function choicesOverlap(left: ComposerChoice, right: ComposerChoice): boolean {
  const leftRange = choiceRange(left);
  const rightRange = choiceRange(right);
  if (leftRange.start < 0 || rightRange.start < 0) {
    return false;
  }
  return leftRange.start <= rightRange.end && rightRange.start <= leftRange.end;
}

function isWorkingSequenceComplete(sequence: WorkingVerseSegment[], tokenCount: number): boolean {
  if (tokenCount <= 0 || sequence.length === 0) {
    return false;
  }

  const orderedRanges = sequence
    .map((segment) => choiceRange(segment.choice))
    .filter((range) => range.start >= 0)
    .sort((left, right) => left.start - right.start || left.end - right.end);

  if (orderedRanges.length === 0 || orderedRanges[0].start > 0) {
    return false;
  }

  let coveredEnd = -1;
  for (const range of orderedRanges) {
    if (range.start > coveredEnd + 1) {
      return false;
    }
    coveredEnd = Math.max(coveredEnd, range.end);
  }

  return coveredEnd >= tokenCount - 1;
}

function getPreferredUnitRendering(unit: Unit | undefined, layer: Layer): Rendering | null {
  if (!unit) {
    return null;
  }

  const exactLayer = sortRenderingsByStatus(unit.renderings.filter((rendering) => rendering.layer === layer))[0];
  if (exactLayer) {
    return exactLayer;
  }

  return sortRenderingsByStatus(
    unit.renderings.filter(
      (rendering) => rendering.layer === 'lyric' || rendering.layer === 'metered_lyric' || rendering.layer === 'parallelism_lyric',
    ),
  )[0] ?? null;
}

export function WorkbenchPage() {
  const {
    workbenchSelection,
    updateWorkbenchSelection,
    workbenchUi,
    updateWorkbenchUi,
    assistantUi,
    toggleWorkbenchTokenSelection,
    toggleWorkbenchSpanSelection,
    clearWorkbenchSelections,
  } = useAppRuntime();
  const selectedPsalmId = workbenchSelection.psalmId;
  const selectedUnitId = workbenchSelection.unitId;
  const activeLayer = workbenchSelection.layer;
  const granularity = workbenchSelection.granularity;
  const hoveredTokenId = workbenchUi.hoveredTokenId;
  const hoveredSpanId = workbenchUi.hoveredSpanId;
  const selectedTokenIds = workbenchUi.selectedTokenIds;
  const selectedSpanIds = workbenchUi.selectedSpanIds;
  const selectedAlignmentId = workbenchUi.selectedAlignmentId;
  const compareLeftId = workbenchUi.compareLeftId;
  const compareRightId = workbenchUi.compareRightId;
  const [selectedCloudNodeId, setSelectedCloudNodeId] = useState<string | null>(null);
  const [previewTokenIds, setPreviewTokenIds] = useState<string[]>([]);

  const projectQuery = useProject();
  const psalmsQuery = usePsalms();
  const { data: psalms } = psalmsQuery;
  const selectablePsalms = useMemo(() => getSelectablePsalmOptions(psalms), [psalms]);
  const selectedPsalm = useCurrentPsalm(selectablePsalms, selectedPsalmId);
  const defaultPsalm = useMemo(
    () => getDefaultPsalmSelection(selectablePsalms, selectedPsalmId),
    [selectablePsalms, selectedPsalmId],
  );
  const effectivePsalmId = selectedPsalm?.psalm_id ?? defaultPsalm?.psalm_id ?? null;
  const currentPsalmQuery = usePsalm(effectivePsalmId);
  const visualFlowQuery = usePsalmVisualFlow(effectivePsalmId);
  const cloudQuery = usePsalmCloud(effectivePsalmId);
  const retrievalQuery = usePsalmRetrieval(effectivePsalmId, selectedCloudNodeId);
  const unitQuery = useUnit(selectedUnitId);
  const concernsQuery = useOpenConcerns();
  const pinnedLexicalCardQuery = usePinnedLexicalCard();
  const { data: project } = projectQuery;
  const { data: currentPsalm } = currentPsalmQuery;
  const { data: visualFlow } = visualFlowQuery;
  const { data: unit } = unitQuery;
  const { data: concerns } = concernsQuery;
  const { data: pinnedLexicalCard } = pinnedLexicalCardQuery;
  const setPinnedLexicalCard = useSetPinnedLexicalCard();
  const alternateAction = useAlternateLifecycleAction(selectedUnitId);
  const demoteRendering = useDemoteRendering(selectedUnitId);
  const createRendering = useCreateRendering(selectedUnitId);
  const generateJob = useGenerateJob(selectedUnitId);
  const [guidedDraftText, setGuidedDraftText] = useState('');
  const [guidedMessage, setGuidedMessage] = useState<string | null>(null);
  const [workingVerseByUnit, setWorkingVerseByUnit] = useState<Record<string, WorkingVerseState>>({});
  const [returnToUnitId, setReturnToUnitId] = useState<string | null>(null);

  const pinnedTokenId = workbenchUi.pinnedTokenId ?? pinnedLexicalCard?.token_id ?? null;
  const [pinOverrideTokenId, setPinOverrideTokenId] = useState<string | null | undefined>(undefined);
  const effectivePinnedTokenId = pinOverrideTokenId !== undefined ? pinOverrideTokenId : pinnedTokenId;
  const hoveredToken = useTokenCard(!effectivePinnedTokenId ? hoveredTokenId : null);
  const pendingPinnedToken = useTokenCard(
    pinOverrideTokenId !== undefined && pinOverrideTokenId !== null && pinOverrideTokenId !== pinnedTokenId ? pinOverrideTokenId : null,
  );
  const tokenCard = pinnedLexicalCard?.token ?? pendingPinnedToken.data ?? hoveredToken.data;
  const [displayedTokenCard, setDisplayedTokenCard] = useState<TokenCard | undefined>(undefined);
  const tokenId = displayedTokenCard?.token_id ?? tokenCard?.token_id ?? hoveredTokenId;

  const bootstrapError = projectQuery.error ?? psalmsQuery.error ?? currentPsalmQuery.error ?? visualFlowQuery.error;
  const isPsalmListLoading = (psalmsQuery.isPending || psalmsQuery.isFetching) && selectablePsalms.length === 0;
  const isUnitListLoading =
    effectivePsalmId !== null &&
    !currentPsalm &&
    (currentPsalmQuery.isPending || currentPsalmQuery.isFetching);
  const showStartupDropdownNotice = !bootstrapError && (isPsalmListLoading || isUnitListLoading);
  const unitMap = useMemo(
    () => new Map((currentPsalm?.units ?? []).map((item) => [item.unit_id, item])),
    [currentPsalm?.units],
  );

  const activeAlignments = useMemo(() => unit?.alignments.filter((alignment: Alignment) => alignment.layer === activeLayer) ?? [], [unit, activeLayer]);
  const selectedUnitLayerState = useMemo(() => resolveLayerState(unit, activeLayer), [unit, activeLayer]);
  const selectableLayers = useMemo(
    () => getSelectableLayers(getAvailableCorpusLayers(selectablePsalms)),
    [selectablePsalms],
  );
  const selectedWorkflowLayer = useMemo(
    () => getPreferredSelectableLayer(activeLayer, selectableLayers),
    [activeLayer, selectableLayers],
  );

  const activeAlignment = useMemo(
    () => activeAlignments.find((alignment: Alignment) => alignment.alignment_id === selectedAlignmentId) ?? null,
    [activeAlignments, selectedAlignmentId],
  );

  const tokenToAlignments = useMemo(() => {
    const mapping = new Map<string, Alignment[]>();
    activeAlignments.forEach((alignment) => {
      alignment.source_token_ids.forEach((alignmentTokenId) => {
        mapping.set(alignmentTokenId, [...(mapping.get(alignmentTokenId) ?? []), alignment]);
      });
    });
    return mapping;
  }, [activeAlignments]);

  const spanToAlignments = useMemo(() => {
    const mapping = new Map<string, Alignment[]>();
    activeAlignments.forEach((alignment) => {
      alignment.target_span_ids.forEach((spanId) => {
        mapping.set(spanId, [...(mapping.get(spanId) ?? []), alignment]);
      });
    });
    return mapping;
  }, [activeAlignments]);

  const highlightedTokenIds = useMemo(() => {
    const ids = new Set<string>([...selectedTokenIds, ...previewTokenIds]);
    selectedSpanIds.forEach((spanId) => {
      (spanToAlignments.get(spanId) ?? []).forEach((alignment) => alignment.source_token_ids.forEach((alignmentTokenId) => ids.add(alignmentTokenId)));
    });
    if (hoveredSpanId) {
      (spanToAlignments.get(hoveredSpanId) ?? []).forEach((alignment) => alignment.source_token_ids.forEach((alignmentTokenId) => ids.add(alignmentTokenId)));
    }
    activeAlignment?.source_token_ids.forEach((alignmentTokenId) => ids.add(alignmentTokenId));
    return [...ids];
  }, [activeAlignment, hoveredSpanId, previewTokenIds, selectedTokenIds, selectedSpanIds, spanToAlignments]);

  const highlightedSpanIds = useMemo(() => {
    const ids = new Set<string>(selectedSpanIds);
    [...selectedTokenIds, ...previewTokenIds].forEach((selectedTokenId) => {
      (tokenToAlignments.get(selectedTokenId) ?? []).forEach((alignment) => alignment.target_span_ids.forEach((spanId) => ids.add(spanId)));
    });
    if (hoveredTokenId) {
      (tokenToAlignments.get(hoveredTokenId) ?? []).forEach((alignment) => alignment.target_span_ids.forEach((spanId) => ids.add(spanId)));
    }
    activeAlignment?.target_span_ids.forEach((spanId) => ids.add(spanId));
    return [...ids];
  }, [activeAlignment, hoveredTokenId, previewTokenIds, selectedSpanIds, selectedTokenIds, tokenToAlignments]);

  const cloudNodes = cloudQuery.data?.nodes ?? visualFlow?.cloud_nodes ?? [];
  const selectedVisualUnit = useMemo(
    () => visualFlow?.units.find((visualUnit) => visualUnit.unit_id === selectedUnitId) ?? null,
    [selectedUnitId, visualFlow?.units],
  );
  const activeCloudNode = useMemo(
    () => cloudNodes.find((node) => node.node_id === selectedCloudNodeId) ?? retrievalQuery.data?.node ?? null,
    [cloudNodes, retrievalQuery.data?.node, selectedCloudNodeId],
  );

  const retrievalHitsByUnit = useMemo(() => {
    const grouped = new Map<string, RetrievalHit[]>();
    (retrievalQuery.data?.hits ?? []).forEach((hit) => {
      grouped.set(hit.unit_id, [...(grouped.get(hit.unit_id) ?? []), hit]);
    });
    return grouped;
  }, [retrievalQuery.data?.hits]);
  const selectedUnitRetrievalHits = selectedUnitId ? retrievalHitsByUnit.get(selectedUnitId) ?? [] : [];
  const selectedUnitRenderings = useMemo(() => sortRenderingsByStatus(unit?.renderings ?? []), [unit?.renderings]);
  const activeLayerRenderings = useMemo(
    () => selectedUnitRenderings.filter((rendering) => rendering.layer === activeLayer),
    [activeLayer, selectedUnitRenderings],
  );
  const phraseAidRenderings = useMemo(
    () => selectedUnitRenderings.filter((rendering) => rendering.layer === 'phrase'),
    [selectedUnitRenderings],
  );
  const conceptAidRenderings = useMemo(
    () => selectedUnitRenderings.filter((rendering) => rendering.layer === 'concept'),
    [selectedUnitRenderings],
  );
  const literalAidRenderings = useMemo(
    () => selectedUnitRenderings.filter((rendering) => rendering.layer === 'literal' || rendering.layer === 'gloss'),
    [selectedUnitRenderings],
  );
  const currentEnglishRenderings = useMemo(
    () => {
      if (activeLayerRenderings.length > 0) {
        return activeLayerRenderings;
      }
      return selectedUnitRenderings.filter(
        (rendering) => rendering.layer === 'lyric' || rendering.layer === 'metered_lyric' || rendering.layer === 'parallelism_lyric',
      );
    },
    [activeLayerRenderings, selectedUnitRenderings],
  );
  const currentUnitWorkingState = selectedUnitId ? workingVerseByUnit[selectedUnitId] ?? null : null;
  const currentWorkingChoices = currentUnitWorkingState?.selectedByLevel ?? {};
  const currentReferenceRendering = activeLayerRenderings[0] ?? currentEnglishRenderings[0] ?? null;
  const currentWorkingText = currentUnitWorkingState?.workingText?.trim() || currentReferenceRendering?.text || '';
  const currentWorkingPath = currentUnitWorkingState?.sequence ?? [];
  const currentCursorTokenIndex = useMemo(() => {
    if (!unit) {
      return 0;
    }
    if (typeof currentUnitWorkingState?.cursorTokenIndex === 'number') {
      return Math.max(0, Math.min(currentUnitWorkingState.cursorTokenIndex, unit.tokens.length - 1));
    }
    if (currentWorkingPath.length === 0) {
      return 0;
    }
    const lastCovered = currentWorkingPath.reduce((maximum, segment) => {
      const segmentEnd = segment.choice.tokenEnd ?? segment.choice.tokenStart ?? -1;
      return Math.max(maximum, segmentEnd);
    }, -1);
    return Math.max(0, Math.min(lastCovered + 1, unit.tokens.length - 1));
  }, [currentUnitWorkingState?.cursorTokenIndex, currentWorkingPath, unit]);
  const totalUnits = currentPsalm?.unit_ids.length ?? 0;
  const currentUnitIndex = selectedUnitId && currentPsalm ? currentPsalm.unit_ids.indexOf(selectedUnitId) : -1;
  const completedUnitCount = currentPsalm?.unit_ids.filter((unitId) => workingVerseByUnit[unitId]?.completed).length ?? 0;
  const previousUnitId = currentPsalm && currentUnitIndex > 0 ? currentPsalm.unit_ids[currentUnitIndex - 1] : null;
  const nextUnitId = currentPsalm && currentUnitIndex >= 0 ? currentPsalm.unit_ids[currentUnitIndex + 1] ?? null : null;
  const currentCompletionState = currentUnitWorkingState?.completed
    ? 'Approved'
    : currentWorkingPath.length > 0 || currentWorkingText.trim().length > 0
      ? 'In progress'
      : 'Not started';
  const currentDirty = currentWorkingPath.length > 0 && currentWorkingText.trim() !== (currentReferenceRendering?.text ?? '').trim();
  const currentVerseReadyToLock = useMemo(
    () => (unit ? isWorkingSequenceComplete(currentWorkingPath, unit.tokens.length) : false),
    [currentWorkingPath, unit],
  );
  const canAdvanceToNextVerse = Boolean(nextUnitId) && (Boolean(currentUnitWorkingState?.completed) || currentVerseReadyToLock);
  const chapterDraftItems = useMemo<ChapterDraftItem[]>(
    () => (currentPsalm?.unit_ids ?? []).map((unitId, index) => {
      const unitEntry = unitMap.get(unitId);
      const workingState = workingVerseByUnit[unitId];
      const savedRendering = getPreferredUnitRendering(unitEntry, activeLayer);
      const text = workingState?.workingText?.trim() || savedRendering?.text?.trim() || '';
      return {
        unitId,
        refLabel: unitEntry?.ref ?? `Verse ${index + 1}`,
        verseNumber: index + 1,
        text,
        words: text ? text.split(/\s+/).filter(Boolean) : [],
        active: unitId === selectedUnitId,
        completionState: workingState?.completed ? 'approved' : text ? 'in-progress' : 'not-started',
      };
    }),
    [activeLayer, currentPsalm?.unit_ids, selectedUnitId, unitMap, workingVerseByUnit],
  );
  const returnToVerseRef = returnToUnitId ? unitMap.get(returnToUnitId)?.ref ?? returnToUnitId : null;
  const clickOnlySuggestions = useMemo(() => {
    const suggestions = new Map<string, {
      id: string;
      text: string;
      source: string;
      tone: 'generated' | 'word' | 'phrase' | 'idea' | 'lyric';
      renderingId?: string;
    }>();

    const addSuggestion = (suggestion: {
      id: string;
      text: string;
      source: string;
      tone: 'generated' | 'word' | 'phrase' | 'idea' | 'lyric';
      renderingId?: string;
    }) => {
      const normalized = suggestion.text.trim();
      if (!normalized || suggestions.has(normalized)) {
        return;
      }
      suggestions.set(normalized, { ...suggestion, text: normalized });
    };

    if (guidedDraftText.trim()) {
      addSuggestion({
        id: 'generated-click-suggestion',
        text: guidedDraftText,
        source: `Generated ${activeLayer}`,
        tone: 'generated',
      });
    }

    literalAidRenderings.slice(0, 2).forEach((rendering) => {
      addSuggestion({
        id: `word-${rendering.rendering_id}`,
        text: rendering.text,
        source: `${rendering.layer} aid`,
        tone: 'word',
        renderingId: rendering.rendering_id,
      });
    });

    phraseAidRenderings.slice(0, 3).forEach((rendering) => {
      addSuggestion({
        id: `phrase-${rendering.rendering_id}`,
        text: rendering.text,
        source: 'Phrase aid',
        tone: 'phrase',
        renderingId: rendering.rendering_id,
      });
    });

    conceptAidRenderings.slice(0, 2).forEach((rendering) => {
      addSuggestion({
        id: `idea-${rendering.rendering_id}`,
        text: rendering.text,
        source: 'Idea aid',
        tone: 'idea',
        renderingId: rendering.rendering_id,
      });
    });

    selectedUnitRetrievalHits.slice(0, 2).forEach((hit) => {
      addSuggestion({
        id: `lyric-${hit.hit_id}`,
        text: hit.label,
        source: hit.scope === 'same_psalm' ? 'Lyric witness' : 'Cross-Psalm lyric',
        tone: 'lyric',
        renderingId: hit.rendering_id,
      });
    });

    return [...suggestions.values()].slice(0, 6);
  }, [activeLayer, conceptAidRenderings, guidedDraftText, literalAidRenderings, phraseAidRenderings, selectedUnitRetrievalHits]);
  const focusedTokenId = effectivePinnedTokenId ?? hoveredTokenId ?? selectedTokenIds[0] ?? unit?.tokens[0]?.token_id ?? null;
  const focusedUnitToken = useMemo(
    () => unit?.tokens.find((token) => token.token_id === focusedTokenId) ?? unit?.tokens[0] ?? null,
    [focusedTokenId, unit?.tokens],
  );

  useEffect(() => {
    setPreviewTokenIds([]);
    updateWorkbenchUi({
      hoveredTokenId: null,
      hoveredSpanId: null,
      selectedTokenIds: [],
      selectedSpanIds: [],
      selectedAlignmentId: null,
    });
  }, [selectedUnitId, activeLayer]);

  useEffect(() => {
    setSelectedCloudNodeId(null);
  }, [selectedPsalmId]);

  useEffect(() => {
    if (!selectablePsalms.length) {
      return;
    }
    const nextPsalm = getDefaultPsalmSelection(selectablePsalms, selectedPsalmId);
    if (!nextPsalm) {
      return;
    }
    const nextUnitId = nextPsalm.unit_ids[0] ?? null;
    if (nextPsalm.psalm_id !== selectedPsalmId || !workbenchSelection.unitId || !nextPsalm.unit_ids.includes(workbenchSelection.unitId)) {
      updateWorkbenchSelection({
        psalmId: nextPsalm.psalm_id,
        unitId: nextUnitId,
      });
    }
  }, [selectablePsalms, selectedPsalmId, updateWorkbenchSelection, workbenchSelection.unitId]);

  useEffect(() => {
    if (!currentPsalm) {
      return;
    }
    const firstIncompleteUnitId = currentPsalm.unit_ids.find((unitId) => !workingVerseByUnit[unitId]?.completed) ?? currentPsalm.unit_ids[0] ?? null;
    if (!selectedUnitId || !currentPsalm.unit_ids.includes(selectedUnitId)) {
      updateWorkbenchSelection({ unitId: firstIncompleteUnitId });
    }
  }, [currentPsalm, selectedUnitId, updateWorkbenchSelection, workingVerseByUnit]);

  useEffect(() => {
    if (activeLayer !== selectedWorkflowLayer) {
      updateWorkbenchSelection({ layer: selectedWorkflowLayer });
    }
  }, [activeLayer, selectedWorkflowLayer, updateWorkbenchSelection]);

  useEffect(() => {
    if (returnToUnitId && selectedUnitId === returnToUnitId) {
      setReturnToUnitId(null);
    }
  }, [returnToUnitId, selectedUnitId]);

  useEffect(() => {
    if (!selectedAlignmentId) {
      return;
    }
    if (!activeAlignments.some((alignment) => alignment.alignment_id === selectedAlignmentId)) {
      updateWorkbenchUi({ selectedAlignmentId: null });
    }
  }, [activeAlignments, selectedAlignmentId]);

  useEffect(() => {
    if (!activeAlignment) {
      return;
    }
    updateWorkbenchUi({
      selectedTokenIds: activeAlignment.source_token_ids,
      selectedSpanIds: activeAlignment.target_span_ids,
    });
  }, [activeAlignment]);

  useEffect(() => {
    setPinOverrideTokenId(undefined);
  }, [pinnedTokenId]);

  useEffect(() => {
    if (pinnedLexicalCard?.token_id && workbenchUi.pinnedTokenId === null) {
      updateWorkbenchUi({ pinnedTokenId: pinnedLexicalCard.token_id });
    }
  }, [pinnedLexicalCard?.token_id]);

  useEffect(() => {
    if (tokenCard) {
      setDisplayedTokenCard(tokenCard);
      return;
    }
    if (!effectivePinnedTokenId && !hoveredTokenId) {
      setDisplayedTokenCard(undefined);
    }
  }, [effectivePinnedTokenId, hoveredTokenId, tokenCard]);

  useEffect(() => {
    setGuidedDraftText('');
    setGuidedMessage(null);
  }, [activeLayer, selectedUnitId]);

  useEffect(() => {
    if (!unit) {
      return;
    }
    const renderingIds = new Set(unit.renderings.map((rendering) => rendering.rendering_id));
    const patch: {
      compareLeftId?: string | null;
      compareRightId?: string | null;
    } = {};
    if (compareLeftId && !renderingIds.has(compareLeftId)) {
      patch.compareLeftId = null;
    }
    if (compareRightId && !renderingIds.has(compareRightId)) {
      patch.compareRightId = null;
    }
    if (Object.keys(patch).length > 0) {
      updateWorkbenchUi(patch);
    }
  }, [compareLeftId, compareRightId, unit, updateWorkbenchUi]);

  const handlePsalmChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const nextPsalmId = event.target.value;
    const nextPsalm = selectablePsalms.find((psalm: Psalm) => psalm.psalm_id === nextPsalmId);
    updateWorkbenchSelection({
      psalmId: nextPsalmId,
      unitId: nextPsalm?.unit_ids[0] ?? null,
    });
  };

  const handleUnitChange = (event: ChangeEvent<HTMLSelectElement>) => {
    updateWorkbenchSelection({ unitId: event.target.value });
  };

  const handleNavigateToUnit = (unitId: string, psalmId: string) => {
    updateWorkbenchSelection({ psalmId, unitId });
  };

  const handleGranularityChange = (event: ChangeEvent<HTMLSelectElement>) => {
    updateWorkbenchSelection({ granularity: event.target.value as 'colon' | 'verse' });
  };

  const handlePinToken = (nextTokenId: string) => {
    const tokenIdToPersist = effectivePinnedTokenId === nextTokenId ? null : nextTokenId;
    setPinOverrideTokenId(tokenIdToPersist);
    updateWorkbenchUi({ pinnedTokenId: tokenIdToPersist });
    setPinnedLexicalCard.mutate(tokenIdToPersist);
  };

  const handleUnpinToken = () => {
    setPinOverrideTokenId(null);
    updateWorkbenchUi({ pinnedTokenId: null });
    setPinnedLexicalCard.mutate(null);
  };

  const ensureSelectedUnit = (unitId: string) => {
    if (selectedUnitId !== unitId) {
      updateWorkbenchSelection({ unitId });
    }
  };

  const handleToggleToken = (unitId: string, nextTokenId: string) => {
    ensureSelectedUnit(unitId);
    toggleWorkbenchTokenSelection(nextTokenId);
  };

  const handleToggleSpan = (unitId: string, spanId: string) => {
    ensureSelectedUnit(unitId);
    toggleWorkbenchSpanSelection(spanId);
  };

  const handlePromoteAlternate = (renderingId: string) => {
    alternateAction.mutate({ renderingId, action: 'promote', payload: { reviewer: 'ui', reviewer_role: 'release reviewer' } });
  };

  const handleAcceptAlternate = (renderingId: string) => {
    alternateAction.mutate({ renderingId, action: 'accept', payload: { created_by: 'ui' } });
  };

  const handleRejectAlternate = (renderingId: string) => {
    alternateAction.mutate({ renderingId, action: 'reject', payload: { created_by: 'ui' } });
  };

  const handleDeprecateAlternate = (renderingId: string) => {
    alternateAction.mutate({ renderingId, action: 'deprecate', payload: { created_by: 'ui' } });
  };

  const handleGuidedDraftSave = () => {
    const nextText = guidedDraftText.trim();
    if (!selectedUnitId || !nextText) {
      return;
    }
    setGuidedMessage(null);
    createRendering.mutate(
      {
        layer: activeLayer,
        text: nextText,
        status: 'proposed',
        rationale: 'guided draft from workbench fallback',
        created_by: 'ui-guided-draft',
        style_tags: [activeLayer, 'guided-draft'],
      },
      {
        onError: (error) => {
          setGuidedMessage(error instanceof Error ? error.message : 'Unable to save draft.');
        },
        onSuccess: () => {
          setGuidedDraftText('');
          setGuidedMessage(`Saved proposed ${activeLayer} draft.`);
        },
      },
    );
  };

  const handleGenerateStarter = () => {
    if (!selectedUnitId) {
      return;
    }
    setGuidedMessage(null);
    generateJob.mutate(
      { layer: activeLayer, candidate_count: 1 },
      {
        onError: (error) => {
          setGuidedMessage(error instanceof Error ? error.message : 'Unable to generate starter.');
        },
        onSuccess: (job) => {
          const candidateText = job.output?.candidates[0]?.text?.trim() ?? '';
          setGuidedDraftText(candidateText);
          setGuidedMessage(candidateText ? `Generated starter for ${activeLayer}.` : `Generation completed for ${activeLayer}.`);
        },
      },
    );
  };

  const handleApproveSuggestion = (text: string, source: string) => {
    const nextText = text.trim();
    if (!selectedUnitId || !nextText) {
      return;
    }
    setGuidedMessage(null);
    createRendering.mutate(
      {
        layer: activeLayer,
        text: nextText,
        status: 'proposed',
        rationale: `click-approved from ${source}`,
        created_by: 'ui-click-approval',
        style_tags: [activeLayer, 'click-only', source.toLowerCase().replace(/\s+/g, '-')],
      },
      {
        onError: (error) => {
          setGuidedMessage(error instanceof Error ? error.message : 'Unable to save suggestion.');
        },
        onSuccess: () => {
          setGuidedMessage(`Saved proposed ${activeLayer} rendering from ${source}.`);
        },
      },
    );
  };

  const handleApplyWorkingChoice = (level: ComposerChoiceLevel, choice: ComposerChoice) => {
    if (!selectedUnitId) {
      return;
    }
    setGuidedMessage(null);
    setPreviewTokenIds([]);
    if (unit && typeof choice.tokenStart === 'number') {
      const start = Math.max(0, choice.tokenStart);
      const end = Math.min(unit.tokens.length - 1, choice.tokenEnd ?? choice.tokenStart);
      const tokenIds = unit.tokens.slice(start, end + 1).map((token) => token.token_id);
      updateWorkbenchUi({
        selectedTokenIds: tokenIds,
        selectedSpanIds: [],
        selectedAlignmentId: null,
        hoveredTokenId: null,
        hoveredSpanId: null,
      });
    }
    setWorkingVerseByUnit((previous) => {
      const existing = previous[selectedUnitId] ?? { selectedByLevel: {}, sequence: [], workingText: '', completed: false, cursorTokenIndex: 0 };
      const nextSequenceBase = existing.sequence.filter((segment) => !choicesOverlap(segment.choice, choice));
      const nextSequence = [...nextSequenceBase, { level, choice }].sort((left, right) => {
        const leftRange = choiceRange(left.choice);
        const rightRange = choiceRange(right.choice);
        return leftRange.start - rightRange.start || leftRange.end - rightRange.end;
      });
      const nextSelectedByLevel = latestChoicesByLevel(nextSequence);
      const nextWorkingText = assembleComposerText(nextSequence) || currentReferenceRendering?.text || '';
      const nextCursorTokenIndex = typeof choice.tokenStart === 'number'
        ? (choice.tokenEnd ?? choice.tokenStart) + 1
        : existing.cursorTokenIndex ?? 0;

      return {
        ...previous,
        [selectedUnitId]: {
          selectedByLevel: nextSelectedByLevel,
          sequence: nextSequence,
          workingText: nextWorkingText,
          completed: false,
          cursorTokenIndex: nextCursorTokenIndex,
        },
      };
    });
  };

  const handlePreviewWorkingChoice = (choice: ComposerChoice | null) => {
    if (!unit || !choice || typeof choice.tokenStart !== 'number') {
      setPreviewTokenIds([]);
      return;
    }
    const start = Math.max(0, choice.tokenStart);
    const end = Math.min(unit.tokens.length - 1, choice.tokenEnd ?? choice.tokenStart);
    setPreviewTokenIds(unit.tokens.slice(start, end + 1).map((token) => token.token_id));
  };

  const handleClearWorkingChoicePreview = () => {
    setPreviewTokenIds([]);
  };

  const handleSetWorkingCursor = (tokenIndex: number) => {
    if (!selectedUnitId || !unit) {
      return;
    }
    const clampedIndex = Math.max(0, Math.min(tokenIndex, unit.tokens.length - 1));
    const tokenId = unit.tokens[clampedIndex]?.token_id;

    setWorkingVerseByUnit((previous) => {
      const existing = previous[selectedUnitId] ?? {
        selectedByLevel: {},
        sequence: [],
        workingText: currentReferenceRendering?.text ?? '',
        completed: false,
        cursorTokenIndex: 0,
      };
      const trimmedSequence = existing.sequence.filter((segment) => {
        const segmentEnd = segment.choice.tokenEnd ?? segment.choice.tokenStart ?? -1;
        return segmentEnd < clampedIndex;
      });

      return {
        ...previous,
        [selectedUnitId]: {
          ...existing,
          sequence: trimmedSequence,
          selectedByLevel: latestChoicesByLevel(trimmedSequence),
          workingText: assembleComposerText(trimmedSequence) || currentReferenceRendering?.text || '',
          completed: false,
          cursorTokenIndex: clampedIndex,
        },
      };
    });

    if (tokenId) {
      updateWorkbenchUi({
        selectedTokenIds: [tokenId],
        selectedSpanIds: [],
        selectedAlignmentId: null,
        hoveredTokenId: null,
        hoveredSpanId: null,
      });
    }

    setGuidedMessage(`Editing from token ${clampedIndex + 1}. Choose a new word or phrase to revise the verse path.`);
  };

  const handleResetWorkingVerse = () => {
    if (!selectedUnitId) {
      return;
    }
    setWorkingVerseByUnit((previous) => ({
      ...previous,
      [selectedUnitId]: {
        selectedByLevel: {},
        sequence: [],
        workingText: currentReferenceRendering?.text ?? '',
        completed: false,
        cursorTokenIndex: 0,
      },
    }));
    setGuidedMessage('Cleared current verse choices.');
  };

  const markVerseCompleted = (unitId: string, advance: boolean) => {
    setWorkingVerseByUnit((previous) => ({
      ...previous,
      [unitId]: {
        ...(previous[unitId] ?? { selectedByLevel: {}, sequence: [], workingText: '', completed: false, cursorTokenIndex: 0 }),
        completed: true,
      },
    }));

    if (!currentPsalm || !advance) {
      setGuidedMessage(`${unitMap.get(unitId)?.ref ?? unitId} marked complete.`);
      return;
    }

    const currentIndex = currentPsalm.unit_ids.indexOf(unitId);
    const nextUnitIdToLoad = currentPsalm.unit_ids[currentIndex + 1] ?? null;
    if (nextUnitIdToLoad) {
      updateWorkbenchSelection({ unitId: nextUnitIdToLoad });
      setGuidedMessage(`Verse completed. Moved to ${unitMap.get(nextUnitIdToLoad)?.ref ?? nextUnitIdToLoad}.`);
      return;
    }

    setGuidedMessage(`Psalm complete. Finished ${currentPsalm.unit_ids.length} verse unit(s).`);
  };

  const handleCompleteVerse = (advance: boolean) => {
    if (!selectedUnitId) {
      return;
    }

    const nextText = currentWorkingText.trim();
    if (!nextText) {
      setGuidedMessage('Pick at least one option before completing this verse.');
      return;
    }

    const alreadySaved = selectedUnitRenderings.some(
      (rendering) => rendering.layer === activeLayer && rendering.text.trim() === nextText,
    );

    if (alreadySaved) {
      markVerseCompleted(selectedUnitId, advance);
      return;
    }

    createRendering.mutate(
      {
        layer: activeLayer,
        text: nextText,
        status: 'proposed',
        rationale: 'guided verse composer completion',
        created_by: 'ui-guided-composer',
        style_tags: [activeLayer, 'guided-composer', 'verse-complete'],
      },
      {
        onError: (error) => {
          setGuidedMessage(error instanceof Error ? error.message : 'Unable to complete verse.');
        },
        onSuccess: () => {
          markVerseCompleted(selectedUnitId, advance);
        },
      },
    );
  };

  const handleNavigateRelativeVerse = (unitIdToLoad: string | null) => {
    if (!unitIdToLoad) {
      return;
    }
    updateWorkbenchSelection({ unitId: unitIdToLoad });
    setPreviewTokenIds([]);
    setGuidedMessage(`Loaded ${unitMap.get(unitIdToLoad)?.ref ?? unitIdToLoad}.`);
  };

  const handleJumpToChapterVerse = (unitIdToLoad: string) => {
    if (!selectedUnitId || unitIdToLoad === selectedUnitId) {
      return;
    }
    setReturnToUnitId((existing) => existing ?? selectedUnitId);
    updateWorkbenchSelection({ unitId: unitIdToLoad });
    setPreviewTokenIds([]);
    setGuidedMessage(`Reviewing ${unitMap.get(unitIdToLoad)?.ref ?? unitIdToLoad}. Use catch up to return to ${unitMap.get(selectedUnitId)?.ref ?? selectedUnitId}.`);
  };

  const handleCatchUpToCurrent = () => {
    if (!returnToUnitId) {
      return;
    }
    const unitIdToLoad = returnToUnitId;
    setReturnToUnitId(null);
    updateWorkbenchSelection({ unitId: unitIdToLoad });
    setPreviewTokenIds([]);
    setGuidedMessage(`Returned to ${unitMap.get(unitIdToLoad)?.ref ?? unitIdToLoad}.`);
  };

  if (bootstrapError) {
    return (
      <main className="workbench-shell workbench-shell--empty">
        <section className="empty-state-card">
          <p className="eyebrow">Workbench Unavailable</p>
          <h1>Start the local API before opening the workbench.</h1>
          <p className="subtle">
            The workbench expects the FastAPI backend on <code>127.0.0.1:8765</code>. GitHub Pages can show the welcome page, but the live editor remains local-only. Use the repo setup script to verify dependencies, rebuild local data, and launch both services.
          </p>
          <pre>
            <code>{['./setup.sh', '.\\setup.ps1'].join('\n')}</code>
          </pre>
          <div className="hero-actions">
            <a className="hero-link hero-link-primary" href="#/">
              Back to welcome page
            </a>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="workbench-shell">
      <ActiveVerseHeader
        verseRef={unit?.ref ?? selectedVisualUnit?.ref ?? 'Loading verse'}
        hebrewText={unit?.source_hebrew ?? selectedVisualUnit?.source_hebrew ?? ''}
        transliteration={unit?.source_transliteration ?? null}
        progressText={`Verse ${currentUnitIndex >= 0 ? currentUnitIndex + 1 : 1} of ${Math.max(totalUnits, 1)}`}
        psalmProgressText={`${completedUnitCount} of ${totalUnits} completed`}
        completionState={currentCompletionState}
        wordCount={unit?.tokens.length ?? selectedVisualUnit?.tokens.length ?? 0}
        tokenCount={unit?.token_ids.length ?? selectedVisualUnit?.tokens.length ?? 0}
        startupNotice={showStartupDropdownNotice ? 'Loading project and Psalm data.' : null}
        selectorControls={(
          <div className="active-verse-selectors">
            <label className="compact-field">
              <span>Psalm</span>
              <select value={effectivePsalmId ?? ''} onChange={handlePsalmChange} disabled={showStartupDropdownNotice}>
                {showStartupDropdownNotice ? <option value="">Loading Psalms...</option> : null}
                {!showStartupDropdownNotice && selectablePsalms.length === 0 ? <option value="">No Psalms available</option> : null}
                {!showStartupDropdownNotice
                  ? selectablePsalms.map((psalm: Psalm) => (
                      <option key={psalm.psalm_id} value={psalm.psalm_id}>
                        {psalm.title}
                      </option>
                    ))
                  : null}
              </select>
            </label>
            <label className="compact-field">
              <span>Verse</span>
              <select value={selectedUnitId ?? ''} onChange={handleUnitChange} disabled={showStartupDropdownNotice || !currentPsalm?.unit_ids.length}>
                {showStartupDropdownNotice ? <option value="">Loading verses...</option> : null}
                {!showStartupDropdownNotice && !(currentPsalm?.unit_ids.length ?? 0) ? <option value="">No verses available</option> : null}
                {!showStartupDropdownNotice
                  ? currentPsalm?.unit_ids.map((unitIdOption) => (
                      <option key={unitIdOption} value={unitIdOption}>
                        {unitMap.get(unitIdOption)?.ref ?? unitIdOption}
                      </option>
                    ))
                  : null}
              </select>
            </label>
          </div>
        )}
      />
      <section className="translation-console" aria-label="Translation workbench">
        <section className="translation-pane translation-pane--flow compose-panel">
          <VerseFlowCloudPanel
            unit={unit}
            activeLayer={activeLayer}
            literalAidRenderings={literalAidRenderings}
            currentEnglishRenderings={currentEnglishRenderings}
            phraseAidRenderings={phraseAidRenderings}
            conceptAidRenderings={conceptAidRenderings}
            supportNodes={selectedVisualUnit?.supporting_nodes ?? []}
            allAlignments={unit?.alignments ?? []}
            activeCloudNode={activeCloudNode}
            retrievalHits={selectedUnitRetrievalHits}
            selectedTokenIds={selectedTokenIds}
            selectedSpanIds={selectedSpanIds}
            compareRightId={compareRightId}
            lexicalTokenCard={displayedTokenCard}
            currentWorkingChoices={currentWorkingChoices}
            currentWorkingPath={currentWorkingPath}
            currentCursorTokenIndex={currentCursorTokenIndex}
            currentVerseIndex={currentUnitIndex}
            totalVerses={totalUnits}
            verseNavigatorItems={(currentPsalm?.unit_ids ?? []).map((unitIdOption, index) => {
              const workingState = workingVerseByUnit[unitIdOption];
              const hasWork = Boolean(workingState?.sequence.length || workingState?.workingText.trim());
              return {
                unitId: unitIdOption,
                label: `${index + 1}`,
                active: unitIdOption === selectedUnitId,
                state: workingState?.completed ? 'approved' : hasWork ? 'in-progress' : 'not-started',
              };
            })}
            generatedLyricText={guidedDraftText}
            onApplyChoice={handleApplyWorkingChoice}
            onPreviewChoice={handlePreviewWorkingChoice}
            onClearPreview={handleClearWorkingChoicePreview}
            onHoverToken={(tokenIdToHover) => updateWorkbenchUi({ hoveredTokenId: tokenIdToHover })}
            onSetCursor={handleSetWorkingCursor}
            onGenerateLyric={handleGenerateStarter}
            onPreviousVerse={() => handleNavigateRelativeVerse(previousUnitId)}
            onNextVerse={() => handleCompleteVerse(true)}
            hasPreviousVerse={Boolean(previousUnitId)}
            hasNextVerse={canAdvanceToNextVerse}
            onSelectCloudNode={(nodeId) => setSelectedCloudNodeId((existing) => (existing === nodeId ? null : nodeId))}
          />
        </section>
        <ReviewWorkflowPanel
          unit={unit}
          refLabel={unit?.ref ?? (selectedVisualUnit?.ref ?? 'Select a verse')}
          activeLayer={activeLayer}
          selectableLayers={selectableLayers}
          selectedWorkflowLayer={selectedWorkflowLayer}
          layerNotice={selectedUnitLayerState.notice}
          workingText={currentWorkingText}
          workingPath={currentWorkingPath}
          referenceText={currentReferenceRendering?.text ?? null}
          renderings={currentEnglishRenderings}
          highlightedSpanIds={highlightedSpanIds}
          selectedSpanIds={selectedSpanIds}
          hoveredSpanId={hoveredSpanId}
          completedCount={completedUnitCount}
          totalUnits={totalUnits}
          currentIndex={currentUnitIndex}
          isCompleted={Boolean(currentUnitWorkingState?.completed)}
          isSaving={createRendering.isPending}
          isDirty={currentDirty}
          completionState={currentCompletionState}
          isVerseReadyToLock={currentVerseReadyToLock}
          canAdvanceToNextVerse={canAdvanceToNextVerse}
          chapterDraftItems={chapterDraftItems}
          returnToVerseRef={returnToVerseRef}
          message={guidedMessage}
          onReset={handleResetWorkingVerse}
          onComplete={() => handleCompleteVerse(false)}
          onCompleteAndNext={() => handleCompleteVerse(true)}
          onPreviousVerse={() => handleNavigateRelativeVerse(previousUnitId)}
          onNextVerse={() => handleNavigateRelativeVerse(nextUnitId)}
          onJumpToVerse={handleJumpToChapterVerse}
          onCatchUp={handleCatchUpToCurrent}
          hasPreviousVerse={Boolean(previousUnitId)}
          hasNextVerse={Boolean(nextUnitId)}
          onLayerChange={(layer) => updateWorkbenchSelection({ layer })}
          onSetCursor={handleSetWorkingCursor}
          onPreviewChoice={handlePreviewWorkingChoice}
          onClearPreview={handleClearWorkingChoicePreview}
          onHoverSpan={(spanId) => updateWorkbenchUi({ hoveredSpanId: spanId })}
          onToggleSpan={(spanId) => selectedUnitId ? handleToggleSpan(selectedUnitId, spanId) : undefined}
          onCompareLeft={(renderingId) => updateWorkbenchUi({ compareLeftId: renderingId })}
          onCompareRight={(renderingId) => updateWorkbenchUi({ compareRightId: renderingId })}
          onAcceptAlternate={handleAcceptAlternate}
          onPromoteAlternate={handlePromoteAlternate}
          onDeprecateAlternate={handleDeprecateAlternate}
          onRejectAlternate={handleRejectAlternate}
          onDemote={(renderingId) => demoteRendering.mutate(renderingId)}
        >
          {assistantUi.placement === 'side' ? <AssistantPanel embedded /> : null}
        </ReviewWorkflowPanel>
      </section>
      <BottomDrawer
        unit={unit}
        concerns={concerns}
        tokenCard={displayedTokenCard}
        concordanceSeed={displayedTokenCard?.lemma ?? undefined}
        tab={workbenchUi.drawerTab}
        onTabChange={(tab) => updateWorkbenchUi({ drawerTab: tab })}
        onNavigateToUnit={handleNavigateToUnit}
        activeLayer={activeLayer}
        resolvedLayer={selectedUnitLayerState.renderLayer}
        layerNotice={selectedUnitLayerState.notice}
        selectableLayers={selectableLayers}
        selectedTokenIds={selectedTokenIds}
        selectedSpanIds={selectedSpanIds}
        selectedAlignmentId={selectedAlignmentId}
        onSelectedAlignmentChange={(alignmentId) => updateWorkbenchUi({ selectedAlignmentId: alignmentId })}
        onClearAlignmentSelection={clearWorkbenchSelections}
        compareLeftId={compareLeftId}
        compareRightId={compareRightId}
        onCompareLeftChange={(renderingId) => updateWorkbenchUi({ compareLeftId: renderingId })}
        onCompareRightChange={(renderingId) => updateWorkbenchUi({ compareRightId: renderingId })}
      />
    </main>
  );
}

function ActiveVerseHeader({
  verseRef,
  hebrewText,
  transliteration,
  progressText,
  psalmProgressText,
  completionState,
  wordCount,
  tokenCount,
  startupNotice,
  selectorControls,
}: {
  verseRef: string;
  hebrewText: string;
  transliteration: string | null;
  progressText: string;
  psalmProgressText: string;
  completionState: string;
  wordCount: number;
  tokenCount: number;
  startupNotice: string | null;
  selectorControls?: ReactNode;
}) {
  return (
    <header className="active-verse-header">
      <div className="active-verse-header__main">
        <div className="horizontal-between active-verse-header__meta">
          <div>
            <p className="eyebrow">Active Verse</p>
            <h1>{verseRef}</h1>
          </div>
          <div className="active-verse-header__right">
            {selectorControls}
            <div className="tag-row">
              <span className="tag">{progressText}</span>
              <span className="tag">{psalmProgressText}</span>
              <span className="tag">{completionState}</span>
              <span className="tag">{wordCount} word(s)</span>
              <span className="tag">{tokenCount} token(s)</span>
            </div>
          </div>
        </div>
        <p className="active-verse-header__hebrew" dir="rtl">{hebrewText || 'Loading Hebrew source...'}</p>
        {transliteration ? <p className="active-verse-header__transliteration">{transliteration}</p> : null}
        {startupNotice ? <p className="startup-notice" role="status" aria-live="polite">{startupNotice}</p> : null}
      </div>
    </header>
  );
}

function ReviewWorkflowPanel({
  unit,
  refLabel,
  activeLayer,
  selectableLayers,
  selectedWorkflowLayer,
  layerNotice,
  workingText,
  workingPath,
  referenceText,
  renderings,
  highlightedSpanIds,
  selectedSpanIds,
  hoveredSpanId,
  completedCount,
  totalUnits,
  currentIndex,
  isCompleted,
  isSaving,
  isDirty,
  completionState,
  isVerseReadyToLock,
  canAdvanceToNextVerse,
  chapterDraftItems,
  returnToVerseRef,
  message,
  children,
  onReset,
  onComplete,
  onCompleteAndNext,
  onPreviousVerse,
  onNextVerse,
  onJumpToVerse,
  onCatchUp,
  hasPreviousVerse,
  hasNextVerse,
  onLayerChange,
  onSetCursor,
  onPreviewChoice,
  onClearPreview,
  onHoverSpan,
  onToggleSpan,
  onCompareLeft,
  onCompareRight,
  onAcceptAlternate,
  onPromoteAlternate,
  onDeprecateAlternate,
  onRejectAlternate,
  onDemote,
}: {
  unit?: Unit;
  refLabel: string;
  activeLayer: Layer;
  selectableLayers: Layer[];
  selectedWorkflowLayer: Layer;
  layerNotice: string | null;
  workingText: string;
  workingPath: WorkingVerseSegment[];
  referenceText: string | null;
  renderings: Rendering[];
  highlightedSpanIds: string[];
  selectedSpanIds: string[];
  hoveredSpanId: string | null;
  completedCount: number;
  totalUnits: number;
  currentIndex: number;
  isCompleted: boolean;
  isSaving: boolean;
  isDirty: boolean;
  completionState: string;
  isVerseReadyToLock: boolean;
  canAdvanceToNextVerse: boolean;
  chapterDraftItems: ChapterDraftItem[];
  returnToVerseRef: string | null;
  message: string | null;
  children?: ReactNode;
  onReset: () => void;
  onComplete: () => void;
  onCompleteAndNext: () => void;
  onPreviousVerse: () => void;
  onNextVerse: () => void;
  onJumpToVerse: (unitId: string) => void;
  onCatchUp: () => void;
  hasPreviousVerse: boolean;
  hasNextVerse: boolean;
  onLayerChange: (layer: Layer) => void;
  onSetCursor: (tokenIndex: number) => void;
  onPreviewChoice: (choice: ComposerChoice | null) => void;
  onClearPreview: () => void;
  onHoverSpan: (spanId: string | null) => void;
  onToggleSpan: (spanId: string) => void;
  onCompareLeft: (renderingId: string) => void;
  onCompareRight: (renderingId: string) => void;
  onAcceptAlternate: (renderingId: string) => void;
  onPromoteAlternate: (renderingId: string) => void;
  onDeprecateAlternate: (renderingId: string) => void;
  onRejectAlternate: (renderingId: string) => void;
  onDemote: (renderingId: string) => void;
}) {
  const progressPercent = totalUnits > 0 ? Math.round((completedCount / totalUnits) * 100) : 0;
  const draftedLineCount = chapterDraftItems.filter((item) => item.text.trim().length > 0).length;

  return (
    <section className="translation-pane translation-pane--output">
      <header className="pane-header translation-pane__header">
        <div>
          <p className="eyebrow">Review Workflow</p>
          <h2>{refLabel}</h2>
        </div>
        <div className="tag-row">
          <span className="tag">{completionState}</span>
          <span className="tag">verse {currentIndex >= 0 ? currentIndex + 1 : 1} / {Math.max(totalUnits, 1)}</span>
          {isDirty ? <span className="tag warning">unsaved</span> : null}
        </div>
      </header>

      {unit ? (
        <div className="rendered-output-grid">
          <label className="compact-field workflow-layer-field">
            <span>Workflow layer</span>
            <select value={selectedWorkflowLayer} onChange={(event) => onLayerChange(event.target.value as Layer)}>
              {selectableLayers.map((layer) => (
                <option key={layer} value={layer}>
                  {layer}
                </option>
              ))}
            </select>
          </label>

          <section className="output-live-panel chapter-draft-panel">
            <div className="horizontal-between">
              <strong>Chapter draft</strong>
              <div className="inline-actions">
                <span className="subtle">{draftedLineCount} of {Math.max(totalUnits, 1)} drafted</span>
                {returnToVerseRef ? (
                  <button type="button" className="tab" onClick={onCatchUp}>
                    Catch up to {returnToVerseRef}
                  </button>
                ) : null}
              </div>
            </div>
            <div className="chapter-draft-list" aria-label="Psalm draft by verse">
              {chapterDraftItems.map((item) => (
                <article
                  key={item.unitId}
                  className={`chapter-draft-verse chapter-draft-verse--${item.completionState} ${item.active ? 'active' : ''}`}
                >
                  <div className="horizontal-between">
                    <button type="button" className="chapter-draft-ref" onClick={() => onJumpToVerse(item.unitId)}>
                      {item.refLabel}
                    </button>
                    <div className="tag-row">
                      <span className="tag">{item.active ? 'current' : item.completionState.replace('-', ' ')}</span>
                    </div>
                  </div>
                  {item.words.length > 0 ? (
                    <div className="chapter-draft-words">
                      {item.words.map((word, index) => (
                        <button
                          key={`${item.unitId}:${index}:${word}`}
                          type="button"
                          className="chapter-draft-word"
                          onClick={() => onJumpToVerse(item.unitId)}
                        >
                          {word}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <button type="button" className="chapter-draft-empty" onClick={() => onJumpToVerse(item.unitId)}>
                      Start verse {item.verseNumber}
                    </button>
                  )}
                </article>
              ))}
            </div>
            <p className="output-live-text chapter-draft-current-line">{workingText || 'Choose from the flow rows to start building this verse.'}</p>
            {referenceText ? <p className="subtle">Current saved reference: {referenceText}</p> : null}
            {layerNotice ? <p className="subtle">{layerNotice}</p> : null}
          </section>

          <section className="output-path-panel">
            <div className="horizontal-between">
              <strong>Selected path</strong>
              <span className="subtle">Click a chip to move the cursor back</span>
            </div>
            {workingPath.length > 0 ? (
              <div className="composer-path-row">
                {workingPath.map(({ level, choice }, index) => (
                  <button
                    key={`${level}:${choice.id}:${index}`}
                    type="button"
                    className={`composer-path-chip composer-path-chip--${level}`}
                    onClick={() => onSetCursor(choice.tokenStart ?? 0)}
                    onMouseEnter={() => onPreviewChoice(choice)}
                    onMouseLeave={onClearPreview}
                  >
                    {level === 'idea' ? 'concept' : level}: {choice.label}
                  </button>
                ))}
              </div>
            ) : (
              <p className="empty-state">No selections yet. Start with a word, phrase, or concept bubble.</p>
            )}
          </section>

          <section className="verse-status-panel">
            <div className="horizontal-between">
              <strong>Verse status</strong>
              <span className="subtle">{renderings.length} candidate(s)</span>
            </div>
            <div className="tag-row">
              <span className="tag">{completionState}</span>
              <span className="tag">{isVerseReadyToLock || isCompleted ? 'coverage complete' : 'coverage incomplete'}</span>
              <span className="tag">{isDirty ? 'unsaved changes' : 'saved/reference aligned'}</span>
              <span className="tag">
                approval: {renderings.some((rendering) => rendering.status === 'canonical')
                  ? 'canonical'
                  : renderings.some((rendering) => rendering.status === 'accepted')
                    ? 'accepted'
                    : 'pending'}
              </span>
            </div>
          </section>

          <section className="psalm-progress-card output-progress-panel">
            <div className="horizontal-between">
              <strong>Psalm progress</strong>
              <span className="subtle">{completedCount} of {totalUnits} completed</span>
            </div>
            <div className="psalm-progress-bar" aria-hidden="true">
              <span style={{ width: `${progressPercent}%` }} />
            </div>
          </section>

          <section className="output-saved-panel">
            <div className="horizontal-between">
              <strong>Saved renderings</strong>
              <span className="subtle">{renderings.length} candidate(s)</span>
            </div>
            {renderings.length > 0 ? (
              <div className="rendering-list">
                {renderings.map((rendering) => (
                  <article key={rendering.rendering_id} className="rendering-card">
                    <div className="horizontal-between">
                      <strong>{rendering.layer}</strong>
                      <span className="subtle">{rendering.status}</span>
                    </div>
                    <p className="rendering-text">{rendering.text}</p>
                    <div className="rendering-span-row" aria-label={`Rendering spans for ${rendering.rendering_id}`}>
                      {rendering.target_spans.map((span: RenderingSpan) => {
                        const linked = highlightedSpanIds.includes(span.span_id);
                        const spanSelected = selectedSpanIds.includes(span.span_id);
                        const active = hoveredSpanId === span.span_id;
                        return (
                          <button
                            key={span.span_id}
                            type="button"
                            className={`rendering-span ${linked ? 'linked' : ''} ${spanSelected ? 'selected' : ''} ${active ? 'active' : ''}`}
                            onMouseEnter={() => onHoverSpan(span.span_id)}
                            onMouseLeave={() => onHoverSpan(null)}
                            onClick={() => onToggleSpan(span.span_id)}
                            aria-pressed={spanSelected}
                          >
                            {span.text}
                          </button>
                        );
                      })}
                    </div>
                    <div className="inline-actions">
                      <button type="button" className="tab" onClick={() => onCompareLeft(rendering.rendering_id)}>
                        Compare left
                      </button>
                      <button type="button" className="tab" onClick={() => onCompareRight(rendering.rendering_id)}>
                        Compare right
                      </button>
                      {rendering.status === 'canonical' ? (
                        <button type="button" className="tab" onClick={() => onDemote(rendering.rendering_id)}>
                          Demote
                        </button>
                      ) : (
                        <>
                          <button type="button" className="tab" onClick={() => onAcceptAlternate(rendering.rendering_id)}>
                            Accept
                          </button>
                          <button type="button" className="tab" onClick={() => onPromoteAlternate(rendering.rendering_id)}>
                            Promote
                          </button>
                          <button type="button" className="tab" onClick={() => onDeprecateAlternate(rendering.rendering_id)}>
                            Deprecate
                          </button>
                          <button type="button" className="tab" onClick={() => onRejectAlternate(rendering.rendering_id)}>
                            Reject
                          </button>
                        </>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-state">No saved rendered layer yet. Complete the verse to save this output.</p>
            )}
          </section>

          <section className="verse-workflow-controls">
            <strong>Verse workflow</strong>
            <div className="inline-actions output-actions">
              <button type="button" className="tab" onClick={onPreviousVerse} disabled={!hasPreviousVerse || isSaving}>
                Previous verse
              </button>
              <button type="button" className="tab" onClick={onNextVerse} disabled={!hasNextVerse || isSaving || !isCompleted}>
                Next verse
              </button>
              {returnToVerseRef ? (
                <button type="button" className="tab" onClick={onCatchUp}>
                  Catch up
                </button>
              ) : null}
            </div>
            <div className="inline-actions output-actions">
              <button type="button" className="tab" onClick={onComplete} disabled={isSaving || !isVerseReadyToLock}>
                {isSaving ? 'Saving...' : isCompleted ? 'Locked' : 'Lock verse'}
              </button>
              <button type="button" className="tab tab--primary" onClick={onCompleteAndNext} disabled={isSaving || !canAdvanceToNextVerse}>
                {isSaving ? 'Saving...' : 'Lock verse and next'}
              </button>
            </div>
            <div className="inline-actions output-actions">
              <button type="button" className="tab" onClick={onReset} disabled={isSaving}>
                Reset verse
              </button>
            </div>
          </section>

          {message ? <p className="subtle">{message}</p> : null}
          {children}
        </div>
      ) : (
        <p className="empty-state">Select a verse to view the rendered English output.</p>
      )}
    </section>
  );
}

function GuidedDecisionPanel({
  unit,
  activeLayer,
  resolvedLayer,
  layerNotice,
  renderings,
  phraseAidRenderings,
  conceptAidRenderings,
  literalAidRenderings,
  supportNodes,
  activeCloudNode,
  retrievalHits,
  tokenCard,
  focusedToken,
  concerns,
  guidedDraftText,
  guidedMessage,
  isSaving,
  isGenerating,
  onDraftTextChange,
  onSave,
  onGenerate,
  onSelectToken,
  onOpenConcordance,
  onSelectCloudNode,
  onClearCloudNode,
  onCompareLeft,
  onCompareRight,
  onPromoteAlternate,
  onAcceptAlternate,
  onDeprecateAlternate,
  onRejectAlternate,
  onDemote,
  onUnpinToken,
}: {
  unit?: Unit;
  activeLayer: Layer;
  resolvedLayer: Layer | null;
  layerNotice: string | null;
  renderings: Rendering[];
  phraseAidRenderings: Rendering[];
  conceptAidRenderings: Rendering[];
  literalAidRenderings: Rendering[];
  supportNodes: CloudNode[];
  activeCloudNode: CloudNode | null;
  retrievalHits: RetrievalHit[];
  tokenCard?: TokenCard;
  focusedToken: Token | null;
  concerns?: OpenConcerns;
  guidedDraftText: string;
  guidedMessage: string | null;
  isSaving: boolean;
  isGenerating: boolean;
  onDraftTextChange: (value: string) => void;
  onSave: () => void;
  onGenerate: () => void;
  onSelectToken: (tokenId: string) => void;
  onOpenConcordance: () => void;
  onSelectCloudNode: (nodeId: string) => void;
  onClearCloudNode: () => void;
  onCompareLeft: (renderingId: string) => void;
  onCompareRight: (renderingId: string) => void;
  onPromoteAlternate: (renderingId: string) => void;
  onAcceptAlternate: (renderingId: string) => void;
  onDeprecateAlternate: (renderingId: string) => void;
  onRejectAlternate: (renderingId: string) => void;
  onDemote: (renderingId: string) => void;
  onUnpinToken: () => void;
}) {
  const primaryRendering = renderings[0] ?? literalAidRenderings[0] ?? phraseAidRenderings[0] ?? null;
  const alternateCandidates = renderings.filter((rendering) => rendering.rendering_id !== primaryRendering?.rendering_id);
  const unresolvedWarnings = (concerns?.open_drift_flags.filter((flag: { unit_id: string }) => flag.unit_id === unit?.unit_id).length ?? 0)
    + (concerns?.uncovered_tokens.filter((flag: { unit_id: string }) => flag.unit_id === unit?.unit_id).length ?? 0)
    + (concerns?.unaligned_spans.filter((flag: { unit_id: string }) => flag.unit_id === unit?.unit_id).length ?? 0);

  return (
    <aside className="inspector-rail guided-decision-panel">
      <section className="inspector-card guided-decision-card guided-decision-card--primary">
        <div className="horizontal-between">
          <div>
            <p className="eyebrow">Guided translation</p>
            <h3>{unit?.ref ?? 'Select a unit to translate'}</h3>
            <p className="subtle">
              Make the translation decision here. Use the word, phrase, concept, and Strong&apos;s-based references below as aids.
            </p>
          </div>
          <div className="tag-row">
            <span className="tag">Target layer: {activeLayer}</span>
            {resolvedLayer && resolvedLayer !== activeLayer ? <span className="tag">Showing {resolvedLayer} support</span> : null}
          </div>
        </div>

        {unit ? (
          <>
            <div className="guided-source-card">
              <strong>Source</strong>
              <p dir="rtl" className="guided-source-card__hebrew">{unit.source_hebrew}</p>
              {unit.source_transliteration ? <p className="subtle">{unit.source_transliteration}</p> : null}
              {layerNotice ? <p className="subtle">{layerNotice}</p> : null}
            </div>

            {primaryRendering ? (
              <div className="guided-rendering-focus">
                <div className="horizontal-between">
                  <div>
                    <strong>Current decision candidate</strong>
                    <p className="subtle">
                      {primaryRendering.status === 'canonical'
                        ? 'This is the current canonical rendering.'
                        : 'Review this draft and decide whether to accept, promote, or revise it.'}
                    </p>
                  </div>
                  <span className="tag">{primaryRendering.layer} · {primaryRendering.status}</span>
                </div>
                <p className="guided-rendering-focus__text">{primaryRendering.text}</p>
                {primaryRendering.rationale ? <p className="subtle">{primaryRendering.rationale}</p> : null}
                <div className="inline-actions">
                  <button type="button" className="tab" onClick={() => onCompareLeft(primaryRendering.rendering_id)}>
                    Compare left
                  </button>
                  <button type="button" className="tab" onClick={() => onCompareRight(primaryRendering.rendering_id)}>
                    Compare right
                  </button>
                  {primaryRendering.status === 'canonical' ? (
                    <button type="button" className="tab" onClick={() => onDemote(primaryRendering.rendering_id)}>
                      Demote canonical
                    </button>
                  ) : (
                    <>
                      <button type="button" className="tab" onClick={() => onAcceptAlternate(primaryRendering.rendering_id)}>
                        Accept draft
                      </button>
                      <button type="button" className="tab" onClick={() => onPromoteAlternate(primaryRendering.rendering_id)}>
                        Promote to canonical
                      </button>
                      <button type="button" className="tab" onClick={() => onDeprecateAlternate(primaryRendering.rendering_id)}>
                        Deprecate
                      </button>
                      <button type="button" className="tab" onClick={() => onRejectAlternate(primaryRendering.rendering_id)}>
                        Reject
                      </button>
                    </>
                  )}
                </div>
              </div>
            ) : null}

            <GuidedTranslationCard
              layer={activeLayer}
              refLabel={unit.ref}
              sourceText={unit.source_hebrew}
              transliteration={unit.source_transliteration ?? null}
              draftText={guidedDraftText}
              message={guidedMessage}
              isSaving={isSaving}
              isGenerating={isGenerating}
              onDraftTextChange={onDraftTextChange}
              onSave={onSave}
              onGenerate={onGenerate}
            />

            {alternateCandidates.length > 0 ? (
              <section className="guided-aid-section">
                <div className="horizontal-between">
                  <strong>Other decision candidates</strong>
                  <span className="subtle">{alternateCandidates.length} additional rendering(s)</span>
                </div>
                <div className="candidate-stack">
                  {alternateCandidates.slice(0, 3).map((rendering) => (
                    <article key={rendering.rendering_id} className="candidate-card">
                      <div className="horizontal-between">
                        <span className="tag">{rendering.layer} · {rendering.status}</span>
                        <button type="button" className="link-button" onClick={() => onCompareRight(rendering.rendering_id)}>
                          Compare
                        </button>
                      </div>
                      <p>{rendering.text}</p>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            <section className="guided-aid-section">
              <div className="horizontal-between">
                <strong>Word aids</strong>
                <div className="inline-actions">
                  <button type="button" className="tab" onClick={onOpenConcordance}>
                    Open concordance
                  </button>
                  {tokenCard ? (
                    <button type="button" className="tab" onClick={onUnpinToken}>
                      Unpin token
                    </button>
                  ) : null}
                </div>
              </div>
              <div className="word-aid-grid" dir="rtl">
                {unit.tokens.map((token: Token) => (
                  <button key={token.token_id} type="button" className={`word-aid-chip ${focusedToken?.token_id === token.token_id ? 'active' : ''}`} onClick={() => onSelectToken(token.token_id)}>
                    <span className="surface">{token.surface}</span>
                    <small>{token.transliteration ?? token.token_id}</small>
                    {token.strong ? <small>Strong&apos;s {token.strong}</small> : null}
                  </button>
                ))}
              </div>
              <div className="guided-token-detail">
                <div>
                  <strong>{tokenCard?.surface ?? focusedToken?.surface ?? 'Select a Hebrew word'}</strong>
                  <p className="subtle">
                    {tokenCard?.copy_reference ?? focusedToken?.ref ?? 'Pick a token to inspect Strong’s, glosses, and usage references.'}
                  </p>
                </div>
                <dl className="detail-grid">
                  <dt>Lemma</dt>
                  <dd>{tokenCard?.lemma ?? focusedToken?.lemma ?? '—'}</dd>
                  <dt>Strong&apos;s</dt>
                  <dd>{tokenCard?.strong ?? focusedToken?.strong ?? '—'}</dd>
                  <dt>Glosses</dt>
                  <dd>{tokenCard?.gloss_list.join(', ') || focusedToken?.word_sense || '—'}</dd>
                  <dt>Morphology</dt>
                  <dd>{tokenCard?.morph_readable ?? focusedToken?.morph_readable ?? '—'}</dd>
                  <dt>Syntax</dt>
                  <dd>{tokenCard?.syntax_role ?? focusedToken?.syntax_role ?? '—'}</dd>
                  <dt>Semantic</dt>
                  <dd>{tokenCard?.semantic_role ?? focusedToken?.semantic_role ?? '—'}</dd>
                </dl>
                {(tokenCard?.nearby_usage_examples.length ?? 0) > 0 ? (
                  <ul className="simple-list compact-list">
                    {tokenCard?.nearby_usage_examples.slice(0, 4).map((example) => <li key={example}>{example}</li>)}
                  </ul>
                ) : null}
              </div>
            </section>

            <section className="guided-aid-section">
              <strong>Phrase aids</strong>
              {phraseAidRenderings.length > 0 ? (
                <div className="candidate-stack">
                  {phraseAidRenderings.slice(0, 3).map((rendering) => (
                    <article key={rendering.rendering_id} className="candidate-card">
                      <div className="horizontal-between">
                        <span className="tag">{rendering.status}</span>
                        <button type="button" className="link-button" onClick={() => onCompareRight(rendering.rendering_id)}>
                          Compare
                        </button>
                      </div>
                      <p>{rendering.text}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="empty-state">No saved phrase-level aids yet for this unit.</p>
              )}
            </section>

            <section className="guided-aid-section">
              <strong>Concept aids</strong>
              <div className="tag-row">
                {supportNodes.filter((node) => node.kind === 'concept').map((node) => (
                  <button key={node.node_id} type="button" className={`tag support-tag ${activeCloudNode?.node_id === node.node_id ? 'active' : ''}`} onClick={() => onSelectCloudNode(node.node_id)}>
                    {node.label}
                  </button>
                ))}
                {supportNodes.filter((node) => node.kind === 'concept').length === 0 && conceptAidRenderings.length === 0 ? (
                  <span className="empty-state">No concept aids available.</span>
                ) : null}
              </div>
              {conceptAidRenderings.length > 0 ? (
                <div className="candidate-stack">
                  {conceptAidRenderings.slice(0, 2).map((rendering) => (
                    <article key={rendering.rendering_id} className="candidate-card">
                      <span className="tag">{rendering.status}</span>
                      <p>{rendering.text}</p>
                    </article>
                  ))}
                </div>
              ) : null}
            </section>

            <section className="guided-aid-section">
              <div className="horizontal-between">
                <strong>Context references</strong>
                {activeCloudNode ? (
                  <button type="button" className="tab" onClick={onClearCloudNode}>
                    Clear reference filter
                  </button>
                ) : null}
              </div>
              <div className="tag-row">
                {supportNodes.slice(0, 6).map((node) => (
                  <button key={node.node_id} type="button" className={`tag support-tag ${activeCloudNode?.node_id === node.node_id ? 'active' : ''}`} onClick={() => onSelectCloudNode(node.node_id)}>
                    {node.kind}: {node.label}
                  </button>
                ))}
              </div>
              {retrievalHits.length > 0 ? (
                <div className="retrieval-stack">
                  {retrievalHits.slice(0, 4).map((hit) => (
                    <RetrievedHit key={hit.hit_id} hit={hit} onCompare={onCompareRight} />
                  ))}
                </div>
              ) : (
                <p className="empty-state">
                  Select a phrase or concept reference to see related same-Psalm and cross-Psalm support here.
                </p>
              )}
            </section>

            <section className="guided-aid-section">
              <strong>Translation support summary</strong>
              <div className="tag-row">
                <span className="tag">Saved {activeLayer} renderings: {renderings.length}</span>
                <span className="tag">Literal/gloss aids: {literalAidRenderings.length}</span>
                <span className="tag">Warnings: {unresolvedWarnings}</span>
              </div>
            </section>
          </>
        ) : (
          <p className="empty-state">Select a unit to open the guided translation panel.</p>
        )}
      </section>
    </aside>
  );
}

function GuidedVerseComposerCard({
  refLabel,
  activeLayer,
  sourceText,
  transliteration,
  workingText,
  workingPath,
  referenceText,
  completedCount,
  totalUnits,
  currentIndex,
  isCompleted,
  isSaving,
  message,
  onReset,
  onComplete,
}: {
  refLabel: string;
  activeLayer: Layer;
  sourceText: string;
  transliteration: string | null;
  workingText: string;
  workingPath: Array<{ level: ComposerChoiceLevel; choice: ComposerChoice }>;
  referenceText: string | null;
  completedCount: number;
  totalUnits: number;
  currentIndex: number;
  isCompleted: boolean;
  isSaving: boolean;
  message: string | null;
  onReset: () => void;
  onComplete: () => void;
}) {
  const progressPercent = totalUnits > 0 ? Math.round((completedCount / totalUnits) * 100) : 0;

  return (
    <section className="guided-verse-composer">
      <div className="horizontal-between">
        <div>
          <p className="eyebrow">Current working verse</p>
          <h3>{refLabel}</h3>
          <p className="subtle">Pick bubbles on the right to build this verse, then complete it and move to the next unit.</p>
        </div>
        <div className="tag-row">
          <span className="tag">layer: {activeLayer}</span>
          <span className="tag">verse {currentIndex >= 0 ? currentIndex + 1 : 1} / {Math.max(totalUnits, 1)}</span>
          {isCompleted ? <span className="tag">completed</span> : null}
        </div>
      </div>

      <div className="guided-translation-source">
        <strong>Hebrew source</strong>
        <p dir="rtl">{sourceText}</p>
        {transliteration ? <p className="subtle">{transliteration}</p> : null}
      </div>

      <div className="psalm-progress-card">
        <div className="horizontal-between">
          <strong>Psalm progress</strong>
          <span className="subtle">{completedCount} of {totalUnits} completed</span>
        </div>
        <div className="psalm-progress-bar" aria-hidden="true">
          <span style={{ width: `${progressPercent}%` }} />
        </div>
      </div>

      <div className="working-verse-card">
        <div className="horizontal-between">
          <strong>Working verse translation</strong>
          {referenceText ? <span className="subtle">Reference available below</span> : null}
        </div>
        <p className="working-verse-card__text">{workingText || 'Choose from the word / phrase / idea / lyric rows to start building this verse.'}</p>
        {referenceText ? (
          <p className="subtle">Current saved/reference text: {referenceText}</p>
        ) : null}
      </div>

      <div className="composer-path-card">
        <strong>Selected path</strong>
        {workingPath.length > 0 ? (
          <div className="composer-path-row">
            {workingPath.map(({ level, choice }) => (
              <span key={`${level}:${choice.id}`} className={`composer-path-chip composer-path-chip--${level}`}>
                {level}: {choice.label}
              </span>
            ))}
          </div>
        ) : (
          <p className="empty-state">No selections yet. Start with a word or phrase choice on the right.</p>
        )}
      </div>

      <div className="inline-actions">
        <button type="button" className="tab" onClick={onReset} disabled={isSaving}>
          Reset verse
        </button>
        <button type="button" className="tab" onClick={onComplete} disabled={isSaving || workingText.trim().length === 0}>
          {isSaving ? 'Saving…' : isCompleted ? 'Completed' : 'Complete verse & next'}
        </button>
      </div>

      {message ? <p className="subtle">{message}</p> : null}
    </section>
  );
}

function WorkingVersePreviewCard({
  refLabel,
  activeLayer,
  workingText,
  referenceText,
  workingPath,
  message,
}: {
  refLabel: string;
  activeLayer: Layer;
  workingText: string;
  referenceText: string | null;
  workingPath: Array<{ level: ComposerChoiceLevel; choice: ComposerChoice }>;
  message: string | null;
}) {
  return (
    <section className="guided-verse-composer guided-verse-composer--preview">
      <div className="horizontal-between">
        <div>
          <p className="eyebrow">Live verse preview</p>
          <h3>{refLabel}</h3>
          <p className="subtle">The right rail is the guided composer. This middle panel previews the verse being assembled.</p>
        </div>
        <span className="tag">layer: {activeLayer}</span>
      </div>

      <div className="working-verse-card">
        <div className="horizontal-between">
          <strong>Preview text</strong>
          {referenceText ? <span className="subtle">Saved reference available</span> : null}
        </div>
        <p className="working-verse-card__text">{workingText || 'Choose options from the guided composer on the right.'}</p>
        {referenceText ? <p className="subtle">Reference text: {referenceText}</p> : null}
      </div>

      <div className="composer-path-card">
        <strong>Current selected path</strong>
        {workingPath.length > 0 ? (
          <div className="composer-path-row">
            {workingPath.map(({ level, choice }) => (
              <span key={`${level}:${choice.id}`} className={`composer-path-chip composer-path-chip--${level}`}>
                {level}: {choice.label}
              </span>
            ))}
          </div>
        ) : (
          <p className="empty-state">No selections yet. Use the right rail to start building.</p>
        )}
      </div>

      {message ? <p className="subtle">{message}</p> : null}
    </section>
  );
}

function GuidedTranslationCard({
  layer,
  refLabel,
  sourceText,
  transliteration,
  draftText,
  message,
  isSaving,
  isGenerating,
  onDraftTextChange,
  onSave,
  onGenerate,
}: {
  layer: Layer;
  refLabel: string;
  sourceText: string;
  transliteration: string | null;
  draftText: string;
  message: string | null;
  isSaving: boolean;
  isGenerating: boolean;
  onDraftTextChange: (value: string) => void;
  onSave: () => void;
  onGenerate: () => void;
}) {
  return (
    <section className="guided-translation-card">
      <div className="horizontal-between">
        <div>
          <strong>Guided translation</strong>
          <p className="subtle">
            {refLabel} has no saved {layer} rendering yet. Draft one here or generate a starter.
          </p>
        </div>
        <span className="tag">layer: {layer}</span>
      </div>
      <div className="guided-translation-source">
        <strong>Hebrew source</strong>
        <p dir="rtl">{sourceText}</p>
        {transliteration ? <p className="subtle">{transliteration}</p> : null}
      </div>
      <label className="guided-translation-field">
        <span>Draft translation</span>
        <textarea
          value={draftText}
          onChange={(event) => onDraftTextChange(event.target.value)}
          placeholder={`Draft a ${layer} rendering for ${refLabel}`}
          rows={4}
        />
      </label>
      <div className="inline-actions">
        <button type="button" className="tab" onClick={onGenerate} disabled={isGenerating || isSaving}>
          {isGenerating ? 'Generating…' : 'Generate starter'}
        </button>
        <button type="button" className="tab" onClick={onSave} disabled={isSaving || draftText.trim().length === 0}>
          {isSaving ? 'Saving…' : 'Save proposed draft'}
        </button>
      </div>
      {message ? <p className="subtle">{message}</p> : null}
    </section>
  );
}

function ClickApprovalFallback({
  layer,
  refLabel,
  sourceText,
  transliteration,
  message,
  suggestions,
  isSaving,
  isGenerating,
  onApproveSuggestion,
  onGenerate,
  onCompareSuggestion,
}: {
  layer: Layer;
  refLabel: string;
  sourceText: string;
  transliteration: string | null;
  message: string | null;
  suggestions: Array<{
    id: string;
    text: string;
    source: string;
    tone: 'generated' | 'word' | 'phrase' | 'idea' | 'lyric';
    renderingId?: string;
  }>;
  isSaving: boolean;
  isGenerating: boolean;
  onApproveSuggestion: (text: string, source: string) => void;
  onGenerate: () => void;
  onCompareSuggestion: (renderingId: string) => void;
}) {
  return (
    <section className="click-approval-panel">
      <div className="horizontal-between">
        <div>
          <strong>Click-only approval</strong>
          <p className="subtle">
            {refLabel} has no saved {layer} rendering yet. Choose a suggestion below or generate new options — no typing required.
          </p>
        </div>
        <span className="tag">layer: {layer}</span>
      </div>

      <div className="guided-translation-source">
        <strong>Hebrew source</strong>
        <p dir="rtl">{sourceText}</p>
        {transliteration ? <p className="subtle">{transliteration}</p> : null}
      </div>

      <div className="inline-actions">
        <button type="button" className="tab" onClick={onGenerate} disabled={isGenerating || isSaving}>
          {isGenerating ? 'Generating…' : 'Generate click options'}
        </button>
      </div>

      {suggestions.length > 0 ? (
        <div className="click-approval-grid">
          {suggestions.map((suggestion) => (
            <article key={suggestion.id} className={`click-approval-card click-approval-card--${suggestion.tone}`}>
              <div className="horizontal-between">
                <span className="tag">{suggestion.source}</span>
                {suggestion.renderingId ? (
                  <button type="button" className="link-button" onClick={() => onCompareSuggestion(suggestion.renderingId!)}>
                    Compare
                  </button>
                ) : null}
              </div>
              <p>{suggestion.text}</p>
              <div className="inline-actions">
                <button
                  type="button"
                  className="tab"
                  onClick={() => onApproveSuggestion(suggestion.text, suggestion.source)}
                  disabled={isSaving}
                >
                  {isSaving ? 'Saving…' : 'Approve this wording'}
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-state">Generate options to turn the existing aids into click-only approval choices.</p>
      )}

      {message ? <p className="subtle">{message}</p> : null}
    </section>
  );
}

function VerseFlowCloudPanel({
  unit,
  activeLayer,
  literalAidRenderings,
  currentEnglishRenderings,
  phraseAidRenderings,
  conceptAidRenderings,
  supportNodes,
  allAlignments,
  activeCloudNode,
  retrievalHits,
  selectedTokenIds,
  selectedSpanIds,
  compareRightId,
  lexicalTokenCard,
  currentWorkingChoices,
  currentWorkingPath,
  currentCursorTokenIndex,
  currentVerseIndex,
  totalVerses,
  verseNavigatorItems,
  generatedLyricText,
  onApplyChoice,
  onPreviewChoice,
  onClearPreview,
  onHoverToken,
  onSetCursor,
  onGenerateLyric,
  onPreviousVerse,
  onNextVerse,
  hasPreviousVerse,
  hasNextVerse,
  onSelectCloudNode,
}: {
  unit?: Unit;
  activeLayer: Layer;
  literalAidRenderings: Rendering[];
  currentEnglishRenderings: Rendering[];
  phraseAidRenderings: Rendering[];
  conceptAidRenderings: Rendering[];
  supportNodes: CloudNode[];
  allAlignments: Alignment[];
  activeCloudNode: CloudNode | null;
  retrievalHits: RetrievalHit[];
  selectedTokenIds: string[];
  selectedSpanIds: string[];
  compareRightId: string | null;
  lexicalTokenCard?: TokenCard;
  currentWorkingChoices: Partial<Record<ComposerChoiceLevel, ComposerChoice>>;
  currentWorkingPath: Array<{ level: ComposerChoiceLevel; choice: ComposerChoice }>;
  currentCursorTokenIndex: number;
  currentVerseIndex: number;
  totalVerses: number;
  verseNavigatorItems: Array<{
    unitId: string;
    label: string;
    active: boolean;
    state: 'approved' | 'in-progress' | 'not-started';
  }>;
  generatedLyricText: string;
  onApplyChoice: (level: ComposerChoiceLevel, choice: ComposerChoice) => void;
  onPreviewChoice: (choice: ComposerChoice | null) => void;
  onClearPreview: () => void;
  onHoverToken: (tokenId: string | null) => void;
  onSetCursor: (tokenIndex: number) => void;
  onGenerateLyric: () => void;
  onPreviousVerse: () => void;
  onNextVerse: () => void;
  hasPreviousVerse: boolean;
  hasNextVerse: boolean;
  onSelectCloudNode: (nodeId: string) => void;
}) {
  if (!unit) {
    return (
      <section className="visual-cloud-panel">
        <p className="eyebrow">Verse flow</p>
        <p className="empty-state">Select a unit to view the color-coded word / phrase / idea / lyric flow cloud.</p>
      </section>
    );
  }

  const tokenColumns = Math.max(unit.tokens.length, 1);
  const tokenIndexMap = new Map(unit.tokens.map((token, index) => [token.token_id, index + 1]));
  const alignmentMap = new Map(allAlignments.map((alignment) => [alignment.alignment_id, alignment]));
  const ideaNodes = supportNodes.filter((node) => node.kind === 'concept');
  const lastCoveredTokenIndex = currentWorkingPath.reduce((maximum, segment) => {
    const segmentEnd = segment.choice.tokenEnd ?? segment.choice.tokenStart ?? -1;
    return Math.max(maximum, segmentEnd);
  }, -1);
  const nextTokenIndex = Math.min(lastCoveredTokenIndex + 1, tokenColumns - 1);
  const remainingTokens = unit.tokens.slice(lastCoveredTokenIndex + 1);
  const nextToken = remainingTokens[0] ?? null;

  const resolveRangeFromTokens = (tokenIds: string[]) => {
    const positions = tokenIds
      .map((tokenId) => tokenIndexMap.get(tokenId))
      .filter((value): value is number => typeof value === 'number')
      .sort((a, b) => a - b);
    if (positions.length === 0) {
      return null;
    }
    return { start: positions[0], end: positions[positions.length - 1] };
  };

  const resolveRangeFromAlignmentIds = (alignmentIds: string[]) => {
    const sourceTokenIds = alignmentIds.flatMap((alignmentId) => alignmentMap.get(alignmentId)?.source_token_ids ?? []);
    return resolveRangeFromTokens(sourceTokenIds);
  };

  const resolveRangeFromSpanIds = (spanIds: string[]) => {
    const sourceTokenIds = allAlignments
      .filter((alignment) => alignment.target_span_ids.some((spanId) => spanIds.includes(spanId)))
      .flatMap((alignment) => alignment.source_token_ids);
    return resolveRangeFromTokens(sourceTokenIds);
  };

  const createChoiceText = (tokens: Token[]) => {
    const parts = tokens.map((token) => buildTokenMeaning(token)).filter(Boolean);
    return normalizeComposerText(parts.join(' '));
  };

  const resolvePublicDomainWitness = (config: PublicDomainWitnessConfig): UnitWitness | null => {
    const existingWitness = unit.witnesses.find((witness) => {
      const haystack = [witness.source_id, witness.versionTitle]
        .join(' ')
        .toLowerCase();
      return config.aliases.some((alias) => haystack.includes(alias));
    });
    if (existingWitness) {
      return existingWitness;
    }

    const fallbackText = PSALM_ONE_PUBLIC_DOMAIN_WITNESSES[unit.ref]?.[config.key];
    if (!fallbackText) {
      return null;
    }
    return {
      source_id: config.sourceId,
      versionTitle: config.versionTitle,
      language: 'en',
      ref: unit.ref,
      source_url: '',
      text: fallbackText,
    };
  };

  const splitWitnessText = (text: string, ranges: Array<{ start: number; end: number }>) => {
    const desiredCount = ranges.length;
    const cleaned = normalizeComposerText(text).replace(/[.;:]+$/g, '');
    if (!cleaned || desiredCount === 0) {
      return [];
    }

    const cueSplitText = cleaned
      .replace(/\b(Blessed is the man)\s+(that|who)\b/i, '$1|$2')
      .replace(/\b(walketh not|does not walk|doesn['’]t walk)\s+(in the counsel)\b/i, '$1|$2')
      .replace(/[,;:]\s+(nor|Nor)\b/g, '|$1')
      .replace(/[.;:]\s+(and|And|but|But|for|For)\b/g, '|$1');
    const cueParts = cueSplitText.split('|').map((part) => normalizeComposerText(part)).filter(Boolean);
    if (cueParts.length === desiredCount) {
      return cueParts;
    }
    if (cueParts.length > desiredCount) {
      return [
        ...cueParts.slice(0, desiredCount - 1),
        normalizeComposerText(cueParts.slice(desiredCount - 1).join(' ')),
      ];
    }

    const words = cleaned.split(/\s+/).filter(Boolean);
    if (words.length === 0) {
      return [];
    }
    const totalRangeWidth = ranges.reduce((total, range) => total + (range.end - range.start + 1), 0) || desiredCount;
    let cursor = 0;
    return ranges.map((range, index) => {
      const isLast = index === ranges.length - 1;
      const remainingWords = words.length - cursor;
      const remainingRanges = ranges.length - index;
      const proportionalCount = Math.round(words.length * ((range.end - range.start + 1) / totalRangeWidth));
      const count = isLast
        ? remainingWords
        : Math.max(1, Math.min(remainingWords - (remainingRanges - 1), proportionalCount));
      const part = words.slice(cursor, cursor + count).join(' ');
      cursor += count;
      return normalizeComposerText(part);
    }).filter(Boolean);
  };

  type FlowBubble = {
    id: string;
    label: string;
    meta: string;
    start: number;
    end: number;
    type: ComposerChoiceLevel | 'witness' | 'output';
    accuracy: 'exact' | 'witness' | 'close' | 'interpretive' | 'lyric' | 'output';
    choice: ComposerChoice;
    active: boolean;
    onClick: () => void;
  };

  const laneYByType: Record<ComposerChoiceLevel | 'output', number> = {
    word: 5,
    phrase: 47,
    idea: 60,
    lyric: 79,
    output: 93,
  };

  const clampChoiceRange = (start: number, end: number) => ({
    start: Math.max(0, Math.min(start, tokenColumns - 1)),
    end: Math.max(0, Math.min(Math.max(start, end), tokenColumns - 1)),
  });

  const isActiveChoice = (level: ComposerChoiceLevel, choice: ComposerChoice) => currentWorkingPath.some((segment) => {
    const segmentStart = segment.choice.tokenStart ?? -1;
    const segmentEnd = segment.choice.tokenEnd ?? segmentStart;
    const choiceStart = choice.tokenStart ?? -2;
    const choiceEnd = choice.tokenEnd ?? choiceStart;
    return segment.level === level
      && (segment.choice.id === choice.id || (segmentStart === choiceStart && segmentEnd === choiceEnd && normalizeComposerText(segment.choice.text) === normalizeComposerText(choice.text)));
  });

  const toBubble = (
    level: ComposerChoiceLevel,
    choice: ComposerChoice,
    meta: string,
    accuracy: 'exact' | 'close' | 'interpretive' | 'lyric',
  ): FlowBubble => ({
    id: choice.id,
    label: choice.label,
    meta,
    start: Math.max(1, (choice.tokenStart ?? nextTokenIndex) + 1),
    end: Math.min(tokenColumns, (choice.tokenEnd ?? choice.tokenStart ?? nextTokenIndex) + 1),
    type: level,
    accuracy,
    choice,
    active: isActiveChoice(level, choice),
    onClick: () => onApplyChoice(level, choice),
  });

  const literalChoiceMap = literalAidRenderings.map((rendering, index) => {
    const range = resolveRangeFromAlignmentIds(rendering.alignment_ids)
      ?? resolveRangeFromSpanIds(rendering.target_spans.map((span) => span.span_id))
      ?? { start: Math.min(tokenColumns, index + 1), end: Math.min(tokenColumns, index + 1) };
    return {
      rendering,
      tokenStart: range.start - 1,
      tokenEnd: range.end - 1,
    };
  });

  const createRangeChoice = (
    level: ComposerChoiceLevel,
    id: string,
    label: string,
    start: number,
    end: number,
    description: string,
  ): ComposerChoice => {
    const range = clampChoiceRange(start, end);
    return {
      id,
      label,
      text: label,
      tokenStart: range.start,
      tokenEnd: range.end,
      description,
    };
  };

  const phraseRanges = tokenColumns >= 12
    ? [
        clampChoiceRange(0, 1),
        clampChoiceRange(2, 4),
        clampChoiceRange(5, 6),
        clampChoiceRange(7, 10),
        clampChoiceRange(11, tokenColumns - 1),
      ]
    : Array.from({ length: Math.ceil(tokenColumns / 3) }, (_, index) => clampChoiceRange(index * 3, Math.min(tokenColumns - 1, index * 3 + 2)));

  const conceptRanges = tokenColumns >= 12
    ? [
        clampChoiceRange(0, 1),
        clampChoiceRange(2, 6),
        clampChoiceRange(7, 10),
        clampChoiceRange(11, tokenColumns - 1),
      ]
    : Array.from({ length: Math.ceil(tokenColumns / 4) }, (_, index) => clampChoiceRange(index * 4, Math.min(tokenColumns - 1, index * 4 + 3)));

  const rangeIncludes = (range: { start: number; end: number }, words: string[]) => {
    const text = createChoiceText(unit.tokens.slice(range.start, range.end + 1)).toLowerCase();
    return words.every((word) => text.includes(word));
  };

  const phraseLabel = (range: { start: number; end: number }) => {
    if (rangeIncludes(range, ['blessed', 'man'])) return 'Blessed is the man';
    if (rangeIncludes(range, ['who', 'not']) && unit.tokens.slice(range.start, range.end + 1).some((token) => buildTokenMeaning(token).toLowerCase().includes('walk'))) return 'that walketh not';
    if (rangeIncludes(range, ['counsel'])) return 'in the counsel of the ungodly';
    if (rangeIncludes(range, ['way']) || rangeIncludes(range, ['sinner'])) return 'nor standeth in the way of sinners';
    if (rangeIncludes(range, ['seat']) || rangeIncludes(range, ['mocker'])) return 'nor sitteth in the seat of the scornful';
    return sentenceCase(createChoiceText(unit.tokens.slice(range.start, range.end + 1)));
  };

  const conceptLabel = (range: { start: number; end: number }) => {
    if (rangeIncludes(range, ['blessed', 'man'])) return 'Blessed is the one';
    if (rangeIncludes(range, ['walk']) || rangeIncludes(range, ['counsel'])) return 'who does not walk in the counsel of the wicked';
    if (rangeIncludes(range, ['way']) || rangeIncludes(range, ['sinner'])) return 'nor stand in the path of sinners';
    if (rangeIncludes(range, ['seat']) || rangeIncludes(range, ['mocker'])) return 'nor sit among mockers';
    return sentenceCase(createChoiceText(unit.tokens.slice(range.start, range.end + 1)));
  };

  const rhythmicLabel = (range: { start: number; end: number }) => {
    if (rangeIncludes(range, ['blessed', 'man'])) return 'How blessed is the one';
    if (rangeIncludes(range, ['walk']) || rangeIncludes(range, ['counsel'])) return 'Who does not walk with the wicked';
    if (rangeIncludes(range, ['way']) || rangeIncludes(range, ['sinner'])) return 'who does not stand with sinners';
    if (rangeIncludes(range, ['seat']) || rangeIncludes(range, ['mocker'])) return 'who does not sit among mockers';
    return sentenceCase(createChoiceText(unit.tokens.slice(range.start, range.end + 1)));
  };

  const rhythmicAlternatives = (range: { start: number; end: number }) => {
    if (rangeIncludes(range, ['blessed', 'man'])) {
      return ['How blessed is the one', 'Blessed is the one', 'Fortunate is the one'];
    }
    if (rangeIncludes(range, ['walk']) || rangeIncludes(range, ['counsel'])) {
      return ['Who does not walk with the wicked', 'who will not follow wicked counsel', 'who keeps clear of wicked counsel'];
    }
    if (rangeIncludes(range, ['way']) || rangeIncludes(range, ['sinner'])) {
      return ['who does not stand with sinners', 'nor stand in sinners\' path', 'who will not take the sinners\' road'];
    }
    if (rangeIncludes(range, ['seat']) || rangeIncludes(range, ['mocker'])) {
      return ['who does not sit among mockers', 'nor sit among the scornful', 'who keeps from mockers\' seats'];
    }
    return [rhythmicLabel(range)];
  };

  const wordChoices = unit.tokens.map((token, index) => ({
    id: `flow-word-${token.token_id}`,
    label: sentenceCase(buildTokenMeaning(token)),
    text: buildTokenMeaning(token),
    tokenStart: index,
    tokenEnd: index,
    tokenId: token.token_id,
    description: [token.surface, token.strong ? `Strong's ${token.strong}` : null].filter(Boolean).join(' · '),
  }));

  const phraseChoices = dedupeComposerChoices([
    ...phraseRanges.map((range, index) => createRangeChoice('phrase', `flow-phrase-${unit.unit_id}-${index}`, phraseLabel(range), range.start, range.end, 'phrase decision')),
    ...phraseAidRenderings.slice(0, 3).map((rendering, index) => {
      const renderingRange = resolveRangeFromAlignmentIds(rendering.alignment_ids)
        ?? resolveRangeFromSpanIds(rendering.target_spans.map((span) => span.span_id));
      const range = renderingRange
        ? { start: renderingRange.start - 1, end: renderingRange.end - 1 }
        : phraseRanges[index % Math.max(phraseRanges.length, 1)];
      return createRangeChoice('phrase', `flow-phrase-${rendering.rendering_id}`, sentenceCase(normalizeComposerText(rendering.text)), range.start, range.end, `${rendering.status} phrase aid`);
    }),
  ]);

  const ideaChoices = dedupeComposerChoices([
    ...conceptRanges.map((range, index) => createRangeChoice('idea', `flow-concept-${unit.unit_id}-${index}`, conceptLabel(range), range.start, range.end, 'concept decision')),
    ...conceptAidRenderings.slice(0, 2).map((rendering, index) => {
      const renderingRange = resolveRangeFromAlignmentIds(rendering.alignment_ids)
        ?? resolveRangeFromSpanIds(rendering.target_spans.map((span) => span.span_id));
      const range = renderingRange
        ? { start: renderingRange.start - 1, end: renderingRange.end - 1 }
        : conceptRanges[index % Math.max(conceptRanges.length, 1)];
      return createRangeChoice('idea', `flow-concept-${rendering.rendering_id}`, sentenceCase(normalizeComposerText(rendering.text)), range.start, range.end, `${rendering.status} concept aid`);
    }),
    ...ideaNodes.slice(0, 2).map((node, index) => {
      const range = conceptRanges[index % Math.max(conceptRanges.length, 1)];
      return createRangeChoice('idea', `flow-concept-node-${node.node_id}`, sentenceCase(node.label), range.start, range.end, `${node.support_count} context links`);
    }),
  ]);

  const lyricChoices = dedupeComposerChoices([
    ...conceptRanges.flatMap((range, rangeIndex) =>
      rhythmicAlternatives(range).map((label, choiceIndex) =>
        createRangeChoice(
          'lyric',
          `flow-rhythm-${unit.unit_id}-${rangeIndex}-${choiceIndex}`,
          label,
          range.start,
          range.end,
          choiceIndex === 0 ? 'rhythmic decision' : 'alternate rhythm',
        ),
      ),
    ),
    ...(generatedLyricText.trim()
      ? [createRangeChoice('lyric', 'flow-generated-rhythm', sentenceCase(normalizeComposerText(generatedLyricText)), 0, tokenColumns - 1, 'generated rhythm')]
      : []),
    ...currentEnglishRenderings
      .filter((rendering) => rendering.layer === 'lyric' || rendering.layer === 'metered_lyric' || rendering.layer === 'parallelism_lyric')
      .slice(0, 2)
      .map((rendering) => createRangeChoice(
      'lyric',
      `flow-rhythm-${rendering.rendering_id}`,
      sentenceCase(normalizeComposerText(rendering.text)),
      0,
      tokenColumns - 1,
      `${rendering.layer.replace(/_/g, ' ')} ${rendering.status}`,
    )),
    ...retrievalHits.slice(0, 2).map((hit, index) => createRangeChoice(
      'lyric',
      `flow-rhythm-hit-${hit.hit_id}-${index}`,
      sentenceCase(normalizeComposerText(hit.label)),
      0,
      tokenColumns - 1,
      hit.scope === 'same_psalm' ? 'same-psalm witness' : 'cross-psalm witness',
    )),
  ]);

  const outputChoices = currentWorkingPath.length > 0
    ? currentWorkingPath.map((segment, index) => ({
        id: `flow-output-${segment.choice.id}-${index}`,
        label: sentenceCase(normalizeComposerText(segment.choice.text)),
        text: segment.choice.text,
        tokenStart: segment.choice.tokenStart ?? 0,
        tokenEnd: segment.choice.tokenEnd ?? segment.choice.tokenStart ?? tokenColumns - 1,
        description: `${segment.level === 'idea' ? 'concept' : segment.level} selected`,
      }))
    : lyricChoices.slice(0, Math.min(4, lyricChoices.length)).map((choice, index) => ({
        ...choice,
        id: `flow-output-preview-${choice.id}-${index}`,
        description: 'output preview',
      }));

  const wordBubbles = wordChoices.map((choice) => toBubble('word', choice, choice.description ?? 'word', 'exact'));
  const witnessRows = PUBLIC_DOMAIN_WITNESS_CONFIGS.map((config) => {
    const witness = resolvePublicDomainWitness(config);
    const witnessChunks = witness ? splitWitnessText(witness.text, phraseRanges) : [];
    const bubbles = phraseRanges
      .flatMap((range, index): FlowBubble[] => {
        const chunk = witnessChunks[index] ?? '';
        if (!chunk) {
          return [];
        }
        const choice = createRangeChoice('phrase', `flow-witness-${config.key}-${unit.unit_id}-${index}`, sentenceCase(chunk), range.start, range.end, config.versionTitle);
        return [{
          id: choice.id,
          label: choice.label,
          meta: config.versionTitle,
          start: range.start + 1,
          end: range.end + 1,
          type: 'witness' as const,
          accuracy: 'witness' as const,
          choice,
          active: isActiveChoice('phrase', choice),
          onClick: () => onApplyChoice('phrase', choice),
        }];
      });
    return {
      config,
      bubbles,
    };
  });
  const phraseBubbles = phraseChoices.map((choice) => toBubble('phrase', choice, choice.description ?? 'phrase', 'close'));
  const ideaBubbles = ideaChoices.map((choice) => toBubble('idea', choice, choice.description ?? 'concept', 'interpretive'));
  const lyricBubbles = lyricChoices.map((choice) => toBubble('lyric', choice, choice.description ?? 'rhythmic', 'lyric'));
  const outputBubbles: FlowBubble[] = outputChoices.map((choice) => ({
    id: choice.id,
    label: choice.label,
    meta: choice.description ?? 'output',
    start: Math.max(1, (choice.tokenStart ?? 0) + 1),
    end: Math.min(tokenColumns, (choice.tokenEnd ?? choice.tokenStart ?? tokenColumns - 1) + 1),
    type: 'output',
    accuracy: 'output',
    choice,
    active: currentWorkingPath.length > 0,
    onClick: () => onApplyChoice('lyric', choice),
  }));

  const selectedConnectionNodes = currentWorkingPath.map((segment) => {
    const choiceStart = segment.choice.tokenStart ?? 0;
    const choiceEnd = segment.choice.tokenEnd ?? choiceStart;
    const start = Math.max(1, choiceStart + 1);
    const end = Math.min(tokenColumns, choiceEnd + 1);
    return {
      id: `${segment.level}-${segment.choice.id}`,
      type: segment.level,
      x: (((start - 1) + end) / 2 / tokenColumns) * 100,
      y: laneYByType[segment.level],
    };
  });
  const finalOutputConnectionNode = selectedConnectionNodes.length > 0
    ? {
        id: 'output-final',
        type: 'output' as const,
        x: selectedConnectionNodes[selectedConnectionNodes.length - 1].x,
        y: laneYByType.output,
      }
    : null;
  const arrowNodes = finalOutputConnectionNode ? [...selectedConnectionNodes, finalOutputConnectionNode] : selectedConnectionNodes;
  const arrowSegments = arrowNodes.slice(1).map((node, index) => ({
    id: `${arrowNodes[index].id}-${node.id}`,
    from: arrowNodes[index],
    to: node,
  }));
  const lexicalContextRefs = lexicalTokenCard
    ? Array.from(new Set([
        ...(lexicalTokenCard.nearby_usage_examples ?? []),
        ...(lexicalTokenCard.same_psalm ?? []),
        ...(lexicalTokenCard.same_psalms ?? []),
      ])).slice(0, 6)
    : [];
  const lexicalSourceLabels = lexicalTokenCard?.enrichment_sources
    ? Object.entries(lexicalTokenCard.enrichment_sources).map(([sourceId, source]) => `${sourceId}: ${source.available_fields.join(', ') || source.status}`)
    : [];

  const groupFlowBubbles = (bubbles: FlowBubble[]) => {
    const groups = new Map<string, FlowBubble[]>();
    bubbles.forEach((bubble) => {
      const key = `${bubble.start}:${bubble.end}`;
      groups.set(key, [...(groups.get(key) ?? []), bubble]);
    });
    return [...groups.values()].map((group) => ({
      id: group.map((bubble) => bubble.id).join('|'),
      start: Math.min(...group.map((bubble) => bubble.start)),
      end: Math.max(...group.map((bubble) => bubble.end)),
      bubbles: group,
    }));
  };

  const renderFlowLane = (bubbles: FlowBubble[]) => (
    <div className="flow-lane-track" style={{ gridTemplateColumns: `repeat(${tokenColumns}, minmax(96px, 1fr))` }}>
      {groupFlowBubbles(bubbles).map((group) => (
        <div
          key={group.id}
          className={`flow-choice-stack ${group.bubbles.length > 1 ? 'flow-choice-stack--multi' : ''}`}
          style={{ gridColumn: `${group.start} / ${Math.min(tokenColumns + 1, group.end + 1)}` }}
        >
          {group.bubbles.map((bubble) => (
            <button
              key={bubble.id}
              type="button"
              className={`flow-stage-bubble flow-stage-bubble--${bubble.type} flow-stage-bubble--accuracy-${bubble.accuracy} ${bubble.active ? 'active' : ''}`}
              onClick={bubble.onClick}
              onMouseEnter={() => {
                onPreviewChoice(bubble.choice);
                if (bubble.choice.tokenId) {
                  onHoverToken(bubble.choice.tokenId);
                }
              }}
              onMouseLeave={() => {
                onClearPreview();
                if (bubble.choice.tokenId) {
                  onHoverToken(null);
                }
              }}
            >
              <span className="flow-stage-bubble__label">{bubble.label}</span>
              <small className="flow-stage-bubble__meta">{bubble.meta}</small>
            </button>
          ))}
        </div>
      ))}
    </div>
  );

  return (
    <section className="visual-cloud-panel">
      <div className="flow-stage-bar">
        <button
          type="button"
          className="flow-verse-nav-button"
          onClick={onPreviousVerse}
          disabled={!hasPreviousVerse}
          aria-label="Go to previous verse"
          title="Previous verse"
        >
          <span aria-hidden="true">‹</span>
        </button>
        <div className="flow-stage-bar__center">
          <div className="flow-stage-bar__title">
            <p className="eyebrow">Bubble Flow</p>
            <h3>{unit.ref}</h3>
            <span className="tag">verse {currentVerseIndex >= 0 ? currentVerseIndex + 1 : 1} / {Math.max(totalVerses, 1)}</span>
          </div>
          <div className="flow-stage-bar__meta">
            <span className="tag">cursor {currentCursorTokenIndex + 1} / {tokenColumns}</span>
            <span className="tag">layer: {activeLayer}</span>
            <button type="button" className="tab" onClick={onGenerateLyric}>
              Generate rhythm
            </button>
          </div>
          <div className="flow-verse-progress" aria-label="Verse position in psalm">
            {verseNavigatorItems.map((item) => (
              <span
                key={item.unitId}
                className={`flow-verse-progress__item flow-verse-progress__item--${item.state} ${item.active ? 'active' : ''}`}
                aria-current={item.active ? 'page' : undefined}
                title={`Verse ${item.label} · ${item.active ? 'current' : item.state}`}
              >
                {item.label}
              </span>
            ))}
          </div>
        </div>
        <button
          type="button"
          className={`flow-verse-nav-button ${hasNextVerse ? 'flow-verse-nav-button--ready' : ''}`}
          onClick={onNextVerse}
          disabled={!hasNextVerse}
          aria-label="Lock verse and move to next verse"
          title="Lock verse and move to next verse"
        >
          <span aria-hidden="true">›</span>
        </button>
      </div>

      <div className="flow-diagram-scroll">
        <div className="flow-diagram" style={{ minWidth: `${Math.max(980, tokenColumns * 118 + 128)}px` }}>
          <div className="flow-lane-labels" aria-hidden="true">
            <div className="flow-lane-label">Word</div>
            {witnessRows.map((row) => (
              <div key={row.config.key} className="flow-lane-label" title={row.config.versionTitle}>
                {row.config.laneLabel}
              </div>
            ))}
            <div className="flow-lane-label">Phrase</div>
            <div className="flow-lane-label">Concept</div>
            <div className="flow-lane-label">Rhythmic</div>
            <div className="flow-lane-label">Output</div>
          </div>
          <div className="flow-lane-canvas">
            {arrowSegments.length > 0 ? (
              <svg className="flow-arrow-layer" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                <defs>
                  <marker id="flow-arrow-head" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                    <path d="M0,0 L8,4 L0,8 z" />
                  </marker>
                </defs>
                {arrowSegments.map((segment) => {
                  const midY = (segment.from.y + segment.to.y) / 2;
                  return (
                    <path
                      key={segment.id}
                      d={`M ${segment.from.x} ${segment.from.y} C ${segment.from.x} ${midY}, ${segment.to.x} ${midY}, ${segment.to.x} ${segment.to.y}`}
                      className="flow-arrow-path"
                      markerEnd="url(#flow-arrow-head)"
                    />
                  );
                })}
              </svg>
            ) : null}
            {renderFlowLane(wordBubbles)}
            {witnessRows.map((row) => (
              <Fragment key={row.config.key}>
                {renderFlowLane(row.bubbles)}
              </Fragment>
            ))}
            {renderFlowLane(phraseBubbles)}
            {renderFlowLane(ideaBubbles)}
            {renderFlowLane(lyricBubbles)}
            {renderFlowLane(outputBubbles)}
          </div>
        </div>
      </div>

      {lexicalTokenCard ? (
        <article className="bdb-context-card">
          <div className="horizontal-between">
            <div>
              <p className="eyebrow">BDB Context</p>
              <h4>{lexicalTokenCard.surface}</h4>
            </div>
            <span className="tag">{lexicalTokenCard.ref}</span>
          </div>
          <div className="bdb-context-grid">
            <div>
              <span>Lemma</span>
              <strong>{lexicalTokenCard.lemma ?? '—'}</strong>
            </div>
            <div>
              <span>Strong&apos;s</span>
              <strong>{lexicalTokenCard.strong ?? '—'}</strong>
            </div>
            <div>
              <span>Gloss</span>
              <strong>{lexicalTokenCard.gloss_list.length ? lexicalTokenCard.gloss_list.join(', ') : lexicalTokenCard.word_sense ?? '—'}</strong>
            </div>
            <div>
              <span>Morphology</span>
              <strong>{lexicalTokenCard.morph_readable ?? lexicalTokenCard.morph_code ?? '—'}</strong>
            </div>
          </div>
          <p className="bdb-context-line">
            {lexicalTokenCard.transliteration ? `${lexicalTokenCard.transliteration} · ` : ''}
            {lexicalTokenCard.part_of_speech ?? 'part of speech pending'}
            {lexicalTokenCard.syntax_role ? ` · syntax ${lexicalTokenCard.syntax_role}` : ''}
          </p>
          <div className="bdb-context-meta">
            <span>Passage context</span>
            <strong>{lexicalContextRefs.length ? lexicalContextRefs.join(' · ') : 'No nearby recurrence recorded'}</strong>
          </div>
          {lexicalSourceLabels.length ? (
            <div className="bdb-context-meta">
              <span>Lexical sources</span>
              <strong>{lexicalSourceLabels.join(' · ')}</strong>
            </div>
          ) : null}
        </article>
      ) : null}
    </section>
  );
}

function RetrievedHit({ hit, onCompare }: { hit: RetrievalHit; onCompare: (renderingId: string) => void }) {
  return (
    <article className="retrieval-hit-card">
      <div className="horizontal-between">
        <strong>{hit.scope === 'same_psalm' ? hit.ref : `${hit.ref} · cross-Psalm`}</strong>
        <span className="subtle">score {hit.explanation.final_score.toFixed(2)}</span>
      </div>
      <p className="result-snippet">{hit.label}</p>
      <div className="result-meta">
        <span>{hit.layer}</span>
        <span>{hit.status}</span>
        {hit.rendering_id ? (
          <button type="button" className="link-button" onClick={() => onCompare(hit.rendering_id!)}>
            Send to compare
          </button>
        ) : null}
      </div>
      <p className="subtle">
        vector {hit.explanation.vector_score.toFixed(2)} · overlap {hit.explanation.phrase_concept_overlap.toFixed(2)} · literal priority {hit.explanation.literal_priority.toFixed(2)}
      </p>
    </article>
  );
}
