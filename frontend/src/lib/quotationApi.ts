import { apiClient } from './apiClient'

export type QuotationStatus = 'draft' | 'sent' | 'approved' | 'rejected' | 'expired' | 'converted'
export type LineKind = 'labor' | 'part' | 'service' | 'other'

export const QUOTATION_STATUS_LABELS: Record<QuotationStatus, string> = {
  draft: 'Brouillon',
  sent: 'Envoyé',
  approved: 'Approuvé',
  rejected: 'Refusé',
  expired: 'Expiré',
  converted: 'Converti',
}

export const LINE_KIND_LABELS: Record<LineKind, string> = {
  labor: 'Main d\'œuvre',
  part: 'Pièce',
  service: 'Prestation',
  other: 'Autre',
}

export interface QuotationLineOut {
  id: number
  quotation_id: number
  kind: LineKind
  part_id: number | null
  description: string
  quantity: string
  unit_price_minor: number
  discount_percent: string
  vat_rate: string
  line_total_minor: number
}

export interface QuotationOut {
  id: number
  public_id: string
  garage_id: number
  customer_id: number
  vehicle_id: number | null
  repair_order_id: number | null
  doc_number: string | null
  status: QuotationStatus
  valid_until: string | null
  subtotal_minor: number
  discount_minor: number
  vat_minor: number
  total_minor: number
  currency: string
  notes: string | null
  version: number
  created_at: string
  updated_at: string
  lines: QuotationLineOut[]
}

export interface QuotationListResponse {
  items: QuotationOut[]
  total: number
  page: number
  page_size: number
}

export interface QuotationLineCreateInput {
  kind?: LineKind
  part_id?: number | null
  description: string
  quantity: number
  unit_price_minor: number
  discount_percent?: number
  vat_rate?: number
}

export interface QuotationCreateInput {
  customer_id: number
  vehicle_id?: number | null
  repair_order_id?: number | null
  currency?: string
  valid_until?: string | null
  notes?: string | null
  lines?: QuotationLineCreateInput[]
}

export interface QuotationUpdateInput {
  vehicle_id?: number | null
  repair_order_id?: number | null
  currency?: string
  valid_until?: string | null
  notes?: string | null
}

export const quotationApi = {
  list(params?: {
    customer_id?: number
    status?: QuotationStatus
    page?: number
    page_size?: number
  }): Promise<QuotationListResponse> {
    return apiClient.get('/quotations', { params }).then(r => r.data)
  },

  get(publicId: string): Promise<QuotationOut> {
    return apiClient.get(`/quotations/${publicId}`).then(r => r.data)
  },

  create(input: QuotationCreateInput): Promise<QuotationOut> {
    return apiClient.post('/quotations', input).then(r => r.data)
  },

  update(publicId: string, version: number, input: QuotationUpdateInput): Promise<QuotationOut> {
    return apiClient
      .patch(`/quotations/${publicId}`, input, { headers: { 'If-Match': String(version) } })
      .then(r => r.data)
  },

  addLine(publicId: string, version: number, input: QuotationLineCreateInput): Promise<QuotationOut> {
    return apiClient
      .post(`/quotations/${publicId}/lines`, input, { headers: { 'If-Match': String(version) } })
      .then(r => r.data)
  },

  updateLine(
    publicId: string,
    lineId: number,
    version: number,
    input: Partial<QuotationLineCreateInput>,
  ): Promise<QuotationOut> {
    return apiClient
      .patch(`/quotations/${publicId}/lines/${lineId}`, input, {
        headers: { 'If-Match': String(version) },
      })
      .then(r => r.data)
  },

  removeLine(publicId: string, lineId: number, version: number): Promise<QuotationOut> {
    return apiClient
      .delete(`/quotations/${publicId}/lines/${lineId}`, {
        headers: { 'If-Match': String(version) },
      })
      .then(r => r.data)
  },

  send(publicId: string, version: number): Promise<QuotationOut> {
    return apiClient
      .post(`/quotations/${publicId}/send`, {}, { headers: { 'If-Match': String(version) } })
      .then(r => r.data)
  },

  approve(publicId: string, version: number): Promise<QuotationOut> {
    return apiClient
      .post(`/quotations/${publicId}/approve`, {}, { headers: { 'If-Match': String(version) } })
      .then(r => r.data)
  },

  reject(publicId: string, version: number): Promise<QuotationOut> {
    return apiClient
      .post(`/quotations/${publicId}/reject`, {}, { headers: { 'If-Match': String(version) } })
      .then(r => r.data)
  },

  remove(publicId: string): Promise<void> {
    return apiClient.delete(`/quotations/${publicId}`).then(() => undefined)
  },

  fromRepairOrder(roPublicId: string): Promise<QuotationOut> {
    return apiClient.post(`/quotations/from-repair-order/${roPublicId}`).then(r => r.data)
  },

  getPdf(id: number): Promise<string> {
    return apiClient
      .get(`/pdf/quotations/${id}`, { responseType: 'blob' })
      .then(r => URL.createObjectURL(r.data as Blob))
  },
}
