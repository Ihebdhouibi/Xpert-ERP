import { NavLink, useLocation } from 'react-router-dom'
import {
  Box,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import DirectionsCarRoundedIcon from '@mui/icons-material/DirectionsCarRounded'
import ChevronLeftRoundedIcon from '@mui/icons-material/ChevronLeftRounded'
import { navSections, type NavItem } from './navConfig'
import { useAuth } from '../../contexts/AuthContext'
import { sidebarTokens as T } from '../../theme'

const DRAWER_WIDTH = T.width
const COLLAPSED_WIDTH = T.collapsedWidth

function NavItemRow({
  item,
  collapsed,
}: {
  item: NavItem
  collapsed: boolean
}) {
  const location = useLocation()
  const isActive =
    item.exact
      ? location.pathname === item.path
      : location.pathname === item.path ||
        (item.path !== '/' && location.pathname.startsWith(item.path + '/')) ||
        location.pathname.startsWith(item.path + '?')

  const Icon = item.icon

  const inner = (
    <ListItemButton
      component={NavLink}
      to={item.path}
      sx={{
        mx: 1,
        mb: 0.25,
        px: 1.5,
        py: 0.875,
        minHeight: 40,
        borderRadius: '8px',
        justifyContent: collapsed ? 'center' : 'flex-start',
        bgcolor: isActive ? T.activeBg : 'transparent',
        borderLeft: isActive ? `3px solid ${T.activeBorder}` : '3px solid transparent',
        transition: 'all 0.15s ease',
        '&:hover': {
          bgcolor: isActive ? T.activeBg : T.hover,
        },
        '&.active': {},
      }}
    >
      <ListItemIcon
        sx={{
          minWidth: collapsed ? 0 : 34,
          color: isActive ? T.activeIconColor : T.iconColor,
          mr: collapsed ? 0 : 0,
        }}
      >
        <Icon sx={{ fontSize: 19 }} />
      </ListItemIcon>
      {!collapsed && (
        <ListItemText
          primary={item.label}
          primaryTypographyProps={{
            fontSize: '0.8125rem',
            fontWeight: isActive ? 600 : 400,
            color: isActive ? T.activeText : T.text,
            lineHeight: 1.4,
            noWrap: true,
          }}
        />
      )}
    </ListItemButton>
  )

  if (collapsed) {
    return (
      <Tooltip title={item.label} placement="right" arrow>
        {inner}
      </Tooltip>
    )
  }
  return inner
}

function NavItemWithPermission({
  item,
  collapsed,
}: {
  item: NavItem
  collapsed: boolean
}) {
  const { user } = useAuth()
  if (item.permission && !user?.permissions.includes(item.permission)) return null
  if (item.hideForRoles && user?.roles.some((r) => item.hideForRoles!.includes(r))) return null
  return <NavItemRow item={item} collapsed={collapsed} />
}

function LogoBadge({ size = 32 }: { size?: number }) {
  return (
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: '10px',
        background: 'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        boxShadow: '0 4px 12px rgba(37,99,235,0.4)',
      }}
    >
      <DirectionsCarRoundedIcon sx={{ color: '#fff', fontSize: size * 0.55 }} />
    </Box>
  )
}

interface SidebarContentProps {
  collapsed: boolean
  onToggle: () => void
  onNavClick?: () => void
}

