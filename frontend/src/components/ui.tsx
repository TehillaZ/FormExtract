import type { ReactNode } from 'react'
import type { Confidence } from '../api/types'

type IconName = 'search' | 'chevron-start' | 'chevron-end' | 'plus' | 'minus' | 'fit-height' | 'fit-width' | 'rotate' | 'expand' | 'close' | 'check' | 'lens' | 'list' | 'upload' | 'trash'

const PATHS: Record<IconName, ReactNode> = {
  search: <><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>,
  'chevron-start': <path d="M9 6l6 6-6 6" />,
  'chevron-end': <path d="M15 6l-6 6 6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  minus: <path d="M5 12h14" />,
  'fit-height': <path d="M12 3v18M8 7l4-4 4 4M8 17l4 4 4-4" />,
  'fit-width': <path d="M3 12h18M7 8l-4 4 4 4M17 8l4 4-4 4" />,
  rotate: <><path d="M20 12a8 8 0 1 1-2.6-5.9" /><path d="M20 4v5h-5" /></>,
  expand: <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  check: <path d="M5 12l5 5 9-10" />,
  lens: <><circle cx="10" cy="10" r="6" /><path d="M20 20l-5.5-5.5M10 7v6M7 10h6" /></>,
  list: <path d="M4 6h16M4 12h16M4 18h16" />,
  upload: <><path d="M12 16V4M7 9l5-5 5 5" /><path d="M4 20h16" /></>,
  trash: <path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13" />,
}

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {PATHS[name]}
    </svg>
  )
}

export function IconButton({ icon, label, onClick, active, disabled, size = 36 }: {
  icon: IconName; label: string; onClick?: () => void; active?: boolean; disabled?: boolean; size?: number
}) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} disabled={disabled}
      style={{ width: size, height: size }}
      className={`flex items-center justify-center rounded-lg border-0 ${active ? 'bg-accent-soft text-accent' : 'bg-transparent text-ink hover:bg-muted'}`}>
      <Icon name={icon} />
    </button>
  )
}

export function Tabs<T extends string>({ value, onChange, items }: {
  value: T; onChange: (v: T) => void; items: { id: T; label: string }[]
}) {
  return (
    <div className="flex rounded-[10px] bg-muted p-[3px]" role="tablist">
      {items.map((it) => (
        <button key={it.id} type="button" role="tab" aria-selected={value === it.id} onClick={() => onChange(it.id)}
          className={`rounded-lg border-0 px-4 py-[5px] text-sm ${value === it.id ? 'bg-surface font-semibold text-ink shadow-sm' : 'bg-transparent font-medium text-sub'}`}>
          {it.label}
        </button>
      ))}
    </div>
  )
}

/** "מאומת" for high confidence, a calm "לבדיקה קלה" for medium, an orange "לבדיקה" for low. */
export function ConfidenceBadge({ level }: { level: Confidence }) {
  if (level === 'high') return <span className="shrink-0 rounded-full bg-ok-soft px-2 py-[2px] text-[11px] font-bold text-ok-ink">מאומת</span>
  if (level === 'medium') return <span className="shrink-0 rounded-full border border-mid-line bg-mid-soft px-2 py-[1px] text-[11px] font-bold text-mid-ink">לבדיקה קלה</span>
  return <span className="shrink-0 rounded-full bg-warn px-2 py-[2px] text-[11px] font-bold text-white">לבדיקה</span>
}

/** Count pill used in lists: orange with the number of flagged fields, green check when clean. */
export function CountPill({ count }: { count: number }) {
  return count > 0
    ? <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-warn-soft px-1 text-[11px] font-bold text-warn-ink">{count}</span>
    : <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-ok-soft px-1 text-[11px] font-bold text-ok-ink">✓</span>
}
