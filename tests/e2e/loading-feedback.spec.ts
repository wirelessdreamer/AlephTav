import { expect, test, type Page } from '@playwright/test';

const row = {
  mt_reference: 'Psalm 9:1', display_reference: 'Psalm 9:1', unit_ids: ['ps009.v001.a'],
  hebrew_text: 'שיר', tokens: [{ token_id: 'ps009.v001.t001', surface: 'שיר', display_gloss: 'song', occurrence_refs: [] }],
  literal_text: 'Authored literal', literal_rendering_ids: [], literal_status: 'draft', literal_links: [],
  english_text: 'Authored lyric', english_rendering_ids: [], english_status: 'draft', english_guidance: null,
  accuracy_rating: null, accuracy_note: '', creative_liberties_note: '', assessment_status: null,
  incomplete: false, literal_backbone: [], non_source_material: [], stale: false, verse_notes: [], word_choices: [], pending_rebuild: null,
};
const collections = [{ collection_id: 'col.default', title: 'Loading fixture', built_in: true,
  members: [{ psalm_id: 'ps009', translation_id: 'translation.fixture' }] }];
const psalms = [{ psalm_id: 'ps009', title: 'Psalm 9' }];
const arrangement = { arrangement_id: 'arr.fixture', psalm_id: 'ps009', title: 'Authored setting', layer: 'lyric',
  status: 'draft', guidance: '', created_via: 'human', sections: [], omissions: [], audit_ids: [] };
const arrangementView = { arrangement, sung: [], coverage: { units: [], totals: { words: 0, once: 0, repeated: 0, dropped: 0 } },
  liberties: [], summary: { sung_lines: 0, open: 0, by_kind: {} }, required_approvals: {} };

async function fixture(page: Page) {
  await page.addInitScript(() => localStorage.setItem('aleph-tav.assistant-ui', JSON.stringify({ visibility: 'closed', placement: 'footer' })));
  await page.route('**/assistant/**', route => route.fulfill({ status: 503, json: { detail: 'Authored unavailable service' } }));
  await page.route('**/codex/**', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/lxx/editions', route => route.fulfill({ json: { editions: [] } }));
  await page.route('**/collections', route => route.fulfill({ json: collections }));
  await page.route('**/psalms', route => route.fulfill({ json: psalms }));
  await page.route('**/psalms/ps009/comparison-table?*', route => route.fulfill({ json: { psalm_id: 'ps009', title: 'Psalm 9', rows: [row], analysis: null } }));
  await page.route('**/psalms/ps009/translation-guidance?*', route => route.fulfill({ json: { translation_guidance: 'Saved fixture guidance' } }));
  await page.route('**/psalms/ps009/briefing?*', route => route.fulfill({ json: { briefing: null, history: [], greek_sources: { available: false, by_mt_unit: {}, message: 'No authored Greek source.' } } }));
  await page.route('**/psalms/ps009/arrangements?*', route => route.fulfill({ json: { arrangements: [arrangement], refrains: [] } }));
  await page.route('**/psalms/ps009/arrangements/arr.fixture', route => route.fulfill({ json: arrangementView }));
}

// Controlled requests expose intermediate UI without timing-dependent sleeps.
async function hold(page: Page, pattern: string, json: unknown) {
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route(pattern, async route => { await gate; await route.fulfill({ json }); });
  return release;
}

test('startup distinguishes loading projects and psalms from missing content', async ({ page }) => {
  await fixture(page);
  const projects = await hold(page, '**/collections', collections);
  const list = await hold(page, '**/psalms', psalms);
  await page.goto('/#/workbench');
  await expect(page.getByRole('status').filter({ hasText: 'Loading projects…' })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'Loading psalms…' })).toBeVisible();
  await expect(page.getByText('Select a psalm to compare.', { exact: true })).toHaveCount(0);
  projects(); list();
  await expect(page.getByText('Authored lyric', { exact: true })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'Loading projects…' })).toHaveCount(0);
});

