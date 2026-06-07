import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  InputAdornment,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import CheckIcon from '@mui/icons-material/Check'
import AddIcon from '@mui/icons-material/Add'
import AccountBalanceIcon from '@mui/icons-material/AccountBalance'
import DoneAllIcon from '@mui/icons-material/DoneAll'
import { PermissionGate } from '../../components/auth/PermissionGate'
import {
  stockApi,
  MOVEMENT_LABELS,
  ALERT_STATUS_LABELS,
  type LowStockAlertStatus,
  type StockMovementType,
} from '../../lib/stockApi'
import { partsApi, type PartSummary } from '../../lib/partsApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { TableLoadingSkeleton } from '../../components/ui/LoadingScreen'
import { formatMinor } from '../../components/ui/CurrencyDisplay'

function money(minor: number) {
  return formatMinor(minor, 'EUR')
}

// ---------------------------------------------------------------------------
// Add stock dialog (category → parts → quantity/cost)
// ---------------------------------------------------------------------------
function AddStockDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | ''>('')
  const [selectedPart, setSelectedPart] = useState<PartSummary | null>(null)
  const [quantity, setQuantity] = useState('')
  const [unitCostEur, setUnitCostEur] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const categoriesQ = useQuery({
    queryKey: ['part-categories'],
    queryFn: () => partsApi.listCategories({ flat: true }),
  })

  const partsQ = useQuery({
    queryKey: ['parts', 'by-category', selectedCategoryId],
    queryFn: () => partsApi.list({ category_id: selectedCategoryId as number, page_size: 100, status: 'active' }),
    enabled: selectedCategoryId !== '',
  })

  const handleClose = () => {
    setSelectedCategoryId(''); setSelectedPart(null); setQuantity(''); setUnitCostEur(''); setReason(''); setError(null)
    onClose()
  }

  const mut = useMutation({
    mutationFn: () => {
      if (!selectedPart) throw new Error('Aucune pièce sélectionnée')
      const costEur = parseFloat(unitCostEur)
      return stockApi.createMovement(selectedPart.id, {
        type: 'in',
        quantity: parseInt(quantity),
        unit_cost_minor: unitCostEur ? Math.round(costEur * 100) : undefined,
        reason: reason || 'Approvisionnement initial',
      })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stock'] })
      handleClose()
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      if (typeof detail === 'object' && detail !== null && 'code' in detail) {
        const d = detail as { code: string; available: number; requested: number }
        setError(`Stock insuffisant : disponible=${d.available}, demandé=${d.requested}`)
      } else {
        setError(typeof detail === 'string' ? detail : "Erreur lors de l'approvisionnement.")
      }
    },
  })

  const categories = categoriesQ.data ?? []
  const parts = partsQ.data?.items ?? []

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Approvisionner une pièce</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Stack spacing={2} sx={{ mt: 1 }}>
          {/* Step 1: Category */}
          <TextField
            select
            label="Catégorie"
            value={selectedCategoryId}
            onChange={(e) => {
              setSelectedCategoryId(e.target.value === '' ? '' : Number(e.target.value))
              setSelectedPart(null)
              setUnitCostEur('')
            }}
            fullWidth
          >
            <MenuItem value="">— Toutes les catégories —</MenuItem>
            {categories.map((c) => (
              <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>
            ))}
          </TextField>

          {/* Step 2: Part in selected category */}
          <TextField
            select
            label="Pièce"
            value={selectedPart?.id ?? ''}
            onChange={(e) => {
              const found = parts.find((p) => p.id === e.target.value) ?? null
              setSelectedPart(found)
              if (found) setUnitCostEur((found.selling_price_minor / 100).toFixed(2))
            }}
            fullWidth
            disabled={selectedCategoryId === '' || partsQ.isLoading}
            helperText={selectedCategoryId === '' ? 'Sélectionnez une catégorie d\'abord' : partsQ.isLoading ? 'Chargement…' : parts.length === 0 ? 'Aucune pièce dans cette catégorie' : undefined}
          >
            <MenuItem value="">— Sélectionner une pièce —</MenuItem>
            {parts.map((p) => (
              <MenuItem key={p.id} value={p.id}>
                <Stack>
                  <Typography variant="body2" fontWeight={600}>{p.sku_code} — {p.name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Prix vente : {money(p.selling_price_minor)} · Stock actuel : {p.stock_on_hand}
                  </Typography>
                </Stack>
              </MenuItem>
            ))}
          </TextField>

          <TextField
            label="Quantité à ajouter"
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            inputProps={{ min: 1, step: 1 }}
            fullWidth
            disabled={!selectedPart}
          />
          <TextField
            label="Coût unitaire (optionnel)"
            type="number"
            value={unitCostEur}
            onChange={(e) => setUnitCostEur(e.target.value)}
            InputProps={{ endAdornment: <InputAdornment position="end">€</InputAdornment> }}
            inputProps={{ min: 0, step: 0.01 }}
            fullWidth
            disabled={!selectedPart}
            helperText="Pré-rempli avec le prix de vente"
          />
          <TextField
            label="Raison"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Approvisionnement initial"
            fullWidth
            disabled={!selectedPart}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Annuler</Button>
        <Button
          variant="contained"
          disabled={!selectedPart || !quantity || parseInt(quantity) < 1 || mut.isPending}
          onClick={() => mut.mutate()}
        >
          Approvisionner
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Movement form dialog
// ---------------------------------------------------------------------------
function MovementDialog({
  open,
  onClose,
  part,
}: {
  open: boolean
  onClose: () => void
  part: PartSummary
}) {
  const qc = useQueryClient()
  const [type, setType] = useState<StockMovementType>('in')
  const [quantity, setQuantity] = useState('')
  const [unitCost, setUnitCost] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mut = useMutation({
    mutationFn: () =>
      stockApi.createMovement(part.id, {
        type,
        quantity: parseInt(quantity),
        unit_cost_minor: unitCost ? Math.round(parseFloat(unitCost) * 100) : undefined,
        reason: reason || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stock'] })
      onClose()
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      if (typeof detail === 'object' && detail !== null && 'code' in detail) {
        const d = detail as { code: string; available: number; requested: number }
        setError(`Stock insuffisant : disponible=${d.available}, demandé=${d.requested}`)
      } else {
        setError('Erreur lors du mouvement.')
      }
    },
  })

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Enregistrer un mouvement — {part.sku_code}</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Select value={type} onChange={(e) => setType(e.target.value as StockMovementType)} fullWidth>
            {(['in', 'out', 'adjustment'] as StockMovementType[]).map((t) => (
              <MenuItem key={t} value={t}>{MOVEMENT_LABELS[t]}</MenuItem>
            ))}
          </Select>
          <TextField
            label="Quantité"
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            fullWidth
            helperText={type === 'adjustment' ? 'Positif = ajout, négatif = retrait' : undefined}
          />
          {type === 'in' && (
            <TextField
              label="Coût unitaire (€)"
              type="number"
              value={unitCost}
              onChange={(e) => setUnitCost(e.target.value)}
              fullWidth
              inputProps={{ min: 0, step: '0.01' }}
            />
          )}
          <TextField
            label="Raison"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            fullWidth
            multiline
            rows={2}
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button
          variant="contained"
          disabled={!quantity || mut.isPending}
          onClick={() => mut.mutate()}
        >
          Enregistrer
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Stock levels tab
// ---------------------------------------------------------------------------
function StockLevelsTab() {
  const [movDialog, setMovDialog] = useState<PartSummary | null>(null)
  const [addOpen, setAddOpen] = useState(false)

  const levelsQ = useQuery({
    queryKey: ['stock', 'levels'],
    queryFn: () => stockApi.listAllLevels(),
    refetchInterval: 30000,
  })

  const levels = levelsQ.data ?? []

  if (levelsQ.isLoading) {
    return <Table size="small"><TableHead><TableRow>{['Article','SKU','En stock','Réservé','Disponible','Coût moyen','Mis à jour','Actions'].map(h => <TableCell key={h}>{h}</TableCell>)}</TableRow></TableHead><TableBody><TableLoadingSkeleton cols={8} rows={6} /></TableBody></Table>
  }

  return (
    <Box>
      <Box sx={{ p: 2, display: 'flex', justifyContent: 'flex-end' }}>
        <PermissionGate permission="part.update">
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setAddOpen(true)}>
            Approvisionner une pièce
          </Button>
        </PermissionGate>
      </Box>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Article</TableCell>
            <TableCell>SKU</TableCell>
            <TableCell align="right">En stock</TableCell>
            <TableCell align="right">Réservé</TableCell>
            <TableCell align="right">Disponible</TableCell>
            <TableCell align="right">Coût moyen</TableCell>
            <TableCell>Mis à jour</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {levels.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                Aucun niveau de stock enregistré — cliquez sur « Approvisionner une pièce » pour commencer
              </TableCell>
            </TableRow>
          ) : (
            levels.map((l) => (
              <TableRow key={`${l.garage_id}-${l.part_id}`} hover>
                <TableCell>
                  <Typography variant="body2" fontWeight={500}>
                    {l.part_name ?? `#${l.part_id}`}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="caption" color="text.secondary">{l.sku_code ?? '—'}</Typography>
                </TableCell>
                <TableCell align="right">{l.on_hand}</TableCell>
                <TableCell align="right">{l.reserved}</TableCell>
                <TableCell align="right">
                  <Typography
                    variant="body2"
                    color={l.available <= 0 ? 'error' : l.available < 5 ? 'warning.main' : 'inherit'}
                    fontWeight={l.available <= 0 ? 700 : 400}
                  >
                    {l.available}
                  </Typography>
                </TableCell>
                <TableCell align="right">{money(l.avg_cost_minor)}</TableCell>
                <TableCell>
                  <Typography variant="caption">
                    {new Date(l.updated_at).toLocaleString('fr-FR')}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <PermissionGate permission="part.update">
                    <Button
                      size="small"
                      startIcon={<AddIcon />}
                      onClick={() => {
                        const fakePart = { id: l.part_public_id ?? `internal-${l.part_id}`, sku_code: l.sku_code ?? `#${l.part_id}`, name: l.part_name ?? '', description: null, category_id: null, unit_of_measure: 'pcs', purchase_price_minor: 0, selling_price_minor: 0, supplier_hint_id: null, reorder_threshold: null, reorder_quantity: null, status: 'active' as const, stock_on_hand: l.on_hand, version: 1, created_at: '', updated_at: '' }
                        setMovDialog(fakePart as PartSummary)
                      }}
                    >
                      Mouvement
                    </Button>
                  </PermissionGate>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      {movDialog && (
        <MovementDialog open onClose={() => setMovDialog(null)} part={movDialog} />
      )}
      <AddStockDialog open={addOpen} onClose={() => setAddOpen(false)} />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Movements tab (all garage movements)
// ---------------------------------------------------------------------------
function MovementsTab() {
  const movQ = useQuery({
    queryKey: ['stock', 'movements'],
    queryFn: () => stockApi.listAllMovements({ limit: 100 }),
  })

  const TYPE_COLOR: Record<StockMovementType, 'success' | 'error' | 'warning' | 'info' | 'default'> = {
    in: 'success',
    out: 'error',
    adjustment: 'warning',
    reservation: 'info',
    release: 'default',
  }

  if (movQ.isLoading) {
    return <Table size="small"><TableHead><TableRow>{['Date','Type','Part ID','Qté','Coût unit.','Réf.','Raison'].map(h => <TableCell key={h}>{h}</TableCell>)}</TableRow></TableHead><TableBody><TableLoadingSkeleton cols={7} rows={6} /></TableBody></Table>
  }

  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>Date</TableCell>
          <TableCell>Type</TableCell>
          <TableCell>Part ID</TableCell>
          <TableCell align="right">Qté</TableCell>
          <TableCell align="right">Coût unit.</TableCell>
          <TableCell>Réf.</TableCell>
          <TableCell>Raison</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {(movQ.data ?? []).map((m) => (
          <TableRow key={m.id} hover>
            <TableCell>
              <Typography variant="caption">
                {new Date(m.created_at).toLocaleString('fr-FR')}
              </Typography>
            </TableCell>
            <TableCell>
              <Chip
                size="small"
                label={MOVEMENT_LABELS[m.type]}
                color={TYPE_COLOR[m.type]}
              />
            </TableCell>
            <TableCell>#{m.part_id}</TableCell>
            <TableCell align="right">
              {m.type === 'out' || m.type === 'release' ? '-' : '+'}
              {Math.abs(m.quantity)}
            </TableCell>
            <TableCell align="right">
              {m.unit_cost_minor != null ? money(m.unit_cost_minor) : '—'}
            </TableCell>
            <TableCell>
              {m.ref_type && m.ref_id ? (
                <Typography variant="caption">{m.ref_type}/{m.ref_id.slice(0, 8)}</Typography>
              ) : '—'}
            </TableCell>
            <TableCell>
              <Typography variant="caption" color="text.secondary">
                {m.reason ?? '—'}
              </Typography>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

// ---------------------------------------------------------------------------
// Alerts tab
// ---------------------------------------------------------------------------

function AlertsTab() {
  const qc = useQueryClient()
  const alertsQ = useQuery({
    queryKey: ['stock', 'alerts'],
    queryFn: () => stockApi.listAlerts(),
  })

  const ackMut = useMutation({
    mutationFn: (id: number) => stockApi.acknowledgeAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['stock', 'alerts'] }),
  })

  const resMut = useMutation({
    mutationFn: (id: number) => stockApi.resolveAlert(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stock', 'alerts'] })
      qc.invalidateQueries({ queryKey: ['stock', 'alerts', 'count'] })
    },
  })

  const alerts = alertsQ.data ?? []

  if (alertsQ.isLoading) {
    return <Table size="small"><TableHead><TableRow>{['Date','Part ID','Stock','Seuil','Réappro.','Statut','Actions'].map(h => <TableCell key={h}>{h}</TableCell>)}</TableRow></TableHead><TableBody><TableLoadingSkeleton cols={7} rows={4} /></TableBody></Table>
  }

  return (
    <Box>
      {alerts.length === 0 ? (
        <Box p={4} textAlign="center">
          <CheckIcon color="success" sx={{ fontSize: 48 }} />
          <Typography color="text.secondary">Aucune alerte de stock bas</Typography>
        </Box>
      ) : (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Date</TableCell>
              <TableCell>Part ID</TableCell>
              <TableCell align="right">Stock</TableCell>
              <TableCell align="right">Seuil</TableCell>
              <TableCell align="right">Réappro. suggéré</TableCell>
              <TableCell>Statut</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {alerts.map((a) => (
              <TableRow key={a.id} hover>
                <TableCell>
                  <Typography variant="caption">
                    {new Date(a.created_at).toLocaleString('fr-FR')}
                  </Typography>
                </TableCell>
                <TableCell>#{a.part_id}</TableCell>
                <TableCell align="right">
                  <Typography variant="body2" color="error" fontWeight={700}>
                    {a.on_hand}
                  </Typography>
                </TableCell>
                <TableCell align="right">{a.threshold}</TableCell>
                <TableCell align="right">
                  {a.suggested_reorder_quantity != null ? (
                    <Typography variant="caption">
                      {a.suggested_reorder_quantity} unités
                      {a.suggested_supplier_id != null && ` (fourn. #${a.suggested_supplier_id})`}
                    </Typography>
                  ) : '—'}
                </TableCell>
                <TableCell>
                  <StatusChip status={a.status} label={ALERT_STATUS_LABELS[a.status]} />
                </TableCell>
                <TableCell align="right">
                  <PermissionGate permission="part.update">
                    <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                      {a.status === 'open' && (
                        <Button
                          size="small"
                          startIcon={<CheckIcon />}
                          onClick={() => ackMut.mutate(a.id)}
                          disabled={ackMut.isPending}
                        >
                          Acquitter
                        </Button>
                      )}
                      {a.status !== 'resolved' && (
                        <Button
                          size="small"
                          color="success"
                          startIcon={<DoneAllIcon />}
                          onClick={() => resMut.mutate(a.id)}
                          disabled={resMut.isPending}
                        >
                          Résoudre
                        </Button>
                      )}
                    </Stack>
                  </PermissionGate>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Valuation tab
// ---------------------------------------------------------------------------
function ValuationTab() {
  const valQ = useQuery({
    queryKey: ['stock', 'valuation'],
    queryFn: () => stockApi.getValuation(),
  })

  if (valQ.isLoading) {
    return <Table size="small"><TableHead><TableRow>{['Part ID','En stock','Coût moyen','Valeur totale'].map(h => <TableCell key={h}>{h}</TableCell>)}</TableRow></TableHead><TableBody><TableLoadingSkeleton cols={4} rows={5} /></TableBody></Table>
  }

  const data = valQ.data
  if (!data) return null

  return (
    <Box>
      <Box sx={{ p: 2, pb: 0 }}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <AccountBalanceIcon color="primary" />
          <Typography variant="h6" fontWeight={700}>
            Valeur totale du stock : {money(data.total_inventory_value_minor)}
          </Typography>
        </Stack>
      </Box>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Part ID</TableCell>
            <TableCell align="right">En stock</TableCell>
            <TableCell align="right">Coût moyen</TableCell>
            <TableCell align="right">Valeur totale</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.items.length === 0 ? (
            <TableRow>
              <TableCell colSpan={4} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                Aucun article en stock
              </TableCell>
            </TableRow>
          ) : (
            data.items.map((item) => (
              <TableRow key={item.part_id} hover>
                <TableCell>#{item.part_id}</TableCell>
                <TableCell align="right">{item.on_hand}</TableCell>
                <TableCell align="right">{money(item.avg_cost_minor)}</TableCell>
                <TableCell align="right">
                  <Typography fontWeight={600}>{money(item.total_value_minor)}</Typography>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export function StockPage() {
  const [tab, setTab] = useState(0)

  const alertsQ = useQuery({
    queryKey: ['stock', 'alerts', 'count'],
    queryFn: () => stockApi.listAlerts(),
    refetchInterval: 60000,
  })
  const alertCount = (alertsQ.data ?? []).filter((a) => a.status === 'open').length

  return (
    <Box>
      <PageHeader
        title="Gestion du stock"
        subtitle="Niveaux, mouvements, alertes et valorisation"
        actions={alertCount > 0 ? (
          <StatusChip status="open" label={`${alertCount} alerte${alertCount > 1 ? 's' : ''} ouverte${alertCount > 1 ? 's' : ''}`} />
        ) : undefined}
      />

      <Paper>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="Niveaux de stock" />
          <Tab label="Mouvements" />
          <Tab
            label={
              <Stack direction="row" spacing={0.5} alignItems="center">
                <span>Alertes</span>
                {alertCount > 0 && (
                  <Chip size="small" label={alertCount} color="error" sx={{ height: 18, fontSize: 10 }} />
                )}
              </Stack>
            }
          />
          <Tab label="Valorisation" />
        </Tabs>
        <Box sx={{ p: 0, overflow: 'auto' }}>
          {tab === 0 && <StockLevelsTab />}
          {tab === 1 && <MovementsTab />}
          {tab === 2 && <AlertsTab />}
          {tab === 3 && <ValuationTab />}
        </Box>
      </Paper>
    </Box>
  )
}
