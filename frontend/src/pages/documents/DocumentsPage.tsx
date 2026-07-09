import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
  Paper,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep'
import DownloadIcon from '@mui/icons-material/Download'
import PageviewIcon from '@mui/icons-material/Pageview'
import SearchIcon from '@mui/icons-material/Search'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import type { DocumentCategory, DocumentOut, OwnerEntityType } from '../../lib/documentsApi'
import { documentsApi } from '../../lib/documentsApi'
import { ocrApi } from '../../lib/ocrApi'
import {
  purchaseOrderApi,
  PurchaseOrder,
  STATUS_LABELS,
} from '../../lib/purchaseOrderApi'
import { vehiclesApi, VehicleOut } from '../../lib/vehiclesApi'
import { customerApi, CustomerSummary } from '../../lib/customerApi'
import { PurchaseOrderCreateDialog } from '../../components/purchase-order/PurchaseOrderCreateDialog'

// Complete labels for DISPLAY — covers every enum value (including legacy ones
// no longer offered in the dropdowns) so existing documents always render a
// proper French label.
const CATEGORY_LABELS: Record<DocumentCategory, string> = {
  registration_card: 'Carte grise',
  supplier_invoice: 'Facture fournisseur',
  supplier_delivery_note: 'Bon de livraison',
  invoice: 'Facture',
  id_doc: "Pièce d'identité",
  insurance: 'Assurance',
  accident_photo: 'Photo accident',
  repair_attachment: 'Annexe OR',
  generic: 'Générique',
}

const OWNER_LABELS: Record<OwnerEntityType, string> = {
  vehicle: 'Véhicule',
  supplier: 'Fournisseur',
  purchase_order: 'Bon de commande',
  supplier_invoice: 'Facture fournisseur',
  customer: 'Client',
  repair_order: 'Ordre de réparation',
  invoice: 'Facture',
  generic: 'Générique',
}

// Options OFFERED in the upload + filter dropdowns — scoped to the document
// flows we currently handle (Carte grise, Facture fournisseur, Bon de livraison).
const CATEGORIES: { value: DocumentCategory | ''; label: string }[] = [
  { value: '', label: 'Toutes les catégories' },
  { value: 'registration_card', label: CATEGORY_LABELS.registration_card },
  { value: 'supplier_invoice', label: CATEGORY_LABELS.supplier_invoice },
  { value: 'supplier_delivery_note', label: CATEGORY_LABELS.supplier_delivery_note },
  { value: 'generic', label: CATEGORY_LABELS.generic },
]

