import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet'
import BuildIcon from '@mui/icons-material/Build'
import AccessTimeIcon from '@mui/icons-material/AccessTime'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import PeopleIcon from '@mui/icons-material/People'
import LocalShippingIcon from '@mui/icons-material/LocalShipping'
import RepeatIcon from '@mui/icons-material/Repeat'
import DescriptionIcon from '@mui/icons-material/Description'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { kpiApi, TopCustomerEntry, TopSupplierEntry } from '../../lib/kpiApi'

const TREND_KPIS = [
  { code: 'revenue_mtd', label: 'Chiffre d\'affaires (mois)' },
  { code: 'revenue_ytd', label: 'Chiffre d\'affaires (année)' },
  { code: 'margin_avg_pct', label: 'Marge moyenne (%)' },
  { code: 'workshop_occupancy_pct', label: 'Taux d\'occupation (%)' },
  { code: 'avg_repair_duration_h', label: 'Durée réparation moy. (h)' },
  { code: 'avg_immobilization_h', label: 'Immobilisation moy. (h)' },
  { code: 'outstanding_amount_minor', label: 'Encours clients (€)' },
  { code: 'comeback_rate_pct', label: 'Taux de retour (%)' },
  { code: 'quotation_conversion_rate_pct', label: 'Taux conversion devis (%)' },
]

function fromDate(daysBack: number): string {
  const d = new Date()
  d.setDate(d.getDate() - daysBack)
  return d.toISOString().slice(0, 10)
}

function toDate(): string {
  return new Date().toISOString().slice(0, 10)
}

