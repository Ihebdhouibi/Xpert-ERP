import { useState } from 'react'
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import PaymentsRoundedIcon from '@mui/icons-material/PaymentsRounded'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { paymentApi, PAYMENT_METHOD_LABELS, type PaymentMethod } from '../../lib/paymentApi'
import type { InvoiceOut } from '../../lib/invoiceApi'
import { formatMinor } from '../ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

interface Props {
  open: boolean
  onClose: () => void
  invoice: InvoiceOut
}

const today = () => new Date().toISOString().slice(0, 10)

export function RecordPaymentDialog({ open, onClose, invoice }: Props) {
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()

  const maxMinor = invoice.outstanding_minor
  const maxAmount = maxMinor / 100

  const [amountStr, setAmountStr] = useState<string>(String(maxAmount))
  const [method, setMethod] = useState<PaymentMethod>('cash')
  const [paidAt, setPaidAt] = useState<string>(today())
  const [reference, setReference] = useState<string>('')
  const [notes, setNotes] = useState<string>('')

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
      paymentApi.create({
        invoice_id: invoice.id,
        amount_minor: amountMinor,
        payment_method: method,
        paid_at: paidAt ? new Date(paidAt).toISOString() : null,
        reference: reference.trim() || null,
        notes: notes.trim() || null,
      }),
    onSuccess: () => {
      success('Paiement enregistré')
      queryClient.invalidateQueries({ queryKey: ['invoice', invoice.public_id] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      queryClient.invalidateQueries({ queryKey: ['payment-history', invoice.id] })
      handleClose()
    },
    onError: () => toastError('Impossible d\'enregistrer le paiement.'),
  })

  const handleClose = () => {
    setAmountStr(String(maxAmount))
    setMethod('cash')
    setPaidAt(today())
    setReference('')
    setNotes('')
    onClose()
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, pb: 1 }}>
        <PaymentsRoundedIcon sx={{ color: 'primary.main', fontSize: 22 }} />
        Enregistrer un paiement
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ pt: 2.5 }}>
        <Stack spacing={2.5}>
          <Stack direction="row" justifyContent="space-between" alignItems="center"
            sx={{ bgcolor: '#F8FAFC', borderRadius: 1.5, px: 2, py: 1.25 }}>
            <Typography variant="body2" color="text.secondary" fontWeight={500}>
              Restant dû
            </Typography>
            <Typography variant="body2" fontWeight={700} color="error.main">
              {formatMinor(maxMinor, invoice.currency)}
            </Typography>
          </Stack>

          <TextField
            label="Montant"
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

          <FormControl fullWidth size="small">
            <InputLabel>Moyen de paiement</InputLabel>
            <Select
              label="Moyen de paiement"
              value={method}
              onChange={e => setMethod(e.target.value as PaymentMethod)}
            >
              {(Object.entries(PAYMENT_METHOD_LABELS) as [PaymentMethod, string][]).map(([val, label]) => (
                <MenuItem key={val} value={val}>{label}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            label="Date de paiement"
            type="date"
            value={paidAt}
            onChange={e => setPaidAt(e.target.value)}
            fullWidth
            size="small"
            InputLabelProps={{ shrink: true }}
          />

          <TextField
            label="Référence (optionnel)"
            placeholder="N° chèque, réf. virement…"
            value={reference}
            onChange={e => setReference(e.target.value)}
            fullWidth
            size="small"
            inputProps={{ maxLength: 100 }}
          />

          <TextField
            label="Notes (optionnel)"
            value={notes}
            onChange={e => setNotes(e.target.value)}
            fullWidth
            size="small"
            multiline
            rows={2}
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
          disabled={mutation.isPending || !!amountError || amountValue <= 0}
        >
          {mutation.isPending ? 'Enregistrement…' : 'Confirmer'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
