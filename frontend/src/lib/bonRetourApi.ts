import { apiClient } from './apiClient'

export type BonRetourPartyType = 'client' | 'supplier'
export type BonRetourStatus = 'draft' | 'confirmed' | 'cancelled' | 'reversed'
export type BonRetourLineCondition = 'neuf' | 'utilise' | 'endommage'
export type SupplierCreditNoteStatus = 'draft' | 'issued' | 'void'

export const BON_RETOUR_STATUS_LABELS: Record<BonRetourStatus, string> = {
  draft: 'Brouillon',
  confirmed: 'Confirmé',
  cancelled: 'Annulé',
  reversed: 'Contre-passé',
}

export const SUPPLIER_CREDIT_NOTE_STATUS_LABELS: Record<SupplierCreditNoteStatus, string> = {
  draft: 'Brouillon',
  issued: 'Émis',
  void: 'Annulé',
}

export const BON_RETOUR_PARTY_LABELS: Record<BonRetourPartyType, string> = {
  client: 'Client',
  supplier: 'Fournisseur',
}

export const BON_RETOUR_CONDITION_LABELS: Record<BonRetourLineCondition, string> = {
  neuf: 'Neuf',
  utilise: 'Utilisé',
  endommage: 'Endommagé',
}

export interface BonRetourLineOut {
  id: number
  bon_de_retour_id: number
  part_id: number | null
  description: string
  quantity: string
  unit_price_minor: number
  vat_rate: string
  line_total_minor: number
  condition: BonRetourLineCondition | null
  restock: boolean
}

export interface BonRetourOut {
  id: number
  public_id: string
  garage_id: number
  party_type: BonRetourPartyType
  customer_id: number | null
  supplier_id: number | null
  source_invoice_id: number | null
  source_supplier_invoice_id: number | null
  doc_number: string | null
  status: BonRetourStatus
  reason: string | null
  notes: string | null
  subtotal_minor: number
  vat_minor: number
  total_minor: number
  currency: string
  credit_note_id: number | null
  supplier_credit_note_id: number | null
  version: number
  confirmed_at: string | null
  cancelled_at: string | null
  reversed_at: string | null
  created_at: string
  updated_at: string
  lines: BonRetourLineOut[]
  // Denormalised display fields
  customer_name: string | null
  supplier_name: string | null
  credit_note_doc_number: string | null
  supplier_credit_note_doc_number: string | null
}

export interface BonRetourListResponse {
  items: BonRetourOut[]
  total: number
  page: number
  page_size: number
}

export interface BonRetourLineCreateInput {
  part_id?: number | null
  description: string
  quantity: number
  unit_price_minor?: number
  vat_rate?: number
  condition?: BonRetourLineCondition | null
  restock?: boolean
}

export interface BonRetourCreateInput {
  party_type: BonRetourPartyType
  customer_id?: number | null
  supplier_id?: number | null
  source_invoice_id?: number | null
  source_supplier_invoice_id?: number | null
  currency?: string
  reason?: string | null
  notes?: string | null
  lines?: BonRetourLineCreateInput[]
}

export interface BonRetourLineUpdateInput {
  part_id?: number | null
  description?: string
  quantity?: number
  unit_price_minor?: number
  vat_rate?: number
  condition?: BonRetourLineCondition | null
  restock?: boolean
}

export interface CreateCreditNoteInput {
  invoice_id?: number | null
  total_minor?: number | null
  reason?: string | null
}

export interface CreateSupplierCreditNoteInput {
  total_ht_minor?: number | null
  total_ttc_minor?: number | null
  reason?: string | null
}

export interface SupplierCreditNoteOut {
  id: number
  public_id: string
  garage_id: number
  supplier_id: number
  supplier_invoice_id: number | null
  bon_de_retour_id: number | null
  doc_number: string | null
  status: SupplierCreditNoteStatus
  total_ht_minor: number
  total_ttc_minor: number
  reason: string | null
  issued_at: string | null
  voided_at: string | null
  is_exported: boolean
  created_at: string
  updated_at: string
  // Denormalised display fields
  supplier_name: string | null
  bon_de_retour_public_id: string | null
}

export interface SupplierCreditNoteListResponse {
  items: SupplierCreditNoteOut[]
  total: number
  page: number
  page_size: number
}

export const bonRetourApi = {
  list: async (params: {
    party_type?: BonRetourPartyType
    status?: BonRetourStatus
    page?: number
    page_size?: number
  } = {}): Promise<BonRetourListResponse> => {
    const { data } = await apiClient.get<BonRetourListResponse>('/bon-de-retour', { params })
    return data
  },

  get: async (publicId: string): Promise<BonRetourOut> => {
    const { data } = await apiClient.get<BonRetourOut>(`/bon-de-retour/${publicId}`)
    return data
  },

  create: async (input: BonRetourCreateInput): Promise<BonRetourOut> => {
    const { data } = await apiClient.post<BonRetourOut>('/bon-de-retour', input)
    return data
  },

  addLine: async (publicId: string, line: BonRetourLineCreateInput): Promise<BonRetourOut> => {
    const { data } = await apiClient.post<BonRetourOut>(`/bon-de-retour/${publicId}/lines`, line)
    return data
  },

  updateLine: async (publicId: string, lineId: number, input: BonRetourLineUpdateInput): Promise<BonRetourOut> => {
    const { data } = await apiClient.patch<BonRetourOut>(`/bon-de-retour/${publicId}/lines/${lineId}`, input)
    return data
  },

  removeLine: async (publicId: string, lineId: number): Promise<BonRetourOut> => {
    const { data } = await apiClient.delete<BonRetourOut>(`/bon-de-retour/${publicId}/lines/${lineId}`)
    return data
  },

  confirm: async (publicId: string): Promise<BonRetourOut> => {
    const { data } = await apiClient.post<BonRetourOut>(`/bon-de-retour/${publicId}/confirm`)
    return data
  },

  cancel: async (publicId: string): Promise<BonRetourOut> => {
    const { data } = await apiClient.post<BonRetourOut>(`/bon-de-retour/${publicId}/cancel`)
    return data
  },

  remove: async (publicId: string): Promise<void> => {
    await apiClient.delete(`/bon-de-retour/${publicId}`)
  },

  createCreditNote: async (publicId: string, input: CreateCreditNoteInput): Promise<BonRetourOut> => {
    const { data } = await apiClient.post<BonRetourOut>(`/bon-de-retour/${publicId}/create-credit-note`, input)
    return data
  },

  createSupplierCreditNote: async (publicId: string, input: CreateSupplierCreditNoteInput): Promise<BonRetourOut> => {
    const { data } = await apiClient.post<BonRetourOut>(`/bon-de-retour/${publicId}/create-supplier-credit-note`, input)
    return data
  },

  reverse: async (publicId: string): Promise<BonRetourOut> => {
    const { data } = await apiClient.post<BonRetourOut>(`/bon-de-retour/${publicId}/reverse`)
    return data
  },

  getPdf: async (publicId: string): Promise<ArrayBuffer> => {
    const { data } = await apiClient.get(`/pdf/bon-de-retour/${publicId}`, {
      responseType: 'arraybuffer',
    })
    return data as ArrayBuffer
  },

  listSupplierCreditNotes: async (params: {
    status?: SupplierCreditNoteStatus
    page?: number
    page_size?: number
  } = {}): Promise<SupplierCreditNoteListResponse> => {
    const { data } = await apiClient.get<SupplierCreditNoteListResponse>('/bon-de-retour/supplier-credit-notes', { params })
    return data
  },
}
