import { useState, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
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
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import { customerApi, type CustomerSummary } from '../../lib/customerApi'
import { vehiclesApi, type VehicleOut } from '../../lib/vehiclesApi'
import { partsApi, type PartCategory, type PartSummary } from '../../lib/partsApi'
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

// Only expose 3 types in the UI — 'accessory' is kept in the type for DB compat
// but 'part' now covers both parts and accessories (categories distinguish them)
const LINE_KINDS = (['part', 'service', 'other'] as DeliveryNoteLineKind[]).map((value) => ({
  value,
  label: DELIVERY_NOTE_LINE_KIND_LABELS[value],
}))

interface LineRow {
  tempId: number
  kind: DeliveryNoteLineKind
  // part / accessory only
  selectedCategory: PartCategory | null
  selectedPart: PartSummary | null
  // all kinds
  description: string   // auto-filled for parts, manual for service/other
  quantity: string      // not used for 'service'
  unit_price: string    // decimal string (read-only for parts — from catalogue)
  remise_pct: string    // discount %, 0-100
  vat_rate: string
}

let _lineIdCounter = 0
function newLine(): LineRow {
  return {
    tempId: ++_lineIdCounter,
    kind: 'part',
    selectedCategory: null,
    selectedPart: null,
    description: '',
    quantity: '1',
    unit_price: '',
    remise_pct: '0',
    vat_rate: '20',
  }
}

function computeLineTotalMinor(l: LineRow): number {
  const qty = l.kind === 'service' ? 1 : (parseFloat(l.quantity) || 0)
  const basePriceMinor = Math.round((parseFloat(l.unit_price) || 0) * 100)
  const remise = Math.min(Math.max(parseFloat(l.remise_pct) || 0, 0), 100)
  const netPriceMinor = Math.round(basePriceMinor * (1 - remise / 100))
  const vat = parseFloat(l.vat_rate) || 0
  const sub = qty * netPriceMinor
  return sub + Math.round((sub * vat) / 100)
}

// ─── Per-line card component ──────────────────────────────────────────────────
function LineCard({
  line,
  lineNumber,
  categories,
  currency,
  onUpdate,
  onRemove,
  canRemove,
}: {
  line: LineRow
  lineNumber: number
  categories: PartCategory[]
  currency: string
  onUpdate: (id: number, updates: Partial<LineRow>) => void
  onRemove: (id: number) => void
  canRemove: boolean
}) {
  const [partSearch, setPartSearch] = useState('')
  const [debouncedPartSearch, setDebouncedPartSearch] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedPartSearch(partSearch), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [partSearch])

  const isPart = line.kind === 'part' || line.kind === 'accessory' // accessory = legacy DB value
  const isService = line.kind === 'service'

  const { data: partsData, isFetching: partsLoading } = useQuery({
    queryKey: ['parts', 'for-dn-line', line.selectedCategory?.id, debouncedPartSearch],
    queryFn: () =>
      partsApi.list({
        search: debouncedPartSearch || undefined,
        category_id: line.selectedCategory?.id,
        page_size: 40,
      }),
    enabled: isPart && !!line.selectedCategory,
    placeholderData: (prev) => prev,
  })
  const parts = partsData?.items ?? []

  // Progressive visibility
  const showCategoryPicker = isPart
  const showPartPicker = isPart && !!line.selectedCategory
  const showDescriptionField = !isPart
  const showPriceFields = isPart ? !!line.selectedPart : !!line.description.trim()
  const lineTotal = computeLineTotalMinor(line)

  return (
    <Card variant="outlined" sx={{ borderRadius: 2 }}>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Stack direction="row" alignItems="flex-start" spacing={1}>
          <Stack spacing={2} flex={1}>
            {/* Type selector */}
            <Stack direction="row" alignItems="center" spacing={1.5}>
              <Typography variant="caption" color="text.disabled" fontWeight={700} sx={{ minWidth: 22 }}>
                #{lineNumber}
              </Typography>
              <TextField
                select
                label="Type"
                value={line.kind}
                onChange={(e) =>
                  onUpdate(line.tempId, {
                    kind: e.target.value as DeliveryNoteLineKind,
                    selectedCategory: null,
                    selectedPart: null,
                    description: '',
                    unit_price: '',
                    remise_pct: '0',
                    quantity: '1',
                  })
                }
                size="small"
                sx={{ minWidth: 170 }}
              >
                {LINE_KINDS.map((k) => (
                  <MenuItem key={k.value} value={k.value}>{k.label}</MenuItem>
                ))}
              </TextField>
            </Stack>

            {/* Part/Accessory: category picker */}
            {showCategoryPicker && (
              <Autocomplete
                options={categories}
                value={line.selectedCategory}
                onChange={(_e, v) =>
                  onUpdate(line.tempId, {
                    selectedCategory: v,
                    selectedPart: null,
                    description: '',
                    unit_price: '',
                    remise_pct: '0',
                  })
                }
                getOptionLabel={(c) => c.name}
                isOptionEqualToValue={(a, b) => a.id === b.id}
                noOptionsText="Aucune catégorie"
                renderInput={(params) => (
                  <TextField {...params} label="Catégorie *" size="small" />
                )}
                sx={{ maxWidth: 340 }}
              />
            )}

            {/* Part/Accessory: part picker (only after category selected) */}
            {showPartPicker && (
              <Autocomplete
                options={parts}
                loading={partsLoading}
                value={line.selectedPart}
                onChange={(_e, v) => {
                  onUpdate(line.tempId, {
                    selectedPart: v,
                    description: v?.name ?? '',
                    unit_price: v ? String((v.selling_price_minor / 100).toFixed(2)) : '',
                  })
                }}
                inputValue={partSearch}
                onInputChange={(_e, v) => setPartSearch(v)}
                filterOptions={(x) => x}
                getOptionLabel={(p) => `${p.sku_code} — ${p.name}`}
                isOptionEqualToValue={(a, b) => a.id === b.id}
                noOptionsText={debouncedPartSearch ? 'Aucun résultat' : 'Tapez pour rechercher…'}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Pièce *"
                    size="small"
                    InputProps={{
                      ...params.InputProps,
                      endAdornment: (
                        <>
                          {partsLoading && <CircularProgress size={14} />}
                          {params.InputProps.endAdornment}
                        </>
                      ),
                    }}
                  />
                )}
              />
            )}

            {/* Service / Other: free-text description */}
            {showDescriptionField && (
              <TextField
                label={isService ? 'Prestation *' : 'Description *'}
                value={line.description}
                onChange={(e) => onUpdate(line.tempId, { description: e.target.value })}
                size="small"
                fullWidth
                placeholder={
                  isService
                    ? 'Ex: Vidange moteur, diagnostic électronique…'
                    : 'Description…'
                }
              />
            )}

            {/* Qty / Price / VAT — shown after part selected OR description entered */}
            {showPriceFields && (
              <Stack direction="row" spacing={2} flexWrap="wrap" alignItems="center">
                {/* No quantity for service */}
                {!isService && (
                  <TextField
                    label="Quantité"
                    value={line.quantity}
                    onChange={(e) => onUpdate(line.tempId, { quantity: e.target.value })}
                    size="small"
                    type="number"
                    inputProps={{ min: 0, step: 1, style: { textAlign: 'right' } }}
                    sx={{ width: 100 }}
                  />
                )}
                <Tooltip
                  title={isPart ? 'Prix fixé depuis le catalogue pièces — non modifiable ici' : ''}
                  placement="top"
                >
                  <TextField
                    label={`P.U. (${currency})`}
                    value={line.unit_price}
                    onChange={(e) => !isPart && onUpdate(line.tempId, { unit_price: e.target.value })}
                    size="small"
                    type="number"
                    inputProps={{ min: 0, step: 0.01, style: { textAlign: 'right' } }}
                    InputProps={{ readOnly: isPart }}
                    sx={{
                      width: 140,
                      ...(isPart && {
                        '& .MuiInputBase-root': { bgcolor: 'action.hover', cursor: 'default' },
                        '& input': { color: 'text.secondary' },
                      }),
                    }}
                  />
                </Tooltip>
                <TextField
                  label="Remise %"
                  value={line.remise_pct}
                  onChange={(e) => onUpdate(line.tempId, { remise_pct: e.target.value })}
                  size="small"
                  type="number"
                  inputProps={{ min: 0, max: 100, step: 1, style: { textAlign: 'right' } }}
                  sx={{ width: 100 }}
                  helperText={parseFloat(line.remise_pct) > 0 ? `−${line.remise_pct}%` : undefined}
                  FormHelperTextProps={{ sx: { color: 'success.main', fontWeight: 600, m: 0 } }}
                />
                <TextField
                  label="TVA %"
                  value={line.vat_rate}
                  size="small"
                  type="number"
                  inputProps={{ style: { textAlign: 'right' } }}
                  InputProps={{ readOnly: true }}
                  sx={{
                    width: 90,
                    '& .MuiInputBase-root': { bgcolor: 'action.hover', cursor: 'default' },
                    '& input': { color: 'text.secondary' },
                  }}
                />
                {lineTotal > 0 && (
                  <Typography
                    variant="body2"
                    fontFamily="monospace"
                    fontWeight={700}
                    color="primary.main"
                    sx={{ pl: 1 }}
                  >
                    ={' '}
                    {(lineTotal / 100).toLocaleString('fr-TN', {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{' '}
                    {currency}
                  </Typography>
                )}
              </Stack>
            )}

            {/* Part: show auto-filled description */}
            {isPart && line.selectedPart && (
              <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic', mt: -1 }}>
                {line.description}
              </Typography>
            )}
          </Stack>

          {/* Delete button */}
          <Tooltip title="Supprimer cette ligne">
            <span>
              <IconButton
                size="small"
                color="error"
                onClick={() => onRemove(line.tempId)}
                disabled={!canRemove}
                sx={{ mt: 0.5 }}
              >
                <DeleteOutlineRoundedIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
      </CardContent>
    </Card>
  )
}

export function DeliveryNoteCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { success, error: toastError } = useToast()
  const queryClient = useQueryClient()

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
  const [currency, setCurrency] = useState('EUR')

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

  // Categories fetched once, shared across all line cards
  const { data: categories = [] } = useQuery({
    queryKey: ['part-categories', 'for-dn'],
    queryFn: () => partsApi.listCategories({ flat: true }),
    staleTime: 5 * 60 * 1000,
  })

  const updateLine = (tempId: number, updates: Partial<LineRow>) => {
    setLines((prev) => prev.map((l) => (l.tempId === tempId ? { ...l, ...updates } : l)))
  }

  const removeLine = (tempId: number) => {
    setLines((prev) => prev.filter((l) => l.tempId !== tempId))
  }

  const grandTotal = lines.reduce((sum, l) => sum + computeLineTotalMinor(l), 0)

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
        .filter((l) => {
          if (l.kind === 'part' || l.kind === 'accessory') return !!l.selectedPart && !!l.unit_price
          return !!l.description.trim() && !!l.unit_price
        })
        .map((l) => ({
          kind: l.kind,
          part_id: l.selectedPart?.int_id ?? null,
          description: (l.description.trim() || l.selectedPart?.name || '').slice(0, 500),
          quantity: l.kind === 'service' ? 1 : (parseFloat(l.quantity) || 1),
          unit_price_minor: Math.round(
            Math.round((parseFloat(l.unit_price) || 0) * 100) *
            (1 - Math.min(Math.max(parseFloat(l.remise_pct) || 0, 0), 100) / 100)
          ),
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
      void queryClient.invalidateQueries({ queryKey: ['customer-delivery-notes'] })
      void queryClient.invalidateQueries({ queryKey: ['delivery-notes'] })
      navigate(returnTo ?? `/delivery-notes/${dn.public_id}`, { replace: true })
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

      {submitError && <Alert severity="error" sx={{ mb: 3 }}>{submitError}</Alert>}


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
              <Stack spacing={2}>
                {lines.map((line, idx) => (
                  <LineCard
                    key={line.tempId}
                    line={line}
                    lineNumber={idx + 1}
                    categories={categories}
                    currency={currency}
                    onUpdate={updateLine}
                    onRemove={removeLine}
                    canRemove={lines.length > 1}
                  />
                ))}

                <Stack direction="row" justifyContent="space-between" alignItems="center" mt={1}>
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<AddRoundedIcon />}
                    onClick={() => setLines((prev) => [...prev, newLine()])}
                  >
                    Ajouter une ligne
                  </Button>
                  {grandTotal > 0 && (
                    <Typography variant="body2" fontFamily="monospace" fontWeight={700}>
                      Total estimé:{' '}
                      {(grandTotal / 100).toLocaleString('fr-TN', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}{' '}
                      {currency}
                    </Typography>
                  )}
                </Stack>
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
                value={currency}
                fullWidth
                disabled
              />
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

