import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AppBar,
  Avatar,
  Badge,
  Box,
  Button,
  ButtonBase,
  Divider,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material'
import { inboxApi, notificationSupportsEmail } from '../../lib/notificationApi'
import { useNotificationActions } from '../../hooks/useNotificationActions'
import MenuRoundedIcon from '@mui/icons-material/MenuRounded'
import MenuOpenRoundedIcon from '@mui/icons-material/MenuOpenRounded'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import NotificationsNoneRoundedIcon from '@mui/icons-material/NotificationsNoneRounded'
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import MailRoundedIcon from '@mui/icons-material/MailRounded'
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded'
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded'
import BrightnessAutoRoundedIcon from '@mui/icons-material/BrightnessAutoRounded'
import { useAuth } from '../../contexts/AuthContext'
import { useThemeMode } from '../../contexts/ThemeModeContext'
import { navSections } from './navConfig'

const THEME_MODE_ICON = {
  light: LightModeRoundedIcon,
  dark: DarkModeRoundedIcon,
  system: BrightnessAutoRoundedIcon,
} as const

const THEME_MODE_LABEL = {
  light: 'Thème clair — cliquer pour passer au thème sombre',
  dark: 'Thème sombre — cliquer pour suivre le système',
  system: 'Thème automatique (système) — cliquer pour le thème clair',
} as const

function getPageTitle(pathname: string): string {
  for (const section of navSections) {
    for (const item of section.items) {
      if (item.exact) {
        if (pathname === item.path) return item.label
      } else {
        if (pathname === item.path || pathname.startsWith(item.path + '/')) {
          return item.label
        }
      }
    }
  }
  return 'Motors Utilitaires'
}

interface TopBarProps {
  onMenuClick: () => void
  sidebarOpen: boolean
  onSearchClick: () => void
}

