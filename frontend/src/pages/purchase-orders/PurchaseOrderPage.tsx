import { useState, useEffect, useCallback } from 'react'
import {
  Alert,
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
  MenuItem,
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
  Paper,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import SendIcon from '@mui/icons-material/Send'
import MoveToInboxIcon from '@mui/icons-material/MoveToInbox'
import CancelIcon from '@mui/icons-material/Cancel'
import VisibilityIcon from '@mui/icons-material/Visibility'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import ReceiptIcon from '@mui/icons-material/Receipt'
import { Link as RouterLink } from 'react-router-dom'

import {
  purchaseOrderApi,
  PurchaseOrder,
  POLine,
  POStatus,
  POCreatePayload,
  POLineInput,
  STATUS_LABELS,
  MATCH_FLAG_LABELS,
  POMatchFlag,
} from '../../lib/purchaseOrderApi'
import { supplierApi, Supplier } from '../../lib/supplierApi'
import { partsApi } from '../../lib/partsApi'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<POStatus, 'default' | 'info' | 'warning' | 'success' | 'error'> = {
  draft: 'default',
  sent: 'info',
  partially_received: 'warning',
  completed: 'success',
  cancelled: 'error',
}

const MATCH_COLORS: Record<POMatchFlag, 'success' | 'warning' | 'error'> = {
  ok: 'success',
  qty_mismatch: 'warning',
  inv_mismatch: 'error',
}

function formatMoney(minor: number) {
  return (minor / 100).toFixed(2) + ' MAD'
}

// ---------------------------------------------------------------------------
// CreateDialog
// ---------------------------------------------------------------------------

interface CreateDialogProps {
  open: boolean
  onClose: () => void
  onCreated: (po: PurchaseOrder) => void
}

interface LineForm {
  part_public_id: string
  part_name: string
  quantity_ordered: number
  unit_price_ht: number
}

function CreateDialog({ open, onClose, onCreated }: CreateDialogProps) {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [parts, setParts] = useState<{ id: string; name: string; sku_code: string }[]>([])
  const [supplierPublicId, setSupplierPublicId] = useState('')
  const [expectedDate, setExpectedDate] = useState('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<LineForm[]>([
    { part_public_id: '', part_name: '', quantity_ordered: 1, unit_price_ht: 0 },
  ])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    supplierApi.list({ status: 'active', page_size: 100 }).then((r) => setSuppliers(r.items))
    partsApi.list({ page_size: 200 }).then((r) => setParts(r.items))
  }, [open])

  const handleAddLine = () =>
    setLines((l) => [...l, { part_public_id: '', part_name: '', quantity_ordered: 1, unit_price_ht: 0 }])

  const handleRemoveLine = (i: number) =>
    setLines((l) => l.filter((_, idx) => idx !== i))

  const updateLine = (i: number, field: keyof LineForm, value: string | number) =>
    setLines((l) => l.map((ln, idx) => (idx === i ? { ...ln, [field]: value } : ln)))

  const totalHt = lines.reduce((s, l) => s + l.quantity_ordered * l.unit_price_ht, 0)

  const handleSubmit = async () => {
    setError('')
    if (!supplierPublicId) { setError('Veuillez sélectionner un fournisseur'); return }
    if (lines.some((l) => !l.part_public_id)) { setError('Toutes les lignes doivent avoir une pièce'); return }

    setSaving(true)
    try {
      const payload: POCreatePayload = {
        supplier_public_id: supplierPublicId,
        expected_delivery_date: expectedDate || undefined,
        notes: notes || undefined,
        lines: lines.map((l) => ({
          part_public_id: l.part_public_id,
          quantity_ordered: l.quantity_ordered,
          unit_price_ht: l.unit_price_ht,
        })),
      }
      const po = await purchaseOrderApi.create(payload)
      onCreated(po)
      setSupplierPublicId('')
      setExpectedDate('')
      setNotes('')
      setLines([{ part_public_id: '', part_name: '', quantity_ordered: 1, unit_price_ht: 0 }])
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Erreur lors de la création')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Nouveau bon de commande</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}

          <FormControl fullWidth>
            <InputLabel>Fournisseur *</InputLabel>
            <Select
              value={supplierPublicId}
              label="Fournisseur *"
              onChange={(e) => setSupplierPublicId(e.target.value)}
            >
              {suppliers.map((s) => (
                <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            label="Date de livraison prévue"
            type="date"
            value={expectedDate}
            onChange={(e) => setExpectedDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />

          <TextField
            label="Notes"
            multiline
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />

          <Typography variant="subtitle2" fontWeight={600}>Lignes</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Pièce</TableCell>
                <TableCell width={100}>Qté</TableCell>
                <TableCell width={130}>Prix HT (centimes)</TableCell>
                <TableCell width={40} />
              </TableRow>
            </TableHead>
            <TableBody>
              {lines.map((ln, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Select
                      size="small"
                      fullWidth
                      value={ln.part_public_id}
                      onChange={(e) => updateLine(i, 'part_public_id', e.target.value)}
                      displayEmpty
                    >
                      <MenuItem value="" disabled>Sélectionner…</MenuItem>
                      {parts.map((p) => (
                        <MenuItem key={p.id} value={p.id}>{p.name} ({p.sku_code})</MenuItem>
                      ))}
                    </Select>
                  </TableCell>
                  <TableCell>
                    <TextField
                      size="small"
                      type="number"
                      value={ln.quantity_ordered}
                      onChange={(e) => updateLine(i, 'quantity_ordered', parseInt(e.target.value) || 1)}
                      inputProps={{ min: 1 }}
                    />
                  </TableCell>
                  <TableCell>
                    <TextField
                      size="small"
                      type="number"
                      value={ln.unit_price_ht}
                      onChange={(e) => updateLine(i, 'unit_price_ht', parseInt(e.target.value) || 0)}
                      inputProps={{ min: 0 }}
                    />
                  </TableCell>
                  <TableCell>
                    {lines.length > 1 && (
                      <IconButton size="small" onClick={() => handleRemoveLine(i)}>
                        <CancelIcon fontSize="small" />
                      </IconButton>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Box>
            <Button size="small" startIcon={<AddIcon />} onClick={handleAddLine}>
              Ajouter une ligne
            </Button>
          </Box>

          <Typography variant="body2" fontWeight={600}>
            Total HT : {formatMoney(totalHt)}
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={saving}>
          {saving ? <CircularProgress size={20} /> : 'Créer'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// ReceptionDialog
// ---------------------------------------------------------------------------

interface ReceptionDialogProps {
  open: boolean
  po: PurchaseOrder | null
  onClose: () => void
  onReceived: (po: PurchaseOrder) => void
}

function ReceptionDialog({ open, po, onClose, onReceived }: ReceptionDialogProps) {
  const [qtys, setQtys] = useState<Record<number, number>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (po) {
      const init: Record<number, number> = {}
      po.lines.forEach((l) => { init[l.id] = l.quantity_ordered - l.quantity_received })
      setQtys(init)
    }
  }, [po])

  if (!po) return null

  const handleSubmit = async () => {
    setError('')
    const lines = Object.entries(qtys)
      .filter(([, q]) => q > 0)
      .map(([id, q]) => ({ line_id: parseInt(id), quantity_received: q }))

    if (!lines.length) { setError('Aucune quantité à recevoir'); return }

    setSaving(true)
    try {
      const updated = await purchaseOrderApi.receive(po.id, { version: po.version, lines })
      onReceived(updated)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Erreur lors de la réception')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Réception — {po.doc_number}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Pièce ID</TableCell>
                <TableCell>Commandé</TableCell>
                <TableCell>Déjà reçu</TableCell>
                <TableCell>À réceptionner</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {po.lines.map((l) => {
                const remaining = l.quantity_ordered - l.quantity_received
                return (
                  <TableRow key={l.id}>
                    <TableCell>#{l.part_id}</TableCell>
                    <TableCell>{l.quantity_ordered}</TableCell>
                    <TableCell>{l.quantity_received}</TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        type="number"
                        value={qtys[l.id] ?? remaining}
                        onChange={(e) =>
                          setQtys((q) => ({ ...q, [l.id]: Math.max(0, parseInt(e.target.value) || 0) }))
                        }
                        inputProps={{ min: 0, max: remaining }}
                        disabled={remaining <= 0}
                        sx={{ width: 80 }}
                      />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={saving}>
          {saving ? <CircularProgress size={20} /> : 'Valider la réception'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// InvoiceDialog
// ---------------------------------------------------------------------------

interface InvoiceDialogProps {
  open: boolean
  po: PurchaseOrder | null
  onClose: () => void
  onSaved: (po: PurchaseOrder) => void
}

function InvoiceDialog({ open, po, onClose, onSaved }: InvoiceDialogProps) {
  const [qtys, setQtys] = useState<Record<number, number>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (po) {
      const init: Record<number, number> = {}
      po.lines.forEach((l) => { init[l.id] = l.quantity_invoiced })
      setQtys(init)
    }
  }, [po])

  if (!po) return null

  const handleSubmit = async () => {
    setError('')
    setSaving(true)
    try {
      let updated = po
      for (const line of po.lines) {
        const q = qtys[line.id] ?? line.quantity_invoiced
        if (q !== line.quantity_invoiced) {
          await purchaseOrderApi.updateInvoicedQty(po.id, line.id, q)
        }
      }
      updated = await purchaseOrderApi.get(po.id)
      onSaved(updated)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Erreur')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Facturé — {po.doc_number}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Pièce</TableCell>
                <TableCell>Reçu</TableCell>
                <TableCell>Facturé</TableCell>
                <TableCell>Statut</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {po.lines.map((l) => (
                <TableRow key={l.id}>
                  <TableCell>#{l.part_id}</TableCell>
                  <TableCell>{l.quantity_received}</TableCell>
                  <TableCell>
                    <TextField
                      size="small"
                      type="number"
                      value={qtys[l.id] ?? l.quantity_invoiced}
                      onChange={(e) =>
                        setQtys((q) => ({ ...q, [l.id]: Math.max(0, parseInt(e.target.value) || 0) }))
                      }
                      inputProps={{ min: 0 }}
                      sx={{ width: 80 }}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={MATCH_FLAG_LABELS[l.match_flag]}
                      color={MATCH_COLORS[l.match_flag]}
                      size="small"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={saving}>
          {saving ? <CircularProgress size={20} /> : 'Enregistrer'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// PODetail
// ---------------------------------------------------------------------------

interface PODetailProps {
  po: PurchaseOrder
  onBack: () => void
  onUpdated: (po: PurchaseOrder) => void
}

function PODetail({ po, onBack, onUpdated }: PODetailProps) {
  const [receiveOpen, setReceiveOpen] = useState(false)
  const [invoiceOpen, setInvoiceOpen] = useState(false)
  const [actioning, setActioning] = useState(false)
  const [error, setError] = useState('')

  const canSend = po.status === 'draft'
  const canReceive = po.status === 'sent' || po.status === 'partially_received'
  const canCancel = po.status !== 'completed' && po.status !== 'cancelled'

  const handleSend = async () => {
    setActioning(true); setError('')
    try {
      const updated = await purchaseOrderApi.send(po.id, po.version)
      onUpdated(updated)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Erreur')
    } finally { setActioning(false) }
  }

  const handleCancel = async () => {
    if (!window.confirm('Confirmer l\'annulation ?')) return
    setActioning(true); setError('')
    try {
      const updated = await purchaseOrderApi.cancel(po.id, po.version)
      onUpdated(updated)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Erreur')
    } finally { setActioning(false) }
  }

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} mb={2}>
        <IconButton onClick={onBack}><ArrowBackIcon /></IconButton>
        <Typography variant="h6">{po.doc_number ?? 'BC sans numéro'}</Typography>
        <Chip label={STATUS_LABELS[po.status]} color={STATUS_COLORS[po.status]} size="small" />
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Stack direction="row" spacing={1} mb={3}>
        {canSend && (
          <Button variant="outlined" startIcon={<SendIcon />} onClick={handleSend} disabled={actioning}>
            Envoyer au fournisseur
          </Button>
        )}
        {canReceive && (
          <Button variant="outlined" startIcon={<MoveToInboxIcon />} onClick={() => setReceiveOpen(true)}>
            Réceptionner
          </Button>
        )}
        {(po.status === 'partially_received' || po.status === 'completed') && (
          <Button variant="outlined" startIcon={<ReceiptIcon />} onClick={() => setInvoiceOpen(true)}>
            Contrôle facture
          </Button>
        )}
        {canCancel && (
          <Button variant="outlined" color="error" startIcon={<CancelIcon />} onClick={handleCancel} disabled={actioning}>
            Annuler
          </Button>
        )}
      </Stack>

      <Stack direction="row" spacing={4} mb={3}>
        <Box>
          <Typography variant="caption" color="text.secondary">Fournisseur</Typography>
          <Typography>ID {po.supplier_id}</Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Livraison prévue</Typography>
          <Typography>{po.expected_delivery_date ?? '—'}</Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Total HT</Typography>
          <Typography fontWeight={700}>{formatMoney(po.total_ht)}</Typography>
        </Box>
      </Stack>

      {po.notes && (
        <Typography variant="body2" color="text.secondary" mb={2}>{po.notes}</Typography>
      )}

      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Pièce</TableCell>
            <TableCell align="right">Commandé</TableCell>
            <TableCell align="right">Prix HT</TableCell>
            <TableCell align="right">Reçu</TableCell>
            <TableCell align="right">Facturé</TableCell>
            <TableCell>Match</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {po.lines.map((l) => (
            <TableRow key={l.id}>
              <TableCell>Pièce #{l.part_id}</TableCell>
              <TableCell align="right">{l.quantity_ordered}</TableCell>
              <TableCell align="right">{formatMoney(l.unit_price_ht)}</TableCell>
              <TableCell align="right">{l.quantity_received}</TableCell>
              <TableCell align="right">{l.quantity_invoiced}</TableCell>
              <TableCell>
                <Chip
                  label={MATCH_FLAG_LABELS[l.match_flag]}
                  color={MATCH_COLORS[l.match_flag]}
                  size="small"
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <ReceptionDialog
        open={receiveOpen}
        po={po}
        onClose={() => setReceiveOpen(false)}
        onReceived={(updated) => { onUpdated(updated); setReceiveOpen(false) }}
      />
      <InvoiceDialog
        open={invoiceOpen}
        po={po}
        onClose={() => setInvoiceOpen(false)}
        onSaved={(updated) => { onUpdated(updated); setInvoiceOpen(false) }}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function PurchaseOrderPage() {
  const [pos, setPos] = useState<PurchaseOrder[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<POStatus | ''>('')
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedPO, setSelectedPO] = useState<PurchaseOrder | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await purchaseOrderApi.list({
        status: statusFilter || undefined,
        page,
        page_size: 20,
      })
      setPos(r.items)
      setTotal(r.total)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, page])

  useEffect(() => { load() }, [load])

  if (selectedPO) {
    return (
      <Box p={4}>
        <PODetail
          po={selectedPO}
          onBack={() => { setSelectedPO(null); load() }}
          onUpdated={(updated) => setSelectedPO(updated)}
        />
      </Box>
    )
  }

  return (
    <Box p={4}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>Bons de commande</Typography>
          <Typography variant="body2" color="text.secondary">{total} bon(s) au total</Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button component={RouterLink} to="/" variant="text">← Tableau de bord</Button>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
            Nouveau BC
          </Button>
        </Stack>
      </Stack>

      <Stack direction="row" spacing={2} mb={2} alignItems="center">
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>Statut</InputLabel>
          <Select
            value={statusFilter}
            label="Statut"
            onChange={(e) => { setStatusFilter(e.target.value as POStatus | ''); setPage(1) }}
          >
            <MenuItem value="">Tous</MenuItem>
            {(Object.keys(STATUS_LABELS) as POStatus[]).map((s) => (
              <MenuItem key={s} value={s}>{STATUS_LABELS[s]}</MenuItem>
            ))}
          </Select>
        </FormControl>
      </Stack>

      {loading ? (
        <CircularProgress />
      ) : (
        <Paper variant="outlined">
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>N° document</TableCell>
                <TableCell>Statut</TableCell>
                <TableCell>Fournisseur</TableCell>
                <TableCell>Livraison prévue</TableCell>
                <TableCell align="right">Total HT</TableCell>
                <TableCell>Lignes</TableCell>
                <TableCell>Match</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {pos.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                    Aucun bon de commande
                  </TableCell>
                </TableRow>
              )}
              {pos.map((po) => {
                const hasMismatch = po.lines.some((l) => l.match_flag !== 'ok')
                return (
                  <TableRow key={po.id} hover>
                    <TableCell>{po.doc_number ?? '—'}</TableCell>
                    <TableCell>
                      <Chip label={STATUS_LABELS[po.status]} color={STATUS_COLORS[po.status]} size="small" />
                    </TableCell>
                    <TableCell>ID {po.supplier_id}</TableCell>
                    <TableCell>{po.expected_delivery_date ?? '—'}</TableCell>
                    <TableCell align="right">{formatMoney(po.total_ht)}</TableCell>
                    <TableCell>{po.lines.length}</TableCell>
                    <TableCell>
                      {hasMismatch ? (
                        <Chip label="Écart" color="warning" size="small" />
                      ) : (
                        <Chip label="OK" color="success" size="small" />
                      )}
                    </TableCell>
                    <TableCell>
                      <Tooltip title="Voir détail">
                        <IconButton size="small" onClick={() => setSelectedPO(po)}>
                          <VisibilityIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </Paper>
      )}

      <CreateDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(po) => { setCreateOpen(false); setSelectedPO(po); load() }}
      />
    </Box>
  )
}
