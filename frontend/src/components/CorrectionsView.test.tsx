import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { CorrectionGroup } from '../api/types'
import { installFakeApi } from '../test/fakeApi'
import { renderWithClient } from '../test/render'
import { CorrectionsView } from './CorrectionsView'

const group = (over: Partial<CorrectionGroup> = {}): CorrectionGroup => ({
  field: 'central_numbers', sender: 'מכבי', template: 'maccabi_lab', count: 3, unflagged: 2,
  sources: { handwritten: 2, sticker: 1 }, examples: [{ old: '939376', new: '939999' }, { old: null, new: '939111' }],
  last_at: '2026-10-20T10:00:00Z', ...over,
})

async function open(groups: CorrectionGroup[]) {
  installFakeApi().corrections = groups
  renderWithClient(<CorrectionsView />)
  await screen.findByRole('heading', { name: 'טעויות חוזרות' })
}

describe('CorrectionsView', () => {
  it('invites the first correction when there are none', async () => {
    await open([])
    expect(screen.getByText('עדיין לא תוקן שום ערך.')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('shows each repeated mistake with its sender, counts, how it appeared and examples', async () => {
    await open([group()])
    const row = screen.getByRole('rowheader', { name: 'מספר מרכזי' }).closest('tr') as HTMLElement
    expect(row).toHaveTextContent('מכבי')
    expect(row.querySelector('[data-cell="count"]')).toHaveTextContent('3')
    expect(row.querySelector('[data-cell="unflagged"]')).toHaveTextContent('2')
    expect(row).toHaveTextContent('כתב יד 2 · מדבקה 1')
    expect(row).toHaveTextContent('939376 → 939999')
    expect(row).toHaveTextContent('ריק → 939111')
  })

  it('totals the corrections and the ones that were shown as certain', async () => {
    await open([group(), group({ field: 'sender', sender: null, count: 1, unflagged: 0 })])
    expect(screen.getByRole('note')).toHaveTextContent('4 תיקונים ב-2 קבוצות')
    expect(screen.getByRole('note')).toHaveTextContent('(2)')
    expect(screen.getByText('לא ידוע')).toBeInTheDocument()
  })
})
