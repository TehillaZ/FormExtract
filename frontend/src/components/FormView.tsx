import { useEffect, useMemo, useState } from 'react'
import { ApiError } from '../api/client'
import { useApproveRecord } from '../api/hooks'
import type { CommitmentRecord } from '../api/types'
import { type ListFilter, filterRecords, nextToReview } from '../lib/fields'
import { ExpandedViewer } from './ExpandedViewer'
import { FieldsPanel } from './FieldsPanel'
import { FormList } from './FormList'
import { ImageCanvas, ViewToolbar } from './ImageViewer'
import { useImageView } from './useImageView'
import { Icon } from './ui'

const OPEN_KEY = 'formlist-open'

/** A boolean remembered in the browser. Falls back to `initial` when storage is unavailable (private mode). */
function useStoredFlag(key: string, initial: boolean) {
  const [value, setValue] = useState(() => {
    try {
      const stored = localStorage.getItem(key)
      return stored === null ? initial : stored === '1'
    } catch {
      return initial
    }
  })
  useEffect(() => {
    try { localStorage.setItem(key, value ? '1' : '0') } catch { /* not remembered */ }
  }, [key, value])
  return [value, setValue] as const
}

/** The review screen: a collapsible list of forms, the form image, and its fields. */
export function FormView({ records, selectedId, onSelect }: {
  records: CommitmentRecord[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const [listOpen, setListOpen] = useStoredFlag(OPEN_KEY, true)
  const [filter, setFilter] = useState<ListFilter>('all')
  const [expanded, setExpanded] = useState(false)
  const [percent, setPercent] = useState(100)
  const approve = useApproveRecord()

  const record = records.find((r) => r.id === selectedId) ?? records[0]
  const recordId = record?.id ?? ''
  const view = useImageView(recordId)
  const upNext = useMemo(() => nextToReview(records, recordId || null), [records, recordId])
  const visible = useMemo(() => filterRecords(records, filter, ''), [records, filter])
  const { reset: resetApprove } = approve

  useEffect(() => { resetApprove() }, [recordId, resetApprove])

  if (!record) {
    return <div className="m-auto text-sub">אין טפסים עדיין. אפשר להעלות קבצים בלשונית "העלאה".</div>
  }

  // prev/next walk the list as filtered; when the current form is filtered out they walk everything
  const walkable = visible.some((r) => r.id === record.id) ? visible : records
  const position = walkable.findIndex((r) => r.id === record.id)
  const step = (delta: number) => onSelect(walkable[(position + delta + walkable.length) % walkable.length].id)

  const approveError = approve.error instanceof ApiError ? approve.error.message : approve.error ? 'האישור נכשל' : null
  const doApprove = () => approve.mutate(record.id, {
    onSuccess: () => {
      const next = nextToReview(records, record.id)
      if (next) onSelect(next.id)
    },
  })

  return (
    <div className="flex min-h-0 flex-1">
      <FormList records={records} selectedId={record.id} onSelect={onSelect} open={listOpen}
        onToggle={() => setListOpen((o) => !o)} filter={filter} onFilter={setFilter} />

      <div className="relative flex min-w-0 flex-1 bg-stage">
        {!listOpen && (
          <button type="button" onClick={() => setListOpen(true)} aria-label="פתיחת רשימת הטפסים"
            className="absolute start-3.5 top-3.5 z-10 flex items-center gap-1.5 rounded-xl border border-edge bg-surface px-3 py-2 text-[13px] font-semibold shadow-sm">
            <Icon name="list" size={16} />טפסים ({records.length})
          </button>
        )}
        <ViewToolbar view={view} onExpand={() => setExpanded(true)} />
        <div className="absolute bottom-3 end-3.5 z-10 rounded-lg border border-edge bg-surface px-2.5 py-1 text-xs text-sub">
          {view.fit === 'height' ? 'התאמה לגובה' : view.fit === 'width' ? 'התאמה לרוחב' : 'גודל מקורי'} · {percent}%
        </div>
        <div className="min-h-0 flex-1 p-3">
          <ImageCanvas pageId={record.page_ids[0]} view={view} onPercent={setPercent} />
        </div>
      </div>

      <FieldsPanel record={record} onApprove={doApprove} approving={approve.isPending} approveError={approveError}
        onNextToReview={() => upNext && onSelect(upNext.id)} hasNextToReview={!!upNext} />

      {expanded && (
        <ExpandedViewer record={record} index={position} total={walkable.length}
          onPrev={() => step(-1)} onNext={() => step(1)} onClose={() => setExpanded(false)} />
      )}
    </div>
  )
}
