import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  Divider,
  IconButton,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded'
import StopRoundedIcon from '@mui/icons-material/StopRounded'
import SendRoundedIcon from '@mui/icons-material/SendRounded'
import PhotoCameraRoundedIcon from '@mui/icons-material/PhotoCameraRounded'
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded'
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import ExpandLessRoundedIcon from '@mui/icons-material/ExpandLessRounded'
import ChatBubbleOutlineRoundedIcon from '@mui/icons-material/ChatBubbleOutlineRounded'
import AccessTimeRoundedIcon from '@mui/icons-material/AccessTimeRounded'
import RadioButtonCheckedRoundedIcon from '@mui/icons-material/RadioButtonCheckedRounded'
import { useAuth } from '../../contexts/AuthContext'
import {
  repairOrderApi,
  STATUS_LABELS,
  ALLOWED_TRANSITIONS,
  type ROStatus,
  type RepairOrderSummary,
  type TimeEntry,
} from '../../lib/repairOrderApi'
import { StatusChip } from '../../components/ui/StatusChip'
import { EmptyState } from '../../components/ui/EmptyState'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { useToast } from '../../contexts/ToastContext'

const TOUCH_BTN = { minHeight: 52, borderRadius: '10px' }

const STATUS_ACCENT: Record<ROStatus, string> = {
  created: '#94A3B8',
  diagnosis: '#3B82F6',
  in_repair: '#F59E0B',
  finished: '#10B981',
  delivered: '#6366F1',
  paused_parts: '#EF4444',
  paused_approval: '#F97316',
}

// ── ROCard ────────────────────────────────────────────────────────────────────

