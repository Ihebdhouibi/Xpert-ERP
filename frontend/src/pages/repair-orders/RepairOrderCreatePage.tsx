import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Grid,
  InputAdornment,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import TuneRoundedIcon from '@mui/icons-material/TuneRounded'
import { repairOrderApi } from '../../lib/repairOrderApi'
import { PageHeader } from '../../components/ui/PageHeader'

const schema = z.object({
  customer_id: z.coerce.number().int().positive('Client requis'),
  vehicle_id: z.coerce.number().int().positive().nullable().optional(),
  description: z.string().min(1, 'Description requise'),
  priority: z.string().max(20).nullable().optional(),
  estimated_cost_minor: z.coerce.number().int().min(0).nullable().optional(),
  estimated_cost_currency: z
    .string()
    .length(3)
    .regex(/^[A-Z]{3}$/, 'Devise invalide (ex: EUR)')
    .nullable()
    .optional(),
})

type FormValues = z.infer<typeof schema>

const PRIORITIES = ['low', 'normal', 'high', 'urgent'] as const
const PRIORITY_LABELS: Record<string, string> = {
  low: 'Basse',
  normal: 'Normale',
  high: 'Haute',
  urgent: 'Urgente',
}
const PRIORITY_COLORS: Record<string, string> = {
  low: '#64748B',
  normal: '#2563EB',
  high: '#F59E0B',
  urgent: '#EF4444',
}

function SectionCard({
  title,
  icon,
  children,
}: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardContent sx={{ p: 3 }}>
        <Stack direction="row" alignItems="center" spacing={1.5} mb={2.5}>
          <Box sx={{ color: 'primary.main' }}>{icon}</Box>
          <Typography variant="subtitle1" fontWeight={700}>{title}</Typography>
        </Stack>
        <Divider sx={{ mb: 2.5 }} />
        {children}
      </CardContent>
    </Card>
  )
}

