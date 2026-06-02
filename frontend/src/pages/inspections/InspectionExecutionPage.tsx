import { useState, useEffect, useCallback, useRef, type ReactElement } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Button,
  Chip,
  Collapse,
  Divider,
  IconButton,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import ErrorIcon from '@mui/icons-material/Error'
import RemoveCircleOutlineIcon from '@mui/icons-material/RemoveCircleOutline'
import SyncRoundedIcon from '@mui/icons-material/SyncRounded'
import WifiOffRoundedIcon from '@mui/icons-material/WifiOffRounded'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import DoneAllIcon from '@mui/icons-material/DoneAll'
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded'
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded'
import LinkRoundedIcon from '@mui/icons-material/LinkRounded'
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
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { StatusChip } from '../../components/ui/StatusChip'
import { useToast } from '../../contexts/ToastContext'

const TOUCH_BTN = { minHeight: 52, borderRadius: 2 }

// Design-system aligned status colors for section headers
const SECTION_HEADER_COLORS = {
  issues: { bg: '#FEF2F2', border: '#FECACA', text: '#DC2626' },
  allDone: { bg: '#F0FDF4', border: '#BBF7D0', text: '#16A34A' },
  default: { bg: '#F8FAFC', border: '#E2E8F0', text: '#475569' },
}

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
        {statuses.map(s => (
          <Button
            key={s}
            variant={result?.status === s ? 'contained' : 'outlined'}
            color={
              s === 'ok' ? 'success'
                : s === 'attention' ? 'warning'
                : s === 'defective' ? 'error'
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
        <IconButton size="small" onClick={() => setNotesOpen(v => !v)} disabled={disabled}>
          {notesOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
      </Stack>

      <MediaUploadButton
        inspectionPublicId={inspectionPublicId}
        mediaIds={result?.mediaIds ?? []}
        onUploaded={mediaId => onMediaAdded(item.id, mediaId)}
        onDelete={mediaId => onMediaDeleted(item.id, mediaId)}
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
          onChange={e => setNotes(e.target.value)}
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
  const done = section.items.filter(it => results[it.id]).length
  const issues = section.items.filter(
    it => results[it.id]?.status === 'defective' || results[it.id]?.status === 'attention'
  ).length
  const allDone = done === section.items.length && section.items.length > 0

  const colors = issues > 0
    ? SECTION_HEADER_COLORS.issues
    : allDone
    ? SECTION_HEADER_COLORS.allDone
    : SECTION_HEADER_COLORS.default

  return (
    <Paper
      sx={{
        mb: 2,
        overflow: 'hidden',
        border: '1px solid',
        borderColor: colors.border,
      }}
    >
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        sx={{
          px: 2,
          py: 1.5,
          bgcolor: colors.bg,
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setOpen(v => !v)}
      >
        <Typography variant="h6" fontWeight={700} color={colors.text}>
          {section.title || '(Section sans titre)'}
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip
            label={`${done}/${section.items.length}`}
            size="small"
            sx={{
              bgcolor: allDone ? '#BBF7D0' : '#E2E8F0',
              color: allDone ? '#15803D' : '#475569',
              fontWeight: 700,
              fontSize: '0.75rem',
            }}
          />
          {issues > 0 && (
            <Chip
              label={`${issues} problème${issues > 1 ? 's' : ''}`}
              size="small"
              sx={{ bgcolor: '#FECACA', color: '#DC2626', fontWeight: 700, fontSize: '0.75rem' }}
            />
          )}
          {open ? <ExpandLessIcon sx={{ color: colors.text }} /> : <ExpandMoreIcon sx={{ color: colors.text }} />}
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
  const { success: toastSuccess, error: toastError } = useToast()

  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [localResults, setLocalResults] = useState<LocalResults>({})
  const [syncError, setSyncError] = useState<string | null>(null)
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
    inspectionOfflineStore.getAll(publicId).then(pending => {
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
      setLocalResults(prev => {
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
      setLocalResults(prev => {
        const existing = prev[itemId]
        const mediaIds = [...(existing?.mediaIds ?? []), mediaId]
        return {
          ...prev,
          [itemId]: { ...(existing ?? { status: 'not_applicable' as InspectionItemStatus, notes: '' }), mediaIds, writtenAt },
        }
      })
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
      setLocalResults(prev => {
        const existing = prev[itemId]
        if (!existing) return prev
        const mediaIds = existing.mediaIds.filter(id => id !== mediaId)
        return { ...prev, [itemId]: { ...existing, mediaIds, writtenAt } }
      })
      const existing = localResults[itemId]
      if (existing) {
        await inspectionOfflineStore.saveResult({
          inspectionId: publicId,
          itemId,
          status: existing.status,
          notes: existing.notes || null,
          mediaIds: existing.mediaIds.filter(id => id !== mediaId),
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
        pending.map(p => ({
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
      toastSuccess('Synchronisation réussie')
      setSyncError(null)
    } catch {
      setSyncError('Sync échoué — données conservées localement.')
    } finally {
      syncInProgress.current = false
    }
  }, [publicId, isOnline, queryClient, toastSuccess])

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
      toastError('Impossible de générer le lien.')
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
      toastError('Impossible de télécharger le rapport.')
    } finally {
      setPdfLoading(false)
    }
  }

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <Box sx={{ textAlign: 'center' }}>
          <LinearProgress sx={{ width: 200, mb: 2 }} />
          <Typography variant="body2" color="text.secondary">Chargement de l'inspection…</Typography>
        </Box>
      </Box>
    )
  }

  if (isError && !inspection) {
    return (
      <Box p={2}>
        <Button startIcon={<ArrowBackRoundedIcon />} onClick={() => navigate('/inspections')} sx={{ mb: 2 }}>
          Retour
        </Button>
        <Typography color="error">Impossible de charger l'inspection.</Typography>
      </Box>
    )
  }

  const currentStatus = inspection?.status
  const canStart = currentStatus && INSPECTION_ALLOWED_TRANSITIONS[currentStatus].includes('in_progress')
  const canComplete = currentStatus && INSPECTION_ALLOWED_TRANSITIONS[currentStatus].includes('completed')
  const isReadOnly = currentStatus === 'completed' || currentStatus === 'cancelled'

  const totalItems = inspection?.template_sections.reduce((sum, s) => sum + s.items.length, 0) ?? 0
  const filledItems = Object.keys(localResults).length
  const progress = totalItems > 0 ? Math.round((filledItems / totalItems) * 100) : 0

  return (
    <Box sx={{ maxWidth: 960, mx: 'auto', pb: 14 }}>
      {/* Persistent offline banner — visible anywhere in the page */}
      {!isOnline && (
        <Box
          sx={{
            position: 'sticky',
            top: 0,
            zIndex: 200,
            bgcolor: '#FFFBEB',
            borderBottom: '1px solid #FDE68A',
            px: 2,
            py: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}
        >
          <WifiOffRoundedIcon sx={{ fontSize: 16, color: '#D97706' }} />
          <Typography variant="body2" fontWeight={600} color="#92400E">
            Mode hors ligne
          </Typography>
          <Typography variant="body2" color="#B45309" sx={{ ml: 0.5 }}>
            — Les résultats sont enregistrés localement et synchronisés à la reconnexion.
          </Typography>
        </Box>
      )}

      {/* Sync error banner */}
      {syncError && (
        <Box
          sx={{
            bgcolor: '#FEF2F2',
            borderBottom: '1px solid #FECACA',
            px: 2,
            py: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}
        >
          <Typography variant="body2" color="error.dark" fontWeight={500}>{syncError}</Typography>
          <Button size="small" onClick={() => setSyncError(null)} sx={{ ml: 'auto', minWidth: 0 }}>
            Fermer
          </Button>
        </Box>
      )}

      {/* Header */}
      <Box sx={{ p: 2 }}>
        <Stack
          direction="row"
          alignItems="flex-start"
          justifyContent="space-between"
          mb={2}
          flexWrap="wrap"
          spacing={1}
          useFlexGap
        >
          <Stack direction="row" spacing={1} alignItems="center">
            <IconButton onClick={() => navigate('/inspections')} size="small">
              <ArrowBackRoundedIcon />
            </IconButton>
            <Box>
              <Typography variant="h5" fontWeight={700}>
                {inspection?.template_name ?? 'Inspection'}
              </Typography>
              <Stack direction="row" spacing={1} mt={0.5} flexWrap="wrap" useFlexGap alignItems="center">
                <StatusChip
                  status={currentStatus ?? 'pending'}
                  label={currentStatus ? INSPECTION_STATUS_LABELS[currentStatus] : '…'}
                />
                <Chip
                  label={`${filledItems}/${totalItems} · ${progress}%`}
                  size="small"
                  sx={{
                    bgcolor: progress === 100 ? '#BBF7D0' : '#F1F5F9',
                    color: progress === 100 ? '#15803D' : '#475569',
                    fontWeight: 700,
                    fontSize: '0.75rem',
                  }}
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
              sx={{ ...TOUCH_BTN, border: '1px solid', borderColor: 'divider' }}
              disabled={!isOnline}
              onClick={() => void sync()}
              title="Synchroniser maintenant"
            >
              <SyncRoundedIcon />
            </IconButton>
          </Stack>
        </Stack>

        {/* Progress bar */}
        <LinearProgress
          variant="determinate"
          value={progress}
          color={progress === 100 ? 'success' : 'primary'}
          sx={{ height: 6, borderRadius: 999, mb: 2 }}
        />

        {/* Read-only banner */}
        {isReadOnly && (
          <Box
            sx={{
              bgcolor: currentStatus === 'completed' ? '#F0FDF4' : '#FEF2F2',
              border: '1px solid',
              borderColor: currentStatus === 'completed' ? '#BBF7D0' : '#FECACA',
              borderRadius: 1.5,
              px: 2,
              py: 1.25,
              mb: 2,
            }}
          >
            <Typography
              variant="body2"
              fontWeight={600}
              color={currentStatus === 'completed' ? 'success.dark' : 'error.dark'}
            >
              {currentStatus === 'completed'
                ? 'Inspection terminée — lecture seule.'
                : 'Inspection annulée — lecture seule.'}
            </Typography>
          </Box>
        )}

        {/* Completed actions */}
        {currentStatus === 'completed' && (
          <Stack direction="row" spacing={1} mb={2} flexWrap="wrap" useFlexGap>
            <Button
              variant="outlined"
              startIcon={pdfLoading ? undefined : <PictureAsPdfRoundedIcon />}
              disabled={pdfLoading}
              onClick={() => void handleDownloadPdf()}
              size="small"
            >
              {pdfLoading ? 'Génération…' : 'Télécharger le rapport PDF'}
            </Button>
            <Button
              variant="outlined"
              color={approvalLinkCopied ? 'success' : 'primary'}
              startIcon={<LinkRoundedIcon />}
              onClick={() => void handleGenerateApprovalLink()}
              size="small"
            >
              {approvalLinkCopied ? 'Lien copié !' : 'Générer lien approbation client'}
            </Button>
          </Stack>
        )}

        {/* Sections */}
        {inspection?.template_sections.map(section => (
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
      </Box>

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
            borderTop: '1px solid',
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

      <ConfirmDialog
        open={completeOpen}
        title="Terminer l'inspection ?"
        message={
          filledItems < totalItems
            ? `${totalItems - filledItems} élément(s) n'ont pas encore été évalués. Voulez-vous terminer quand même ?`
            : 'Tous les éléments ont été évalués. L\'inspection sera marquée comme terminée.'
        }
        confirmLabel="Terminer"
        loading={transitionMutation.isPending}
        onConfirm={() => void handleComplete()}
        onCancel={() => setCompleteOpen(false)}
      />
    </Box>
  )
}
