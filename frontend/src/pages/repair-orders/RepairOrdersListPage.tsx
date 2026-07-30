import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
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
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import { PermissionGate } from '../../components/auth/PermissionGate'
import {
  repairOrderApi,
  STATUS_LABELS,
  type ROStatus,
  type RepairOrderSummary,
} from '../../lib/repairOrderApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { formatMinor } from '../../components/ui/CurrencyDisplay'

const PRIORITY_COLOR: Record<string, string> = {
  low: '#64748B',
  normal: '#334155',
  high: '#F59E0B',
  urgent: '#EF4444',
}

const PRIORITY_LABEL: Record<string, string> = {
  low: 'Basse',
  normal: 'Normale',
  high: 'Haute',
  urgent: 'Urgente',
}

const columns: Column<RepairOrderSummary>[] = [
  {
    id: 'description',
    label: 'Description',
    render: row => (
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Box
          sx={{
            width: 34,
            height: 34,
            borderRadius: '9px',
            bgcolor: '#F1F5F9',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <BuildRoundedIcon sx={{ color: '#334155', fontSize: 16 }} />
        </Box>
        <Box>
          <Typography variant="body2" fontWeight={600} noWrap sx={{ maxWidth: 320 }}>
            {row.description || '—'}
          </Typography>
          <Typography variant="caption" color="text.secondary" fontFamily="monospace">
            #{String(row.id).slice(-8).toUpperCase()}
          </Typography>
        </Box>
      </Stack>
    ),
  },
  {
    id: 'status',
    label: 'Statut',
    width: 160,
    render: row => <StatusChip status={row.status} label={STATUS_LABELS[row.status]} />,
  },
  {
    id: 'priority',
    label: 'Priorité',
    width: 110,
    sortable: true,
    render: row => row.priority ? (
      <Typography
        variant="caption"
        fontWeight={700}
        sx={{ color: PRIORITY_COLOR[row.priority] ?? 'text.secondary' }}
      >
        {PRIORITY_LABEL[row.priority] ?? row.priority}
      </Typography>
    ) : (
      <Typography variant="caption" color="text.disabled">—</Typography>
    ),
  },
  {
    id: 'estimated',
    label: 'Estimé',
    align: 'right',
    width: 120,
    sortable: true,
    render: row => (
      <Typography variant="body2" color="text.secondary">
        {row.estimated_cost_minor != null
          ? formatMinor(row.estimated_cost_minor, row.estimated_cost_currency ?? 'EUR')
          : '—'}
      </Typography>
    ),
  },
  {
    id: 'actual',
    label: 'Réel',
    align: 'right',
    width: 120,
    render: row => (
      <Typography variant="body2" fontWeight={row.actual_cost_minor != null ? 600 : 400} color="text.primary">
        {row.actual_cost_minor != null
          ? formatMinor(row.actual_cost_minor, row.estimated_cost_currency ?? 'EUR')
          : '—'}
      </Typography>
    ),
  },
  {
    id: 'date',
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

const STATUS_FILTER_OPTIONS: Array<{ value: ROStatus | ''; label: string }> = [
  { value: '', label: 'Tous' },
  { value: 'created', label: 'Créé' },
  { value: 'diagnosis', label: 'Diagnostic' },
  { value: 'in_repair', label: 'En réparation' },
  { value: 'paused_parts', label: 'Attente pièces' },
  { value: 'finished', label: 'Terminé' },
  { value: 'delivered', label: 'Livré' },
]

export function RepairOrdersListPage() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<ROStatus | ''>('')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [sortBy, setSortBy] = useState<string>('date')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

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
    queryKey: ['repair-orders', { statusFilter, page, pageSize }],
    queryFn: () =>
      repairOrderApi.list({
        status: statusFilter || undefined,
        page: page + 1,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  })

  const sortedRows = [...(data?.items ?? [])].sort((a, b) => {
    const dir = sortOrder === 'asc' ? 1 : -1
    if (sortBy === 'date') return dir * (new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    if (sortBy === 'estimated') return dir * ((a.estimated_cost_minor ?? 0) - (b.estimated_cost_minor ?? 0))
    if (sortBy === 'actual') return dir * ((a.actual_cost_minor ?? 0) - (b.actual_cost_minor ?? 0))
    if (sortBy === 'priority') {
      const PRIO: Record<string, number> = { urgent: 4, high: 3, normal: 2, low: 1 }
      return dir * ((PRIO[a.priority ?? 'normal'] ?? 2) - (PRIO[b.priority ?? 'normal'] ?? 2))
    }
    return 0
  })

  return (
    <Box>
      <PageHeader
        title="Ordres de réparation"
        subtitle={data ? `${data.total} ordre${data.total !== 1 ? 's' : ''}` : 'Gestion des réparations'}
        actions={
          <PermissionGate permission="repair_order.create">
            <Button
              variant="contained"
              startIcon={<AddRoundedIcon />}
              component={RouterLink}
              to="/repair-orders/new"
            >
              Nouvel ordre
            </Button>
          </PermissionGate>
        }
      />

      <Box mb={2} sx={{ overflowX: 'auto' }}>
        <ToggleButtonGroup
          value={statusFilter}
          exclusive
          onChange={(_, v) => { if (v !== null || statusFilter !== '') { setStatusFilter(v ?? ''); setPage(0) } }}
          size="small"
          sx={{ flexWrap: 'nowrap' }}
        >
          {STATUS_FILTER_OPTIONS.map(opt => (
            <ToggleButton
              key={opt.value}
              value={opt.value}
              sx={{
                px: 2,
                py: 0.75,
                fontSize: '0.8125rem',
                fontWeight: 600,
                textTransform: 'none',
                whiteSpace: 'nowrap',
                border: '1px solid #E2E8F0 !important',
                borderRadius: '8px !important',
                mr: 0.75,
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  color: 'white',
                  '&:hover': { bgcolor: 'primary.dark' },
                },
              }}
            >
              {opt.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </Box>

      <DataTable
        columns={columns}
        rows={sortedRows}
        getRowKey={r => String(r.id)}
        onRowClick={r => navigate(`/repair-orders/${r.id}`)}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger les ordres de réparation."
        total={data?.total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={size => { setPageSize(size); setPage(0) }}
        sortBy={sortBy}
        sortOrder={sortOrder}
        onSort={handleSort}
        emptyTitle="Aucun ordre de réparation"
        emptyDescription={statusFilter ? 'Aucun ordre avec ce statut.' : 'Créez votre premier ordre de réparation.'}
      />
    </Box>
  )
}
