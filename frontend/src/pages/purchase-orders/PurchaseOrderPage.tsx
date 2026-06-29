import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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
  Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import SendIcon from '@mui/icons-material/Send'
import MoveToInboxIcon from '@mui/icons-material/MoveToInbox'
import CancelIcon from '@mui/icons-material/Cancel'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import ReceiptIcon from '@mui/icons-material/Receipt'
import {
  purchaseOrderApi,
  PurchaseOrder,
  POStatus,
  STATUS_LABELS,
  MATCH_FLAG_LABELS,
  POMatchFlag,
} from '../../lib/purchaseOrderApi'
import { supplierInvoiceApi } from '../../lib/supplierInvoiceApi'
import { PurchaseOrderCreateDialog } from '../../components/purchase-order/PurchaseOrderCreateDialog'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { DataTable } from '../../components/ui/DataTable'
import { useToast } from '../../contexts/ToastContext'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------


const MATCH_COLORS: Record<POMatchFlag, 'success' | 'warning' | 'error'> = {
  ok: 'success',
  qty_mismatch: 'warning',
  inv_mismatch: 'error',
}

function formatMoney(minor: number) {
  return (minor / 100).toFixed(2) + ' €'
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
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Erreur lors de la réception')
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
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Erreur')
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
// CreateSupplierInvoiceDialog
// ---------------------------------------------------------------------------

interface CreateSIDialogProps {
  open: boolean
  po: PurchaseOrder | null
  onClose: () => void
  onCreated: () => void
}

interface SILineForm {
  po_line_id: number
  part_name: string
  quantity: number
  unit_price_ht: number
}

function CreateSupplierInvoiceDialog({ open, po, onClose, onCreated }: CreateSIDialogProps) {
  const { success } = useToast()
  const [dueDate, setDueDate] = useState('')
  const [notes, setNotes] = useState('')
  const [linesForms, setLinesForms] = useState<SILineForm[]>([])
  const [formError, setFormError] = useState('')

  useEffect(() => {
    if (po && open) {
      setDueDate('')
      setNotes('')
      setFormError('')
      setLinesForms(
        po.lines
          .filter((l) => l.quantity_received > 0)
          .map((l) => ({
            po_line_id: l.id,
            part_name: l.part_name ?? `Pièce #${l.part_id}`,
            quantity: l.quantity_received,
            unit_price_ht: l.unit_price_ht,
          }))
      )
    }
  }, [po, open])

  const createMutation = useMutation({
    mutationFn: () => {
      if (!po?.supplier_public_id) throw new Error('Supplier ID missing')
      return supplierInvoiceApi.create({
        supplier_public_id: po.supplier_public_id!,
        po_public_id: po.id,
        due_date: dueDate || null,
        notes: notes.trim() || null,
        lines: linesForms.map((l) => ({
          po_line_id: l.po_line_id,
          quantity: l.quantity,
          unit_price_ht: l.unit_price_ht,
        })),
      })
    },
    onSuccess: () => {
      success('Facture fournisseur créée.')
      onCreated()
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setFormError(typeof detail === 'string' ? detail : 'Erreur lors de la création.')
    },
  })

  function handleSubmit() {
    setFormError('')
    if (linesForms.length === 0) { setFormError('Aucune ligne à facturer (quantités reçues nulles).'); return }
    createMutation.mutate()
  }

  if (!po) return null

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Créer facture fournisseur — {po.doc_number}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {formError && <Alert severity="error">{formError}</Alert>}
          <Stack direction="row" spacing={2}>
            <TextField
              label="Date d'échéance"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              type="date"
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
          </Stack>
          <TextField
            label="Notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            multiline
            rows={2}
            fullWidth
          />
          <Typography variant="subtitle2">Lignes facturées</Typography>
          {linesForms.length === 0 ? (
            <Alert severity="warning">Aucune pièce reçue sur ce bon de commande.</Alert>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Pièce</TableCell>
                  <TableCell align="right">Quantité</TableCell>
                  <TableCell align="right">Prix unit. HT</TableCell>
                  <TableCell align="right">Total HT</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {linesForms.map((l, idx) => (
                  <TableRow key={l.po_line_id}>
                    <TableCell>{l.part_name}</TableCell>
                    <TableCell align="right">
                      <TextField
                        size="small"
                        type="number"
                        value={l.quantity}
                        onChange={(e) => {
                          const q = Math.max(1, parseInt(e.target.value) || 1)
                          setLinesForms((prev) => prev.map((x, i) => i === idx ? { ...x, quantity: q } : x))
                        }}
                        inputProps={{ min: 1 }}
                        sx={{ width: 80 }}
                      />
                    </TableCell>
                    <TableCell align="right">{formatMoney(l.unit_price_ht)}</TableCell>
                    <TableCell align="right">{formatMoney(l.quantity * l.unit_price_ht)}</TableCell>
                  </TableRow>
                ))}
                <TableRow>
                  <TableCell colSpan={3} align="right"><strong>Total HT</strong></TableCell>
                  <TableCell align="right">
                    <strong>{formatMoney(linesForms.reduce((s, l) => s + l.quantity * l.unit_price_ht, 0))}</strong>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={createMutation.isPending}>Annuler</Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={createMutation.isPending || linesForms.length === 0}
        >
          {createMutation.isPending ? <CircularProgress size={20} /> : 'Créer la facture'}
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
  const qc = useQueryClient()
  const [receiveOpen, setReceiveOpen] = useState(false)
  const [invoiceOpen, setInvoiceOpen] = useState(false)
  const [createSIOpen, setCreateSIOpen] = useState(false)
  const [actioning, setActioning] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [error, setError] = useState('')

  const canSend = po.status === 'draft'
  const canReceive = po.status === 'sent' || po.status === 'partially_received'
  const canCancel = po.status !== 'completed' && po.status !== 'cancelled'

  const handleDownloadPdf = async () => {
    setPdfLoading(true)
    try {
      const url = await purchaseOrderApi.getPdf(po.id)
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      setError('Impossible de générer le PDF.')
    } finally { setPdfLoading(false) }
  }

  const handleSend = async () => {
    setActioning(true); setError('')
    try {
      const updated = await purchaseOrderApi.send(po.id, po.version)
      onUpdated(updated)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Erreur')
    } finally { setActioning(false) }
  }

  const [cancelOpen, setCancelOpen] = useState(false)

  const handleCancel = async () => {
    setActioning(true); setError('')
    try {
      const updated = await purchaseOrderApi.cancel(po.id, po.version)
      onUpdated(updated)
      setCancelOpen(false)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Erreur')
    } finally { setActioning(false) }
  }

  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} mb={2}>
        <IconButton onClick={onBack}><ArrowBackIcon /></IconButton>
        <Typography variant="h6" fontWeight={700}>{po.doc_number ?? 'BC sans numéro'}</Typography>
        <StatusChip status={po.status} label={STATUS_LABELS[po.status]} />
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Stack direction="row" spacing={1} mb={3}>
        <Button variant="outlined" startIcon={<PictureAsPdfIcon />} onClick={handleDownloadPdf} disabled={pdfLoading}>
          {pdfLoading ? <CircularProgress size={20} /> : 'Générer PDF'}
        </Button>
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
        {(po.status === 'partially_received' || po.status === 'completed') && (
          <Button variant="contained" color="success" startIcon={<ReceiptIcon />} onClick={() => setCreateSIOpen(true)}>
            Créer facture fournisseur
          </Button>
        )}
        {canCancel && (
          <Button variant="outlined" color="error" startIcon={<CancelIcon />} onClick={() => setCancelOpen(true)} disabled={actioning}>
            Annuler
          </Button>
        )}
      </Stack>

      <Stack direction="row" spacing={4} mb={3}>
        <Box>
          <Typography variant="caption" color="text.secondary">Fournisseur</Typography>
          <Typography>{po.supplier_name ?? `ID ${po.supplier_id}`}</Typography>
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
              <TableCell>{l.part_name ?? `Pièce #${l.part_id}`}</TableCell>
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
      <CreateSupplierInvoiceDialog
        open={createSIOpen}
        po={po}
        onClose={() => setCreateSIOpen(false)}
        onCreated={() => {
          setCreateSIOpen(false)
          qc.invalidateQueries({ queryKey: ['supplier-invoices'] })
        }}
      />
      <ConfirmDialog
        open={cancelOpen}
        title="Annuler le bon de commande"
        message={`Annuler le BC ${po.doc_number ?? po.id} ? Cette action est irréversible.`}
        confirmLabel="Confirmer l'annulation"
        dangerous
        loading={actioning}
        onConfirm={handleCancel}
        onCancel={() => setCancelOpen(false)}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function PurchaseOrderPage() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<POStatus | ''>('')
  const [createOpen, setCreateOpen] = useState(false)
  const [selectedPO, setSelectedPO] = useState<PurchaseOrder | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['purchase-orders', statusFilter, page],
    queryFn: () => purchaseOrderApi.list({ status: statusFilter || undefined, page, page_size: 20 }),
    placeholderData: (prev) => prev,
  })

  const pos = data?.items ?? []
  const total = data?.total ?? 0

  if (selectedPO) {
    return (
      <Box>
        <PODetail
          po={selectedPO}
          onBack={() => {
            setSelectedPO(null)
            qc.invalidateQueries({ queryKey: ['purchase-orders'] })
          }}
          onUpdated={(updated) => setSelectedPO(updated)}
        />
      </Box>
    )
  }

  return (
    <Box>
      <PageHeader
        title="Bons de commande"
        subtitle={`${total} bon${total !== 1 ? 's' : ''} au total`}
        actions={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
            Nouveau BC
          </Button>
        }
      />

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

      <DataTable
        columns={[
          {
            id: 'doc_number',
            label: 'N° document',
            render: po => (
              <Typography variant="body2" fontWeight={600} fontFamily="monospace">
                {po.doc_number ?? '—'}
              </Typography>
            ),
          },
          {
            id: 'status',
            label: 'Statut',
            width: 150,
            render: po => <StatusChip status={po.status} label={STATUS_LABELS[po.status]} />,
          },
          {
            id: 'supplier',
            label: 'Fournisseur',
            render: po => (
              <Typography variant="body2" color="text.secondary">{po.supplier_name ?? `ID ${po.supplier_id}`}</Typography>
            ),
          },
          {
            id: 'delivery',
            label: 'Livraison prévue',
            width: 140,
            render: po => (
              <Typography variant="body2" color="text.secondary">
                {po.expected_delivery_date ?? '—'}
              </Typography>
            ),
          },
          {
            id: 'total',
            label: 'Total HT',
            align: 'right',
            width: 120,
            render: po => (
              <Typography variant="body2" fontWeight={600}>{formatMoney(po.total_ht)}</Typography>
            ),
          },
          {
            id: 'lines',
            label: 'Lignes',
            width: 70,
            align: 'right',
            render: po => <Typography variant="body2">{po.lines.length}</Typography>,
          },
          {
            id: 'match',
            label: 'Match',
            width: 90,
            render: po => {
              const hasMismatch = po.lines.some(l => l.match_flag !== 'ok')
              return hasMismatch
                ? <Chip label="Écart" color="warning" size="small" />
                : <Chip label="OK" color="success" size="small" />
            },
          },
        ]}
        rows={pos}
        getRowKey={po => po.id}
        onRowClick={po => setSelectedPO(po)}
        loading={isLoading}
        total={total}
        page={page - 1}
        pageSize={20}
        onPageChange={p => setPage(p + 1)}
        emptyTitle="Aucun bon de commande"
        emptyDescription="Créez votre premier bon de commande."
      />

      <PurchaseOrderCreateDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(po) => { setCreateOpen(false); setSelectedPO(po); qc.invalidateQueries({ queryKey: ['purchase-orders'] }) }}
      />
    </Box>
  )
}
