import { describe, expect, it } from 'vitest'
import { emptyFilters, exportUrl, hasFilters, recordQuery } from './recordQuery'

describe('recordQuery', () => {
  it('is empty when nothing is filtered', () => {
    expect(recordQuery(emptyFilters)).toBe('')
  })

  it('includes only the filters that are set', () => {
    expect(recordQuery({ ...emptyFilters, status: 'approved' })).toBe('status=approved')
    expect(recordQuery({ ...emptyFilters, from: '2026-06-01', to: '2026-06-30' })).toBe('from=2026-06-01&to=2026-06-30')
  })

  it('trims the search and ignores a blank one', () => {
    expect(recordQuery({ ...emptyFilters, q: '  פלג ' })).toBe(`q=${encodeURIComponent('פלג')}`)
    expect(recordQuery({ ...emptyFilters, q: '   ' })).toBe('')
  })

  it('encodes Hebrew and special characters safely', () => {
    const query = recordQuery({ ...emptyFilters, sender: 'מכבי & בניו', q: 'a=b&c' })
    const parsed = new URLSearchParams(query)
    expect(parsed.get('sender')).toBe('מכבי & בניו')
    expect(parsed.get('q')).toBe('a=b&c')
  })

  it('adds paging or the export format after the filters', () => {
    expect(recordQuery({ ...emptyFilters, status: 'pending' }, { limit: 25, offset: 50 })).toBe('status=pending&limit=25&offset=50')
  })
})

describe('hasFilters', () => {
  it('is true as soon as any filter has a value', () => {
    expect(hasFilters(emptyFilters)).toBe(false)
    expect(hasFilters({ ...emptyFilters, sender: 'כללית' })).toBe(true)
    expect(hasFilters({ ...emptyFilters, q: 'x' })).toBe(true)
  })
})

describe('exportUrl', () => {
  it('points at the API with the same filters and the chosen format', () => {
    expect(exportUrl(emptyFilters, 'csv')).toBe('/api/export?format=csv')
    expect(exportUrl({ ...emptyFilters, status: 'approved', sender: 'כללית' }, 'xlsx'))
      .toBe(`/api/export?status=approved&sender=${encodeURIComponent('כללית')}&format=xlsx`)
  })

  it('never carries paging: the export is every matching record', () => {
    expect(exportUrl({ ...emptyFilters, q: 'דנה' }, 'csv')).not.toMatch(/limit|offset/)
  })
})
