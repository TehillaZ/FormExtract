import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { field, flaggedRecord, makeRecord } from '../test/factories'
import { ExpandedViewer } from './ExpandedViewer'

function setup(record = flaggedRecord('b', 'רונן', 'לוי')) {
  const handlers = { onPrev: vi.fn(), onNext: vi.fn(), onClose: vi.fn() }
  render(<ExpandedViewer record={record} index={4} total={40} {...handlers} />)
  return handlers
}

describe('ExpandedViewer', () => {
  it('names the form and its place in the stack', () => {
    setup()
    expect(screen.getByRole('dialog', { name: 'תצוגה מוגדלת של הטופס' })).toBeInTheDocument()
    expect(screen.getByText('רונן לוי')).toBeInTheDocument()
    expect(screen.getByText('טופס 5 מתוך 40')).toBeInTheDocument()
  })

  it('keyboard: Escape closes, and the arrow keys step through the forms', async () => {
    const h = setup()
    await userEvent.keyboard('{Escape}')
    expect(h.onClose).toHaveBeenCalledTimes(1)
    await userEvent.keyboard('{ArrowLeft}')    // next is to the left in a right-to-left layout
    expect(h.onNext).toHaveBeenCalledTimes(1)
    await userEvent.keyboard('{ArrowRight}')
    expect(h.onPrev).toHaveBeenCalledTimes(1)
  })

  it('has buttons for closing and stepping too', async () => {
    const h = setup()
    await userEvent.click(screen.getByRole('button', { name: 'הטופס הבא' }))
    await userEvent.click(screen.getByRole('button', { name: 'הטופס הקודם' }))
    await userEvent.click(screen.getByRole('button', { name: 'סגירה' }))
    expect([h.onNext, h.onPrev, h.onClose].map((f) => f.mock.calls.length)).toEqual([1, 1, 1])
  })

  it('lists the extracted values to compare against the image, flagged ones marked', () => {
    setup(flaggedRecord('b', 'רונן', 'לוי', { sender: field(null, 'low', ['לא נמצא']) }))
    const chip = (text: string) => screen.getByText(text).closest('[data-flagged]')
    expect(chip('רונן')).toHaveAttribute('data-flagged', 'true')
    expect(chip('939376')).toHaveAttribute('data-flagged', 'false')
    expect(screen.getByText('— לא נמצא').closest('[data-flagged]')).toHaveAttribute('data-flagged', 'true')
  })

  it('formats the date the way the lab writes it', () => {
    setup(makeRecord('a'))
    expect(screen.getByText('18/06/2026')).toBeInTheDocument()
  })

  it('the lens button is off after rotating, because the lens only works on an upright image', async () => {
    setup()
    const lens = screen.getByRole('button', { name: 'זכוכית מגדלת' })
    await userEvent.click(lens)
    expect(lens).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: 'סיבוב' }))
    expect(lens).toBeDisabled()
  })

  it('stops listening to the keyboard once it is closed (unmounted)', async () => {
    const onClose = vi.fn()
    const { unmount } = render(<ExpandedViewer record={makeRecord('a')} index={0} total={1} onPrev={() => {}} onNext={() => {}} onClose={onClose} />)
    unmount()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })
})
