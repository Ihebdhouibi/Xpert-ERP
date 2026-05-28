import axios from 'axios'
import { apiClient } from './apiClient'

const PUBLIC_BASE = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1`

export type InspectionItemStatus = 'ok' | 'attention' | 'defective' | 'not_applicable'
export type InspectionStatus = 'draft' | 'in_progress' | 'completed' | 'cancelled'

export const ITEM_STATUS_LABELS: Record<InspectionItemStatus, string> = {
  ok: 'OK',
  attention: 'À surveiller',
  defective: 'Défectueux',
  not_applicable: 'N/A',
}

export const ITEM_STATUS_COLORS: Record<
  InspectionItemStatus,
  'success' | 'warning' | 'error' | 'default'
> = {
  ok: 'success',
  attention: 'warning',
  defective: 'error',
  not_applicable: 'default',
}

export const INSPECTION_STATUS_LABELS: Record<InspectionStatus, string> = {
  draft: 'Brouillon',
  in_progress: 'En cours',
  completed: 'Terminée',
  cancelled: 'Annulée',
}

export const INSPECTION_ALLOWED_TRANSITIONS: Record<InspectionStatus, InspectionStatus[]> = {
  draft: ['in_progress', 'cancelled'],
  in_progress: ['completed', 'cancelled'],
  completed: [],
  cancelled: [],
}

export interface TemplateItem {
  id: string
  label: string
  requires_photo: boolean
}

export interface TemplateSection {
  id: string
  title: string
  items: TemplateItem[]
}

export interface InspectionTemplate {
  id: string
  name: string
  sections: TemplateSection[]
  version: number
  created_at: string
  updated_at: string
}

export interface InspectionTemplateListResponse {
  items: InspectionTemplate[]
  total: number
  page: number
  page_size: number
}

export interface ItemResult {
  item_id: string
  status: InspectionItemStatus
  notes: string | null
  media_ids: string[]
  written_at: string
}

export interface InspectionDetail {
  id: string
  template_id: string
  template_name: string
  template_sections: TemplateSection[]
  mechanic_id: number | null
  repair_order_id: string | null
  vehicle_id: number | null
  status: InspectionStatus
  started_at: string | null
  completed_at: string | null
  created_at: string
  results: ItemResult[]
  version: number
}

export interface InspectionSummary {
  id: string
  template_id: string
  template_name: string
  mechanic_id: number | null
  repair_order_id: string | null
  vehicle_id: number | null
  status: InspectionStatus
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface InspectionListResponse {
  items: InspectionSummary[]
  total: number
  page: number
  page_size: number
}

export interface ItemResultPayload {
  item_id: string
  status: InspectionItemStatus
  notes?: string
  media_ids?: string[]
  written_at?: string
}

export interface BulkResultsResponse {
  synced: number
  conflicts: Array<{
    item_id: string
    client_written_at: string
    server_written_at: string
    discarded_status: string
    kept_status: string
  }>
}

export interface VehicleRecommendation {
  id: string
  vehicle_id: number
  item_id: string
  item_label: string
  item_status: string
  status: string
  notes: string | null
  created_at: string
}

export interface DeclinedItemPayload {
  item_id: string
  item_label: string
  item_status: string
  notes?: string
}

export interface ApprovalLinkResponse {
  token: string
  expires_at: string
}

export interface ApprovalPublicItem {
  item_id: string
  item_label: string
  item_status: string | null
  notes: string | null
  actionable: boolean
}

export interface ApprovalPublicSection {
  section_id: string
  section_title: string
  items: ApprovalPublicItem[]
}

export interface ApprovalPublicInspection {
  inspection_id: string
  template_name: string
  vehicle_info: string
  mechanic_name: string
  completed_at: string | null
  sections: ApprovalPublicSection[]
}

export interface ApprovalDecision {
  item_id: string
  decision: 'approved' | 'rejected'
}

export interface ProcessApprovalResponse {
  repair_tasks_created: number
  recommendations_archived: number
}

export const inspectionApi = {
  // Templates
  listTemplates(params?: {
    page?: number
    page_size?: number
  }): Promise<InspectionTemplateListResponse> {
    return apiClient.get('/inspection-templates', { params }).then((r) => r.data)
  },

  createTemplate(body: { name: string; sections: TemplateSection[] }): Promise<InspectionTemplate> {
    return apiClient.post('/inspection-templates', body).then((r) => r.data)
  },

  getTemplate(publicId: string): Promise<InspectionTemplate> {
    return apiClient.get(`/inspection-templates/${publicId}`).then((r) => r.data)
  },

  updateTemplate(
    publicId: string,
    body: { name?: string; sections?: TemplateSection[]; version: number }
  ): Promise<InspectionTemplate> {
    return apiClient.put(`/inspection-templates/${publicId}`, body).then((r) => r.data)
  },

  deleteTemplate(publicId: string): Promise<void> {
    return apiClient.delete(`/inspection-templates/${publicId}`).then(() => undefined)
  },

  // Inspections
  listInspections(params?: {
    status?: InspectionStatus
    mechanic_id?: number
    vehicle_id?: number
    page?: number
    page_size?: number
  }): Promise<InspectionListResponse> {
    return apiClient.get('/inspections', { params }).then((r) => r.data)
  },

  createInspection(body: {
    template_public_id: string
    mechanic_id?: number
    repair_order_public_id?: string
    vehicle_id?: number
  }): Promise<InspectionDetail> {
    return apiClient.post('/inspections', body).then((r) => r.data)
  },

  getInspection(publicId: string): Promise<InspectionDetail> {
    return apiClient.get(`/inspections/${publicId}`).then((r) => r.data)
  },

  transitionStatus(publicId: string, newStatus: InspectionStatus): Promise<InspectionSummary> {
    return apiClient
      .put(`/inspections/${publicId}/status`, { new_status: newStatus })
      .then((r) => r.data)
  },

  submitResults(publicId: string, items: ItemResultPayload[]): Promise<BulkResultsResponse> {
    return apiClient
      .post(`/inspections/${publicId}/results`, { items })
      .then((r) => r.data)
  },

  archiveDeclined(
    publicId: string,
    vehicleId: number,
    declinedItems: DeclinedItemPayload[]
  ): Promise<VehicleRecommendation[]> {
    return apiClient
      .post(`/inspections/${publicId}/recommendations`, {
        vehicle_id: vehicleId,
        declined_items: declinedItems,
      })
      .then((r) => r.data)
  },

  convertToRO(publicId: string, repairOrderPublicId: string): Promise<InspectionSummary> {
    return apiClient
      .post(`/inspections/${publicId}/convert-to-ro`, {
        repair_order_public_id: repairOrderPublicId,
      })
      .then((r) => r.data)
  },

  listVehicleRecommendations(vehicleId: number): Promise<VehicleRecommendation[]> {
    return apiClient.get(`/vehicles/${vehicleId}/recommendations`).then((r) => r.data)
  },

  generateApprovalLink(publicId: string): Promise<ApprovalLinkResponse> {
    return apiClient
      .post(`/inspections/${publicId}/approval-link`)
      .then((r) => r.data)
  },

  downloadReport(publicId: string): Promise<Blob> {
    return apiClient
      .get(`/inspections/${publicId}/report.pdf`, { responseType: 'blob' })
      .then((r) => r.data)
  },

  // Public — no auth token needed
  getApprovalData(token: string): Promise<ApprovalPublicInspection> {
    return axios
      .get(`${PUBLIC_BASE}/inspections/approve/${encodeURIComponent(token)}`)
      .then((r) => r.data)
  },

  submitApproval(token: string, decisions: ApprovalDecision[]): Promise<ProcessApprovalResponse> {
    return axios
      .post(`${PUBLIC_BASE}/inspections/approve/${encodeURIComponent(token)}`, { decisions })
      .then((r) => r.data)
  },
}
