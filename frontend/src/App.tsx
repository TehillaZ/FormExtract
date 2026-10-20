import { useState } from 'react'
import { useRecords } from './api/hooks'
import { AccuracyView } from './components/AccuracyView'
import { FormView } from './components/FormView'
import { RecordsView } from './components/RecordsView'
import { TableView } from './components/TableView'
import { Tabs } from './components/ui'
import { UploadView } from './components/UploadView'
import { flaggedCount } from './lib/fields'

type View = 'upload' | 'table' | 'form' | 'records' | 'accuracy'

export default function App() {
  const [view, setView] = useState<View>('table')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { data: records = [], isLoading, error } = useRecords()

  const open = (id: string) => { setSelectedId(id); setView('form') }
  const pending = records.filter((r) => r.status === 'pending')
  const flagged = pending.reduce((n, r) => n + flaggedCount(r), 0)

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-edge bg-surface px-6">
        <div className="flex items-center gap-5">
          <div className="text-[19px] font-bold text-accent">חילוץ טפסי התחייבות</div>
          <Tabs<View> value={view} onChange={setView} items={[
            { id: 'upload', label: 'העלאה' }, { id: 'table', label: 'טבלה' }, { id: 'form', label: 'טופס' },
            { id: 'records', label: 'רשומות' }, { id: 'accuracy', label: 'דוח דיוק' },
          ]} />
        </div>
        <div className="text-sm text-sub">
          {records.length} טפסים · {pending.length} ממתינים · {flagged} שדות לבדיקה
        </div>
      </header>

      <main className="flex min-h-0 flex-1 flex-col">
        {view === 'accuracy' ? (
          <AccuracyView />
        ) : error ? (
          <div role="alert" className="m-auto text-warn-ink">לא ניתן להתחבר לשרת. ודאי שהשרת פועל.</div>
        ) : isLoading ? (
          <div className="m-auto text-sub">טוען…</div>
        ) : view === 'upload' ? (
          <div className="min-h-0 flex-1 overflow-y-auto"><UploadView onReview={() => setView('table')} /></div>
        ) : view === 'table' ? (
          <TableView records={records} onOpen={open} />
        ) : view === 'records' ? (
          <RecordsView onOpen={open} />
        ) : (
          <FormView records={records} selectedId={selectedId} onSelect={setSelectedId} />
        )}
      </main>
    </div>
  )
}
