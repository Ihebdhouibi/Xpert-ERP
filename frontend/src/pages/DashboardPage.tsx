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
  Skeleton,
  Stack,
  Typography,
} from '@mui/material'
import BuildRoundedIcon from '@mui/icons-material/BuildRounded'
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded'
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded'
import AccountBalanceWalletRoundedIcon from '@mui/icons-material/AccountBalanceWalletRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import ViewKanbanRoundedIcon from '@mui/icons-material/ViewKanbanRounded'
import FindInPageRoundedIcon from '@mui/icons-material/FindInPageRounded'
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded'
import BarChartRoundedIcon from '@mui/icons-material/BarChartRounded'
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded'
import { kpiApi } from '../lib/kpiApi'
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
        cursor: 'pointer',
        transition: 'box-shadow 0.15s, transform 0.15s',
        '&:hover': {
          boxShadow: '0 8px 24px rgba(0,0,0,0.1)',
          transform: 'translateY(-2px)',
        },
      }}
      onClick={() => navigate(to)}
    >
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
        cursor: 'pointer',
        transition: 'box-shadow 0.15s, transform 0.15s, border-color 0.15s',
        '&:hover': {
          boxShadow: '0 8px 24px rgba(37,99,235,0.12)',
          borderColor: '#BFDBFE',
          transform: 'translateY(-2px)',
        },
      }}
      onClick={() => navigate(to)}
    >
      <CardContent sx={{ p: 2 }}>
        <Box
          sx={{
            width: 36,
            height: 36,
            borderRadius: '10px',
            bgcolor: '#EFF6FF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#2563EB',
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
            <MetricCard
              label="CA du mois"
              value={
                k?.revenue_mtd?.value != null
                  ? formatMinor(k.revenue_mtd.value)
                  : '—'
              }
              sub="Chiffre d'affaires mois en cours"
              icon={<TrendingUpRoundedIcon sx={{ fontSize: 22 }} />}
              iconBg="#DCFCE7"
              iconColor="#059669"
              loading={isLoading}
              onClick={() => navigate('/kpi')}
            />
          </Grid>
        )}
        {!isMechanic && (
          <Grid item xs={6} md={3}>
            <MetricCard
              label="Encours clients"
              value={
                k?.outstanding_amount_minor?.value != null
                  ? formatMinor(k.outstanding_amount_minor.value)
                  : '—'
              }
              sub="Créances clients en attente"
              icon={<AccountBalanceWalletRoundedIcon sx={{ fontSize: 22 }} />}
              iconBg="#FEE2E2"
              iconColor="#DC2626"
              loading={isLoading}
              onClick={() => navigate('/kpi')}
            />
          </Grid>
        )}
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
                  label="Kanban atelier"
                  description="Vue en temps réel des OTs en cours"
                  icon={<ViewKanbanRoundedIcon sx={{ fontSize: 22 }} />}
                  iconBg="#EFF6FF"
                  iconColor="#2563EB"
                  to="/workshop"
                />
                <QuickActionCard
                  label="Inspections"
                  description="Contrôles véhicules et approbations clients"
                  icon={<FindInPageRoundedIcon sx={{ fontSize: 22 }} />}
                  iconBg="#F0FDF4"
                  iconColor="#059669"
                  to="/inspections"
                />
                <QuickActionCard
                  label="Stock & pièces"
                  description="Niveaux de stock et alertes"
                  icon={<InventoryRoundedIcon sx={{ fontSize: 22 }} />}
                  iconBg="#FFF7ED"
                  iconColor="#EA580C"
                  to="/stock"
                />
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
                    { label: 'Inspections', sub: 'Contrôles véhicules', icon: <FindInPageRoundedIcon sx={{ fontSize: 18 }} />, to: '/inspections' },
                    { label: 'Kanban', sub: 'Vue atelier', icon: <ViewKanbanRoundedIcon sx={{ fontSize: 18 }} />, to: '/workshop' },
                  ].map(m => (
                    <Grid item xs={6} sm={3} key={m.to}>
                      <ModuleTile {...m} />
                    </Grid>
                  ))}
                </Grid>
              </Box>

              <Divider sx={{ my: 1.5 }} />

              {(hasPermission('supplier.read') || hasPermission('part.read')) && (
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
                  ].filter((m): m is { label: string; sub: string; icon: React.ReactNode; to: string } => Boolean(m)).map((m) => (
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
