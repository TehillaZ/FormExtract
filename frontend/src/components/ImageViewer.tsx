import { useEffect, useRef, useState } from 'react'
import type { PointerEvent } from 'react'
import { pageImageUrl } from '../api/client'
import { IconButton } from './ui'
import type { ImageView } from './useImageView'

const PAD = 32
const LENS_RADIUS = 90
const LENS_ZOOM = 2.5

function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [size, setSize] = useState({ w: 0, h: 0 })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setSize({ w: entry.contentRect.width, h: entry.contentRect.height }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, size] as const
}

/** The page image at the scale the view asks for. Scrolls when larger than the space it has. */
export function ImageCanvas({ pageId, view, onPercent }: {
  pageId: string | undefined; view: ImageView; onPercent?: (percent: number) => void
}) {
  const [boxRef, box] = useElementSize<HTMLDivElement>()
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null)
  const [failed, setFailed] = useState(false)
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null)
  const src = pageId ? pageImageUrl(pageId) : undefined

  const [seenSrc, setSeenSrc] = useState(src)
  if (seenSrc !== src) {   // another page: forget the old image's size
    setSeenSrc(src)
    setNatural(null)
    setFailed(false)
  }

  const turned = view.rotation === 90 || view.rotation === 270
  const rw = natural ? (turned ? natural.h : natural.w) : 1
  const rh = natural ? (turned ? natural.w : natural.h) : 1
  const fitHeightScale = box.h > PAD ? (box.h - PAD) / rh : 1
  const fitScale = view.fit === 'actual' ? 1 : view.fit === 'width' ? Math.max(0.01, (box.w - PAD) / rw) : fitHeightScale
  const scale = fitScale * view.zoom
  const percent = Math.round((scale / fitHeightScale) * 100)

  useEffect(() => { if (natural) onPercent?.(percent) }, [percent, natural, onPercent])

  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    setPointer({ x: e.clientX - r.left, y: e.clientY - r.top })
  }

  if (!src) return <div ref={boxRef} className="flex h-full w-full items-center justify-center text-sub">אין תמונה לטופס</div>

  const w = natural ? rw * scale : 0
  const h = natural ? rh * scale : 0
  const lensOn = view.lens && view.rotation === 0 && natural && pointer

  return (
    <div ref={boxRef} className="flex h-full w-full overflow-auto">
      {failed && <div className="m-auto text-sub">התמונה לא זמינה</div>}
      {!natural && !failed && <div className="m-auto text-sub">טוען תמונה…</div>}
      <div className="relative m-auto shrink-0 bg-white shadow-[0_6px_24px_rgba(20,22,28,0.2)]"
        style={{ width: w, height: h, display: natural ? 'block' : 'none', cursor: view.lens && view.rotation === 0 ? 'none' : 'default' }}
        onPointerMove={onMove} onPointerLeave={() => setPointer(null)}>
        <img src={src} alt="תמונת הטופס" draggable={false}
          onLoad={(e) => setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
          onError={() => setFailed(true)}
          className="absolute left-1/2 top-1/2 max-w-none select-none"
          style={{
            width: natural ? natural.w * scale : undefined, height: natural ? natural.h * scale : undefined,
            transform: `translate(-50%, -50%) rotate(${view.rotation}deg)`,   // physical centring: independent of text direction
          }} />
        {lensOn && (
          <div aria-hidden="true" className="pointer-events-none absolute rounded-full border-2 border-accent shadow-lg"
            style={{
              width: LENS_RADIUS * 2, height: LENS_RADIUS * 2,
              left: pointer.x - LENS_RADIUS, top: pointer.y - LENS_RADIUS,
              backgroundImage: `url(${src})`, backgroundRepeat: 'no-repeat',
              backgroundSize: `${w * LENS_ZOOM}px ${h * LENS_ZOOM}px`,
              backgroundPosition: `${LENS_RADIUS - pointer.x * LENS_ZOOM}px ${LENS_RADIUS - pointer.y * LENS_ZOOM}px`,
            }} />
        )}
      </div>
    </div>
  )
}

/** The vertical toolbar floating over the image on the review screen. */
export function ViewToolbar({ view, onExpand }: { view: ImageView; onExpand?: () => void }) {
  return (
    <div className="absolute end-3.5 top-3.5 z-10 flex flex-col gap-1.5 rounded-xl border border-edge bg-surface p-1.5 shadow-sm">
      <IconButton icon="plus" label="הגדלה" onClick={() => view.zoomBy(1.25)} />
      <IconButton icon="minus" label="הקטנה" onClick={() => view.zoomBy(0.8)} />
      <div className="h-px bg-edge" />
      <IconButton icon="fit-height" label="התאמה לגובה" active={view.fit === 'height' && view.zoom === 1} onClick={() => view.setFit('height')} />
      <IconButton icon="fit-width" label="התאמה לרוחב" active={view.fit === 'width' && view.zoom === 1} onClick={() => view.setFit('width')} />
      <IconButton icon="rotate" label="סיבוב" onClick={view.rotate} />
      <IconButton icon="lens" label="זכוכית מגדלת" active={view.lens} disabled={view.rotation !== 0} onClick={view.toggleLens} />
      {onExpand && <><div className="h-px bg-edge" /><IconButton icon="expand" label="הרחבה למסך מלא" onClick={onExpand} /></>}
    </div>
  )
}
