import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import {
  Autocomplete,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import DeleteRoundedIcon from '@mui/icons-material/DeleteRounded'
import PersonAddRoundedIcon from '@mui/icons-material/PersonAddRounded'
import { invoiceApi, INVOICE_STATUS_LABELS, type InvoiceOut, type InvoiceStatus } from '../../lib/invoiceApi'
import { customerApi } from '../../lib/customerApi'
import { deliveryNoteApi, type DeliveryNoteOut } from '../../lib/deliveryNoteApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
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

const buildColumns = (
  onAssign: (inv: InvoiceOut) => void,
  onDelete: (inv: InvoiceOut) => void,
): Column<InvoiceOut>[] => [
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
        {row.customer_name ?? `Client #${row.customer_id}`}
      </Typography>
    ),
  },
  {
    id: 'actions',
    label: '',
    align: 'right',
    width: 96,
    render: row =>
      row.status === 'draft' ? (
        <Stack direction="row" spacing={0.5} alignItems="center" justifyContent="flex-end">
          {!row.customer_name && (
            <Tooltip title="Assigner un client">
              <IconButton
                size="small"
                color="primary"
                onClick={(e) => {
                  e.stopPropagation()
                  onAssign(row)
                }}
              >
                <PersonAddRoundedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title="Supprimer la facture">
            <IconButton
              size="small"
              color="error"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(row)
              }}
            >
              <DeleteRoundedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Stack>
      ) : null,
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
  const [selectedBls, setSelectedBls] = useState<DeliveryNoteOut[]>([])

  const { data: blsData, isLoading: blsLoading } = useQuery({
    queryKey: ['delivery-notes', 'available-for-invoice', customerId],
    queryFn: () => deliveryNoteApi.listAvailableForInvoice(customerId!),
    enabled: !!customerId,
  })

  const availableBls = blsData?.items ?? []

  const mutation = useMutation({
    mutationFn: () => {
      if (selectedBls.length > 0) {
        return invoiceApi.fromDeliveryNotes({
          customer_id: customerId!,
          delivery_note_ids: selectedBls.map(bl => bl.public_id),
          due_at: dueAt ? `${dueAt}T00:00:00` : null,
          notes: notes || null,
        })
      }
      return invoiceApi.create({
        customer_id: customerId!,
        due_at: dueAt ? `${dueAt}T00:00:00` : null,
        notes: notes || null,
      })
    },
    onSuccess: inv => {
      onCreated(inv.public_id)
      setCustomerId(null)
      setDueAt('')
      setNotes('')
      setSelectedBls([])
    },
    onError: () => toastError('Erreur lors de la création de la facture.'),
  })

  function handleCustomerChange(id: number | null) {
    setCustomerId(id)
    setCustomerError(false)
    setSelectedBls([])
  }

  function handleSubmit() {
    if (!customerId) { setCustomerError(true); return }
    setCustomerError(false)
    mutation.mutate()
  }

  function handleClose() {
    setCustomerId(null)
    setDueAt('')
    setNotes('')
    setSelectedBls([])
    setCustomerError(false)
    onClose()
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Nouvelle facture</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5} pt={1}>
          <CustomerAutocomplete
            value={customerId}
            onChange={handleCustomerChange}
            required
            error={customerError}
            helperText={customerError ? 'Sélectionnez un client' : undefined}
          />
          {customerId && (
            <Autocomplete
              multiple
              options={availableBls}
              loading={blsLoading}
              value={selectedBls}
              onChange={(_, newValue) => setSelectedBls(newValue)}
              getOptionLabel={bl =>
                `${bl.doc_number ?? 'Sans numéro'} — ${bl.issued_at ? new Date(bl.issued_at).toLocaleDateString('fr-FR') : ''} — ${formatMinor(bl.total_minor, bl.currency)}`
              }
              isOptionEqualToValue={(a, b) => a.public_id === b.public_id}
              renderInput={params => (
                <TextField
                  {...params}
                  label="Bons de livraison (optionnel)"
                  placeholder={!blsLoading && availableBls.length === 0 ? 'Aucun BL disponible' : 'Sélectionner...'}
                />
              )}
              noOptionsText="Aucun bon de livraison disponible"
              loadingText="Chargement..."
            />
          )}
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
        <Button variant="outlined" onClick={handleClose}>Annuler</Button>
        <Button variant="contained" onClick={handleSubmit} disabled={mutation.isPending}>
          Créer la facture
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export function InvoicesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const qc = queryClient
  const { success, error: toastError } = useToast()
  const [page, setPage] = useState(0)
  const [pageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | 'all'>('all')
  const [assignTarget, setAssignTarget] = useState<InvoiceOut | null>(null)
  const [assignCustomerId, setAssignCustomerId] = useState<number | ''>('')
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

  const { data: customersData } = useQuery({
    queryKey: ['customers', 'for-invoice-assign'],
    queryFn: () => customerApi.list({ page_size: 100 }),
    enabled: assignTarget !== null,
  })

  const assignMutation = useMutation({
    mutationFn: () =>
      invoiceApi.update(assignTarget!.public_id, assignTarget!.version, {
        customer_id: assignCustomerId as number,
      }),
    onSuccess: () => {
      success('Client assigné')
      setAssignTarget(null)
      setAssignCustomerId('')
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
    onError: () => toastError("Impossible d'assigner le client."),
  })

  const [deleteTarget, setDeleteTarget] = useState<InvoiceOut | null>(null)
  const deleteMutation = useMutation({
    mutationFn: () => invoiceApi.remove(deleteTarget!.public_id),
    onSuccess: () => {
      success('Facture supprimée')
      setDeleteTarget(null)
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
    onError: () => {
      toastError('Impossible de supprimer la facture.')
      setDeleteTarget(null)
    },
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
        columns={buildColumns(setAssignTarget, setDeleteTarget)}
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

      <Dialog
        open={assignTarget !== null}
        onClose={() => setAssignTarget(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Assigner un client</DialogTitle>
        <DialogContent>
          <FormControl fullWidth size="small" sx={{ mt: 1 }}>
            <InputLabel>Client</InputLabel>
            <Select
              label="Client"
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
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAssignTarget(null)}>Annuler</Button>
          <Button
            variant="contained"
            disabled={assignCustomerId === '' || assignMutation.isPending}
            onClick={() => assignMutation.mutate()}
          >
            Assigner
          </Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Supprimer la facture"
        message={`Supprimer la facture ${deleteTarget?.doc_number ?? 'brouillon'} ? Cette action est irréversible.`}
        confirmLabel="Supprimer"
        dangerous
        loading={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate()}
        onCancel={() => setDeleteTarget(null)}
      />
    </Box>
  )
}