const OWNER_TYPES: { value: OwnerEntityType | ''; label: string }[] = [
  { value: '', label: 'Tous les types' },
  { value: 'vehicle', label: OWNER_LABELS.vehicle },
  { value: 'supplier', label: OWNER_LABELS.supplier },
  { value: 'purchase_order', label: OWNER_LABELS.purchase_order },
  { value: 'supplier_invoice', label: OWNER_LABELS.supplier_invoice },
  { value: 'generic', label: OWNER_LABELS.generic },
]

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / 1024 / 1024).toFixed(1)} Mo`
}

function categoryLabel(cat: DocumentCategory): string {
  return CATEGORY_LABELS[cat] ?? cat
}

function ownerLabel(owner: OwnerEntityType): string {
  return OWNER_LABELS[owner] ?? owner
}

// ---------------------------------------------------------------------------
// Purchase order picker (searchable + create-new)
// ---------------------------------------------------------------------------
interface PurchaseOrderPickerProps {
  value: PurchaseOrder | null
  onChange: (po: PurchaseOrder | null) => void
}

function PurchaseOrderPicker({ value, onChange }: PurchaseOrderPickerProps) {
  const [inputValue, setInputValue] = useState('')
  const [debounced, setDebounced] = useState('')
  const [options, setOptions] = useState<PurchaseOrder[]>([])
  const [fetching, setFetching] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)

  // Debounce the typed search text.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(inputValue), 300)
    return () => clearTimeout(t)
  }, [inputValue])

  useEffect(() => {
    let cancelled = false
    setFetching(true)
    purchaseOrderApi
      .list({ search: debounced || undefined, page_size: 20 })
      .then((r) => { if (!cancelled) setOptions(r.items) })
      .catch(() => { if (!cancelled) setOptions([]) })
      .finally(() => { if (!cancelled) setFetching(false) })
    return () => { cancelled = true }
  }, [debounced])

  const getLabel = (po: PurchaseOrder) =>
    `${po.doc_number ?? 'Brouillon'} — ${po.supplier_name ?? ''} — ${STATUS_LABELS[po.status]}`

  return (
    <>
      <Autocomplete
        value={value}
        onChange={(_, newValue) => onChange(newValue)}
        inputValue={inputValue}
        onInputChange={(_, v) => setInputValue(v)}
        options={options}
        getOptionLabel={getLabel}
        isOptionEqualToValue={(a, b) => a.int_id === b.int_id}
        loading={fetching}
        size="small"
        noOptionsText="Aucun bon de commande trouvé"
        renderInput={(params) => (
          <TextField
            {...params}
            label="Bon de commande *"
            InputProps={{
              ...params.InputProps,
              endAdornment: (
                <>
                  {fetching ? <CircularProgress size={16} /> : null}
                  {params.InputProps.endAdornment}
                </>
              ),
            }}
          />
        )}
        renderOption={(props, option) => (
          <Box component="li" {...props} key={option.int_id}>
            {getLabel(option)}
          </Box>
        )}
      />
      <Box>
        <Button size="small" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          Créer un nouveau bon de commande
        </Button>
      </Box>
      <PurchaseOrderCreateDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(po) => {
          onChange(po)
          setCreateOpen(false)
        }}
      />
    </>
  )
}

// ---------------------------------------------------------------------------
// Vehicle picker for carte grise uploads (only vehicles without one)
// ---------------------------------------------------------------------------
interface VehicleRegistrationPickerProps {
  value: VehicleOut | null
  onChange: (v: VehicleOut | null) => void
}

function VehicleRegistrationPicker({ value, onChange }: VehicleRegistrationPickerProps) {
  const [allVehicles, setAllVehicles] = useState<VehicleOut[]>([])
  const [takenIds, setTakenIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(false)
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerSummary | null>(null)
  const [customers, setCustomers] = useState<CustomerSummary[]>([])
  const [custSearch, setCustSearch] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  // inline create form state
  const [newMake, setNewMake] = useState('')
  const [newModel, setNewModel] = useState('')
  const [newReg, setNewReg] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([
      vehiclesApi.list({ status: 'active', page_size: 200 }),
      documentsApi.list({ category: 'registration_card', owner_entity_type: 'vehicle', limit: 500 }),
    ])
      .then(([vRes, dRes]) => {
        if (cancelled) return
        const ids = new Set<number>(
          (dRes?.items ?? []).map((d) => d.owner_entity_id).filter((id): id is number => id != null)
        )
        setTakenIds(ids)
        setAllVehicles(vRes?.items ?? [])
      })
      .catch(() => { setAllVehicles([]); setTakenIds(new Set()) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  // Load customers for the client filter (debounced search).
  useEffect(() => {
    let cancelled = false
    customerApi.list({ q: custSearch || undefined, page_size: 50 })
      .then((r) => { if (!cancelled) setCustomers(r?.items ?? []) })
      .catch(() => { if (!cancelled) setCustomers([]) })
    return () => { cancelled = true }
  }, [custSearch])

  const available = (allVehicles ?? []).filter((v) => {
    if (takenIds.has(v.id)) return false
    if (selectedCustomer && v.customer_id !== selectedCustomer.int_id) return false
    return true
  })

  const getLabel = (v: VehicleOut) =>
    `${v.make} ${v.model}${v.registration ? ` — ${v.registration}` : ''}${v.year ? ` (${v.year})` : ''}`

  const handleCreate = async () => {
    if (!newMake.trim() || !newModel.trim()) return
    setCreating(true)
    try {
      const created = await vehiclesApi.create({
        make: newMake.trim(),
        model: newModel.trim(),
        registration: newReg.trim() || null,
      })
      setAllVehicles((prev) => [created, ...prev])
      onChange(created)
      setCreateOpen(false)
      setNewMake(''); setNewModel(''); setNewReg('')
    } catch {
      /* ignore */
    } finally {
      setCreating(false)
    }
  }

  return (
    <>
      {/* Client filter — narrows the vehicle list to one client's fleet */}
      <Autocomplete
        value={selectedCustomer}
        onChange={(_, v) => { setSelectedCustomer(v); onChange(null) }}
        inputValue={custSearch}
        onInputChange={(_, v) => setCustSearch(v)}
        options={customers ?? []}
        getOptionLabel={(c) => (c ? (c.company_name || c.full_name) : '')}
        isOptionEqualToValue={(a, b) => a.int_id === b.int_id}
        size="small"
        clearOnEscape
        noOptionsText="Aucun client trouvé"
        renderInput={(params) => <TextField {...params} label="Filtrer par client (optionnel)" />}
        renderOption={(props, option) => (
          <Box component="li" {...props} key={option.int_id}>
            {option.company_name || option.full_name}
          </Box>
        )}
      />
      {/* Vehicle autocomplete filtered by client + no existing CG */}
      <Autocomplete
        value={value}
        onChange={(_, v) => onChange(v)}
        options={available ?? []}
        getOptionLabel={getLabel}
        isOptionEqualToValue={(a, b) => a.id === b.id}
        loading={loading}
        size="small"
        noOptionsText="Aucun véhicule sans carte grise"
        renderInput={(params) => (
          <TextField
            {...params}
            label="Véhicule *"
            InputProps={{
              ...params.InputProps,
              endAdornment: (
                <>
                  {loading ? <CircularProgress size={16} /> : null}
                  {params.InputProps.endAdornment}
                </>
              ),
            }}
          />
        )}
        renderOption={(props, option) => (
          <Box component="li" {...props} key={option.id}>{getLabel(option)}</Box>
        )}
      />
      <Box>
        <Button size="small" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
          Créer un nouveau véhicule
        </Button>
      </Box>
      {createOpen && (
        <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1.5 }}>
          <Typography variant="caption" fontWeight={600} display="block" mb={1}>
            Nouveau véhicule
          </Typography>
          <Stack spacing={1}>
            <TextField size="small" label="Marque *" value={newMake} onChange={(e) => setNewMake(e.target.value)} />
            <TextField size="small" label="Modèle *" value={newModel} onChange={(e) => setNewModel(e.target.value)} />
            <TextField size="small" label="Immatriculation (optionnel)" value={newReg} onChange={(e) => setNewReg(e.target.value)} />
            <Stack direction="row" spacing={1}>
              <Button size="small" onClick={() => setCreateOpen(false)}>Annuler</Button>
              <Button
                size="small"
                variant="contained"
                disabled={!newMake.trim() || !newModel.trim() || creating}
                onClick={handleCreate}
              >
                {creating ? <CircularProgress size={16} /> : 'Créer'}
              </Button>
            </Stack>
          </Stack>
        </Box>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Upload dialog
// ---------------------------------------------------------------------------
interface UploadDialogProps {
  open: boolean
  onClose: () => void
  onUploaded: (doc: DocumentOut) => void
}

function UploadDialog({ open, onClose, onUploaded }: UploadDialogProps) {
  const [file, setFile] = useState<File | null>(null)
  const [category, setCategory] = useState<DocumentCategory>('generic')
  const [ownerType, setOwnerType] = useState<OwnerEntityType>('generic')
  const [ownerId, setOwnerId] = useState('')
  const [selectedPO, setSelectedPO] = useState<PurchaseOrder | null>(null)
  const [selectedVehicle, setSelectedVehicle] = useState<VehicleOut | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const isRegistrationCard = category === 'registration_card'
  const isPurchaseOrder = ownerType === 'purchase_order'

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const effectiveOwnerType: OwnerEntityType = isRegistrationCard ? 'vehicle' : ownerType
      const effectiveOwnerId = isRegistrationCard
        ? (selectedVehicle ? selectedVehicle.id : undefined)
        : (ownerId ? Number(ownerId) : undefined)
      const doc = await documentsApi.upload(
        file,
        category,
        effectiveOwnerType,
        effectiveOwnerId,
      )
      onUploaded(doc)
      onClose()
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(
        detail
          ? `Erreur lors du téléchargement : ${detail}`
          : 'Erreur lors du téléchargement. Vérifiez le fichier et réessayez.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Télécharger un document</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}
          <Button
            variant="outlined"
            startIcon={<UploadFileIcon />}
            onClick={() => fileRef.current?.click()}
          >
            {file ? file.name : 'Sélectionner un fichier'}
          </Button>
          <input
            ref={fileRef}
            type="file"
            hidden
            accept="application/pdf,image/jpeg,image/png,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />

          <FormControl fullWidth size="small">
            <InputLabel>Catégorie</InputLabel>
            <Select
              value={category}
              label="Catégorie"
              onChange={(e) => {
                const next = e.target.value as DocumentCategory
                setCategory(next)
                // Carte grise is always linked to a vehicle — reset other pickers.
                if (next === 'registration_card') {
                  setOwnerType('vehicle')
                  setOwnerId('')
                  setSelectedPO(null)
                  setSelectedVehicle(null)
                }
              }}
            >
              {CATEGORIES.filter((c) => c.value !== '').map((c) => (
                <MenuItem key={c.value} value={c.value}>
                  {c.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Carte grise: locked to vehicle, show dedicated picker */}
          {isRegistrationCard ? (
            <VehicleRegistrationPicker
              value={selectedVehicle}
              onChange={setSelectedVehicle}
            />
          ) : (
            <>
              <FormControl fullWidth size="small">
                <InputLabel>Type propriétaire</InputLabel>
                <Select
                  value={ownerType}
                  label="Type propriétaire"
                  onChange={(e) => {
                    const next = e.target.value as OwnerEntityType
                    setOwnerType(next)
                    setOwnerId('')
                    setSelectedPO(null)
                  }}
                >
                  {OWNER_TYPES.filter((o) => o.value !== '').map((o) => (
                    <MenuItem key={o.value} value={o.value}>
                      {o.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {isPurchaseOrder ? (
                <PurchaseOrderPicker
                  value={selectedPO}
                  onChange={(po) => {
                    setSelectedPO(po)
                    setOwnerId(po ? String(po.int_id) : '')
                  }}
                />
              ) : (
                <TextField
                  label="ID propriétaire (optionnel)"
                  size="small"
                  value={ownerId}
                  onChange={(e) => setOwnerId(e.target.value)}
                />
              )}
            </>
          )}

          <Button
            variant="contained"
            disabled={!file || loading || (isPurchaseOrder && !selectedPO) || (isRegistrationCard && !selectedVehicle)}
            onClick={handleUpload}
          >
            {loading ? <CircularProgress size={20} /> : 'Télécharger'}
          </Button>
        </Stack>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export function DocumentsPage() {
  const navigate = useNavigate()
  const [docs, setDocs] = useState<DocumentOut[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Filters
  const [q, setQ] = useState('')
  const [category, setCategory] = useState<DocumentCategory | ''>('')
  const [ownerType, setOwnerType] = useState<OwnerEntityType | ''>('')

  const [uploadOpen, setUploadOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [enqueuingId, setEnqueuingId] = useState<string | null>(null)

  // Batch selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false)
  const [batchDeleting, setBatchDeleting] = useState(false)

  const allSelected = docs.length > 0 && selectedIds.size === docs.length
  const someSelected = selectedIds.size > 0 && !allSelected

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(docs.map((d) => d.id)))
    }
  }

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleBatchDelete = async () => {
    setBatchDeleting(true)
    try {
      await Promise.all([...selectedIds].map((id) => documentsApi.delete(id)))
      setDocs((prev) => prev.filter((d) => !selectedIds.has(d.id)))
      setSelectedIds(new Set())
    } catch {
      alert('Certains documents n\'ont pas pu être supprimés.')
    } finally {
      setBatchDeleting(false)
      setBatchDeleteOpen(false)
    }
  }

  const handleLaunchOcr = async (doc: DocumentOut) => {
    setEnqueuingId(doc.id)
    try {
      // Reuse the cached extraction if the document was already analysed.
      const existing = await ocrApi.getByDocument(doc.id)
      const extraction = existing ?? (await ocrApi.enqueue(doc.id))
      navigate(`/ocr/${extraction.id}`)
    } catch {
      alert('Impossible de lancer l\'analyse OCR.')
    } finally {
      setEnqueuingId(null)
    }
  }

  const fetchDocs = async () => {
    setLoading(true)
    setError('')
    setSelectedIds(new Set())
    try {
      const res = await documentsApi.list({
        q: q || undefined,
        category: category || undefined,
        owner_entity_type: ownerType || undefined,
        limit: 100,
      })
      setDocs(res.items)
    } catch {
      setError('Impossible de charger les documents.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDocs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, ownerType])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    fetchDocs()
  }

  const handleDownload = async (doc: DocumentOut) => {
    try {
      const res = await documentsApi.getSignedUrl(doc.id)
      window.open(res.url, '_blank')
    } catch {
      alert('Impossible de générer le lien de téléchargement.')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    setDeleting(true)
    try {
      await documentsApi.delete(deleteId)
      setDocs((prev) => prev.filter((d) => d.id !== deleteId))
    } catch {
      alert('Suppression impossible.')
    } finally {
      setDeleting(false)
      setDeleteId(null)
    }
  }

  return (
    <Box p={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Documents</Typography>
        <Stack direction="row" spacing={1}>
          {selectedIds.size > 0 && (
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteSweepIcon />}
              onClick={() => setBatchDeleteOpen(true)}
            >
              Supprimer la sélection ({selectedIds.size})
            </Button>
          )}
          <Button
            variant="contained"
            startIcon={<UploadFileIcon />}
            onClick={() => setUploadOpen(true)}
          >
            Télécharger
          </Button>
        </Stack>
      </Stack>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center">
          <Box component="form" onSubmit={handleSearch} sx={{ flexGrow: 1 }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Recherche plein texte…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton type="submit" size="small">
                      <SearchIcon />
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
          </Box>

          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Catégorie</InputLabel>
            <Select
              value={category}
              label="Catégorie"
              onChange={(e) => setCategory(e.target.value as DocumentCategory | '')}
            >
              {CATEGORIES.map((c) => (
                <MenuItem key={c.value} value={c.value}>
                  {c.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Type</InputLabel>
            <Select
              value={ownerType}
              label="Type"
              onChange={(e) => setOwnerType(e.target.value as OwnerEntityType | '')}
            >
              {OWNER_TYPES.map((o) => (
                <MenuItem key={o.value} value={o.value}>
                  {o.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {loading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox
                    indeterminate={someSelected}
                    checked={allSelected}
                    onChange={toggleSelectAll}
                    size="small"
                  />
                </TableCell>
                <TableCell>Nom du fichier</TableCell>
                <TableCell>Catégorie</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Taille</TableCell>
                <TableCell>Téléchargé le</TableCell>
                <TableCell>Statut</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {docs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} align="center">
                    Aucun document trouvé.
                  </TableCell>
                </TableRow>
              )}
              {docs.map((doc) => (
                <TableRow key={doc.id} hover selected={selectedIds.has(doc.id)}>
                  <TableCell padding="checkbox">
                    <Checkbox
                      size="small"
                      checked={selectedIds.has(doc.id)}
                      onChange={() => toggleSelect(doc.id)}
                    />
                  </TableCell>
                  <TableCell sx={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <Tooltip title={doc.filename}>
                      <span>{doc.filename}</span>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Chip label={categoryLabel(doc.category)} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>{ownerLabel(doc.owner_entity_type)}</TableCell>
                  <TableCell>{formatBytes(doc.size_bytes)}</TableCell>
                  <TableCell>{new Date(doc.uploaded_at).toLocaleDateString('fr-FR')}</TableCell>
                  <TableCell>
                    {doc.archived ? (
                      <Chip label="Archivé" size="small" color="default" />
                    ) : (
                      <Chip label="Actif" size="small" color="success" />
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Analyser (OCR)">
                      <span>
                        <IconButton
                          size="small"
                          color="primary"
                          onClick={() => handleLaunchOcr(doc)}
                          disabled={enqueuingId === doc.id}
                        >
                          {enqueuingId === doc.id ? (
                            <CircularProgress size={16} />
                          ) : (
                            <PageviewIcon fontSize="small" />
                          )}
                        </IconButton>
                      </span>
                    </Tooltip>
                    <Tooltip title="Télécharger">
                      <IconButton size="small" onClick={() => handleDownload(doc)}>
                        <DownloadIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Supprimer">
                      <IconButton size="small" color="error" onClick={() => setDeleteId(doc.id)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Upload dialog */}
      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={(doc) => {
          setDocs((prev) => [doc, ...prev])
        }}
      />

      {/* Delete confirm dialog */}
      <Dialog open={!!deleteId} onClose={() => setDeleteId(null)} maxWidth="xs" fullWidth>
        <DialogTitle>Confirmer la suppression</DialogTitle>
        <DialogContent>
          <Typography>Supprimer ce document ? Cette action est irréversible.</Typography>
          <Stack direction="row" spacing={2} justifyContent="flex-end" mt={2}>
            <Button onClick={() => setDeleteId(null)} disabled={deleting}>
              Annuler
            </Button>
            <Button variant="contained" color="error" onClick={handleDelete} disabled={deleting}>
              {deleting ? <CircularProgress size={18} /> : 'Supprimer'}
            </Button>
          </Stack>
        </DialogContent>
      </Dialog>

      {/* Batch delete confirm dialog */}
      <Dialog open={batchDeleteOpen} onClose={() => setBatchDeleteOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>Confirmer la suppression groupée</DialogTitle>
        <DialogContent>
          <Typography>
            Supprimer <strong>{selectedIds.size}</strong> document{selectedIds.size > 1 ? 's' : ''} sélectionné{selectedIds.size > 1 ? 's' : ''} ? Cette action est irréversible.
          </Typography>
          <Stack direction="row" spacing={2} justifyContent="flex-end" mt={2}>
            <Button onClick={() => setBatchDeleteOpen(false)} disabled={batchDeleting}>
              Annuler
            </Button>
            <Button
              variant="contained"
              color="error"
              onClick={handleBatchDelete}
              disabled={batchDeleting}
            >
              {batchDeleting ? <CircularProgress size={18} /> : `Supprimer ${selectedIds.size} document${selectedIds.size > 1 ? 's' : ''}`}
            </Button>
          </Stack>
        </DialogContent>
      </Dialog>
    </Box>
  )
}
