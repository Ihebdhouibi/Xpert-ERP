import { apiClient } from './apiClient'

export type ROStatus =
  | 'created'
  | 'diagnosis'
  | 'in_repair'
  | 'finished'
  | 'delivered'
  | 'paused_parts'

export interface ROLaborLine {
  id: number
  labor_type: string
  duration_minutes: number
  rate_minor: number
  amount_minor: number
  created_at: string
}

export interface ROPartLine {
  id: number
  part_name: string
  quantity: number
  unit_cost_minor: number
  remise_pct: number
  tva_pct: number
  amount_minor: number
  created_at: string
}

export interface ROStatusEvent {
  id: number
  old_status: string | null
  new_status: string
  occurred_at: string
}

export interface RepairOrderSummary {
  id: string
  customer_id: number
  customer_name?: string | null
  vehicle_id: number | null
  description: string
  status: ROStatus
  priority: string | null
  estimated_cost_minor: number | null
  estimated_cost_currency: string | null
  actual_cost_minor: number
  assigned_user_id: number | null
  created_at: string
}

export interface RepairOrderDetail extends RepairOrderSummary {
  notes: string | null
  updated_at: string
  version: number
  assigned_user_id: number | null
  assigned_user_name: string | null
  assignment_accepted_at: string | null
  diagnosis: { answers: Record<string, boolean>; notes: string | null } | null
  diagnosis_completed_at: string | null
  labor_lines: ROLaborLine[]
  part_lines: ROPartLine[]
  status_events: ROStatusEvent[]
}

export interface MechanicSummary {
  id: number
  name: string
  active_orders: number
}

export interface RepairOrderListResponse {
  items: RepairOrderSummary[]
  total: number
  page: number
  page_size: number
}

export interface RepairOrderCreateInput {
  customer_id: number
  vehicle_id?: number | null
  description: string
  priority?: string | null
  estimated_cost_minor?: number | null
  estimated_cost_currency?: string | null
}

export interface RepairOrderUpdateInput {
  description?: string
  priority?: string | null
  estimated_cost_minor?: number | null
  estimated_cost_currency?: string | null
  notes?: string | null
}

export interface StatusTransitionInput {
  new_status: ROStatus
  reason?: string | null
}

export interface LaborLineInput {
  labor_type: string
  duration_minutes?: number
  rate_minor: number
}

export interface PartLineInput {
  part_name: string
  quantity: number
  unit_cost_minor: number
  // Public id of the catalogue part — when set, the backend reserves stock.
  part_public_id?: string
  remise_pct?: number
  tva_pct?: number
}

export const STATUS_LABELS: Record<ROStatus, string> = {
  created: 'Créé',
  diagnosis: 'Diagnostic',
  in_repair: 'En réparation',
  finished: 'Terminé',
  delivered: 'Livré',
  paused_parts: 'En attente de pièces',
}

export const ALLOWED_TRANSITIONS: Record<ROStatus, ROStatus[]> = {
  created: ['diagnosis'],
  diagnosis: ['in_repair'],
  in_repair: ['paused_parts', 'finished'],
  paused_parts: ['in_repair'],
  finished: ['delivered'],
  delivered: [],
}

export interface TimeEntry {
  id: number
  ro_id: number
  user_id: number
  started_at: string
  ended_at: string | null
  duration_minutes: number | null
  notes: string | null
}

export interface TimeEntryListResponse {
  items: TimeEntry[]
  total: number
}

export interface Comment {
  id: number
  ro_id: number
  user_id: number | null
  body: string
  created_at: string
  updated_at: string
}

export interface CommentListResponse {
  items: Comment[]
  total: number
}

export interface ROPhotoSummary {
  id: number
  ro_id: number
  uploaded_by_user_id: number | null
  filename: string
  mime_type: string
  size_bytes: number
  created_at: string
  url: string
}

export interface ROPhotoListResponse {
  items: ROPhotoSummary[]
  total: number
}

