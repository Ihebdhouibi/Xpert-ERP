import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputLabel,
  ListItemIcon,
  Menu,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import TableChartIcon from '@mui/icons-material/TableChart'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorIcon from '@mui/icons-material/Error'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import GavelIcon from '@mui/icons-material/Gavel'
import ThumbUpAltIcon from '@mui/icons-material/ThumbUpAlt'
import PaymentsIcon from '@mui/icons-material/Payments'
import CancelIcon from '@mui/icons-material/Cancel'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import AttachFileIcon from '@mui/icons-material/AttachFile'

import {
  supplierInvoiceApi,
  SupplierInvoice,
  SILine,
  SIStatus,
  SIMatchStatus,
  SICreatePayload,
  STATUS_LABELS,
  MATCH_STATUS_LABELS,
} from '../../lib/supplierInvoiceApi'
import { supplierApi, Supplier } from '../../lib/supplierApi'
import { purchaseOrderApi, PurchaseOrder } from '../../lib/purchaseOrderApi'
import { partsApi, type PartSummary } from '../../lib/partsApi'
import { apiClient } from '../../lib/apiClient'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { DataTable } from '../../components/ui/DataTable'
import { useToast } from '../../contexts/ToastContext'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------


const MATCH_COLORS: Record<SIMatchStatus, 'success' | 'warning' | 'error'> = {
  ok: 'success',
  qty_mismatch: 'error',
  price_mismatch: 'warning',
}

const MATCH_ICONS: Record<SIMatchStatus, JSX.Element> = {
  ok: <CheckCircleIcon color="success" fontSize="small" />,
  qty_mismatch: <ErrorIcon color="error" fontSize="small" />,
  price_mismatch: <WarningAmberIcon color="warning" fontSize="small" />,
}

