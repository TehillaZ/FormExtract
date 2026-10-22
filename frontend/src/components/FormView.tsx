import { useEffect, useMemo, useState } from 'react'
import { ApiError } from '../api/client'
import { useApproveRecord, useReprocess } from '../api/hooks'
import type { ActivePage, CommitmentRecord } from '../api/types'
import { FIELD_DEFS } from '../lib/fields'
import { type ListFilter, filterRecords, flaggedCount, nextToReview } from '../lib/fields'
import { useShortcuts } from '../lib/useShortcuts'
import { ExpandedViewer } from './ExpandedViewer'
import { FieldsPanel } from './FieldsPanel'
import { FormList } from './FormList'
import { ImageCanvas, ViewToolbar } from './ImageViewer'
import { Icon } from './ui'
import { useImageView } from './useImageView'

const OPEN_KEY = 'formlist-open'
const NOTE_MS = 4000

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

interface Props {
  records: CommitmentRecord[]
  pending?: ActivePage[]       // pages still being read: their image is already viewable
  selectedId: string | null
  onSelect: (id: string) => void
}

/** The review screen. With no forms there is nothing to review: say how to get some. */
export function FormView(props: Props) {
  const { records, pending = [], selectedId } = props
  // the selection is a record, or a page that has not become one yet (a page's record then takes its place)
  const record = records.find((r) => r.id === selectedId || (!!selectedId && r.page_ids.includes(selectedId)))
  const waiting = pending.find((p) => p.id === selectedId)
  if (record) return <ReviewScreen {...props} pending={pending} record={record} />
  if (waiting) return <WaitingScreen {...props} pending={pending} page={waiting} />
  if (records[0]) return <ReviewScreen {...props} pending={pending} record={records[0]} />
  if (pending[0]) return <WaitingScreen {...props} pending={pending} page={pending[0]} />
  return <div className="m-auto text-sub">אין טפסים עדיין. אפשר להעלות קבצים בלשונית "העלאה".</div>
}

/** A form that is uploaded but not read yet: the image is there to look at while the fields are being filled in. */
function WaitingScreen({ records, pending = [], page, onSelect }: Props & { page: ActivePage }) {
  const [listOpen, setListOpen] = useStoredFlag(OPEN_KEY, true)
  const [filter, setFilter] = useState<ListFilter>('all')
  const reprocess = useReprocess()
  const view = useImageView(page.id)
  const failed = page.status === 'error'

  return (
    <div className="flex min-h-0 flex-1">
      <FormList records={records} pending={pending} selectedId={page.id} onSelect={onSelect} open={listOpen}
        onToggle={() => setListOpen((o) => !o)} filter={filter} onFilter={setFilter} />
      <div className="relative flex min-w-0 flex-1 bg-stage">
        <ViewToolbar view={view} />
        <div className="min-h-0 flex-1 p-3">
          <ImageCanvas pageId={page.id} view={view} />
        </div>
      </div>
      <section aria-label="שדות הטופס" className="flex w-[316px] shrink-0 flex-col overflow-hidden border-s border-edge bg-surface">
        <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
          <h2 className="m-0 truncate text-base font-bold">{page.filename} · עמוד {page.page_number}</h2>
        </div>
        {failed ? (
          <div role="alert" className="flex flex-col gap-2 px-4 py-4 text-sm font-semibold text-warn-ink">
            קריאת השדות נכשלה ({page.error ?? 'שגיאה'}).
            <button type="button" onClick={() => reprocess.mutate(page.id)} disabled={reprocess.isPending}
              className="self-start rounded-[10px] border-[1.5px] border-warn bg-surface px-4 py-2 text-sm font-semibold text-warn-ink">נסי שוב</button>
          </div>
        ) : (
          <div role="status" className="flex flex-col">
            <div className="border-b border-edge px-4 py-2 text-xs font-semibold text-accent">
              {page.status === 'pending' ? 'ממתין לתור…' : 'קורא את השדות… אפשר לעיין בטופס בינתיים'}
            </div>
            {FIELD_DEFS.map((def) => (
              <div key={def.key} className="flex items-center gap-2 border-b border-[#eeeff1] px-4 py-3">
                <div className="w-[66px] shrink-0 text-xs text-sub">{def.label}</div>
                <div className="flex-1 animate-pulse text-[15px] italic text-faint" data-testid="reading">קורא…</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

/** A collapsible list of forms, the form image, and its fields, with keyboard shortcuts. */
function ReviewScreen({ records, pending = [], record, onSelect }: Props & { record: CommitmentRecord }) {
  const [listOpen, setListOpen] = useStoredFlag(OPEN_KEY, true)
  const [filter, setFilter] = useState<ListFilter>('all')
  const [expanded, setExpanded] = useState(false)
  const [percent, setPercent] = useState(100)
  const [note, setNote] = useState<{ id: string; text: string } | null>(null)
  const approve = useApproveRecord()

  const view = useImageView(record.id)
  const upNext = useMemo(() => nextToReview(records, record.id), [records, record.id])
  const visible = useMemo(() => filterRecords(records, filter, ''), [records, filter])
  const { reset: resetApprove } = approve

  useEffect(() => { resetApprove() }, [record.id, resetApprove])
  useEffect(() => {
    if (!note) return
    const timer = setTimeout(() => setNote(null), NOTE_MS)
    return () => clearTimeout(timer)
  }, [note])

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

  useShortcuts({
    ArrowDown: () => step(1),
    ArrowUp: () => step(-1),
    KeyN: () => upNext && onSelect(upNext.id),
    KeyL: () => setListOpen((open) => !open),
    // approving from the keyboard is only for a form with nothing left to check: a keystroke must never wave
    // through values nobody looked at (the buttons still allow a deliberate approval of a flagged form)
    KeyA: () => {
      if (record.status === 'approved' || approve.isPending) return
      if (flaggedCount(record) > 0) setNote({ id: record.id, text: 'אי אפשר לאשר במקלדת כשיש שדות לבדיקה. אשרי או תקני אותם, או השתמשי בכפתור.' })
      else doApprove()
    },
  }, !expanded)

  return (
    <div className="flex min-h-0 flex-1">
      <FormList records={records} pending={pending} selectedId={record.id} onSelect={onSelect} open={listOpen}
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
        <div className="absolute bottom-3 start-3.5 z-10 flex max-w-[60%] flex-col items-start gap-1">
          {note?.id === record.id && (
            <div role="status" className="rounded-lg border border-warn-line bg-warn-soft px-2.5 py-1 text-xs font-semibold text-warn-ink">{note.text}</div>
          )}
          <div aria-label="קיצורי מקלדת" className="rounded-lg border border-edge bg-surface px-2.5 py-1 text-xs text-sub">
            <kbd>↑</kbd><kbd>↓</kbd> טפסים · <kbd>N</kbd> הבא לבדיקה · <kbd>A</kbd> אישור (כשאין שדות לבדיקה) · <kbd>L</kbd> רשימה
          </div>
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
