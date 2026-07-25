import { useState, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  Autocomplete,
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  Grid,
  InputAdornment,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import DirectionsCarRoundedIcon from '@mui/icons-material/DirectionsCarRounded'
import CalendarMonthRoundedIcon from '@mui/icons-material/CalendarMonthRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import {
  vehiclesApi,
  FUEL_TYPE_LABELS,
  type FuelType,
  type VehicleCreateInput,
} from '../../lib/vehiclesApi'
import { customerApi, type CustomerSummary } from '../../lib/customerApi'
import { mergeMakeOptions, mergeModelOptions } from '../../lib/vehicleOptions'
import { ConfirmableAutocomplete } from '../../components/vehicles/ConfirmableAutocomplete'
import { PageHeader } from '../../components/ui/PageHeader'
import { useToast } from '../../contexts/ToastContext'
import { useAuth } from '../../contexts/AuthContext'

const FUEL_TYPES = Object.entries(FUEL_TYPE_LABELS).map(([value, label]) => ({
  value: value as FuelType,
  label,
}))

const CURRENT_YEAR = new Date().getFullYear()

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

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
    errors.registration = 'Au moins un des deux champs est requis'
    errors.vin = 'Au moins un des deux champs est requis'
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

// ---------------------------------------------------------------------------
// SectionCard
// ---------------------------------------------------------------------------

