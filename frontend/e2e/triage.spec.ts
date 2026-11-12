import { expect, test } from '@playwright/test'

test('symptom chat -> follow-up -> result with the hospital area', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('증상 입력').fill('어제부터 열이 나요')
  await page.getByRole('button', { name: '보내기' }).click()

  await expect(page.locator('[data-test="progress"]').or(page.locator('.assistant').first())).toBeVisible()
  await page.getByRole('button', { name: '오늘' }).click()

  await expect(page.locator('[data-test="prediction"]')).toHaveCount(3)
  await expect(page.getByText('권장 진료과')).toBeVisible()
  await expect(page.locator('[data-test="hospital-finder"]')).toBeVisible()
  await expect(page.locator('[data-test="disclaimer"]')).toContainText('의학적 진단이 아니며')
  await expect(page.locator('[data-test="emergency-banner"]')).toHaveCount(0)
})

test('emergency -> 119 and ER finder, no hospital list', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('증상 입력').fill('갑자기 가슴이 아파요')
  await page.getByRole('button', { name: '보내기' }).click()

  const banner = page.locator('[data-test="emergency-banner"]')
  await expect(banner).toBeVisible()
  await expect(banner.locator('a[href="tel:119"]')).toBeVisible()
  await expect(banner.locator('[data-test="egen-link"]')).toHaveAttribute('href', /^https:\/\/www\.e-gen\.or\.kr/)
  await expect(page.locator('[data-test="prediction"]').first()).toBeVisible()
  await expect(page.locator('[data-test="hospital-finder"]')).toHaveCount(0)
})
