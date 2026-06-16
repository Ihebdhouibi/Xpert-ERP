import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import AccountBalanceRoundedIcon from '@mui/icons-material/AccountBalanceRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import PictureAsPdfRoundedIcon from '@mui/icons-material/PictureAsPdfRounded'
import UndoRoundedIcon from '@mui/icons-material/UndoRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import { AxiosError } from 'axios'
import {
  bonRetourApi,
  BON_RETOUR_CONDITION_LABELS,
  BON_RETOUR_PARTY_LABELS,
  BON_RETOUR_STATUS_LABELS,
  type BonRetourOut,
} from '../../lib/bonRetourApi'
import { invoiceApi, type InvoiceOut } from '../../lib/invoiceApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { LoadingScreen } from '../../components/ui/LoadingScreen'
import { useToast } from '../../contexts/ToastContext'

function errMsg(e: unknown, fallback: string): string {
  const detail = (e as AxiosError<{ detail?: string }>)?.response?.data?.detail
  return typeof detail === 'string' ? detail : fallback
}

export function BonRetourDetailPage() {
  const { publicId = '' } = useParams()
  const qc = useQueryClient()
  const { success, error } = useToast()

  const [confirmOpen, setConfirmOpen] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [avoirOpen, setAvoirOpen] = useState(false)
  const [reverseOpen, setReverseOpen] = useState(false)
  const [pdfLoading, setPdfLoading] = useState(false)

  const { data: bdr, isLoading, isError } = useQuery({
    queryKey: ['bon-de-retour', publicId],
    queryFn: () => bonRetourApi.get(publicId),
  })

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['bon-de-retour'] })
  }

  const confirmMut = useMutation({
    mutationFn: () => bonRetourApi.confirm(publicId),
    onSuccess: () => { success('Bon de retour confirmé — stock mis à jour.'); setConfirmOpen(false); invalidate() },
    onError: e => error(errMsg(e, 'Impossible de confirmer le bon de retour.')),
  })
  const cancelMut = useMutation({
    mutationFn: () => bonRetourApi.cancel(publicId),
    onSuccess: () => { success('Bon de retour annulé.'); setCancelOpen(false); invalidate() },
    onError: e => error(errMsg(e, "Impossible d'annuler le bon de retour.")),
  })

  const reverseMut = useMutation({
    mutationFn: () => bonRetourApi.reverse(publicId),
    onSuccess: () => { success('Bon de retour contre-passé — mouvements de stock annulés.'); setReverseOpen(false); invalidate() },
    onError: e => error(errMsg(e, 'Impossible de contre-passer le bon de retour.')),
  })

  const handlePdfPreview = async () => {
    setPdfLoading(true)
    try {
      const data = await bonRetourApi.getPdf(publicId)
      const url = URL.createObjectURL(new Blob([data], { type: 'application/pdf' }))
      window.open(url, '_blank')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      error('Impossible de générer le PDF.')
    } finally {
      setPdfLoading(false)
    }
  }

  if (isLoading) return <LoadingScreen />
  if (isError || !bdr) return <Alert severity="error">Bon de retour introuvable.</Alert>

  const isSupplier = bdr.party_type === 'supplier'
  const tiers = isSupplier
    ? bdr.supplier_name ?? `Fournisseur #${bdr.supplier_id}`
    : bdr.customer_name ?? `Client #${bdr.customer_id}`
  const avoirDoc = bdr.credit_note_doc_number ?? bdr.supplier_credit_note_doc_number
  const hasAvoir = bdr.credit_note_id != null || bdr.supplier_credit_note_id != null

  return (
    <Box>
      <PageHeader
        title={bdr.doc_number ?? 'Bon de retour (brouillon)'}
        subtitle={`${BON_RETOUR_PARTY_LABELS[bdr.party_type]} · ${tiers}`}
        breadcrumbs={[{ label: 'Bons de retour', href: '/bon-retour' }, { label: bdr.doc_number ?? 'Brouillon' }]}
        actions={
          <Stack direction="row" spacing={1.5} alignItems="center">
            <StatusChip status={bdr.status} label={BON_RETOUR_STATUS_LABELS[bdr.status]} size="medium" />
            <Button
              variant="outlined"
              size="small"
              startIcon={<PictureAsPdfRoundedIcon />}
              onClick={handlePdfPreview}
              disabled={pdfLoading}
            >
              {pdfLoading ? 'Génération…' : 'PDF'}
            </Button>
            {bdr.status === 'draft' && (
              <>
                <Button color="inherit" onClick={() => setCancelOpen(true)}>Annuler</Button>
                <Button
                  variant="contained"
                  onClick={() => setConfirmOpen(true)}
                  sx={{ bgcolor: '#EA580C', '&:hover': { bgcolor: '#C2410C' } }}
                >
                  Confirmer le retour
                </Button>
              </>
            )}
            {bdr.status === 'confirmed' && (
              <>
                <Button
                  color="inherit"
                  size="small"
                  startIcon={<UndoRoundedIcon />}
                  onClick={() => setReverseOpen(true)}
                >
                  Contrepasser
                </Button>
                {!hasAvoir && (
                  <Button
                    variant="contained"
                    startIcon={<AccountBalanceRoundedIcon />}
                    onClick={() => setAvoirOpen(true)}
                    sx={{ bgcolor: '#EA580C', '&:hover': { bgcolor: '#C2410C' } }}
                  >
                    Créer un avoir
                  </Button>
                )}
              </>
            )}
          </Stack>
        }
      />

      {bdr.status === 'reversed' && (
        <Alert
          icon={<WarningAmberRoundedIcon fontSize="inherit" />}
          severity="warning"
          sx={{ mb: 2 }}
        >
          Ce bon de retour a été contre-passé — les mouvements de stock ont été annulés.
        </Alert>
      )}
      {hasAvoir && (
        <Alert
          icon={<CheckCircleRoundedIcon fontSize="inherit" />}
          severity="success"
          sx={{ mb: 2 }}
        >
          Avoir lié : <strong>{avoirDoc ?? '—'}</strong>
        </Alert>
      )}

      <Stack spacing={2.5} sx={{ maxWidth: 980 }}>
        {bdr.reason && (
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary">Motif</Typography>
            <Typography variant="body2">{bdr.reason}</Typography>
          </Paper>
        )}

        <Paper variant="outlined" sx={{ p: 0, overflow: 'hidden' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Pièce / description</TableCell>
                <TableCell align="center">État</TableCell>
                {!isSupplier && <TableCell align="center">Réintégrée</TableCell>}
                <TableCell align="right">Qté</TableCell>
                <TableCell align="right">P.U. HT</TableCell>
                <TableCell align="right">Total HT</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {bdr.lines.map(line => (
                <TableRow key={line.id}>
                  <TableCell>{line.description}</TableCell>
                  <TableCell align="center">
                    {line.condition ? BON_RETOUR_CONDITION_LABELS[line.condition] : '—'}
                  </TableCell>
                  {!isSupplier && (
                    <TableCell align="center">
                      <Chip
                        size="small"
                        label={line.restock ? 'Oui' : 'Non'}
                        sx={{ height: 20, fontSize: '0.7rem', bgcolor: line.restock ? '#F0FDF4' : '#F8FAFC' }}
                      />
                    </TableCell>
                  )}
                  <TableCell align="right">{line.quantity}</TableCell>
                  <TableCell align="right">{formatMinor(line.unit_price_minor, bdr.currency)}</TableCell>
                  <TableCell align="right">{formatMinor(line.line_total_minor, bdr.currency)}</TableCell>
                </TableRow>
              ))}
              {bdr.lines.length === 0 && (
                <TableRow>
                  <TableCell colSpan={isSupplier ? 5 : 6} align="center">
                    <Typography variant="body2" color="text.disabled" sx={{ py: 2 }}>Aucune ligne</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          <Divider />
          <Stack spacing={0.5} sx={{ p: 2, ml: 'auto', width: 260 }}>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="body2" color="text.secondary">Sous-total HT</Typography>
              <Typography variant="body2">{formatMinor(bdr.subtotal_minor, bdr.currency)}</Typography>
            </Stack>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="body2" color="text.secondary">TVA</Typography>
              <Typography variant="body2">{formatMinor(bdr.vat_minor, bdr.currency)}</Typography>
            </Stack>
            <Stack direction="row" justifyContent="space-between">
              <Typography variant="body2" fontWeight={700}>Total TTC</Typography>
              <Typography variant="body2" fontWeight={700}>{formatMinor(bdr.total_minor, bdr.currency)}</Typography>
            </Stack>
          </Stack>
        </Paper>
      </Stack>

      <ConfirmDialog
        open={confirmOpen}
        title="Confirmer le bon de retour"
        message={
          isSupplier
            ? 'Le stock des pièces retournées sera diminué (sortie). Un numéro BR sera attribué. Continuer ?'
            : 'Les pièces marquées « réintégrée » seront ajoutées au stock. Un numéro BR sera attribué. Continuer ?'
        }
        confirmLabel="Confirmer"
        loading={confirmMut.isPending}
        onConfirm={() => confirmMut.mutate()}
        onCancel={() => setConfirmOpen(false)}
      />
      <ConfirmDialog
        open={cancelOpen}
        title="Annuler le bon de retour"
        message="Ce brouillon sera annulé. Cette action est irréversible."
        confirmLabel="Annuler le bon"
        dangerous
        loading={cancelMut.isPending}
        onConfirm={() => cancelMut.mutate()}
        onCancel={() => setCancelOpen(false)}
      />
      <ConfirmDialog
        open={reverseOpen}
        title="Contre-passer le bon de retour"
        message={
          isSupplier
            ? 'Les pièces retournées seront réintégrées au stock (mouvement inverse). Cette action est irréversible.'
            : 'Les pièces précédemment réintégrées seront retirées du stock (mouvement inverse). Cette action est irréversible.'
        }
        confirmLabel="Contre-passer"
        dangerous
        loading={reverseMut.isPending}
        onConfirm={() => reverseMut.mutate()}
        onCancel={() => setReverseOpen(false)}
      />

      {avoirOpen && (
        <AvoirDialog
          bdr={bdr}
          onClose={() => setAvoirOpen(false)}
          onCreated={() => { setAvoirOpen(false); invalidate() }}
        />
      )}
    </Box>
  )
}

// ── Avoir creation dialog ────────────────────────────────────────────────────

function AvoirDialog({
  bdr,
  onClose,
  onCreated,
}: {
  bdr: BonRetourOut
  onClose: () => void
  onCreated: () => void
}) {
  const { success, error } = useToast()
  const isSupplier = bdr.party_type === 'supplier'
  const [reason, setReason] = useState('')
  const [amountStr, setAmountStr] = useState(String(bdr.total_minor / 100))
  const [invoice, setInvoice] = useState<InvoiceOut | null>(null)

  const { data: invoices } = useQuery({
    queryKey: ['invoices', 'bdr-avoir', bdr.customer_id],
    queryFn: () => invoiceApi.list({ customer_id: bdr.customer_id!, page: 1, page_size: 100 }),
    enabled: !isSupplier && bdr.customer_id != null,
    select: data => data.items.filter(i => ['issued', 'partial', 'paid'].includes(i.status)),
  })

  const amountMinor = Math.round((parseFloat(amountStr) || 0) * 100)
  // Client avoir needs an invoice (the BR's source invoice or a selected one).
  const needsInvoice = !isSupplier && bdr.source_invoice_id == null
  const canSubmit = isSupplier
    ? amountMinor >= 0
    : amountMinor >= 1 && (!needsInvoice || invoice != null)

  const mutation = useMutation({
    mutationFn: () =>
      isSupplier
        ? bonRetourApi.createSupplierCreditNote(bdr.public_id, {
            total_ttc_minor: amountMinor,
            reason: reason.trim() || null,
          })
        : bonRetourApi.createCreditNote(bdr.public_id, {
            invoice_id: invoice?.id ?? null,
            total_minor: amountMinor,
            reason: reason.trim() || null,
          }),
    onSuccess: () => { success('Avoir créé et lié au bon de retour.'); onCreated() },
    onError: e => error(errMsg(e, "Impossible de créer l'avoir.")),
  })

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <AccountBalanceRoundedIcon sx={{ color: '#EA580C', fontSize: 22 }} />
        {isSupplier ? 'Nouvel avoir fournisseur' : 'Nouvel avoir client'}
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ pt: 2.5 }}>
        <Stack spacing={2.5}>
          {needsInvoice && (
            <Autocomplete
              options={invoices ?? []}
              getOptionLabel={i => `${i.doc_number ?? `Brouillon #${i.id}`} — ${formatMinor(i.total_minor, i.currency)}`}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              value={invoice}
              onChange={(_, v) => setInvoice(v)}
              renderInput={params => <TextField {...params} label="Facture liée" size="small" required />}
              noOptionsText="Aucune facture"
            />
          )}
          <TextField
            label="Montant de l'avoir (TTC)"
            type="number"
            size="small"
            fullWidth
            value={amountStr}
            onChange={e => setAmountStr(e.target.value)}
            inputProps={{ min: 0, step: 0.01 }}
          />
          <TextField
            label="Motif (optionnel)"
            size="small"
            fullWidth
            multiline
            rows={2}
            value={reason}
            onChange={e => setReason(e.target.value)}
          />
        </Stack>
      </DialogContent>
      <Divider />
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button color="inherit" onClick={onClose} disabled={mutation.isPending}>Annuler</Button>
        <Button
          variant="contained"
          disabled={!canSubmit || mutation.isPending}
          onClick={() => mutation.mutate()}
          sx={{ bgcolor: '#EA580C', '&:hover': { bgcolor: '#C2410C' } }}
        >
          {mutation.isPending ? "Création…" : "Créer l'avoir"}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
