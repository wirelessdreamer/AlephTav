import { expect, test, type Page } from '@playwright/test';

const identity = { study_snapshot_id: 'study.arrangement-fixture', policy_revision_id: 'policy.fixture' };
const unitId = (verse: number) => `ps009.v${String(verse).padStart(3, '0')}.a`;
const tokenId = (verse: number) => `ps009.v${String(verse).padStart(3, '0')}.t001`;

function evidence() {
  const greek = (verse: number, text: string, partial = false) => ({
    unit_id: `lxx.authored.r0001.ps008.v${String(verse).padStart(3, '0')}.a`,
    ref: `Greek Psalm 8:${verse}`, source_greek: text + (verse === 5 ? '·' : ''), literal_text: 'authored lexical aid', partial,
    tokens: [{ token_id: `lxx.authored.r0001.ps008.v${String(verse).padStart(3, '0')}.t001`, surface: text, gloss: 'fixture' }],
  });
  return { ...identity, available: true, edition_id: 'authored', text_revision_id: 'r0001',
    source_attribution: [{ attribution: 'Authored Greek source fixture', license: 'CC0' }],
    by_mt_unit: {
      [unitId(1)]: { relations: ['merge'], units: [greek(5, 'λόγος'), greek(6, 'ἔλεος')] },
      [unitId(2)]: { relations: ['partial'], units: [greek(6, 'ἔλεος', true)] },
      [unitId(3)]: { relations: ['edition_absent'], units: [] },
    },
  };
}

