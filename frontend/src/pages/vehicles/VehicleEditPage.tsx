import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  Alert,
  Autocomplete,
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
  VEHICLE_STATUS_LABELS,
  type FuelType,
  type VehicleStatus,
} from '../../lib/vehiclesApi'
import { customerApi, type CustomerSummary } from '../../lib/customerApi'
import { mergeMakeOptions, mergeModelOptions } from '../../lib/vehicleOptions'
import { ConfirmableAutocomplete } from '../../components/vehicles/ConfirmableAutocomplete'
import { PageHeader } from '../../components/ui/PageHeader'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { useAuth } from '../../contexts/AuthContext'

const FUEL_TYPES = Object.entries(FUEL_TYPE_LABELS).map(([value, label]) => ({
  value: value as FuelType,
  label,
}))

const VEHICLE_STATUSES = Object.entries(VEHICLE_STATUS_LABELS).map(([value, label]) => ({
  value: value as VehicleStatus,
  label,
}))

const CURRENT_YEAR = new Date().getFullYear()

interface FormErrors {
  make?: string
  model?: string
  vin?: string
  year?: string
  mileage?: string
}

function validate(fields: {
  make: string
  model: string
  vin: string
  year: string
  mileage: string
}): FormErrors {
  const errors: FormErrors = {}
  if (!fields.make.trim()) errors.make = 'Champ obligatoire'
  if (!fields.model.trim()) errors.model = 'Champ obligatoire'
  const vin = fields.vin.trim()
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
          <Typography variant="subtitle1" fontWeight={700}>{title}</Typography>
        </Stack>
        <Divider sx={{ mb: 2.5 }} />
        {children}
      </CardContent>
    </Card>
  )
}

