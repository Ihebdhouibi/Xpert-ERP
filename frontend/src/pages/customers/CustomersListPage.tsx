import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import {
  Box,
  Button,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import BusinessRoundedIcon from '@mui/icons-material/BusinessRounded'
import { PermissionGate } from '../../components/auth/PermissionGate'
import { customerApi } from '../../lib/customerApi'
import type { CustomerSummary } from '../../lib/customerApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { formatMinor } from '../../components/ui/CurrencyDisplay'

const columns: Column<CustomerSummary>[] = [
  {
    id: 'name',
    label: 'Nom',
    sortable: true,
    render: row => (
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Box
          sx={{
            width: 34,
            height: 34,
            borderRadius: '9px',
            bgcolor: row.type === 'company' ? '#EFF6FF' : '#F0FDF4',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {row.type === 'company'
            ? <BusinessRoundedIcon sx={{ color: '#2563EB', fontSize: 16 }} />
            : <PersonRoundedIcon sx={{ color: '#16A34A', fontSize: 16 }} />}
        </Box>
        <Box>
          <Typography variant="body2" fontWeight={600}>{row.full_name}</Typography>
          {row.company_name && (
            <Typography variant="caption" color="text.secondary">{row.company_name}</Typography>
          )}
        </Box>
      </Stack>
    ),
  },
  {
    id: 'type',
    label: 'Type',
    width: 120,
    render: row => (
      <Typography variant="body2" color="text.secondary">
        {row.type === 'company' ? 'Société' : 'Particulier'}
      </Typography>
    ),
  },
  {
    id: 'phone',
    label: 'Téléphone',
    width: 150,
    render: row => (
      <Typography variant="body2" fontFamily="monospace">
        {row.phone_e164 ?? '—'}
      </Typography>
    ),
  },
  {
    id: 'email',
    label: 'Email',
    render: row => (
      <Typography variant="body2" color="text.secondary" noWrap>
        {row.email ?? '—'}
      </Typography>
    ),
  },
  {
    id: 'outstanding',
    label: 'Encours',
    align: 'right',
    width: 130,
    sortable: true,
    render: row => (
      <Typography
        variant="body2"
        fontWeight={600}
        color={row.outstanding_minor > 0 ? 'error.main' : 'text.secondary'}
      >
        {formatMinor(row.outstanding_minor, row.credit_currency ?? 'EUR')}
      </Typography>
    ),
  },
  {
    id: 'status',
    label: 'Statut',
    width: 100,
    sortable: true,
    render: row => <StatusChip status={row.status} />,
  },
]

export function CustomersListPage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [sortBy, setSortBy] = useState<string>('name')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')

  const handleSort = (col: string) => {
    if (col === sortBy) {
      setSortOrder(o => o === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(col)
      setSortOrder('asc')
    }
    setPage(0)
  }

  const { data, isLoading, isError } = useQuery({
    queryKey: ['customers', { q, page, pageSize, sortBy, sortOrder }],
    queryFn: () =>
      customerApi.list({
        q: q || undefined,
        page: page + 1,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  })

  const sortedRows = [...(data?.items ?? [])].sort((a, b) => {
    const dir = sortOrder === 'asc' ? 1 : -1
    if (sortBy === 'name') return dir * a.full_name.localeCompare(b.full_name, 'fr')
    if (sortBy === 'outstanding') return dir * (a.outstanding_minor - b.outstanding_minor)
    if (sortBy === 'status') return dir * a.status.localeCompare(b.status)
    return 0
  })

  return (
    <Box>
      <PageHeader
        title="Clients"
        subtitle={data ? `${data.total} client${data.total !== 1 ? 's' : ''}` : 'Gestion des clients'}
        actions={
          <PermissionGate permission="customer.create">
            <Button
              variant="contained"
              startIcon={<AddRoundedIcon />}
              component={RouterLink}
              to="/customers/new"
            >
              Nouveau client
            </Button>
          </PermissionGate>
        }
      />

      <Box mb={2}>
        <TextField
          placeholder="Rechercher par nom, téléphone, email ou identifiant fiscal…"
          fullWidth
          size="small"
          value={q}
          onChange={e => { setQ(e.target.value); setPage(0) }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchRoundedIcon sx={{ color: 'text.disabled', fontSize: 18 }} />
              </InputAdornment>
            ),
          }}
        />
      </Box>

      <DataTable
        columns={columns}
        rows={sortedRows}
        getRowKey={r => String(r.id)}
        onRowClick={r => navigate(`/customers/${r.id}`)}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger la liste des clients."
        total={data?.total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={size => { setPageSize(size); setPage(0) }}
        sortBy={sortBy}
        sortOrder={sortOrder}
        onSort={handleSort}
        emptyTitle={q ? 'Aucun résultat' : 'Aucun client'}
        emptyDescription={q ? `Aucun client ne correspond à "${q}".` : 'Créez votre premier client pour commencer.'}
      />
    </Box>
  )
}
