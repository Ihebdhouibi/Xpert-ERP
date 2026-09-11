import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import {
  Box,
  Button,
  IconButton,
  InputAdornment,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import UploadFileRoundedIcon from '@mui/icons-material/UploadFileRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import BusinessRoundedIcon from '@mui/icons-material/BusinessRounded'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import ArchiveRoundedIcon from '@mui/icons-material/ArchiveRounded'
import SettingsBackupRestoreRoundedIcon from '@mui/icons-material/SettingsBackupRestoreRounded'
import { PermissionGate } from '../../components/auth/PermissionGate'
import { customerApi } from '../../lib/customerApi'
import type { CustomerSummary } from '../../lib/customerApi'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { ConfirmDialog } from '../../components/ui/ConfirmDialog'
import { SavedViewsBar } from '../../components/ui/SavedViewsBar'
import { CustomerImportDialog } from '../../components/customer/CustomerImportDialog'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { useToast } from '../../contexts/ToastContext'

interface CustomersViewState {
  q: string
  statusFilter: 'active' | 'inactive' | 'blocked' | ''
  sortBy: string
  sortOrder: 'asc' | 'desc'
}

const BASE_COLUMNS: Column<CustomerSummary>[] = [
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
            bgcolor: row.type === 'company' ? '#F1F5F9' : '#F0FDF4',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {row.type === 'company'
            ? <BusinessRoundedIcon sx={{ color: '#334155', fontSize: 16 }} />
            : <PersonRoundedIcon sx={{ color: '#16A34A', fontSize: 16 }} />}
        </Box>
        <Box>
          {row.type === 'company' && row.company_name ? (
            <>
              <Typography variant="body2" fontWeight={600}>{row.company_name}</Typography>
              <Typography variant="caption" color="text.secondary">{row.full_name}</Typography>
            </>
          ) : (
            <Typography variant="body2" fontWeight={600}>{row.full_name}</Typography>
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
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState<'active' | 'inactive' | 'blocked' | ''>('active')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [sortBy, setSortBy] = useState<string>('name')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [toArchive, setToArchive] = useState<CustomerSummary | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())

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
    queryKey: ['customers', { q, page, pageSize, sortBy, sortOrder, statusFilter }],
    queryFn: () =>
      customerApi.list({
        q: q || undefined,
        status: statusFilter || undefined,
        include_deleted: statusFilter === '' || statusFilter === 'inactive',
        page: page + 1,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  })

  const archiveMutation = useMutation({
    mutationFn: (c: CustomerSummary) => customerApi.remove(c.id),
    onSuccess: () => {
      success('Client archivé')
      setToArchive(null)
      queryClient.invalidateQueries({ queryKey: ['customers'] })
    },
    onError: () => toastError("Impossible d'archiver ce client."),
  })

  const restoreMutation = useMutation({
    mutationFn: (c: CustomerSummary) => customerApi.restore(c.id),
    onSuccess: () => {
      success('Client restauré')
      queryClient.invalidateQueries({ queryKey: ['customers'] })
    },
    onError: () => toastError("Impossible de restaurer ce client."),
  })

  const bulkArchiveMutation = useMutation({
    mutationFn: (ids: string[]) => customerApi.bulkArchive(ids),
    onSuccess: result => {
      if (result.skipped.length === 0) {
        success(`${result.archived.length} client${result.archived.length > 1 ? 's' : ''} archivé${result.archived.length > 1 ? 's' : ''}`)
      } else {
        toastError(`${result.archived.length} archivé(s), ${result.skipped.length} ignoré(s) (introuvable(s)).`)
      }
      setSelected(new Set())
      queryClient.invalidateQueries({ queryKey: ['customers'] })
    },
    onError: () => toastError("Impossible d'archiver la sélection."),
  })

  const columns: Column<CustomerSummary>[] = [
    ...BASE_COLUMNS,
    {
      id: 'actions',
      label: '',
      width: 90,
      render: row => (
        <Stack direction="row" spacing={0.25} justifyContent="flex-end" onClick={e => e.stopPropagation()}>
          <PermissionGate permission="customer.update">
            <Tooltip title="Modifier">
              <IconButton size="small" onClick={() => navigate(`/customers/${row.id}/edit`)}>
                <EditRoundedIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </PermissionGate>
          <PermissionGate permission="customer.delete">
            {row.status === 'inactive' ? (
              <Tooltip title="Restaurer">
                <span>
                  <IconButton size="small" color="success"
                    disabled={restoreMutation.isPending}
                    onClick={() => restoreMutation.mutate(row)}>
                    <SettingsBackupRestoreRoundedIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </span>
              </Tooltip>
            ) : (
              <Tooltip title="Archiver">
                <IconButton size="small" color="error" onClick={() => setToArchive(row)}>
                  <ArchiveRoundedIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            )}
          </PermissionGate>
        </Stack>
      ),
    },
  ]

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
            <Stack direction="row" spacing={1.5}>
              <Button
                variant="outlined"
                startIcon={<UploadFileRoundedIcon />}
                onClick={() => setImportOpen(true)}
              >
                Importer Excel
              </Button>
              <Button
                variant="contained"
                startIcon={<AddRoundedIcon />}
                component={RouterLink}
                to="/customers/new"
              >
                Nouveau client
              </Button>
            </Stack>
          </PermissionGate>
        }
      />

      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} mb={2} alignItems="flex-start">
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
        <ToggleButtonGroup
          value={statusFilter}
          exclusive
          onChange={(_e, v) => { if (v !== null) { setStatusFilter(v); setPage(0) } }}
          size="small"
          sx={{ flexShrink: 0 }}
        >
          <ToggleButton value="active" sx={{ textTransform: 'none', px: 2, fontSize: '0.8rem' }}>Actifs</ToggleButton>
          <ToggleButton value="inactive" sx={{ textTransform: 'none', px: 2, fontSize: '0.8rem' }}>Archivés</ToggleButton>
          <ToggleButton value="blocked" sx={{ textTransform: 'none', px: 2, fontSize: '0.8rem' }}>Bloqués</ToggleButton>
          <ToggleButton value="" sx={{ textTransform: 'none', px: 2, fontSize: '0.8rem' }}>Tous</ToggleButton>
        </ToggleButtonGroup>
      </Stack>

      <SavedViewsBar<CustomersViewState>
        storageKey="customers_list"
        currentState={{ q, statusFilter, sortBy, sortOrder }}
        onApply={view => {
          setQ(view.q)
          setStatusFilter(view.statusFilter)
          setSortBy(view.sortBy)
          setSortOrder(view.sortOrder)
          setPage(0)
        }}
      />

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
        selectable
        selected={selected}
        onSelectionChange={setSelected}
        bulkActionsSlot={(selectedIds, clearSelection) => (
          <PermissionGate permission="customer.delete">
            <Button
              size="small"
              color="error"
              variant="outlined"
              startIcon={<ArchiveRoundedIcon />}
              disabled={bulkArchiveMutation.isPending}
              onClick={() => bulkArchiveMutation.mutate(Array.from(selectedIds))}
              sx={{ textTransform: 'none', bgcolor: 'background.paper' }}
            >
              Archiver la sélection
            </Button>
            <Button size="small" onClick={clearSelection} sx={{ textTransform: 'none' }}>
              Annuler
            </Button>
          </PermissionGate>
        )}
      />

      <ConfirmDialog
        open={toArchive !== null}
        title="Archiver ce client ?"
        message={`"${toArchive?.full_name}" sera archivé et n'apparaîtra plus dans la liste active. Il pourra être restauré à tout moment.`}
        confirmLabel="Archiver"
        dangerous
        loading={archiveMutation.isPending}
        onConfirm={() => toArchive && archiveMutation.mutate(toArchive)}
        onCancel={() => setToArchive(null)}
      />

      <CustomerImportDialog open={importOpen} onClose={() => setImportOpen(false)} />
    </Box>
  )
}
