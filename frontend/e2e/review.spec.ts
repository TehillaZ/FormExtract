import { expect, test } from '@playwright/test'
import { fieldRow, fieldsPanel, formImage, formList, header, openForm, resetBackend, signIn, tableRow, uploadForms, widthOf } from './helpers'

test.beforeEach(async ({ page }) => {
  await resetBackend(page)
  await signIn(page)
})

test.describe('upload to table', () => {
  test('an uploaded form goes through the real pipeline and appears in the table', async ({ page }) => {
    await uploadForms(page, 'form-a')

    const row = page.getByRole('button', { name: /דנה/ })
    await expect(row).toContainText('כהן')
    await expect(row).toContainText('כללית')
    await expect(row).toContainText('730578626')
    // form A: names, central number, date and commitment number are read but unverified; ID and sender are verified
    await expect(page.getByText('5 שדות דורשים בדיקה')).toBeVisible()
    await expect(row.locator('[data-flagged="true"]')).toHaveCount(5)
  })

  test('right after an upload the form screen opens with the form image', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('tab', { name: 'העלאה' }).click()
    await page.getByLabel('בחירת קבצים').setInputFiles('e2e/fixtures/form-a.png')
    await expect(page.getByRole('tab', { name: 'טופס', selected: true })).toBeVisible()
    await expect(page.locator('img[src*="/pages/"]')).toBeVisible()
    await expect(page.getByRole('heading', { name: /דנה/ })).toBeVisible({ timeout: 30_000 })   // the fields arrive after
  })

  test('uploading the same file twice is recognised and not processed again', async ({ page }) => {
    await uploadForms(page, 'form-a')
    await page.getByRole('tab', { name: 'העלאה' }).click()
    await page.getByLabel('בחירת קבצים').setInputFiles('e2e/fixtures/form-a.png')
    await expect(page.getByText('קובץ זהה כבר הועלה בעבר, לא עובד שוב')).toBeVisible()
    await page.getByRole('tab', { name: 'טבלה' }).click()
    await expect(header(page)).toContainText('1 טפסים')
  })

  test('a form with almost nothing found shows empty fields and what was read for a rejected sender', async ({ page }) => {
    await uploadForms(page, 'form-c')
    await expect(page.getByText('7 שדות דורשים בדיקה')).toBeVisible()
    await openForm(page, 'לא נמצא')
    await expect(fieldRow(page, 'גורם שולח')).toContainText('נקרא: קליניקה לא ידועה')
    await expect(fieldRow(page, 'גורם שולח')).toContainText('— לא נמצא')
  })
})

test.describe('the form screen', () => {
  test('the page image really loads from the server', async ({ page }) => {
    await uploadForms(page, 'form-a')
    await openForm(page, /דנה/)
    const image = formImage(page)
    await expect(image).toBeVisible()
    await expect.poll(() => image.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth)).toBe(600)
  })

  test('layout is right to left: the form list on the right, the fields on the left', async ({ page }) => {
    await uploadForms(page, 'form-a', 'form-b')
    await openForm(page, /דנה/)
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
    const list = await formList(page).boundingBox()
    const fields = await fieldsPanel(page).boundingBox()
    const image = await formImage(page).boundingBox()
    expect(list!.x).toBeGreaterThan(image!.x)
    expect(image!.x).toBeGreaterThan(fields!.x)
  })

  test('the form image gets most of the screen', async ({ page }) => {
    await uploadForms(page, 'form-a')
    await openForm(page, /דנה/)
    const fields = await widthOf(fieldsPanel(page))
    const list = await widthOf(formList(page))
    expect(fields).toBeLessThan(340)
    const stage = 1440 - fields - list
    expect(stage).toBeGreaterThan(fields * 2)
  })

  test('the form list can be closed and opened, and the choice is remembered', async ({ page }) => {
    await uploadForms(page, 'form-a', 'form-b')
    await openForm(page, /דנה/)
    const list = formList(page)
    const imageBefore = await widthOf(page.locator('main img[alt="תמונת הטופס"]'))
    expect(await widthOf(list)).toBeCloseTo(236, 0)

    await page.getByRole('button', { name: 'סגירת הרשימה' }).click()
    await expect.poll(() => list.boundingBox().then((b) => b?.width ?? 0)).toBe(0)
    await expect(page.getByRole('button', { name: 'פתיחת רשימת הטפסים' })).toBeVisible()

    // the room it left goes to the picture
    await page.getByRole('button', { name: 'התאמה לרוחב' }).click()
    const stageWidth = await widthOf(page.locator('main img[alt="תמונת הטופס"]'))
    expect(stageWidth).toBeGreaterThan(imageBefore)

    await page.reload()
    await openForm(page, /דנה/)
    await expect(page.getByRole('button', { name: 'פתיחת רשימת הטפסים' })).toBeVisible()

    await page.getByRole('button', { name: 'פתיחת רשימת הטפסים' }).click()
    await expect.poll(() => list.boundingBox().then((b) => b?.width ?? 0)).toBeCloseTo(236, 0)
  })

  test('zooming changes the picture, and the expanded view covers the screen until Escape', async ({ page }) => {
    await uploadForms(page, 'form-a')
    await openForm(page, /דנה/)
    const image = formImage(page)
    await expect(image).toBeVisible()
    const before = await widthOf(image)

    await page.getByRole('button', { name: 'הגדלה' }).click()
    await expect.poll(() => widthOf(image)).toBeGreaterThan(before * 1.2)
    await page.getByRole('button', { name: 'התאמה לגובה' }).click()
    await expect.poll(() => widthOf(image)).toBeCloseTo(before, 0)

    await page.getByRole('button', { name: 'הרחבה למסך מלא' }).click()
    const dialog = page.getByRole('dialog', { name: 'תצוגה מוגדלת של הטופס' })
    const box = await dialog.boundingBox()
    expect(box).toMatchObject({ x: 0, y: 0, width: 1440, height: 900 })
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
  })
})