async function mountedFixture(page: Page, blocked = false, long = false, preview = false, origins = false, tallSources = false, extraMatches = false, context = false) {
  await page.addInitScript(() => localStorage.setItem('aleph-tav.full-workbench', 'true'));
  await page.addInitScript(() => localStorage.setItem('aleph-tav.assistant-ui', JSON.stringify({
    visibility: 'closed', placement: 'footer',
  })));
  const units = [1, 2, 3, 4].map(verse => ({
    unit_id: unitId(verse), ref: `Psalm 9:${verse}`, tokens: [{ token_id: tokenId(verse),
      surface: `שיר${verse}`, gloss: 'authored song', count: 1 }],
  }));
  for (const unit of tallSources ? units : long ? [units[0]] : []) {
    unit.tokens.push(...Array.from({ length: tallSources ? 79 : 39 }, (_, i) => ({
      token_id: `${unit.unit_id.slice(0, -1)}t${String(i + 2).padStart(3, '0')}`, surface: 'שיר', gloss: 'authored song', count: 1,
    })));
  }
  const rows = units.map((unit, index) => ({
    mt_reference: unit.ref, display_reference: unit.ref, unit_ids: [unit.unit_id],
    hebrew_text: unit.tokens[0].surface, tokens: unit.tokens.map(token => ({ ...token, transliteration: 'shir', display_gloss: 'song' })),
    literal_text: `Authored Hebrew literal ${index + 1}`, literal_rendering_ids: [], literal_status: 'draft', literal_links: [],
    english_text: `Authored English line ${index + 1}`, english_rendering_ids: [], english_status: 'draft',
    english_guidance: null, accuracy_rating: null, accuracy_note: '', creative_liberties_note: '',
    assessment_status: 'draft', created_via: 'human', generator_provider: null, comparison_id: null,
    incomplete: false, literal_backbone: [], non_source_material: [], stale: false, verse_notes: [],
    word_choices: [], pending_rebuild: null,
  }));
  const lines = [1, 2, 3, 4].map(verse => ({ line_id: `ln.${verse}`, text: `Authored song line ${verse}`,
    anchors: [{ unit_id: unitId(verse), token_ids: [tokenId(verse)] }], liberty: 'tracks', rationale: '', approvals: [] }));
  if (extraMatches) lines.push(
    { ...lines[2], line_id: 'ln.5', text: 'Authored verse 3 reprise' },
    { ...lines[3], line_id: 'ln.6', text: 'Unanchored addition', anchors: [], liberty: 'added' },
  );
  if (long) {
    lines[0].anchors = units.map(unit => ({ unit_id: unit.unit_id, token_ids: unit.tokens.map(token => token.token_id) }));
    lines.slice(1).forEach(line => { line.anchors = []; });
  }
  if (context) {
    lines[0].rationale = 'Retains the opening address.';
    lines[1].rationale = 'Compresses the request to incline an ear into a request to hear.';
    lines.splice(1, 0, { ...lines[0], line_id: 'ln.added', text: 'That is what I have called you',
      anchors: [], liberty: 'added', rationale: 'Adds a retrospective comment on addressing God as the source of salvation.' });
  }
  const arrangement = { arrangement_id: 'arr.fixture', psalm_id: 'ps009', title: 'Authored setting',
    layer: 'lyric', status: 'draft', guidance: '', created_via: 'human', sections: [{ section_id: 'sec.fixture',
      kind: 'verse', label: 'First stanza', repeat_of: null, lines }], omissions: [], audit_ids: [] };
  const greek = blocked ? { available: false, message: 'Greek source blocked by current policy.', by_mt_unit: {} }
    : { ...evidence(), ...(preview ? { preview: true, study_snapshot_id: undefined, policy_revision_id: undefined } : {}) };
  if (preview && 'edition_id' in greek) {
    for (const mapping of Object.values(greek.by_mt_unit)) for (const unit of mapping.units) {
      unit.literal_text = '';
      unit.tokens.forEach(token => { token.gloss = ''; });
    }
  }
  if (long && 'edition_id' in greek) {
    const source = greek.by_mt_unit[unitId(1)].units[0];
    source.source_greek = `${'λόγος '.repeat(120)}τέλος.`;
    source.tokens = Array.from({ length: 120 }, (_, i) => ({
      token_id: `lxx.authored.r0001.ps008.v005.t${String(i + 1).padStart(3, '0')}`, surface: 'λόγος', gloss: 'fixture',
    }));
    source.tokens.push({ token_id: 'lxx.authored.r0001.ps008.v005.t121', surface: 'τέλος', gloss: 'fixture' });
  }
  await page.route('**/assistant/**', route => route.fulfill({ status: 503, body: '{}' }));
  await page.route('**/codex/**', route => route.fulfill({ status: 503, body: '{}' }));
  await page.route('**/lxx/editions', route => route.fulfill({ json: { editions: [] } }));
  await page.route('**/collections', route => route.fulfill({ json: [{ collection_id: 'col.default',
    title: 'Source fixture project', built_in: true, members: [{ psalm_id: 'ps009', translation_id: 'translation.fixture' }] }] }));
  await page.route('**/psalms', route => route.fulfill({ json: [{ psalm_id: 'ps009', title: 'Psalm 9' }] }));
  await page.route('**/psalms/ps009/comparison-table?*', route => route.fulfill({ json: {
    psalm_id: 'ps009', title: 'Psalm 9', rows, analysis: null, canonical_numbering: null,
  } }));
  await page.route('**/psalms/ps009/briefing?*', route => route.fulfill({ json: { briefing: null, history: [], greek_sources: greek } }));
  await page.route('**/psalms/ps009/translation-guidance?*', route => route.fulfill({ json: { translation_guidance: '' } }));
  await page.route('**/psalms/ps009/arrangements?*', route => route.fulfill({ json: { arrangements: [arrangement], refrains: [] } }));
  await page.route('**/psalms/ps009/arrangements/arr.fixture', route => route.fulfill({ json: {
    source_choices: origins ? [{ choice_id: 'ln.1:ps009.v001.a', line_id: 'ln.1', unit_id: unitId(1),
      mt_reference: 'Psalm 9:1', greek_reference: 'Greek Psalm 8:5', edition_id: 'authored', text_revision_id: 'r0001',
      source_version: 'authored:r0001:fixture', rendering_id: 'rnd.fixture', text: lines[0].text,
      rationale: 'Follows Greek Psalm 8:5.', decision_scope: 'verse_translation', status: 'proposed',
      hebrew_phrases: [{ start: 9, end: 18, text: 'song line', token_ids: [tokenId(1)] }],
      decisions: [{ briefing_run_id: 'brief.fixture', question_index: 0,
        question: { topic: 'A source choice', verses: [1], question: 'Which reading?', background: '', options: [] },
        answer: 'Follow the Greek reading.', notes: 'Preserve this recorded reason.' }] }] : [],
    arrangement, greek_sources: greek, coverage: { units, totals: { words: 4, once: 4, repeated: 0, dropped: 0 } },
    sung: lines.map((line, i) => ({ position: i + 1, section_id: 'sec.fixture', section_label: 'First stanza',
      kind: 'verse', time: 1, repeat: false, variation: false, line })),
    liberties: [], summary: { sung_lines: 4, open: 0, by_kind: {} }, required_approvals: {},
  } }));
  await page.route('**/greek/tokens/*/card?*', route => {
    const params = new URL(route.request().url()).searchParams;
    expect(params.get('study_snapshot_id')).toBe(identity.study_snapshot_id);
    expect(params.get('policy_revision_id')).toBe(identity.policy_revision_id);
    return route.fulfill({ json: { ...identity, token: { surface: 'λόγος' },
      analyses: [{ analysis_id: 'a.fixture', lemma: 'λόγος', status: 'proposed', scheme: 'fixture', raw_tag: 'N-NSM' }],
      dictionary_entries: [], counts: { total_matches: 2 },
    } });
  });
  await page.goto('/#/workbench');
  await page.getByRole('button', { name: 'Sources', exact: true }).click();
  return page.locator('.arr-sources');
}

