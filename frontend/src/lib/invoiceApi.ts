import { apiClient } from './apiClient'

export type InvoiceStatus = 'draft' | 'issued' | 'partial' | 'paid' | 'cancelled'
export type InvoiceLineKind = 'labor' | 'part' | 'service' | 'other'

export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: 'Brouillon',
  issued: 'Émise',
  partial: 'Part. payée',
  paid: 'Payée',
  cancelled: 'Annulée',
}

export interface InvoiceLineOut {
  id: number
  invoice_id: number
  kind: InvoiceLineKind
  part_id: number | null
  description: string
  quantity: string
  unit_price_minor: number
  discount_percent: string
  vat_rate: string
  line_total_minor: number
}

export interface InvoiceOut {
  id: number
  public_id: string
  garage_id: number
  customer_id: number
  customer_name: string | null
  vehicle_id: number | null
  vehicle_label: string | null
  repair_order_id: number | null
  quotation_id: number | null
  doc_number: string | null
  status: InvoiceStatus
  issued_at: string | null
  due_at: string | null
  subtotal_minor: number
  discount_minor: number
  vat_minor: number
  total_minor: number
  paid_amount_minor: number
  outstanding_minor: number
  currency: string
  is_exported: boolean
  notes: string | null
  version: number
  created_at: string
  updated_at: string
  lines: InvoiceLineOut[]
}

export interface InvoiceListResponse {
  items: InvoiceOut[]
  total: number
  page: number
  page_size: number
}

export interface InvoiceLineCreateInput {
  kind?: InvoiceLineKind
  part_id?: number | null
  description: string
  quantity: number
  unit_price_minor: number
  discount_percent?: number
  vat_rate?: number
}

export interface InvoiceCreateInput {
  customer_id: number
  vehicle_id?: number | null
  repair_order_id?: number | null
  currency?: string
  due_at?: string | null
  notes?: string | null
  lines?: InvoiceLineCreateInput[]
}

export interface InvoiceFromDeliveryNotesInput {
  customer_id: number
  delivery_note_ids: string[]
  currency?: string
  due_at?: string | null
  notes?: string | null
}

export interface InvoiceUpdateInput {
  customer_id?: number | null
  vehicle_id?: number | null
  repair_order_id?: number | null
  currency?: string
  due_at?: string | null
  notes?: string | null
}

export const invoiceApi = {
  list(params?: {
    customer_id?: number
    status?: InvoiceStatus
    quotation_id?: number
    page?: number
    page_size?: number
  }): Promise<InvoiceListResponse> {
    return apiClient.get('/invoices', { params }).then(r => r.data)
  },

  get(publicId: string): Promise<InvoiceOut> {
    return apiClient.get(`/invoices/${publicId}`).then(r => r.data)
  },

  create(input: InvoiceCreateInput): Promise<InvoiceOut> {
    return apiClient.post('/invoices', input).then(r => r.data)
  },

  fromQuotation(quotationId: number, dueAt?: string | null): Promise<InvoiceOut> {
    return apiClient
      .post(`/invoices/from-quotation/${quotationId}`, { due_at: dueAt ?? null })
      .then(r => r.data)
  },

  fromDeliveryNotes(input: InvoiceFromDeliveryNotesInput): Promise<InvoiceOut> {
    return apiClient.post('/invoices/from-delivery-notes', input).then(r => r.data)
  },

  update(publicId: string, version: number, input: InvoiceUpdateInput): Promise<InvoiceOut> {
    return apiClient
      .patch(`/invoices/${publicId}`, input, { headers: { 'If-Match': String(version) } })
      .then(r => r.data)
  },

  addLine(publicId: string, version: number, input: InvoiceLineCreateInput): Promise<InvoiceOut> {
    return apiClient
      .post(`/invoices/${publicId}/lines`, input, { headers: { 'If-Match': String(version) } })
      .then(r => r.data)
  },

  updateLine(
    publicId: string,
    lineId: number,
    version: number,
    input: Partial<InvoiceLineCreateInput>,
  ): Promise<InvoiceOut> {
    return apiClient
      .patch(`/invoices/${publicId}/lines/${lineId}`, input, {
        headers: { 'If-Match': String(version) },
      })
      .then(r => r.data)
  },

  removeLine(publicId: string, lineId: number, version: number): Promise<InvoiceOut> {
    return apiClient
      .delete(`/invoices/${publicId}/lines/${lineId}`, {
        headers: { 'If-Match': String(version) },
      })
      .then(r => r.data)
  },

  issue(publicId: string, version: number): Promise<InvoiceOut> {
    return apiClient
      .post(`/invoices/${publicId}/issue`, {}, { headers: { 'If-Match': String(version) } })
      .then(r => r.data)
  },

  cancel(publicId: string, version: number): Promise<InvoiceOut> {
    return apiClient
      .post(`/invoices/${publicId}/cancel`, {}, { headers: { 'If-Match': String(version) } })
      .then(r => r.data)
  },

  remove(publicId: string): Promise<void> {
    return apiClient.delete(`/invoices/${publicId}`).then(() => undefined)
  },

  fromRepairOrder(roPublicId: string): Promise<InvoiceOut> {
    return apiClient.post(`/invoices/from-repair-order/${roPublicId}`).then(r => r.data)
  },

  sendEmail(publicId: string, recipient: 'client' | 'admin'): Promise<{ status: string }> {
    return apiClient
      .post(`/invoices/${publicId}/send-email`, {}, { params: { recipient } })
      .then(r => r.data)
  },
}