test.describe('checking and correcting fields', () => {
  test('confirming a flagged field clears its flag and lowers the totals', async ({ page }) => {
    await uploadForms(page, 'form-a')
    await openForm(page, /דנה/)
    await expect(fieldRow(page, 'שם פרטי')).toHaveAttribute('data-flagged', 'true')

    await fieldsPanel(page).getByRole('button', { name: 'אשרי שהערך של שם פרטי נכון' }).click()

    await expect(fieldRow(page, 'שם פרטי')).toHaveAttribute('data-flagged', 'false')
    await expect(fieldRow(page, 'שם פרטי')).toContainText('אושר ידנית')
    await expect(header(page)).toContainText('4 שדות לבדיקה')
  })

  test('re-saving the same value in the editor also clears the flag', async ({ page }) => {
    // the bug found in real use
    await uploadForms(page, 'form-a')
    await openForm(page, /דנה/)
    await fieldRow(page, 'שם משפחה').getByText('כהן').click()
    await page.getByRole('button', { name: 'שמרי', exact: true }).click()
    await expect(fieldRow(page, 'שם משפחה')).toHaveAttribute('data-flagged', 'false')
  })

  test('a corrected value is saved on the server and survives a reload', async ({ page }) => {
    await uploadForms(page, 'form-b')
    await openForm(page, /רונן/)
    await fieldRow(page, 'שם פרטי').getByText('רונן').click()
    const box = page.getByLabel('שם פרטי', { exact: true })
    await box.fill('רון')
    await box.press('Enter')
    await expect(fieldRow(page, 'שם פרטי')).toContainText('תוקן ידנית')
    await expect(fieldRow(page, 'שם פרטי')).toHaveAttribute('data-flagged', 'false')

    await page.reload()
    await page.getByRole('tab', { name: 'טבלה' }).click()
    await expect(page.getByRole('button', { name: /רון/ })).toContainText('פלג')
    await expect(page.getByText('רונן')).toHaveCount(0)
  })

  test('the server rejects an invalid value and the editor shows its message', async ({ page }) => {
    await uploadForms(page, 'form-a')
    await openForm(page, /דנה/)
    await fieldRow(page, 'מספר מרכזי').getByText('939376').click()
    const box = page.getByLabel('מספר מרכזי', { exact: true })
    await box.fill('12')
    await box.press('Enter')
    await expect(page.getByRole('alert')).toContainText('מספר מרכזי חייב להכיל 6 ספרות')
    await expect(box).toBeVisible()
  })

  test('a field that is really empty on the form can be confirmed as empty', async ({ page }) => {
    await uploadForms(page, 'form-c')
    await openForm(page, 'לא נמצא')
    await fieldsPanel(page).getByRole('button', { name: 'אשרי שמספר התחייבות ריק בטופס' }).click()
    await expect(fieldRow(page, 'מספר התחייבות')).toHaveAttribute('data-flagged', 'false')
    await expect(fieldRow(page, 'מספר התחייבות')).toContainText('אושר ידנית: אין בטופס')
  })

  test('a rejected ID shows what was read, and confirming a number list entry works through the list editor', async ({ page }) => {
    await uploadForms(page, 'form-b')
    await openForm(page, /רונן/)
    await expect(fieldRow(page, 'ת"ז')).toContainText('נקרא: 0011223344')

    await fieldRow(page, 'מספר מרכזי').getByText('939158').click()
    await page.getByRole('button', { name: '+ הוספת מספר' }).click()
    await page.getByLabel('מספר מרכזי', { exact: true }).nth(1).fill('939159')
    await page.getByRole('button', { name: 'שמרי', exact: true }).click()
    await expect(fieldRow(page, 'מספר מרכזי')).toContainText('939158 · 939159')
  })
})

