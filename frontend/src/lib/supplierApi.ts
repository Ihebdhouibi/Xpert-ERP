import { apiClient } from './apiClient'

export type SupplierStatus = 'active' | 'inactive'

export interface Supplier {
  id: string
  name: string
  email: string | null
  phone: string | null
  address: string | null
  payment_terms_days: number | null
  average_delivery_days: number | null
  reliability_score: number | null
  status: SupplierStatus
  version: number
  created_at: string
  updated_at: string
}

export interface SupplierListResponse {
  items: Supplier[]
  total: number
  page: number
  page_size: number
}

export interface SupplierCreatePayload {
  name: string
  email?: string
  phone?: string
  address?: string
  payment_terms_days?: number
  average_delivery_days?: number
}

export interface SupplierUpdatePayload extends Partial<SupplierCreatePayload> {
  version: number
  status?: SupplierStatus
}

export interface PriceEntry {
  id: number
  part_public_id: string
  part_name: string
  part_sku: string
  unit_price_minor: number
  currency: string
  effective_from: string
  effective_to: string | null
  created_at: string
}

export interface PriceAddPayload {
  part_public_id: string
  unit_price_minor: number
  currency: string
  effective_from: string
}

export interface PriceComparisonItem {
  supplier_public_id: string
  supplier_name: string
  average_delivery_days: number | null
  reliability_score: number | null
  unit_price_minor: number
  currency: string
  effective_from: string
  effective_to: string | null
}

export const STATUS_LABELS: Record<SupplierStatus, string> = {
  active: 'Actif',
  inactive: 'Inactif',
}

export const supplierApi = {
  list(params?: {
    search?: string
    status?: SupplierStatus
    page?: number
    page_size?: number
    include_deleted?: boolean
  }): Promise<SupplierListResponse> {
    return apiClient.get('/suppliers', { params }).then((r) => r.data)
  },

  create(body: SupplierCreatePayload): Promise<Supplier> {
    return apiClient.post('/suppliers', body).then((r) => r.data)
  },

  get(publicId: string): Promise<Supplier> {
    return apiClient.get(`/suppliers/${publicId}`).then((r) => r.data)
  },

  update(publicId: string, body: SupplierUpdatePayload): Promise<Supplier> {
    return apiClient.put(`/suppliers/${publicId}`, body).then((r) => r.data)
  },

  delete(publicId: string): Promise<void> {
    return apiClient.delete(`/suppliers/${publicId}`).then(() => undefined)
  },

  listPrices(
    supplierPublicId: string,
    params?: { limit?: number; offset?: number }
  ): Promise<PriceEntry[]> {
    return apiClient
      .get(`/suppliers/${supplierPublicId}/prices`, { params })
      .then((r) => r.data)
  },

  addPrice(supplierPublicId: string, body: PriceAddPayload): Promise<PriceEntry> {
    return apiClient
      .post(`/suppliers/${supplierPublicId}/prices`, body)
      .then((r) => r.data)
  },

  getPartPrices(
    partPublicId: string,
    params?: { at?: string }
  ): Promise<PriceComparisonItem[]> {
    return apiClient
      .get(`/parts/${partPublicId}/supplier-prices`, { params })
      .then((r) => r.data)
  },
}
