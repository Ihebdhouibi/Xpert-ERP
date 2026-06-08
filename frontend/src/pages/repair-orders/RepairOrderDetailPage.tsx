import { useState, useRef } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Grid,
  IconButton,
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
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import DeleteRoundedIcon from '@mui/icons-material/DeleteRounded'
import SendRoundedIcon from '@mui/icons-material/SendRounded'
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded'
import AddPhotoAlternateRoundedIcon from '@mui/icons-material/AddPhotoAlternateRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import BrokenImageRoundedIcon from '@mui/icons-material/BrokenImageRounded'
import { PermissionGate } from '../../components/auth/PermissionGate'
import {
  repairOrderApi,
  STATUS_LABELS,
  ALLOWED_TRANSITIONS,
  type ROStatus,
  type RepairOrderDetail,
  type Comment,
  type ROPhotoSummary,
} from '../../lib/repairOrderApi'
import { customerApi } from '../../lib/customerApi'
import { vehiclesApi } from '../../lib/vehiclesApi'
import { quotationApi } from '../../lib/quotationApi'
import { invoiceApi } from '../../lib/invoiceApi'
import { partsApi, type PartSummary } from '../../lib/partsApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

// ─── helpers ────────────────────────────────────────────────────────────────

const PRIORITY_LABEL: Record<string, string> = {
  low: 'Basse', normal: 'Normale', high: 'Haute', urgent: 'Urgente',
}
const PRIORITY_COLOR: Record<string, string> = {
  low: '#64748B', normal: '#2563EB', high: '#F59E0B', urgent: '#EF4444',
}

const SECTION_LABEL_SX = {
  textTransform: 'uppercase' as const,
  letterSpacing: '0.08em',
  display: 'block',
  mb: 2,
}

function InfoField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" display="block" mb={0.25}>
        {label}
      </Typography>
      {typeof value === 'string' || typeof value === 'number' ? (
        <Typography variant="body2" fontWeight={500}>{value}</Typography>
      ) : (
        value
      )}
    </Box>
  )
}

// Status accent colors — same palette as Kanban for consistency
const STATUS_ACCENT_COLOR: Record<string, string> = {
  created:         '#94A3B8',
  diagnosis:       '#3B82F6',
  in_repair:       '#F59E0B',
  finished:        '#10B981',
  delivered:       '#6366F1',
  paused_parts:    '#EF4444',
  paused_approval: '#F97316',
}

// ─── Status transition ───────────────────────────────────────────────────────
// Each allowed transition is a quiet pill — flat bg, colored left border,
// muted text. Selected state reveals the confirm step inline.
// Zero competing colors at rest — only the selected pill activates.

function StatusTransitionPanel({
  ro,
  onTransitioned,
}: {
  ro: RepairOrderDetail
  onTransitioned: () => void
}) {
  const { success, error: toastError } = useToast()
  const [selectedStatus, setSelectedStatus] = useState<ROStatus | null>(null)
  const [reason, setReason] = useState('')
  const allowed = ALLOWED_TRANSITIONS[ro.status]

  const mutation = useMutation({
    mutationFn: () =>
      repairOrderApi.transition(ro.id, {
        new_status: selectedStatus!,
        reason: reason || null,
      }),
    onSuccess: () => {
      success(`Statut → ${STATUS_LABELS[selectedStatus!]}`)
      setSelectedStatus(null)
      setReason('')
      onTransitioned()
    },
    onError: () => toastError('Transition invalide ou accès refusé.'),
  })

  if (allowed.length === 0) return null

  return (
    <Box>
      <Typography variant="caption" fontWeight={600} color="text.secondary" display="block" mb={1.5}>
        Changer le statut
      </Typography>
      <Stack spacing={0.75}>
        {allowed.map(s => {
          const accent = STATUS_ACCENT_COLOR[s] ?? '#94A3B8'
          const isSelected = selectedStatus === s
          return (
            <Box key={s}>
              {/* Quiet pill — left accent border, flat background */}
              <Box
                onClick={() => setSelectedStatus(isSelected ? null : s)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.25,
                  px: 1.5,
                  py: 1,
                  borderRadius: 1.5,
                  border: '1px solid',
                  borderLeft: `3px solid ${accent}`,
                  borderColor: isSelected ? accent : '#E2E8F0',
                  borderLeftColor: accent,
                  bgcolor: isSelected ? `${accent}10` : '#FAFAFA',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  '&:hover': {
                    borderColor: accent,
                    bgcolor: `${accent}08`,
                  },
                }}
              >
                <Box
                  sx={{
                    width: 8, height: 8,
                    borderRadius: '50%',
                    bgcolor: accent,
                    flexShrink: 0,
                  }}
                />
                <Typography
                  variant="body2"
                  fontWeight={isSelected ? 600 : 500}
                  color={isSelected ? 'text.primary' : 'text.secondary'}
                  flex={1}
                >
                  {STATUS_LABELS[s]}
                </Typography>
                <ArrowForwardRoundedIcon
                  sx={{
                    fontSize: 14,
                    color: isSelected ? accent : '#CBD5E1',
                    transition: 'color 0.15s',
                  }}
                />
              </Box>

              {/* Inline confirm step — expands below the selected pill */}
              {isSelected && (
                <Box
                  sx={{
                    mt: 0.75,
                    ml: 0.5,
                    pl: 1.5,
                    borderLeft: `2px solid ${accent}40`,
                  }}
                >
                  <TextField
                    size="small"
                    fullWidth
                    placeholder="Motif (optionnel)"
                    value={reason}
                    onChange={e => setReason(e.target.value)}
                    sx={{ mb: 1 }}
                  />
                  <Button
                    variant="contained"
                    fullWidth
                    size="small"
                    disabled={mutation.isPending}
                    onClick={() => mutation.mutate()}
                    sx={{
                      background: accent,
                      '&:hover': { background: accent, opacity: 0.9 },
                      fontWeight: 600,
                    }}
                  >
                    {mutation.isPending ? 'En cours…' : `Confirmer → ${STATUS_LABELS[s]}`}
                  </Button>
                </Box>
              )}
            </Box>
          )
        })}
      </Stack>
    </Box>
  )
}

