import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import { invoiceApi, INVOICE_STATUS_LABELS, type InvoiceOut, type InvoiceStatus } from '../../lib/invoiceApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { CustomerAutocomplete } from '../../components/ui/CustomerAutocomplete'
import { useToast } from '../../contexts/ToastContext'

function PaymentProgress({ total, paid, currency }: { total: number; paid: number; currency: string }) {
  const pct = total > 0 ? Math.min((paid / total) * 100, 100) : 0
  return (
    <Tooltip title={`${formatMinor(paid, currency)} payé sur ${formatMinor(total, currency)}`}>
      <Box sx={{ width: 90 }}>
        <LinearProgress
          variant="determinate"
          value={pct}
          color={pct === 100 ? 'success' : pct > 0 ? 'warning' : 'inherit'}
          sx={{ height: 6, borderRadius: 999, mb: 0.5 }}
        />
        <Typography variant="caption" color="text.secondary">
          {Math.round(pct)}%
        </Typography>
      </Box>
    </Tooltip>
  )
}

const STATUS_FILTERS: { value: InvoiceStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'Toutes' },
  { value: 'draft', label: 'Brouillons' },
  { value: 'issued', label: 'Émises' },
  { value: 'partial', label: 'Part. payées' },
  { value: 'paid', label: 'Payées' },
  { value: 'cancelled', label: 'Annulées' },
]

