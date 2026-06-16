import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Divider,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import SaveRoundedIcon from '@mui/icons-material/SaveRounded'
import { PageHeader } from '../../components/ui/PageHeader'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'
import {
  bonRetourApi,
  BON_RETOUR_CONDITION_LABELS,
  type BonRetourLineCondition,
  type BonRetourPartyType,
} from '../../lib/bonRetourApi'
import { supplierApi } from '../../lib/supplierApi'
import { customerApi } from '../../lib/customerApi'
import { invoiceApi, type InvoiceOut } from '../../lib/invoiceApi'
import { partsApi, type PartSummary } from '../../lib/partsApi'

interface DraftLine {
  key: string
  part: PartSummary | null
  description: string
  qty: string
  price: string
  vat: string
  condition: BonRetourLineCondition | ''
  restock: boolean
}

function newLine(): DraftLine {
  return { key: crypto.randomUUID(), part: null, description: '', qty: '1', price: '0', vat: '20', condition: '', restock: true }
}

function useDebounced<T>(value: T, delay = 300): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return v
}

export function BonRetourCreatePage() {
  const navigate = useNavigate()
  const { error: toastError } = useToast()
  const [searchParams] = useSearchParams()
  const initialParty = (searchParams.get('party') as BonRetourPartyType) || 'supplier'

  const [party, setParty] = useState<BonRetourPartyType>(initialParty)
  const [supplier, setSupplier] = useState<{ int_id: number; name: string } | null>(null)
  const [customer, setCustomer] = useState<{ int_id: number; full_name: string } | null>(null)
  const [sourceInvoice, setSourceInvoice] = useState<InvoiceOut | null>(null)
  const [reason, setReason] = useState('')
  const [lines, setLines] = useState<DraftLine[]>([newLine()])

  const [supplierSearch, setSupplierSearch] = useState('')
  const [customerSearch, setCustomerSearch] = useState('')
  const [partSearch, setPartSearch] = useState('')
  const dSupplier = useDebounced(supplierSearch)
  const dCustomer = useDebounced(customerSearch)
  const dPart = useDebounced(partSearch)

  const { data: suppliers } = useQuery({
    queryKey: ['suppliers', 'bdr-picker', dSupplier],
    queryFn: () => supplierApi.list({ search: dSupplier || undefined, status: 'active', page_size: 50 }),
    enabled: party === 'supplier',
  })
  const { data: customers } = useQuery({
    queryKey: ['customers', 'bdr-picker', dCustomer],
    queryFn: () => customerApi.list({ q: dCustomer || undefined, status: 'active', page_size: 50 }),
    enabled: party === 'client',
  })
  const { data: invoices } = useQuery({
    queryKey: ['invoices', 'bdr-picker', customer?.int_id],
    queryFn: () => invoiceApi.list({ customer_id: customer!.int_id, page: 1, page_size: 100 }),
    enabled: party === 'client' && !!customer,
    select: data => data.items.filter(i => ['issued', 'partial', 'paid'].includes(i.status)),
  })
  const { data: parts } = useQuery({
    queryKey: ['parts', 'bdr-picker', dPart],
    queryFn: () => partsApi.list({ search: dPart || undefined, page_size: 25 }),
  })

  // Reset party-specific selections when switching party type
  useEffect(() => {
    setSupplier(null)
    setCustomer(null)
    setSourceInvoice(null)
  }, [party])

  const totals = useMemo(() => {
    let subtotal = 0
    let vat = 0
    for (const l of lines) {
      const lt = Math.round((parseFloat(l.price) || 0) * 100) * (parseFloat(l.qty) || 0)
      subtotal += lt
      vat += lt * (parseFloat(l.vat) || 0) / 100
    }
    return { subtotal: Math.round(subtotal), vat: Math.round(vat), total: Math.round(subtotal + vat) }
  }, [lines])

  const setLine = (key: string, patch: Partial<DraftLine>) =>
    setLines(prev => prev.map(l => (l.key === key ? { ...l, ...patch } : l)))

  const onPickPart = (key: string, part: PartSummary | null) => {
    if (!part) {
      setLine(key, { part: null })
      return
    }
    const priceMinor = party === 'supplier' ? part.purchase_price_minor : part.selling_price_minor
    setLine(key, { part, description: part.name, price: String(priceMinor / 100) })
  }

  const partyValid = party === 'supplier' ? !!supplier : !!customer
  const linesValid = lines.every(l => l.description.trim() !== '' && (parseFloat(l.qty) || 0) > 0)
  const canSubmit = partyValid && lines.length > 0 && linesValid

  const mutation = useMutation({
    mutationFn: () =>
      bonRetourApi.create({
        party_type: party,
        supplier_id: party === 'supplier' ? supplier!.int_id : null,
        customer_id: party === 'client' ? customer!.int_id : null,
        source_invoice_id: party === 'client' ? sourceInvoice?.id ?? null : null,
        reason: reason.trim() || null,
        lines: lines.map(l => ({
          part_id: l.part?.int_id ?? null,
          description: l.description.trim(),
          quantity: parseFloat(l.qty) || 0,
          unit_price_minor: Math.round((parseFloat(l.price) || 0) * 100),
          vat_rate: parseFloat(l.vat) || 0,
          condition: l.condition || null,
          restock: l.restock,
        })),
      }),
    onSuccess: result => navigate(`/bon-retour/${result.public_id}`, { replace: true }),
    onError: () => toastError('Impossible de créer le bon de retour.'),
  })

  return (
    <Box>
      <PageHeader
        title="Nouveau bon de retour"
        subtitle="Enregistrer un retour physique de pièces"
        breadcrumbs={[{ label: 'Bons de retour', href: '/bon-retour' }, { label: 'Nouveau' }]}
      />

      <Stack spacing={2.5} sx={{ maxWidth: 900 }}>
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <ToggleButtonGroup
            exclusive
            value={party}
            onChange={(_, v) => v && setParty(v)}
            size="small"
            sx={{ mb: 2.5 }}
          >
            <ToggleButton value="supplier">Retour fournisseur</ToggleButton>
            <ToggleButton value="client">Retour client</ToggleButton>
          </ToggleButtonGroup>

          <Stack spacing={2}>
            {party === 'supplier' ? (
              <Autocomplete
                options={suppliers?.items ?? []}
                getOptionLabel={s => s.name}
                isOptionEqualToValue={(a, b) => a.int_id === b.int_id}
                value={supplier as any}
                onChange={(_, v) => setSupplier(v ? { int_id: (v as any).int_id, name: (v as any).name } : null)}
                onInputChange={(_, v) => setSupplierSearch(v)}
                renderInput={params => <TextField {...params} label="Fournisseur" size="small" required />}
                noOptionsText="Aucun fournisseur"
              />
            ) : (
              <>
                <Autocomplete
                  options={customers?.items ?? []}
                  getOptionLabel={c => c.full_name}
                  isOptionEqualToValue={(a, b) => a.int_id === b.int_id}
                  value={customer as any}
                  onChange={(_, v) => setCustomer(v ? { int_id: (v as any).int_id, full_name: (v as any).full_name } : null)}
                  onInputChange={(_, v) => setCustomerSearch(v)}
                  renderInput={params => <TextField {...params} label="Client" size="small" required />}
                  noOptionsText="Aucun client"
                />
                <Autocomplete
                  options={invoices ?? []}
                  getOptionLabel={i => `${i.doc_number ?? `Brouillon #${i.id}`} — ${formatMinor(i.total_minor, i.currency)}`}
                  isOptionEqualToValue={(a, b) => a.id === b.id}
                  value={sourceInvoice}
                  onChange={(_, v) => setSourceInvoice(v)}
                  disabled={!customer}
                  renderInput={params => (
                    <TextField {...params} label="Facture d'origine (optionnel — requise pour l'avoir)" size="small" />
                  )}
                  noOptionsText="Aucune facture"
                />
              </>
            )}

            <TextField
              label="Motif du retour"
              value={reason}
              onChange={e => setReason(e.target.value)}
              size="small"
              fullWidth
              placeholder={party === 'supplier' ? 'Marchandise endommagée à la réception…' : 'Mauvaise référence, pièce non utilisée…'}
            />
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
            <Typography variant="subtitle2" fontWeight={700}>Pièces retournées</Typography>
            <Button size="small" startIcon={<AddRoundedIcon />} onClick={() => setLines(prev => [...prev, newLine()])}>
              Ajouter une ligne
            </Button>
          </Stack>

          <Stack spacing={1.5}>
            {lines.map(line => (
              <Stack key={line.key} direction={{ xs: 'column', md: 'row' }} spacing={1} alignItems="flex-start">
                <Autocomplete
                  sx={{ flex: 2, minWidth: 200 }}
                  options={parts?.items ?? []}
                  getOptionLabel={p => `${p.sku_code} — ${p.name}`}
                  isOptionEqualToValue={(a, b) => a.int_id === b.int_id}
                  value={line.part}
                  onChange={(_, v) => onPickPart(line.key, v)}
                  onInputChange={(_, v) => setPartSearch(v)}
                  renderOption={(props, p) => (
                    <Box component="li" {...props} key={p.int_id}>
                      <Stack>
                        <Typography variant="body2">{p.name}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {p.sku_code} · Stock : {p.stock_on_hand}
                        </Typography>
                      </Stack>
                    </Box>
                  )}
                  renderInput={params => <TextField {...params} label="Pièce (catalogue)" size="small" />}
                  noOptionsText="Aucune pièce"
                />
                <TextField
                  sx={{ flex: 2, minWidth: 160 }}
                  label="Description"
                  size="small"
                  value={line.description}
                  onChange={e => setLine(line.key, { description: e.target.value })}
                  required
                />
                <TextField
                  sx={{ width: 80 }}
                  label="Qté"
                  size="small"
                  type="number"
                  value={line.qty}
                  onChange={e => setLine(line.key, { qty: e.target.value })}
                />
                <TextField
                  sx={{ width: 110 }}
                  label="P.U. HT"
                  size="small"
                  type="number"
                  value={line.price}
                  onChange={e => setLine(line.key, { price: e.target.value })}
                />
                <TextField
                  sx={{ width: 90 }}
                  label="État"
                  size="small"
                  select
                  value={line.condition}
                  onChange={e => setLine(line.key, { condition: e.target.value as BonRetourLineCondition | '' })}
                >
                  <MenuItem value="">—</MenuItem>
                  {(Object.keys(BON_RETOUR_CONDITION_LABELS) as BonRetourLineCondition[]).map(c => (
                    <MenuItem key={c} value={c}>{BON_RETOUR_CONDITION_LABELS[c]}</MenuItem>
                  ))}
                </TextField>
                {party === 'client' && (
                  <FormControlLabel
                    sx={{ m: 0, whiteSpace: 'nowrap' }}
                    control={<Checkbox size="small" checked={line.restock} onChange={e => setLine(line.key, { restock: e.target.checked })} />}
                    label={<Typography variant="caption">Réintégrer</Typography>}
                  />
                )}
                <IconButton
                  size="small"
                  onClick={() => setLines(prev => (prev.length > 1 ? prev.filter(l => l.key !== line.key) : prev))}
                  disabled={lines.length === 1}
                >
                  <DeleteOutlineRoundedIcon fontSize="small" />
                </IconButton>
              </Stack>
            ))}
          </Stack>

          <Divider sx={{ my: 2 }} />
          <Stack spacing={0.5} sx={{ ml: 'auto', width: 240 }}>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="body2" color="text.secondary">Sous-total HT</Typography>
              <Typography variant="body2">{formatMinor(totals.subtotal)}</Typography>
            </Stack>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="body2" color="text.secondary">TVA</Typography>
              <Typography variant="body2">{formatMinor(totals.vat)}</Typography>
            </Stack>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="body2" fontWeight={700}>Total TTC</Typography>
              <Typography variant="body2" fontWeight={700}>{formatMinor(totals.total)}</Typography>
            </Stack>
          </Stack>
        </Paper>

        <Stack direction="row" spacing={1.5} justifyContent="flex-end">
          <Button color="inherit" onClick={() => navigate('/bon-retour')}>Annuler</Button>
          <Button
            variant="contained"
            startIcon={<SaveRoundedIcon />}
            disabled={!canSubmit || mutation.isPending}
            onClick={() => mutation.mutate()}
            sx={{ bgcolor: '#EA580C', '&:hover': { bgcolor: '#C2410C' } }}
          >
            {mutation.isPending ? 'Création…' : 'Créer le brouillon'}
          </Button>
        </Stack>
      </Stack>
    </Box>
  )
}
