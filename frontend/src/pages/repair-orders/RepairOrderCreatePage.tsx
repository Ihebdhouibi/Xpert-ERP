import { useState, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
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
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import TuneRoundedIcon from '@mui/icons-material/TuneRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import { repairOrderApi } from '../../lib/repairOrderApi'
import { customerApi, type CustomerSummary } from '../../lib/customerApi'
import { vehiclesApi, type VehicleOut } from '../../lib/vehiclesApi'
import { VehicleQuickCreateDialog } from '../../components/vehicles/VehicleQuickCreateDialog'
import { useAuth } from '../../contexts/AuthContext'
import { PageHeader } from '../../components/ui/PageHeader'

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
  const [searchParams] = useSearchParams()
  const { user } = useAuth()
  const canCreateVehicle = user?.permissions.includes('vehicle.create') ?? false
  const canDeleteCustomOptions = user?.permissions.includes('vehicle.delete') ?? false
  const prefillVehicleId = searchParams.get('vehicleId') ? Number(searchParams.get('vehicleId')) : null
  const prefillCustomerId = searchParams.get('customerId') ? Number(searchParams.get('customerId')) : null

  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [vehicleDialogOpen, setVehicleDialogOpen] = useState(false)

  // Customer autocomplete state
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerSummary | null>(null)
  const [customerInputValue, setCustomerInputValue] = useState('')
  const [customerSearch, setCustomerSearch] = useState('')
  const [debouncedCustomerSearch, setDebouncedCustomerSearch] = useState('')
  const customerDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Vehicle autocomplete state
  const [selectedVehicle, setSelectedVehicle] = useState<VehicleOut | null>(null)
  const [vehicleInputValue, setVehicleInputValue] = useState('')
  const [vehicleSearch, setVehicleSearch] = useState('')
  const [debouncedVehicleSearch, setDebouncedVehicleSearch] = useState('')
  const vehicleDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Form fields
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('normal')

  // Validation errors
  const [fieldErrors, setFieldErrors] = useState<{ customer?: string }>({})

  // Debounce customer search
  useEffect(() => {
    if (customerDebounceRef.current) clearTimeout(customerDebounceRef.current)
    customerDebounceRef.current = setTimeout(() => setDebouncedCustomerSearch(customerSearch), 300)
    return () => { if (customerDebounceRef.current) clearTimeout(customerDebounceRef.current) }
  }, [customerSearch])

  // Debounce vehicle search
  useEffect(() => {
    if (vehicleDebounceRef.current) clearTimeout(vehicleDebounceRef.current)
    vehicleDebounceRef.current = setTimeout(() => setDebouncedVehicleSearch(vehicleSearch), 300)
    return () => { if (vehicleDebounceRef.current) clearTimeout(vehicleDebounceRef.current) }
  }, [vehicleSearch])

  // Prefill: fetch vehicle from URL param
  const { data: prefillVehicle } = useQuery({
    queryKey: ['vehicle-prefill', prefillVehicleId],
    queryFn: () => vehiclesApi.get(prefillVehicleId!),
    enabled: !!prefillVehicleId,
    staleTime: Infinity,
  })

  // Prefill: fetch customer from URL param
  const { data: prefillCustomer } = useQuery({
    queryKey: ['customer-prefill', prefillCustomerId],
    queryFn: () => customerApi.getByIntId(prefillCustomerId!),
    enabled: !!prefillCustomerId,
    staleTime: Infinity,
  })

  useEffect(() => {
    if (prefillVehicle) {
      setSelectedVehicle(prefillVehicle)
      const label = [prefillVehicle.registration, `${prefillVehicle.make} ${prefillVehicle.model}`, prefillVehicle.year]
        .filter(Boolean).join(' — ')
      setVehicleInputValue(label)
    }
  }, [prefillVehicle])

  useEffect(() => {
    if (prefillCustomer) {
      setSelectedCustomer(prefillCustomer)
      const label = prefillCustomer.company_name
        ? `${prefillCustomer.full_name} (${prefillCustomer.company_name})`
        : prefillCustomer.full_name
      setCustomerInputValue(label)
    }
  }, [prefillCustomer])

  // Customer search results
  const { data: customersData, isFetching: customersLoading } = useQuery({
    queryKey: ['customers', 'for-ro', debouncedCustomerSearch],
    queryFn: () => customerApi.list({ status: 'active', q: debouncedCustomerSearch || undefined, page_size: 50 }),
    placeholderData: keepPreviousData,
  })
  const customers = customersData?.items ?? []

  // Vehicle search results (filter by selected customer if one is chosen)
  const { data: vehiclesData, isFetching: vehiclesLoading } = useQuery({
    queryKey: ['vehicles', 'for-ro', debouncedVehicleSearch, selectedCustomer?.int_id],
    queryFn: () =>
      vehiclesApi.list({
        q: debouncedVehicleSearch || undefined,
        customer_id: selectedCustomer?.int_id,
        page_size: 50,
      }),
    placeholderData: keepPreviousData,
  })
  const vehicles = vehiclesData?.items ?? []

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errs: typeof fieldErrors = {}
    if (!selectedCustomer) errs.customer = 'Client requis'
    setFieldErrors(errs)
    if (Object.keys(errs).length > 0) return

    setIsSubmitting(true)
    setSubmitError(null)
    try {
      const ro = await repairOrderApi.create({
        customer_id: selectedCustomer!.int_id,
        vehicle_id: selectedVehicle?.id ?? null,
        description: description.trim() || undefined,
        priority: priority ?? null,
      })
      navigate(`/repair-orders/${ro.id}`)
    } catch (err) {
      let msg = 'Erreur lors de la création.'
      if (axios.isAxiosError(err) && err.response?.data) {
        const d = err.response.data
        msg = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail)
      }
      setSubmitError(msg)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Box component="form" onSubmit={handleSubmit}>
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
                {/* Customer autocomplete */}
                <Autocomplete
                  options={customers}
                  loading={customersLoading}
                  value={selectedCustomer}
                  onChange={(_e, value) => {
                    setSelectedCustomer(value)
                    // Clear vehicle if new customer selected and vehicle doesn't belong to them
                    if (value && selectedVehicle?.customer_id !== value.int_id) {
                      setSelectedVehicle(null)
                      setVehicleInputValue('')
                      setVehicleSearch('')
                    }
                  }}
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
                      label="Client *"
                      placeholder="Rechercher par nom…"
                      error={!!fieldErrors.customer}
                      helperText={fieldErrors.customer}
                      autoFocus
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

                {/* Vehicle autocomplete */}
                <Autocomplete
                  options={vehicles}
                  loading={vehiclesLoading}
                  value={selectedVehicle}
                  onChange={(_e, value) => setSelectedVehicle(value)}
                  inputValue={vehicleInputValue}
                  onInputChange={(_e, value, reason) => {
                    setVehicleInputValue(value)
                    if (reason === 'input') setVehicleSearch(value)
                    if (reason === 'clear') setVehicleSearch('')
                  }}
                  filterOptions={x => x}
                  noOptionsText={debouncedVehicleSearch ? 'Aucun véhicule trouvé' : 'Tapez pour rechercher'}
                  getOptionLabel={v =>
                    [v.registration, `${v.make} ${v.model}`, v.year].filter(Boolean).join(' — ')
                  }
                  isOptionEqualToValue={(a, b) => a.id === b.id}
                  renderOption={(props, v) => (
                    <Box component="li" {...props} key={v.id}>
                      <Stack>
                        <Typography variant="body2" fontWeight={600}>
                          {v.make} {v.model}
                          {v.year && (
                            <Typography component="span" variant="caption" color="text.secondary" ml={0.5}>
                              ({v.year})
                            </Typography>
                          )}
                        </Typography>
                        {v.registration && (
                          <Typography variant="caption" fontFamily="monospace" color="text.secondary">
                            {v.registration}
                          </Typography>
                        )}
                      </Stack>
                    </Box>
                  )}
                  renderInput={params => (
                    <TextField
                      {...params}
                      label="Véhicule"
                      placeholder="Rechercher par immatriculation…"
                      InputProps={{
                        ...params.InputProps,
                        endAdornment: (
                          <>
                            {vehiclesLoading && <CircularProgress color="inherit" size={16} />}
                            {params.InputProps.endAdornment}
                          </>
                        ),
                      }}
                    />
                  )}
                />

                {canCreateVehicle && selectedCustomer && (
                  <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
                    <Typography variant="caption" color="text.secondary">
                      {!vehiclesLoading && vehicles.length === 0 && !debouncedVehicleSearch
                        ? 'Ce client n’a aucun véhicule enregistré.'
                        : 'Le véhicule recherché n’existe pas ?'}
                    </Typography>
                    <Button
                      size="small"
                      startIcon={<AddRoundedIcon />}
                      onClick={() => setVehicleDialogOpen(true)}
                    >
                      Nouveau véhicule
                    </Button>
                  </Stack>
                )}

                <TextField
                  label="Description"
                  multiline
                  rows={4}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  helperText="Décrivez le problème signalé par le client"
                  fullWidth
                />
              </Stack>
            </SectionCard>
          </Stack>
        </Grid>

        <Grid item xs={12} md={5}>
          <Stack spacing={3}>
            <SectionCard
              title="Priorité"
              icon={<TuneRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Stack spacing={2.5}>
                <TextField
                  select
                  label="Priorité"
                  value={priority}
                  onChange={e => setPriority(e.target.value)}
                  fullWidth
                >
                  {PRIORITIES.map(p => (
                    <MenuItem key={p} value={p}>
                      <Stack direction="row" alignItems="center" spacing={1.25}>
                        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: PRIORITY_COLORS[p], flexShrink: 0 }} />
                        <span>{PRIORITY_LABELS[p]}</span>
                      </Stack>
                    </MenuItem>
                  ))}
                </TextField>
              </Stack>
            </SectionCard>
          </Stack>
        </Grid>
      </Grid>

      {selectedCustomer && (
        <VehicleQuickCreateDialog
          open={vehicleDialogOpen}
          customer={selectedCustomer}
          canDeleteCustomOptions={canDeleteCustomOptions}
          onClose={() => setVehicleDialogOpen(false)}
          onCreated={created => {
            setVehicleDialogOpen(false)
            setSelectedVehicle(created)
            const label = [created.registration, `${created.make} ${created.model}`, created.year]
              .filter(Boolean)
              .join(' — ')
            setVehicleInputValue(label)
            setVehicleSearch('')
          }}
        />
      )}
    </Box>
  )
}
