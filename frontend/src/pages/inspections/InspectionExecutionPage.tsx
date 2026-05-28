import { useState, useEffect, useCallback, useRef, type ReactElement } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Paper,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import ErrorIcon from '@mui/icons-material/Error'
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline'
import SyncIcon from '@mui/icons-material/Sync'
import WifiOffIcon from '@mui/icons-material/WifiOff'
import WifiIcon from '@mui/icons-material/Wifi'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import DoneAllIcon from '@mui/icons-material/DoneAll'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'
import LinkIcon from '@mui/icons-material/Link'
import {
  inspectionApi,
  type InspectionItemStatus,
  type TemplateSection,
  ITEM_STATUS_LABELS,
  INSPECTION_ALLOWED_TRANSITIONS,
  INSPECTION_STATUS_LABELS,
} from '../../lib/inspectionApi'
import { inspectionOfflineStore } from '../../lib/inspectionOfflineStore'
import { MediaUploadButton } from '../../components/inspections/MediaUploadButton'

const TOUCH_BTN = { minHeight: 52, borderRadius: 2 }

const STATUS_ICONS: Record<InspectionItemStatus, ReactElement> = {
  ok: <CheckCircleIcon />,
  attention: <WarningAmberIcon />,
  defective: <ErrorIcon />,
  not_applicable: <RemoveCircleOutlineIcon />,
}

type LocalResults = Record<
  string,
  { status: InspectionItemStatus; notes: string; mediaIds: string[]; writtenAt: string }
>

// ── ItemRow ───────────────────────────────────────────────────────────────────

function ItemRow({
  item,
  result,
  inspectionPublicId,
  onChange,
  onMediaAdded,
  onMediaDeleted,
  disabled,
}: {
  item: { id: string; label: string }
  result: LocalResults[string] | undefined
  inspectionPublicId: string
  onChange: (itemId: string, status: InspectionItemStatus, notes: string) => void
  onMediaAdded: (itemId: string, mediaId: string) => void
  onMediaDeleted: (itemId: string, mediaId: string) => void
  disabled: boolean
}) {
  const [notesOpen, setNotesOpen] = useState(false)
  const [notes, setNotes] = useState(result?.notes ?? '')
  const statuses: InspectionItemStatus[] = ['ok', 'attention', 'defective', 'not_applicable']

  useEffect(() => {
    setNotes(result?.notes ?? '')
  }, [result?.notes])

  const pick = (s: InspectionItemStatus) => {
    onChange(item.id, s, notes)
    if (!notesOpen && (s === 'attention' || s === 'defective')) setNotesOpen(true)
  }

  return (
    <Box sx={{ py: 1.5 }}>
      <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
        <Typography
          sx={{
            flex: 1,
            minWidth: 160,
            fontWeight: result?.status ? 600 : 400,
            opacity: disabled ? 0.6 : 1,
          }}
        >
          {item.label}
        </Typography>
        {statuses.map((s) => (
          <Button
            key={s}
            variant={result?.status === s ? 'contained' : 'outlined'}
            color={
              s === 'ok'
                ? 'success'
                : s === 'attention'
                ? 'warning'
                : s === 'defective'
                ? 'error'
                : 'inherit'
            }
            size="large"
            sx={{ ...TOUCH_BTN, minWidth: 120, flex: '0 0 auto' }}
            disabled={disabled}
            startIcon={STATUS_ICONS[s]}
            onClick={() => pick(s)}
          >
            {ITEM_STATUS_LABELS[s]}
          </Button>
        ))}
        <IconButton size="small" onClick={() => setNotesOpen((v) => !v)} disabled={disabled}>
          {notesOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Stack>

      {/* Media upload + thumbnails */}
      <MediaUploadButton
        inspectionPublicId={inspectionPublicId}
        mediaIds={result?.mediaIds ?? []}
        onUploaded={(mediaId) => onMediaAdded(item.id, mediaId)}
        onDelete={(mediaId) => onMediaDeleted(item.id, mediaId)}
        disabled={disabled}
      />

      <Collapse in={notesOpen}>
        <TextField
          fullWidth
          multiline
          rows={2}
          size="small"
          placeholder="Notes sur cet élément..."
          value={notes}
          disabled={disabled}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => {
            if (result?.status) onChange(item.id, result.status, notes)
          }}
          sx={{ mt: 1 }}
        />
      </Collapse>
    </Box>
  )
}

// ── SectionCard ───────────────────────────────────────────────────────────────

