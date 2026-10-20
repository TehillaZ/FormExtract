import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { CommitmentRecord } from '../api/types'
import { field, flaggedRecord, makeRecord } from '../test/factories'
import { installFakeApi } from '../test/fakeApi'
import { renderWithClient } from '../test/render'
import { RecordsView } from './RecordsView'

const named = (id: string, first: string, last: string, over: Partial<CommitmentRecord> = {}) =>
  makeRecord(id, { first_name: field(first), last_name: field(last), ...over })

const sample = () => [
  named('a', 'דנה', 'כהן', { received_date: field('2026-06-10'), sender: field('כללית'), commitment_numbers: [field('111111111')] }),
  named('b', 'רונן', 'פלג', { received_date: field('2026-06-15'), sender: field('מכבי'), status: 'approved', approved_at: '2026-06-16T10:00:00Z', commitment_numbers: [field('222222222')] }),
  flaggedRecord('c', 'משה', 'ישראלי', { received_date: field('2026-06-20'), sender: field('כללית'), commitment_numbers: [field('333333333')] }),
]

async function open(records = sample(), onOpen = () => {}) {
  const api = installFakeApi(records)
  renderWithClient(<RecordsView onOpen={onOpen} />)
  await screen.findByRole('status')
  await waitFor(() => expect(screen.getByRole('status')).not.toHaveTextContent('טוען'))
  return { api, user: userEvent.setup() }
}

const listCalls = (api: ReturnType<typeof installFakeApi>) => api.calls.filter((c) => c.method === 'GET' && c.path.startsWith('/records?'))
const lastListCall = (api: ReturnType<typeof installFakeApi>) => new URLSearchParams(listCalls(api).at(-1)!.path.split('?')[1])

describe('RecordsView: the list', () => {
  it('shows each record with its name, ID, number, date, sender and commitment number', async () => {
    await open()
    const row = screen.getByRole('button', { name: /דנה כהן/ })
    for (const text of ['011223344', '939376', '10/06/2026', 'כללית', '111111111']) expect(row).toHaveTextContent(text)
    expect(screen.getByRole('status')).toHaveTextContent('מציג 1–3 מתוך 3 רשומות')
  })

  it('shows approval status, and the number of flagged fields on a pending form', async () => {
    await open()
    const approved = screen.getByRole('button', { name: /רונן פלג/ })
    expect(approved).toHaveTextContent('מאושר')
    expect(within(approved).getByText('מאושר')).toHaveAttribute('title', 'אושר ב-16/06/2026')
    const pending = screen.getByRole('button', { name: /משה ישראלי/ })
    expect(pending).toHaveTextContent('ממתין')
    expect(within(pending).getByText('1')).toBeInTheDocument()
  })

  it('opens a record when its row is clicked', async () => {
    const onOpen = vi.fn()
    const { user } = await open(sample(), onOpen)
    await user.click(screen.getByRole('button', { name: /דנה כהן/ }))
    expect(onOpen).toHaveBeenCalledWith('a')
  })

  it('says so when nothing is stored', async () => {
    await open([])
    expect(screen.getByRole('status')).toHaveTextContent('אין רשומות מתאימות')
    expect(screen.getAllByText('אין רשומות מתאימות')).toHaveLength(2)
  })

  it('says so when the server cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderWithClient(<RecordsView onOpen={() => {}} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('לא ניתן לטעון את הרשומות')
  })
})

