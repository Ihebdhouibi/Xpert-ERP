import { useState, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
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
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import ReceiptLongRoundedIcon from '@mui/icons-material/ReceiptLongRounded'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import { quotationApi, LINE_KIND_LABELS, type LineKind, type QuotationLineCreateInput } from '../../lib/quotationApi'
import { customerApi, type CustomerSummary } from '../../lib/customerApi'
import { vehiclesApi, type VehicleOut } from '../../lib/vehiclesApi'
import { partsApi, type PartSummary } from '../../lib/partsApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { useToast } from '../../contexts/ToastContext'

const LINE_KINDS: LineKind[] = ['labor', 'part', 'service', 'other']

const CURRENCIES = ['EUR']

interface DraftLine extends QuotationLineCreateInput {
  _key: number
  _partSearch?: string        // debounced search string for part autocomplete
  _selectedPart?: PartSummary | null
}

// ─── Part selector autocomplete ──────────────────────────────────────────────

function PartAutocomplete({
  value,
  inputValue,
  onInputChange,
  onChange,
}: {
  value: PartSummary | null
  inputValue: string
  onInputChange: (v: string) => void
  onChange: (part: PartSummary | null) => void
}) {
  const [debounced, setDebounced] = useState(inputValue)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleInput = (v: string) => {
    onInputChange(v)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setDebounced(v), 300)
  }

  const { data, isFetching } = useQuery({
    queryKey: ['parts-search', debounced],
    queryFn: () => partsApi.list({ search: debounced || undefined, page_size: 50 }),
    placeholderData: (prev: typeof data) => prev,
  })
  const parts = data?.items ?? []

  return (
    <Autocomplete
      options={parts}
      loading={isFetching}
      value={value}
      onChange={(_e, v) => onChange(v)}
      inputValue={inputValue}
      onInputChange={(_e, v) => handleInput(v)}
      filterOptions={x => x}
      noOptionsText={debounced ? 'Aucune pièce trouvée' : 'Tapez un nom ou référence'}
      getOptionLabel={p => `${p.sku_code} — ${p.name}`}
      isOptionEqualToValue={(a, b) => a.int_id === b.int_id}
      renderOption={(props, p) => (
        <Box component="li" {...props} key={p.int_id}>
          <Stack>
            <Typography variant="body2" fontWeight={600}>{p.name}</Typography>
            <Typography variant="caption" color="text.secondary" fontFamily="monospace">{p.sku_code}</Typography>
          </Stack>
        </Box>
      )}
      renderInput={params => (
        <TextField
          {...params}
          label="Pièce"
          size="small"
          sx={{ flex: 1 }}
          InputProps={{
            ...params.InputProps,
            endAdornment: (
              <>
                {isFetching && <CircularProgress size={16} />}
                {params.InputProps.endAdornment}
              </>
            ),
          }}
        />
      )}
    />
  )
}

// ─── Section card ─────────────────────────────────────────────────────────────

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

function computeLineTotals(lines: DraftLine[], currency: string) {
  let subtotal = 0
  let discountTotal = 0
  let vatTotal = 0

  for (const line of lines) {
    const unitMinor = Math.round((parseFloat(String(line.unit_price_minor)) || 0))
    const qty = parseInt(String(line.quantity), 10) || 0
    const discPct = parseFloat(String(line.discount_percent ?? '0')) || 0
    const vatPct = parseFloat(String(line.vat_rate ?? '0')) || 0
    const lineSubtotal = unitMinor * qty
    const lineDiscount = Math.round(lineSubtotal * discPct / 100)
    const lineBase = lineSubtotal - lineDiscount
    const lineVat = Math.round(lineBase * vatPct / 100)
    subtotal += lineSubtotal
    discountTotal += lineDiscount
    vatTotal += lineVat
  }

  const total = subtotal - discountTotal + vatTotal

  const fmt = (v: number) =>
    (v / 1000).toLocaleString('fr-FR', { minimumFractionDigits: 3 }) + ' ' + currency

  return { subtotal, discountTotal, vatTotal, total, fmt }
}

