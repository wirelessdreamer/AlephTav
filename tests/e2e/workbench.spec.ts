import { expect, test } from '@playwright/test';

test('welcome page renders without requiring the api-backed workbench route', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Psalms Copyleft Workbench' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Quick local startup' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open Workbench' })).toBeVisible();
});

test('assistant docks beside the workbench and can be reopened after closing', async ({ page }) => {
  await page.goto('/#/workbench');

  const comparison = page.locator('.comparison-shell');
  const assistantPanel = page.locator('.assistant-panel');
  await expect(assistantPanel).toBeVisible();

  const comparisonBox = await comparison.boundingBox();
  const assistantBox = await assistantPanel.boundingBox();
  expect(comparisonBox).not.toBeNull();
  expect(assistantBox).not.toBeNull();
  expect(assistantBox!.x).toBeGreaterThan(comparisonBox!.x + comparisonBox!.width - 20);

  await page.getByRole('button', { name: 'Close' }).click();
  await expect(page.locator('.assistant-launcher__button')).toBeVisible();
  await expect(assistantPanel).toHaveCount(0);

  await page.getByRole('button', { name: 'Open assistant side panel' }).click();
  await expect(assistantPanel).toBeVisible();
});

test('assistant visibility persists across reloads', async ({ page }) => {
  await page.goto('/#/workbench');

  await page.getByRole('button', { name: 'Close' }).click();
  await page.reload();
  await expect(page.locator('.assistant-launcher__button')).toBeVisible();

  await page.getByRole('button', { name: 'Open assistant side panel' }).click();
  await page.reload();
  await expect(page.locator('.assistant-panel')).toBeVisible();
});

test('phone workbench uses the phone comparison instead of the shell assistant', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 1100 });
  await page.goto('/#/workbench');

  await expect(page.getByRole('heading', { name: 'Verse comparison', exact: true })).toBeVisible();
  await expect(page.locator('.assistant-panel')).toHaveCount(0);
  await expect(page.locator('.assistant-launcher__button')).toHaveCount(0);
});

test('psalm selector exposes the full audited corpus', async ({ page }) => {
  await page.goto('/#/workbench');

  const psalmSelect = page.locator('label').filter({ hasText: 'Psalm' }).locator('select');
  await expect(psalmSelect.locator('option')).toHaveCount(5);
  await expect(psalmSelect.locator('option')).toHaveText([
    'Psalm 1',
    'Psalm 19',
    'Psalm 23',
    'Psalm 51',
    'Add a psalm…',
  ]);
});

