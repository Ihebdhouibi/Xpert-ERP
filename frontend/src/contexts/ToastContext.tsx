import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react'
import { Alert, Snackbar, type AlertColor } from '@mui/material'

interface ToastItem {
  id: number
  message: string
  severity: AlertColor
}

interface ToastContextValue {
  toast: (message: string, severity?: AlertColor) => void
  success: (message: string) => void
  error: (message: string) => void
  warning: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

let nextId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const toast = useCallback((message: string, severity: AlertColor = 'info') => {
    const id = ++nextId
    setToasts(prev => [...prev.slice(-2), { id, message, severity }])
  }, [])

  const success = useCallback((m: string) => toast(m, 'success'), [toast])
  const error = useCallback((m: string) => toast(m, 'error'), [toast])
  const warning = useCallback((m: string) => toast(m, 'warning'), [toast])
  const info = useCallback((m: string) => toast(m, 'info'), [toast])

  return (
    <ToastContext.Provider value={{ toast, success, error, warning, info }}>
      {children}
      {toasts.map(t => (
        <Snackbar
          key={t.id}
          open
          autoHideDuration={t.severity === 'error' ? 6000 : 4000}
          onClose={() => dismiss(t.id)}
          sx={{ bottom: { xs: 16, sm: 24 } }}
        >
          <Alert
            onClose={() => dismiss(t.id)}
            severity={t.severity}
            variant="filled"
            sx={{
              width: '100%',
              minWidth: 320,
              borderRadius: 2,
              fontWeight: 500,
              boxShadow: '0 10px 25px rgb(0 0 0 / 0.15)',
            }}
          >
            {t.message}
          </Alert>
        </Snackbar>
      ))}
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}
