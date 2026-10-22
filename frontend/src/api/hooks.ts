import { type QueryClient, keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type RecordFilters, recordQuery } from '../lib/recordQuery'
import { api, apiWithTotal, jsonBody } from './client'
import type {
  ApproveCleanResult, CommitmentRecord, CorrectionGroup, DocumentStatus, EvaluationOverview, FieldChanges, PageStatus,
} from './types'

const RECORDS = ['records'] as const
const RECORDS_PAGE = ['records-page'] as const

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

export function useUpload() {
  return useMutation({
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ['document'] }),
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
