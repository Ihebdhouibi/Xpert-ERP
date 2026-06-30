import { apiClient } from './apiClient'

export interface PoForExtractionResponse {
  purchase_order_public_id: string
  supplier_id: number
}

export interface SupplierDeliveryNoteLineInput {
  po_line_id: number
  quantity_received: number
  part_public_id?: string
  // Optional per-line capture from the OCR review grid. Prices are MINOR units (cents).
  code?: string
  designation?: string
  pu_brut?: number
  pu_net?: number
  montant_ht?: number
}

export interface SupplierDeliveryNoteCreatePayload {
  extraction_id: string
  bl_number?: string
  bl_date?: string
  notes?: string
  allow_duplicate_bl_number?: boolean
  lines: SupplierDeliveryNoteLineInput[]
}

export interface SupplierDeliveryNote {
  id: string
  bl_number: string | null
  bl_date: string | null
  status: string
  has_discrepancy: boolean
  created_at: string
}

export const supplierDeliveryNoteApi = {
  poForExtraction(extractionId: string): Promise<PoForExtractionResponse> {
    return apiClient
      .get(`/supplier-delivery-notes/po-for-extraction/${extractionId}`)
      .then((r) => r.data)
  },

  create(
    payload: SupplierDeliveryNoteCreatePayload,
  ): Promise<SupplierDeliveryNote> {
    return apiClient
      .post('/supplier-delivery-notes', payload)
      .then((r) => r.data)
  },
}
