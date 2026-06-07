/**
 * API client for the /ocr endpoints (OCR pipeline).
 */
import { apiClient } from './apiClient'

export type OcrStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'needs_review'

export interface OcrExtractionOut {
  id: string
  document_id: number
  document_public_id: string | null
  document_category: string | null
  engine_version: string
  status: OcrStatus
  raw_text: string | null
  structured_fields: Record<string, string> | null
  confidence_scores: Record<string, number> | null
  created_at: string
  processed_at: string | null
  reviewed_by: number | null
  reviewed_at: string | null
}

export interface ConfirmFieldsRequest {
  confirmed_fields: Record<string, string>
}

export interface IngestLine {
  description: string | null
  quantity: string | null
  unit_price: string | null
  line_total: string | null
}

export interface InvoicePrefill {
  number: string | null
  invoice_date: string | null
  due_date: string | null
  party: string | null
  total_ht_cents: number | null
  total_ttc_cents: number | null
  suggested_lines: IngestLine[]
}

export type IngestTarget =
  | 'vehicle'
  | 'customer'
  | 'supplier_invoice'
  | 'invoice'
  | 'none'

export interface IngestionResult {
  target: IngestTarget
  prefill: InvoicePrefill | null
  created_id: string | null
}

export const ocrApi = {
  enqueue: (documentPublicId: string) =>
    apiClient
      .post<OcrExtractionOut>(`/ocr/enqueue/${documentPublicId}`)
      .then((r) => r.data),

  get: (extractionId: string) =>
    apiClient
      .get<OcrExtractionOut>(`/ocr/${extractionId}`)
      .then((r) => r.data),

  confirm: (extractionId: string, body: ConfirmFieldsRequest) =>
    apiClient
      .post<OcrExtractionOut>(`/ocr/${extractionId}/confirm`, body)
      .then((r) => r.data),

  ingest: (extractionId: string, body: ConfirmFieldsRequest) =>
    apiClient
      .post<IngestionResult>(`/ocr/${extractionId}/ingest`, body)
      .then((r) => r.data),

  reject: (extractionId: string) =>
    apiClient
      .post<OcrExtractionOut>(`/ocr/${extractionId}/reject`)
      .then((r) => r.data),
}
