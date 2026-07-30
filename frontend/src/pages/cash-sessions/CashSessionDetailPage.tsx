import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
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
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import LockRoundedIcon from '@mui/icons-material/LockRounded'
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded'
import RadioButtonCheckedRoundedIcon from '@mui/icons-material/RadioButtonCheckedRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded'
import { cashSessionApi } from '../../lib/cashSessionApi'
import type { SessionTransactionOut } from '../../lib/cashSessionApi'
import { PAYMENT_METHOD_LABELS, type PaymentMethod } from '../../lib/paymentApi'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

const fmt = (v: number) => formatMinor(v)

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })

const METHOD_COLOR: Record<string, 'default' | 'success' | 'primary' | 'warning'> = {
  cash: 'success',
  card: 'primary',
  wire: 'warning',
  check: 'default',
}

// Movement type → chip label + colour (green = money in, red = money out,
// slate = advance/deposit which is a distinct process).
const KIND_META: Record<string, { label: string; color: 'success' | 'error' | 'info' }> = {
  payment: { label: 'Paiement', color: 'success' },
  advance: { label: 'Acompte', color: 'info' },
  refund: { label: 'Remboursement', color: 'error' },
  supplier_payment: { label: 'Paiement fournisseur', color: 'error' },
}

// Threshold below which we show no discrepancy warning (10 cents)
const DIFF_ALERT_THRESHOLD = 10

