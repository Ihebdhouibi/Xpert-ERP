import { useState, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  Grid,
  IconButton,
  InputAdornment,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import DeleteRoundedIcon from '@mui/icons-material/DeleteRounded'
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import { Autocomplete } from '@mui/material'
import { customerApi, type CustomerSummary } from '../../lib/customerApi'
import { vehiclesApi, type VehicleOut } from '../../lib/vehiclesApi'
import {
  deliveryNoteApi,
  DELIVERY_NOTE_LINE_KIND_LABELS,
  type DeliveryNoteLineKind,
  type DeliveryNoteLineCreateInput,
} from '../../lib/deliveryNoteApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { useToast } from '../../contexts/ToastContext'

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

const LINE_KINDS = Object.entries(DELIVERY_NOTE_LINE_KIND_LABELS).map(([value, label]) => ({
  value: value as DeliveryNoteLineKind,
  label,
}))

interface LineRow {
  tempId: number
  kind: DeliveryNoteLineKind
  description: string
  quantity: string
  unit_price: string
  vat_rate: string
}

let _lineIdCounter = 0
function newLine(): LineRow {
  return {
    tempId: ++_lineIdCounter,
    kind: 'part',
    description: '',
    quantity: '1',
    unit_price: '',
    vat_rate: '0',
  }
}

export function DeliveryNoteCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { success, error: toastError } = useToast()

  const prefillCustomerId = searchParams.get('customerId')
    ? Number(searchParams.get('customerId'))
    : null
  const returnTo = searchParams.get('returnTo') ?? null

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Customer
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerSummary | null>(null)
  const [customerSearch, setCustomerSearch] = useState('')
  const [debouncedCustomerSearch, setDebouncedCustomerSearch] = useState('')
  const customerDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Vehicle
  const [selectedVehicle, setSelectedVehicle] = useState<VehicleOut | null>(null)
  const [vehicleSearch, setVehicleSearch] = useState('')
  const [debouncedVehicleSearch, setDebouncedVehicleSearch] = useState('')
  const vehicleDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Lines
  const [lines, setLines] = useState<LineRow[]>([newLine()])

  // Header
  const [notes, setNotes] = useState('')
  const [currency, setCurrency] = useState('TND')

  // Validation
  const [fieldErrors, setFieldErrors] = useState<{ customer?: string }>({})

  useEffect(() => {
    if (customerDebounceRef.current) clearTimeout(customerDebounceRef.current)
    customerDebounceRef.current = setTimeout(() => setDebouncedCustomerSearch(customerSearch), 300)
    return () => { if (customerDebounceRef.current) clearTimeout(customerDebounceRef.current) }
  }, [customerSearch])

  useEffect(() => {
    if (vehicleDebounceRef.current) clearTimeout(vehicleDebounceRef.current)
    vehicleDebounceRef.current = setTimeout(() => setDebouncedVehicleSearch(vehicleSearch), 300)
    return () => { if (vehicleDebounceRef.current) clearTimeout(vehicleDebounceRef.current) }
  }, [vehicleSearch])

  // Prefill customer
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

  const { data: customersData, isFetching: customersLoading } = useQuery({
    queryKey: ['customers', 'for-dn', debouncedCustomerSearch],
    queryFn: () => customerApi.list({ status: 'active', q: debouncedCustomerSearch || undefined, page_size: 50 }),
    placeholderData: (prev) => prev,
  })
  const customers = customersData?.items ?? []

  const { data: vehiclesData, isFetching: vehiclesLoading } = useQuery({
    queryKey: ['vehicles', 'for-dn', debouncedVehicleSearch, selectedCustomer?.int_id],
    queryFn: () =>
      vehiclesApi.list({
        q: debouncedVehicleSearch || undefined,
        customer_id: selectedCustomer?.int_id,
        page_size: 50,
      }),
    placeholderData: (prev) => prev,
  })
  const vehicles = vehiclesData?.items ?? []

  const updateLine = (tempId: number, field: keyof LineRow, value: string) => {
    setLines((prev) =>
      prev.map((l) => (l.tempId === tempId ? { ...l, [field]: value } : l)),
    )
  }

  const removeLine = (tempId: number) => {
    setLines((prev) => prev.filter((l) => l.tempId !== tempId))
  }

  // Computed total
  const total = lines.reduce((sum, l) => {
    const qty = parseFloat(l.quantity) || 0
    const price = parseFloat(l.unit_price) * 100 || 0 // convert to minor
    const vat = parseFloat(l.vat_rate) || 0
    const lineTotal = qty * price
    return sum + lineTotal + (lineTotal * vat) / 100
  }, 0)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const errs: typeof fieldErrors = {}
    if (!selectedCustomer) errs.customer = 'Client requis'
    setFieldErrors(errs)
    if (Object.keys(errs).length > 0) return

    setIsSubmitting(true)
    setSubmitError(null)
    try {
      const apiLines: DeliveryNoteLineCreateInput[] = lines
        .filter((l) => l.description.trim() && l.unit_price)
        .map((l) => ({
          kind: l.kind,
          description: l.description.trim(),
          quantity: parseFloat(l.quantity) || 1,
          unit_price_minor: Math.round((parseFloat(l.unit_price) || 0) * 100),
          vat_rate: parseFloat(l.vat_rate) || 0,
        }))

      const dn = await deliveryNoteApi.create({
        customer_id: selectedCustomer!.int_id,
        vehicle_id: selectedVehicle?.id ?? null,
        currency,
        notes: notes.trim() || null,
        lines: apiLines,
      })

      success('Bon de livraison créé')
      if (returnTo) {
        navigate(returnTo, { replace: true })
      } else {
        navigate(`/delivery-notes/${dn.public_id}`, { replace: true })
      }
    } catch (err) {
      let msg = 'Erreur lors de la création.'
      if (axios.isAxiosError(err) && err.response?.data) {
        const d = err.response.data
        if (typeof d.detail === 'string') msg = d.detail
      }
      setSubmitError(msg)
      toastError(msg)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <PageHeader
        title="Nouveau bon de livraison"
        subtitle="Créez un BL pour une vente directe de pièces ou accessoires"
        breadcrumbs={[
          returnTo
            ? { label: 'Client', href: returnTo }
            : { label: 'Facturation', href: '/invoices' },
          { label: 'Nouveau BL' },
        ]}
        actions={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={<ArrowBackRoundedIcon />}
              onClick={() => navigate(returnTo ?? '/invoices')}
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
              Créer le BL
            </Button>
          </Stack>
        }
      />

      {submitError && (
        <Alert severity="error" sx={{ mb: 3 }}>{submitError}</Alert>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Stack spacing={3}>
            {/* Customer & Vehicle */}
            <SectionCard
              title="Client & Véhicule"
              icon={<PersonRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Stack spacing={2}>
                <Autocomplete
                  options={customers}
                  loading={customersLoading}
                  value={selectedCustomer}
                  onChange={(_e, v) => setSelectedCustomer(v)}
                  inputValue={customerSearch}
                  onInputChange={(_e, v) => setCustomerSearch(v)}
                  filterOptions={(x) => x}
                  disabled={!!prefillCustomerId}
                  noOptionsText={debouncedCustomerSearch ? 'Aucun résultat' : 'Tapez un nom…'}
                  getOptionLabel={(c) =>
                    c.company_name ? `${c.full_name} (${c.company_name})` : c.full_name
                  }
                  isOptionEqualToValue={(a, b) => a.int_id === b.int_id}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Client *"
                      error={!!fieldErrors.customer}
                      helperText={fieldErrors.customer}
                      InputProps={{
                        ...params.InputProps,
                        endAdornment: (
                          <>
                            {customersLoading && <CircularProgress size={16} />}
                            {params.InputProps.endAdornment}
                          </>
                        ),
                      }}
                    />
                  )}
                />

                <Autocomplete
                  options={vehicles}
                  loading={vehiclesLoading}
                  value={selectedVehicle}
                  onChange={(_e, v) => setSelectedVehicle(v)}
                  inputValue={vehicleSearch}
                  onInputChange={(_e, v) => setVehicleSearch(v)}
                  filterOptions={(x) => x}
                  noOptionsText={debouncedVehicleSearch ? 'Aucun résultat' : 'Optionnel — tapez pour rechercher'}
                  getOptionLabel={(v) =>
                    [v.registration, `${v.make} ${v.model}`, v.year].filter(Boolean).join(' — ')
                  }
                  isOptionEqualToValue={(a, b) => a.id === b.id}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Véhicule concerné (optionnel)"
                      InputProps={{
                        ...params.InputProps,
                        endAdornment: (
                          <>
                            {vehiclesLoading && <CircularProgress size={16} />}
                            {params.InputProps.endAdornment}
                          </>
                        ),
                      }}
                    />
                  )}
                />
              </Stack>
            </SectionCard>

            {/* Lines */}
            <SectionCard
              title="Lignes du bon de livraison"
              icon={<LocalShippingRoundedIcon sx={{ fontSize: 20 }} />}
            >
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ width: 110 }}>Type</TableCell>
                    <TableCell>Description</TableCell>
                    <TableCell sx={{ width: 80 }} align="right">Qté</TableCell>
                    <TableCell sx={{ width: 120 }} align="right">P.U. (TND)</TableCell>
                    <TableCell sx={{ width: 80 }} align="right">TVA %</TableCell>
                    <TableCell sx={{ width: 40 }} />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {lines.map((line) => (
                    <TableRow key={line.tempId}>
                      <TableCell>
                        <TextField
                          select
                          value={line.kind}
                          onChange={(e) => updateLine(line.tempId, 'kind', e.target.value)}
                          size="small"
                          fullWidth
                          variant="standard"
                        >
                          {LINE_KINDS.map((k) => (
                            <MenuItem key={k.value} value={k.value}>{k.label}</MenuItem>
                          ))}
                        </TextField>
                      </TableCell>
                      <TableCell>
                        <TextField
                          value={line.description}
                          onChange={(e) => updateLine(line.tempId, 'description', e.target.value)}
                          size="small"
                          fullWidth
                          variant="standard"
                          placeholder="Description…"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <TextField
                          value={line.quantity}
                          onChange={(e) => updateLine(line.tempId, 'quantity', e.target.value)}
                          size="small"
                          type="number"
                          inputProps={{ min: 0, step: 1, style: { textAlign: 'right' } }}
                          variant="standard"
                          sx={{ width: 60 }}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <TextField
                          value={line.unit_price}
                          onChange={(e) => updateLine(line.tempId, 'unit_price', e.target.value)}
                          size="small"
                          type="number"
                          inputProps={{ min: 0, step: 0.01, style: { textAlign: 'right' } }}
                          variant="standard"
                          sx={{ width: 100 }}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <TextField
                          value={line.vat_rate}
                          onChange={(e) => updateLine(line.tempId, 'vat_rate', e.target.value)}
                          size="small"
                          type="number"
                          inputProps={{ min: 0, max: 100, step: 1, style: { textAlign: 'right' } }}
                          variant="standard"
                          sx={{ width: 60 }}
                        />
                      </TableCell>
                      <TableCell>
                        <IconButton
                          size="small"
                          onClick={() => removeLine(line.tempId)}
                          disabled={lines.length === 1}
                        >
                          <DeleteRoundedIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <Stack direction="row" justifyContent="space-between" alignItems="center" mt={2}>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<AddRoundedIcon />}
                  onClick={() => setLines((prev) => [...prev, newLine()])}
                >
                  Ajouter une ligne
                </Button>
                <Typography variant="body2" fontFamily="monospace" fontWeight={700}>
                  Total estimé:{' '}
                  {(total / 100).toLocaleString('fr-FR', {
                    style: 'currency',
                    currency,
                    minimumFractionDigits: 3,
                  })}
                </Typography>
              </Stack>
            </SectionCard>
          </Stack>
        </Grid>

        {/* Right column */}
        <Grid item xs={12} md={4}>
          <SectionCard title="Options">
            <Stack spacing={2}>
              <TextField
                label="Devise"
                select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                fullWidth
              >
                <MenuItem value="TND">TND — Dinar Tunisien</MenuItem>
                <MenuItem value="EUR">EUR — Euro</MenuItem>
                <MenuItem value="USD">USD — Dollar</MenuItem>
              </TextField>
              <TextField
                label="Notes internes"
                multiline
                rows={4}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                fullWidth
                placeholder="Observations, conditions, remarques…"
              />
            </Stack>
          </SectionCard>
        </Grid>
      </Grid>
    </Box>
  )
}
