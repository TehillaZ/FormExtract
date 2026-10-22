import { expect, test, type Download, type Page } from '@playwright/test'
import fs from 'node:fs'
import { openForm, resetBackend, signIn, seedRecords, tableRow, uploadForms } from './helpers'

test.beforeEach(async ({ page }) => {
  await resetBackend(page)
  await signIn(page)
})

const status = (page: Page) => page.getByRole('status')

async function openRecords(page: Page) {
  await page.getByRole('tab', { name: 'רשומות' }).click()
  await expect(status(page)).not.toHaveText('טוען…')
}

/** Seed straight into the database, then show the records screen. */
async function openSeeded(page: Page, n: number, approved = 0) {
  await seedRecords(page, n, approved)
  await page.goto('/')
  await openRecords(page)
}

async function downloaded(page: Page, link: string | RegExp): Promise<{ file: Download; bytes: Buffer }> {
  const [file] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: link }).click()])
  return { file, bytes: fs.readFileSync(await file.path()) }
}

const csvLines = (bytes: Buffer) => bytes.toString('utf-8').replace(/^﻿/, '').split('\r\n').filter(Boolean)

test.describe('records screen', () => {
  test('lists the forms from every upload and filters them by status', async ({ page }) => {
    await uploadForms(page, 'form-a', 'form-b')
    await openForm(page, /דנה/)
    await page.getByRole('button', { name: 'אשרי ושמרי' }).click()          // approves form A
    await openRecords(page)
    await expect(status(page)).toHaveText('מציג 1–2 מתוך 2 רשומות')

    await page.getByLabel('סטטוס').selectOption('approved')
    await expect(status(page)).toHaveText('מציג 1–1 מתוך 1 רשומות')
    await expect(tableRow(page, 'דנה')).toContainText('מאושר')
    await expect(tableRow(page, 'רונן')).toHaveCount(0)

    await page.getByRole('button', { name: 'נקי סינון' }).click()
    await expect(status(page)).toHaveText('מציג 1–2 מתוך 2 רשומות')
  })

  test('searching finds a person by name', async ({ page }) => {
    await uploadForms(page, 'form-a', 'form-b')
    await openRecords(page)
    await page.getByLabel('חיפוש רשומות').fill('פלג')
    await expect(status(page)).toHaveText('מציג 1–1 מתוך 1 רשומות')
    await expect(tableRow(page, 'רונן')).toBeVisible()
    await expect(tableRow(page, 'דנה')).toHaveCount(0)
  })

  test('filters by sender and by received date', async ({ page }) => {
    await uploadForms(page, 'form-a', 'form-b')      // A: כללית, received 18/06; B: מכבי, received 16/06
    await openRecords(page)

    await page.getByLabel('גורם שולח').selectOption('מכבי')
    await expect(status(page)).toHaveText('מציג 1–1 מתוך 1 רשומות')
    await expect(tableRow(page, 'רונן')).toBeVisible()
    await page.getByRole('button', { name: 'נקי סינון' }).click()

    await page.getByLabel('תאריך קבלה מ-').fill('2026-06-17')
    await expect(status(page)).toHaveText('מציג 1–1 מתוך 1 רשומות')
    await expect(tableRow(page, 'דנה')).toBeVisible()
    await page.getByLabel('תאריך קבלה עד').fill('2026-06-17')
    await expect(status(page)).toHaveText('אין רשומות מתאימות')       // nothing was received exactly on the 17th
  })

  test('picking a record opens its form', async ({ page }) => {
    await uploadForms(page, 'form-a')
    await openRecords(page)
    await tableRow(page, 'דנה').click()
    await expect(page.getByRole('tab', { name: 'טופס', selected: true })).toBeVisible()
    await expect(page.getByRole('heading', { level: 2 })).toContainText('דנה כהן')
  })

  test('pages through many records using the real total', async ({ page }) => {
    await openSeeded(page, 30)
    await expect(status(page)).toHaveText('מציג 1–25 מתוך 30 רשומות')
    await expect(tableRow(page, 'דמה')).toHaveCount(25)
    await expect(page.getByRole('button', { name: 'הקודם' })).toBeDisabled()

    await page.getByRole('button', { name: 'הבא' }).click()
    await expect(status(page)).toHaveText('מציג 26–30 מתוך 30 רשומות')
    await expect(tableRow(page, 'דמה')).toHaveCount(5)
    await expect(page.getByRole('button', { name: 'הבא' })).toBeDisabled()

    await page.getByRole('button', { name: 'הקודם' }).click()
    await expect(tableRow(page, 'דמה')).toHaveCount(25)
  })

  test('an edit made on the form shows on the records screen', async ({ page }) => {
    await uploadForms(page, 'form-a')
    await openRecords(page)
    await expect(tableRow(page, 'דנה')).toContainText('ממתין')
    await tableRow(page, 'דנה').click()
    await page.getByRole('button', { name: 'אשרי ושמרי' }).click()
    await page.getByRole('tab', { name: 'רשומות' }).click()
    await expect(tableRow(page, 'דנה')).toContainText('מאושר')
  })
})

