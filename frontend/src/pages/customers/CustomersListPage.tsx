import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
  InputAdornment,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import AddIcon from '@mui/icons-material/Add'
import { PermissionGate } from '../../components/auth/PermissionGate'
import { customerApi } from '../../lib/customerApi'
import type { CustomerStatus, CustomerSummary } from '../../lib/customerApi'

function formatMoney(minor: number, currency: string | null): string {
  if (!currency) return minor.toString()
  return (minor / 100).toLocaleString('fr-FR', {
    style: 'currency',
    currency,
  })
}

function StatusChip({ status }: { status: CustomerStatus }) {
  const palette: Record<CustomerStatus, 'success' | 'default' | 'error'> = {
    active: 'success',
    inactive: 'default',
    blocked: 'error',
  }
  return <Chip size="small" color={palette[status]} label={status} />
}

export function CustomersListPage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(20)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['customers', { q, page, pageSize }],
    queryFn: () =>
      customerApi.list({
        q: q || undefined,
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
          Clients
        </Typography>
        <PermissionGate permission="customer.create">
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            component={RouterLink}
            to="/customers/new"
          >
            Nouveau client
          </Button>
        </PermissionGate>
      </Stack>

      <Paper sx={{ p: 2, mb: 2 }}>
        <TextField
          placeholder="Rechercher par nom, téléphone, email ou identifiant fiscal..."
          fullWidth
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setPage(0)
          }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Nom</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Téléphone</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Encours</TableCell>
              <TableCell>Statut</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <CircularProgress size={24} />
                </TableCell>
              </TableRow>
            )}
            {isError && (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <Typography color="error">
                    Impossible de charger la liste des clients.
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {data?.items.length === 0 && !isLoading && (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <Typography color="text.secondary">
                    {q ? 'Aucun client trouvé.' : 'Aucun client enregistré.'}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((c: CustomerSummary) => (
              <TableRow
                key={c.id}
                hover
                sx={{ cursor: 'pointer' }}
                onClick={() => navigate(`/customers/${c.id}`)}
              >
                <TableCell>
                  <Typography fontWeight={500}>{c.full_name}</Typography>
                  {c.company_name && (
                    <Typography variant="caption" color="text.secondary">
                      {c.company_name}
                    </Typography>
                  )}
                </TableCell>
                <TableCell>{c.type === 'company' ? 'Société' : 'Particulier'}</TableCell>
                <TableCell>{c.phone_e164 ?? '-'}</TableCell>
                <TableCell>{c.email ?? '-'}</TableCell>
                <TableCell>
                  {formatMoney(c.outstanding_minor, c.credit_currency)}
                </TableCell>
                <TableCell>
                  <StatusChip status={c.status} />
                </TableCell>
                <TableCell align="right">
                  <IconButton
                    component={RouterLink}
                    to={`/customers/${c.id}`}
                    size="small"
                  >
                    <SearchIcon fontSize="small" />
                  </IconButton>
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
            rowsPerPageOptions={[10, 20, 50, 100]}
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
