import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import {
  Box,
  Button,
  Chip,
  InputAdornment,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import DirectionsCarRoundedIcon from '@mui/icons-material/DirectionsCarRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import { vehiclesApi, FUEL_TYPE_LABELS, type VehicleOut, type VehicleStatus } from '../../lib/vehiclesApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { EmptyState } from '../../components/ui/EmptyState'

function isOverdue(dateStr: string | null): boolean {
  if (!dateStr) return false
  return new Date(dateStr) < new Date()
}

function isDueSoon(dateStr: string | null, daysAhead = 30): boolean {
  if (!dateStr) return false
  const due = new Date(dateStr)
  const soon = new Date()
  soon.setDate(soon.getDate() + daysAhead)
  return due <= soon && due >= new Date()
}

function DateBadge({ label, date }: { label: string; date: string | null }) {
  if (!date) return <Typography variant="caption" color="text.disabled">—</Typography>
  const overdue = isOverdue(date)
  const soon = !overdue && isDueSoon(date)
  const formatted = new Date(date).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
  return (
    <Tooltip title={`${label} : ${formatted}`}>
      <Chip
        size="small"
        label={formatted}
        icon={overdue || soon ? <WarningAmberRoundedIcon /> : undefined}
        color={overdue ? 'error' : soon ? 'warning' : 'default'}
        sx={{ fontWeight: 500, fontSize: '0.7rem' }}
      />
    </Tooltip>
  )
}

const columns: Column<VehicleOut>[] = [
  {
    id: 'registration',
    label: 'Immatriculation',
    width: 150,
    render: row => (
      <Stack direction="row" alignItems="center" spacing={1.5}>
        <Box
          sx={{
            width: 36,
            height: 36,
            borderRadius: '10px',
            bgcolor: '#EFF6FF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <DirectionsCarRoundedIcon sx={{ color: '#2563EB', fontSize: 18 }} />
        </Box>
        <Box>
          <Typography variant="body2" fontWeight={700} fontFamily="monospace" letterSpacing="0.05em">
            {row.registration ?? <span style={{ color: '#94A3B8' }}>—</span>}
          </Typography>
          {row.vin && (
            <Typography variant="caption" color="text.disabled" fontFamily="monospace">
              {row.vin}
            </Typography>
          )}
        </Box>
      </Stack>
    ),
  },
  {
    id: 'vehicle',
    label: 'Véhicule',
    render: row => (
      <Box>
        <Typography variant="body2" fontWeight={500}>
          {row.make} {row.model}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {row.year ?? '—'} · {row.fuel_type ? FUEL_TYPE_LABELS[row.fuel_type] : '—'}
          {row.color ? ` · ${row.color}` : ''}
        </Typography>
      </Box>
    ),
  },
  {
    id: 'mileage',
    label: 'Kilométrage',
    align: 'right',
    width: 130,
    render: row =>
      row.mileage_current != null ? (
        <Typography variant="body2" fontWeight={500}>
          {row.mileage_current.toLocaleString('fr-FR')} km
        </Typography>
      ) : (
        <Typography variant="caption" color="text.disabled">—</Typography>
      ),
  },
  {
    id: 'ct',
    label: 'Contrôle technique',
    width: 160,
    render: row => <DateBadge label="CT" date={row.technical_inspection_due_at} />,
  },
  {
    id: 'maintenance',
    label: 'Entretien',
    width: 140,
    render: row => <DateBadge label="Entretien" date={row.maintenance_due_at} />,
  },
  {
    id: 'status',
    label: 'Statut',
    width: 100,
    render: row => <StatusChip status={row.status} />,
  },
]

export function VehiclesPage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [pageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<VehicleStatus | 'all'>('all')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['vehicles', { q, page, pageSize, statusFilter }],
    queryFn: () =>
      vehiclesApi.list({
        q: q || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        page: page + 1,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  })

  return (
    <Box>
      <PageHeader
        title="Véhicules"
        subtitle="Gérez le parc véhicules et leur historique d'interventions"
        actions={
          <Button
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => navigate('/vehicles/new')}
          >
            Nouveau véhicule
          </Button>
        }
      />

      {/* Filters */}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} mb={2.5} alignItems="flex-start">
        <TextField
          placeholder="Rechercher par immatriculation, VIN, marque ou modèle…"
          value={q}
          onChange={e => { setQ(e.target.value); setPage(0) }}
          sx={{ flex: 1, maxWidth: 480 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchRoundedIcon sx={{ color: 'text.disabled', fontSize: 18 }} />
              </InputAdornment>
            ),
          }}
        />
        <ToggleButtonGroup
          value={statusFilter}
          exclusive
          onChange={(_, v) => { if (v) { setStatusFilter(v); setPage(0) } }}
          size="small"
          sx={{ '& .MuiToggleButton-root': { px: 2, fontWeight: 500, fontSize: '0.8125rem', textTransform: 'none' } }}
        >
          <ToggleButton value="all">Tous</ToggleButton>
          <ToggleButton value="active">Actifs</ToggleButton>
          <ToggleButton value="inactive">Inactifs</ToggleButton>
          <ToggleButton value="scrapped">Épaves</ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        getRowKey={r => String(r.id)}
        onRowClick={r => navigate(`/vehicles/${r.id}`)}
        loading={isLoading}
        error={isError}
        errorMessage="Impossible de charger la liste des véhicules."
        total={data?.total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        emptyTitle="Aucun véhicule"
        emptyDescription={
          q
            ? `Aucun véhicule ne correspond à "${q}".`
            : 'Commencez par enregistrer un véhicule client.'
        }
        emptyAction={
          !q ? (
            <Button
              variant="contained"
              startIcon={<AddRoundedIcon />}
              onClick={() => navigate('/vehicles/new')}
            >
              Nouveau véhicule
            </Button>
          ) : undefined
        }
      />
    </Box>
  )
}
