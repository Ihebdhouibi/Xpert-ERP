import { apiClient } from './apiClient'

export interface GarageSettingOut {
  id: number
  garage_id: number
  key: string
  value: string
  description: string | null
  updated_at: string
  updated_by: number | null
}

export interface GarageSettingListResponse {
  items: GarageSettingOut[]
  total: number
}

export const settingsApi = {
  list: (garage_id = 0) =>
    apiClient
      .get<GarageSettingListResponse>('/settings', { params: { garage_id } })
      .then(r => r.data),

  upsert: (key: string, value: string, garage_id = 0, description?: string) =>
    apiClient
      .put<GarageSettingOut>(`/settings/${key}`, { value, description }, { params: { garage_id } })
      .then(r => r.data),

  delete: (key: string, garage_id = 0) =>
    apiClient.delete(`/settings/${key}`, { params: { garage_id } }),
}
