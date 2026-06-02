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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import SendRoundedIcon from '@mui/icons-material/SendRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import CancelRoundedIcon from '@mui/icons-material/CancelRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import DeleteRoundedIcon from '@mui/icons-material/DeleteRounded'
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded'
import InfoRoundedIcon from '@mui/icons-material/InfoRounded'
import {
  quotationApi,
  QUOTATION_STATUS_LABELS,
  LINE_KIND_LABELS,
} from '../../lib/quotationApi'
import { invoiceApi } from '../../lib/invoiceApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

const KIND_COLORS: Record<string, { bg: string; color: string }> = {
  labor: { bg: '#EFF6FF', color: '#2563EB' },
  part: { bg: '#FFFBEB', color: '#D97706' },
  service: { bg: '#F0FDF4', color: '#16A34A' },
  other: { bg: '#F1F5F9', color: '#64748B' },
}

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

function TotalRow({
  label,
  value,
  bold,
  color,
}: {
  label: string
  value: string
  bold?: boolean
  color?: string
}) {
  return (
    <Stack direction="row" justifyContent="space-between" alignItems="center" py={0.75}>
      <Typography variant="body2" color="text.secondary" fontWeight={bold ? 600 : 400}>
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={bold ? 700 : 500} color={color}>
        {value}
      </Typography>
    </Stack>
  )
}