test.describe('approving', () => {
  test('approving moves on to the next form that needs review and the table shows it approved', async ({ page }) => {
    await uploadForms(page, 'form-a', 'form-c')
    await openForm(page, /דנה/)
    await expect(page.getByRole('heading', { level: 2 })).toContainText('דנה כהן')

    await page.getByRole('button', { name: 'אשרי ושמרי' }).click()
    await expect(page.getByRole('heading', { level: 2 })).toContainText('ללא שם')

    await page.getByRole('tab', { name: 'טבלה' }).click()
    await expect(tableRow(page, 'דנה')).toContainText('מאושר')
    await expect(header(page)).toContainText('1 ממתינים')
  })

  test('two forms cannot be approved with the same commitment number', async ({ page }) => {
    await uploadForms(page, 'form-a', 'form-b')
    await openForm(page, /דנה/)
    await page.getByRole('button', { name: 'אשרי ושמרי' }).click()
    await expect(page.getByRole('heading', { level: 2 })).toContainText('רונן פלג')

    // the second form warns about the duplicate, and approving it is refused with a clear message
    await expect(page.getByText('מספר התחייבות 730578626 כבר קיים ברשומה אחרת')).toBeVisible()
    await page.getByRole('button', { name: 'אשרי ושמרי' }).click()
    await expect(page.getByRole('alert').filter({ hasText: 'כבר קיים ברשומה מאושרת' })).toBeVisible()
    await expect(page.getByRole('heading', { level: 2 })).toContainText('רונן פלג')
  })

  test('"approve all clean rows" approves the forms a person has finished checking', async ({ page }) => {
    await uploadForms(page, 'form-a', 'form-c')
    const approveClean = page.getByRole('button', { name: /אשרי את כל השורות התקינות/ })
    await expect(approveClean).toBeDisabled()

    await openForm(page, /דנה/)
    for (const label of ['שם פרטי', 'שם משפחה', 'מספר מרכזי', 'תאריך קבלה', 'מספר התחייבות']) {
      await fieldsPanel(page).getByRole('button', { name: new RegExp(`אשרי ש.*${label}`) }).click()
      await expect(fieldRow(page, label)).toHaveAttribute('data-flagged', 'false')
    }
    await expect(page.getByRole('heading', { level: 2 })).toContainText('דנה כהן')
    await expect(fieldsPanel(page)).toContainText('תקין')

    await page.getByRole('tab', { name: 'טבלה' }).click()
    await expect(approveClean).toBeEnabled()
    await approveClean.click()
    await expect(page.getByRole('status')).toContainText('אושרו 1 שורות')
    await expect(page.getByRole('button', { name: /דנה/ })).toContainText('מאושר')
    await expect(tableRow(page, 'לא נמצא')).not.toContainText('מאושר')
  })
})

test.describe('keyboard shortcuts', () => {
  test('A is refused while fields are flagged, and approves once every one is confirmed', async ({ page }) => {
    await uploadForms(page, 'form-a', 'form-c')
    await openForm(page, /דנה/)
    const title = page.getByRole('heading', { level: 2 })

    await page.keyboard.press('KeyA')
    await expect(page.getByRole('status')).toContainText('אי אפשר לאשר במקלדת')
    await expect(title).toContainText('דנה כהן')

    for (const label of ['שם פרטי', 'שם משפחה', 'מספר מרכזי', 'תאריך קבלה', 'מספר התחייבות']) {
      await fieldsPanel(page).getByRole('button', { name: new RegExp(`אשרי ש.*${label}`) }).click()
      await expect(fieldRow(page, label)).toHaveAttribute('data-flagged', 'false')
    }
    await page.keyboard.press('KeyA')
    await expect(title).toContainText('ללא שם')          // approved, and moved on to the next form to review

    await page.getByRole('tab', { name: 'טבלה' }).click()
    await expect(tableRow(page, 'דנה')).toContainText('מאושר')
  })

  test('the arrow keys and N move between forms, and typing in a field does not trigger them', async ({ page }) => {
    await uploadForms(page, 'form-a', 'form-b')
    await openForm(page, /דנה/)
    const title = page.getByRole('heading', { level: 2 })

    await page.keyboard.press('ArrowDown')
    await expect(title).toContainText('רונן פלג')
    await page.keyboard.press('ArrowUp')
    await expect(title).toContainText('דנה כהן')
    await page.keyboard.press('KeyN')
    await expect(title).toContainText('רונן פלג')

    await fieldRow(page, 'שם פרטי').getByText('רונן').click()
    const box = page.getByLabel('שם פרטי', { exact: true })
    await box.press('Control+a')
    await page.keyboard.type('nal')                      // N, A and L are all shortcuts
    await expect(box).toHaveValue('nal')
    await expect(title).toContainText('רונן פלג')
  })
})