test('Sources shows saved arrangement context after Greek, including explicitly unanchored stanza additions', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const sources = await mountedFixture(page, false, false, false, false, false, false, true);
  const first = sources.getByRole('group', { name: 'Sources for Psalm 9:1', exact: true });
  const context = first.getByRole('region', { name: 'Arrangement context' });
  await expect(context.getByRole('heading', { name: 'Context', exact: true })).toBeVisible();
  await expect(context.getByText('Retains the opening address.', { exact: true })).toBeVisible();
  await expect(context.getByText('That is what I have called you', { exact: true })).toBeVisible();
  await expect(context.getByText('First stanza · added line; no source anchor', { exact: true })).toBeVisible();
  await expect(context.getByText('Adds a retrospective comment on addressing God as the source of salvation.', { exact: true })).toBeVisible();
  const greekBox = await first.locator('.arr-verse__greek').boundingBox();
  const contextBox = await context.boundingBox();
  expect(contextBox!.y).toBeGreaterThanOrEqual(greekBox!.y + greekBox!.height);
  const second = sources.getByRole('group', { name: 'Sources for Psalm 9:2', exact: true });
  await expect(second.getByRole('region', { name: 'Arrangement context' })).toHaveText(/Compresses the request/);
  await expect(second.getByText('Retains the opening address.', { exact: true })).toHaveCount(0);
  await expect(sources.getByRole('group', { name: 'Sources for Psalm 9:3', exact: true }).locator('.arr-verse__context')).toHaveCount(0);
  await expect(sources.locator('.arr-band[data-position="2"]')).toHaveCount(0);
  await first.getByRole('button', { name: 'Collapse source details for Psalm 9:1' }).click();
  await expect(context).toHaveCount(0);
  await first.getByRole('button', { name: 'Expand source details for Psalm 9:1' }).click();
  await expect(context).toBeVisible();
  await page.setViewportSize({ width: 430, height: 900 });
  await expect(context).toBeVisible();
  expect(await sources.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
});

