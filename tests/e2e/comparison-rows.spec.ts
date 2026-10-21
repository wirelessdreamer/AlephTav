import { expect, test } from '@playwright/test';

test('imported untranslated headings stay separate from Hebrew and align with verse rows', async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.setItem('aleph-tav.full-workbench', 'true'));
  await page.addInitScript(() => localStorage.setItem('aleph-tav.assistant-ui', JSON.stringify({ visibility: 'closed', placement: 'footer' })));
  const row = (verse: number, heading = false) => ({
    mt_reference: `Psalm 8:${verse}`, display_reference: heading ? 'Psalm 8 heading' : `Psalm 8:${verse - 1}`,
    unit_ids: [`ps008.v00${verse}.a`], hebrew_text: 'לַמְנַצֵּחַ עַל־הַגִּתִּית מִזְמוֹר לְדָוִד', tokens: [],
    literal_text: null, literal_rendering_ids: [], literal_status: null,
    english_text: heading ? null : 'O Yahweh, our Lord, how majestic is your name.',
    english_rendering_ids: heading ? [] : ['imported.lyric'], english_status: heading ? null : 'proposed',
    english_guidance: null, accuracy_rating: null, accuracy_note: '', creative_liberties_note: '',
    assessment_status: null, created_via: heading ? null : 'import', generator_provider: null,
    comparison_id: null, incomplete: heading, literal_backbone: [], non_source_material: [],
    stale: false, verse_notes: [], word_choices: [], pending_rebuild: null,
  });
  await page.route('**/assistant/**', route => route.fulfill({ status: 503, body: '{}' }));
  await page.route('**/codex/**', route => route.fulfill({ status: 503, body: '{}' }));
  await page.route('**/lxx/editions', route => route.fulfill({ json: { editions: [] } }));
  await page.route('**/collections', route => route.fulfill({ json: [{
    collection_id: 'col.default', title: 'Imported translation', built_in: true,
    members: [{ psalm_id: 'ps008', translation_id: 'tr.ps008.0001' }],
  }] }));
  await page.route('**/psalms', route => route.fulfill({ json: [{ psalm_id: 'ps008', title: 'Psalm 8' }] }));
  await page.route('**/psalms/ps008/comparison-table?*', route => route.fulfill({ json: {
    psalm_id: 'ps008', title: 'Psalm 8', rows: [row(1, true), row(2)], analysis: null, canonical_numbering: null,
  } }));
  await page.route('**/psalms/ps008/briefing?*', route => route.fulfill({ json: {
    briefing: null, history: [], greek_sources: { available: false, by_mt_unit: {} },
  } }));
  await page.route('**/psalms/ps008/translation-guidance?*', route => route.fulfill({ json: { translation_guidance: '' } }));
  await page.goto('/#/workbench');
  const heading = page.locator('.verse-row').filter({ has: page.getByText('Heading', { exact: true }) });
  await expect(heading.locator('.verse-row__en')).toHaveText('Not translated');

  for (const width of [1440, 820, 430]) {
    await page.setViewportSize({ width, height: 950 });
    const layout = await heading.evaluate(element => {
      const label = element.querySelector('.verse-row__n')!;
      const source = element.querySelector('.verse-row__he')!;
      const english = element.querySelector('.verse-row__en')!;
      const text = document.createRange();
      text.selectNodeContents(label);
      const next = getComputedStyle(source).display === 'none' ? english : source;
      return { labelRight: text.getBoundingClientRect().right, nextLeft: next.getBoundingClientRect().left };
    });
    expect(layout.labelRight, `Heading overlaps the next column at ${width}px`).toBeLessThanOrEqual(layout.nextLeft);
    const starts = await page.locator('.verse-row__en').evaluateAll(elements => elements.map(element => element.getBoundingClientRect().left));
    expect(starts[0]).toBe(starts[1]);
    await page.screenshot({ path: testInfo.outputPath(`heading-${width}.png`) });
  }
});
