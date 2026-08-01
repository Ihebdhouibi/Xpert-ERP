import { useEffect, useRef, useState } from 'react'
import {
  Box,
  Button,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import { purchaseOrderApi, type PurchaseOrder, type POLine } from '../../lib/purchaseOrderApi'
import type { PartSummary } from '../../lib/partsApi'
import { PurchaseOrderCreateDialog } from '../purchase-order/PurchaseOrderCreateDialog'

export interface PoReceiveState {
  po: PurchaseOrder
  line: POLine
  quantity: number
  unitCostMinor: number
}

/**
 * Stock-in must be traceable to a purchase order — this lets the user pick an
 * existing PO with an unreceived line for the given part, or create a new PO
 * on the spot, then set the quantity/cost to receive. The parent dialog reads
 * `onReady` to know when a valid selection exists and to build the payload
 * for `purchaseOrderApi.receive()`.
 */
export function PoReceiveFields({
  part,
  onReady,
}: {
  part: PartSummary
  onReady: (state: PoReceiveState | null) => void
}) {
  const [pos, setPos] = useState<PurchaseOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedPoId, setSelectedPoId] = useState('')
  const [quantity, setQuantity] = useState('')
  const [unitCostEur, setUnitCostEur] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const onReadyRef = useRef(onReady)
  onReadyRef.current = onReady

  const loadPos = () => {
    setLoading(true)
    purchaseOrderApi.list({ page_size: 100 }).then((r) => {
      const matches = r.items.filter(
        (po) =>
          ['draft', 'sent', 'partially_received'].includes(po.status) &&
          po.lines.some((l) => l.part_id === part.int_id && l.quantity_ordered > l.quantity_received),
      )
      setPos(matches)
      setLoading(false)
    })
  }

  useEffect(loadPos, [part.int_id])

  const selectedPo = pos.find((p) => p.id === selectedPoId) ?? null
  const selectedLine = selectedPo?.lines.find(
    (l) => l.part_id === part.int_id && l.quantity_ordered > l.quantity_received,
  ) ?? null
  const remaining = selectedLine ? selectedLine.quantity_ordered - selectedLine.quantity_received : 0

  const selectPo = (po: PurchaseOrder) => {
    setSelectedPoId(po.id)
    const line = po.lines.find((l) => l.part_id === part.int_id && l.quantity_ordered > l.quantity_received)
    const rem = line ? line.quantity_ordered - line.quantity_received : 0
    setQuantity(rem ? String(rem) : '')
    setUnitCostEur(line ? (line.unit_price_ht / 100).toFixed(2) : '')
  }

  useEffect(() => {
    if (!selectedPo || !selectedLine) {
      onReadyRef.current(null)
      return
    }
    const qty = parseInt(quantity, 10)
    const costEur = parseFloat(unitCostEur)
    if (!qty || qty < 1 || qty > remaining || isNaN(costEur) || costEur < 0) {
      onReadyRef.current(null)
      return
    }
    onReadyRef.current({
      po: selectedPo,
      line: selectedLine,
      quantity: qty,
      unitCostMinor: Math.round(costEur * 100),
    })
  }, [selectedPo, selectedLine, quantity, unitCostEur, remaining])

  return (
    <Stack spacing={2}>
      <TextField
        select
        label="Bon de commande"
        value={selectedPoId}
        onChange={(e) => {
          const po = pos.find((p) => p.id === e.target.value)
          if (po) selectPo(po)
        }}
        fullWidth
        disabled={loading}
        helperText={
          loading
            ? 'Chargement…'
            : pos.length === 0
              ? "Aucun bon de commande ouvert n'a de ligne pour cette pièce."
              : undefined
        }
      >
        <MenuItem value="">— Sélectionner —</MenuItem>
        {pos.map((po) => (
          <MenuItem key={po.id} value={po.id}>
            {po.doc_number ?? `BC #${po.int_id}`} — {po.supplier_name ?? 'Fournisseur inconnu'}
          </MenuItem>
        ))}
      </TextField>

      <Box>
        <Button size="small" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          Créer un bon de commande
        </Button>
      </Box>

      {selectedPo && selectedLine && (
        <>
          <Typography variant="caption" color="text.secondary">
            Commandé : {selectedLine.quantity_ordered} · Déjà reçu : {selectedLine.quantity_received} · Restant : {remaining}
          </Typography>
          <TextField
            label="Quantité à recevoir"
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            inputProps={{ min: 1, max: remaining, step: 1 }}
            fullWidth
          />
          <TextField
            label="Coût unitaire (€)"
            type="number"
            value={unitCostEur}
            onChange={(e) => setUnitCostEur(e.target.value)}
            inputProps={{ min: 0, step: 0.01 }}
            helperText="Pré-rempli avec le prix du bon de commande"
            fullWidth
          />
        </>
      )}

      <PurchaseOrderCreateDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        prefillPart={{ id: part.id, name: part.name, sku_code: part.sku_code }}
        onCreated={(po) => {
          setCreateOpen(false)
          setPos((prev) => [po, ...prev.filter((p) => p.id !== po.id)])
          selectPo(po)
        }}
      />
    </Stack>
  )
}
