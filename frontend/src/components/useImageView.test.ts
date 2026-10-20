import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useImageView } from './useImageView'

const setup = (key = 'a', fit?: 'height' | 'width' | 'actual') => renderHook(({ k }) => useImageView(k, fit), { initialProps: { k: key } })

describe('useImageView', () => {
  it('starts fitted to the height, unzoomed, upright, without the lens', () => {
    const { result } = setup()
    expect(result.current).toMatchObject({ fit: 'height', zoom: 1, rotation: 0, lens: false })
  })

  it('can start fitted to the width', () => {
    expect(setup('a', 'width').result.current.fit).toBe('width')
  })

  it('zooming multiplies and is limited at both ends', () => {
    const { result } = setup()
    act(() => result.current.zoomBy(1.25))
    act(() => result.current.zoomBy(1.25))
    expect(result.current.zoom).toBeCloseTo(1.5625)
    for (let i = 0; i < 20; i++) act(() => result.current.zoomBy(2))
    expect(result.current.zoom).toBe(8)
    for (let i = 0; i < 20; i++) act(() => result.current.zoomBy(0.5))
    expect(result.current.zoom).toBe(0.5)
  })

  it('choosing a fit mode also resets the zoom', () => {
    const { result } = setup()
    act(() => result.current.zoomBy(2))
    act(() => result.current.setFit('width'))
    expect(result.current).toMatchObject({ fit: 'width', zoom: 1 })
  })

  it('rotating goes round in quarter turns', () => {
    const { result } = setup()
    const seen: number[] = []
    for (let i = 0; i < 4; i++) { act(() => result.current.rotate()); seen.push(result.current.rotation) }
    expect(seen).toEqual([90, 180, 270, 0])
  })

  it('the lens toggles, and rotating turns it off (it only works on an upright image)', () => {
    const { result } = setup()
    act(() => result.current.toggleLens())
    expect(result.current.lens).toBe(true)
    act(() => result.current.rotate())
    expect(result.current.lens).toBe(false)
  })

  it('showing another form starts fresh, but the lens choice stays', () => {
    const { result, rerender } = setup('a')
    act(() => { result.current.zoomBy(2); result.current.rotate(); result.current.setFit('actual'); result.current.zoomBy(3) })
    rerender({ k: 'b' })
    expect(result.current).toMatchObject({ fit: 'height', zoom: 1, rotation: 0 })
  })

  it('keeps the same state when re-rendered for the same form', () => {
    const { result, rerender } = setup('a')
    act(() => result.current.zoomBy(2))
    rerender({ k: 'a' })
    expect(result.current.zoom).toBe(2)
  })
})
