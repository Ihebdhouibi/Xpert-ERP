import { apiClient } from './apiClient'

export type CustomerType = 'individual' | 'company'
export type CustomerStatus = 'active' | 'inactive' | 'blocked'
export type ContactChannel = 'phone' | 'email' | 'whatsapp'

export interface Address {
  street?: string | null
  city?: string | null
  postal_code?: string | null
  country?: string | null
}

export interface CustomerContact {
  id?: number
  channel: ContactChannel
  value: string
  label?: string | null
  is_primary?: boolean
}

export interface CustomerSummary {
  id: string
  int_id: number
  garage_id: number
  type: CustomerType
  full_name: string
  company_name: string | null
  email: string | null
  phone_e164: string | null
  status: CustomerStatus
  segment: string | null
  credit_limit_minor: number
  credit_currency: string | null
  outstanding_minor: number
  last_visit_at: string | null
  created_at: string
}

export interface CustomerDetail extends CustomerSummary {
  fiscal_id: string | null
  address: Address | null
  loyalty_points: number
  notes: string | null
  version: number
  updated_at: string
  contacts: CustomerContact[]
}

export interface CustomerListResponse {
  items: CustomerSummary[]
  total: number
  page: number
  page_size: number
}

export interface CustomerCreateInput {
  type: CustomerType
  full_name: string
  company_name?: string | null
  fiscal_id?: string | null
  email?: string | null
  phone_e164?: string | null
  address?: Address | null
  segment?: string | null
  credit_limit_minor?: number
  credit_currency?: string | null
  notes?: string | null
  contacts?: CustomerContact[]
}

export interface CustomerUpdateInput {
  version: number
  full_name?: string
  company_name?: string | null
  fiscal_id?: string | null
  email?: string | null
  phone_e164?: string | null
  address?: Address | null
  segment?: string | null
  status?: CustomerStatus
  notes?: string | null
}

export type MergeMatchReason =
  | 'phone_and_fiscal_id'
  | 'email_and_fiscal_id'
  | 'fiscal_id_only'

export interface MergePromptResponse {
  code: 'duplicate_customer'
  match_reason: MergeMatchReason
  existing: CustomerSummary
}

export interface ListParams {
  q?: string
  status?: CustomerStatus
  type?: CustomerType
  segment?: string
  include_deleted?: boolean
  page?: number
  page_size?: number
}

export const customerApi = {
  list: async (params: ListParams = {}): Promise<CustomerListResponse> => {
    const { data } = await apiClient.get<CustomerListResponse>('/customers', {
      params,
    })
    return data
  },

  get: async (publicId: string): Promise<CustomerDetail> => {
    const { data } = await apiClient.get<CustomerDetail>(
      `/customers/${publicId}`,
    )
    return data
  },

  create: async (input: CustomerCreateInput): Promise<CustomerDetail> => {
    const { data } = await apiClient.post<CustomerDetail>('/customers', input)
    return data
  },

  update: async (
    publicId: string,
    input: CustomerUpdateInput,
  ): Promise<CustomerDetail> => {
    const { data } = await apiClient.patch<CustomerDetail>(
      `/customers/${publicId}`,
      input,
    )
    return data
  },

  remove: async (publicId: string, reason?: string): Promise<void> => {
    await apiClient.delete(`/customers/${publicId}`, {
      params: reason ? { reason } : undefined,
    })
  },

  restore: async (publicId: string): Promise<CustomerDetail> => {
    const { data } = await apiClient.post<CustomerDetail>(
      `/customers/${publicId}/restore`,
    )
    return data
  },
}
