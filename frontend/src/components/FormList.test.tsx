import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { CommitmentRecord } from '../api/types'
import type { ListFilter } from '../lib/fields'
import { field, flaggedRecord, makeRecord } from '../test/factories'
import { FormList } from './FormList'

const records = (): CommitmentRecord[] => [
  makeRecord('a'),                                                                     // דנה כהן, clean
  flaggedRecord('b', 'רונן', 'לוי'),                                                   // 1 flagged field
  flaggedRecord('c', 'משה', 'ישראלי', { sender: field(null, 'low', ['לא נמצא']) }),    // 2 flagged fields, no sender
  makeRecord('d', { status: 'approved', first_name: field('אבי'), last_name: field('גל') }),
]

/** The list is controlled by its parent; this stands in for it. */
function Harness({ onSelect = () => {}, initialOpen = true, onToggle = () => {} }: {
  onSelect?: (id: string) => void; initialOpen?: boolean; onToggle?: () => void
}) {
  const [open, setOpen] = useState(initialOpen)
  const [filter, setFilter] = useState<ListFilter>('all')
  return (
    <FormList records={records()} selectedId="a" onSelect={onSelect} open={open}
      onToggle={() => { onToggle(); setOpen((o) => !o) }} filter={filter} onFilter={setFilter} />
  )
}

const item = (name: string) => screen.getByRole('button', { name: new RegExp(name) })

describe('FormList', () => {
  it('lists every form with its number of flagged fields, or a check when it is clean', () => {
    render(<Harness />)
    expect(within(item('דנה כהן')).getByText('✓')).toBeInTheDocument()
    expect(within(item('רונן לוי')).getByText('1')).toBeInTheDocument()
    expect(within(item('משה ישראלי')).getByText('2')).toBeInTheDocument()
    expect(within(item('אבי גל')).getByText('מאושר')).toBeInTheDocument()
  })

  it('shows the sender, or a dash when there is none', () => {
    render(<Harness />)
    expect(within(item('דנה כהן')).getByText('כללית')).toBeInTheDocument()
    expect(within(item('משה ישראלי')).getByText('—')).toBeInTheDocument()
  })

  it('marks the selected form', () => {
    render(<Harness />)
    expect(item('דנה כהן')).toHaveAttribute('aria-current', 'true')
    expect(item('רונן לוי')).toHaveAttribute('aria-current', 'false')
  })

  it('selects a form when it is clicked', async () => {
    const onSelect = vi.fn()
    render(<Harness onSelect={onSelect} />)
    await userEvent.click(item('רונן לוי'))
    expect(onSelect).toHaveBeenCalledWith('b')
  })

  it('filters to the forms that need review', async () => {
    render(<Harness />)
    expect(screen.getByRole('tab', { name: 'הכול 4' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'לבדיקה 2' }))
    expect(screen.queryByRole('button', { name: /דנה כהן/ })).not.toBeInTheDocument()
    expect(item('רונן לוי')).toBeInTheDocument()
    expect(screen.getByText('מציג 2 מתוך 4')).toBeInTheDocument()
  })

  it('searches names, IDs and numbers', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const box = screen.getByLabelText('חיפוש טפסים')
    await user.type(box, 'משה')
    expect(screen.getAllByRole('listitem')).toHaveLength(1)

    await user.clear(box)
    await user.type(box, '730578626')   // every record has this commitment number
    expect(screen.getAllByRole('listitem')).toHaveLength(4)
  })

  it('says so when nothing matches', async () => {
    render(<Harness />)
    await userEvent.type(screen.getByLabelText('חיפוש טפסים'), 'zzzz')
    expect(screen.getByText('אין טפסים להצגה')).toBeInTheDocument()
  })
})

describe('FormList: closing', () => {
  it('asks its parent to close when the close button is pressed', async () => {
    const onToggle = vi.fn()
    render(<Harness onToggle={onToggle} />)
    await userEvent.click(screen.getByRole('button', { name: 'סגירת הרשימה' }))
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('when closed it has no width and its contents are hidden from the keyboard and screen readers', () => {
    render(<Harness initialOpen={false} />)
    const list = screen.getByLabelText('רשימת הטפסים', { selector: 'aside' })
    expect(list).toHaveStyle({ width: '0px' })
    expect(list).toHaveAttribute('aria-hidden', 'true')
    expect(list).toHaveAttribute('inert')
  })

  it('when open it is 236px wide and available', () => {
    render(<Harness />)
    const list = screen.getByLabelText('רשימת הטפסים', { selector: 'aside' })
    expect(list).toHaveStyle({ width: '236px' })
    expect(list).not.toHaveAttribute('inert')
  })
})
