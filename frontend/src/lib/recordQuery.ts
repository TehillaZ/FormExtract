/** The filters of the records screen, and how they become a query string. The list and the export links both
 *  use this, so what you see and what you download are always the same set of records. */
export interface RecordFilters {
  q: string
  status: '' | 'pending' | 'approved'
  sender: string
  from: string   // yyyy-mm-dd, received date
  to: string
}

export const emptyFilters: RecordFilters = { q: '', status: '', sender: '', from: '', to: '' }

export const hasFilters = (f: RecordFilters) => Object.values(f).some((v) => v !== '')

/** Only the filters that are set become parameters. `extra` adds paging or the export format. */
export function recordQuery(filters: RecordFilters, extra: Record<string, string | number> = {}): string {
  const params = new URLSearchParams()
  const q = filters.q.trim()
  if (q) params.set('q', q)
  if (filters.status) params.set('status', filters.status)
  if (filters.sender) params.set('sender', filters.sender)
  if (filters.from) params.set('from', filters.from)
  if (filters.to) params.set('to', filters.to)
  for (const [key, value] of Object.entries(extra)) params.set(key, String(value))
  return params.toString()
}

export type ExportFormat = 'xlsx' | 'csv'

/** Where the browser downloads the filtered records from. */
export const exportUrl = (filters: RecordFilters, format: ExportFormat) => `/api/export?${recordQuery(filters, { format })}`