export function RepairOrderCreatePage() {
  const navigate = useNavigate()
  const [submitError, setSubmitError] = useState<string | null>(null)

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      customer_id: undefined,
      vehicle_id: null,
      description: '',
      priority: 'normal',
      estimated_cost_minor: null,
      estimated_cost_currency: 'EUR',
    },
  })

  const estimatedMinor = watch('estimated_cost_minor')
  const estimatedCurrency = watch('estimated_cost_currency')
  const estimatedDisplay =
    estimatedMinor != null && estimatedMinor > 0
      ? (estimatedMinor / 100).toLocaleString('fr-FR', {
          style: 'currency',
          currency: estimatedCurrency || 'EUR',
          minimumFractionDigits: 2,
        })
      : null

  const onSubmit = async (values: FormValues) => {
    setSubmitError(null)
    try {
      const ro = await repairOrderApi.create({
        customer_id: values.customer_id,
        vehicle_id: values.vehicle_id ?? null,
        description: values.description,
        priority: values.priority ?? null,
        estimated_cost_minor: values.estimated_cost_minor ?? null,
        estimated_cost_currency: values.estimated_cost_currency ?? null,
      })
      navigate(`/repair-orders/${ro.id}`)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'Erreur lors de la création.'
      setSubmitError(typeof msg === 'string' ? msg : JSON.stringify(msg))
    }
  }

  return (
    <Box component="form" onSubmit={handleSubmit(onSubmit)}>
      <PageHeader
        title="Nouvel ordre de réparation"
        subtitle="Créez un OT et assignez-le à un client et un véhicule"
        breadcrumbs={[
          { label: 'Ordres de réparation', href: '/repair-orders' },
          { label: 'Nouvel OT' },
        ]}
        actions={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={<ArrowBackRoundedIcon />}
              onClick={() => navigate('/repair-orders')}
              disabled={isSubmitting}
            >
              Annuler
            </Button>
            <Button
              type="submit"
              variant="contained"
              startIcon={<SaveRoundedIcon />}
              disabled={isSubmitting}
            >
              Créer l'OT
            </Button>
          </Stack>
        }
      />

      {submitError && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setSubmitError(null)}>
          {submitError}
        </Alert>
      )}

      <Grid container spacing={3} sx={{ maxWidth: 860 }}>
        <Grid item xs={12} md={7}>
          <Stack spacing={3}>
            <SectionCard
              title="Informations principales"
              icon={<BuildRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Stack spacing={2.5}>
                <Controller
                  name="customer_id"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      label="ID Client *"
                      type="number"
                      error={!!errors.customer_id}
                      helperText={errors.customer_id?.message ?? 'Numéro du client propriétaire du véhicule'}
                      fullWidth
                      autoFocus
                      inputProps={{ min: 1 }}
                    />
                  )}
                />

                <Controller
                  name="vehicle_id"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      value={field.value ?? ''}
                      label="ID Véhicule"
                      type="number"
                      error={!!errors.vehicle_id}
                      helperText={errors.vehicle_id?.message ?? 'Optionnel — peut être associé après création'}
                      fullWidth
                      inputProps={{ min: 1 }}
                    />
                  )}
                />

                <Controller
                  name="description"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      label="Description *"
                      multiline
                      rows={4}
                      error={!!errors.description}
                      helperText={errors.description?.message ?? 'Décrivez le problème signalé par le client'}
                      fullWidth
                    />
                  )}
                />
              </Stack>
            </SectionCard>
          </Stack>
        </Grid>

        <Grid item xs={12} md={5}>
          <Stack spacing={3}>
            <SectionCard
              title="Priorité & Estimation"
              icon={<TuneRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Stack spacing={2.5}>
                <Controller
                  name="priority"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      select
                      label="Priorité"
                      error={!!errors.priority}
                      helperText={errors.priority?.message}
                      fullWidth
                    >
                      {PRIORITIES.map((p) => (
                        <MenuItem key={p} value={p}>
                          <Stack direction="row" alignItems="center" spacing={1.25}>
                            <Box
                              sx={{
                                width: 8,
                                height: 8,
                                borderRadius: '50%',
                                bgcolor: PRIORITY_COLORS[p],
                                flexShrink: 0,
                              }}
                            />
                            <span>{PRIORITY_LABELS[p]}</span>
                          </Stack>
                        </MenuItem>
                      ))}
                    </TextField>
                  )}
                />

                <Stack direction="row" spacing={1.5} alignItems="flex-start">
                  <Controller
                    name="estimated_cost_minor"
                    control={control}
                    render={({ field }) => (
                      <TextField
                        {...field}
                        value={field.value ?? ''}
                        label="Coût estimé"
                        type="number"
                        error={!!errors.estimated_cost_minor}
                        helperText={
                          estimatedDisplay
                            ? `≈ ${estimatedDisplay}`
                            : 'Valeur en centimes (ex: 15000 = 150,00)'
                        }
                        InputProps={{
                          endAdornment: (
                            <InputAdornment position="end">
                              <Typography variant="caption" color="text.secondary">cts</Typography>
                            </InputAdornment>
                          ),
                        }}
                        fullWidth
                        inputProps={{ min: 0 }}
                      />
                    )}
                  />
                  <Controller
                    name="estimated_cost_currency"
                    control={control}
                    render={({ field }) => (
                      <TextField
                        {...field}
                        value={field.value ?? ''}
                        label="Devise"
                        error={!!errors.estimated_cost_currency}
                        helperText={errors.estimated_cost_currency?.message}
                        sx={{ width: 100, flexShrink: 0 }}
                        inputProps={{ style: { fontFamily: 'monospace', textTransform: 'uppercase' } }}
                      />
                    )}
                  />
                </Stack>
              </Stack>
            </SectionCard>
          </Stack>
        </Grid>
      </Grid>
    </Box>
  )
}
