import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { EvaluationReport } from '../api/types'
import { makeReport, result } from '../test/factories'
import { installFakeApi } from '../test/fakeApi'
import { renderWithClient } from '../test/render'
import { AccuracyView } from './AccuracyView'

const coverage = { pages: 48, dev_pages: 34, test_pages: 14 }

async function open(reports: EvaluationReport[], extra: Partial<typeof coverage> = {}) {
  const api = installFakeApi()
  api.evaluation = { reports, ...coverage, ...extra }
  renderWithClient(<AccuracyView />)
  await screen.findByRole('heading', { name: 'דוח דיוק' })
  return { api, user: userEvent.setup() }
}

const rowOf = (field: string) => screen.getByRole('rowheader', { name: field }).closest('tr') as HTMLElement

const reportA = () => makeReport()   // model-a: ID 35% with 4 silent errors
const reportB = () => makeReport({
  tag: 'gemini-model-b-def456', model: 'model-b', prompt_id: 'def456', created_at: '2026-10-19T10:00:00Z',
  fields: { ...makeReport().fields, id_number: result(20, 11, 7, 1) },   // ID 55%, one silent error
})

describe('AccuracyView: with no reports', () => {
  it('explains how to produce one', async () => {
    await open([])
    expect(screen.getByText('עדיין אין דוחות דיוק.')).toBeInTheDocument()
    expect(screen.getByText(/python scripts\/evaluate\.py/)).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('says so when the reports cannot be loaded', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderWithClient(<AccuracyView />)
    expect(await screen.findByRole('alert')).toHaveTextContent('לא ניתן לטעון את דוחות הדיוק')
  })
})

describe('AccuracyView: one report', () => {
  it('shows accuracy, share flagged and errors that were not flagged for each field', async () => {
    await open([reportA()])
    const id = rowOf('ת"ז')
    expect(id).toHaveTextContent('35%')              // 7 of 20
    expect(id).toHaveTextContent('55%')              // 11 of 20 flagged
    expect(id).toHaveTextContent('4 מתוך 13')        // 4 of the 13 errors were not flagged
    expect(rowOf('גורם שולח')).toHaveTextContent('70%')
  })

  it('highlights fields that have errors nobody was warned about, and only those', async () => {
    await open([reportA()])
    expect(within(rowOf('ת"ז')).getByText('4 מתוך 13')).toHaveAttribute('data-silent', 'true')
    expect(within(rowOf('מספר התחייבות')).getByText('1 מתוך 5')).toHaveAttribute('data-silent', 'true')
    expect(within(rowOf('גורם שולח')).getByText('0 מתוך 6')).toHaveAttribute('data-silent', 'false')
  })

  it('adds up the errors that were not flagged', async () => {
    await open([reportA()])
    expect(screen.getByText('סך שגיאות שלא סומנו').closest('tr')).toHaveTextContent('5')
  })

  it('shows how many pages stand behind the numbers, out of how many exist', async () => {
    await open([reportA()])
    expect(screen.getAllByText(/20 עמודים/).length).toBeGreaterThan(0)
    expect(screen.getByText(/20 מתוך 34 עמודים/)).toBeInTheDocument()
  })

  it('says which model, which split, and the ID mode', async () => {
    await open([reportA()])
    const picker = screen.getByRole('group', { name: /השוואה/ })
    expect(picker).toHaveTextContent('model-a · עמודי פיתוח')
    expect(picker).toHaveTextContent('ת"ז: strict')
  })
})

describe('AccuracyView: what was not measured', () => {
  it('warns loudly that the test set has not been run, with the page counts', async () => {
    await open([reportA()])
    const warning = screen.getByTestId('test-not-run')
    expect(warning).toHaveTextContent('סט הבדיקה (14 עמודים) טרם הורץ')
    expect(warning).toHaveTextContent('34 עמודים')
  })

  it('stops warning once a test-set report exists', async () => {
    await open([reportA(), makeReport({ tag: 'gemini-model-a-abc123', split: 'test', pages_scored: 14 })])
    expect(screen.queryByTestId('test-not-run')).not.toBeInTheDocument()
  })

  it('always says the samples are highlighted, so real accuracy is probably lower', async () => {
    await open([reportA()])
    expect(screen.getByRole('note')).toHaveTextContent('מסומנות במרקר צהוב')
    expect(screen.getByRole('note')).toHaveTextContent('שגיאה שלא סומנה')
  })
})

describe('AccuracyView: comparing reports', () => {
  it('compares the two newest reports by default, with the change in accuracy from the first', async () => {
    await open([reportA(), reportB()])
    const id = rowOf('ת"ז')
    expect(id).toHaveTextContent('35%')
    expect(id).toHaveTextContent('55%')
    expect(id).toHaveTextContent('+20')               // model-b is 20 points better on the ID
    expect(rowOf('גורם שולח')).toHaveTextContent('±0')
  })

  it('shows a drop as a negative change', async () => {
    await open([reportB(), reportA()])   // the better model first: the second column is compared against it
    expect(rowOf('ת"ז')).toHaveTextContent('−20')
  })

  it('lets the user add and remove reports from the comparison', async () => {
    const { user } = await open([reportA(), reportB()])
    const picker = screen.getByRole('group', { name: /השוואה/ })
    expect(screen.getAllByRole('columnheader', { name: /model-/ })).toHaveLength(2)

    await user.click(within(picker).getByRole('checkbox', { name: /model-b/ }))
    expect(screen.getAllByRole('columnheader', { name: /model-/ })).toHaveLength(1)
    expect(rowOf('ת"ז')).not.toHaveTextContent('+20')   // nothing to compare with

    await user.click(within(picker).getByRole('checkbox', { name: /model-a/ }))
    expect(screen.getByText('בחרי דוח אחד או יותר להצגה.')).toBeInTheDocument()
  })

  it('compares at most three reports at once: choosing a fourth drops the oldest choice', async () => {
    const third = makeReport({ tag: 'gemini-model-c-1', model: 'model-c', created_at: '2026-10-18T10:00:00Z' })
    const fourth = makeReport({ tag: 'gemini-model-d-1', model: 'model-d', created_at: '2026-10-17T10:00:00Z' })
    const { user } = await open([reportA(), reportB(), third, fourth])
    const picker = screen.getByRole('group', { name: /השוואה/ })

    await user.click(within(picker).getByRole('checkbox', { name: /model-c/ }))      // now a, b, c
    expect(screen.getAllByRole('columnheader', { name: /model-/ })).toHaveLength(3)
    await user.click(within(picker).getByRole('checkbox', { name: /model-d/ }))      // d replaces the oldest choice, a
    await waitFor(() => expect(screen.getAllByRole('columnheader', { name: /model-/ })).toHaveLength(3))
    expect(screen.queryByRole('columnheader', { name: /model-a/ })).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: /model-d/ })).toBeInTheDocument()
  })

  it('shows a dash for a field a report does not have', async () => {
    const sparse = makeReport({ tag: 'gemini-model-s-1', model: 'model-s', created_at: '2026-10-18T10:00:00Z', fields: { sender: result(20, 14, 7, 0) } })
    await open([reportA(), sparse])
    expect(rowOf('ת"ז')).toHaveTextContent('—')
  })

  it('notes that small differences are noise with so few pages', async () => {
    await open([reportA(), reportB()])
    expect(screen.getByText(/בגדר רעש/)).toBeInTheDocument()
  })
})
