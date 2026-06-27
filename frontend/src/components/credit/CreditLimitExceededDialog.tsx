import { useState } from 'react'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  Stack,
  Typography,
} from '@mui/material'
import BlockRoundedIcon from '@mui/icons-material/BlockRounded'
import SendRoundedIcon from '@mui/icons-material/SendRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import {
  creditOverrideApi,
  formatMinorEur,
  type CreditLimitExceededDetail,
} from '../../lib/creditOverrideApi'

interface Props {
  open: boolean
  detail: CreditLimitExceededDetail | null
  documentPublicId: string
  onClose: () => void
}

export function CreditLimitExceededDialog({ open, detail, documentPublicId, onClose }: Props) {
  const [loading, setLoading] = useState(false)
  const [requested, setRequested] = useState(false)
  const [requestError, setRequestError] = useState<string | null>(null)

  const handleRequestOverride = async () => {
    if (!detail?.customer_public_id) return
    setLoading(true)
    setRequestError(null)
    try {
      await creditOverrideApi.request(detail.customer_public_id, detail.doc_type, documentPublicId)
      setRequested(true)
    } catch {
      setRequestError("Impossible d'envoyer la demande. Réessayez.")
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setRequested(false)
    setRequestError(null)
    onClose()
  }

  if (!detail) return null

  const ratio = detail.limit > 0 ? Math.min((detail.outstanding / detail.limit) * 100, 100) : 100
  const projected = Math.min(((detail.outstanding + detail.additional) / detail.limit) * 100, 100)

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth PaperProps={{ sx: { borderRadius: 3 } }}>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <BlockRoundedIcon sx={{ color: 'error.main', fontSize: 22 }} />
        Limite de crédit dépassée
      </DialogTitle>

      <DialogContent>
        {requested ? (
          <Stack alignItems="center" spacing={2} py={2}>
            <CheckCircleRoundedIcon sx={{ color: 'success.main', fontSize: 48 }} />
            <Typography variant="body1" fontWeight={600} textAlign="center">
              Demande envoyée à l'administrateur
            </Typography>
            <Typography variant="body2" color="text.secondary" textAlign="center">
              Vous serez notifié dès que l'administrateur aura pris une décision.
              Une fois approuvé, vous aurez 24 heures pour émettre le document.
            </Typography>
          </Stack>
        ) : (
          <Stack spacing={2.5}>
            <Typography variant="body2" color="text.secondary">
              L'encours de ce client dépasse sa limite de crédit. Vous ne pouvez pas émettre ce document sans approbation de l'administrateur.
            </Typography>

            <Box>
              <Stack direction="row" justifyContent="space-between" mb={0.5}>
                <Typography variant="caption" color="text.secondary">Encours actuel</Typography>
                <Typography variant="caption" fontWeight={600} color="error.main">
                  {formatMinorEur(detail.outstanding)}
                </Typography>
              </Stack>
              <LinearProgress
                variant="determinate"
                value={ratio}
                color="error"
                sx={{ height: 8, borderRadius: 4 }}
              />
              <Stack direction="row" justifyContent="space-between" mt={0.5}>
                <Typography variant="caption" color="text.secondary">
                  Après émission : {formatMinorEur(detail.outstanding + detail.additional)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Limite : {formatMinorEur(detail.limit)}
                </Typography>
              </Stack>
            </Box>

            {projected > ratio && (
              <Box>
                <Stack direction="row" justifyContent="space-between" mb={0.5}>
                  <Typography variant="caption" color="text.secondary">Projection après émission</Typography>
                  <Typography variant="caption" fontWeight={600} color="warning.main">
                    {projected.toFixed(0)} %
                  </Typography>
                </Stack>
                <LinearProgress
                  variant="determinate"
                  value={projected}
                  color="warning"
                  sx={{ height: 6, borderRadius: 4 }}
                />
              </Box>
            )}

            {requestError && (
              <Alert severity="error">{requestError}</Alert>
            )}

            <Alert severity="info" icon={false}>
              En cliquant sur <strong>Demander une dérogation</strong>, une notification sera envoyée à l'administrateur pour validation.
            </Alert>
          </Stack>
        )}
      </DialogContent>

      <DialogActions>
        <Button variant="outlined" onClick={handleClose}>
          {requested ? 'Fermer' : 'Annuler'}
        </Button>
        {!requested && (
          <Button
            variant="contained"
            color="primary"
            onClick={handleRequestOverride}
            disabled={loading || !detail.customer_public_id}
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <SendRoundedIcon />}
          >
            Demander une dérogation
          </Button>
        )}
      </DialogActions>
    </Dialog>
  )
}