// ─── Status timeline ─────────────────────────────────────────────────────────

function StatusTimeline({ events }: { events: RepairOrderDetail['status_events'] }) {
  if (events.length === 0) {
    return <Typography variant="body2" color="text.secondary">Aucun historique.</Typography>
  }
  return (
    <Stack spacing={0}>
      {events.map((evt, i) => (
        <Stack key={evt.id} direction="row" spacing={1.5} sx={{ position: 'relative', pb: i < events.length - 1 ? 2 : 0 }}>
          {i < events.length - 1 && (
            <Box sx={{ position: 'absolute', left: 6, top: 16, width: 2, bottom: 0, bgcolor: '#E2E8F0', zIndex: 0 }} />
          )}
          <Box
            sx={{
              width: 14, height: 14, borderRadius: '50%',
              bgcolor: i === 0 ? 'primary.main' : '#94A3B8',
              flexShrink: 0, mt: 0.3, zIndex: 1,
              border: '2px solid white',
              boxShadow: i === 0 ? '0 0 0 2px #2563EB' : '0 0 0 2px #94A3B8',
            }}
          />
          <Box>
            <Stack direction="row" alignItems="center" spacing={0.5} flexWrap="wrap">
              {evt.old_status && (
                <>
                  <Typography variant="caption" color="text.secondary">
                    {STATUS_LABELS[evt.old_status as ROStatus] ?? evt.old_status}
                  </Typography>
                  <ArrowForwardRoundedIcon sx={{ fontSize: 11, color: 'text.disabled' }} />
                </>
              )}
              <Typography variant="caption" fontWeight={700} color={i === 0 ? 'primary.main' : 'text.primary'}>
                {STATUS_LABELS[evt.new_status as ROStatus] ?? evt.new_status}
              </Typography>
            </Stack>
            <Typography variant="caption" color="text.disabled" display="block">
              {new Date(evt.occurred_at).toLocaleString('fr-FR')}
            </Typography>
          </Box>
        </Stack>
      ))}
    </Stack>
  )
}

// ─── Comments ────────────────────────────────────────────────────────────────

