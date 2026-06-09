import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import LockOpenRoundedIcon from '@mui/icons-material/LockOpenRounded'
import LockRoundedIcon from '@mui/icons-material/LockRounded'
import RadioButtonCheckedRoundedIcon from '@mui/icons-material/RadioButtonCheckedRounded'
import { cashSessionApi, type CashSessionOut } from '../../lib/cashSessionApi'
import { PAYMENT_METHOD_LABELS, type PaymentMethod } from '../../lib/paymentApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

const columns: Column<CashSessionOut>[] = [
  {
    id: 'id',
    label: 'Session',
    width: 90,
    render: row => (
      <Typography variant="body2" fontWeight={700} fontFamily="monospace">
        #{row.id}
      </Typography>
    ),
  },
  {
    id: 'opened',
    label: 'Ouverture',
    render: row => (
      <Typography variant="body2">
        {new Date(row.opened_at).toLocaleString('fr-FR', {
          day: '2-digit', month: '2-digit', year: 'numeric',
          hour: '2-digit', minute: '2-digit',
        })}
      </Typography>
    ),
  },
  {
    id: 'closed',
    label: 'Clôture',
    render: row =>
      row.closed_at ? (
        <Typography variant="body2">
          {new Date(row.closed_at).toLocaleString('fr-FR', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
          })}
        </Typography>
      ) : (
        <Stack direction="row" alignItems="center" spacing={0.75}>
          <RadioButtonCheckedRoundedIcon sx={{ color: '#16A34A', fontSize: 14 }} />
          <Typography variant="body2" color="success.main" fontWeight={600}>En cours</Typography>
        </Stack>
      ),
  },
  {
    id: 'cash',
    label: 'Caisse comptée',
    align: 'right',
    render: row =>
      row.counted_total_cash != null ? (
        <Stack alignItems="flex-end">
          <Typography variant="body2" fontWeight={600}>{formatMinor(row.counted_total_cash)}</Typography>
          {row.difference != null && row.difference !== 0 && (
            <Typography
              variant="caption"
              color={row.difference < 0 ? 'error.main' : 'success.main'}
              fontWeight={600}
            >
              {row.difference > 0 ? '+' : ''}{formatMinor(row.difference)}
            </Typography>
          )}
        </Stack>
      ) : <Typography variant="caption" color="text.disabled">—</Typography>,
  },
  {
    id: 'status',
    label: 'Statut',
    width: 100,
    render: row => <StatusChip status={row.status} />,
  },
]

function CurrentSessionBanner({
  session,
  onClose,
}: {
  session: CashSessionOut
  onClose: () => void
}) {
  return (
    <Alert
      severity="success"
      icon={<RadioButtonCheckedRoundedIcon />}
      action={
        <Button
          size="small"
          color="inherit"
          variant="outlined"
          startIcon={<LockRoundedIcon />}
          onClick={onClose}
          sx={{ fontWeight: 600 }}
        >
          Clôturer
        </Button>
      }
      sx={{ mb: 2.5, borderRadius: 2, fontWeight: 500 }}
    >
      Session #{session.id} ouverte depuis le{' '}
      {new Date(session.opened_at).toLocaleString('fr-FR', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })}
    </Alert>
  )
}

