import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import ReceiptLongRoundedIcon from '@mui/icons-material/ReceiptLongRounded'
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded'
import SwapHorizRoundedIcon from '@mui/icons-material/SwapHorizRounded'
import CancelRoundedIcon from '@mui/icons-material/CancelRounded'
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded'
import { deliveryNoteApi, DELIVERY_NOTE_LINE_KIND_LABELS } from '../../lib/deliveryNoteApi'
import { parseCreditLimitError, type CreditLimitExceededDetail } from '../../lib/creditOverrideApi'
import { CreditLimitExceededDialog } from '../../components/credit/CreditLimitExceededDialog'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'
import { PermissionGate } from '../../components/auth/PermissionGate'
import type { StatusKey } from '../../components/ui/StatusChip'

export function DeliveryNoteDetailPage() {
  const { publicId = '' } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()

  const [confirmCancel, setConfirmCancel] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)
  const [creditLimitDetail, setCreditLimitDetail] = useState<CreditLimitExceededDetail | null>(null)

  const { data: dn, isLoading, isError } = useQuery({
    queryKey: ['delivery-note', publicId],
    queryFn: () => deliveryNoteApi.get(publicId),
    enabled: !!publicId,
  })

  const handleIssue = async () => {
    setActionLoading(true)
    try {
      await deliveryNoteApi.issue(publicId)
      await queryClient.invalidateQueries({ queryKey: ['delivery-note', publicId] })
      success('Bon de livraison émis')
    } catch (err) {
      const creditError = parseCreditLimitError(err)
      if (creditError) {
        setCreditLimitDetail(creditError)
      } else {
        toastError('Erreur lors de l\'émission.')
      }
    } finally {
      setActionLoading(false)
    }
  }

  const handleMarkDelivered = async () => {
    setActionLoading(true)
    try {
      await deliveryNoteApi.markDelivered(publicId)
      await queryClient.invalidateQueries({ queryKey: ['delivery-note', publicId] })
      success('Bon de livraison marqué livré')
    } catch { toastError('Erreur lors de la mise à jour.') }
    finally { setActionLoading(false) }
  }

  const handleConvertToInvoice = async () => {
    setActionLoading(true)
    try {
      const updated = await deliveryNoteApi.convertToInvoice(publicId)
      await queryClient.invalidateQueries({ queryKey: ['delivery-note', publicId] })
      success('Facture créée depuis ce BL')
      if (updated.invoice_public_id) {
        navigate(`/invoices/${updated.invoice_public_id}`)
      }
    } catch { toastError('Erreur lors de la conversion.') }
    finally { setActionLoading(false) }
  }

  const handleCancel = async () => {
    setActionLoading(true)
    try {
      await deliveryNoteApi.cancel(publicId)
      await queryClient.invalidateQueries({ queryKey: ['delivery-note', publicId] })
      success('Bon de livraison annulé')
      setConfirmCancel(false)
    } catch { toastError('Erreur lors de l\'annulation.') }
    finally { setActionLoading(false) }
  }

  const handlePdfPreview = async () => {
    if (!dn) return
    setPdfLoading(true)
    try {
      const token = localStorage.getItem('access_token')
      const response = await axios.get(
        `/api/v1/pdf/delivery-notes/${dn.id}`,
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

  if (isLoading) return <LoadingScreen />
  if (isError || !dn) return <Typography color="error">Impossible de charger ce bon de livraison.</Typography>

  const isDraft = dn.status === 'draft'
  const isIssued = dn.status === 'issued'
  const isDelivered = dn.status === 'delivered'
  const canConvert = (isIssued || isDelivered) && !dn.invoice_id

  return (
    <Box>
      <PageHeader
        title={dn.doc_number ?? `BL #${dn.id}`}
        subtitle="Bon de livraison"
        breadcrumbs={[
          { label: 'Facturation', href: '/invoices' },
          { label: dn.doc_number ?? `BL #${dn.id}` },
        ]}
        actions={
          <Stack direction="row" spacing={1} alignItems="center">
            <StatusChip status={dn.status as StatusKey} />
            {dn.status !== 'draft' && (
              <Button
                variant="outlined"
                size="small"
                startIcon={<PictureAsPdfRoundedIcon />}
                onClick={handlePdfPreview}
                disabled={pdfLoading}
              >
                {pdfLoading ? 'Génération…' : 'Aperçu PDF'}
              </Button>
            )}
            <PermissionGate permission="invoice.issue">
              {isDraft && (
                <Button
                  variant="contained"
                  size="small"
                  onClick={handleIssue}
                  disabled={actionLoading}
                >
                  Émettre
                </Button>
              )}
              {isIssued && (
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<LocalShippingRoundedIcon />}
                  onClick={handleMarkDelivered}
                  disabled={actionLoading}
                >
                  Marquer livré
                </Button>
              )}
            </PermissionGate>
            <PermissionGate permission="invoice.create">
              {canConvert && (
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<SwapHorizRoundedIcon />}
                  onClick={handleConvertToInvoice}
                  disabled={actionLoading}
                >
                  Convertir en facture
                </Button>
              )}
            </PermissionGate>
            <PermissionGate permission="invoice.cancel">
              {(isDraft || isIssued) && (
                <Button
                  variant="outlined"
                  color="error"
                  size="small"
                  startIcon={<CancelRoundedIcon />}
                  onClick={() => setConfirmCancel(true)}
                  disabled={actionLoading}
                >
                  Annuler
                </Button>
              )}
            </PermissionGate>
          </Stack>
        }
      />

      <Stack spacing={3}>
        {/* Header info */}
        <Card>
          <CardContent sx={{ p: 3 }}>
            <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
              <Box sx={{ color: 'primary.main' }}>
                <ReceiptLongRoundedIcon sx={{ fontSize: 20 }} />
              </Box>
              <Typography variant="subtitle1" fontWeight={700}>Détails</Typography>
            </Stack>
            <Divider sx={{ mb: 2 }} />
            <Stack spacing={1}>
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="body2" color="text.secondary">Référence</Typography>
                <Typography variant="body2" fontFamily="monospace" fontWeight={600}>
                  {dn.doc_number ?? '—'}
                </Typography>
              </Stack>
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="body2" color="text.secondary">Statut</Typography>
                <StatusChip status={dn.status as StatusKey} />
              </Stack>
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="body2" color="text.secondary">Devise</Typography>
                <Typography variant="body2">{dn.currency}</Typography>
              </Stack>
              {dn.issued_at && (
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Date d'émission</Typography>
                  <Typography variant="body2">
                    {new Date(dn.issued_at).toLocaleDateString('fr-FR')}
                  </Typography>
                </Stack>
              )}
              {dn.delivered_at && (
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Date de livraison</Typography>
                  <Typography variant="body2">
                    {new Date(dn.delivered_at).toLocaleDateString('fr-FR')}
                  </Typography>
                </Stack>
              )}
              {dn.invoice_id && (
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Facture associée</Typography>
                  <Button
                    size="small"
                    variant="text"
                    sx={{ p: 0, minWidth: 0 }}
                    onClick={() => navigate(`/invoices/${dn.invoice_public_id ?? dn.invoice_id}`)}
                  >
                    Facture #{dn.invoice_id}
                  </Button>
                </Stack>
              )}
              {dn.notes && (
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Notes</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ maxWidth: '60%', textAlign: 'right' }}>
                    {dn.notes}
                  </Typography>
                </Stack>
              )}
            </Stack>
          </CardContent>
        </Card>

        {/* Lines */}
        <Card>
          <CardContent sx={{ p: 3 }}>
            <Stack direction="row" alignItems="center" spacing={1.5} mb={2}>
              <Box sx={{ color: 'primary.main' }}>
                <LocalShippingRoundedIcon sx={{ fontSize: 20 }} />
              </Box>
              <Typography variant="subtitle1" fontWeight={700}>Lignes</Typography>
            </Stack>
            <Divider sx={{ mb: 2 }} />
            {dn.lines.length === 0 ? (
              <Typography variant="body2" color="text.disabled" py={1}>
                Aucune ligne.
              </Typography>
            ) : (
              <>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Type</TableCell>
                      <TableCell>Description</TableCell>
                      <TableCell align="right">Qté</TableCell>
                      <TableCell align="right">P.U.</TableCell>
                      <TableCell align="right">TVA %</TableCell>
                      <TableCell align="right">Total TTC</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {dn.lines.map((line) => (
                      <TableRow key={line.id}>
                        <TableCell>
                          <Chip
                            label={DELIVERY_NOTE_LINE_KIND_LABELS[line.kind] ?? line.kind}
                            size="small"
                            sx={{ fontSize: '0.65rem', height: 20 }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{line.description}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontFamily="monospace">{line.quantity}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontFamily="monospace">
                            {formatMinor(line.unit_price_minor, dn.currency)}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontFamily="monospace">{line.vat_rate}%</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontFamily="monospace" fontWeight={600}>
                            {formatMinor(
                              line.line_total_minor + Math.round(line.line_total_minor * parseFloat(String(line.vat_rate)) / 100),
                              dn.currency,
                            )}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                <Stack alignItems="flex-end" mt={2} spacing={0.5}>
                  <Stack direction="row" spacing={4}>
                    <Typography variant="body2" color="text.secondary">Sous-total HT</Typography>
                    <Typography variant="body2" fontFamily="monospace">
                      {formatMinor(dn.subtotal_minor, dn.currency)}
                    </Typography>
                  </Stack>
                  <Stack direction="row" spacing={4}>
                    <Typography variant="body2" color="text.secondary">TVA</Typography>
                    <Typography variant="body2" fontFamily="monospace">
                      {formatMinor(dn.vat_minor, dn.currency)}
                    </Typography>
                  </Stack>
                  <Divider sx={{ width: 200 }} />
                  <Stack direction="row" spacing={4}>
                    <Typography variant="subtitle2" fontWeight={700}>Total TTC</Typography>
                    <Typography variant="subtitle2" fontFamily="monospace" fontWeight={700}>
                      {formatMinor(dn.total_minor, dn.currency)}
                    </Typography>
                  </Stack>
                </Stack>
              </>
            )}
          </CardContent>
        </Card>
      </Stack>

      <ConfirmDialog
        open={confirmCancel}
        title="Annuler ce bon de livraison ?"
        message="Cette action est irréversible."
        confirmLabel="Annuler le BL"
        dangerous
        loading={actionLoading}
        onConfirm={handleCancel}
        onCancel={() => setConfirmCancel(false)}
      />

      <CreditLimitExceededDialog
        open={creditLimitDetail !== null}
        detail={creditLimitDetail}
        documentPublicId={publicId}
        onClose={() => setCreditLimitDetail(null)}
      />
    </Box>
  )
}