export function CashSessionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const sessionId = Number(id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { success, error } = useToast()

  const [closeOpen, setCloseOpen] = useState(false)
  const [countedCash, setCountedCash] = useState('')
  const [closingReason, setClosingReason] = useState('')
  const [diffAcknowledged, setDiffAcknowledged] = useState(false)

  const { data: session, isLoading } = useQuery({
    queryKey: ['cash-session', sessionId],
    queryFn: () => cashSessionApi.get(sessionId),
  })

  const { data: zreport } = useQuery({
    queryKey: ['cash-session-zreport', sessionId],
    queryFn: () => cashSessionApi.getZReport(sessionId),
    enabled: !!sessionId,
    refetchInterval: session?.status === 'open' ? 15_000 : false,
  })

  const { data: transactions = [] } = useQuery({
    queryKey: ['cash-session-transactions', sessionId],
    queryFn: () => cashSessionApi.listTransactions(sessionId),
    enabled: !!sessionId,
    refetchInterval: session?.status === 'open' ? 15_000 : false,
  })

  const navigateTransaction = (t: SessionTransactionOut) => {
    if (t.kind === 'refund' && t.credit_note_id != null) {
      navigate(`/credit-notes/${t.credit_note_id}`)
    } else if (t.kind === 'supplier_payment') {
      navigate('/supplier-invoices')
    } else if (t.invoice_public_id) {
      navigate(`/invoices/${t.invoice_public_id}`)
    } else if (t.customer_public_id) {
      navigate(`/customers/${t.customer_public_id}`)
    }
  }

  const countedMinor = countedCash ? Math.round(parseFloat(countedCash) * 100) : null
  const expectedMinor = session?.expected_cash_so_far ?? session?.expected_total_cash ?? null
  const liveDiff = countedMinor != null && expectedMinor != null ? countedMinor - expectedMinor : null
  const hasDiff = liveDiff != null && Math.abs(liveDiff) >= DIFF_ALERT_THRESHOLD
  const canClose = countedCash !== '' && !isNaN(parseFloat(countedCash)) && (!hasDiff || diffAcknowledged)

  const closeMutation = useMutation({
    mutationFn: () =>
      cashSessionApi.close(sessionId, {
        counted_total_cash: countedMinor!,
        closing_reason: closingReason || null,
      }),
    onSuccess: () => {
      success('Session clôturée avec succès.')
      setCloseOpen(false)
      setCountedCash('')
      setClosingReason('')
      setDiffAcknowledged(false)
      void qc.invalidateQueries({ queryKey: ['cash-session', sessionId] })
      void qc.invalidateQueries({ queryKey: ['cash-session-current'] })
      void qc.invalidateQueries({ queryKey: ['cash-sessions'] })
    },
    onError: () => error('Erreur lors de la clôture.'),
  })

  if (isLoading || !session) {
    return (
      <Box p={3}>
        <Typography color="text.secondary">Chargement…</Typography>
      </Box>
    )
  }

  const isOpen = session.status === 'open'
  const storedDiff = session.difference

  return (
    <Box p={3}>
      {/* Header */}
      <Stack direction="row" alignItems="center" spacing={2} mb={3}>
        <Tooltip title="Retour aux sessions">
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/cash-sessions')}
            size="small"
            variant="outlined"
            color="inherit"
          >
            Retour
          </Button>
        </Tooltip>
        <Typography variant="h5" fontWeight={700}>
          Session #{session.id}
        </Typography>
        {isOpen ? (
          <Chip
            icon={<RadioButtonCheckedRoundedIcon sx={{ fontSize: '14px !important' }} />}
            label="En cours"
            color="success"
            size="small"
            sx={{ fontWeight: 600 }}
          />
        ) : (
          <Chip label="Clôturée" size="small" sx={{ fontWeight: 600 }} />
        )}
        <Box flexGrow={1} />
        <Button
          variant="outlined"
          startIcon={<PictureAsPdfRoundedIcon />}
          href={`/api/v1/cash-sessions/${session.id}/z-report/pdf`}
          target="_blank"
          size="small"
        >
          Rapport Z (PDF)
        </Button>
        {isOpen && (
          <Button
            variant="contained"
            color="error"
            startIcon={<LockRoundedIcon />}
            onClick={() => setCloseOpen(true)}
            size="small"
          >
            Clôturer la session
          </Button>
        )}
      </Stack>

      {/* Info row */}
      <Stack direction="row" spacing={1} mb={3} flexWrap="wrap" useFlexGap>
        <Typography variant="body2" color="text.secondary">
          Ouverte le <strong>{fmtDate(session.opened_at)}</strong>
        </Typography>
        {session.closed_at && (
          <>
            <Typography variant="body2" color="text.secondary">·</Typography>
            <Typography variant="body2" color="text.secondary">
              Clôturée le <strong>{fmtDate(session.closed_at)}</strong>
            </Typography>
          </>
        )}
      </Stack>

      {/* Summary cards */}
      <Grid container spacing={2} mb={3}>
        {/* Fond de caisse */}
        <Grid item xs={12} sm={6} md={3}>
          <Card variant="outlined" sx={{ borderRadius: 2, height: '100%' }}>
            <CardContent>
              <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
                Fond de caisse
              </Typography>
              <Typography variant="h6" fontWeight={700}>
                {fmt(session.opening_float)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Montant à l'ouverture
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Total encaissé */}
        <Grid item xs={12} sm={6} md={3}>
          <Card variant="outlined" sx={{ borderRadius: 2, height: '100%' }}>
            <CardContent>
              <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
                Total encaissé
              </Typography>
              <Typography variant="h6" fontWeight={700} color="success.main">
                {fmt(zreport?.total_all_methods ?? 0)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Tous moyens confondus
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Espèces attendues */}
        <Grid item xs={12} sm={6} md={3}>
          <Card variant="outlined" sx={{ borderRadius: 2, height: '100%' }}>
            <CardContent>
              <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
                Espèces attendues
              </Typography>
              <Typography variant="h6" fontWeight={700}>
                {isOpen
                  ? fmt(session.expected_cash_so_far ?? 0)
                  : fmt(session.expected_total_cash ?? 0)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Fond + encaissements espèces
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Écart (closed) / Nb transactions (open) */}
        <Grid item xs={12} sm={6} md={3}>
          {isOpen ? (
            <Card variant="outlined" sx={{ borderRadius: 2, height: '100%' }}>
              <CardContent>
                <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
                  Transactions
                </Typography>
                <Typography variant="h6" fontWeight={700}>
                  {transactions.length}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Mouvements enregistrés
                </Typography>
              </CardContent>
            </Card>
          ) : (
            <Card
              variant="outlined"
              sx={{
                borderRadius: 2,
                height: '100%',
                borderColor: storedDiff != null && Math.abs(storedDiff) >= DIFF_ALERT_THRESHOLD
                  ? (storedDiff < 0 ? 'error.main' : 'warning.main')
                  : 'divider',
              }}
            >
              <CardContent>
                <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
                  Écart de caisse
                </Typography>
                {storedDiff == null ? (
                  <Typography variant="h6" color="text.disabled">—</Typography>
                ) : storedDiff === 0 ? (
                  <Stack direction="row" alignItems="center" spacing={0.5}>
                    <CheckCircleOutlineRoundedIcon color="success" fontSize="small" />
                    <Typography variant="h6" fontWeight={700} color="success.main">
                      Aucun écart
                    </Typography>
                  </Stack>
                ) : (
                  <Typography
                    variant="h6"
                    fontWeight={700}
                    color={storedDiff < 0 ? 'error.main' : 'warning.main'}
                  >
                    {storedDiff > 0 ? '+' : ''}{fmt(storedDiff)}
                  </Typography>
                )}
                {session.counted_total_cash != null && (
                  <Typography variant="caption" color="text.secondary">
                    Compté : {fmt(session.counted_total_cash)}
                  </Typography>
                )}
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>

      {/* Closing reason (if any) */}
      {session.closing_reason && (
        <Alert severity="info" sx={{ mb: 3, borderRadius: 2 }}>
          <strong>Motif de l'écart :</strong> {session.closing_reason}
        </Alert>
      )}

      {/* Payment method breakdown */}
      <Card variant="outlined" sx={{ borderRadius: 2, mb: 3 }}>
        <CardContent>
          <Typography variant="subtitle2" fontWeight={700} mb={2}>
            Répartition par moyen de paiement
          </Typography>
          {(zreport?.tallies ?? []).length === 0 ? (
            <Typography variant="body2" color="text.disabled">
              Aucun encaissement enregistré.
            </Typography>
          ) : (
            <Stack spacing={1}>
              {zreport!.tallies.map((t) => (
                <Stack key={t.payment_method} direction="row" alignItems="center" justifyContent="space-between">
                  <Stack direction="row" alignItems="center" spacing={1.5}>
                    <Chip
                      label={PAYMENT_METHOD_LABELS[t.payment_method as PaymentMethod] ?? t.payment_method}
                      size="small"
                      color={METHOD_COLOR[t.payment_method] ?? 'default'}
                      variant="outlined"
                    />
                    <Typography variant="caption" color="text.secondary">
                      {t.count} opération{t.count > 1 ? 's' : ''}
                    </Typography>
                  </Stack>
                  <Typography variant="body2" fontWeight={600}>
                    {fmt(t.total_minor)}
                  </Typography>
                </Stack>
              ))}
              <Divider />
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="body2" fontWeight={700}>Total</Typography>
                <Typography variant="body2" fontWeight={700} color="success.main">
                  {fmt(zreport?.total_all_methods ?? 0)}
                </Typography>
              </Stack>
            </Stack>
          )}
        </CardContent>
      </Card>

      {/* Transaction table */}
      <Card variant="outlined" sx={{ borderRadius: 2 }}>
        <CardContent sx={{ pb: '12px !important' }}>
          <Typography variant="subtitle2" fontWeight={700} mb={2}>
            Historique des transactions ({transactions.length})
          </Typography>
          {transactions.length === 0 ? (
            <Typography variant="body2" color="text.disabled">
              Aucun mouvement enregistré dans cette session.
            </Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary', fontSize: '0.75rem' }}>
                      Date / Heure
                    </TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary', fontSize: '0.75rem' }}>
                      Type
                    </TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary', fontSize: '0.75rem' }}>
                      Référence doc.
                    </TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary', fontSize: '0.75rem' }}>
                      Client / Fournisseur
                    </TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary', fontSize: '0.75rem' }}>
                      Moyen
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700, color: 'text.secondary', fontSize: '0.75rem' }}>
                      Montant
                    </TableCell>
                    <TableCell sx={{ fontWeight: 700, color: 'text.secondary', fontSize: '0.75rem' }}>
                      Encaissé par
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {transactions.map((t) => {
                    const meta = KIND_META[t.kind] ?? { label: t.label, color: 'default' as const }
                    const docLabel = t.invoice_number
                      ?? (t.invoice_id != null ? `#${t.invoice_id}` : null)
                      ?? (t.credit_note_id != null ? `Avoir #${t.credit_note_id}` : null)
                      ?? t.supplier_invoice_number
                    const clickable = t.invoice_public_id != null || t.credit_note_id != null
                      || t.customer_public_id != null || t.kind === 'supplier_payment'
                    return (
                      <TableRow
                        key={`${t.kind}-${t.id}`}
                        hover
                        sx={{ cursor: clickable ? 'pointer' : 'default' }}
                        onClick={clickable ? () => navigateTransaction(t) : undefined}
                      >
                        <TableCell>
                          <Typography variant="body2">
                            {fmtDate(t.occurred_at)}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={meta.label}
                            size="small"
                            color={meta.color}
                            variant="filled"
                            sx={{ fontWeight: 600 }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" fontFamily="monospace" fontWeight={600} color={docLabel ? 'primary.main' : 'text.disabled'}>
                            {docLabel ?? '—'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {t.customer_name ?? t.supplier_name ?? '—'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={PAYMENT_METHOD_LABELS[t.payment_method as PaymentMethod] ?? t.payment_method}
                            size="small"
                            color={METHOD_COLOR[t.payment_method] ?? 'default'}
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Typography
                            variant="body2"
                            fontWeight={700}
                            color={t.direction === 'out' ? 'error.main' : 'success.main'}
                          >
                            {t.direction === 'out' ? '-' : '+'}{fmt(t.amount_minor)}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" color="text.secondary">
                            {t.created_by_name ?? '—'}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* Close session dialog */}
      <Dialog open={closeOpen} onClose={() => setCloseOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <LockRoundedIcon sx={{ color: 'primary.main', fontSize: 20 }} />
          Clôturer la session #{session.id}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} pt={1}>
            {/* Expected breakdown */}
            <Card variant="outlined" sx={{ bgcolor: '#F8FAFC', borderRadius: 2 }}>
              <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                <Typography variant="caption" color="text.secondary" display="block" mb={1} fontWeight={600}>
                  Récapitulatif de la caisse
                </Typography>
                <Stack spacing={0.5}>
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2" color="text.secondary">Fond de caisse</Typography>
                    <Typography variant="body2">{fmt(session.opening_float)}</Typography>
                  </Stack>
                  {(zreport?.tallies ?? []).map((t) => (
                    <Stack key={t.payment_method} direction="row" justifyContent="space-between">
                      <Typography variant="body2" color="text.secondary">
                        {PAYMENT_METHOD_LABELS[t.payment_method as PaymentMethod] ?? t.payment_method}
                        <Typography component="span" variant="caption" color="text.disabled" ml={0.5}>
                          ({t.count})
                        </Typography>
                      </Typography>
                      <Typography variant="body2">{fmt(t.total_minor)}</Typography>
                    </Stack>
                  ))}
                  <Divider sx={{ my: 0.5 }} />
                  <Stack direction="row" justifyContent="space-between">
                    <Typography variant="body2" fontWeight={700}>Espèces attendues</Typography>
                    <Typography variant="body2" fontWeight={700}>
                      {fmt(session.expected_cash_so_far ?? 0)}
                    </Typography>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>

            <TextField
              label="Montant compté en caisse (€)"
              type="number"
              value={countedCash}
              onChange={(e) => {
                setCountedCash(e.target.value)
                setDiffAcknowledged(false)
              }}
              fullWidth
              autoFocus
              placeholder="Ex : 350.00"
              inputProps={{ step: '0.01', min: '0' }}
            />

            {/* Live difference */}
            {liveDiff != null && (
              <Card
                variant="outlined"
                sx={{
                  borderRadius: 2,
                  borderColor: Math.abs(liveDiff) < DIFF_ALERT_THRESHOLD
                    ? 'success.main'
                    : liveDiff < 0 ? 'error.main' : 'warning.main',
                  bgcolor: Math.abs(liveDiff) < DIFF_ALERT_THRESHOLD
                    ? '#F0FDF4'
                    : liveDiff < 0 ? '#FEF2F2' : '#FFFBEB',
                }}
              >
                <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    {Math.abs(liveDiff) < DIFF_ALERT_THRESHOLD ? (
                      <CheckCircleOutlineRoundedIcon color="success" fontSize="small" />
                    ) : (
                      <WarningAmberRoundedIcon
                        sx={{ color: liveDiff < 0 ? 'error.main' : 'warning.main' }}
                        fontSize="small"
                      />
                    )}
                    <Stack>
                      <Typography variant="body2" fontWeight={700}
                        color={
                          Math.abs(liveDiff) < DIFF_ALERT_THRESHOLD ? 'success.main'
                            : liveDiff < 0 ? 'error.main' : 'warning.main'
                        }
                      >
                        {Math.abs(liveDiff) < DIFF_ALERT_THRESHOLD
                          ? 'Caisse équilibrée'
                          : liveDiff < 0
                          ? `Manquant : ${fmt(Math.abs(liveDiff))}`
                          : `Surplus : +${fmt(liveDiff)}`}
                      </Typography>
                      {Math.abs(liveDiff) >= DIFF_ALERT_THRESHOLD && (
                        <Typography variant="caption" color="text.secondary">
                          Écart détecté. Indiquez le motif ci-dessous, ou cochez pour confirmer
                          que cet écart a été approuvé par la direction.
                        </Typography>
                      )}
                    </Stack>
                  </Stack>
                </CardContent>
              </Card>
            )}

            {/* Discrepancy acknowledgement + reason */}
            {hasDiff && (
              <>
                <TextField
                  label="Motif de l'écart (recommandé)"
                  multiline
                  rows={2}
                  value={closingReason}
                  onChange={(e) => setClosingReason(e.target.value)}
                  fullWidth
                  placeholder="Ex : Opération approuvée hors système par le responsable"
                />
                <Button
                  variant={diffAcknowledged ? 'contained' : 'outlined'}
                  color="warning"
                  size="small"
                  onClick={() => setDiffAcknowledged((v) => !v)}
                  startIcon={<WarningAmberRoundedIcon />}
                >
                  {diffAcknowledged
                    ? '✓ Écart confirmé — clôture autorisée'
                    : 'Confirmer l\'écart et autoriser la clôture'}
                </Button>
              </>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setCloseOpen(false)}>
            Annuler
          </Button>
          <Button
            variant="contained"
            color="error"
            startIcon={<LockRoundedIcon />}
            onClick={() => closeMutation.mutate()}
            disabled={!canClose || closeMutation.isPending}
          >
            Clôturer définitivement
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