export function VehicleEditPage() {
  const { id = '' } = useParams<{ id: string }>()
  const vehicleId = Number(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const canDeleteCustomOptions = user?.permissions.includes('vehicle.delete') ?? false

  const { data: vehicle, isLoading, isError } = useQuery({
    queryKey: ['vehicle', vehicleId],
    queryFn: () => vehiclesApi.get(vehicleId),
    enabled: !!vehicleId,
  })

  // Form state
  const [make, setMake] = useState('')
  const [model, setModel] = useState('')
  const [trim, setTrim] = useState('')
  const [year, setYear] = useState('')
  const [fuelType, setFuelType] = useState<FuelType | ''>('')
  const [color, setColor] = useState('')
  const [vin, setVin] = useState('')
  const [mileage, setMileage] = useState('')
  const [ctDate, setCtDate] = useState('')
  const [maintenanceDate, setMaintenanceDate] = useState('')
  const [status, setStatus] = useState<VehicleStatus>('active')

  // Customer autocomplete
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerSummary | null>(null)
  const [customerInputValue, setCustomerInputValue] = useState('')
  const [customerSearch, setCustomerSearch] = useState('')
  const [debouncedCustomerSearch, setDebouncedCustomerSearch] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const previousMakeRef = useRef<string | null>(null)

  const [initialised, setInitialised] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  // Populate form once vehicle loads
  if (vehicle && !initialised) {
    setMake(vehicle.make)
    setModel(vehicle.model)
    setTrim(vehicle.trim ?? '')
    setYear(vehicle.year != null ? String(vehicle.year) : '')
    setFuelType(vehicle.fuel_type ?? '')
    setColor(vehicle.color ?? '')
    setVin(vehicle.vin ?? '')
    setMileage(vehicle.mileage_current != null ? String(vehicle.mileage_current) : '')
    setCtDate(vehicle.technical_inspection_due_at?.slice(0, 10) ?? '')
    setMaintenanceDate(vehicle.maintenance_due_at?.slice(0, 10) ?? '')
    setStatus(vehicle.status)
    setInitialised(true)
  }

  // Clear the model whenever the make changes to a genuinely different value —
  // but not on initial population, where make/model are set together from the loaded vehicle.
  useEffect(() => {
    if (!initialised) return
    if (previousMakeRef.current === null) {
      previousMakeRef.current = make
      return
    }
    if (previousMakeRef.current !== make) {
      previousMakeRef.current = make
      setModel('')
    }
  }, [make, initialised])

  // Fetch owner once vehicle loads (only if it has a customer_id)
  const { data: ownerData } = useQuery({
    queryKey: ['customer-by-int-id', vehicle?.customer_id],
    queryFn: () => customerApi.getByIntId(vehicle!.customer_id!),
    enabled: !!vehicle?.customer_id,
    staleTime: Infinity,
  })

  useEffect(() => {
    if (ownerData && !initialised) return // will be set during init
    if (ownerData && initialised && !selectedCustomer) {
      setSelectedCustomer(ownerData)
      const label = ownerData.company_name
        ? `${ownerData.full_name} (${ownerData.company_name})`
        : ownerData.full_name
      setCustomerInputValue(label)
    }
  }, [ownerData, initialised, selectedCustomer])

  // Pre-fill owner after both vehicle and owner data arrive
  useEffect(() => {
    if (vehicle && ownerData && initialised && !selectedCustomer) {
      setSelectedCustomer(ownerData)
      const label = ownerData.company_name
        ? `${ownerData.full_name} (${ownerData.company_name})`
        : ownerData.full_name
      setCustomerInputValue(label)
    }
  }, [vehicle, ownerData, initialised]) // eslint-disable-line react-hooks/exhaustive-deps

  // Debounce customer search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedCustomerSearch(customerSearch), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [customerSearch])

  const { data: customersData, isFetching: customersLoading } = useQuery({
    queryKey: ['customers', 'for-vehicle-edit', debouncedCustomerSearch],
    queryFn: () => customerApi.list({ status: 'active', q: debouncedCustomerSearch || undefined, page_size: 50 }),
    placeholderData: prev => prev,
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

  const errors = validate({ make, model, vin, year, mileage })
  const hasErrors = Object.keys(errors).length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    if (hasErrors) return
    setSubmitting(true)
    setServerError(null)
    try {
      await vehiclesApi.update(vehicleId, vehicle!.version, {
        make: make.trim(),
        model: model.trim(),
        trim: trim.trim() || null,
        year: year ? Number(year) : null,
        fuel_type: fuelType || null,
        color: color.trim() || null,
        mileage_current: mileage ? Number(mileage) : null,
        technical_inspection_due_at: ctDate || null,
        maintenance_due_at: maintenanceDate || null,
        status,
        customer_id: selectedCustomer?.int_id ?? null,
      })
      await queryClient.invalidateQueries({ queryKey: ['vehicle', vehicleId] })
      await queryClient.invalidateQueries({ queryKey: ['vehicles'] })
      navigate(`/vehicles/${vehicleId}`, { replace: true })
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status
        if (status === 409) {
          setServerError('Ce véhicule a été modifié par quelqu\'un d\'autre. Rechargez la page et réessayez.')
        } else {
          const d = err.response?.data
          const msg = typeof d?.detail === 'string' ? d.detail : JSON.stringify(d?.detail)
          setServerError(msg || 'Erreur lors de la mise à jour.')
        }
      } else {
        setServerError('Erreur lors de la mise à jour.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (isLoading) return <LoadingScreen />
  if (isError || !vehicle) {
    return (
      <Box>
        <PageHeader
          title="Modifier le véhicule"
          breadcrumbs={[{ label: 'Véhicules', href: '/vehicles' }, { label: 'Modifier' }]}
        />
        <Alert severity="error">Impossible de charger ce véhicule.</Alert>
      </Box>
    )
  }

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <PageHeader
        title={`Modifier — ${vehicle.make} ${vehicle.model}`}
        subtitle={vehicle.registration ?? vehicle.vin ?? `#${vehicle.id}`}
        breadcrumbs={[
          { label: 'Véhicules', href: '/vehicles' },
          { label: vehicle.registration ?? `${vehicle.make} ${vehicle.model}`, href: `/vehicles/${vehicleId}` },
          { label: 'Modifier' },
        ]}
        actions={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={<ArrowBackRoundedIcon />}
              onClick={() => navigate(`/vehicles/${vehicleId}`)}
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
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setServerError(null)}>
          {serverError}
        </Alert>
      )}

      <Grid container spacing={3} sx={{ maxWidth: 920 }}>
        {/* Left column */}
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
                    error={submitted && !!errors.model}
                    helperText={submitted ? errors.model : make ? undefined : 'Choisissez d’abord une marque'}
                    canDeleteCustomOptions={canDeleteCustomOptions}
                    onDeleteCustomOption={handleDeleteCustomModel}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    label="Version"
                    value={trim}
                    onChange={e => setTrim(e.target.value)}
                    fullWidth
                    placeholder="ex. 2.3 dCi 145 FWD 146cv"
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    label="Année"
                    type="number"
                    value={year}
                    onChange={e => setYear(e.target.value)}
                    fullWidth
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
                  />
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    label="Numéro VIN"
                    value={vin}
                    onChange={e => setVin(e.target.value.toUpperCase())}
                    fullWidth
                    inputProps={{ maxLength: 17, style: { fontFamily: 'monospace', fontSize: '0.875rem' } }}
                    error={submitted && !!errors.vin}
                    helperText={
                      submitted && errors.vin
                        ? errors.vin
                        : vin ? `${vin.length} / 17 caractères` : undefined
                    }
                  />
                </Grid>
              </Grid>
            </SectionCard>

            <SectionCard
              title="Statut"
            >
              <TextField
                label="Statut du véhicule"
                select
                value={status}
                onChange={e => setStatus(e.target.value as VehicleStatus)}
                fullWidth
              >
                {VEHICLE_STATUSES.map(s => (
                  <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>
                ))}
              </TextField>
            </SectionCard>
          </Stack>
        </Grid>

        {/* Right column */}
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
                  label="Contrôle technique"
                  type="date"
                  value={ctDate}
                  onChange={e => setCtDate(e.target.value)}
                  fullWidth
                  InputLabelProps={{ shrink: true }}
                />
                <TextField
                  label="Prochain entretien"
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
                inputValue={customerInputValue}
                onInputChange={(_e, value, reason) => {
                  setCustomerInputValue(value)
                  if (reason === 'input') setCustomerSearch(value)
                  if (reason === 'clear') setCustomerSearch('')
                }}
                filterOptions={x => x}
                noOptionsText={debouncedCustomerSearch ? 'Aucun client trouvé' : 'Tapez un nom pour rechercher'}
                getOptionLabel={c => c.company_name ? `${c.full_name} (${c.company_name})` : c.full_name}
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
