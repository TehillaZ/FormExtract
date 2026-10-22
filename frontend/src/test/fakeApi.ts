import { vi } from 'vitest'
import type { CommitmentRecord, CorrectionGroup, DocumentStatus, EvaluationOverview, Field } from '../api/types'
import { FIELD_DEFS, displayValue, fieldsOf } from '../lib/fields'
import { field } from './factories'

export interface Call {
  method: string
  path: string
  body: unknown
}

export interface FakeApi {
  records: CommitmentRecord[]
  documents: Record<string, DocumentStatus>
  uploadResult: DocumentStatus[]
  calls: Call[]
  patchError: string | null       // makes PATCH answer 422 with this message
  approveError: string | null     // makes approve answer 409 with this message
  uploadError: string | null      // makes the upload answer 400 with this message
  senders: string[]
  evaluation: EvaluationOverview
  corrections: CorrectionGroup[]
  called: (method: string, pathPart: string) => Call[]
}

const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } })

/** Everything searchable about a record, like the server's search over names, ID and numbers. */
const searchable = (r: CommitmentRecord) =>
  FIELD_DEFS.map((d) => displayValue(d, fieldsOf(r, d))).join(' ').toLowerCase()

/** The server's record filters and paging, with the total sent in X-Total-Count. */
function listRecords(records: CommitmentRecord[], search: URLSearchParams): Response {
  const q = (search.get('q') ?? '').trim().toLowerCase()
  const matching = records.filter((r) =>
    (!search.get('status') || r.status === search.get('status')) &&
    (!search.get('sender') || r.sender.value === search.get('sender')) &&
    (!search.get('from') || (r.received_date.value ?? '') >= search.get('from')!) &&
    (!search.get('to') || (r.received_date.value ?? '9999') <= search.get('to')!) &&
    (!q || searchable(r).includes(q)))
  const offset = Number(search.get('offset') ?? 0)
  const limit = Number(search.get('limit') ?? 200)
  return json(matching.slice(offset, offset + limit), 200, { 'X-Total-Count': String(matching.length) })
}

/** What the backend does to a field a person saves: a different value is a correction, the same value on a
 *  flagged field is a confirmation. Mirrors backend/app/db/repo.py closely enough for UI tests. */
function applySaved(rec: CommitmentRecord, changes: Record<string, string | string[]>): CommitmentRecord {
  const next = structuredClone(rec)
  for (const [key, sent] of Object.entries(changes)) {
    const def = FIELD_DEFS.find((d) => d.key === key)
    if (!def) continue
    const current = (next[def.key] as Field | Field[])
    const fields = Array.isArray(current) ? current : [current]
    const oldValues = fields.map((f) => f.value).filter((v): v is string => !!v)
    const newValues = (Array.isArray(sent) ? sent : [sent]).map((v) => v.trim()).filter(Boolean)
    const flagged = fields.some((f) => f.confidence !== 'high')
    const same = JSON.stringify(newValues.map(normalise(def.key))) === JSON.stringify(oldValues)
    if (same && !flagged) continue
    const reason = same ? 'אושר ידנית' : 'תוקן ידנית'
    const made = newValues.length
      ? newValues.map((v) => ({ ...field(normalise(def.key)(v), 'high', [reason]), source: 'manual' }))
      : [{ ...field(null, 'high', ['אושר ידנית: אין בטופס']), source: 'manual' }]
    ;(next as unknown as Record<string, unknown>)[def.key] = def.list ? made : made[0]
  }
  return next
}

const normalise = (key: string) => (v: string) => {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(v)
  return key === 'received_date' && m ? `${m[3]}-${m[2]}-${m[1]}` : v
}

/** Replaces `fetch` with an in-memory copy of the API. Returns a handle to inspect calls and steer behaviour. */
export function installFakeApi(initial: CommitmentRecord[] = []): FakeApi {
  const api: FakeApi = {
    records: structuredClone(initial), documents: {}, uploadResult: [], calls: [], patchError: null, approveError: null, uploadError: null,
    senders: ['כללית', 'מכבי', 'מאוחדת', 'לאומית'], evaluation: { reports: [], pages: 0, dev_pages: 0, test_pages: 0 }, corrections: [],
    called: (method, part) => api.calls.filter((c) => c.method === method && c.path.includes(part)),
  }
  const replace = (rec: CommitmentRecord) => { api.records = api.records.map((r) => (r.id === rec.id ? rec : r)) }

  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input).replace(/^\/api/, '')
    const method = init?.method ?? 'GET'
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) : init?.body
    api.calls.push({ method, path, body })

    if (method === 'GET' && path.startsWith('/records?')) return listRecords(api.records, new URL(path, 'http://x').searchParams)
    if (method === 'GET' && path === '/senders') return json(api.senders)
    if (method === 'GET' && path === '/evaluation') return json(api.evaluation)
    if (method === 'GET' && path === '/corrections/summary') return json(api.corrections)
    if (method === 'POST' && path === '/records/approve-clean') {
      const clean = api.records.filter((r) => r.status === 'pending' && r.id && !hasFlag(r))
      clean.forEach((r) => replace({ ...r, status: 'approved' }))
      return json({ approved: clean.map((r) => r.id), skipped_duplicates: [] })
    }
    const rec = /^\/records\/([^/?]+)(\/approve)?$/.exec(path)
    if (rec) {
      const found = api.records.find((r) => r.id === rec[1])
      if (!found) return json({ detail: 'הרשומה לא נמצאה' }, 404)
      if (method === 'PATCH') {
        if (api.patchError) return json({ detail: api.patchError }, 422)
        const updated = applySaved(found, body as Record<string, string | string[]>)
        replace(updated)
        return json(updated)
      }
      if (method === 'POST' && rec[2]) {
        if (api.approveError) return json({ detail: api.approveError }, 409)
        const approved = { ...found, status: 'approved' as const }
        replace(approved)
        return json(approved)
      }
    }
    if (method === 'POST' && path === '/documents') return api.uploadError ? json({ detail: api.uploadError }, 400) : json(api.uploadResult, 202)
    if (method === 'POST' && /^\/pages\/[^/]+\/reprocess$/.test(path)) return json({}, 202)
    const doc = /^\/documents\/([^/]+)$/.exec(path)
    if (doc && method === 'GET') return api.documents[doc[1]] ? json(api.documents[doc[1]]) : json({ detail: 'x' }, 404)
    return json({ detail: `unexpected ${method} ${path}` }, 500)
  }))
  return api
}

const hasFlag = (r: CommitmentRecord) =>
  FIELD_DEFS.some((d) => {
    const f = r[d.key] as Field | Field[]
    return (Array.isArray(f) ? f : [f]).some((x) => x.confidence !== 'high')
  })
