import { expect, test, type Locator, type Page } from '@playwright/test'
import { resetBackend, signIn } from './helpers'

// The test server holds two saved reports (model-a: ID 3 of 8 right, 2 silent errors; model-b: 5 of 8, none) and a
// ground truth of 10 pages: 8 for development and 2 held out, which no report covers.
test.beforeEach(async ({ page }) => {
  await resetBackend(page)
  await signIn(page)
  await page.goto('/')
  await page.getByRole('tab', { name: 'דוח דיוק' }).click()
  await expect(page.getByRole('heading', { name: 'דוח דיוק' })).toBeVisible()
})

const rowOf = (page: Page, field: string): Locator => page.getByRole('rowheader', { name: field }).locator('xpath=..')

test('compares the two saved reports, with the change from the first', async ({ page }) => {
  await expect(page.getByRole('columnheader', { name: /model-a/ })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /model-b/ })).toBeVisible()
  const id = rowOf(page, 'ת"ז')
  await expect(id).toContainText('38%')       // 3 of 8
  await expect(id).toContainText('63%')       // 5 of 8
  await expect(id).toContainText('+25')       // model-b is 25 points better on the ID
})

test('highlights errors that nobody was warned about', async ({ page }) => {
  await expect(rowOf(page, 'ת"ז').getByText('2 מתוך 5')).toHaveAttribute('data-silent', 'true')
  await expect(rowOf(page, 'ת"ז').getByText('0 מתוך 3')).toHaveAttribute('data-silent', 'false')
})

test('says plainly what was not measured', async ({ page }) => {
  await expect(page.getByTestId('test-not-run')).toContainText('סט הבדיקה (2 עמודים) טרם הורץ')
  await expect(page.getByRole('note')).toContainText('מסומנות במרקר צהוב')
  await expect(page.getByText(/8 מתוך 8 עמודים/).first()).toBeVisible()
})

test('a report can be taken out of the comparison', async ({ page }) => {
  await page.getByRole('group', { name: /השוואה/ }).getByRole('checkbox', { name: /model-b/ }).uncheck()
  await expect(page.getByRole('columnheader', { name: /model-b/ })).toHaveCount(0)
  await expect(rowOf(page, 'ת"ז')).not.toContainText('+25')
})

test('refuses to compare a report that covers other pages', async ({ page }) => {
  const picker = page.getByRole('group', { name: /השוואה/ })
  await expect(page.getByTestId('different-pages')).toHaveCount(0)          // model-a and model-b share all 8 pages

  await picker.getByRole('checkbox', { name: /model-c/ }).check()           // model-c covers only 4 of them
  await expect(page.getByTestId('different-pages')).toContainText('נמדדו על עמודים שונים (4 עמודים משותפים)')
  await expect(rowOf(page, 'ת"ז')).not.toContainText('+25')                 // no difference is shown
  await expect(page.getByRole('columnheader', { name: /model-c/ })).toBeVisible()
})

test('works without any records', async ({ page }) => {
  await expect(page.getByRole('banner')).toContainText('0 טפסים')
  await expect(page.getByRole('table')).toBeVisible()
})