function CommentsPanel({ publicId }: { publicId: string }) {
  const queryClient = useQueryClient()
  const { error: toastError } = useToast()
  const [newBody, setNewBody] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editBody, setEditBody] = useState('')

  const { data } = useQuery({
    queryKey: ['comments', publicId],
    queryFn: () => repairOrderApi.listComments(publicId),
  })

  const createMutation = useMutation({
    mutationFn: () => repairOrderApi.createComment(publicId, newBody),
    onSuccess: () => {
      setNewBody('')
      queryClient.invalidateQueries({ queryKey: ['comments', publicId] })
    },
    onError: () => toastError("Impossible d'ajouter le commentaire."),
  })

  const updateMutation = useMutation({
    mutationFn: (comment: Comment) =>
      repairOrderApi.updateComment(publicId, comment.id, editBody),
    onSuccess: () => {
      setEditingId(null)
      setEditBody('')
      queryClient.invalidateQueries({ queryKey: ['comments', publicId] })
    },
    onError: () => toastError('Impossible de modifier le commentaire.'),
  })

  const deleteMutation = useMutation({
    mutationFn: (commentId: number) => repairOrderApi.deleteComment(publicId, commentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['comments', publicId] }),
    onError: () => toastError('Impossible de supprimer le commentaire.'),
  })

  return (
    <Box>
      <Stack spacing={1.5} mb={2} sx={{ maxHeight: 400, overflowY: 'auto' }}>
        {data?.items.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            Aucun commentaire pour l'instant.
          </Typography>
        )}
        {data?.items.map(comment => (
          <Box
            key={comment.id}
            sx={{ p: 1.5, bgcolor: '#F8FAFC', borderRadius: 1.5, border: '1px solid #E2E8F0' }}
          >
            {editingId === comment.id ? (
              <Stack spacing={1}>
                <TextField size="small" multiline fullWidth value={editBody} onChange={e => setEditBody(e.target.value)} />
                <Stack direction="row" spacing={1} justifyContent="flex-end">
                  <Button size="small" variant="outlined" onClick={() => setEditingId(null)}>Annuler</Button>
                  <Button
                    size="small"
                    variant="contained"
                    disabled={updateMutation.isPending || !editBody.trim()}
                    onClick={() => updateMutation.mutate(comment)}
                  >
                    Sauvegarder
                  </Button>
                </Stack>
              </Stack>
            ) : (
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
                <Box flex={1}>
                  <Typography variant="body2" whiteSpace="pre-wrap">{comment.body}</Typography>
                  <Typography variant="caption" color="text.disabled">
                    {new Date(comment.created_at).toLocaleString('fr-FR')}
                    {comment.created_at !== comment.updated_at && ' · modifié'}
                  </Typography>
                </Box>
                <Stack direction="row" flexShrink={0}>
                  <Tooltip title="Modifier">
                    <IconButton
                      size="small"
                      onClick={() => { setEditingId(comment.id); setEditBody(comment.body) }}
                    >
                      <EditRoundedIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Supprimer">
                    <IconButton
                      size="small"
                      color="error"
                      disabled={deleteMutation.isPending}
                      onClick={() => deleteMutation.mutate(comment.id)}
                    >
                      <DeleteRoundedIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </Stack>
            )}
          </Box>
        ))}
      </Stack>

      <Stack direction="row" spacing={1} alignItems="flex-end">
        <TextField
          size="small"
          multiline
          fullWidth
          placeholder="Ajouter un commentaire… (Ctrl+Entrée pour envoyer)"
          value={newBody}
          onChange={e => setNewBody(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && newBody.trim()) {
              createMutation.mutate()
            }
          }}
        />
        <Button
          variant="contained"
          size="small"
          startIcon={<SendRoundedIcon />}
          disabled={createMutation.isPending || !newBody.trim()}
          onClick={() => createMutation.mutate()}
          sx={{ height: 40, flexShrink: 0, textTransform: 'none', fontWeight: 700 }}
        >
          Envoyer
        </Button>
      </Stack>
    </Box>
  )
}

// ─── Photos ──────────────────────────────────────────────────────────────────

function PhotosPanel({ publicId }: { publicId: string }) {
  const queryClient = useQueryClient()
  const { error: toastError } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [brokenIds, setBrokenIds] = useState<Set<number>>(new Set())

  const { data } = useQuery({
    queryKey: ['photos', publicId],
    queryFn: () => repairOrderApi.listPhotos(publicId),
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => repairOrderApi.uploadPhoto(publicId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['photos', publicId] }),
    onError: () => toastError("Impossible d'envoyer la photo."),
  })

  function handleFiles(files: FileList | null) {
    if (!files) return
    Array.from(files).forEach(f => uploadMutation.mutate(f))
  }

  const photos: ROPhotoSummary[] = data?.items ?? []

  return (
    <Box>
      {photos.length === 0 && !uploadMutation.isPending && (
        <Typography variant="body2" color="text.secondary" mb={2}>
          Aucune photo pour l'instant.
        </Typography>
      )}

      {photos.length > 0 && (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
            gap: 1,
            mb: 2,
          }}
        >
          {photos.map(photo => (
            <Box
              key={photo.id}
              component="a"
              href={photo.url}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                display: 'block',
                aspectRatio: '1',
                borderRadius: 1,
                overflow: 'hidden',
                bgcolor: '#F1F5F9',
                border: '1px solid #E2E8F0',
                '&:hover': { opacity: 0.85 },
              }}
            >
              {brokenIds.has(photo.id) ? (
                <Box
                  sx={{
                    width: '100%',
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <BrokenImageRoundedIcon sx={{ color: '#CBD5E1', fontSize: 32 }} />
                </Box>
              ) : (
                <img
                  src={photo.url}
                  alt={photo.filename}
                  onError={() => setBrokenIds(prev => new Set(prev).add(photo.id))}
                  style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                />
              )}
            </Box>
          ))}
        </Box>
      )}

      <PermissionGate permission="repair_order.update">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic"
          multiple
          style={{ display: 'none' }}
          onChange={e => handleFiles(e.target.files)}
        />
        <Button
          variant="outlined"
          size="small"
          startIcon={<AddPhotoAlternateRoundedIcon />}
          disabled={uploadMutation.isPending}
          onClick={() => fileInputRef.current?.click()}
          sx={{ textTransform: 'none', fontWeight: 600 }}
        >
          {uploadMutation.isPending ? 'Envoi…' : 'Ajouter des photos'}
        </Button>
      </PermissionGate>
    </Box>
  )
}

