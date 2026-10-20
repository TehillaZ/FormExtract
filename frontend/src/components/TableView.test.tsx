import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { field, flaggedRecord, makeRecord } from '../test/factories'
import { installFakeApi } from '../test/fakeApi'
import { renderWithClient } from '../test/render'
import { TableView } from './TableView'

const sample = () => [
  makeRecord('a'),                                                                              // clean
  flaggedRecord('b', 'רונן', 'לוי'),                                                            // 1 flagged
  flaggedRecord('c', 'משה', 'ישראלי', { commitment_numbers: [field(null, 'low', ['לא נמצא'])] }),   // 2 flagged, one empty
  makeRecord('d', { status: 'approved', first_name: field('אבי', 'low'), last_name: field('גל') }),   // approved: not highlighted
]

function renderTable(records = sample(), onOpen = () => {}) {
  const api = installFakeApi(records)
  renderWithClient(<TableView records={records} onOpen={onOpen} />)
  return api
}

const cell = (text: string) => screen.getByText(text).closest('[data-flagged]') as HTMLElement

describe('TableView', () => {
  it('counts the forms and the fields that need review (approved forms do not count)', () => {
    renderTable()
    expect(screen.getByText('4 טפסים')).toBeInTheDocument()
    expect(screen.getByText('3 שדות דורשים בדיקה')).toBeInTheDocument()
  })

  it('marks uncertain cells and leaves verified ones alone', () => {
    renderTable()
    expect(cell('רונן')).toHaveAttribute('data-flagged', 'true')
    expect(cell('דנה')).toHaveAttribute('data-flagged', 'false')
  })

  it('shows the reason as a tooltip on an uncertain cell', () => {
    renderTable()
    expect(cell('רונן')).toHaveAttribute('title', 'כתב יד')
  })

  it('shows an empty field as "not found", clearly different from a value', () => {
    renderTable()
    const empty = screen.getByText('— לא נמצא').closest('[data-empty]') as HTMLElement
    expect(empty).toHaveAttribute('data-empty', 'true')
    expect(empty).toHaveAttribute('data-flagged', 'true')
  })

  it('does not highlight cells of approved forms', () => {
    renderTable()
    expect(cell('אבי')).toHaveAttribute('data-flagged', 'false')
    expect(within(screen.getByText('אבי').closest('button')!).getByText('מאושר')).toBeInTheDocument()
  })

  it('"only rows to review" hides the clean and approved rows', async () => {
    renderTable()
    await userEvent.click(screen.getByLabelText('הצג רק שורות עם שדות לבדיקה'))
    expect(screen.queryByText('דנה')).not.toBeInTheDocument()
    expect(screen.queryByText('אבי')).not.toBeInTheDocument()
    expect(screen.getByText('רונן')).toBeInTheDocument()
    expect(screen.getByText('משה')).toBeInTheDocument()
  })

  it('opens a form when its row is clicked', async () => {
    const onOpen = vi.fn()
    renderTable(sample(), onOpen)
    await userEvent.click(screen.getByText('רונן'))
    expect(onOpen).toHaveBeenCalledWith('b')
  })

  it('shows a message when there is nothing to show', async () => {
    renderTable([])
    expect(screen.getByText('אין שורות להצגה')).toBeInTheDocument()
  })
})

describe('TableView: approve all clean rows', () => {
  it('names how many rows it would approve', () => {
    renderTable()
    expect(screen.getByRole('button', { name: 'אשרי את כל השורות התקינות (1)' })).toBeEnabled()
  })

  it('approves them through the API and reports how many', async () => {
    const api = renderTable()
    await userEvent.click(screen.getByRole('button', { name: /אשרי את כל השורות התקינות/ }))
    await waitFor(() => expect(api.called('POST', '/records/approve-clean')).toHaveLength(1))
    expect(await screen.findByRole('status')).toHaveTextContent('אושרו 1 שורות')
  })

  it('is disabled when no row is clean', () => {
    renderTable([flaggedRecord('b', 'רונן')])
    expect(screen.getByRole('button', { name: 'אשרי את כל השורות התקינות (0)' })).toBeDisabled()
  })
})