test('arrangement source ribbon cards each retain Hebrew and edition-mapped Greek inline and collapsed', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  const sources = await mountedFixture(page);
  const blocks = sources.locator('.arr-verse');
  await expect(blocks).toHaveCount(4);
  for (let verse = 1; verse <= 4; verse += 1) {
    const block = sources.getByRole('group', { name: `Sources for Psalm 9:${verse}`, exact: true });
    await expect(block.getByRole('heading', { name: `Hebrew (MT) · Psalm 9:${verse}`, exact: true })).toBeVisible();
    await expect(block.getByRole('heading', { name: 'Greek (LXX) · authored r0001', exact: true })).toBeVisible();
    await expect(block.locator('[lang="he"][dir="rtl"]')).toBeVisible();
  }
  const merged = sources.getByRole('group', { name: 'Sources for Psalm 9:1', exact: true });
  await expect(merged.getByText('Greek Psalm 8:5', { exact: true })).toBeVisible();
  await expect(merged.getByText('Greek Psalm 8:6', { exact: true })).toBeVisible();
  await expect(merged.locator('.arr-greek-text[lang="grc"][dir="ltr"]')).toHaveCount(2);
  await expect(merged.getByText('λόγος', { exact: true })).toBeVisible();
  await expect(merged.locator('.arr-greek-surface').first()).toHaveText('λόγος·');
  await expect(merged.locator('.arr-greek-token').first().locator('.interlinear__gl')).toHaveText('fixture');
  await expect(sources.getByRole('group', { name: 'Sources for Psalm 9:2', exact: true }).getByText(/partial correspondence; full Greek verse shown/)).toBeVisible();
  await expect(sources.getByRole('group', { name: 'Sources for Psalm 9:3', exact: true }).getByText(/edition_absent/)).toBeVisible();
  await expect(sources.getByRole('group', { name: 'Sources for Psalm 9:4', exact: true }).getByText(/No reviewed Greek correspondence/)).toBeVisible();
  await expect(sources.getByText(/Ribbons flow from source languages/)).toBeVisible();
  const licenses = sources.locator('.source-licenses');
  await expect(licenses).toHaveCount(1);
  await expect(licenses.getByText(/Authored Greek source fixture/)).toBeHidden();
  await licenses.locator('summary').click();
  await expect(licenses.getByText(/Authored Greek source fixture · CC0/)).toBeVisible();
  await licenses.locator('summary').click();
  await page.screenshot({ path: testInfo.outputPath('arrangement-dual-sources.png'), fullPage: true });
  const toggle = merged.getByRole('button', { name: 'Collapse source details for Psalm 9:1' });
  const firstRibbon = sources.locator('.arr-band').first();
  const expandedRibbon = await firstRibbon.getAttribute('d');
  await toggle.click();
  await expect.poll(() => firstRibbon.getAttribute('d')).not.toBe(expandedRibbon);
  await expect(merged.getByText('λόγος', { exact: true })).toBeVisible();
  await expect(merged.locator('p.hebrew[lang="he"][dir="rtl"]')).toBeVisible();
  await expect(merged.getByText('Authored Hebrew literal 1')).toHaveCount(0);
  await page.mouse.move(0, 0);
  await merged.hover({ position: { x: 8, y: 8 } });
  const tooltip = sources.getByRole('tooltip');
  await expect(tooltip.getByText('λόγος·', { exact: true })).toBeVisible();
  const tooltipWord = tooltip.locator('.arr-greek-token').first();
  await expect(tooltipWord.locator('.interlinear__gl')).toHaveText('fixture');
  const surfaceBounds = await tooltipWord.locator('.arr-greek-surface').boundingBox();
  const meaningBounds = await tooltipWord.locator('.interlinear__gl').boundingBox();
  expect(meaningBounds!.y).toBeGreaterThanOrEqual(surfaceBounds!.y + surfaceBounds!.height);
  await expect(tooltip.locator('.arr-greek-literal')).toHaveCount(0);
  await expect(tooltip.getByRole('heading', { name: 'Hebrew (MT) · Psalm 9:1', exact: true })).toBeVisible();
  await sources.locator('.arr-sung').first().hover();
  await expect(tooltip.getByText('λόγος·', { exact: true })).toBeVisible();
  await expect(tooltip.getByText('Authored song line 1', { exact: true })).toBeVisible();
  await page.mouse.move(0, 0);
  const word = merged.getByRole('button', { name: 'Study Greek λόγος · Greek Psalm 8:5', exact: true });
  await word.focus();
  await page.keyboard.press('Enter');
  await expect(sources.getByRole('dialog', { name: 'Greek word study' }).getByText('fixture N-NSM')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(word).toBeFocused();
  await page.setViewportSize({ width: 430, height: 900 });
  await expect(merged.getByText('λόγος', { exact: true })).toBeVisible();
  for (const verse of [2, 3, 4]) {
    const block = sources.getByRole('group', { name: `Sources for Psalm 9:${verse}`, exact: true });
    await block.getByRole('button', { name: `Collapse source details for Psalm 9:${verse}` }).click();
    await expect(block.getByRole('heading', { name: 'Greek (LXX) · authored r0001', exact: true })).toBeVisible();
  }
  await page.mouse.move(0, 0);
  await page.screenshot({ path: testInfo.outputPath('arrangement-dual-sources-narrow.png'), fullPage: true });
  expect(await sources.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  const paths = () => sources.locator('.arr-band').evaluateAll(elements => elements.map(element => element.getAttribute('d')).join('|'));
  const beforeResize = await paths();
  await merged.locator('.arr-greek-text').first().evaluate(element => { element.style.fontSize = '4rem'; });
  await expect.poll(paths).not.toBe(beforeResize);
  expect(errors).toEqual([]);
});

test('pinned source details close on outside clicks while inside clicks keep them open', async ({ page }) => {
  const sources = await mountedFixture(page);
  const read = sources.getByRole('button', { name: 'Read source evidence for Psalm 9:1', exact: true });
  const song = sources.getByRole('button', { name: 'Source evidence for song line 1', exact: true });
  const dialog = sources.getByRole('dialog', { name: 'Source evidence', exact: true });

  for (const trigger of [read, song]) {
    await trigger.click();
    await expect(dialog).toBeVisible();
    await dialog.getByRole('heading', { name: 'Hebrew (MT) · Psalm 9:1', exact: true }).click();
    await expect(dialog).toBeVisible();
    await page.mouse.click(2, 2);
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
  }
});

test('Hebrew and Greek words share hover outlines, pinned study, keyboard access and outside dismissal', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const sources = await mountedFixture(page);
  const verse = sources.getByRole('group', { name: 'Sources for Psalm 9:1', exact: true });
  const hebrew = verse.getByRole('button', { name: 'Study Hebrew שיר1 · Psalm 9:1', exact: true });
  const greek = verse.getByRole('button', { name: 'Study Greek λόγος · Greek Psalm 8:5', exact: true });
  for (const compact of [false, true]) {
    if (compact) await verse.getByRole('button', { name: 'Collapse source details for Psalm 9:1' }).click();
    for (const [word, language] of [[hebrew, 'Hebrew'], [greek, 'Greek']] as const) {
      const dialog = sources.getByRole('dialog', { name: `${language} word study`, exact: true });
      const tooltip = sources.getByRole('tooltip', { name: `${language} word study`, exact: true });
      await word.hover();
      await expect(tooltip).toBeVisible();
      await expect(word).toHaveCSS('cursor', 'pointer');
      await expect(word).toHaveCSS('outline-style', 'solid');
      await expect(word).toHaveCSS('outline-width', '2px');
      await word.click();
      await expect(dialog).toBeVisible();
      await expect(dialog.getByRole('button', { name: `Close ${language} word study` })).toBeFocused();
      await dialog.locator('strong').first().click();
      await expect(dialog).toBeVisible();
      await sources.getByText('Song · as sung', { exact: true }).click();
      await expect(dialog).toHaveCount(0);
      await expect(tooltip).toHaveCount(0);
      await word.focus();
      await page.keyboard.press('Enter');
      await expect(dialog).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(dialog).toHaveCount(0);
      await expect(word).toBeFocused();
      await expect(tooltip).toHaveCount(0);
      await page.keyboard.press('Space');
      await expect(dialog).toBeVisible();
      await dialog.getByRole('button', { name: `Close ${language} word study` }).click();
      await expect(dialog).toHaveCount(0);
      await expect(tooltip).toHaveCount(0);
      await page.mouse.move(0, 0);
    }
  }
});

