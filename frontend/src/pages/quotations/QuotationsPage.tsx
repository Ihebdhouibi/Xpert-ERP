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
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
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
import { SearchField } from '../../components/ui/SearchField'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { CustomerAutocomplete } from '../../components/ui/CustomerAutocomplete'
import { useToast } from '../../contexts/ToastContext'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'

const STATUS_FILTERS: { value: QuotationStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'Tous' },
  { value: 'draft', label: 'Brouillons' },
  { value: 'sent', label: 'Envoyés' },
  { value: 'approved', label: 'Approuvés' },
  { value: 'rejected', label: 'Refusés' },
]

const columns: Column<QuotationOut>[] = [
  {
    id: 'doc_number',
    label: 'Numéro',
    width: 140,
    sortable: true,
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
    id: 'customer_name',
    label: 'Client',
    sortable: true,
    render: row => (
      <Typography variant="body2" fontWeight={500}>
        {row.customer_name || `Client #${row.customer_id}`}
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
    id: 'total_minor',
    label: 'Total TTC',
    align: 'right',
    width: 130,
    sortable: true,
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
    sortable: true,
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
    sortable: true,
    render: row => <StatusChip status={row.status} label={QUOTATION_STATUS_LABELS[row.status]} />,
  },
  {
    id: 'created_at',
    label: 'Créé le',
    width: 110,
    sortable: true,
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
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 300)
  const [sortBy, setSortBy] = useState<string | undefined>(undefined)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [createOpen, setCreateOpen] = useState(false)

  const handleSort = (columnId: string) => {
    if (columnId === sortBy) {
      setSortOrder(o => (o === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(columnId)
      setSortOrder('asc')
    }
    setPage(0)
  }

  const { data, isLoading, isError } = useQuery({
    queryKey: ['quotations', { page, pageSize, statusFilter, search: debouncedSearch, sortBy, sortOrder }],
    queryFn: () =>
      quotationApi.list({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        search: debouncedSearch || undefined,
        sort_by: sortBy,
        sort_dir: sortOrder,
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
        <Box sx={{ minWidth: 260 }}>
          <SearchField
            value={search}
            onChange={v => { setSearch(v); setPage(0) }}
            placeholder="Rechercher par client ou numéro…"
          />
        </Box>
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
        sortBy={sortBy}
        sortOrder={sortOrder}
        onSort={handleSort}
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
