import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  InputAdornment,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded'
import {
  quotationApi,
  QUOTATION_STATUS_LABELS,
  type QuotationOut,
  type QuotationStatus,
} from '../../lib/quotationApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { CustomerAutocomplete } from '../../components/ui/CustomerAutocomplete'
import { useToast } from '../../contexts/ToastContext'

const STATUS_FILTERS: { value: QuotationStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'Tous' },
  { value: 'draft', label: 'Brouillons' },
  { value: 'sent', label: 'Envoyés' },
  { value: 'approved', label: 'Approuvés' },
  { value: 'rejected', label: 'Refusés' },
]

const columns: Column<QuotationOut>[] = [
  {
    id: 'number',
    label: 'Numéro',
    width: 140,
    render: row => (
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Box
          sx={{
            width: 34,
            height: 34,
            borderRadius: '9px',
            bgcolor: '#F0FDF4',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <DescriptionRoundedIcon sx={{ color: '#16A34A', fontSize: 17 }} />
        </Box>
        <Typography variant="body2" fontWeight={700} fontFamily="monospace">
          {row.doc_number ?? (
            <Typography component="span" variant="caption" color="text.disabled" fontFamily="inherit">
              Brouillon
            </Typography>
          )}
        </Typography>
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
    id: 'lines',
    label: 'Lignes',
    align: 'right',
    width: 80,
    render: row => (
      <Chip
        label={row.lines.length}
        size="small"
        sx={{ bgcolor: '#F1F5F9', color: '#475569', fontWeight: 600, fontSize: '0.75rem' }}
      />
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
    id: 'valid_until',
    label: 'Valide jusqu\'au',
    width: 140,
    render: row => {
      if (!row.valid_until) return <Typography variant="caption" color="text.disabled">—</Typography>
      const expired = new Date(row.valid_until) < new Date()
      return (
        <Typography
          variant="body2"
          color={expired ? 'error.main' : 'text.secondary'}
          fontWeight={expired ? 600 : 400}
        >
          {new Date(row.valid_until).toLocaleDateString('fr-FR')}
        </Typography>
      )
    },
  },
  {
    id: 'status',
    label: 'Statut',
    width: 120,
    render: row => <StatusChip status={row.status} label={QUOTATION_STATUS_LABELS[row.status]} />,
  },
  {
    id: 'date',
    label: 'Créé le',
    width: 110,
    render: row => (
      <Typography variant="caption" color="text.secondary">
        {new Date(row.created_at).toLocaleDateString('fr-FR')}
      </Typography>
    ),
  },
]

function CreateQuotationDialog({ open, onClose, onCreated }: {
  open: boolean
  onClose: () => void
  onCreated: (publicId: string) => void
}) {
  const { error: toastError } = useToast()
  const [customerId, setCustomerId] = useState<number | null>(null)
  const [validUntil, setValidUntil] = useState('')
  const [notes, setNotes] = useState('')
  const [customerError, setCustomerError] = useState(false)

  const mutation = useMutation({
    mutationFn: () =>
      quotationApi.create({
        customer_id: customerId!,
        valid_until: validUntil ? `${validUntil}T00:00:00` : null,
        notes: notes || null,
      }),
    onSuccess: q => {
      onCreated(q.public_id)
      setCustomerId(null)
      setValidUntil('')
      setNotes('')
    },
    onError: () => toastError('Erreur lors de la création du devis.'),
  })

  function handleSubmit() {
    if (!customerId) { setCustomerError(true); return }
    setCustomerError(false)
    mutation.mutate()
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Nouveau devis</DialogTitle>
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
            label="Valide jusqu'au (optionnel)"
            type="date"
            value={validUntil}
            onChange={e => setValidUntil(e.target.value)}
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
          Créer le devis
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export function QuotationsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [page, setPage] = useState(0)
  const [pageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<QuotationStatus | 'all'>('all')
  const [createOpen, setCreateOpen] = useState(false)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['quotations', { page, pageSize, statusFilter }],
    queryFn: () =>
      quotationApi.list({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        page: page + 1,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  })

  return (
    <Box>
      <CreateQuotationDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={publicId => {
          void qc.invalidateQueries({ queryKey: ['quotations'] })
          navigate(`/quotations/${publicId}`)
        }}
      />
      <PageHeader
        title="Devis"
        subtitle="Gérez les estimations et propositions commerciales clients"
        actions={
          <Button
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => setCreateOpen(true)}
          >
            Nouveau devis
          </Button>
        }
      />

      {/* Status filter tabs */}
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
        onRowClick={r => navigate(`/quotations/${r.public_id}`)}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger les devis."
        total={data?.total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        emptyTitle="Aucun devis"
        emptyDescription="Créez votre premier devis pour commencer à facturer."
        emptyAction={
          <Button
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => setCreateOpen(true)}
          >
            Nouveau devis
          </Button>
        }
      />
    </Box>
  )
}