test('source context uses the ribbon gutter and keeps the English column clear when resized', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 2232, height: 1076 });
  const sources = await mountedFixture(page);
  const song = sources.locator('.arr-sources__song');
  const gutter = sources.locator('.arr-sources__gutter');
  const line = sources.getByRole('button', { name: 'Source evidence for song line 1', exact: true });
  const read = sources.getByRole('button', { name: 'Read source evidence for Psalm 9:1', exact: true });
  const assertClear = async (card: ReturnType<typeof page.getByRole>, centered = false) => {
    const box = (await card.boundingBox())!;
    const english = (await song.boundingBox())!;
    expect(box.x + box.width).toBeLessThanOrEqual(english.x - 7);
    expect(box.x).toBeGreaterThanOrEqual(7);
    if (centered) {
      const space = (await gutter.boundingBox())!;
      expect(box.x).toBeGreaterThanOrEqual(space.x + 7);
      expect(box.x + box.width).toBeLessThanOrEqual(space.x + space.width - 7);
    }
  };
  await line.hover();
  const preview = sources.getByRole('tooltip', { name: 'Source evidence', exact: true });
  await expect(preview).toBeVisible();
  await assertClear(preview, true);
  const dialog = sources.getByRole('dialog', { name: 'Source evidence', exact: true });
  for (const trigger of [line, read]) {
    await trigger.click();
    await expect(dialog).toBeVisible();
    await assertClear(dialog, true);
    const mapTop = await sources.locator('.arr-sources__map').evaluate(el => el.getBoundingClientRect().top);
    expect((await dialog.boundingBox())!.y).toBeLessThanOrEqual(Math.max(8, mapTop) + 1);
    expect(await dialog.evaluate(el => el.scrollHeight <= el.clientHeight + 1)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath('source-context-in-ribbons.png') });
    await dialog.getByRole('button', { name: 'Close source details' }).click();
  }
  await line.click();
  for (const width of [1440, 700, 430, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await expect.poll(async () => {
      const box = (await dialog.boundingBox())!;
      const english = (await song.boundingBox())!;
      return box.x + box.width <= english.x - 7;
    }).toBe(true);
    await assertClear(dialog);
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  }
  await dialog.getByRole('button', { name: 'Close source details' }).click();
  await expect(line).toBeFocused();
});

test('source context stays near the visible map top and uses spare vertical space before scrolling', async ({ page }) => {
  await page.setViewportSize({ width: 2232, height: 1200 });
  const sources = await mountedFixture(page);
  const line = sources.getByRole('button', { name: 'Source evidence for song line 4', exact: true });
  await line.click();
  const dialog = sources.getByRole('dialog', { name: 'Source evidence', exact: true });
  await expect(dialog).toBeVisible();
  const initial = (await dialog.boundingBox())!;
  expect(initial.y + initial.height).toBeLessThan(1192);
  expect(await dialog.evaluate(el => el.scrollHeight <= el.clientHeight + 1)).toBe(true);
  // Page scrolling moves the map's top offscreen; the context stays at the viewport top.
  await sources.locator('.arr-sources__map').evaluate(el => window.scrollTo(0, window.scrollY + el.getBoundingClientRect().top + 30));
  await expect.poll(async () => (await dialog.boundingBox())!.y).toBeLessThanOrEqual(9);
  expect(await dialog.evaluate(el => el.scrollHeight <= el.clientHeight + 1)).toBe(true);
  await page.setViewportSize({ width: 2232, height: 400 });
  await expect.poll(async () => {
    const box = (await dialog.boundingBox())!;
    return box.y >= 7 && box.y + box.height <= 393;
  }).toBe(true);
  await page.setViewportSize({ width: 2232, height: 1200 });
  await expect.poll(() => dialog.evaluate(el => el.scrollHeight <= el.clientHeight + 1)).toBe(true);
  await dialog.getByRole('button', { name: 'Close source details' }).click();
  await expect(line).toBeFocused();
});

