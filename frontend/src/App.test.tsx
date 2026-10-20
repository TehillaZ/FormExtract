import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { field, flaggedRecord, makeRecord } from './test/factories'
import { installFakeApi } from './test/fakeApi'
import { renderWithClient } from './test/render'

const sample = () => [makeRecord('a'), flaggedRecord('b', 'רונן', 'לוי', { received_date: field('2026-06-19', 'medium') })]

async function openApp(records = sample()) {
  const api = installFakeApi(records)
  renderWithClient(<App />)
  await screen.findByText('רונן')   // the table has loaded
  return { api, user: userEvent.setup() }
}

const header = () => screen.getByRole('banner')

describe('App', () => {
  it('starts on the table with the totals in the header', async () => {
    await openApp()
    expect(screen.getByRole('tab', { name: 'טבלה', selected: true })).toBeInTheDocument()
    expect(header()).toHaveTextContent('2 טפסים · 2 ממתינים · 2 שדות לבדיקה')
  })

  it('opens the form behind a clicked table row', async () => {
    const { user } = await openApp()
    await user.click(screen.getByText('רונן'))
    expect(screen.getByRole('tab', { name: 'טופס', selected: true })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('רונן לוי')
  })

  it('a field confirmed on the form clears the totals and the table', async () => {
    const { user } = await openApp()
    await user.click(screen.getByText('רונן'))
    await user.click(screen.getByRole('button', { name: 'אשרי שהערך של שם פרטי נכון' }))
    await user.click(screen.getByRole('button', { name: 'אשרי שהערך של תאריך קבלה נכון' }))

    await waitFor(() => expect(header()).toHaveTextContent('0 שדות לבדיקה'))
    await user.click(screen.getByRole('tab', { name: 'טבלה' }))
    expect(screen.getByText('רונן').closest('[data-flagged]')).toHaveAttribute('data-flagged', 'false')
    expect(screen.getByText('0 שדות דורשים בדיקה')).toBeInTheDocument()
  })

  it('a corrected field is reflected on the form and then in the table', async () => {
    const { api, user } = await openApp()
    await user.click(screen.getByText('רונן'))
    await user.click(screen.getByText('רונן'))
    const input = screen.getByLabelText('שם פרטי')
    await user.clear(input)
    await user.type(input, 'רן{Enter}')

    await waitFor(() => expect(api.called('PATCH', '/records/b')).toHaveLength(1))
    await user.click(screen.getByRole('tab', { name: 'טבלה' }))
    expect(await screen.findByText('רן')).toBeInTheDocument()
    expect(screen.queryByText('רונן')).not.toBeInTheDocument()
  })

  it('approving all clean rows from the table updates the totals', async () => {
    const { user } = await openApp()
    await user.click(screen.getByRole('button', { name: /אשרי את כל השורות התקינות/ }))
    await waitFor(() => expect(header()).toHaveTextContent('1 ממתינים'))
  })

  it('switches to the upload screen', async () => {
    const { user } = await openApp()
    await user.click(screen.getByRole('tab', { name: 'העלאה' }))
    expect(screen.getByText('גררי לכאן קבצי טפסים')).toBeInTheDocument()
  })

  it('tells the user when the server cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderWithClient(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('לא ניתן להתחבר לשרת')
  })

  it('shows an empty table and a way to upload when there are no forms yet', async () => {
    installFakeApi([])
    renderWithClient(<App />)
    expect(await screen.findByText('אין שורות להצגה')).toBeInTheDocument()
    expect(within(header()).getByRole('tab', { name: 'העלאה' })).toBeInTheDocument()
  })
})

describe('App: records and accuracy screens', () => {
  it('has tabs for records and the accuracy report', async () => {
    await openApp()
    expect(screen.getByRole('tab', { name: 'רשומות' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'דוח דיוק' })).toBeInTheDocument()
  })

  it('opens the form behind a record picked on the records screen', async () => {
    const { user } = await openApp()
    await user.click(screen.getByRole('tab', { name: 'רשומות' }))
    await user.click(await screen.findByRole('button', { name: /רונן לוי/ }))
    expect(screen.getByRole('tab', { name: 'טופס', selected: true })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('רונן לוי')
  })

  it('a record approved elsewhere shows as approved on the records screen', async () => {
    const { user } = await openApp()
    await user.click(screen.getByRole('tab', { name: 'רשומות' }))
    await screen.findByRole('button', { name: /דנה כהן/ })
    await user.click(screen.getByRole('tab', { name: 'טבלה' }))
    await user.click(screen.getByRole('button', { name: /אשרי את כל השורות התקינות/ }))
    await waitFor(() => expect(header()).toHaveTextContent('1 ממתינים'))

    await user.click(screen.getByRole('tab', { name: 'רשומות' }))
    await waitFor(() => expect(screen.getByRole('button', { name: /דנה כהן/ })).toHaveTextContent('מאושר'))
  })

  it('the accuracy report works even when the records cannot be loaded', async () => {
    const api = installFakeApi([])
    api.evaluation = { reports: [], pages: 48, dev_pages: 34, test_pages: 14 }
    const realFetch = globalThis.fetch
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      String(input).startsWith('/api/records') ? Promise.reject(new TypeError('down')) : realFetch(input, init)))
    renderWithClient(<App />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('tab', { name: 'דוח דיוק' }))
    expect(await screen.findByText('עדיין אין דוחות דיוק.')).toBeInTheDocument()
  })
})