function ROCard({ ro }: { ro: RepairOrderSummary }) {
  const queryClient = useQueryClient()
  const { success: toastSuccess, error: toastError } = useToast()
  const [commentText, setCommentText] = useState('')
  const [commentsOpen, setCommentsOpen] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: timeData } = useQuery({
    queryKey: ['time-entries', ro.id],
    queryFn: () => repairOrderApi.listTimeEntries(ro.id),
    refetchInterval: 15000,
  })

  const openEntry: TimeEntry | undefined = timeData?.items.find(e => e.ended_at === null)

  const { data: commentData } = useQuery({
    queryKey: ['comments', ro.id],
    queryFn: () => repairOrderApi.listComments(ro.id),
  })

  const { data: photoData } = useQuery({
    queryKey: ['photos', ro.id],
    queryFn: () => repairOrderApi.listPhotos(ro.id),
  })

  const startMutation = useMutation({
    mutationFn: () => repairOrderApi.startTimeEntry(ro.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['time-entries', ro.id] })
      toastSuccess('Session de travail démarrée')
    },
    onError: () => toastError('Une session est déjà ouverte.'),
  })

  const stopMutation = useMutation({
    mutationFn: () => repairOrderApi.stopTimeEntry(ro.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['time-entries', ro.id] })
      toastSuccess('Session arrêtée')
    },
    onError: () => toastError('Aucune session en cours.'),
  })

  const commentMutation = useMutation({
    mutationFn: () => repairOrderApi.createComment(ro.id, commentText),
    onSuccess: () => {
      setCommentText('')
      queryClient.invalidateQueries({ queryKey: ['comments', ro.id] })
      toastSuccess('Commentaire ajouté')
    },
    onError: () => toastError('Impossible d\'ajouter le commentaire.'),
  })

  const photoMutation = useMutation({
    mutationFn: (file: File) => repairOrderApi.uploadPhoto(ro.id, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['photos', ro.id] })
      toastSuccess('Photo ajoutée')
    },
    onError: () => toastError('Échec de l\'upload photo.'),
  })

  const transitionMutation = useMutation({
    mutationFn: (newStatus: ROStatus) =>
      repairOrderApi.transition(ro.id, { new_status: newStatus }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tablet-orders'] })
      toastSuccess('Statut mis à jour')
    },
    onError: () => toastError('Transition non permise.'),
  })

  const totalMinutes =
    timeData?.items
      .filter(e => e.duration_minutes !== null)
      .reduce((sum, e) => sum + (e.duration_minutes ?? 0), 0) ?? 0

  const allowed = ALLOWED_TRANSITIONS[ro.status]
  const accent = STATUS_ACCENT[ro.status] ?? '#94A3B8'

  return (
    <Card
      sx={{
        borderTop: `4px solid ${accent}`,
        transition: 'box-shadow 0.15s',
        '&:hover': { boxShadow: '0 4px 16px rgba(0,0,0,0.08)' },
      }}
    >
      <CardContent sx={{ p: 2.5 }}>
        <Stack spacing={2.5}>

          {/* ── Header ── */}
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
            <Box flex={1} minWidth={0}>
              <Typography variant="h6" fontWeight={700} gutterBottom={false} noWrap>
                {ro.description}
              </Typography>
              <Stack direction="row" spacing={1} alignItems="center" mt={0.5} flexWrap="wrap" useFlexGap>
                <Typography variant="caption" color="text.disabled" fontFamily="monospace">
                  #{ro.id.slice(-8).toUpperCase()}
                </Typography>
                <Typography variant="caption" color="text.disabled">·</Typography>
                <Typography variant="caption" color="text.secondary">
                  {ro.customer_name ?? `Client #${ro.customer_id}`}
                </Typography>
                {ro.vehicle_id && (
                  <>
                    <Typography variant="caption" color="text.disabled">·</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Véhicule #{ro.vehicle_id}
                    </Typography>
                  </>
                )}
              </Stack>
            </Box>
            <StatusChip status={ro.status} label={STATUS_LABELS[ro.status]} />
          </Stack>

          {/* ── Status transitions ── */}
          {allowed.length > 0 && (
            <Box>
              <Typography
                variant="caption"
                color="text.secondary"
                fontWeight={600}
                display="block"
                mb={1}
              >
                Changer le statut
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {allowed.map(s => (
                  <Button
                    key={s}
                    variant="outlined"
                    size="large"
                    sx={{ ...TOUCH_BTN, flex: '1 1 140px' }}
                    disabled={transitionMutation.isPending}
                    onClick={() => transitionMutation.mutate(s)}
                  >
                    {STATUS_LABELS[s]}
                  </Button>
                ))}
              </Stack>
            </Box>
          )}

          <Divider />

          {/* ── Timer ── */}
          <Box>
            <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
              <Stack direction="row" alignItems="center" spacing={0.75}>
                <AccessTimeRoundedIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  Pointage
                </Typography>
              </Stack>
              {totalMinutes > 0 && (
                <Typography variant="caption" color="text.secondary" fontFamily="monospace">
                  {Math.floor(totalMinutes / 60)}h{String(totalMinutes % 60).padStart(2, '0')} total
                </Typography>
              )}
            </Stack>

            {openEntry ? (
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Stack direction="row" alignItems="center" spacing={0.75} flex={1}>
                  <RadioButtonCheckedRoundedIcon
                    sx={{ fontSize: 14, color: 'success.main', animation: 'pulse 2s infinite' }}
                  />
                  <Typography variant="body2" fontWeight={600} color="success.dark">
                    En cours depuis {new Date(openEntry.started_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
                  </Typography>
                </Stack>
                <Button
                  variant="contained"
                  color="error"
                  size="large"
                  startIcon={<StopRoundedIcon />}
                  sx={TOUCH_BTN}
                  disabled={stopMutation.isPending}
                  onClick={() => stopMutation.mutate()}
                >
                  Arrêter
                </Button>
              </Stack>
            ) : (
              <Button
                variant="contained"
                color="success"
                size="large"
                fullWidth
                startIcon={<PlayArrowRoundedIcon />}
                sx={TOUCH_BTN}
                disabled={startMutation.isPending}
                onClick={() => startMutation.mutate()}
              >
                Démarrer une session
              </Button>
            )}
          </Box>

          <Divider />

          {/* ── Photos ── */}
          <Box>
            <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
              <Stack direction="row" alignItems="center" spacing={0.75}>
                <PhotoCameraRoundedIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  Photos
                </Typography>
                {(photoData?.total ?? 0) > 0 && (
                  <Chip
                    label={photoData!.total}
                    size="small"
                    sx={{ height: 18, fontSize: '0.65rem', bgcolor: '#F1F5F9', fontWeight: 600 }}
                  />
                )}
              </Stack>
            </Stack>

            {photoData && photoData.items.length > 0 && (
              <Stack direction="row" spacing={1} mb={1.5} flexWrap="wrap" useFlexGap>
                {photoData.items.slice(-6).map(p => (
                  <Box
                    key={p.id}
                    component="img"
                    src={p.url}
                    alt={p.filename}
                    sx={{
                      width: 96, height: 96,
                      objectFit: 'cover',
                      borderRadius: 1.5,
                      border: '1px solid #E2E8F0',
                    }}
                  />
                ))}
              </Stack>
            )}

            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              capture="environment"
              style={{ display: 'none' }}
              onChange={e => {
                const file = e.target.files?.[0]
                if (file) photoMutation.mutate(file)
                e.target.value = ''
              }}
            />
            <Button
              variant="outlined"
              size="large"
              fullWidth
              startIcon={<PhotoCameraRoundedIcon />}
              sx={TOUCH_BTN}
              disabled={photoMutation.isPending}
              onClick={() => fileRef.current?.click()}
            >
              {photoMutation.isPending ? 'Envoi en cours…' : 'Prendre une photo'}
            </Button>
          </Box>

          <Divider />

          {/* ── Comments ── */}
          <Box>
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              mb={commentsOpen ? 1.5 : 0}
              sx={{ cursor: 'pointer', userSelect: 'none' }}
              onClick={() => setCommentsOpen(v => !v)}
            >
              <Stack direction="row" alignItems="center" spacing={0.75}>
                <ChatBubbleOutlineRoundedIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  Commentaires
                </Typography>
                {(commentData?.total ?? 0) > 0 && (
                  <Chip
                    label={commentData!.total}
                    size="small"
                    sx={{ height: 18, fontSize: '0.65rem', bgcolor: '#F1F5F9', fontWeight: 600 }}
                  />
                )}
              </Stack>
              {commentsOpen
                ? <ExpandLessRoundedIcon sx={{ fontSize: 18, color: 'text.disabled' }} />
                : <ExpandMoreRoundedIcon sx={{ fontSize: 18, color: 'text.disabled' }} />
              }
            </Stack>

            <Collapse in={commentsOpen}>
              {commentData && commentData.items.length > 0 && (
                <Stack spacing={0.75} mb={1.5}>
                  {commentData.items.slice(-5).map(c => (
                    <Box
                      key={c.id}
                      sx={{
                        px: 1.5, py: 1,
                        bgcolor: '#F8FAFC',
                        borderRadius: 1.5,
                        border: '1px solid #E2E8F0',
                      }}
                    >
                      <Typography variant="body2">{c.body}</Typography>
                      <Typography variant="caption" color="text.disabled">
                        {new Date(c.created_at).toLocaleString('fr-FR', {
                          day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
                        })}
                      </Typography>
                    </Box>
                  ))}
                </Stack>
              )}

              <Stack direction="row" spacing={1} alignItems="flex-end">
                <TextField
                  multiline
                  size="small"
                  placeholder="Ajouter une note…"
                  value={commentText}
                  onChange={e => setCommentText(e.target.value)}
                  sx={{ flex: 1 }}
                  inputProps={{ style: { fontSize: '1rem', minHeight: 44 } }}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && e.ctrlKey && commentText.trim()) {
                      commentMutation.mutate()
                    }
                  }}
                />
                <IconButton
                  color="primary"
                  size="large"
                  sx={{
                    ...TOUCH_BTN,
                    bgcolor: 'primary.main',
                    color: 'white',
                    '&:hover': { bgcolor: 'primary.dark' },
                    '&:disabled': { bgcolor: 'action.disabledBackground' },
                  }}
                  disabled={commentMutation.isPending || !commentText.trim()}
                  onClick={() => commentMutation.mutate()}
                >
                  <SendRoundedIcon />
                </IconButton>
              </Stack>
            </Collapse>
          </Box>

        </Stack>
      </CardContent>
    </Card>
  )
}

