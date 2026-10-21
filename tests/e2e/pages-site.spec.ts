import { expect, test } from '@playwright/test';

for (const width of [1440, 430, 360]) {
  test(`public feature site works without an API at ${width}px`, async ({ page }) => {
    const errors: string[] = [];
    const apiRequests: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (/\/(assistant|codex|collections|psalms|lxx|greek|project)(\/|\?|$)/.test(new URL(request.url()).pathname)) apiRequests.push(request.url());
    });
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('./');
    await expect(page.getByRole('heading', { name: 'Psalms Copyleft Workbench', exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Brief, decide, translate', exact: true })).toBeVisible();
    await expect(page.getByText(/Lexical lookup resources cover Septuagint and Greek New Testament forms/)).toBeVisible();
    await expect(page.getByRole('button', { name: /Open assistant/ })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Open Workbench', exact: true })).toHaveCount(0);
    await page.getByRole('link', { name: 'Get started locally', exact: true }).click();
    await expect(page).toHaveURL(/#run-it$/);
    await expect(page.getByRole('heading', { name: 'Quick local startup', exact: true })).toBeInViewport();
    expect(await page.locator('body').evaluate(element => element.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.goto('./#/workbench');
    await expect(page.getByRole('heading', { name: 'Psalms Copyleft Workbench', exact: true })).toBeVisible();
    expect(apiRequests).toEqual([]);
    expect(errors).toEqual([]);
    if (width === 1440) await page.screenshot({ path: '.run/public-feature-site-desktop.png', fullPage: true });
    if (width === 430) await page.screenshot({ path: '.run/public-feature-site-phone.png', fullPage: true });
  });
}
