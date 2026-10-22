import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { useDocument, useReprocess, useUpload } from '../api/hooks'
import type { DocumentStatus, PageStatus } from '../api/types'
import { Icon } from './ui'

const ACCEPT = '.pdf,.jpg,.jpeg,.png,.heic,.heif,.tif,.tiff'
const STATUS_TEXT: Record<PageStatus['status'], string> = { pending: 'ממתין', processing: 'בעיבוד', ready: 'מוכן', error: 'שגיאה' }
const STATUS_STYLE: Record<PageStatus['status'], string> = {
  pending: 'bg-muted text-sub', processing: 'bg-accent-soft text-accent', ready: 'bg-ok-soft text-ok-ink', error: 'bg-warn-soft text-warn-ink',
}

function DocumentCard({ initial, onSettled }: { initial: DocumentStatus; onSettled: () => void }) {
  const { data } = useDocument(initial.id)
  // the status endpoint does not repeat `duplicate`: that fact comes only from the upload's answer
  const doc = { ...(data ?? initial), duplicate: initial.duplicate }
  const reprocess = useReprocess()

  useEffect(() => { if (doc.done) onSettled() }, [doc.done])   // eslint-disable-line react-hooks/exhaustive-deps

  const ready = doc.pages.filter((p) => p.status === 'ready').length
  return (
    <li className="rounded-xl border border-edge bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate font-semibold">{doc.filename}</div>
          <div className="text-xs text-sub">
            {doc.duplicate ? 'קובץ זהה כבר הועלה בעבר, לא עובד שוב' : `${ready} מתוך ${doc.pages.length} עמודים מוכנים`}
          </div>
        </div>
        {!doc.duplicate && (
          <div className="h-2 w-40 shrink-0 overflow-hidden rounded bg-muted">
            <div className="h-full bg-accent transition-[width]" style={{ width: `${doc.pages.length ? (ready / doc.pages.length) * 100 : 0}%` }} />
          </div>
        )}
      </div>
      {!doc.duplicate && (
        <ul className="m-0 mt-3 flex list-none flex-wrap gap-2 p-0">
          {doc.pages.map((p) => (
            <li key={p.id} className={`flex items-center gap-2 rounded-lg px-2.5 py-1 text-xs font-semibold ${STATUS_STYLE[p.status]}`}>
              עמוד {p.page_number} · {STATUS_TEXT[p.status]}
              {p.status === 'error' && (
                <button type="button" onClick={() => reprocess.mutate(p.id)} className="border-0 bg-transparent p-0 text-xs font-bold text-warn-ink underline">נסי שוב</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

/** Drag-and-drop upload and the processing status of every file (PLAN 4.1). */
export function UploadView({ onReview, onUploaded }: { onReview: () => void; onUploaded?: (pageId: string) => void }) {
  const upload = useUpload()
  const qc = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [docs, setDocs] = useState<DocumentStatus[]>([])

  const send = (files: FileList | File[]) => {
    const list = Array.from(files)
    if (!list.length) return
    upload.mutate(list, {
      onSuccess: (created) => {
        setDocs((d) => [...created, ...d])
        // the form can be viewed as soon as it is uploaded, while its fields are still being read
        const first = created.find((d) => !d.duplicate)?.pages[0]
        if (first) onUploaded?.(first.id)
      },
    })
  }
  const error = upload.error instanceof ApiError ? upload.error.message : upload.error ? 'ההעלאה נכשלה' : null

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-6 py-10">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); send(e.dataTransfer.files) }}
        className={`flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-6 py-14 text-center ${dragging ? 'border-accent bg-accent-soft' : 'border-line bg-surface'}`}>
        <span className="text-accent"><Icon name="upload" size={36} /></span>
        <div className="text-lg font-semibold">גררי לכאן קבצי טפסים</div>
        <div className="text-sm text-sub">PDF, JPG, PNG או HEIC. קובץ אחד או ערימה.</div>
        <button type="button" onClick={() => input.current?.click()} disabled={upload.isPending}
          className="rounded-[10px] border-0 bg-accent px-5 py-2.5 text-[15px] font-semibold text-white">{upload.isPending ? 'מעלה…' : 'בחרי קבצים'}</button>
        <input ref={input} type="file" multiple accept={ACCEPT} hidden aria-label="בחירת קבצים"
          onChange={(e) => { if (e.target.files) send(e.target.files); e.target.value = '' }} />
        {error && <div role="alert" className="text-sm font-semibold text-warn-ink">{error}</div>}
      </div>

      {docs.length > 0 && (
        <>
          <ul className="m-0 flex list-none flex-col gap-3 p-0">
            {docs.map((d) => <DocumentCard key={d.id} initial={d} onSettled={() => qc.invalidateQueries({ queryKey: ['records'] })} />)}
          </ul>
          <button type="button" onClick={onReview}
            className="self-start rounded-[10px] border-[1.5px] border-accent bg-surface px-5 py-2.5 text-[15px] font-semibold text-accent">לבדיקה</button>
        </>
      )}
    </div>
  )
}