export function QuotationDetailPage() {
  const { publicId } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const [deleteOpen, setDeleteOpen] = useState(false)

  const { data: quotation, isLoading, isError } = useQuery({
    queryKey: ['quotation', publicId],
    queryFn: () => quotationApi.get(publicId!),
    enabled: !!publicId,
  })

  const sendMutation = useMutation({
    mutationFn: () => quotationApi.send(publicId!, quotation!.version),
    onSuccess: () => {
      success('Devis envoyé au client')
      queryClient.invalidateQueries({ queryKey: ['quotation', publicId] })
      queryClient.invalidateQueries({ queryKey: ['quotations'] })
    },
    onError: () => toastError('Impossible d\'envoyer le devis.'),
  })

  const approveMutation = useMutation({
    mutationFn: () => quotationApi.approve(publicId!, quotation!.version),
    onSuccess: () => {
      success('Devis approuvé')
      queryClient.invalidateQueries({ queryKey: ['quotation', publicId] })
      queryClient.invalidateQueries({ queryKey: ['quotations'] })
    },
    onError: () => toastError('Impossible d\'approuver le devis.'),
  })

  const rejectMutation = useMutation({
    mutationFn: () => quotationApi.reject(publicId!, quotation!.version),
    onSuccess: () => {
      success('Devis refusé')
      queryClient.invalidateQueries({ queryKey: ['quotation', publicId] })
      queryClient.invalidateQueries({ queryKey: ['quotations'] })
    },
    onError: () => toastError('Impossible de refuser le devis.'),
  })

  const convertMutation = useMutation({
    mutationFn: () => invoiceApi.fromQuotation(quotation!.id),
    onSuccess: (invoice) => {
      success('Facture créée à partir du devis')
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      navigate(`/invoices/${invoice.public_id}`, { replace: true })
    },
    onError: () => toastError('Impossible de convertir le devis.'),
  })

  const deleteMutation = useMutation({
    mutationFn: () => quotationApi.remove(publicId!),
    onSuccess: () => {
      success('Devis supprimé')
      queryClient.invalidateQueries({ queryKey: ['quotations'] })
      navigate('/quotations', { replace: true })
    },
    onError: () => toastError('Impossible de supprimer le devis.'),
  })

  if (isLoading) return <LoadingScreen />
  if (isError || !quotation) {
    return (
      <Box>
        <PageHeader title="Devis" breadcrumbs={[{ label: 'Devis', href: '/quotations' }, { label: '—' }]} />
        <Typography color="error">Impossible de charger ce devis.</Typography>
      </Box>
    )
  }

  const isExpired = quotation.valid_until
    ? new Date(quotation.valid_until) < new Date()
    : false

  const anyMutating =
    sendMutation.isPending ||
    approveMutation.isPending ||
    rejectMutation.isPending ||
    convertMutation.isPending

  return (
    <Box>
      <PageHeader
        title={quotation.doc_number ?? 'Devis brouillon'}
        subtitle={`Client #${quotation.customer_id}`}
        breadcrumbs={[
          { label: 'Devis', href: '/quotations' },
          { label: quotation.doc_number ?? 'Brouillon' },
        ]}
        actions={
          quotation.status === 'draft' ? (
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteRoundedIcon />}
              onClick={() => setDeleteOpen(true)}
              size="small"
            >
              Supprimer
            </Button>
          ) : undefined
        }
      />

      <Grid container spacing={3}>
        {/* Left — details + lines */}
        <Grid item xs={12} md={8}>
          <Stack spacing={3}>
            {/* Info card */}
            <Card>
              <CardContent sx={{ p: 3 }}>
                <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
                  <Box sx={{ color: 'primary.main' }}>
                    <InfoRoundedIcon sx={{ fontSize: 20 }} />
                  </Box>
                  <Typography variant="subtitle1" fontWeight={700}>
                    Informations
                  </Typography>
                </Stack>
                <Divider sx={{ mb: 0.5 }} />
                <InfoRow label="Numéro" value={
                  quotation.doc_number
                    ? <Typography variant="body2" fontWeight={700} fontFamily="monospace">{quotation.doc_number}</Typography>
                    : <Chip label="Brouillon" size="small" sx={{ bgcolor: '#F1F5F9', color: '#64748B', fontWeight: 600 }} />
                } />
                <Divider />
                <InfoRow label="Client" value={
                  <Typography variant="body2" fontWeight={500}>Client #{quotation.customer_id}</Typography>
                } />
                {quotation.vehicle_id && (
                  <>
                    <Divider />
                    <InfoRow label="Véhicule" value={
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => navigate(`/vehicles/${quotation.vehicle_id}`)}
                        sx={{ p: 0, minWidth: 0, fontWeight: 600, fontSize: '0.8125rem' }}
                      >
                        Véhicule #{quotation.vehicle_id}
                      </Button>
                    } />
                  </>
                )}
                {quotation.repair_order_id && (
                  <>
                    <Divider />
                    <InfoRow label="Ordre de réparation" value={
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => navigate(`/repair-orders/${quotation.repair_order_id}`)}
                        sx={{ p: 0, minWidth: 0, fontWeight: 600, fontSize: '0.8125rem' }}
                      >
                        OT #{quotation.repair_order_id}
                      </Button>
                    } />
                  </>
                )}
                <Divider />
                <InfoRow label="Valide jusqu'au" value={
                  quotation.valid_until ? (
                    <Typography
                      variant="body2"
                      fontWeight={isExpired ? 700 : 500}
                      color={isExpired ? 'error.main' : 'text.primary'}
                    >
                      {new Date(quotation.valid_until).toLocaleDateString('fr-FR')}
                      {isExpired && ' — Expiré'}
                    </Typography>
                  ) : null
                } />
                <Divider />
                <InfoRow label="Créé le" value={
                  <Typography variant="body2" color="text.secondary">
                    {new Date(quotation.created_at).toLocaleDateString('fr-FR', {
                      day: '2-digit', month: 'long', year: 'numeric',
                    })}
                  </Typography>
                } />
                {quotation.notes && (
                  <>
                    <Divider />
                    <Box pt={1.5} pb={0.5}>
                      <Typography variant="caption" color="text.secondary" display="block" mb={0.75} fontWeight={500}>
                        Notes
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                        {quotation.notes}
                      </Typography>
                    </Box>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Lines card */}
            <Card>
              <CardContent sx={{ p: 3 }}>
                <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
                  <Box sx={{ color: 'primary.main' }}>
                    <DescriptionRoundedIcon sx={{ fontSize: 20 }} />
                  </Box>
                  <Typography variant="subtitle1" fontWeight={700}>
                    Lignes du devis
                  </Typography>
                  <Chip
                    label={quotation.lines.length}
                    size="small"
                    sx={{ bgcolor: '#F1F5F9', color: '#475569', fontWeight: 600, ml: 'auto !important' }}
                  />
                </Stack>
                <Divider sx={{ mb: 0 }} />
                {quotation.lines.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" py={3} textAlign="center">
                    Aucune ligne dans ce devis.
                  </Typography>
                ) : (
                  <Box sx={{ overflowX: 'auto' }}>
                    <Table size="small" sx={{ minWidth: 560 }}>
                      <TableHead>
                        <TableRow sx={{ bgcolor: '#F8FAFC' }}>
                          {['Type', 'Description', 'Qté', 'P.U. HT', 'Remise', 'TVA', 'Total HT'].map(h => (
                            <TableCell
                              key={h}
                              align={['Qté', 'P.U. HT', 'Remise', 'TVA', 'Total HT'].includes(h) ? 'right' : 'left'}
                              sx={{ fontSize: '0.6875rem', fontWeight: 600, color: 'text.secondary', py: 1.25 }}
                            >
                              {h}
                            </TableCell>
                          ))}
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {quotation.lines.map(line => {
                          const kindCfg = KIND_COLORS[line.kind] ?? KIND_COLORS.other
                          return (
                            <TableRow
                              key={line.id}
                              sx={{ '&:hover': { bgcolor: '#F9FAFB' } }}
                            >
                              <TableCell sx={{ py: 1.5 }}>
                                <Chip
                                  label={LINE_KIND_LABELS[line.kind]}
                                  size="small"
                                  sx={{
                                    bgcolor: kindCfg.bg,
                                    color: kindCfg.color,
                                    fontWeight: 600,
                                    fontSize: '0.6875rem',
                                    height: 22,
                                  }}
                                />
                              </TableCell>
                              <TableCell sx={{ py: 1.5, maxWidth: 240 }}>
                                <Typography variant="body2" fontWeight={500}>
                                  {line.description}
                                </Typography>
                              </TableCell>
                              <TableCell align="right" sx={{ py: 1.5 }}>
                                <Typography variant="body2" fontFamily="monospace" fontWeight={500}>
                                  {line.quantity}
                                </Typography>
                              </TableCell>
                              <TableCell align="right" sx={{ py: 1.5 }}>
                                <Typography variant="body2" fontFamily="monospace">
                                  {formatMinor(line.unit_price_minor, quotation.currency)}
                                </Typography>
                              </TableCell>
                              <TableCell align="right" sx={{ py: 1.5 }}>
                                <Typography
                                  variant="body2"
                                  color={parseFloat(line.discount_percent) > 0 ? 'warning.dark' : 'text.disabled'}
                                  fontWeight={parseFloat(line.discount_percent) > 0 ? 600 : 400}
                                >
                                  {parseFloat(line.discount_percent) > 0
                                    ? `${parseFloat(line.discount_percent)}%`
                                    : '—'}
                                </Typography>
                              </TableCell>
                              <TableCell align="right" sx={{ py: 1.5 }}>
                                <Typography variant="body2" color="text.secondary">
                                  {parseFloat(line.vat_rate)}%
                                </Typography>
                              </TableCell>
                              <TableCell align="right" sx={{ py: 1.5 }}>
                                <Typography variant="body2" fontWeight={700} fontFamily="monospace">
                                  {formatMinor(line.line_total_minor, quotation.currency)}
                                </Typography>
                              </TableCell>
                            </TableRow>
                          )
                        })}
                      </TableBody>
                    </Table>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Stack>
        </Grid>

        {/* Right — sticky summary + actions */}
        <Grid item xs={12} md={4}>
          <Box sx={{ position: 'sticky', top: 24 }}>
            <Card>
              <CardContent sx={{ p: 3 }}>
                {/* Status */}
                <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2.5}>
                  <Typography variant="subtitle1" fontWeight={700}>Récapitulatif</Typography>
                  <StatusChip status={quotation.status} label={QUOTATION_STATUS_LABELS[quotation.status]} />
                </Stack>

                {/* Totals */}
                <Box sx={{ bgcolor: '#F8FAFC', borderRadius: 1.5, p: 2, mb: 2.5 }}>
                  <TotalRow
                    label="Sous-total HT"
                    value={formatMinor(quotation.subtotal_minor, quotation.currency)}
                  />
                  {quotation.discount_minor > 0 && (
                    <TotalRow
                      label="Remise"
                      value={`− ${formatMinor(quotation.discount_minor, quotation.currency)}`}
                      color="warning.dark"
                    />
                  )}
                  <TotalRow
                    label="TVA"
                    value={formatMinor(quotation.vat_minor, quotation.currency)}
                  />
                  <Divider sx={{ my: 1 }} />
                  <TotalRow
                    label="Total TTC"
                    value={formatMinor(quotation.total_minor, quotation.currency)}
                    bold
                  />
                </Box>

                {/* Actions by status */}
                <Stack spacing={1.25}>
                  {quotation.status === 'draft' && (
                    <Button
                      variant="contained"
                      fullWidth
                      startIcon={<SendRoundedIcon />}
                      onClick={() => sendMutation.mutate()}
                      disabled={anyMutating}
                    >
                      Envoyer au client
                    </Button>
                  )}

                  {quotation.status === 'sent' && (
                    <>
                      <Button
                        variant="contained"
                        color="success"
                        fullWidth
                        startIcon={<CheckCircleRoundedIcon />}
                        onClick={() => approveMutation.mutate()}
                        disabled={anyMutating}
                      >
                        Approuver
                      </Button>
                      <Button
                        variant="outlined"
                        color="error"
                        fullWidth
                        startIcon={<CancelRoundedIcon />}
                        onClick={() => rejectMutation.mutate()}
                        disabled={anyMutating}
                      >
                        Refuser
                      </Button>
                    </>
                  )}

                  {quotation.status === 'approved' && (
                    <Button
                      variant="contained"
                      fullWidth
                      startIcon={<ReceiptRoundedIcon />}
                      onClick={() => convertMutation.mutate()}
                      disabled={anyMutating}
                    >
                      Convertir en facture
                    </Button>
                  )}

                  {['rejected', 'expired', 'converted'].includes(quotation.status) && (
                    <Box
                      sx={{
                        bgcolor: '#F8FAFC',
                        borderRadius: 1.5,
                        p: 2,
                        textAlign: 'center',
                      }}
                    >
                      <Typography variant="body2" color="text.secondary">
                        {quotation.status === 'converted'
                          ? 'Ce devis a été converti en facture.'
                          : 'Ce devis est clôturé et ne peut plus être modifié.'}
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
        open={deleteOpen}
        title="Supprimer ce devis ?"
        message="Cette action est irréversible. Le devis sera définitivement supprimé."
        confirmLabel="Supprimer"
        dangerous
        loading={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => setDeleteOpen(false)}
      />
    </Box>
  )
}
