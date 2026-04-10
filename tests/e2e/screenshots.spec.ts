import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { test } from '@playwright/test';

const screenshotDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../app/ui/public/screenshots');

test.beforeAll(() => {
  fs.mkdirSync(screenshotDir, { recursive: true });
});

test('capture lexical analysis screenshot', async ({ page }) => {
  await page.goto('/#/workbench');
  await page.setViewportSize({ width: 1440, height: 1180 });

  const firstToken = page.getByTitle(/ps001\.v001\.t001/);
  await firstToken.click();
  await page.getByRole('button', { name: 'Pivot lemma' }).click();

  await page.screenshot({
    path: path.join(screenshotDir, 'lexical-analysis.png'),
    fullPage: true,
  });
});

test('capture translation workflow screenshot', async ({ page }) => {
  await page.goto('/#/workbench');
  await page.setViewportSize({ width: 1440, height: 1320 });

  await page.getByRole('button', { name: 'workflow' }).click();
  await page.getByTitle(/ps001\.v001\.t001/).click();
  await page.getByTitle(/spn\.ps001\.v001\.a\.literal\.0001/).click();

  await page.screenshot({
    path: path.join(screenshotDir, 'translation-workflow.png'),
    fullPage: true,
  });
});