test('English lazily follows the visible source verse without scrolling the source or losing ribbons', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const sources = await mountedFixture(page, false, false, false, false, true);
  const verse = sources.getByRole('group', { name: 'Sources for Psalm 9:3', exact: true });
  const english = sources.getByRole('button', { name: 'Source evidence for song line 3', exact: true });
  const band = sources.locator('.arr-band[data-position="3"]');
  const originalBand = await band.getAttribute('d');
  const scrollToVerse = () => verse.evaluate(el => window.scrollTo(0, window.scrollY + el.getBoundingClientRect().top - 150));
  await page.mouse.move(1, 1);
  await scrollToVerse();
  const sourceTop = (await verse.boundingBox())!.y;
  const scrollY = await page.evaluate(() => window.scrollY);
  await expect(english).toBeInViewport();
  await expect.poll(async () => {
    const box = (await english.boundingBox())!;
    return box.y >= 0 && box.y + box.height <= 900;
  }).toBe(true);
  await expect.poll(() => band.getAttribute('d')).not.toBe(originalBand);
  expect((await verse.boundingBox())!.y).toBeCloseTo(sourceTop, 0);
  expect(await page.evaluate(() => window.scrollY)).toBe(scrollY);
  await expect(sources.locator('.arr-sung')).toHaveCount(4);
  await expect(sources.locator('.arr-sung__text')).toHaveText([1, 2, 3, 4].map(n => `Authored song line ${n}`));
  await page.screenshot({ path: testInfo.outputPath('english-following-source.png') });
  // Reading the right column must not fight the user's pointer or keyboard focus.
  await english.focus();
  await verse.evaluate(el => window.scrollBy(0, 100));
  const frozen = await sources.locator('.arr-sources__song').evaluate(el => getComputedStyle(el).transform);
  await expect.poll(() => sources.locator('.arr-sources__song').evaluate(el => getComputedStyle(el).transform)).toBe(frozen);
  await page.keyboard.press('Tab');
  await page.mouse.move(1, 1);
  await page.setViewportSize({ width: 430, height: 900 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  // Move focus to the source side before following another verse.
  await verse.getByRole('button', { name: 'Read source evidence for Psalm 9:3', exact: true }).focus();
  await scrollToVerse();
  await expect(english).toBeInViewport();
  await expect.poll(async () => (await english.boundingBox())!.y).toBeGreaterThanOrEqual(0);
  expect(await sources.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect.poll(() => sources.locator('.arr-sources__song').evaluate(el => getComputedStyle(el).transform)).toBe('matrix(1, 0, 0, 1, 0, 0)');
});

test('scroll tracking highlights every anchored English match and clears the previous verse', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 700 });
  const sources = await mountedFixture(page, false, false, false, false, true, true);
  const highlights = sources.locator('.arr-sung.is-reading');
  const showVerse = async (verse: number) => {
    await sources.getByRole('group', { name: `Sources for Psalm 9:${verse}`, exact: true })
      .evaluate(el => window.scrollTo(0, window.scrollY + el.getBoundingClientRect().top - 100));
  };
  await page.mouse.move(1, 1);
  await showVerse(3);
  await expect(highlights.locator('.arr-sung__text')).toHaveText(['Authored song line 3', 'Authored verse 3 reprise']);
  for (const highlight of await highlights.all()) await expect(highlight).toHaveAttribute('data-reading-source', unitId(3));
  await expect(sources.getByRole('button', { name: 'Source evidence for song line 6', exact: true })).not.toHaveClass(/is-reading/);
  await page.screenshot({ path: testInfo.outputPath('matching-English-lines-highlighted.png') });
  // Highlight tracking continues even while motion pauses for keyboard reading on the right.
  await sources.getByRole('button', { name: 'Source evidence for song line 3', exact: true }).focus();
  await showVerse(2);
  await expect(highlights.locator('.arr-sung__text')).toHaveText(['Authored song line 2']);
  await expect(highlights).toHaveAttribute('data-reading-source', unitId(2));
  await sources.getByRole('button', { name: 'Read source evidence for Psalm 9:2', exact: true }).focus();
  await showVerse(4);
  await expect(highlights.locator('.arr-sung__text')).toHaveText(['Authored song line 4']);
  await page.setViewportSize({ width: 430, height: 700 });
  await showVerse(3);
  await expect(highlights.locator('.arr-sung__text')).toHaveText(['Authored song line 3', 'Authored verse 3 reprise']);
});

