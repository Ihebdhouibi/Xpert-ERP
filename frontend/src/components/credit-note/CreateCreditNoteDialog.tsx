import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import AccountBalanceRoundedIcon from '@mui/icons-material/AccountBalanceRounded'
import { useMutation } from '@tanstack/react-query'
import { creditNoteApi } from '../../lib/creditNoteApi'
import type { InvoiceOut } from '../../lib/invoiceApi'
import { formatMinor } from '../ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

interface Props {
  open: boolean
  onClose: () => void
  invoice: InvoiceOut
}

export function CreateCreditNoteDialog({ open, onClose, invoice }: Props) {
  const navigate = useNavigate()
  const { error: toastError } = useToast()

  const maxMinor = invoice.total_minor
  const maxAmount = maxMinor / 100

  const [amountStr, setAmountStr] = useState<string>(String(maxAmount))
  const [reason, setReason] = useState<string>('')

  const amountValue = parseFloat(amountStr) || 0
  const amountMinor = Math.round(amountValue * 100)
  const amountError =
    amountValue <= 0
      ? 'Le montant doit être supérieur à 0'
      : amountMinor > maxMinor
      ? `Le montant ne peut pas dépasser ${formatMinor(maxMinor, invoice.currency)}`
      : ''

  const mutation = useMutation({
    mutationFn: () =>
      creditNoteApi.create({
        invoice_id: invoice.id,
        total_minor: amountMinor,
        reason: reason.trim() || null,
      }),
    onSuccess: result => {
      handleClose()
      navigate(`/credit-notes/${result.id}`)
    },
    onError: () => toastError('Impossible de créer l\'avoir.'),
  })

  const handleClose = () => {
    setAmountStr(String(maxAmount))
    setReason('')
    onClose()
  }

  const canSubmit = !amountError && amountValue > 0 && !mutation.isPending

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, pb: 1 }}>
        <AccountBalanceRoundedIcon sx={{ color: '#EA580C', fontSize: 22 }} />
        Créer un avoir
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ pt: 2.5 }}>
        <Stack spacing={2.5}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            sx={{ bgcolor: '#F8FAFC', borderRadius: 1.5, px: 2, py: 1.25 }}
          >
            <Typography variant="body2" color="text.secondary" fontWeight={500}>
              Facture {invoice.doc_number}
            </Typography>
            <Typography variant="body2" fontWeight={700}>
              {formatMinor(invoice.total_minor, invoice.currency)}
            </Typography>
          </Stack>

          <TextField
            label="Montant de l'avoir (TTC)"
            type="number"
            inputProps={{ min: 0.01, max: maxAmount, step: 0.01 }}
            value={amountStr}
            onChange={e => setAmountStr(e.target.value)}
            error={!!amountError && amountStr !== ''}
            helperText={amountStr !== '' ? amountError : ''}
            fullWidth
            size="small"
            InputProps={{
              endAdornment: (
                <Typography variant="body2" color="text.secondary" sx={{ ml: 0.5, flexShrink: 0 }}>
                  {invoice.currency}
                </Typography>
              ),
            }}
          />

          <TextField
            label="Motif (optionnel)"
            placeholder="Erreur de facturation, remise oubliée, retour pièce…"
            value={reason}
            onChange={e => setReason(e.target.value)}
            fullWidth
            size="small"
            multiline
            rows={3}
            inputProps={{ maxLength: 500 }}
          />
        </Stack>
      </DialogContent>
      <Divider />
      <DialogActions sx={{ px: 3, py: 2, gap: 1 }}>
        <Button onClick={handleClose} disabled={mutation.isPending} color="inherit">
          Annuler
        </Button>
        <Button
          variant="contained"
          onClick={() => mutation.mutate()}
          disabled={!canSubmit}
          sx={{ bgcolor: '#EA580C', '&:hover': { bgcolor: '#C2410C' } }}
        >
          {mutation.isPending ? 'Création…' : 'Créer l\'avoir'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