test('comparison and Sources report both stages of loading and finish with content', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await fixture(page);
  const comparison = await hold(page, '**/psalms/ps009/comparison-table?*', { psalm_id: 'ps009', title: 'Psalm 9', rows: [row], analysis: null });
  const settings = await hold(page, '**/psalms/ps009/arrangements?*', { arrangements: [arrangement], refrains: [] });
  const sources = await hold(page, '**/psalms/ps009/arrangements/arr.fixture', arrangementView);
  await page.goto('/#/workbench');
  await expect(page.getByRole('status').filter({ hasText: 'Loading comparison…' })).toBeVisible();
  comparison();
  await page.getByRole('button', { name: 'Sources', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Loading song settings…' })).toBeVisible();
  await expect(page.getByText('No song setting yet', { exact: true })).toHaveCount(0);
  settings();
  await expect(page.getByRole('status').filter({ hasText: 'Loading source flow and word meanings…' })).toBeVisible();
  await page.screenshot({ path: '.run/loading-feedback-sources.png' });
  sources();
  await expect(page.getByRole('textbox', { name: 'Setting title' })).toHaveValue('Authored setting');
  await expect(page.getByRole('status').filter({ hasText: 'Loading source flow' })).toHaveCount(0);
});

test('guidance stays protected while saved content loads, then becomes editable', async ({ page }) => {
  await fixture(page);
  const release = await hold(page, '**/psalms/ps009/translation-guidance?*', { translation_guidance: 'Saved fixture guidance' });
  await page.goto('/#/workbench');
  await page.getByRole('button', { name: 'Guidance', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Loading saved guidance…' })).toBeVisible();
  await expect(page.locator('#translation-guidance')).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Save guidance' })).toBeDisabled();
  release();
  await expect(page.locator('#translation-guidance')).toHaveValue('Saved fixture guidance');
  await expect(page.locator('#translation-guidance')).toBeEnabled();
});

test('a failed project request offers a working retry instead of a blank page', async ({ page }) => {
  await fixture(page);
  let recovered = false;
  await page.route('**/collections', route => recovered ? route.fulfill({ json: collections }) : route.fulfill({ status: 500, body: 'Fixture outage' }));
  await page.goto('/#/workbench');
  const error = page.getByRole('alert').filter({ hasText: 'Could not load projects.' });
  await expect(error).toBeVisible({ timeout: 15000 });
  recovered = true;
  await error.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByText('Authored lyric', { exact: true })).toBeVisible();
  await expect(error).toHaveCount(0);
});

test('Greek edition discovery is visible while pending and failures can be retried', async ({ page }) => {
  await fixture(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let recovered = false;
  await page.route('**/lxx/editions', async route => {
    await gate;
    await route.fulfill(recovered ? { json: { editions: [] } } : { status: 503, body: 'Fixture edition outage' });
  });
  await page.goto('/#/workbench');
  await expect(page.getByRole('status').filter({ hasText: 'Loading Greek editions…' })).toBeVisible();
  release();
  const error = page.getByRole('alert').filter({ hasText: 'Greek study unavailable.' });
  await expect(error).toBeVisible();
  recovered = true;
  await error.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByText('No Greek study editions available.', { exact: true })).toBeVisible();
});

test('assistant session errors stop retrying until asked and message waits show progress', async ({ page }) => {
  await fixture(page);
  let starts = 0;
  await page.route('**/assistant/sessions', route => {
    starts++;
    return route.fulfill(starts === 1 ? { status: 503, body: 'Fixture conversation outage' } : { json: { session_id: 'session.fixture' } });
  });
  const reply = await hold(page, '**/assistant/sessions/session.fixture/messages', {
    message: { role: 'assistant', content: 'Authored reply', created_at: '2026-10-21T12:00:00Z' },
  });
  await page.goto('/#/workbench');
  await page.getByRole('button', { name: /Open assistant/ }).click();
  const error = page.getByRole('alert').filter({ hasText: 'Could not start the assistant.' });
  await expect(error).toBeVisible();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  expect(starts).toBe(1);
  await error.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeEnabled();
  await page.getByPlaceholder('Ask the app to inspect, navigate, select, compare, review, transcribe, or prepare a change.').fill('Explain this authored verse');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Waiting for the assistant’s response…' })).toBeVisible();
  reply();
  await expect(page.getByText('Authored reply', { exact: true })).toBeVisible();
});

test('word choices and history show pending feedback without pretending they are empty', async ({ page }) => {
  await fixture(page);
  const choices = await hold(page, '**/units/ps009.v001.a/word-suggestions?*', { suggestions: [] });
  const history = await hold(page, '**/units/ps009.v001.a/verse-history?*', { events: [], rebuilds: [], translation_history: [] });
  await page.goto('/#/workbench');
  await page.getByRole('button', { name: /1 שיר Authored lyric/ }).click();
  await page.locator('.interlinear__word').first().click();
  await expect(page.getByRole('status').filter({ hasText: 'Loading saved word choices…' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Suggest renderings', exact: true })).toHaveCount(0);
  choices();
  await expect(page.getByRole('button', { name: 'Suggest renderings', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'History', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Loading history…' })).toBeVisible();
  await expect(page.getByText('This verse has not been rebuilt with notes.', { exact: true })).toHaveCount(0);
  history();
  await expect(page.getByText('This verse has not been rebuilt with notes.', { exact: true })).toBeVisible();
});

test('a failed comparison refresh retains the previously loaded translation', async ({ page }) => {
  await fixture(page);
  await page.goto('/#/workbench');
  await expect(page.getByText('Authored lyric', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'AlephTav home', exact: true }).click();
  await page.route('**/psalms/ps009/comparison-table?*', route => route.fulfill({ status: 503, body: 'Authored refresh failure' }));
  await page.locator('a[href="#/workbench"]').first().click();
  await expect(page.getByRole('status').filter({ hasText: 'Updating comparison…' })).toBeVisible();
  await expect(page.getByText('Authored lyric', { exact: true })).toBeVisible();
  await expect(page.getByRole('alert').filter({ hasText: 'Could not refresh comparison; showing saved content.' })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('Authored lyric', { exact: true })).toBeVisible();
});

test('an initially open assistant does not duplicate or orphan its session request', async ({ page }) => {
  await fixture(page);
  await page.addInitScript(() => localStorage.setItem('aleph-tav.assistant-ui', JSON.stringify({ visibility: 'open', placement: 'side' })));
  let starts = 0;
  await page.route('**/assistant/sessions', route => {
    starts++;
    return route.fulfill({ status: 503, body: 'Authored session failure' });
  });
  await page.goto('/#/workbench');
  await expect(page.getByRole('alert').filter({ hasText: 'Could not start the assistant.' })).toBeVisible();
  expect(starts).toBe(1);
});
