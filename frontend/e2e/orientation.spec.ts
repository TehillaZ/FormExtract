import { expect, test, type Locator } from '@playwright/test'
import { formImage, modelCalls, openForm, resetBackend, uploadForms } from './helpers'

/** Scans arrive turned: the pipeline must find the right way up, and the reviewer must see the corrected page. */
test.beforeEach(async ({ page }) => {
  await resetBackend(page)
})

/** Brightness (0 black .. 255 white) of one pixel of the picture as the browser really loaded it. */
function pixelAt(image: Locator, x: number, y: number): Promise<number> {
  return image.evaluate((img: HTMLImageElement, [px, py]) => {
    const canvas = document.createElement('canvas')
    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(img, 0, 0)
    const [r, g, b] = ctx.getImageData(px, py, 1, 1).data
    return (r + g + b) / 3
  }, [x, y])
}

const naturalSize = (image: Locator) => image.evaluate((img: HTMLImageElement) => ({ w: img.naturalWidth, h: img.naturalHeight }))

/** The marked page has a black block in its upright top-left corner (see backend/e2e/make_fixtures.py). */
async function expectMarkerOnTop(image: Locator, height: number) {
  expect(await pixelAt(image, 60, 60), 'marker block at the top-left').toBeLessThan(40)
  expect(await pixelAt(image, 60, height - 60), 'nothing dark at the bottom-left').toBeGreaterThan(200)
}

test('a sideways scan is turned upright, read once, and shown upright to the reviewer', async ({ page }) => {
  // uploaded as 800 x 600 with vertical text; one clockwise turn makes it the 600 x 800 form A
  await uploadForms(page, 'sideways')
  await expect(page.getByRole('button', { name: /דנה/ })).toContainText('כללית')   // the model saw an upright page

  await openForm(page, /דנה/)
  const image = formImage(page)
  await expect.poll(() => naturalSize(image)).toEqual({ w: 600, h: 800 })        // portrait again, not the 800 x 600 upload
  expect(await modelCalls(page)).toBe(1)                                         // turning is local: no extra call
})

test('an upside-down scan is flipped after the model says so, at the price of one more call', async ({ page }) => {
  await uploadForms(page, 'upside-down')
  await expect(page.getByRole('button', { name: /יעל/ })).toContainText('אדם')   // the second answer is the real one

  await openForm(page, /יעל/)
  const image = formImage(page)
  await expect.poll(() => naturalSize(image)).toEqual({ w: 630, h: 800 })
  await expectMarkerOnTop(image, 800)
  expect(await modelCalls(page)).toBe(2)
})

test('a sideways scan that is also upside down is turned and then flipped', async ({ page }) => {
  await uploadForms(page, 'sideways-flipped')
  await expect(page.getByRole('button', { name: /יעל/ })).toContainText('אדם')

  await openForm(page, /יעל/)
  const image = formImage(page)
  await expect.poll(() => naturalSize(image)).toEqual({ w: 630, h: 800 })
  await expectMarkerOnTop(image, 800)
  expect(await modelCalls(page)).toBe(2)
})

test('an upright scan costs a single call and is left as it was', async ({ page }) => {
  await uploadForms(page, 'form-a')
  await openForm(page, /דנה/)
  await expect.poll(() => naturalSize(formImage(page))).toEqual({ w: 600, h: 800 })
  expect(await modelCalls(page)).toBe(1)
})
