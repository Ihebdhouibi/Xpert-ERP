import { apiClient } from './apiClient'

export type UserStatus = 'active' | 'inactive' | 'locked'

export interface UserSummary {
  id: string
  garage_id: number
  email: string
  full_name: string
  status: UserStatus
  roles: string[]
  last_login_at: string | null
  created_at: string
}

export interface UserListResponse {
  items: UserSummary[]
  total: number
  page: number
  page_size: number
}

export interface UserCreateRequest {
  email: string
  full_name: string
  password: string
  role_codes: string[]
}

export interface UserUpdateRequest {
  full_name?: string
  status?: 'active' | 'inactive'
}

export const usersApi = {
  list: (params?: { page?: number; page_size?: number }) =>
    apiClient.get<UserListResponse>('/users', { params }).then(r => r.data),

  create: (body: UserCreateRequest) =>
    apiClient.post<UserSummary>('/users', body).then(r => r.data),

  update: (publicId: string, body: UserUpdateRequest) =>
    apiClient.patch<UserSummary>(`/users/${publicId}`, body).then(r => r.data),

  assignRoles: (publicId: string, role_codes: string[]) =>
    apiClient.post<UserSummary>(`/users/${publicId}/roles`, { role_codes }).then(r => r.data),

  deactivate: (publicId: string) =>
    apiClient.delete(`/users/${publicId}`),
}
