import { useEffect, useRef } from 'react'

/** True when the keystroke is going into something the user is typing in. */
export function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  return !!el && (el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName))
}

/**
 * Keyboard shortcuts, keyed by `event.code` (the physical key). Unlike `event.key`, the code does not change with
 * the keyboard layout, so "N" is the same key on a Hebrew keyboard.
 *
 * A shortcut is ignored while typing, with Ctrl, Alt or Meta held (Ctrl+A must still mean "select all"), and while
 * `enabled` is false. A key with no handler is left alone.
 */
export function useShortcuts(handlers: Record<string, () => void>, enabled = true) {
  const latest = useRef(handlers)
  useEffect(() => { latest.current = handlers })   // always call the handlers of the latest render

  useEffect(() => {
    if (!enabled) return
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing || isTyping(e.target)) return
      const handler = latest.current[e.code]
      if (!handler) return
      e.preventDefault()
      handler()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [enabled])
}
