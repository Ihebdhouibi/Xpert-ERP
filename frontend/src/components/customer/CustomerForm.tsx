import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  Box,
  Button,
  Grid,
  MenuItem,
  TextField,
  Typography,
  Divider,
} from '@mui/material'
import type {
  CustomerCreateInput,
  CustomerDetail,
  CustomerStatus,
  CustomerType,
} from '../../lib/customerApi'

const e164Regex = /^\+[1-9]\d{6,14}$/

const optionalString = z
  .string()
  .trim()
  .transform((s) => (s === '' ? null : s))
  .nullable()

export const customerFormSchema = z
  .object({
    type: z.enum(['individual', 'company']),
    full_name: z.string().trim().min(1, 'Nom requis').max(255),
    company_name: optionalString,
    fiscal_id: optionalString,
    email: z
      .string()
      .trim()
      .email('Email invalide')
      .or(z.literal(''))
      .transform((s) => (s === '' ? null : s))
      .nullable(),
    phone_e164: z
      .string()
      .trim()
      .regex(e164Regex, 'Format requis : +212XXXXXXXXX')
      .or(z.literal(''))
      .transform((s) => (s === '' ? null : s))
      .nullable(),
    address_street: optionalString,
    address_city: optionalString,
    address_postal_code: optionalString,
    address_country: optionalString,
    segment: optionalString,
    status: z.enum(['active', 'inactive', 'blocked']).optional(),
    credit_limit_minor: z
      .union([z.number(), z.string()])
      .transform((v) => (v === '' || v === undefined ? 0 : Number(v)))
      .refine((v) => Number.isInteger(v) && v >= 0, 'Doit être un entier positif'),
    credit_currency: z
      .string()
      .trim()
      .regex(/^[A-Z]{3}$/, '3 lettres majuscules (ISO 4217)')
      .or(z.literal(''))
      .transform((s) => (s === '' ? null : s))
      .nullable(),
    notes: optionalString,
  })
  .refine(
    (data) => data.type !== 'company' || !!data.company_name,
    {
      message: 'Le nom de société est requis pour un client société',
      path: ['company_name'],
    },
  )
  .refine(
    (data) => data.credit_limit_minor === 0 || !!data.credit_currency,
    {
      message: 'Devise requise dès qu’une limite de crédit est définie',
      path: ['credit_currency'],
    },
  )

export type CustomerFormValues = z.infer<typeof customerFormSchema>

interface CustomerFormProps {
  mode: 'create' | 'edit'
  initial?: CustomerDetail
  submitting?: boolean
  onSubmit: (
    payload: CustomerCreateInput & { status?: CustomerStatus },
  ) => Promise<void> | void
  onCancel: () => void
}

const defaults = (initial?: CustomerDetail): CustomerFormValues => ({
  type: (initial?.type ?? 'individual') as CustomerType,
  full_name: initial?.full_name ?? '',
  company_name: initial?.company_name ?? null,
  fiscal_id: initial?.fiscal_id ?? null,
  email: initial?.email ?? null,
  phone_e164: initial?.phone_e164 ?? null,
  address_street: initial?.address?.street ?? null,
  address_city: initial?.address?.city ?? null,
  address_postal_code: initial?.address?.postal_code ?? null,
  address_country: initial?.address?.country ?? null,
  segment: initial?.segment ?? null,
  status: (initial?.status ?? 'active') as CustomerStatus,
  credit_limit_minor: initial?.credit_limit_minor ?? 0,
  credit_currency: initial?.credit_currency ?? null,
  notes: initial?.notes ?? null,
})

