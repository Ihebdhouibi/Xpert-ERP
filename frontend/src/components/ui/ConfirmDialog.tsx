import type { ReactNode } from 'react'
import {
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Typography,
} from '@mui/material'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import DeleteRoundedIcon from '@mui/icons-material/DeleteRounded'

interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  loading?: boolean
  dangerous?: boolean
  confirmDisabled?: boolean
  children?: ReactNode
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirmer',
  cancelLabel = 'Annuler',
  loading = false,
  dangerous = false,
  confirmDisabled = false,
  children,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      maxWidth="xs"
      fullWidth
      PaperProps={{ sx: { borderRadius: 3 } }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        {dangerous ? (
          <DeleteRoundedIcon sx={{ color: 'error.main', fontSize: 22 }} />
        ) : (
          <WarningAmberRoundedIcon sx={{ color: 'warning.main', fontSize: 22 }} />
        )}
        {title}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" lineHeight={1.7}>
          {message}
        </Typography>
        {children}
      </DialogContent>
      <DialogActions>
        <Button variant="outlined" onClick={onCancel} disabled={loading}>
          {cancelLabel}
        </Button>
        <Button
          variant="contained"
          color={dangerous ? 'error' : 'primary'}
          onClick={onConfirm}
          disabled={loading || confirmDisabled}
          startIcon={loading ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
