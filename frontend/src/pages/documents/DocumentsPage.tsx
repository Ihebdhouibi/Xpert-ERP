import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
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
import DeleteIcon from '@mui/icons-material/Delete'
import DownloadIcon from '@mui/icons-material/Download'
import SearchIcon from '@mui/icons-material/Search'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import type { DocumentCategory, DocumentOut, OwnerEntityType } from '../../lib/documentsApi'
import { documentsApi } from '../../lib/documentsApi'

const CATEGORIES: { value: DocumentCategory | ''; label: string }[] = [
  { value: '', label: 'Toutes les catégories' },
  { value: 'registration_card', label: 'Carte grise' },
  { value: 'national_id', label: 'Pièce d\'identité' },
  { value: 'insurance', label: 'Assurance' },
  { value: 'accident_photo', label: 'Photo accident' },
  { value: 'repair_attachment', label: 'Annexe OR' },
  { value: 'invoice', label: 'Facture' },
  { value: 'supplier_invoice', label: 'Facture fournisseur' },
  { value: 'generic', label: 'Générique' },
]

const OWNER_TYPES: { value: OwnerEntityType | ''; label: string }[] = [
  { value: '', label: 'Tous les types' },
  { value: 'customer', label: 'Client' },
  { value: 'vehicle', label: 'Véhicule' },
  { value: 'repair_order', label: 'Ordre de réparation' },
  { value: 'invoice', label: 'Facture' },
  { value: 'supplier_invoice', label: 'Facture fournisseur' },
  { value: 'generic', label: 'Générique' },
]

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / 1024 / 1024).toFixed(1)} Mo`
}

function categoryLabel(cat: DocumentCategory): string {
  return CATEGORIES.find((c) => c.value === cat)?.label ?? cat
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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    try {
      const doc = await documentsApi.upload(
        file,
        category,
        ownerType,
        ownerId ? Number(ownerId) : undefined,
      )
      onUploaded(doc)
      onClose()
    } catch {
      setError('Erreur lors du téléchargement. Vérifiez le fichier et réessayez.')
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
              onChange={(e) => setCategory(e.target.value as DocumentCategory)}
            >
              {CATEGORIES.filter((c) => c.value !== '').map((c) => (
                <MenuItem key={c.value} value={c.value}>
                  {c.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth size="small">
            <InputLabel>Type propriétaire</InputLabel>
            <Select
              value={ownerType}
              label="Type propriétaire"
              onChange={(e) => setOwnerType(e.target.value as OwnerEntityType)}
            >
              {OWNER_TYPES.filter((o) => o.value !== '').map((o) => (
                <MenuItem key={o.value} value={o.value}>
                  {o.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            label="ID propriétaire (optionnel)"
            size="small"
            value={ownerId}
            onChange={(e) => setOwnerId(e.target.value)}
          />

          <Button
            variant="contained"
            disabled={!file || loading}
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

  const fetchDocs = async () => {
    setLoading(true)
    setError('')
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
        <Button
          variant="contained"
          startIcon={<UploadFileIcon />}
          onClick={() => setUploadOpen(true)}
        >
          Télécharger
        </Button>
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
                  <TableCell colSpan={7} align="center">
                    Aucun document trouvé.
                  </TableCell>
                </TableRow>
              )}
              {docs.map((doc) => (
                <TableRow key={doc.id} hover>
                  <TableCell sx={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <Tooltip title={doc.filename}>
                      <span>{doc.filename}</span>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Chip label={categoryLabel(doc.category)} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>{doc.owner_entity_type}</TableCell>
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
    </Box>
  )
}
