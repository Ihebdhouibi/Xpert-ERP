import { useMemo } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  Box,
  ButtonBase,
  Collapse,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import ChevronLeftRoundedIcon from '@mui/icons-material/ChevronLeftRounded'
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import StarRoundedIcon from '@mui/icons-material/StarRounded'
import StarBorderRoundedIcon from '@mui/icons-material/StarBorderRounded'
import { navSections, type NavItem } from './navConfig'
import { useAuth } from '../../contexts/AuthContext'
import { SIDEBAR_METRICS } from '../../theme'
import { useLocalStoragePref } from '../../hooks/useLocalStoragePref'

const FAVORITES_SECTION_LABEL = 'Favoris'

/** Same permission/role gate used for section visibility and for each item — kept in one place. */
function isItemVisible(item: NavItem, permissions?: string[], roles?: string[]): boolean {
  if (item.permission && !permissions?.includes(item.permission)) return false
  if (item.hideForRoles && roles?.some(r => item.hideForRoles!.includes(r))) return false
  return true
}

const DRAWER_WIDTH = SIDEBAR_METRICS.width
const COLLAPSED_WIDTH = SIDEBAR_METRICS.collapsedWidth

function NavItemRow({
  item,
  collapsed,
  favorited,
  onToggleFavorite,
}: {
  item: NavItem
  collapsed: boolean
  favorited?: boolean
  onToggleFavorite?: () => void
}) {
  const location = useLocation()
  const T = useTheme().custom.sidebar
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
      {!collapsed && onToggleFavorite && (
        <IconButton
          aria-label={favorited ? `Retirer ${item.label} des favoris` : `Ajouter ${item.label} aux favoris`}
          size="small"
          onClick={e => {
            // Nested inside a NavLink — prevent it from also navigating.
            e.preventDefault()
            e.stopPropagation()
            onToggleFavorite()
          }}
          sx={{
            p: 0.5,
            ml: 0.5,
            flexShrink: 0,
            color: favorited ? T.activeBorder : T.iconColor,
            opacity: favorited ? 1 : 0,
            transition: 'opacity 0.15s',
            '.MuiListItemButton-root:hover &, .MuiListItemButton-root:focus-within &': { opacity: 1 },
          }}
        >
          {favorited ? <StarRoundedIcon sx={{ fontSize: 16 }} /> : <StarBorderRoundedIcon sx={{ fontSize: 16 }} />}
        </IconButton>
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
  favorited,
  onToggleFavorite,
}: {
  item: NavItem
  collapsed: boolean
  favorited?: boolean
  onToggleFavorite?: () => void
}) {
  const { user } = useAuth()
  if (!isItemVisible(item, user?.permissions, user?.roles)) return null
  return (
    <NavItemRow
      item={item}
      collapsed={collapsed}
      favorited={favorited}
      onToggleFavorite={onToggleFavorite}
    />
  )
}

function LogoBadge({ size = 44 }: { size?: number }) {
  const navigate = useNavigate()
  // Small collapsed-state version: show just the car portion of the logo
  return (
    <ButtonBase
      aria-label="Accueil"
      onClick={(e) => { e.stopPropagation(); navigate('/') }}
      sx={{
        width: size,
        height: size,
        borderRadius: '8px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        overflow: 'hidden',
      }}
    >
      <img
        src="/assets/logo.png"
        alt="Motors Utilitaires"
        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
      />
    </ButtonBase>
  )
}

function SidebarSection({
  label,
  items,
  index,
  collapsed,
  isSectionCollapsed,
  onToggleSection,
  favoritePaths,
  onToggleFavorite,
}: {
  label: string
  items: NavItem[]
  index: number
  collapsed: boolean
  isSectionCollapsed: boolean
  onToggleSection: () => void
  favoritePaths: string[]
  onToggleFavorite: (path: string) => void
}) {
  const { user } = useAuth()
  const T = useTheme().custom.sidebar
  const visibleItems = items.filter(item => isItemVisible(item, user?.permissions, user?.roles))
  if (visibleItems.length === 0) return null

  return (
    <Box sx={{ mb: 0.5 }}>
      {!collapsed && (
        <ButtonBase
          onClick={e => {
            // The whole sidebar closes on any click when it's the mobile drawer —
            // toggling a section's collapse state shouldn't also close it.
            e.stopPropagation()
            onToggleSection()
          }}
          aria-expanded={!isSectionCollapsed}
          disableRipple
          sx={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 2.5,
            pt: index === 0 ? 0 : 1.5,
            pb: 0.5,
            borderRadius: 0,
          }}
        >
          <Typography
            sx={{
              fontSize: '0.6875rem',
              fontWeight: 700,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: T.sectionLabel,
              userSelect: 'none',
            }}
          >
            {label}
          </Typography>
          <ExpandMoreRoundedIcon
            sx={{
              fontSize: 15,
              color: T.sectionLabel,
              transition: 'transform 0.15s',
              transform: isSectionCollapsed ? 'rotate(-90deg)' : 'none',
            }}
          />
        </ButtonBase>
      )}
      {collapsed && index > 0 && (
        <Box
          sx={{
            borderTop: `1px solid ${T.divider}`,
            mx: 1.5,
            my: 1,
          }}
        />
      )}
      {/* When the whole sidebar is icon-only, ignore per-section collapse — there's
          no header to toggle it from, and the compact view should show everything. */}
      <Collapse in={collapsed || !isSectionCollapsed}>
        <List disablePadding>
          {visibleItems.map(item => (
            <NavItemWithPermission
              key={item.path}
              item={item}
              collapsed={collapsed}
              favorited={favoritePaths.includes(item.path)}
              onToggleFavorite={() => onToggleFavorite(item.path)}
            />
          ))}
        </List>
      </Collapse>
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
  const navigate = useNavigate()
  const T = useTheme().custom.sidebar

  const [favoritePaths, setFavoritePaths] = useLocalStoragePref<string[]>('sidebar_favorites', [])
  const [collapsedSections, setCollapsedSections] = useLocalStoragePref<string[]>(
    'sidebar_collapsed_sections',
    []
  )

  const toggleFavorite = (path: string) =>
    setFavoritePaths(prev => (prev.includes(path) ? prev.filter(p => p !== path) : [...prev, path]))

  const toggleSection = (label: string) =>
    setCollapsedSections(prev => (prev.includes(label) ? prev.filter(l => l !== label) : [...prev, label]))

  const allItems = useMemo(() => navSections.flatMap(s => s.items), [])
  const favoriteItems = useMemo(
    () =>
      favoritePaths
        .map(p => allItems.find(i => i.path === p))
        .filter((i): i is NavItem => Boolean(i) && isItemVisible(i!, user?.permissions, user?.roles)),
    [favoritePaths, allItems, user?.permissions, user?.roles]
  )

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
          minHeight: 96,
          borderBottom: `1px solid ${T.divider}`,
          position: 'relative',
          zIndex: 10,
          bgcolor: T.bg,
        }}
      >
        {collapsed ? (
          <LogoBadge />
        ) : (
          <>
            <ButtonBase
              aria-label="Accueil"
              onClick={(e) => { e.stopPropagation(); navigate('/') }}
              sx={{
                display: 'flex',
                alignItems: 'center',
                py: 1,
                flex: 1,
                minWidth: 0,
                borderRadius: '6px',
                mr: 1,
              }}
            >
              <img
                src="/assets/logo.png"
                alt="Motors Utilitaires"
                style={{ display: 'block', width: '92%', height: 'auto', maxHeight: 80 }}
              />
            </ButtonBase>
            <Tooltip title="Réduire le menu" placement="right">
              <IconButton
                aria-label="Réduire le menu"
                onClick={e => {
                  e.stopPropagation()
                  onToggle()
                }}
                sx={{
                  width: 28,
                  height: 28,
                  borderRadius: '6px',
                  color: T.sectionLabel,
                  border: `1px solid ${T.divider}`,
                  flexShrink: 0,
                  transition: 'all 0.15s',
                  '&:hover': { color: T.text, borderColor: T.iconColor, bgcolor: T.hover },
                }}
              >
                <ChevronLeftRoundedIcon sx={{ fontSize: 18 }} />
              </IconButton>
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
            background: 'rgba(15,23,42,0.15)',
            borderRadius: 2,
          },
        }}
      >
        {[
          ...(favoriteItems.length > 0
            ? [{ key: '__favorites__', label: FAVORITES_SECTION_LABEL, items: favoriteItems }]
            : []),
          ...navSections.map((s, i) => ({ key: `section-${i}`, label: s.label, items: s.items })),
        ].map((section, idx) => (
          <SidebarSection
            key={section.key}
            label={section.label}
            items={section.items}
            index={idx}
            collapsed={collapsed}
            isSectionCollapsed={collapsedSections.includes(section.label)}
            onToggleSection={() => toggleSection(section.label)}
            favoritePaths={favoritePaths}
            onToggleFavorite={toggleFavorite}
          />
        ))}
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
            background: 'linear-gradient(135deg, #F59E0B, #D97706)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            boxShadow: '0 2px 8px rgba(245,158,11,0.35)',
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
                color: T.activeText,
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
  const T = theme.custom.sidebar
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
