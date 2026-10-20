import { useState } from 'react'
import { useEvaluation } from '../api/hooks'
import type { EvaluationReport } from '../api/types'
import {
  FIELD_LABELS, accuracy, deltaPoints, errors, fieldOrder, flaggedRate, percent, reportTitle, splitSize, totalSilentErrors,
} from '../lib/accuracy'

const MAX_COMPARED = 3
const keyOf = (r: EvaluationReport) => `${r.tag}__${r.split}`

function Delta({ points }: { points: number }) {
  if (points === 0) return <span className="text-xs text-faint">±0</span>
  return <span className={`text-xs font-bold ${points > 0 ? 'text-ok-ink' : 'text-warn-ink'}`}>{points > 0 ? '+' : '−'}{Math.abs(points)}</span>
}

/** What the accuracy numbers are and are not: never show a number without saying how many pages stand behind it. */
function Caveats({ reports, testPages, devPages }: { reports: EvaluationReport[]; testPages: number; devPages: number }) {
  const testRun = reports.some((r) => r.split === 'test' || r.split === 'all')
  return (
    <div role="note" className="flex flex-col gap-1.5 rounded-xl border border-edge bg-surface px-4 py-3 text-[13px] text-sub">
      {!testRun && (
        <div className="font-semibold text-warn-ink" data-testid="test-not-run">
          סט הבדיקה ({testPages} עמודים) טרם הורץ. כל המספרים כאן הם על עמודי פיתוח ({devPages} עמודים), שעליהם כוונו הפרומפט והכללים,
          ולכן אינם מייצגים דיוק סופי.
        </div>
      )}
      <div>הדוגמאות מסומנות במרקר צהוב, ולכן הדיוק בשטח צפוי להיות נמוך יותר.</div>
      <div>
        <b>שגיאה שלא סומנה</b> היא ערך שגוי שהמערכת הציגה כבטוח, כלומר טעות שמגיעה למסד הנתונים בלי שאיש בדק אותה. זה המדד החשוב ביותר.
      </div>
    </div>
  )
}