test('arrangement cards show an explicit Greek blocked state for every verse', async ({ page }) => {
  const sources = await mountedFixture(page, true);
  for (const verse of [1, 2, 3, 4]) {
    const block = sources.getByRole('group', { name: `Sources for Psalm 9:${verse}`, exact: true });
    await expect(block.getByRole('heading', { name: 'Greek (LXX)', exact: true })).toBeVisible();
    await expect(block.getByText('Greek source blocked by current policy.', { exact: true })).toBeVisible();
    await expect(block.locator('.arr-greek-text')).toHaveCount(0);
  }
});

test('owner-approved display preview shows actual Greek without claiming lexical review', async ({ page }) => {
  let lexicalRequests = 0;
  page.on('request', request => { if (request.url().includes('/greek/tokens/')) lexicalRequests += 1; });
  const sources = await mountedFixture(page, false, false, true);
  const first = sources.getByRole('group', { name: 'Sources for Psalm 9:1', exact: true });
  await expect(first.getByRole('heading', { name: /Greek \(LXX\).*unreviewed preview/ })).toBeVisible();
  await expect(first.locator('.arr-greek-text').first()).toHaveText('λόγος·');
  await expect(first.getByRole('button', { name: /^Study Greek/ })).toHaveCount(0);
  await expect(first.getByText(/Greek word-by-word aid/)).toHaveCount(0);
  await first.getByRole('button', { name: 'Collapse source details for Psalm 9:1' }).click();
  await expect(first.locator('.arr-greek-text').first()).toHaveText('λόγος·');
  const unmapped = sources.getByRole('group', { name: 'Sources for Psalm 9:4', exact: true });
  await expect(unmapped.getByText(/No proposed Greek correspondence/)).toBeVisible();
  expect(lexicalRequests).toBe(0);
});

test.describe('long source details access', () => {
  test.use({ hasTouch: true, viewport: { width: 430, height: 640 } });

  test('viewport-spanning verse previews and multiverse source dialogs remain scrollable by pointer, keyboard and touch', async ({ page }, testInfo) => {
    const sources = await mountedFixture(page, false, true);
    const first = sources.getByRole('group', { name: 'Sources for Psalm 9:1', exact: true });
    await first.evaluate(element => window.scrollTo(0, window.scrollY + element.getBoundingClientRect().top + 100));
    const trigger = await first.boundingBox();
    expect(trigger!.y).toBeLessThan(0);
    expect(trigger!.y + trigger!.height).toBeGreaterThan(640);
    await page.mouse.move(trigger!.x + 8, 80);
    const preview = sources.getByRole('tooltip', { name: 'Source evidence', exact: true });
    await expect(preview).toBeVisible();
    const assertWithinViewport = async (card: typeof preview) => {
      const bounds = await card.boundingBox();
      const viewport = page.viewportSize()!;
      expect(bounds!.y).toBeGreaterThanOrEqual(7);
      expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(viewport.height - 7);
      expect(bounds!.x).toBeGreaterThanOrEqual(7);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width - 7);
    };
    await assertWithinViewport(preview);
    await preview.hover();
    await page.mouse.wheel(0, 900);
    await expect.poll(() => preview.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
    await page.mouse.wheel(0, 100000);
    await expect(preview.getByText('Authored song line 1', { exact: true })).toBeInViewport();
    await page.mouse.move(0, 0);
    await expect(preview).toHaveCount(0);

    const read = first.getByRole('button', { name: 'Read source evidence for Psalm 9:1', exact: true });
    await read.focus();
    await page.keyboard.press('Enter');
    const dialog = sources.getByRole('dialog', { name: 'Source evidence', exact: true });
    await expect(dialog).toBeFocused();
    await assertWithinViewport(dialog);
    await page.keyboard.press('End');
    await expect.poll(() => dialog.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
    await expect(dialog.getByText('Authored song line 1', { exact: true })).toBeInViewport();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(read).toBeFocused();

    const song = sources.getByRole('button', { name: 'Source evidence for song line 1', exact: true });
    await song.scrollIntoViewIfNeeded();
    await song.tap();
    await expect(dialog).toBeVisible();
    await assertWithinViewport(dialog);
    await expect(dialog.getByRole('heading', { name: /^Hebrew \(MT\)/ })).toHaveCount(4);
    await expect(dialog.getByRole('heading', { name: /^Greek \(LXX\)/ })).toHaveCount(4);
    const touch = await page.context().newCDPSession(page);
    const bounds = await dialog.boundingBox();
    const x = bounds!.x + bounds!.width / 2;
    const bottom = bounds!.y + bounds!.height - 60;
    await touch.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y: bottom }] });
    for (let offset = 40; offset <= 240; offset += 40) {
      await touch.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: bottom - offset }] });
    }
    await touch.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await touch.detach();
    await expect.poll(() => dialog.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
    await dialog.focus();
    await page.keyboard.press('End');
    await expect(dialog.getByText('Authored Hebrew literal 4', { exact: true })).toBeInViewport();
    await page.setViewportSize({ width: 430, height: 320 });
    await assertWithinViewport(dialog);
    await expect(dialog.getByRole('button', { name: 'Close source details', exact: true })).toBeInViewport();
    await page.screenshot({ path: testInfo.outputPath('long-source-details-clamped.png') });
    await dialog.getByRole('button', { name: 'Close source details', exact: true }).tap();
    await expect(dialog).toHaveCount(0);
    await expect(song).toBeFocused();
  });
});