export function CustomerForm({
  mode,
  initial,
  submitting,
  onSubmit,
  onCancel,
}: CustomerFormProps) {
  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors },
  } = useForm<CustomerFormValues>({
    resolver: zodResolver(customerFormSchema),
    defaultValues: defaults(initial),
  })

  const type = watch('type')

  const submit = handleSubmit(async (values) => {
    const address =
      values.address_street ||
      values.address_city ||
      values.address_postal_code ||
      values.address_country
        ? {
            street: values.address_street,
            city: values.address_city,
            postal_code: values.address_postal_code,
            country: values.address_country,
          }
        : null

    await onSubmit({
      type: values.type,
      full_name: values.full_name,
      company_name: values.company_name,
      fiscal_id: values.fiscal_id,
      email: values.email,
      phone_e164: values.phone_e164,
      address,
      segment: values.segment,
      status: mode === 'edit' ? values.status : undefined,
      credit_limit_minor: values.credit_limit_minor,
      credit_currency: values.credit_currency,
      notes: values.notes,
    })
  })

  return (
    <Box component="form" onSubmit={submit} noValidate>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={4}>
          <Controller
            control={control}
            name="type"
            render={({ field }) => (
              <TextField
                {...field}
                select
                label="Type"
                fullWidth
                disabled={mode === 'edit'}
              >
                <MenuItem value="individual">Particulier</MenuItem>
                <MenuItem value="company">Société</MenuItem>
              </TextField>
            )}
          />
        </Grid>
        <Grid item xs={12} sm={8}>
          <TextField
            label={type === 'company' ? 'Nom du contact principal' : 'Nom complet'}
            fullWidth
            autoFocus
            {...register('full_name')}
            error={!!errors.full_name}
            helperText={errors.full_name?.message}
          />
        </Grid>

        {type === 'company' && (
          <Grid item xs={12}>
            <TextField
              label="Raison sociale"
              fullWidth
              {...register('company_name')}
              error={!!errors.company_name}
              helperText={errors.company_name?.message}
            />
          </Grid>
        )}

        <Grid item xs={12} sm={6}>
          <TextField
            label="Téléphone (format +212...)"
            fullWidth
            placeholder="+212612345678"
            {...register('phone_e164')}
            error={!!errors.phone_e164}
            helperText={errors.phone_e164?.message}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            label="Email"
            type="email"
            fullWidth
            {...register('email')}
            error={!!errors.email}
            helperText={errors.email?.message}
          />
        </Grid>

        <Grid item xs={12} sm={6}>
          <TextField
            label="Identifiant fiscal (ICE / CIN)"
            fullWidth
            {...register('fiscal_id')}
            error={!!errors.fiscal_id}
            helperText={errors.fiscal_id?.message}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            label="Segment"
            fullWidth
            placeholder="vip, flotte, particulier..."
            {...register('segment')}
          />
        </Grid>

        <Grid item xs={12}>
          <Divider sx={{ my: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Adresse
            </Typography>
          </Divider>
        </Grid>
        <Grid item xs={12} sm={8}>
          <TextField label="Rue" fullWidth {...register('address_street')} />
        </Grid>
        <Grid item xs={6} sm={4}>
          <TextField label="Code postal" fullWidth {...register('address_postal_code')} />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField label="Ville" fullWidth {...register('address_city')} />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField label="Pays" fullWidth {...register('address_country')} />
        </Grid>

        <Grid item xs={12}>
          <Divider sx={{ my: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Crédit
            </Typography>
          </Divider>
        </Grid>
        <Grid item xs={6} sm={4}>
          <TextField
            label="Limite (centimes)"
            type="number"
            fullWidth
            inputProps={{ min: 0, step: 1 }}
            {...register('credit_limit_minor', { valueAsNumber: true })}
            error={!!errors.credit_limit_minor}
            helperText={errors.credit_limit_minor?.message}
          />
        </Grid>
        <Grid item xs={6} sm={4}>
          <TextField
            label="Devise"
            fullWidth
            placeholder="MAD"
            {...register('credit_currency')}
            error={!!errors.credit_currency}
            helperText={errors.credit_currency?.message}
          />
        </Grid>

        {mode === 'edit' && (
          <Grid item xs={12} sm={4}>
            <Controller
              control={control}
              name="status"
              render={({ field }) => (
                <TextField {...field} select label="Statut" fullWidth>
                  <MenuItem value="active">Actif</MenuItem>
                  <MenuItem value="inactive">Inactif</MenuItem>
                  <MenuItem value="blocked">Bloqué</MenuItem>
                </TextField>
              )}
            />
          </Grid>
        )}

        <Grid item xs={12}>
          <TextField
            label="Notes"
            fullWidth
            multiline
            rows={3}
            {...register('notes')}
          />
        </Grid>

        <Grid item xs={12} display="flex" justifyContent="flex-end" gap={1} mt={1}>
          <Button onClick={onCancel} disabled={submitting}>
            Annuler
          </Button>
          <Button type="submit" variant="contained" disabled={submitting}>
            {submitting
              ? 'Enregistrement...'
              : mode === 'create'
                ? 'Créer le client'
                : 'Enregistrer'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  )
}
