import { apiClient } from './apiClient'

export interface TriggerEntry {
  code: string
  label: string
  description: string
  type: 'event' | 'scheduled'
  channels: string[]
}

export interface NotificationTemplate {
  id: number
  garage_id: number
  code: string
  channel: string
  locale: string
  subject: string | null
  body: string
  active: boolean
  updated_at: string
  is_override: boolean
}

export interface TemplateUpdatePayload {
  subject?: string | null
  body: string
  active: boolean
}

export interface PreviewRequest {
  context?: Record<string, string>
}

export interface PreviewResponse {
  subject: string | null
  body: string
}

export const notificationApi = {
  triggers: () =>
    apiClient.get<TriggerEntry[]>('/notification-templates/triggers').then(r => r.data),

  list: () =>
    apiClient.get<NotificationTemplate[]>('/notification-templates').then(r => r.data),

  get: (id: number) =>
    apiClient.get<NotificationTemplate>(`/notification-templates/${id}`).then(r => r.data),

  update: (id: number, payload: TemplateUpdatePayload) =>
    apiClient.put<NotificationTemplate>(`/notification-templates/${id}`, payload).then(r => r.data),

  preview: (id: number, req: PreviewRequest = {}) =>
    apiClient.post<PreviewResponse>(`/notification-templates/${id}/preview`, req).then(r => r.data),
}
