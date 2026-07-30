import { apiClient } from './apiClient'
import type { PaymentMethod } from './paymentApi'

export type CashSessionStatus = 'open' | 'closed'

export interface PaymentMethodTally {
  payment_method: PaymentMethod
  count: number
  total_minor: number
}

export interface SessionPaymentOut {
  id: number
  paid_at: string
  amount_minor: number
  payment_method: PaymentMethod
  reference: string | null
  notes: string | null
  invoice_id: number
  invoice_number: string | null
  customer_name: string | null
  created_by_name: string | null
}

export type SessionTransactionKind = 'payment' | 'refund' | 'advance' | 'supplier_payment'
export type SessionTransactionDirection = 'in' | 'out'

export interface SessionTransactionOut {
  kind: SessionTransactionKind
  direction: SessionTransactionDirection
  id: number
  occurred_at: string
  amount_minor: number
  payment_method: PaymentMethod
  reference: string | null
  label: string
  customer_name: string | null
  invoice_id: number | null
  invoice_number: string | null
  invoice_public_id: string | null
  credit_note_id: number | null
  customer_public_id: string | null
  supplier_name: string | null
  supplier_invoice_number: string | null
  created_by_name: string | null
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
  opening_float: number
  expected_total_cash: number | null
  counted_total_cash: number | null
  difference: number | null
  closing_reason: string | null
  /** opening_float + cash payments so far (live for open sessions). */
  expected_cash_so_far: number | null
}

export interface OpenSessionInput {
  opening_float?: number
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
  open(input?: OpenSessionInput): Promise<CashSessionOut> {
    return apiClient.post('/cash-sessions', input ?? {}).then(r => r.data)
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

  listPayments(sessionId: number): Promise<SessionPaymentOut[]> {
    return apiClient.get(`/cash-sessions/${sessionId}/payments`).then(r => r.data)
  },

  listTransactions(sessionId: number): Promise<SessionTransactionOut[]> {
    return apiClient.get(`/cash-sessions/${sessionId}/transactions`).then(r => r.data)
  },
}
