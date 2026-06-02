import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Box,
  Button,
  ButtonGroup,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
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
import InventoryIcon from '@mui/icons-material/Inventory'
import DownloadIcon from '@mui/icons-material/Download'
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { kpiApi, TopCustomerEntry, TopSupplierEntry, ExportTable } from '../../lib/kpiApi'
import { useAuth } from '../../contexts/AuthContext'
import { PageHeader } from '../../components/ui/PageHeader'

// ---------------------------------------------------------------------------
// Period helpers
// ---------------------------------------------------------------------------

type Period = 'today' | 'week' | 'month' | 'quarter' | 'year' | 'custom'

function todayStr(): string {
  return new Date().toISOString().slice(0, 10)
}

function periodDates(period: Period, custom: { from: string; to: string }): { from: string; to: string } {
  const now = new Date()
  const to = todayStr()
  if (period === 'today') return { from: to, to }
  if (period === 'week') {
    const d = new Date(now)
    const day = d.getDay() === 0 ? 6 : d.getDay() - 1 // Monday = 0
    d.setDate(d.getDate() - day)
    return { from: d.toISOString().slice(0, 10), to }
  }
  if (period === 'month') {
    return { from: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`, to }
  }
  if (period === 'quarter') {
    const q = Math.floor(now.getMonth() / 3)
    const fromMonth = String(q * 3 + 1).padStart(2, '0')
    return { from: `${now.getFullYear()}-${fromMonth}-01`, to }
  }
  if (period === 'year') {
    return { from: `${now.getFullYear()}-01-01`, to }
  }
  return custom
}

const PERIOD_LABELS: Record<Period, string> = {
  today: "Aujourd'hui",
  week: 'Cette semaine',
  month: 'Ce mois',
  quarter: 'Ce trimestre',
  year: 'Cette année',
  custom: 'Personnalisé',
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function fmtMinor(v: number | null | undefined): string {
  if (v == null) return '—'
  return (v / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v.toFixed(1)} %`
}

function fmtHours(v: number | null | undefined): string {
  if (v == null) return '—'
  return `${v.toFixed(1)} h`
}

function fmtCount(v: number | null | undefined): string {
  if (v == null) return '—'
  return String(Math.round(v))
}

// ---------------------------------------------------------------------------
// KPI card
// ---------------------------------------------------------------------------

interface KpiCardProps {
  label: string
  value: string
  icon: React.ReactNode
  color?: string
}

function KpiCard({ label, value, icon, color = 'primary.main' }: KpiCardProps) {
  return (
    <Card sx={{ minWidth: 180, flex: '1 1 180px', borderRadius: 2 }}>
      <CardContent sx={{ p: 2.5 }}>
        <Typography variant="caption" color="text.secondary" fontWeight={500} display="block" mb={1.5}>
          {label}
        </Typography>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="h5" fontWeight={700} color="text.primary" lineHeight={1}>
            {value}
          </Typography>
          <Box
            sx={{
              width: 36, height: 36,
              borderRadius: '9px',
              bgcolor: `${color === 'error.main' ? '#FEF2F2' : color === 'success.main' ? '#F0FDF4' : color === 'warning.main' ? '#FFFBEB' : '#EFF6FF'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color,
            }}
          >
            {icon}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  )
}

// Shared custom tooltip style — consistent with design system
function ChartTooltip({ active, payload, label, formatter }: {
  active?: boolean
  payload?: Array<{ value: number; name?: string }>
  label?: string
  formatter?: (v: number) => string
}) {
  if (!active || !payload?.length) return null
  return (
    <Box
      sx={{
        bgcolor: '#1E293B',
        borderRadius: 1.5,
        px: 1.5, py: 1,
        boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
      }}
    >
      {label && (
        <Box sx={{ color: '#94A3B8', fontSize: '0.6875rem', mb: 0.375 }}>{label}</Box>
      )}
      {payload.map((p, i) => (
        <Box key={i} sx={{ color: 'white', fontSize: '0.8125rem', fontWeight: 600 }}>
          {formatter ? formatter(p.value) : p.value}
        </Box>
      ))}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Chart card wrapper
// ---------------------------------------------------------------------------

function ChartCard({ title, loading, empty, children }: {
  title: string
  loading?: boolean
  empty?: boolean
  children: React.ReactNode
}) {
  return (
    <Card sx={{ flex: '1 1 400px', minWidth: 320 }}>
      <CardContent>
        <Typography variant="h6" fontWeight={600} mb={2}>{title}</Typography>
        {loading ? (
          <Box display="flex" justifyContent="center" py={4}><CircularProgress size={32} /></Box>
        ) : empty ? (
          <Alert severity="info">Aucune donnée pour cette période.</Alert>
        ) : children}
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Export button
// ---------------------------------------------------------------------------

function ExportButtons({ table, canExport }: { table: ExportTable; canExport: boolean }) {
  const [loading, setLoading] = useState(false)

  const download = async (format: 'csv' | 'xlsx') => {
    setLoading(true)
    try { await kpiApi.downloadExport(table, format) } finally { setLoading(false) }
  }

  if (!canExport) return null

  return (
    <ButtonGroup size="small" variant="outlined" disabled={loading}>
      <Button startIcon={<DownloadIcon />} onClick={() => download('csv')}>CSV</Button>
      <Button startIcon={<DownloadIcon />} onClick={() => download('xlsx')}>Excel</Button>
    </ButtonGroup>
  )
}

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------

export function KpiDashboardPage() {
  const { user } = useAuth()
  const [period, setPeriod] = useState<Period>('month')
  const [customFrom, setCustomFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 29); return d.toISOString().slice(0, 10)
  })
  const [customTo, setCustomTo] = useState(todayStr)

  const { from, to } = periodDates(period, { from: customFrom, to: customTo })

  const isAdmin = user?.roles.some(r => r === 'admin' || r === 'super_admin') ?? false
  const isAccountant = user?.roles.some(r => r === 'accountant') ?? false
  const hasPerm = useCallback((p: string) => user?.permissions.includes(p) ?? false, [user])

  const showWorkshop = isAdmin || (hasPerm('reporting.workshop.read') && !isAccountant)
  const showInventory = isAdmin || (hasPerm('reporting.inventory.read') && !isAccountant)
  const showExportFinance = hasPerm('reporting.accounting.export') || isAdmin
  const showExportInventory = (hasPerm('reporting.inventory.read') || isAdmin)

  const { data: live, isLoading: liveLoading, error: liveError } = useQuery({
    queryKey: ['kpi', 'live'],
    queryFn: kpiApi.getLive,
    refetchInterval: (query) =>
      query.state.data ? (query.state.data.refresh_interval_seconds ?? 300) * 1000 : 300_000,
    staleTime: 0,
  })

  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['kpi', 'analytics', from, to],
    queryFn: () => kpiApi.getAnalytics(from, to),
    enabled: !!live,
    staleTime: 60_000,
  })

  const { data: outstandingTrend, isLoading: outstandingLoading } = useQuery({
    queryKey: ['kpi', 'snapshots', 'outstanding', from, to],
    queryFn: () => kpiApi.getTrend('outstanding_amount_minor', from, to),
    enabled: !!live,
    staleTime: 60_000,
  })

  if (liveLoading) {
    return (
      <Box display="flex" justifyContent="center" mt={8}>
        <CircularProgress />
      </Box>
    )
  }

  if (liveError || !live) {
    return (
      <Box p={4}>
        <Alert severity="error">Impossible de charger les KPIs.</Alert>
      </Box>
    )
  }

  const k = live.kpis
  const topCustomers = (k.top_customers?.meta ?? []) as TopCustomerEntry[]
  const topSuppliers = (k.top_suppliers?.meta ?? []) as TopSupplierEntry[]

  const revenueTrend = (analytics?.revenue_trend ?? []).map(p => ({
    date: p.date,
    value: p.value,
  }))
  const repairTrend = (analytics?.repair_count_trend ?? []).map(p => ({
    date: p.date,
    value: p.value,
  }))
  const outstandingPoints = (outstandingTrend?.points ?? []).map(p => ({
    date: p.snapshot_date,
    value: p.value != null ? Number(p.value) : null,
  }))
  const mechanicData = analytics?.mechanic_productivity ?? []

  // Design system palette — consistent with the rest of the app
  const BAR_COLORS = ['#2563EB', '#10B981', '#F59E0B', '#8B5CF6', '#EF4444', '#06B6D4']

  return (
    <Box>
      <PageHeader
        title="Tableau de bord analytique"
        subtitle={`Actualisé toutes les ${Math.round(live.refresh_interval_seconds / 60)} min — ${new Date(live.computed_at).toLocaleTimeString('fr-FR')}`}
        actions={
          <Stack direction="column" gap={1} alignItems="flex-end">
            <ButtonGroup size="small" variant="outlined">
              {(['today', 'week', 'month', 'quarter', 'year', 'custom'] as Period[]).map(p => (
                <Button
                  key={p}
                  variant={period === p ? 'contained' : 'outlined'}
                  onClick={() => setPeriod(p)}
                  sx={{ textTransform: 'none', fontWeight: 600 }}
                >
                  {PERIOD_LABELS[p]}
                </Button>
              ))}
            </ButtonGroup>
            {period === 'custom' && (
              <Stack direction="row" gap={1}>
                <TextField
                  type="date"
                  size="small"
                  label="Du"
                  value={customFrom}
                  onChange={e => setCustomFrom(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                />
                <TextField
                  type="date"
                  size="small"
                  label="Au"
                  value={customTo}
                  onChange={e => setCustomTo(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                />
              </Stack>
            )}
          </Stack>
        }
      />

      {/* Finance KPI cards — visible to all */}
      <Stack direction="row" flexWrap="wrap" gap={2} mb={3}>
        <KpiCard
          label="CA mois en cours"
          value={fmtMinor(k.revenue_mtd?.value)}
          icon={<TrendingUpIcon />}
        />
        <KpiCard
          label="CA année en cours"
          value={fmtMinor(k.revenue_ytd?.value)}
          icon={<TrendingUpIcon />}
          color="success.main"
        />
        <KpiCard
          label="Encours total"
          value={fmtMinor(k.outstanding_amount_minor?.value)}
          icon={<AccountBalanceWalletIcon />}
          color="error.main"
        />
        <KpiCard
          label="Factures impayées"
          value={fmtCount(k.unpaid_invoices_count?.value)}
          icon={<WarningAmberIcon />}
          color="error.main"
        />
        <KpiCard
          label="Conversion devis"
          value={fmtPct(k.quotation_conversion_rate_pct?.value)}
          icon={<DescriptionIcon />}
          color="success.main"
        />
        <KpiCard
          label="Marge moyenne"
          value={fmtPct(k.margin_avg_pct?.value)}
          icon={<AccountBalanceWalletIcon />}
          color="success.main"
        />
      </Stack>

      {/* Workshop KPI cards — admin or workshop.read (not accountant) */}
      {showWorkshop && (
        <Stack direction="row" flexWrap="wrap" gap={2} mb={3}>
          <KpiCard
            label="OT ouverts"
            value={fmtCount(k.open_repair_orders_count?.value)}
            icon={<BuildIcon />}
            color="warning.main"
          />
          <KpiCard
            label="Taux d'occupation atelier"
            value={fmtPct(k.workshop_occupancy_pct?.value)}
            icon={<BuildIcon />}
            color="warning.main"
          />
          <KpiCard
            label="Durée réparation moy."
            value={fmtHours(k.avg_repair_duration_h?.value)}
            icon={<AccessTimeIcon />}
          />
          <KpiCard
            label="Immobilisation moy."
            value={fmtHours(k.avg_immobilization_h?.value)}
            icon={<AccessTimeIcon />}
            color="warning.main"
          />
          <KpiCard
            label="Taux de retour"
            value={fmtPct(k.comeback_rate_pct?.value)}
            icon={<RepeatIcon />}
            color={(k.comeback_rate_pct?.value ?? 0) > 10 ? 'error.main' : 'success.main'}
          />
        </Stack>
      )}

      {/* Inventory KPI cards */}
      {showInventory && (
        <Stack direction="row" flexWrap="wrap" gap={2} mb={3}>
          <KpiCard
            label="Alertes stock bas"
            value={fmtCount(k.low_stock_alerts_count?.value)}
            icon={<InventoryIcon />}
            color={(k.low_stock_alerts_count?.value ?? 0) > 0 ? 'error.main' : 'success.main'}
          />
        </Stack>
      )}

      {/* Charts row 1: revenue + outstanding balance */}
      <Stack direction="row" flexWrap="wrap" gap={3} mb={3}>
        <ChartCard
          title="Évolution du chiffre d'affaires"
          loading={analyticsLoading}
          empty={!analyticsLoading && revenueTrend.length === 0}
        >
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={revenueTrend} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563EB" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" strokeOpacity={0.7} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={v => `${(v / 100).toLocaleString('fr-FR')} €`}
              />
              <Tooltip
                content={(props) => (
                  <ChartTooltip
                    {...props}
                    formatter={v => (v / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
                  />
                )}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#2563EB"
                strokeWidth={2}
                fill="url(#revenueGrad)"
                dot={false}
                connectNulls
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Évolution de l'encours clients"
          loading={outstandingLoading}
          empty={!outstandingLoading && outstandingPoints.length === 0}
        >
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={outstandingPoints} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="outstandingGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#EF4444" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" strokeOpacity={0.7} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={v => `${(v / 100).toLocaleString('fr-FR')} €`}
              />
              <Tooltip
                content={(props) => (
                  <ChartTooltip
                    {...props}
                    formatter={v => (v / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
                  />
                )}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#EF4444"
                strokeWidth={2}
                fill="url(#outstandingGrad)"
                dot={false}
                connectNulls
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
      </Stack>

      {/* Charts row 2: repair count + mechanic productivity (workshop only) */}
      {showWorkshop && (
        <Stack direction="row" flexWrap="wrap" gap={3} mb={3}>
          <ChartCard
            title="Réparations terminées par jour"
            loading={analyticsLoading}
            empty={!analyticsLoading && repairTrend.length === 0}
          >
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={repairTrend} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" strokeOpacity={0.7} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  content={(props) => (
                    <ChartTooltip {...props} formatter={v => `${v} réparation${v > 1 ? 's' : ''}`} />
                  )}
                />
                <Bar dataKey="value" fill="#10B981" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard
            title="Productivité mécaniciens"
            loading={analyticsLoading}
            empty={!analyticsLoading && mechanicData.length === 0}
          >
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={mechanicData}
                layout="vertical"
                margin={{ top: 5, right: 20, left: 60, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" strokeOpacity={0.7} />
                <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={60} />
                <Tooltip
                  content={(props) => (
                    <ChartTooltip {...props} formatter={v => `${v} OT terminé${v > 1 ? 's' : ''}`} />
                  )}
                />
                <Bar dataKey="completed_count" radius={[0, 3, 3, 0]}>
                  {mechanicData.map((_, i) => (
                    <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </Stack>
      )}

      {/* Tables: top customers + top suppliers */}
      <Stack direction="row" gap={3} flexWrap="wrap" mb={3}>
        <Card sx={{ flex: '1 1 300px', minWidth: 300 }}>
          <CardContent>
            <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <PeopleIcon color="primary" />
                <Typography variant="h6" fontWeight={600}>Top 10 clients</Typography>
              </Stack>
              <ExportButtons table="top_customers" canExport={showExportFinance} />
            </Stack>
            <Divider sx={{ mb: 1 }} />
            {topCustomers.length === 0 ? (
              <Typography variant="body2" color="text.secondary">Aucune donnée</Typography>
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
                      <TableCell align="right">{fmtMinor(c.revenue_minor)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card sx={{ flex: '1 1 300px', minWidth: 300 }}>
          <CardContent>
            <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <LocalShippingIcon color="primary" />
                <Typography variant="h6" fontWeight={600}>Top 10 fournisseurs</Typography>
              </Stack>
              <ExportButtons table="top_suppliers" canExport={showExportFinance} />
            </Stack>
            <Divider sx={{ mb: 1 }} />
            {topSuppliers.length === 0 ? (
              <Typography variant="body2" color="text.secondary">Aucune donnée</Typography>
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
                      <TableCell align="right">{fmtMinor(s.spend_minor)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </Stack>

      {/* Low-stock alerts table (inventory section) */}
      {showInventory && (
        <Card>
          <CardContent>
            <Stack direction="row" alignItems="center" justifyContent="space-between" mb={2}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <InventoryIcon color="error" />
                <Typography variant="h6" fontWeight={600}>Alertes stock bas (ouvertes)</Typography>
              </Stack>
              <ExportButtons table="low_stock_alerts" canExport={showExportInventory} />
            </Stack>
            <Divider sx={{ mb: 1 }} />
            <Typography variant="body2" color="text.secondary">
              Données en temps réel — le tableau liste uniquement les alertes à statut <em>ouvert</em>.
            </Typography>
            <Typography variant="caption" color="text.disabled">
              Allez dans le module Stock pour acquitter ou résoudre les alertes.
            </Typography>
          </CardContent>
        </Card>
      )}
    </Box>
  )
}
