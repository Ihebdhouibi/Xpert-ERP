import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import {
  Box,
  Button,
  Checkbox,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import LocalShippingRoundedIcon from '@mui/icons-material/LocalShippingRounded'
import ReceiptRoundedIcon from '@mui/icons-material/ReceiptRounded'
import {
  deliveryNoteApi,
  DELIVERY_NOTE_STATUS_LABELS,
  type DeliveryNoteOut,
  type DeliveryNoteStatus,
} from '../../lib/deliveryNoteApi'
import { invoiceApi } from '../../lib/invoiceApi'
import { getPeriodRange, DATE_RANGE_PERIOD_LABELS, type DateRangePeriod } from '../../lib/dateRangePresets'
import { PageHeader } from '../../components/ui/PageHeader'
import { DataTable, type Column } from '../../components/ui/DataTable'
import { StatusChip } from '../../components/ui/StatusChip'
import { SearchField } from '../../components/ui/SearchField'
import { formatMinor } from '../../components/ui/CurrencyDisplay'
import { PermissionGate } from '../../components/auth/PermissionGate'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { useToast } from '../../contexts/ToastContext'

const STATUS_FILTERS: { value: DeliveryNoteStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'Tous' },
  { value: 'draft', label: 'Brouillons' },
  { value: 'issued', label: 'Émis' },
  { value: 'delivered', label: 'Livrés' },
  { value: 'cancelled', label: 'Annulés' },
]

/** A BL can be picked for bulk invoicing once issued/delivered and not already billed. */
function isSelectableForInvoice(row: DeliveryNoteOut): boolean {
  return !row.invoice_id && (row.status === 'issued' || row.status === 'delivered')
}

export function DeliveryNotesListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { success, error: toastError } = useToast()
  const [page, setPage] = useState(0)
  const [pageSize] = useState(20)
  const [statusFilter, setStatusFilter] = useState<DeliveryNoteStatus | 'all'>('all')
  const [period, setPeriod] = useState<DateRangePeriod | 'all'>('all')
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebouncedValue(search, 300)
  const [sortBy, setSortBy] = useState<string | undefined>(undefined)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const range = period === 'all' ? undefined : getPeriodRange(period)

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
    queryKey: ['delivery-notes', { page, pageSize, statusFilter, period, search: debouncedSearch, sortBy, sortOrder }],
    queryFn: () =>
      deliveryNoteApi.list({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        search: debouncedSearch || undefined,
        date_from: range?.date_from,
        date_to: range?.date_to,
        sort_by: sortBy,
        sort_dir: sortOrder,
        page: page + 1,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  })

  // Selection is scoped to what's currently on screen — clear it whenever
  // the page or any filter changes so it can't silently drift out of sync
  // with rows that are no longer visible.
  useEffect(() => {
    setSelectedIds(new Set())
  }, [page, statusFilter, period, debouncedSearch, sortBy, sortOrder])

  const rows = data?.items ?? []
  const selectedRows = rows.filter(r => selectedIds.has(r.public_id))
  // A bulk invoice can only be created for one customer at a time — same
  // constraint as the single-customer "Nouvelle facture" dialog.
  const distinctCustomers = new Set(selectedRows.map(r => r.customer_id))
  const canGenerateInvoice = selectedRows.length > 0 && distinctCustomers.size === 1

  function toggleRow(publicId: string) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(publicId)) next.delete(publicId)
      else next.add(publicId)
      return next
    })
  }

  const selectablePageIds = rows.filter(isSelectableForInvoice).map(r => r.public_id)
  const allPageSelected = selectablePageIds.length > 0 && selectablePageIds.every(id => selectedIds.has(id))

  function toggleSelectAllOnPage() {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (allPageSelected) {
        selectablePageIds.forEach(id => next.delete(id))
      } else {
        selectablePageIds.forEach(id => next.add(id))
      }
      return next
    })
  }

  const generateInvoiceMutation = useMutation({
    mutationFn: () =>
      invoiceApi.fromDeliveryNotes({
        customer_id: selectedRows[0].customer_id,
        delivery_note_ids: selectedRows.map(r => r.public_id),
      }),
    onSuccess: inv => {
      success('Facture créée à partir des bons de livraison sélectionnés')
      setSelectedIds(new Set())
      void queryClient.invalidateQueries({ queryKey: ['delivery-notes'] })
      void queryClient.invalidateQueries({ queryKey: ['invoices'] })
      navigate(`/invoices/${inv.public_id}`)
    },
    onError: () => toastError('Impossible de créer la facture à partir de ces bons de livraison.'),
  })

  const columns: Column<DeliveryNoteOut>[] = useMemo(() => [
    {
      id: 'select',
      label: '',
      width: 48,
      render: row => (
        <Checkbox
          size="small"
          checked={selectedIds.has(row.public_id)}
          disabled={!isSelectableForInvoice(row)}
          onClick={e => e.stopPropagation()}
          onChange={() => toggleRow(row.public_id)}
        />
      ),
    },
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
  ], [selectedIds])

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
        <ToggleButtonGroup
          value={period}
          exclusive
          onChange={(_, v) => { if (v) { setPeriod(v); setPage(0) } }}
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
          <ToggleButton value="all">Toutes dates</ToggleButton>
          {(Object.keys(DATE_RANGE_PERIOD_LABELS) as DateRangePeriod[]).map(p => (
            <ToggleButton key={p} value={p}>{DATE_RANGE_PERIOD_LABELS[p]}</ToggleButton>
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

      <PermissionGate permission="invoice.create">
        <Stack
          direction="row"
          spacing={2}
          alignItems="center"
          mb={selectedIds.size > 0 ? 2 : 0}
          sx={{ minHeight: selectedIds.size > 0 ? 'auto' : 0, overflow: 'hidden' }}
        >
          {selectedIds.size > 0 && (
            <>
              <Button size="small" onClick={toggleSelectAllOnPage}>
                {allPageSelected ? 'Tout désélectionner' : 'Tout sélectionner sur cette page'}
              </Button>
              <Typography variant="body2" color="text.secondary">
                {selectedRows.length} sélectionné{selectedRows.length > 1 ? 's' : ''}
                {distinctCustomers.size > 1 && ' — un seul client à la fois'}
              </Typography>
              <Button
                variant="contained"
                size="small"
                startIcon={<ReceiptRoundedIcon />}
                disabled={!canGenerateInvoice || generateInvoiceMutation.isPending}
                onClick={() => generateInvoiceMutation.mutate()}
              >
                Générer une facture
              </Button>
            </>
          )}
        </Stack>
      </PermissionGate>

      <DataTable
        columns={columns}
        rows={rows}
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
