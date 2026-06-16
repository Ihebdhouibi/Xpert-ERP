import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Autocomplete,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import AccountBalanceRoundedIcon from '@mui/icons-material/AccountBalanceRounded'
import MoneyOffRoundedIcon from '@mui/icons-material/MoneyOffRounded'
import { creditNoteApi, CREDIT_NOTE_STATUS_LABELS, type CreditNoteOut } from '../../lib/creditNoteApi'
import { invoiceApi, type InvoiceOut } from '../../lib/invoiceApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { useToast } from '../../contexts/ToastContext'

// ── Nouvel avoir dialog (invoice picker + form) ──────────────────────────────

function NewCreditNoteDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const { error: toastError } = useToast()

  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceOut | null>(null)
  const [amountStr, setAmountStr] = useState<string>('')
  const [reason, setReason] = useState<string>('')

  const { data: invoiceList, isLoading: invoicesLoading } = useQuery({
    queryKey: ['invoices-for-cn-picker'],
    queryFn: () => invoiceApi.list({ page: 1, page_size: 200 }),
    enabled: open,
    select: data => data.items.filter(i => i.status === 'issued' || i.status === 'partial' || i.status === 'paid'),
  })

  const maxMinor = selectedInvoice?.total_minor ?? 0
  const maxAmount = maxMinor / 100
  const amountValue = parseFloat(amountStr) || 0
  const amountMinor = Math.round(amountValue * 100)
  const amountError =
    !selectedInvoice
      ? ''
      : amountValue <= 0
      ? 'Le montant doit être supérieur à 0'
      : amountMinor > maxMinor
      ? `Le montant ne peut pas dépasser ${formatMinor(maxMinor, selectedInvoice.currency)}`
      : ''

  const mutation = useMutation({
    mutationFn: () =>
      creditNoteApi.create({
        invoice_id: selectedInvoice!.id,
        total_minor: amountMinor,
        reason: reason.trim() || null,
      }),
    onSuccess: result => {
      handleClose()
      navigate(`/credit-notes/${result.id}`)
    },
    onError: () => toastError('Impossible de créer l\'avoir.'),
  })

  const handleClose = () => {
    setSelectedInvoice(null)
    setAmountStr('')
    setReason('')
    onClose()
  }

  const handleInvoiceChange = (inv: InvoiceOut | null) => {
    setSelectedInvoice(inv)
    setAmountStr(inv ? String(inv.total_minor / 100) : '')
  }

  const canSubmit = !!selectedInvoice && !amountError && amountValue > 0 && !mutation.isPending

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1, pb: 1 }}>
        <AccountBalanceRoundedIcon sx={{ color: '#EA580C', fontSize: 22 }} />
        Nouvel avoir
      </DialogTitle>
      <Divider />
      <DialogContent sx={{ pt: 2.5 }}>
        <Stack spacing={2.5}>
          <Autocomplete
            options={invoiceList ?? []}
            loading={invoicesLoading}
            value={selectedInvoice}
            onChange={(_, v) => handleInvoiceChange(v)}
            getOptionLabel={inv => `${inv.doc_number ?? `Brouillon #${inv.id}`} — ${inv.customer_name ?? `Client #${inv.customer_id}`}`}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            renderInput={params => (
              <TextField
                {...params}
                label="Facture liée"
                size="small"
                placeholder="Rechercher par numéro ou client…"
              />
            )}
            noOptionsText="Aucune facture trouvée"
          />

          {selectedInvoice && (
            <Stack
              direction="row"
              justifyContent="space-between"
              alignItems="center"
              sx={{ bgcolor: '#F8FAFC', borderRadius: 1.5, px: 2, py: 1.25 }}
            >
              <Typography variant="body2" color="text.secondary" fontWeight={500}>
                Total TTC de la facture
              </Typography>
              <Typography variant="body2" fontWeight={700}>
                {formatMinor(selectedInvoice.total_minor, selectedInvoice.currency)}
              </Typography>
            </Stack>
          )}

          <TextField
            label="Montant de l'avoir (TTC)"
            type="number"
            inputProps={{ min: 0.01, max: maxAmount, step: 0.01 }}
            value={amountStr}
            onChange={e => setAmountStr(e.target.value)}
            error={!!amountError && amountStr !== ''}
            helperText={amountStr !== '' ? amountError : ''}
            fullWidth
            size="small"
            disabled={!selectedInvoice}
            InputProps={{
              endAdornment: selectedInvoice ? (
                <Typography variant="body2" color="text.secondary" sx={{ ml: 0.5, flexShrink: 0 }}>
                  {selectedInvoice.currency}
                </Typography>
              ) : undefined,
            }}
          />

          <TextField
            label="Motif (optionnel)"
            placeholder="Erreur de facturation, remise oubliée, retour pièce…"
            value={reason}
            onChange={e => setReason(e.target.value)}
            fullWidth
            size="small"
            multiline
            rows={3}
            disabled={!selectedInvoice}
            inputProps={{ maxLength: 500 }}
          />
        </Stack>
      </DialogContent>
      <Divider />
      <DialogActions sx={{ px: 3, py: 2, gap: 1 }}>
        <Button onClick={handleClose} disabled={mutation.isPending} color="inherit">
          Annuler
        </Button>
        <Button
          variant="contained"
          onClick={() => mutation.mutate()}
          disabled={!canSubmit}
          sx={{ bgcolor: '#EA580C', '&:hover': { bgcolor: '#C2410C' } }}
        >
          {mutation.isPending ? 'Création…' : 'Créer l\'avoir'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

const columns: Column<CreditNoteOut>[] = [
  {
    id: 'number',
    label: 'Numéro',
    width: 170,
    render: row => (
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Box
          sx={{
            width: 34,
            height: 34,
            borderRadius: '9px',
            bgcolor: '#FFF7ED',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <AccountBalanceRoundedIcon sx={{ color: '#EA580C', fontSize: 17 }} />
        </Box>
        <Stack spacing={0.25}>
          <Typography variant="body2" fontWeight={700} fontFamily="monospace">
            {row.doc_number ?? (
              <Typography component="span" variant="caption" color="text.disabled" fontFamily="inherit">
                Brouillon
              </Typography>
            )}
          </Typography>
          <Typography variant="caption" color="text.secondary" fontFamily="monospace">
            Facture #{row.invoice_id}
          </Typography>
        </Stack>
      </Stack>
    ),
  },
  {
    id: 'amount',
    label: 'Montant avoir',
    align: 'right',
    width: 130,
    render: row => {
      const totalRefunded = (row.refunds ?? []).reduce((s, r) => s + r.amount_minor, 0)
      return (
        <Stack alignItems="flex-end" spacing={0.25}>
          <Typography variant="body2" fontWeight={700} color="error.main">
            -{formatMinor(row.total_minor)}
          </Typography>
          {totalRefunded > 0 && (
            <Stack direction="row" alignItems="center" spacing={0.5}>
              <MoneyOffRoundedIcon sx={{ fontSize: 11, color: 'success.main' }} />
              <Typography variant="caption" color="success.main" fontWeight={600}>
                -{formatMinor(totalRefunded)} remb.
              </Typography>
            </Stack>
          )}
        </Stack>
      )
    },
  },
  {
    id: 'reason',
    label: 'Motif',
    render: row => (
      <Typography variant="body2" color="text.secondary" noWrap sx={{ maxWidth: 260 }}>
        {row.reason ?? '—'}
      </Typography>
    ),
  },
  {
    id: 'status',
    label: 'Statut',
    width: 130,
    render: row => {
      const totalRefunded = (row.refunds ?? []).reduce((s, r) => s + r.amount_minor, 0)
      const fullyRefunded = totalRefunded >= row.total_minor
      return (
        <Stack spacing={0.5}>
          <StatusChip status={row.status} label={CREDIT_NOTE_STATUS_LABELS[row.status]} />
          {row.status === 'issued' && row.refunds.length > 0 && (
            <Chip
              label={fullyRefunded ? 'Remboursé' : 'Part. remb.'}
              size="small"
              sx={{
                height: 18,
                fontSize: '0.625rem',
                fontWeight: 700,
                bgcolor: fullyRefunded ? '#F0FDF4' : '#FFFBEB',
                color: fullyRefunded ? '#16A34A' : '#D97706',
              }}
            />
          )}
        </Stack>
      )
    },
  },
  {
    id: 'date',
    label: 'Créé le',
    width: 100,
    render: row => (
      <Typography variant="caption" color="text.secondary">
        {new Date(row.created_at).toLocaleDateString('fr-FR')}
      </Typography>
    ),
  },
]

export function CreditNotesPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { success, error } = useToast()
  const [page, setPage] = useState(0)
  const [voidTarget, setVoidTarget] = useState<CreditNoteOut | null>(null)
  const [newOpen, setNewOpen] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['credit-notes', page],
    queryFn: () => creditNoteApi.list({ page: page + 1, page_size: 20 }),
  })

  const voidMutation = useMutation({
    mutationFn: (id: number) => creditNoteApi.void(id),
    onSuccess: () => {
      success('Avoir annulé.')
      setVoidTarget(null)
      void qc.invalidateQueries({ queryKey: ['credit-notes'] })
    },
    onError: () => error('Impossible d\'annuler cet avoir.'),
  })

  return (
    <Box>
      <PageHeader
        title="Avoirs"
        subtitle="Notes de crédit et remboursements clients"
        actions={
          <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setNewOpen(true)}
            sx={{ bgcolor: '#EA580C', '&:hover': { bgcolor: '#C2410C' } }}
          >
            Nouvel avoir
          </Button>
        }
      />

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        getRowKey={r => String(r.id)}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger les avoirs."
        total={data?.total}
        page={page}
        pageSize={20}
        onPageChange={setPage}
        emptyTitle="Aucun avoir"
        emptyDescription="Les avoirs sont créés à partir d'une facture existante."
        onRowClick={row => navigate(`/credit-notes/${row.id}`)}
      />

      <NewCreditNoteDialog open={newOpen} onClose={() => setNewOpen(false)} />

      <ConfirmDialog
        open={voidTarget !== null}
        title="Annuler l'avoir"
        message={`Voulez-vous annuler l'avoir ${voidTarget?.doc_number ?? `#${voidTarget?.id}`} ? Cette action est irréversible.`}
        confirmLabel="Annuler l'avoir"
        dangerous
        loading={voidMutation.isPending}
        onConfirm={() => voidTarget && voidMutation.mutate(voidTarget.id)}
        onCancel={() => setVoidTarget(null)}
      />
    </Box>
  )
}
