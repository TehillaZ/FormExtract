import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { isTyping, useShortcuts } from './useShortcuts'

/** Dispatches a keydown from `target` (it bubbles up to the window, as a real keystroke does). */
function press(code: string, init: KeyboardEventInit = {}, target: EventTarget = document.body) {
  const event = new KeyboardEvent('keydown', { code, bubbles: true, cancelable: true, ...init })
  target.dispatchEvent(event)
  return event
}

const mount = (el: HTMLElement) => { document.body.appendChild(el); return el }
afterEach(() => { document.body.innerHTML = '' })

describe('useShortcuts', () => {
  it('runs the handler for the key and stops the browser from also acting on it', () => {
    const next = vi.fn()
    renderHook(() => useShortcuts({ KeyN: next }))
    const event = press('KeyN')
    expect(next).toHaveBeenCalledTimes(1)
    expect(event.defaultPrevented).toBe(true)
  })

  it('goes by the physical key, so it works on a Hebrew keyboard', () => {
    const next = vi.fn()
    renderHook(() => useShortcuts({ KeyN: next }))
    press('KeyN', { key: 'ט' })          // the same key, typing a Hebrew letter
    expect(next).toHaveBeenCalledTimes(1)
  })

  it('does not go by the letter typed: another key that happens to type "n" does nothing', () => {
    const next = vi.fn()
    renderHook(() => useShortcuts({ KeyN: next }))
    press('KeyM', { key: 'n' })
    expect(next).not.toHaveBeenCalled()
  })

  it('leaves keys it has no handler for alone, so the browser still acts on them', () => {
    renderHook(() => useShortcuts({ KeyN: vi.fn() }))
    expect(press('KeyQ').defaultPrevented).toBe(false)
  })

  describe('never while the user is typing', () => {
    it.each([
      ['a text box', () => document.createElement('input')],
      ['a text area', () => document.createElement('textarea')],
      ['a drop-down', () => document.createElement('select')],
    ])('%s', (_, make) => {
      const next = vi.fn()
      renderHook(() => useShortcuts({ KeyN: next }))
      const field = mount(make())
      const event = press('KeyN', {}, field)
      expect(next).not.toHaveBeenCalled()
      expect(event.defaultPrevented).toBe(false)         // the letter still reaches the field
    })

    it('an editable region', () => {
      const next = vi.fn()
      renderHook(() => useShortcuts({ KeyN: next }))
      const region = document.createElement('div')
      Object.defineProperty(region, 'isContentEditable', { value: true })
      press('KeyN', {}, mount(region))
      expect(next).not.toHaveBeenCalled()
    })

    it('while text is being composed (an input method)', () => {
      const next = vi.fn()
      renderHook(() => useShortcuts({ KeyN: next }))
      press('KeyN', { isComposing: true })
      expect(next).not.toHaveBeenCalled()
    })
  })

  describe('modifier keys', () => {
    it.each([['Ctrl', { ctrlKey: true }], ['Alt', { altKey: true }], ['Meta', { metaKey: true }]])(
      '%s turns a shortcut into an ordinary browser command (Ctrl+A is still "select all")',
      (_, init) => {
        const approve = vi.fn()
        renderHook(() => useShortcuts({ KeyA: approve }))
        const event = press('KeyA', init)
        expect(approve).not.toHaveBeenCalled()
        expect(event.defaultPrevented).toBe(false)
      })

    it('Shift does not get in the way (Caps Lock and capital letters)', () => {
      const next = vi.fn()
      renderHook(() => useShortcuts({ KeyN: next }))
      press('KeyN', { shiftKey: true })
      expect(next).toHaveBeenCalledTimes(1)
    })
  })

  describe('turning it off and on', () => {
    it('does nothing while disabled, and works again once enabled', () => {
      const next = vi.fn()
      const { rerender } = renderHook(({ on }) => useShortcuts({ KeyN: next }, on), { initialProps: { on: false } })
      press('KeyN')
      expect(next).not.toHaveBeenCalled()
      rerender({ on: true })
      press('KeyN')
      expect(next).toHaveBeenCalledTimes(1)
    })

    it('stops listening when the screen goes away', () => {
      const next = vi.fn()
      const { unmount } = renderHook(() => useShortcuts({ KeyN: next }))
      unmount()
      press('KeyN')
      expect(next).not.toHaveBeenCalled()
    })
  })

  it('always calls the handlers of the latest render, not the ones it first saw', () => {
    const first = vi.fn()
    const second = vi.fn()
    const { rerender } = renderHook(({ handler }) => useShortcuts({ KeyN: handler }), { initialProps: { handler: first } })
    rerender({ handler: second })
    press('KeyN')
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledTimes(1)
  })
})

describe('isTyping', () => {
  it('knows where typing happens', () => {
    expect(isTyping(document.createElement('input'))).toBe(true)
    expect(isTyping(document.createElement('button'))).toBe(false)
    expect(isTyping(document.body)).toBe(false)
    expect(isTyping(null)).toBe(false)
  })
})
