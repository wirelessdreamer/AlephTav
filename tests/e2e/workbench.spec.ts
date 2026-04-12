import { expect, test } from '@playwright/test';

test('hovering and pinning a token updates the inspector', async ({ page }) => {
  await page.goto('/#/workbench');

  const firstToken = page.getByTitle(/ps001\.v001\.t001/);
  await firstToken.hover();
  await expect(page.getByRole('definition').filter({ hasText: 'fortunate/blessed' })).toBeVisible();

  await firstToken.click();
  await expect(page.locator('.inspector-rail').getByText(/Psalm 1:1a .* ps001\.v001\.t001/)).toBeVisible();

  await page.getByRole('button', { name: 'Unpin' }).click();
  await expect(page.getByText('Hover or pin a Hebrew token to inspect lexical details.')).toBeVisible();
});

test('pinned inspector stays fixed while hovering another token', async ({ page }) => {
  await page.goto('/#/workbench');

  const firstToken = page.getByTitle(/ps001\.v001\.t001/);
  const secondToken = page.getByTitle(/ps001\.v001\.t002/);

  await firstToken.click();
  await expect(page.getByRole('definition').filter({ hasText: 'fortunate/blessed' })).toBeVisible();

  await secondToken.hover();
  await expect(page.getByRole('definition').filter({ hasText: 'fortunate/blessed' })).toBeVisible();
  await expect(page.getByRole('definition').filter({ hasText: 'man/person' })).not.toBeVisible();
});

test('workflow actions cover alignment creation, alternate promotion, and release export', async ({ page }) => {
  await page.goto('/#/workbench');
  await page.getByRole('button', { name: 'workflow' }).click();
  const reviewPanel = page.locator('article').filter({ has: page.getByRole('heading', { name: 'Review actions' }) });

  await page.getByTitle(/ps001\.v001\.t001/).click();
  await page.getByTitle(/spn\.ps001\.v001\.a\.literal\.0001/).click();
  await page.getByLabel('Alignment notes').fill('Playwright alignment coverage');
  await page.getByRole('button', { name: 'Create alignment' }).click();
  await expect(page.getByText(/Alignment created:/)).toBeVisible();

  await page.getByLabel('Alternate layer').selectOption('lyric');
  await page.getByLabel('Alternate text').fill('Playwright alternate line');
  await page.getByRole('button', { name: 'Add alternate' }).click();
  await expect(page.getByText(/Alternate added:/)).toBeVisible();

  await reviewPanel.getByRole('textbox', { name: 'Reviewer' }).fill('playwright-reviewer-1');
  await reviewPanel.getByRole('combobox').nth(1).selectOption('alignment reviewer');
  await reviewPanel.getByRole('button', { name: 'Approve' }).click();
  await expect(page.getByText(/Review action recorded: approve/)).toBeVisible();

  await reviewPanel.getByRole('textbox', { name: 'Reviewer' }).fill('playwright-reviewer-2');
  await reviewPanel.getByRole('combobox').nth(1).selectOption('theology reviewer');
  await reviewPanel.getByRole('button', { name: 'Approve' }).click();
  await expect(page.getByText(/Review action recorded: approve/)).toBeVisible();

  await reviewPanel.getByRole('textbox', { name: 'Reviewer' }).fill('playwright-release-reviewer');
  await reviewPanel.getByRole('combobox').nth(1).selectOption('release reviewer');
  await reviewPanel.getByRole('button', { name: 'Promote to canonical' }).click();
  await expect(page.getByText(/Alternate promoted:/)).toBeVisible();

  await page.getByLabel('Release id').fill('v0.1.0-e2e');
  await page.getByRole('button', { name: 'Export release' }).click();
  await expect(page.getByText(/Release validation failed/)).toBeVisible();
});

test('hovering an English span highlights linked Hebrew tokens', async ({ page }) => {
  await page.goto('/#/workbench');

  const englishSpan = page.getByTitle(/spn\.ps001\.v001\.a\.literal\.0001/);
  const hebrewToken = page.getByTitle(/ps001\.v001\.t001/);

  await englishSpan.hover();
  await expect(hebrewToken).toHaveClass(/linked/);
});

test('source visibility and unresolved warning details are surfaced', async ({ page }) => {
  await page.goto('/#/workbench');

  await expect(page.getByText('export blocked', { exact: true })).toBeVisible();
  await expect(page.getByText('Witness text present and version-pinned separately.')).toBeVisible();
  await expect(page.getByLabel('Unit warning details')).toContainText('parallelism_break');
});

test('welcome page renders without requiring the api-backed workbench route', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Psalms Copyleft Workbench' })).toBeVisible();
  await expect(page.getByText('Quick local demo')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open Workbench' })).toBeVisible();
});


test('workbench defaults to a full-psalm visual flow canvas with cloud-driven retrieval', async ({ page }) => {
  await page.goto('/#/workbench');

  await expect(page.getByRole('heading', { name: 'Phrase And Concept Cloud' })).toBeVisible();
  await expect(page.locator('.flow-unit-card').filter({ has: page.getByText('Psalm 1:1a') })).toHaveCount(2);

  await page.locator('.cloud-node').first().click();
  await expect(page.getByText(/Retrieved support/).first()).toBeVisible();
});
