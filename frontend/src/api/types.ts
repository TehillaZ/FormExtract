export type Confidence = 'high' | 'medium' | 'low'

export interface Field {
  value: string | null
  raw_text: string | null
  confidence: Confidence
  source: string | null
  reasons: string[]
}

export interface Correction {
  field: string
  old_value: string | null
  new_value: string | null
  at: string
}

export interface CommitmentRecord {
  id: string
  document_id: string | null
  page_numbers: number[]
  page_ids: string[]
  template: string | null
  provider: string | null
  first_name: Field
  last_name: Field
  id_number: Field
  central_numbers: Field[]
  received_date: Field
  sender: Field
  commitment_numbers: Field[]
  status: 'pending' | 'approved'
  corrections: Correction[]
  duplicate_warnings: string[]
}

export interface PageStatus {
  id: string
  page_number: number
  status: 'pending' | 'processing' | 'ready' | 'error'
  error: string | null
  record_id: string | null
}

export interface DocumentStatus {
  id: string
  filename: string
  duplicate: boolean
  done: boolean
  pages: PageStatus[]
}

export interface ApproveCleanResult {
  approved: string[]
  skipped_duplicates: string[]
}

/** What a PATCH accepts: a text per scalar field, a list per list field. */
export type FieldChanges = Record<string, string | string[] | null>
