import type { Layer, Psalm, Rendering, Unit } from '../types';

export const SUPPORTED_LAYERS: Layer[] = ['gloss', 'literal', 'phrase', 'concept', 'lyric', 'metered_lyric', 'parallelism_lyric'];

export interface ResolvedLayerState {
  availableLayers: Layer[];
  renderLayer: Layer | null;
  notice: string | null;
}

function orderAvailableLayers(layers: Iterable<string>): Layer[] {
  const available = new Set<Layer>();
  for (const layer of layers) {
    if (SUPPORTED_LAYERS.includes(layer as Layer)) {
      available.add(layer as Layer);
    }
  }
  return SUPPORTED_LAYERS.filter((layer) => available.has(layer));
}

export function getAvailableRenderingLayers(unit?: Pick<Unit, 'renderings'> | null): Layer[] {
  return orderAvailableLayers((unit?.renderings ?? []).map((rendering) => rendering.layer));
}

export function getAvailablePsalmLayers(psalm?: Pick<Psalm, 'units'> | null): Layer[] {
  return orderAvailableLayers(
    (psalm?.units ?? []).flatMap((unit) => unit.renderings.map((rendering) => rendering.layer)),
  );
}

export function getAvailableCorpusLayers(psalms?: Psalm[] | null): Layer[] {
  return orderAvailableLayers(
    (psalms ?? []).flatMap((psalm) => psalm.units.flatMap((unit) => unit.renderings.map((rendering) => rendering.layer))),
  );
}

export function getSelectableLayers(preferredLayers: Layer[], fallbackLayers: Layer[] = SUPPORTED_LAYERS): Layer[] {
  return preferredLayers.length > 0 ? preferredLayers : fallbackLayers;
}

export function getPreferredSelectableLayer(activeLayer: Layer, availableLayers: Layer[]): Layer {
  if (availableLayers.includes(activeLayer)) {
    return activeLayer;
  }
  return availableLayers[0] ?? activeLayer;
}

export function getSelectablePsalmOptions(psalms?: Psalm[] | null): Psalm[] {
  return psalms ?? [];
}

export function getDefaultPsalmSelection(psalms?: Psalm[] | null, selectedPsalmId?: string | null): Psalm | null {
  const selectablePsalms = getSelectablePsalmOptions(psalms);
  if (!selectablePsalms.length) {
    return null;
  }
  return selectablePsalms.find((psalm) => psalm.psalm_id === selectedPsalmId) ?? selectablePsalms[0] ?? null;
}

function resolveNearestLayer(selectedLayer: Layer, availableLayers: Layer[]): Layer | null {
  if (!availableLayers.length) {
    return null;
  }
  const selectedIndex = SUPPORTED_LAYERS.indexOf(selectedLayer);
  const ranked = [...availableLayers].sort((left, right) => {
    const leftIndex = SUPPORTED_LAYERS.indexOf(left);
    const rightIndex = SUPPORTED_LAYERS.indexOf(right);
    const leftDistance = Math.abs(leftIndex - selectedIndex);
    const rightDistance = Math.abs(rightIndex - selectedIndex);
    if (leftDistance !== rightDistance) {
      return leftDistance - rightDistance;
    }
    const leftDownstream = leftIndex >= selectedIndex ? 0 : 1;
    const rightDownstream = rightIndex >= selectedIndex ? 0 : 1;
    if (leftDownstream !== rightDownstream) {
      return leftDownstream - rightDownstream;
    }
    return leftIndex - rightIndex;
  });
  return ranked[0] ?? null;
}

export function resolveLayerState(unit: Unit | null | undefined, selectedLayer: Layer): ResolvedLayerState {
  const availableLayers = getAvailableRenderingLayers(unit);
  if (!availableLayers.length) {
    return {
      availableLayers,
      renderLayer: null,
      notice: null,
    };
  }
  if (availableLayers.includes(selectedLayer)) {
    return {
      availableLayers,
      renderLayer: selectedLayer,
      notice: null,
    };
  }
  const latestLayer = unit?.current_layer_state?.latest_layer;
  const resolvedLayer =
    latestLayer && availableLayers.includes(latestLayer)
      ? latestLayer
      : resolveNearestLayer(selectedLayer, availableLayers);
  return {
    availableLayers,
    renderLayer: resolvedLayer,
    notice: resolvedLayer ? `Showing ${resolvedLayer}; no ${selectedLayer} rendering exists for this unit.` : null,
  };
}

export function sortRenderingsByStatus(renderings: Rendering[]): Rendering[] {
  return [...renderings].sort((left, right) => {
    if (left.status === right.status) {
      return left.rendering_id.localeCompare(right.rendering_id);
    }
    if (left.status === 'canonical') return -1;
    if (right.status === 'canonical') return 1;
    return left.status.localeCompare(right.status);
  });
}
