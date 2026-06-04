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

  reject: (extractionId: string) =>
    apiClient
      .post<OcrExtractionOut>(`/ocr/${extractionId}/reject`)
      .then((r) => r.data),
}
