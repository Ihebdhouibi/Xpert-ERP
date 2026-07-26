import { apiClient } from './apiClient'

export type FuelType = 'gasoline' | 'diesel' | 'hybrid' | 'ev' | 'lpg' | 'cng'
export type VehicleStatus = 'active' | 'inactive' | 'scrapped'

export const FUEL_TYPE_LABELS: Record<FuelType, string> = {
  gasoline: 'Essence',
  diesel: 'Diesel',
  hybrid: 'Hybride',
  ev: 'Électrique',
  lpg: 'GPL',
  cng: 'GNV',
}

export const VEHICLE_STATUS_LABELS: Record<VehicleStatus, string> = {
  active: 'Actif',
  inactive: 'Inactif',
  scrapped: 'Épave',
}

export interface VehicleOut {
  id: number
  garage_id: number
  customer_id: number | null
  customer_name: string | null
  registration: string | null
  vin: string | null
  make: string
  model: string
  year: number | null
  fuel_type: FuelType | null
  color: string | null
  mileage_current: number | null
  last_service_at: string | null
  technical_inspection_due_at: string | null
  maintenance_due_at: string | null
  status: VehicleStatus
  version: number
  created_at: string
  updated_at: string
}

export interface VehicleListResponse {
  items: VehicleOut[]
  total: number
  page: number
  page_size: number
}

export interface VehicleCreateInput {
  customer_id?: number | null
  registration?: string | null
  vin?: string | null
  make: string
  model: string
  year?: number | null
  fuel_type?: FuelType | null
  color?: string | null
  mileage_current?: number | null
  technical_inspection_due_at?: string | null
  maintenance_due_at?: string | null
}

export interface VehicleUpdateInput {
  customer_id?: number | null
  make?: string
  model?: string
  year?: number | null
  fuel_type?: FuelType | null
  color?: string | null
  mileage_current?: number | null
  last_service_at?: string | null
  technical_inspection_due_at?: string | null
  maintenance_due_at?: string | null
  status?: VehicleStatus
}

export interface OwnershipTransferInput {
  new_customer_id: number | null
  note?: string | null
}

export interface ReRegistrationInput {
  new_registration: string
  note?: string | null
}

export interface OwnershipHistoryOut {
  id: number
  vehicle_id: number
  previous_customer_id: number | null
  new_customer_id: number | null
  transferred_by: number | null
  note: string | null
  transferred_at: string
}

export interface RegistrationAliasOut {
  id: number
  registration: string
  valid_until: string | null
  note: string | null
  created_at: string
}

export interface VehicleROSummary {
  id: number
  public_id: string
  status: string
  description: string
  created_at: string
}

export interface VehicleHistoryOut {
  vehicle: VehicleOut
  ownership_history: OwnershipHistoryOut[]
  registration_aliases: RegistrationAliasOut[]
  repair_orders: VehicleROSummary[]
}

export const vehiclesApi = {
  list(params?: {
    q?: string
    customer_id?: number
    status?: VehicleStatus
    page?: number
    page_size?: number
  }): Promise<VehicleListResponse> {
    return apiClient.get('/vehicles', { params }).then(r => r.data)
  },

  get(id: number): Promise<VehicleOut> {
    return apiClient.get(`/vehicles/${id}`).then(r => r.data)
  },

  create(input: VehicleCreateInput): Promise<VehicleOut> {
    return apiClient.post('/vehicles', input).then(r => r.data)
  },

  update(id: number, version: number, input: VehicleUpdateInput): Promise<VehicleOut> {
    return apiClient
      .patch(`/vehicles/${id}`, input, { headers: { 'If-Match': String(version) } })
      .then(r => r.data)
  },

  remove(id: number): Promise<void> {
    return apiClient.delete(`/vehicles/${id}`).then(() => undefined)
  },

  transferOwnership(id: number, input: OwnershipTransferInput): Promise<VehicleOut> {
    return apiClient.post(`/vehicles/${id}/transfer-ownership`, input).then(r => r.data)
  },

  reRegister(id: number, input: ReRegistrationInput): Promise<VehicleOut> {
    return apiClient.post(`/vehicles/${id}/re-register`, input).then(r => r.data)
  },

  getHistory(id: number): Promise<VehicleHistoryOut> {
    return apiClient.get(`/vehicles/${id}/history`).then(r => r.data)
  },

  getMakes(): Promise<string[]> {
    return apiClient.get('/vehicles/makes').then(r => r.data)
  },

  getModels(make: string): Promise<string[]> {
    return apiClient.get('/vehicles/models', { params: { make } }).then(r => r.data)
  },

  removeMake(name: string): Promise<void> {
    return apiClient.delete(`/vehicles/makes/${encodeURIComponent(name)}`).then(() => undefined)
  },

  removeModel(make: string, name: string): Promise<void> {
    return apiClient
      .delete(`/vehicles/models/${encodeURIComponent(make)}/${encodeURIComponent(name)}`)
      .then(() => undefined)
  },
}
