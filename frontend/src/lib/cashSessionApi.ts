import { apiClient } from './apiClient'
import type { PaymentMethod } from './paymentApi'

export type CashSessionStatus = 'open' | 'closed'

export interface PaymentMethodTally {
  payment_method: PaymentMethod
  count: number
  total_minor: number
}

export interface ZReportData {
  session_id: number
  garage_id: number
  opened_at: string
  closed_at: string | null
  opened_by_id: number | null
  closed_by_id: number | null
  tallies: PaymentMethodTally[]
  expected_total_cash: number | null
  counted_total_cash: number | null
  difference: number | null
  closing_reason: string | null
  total_all_methods: number
}

export interface CashSessionOut {
  id: number
  garage_id: number
  status: CashSessionStatus
  opened_at: string
  opened_by_id: number | null
  closed_at: string | null
  closed_by_id: number | null
  expected_total_cash: number | null
  counted_total_cash: number | null
  difference: number | null
  closing_reason: string | null
}

export interface CashSessionListResponse {
  items: CashSessionOut[]
  total: number
  page: number
  page_size: number
}

export interface CloseSessionInput {
  counted_total_cash: number
  closing_reason?: string | null
}

export const cashSessionApi = {
  open(): Promise<CashSessionOut> {
    return apiClient.post('/cash-sessions').then(r => r.data)
  },

  close(sessionId: number, input: CloseSessionInput): Promise<CashSessionOut> {
    return apiClient.post(`/cash-sessions/${sessionId}/close`, input).then(r => r.data)
  },

  getCurrent(): Promise<CashSessionOut | null> {
    return apiClient
      .get('/cash-sessions/current')
      .then(r => r.data)
      .catch(() => null)
  },

  list(params?: { page?: number; page_size?: number }): Promise<CashSessionListResponse> {
    return apiClient.get('/cash-sessions', { params }).then(r => r.data)
  },

  get(sessionId: number): Promise<CashSessionOut> {
    return apiClient.get(`/cash-sessions/${sessionId}`).then(r => r.data)
  },

  getZReport(sessionId: number): Promise<ZReportData> {
    return apiClient.get(`/cash-sessions/${sessionId}/z-report`).then(r => r.data)
  },

  getZReportPdfUrl(sessionId: number): string {
    return `/cash-sessions/${sessionId}/z-report/pdf`
  },
}
