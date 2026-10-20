import type { EvaluationReport, FieldResult } from '../api/types'

export const FIELD_LABELS: Record<string, string> = {
  id_number: 'ת"ז',
  central_numbers: 'מספר מרכזי',
  received_date: 'תאריך קבלה',
  sender: 'גורם שולח',
  commitment_numbers: 'מספר התחייבות',
}

/** The fields in the order the screen shows them, then any the report has that we do not know. */
export function fieldOrder(reports: EvaluationReport[]): string[] {
  const known = Object.keys(FIELD_LABELS)
  const extra = new Set(reports.flatMap((r) => Object.keys(r.fields)).filter((f) => !known.includes(f)))
  return [...known, ...extra]
}

export const accuracy = (f: FieldResult) => (f.pages ? f.correct / f.pages : 0)
export const flaggedRate = (f: FieldResult) => (f.pages ? f.flagged / f.pages : 0)
export const errors = (f: FieldResult) => f.pages - f.correct

export const percent = (ratio: number) => `${Math.round(ratio * 100)}%`

/** Change in accuracy from `before` to `after`, in percentage points, rounded. */
export const deltaPoints = (before: FieldResult, after: FieldResult) => Math.round((accuracy(after) - accuracy(before)) * 100)

/** Errors that were not flagged, summed over all fields: the number that matters most. */
export const totalSilentErrors = (r: EvaluationReport) => Object.values(r.fields).reduce((n, f) => n + f.silent_errors, 0)

export const SPLIT_LABEL = { dev: 'עמודי פיתוח', test: 'סט בדיקה', all: 'כל העמודים' } as const

/** How many pages a split has, given what the ground truth contains. */
export function splitSize(split: EvaluationReport['split'], coverage: { pages: number; dev_pages: number; test_pages: number }) {
  return split === 'dev' ? coverage.dev_pages : split === 'test' ? coverage.test_pages : coverage.pages
}

/** A short name that tells two reports apart: model, split, and whether orientation correction was on. */
export function reportTitle(r: EvaluationReport): string {
  return `${r.model || r.provider} · ${SPLIT_LABEL[r.split]}${r.oriented ? '' : ' · בלי יישור'}`
}
