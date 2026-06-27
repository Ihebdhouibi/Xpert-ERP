import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import CreditCardRoundedIcon from '@mui/icons-material/CreditCardRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import PendingRoundedIcon from '@mui/icons-material/PendingRounded'
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded'
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import axios from 'axios'
import { advancePaymentApi, type AdvancePaymentOut, type AdvancePaymentListResponse } from '../../lib/advancePaymentApi'
import { PAYMENT_METHOD_LABELS, type PaymentMethod } from '../../lib/paymentApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { CustomerAutocomplete } from '../../components/ui/CustomerAutocomplete'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

const schema = z.object({
  customer_id: z.number({ required_error: 'Requis' }).int().positive('Sélectionnez un client'),
  amount_euros: z.number({ required_error: 'Requis' }).positive('Montant invalide'),
  payment_method: z.enum(['cash', 'card', 'bank_transfer', 'cheque', 'other'] as const),
  reference: z.string().optional(),
  notes: z.string().optional(),
})
type FormValues = z.infer<typeof schema>

type StatusFilter = 'all' | 'pending' | 'applied'

function AdvanceCard({ ap }: { ap: AdvancePaymentOut }) {
  const navigate = useNavigate()
  const applied = ap.applied_to_invoice_id != null
  const { error: toastError } = useToast()
  const [pdfLoading, setPdfLoading] = useState(false)

  const handlePdf = async () => {
    setPdfLoading(true)
    try {
      const token = localStorage.getItem('access_token')
      const response = await axios.get(
        `/api/v1/pdf/advance-payments/${ap.id}`,
        {
          responseType: 'blob',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      )
      const url = URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      toastError('Impossible de générer le reçu PDF.')
    } finally {
      setPdfLoading(false)
    }
  }

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
            <Stack direction="row" alignItems="center" justifyContent="space-between">
              <Typography variant="caption" color="text.secondary">
                Imputé — {formatMinor(ap.applied_amount_minor)}
              </Typography>
              {ap.applied_invoice_public_id && (
                <Button
                  size="small"
                  variant="text"
                  endIcon={<OpenInNewRoundedIcon sx={{ fontSize: 13 }} />}
                  onClick={() => navigate(`/invoices/${ap.applied_invoice_public_id}`)}
                  sx={{ p: 0, minWidth: 0, fontWeight: 600, fontSize: '0.75rem', color: 'primary.main' }}
                >
                  Voir la facture
                </Button>
              )}
            </Stack>
          </>
        )}
        <Divider sx={{ my: 1 }} />
        <Stack direction="row" justifyContent="flex-end">
          <Tooltip title="Reçu PDF">
            <Button
              size="small"
              variant="outlined"
              startIcon={<PictureAsPdfRoundedIcon sx={{ fontSize: 14 }} />}
              onClick={handlePdf}
              disabled={pdfLoading}
              sx={{ fontSize: '0.75rem', py: 0.25 }}
            >
              {pdfLoading ? 'Génération…' : 'Reçu'}
            </Button>
          </Tooltip>
        </Stack>
      </CardContent>
    </Card>
  )
}

