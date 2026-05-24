import { useRef, useState, useMemo } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import SendIcon from '@mui/icons-material/Send'
import PhotoCameraIcon from '@mui/icons-material/PhotoCamera'
import RefreshIcon from '@mui/icons-material/Refresh'
import { useAuth } from '../../contexts/AuthContext'
import {
  repairOrderApi,
  STATUS_LABELS,
  ALLOWED_TRANSITIONS,
  type ROStatus,
  type RepairOrderSummary,
  type TimeEntry,
} from '../../lib/repairOrderApi'

const TOUCH_BTN = { minHeight: 56, minWidth: 56, fontSize: '1rem' }

const STATUS_COLORS: Record<ROStatus, 'default' | 'info' | 'warning' | 'success' | 'error' | 'primary'> = {
  created: 'default',
  diagnosis: 'info',
  in_repair: 'primary',
  finished: 'warning',
  delivered: 'success',
  paused_parts: 'error',
  paused_approval: 'error',
}

function ROCard({ ro }: { ro: RepairOrderSummary }) {
  const queryClient = useQueryClient()
  const [commentText, setCommentText] = useState('')
  const [timerError, setTimerError] = useState<string | null>(null)
  const [transitionError, setTransitionError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const { data: timeData } = useQuery({
    queryKey: ['time-entries', ro.id],
    queryFn: () => repairOrderApi.listTimeEntries(ro.id),
    refetchInterval: 15000,
  })

  const openEntry: TimeEntry | undefined = timeData?.items.find((e) => e.ended_at === null)

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
      setTimerError(null)
      queryClient.invalidateQueries({ queryKey: ['time-entries', ro.id] })
    },
    onError: () => setTimerError('Session déjà ouverte.'),
  })

  const stopMutation = useMutation({
    mutationFn: () => repairOrderApi.stopTimeEntry(ro.id),
    onSuccess: () => {
      setTimerError(null)
      queryClient.invalidateQueries({ queryKey: ['time-entries', ro.id] })
    },
    onError: () => setTimerError('Aucune session ouverte.'),
  })

  const commentMutation = useMutation({
    mutationFn: () => repairOrderApi.createComment(ro.id, commentText),
    onSuccess: () => {
      setCommentText('')
      queryClient.invalidateQueries({ queryKey: ['comments', ro.id] })
    },
  })

  const photoMutation = useMutation({
    mutationFn: (file: File) => repairOrderApi.uploadPhoto(ro.id, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['photos', ro.id] }),
  })

  const transitionMutation = useMutation({
    mutationFn: (newStatus: ROStatus) =>
      repairOrderApi.transition(ro.id, { new_status: newStatus }),
    onSuccess: () => {
      setTransitionError(null)
      queryClient.invalidateQueries({ queryKey: ['tablet-orders'] })
    },
    onError: () => setTransitionError('Transition non permise.'),
  })

  const totalMinutes = timeData?.items
    .filter((e) => e.duration_minutes !== null)
    .reduce((sum, e) => sum + (e.duration_minutes ?? 0), 0) ?? 0

  const allowed = ALLOWED_TRANSITIONS[ro.status]

  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Stack spacing={1.5}>
        {/* Header */}
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
          <Box>
            <Typography variant="h6" fontWeight={700} noWrap>
              {ro.description}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              #{ro.id.slice(-8).toUpperCase()} · Client #{ro.customer_id}
              {ro.vehicle_id ? ` · Véhicule #${ro.vehicle_id}` : ''}
            </Typography>
          </Box>
          <Chip
            label={STATUS_LABELS[ro.status]}
            color={STATUS_COLORS[ro.status]}
            sx={{ fontWeight: 700 }}
          />
        </Stack>

        <Divider />

        {/* Status transition buttons */}
        {allowed.length > 0 && (
          <Box>
            <Typography variant="overline" color="text.secondary" display="block" mb={0.5}>
              Changer le statut
            </Typography>
            {transitionError && (
              <Alert severity="error" sx={{ mb: 1 }} onClose={() => setTransitionError(null)}>
                {transitionError}
              </Alert>
            )}
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {allowed.map((s) => (
                <Button
                  key={s}
                  variant="outlined"
                  size="large"
                  sx={TOUCH_BTN}
                  disabled={transitionMutation.isPending}
                  onClick={() => transitionMutation.mutate(s)}
                >
                  {STATUS_LABELS[s]}
                </Button>
              ))}
            </Stack>
          </Box>
        )}

        {/* Timer */}
        <Box>
          <Typography variant="overline" color="text.secondary" display="block" mb={0.5}>
            Pointage
            {totalMinutes > 0 && ` · ${Math.floor(totalMinutes / 60)}h${String(totalMinutes % 60).padStart(2, '0')} total`}
          </Typography>
          {timerError && (
            <Alert severity="error" sx={{ mb: 1 }} onClose={() => setTimerError(null)}>
              {timerError}
            </Alert>
          )}
          {openEntry ? (
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip
                icon={<PlayArrowIcon />}
                label={`En cours depuis ${new Date(openEntry.started_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`}
                color="success"
                variant="outlined"
              />
              <Button
                variant="contained"
                color="error"
                size="large"
                startIcon={<StopIcon />}
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
              startIcon={<PlayArrowIcon />}
              sx={TOUCH_BTN}
              disabled={startMutation.isPending}
              onClick={() => startMutation.mutate()}
            >
              Démarrer une session
            </Button>
          )}
        </Box>

        {/* Comment input */}
        <Box>
          <Typography variant="overline" color="text.secondary" display="block" mb={0.5}>
            Commentaire ({commentData?.total ?? 0})
          </Typography>
          <Stack direction="row" spacing={1} alignItems="flex-end">
            <TextField
              multiline
              size="small"
              placeholder="Ajouter une note..."
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              sx={{ flex: 1 }}
              inputProps={{ style: { fontSize: '1rem', minHeight: 44 } }}
            />
            <IconButton
              color="primary"
              size="large"
              sx={{ ...TOUCH_BTN, bgcolor: 'primary.main', color: 'white', borderRadius: 2, '&:hover': { bgcolor: 'primary.dark' } }}
              disabled={commentMutation.isPending || !commentText.trim()}
              onClick={() => commentMutation.mutate()}
            >
              <SendIcon />
            </IconButton>
          </Stack>
          {commentData && commentData.items.length > 0 && (
            <Stack spacing={0.5} mt={1}>
              {commentData.items.slice(-3).map((c) => (
                <Box key={c.id} sx={{ px: 1, py: 0.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                  <Typography variant="body2">{c.body}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(c.created_at).toLocaleString('fr-FR')}
                  </Typography>
                </Box>
              ))}
            </Stack>
          )}
        </Box>

        {/* Photo upload */}
        <Box>
          <Typography variant="overline" color="text.secondary" display="block" mb={0.5}>
            Photos ({photoData?.total ?? 0})
          </Typography>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            capture="environment"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) photoMutation.mutate(file)
              e.target.value = ''
            }}
          />
          <Button
            variant="outlined"
            size="large"
            startIcon={<PhotoCameraIcon />}
            sx={TOUCH_BTN}
            disabled={photoMutation.isPending}
            onClick={() => fileRef.current?.click()}
          >
            {photoMutation.isPending ? 'Envoi...' : 'Prendre une photo'}
          </Button>
          {photoData && photoData.items.length > 0 && (
            <Stack direction="row" spacing={1} mt={1} flexWrap="wrap">
              {photoData.items.slice(-4).map((p) => (
                <Box
                  key={p.id}
                  component="img"
                  src={p.url}
                  alt={p.filename}
                  sx={{ width: 72, height: 72, objectFit: 'cover', borderRadius: 1 }}
                />
              ))}
            </Stack>
          )}
        </Box>
      </Stack>
    </Paper>
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

export function TabletViewPage() {
  const { user } = useAuth()
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

  const openOrders = data?.items.filter(
    (ro) => ro.status !== 'delivered'
  ) ?? []

  return (
    <Box
      sx={{
        p: 2,
        maxWidth: 800,
        mx: 'auto',
        minHeight: '100vh',
        bgcolor: 'background.default',
      }}
    >
      <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            Mes ordres de réparation
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {user?.full_name} · {openOrders.length} ordre{openOrders.length !== 1 ? 's' : ''} en cours
          </Typography>
        </Box>
        <IconButton size="large" onClick={() => refetch()} sx={TOUCH_BTN}>
          <RefreshIcon />
        </IconButton>
      </Stack>

      {isLoading && (
        <Box display="flex" justifyContent="center" pt={8}>
          <CircularProgress size={60} />
        </Box>
      )}
      {isError && (
        <Alert severity="error">Impossible de charger vos ordres de réparation.</Alert>
      )}

      {!isLoading && openOrders.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">
            Aucun ordre de réparation assigné pour le moment.
          </Typography>
        </Paper>
      )}

      {openOrders.map((ro) => (
        <ROCard key={ro.id} ro={ro} />
      ))}
    </Box>
  )
}
