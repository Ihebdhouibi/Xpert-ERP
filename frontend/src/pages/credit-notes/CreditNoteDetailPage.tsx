import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Grid,
  Stack,
  Typography,
} from '@mui/material'
import AccountBalanceRoundedIcon from '@mui/icons-material/AccountBalanceRounded'
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded'
import PublishRoundedIcon from '@mui/icons-material/PublishRounded'
import CancelRoundedIcon from '@mui/icons-material/CancelRounded'
import InfoRoundedIcon from '@mui/icons-material/InfoRounded'
import MoneyOffRoundedIcon from '@mui/icons-material/MoneyOffRounded'
import { creditNoteApi, CREDIT_NOTE_STATUS_LABELS } from '../../lib/creditNoteApi'
import { PAYMENT_METHOD_LABELS } from '../../lib/paymentApi'
import { RecordRefundDialog } from '../../components/credit-note/RecordRefundDialog'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Stack direction="row" justifyContent="space-between" alignItems="flex-start" py={1.25} gap={2}>
      <Typography variant="body2" color="text.secondary" fontWeight={500} flexShrink={0}>
        {label}
      </Typography>
      <Box textAlign="right">
        {value ?? <Typography variant="body2" color="text.disabled">—</Typography>}
      </Box>
    </Stack>
  )
}