function SectionCard({
  section,
  results,
  inspectionPublicId,
  onChange,
  onMediaAdded,
  onMediaDeleted,
  disabled,
}: {
  section: TemplateSection
  results: LocalResults
  inspectionPublicId: string
  onChange: (itemId: string, status: InspectionItemStatus, notes: string) => void
  onMediaAdded: (itemId: string, mediaId: string) => void
  onMediaDeleted: (itemId: string, mediaId: string) => void
  disabled: boolean
}) {
  const [open, setOpen] = useState(true)
  const done = section.items.filter((it) => results[it.id]).length
  const issues = section.items.filter(
    (it) =>
      results[it.id]?.status === 'defective' || results[it.id]?.status === 'attention'
  ).length
  const allDone = done === section.items.length

  return (
    <Paper sx={{ mb: 2, overflow: 'hidden' }}>
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        sx={{
          px: 2,
          py: 1.5,
          bgcolor: issues > 0 ? 'error.light' : allDone ? 'success.light' : 'grey.100',
          cursor: 'pointer',
        }}
        onClick={() => setOpen((v) => !v)}
      >
        <Typography variant="h6" fontWeight={700}>
          {section.title || '(Section sans titre)'}
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip
            label={`${done}/${section.items.length}`}
            size="small"
            color={allDone ? 'success' : 'default'}
          />
          {issues > 0 && (
            <Chip
              label={`${issues} problème${issues > 1 ? 's' : ''}`}
              size="small"
              color="error"
            />
          )}
          {open ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </Stack>
      </Stack>
      <Collapse in={open}>
        <Box sx={{ px: 2 }}>
          <Divider />
          {section.items.map((item, idx) => (
            <Box key={item.id}>
              <ItemRow
                item={item}
                result={results[item.id]}
                inspectionPublicId={inspectionPublicId}
                onChange={onChange}
                onMediaAdded={onMediaAdded}
                onMediaDeleted={onMediaDeleted}
                disabled={disabled}
              />
              {idx < section.items.length - 1 && <Divider />}
            </Box>
          ))}
        </Box>
      </Collapse>
    </Paper>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function InspectionExecutionPage() {
  const { publicId } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [localResults, setLocalResults] = useState<LocalResults>({})
  const [syncError, setSyncError] = useState<string | null>(null)
  const [syncSuccess, setSyncSuccess] = useState(false)
  const [completeOpen, setCompleteOpen] = useState(false)
  const [approvalLinkCopied, setApprovalLinkCopied] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const syncInProgress = useRef(false)

  useEffect(() => {
    const up = () => setIsOnline(true)
    const down = () => setIsOnline(false)
    window.addEventListener('online', up)
    window.addEventListener('offline', down)
    return () => {
      window.removeEventListener('online', up)
      window.removeEventListener('offline', down)
    }
  }, [])

  const { data: inspection, isLoading, isError } = useQuery({
    queryKey: ['inspection', publicId],
    queryFn: () => inspectionApi.getInspection(publicId!),
    enabled: !!publicId && isOnline,
    staleTime: 60_000,
  })

  // Seed local state: server results overlaid with any pending offline writes
  useEffect(() => {
    if (!inspection || !publicId) return
    const init: LocalResults = {}
    for (const r of inspection.results) {
      init[r.item_id] = {
        status: r.status,
        notes: r.notes ?? '',
        mediaIds: r.media_ids ?? [],
        writtenAt: r.written_at,
      }
    }
    inspectionOfflineStore.getAll(publicId).then((pending) => {
      for (const p of pending) {
        const existing = init[p.itemId]
        if (!existing || p.writtenAt > existing.writtenAt) {
          init[p.itemId] = {
            status: p.status as InspectionItemStatus,
            notes: p.notes ?? '',
            mediaIds: p.mediaIds ?? [],
            writtenAt: p.writtenAt,
          }
        }
      }
      setLocalResults(init)
    })
  }, [inspection, publicId])

  const handleItemChange = useCallback(
    async (itemId: string, status: InspectionItemStatus, notes: string) => {
      if (!publicId) return
      const writtenAt = new Date().toISOString()
      setLocalResults((prev) => {
        const mediaIds = prev[itemId]?.mediaIds ?? []
        return { ...prev, [itemId]: { status, notes, mediaIds, writtenAt } }
      })
      await inspectionOfflineStore.saveResult({
        inspectionId: publicId,
        itemId,
        status,
        notes: notes || null,
        mediaIds: localResults[itemId]?.mediaIds ?? [],
        writtenAt,
        synced: false,
      })
    },
    [publicId, localResults]
  )

  const handleMediaAdded = useCallback(
    async (itemId: string, mediaId: string) => {
      if (!publicId) return
      const writtenAt = new Date().toISOString()
      setLocalResults((prev) => {
        const existing = prev[itemId]
        const mediaIds = [...(existing?.mediaIds ?? []), mediaId]
        return {
          ...prev,
          [itemId]: { ...(existing ?? { status: 'not_applicable' as InspectionItemStatus, notes: '' }), mediaIds, writtenAt },
        }
      })
      // Persist updated mediaIds to offline store so sync includes them
      const existing = localResults[itemId]
      if (existing) {
        await inspectionOfflineStore.saveResult({
          inspectionId: publicId,
          itemId,
          status: existing.status,
          notes: existing.notes || null,
          mediaIds: [...existing.mediaIds, mediaId],
          writtenAt,
          synced: false,
        })
      }
    },
    [publicId, localResults]
  )

  const handleMediaDeleted = useCallback(
    async (itemId: string, mediaId: string) => {
      if (!publicId) return
      const writtenAt = new Date().toISOString()
      setLocalResults((prev) => {
        const existing = prev[itemId]
        if (!existing) return prev
        const mediaIds = existing.mediaIds.filter((id) => id !== mediaId)
        return { ...prev, [itemId]: { ...existing, mediaIds, writtenAt } }
      })
      const existing = localResults[itemId]
      if (existing) {
        await inspectionOfflineStore.saveResult({
          inspectionId: publicId,
          itemId,
          status: existing.status,
          notes: existing.notes || null,
          mediaIds: existing.mediaIds.filter((id) => id !== mediaId),
          writtenAt,
          synced: false,
        })
      }
    },
    [publicId, localResults]
  )

  const sync = useCallback(async () => {
    if (!publicId || syncInProgress.current || !isOnline) return
    syncInProgress.current = true
    try {
      const pending = await inspectionOfflineStore.getPending(publicId)
      if (pending.length === 0) return
      await inspectionApi.submitResults(
        publicId,
        pending.map((p) => ({
          item_id: p.itemId,
          status: p.status as InspectionItemStatus,
          notes: p.notes ?? undefined,
          media_ids: p.mediaIds,
          written_at: p.writtenAt,
        }))
      )
      for (const p of pending) {
        await inspectionOfflineStore.markSynced(publicId, p.itemId)
      }
      await inspectionOfflineStore.clearSynced(publicId)
      queryClient.invalidateQueries({ queryKey: ['inspection', publicId] })
      setSyncSuccess(true)
      setSyncError(null)
    } catch {
      setSyncError('Sync échoué — données conservées localement.')
    } finally {
      syncInProgress.current = false
    }
  }, [publicId, isOnline, queryClient])

  // Auto-sync when reconnecting
  useEffect(() => {
    if (isOnline) void sync()
  }, [isOnline, sync])

  const transitionMutation = useMutation({
    mutationFn: (newStatus: 'in_progress' | 'completed' | 'cancelled') =>
      inspectionApi.transitionStatus(publicId!, newStatus),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inspection', publicId] })
      queryClient.invalidateQueries({ queryKey: ['inspections'] })
    },
  })

  const handleComplete = async () => {
    await sync()
    transitionMutation.mutate('completed', {
      onSuccess: () => {
        setCompleteOpen(false)
        navigate('/inspections')
      },
    })
  }

  const handleGenerateApprovalLink = async () => {
    if (!publicId) return
    try {
      const res = await inspectionApi.generateApprovalLink(publicId)
      const link = `${window.location.origin}/approve/${res.token}`
      await navigator.clipboard.writeText(link)
      setApprovalLinkCopied(true)
      setTimeout(() => setApprovalLinkCopied(false), 3000)
    } catch {
      // ignore
    }
  }

  const handleDownloadPdf = async () => {
    if (!publicId) return
    setPdfLoading(true)
    try {
      const blob = await inspectionApi.downloadReport(publicId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `inspection-${publicId}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // ignore
    } finally {
      setPdfLoading(false)
    }
  }

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress size={60} />
      </Box>
    )
  }

  if (isError && !inspection) {
    return (
      <Box p={2}>
        <Alert severity="error">Impossible de charger l'inspection.</Alert>
      </Box>
    )
  }

  const currentStatus = inspection?.status
  const canStart = currentStatus && INSPECTION_ALLOWED_TRANSITIONS[currentStatus].includes('in_progress')
  const canComplete = currentStatus && INSPECTION_ALLOWED_TRANSITIONS[currentStatus].includes('completed')
  const isReadOnly = currentStatus === 'completed' || currentStatus === 'cancelled'

  const totalItems =
    inspection?.template_sections.reduce((sum, s) => sum + s.items.length, 0) ?? 0
  const filledItems = Object.keys(localResults).length
  const progress = totalItems > 0 ? Math.round((filledItems / totalItems) * 100) : 0

  return (
    <Box sx={{ p: 2, maxWidth: 960, mx: 'auto', pb: 14 }}>
      {/* Header */}
      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" mb={2} flexWrap="wrap" spacing={1} useFlexGap>
        <Stack direction="row" spacing={1} alignItems="center">
          <IconButton onClick={() => navigate('/inspections')}>
            <ArrowBackIcon />
          </IconButton>
          <Box>
            <Typography variant="h5" fontWeight={700}>
              {inspection?.template_name ?? 'Inspection'}
            </Typography>
            <Stack direction="row" spacing={1} mt={0.5} flexWrap="wrap" useFlexGap>
              <Chip
                label={
                  currentStatus ? INSPECTION_STATUS_LABELS[currentStatus] : '…'
                }
                color={
                  currentStatus === 'completed'
                    ? 'success'
                    : currentStatus === 'in_progress'
                    ? 'primary'
                    : currentStatus === 'cancelled'
                    ? 'error'
                    : 'default'
                }
                size="small"
              />
              <Chip
                icon={isOnline ? <WifiIcon /> : <WifiOffIcon />}
                label={isOnline ? 'En ligne' : 'Hors ligne'}
                color={isOnline ? 'success' : 'warning'}
                variant="outlined"
                size="small"
              />
              <Chip
                label={`${filledItems}/${totalItems} (${progress}%)`}
                size="small"
                color={progress === 100 ? 'success' : 'default'}
              />
            </Stack>
          </Box>
        </Stack>
        <Stack direction="row" spacing={1}>
          {canStart && (
            <Button
              variant="contained"
              size="large"
              sx={TOUCH_BTN}
              disabled={transitionMutation.isPending}
              onClick={() => transitionMutation.mutate('in_progress')}
            >
              Démarrer
            </Button>
          )}
          <IconButton
            size="large"
            sx={TOUCH_BTN}
            disabled={!isOnline}
            onClick={() => void sync()}
            title="Synchroniser maintenant"
          >
            <SyncIcon />
          </IconButton>
        </Stack>
      </Stack>

      {/* Banners */}
      {syncError && (
        <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setSyncError(null)}>
          {syncError}
        </Alert>
      )}
      {!isOnline && (
        <Alert severity="info" sx={{ mb: 2 }} icon={<WifiOffIcon />}>
          Mode hors ligne — les résultats sont enregistrés localement et synchronisés à la reconnexion.
        </Alert>
      )}
      {isReadOnly && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Cette inspection est{' '}
          {currentStatus === 'completed' ? 'terminée' : 'annulée'} — lecture seule.
        </Alert>
      )}

      {/* Completed-only actions */}
      {currentStatus === 'completed' && (
        <Stack direction="row" spacing={1} mb={2} flexWrap="wrap" useFlexGap>
          <Button
            variant="outlined"
            startIcon={pdfLoading ? <CircularProgress size={16} /> : <PictureAsPdfIcon />}
            disabled={pdfLoading}
            onClick={() => void handleDownloadPdf()}
            size="small"
          >
            Télécharger le rapport PDF
          </Button>
          <Button
            variant="outlined"
            color={approvalLinkCopied ? 'success' : 'primary'}
            startIcon={<LinkIcon />}
            onClick={() => void handleGenerateApprovalLink()}
            size="small"
          >
            {approvalLinkCopied ? 'Lien copié !' : 'Générer lien approbation client'}
          </Button>
        </Stack>
      )}

      {/* Sections */}
      {inspection?.template_sections.map((section) => (
        <SectionCard
          key={section.id}
          section={section}
          results={localResults}
          inspectionPublicId={publicId!}
          onChange={handleItemChange}
          onMediaAdded={handleMediaAdded}
          onMediaDeleted={handleMediaDeleted}
          disabled={!!isReadOnly}
        />
      ))}

      {/* Sticky complete button */}
      {canComplete && !isReadOnly && (
        <Box
          sx={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            p: 2,
            bgcolor: 'background.paper',
            borderTop: 1,
            borderColor: 'divider',
            zIndex: 100,
          }}
        >
          <Button
            fullWidth
            variant="contained"
            color="success"
            size="large"
            sx={{ minHeight: 64, fontSize: '1.1rem', borderRadius: 2 }}
            startIcon={<DoneAllIcon />}
            disabled={transitionMutation.isPending}
            onClick={() => setCompleteOpen(true)}
          >
            Terminer l'inspection
          </Button>
        </Box>
      )}

      {/* Confirm dialog */}
      <Dialog open={completeOpen} onClose={() => setCompleteOpen(false)}>
        <DialogTitle>Terminer l'inspection ?</DialogTitle>
        <DialogContent>
          {filledItems < totalItems ? (
            <Alert severity="warning">
              {totalItems - filledItems} élément(s) non évalué(s). Continuer quand même ?
            </Alert>
          ) : (
            <Typography>Tous les éléments ont été évalués.</Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCompleteOpen(false)}>Annuler</Button>
          <Button
            variant="contained"
            color="success"
            disabled={transitionMutation.isPending}
            onClick={() => void handleComplete()}
          >
            Confirmer
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={syncSuccess}
        autoHideDuration={3000}
        onClose={() => setSyncSuccess(false)}
        message="Synchronisation réussie"
      />
    </Box>
  )
}
