import { useCorrectionSummary } from '../api/hooks'
import type { CorrectionGroup } from '../api/types'
import { FIELD_LABELS } from '../lib/accuracy'

const SOURCE_LABELS: Record<string, string> = {
  handwritten: 'כתב יד', printed: 'מודפס', sticker: 'מדבקה', stamp: 'חותמת', barcode: 'ברקוד', manual: 'ידני',
}

const show = (v: string | null) => v ?? 'ריק'

function Group({ g }: { g: CorrectionGroup }) {
  const sources = Object.entries(g.sources).map(([s, n]) => `${SOURCE_LABELS[s] ?? s} ${n}`).join(' · ')
  return (
    <tr className="border-t border-[#edeff2] align-top">
      <th scope="row" className="px-5 py-3 text-start font-semibold">{FIELD_LABELS[g.field] ?? g.field}</th>
      <td className="px-3 py-3">{g.sender ?? <span className="text-faint">לא ידוע</span>}</td>
      <td className="px-3 py-3 text-sub" dir="ltr">{g.template ?? '—'}</td>
      <td className="px-3 py-3 font-bold" data-cell="count">{g.count}</td>
      <td className={`px-3 py-3 ${g.unflagged ? 'font-bold text-warn-ink' : 'text-sub'}`} data-cell="unflagged">{g.unflagged}</td>
      <td className="px-3 py-3 text-sub">{sources || '—'}</td>
      <td className="px-3 py-3">
        <ul className="m-0 list-none p-0">
          {g.examples.map((e, i) => (
            <li key={i} dir="ltr" className="text-start text-[13px]">{show(e.old)} → {show(e.new)}</li>
          ))}
        </ul>
      </td>
    </tr>
  )
}

/** Mistakes that people keep fixing: the same field on the same sender's forms. The basis for sender-specific rules. */
export function CorrectionsView() {
  const { data, isLoading, isError } = useCorrectionSummary()

  if (isLoading) return <div className="m-auto text-sub">טוען…</div>
  if (isError || !data) return <div role="alert" className="m-auto text-warn-ink">לא ניתן לטעון את התיקונים.</div>

  const total = data.reduce((n, g) => n + g.count, 0)
  const unflagged = data.reduce((n, g) => n + g.unflagged, 0)
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-10 pt-6 pb-8">
      <h1 className="m-0 text-2xl font-bold">טעויות חוזרות</h1>

      {!data.length ? (
        <div className="rounded-xl border border-edge bg-surface px-5 py-8 text-center text-sub">
          <p className="m-0 font-semibold text-ink">עדיין לא תוקן שום ערך.</p>
          <p className="mb-0 mt-1">כל תיקון שתבצעי בטופס יופיע כאן, מקובץ לפי שדה וגורם שולח.</p>
        </div>
      ) : (
        <>
          <div role="note" className="rounded-xl border border-edge bg-surface px-4 py-3 text-[13px] text-sub">
            {total} תיקונים ב-{data.length} קבוצות. <b>תוקנו אף שהוצגו כבטוחים</b> הם ערכים שגויים שהמערכת סימנה כנכונים ({unflagged}):
            הם הסימן הברור ביותר לכלל שחסר. אישור של ערך בלי שינוי אינו נספר כתיקון.
          </div>
          <div className="overflow-x-auto rounded-[14px] border border-edge bg-surface">
            <table className="w-full border-collapse text-[15px]">
              <caption className="sr-only">תיקונים לפי שדה וגורם שולח</caption>
              <thead>
                <tr className="bg-page text-[13px] text-sub">
                  <th scope="col" className="px-5 py-3 text-start font-semibold">שדה</th>
                  <th scope="col" className="px-3 py-3 text-start font-semibold">גורם שולח</th>
                  <th scope="col" className="px-3 py-3 text-start font-semibold">סוג טופס</th>
                  <th scope="col" className="px-3 py-3 text-start font-semibold">תיקונים</th>
                  <th scope="col" className="px-3 py-3 text-start font-semibold">תוקנו אף שהוצגו כבטוחים</th>
                  <th scope="col" className="px-3 py-3 text-start font-semibold">איך הופיע</th>
                  <th scope="col" className="px-3 py-3 text-start font-semibold">דוגמאות (נקרא → תוקן)</th>
                </tr>
              </thead>
              <tbody>{data.map((g) => <Group key={`${g.field}|${g.sender}|${g.template}`} g={g} />)}</tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
