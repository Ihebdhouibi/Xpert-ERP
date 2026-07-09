import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  InputAdornment,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import { supplierInvoiceApi, SupplierInvoice, STATUS_LABELS, SIStatus } from '../../lib/supplierInvoiceApi'

function formatMoney(minor: number) {
  return `${(minor / 100).toFixed(2)} €`
}

const STATUS_COLORS: Record<SIStatus, 'default' | 'warning' | 'info' | 'success' | 'error'> = {
  draft: 'default',
  posted: 'warning',
  approved: 'info',
  paid: 'success',
  cancelled: 'error',
}

export function ServicesExternesPage() {
  const navigate = useNavigate()
  const [invoices, setInvoices] = useState<SupplierInvoice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')

  const fetchData = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await supplierInvoiceApi.list({
        invoice_type: 'services',
        search: search || undefined,
        page_size: 100,
      })
      setInvoices(res.items)
    } catch {
      setError('Impossible de charger les services externes.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [search]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(searchInput)
  }

  const totalPaid = invoices
    .filter((i) => i.status === 'paid')
    .reduce((s, i) => s + i.total_ttc, 0)

  return (
    <Box p={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
        <Box>
          <Typography variant="h5">Services externes</Typography>
          <Typography variant="body2" color="text.secondary">
            Factures de service fournisseur (hors bon de commande) — {invoices.length} facture{invoices.length !== 1 ? 's' : ''}
            {totalPaid > 0 && ` · ${formatMoney(totalPaid)} payés`}
          </Typography>
        </Box>
      </Stack>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Box component="form" onSubmit={handleSearch}>
          <TextField
            fullWidth
            size="small"
            placeholder="Rechercher par N° de facture…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton type="submit" size="small"><SearchIcon /></IconButton>
                </InputAdornment>
              ),
            }}
          />
        </Box>
      </Paper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {loading ? (
        <Box display="flex" justifyContent="center" py={6}><CircularProgress /></Box>
      ) : (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>N° facture</TableCell>
                <TableCell>Fournisseur</TableCell>
                <TableCell>Services</TableCell>
                <TableCell align="right">Total HT</TableCell>
                <TableCell align="right">Total TTC</TableCell>
                <TableCell>Date</TableCell>
                <TableCell>Échéance</TableCell>
                <TableCell>Statut</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {invoices.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} align="center">
                    Aucune facture de service trouvée.{' '}
                    <Button size="small" onClick={() => navigate('/documents')}>
                      Télécharger une facture service
                    </Button>
                  </TableCell>
                </TableRow>
              )}
              {invoices.map((inv) => {
                const services = (inv.lines ?? []).filter((l) => l.description)
                return (
                  <TableRow
                    key={inv.id}
                    hover
                    sx={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/supplier-invoices/${inv.id}`)}
                  >
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>
                        {inv.number}
                      </Typography>
                    </TableCell>
                    <TableCell>{inv.supplier_name ?? '—'}</TableCell>
                    <TableCell sx={{ maxWidth: 300 }}>
                      {services.length > 0 ? (
                        <Tooltip title={services.map((s) => s.description).join(' · ')}>
                          <Typography variant="body2" noWrap>
                            {services.map((s) => s.description).join(' · ')}
                          </Typography>
                        </Tooltip>
                      ) : (
                        <Typography variant="body2" color="text.secondary">—</Typography>
                      )}
                    </TableCell>
                    <TableCell align="right">{formatMoney(inv.total_ht)}</TableCell>
                    <TableCell align="right">{formatMoney(inv.total_ttc)}</TableCell>
                    <TableCell>
                      {inv.received_at
                        ? new Date(inv.received_at).toLocaleDateString('fr-FR')
                        : inv.created_at
                        ? new Date(inv.created_at).toLocaleDateString('fr-FR')
                        : '—'}
                    </TableCell>
                    <TableCell>
                      {inv.due_date
                        ? new Date(inv.due_date).toLocaleDateString('fr-FR')
                        : '—'}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={STATUS_LABELS[inv.status as SIStatus] ?? inv.status}
                        size="small"
                        color={STATUS_COLORS[inv.status as SIStatus] ?? 'default'}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Ouvrir la facture">
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation()
                            navigate(`/supplier-invoices/${inv.id}`)
                          }}
                        >
                          <OpenInNewIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  )
}
