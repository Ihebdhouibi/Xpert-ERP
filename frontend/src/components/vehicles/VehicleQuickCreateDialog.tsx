import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  MenuItem,
  TextField,
  Typography,
} from '@mui/material'
import DirectionsCarRoundedIcon from '@mui/icons-material/DirectionsCarRounded'
import {
  vehiclesApi,
  FUEL_TYPE_LABELS,
  type FuelType,
  type VehicleCreateInput,
  type VehicleOut,
} from '../../lib/vehiclesApi'
import type { CustomerSummary } from '../../lib/customerApi'
import { mergeMakeOptions, mergeModelOptions } from '../../lib/vehicleOptions'
import { ConfirmableAutocomplete } from './ConfirmableAutocomplete'
import { useToast } from '../../contexts/ToastContext'

const FUEL_TYPES = Object.entries(FUEL_TYPE_LABELS).map(([value, label]) => ({
  value: value as FuelType,
  label,
}))

const CURRENT_YEAR = new Date().getFullYear()

interface FormErrors {
  make?: string
  model?: string
  registration?: string
  vin?: string
  year?: string
  mileage?: string
}

function validate(fields: {
  make: string
  model: string
  registration: string
  vin: string
  year: string
  mileage: string
}): FormErrors {
  const errors: FormErrors = {}
  if (!fields.make.trim()) errors.make = 'Champ obligatoire'
  if (!fields.model.trim()) errors.model = 'Champ obligatoire'

  const reg = fields.registration.trim()
  const vin = fields.vin.trim()
  if (!reg && !vin) {
    errors.registration = 'Immatriculation ou VIN requis'
    errors.vin = 'Immatriculation ou VIN requis'
  }
  if (vin && (vin.length < 11 || vin.length > 17)) {
    errors.vin = 'Le VIN doit contenir entre 11 et 17 caractères'
  }
  if (fields.year) {
    const y = Number(fields.year)
    if (!Number.isInteger(y) || y < 1900 || y > CURRENT_YEAR + 1) {
      errors.year = `Année invalide (1900 – ${CURRENT_YEAR + 1})`
    }
  }
  if (fields.mileage) {
    const m = Number(fields.mileage)
    if (isNaN(m) || m < 0) errors.mileage = 'Kilométrage invalide (≥ 0)'
  }
  return errors
}

interface VehicleQuickCreateDialogProps {
  open: boolean
  customer: CustomerSummary
  canDeleteCustomOptions?: boolean
  onClose: () => void
  onCreated: (vehicle: VehicleOut) => void
}