function SectionCard({
  title,
  icon,
  children,
}: {
  title: string
  icon?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardContent sx={{ p: 3 }}>
        <Stack direction="row" alignItems="center" spacing={1.5} mb={2.5}>
          {icon && <Box sx={{ color: 'primary.main' }}>{icon}</Box>}
          <Typography variant="subtitle1" fontWeight={700}>
            {title}
          </Typography>
        </Stack>
        <Divider sx={{ mb: 2.5 }} />
        {children}
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function VehicleCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const { user } = useAuth()
  const canDeleteCustomOptions = user?.permissions.includes('vehicle.delete') ?? false

  // Query params for prefill
  const prefillCustomerId = searchParams.get('customerId') ? Number(searchParams.get('customerId')) : null
  const returnTo = searchParams.get('returnTo') ?? null

  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  const [make, setMake] = useState('')
  const [model, setModel] = useState('')
  const [year, setYear] = useState('')
  const [fuelType, setFuelType] = useState<FuelType | ''>('')
  const [color, setColor] = useState('')
  const [registration, setRegistration] = useState('')
  const [vin, setVin] = useState('')
  const [mileage, setMileage] = useState('')
  const [ctDate, setCtDate] = useState('')
  const [maintenanceDate, setMaintenanceDate] = useState('')
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerSummary | null>(null)
  const [customerSearch, setCustomerSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const previousMakeRef = useRef(make)

  // Debounce the search input by 300 ms
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedSearch(customerSearch), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [customerSearch])

  // Clear the model whenever the make changes to a genuinely different value
  useEffect(() => {
    if (previousMakeRef.current !== make) {
      previousMakeRef.current = make
      setModel('')
    }
  }, [make])

  // Prefill customer from query param
  const { data: prefillCustomer } = useQuery({
    queryKey: ['customer-prefill', prefillCustomerId],
    queryFn: () => customerApi.getByIntId(prefillCustomerId!),
    enabled: !!prefillCustomerId,
    staleTime: Infinity,
  })

  useEffect(() => {
    if (prefillCustomer) {
      setSelectedCustomer(prefillCustomer)
      setCustomerSearch(
        prefillCustomer.company_name
          ? `${prefillCustomer.full_name} (${prefillCustomer.company_name})`
          : prefillCustomer.full_name,
      )
    }
  }, [prefillCustomer])

  // Fetch customers from the API whenever the debounced query changes
  const { data: customersData, isFetching: customersLoading } = useQuery({
    queryKey: ['customers', 'for-vehicle', debouncedSearch],
    queryFn: () =>
      customerApi.list({ status: 'active', q: debouncedSearch || undefined, page_size: 50 }),
    placeholderData: previousData => previousData,
  })
  const customers = customersData?.items ?? []

  const { data: customMakes, isFetching: makesLoading } = useQuery({
    queryKey: ['vehicle-makes'],
    queryFn: vehiclesApi.getMakes,
    staleTime: 60_000,
  })
  const makeOptions = mergeMakeOptions(customMakes ?? [])

  const { data: customModels, isFetching: modelsLoading } = useQuery({
    queryKey: ['vehicle-models', make],
    queryFn: () => vehiclesApi.getModels(make),
    enabled: !!make,
    staleTime: 60_000,
  })
  const modelOptions = mergeModelOptions(make, customModels ?? [])

  const handleDeleteCustomMake = async (name: string) => {
    await vehiclesApi.removeMake(name)
    await queryClient.invalidateQueries({ queryKey: ['vehicle-makes'] })
  }

  const handleDeleteCustomModel = async (name: string) => {
    await vehiclesApi.removeModel(make, name)
    await queryClient.invalidateQueries({ queryKey: ['vehicle-models', make] })
  }

  const errors = validate({ make, model, registration, vin, year, mileage })
  const hasErrors = Object.keys(errors).length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
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
        technical_inspection_due_at: ctDate || undefined,
        maintenance_due_at: maintenanceDate || undefined,
        customer_id: selectedCustomer?.int_id ?? undefined,
      }
      const created = await vehiclesApi.create(input)
      await queryClient.invalidateQueries({ queryKey: ['vehicles'] })
      // Also invalidate customer-scoped vehicle list so CustomerVehiclesPanel refreshes on return
      if (prefillCustomerId) {
        await queryClient.invalidateQueries({ queryKey: ['customer-vehicles'] })
      }
      success('Véhicule créé avec succès')
      navigate(returnTo ?? `/vehicles/${created.id}`, { replace: true })
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

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <PageHeader
        title="Nouveau véhicule"
        subtitle="Enregistrez un véhicule dans le parc atelier"
        breadcrumbs={[
          { label: 'Véhicules', href: '/vehicles' },
          { label: 'Nouveau véhicule' },
        ]}
        actions={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={<ArrowBackRoundedIcon />}
              onClick={() => navigate('/vehicles')}
              disabled={submitting}
            >
              Annuler
            </Button>
            <Button
              type="submit"
              variant="contained"
              startIcon={<SaveRoundedIcon />}
              disabled={submitting}
            >
              Enregistrer
            </Button>
          </Stack>
        }
      />

      {serverError && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {serverError}
        </Alert>
      )}

      <Grid container spacing={3} sx={{ maxWidth: 920 }}>
        {/* Left column — identity + registration */}
        <Grid item xs={12} md={7}>
          <Stack spacing={3}>
            <SectionCard
              title="Identification du véhicule"
              icon={<DirectionsCarRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <ConfirmableAutocomplete
                    label="Marque *"
                    value={make}
                    onChange={setMake}
                    options={makeOptions}
                    loading={makesLoading}
                    placeholder="ex. Peugeot"
                    autoFocus
                    error={submitted && !!errors.make}
                    helperText={submitted ? errors.make : undefined}
                    canDeleteCustomOptions={canDeleteCustomOptions}
                    onDeleteCustomOption={handleDeleteCustomMake}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <ConfirmableAutocomplete
                    label="Modèle *"
                    value={model}
                    onChange={setModel}
                    options={modelOptions}
                    loading={!!make && modelsLoading}
                    disabled={!make}
                    placeholder="ex. 308"
                    error={submitted && !!errors.model}
                    helperText={submitted ? errors.model : make ? undefined : 'Choisissez d’abord une marque'}
                    canDeleteCustomOptions={canDeleteCustomOptions}
                    onDeleteCustomOption={handleDeleteCustomModel}
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    label="Année"
                    type="number"
                    value={year}
                    onChange={e => setYear(e.target.value)}
                    fullWidth
                    placeholder={String(CURRENT_YEAR)}
                    inputProps={{ min: 1900, max: CURRENT_YEAR + 1 }}
                    error={submitted && !!errors.year}
                    helperText={submitted ? errors.year : undefined}
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    label="Carburant"
                    select
                    value={fuelType}
                    onChange={e => setFuelType(e.target.value as FuelType | '')}
                    fullWidth
                  >
                    <MenuItem value=""><em>Non renseigné</em></MenuItem>
                    {FUEL_TYPES.map(ft => (
                      <MenuItem key={ft.value} value={ft.value}>{ft.label}</MenuItem>
                    ))}
                  </TextField>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    label="Couleur"
                    value={color}
                    onChange={e => setColor(e.target.value)}
                    fullWidth
                    placeholder="ex. Gris anthracite"
                  />
                </Grid>
              </Grid>
            </SectionCard>

            <SectionCard title="Immatriculation & VIN">
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    label="Immatriculation"
                    value={registration}
                    onChange={e => setRegistration(e.target.value.toUpperCase())}
                    fullWidth
                    placeholder="AB-123-CD"
                    error={submitted && !!errors.registration}
                    helperText={
                      submitted && errors.registration
                        ? errors.registration
                        : undefined
                    }
                    inputProps={{
                      style: {
                        fontFamily: 'monospace',
                        letterSpacing: '0.1em',
                        fontWeight: 700,
                        fontSize: '1rem',
                      },
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    label="Numéro VIN"
                    value={vin}
                    onChange={e => setVin(e.target.value.toUpperCase())}
                    fullWidth
                    placeholder="VF3XXXXXXXXXX"
                    error={submitted && !!errors.vin}
                    inputProps={{
                      maxLength: 17,
                      style: { fontFamily: 'monospace', fontSize: '0.875rem' },
                    }}
                    helperText={
                      submitted && errors.vin
                        ? errors.vin
                        : vin
                          ? `${vin.length} / 17 caractères`
                          : 'Numéro de châssis (11–17 caractères)'
                    }
                  />
                </Grid>
              </Grid>
            </SectionCard>
          </Stack>
        </Grid>

        {/* Right column — maintenance + owner */}
        <Grid item xs={12} md={5}>
          <Stack spacing={3}>
            <SectionCard
              title="Entretien & Contrôles"
              icon={<CalendarMonthRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Stack spacing={2}>
                <TextField
                  label="Kilométrage actuel"
                  type="number"
                  value={mileage}
                  onChange={e => setMileage(e.target.value)}
                  fullWidth
                  placeholder="ex. 75 000"
                  inputProps={{ min: 0 }}
                  error={submitted && !!errors.mileage}
                  helperText={submitted ? errors.mileage : undefined}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <Typography variant="caption" color="text.secondary">km</Typography>
                      </InputAdornment>
                    ),
                  }}
                />
                <TextField
                  label="Échéance contrôle technique"
                  type="date"
                  value={ctDate}
                  onChange={e => setCtDate(e.target.value)}
                  fullWidth
                  InputLabelProps={{ shrink: true }}
                />
                <TextField
                  label="Date prochain entretien"
                  type="date"
                  value={maintenanceDate}
                  onChange={e => setMaintenanceDate(e.target.value)}
                  fullWidth
                  InputLabelProps={{ shrink: true }}
                />
              </Stack>
            </SectionCard>

            <SectionCard
              title="Propriétaire"
              icon={<PersonRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Autocomplete
                options={customers}
                loading={customersLoading}
                value={selectedCustomer}
                onChange={(_e, value) => setSelectedCustomer(value)}
                inputValue={customerSearch}
                onInputChange={(_e, value) => setCustomerSearch(value)}
                filterOptions={x => x}
                disabled={!!prefillCustomerId}
                noOptionsText={
                  debouncedSearch.length === 0
                    ? 'Tapez un nom pour rechercher'
                    : 'Aucun client trouvé'
                }
                getOptionLabel={c =>
                  c.company_name ? `${c.full_name} (${c.company_name})` : c.full_name
                }
                isOptionEqualToValue={(a, b) => a.int_id === b.int_id}
                renderOption={(props, c) => (
                  <Box component="li" {...props} key={c.int_id}>
                    <Stack>
                      <Typography variant="body2" fontWeight={600}>
                        {c.full_name}
                        {c.company_name && (
                          <Typography component="span" variant="caption" color="text.secondary" ml={0.5}>
                            ({c.company_name})
                          </Typography>
                        )}
                      </Typography>
                      {(c.phone_e164 || c.email) && (
                        <Typography variant="caption" color="text.secondary">
                          {c.phone_e164 ?? c.email}
                        </Typography>
                      )}
                    </Stack>
                  </Box>
                )}
                renderInput={params => (
                  <TextField
                    {...params}
                    label="Client propriétaire"
                    placeholder="Rechercher par nom…"
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <>
                          {customersLoading && <CircularProgress color="inherit" size={16} />}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    }}
                  />
                )}
              />
            </SectionCard>
          </Stack>
        </Grid>
      </Grid>
    </Box>
  )
}
