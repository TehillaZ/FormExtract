import { describe, expect, it } from 'vitest'
import type { CommitmentRecord, Confidence, Field } from '../api/types'
import { displayValue, filterRecords, flaggedCount, formatDate, needsReview, nextToReview, FIELD_DEFS } from './fields'

const field = (value: string | null, confidence: Confidence = 'high', reasons: string[] = []): Field =>
  ({ value, raw_text: value, confidence, source: null, reasons })

function record(id: string, over: Partial<CommitmentRecord> = {}): CommitmentRecord {
  return {
    id, document_id: null, page_numbers: [1], page_ids: ['p-' + id], template: null, provider: null,
    first_name: field('דנה'), last_name: field('כהן'), id_number: field('011223344'),
    central_numbers: [field('939376')], received_date: field('2026-06-18'), sender: field('כללית'),
    commitment_numbers: [field('730578626')], status: 'pending', approved_at: null, corrections: [], duplicate_warnings: [], ...over,
  }
}

describe('flagging', () => {
  it('counts every field that is not high confidence, including list entries', () => {
    const r = record('a', { first_name: field('רונן', 'low'), central_numbers: [field('939376'), field('939377', 'medium')] })
    expect(flaggedCount(r)).toBe(2)
    expect(needsReview(r)).toBe(true)
    expect(needsReview(record('b'))).toBe(false)
  })

  it('treats a missing value as flagged', () => {
    expect(needsReview(record('a', { sender: field(null, 'low', ['לא נמצא']) }))).toBe(true)
  })
})

describe('formatting', () => {
  it('shows ISO dates the way the lab writes them and leaves anything else alone', () => {
    expect(formatDate('2026-06-18')).toBe('18/06/2026')
    expect(formatDate('18/06/2026')).toBe('18/06/2026')
  })

  it('joins list values and skips empty ones', () => {
    const def = FIELD_DEFS.find((d) => d.key === 'central_numbers')!
    expect(displayValue(def, [field('939376'), field(null, 'low'), field('939377')])).toBe('939376 · 939377')
    expect(displayValue(def, [field(null, 'low')])).toBe('')
  })
})

describe('nextToReview', () => {
  const clean = (id: string) => record(id)
  const dirty = (id: string) => record(id, { first_name: field('x', 'low') })

  it('finds the next pending form with something to review, wrapping around', () => {
    const rs = [dirty('a'), clean('b'), dirty('c'), clean('d')]
    expect(nextToReview(rs, 'a')?.id).toBe('c')
    expect(nextToReview(rs, 'c')?.id).toBe('a')
  })

  it('skips approved forms and returns nothing when none are left', () => {
    const rs = [dirty('a'), record('b', { status: 'approved', first_name: field('x', 'low') })]
    expect(nextToReview(rs, 'a')).toBeUndefined()
    expect(nextToReview([], null)).toBeUndefined()
  })
})

describe('filterRecords', () => {
  const rs = [record('a'), record('b', { first_name: field('רונן', 'low'), id_number: field('001122344') })]

  it('filters to forms needing review', () => {
    expect(filterRecords(rs, 'review', '').map((r) => r.id)).toEqual(['b'])
  })

  it('searches names, IDs and numbers', () => {
    expect(filterRecords(rs, 'all', 'רונן').map((r) => r.id)).toEqual(['b'])
    expect(filterRecords(rs, 'all', '001122344').map((r) => r.id)).toEqual(['b'])
    expect(filterRecords(rs, 'all', '730578626')).toHaveLength(2)
    expect(filterRecords(rs, 'all', 'zzz')).toHaveLength(0)
  })
})
