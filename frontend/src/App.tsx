import { useState } from 'react'
import { useActivePages, useLogout, useRecords, useSession } from './api/hooks'
import type { Role } from './api/types'
import { AccuracyView } from './components/AccuracyView'
import { CorrectionsView } from './components/CorrectionsView'
import { FormView } from './components/FormView'
import { LoginView } from './components/LoginView'
import { RecordsView } from './components/RecordsView'
import { TableView } from './components/TableView'
import { Tabs } from './components/ui'
import { UploadView } from './components/UploadView'
import { flaggedCount } from './lib/fields'

type View = 'upload' | 'table' | 'form' | 'records' | 'accuracy' | 'corrections'

/** What each role may open. A developer also sees the user's screens. */
const TABS: { id: View; label: string; developerOnly?: boolean }[] = [
  { id: 'upload', label: 'העלאה' }, { id: 'table', label: 'טבלה' }, { id: 'form', label: 'טופס' }, { id: 'records', label: 'רשומות' },
  { id: 'accuracy', label: 'דוח דיוק', developerOnly: true }, { id: 'corrections', label: 'טעויות חוזרות', developerOnly: true },
]

export default function App() {
  const { data: role, isLoading, error } = useSession()
  if (role) return <Workspace role={role} />
  return (
    <div className="flex h-full">
      {isLoading ? <div className="m-auto text-sub">טוען…</div>
        : error ? <div role="alert" className="m-auto text-warn-ink">לא ניתן להתחבר לשרת. ודאי שהשרת פועל.</div>
        : <LoginView />}
    </div>
  )
}

function Workspace({ role }: { role: Role }) {
  const logout = useLogout()
  const [view, setView] = useState<View>('table')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { data: records = [], isLoading, error } = useRecords()
  const { data: unread = [] } = useActivePages()

  const open = (id: string) => { setSelectedId(id); setView('form') }
  const pending = records.filter((r) => r.status === 'pending')
  const flagged = pending.reduce((n, r) => n + flaggedCount(r), 0)

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-edge bg-surface px-6">
        <div className="flex items-center gap-5">
          <div className="text-[19px] font-bold text-accent">חילוץ טפסי התחייבות</div>
          <Tabs<View> value={view} onChange={setView} items={TABS.filter((t) => role === 'developer' || !t.developerOnly)} />
        </div>
        <div className="flex items-center gap-4 text-sm text-sub">
          <span>{records.length} טפסים · {pending.length} ממתינים · {flagged} שדות לבדיקה</span>
          <button type="button" onClick={() => logout.mutate()} className="rounded-lg border border-line bg-surface px-3 py-1 text-sm text-ink">
            יציאה
          </button>
        </div>
      </header>

      <main className="flex min-h-0 flex-1 flex-col">
        {view === 'accuracy' ? (
          <AccuracyView />
        ) : view === 'corrections' ? (
          <CorrectionsView />
        ) : error ? (
          <div role="alert" className="m-auto text-warn-ink">לא ניתן להתחבר לשרת. ודאי שהשרת פועל.</div>
        ) : isLoading ? (
          <div className="m-auto text-sub">טוען…</div>
        ) : view === 'upload' ? (
          <div className="min-h-0 flex-1 overflow-y-auto"><UploadView onReview={() => setView('table')} onUploaded={open} /></div>
        ) : view === 'table' ? (
          <TableView records={records} onOpen={open} />
        ) : view === 'records' ? (
          <RecordsView onOpen={open} />
        ) : (
          <FormView records={records} pending={unread} selectedId={selectedId} onSelect={setSelectedId} />
        )}
      </main>
    </div>
  )
}
