import { describe, expect, it } from 'vitest'
import { makeReport, result } from '../test/factories'
import { accuracy, deltaPoints, errors, fieldOrder, flaggedRate, percent, reportTitle, splitSize, totalSilentErrors } from './accuracy'

describe('field results', () => {
  it('computes accuracy, flag rate and errors from the counts', () => {
    const f = result(20, 7, 11, 4)
    expect(accuracy(f)).toBe(0.35)
    expect(flaggedRate(f)).toBe(0.55)
    expect(errors(f)).toBe(13)
  })

  it('is zero, not NaN, when no pages were scored', () => {
    const none = result(0, 0, 0, 0)
    expect(accuracy(none)).toBe(0)
    expect(flaggedRate(none)).toBe(0)
  })

  it('formats a ratio as a whole percent', () => {
    expect(percent(0.6667)).toBe('67%')
    expect(percent(1)).toBe('100%')
    expect(percent(0)).toBe('0%')
  })
})

describe('comparing two results', () => {
  it('gives the change in percentage points, up and down', () => {
    expect(deltaPoints(result(20, 10, 0, 0), result(20, 14, 0, 0))).toBe(20)
    expect(deltaPoints(result(20, 14, 0, 0), result(20, 10, 0, 0))).toBe(-20)
    expect(deltaPoints(result(20, 10, 0, 0), result(20, 10, 0, 0))).toBe(0)
  })

  it('compares rates, so reports on different numbers of pages are still comparable', () => {
    expect(deltaPoints(result(10, 5, 0, 0), result(40, 30, 0, 0))).toBe(25)
  })
})

describe('report totals and titles', () => {
  it('sums the errors that were not flagged over every field', () => {
    expect(totalSilentErrors(makeReport())).toBe(5)       // 4 on the ID and 1 on the commitment number
  })

  it('names a report by model and split, and says when orientation correction was off', () => {
    expect(reportTitle(makeReport())).toBe('model-a · עמודי פיתוח')
    expect(reportTitle(makeReport({ oriented: false, split: 'test' }))).toBe('model-a · סט בדיקה · בלי יישור')
  })

  it('falls back to the provider when a report has no model name', () => {
    expect(reportTitle(makeReport({ model: '' }))).toBe('gemini · עמודי פיתוח')
  })
})

describe('splitSize and fieldOrder', () => {
  const coverage = { pages: 48, dev_pages: 34, test_pages: 14 }

  it('says how many pages a split has', () => {
    expect([splitSize('dev', coverage), splitSize('test', coverage), splitSize('all', coverage)]).toEqual([34, 14, 48])
  })

  it('lists the known fields first, then any the reports add', () => {
    const extra = makeReport({ fields: { ...makeReport().fields, first_name: result(20, 1, 1, 0) } })
    expect(fieldOrder([extra]).slice(-1)).toEqual(['first_name'])
    expect(fieldOrder([extra])[0]).toBe('id_number')
  })
})
