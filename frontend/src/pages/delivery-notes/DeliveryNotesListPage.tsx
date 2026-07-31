import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import {
  Box,
  Button,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded'
import {
  deliveryNoteApi,
  DELIVERY_NOTE_STATUS_LABELS,
  type DeliveryNoteOut,
  type DeliveryNoteStatus,
} from '../../lib/deliveryNoteApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { SearchField } from '../../components/ui/SearchField'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { PermissionGate } from '../../components/auth/PermissionGate'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'

const STATUS_FILTERS: { value: DeliveryNoteStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'Tous' },
  { value: 'draft', label: 'Brouillons' },
  { value: 'issued', label: 'Émis' },
  { value: 'delivered', label: 'Livrés' },
  { value: 'cancelled', label: 'Annulés' },
]

const columns: Column<DeliveryNoteOut>[] = [
  {
    id: 'doc_number',
    label: 'Référence',
    width: 150,
    sortable: true,
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
          <LocalShippingRoundedIcon sx={{ color: '#2563EB', fontSize: 17 }} />
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
    id: 'created_at',
    label: 'Date',
    width: 120,
    sortable: true,
    render: row => (
      <Typography variant="body2" color="text.secondary">
        {new Date(row.created_at).toLocaleDateString('fr-FR')}
      </Typography>
    ),
  },
  {
    id: 'customer_name',
    label: 'Client',
    sortable: true,
    render: row => (
      <Typography variant="body2" fontWeight={500}>
        {row.customer_name ?? `Client #${row.customer_id}`}
      </Typography>
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
    id: 'status',
    label: 'Statut',
    width: 130,
    sortable: true,
    render: row => <StatusChip status={row.status} label={DELIVERY_NOTE_STATUS_LABELS[row.status]} />,
  },
]

export function DeliveryNotesListPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(0)
  const [pageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<DeliveryNoteStatus | 'all'>('all')
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 300)
  const [sortBy, setSortBy] = useState<string | undefined>(undefined)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

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
    queryKey: ['delivery-notes', { page, pageSize, statusFilter, search: debouncedSearch, sortBy, sortOrder }],
    queryFn: () =>
      deliveryNoteApi.list({
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
      <PageHeader
        title="Bons de livraison"
        breadcrumbs={[{ label: 'Facturation' }, { label: 'Bons de livraison' }]}
        actions={
          <PermissionGate permission="invoice.create">
            <Button
              variant="contained"
              startIcon={<AddRoundedIcon />}
              onClick={() => navigate('/delivery-notes/new')}
            >
              Nouveau BL
            </Button>
          </PermissionGate>
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
        <Box sx={{ minWidth: 260 }}>
          <SearchField
            value={search}
            onChange={v => { setSearch(v); setPage(0) }}
            placeholder="Rechercher par client ou référence…"
          />
        </Box>
      </Stack>

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        getRowKey={r => r.public_id}
        onRowClick={r => navigate(`/delivery-notes/${r.public_id}`)}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger les bons de livraison."
        total={data?.total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        sortBy={sortBy}
        sortOrder={sortOrder}
        onSort={handleSort}
        emptyTitle="Aucun bon de livraison"
        emptyDescription="Créez un bon de livraison directement ou depuis un devis/ordre de réparation."
        emptyAction={
          <PermissionGate permission="invoice.create">
            <Button
              variant="contained"
              startIcon={<AddRoundedIcon />}
              onClick={() => navigate('/delivery-notes/new')}
            >
              Nouveau BL
            </Button>
          </PermissionGate>
        }
      />
    </Box>
  )
}