let _lineKey = 0

export function QuotationCreatePage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { error: toastError } = useToast()

  const prefillCustomerId = searchParams.get('customerId') ? Number(searchParams.get('customerId')) : null
  const prefillVehicleId = searchParams.get('vehicleId') ? Number(searchParams.get('vehicleId')) : null

  // Customer autocomplete
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerSummary | null>(null)
  const [customerInput, setCustomerInput] = useState('')
  const [customerSearch, setCustomerSearch] = useState('')
  const [debouncedCustomerSearch, setDebouncedCustomerSearch] = useState('')
  const customerDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Vehicle autocomplete
  const [selectedVehicle, setSelectedVehicle] = useState<VehicleOut | null>(null)
  const [vehicleInput, setVehicleInput] = useState('')
  const [vehicleSearch, setVehicleSearch] = useState('')
  const [debouncedVehicleSearch, setDebouncedVehicleSearch] = useState('')
  const vehicleDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Lines
  const [lines, setLines] = useState<DraftLine[]>([])

  // Header fields
  const [notes, setNotes] = useState('')
  const [validUntil, setValidUntil] = useState('')
  const [currency, setCurrency] = useState('EUR')

  const [submitError, setSubmitError] = useState<string | null>(null)
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

  // Prefill vehicle
  const { data: prefillVehicle } = useQuery({
    queryKey: ['vehicle-prefill', prefillVehicleId],
    queryFn: () => vehiclesApi.get(prefillVehicleId!),
    enabled: !!prefillVehicleId,
    staleTime: Infinity,
  })
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
      setCustomerInput(prefillCustomer.company_name
        ? `${prefillCustomer.full_name} (${prefillCustomer.company_name})`
        : prefillCustomer.full_name)
    }
  }, [prefillCustomer])

  useEffect(() => {
    if (prefillVehicle) {
      setSelectedVehicle(prefillVehicle)
      const label = [prefillVehicle.registration, `${prefillVehicle.make} ${prefillVehicle.model}`, prefillVehicle.year]
        .filter(Boolean).join(' — ')
      setVehicleInput(label)
    }
  }, [prefillVehicle])

  // Customer list
  const { data: customersData, isFetching: customersLoading } = useQuery({
    queryKey: ['customers', 'for-quotation', debouncedCustomerSearch],
    queryFn: () => customerApi.list({ status: 'active', q: debouncedCustomerSearch || undefined, page_size: 50 }),
    placeholderData: (prev: typeof customersData) => prev,
  })
  const customers = customersData?.items ?? []

  // Vehicle list
  const { data: vehiclesData, isFetching: vehiclesLoading } = useQuery({
    queryKey: ['vehicles', 'for-quotation', debouncedVehicleSearch, selectedCustomer?.int_id],
    queryFn: () => vehiclesApi.list({
      q: debouncedVehicleSearch || undefined,
      customer_id: selectedCustomer?.int_id,
      page_size: 50,
    }),
    placeholderData: (prev: typeof vehiclesData) => prev,
  })
  const vehicles = vehiclesData?.items ?? []

  const createMutation = useMutation({
    mutationFn: () =>
      quotationApi.create({
        customer_id: selectedCustomer!.int_id,
        vehicle_id: selectedVehicle?.id ?? null,
        currency,
        valid_until: validUntil || null,
        notes: notes.trim() || null,
        lines: lines.map(({ _key, _partSearch, _selectedPart, ...l }) => ({
          ...l,
          unit_price_minor: Math.round((parseFloat(String(l.unit_price_minor)) || 0)),
          quantity: parseInt(String(l.quantity), 10) || 1,
          discount_percent: parseFloat(String(l.discount_percent ?? '0')) || 0,
          vat_rate: parseFloat(String(l.vat_rate ?? '0')) || 0,
        })),
      }),
    onSuccess: (q) => {
      navigate(`/quotations/${q.public_id}`)
    },
    onError: (err) => {
      let msg = 'Erreur lors de la création.'
      if (axios.isAxiosError(err) && err.response?.data) {
        const d = err.response.data
        msg = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail)
      }
      setSubmitError(msg)
      toastError(msg)
    },
  })

  const addLine = () => {
    setLines(prev => [
      ...prev,
      { _key: ++_lineKey, kind: 'labor', description: '', quantity: 1, unit_price_minor: 0, discount_percent: 0, vat_rate: 20, _partSearch: '', _selectedPart: null },
    ])
  }

  const updateLine = (key: number, patch: Partial<DraftLine>) => {
    setLines(prev => prev.map(l => l._key === key ? { ...l, ...patch } : l))
  }

  const removeLine = (key: number) => {
    setLines(prev => prev.filter(l => l._key !== key))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const errs: typeof fieldErrors = {}
    if (!selectedCustomer) errs.customer = 'Client requis'
    setFieldErrors(errs)
    if (Object.keys(errs).length > 0) return
    setSubmitError(null)
    createMutation.mutate()
  }

  const totals = computeLineTotals(lines, currency)

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <PageHeader
        title="Nouveau devis"
        subtitle="Créez un devis commercial pour un client"
        breadcrumbs={[
          { label: 'Devis', href: '/quotations' },
          { label: 'Nouveau devis' },
        ]}
        actions={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={<ArrowBackRoundedIcon />}
              onClick={() => navigate('/quotations')}
              disabled={createMutation.isPending}
              sx={{ textTransform: 'none' }}
            >
              Annuler
            </Button>
            <Button
              type="submit"
              variant="contained"
              startIcon={<SaveRoundedIcon />}
              disabled={createMutation.isPending}
              sx={{ textTransform: 'none', fontWeight: 700 }}
            >
              {createMutation.isPending ? 'Création…' : 'Créer le devis'}
            </Button>
          </Stack>
        }
      />

      {submitError && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setSubmitError(null)}>
          {submitError}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* ── LEFT COLUMN ──────────────────────────────────────── */}
        <Grid item xs={12} md={8}>
          <Stack spacing={3}>

            {/* Client & Véhicule */}
            <SectionCard title="Client et véhicule" icon={<PersonRoundedIcon sx={{ fontSize: 20 }} />}>
              <Stack spacing={2.5}>
                {/* Customer */}
                <Autocomplete
                  options={customers}
                  loading={customersLoading}
                  value={selectedCustomer}
                  onChange={(_e, value) => {
                    setSelectedCustomer(value)
                    if (value && selectedVehicle?.customer_id !== value.int_id) {
                      setSelectedVehicle(null)
                      setVehicleInput('')
                      setVehicleSearch('')
                    }
                  }}
                  inputValue={customerInput}
                  onInputChange={(_e, value, reason) => {
                    setCustomerInput(value)
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
                      size="small"
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

                {/* Vehicle */}
                <Autocomplete
                  options={vehicles}
                  loading={vehiclesLoading}
                  value={selectedVehicle}
                  onChange={(_e, value) => setSelectedVehicle(value)}
                  inputValue={vehicleInput}
                  onInputChange={(_e, value, reason) => {
                    setVehicleInput(value)
                    if (reason === 'input') setVehicleSearch(value)
                    if (reason === 'clear') setVehicleSearch('')
                  }}
                  filterOptions={x => x}
                  noOptionsText={
                    !selectedCustomer
                      ? 'Sélectionnez d\'abord un client'
                      : debouncedVehicleSearch
                        ? 'Aucun véhicule trouvé'
                        : 'Tapez une immatriculation ou marque'
                  }
                  getOptionLabel={v =>
                    [v.registration, `${v.make} ${v.model}`, v.year].filter(Boolean).join(' — ')
                  }
                  isOptionEqualToValue={(a, b) => a.id === b.id}
                  renderOption={(props, v) => (
                    <Box component="li" {...props} key={v.id}>
                      <Stack>
                        <Typography variant="body2" fontWeight={600} fontFamily="monospace">
                          {v.registration ?? '—'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {v.make} {v.model}{v.year ? ` (${v.year})` : ''}
                        </Typography>
                      </Stack>
                    </Box>
                  )}
                  renderInput={params => (
                    <TextField
                      {...params}
                      label="Véhicule (optionnel)"
                      size="small"
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
            <SectionCard title="Lignes du devis" icon={<DescriptionRoundedIcon sx={{ fontSize: 20 }} />}>
              {lines.length === 0 ? (
                <Typography variant="body2" color="text.secondary" textAlign="center" py={2}>
                  Aucune ligne pour l'instant. Ajoutez une ligne pour commencer.
                </Typography>
              ) : (
                <Stack spacing={1.5} mb={2}>
                  {lines.map((line, idx) => {
                    const isLabor = line.kind === 'labor'
                    const isPart = line.kind === 'part'
                    const lineUnitMinor = line.unit_price_minor
                    const lineQty = parseInt(String(line.quantity), 10) || 0
                    const lineDisc = parseFloat(String(line.discount_percent ?? 0)) || 0
                    const lineVat = parseFloat(String(line.vat_rate ?? 0)) || 0
                    const lineBase = lineUnitMinor * lineQty * (1 - lineDisc / 100)
                    const lineTotal = lineBase * (1 + lineVat / 100)

                    return (
                      <Box
                        key={line._key}
                        sx={{ p: 2, bgcolor: '#F8FAFC', borderRadius: 1.5, border: '1px solid #E2E8F0' }}
                      >
                        <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1.25}>
                          <Typography variant="caption" fontWeight={700} color="text.secondary">
                            Ligne {idx + 1}
                          </Typography>
                          <Tooltip title="Supprimer la ligne">
                            <IconButton size="small" color="error" onClick={() => removeLine(line._key)}>
                              <DeleteOutlineRoundedIcon sx={{ fontSize: 16 }} />
                            </IconButton>
                          </Tooltip>
                        </Stack>

                        <Stack spacing={1.5}>
                          {/* Row 1: type + description/part selector */}
                          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                            <TextField
                              select
                              size="small"
                              label="Type"
                              value={line.kind ?? 'labor'}
                              onChange={e => updateLine(line._key, {
                                kind: e.target.value as LineKind,
                                description: '',
                                _selectedPart: null,
                                _partSearch: '',
                              })}
                              sx={{ minWidth: 130 }}
                            >
                              {LINE_KINDS.map(k => (
                                <MenuItem key={k} value={k}>{LINE_KIND_LABELS[k]}</MenuItem>
                              ))}
                            </TextField>

                            {isPart ? (
                              <PartAutocomplete
                                value={line._selectedPart ?? null}
                                inputValue={line._partSearch ?? ''}
                                onInputChange={v => updateLine(line._key, { _partSearch: v })}
                                onChange={part => {
                                  if (part) {
                                    updateLine(line._key, {
                                      _selectedPart: part,
                                      description: part.name,
                                      unit_price_minor: part.selling_price_minor,
                                    })
                                  } else {
                                    updateLine(line._key, { _selectedPart: null, description: '', unit_price_minor: 0 })
                                  }
                                }}
                              />
                            ) : (
                              <TextField
                                size="small"
                                label="Description"
                                value={line.description}
                                onChange={e => updateLine(line._key, { description: e.target.value })}
                                sx={{ flex: 1 }}
                                required
                              />
                            )}
                          </Stack>

                          {/* Row 2: qty (not for labor) + price + discount + vat + total */}
                          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems="flex-start">
                            {!isLabor && (
                              <TextField
                                size="small"
                                label="Quantité"
                                type="number"
                                value={line.quantity}
                                onChange={e => updateLine(line._key, { quantity: parseInt(e.target.value, 10) || 1 })}
                                sx={{ width: 90 }}
                                inputProps={{ min: 1, step: 1 }}
                              />
                            )}
                            <TextField
                              size="small"
                              label="Prix"
                              type="number"
                              value={lineUnitMinor === 0 ? '' : String(lineUnitMinor / 100)}
                              onChange={e => updateLine(line._key, { unit_price_minor: Math.round((parseFloat(e.target.value) || 0) * 100) })}
                              sx={{ flex: 1, minWidth: 120 }}
                              inputProps={{ min: 0, step: 0.001 }}
                              InputProps={{
                                endAdornment: <Typography variant="caption" color="text.secondary">{currency}</Typography>,
                              }}
                              required
                            />
                            <TextField
                              size="small"
                              label="Remise %"
                              type="number"
                              value={line.discount_percent ?? 0}
                              onChange={e => updateLine(line._key, { discount_percent: parseFloat(e.target.value) || 0 })}
                              sx={{ width: 100 }}
                              inputProps={{ min: 0, max: 100 }}
                            />
                            <TextField
                              size="small"
                              label="TVA %"
                              type="number"
                              value={line.vat_rate ?? 20}
                              inputProps={{ style: {} }}
                              InputProps={{ readOnly: true }}
                              sx={{
                                width: 90,
                                '& .MuiInputBase-root': { bgcolor: 'action.hover', cursor: 'default' },
                                '& input': { color: 'text.secondary' },
                              }}
                            />
                            <Box sx={{ minWidth: 90, pt: 0.75, textAlign: 'right' }}>
                              <Typography variant="caption" color="text.secondary" display="block" fontSize="0.65rem">
                                Total HT
                              </Typography>
                              <Typography variant="body2" fontWeight={700} fontFamily="monospace">
                                {(lineTotal / 1000).toLocaleString('fr-FR', { minimumFractionDigits: 3 })} {currency}
                              </Typography>
                            </Box>
                          </Stack>
                        </Stack>
                      </Box>
                    )
                  })}
                </Stack>
              )}

              <Button
                variant="outlined"
                fullWidth
                startIcon={<AddRoundedIcon />}
                onClick={addLine}
                sx={{ textTransform: 'none', fontWeight: 600, borderStyle: 'dashed' }}
              >
                Ajouter une ligne
              </Button>
            </SectionCard>

            {/* Options */}
            <SectionCard title="Options du devis" icon={<ReceiptLongRoundedIcon sx={{ fontSize: 20 }} />}>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2, p: 1.5, bgcolor: '#F0F9FF', borderRadius: 1.5, border: '1px solid #BAE6FD' }}>
                <InfoOutlinedIcon sx={{ fontSize: 16, color: '#0369A1', mt: 0.25, flexShrink: 0 }} />
                <Typography variant="caption" color="#0369A1">
                  <strong>Devise</strong> — monnaie utilisée pour toutes les lignes du devis.<br />
                  <strong>Valide jusqu'au</strong> — date limite au-delà de laquelle le devis expire automatiquement.<br />
                  <strong>Notes internes</strong> — commentaires visibles uniquement en interne (non imprimés sur le PDF client).
                </Typography>
              </Box>
              <Stack spacing={2.5}>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                  <TextField
                    size="small"
                    label="Devise"
                    value={currency}
                    disabled
                    sx={{ width: 130 }}
                  />
                  <TextField
                    size="small"
                    label="Valide jusqu'au"
                    type="date"
                    value={validUntil}
                    onChange={e => setValidUntil(e.target.value)}
                    InputLabelProps={{ shrink: true }}
                    sx={{ flex: 1 }}
                  />
                </Stack>
                <TextField
                  size="small"
                  label="Notes internes (optionnel)"
                  multiline
                  minRows={2}
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  fullWidth
                />
              </Stack>
            </SectionCard>

          </Stack>
        </Grid>

        {/* ── RIGHT COLUMN — live summary ───────────────────── */}
        <Grid item xs={12} md={4}>
          <Box sx={{ position: 'sticky', top: 24 }}>
            <Card>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="subtitle1" fontWeight={700} mb={2.5}>
                  Récapitulatif
                </Typography>
                <Box sx={{ bgcolor: '#F8FAFC', borderRadius: 1.5, p: 2, mb: 2.5 }}>
                  <Stack direction="row" justifyContent="space-between" py={0.75}>
                    <Typography variant="body2" color="text.secondary">Sous-total HT</Typography>
                    <Typography variant="body2" fontWeight={500} fontFamily="monospace">
                      {totals.fmt(totals.subtotal)}
                    </Typography>
                  </Stack>
                  {totals.discountTotal > 0 && (
                    <Stack direction="row" justifyContent="space-between" py={0.75}>
                      <Typography variant="body2" color="text.secondary">Remise</Typography>
                      <Typography variant="body2" fontWeight={500} color="warning.dark" fontFamily="monospace">
                        − {totals.fmt(totals.discountTotal)}
                      </Typography>
                    </Stack>
                  )}
                  <Stack direction="row" justifyContent="space-between" py={0.75}>
                    <Typography variant="body2" color="text.secondary">TVA</Typography>
                    <Typography variant="body2" fontWeight={500} fontFamily="monospace">
                      {totals.fmt(totals.vatTotal)}
                    </Typography>
                  </Stack>
                  <Divider sx={{ my: 1 }} />
                  <Stack direction="row" justifyContent="space-between" py={0.5}>
                    <Typography variant="body2" fontWeight={700}>Total TTC</Typography>
                    <Typography variant="body2" fontWeight={800} fontFamily="monospace" color="primary.main">
                      {totals.fmt(totals.total)}
                    </Typography>
                  </Stack>
                </Box>

                {/* Summary stats */}
                <Stack spacing={0.75} mb={2.5}>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="caption" color="text.secondary">Client</Typography>
                    <Typography variant="caption" fontWeight={600} textAlign="right" sx={{ maxWidth: 160 }}>
                      {selectedCustomer
                        ? selectedCustomer.company_name
                          ? `${selectedCustomer.full_name} (${selectedCustomer.company_name})`
                          : selectedCustomer.full_name
                        : <Typography component="span" variant="caption" color="text.disabled">Non sélectionné</Typography>
                      }
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="caption" color="text.secondary">Véhicule</Typography>
                    <Typography variant="caption" fontWeight={600} fontFamily={selectedVehicle ? 'monospace' : 'inherit'} textAlign="right">
                      {selectedVehicle
                        ? [selectedVehicle.registration, `${selectedVehicle.make} ${selectedVehicle.model}`].filter(Boolean).join(' — ')
                        : <Typography component="span" variant="caption" color="text.disabled">—</Typography>
                      }
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="caption" color="text.secondary">Lignes</Typography>
                    <Typography variant="caption" fontWeight={600}>{lines.length}</Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="caption" color="text.secondary">Devise</Typography>
                    <Typography variant="caption" fontWeight={600}>{currency}</Typography>
                  </Stack>
                  {validUntil && (
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="caption" color="text.secondary">Valable jusqu'au</Typography>
                      <Typography variant="caption" fontWeight={600}>
                        {new Date(validUntil).toLocaleDateString('fr-FR')}
                      </Typography>
                    </Stack>
                  )}
                </Stack>

                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  startIcon={<SaveRoundedIcon />}
                  disabled={createMutation.isPending || !selectedCustomer}
                  sx={{ textTransform: 'none', fontWeight: 700 }}
                >
                  {createMutation.isPending ? 'Création…' : 'Créer le devis'}
                </Button>
                {!selectedCustomer && (
                  <Typography variant="caption" color="text.secondary" display="block" textAlign="center" mt={0.75}>
                    Sélectionnez un client pour continuer.
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Box>
        </Grid>
      </Grid>
    </Box>
  )
}
