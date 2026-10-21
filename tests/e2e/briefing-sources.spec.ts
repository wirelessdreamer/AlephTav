import { expect, test, type Page } from '@playwright/test';

async function briefingFixture(page: Page, { sourceGate = undefined as Promise<void> | undefined, briefingGate = undefined as Promise<void> | undefined, preview = true, generation = false, lexical = false, missing = false, review = false, markVariant = false, long = false, literal = null as string | null, decisions = false, inference = false } = {}) {
  await page.addInitScript(() => localStorage.setItem('aleph-tav.assistant-ui', JSON.stringify({ visibility: 'closed', placement: 'footer' })));
  const tokenId = 'lxx.authored.r0001.ps025.v001.t001';
  const identity = { study_snapshot_id: 'study.fixture', policy_revision_id: 'policy.fixture' };
  const row = {
    mt_reference: 'Psalm 26:1', display_reference: 'Psalm 26:1', unit_ids: ['ps026.v001.a'],
    hebrew_text: 'שָׁפְטֵנִי יְהוָה', tokens: [
      { token_id: 'ps026.v001.t001', surface: 'שָׁפְטֵנִי', display_gloss: 'judge me', occurrence_count: 1, occurrence_refs: [] },
      { token_id: 'ps026.v001.t002', surface: 'יְהוָה', gloss_parts: ['Yahweh'], occurrence_count: 1, occurrence_refs: [] },
      { token_id: 'ps026.v001.t003', surface: 'אֲנִי', occurrence_count: 1, occurrence_refs: [] },
    ],
    literal_text: literal, literal_rendering_ids: [], literal_status: null,
    english_text: null, english_rendering_ids: [], english_status: null,
    english_guidance: null, accuracy_rating: null, accuracy_note: '', creative_liberties_note: '',
    assessment_status: null, created_via: null, generator_provider: null, comparison_id: null,
    incomplete: true, literal_backbone: [], non_source_material: [], stale: false, verse_notes: [],
    word_choices: [], pending_rebuild: null,
  };
  const greek = {
    available: true, preview, generation_available: generation, lexical_preview: lexical, ...(preview ? {} : identity), edition_id: 'authored', text_revision_id: 'r0001',
    source_attribution: [{ attribution: 'Authored Greek fixture', license: 'CC0' },
      { attribution: 'Authored STEP dictionary fixture', license: 'CC BY 4.0' }],
    by_mt_unit: { 'ps026.v001.a': { relations: ['equivalent'], units: [{
      unit_id: 'lxx.authored.r0001.ps025.v001.a', ref: 'Greek Psalm 25:1',
      source_greek: review ? 'τόπαν με, Κύριε.' : markVariant ? 'ἰνα με, Κύριε.' : 'Κρῖνόν με, Κύριε.', partial: false,
      literal_text: review ? '[place?] · me · Lord' : markVariant ? '[so that?] · me · Lord' : preview && !lexical ? '? · ? · ?' : 'judge · me · Lord',
      tokens: [
        { token_id: tokenId, surface: review ? 'τόπαν' : markVariant ? 'ἰνα' : 'Κρῖνόν', gloss: review ? 'place' : markVariant ? 'so that' : missing || (preview && !lexical) ? null : 'judge',
          lookup_status: review ? 'possible_variant' : markVariant ? 'mark_variant' : 'matched',
          ...(lexical ? { analyses: missing ? [] : [{ lemma: 'κρίνω', status: 'proposed', scheme: 'MorphGNT', raw_tag: '2AAD-S--',
            features: { mood: 'imperative', voice: 'active', degree: null },
            ...(review ? { lemma: 'τόπον', scheme: 'Possible source reading', raw_tag: '', features: {},
              lookup_note: 'Printed τόπαν; possible reading τόπον. The reading needs review.' } : {}),
            ...(markVariant ? { lemma: 'ἵνα', scheme: 'Accent/breathing variant context', raw_tag: '', features: {},
              lookup_note: 'Printed ἰνα; possible context for ἵνα. Needs lexical review.' } : {}) }],
          dictionary_entries: missing ? [] : [{ entry_id: 'step.fixture', headword: markVariant ? 'ἵνα' : 'κρίνω',
            gloss: (markVariant ? 'so that' : 'to judge') + (long ? ' · alternative sense'.repeat(100) : ''),
            attribution: { required_attribution: 'Authored STEP dictionary fixture', license: 'CC BY 4.0' } }] } : {}) },
        { token_id: tokenId.replace('t001', 't002'), surface: 'με', gloss: preview && !lexical ? null : 'me' },
        { token_id: tokenId.replace('t001', 't003'), surface: 'Κύριε', gloss: preview && !lexical ? null : 'Lord' },
      ],
    }] } },
  };
  await page.route('**/assistant/**', route => route.fulfill({ status: 503, body: '{}' }));
  await page.route('**/codex/**', route => route.fulfill({ status: 503, body: '{}' }));
  if (decisions) await page.route('**/codex/status', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/lxx/editions', route => route.fulfill({ json: { editions: [] } }));
  await page.route('**/collections', route => route.fulfill({ json: [{ collection_id: 'col.default',
    title: 'Briefing fixture', built_in: true, members: [{ psalm_id: 'ps026', translation_id: 'tr.fixture' }] }] }));
  await page.route('**/psalms', route => route.fulfill({ json: [{ psalm_id: 'ps026', title: 'Psalm 26' }] }));
  await page.route('**/psalms/ps026/comparison-table?*', route => route.fulfill({ json: {
    psalm_id: 'ps026', title: 'Psalm 26', rows: [row], analysis: null, canonical_numbering: null,
  } }));
  const history: Array<Record<string, unknown>> = [];
  if (inference) history.push({ kind: 'briefing_inference', audit_id: 'inference.fixture',
    created_at: '2026-10-20T09:00:00Z', created_by: 'codex', summary: 'Inferred suggestions',
    guidance: '', inferences: { briefing_run_id: 'brief.fixture', source_hash: 'fixture-hash',
      items: [{ question_index: 0, topic: 'The opening judgment', answer: 'Ask for vindication.',
        confidence: 'high', evidence: 'Existing text says "vindicate me".',
        rationale: 'This wording describes the expected favorable outcome.' }] } });
  await page.route('**/psalms/ps026/briefing-decisions', async route => {
    expect(route.request().method()).toBe('PUT');
    const body = route.request().postDataJSON();
    expect(body.translation_id).toBe('tr.fixture');
    expect(body.annotation.briefing_run_id).toBe('brief.fixture');
    history.push({ kind: 'briefing_decision', audit_id: `audit.${history.length}`,
      created_at: '2026-10-20T10:00:00Z', created_by: 'reviewer',
      summary: 'Record briefing decision', guidance: '', annotations: [body.annotation] });
    await route.fulfill({ json: body.annotation });
  });
  await page.route('**/psalms/ps026/briefing?*', async route => {
    const savedOnly = new URL(route.request().url()).searchParams.get('include_sources') === 'false';
    await (savedOnly ? briefingGate : sourceGate);
    return route.fulfill({ json: {
    briefing: { psalm_id: 'ps026', translation_id: 'tr.fixture', run_id: 'brief.fixture', guidance: '',
      background: { authorship: '', setting: '', form: '', themes: '', reception: '' },
      questions: [{ topic: 'The opening judgment', verses: [1], question: 'How should the opening be rendered?',
        background: 'Authored question', options: decisions ? [
          { choice: 'Ask for judgment.', held_by: 'Fixture', effect: 'Open judgment.' },
          { choice: 'Ask for vindication.', held_by: 'Fixture', effect: 'Expected outcome.' },
        ] : [] }],
    }, history, greek_sources: greek,
  } });
  });
  await page.route('**/psalms/ps026/translation-guidance?*', route => route.fulfill({ json: { translation_guidance: '' } }));
  await page.route('**/greek/tokens/*/card?*', async route => {
    expect(preview, 'Preview word hovers must not request a released-snapshot card').toBe(false);
    const params = new URL(route.request().url()).searchParams;
    expect(params.get('study_snapshot_id')).toBe(identity.study_snapshot_id);
    expect(params.get('policy_revision_id')).toBe(identity.policy_revision_id);
    if (long) await new Promise(resolve => setTimeout(resolve, 200));
    return route.fulfill({ json: { ...identity, token: { token_id: tokenId, surface: 'Κρῖνόν' },
      analyses: [{ analysis_id: 'a.fixture', lemma: 'κρίνω', status: 'proposed' }],
      dictionary_entries: [{ entry_id: 'd.fixture', headword: 'κρίνω', gloss: 'judge, decide' + (long ? ' · alternative sense'.repeat(100) : ''),
        attribution: { required_attribution: 'Authored STEP dictionary fixture', license: 'CC BY 4.0' } }],
      counts: { total_matches: 2 },
    } });
  });
  await page.goto('/#/workbench');
  await page.getByRole('button', { name: /^Briefing/ }).click();
  return page.locator('.briefing-sources');
}

test('briefing shows known Hebrew meanings without requiring a saved literal and supports preview Greek hover', async ({ page }, testInfo) => {
  const sources = await briefingFixture(page);
  await expect(sources.locator('.briefing-hebrew-literal')).toContainText('judge me · Yahweh · ?');
  await expect(sources.locator('.briefing-hebrew-literal')).toContainText('Word-by-word literal');
  const hebrew = sources.locator('[lang="he"] [tabindex]').first();
  await hebrew.hover();
  await expect(page.getByRole('tooltip')).toContainText('judge me');
  await expect(page.getByRole('tooltip')).not.toContainText('no literal or');
  await sources.locator('[lang="he"] [tabindex]').nth(1).hover();
  await expect(page.getByRole('tooltip')).toContainText('“Yahweh”');
  const greek = sources.locator('[lang="grc"] [tabindex]').first();
  await greek.hover();
  await expect(page.getByRole('tooltip')).toContainText('Κρῖνόν');
  await expect(page.getByRole('tooltip')).toContainText('Greek Psalm 25:1');
  await expect(page.getByRole('tooltip')).toContainText('No Greek word meaning');
  await greek.focus();
  await expect(page.getByRole('tooltip')).toBeVisible();
  await greek.press('Escape');
  await expect(page.getByRole('tooltip')).toHaveCount(0);
  await expect(sources.locator('.briefing-source-words[lang="grc"]')).toHaveText('Κρῖνόν με, Κύριε.');
  await expect(sources.locator('.briefing-greek-literal')).toContainText('Greek word meanings are not loaded');
  await page.screenshot({ path: testInfo.outputPath('briefing-literal-context.png'), fullPage: true });
});

for (const preview of [true, false]) {
  test(`Hebrew and ${preview ? 'preview' : 'loaded'} Greek hover cards keep words clear at viewport edges`, async ({ page }, testInfo) => {
    const sources = await briefingFixture(page, { preview, lexical: preview, long: true });
    await page.evaluate(() => { document.body.style.paddingBlock = '1000px'; });
    await page.evaluate(() => document.fonts.ready);
    for (const width of [1280, 430]) {
      await page.setViewportSize({ width, height: 900 });
      for (const language of ['he', 'grc']) {
        const word = sources.locator(`[lang="${language}"] [tabindex]`).first();
        for (const targetTop of [60, 420, 780]) {
          await page.mouse.move(0, 0);
          await word.evaluate((element, top) => {
            window.scrollTo(0, window.scrollY + element.getBoundingClientRect().top - top);
          }, targetTop);
          await word.hover();
          const card = page.getByRole('tooltip');
          await expect(card).toBeVisible();
          if (language === 'grc') await expect(card).toContainText('alternative sense');
          await expect.poll(async () => {
            const trigger = await word.boundingBox();
            const box = await card.boundingBox();
            if (!trigger || !box) return false;
            return (box.y + box.height <= trigger.y - 7 || box.y >= trigger.y + trigger.height + 7)
              && box.y >= 7 && box.y + box.height <= 893
              && box.x >= 7 && box.x + box.width <= width - 7;
          }, { message: `${language} card covers its word or leaves the viewport at ${width}px / y=${targetTop}` }).toBe(true);
          if (language === 'grc' && width === 1280 && targetTop === 780) {
            await page.screenshot({ path: testInfo.outputPath('greek-hover-above-word.png') });
          }
        }
      }
    }
  });
}

test('briefing keeps saved literal sentences and Greek dictionary meanings available', async ({ page }) => {
  const sources = await briefingFixture(page, { preview: false, literal: 'Judge me, Yahweh.' });
  await expect(sources.locator('.briefing-hebrew-literal')).toHaveText('Literal Judge me, Yahweh.');
  await expect(sources.locator('.briefing-greek-literal')).toContainText('judge · me · Lord');
  await sources.locator('[lang="grc"] [tabindex]').first().hover();
  await expect(page.getByRole('tooltip')).toContainText('judge, decide');
  await expect(page.getByRole('tooltip')).not.toContainText('Authored STEP dictionary fixture');
});

test('loaded preview dictionary appears below Greek and on hover without a released snapshot', async ({ page }, testInfo) => {
  const sources = await briefingFixture(page, { lexical: true });
  await expect(page.locator('.briefing-source-limit')).toContainText('Generation from Greek is not enabled yet');
  await expect(sources.locator('.briefing-greek-literal')).toContainText('judge · me · Lord');
  const word = sources.locator('[lang="grc"] [tabindex]').first();
  await word.hover();
  const card = page.getByRole('tooltip');
  await expect(card).toContainText('to judge');
  await expect(card).toContainText('κρίνω');
  await expect(card).toContainText('mood: imperative');
  await expect(card).not.toContainText('Authored STEP dictionary fixture');
  await expect(card).not.toContainText('not loaded');
  await page.screenshot({ path: testInfo.outputPath('greek-dictionary-hover.png'), fullPage: true });
  await word.focus();
  await expect(card).toBeVisible();
  await word.press('Escape');
  await expect(card).toHaveCount(0);
});

test('unmatched Greek forms explain the lookup gap when the dictionary is loaded', async ({ page }) => {
  const sources = await briefingFixture(page, { lexical: true, missing: true });
  await sources.locator('[lang="grc"] [tabindex]').first().hover();
  await expect(page.getByRole('tooltip')).toContainText('No matching dictionary entry was found for this word form.');
  await expect(page.getByRole('tooltip')).not.toContainText('No Greek word meaning is loaded');
});

test('suggested source readings remain bracketed and explained without replacing Greek', async ({ page }) => {
  const sources = await briefingFixture(page, { lexical: true, review: true });
  await expect(sources.locator('.briefing-greek-literal')).toContainText('[place?]');
  await sources.locator('[lang="grc"] [tabindex]').first().hover();
  await expect(page.getByRole('tooltip')).toContainText('Possible reading — source review needed.');
  await expect(page.getByRole('tooltip')).toContainText('Printed τόπαν; possible reading τόπον.');
  await expect(sources.locator('.briefing-source-words[lang="grc"]')).toHaveText('τόπαν με, Κύριε.');
});

test('accent and breathing suggestions remain marked for review in literal and hover', async ({ page }) => {
  const sources = await briefingFixture(page, { lexical: true, markVariant: true });
  await expect(sources.locator('.briefing-greek-literal')).toContainText('[so that?]');
  await sources.locator('[lang="grc"] [tabindex]').first().hover();
  await expect(page.getByRole('tooltip')).toContainText('Possible accent or breathing variant — needs review.');
  await expect(page.getByRole('tooltip')).toContainText('so that');
  await expect(sources.locator('.briefing-source-words[lang="grc"]')).toHaveText('ἰνα με, Κύριε.');
});

test('source credits and reading explanations are available in one collapsed briefing footer', async ({ page }) => {
  const sources = await briefingFixture(page, { lexical: true });
  const licenses = page.locator('.briefing-panel .source-licenses');
  await expect(licenses).toHaveCount(1);
  await expect(licenses.getByText(/Authored Greek fixture/)).toBeHidden();
  await expect(licenses.getByText(/Authored STEP dictionary fixture/)).toBeHidden();
  await expect(sources).not.toContainText('Authored Greek fixture');
  await expect(sources).not.toContainText('No sentence translation recorded');
  await expect(sources.locator('.basis')).toHaveCount(0);
  const summary = licenses.locator('summary');
  await summary.click();
  await expect(licenses.getByText(/Authored Greek fixture · CC0/)).toBeVisible();
  await expect(licenses.getByText(/Authored STEP dictionary fixture · CC BY 4.0/)).toBeVisible();
  await expect(licenses.getByText(/separate from saved verse translations/)).toBeVisible();
  await summary.press('Enter');
  await expect(licenses.getByText(/Authored STEP dictionary fixture/)).toBeHidden();
});

test('briefing answers and notes save automatically and restore after reload without guidance clicks', async ({ page }) => {
  await briefingFixture(page, { lexical: true, decisions: true });
  const panel = page.locator('.briefing-panel');
  await panel.getByRole('radio', { name: /Ask for vindication/ }).check();
  await panel.getByLabel('Notes: The opening judgment').fill('Keep the request confident.');
  await expect(panel.getByRole('status')).toHaveText('Briefing decisions saved.');
  await page.reload();
  await page.getByRole('button', { name: /^Briefing/ }).click();
  await expect(panel.getByRole('radio', { name: /Ask for vindication/ })).toBeChecked();
  await expect(panel.getByLabel('Notes: The opening judgment')).toHaveValue('Keep the request confident.');
  const own = panel.getByRole('radio').last();
  await own.check();
  await expect(own).toBeChecked();
  await panel.getByLabel('Your own answer: The opening judgment').fill('Keep the verdict open.');
  await expect(panel.getByRole('status')).toHaveText('Briefing decisions saved.');
  await page.reload();
  await page.getByRole('button', { name: /^Briefing/ }).click();
  await expect(own).toBeChecked();
  await expect(panel.getByLabel('Your own answer: The opening judgment')).toHaveValue('Keep the verdict open.');
  await panel.getByRole('button', { name: 'Leave open', exact: true }).click();
  await panel.getByLabel('Notes: The opening judgment').fill('');
  await expect(panel.getByRole('status')).toHaveText('No briefing decisions selected yet. Answers and notes save automatically.');
  await page.reload();
  await page.getByRole('button', { name: /^Briefing/ }).click();
  await expect(panel.getByRole('radio', { name: /Ask for vindication/ })).not.toBeChecked();
  await expect(panel.getByLabel('Notes: The opening judgment')).toHaveValue('');
  await panel.locator('.translation-context-history > summary').click();
  await expect(panel.locator('.translation-context-history')).toContainText('Record briefing decision');
});

test('failed briefing saves remain recoverable after reload and retry', async ({ page }) => {
  await briefingFixture(page, { decisions: true });
  const endpoint = '**/psalms/ps026/briefing-decisions';
  let failed = true;
  await page.route(endpoint, route => failed
    ? route.fulfill({ status: 503, body: 'Test connection interrupted' }) : route.fallback());
  const panel = page.locator('.briefing-panel');
  await panel.getByLabel('Your own answer: The opening judgment').fill('Preserve the open request.');
  await panel.getByLabel('Notes: The opening judgment').fill('Do not lose this note.');
  await expect(panel.getByRole('status')).toContainText('Could not save to history');
  await page.reload();
  await page.getByRole('button', { name: /^Briefing/ }).click();
  await expect(panel.getByLabel('Your own answer: The opening judgment')).toHaveValue('Preserve the open request.');
  await expect(panel.getByLabel('Notes: The opening judgment')).toHaveValue('Do not lose this note.');
  await expect(panel.getByRole('status')).toContainText('Could not save to history');
  failed = false;
  await panel.getByRole('button', { name: 'Retry saving decisions' }).click();
  await expect(panel.getByRole('status')).toHaveText('Briefing decisions saved.');
  await expect.poll(() => page.evaluate(() => Object.keys(localStorage)
    .filter(key => key.startsWith('aleph-tav.briefing-decisions:')).length)).toBe(0);
  await page.reload();
  await page.getByRole('button', { name: /^Briefing/ }).click();
  await expect(panel.getByLabel('Your own answer: The opening judgment')).toHaveValue('Preserve the open request.');
});

test('translation waits for an in-flight briefing save and stops on save failure', async ({ page }) => {
  await briefingFixture(page, { decisions: true });
  let saved = false;
  let fail = true;
  let calls = 0;
  await page.route('**/psalms/ps026/briefing-decisions', async route => {
    await new Promise(resolve => setTimeout(resolve, 650));
    if (fail) return route.fulfill({ status: 503, body: 'Test interrupted save' });
    saved = true;
    return route.fallback();
  });
  await page.route('**/codex/sessions', route => {
    expect(saved).toBe(true);
    calls += 1;
    return route.fulfill({ json: { session_id: 'session.fixture' } });
  });
  await page.route('**/codex/psalms/ps026/fill', route => {
    expect(saved).toBe(true);
    return route.fulfill({ json: { status: 'completed', error: null, failed_units: [],
      run_ids: [], rendering_ids: [] } });
  });
  await page.getByRole('radio', { name: /Ask for judgment/ }).check();
  await page.getByRole('button', { name: 'Translate psalm', exact: true }).click();
  await expect(page.locator('.batch-report')).toContainText('Briefing decisions could not be saved');
  expect(calls).toBe(0);
  fail = false;
  await page.getByRole('button', { name: 'Translate psalm', exact: true }).click();
  await expect(page.locator('.batch-report')).toContainText('Translation finished: 1 of 1 succeeded.');
  expect(calls).toBe(1);
});

test('a slow save cannot replace a newer briefing edit', async ({ page }) => {
  await briefingFixture(page, { decisions: true });
  await page.route('**/psalms/ps026/briefing-decisions', async route => {
    await new Promise(resolve => setTimeout(resolve, 650));
    return route.fallback();
  });
  const input = page.getByLabel('Notes: The opening judgment');
  const first = page.waitForRequest(request => request.url().endsWith('/briefing-decisions'));
  await input.fill('Earlier note.');
  await first;
  await input.fill('The final note, entered while the earlier save was running.');
  await expect(page.locator('.briefing-save-status')).toHaveText('Briefing decisions saved.');
  await page.reload();
  await page.getByRole('button', { name: /^Briefing/ }).click();
  await expect(input).toHaveValue('The final note, entered while the earlier save was running.');
});

test('saved answers automatically guide translation and inferred answers remain suggestions until chosen', async ({ page }, testInfo) => {
  await briefingFixture(page, { decisions: true, inference: true });
  const panel = page.locator('.briefing-panel');
  await expect(panel.getByRole('button', { name: /Add decisions/ })).toHaveCount(0);
  await expect(panel).toContainText('Saved answers and notes automatically guide translation.');
  const radio = panel.getByRole('radio', { name: /Ask for vindication/ });
  await expect(radio).not.toBeChecked();
  await expect(panel.getByRole('status')).toContainText('No briefing decisions selected yet');
  const suggestion = panel.locator('.briefing-inference');
  await suggestion.locator('summary').click();
  await expect(suggestion).toContainText('not a recovered original answer');
  await page.screenshot({ path: testInfo.outputPath('inferred-briefing-review.png'), fullPage: true });
  await suggestion.getByRole('button', { name: 'Use this inferred answer' }).click();
  await expect(radio).toBeChecked();
  await expect(panel.getByLabel('Notes: The opening judgment')).toHaveValue(/Adopted inference.*vindicate me/);
  await expect(panel.getByRole('status')).toHaveText('Briefing decisions saved.');
  await page.reload();
  await page.getByRole('button', { name: /^Briefing/ }).click();
  await expect(radio).toBeChecked();
});


test('approved Greek generation does not show a study-only warning', async ({ page }) => {
  await briefingFixture(page, { generation: true, lexical: true });
  await expect(page.locator('.briefing-source-limit')).toHaveCount(0);
  await expect(page.locator('.briefing-sources')).toContainText('Greek');
});


test('reopening restores saved answers while Greek dictionaries are still loading', async ({ page }) => {
  let releaseSources!: () => void;
  const sourceGate = new Promise<void>(resolve => { releaseSources = resolve; });
  await briefingFixture(page, { decisions: true, lexical: true, sourceGate });
  const panel = page.locator('.briefing-panel');
  await panel.getByRole('radio', { name: /Ask for vindication/ }).check();
  await panel.getByLabel('Notes: The opening judgment').fill('Preserve this on return.');
  await expect(panel.getByText('1 of 1 questions answered · Saved')).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: /^Briefing/ }).click();
  await expect(panel.getByRole('radio', { name: /Ask for vindication/ })).toBeChecked();
  await expect(panel.getByLabel('Notes: The opening judgment')).toHaveValue('Preserve this on return.');
  await expect(panel.getByText(/Loading Greek reading context/)).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Start with a briefing' })).toHaveCount(0);
  await expect(panel.locator('.translation-context-history > summary')).not.toHaveText(/\(0\)/);
  releaseSources();
  await expect(panel.locator('[lang="grc"]').first()).toBeVisible();
});

test('a pending saved briefing never appears as a missing briefing', async ({ page }) => {
  let releaseBriefing!: () => void;
  const briefingGate = new Promise<void>(resolve => { releaseBriefing = resolve; });
  await briefingFixture(page, { decisions: true, briefingGate });
  await expect(page.getByText('Loading saved briefing and decisions…')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start with a briefing' })).toHaveCount(0);
  await expect(page.getByText('Briefing & guidance history (0)')).toHaveCount(0);
  releaseBriefing();
  await expect(page.locator('.briefing-panel').getByRole('radio', { name: /Ask for vindication/ })).toBeVisible();
});
