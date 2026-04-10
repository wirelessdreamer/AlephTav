import { expect, test } from '@playwright/test';

test('hovering and pinning a token updates the inspector', async ({ page }) => {
  await page.goto('/');

  const firstToken = page.getByTitle(/ps001\.v001\.t001/);
  await firstToken.hover();
  await expect(page.getByText('fortunate/blessed')).toBeVisible();

  await firstToken.click();
  await expect(page.getByText(/Psalm 1:1a .* ps001\.v001\.t001/)).toBeVisible();

  await page.getByRole('button', { name: 'Unpin' }).click();
  await expect(page.getByText('Hover or pin a Hebrew token to inspect lexical details.')).toBeVisible();
});

test('workflow actions cover alignment creation, alternate promotion, and release export', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'workflow' }).click();

  await page.getByLabel('Alignment notes').fill('Playwright alignment coverage');
  await page.getByRole('button', { name: 'Create alignment' }).click();
  await expect(page.getByText(/Alignment created:/)).toBeVisible();

  await page.getByLabel('Alternate layer').selectOption('lyric');
  await page.getByLabel('Alternate text').fill('Playwright alternate line');
  await page.getByRole('button', { name: 'Add alternate' }).click();
  await expect(page.getByText(/Alternate added:/)).toBeVisible();

  await page.getByRole('button', { name: 'Approve and promote alternate' }).click();
  await expect(page.getByText(/Alternate promoted:/)).toBeVisible();

  await page.getByLabel('Release id').fill('v0.1.0-e2e');
  await page.getByRole('button', { name: 'Export release' }).click();
  await expect(page.getByText(/Release exported:/)).toBeVisible();
});
