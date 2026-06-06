import { apiClient } from './apiClient'

export type DeliveryNoteStatus = 'draft' | 'issued' | 'delivered' | 'cancelled'
export type DeliveryNoteLineKind = 'part' | 'accessory' | 'service' | 'other'

export const DELIVERY_NOTE_STATUS_LABELS: Record<DeliveryNoteStatus, string> = {
  draft: 'Brouillon',
  issued: 'Émis',
  delivered: 'Livré',
  cancelled: 'Annulé',
}

// 'accessory' kept for backward-compat with existing DB rows but not shown in UI
export const DELIVERY_NOTE_LINE_KIND_LABELS: Record<DeliveryNoteLineKind, string> = {
  part: 'Pièce / Accessoire',
  accessory: 'Accessoire',  // legacy — not shown in create form
  service: 'Prestation',
  other: 'Autre',
}

export interface DeliveryNoteLineOut {
  id: number
  delivery_note_id: number
  kind: DeliveryNoteLineKind
  part_id: number | null
  description: string
  quantity: string
  unit_price_minor: number
  vat_rate: string
  line_total_minor: number
}

export interface DeliveryNoteOut {
  id: number
  public_id: string
  garage_id: number
  customer_id: number
  vehicle_id: number | null
  invoice_id: number | null
  doc_number: string | null
  status: DeliveryNoteStatus
  issued_at: string | null
  delivered_at: string | null
  subtotal_minor: number
  vat_minor: number
  total_minor: number
  currency: string
  notes: string | null
  version: number
  created_at: string
  updated_at: string
  lines: DeliveryNoteLineOut[]
}

export interface DeliveryNoteListResponse {
  items: DeliveryNoteOut[]
  total: number
  page: number
  page_size: number
}

export interface DeliveryNoteCreateInput {
  customer_id: number
  vehicle_id?: number | null
  currency?: string
  notes?: string | null
  lines?: DeliveryNoteLineCreateInput[]
}

export interface DeliveryNoteLineCreateInput {
  kind?: DeliveryNoteLineKind
  part_id?: number | null
  description: string
  quantity: number
  unit_price_minor: number
  vat_rate?: number
}

export interface DeliveryNoteUpdateInput {
  vehicle_id?: number | null
  currency?: string
  notes?: string | null
}

export interface DeliveryNoteLineUpdateInput {
  kind?: DeliveryNoteLineKind
  part_id?: number | null
  description?: string
  quantity?: number
  unit_price_minor?: number
  vat_rate?: number
}

export const deliveryNoteApi = {
  list: async (params: {
    customer_id?: number
    status?: DeliveryNoteStatus
    page?: number
    page_size?: number
  } = {}): Promise<DeliveryNoteListResponse> => {
    const { data } = await apiClient.get<DeliveryNoteListResponse>('/delivery-notes', { params })
    return data
  },

  get: async (publicId: string): Promise<DeliveryNoteOut> => {
    const { data } = await apiClient.get<DeliveryNoteOut>(`/delivery-notes/${publicId}`)
    return data
  },

  create: async (input: DeliveryNoteCreateInput): Promise<DeliveryNoteOut> => {
    const { data } = await apiClient.post<DeliveryNoteOut>('/delivery-notes', input)
    return data
  },

  update: async (
    publicId: string,
    version: number,
    input: DeliveryNoteUpdateInput,
  ): Promise<DeliveryNoteOut> => {
    const { data } = await apiClient.patch<DeliveryNoteOut>(`/delivery-notes/${publicId}`, input, {
      headers: { 'If-Match': String(version) },
    })
    return data
  },

  remove: async (publicId: string): Promise<void> => {
    await apiClient.delete(`/delivery-notes/${publicId}`)
  },

  addLine: async (publicId: string, line: DeliveryNoteLineCreateInput): Promise<DeliveryNoteOut> => {
    const { data } = await apiClient.post<DeliveryNoteOut>(`/delivery-notes/${publicId}/lines`, line)
    return data
  },

  updateLine: async (
    publicId: string,
    lineId: number,
    input: DeliveryNoteLineUpdateInput,
  ): Promise<DeliveryNoteOut> => {
    const { data } = await apiClient.patch<DeliveryNoteOut>(
      `/delivery-notes/${publicId}/lines/${lineId}`,
      input,
    )
    return data
  },

  removeLine: async (publicId: string, lineId: number): Promise<DeliveryNoteOut> => {
    const { data } = await apiClient.delete<DeliveryNoteOut>(
      `/delivery-notes/${publicId}/lines/${lineId}`,
    )
    return data
  },

  issue: async (publicId: string): Promise<DeliveryNoteOut> => {
    const { data } = await apiClient.post<DeliveryNoteOut>(`/delivery-notes/${publicId}/issue`)
    return data
  },

  markDelivered: async (publicId: string): Promise<DeliveryNoteOut> => {
    const { data } = await apiClient.post<DeliveryNoteOut>(`/delivery-notes/${publicId}/mark-delivered`)
    return data
  },

  cancel: async (publicId: string): Promise<DeliveryNoteOut> => {
    const { data } = await apiClient.post<DeliveryNoteOut>(`/delivery-notes/${publicId}/cancel`)
    return data
  },

  convertToInvoice: async (publicId: string): Promise<DeliveryNoteOut> => {
    const { data } = await apiClient.post<DeliveryNoteOut>(
      `/delivery-notes/${publicId}/convert-to-invoice`,
    )
    return data
  },
}
