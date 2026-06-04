import axios, {
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: false,
})

// Attach access token from localStorage on every request
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
)

// Handle 401: attempt silent token refresh, else redirect to /login
let isRefreshing = false
type PendingEntry = { resolve: (token: string) => void; reject: (err: unknown) => void }
let pendingRequests: PendingEntry[] = []

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }

    // Never intercept auth endpoints — their 401s are credential errors, not expired tokens
    const url = original.url ?? ''
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/refresh') || url.includes('/auth/logout')

    if (error.response?.status === 401 && !original._retry && !isAuthEndpoint) {
      if (isRefreshing) {
        // Queue this request until the in-flight refresh completes or fails.
        // Both resolve AND reject paths are wired so the promise always settles.
        return new Promise((resolve, reject) => {
          pendingRequests.push({
            resolve: (token) => {
              original.headers.Authorization = `Bearer ${token}`
              resolve(apiClient(original))
            },
            reject,
          })
        })
      }

      original._retry = true
      isRefreshing = true

      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (!refreshToken) throw new Error('No refresh token')

        const { data } = await axios.post(`${BASE_URL}/api/v1/auth/refresh`, {
          refresh_token: refreshToken,
        })

        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)

        const queue = pendingRequests
        pendingRequests = []
        isRefreshing = false
        queue.forEach(({ resolve }) => resolve(data.access_token))

        original.headers.Authorization = `Bearer ${data.access_token}`
        return apiClient(original)
      } catch (refreshError) {
        const queue = pendingRequests
        pendingRequests = []
        isRefreshing = false
        // Reject all queued promises so their callers (e.g. logout) can settle
        queue.forEach(({ reject }) => reject(refreshError))
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('auth_user')
        window.location.href = '/login'
        return Promise.reject(error)
      }
    }

    return Promise.reject(error)
  },
)
