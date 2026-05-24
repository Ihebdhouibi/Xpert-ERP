import { useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
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
  Typography,
} from '@mui/material'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import SwapHorizIcon from '@mui/icons-material/SwapHoriz'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import StopIcon from '@mui/icons-material/Stop'
import SendIcon from '@mui/icons-material/Send'
import { PermissionGate } from '../../components/auth/PermissionGate'
import {
  repairOrderApi,
  STATUS_LABELS,
  ALLOWED_TRANSITIONS,
  type ROStatus,
  type RepairOrderDetail,
  type TimeEntry,
  type Comment,
} from '../../lib/repairOrderApi'

const STATUS_COLORS: Record<
  ROStatus,
  'default' | 'info' | 'warning' | 'success' | 'error' | 'primary'
> = {
  created: 'default',
  diagnosis: 'info',
  in_repair: 'primary',
  finished: 'warning',
  delivered: 'success',
  paused_parts: 'error',
  paused_approval: 'error',
}

function formatMoney(minor: number | null, currency: string | null): string {
  if (minor === null) return '-'
  if (!currency) return `${minor}`
  return (minor / 100).toLocaleString('fr-FR', { style: 'currency', currency })
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body1">{value || '-'}</Typography>
    </Box>
  )
}

function StatusTransitionPanel({
  ro,
  onTransitioned,
}: {
  ro: RepairOrderDetail
  onTransitioned: () => void
}) {
  const [targetStatus, setTargetStatus] = useState<ROStatus | ''>('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const allowed = ALLOWED_TRANSITIONS[ro.status]

  const mutation = useMutation({
    mutationFn: () =>
      repairOrderApi.transition(ro.id, {
        new_status: targetStatus as ROStatus,
        reason: reason || null,
      }),
    onSuccess: () => {
      setTargetStatus('')
      setReason('')
      setError(null)
      onTransitioned()
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail
      if (detail && typeof detail === 'object' && 'code' in detail) {
        const d = detail as unknown as { from_status?: string; to_status?: string }
        setError(`Transition invalide : ${d.from_status ?? '?'} → ${d.to_status ?? '?'}`)
      } else {
        setError('Erreur lors du changement de statut.')
      }
    },
  })

  if (allowed.length === 0) return null

  return (
    <Box>
      <Typography variant="overline" color="text.secondary">
        Changer le statut
      </Typography>
      <Stack direction="row" spacing={1} alignItems="center" mt={0.5}>
        <Select
          size="small"
          displayEmpty
          value={targetStatus}
          onChange={(e) => setTargetStatus(e.target.value as ROStatus)}
          sx={{ minWidth: 200 }}
        >
          <MenuItem value="">Sélectionner...</MenuItem>
          {allowed.map((s) => (
            <MenuItem key={s} value={s}>
              {STATUS_LABELS[s]}
            </MenuItem>
          ))}
        </Select>
        <TextField
          size="small"
          placeholder="Motif (optionnel)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          sx={{ flex: 1 }}
        />
        <Button
          variant="contained"
          size="small"
          startIcon={<SwapHorizIcon />}
          disabled={!targetStatus || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          Appliquer
        </Button>
      </Stack>
      {error && (
        <Alert severity="error" sx={{ mt: 1 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
    </Box>
  )
}

function TimerPanel({ publicId }: { publicId: string }) {
  const queryClient = useQueryClient()
  const [stopNotes, setStopNotes] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data } = useQuery({
    queryKey: ['time-entries', publicId],
    queryFn: () => repairOrderApi.listTimeEntries(publicId),
  })

  const openEntry: TimeEntry | undefined = data?.items.find((e) => e.ended_at === null)

  const startMutation = useMutation({
    mutationFn: () => repairOrderApi.startTimeEntry(publicId),
    onSuccess: () => {
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['time-entries', publicId] })
    },
    onError: () => setError('Une session de pointage est déjà ouverte.'),
  })

  const stopMutation = useMutation({
    mutationFn: () => repairOrderApi.stopTimeEntry(publicId, stopNotes || undefined),
    onSuccess: () => {
      setStopNotes('')
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['time-entries', publicId] })
    },
    onError: () => setError('Aucune session ouverte à arrêter.'),
  })

  const totalMinutes = data?.items
    .filter((e) => e.duration_minutes !== null)
    .reduce((sum, e) => sum + (e.duration_minutes ?? 0), 0) ?? 0

  return (
    <Box>
      <Typography variant="overline" color="text.secondary">
        Pointage du temps
      </Typography>
      <Stack direction="row" spacing={1} alignItems="center" mt={0.5} flexWrap="wrap">
        {openEntry ? (
          <>
            <Chip
              icon={<PlayArrowIcon />}
              label={`En cours depuis ${new Date(openEntry.started_at).toLocaleTimeString('fr-FR')}`}
              color="success"
              variant="outlined"
            />
            <TextField
              size="small"
              placeholder="Note de fin (optionnel)"
              value={stopNotes}
              onChange={(e) => setStopNotes(e.target.value)}
              sx={{ flex: 1, minWidth: 200 }}
            />
            <Button
              variant="contained"
              color="error"
              size="small"
              startIcon={<StopIcon />}
              disabled={stopMutation.isPending}
              onClick={() => stopMutation.mutate()}
            >
              Arrêter
            </Button>
          </>
        ) : (
          <Button
            variant="outlined"
            size="small"
            startIcon={<PlayArrowIcon />}
            disabled={startMutation.isPending}
            onClick={() => startMutation.mutate()}
          >
            Démarrer une session
          </Button>
        )}
        {totalMinutes > 0 && (
          <Typography variant="body2" color="text.secondary">
            Total : {Math.floor(totalMinutes / 60)}h{String(totalMinutes % 60).padStart(2, '0')}
          </Typography>
        )}
      </Stack>
      {error && (
        <Alert severity="error" sx={{ mt: 1 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      {data && data.items.length > 0 && (
        <Table size="small" sx={{ mt: 2 }}>
          <TableHead>
            <TableRow>
              <TableCell>Début</TableCell>
              <TableCell>Fin</TableCell>
              <TableCell align="right">Durée (min)</TableCell>
              <TableCell>Note</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.items.map((e) => (
              <TableRow key={e.id}>
                <TableCell>{new Date(e.started_at).toLocaleString('fr-FR')}</TableCell>
                <TableCell>
                  {e.ended_at ? new Date(e.ended_at).toLocaleString('fr-FR') : '—'}
                </TableCell>
                <TableCell align="right">{e.duration_minutes ?? '—'}</TableCell>
                <TableCell>{e.notes ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Box>
  )
}

function CommentsPanel({ publicId }: { publicId: string }) {
  const queryClient = useQueryClient()
  const [newBody, setNewBody] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editBody, setEditBody] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data } = useQuery({
    queryKey: ['comments', publicId],
    queryFn: () => repairOrderApi.listComments(publicId),
  })

  const createMutation = useMutation({
    mutationFn: () => repairOrderApi.createComment(publicId, newBody),
    onSuccess: () => {
      setNewBody('')
      setError(null)
      queryClient.invalidateQueries({ queryKey: ['comments', publicId] })
    },
    onError: () => setError('Impossible d\'ajouter le commentaire.'),
  })

  const updateMutation = useMutation({
    mutationFn: (comment: Comment) =>
      repairOrderApi.updateComment(publicId, comment.id, editBody),
    onSuccess: () => {
      setEditingId(null)
      setEditBody('')
      queryClient.invalidateQueries({ queryKey: ['comments', publicId] })
    },
    onError: () => setError('Impossible de modifier le commentaire.'),
  })

  const deleteMutation = useMutation({
    mutationFn: (commentId: number) =>
      repairOrderApi.deleteComment(publicId, commentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', publicId] })
    },
    onError: () => setError('Impossible de supprimer le commentaire.'),
  })

  return (
    <Box>
      <Typography variant="overline" color="text.secondary">
        Commentaires
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mt: 1, mb: 1 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Stack spacing={1.5} mt={1}>
        {data?.items.map((comment) => (
          <Box key={comment.id} sx={{ borderLeft: '3px solid', borderColor: 'divider', pl: 1.5 }}>
            {editingId === comment.id ? (
              <Stack direction="row" spacing={1} alignItems="flex-start">
                <TextField
                  size="small"
                  multiline
                  value={editBody}
                  onChange={(e) => setEditBody(e.target.value)}
                  sx={{ flex: 1 }}
                />
                <Button
                  size="small"
                  variant="contained"
                  disabled={updateMutation.isPending || !editBody.trim()}
                  onClick={() => updateMutation.mutate(comment)}
                >
                  Sauvegarder
                </Button>
                <Button size="small" onClick={() => setEditingId(null)}>
                  Annuler
                </Button>
              </Stack>
            ) : (
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box>
                  <Typography variant="body2" whiteSpace="pre-wrap">
                    {comment.body}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(comment.created_at).toLocaleString('fr-FR')}
                    {comment.created_at !== comment.updated_at && ' (modifié)'}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={0.5}>
                  <IconButton
                    size="small"
                    onClick={() => {
                      setEditingId(comment.id)
                      setEditBody(comment.body)
                    }}
                  >
                    <EditIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    size="small"
                    color="error"
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(comment.id)}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Stack>
              </Stack>
            )}
          </Box>
        ))}
        {data?.items.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            Aucun commentaire.
          </Typography>
        )}
      </Stack>

      <Stack direction="row" spacing={1} alignItems="flex-end" mt={2}>
        <TextField
          size="small"
          multiline
          placeholder="Ajouter un commentaire..."
          value={newBody}
          onChange={(e) => setNewBody(e.target.value)}
          sx={{ flex: 1 }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && newBody.trim()) {
              createMutation.mutate()
            }
          }}
        />
        <Button
          variant="contained"
          size="small"
          startIcon={<SendIcon />}
          disabled={createMutation.isPending || !newBody.trim()}
          onClick={() => createMutation.mutate()}
        >
          Envoyer
        </Button>
      </Stack>
    </Box>
  )
}

export function RepairOrderDetailPage() {
  const { publicId = '' } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['repair-order', publicId],
    queryFn: () => repairOrderApi.get(publicId),
    enabled: !!publicId,
  })

  const handleDelete = async () => {
    try {
      await repairOrderApi.remove(publicId)
      await queryClient.invalidateQueries({ queryKey: ['repair-orders'] })
      navigate('/repair-orders', { replace: true })
    } catch {
      setActionError('Erreur lors de la suppression.')
      setConfirmDelete(false)
    }
  }

  if (isLoading) {
    return (
      <Box p={4} display="flex" justifyContent="center">
        <CircularProgress />
      </Box>
    )
  }
  if (isError || !data) {
    return (
      <Box p={4}>
        <Alert severity="error">Impossible de charger cet ordre de réparation.</Alert>
        <Button sx={{ mt: 2 }} onClick={() => navigate('/repair-orders')}>
          Retour à la liste
        </Button>
      </Box>
    )
  }

  const ro: RepairOrderDetail = data

  return (
    <Box p={4} maxWidth={960} mx="auto">
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        mb={3}
      >
        <Box>
          <Typography variant="h5" fontWeight={700}>
            Ordre de réparation
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {ro.description}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip
            color={STATUS_COLORS[ro.status]}
            label={STATUS_LABELS[ro.status]}
          />
          <PermissionGate permission="repair_order.update">
            <Button
              startIcon={<EditIcon />}
              component={RouterLink}
              to={`/repair-orders/${ro.id}/edit`}
            >
              Modifier
            </Button>
          </PermissionGate>
          <PermissionGate permission="repair_order.delete">
            <Button
              color="error"
              startIcon={<DeleteIcon />}
              onClick={() => setConfirmDelete(true)}
            >
              Supprimer
            </Button>
          </PermissionGate>
        </Stack>
      </Stack>

      {actionError && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setActionError(null)}>
          {actionError}
        </Alert>
      )}

      {/* General info */}
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="overline" color="text.secondary">
          Informations générales
        </Typography>
        <Grid container spacing={2} mt={0.5}>
          <Grid item xs={6} sm={3}>
            <Field label="Client ID" value={ro.customer_id} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Field label="Véhicule ID" value={ro.vehicle_id ?? '-'} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Field label="Priorité" value={ro.priority ?? '-'} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Field
              label="Créé le"
              value={new Date(ro.created_at).toLocaleDateString('fr-FR')}
            />
          </Grid>
          <Grid item xs={6} sm={4}>
            <Field
              label="Coût estimé"
              value={formatMoney(ro.estimated_cost_minor, ro.estimated_cost_currency)}
            />
          </Grid>
          <Grid item xs={6} sm={4}>
            <Field
              label="Coût réel"
              value={formatMoney(ro.actual_cost_minor, ro.estimated_cost_currency)}
            />
          </Grid>
          <Grid item xs={6} sm={4}>
            <Field label="Version" value={ro.version} />
          </Grid>
        </Grid>
        {ro.notes && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="overline" color="text.secondary">
              Notes
            </Typography>
            <Typography mt={0.5} whiteSpace="pre-wrap">
              {ro.notes}
            </Typography>
          </>
        )}
      </Paper>

      {/* Status transition */}
      <PermissionGate permission="repair_order.transition">
        <Paper sx={{ p: 3, mb: 2 }}>
          <StatusTransitionPanel ro={ro} onTransitioned={() => refetch()} />
        </Paper>
      </PermissionGate>

      {/* Labor lines */}
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="overline" color="text.secondary">
          Main d'œuvre
        </Typography>
        {ro.labor_lines.length === 0 ? (
          <Typography color="text.secondary" mt={1}>
            Aucune ligne de main d'œuvre.
          </Typography>
        ) : (
          <Table size="small" sx={{ mt: 1 }}>
            <TableHead>
              <TableRow>
                <TableCell>Type</TableCell>
                <TableCell align="right">Durée (min)</TableCell>
                <TableCell align="right">Taux</TableCell>
                <TableCell align="right">Montant</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {ro.labor_lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell>{line.labor_type}</TableCell>
                  <TableCell align="right">{line.duration_minutes}</TableCell>
                  <TableCell align="right">
                    {formatMoney(line.rate_minor, ro.estimated_cost_currency)}
                  </TableCell>
                  <TableCell align="right">
                    {formatMoney(line.amount_minor, ro.estimated_cost_currency)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>

      {/* Part lines */}
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="overline" color="text.secondary">
          Pièces
        </Typography>
        {ro.part_lines.length === 0 ? (
          <Typography color="text.secondary" mt={1}>
            Aucune pièce.
          </Typography>
        ) : (
          <Table size="small" sx={{ mt: 1 }}>
            <TableHead>
              <TableRow>
                <TableCell>Pièce</TableCell>
                <TableCell align="right">Qté</TableCell>
                <TableCell align="right">Prix unitaire</TableCell>
                <TableCell align="right">Montant</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {ro.part_lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell>{line.part_name}</TableCell>
                  <TableCell align="right">{line.quantity}</TableCell>
                  <TableCell align="right">
                    {formatMoney(line.unit_cost_minor, ro.estimated_cost_currency)}
                  </TableCell>
                  <TableCell align="right">
                    {formatMoney(line.amount_minor, ro.estimated_cost_currency)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>

      {/* Time tracking */}
      <PermissionGate permission="repair_order.update">
        <Paper sx={{ p: 3, mb: 2 }}>
          <TimerPanel publicId={publicId} />
        </Paper>
      </PermissionGate>

      {/* Comments */}
      <Paper sx={{ p: 3, mb: 2 }}>
        <CommentsPanel publicId={publicId} />
      </Paper>

      {/* Status history */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="overline" color="text.secondary">
          Historique des statuts
        </Typography>
        {ro.status_events.length === 0 ? (
          <Typography color="text.secondary" mt={1}>
            Aucun historique.
          </Typography>
        ) : (
          <Table size="small" sx={{ mt: 1 }}>
            <TableHead>
              <TableRow>
                <TableCell>De</TableCell>
                <TableCell>Vers</TableCell>
                <TableCell>Date</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {ro.status_events.map((evt) => (
                <TableRow key={evt.id}>
                  <TableCell>
                    {evt.old_status
                      ? STATUS_LABELS[evt.old_status as ROStatus] ?? evt.old_status
                      : '-'}
                  </TableCell>
                  <TableCell>
                    {STATUS_LABELS[evt.new_status as ROStatus] ?? evt.new_status}
                  </TableCell>
                  <TableCell>
                    {new Date(evt.occurred_at).toLocaleString('fr-FR')}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Paper>

      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)}>
        <DialogTitle>Supprimer cet ordre de réparation ?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            L'ordre sera archivé et n'apparaîtra plus dans la liste.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(false)}>Annuler</Button>
          <Button color="error" onClick={handleDelete}>
            Supprimer
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
