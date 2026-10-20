import { useMemo, useState } from 'react'
import { useApproveClean } from '../api/hooks'
import type { CommitmentRecord } from '../api/types'
import { FIELD_DEFS, displayValue, fieldsOf, flaggedCount, isFlagged, needsReview, reasonText } from '../lib/fields'

const COLUMNS = 'grid-cols-[0.9fr_0.9fr_1.1fr_1fr_1.1fr_1.5fr_1.4fr_0.8fr]'

/** One row per form, one column per field. Orange cell = a person must look at it. */
export function TableView({ records, onOpen }: { records: CommitmentRecord[]; onOpen: (id: string) => void }) {
  const [onlyReview, setOnlyReview] = useState(false)
  const approveClean = useApproveClean()

  const flagged = useMemo(() => records.reduce((n, r) => n + (r.status === 'pending' ? flaggedCount(r) : 0), 0), [records])
  const cleanPending = records.filter((r) => r.status === 'pending' && !needsReview(r)).length
  const rows = onlyReview ? records.filter((r) => needsReview(r) && r.status === 'pending') : records

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-10 pt-6 pb-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-4">
          <h1 className="m-0 text-2xl font-bold">{records.length} טפסים</h1>
          <span className="flex items-center gap-2 rounded-full border border-warn-line bg-warn-soft px-3.5 py-1.5 text-[15px] font-semibold text-warn-ink">
            <span className="h-2.5 w-2.5 rounded-full bg-warn" />{flagged} שדות דורשים בדיקה
          </span>
        </div>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-[15px]">
            <input type="checkbox" checked={onlyReview} onChange={(e) => setOnlyReview(e.target.checked)} className="h-[18px] w-[18px] accent-accent" />
            הצג רק שורות עם שדות לבדיקה
          </label>
          <button type="button" disabled={!cleanPending || approveClean.isPending} onClick={() => approveClean.mutate()}
            className="rounded-[10px] border-0 bg-accent px-5 py-2.5 text-[15px] font-semibold text-white">
            אשרי את כל השורות התקינות ({cleanPending})
          </button>
        </div>
      </div>
      {approveClean.data && (
        <div role="status" className="text-sm text-ok-ink">
          אושרו {approveClean.data.approved.length} שורות
          {approveClean.data.skipped_duplicates.length > 0 && ` · ${approveClean.data.skipped_duplicates.length} לא אושרו בגלל מספר התחייבות כפול`}
        </div>
      )}

      <div className="overflow-hidden rounded-[14px] border border-edge bg-surface">
        <div className={`grid ${COLUMNS} gap-3 border-b border-edge bg-page px-5 py-3.5 text-[13px] font-semibold text-sub`}>
          {FIELD_DEFS.map((d) => <div key={d.key}>{d.label}</div>)}
          <div>סטטוס</div>
        </div>
        {rows.map((r) => (
          <button key={r.id} type="button" onClick={() => onOpen(r.id)}
            className={`grid w-full ${COLUMNS} items-center gap-3 border-0 border-b border-[#edeff2] bg-transparent px-5 py-2 text-start text-[15px] hover:bg-page`}>
            {FIELD_DEFS.map((d) => {
              const fields = fieldsOf(r, d)
              const text = displayValue(d, fields)
              const flaggedCell = r.status === 'pending' && fields.some(isFlagged)
              const empty = !text
              return (
                <div key={d.key} title={reasonText(fields) || undefined}
                  className={`flex min-h-[34px] items-center truncate rounded-lg px-2.5 py-1.5 ${
                    empty ? 'border-[1.5px] border-dashed border-faint italic text-sub'
                      : flaggedCell ? 'border border-warn-line bg-warn-soft font-semibold text-warn-ink' : ''}`}>
                  {empty ? '— לא נמצא' : text}
                </div>
              )
            })}
            <div className={`text-[13px] font-semibold ${r.status === 'approved' ? 'text-ok-ink' : 'text-sub'}`}>
              {r.status === 'approved' ? 'מאושר' : needsReview(r) ? 'לבדיקה' : 'תקין'}
            </div>
          </button>
        ))}
        {!rows.length && <div className="px-5 py-10 text-center text-faint">אין שורות להצגה</div>}
      </div>

      <div className="flex items-center gap-5 text-[13px] text-sub">
        <span className="flex items-center gap-1.5"><span className="h-3.5 w-3.5 rounded border border-warn-line bg-warn-soft" />לא בטוח, נדרשת בדיקה</span>
        <span className="flex items-center gap-1.5"><span className="h-3.5 w-3.5 rounded border-[1.5px] border-dashed border-faint" />לא נמצא בטופס (ריק בכוונה)</span>
      </div>
    </div>
  )
}
