import { useAuth } from '../../contexts/AuthContext'
import type { ReactNode } from 'react'

interface PermissionGateProps {
  permission: string
  children: ReactNode
  fallback?: ReactNode
}

export function PermissionGate({
  permission,
  children,
  fallback = null,
}: PermissionGateProps) {
  const { user } = useAuth()
  if (!user?.permissions.includes(permission)) return <>{fallback}</>
  return <>{children}</>
}