test.describe('export', () => {
  test('CSV: downloads exactly the filtered records, not just the page on screen', async ({ page }) => {
    await openSeeded(page, 30, 5)
    await page.getByLabel('סטטוס').selectOption('approved')
    await expect(status(page)).toHaveText('מציג 1–5 מתוך 5 רשומות')

    const { file, bytes } = await downloaded(page, /CSV/)

    expect(file.suggestedFilename()).toMatch(/^forms-\d{8}-\d{4}\.csv$/)
    expect(bytes.subarray(0, 3)).toEqual(Buffer.from([0xef, 0xbb, 0xbf]))          // byte-order mark: Excel shows Hebrew
    const lines = csvLines(bytes)
    expect(lines).toHaveLength(6)                                                  // header + the 5 approved
    expect(lines[0]).toContain('שם פרטי')
    for (const line of lines.slice(1)) expect(line).toContain('מאושר')
  })

  test('CSV: covers every record even when the list needs several pages', async ({ page }) => {
    await openSeeded(page, 30)
    await expect(status(page)).toHaveText('מציג 1–25 מתוך 30 רשומות')
    expect(csvLines((await downloaded(page, /CSV/)).bytes)).toHaveLength(31)       // header + all 30
  })

  test('Excel: downloads a real workbook', async ({ page }) => {
    await openSeeded(page, 5, 2)
    const { file, bytes } = await downloaded(page, /Excel/)
    expect(file.suggestedFilename()).toMatch(/^forms-\d{8}-\d{4}\.xlsx$/)
    expect(bytes.subarray(0, 2).toString()).toBe('PK')                             // an .xlsx file is a zip
    expect(bytes.toString('latin1')).toContain('xl/worksheets/sheet1.xml')
  })

  test('follows the search on screen', async ({ page }) => {
    await openSeeded(page, 30)
    await page.getByLabel('חיפוש רשומות').fill('דמה03')
    await expect(status(page)).toHaveText('מציג 1–1 מתוך 1 רשומות')
    const lines = csvLines((await downloaded(page, /CSV/)).bytes)
    expect(lines).toHaveLength(2)
    expect(lines[1]).toContain('דמה03')
  })

  test('is switched off when nothing matches', async ({ page }) => {
    await openSeeded(page, 3)
    await page.getByLabel('חיפוש רשומות').fill('zzzz')
    await expect(status(page)).toHaveText('אין רשומות מתאימות')
    await expect(page.getByText('ייצוא ל-Excel')).toHaveAttribute('aria-disabled', 'true')
    await expect(page.getByRole('link', { name: /Excel|CSV/ })).toHaveCount(0)
  })
})
