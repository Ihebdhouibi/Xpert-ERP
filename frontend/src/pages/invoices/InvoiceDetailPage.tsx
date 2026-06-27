import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material'
import PublishRoundedIcon from '@mui/icons-material/PublishRounded'
import CancelRoundedIcon from '@mui/icons-material/CancelRounded'
import DeleteRoundedIcon from '@mui/icons-material/DeleteRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import InfoRoundedIcon from '@mui/icons-material/InfoRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded'
import PaymentsRoundedIcon from '@mui/icons-material/PaymentsRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import NoteAddRoundedIcon from '@mui/icons-material/NoteAddRounded'
import {
  invoiceApi,
  INVOICE_STATUS_LABELS,
  type InvoiceLineKind,
  type InvoiceLineOut,
  type InvoiceOut,
} from '../../lib/invoiceApi'
import { customerApi } from '../../lib/customerApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'
import { RecordPaymentDialog } from '../../components/invoice/RecordPaymentDialog'
import { PaymentHistoryPanel } from '../../components/invoice/PaymentHistoryPanel'
import { AddInvoiceLineDialog } from '../../components/invoice/AddInvoiceLineDialog'
import { CreateCreditNoteDialog } from '../../components/credit-note/CreateCreditNoteDialog'
import { CreditNotesPanel } from '../../components/credit-note/CreditNotesPanel'
import { advancePaymentApi } from '../../lib/advancePaymentApi'
import { parseCreditLimitError, type CreditLimitExceededDetail } from '../../lib/creditOverrideApi'
import { CreditLimitExceededDialog } from '../../components/credit/CreditLimitExceededDialog'

const LINE_KIND_LABELS: Record<InvoiceLineKind, string> = {
  labor: "Main d'œuvre",
  part: 'Pièce',
  service: 'Prestation',
  other: 'Autre',
}

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