export const repairOrderApi = {
  list(params?: {
    status?: ROStatus
    customer_id?: number
    vehicle_id?: number
    assigned_user_id?: number
    include_deleted?: boolean
    page?: number
    page_size?: number
  }): Promise<RepairOrderListResponse> {
    return apiClient.get('/repair-orders', { params }).then((r) => r.data)
  },

  get(publicId: string): Promise<RepairOrderDetail> {
    return apiClient.get(`/repair-orders/${publicId}`).then((r) => r.data)
  },

  create(input: RepairOrderCreateInput): Promise<RepairOrderDetail> {
    return apiClient.post('/repair-orders', input).then((r) => r.data)
  },

  update(
    publicId: string,
    version: number,
    input: RepairOrderUpdateInput
  ): Promise<RepairOrderDetail> {
    return apiClient
      .patch(`/repair-orders/${publicId}?version=${version}`, input)
      .then((r) => r.data)
  },

  transition(
    publicId: string,
    input: StatusTransitionInput
  ): Promise<RepairOrderDetail> {
    return apiClient
      .post(`/repair-orders/${publicId}/status-transition`, input)
      .then((r) => r.data)
  },

  addLaborLine(
    publicId: string,
    input: LaborLineInput
  ): Promise<RepairOrderDetail> {
    return apiClient
      .post(`/repair-orders/${publicId}/labor-lines`, input)
      .then((r) => r.data)
  },

  addPartLine(
    publicId: string,
    input: PartLineInput
  ): Promise<RepairOrderDetail> {
    return apiClient
      .post(`/repair-orders/${publicId}/part-lines`, input)
      .then((r) => r.data)
  },

  remove(publicId: string): Promise<void> {
    return apiClient.delete(`/repair-orders/${publicId}`).then(() => undefined)
  },

  restore(publicId: string): Promise<RepairOrderDetail> {
    return apiClient
      .post(`/repair-orders/${publicId}/restore`)
      .then((r) => r.data)
  },

  startTimeEntry(publicId: string, notes?: string): Promise<TimeEntry> {
    return apiClient
      .post(`/repair-orders/${publicId}/time-entries/start`, { notes: notes ?? null })
      .then((r) => r.data)
  },

  stopTimeEntry(publicId: string, notes?: string): Promise<TimeEntry> {
    return apiClient
      .post(`/repair-orders/${publicId}/time-entries/stop`, { notes: notes ?? null })
      .then((r) => r.data)
  },

  listTimeEntries(publicId: string): Promise<TimeEntryListResponse> {
    return apiClient
      .get(`/repair-orders/${publicId}/time-entries`)
      .then((r) => r.data)
  },

  createComment(publicId: string, body: string): Promise<Comment> {
    return apiClient
      .post(`/repair-orders/${publicId}/comments`, { body })
      .then((r) => r.data)
  },

  listComments(publicId: string): Promise<CommentListResponse> {
    return apiClient
      .get(`/repair-orders/${publicId}/comments`)
      .then((r) => r.data)
  },

  updateComment(publicId: string, commentId: number, body: string): Promise<Comment> {
    return apiClient
      .put(`/repair-orders/${publicId}/comments/${commentId}`, { body })
      .then((r) => r.data)
  },

  deleteComment(publicId: string, commentId: number): Promise<void> {
    return apiClient
      .delete(`/repair-orders/${publicId}/comments/${commentId}`)
      .then(() => undefined)
  },

  assignMechanic(publicId: string, userId: number | null): Promise<RepairOrderDetail> {
    return apiClient
      .put(`/repair-orders/${publicId}/assign`, { user_id: userId })
      .then((r) => r.data)
  },

  listMechanics(): Promise<MechanicSummary[]> {
    return apiClient.get('/repair-orders/mechanics').then((r) => r.data)
  },

  acceptAssignment(publicId: string): Promise<RepairOrderDetail> {
    return apiClient
      .post(`/repair-orders/${publicId}/accept-assignment`)
      .then((r) => r.data)
  },

  saveDiagnosis(
    publicId: string,
    body: { answers: Record<string, boolean>; notes: string | null; completed: boolean },
  ): Promise<RepairOrderDetail> {
    return apiClient
      .put(`/repair-orders/${publicId}/diagnosis`, body)
      .then((r) => r.data)
  },

  uploadPhoto(publicId: string, file: File): Promise<ROPhotoSummary> {
    const form = new FormData()
    form.append('file', file)
    return apiClient
      .post(`/repair-orders/${publicId}/photos`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },

  listPhotos(publicId: string): Promise<ROPhotoListResponse> {
    return apiClient.get(`/repair-orders/${publicId}/photos`).then((r) => r.data)
  },

  getPdfUrl(publicId: string): Promise<{ url: string; expires_in: number }> {
    return apiClient.get(`/repair-orders/${publicId}/pdf`).then((r) => r.data)
  },
}