export function TopBar({ onMenuClick, sidebarOpen, onSearchClick }: TopBarProps) {
  const { user, logout } = useAuth()
  const { preference, cyclePreference } = useThemeMode()
  const location = useLocation()
  const navigate = useNavigate()
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null)
  const [notifAnchor, setNotifAnchor] = useState<HTMLElement | null>(null)
  const { openNotification, markAll, sendNotificationEmail, sendingEmailId } = useNotificationActions()

  const { data: inbox } = useQuery({
    queryKey: ['notifications', 'inbox'],
    queryFn: () => inboxApi.list(),
    // Real-time delivery comes from useNotificationSocket (mounted in
    // AppShell) — this is now just a safety net for a socket that never
    // connected or silently dropped.
    refetchInterval: 5 * 60_000,
    refetchOnWindowFocus: true,
  })

  const handleOpenNotification = async (n: { id: number; link: string | null }) => {
    setNotifAnchor(null)
    await openNotification(n)
  }

  const goToNotifications = () => {
    setNotifAnchor(null)
    navigate('/notifications')
  }

  const pageTitle = getPageTitle(location.pathname)

  const initials =
    user?.full_name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2) ?? '?'

  const handleLogout = async () => {
    setAnchorEl(null)
    await logout()
    navigate('/login', { replace: true })
  }

  // Detect Mac for the shortcut hint
  const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0

  return (
    <AppBar
      position="sticky"
      elevation={0}
      sx={{
        bgcolor: 'background.paper',
        borderBottom: theme => `1px solid ${theme.palette.divider}`,
        color: 'text.primary',
        zIndex: theme => theme.zIndex.appBar,
      }}
    >
      <Toolbar sx={{ gap: 1, minHeight: '64px !important', px: { xs: 2, md: 3 } }}>
        {/* Mobile menu toggle */}
        <IconButton
          onClick={onMenuClick}
          size="small"
          sx={{ display: { xs: 'flex', md: 'none' }, color: 'text.secondary', mr: 0.5 }}
        >
          <MenuRoundedIcon />
        </IconButton>

        {/* Desktop sidebar toggle */}
        <Tooltip title={sidebarOpen ? 'Réduire' : 'Développer'} placement="bottom">
          <IconButton
            onClick={onMenuClick}
            size="small"
            sx={{ display: { xs: 'none', md: 'flex' }, color: 'text.secondary', mr: 0.5 }}
          >
            {sidebarOpen ? <MenuOpenRoundedIcon /> : <MenuRoundedIcon />}
          </IconButton>
        </Tooltip>

        {/* Page title */}
        <Typography
          variant="h6"
          fontWeight={600}
          fontSize="1rem"
          letterSpacing="-0.01em"
          sx={{ color: 'text.primary', display: { xs: 'none', sm: 'block' } }}
        >
          {pageTitle}
        </Typography>

        {/* Cmd+K search trigger — desktop only. A real button (not a bare
            Box with onClick) so it's reachable and operable by keyboard;
            the placeholder text is decorative, not a live input. */}
        <ButtonBase
          aria-label="Rechercher — Ctrl/⌘+K"
          onClick={onSearchClick}
          sx={{
            display: { xs: 'none', md: 'flex' },
            alignItems: 'center',
            gap: 1,
            ml: 2,
            px: 1.5,
            py: 0.625,
            borderRadius: 1.5,
            border: '1px solid',
            borderColor: 'divider',
            bgcolor: 'action.hover',
            minWidth: 200,
            justifyContent: 'flex-start',
            transition: 'border-color 0.15s, background-color 0.15s',
            '&:hover': { borderColor: 'text.disabled', bgcolor: 'action.selected' },
          }}
        >
          <SearchRoundedIcon sx={{ fontSize: 15, color: 'text.disabled', flexShrink: 0 }} />
          <Typography variant="body2" sx={{ flex: 1, textAlign: 'left', fontSize: '0.8125rem', color: 'text.disabled' }}>
            Rechercher…
          </Typography>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.375,
              flexShrink: 0,
            }}
          >
            <Box
              component="kbd"
              sx={{
                px: 0.5, py: 0.25,
                bgcolor: 'background.paper',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: '4px',
                fontSize: '0.6875rem',
                fontFamily: 'inherit',
                color: 'text.disabled',
                lineHeight: 1.4,
              }}
            >
              {isMac ? '⌘' : 'Ctrl'}
            </Box>
            <Box
              component="kbd"
              sx={{
                px: 0.5, py: 0.25,
                bgcolor: 'background.paper',
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: '4px',
                fontSize: '0.6875rem',
                fontFamily: 'inherit',
                color: 'text.disabled',
                lineHeight: 1.4,
              }}
            >
              K
            </Box>
          </Box>
        </ButtonBase>

        {/* Mobile search icon */}
        <IconButton
          size="small"
          onClick={onSearchClick}
          sx={{ display: { xs: 'flex', md: 'none' }, color: 'text.secondary', ml: 'auto' }}
        >
          <SearchRoundedIcon sx={{ fontSize: 20 }} />
        </IconButton>

        <Box sx={{ flex: 1, display: { xs: 'none', md: 'block' } }} />

        {/* Theme mode toggle — cycles light → dark → system */}
        <Tooltip title={THEME_MODE_LABEL[preference]} placement="bottom">
          <IconButton size="small" onClick={cyclePreference} sx={{ color: 'text.secondary' }}>
            {(() => {
              const Icon = THEME_MODE_ICON[preference]
              return <Icon sx={{ fontSize: 20 }} />
            })()}
          </IconButton>
        </Tooltip>

        {/* Notifications */}
        <Tooltip title="Notifications" placement="bottom">
          <IconButton
            size="small"
            sx={{ color: 'text.secondary' }}
            onClick={(e) => setNotifAnchor(e.currentTarget)}
          >
            <Badge badgeContent={inbox?.unread_count ?? 0} color="error" max={9}>
              <NotificationsNoneRoundedIcon sx={{ fontSize: 20 }} />
            </Badge>
          </IconButton>
        </Tooltip>
        <Menu
          anchorEl={notifAnchor}
          open={Boolean(notifAnchor)}
          onClose={() => setNotifAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          PaperProps={{ sx: { width: 360, maxHeight: 460 } }}
        >
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 2, py: 1 }}>
            <Typography variant="subtitle2" fontWeight={700}>Notifications</Typography>
            {(inbox?.unread_count ?? 0) > 0 && (
              <Button size="small" onClick={markAll} sx={{ textTransform: 'none' }}>
                Tout marquer comme lu
              </Button>
            )}
          </Stack>
          <Divider />
          {(inbox?.items ?? []).length === 0 ? (
            <Box sx={{ px: 2, py: 3, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">Aucune notification.</Typography>
            </Box>
          ) : (
            (inbox?.items ?? []).map((n) => (
              <MenuItem
                key={n.id}
                onClick={() => handleOpenNotification(n)}
                sx={{ alignItems: 'flex-start', py: 1, whiteSpace: 'normal', bgcolor: n.read_at ? 'transparent' : 'action.hover' }}
              >
                <ListItemText
                  primary={n.title}
                  secondary={
                    <>
                      {n.body}
                      <Typography component="span" variant="caption" color="text.disabled" display="block">
                        {new Date(n.created_at).toLocaleString('fr-FR')}
                      </Typography>
                      {notificationSupportsEmail(n.link) && (
                        <Stack direction="row" spacing={1} mt={0.5}>
                          <Button
                            size="small"
                            variant="text"
                            startIcon={<MailRoundedIcon fontSize="small" />}
                            disabled={sendingEmailId === n.id}
                            onClick={(e) => sendNotificationEmail(e, n.id, 'client')}
                            sx={{ textTransform: 'none', minWidth: 0, p: 0 }}
                          >
                            Email client
                          </Button>
                          <Button
                            size="small"
                            variant="text"
                            startIcon={<MailRoundedIcon fontSize="small" />}
                            disabled={sendingEmailId === n.id}
                            onClick={(e) => sendNotificationEmail(e, n.id, 'admin')}
                            sx={{ textTransform: 'none', minWidth: 0, p: 0 }}
                          >
                            Email admin
                          </Button>
                        </Stack>
                      )}
                    </>
                  }
                  primaryTypographyProps={{ fontWeight: n.read_at ? 500 : 700, variant: 'body2' }}
                  secondaryTypographyProps={{ variant: 'caption', component: 'div' }}
                />
              </MenuItem>
            ))
          )}
          <Divider />
          <MenuItem onClick={goToNotifications} sx={{ justifyContent: 'center', py: 1 }}>
            <Typography variant="body2" fontWeight={600} color="primary">
              Voir toutes les notifications
            </Typography>
          </MenuItem>
        </Menu>

        {/* User avatar */}
        <Tooltip title="Mon compte" placement="bottom">
          <IconButton
            size="small"
            onClick={e => setAnchorEl(e.currentTarget)}
            sx={{ ml: 0.5, p: 0.5 }}
          >
            <Avatar
              sx={{
                width: 32,
                height: 32,
                fontSize: '0.75rem',
                fontWeight: 700,
                color: 'primary.contrastText',
                background: theme =>
                  `linear-gradient(135deg, ${theme.palette.primary.main}, ${theme.palette.primary.dark})`,
              }}
            >
              {initials}
            </Avatar>
          </IconButton>
        </Tooltip>

        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={() => setAnchorEl(null)}
          PaperProps={{
            elevation: 3,
            sx: {
              borderRadius: 2,
              minWidth: 220,
              mt: 1,
              border: '1px solid',
              borderColor: 'divider',
              '& .MuiMenuItem-root': {
                borderRadius: 1,
                mx: 0.5,
                fontSize: '0.875rem',
              },
            },
          }}
          transformOrigin={{ horizontal: 'right', vertical: 'top' }}
          anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        >
          <Box sx={{ px: 2, py: 1.5 }}>
            <Typography variant="subtitle2" fontWeight={600} noWrap>
              {user?.full_name}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap>
              {user?.email}
            </Typography>
          </Box>
          <Divider sx={{ my: 0.5 }} />
          <MenuItem onClick={() => setAnchorEl(null)} disabled>
            <ListItemIcon>
              <PersonRoundedIcon fontSize="small" />
            </ListItemIcon>
            Mon profil
          </MenuItem>
          <Divider sx={{ my: 0.5 }} />
          <MenuItem
            onClick={handleLogout}
            sx={{ color: 'error.main', '& .MuiListItemIcon-root': { color: 'error.main' } }}
          >
            <ListItemIcon>
              <LogoutRoundedIcon fontSize="small" />
            </ListItemIcon>
            Se déconnecter
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  )
}