export function CashSessionsPage() {
  const qc = useQueryClient()
  const { success, error } = useToast()
  const [page, setPage] = useState(0)
  const [openOpen, setOpenOpen] = useState(false)
  const [openingFloat, setOpeningFloat] = useState('')
  const [closeOpen, setCloseOpen] = useState(false)
  const [countedCash, setCountedCash] = useState('')
  const [closingReason, setClosingReason] = useState('')

  const { data: current } = useQuery({
    queryKey: ['cash-session-current'],
    queryFn: cashSessionApi.getCurrent,
    staleTime: 10_000,
    refetchOnWindowFocus: true,
    // Poll only while a session is open so the expected cash stays current.
    refetchInterval: q => (q.state.data ? 15_000 : false),
  })

  // Live per-method tallies for the open session (income as payments come in).
  const { data: zreport } = useQuery({
    queryKey: ['cash-session-zreport', current?.id],
    queryFn: () => cashSessionApi.getZReport(current!.id),
    enabled: !!current,
    staleTime: 10_000,
    refetchOnWindowFocus: true,
    refetchInterval: 15_000,
  })

  const { data, isLoading, isError } = useQuery({
    queryKey: ['cash-sessions', page],
    queryFn: () => cashSessionApi.list({ page: page + 1, page_size: 20 }),
  })

  const openMutation = useMutation({
    mutationFn: (opening: number) => cashSessionApi.open({ opening_float: opening }),
    onSuccess: () => {
      success('Session de caisse ouverte.')
      setOpenOpen(false)
      setOpeningFloat('')
      void qc.invalidateQueries({ queryKey: ['cash-session-current'] })
      void qc.invalidateQueries({ queryKey: ['cash-sessions'] })
    },
    onError: () => error('Impossible d\'ouvrir la session. Une session est peut-être déjà ouverte.'),
  })

  const handleOpen = () => {
    const minor = openingFloat ? Math.round(parseFloat(openingFloat) * 100) : 0
    openMutation.mutate(minor)
  }

  const closeMutation = useMutation({
    mutationFn: ({ id, counted }: { id: number; counted: number; reason?: string }) =>
      cashSessionApi.close(id, { counted_total_cash: counted, closing_reason: closingReason || null }),
    onSuccess: () => {
      success('Session clôturée avec succès.')
      setCloseOpen(false)
      setCountedCash('')
      setClosingReason('')
      void qc.invalidateQueries({ queryKey: ['cash-session-current'] })
      void qc.invalidateQueries({ queryKey: ['cash-sessions'] })
    },
    onError: () => error('Erreur lors de la clôture.'),
  })

  const handleClose = () => {
    if (!current || !countedCash) return
    closeMutation.mutate({ id: current.id, counted: Math.round(parseFloat(countedCash) * 100) })
  }

  return (
    <Box>
      <PageHeader
        title="Sessions de caisse"
        subtitle="Gérez l'ouverture et la clôture des caisses journalières"
        actions={
          !current && (
            <Button
              variant="contained"
              startIcon={<LockOpenRoundedIcon />}
              onClick={() => setOpenOpen(true)}
              disabled={openMutation.isPending}
            >
              Ouvrir une session
            </Button>
          )
        }
      />

      {current && (
        <CurrentSessionBanner session={current} onClose={() => setCloseOpen(true)} />
      )}

      {current && (
        <Card variant="outlined" sx={{ mb: 2.5, borderRadius: 2 }}>
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5}>
              <Typography variant="subtitle2" fontWeight={700}>Encaissements de la session</Typography>
              <Typography variant="caption" color="text.secondary">Mis à jour automatiquement</Typography>
            </Stack>
            <Stack spacing={1}>
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="body2" color="text.secondary">Fond de caisse (ouverture)</Typography>
                <Typography variant="body2" fontWeight={600}>{formatMinor(current.opening_float ?? 0)}</Typography>
              </Stack>
              {(zreport?.tallies ?? []).length === 0 ? (
                <Typography variant="body2" color="text.disabled">Aucun encaissement pour le moment.</Typography>
              ) : (
                zreport!.tallies.map(t => (
                  <Stack key={t.payment_method} direction="row" justifyContent="space-between">
                    <Typography variant="body2" color="text.secondary">
                      {PAYMENT_METHOD_LABELS[t.payment_method as PaymentMethod] ?? t.payment_method}
                      <Typography component="span" variant="caption" color="text.disabled" ml={0.75}>
                        ({t.count})
                      </Typography>
                    </Typography>
                    <Typography variant="body2" fontWeight={600}>{formatMinor(t.total_minor)}</Typography>
                  </Stack>
                ))
              )}
              <Divider />
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="body2" fontWeight={700}>Total encaissé</Typography>
                <Typography variant="body2" fontWeight={700} color="success.main">
                  {formatMinor(zreport?.total_all_methods ?? 0)}
                </Typography>
              </Stack>
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="body2" fontWeight={700}>Caisse espèces attendue</Typography>
                <Typography variant="body2" fontWeight={700}>
                  {current.expected_cash_so_far != null ? formatMinor(current.expected_cash_so_far) : '—'}
                </Typography>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      )}

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        getRowKey={r => String(r.id)}
        loading={isLoading}
        error={isError}
        total={data?.total}
        page={page}
        pageSize={20}
        onPageChange={setPage}
        emptyTitle="Aucune session"
        emptyDescription="Ouvrez votre première session de caisse pour commencer."
      />

      {/* Open session dialog */}
      <Dialog open={openOpen} onClose={() => setOpenOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <LockOpenRoundedIcon sx={{ color: 'primary.main', fontSize: 20 }} />
          Ouvrir une session
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} pt={1}>
            <TextField
              label="Fond de caisse (€)"
              type="number"
              value={openingFloat}
              onChange={e => setOpeningFloat(e.target.value)}
              fullWidth
              placeholder="Ex: 100.00"
              helperText="Montant d'espèces présent dans la caisse à l'ouverture (laisser vide pour 0)"
              autoFocus
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setOpenOpen(false)}>Annuler</Button>
          <Button
            variant="contained"
            startIcon={<LockOpenRoundedIcon />}
            onClick={handleOpen}
            disabled={openMutation.isPending}
          >
            Ouvrir
          </Button>
        </DialogActions>
      </Dialog>

      {/* Close session dialog */}
      <Dialog open={closeOpen} onClose={() => setCloseOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <LockRoundedIcon sx={{ color: 'primary.main', fontSize: 20 }} />
          Clôturer la session
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} pt={1}>
            <Card variant="outlined" sx={{ bgcolor: '#F8FAFC' }}>
              <CardContent sx={{ p: 2 }}>
                <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                  Récapitulatif de la session #{current?.id}
                </Typography>
                <Stack direction="row" justifyContent="space-between" mb={0.5}>
                  <Typography variant="body2" color="text.secondary">Fond de caisse (ouverture)</Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {formatMinor(current?.opening_float ?? 0)}
                  </Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Caisse espèces attendue</Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {current?.expected_cash_so_far != null
                      ? formatMinor(current.expected_cash_so_far)
                      : '—'}
                  </Typography>
                </Stack>
              </CardContent>
            </Card>
            <TextField
              label="Montant espèces compté (€)"
              type="number"
              value={countedCash}
              onChange={e => setCountedCash(e.target.value)}
              fullWidth
              placeholder="Ex: 250.00"
              helperText="Entrez le montant physiquement compté dans la caisse"
            />
            <TextField
              label="Motif de clôture (optionnel)"
              value={closingReason}
              onChange={e => setClosingReason(e.target.value)}
              fullWidth
              multiline
              rows={2}
            />
            {countedCash && current?.expected_cash_so_far != null && (
              <Box>
                <Divider sx={{ mb: 1.5 }} />
                {(() => {
                  const counted = Math.round(parseFloat(countedCash) * 100)
                  const diff = counted - (current.expected_cash_so_far ?? 0)
                  return (
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2" fontWeight={600}>Écart</Typography>
                      <Typography
                        variant="body1"
                        fontWeight={700}
                        color={diff === 0 ? 'success.main' : diff > 0 ? 'warning.main' : 'error.main'}
                      >
                        {diff > 0 ? '+' : ''}{formatMinor(diff)}
                      </Typography>
                    </Stack>
                  )
                })()}
              </Box>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setCloseOpen(false)}>Annuler</Button>
          <Button
            variant="contained"
            color="error"
            startIcon={<LockRoundedIcon />}
            onClick={handleClose}
            disabled={!countedCash || closeMutation.isPending}
          >
            Clôturer
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
