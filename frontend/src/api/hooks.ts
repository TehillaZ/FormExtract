import { useEffect, useRef } from 'react'
import { type QueryClient, keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type RecordFilters, recordQuery } from '../lib/recordQuery'
import { ApiError, api, apiWithTotal, jsonBody } from './client'
import type {
  ActivePage, ApproveCleanResult, CommitmentRecord, CorrectionGroup, DocumentStatus, EvaluationOverview, FieldChanges, PageStatus, Role,
} from './types'

const RECORDS = ['records'] as const
const RECORDS_PAGE = ['records-page'] as const
const ACTIVE = ['active-pages'] as const

/** The records screen keeps its own pages of results; any change to a record makes them stale. */
const refreshRecordsScreen = (qc: QueryClient) => qc.invalidateQueries({ queryKey: RECORDS_PAGE })

export function useRecords() {
  return useQuery({
    queryKey: RECORDS,
    queryFn: () => api<CommitmentRecord[]>('/records?limit=1000'),
  })
}

/** One page of the records screen: filtered on the server, with the total number of matches. */
export function useRecordsPage(filters: RecordFilters, page: number, pageSize: number) {
  return useQuery({
    queryKey: [...RECORDS_PAGE, filters, page, pageSize],
    queryFn: () => apiWithTotal<CommitmentRecord[]>(`/records?${recordQuery(filters, { limit: pageSize, offset: page * pageSize })}`),
    placeholderData: keepPreviousData,   // keep showing the old page while the next one loads
  })
}

/** The closed sender list, for the filter and the correction dropdown. It never changes while the app runs. */
export function useSenders() {
  return useQuery({ queryKey: ['senders'], queryFn: () => api<string[]>('/senders'), staleTime: Infinity })
}

/** The saved accuracy reports, and how much verified data exists. */
export function useEvaluation() {
  return useQuery({ queryKey: ['evaluation'], queryFn: () => api<EvaluationOverview>('/evaluation') })
}

/** Polls every 2.5s until every page of the document is ready or failed (ADR-005). */
export function useDocument(id: string) {
  return useQuery({
    queryKey: ['document', id],
    queryFn: () => api<DocumentStatus>(`/documents/${id}`),
    refetchInterval: (q) => (q.state.data?.done ? false : 2500),
  })
}

/** Pages that are not records yet. Polls while any is being read, and when one finishes its record is fetched. */
export function useActivePages() {
  const qc = useQueryClient()
  const query = useQuery({
    queryKey: ACTIVE,
    queryFn: () => api<ActivePage[]>('/pages/active'),
    refetchInterval: (q) => (q.state.data?.some((p) => p.status !== 'error') ? 2000 : false),
  })
  const before = useRef<string[]>([])
  useEffect(() => {
    if (!query.data) return
    const now = query.data.map((p) => p.id)
    if (before.current.some((id) => !now.includes(id))) {   // a page left the list: it became a record, or was removed
      void qc.invalidateQueries({ queryKey: RECORDS })
      void refreshRecordsScreen(qc)
    }
    before.current = now
  }, [query.data, qc])
  return query
}

export function useUpload() {
  const qc = useQueryClient()
  return useMutation({
    onSuccess: async (created) => {
      // The new pages are listed at once, before the server is asked. They are in the list when it is polled, so
      // we notice when they leave it.
      const fresh: ActivePage[] = created.filter((d) => !d.duplicate).flatMap((d) => d.pages
        .filter((p) => p.status !== 'ready' && p.status !== 'error' && !p.record_id)
        .map((p) => ({ id: p.id, document_id: d.id, filename: d.filename, page_number: p.page_number, status: p.status as ActivePage['status'], error: null })))
      qc.setQueryData<ActivePage[]>(ACTIVE, (old = []) => [...old, ...fresh.filter((f) => !old.some((o) => o.id === f.id))])
      await qc.invalidateQueries({ queryKey: ACTIVE })
      // a page can be read before the list is first asked (a small file, a fast model): then it never shows up
      // there as leaving, so fetch the records once the list has been refreshed
      await qc.invalidateQueries({ queryKey: RECORDS })
      await refreshRecordsScreen(qc)
    },
    mutationFn: (files: File[]) => {
      const form = new FormData()
      files.forEach((f) => form.append('files', f))
      return api<DocumentStatus[]>('/documents', { method: 'POST', body: form })
    },
  })
}

export function useReprocess() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (pageId: string) => api<PageStatus>(`/pages/${pageId}/reprocess`, { method: 'POST' }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['document'] }); void qc.invalidateQueries({ queryKey: ACTIVE }) },
  })
}

/** A changed record replaces its old copy in the list, so every screen updates at once. */
function useReplaceRecord() {
  const qc = useQueryClient()
  return (rec: CommitmentRecord) => {
    qc.setQueryData<CommitmentRecord[]>(RECORDS, (old) => old?.map((r) => (r.id === rec.id ? rec : r)))
    void refreshRecordsScreen(qc)
  }
}

export function usePatchRecord(id: string) {
  const replace = useReplaceRecord()
  return useMutation({
    mutationFn: (changes: FieldChanges) => api<CommitmentRecord>(`/records/${id}`, jsonBody('PATCH', changes)),
    onSuccess: replace,
  })
}

export function useApproveRecord() {
  const replace = useReplaceRecord()
  return useMutation({
    mutationFn: (id: string) => api<CommitmentRecord>(`/records/${id}/approve`, { method: 'POST' }),
    onSuccess: replace,
  })
}

export function useApproveClean() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<ApproveCleanResult>('/records/approve-clean', { method: 'POST' }),
    onSuccess: () => Promise.all([qc.invalidateQueries({ queryKey: RECORDS }), refreshRecordsScreen(qc)]),
  })
}

/** What people had to fix, grouped by field, sender and form type. */
export function useCorrectionSummary() {
  return useQuery({ queryKey: ['corrections-summary'], queryFn: () => api<CorrectionGroup[]>('/corrections/summary') })
}

/** Who is logged in: the role, or null when nobody is (the server answers 401). */
export function useSession() {
  return useQuery({
    queryKey: ['session'],
    queryFn: async () => {
      try {
        return (await api<{ role: Role }>('/auth/me')).role
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
    staleTime: Infinity,
    retry: false,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (password: string) => api<{ role: Role }>('/auth/login', jsonBody('POST', { password })),
    onSuccess: ({ role }) => qc.setQueryData(['session'], role),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<void>('/auth/logout', { method: 'POST' }),
    onSuccess: () => {
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== 'session' })   // nothing of the last person's data stays in memory
      qc.setQueryData(['session'], null)
    },
  })
}
