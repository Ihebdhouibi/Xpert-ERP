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

export interface AppNotification {
  id: number
  title: string
  body: string | null
  link: string | null
  read_at: string | null
  created_at: string
}

export interface InboxResponse {
  items: AppNotification[]
  unread_count: number
}

export interface NotificationHistoryResponse {
  items: AppNotification[]
  total: number
  page: number
  page_size: number
  unread_count: number
}

export const inboxApi = {
  list: () => apiClient.get<InboxResponse>('/notifications').then(r => r.data),
  history: (params: { page: number; page_size: number; unread_only?: boolean }) =>
    apiClient.get<NotificationHistoryResponse>('/notifications/history', { params }).then(r => r.data),
  markRead: (id: number) => apiClient.post(`/notifications/${id}/read`).then(r => r.data),
  markAllRead: () => apiClient.post('/notifications/read-all').then(r => r.data),
  sendEmail: (id: number, recipient: 'client' | 'admin') =>
    apiClient
      .post(`/notifications/${id}/send-email`, {}, { params: { recipient } })
      .then(r => r.data),
}

/** True for notifications that support the "send email" action (échéance / credit-limit alerts). */
export function notificationSupportsEmail(link: string | null): boolean {
  return !!link && /^\/(invoices|customers)\/[^/]+$/.test(link)
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