export function AdvancePaymentsPage() {
  const { success, error } = useToast()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [filterCustomerId, setFilterCustomerId] = useState<number | null>(null)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')

  // Global list (all garage advances by default)
  const { data: allData } = useQuery({
    queryKey: ['advance-payments', 'all', statusFilter],
    queryFn: () => advancePaymentApi.listAll(statusFilter !== 'all' ? { status: statusFilter } : undefined),
    enabled: filterCustomerId === null,
  })

  // Customer-scoped list when customer filter is active
  const { data: customerData } = useQuery({
    queryKey: ['advance-payments', 'customer', filterCustomerId],
    queryFn: () => advancePaymentApi.listByCustomer(Number(filterCustomerId)),
    enabled: filterCustomerId !== null,
  } as Parameters<typeof useQuery>[0])

  const advances: AdvancePaymentOut[] = filterCustomerId !== null
    ? (customerData as AdvancePaymentListResponse | undefined)?.items ?? []
    : (allData as AdvancePaymentListResponse | undefined)?.items ?? []

  const filteredAdvances = filterCustomerId !== null && statusFilter !== 'all'
    ? advances.filter(a =>
        statusFilter === 'pending'
          ? a.applied_to_invoice_id === null
          : a.applied_to_invoice_id !== null
      )
    : advances

  const { control, handleSubmit, reset, setValue, formState: { isSubmitting } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { payment_method: 'cash' },
  })

  const createMutation = useMutation({
    mutationFn: (values: FormValues) =>
      advancePaymentApi.create({
        customer_id: values.customer_id,
        amount_minor: Math.round(values.amount_euros * 100),
        payment_method: values.payment_method,
        reference: values.reference || null,
        notes: values.notes || null,
      }),
    onSuccess: () => {
      success('Avance enregistrée avec succès.')
      reset({ payment_method: 'cash' })
      setOpen(false)
      queryClient.invalidateQueries({ queryKey: ['advance-payments'] })
    },
    onError: () => error("Erreur lors de l'enregistrement de l'avance."),
  })

  const pendingCount = (allData as AdvancePaymentListResponse | undefined)?.items.filter(a => !a.applied_to_invoice_id).length ?? 0

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

      {/* Filters bar */}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} mb={3} alignItems={{ sm: 'center' }}>
        <Box sx={{ maxWidth: 320, flex: 1 }}>
          <CustomerAutocomplete
            value={filterCustomerId}
            onChange={id => setFilterCustomerId(id)}
            label="Filtrer par client"
          />
        </Box>
        <ToggleButtonGroup
          size="small"
          value={statusFilter}
          exclusive
          onChange={(_, v) => { if (v) setStatusFilter(v) }}
        >
          <ToggleButton value="all" sx={{ textTransform: 'none', fontWeight: 600, px: 2 }}>
            Tous
          </ToggleButton>
          <ToggleButton value="pending" sx={{ textTransform: 'none', fontWeight: 600, px: 2 }}>
            Disponibles{pendingCount > 0 && ` (${pendingCount})`}
          </ToggleButton>
          <ToggleButton value="applied" sx={{ textTransform: 'none', fontWeight: 600, px: 2 }}>
            Imputés
          </ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      {filteredAdvances.length > 0 ? (
        <Stack spacing={2}>
          {filteredAdvances.map(ap => <AdvanceCard key={ap.id} ap={ap} />)}
        </Stack>
      ) : (
        <Card>
          <CardContent sx={{ py: 6, textAlign: 'center' }}>
            <CreditCardRoundedIcon sx={{ fontSize: 48, color: '#CBD5E1', mb: 2 }} />
            <Typography variant="h6" fontWeight={600} color="text.secondary">
              Aucune avance
            </Typography>
            <Typography variant="body2" color="text.disabled" mt={0.5}>
              {filterCustomerId
                ? 'Ce client n\'a aucune avance pour ce filtre.'
                : 'Enregistrez une nouvelle avance client.'}
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
                <CustomerAutocomplete
                  value={field.value ?? null}
                  onChange={id => setValue('customer_id', id ?? 0, { shouldValidate: true })}
                  required
                  error={!!fieldState.error}
                  helperText={fieldState.error?.message}
                />
              )}
            />
            <Controller
              name="amount_euros"
              control={control}
              render={({ field, fieldState }) => (
                <TextField
                  {...field}
                  label="Montant (€)"
                  type="number"
                  fullWidth
                  inputProps={{ min: 0, step: '0.01' }}
                  error={!!fieldState.error}
                  helperText={fieldState.error?.message ?? 'Ex: 50.00'}
                  onChange={e => field.onChange(parseFloat(e.target.value) || 0)}
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
          <Button
            variant="contained"
            onClick={handleSubmit(v => createMutation.mutate(v))}
            disabled={isSubmitting || createMutation.isPending}
          >
            Enregistrer
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
