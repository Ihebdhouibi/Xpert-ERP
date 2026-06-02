import { apiClient } from './apiClient'

export interface AccountingExportOut {
  public_id: string
  garage_id: number
  period_start: string
  period_end: string
  format: string
  status: string
  file_storage_key: string | null
  exported_by: number | null
  exported_at: string | null
  record_counts: Record<string, number> | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface AccountingExportListResponse {
  items: AccountingExportOut[]
  total: number
  page: number
  page_size: number
}

export interface AccountingExportPreviewResponse {
  already_exported_invoices: number
  already_exported_payments: number
  already_exported_supplier_invoices: number
  pending_invoices: number
  pending_payments: number
  pending_supplier_invoices: number
  warning: string | null
}

export interface AccountingExportCreateInput {
  period_start: string
  period_end: string
  format?: string | null
}

export const accountingExportApi = {
  preview(periodStart: string, periodEnd: string): Promise<AccountingExportPreviewResponse> {
    return apiClient
      .get('/accounting-exports/preview', {
        params: { period_start: periodStart, period_end: periodEnd },
      })
      .then(r => r.data)
  },

  create(input: AccountingExportCreateInput): Promise<AccountingExportOut> {
    return apiClient.post('/accounting-exports', input).then(r => r.data)
  },

  list(params?: { page?: number; page_size?: number }): Promise<AccountingExportListResponse> {
    return apiClient.get('/accounting-exports', { params }).then(r => r.data)
  },

  get(publicId: string): Promise<AccountingExportOut> {
    return apiClient.get(`/accounting-exports/${publicId}`).then(r => r.data)
  },

  getDownloadUrl(publicId: string): Promise<{ url: string }> {
    return apiClient.get(`/accounting-exports/${publicId}/download`).then(r => r.data)
  },
}
