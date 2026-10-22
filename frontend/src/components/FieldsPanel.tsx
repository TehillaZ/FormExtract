import { useState } from 'react'
import { ApiError } from '../api/client'
import { usePatchRecord } from '../api/hooks'
import type { CommitmentRecord, Field, FieldChanges, Suggestion } from '../api/types'
import { FIELD_DEFS, type FieldDef, type FlagLevel, displayValue, editValues, fieldsOf, flagLevel, flaggedCount, reasonText, recordTitle } from '../lib/fields'
import { ConfidenceBadge, Icon } from './ui'

/** What to save to say "this is right as it stands": the field's current values, unchanged. */
function currentValues(def: FieldDef, fields: Field[]): FieldChanges {
  const values = editValues(def, fields)
  return def.list ? { [def.key]: values } : { [def.key]: values[0] ?? '' }
}

/** "Smart memory": people fixed this very reading the same way on earlier forms. Offered, never applied by itself. */
function SuggestionBox({ def, suggestion, recordId }: { def: FieldDef; suggestion: Suggestion; recordId: string }) {
  const [dismissed, setDismissed] = useState(false)
  const apply = usePatchRecord(recordId)
  if (dismissed) return null
  const text = (v: string | null) => v ?? 'ריק'
  const accept = () => {
    const changes = def.list
      ? { [def.key]: suggestion.suggested ? suggestion.suggested.split(', ') : [] }
      : { [def.key]: suggestion.suggested ?? '' }
    apply.mutate(changes)
  }
  return (
    <div role="group" aria-label={`הצעה ל${def.label}`}
      className="mt-1 rounded-[8px] border border-accent-line bg-accent-soft px-2.5 py-1.5 text-xs">
      <div className="font-semibold">
        {def.key === 'sender' && suggestion.current === null
          ? <>בטפסים קודמים מסוג זה הגורם השולח היה ריק ומולא: {text(suggestion.suggested)}</>
          : def.key === 'sender'
          ? <>בטפסים קודמים נקרא הגורם {text(suggestion.current)} ותוקן ל-{text(suggestion.suggested)}</>
          : <>בטפסים קודמים{suggestion.sender ? ` מ${suggestion.sender}` : ''} תוקן {text(suggestion.current)} ל-{text(suggestion.suggested)}</>}
      </div>
      <div className="text-sub">{suggestion.times} מתוך {suggestion.total} תיקונים קודמים של קריאה זו · ההצעה לא הוחלה</div>
      {apply.isError && <div role="alert" className="font-semibold text-warn-ink">ההחלה נכשלה</div>}
      <div className="mt-1 flex gap-1.5">
        <button type="button" onClick={accept} disabled={apply.isPending}
          className="rounded-[7px] border-0 bg-accent px-2.5 py-[3px] text-xs font-semibold text-white">החילי את ההצעה</button>
        <button type="button" onClick={() => setDismissed(true)}
          className="rounded-[7px] border border-line bg-surface px-2.5 py-[3px] text-xs text-ink">התעלמי</button>
      </div>
    </div>
  )
}

const ROW_STYLE: Record<FlagLevel, string> = {
  low: 'bg-warn-row shadow-[inset_-4px_0_0_var(--color-warn)]',
  medium: 'bg-mid-row shadow-[inset_-4px_0_0_var(--color-mid-line)]',
  ok: '',
}

function FieldRow({ def, record }: { def: FieldDef; record: CommitmentRecord }) {
  const fields = fieldsOf(record, def)
  const level = flagLevel(fields)
  const flagged = level !== 'ok'
  const [editing, setEditing] = useState(false)
  const confirm = usePatchRecord(record.id)
  const suggestion = record.suggestions.find((s) => s.field === def.key)

  return (
    <div className={`flex items-start gap-2 border-b border-[#eeeff1] px-4 py-2 ${ROW_STYLE[level]}`}
      data-flagged={flagged} data-level={level}>
      <div className="w-[66px] shrink-0 pt-[2px] text-xs text-sub">{def.label}</div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-2">
          {editing
            ? <FieldEditor def={def} record={record} fields={fields} onDone={() => setEditing(false)} />
            : <ReadOnlyValue def={def} fields={fields} level={level} onEdit={() => setEditing(true)}
                onConfirm={() => confirm.mutate(currentValues(def, fields))} confirming={confirm.isPending}
                error={confirm.error instanceof ApiError ? confirm.error.message : confirm.error ? 'השמירה נכשלה' : null} />}
        </div>
        {suggestion && !editing && <SuggestionBox def={def} suggestion={suggestion} recordId={record.id} />}
      </div>
    </div>
  )
}

function ReadOnlyValue({ def, fields, level, onEdit, onConfirm, confirming, error }: {
  def: FieldDef; fields: Field[]; level: FlagLevel; onEdit: () => void
  onConfirm: () => void; confirming: boolean; error: string | null
}) {
  const text = displayValue(def, fields)
  const reason = reasonText(fields)
  // a value the system rejected (a bad ID, a sender not on the list) is empty, but what was read helps the reviewer
  const readAs = !text ? fields.map((f) => f.raw_text).find(Boolean) : null
  return (
    <>
      <button type="button" onClick={onEdit} title="לחצי לעריכה"
        className="min-w-0 flex-1 border-0 bg-transparent p-0 text-start">
        {text
          ? <div className="truncate text-[15px] font-semibold">{text}</div>
          : <div className="text-[15px] italic text-faint">— לא נמצא</div>}
        {readAs && <div className="truncate text-[11.5px] leading-[1.3] text-sub">נקרא: {readAs}</div>}
        {reason && <div className="text-[11.5px] leading-[1.3] text-sub">{reason}</div>}
        {error && <div role="alert" className="text-[11.5px] font-semibold text-warn-ink">{error}</div>}
      </button>
      {level !== 'ok'
        ? (
          <div className="flex shrink-0 items-center gap-1.5">
            <button type="button" onClick={onConfirm} disabled={confirming}
              aria-label={text ? `אשרי שהערך של ${def.label} נכון` : `אשרי ש${def.label} ריק בטופס`}
              title={text ? 'הערך נכון, אשרי' : 'השדה ריק בטופס, אשרי'}
              className="flex h-6 w-6 items-center justify-center rounded-full border border-accent-line bg-accent-soft text-accent">
              <Icon name="check" size={14} />
            </button>
            <ConfidenceBadge level={level === 'low' ? 'low' : 'medium'} />
          </div>
        )
        : <ConfidenceBadge level="high" />}
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
  const confirmAll = usePatchRecord(record.id)
  // fields read from print that nothing could verify: one look, one click, instead of one click each
  const probable = FIELD_DEFS.filter((def) => flagLevel(fieldsOf(record, def)) === 'medium')
  const confirmProbable = () => confirmAll.mutate(Object.assign({}, ...probable.map((def) => currentValues(def, fieldsOf(record, def)))))
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

      {probable.length > 0 && (
        <div className="flex items-center justify-between gap-2 border-b border-mid-line bg-mid-soft px-4 py-2 text-xs text-mid-ink">
          <span>{probable.length} שדות נקראו בבירור אך לא אומתו</span>
          <button type="button" onClick={confirmProbable} disabled={confirmAll.isPending}
            className="shrink-0 rounded-[7px] border border-mid-line bg-surface px-2.5 py-[3px] text-xs font-semibold text-mid-ink">אשרי את כולם</button>
        </div>
      )}
      {confirmAll.isError && <div role="alert" className="border-b border-warn-line bg-warn-soft px-4 py-1.5 text-xs font-semibold text-warn-ink">האישור נכשל</div>}

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
