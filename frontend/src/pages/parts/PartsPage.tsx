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
  List,
  ListItemButton,
  ListItemText,
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
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import SearchIcon from '@mui/icons-material/Search'
import LinkIcon from '@mui/icons-material/Link'
import LinkOffIcon from '@mui/icons-material/LinkOff'
import FolderIcon from '@mui/icons-material/Folder'
import { PermissionGate } from '../../components/auth/PermissionGate'
import {
  partsApi,
  STATUS_LABELS,
  type PartCategory,
  type PartSummary,
  type PartStatus,
  type PartCreatePayload,
} from '../../lib/partsApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { MoneyField } from '../../components/ui/MoneyField'
import { StatusChip } from '../../components/ui/StatusChip'
import { useToast } from '../../contexts/ToastContext'
import { formatMinor } from '../../components/ui/CurrencyDisplay'

const STATUS_COLORS: Record<PartStatus, 'success' | 'default' | 'error'> = {
  active: 'success',
  discontinued: 'default',
  out_of_stock: 'error',
}

function money(minor: number) {
  return formatMinor(minor, 'EUR')
}

// ---------------------------------------------------------------------------
// Category form dialog
// ---------------------------------------------------------------------------
function CategoryDialog({
  open,
  onClose,
  editing,
}: {
  open: boolean
  onClose: () => void
  editing: PartCategory | null
}) {
  const qc = useQueryClient()
  const [name, setName] = useState(editing?.name ?? '')
  const [description, setDescription] = useState(editing?.description ?? '')
  const [error, setError] = useState<string | null>(null)

  const saveMut = useMutation({
    mutationFn: async () => {
      if (editing) {
        return partsApi.updateCategory(editing.id, { name, description: description || undefined })
      }
      return partsApi.createCategory({ name, description: description || undefined })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['part-categories'] })
      onClose()
    },
    onError: () => setError('Erreur lors de la sauvegarde.'),
  })

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{editing ? 'Modifier catégorie' : 'Nouvelle catégorie'}</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <TextField
          label="Nom"
          value={name}
          onChange={(e) => setName(e.target.value)}
          fullWidth
          sx={{ mt: 1 }}
        />
        <TextField
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          fullWidth
          multiline
          rows={2}
          sx={{ mt: 2 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button
          variant="contained"
          disabled={!name.trim() || saveMut.isPending}
          onClick={() => saveMut.mutate()}
        >
          Enregistrer
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Part form dialog
// ---------------------------------------------------------------------------
function PartDialog({
  open,
  onClose,
  editing,
  categories,
}: {
  open: boolean
  onClose: () => void
  editing: PartSummary | null
  categories: PartCategory[]
}) {
  const qc = useQueryClient()
  const [form, setForm] = useState<PartCreatePayload>({
    sku_code: editing?.sku_code ?? '',
    name: editing?.name ?? '',
    description: editing?.description ?? '',
    category_id: editing?.category_id ?? undefined,
    unit_of_measure: editing?.unit_of_measure ?? 'pcs',
    purchase_price_minor: editing?.purchase_price_minor ?? 0,
    selling_price_minor: editing?.selling_price_minor ?? 0,
    reorder_threshold: editing?.reorder_threshold ?? undefined,
    reorder_quantity: editing?.reorder_quantity ?? undefined,
    status: editing?.status ?? 'active',
  })
  const [error, setError] = useState<string | null>(null)

  const field = (key: keyof PartCreatePayload, value: unknown) =>
    setForm((f) => ({ ...f, [key]: value }))

  const saveMut = useMutation({
    mutationFn: async () => {
      if (editing) {
        return partsApi.update(editing.id, editing.version, {
          name: form.name,
          description: form.description || undefined,
          category_id: form.category_id,
          unit_of_measure: form.unit_of_measure,
          purchase_price_minor: form.purchase_price_minor,
          selling_price_minor: form.selling_price_minor,
          reorder_threshold: form.reorder_threshold,
          reorder_quantity: form.reorder_quantity,
          status: form.status,
        })
      }
      return partsApi.create(form)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['parts'] })
      onClose()
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail
      if (typeof msg === 'object' && msg !== null && 'code' in msg && (msg as { code: string }).code === 'sku_conflict') {
        setError(`Le code SKU existe déjà.`)
      } else {
        setError('Erreur lors de la sauvegarde.')
      }
    },
  })

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{editing ? 'Modifier la pièce' : 'Nouvelle pièce'}</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField
            label="Code SKU"
            value={form.sku_code}
            onChange={(e) => field('sku_code', e.target.value)}
            disabled={!!editing}
            fullWidth
          />
          <TextField
            label="Nom"
            value={form.name}
            onChange={(e) => field('name', e.target.value)}
            fullWidth
          />
          <TextField
            label="Description"
            value={form.description}
            onChange={(e) => field('description', e.target.value)}
            fullWidth
            multiline
            rows={2}
          />
          <Select
            value={form.category_id ?? ''}
            onChange={(e) => field('category_id', e.target.value || undefined)}
            displayEmpty
            fullWidth
          >
            <MenuItem value="">— Aucune catégorie —</MenuItem>
            {categories.map((c) => (
              <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>
            ))}
          </Select>
          <TextField
            label="Unité de mesure"
            value={form.unit_of_measure}
            onChange={(e) => field('unit_of_measure', e.target.value)}
            fullWidth
          />
          <Stack direction="row" spacing={2}>
            <MoneyField
              label="Prix d'achat"
              valueMinor={form.purchase_price_minor}
              onChangeMinor={(m) => field('purchase_price_minor', m)}
              fullWidth
            />
            <MoneyField
              label="Prix de vente"
              valueMinor={form.selling_price_minor}
              onChangeMinor={(m) => field('selling_price_minor', m)}
              fullWidth
            />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField
              label="Seuil réappro."
              type="number"
              value={form.reorder_threshold ?? ''}
              onChange={(e) => field('reorder_threshold', e.target.value ? parseInt(e.target.value) : undefined)}
              fullWidth
              inputProps={{ min: 0, step: 1 }}
            />
            <TextField
              label="Qté réappro."
              type="number"
              value={form.reorder_quantity ?? ''}
              onChange={(e) => field('reorder_quantity', e.target.value ? parseInt(e.target.value) : undefined)}
              fullWidth
              inputProps={{ min: 1, step: 1 }}
            />
          </Stack>
          {editing && (
            <Select
              value={form.status}
              onChange={(e) => field('status', e.target.value as PartStatus)}
              fullWidth
            >
              {(Object.keys(STATUS_LABELS) as PartStatus[]).map((s) => (
                <MenuItem key={s} value={s}>{STATUS_LABELS[s]}</MenuItem>
              ))}
            </Select>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button
          variant="contained"
          disabled={!form.sku_code.trim() || !form.name.trim() || saveMut.isPending}
          onClick={() => saveMut.mutate()}
        >
          Enregistrer
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Equivalent link dialog
// ---------------------------------------------------------------------------
function EquivalentDialog({
  open,
  onClose,
  sourcePart,
}: {
  open: boolean
  onClose: () => void
  sourcePart: PartSummary
}) {
  const qc = useQueryClient()
  const [targetId, setTargetId] = useState('')
  const [error, setError] = useState<string | null>(null)

  const partsQuery = useQuery({
    queryKey: ['parts', 'all'],
    queryFn: () => partsApi.list({ page_size: 100 }),
  })

  const linkMut = useMutation({
    mutationFn: () => partsApi.addEquivalent(sourcePart.id, targetId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['parts'] })
      onClose()
    },
    onError: () => setError('Impossible de lier ces pièces.'),
  })

  const available = partsQuery.data?.items.filter(
    (p) => p.id !== sourcePart.id
  ) ?? []

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Lier une pièce équivalente</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Select
          value={targetId}
          onChange={(e) => setTargetId(e.target.value)}
          displayEmpty
          fullWidth
          sx={{ mt: 1 }}
        >
          <MenuItem value="">— Choisir une pièce —</MenuItem>
          {available.map((p) => (
            <MenuItem key={p.id} value={p.id}>
              [{p.sku_code}] {p.name}
            </MenuItem>
          ))}
        </Select>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Annuler</Button>
        <Button
          variant="contained"
          disabled={!targetId || linkMut.isPending}
          onClick={() => linkMut.mutate()}
        >
          Lier
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export function PartsPage() {
  const qc = useQueryClient()
  const { error: toastError } = useToast()
  const [search, setSearch] = useState('')
  const [selectedCat, setSelectedCat] = useState<number | undefined>()
  const [statusFilter, setStatusFilter] = useState<PartStatus | ''>('')
  const [page, setPage] = useState(1)

  const [catDialog, setCatDialog] = useState(false)
  const [editingCat, setEditingCat] = useState<PartCategory | null>(null)
  const [partDialog, setPartDialog] = useState(false)
  const [editingPart, setEditingPart] = useState<PartSummary | null>(null)
  const [equivDialog, setEquivDialog] = useState<PartSummary | null>(null)

  const categoriesQ = useQuery({
    queryKey: ['part-categories'],
    queryFn: () => partsApi.listCategories({ flat: true }),
  })

  const partsQ = useQuery({
    queryKey: ['parts', { search, selectedCat, statusFilter, page }],
    queryFn: () =>
      partsApi.list({
        search: search || undefined,
        category_id: selectedCat,
        status: statusFilter || undefined,
        page,
        page_size: 20,
      }),
  })

  const deleteCatMut = useMutation({
    mutationFn: (id: number) => partsApi.deleteCategory(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['part-categories'] }),
    onError: () => toastError('Impossible de supprimer cette catégorie (des pièces y sont rattachées).'),
  })

  const deletePartMut = useMutation({
    mutationFn: (id: string) => partsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['parts'] }),
    onError: () => toastError('Erreur lors de la suppression de la pièce.'),
  })

  const unlinkMut = useMutation({
    mutationFn: ({ src, tgt }: { src: string; tgt: string }) =>
      partsApi.removeEquivalent(src, tgt),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['parts'] }),
  })

  const categories = categoriesQ.data ?? []
  const parts = partsQ.data?.items ?? []
  const total = partsQ.data?.total ?? 0

  return (
    <Box display="flex" flexDirection="column" height="100%">
      <PageHeader
        title="Catalogue pièces"
        subtitle="Gérez vos pièces, catégories et équivalences"
        actions={
          <PermissionGate permission="part.create">
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => { setEditingPart(null); setPartDialog(true) }}
            >
              Nouvelle pièce
            </Button>
          </PermissionGate>
        }
      />

      <Box display="flex" flex={1} gap={2} overflow="hidden">
      {/* ---------------------------------------------------------------- */}
      {/* Left panel — categories                                           */}
      {/* ---------------------------------------------------------------- */}
      <Paper sx={{ width: 220, flexShrink: 0, p: 1, overflowY: 'auto' }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" px={1} py={0.5}>
          <Typography variant="subtitle2">Catégories</Typography>
          <PermissionGate permission="part.create">
            <Tooltip title="Nouvelle catégorie">
              <IconButton size="small" onClick={() => { setEditingCat(null); setCatDialog(true) }}>
                <AddIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </PermissionGate>
        </Stack>
        <Divider sx={{ mb: 1 }} />
        <List dense disablePadding>
          <ListItemButton
            selected={selectedCat === undefined}
            onClick={() => setSelectedCat(undefined)}
          >
            <ListItemText primary="Toutes" />
          </ListItemButton>
          {categories.map((c) => (
            <ListItemButton
              key={c.id}
              selected={selectedCat === c.id}
              onClick={() => setSelectedCat(c.id)}
            >
              <FolderIcon fontSize="small" sx={{ mr: 1, opacity: 0.6 }} />
              <ListItemText primary={c.name} />
              <PermissionGate permission="part.update">
                <Tooltip title="Modifier">
                  <IconButton size="small" onClick={(e) => {
                    e.stopPropagation()
                    setEditingCat(c)
                    setCatDialog(true)
                  }}>
                    <EditIcon sx={{ fontSize: 14 }} />
                  </IconButton>
                </Tooltip>
              </PermissionGate>
              <PermissionGate permission="part.delete">
                <Tooltip title="Supprimer">
                  <IconButton size="small" onClick={(e) => {
                    e.stopPropagation()
                    deleteCatMut.mutate(c.id)
                  }}>
                    <DeleteIcon sx={{ fontSize: 14 }} />
                  </IconButton>
                </Tooltip>
              </PermissionGate>
            </ListItemButton>
          ))}
        </List>
      </Paper>

      {/* ---------------------------------------------------------------- */}
      {/* Right panel — parts list                                          */}
      {/* ---------------------------------------------------------------- */}
      <Box flex={1} display="flex" flexDirection="column" overflow="hidden">
        {/* Toolbar */}
        <Stack direction="row" spacing={1} mb={2} alignItems="center">
          <TextField
            size="small"
            placeholder="Rechercher (nom, SKU)…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            sx={{ flex: 1 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>
              ),
            }}
          />
          <Select
            size="small"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value as PartStatus | ''); setPage(1) }}
            displayEmpty
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="">Tous statuts</MenuItem>
            {(Object.keys(STATUS_LABELS) as PartStatus[]).map((s) => (
              <MenuItem key={s} value={s}>{STATUS_LABELS[s]}</MenuItem>
            ))}
          </Select>
        </Stack>

        {/* Table */}
        <Paper sx={{ flex: 1, overflow: 'auto' }}>
          {partsQ.isLoading ? (
            <Box p={4} display="flex" justifyContent="center"><CircularProgress /></Box>
          ) : (
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>SKU</TableCell>
                  <TableCell>Nom</TableCell>
                  <TableCell>Catégorie</TableCell>
                  <TableCell>Unité</TableCell>
                  <TableCell align="right">Achat</TableCell>
                  <TableCell align="right">Vente</TableCell>
                  <TableCell>Statut</TableCell>
                  <TableCell>Équivalents</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {parts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                      Aucune pièce trouvée
                    </TableCell>
                  </TableRow>
                ) : (
                  parts.map((p) => (
                    <TableRow key={p.id} hover>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">{p.sku_code}</Typography>
                      </TableCell>
                      <TableCell>{p.name}</TableCell>
                      <TableCell>
                        {categories.find((c) => c.id === p.category_id)?.name ?? '—'}
                      </TableCell>
                      <TableCell>{p.unit_of_measure}</TableCell>
                      <TableCell align="right">{money(p.purchase_price_minor)}</TableCell>
                      <TableCell align="right">{money(p.selling_price_minor)}</TableCell>
                      <TableCell>
                        <StatusChip status={p.status} label={STATUS_LABELS[p.status]} />
                      </TableCell>
                      <TableCell>
                        <EquivalentCell part={p} onUnlink={(tgt) => unlinkMut.mutate({ src: p.id, tgt })} />
                      </TableCell>
                      <TableCell align="right">
                        <PermissionGate permission="part.update">
                          <Tooltip title="Lier équivalent">
                            <IconButton size="small" onClick={() => setEquivDialog(p)}>
                              <LinkIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Modifier">
                            <IconButton size="small" onClick={() => { setEditingPart(p); setPartDialog(true) }}>
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </PermissionGate>
                        <PermissionGate permission="part.delete">
                          <Tooltip title="Supprimer">
                            <IconButton size="small" color="error" onClick={() => deletePartMut.mutate(p.id)}>
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
        </Paper>

        {/* Pagination */}
        {total > 20 && (
          <Stack direction="row" justifyContent="flex-end" spacing={1} mt={1}>
            <Button size="small" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
              Précédent
            </Button>
            <Typography variant="body2" alignSelf="center">
              Page {page} / {Math.ceil(total / 20)}
            </Typography>
            <Button
              size="small"
              disabled={page >= Math.ceil(total / 20)}
              onClick={() => setPage((p) => p + 1)}
            >
              Suivant
            </Button>
          </Stack>
        )}
      </Box>
      </Box>

      {/* Dialogs */}
      {catDialog && (
        <CategoryDialog
          open
          onClose={() => setCatDialog(false)}
          editing={editingCat}
        />
      )}
      {partDialog && (
        <PartDialog
          open
          onClose={() => setPartDialog(false)}
          editing={editingPart}
          categories={categories}
        />
      )}
      {equivDialog && (
        <EquivalentDialog
          open
          onClose={() => setEquivDialog(null)}
          sourcePart={equivDialog}
        />
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Equivalent cell — fetches per-row
// ---------------------------------------------------------------------------
function EquivalentCell({
  part,
  onUnlink,
}: {
  part: PartSummary
  onUnlink: (targetId: string) => void
}) {
  const equivQ = useQuery({
    queryKey: ['parts', part.id, 'equivalents'],
    queryFn: () => partsApi.listEquivalents(part.id),
  })
  const peers = equivQ.data ?? []
  if (peers.length === 0) return <Typography variant="caption" color="text.secondary">—</Typography>
  return (
    <Stack direction="row" flexWrap="wrap" gap={0.5}>
      {peers.map((p) => (
        <Chip
          key={p.id}
          size="small"
          label={p.sku_code}
          onDelete={() => onUnlink(p.id)}
          deleteIcon={<LinkOffIcon />}
        />
      ))}
    </Stack>
  )
}
