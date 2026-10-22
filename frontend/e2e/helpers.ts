import { expect, type Locator, type Page } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { API_URL, UI_URL } from './env'

/** The passwords the test server accepts (see backend/e2e/server.py). */
export const PASSWORDS = { user: 'user-test-pw', developer: 'developer-test-pw' }

const fixture = (name: string) => fileURLToPath(new URL(`./fixtures/${name}.png`, import.meta.url))

/** Which scripted answer a fixture gets (see backend/e2e/server.py). */
export type Form = 'form-a' | 'form-b' | 'form-c' | 'sideways' | 'upside-down' | 'sideways-flipped'

/** Start every test from an empty system. */
export async function resetBackend(page: Page) {
  const res = await page.request.post(`${API_URL}/__test__/reset`)
  expect(res.ok()).toBeTruthy()
}

/** Log in without going through the screen. The session cookie belongs to the page's browser, and goes through the
 *  UI server's /api proxy so that it is for the host the page is on. A developer sees every screen. */
export async function signIn(page: Page, role: keyof typeof PASSWORDS = 'developer') {
  const res = await page.request.post(`${UI_URL}/api/auth/login`, { data: { password: PASSWORDS[role] } })
  expect(res.ok()).toBeTruthy()
}

/** Upload forms through the upload screen, wait until the server has processed them, and show the table.
 *  The app opens the form screen by itself right after an upload (the form is viewable before it is read). */
export async function uploadForms(page: Page, ...forms: Form[]) {
  await page.goto('/')
  await page.getByRole('tab', { name: 'העלאה' }).click()
  await page.getByLabel('בחירת קבצים').setInputFiles(forms.map(fixture))
  await expect(page.getByRole('banner')).toContainText(`${forms.length} טפסים`, { timeout: 30_000 })
  await page.getByRole('tab', { name: 'טבלה' }).click()
}

/** How many times the scripted vision model has been asked since the last reset. */
export async function modelCalls(page: Page): Promise<number> {
  const res = await page.request.get(`${API_URL}/__test__/calls`)
  return (await res.json()).calls
}

/** Add many records at once, straight into the test database. The first `approved` of them are approved. */
export async function seedRecords(page: Page, n: number, approved = 0) {
  const res = await page.request.post(`${API_URL}/__test__/seed`, { params: { n, approved } })
  expect(res.ok()).toBeTruthy()
}

export const header = (page: Page) => page.getByRole('banner')

/** Open a form from the table by a word in its row, and wait for the form screen. */
export async function openForm(page: Page, rowText: string | RegExp) {
  await tableRow(page, rowText).first().click()
  await expect(page.getByRole('tab', { name: 'טופס', selected: true })).toBeVisible()
}

export const formList = (page: Page) => page.getByLabel('רשימת הטפסים', { exact: true })

/** A table row by its text. A form with no names has no text of its own, so "— לא נמצא" finds it. */
export const tableRow = (page: Page, text: string | RegExp) => page.getByRole('main').getByRole('button').filter({ hasText: text })

export const fieldsPanel = (page: Page) => page.getByLabel('שדות הטופס')

/** The row of one field in the fields panel (it carries `data-flagged`). */
export const fieldRow = (page: Page, label: string): Locator =>
  fieldsPanel(page).locator('[data-flagged]').filter({ has: page.getByText(label, { exact: true }) })

export async function widthOf(locator: Locator): Promise<number> {
  const box = await locator.boundingBox()
  expect(box, 'element should be on screen').not.toBeNull()
  return box!.width
}

export const formImage = (page: Page) => page.getByAltText('תמונת הטופס')
