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
  IconButton,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import SendRoundedIcon from '@mui/icons-material/SendRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import CancelRoundedIcon from '@mui/icons-material/CancelRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import DeleteRoundedIcon from '@mui/icons-material/DeleteRounded'
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded'
import InfoRoundedIcon from '@mui/icons-material/InfoRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded'
import PrintRoundedIcon from '@mui/icons-material/PrintRounded'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import {
  quotationApi,
  QUOTATION_STATUS_LABELS,
  LINE_KIND_LABELS,
  type LineKind,
} from '../../lib/quotationApi'
import { invoiceApi } from '../../lib/invoiceApi'
import { customerApi } from '../../lib/customerApi'
import { vehiclesApi } from '../../lib/vehiclesApi'
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

const LINE_KINDS: LineKind[] = ['labor', 'part', 'service', 'other']

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
  const [pdfLoading, setPdfLoading] = useState(false)

  // Add-line form
  const [showAddLine, setShowAddLine] = useState(false)
  const [lineKind, setLineKind] = useState<LineKind>('labor')
  const [lineDesc, setLineDesc] = useState('')
  const [lineQty, setLineQty] = useState('1')
  const [linePrice, setLinePrice] = useState('')
  const [lineDiscount, setLineDiscount] = useState('0')
  const [lineVat, setLineVat] = useState('0')

  const { data: quotation, isLoading, isError } = useQuery({
    queryKey: ['quotation', publicId],
    queryFn: () => quotationApi.get(publicId!),
    enabled: !!publicId,
  })

  // Resolve customer and vehicle names
  const { data: customer } = useQuery({
    queryKey: ['customer-by-int-id', quotation?.customer_id],
    queryFn: () => customerApi.getByIntId(quotation!.customer_id),
    enabled: !!quotation?.customer_id,
    staleTime: 5 * 60 * 1000,
  })
  const { data: vehicle } = useQuery({
    queryKey: ['vehicle', quotation?.vehicle_id],
    queryFn: () => vehiclesApi.get(quotation!.vehicle_id!),
    enabled: !!quotation?.vehicle_id,
    staleTime: 5 * 60 * 1000,
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

  const addLineMutation = useMutation({
    mutationFn: () =>
      quotationApi.addLine(publicId!, quotation!.version, {
        kind: lineKind,
        description: lineDesc,
        quantity: parseFloat(lineQty) || 1,
        unit_price_minor: Math.round(parseFloat(linePrice) * 1000),
        discount_percent: parseFloat(lineDiscount) || 0,
        vat_rate: parseFloat(lineVat) || 0,
      }),
    onSuccess: () => {
      success('Ligne ajoutée')
      setShowAddLine(false)
      setLineDesc(''); setLineQty('1'); setLinePrice(''); setLineDiscount('0'); setLineVat('0')
      queryClient.invalidateQueries({ queryKey: ['quotation', publicId] })
    },
    onError: () => toastError('Impossible d\'ajouter la ligne.'),
  })

  const removeLineMutation = useMutation({
    mutationFn: (lineId: number) => quotationApi.removeLine(publicId!, lineId, quotation!.version),
    onSuccess: () => {
      success('Ligne supprimée')
      queryClient.invalidateQueries({ queryKey: ['quotation', publicId] })
    },
    onError: () => toastError('Impossible de supprimer la ligne.'),
  })

  const handleDownloadPdf = async (mode: 'download' | 'print') => {
    if (!quotation) return
    setPdfLoading(true)
    try {
      const url = await quotationApi.getPdf(quotation.id)
      if (mode === 'print') {
        const win = window.open(url, '_blank', 'noopener,noreferrer')
        win?.focus()
      } else {
        const a = document.createElement('a')
        a.href = url
        a.download = `devis-${quotation.doc_number ?? quotation.id}.pdf`
        a.click()
      }
    } catch {
      toastError('Impossible de générer le PDF.')
    } finally {
      setPdfLoading(false)
    }
  }

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

  const canEditLines = quotation.status === 'draft'

  const customerLabel = customer
    ? customer.company_name
      ? `${customer.full_name} — ${customer.company_name}`
      : customer.full_name
    : `Client #${quotation.customer_id}`

  const vehicleLabel = vehicle
    ? [vehicle.registration, `${vehicle.make} ${vehicle.model}`, vehicle.year].filter(Boolean).join(' — ')
    : quotation.vehicle_id ? `Véhicule #${quotation.vehicle_id}` : null

  return (
    <Box>
      <PageHeader
        title={quotation.doc_number ?? 'Devis brouillon'}
        subtitle={customerLabel}
        breadcrumbs={[
          { label: 'Devis', href: '/quotations' },
          { label: quotation.doc_number ?? 'Brouillon' },
        ]}
        actions={
          <Stack direction="row" spacing={1} alignItems="center">
            <Tooltip title="Aperçu / Imprimer">
              <span>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<PrintRoundedIcon />}
                  onClick={() => handleDownloadPdf('print')}
                  disabled={pdfLoading}
                  sx={{ textTransform: 'none' }}
                >
                  Imprimer
                </Button>
              </span>
            </Tooltip>
            <Tooltip title="Télécharger PDF">
              <span>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<PictureAsPdfRoundedIcon />}
                  onClick={() => handleDownloadPdf('download')}
                  disabled={pdfLoading}
                  sx={{ textTransform: 'none' }}
                >
                  {pdfLoading ? 'PDF…' : 'PDF'}
                </Button>
              </span>
            </Tooltip>
            {quotation.status === 'draft' && (
              <Button
                variant="outlined"
                color="error"
                startIcon={<DeleteRoundedIcon />}
                onClick={() => setDeleteOpen(true)}
                size="small"
                sx={{ textTransform: 'none' }}
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
                  quotation.doc_number
                    ? <Typography variant="body2" fontWeight={700} fontFamily="monospace">{quotation.doc_number}</Typography>
                    : <Chip label="Brouillon" size="small" sx={{ bgcolor: '#F1F5F9', color: '#64748B', fontWeight: 600 }} />
                } />
                <Divider />
                <InfoRow label="Client" value={
                  <Typography
                    variant="body2"
                    fontWeight={600}
                    sx={{ color: 'primary.main', cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                    onClick={() => customer && navigate(`/customers/${customer.id}`)}
                  >
                    {customerLabel}
                  </Typography>
                } />
                {vehicleLabel && (
                  <>
                    <Divider />
                    <InfoRow label="Véhicule" value={
                      <Typography
                        variant="body2"
                        fontWeight={600}
                        sx={{ color: 'primary.main', cursor: 'pointer', fontFamily: vehicle ? 'monospace' : 'inherit', '&:hover': { textDecoration: 'underline' } }}
                        onClick={() => vehicle && navigate(`/vehicles/${vehicle.id}`)}
                      >
                        {vehicleLabel}
                      </Typography>
                    } />
                  </>
                )}
                {quotation.repair_order_id && (
                  <>
                    <Divider />
                    <InfoRow label="Ordre de réparation" value={
                      <Typography
                        variant="body2"
                        fontWeight={600}
                        sx={{ color: 'primary.main', cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                        onClick={() => navigate(`/repair-orders/${quotation.repair_order_id}`)}
                      >
                        OT #{quotation.repair_order_id}
                      </Typography>
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
                    sx={{ bgcolor: '#F1F5F9', color: '#475569', fontWeight: 600 }}
                  />
                  {canEditLines && (
                    <Box ml="auto !important">
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<AddRoundedIcon />}
                        onClick={() => setShowAddLine(v => !v)}
                        sx={{ textTransform: 'none', fontWeight: 600 }}
                      >
                        Ajouter une ligne
                      </Button>
                    </Box>
                  )}
                </Stack>
                <Divider sx={{ mb: 0 }} />

                {/* Add-line inline form */}
                {showAddLine && canEditLines && (
                  <Box sx={{ py: 2, px: 0.5, borderBottom: '1px solid #E2E8F0', mb: 1 }}>
                    <Stack spacing={1.5}>
                      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                        <TextField
                          select
                          size="small"
                          label="Type"
                          value={lineKind}
                          onChange={e => setLineKind(e.target.value as LineKind)}
                          sx={{ minWidth: 140 }}
                        >
                          {LINE_KINDS.map(k => (
                            <MenuItem key={k} value={k}>{LINE_KIND_LABELS[k]}</MenuItem>
                          ))}
                        </TextField>
                        <TextField
                          size="small"
                          label="Description"
                          value={lineDesc}
                          onChange={e => setLineDesc(e.target.value)}
                          sx={{ flex: 1 }}
                          required
                        />
                      </Stack>
                      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                        <TextField
                          size="small"
                          label="Quantité"
                          type="number"
                          value={lineQty}
                          onChange={e => setLineQty(e.target.value)}
                          sx={{ width: 100 }}
                          inputProps={{ min: 0, step: 0.01 }}
                        />
                        <TextField
                          size="small"
                          label="Prix unitaire HT (TND)"
                          type="number"
                          value={linePrice}
                          onChange={e => setLinePrice(e.target.value)}
                          sx={{ flex: 1 }}
                          inputProps={{ min: 0, step: 0.001 }}
                          required
                        />
                        <TextField
                          size="small"
                          label="Remise (%)"
                          type="number"
                          value={lineDiscount}
                          onChange={e => setLineDiscount(e.target.value)}
                          sx={{ width: 110 }}
                          inputProps={{ min: 0, max: 100 }}
                        />
                        <TextField
                          size="small"
                          label="TVA (%)"
                          type="number"
                          value={lineVat}
                          onChange={e => setLineVat(e.target.value)}
                          sx={{ width: 100 }}
                          inputProps={{ min: 0 }}
                        />
                      </Stack>
                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        <Button size="small" onClick={() => setShowAddLine(false)} sx={{ textTransform: 'none' }}>
                          Annuler
                        </Button>
                        <Button
                          size="small"
                          variant="contained"
                          disabled={addLineMutation.isPending || !lineDesc.trim() || !linePrice}
                          onClick={() => addLineMutation.mutate()}
                          sx={{ textTransform: 'none', fontWeight: 700 }}
                        >
                          {addLineMutation.isPending ? 'Ajout…' : 'Ajouter'}
                        </Button>
                      </Stack>
                    </Stack>
                  </Box>
                )}

                {quotation.lines.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" py={3} textAlign="center">
                    Aucune ligne dans ce devis.{canEditLines && ' Cliquez sur "Ajouter une ligne" pour commencer.'}
                  </Typography>
                ) : (
                  <Box sx={{ overflowX: 'auto' }}>
                    <Table size="small" sx={{ minWidth: 560 }}>
                      <TableHead>
                        <TableRow sx={{ bgcolor: '#F8FAFC' }}>
                          {['Type', 'Description', 'Qté', 'P.U. HT', 'Remise', 'TVA', 'Total HT', ...(canEditLines ? [''] : [])].map(h => (
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
                            <TableRow key={line.id} sx={{ '&:hover': { bgcolor: '#F9FAFB' } }}>
                              <TableCell sx={{ py: 1.5 }}>
                                <Chip
                                  label={LINE_KIND_LABELS[line.kind]}
                                  size="small"
                                  sx={{ bgcolor: kindCfg.bg, color: kindCfg.color, fontWeight: 600, fontSize: '0.6875rem', height: 22 }}
                                />
                              </TableCell>
                              <TableCell sx={{ py: 1.5, maxWidth: 240 }}>
                                <Typography variant="body2" fontWeight={500}>{line.description}</Typography>
                              </TableCell>
                              <TableCell align="right" sx={{ py: 1.5 }}>
                                <Typography variant="body2" fontFamily="monospace" fontWeight={500}>{line.quantity}</Typography>
                              </TableCell>
                              <TableCell align="right" sx={{ py: 1.5 }}>
                                <Typography variant="body2" fontFamily="monospace">{formatMinor(line.unit_price_minor, quotation.currency)}</Typography>
                              </TableCell>
                              <TableCell align="right" sx={{ py: 1.5 }}>
                                <Typography
                                  variant="body2"
                                  color={parseFloat(line.discount_percent) > 0 ? 'warning.dark' : 'text.disabled'}
                                  fontWeight={parseFloat(line.discount_percent) > 0 ? 600 : 400}
                                >
                                  {parseFloat(line.discount_percent) > 0 ? `${parseFloat(line.discount_percent)}%` : '—'}
                                </Typography>
                              </TableCell>
                              <TableCell align="right" sx={{ py: 1.5 }}>
                                <Typography variant="body2" color="text.secondary">{parseFloat(line.vat_rate)}%</Typography>
                              </TableCell>
                              <TableCell align="right" sx={{ py: 1.5 }}>
                                <Typography variant="body2" fontWeight={700} fontFamily="monospace">{formatMinor(line.line_total_minor, quotation.currency)}</Typography>
                              </TableCell>
                              {canEditLines && (
                                <TableCell align="right" sx={{ py: 1.5 }}>
                                  <Tooltip title="Supprimer">
                                    <IconButton
                                      size="small"
                                      color="error"
                                      disabled={removeLineMutation.isPending}
                                      onClick={() => removeLineMutation.mutate(line.id)}
                                    >
                                      <CloseRoundedIcon sx={{ fontSize: 14 }} />
                                    </IconButton>
                                  </Tooltip>
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
                  <TotalRow label="Sous-total HT" value={formatMinor(quotation.subtotal_minor, quotation.currency)} />
                  {quotation.discount_minor > 0 && (
                    <TotalRow label="Remise" value={`− ${formatMinor(quotation.discount_minor, quotation.currency)}`} color="warning.dark" />
                  )}
                  <TotalRow label="TVA" value={formatMinor(quotation.vat_minor, quotation.currency)} />
                  <Divider sx={{ my: 1 }} />
                  <TotalRow label="Total TTC" value={formatMinor(quotation.total_minor, quotation.currency)} bold />
                </Box>

                {/* Actions by status */}
                <Stack spacing={1.25}>
                  {quotation.status === 'draft' && (
                    <Button
                      variant="contained"
                      fullWidth
                      startIcon={<SendRoundedIcon />}
                      onClick={() => sendMutation.mutate()}
                      disabled={anyMutating || quotation.lines.length === 0}
                    >
                      Envoyer au client
                    </Button>
                  )}
                  {quotation.status === 'draft' && quotation.lines.length === 0 && (
                    <Typography variant="caption" color="text.secondary" textAlign="center">
                      Ajoutez au moins une ligne pour envoyer.
                    </Typography>
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
                    <Box sx={{ bgcolor: '#F8FAFC', borderRadius: 1.5, p: 2, textAlign: 'center' }}>
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