export function InvoiceDetailPage() {
  const { publicId } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const [cancelOpen, setCancelOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [paymentOpen, setPaymentOpen] = useState(false)
  const [creditNoteOpen, setCreditNoteOpen] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [lineDialogOpen, setLineDialogOpen] = useState(false)
  const [editLine, setEditLine] = useState<InvoiceLineOut | null>(null)
  const [deleteLineId, setDeleteLineId] = useState<number | null>(null)
  const [creditLimitDetail, setCreditLimitDetail] = useState<CreditLimitExceededDetail | null>(null)

  const handlePdfPreview = async () => {
    if (!invoice) return
    setPdfLoading(true)
    try {
      const token = localStorage.getItem('access_token')
      const response = await axios.get(
        `/api/v1/pdf/invoices/${invoice.id}`,
        {
          responseType: 'blob',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      )
      const url = URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      toastError('Impossible de générer le PDF.')
    } finally {
      setPdfLoading(false)
    }
  }

  const { data: invoice, isLoading, isError } = useQuery({
    queryKey: ['invoice', publicId],
    queryFn: () => invoiceApi.get(publicId!),
    enabled: !!publicId,
  })

  const { data: appliedAdvances } = useQuery({
    queryKey: ['advance-payments', 'invoice', invoice?.id],
    queryFn: () => advancePaymentApi.listByInvoice(invoice!.id),
    enabled: !!invoice?.id && invoice?.status !== 'draft',
  })

  const issueMutation = useMutation({
    mutationFn: () => invoiceApi.issue(publicId!, invoice!.version),
    onSuccess: () => {
      success('Facture émise')
      queryClient.invalidateQueries({ queryKey: ['invoice', publicId] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
    onError: (err: unknown) => {
      const creditError = parseCreditLimitError(err)
      if (creditError) {
        setCreditLimitDetail(creditError)
        return
      }
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toastError(typeof detail === 'string' ? detail : 'Impossible d\'émettre la facture.')
    },
  })

  // Customer assignment for OCR-captured drafts that have no customer yet
  const [assignCustomerId, setAssignCustomerId] = useState<number | ''>('')
  const needsCustomer = invoice?.status === 'draft' && invoice?.customer_id == null
  const { data: customersData } = useQuery({
    queryKey: ['customers', 'for-invoice-assign'],
    queryFn: () => customerApi.list({ page_size: 100 }),
    enabled: !!needsCustomer,
  })
  const assignCustomerMutation = useMutation({
    mutationFn: () =>
      invoiceApi.update(publicId!, invoice!.version, {
        customer_id: assignCustomerId as number,
      }),
    onSuccess: () => {
      success('Client assigné')
      queryClient.invalidateQueries({ queryKey: ['invoice', publicId] })
    },
    onError: () => toastError("Impossible d'assigner le client."),
  })

  const cancelMutation = useMutation({
    mutationFn: () => invoiceApi.cancel(publicId!, invoice!.version),
    onSuccess: () => {
      success('Facture annulée')
      setCancelOpen(false)
      queryClient.invalidateQueries({ queryKey: ['invoice', publicId] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
    onError: () => {
      toastError('Impossible d\'annuler la facture.')
      setCancelOpen(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => invoiceApi.remove(publicId!),
    onSuccess: () => {
      success('Facture supprimée')
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      navigate('/invoices', { replace: true })
    },
    onError: () => toastError('Impossible de supprimer la facture.'),
  })

  const removeLineMutation = useMutation({
    mutationFn: (lineId: number) => invoiceApi.removeLine(publicId!, lineId, invoice!.version),
    onSuccess: (updated: InvoiceOut) => {
      success('Ligne supprimée')
      setDeleteLineId(null)
      queryClient.setQueryData(['invoice', publicId], updated)
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
    onError: () => {
      toastError('Impossible de supprimer la ligne.')
      setDeleteLineId(null)
    },
  })

  function handleLineSaved(updated: InvoiceOut) {
    queryClient.setQueryData(['invoice', publicId], updated)
    queryClient.invalidateQueries({ queryKey: ['invoices'] })
  }

  function openAddLine() {
    setEditLine(null)
    setLineDialogOpen(true)
  }

  function openEditLine(line: InvoiceLineOut) {
    setEditLine(line)
    setLineDialogOpen(true)
  }

  function closeLineDialog() {
    setLineDialogOpen(false)
    setEditLine(null)
  }

  if (isLoading) return <LoadingScreen />
  if (isError || !invoice) {
    return (
      <Box>
        <PageHeader title="Facture" breadcrumbs={[{ label: 'Factures', href: '/invoices' }, { label: '—' }]} />
        <Typography color="error">Impossible de charger cette facture.</Typography>
      </Box>
    )
  }

  const paidPct = invoice.total_minor > 0
    ? Math.min((invoice.paid_amount_minor / invoice.total_minor) * 100, 100)
    : 0
  const isOverdue =
    invoice.due_at &&
    new Date(invoice.due_at) < new Date() &&
    invoice.status !== 'paid' &&
    invoice.status !== 'cancelled'
  const anyMutating = issueMutation.isPending || cancelMutation.isPending

  return (
    <Box>
      <PageHeader
        title={invoice.doc_number ?? 'Facture brouillon'}
        subtitle={invoice.customer_name ?? (invoice.customer_id == null ? 'Sans client' : `Client #${invoice.customer_id}`)}
        breadcrumbs={[
          { label: 'Factures', href: '/invoices' },
          { label: invoice.doc_number ?? 'Brouillon' },
        ]}
        actions={
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={<PictureAsPdfRoundedIcon />}
              onClick={handlePdfPreview}
              disabled={pdfLoading}
              size="small"
            >
              {pdfLoading ? 'Génération…' : 'Aperçu PDF'}
            </Button>
            {invoice.status === 'draft' && (
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteRoundedIcon />}
                onClick={() => setDeleteOpen(true)}
                size="small"
              >
                Supprimer
              </Button>
            )}
          </Stack>
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
                  invoice.doc_number
                    ? <Typography variant="body2" fontWeight={700} fontFamily="monospace">{invoice.doc_number}</Typography>
                    : <Chip label="Brouillon" size="small" sx={{ bgcolor: '#F1F5F9', color: '#64748B', fontWeight: 600 }} />
                } />
                <Divider />
                <InfoRow label="Client" value={
                  needsCustomer ? (
                    <Stack direction="row" spacing={1} alignItems="center">
                      <FormControl size="small" sx={{ minWidth: 200 }}>
                        <InputLabel>Choisir un client</InputLabel>
                        <Select
                          label="Choisir un client"
                          value={assignCustomerId}
                          onChange={(e) => setAssignCustomerId(e.target.value as number)}
                        >
                          {(customersData?.items ?? []).map((c) => (
                            <MenuItem key={c.int_id} value={c.int_id}>
                              {c.company_name ? `${c.full_name} (${c.company_name})` : c.full_name}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                      <Button
                        size="small"
                        variant="contained"
                        disabled={assignCustomerId === '' || assignCustomerMutation.isPending}
                        onClick={() => assignCustomerMutation.mutate()}
                      >
                        Assigner
                      </Button>
                    </Stack>
                  ) : (
                    <Typography variant="body2" fontWeight={500}>
                      {invoice.customer_name ?? (invoice.customer_id == null ? 'Sans client' : `Client #${invoice.customer_id}`)}
                    </Typography>
                  )
                } />
                {invoice.vehicle_id && (
                  <>
                    <Divider />
                    <InfoRow label="Véhicule" value={
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => navigate(`/vehicles/${invoice.vehicle_id}`)}
                        sx={{ p: 0, minWidth: 0, fontWeight: 600, fontSize: '0.8125rem' }}
                      >
                        {invoice.vehicle_label ?? `Véhicule #${invoice.vehicle_id}`}
                      </Button>
                    } />
                  </>
                )}
                {invoice.quotation_id && (
                  <>
                    <Divider />
                    <InfoRow label="Devis source" value={
                      <Typography variant="body2" color="text.secondary">
                        Devis #{invoice.quotation_id}
                      </Typography>
                    } />
                  </>
                )}
                <Divider />
                <InfoRow label="Date d'émission" value={
                  invoice.issued_at
                    ? <Typography variant="body2">{new Date(invoice.issued_at).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })}</Typography>
                    : null
                } />
                <Divider />
                <InfoRow label="Échéance" value={
                  invoice.due_at ? (
                    <Stack direction="row" alignItems="center" spacing={0.5}>
                      {isOverdue && <WarningAmberRoundedIcon sx={{ fontSize: 14, color: 'error.main' }} />}
                      <Typography
                        variant="body2"
                        fontWeight={isOverdue ? 700 : 500}
                        color={isOverdue ? 'error.main' : 'text.primary'}
                      >
                        {new Date(invoice.due_at).toLocaleDateString('fr-FR')}
                        {isOverdue && ' — En retard'}
                      </Typography>
                    </Stack>
                  ) : null
                } />
                <Divider />
                <InfoRow label="Exporté comptabilité" value={
                  <Chip
                    label={invoice.is_exported ? 'Exporté' : 'Non exporté'}
                    size="small"
                    color={invoice.is_exported ? 'success' : 'default'}
                    sx={{ fontWeight: 600, fontSize: '0.75rem' }}
                  />
                } />
                {invoice.notes && (
                  <>
                    <Divider />
                    <Box pt={1.5} pb={0.5}>
                      <Typography variant="caption" color="text.secondary" display="block" mb={0.75} fontWeight={500}>
                        Notes
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                        {invoice.notes}
                      </Typography>
                    </Box>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Payment history */}
            {invoice.status !== 'draft' && (
              <PaymentHistoryPanel invoiceId={invoice.id} currency={invoice.currency} />
            )}

            {/* Credit notes */}
            {invoice.status !== 'draft' && (
              <CreditNotesPanel invoiceId={invoice.id} />
            )}

            {/* Lines card */}
            <Card>
              <CardContent sx={{ p: 3 }}>
                <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
                  <Box sx={{ color: 'primary.main' }}>
                    <ReceiptRoundedIcon sx={{ fontSize: 20 }} />
                  </Box>
                  <Typography variant="subtitle1" fontWeight={700}>
                    Lignes de la facture
                  </Typography>
                  <Chip
                    label={invoice.lines.length}
                    size="small"
                    sx={{ bgcolor: '#F1F5F9', color: '#475569', fontWeight: 600 }}
                  />
                  {invoice.status === 'draft' && (
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<AddRoundedIcon />}
                      onClick={openAddLine}
                      sx={{ ml: 'auto !important' }}
                    >
                      Ajouter une ligne
                    </Button>
                  )}
                </Stack>
                <Divider sx={{ mb: 0 }} />
                {invoice.lines.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" py={3} textAlign="center">
                    Aucune ligne dans cette facture.
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
                          {invoice.status === 'draft' && (
                            <TableCell sx={{ py: 1.25, width: 72 }} />
                          )}
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {invoice.lines.map(line => {
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
                                  {formatMinor(line.unit_price_minor, invoice.currency)}
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
                                  {formatMinor(line.line_total_minor, invoice.currency)}
                                </Typography>
                              </TableCell>
                              {invoice.status === 'draft' && (
                                <TableCell align="right" sx={{ py: 1, px: 0.5 }}>
                                  <Stack direction="row" spacing={0} justifyContent="flex-end">
                                    <Tooltip title="Modifier">
                                      <IconButton
                                        size="small"
                                        onClick={() => openEditLine(line)}
                                        sx={{ color: 'text.secondary', '&:hover': { color: 'primary.main' } }}
                                      >
                                        <EditRoundedIcon sx={{ fontSize: 15 }} />
                                      </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Supprimer">
                                      <IconButton
                                        size="small"
                                        onClick={() => setDeleteLineId(line.id)}
                                        disabled={removeLineMutation.isPending && deleteLineId === line.id}
                                        sx={{ color: 'text.secondary', '&:hover': { color: 'error.main' } }}
                                      >
                                        <DeleteRoundedIcon sx={{ fontSize: 15 }} />
                                      </IconButton>
                                    </Tooltip>
                                  </Stack>
                                </TableCell>
                              )}
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

        {/* Right — sticky payment summary + actions */}
        <Grid item xs={12} md={4}>
          <Box sx={{ position: 'sticky', top: 24 }}>
            <Card>
              <CardContent sx={{ p: 3 }}>
                <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2.5}>
                  <Typography variant="subtitle1" fontWeight={700}>Paiement</Typography>
                  <StatusChip status={invoice.status} label={INVOICE_STATUS_LABELS[invoice.status]} />
                </Stack>

                {/* Payment progress */}
                {invoice.status !== 'draft' && invoice.status !== 'cancelled' && (
                  <Box mb={2.5}>
                    <Stack direction="row" justifyContent="space-between" mb={0.75}>
                      <Typography variant="caption" color="text.secondary" fontWeight={500}>
                        Progression du paiement
                      </Typography>
                      <Typography variant="caption" fontWeight={700} color={paidPct === 100 ? 'success.main' : 'text.primary'}>
                        {Math.round(paidPct)}%
                      </Typography>
                    </Stack>
                    <Tooltip title={`${formatMinor(invoice.paid_amount_minor, invoice.currency)} payé sur ${formatMinor(invoice.total_minor, invoice.currency)}`}>
                      <LinearProgress
                        variant="determinate"
                        value={paidPct}
                        color={paidPct === 100 ? 'success' : paidPct > 0 ? 'warning' : 'primary'}
                        sx={{ height: 8, borderRadius: 999 }}
                      />
                    </Tooltip>
                  </Box>
                )}

                {/* Financial breakdown */}
                <Box sx={{ bgcolor: '#F8FAFC', borderRadius: 1.5, p: 2, mb: 2.5 }}>
                  <TotalRow
                    label="Sous-total HT"
                    value={formatMinor(invoice.subtotal_minor, invoice.currency)}
                  />
                  {invoice.discount_minor > 0 && (
                    <TotalRow
                      label="Remise"
                      value={`− ${formatMinor(invoice.discount_minor, invoice.currency)}`}
                      color="warning.dark"
                    />
                  )}
                  <TotalRow
                    label="TVA"
                    value={formatMinor(invoice.vat_minor, invoice.currency)}
                  />
                  <Divider sx={{ my: 1 }} />
                  <TotalRow
                    label="Total TTC"
                    value={formatMinor(invoice.total_minor, invoice.currency)}
                    bold
                  />
                  {invoice.status !== 'draft' && (
                    <>
                      <Divider sx={{ my: 1 }} />
                      {(appliedAdvances?.items ?? []).length > 0 && (
                        <>
                          {appliedAdvances!.items.map(adv => (
                            <TotalRow
                              key={adv.id}
                              label={`Acompte${adv.reference ? ` (${adv.reference})` : ''}`}
                              value={`− ${formatMinor(adv.applied_amount_minor ?? adv.amount_minor, invoice.currency)}`}
                              color="primary.main"
                            />
                          ))}
                          <Divider sx={{ my: 1 }} />
                        </>
                      )}
                      <TotalRow
                        label="Payé"
                        value={formatMinor(invoice.paid_amount_minor, invoice.currency)}
                        color="success.main"
                      />
                      <TotalRow
                        label="Restant dû"
                        value={invoice.outstanding_minor > 0
                          ? formatMinor(invoice.outstanding_minor, invoice.currency)
                          : '—'}
                        bold={invoice.outstanding_minor > 0}
                        color={invoice.outstanding_minor > 0 ? 'error.main' : 'text.secondary'}
                      />
                    </>
                  )}
                </Box>

                {/* Actions by status */}
                <Stack spacing={1.25}>
                  {invoice.status === 'draft' && (
                    <Tooltip title={needsCustomer ? 'Assignez un client avant d\'émettre' : ''}>
                      <span>
                        <Button
                          variant="contained"
                          fullWidth
                          startIcon={<PublishRoundedIcon />}
                          onClick={() => issueMutation.mutate()}
                          disabled={anyMutating || needsCustomer}
                        >
                          Émettre la facture
                        </Button>
                      </span>
                    </Tooltip>
                  )}

                  {(invoice.status === 'issued' || invoice.status === 'partial') && (
                    <Button
                      variant="contained"
                      color="success"
                      fullWidth
                      startIcon={<PaymentsRoundedIcon />}
                      onClick={() => setPaymentOpen(true)}
                      disabled={anyMutating}
                    >
                      Enregistrer un paiement
                    </Button>
                  )}

                  {(invoice.status === 'issued' || invoice.status === 'partial' || invoice.status === 'paid') && (
                    <Button
                      variant="outlined"
                      fullWidth
                      startIcon={<NoteAddRoundedIcon />}
                      onClick={() => setCreditNoteOpen(true)}
                      disabled={anyMutating}
                      sx={{ borderColor: '#EA580C', color: '#EA580C', '&:hover': { borderColor: '#C2410C', bgcolor: '#FFF7ED' } }}
                    >
                      Créer un avoir
                    </Button>
                  )}

                  {(invoice.status === 'issued' || invoice.status === 'partial') && (
                    <Button
                      variant="outlined"
                      color="error"
                      fullWidth
                      startIcon={<CancelRoundedIcon />}
                      onClick={() => setCancelOpen(true)}
                      disabled={anyMutating}
                    >
                      Annuler la facture
                    </Button>
                  )}

                  {invoice.status === 'paid' && (
                    <Box sx={{ bgcolor: '#F0FDF4', borderRadius: 1.5, p: 2, textAlign: 'center' }}>
                      <Typography variant="body2" color="success.dark" fontWeight={600}>
                        Facture entièrement payée
                      </Typography>
                    </Box>
                  )}

                  {invoice.status === 'cancelled' && (
                    <Box sx={{ bgcolor: '#FEF2F2', borderRadius: 1.5, p: 2, textAlign: 'center' }}>
                      <Typography variant="body2" color="error.dark" fontWeight={600}>
                        Facture annulée
                      </Typography>
                    </Box>
                  )}
                </Stack>
              </CardContent>
            </Card>
          </Box>
        </Grid>
      </Grid>

      {invoice && (
        <RecordPaymentDialog
          open={paymentOpen}
          onClose={() => setPaymentOpen(false)}
          invoice={invoice}
        />
      )}

      {invoice && (
        <CreateCreditNoteDialog
          open={creditNoteOpen}
          onClose={() => setCreditNoteOpen(false)}
          invoice={invoice}
        />
      )}

      <ConfirmDialog
        open={cancelOpen}
        title="Annuler cette facture ?"
        message="La facture sera marquée comme annulée. Cette action est irréversible."
        confirmLabel="Annuler la facture"
        dangerous
        loading={cancelMutation.isPending}
        onConfirm={() => cancelMutation.mutate()}
        onCancel={() => setCancelOpen(false)}
      />

      <ConfirmDialog
        open={deleteOpen}
        title="Supprimer cette facture ?"
        message="Cette action est irréversible. La facture sera définitivement supprimée."
        confirmLabel="Supprimer"
        dangerous
        loading={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => setDeleteOpen(false)}
      />

      <ConfirmDialog
        open={deleteLineId !== null}
        title="Supprimer cette ligne ?"
        message="La ligne sera définitivement retirée de la facture."
        confirmLabel="Supprimer"
        dangerous
        loading={removeLineMutation.isPending}
        onConfirm={() => deleteLineId !== null && removeLineMutation.mutate(deleteLineId)}
        onCancel={() => setDeleteLineId(null)}
      />

      {invoice && (
        <AddInvoiceLineDialog
          open={lineDialogOpen}
          onClose={closeLineDialog}
          invoicePublicId={publicId!}
          invoiceVersion={invoice.version}
          editLine={editLine}
          onSaved={handleLineSaved}
        />
      )}

      <CreditLimitExceededDialog
        open={creditLimitDetail !== null}
        detail={creditLimitDetail}
        documentPublicId={publicId ?? ''}
        onClose={() => setCreditLimitDetail(null)}
      />
    </Box>
  )
}
