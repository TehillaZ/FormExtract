import type { CommitmentRecord, Field } from '../api/types'

export type FieldKey =
  | 'first_name' | 'last_name' | 'id_number' | 'central_numbers' | 'received_date' | 'sender' | 'commitment_numbers'

export interface FieldDef {
  key: FieldKey
  label: string
  short: string       // for tight spaces
  list: boolean       // central / commitment numbers hold several values
}

export const FIELD_DEFS: FieldDef[] = [
  { key: 'first_name', label: 'שם פרטי', short: 'שם פרטי', list: false },
  { key: 'last_name', label: 'שם משפחה', short: 'שם משפחה', list: false },
  { key: 'id_number', label: 'ת"ז', short: 'ת"ז', list: false },
  { key: 'central_numbers', label: 'מספר מרכזי', short: 'מרכזי', list: true },
  { key: 'received_date', label: 'תאריך קבלה', short: 'תאריך', list: false },
  { key: 'sender', label: 'גורם שולח', short: 'שולח', list: false },
  { key: 'commitment_numbers', label: 'מספר התחייבות', short: 'התחייבות', list: true },
]

/** The fields of a def, always as a list (scalar fields have one entry). */
export function fieldsOf(rec: CommitmentRecord, def: FieldDef): Field[] {
  const f = rec[def.key]
  return Array.isArray(f) ? f : [f]
}

export const isFlagged = (f: Field) => f.confidence !== 'high'

/** How loudly a field is flagged: 'low' (doubtful: handwriting, a failed check, a missing value) is orange, 'medium'
 *  (read from print but nothing could verify it) is a calmer yellow. Both still need a person; 'high' needs nothing. */
export type FlagLevel = 'low' | 'medium' | 'ok'
export function flagLevel(fields: Field[]): FlagLevel {
  if (fields.some((f) => f.confidence === 'low')) return 'low'
  return fields.some(isFlagged) ? 'medium' : 'ok'
}

export function flaggedCount(rec: CommitmentRecord): number {
  return FIELD_DEFS.flatMap((d) => fieldsOf(rec, d)).filter(isFlagged).length
}

export const needsReview = (rec: CommitmentRecord) => flaggedCount(rec) > 0

/** ISO 2026-06-18 -> 18/06/2026, as the lab writes dates. Anything else is shown as is. */
export function formatDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso
}

/** The text shown for a field: its value, or the raw text read when the value was rejected. */
export function displayValue(def: FieldDef, fields: Field[]): string {
  const values = fields.map((f) => f.value).filter((v): v is string => !!v)
  if (!values.length) return ''
  return def.key === 'received_date' ? formatDate(values[0]) : values.join(' · ')
}

/** The values to put in an edit box: dates in the lab's format, lists as separate entries. */
export function editValues(def: FieldDef, fields: Field[]): string[] {
  const values = fields.map((f) => f.value).filter((v): v is string => !!v)
  return def.key === 'received_date' ? values.map(formatDate) : values
}

export function reasonText(fields: Field[]): string {
  const reasons = fields.flatMap((f) => f.reasons)
  return [...new Set(reasons)].join(' · ')
}

export function recordTitle(rec: CommitmentRecord): string {
  const name = [rec.first_name.value, rec.last_name.value].filter(Boolean).join(' ')
  return name || 'ללא שם'
}

/** The next pending record (after `currentId`, wrapping around) that still has something to review. */
export function nextToReview(records: CommitmentRecord[], currentId: string | null): CommitmentRecord | undefined {
  if (!records.length) return undefined
  const start = Math.max(0, records.findIndex((r) => r.id === currentId))
  for (let i = 1; i <= records.length; i++) {
    const r = records[(start + i) % records.length]
    if (r.id !== currentId && r.status === 'pending' && needsReview(r)) return r
  }
  return undefined
}

export type ListFilter = 'all' | 'review'

/** Everything searchable about a record, as one lowercase string. */
function haystack(rec: CommitmentRecord): string {
  return FIELD_DEFS.map((d) => displayValue(d, fieldsOf(rec, d))).join(' ').toLowerCase()
}

/** Records matching the list's filter and search text, in list order. */
export function filterRecords(records: CommitmentRecord[], filter: ListFilter, query: string): CommitmentRecord[] {
  const q = query.trim().toLowerCase()
  return records.filter((r) => (filter === 'all' || needsReview(r)) && (!q || haystack(r).includes(q)))
}