const columns: Column<InvoiceOut>[] = [
  {
    id: 'number',
    label: 'Numéro',
    width: 150,
    render: row => (
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Box
          sx={{
            width: 34,
            height: 34,
            borderRadius: '9px',
            bgcolor: '#EFF6FF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <ReceiptRoundedIcon sx={{ color: '#2563EB', fontSize: 17 }} />
        </Box>
        <Box>
          <Typography variant="body2" fontWeight={700} fontFamily="monospace">
            {row.doc_number ?? (
              <Typography component="span" variant="caption" color="text.disabled" fontFamily="inherit">
                Brouillon
              </Typography>
            )}
          </Typography>
          {row.issued_at && (
            <Typography variant="caption" color="text.secondary">
              {new Date(row.issued_at).toLocaleDateString('fr-FR')}
            </Typography>
          )}
        </Box>
      </Stack>
    ),
  },
  {
    id: 'customer',
    label: 'Client',
    render: row => (
      <Typography variant="body2" fontWeight={500}>
        Client #{row.customer_id}
      </Typography>
    ),
  },
  {
    id: 'total',
    label: 'Total TTC',
    align: 'right',
    width: 130,
    render: row => (
      <Typography variant="body2" fontWeight={700}>
        {formatMinor(row.total_minor, row.currency)}
      </Typography>
    ),
  },
  {
    id: 'outstanding',
    label: 'Restant dû',
    align: 'right',
    width: 130,
    render: row => (
      <Typography
        variant="body2"
        fontWeight={700}
        color={row.outstanding_minor > 0 && row.status !== 'draft' ? 'error.main' : 'text.secondary'}
      >
        {row.outstanding_minor > 0 ? formatMinor(row.outstanding_minor, row.currency) : '—'}
      </Typography>
    ),
  },
  {
    id: 'progress',
    label: 'Paiement',
    width: 110,
    render: row =>
      row.status === 'draft' || row.status === 'cancelled' ? (
        <Typography variant="caption" color="text.disabled">—</Typography>
      ) : (
        <PaymentProgress
          total={row.total_minor}
          paid={row.paid_amount_minor}
          currency={row.currency}
        />
      ),
  },
  {
    id: 'due',
    label: 'Échéance',
    width: 120,
    render: row => {
      if (!row.due_at) return <Typography variant="caption" color="text.disabled">—</Typography>
      const overdue = new Date(row.due_at) < new Date() && row.status !== 'paid' && row.status !== 'cancelled'
      return (
        <Typography
          variant="body2"
          color={overdue ? 'error.main' : 'text.secondary'}
          fontWeight={overdue ? 700 : 400}
        >
          {new Date(row.due_at).toLocaleDateString('fr-FR')}
        </Typography>
      )
    },
  },
  {
    id: 'status',
    label: 'Statut',
    width: 130,
    render: row => <StatusChip status={row.status} label={INVOICE_STATUS_LABELS[row.status]} />,
  },
]

function CreateInvoiceDialog({ open, onClose, onCreated }: {
  open: boolean
  onClose: () => void
  onCreated: (publicId: string) => void
}) {
  const { error: toastError } = useToast()
  const [customerId, setCustomerId] = useState<number | null>(null)
  const [dueAt, setDueAt] = useState('')
  const [notes, setNotes] = useState('')
  const [customerError, setCustomerError] = useState(false)

  const mutation = useMutation({
    mutationFn: () =>
      invoiceApi.create({
        customer_id: customerId!,
        due_at: dueAt ? `${dueAt}T00:00:00` : null,
        notes: notes || null,
      }),
    onSuccess: inv => {
      onCreated(inv.public_id)
      setCustomerId(null)
      setDueAt('')
      setNotes('')
    },
    onError: () => toastError('Erreur lors de la création de la facture.'),
  })

  function handleSubmit() {
    if (!customerId) { setCustomerError(true); return }
    setCustomerError(false)
    mutation.mutate()
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Nouvelle facture</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5} pt={1}>
          <CustomerAutocomplete
            value={customerId}
            onChange={id => { setCustomerId(id); setCustomerError(false) }}
            required
            error={customerError}
            helperText={customerError ? 'Sélectionnez un client' : undefined}
          />
          <TextField
            label="Date d'échéance (optionnel)"
            type="date"
            value={dueAt}
            onChange={e => setDueAt(e.target.value)}
            InputLabelProps={{ shrink: true }}
            fullWidth
          />
          <TextField
            label="Notes (optionnel)"
            multiline
            rows={2}
            value={notes}
            onChange={e => setNotes(e.target.value)}
            fullWidth
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button variant="outlined" onClick={onClose}>Annuler</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={mutation.isPending}>
          Créer la facture
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export function InvoicesPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [page, setPage] = useState(0)
  const [pageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | 'all'>('all')
  const [createOpen, setCreateOpen] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['invoices', { page, pageSize, statusFilter }],
    queryFn: () =>
      invoiceApi.list({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        page: page + 1,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  })

  return (
    <Box>
      <CreateInvoiceDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={publicId => {
          void qc.invalidateQueries({ queryKey: ['invoices'] })
          navigate(`/invoices/${publicId}`)
        }}
      />
      <PageHeader
        title="Factures"
        subtitle="Suivi de la facturation client et des encours"
        actions={
          <Button
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => setCreateOpen(true)}
          >
            Nouvelle facture
          </Button>
        }
      />

      <Stack direction="row" spacing={2} mb={2.5} alignItems="center" flexWrap="wrap">
        <ToggleButtonGroup
          value={statusFilter}
          exclusive
          onChange={(_, v) => { if (v) { setStatusFilter(v); setPage(0) } }}
          size="small"
          sx={{
            '& .MuiToggleButton-root': {
              px: 2,
              fontWeight: 500,
              fontSize: '0.8125rem',
              textTransform: 'none',
            },
          }}
        >
          {STATUS_FILTERS.map(f => (
            <ToggleButton key={f.value} value={f.value}>
              {f.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Stack>

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        getRowKey={r => r.public_id}
        onRowClick={r => navigate(`/invoices/${r.public_id}`)}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger les factures."
        total={data?.total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        emptyTitle="Aucune facture"
        emptyDescription="Créez une facture directement ou convertissez un devis approuvé."
        emptyAction={
          <Button
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => setCreateOpen(true)}
          >
            Nouvelle facture
          </Button>
        }
      />
    </Box>
  )
}