// ─── Main page ───────────────────────────────────────────────────────────────

export function RepairOrderDetailPage() {
  const { publicId = '' } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)

  // Add-labor inline form state
  const [showAddLabor, setShowAddLabor] = useState(false)
  const [laborType, setLaborType] = useState('')
  const [laborMinutes, setLaborMinutes] = useState('')
  const [laborRate, setLaborRate] = useState('')

  // Add-part inline form state
  const [showAddPart, setShowAddPart] = useState(false)
  const [partSearch, setPartSearch] = useState('')
  const [selectedPart, setSelectedPart] = useState<PartSummary | null>(null)
  const [partQty, setPartQty] = useState('')

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['repair-order', publicId],
    queryFn: () => repairOrderApi.get(publicId),
    enabled: !!publicId,
  })

  const roForQueries = data

  const { data: customer } = useQuery({
    queryKey: ['customer-by-int-id', roForQueries?.customer_id],
    queryFn: () => customerApi.getByIntId(roForQueries!.customer_id),
    enabled: !!roForQueries?.customer_id,
    staleTime: 5 * 60 * 1000,
  })

  const { data: vehicle } = useQuery({
    queryKey: ['vehicle', roForQueries?.vehicle_id],
    queryFn: () => vehiclesApi.get(roForQueries!.vehicle_id!),
    enabled: !!roForQueries?.vehicle_id,
    staleTime: 5 * 60 * 1000,
  })

  const { data: partsResults } = useQuery({
    queryKey: ['parts-search', partSearch],
    queryFn: () => partsApi.list({ search: partSearch || undefined, page_size: 30, status: 'active' }),
    enabled: showAddPart,
    staleTime: 30_000,
  })

  const createDevisMutation = useMutation({
    mutationFn: () => quotationApi.fromRepairOrder(publicId),
    onSuccess: (quotation) => {
      success('Devis créé avec succès.')
      navigate(`/quotations/${quotation.public_id}`)
    },
    onError: () => toastError('Impossible de créer le devis.'),
  })

  const createInvoiceMutation = useMutation({
    mutationFn: () => invoiceApi.fromRepairOrder(publicId),
    onSuccess: (invoice) => {
      success('Facture créée avec succès.')
      navigate(`/invoices/${invoice.public_id}`)
    },
    onError: () => toastError('Impossible de créer la facture.'),
  })

  const addLaborMutation = useMutation({
    mutationFn: () => repairOrderApi.addLaborLine(publicId, {
      labor_type: laborType,
      duration_minutes: parseInt(laborMinutes, 10),
      rate_minor: Math.round(parseFloat(laborRate) * 100),
    }),
    onSuccess: () => {
      success('Ligne de main d\'œuvre ajoutée.')
      setShowAddLabor(false)
      setLaborType(''); setLaborMinutes(''); setLaborRate('')
      refetch()
    },
    onError: () => toastError('Impossible d\'ajouter la ligne.'),
  })

  const addPartMutation = useMutation({
    mutationFn: () => repairOrderApi.addPartLine(publicId, {
      part_name: selectedPart!.name,
      quantity: parseInt(partQty, 10),
      unit_cost_minor: selectedPart!.selling_price_minor,
    }),
    onSuccess: () => {
      success('Pièce ajoutée.')
      setShowAddPart(false)
      setSelectedPart(null); setPartSearch(''); setPartQty('')
      refetch()
    },
    onError: () => toastError('Impossible d\'ajouter la pièce.'),
  })

  const handleDelete = async () => {
    try {
      await repairOrderApi.remove(publicId)
      await queryClient.invalidateQueries({ queryKey: ['repair-orders'] })
      navigate('/repair-orders', { replace: true })
    } catch {
      toastError('Erreur lors de la suppression.')
      setConfirmDelete(false)
    }
  }

  const handleDownloadPdf = async () => {
    setPdfLoading(true)
    try {
      const { url } = await repairOrderApi.getPdfUrl(publicId)
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch {
      toastError('Erreur lors de la génération du PDF.')
    } finally {
      setPdfLoading(false)
    }
  }

  if (isLoading) {
    return <LoadingScreen message="Chargement de l'ordre de réparation…" />
  }
  if (isError || !data) {
    return (
      <Box>
        <Alert severity="error" sx={{ mb: 2 }}>Impossible de charger cet ordre de réparation.</Alert>
        <Button variant="outlined" onClick={() => navigate('/repair-orders')}>
          ← Retour à la liste
        </Button>
      </Box>
    )
  }

  const ro = data as RepairOrderDetail
  const currency = ro.estimated_cost_currency ?? 'EUR'
  const laborTotal = ro.labor_lines.reduce((s, l) => s + (l.amount_minor ?? 0), 0)
  const partsTotal = ro.part_lines.reduce((s, l) => s + (l.amount_minor ?? 0), 0)

  return (
    <Box>
      <PageHeader
        title={ro.description || 'Ordre de réparation'}
        subtitle={`#${String(ro.id).slice(-8).toUpperCase()} · Créé le ${new Date(ro.created_at).toLocaleDateString('fr-FR')}`}
        breadcrumbs={[
          { label: 'Ordres de réparation', href: '/repair-orders' },
          { label: ro.description || 'Détail' },
        ]}
        actions={
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <StatusChip status={ro.status} label={STATUS_LABELS[ro.status]} size="medium" />
            <PermissionGate permission="repair_order.read">
              <Button
                size="small"
                variant="outlined"
                startIcon={<PictureAsPdfRoundedIcon />}
                onClick={handleDownloadPdf}
                disabled={pdfLoading}
                sx={{ textTransform: 'none' }}
              >
                {pdfLoading ? 'Génération…' : 'PDF'}
              </Button>
            </PermissionGate>
            <PermissionGate permission="repair_order.update">
              <Button
                size="small"
                variant="outlined"
                startIcon={<EditRoundedIcon />}
                component={RouterLink}
                to={`/repair-orders/${ro.id}/edit`}
                sx={{ textTransform: 'none' }}
              >
                Modifier
              </Button>
            </PermissionGate>
            <PermissionGate permission="repair_order.delete">
              <Button
                size="small"
                color="error"
                variant="outlined"
                startIcon={<DeleteRoundedIcon />}
                onClick={() => setConfirmDelete(true)}
                sx={{ textTransform: 'none' }}
              >
                Supprimer
              </Button>
            </PermissionGate>
          </Stack>
        }
      />

      <Grid container spacing={3}>
        {/* ── LEFT COLUMN ─────────────────────────────────────────────── */}
        <Grid item xs={12} md={8}>

          {/* Key info */}
          <Card sx={{ mb: 3 }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="caption" fontWeight={700} color="text.secondary" sx={SECTION_LABEL_SX}>
                Informations
              </Typography>
              <Grid container spacing={2.5}>
                <Grid item xs={6} sm={3}>
                  <InfoField
                    label="Client"
                    value={
                      customer ? (
                        <Typography
                          variant="body2"
                          fontWeight={500}
                          component={RouterLink}
                          to={`/customers/${customer.id}`}
                          sx={{ color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}
                        >
                          {customer.full_name}
                        </Typography>
                      ) : (ro.customer_name ?? `#${ro.customer_id}`)
                    }
                  />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <InfoField
                    label="Véhicule"
                    value={
                      vehicle ? (
                        <Typography
                          variant="body2"
                          fontWeight={500}
                          component={RouterLink}
                          to={`/vehicles/${vehicle.id}`}
                          sx={{ color: 'primary.main', textDecoration: 'none', fontFamily: 'monospace', '&:hover': { textDecoration: 'underline' } }}
                        >
                          {[vehicle.registration, `${vehicle.make} ${vehicle.model}`].filter(Boolean).join(' — ')}
                        </Typography>
                      ) : ro.vehicle_id ? `#${ro.vehicle_id}` : '—'
                    }
                  />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <InfoField
                    label="Priorité"
                    value={
                      ro.priority ? (
                        <Typography
                          variant="body2"
                          fontWeight={700}
                          sx={{ color: PRIORITY_COLOR[ro.priority] ?? 'text.primary' }}
                        >
                          {PRIORITY_LABEL[ro.priority] ?? ro.priority}
                        </Typography>
                      ) : '—'
                    }
                  />
                </Grid>
                <Grid item xs={6} sm={3}>
                  <InfoField label="Version" value={`v${ro.version}`} />
                </Grid>
                <Grid item xs={6} sm={4}>
                  <InfoField
                    label="Coût estimé"
                    value={
                      ro.estimated_cost_minor != null
                        ? <Typography variant="body2" fontWeight={600}>{formatMinor(ro.estimated_cost_minor, currency)}</Typography>
                        : '—'
                    }
                  />
                </Grid>
                <Grid item xs={6} sm={4}>
                  <InfoField
                    label="Coût réel"
                    value={
                      ro.actual_cost_minor != null
                        ? <Typography variant="body2" fontWeight={700} color="primary.main">{formatMinor(ro.actual_cost_minor, currency)}</Typography>
                        : '—'
                    }
                  />
                </Grid>
              </Grid>

              {ro.notes && (
                <>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={1} sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Notes
                  </Typography>
                  <Typography variant="body2" color="text.secondary" whiteSpace="pre-wrap">
                    {ro.notes}
                  </Typography>
                </>
              )}
            </CardContent>
          </Card>

          {/* Labor lines */}
          <Card sx={{ mb: 3 }}>
            <CardContent sx={{ p: 0 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 3, py: 2 }}>
                <Typography variant="subtitle2" fontWeight={700}>
                  Main d'œuvre
                  <Typography component="span" variant="caption" color="text.secondary" ml={1} fontWeight={400}>
                    {ro.labor_lines.length} ligne{ro.labor_lines.length !== 1 ? 's' : ''}
                  </Typography>
                </Typography>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2" fontWeight={700} color={laborTotal > 0 ? 'text.primary' : 'text.disabled'}>
                    {formatMinor(laborTotal, currency)}
                  </Typography>
                  {(ro.status === 'paused_approval' || ro.status === 'in_repair') && (
                    <PermissionGate permission="repair_order.update">
                      <Button size="small" variant="outlined" startIcon={<AddRoundedIcon />} onClick={() => setShowAddLabor(v => !v)} sx={{ textTransform: 'none', fontWeight: 600, fontSize: 12 }}>
                        Ajouter
                      </Button>
                    </PermissionGate>
                  )}
                </Stack>
              </Stack>
              {showAddLabor && (
                <Box sx={{ px: 3, pb: 2 }}>
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} mb={1}>
                    <TextField size="small" label="Désignation" value={laborType} onChange={e => setLaborType(e.target.value)} sx={{ flex: 2 }} />
                    <TextField size="small" label="Durée (min)" type="number" value={laborMinutes} onChange={e => setLaborMinutes(e.target.value)} sx={{ flex: 1 }} />
                    <TextField size="small" label="Prix (€)" type="number" value={laborRate} onChange={e => setLaborRate(e.target.value)} inputProps={{ min: 0, step: 0.01 }} sx={{ flex: 1 }} />
                  </Stack>
                  <Stack direction="row" spacing={1}>
                    <Button size="small" onClick={() => setShowAddLabor(false)} sx={{ textTransform: 'none' }}>Annuler</Button>
                    <Button
                      size="small" variant="contained"
                      disabled={addLaborMutation.isPending || !laborType.trim() || !laborMinutes || !laborRate}
                      onClick={() => addLaborMutation.mutate()}
                      sx={{ textTransform: 'none', fontWeight: 700 }}
                    >
                      {addLaborMutation.isPending ? 'Enregistrement…' : 'Ajouter'}
                    </Button>
                  </Stack>
                </Box>
              )}
              <Divider />
              {ro.labor_lines.length === 0 ? (
                <Box sx={{ px: 3, py: 4, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">Aucune ligne de main d'œuvre.</Typography>
                </Box>
              ) : (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Désignation</TableCell>
                      <TableCell align="right">Durée</TableCell>
                      <TableCell align="right">Prix</TableCell>
                      <TableCell align="right">Montant</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {ro.labor_lines.map(line => (
                      <TableRow key={line.id}>
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>{line.labor_type}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2">{line.duration_minutes} min</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2">{formatMinor(line.rate_minor, currency)}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontWeight={600}>{formatMinor(line.amount_minor, currency)}</Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                    <TableRow sx={{ bgcolor: '#F8FAFC' }}>
                      <TableCell colSpan={3}>
                        <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          Total MO
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" fontWeight={700}>{formatMinor(laborTotal, currency)}</Typography>
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Parts lines */}
          <Card sx={{ mb: 3 }}>
            <CardContent sx={{ p: 0 }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 3, py: 2 }}>
                <Typography variant="subtitle2" fontWeight={700}>
                  Pièces
                  <Typography component="span" variant="caption" color="text.secondary" ml={1} fontWeight={400}>
                    {ro.part_lines.length} ligne{ro.part_lines.length !== 1 ? 's' : ''}
                  </Typography>
                </Typography>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2" fontWeight={700} color={partsTotal > 0 ? 'text.primary' : 'text.disabled'}>
                    {formatMinor(partsTotal, currency)}
                  </Typography>
                  {(ro.status === 'paused_parts' || ro.status === 'in_repair') && (
                    <PermissionGate permission="repair_order.update">
                      <Button size="small" variant="outlined" startIcon={<AddRoundedIcon />} onClick={() => setShowAddPart(v => !v)} sx={{ textTransform: 'none', fontWeight: 600, fontSize: 12 }}>
                        Ajouter
                      </Button>
                    </PermissionGate>
                  )}
                </Stack>
              </Stack>
              {showAddPart && (
                <Box sx={{ px: 3, pb: 2 }}>
                  <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} mb={1} alignItems="flex-start">
                    <Autocomplete
                      sx={{ flex: 2 }}
                      size="small"
                      options={partsResults?.items ?? []}
                      getOptionLabel={(o) => `${o.sku_code} — ${o.name}`}
                      filterOptions={(x) => x}
                      inputValue={partSearch}
                      onInputChange={(_, val) => { setPartSearch(val); setSelectedPart(null) }}
                      value={selectedPart}
                      onChange={(_, val) => { setSelectedPart(val); setPartQty('1') }}
                      noOptionsText={partSearch.length < 1 ? 'Tapez pour rechercher…' : 'Aucun résultat'}
                      renderOption={(props, option) => (
                        <Box component="li" {...props} key={option.int_id}>
                          <Stack direction="row" justifyContent="space-between" width="100%" spacing={1}>
                            <Typography variant="body2">{option.sku_code} — {option.name}</Typography>
                            <Typography variant="caption" color={option.stock_on_hand > 0 ? 'success.main' : 'error.main'}>
                              Stock : {option.stock_on_hand}
                            </Typography>
                          </Stack>
                        </Box>
                      )}
                      renderInput={(params) => (
                        <TextField {...params} label="Rechercher une pièce" placeholder="SKU ou nom…" />
                      )}
                    />
                    <TextField
                      size="small"
                      label="Quantité"
                      type="number"
                      value={partQty}
                      onChange={e => setPartQty(e.target.value)}
                      inputProps={{ min: 1, max: selectedPart?.stock_on_hand ?? undefined, step: 1 }}
                      sx={{ flex: 0, width: 110 }}
                      helperText={selectedPart ? `Max : ${selectedPart.stock_on_hand}` : ''}
                    />
                    <TextField
                      size="small"
                      label="Prix unit. (€)"
                      value={selectedPart ? (selectedPart.selling_price_minor / 100).toFixed(2) : ''}
                      InputProps={{ readOnly: true }}
                      sx={{ flex: 0, width: 120 }}
                    />
                  </Stack>
                  <Stack direction="row" spacing={1}>
                    <Button size="small" onClick={() => { setShowAddPart(false); setSelectedPart(null); setPartSearch(''); setPartQty('') }} sx={{ textTransform: 'none' }}>Annuler</Button>
                    <Button
                      size="small" variant="contained"
                      disabled={
                        addPartMutation.isPending ||
                        !selectedPart ||
                        !partQty ||
                        parseInt(partQty, 10) < 1 ||
                        parseInt(partQty, 10) > (selectedPart?.stock_on_hand ?? 0)
                      }
                      onClick={() => addPartMutation.mutate()}
                      sx={{ textTransform: 'none', fontWeight: 700 }}
                    >
                      {addPartMutation.isPending ? 'Enregistrement…' : 'Ajouter'}
                    </Button>
                  </Stack>
                </Box>
              )}
              <Divider />
              {ro.part_lines.length === 0 ? (
                <Box sx={{ px: 3, py: 4, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">Aucune pièce.</Typography>
                </Box>
              ) : (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Pièce</TableCell>
                      <TableCell align="right">Qté</TableCell>
                      <TableCell align="right">Prix unit.</TableCell>
                      <TableCell align="right">Montant</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {ro.part_lines.map(line => (
                      <TableRow key={line.id}>
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>{line.part_name}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2">{line.quantity}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2">{formatMinor(line.unit_cost_minor, currency)}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontWeight={600}>{formatMinor(line.amount_minor, currency)}</Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                    <TableRow sx={{ bgcolor: '#F8FAFC' }}>
                      <TableCell colSpan={3}>
                        <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          Total Pièces
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" fontWeight={700}>{formatMinor(partsTotal, currency)}</Typography>
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Grand total banner */}
          {(laborTotal > 0 || partsTotal > 0) && (
            <Card sx={{ mb: 3, bgcolor: '#0F172A', color: 'white' }}>
              <CardContent sx={{ py: 2, px: 3 }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="subtitle2" fontWeight={700} color="rgba(255,255,255,0.7)">
                    Total estimé (MO + Pièces)
                  </Typography>
                  <Typography variant="h6" fontWeight={800} color="white">
                    {formatMinor(laborTotal + partsTotal, currency)}
                  </Typography>
                </Stack>
              </CardContent>
            </Card>
          )}

          {/* Comments */}
          <Card>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="subtitle2" fontWeight={700} mb={2}>
                Commentaires
              </Typography>
              <CommentsPanel publicId={publicId} />
            </CardContent>
          </Card>

          {/* Photos */}
          <Card>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="subtitle2" fontWeight={700} mb={2}>
                Photos
              </Typography>
              <PhotosPanel publicId={publicId} />
            </CardContent>
          </Card>
        </Grid>

        {/* ── RIGHT COLUMN ────────────────────────────────────────────── */}
        <Grid item xs={12} md={4}>
          <Stack spacing={3} sx={{ position: { md: 'sticky' }, top: { md: 24 } }}>

            {/* Status transition */}
            <PermissionGate permission="repair_order.transition">
              <Card>
                <CardContent sx={{ p: 2.5 }}>
                  <StatusTransitionPanel ro={ro} onTransitioned={() => refetch()} />
                </CardContent>
              </Card>
            </PermissionGate>

            {/* Create Devis (diagnosis only) */}
            {ro.status === 'diagnosis' && (
              <PermissionGate permission="quotation.create">
                <Card>
                  <CardContent sx={{ p: 2.5 }}>
                    <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={1.5} sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      Actions
                    </Typography>
                    <Button
                      variant="contained"
                      fullWidth
                      startIcon={<DescriptionRoundedIcon />}
                      disabled={createDevisMutation.isPending}
                      onClick={() => createDevisMutation.mutate()}
                      sx={{ textTransform: 'none', fontWeight: 700 }}
                    >
                      {createDevisMutation.isPending ? 'Création…' : 'Créer un devis'}
                    </Button>
                  </CardContent>
                </Card>
              </PermissionGate>
            )}

            {/* Create Invoice (finished or delivered) */}
            {(ro.status === 'finished' || ro.status === 'delivered') && (
              <PermissionGate permission="invoice.create">
                <Card>
                  <CardContent sx={{ p: 2.5 }}>
                    <Typography variant="caption" fontWeight={700} color="text.secondary" display="block" mb={1.5} sx={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      Actions
                    </Typography>
                    <Button
                      variant="contained"
                      color="success"
                      fullWidth
                      startIcon={<ReceiptRoundedIcon />}
                      disabled={createInvoiceMutation.isPending}
                      onClick={() => createInvoiceMutation.mutate()}
                      sx={{ textTransform: 'none', fontWeight: 700 }}
                    >
                      {createInvoiceMutation.isPending ? 'Création…' : 'Créer une facture'}
                    </Button>
                  </CardContent>
                </Card>
              </PermissionGate>
            )}

            {/* Status timeline */}
            <Card>
              <CardContent sx={{ p: 2.5 }}>
                <Typography variant="caption" fontWeight={700} color="text.secondary" sx={SECTION_LABEL_SX}>
                  Historique des statuts
                </Typography>
                <StatusTimeline events={ro.status_events} />
              </CardContent>
            </Card>

          </Stack>
        </Grid>
      </Grid>

      <ConfirmDialog
        open={confirmDelete}
        title="Supprimer l'ordre de réparation ?"
        message="L'ordre sera archivé et n'apparaîtra plus dans la liste principale."
        confirmLabel="Supprimer"
        dangerous
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </Box>
  )
}
