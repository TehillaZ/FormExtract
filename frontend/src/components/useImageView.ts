import { useCallback, useState } from 'react'

export type Fit = 'height' | 'width' | 'actual'
export type Rotation = 0 | 90 | 180 | 270

const MIN_ZOOM = 0.5
const MAX_ZOOM = 8

export interface ImageView {
  fit: Fit
  zoom: number
  rotation: Rotation
  lens: boolean
  setFit: (fit: Fit) => void
  zoomBy: (factor: number) => void
  rotate: () => void
  toggleLens: () => void
}

/** Zoom, fit mode, rotation and lens state of one image. Showing another form (`resetKey`) starts fresh. */
export function useImageView(resetKey: string, initialFit: Fit = 'height'): ImageView {
  const [fit, setFitState] = useState<Fit>(initialFit)
  const [zoom, setZoom] = useState(1)
  const [rotation, setRotation] = useState<Rotation>(0)
  const [lens, setLens] = useState(false)

  // Reset while rendering when the form changes (React's recommended alternative to a reset effect).
  const [seenKey, setSeenKey] = useState(resetKey)
  if (seenKey !== resetKey) {
    setSeenKey(resetKey)
    setFitState(initialFit)
    setZoom(1)
    setRotation(0)
  }

  return {
    fit, zoom, rotation, lens,
    setFit: useCallback((f: Fit) => { setFitState(f); setZoom(1) }, []),
    zoomBy: useCallback((factor: number) => setZoom((z) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z * factor))), []),
    rotate: useCallback(() => { setRotation((r) => ((r + 90) % 360) as Rotation); setLens(false) }, []),
    toggleLens: useCallback(() => setLens((on) => !on), []),
  }
}
