import { apiClient } from './apiClient'
import type { PaymentMethod } from './paymentApi'

export interface AdvancePaymentOut {
  id: number
  garage_id: number
  customer_id: number
  repair_order_id: number | null
  amount_minor: number
  payment_method: PaymentMethod
  paid_at: string
  reference: string | null
  notes: string | null
  applied_to_invoice_id: number | null
  applied_at: string | null
  applied_amount_minor: number | null
  created_by: number | null
  created_at: string
}

export interface AdvancePaymentListResponse {
  items: AdvancePaymentOut[]
  total: number
}

export interface AdvancePaymentCreateInput {
  customer_id: number
  repair_order_id?: number | null
  amount_minor: number
  payment_method?: PaymentMethod
  paid_at?: string | null
  reference?: string | null
  notes?: string | null
}

export const advancePaymentApi = {
  create(input: AdvancePaymentCreateInput): Promise<AdvancePaymentOut> {
    return apiClient.post('/advance-payments', input).then(r => r.data)
  },

  listByCustomer(customerId: number): Promise<AdvancePaymentListResponse> {
    return apiClient.get(`/advance-payments/customers/${customerId}`).then(r => r.data)
  },
}
