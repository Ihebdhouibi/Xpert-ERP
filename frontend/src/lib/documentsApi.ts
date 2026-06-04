/**
 * API client for the /documents endpoints (GED).
 */
import { apiClient } from './apiClient'

export type DocumentCategory =
  | 'registration_card'
  | 'id_doc'
  | 'insurance'
  | 'accident_photo'
  | 'repair_attachment'
  | 'invoice'
  | 'supplier_invoice'
  | 'generic'

export type OwnerEntityType =
  | 'customer'
  | 'vehicle'
  | 'repair_order'
  | 'invoice'
  | 'supplier_invoice'
  | 'generic'

export interface DocumentOut {
  id: string
  garage_id: number
  owner_entity_type: OwnerEntityType
  owner_entity_id: number | null
  category: DocumentCategory
  filename: string
  mime_type: string
  size_bytes: number
  uploaded_by: number
  uploaded_at: string
  status: 'active' | 'deleted'
  archived: boolean
  archived_at: string | null
}

export interface DocumentListResponse {
  items: DocumentOut[]
  limit: number
  offset: number
}

export interface SignedUrlResponse {
  document_id: string
  url: string
  expires_in_seconds: number
}

export interface ListDocumentsParams {
  category?: DocumentCategory
  owner_entity_type?: OwnerEntityType
  owner_entity_id?: number
  from_date?: string
  to_date?: string
  q?: string
  limit?: number
  offset?: number
}

export const documentsApi = {
  list(params: ListDocumentsParams = {}): Promise<DocumentListResponse> {
    return apiClient.get('/documents', { params }).then((r) => r.data)
  },

  get(id: string): Promise<DocumentOut> {
    return apiClient.get(`/documents/${id}`).then((r) => r.data)
  },

  getSignedUrl(id: string): Promise<SignedUrlResponse> {
    return apiClient.get(`/documents/${id}/signed-url`).then((r) => r.data)
  },

  upload(
    file: File,
    category: DocumentCategory,
    ownerEntityType: OwnerEntityType,
    ownerEntityId?: number,
  ): Promise<DocumentOut> {
    const form = new FormData()
    form.append('file', file)
    form.append('category', category)
    form.append('owner_entity_type', ownerEntityType)
    if (ownerEntityId != null) form.append('owner_entity_id', String(ownerEntityId))
    return apiClient
      .post('/documents', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then((r) => r.data)
  },

  delete(id: string): Promise<void> {
    return apiClient.delete(`/documents/${id}`).then(() => undefined)
  },
}