export function CreditNoteDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { success, error: toastError } = useToast()

  const [issueOpen, setIssueOpen] = useState(false)
  const [voidOpen, setVoidOpen] = useState(false)
  const [refundOpen, setRefundOpen] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)

  const { data: avoir, isLoading, isError } = useQuery({
    queryKey: ['credit-note', id],
    queryFn: () => creditNoteApi.get(Number(id)),
    enabled: !!id,
  })

  const issueMutation = useMutation({
    mutationFn: () => creditNoteApi.issue(Number(id)),
    onSuccess: updated => {
      success('Avoir émis.')
      setIssueOpen(false)
      qc.setQueryData(['credit-note', id], updated)
      qc.invalidateQueries({ queryKey: ['credit-notes'] })
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.detail
      toastError(typeof detail === 'string' ? detail : 'Impossible d\'émettre l\'avoir.')
      setIssueOpen(false)
    },
  })

  const voidMutation = useMutation({
    mutationFn: () => creditNoteApi.void(Number(id)),
    onSuccess: updated => {
      success('Avoir annulé.')
      setVoidOpen(false)
      qc.setQueryData(['credit-note', id], updated)
      qc.invalidateQueries({ queryKey: ['credit-notes'] })
    },
    onError: () => {
      toastError('Impossible d\'annuler l\'avoir.')
      setVoidOpen(false)
    },
  })

  const handlePdfPreview = async () => {
    if (!avoir) return
    setPdfLoading(true)
    try {
      const blob = await creditNoteApi.getPdf(avoir.id)
      const url = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }))
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      toastError('Impossible de générer le PDF.')
    } finally {
      setPdfLoading(false)
    }
  }

  if (isLoading) return <LoadingScreen />
  if (isError || !avoir) {
    return (
      <Box>
        <PageHeader
          title="Avoir"
          breadcrumbs={[{ label: 'Avoirs', href: '/credit-notes' }, { label: '—' }]}
        />
        <Typography color="error">Impossible de charger cet avoir.</Typography>
      </Box>
    )
  }

  const anyMutating = issueMutation.isPending || voidMutation.isPending

  // Refund logic — invoice data is embedded in avoir by the backend
  const overpaidMinor = Math.max(
    0,
    avoir.invoice_paid_amount_minor - (avoir.invoice_total_minor - avoir.total_minor),
  )
  const totalRefundedMinor = (avoir.refunds ?? []).reduce((s, r) => s + r.amount_minor, 0)
  const remainingRefundMinor = Math.max(0, overpaidMinor - totalRefundedMinor)
  const showRefundSection = avoir.status === 'issued' && overpaidMinor > 0

  return (
    <Box>
      <PageHeader
        title={avoir.doc_number ?? 'Avoir brouillon'}
        subtitle={`Facture ${avoir.invoice_doc_number ?? `#${avoir.invoice_id}`}`}
        breadcrumbs={[
          { label: 'Avoirs', href: '/credit-notes' },
          { label: avoir.doc_number ?? 'Brouillon' },
        ]}
        actions={
          <Button
            variant="outlined"
            startIcon={<PictureAsPdfRoundedIcon />}
            onClick={handlePdfPreview}
            disabled={pdfLoading}
            size="small"
          >
            {pdfLoading ? 'Génération…' : 'Aperçu PDF'}
          </Button>
        }
      />

      <Grid container spacing={3}>
        {/* Left — info */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent sx={{ p: 3 }}>
              <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
                <Box sx={{ color: '#EA580C' }}>
                  <InfoRoundedIcon sx={{ fontSize: 20 }} />
                </Box>
                <Typography variant="subtitle1" fontWeight={700}>
                  Informations
                </Typography>
              </Stack>
              <Divider sx={{ mb: 0.5 }} />

              <InfoRow
                label="Numéro"
                value={
                  avoir.doc_number
                    ? <Typography variant="body2" fontWeight={700} fontFamily="monospace">{avoir.doc_number}</Typography>
                    : <Chip label="Brouillon" size="small" sx={{ bgcolor: '#F1F5F9', color: '#64748B', fontWeight: 600 }} />
                }
              />
              <Divider />
              <InfoRow
                label="Facture liée"
                value={
                  avoir.invoice_public_id ? (
                    <Button
                      size="small"
                      variant="text"
                      onClick={() => navigate(`/invoices/${avoir.invoice_public_id}`)}
                      sx={{ p: 0, minWidth: 0, fontWeight: 600, fontSize: '0.8125rem' }}
                    >
                      {avoir.invoice_doc_number ?? `Facture #${avoir.invoice_id}`}
                    </Button>
                  ) : (
                    <Typography variant="body2" fontFamily="monospace">
                      Facture #{avoir.invoice_id}
                    </Typography>
                  )
                }
              />
              <Divider />
              <InfoRow
                label="Montant TTC"
                value={
                  <Typography variant="body2" fontWeight={700} color="error.main">
                    -{formatMinor(avoir.total_minor)}
                  </Typography>
                }
              />
              <Divider />
              <InfoRow
                label="Motif"
                value={
                  avoir.reason
                    ? <Typography variant="body2" color="text.secondary">{avoir.reason}</Typography>
                    : null
                }
              />
              <Divider />
              <InfoRow
                label="Créé le"
                value={
                  <Typography variant="body2">
                    {new Date(avoir.created_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })}
                  </Typography>
                }
              />
              {avoir.issued_at && (
                <>
                  <Divider />
                  <InfoRow
                    label="Émis le"
                    value={
                      <Typography variant="body2">
                        {new Date(avoir.issued_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })}
                      </Typography>
                    }
                  />
                </>
              )}
              {avoir.voided_at && (
                <>
                  <Divider />
                  <InfoRow
                    label="Annulé le"
                    value={
                      <Typography variant="body2" color="error.main">
                        {new Date(avoir.voided_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })}
                      </Typography>
                    }
                  />
                </>
              )}

              {/* Refunds history */}
              {(avoir.refunds ?? []).length > 0 && (
                <>
                  <Divider sx={{ mt: 1 }} />
                  <Box pt={1.5} pb={0.5}>
                    <Stack direction="row" alignItems="center" spacing={1} mb={1.5}>
                      <MoneyOffRoundedIcon sx={{ fontSize: 16, color: '#EA580C' }} />
                      <Typography variant="body2" fontWeight={700}>
                        Remboursements effectués
                      </Typography>
                      <Chip
                        label={(avoir.refunds ?? []).length}
                        size="small"
                        sx={{ bgcolor: '#FFF7ED', color: '#EA580C', fontWeight: 600 }}
                      />
                    </Stack>
                    <Stack divider={<Divider />}>
                      {(avoir.refunds ?? []).map(refund => (
                        <Stack
                          key={refund.id}
                          direction="row"
                          alignItems="center"
                          justifyContent="space-between"
                          py={1}
                        >
                          <Stack spacing={0.25}>
                            <Typography variant="body2" fontWeight={600}>
                              {formatMinor(refund.amount_minor)}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {PAYMENT_METHOD_LABELS[refund.payment_method]}
                              {refund.reference ? ` · ${refund.reference}` : ''}
                            </Typography>
                          </Stack>
                          <Typography variant="caption" color="text.secondary">
                            {new Date(refund.refunded_at).toLocaleDateString('fr-FR')}
                          </Typography>
                        </Stack>
                      ))}
                    </Stack>
                  </Box>
                </>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Right — sticky actions */}
        <Grid item xs={12} md={4}>
          <Box sx={{ position: 'sticky', top: 24 }}>
            <Card>
              <CardContent sx={{ p: 3 }}>
                <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2.5}>
                  <Typography variant="subtitle1" fontWeight={700}>Avoir</Typography>
                  <StatusChip
                    status={avoir.status}
                    label={CREDIT_NOTE_STATUS_LABELS[avoir.status]}
                  />
                </Stack>

                <Box sx={{ bgcolor: '#FFF7ED', borderRadius: 1.5, p: 2, mb: 2.5, textAlign: 'center' }}>
                  <Stack direction="row" alignItems="center" justifyContent="center" spacing={1} mb={0.5}>
                    <AccountBalanceRoundedIcon sx={{ color: '#EA580C', fontSize: 20 }} />
                    <Typography variant="body2" color="#EA580C" fontWeight={600}>
                      Montant de l'avoir
                    </Typography>
                  </Stack>
                  <Typography variant="h5" fontWeight={800} color="error.main">
                    -{formatMinor(avoir.total_minor)}
                  </Typography>
                </Box>

                {/* Refund section */}
                {showRefundSection && (
                  <Box sx={{ bgcolor: '#F8FAFC', borderRadius: 1.5, p: 2, mb: 2 }}>
                    <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                      <MoneyOffRoundedIcon sx={{ fontSize: 16, color: '#EA580C' }} />
                      <Typography variant="body2" fontWeight={700} color="#EA580C">
                        Remboursement client
                      </Typography>
                    </Stack>
                    <Stack spacing={0.5} mb={1.5}>
                      <Stack direction="row" justifyContent="space-between">
                        <Typography variant="caption" color="text.secondary">Trop-perçu</Typography>
                        <Typography variant="caption" fontWeight={600} color="error.main">
                          {formatMinor(overpaidMinor)}
                        </Typography>
                      </Stack>
                      {totalRefundedMinor > 0 && (
                        <Stack direction="row" justifyContent="space-between">
                          <Typography variant="caption" color="text.secondary">Déjà remboursé</Typography>
                          <Typography variant="caption" fontWeight={600} color="success.main">
                            {formatMinor(totalRefundedMinor)}
                          </Typography>
                        </Stack>
                      )}
                      <Divider />
                      <Stack direction="row" justifyContent="space-between">
                        <Typography variant="caption" fontWeight={700}>Restant à rembourser</Typography>
                        <Typography variant="caption" fontWeight={700} color={remainingRefundMinor > 0 ? 'error.main' : 'success.main'}>
                          {remainingRefundMinor > 0 ? formatMinor(remainingRefundMinor) : 'Soldé'}
                        </Typography>
                      </Stack>
                    </Stack>
                    {remainingRefundMinor > 0 && (
                      <Button
                        variant="contained"
                        fullWidth
                        size="small"
                        startIcon={<MoneyOffRoundedIcon />}
                        onClick={() => setRefundOpen(true)}
                        sx={{ bgcolor: '#EA580C', '&:hover': { bgcolor: '#C2410C' } }}
                      >
                        Enregistrer un remboursement
                      </Button>
                    )}
                  </Box>
                )}

                <Stack spacing={1.25}>
                  {avoir.status === 'draft' && (
                    <Button
                      variant="contained"
                      fullWidth
                      startIcon={<PublishRoundedIcon />}
                      onClick={() => setIssueOpen(true)}
                      disabled={anyMutating}
                      sx={{ bgcolor: '#EA580C', '&:hover': { bgcolor: '#C2410C' } }}
                    >
                      Émettre l'avoir
                    </Button>
                  )}

                  {(avoir.status === 'draft' || avoir.status === 'issued') && (
                    <Button
                      variant="outlined"
                      color="error"
                      fullWidth
                      startIcon={<CancelRoundedIcon />}
                      onClick={() => setVoidOpen(true)}
                      disabled={anyMutating}
                    >
                      Annuler l'avoir
                    </Button>
                  )}

                  {avoir.status === 'void' && (
                    <Box sx={{ bgcolor: '#FEF2F2', borderRadius: 1.5, p: 2, textAlign: 'center' }}>
                      <Typography variant="body2" color="error.dark" fontWeight={600}>
                        Avoir annulé
                      </Typography>
                    </Box>
                  )}
                </Stack>
              </CardContent>
            </Card>
          </Box>
        </Grid>
      </Grid>

      <ConfirmDialog
        open={issueOpen}
        title="Émettre l'avoir ?"
        message={`L'avoir sera émis et un numéro lui sera attribué. Cette action est irréversible.`}
        confirmLabel="Émettre"
        loading={issueMutation.isPending}
        onConfirm={() => issueMutation.mutate()}
        onCancel={() => setIssueOpen(false)}
      />

      <ConfirmDialog
        open={voidOpen}
        title="Annuler l'avoir ?"
        message={`L'avoir ${avoir.doc_number ?? `#${avoir.id}`} sera définitivement annulé. Cette action est irréversible.`}
        confirmLabel="Annuler l'avoir"
        dangerous
        loading={voidMutation.isPending}
        onConfirm={() => voidMutation.mutate()}
        onCancel={() => setVoidOpen(false)}
      />

      {refundOpen && (
        <RecordRefundDialog
          open={refundOpen}
          onClose={() => setRefundOpen(false)}
          avoir={avoir}
          remainingRefundMinor={remainingRefundMinor}
        />
      )}
    </Box>
  )
}