function SidebarContent({ collapsed, onToggle, onNavClick }: SidebarContentProps) {
  const { user } = useAuth()

  const initials =
    user?.full_name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2) ?? '?'

  return (
    <Box
      sx={{
        width: collapsed ? COLLAPSED_WIDTH : DRAWER_WIDTH,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: T.bg,
        overflow: 'hidden',
        transition: 'width 0.22s cubic-bezier(0.4,0,0.2,1)',
      }}
      onClick={onNavClick}
    >
      {/* Logo header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          px: collapsed ? 1 : 2,
          py: 0,
          minHeight: 64,
          borderBottom: `1px solid ${T.divider}`,
        }}
      >
        {collapsed ? (
          <LogoBadge />
        ) : (
          <>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <LogoBadge />
              <Box>
                <Typography
                  sx={{
                    color: '#F8FAFC',
                    fontWeight: 700,
                    fontSize: '0.9375rem',
                    lineHeight: 1.2,
                    letterSpacing: '-0.02em',
                  }}
                >
                  Xpert ERP
                </Typography>
                <Typography
                  sx={{
                    color: T.sectionLabel,
                    fontSize: '0.6875rem',
                    lineHeight: 1.3,
                    fontWeight: 500,
                  }}
                >
                  Atelier automobile
                </Typography>
              </Box>
            </Box>
            <Tooltip title="Réduire le menu" placement="right">
              <Box
                onClick={e => {
                  e.stopPropagation()
                  onToggle()
                }}
                sx={{
                  width: 28,
                  height: 28,
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  color: T.sectionLabel,
                  border: `1px solid ${T.divider}`,
                  flexShrink: 0,
                  transition: 'all 0.15s',
                  '&:hover': { color: T.text, borderColor: '#334155', bgcolor: T.hover },
                }}
              >
                <ChevronLeftRoundedIcon sx={{ fontSize: 18 }} />
              </Box>
            </Tooltip>
          </>
        )}
      </Box>

      {/* Navigation */}
      <Box
        sx={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          py: 1.5,
          '&::-webkit-scrollbar': { width: 4 },
          '&::-webkit-scrollbar-thumb': {
            background: '#1E293B',
            borderRadius: 2,
          },
        }}
      >
        {navSections.map((section, si) => {
          const hasVisible = section.items.some(
            item =>
              (!item.permission || user?.permissions.includes(item.permission)) &&
              !(item.hideForRoles && user?.roles.some(r => item.hideForRoles!.includes(r)))
          )
          if (!hasVisible) return null
          return (
          <Box key={si} sx={{ mb: 0.5 }}>
            {!collapsed && (
              <Typography
                sx={{
                  px: 2.5,
                  pt: si === 0 ? 0 : 1.5,
                  pb: 0.5,
                  fontSize: '0.6875rem',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: T.sectionLabel,
                  userSelect: 'none',
                }}
              >
                {section.label}
              </Typography>
            )}
            {collapsed && si > 0 && (
              <Box
                sx={{
                  borderTop: `1px solid ${T.divider}`,
                  mx: 1.5,
                  my: 1,
                }}
              />
            )}
            <List disablePadding>
              {section.items.map(item => (
                <NavItemWithPermission
                  key={item.path}
                  item={item}
                  collapsed={collapsed}
                />
              ))}
            </List>
          </Box>
          )
        })}
      </Box>

      {/* User profile footer */}
      <Box
        sx={{
          borderTop: `1px solid ${T.divider}`,
          p: 1.5,
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          justifyContent: collapsed ? 'center' : 'flex-start',
        }}
      >
        <Box
          sx={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #2563EB, #1D4ED8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            boxShadow: '0 2px 8px rgba(37,99,235,0.35)',
          }}
        >
          <Typography sx={{ color: '#fff', fontSize: '0.6875rem', fontWeight: 700 }}>
            {initials}
          </Typography>
        </Box>
        {!collapsed && (
          <Box sx={{ overflow: 'hidden', flex: 1, minWidth: 0 }}>
            <Typography
              sx={{
                color: '#E2E8F0',
                fontSize: '0.8125rem',
                fontWeight: 500,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {user?.full_name}
            </Typography>
            <Typography
              sx={{
                color: T.sectionLabel,
                fontSize: '0.6875rem',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {user?.roles[0] ?? 'Utilisateur'}
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  )
}

export interface SidebarProps {
  open: boolean
  onToggle: () => void
  mobileOpen: boolean
  onMobileClose: () => void
}

export function Sidebar({ open, onToggle, mobileOpen, onMobileClose }: SidebarProps) {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))

  const drawerWidth = open ? DRAWER_WIDTH : COLLAPSED_WIDTH

  if (isMobile) {
    return (
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onMobileClose}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            border: 'none',
            bgcolor: T.bg,
          },
        }}
      >
        <SidebarContent
          collapsed={false}
          onToggle={onMobileClose}
          onNavClick={onMobileClose}
        />
      </Drawer>
    )
  }

  return (
    <Drawer
      variant="permanent"
      sx={{
        display: { xs: 'none', md: 'block' },
        width: drawerWidth,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: drawerWidth,
          border: 'none',
          bgcolor: T.bg,
          overflowX: 'hidden',
          transition: theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
        },
      }}
      open
    >
      <SidebarContent collapsed={!open} onToggle={onToggle} />
    </Drawer>
  )
}

export { DRAWER_WIDTH, COLLAPSED_WIDTH }
