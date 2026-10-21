import { expect, test, type Page } from '@playwright/test';

const identity = { study_snapshot_id: 'study.fixture', policy_revision_id: 'policy.fixture' };
const edition = { ...identity, edition_id: 'authored', text_revision_id: 'r0001' };
const query = { ...identity, query_kind: 'surface', value: 'λόγος', analysis_scope: 'all',
  analysis_selection: 'possible', match_unit: 'token', expand_components: false };
const token = { token_id: 'lxx.authored.r0001.ps001.v001.t001', surface: 'λόγος', position: 1 };

async function fixtures(page: Page, staleFirstPage = false) {
  await page.addInitScript(() => localStorage.setItem('aleph-tav.full-workbench', 'true'));
  await page.addInitScript(() => localStorage.setItem('aleph-tav.assistant-ui', JSON.stringify({
    visibility: 'closed', placement: 'footer',
  })));
  const writes: string[] = [];
  page.on('request', (request) => { if (request.method() !== 'GET') writes.push(request.url()); });
  await page.route('**/assistant/**', (route) => route.fulfill({ status: 503, body: '{}' }));
  await page.route('**/codex/**', (route) => route.fulfill({ status: 503, body: '{}' }));
  await page.route('**/psalms', (route) => route.fulfill({ json: [] }));
  await page.route('**/collections', (route) => route.fulfill({ json: [
    { collection_id: 'col.default', title: 'Empty project', members: [], built_in: true },
    { collection_id: 'col.other', title: 'Other empty project', members: [], built_in: false },
  ] }));
  await page.route('**/lxx/editions', (route) => route.fulfill({ json: { editions: [edition] } }));
  await page.route('**/lxx/psalms?*', (route) => route.fulfill({ json: { ...identity, psalms: [1, 9, 151] } }));
  await page.route('**/lxx/reader?*', async (route) => {
    const psalm = Number(new URL(route.request().url()).searchParams.get('psalm'));
    await route.fulfill({ json: { ...identity, units: [{
      unit_id: `lxx.authored.r0001.ps${String(psalm).padStart(3, '0')}.v001.a`,
      ref: `Greek Psalm ${psalm}:1`, source_greek: 'λόγος', tokens: [token],
    }] } });
  });
  await page.route('**/greek/tokens/*/card?*', (route) => route.fulfill({ json: {
    ...identity, token, query, counts: { total_matches: 2, total_tokens: 2, total_verses: 2 },
    analyses: [{ analysis_id: 'analysis-1', lemma: 'λόγος', status: 'proposed',
      raw_tag: 'N-NSM', scheme: 'fixture', identifiers: [{ scheme: 'eStrong', value: 'G1' }] }],
    dictionary_entries: [{ entry_id: 'fixture:word', headword: 'λόγος', attribution: {
      source_id: 'authored', license: 'CC0', required_attribution: 'Authored dictionary fixture',
    } }],
  } }));
  await page.route('**/greek/lexicon/entries/*?*', (route) => route.fulfill({ json: {
    ...identity, entry: { entry_id: 'fixture:word', headword: 'λόγος', presentation: {
      type: 'root', children: [{ type: 'paragraph', children: [
        { type: 'text', text: 'An authored word definition.' },
        { type: 'script', text: '<script>window.greekUnsafe = true</script>' },
      ] }],
    }, attribution: { source_id: 'authored', license: 'CC0', required_attribution: 'Authored dictionary fixture' },
      citations: [{ original_label: 'Psa.45.15', baseline: 'english_kjv' }],
    },
  } }));
  await page.route('**/greek/concordance?*', async (route) => {
    const params = new URL(route.request().url()).searchParams;
    expect(params.get('study_snapshot_id')).toBe(identity.study_snapshot_id);
    expect(params.get('policy_revision_id')).toBe(identity.policy_revision_id);
    if (staleFirstPage) { await route.fulfill({ status: 409, json: { code: 'study_stale' } }); return; }
    const next = params.has('cursor');
    await route.fulfill({ json: { ...identity, total_matches: 2, total_tokens: 2, total_verses: 2,
      next_cursor: next ? null : 'page-2', coverage: { unresolved: 1, statement: 'Unresolved analyses are not proven nonmatches.' },
      matches: [{ occurrence_id: next ? 'hit-151' : 'hit-1', unit_id: 'fixture',
        psalm: next ? 151 : 1, verse: 1, surface: 'λόγος' }],
    } });
  });
  return writes;
}