test('visible dual-source flow preserves mixed phrases, mouseovers and the decision trail beneath it', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  const sources = await mountedFixture(page, false, false, false, true);
  const origins = page.getByRole('region', { name: 'Source decisions beneath the flow map' });
  await expect(sources.locator('.arr-sources__map')).toBeVisible();
  await expect(page.locator('.source-coverage-map')).toHaveCount(0);
  const line = sources.locator('.arr-sung').first();
  await expect(line.locator('.arr-origin-phrase--both')).toHaveText('song line');
  await expect(line.locator('.arr-origin-phrase--grc')).toHaveCount(2);
  const greekRibbon = sources.locator('.arr-band[data-position="1"][data-language="grc"]');
  const hebrewRibbon = sources.locator('.arr-band[data-position="1"][data-language="he"]');
  await expect(greekRibbon).toHaveCount(1);
  await expect(hebrewRibbon).toHaveCount(1);
  await expect(hebrewRibbon).toHaveAttribute('data-scope', 'phrase');
  expect(await greekRibbon.getAttribute('d')).not.toBe(await hebrewRibbon.getAttribute('d'));
  const mapBottom = await sources.locator('.arr-sources__map').evaluate(el => el.getBoundingClientRect().bottom);
  expect(await origins.evaluate(el => el.getBoundingClientRect().top)).toBeGreaterThan(mapBottom);
  const block = sources.getByRole('group', { name: 'Sources for Psalm 9:1', exact: true });
  const sourceHebrew = block.locator('[data-hebrew-token]').first();
  await sourceHebrew.hover();
  await expect(sources.getByRole('tooltip')).toContainText('song');
  await sourceHebrew.press('Escape');
  const sourceGreek = block.getByRole('button', { name: 'Study Greek λόγος · Greek Psalm 8:5', exact: true });
  await sourceGreek.hover();
  await expect(sources.getByRole('tooltip', { name: 'Greek word study' })).toContainText('λόγος');
  await sourceGreek.press('Escape');
  const before = await greekRibbon.getAttribute('d');
  await block.getByRole('button', { name: 'Collapse source details for Psalm 9:1' }).click();
  await expect.poll(() => greekRibbon.getAttribute('d')).not.toBe(before);
  await expect(hebrewRibbon).toHaveCount(1);
  await expect(origins.locator('.source-decision-trail')).not.toHaveAttribute('open', '');
  await origins.locator('.source-decision-trail > summary').click();
  const phrase = origins.getByRole('button', { name: 'View source choice for Psalm 9:1', exact: true });
  await phrase.click();
  const detail = origins.getByRole('region', { name: 'Source choice for Psalm 9:1', exact: true });
  await expect(detail).toContainText('Follow the Greek reading.');
  await expect(detail).toContainText('Preserve this recorded reason.');
  const hebrew = detail.locator('[lang="he"] [tabindex]').first();
  await hebrew.hover();
  await expect(origins.getByRole('tooltip')).toContainText('song');
  await hebrew.press('Escape');
  await expect(origins.getByRole('tooltip')).toHaveCount(0);
  await expect(detail).toBeVisible();
  const greek = detail.locator('[lang="grc"] [tabindex]').first();
  await greek.hover();
  const word = await greek.boundingBox();
  const tooltip = origins.getByRole('tooltip');
  await expect(tooltip).toContainText('λόγος');
  const card = await tooltip.boundingBox();
  expect(card!.y >= word!.y + word!.height || card!.y + card!.height <= word!.y).toBe(true);
  await greek.press('Escape');
  await expect(tooltip).toHaveCount(0);
  await detail.getByRole('button', { name: 'Close source detail' }).click();
  await expect(detail).toHaveCount(0);
  await expect(phrase).toBeFocused();
  await expect(origins.locator('.source-decision-trail')).toContainText('Follow the Greek reading.');
  await origins.getByRole('button', { name: 'View source choice for Psalm 9:1' }).click();
  await expect(detail).toBeVisible();
  await page.setViewportSize({ width: 360, height: 850 });
  expect(await sources.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  expect(await origins.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('source-origins-narrow.png'), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Verses', exact: true }).click();
  await expect(page.locator('.source-origins')).toHaveCount(0);
  await expect(page.locator('.verse-row__he').first()).toBeVisible();
  expect(errors).toEqual([]);
});
