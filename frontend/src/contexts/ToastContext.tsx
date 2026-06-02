import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react'
import { Box, IconButton, Stack, Typography, type AlertColor } from '@mui/material'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import ErrorRoundedIcon from '@mui/icons-material/ErrorRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import InfoRoundedIcon from '@mui/icons-material/InfoRounded'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import { AnimatePresence, motion } from 'framer-motion'

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

// Design per severity — icon + muted palette, not harsh filled alerts
const TOAST_STYLES: Record<AlertColor, {
  icon: React.ReactNode
  bg: string
  border: string
  iconColor: string
  textColor: string
}> = {
  success: {
    icon: <CheckCircleRoundedIcon sx={{ fontSize: 18 }} />,
    bg: '#F0FDF4',
    border: '#BBF7D0',
    iconColor: '#16A34A',
    textColor: '#15803D',
  },
  error: {
    icon: <ErrorRoundedIcon sx={{ fontSize: 18 }} />,
    bg: '#FEF2F2',
    border: '#FECACA',
    iconColor: '#DC2626',
    textColor: '#B91C1C',
  },
  warning: {
    icon: <WarningAmberRoundedIcon sx={{ fontSize: 18 }} />,
    bg: '#FFFBEB',
    border: '#FDE68A',
    iconColor: '#D97706',
    textColor: '#92400E',
  },
  info: {
    icon: <InfoRoundedIcon sx={{ fontSize: 18 }} />,
    bg: '#EFF6FF',
    border: '#BFDBFE',
    iconColor: '#2563EB',
    textColor: '#1D4ED8',
  },
}

function ToastItem({ item, onDismiss }: { item: ToastItem; onDismiss: () => void }) {
  const style = TOAST_STYLES[item.severity]

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 48, scale: 0.96 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 48, scale: 0.96 }}
      transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
    >
      <Box
        sx={{
          minWidth: 300,
          maxWidth: 420,
          bgcolor: style.bg,
          border: '1px solid',
          borderColor: style.border,
          borderRadius: 2,
          px: 2,
          py: 1.25,
          boxShadow: '0 4px 16px rgba(0,0,0,0.10)',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 1.25,
        }}
      >
        <Box sx={{ color: style.iconColor, mt: 0.125, flexShrink: 0 }}>
          {style.icon}
        </Box>
        <Typography
          variant="body2"
          fontWeight={500}
          color={style.textColor}
          flex={1}
          lineHeight={1.5}
        >
          {item.message}
        </Typography>
        <IconButton
          size="small"
          onClick={onDismiss}
          sx={{
            p: 0.25,
            mt: -0.25,
            mr: -0.5,
            color: style.iconColor,
            opacity: 0.6,
            '&:hover': { opacity: 1, bgcolor: 'transparent' },
          }}
        >
          <CloseRoundedIcon sx={{ fontSize: 15 }} />
        </IconButton>
      </Box>
    </motion.div>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const toast = useCallback((message: string, severity: AlertColor = 'info') => {
    const id = ++nextId
    setToasts(prev => [...prev.slice(-2), { id, message, severity }])
    // Auto-dismiss
    const duration = severity === 'error' ? 6000 : 4000
    setTimeout(() => dismiss(id), duration)
  }, [dismiss])

  const success = useCallback((m: string) => toast(m, 'success'), [toast])
  const error   = useCallback((m: string) => toast(m, 'error'),   [toast])
  const warning = useCallback((m: string) => toast(m, 'warning'), [toast])
  const info    = useCallback((m: string) => toast(m, 'info'),    [toast])

  return (
    <ToastContext.Provider value={{ toast, success, error, warning, info }}>
      {children}

      {/* Fixed bottom-right toast stack */}
      <Box
        sx={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          zIndex: 1500,
          display: 'flex',
          flexDirection: 'column',
          gap: 1,
          alignItems: 'flex-end',
          pointerEvents: 'none',
          '& > *': { pointerEvents: 'all' },
        }}
      >
        <AnimatePresence mode="popLayout">
          {toasts.map(t => (
            <ToastItem key={t.id} item={t} onDismiss={() => dismiss(t.id)} />
          ))}
        </AnimatePresence>
      </Box>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}
