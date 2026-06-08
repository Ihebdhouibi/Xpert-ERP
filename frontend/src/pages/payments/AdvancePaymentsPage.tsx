import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import CreditCardRoundedIcon from '@mui/icons-material/CreditCardRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import PendingRoundedIcon from '@mui/icons-material/PendingRounded'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { advancePaymentApi, type AdvancePaymentOut, type AdvancePaymentListResponse } from '../../lib/advancePaymentApi'
import { PAYMENT_METHOD_LABELS, type PaymentMethod } from '../../lib/paymentApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

const schema = z.object({
  customer_id: z.number({ required_error: 'Requis' }).int().positive(),
  amount_minor: z.number({ required_error: 'Requis' }).int().positive('Montant invalide'),
  payment_method: z.enum(['cash', 'card', 'bank_transfer', 'cheque', 'other'] as const),
  reference: z.string().optional(),
  notes: z.string().optional(),
})
type FormValues = z.infer<typeof schema>

function AdvanceCard({ ap }: { ap: AdvancePaymentOut }) {
  const applied = ap.applied_to_invoice_id != null
  return (
    <Card>
      <CardContent sx={{ p: 2.5 }}>
        <Stack direction="row" alignItems="flex-start" justifyContent="space-between" mb={1}>
          <Stack direction="row" alignItems="center" spacing={1.5}>
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: '12px',
                bgcolor: applied ? '#F0FDF4' : '#EFF6FF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {applied
                ? <CheckCircleRoundedIcon sx={{ color: '#16A34A', fontSize: 20 }} />
                : <PendingRoundedIcon sx={{ color: '#2563EB', fontSize: 20 }} />}
            </Box>
            <Box>
              <Typography variant="subtitle2" fontWeight={700}>
                {ap.customer_name ?? `Client #${ap.customer_id}`}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {new Date(ap.paid_at).toLocaleDateString('fr-FR')} · {PAYMENT_METHOD_LABELS[ap.payment_method]}
              </Typography>
            </Box>
          </Stack>
          <Box textAlign="right">
            <Typography variant="h6" fontWeight={700} color={applied ? 'text.secondary' : 'primary.main'}>
              {formatMinor(ap.amount_minor)}
            </Typography>
            <Chip
              size="small"
              label={applied ? 'Imputé' : 'Disponible'}
              color={applied ? 'default' : 'success'}
              sx={{ fontWeight: 600 }}
            />
          </Box>
        </Stack>
        {ap.reference && (
          <>
            <Divider sx={{ my: 1 }} />
            <Typography variant="caption" color="text.secondary">
              Réf. {ap.reference}
            </Typography>
          </>
        )}
        {applied && ap.applied_amount_minor != null && (
          <>
            <Divider sx={{ my: 1 }} />
            <Typography variant="caption" color="text.secondary">
              Imputé sur facture #{ap.applied_to_invoice_id} — {formatMinor(ap.applied_amount_minor)}
            </Typography>
          </>
        )}
      </CardContent>
    </Card>
  )
}

export function AdvancePaymentsPage() {
  const { success, error } = useToast()
  const [open, setOpen] = useState(false)
  const [customerId, setCustomerId] = useState<number | ''>('')
  const [advances, setAdvances] = useState<AdvancePaymentOut[]>([])

  const { refetch } = useQuery({
    queryKey: ['advance-payments', customerId],
    queryFn: () => advancePaymentApi.listByCustomer(Number(customerId)),
    enabled: typeof customerId === 'number',
    onSuccess: (data: AdvancePaymentListResponse) => setAdvances(data.items),
  } as Parameters<typeof useQuery>[0])

  const { control, handleSubmit, reset, formState: { isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { payment_method: 'cash' },
  })

  const onSubmit = async (values: FormValues) => {
    try {
      await advancePaymentApi.create({
        customer_id: values.customer_id,
        amount_minor: values.amount_minor,
        payment_method: values.payment_method,
        reference: values.reference || null,
        notes: values.notes || null,
      })
      success('Avance enregistrée avec succès.')
      reset()
      setOpen(false)
      void refetch()
    } catch {
      error('Erreur lors de l\'enregistrement de l\'avance.')
    }
  }

  return (
    <Box>
      <PageHeader
        title="Avances & acomptes"
        subtitle="Suivez les dépôts clients avant facturation"
        actions={
          <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setOpen(true)}>
            Nouvelle avance
          </Button>
        }
      />

      {/* Customer lookup */}
      <Stack direction="row" spacing={2} mb={3} alignItems="center">
        <TextField
          label="ID client"
          type="number"
          value={customerId}
          onChange={e => setCustomerId(e.target.value ? Number(e.target.value) : '')}
          sx={{ width: 200 }}
          placeholder="Ex: 42"
        />
        <Typography variant="body2" color="text.secondary">
          Entrez un ID client pour voir ses avances.
        </Typography>
      </Stack>

      {advances.length > 0 ? (
        <Stack spacing={2}>
          {advances.map(ap => <AdvanceCard key={ap.id} ap={ap} />)}
        </Stack>
      ) : (
        <Card>
          <CardContent sx={{ py: 6, textAlign: 'center' }}>
            <CreditCardRoundedIcon sx={{ fontSize: 48, color: '#CBD5E1', mb: 2 }} />
            <Typography variant="h6" fontWeight={600} color="text.secondary">
              Aucune avance
            </Typography>
            <Typography variant="body2" color="text.disabled" mt={0.5}>
              Sélectionnez un client ou enregistrez une nouvelle avance.
            </Typography>
          </CardContent>
        </Card>
      )}

      {/* Create dialog */}
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Nouvelle avance client</DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} pt={1}>
            <Controller
              name="customer_id"
              control={control}
              render={({ field, fieldState }) => (
                <TextField
                  {...field}
                  label="ID client"
                  type="number"
                  fullWidth
                  error={!!fieldState.error}
                  helperText={fieldState.error?.message}
                  onChange={e => field.onChange(Number(e.target.value))}
                />
              )}
            />
            <Controller
              name="amount_minor"
              control={control}
              render={({ field, fieldState }) => (
                <TextField
                  {...field}
                  label="Montant (en centimes)"
                  type="number"
                  fullWidth
                  error={!!fieldState.error}
                  helperText={fieldState.error?.message ?? 'Ex: 5000 = 50,00 €'}
                  onChange={e => field.onChange(Number(e.target.value))}
                />
              )}
            />
            <Controller
              name="payment_method"
              control={control}
              render={({ field }) => (
                <TextField {...field} label="Mode de paiement" select fullWidth>
                  {(Object.entries(PAYMENT_METHOD_LABELS) as [PaymentMethod, string][]).map(([v, l]) => (
                    <MenuItem key={v} value={v}>{l}</MenuItem>
                  ))}
                </TextField>
              )}
            />
            <Controller
              name="reference"
              control={control}
              render={({ field }) => (
                <TextField {...field} label="Référence (optionnel)" fullWidth />
              )}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setOpen(false)}>Annuler</Button>
          <Button variant="contained" onClick={handleSubmit(onSubmit)} disabled={isSubmitting}>
            Enregistrer
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
