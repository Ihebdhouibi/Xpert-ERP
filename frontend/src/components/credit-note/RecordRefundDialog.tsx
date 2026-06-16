import { useState, useEffect } from 'react'
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
import MoneyOffRoundedIcon from '@mui/icons-material/MoneyOffRounded'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { creditNoteApi, type CreditNoteOut } from '../../lib/creditNoteApi'
import { paymentApi, PAYMENT_METHOD_LABELS, type PaymentMethod, type PaymentOut } from '../../lib/paymentApi'
import { formatMinor } from '../ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

interface Props {
  open: boolean
  onClose: () => void
  avoir: CreditNoteOut
  remainingRefundMinor: number
}

export function RecordRefundDialog({ open, onClose, avoir, remainingRefundMinor }: Props) {
  const qc = useQueryClient()
  const { success, error: toastError } = useToast()

  const [selectedPaymentId, setSelectedPaymentId] = useState<number | ''>('')
  const [amountStr, setAmountStr] = useState<string>(String(remainingRefundMinor / 100))
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash')
  const [reference, setReference] = useState<string>('')

  const { data: payments } = useQuery({
    queryKey: ['payment-history', avoir.invoice_id],
    queryFn: () => paymentApi.listByInvoice(avoir.invoice_id),
    enabled: open,
  })

  // Auto-select when only one payment
  useEffect(() => {
    if (payments && payments.length === 1 && selectedPaymentId === '') {
      setSelectedPaymentId(payments[0].id)
      setPaymentMethod(payments[0].payment_method)
    }
  }, [payments, selectedPaymentId])

  const selectedPayment: PaymentOut | undefined = payments?.find(p => p.id === selectedPaymentId)

  const amountValue = parseFloat(amountStr) || 0
  const amountMinor = Math.round(amountValue * 100)
  const amountError =
    amountValue <= 0
      ? 'Le montant doit être supérieur à 0'
      : amountMinor > remainingRefundMinor
      ? `Le montant ne peut pas dépasser ${formatMinor(remainingRefundMinor)}`
      : ''

  const mutation = useMutation({
    mutationFn: () =>
      creditNoteApi.createRefund({
        payment_id: selectedPayment!.id,
        amount_minor: amountMinor,
        payment_method: paymentMethod,
        reference: reference.trim() || null,
        credit_note_id: avoir.id,
      }),
    onSuccess: () => {
      success('Remboursement enregistré.')
      qc.invalidateQueries({ queryKey: ['credit-note', String(avoir.id)] })
      qc.invalidateQueries({ queryKey: ['payment-history', avoir.invoice_id] })
      handleClose()
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail
      toastError(typeof detail === 'string' ? detail : 'Impossible d\'enregistrer le remboursement.')
    },
  })

  const handleClose = () => {
    setSelectedPaymentId('')
    setAmountStr(String(remainingRefundMinor / 100))
    setPaymentMethod('cash')
    setReference('')
    onClose()
  }

  const canSubmit =
    !!selectedPayment && !amountError && amountValue > 0 && !mutation.isPending

  const showPaymentPicker = payments && payments.length > 1

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, pb: 1 }}>
        <MoneyOffRoundedIcon sx={{ color: '#EA580C', fontSize: 22 }} />
        Enregistrer un remboursement
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ pt: 2.5 }}>
        <Stack spacing={2.5}>
          {/* Context summary */}
          <Stack
            sx={{ bgcolor: '#FFF7ED', borderRadius: 1.5, px: 2, py: 1.5 }}
            spacing={0.5}
          >
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="caption" color="text.secondary" fontWeight={500}>
                Avoir {avoir.doc_number}
              </Typography>
              <Typography variant="caption" fontWeight={700} color="error.main">
                -{formatMinor(avoir.total_minor)}
              </Typography>
            </Stack>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="caption" color="text.secondary" fontWeight={500}>
                Déjà remboursé
              </Typography>
              <Typography variant="caption" fontWeight={600}>
                -{formatMinor(avoir.total_minor - remainingRefundMinor)}
              </Typography>
            </Stack>
            <Divider sx={{ my: 0.5 }} />
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="body2" color="#EA580C" fontWeight={700}>
                Restant à rembourser
              </Typography>
              <Typography variant="body2" color="#EA580C" fontWeight={800}>
                {formatMinor(remainingRefundMinor)}
              </Typography>
            </Stack>
          </Stack>

          {/* Payment picker (only when multiple payments) */}
          {showPaymentPicker && (
            <FormControl fullWidth size="small">
              <InputLabel>Paiement d'origine</InputLabel>
              <Select
                label="Paiement d'origine"
                value={selectedPaymentId}
                onChange={e => {
                  const id = e.target.value as number
                  setSelectedPaymentId(id)
                  const p = payments?.find(p => p.id === id)
                  if (p) setPaymentMethod(p.payment_method)
                }}
              >
                {payments!.map(p => (
                  <MenuItem key={p.id} value={p.id}>
                    {new Date(p.paid_at).toLocaleDateString('fr-FR')} —{' '}
                    {formatMinor(p.amount_minor)} —{' '}
                    {PAYMENT_METHOD_LABELS[p.payment_method]}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}

          {/* Amount */}
          <TextField
            label="Montant remboursé"
            type="number"
            inputProps={{ min: 0.01, max: remainingRefundMinor / 100, step: 0.01 }}
            value={amountStr}
            onChange={e => setAmountStr(e.target.value)}
            error={!!amountError && amountStr !== ''}
            helperText={amountStr !== '' ? amountError : ''}
            fullWidth
            size="small"
            InputProps={{
              endAdornment: (
                <Typography variant="body2" color="text.secondary" sx={{ ml: 0.5, flexShrink: 0 }}>
                  €
                </Typography>
              ),
            }}
          />

          {/* Payment method (how the garage pays back) */}
          <FormControl fullWidth size="small">
            <InputLabel>Moyen de remboursement</InputLabel>
            <Select
              label="Moyen de remboursement"
              value={paymentMethod}
              onChange={e => setPaymentMethod(e.target.value as PaymentMethod)}
            >
              {(Object.entries(PAYMENT_METHOD_LABELS) as [PaymentMethod, string][]).map(([val, label]) => (
                <MenuItem key={val} value={val}>{label}</MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Reference */}
          <TextField
            label="Référence (optionnel)"
            placeholder="N° virement, N° chèque…"
            value={reference}
            onChange={e => setReference(e.target.value)}
            fullWidth
            size="small"
            inputProps={{ maxLength: 100 }}
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
          {mutation.isPending ? 'Enregistrement…' : 'Confirmer'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