/** The saved evaluation results, side by side, so two models or two prompt versions can be compared (PLAN 9, extra 2). */
export function AccuracyView() {
  const { data, isLoading, isError } = useEvaluation()
  const [chosen, setChosen] = useState<string[] | null>(null)

  if (isLoading) return <div className="m-auto text-sub">טוען…</div>
  if (isError || !data) return <div role="alert" className="m-auto text-warn-ink">לא ניתן לטעון את דוחות הדיוק.</div>

  const { reports } = data
  const selectedKeys = chosen ?? reports.slice(0, 2).map(keyOf)
  const selected = reports.filter((r) => selectedKeys.includes(keyOf(r)))
  const toggle = (key: string) =>
    setChosen(selectedKeys.includes(key) ? selectedKeys.filter((k) => k !== key) : [...selectedKeys, key].slice(-MAX_COMPARED))

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-10 pt-6 pb-8">
      <h1 className="m-0 text-2xl font-bold">דוח דיוק</h1>

      {!reports.length ? (
        <div className="rounded-xl border border-edge bg-surface px-5 py-8 text-center text-sub">
          <p className="m-0 font-semibold text-ink">עדיין אין דוחות דיוק.</p>
          <p className="mb-2 mt-1">דוח נשמר בכל הרצה של סקריפט ההערכה על קבוצת עמודים שלמה:</p>
          <code dir="ltr" className="rounded bg-muted px-3 py-1.5 text-[13px]">python scripts/evaluate.py --provider gemini --split dev</code>
        </div>
      ) : (
        <>
          <Caveats reports={reports} testPages={data.test_pages} devPages={data.dev_pages} />

          <fieldset className="m-0 flex flex-wrap gap-3 border-0 p-0">
            <legend className="mb-1 text-sm font-semibold">השוואה (עד {MAX_COMPARED} דוחות)</legend>
            {reports.map((r) => {
              const key = keyOf(r)
              const on = selectedKeys.includes(key)
              const of = splitSize(r.split, { pages: data.pages, dev_pages: data.dev_pages, test_pages: data.test_pages })
              return (
                <label key={key} className={`flex cursor-pointer items-start gap-2 rounded-xl border px-3 py-2 text-sm ${on ? 'border-accent-line bg-accent-soft' : 'border-edge bg-surface'}`}>
                  <input type="checkbox" checked={on} onChange={() => toggle(key)} className="mt-1 h-4 w-4 accent-accent" />
                  <span>
                    <span className="block font-semibold">{reportTitle(r)}</span>
                    <span className="block text-xs text-sub">
                      {r.pages_scored} מתוך {of} עמודים · {new Date(r.created_at).toLocaleDateString('he-IL')} · ת"ז: {r.checksum_mode}
                    </span>
                  </span>
                </label>
              )
            })}
          </fieldset>

          {selected.length === 0 ? (
            <div className="text-sub">בחרי דוח אחד או יותר להצגה.</div>
          ) : (
            <div className="overflow-x-auto rounded-[14px] border border-edge bg-surface">
              <table className="w-full border-collapse text-[15px]">
                <caption className="sr-only">דיוק לפי שדה</caption>
                <thead>
                  <tr className="bg-page text-[13px] text-sub">
                    <th rowSpan={2} scope="col" className="px-5 py-3 text-start font-semibold">שדה</th>
                    {selected.map((r) => (
                      <th key={keyOf(r)} colSpan={3} scope="colgroup" className="border-s border-edge px-3 py-2 text-center font-semibold">
                        {reportTitle(r)}
                        <span className="block text-xs font-normal">{r.pages_scored} עמודים</span>
                      </th>
                    ))}
                  </tr>
                  <tr className="bg-page text-xs text-sub">
                    {selected.flatMap((r) => [
                      <th key={`${keyOf(r)}-a`} scope="col" className="border-s border-edge px-3 py-2 font-semibold">דיוק</th>,
                      <th key={`${keyOf(r)}-f`} scope="col" className="px-3 py-2 font-semibold">סומנו לבדיקה</th>,
                      <th key={`${keyOf(r)}-s`} scope="col" className="px-3 py-2 font-semibold">שגיאות שלא סומנו</th>,
                    ])}
                  </tr>
                </thead>
                <tbody>
                  {fieldOrder(selected).map((field) => (
                    <tr key={field} className="border-t border-[#edeff2]">
                      <th scope="row" className="px-5 py-3 text-start font-semibold">{FIELD_LABELS[field] ?? field}</th>
                      {selected.map((r, i) => {
                        const f = r.fields[field]
                        if (!f) return <td key={keyOf(r)} colSpan={3} className="border-s border-edge px-3 py-3 text-center text-faint">—</td>
                        const base = selected[0].fields[field]
                        return [
                          <td key={`${keyOf(r)}-a`} className="border-s border-edge px-3 py-3" data-cell="accuracy">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold">{percent(accuracy(f))}</span>
                              {i > 0 && base && <Delta points={deltaPoints(base, f)} />}
                            </div>
                            <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-muted" aria-hidden="true">
                              <div className="h-full bg-accent" style={{ width: percent(accuracy(f)) }} />
                            </div>
                          </td>,
                          <td key={`${keyOf(r)}-f`} className="px-3 py-3 text-sub">{percent(flaggedRate(f))}</td>,
                          <td key={`${keyOf(r)}-s`} data-silent={f.silent_errors > 0}
                            className={`px-3 py-3 ${f.silent_errors > 0 ? 'font-bold text-warn-ink' : 'text-sub'}`}>
                            {f.silent_errors} מתוך {errors(f)}
                          </td>,
                        ]
                      })}
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-edge bg-page">
                    <th scope="row" className="px-5 py-3 text-start font-semibold">סך שגיאות שלא סומנו</th>
                    {selected.map((r) => (
                      <td key={keyOf(r)} colSpan={3} data-silent-total className={`border-s border-edge px-3 py-3 text-center font-bold ${totalSilentErrors(r) > 0 ? 'text-warn-ink' : 'text-ok-ink'}`}>
                        {totalSilentErrors(r)}
                      </td>
                    ))}
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
          {selected.length > 1 && (
            <p className="m-0 text-xs text-faint">
              השינוי ליד הדיוק הוא בנקודות אחוז ביחס לדוח הראשון בטבלה. עם עשרות עמודים בלבד, הפרשים קטנים הם בגדר רעש.
            </p>
          )}
        </>
      )}
    </div>
  )
}
