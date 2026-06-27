import { apiClient } from './apiClient'

export type SIStatus = 'draft' | 'posted' | 'approved' | 'paid' | 'cancelled'
export type SIMatchStatus = 'ok' | 'qty_mismatch' | 'price_mismatch'

export interface SILine {
  po_line_id: number
  description: string
  quantity: number
  unit_price_ht: number
  vat_rate: number
  line_total_ht: number
  line_total_ttc: number
  match_status: SIMatchStatus
  po_quantity_ordered: number
  po_quantity_received: number
  po_unit_price_ht: number
}

export interface SupplierInvoice {
  id: string
  supplier_id: number
  supplier_name: string | null
  purchase_order_id: number
  number: string
  status: SIStatus
  lines: SILine[]
  total_ht: number
  total_ttc: number
  has_discrepancy: boolean
  override_reason: string | null
  received_at: string | null
  due_date: string | null
  notes: string | null
  version: number
  created_at: string
  updated_at: string
}

export interface SIListResponse {
  items: SupplierInvoice[]
  total: number
  page: number
  page_size: number
}

export interface SILineInput {
  po_line_id?: number | null
  part_public_id?: string
  description?: string
  quantity: number
  unit_price_ht: number
  vat_rate?: number
}

export interface SICreatePayload {
  supplier_public_id: string
  po_public_id: string
  number?: string
  lines: SILineInput[]
  received_at?: string | null
  due_date?: string | null
  notes?: string | null
}

export interface SIUpdatePayload {
  version: number
  number?: string
  lines?: SILineInput[]
  received_at?: string | null
  due_date?: string | null
  notes?: string | null
}

export interface SIVersionPayload {
  version: number
}

export interface SIOverridePayload {
  version: number
  reason: string
}

export interface AccountingExport {
  journal: string
  invoice_number: string
  supplier_invoice_id: string
  purchase_order_id: number
  date: string | null
  due_date: string | null
  status: SIStatus
  has_discrepancy: boolean
  override_reason: string | null
  entries: Array<{
    account: string
    label: string
    debit: number
    credit: number
  }>
  lines: SILine[]
  total_ht: number
  total_ttc: number
}

export const STATUS_LABELS: Record<SIStatus, string> = {
  draft: 'Brouillon',
  posted: 'Enregistré',
  approved: 'Approuvé',
  paid: 'Payé',
  cancelled: 'Annulé',
}

export const MATCH_STATUS_LABELS: Record<SIMatchStatus, string> = {
  ok: 'OK',
  qty_mismatch: 'Écart quantité',
  price_mismatch: 'Écart prix',
}

export const supplierInvoiceApi = {
  list(params?: {
    status?: SIStatus
    search?: string
    page?: number
    page_size?: number
  }): Promise<SIListResponse> {
    return apiClient.get('/supplier-invoices', { params }).then((r) => r.data)
  },

  create(body: SICreatePayload): Promise<SupplierInvoice> {
    return apiClient.post('/supplier-invoices', body).then((r) => r.data)
  },

  get(id: string): Promise<SupplierInvoice> {
    return apiClient.get(`/supplier-invoices/${id}`).then((r) => r.data)
  },

  update(id: string, body: SIUpdatePayload): Promise<SupplierInvoice> {
    return apiClient.put(`/supplier-invoices/${id}`, body).then((r) => r.data)
  },

  post(id: string, body: SIVersionPayload): Promise<SupplierInvoice> {
    return apiClient.post(`/supplier-invoices/${id}/post`, body).then((r) => r.data)
  },

  override(id: string, body: SIOverridePayload): Promise<SupplierInvoice> {
    return apiClient.post(`/supplier-invoices/${id}/override`, body).then((r) => r.data)
  },

  approve(id: string, body: SIVersionPayload): Promise<SupplierInvoice> {
    return apiClient.post(`/supplier-invoices/${id}/approve`, body).then((r) => r.data)
  },

  markPaid(id: string, body: SIVersionPayload): Promise<SupplierInvoice> {
    return apiClient.post(`/supplier-invoices/${id}/mark-paid`, body).then((r) => r.data)
  },

  cancel(id: string, body: SIVersionPayload): Promise<SupplierInvoice> {
    return apiClient.post(`/supplier-invoices/${id}/cancel`, body).then((r) => r.data)
  },

  accountingExport(id: string): Promise<AccountingExport> {
    return apiClient.get(`/supplier-invoices/${id}/accounting-export`).then((r) => r.data)
  },

  getPdf(id: string): Promise<string> {
    return apiClient
      .get(`/pdf/supplier-invoices/${id}`, { responseType: 'blob' })
      .then((r) => URL.createObjectURL(r.data as Blob))
  },

  exportCsv(): Promise<void> {
    return apiClient
      .get('/supplier-invoices/accounting-export-csv', { responseType: 'blob' })
      .then((r) => {
        const url = URL.createObjectURL(r.data as Blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'export-comptable-fournisseurs.csv'
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      })
  },

  exportPdf(): Promise<string> {
    return apiClient
      .get('/supplier-invoices/accounting-export-pdf', { responseType: 'blob' })
      .then((r) => URL.createObjectURL(r.data as Blob))
  },
}