export function VehicleQuickCreateDialog({
  open,
  customer,
  canDeleteCustomOptions = false,
  onClose,
  onCreated,
}: VehicleQuickCreateDialogProps) {
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()

  const [make, setMake] = useState('')
  const [model, setModel] = useState('')
  const [year, setYear] = useState('')
  const [fuelType, setFuelType] = useState<FuelType | ''>('')
  const [registration, setRegistration] = useState('')
  const [vin, setVin] = useState('')
  const [mileage, setMileage] = useState('')
  const [color, setColor] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  // Reset the form each time the dialog is (re)opened.
  useEffect(() => {
    if (open) {
      setMake('')
      setModel('')
      setYear('')
      setFuelType('')
      setRegistration('')
      setVin('')
      setMileage('')
      setColor('')
      setSubmitted(false)
      setServerError(null)
    }
  }, [open])

  // Clear model when make changes.
  useEffect(() => {
    setModel('')
  }, [make])

  const { data: customMakes, isFetching: makesLoading } = useQuery({
    queryKey: ['vehicle-makes'],
    queryFn: vehiclesApi.getMakes,
    staleTime: 60_000,
    enabled: open,
  })
  const makeOptions = mergeMakeOptions(customMakes ?? [])

  const { data: customModels, isFetching: modelsLoading } = useQuery({
    queryKey: ['vehicle-models', make],
    queryFn: () => vehiclesApi.getModels(make),
    enabled: open && !!make,
    staleTime: 60_000,
  })
  const modelOptions = mergeModelOptions(make, customModels ?? [])

  const errors = validate({ make, model, registration, vin, year, mileage })
  const hasErrors = Object.keys(errors).length > 0

  const handleDeleteCustomMake = async (name: string) => {
    await vehiclesApi.removeMake(name)
    await queryClient.invalidateQueries({ queryKey: ['vehicle-makes'] })
  }

  const handleDeleteCustomModel = async (name: string) => {
    await vehiclesApi.removeModel(make, name)
    await queryClient.invalidateQueries({ queryKey: ['vehicle-models', make] })
  }

  const handleSubmit = async () => {
    setSubmitted(true)
    if (hasErrors) return
    setSubmitting(true)
    setServerError(null)
    try {
      const input: VehicleCreateInput = {
        make: make.trim(),
        model: model.trim(),
        year: year ? Number(year) : undefined,
        fuel_type: fuelType || undefined,
        color: color.trim() || undefined,
        registration: registration.trim().toUpperCase() || undefined,
        vin: vin.trim().toUpperCase() || undefined,
        mileage_current: mileage ? Number(mileage) : undefined,
        customer_id: customer.int_id,
      }
      const created = await vehiclesApi.create(input)
      await queryClient.invalidateQueries({ queryKey: ['vehicles'] })
      await queryClient.invalidateQueries({ queryKey: ['customer-vehicles'] })
      success('Véhicule créé avec succès')
      onCreated(created)
    } catch (err) {
      let detail = 'Erreur lors de la création. Vérifiez les données saisies.'
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data
        if (typeof data.detail === 'string') {
          detail = data.detail
        } else if (Array.isArray(data.detail)) {
          detail = data.detail
            .map((d: { loc?: string[]; msg?: string }) =>
              d.loc ? `${d.loc.slice(1).join('.')}: ${d.msg}` : d.msg,
            )
            .join(' · ')
        }
      }
      setServerError(detail)
      toastError('Impossible de créer le véhicule.')
    } finally {
      setSubmitting(false)
    }
  }

  const customerLabel = customer.company_name
    ? `${customer.full_name} (${customer.company_name})`
    : customer.full_name

  return (
    <Dialog open={open} onClose={submitting ? undefined : onClose} maxWidth="sm" fullWidth PaperProps={{ sx: { borderRadius: 3 } }}>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <DirectionsCarRoundedIcon sx={{ color: 'primary.main', fontSize: 22 }} />
        Nouveau véhicule
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" mb={2.5}>
          Le véhicule sera rattaché à <strong>{customerLabel}</strong>.
        </Typography>

        {serverError && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setServerError(null)}>
            {serverError}
          </Alert>
        )}

        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <ConfirmableAutocomplete
              label="Marque"
              value={make}
              onChange={setMake}
              options={makeOptions}
              loading={makesLoading}
              required
              error={submitted && !!errors.make}
              helperText={submitted ? errors.make : undefined}
              placeholder="Ex : Renault"
              canDeleteCustomOptions={canDeleteCustomOptions}
              onDeleteCustomOption={handleDeleteCustomMake}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <ConfirmableAutocomplete
              label="Modèle"
              value={model}
              onChange={setModel}
              options={modelOptions}
              loading={modelsLoading}
              disabled={!make}
              required
              error={submitted && !!errors.model}
              helperText={submitted ? errors.model : undefined}
              placeholder="Ex : Clio"
              canDeleteCustomOptions={canDeleteCustomOptions}
              onDeleteCustomOption={handleDeleteCustomModel}
            />
          </Grid>

          <Grid item xs={12} sm={6}>
            <TextField
              label="Immatriculation"
              value={registration}
              onChange={e => setRegistration(e.target.value)}
              error={submitted && !!errors.registration}
              helperText={submitted ? errors.registration : undefined}
              placeholder="AB-123-CD"
              fullWidth
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              label="VIN"
              value={vin}
              onChange={e => setVin(e.target.value)}
              error={submitted && !!errors.vin}
              helperText={submitted ? errors.vin : undefined}
              fullWidth
            />
          </Grid>

          <Grid item xs={6} sm={4}>
            <TextField
              label="Année"
              value={year}
              onChange={e => setYear(e.target.value)}
              error={submitted && !!errors.year}
              helperText={submitted ? errors.year : undefined}
              inputProps={{ inputMode: 'numeric' }}
              fullWidth
            />
          </Grid>
          <Grid item xs={6} sm={4}>
            <TextField
              select
              label="Carburant"
              value={fuelType}
              onChange={e => setFuelType(e.target.value as FuelType | '')}
              fullWidth
            >
              <MenuItem value="">—</MenuItem>
              {FUEL_TYPES.map(f => (
                <MenuItem key={f.value} value={f.value}>{f.label}</MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField
              label="Kilométrage"
              value={mileage}
              onChange={e => setMileage(e.target.value)}
              error={submitted && !!errors.mileage}
              helperText={submitted ? errors.mileage : undefined}
              inputProps={{ inputMode: 'numeric' }}
              fullWidth
            />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={submitting} color="inherit">
          Annuler
        </Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={submitting}
          startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          Créer le véhicule
        </Button>
      </DialogActions>
    </Dialog>
  )
}
