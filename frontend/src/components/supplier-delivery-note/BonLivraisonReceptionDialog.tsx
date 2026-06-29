import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
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
import { purchaseOrderApi, PurchaseOrder, POLine } from '../../lib/purchaseOrderApi'
import { partsApi } from '../../lib/partsApi'
import { supplierDeliveryNoteApi } from '../../lib/supplierDeliveryNoteApi'

interface BonLivraisonReceptionDialogProps {
  open: boolean
  onClose: () => void
  extractionId: string
  defaultBlNumber?: string
  defaultBlDate?: string
  onConfirmed: () => void
}

interface LineState {
  quantityReceived: string
  partPublicId: string
}

// Normalise a possibly-noisy OCR date string to YYYY-MM-DD for the date input.
function parseBlDate(raw?: string): string {
  if (!raw) return ''
  const trimmed = raw.trim()
  // Already ISO (YYYY-MM-DD)
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed
  // DD/MM/YYYY or DD-MM-YYYY
  const m = trimmed.match(/^(\d{2})[/\-.](\d{2})[/\-.](\d{4})$/)
  if (m) return `${m[3]}-${m[2]}-${m[1]}`
  return ''
}

function lineLabel(line: POLine): string {
  return line.part_name ?? line.label ?? '—'
}

export function BonLivraisonReceptionDialog({
  open,
  onClose,
  extractionId,
  defaultBlNumber,
  defaultBlDate,
  onConfirmed,
}: BonLivraisonReceptionDialogProps) {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [duplicateWarning, setDuplicateWarning] = useState(false)

  const [po, setPo] = useState<PurchaseOrder | null>(null)
  const [parts, setParts] = useState<{ id: string; name: string; sku_code: string }[]>([])

  const [blNumber, setBlNumber] = useState('')
  const [blDate, setBlDate] = useState('')
  const [notes, setNotes] = useState('')
  // Keyed by PO line id.
  const [lineStates, setLineStates] = useState<Record<number, LineState>>({})

  useEffect(() => {
    if (!open) return
    let cancelled = false

    setLoading(true)
    setError('')
    setDuplicateWarning(false)
    setPo(null)
    setBlNumber(defaultBlNumber ?? '')
    setBlDate(parseBlDate(defaultBlDate))
    setNotes('')
    setLineStates({})

    async function load() {
      try {
        const { purchase_order_public_id } =
          await supplierDeliveryNoteApi.poForExtraction(extractionId)
        const order = await purchaseOrderApi.get(purchase_order_public_id)
        if (cancelled) return
        setPo(order)
        const initial: Record<number, LineState> = {}
        for (const ln of order.lines) {
          initial[ln.id] = { quantityReceived: '0', partPublicId: '' }
        }
        setLineStates(initial)
      } catch {
        if (!cancelled)
          setError('Impossible de charger le bon de commande associé.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    partsApi
      .list({ page_size: 200 })
      .then((r) => {
        if (!cancelled) setParts(r.items)
      })
      .catch(() => {
        /* parts list is best-effort; "Autre" assignment just won't be available */
      })

    return () => {
      cancelled = true
    }
  }, [open, extractionId, defaultBlNumber, defaultBlDate])

  const updateLine = (lineId: number, patch: Partial<LineState>) =>
    setLineStates((prev) => ({
      ...prev,
      [lineId]: { ...prev[lineId], ...patch },
    }))

  const receivedLines = useMemo(() => {
    if (!po) return []
    return po.lines
      .map((ln) => ({ ln, state: lineStates[ln.id] }))
      .filter(({ state }) => state && (parseInt(state.quantityReceived, 10) || 0) > 0)
  }, [po, lineStates])

  const handleConfirm = async (allowDuplicate: boolean) => {
    if (!po) return
    setError('')

    if (receivedLines.length === 0) {
      setError('Veuillez saisir une quantité reçue pour au moins une ligne.')
      return
    }

    // An "Autre" line (no catalogue part) with a received qty must have a part assigned.
    const unassignedOther = receivedLines.find(
      ({ ln, state }) => ln.part_id === null && !state.partPublicId,
    )
    if (unassignedOther) {
      setError(
        `Veuillez affecter une pièce à la ligne « ${lineLabel(
          unassignedOther.ln,
        )} » avant de confirmer la réception.`,
      )
      return
    }

    setSaving(true)
    try {
      await supplierDeliveryNoteApi.create({
        extraction_id: extractionId,
        bl_number: blNumber.trim() || undefined,
        bl_date: blDate || undefined,
        notes: notes.trim() || undefined,
        allow_duplicate_bl_number: allowDuplicate || undefined,
        lines: receivedLines.map(({ ln, state }) => ({
          po_line_id: ln.id,
          quantity_received: parseInt(state.quantityReceived, 10) || 0,
          part_public_id:
            ln.part_id === null ? state.partPublicId || undefined : undefined,
        })),
      })
      onConfirmed()
      onClose()
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response
        ?.data?.detail
      if (
        status === 409 &&
        typeof detail === 'string' &&
        detail.startsWith('DUPLICATE_BL_NUMBER')
      ) {
        setDuplicateWarning(true)
      } else {
        setError(
          typeof detail === 'string'
            ? detail
            : 'Échec de la création du bon de livraison.',
        )
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Réception du bon de livraison</DialogTitle>
      <DialogContent>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        ) : !po ? (
          <Alert severity="error" sx={{ mt: 1 }}>
            {error || 'Bon de commande introuvable.'}
          </Alert>
        ) : (
          <Stack spacing={2} mt={1}>
            {error && <Alert severity="error">{error}</Alert>}

            {duplicateWarning && (
              <Alert
                severity="warning"
                action={
                  <Button
                    color="inherit"
                    size="small"
                    disabled={saving}
                    onClick={() => handleConfirm(true)}
                  >
                    Confirmer quand même
                  </Button>
                }
              >
                Ce numéro de BL existe déjà pour ce fournisseur.
              </Alert>
            )}

            <Stack
              direction={{ xs: 'column', sm: 'row' }}
              spacing={2}
              justifyContent="space-between"
            >
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Bon de commande
                </Typography>
                <Typography variant="body1" fontWeight={600}>
                  {po.doc_number ?? '—'}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Fournisseur
                </Typography>
                <Typography variant="body1" fontWeight={600}>
                  {po.supplier_name ?? '—'}
                </Typography>
              </Box>
            </Stack>

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                label="N° de bon de livraison"
                fullWidth
                value={blNumber}
                onChange={(e) => setBlNumber(e.target.value)}
              />
              <TextField
                label="Date de livraison"
                type="date"
                fullWidth
                value={blDate}
                onChange={(e) => setBlDate(e.target.value)}
                InputLabelProps={{ shrink: true }}
              />
            </Stack>

            <TextField
              label="Notes"
              multiline
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />

            <Typography variant="subtitle2" fontWeight={600}>
              Lignes reçues
            </Typography>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Pièce</TableCell>
                  <TableCell width={90} align="right">
                    Commandé
                  </TableCell>
                  <TableCell width={90} align="right">
                    Déjà reçu
                  </TableCell>
                  <TableCell width={130}>Quantité reçue</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {po.lines.map((ln) => {
                  const state = lineStates[ln.id]
                  const isOther = ln.part_id === null
                  return (
                    <TableRow key={ln.id}>
                      <TableCell>
                        <Typography variant="body2">{lineLabel(ln)}</Typography>
                        {isOther && (
                          <Select
                            size="small"
                            fullWidth
                            displayEmpty
                            sx={{ mt: 1 }}
                            value={state?.partPublicId ?? ''}
                            onChange={(e) =>
                              updateLine(ln.id, { partPublicId: e.target.value })
                            }
                          >
                            <MenuItem value="" disabled>
                              Affecter une pièce…
                            </MenuItem>
                            {parts.map((p) => (
                              <MenuItem key={p.id} value={p.id}>
                                {p.name} ({p.sku_code})
                              </MenuItem>
                            ))}
                          </Select>
                        )}
                      </TableCell>
                      <TableCell align="right">{ln.quantity_ordered}</TableCell>
                      <TableCell align="right">{ln.quantity_received}</TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          type="number"
                          value={state?.quantityReceived ?? '0'}
                          onChange={(e) =>
                            updateLine(ln.id, { quantityReceived: e.target.value })
                          }
                          inputProps={{ min: 0, step: 1 }}
                        />
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          Annuler
        </Button>
        <Button
          variant="contained"
          onClick={() => handleConfirm(false)}
          disabled={saving || loading || !po}
        >
          {saving ? <CircularProgress size={20} /> : 'Confirmer la réception'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
