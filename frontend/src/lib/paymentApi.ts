import { apiClient } from './apiClient'

export type PaymentMethod = 'cash' | 'card' | 'bank_transfer' | 'cheque' | 'other'

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  cash: 'Espèces',
  card: 'Carte bancaire',
  bank_transfer: 'Virement',
  cheque: 'Chèque',
  other: 'Autre',
}

export interface PaymentOut {
  id: number
  invoice_id: number
  garage_id: number
  amount_minor: number
  payment_method: PaymentMethod
  paid_at: string
  reference: string | null
  notes: string | null
  cash_session_id: number | null
  created_by: number | null
  created_at: string
}

export interface PaymentCreateInput {
  invoice_id: number
  amount_minor: number
  payment_method?: PaymentMethod
  paid_at?: string | null
  reference?: string | null
  notes?: string | null
}

export const paymentApi = {
  create(input: PaymentCreateInput): Promise<PaymentOut> {
    return apiClient.post('/payments', input).then(r => r.data)
  },

  listByInvoice(invoiceId: number): Promise<{ items: PaymentOut[] }> {
    return apiClient.get(`/payments/invoices/${invoiceId}`).then(r => r.data)
  },
}
