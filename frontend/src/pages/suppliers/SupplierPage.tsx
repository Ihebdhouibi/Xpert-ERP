import { useState } from 'react'
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
  Divider,
  IconButton,
  InputAdornment,
  MenuItem,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import SearchIcon from '@mui/icons-material/Search'
import HistoryIcon from '@mui/icons-material/History'
import PriceCheckIcon from '@mui/icons-material/PriceCheck'
import { PermissionGate } from '../../components/auth/PermissionGate'
import {
  supplierApi,
  STATUS_LABELS,
  type Supplier,
  type SupplierCreatePayload,
  type SupplierStatus,
} from '../../lib/supplierApi'
import { partsApi, type PartSummary } from '../../lib/partsApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { useToast } from '../../contexts/ToastContext'

const STATUS_COLOR: Record<SupplierStatus, 'success' | 'default'> = {
  active: 'success',
  inactive: 'default',
}

function money(minor: number, currency = 'MAD') {
  return `${(minor / 100).toFixed(2)} ${currency}`
}

// ---------------------------------------------------------------------------
// Supplier form dialog (create / edit)
// ---------------------------------------------------------------------------

interface SupplierFormDialogProps {
  open: boolean
  initial?: Supplier | null
  onClose: () => void
  onSaved: () => void
}

