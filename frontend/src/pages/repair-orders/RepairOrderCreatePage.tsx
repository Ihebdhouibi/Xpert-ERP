import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { repairOrderApi } from '../../lib/repairOrderApi'

const schema = z.object({
  customer_id: z.coerce.number().int().positive('Client requis'),
  vehicle_id: z.coerce.number().int().positive().nullable().optional(),
  description: z.string().min(1, 'Description requise'),
  priority: z.string().max(20).nullable().optional(),
  estimated_cost_minor: z.coerce.number().int().min(0).nullable().optional(),
  estimated_cost_currency: z
    .string()
    .length(3)
    .regex(/^[A-Z]{3}$/, 'Devise invalide (ex: TND)')
    .nullable()
    .optional(),
})

type FormValues = z.infer<typeof schema>

const PRIORITIES = ['low', 'normal', 'high', 'urgent']
const PRIORITY_LABELS: Record<string, string> = {
  low: 'Basse',
  normal: 'Normale',
  high: 'Haute',
  urgent: 'Urgente',
}

export function RepairOrderCreatePage() {
  const navigate = useNavigate()
  const [submitError, setSubmitError] = useState<string | null>(null)

  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      customer_id: undefined,
      vehicle_id: null,
      description: '',
      priority: 'normal',
      estimated_cost_minor: null,
      estimated_cost_currency: null,
    },
  })

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
    <Box p={4} maxWidth={700} mx="auto">
      <Typography variant="h4" fontWeight={700} mb={3}>
        Nouvel ordre de réparation
      </Typography>

      {submitError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setSubmitError(null)}>
          {submitError}
        </Alert>
      )}

      <Paper sx={{ p: 3 }}>
        <Stack spacing={2} component="form" onSubmit={handleSubmit(onSubmit)}>
          <Controller
            name="customer_id"
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                label="ID Client *"
                type="number"
                error={!!errors.customer_id}
                helperText={errors.customer_id?.message}
                fullWidth
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
                label="ID Véhicule (optionnel)"
                type="number"
                error={!!errors.vehicle_id}
                helperText={errors.vehicle_id?.message}
                fullWidth
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
                rows={3}
                error={!!errors.description}
                helperText={errors.description?.message}
                fullWidth
              />
            )}
          />

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
                    {PRIORITY_LABELS[p]}
                  </MenuItem>
                ))}
              </TextField>
            )}
          />

          <Stack direction="row" spacing={2}>
            <Controller
              name="estimated_cost_minor"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  value={field.value ?? ''}
                  label="Coût estimé (centimes)"
                  type="number"
                  error={!!errors.estimated_cost_minor}
                  helperText={errors.estimated_cost_minor?.message ?? 'Ex: 15000 = 150,00'}
                  fullWidth
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
                  placeholder="TND"
                  error={!!errors.estimated_cost_currency}
                  helperText={errors.estimated_cost_currency?.message}
                  sx={{ maxWidth: 120 }}
                />
              )}
            />
          </Stack>

          <Stack direction="row" spacing={2} justifyContent="flex-end" pt={1}>
            <Button onClick={() => navigate('/repair-orders')}>Annuler</Button>
            <Button
              type="submit"
              variant="contained"
              disabled={isSubmitting}
              startIcon={isSubmitting ? <CircularProgress size={16} /> : null}
            >
              Créer
            </Button>
          </Stack>
        </Stack>
      </Paper>
    </Box>
  )
}
