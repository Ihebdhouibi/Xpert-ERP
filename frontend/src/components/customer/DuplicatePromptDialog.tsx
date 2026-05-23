import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material'
import type {
  CustomerSummary,
  MergeMatchReason,
} from '../../lib/customerApi'

interface DuplicatePromptDialogProps {
  open: boolean
  existing: CustomerSummary | null
  reason: MergeMatchReason | null
  onUseExisting: (publicId: string) => void
  onClose: () => void
}

const REASON_LABELS: Record<MergeMatchReason, string> = {
  phone_and_fiscal_id:
    'Un client existant partage le même identifiant fiscal et le même numéro de téléphone.',
  email_and_fiscal_id:
    'Un client existant partage le même identifiant fiscal et la même adresse email.',
  fiscal_id_only:
    'Un client existant utilise déjà cet identifiant fiscal.',
}

export function DuplicatePromptDialog({
  open,
  existing,
  reason,
  onUseExisting,
  onClose,
}: DuplicatePromptDialogProps) {
  if (!existing || !reason) return null

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Client en doublon détecté</DialogTitle>
      <DialogContent dividers>
        <Alert severity="warning" sx={{ mb: 2 }}>
          {REASON_LABELS[reason]}
        </Alert>
        <Typography variant="subtitle2" gutterBottom>
          Client existant :
        </Typography>
        <Stack spacing={0.5}>
          <Typography>
            <b>{existing.full_name}</b>
            {existing.company_name ? ` — ${existing.company_name}` : ''}
          </Typography>
          {existing.phone_e164 && (
            <Typography color="text.secondary" variant="body2">
              📞 {existing.phone_e164}
            </Typography>
          )}
          {existing.email && (
            <Typography color="text.secondary" variant="body2">
              ✉ {existing.email}
            </Typography>
          )}
          <Typography color="text.secondary" variant="body2">
            Statut : {existing.status}
          </Typography>
        </Stack>
        <Typography variant="body2" sx={{ mt: 2 }} color="text.secondary">
          Que souhaitez-vous faire ?
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Modifier la saisie</Button>
        <Button
          variant="contained"
          onClick={() => onUseExisting(existing.id)}
        >
          Utiliser le client existant
        </Button>
      </DialogActions>
    </Dialog>
  )
}
