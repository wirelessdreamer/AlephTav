import { expect, test, type Page } from '@playwright/test';

import type { IntentionalTranslationChoice, RecordTranslationChoice, TranslationChoiceTarget } from '../../app/ui/src/types';

async function fixture(page: Page, repeat = false) {
  await page.addInitScript(() => localStorage.setItem('aleph-tav.full-workbench', 'true'));
  await page.addInitScript(() => localStorage.setItem('aleph-tav.assistant-ui', JSON.stringify({ visibility: 'closed', placement: 'footer' })));
  // Every API request is intercepted; these tests never use a live content service.
  await page.route('**/*', route => ['fetch', 'xhr'].includes(route.request().resourceType())
    ? route.fulfill({ status: 503, json: { detail: 'No live API in this fixture.' } }) : route.continue());
  const translationId = 'tr.authored';
  const targets: TranslationChoiceTarget[] = [1, 2].map(n => ({ kind: 'arrangement_line',
    id: `ln.${n}`, arrangement_id: 'arr.authored', translation_id: translationId, shared: false,
    layer: 'lyric', text: `Authored closing line ${n}`, context_text:
      ['Authored closing line 1', 'Authored closing line 2', ...(repeat ? ['Authored closing line 1'] : [])].join('\n'),
    revision: { version: 1, algorithm: 'sha256', value: String(n).repeat(64) } }));
  const lines = targets.map(target => ({ line_id: target.id, text: target.text,
    anchors: [], liberty: 'added', rationale: '', approvals: [] }));
  const arrangement = { arrangement_id: 'arr.authored', psalm_id: 'ps009', title: 'Authored setting',
    translation_id: translationId,
    layer: 'lyric', status: 'proposed', guidance: '', created_via: 'human', sections: [{
      section_id: 'sec.authored', kind: 'outro', label: 'Closing stanza', repeat_of: null, lines,
    }], omissions: [], audit_ids: [] };
  const row = { mt_reference: 'Psalm 9:1', display_reference: 'Psalm 9:1', unit_ids: ['ps009.v001.a'],
    hebrew_text: 'שיר', tokens: [], literal_text: null, literal_rendering_ids: [], literal_status: null,
    english_text: 'Authored verse', english_rendering_ids: [], english_status: 'proposed', english_guidance: null,
    accuracy_rating: null, accuracy_note: '', creative_liberties_note: '', assessment_status: null,
    incomplete: false, literal_backbone: [], non_source_material: [], stale: false, verse_notes: [],
    word_choices: [], pending_rebuild: null };
  const entries: IntentionalTranslationChoice[] = [];
  const posts: RecordTranslationChoice[] = [];
  let failNext = false;
  let briefingReads = 0;
  await page.route('**/lxx/editions', route => route.fulfill({ json: { editions: [] } }));
  await page.route('**/collections', route => route.fulfill({ json: [{ collection_id: 'col.default',
    title: 'Authored choices', built_in: true, members: [{ psalm_id: 'ps009', translation_id: translationId }] },
    { collection_id: 'col.other', title: 'Other authored choices', built_in: true,
      members: [{ psalm_id: 'ps009', translation_id: 'tr.other' }] }] }));
  await page.route('**/psalms', route => route.fulfill({ json: [{ psalm_id: 'ps009', title: 'Psalm 9' }] }));
  await page.route('**/psalms/ps009/comparison-table?*', route => route.fulfill({ json: {
    psalm_id: 'ps009', title: 'Psalm 9', rows: [row], analysis: null, canonical_numbering: null,
  } }));
  await page.route('**/psalms/ps009/translation-guidance?*', route => route.fulfill({ json: { translation_guidance: '' } }));
  await page.route('**/psalms/ps009/briefing?*', route => {
    briefingReads += 1;
    return route.fulfill({ json: { briefing: null, history: entries,
      greek_sources: { available: false, by_mt_unit: {} } } });
  });
  await page.route('**/psalms/ps009/arrangements?*', route => route.fulfill({ json: { arrangements: [arrangement], refrains: [] } }));
  const arrangementView = {
    arrangement, sung: [...lines, ...(repeat ? [lines[0]] : [])].map((line, i) => ({ position: i + 1, section_id: 'sec.authored',
      section_label: 'Closing stanza', kind: 'outro', time: 1, repeat: false, variation: false, line })),
    coverage: { units: [], totals: { words: 0, once: 0, repeated: 0, dropped: 0 } },
    liberties: [], summary: { sung_lines: 2, open: 0, by_kind: {} }, required_approvals: {},
  };
  await page.route('**/psalms/ps009/arrangements/arr.authored', route => route.fulfill({ json: arrangementView }));
  await page.route('**/psalms/ps009/translation-choices**', async route => {
    if (route.request().method() === 'GET') {
      const params = new URL(route.request().url()).searchParams;
      const owner = params.get('translation_id');
      expect([translationId, 'tr.other']).toContain(owner);
      const scopedTargets = params.has('unit_id') ? [{ ...targets[0], kind: 'rendering', id: 'rnd.authored',
        arrangement_id: undefined, unit_id: params.get('unit_id'), translation_id: owner }] :
        targets.map(target => ({ ...target, translation_id: owner }));
      return route.fulfill({ json: { psalm_id: 'ps009', translation_id: owner, targets: scopedTargets, choices: entries } });
    }
    const body = route.request().postDataJSON() as RecordTranslationChoice;
    posts.push(body);
    if (failNext) {
      failNext = false;
      targets[0] = { ...targets[0], text: 'Authored revised closing line', revision: {
        version: 1, algorithm: 'sha256', value: 'f'.repeat(64),
      } };
      return route.fulfill({ status: 400, json: { detail: 'Choice target changed; reload before recording the choice' } });
    }
    const auditId = `audit.choice.${entries.length + 1}`;
    const entry: IntentionalTranslationChoice = { audit_id: auditId, created_at: '2026-11-05T12:00:00Z',
      created_by: body.created_by, summary: 'Record intentional translation choice', kind: 'intentional_choice',
      choice: { version: 1, targets: body.targets.map(target => ({ ...targets.find(item => item.id === target.id)! })),
        decision: body.decision, rationale: body.rationale, context_status: body.context_status,
        context_note: body.context_note, supersedes_audit_id: body.supersedes_audit_id ?? null },
      target_state: 'current', superseded_by_audit_id: null, counts_for_publication: false };
    const prior = entries.find(item => item.audit_id === body.supersedes_audit_id);
    if (prior) prior.superseded_by_audit_id = auditId;
    entries.push(entry);
    return route.fulfill({ json: entry });
  });
  await page.goto('/#/workbench');
  await page.getByRole('button', { name: 'Liberties', exact: true }).click();
  const panel = page.locator('details').filter({ has: page.locator(':scope > summary', { hasText: /^Intentional translation choices/ }) });
  await panel.locator(':scope > summary').click();
  return { panel, posts, entries, targets, arrangementView,
    staleNext: () => { failNext = true; }, briefingReads: () => briefingReads,
    changeTarget: () => {
      targets[0] = { ...targets[0], text: 'Background changed closing line',
        revision: { version: 1, algorithm: 'sha256', value: 'b'.repeat(64) } };
    } };
}

