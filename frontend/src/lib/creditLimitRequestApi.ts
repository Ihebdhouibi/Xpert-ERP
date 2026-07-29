import { apiClient } from './apiClient'

export interface CreditLimitChangeRequestOut {
  id: number
  customer_id: number
  customer_name: string | null
  requested_by_id: number
  current_credit_limit_minor: number
  requested_credit_limit_minor: number
  requested_credit_currency: string
  reason: string
  status: 'pending' | 'approved' | 'rejected'
  approved_by_id: number | null
  rejection_reason: string | null
  created_at: string
}

export const creditLimitRequestApi = {
  create: (
    customer_public_id: string,
    credit_limit_minor: number,
    credit_currency: string,
    reason: string,
  ) =>
    apiClient
      .post<CreditLimitChangeRequestOut>('/credit-limit-requests', {
        customer_public_id,
        credit_limit_minor,
        credit_currency,
        reason,
      })
      .then(r => r.data),

  list: (params: { status?: string; customer_public_id?: string } = {}) =>
    apiClient
      .get<CreditLimitChangeRequestOut[]>('/credit-limit-requests', { params })
      .then(r => r.data),

  getPendingForCustomer: async (customerPublicId: string): Promise<CreditLimitChangeRequestOut | null> => {
    const items = await apiClient
      .get<CreditLimitChangeRequestOut[]>('/credit-limit-requests', {
        params: { status: 'pending', customer_public_id: customerPublicId },
      })
      .then(r => r.data)
    return items[0] ?? null
  },

  approve: (id: number) =>
    apiClient.post<CreditLimitChangeRequestOut>(`/credit-limit-requests/${id}/approve`).then(r => r.data),

  reject: (id: number, reason?: string) =>
    apiClient
      .post<CreditLimitChangeRequestOut>(`/credit-limit-requests/${id}/reject`, { reason: reason ?? null })
      .then(r => r.data),
}
