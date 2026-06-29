import { useState, useEffect } from 'react'
import {
  Alert,
  Box,
  Button,
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
import CancelIcon from '@mui/icons-material/Cancel'
import {
  purchaseOrderApi,
  PurchaseOrder,
  POCreatePayload,
} from '../../lib/purchaseOrderApi'
import { supplierApi, Supplier } from '../../lib/supplierApi'
import { partsApi } from '../../lib/partsApi'
import { SupplierQuickCreateDialog } from '../supplier/SupplierQuickCreateDialog'

interface PurchaseOrderCreateDialogProps {
  open: boolean
  onClose: () => void
  onCreated: (po: PurchaseOrder) => void
}

// Sentinel for an "Autre" (uncatalogued) line — selected from the part dropdown.
const OTHER_PART = '__autre__'

interface LineForm {
  part_public_id: string
  part_name: string
  label: string
  quantity_ordered: number
  unit_price_ht: number
}

export function PurchaseOrderCreateDialog({ open, onClose, onCreated }: PurchaseOrderCreateDialogProps) {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [parts, setParts] = useState<{ id: string; name: string; sku_code: string }[]>([])
  const [supplierPublicId, setSupplierPublicId] = useState('')
  const [expectedDate, setExpectedDate] = useState('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<LineForm[]>([
    { part_public_id: '', part_name: '', label: '', quantity_ordered: 1, unit_price_ht: 0 },
  ])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [supplierCreateOpen, setSupplierCreateOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    supplierApi.list({ status: 'active', page_size: 100 }).then((r) => setSuppliers(r.items))
    partsApi.list({ page_size: 200 }).then((r) => setParts(r.items)).catch(() => setError('Impossible de charger les pièces'))
  }, [open])

  const handleAddLine = () =>
    setLines((l) => [...l, { part_public_id: '', part_name: '', label: '', quantity_ordered: 1, unit_price_ht: 0 }])

  const handleRemoveLine = (i: number) =>
    setLines((l) => l.filter((_, idx) => idx !== i))

  const updateLine = (i: number, field: keyof LineForm, value: string | number) =>
    setLines((l) => l.map((ln, idx) => (idx === i ? { ...ln, [field]: value } : ln)))

  const totalHt = lines.reduce((s, l) => s + l.quantity_ordered * l.unit_price_ht, 0)

  const handleSubmit = async () => {
    setError('')
    if (!supplierPublicId) { setError('Veuillez sélectionner un fournisseur'); return }
    const invalidLine = lines.some((l) =>
      l.part_public_id === OTHER_PART ? !l.label.trim() : !l.part_public_id,
    )
    if (invalidLine) {
      setError('Chaque ligne doit avoir une pièce, ou un libellé pour les lignes « Autre ».')
      return
    }

    setSaving(true)
    try {
      const payload: POCreatePayload = {
        supplier_public_id: supplierPublicId,
        expected_delivery_date: expectedDate || undefined,
        notes: notes || undefined,
        lines: lines.map((l) =>
          l.part_public_id === OTHER_PART
            ? {
                label: l.label.trim(),
                quantity_ordered: l.quantity_ordered,
                unit_price_ht: Math.round(l.unit_price_ht * 100),
              }
            : {
                part_public_id: l.part_public_id,
                quantity_ordered: l.quantity_ordered,
                unit_price_ht: Math.round(l.unit_price_ht * 100),
              },
        ),
      }
      const po = await purchaseOrderApi.create(payload)
      onCreated(po)
      setSupplierPublicId('')
      setExpectedDate('')
      setNotes('')
      setLines([{ part_public_id: '', part_name: '', label: '', quantity_ordered: 1, unit_price_ht: 0 }])
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Erreur lors de la création')
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
          <Box>
            <Button
              size="small"
              startIcon={<AddIcon />}
              onClick={() => setSupplierCreateOpen(true)}
            >
              Ajouter un nouveau fournisseur
            </Button>
          </Box>

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
                <TableCell width={130}>Prix HT</TableCell>
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
                      {/* "Autre" first so it's always reachable without scrolling. */}
                      <MenuItem value={OTHER_PART}>Autre (pièce non répertoriée)</MenuItem>
                      {parts.map((p) => (
                        <MenuItem key={p.id} value={p.id}>{p.name} ({p.sku_code})</MenuItem>
                      ))}
                    </Select>
                    {ln.part_public_id === OTHER_PART && (
                      <TextField
                        size="small"
                        fullWidth
                        sx={{ mt: 1 }}
                        placeholder="Désignation de la pièce (Autre)"
                        value={ln.label}
                        onChange={(e) => updateLine(i, 'label', e.target.value)}
                      />
                    )}
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
                      value={ln.unit_price_ht || ''}
                      onChange={(e) => {
                        const raw = e.target.value
                        if (raw === '') return
                        const num = parseFloat(raw)
                        if (!isNaN(num) && num >= 0) updateLine(i, 'unit_price_ht', num)
                      }}
                      onBlur={() => updateLine(i, 'unit_price_ht', Math.round(ln.unit_price_ht * 100) / 100)}
                      inputProps={{ min: 0, step: 1 }}
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
            Total HT : {totalHt.toFixed(2)} €
          </Typography>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={saving}>
          {saving ? <CircularProgress size={20} /> : 'Créer'}
        </Button>
      </DialogActions>

      <SupplierQuickCreateDialog
        open={supplierCreateOpen}
        onClose={() => setSupplierCreateOpen(false)}
        onCreated={(s) => {
          setSuppliers((prev) => [s, ...prev.filter((p) => p.id !== s.id)])
          setSupplierPublicId(s.id)
          setSupplierCreateOpen(false)
        }}
      />
    </Dialog>
  )
}
