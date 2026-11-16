import { readFileSync } from 'node:fs'

import { expect, test, type Page, type Request } from '@playwright/test'
import { parse } from 'yaml'

// The real HospitalFinder (T21, features/hospitals/) asks the browser for a location and calls
// GET /api/hospitals. Kakao and the public data API are not reachable here or in CI, so
// /api/hospitals answers with the contract example and the Kakao map SDK is blocked: the finder
// must still show the list (map error message only). Location: a fixed test point.
const contract = parse(readFileSync(new URL('../../contracts/openapi.yaml', import.meta.url), 'utf8'))
const HOSPITALS = Object.values(
  contract.paths['/api/hospitals'].get.responses['200'].content['application/json'].examples as Record<
    string,
    { value: { items: unknown[] } }
  >,
)[0]!.value

test.use({ geolocation: { latitude: 37.4979, longitude: 127.0276 }, permissions: ['geolocation'] })

async function fakeHospitalSearch(page: Page): Promise<Request[]> {
  const calls: Request[] = []
  await page.route('https://dapi.kakao.com/**', (route) => route.abort())
  await page.route('**/api/hospitals?**', (route) => {
    calls.push(route.request())
    return route.fulfill({ json: HOSPITALS })
  })
  return calls
}

test('symptom chat -> follow-up -> result with the hospital list', async ({ page }) => {
  const hospitalCalls = await fakeHospitalSearch(page)
  await page.goto('/')
  await page.getByLabel('증상 입력').fill('어제부터 열이 나요')
  await page.getByRole('button', { name: '보내기' }).click()

  await expect(page.locator('[data-test="progress"]').or(page.locator('.assistant').first())).toBeVisible()
  await page.getByRole('button', { name: '오늘' }).click()

  await expect(page.locator('[data-test="prediction"]')).toHaveCount(3)
  // Labels instead of percentages (2026-11-15); stub ranking has no rare-disease reorder.
  await expect(page.locator('[data-test="likelihood"]')).toHaveCount(3)
  await expect(page.locator('.result')).not.toContainText('%')
  await expect(page.locator('[data-test="order-adjusted"]')).toHaveCount(0)
  await expect(page.getByText('권장 진료과')).toBeVisible()
  await expect(page.locator('[data-test="disclaimer"]')).toContainText('의학적 진단이 아니며')
  await expect(page.locator('[data-test="emergency-banner"]')).toHaveCount(0)

  const finder = page.locator('[data-test="hospital-finder"]')
  await expect(finder).toBeVisible()
  await expect(finder).toHaveAttribute('data-department', '01')
  await expect(finder.locator('[data-test="hospital"]')).toHaveCount(HOSPITALS.items.length)
  // No Kakao SDK: the list still works and the map says it is unavailable.
  await expect(finder.locator('[data-test="map-error"]')).toBeVisible()
  expect(hospitalCalls.length).toBeGreaterThan(0)
  const query = new URL(hospitalCalls[0]!.url()).searchParams
  expect(query.get('department')).toBe('01')
  expect(Number(query.get('lat'))).toBeCloseTo(37.4979)
})

test('emergency -> 119 and ER finder, no hospital list', async ({ page }) => {
  const hospitalCalls = await fakeHospitalSearch(page)
  await page.goto('/')
  await page.getByLabel('증상 입력').fill('갑자기 가슴이 아파요')
  await page.getByRole('button', { name: '보내기' }).click()

  const banner = page.locator('[data-test="emergency-banner"]')
  await expect(banner).toBeVisible()
  await expect(banner.locator('a[href="tel:119"]')).toBeVisible()
  await expect(banner.locator('[data-test="egen-link"]')).toHaveAttribute('href', /^https:\/\/www\.e-gen\.or\.kr/)
  await expect(page.locator('[data-test="prediction"]').first()).toBeVisible()
  await expect(page.locator('[data-test="likelihood"]').first()).toBeVisible()
  await expect(page.locator('.result')).not.toContainText('%')
  await expect(page.locator('[data-test="hospital-finder"]')).toHaveCount(0)
  expect(hospitalCalls).toHaveLength(0)
})