function fmt(minor: number) {
  return (minor / 100).toLocaleString('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }) + ' €'
}

// ---------------------------------------------------------------------------
// CreateDialog
// ---------------------------------------------------------------------------

interface CreateDialogProps {
  open: boolean
  onClose: () => void
  onCreated: (si: SupplierInvoice) => void
}

interface LineForm {
  po_line_id: number | null
  part_public_id: string
  part_name: string
  description: string
  quantity: number
  unit_price_eur: number
  vat_rate: number
}

function CreateDialog({ open, onClose, onCreated }: CreateDialogProps) {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [pos, setPos] = useState<PurchaseOrder[]>([])
  const [supplierPublicId, setSupplierPublicId] = useState('')
  const [poPublicId, setPoPublicId] = useState('')
  const [selectedPo, setSelectedPo] = useState<PurchaseOrder | null>(null)
  const [number, setNumber] = useState('')
  const [receivedAt, setReceivedAt] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<LineForm[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [extraLinePart, setExtraLinePart] = useState<PartSummary | null>(null)

  const { data: partsData } = useQuery({
    queryKey: ['parts-all'],
    queryFn: () => partsApi.list({ page_size: 200 }),
    enabled: open,
  })
  const allParts: PartSummary[] = partsData?.items ?? []

  useEffect(() => {
    if (!open) return
    supplierApi.list({ status: 'active', page_size: 100 }).then((r) => setSuppliers(r.items))
  }, [open])

  useEffect(() => {
    if (!supplierPublicId) {
      setPos([])
      setPoPublicId('')
      setSelectedPo(null)
      setLines([])
      return
    }
    purchaseOrderApi
      .list({ page_size: 100 })
      .then((r) =>
        setPos(
          r.items.filter(
            (po) =>
              ['sent', 'partially_received', 'completed'].includes(po.status) &&
              (po.supplier_public_id === supplierPublicId || !po.supplier_public_id),
          ),
        ),
      )
  }, [supplierPublicId])

  useEffect(() => {
    if (!poPublicId) {
      setSelectedPo(null)
      setLines([])
      return
    }
    const found = pos.find((p) => p.id === poPublicId) ?? null
    setSelectedPo(found)
    if (found) {
      setLines(
        found.lines.map((l) => ({
          po_line_id: l.id,
          part_public_id: '',
          part_name: l.part_name ?? `Pièce #${l.part_id}`,
          description: l.part_name ?? '',
          quantity: l.quantity_received > 0 ? l.quantity_received : l.quantity_ordered,
          unit_price_eur: l.unit_price_ht / 100,
          vat_rate: 20,
        })),
      )
    } else {
      setLines([])
    }
  }, [poPublicId, pos])

  const updateLine = (i: number, field: keyof LineForm, value: string | number | null) =>
    setLines((l) => l.map((ln, idx) => (idx === i ? { ...ln, [field]: value } : ln)))

  const removeLine = (i: number) =>
    setLines((prev) => prev.filter((_, idx) => idx !== i))

  const addExtraLine = (part: PartSummary) => {
    setLines((prev) => [
      ...prev,
      {
        po_line_id: null,
        part_public_id: part.id,
        part_name: part.name,
        description: part.name,
        quantity: 1,
        unit_price_eur: 0,
        vat_rate: 20,
      },
    ])
    setExtraLinePart(null)
  }

  const totalHtEur = lines.reduce((s, l) => s + l.unit_price_eur * l.quantity, 0)
  const totalTtcEur = lines.reduce(
    (s, l) => s + l.unit_price_eur * l.quantity * (1 + l.vat_rate / 100),
    0,
  )

  const handleSubmit = async () => {
    setError('')
    if (!supplierPublicId) { setError('Sélectionnez un fournisseur'); return }
    if (!poPublicId) { setError('Sélectionnez un bon de commande'); return }
    if (!number.trim()) { setError('Numéro de facture requis'); return }
    if (lines.length === 0) { setError('Au moins une ligne est requise'); return }
    setSaving(true)
    try {
      const payload: SICreatePayload = {
        supplier_public_id: supplierPublicId,
        po_public_id: poPublicId,
        number: number.trim(),
        lines: lines.map((l) => ({
          ...(l.po_line_id !== null ? { po_line_id: l.po_line_id } : { part_public_id: l.part_public_id }),
          description: l.description,
          quantity: l.quantity,
          unit_price_ht: Math.round(l.unit_price_eur * 100),
          vat_rate: l.vat_rate,
        })),
        received_at: receivedAt || null,
        due_date: dueDate || null,
        notes: notes || null,
      }
      const si = await supplierInvoiceApi.create(payload)
      onCreated(si)
      setSupplierPublicId('')
      setPoPublicId('')
      setNumber('')
      setReceivedAt('')
      setDueDate('')
      setNotes('')
      setLines([])
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Erreur lors de la création')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle>Nouvelle facture fournisseur</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}
          <Stack direction="row" spacing={2}>
            <FormControl fullWidth>
              <InputLabel>Fournisseur</InputLabel>
              <Select
                value={supplierPublicId}
                label="Fournisseur"
                onChange={(e) => setSupplierPublicId(e.target.value)}
              >
                {suppliers.map((s) => (
                  <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth disabled={!supplierPublicId}>
              <InputLabel>Bon de commande</InputLabel>
              <Select
                value={poPublicId}
                label="Bon de commande"
                onChange={(e) => setPoPublicId(e.target.value)}
              >
                {pos.map((po) => (
                  <MenuItem key={po.id} value={po.id}>
                    {po.doc_number ?? po.id} — {fmt(po.total_ht)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField
              label="N° facture fournisseur"
              fullWidth
              value={number}
              onChange={(e) => setNumber(e.target.value)}
            />
            <TextField
              label="Date de réception"
              type="datetime-local"
              fullWidth
              InputLabelProps={{ shrink: true }}
              value={receivedAt}
              onChange={(e) => setReceivedAt(e.target.value)}
            />
            <TextField
              label="Échéance"
              type="date"
              fullWidth
              InputLabelProps={{ shrink: true }}
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
          </Stack>
          <TextField
            label="Notes"
            multiline
            rows={2}
            fullWidth
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />

          {selectedPo && (
            <>
              <Typography variant="subtitle2">Lignes</Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Pièce</TableCell>
                    <TableCell>Note</TableCell>
                    <TableCell align="right">Qté reçue (BC)</TableCell>
                    <TableCell align="right">Qté facturée</TableCell>
                    <TableCell align="right">PU HT (€)</TableCell>
                    <TableCell align="right">TVA %</TableCell>
                    <TableCell align="right">Total HT</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {lines.map((ln, i) => {
                    const poLine = selectedPo?.lines.find((l) => l.id === ln.po_line_id)
                    return (
                      <TableRow key={i}>
                        <TableCell>
                          <Typography variant="body2" fontWeight={600}>{ln.part_name}</Typography>
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            placeholder="Note optionnelle"
                            value={ln.description}
                            onChange={(e) => updateLine(i, 'description', e.target.value)}
                            variant="standard"
                            sx={{ minWidth: 120 }}
                          />
                        </TableCell>
                        <TableCell align="right">
                          {poLine?.quantity_received ?? '—'}
                        </TableCell>
                        <TableCell align="right">
                          <TextField
                            size="small"
                            type="number"
                            value={ln.quantity}
                            onChange={(e) => updateLine(i, 'quantity', Math.max(1, parseInt(e.target.value) || 1))}
                            inputProps={{ min: 1, style: { width: 70 } }}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <TextField
                            size="small"
                            type="number"
                            value={ln.unit_price_eur || ''}
                            onChange={(e) => {
                              const v = parseFloat(e.target.value)
                              updateLine(i, 'unit_price_eur', isNaN(v) ? 0 : v)
                            }}
                            onBlur={(e) => {
                              const v = parseFloat(e.target.value)
                              if (!isNaN(v)) updateLine(i, 'unit_price_eur', Math.round(v * 100) / 100)
                            }}
                            inputProps={{ min: 0, step: 1, style: { width: 90 } }}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <TextField
                            size="small"
                            type="number"
                            value={ln.vat_rate}
                            onChange={(e) => updateLine(i, 'vat_rate', parseFloat(e.target.value) || 0)}
                            inputProps={{ min: 0, max: 100, style: { width: 60 } }}
                          />
                        </TableCell>
                        <TableCell align="right">
                          {(ln.unit_price_eur * ln.quantity).toFixed(2)} €
                        </TableCell>
                        <TableCell>
                          {ln.po_line_id === null && (
                            <IconButton size="small" onClick={() => removeLine(i)} color="error">
                              <DeleteOutlineIcon fontSize="small" />
                            </IconButton>
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>

              {/* Extra line adder */}
              <Stack direction="row" spacing={1} alignItems="center">
                <Autocomplete
                  options={allParts}
                  getOptionLabel={(p) => `${p.name} (${p.sku_code})`}
                  value={extraLinePart}
                  onChange={(_, val) => setExtraLinePart(val)}
                  size="small"
                  sx={{ minWidth: 260 }}
                  renderInput={(params) => <TextField {...params} label="Ajouter une pièce (optionnel)" />}
                />
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<AddIcon />}
                  disabled={!extraLinePart}
                  onClick={() => extraLinePart && addExtraLine(extraLinePart)}
                >
                  Ajouter
                </Button>
              </Stack>

              <Stack direction="row" justifyContent="flex-end" spacing={3} pr={1}>
                <Typography variant="body2">Total HT: <strong>{totalHtEur.toFixed(2)} €</strong></Typography>
                <Typography variant="body2">Total TTC: <strong>{totalTtcEur.toFixed(2)} €</strong></Typography>
              </Stack>
            </>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>Annuler</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={saving}>
          {saving ? <CircularProgress size={18} /> : 'Créer'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// OverrideDialog
// ---------------------------------------------------------------------------

interface OverrideDialogProps {
  open: boolean
  si: SupplierInvoice | null
  onClose: () => void
  onDone: (si: SupplierInvoice) => void
}

function OverrideDialog({ open, si, onClose, onDone }: OverrideDialogProps) {
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) { setReason(''); setError('') }
  }, [open])

  const handleSubmit = async () => {
    if (!si) return
    setError('')
    if (!reason.trim()) { setError('Motif obligatoire'); return }
    setSaving(true)
    try {
      const updated = await supplierInvoiceApi.override(si.id, {
        version: si.version,
        reason: reason.trim(),
      })
      onDone(updated)
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Erreur')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Accepter l'écart avec motif</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}
          <Alert severity="warning">
            Cette facture présente des écarts (quantité ou prix). Veuillez documenter la raison
            d'acceptation. Cette action sera enregistrée dans le journal d'audit.
          </Alert>
          <TextField
            label="Motif de l'acceptation de l'écart"
            multiline
            rows={3}
            fullWidth
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Expliquez pourquoi l'écart est acceptable..."
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>Annuler</Button>
        <Button
          variant="contained"
          color="warning"
          onClick={handleSubmit}
          disabled={saving || !reason.trim()}
          startIcon={<GavelIcon />}
        >
          {saving ? <CircularProgress size={18} /> : 'Accepter l\'écart'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// AccountingExportDialog
// ---------------------------------------------------------------------------

interface AccountingExportDialogProps {
  open: boolean
  si: SupplierInvoice | null
  onClose: () => void
}

function AccountingExportDialog({ open, si, onClose }: AccountingExportDialogProps) {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !si) return
    setLoading(true)
    setError('')
    supplierInvoiceApi
      .accountingExport(si.id)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail ?? 'Erreur'))
      .finally(() => setLoading(false))
  }, [open, si])

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Export comptable — Journal des achats</DialogTitle>
      <DialogContent>
        {loading && <CircularProgress />}
        {error && <Alert severity="error">{error}</Alert>}
        {data && (
          <Stack spacing={2} mt={1}>
            <Stack direction="row" spacing={4}>
              <Box>
                <Typography variant="caption" color="text.secondary">N° facture</Typography>
                <Typography>{data.invoice_number}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Date</Typography>
                <Typography>{data.date ?? '—'}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Échéance</Typography>
                <Typography>{data.due_date ?? '—'}</Typography>
              </Box>
            </Stack>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Compte</TableCell>
                  <TableCell>Libellé</TableCell>
                  <TableCell align="right">Débit</TableCell>
                  <TableCell align="right">Crédit</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.entries.map((e: any, i: number) => (
                  <TableRow key={i}>
                    <TableCell>{e.account}</TableCell>
                    <TableCell>{e.label}</TableCell>
                    <TableCell align="right">{e.debit > 0 ? fmt(e.debit) : '—'}</TableCell>
                    <TableCell align="right">{e.credit > 0 ? fmt(e.credit) : '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Stack direction="row" justifyContent="flex-end" spacing={3}>
              <Typography variant="body2">Total HT: <strong>{fmt(data.total_ht)}</strong></Typography>
              <Typography variant="body2">Total TTC: <strong>{fmt(data.total_ttc)}</strong></Typography>
            </Stack>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Fermer</Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// SIDetail — full detail view with match report
// ---------------------------------------------------------------------------

interface SIDetailProps {
  si: SupplierInvoice
  onBack: () => void
  onUpdated: (si: SupplierInvoice) => void
}

function SIDetail({ si, onBack, onUpdated }: SIDetailProps) {
  const { success: toastSuccess, error: toastError } = useToast()
  const [acting, setActing] = useState(false)
  const [overrideOpen, setOverrideOpen] = useState(false)
  const [accountingOpen, setAccountingOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)

  const showSnack = (message: string, severity: 'success' | 'error' = 'success') => {
    if (severity === 'success') toastSuccess(message)
    else toastError(message)
  }

  const doAction = async (fn: () => Promise<SupplierInvoice>, successMsg: string) => {
    setActing(true)
    try {
      const updated = await fn()
      onUpdated(updated)
      showSnack(successMsg)
    } catch (e: any) {
      showSnack(e?.response?.data?.detail ?? 'Erreur', 'error')
    } finally {
      setActing(false)
    }
  }

  const handlePost = () =>
    doAction(
      () => supplierInvoiceApi.post(si.id, { version: si.version }),
      'Rapprochement 3 voies effectué',
    )

  const handleApprove = () =>
    doAction(
      () => supplierInvoiceApi.approve(si.id, { version: si.version }),
      'Facture approuvée',
    )

  const handleMarkPaid = () =>
    doAction(
      () => supplierInvoiceApi.markPaid(si.id, { version: si.version }),
      'Facture marquée payée',
    )

  const handleCancel = () =>
    doAction(
      () => supplierInvoiceApi.cancel(si.id, { version: si.version }),
      'Facture annulée',
    )

  const handleDownloadPdf = async () => {
    setPdfLoading(true)
    try {
      const url = await supplierInvoiceApi.getPdf(si.id)
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      showSnack('Impossible de générer le PDF.', 'error')
    } finally {
      setPdfLoading(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('category', 'supplier_invoice')
      form.append('owner_entity_type', 'supplier_invoice')
      form.append('owner_entity_id', si.id)
      await apiClient.post('/documents', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      showSnack('PDF joint avec succès')
    } catch (e: any) {
      showSnack(e?.response?.data?.detail ?? 'Erreur lors du chargement', 'error')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const hasUnresolvedDiscrepancy = si.has_discrepancy && !si.override_reason

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={2} mb={3}>
        <IconButton onClick={onBack}><ArrowBackIcon /></IconButton>
        <Typography variant="h5" fontWeight={700}>
          Facture fournisseur — {si.number}
        </Typography>
        <StatusChip status={si.status} label={STATUS_LABELS[si.status]} />
        {si.has_discrepancy && (
          <Chip
            label={si.override_reason ? 'Écart accepté' : 'Écarts détectés'}
            color={si.override_reason ? 'warning' : 'error'}
            icon={si.override_reason ? <GavelIcon /> : <ErrorIcon />}
          />
        )}
      </Stack>

      {/* Info row */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction="row" spacing={4} flexWrap="wrap">
          <Box>
            <Typography variant="caption" color="text.secondary">Réception</Typography>
            <Typography>{si.received_at ? new Date(si.received_at).toLocaleDateString('fr-FR') : '—'}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Échéance</Typography>
            <Typography>{si.due_date ?? '—'}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Total HT</Typography>
            <Typography>{fmt(si.total_ht)}</Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Total TTC</Typography>
            <Typography fontWeight={700}>{fmt(si.total_ttc)}</Typography>
          </Box>
          {si.notes && (
            <Box>
              <Typography variant="caption" color="text.secondary">Notes</Typography>
              <Typography>{si.notes}</Typography>
            </Box>
          )}
        </Stack>
      </Paper>

      {/* Override reason banner */}
      {si.override_reason && (
        <Alert severity="warning" icon={<GavelIcon />} sx={{ mb: 2 }}>
          <strong>Motif d'acceptation de l'écart :</strong> {si.override_reason}
        </Alert>
      )}

      {/* Match report — lines table */}
      <Paper sx={{ mb: 2 }}>
        <Box p={2}>
          <Typography variant="subtitle1" fontWeight={600} mb={1}>
            Rapport de rapprochement (3 voies)
          </Typography>
        </Box>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Description</TableCell>
              <TableCell align="right">Qté BC</TableCell>
              <TableCell align="right">Qté reçue</TableCell>
              <TableCell align="right">Qté facturée</TableCell>
              <TableCell align="right">PU BC (HT)</TableCell>
              <TableCell align="right">PU Facture (HT)</TableCell>
              <TableCell align="right">TVA</TableCell>
              <TableCell align="right">Total TTC</TableCell>
              <TableCell align="center">Statut</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {si.lines.map((ln: SILine, i) => (
              <TableRow
                key={i}
                sx={{
                  bgcolor:
                    ln.match_status === 'ok'
                      ? 'success.50'
                      : ln.match_status === 'price_mismatch'
                      ? 'warning.50'
                      : 'error.50',
                }}
              >
                <TableCell>{ln.description || '—'}</TableCell>
                <TableCell align="right">{ln.po_quantity_ordered}</TableCell>
                <TableCell align="right">{ln.po_quantity_received}</TableCell>
                <TableCell
                  align="right"
                  sx={
                    ln.match_status === 'qty_mismatch'
                      ? { color: 'error.main', fontWeight: 700 }
                      : {}
                  }
                >
                  {ln.quantity}
                </TableCell>
                <TableCell align="right">{fmt(ln.po_unit_price_ht)}</TableCell>
                <TableCell
                  align="right"
                  sx={
                    ln.match_status === 'price_mismatch'
                      ? { color: 'warning.main', fontWeight: 700 }
                      : {}
                  }
                >
                  {fmt(ln.unit_price_ht)}
                </TableCell>
                <TableCell align="right">{ln.vat_rate}%</TableCell>
                <TableCell align="right">{fmt(ln.line_total_ttc)}</TableCell>
                <TableCell align="center">
                  <Tooltip title={MATCH_STATUS_LABELS[ln.match_status]}>
                    <Chip
                      size="small"
                      label={MATCH_STATUS_LABELS[ln.match_status]}
                      color={MATCH_COLORS[ln.match_status]}
                      icon={MATCH_ICONS[ln.match_status]}
                    />
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>

      {/* Actions */}
      <Stack direction="row" spacing={1} flexWrap="wrap">
        <Button
          variant="outlined"
          startIcon={<PictureAsPdfIcon />}
          onClick={handleDownloadPdf}
          disabled={pdfLoading}
        >
          {pdfLoading ? <CircularProgress size={18} /> : 'Générer PDF'}
        </Button>
        {si.status === 'draft' && (
          <Button
            variant="contained"
            startIcon={<CheckCircleIcon />}
            onClick={handlePost}
            disabled={acting}
          >
            Enregistrer & Rapprocher
          </Button>
        )}
        {si.status === 'posted' && hasUnresolvedDiscrepancy && (
          <Button
            variant="outlined"
            color="warning"
            startIcon={<GavelIcon />}
            onClick={() => setOverrideOpen(true)}
            disabled={acting}
          >
            Accepter l'écart
          </Button>
        )}
        {si.status === 'posted' && !hasUnresolvedDiscrepancy && (
          <Button
            variant="contained"
            color="success"
            startIcon={<ThumbUpAltIcon />}
            onClick={handleApprove}
            disabled={acting}
          >
            Approuver
          </Button>
        )}
        {si.status === 'approved' && (
          <Button
            variant="contained"
            color="primary"
            startIcon={<PaymentsIcon />}
            onClick={handleMarkPaid}
            disabled={acting}
          >
            Marquer payé
          </Button>
        )}
        {['approved', 'paid'].includes(si.status) && (
          <Button
            variant="outlined"
            startIcon={<AccountBalanceIcon />}
            onClick={() => setAccountingOpen(true)}
          >
            Export comptable
          </Button>
        )}
        {['draft', 'posted'].includes(si.status) && (
          <Button
            variant="outlined"
            color="error"
            startIcon={<CancelIcon />}
            onClick={handleCancel}
            disabled={acting}
          >
            Annuler
          </Button>
        )}
        {/* PDF attachment */}
        <Button
          variant="outlined"
          startIcon={<AttachFileIcon />}
          component="label"
          disabled={uploading}
        >
          {uploading ? <CircularProgress size={18} /> : 'Joindre PDF'}
          <input type="file" hidden accept="application/pdf" onChange={handleFileUpload} />
        </Button>
      </Stack>

      <OverrideDialog
        open={overrideOpen}
        si={si}
        onClose={() => setOverrideOpen(false)}
        onDone={(updated) => {
          setOverrideOpen(false)
          onUpdated(updated)
          showSnack('Écart accepté — entrée d\'audit enregistrée')
        }}
      />

      <AccountingExportDialog
        open={accountingOpen}
        si={si}
        onClose={() => setAccountingOpen(false)}
      />

    </Box>
  )
}

// ---------------------------------------------------------------------------
// SupplierInvoicePage — list view
// ---------------------------------------------------------------------------

export function SupplierInvoicePage() {
  const { success: toastSuccess, error: toastError } = useToast()
  const qc = useQueryClient()
  const [page, setPage] = useState(0)
  const [statusFilter, setStatusFilter] = useState<SIStatus | ''>('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<SupplierInvoice | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [exportMenuAnchor, setExportMenuAnchor] = useState<null | HTMLElement>(null)
  const [exporting, setExporting] = useState(false)

  const handleExportCsv = async () => {
    setExportMenuAnchor(null)
    setExporting(true)
    try {
      await supplierInvoiceApi.exportCsv()
      toastSuccess('Export CSV téléchargé.')
    } catch {
      toastError('Erreur lors de l\'export.')
    } finally {
      setExporting(false)
    }
  }

  const handleExportPdf = async () => {
    setExportMenuAnchor(null)
    setExporting(true)
    try {
      const url = await supplierInvoiceApi.exportPdf()
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      toastError('Erreur lors de l\'export.')
    } finally {
      setExporting(false)
    }
  }

  const { data, isLoading, isError } = useQuery({
    queryKey: ['supplier-invoices', statusFilter, search, page],
    queryFn: () => supplierInvoiceApi.list({
      status: statusFilter || undefined,
      search: search || undefined,
      page: page + 1,
      page_size: 20,
    }),
    placeholderData: (prev) => prev,
  })

  const invoices = data?.items ?? []
  const total = data?.total ?? 0

  if (selected) {
    return (
      <Box>
        <SIDetail
          si={selected}
          onBack={() => {
            setSelected(null)
            qc.invalidateQueries({ queryKey: ['supplier-invoices'] })
          }}
          onUpdated={(si) => setSelected(si)}
        />
      </Box>
    )
  }

  return (
    <Box>
      <PageHeader
        title="Factures fournisseurs"
        subtitle={`${total} facture${total !== 1 ? 's' : ''} · Rapprochement 3 voies`}
        actions={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={exporting ? <CircularProgress size={18} /> : <AccountBalanceIcon />}
              endIcon={<ArrowDropDownIcon />}
              onClick={(e) => setExportMenuAnchor(e.currentTarget)}
              disabled={exporting}
            >
              Export comptable (payées)
            </Button>
            <Menu
              anchorEl={exportMenuAnchor}
              open={Boolean(exportMenuAnchor)}
              onClose={() => setExportMenuAnchor(null)}
            >
              <MenuItem onClick={handleExportCsv}>
                <ListItemIcon><TableChartIcon fontSize="small" /></ListItemIcon>
                Télécharger CSV
              </MenuItem>
              <MenuItem onClick={handleExportPdf}>
                <ListItemIcon><PictureAsPdfIcon fontSize="small" /></ListItemIcon>
                Télécharger PDF
              </MenuItem>
            </Menu>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
              Nouvelle facture
            </Button>
          </Stack>
        }
      />

      <Stack direction="row" spacing={2} mb={2}>
        <TextField
          label="Rechercher (N° facture)"
          size="small"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0) }}
          sx={{ minWidth: 220 }}
        />
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Statut</InputLabel>
          <Select
            value={statusFilter}
            label="Statut"
            onChange={(e) => { setStatusFilter(e.target.value as SIStatus | ''); setPage(0) }}
          >
            <MenuItem value="">Tous</MenuItem>
            {(Object.keys(STATUS_LABELS) as SIStatus[]).map((s) => (
              <MenuItem key={s} value={s}>{STATUS_LABELS[s]}</MenuItem>
            ))}
          </Select>
        </FormControl>
      </Stack>

      <DataTable
        columns={[
          {
            id: 'number',
            label: 'N° Facture',
            render: si => (
              <Typography variant="body2" fontWeight={700} fontFamily="monospace">{si.number}</Typography>
            ),
          },
          {
            id: 'status',
            label: 'Statut',
            width: 130,
            render: si => <StatusChip status={si.status} label={STATUS_LABELS[si.status]} />,
          },
          {
            id: 'discrepancy',
            label: 'Rapprochement',
            width: 140,
            render: si => si.status === 'draft' ? (
              <Typography variant="caption" color="text.secondary">—</Typography>
            ) : si.has_discrepancy ? (
              <Chip
                size="small"
                label={si.override_reason ? 'Accepté' : 'Écarts'}
                color={si.override_reason ? 'warning' : 'error'}
                icon={si.override_reason ? <GavelIcon /> : <ErrorIcon />}
              />
            ) : (
              <Chip size="small" label="OK" color="success" icon={<CheckCircleIcon />} />
            ),
          },
          {
            id: 'total_ht',
            label: 'Total HT',
            align: 'right',
            width: 120,
            render: si => <Typography variant="body2">{fmt(si.total_ht)}</Typography>,
          },
          {
            id: 'total_ttc',
            label: 'Total TTC',
            align: 'right',
            width: 120,
            render: si => <Typography variant="body2" fontWeight={600}>{fmt(si.total_ttc)}</Typography>,
          },
          {
            id: 'received_at',
            label: 'Réception',
            width: 110,
            render: si => (
              <Typography variant="caption" color="text.secondary">
                {si.received_at ? new Date(si.received_at).toLocaleDateString('fr-FR') : '—'}
              </Typography>
            ),
          },
          {
            id: 'due_date',
            label: 'Échéance',
            width: 110,
            render: si => (
              <Typography variant="caption" color="text.secondary">{si.due_date ?? '—'}</Typography>
            ),
          },
        ]}
        rows={invoices}
        getRowKey={si => si.id}
        onRowClick={si => setSelected(si)}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger les factures fournisseurs."
        total={total}
        page={page}
        pageSize={20}
        onPageChange={setPage}
        emptyTitle="Aucune facture fournisseur"
        emptyDescription="Créez votre première facture fournisseur pour commencer."
      />

      <CreateDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(si) => {
          setCreateOpen(false)
          setSelected(si)
          toastSuccess('Facture fournisseur créée.')
        }}
      />
    </Box>
  )
}
