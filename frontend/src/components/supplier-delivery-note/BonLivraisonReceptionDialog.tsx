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
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh'
import { purchaseOrderApi, PurchaseOrder, POLine } from '../../lib/purchaseOrderApi'
import { partsApi } from '../../lib/partsApi'
import {
  supplierDeliveryNoteApi,
  SupplierDeliveryNoteLineInput,
} from '../../lib/supplierDeliveryNoteApi'

export interface CapturedBlLine {
  code: string
  designation: string
  quantite: string
  pu_brut: string
  pu_net: string
  montant: string
}

interface BonLivraisonReceptionDialogProps {
  open: boolean
  onClose: () => void
  extractionId: string
  defaultBlNumber?: string
  defaultBlDate?: string
  defaultEmail?: string
  // Per-line capture from the OCR review grid. When provided & non-empty, the
  // dialog maps each captured line to a PO line instead of driving from PO lines.
  blLines?: CapturedBlLine[]
  onConfirmed: () => void
}

interface LineState {
  quantityReceived: string
  partPublicId: string
}

// One mapping row when receiving from captured BL lines.
interface BlMapState {
  poLineId: string
  quantityReceived: string
  partPublicId: string
}

// Convert a euro string ("12,50" / "12.50") to integer cents, or undefined if blank.
function eurosToCents(raw: string): number | undefined {
  const t = (raw ?? '').trim().replace(',', '.')
  if (!t) return undefined
  const n = parseFloat(t)
  return Number.isNaN(n) ? undefined : Math.round(n * 100)
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

// Normalise a part code for loose matching (remove dots, dashes, spaces).
function normalizeCode(s: string): string {
  return s.replace(/[\s.\-_]/g, '').toLowerCase()
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
  defaultEmail,
  blLines,
  onConfirmed,
}: BonLivraisonReceptionDialogProps) {
  // When captured BL lines are provided, the dialog maps them to PO lines.
  const useCaptured = Boolean(blLines && blLines.length > 0)
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
  // One mapping row per captured BL line (parallel to blLines), used when
  // useCaptured is true.
  const [blMap, setBlMap] = useState<BlMapState[]>([])
  // Per-row flag: show manual part picker even when no auto-match was found.
  const [showPartOverride, setShowPartOverride] = useState<Record<number, boolean>>({})

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
    setShowPartOverride({})
    setBlMap(
      (blLines ?? []).map((l) => ({
        poLineId: '',
        quantityReceived: String(parseInt(l.quantite, 10) || 1),
        partPublicId: '',
      })),
    )

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
    // blLines is snapshotted on open; we intentionally don't re-init the mapping
    // while the dialog is open (would clobber the user's PO-line choices).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, extractionId, defaultBlNumber, defaultBlDate])

  const updateLine = (lineId: number, patch: Partial<LineState>) =>
    setLineStates((prev) => ({
      ...prev,
      [lineId]: { ...prev[lineId], ...patch },
    }))

  const updateBlMap = (i: number, patch: Partial<BlMapState>) =>
    setBlMap((prev) =>
      prev.map((row, idx) => (idx === i ? { ...row, ...patch } : row)),
    )

  // When the user picks a PO line, try to auto-match the captured code to an
  // existing inventory part so the "Affecter une pièce" field fills itself.
  const handlePoLineSelect = (i: number, poLineId: string) => {
    const poLine = po?.lines.find((ln) => String(ln.id) === poLineId)
    const captured = blLines?.[i]
    let partPublicId = ''

    if (poLine?.part_id === null && captured?.code) {
      const normCode = normalizeCode(captured.code)
      const match = parts.find((p) => normalizeCode(p.sku_code) === normCode)
      if (match) partPublicId = match.id
    }

    // Reset the manual override picker when PO line changes.
    setShowPartOverride((prev) => ({ ...prev, [i]: false }))
    updateBlMap(i, { poLineId, partPublicId })
  }

  // Look up a PO line by its (string) id from a mapping select.
  const poLineById = (id: string): POLine | undefined =>
    po?.lines.find((ln) => String(ln.id) === id)

  const receivedLines = useMemo(() => {
    if (!po) return []
    return po.lines
      .map((ln) => ({ ln, state: lineStates[ln.id] }))
      .filter(({ state }) => state && (parseInt(state.quantityReceived, 10) || 0) > 0)
  }, [po, lineStates])

  // Build the payload lines, validating along the way. Returns null on a
  // validation error (after setting the message).
  // autoCreatedPartIds maps blMap index → newly created part public_id.
  const buildPayloadLines = (
    autoCreatedPartIds: Record<number, string> = {},
  ): SupplierDeliveryNoteLineInput[] | null => {
    if (useCaptured) {
      const lines: SupplierDeliveryNoteLineInput[] = []
      for (let i = 0; i < blMap.length; i++) {
        const map = blMap[i]
        const captured = blLines![i]
        const qty = parseInt(map.quantityReceived, 10) || 0
        const poLine = poLineById(map.poLineId)

        // No PO line selected → skip this BL line (don't error).
        if (!poLine) continue
        if (qty <= 0) continue

        const resolvedPartId = map.partPublicId || autoCreatedPartIds[i] || undefined
        if (poLine.part_id === null && !resolvedPartId) {
          setError(
            `Ligne « ${captured.designation || captured.code || `#${i + 1}`} » : ` +
              'affectez une pièce à la ligne « Autre » sélectionnée.',
          )
          return null
        }
        lines.push({
          po_line_id: poLine.id,
          quantity_received: qty,
          part_public_id: poLine.part_id === null ? resolvedPartId : undefined,
          code: captured.code.trim() || undefined,
          designation: captured.designation.trim() || undefined,
          pu_brut: eurosToCents(captured.pu_brut),
          pu_net: eurosToCents(captured.pu_net),
          montant_ht: eurosToCents(captured.montant),
        })
      }
      if (lines.length === 0) {
        setError('Associez au moins une ligne de BL à une ligne de commande.')
        return null
      }
      return lines
    }

    if (receivedLines.length === 0) {
      setError('Veuillez saisir une quantité reçue pour au moins une ligne.')
      return null
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
      return null
    }
    return receivedLines.map(({ ln, state }) => ({
      po_line_id: ln.id,
      quantity_received: parseInt(state.quantityReceived, 10) || 0,
      part_public_id:
        ln.part_id === null ? state.partPublicId || undefined : undefined,
    }))
  }

  const handleConfirm = async (allowDuplicate: boolean) => {
    if (!po) return
    setError('')
    setSaving(true)

    try {
      // --- Auto-create missing parts for "Autre" PO lines (useCaptured mode) ---
      const autoCreatedPartIds: Record<number, string> = {}
      if (useCaptured) {
        for (let i = 0; i < blMap.length; i++) {
          const map = blMap[i]
          if (!map.poLineId || map.partPublicId) continue
          const poLine = poLineById(map.poLineId)
          if (!poLine || poLine.part_id !== null) continue
          const captured = blLines![i]
          if (!captured.code && !captured.designation) continue
          // Part not in catalogue → auto-create with BL data.
          const created = await partsApi.create({
            sku_code: captured.code.trim() || `BL-${Date.now()}-${i}`,
            name: captured.designation.trim() || captured.code.trim() || `Pièce ${i + 1}`,
            purchase_price_minor: eurosToCents(captured.pu_net) ?? 0,
            selling_price_minor: 0,
            unit_of_measure: 'unité',
          })
          autoCreatedPartIds[i] = created.id
        }
      }

      const lines = buildPayloadLines(autoCreatedPartIds)
      if (!lines) return

      await supplierDeliveryNoteApi.create({
        extraction_id: extractionId,
        bl_number: blNumber.trim() || undefined,
        bl_date: blDate || undefined,
        notes: notes.trim() || undefined,
        allow_duplicate_bl_number: allowDuplicate || undefined,
        supplier_email: defaultEmail?.trim() || undefined,
        lines,
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
            {useCaptured ? (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Ligne du BL</TableCell>
                    <TableCell width={220}>Ligne de commande</TableCell>
                    <TableCell width={120}>Quantité reçue</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {blLines!.map((captured, i) => {
                    const map = blMap[i]
                    const selectedPoLine = poLineById(map?.poLineId ?? '')
                    const isOther = selectedPoLine?.part_id === null
                    return (
                      <TableRow key={i}>
                        <TableCell>
                          <Typography variant="body2" fontWeight={600}>
                            {captured.designation || '—'}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {[
                              captured.code && `Code ${captured.code}`,
                              captured.pu_net && `PU ${captured.pu_net}`,
                              captured.montant && `Montant ${captured.montant}`,
                            ]
                              .filter(Boolean)
                              .join(' · ')}
                          </Typography>
                          {isOther && (
                            <Box sx={{ mt: 1 }}>
                              {map?.partPublicId ? (
                                // ✓ Auto-matched (or manually picked)
                                <Stack direction="row" alignItems="center" spacing={0.5}>
                                  <AutoFixHighIcon fontSize="small" color="success" />
                                  <Typography variant="caption" color="success.main">
                                    {parts.find((p) => p.id === map.partPublicId)?.name ?? 'Pièce sélectionnée'}
                                  </Typography>
                                  <Button
                                    size="small"
                                    sx={{ minWidth: 0, p: 0, fontSize: '0.7rem' }}
                                    onClick={() => {
                                      updateBlMap(i, { partPublicId: '' })
                                      setShowPartOverride((prev) => ({ ...prev, [i]: true }))
                                    }}
                                  >
                                    Modifier
                                  </Button>
                                </Stack>
                              ) : showPartOverride[i] ? (
                                // Manual picker (user requested override)
                                <Select
                                  size="small"
                                  fullWidth
                                  displayEmpty
                                  value=""
                                  onChange={(e) => {
                                    updateBlMap(i, { partPublicId: e.target.value })
                                    setShowPartOverride((prev) => ({ ...prev, [i]: false }))
                                  }}
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
                              ) : (
                                // No match — will auto-create on confirm
                                <Stack direction="row" alignItems="center" spacing={0.5}>
                                  <Typography variant="caption" color="text.secondary">
                                    {captured.code
                                      ? `Sera créée automatiquement (${captured.code})`
                                      : 'Aucune pièce en catalogue — sera créée'}
                                  </Typography>
                                  <Button
                                    size="small"
                                    sx={{ minWidth: 0, p: 0, fontSize: '0.7rem' }}
                                    onClick={() =>
                                      setShowPartOverride((prev) => ({ ...prev, [i]: true }))
                                    }
                                  >
                                    Choisir
                                  </Button>
                                </Stack>
                              )}
                            </Box>
                          )}
                        </TableCell>
                        <TableCell>
                          <Select
                            size="small"
                            fullWidth
                            displayEmpty
                            value={map?.poLineId ?? ''}
                            onChange={(e) => handlePoLineSelect(i, e.target.value)}
                          >
                            <MenuItem value="">
                              <em>Ignorer cette ligne</em>
                            </MenuItem>
                            {po.lines.map((ln) => (
                              <MenuItem key={ln.id} value={String(ln.id)}>
                                {lineLabel(ln)}
                              </MenuItem>
                            ))}
                          </Select>
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            type="number"
                            value={map?.quantityReceived ?? '1'}
                            onChange={(e) =>
                              updateBlMap(i, { quantityReceived: e.target.value })
                            }
                            inputProps={{ min: 0, step: 1 }}
                          />
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            ) : (
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
            )}
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