async function fill(page: Page) {
  await page.getByRole('checkbox', { name: /ln.1:/ }).check();
  await page.getByRole('checkbox', { name: /ln.2:/ }).check();
  await page.getByRole('textbox', { name: 'Intentional choice', exact: true }).fill('Keep the closing pair together.');
  await page.getByRole('textbox', { name: 'Reason for this choice', exact: true }).fill('The two lines form a deliberate final phrase.');
  await page.getByRole('textbox', { name: 'Context note', exact: true }).fill('The translator’s supporting source context has not been established.');
  await page.getByRole('textbox', { name: 'Recorded by', exact: true }).fill('Fixture recorder');
}

test('missing context stays explicit, stale save keeps the draft, and refresh binds both current lines', async ({ page }) => {
  const state = await fixture(page);
  await expect(page.getByRole('combobox', { name: 'Supporting context', exact: true })).toHaveValue('not_established');
  await fill(page);
  await page.getByRole('textbox', { name: 'Context note', exact: true }).fill('');
  await expect(page.getByRole('button', { name: 'Record choice', exact: true })).toBeDisabled();
  await page.getByRole('textbox', { name: 'Context note', exact: true }).fill('Supporting context is unknown.');
  state.staleNext();
  await page.getByRole('button', { name: 'Record choice', exact: true }).click();
  await expect(state.panel.getByRole('alert')).toContainText('Refresh targets');
  await expect(page.getByRole('textbox', { name: 'Intentional choice', exact: true })).toHaveValue('Keep the closing pair together.');
  await expect(page.getByRole('textbox', { name: 'Context note', exact: true })).toHaveValue('Supporting context is unknown.');
  await expect(page.getByRole('checkbox', { checked: true })).toHaveCount(2);
  await expect(page.getByRole('button', { name: 'Record choice', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Refresh targets' }).click();
  await expect(page.getByRole('checkbox', { name: /Authored revised closing line/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Record choice', exact: true })).toBeDisabled();
  await expect(state.panel.getByRole('alert')).toContainText('Selected: Authored closing line 1');
  await page.getByRole('button', { name: 'Use current wording for selected targets', exact: true }).click();
  await page.getByRole('button', { name: 'Record choice', exact: true }).click();
  await expect(state.panel.getByRole('status')).toHaveText('Choice recorded.');
  expect(state.posts).toHaveLength(2);
  expect(state.posts[1].targets.map(target => target.id)).toEqual(['ln.1', 'ln.2']);
  expect(state.posts[1].targets[0].expected_revision).toBe('f'.repeat(64));
  expect(state.posts[1].context_status).toBe('not_established');
  expect(state.briefingReads()).toBeGreaterThan(1);
});

test('a background refetch cannot silently replace a selected revision', async ({ page }) => {
  const state = await fixture(page);
  await fill(page);
  state.changeTarget();
  const refetched = page.waitForResponse(response => response.request().method() === 'GET' &&
    response.url().includes('/translation-choices?'));
  await page.evaluate(() => window.dispatchEvent(new Event('visibilitychange')));
  await refetched;
  await expect(page.getByRole('checkbox', { name: /Background changed closing line/ })).toBeVisible();
  await expect(state.panel.getByRole('alert')).toContainText('Selected: Authored closing line 1');
  await expect(state.panel.getByRole('alert')).toContainText('Current: Background changed closing line');
  await expect(page.getByRole('textbox', { name: 'Reason for this choice', exact: true }))
    .toHaveValue('The two lines form a deliberate final phrase.');
  await expect(page.getByRole('button', { name: 'Record choice', exact: true })).toBeDisabled();
  // Even a submit event cannot bypass the changed-selection guard.
  await page.getByRole('form', { name: 'Record intentional translation choice' })
    .evaluate(form => form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  expect(state.posts).toHaveLength(0);
  await state.panel.screenshot({ path: '.run/choices-01a1ae05/choice-changed-selection.png' });
  await page.getByRole('button', { name: 'Use current wording for selected targets', exact: true }).click();
  await page.getByRole('button', { name: 'Record choice', exact: true }).click();
  await expect(state.panel.getByRole('status')).toHaveText('Choice recorded.');
  expect(state.posts).toHaveLength(1);
  expect(state.posts[0].targets[0].expected_revision).toBe('b'.repeat(64));
});

test('corrections append records and history displays supplied context without inventing old guidance', async ({ page }) => {
  const state = await fixture(page);
  await fill(page);
  await page.getByRole('button', { name: 'Record choice', exact: true }).click();
  await expect(state.panel.getByRole('status')).toHaveText('Choice recorded.');
  state.changeTarget();
  await page.getByRole('button', { name: 'Refresh targets' }).click();
  await expect(page.getByRole('checkbox', { name: /Background changed closing line/ })).toBeVisible();
  await state.panel.getByText(/^Recorded 2026/).click();
  await state.panel.getByRole('button', { name: 'Append a correction' }).click();
  await expect(page.getByRole('checkbox', { checked: true })).toHaveCount(2);
  await state.panel.screenshot({ path: '.run/choices-01a1ae05/choice-form-and-history.png' });
  await page.setViewportSize({ width: 430, height: 900 });
  expect(await state.panel.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
  await state.panel.screenshot({ path: '.run/choices-01a1ae05/choice-form-mobile.png' });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole('textbox', { name: 'Reason for this choice', exact: true }).fill('A corrected explanation supplied now.');
  await page.getByRole('combobox', { name: 'Supporting context', exact: true }).selectOption('provided_by_translator');
  await page.getByRole('textbox', { name: 'Context note', exact: true }).fill('Translator supplied this explanation; no source verification recorded.');
  await page.getByRole('button', { name: 'Append correction', exact: true }).click();
  await expect(state.panel.getByRole('status')).toHaveText('Choice recorded.');
  expect(state.entries).toHaveLength(2);
  expect(state.entries[0].choice.rationale).toBe('The two lines form a deliberate final phrase.');
  expect(state.entries[1].choice.supersedes_audit_id).toBe('audit.choice.1');
  expect(state.entries[0].superseded_by_audit_id).toBe('audit.choice.2');
  expect(state.posts[1].targets[0].expected_revision).toBe('b'.repeat(64));
  await page.getByRole('button', { name: /^Briefing/ }).click();
  const history = page.locator('details').filter({ has: page.locator(':scope > summary', { hasText: /^Briefing, guidance & choices history/ }) });
  await history.locator(':scope > summary').click();
  await history.locator('li > details > summary').first().click();
  await expect(history.getByText('Context supplied by translator', { exact: true })).toBeVisible();
  await expect(history.getByText('This records supplied context; it does not verify a source claim.')).toBeVisible();
  await expect(history.getByText('Guidance at this step')).toHaveCount(0);
  await expect(history.getByText('(none)', { exact: true })).toHaveCount(0);
});

test('switching translations clears the local choice draft', async ({ page }) => {
  await fixture(page);
  await fill(page);
  await page.getByRole('combobox', { name: 'Project', exact: true }).selectOption('col.other');
  const panel = page.locator('details').filter({ has: page.locator(':scope > summary', { hasText: /^Intentional translation choices/ }) });
  await panel.locator(':scope > summary').click();
  await expect(page.getByRole('textbox', { name: 'Intentional choice', exact: true })).toHaveValue('');
  await expect(page.getByRole('textbox', { name: 'Reason for this choice', exact: true })).toHaveValue('');
  await expect(page.getByRole('textbox', { name: 'Context note', exact: true })).toHaveValue('');
  await expect(page.getByRole('textbox', { name: 'Recorded by', exact: true })).toHaveValue('');
  await expect(page.getByRole('checkbox', { checked: true })).toHaveCount(0);
});

test('verse History mounts the same recorder with the unit scope', async ({ page }) => {
  await fixture(page);
  await page.route('**/units/ps009.v001.a/verse-history?*', route => route.fulfill({ json: {
    unit_id: 'ps009.v001.a', events: [], translation_history: [], translation_contexts: [], rebuilds: [], notes: [],
  } }));
  await page.getByRole('button', { name: 'Verses', exact: true }).click();
  await page.locator('.verse-row').first().click();
  const loaded = page.waitForRequest(request => request.url().includes('/translation-choices?') &&
    new URL(request.url()).searchParams.get('unit_id') === 'ps009.v001.a');
  await page.getByRole('tab', { name: 'History', exact: true }).click();
  await loaded;
  const panel = page.locator('details').filter({ has: page.locator(':scope > summary', { hasText: /^Intentional translation choices/ }) });
  await panel.locator(':scope > summary').click();
  await expect(page.getByRole('checkbox', { name: /rnd.authored/ })).toBeVisible();
});

function contextEntry(targets: TranslationChoiceTarget[], auditId: string, note: string): IntentionalTranslationChoice {
  return { audit_id: auditId, created_at: '2026-11-05T12:00:00Z', created_by: 'Authored recorder',
    summary: 'Record intentional translation choice', kind: 'intentional_choice',
    choice: { version: 1, targets, decision: 'Retain the authored closing pair.', rationale: 'Recorded creative choice.',
      context_status: 'not_established', context_note: note, supersedes_audit_id: null },
    target_state: 'current', superseded_by_audit_id: null, counts_for_publication: false };
}

async function clipboard(page: Page, fail = false) {
  await page.evaluate(shouldFail => Object.defineProperty(navigator, 'clipboard', { configurable: true,
    value: { writeText: async (text: string) => {
      if (shouldFail) throw new Error('Authored clipboard failure');
      (window as Window & { copiedLyrics?: string }).copiedLyrics = text;
    } },
  }), fail);
}

test('lyric footnotes group multiple targets and repeats, copy context, and keep hash navigation stable', async ({ page }) => {
  const state = await fixture(page, true);
  const original = 'Original textual context: שִׁיר (song). Unreviewed literal context; supporting historical context is not established.';
  const current = contextEntry(state.targets, 'audit.current', original);
  state.entries.push(
    { ...contextEntry(state.targets, 'audit.superseded', 'Superseded context must not attach.'), superseded_by_audit_id: current.audit_id },
    { ...contextEntry(state.targets, 'audit.changed', 'Changed context must not attach.'), target_state: 'changed' },
    { ...contextEntry(state.targets, 'audit.missing', 'Missing context must not attach.'), target_state: 'missing' },
    contextEntry([{ ...state.targets[0], arrangement_id: 'arr.other' }], 'audit.foreign', 'Other arrangement must not attach.'),
    contextEntry([{ ...state.targets[0], translation_id: 'tr.other' }], 'audit.owner', 'Other translation must not attach.'),
    contextEntry([{ ...state.targets[0], revision: { version: 1, algorithm: 'sha256', value: 'f'.repeat(64) } }],
      'audit.revision', 'Mismatched revision must not attach.'), current,
  );
  await page.getByRole('button', { name: 'Raw text', exact: true }).click();
  const sheet = page.locator('.arr-text__sheet');
  await expect(sheet).toContainText('Authored closing line 1[1]');
  expect((await sheet.textContent())?.match(/Authored closing line 1\[1\]/g)).toHaveLength(2);
  await expect(sheet.getByRole('link')).toHaveCount(3);
  const notes = page.getByRole('region', { name: 'Context footnotes', exact: true });
  await expect(notes.locator('ol > li')).toHaveCount(1);
  await expect(notes).toContainText(original);
  await expect(notes).not.toContainText('must not attach');
  const marker = sheet.getByRole('link', { name: 'Context footnote 1 for lyric line 1', exact: true });
  await marker.click();
  await expect(notes.locator('li')).toBeFocused();
  expect(new URL(page.url()).hash).toBe('#/workbench');
  await notes.getByRole('link', { name: 'Back to lyric line 3 from footnote 1', exact: true }).click();
  await expect(sheet.getByRole('link', { name: 'Context footnote 1 for lyric line 3', exact: true })).toBeFocused();
  expect(new URL(page.url()).hash).toBe('#/workbench');
  await clipboard(page);
  await page.getByRole('button', { name: 'Copy text with footnotes', exact: true }).click();
  expect(await page.evaluate(() => (window as Window & { copiedLyrics?: string }).copiedLyrics)).toBe(
    `Authored setting\n\n[Closing stanza]\nAuthored closing line 1[1]\nAuthored closing line 2[1]\nAuthored closing line 1[1]\n\nContext footnotes\n[1] ${original}`);
  await page.locator('.arr-text').screenshot({ path: '.run/choices-01a1ae05/lyric-context-footnotes.png' });
});

test('plain lyric copy stays clean and clipboard errors remain visible when no footnotes apply', async ({ page }) => {
  await fixture(page);
  await page.getByRole('button', { name: 'Raw text', exact: true }).click();
  const copy = page.getByRole('button', { name: 'Copy text', exact: true });
  await expect(copy).toBeEnabled();
  await expect(page.getByRole('region', { name: 'Context footnotes', exact: true })).toHaveCount(0);
  await clipboard(page, true);
  await copy.click();
  await expect(page.getByText('Copy failed; select the text instead.', { exact: true })).toBeVisible();
  await clipboard(page);
  await copy.click();
  expect(await page.evaluate(() => (window as Window & { copiedLyrics?: string }).copiedLyrics)).toBe(
    'Authored setting\n\n[Closing stanza]\nAuthored closing line 1\nAuthored closing line 2');
});

test('footnote loading and errors block copying without hiding the lyrics', async ({ page }) => {
  const state = await fixture(page);
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/psalms/ps009/translation-choices**', async route => {
    await gate;
    await route.fulfill({ status: 500, json: { detail: 'Authored context service failure' } });
  });
  await page.getByRole('button', { name: 'Raw text', exact: true }).click();
  const copy = page.getByRole('button', { name: 'Copy text', exact: true });
  await expect(copy).toBeDisabled();
  await expect(page.getByRole('status').filter({ hasText: 'Loading context footnotes' })).toBeVisible();
  await expect(page.locator('.arr-text__sheet')).toContainText('Authored closing line 1');
  release();
  await expect(page.getByRole('alert').filter({ hasText: 'Could not load context footnotes' })).toBeVisible({ timeout: 15_000 });
  await expect(copy).toBeDisabled();
  expect(state.posts).toHaveLength(0);
});

test('arrangement edits recheck cached footnotes even when lyric wording stays the same', async ({ page }) => {
  const state = await fixture(page);
  state.entries.push(contextEntry(state.targets, 'audit.current', 'Original textual context: authored unreviewed aid.'));
  await page.getByRole('button', { name: 'Raw text', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Copy text with footnotes', exact: true })).toBeEnabled();
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/psalms/ps009/translation-choices**', async route => {
    await gate;
    await route.fulfill({ json: { psalm_id: 'ps009', translation_id: 'tr.authored',
      targets: state.targets, choices: state.entries } });
  });
  await page.route('**/psalms/ps009/arrangements/arr.authored', async route => {
    if (route.request().method() !== 'PATCH') return route.fallback();
    state.arrangementView.arrangement.title = route.request().postDataJSON().title;
    state.entries[0].target_state = 'changed';
    await route.fulfill({ json: state.arrangementView });
  });
  const checking = page.waitForRequest(request => request.url().includes('/translation-choices?'));
  await page.getByRole('textbox', { name: 'Setting title', exact: true }).fill('Renamed setting');
  await page.getByRole('textbox', { name: 'Setting title', exact: true }).press('Tab');
  await checking;
  await expect(page.getByRole('button', { name: 'Copy text', exact: true })).toBeDisabled();
  await expect(page.getByRole('region', { name: 'Context footnotes', exact: true })).toHaveCount(0);
  await expect(page.locator('.arr-text__sheet')).toContainText('Authored closing line 1');
  release();
  await expect(page.getByRole('button', { name: 'Copy text', exact: true })).toBeEnabled();
  await expect(page.getByRole('region', { name: 'Context footnotes', exact: true })).toHaveCount(0);
});

test('annotation footnotes stay attached to archived quotations with unique links across duplicate views', async ({ page }) => {
  const state = await fixture(page);
  state.entries.push({ ...contextEntry(state.targets, 'audit.archived',
    'Original textual context: authored unreviewed aid. Historical supporting context remains unknown.'),
    target_state: 'changed', superseded_by_audit_id: 'audit.later' });
  await page.getByRole('button', { name: 'Refresh targets', exact: true }).click();
  await state.panel.getByText(/^Recorded 2026/).click();
  const recorded = state.panel.getByRole('list', { name: 'Recorded context footnotes', exact: true });
  await expect(recorded).toContainText('Original textual context:');
  await state.panel.getByRole('link', { name: 'Context footnote 1 for ln.1', exact: true }).click();
  await expect(recorded.locator('li')).toBeFocused();
  await recorded.getByRole('link', { name: 'Back to ln.1', exact: true }).click();
  await expect(state.panel.getByRole('link', { name: 'Context footnote 1 for ln.1', exact: true })).toBeFocused();
  expect(new URL(page.url()).hash).toBe('#/workbench');
  const briefingUpdated = page.waitForResponse(response => response.url().includes('/briefing?'));
  await page.evaluate(() => window.dispatchEvent(new Event('visibilitychange')));
  await briefingUpdated;
  await page.getByRole('button', { name: /^Briefing/ }).click();
  const history = page.locator('details').filter({ has: page.locator(':scope > summary', { hasText: /^Briefing, guidance & choices history/ }) });
  await history.locator(':scope > summary').click();
  await history.locator('li > details > summary').first().click();
  await expect(page.getByRole('list', { name: 'Recorded context footnotes', exact: true })).toHaveCount(2);
  const ids = await page.locator('[id]').evaluateAll(elements => elements.map(element => element.id));
  expect(ids.length).toBe(new Set(ids).size);
  const reference = history.getByRole('link', { name: 'Context footnote 1 for ln.2', exact: true });
  await reference.click();
  await expect(history.getByRole('list', { name: 'Recorded context footnotes', exact: true }).locator('li')).toBeFocused();
  expect(new URL(page.url()).hash).toBe('#/workbench');
});
