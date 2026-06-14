import { apiClient } from './apiClient'

export type POStatus =
  | 'draft'
  | 'sent'
  | 'partially_received'
  | 'completed'
  | 'cancelled'

export type POMatchFlag = 'ok' | 'qty_mismatch' | 'inv_mismatch'

export interface POLine {
  id: number
  part_id: number
  part_name?: string | null
  quantity_ordered: number
  unit_price_ht: number
  quantity_received: number
  quantity_invoiced: number
  match_flag: POMatchFlag
}

export interface PurchaseOrder {
  id: string
  supplier_id: number
  supplier_name?: string | null
  supplier_public_id?: string | null
  doc_number: string | null
  status: POStatus
  expected_delivery_date: string | null
  notes: string | null
  total_ht: number
  version: number
  created_at: string
  updated_at: string
  lines: POLine[]
}

export interface POListResponse {
  items: PurchaseOrder[]
  total: number
  page: number
  page_size: number
}

export interface POLineInput {
  part_public_id: string
  quantity_ordered: number
  unit_price_ht: number
}

export interface POCreatePayload {
  supplier_public_id: string
  expected_delivery_date?: string
  notes?: string
  lines: POLineInput[]
}

export interface POUpdatePayload {
  version: number
  expected_delivery_date?: string | null
  notes?: string | null
  lines?: POLineInput[]
}

export interface POReceiveLineInput {
  line_id: number
  quantity_received: number
}

export interface POReceivePayload {
  version: number
  lines: POReceiveLineInput[]
}

export interface POFromAlertPayload {
  supplier_public_id: string
  unit_price_ht: number
}

export const STATUS_LABELS: Record<POStatus, string> = {
  draft: 'Brouillon',
  sent: 'Envoyé',
  partially_received: 'Partiellement reçu',
  completed: 'Complété',
  cancelled: 'Annulé',
}

export const MATCH_FLAG_LABELS: Record<POMatchFlag, string> = {
  ok: 'OK',
  qty_mismatch: 'Écart quantité',
  inv_mismatch: 'Écart facture',
}

export const purchaseOrderApi = {
  list(params?: {
    status?: POStatus
    search?: string
    page?: number
    page_size?: number
  }): Promise<POListResponse> {
    return apiClient.get('/purchase-orders', { params }).then((r) => r.data)
  },

  create(body: POCreatePayload): Promise<PurchaseOrder> {
    return apiClient.post('/purchase-orders', body).then((r) => r.data)
  },

  get(publicId: string): Promise<PurchaseOrder> {
    return apiClient.get(`/purchase-orders/${publicId}`).then((r) => r.data)
  },

  update(publicId: string, body: POUpdatePayload): Promise<PurchaseOrder> {
    return apiClient.put(`/purchase-orders/${publicId}`, body).then((r) => r.data)
  },

  send(publicId: string, version: number): Promise<PurchaseOrder> {
    return apiClient
      .post(`/purchase-orders/${publicId}/send`, { version })
      .then((r) => r.data)
  },

  receive(publicId: string, body: POReceivePayload): Promise<PurchaseOrder> {
    return apiClient
      .post(`/purchase-orders/${publicId}/receive`, body)
      .then((r) => r.data)
  },

  cancel(publicId: string, version: number): Promise<PurchaseOrder> {
    return apiClient
      .post(`/purchase-orders/${publicId}/cancel`, { version })
      .then((r) => r.data)
  },

  updateInvoicedQty(
    publicId: string,
    lineId: number,
    quantity_invoiced: number
  ): Promise<POLine> {
    return apiClient
      .patch(`/purchase-orders/${publicId}/lines/${lineId}/invoice`, { quantity_invoiced })
      .then((r) => r.data)
  },

  createFromAlert(alertId: number, body: POFromAlertPayload): Promise<PurchaseOrder> {
    return apiClient
      .post(`/stock/alerts/${alertId}/create-po`, body)
      .then((r) => r.data)
  },

  getPdf(publicId: string): Promise<string> {
    return apiClient
      .get(`/pdf/purchase-orders/${publicId}`, { responseType: 'blob' })
      .then((r) => URL.createObjectURL(r.data as Blob))
  },
}