describe('RecordsView: filters', () => {
  it('searching waits for a pause in typing, then asks the server once', async () => {
    const { api, user } = await open()
    const before = listCalls(api).length
    await user.type(screen.getByLabelText('חיפוש רשומות'), 'פלג')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('מתוך 1 רשומות'))   // the filtered answer arrived

    const searches = listCalls(api).slice(before).map((c) => new URLSearchParams(c.path.split('?')[1]).get('q'))
    expect(searches.filter(Boolean)).toEqual(['פלג'])       // never 'פ' or 'פל'
    expect(screen.getByRole('status')).toHaveTextContent('מציג 1–1 מתוך 1 רשומות')
  })

  it('searching also finds by ID and by commitment number', async () => {
    const { user } = await open()
    await user.type(screen.getByLabelText('חיפוש רשומות'), '333333333')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('מתוך 1 רשומות'))
    expect(screen.getByRole('button', { name: /משה ישראלי/ })).toBeInTheDocument()
  })

  it('filters by status', async () => {
    const { api, user } = await open()
    await user.selectOptions(screen.getByLabelText('סטטוס'), 'approved')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('מתוך 1 רשומות'))
    expect(lastListCall(api).get('status')).toBe('approved')
    expect(screen.getByRole('button', { name: /רונן פלג/ })).toBeInTheDocument()
  })

  it('lists the senders the server knows and filters by one', async () => {
    const { api, user } = await open()
    const select = screen.getByLabelText('גורם שולח')
    await waitFor(() => expect(within(select).getAllByRole('option')).toHaveLength(5))   // all + 4 senders
    await user.selectOptions(select, 'כללית')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('מתוך 2 רשומות'))
    expect(lastListCall(api).get('sender')).toBe('כללית')
  })

  it('filters by received date, both ends included', async () => {
    const { api, user } = await open()
    await user.type(screen.getByLabelText('תאריך קבלה מ-'), '2026-06-15')
    await user.type(screen.getByLabelText('תאריך קבלה עד'), '2026-06-20')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('מתוך 2 רשומות'))
    const call = lastListCall(api)
    expect([call.get('from'), call.get('to')]).toEqual(['2026-06-15', '2026-06-20'])
  })

  it('offers "clear filters" only when a filter is set, and clears them all', async () => {
    const { user } = await open()
    expect(screen.queryByRole('button', { name: 'נקי סינון' })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('סטטוס'), 'pending')
    await user.selectOptions(screen.getByLabelText('גורם שולח'), 'מכבי')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('אין רשומות מתאימות'))

    await user.click(screen.getByRole('button', { name: 'נקי סינון' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('מתוך 3 רשומות'))
    expect(screen.getByLabelText('סטטוס')).toHaveValue('')
    expect(screen.queryByRole('button', { name: 'נקי סינון' })).not.toBeInTheDocument()
  })
})

describe('RecordsView: paging', () => {
  const many = (n: number) => Array.from({ length: n }, (_, i) => named(`r${i}`, 'שם', `מס${String(i).padStart(2, '0')}`, { commitment_numbers: [field(`4000000${String(i).padStart(2, '0')}`)] }))

  it('shows one page of 25 and the total, with no pager when everything fits', async () => {
    await open(many(25))
    expect(screen.getByRole('status')).toHaveTextContent('מציג 1–25 מתוך 25 רשומות')
    expect(screen.queryByRole('navigation', { name: 'דפי תוצאות' })).not.toBeInTheDocument()
  })

  it('pages through the results using the server total', async () => {
    const { api, user } = await open(many(30))
    expect(screen.getByRole('status')).toHaveTextContent('מציג 1–25 מתוך 30 רשומות')
    expect(screen.getByText('עמוד 1 מתוך 2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'הקודם' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'הבא' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('מציג 26–30 מתוך 30 רשומות'))
    expect(lastListCall(api).get('offset')).toBe('25')
    expect(screen.getByRole('button', { name: 'הבא' })).toBeDisabled()
    expect(screen.getByText('עמוד 2 מתוך 2')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'הקודם' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('מציג 1–25'))
  })

  it('a new filter goes back to the first page', async () => {
    const { user } = await open(many(30))
    await user.click(screen.getByRole('button', { name: 'הבא' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('מציג 26–30'))
    await user.selectOptions(screen.getByLabelText('סטטוס'), 'pending')
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('מציג 1–25 מתוך 30'))
  })
})

describe('RecordsView: export', () => {
  const link = (name: RegExp) => screen.getByRole('link', { name })

  it('has Excel and CSV links that download every matching record', async () => {
    await open()
    expect(link(/Excel/)).toHaveAttribute('href', '/api/export?format=xlsx')
    expect(link(/CSV/)).toHaveAttribute('href', '/api/export?format=csv')
    expect(link(/Excel/)).toHaveAttribute('download')
    expect(link(/CSV/)).toHaveAttribute('download')
  })

  it('the links follow the filters on screen, and never carry paging', async () => {
    const { user } = await open()
    await user.selectOptions(screen.getByLabelText('סטטוס'), 'approved')
    await user.selectOptions(screen.getByLabelText('גורם שולח'), 'מכבי')
    await waitFor(() => expect(link(/Excel/).getAttribute('href')).toContain('status=approved'))

    const url = new URL(link(/Excel/).getAttribute('href')!, 'http://x')
    expect(url.pathname).toBe('/api/export')
    expect(Object.fromEntries(url.searchParams)).toEqual({ status: 'approved', sender: 'מכבי', format: 'xlsx' })
  })

  it('is switched off, not a dead link, when there is nothing to export', async () => {
    await open([])
    const excel = screen.getByText('ייצוא ל-Excel')
    expect(excel).toHaveAttribute('aria-disabled', 'true')
    expect(screen.queryByRole('link', { name: /Excel/ })).not.toBeInTheDocument()
  })

  it('explains that the export covers all matches and that only Excel keeps leading zeros', async () => {
    await open()
    expect(screen.getByText(/כולל את כל הרשומות המסוננות/)).toHaveTextContent('אפסים מובילים')
  })
})
