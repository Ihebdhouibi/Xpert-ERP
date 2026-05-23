import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import { PermissionGate } from '../../components/auth/PermissionGate'
import {
  repairOrderApi,
  STATUS_LABELS,
  type ROStatus,
  type RepairOrderSummary,
} from '../../lib/repairOrderApi'

const STATUS_COLORS: Record<ROStatus, 'default' | 'info' | 'warning' | 'success' | 'error' | 'primary'> = {
  created: 'default',
  diagnosis: 'info',
  in_repair: 'primary',
  finished: 'warning',
  delivered: 'success',
  paused_parts: 'error',
  paused_approval: 'error',
}

function StatusChip({ status }: { status: ROStatus }) {
  return (
    <Chip
      size="small"
      color={STATUS_COLORS[status]}
      label={STATUS_LABELS[status]}
    />
  )
}

function formatMoney(minor: number | null, currency: string | null): string {
  if (minor === null) return '-'
  if (!currency) return `${minor}`
  return (minor / 100).toLocaleString('fr-FR', { style: 'currency', currency })
}

export function RepairOrdersListPage() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<ROStatus | ''>('')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)

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

  return (
    <Box p={4}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        mb={3}
      >
        <Typography variant="h4" fontWeight={700}>
          Ordres de réparation
        </Typography>
        <PermissionGate permission="repair_order.create">
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            component={RouterLink}
            to="/repair-orders/new"
          >
            Nouvel ordre
          </Button>
        </PermissionGate>
      </Stack>

      <Paper sx={{ p: 2, mb: 2 }}>
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>Statut</InputLabel>
          <Select
            value={statusFilter}
            label="Statut"
            onChange={(e) => {
              setStatusFilter(e.target.value as ROStatus | '')
              setPage(0)
            }}
          >
            <MenuItem value="">Tous les statuts</MenuItem>
            {(Object.keys(STATUS_LABELS) as ROStatus[]).map((s) => (
              <MenuItem key={s} value={s}>
                {STATUS_LABELS[s]}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Description</TableCell>
              <TableCell>Statut</TableCell>
              <TableCell>Priorité</TableCell>
              <TableCell>Coût estimé</TableCell>
              <TableCell>Coût réel</TableCell>
              <TableCell>Date</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <CircularProgress size={24} />
                </TableCell>
              </TableRow>
            )}
            {isError && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography color="error">
                    Impossible de charger les ordres de réparation.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {data?.items.length === 0 && !isLoading && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography color="text.secondary">
                    Aucun ordre de réparation.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((ro: RepairOrderSummary) => (
              <TableRow
                key={ro.id}
                hover
                sx={{ cursor: 'pointer' }}
                onClick={() => navigate(`/repair-orders/${ro.id}`)}
              >
                <TableCell>
                  <Typography fontWeight={500} noWrap sx={{ maxWidth: 300 }}>
                    {ro.description}
                  </Typography>
                </TableCell>
                <TableCell>
                  <StatusChip status={ro.status} />
                </TableCell>
                <TableCell>{ro.priority ?? '-'}</TableCell>
                <TableCell>
                  {formatMoney(ro.estimated_cost_minor, ro.estimated_cost_currency)}
                </TableCell>
                <TableCell>
                  {formatMoney(ro.actual_cost_minor, ro.estimated_cost_currency)}
                </TableCell>
                <TableCell>
                  {new Date(ro.created_at).toLocaleDateString('fr-FR')}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {data && (
          <TablePagination
            component="div"
            count={data.total}
            page={page}
            onPageChange={(_, newPage) => setPage(newPage)}
            rowsPerPage={pageSize}
            rowsPerPageOptions={[10, 20, 50]}
            onRowsPerPageChange={(e) => {
              setPageSize(parseInt(e.target.value, 10))
              setPage(0)
            }}
            labelRowsPerPage="Lignes par page :"
          />
        )}
      </TableContainer>
    </Box>
  )
}
