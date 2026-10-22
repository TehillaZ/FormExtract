import { expect, test } from '@playwright/test'
import { PASSWORDS, resetBackend } from './helpers'

test.beforeEach(async ({ page }) => {
  await resetBackend(page)
})

async function logIn(page: import('@playwright/test').Page, password: string) {
  await page.goto('/')
  await page.getByLabel('סיסמה').fill(password)
  await page.getByRole('button', { name: 'כניסה' }).click()
}

test('nothing is shown before a password, and a wrong password is refused', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('tab')).toHaveCount(0)
  await logIn(page, 'wrong')
  await expect(page.getByRole('alert')).toHaveText('סיסמה שגויה')
  await expect(page.getByRole('tab')).toHaveCount(0)
})

test('a user sees the four working screens and not the developer reports', async ({ page }) => {
  await logIn(page, PASSWORDS.user)
  await expect(page.getByRole('tab', { name: 'טבלה' })).toBeVisible()
  await expect(page.getByRole('tab')).toHaveText(['העלאה', 'טבלה', 'טופס', 'רשומות'])
  // the server refuses too, not only the interface
  expect((await page.request.get('/api/evaluation')).status()).toBe(403)
  expect((await page.request.get('/api/corrections/summary')).status()).toBe(403)
})

test('a developer also sees the accuracy and repeated-mistakes screens, and can log out', async ({ page }) => {
  await logIn(page, PASSWORDS.developer)
  await page.getByRole('tab', { name: 'דוח דיוק' }).click()
  await expect(page.getByRole('heading', { name: 'דוח דיוק' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'טעויות חוזרות' })).toBeVisible()

  await page.getByRole('button', { name: 'יציאה' }).click()
  await expect(page.getByLabel('סיסמה')).toBeVisible()
  await page.reload()   // the cookie is gone, not only the screen
  await expect(page.getByLabel('סיסמה')).toBeVisible()
})