function SupplierFormDialog({ open, initial, onClose, onSaved }: SupplierFormDialogProps) {
  const qc = useQueryClient()
  const isEdit = !!initial

  const [name, setName] = useState(initial?.name ?? '')
  const [email, setEmail] = useState(initial?.email ?? '')
  const [phone, setPhone] = useState(initial?.phone ?? '')
  const [address, setAddress] = useState(initial?.address ?? '')
  const [paymentDays, setPaymentDays] = useState(String(initial?.payment_terms_days ?? ''))
  const [deliveryDays, setDeliveryDays] = useState(String(initial?.average_delivery_days ?? ''))
  const [status, setStatus] = useState<SupplierStatus>(initial?.status ?? 'active')
  const [error, setError] = useState('')

  const createMutation = useMutation({
    mutationFn: (payload: SupplierCreatePayload) => supplierApi.create(payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['suppliers'] }); onSaved() },
    onError: () => setError('Erreur lors de la création du fournisseur.'),
  })

  const updateMutation = useMutation({
    mutationFn: (payload: ReturnType<typeof buildPayload>) =>
      supplierApi.update(initial!.id, payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['suppliers'] }); onSaved() },
    onError: (err: any) => {
      if (err?.response?.data?.detail?.code === 'version_conflict') {
        setError('Conflit de version — veuillez recharger la page.')
      } else {
        setError('Erreur lors de la mise à jour.')
      }
    },
  })

  function buildPayload() {
    return {
      name,
      email: email || undefined,
      phone: phone || undefined,
      address: address || undefined,
      payment_terms_days: paymentDays ? Number(paymentDays) : undefined,
      average_delivery_days: deliveryDays ? Number(deliveryDays) : undefined,
      ...(isEdit ? { version: initial!.version, status } : {}),
    }
  }

  function handleSubmit() {
    setError('')
    if (!name.trim()) { setError('Le nom est obligatoire.'); return }
    const payload = buildPayload()
    if (isEdit) {
      updateMutation.mutate(payload as any)
    } else {
      createMutation.mutate(payload as SupplierCreatePayload)
    }
  }

  const busy = createMutation.isPending || updateMutation.isPending

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isEdit ? 'Modifier le fournisseur' : 'Nouveau fournisseur'}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="Nom"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            fullWidth
          />
          <TextField
            label="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            fullWidth
          />
          <TextField
            label="Téléphone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            fullWidth
          />
          <TextField
            label="Adresse"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            multiline
            rows={2}
            fullWidth
          />
          <Stack direction="row" spacing={2}>
            <TextField
              label="Délai de paiement (jours)"
              value={paymentDays}
              onChange={(e) => setPaymentDays(e.target.value)}
              type="number"
              inputProps={{ min: 0 }}
              fullWidth
            />
            <TextField
              label="Délai de livraison (jours)"
              value={deliveryDays}
              onChange={(e) => setDeliveryDays(e.target.value)}
              type="number"
              inputProps={{ min: 0 }}
              fullWidth
            />
          </Stack>
          {isEdit && (
            <TextField
              select
              label="Statut"
              value={status}
              onChange={(e) => setStatus(e.target.value as SupplierStatus)}
              fullWidth
            >
              <MenuItem value="active">Actif</MenuItem>
              <MenuItem value="inactive">Inactif</MenuItem>
            </TextField>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>Annuler</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={busy}>
          {busy ? <CircularProgress size={20} /> : isEdit ? 'Enregistrer' : 'Créer'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Price history dialog
// ---------------------------------------------------------------------------

interface PriceHistoryDialogProps {
  open: boolean
  supplier: Supplier | null
  onClose: () => void
}

function PriceHistoryDialog({ open, supplier, onClose }: PriceHistoryDialogProps) {
  const qc = useQueryClient()
  const [partSearch, setPartSearch] = useState('')
  const [selectedPartId, setSelectedPartId] = useState('')
  const [priceMinor, setPriceMinor] = useState('')
  const [currency, setCurrency] = useState('MAD')
  const [effectiveFrom, setEffectiveFrom] = useState('')
  const [addError, setAddError] = useState('')

  const { data: prices = [], isLoading } = useQuery({
    queryKey: ['supplier-prices', supplier?.id],
    queryFn: () => supplierApi.listPrices(supplier!.id),
    enabled: open && !!supplier,
  })

  const { data: partsData } = useQuery({
    queryKey: ['parts', partSearch],
    queryFn: () => partsApi.list({ search: partSearch, page_size: 10 }),
    enabled: partSearch.length >= 2,
  })

  const addMutation = useMutation({
    mutationFn: () =>
      supplierApi.addPrice(supplier!.id, {
        part_public_id: selectedPartId,
        unit_price_minor: Math.round(Number(priceMinor) * 100),
        currency,
        effective_from: effectiveFrom,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['supplier-prices', supplier?.id] })
      setSelectedPartId('')
      setPartSearch('')
      setPriceMinor('')
      setEffectiveFrom('')
      setAddError('')
    },
    onError: () => setAddError('Erreur lors de l\'ajout du prix.'),
  })

  function handleAdd() {
    setAddError('')
    if (!selectedPartId || !priceMinor || !effectiveFrom) {
      setAddError('Tous les champs sont obligatoires.')
      return
    }
    addMutation.mutate()
  }

  const parts: PartSummary[] = partsData?.items ?? []

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Historique des prix — {supplier?.name}
      </DialogTitle>
      <DialogContent>
        <Typography variant="subtitle2" mb={1}>Ajouter un prix</Typography>
        <Stack direction="row" spacing={1} mb={2} flexWrap="wrap">
          <TextField
            label="Rechercher une pièce"
            value={partSearch}
            onChange={(e) => { setPartSearch(e.target.value); setSelectedPartId('') }}
            size="small"
            sx={{ minWidth: 200 }}
          />
          {parts.length > 0 && !selectedPartId && (
            <Paper sx={{ p: 1, maxHeight: 140, overflowY: 'auto', minWidth: 220 }}>
              {parts.map((p) => (
                <Box
                  key={p.id}
                  sx={{ cursor: 'pointer', px: 1, py: 0.5, '&:hover': { bgcolor: 'action.hover' } }}
                  onClick={() => { setSelectedPartId(p.id); setPartSearch(p.name) }}
                >
                  <Typography variant="body2">{p.name} ({p.sku_code})</Typography>
                </Box>
              ))}
            </Paper>
          )}
          <TextField
            label="Prix (MAD)"
            value={priceMinor}
            onChange={(e) => setPriceMinor(e.target.value)}
            type="number"
            inputProps={{ min: 0, step: '0.01' }}
            size="small"
            sx={{ width: 130 }}
          />
          <TextField
            label="Devise"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            size="small"
            sx={{ width: 80 }}
          />
          <TextField
            label="Valable dès"
            value={effectiveFrom}
            onChange={(e) => setEffectiveFrom(e.target.value)}
            type="date"
            size="small"
            InputLabelProps={{ shrink: true }}
            sx={{ width: 160 }}
          />
          <Button
            variant="contained"
            size="small"
            onClick={handleAdd}
            disabled={addMutation.isPending}
          >
            Ajouter
          </Button>
        </Stack>
        {addError && <Alert severity="error" sx={{ mb: 1 }}>{addError}</Alert>}
        <Divider sx={{ mb: 1 }} />
        <Typography variant="subtitle2" mb={1}>Historique</Typography>
        {isLoading ? (
          <CircularProgress size={24} />
        ) : prices.length === 0 ? (
          <Typography variant="body2" color="text.secondary">Aucun prix enregistré.</Typography>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Pièce</TableCell>
                <TableCell>SKU</TableCell>
                <TableCell>Prix</TableCell>
                <TableCell>Devise</TableCell>
                <TableCell>Valable dès</TableCell>
                <TableCell>Valable jusqu'à</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {prices.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>{p.part_name}</TableCell>
                  <TableCell>{p.part_sku}</TableCell>
                  <TableCell>{money(p.unit_price_minor, p.currency)}</TableCell>
                  <TableCell>{p.currency}</TableCell>
                  <TableCell>{p.effective_from}</TableCell>
                  <TableCell>
                    {p.effective_to ? (
                      p.effective_to
                    ) : (
                      <Chip label="Actuel" size="small" color="success" />
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Fermer</Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Price comparison tab
// ---------------------------------------------------------------------------

function PriceComparisonTab() {
  const [partSearch, setPartSearch] = useState('')
  const [selectedPart, setSelectedPart] = useState<PartSummary | null>(null)
  const [atDate, setAtDate] = useState('')

  const { data: partsData } = useQuery({
    queryKey: ['parts-search', partSearch],
    queryFn: () => partsApi.list({ search: partSearch, page_size: 10 }),
    enabled: partSearch.length >= 2,
  })

  const { data: comparison = [], isLoading, isFetched } = useQuery({
    queryKey: ['price-comparison', selectedPart?.id, atDate],
    queryFn: () =>
      supplierApi.getPartPrices(selectedPart!.id, atDate ? { at: atDate } : undefined),
    enabled: !!selectedPart,
  })

  const parts: PartSummary[] = partsData?.items ?? []

  return (
    <Box>
      <Typography variant="h6" mb={2}>
        Comparaison des prix fournisseurs
      </Typography>
      <Stack direction="row" spacing={2} mb={3} flexWrap="wrap">
        <Box sx={{ position: 'relative' }}>
          <TextField
            label="Rechercher une pièce"
            value={partSearch}
            onChange={(e) => { setPartSearch(e.target.value); setSelectedPart(null) }}
            size="small"
            sx={{ minWidth: 250 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
          {parts.length > 0 && !selectedPart && (
            <Paper
              sx={{
                position: 'absolute',
                zIndex: 10,
                mt: 0.5,
                p: 1,
                maxHeight: 160,
                overflowY: 'auto',
                minWidth: 280,
              }}
            >
              {parts.map((p) => (
                <Box
                  key={p.id}
                  sx={{ cursor: 'pointer', px: 1, py: 0.5, '&:hover': { bgcolor: 'action.hover' } }}
                  onClick={() => { setSelectedPart(p); setPartSearch(p.name) }}
                >
                  <Typography variant="body2" fontWeight={600}>{p.name}</Typography>
                  <Typography variant="caption" color="text.secondary">{p.sku_code}</Typography>
                </Box>
              ))}
            </Paper>
          )}
        </Box>
        <TextField
          label="Date historique"
          value={atDate}
          onChange={(e) => setAtDate(e.target.value)}
          type="date"
          size="small"
          InputLabelProps={{ shrink: true }}
          sx={{ width: 180 }}
          helperText="Laisser vide pour le prix actuel"
        />
      </Stack>

      {!selectedPart && (
        <Typography color="text.secondary">
          Sélectionnez une pièce pour afficher les prix fournisseurs.
        </Typography>
      )}

      {selectedPart && isLoading && <CircularProgress size={24} />}

      {selectedPart && isFetched && comparison.length === 0 && (
        <Alert severity="info">Aucun fournisseur ne propose cette pièce.</Alert>
      )}

      {comparison.length > 0 && (
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Fournisseur</TableCell>
              <TableCell align="right">Prix unitaire</TableCell>
              <TableCell>Devise</TableCell>
              <TableCell align="right">Délai livraison</TableCell>
              <TableCell align="right">Score fiabilité</TableCell>
              <TableCell>Valable dès</TableCell>
              <TableCell>Valable jusqu'à</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {comparison.map((item, idx) => (
              <TableRow
                key={item.supplier_public_id}
                sx={idx === 0 ? { bgcolor: 'success.50' } : undefined}
              >
                <TableCell>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    {idx === 0 && (
                      <Chip label="Meilleur prix" size="small" color="success" />
                    )}
                    <Typography variant="body2">{item.supplier_name}</Typography>
                  </Stack>
                </TableCell>
                <TableCell align="right">
                  <Typography fontWeight={idx === 0 ? 700 : 400}>
                    {money(item.unit_price_minor, item.currency)}
                  </Typography>
                </TableCell>
                <TableCell>{item.currency}</TableCell>
                <TableCell align="right">
                  {item.average_delivery_days != null
                    ? `${item.average_delivery_days} j`
                    : '—'}
                </TableCell>
                <TableCell align="right">
                  {item.reliability_score != null ? (
                    <Chip
                      label={`${item.reliability_score.toFixed(1)} %`}
                      size="small"
                      color={
                        item.reliability_score >= 80
                          ? 'success'
                          : item.reliability_score >= 50
                          ? 'warning'
                          : 'error'
                      }
                    />
                  ) : (
                    '—'
                  )}
                </TableCell>
                <TableCell>{item.effective_from}</TableCell>
                <TableCell>
                  {item.effective_to ?? <Chip label="Actuel" size="small" color="success" />}
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
// Main page
// ---------------------------------------------------------------------------

export function SupplierPage() {
  const qc = useQueryClient()
  const { success, error: toastError } = useToast()
  const [tab, setTab] = useState(0)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<SupplierStatus | ''>('')
  const [page] = useState(1)

  const [formOpen, setFormOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Supplier | null>(null)
  const [priceDialogSupplier, setPriceDialogSupplier] = useState<Supplier | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<Supplier | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['suppliers', search, statusFilter, page],
    queryFn: () =>
      supplierApi.list({
        search: search || undefined,
        status: (statusFilter as SupplierStatus) || undefined,
        page,
      }),
    enabled: tab === 0,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => supplierApi.delete(id),
    onSuccess: () => {
      success('Fournisseur supprimé.')
      qc.invalidateQueries({ queryKey: ['suppliers'] })
      setDeleteConfirm(null)
    },
    onError: () => toastError('Impossible de supprimer ce fournisseur.'),
  })

  function openCreate() {
    setEditTarget(null)
    setFormOpen(true)
  }

  function openEdit(s: Supplier) {
    setEditTarget(s)
    setFormOpen(true)
  }

  const items = data?.items ?? []

  return (
    <Box>
      <PageHeader
        title="Fournisseurs"
        subtitle={data ? `${data.total} fournisseur${data.total !== 1 ? 's' : ''}` : 'Gestion des fournisseurs'}
        actions={
          <PermissionGate permission="supplier.create">
            <Button startIcon={<AddIcon />} variant="contained" onClick={openCreate}>
              Nouveau fournisseur
            </Button>
          </PermissionGate>
        }
      />

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label="Liste" />
        <Tab label="Comparaison des prix" icon={<PriceCheckIcon />} iconPosition="start" />
      </Tabs>

      {tab === 0 && (
        <>
          <Stack direction="row" spacing={2} mb={2}>
            <TextField
              placeholder="Rechercher par nom, email, téléphone…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              size="small"
              sx={{ width: 340 }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              select
              label="Statut"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as SupplierStatus | '')}
              size="small"
              sx={{ width: 140 }}
            >
              <MenuItem value="">Tous</MenuItem>
              <MenuItem value="active">Actif</MenuItem>
              <MenuItem value="inactive">Inactif</MenuItem>
            </TextField>
          </Stack>

          {isLoading && <CircularProgress size={24} />}
          {error && <Alert severity="error">Erreur de chargement.</Alert>}

          {!isLoading && !error && (
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Nom</TableCell>
                  <TableCell>Email</TableCell>
                  <TableCell>Téléphone</TableCell>
                  <TableCell align="right">Délai paiement</TableCell>
                  <TableCell align="right">Délai livraison</TableCell>
                  <TableCell align="right">Fiabilité</TableCell>
                  <TableCell>Statut</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} align="center">
                      <Typography color="text.secondary">Aucun fournisseur.</Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  items.map((s) => (
                    <TableRow key={s.id} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {s.name}
                        </Typography>
                      </TableCell>
                      <TableCell>{s.email ?? '—'}</TableCell>
                      <TableCell>{s.phone ?? '—'}</TableCell>
                      <TableCell align="right">
                        {s.payment_terms_days != null ? `${s.payment_terms_days} j` : '—'}
                      </TableCell>
                      <TableCell align="right">
                        {s.average_delivery_days != null
                          ? `${s.average_delivery_days} j`
                          : '—'}
                      </TableCell>
                      <TableCell align="right">
                        {s.reliability_score != null ? (
                          <Chip
                            label={`${s.reliability_score.toFixed(1)} %`}
                            size="small"
                            color={
                              s.reliability_score >= 80
                                ? 'success'
                                : s.reliability_score >= 50
                                ? 'warning'
                                : 'error'
                            }
                          />
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell>
                        <StatusChip status={s.status} label={STATUS_LABELS[s.status]} />
                      </TableCell>
                      <TableCell align="right">
                        <Tooltip title="Historique des prix">
                          <IconButton
                            size="small"
                            onClick={() => setPriceDialogSupplier(s)}
                          >
                            <HistoryIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <PermissionGate permission="supplier.create">
                          <Tooltip title="Modifier">
                            <IconButton size="small" onClick={() => openEdit(s)}>
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Supprimer">
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => setDeleteConfirm(s)}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </PermissionGate>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}

        </>
      )}

      {tab === 1 && <PriceComparisonTab />}

      {/* Create / Edit dialog */}
      <SupplierFormDialog
        open={formOpen}
        initial={editTarget}
        onClose={() => setFormOpen(false)}
        onSaved={() => setFormOpen(false)}
      />

      {/* Price history dialog */}
      <PriceHistoryDialog
        open={!!priceDialogSupplier}
        supplier={priceDialogSupplier}
        onClose={() => setPriceDialogSupplier(null)}
      />

      <ConfirmDialog
        open={!!deleteConfirm}
        title="Supprimer le fournisseur"
        message={`Supprimer "${deleteConfirm?.name}" ? Les bons de commande associés seront conservés.`}
        confirmLabel="Supprimer"
        dangerous
        loading={deleteMutation.isPending}
        onConfirm={() => deleteConfirm && deleteMutation.mutate(deleteConfirm.id)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Box>
  )
}
