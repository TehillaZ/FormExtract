import { useState } from 'react'
import type { ReactNode } from 'react'
import { useRecordsPage, useSenders } from '../api/hooks'
import type { CommitmentRecord } from '../api/types'
import { FIELD_DEFS, displayValue, fieldsOf, flaggedCount, formatDate, recordTitle } from '../lib/fields'
import { type ExportFormat, type RecordFilters, emptyFilters, exportUrl, hasFilters } from '../lib/recordQuery'
import { useDebounced } from '../lib/useDebounced'
import { CountPill } from './ui'

const PAGE_SIZE = 25
const COLUMNS = 'grid-cols-[1.3fr_1fr_1fr_1fr_1.4fr_1.3fr_0.9fr]'
const SEARCH_DELAY_MS = 300

const control = 'rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink'

function Labelled({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-semibold text-sub">
      {label}
      {children}
    </label>
  )
}

function ExportLink({ filters, format, disabled, children }: {
  filters: RecordFilters; format: ExportFormat; disabled: boolean; children: ReactNode
}) {
  const style = 'rounded-[10px] border px-4 py-2 text-sm font-semibold no-underline'
  return disabled
    ? <span aria-disabled="true" className={`${style} cursor-not-allowed border-line bg-muted text-faint`}>{children}</span>
    : <a href={exportUrl(filters, format)} download className={`${style} border-accent-line bg-accent-soft text-accent`}>{children}</a>
}

function RecordRow({ rec, onOpen }: { rec: CommitmentRecord; onOpen: (id: string) => void }) {
  const text = (key: string) => {
    const def = FIELD_DEFS.find((d) => d.key === key)!
    return displayValue(def, fieldsOf(rec, def)) || '—'
  }
  const approved = rec.status === 'approved'
  return (
    <button type="button" onClick={() => onOpen(rec.id)}
      className={`grid w-full ${COLUMNS} items-center gap-3 border-0 border-b border-[#edeff2] bg-transparent px-5 py-3 text-start text-[15px] hover:bg-page`}>
      <span className="truncate font-semibold">{recordTitle(rec)}</span>
      <span className="truncate">{text('id_number')}</span>
      <span className="truncate">{text('central_numbers')}</span>
      <span>{rec.received_date.value ? formatDate(rec.received_date.value) : '—'}</span>
      <span className="truncate">{text('sender')}</span>
      <span className="truncate">{text('commitment_numbers')}</span>
      <span className="flex items-center gap-2 text-[13px] font-semibold">
        {approved
          ? <span className="text-ok-ink" title={rec.approved_at ? `אושר ב-${formatDate(rec.approved_at.slice(0, 10))}` : undefined}>מאושר</span>
          : <><span className="text-sub">ממתין</span>{flaggedCount(rec) > 0 && <CountPill count={flaggedCount(rec)} />}</>}
      </span>
    </button>
  )
}

