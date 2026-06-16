import axios from 'axios'
import { apiClient } from './apiClient'
import type { PaymentMethod } from './paymentApi'

export type CreditNoteStatus = 'draft' | 'issued' | 'void'

export const CREDIT_NOTE_STATUS_LABELS: Record<CreditNoteStatus, string> = {
  draft: 'Brouillon',
  issued: 'Émis',
  void: 'Annulé',
}

export interface CreditNoteOut {
  id: number
  garage_id: number
  invoice_id: number
  doc_number: string | null
  status: CreditNoteStatus
  total_minor: number
  reason: string | null
  issued_at: string | null
  voided_at: string | null
  created_at: string
  updated_at: string
  created_by: number | null
}

export interface CreditNoteListResponse {
  items: CreditNoteOut[]
  total: number
  page: number
  page_size: number
}

export interface CreditNoteCreateInput {
  invoice_id: number
  total_minor: number
  reason?: string | null
}

export interface RefundOut {
  id: number
  garage_id: number
  payment_id: number
  credit_note_id: number | null
  amount_minor: number
  payment_method: PaymentMethod
  reason: string | null
  reference: string | null
  refunded_at: string
  created_at: string
  created_by: number | null
}

export interface RefundCreateInput {
  payment_id: number
  amount_minor: number
  payment_method?: PaymentMethod
  reason?: string | null
  reference?: string | null
  credit_note_id?: number | null
}

export const creditNoteApi = {
  list(params?: { page?: number; page_size?: number; invoice_id?: number }): Promise<CreditNoteListResponse> {
    return apiClient.get('/credit-notes', { params }).then(r => r.data)
  },

  get(id: number): Promise<CreditNoteOut> {
    return apiClient.get(`/credit-notes/${id}`).then(r => r.data)
  },

  create(input: CreditNoteCreateInput): Promise<CreditNoteOut> {
    return apiClient.post('/credit-notes', input).then(r => r.data)
  },

  issue(id: number): Promise<CreditNoteOut> {
    return apiClient.post(`/credit-notes/${id}/issue`).then(r => r.data)
  },

  void(id: number): Promise<CreditNoteOut> {
    return apiClient.post(`/credit-notes/${id}/void`).then(r => r.data)
  },

  getPdf(id: number): Promise<Blob> {
    const token = localStorage.getItem('access_token')
    return axios
      .get(`/api/v1/pdf/credit-notes/${id}`, {
        responseType: 'blob',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      .then(r => r.data)
  },

  createRefund(input: RefundCreateInput): Promise<RefundOut> {
    return apiClient.post('/refunds', input).then(r => r.data)
  },

  getRefund(refundId: number): Promise<RefundOut> {
    return apiClient.get(`/refunds/${refundId}`).then(r => r.data)
  },
}
