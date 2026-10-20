import { useMemo, useState } from 'react'
import type { CommitmentRecord } from '../api/types'
import { type ListFilter, filterRecords, flaggedCount, needsReview, recordTitle } from '../lib/fields'
import { CountPill, Icon, IconButton } from './ui'

const LIST_WIDTH = 236

export function FormList({ records, selectedId, onSelect, open, onToggle, filter, onFilter }: {
  records: CommitmentRecord[]
  selectedId: string | null
  onSelect: (id: string) => void
  open: boolean
  onToggle: () => void
  filter: ListFilter
  onFilter: (f: ListFilter) => void
}) {
  const [query, setQuery] = useState('')
  const reviewCount = useMemo(() => records.filter(needsReview).length, [records])
  const shown = useMemo(() => filterRecords(records, filter, query), [records, filter, query])
  const numbers = useMemo(() => new Map(records.map((r, i) => [r.id, i + 1])), [records])

  return (
    <aside aria-label="רשימת הטפסים" aria-hidden={!open} inert={!open}
      className="shrink-0 overflow-hidden border-e border-edge bg-surface transition-[width] duration-200"
      style={{ width: open ? LIST_WIDTH : 0 }}>
      <div className="flex h-full flex-col gap-2 px-2.5 pt-3" style={{ width: LIST_WIDTH }}>
        <div className="flex items-center gap-1.5">
          <label className="flex min-w-0 flex-1 items-center gap-2 rounded-[9px] border border-line bg-page px-2.5 py-[6px]">
            <Icon name="search" size={16} />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="חיפוש שם, ת״ז או מספר"
              aria-label="חיפוש טפסים" className="min-w-0 flex-1 border-0 bg-transparent text-[13px] outline-none" />
          </label>
          <IconButton icon="chevron-start" label="סגירת הרשימה" size={32} onClick={onToggle} />
        </div>

        <div className="flex rounded-[9px] bg-muted p-[3px]" role="tablist">
          {([['all', `הכול ${records.length}`], ['review', `לבדיקה ${reviewCount}`]] as const).map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={filter === id} onClick={() => onFilter(id)}
              className={`flex-1 rounded-[7px] border-0 py-[5px] text-[13px] ${filter === id ? 'bg-surface font-semibold shadow-sm' : 'bg-transparent text-sub'}`}>{label}</button>
          ))}
        </div>

        <ul className="m-0 flex min-h-0 flex-1 list-none flex-col gap-0.5 overflow-y-auto p-0">
          {shown.map((r) => {
            const selected = r.id === selectedId
            return (
              <li key={r.id}>
                <button type="button" onClick={() => onSelect(r.id)} aria-current={selected}
                  className={`flex w-full items-center gap-1.5 rounded-[9px] border px-2 py-1.5 text-start ${selected ? 'border-accent-line bg-accent-soft' : 'border-transparent bg-transparent hover:bg-page'}`}>
                  <span className="w-5 shrink-0 text-xs text-faint">{numbers.get(r.id)}</span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-sm font-semibold">{recordTitle(r)}</span>
                    <span className="truncate text-xs text-faint">{r.sender.value ?? r.sender.raw_text ?? '—'}</span>
                  </span>
                  {r.status === 'approved' ? <span className="text-xs font-bold text-ok-ink">מאושר</span> : <CountPill count={flaggedCount(r)} />}
                </button>
              </li>
            )
          })}
          {!shown.length && <li className="px-2 py-6 text-center text-[13px] text-faint">אין טפסים להצגה</li>}
        </ul>

        <div className="border-t border-edge py-2 text-center text-xs text-faint">מציג {shown.length} מתוך {records.length}</div>
      </div>
    </aside>
  )
}
