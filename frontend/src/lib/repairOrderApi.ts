import { apiClient } from './apiClient'

export type ROStatus =
  | 'created'
  | 'diagnosis'
  | 'in_repair'
  | 'finished'
  | 'delivered'
  | 'paused_parts'
  | 'paused_approval'

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
  vehicle_id: number | null
  description: string
  status: ROStatus
  priority: string | null
  estimated_cost_minor: number | null
  estimated_cost_currency: string | null
  actual_cost_minor: number
  created_at: string
}

export interface RepairOrderDetail extends RepairOrderSummary {
  notes: string | null
  updated_at: string
  version: number
  labor_lines: ROLaborLine[]
  part_lines: ROPartLine[]
  status_events: ROStatusEvent[]
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
  duration_minutes: number
  rate_minor: number
}

export interface PartLineInput {
  part_name: string
  quantity: number
  unit_cost_minor: number
}

export const STATUS_LABELS: Record<ROStatus, string> = {
  created: 'Créé',
  diagnosis: 'Diagnostic',
  in_repair: 'En réparation',
  finished: 'Terminé',
  delivered: 'Livré',
  paused_parts: 'En attente de pièces',
  paused_approval: 'En attente d\'approbation',
}

export const ALLOWED_TRANSITIONS: Record<ROStatus, ROStatus[]> = {
  created: ['diagnosis', 'paused_approval'],
  diagnosis: ['in_repair', 'paused_parts', 'paused_approval'],
  in_repair: ['finished', 'paused_parts', 'paused_approval'],
  finished: ['delivered', 'paused_approval'],
  delivered: [],
  paused_parts: ['in_repair', 'diagnosis'],
  paused_approval: ['in_repair', 'diagnosis', 'created'],
}

export const repairOrderApi = {
  list(params?: {
    status?: ROStatus
    customer_id?: number
    vehicle_id?: number
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
}