/** All records from every upload: search, filter by status, sender and received date, page through, export (PLAN 4.4). */
export function RecordsView({ onOpen }: { onOpen: (id: string) => void }) {
  const [filters, setFilters] = useState<RecordFilters>(emptyFilters)
  const [page, setPage] = useState(0)
  const senders = useSenders()
  // typing waits for a pause; the other filters apply at once
  const debouncedQ = useDebounced(filters.q, SEARCH_DELAY_MS)
  const applied: RecordFilters = { ...filters, q: debouncedQ }
  const { data, isLoading, isError, isFetching } = useRecordsPage(applied, page, PAGE_SIZE)

  const change = (patch: Partial<RecordFilters>) => {
    setFilters((f) => ({ ...f, ...patch }))
    setPage(0)
  }
  const total = data?.total ?? 0
  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1)
  if (data && page > lastPage) setPage(lastPage)   // the list shrank under us (a record was edited): step back

  const items = data?.items ?? []
  const first = total ? page * PAGE_SIZE + 1 : 0
  const last = page * PAGE_SIZE + items.length

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-10 pt-6 pb-8">
      <div className="flex flex-wrap items-end gap-3 rounded-[14px] border border-edge bg-surface p-4">
        <Labelled label="חיפוש">
          <input type="search" value={filters.q} onChange={(e) => change({ q: e.target.value })} aria-label="חיפוש רשומות"
            placeholder='שם, ת"ז או מספר' className={`${control} w-60`} />
        </Labelled>
        <Labelled label="סטטוס">
          <select value={filters.status} onChange={(e) => change({ status: e.target.value as RecordFilters['status'] })}
            aria-label="סטטוס" className={control}>
            <option value="">הכול</option>
            <option value="pending">ממתין</option>
            <option value="approved">מאושר</option>
          </select>
        </Labelled>
        <Labelled label="גורם שולח">
          <select value={filters.sender} onChange={(e) => change({ sender: e.target.value })} aria-label="גורם שולח" className={`${control} w-52`}>
            <option value="">הכול</option>
            {senders.data?.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Labelled>
        <Labelled label="תאריך קבלה מ-">
          <input type="date" value={filters.from} max={filters.to || undefined} onChange={(e) => change({ from: e.target.value })}
            aria-label="תאריך קבלה מ-" className={control} />
        </Labelled>
        <Labelled label="עד">
          <input type="date" value={filters.to} min={filters.from || undefined} onChange={(e) => change({ to: e.target.value })}
            aria-label="תאריך קבלה עד" className={control} />
        </Labelled>
        {hasFilters(filters) && (
          <button type="button" onClick={() => change(emptyFilters)}
            className="rounded-lg border border-line bg-surface px-3 py-2 text-sm text-sub">נקי סינון</button>
        )}
        <div className="ms-auto flex items-center gap-2">
          <ExportLink filters={applied} format="xlsx" disabled={!total}>ייצוא ל-Excel</ExportLink>
          <ExportLink filters={applied} format="csv" disabled={!total}>ייצוא CSV</ExportLink>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-[13px] text-sub">
        <span role="status">
          {isLoading ? 'טוען…' : total ? `מציג ${first}–${last} מתוך ${total} רשומות` : 'אין רשומות מתאימות'}
        </span>
        <span>הייצוא כולל את כל הרשומות המסוננות, לא רק את העמוד הנוכחי. אפסים מובילים ב-ת"ז נשמרים רק בקובץ Excel.</span>
      </div>

      <div className={`overflow-hidden rounded-[14px] border border-edge bg-surface ${isFetching && !isLoading ? 'opacity-70' : ''}`}>
        <div className={`grid ${COLUMNS} gap-3 border-b border-edge bg-page px-5 py-3.5 text-[13px] font-semibold text-sub`}>
          <div>שם</div><div>ת"ז</div><div>מספר מרכזי</div><div>תאריך קבלה</div><div>גורם שולח</div><div>מספר התחייבות</div><div>סטטוס</div>
        </div>
        {isError && <div role="alert" className="px-5 py-10 text-center text-warn-ink">לא ניתן לטעון את הרשומות. ודאי שהשרת פועל.</div>}
        {items.map((rec) => <RecordRow key={rec.id} rec={rec} onOpen={onOpen} />)}
        {!isError && !isLoading && !items.length && <div className="px-5 py-10 text-center text-faint">אין רשומות מתאימות</div>}
      </div>

      {total > PAGE_SIZE && (
        <nav aria-label="דפי תוצאות" className="flex items-center justify-center gap-3">
          <button type="button" onClick={() => setPage((p) => p - 1)} disabled={page === 0}
            className="rounded-lg border border-line bg-surface px-4 py-2 text-sm">הקודם</button>
          <span className="text-sm text-sub">עמוד {page + 1} מתוך {lastPage + 1}</span>
          <button type="button" onClick={() => setPage((p) => p + 1)} disabled={page >= lastPage}
            className="rounded-lg border border-line bg-surface px-4 py-2 text-sm">הבא</button>
        </nav>
      )}
    </div>
  )
}
