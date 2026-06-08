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
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import { invoiceApi, INVOICE_STATUS_LABELS, type InvoiceOut, type InvoiceStatus } from '../../lib/invoiceApi'
import { customerApi } from '../../lib/customerApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
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
    render: row =>
      row.customer_name ? (
        <Typography variant="body2" fontWeight={500}>
          {row.customer_name}
        </Typography>
      ) : row.status === 'draft' ? (
        <Button
          size="small"
          variant="outlined"
          onClick={(e) => {
            e.stopPropagation()
            onAssign(row)
          }}
        >
          Assigner un client
        </Button>
      ) : (
        <Typography variant="body2" color="text.disabled">
          Sans client
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

export function InvoicesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const [page, setPage] = useState(0)
  const [pageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | 'all'>('all')
  const [assignTarget, setAssignTarget] = useState<InvoiceOut | null>(null)
  const [assignCustomerId, setAssignCustomerId] = useState<number | ''>('')

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
    queryFn: () => customerApi.list({ page_size: 200 }),
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

  return (
    <Box>
      <PageHeader
        title="Factures"
        subtitle="Suivi de la facturation client et des encours"
        actions={
          <Button
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => navigate('/invoices/new')}
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
        columns={buildColumns(setAssignTarget)}
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
            onClick={() => navigate('/invoices/new')}
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
    </Box>
  )
}