test('mounted empty-project reader supports keyboard, safe entry, complete pages, and Greek-only navigation', async ({ page }) => {
  const writes = await fixtures(page);
  await page.setViewportSize({ width: 430, height: 900 });
  await page.goto('/#/workbench');
  const panel = page.getByRole('region', { name: 'Greek source study' });
  await expect(panel).toBeVisible();
  await panel.getByLabel('Source view').selectOption('lxx');
  const word = panel.getByRole('button', { name: 'λόγος · Greek Psalm 1:1', exact: true });
  await word.focus();
  await page.keyboard.press('Enter');
  await expect(panel.getByText('Dictionary lemma:')).toBeVisible();
  await panel.getByRole('button', { name: 'Read λόγος' }).click();
  await expect(panel.getByText('An authored word definition.', { exact: false })).toBeVisible();
  await expect(panel.getByText('Psa.45.15 · english_kjv · external/unresolved reference')).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as Record<string, unknown>).greekUnsafe)).toBeUndefined();
  await panel.getByRole('button', { name: 'Close word study' }).focus();
  await page.keyboard.press('Escape');
  await expect(word).toBeFocused();
  await page.keyboard.press('Space');
  await panel.getByRole('button', { name: 'Next occurrences' }).click();
  await panel.getByRole('button', { name: 'Greek Psalm 151:1 · λόγος' }).click();
  await expect(panel.getByRole('heading', { name: 'Greek Psalm 151:1' })).toBeVisible();
  await expect(panel.getByText('No English translation in this project for this source view.')).toBeVisible();
  expect(writes.filter((url) => /translations|collections|renderings/.test(url))).toEqual([]);
  await page.getByRole('combobox', { name: 'Project', exact: true }).selectOption('col.other');
  await expect(panel.getByRole('complementary', { name: 'Greek word study' })).toHaveCount(0);
  expect(await panel.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
});

test('snapshot changes before the first dependent page produce a restart state', async ({ page }) => {
  await fixtures(page, true);
  await page.goto('/#/workbench');
  await page.getByLabel('Source view').selectOption('lxx');
  await page.getByRole('button', { name: 'λόγος · Greek Psalm 1:1', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Restart Greek study' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next occurrences' })).toHaveCount(0);
});

test('Greek 9 and 151 navigation preserves both MT 9 and MT 10 translation members', async ({ page }) => {
  const writes = await fixtures(page);
  await page.route('**/psalms', (route) => route.fulfill({ json: [
    { psalm_id: 'ps009', title: 'MT Psalm 9' }, { psalm_id: 'ps010', title: 'MT Psalm 10' },
  ] }));
  await page.route('**/collections', (route) => route.fulfill({ json: [{
    collection_id: 'col.default', title: 'MT ownership fixture', built_in: true, members: [
      { psalm_id: 'ps009', translation_id: 'translation-9' },
      { psalm_id: 'ps010', translation_id: 'translation-10' },
    ],
  }] }));
  await page.route('**/psalms/*/**', (route) => route.fulfill({ status: 503, body: '{}' }));
  await page.goto('/#/workbench');
  await page.getByLabel('Source view').selectOption('lxx');
  await page.getByLabel('Greek source psalm').selectOption('9');
  await expect(page.getByRole('heading', { name: 'Greek Psalm 9:1' })).toBeVisible();
  const mtPicker = page.getByRole('combobox', { name: /^Psalm/ });
  await expect(mtPicker).toHaveValue('ps009');
  await expect(mtPicker.locator('option[value="ps009"]')).toHaveCount(1);
  await expect(mtPicker.locator('option[value="ps010"]')).toHaveCount(1);
  await page.getByLabel('Greek source psalm').selectOption('151');
  await expect(page.getByRole('heading', { name: 'Greek Psalm 151:1' })).toBeVisible();
  await expect(mtPicker).toHaveValue('ps009');
  expect(writes.filter((url) => /translations|collections|renderings/.test(url))).toEqual([]);
});
