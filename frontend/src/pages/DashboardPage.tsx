import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Divider,
  Grid,
  IconButton,
  Menu,
  MenuItem,
  Popover,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded'
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded'
import AccountBalanceWalletRoundedIcon from '@mui/icons-material/AccountBalanceWalletRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import ViewKanbanRoundedIcon from '@mui/icons-material/ViewKanbanRounded'
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded'
import BarChartRoundedIcon from '@mui/icons-material/BarChartRounded'
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded'
import CalendarMonthRoundedIcon from '@mui/icons-material/CalendarMonthRounded'
import { kpiApi } from '../lib/kpiApi'
import {
  AsOfPreset,
  AS_OF_LABELS,
  asOfDate,
  Period,
  PERIOD_LABELS,
  periodDates,
  toLocalDateStr,
  todayStr,
} from '../lib/periodHelpers'
import { useAuth } from '../contexts/AuthContext'
import { formatMinor } from '../components/ui/CurrencyDisplay'

function greeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Bonjour'
  if (h < 18) return 'Bon après-midi'
  return 'Bonsoir'
}

function todayLabel(): string {
  return new Date().toLocaleDateString('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

// ─── Metric card ──────────────────────────────────────────────────────────────

interface MetricCardProps {
  label: string
  value: string
  sub?: string
  icon: React.ReactNode
  iconBg: string
  iconColor: string
  trend?: 'up' | 'down' | 'neutral'
  loading?: boolean
  onClick?: () => void
}

function MetricCard({
  label,
  value,
  sub,
  icon,
  iconBg,
  iconColor,
  loading,
  onClick,
}: MetricCardProps) {
  const inner = (
    <CardContent sx={{ p: 2.5 }}>
      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" mb={2}>
        <Box
          sx={{
            width: 44,
            height: 44,
            borderRadius: '12px',
            bgcolor: iconBg,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: iconColor,
          }}
        >
          {icon}
        </Box>
      </Stack>
      {loading ? (
        <>
          <Skeleton width="55%" height={32} sx={{ mb: 0.5 }} />
          <Skeleton width="70%" height={18} />
        </>
      ) : (
        <>
          <Typography variant="h5" fontWeight={700} lineHeight={1.1} mb={0.5}>
            {value}
          </Typography>
          <Typography variant="caption" color="text.secondary" fontWeight={500}>
            {sub ?? label}
          </Typography>
        </>
      )}
    </CardContent>
  )

  return (
    <Card
      sx={{
        height: '100%',
        transition: 'box-shadow 0.15s, transform 0.15s',
        ...(onClick && {
          '&:hover': {
            boxShadow: '0 8px 24px rgba(0,0,0,0.1)',
            transform: 'translateY(-2px)',
          },
        }),
      }}
    >
      {onClick ? (
        <CardActionArea onClick={onClick} sx={{ height: '100%', alignItems: 'flex-start' }}>
          {inner}
        </CardActionArea>
      ) : (
        inner
      )}
    </Card>
  )
}

// ─── Revenue metric card — period-scoped (Aujourd'hui/Semaine/Mois/Année/Perso) ─

const REVENUE_MENU_PERIODS: Period[] = ['today', 'week', 'month', 'year']

function RevenueMetricCard({ onNavigate }: { onNavigate: () => void }) {
  const [period, setPeriod] = useState<Period>('month')
  const [customFrom, setCustomFrom] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - 29)
    return toLocalDateStr(d)
  })
  const [customTo, setCustomTo] = useState(todayStr)
  const [menuOpen, setMenuOpen] = useState(false)
  const [customOpen, setCustomOpen] = useState(false)
  const anchorRef = useRef<HTMLButtonElement>(null)

  const { from, to } = periodDates(period, { from: customFrom, to: customTo })

  const { data, isLoading } = useQuery({
    queryKey: ['kpi', 'revenue', from, to],
    queryFn: () => kpiApi.getRevenue(from, to),
    staleTime: 60_000,
    retry: false,
  })

  const selectPeriod = (p: Period) => {
    setMenuOpen(false)
    if (p === 'custom') {
      setCustomOpen(true)
    } else {
      setPeriod(p)
    }
  }

  return (
    <Card
      sx={{
        height: '100%',
        transition: 'box-shadow 0.15s, transform 0.15s',
        '&:hover': {
          boxShadow: '0 8px 24px rgba(0,0,0,0.1)',
          transform: 'translateY(-2px)',
        },
      }}
    >
      {/* Header row sits outside the clickable action area so the period
          icon button is never a <button> nested inside another <button>. */}
      <CardContent sx={{ p: 2.5, pb: 0 }}>
        <Stack direction="row" alignItems="flex-start" justifyContent="space-between" mb={2}>
          <Box
            sx={{
              width: 44,
              height: 44,
              borderRadius: '12px',
              bgcolor: '#DCFCE7',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#059669',
            }}
          >
            <TrendingUpRoundedIcon sx={{ fontSize: 22 }} />
          </Box>
          <IconButton
            ref={anchorRef}
            size="small"
            onClick={() => setMenuOpen(true)}
            aria-label="Choisir la période du chiffre d'affaires"
            sx={{ mt: -0.5, mr: -0.5, color: 'text.secondary' }}
          >
            <CalendarMonthRoundedIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Stack>
      </CardContent>

      <CardActionArea onClick={onNavigate} sx={{ alignItems: 'flex-start', display: 'block' }}>
        <CardContent sx={{ p: 2.5, pt: 0 }}>
          {isLoading ? (
            <>
              <Skeleton width="55%" height={32} sx={{ mb: 0.5 }} />
              <Skeleton width="70%" height={18} />
            </>
          ) : (
            <>
              <Typography variant="h5" fontWeight={700} lineHeight={1.1} mb={0.5}>
                {formatMinor(data?.value ?? null)}
              </Typography>
              <Typography variant="caption" color="text.secondary" fontWeight={500}>
                Chiffre d'affaires — {PERIOD_LABELS[period]}
              </Typography>
            </>
          )}
        </CardContent>
      </CardActionArea>

      <Menu anchorEl={anchorRef.current} open={menuOpen} onClose={() => setMenuOpen(false)}>
        {REVENUE_MENU_PERIODS.map(p => (
          <MenuItem key={p} selected={period === p} onClick={() => selectPeriod(p)}>
            {PERIOD_LABELS[p]}
          </MenuItem>
        ))}
        <MenuItem selected={period === 'custom'} onClick={() => selectPeriod('custom')}>
          {PERIOD_LABELS.custom}
        </MenuItem>
      </Menu>

      <Popover
        anchorEl={anchorRef.current}
        open={customOpen}
        onClose={() => setCustomOpen(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Stack spacing={1.5} sx={{ p: 2, width: 220 }}>
          <Typography variant="subtitle2" fontWeight={700}>
            Période personnalisée
          </Typography>
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
          <Button
            size="small"
            variant="contained"
            onClick={() => {
              setPeriod('custom')
              setCustomOpen(false)
            }}
          >
            Appliquer
          </Button>
        </Stack>
      </Popover>
    </Card>
  )
}

// ─── Outstanding balance card — "as of" a date, not a period ──────────────────
// Encours clients is a balance (a snapshot), not a flow — "as of a date" is
// the meaningful question, not "during a range". See RevenueMetricCard above
// for the analogous range-based card.

const OUTSTANDING_MENU_PRESETS: AsOfPreset[] = ['today', 'last_month_end', 'year_start']

function OutstandingMetricCard({ onNavigate }: { onNavigate: () => void }) {
  const [preset, setPreset] = useState<AsOfPreset>('today')
  const [customDate, setCustomDate] = useState(todayStr)
  const [menuOpen, setMenuOpen] = useState(false)
  const [customOpen, setCustomOpen] = useState(false)
  const anchorRef = useRef<HTMLButtonElement>(null)

  const asOf = asOfDate(preset, customDate)

  const { data, isLoading } = useQuery({
    queryKey: ['kpi', 'outstanding', asOf],
    queryFn: () => kpiApi.getOutstanding(asOf),
    staleTime: 60_000,
    retry: false,
  })

  const selectPreset = (p: AsOfPreset) => {
    setMenuOpen(false)
    if (p === 'custom') {
      setCustomOpen(true)
    } else {
      setPreset(p)
    }
  }

  return (
    <Card
      sx={{
        height: '100%',
        transition: 'box-shadow 0.15s, transform 0.15s',
        '&:hover': {
          boxShadow: '0 8px 24px rgba(0,0,0,0.1)',
          transform: 'translateY(-2px)',
        },
      }}
    >
      <CardContent sx={{ p: 2.5, pb: 0 }}>
        <Stack direction="row" alignItems="flex-start" justifyContent="space-between" mb={2}>
          <Box
            sx={{
              width: 44,
              height: 44,
              borderRadius: '12px',
              bgcolor: '#FEE2E2',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#DC2626',
            }}
          >
            <AccountBalanceWalletRoundedIcon sx={{ fontSize: 22 }} />
          </Box>
          <IconButton
            ref={anchorRef}
            size="small"
            onClick={() => setMenuOpen(true)}
            aria-label="Choisir la date de l'encours clients"
            sx={{ mt: -0.5, mr: -0.5, color: 'text.secondary' }}
          >
            <CalendarMonthRoundedIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Stack>
      </CardContent>

      <CardActionArea onClick={onNavigate} sx={{ alignItems: 'flex-start', display: 'block' }}>
        <CardContent sx={{ p: 2.5, pt: 0 }}>
          {isLoading ? (
            <>
              <Skeleton width="55%" height={32} sx={{ mb: 0.5 }} />
              <Skeleton width="70%" height={18} />
            </>
          ) : (
            <>
              <Typography variant="h5" fontWeight={700} lineHeight={1.1} mb={0.5}>
                {formatMinor(data?.value ?? null)}
              </Typography>
              <Typography variant="caption" color="text.secondary" fontWeight={500}>
                Encours clients — {AS_OF_LABELS[preset]}
              </Typography>
            </>
          )}
        </CardContent>
      </CardActionArea>

      <Menu anchorEl={anchorRef.current} open={menuOpen} onClose={() => setMenuOpen(false)}>
        {OUTSTANDING_MENU_PRESETS.map(p => (
          <MenuItem key={p} selected={preset === p} onClick={() => selectPreset(p)}>
            {AS_OF_LABELS[p]}
          </MenuItem>
        ))}
        <MenuItem selected={preset === 'custom'} onClick={() => selectPreset('custom')}>
          {AS_OF_LABELS.custom}
        </MenuItem>
      </Menu>

      <Popover
        anchorEl={anchorRef.current}
        open={customOpen}
        onClose={() => setCustomOpen(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Stack spacing={1.5} sx={{ p: 2, width: 200 }}>
          <Typography variant="subtitle2" fontWeight={700}>
            Date personnalisée
          </Typography>
          <TextField
            type="date"
            size="small"
            label="Encours au"
            value={customDate}
            onChange={e => setCustomDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
          <Button
            size="small"
            variant="contained"
            onClick={() => {
              setPreset('custom')
              setCustomOpen(false)
            }}
          >
            Appliquer
          </Button>
        </Stack>
      </Popover>
    </Card>
  )
}

// ─── Quick action card ─────────────────────────────────────────────────────────

interface QuickActionProps {
  label: string
  description: string
  icon: React.ReactNode
  iconBg: string
  iconColor: string
  to: string
}

function QuickActionCard({ label, description, icon, iconBg, iconColor, to }: QuickActionProps) {
  const navigate = useNavigate()
  return (
    <Card
      sx={{
        transition: 'box-shadow 0.15s, transform 0.15s',
        '&:hover': {
          boxShadow: '0 8px 24px rgba(0,0,0,0.1)',
          transform: 'translateY(-2px)',
        },
      }}
    >
      <CardActionArea onClick={() => navigate(to)} sx={{ alignItems: 'flex-start', display: 'block' }}>
      <CardContent sx={{ p: 2.5 }}>
        <Stack direction="row" alignItems="center" spacing={2}>
          <Box
            sx={{
              width: 48,
              height: 48,
              borderRadius: '14px',
              bgcolor: iconBg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: iconColor,
              flexShrink: 0,
            }}
          >
            {icon}
          </Box>
          <Box flex={1} minWidth={0}>
            <Typography variant="subtitle2" fontWeight={700} mb={0.25} noWrap>
              {label}
            </Typography>
            <Typography variant="caption" color="text.secondary" lineHeight={1.4}>
              {description}
            </Typography>
          </Box>
          <ArrowForwardRoundedIcon sx={{ color: 'text.disabled', fontSize: 18, flexShrink: 0 }} />
        </Stack>
      </CardContent>
      </CardActionArea>
    </Card>
  )
}

// ─── Module tile ───────────────────────────────────────────────────────────────

interface ModuleTileProps {
  label: string
  sub: string
  icon: React.ReactNode
  to: string
  permission?: string
}

function ModuleTile({ label, sub, icon, to }: ModuleTileProps) {
  const navigate = useNavigate()
  return (
    <Card
      sx={{
        transition: 'box-shadow 0.15s, transform 0.15s, border-color 0.15s',
        '&:hover': {
          boxShadow: '0 8px 24px rgba(15,23,42,0.12)',
          borderColor: 'text.disabled',
          transform: 'translateY(-2px)',
        },
      }}
    >
      <CardActionArea onClick={() => navigate(to)} sx={{ alignItems: 'flex-start', display: 'block' }}>
      <CardContent sx={{ p: 2 }}>
        <Box
          sx={{
            width: 36,
            height: 36,
            borderRadius: '10px',
            bgcolor: 'action.hover',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'text.primary',
            mb: 1.5,
          }}
        >
          {icon}
        </Box>
        <Typography variant="subtitle2" fontWeight={600} mb={0.25} lineHeight={1.3}>
          {label}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {sub}
        </Typography>
      </CardContent>
      </CardActionArea>
    </Card>
  )
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export function DashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const firstName = user?.full_name.split(' ')[0] ?? ''

  const { data: live, isLoading } = useQuery({
    queryKey: ['kpi', 'live'],
    queryFn: kpiApi.getLive,
    staleTime: 60_000,
    retry: false,
  })

  const k = live?.kpis

  const hasPermission = (p: string) => user?.permissions.includes(p) ?? false
  const isMechanic = user?.roles.includes('mechanic') ?? false

  return (
    <Box>
      {/* ── Flat typographic hero — no gradient, typography does the work ─── */}
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        gap={2}
        mb={3}
      >
        <Box>
          <Typography
            variant="h4"
            fontWeight={700}
            letterSpacing="-0.02em"
            color="text.primary"
            mb={0.375}
          >
            {greeting()}, {firstName}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {todayLabel()}
          </Typography>
        </Box>

        <Stack direction="row" spacing={1.25} flexShrink={0}>
          {hasPermission('repair_order.create') && (
            <Button
              variant="outlined"
              startIcon={<AddRoundedIcon />}
              onClick={() => navigate('/repair-orders/new')}
            >
              Nouvel OT
            </Button>
          )}
          {hasPermission('customer.create') && (
            <Button
              variant="contained"
              startIcon={<AddRoundedIcon />}
              onClick={() => navigate('/customers/new')}
            >
              Nouveau client
            </Button>
          )}
        </Stack>
      </Stack>

      {/* ── KPI metrics row ──────────────────────────────────────────────────── */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6} md={3}>
          <MetricCard
            label="OTs en cours"
            value={
              k?.open_repair_orders_count?.value != null
                ? String(Math.round(k.open_repair_orders_count.value))
                : '—'
            }
            sub="Ordres de réparation ouverts"
            icon={<BuildRoundedIcon sx={{ fontSize: 22 }} />}
            iconBg="#FEF3C7"
            iconColor="#D97706"
            loading={isLoading}
            onClick={() => navigate('/repair-orders')}
          />
        </Grid>
        {!isMechanic && (
          <Grid item xs={6} md={3}>
            <RevenueMetricCard onNavigate={() => navigate('/kpi')} />
          </Grid>
        )}
        {!isMechanic && (
          <Grid item xs={6} md={3}>
            <OutstandingMetricCard onNavigate={() => navigate('/kpi')} />
          </Grid>
        )}
        {!isMechanic && (
          <Grid item xs={6} md={3}>
            <MetricCard
              label="Alertes stock"
              value={
                k?.low_stock_alerts_count?.value != null
                  ? String(Math.round(k.low_stock_alerts_count.value))
                  : '—'
              }
              sub="Pièces en rupture ou seuil bas"
              icon={<WarningAmberRoundedIcon sx={{ fontSize: 22 }} />}
              iconBg={
                (k?.low_stock_alerts_count?.value ?? 0) > 0 ? '#FEE2E2' : '#F0FDF4'
              }
              iconColor={
                (k?.low_stock_alerts_count?.value ?? 0) > 0 ? '#DC2626' : '#059669'
              }
              loading={isLoading}
              onClick={() => navigate('/stock')}
            />
          </Grid>
        )}
      </Grid>

      <Grid container spacing={3}>
        {/* ── Quick actions ──────────────────────────────────────────────────── */}
        <Grid item xs={12} md={5}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 2.5 }}>
              <Typography variant="h6" fontWeight={700} mb={0.5}>
                Accès rapide
              </Typography>
              <Typography variant="caption" color="text.secondary" mb={2} display="block">
                Vos raccourcis les plus utilisés
              </Typography>
              <Stack spacing={1.5}>
                <QuickActionCard
                  label="Suivi Atelier"
                  description="Vue en temps réel des OTs en cours"
                  icon={<ViewKanbanRoundedIcon sx={{ fontSize: 22 }} />}
                  iconBg="#F1F5F9"
                  iconColor="#334155"
                  to="/workshop"
                />
                {!isMechanic && (
                  <QuickActionCard
                    label="Stock & pièces"
                    description="Niveaux de stock et alertes"
                    icon={<InventoryRoundedIcon sx={{ fontSize: 22 }} />}
                    iconBg="#FFF7ED"
                    iconColor="#EA580C"
                    to="/stock"
                  />
                )}
                {hasPermission('reporting.dashboard.read') && !isMechanic && (
                  <QuickActionCard
                    label="Tableau de bord KPI"
                    description="Indicateurs de performance de l'atelier"
                    icon={<BarChartRoundedIcon sx={{ fontSize: 22 }} />}
                    iconBg="#FAF5FF"
                    iconColor="#7C3AED"
                    to="/kpi"
                  />
                )}
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        {/* ── All modules grid ───────────────────────────────────────────────── */}
        <Grid item xs={12} md={7}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 2.5 }}>
              <Typography variant="h6" fontWeight={700} mb={0.5}>
                Modules
              </Typography>
              <Typography variant="caption" color="text.secondary" mb={2} display="block">
                Accéder à tous les modules de l'ERP
              </Typography>

              <Box mb={1.5}>
                <Typography
                  variant="caption"
                  fontWeight={700}
                  color="text.disabled"
                  letterSpacing="0.07em"
                  textTransform="uppercase"
                  display="block"
                  mb={1}
                >
                  Atelier & Commercial
                </Typography>
                <Grid container spacing={1}>
                  {[
                    { label: 'Clients', sub: 'Gestion clients', icon: <PeopleRoundedIcon sx={{ fontSize: 18 }} />, to: '/customers' },
                    { label: 'OTs', sub: 'Ordres de réparation', icon: <BuildRoundedIcon sx={{ fontSize: 18 }} />, to: '/repair-orders' },
                    { label: 'Suivi Atelier', sub: 'Vue atelier', icon: <ViewKanbanRoundedIcon sx={{ fontSize: 18 }} />, to: '/workshop' },
                  ].filter(m => !isMechanic || m.to !== '/customers').map(m => (
                    <Grid item xs={6} sm={3} key={m.to}>
                      <ModuleTile {...m} />
                    </Grid>
                  ))}
                </Grid>
              </Box>

              <Divider sx={{ my: 1.5 }} />

              {!isMechanic && (hasPermission('supplier.read') || hasPermission('part.read')) && (
              <Box mb={1.5}>
                <Typography
                  variant="caption"
                  fontWeight={700}
                  color="text.disabled"
                  letterSpacing="0.07em"
                  textTransform="uppercase"
                  display="block"
                  mb={1}
                >
                  Achats & Stock
                </Typography>
                <Grid container spacing={1}>
                  {[
                    hasPermission('supplier.read') && { label: 'Fournisseurs', sub: 'Gestion achats', icon: <PeopleRoundedIcon sx={{ fontSize: 18 }} />, to: '/suppliers' },
                    hasPermission('purchase_order.read') && { label: 'Bons de cmd.', sub: "Ordres d'achat", icon: <BuildRoundedIcon sx={{ fontSize: 18 }} />, to: '/purchase-orders' },
                    hasPermission('part.read') && { label: 'Catalogue', sub: 'Pièces & SKU', icon: <InventoryRoundedIcon sx={{ fontSize: 18 }} />, to: '/parts' },
                    hasPermission('part.read') && { label: 'Stock', sub: 'Niveaux & alertes', icon: <WarningAmberRoundedIcon sx={{ fontSize: 18 }} />, to: '/stock' },
                  ].filter((m): m is Exclude<typeof m, false> => Boolean(m)).map((m) => (
                    <Grid item xs={6} sm={3} key={m.to}>
                      <ModuleTile {...m} />
                    </Grid>
                  ))}
                </Grid>
              </Box>
              )}

              {hasPermission('reporting.dashboard.read') && !isMechanic && (
                <>
                  <Divider sx={{ my: 1.5 }} />
                  <Box>
                    <Typography
                      variant="caption"
                      fontWeight={700}
                      color="text.disabled"
                      letterSpacing="0.07em"
                      textTransform="uppercase"
                      display="block"
                      mb={1}
                    >
                      Analytique
                    </Typography>
                    <Grid container spacing={1}>
                      <Grid item xs={6} sm={3}>
                        <ModuleTile
                          label="KPIs"
                          sub="Rapports & tendances"
                          icon={<BarChartRoundedIcon sx={{ fontSize: 18 }} />}
                          to="/kpi"
                        />
                      </Grid>
                    </Grid>
                  </Box>
                </>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}