// ── Live clock ─────────────────────────────────────────────────────────────────

function LiveClock() {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 60000)
    return () => clearInterval(id)
  }, [])
  return (
    <Typography variant="h6" fontFamily="monospace" fontWeight={600} color="text.secondary">
      {time.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
    </Typography>
  )
}

function getInternalUserId(): number | undefined {
  const token = localStorage.getItem('access_token')
  if (!token) return undefined
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.uid as number | undefined
  } catch {
    return undefined
  }
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function TabletViewPage() {
  const { user } = useAuth()
  // Recompute when the authenticated user changes (getInternalUserId reads auth state).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const internalUserId = useMemo(() => getInternalUserId(), [user])

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['tablet-orders', internalUserId],
    queryFn: () =>
      repairOrderApi.list({
        assigned_user_id: internalUserId,
        page_size: 50,
      }),
    refetchInterval: 15000,
    enabled: !!internalUserId,
  })

  const openOrders = data?.items.filter(ro => ro.status !== 'delivered') ?? []

  return (
    <Box
      sx={{
        minHeight: '100vh',
        bgcolor: '#F1F5F9',
        pb: 4,
      }}
    >
      {/* Header */}
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 100,
          bgcolor: '#0F172A',
          px: 3,
          py: 2,
          borderBottom: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack spacing={0.25}>
            <Stack direction="row" alignItems="center" spacing={1.5}>
              {/* X logo mark */}
              <Box
                sx={{
                  width: 32, height: 32,
                  borderRadius: '8px',
                  bgcolor: '#2563EB',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Typography fontWeight={800} fontSize="1rem" color="white" lineHeight={1}>
                  X
                </Typography>
              </Box>
              <Typography variant="h6" fontWeight={700} color="white">
                {user?.full_name ?? 'Mécanicien'}
              </Typography>
            </Stack>
            <Typography variant="caption" color="rgba(255,255,255,0.5)" pl={0.5}>
              {openOrders.length} ordre{openOrders.length !== 1 ? 's' : ''} en cours
            </Typography>
          </Stack>

          <Stack direction="row" alignItems="center" spacing={2}>
            <LiveClock />
            <IconButton
              size="large"
              onClick={() => refetch()}
              sx={{
                color: 'white',
                bgcolor: 'rgba(255,255,255,0.08)',
                borderRadius: '10px',
                minHeight: 44,
                minWidth: 44,
                '&:hover': { bgcolor: 'rgba(255,255,255,0.15)' },
              }}
            >
              <RefreshRoundedIcon />
            </IconButton>
          </Stack>
        </Stack>
      </Box>

      {/* Content */}
      <Box sx={{ p: { xs: 2, sm: 3 }, maxWidth: 840, mx: 'auto' }}>
        {isLoading && <LoadingScreen message="Chargement de vos ordres…" />}

        {isError && (
          <Box
            sx={{
              bgcolor: '#FEF2F2',
              border: '1px solid #FECACA',
              borderRadius: 2,
              p: 2.5,
              mt: 2,
            }}
          >
            <Typography color="error.dark" fontWeight={600}>
              Impossible de charger vos ordres de réparation.
            </Typography>
            <Button
              size="small"
              onClick={() => refetch()}
              sx={{ mt: 1 }}
              startIcon={<RefreshRoundedIcon />}
            >
              Réessayer
            </Button>
          </Box>
        )}

        {!isLoading && !isError && openOrders.length === 0 && (
          <EmptyState
            title="Aucun ordre assigné"
            description="Vous n'avez pas d'ordre de réparation en cours pour le moment."
          />
        )}

        <Stack spacing={2.5} mt={isLoading || isError ? 0 : 1}>
          {openOrders.map(ro => (
            <ROCard key={ro.id} ro={ro} />
          ))}
        </Stack>
      </Box>
    </Box>
  )
}
