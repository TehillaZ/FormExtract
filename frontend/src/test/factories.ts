import type { CommitmentRecord, Confidence, DocumentStatus, EvaluationReport, Field, FieldResult } from '../api/types'

export const field = (value: string | null, confidence: Confidence = 'high', reasons: string[] = [], raw: string | null = value): Field =>
  ({ value, raw_text: raw, confidence, source: null, reasons })

/** A record with every field verified. Override a field to make it flagged. */
export function makeRecord(id: string, over: Partial<CommitmentRecord> = {}): CommitmentRecord {
  return {
    id, document_id: null, page_numbers: [1], page_ids: [`page-${id}`], template: null, provider: 'gemini',
    first_name: field('דנה'), last_name: field('כהן'), id_number: field('011223344'),
    central_numbers: [field('939376')], received_date: field('2026-06-18'), sender: field('כללית'),
    commitment_numbers: [field('730578626')], status: 'pending', approved_at: null, corrections: [], duplicate_warnings: [], ...over,
  }
}

/** A record named `first last` whose first name is flagged (handwritten). */
export function flaggedRecord(id: string, first: string, last = 'לוי', over: Partial<CommitmentRecord> = {}): CommitmentRecord {
  return makeRecord(id, { first_name: field(first, 'low', ['כתב יד']), last_name: field(last), ...over })
}

export function makeDocument(id: string, pages: DocumentStatus['pages'], over: Partial<DocumentStatus> = {}): DocumentStatus {
  return { id, filename: `${id}.png`, duplicate: false, done: pages.every((p) => p.status === 'ready' || p.status === 'error'), pages, ...over }
}

export const pageStatus = (id: string, n: number, status: DocumentStatus['pages'][number]['status'], record_id: string | null = null) =>
  ({ id, page_number: n, status, error: status === 'error' ? 'RateLimited' : null, record_id })

/** A field result: `pages` pages scored, `correct` right, `flagged` flagged, `silent` wrong and unflagged. */
export const result = (pages: number, correct: number, flagged: number, silent: number): FieldResult =>
  ({ pages, correct, flagged, silent_errors: silent })

export function makeReport(over: Partial<EvaluationReport> = {}): EvaluationReport {
  return {
    tag: 'gemini-model-a-abc123', provider: 'gemini', model: 'model-a', prompt_id: 'abc123', oriented: true,
    checksum_mode: 'strict', split: 'dev', created_at: '2026-10-20T22:00:00Z', pages_scored: 20, pages_failed: 0,
    pages: Array.from({ length: 20 }, (_, i) => `p${i}`),
    fields: {
      id_number: result(20, 7, 11, 4), central_numbers: result(20, 14, 8, 0), received_date: result(20, 12, 19, 0),
      sender: result(20, 14, 7, 0), commitment_numbers: result(20, 15, 17, 1),
    },
    ...over,
  }
}
