import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import CancelRoundedIcon from '@mui/icons-material/CancelRounded'
import AccessTimeRoundedIcon from '@mui/icons-material/AccessTimeRounded'
import { creditLimitRequestApi, type CreditLimitChangeRequestOut } from '../../lib/creditLimitRequestApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { useToast } from '../../contexts/ToastContext'

const STATUS_CONFIG = {
  pending: { label: 'En attente', color: 'warning' as const, icon: <AccessTimeRoundedIcon sx={{ fontSize: 14 }} /> },
  approved: { label: 'Approuvée', color: 'success' as const, icon: <CheckCircleRoundedIcon sx={{ fontSize: 14 }} /> },
  rejected: { label: 'Refusée', color: 'error' as const, icon: <CancelRoundedIcon sx={{ fontSize: 14 }} /> },
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function formatMinor(minor: number, currency: string) {
  return (minor / 100).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ' + currency
}

export function CreditLimitChangeRequestsPage() {
  const { success, error: toastError } = useToast()
  const queryClient = useQueryClient()
  const { id } = useParams<{ id: string }>()
  const targetId = id ? Number(id) : null
  const [statusFilter, setStatusFilter] = useState<string>('pending')
  const [rejectTarget, setRejectTarget] = useState<CreditLimitChangeRequestOut | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const highlightedRowRef = useRef<HTMLTableRowElement | null>(null)
  const [hasScrolled, setHasScrolled] = useState(false)

  const { data: requests = [], isLoading } = useQuery({
    queryKey: ['credit-limit-requests', statusFilter],
    queryFn: () => creditLimitRequestApi.list({ status: statusFilter }),
    refetchInterval: 30_000,
  })

  // Deep-linked from a notification: switch to the request's own status tab.
  const { data: targetRequest } = useQuery({
    queryKey: ['credit-limit-request', targetId],
    queryFn: () => creditLimitRequestApi.get(targetId as number),
    enabled: targetId != null,
  })

  useEffect(() => {
    if (targetRequest) setStatusFilter(targetRequest.status)
  }, [targetRequest])

  useEffect(() => {
    setHasScrolled(false)
  }, [targetId])

  useEffect(() => {
    if (targetId != null && !hasScrolled && highlightedRowRef.current) {
      highlightedRowRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
      setHasScrolled(true)
    }
  }, [requests, targetId, hasScrolled])

  const approveMutation = useMutation({
    mutationFn: (id: number) => creditLimitRequestApi.approve(id),
    onSuccess: () => {
      success('Limite de crédit mise à jour — l\'utilisateur a été notifié.')
      queryClient.invalidateQueries({ queryKey: ['credit-limit-requests'] })
    },
    onError: () => toastError('Impossible d\'approuver la demande.'),
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      creditLimitRequestApi.reject(id, reason || undefined),
    onSuccess: () => {
      success('Demande refusée — l\'utilisateur a été notifié.')
      setRejectTarget(null)
      setRejectReason('')
      queryClient.invalidateQueries({ queryKey: ['credit-limit-requests'] })
    },
    onError: () => toastError('Impossible de refuser la demande.'),
  })

  return (
    <Box>
      <PageHeader title="Demandes de limite de crédit" />

      <Stack direction="row" spacing={1} mb={3}>
        {(['pending', 'approved', 'rejected'] as const).map(s => (
          <Button
            key={s}
            variant={statusFilter === s ? 'contained' : 'outlined'}
            size="small"
            onClick={() => setStatusFilter(s)}
            sx={{ textTransform: 'none', borderRadius: 2 }}
          >
            {STATUS_CONFIG[s].label}
          </Button>
        ))}
      </Stack>

      {isLoading ? (
        <Stack alignItems="center" py={6}>
          <CircularProgress />
        </Stack>
      ) : requests.length === 0 ? (
        <Stack alignItems="center" py={6} spacing={1}>
          <CheckCircleRoundedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />
          <Typography color="text.secondary">
            Aucune demande{statusFilter === 'pending' ? ' en attente' : ''}.
          </Typography>
        </Stack>
      ) : (
        <Table size="small" sx={{ bgcolor: 'background.paper', borderRadius: 2, overflow: 'hidden' }}>
          <TableHead>
            <TableRow sx={{ bgcolor: 'grey.50' }}>
              <TableCell><Typography variant="caption" fontWeight={600}>Client</Typography></TableCell>
              <TableCell><Typography variant="caption" fontWeight={600}>Limite actuelle</Typography></TableCell>
              <TableCell><Typography variant="caption" fontWeight={600}>Limite demandée</Typography></TableCell>
              <TableCell><Typography variant="caption" fontWeight={600}>Motif</Typography></TableCell>
              <TableCell><Typography variant="caption" fontWeight={600}>Demandé le</Typography></TableCell>
              <TableCell><Typography variant="caption" fontWeight={600}>Statut</Typography></TableCell>
              {statusFilter === 'rejected' && (
                <TableCell><Typography variant="caption" fontWeight={600}>Motif du refus</Typography></TableCell>
              )}
              {statusFilter === 'pending' && (
                <TableCell align="right"><Typography variant="caption" fontWeight={600}>Actions</Typography></TableCell>
              )}
            </TableRow>
          </TableHead>
          <TableBody>
            {requests.map(req => {
              const cfg = STATUS_CONFIG[req.status]
              return (
                <TableRow
                  key={req.id}
                  hover
                  ref={req.id === targetId ? highlightedRowRef : undefined}
                  sx={req.id === targetId ? { bgcolor: 'warning.50' } : undefined}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {req.customer_name ?? `Client #${req.customer_id}`}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {formatMinor(req.current_credit_limit_minor, req.requested_credit_currency)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {formatMinor(req.requested_credit_limit_minor, req.requested_credit_currency)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {req.reason}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {formatDate(req.created_at)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={cfg.label}
                      color={cfg.color}
                      size="small"
                      icon={cfg.icon}
                      sx={{ fontWeight: 600 }}
                    />
                  </TableCell>
                  {statusFilter === 'rejected' && (
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {req.rejection_reason || '—'}
                      </Typography>
                    </TableCell>
                  )}
                  {statusFilter === 'pending' && (
                    <TableCell align="right">
                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        <Button
                          size="small"
                          variant="contained"
                          color="success"
                          startIcon={approveMutation.isPending ? <CircularProgress size={12} color="inherit" /> : <CheckCircleRoundedIcon />}
                          disabled={approveMutation.isPending}
                          onClick={() => approveMutation.mutate(req.id)}
                          sx={{ textTransform: 'none', borderRadius: 2 }}
                        >
                          Approuver
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          color="error"
                          startIcon={<CancelRoundedIcon />}
                          onClick={() => { setRejectTarget(req); setRejectReason('') }}
                          sx={{ textTransform: 'none', borderRadius: 2 }}
                        >
                          Refuser
                        </Button>
                      </Stack>
                    </TableCell>
                  )}
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}

      <Dialog
        open={rejectTarget !== null}
        onClose={() => setRejectTarget(null)}
        maxWidth="xs"
        fullWidth
        PaperProps={{ sx: { borderRadius: 3 } }}
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <CancelRoundedIcon sx={{ color: 'error.main', fontSize: 22 }} />
          Refuser la demande
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} pt={1}>
            <Typography variant="body2" color="text.secondary">
              Modification de limite de crédit pour <strong>{rejectTarget?.customer_name}</strong> —{' '}
              {rejectTarget ? formatMinor(rejectTarget.requested_credit_limit_minor, rejectTarget.requested_credit_currency) : ''}
            </Typography>
            <TextField
              label="Motif du refus (optionnel)"
              multiline
              rows={3}
              value={rejectReason}
              onChange={e => setRejectReason(e.target.value)}
              size="small"
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setRejectTarget(null)} disabled={rejectMutation.isPending}>
            Annuler
          </Button>
          <Button
            variant="contained"
            color="error"
            disabled={rejectMutation.isPending}
            startIcon={rejectMutation.isPending ? <CircularProgress size={16} color="inherit" /> : undefined}
            onClick={() => rejectTarget && rejectMutation.mutate({ id: rejectTarget.id, reason: rejectReason })}
          >
            Confirmer le refus
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
