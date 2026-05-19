import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react'
import { apiClient } from '../lib/apiClient'

const GARAGE_ID = import.meta.env.VITE_GARAGE_ID ?? '1'

interface User {
  id: string
  email: string
  full_name: string
  roles: string[]
  permissions: string[]
  garage_id: string
}

interface AuthContextValue {
  user: User | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const storedUser = localStorage.getItem('auth_user')
  const [user, setUser] = useState<User | null>(
    storedUser ? (JSON.parse(storedUser) as User) : null,
  )

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await apiClient.post<{
      access_token: string
      refresh_token: string
      user: User
    }>('/auth/login', { email, password }, { headers: { 'X-Garage-ID': GARAGE_ID } })

    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    localStorage.setItem('auth_user', JSON.stringify(data.user))
    setUser(data.user)
  }, [])

  const logout = useCallback(async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        await apiClient.post('/auth/logout', { refresh_token: refreshToken })
      }
    } finally {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('auth_user')
      setUser(null)
    }
  }, [])

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated: user !== null, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
