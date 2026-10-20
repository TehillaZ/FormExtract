import { useEffect, useState } from 'react'
import type { CommitmentRecord } from '../api/types'
import { FIELD_DEFS, displayValue, fieldsOf, isFlagged, recordTitle } from '../lib/fields'
import { ImageCanvas } from './ImageViewer'
import { useImageView } from './useImageView'
import { Icon, IconButton } from './ui'

/** Full-screen close-up of the form, with prev/next and the extracted values for comparing against the image. */
export function ExpandedViewer({ record, index, total, onPrev, onNext, onClose }: {
  record: CommitmentRecord
  index: number
  total: number
  onPrev: () => void
  onNext: () => void
  onClose: () => void
}) {
  const view = useImageView(record.id, 'width')
  const [percent, setPercent] = useState(100)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowLeft') onNext()    // in a right-to-left layout "next" is to the left
      if (e.key === 'ArrowRight') onPrev()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, onNext, onPrev])

  return (
    <div role="dialog" aria-modal="true" aria-label="תצוגה מוגדלת של הטופס" className="fixed inset-0 z-50 flex flex-col bg-stage">
      <div className="flex h-14 items-center justify-between border-b border-edge bg-surface px-5">
        <div className="flex items-center gap-3.5">
          <IconButton icon="close" label="סגירה" onClick={onClose} />
          <div className="text-[17px] font-bold">{recordTitle(record)}</div>
          <div className="text-sm text-sub">טופס {index + 1} מתוך {total}</div>
        </div>

        <div className="flex items-center gap-2">
          <IconButton icon="minus" label="הקטנה" onClick={() => view.zoomBy(0.8)} />
          <div className="min-w-12 text-center text-sm font-semibold">{percent}%</div>
          <IconButton icon="plus" label="הגדלה" onClick={() => view.zoomBy(1.25)} />
          <span className="mx-1 h-6 w-px bg-edge" />
          <button type="button" onClick={() => view.setFit('actual')} className="rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px]">גודל מקורי</button>
          <button type="button" onClick={() => view.setFit('width')} className="rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px]">התאמה לרוחב</button>
          <button type="button" onClick={() => view.setFit('height')} className="rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px]">התאמה לגובה</button>
          <IconButton icon="rotate" label="סיבוב" onClick={view.rotate} />
          <IconButton icon="lens" label="זכוכית מגדלת" active={view.lens} disabled={view.rotation !== 0} onClick={view.toggleLens} />
        </div>

        <div className="flex gap-2">
          <IconButton icon="chevron-start" label="הטופס הקודם" onClick={onPrev} />
          <IconButton icon="chevron-end" label="הטופס הבא" onClick={onNext} />
        </div>
      </div>

      <div className="min-h-0 flex-1 p-3">
        <ImageCanvas pageId={record.page_ids[0]} view={view} onPercent={setPercent} />
      </div>

      <div className="flex h-14 items-center gap-2 overflow-x-auto border-t border-edge bg-surface px-5">
        {FIELD_DEFS.map((def) => {
          const fields = fieldsOf(record, def)
          const flagged = fields.some(isFlagged)
          return (
            <span key={def.key} className={`flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 ${flagged ? 'border-warn-line bg-warn-soft' : 'border-edge bg-page'}`}>
              <span className={`h-2 w-2 rounded-full ${flagged ? 'bg-warn' : 'bg-accent'}`} />
              <span className="text-xs text-sub">{def.short}</span>
              <span className="text-sm font-semibold">{displayValue(def, fields) || '— לא נמצא'}</span>
            </span>
          )
        })}
        <span className="ms-auto flex shrink-0 items-center gap-1 text-xs text-faint"><Icon name="close" size={12} />Esc לסגירה</span>
      </div>
    </div>
  )
}