function formatMinor(v: number | null | undefined): string {
  if (v == null) return '—'
  return (v / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

function formatPct(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v.toFixed(1)} %`
}

function formatHours(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v.toFixed(1)} h`
}

function formatCount(v: number | null | undefined): string {
  if (v == null) return '—'
  return String(Math.round(v))
}

interface KpiCardProps {
  label: string
  value: string
  icon: React.ReactNode
  color?: string
}

function KpiCard({ label, value, icon, color = 'primary.main' }: KpiCardProps) {
  return (
    <Card sx={{ minWidth: 200, flex: '1 1 200px' }}>
      <CardContent>
        <Stack direction="row" alignItems="center" spacing={1.5} mb={1}>
          <Box sx={{ color }}>{icon}</Box>
          <Typography variant="body2" color="text.secondary" flex={1}>
            {label}
          </Typography>
        </Stack>
        <Typography variant="h5" fontWeight={700} color={color}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  )
}

export function KpiDashboardPage() {
  const [trendKpi, setTrendKpi] = useState('revenue_mtd')

  const {
    data: live,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['kpi', 'live'],
    queryFn: kpiApi.getLive,
    refetchInterval: (data) =>
      data ? (data.refresh_interval_seconds ?? 300) * 1000 : 300_000,
    staleTime: 0,
  })

  const {
    data: trend,
    isLoading: trendLoading,
  } = useQuery({
    queryKey: ['kpi', 'trend', trendKpi],
    queryFn: () => kpiApi.getTrend(trendKpi, fromDate(29), toDate()),
    enabled: !!live,
    staleTime: 60_000,
  })

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" mt={8}>
        <CircularProgress />
      </Box>
    )
  }

  if (error || !live) {
    return (
      <Box p={4}>
        <Alert severity="error">Impossible de charger les KPIs.</Alert>
      </Box>
    )
  }

  const k = live.kpis
  const topCustomers = (k.top_customers?.meta ?? []) as TopCustomerEntry[]
  const topSuppliers = (k.top_suppliers?.meta ?? []) as TopSupplierEntry[]

  const trendLabel = TREND_KPIS.find(t => t.code === trendKpi)?.label ?? trendKpi
  const trendPoints = (trend?.points ?? []).map(p => ({
    date: p.snapshot_date,
    value: p.value != null ? Number(p.value) : null,
  }))

  const isMoneyKpi = trendKpi.includes('revenue') || trendKpi.includes('amount')

  return (
    <Box p={4}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Tableau de bord KPI
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Actualisé toutes les {Math.round(live.refresh_interval_seconds / 60)} min —{' '}
            {new Date(live.computed_at).toLocaleTimeString('fr-FR')}
          </Typography>
        </Box>
      </Stack>

      {/* --- Scalar KPI cards --- */}
      <Stack direction="row" flexWrap="wrap" gap={2} mb={4}>
        <KpiCard
          label="CA mois en cours"
          value={formatMinor(k.revenue_mtd?.value)}
          icon={<TrendingUpIcon />}
        />
        <KpiCard
          label="CA année en cours"
          value={formatMinor(k.revenue_ytd?.value)}
          icon={<TrendingUpIcon />}
          color="success.main"
        />
        <KpiCard
          label="Marge moyenne"
          value={formatPct(k.margin_avg_pct?.value)}
          icon={<AccountBalanceWalletIcon />}
          color="success.main"
        />
        <KpiCard
          label="Taux d'occupation atelier"
          value={formatPct(k.workshop_occupancy_pct?.value)}
          icon={<BuildIcon />}
          color="warning.main"
        />
        <KpiCard
          label="Durée réparation moy."
          value={formatHours(k.avg_repair_duration_h?.value)}
          icon={<AccessTimeIcon />}
        />
        <KpiCard
          label="Immobilisation moy."
          value={formatHours(k.avg_immobilization_h?.value)}
          icon={<AccessTimeIcon />}
          color="warning.main"
        />
        <KpiCard
          label="Factures impayées"
          value={formatCount(k.unpaid_invoices_count?.value)}
          icon={<WarningAmberIcon />}
          color="error.main"
        />
        <KpiCard
          label="Encours total"
          value={formatMinor(k.outstanding_amount_minor?.value)}
          icon={<AccountBalanceWalletIcon />}
          color="error.main"
        />
        <KpiCard
          label="Taux de retour"
          value={formatPct(k.comeback_rate_pct?.value)}
          icon={<RepeatIcon />}
          color={
            (k.comeback_rate_pct?.value ?? 0) > 10 ? 'error.main' : 'success.main'
          }
        />
        <KpiCard
          label="Conversion devis"
          value={formatPct(k.quotation_conversion_rate_pct?.value)}
          icon={<DescriptionIcon />}
          color="success.main"
        />
      </Stack>

      {/* --- Trend chart --- */}
      <Card sx={{ mb: 4 }}>
        <CardContent>
          <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
            <Typography variant="h6" fontWeight={600}>
              Évolution — {trendLabel}
            </Typography>
            <FormControl size="small" sx={{ minWidth: 280 }}>
              <InputLabel>Indicateur</InputLabel>
              <Select
                value={trendKpi}
                label="Indicateur"
                onChange={e => setTrendKpi(e.target.value)}
              >
                {TREND_KPIS.map(t => (
                  <MenuItem key={t.code} value={t.code}>
                    {t.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>

          {trendLoading ? (
            <Box display="flex" justifyContent="center" py={4}>
              <CircularProgress size={32} />
            </Box>
          ) : trendPoints.length === 0 ? (
            <Alert severity="info">Aucune donnée de tendance disponible pour cet indicateur.</Alert>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={trendPoints} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickFormatter={v =>
                    isMoneyKpi
                      ? `${(v / 100).toLocaleString('fr-FR')} €`
                      : String(v)
                  }
                />
                <Tooltip
                  formatter={(v: number) =>
                    isMoneyKpi
                      ? [(v / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' }), trendLabel]
                      : [v, trendLabel]
                  }
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#1976d2"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* --- Top customers / suppliers --- */}
      <Stack direction="row" gap={3} flexWrap="wrap">
        <Card sx={{ flex: '1 1 300px', minWidth: 300 }}>
          <CardContent>
            <Stack direction="row" alignItems="center" spacing={1} mb={2}>
              <PeopleIcon color="primary" />
              <Typography variant="h6" fontWeight={600}>
                Top 10 clients
              </Typography>
            </Stack>
            <Divider sx={{ mb: 1 }} />
            {topCustomers.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                Aucune donnée
              </Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>#</TableCell>
                    <TableCell>Client</TableCell>
                    <TableCell align="right">CA</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {topCustomers.map(c => (
                    <TableRow key={c.customer_id}>
                      <TableCell>{c.rank}</TableCell>
                      <TableCell>{c.name}</TableCell>
                      <TableCell align="right">
                        {formatMinor(c.revenue_minor)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card sx={{ flex: '1 1 300px', minWidth: 300 }}>
          <CardContent>
            <Stack direction="row" alignItems="center" spacing={1} mb={2}>
              <LocalShippingIcon color="primary" />
              <Typography variant="h6" fontWeight={600}>
                Top 10 fournisseurs
              </Typography>
            </Stack>
            <Divider sx={{ mb: 1 }} />
            {topSuppliers.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                Aucune donnée
              </Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>#</TableCell>
                    <TableCell>Fournisseur</TableCell>
                    <TableCell align="right">Achats</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {topSuppliers.map(s => (
                    <TableRow key={s.supplier_id}>
                      <TableCell>{s.rank}</TableCell>
                      <TableCell>{s.name}</TableCell>
                      <TableCell align="right">
                        {formatMinor(s.spend_minor)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </Stack>
    </Box>
  )
}
