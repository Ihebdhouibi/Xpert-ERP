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
import { PermissionGate } from '../../components/auth/PermissionGate'
import {
  repairOrderApi,
  STATUS_LABELS,
  ALLOWED_TRANSITIONS,
  type ROStatus,
  type RepairOrderDetail,
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
        setError(`Transition invalide : ${(detail as { from_status: string; to_status: string }).from_status} → ${(detail as { from_status: string; to_status: string }).to_status}`)
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
