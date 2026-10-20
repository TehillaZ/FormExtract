import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, jsonBody } from './client'
import type { ApproveCleanResult, CommitmentRecord, DocumentStatus, FieldChanges, PageStatus } from './types'

const RECORDS = ['records'] as const

export function useRecords() {
  return useQuery({
    queryKey: RECORDS,
    queryFn: () => api<CommitmentRecord[]>('/records?limit=1000'),
  })
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
  return (rec: CommitmentRecord) =>
    qc.setQueryData<CommitmentRecord[]>(RECORDS, (old) => old?.map((r) => (r.id === rec.id ? rec : r)))
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
    onSuccess: () => qc.invalidateQueries({ queryKey: RECORDS }),
  })
}
