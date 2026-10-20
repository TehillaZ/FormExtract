import { useState } from 'react'
import { ApiError } from '../api/client'
import { usePatchRecord } from '../api/hooks'
import type { CommitmentRecord, Field } from '../api/types'
import { FIELD_DEFS, type FieldDef, displayValue, editValues, fieldsOf, flaggedCount, isFlagged, reasonText, recordTitle } from '../lib/fields'
import { ConfidenceBadge, Icon } from './ui'

function FieldRow({ def, record }: { def: FieldDef; record: CommitmentRecord }) {
  const fields = fieldsOf(record, def)
  const flagged = fields.some(isFlagged)
  const [editing, setEditing] = useState(false)

  return (
    <div className={`flex items-start gap-2 border-b border-[#eeeff1] px-4 py-2 ${flagged ? 'bg-warn-row shadow-[inset_-4px_0_0_var(--color-warn)]' : ''}`}>
      <div className="w-[66px] shrink-0 pt-[2px] text-xs text-sub">{def.label}</div>
      {editing
        ? <FieldEditor def={def} record={record} fields={fields} onDone={() => setEditing(false)} />
        : <ReadOnlyValue def={def} fields={fields} flagged={flagged} onEdit={() => setEditing(true)} />}
    </div>
  )
}

function ReadOnlyValue({ def, fields, flagged, onEdit }: { def: FieldDef; fields: Field[]; flagged: boolean; onEdit: () => void }) {
  const text = displayValue(def, fields)
  const reason = reasonText(fields)
  return (
    <>
      <button type="button" onClick={onEdit} title="לחצי לעריכה"
        className="min-w-0 flex-1 border-0 bg-transparent p-0 text-start">
        {text
          ? <div className="truncate text-[15px] font-semibold">{text}</div>
          : <div className="text-[15px] italic text-faint">— לא נמצא</div>}
        {reason && <div className="text-[11.5px] leading-[1.3] text-sub">{reason}</div>}
      </button>
      <ConfidenceBadge level={flagged ? 'low' : 'high'} />
    </>
  )
}

function FieldEditor({ def, record, fields, onDone }: { def: FieldDef; record: CommitmentRecord; fields: Field[]; onDone: () => void }) {
  const patch = usePatchRecord(record.id)
  const [values, setValues] = useState<string[]>(() => {
    const v = editValues(def, fields)
    return def.list && !v.length ? [''] : v.length ? v : ['']
  })
  const error = patch.error instanceof ApiError ? patch.error.message : patch.error ? 'השמירה נכשלה' : null

  const save = () => {
    const changes = def.list ? { [def.key]: values } : { [def.key]: values[0] ?? '' }
    patch.mutate(changes, { onSuccess: onDone })
  }
  const setAt = (i: number, v: string) => setValues((vs) => vs.map((x, j) => (j === i ? v : x)))
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') { e.preventDefault(); save() }
    if (e.key === 'Escape') onDone()
  }

  return (
    <div className="min-w-0 flex-1">
      <div className="flex flex-col gap-1.5">
        {values.map((v, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <input autoFocus={i === 0} value={v} onChange={(e) => setAt(i, e.target.value)} onKeyDown={onKey}
              aria-label={def.label} dir="auto"
              className="min-w-0 flex-1 rounded-[7px] border-[1.5px] border-ink bg-surface px-2 py-[5px] text-[15px] font-semibold" />
            {def.list && values.length > 1 && (
              <button type="button" aria-label="הסרה" onClick={() => setValues((vs) => vs.filter((_, j) => j !== i))}
                className="flex h-[30px] w-[30px] items-center justify-center rounded-[7px] border border-line bg-surface text-sub"><Icon name="trash" size={15} /></button>
            )}
          </div>
        ))}
      </div>
      {def.list && (
        <button type="button" onClick={() => setValues((vs) => [...vs, ''])}
          className="mt-1.5 border-0 bg-transparent p-0 text-xs font-semibold text-accent">+ הוספת מספר</button>
      )}
      {error && <div role="alert" className="mt-1 text-xs font-semibold text-warn-ink">{error}</div>}
      <div className="mt-1.5 flex gap-1.5">
        <button type="button" onClick={save} disabled={patch.isPending}
          className="flex items-center gap-1 rounded-[7px] border-0 bg-accent px-3 py-1 text-xs font-semibold text-white"><Icon name="check" size={14} />שמרי</button>
        <button type="button" onClick={onDone}
          className="rounded-[7px] border border-line bg-surface px-3 py-1 text-xs text-ink">בטלי</button>
      </div>
    </div>
  )
}

export function FieldsPanel({ record, onApprove, approving, approveError, onNextToReview, hasNextToReview }: {
  record: CommitmentRecord
  onApprove: () => void
  approving: boolean
  approveError: string | null
  onNextToReview: () => void
  hasNextToReview: boolean
}) {
  const flagged = flaggedCount(record)
  const approved = record.status === 'approved'
  return (
    <section aria-label="שדות הטופס" className="flex w-[316px] shrink-0 flex-col overflow-hidden border-s border-edge bg-surface">
      <div className="flex items-center justify-between border-b border-edge px-4 py-2.5">
        <h2 className="m-0 truncate text-base font-bold">{recordTitle(record)}</h2>
        {approved
          ? <span className="rounded-full bg-ok-soft px-2.5 py-[2px] text-xs font-bold text-ok-ink">מאושר</span>
          : flagged > 0
            ? <span className="rounded-full bg-warn-soft px-2.5 py-[2px] text-xs font-bold text-warn-ink">{flagged} לבדיקה</span>
            : <span className="rounded-full bg-ok-soft px-2.5 py-[2px] text-xs font-bold text-ok-ink">תקין</span>}
      </div>

      {record.duplicate_warnings.length > 0 && (
        <div role="alert" className="border-b border-warn-line bg-warn-soft px-4 py-2 text-xs font-semibold text-warn-ink">
          {record.duplicate_warnings.map((w) => <div key={w}>{w}</div>)}
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {FIELD_DEFS.map((def) => <FieldRow key={def.key + record.id} def={def} record={record} />)}
      </div>

      <div className="border-t border-edge px-4 py-3">
        {approveError && <div role="alert" className="mb-2 text-xs font-semibold text-warn-ink">{approveError}</div>}
        <div className="flex gap-2">
          <button type="button" onClick={onNextToReview} disabled={!hasNextToReview}
            className="flex-1 rounded-[10px] border-[1.5px] border-warn bg-surface py-2.5 text-sm font-semibold text-warn-ink">הבא לבדיקה</button>
          <button type="button" onClick={onApprove} disabled={approving || approved}
            className="flex-1 rounded-[10px] border-0 bg-accent py-2.5 text-sm font-semibold text-white">{approved ? 'מאושר' : 'אשרי ושמרי'}</button>
        </div>
      </div>
    </section>
  )
}
