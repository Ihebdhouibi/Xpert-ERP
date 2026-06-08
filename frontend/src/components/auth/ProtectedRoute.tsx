import { Navigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import type { ReactNode } from 'react'

interface ProtectedRouteProps {
  children: ReactNode
  requiredPermission?: string
  /** Redirect away if the user holds any of these roles (e.g. mechanic). */
  deniedRoles?: string[]
}

export function ProtectedRoute({
  children,
  requiredPermission,
  deniedRoles,
}: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (requiredPermission && !user?.permissions.includes(requiredPermission)) {
    return <Navigate to="/" replace />
  }

  if (deniedRoles && user?.roles.some((r) => deniedRoles.includes(r))) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
