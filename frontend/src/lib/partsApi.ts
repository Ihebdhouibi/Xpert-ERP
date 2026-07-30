import { apiClient } from './apiClient'

export type PartStatus = 'active' | 'discontinued' | 'out_of_stock'

export interface PartCategory {
  id: number
  garage_id: number
  name: string
  description: string | null
  parent_id: number | null
  created_at: string
  updated_at: string
}

// Synthetic category used as a sentinel in category pickers so the user can
// select parts that have no category_id assigned (id -1 never collides with
// a real category, which is a positive DB id).
export const UNCATEGORIZED_CATEGORY: PartCategory = {
  id: -1,
  garage_id: 0,
  name: 'Sans catégorie',
  description: null,
  parent_id: null,
  created_at: '',
  updated_at: '',
}

export interface PartSummary {
  id: string
  int_id: number
  sku_code: string
  name: string
  description: string | null
  category_id: number | null
  unit_of_measure: string
  purchase_price_minor: number
  selling_price_minor: number
  supplier_hint_id: number | null
  reorder_threshold: number | null
  reorder_quantity: number | null
  status: PartStatus
  stock_on_hand: number
  version: number
  created_at: string
  updated_at: string
}

export interface PartDetail extends PartSummary {
  garage_id: number
  deleted_at: string | null
  category: PartCategory | null
  equivalents: PartSummary[]
}

export interface PartListResponse {
  items: PartSummary[]
  total: number
  page: number
  page_size: number
}

export interface PartListParams {
  search?: string
  category_id?: number
  uncategorized?: boolean
  status?: PartStatus
  include_deleted?: boolean
  page?: number
  page_size?: number
}

export interface PartCreatePayload {
  sku_code: string
  name: string
  description?: string
  category_id?: number
  unit_of_measure?: string
  purchase_price_minor: number
  selling_price_minor: number
  supplier_hint_id?: number
  reorder_threshold?: number
  reorder_quantity?: number
  status?: PartStatus
}

export interface PartUpdatePayload {
  name?: string
  description?: string
  category_id?: number
  unit_of_measure?: string
  purchase_price_minor?: number
  selling_price_minor?: number
  supplier_hint_id?: number
  reorder_threshold?: number
  reorder_quantity?: number
  status?: PartStatus
}

export const STATUS_LABELS: Record<PartStatus, string> = {
  active: 'Actif',
  discontinued: 'Discontinué',
  out_of_stock: 'En rupture',
}

export const partsApi = {
  listCategories(params?: { parent_id?: number; flat?: boolean }): Promise<PartCategory[]> {
    return apiClient.get('/part-categories', { params }).then((r) => r.data)
  },

  createCategory(body: { name: string; description?: string; parent_id?: number }): Promise<PartCategory> {
    return apiClient.post('/part-categories', body).then((r) => r.data)
  },

  updateCategory(id: number, body: { name?: string; description?: string; parent_id?: number }): Promise<PartCategory> {
    return apiClient.patch(`/part-categories/${id}`, body).then((r) => r.data)
  },

  deleteCategory(id: number): Promise<void> {
    return apiClient.delete(`/part-categories/${id}`).then((r) => r.data)
  },

  list(params?: PartListParams): Promise<PartListResponse> {
    return apiClient.get('/parts', { params }).then((r) => r.data)
  },

  get(publicId: string): Promise<PartDetail> {
    return apiClient.get(`/parts/${publicId}`).then((r) => r.data)
  },

  create(body: PartCreatePayload): Promise<PartDetail> {
    return apiClient.post('/parts', body).then((r) => r.data)
  },

  update(publicId: string, version: number, body: PartUpdatePayload): Promise<PartDetail> {
    return apiClient.patch(`/parts/${publicId}?version=${version}`, body).then((r) => r.data)
  },

  remove(publicId: string): Promise<void> {
    return apiClient.delete(`/parts/${publicId}`).then((r) => r.data)
  },

  listEquivalents(publicId: string): Promise<PartSummary[]> {
    return apiClient.get(`/parts/${publicId}/equivalents`).then((r) => r.data)
  },

  addEquivalent(publicId: string, targetId: string): Promise<PartSummary[]> {
    return apiClient.post(`/parts/${publicId}/equivalents`, { target_id: targetId }).then((r) => r.data)
  },

  removeEquivalent(publicId: string, targetId: string): Promise<void> {
    return apiClient.delete(`/parts/${publicId}/equivalents/${targetId}`).then((r) => r.data)
  },
}
