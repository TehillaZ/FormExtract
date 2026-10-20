import type { CommitmentRecord, Confidence, DocumentStatus, Field } from '../api/types'

export const field = (value: string | null, confidence: Confidence = 'high', reasons: string[] = [], raw: string | null = value): Field =>
  ({ value, raw_text: raw, confidence, source: null, reasons })

/** A record with every field verified. Override a field to make it flagged. */
export function makeRecord(id: string, over: Partial<CommitmentRecord> = {}): CommitmentRecord {
  return {
    id, document_id: null, page_numbers: [1], page_ids: [`page-${id}`], template: null, provider: 'gemini',
    first_name: field('דנה'), last_name: field('כהן'), id_number: field('011223344'),
    central_numbers: [field('939376')], received_date: field('2026-06-18'), sender: field('כללית'),
    commitment_numbers: [field('730578626')], status: 'pending', corrections: [], duplicate_warnings: [], ...over,
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
