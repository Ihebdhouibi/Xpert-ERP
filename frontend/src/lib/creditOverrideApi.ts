import { apiClient } from './apiClient'

export interface CreditLimitExceededDetail {
  error_code: 'credit_limit_exceeded'
  customer_public_id: string | null
  doc_type: 'invoice' | 'delivery_note'
  outstanding: number
  limit: number
  additional: number
  message: string
}

export interface OverrideRequestOut {
  id: number
  customer_id: number
  customer_name: string | null
  requested_by_id: number
  doc_type: string
  status: 'pending' | 'approved' | 'rejected'
  approved_by_id: number | null
  expires_at: string | null
  rejection_reason: string | null
  created_at: string
}

export const creditOverrideApi = {
  request: (
    customer_public_id: string,
    doc_type: 'invoice' | 'delivery_note',
    source_document_public_id: string,
  ) =>
    apiClient
      .post<OverrideRequestOut>('/credit-override-requests', {
        customer_public_id,
        doc_type,
        source_document_public_id,
      })
      .then(r => r.data),

  list: (status?: string) =>
    apiClient
      .get<OverrideRequestOut[]>('/credit-override-requests', { params: status ? { status } : undefined })
      .then(r => r.data),

  approve: (id: number) =>
    apiClient.post<OverrideRequestOut>(`/credit-override-requests/${id}/approve`).then(r => r.data),

  reject: (id: number, reason?: string) =>
    apiClient
      .post<OverrideRequestOut>(`/credit-override-requests/${id}/reject`, { reason: reason ?? null })
      .then(r => r.data),
}

/** Extract a CreditLimitExceededDetail from an axios error, or null. */
export function parseCreditLimitError(err: unknown): CreditLimitExceededDetail | null {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (detail && typeof detail === 'object' && (detail as { error_code?: string }).error_code === 'credit_limit_exceeded') {
    return detail as CreditLimitExceededDetail
  }
  return null
}

export function formatMinorEur(minor: number): string {
  return (minor / 100).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €'
}
